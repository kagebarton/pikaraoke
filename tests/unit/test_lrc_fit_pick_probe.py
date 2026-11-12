"""Tests for the pure parts of scripts/lrc_fit_pick_probe.py, on made-up values.

No network and no library: the fits are small made-up songs or built by hand.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pikaraoke.lib.lrc_auto_pick import Entry, evaluate, refusal
from pikaraoke.lib.srt_slice_fit import ASR, FITS, REFUSED, TRANSCRIBE, SliceFit
from scripts import lrc_fit_pick_probe as probe
from scripts.lrc_fit_pick_probe import (
    CAPTIONED,
    EDITED,
    JOINT,
    NO_BUNDLE,
    NO_CAPTION_FILE,
    NO_WORDS,
    OTHER,
    OUT_OF_SCOPE,
    PICKS,
    Rec,
    SongResult,
)


def _classify(**overrides):
    row = {
        "bundle": True,
        "origin": "srt",
        "method": "cue_align",
        "edited": False,
        "words": True,
        "caption_file": True,
    }
    return probe.classify(**(row | overrides))


class TestGroups:
    def test_a_caption_song_has_an_unedited_srt_origin_words_and_its_caption_file(self):
        assert _classify() == (CAPTIONED, "")

    def test_an_lrclib_timed_song_with_words_is_a_pick_song(self):
        assert _classify(origin="lrclib_srt") == (PICKS, "")

    def test_a_genius_song_timed_by_the_joint_matcher_is_a_joint_song(self):
        assert _classify(origin="genius", method="joint") == (JOINT, "")

    def test_each_way_out_of_scope_names_its_reason(self):
        assert _classify(bundle=False) == (OUT_OF_SCOPE, NO_BUNDLE)
        assert _classify(origin="custom") == (OUT_OF_SCOPE, "custom")
        assert _classify(origin="movie_srt") == (OUT_OF_SCOPE, "movie_srt")
        assert _classify(origin="genius", words=False) == (OUT_OF_SCOPE, NO_WORDS)
        assert _classify(edited=True) == (OUT_OF_SCOPE, EDITED)
        assert _classify(caption_file=False) == (OUT_OF_SCOPE, NO_CAPTION_FILE)

    def test_a_song_the_rules_do_not_name_is_other(self):
        assert _classify(origin="genius", method="cue_align") == (OUT_OF_SCOPE, OTHER)
        assert _classify(origin=None) == (OUT_OF_SCOPE, OTHER)

    def test_a_custom_or_movie_song_is_that_whatever_else_is_missing(self):
        assert _classify(origin="custom", words=False) == (OUT_OF_SCOPE, "custom")
        assert _classify(origin="movie_srt", caption_file=False) == (OUT_OF_SCOPE, "movie_srt")

    def test_an_uploader_caption_is_a_file_with_no_generated_marker(self, tmp_path):
        song = tmp_path / "Title---abcdefghijk.mp4"
        (tmp_path / "subtitles").mkdir()
        assert not probe.has_caption_file(song)

        (tmp_path / "subtitles" / f"{song.stem}.srt").write_text("x", encoding="utf-8")
        assert probe.has_caption_file(song)

        (tmp_path / "subtitles" / f"{song.stem}.srt.generated").write_text("", encoding="utf-8")
        assert not probe.has_caption_file(song)


class TestReferenceFlags:
    TRANSCRIBE_FIT = SliceFit(FITS, shift_s=2.0)

    def _flags(self, **ref_fields):
        ref = SliceFit(FITS, shift_s=2.0) if not ref_fields else SliceFit(FITS, **ref_fields)
        return probe.reference_flags(self.TRANSCRIBE_FIT, ref)

    def test_a_reference_fit_that_agrees_raises_no_flag(self):
        assert self._flags() == []

    def test_a_reference_that_did_not_fit_is_refused_and_nothing_else_is_read(self):
        ref = SliceFit(REFUSED, shift_s=9.0)
        assert probe.reference_flags(self.TRANSCRIBE_FIT, ref) == ["ref_refused"]

    def test_a_mistimed_line_is_flagged(self):
        assert self._flags(shift_s=2.0, mistimed=(3,)) == ["ref_mistimed"]

    def test_caption_words_no_line_claims_are_flagged_over_twelve_only(self):
        assert self._flags(shift_s=2.0, unclaimed_run=12) == []
        assert self._flags(shift_s=2.0, unclaimed_run=13) == ["ref_unclaimed"]

    def test_a_run_of_unheard_lines_is_flagged_but_two_are_not(self):
        assert self._flags(shift_s=2.0, unheard=(4, 5)) == []
        assert self._flags(shift_s=2.0, unheard=(4, 5, 6)) == ["ref_unheard"]

    def test_a_shift_further_than_a_second_and_a_half_from_the_heard_fits_is_flagged(self):
        assert self._flags(shift_s=3.5) == []
        assert self._flags(shift_s=3.6) == ["ref_shift"]
        assert self._flags(shift_s=0.4) == ["ref_shift"]

    def test_a_run_of_lines_off_the_same_way_against_the_caption_is_flagged_over_two_only(self):
        assert self._flags(shift_s=2.0, offsets=(2.0, 2.0)) == []
        assert self._flags(shift_s=2.0, offsets=(2.0, 2.0, 2.0)) == ["ref_shift_run"]

    def test_every_name_that_applies_is_given_in_order(self):
        flags = self._flags(
            shift_s=9.0, mistimed=(1,), unclaimed_run=20, unheard=(1, 2, 3), offsets=(-2.0,) * 3
        )
        assert flags == [
            "ref_mistimed",
            "ref_unclaimed",
            "ref_unheard",
            "ref_shift",
            "ref_shift_run",
        ]


class TestCaptionIsAReference:
    def test_it_must_fit_at_speed_one_within_the_shift_with_no_flagged_run(self):
        assert probe.caption_ok(SliceFit(FITS, shift_s=1.5))
        assert not probe.caption_ok(SliceFit(REFUSED))
        assert not probe.caption_ok(SliceFit(FITS, speed=1.07))
        assert not probe.caption_ok(SliceFit(FITS, shift_s=-1.6))
        assert not probe.caption_ok(SliceFit(FITS, mistimed=(4, 5)))
        assert probe.caption_ok(SliceFit(FITS, mistimed=(4,)))


class TestNeedsAVerdict:
    def test_no_pick_needs_none(self):
        assert not probe.needs_verdict(PICKS, None, "t")

    def test_a_pick_song_whose_pick_has_the_on_disk_timing_is_already_sung_on(self):
        assert not probe.needs_verdict(PICKS, "t", "t")

    def test_a_pick_song_whose_pick_has_another_timing_needs_one(self):
        assert probe.needs_verdict(PICKS, "t", "other")

    def test_a_pick_song_with_no_on_disk_record_needs_one(self):
        assert probe.needs_verdict(PICKS, "t", None)

    def test_only_a_pick_song_is_excused_by_the_on_disk_timing(self):
        assert probe.needs_verdict(JOINT, "t", "t")
        assert probe.needs_verdict(CAPTIONED, "t", "t")


def _rec(
    rec_id: int,
    fit: SliceFit | None = None,
    flags=(),
    timing: str = "t",
    passes: bool = True,
    asr: SliceFit | None = None,
) -> Rec:
    fit = fit or SliceFit(FITS)
    return Rec(
        {"id": rec_id},
        fit,
        None if passes else "unclaimed",
        True,
        False,
        timing,
        rec_id,
        1,
        flags=tuple(flags),
        asr=asr,
    )


def _shifted(run: int) -> SliceFit:
    """A fit with ``run`` neighbouring lines heard 2 s off."""
    return SliceFit(FITS, offsets=(2.0,) * run)


def _song(youtube_id: str, pick: Rec | None = None, ref_ok: bool = False, recs=()) -> SongResult:
    song = SongResult(CAPTIONED, "", False, youtube_id, "Title", "stem")
    song.pick, song.ref_ok, song.recs = pick, ref_ok, list(recs)
    return song


class TestListenOrder:
    def _order(self, songs):
        return [s.youtube_id for s in sorted(songs, key=probe.listen_key)]

    def test_no_reference_first_then_flagged_then_the_rest(self):
        plain = _song("plain", _rec(1, SliceFit(FITS, unclaimed_run=12)), ref_ok=True)
        flagged = _song("flagged", _rec(2, SliceFit(FITS, unclaimed_run=1), ["ref_shift"]), True)
        bare = _song("bare", _rec(3, SliceFit(FITS, unclaimed_run=0)), ref_ok=False)

        assert self._order([plain, flagged, bare]) == ["bare", "flagged", "plain"]

    def test_within_a_tier_the_longest_unclaimed_run_then_the_most_mistimed_then_the_id(self):
        def song(name, run, mistimed):
            fit = SliceFit(FITS, unclaimed_run=run, mistimed=tuple(range(mistimed)))
            return _song(name, _rec(1, fit), ref_ok=False)

        songs = [song("c", 5, 0), song("b", 9, 0), song("a", 5, 1), song("d", 5, 0)]

        assert self._order(songs) == ["b", "a", "c", "d"]


class TestTableKSource:
    def test_this_runs_search_wins_then_the_old_cache_then_not_found(self):
        assert probe.locate_record(1, {1, 2}, {1, 3}) == "pool"
        assert probe.locate_record(3, {1, 2}, {1, 3}) == "old cache"
        assert probe.locate_record(4, {1, 2}, {1, 3}) == "not found"


class TestSensitivity:
    def _song(self, *fits: SliceFit) -> SongResult:
        return _song("x", recs=[_rec(n, fit) for n, fit in enumerate(fits)])

    def test_a_song_has_a_pick_when_some_record_passes_at_the_limits(self):
        one_flag = SliceFit(FITS, mistimed=(1,), unclaimed_run=10)
        long_run = SliceFit(FITS, unclaimed_run=14)
        songs = [self._song(one_flag), self._song(long_run), self._song(SliceFit(REFUSED))]

        assert probe.songs_with_pick_at(songs, 0, 12) == 0
        assert probe.songs_with_pick_at(songs, 1, 12) == 1
        assert probe.songs_with_pick_at(songs, 0, 15) == 1
        assert probe.songs_with_pick_at(songs, 1, 15) == 2

    def test_any_one_record_is_enough_and_a_changed_speed_never_passes(self):
        sped_up = SliceFit(FITS, speed=1.07)
        clean = SliceFit(FITS)

        assert probe.songs_with_pick_at([self._song(sped_up)], 1, 99) == 0
        assert probe.songs_with_pick_at([self._song(sped_up, clean)], 0, 0) == 1


class TestSheetHelpers:
    def test_the_header_an_lrc_file_carries_is_dropped_and_the_stamps_kept(self):
        text = "[ti:A Title]\n[ar:An Artist]\n[length:03:20]\n[lrclib_id:7]\n[00:10.00] one\n[00:12.00]\n"

        assert probe.body_of_lrc(text) == "[00:10.00] one\n[00:12.00]"

    def test_lines_match_by_text_in_order_so_a_repeat_is_not_taken_twice(self):
        fit_lines = (("a", 1.0), ("b", 2.0), ("a", 3.0), ("c", 4.0))
        other = (("b", 2.1), ("a", 3.1), ("c", 4.1))

        assert probe.match_lines(fit_lines, other) == {0: 1, 1: 2, 2: 3}

    def test_a_line_the_other_fit_dropped_at_the_edge_leaves_the_rest_matched(self):
        fit_lines = (("a", 1.0), ("b", 2.0), ("c", 3.0))
        other = (("b", 2.1), ("c", 3.1))

        assert probe.match_lines(fit_lines, other) == {0: 1, 1: 2}

    def test_rows_are_in_time_order_with_both_fits_flags_offsets_and_the_long_runs_only(self):
        fit = SliceFit(
            FITS,
            lines=(("first", 10.0), ("second", 20.0), ("third", 30.0)),
            mistimed=(1,),
            unheard=(2,),
            offsets=(0.1, 6.0, None),
            unclaimed_runs=((0, 3), (2, 5)),
        )
        ref = SliceFit(
            FITS,
            lines=(("second", 20.2), ("third", 30.2)),
            mistimed=(1,),
            unheard=(0,),
            offsets=(None, 5.5),
        )
        words = [{"norm": w, "start": 25.0 + n} for n, w in enumerate("a b c d e f".split())]

        rows = probe.sheet_rows(fit, ref, (("caption cue", 10.0),), words)

        assert rows == [
            (10.0, "L", "", 0.1, None, "first"),
            (10.0, "C", "", None, None, "caption cue"),
            (20.0, "L", "Mu", 6.0, None, "second"),
            (27.0, "X", "5", None, None, "c d e f"),
            (30.0, "L", "Um", None, 5.5, "third"),
        ]

    def test_the_caption_offset_is_from_this_fits_line_start_not_the_caption_fits(self):
        fit = SliceFit(FITS, lines=(("only", 12.0),), offsets=(0.0,), shift_s=2.0)
        # The caption puts the line 0.3 s after its own fit's start, which is 0.5 s later.
        ref = SliceFit(FITS, lines=(("only", 12.5),), offsets=(0.3,), shift_s=2.5)

        rows = probe.sheet_rows(fit, ref, (), [])

        assert rows[0][4] == pytest.approx(0.8)

    def test_a_refused_reference_adds_no_caption_flags_or_offsets(self):
        fit = SliceFit(FITS, lines=(("only", 5.0),), mistimed=(0,), offsets=(7.0,))

        rows = probe.sheet_rows(fit, SliceFit(REFUSED), (), [])

        assert rows == [(5.0, "L", "M", 7.0, None, "only")]

    def test_a_line_is_written_with_signed_offsets_blank_when_unheard(self):
        line = probe.sheet_line(12.345, "L", "Mu", 2.5, None, "some\ttext")

        assert line == "12.35\tL\tMu\t+2.50\t\tsome text"
        assert probe.sheet_line(1.0, "C", "", None, None, "x") == "1.00\tC\t\t\t\tx"
        assert probe.sheet_line(1.0, "L", "", -0.04, -3.0, "x") == "1.00\tL\t\t-0.04\t-3.00\tx"


class TestFlaggedUnpicked:
    def test_flagged_passing_timings_the_pick_does_not_share_one_group_each(self):
        pick = _rec(5, timing="picked")
        recs = [
            pick,
            _rec(9, flags=["ref_shift"], timing="b"),
            _rec(7, flags=["ref_shift"], timing="b"),
            _rec(3, flags=["ref_mistimed"], timing="a"),
            _rec(2, flags=["ref_shift"], timing="picked"),  # the pick's own timing
            _rec(1, timing="clean"),  # passes, not flagged
            _rec(4, flags=["ref_shift"], timing="refused", passes=False),
        ]

        groups = probe.flagged_unpicked(recs, pick)

        assert [[r.id for r in group] for group in groups] == [[3], [7, 9]]


# ---- the real fit, on made-up songs -----------------------------------------------------


def _word(i: int) -> str:
    return f"w{chr(97 + i // 26)}{chr(97 + i % 26)}x"


def _sung(lines: int) -> list[dict]:
    return [
        {"norm": _word(k * 5 + i), "start": 10.0 + 5.0 * k + 0.6 * i}
        for k in range(lines)
        for i in range(5)
    ]


def _lrc(lines: int) -> str:
    def stamp(k: int) -> str:
        seconds = 10.0 + 5.0 * k
        return f"[{int(seconds) // 60:02d}:{seconds % 60:05.2f}]"

    return "\n".join(
        f"{stamp(k)} {' '.join(_word(k * 5 + i) for i in range(5))}" for k in range(lines)
    )


class TestRecords:
    def _entries(self, records):
        return evaluate(records, _sung(30), 300.0)

    def test_the_on_disk_record_the_search_returned_is_the_pools_own(self):
        entries = self._entries([{"id": 5, "syncedLyrics": _lrc(30)}])

        recs, disk = probe.make_recs(entries, {"id": 5, "syncedLyrics": _lrc(30)}, _sung(30), 300.0)

        assert disk is recs[0] and disk.in_pool and disk.on_disk

    def test_an_on_disk_record_the_search_lacks_is_fitted_apart_with_its_timings_pool_count(self):
        entries = self._entries(
            [{"id": 8, "syncedLyrics": _lrc(30)}, {"id": 6, "syncedLyrics": _lrc(30)}]
        )

        recs, disk = probe.make_recs(entries, {"id": 9, "syncedLyrics": _lrc(30)}, _sung(30), 300.0)

        assert [r.on_disk for r in recs] == [False, False]
        assert (disk.in_pool, disk.on_disk, disk.refusal) == (False, True, None)
        assert (disk.timing_id, disk.timing_size) == (6, 2)

    def test_a_timing_is_named_by_the_lowest_id_of_the_records_that_share_it(self):
        entries = self._entries(
            [
                {"id": 8, "syncedLyrics": _lrc(30)},
                {"id": 6, "syncedLyrics": _lrc(30) + "\n"},
                {"id": 2, "syncedLyrics": _lrc(20)},
            ]
        )

        recs, disk = probe.make_recs(entries, None, _sung(30), 300.0)

        assert disk is None
        assert {r.id: r.timing_id for r in recs} == {8: 6, 6: 6, 2: 2}

    def test_a_record_with_no_usable_id_does_not_name_a_timing_over_one_that_has(self):
        entries = [
            Entry({"id": None, "syncedLyrics": "x"}, SliceFit(FITS), None, 2),
            Entry({"id": 4, "syncedLyrics": "x"}, SliceFit(FITS), None, 2),
        ]

        recs, _ = probe.make_recs(entries, None, [], 100.0)

        assert [r.timing_id for r in recs] == [4, 4]

    def test_a_timing_whose_records_all_lack_an_id_is_named_none(self):
        entries = [Entry({"syncedLyrics": "x"}, SliceFit(FITS), None, 1)]

        recs, _ = probe.make_recs(entries, None, [], 100.0)

        assert recs[0].timing_id is None


class TestCaptionReference:
    def test_the_records_are_screened_against_the_caption_on_the_heard_words_clock(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            probe, "read_caption", lambda song: ("text", [{"norm": "a", "start": 10.0}])
        )
        monkeypatch.setattr(
            probe, "fit_slice", lambda *args: SliceFit(FITS, lines=(("a", 11.4),), shift_s=1.4)
        )
        screened = []
        monkeypatch.setattr(
            probe, "add_references", lambda recs, stream, length: screened.append(stream)
        )
        song = SongResult(CAPTIONED, "", False, "vid", "Title", "stem", 300.0, _sung(3))

        lines = probe.judge_reference(song, tmp_path / "stem.mp4")

        assert song.ref_ok and lines == (("a", 11.4),)
        assert screened == [[{"norm": "a", "start": pytest.approx(11.4)}]]


class TestTableK:
    def test_each_record_is_read_from_this_runs_search_else_the_old_cache(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(probe, "GATE_M_WRONG", {"vid": (1, 2, 3), "other": (9,)})
        (tmp_path / "vid.json").write_text(
            json.dumps(
                {
                    "query": "q",
                    "records": [
                        {"id": 1, "syncedLyrics": _lrc(30)},
                        {"id": 2, "syncedLyrics": _lrc(10)},
                    ],
                }
            ),
            encoding="utf-8",
        )
        song = SongResult(CAPTIONED, "", False, "vid", "Title", "stem", 300.0, _sung(30))
        song.recs, _ = probe.make_recs(
            evaluate([{"id": 1, "syncedLyrics": _lrc(30)}], song.words, 300.0),
            None,
            song.words,
            300.0,
        )
        song.pick = song.recs[0]

        table = probe.table_k([song], tmp_path)

        rows = [[c.strip() for c in line.strip("|").split("|")] for line in table.splitlines()[2:]]
        assert [(r[1], r[2], r[3], r[8], r[9]) for r in rows] == [
            ("1", "pool", "yes", "passes", "yes"),
            ("2", "old cache", "no", "unclaimed", "no"),
            ("3", "not found", "", "", ""),
            ("9", "not found", "", "", ""),
        ]
        assert rows[3][10] == "song not probed in this run"
        assert rows[2][10] == ""

    def test_the_refusals_of_the_bar_are_the_columns_of_table_s(self):
        assert probe.REFUSALS == ("no_fit", "speed", "mistimed", "unclaimed", "shifted")
        assert refusal(SliceFit(REFUSED)) in probe.REFUSALS
        assert TRANSCRIBE == "transcribe"


class TestSecondHearing:
    def test_a_record_is_refused_when_its_auto_caption_fit_has_a_longer_shift_run_than_the_bar(
        self,
    ):
        assert _rec(1, asr=_shifted(3)).asr_refuses
        assert not _rec(1, asr=_shifted(2)).asr_refuses

    def test_an_auto_caption_fit_that_did_not_fit_or_is_missing_refuses_nothing(self):
        assert not _rec(1, asr=SliceFit(REFUSED, offsets=(2.0,) * 9)).asr_refuses
        assert not _rec(1).asr_refuses

    def test_the_pick_with_the_rule_is_the_first_passing_record_it_does_not_refuse(self):
        song = _song(
            "x",
            recs=[
                _rec(1, asr=_shifted(4)),
                _rec(2, passes=False),
                _rec(3, asr=_shifted(1)),
                _rec(4),
            ],
        )
        song.pick = song.recs[0]

        assert song.asr_pick.id == 3

    def test_no_pick_with_the_rule_when_it_refuses_every_passing_record(self):
        song = _song("x", recs=[_rec(1, asr=_shifted(3)), _rec(2, asr=_shifted(5))])

        assert song.asr_pick is None

    def test_a_song_without_an_auto_caption_picks_as_the_bar_does(self):
        song = _song("x", recs=[_rec(1), _rec(2)])

        assert song.asr_pick is song.recs[0]


def _json3(words: int, word_level: bool = True) -> str:
    """An auto-caption of ``words`` words from 1 s, half a second apart when word-level; a
    line-level one stamps them all at the line's start."""
    segs = [
        {"utf8": f" w{n}", **({"tOffsetMs": 500 * n} if word_level else {})} for n in range(words)
    ]
    return json.dumps({"events": [{"tStartMs": 1000, "segs": segs}]})


