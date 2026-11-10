"""Tests for the pure parts of scripts/onset_loud_start_probe.py, on made-up values.

No library and no audio: envelopes and lines are built by hand.
"""

import numpy as np
import pytest

from pikaraoke.lib.onset_snap import HOP_S, snap_line_edges, snap_line_onsets
from scripts import onset_loud_start_probe as probe


def _env(total_s: float, segments: list[tuple[float, float, float]]) -> np.ndarray:
    """dB envelope: -60 everywhere except the given (t0, t1, level) spans."""
    env = np.full(int(total_s / HOP_S), -60.0)
    for t0, t1, level in segments:
        env[int(t0 / HOP_S) : int(t1 / HOP_S)] = level
    return env


def _line(*spans: tuple[float, float], **extra) -> dict:
    words = [{"word": f"w{i}", "start": s, "end": e} for i, (s, e) in enumerate(spans)]
    return {"line_id": 0, "words": words, "start": spans[0][0], "end": spans[-1][1], **extra}


# The previous line's note is held to 1.5 s and this line's voice rises at 2.2 s.
HELD_NOTE = [(0.0, 1.5, -28.0), (2.2, 4.5, -28.0)]


class TestHeardFirst:
    def test_takes_the_matching_word_nearest_the_anchor(self):
        heard = [
            {"word": "Never", "start": 10.0},
            {"word": "mind,", "start": 10.4},
            {"word": "never", "start": 12.5},
        ]

        assert probe.heard_first(heard, "never", 12.0) == 12.5

    def test_ignores_case_and_punctuation(self):
        assert probe.heard_first([{"word": "Don't,", "start": 5.0}], "don't", 5.2) == 5.0

    def test_no_match_inside_the_window(self):
        heard = [{"word": "never", "start": 20.0}, {"word": "mind", "start": 10.0}]

        assert probe.heard_first(heard, "never", 10.0) is None

    def test_a_first_word_with_no_letters_has_no_heard_word(self):
        assert probe.heard_first([{"word": "...", "start": 1.0}], "...", 1.0) is None


class TestOnsetBranch:
    @pytest.mark.parametrize(
        "segments, spans, source, expected",
        [
            (HELD_NOTE, [(1.2, 1.6), (2.5, 2.7), (3.0, 4.0)], "cue_align", "on_time"),
            (HELD_NOTE, [(1.2, 1.6), (2.5, 2.7), (3.0, 4.0)], "cue_align_line", "snapped"),
            ([(2.2, 4.5, -28.0)], [(1.2, 2.4), (2.5, 2.7), (3.0, 4.0)], "cue_align", "snapped"),
            (
                [(2.2, 4.5, -28.0)],
                [(2.1, 2.4), (2.5, 2.7), (3.0, 4.0)],
                "cue_align",
                "below_min_shift",
            ),
            ([(0.0, 5.0, -28.0)], [(1.2, 1.25), (1.25, 2.7)], "cue_align", "narrow"),
            ([], [(1.2, 1.6), (2.5, 2.7)], "cue_align", "low_ref"),
        ],
    )
    def test_names_the_exit_the_snap_takes(self, segments, spans, source, expected):
        env = _env(5.0, segments)
        obj = _line(*spans, source=source)

        branch, _ = probe.onset_branch(obj, env)
        _, stats = snap_line_onsets([obj], "", env=env, doubted_sources=probe.DOUBTED)

        assert branch == expected
        assert stats["n_snapped"] == (1 if expected == "snapped" else 0)

    def test_no_rise_when_the_gap_never_falls_ten_db(self):
        env = _env(5.0, [(2.2, 4.5, -28.0)])
        ramp = slice(int(1.2 / HOP_S), int(2.2 / HOP_S))
        env[ramp] = np.linspace(-45.0, -28.0, ramp.stop - ramp.start)

        assert probe.onset_branch(_line((1.2, 2.4), (2.5, 2.7), (3.0, 4.0)), env)[0] == "no_rise"


class TestRiseStart:
    def test_a_skipped_line_has_a_rise_to_move_to(self):
        env = _env(5.0, HELD_NOTE)
        obj = _line((1.2, 1.6), (2.5, 2.7), (3.0, 4.0), source="cue_align")
        _, ref = probe.onset_branch(obj, env)

        assert probe.rise_start(env, obj["words"], ref) == pytest.approx(2.15, abs=0.05)

    def test_continuous_singing_has_none(self):
        env = _env(5.0, [(0.0, 4.5, -28.0)])
        obj = _line((1.2, 1.6), (2.5, 2.7), (3.0, 4.0), source="cue_align")
        _, ref = probe.onset_branch(obj, env)

        assert probe.rise_start(env, obj["words"], ref) is None


class TestCompare:
    @pytest.mark.parametrize(
        "new_start, expected", [(2.1, "closer"), (1.22, "same"), (3.6, "further")]
    )
    def test_against_the_start_before_the_snap(self, new_start, expected):
        assert probe.compare({"heard": 2.2, "before": 1.2}, new_start) == expected


class TestReplaySong:
    def _bundle(self, sections: list[dict], recorded: list[dict], n_snapped: int) -> dict:
        return {
            "cue_inputs": {
                "spans": [(s["start"], s["end"]) for s in sections],
                "sections": sections,
                "realigns": [],
            },
            "lyrics": {
                "lines": [s["text"] for s in sections],
                "align_lines": [s["text"] for s in sections],
            },
            "media_duration_s": 10.0,
            "output_line_timings": recorded,
            "joint_stats": {"edge_snap": {"onset": {"n_snapped": n_snapped}}},
        }

    def _section(self) -> dict:
        words = [
            {"word": "never", "start": 1.2, "end": 2.4},
            {"word": "mind", "start": 2.5, "end": 2.7},
            {"word": "it", "start": 3.0, "end": 4.0},
        ]
        return {
            "line_id": 0,
            "text": "never mind it",
            "words": words,
            "start": 1.2,
            "end": 4.0,
            "source": "cue_align",
        }

    def test_a_replay_equal_to_the_bundle_is_returned(self):
        env = _env(10.0, [(2.2, 4.0, -28.0)])
        snapped, _ = snap_line_edges([self._section()], "", env=env)
        recorded = [{"line_id": 0, "start": snapped[0]["start"], "end": snapped[0]["end"]}]

        before, after = probe.replay_song(self._bundle([self._section()], recorded, 1), env)

        assert before[0]["words"][0]["start"] == 1.2
        assert after[0]["words"][0]["start"] == pytest.approx(2.15, abs=0.05)

    def test_a_line_off_its_recorded_time_leaves_the_song_out(self):
        env = _env(10.0, [(2.2, 4.0, -28.0)])
        recorded = [{"line_id": 0, "start": 1.2, "end": 4.0}]

        assert probe.replay_song(self._bundle([self._section()], recorded, 1), env) is None

    def test_a_different_snap_count_leaves_the_song_out(self):
        env = _env(10.0, [(2.2, 4.0, -28.0)])
        recorded = [{"line_id": 0, "start": 2.15, "end": 4.0}]

        assert probe.replay_song(self._bundle([self._section()], recorded, 0), env) is None
