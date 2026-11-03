"""Tests for the SRT cue utilities (lib/srt_cues.py)."""

import pytest
import srt

from pikaraoke.lib.srt_cues import (
    clean_cue_texts,
    cue_spans_from_srt,
    cues_to_srt,
    offset_mad_against_cues,
)

# Cue files from the cleaning tests in this module (and the label-behind-a-tag pair), each
# one cleaned as a whole, to check that every cleaned line cleans to itself.
CUE_FILES = [
    ["(gentle music)", "<i>♪ Hello\nworld ♪</i>"],
    ["♪ I′M GOING UNDER,\nAND THIS TIME ♪", "'TIL I COME BACK AROUND", "WAIT. NOW I KNOW"],
    ["I'm going under", "and this time", "I fear there's no one", "HEY!"],
    ["DJ 放音乐", "走吧 OK", "你是我的 MVP"],
    ["ANNA:", "Hello there", "BOTH:"],
    ["ANNA: Hello there", "MR. POTTS: Be our guest", "<i>MEN: Be a man</i>", "Listen: it's time"],
    ["- ANNA: Hello there", "BOB: * Sing along *", "Hi\nCARL: bye"],
    ["ANNA: HELLO THERE", "I FEAR THERE'S NO ONE"],
    ["* Sing along *", "* Next line", "what the f***"],
    ["- Hello there. - What?", "- One\n- Two", "* - Sing it", "♪ - Sing it"],
    ["-Hello there. -What?", "-One\n-Two", "-Be a man -With all", "--miss it"],
    ["nine-to-five", "won- derful", "wait - what"],
    ["(gentle music)", "<i>Hello\nworld</i>", "- Hi. - What?"],
    ["HELLO THERE", "I KNOW", "(MUSIC)"],
    ["Hello there", "I know", "HEY!"],
    ["<i>Hi there</i>\n<i>MEN:</i> go now", "Hi there\n(softly) MARA: hey", "(soft\nly) MARA: hi"],
    ["MEN: MARA: hey", "- MEN: - MARA: hey", "* - * - Sing it"],
    ["Hey\nMEN: MARA: go", "OH\n- MEN: - MARA: go", "I\n* - * - go", "NO\rMEN: go"],
    ["*MEN: go", "-*<i>MEN:</i> go", "hey\n**MEN: go", "OH\nU2: go"],
    ["T.I.: Hello", "M.I.A.: go", "E-40: yeah", "R2-D2: Beep", "U2: day", "I I: so"],
    ["U2: LIVE TONIGHT", "I I: SO", "E-40: YEAH", "T.I.: HEY", "WE ARE HERE"],
    ["MULAN: GO", "MEN: NOW"],
    ["MULAN: HELLO", "WAIT. NOW I KNOW", "(music)"],
    ["(softly) MARA: hey there", "<i>MEN:</i> go now"],
    ["U2: LIVE TONIGHT", "WE ARE HERE"],
    ["R2-D2: BEEP", "C3PO: OH DEAR", "A1: GO"],
    ["I I: SO", "A. B: GO", "I. A: YES", "WE ARE HERE"],
]


class TestOffsetMadAgainstCues:
    """Direct tests of the pure offset-calibration step."""

    def test_consistent_anchors_fit_offset(self):
        anchors = [{"lid": i, "start": 10.0 * (i + 1)} for i in range(4)]
        cues = {i: (10.0 * (i + 1) - 1.5, 10.0 * (i + 1) - 1.5 + 2.0) for i in range(4)}
        stats = offset_mad_against_cues(anchors, cues)
        assert stats == {"n_anchors_fit": 4, "bailed": None, "offset_s": 1.5, "mad_s": 0.0}

    def test_few_anchors_bails_without_offset_or_mad(self):
        anchors = [{"lid": i, "start": 10.0 * (i + 1)} for i in range(3)]
        cues = {i: (10.0 * (i + 1) - 1.5, 10.0 * (i + 1) - 1.5 + 2.0) for i in range(3)}
        stats = offset_mad_against_cues(anchors, cues)
        assert stats == {"n_anchors_fit": 3, "bailed": "few_anchors"}

    def test_wide_spread_bails_but_still_reports_offset_and_mad(self):
        anchors = [{"lid": i, "start": 10.0 * (i + 1)} for i in range(4)]
        leads = (0.0, 0.9, 1.8, 3.6)
        cues = {
            i: (10.0 * (i + 1) - lead, 10.0 * (i + 1) - lead + 2.0) for i, lead in enumerate(leads)
        }
        stats = offset_mad_against_cues(anchors, cues)
        assert stats["bailed"] == "wide_spread"
        assert stats["n_anchors_fit"] == 4
        assert "offset_s" in stats and "mad_s" in stats

    def test_anchors_without_a_cue_are_ignored(self):
        anchors = [{"lid": 0, "start": 10.0}, {"lid": 99, "start": 999.0}]
        cues = {0: (8.5, 10.5)}
        stats = offset_mad_against_cues(anchors, cues)
        assert stats["n_anchors_fit"] == 1


