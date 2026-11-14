"""Unit tests for scripts/cue_heard_probe.py: made-up bundles, a silent envelope, no audio."""

import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pikaraoke.lib import cue_align, heard_lines
from pikaraoke.lib.alignment_capture import output_line_timings
from pikaraoke.lib.onset_snap import HOP_S

# scripts/ is not a package: load the module straight from its file (registered in
# sys.modules first so its dataclasses can resolve their own module).
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cue_heard_probe.py"
_spec = importlib.util.spec_from_file_location("cue_heard_probe", _SCRIPT)
probe = importlib.util.module_from_spec(_spec)
sys.modules["cue_heard_probe"] = probe
_spec.loader.exec_module(probe)

STEM = "Made Up Song---abcdefghijk"
DURATION = 60.0
ENV = np.full(int(DURATION / HOP_S), -70.0)  # silent: no singing end, nothing to snap to


def _words(*spans: tuple[str, float, float]) -> list[dict]:
    return [{"word": w, "start": s, "end": e} for w, s, e in spans]


def _spans(text: str, start: float) -> list[tuple[str, float, float]]:
    """The tokens of ``text`` sung from ``start``, 0.3 s each, 0.4 s apart."""
    return [(tok, start + 0.4 * i, start + 0.4 * i + 0.3) for i, tok in enumerate(text.split())]


def _sung(text: str, start: float) -> list[dict]:
    return _words(*_spans(text, start))


def _line(lid: int, text: str, *spans: tuple[str, float, float]) -> dict:
    words = _words(*spans)
    return {
        "line_id": lid,
        "text": text,
        "words": words,
        "start": words[0]["start"] if words else None,
        "end": words[-1]["end"] if words else None,
        "source": cue_align.SOURCE,
    }


def _anchor_lines(n: int = 4) -> tuple[list[dict], list, list[str]]:
    """n cleanly-aligned two-word lines at cues (2i, 2i+1)."""
    objs, cues, lines = [], [], []
    for i in range(n):
        c0 = 2.0 * i
        cues.append((c0, c0 + 1.0))
        lines.append("a a")
        objs.append(_line(i, "a a", ("a", c0, c0 + 0.3), ("a", c0 + 0.4, c0 + 0.8)))
    return objs, cues, lines


def _make_song(objs, cues, lines, heard, answer=None, origin="srt") -> "probe.Song":
    """A bundle for the first pass ``objs``. ``answer(line_id, w0, w1)`` is the aligner that
    made the saved re-aligns (it may return None, a failed align; without it the bundle holds
    no answers at all); the baseline's output timings are what the probe's own baseline replay
    gives, so the bundle is consistent by construction."""
    bundle = {
        "lyrics": {"origin": origin, "lines": lines, "align_lines": lines},
        "cue_inputs": {"spans": cues, "sections": objs, "realigns": []},
        "transcribe_words": heard,
        "joint_stats": {},
        "output_line_timings": [],
    }
    kind = probe.LRCLIB if origin.startswith("lrclib") else probe.CAPTION
    song = probe.Song(STEM, kind, bundle)
    for _ in range(4 if answer else 0):  # an answer can lead the rescue to ask again
        asked = {
            (c.line_id, c.w0, c.w1)
            for heard_flag in (False, True)
            for c in probe.replay(song, Path("stem.m4a"), ENV, DURATION, heard=heard_flag).calls
            if not c.answered
        }
        if not asked:
            break
        for lid, w0, w1 in sorted(asked):
            words = answer(lid, w0, w1)
            bundle["cue_inputs"]["realigns"].append(
                {"line_id": lid, "w0": w0, "w1": w1, "words": words}
            )
    baseline = probe.replay(song, Path("stem.m4a"), ENV, DURATION, heard=False)
    bundle["output_line_timings"] = output_line_timings(list(baseline.final.values()))
    return song