class TestAutoCaptionFile:
    def _song(self, tmp_path, text: str | None = None) -> Path:
        song = tmp_path / "Title---abcdefghijk.mp4"
        if text is not None:
            (tmp_path / "subtitles").mkdir(parents=True)
            (tmp_path / "subtitles" / f"{song.stem}.en.asr.json3").write_text(
                text, encoding="utf-8"
            )
        return song

    def test_a_word_level_caption_is_read_as_a_word_stream(self, tmp_path):
        words = probe.read_asr(self._song(tmp_path, _json3(20)), 60.0)

        assert len(words) == 20
        assert words[:2] == [{"norm": "w0", "start": 1.0}, {"norm": "w1", "start": 1.5}]

    def test_a_caption_the_pipeline_would_not_adopt_is_not_used(self, tmp_path):
        # Line-level (every word at its line's start), then too sparse for the song's length.
        assert probe.read_asr(self._song(tmp_path, _json3(20, word_level=False)), 60.0) == []
        assert probe.read_asr(self._song(tmp_path / "x", _json3(20)), 600.0) == []

    def test_no_file_an_unreadable_one_and_a_wrong_shape_are_all_empty(self, tmp_path, caplog):
        song = self._song(tmp_path)
        assert probe.read_asr(song, 60.0) == []

        (tmp_path / "subtitles").mkdir()
        path = tmp_path / "subtitles" / f"{song.stem}.en.asr.json3"
        path.write_bytes(b"\xff\xfe not utf-8")
        assert probe.read_asr(song, 60.0) == []
        assert "Cannot read auto-caption" in caplog.text

        path.write_text("[]", encoding="utf-8")
        assert probe.read_asr(song, 60.0) == []

    def test_each_record_is_fitted_to_the_stream_and_a_shifted_stretch_refuses_it(self):
        heard = _sung(30)
        late = [
            {**w, "start": w["start"] + 3.0} if 14 * 5 <= n < 17 * 5 else w
            for n, w in enumerate(heard)
        ]
        entries = evaluate([{"id": 5, "syncedLyrics": _lrc(30)}], heard, 300.0)
        recs, _ = probe.make_recs(entries, None, heard, 300.0)

        probe.add_asr_fits(recs, late, 300.0)

        assert recs[0].passes
        assert (recs[0].asr.status, recs[0].asr.shift_run) == (FITS, 3)
        assert recs[0].asr_refuses
        assert ASR == "asr"


