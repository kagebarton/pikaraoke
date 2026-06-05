"""Unit tests for pipeline config defaults and context/cancellation scaffolding.

These pin the corpus-tuned tunables in ``config.py`` (so a stray edit can't
silently regress the matcher knobs) and exercise the cancellation contract in
``context.py`` that every stage and the orchestrator rely on.
"""

import threading

import pytest

from pikaraoke.pipeline.config import PipelineConfig, WhisperModelConfig
from pikaraoke.pipeline.context import (
    CancelToken,
    Phase,
    PipelineCancelled,
    StageContext,
)


class TestPipelineConfigDefaults:
    """Pin the tunables the stages and matchers read straight off the config."""

    def test_match_method_defaults_to_auto(self):
        assert PipelineConfig().match_method == "auto"

    def test_joint_knobs_are_corpus_tuned(self):
        # joint_alpha ships at the 2.0 sweep result, NOT the 4.0 design prior;
        # joint_margin_s reuses the prior repair-margin. Stages read these directly.
        cfg = PipelineConfig()
        assert cfg.joint_alpha == 2.0
        assert cfg.joint_margin_s == 0.3

    def test_auto_escalation_thresholds(self):
        cfg = PipelineConfig()
        assert cfg.align_failure_escalation == 0.1
        assert cfg.collapse_escalation_threshold == 0.15

    def test_loudnorm_targets(self):
        cfg = PipelineConfig()
        assert cfg.loudnorm_target_i == -24.0
        assert cfg.loudnorm_target_tp == -2.0
        assert cfg.loudnorm_target_lra == 7.0

    def test_capture_alignment_debug_on_by_default(self):
        assert PipelineConfig().capture_alignment_debug is True

    def test_whisper_subconfig_is_populated(self):
        cfg = PipelineConfig()
        assert isinstance(cfg.whisper, WhisperModelConfig)
        # A couple of the sung-vocal tunings the worker depends on.
        assert cfg.whisper.align.token_step == 150
        assert cfg.whisper.transcribe.condition_on_previous_text is False

    def test_nested_configs_are_not_shared_between_instances(self):
        # default_factory (not a mutable default): each PipelineConfig owns its
        # own whisper sub-tree, so tuning one instance can't bleed into another.
        a = PipelineConfig()
        b = PipelineConfig()
        assert a.whisper is not b.whisper
        assert a.whisper.align is not b.whisper.align


class _RecordingCancellable:
    """Cancellable test double that records whether cancel() was called."""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class TestStageContext:
    """The per-job context the stages mutate as they run."""

    def test_defaults(self, tmp_path):
        ctx = StageContext(
            song_path=tmp_path / "song.mp4", tmp_dir=tmp_path, config=PipelineConfig()
        )
        assert ctx.artifacts == {}
        assert ctx.cancel is None

    def test_artifacts_are_per_instance(self, tmp_path):
        a = StageContext(song_path=tmp_path / "a", tmp_dir=tmp_path, config=PipelineConfig())
        b = StageContext(song_path=tmp_path / "b", tmp_dir=tmp_path, config=PipelineConfig())
        a.artifacts["stem"] = "vocal.m4a"
        assert b.artifacts == {}


class TestPipelineCancelled:
    """The exception stage code catches/re-raises across phase boundaries."""

    def test_message_includes_phase(self):
        exc = PipelineCancelled(Phase.EXTRACT)
        assert exc.phase is Phase.EXTRACT
        assert "extract" in str(exc)

    def test_message_without_phase(self):
        exc = PipelineCancelled()
        assert exc.phase is None
        assert "cancelled" in str(exc).lower()


class TestCancelToken:
    """The cancellation state machine the orchestrator drives the stages with."""

    @staticmethod
    def _token():
        return CancelToken(event=threading.Event())

    def test_starts_uncancelled(self):
        tok = self._token()
        assert tok.is_cancelled() is False
        tok.check_cancelled()  # must not raise

    def test_check_cancelled_raises_after_cancel(self):
        tok = self._token()
        tok.cancel()
        assert tok.is_cancelled() is True
        with pytest.raises(PipelineCancelled):
            tok.check_cancelled()

    def test_cancel_signals_active_target_and_raises_on_exit(self):
        # cancel() sets the flag, calls target.cancel(), and the activity's exit
        # synthesises PipelineCancelled because the body finished without error.
        tok = self._token()
        target = _RecordingCancellable()
        with pytest.raises(PipelineCancelled):
            with tok.activity(Phase.STEM_SEPARATION, target):
                tok.cancel()
                assert target.cancelled is True

    def test_cancel_before_activity_raises_immediately(self):
        tok = self._token()
        tok.cancel()
        with pytest.raises(PipelineCancelled):
            with tok.activity(Phase.ALIGN, _RecordingCancellable()):
                pytest.fail("activity body must not run after a pre-cancel")

    def test_activity_does_not_mask_body_exception(self):
        # If the body raises, that error propagates even when cancelled — the
        # exit check only synthesises when the body completed cleanly.
        tok = self._token()
        with pytest.raises(ValueError):
            with tok.activity(Phase.REFINE, _RecordingCancellable()):
                tok.cancel()
                raise ValueError("boom")

    def test_activity_clears_active_target_on_clean_exit(self):
        tok = self._token()
        target = _RecordingCancellable()
        with tok.activity(Phase.LOUDNORM, target):
            assert tok.active is target
        assert tok.active is None

    def test_on_phase_change_callback_fires_with_phase_value(self):
        seen = []
        tok = self._token()
        tok.on_phase_change = seen.append
        with tok.activity(Phase.EXTRACT, _RecordingCancellable()):
            pass
        assert seen == ["extract"]