@pytest.fixture
def analyse(tmp_path, monkeypatch):
    """``analyse(song)``: the probe's analysis of ``song`` in a library with its stem."""
    stem_dir = tmp_path / "vocal"
    stem_dir.mkdir()
    (stem_dir / f"{STEM}---vocal.m4a").touch()
    monkeypatch.setattr(probe, "load_envelope", lambda stem_file, cache_dir: (ENV, DURATION))
    return lambda song: probe.analyse_song(tmp_path, tmp_path / "env", song)


def _repeat_song(off: float = 0.05):
    """Four anchors plus two identical lines cued at 12 and 14 but sung 3 s earlier (where
    the first pass put them), heard there ``off`` s late."""
    objs, cues, lines = _anchor_lines(4)
    heard: list[dict] = []
    for lid, (cue, sung) in enumerate(((12.0, 9.0), (14.0, 11.0)), start=4):
        cues.append((cue, cue + 1.0))
        lines.append("zim zam")
        objs.append(
            _line(lid, "zim zam", ("zim", sung, sung + 0.3), ("zam", sung + 0.4, sung + 0.8))
        )
        heard += _words(
            ("zim", sung + off, sung + off + 0.3), ("zam", sung + off + 0.4, sung + off + 0.8)
        )
    return objs, cues, lines, heard


def _one_line_song(cue, *placed, text="ee ff gg"):
    """Four anchors plus line 4, cued over ``cue`` and holding ``placed`` words."""
    objs, cues, lines = _anchor_lines(4)
    cues.append(cue)
    lines.append(text)
    objs.append(_line(4, text, *placed))
    return objs, cues, lines


def _free_stretch_song(bad=("ee ff gg",)):
    """Four anchors (the last ends at 6.8), the ``bad`` lines with no words (cued from 8-9.5,
    each next 2 s later), then a clean line "a a" at 20 s: rule C's free stretch."""
    objs, cues, lines = _anchor_lines(4)
    for i, text in enumerate(bad):
        cues.append((8.0 + 2.0 * i, 9.5 + 2.0 * i))
        lines.append(text)
        objs.append(_line(4 + i, text))
    cues.append((20.0, 21.0))
    lines.append("a a")
    objs.append(_line(4 + len(bad), "a a", ("a", 20.1, 20.4), ("a", 20.5, 20.9)))
    return objs, cues, lines


class TestAnswers:
    SAVED = [
        {"line_id": 4, "w0": 7.0, "w1": 10.0, "words": [{"word": "x"}]},
        {"line_id": 4, "w0": 12.0, "w1": 15.0, "words": None},
    ]

    def test_a_call_is_answered_by_its_line_and_window_not_its_line_alone(self):
        answers = probe.Answers(self.SAVED)
        assert answers(4, 7.0, 10.0) == [{"word": "x"}]
        assert answers(4, 12.0, 15.0) is None  # the saved answer was a failed align
        assert [c.answered for c in answers.calls] == [True, True]

    def test_a_call_with_no_saved_answer_returns_none_and_is_recorded_unanswered(self):
        answers = probe.Answers(self.SAVED)
        assert answers(4, 7.0, 10.5) is None
        assert answers(5, 7.0, 10.0) is None
        assert answers.calls == [probe.Call(4, 7.0, 10.5, False), probe.Call(5, 7.0, 10.0, False)]

    def test_an_answer_is_a_copy(self):
        answers = probe.Answers(self.SAVED)
        answers(4, 7.0, 10.0)[0]["word"] = "changed"
        assert self.SAVED[0]["words"] == [{"word": "x"}]