class TestRows:
    def test_a_candidate_row_has_a_cell_for_every_column_with_or_without_the_other_fits(self):
        song = SongResult(CAPTIONED, "", False, "vid", "Title", "stem", 300.0)
        bare = _rec(1)
        full = _rec(2, SliceFit(FITS, offsets=(2.0,) * 3), flags=["ref_shift_run"], asr=_shifted(4))
        full.ref = _shifted(5)

        for rec in (bare, full):
            assert len(probe.candidate_row(song, rec)) == len(probe.CANDIDATE_HEADER)
        row = dict(zip(probe.CANDIDATE_HEADER, probe.candidate_row(song, full)))
        assert (row["shift_run"], row["ref_shift_run"], row["ref_flags"]) == (3, 5, "ref_shift_run")
        assert (row["asr_status"], row["asr_shift_run"]) == ("fits", 4)
        assert (row["asr_mistimed_n"], row["asr_unheard_n"]) == (0, 0)
        blank = dict(zip(probe.CANDIDATE_HEADER, probe.candidate_row(song, bare)))
        assert (blank["ref_shift_run"], blank["asr_status"], blank["asr_shift_run"]) == ("", "", "")

    def test_a_song_row_has_the_pick_shift_run_the_auto_caption_flag_and_the_rule_pick(self):
        recs = [_rec(1, _shifted(3), asr=_shifted(3)), _rec(2, _shifted(1))]
        song = _song("vid", recs[0], recs=recs)
        song.has_asr = True

        row = dict(zip(probe.SONG_HEADER, probe.song_row(song)))

        assert len(probe.song_row(song)) == len(probe.SONG_HEADER)
        assert (row["pick_id"], row["pick_shift_run"]) == (1, 3)
        assert (row["has_asr"], row["asr_pick_id"]) == (1, 2)

    def test_a_song_row_leaves_the_rule_pick_empty_when_the_rule_leaves_none(self):
        recs = [_rec(1, asr=_shifted(3))]
        song = _song("vid", recs[0], recs=recs)

        row = dict(zip(probe.SONG_HEADER, probe.song_row(song)))

        assert row["asr_pick_id"] == ""


