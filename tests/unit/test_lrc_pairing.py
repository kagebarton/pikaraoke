"""Tests for pairing a lyric sheet's lines with an LRC's (lib/lrc_pairing.py).

Lines are invented. The Hangul-looking ones are placeholder syllables: they
normalise to nothing, as real Hangul does, so they never pair by text.
"""

import pytest

from pikaraoke.lib.lrc_pairing import (
    Pairing,
    Stretch,
    clean_sheet_lines,
    line_spans,
    pair_lines,
    timed_sheet_srt,
)
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.lib.srt_slice_fit import lrc_to_srt

KOREAN_A = "가나다 라마바"
KOREAN_B = "사아자 차카타"
KOREAN_C = "파하가 나다라"

OPENING = "hold the line tonight"
CLOSING = "never let it go"


def assert_each_line_has_one_time(sheet: list[str], lrc: list[str], pairing: Pairing) -> None:
    """Every sheet line is in exactly one place, and no LRC line is given out twice."""
    sheet_lines = list(pairing.line_map())
    lrc_lines = list(pairing.line_map().values())
    for stretch in pairing.shared:
        sheet_lines += range(*stretch.sheet)
        lrc_lines += range(*stretch.lrc)
    assert sorted(sheet_lines) == list(range(len(sheet)))
    assert len(set(lrc_lines)) == len(lrc_lines) <= len(lrc)


class TestCleanSheetLines:
    def test_drops_lines_that_clean_to_nothing_and_strips_parenthesised_words(self):
        lines = ["hold the line (hold it)", "(oh oh)", "", "never let it go"]
        assert clean_sheet_lines(lines) == ["hold the line", "never let it go"]

    def test_a_sheet_typed_in_capitals_is_recased_as_the_cue_route_would(self):
        assert clean_sheet_lines(["HOLD THE LINE TONIGHT", "NEVER LET IT GO"]) == [
            "Hold the line tonight",
            "Never let it go",
        ]

    def test_cleaning_a_cleaned_sheet_changes_nothing(self):
        cleaned = clean_sheet_lines(["MULAN: hold the line", "(oh oh)", "- never let it go"])
        assert clean_sheet_lines(cleaned) == cleaned

    def test_no_lines_is_no_lines(self):
        assert clean_sheet_lines([]) == []