class TestWorstDeviation:
    SAVED = [
        {"line_id": 0, "start": 1.0, "end": 2.0, "n_words": 2},
        {"line_id": 1, "start": None, "end": None, "n_words": 0},
    ]

    @staticmethod
    def _final(start=1.0, end=2.0, hidden=True, n_words=2):
        return {
            0: {"start": start, "end": end, "words": [{}] * n_words},
            1: {"start": None, "end": None, "words": []}
            if hidden
            else {"start": 3.0, "end": 4.0, "words": []},
        }

    def test_a_replay_within_the_tolerance_agrees_and_just_outside_it_does_not(self):
        # one envelope frame (0.025 s) agrees; 0.027 s does not
        assert probe.worst_deviation(self._final(start=1.025), self.SAVED) is None
        assert probe.worst_deviation(self._final(start=1.027), self.SAVED).field == "start"

    def test_the_largest_difference_is_named(self):
        dev = probe.worst_deviation(self._final(start=1.2, end=2.5), self.SAVED)
        assert (dev.line_id, dev.field) == (0, "end")
        assert str(dev) == "line 0 end off by 0.500 s"

    def test_a_word_count_or_a_vanished_line_is_a_difference(self):
        assert probe.worst_deviation(self._final(n_words=3), self.SAVED).field == "n_words"
        assert probe.worst_deviation(self._final(hidden=False), self.SAVED).amount == float("inf")

    def test_other_line_ids_are_a_difference(self):
        assert probe.worst_deviation({0: self._final()[0]}, self.SAVED).field == "line ids"


class TestBaselineReplay:
    def test_the_baseline_asks_the_cue_window_only_and_the_new_replay_also_the_stretch(self):
        objs, cues, lines = _free_stretch_song()
        song = probe.Song(
            STEM,
            probe.CAPTION,
            {
                "lyrics": {"lines": lines, "align_lines": lines},
                "cue_inputs": {"spans": cues, "sections": objs, "realigns": []},
                "transcribe_words": [],
            },
        )
        for heard, n_calls in ((False, 1), (True, 2)):
            answers = probe.Answers([])
            _, stats = probe.rescue_song(song, ENV, DURATION, answers, heard=heard)
            assert len(answers.calls) == n_calls
            assert stats["gap_retry_line_ids"] == ([4] if heard else [])

    def test_the_baseline_leaves_a_crammed_lines_zero_length_words_and_the_new_replay_retimes_them(
        self,
    ):
        objs, cues, lines = _one_line_song(
            (8.0, 12.0),
            ("ee", 8.0, 8.3),
            ("ff", 8.3, 8.3),
            ("gg", 8.3, 8.3),
            ("hh", 8.3, 8.8),
            text="ee ff gg hh",
        )
        song = probe.Song(
            STEM,
            probe.CAPTION,
            {
                "lyrics": {"lines": lines, "align_lines": lines},
                "cue_inputs": {"spans": cues, "sections": objs, "realigns": []},
                "transcribe_words": [],
            },
        )
        before, stats = probe.rescue_song(song, ENV, DURATION, probe.Answers([]), heard=False)
        assert before[4]["words"] == objs[4]["words"] and stats["n_guessed_words"] == 0
        after, stats = probe.rescue_song(song, ENV, DURATION, probe.Answers([]), heard=True)
        assert after[4]["words"] != objs[4]["words"] and stats["n_guessed_words"] == 2

    def test_the_patches_are_undone_afterwards(self):
        original = cue_align._Rescue.gap_retry_line
        with probe.before_rule_c_and_zero_length():
            assert cue_align._Rescue.gap_retry_line is not original
        assert cue_align._Rescue.gap_retry_line is original
        assert cue_align._timed_slots.__name__ == "_timed_slots"


class TestLeftOut:
    def test_a_song_whose_stem_is_missing_is_left_out(self, tmp_path):
        song = _make_song(*_anchor_lines(4), heard=[])
        result = probe.analyse_song(tmp_path, tmp_path / "env", song)
        assert isinstance(result, probe.LeftOut)
        assert result.reason == f"stem missing: vocal/{STEM}---vocal.m4a"

    def test_a_stem_ffmpeg_cannot_read_is_left_out(self, analyse, monkeypatch):
        def broken(stem_file, cache_dir):
            raise subprocess.CalledProcessError(1, "ffmpeg")

        monkeypatch.setattr(probe, "load_envelope", broken)
        result = analyse(_make_song(*_anchor_lines(4), heard=[]))
        assert result.reason == "stem unreadable: CalledProcessError"

    def test_a_baseline_replay_that_differs_from_the_bundle_is_left_out_and_says_where(
        self, analyse
    ):
        song = _make_song(*_anchor_lines(4), heard=[])
        song.bundle["output_line_timings"][2]["start"] += 0.5
        result = analyse(song)
        assert isinstance(result, probe.LeftOut)
        assert result.reason == "baseline replay differs: line 2 start off by 0.500 s"

    def test_a_consistent_song_is_analysed(self, analyse):
        assert isinstance(analyse(_make_song(*_anchor_lines(4), heard=[])), probe.Analysed)