def _table_rows(table: str) -> list[list[str]]:
    return [[c.strip() for c in line.strip("|").split("|")] for line in table.splitlines()[2:]]


class TestTableG:
    def test_each_record_shows_its_refusal_shift_run_and_auto_caption_fit(self, monkeypatch):
        monkeypatch.setattr(probe, "GATE_P_WRONG", {"vid": (1, 2, 3), "other": (9,)})
        shifted = _rec(1, _shifted(3), passes=False, asr=_shifted(4))
        shifted.refusal = "shifted"
        picked = _rec(2, SliceFit(FITS), asr=SliceFit(REFUSED))
        song = _song("vid", picked, recs=[shifted, picked])
        song.reason = ""

        rows = _table_rows(probe.table_g([song]))

        assert [(r[1], r[2], r[6], r[7], r[8], r[9], r[10], r[13]) for r in rows] == [
            ("1", "yes", "3", "shifted", "no", "fits", "4", ""),
            ("2", "yes", "0", "passes", "yes", "refused", "0", ""),
            ("3", "no", "", "", "", "", "", "not in the search"),
            ("9", "no", "", "", "", "", "", "song not probed in this run"),
        ]

    def test_the_seven_gate_p_records_are_named_by_song(self):
        ids = [i for ids in probe.GATE_P_WRONG.values() for i in ids]

        assert sorted(ids) == sorted(
            [28421947, 26614056, 23648746, 4626353, 19452078, 2137556, 685756]
        )


