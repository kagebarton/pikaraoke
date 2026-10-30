"""Tests for pairing a lyric sheet's lines with an LRC's (lib/lrc_pairing.py).

Lines are invented. The Hangul-looking ones are placeholder syllables: they
normalise to nothing, as real Hangul does, so they never pair by text.
"""

import pytest

from pikaraoke.lib.lrc_pairing import Pairing, Stretch, pair_lines, timed_sheet_srt
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.lib.srt_slice_fit import lrc_to_srt

KOREAN_A = "가나다 라마바"
KOREAN_B = "사아자 차카타"
KOREAN_C = "파하가 나다라"


class TestPairLines:
    def test_every_line_pairs_by_text(self):
        lines = ["hold the line tonight", "we are the morning light", "never let it go"]
        pairing = pair_lines(lines, list(lines))
        assert pairing.by_text == {0: 0, 1: 1, 2: 2}
        assert pairing.by_position == ()
        assert pairing.refused == ()

    def test_a_stretch_of_equal_counts_between_text_pairs_pairs_by_position(self):
        sheet = ["hold the line tonight", "romanized one", "romanized two", "never let it go"]
        lrc = ["hold the line tonight", KOREAN_A, KOREAN_B, "never let it go"]
        pairing = pair_lines(sheet, lrc)
        assert pairing.by_text == {0: 0, 3: 3}
        assert pairing.by_position == (Stretch((1, 3), (1, 3)),)
        assert pairing.refused == ()
        assert pairing.line_map() == {0: 0, 1: 1, 2: 2, 3: 3}

    def test_a_stretch_of_unequal_counts_is_refused(self):
        sheet = ["hold the line tonight", "romanized one", "romanized two", "never let it go"]
        lrc = ["hold the line tonight", KOREAN_A, "never let it go"]
        pairing = pair_lines(sheet, lrc)
        assert pairing.by_text == {0: 0, 3: 2}
        assert pairing.by_position == ()
        assert pairing.refused == (Stretch((1, 3), (1, 2)),)

    def test_a_refused_stretch_leaves_the_text_pairs_each_side_alone(self):
        sheet = ["first anchor line", "a", "b", "second anchor line", "c", "d", "last anchor line"]
        lrc = [
            "first anchor line",
            KOREAN_A,
            "second anchor line",
            KOREAN_B,
            KOREAN_C,
            "last anchor line",
        ]
        pairing = pair_lines(sheet, lrc)
        assert pairing.by_text == {0: 0, 3: 2, 6: 5}
        assert pairing.refused == (Stretch((1, 3), (1, 2)),)
        assert pairing.by_position == (Stretch((4, 6), (3, 5)),)

    def test_a_stretch_before_the_first_pair_and_after_the_last(self):
        sheet = ["intro one", "intro two", "the only anchor line", "outro"]
        lrc = [KOREAN_A, KOREAN_B, "the only anchor line", KOREAN_C]
        pairing = pair_lines(sheet, lrc)
        assert pairing.by_text == {2: 2}
        assert pairing.by_position == (Stretch((0, 2), (0, 2)), Stretch((3, 4), (3, 4)))
        assert pairing.refused == ()

    def test_an_intro_the_lrc_lacks_is_refused(self):
        sheet = ["spoken intro", "the only anchor line"]
        pairing = pair_lines(sheet, ["the only anchor line"])
        assert pairing.by_text == {1: 0}
        assert pairing.refused == (Stretch((0, 1), (0, 0)),)

    def test_lrc_lines_the_sheet_lacks_are_refused(self):
        sheet = ["the only anchor line"]
        pairing = pair_lines(sheet, ["the only anchor line", KOREAN_A, KOREAN_B])
        assert pairing.refused == (Stretch((1, 1), (1, 3)),)

    def test_no_lrc_lines_refuses_the_whole_sheet(self):
        pairing = pair_lines(["one line", "another line"], [])
        assert pairing.by_text == {}
        assert pairing.refused == (Stretch((0, 2), (0, 0)),)

    def test_two_empty_sides_pair_nothing(self):
        assert pair_lines([], []) == Pairing({}, (), ())

    def test_a_duet_lrc_line_against_two_sheet_lines_is_refused(self):
        lrc_text = (
            "[00:10.00]hold the line tonight\n"
            "[00:14.00]she sings this\n"
            "[00:14.00]he sings that\n"
            "[00:18.00]never let it go\n"
        )
        lrc_lines, _ = cue_spans_from_srt(lrc_to_srt(lrc_text))
        assert lrc_lines[1] == "she sings this he sings that"
        sheet = ["hold the line tonight", "she sings this", "he sings that", "never let it go"]
        pairing = pair_lines(sheet, lrc_lines)
        assert pairing.by_text == {0: 0, 3: 2}
        assert pairing.refused == (Stretch((1, 3), (1, 2)),)

    def test_a_repeated_chorus_keeps_each_instance_in_its_own_place(self):
        sheet = [
            "verse one starts here",
            "chorus line number one",
            "chorus line number two",
            "verse two starts here",
            "chorus line number one",
            "chorus line number two",
        ]
        lrc = [
            "verse one starts here",
            "chorus line number one",
            "chorus line number two",
            "verse two starts here",
            "chorus line number one",
            "chorus line number two",
        ]
        assert pair_lines(sheet, lrc).by_text == {i: i for i in range(6)}

    def test_a_chorus_the_lrc_repeats_once_more_refuses_the_extra_lines(self):
        # Which instance the sheet's last chorus pairs with is a tie; the extra one is refused.
        chorus = ["chorus line number one", "chorus line number two"]
        sheet = ["verse one starts here", *chorus, "verse two starts here", *chorus]
        lrc = [
            "verse one starts here",
            *chorus,
            "verse two starts here",
            *chorus,
            "chorus line number three",
            *chorus,
        ]
        pairing = pair_lines(sheet, lrc)
        assert sorted(pairing.by_text) == list(range(6))
        (extra,) = pairing.refused
        assert extra.sheet[0] == extra.sheet[1]
        assert extra.lrc[1] - extra.lrc[0] == 3


class TestTimedSheetSrt:
    SPANS = [(1.0, 4.5), (4.5, 9.25), (9.25, 12.0), (12.0, 20.5)]

    def test_each_sheet_line_takes_its_paired_lrc_lines_span(self):
        sheet = ["hold the line tonight", "romanized one", "romanized two", "never let it go"]
        lrc = ["hold the line tonight", KOREAN_A, KOREAN_B, "never let it go"]
        pairing = pair_lines(sheet, lrc)
        texts, spans = cue_spans_from_srt(timed_sheet_srt(sheet, self.SPANS, pairing))
        assert texts == sheet
        assert spans == self.SPANS

    def test_a_sheet_with_a_different_split_keeps_its_own_lines(self):
        sheet = ["hold the line tonight", "never let it go"]
        lrc = ["hold the line tonight", "never let it go"]
        pairing = pair_lines(sheet, lrc)
        texts, spans = cue_spans_from_srt(timed_sheet_srt(sheet, self.SPANS[:2], pairing))
        assert texts == sheet
        assert spans == self.SPANS[:2]

    def test_a_refused_stretch_has_no_sheet(self):
        pairing = pair_lines(["first anchor line", "extra"], ["first anchor line"])
        with pytest.raises(ValueError):
            timed_sheet_srt(["first anchor line", "extra"], self.SPANS, pairing)
