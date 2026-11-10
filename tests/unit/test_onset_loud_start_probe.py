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


class TestHeardNear:
    def test_a_matching_word_inside_the_tolerance(self):
        assert probe.heard_near([{"word": "Never", "start": 2.3}], "never", 2.15)

    def test_a_matching_word_outside_it(self):
        assert not probe.heard_near([{"word": "never", "start": 2.6}], "never", 2.15)

    def test_another_word_at_the_rise(self):
        assert not probe.heard_near([{"word": "mind", "start": 2.15}], "never", 2.15)


def _row(song: str, line_id: int, before: float, rise: float, agreed: bool = True) -> dict:
    return {
        "song": song,
        "line_id": line_id,
        "text": f"line {line_id}",
        "before": before,
        "rise": rise,
        "agreed": agreed,
    }


class TestWithRule:
    def test_an_agreed_line_moves_and_the_line_before_fills_the_room(self):
        # Line 0's last note is held to 1.5 s; line 1 claims 1.2 s and its voice rises at 2.2 s.
        env = _env(6.0, [(0.3, 1.5, -28.0), (2.2, 4.5, -28.0)])
        first = _line((0.3, 0.6), (0.6, 1.2), source="cue_align")
        second = {**_line((1.2, 1.6), (2.5, 2.7), (3.0, 4.0), source="cue_align"), "line_id": 1}
        _, ref = probe.onset_branch(second, env)
        rise = probe.rise_start(env, second["words"], ref)
        rows = [
            {"line_id": 0, "rise": None, "agreed": False},
            {"line_id": 1, "rise": rise, "agreed": True},
        ]

        after = probe.with_rule([first, second], rows, env)

        assert after[1]["words"][0]["start"] == pytest.approx(2.15, abs=0.05)
        # The shipped snap leaves line 0 ending at 1.2 s, against line 1's early start.
        assert after[0]["end"] == pytest.approx(1.4, abs=0.05)

    def test_no_agreed_line_is_the_shipped_snap(self):
        env = _env(6.0, [(0.3, 1.5, -28.0), (2.2, 4.5, -28.0)])
        lines = [
            _line((0.3, 0.6), (0.6, 1.2), source="cue_align"),
            {**_line((1.2, 1.6), (2.5, 2.7), (3.0, 4.0), source="cue_align"), "line_id": 1},
        ]
        rows = [
            {"line_id": 0, "rise": None, "agreed": False},
            {"line_id": 1, "rise": 2.15, "agreed": False},
        ]
        shipped, _ = snap_line_edges(lines, "", env=env, doubted_sources=probe.DOUBTED)

        assert probe.with_rule(lines, rows, env) == shipped


class TestSheetPicks:
    def test_largest_and_median_move_from_the_songs_with_the_most(self, monkeypatch):
        monkeypatch.setattr(probe, "SHEET_SONGS", 1)
        rows = [
            _row("b", 1, 10.0, 10.2),
            _row("b", 2, 20.0, 20.9),
            _row("b", 3, 30.0, 30.5),
            _row("a", 1, 10.0, 12.0),
            _row("b", 4, 40.0, 41.0, agreed=False),
        ]

        picks = probe.sheet_picks(rows, {"a", "b"})

        assert [(r["song"], r["line_id"]) for r in picks] == [("b", 2), ("b", 3)]

    def test_ties_go_by_name_and_a_one_line_song_gives_one(self, monkeypatch):
        monkeypatch.setattr(probe, "SHEET_SONGS", 1)
        rows = [_row("b", 1, 10.0, 10.2), _row("a", 1, 10.0, 10.3)]

        assert [r["song"] for r in probe.sheet_picks(rows, {"a", "b"})] == ["a"]

    def test_a_song_not_eligible_is_passed_over(self):
        rows = [_row("a", 1, 10.0, 10.3), _row("b", 1, 10.0, 10.2)]

        assert [r["song"] for r in probe.sheet_picks(rows, {"b"})] == ["b"]


class TestChangedDialogue:
    def test_positions_of_the_lines_that_differ(self):
        shipped = "[Events]\nDialogue: 0,a\nDialogue: 0,b\nDialogue: 0,c\n"
        fixed = "[Events]\nDialogue: 0,a\nDialogue: 0,B\nDialogue: 0,c\n"

        assert probe.changed_dialogue(shipped, fixed) == [1]

    def test_a_different_line_count_is_an_error(self):
        with pytest.raises(ValueError):
            probe.changed_dialogue("Dialogue: 0,a\n", "Dialogue: 0,a\nDialogue: 0,b\n")


class TestSheetHtml:
    def test_a_row_plays_both_files_from_before_the_earlier_start(self):
        row = {**_row("A <B> & C---abcdefghijk", 3, 65.0, 65.5), "text": "you & <me>"}

        page = probe.sheet_html([row], {row["song"]: "A <B> & C---abcdefghijk.mp4"})

        assert "you &amp; &lt;me&gt;" in page
        assert "<td>1:05.00</td><td>1:05.50</td><td>+0.50</td>" in page
        assert page.count("mpv --start=61.0") == 2
        assert 'karaoke/A &lt;B&gt; &amp; C---abcdefghijk.onsetfix.ass"' in page


class TestWriteListenFiles:
    def test_writes_the_after_file_and_the_sheet_and_no_lyric_text_in_the_table(self, tmp_path):
        folder, out = tmp_path / "songs", tmp_path / "out"
        (folder / "karaoke").mkdir(parents=True)
        song = "A [live]---abcdefghijk"
        (folder / f"{song}.mp4").write_bytes(b"")
        (folder / "karaoke" / f"{song}.ass").write_text("Dialogue: 0,old\n", encoding="utf-8")
        rows = [{**_row(song, 0, 1.2, 2.15), "text": "secret words"}]

        table = probe.write_listen_files(folder, out, rows, {song: "Dialogue: 0,new\n"})

        fixed = folder / "karaoke" / f"{song}.onsetfix.ass"
        assert fixed.read_text(encoding="utf-8") == "Dialogue: 0,new\n"
        assert (folder / "karaoke" / f"{song}.ass").read_text(
            encoding="utf-8"
        ) == "Dialogue: 0,old\n"
        assert "secret words" in (out / "listening-sheet.html").read_text(encoding="utf-8")
        assert "secret words" not in table
        assert "| 1 | abcdefghijk | 0 | 1.20 | 2.15 | 1 | 1 |" in table