class TestTableA:
    def test_the_quit_playing_games_shape_is_two_a1_lines_in_a_run(self, analyse):
        *first, heard = _repeat_song()
        rows = analyse(_make_song(*first, heard)).rows["A"]
        assert [(r["line"], r["rule"], r["run"]) for r in rows] == [
            (4, "A1", True),
            (5, "A1", True),
        ]
        assert [r["cue"] for r in rows] == [12.0, 14.0]
        assert [r["today"] for r in rows] == [12.0, 14.0]  # spaced from the cue
        assert [r["new"] for r in rows] == [9.0, 11.0]
        assert [r["heard"] for r in rows] == [pytest.approx(9.05), pytest.approx(11.05)]
        assert rows[0]["text"] == "zim zam" and rows[0]["src"] == probe.CAPTION

    def test_a_line_with_an_inner_gap_heard_on_one_side_is_flagged(self):
        line = _line(0, "x", ("ee", 7.0, 7.3), ("ff", 7.4, 7.7), ("gg", 10.2, 10.5))
        before = heard_lines.HeardLine(tuple(_words(("ee", 7.0, 7.3), ("ff", 7.4, 7.7))), True)
        across = heard_lines.HeardLine(tuple(_words(("ee", 7.0, 7.3), ("gg", 10.2, 10.5))), True)
        assert probe.inner_gap_one_side(line, before)
        assert not probe.inner_gap_one_side(line, across)
        # No gap in the line: heard all on one side of its middle is not the signal.
        no_gap = _line(0, "x", ("ee", 7.0, 7.3), ("ff", 7.4, 7.7))
        early = heard_lines.HeardLine(tuple(_words(("ee", 6.0, 6.3), ("ff", 6.4, 6.7))), True)
        assert not probe.inner_gap_one_side(no_gap, early)


class TestTableV:
    def test_the_counts_follow_the_thresholds_and_the_constants_come_back(self):
        *first, heard = _repeat_song(off=0.7)
        counts = probe.a_counts(_make_song(*first, heard), ENV, DURATION)
        assert counts[(0.5, 2)] == (0, 0)  # 0.7 s apart is not an agreement at 0.5 s
        assert counts[(1.0, 2)] == (2, 0) and counts[(1.5, 2)] == (2, 0)
        assert counts[(1.0, 3)] == (0, 0)  # a two-word line cannot be heard on three words
        assert heard_lines.HEARD_AGREE_S == 1.0 and heard_lines.HEARD_MIN_WORDS == 2


class TestTableG:
    def test_a_start_freed_of_the_previous_line_names_that_lines_end(self, analyse):
        objs, cues, lines = _anchor_lines(3)
        cues += [(6.0, 7.0), (7.5, 9.0)]
        lines += ["bb cc", "ee ff"]
        objs += [_line(3, "bb cc", ("bb", 6.0, 6.3), ("cc", 7.0, 8.2)), _line(4, "ee ff")]
        short_first = _words(("ee", 7.3, 7.7), ("ff", 7.8, 8.6))
        heard = _words(("ee", 7.35, 7.75), ("ff", 7.85, 8.65))
        (row,) = analyse(_make_song(objs, cues, lines, heard, lambda *_: short_first)).rows["G"]
        assert row["line"] == 4 and row["new"] == pytest.approx(7.3)
        assert row["previous_end"] == 8.2 and row["heard"] == pytest.approx(7.35)
        assert row["today"] == 7.5  # the baseline cut the re-align to nothing and filled the line


