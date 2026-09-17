"""Unit tests for the line-initial onset snap post-pass."""

import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from pikaraoke.lib import onset_snap
from pikaraoke.lib.onset_snap import (
    HOP_S,
    rms_envelope_db,
    snap_line_edges,
    snap_line_ends,
    snap_line_onsets,
)

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
        # Flat -50dB: the reference is -50, below MIN_REF_DB, so the
        # low-ref gate claims this line before rise detection is reached.
        use_env(np.full(200, -50.0))
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_low_ref"] == 1
        assert stats["n_fired"] == 0
        assert stats["n_snapped"] == 0

    def test_step_below_threshold_counts_no_rise(self, use_env):
        # The guard fails (-41 < ref-8 = -40) so the line fires, but the
        # only step in the search window is -41 -> -32, 9dB < STEP_DB: no
        # rise qualifies.
        use_env(_env(5.0, [(0.5, 2.5, -41.0), (2.5, 4.5, -32.0)]))
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_fired"] == 1
        assert stats["n_no_rise"] == 1
        assert stats["n_below_min_shift"] == 0
        assert stats["n_snapped"] == 0

    def test_shift_below_jitter_threshold_untouched(self, use_env):
        use_env(_env(5.0, [(1.3, 4.0, -28.0)]))
        obj = _line((1.2, 1.5), (1.8, 2.0), (2.5, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_fired"] == 1
        assert stats["n_below_min_shift"] == 1
        assert stats["n_no_rise"] == 0
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

    def test_rise_truncated_by_stem_end_rejected(self, use_env):
        # The envelope ends at 5.0s (len(env)=200, b_env=197). Word 2 starts
        # at 4.95 (b_bound=198 > b_env), so the window is env-truncated, not
        # word-2-proximate. The soft tier accepts frame 187, one hop before
        # the 4.7s step, where b - i = 10 < sustain_frames = 16 -- the trust
        # branch fires, but b_bound > b_env means it must not trust it.
        use_env(_env(5.0, [(4.7, 5.0, -20.0)]))
        obj = _line((3.0, 4.6), (4.95, 5.4))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_no_rise"] == 1

    def test_on_time_word_before_pause_untouched(self, use_env):
        # Back-to-back lines leave no quiet before word 1. An on-time
        # staccato word followed by an intra-line pause must not get
        # snapped to word 2's onset.
        use_env(_env(5.0, [(0.0, 1.5, -28.0), (2.5, 3.5, -28.0)]))
        obj = _line((1.2, 1.5), (2.5, 2.8), (3.0, 3.5))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_snapped"] == 0

    def test_line_in_silence_untouched(self, use_env):
        # Without the gate the on-time guard's start check (-60 >= ref-8)
        # is False here, so it would NOT catch this line, and the 12dB
        # bump at 2.5s would pass the rise detector and snap to 2.45 --
        # this construction actually discriminates the new gate.
        use_env(_env(8.0, [(2.5, 3.0, -48.0), (3.2, 4.0, -50.0)]))
        obj = _line((2.0, 3.0), (3.2, 3.5), (3.6, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_low_ref"] == 1
        assert stats["n_snapped"] == 0

    def test_empty_words_skipped(self, use_env):
        use_env(_env(5.0, [(2.2, 4.5, -28.0)]))
        empty = {"words": [], "start": None, "end": None}

        out, stats = snap_line_onsets([empty], "vocal.wav")

        assert out == [empty]
        assert stats["n_snapped"] == 0

    def test_single_word_smeared_start_snaps(self, use_env):
        # A single-word line's reference comes from its own claimed span
        # (80th percentile): 60 of 121 frames are the sung patch, enough
        # for the percentile to land at sung level and reject on-time.
        use_env(_env(8.0, [(3.5, 5.0, -20.0)]))
        obj = _line((2.0, 5.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(3.425, abs=0.01)
        assert out[0]["words"][0]["end"] == pytest.approx(5.0, abs=0.01)
        assert stats["n_snapped"] == 1

    def test_single_word_on_time_untouched(self, use_env):
        use_env(_env(8.0, [(2.0, 4.0, -20.0)]))
        obj = _line((2.0, 4.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_fired"] == 0

    def test_single_word_in_silence_untouched(self, use_env):
        # pct80 over a wholly-unsung span sits at the floor, below
        # MIN_REF_DB, on both the onset and end paths.
        use_env(_env(12.0, [(1.0, 4.0, -28.0)]))
        obj = _line((6.0, 7.0))

        out, stats = snap_line_onsets([obj], "vocal.wav")
        assert out[0] is obj
        assert stats["n_low_ref"] == 1

        out, stats = snap_line_ends([obj], "vocal.wav")
        assert out[0] is obj
        assert stats["n_low_ref"] == 1

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
# snap_line_ends
# ---------------------------------------------------------------------------


class TestSnapLineEnds:
    def test_clipped_held_note_extends_to_release(self, use_env):
        # Voice holds at -28dB until 4.0s but the last word's claimed end
        # is 2.5s; the end must trace the run to its release.
        use_env(_env(8.0, [(1.0, 4.0, -28.0)]))
        clipped = _line((1.0, 1.3), (1.5, 2.5), line_id=7)
        following = _line((6.0, 6.3), (6.5, 7.0))

        out, stats = snap_line_ends([clipped, following], "vocal.wav")

        w_last = out[0]["words"][-1]
        assert w_last["end"] == pytest.approx(3.9, abs=0.1)
        assert w_last["start"] == 1.5
        assert out[0]["end"] == w_last["end"]
        assert out[0]["words"][:-1] == clipped["words"][:-1]
        assert out[1] is following
        assert stats["n_fired"] == 1
        assert stats["n_extended"] == 1
        assert stats["extends"][0]["line_id"] == 7
        assert stats["extends"][0]["extend_s"] == pytest.approx(1.4, abs=0.1)
        assert stats["extends"][0]["to_bound"] is False

    def test_correct_end_untouched(self, use_env):
        # Voice falls exactly at the claimed end: no clip evidence.
        use_env(_env(8.0, [(1.0, 2.5, -28.0)]))
        obj = _line((1.0, 1.3), (1.5, 2.5))

        out, stats = snap_line_ends([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_fired"] == 0
        assert stats["n_extended"] == 0

    def test_sub_jitter_extension_untouched(self, use_env):
        # Voice runs 0.2s past the claimed end; within whisper jitter.
        use_env(_env(8.0, [(1.0, 2.7, -28.0)]))
        obj = _line((1.0, 1.3), (1.5, 2.5))

        out, stats = snap_line_ends([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_fired"] == 1
        assert stats["n_below_min_shift"] == 1
        assert stats["n_extended"] == 0

    def test_tremolo_dip_ridden_over(self, use_env):
        # A 0.1s vibrato dip mid-hold must not register as the release;
        # the trace continues to the real fall at 4.0s.
        use_env(_env(8.0, [(1.0, 2.8, -28.0), (2.8, 2.9, -45.0), (2.9, 4.0, -28.0)]))
        obj = _line((1.0, 1.3), (1.5, 2.5))

        out, _ = snap_line_ends([obj], "vocal.wav")

        assert out[0]["words"][-1]["end"] == pytest.approx(3.9, abs=0.1)

    def test_melisma_bounded_by_next_line(self, use_env):
        # Voice continuous into the next line: no release before the
        # bound, so the end extends to just short of the next first word.
        use_env(_env(12.0, [(1.0, 6.0, -28.0)]))
        melisma = _line((1.0, 1.3), (1.5, 2.5))
        nxt = _line((5.0, 5.3), (5.5, 6.0))

        out, stats = snap_line_ends([melisma, nxt], "vocal.wav")

        assert out[0]["words"][-1]["end"] == pytest.approx(4.9, abs=0.03)
        assert out[1] is nxt
        assert stats["extends"][0]["to_bound"] is True

    def test_tail_dip_at_envelope_end_not_a_release(self, use_env):
        # Voice held to the end of the stem with a 2-frame dip at the very
        # tail (a fade artifact). A truncated window there must not pass
        # for a RELEASE_SUSTAIN_S fall; the hold extends to the bound.
        env = _env(4.0, [(1.0, 4.0, -28.0)])
        env[-2:] = -45.0
        use_env(env)
        obj = _line((1.0, 1.3), (1.5, 2.5))

        out, stats = snap_line_ends([obj], "vocal.wav")

        assert out[0]["words"][-1]["end"] == pytest.approx(4.0, abs=0.03)
        assert stats["extends"][0]["to_bound"] is True

    def test_line_in_silence_untouched(self, use_env):
        # A line misplaced over digital silence has its sung reference at
        # the noise floor, where "still near sung level" is trivially
        # true; the ref floor must keep its end from being dragged to the
        # next line.
        use_env(_env(12.0, [(1.0, 4.0, -28.0)]))
        silent = _line((6.0, 6.3), (6.5, 7.0))
        nxt = _line((9.0, 9.3), (9.5, 10.0))

        out, stats = snap_line_ends([silent, nxt], "vocal.wav")

        assert out[0] is silent
        assert out[1] is nxt
        assert stats["n_low_ref"] == 2
        assert stats["n_fired"] == 0
        assert stats["n_extended"] == 0

    def test_overlapping_next_line_skipped(self, use_env):
        # Doubled-chorus lines overlap: the next line starts before this
        # line's claimed end, leaving no room to extend.
        use_env(_env(8.0, [(1.0, 3.0, -28.0)]))
        doubled = _line((1.0, 1.3), (1.5, 2.5))
        overlap = _line((2.0, 2.3), (2.5, 3.0))

        out, stats = snap_line_ends([doubled, overlap], "vocal.wav")

        assert out[0] is doubled
        assert stats["n_fired"] == 0

    def test_empty_words_skipped(self, use_env):
        use_env(_env(8.0, [(1.0, 4.0, -28.0)]))
        empty = {"words": [], "start": None, "end": None}

        out, stats = snap_line_ends([empty], "vocal.wav")

        assert out == [empty]
        assert stats["n_extended"] == 0

    def test_single_word_clipped_end_extends(self, use_env):
        use_env(_env(10.0, [(2.0, 6.0, -20.0)]))
        obj = _line((2.0, 3.0))

        out, stats = snap_line_ends([obj], "vocal.wav")

        assert out[0]["words"][-1]["end"] == pytest.approx(5.875, abs=0.01)
        assert stats["n_fired"] == 1
        assert stats["n_extended"] == 1

    def test_end_ref_includes_long_word1(self, use_env):
        # Word 1 is a long held note (1.0-3.0 at -20dB); words 2-3 are
        # short trailing words in a quieter patch (-34dB). Excluding word
        # 1 would put the reference at -34 and read the claimed end as
        # still clipped; including it puts the reference at -20 (word 1's
        # 81 frames dominate the median) and reads the end as already
        # released -- 14dB below the line's true sung level.
        use_env(_env(10.0, [(1.0, 3.0, -20.0), (3.2, 5.5, -34.0)]))
        obj = _line((1.0, 3.0), (3.2, 3.4), (3.6, 4.0))

        out, stats = snap_line_ends([obj], "vocal.wav")

        assert out[0] is obj
        assert stats["n_fired"] == 0

    def test_decode_failure_bails(self, monkeypatch):
        def boom(path):
            raise FileNotFoundError("missing.wav")

        monkeypatch.setattr(onset_snap, "rms_envelope_db", boom)
        obj = _line((1.2, 1.4), (2.5, 2.7))

        out, stats = snap_line_ends([obj], "missing.wav")

        assert out == [obj]
        assert stats["bailed"] == "decode_failed"


# ---------------------------------------------------------------------------
# snap_line_edges
# ---------------------------------------------------------------------------


class TestSnapLineEdges:
    def test_single_decode_fixes_both_edges(self, monkeypatch):
        # A line smeared early at the start AND clipped at the end must
        # come out fixed on both edges from one envelope decode.
        calls = []

        def fake_env(path):
            calls.append(path)
            return _env(8.0, [(2.2, 4.5, -28.0)])

        monkeypatch.setattr(onset_snap, "rms_envelope_db", fake_env)
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 3.2))

        out, stats = snap_line_edges([obj], "vocal.wav")

        assert len(calls) == 1
        assert out[0]["words"][0]["start"] == pytest.approx(2.15, abs=0.05)
        assert out[0]["words"][-1]["end"] == pytest.approx(4.4, abs=0.1)
        assert stats["onset"]["n_snapped"] == 1
        assert stats["end"]["n_extended"] == 1

    def test_single_word_both_edges(self, monkeypatch):
        # The held-"Oooh" showcase: both edges derived from the envelope,
        # with no words 2..n on either pass.
        def fake_env(path):
            return _env(10.0, [(3.5, 6.5, -20.0)])

        monkeypatch.setattr(onset_snap, "rms_envelope_db", fake_env)
        obj = _line((2.0, 4.5))

        out, stats = snap_line_edges([obj], "vocal.wav")

        assert out[0]["words"][0]["start"] == pytest.approx(3.425, abs=0.01)
        assert out[0]["words"][-1]["end"] == pytest.approx(6.375, abs=0.01)
        assert stats["onset"]["n_snapped"] == 1
        assert stats["end"]["n_extended"] == 1

    def test_decode_failure_bails(self, monkeypatch):
        def boom(path):
            raise FileNotFoundError("missing.wav")

        monkeypatch.setattr(onset_snap, "rms_envelope_db", boom)
        obj = _line((1.2, 1.4), (2.5, 2.7))

        out, stats = snap_line_edges([obj], "missing.wav")

        assert out == [obj]
        assert stats["bailed"] == "decode_failed"

    def test_precomputed_env_skips_decode(self, monkeypatch):
        # A caller (the stage) shares one envelope with the veto; passing it
        # in must skip the internal decode entirely.
        def boom(path):
            raise AssertionError("must not decode when env is supplied")

        monkeypatch.setattr(onset_snap, "rms_envelope_db", boom)
        env = _env(8.0, [(2.2, 4.5, -28.0)])
        obj = _line((1.2, 1.4), (2.5, 2.7), (3.0, 3.2))

        out, stats = snap_line_edges([obj], "vocal.wav", env=env)

        assert out[0]["words"][0]["start"] == pytest.approx(2.15, abs=0.05)
        assert stats["onset"]["n_snapped"] == 1


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
