"""Unit tests for the pipeline orchestrator.

The orchestrator is the integration seam of the whole pipeline: it owns
the stem/whisper worker lifecycle, runs stages in order, exposes phase to
callbacks, and surfaces per-job cancellation.  These tests drive it with
stub stages and mock workers so no real ffmpeg/whisper/stem work happens.
"""

import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import Phase, PipelineCancelled, SetEvent, StageContext
from pikaraoke.pipeline.orchestrator import PipelineOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingStage:
    """Stub stage: records that it ran (in order) and optionally runs a hook."""

    def __init__(self, name, log, hook=None):
        self.name = name
        self._log = log
        self._hook = hook

    def run(self, ctx: StageContext) -> None:
        self._log.append(self.name)
        if self._hook is not None:
            self._hook(ctx)


def _emit_phase(phase: Phase):
    """Hook that opens (and immediately closes) an activity for *phase*."""

    def hook(ctx: StageContext) -> None:
        with ctx.cancel.activity(phase, SetEvent(threading.Event())):
            pass

    return hook


def _make_orch(stages, *, on_stage_change=None, intermediate_dir=""):
    """Build an orchestrator wrapping *stages* with mock workers."""
    config = PipelineConfig(intermediate_dir=intermediate_dir)
    return PipelineOrchestrator(
        stages=stages,
        stem_worker=Mock(),
        whisper_worker=Mock(),
        config=config,
        on_stage_change=on_stage_change,
    )


@pytest.fixture
def song(tmp_path) -> Path:
    p = tmp_path / "song.mp4"
    p.write_bytes(b"\x00")
    return p


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------


class TestWorkerLifecycle:
    def test_start_is_eager_and_idempotent(self):
        orch = _make_orch([])
        orch.start()
        orch.start()  # second call is a no-op
        orch.stem_worker.start.assert_called_once()
        orch.whisper_worker.start.assert_called_once()

    def test_stop_is_idempotent(self):
        orch = _make_orch([])
        orch.start()
        orch.stop()
        orch.stop()  # second call is a no-op
        orch.stem_worker.stop.assert_called_once()
        orch.whisper_worker.stop.assert_called_once()

    def test_stop_without_start_is_noop(self):
        orch = _make_orch([])
        orch.stop()
        orch.stem_worker.stop.assert_not_called()
        orch.whisper_worker.stop.assert_not_called()

    def test_run_starts_then_stops_workers(self, song):
        log = []
        orch = _make_orch([RecordingStage("s", log)])
        orch.run(song)
        assert log == ["s"]
        orch.stem_worker.start.assert_called_once()
        orch.stem_worker.stop.assert_called_once()
        orch.whisper_worker.start.assert_called_once()
        orch.whisper_worker.stop.assert_called_once()

    def test_stop_swallows_worker_errors(self):
        orch = _make_orch([])
        orch.start()
        orch.stem_worker.stop.side_effect = RuntimeError("teardown blew up")
        orch.stop()  # must not raise
        # The whisper worker is still torn down despite the stem failure.
        orch.whisper_worker.stop.assert_called_once()

    def test_failed_second_worker_start_still_lets_stop_clean_up(self):
        # Eager start exists to surface whisper GPU-OOM at startup. When it
        # fails after the stem worker already started, a follow-up stop() must
        # still tear that stem worker down rather than leak it.
        orch = _make_orch([])
        orch.whisper_worker.start.side_effect = RuntimeError("OOM")
        with pytest.raises(RuntimeError, match="OOM"):
            orch.start()
        orch.stop()
        orch.stem_worker.stop.assert_called_once()

    def test_run_stops_workers_when_start_fails(self, song):
        orch = _make_orch([RecordingStage("s", [])])
        orch.whisper_worker.start.side_effect = RuntimeError("OOM")
        with pytest.raises(RuntimeError, match="OOM"):
            orch.run(song)
        # run() must tear down the already-started stem worker on a start failure.
        orch.stem_worker.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Stage ordering
# ---------------------------------------------------------------------------


class TestStageOrdering:
    def test_runs_stages_in_order(self, song):
        log = []
        stages = [RecordingStage(n, log) for n in ("a", "b", "c")]
        orch = _make_orch(stages)
        orch.run(song)
        assert log == ["a", "b", "c"]

    def test_workers_started_before_first_stage(self, song):
        seen = {}

        def hook(ctx):
            seen["stem_started"] = bool(orch.stem_worker.start.called)

        orch = _make_orch([RecordingStage("s", [], hook=hook)])
        orch.run(song)
        assert seen["stem_started"] is True


# ---------------------------------------------------------------------------
# Phase exposure to callbacks
# ---------------------------------------------------------------------------