class TestTableZ:
    def test_a_crammed_lines_zero_length_words_are_counted_before_and_after(self, analyse):
        objs, cues, lines = _one_line_song(
            (8.0, 12.0),
            ("ee", 8.0, 8.3),
            ("ff", 8.3, 8.3),
            ("gg", 8.3, 8.3),
            ("hh", 8.3, 8.8),
            text="ee ff gg hh",
        )
        (row,) = analyse(_make_song(objs, cues, lines, [])).rows["Z"]
        assert (row["line"], row["tokens"], row["zero_length"]) == (4, 4, 2)
        assert row["retimed"] >= 1

    def test_a_re_aligned_line_with_a_zero_length_word_is_listed_too(self, analyse):
        objs, cues, lines = _one_line_song((8.0, 12.0))
        realigned = _words(("ee", 8.0, 8.3), ("ff", 8.4, 8.4), ("gg", 8.5, 8.8))
        (row,) = analyse(_make_song(objs, cues, lines, [], lambda *_: realigned)).rows["Z"]
        assert (row["line"], row["tokens"], row["zero_length"]) == (4, 3, 1)
        assert row["retimed"] == 1

    def test_a_line_with_all_its_words_timed_is_not_listed(self, analyse):
        song = _make_song(*_one_line_song((8.0, 12.0), *_spans("ee ff gg", 8.0)), heard=[])
        assert analyse(song).rows["Z"] == []


class TestTableB:
    @staticmethod
    def _crazy(heard, answer):
        """Line 4, cued over 8-12 with no first-pass words, heard from 12.6."""
        song = _one_line_song((8.0, 12.0))
        return _make_song(*song, heard, answer)

    @staticmethod
    def _at_12_65(lid, w0, w1):
        return _sung("ee ff gg", 12.65) if w0 > 11 else None

    def test_the_crazy_shape_is_one_kept_line_with_its_shift_and_window(self, analyse):
        (row,) = analyse(self._crazy(_sung("ee ff gg", 12.6), self._at_12_65)).rows["B"]
        assert (row["line"], row["answered"], row["kept"]) == (4, True, True)
        assert row["shift"] == pytest.approx(4.6) and row["window"][0] == pytest.approx(11.85)
        assert (row["today"], row["new"]) == (8.0, 12.65)
        assert not row["lone_first"]

    def test_a_first_heard_word_two_seconds_before_the_second_is_flagged(self, analyse):
        heard = _words(("ee", 12.6, 12.9), ("ff", 14.8, 15.1), ("gg", 15.2, 15.5))
        (row,) = analyse(self._crazy(heard, self._at_12_65)).rows["B"]
        assert row["lone_first"]

    def test_a_window_the_bundle_has_no_answer_for_is_not_answered_or_kept(self, analyse):
        (row,) = analyse(self._crazy(_sung("ee ff gg", 12.6), None)).rows["B"]
        assert (row["answered"], row["kept"]) == (False, False)
        # The row shows the heard-aimed window, not the cue-aimed retry's that followed it.
        assert row["window"][0] == pytest.approx(11.85) and row["new"] == 8.0


class TestTableC:
    @staticmethod
    def _reflection(heard, bad=("ee ff gg",)):
        """Only the free stretch (it starts before 7.0) holds the first bad line."""
        return _make_song(
            *_free_stretch_song(bad),
            heard,
            lambda lid, w0, w1: _sung("ee ff gg", 13.0) if w0 < 7.0 else None,
        )

    def test_an_unheard_line_outside_a_run_has_blank_heard_shift_and_no_run(self, analyse):
        (row,) = analyse(self._reflection([])).rows["C"]
        assert row["line"] == 4 and row["stretch"] == (6.8, pytest.approx(20.1))
        assert row["length"] == pytest.approx(13.3)
        assert row["heard_shift"] is None and not row["run"]
        assert (row["answered"], row["kept"], row["today"], row["new"]) == (True, True, 8.0, 13.0)

    def test_a_line_heard_on_its_cue_shows_how_far_the_heard_start_is_from_it(self, analyse):
        (row,) = analyse(self._reflection(_sung("ee ff gg", 8.05))).rows["C"]
        assert row["heard_shift"] == pytest.approx(0.05) and row["kept"] and row["new"] == 13.0

    def test_two_identical_bad_lines_are_both_in_a_run(self, analyse):
        rows = analyse(self._reflection([], bad=("ee ff gg", "ee ff gg"))).rows["C"]
        assert [(r["line"], r["run"]) for r in rows] == [(4, True), (5, True)]