class TestCueSpansFromSrt:
    def test_cleanup_and_spans_stay_parallel(self):
        srt_text = (
            "1\n00:00:01,000 --> 00:00:02,000\n(gentle music)\n"
            "\n2\n00:00:02,500 --> 00:00:04,000\n<i>♪ Hello\nworld ♪</i>\n"
        )
        texts, spans = cue_spans_from_srt(srt_text)
        assert texts == ["Hello world"]
        assert spans == [(2.5, 4.0)]

    @staticmethod
    def _srt(*cues: str) -> str:
        return "\n".join(
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\n{cue}\n"
            for i, cue in enumerate(cues, start=1)
        )

    def test_all_caps_file_is_recased(self):
        texts, _ = cue_spans_from_srt(
            self._srt(
                "♪ I′M GOING UNDER,\nAND THIS TIME ♪",
                "'TIL I COME BACK AROUND",
                "WAIT. NOW I KNOW",
            )
        )
        assert texts == [
            "I'm going under, and this time",
            "'Til I come back around",
            "Wait. Now I know",
        ]

    def test_shouted_line_in_a_normal_file_stays_as_written(self):
        texts, _ = cue_spans_from_srt(
            self._srt("I'm going under", "and this time", "I fear there's no one", "HEY!")
        )
        assert texts == ["I'm going under", "and this time", "I fear there's no one", "HEY!"]

    def test_caseless_script_is_not_recased_by_its_acronyms(self):
        """A caseless script has no lower case to dilute the share, so
        counting only cased letters made a handful of Latin acronyms read
        as a fully capitalized file."""
        cues = ["DJ 放音乐", "走吧 OK", "你是我的 MVP"]
        texts, _ = cue_spans_from_srt(self._srt(*cues))
        assert texts == cues

    def test_speaker_label_on_its_own_line_drops_the_cue(self):
        texts, spans = cue_spans_from_srt(self._srt("ANNA:", "Hello there", "BOTH:"))
        assert texts == ["Hello there"]
        assert spans == [(2.0, 2.9)]

    def test_inline_speaker_label_is_stripped_and_listen_style_prose_survives(self):
        texts, _ = cue_spans_from_srt(
            self._srt(
                "ANNA: Hello there",
                "MR. POTTS: Be our guest",
                "<i>MEN: Be a man</i>",
                "Listen: it's time",
            )
        )
        assert texts == ["Hello there", "Be our guest", "Be a man", "Listen: it's time"]

    def test_label_after_a_dialogue_dash_or_star_is_stripped(self):
        texts, _ = cue_spans_from_srt(
            self._srt("- ANNA: Hello there", "BOB: * Sing along *", "Hi\nCARL: bye")
        )
        assert texts == ["Hello there", "Sing along", "Hi bye"]

    def test_labels_survive_in_an_all_caps_file(self):
        texts, _ = cue_spans_from_srt(self._srt("ANNA: HELLO THERE", "I FEAR THERE'S NO ONE"))
        assert texts == ["Anna: hello there", "I fear there's no one"]

    def test_standalone_stars_are_stripped_and_censored_words_keep_theirs(self):
        texts, _ = cue_spans_from_srt(self._srt("* Sing along *", "* Next line", "what the f***"))
        assert texts == ["Sing along", "Next line", "what the f***"]

    def test_dialogue_dashes_at_line_start_and_after_a_sentence_end_are_stripped(self):
        texts, _ = cue_spans_from_srt(
            self._srt(
                "- Hello there. - What?",
                "- One\n- Two",
                "* - Sing it",
                "♪ - Sing it",
            )
        )
        assert texts == ["Hello there. What?", "One Two", "Sing it", "Sing it"]

    def test_glued_dialogue_dashes_are_stripped(self):
        """Many releases write the dash against the word: "-What?", "Be a man -With all"."""
        texts, _ = cue_spans_from_srt(
            self._srt("-Hello there. -What?", "-One\n-Two", "-Be a man -With all", "--miss it")
        )
        assert texts == ["Hello there. What?", "One Two", "Be a man With all", "miss it"]

    def test_hyphens_inside_words_and_a_spaced_dash_mid_sentence_stay(self):
        texts, _ = cue_spans_from_srt(self._srt("nine-to-five", "won- derful", "wait - what"))
        assert texts == ["nine-to-five", "won- derful", "wait - what"]


