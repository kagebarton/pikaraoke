"""Unit tests for the line-initial onset snap post-pass."""

import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from pikaraoke.lib import onset_snap
from pikaraoke.lib.onset_snap import HOP_S, rms_envelope_db, snap_line_onsets

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env(total_s: float, segments: list[tuple[float, float, float]]) -> np.ndarray:
    """dB envelope: -60 everywhere except the given (t0, t1, level) spans."""
    env = np.full(int(total_s / HOP_S), -60.0)
    for t0, t1, level in segments:
        env[int(t0 / HOP_S) : int(t1 / HOP_S)] = level
    return env


def _line(*spans: tuple[float, float], **extra) -> dict:
    words = [{"word": f"w{i}", "start": s, "end": e} for i, (s, e) in enumerate(spans)]
    return {
        "words": words,
        "start": words[0]["start"] if words else None,
        "end": words[-1]["end"] if words else None,
        **extra,
    }


@pytest.fixture
def use_env(monkeypatch):
    """Inject a synthetic envelope in place of the ffmpeg decode."""

    def _install(env: np.ndarray) -> None:
        monkeypatch.setattr(onset_snap, "rms_envelope_db", lambda path: env)

    return _install


# ---------------------------------------------------------------------------
# snap_line_onsets
# ---------------------------------------------------------------------------