class TestTableA:
    def test_only_a_song_whose_pick_the_rule_changes_is_listed_with_both_picks_flags(self):
        changed = _song(
            "changed", ref_ok=True, recs=[_rec(1, asr=_shifted(3)), _rec(2, flags=["ref_shift"])]
        )
        changed.pick = changed.recs[0]
        lost = _song("lost", recs=[_rec(5, asr=_shifted(3))])
        lost.pick = lost.recs[0]
        same = _song("same", recs=[_rec(7)])
        same.pick = same.recs[0]
        for song in (changed, lost, same):
            song.reason = ""

        rows = _table_rows(probe.table_a([changed, lost, same]))

        assert [(r[1], r[3], r[4], r[5], r[6]) for r in rows] == [
            ("changed", "1", "none", "2", "ref_shift"),
            ("lost", "5", "no reference", "none", ""),
        ]


class TestTableC:
    def test_the_old_picks_are_read_for_the_songs_that_were_searched(self, tmp_path):
        path = tmp_path / "songs.tsv"
        path.write_text(
            "group\treason\tyoutube_id\tpick_id\n"
            "caption\t\ta\t11\n"
            "joint\t\tb\t\n"
            "joint\tlrclib_unavailable\tc\t\n"
            "out_of_scope\tcustom\td\t\n",
            encoding="utf-8",
        )

        assert probe.read_compare(path) == {"a": "11", "b": ""}

    def test_a_song_is_listed_when_its_pick_differs_and_both_runs_searched_it(self):
        def song(name, pick_id):
            result = _song(name, _rec(pick_id) if pick_id else None)
            result.reason = ""
            return result

        songs = [song("same", 1), song("moved", 2), song("lost", None), song("gained", 4)]
        songs.append(song("unseen", 9))
        songs[1].pick.record["id"] = 2
        compared = {"same": "1", "moved": "5", "lost": "3", "gained": ""}

        rows = _table_rows(probe.table_c(songs, compared))

        assert [(r[1], r[3], r[4]) for r in rows] == [
            ("moved", "5", "2"),
            ("lost", "3", "none"),
            ("gained", "none", "4"),
        ]