class TestPhaseCallback:
    def test_phase_forwarded_to_callback(self, song):
        phases = []
        stage = RecordingStage("s", [], hook=_emit_phase(Phase.EXTRACT))
        orch = _make_orch([stage], on_stage_change=phases.append)
        orch.run(song)
        assert phases == ["extract"]

    def test_phases_forwarded_in_stage_order(self, song):
        phases = []
        stages = [
            RecordingStage("s0", [], hook=_emit_phase(Phase.EXTRACT)),
            RecordingStage("s1", [], hook=_emit_phase(Phase.LOUDNORM)),
        ]
        orch = _make_orch(stages, on_stage_change=phases.append)
        orch.run(song)
        assert phases == ["extract", "loudnorm"]

    def test_no_callback_is_safe(self, song):
        # A stage that opens an activity must not crash when on_stage_change
        # is None (the default).
        stage = RecordingStage("s", [], hook=_emit_phase(Phase.EXTRACT))
        orch = _make_orch([stage])
        ctx = orch.run(song)
        assert ctx.song_path == song


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_missing_song_raises(self, tmp_path):
        orch = _make_orch([])
        with pytest.raises(FileNotFoundError):
            orch.run(tmp_path / "nope.mp4")

    def test_missing_lyrics_raises(self, song, tmp_path):
        orch = _make_orch([])
        with pytest.raises(FileNotFoundError):
            orch.run(song, tmp_path / "nope.txt")

    def test_bad_lyrics_suffix_raises(self, song, tmp_path):
        bad = tmp_path / "lyrics.mp3"
        bad.write_text("not lyrics")
        orch = _make_orch([])
        with pytest.raises(ValueError):
            orch.run(song, bad)

    @pytest.mark.parametrize("suffix", [".txt", ".srt"])
    def test_valid_lyrics_roundtrip_into_artifacts(self, song, tmp_path, suffix):
        lyrics = tmp_path / f"lyrics{suffix}"
        lyrics.write_text("la la la")
        orch = _make_orch([RecordingStage("s", [])])
        ctx = orch.run(song, lyrics)
        assert ctx.artifacts["lyrics_path"] == lyrics

    def test_no_lyrics_stores_none(self, song):
        orch = _make_orch([RecordingStage("s", [])])
        ctx = orch.run(song)
        assert ctx.artifacts["lyrics_path"] is None


# ---------------------------------------------------------------------------
# Async execution, exceptions, and temp-dir lifecycle
# ---------------------------------------------------------------------------


class TestAsyncExecution:
    def test_join_returns_context(self, song):
        orch = _make_orch([RecordingStage("s", [])])
        orch.start()
        try:
            orch.run_one_async(song)
            ctx = orch.join(timeout=5)
        finally:
            orch.stop()
        assert ctx.song_path == song

    def test_stage_exception_propagates_through_join(self, song):
        # A stage that rejects the job by raising must surface through join,
        # untouched — this is the orchestrator's rejection seam.
        def boom(ctx):
            raise RuntimeError("rejected")

        orch = _make_orch([RecordingStage("s", [], hook=boom)])
        with pytest.raises(RuntimeError, match="rejected"):
            orch.run(song)
        # Workers were still torn down on the failure path.
        orch.stem_worker.stop.assert_called_once()

    def test_tmp_dir_created_then_cleaned_up(self, song):
        holder = {}

        def hook(ctx):
            holder["tmp"] = ctx.tmp_dir
            assert ctx.tmp_dir.exists()  # present while stages run

        orch = _make_orch([RecordingStage("s", [], hook=hook)])
        orch.run(song)
        assert not holder["tmp"].exists()  # removed afterwards

    def test_join_timeout_raises(self, song):
        release = threading.Event()

        class BlockingStage:
            name = "block"

            def run(self, ctx):
                release.wait(timeout=5)

        orch = _make_orch([BlockingStage()])
        orch.start()
        try:
            orch.run_one_async(song)
            with pytest.raises(TimeoutError):
                orch.join(timeout=0.1)
        finally:
            release.set()
            orch.join(timeout=5)  # let the thread drain
            orch.stop()


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    def test_cancel_active_stops_before_next_stage(self, song):
        log = []
        box = {}
        stage0 = RecordingStage("s0", log, hook=lambda ctx: box["orch"].cancel_active())
        stage1 = RecordingStage("s1", log)
        orch = _make_orch([stage0, stage1])
        box["orch"] = orch
        with pytest.raises(PipelineCancelled):
            orch.run(song)
        # s0 ran and cancelled; the between-stage check stops s1 from running.
        assert log == ["s0"]

    def test_cancel_active_without_job_is_noop(self):
        orch = _make_orch([])
        orch.cancel_active()  # no active token — must not raise

    def test_fresh_token_per_job(self, song):
        orch = _make_orch([RecordingStage("s", [])])
        orch.start()
        try:
            t1 = orch.run_one_async(song)
            orch.join(timeout=5)
            t2 = orch.run_one_async(song)
            orch.join(timeout=5)
        finally:
            orch.stop()
        assert t1 is not t2
        assert t1.event is not t2.event