class TestTableD:
    @staticmethod
    def _whole(placed_at, heard_words, answer_at=None):
        song = _one_line_song((8.0, 12.0), *_spans("ee ff gg", placed_at))
        answer = None if answer_at is None else lambda *_: _sung("ee ff gg", answer_at)
        return _make_song(*song, heard_words, answer)

    def test_a_whole_line_placed_3_s_from_its_heard_words_is_listed_with_its_pairs(self, analyse):
        (row,) = analyse(self._whole(8.0, _sung("ee ff gg", 11.0), 11.05)).rows["D"]
        assert (row["line"], row["pairs"], row["run"]) == (4, 3, False)
        assert row["smallest"] == pytest.approx(3.0) and row["largest"] == pytest.approx(3.0)
        assert (row["today"], row["heard"], row["new"]) == (8.0, 11.0, 11.05)
        assert (row["answered"], row["kept"]) == (True, True)

    @pytest.mark.parametrize(
        "heard, reason",
        [
            (_sung("ee ff gg", 9.2), "some pair under 1.5 s"),
            (_sung("ee ff gg", 8.05), None),  # confirmed: not a candidate
            (_sung("ee ff gg", 11.0)[1:], "first token unheard"),
            (
                _words(("ee", 6.0, 6.3), ("ff", 10.4, 10.7), ("gg", 10.8, 11.1)),
                "pairs off both ways",
            ),
            # Off both ways and one pair within jitter: the closer pair is named first.
            (
                _words(("ee", 6.0, 6.3), ("ff", 8.5, 8.8), ("gg", 10.8, 11.1)),
                "some pair under 1.5 s",
            ),
        ],
    )
    def test_a_line_rule_d_does_not_aim_is_counted_by_why(self, analyse, heard, reason):
        result = analyse(self._whole(8.0, heard))
        assert result.rows["D"] == []
        assert result.d_unaimed == (Counter({reason: 1}) if reason else Counter())


class TestTableO:
    def test_only_lines_outside_the_rules_lists_that_moved_are_listed(self):
        def replay(*starts_ends):
            final = {i: {"start": s, "end": e, "words": []} for i, (s, e) in enumerate(starts_ends)}
            return probe.Replay({}, final, {}, [])

        ctx = probe.Ctx(
            probe.Song(STEM, probe.LRCLIB, {}),
            SimpleNamespace(display_lines=["l0", "l1", "l2", "l3", "l4"]),
            {},
            replay((1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0), (9.0, 10.0)),
            replay((1.0, 2.0), (3.0, 4.2), (5.5, 6.0), (7.005, 8.0), (9.0, 10.02)),
        )
        rows = probe.rows_o(ctx, claimed={2})
        # 0.02 s is under the baseline check's tolerance but over Table O's own threshold
        assert [(r["line"], r["moved"]) for r in rows] == [
            (1, pytest.approx(0.2)),
            (4, pytest.approx(0.02)),
        ]
        assert rows[0]["src"] == probe.LRCLIB and rows[0]["text"] == "l1"