class TestPairLines:
    def test_every_line_pairs_by_text(self):
        lines = [OPENING, "we are the morning light", CLOSING]
        pairing = pair_lines(lines, list(lines))
        assert pairing.by_text == {0: 0, 1: 1, 2: 2}
        assert pairing.by_position == ()
        assert pairing.shared == ()

    def test_a_stretch_of_equal_counts_between_text_pairs_pairs_by_position(self):
        sheet = [OPENING, "romanized one", "romanized two", CLOSING]
        lrc = [OPENING, KOREAN_A, KOREAN_B, CLOSING]
        pairing = pair_lines(sheet, lrc)
        assert pairing.by_text == {0: 0, 3: 3}
        assert pairing.by_position == (Stretch((1, 3), (1, 3)),)
        assert pairing.shared == ()
        assert pairing.line_map() == {0: 0, 1: 1, 2: 2, 3: 3}

    def test_two_sheet_lines_against_one_lrc_line_share_it(self):
        sheet = [OPENING, "romanized one", "romanized two", CLOSING]
        pairing = pair_lines(sheet, [OPENING, KOREAN_A, CLOSING])
        assert pairing.by_text == {0: 0, 3: 2}
        assert pairing.by_position == ()
        assert pairing.shared == (Stretch((1, 3), (1, 2)),)

    def test_one_sheet_line_against_two_lrc_lines_shares_them(self):
        pairing = pair_lines(
            [OPENING, "romanized one", CLOSING], [OPENING, KOREAN_A, KOREAN_B, CLOSING]
        )
        assert pairing.by_text == {0: 0, 2: 3}
        assert pairing.shared == (Stretch((1, 2), (1, 3)),)

    def test_a_shared_stretch_leaves_the_text_pairs_each_side_alone(self):
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
        assert pairing.shared == (Stretch((1, 3), (1, 2)),)
        assert pairing.by_position == (Stretch((4, 6), (3, 5)),)

    def test_a_stretch_before_the_first_pair_and_after_the_last(self):
        sheet = ["intro one", "intro two", "the only anchor line", "outro"]
        lrc = [KOREAN_A, KOREAN_B, "the only anchor line", KOREAN_C]
        pairing = pair_lines(sheet, lrc)
        assert pairing.by_text == {2: 2}
        assert pairing.by_position == (Stretch((0, 2), (0, 2)), Stretch((3, 4), (3, 4)))
        assert pairing.shared == ()

    def test_a_sheet_line_the_lrc_lacks_takes_in_the_pair_before_it(self):
        sheet = ["first anchor line", "spoken aside", "second anchor line"]
        pairing = pair_lines(sheet, ["first anchor line", "second anchor line"])
        assert pairing.by_text == {2: 1}
        assert pairing.shared == (Stretch((0, 2), (0, 1)),)

    def test_an_lrc_line_the_sheet_lacks_takes_in_the_pair_before_it(self):
        sheet = ["first anchor line", "second anchor line"]
        pairing = pair_lines(sheet, ["first anchor line", KOREAN_A, "second anchor line"])
        assert pairing.by_text == {1: 2}
        assert pairing.shared == (Stretch((0, 1), (0, 2)),)

    def test_a_one_sided_stretch_at_the_start_takes_in_the_pair_after_it(self):
        pairing = pair_lines(["spoken intro", "the only anchor line"], ["the only anchor line"])
        assert pairing.by_text == {}
        assert pairing.shared == (Stretch((0, 2), (0, 1)),)

        sheet = ["the only anchor line", "tail words here"]
        pairing = pair_lines(sheet, [KOREAN_A, "the only anchor line", "tail words here"])
        assert pairing.by_text == {1: 2}
        assert pairing.shared == (Stretch((0, 1), (0, 2)),)

    def test_a_one_sided_stretch_at_the_end_takes_in_the_pair_before_it(self):
        pairing = pair_lines(["the only anchor line"], ["the only anchor line", KOREAN_A, KOREAN_B])
        assert pairing.by_text == {}
        assert pairing.shared == (Stretch((0, 1), (0, 3)),)

    def test_one_sided_stretches_around_one_pair_merge(self):
        # The LRC's intro before the pair and the sheet's extra lines after it both take
        # the pair in, and so are one stretch.
        sheet = [OPENING, "extra one", "extra two", CLOSING]
        pairing = pair_lines(sheet, [KOREAN_A, KOREAN_B, OPENING, CLOSING])
        assert pairing.by_text == {3: 3}
        assert pairing.shared == (Stretch((0, 3), (0, 3)),)

    def test_unequal_counts_with_no_text_pair_are_one_shared_stretch(self):
        pairing = pair_lines(["one", "two"], [KOREAN_A, KOREAN_B, KOREAN_C])
        assert pairing.by_text == {}
        assert pairing.shared == (Stretch((0, 2), (0, 3)),)

    def test_no_lrc_lines_leaves_the_sheet_with_nothing_to_share(self):
        pairing = pair_lines(["one line", "another line"], [])
        assert pairing.shared == (Stretch((0, 2), (0, 0)),)

    def test_no_sheet_lines_pairs_nothing(self):
        assert pair_lines([], [KOREAN_A, KOREAN_B]) == Pairing({}, (), ())
        assert pair_lines([], []) == Pairing({}, (), ())

    def test_a_duet_lrc_line_against_two_sheet_lines_shares_it(self):
        lrc_text = (
            "[00:10.00]hold the line tonight\n"
            "[00:14.00]she sings this\n"
            "[00:14.00]he sings that\n"
            "[00:18.00]never let it go\n"
        )
        lrc_lines, _ = cue_spans_from_srt(lrc_to_srt(lrc_text))
        assert lrc_lines[1] == "she sings this he sings that"
        sheet = [OPENING, "she sings this", "he sings that", CLOSING]
        pairing = pair_lines(sheet, lrc_lines)
        assert pairing.by_text == {0: 0, 3: 2}
        assert pairing.shared == (Stretch((1, 3), (1, 2)),)

    def test_a_repeated_chorus_keeps_each_instance_in_its_own_place(self):
        lines = [
            "verse one starts here",
            "chorus line number one",
            "chorus line number two",
            "verse two starts here",
            "chorus line number one",
            "chorus line number two",
        ]
        assert pair_lines(lines, list(lines)).by_text == {i: i for i in range(6)}

    def test_a_chorus_the_lrc_repeats_once_more_is_shared_with_the_line_before_it(self):
        # Which instance the sheet's last chorus pairs with is a tie; the extra one is
        # LRC lines with no sheet lines, so it is shared with the sheet line before it.
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
        assert pairing.shared == (Stretch((3, 4), (3, 7)),)
        assert_each_line_has_one_time(sheet, lrc, pairing)

    @pytest.mark.parametrize(
        "sheet, lrc",
        [
            ([OPENING, "romanized one", "romanized two", CLOSING], [OPENING, KOREAN_A, CLOSING]),
            ([OPENING, "extra one", "extra two", CLOSING], [KOREAN_A, KOREAN_B, OPENING, CLOSING]),
            (["spoken intro", "the only anchor line"], ["the only anchor line"]),
            (["the only anchor line"], ["the only anchor line", KOREAN_A, KOREAN_B]),
            (["one", "two"], [KOREAN_A, KOREAN_B, KOREAN_C]),
        ],
    )
    def test_every_sheet_line_ends_up_in_exactly_one_place(self, sheet, lrc):
        assert_each_line_has_one_time(sheet, lrc, pair_lines(sheet, lrc))