class TestTableVShift:
    def test_the_shift_rows_count_songs_with_a_pick_by_offset_limit_and_run_limit(self):
        three_late = SliceFit(FITS, offsets=(1.2, 1.2, 1.2))
        four_far = SliceFit(FITS, offsets=(2.5, 2.5, 2.5, 2.5))
        song = _song("x", recs=[_rec(1, three_late)])
        other = _song("y", recs=[_rec(2, four_far)])
        song.reason = other.reason = ""

        # By the bar's own limit (1.5 s, run of 2), a run of 3 lines 1.2 s off is no run.
        assert probe.songs_with_pick_at([song], 1, 12) == 1
        assert probe.songs_with_pick_at([song], 1, 12, 1.0, 2) == 0
        assert probe.songs_with_pick_at([song], 1, 12, 1.0, 3) == 1
        assert probe.songs_with_pick_at([other], 1, 12, 2.0, 3) == 0
        assert probe.songs_with_pick_at([other], 1, 12, 2.0, 4) == 1

    def test_the_bar_includes_the_shift_condition_in_the_first_limits_too(self):
        assert not probe.passes_at(_shifted(3), 1, 12)
        assert probe.passes_at(_shifted(2), 1, 12)

    def test_the_table_has_a_row_per_group_and_offset_with_a_column_per_run_limit(self):
        song = _song("x", recs=[_rec(1, SliceFit(FITS, offsets=(1.2,) * 3))])
        song.reason = ""

        table = probe.table_v([song])

        shift = table.split("\n\n")[1]
        rows = _table_rows(shift)
        assert shift.splitlines()[0].count("Shift run <=") == 3
        assert [r[:2] + r[3:] for r in rows if r[0] == CAPTIONED] == [
            ["caption", "1.0", "0", "1", "1"],
            ["caption", "1.5", "1", "1", "1"],
            ["caption", "2.0", "1", "1", "1"],
        ]