class TestStemAndEnvelope:
    @pytest.mark.parametrize(
        "dereverb, kind",
        [(None, "vocal"), ({"succeeded": False}, "vocal"), ({"succeeded": True}, "dereverb")],
    )
    def test_the_snap_stem_is_the_dereverbed_one_only_when_that_retry_succeeded(
        self, tmp_path, dereverb, kind
    ):
        song = probe.Song(STEM, probe.CAPTION, {"joint_stats": {"dereverb": dereverb}})
        assert probe.snap_stem(tmp_path, song) == tmp_path / kind / f"{STEM}---{kind}.m4a"

    def test_the_envelope_is_decoded_once_and_again_when_the_stem_changes(
        self, tmp_path, monkeypatch
    ):
        stem = tmp_path / "s.m4a"
        stem.touch()
        decodes = []

        def decode(stem_file):
            decodes.append(stem_file)
            return np.array([-30.0, -40.0]), 12.5

        monkeypatch.setattr(probe, "decode_stem", decode)
        env, duration = probe.load_envelope(stem, tmp_path / "cache")
        again, same = probe.load_envelope(stem, tmp_path / "cache")
        assert len(decodes) == 1 and duration == same == 12.5
        assert env.tolist() == again.tolist() == [-30.0, -40.0]
        newer = (tmp_path / "cache" / "s.npz").stat().st_mtime + 10
        os.utime(stem, (newer, newer))
        probe.load_envelope(stem, tmp_path / "cache")
        assert len(decodes) == 2


class TestCueRouteSongs:
    @staticmethod
    def _write(folder, stem, origin, cue_inputs, words):
        debug = folder / "alignment_debug"
        debug.mkdir(exist_ok=True)
        bundle = {"lyrics": {"origin": origin}, "cue_inputs": cue_inputs, "transcribe_words": words}
        (debug / f"{stem}.json").write_text(json.dumps(bundle), encoding="utf-8")

    def test_only_cue_route_bundles_with_heard_words_are_read_and_split_by_source(self, tmp_path):
        cue = {"spans": []}
        self._write(tmp_path, "b caption", "srt", cue, [])
        self._write(tmp_path, "a lrclib", "lrclib_srt", cue, [{"word": "x"}])
        self._write(tmp_path, "c movie", "movie_srt", cue, [])
        self._write(tmp_path, "d joint", "genius", None, [{"word": "x"}])
        self._write(tmp_path, "e no words", "srt", cue, None)
        songs = probe.cue_route_songs(tmp_path)
        assert [(s.stem, s.kind) for s in songs] == [
            ("a lrclib", probe.LRCLIB),
            ("b caption", probe.CAPTION),
            ("c movie", probe.CAPTION),
        ]

    def test_a_folder_without_bundles_has_no_songs(self, tmp_path):
        assert probe.cue_route_songs(tmp_path) == []


class TestReport:
    def test_the_report_has_every_table_and_rows_json_rows_carry_their_table(self, analyse):
        *first, heard = _repeat_song()
        result = analyse(_make_song(*first, heard))
        left = probe.LeftOut(probe.Song("Other---bbbbbbbbbbb", probe.LRCLIB, {}), "stem missing")
        text, rows = probe.report([result], [left], Counter({probe.CAPTION: 1, probe.LRCLIB: 1}))
        for title in ("Table P", "Table A", "Table G", "Table Z", "Table B", "Table D", "Table C"):
            assert f"### {title}" in text
        assert "Table O" in text and "### Table V" in text
        assert "caption: 2 lines in 1 songs; LRCLIB: 0 lines in 0 songs" in text
        assert "| LRCLIB | Other bbbbbbbbbbb | stem missing |" in text
        assert [r["table"] for r in rows if r["table"] == "A"] == ["A", "A"]
        assert rows[0]["text"] == "zim zam"

    def test_booleans_none_and_floats_print_plainly(self):
        assert [probe.fmt(v) for v in (True, False, None, 1.23456, (1.0, 2.5))] == [
            "yes",
            "",
            "",
            "1.235",
            "1.000-2.500",
        ]