class TestTimedSheetSrt:
    SPANS = [(1.0, 4.5), (4.5, 9.25), (9.25, 12.0), (12.0, 20.5)]

    def test_each_paired_line_takes_its_lrc_lines_span(self):
        sheet = [OPENING, "romanized one", "romanized two", CLOSING]
        lrc = [OPENING, KOREAN_A, KOREAN_B, CLOSING]
        pairing = pair_lines(sheet, lrc)
        texts, spans = cue_spans_from_srt(timed_sheet_srt(sheet, self.SPANS, pairing))
        assert texts == sheet
        assert spans == self.SPANS

    def test_a_sheet_with_a_different_split_keeps_its_own_lines(self):
        sheet = [OPENING, CLOSING]
        pairing = pair_lines(sheet, [OPENING, CLOSING])
        texts, spans = cue_spans_from_srt(timed_sheet_srt(sheet, self.SPANS[:2], pairing))
        assert texts == sheet
        assert spans == self.SPANS[:2]

    def test_two_sheet_lines_divide_one_lrc_lines_time_by_character_count(self):
        sheet = [OPENING, "abcd", "abcdefghijkl", CLOSING]
        pairing = pair_lines(sheet, [OPENING, KOREAN_A, CLOSING])
        spans = [(1.0, 4.5), (4.5, 9.25), (9.25, 20.5)]
        assert line_spans(sheet, spans, pairing) == [
            (1.0, 4.5),
            (4.5, 5.6875),
            (5.6875, 9.25),
            (9.25, 20.5),
        ]

    def test_one_sheet_line_takes_the_time_of_all_its_lrc_lines(self):
        sheet = [OPENING, "romanized one", CLOSING]
        pairing = pair_lines(sheet, [OPENING, KOREAN_A, KOREAN_B, CLOSING])
        assert line_spans(sheet, self.SPANS, pairing) == [
            (1.0, 4.5),
            (4.5, 12.0),
            (12.0, 20.5),
        ]

    def test_a_pair_taken_into_a_shared_stretch_divides_the_time_with_the_extra_lines(self):
        first = "first anchor line"
        sheet = [first, "x" * len(first), "second anchor line"]
        pairing = pair_lines(sheet, [first, "second anchor line"])
        assert line_spans(sheet, [(0.0, 6.0), (6.0, 9.0)], pairing) == [
            (0.0, 3.0),
            (3.0, 6.0),
            (6.0, 9.0),
        ]

    def test_shared_lines_read_back_through_the_cue_route_unchanged(self):
        sheet = [OPENING, "romanized one", "romanized two", "romanized three", CLOSING]
        pairing = pair_lines(sheet, [OPENING, KOREAN_A, KOREAN_B, CLOSING])
        texts, spans = cue_spans_from_srt(timed_sheet_srt(sheet, self.SPANS, pairing))
        assert texts == sheet
        built = line_spans(sheet, self.SPANS, pairing)
        # An SRT keeps milliseconds.
        flat = pytest.approx([t for span in built for t in span], abs=0.001)
        assert [t for span in spans for t in span] == flat
        # Contiguous: each shared line ends where the next begins.
        assert [end for _, end in spans[1:3]] == [start for start, _ in spans[2:4]]

    def test_a_stretch_with_no_lrc_line_has_no_time_to_share(self):
        pairing = pair_lines(["first anchor line", "extra"], [])
        with pytest.raises(ValueError):
            timed_sheet_srt(["first anchor line", "extra"], self.SPANS, pairing)
