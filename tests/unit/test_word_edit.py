"""Tests for editing a cue sheet's words line by line (lib/word_edit.py)."""

import pytest

from pikaraoke.lib.library_regen import RegenError
from pikaraoke.lib.srt_cues import cue_spans_from_srt, cues_to_srt
from pikaraoke.lib.word_edit import (
    EDIT_LINE_MAX_CHARS,
    STALE_MESSAGE,
    WordsCleaned,
    WordSheet,
    edited_srt,
)

LINES = [
    "Moon over the river",
    "Carry me home",
    "Down by the old mill",
    "Carry me home",
    "Sing it again",
]
SPANS = [(1.0, 3.5), (4.0, 6.25), (7.0, 9.5), (10.0, 12.125), (13.0, 15.0)]


@pytest.fixture
def sheet():
    return WordSheet(kind="lrclib_edited", lines=list(LINES), spans=list(SPANS))


def edit(sheet, **changed):
    """The page's boxes: the sheet's lines with the ``{index: text}`` changes."""
    boxes = list(sheet.lines)
    for index, text in changed.items():
        boxes[int(index[1:])] = text
    return boxes


class TestARefusedSave:
    @pytest.mark.parametrize(
        "original",
        [
            None,
            "Moon over the river",
            tuple(LINES),
            LINES[:-1],
            [*LINES[:-1], "Sing it once more"],
            [*LINES[:-1], 5],
        ],
        ids=["none", "text", "tuple", "shorter", "other_words", "not_text"],
    )
    def test_a_page_opened_on_other_lyrics_is_stale(self, sheet, original):
        with pytest.raises(RegenError) as refused:
            edited_srt(sheet, original, edit(sheet, l0="Moon on the river"))

        assert str(refused.value) == STALE_MESSAGE

    @pytest.mark.parametrize(
        "boxes",
        [
            None,
            "Moon on the river",
            LINES[:-1],
            [*LINES, "One more"],
            [None, *LINES[1:]],
            [["Moon"], *LINES[1:]],
        ],
        ids=["none", "text", "short", "long", "none_box", "list_box"],
    )
    def test_boxes_that_are_not_one_text_per_line_are_stale(self, sheet, boxes):
        with pytest.raises(RegenError) as refused:
            edited_srt(sheet, LINES, boxes)

        assert str(refused.value) == STALE_MESSAGE

    def test_a_line_over_the_limit_is_refused_by_its_number(self, sheet):
        boxes = edit(sheet, l2="a" * (EDIT_LINE_MAX_CHARS + 1))

        with pytest.raises(RegenError) as refused:
            edited_srt(sheet, LINES, boxes)

        assert str(refused.value) == "Line 3 is too long."

    def test_a_line_of_exactly_the_limit_is_taken(self, sheet):
        text = "a" * EDIT_LINE_MAX_CHARS

        assert text in edited_srt(sheet, LINES, edit(sheet, l2=text))

    def test_the_limit_counts_a_line_after_its_spaces_collapse(self, sheet):
        padded = "Down  " + " " * 400 + "by\nthe old mill"

        saved = edited_srt(sheet, LINES, edit(sheet, l2=padded, l0="Moon on the river"))

        assert "Down by the old mill" in saved

    def test_a_save_that_changes_nothing_is_refused(self, sheet):
        with pytest.raises(RegenError) as refused:
            edited_srt(sheet, LINES, list(LINES))

        assert str(refused.value) == "No line was changed."

    def test_a_change_of_spacing_alone_is_no_change(self, sheet):
        with pytest.raises(RegenError) as refused:
            edited_srt(sheet, LINES, edit(sheet, l1="  Carry   me\thome "))

        assert str(refused.value) == "No line was changed."

    @pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
    def test_clearing_every_line_is_refused(self, sheet, blank):
        with pytest.raises(RegenError) as refused:
            edited_srt(sheet, LINES, [blank] * len(LINES))

        assert str(refused.value) == (
            "Every line is cleared. To replace the lyrics, use Repair lyrics."
        )

    def test_the_checks_run_in_order(self, sheet):
        # Stale wins over everything else wrong with the save...
        boxes = edit(sheet, l0="a" * (EDIT_LINE_MAX_CHARS + 1))
        with pytest.raises(RegenError) as stale:
            edited_srt(sheet, [*LINES[:-1], "Other"], boxes)
        assert str(stale.value) == STALE_MESSAGE

        # ...too long wins over a cleaning change...
        boxes = edit(sheet, l0="a" * (EDIT_LINE_MAX_CHARS + 1), l1="Carry me (home)")
        with pytest.raises(RegenError) as too_long:
            edited_srt(sheet, LINES, boxes)
        assert str(too_long.value) == "Line 1 is too long."

        # ...and cleared lines are dropped before the cleaning is checked.
        boxes = [""] * 4 + ["Sing it (again)"]
        with pytest.raises(WordsCleaned) as cleaned:
            edited_srt(sheet, LINES, boxes)
        assert cleaned.value.cleaned == {4: "Sing it"}