class TestStaging:
    @staticmethod
    def _song(folder: Path, name: str, content: str, *, stems=True) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        video = folder / f"{name}.mp4"
        video.write_text(content)
        files = [("alignment_debug", f"{name}.json"), ("subtitles", f"{name}.srt")]
        if stems:
            files.append(("vocal", f"{name}---vocal.m4a"))
        for sub, file in files:
            (folder / sub).mkdir(exist_ok=True)
            (folder / sub / file).write_text(content)
        return video

    def test_a_song_is_copied_with_its_files_and_nothing_else(self, tmp_path):
        self._song(tmp_path / "lib", "A---aaaaaaaaaaa", "lib")
        self._song(tmp_path / "lib", "B---bbbbbbbbbbb", "lib")
        staged = probe.stage_songs(["aaaaaaaaaaa"], [tmp_path / "lib"], tmp_path / "copy")
        assert [p.name for p in staged] == ["A---aaaaaaaaaaa.mp4"]
        copied = sorted(
            p.relative_to(tmp_path / "copy").as_posix()
            for p in (tmp_path / "copy").rglob("*")
            if p.is_file()
        )
        assert copied == [
            "A---aaaaaaaaaaa.mp4",
            "alignment_debug/A---aaaaaaaaaaa.json",
            "subtitles/A---aaaaaaaaaaa.srt",
            "vocal/A---aaaaaaaaaaa---vocal.m4a",
        ]

    def test_a_from_folder_wins_over_the_library_for_the_songs_it_has(self, tmp_path):
        self._song(tmp_path / "lib", "A---aaaaaaaaaaa", "lib")
        self._song(tmp_path / "lib", "B---bbbbbbbbbbb", "lib")
        self._song(tmp_path / "trial", "A---aaaaaaaaaaa", "trial", stems=False)
        sources = [tmp_path / "trial", tmp_path / "lib"]
        probe.stage_songs(["aaaaaaaaaaa", "bbbbbbbbbbb"], sources, tmp_path / "copy")
        copy = tmp_path / "copy"
        assert (copy / "alignment_debug" / "A---aaaaaaaaaaa.json").read_text() == "trial"
        assert not (copy / "vocal" / "A---aaaaaaaaaaa---vocal.m4a").exists()
        assert (copy / "alignment_debug" / "B---bbbbbbbbbbb.json").read_text() == "lib"

    def test_main_stages_from_the_from_folders_before_the_library(
        self, tmp_path, monkeypatch, capsys
    ):
        self._song(tmp_path / "lib", "A---aaaaaaaaaaa", "lib")
        self._song(tmp_path / "trial", "A---aaaaaaaaaaa", "trial", stems=False)
        argv = ["--folder", str(tmp_path / "lib"), "--from", str(tmp_path / "trial")]
        argv += ["--stage", str(tmp_path / "copy"), "--song", "aaaaaaaaaaa"]
        monkeypatch.setattr(sys, "argv", ["probe", *argv])
        assert probe.main() == 0
        assert "Staged 1 songs" in capsys.readouterr().out
        assert (
            tmp_path / "copy" / "alignment_debug" / "A---aaaaaaaaaaa.json"
        ).read_text() == "trial"

    def test_a_file_with_no_id_is_staged_by_its_whole_stem(self, tmp_path):
        self._song(tmp_path / "lib", "Plain Name", "lib")
        staged = probe.stage_songs(["Plain Name"], [tmp_path / "lib"], tmp_path / "copy")
        assert [p.name for p in staged] == ["Plain Name.mp4"]
        assert (tmp_path / "copy" / "alignment_debug" / "Plain Name.json").is_file()

    def test_a_song_with_no_id_is_named_in_full_and_one_with_an_id_in_short(self):
        long = "A Very Long Artist Name - A Very Long Song Title"
        assert probe.label(long) == long
        assert probe.label(f"{long}---abcdefghijk") == "A Very Long Artist Name - A Ve abcdefghijk"

    def test_an_unknown_id_is_an_error(self, tmp_path):
        self._song(tmp_path / "lib", "A---aaaaaaaaaaa", "lib")
        with pytest.raises(ValueError, match="No video with id or stem zzzzzzzzzzz"):
            probe.stage_songs(["zzzzzzzzzzz"], [tmp_path / "lib"], tmp_path / "copy")

    @pytest.mark.parametrize("argv", [["--song", "aaaaaaaaaaa"], ["--stage", "x"]])
    def test_song_and_stage_go_together(self, monkeypatch, argv):
        monkeypatch.setattr(sys, "argv", ["probe", *argv])
        with pytest.raises(SystemExit) as exc:
            probe.main()
        assert exc.value.code == 2