class TestSelection:
    STATUSES = [
        SimpleNamespace(path=Path("A---aaaaaaaaaaa.mp4"), youtube_id="aaaaaaaaaaa"),
        SimpleNamespace(path=Path("B---bbbbbbbbbbb.mp4"), youtube_id="bbbbbbbbbbb"),
        SimpleNamespace(path=Path("No Id.mp4"), youtube_id=None),
    ]

    def _ids(self, **kwargs):
        args = {"only": [], "baseline": {"aaaaaaaaaaa"}, "skip_new": False, "new_only": False}
        return [probe.song_id(s) for s in probe.select_statuses(self.STATUSES, **(args | kwargs))]

    def test_every_song_is_read_by_default(self):
        assert self._ids() == ["aaaaaaaaaaa", "bbbbbbbbbbb", "No Id"]

    def test_skip_new_reads_only_the_baseline_songs_and_new_only_the_rest(self):
        assert self._ids(skip_new=True) == ["aaaaaaaaaaa"]
        assert self._ids(new_only=True) == ["bbbbbbbbbbb", "No Id"]

    def test_only_narrows_either_way(self):
        assert self._ids(only=["bbbbbbbbbbb", "aaaaaaaaaaa"], new_only=True) == ["bbbbbbbbbbb"]

    def test_without_a_baseline_the_flags_ask_for_one(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["probe", "--folder", "x", "--skip-new"])
        with pytest.raises(SystemExit):
            probe.parse_args()

        monkeypatch.setattr(
            sys, "argv", ["probe", "--folder", "x", "--baseline", "b", "--new-only"]
        )
        assert probe.parse_args().new_only

    def test_the_two_flags_exclude_each_other(self, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["probe", "--folder", "x", "--baseline", "b", "--skip-new", "--new-only"]
        )
        with pytest.raises(SystemExit):
            probe.parse_args()


