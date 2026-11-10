"""Tests for the pure parts of scripts/lrc_fit_pick_probe.py, on made-up values.

No network and no library: the fits are small made-up songs or built by hand.
"""

import json

import pytest

from pikaraoke.lib.lrc_auto_pick import Entry, evaluate, refusal
from pikaraoke.lib.srt_slice_fit import FITS, REFUSED, TRANSCRIBE, SliceFit
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

    def test_every_name_that_applies_is_given_in_order(self):
        flags = self._flags(shift_s=9.0, mistimed=(1,), unclaimed_run=20, unheard=(1, 2, 3))
        assert flags == ["ref_mistimed", "ref_unclaimed", "ref_unheard", "ref_shift"]


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
    rec_id: int, fit: SliceFit | None = None, flags=(), timing: str = "t", passes: bool = True
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
    )


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

    def test_rows_are_in_time_order_with_both_fits_flags_and_the_long_runs_only(self):
        fit = SliceFit(
            FITS,
            lines=(("first", 10.0), ("second", 20.0), ("third", 30.0)),
            mistimed=(1,),
            unheard=(2,),
            unclaimed_runs=((0, 3), (2, 5)),
        )
        ref = SliceFit(FITS, lines=(("second", 20.2), ("third", 30.2)), mistimed=(1,), unheard=(0,))
        words = [{"norm": w, "start": 25.0 + n} for n, w in enumerate("a b c d e f".split())]

        rows = probe.sheet_rows(fit, ref, (("caption cue", 10.0),), words)

        assert rows == [
            (10.0, "L", "", "first"),
            (10.0, "C", "", "caption cue"),
            (20.0, "L", "Mu", "second"),
            (27.0, "X", "5", "c d e f"),
            (30.0, "L", "Um", "third"),
        ]

    def test_a_refused_reference_adds_no_caption_flags(self):
        fit = SliceFit(FITS, lines=(("only", 5.0),), mistimed=(0,))

        rows = probe.sheet_rows(fit, SliceFit(REFUSED), (), [])

        assert rows == [(5.0, "L", "M", "only")]


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
        assert probe.REFUSALS == ("no_fit", "speed", "mistimed", "unclaimed")
        assert refusal(SliceFit(REFUSED)) in probe.REFUSALS
        assert TRANSCRIBE == "transcribe"