class TestCleanCueTexts:
    def test_each_cue_keeps_its_position_and_a_dropped_one_is_empty(self):
        assert clean_cue_texts(["(gentle music)", "<i>Hello\nworld</i>", "- Hi. - What?"]) == [
            "",
            "Hello world",
            "Hi. What?",
        ]

    def test_all_caps_is_decided_over_the_whole_list(self):
        assert clean_cue_texts(["HELLO THERE", "I KNOW", "(MUSIC)"]) == [
            "Hello there",
            "I know",
            "",
        ]
        assert clean_cue_texts(["Hello there", "I know", "HEY!"]) == [
            "Hello there",
            "I know",
            "HEY!",
        ]

    def test_speaker_label_is_kept_in_an_all_caps_list(self):
        assert clean_cue_texts(["MULAN: GO", "MEN: NOW"]) == ["Mulan: go", "Men: now"]

    def test_cleaning_twice_changes_nothing(self):
        once = clean_cue_texts(["MULAN: HELLO", "WAIT. NOW I KNOW", "(music)"])
        kept = [text for text in once if text]
        assert clean_cue_texts(kept) == kept

    def test_a_label_behind_parentheses_or_a_tag_is_stripped(self):
        assert clean_cue_texts(["(softly) MARA: hey there", "<i>MEN:</i> go now"]) == [
            "hey there",
            "go now",
        ]

    def test_a_label_behind_parentheses_or_a_tag_on_a_later_line_is_stripped(self):
        assert clean_cue_texts(
            ["<i>Hi there</i>\n<i>MEN:</i> go now", "Hi there\n(softly) MARA: hey"]
        ) == ["Hi there go now", "Hi there hey"]

    def test_a_label_or_dash_exposed_by_stripping_another_is_stripped(self):
        assert clean_cue_texts(["MEN: MARA: hey", "- MEN: - MARA: hey", "* - * - Sing it"]) == [
            "hey",
            "hey",
            "Sing it",
        ]

    def test_marks_on_a_later_line_are_judged_on_that_line(self):
        """A capitals line above is not taken into the label below it."""
        assert clean_cue_texts(
            ["Hey\nMEN: MARA: go", "OH\n- MEN: - MARA: go", "I\n* - * - go", "NO\rMEN: go"]
        ) == ["Hey go", "OH go", "I go", "NO go"]

    def test_a_star_before_a_label_goes_with_it(self):
        assert clean_cue_texts(["*MEN: go", "-*<i>MEN:</i> go", "hey\n**MEN: go"]) == [
            "go",
            "go",
            "hey go",
        ]

    def test_a_label_sentence_case_writes_as_it_stands_is_kept(self):
        """A label kept in a file typed in capitals and recased ("U2:", "I I:") is not one to
        a later cleaning; one that recases to something else is a label in any file."""
        assert clean_cue_texts(
            ["U2: Beautiful day", "E-40: yeah", "T.I.: Hello", "R2-D2: Beep", "M.I.A.: go"]
        ) == ["U2: Beautiful day", "E-40: yeah", "T.I.: Hello", "Beep", "go"]
        assert clean_cue_texts(["U2: LIVE TONIGHT", "I I: SO", "WE ARE HERE"]) == [
            "U2: live tonight",
            "I I: so",
            "We are here",
        ]

    @pytest.mark.parametrize("contents", CUE_FILES)
    def test_a_cleaned_cue_cleans_to_itself(self, contents):
        kept = [text for text in clean_cue_texts(contents) if text]
        assert clean_cue_texts(kept) == kept

    def test_cue_spans_are_the_cleaned_texts_that_survive(self):
        text = (
            "1\n00:00:01,000 --> 00:00:02,000\n(music)\n"
            "\n2\n00:00:02,500 --> 00:00:04,000\nHello\n"
        )
        texts, spans = cue_spans_from_srt(text)
        assert texts == ["Hello"]
        assert spans == [(2.5, 4.0)]


class TestCuesToSrt:
    def test_round_trip_gives_the_same_lines_and_spans(self):
        lines = ["Hello there", "Sing it loud", "Hello there"]
        spans = [(1.0, 2.5), (3.25, 5.0), (61.125, 63.5)]
        assert cue_spans_from_srt(cues_to_srt(lines, spans)) == (lines, spans)

    def test_a_zero_length_cue_is_written_back(self):
        lines = ["Hello there", "A blink", "Sing it loud"]
        spans = [(1.0, 2.5), (2.5, 2.5), (3.0, 5.0)]
        assert cue_spans_from_srt(cues_to_srt(lines, spans)) == (lines, spans)

    def test_cues_out_of_start_order_keep_their_sheet_order(self):
        lines = ["Second in time", "First in time", "Third in time"]
        spans = [(4.0, 5.0), (1.0, 2.0), (6.0, 7.0)]
        text = cues_to_srt(lines, spans)
        assert cue_spans_from_srt(text) == (lines, spans)
        assert [cue.index for cue in srt.parse(text)] == [1, 2, 3]

    def test_lines_and_spans_of_different_length_are_refused(self):
        with pytest.raises(ValueError):
            cues_to_srt(["one", "two"], [(0.0, 1.0)])