class TestProbeSong:
    """One joint song end to end on made-up data: a cached search, no library, no network."""

    @staticmethod
    def _run(tmp_path, monkeypatch, asr_late: bool):
        heard = _sung(30)
        bundle = {"transcribe_words": [{"word": w["norm"], "start": w["start"]} for w in heard]}
        monkeypatch.setattr(probe, "read_bundle", lambda folder, stem: bundle)
        monkeypatch.setattr(probe, "media_duration", lambda job: 300.0)
        song = tmp_path / "lib" / "Title---abcdefghijk.mp4"
        (song.parent / "subtitles").mkdir(parents=True)
        asr_words = [
            {**w, "start": w["start"] + (3.0 if asr_late and 14 * 5 <= n < 17 * 5 else 0.0)}
            for n, w in enumerate(heard)
        ]
        events = [
            {"tStartMs": 0, "segs": [{"utf8": w["norm"], "tOffsetMs": int(w["start"] * 1000)}]}
            for w in asr_words
        ]
        (song.parent / "subtitles" / f"{song.stem}.en.asr.json3").write_text(
            json.dumps({"events": events}), encoding="utf-8"
        )
        out = tmp_path / "out"
        (out / "cache").mkdir(parents=True)
        record = {"id": 5, "syncedLyrics": _lrc(30), "trackName": "T", "albumName": "A"}
        (out / "cache" / "abcdefghijk.json").write_text(
            json.dumps({"query": "q", "records": [record]}), encoding="utf-8"
        )
        status = SimpleNamespace(
            path=song, youtube_id="abcdefghijk", origin="genius", method="joint", edited=False
        )
        return probe.probe_song(status, probe.Run(out, out / "listen", {"other"})), out

    def test_an_auto_caption_that_puts_a_stretch_off_refuses_the_pick_only_under_the_rule(
        self, tmp_path, monkeypatch
    ):
        result, out = self._run(tmp_path, monkeypatch, asr_late=True)

        assert (result.group, result.has_asr, result.new) == (JOINT, True, True)
        assert result.pick.id == 5 and result.pick.refusal is None
        assert (result.pick.asr.status, result.pick.asr.shift_run) == (FITS, 3)
        assert result.asr_pick is None
        sheet = (out / "sheets" / "abcdefghijk" / "5.txt").read_text(encoding="utf-8").splitlines()
        assert sheet[4] == "time\tkind\tflags\toffset\tcaption_offset\ttext"
        assert sheet[5].split("\t")[:5] == ["10.00", "L", "", "+0.00", ""]

    def test_an_agreeing_auto_caption_leaves_the_pick_alone(self, tmp_path, monkeypatch):
        result, _ = self._run(tmp_path, monkeypatch, asr_late=False)

        assert result.pick.asr.shift_run == 0
        assert result.asr_pick is result.pick