class TestACleaningChange:
    def test_parentheses_and_a_singer_label_come_back_cleaned(self, sheet):
        boxes = edit(sheet, l1="Carry me (oh oh) home", l2="MARA: Down by the old mill")

        with pytest.raises(WordsCleaned) as refused:
            edited_srt(sheet, LINES, boxes)

        assert refused.value.cleaned == {1: "Carry me home", 2: "Down by the old mill"}

    def test_a_line_that_cleans_to_nothing_comes_back_empty(self, sheet):
        with pytest.raises(WordsCleaned) as refused:
            edited_srt(sheet, LINES, edit(sheet, l3="(la la la)", l0="Moon on the river"))

        assert refused.value.cleaned == {3: ""}

    def test_a_line_with_no_letters_cleans_to_nothing(self, sheet):
        with pytest.raises(WordsCleaned) as refused:
            edited_srt(sheet, LINES, edit(sheet, l3="1 2 3 4"))

        assert refused.value.cleaned == {3: ""}

    def test_the_indexes_count_the_lines_cleared_before_them(self, sheet):
        boxes = ["", "", "Down by (the) old mill", "", "MARA: Sing it again"]

        with pytest.raises(WordsCleaned) as refused:
            edited_srt(sheet, LINES, boxes)

        assert refused.value.cleaned == {2: "Down by old mill", 4: "Sing it again"}

    def test_it_is_a_regen_error_for_a_caller_that_only_knows_those(self, sheet):
        with pytest.raises(RegenError):
            edited_srt(sheet, LINES, edit(sheet, l0="Moon (on) the river"))

    def test_untouched_lines_are_never_listed(self, sheet):
        with pytest.raises(WordsCleaned) as refused:
            edited_srt(sheet, LINES, edit(sheet, l4="Sing it (again)"))

        assert list(refused.value.cleaned) == [4]


class TestASavedEdit:
    def test_every_kept_line_keeps_its_span(self, sheet):
        saved = edited_srt(sheet, LINES, edit(sheet, l0="Moon on the river", l3="Carry us home"))

        assert cue_spans_from_srt(saved) == (
            [
                "Moon on the river",
                "Carry me home",
                "Down by the old mill",
                "Carry us home",
                "Sing it again",
            ],
            SPANS,
        )

    def test_a_cleared_line_is_dropped_with_its_span(self, sheet):
        saved = edited_srt(sheet, LINES, edit(sheet, l2="", l1="Carry us home"))

        texts, spans = cue_spans_from_srt(saved)

        assert texts == ["Moon over the river", "Carry us home", "Carry me home", "Sing it again"]
        assert spans == [SPANS[0], SPANS[1], SPANS[3], SPANS[4]]

    def test_spaces_are_collapsed_in_what_is_saved(self, sheet):
        saved = edited_srt(sheet, LINES, edit(sheet, l0="  Moon   on\tthe river "))

        assert cue_spans_from_srt(saved)[0][0] == "Moon on the river"

    def test_clearing_the_last_line_drops_it_and_keeps_the_others(self, sheet):
        saved = edited_srt(sheet, LINES, edit(sheet, l2="Down by the new mill", l4=""))

        assert cue_spans_from_srt(saved) == (
            ["Moon over the river", "Carry me home", "Down by the new mill", "Carry me home"],
            SPANS[:4],
        )

    def test_a_second_edit_of_the_saved_sheet_works_the_same(self, sheet):
        texts, spans = cue_spans_from_srt(
            edited_srt(sheet, LINES, edit(sheet, l0="Moon on the river"))
        )
        again = WordSheet(kind=sheet.kind, lines=texts, spans=spans)

        saved = edited_srt(again, texts, ["Moon on the water", *texts[1:]])

        assert cue_spans_from_srt(saved) == (["Moon on the water", *texts[1:]], SPANS)

    def test_a_label_that_sat_behind_a_tag_does_not_make_untouched_lines_refused(self):
        raw = (
            "1\n00:00:01,000 --> 00:00:03,500\n(softly) MARA: hey there\n\n"
            "2\n00:00:04,000 --> 00:00:06,250\n<i>MEN:</i> go now\n\n"
            "3\n00:00:07,000 --> 00:00:09,500\nSing it again\n"
        )
        texts, spans = cue_spans_from_srt(raw)
        sheet = WordSheet(kind="caption_edited", lines=texts, spans=spans)
        boxes = [texts[0], texts[1], "Sing it once more"]

        saved = edited_srt(sheet, texts, boxes)

        assert texts == ["hey there", "go now", "Sing it again"]
        assert cue_spans_from_srt(saved) == (boxes, spans)

    def test_a_song_typed_in_capitals_edits_as_cleaned_sentence_case(self):
        capitals = cues_to_srt(
            ["MOON OVER THE RIVER", "CARRY ME HOME", "DOWN BY THE OLD MILL"], SPANS[:3]
        )
        texts, spans = cue_spans_from_srt(capitals)
        sheet = WordSheet(kind="caption_edited", lines=texts, spans=spans)

        saved = edited_srt(sheet, texts, ["Moon over the river", "Carry us home", texts[2]])

        assert cue_spans_from_srt(saved) == (
            ["Moon over the river", "Carry us home", "Down by the old mill"],
            SPANS[:3],
        )