class TestSnapLineOnsets:
    def test_reverb_tail_start_snaps_to_rise(self, use_env):
        # Previous line to 1.0s, -40dB tail to 2.2s, voice at -28dB after.
        use_env(_env(5.0, [(0.0, 1.0, -30.0), (1.0, 2.2, -40.0), (2.2, 4.5, -28.0)]))
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 4.0), line_id=3)
        obj["words"][0]["probability"] = 0.9

        out, stats = snap_line_onsets([obj], "vocal.wav")

        w1 = out[0]["words"][0]
        assert w1["start"] == pytest.approx(2.15, abs=0.05)
        # Original end sat inside the gap: duration carried forward instead.
        assert w1["end"] == pytest.approx(w1["start"] + 0.2, abs=0.05)
        assert w1["probability"] == 0.9
        assert out[0]["start"] == w1["start"]
        assert out[0]["words"][1:] == obj["words"][1:]
        assert stats["n_snapped"] == 1
        assert stats["snaps"][0]["line_id"] == 3
        assert stats["snaps"][0]["shift_s"] == pytest.approx(0.95, abs=0.05)

    def test_plausible_end_is_kept(self, use_env):
        use_env(_env(5.0, [(1.0, 2.2, -40.0), (2.2, 4.5, -28.0)]))
        obj = _line((1.2, 3.4), (3.5, 3.7), (3.8, 4.0))

        out, _ = snap_line_onsets([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(2.15, abs=0.05)
        assert out[0]["words"][0]["end"] == 3.4

    def test_on_time_line_untouched(self, use_env):
        use_env(_env(5.0, [(1.2, 4.0, -28.0)]))
        obj = _line((1.2, 1.5), (1.8, 2.0), (2.5, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_snapped"] == 0

    def test_no_rise_untouched(self, use_env):
        use_env(np.full(200, -50.0))
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_snapped"] == 0

    def test_shift_below_jitter_threshold_untouched(self, use_env):
        use_env(_env(5.0, [(1.3, 4.0, -28.0)]))
        obj = _line((1.2, 1.5), (1.8, 2.0), (2.5, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_snapped"] == 0

    def test_gap_artifact_below_sung_level_rejected(self, use_env):
        # A -45dB bump mid-gap is a >10dB step but lands far below the
        # line's -28dB sung level; the snap must wait for the real rise.
        use_env(_env(5.0, [(1.5, 1.9, -45.0), (2.2, 4.5, -28.0)]))
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 4.0))

        out, _ = snap_line_onsets([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(2.15, abs=0.05)

    def test_soft_pickup_word_accepted(self, use_env):
        # A quietly sung pickup ("I'm doing...") sits well below the
        # line's belted level but sustains; the snap must land on it,
        # not skip ahead to the louder continuation at 2.6s.
        use_env(_env(5.0, [(2.0, 2.5, -38.0), (2.6, 4.5, -28.0)]))
        obj = _line((1.2, 1.4), (2.9, 3.1), (3.3, 4.0))

        out, _ = snap_line_onsets([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(1.95, abs=0.05)

    def test_unsustained_soft_bump_rejected(self, use_env):
        # A breath bump has the same soft level but dies immediately;
        # the snap must wait for the real rise at 2.6s.
        use_env(_env(5.0, [(2.0, 2.1, -38.0), (2.6, 4.5, -28.0)]))
        obj = _line((1.2, 1.4), (2.9, 3.1), (3.3, 4.0))

        out, _ = snap_line_onsets([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(2.55, abs=0.05)

    def test_stretched_word_over_tail_and_silence_snaps(self, use_env):
        # Word 1 stretched from the previous line's loud, bumpy reverb
        # tail across silence to just before word 2 (Bye Bye Bye's 5s
        # {\kf498}). Three traps at once: the tail at the claimed start
        # is within NEAR_SUNG_DB of the sung level (the on-time guard
        # must see the span collapse and not fire); word 1's own span
        # must not drag the sung-level reference down; and the tail's
        # sustained bump at 1.6s must fail the continuity-to-word-2
        # check so the snap reaches the real onset at 4.2s.
        use_env(
            _env(
                7.0,
                [
                    (0.0, 1.0, -28.0),
                    (1.0, 1.4, -30.0),
                    (1.6, 2.2, -27.0),
                    (2.2, 4.2, -90.0),
                    (4.2, 5.5, -26.0),
                ],
            )
        )
        obj = _line((1.05, 4.3), (4.4, 4.7))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        w1 = out[0]["words"][0]
        assert w1["start"] == pytest.approx(4.15, abs=0.05)
        assert w1["end"] == 4.3
        assert stats["n_snapped"] == 1

    def test_soft_rise_just_before_word2_accepted(self, use_env):
        # A soft attack landing within the sustain window of word 2
        # ("A" right before "kingdom") is already continuous with it;
        # the continuity median over that sliver must not reject it.
        use_env(_env(5.0, [(2.3, 2.375, -42.0), (2.375, 2.5, -52.0), (2.5, 3.5, -28.0)]))
        obj = _line((1.0, 2.4), (2.5, 2.8), (3.0, 3.5))

        out, _ = snap_line_onsets([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(2.25, abs=0.05)

    def test_on_time_word_before_pause_untouched(self, use_env):
        # Back-to-back lines leave no quiet before word 1. An on-time
        # staccato word followed by an intra-line pause must not get
        # snapped to word 2's onset.
        use_env(_env(5.0, [(0.0, 1.5, -28.0), (2.5, 3.5, -28.0)]))
        obj = _line((1.2, 1.5), (2.5, 2.8), (3.0, 3.5))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_snapped"] == 0

    def test_short_lines_skipped(self, use_env):
        use_env(_env(5.0, [(2.2, 4.5, -28.0)]))
        one_word = _line((1.2, 1.4))
        empty = {"words": [], "start": None, "end": None}

        out, stats = snap_line_onsets([one_word, empty], "vocal.wav")

        assert out == [one_word, empty]
        assert stats["n_snapped"] == 0

    @pytest.mark.parametrize(
        "exc",
        [
            FileNotFoundError("missing.wav"),
            PermissionError("ffmpeg not executable"),
            subprocess.CalledProcessError(1, "ffmpeg"),
        ],
    )
    def test_decode_failure_bails(self, monkeypatch, exc):
        # Any ffmpeg failure (missing, non-executable, nonzero exit) must
        # bail gracefully, not crash the alignment stage.
        def boom(path):
            raise exc

        monkeypatch.setattr(onset_snap, "rms_envelope_db", boom)
        obj = _line((1.2, 1.4), (2.5, 2.7))

        out, stats = snap_line_onsets([obj], "missing.wav")

        assert out == [obj]
        assert stats["bailed"] == "decode_failed"


# ---------------------------------------------------------------------------
# rms_envelope_db
# ---------------------------------------------------------------------------


class TestRmsEnvelopeDb:
    def _run_with_pcm(self, monkeypatch, samples: np.ndarray) -> np.ndarray:
        def fake_run(cmd, capture_output, check):
            return SimpleNamespace(stdout=samples.astype(np.int16).tobytes())

        monkeypatch.setattr(onset_snap.subprocess, "run", fake_run)
        return rms_envelope_db("vocal.wav")

    def test_full_scale_and_silence_levels(self, monkeypatch):
        # 1s full-scale square wave then 1s silence at 16kHz.
        loud = np.full(16000, 32767)
        quiet = np.zeros(16000)
        env = self._run_with_pcm(monkeypatch, np.concatenate([loud, quiet]))

        assert env[2] == pytest.approx(0.0, abs=0.1)
        assert env[-2] == pytest.approx(-120.0, abs=1.0)

    def test_too_short_input(self, monkeypatch):
        env = self._run_with_pcm(monkeypatch, np.zeros(100))
        assert len(env) == 1
        assert env[0] == -120.0

    def test_decode_error_propagates(self, monkeypatch):
        def fake_run(cmd, capture_output, check):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(onset_snap.subprocess, "run", fake_run)
        with pytest.raises(subprocess.CalledProcessError):
            rms_envelope_db("bad.m4a")
