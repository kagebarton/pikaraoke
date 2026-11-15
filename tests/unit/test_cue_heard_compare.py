"""Unit tests for scripts/cue_heard_compare.py: made-up bundles, a silent envelope, no audio."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from pikaraoke.lib.alignment_capture import output_line_timings
from tests.unit.test_cue_heard_probe import (
    DURATION,
    ENV,
    STEM,
    _free_stretch_song,
    _make_song,
    _one_line_song,
    _repeat_song,
    _sung,
    probe,
)

# scripts/ is not a package; the module imports the probe by name, which the probe's own test
# module has registered in sys.modules.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cue_heard_compare.py"
_spec = importlib.util.spec_from_file_location("cue_heard_compare", _SCRIPT)
compare = importlib.util.module_from_spec(_spec)
sys.modules["cue_heard_compare"] = compare
_spec.loader.exec_module(compare)


def _regen_bundle(first, heard, answer=None, *, captured_at="regen") -> dict:
    """A bundle as the regen leaves it: made with the heard words and every rule, so it saves
    only the re-aligns that run asked for (not the cue-aimed retry a rule made unnecessary)."""
    objs, cues, lines = first
    bundle = {
        "captured_at": captured_at,
        "lyrics": {"origin": "srt", "lines": lines, "align_lines": lines},
        "cue_inputs": {"spans": cues, "sections": objs, "realigns": []},
        "transcribe_words": heard,
        "joint_stats": {},
        "output_line_timings": [],
    }
    song = probe.Song(STEM, probe.CAPTION, bundle)
    while answer is not None:  # the real aligner is asked one call at a time, in order
        run = probe.replay(song, Path("stem.m4a"), ENV, DURATION, heard=True)
        asked = next((c for c in run.calls if not c.answered), None)
        if asked is None:
            break
        words = answer(asked.line_id, asked.w0, asked.w1)
        bundle["cue_inputs"]["realigns"].append(
            {"line_id": asked.line_id, "w0": asked.w0, "w1": asked.w1, "words": words}
        )
    run = probe.replay(song, Path("stem.m4a"), ENV, DURATION, heard=True)
    bundle["output_line_timings"] = output_line_timings(list(run.final.values()))
    bundle["joint_stats"]["repace"] = run.stats
    return bundle


def _source_bundle(first, heard, answer=None) -> dict:
    """The bundle before the regen: made without the rules, so the baseline reproduces it."""
    bundle = _make_song(*first, heard, answer, origin="srt").bundle
    bundle["captured_at"] = "source"
    return bundle


@pytest.fixture
def library(tmp_path, monkeypatch):
    """``library(source, new)``: a copy folder (stem, new bundle) and its backup (source
    bundle); returns ``(copy, backup)``."""
    monkeypatch.setattr(probe, "load_envelope", lambda stem_file, cache_dir: (ENV, DURATION))

    def make(source: dict | None, new: dict | None, stem: str = STEM) -> tuple[Path, Path]:
        copy, backup = tmp_path / "copy", tmp_path / "copy" / "regen_backups" / "20260101T000000Z"
        (copy / "vocal").mkdir(parents=True, exist_ok=True)
        (copy / "vocal" / f"{stem}---vocal.m4a").touch()
        for folder, bundle in ((copy, new), (backup, source)):
            if bundle is not None:
                (folder / "alignment_debug").mkdir(parents=True, exist_ok=True)
                (folder / "alignment_debug" / f"{stem}.json").write_text(json.dumps(bundle))
        return copy, backup

    return make


def _compare(library, source, new, tmp_path):
    copy, backup = library(source, new)
    return compare.compare_song(copy, backup, tmp_path / "env", STEM)


def _crazy():
    """Line 4 cued over 8-12, heard from 12.6: rule B moves it there, so the regen never asked
    for the cue-aimed retry the source bundle holds."""
    first = _one_line_song((8.0, 12.0))
    heard = _sung("ee ff gg", 12.6)

    def answer(lid, w0, w1):
        return _sung("ee ff gg", 12.65) if w0 > 11 else None

    return first, heard, answer


class TestHelpers:
    @pytest.mark.parametrize(
        ("before", "after", "heard", "expected"),
        [
            (8.0, 12.65, 12.6, "within"),
            (8.0, 12.0, 12.6, "closer"),
            (8.0, 12.2, 12.6, "closer"),  # 0.4 s off is not within 0.05 s
            (12.5, 8.0, 12.6, "further"),
            (8.0, 8.0, 12.6, "further"),
            (None, 12.6, 12.6, None),
            (8.0, 12.6, None, None),
        ],
    )
    def test_the_new_start_is_within_closer_or_further_from_the_heard_one(
        self, before, after, heard, expected
    ):
        assert compare.vs_heard(before, after, heard) == expected

    def test_within_is_decided_before_closer(self):
        # Already within 0.05 s before: still "within", not "closer" or "further".
        assert compare.vs_heard(12.58, 12.62, 12.6) == "within"

    def test_neighbours_skip_lines_without_words(self):
        final = {
            0: {"start": 1.0, "end": 2.0, "words": [{"start": 1.0, "end": 2.0}]},
            1: {"start": None, "end": None, "words": []},
            2: {"start": 5.0, "end": 6.0, "words": [{"start": 5.0, "end": 6.0}]},
        }
        assert compare.neighbour(final, 0, 1) == (5.0, 6.0)
        assert compare.neighbour(final, 2, -1) == (1.0, 2.0)
        assert compare.neighbour(final, 2, 1) is None and compare.neighbour(final, 0, -1) is None

    def test_a_line_runs_into_the_next_when_its_last_word_ends_after_the_next_ones_start(self):
        def line(*words):
            return {"words": [{"start": s, "end": e} for s, e in words]}

        final = {
            0: line((1.0, 2.0), (2.0, 5.1)),
            1: line(),
            2: line((5.0, 6.0)),
            3: line((9.0, 9.5)),
        }
        assert compare.runs_into_next(final, 0)  # past the empty line 1, line 2 starts at 5.0
        assert not compare.runs_into_next(final, 2)
        assert not compare.runs_into_next({0: line((1.0, 5.0)), 1: line((5.0, 6.0))}, 0)  # touching
        assert not compare.runs_into_next(final, 3)  # the last line has no next

    def test_only_line_id_lists_are_checked_for_stats_and_order_does_not_matter(self):
        replayed = {"a_line_ids": [2, 1], "b_line_ids": [3], "n_heard_lines": 4}
        saved = {"a_line_ids": [1, 2], "b_line_ids": [], "n_heard_lines": 9}
        assert compare.stats_mismatch(replayed, saved) == ["b_line_ids"]

    def test_a_spot_listens_four_seconds_before_the_earlier_start(self):
        spot = compare.Spot(
            "target", 0, STEM, "S", (24, 25), "target", "", ((113.6, 115.0),), ((117.0, 118.0),)
        )
        assert spot.listen_at == "1:49"  # 113.6 - 4 = 109.6 s
        assert spot.moved == pytest.approx(3.4)
        assert (
            compare.Spot("t", 0, "s", "S", (1,), "r", "", ((1.0, 2.0),), ((3.0, 4.0),)).listen_at
            == "0:00"
        )


class TestCompareSong:
    def test_a_regen_that_changed_the_lyrics_is_not_the_same_lyrics(self, library, tmp_path):
        first, heard, answer = _crazy()
        new = _regen_bundle(first, heard, answer)
        new["lyrics"] = {**new["lyrics"], "origin": "lrclib_srt"}
        done = _compare(library, _source_bundle(first, heard, answer), new, tmp_path)
        assert done.check["same_lyrics"] is False and done.check["src"] == probe.LRCLIB

    def test_a_song_the_source_has_no_bundle_for_is_not_compared(self, library, tmp_path):
        first, heard, answer = _crazy()
        assert _compare(library, None, _regen_bundle(first, heard, answer), tmp_path) is None

    def test_a_missing_new_bundle_and_an_unregenerated_one_are_named_in_table_p(
        self, library, tmp_path
    ):
        first, heard, answer = _crazy()
        source = _source_bundle(first, heard, answer)
        assert _compare(library, source, None, tmp_path).check["replay"] == "bundle missing"
        same = {**_regen_bundle(first, heard, answer), "captured_at": "source"}
        done = _compare(library, source, same, tmp_path)
        assert done.check["replay"] == "not regenerated" and list(done.rows) == ["S"]

    def test_a_missing_stem_is_named(self, library, tmp_path):
        first, heard, answer = _crazy()
        copy, backup = library(
            _source_bundle(first, heard, answer), _regen_bundle(first, heard, answer)
        )
        (copy / "vocal" / f"{STEM}---vocal.m4a").unlink()
        done = compare.compare_song(copy, backup, tmp_path / "env", STEM)
        assert done.check["replay"] == f"stem missing: vocal/{STEM}---vocal.m4a"

    def test_a_heard_replay_that_differs_from_the_new_bundle_leaves_the_song_out(
        self, library, tmp_path
    ):
        first, heard, answer = _crazy()
        new = _regen_bundle(first, heard, answer)
        new["output_line_timings"][4]["start"] += 0.5
        done = _compare(library, _source_bundle(first, heard, answer), new, tmp_path)
        assert done.check["replay"] == "differs: line 4 start off by 0.500 s"
        # No rule table is built from a replay that does not hold; Table S needs no replay.
        assert list(done.rows) == ["S"] and done.pool == {}
        assert [(r["line"], r["today"], r["rules"]) for r in done.rows["S"]] == [(4, None, "")]

    def test_the_crazy_shape_is_a_kept_b_line_whose_cue_aimed_retry_has_no_answer(
        self, library, tmp_path
    ):
        first, heard, answer = _crazy()
        done = _compare(
            library,
            _source_bundle(first, heard, answer),
            _regen_bundle(first, heard, answer),
            tmp_path,
        )
        assert done.check["replay"] == "reproduces" and done.check["stats_match"]
        assert (done.check["new_unanswered"], done.check["today_unanswered"]) == (0, 1)
        (row,) = done.rows["B"]
        assert (row["line"], row["kept"], row["answered"], row["today_ok"]) == (
            4,
            True,
            True,
            False,
        )
        assert (row["source"], row["new"], row["vs_source"]) == (8.0, 12.65, "within")
        assert row["align_empty"] is False  # the aligner answered; a check kept the line
        (spot,) = done.pool["B"]  # the sheet offers the line, with the move against the source
        assert (spot.rule, spot.lines, spot.moved) == ("B", (4,), pytest.approx(4.65))
        text, _ = compare.report([done])
        assert (
            f"Kept B lines whose cue-aimed retry has no saved answer: {row['song']} line 4" in text
        )

    def test_a_b_line_that_was_not_kept_has_no_vs_heard_and_a_baseline_with_every_answer(
        self, library, tmp_path
    ):
        first, heard, _ = _crazy()
        # The aligner finds nothing anywhere: rule B tries, is refused, the cue-aimed retry
        # fails too and the line is a fill.
        new = _regen_bundle(first, heard, lambda *_: None)
        done = _compare(library, _source_bundle(first, heard, lambda *_: None), new, tmp_path)
        (row,) = done.rows["B"]
        assert (row["kept"], row["today_ok"], row["vs_today"], row["overlap"]) == (
            False,
            True,
            None,
            None,
        )
        assert done.pool["B"] == []  # a refused retry is not a spot to listen to
        # The aligner returned nothing for the heard-aimed window: not a refusal by a check.
        assert row["align_empty"] is True

    def test_a_refused_b_line_that_moved_against_the_source_is_in_table_s_but_not_on_the_sheet(
        self, library, tmp_path
    ):
        first, heard, _ = _crazy()
        source = _source_bundle(first, heard, lambda lid, w0, w1: _sung("ee ff gg", 9.0))
        done = _compare(library, source, _regen_bundle(first, heard, lambda *_: None), tmp_path)
        (row,) = done.rows["S"]
        assert (row["line"], row["rules"]) == (4, "B tried") and row["moved"] > 0.5
        assert done.pool["B"] == []

    def test_a_kept_line_that_did_not_move_against_the_source_is_not_a_spot(
        self, library, tmp_path
    ):
        first, heard, answer = _crazy()
        new = _regen_bundle(first, heard, answer)
        source = _source_bundle(first, heard, answer)
        source["output_line_timings"] = new["output_line_timings"]
        done = _compare(library, source, new, tmp_path)
        assert done.rows["B"][0]["kept"] and done.rows["S"] == [] and done.pool["B"] == []

    def test_the_a1_shape_has_its_source_start_its_heard_start_and_a_baseline_with_no_answer(
        self, library, tmp_path
    ):
        *first, heard = _repeat_song()
        done = _compare(
            library,
            _source_bundle(first, heard, lambda *_: None),
            _regen_bundle(first, heard, lambda *_: None),
            tmp_path,
        )
        rows = done.rows["A"]
        assert [(r["line"], r["rule"], r["new"], r["vs_today"]) for r in rows] == [
            (4, "A1", 9.0, "within"),
            (5, "A1", 11.0, "within"),
        ]
        assert [r["today"] for r in rows] == [12.0, 14.0]  # the baseline spaced them from the cue
        assert done.check["today_unanswered"] == 2 and not any(r["today_ok"] for r in rows)
        assert [s.rule for s in done.pool["A"]] == ["A1", "A1"]

    def test_a_line_that_moved_against_the_source_is_in_table_s_with_its_rules(
        self, library, tmp_path
    ):
        first, heard, answer = _crazy()
        done = _compare(
            library,
            _source_bundle(first, heard, answer),
            _regen_bundle(first, heard, answer),
            tmp_path,
        )
        # The source bundle was made without the rules: the cue-aimed retry failed and the
        # line was spaced from its cue at 8.0.
        (row,) = done.rows["S"]
        assert row["line"] == 4 and row["rules"] == "B kept"
        assert row["source"][0] == 8.0 and row["new"][0] == 12.65
        assert row["moved"] == pytest.approx(4.65)
        assert done.check["moved_0.3"] == 1 and done.check["moved_1.0"] == 1

    def test_table_s_leaves_out_a_line_that_stayed_within_the_threshold(self, library, tmp_path):
        first, heard, _ = _crazy()
        source = _source_bundle(first, heard, lambda *_: None)
        new = _regen_bundle(first, heard, lambda *_: None)
        done = _compare(library, source, new, tmp_path)
        assert done.rows["S"] == []

    def test_table_o_flags_lines_beside_an_unanswered_baseline_call(self, library, tmp_path):
        first, heard, answer = _crazy()
        done = _compare(
            library,
            _source_bundle(first, heard, answer),
            _regen_bundle(first, heard, answer),
            tmp_path,
        )
        assert all(row["near_unanswered"] in (True, False) for row in done.rows["O"])


class TestRuleC:
    @staticmethod
    def _row(library, tmp_path, stretch_answer):
        """Bad line 4 between clean neighbours: the cue-aimed retry finds nothing, rule C's
        stretch (it starts before 7.0) is answered by ``stretch_answer``."""
        first = _free_stretch_song(("ee ff gg",))

        def answer(lid, w0, w1):
            return stretch_answer if w0 < 7.0 else None

        done = _compare(
            library, _source_bundle(first, [], answer), _regen_bundle(first, [], answer), tmp_path
        )
        (row,) = (r for r in done.rows["C"] if r["line"] == 4)
        return row

    def test_a_kept_gap_retry_is_about_the_stretch_call_not_the_failed_cue_aimed_one(
        self, library, tmp_path
    ):
        row = self._row(library, tmp_path, _sung("ee ff gg", 13.0))
        assert (row["kept"], row["align_empty"], row["today_ok"]) == (True, False, True)
        assert (row["source"], row["today"], row["new"]) == (8.0, 8.0, 13.0)

    def test_a_gap_retry_the_aligner_gave_nothing_for_is_flagged(self, library, tmp_path):
        row = self._row(library, tmp_path, None)
        assert (row["kept"], row["align_empty"]) == (False, True)


class TestRuleCByRun:
    def test_the_tries_and_keeps_are_counted_by_run_and_by_twin(self):
        rows = [
            {"run": False, "twin": False, "kept": True},
            {"run": False, "twin": False, "kept": False},
            {"run": True, "twin": False, "kept": True},
            {"run": True, "twin": True, "kept": False},
            {"run": True, "twin": True, "kept": False},
        ]
        text = compare.table_c_runs(rows)
        assert "| not in a run | 2 | 1 |" in text
        assert "| in a run, stretch between twins on their cues | 1 | 1 |" in text
        assert "| in a run, stretch ends at a parked twin | 2 | 0 |" in text


class TestSheet:
    @staticmethod
    def _spot(group, rank, stem="a", lines=(1,), rule=None):
        return compare.Spot(
            group,
            rank,
            stem,
            stem,
            lines,
            rule or group,
            f"text {stem}{lines}",
            ((1.0, 2.0),),
            ((5.0, 6.0),),
        )

    @staticmethod
    def _done(*spots):
        pool = {}
        for spot in spots:
            pool.setdefault(spot.group, []).append(spot)
        return compare.Compared(probe.Song("x", probe.CAPTION, {}), {}, {}, pool)

    def test_targets_come_first_in_spot_order_then_each_group_by_largest_move(self):
        done = self._done(
            self._spot("D", 2.0, "d"),
            self._spot("target", 3, "a3"),
            self._spot("target", 0, "z0"),
            self._spot("C", 1.0, "c1"),
            self._spot("C", 9.0, "c9"),
            self._spot("B", 4.0, "b"),
        )
        order = [s.stem for s in compare.pick_spots([done])]
        assert order == ["z0", "a3", "c9", "c1", "d", "b"]

    def test_rule_c_takes_two_a_song_and_eight_in_all_and_rule_d_three(self):
        spots = [self._spot("C", 100 - i, f"song{i // 3}", (i,)) for i in range(30)]
        spots += [self._spot("D", 50 - i, "d", (i,)) for i in range(6)]
        picked = compare.pick_spots([self._done(*spots)])
        assert [s.group for s in picked].count("C") == 8
        per_song = {}
        for s in picked:
            if s.group == "C":
                per_song[s.stem] = per_song.get(s.stem, 0) + 1
        assert max(per_song.values()) == 2
        assert [s.group for s in picked].count("D") == 3

    def test_a_line_already_on_the_sheet_is_not_picked_again(self):
        done = self._done(self._spot("target", 0, "a", (1,)), self._spot("C", 5.0, "a", (1,)))
        assert [s.group for s in compare.pick_spots([done])] == ["target"]

    def test_the_sheet_names_the_video_and_both_ass_files_and_escapes_the_text(self, tmp_path):
        copy, backup = tmp_path / "copy", tmp_path / "backup"
        (backup / "karaoke").mkdir(parents=True)
        (copy / "karaoke").mkdir(parents=True)
        (copy / f"{STEM}.mp4").touch()
        (copy / "karaoke" / f"{STEM}.ass").touch()  # the old .ass is missing
        spot = compare.Spot(
            "C", 1.0, STEM, "Song <x>", (3,), "C", "a <b> & c", ((1.0, 2.0),), ((5.0, 6.0),)
        )
        page = compare.sheet_html([spot], copy, backup)
        assert str(copy / f"{STEM}.mp4") in page and str(copy / "karaoke" / f"{STEM}.ass") in page
        assert "(missing)" in page and "Song &lt;x&gt;" in page and "a &lt;b&gt; &amp; c" in page
        assert "0:00" in page and "<!doctype html>" in page


class TestRun:
    def test_the_oldest_backup_is_the_source_and_no_backup_is_an_error(self, tmp_path):
        with pytest.raises(SystemExit):
            compare.source_folder(tmp_path)
        for name in ("20260102T000000Z", "20260101T000000Z"):
            (tmp_path / "regen_backups" / name / "alignment_debug").mkdir(parents=True)
        (tmp_path / "regen_backups" / "20251231T000000Z").mkdir()  # no alignment_debug
        assert compare.source_folder(tmp_path).name == "20260101T000000Z"

    def test_the_run_writes_its_own_files_and_leaves_the_probes_alone(
        self, library, tmp_path, capsys
    ):
        first, heard, answer = _crazy()
        copy, backup = library(
            _source_bundle(first, heard, answer), _regen_bundle(first, heard, answer)
        )
        out = tmp_path / "out"
        out.mkdir()
        (out / "rows.json").write_text("probe rows")
        text = compare.run_compare(copy, backup, out)
        assert "### Table P" in text and "### Table S" in text
        assert (out / "rows.json").read_text() == "probe rows" and not (out / "started").exists()
        rows = json.loads((out / "compare" / "rows.json").read_text())
        assert {row["table"] for row in rows} >= {"B", "S"} and rows[0]["text"]
        assert "<table>" in (out / "listening-sheet.html").read_text()
        assert "[1/1]" in capsys.readouterr().err

    def test_the_report_has_every_table_in_order(self, library, tmp_path):
        first, heard, answer = _crazy()
        done = _compare(
            library,
            _source_bundle(first, heard, answer),
            _regen_bundle(first, heard, answer),
            tmp_path,
        )
        text, _ = compare.report([done])
        headings = [line for line in text.splitlines() if line.startswith("### Table")]
        assert [h[10] for h in headings] == list("PTAGZBDCOS")
        assert "Rule C by run" in text
