"""Tests for the backing-vocal keep rule (lib/backing_vocals.py)."""

from pikaraoke.lib.backing_vocals import ORIGINS, Verdict, judge, show_parens
from pikaraoke.lib.library_regen import LRC_ORIGIN, MOVIE_ORIGIN
from pikaraoke.lib.srt_cues import ParenCue, ParenGroup


def _cue(
    index: int,
    span: tuple[float, float],
    *texts: str,
    inline: bool = True,
    at: int | None = 1,
) -> ParenCue:
    groups = tuple(ParenGroup(text, at if inline else 0) for text in texts)
    return ParenCue(index, span, inline, index, groups)


def _heard(*words: tuple[str, float, float]) -> list[dict]:
    return [{"word": w, "start": s, "end": e, "probability": 0.9} for w, s, e in words]


def _verdicts(cues, heard=(), lines=(), offset=0.0) -> list[str]:
    return [v.verdict for v in judge(cues, list(lines), _heard(*heard), offset)]


class TestHeardShare:
    def test_half_of_the_distinct_words_is_heard_and_less_is_not(self):
        window = [("stand", 10.2, 10.6)]
        assert _verdicts([_cue(0, (10.0, 12.0), "stand tall")], window) == ["heard"]
        assert _verdicts([_cue(0, (10.0, 12.0), "stand tall now")], window) == ["not_heard"]

    def test_the_share_counts_distinct_words_not_repeats(self):
        window = [("stand", 10.2, 10.6)]
        assert _verdicts([_cue(0, (10.0, 12.0), "stand stand stand tall")], window) == ["heard"]

    def test_words_compare_by_their_normal_form(self):
        window = [("Don't", 10.0, 10.3), ("STOP,", 10.3, 10.6)]
        assert _verdicts([_cue(0, (10.0, 12.0), "dont stop")], window) == ["heard"]

    def test_hyphens_split_both_the_group_and_the_transcript(self):
        window = [("stand-tall", 10.0, 10.6)]
        assert _verdicts([_cue(0, (10.0, 12.0), "stand-up tall")], window) == ["heard"]

    def test_the_share_is_recorded_on_the_verdict(self):
        [verdict] = judge(
            [_cue(0, (10.0, 12.0), "stand tall now")], [], _heard(("stand", 10.0, 10.5)), 0.0
        )
        assert verdict == Verdict(0, 0, "inline", "not_heard", 1 / 3)

    def test_a_vocable_is_heard_as_another_of_its_class(self):
        window = [("oh", 10.0, 10.4)]
        assert judge([_cue(0, (10.0, 12.0), "ooh")], [], _heard(*window), 0.0)[0].verdict == (
            "heard"
        )

    def test_an_echo_is_heard_on_its_own_lines_words(self):
        """Nothing is used up: the lead's words in the window count for the echo."""
        window = [("baby", 10.0, 10.4), ("tonight", 10.4, 10.9)]
        assert _verdicts([_cue(0, (10.0, 12.0), "baby")], window) == ["heard"]


class TestWindow:
    def test_a_word_ending_exactly_where_the_padded_window_starts_is_out(self):
        cue = _cue(0, (10.0, 12.0), "stand tall")
        assert _verdicts([cue], [("stand", 9.0, 9.5)]) == ["not_heard"]
        assert _verdicts([cue], [("stand", 9.0, 9.6)]) == ["heard"]

    def test_a_word_starting_exactly_where_the_padded_window_ends_is_out(self):
        cue = _cue(0, (10.0, 12.0), "stand tall")
        assert _verdicts([cue], [("stand", 12.5, 13.0)]) == ["not_heard"]
        assert _verdicts([cue], [("stand", 12.4, 13.0)]) == ["heard"]

    def test_the_display_lead_shifts_the_window(self):
        cue = _cue(0, (10.0, 12.0), "stand tall")
        late = [("stand", 13.0, 13.4)]
        assert _verdicts([cue], late, offset=0.0) == ["not_heard"]
        assert _verdicts([cue], late, offset=2.0) == ["heard"]


class TestVocables:
    def test_a_vocable_only_group_is_kept_with_an_empty_transcript(self):
        [verdict] = judge([_cue(0, (10.0, 12.0), "la la")], [], [], 0.0)
        assert (verdict.verdict, verdict.share, verdict.kept) == ("vocable", 0.0, True)

    def test_a_group_with_one_word_beyond_the_vocables_is_not_kept(self):
        assert _verdicts([_cue(0, (10.0, 12.0), "la la tonight")]) == ["not_heard"]

    def test_a_group_with_no_word_once_normalised_is_not_heard(self):
        """All words of nothing are vocables, so this must be told before the vocable test."""
        assert _verdicts([_cue(0, (10.0, 12.0), "?!", "...")]) == ["not_heard", "not_heard"]


class TestConsistency:
    def test_an_unheard_repeat_of_a_heard_text_is_kept(self):
        cues = [_cue(0, (10.0, 12.0), "stand tall"), _cue(1, (50.0, 52.0), "Stand tall!")]
        assert _verdicts(cues, [("stand", 10.0, 10.5)]) == ["heard", "consistency"]

    def test_a_vocable_repeat_is_a_vocable_not_a_consistency_keep(self):
        cues = [_cue(0, (10.0, 12.0), "la la"), _cue(1, (50.0, 52.0), "la la")]
        assert _verdicts(cues) == ["vocable", "vocable"]

    def test_a_text_heard_nowhere_stays_dropped(self):
        cues = [_cue(0, (10.0, 12.0), "stand tall"), _cue(1, (50.0, 52.0), "stand tall")]
        assert _verdicts(cues) == ["not_heard", "not_heard"]

    def test_a_heard_quote_opened_group_is_dropped_and_keeps_no_repeat(self):
        cues = [_cue(0, (10.0, 12.0), '"Let It Go"'), _cue(1, (50.0, 52.0), "let it go")]
        heard = [("let", 10.0, 10.3), ("it", 10.3, 10.6), ("go", 10.6, 11.0)]
        assert _verdicts(cues, heard) == ["quote", "not_heard"]

    def test_an_unplaced_group_still_feeds_a_repeat(self):
        cues = [
            _cue(0, (10.0, 12.0), "stand tall", at=None),
            _cue(1, (50.0, 52.0), "stand tall"),
        ]
        assert _verdicts(cues, [("stand", 10.0, 10.5)]) == ["unplaced", "consistency"]


class TestPlacement:
    def test_an_inline_group_with_no_place_is_dropped_as_unplaced(self):
        cues = [_cue(0, (10.0, 12.0), "la la", at=None), _cue(1, (20.0, 22.0), "tonight", at=None)]
        assert _verdicts(cues) == ["unplaced", "not_heard"]

    def test_a_paren_only_cue_over_one_of_todays_lines_is_dropped_as_overlap(self):
        cue = _cue(0, (5.0, 7.0), "la la", inline=False)
        assert _verdicts([cue], lines=[(6.0, 8.0)]) == ["overlap"]

    def test_a_paren_only_cue_that_only_touches_a_line_is_kept(self):
        cue = _cue(0, (5.0, 7.0), "la la", inline=False)
        assert _verdicts([cue], lines=[(7.0, 9.0), (1.0, 5.0)]) == ["vocable"]

    def test_a_paren_only_cue_over_an_earlier_kept_paren_only_cue_is_dropped(self):
        cues = [
            _cue(0, (5.0, 7.0), "la la", inline=False),
            _cue(1, (6.5, 8.0), "oh oh", inline=False),
        ]
        assert _verdicts(cues) == ["vocable", "overlap"]

    def test_a_later_cue_over_only_a_dropped_one_is_kept(self):
        cues = [
            _cue(0, (5.0, 7.0), "la la", inline=False),
            _cue(1, (6.5, 8.0), "oh oh", inline=False),
        ]
        assert _verdicts(cues, lines=[(4.0, 6.0)]) == ["overlap", "vocable"]

    def test_an_unheard_paren_only_cue_does_not_take_the_time_from_a_later_one(self):
        cues = [
            _cue(0, (5.0, 7.0), "tonight", inline=False),
            _cue(1, (6.0, 8.0), "oh oh", inline=False),
        ]
        assert _verdicts(cues) == ["not_heard", "vocable"]

    def test_an_inline_cue_over_a_line_is_not_an_overlap(self):
        assert _verdicts([_cue(0, (5.0, 7.0), "la la")], lines=[(5.0, 7.0)]) == ["vocable"]

    def test_a_dropped_overlap_still_feeds_a_repeat(self):
        cues = [
            _cue(0, (5.0, 7.0), "stand tall", inline=False),
            _cue(1, (50.0, 52.0), "stand tall"),
        ]
        verdicts = _verdicts(cues, [("stand", 5.0, 5.5)], lines=[(6.0, 8.0)])
        assert verdicts == ["overlap", "consistency"]

    def test_the_cues_groups_are_judged_one_by_one(self):
        cue = _cue(0, (10.0, 12.0), "la la", "tonight", "stand tall")
        verdicts = judge([cue], [], _heard(("stand", 10.0, 10.5)), 0.0)
        assert [(v.group, v.verdict) for v in verdicts] == [
            (0, "vocable"),
            (1, "not_heard"),
            (2, "heard"),
        ]
        assert [v.kept for v in verdicts] == [True, False, True]


class TestOrigins:
    def test_the_origins_are_caption_and_lrclib_and_not_movie(self):
        assert ORIGINS == {"srt", LRC_ORIGIN}
        assert MOVIE_ORIGIN not in ORIGINS


def _line(line_id: int, *words: str, start: float = 1.0) -> dict:
    """A line object with its words timed 0.5 s apart, as the aligner leaves them."""
    timed = [
        {"word": w, "start": start + 0.5 * i, "end": start + 0.5 * i + 0.4}
        for i, w in enumerate(words)
    ]
    return {"line_id": line_id, "text": "", "words": timed, "start": start, "source": "x"}


def _shown(display: str, align: str, *words: str) -> list[str]:
    [out] = show_parens([_line(0, *words)], [display], [align])
    return [w["word"] for w in out["words"]]


class TestShowParens:
    def test_a_genius_line_shows_its_parentheses_and_keeps_every_time(self):
        line = _line(0, "I", "can't", "help", "Falling")
        [out] = show_parens([line], ["(I can't help) Falling"], ["I can't help Falling"])
        assert [w["word"] for w in out["words"]] == ["(I", "can't", "help)", "Falling"]
        assert [(w["start"], w["end"]) for w in out["words"]] == [
            (w["start"], w["end"]) for w in line["words"]
        ]
        assert {k: v for k, v in out.items() if k != "words"} == {
            k: v for k, v in line.items() if k != "words"
        }

    def test_the_input_line_objects_are_not_changed(self):
        line = _line(0, "oh", "oh")
        show_parens([line], ["oh (oh)"], ["oh oh"])
        assert [w["word"] for w in line["words"]] == ["oh", "oh"]

    def test_a_lone_open_paren_sticks_to_the_next_token_and_a_lone_close_to_the_previous(self):
        assert _shown("( oh ) hey", "oh hey", "oh", "hey") == ["(oh)", "hey"]
        assert _shown("oh ( oh )", "oh oh", "oh", "oh") == ["oh", "(oh)"]

    def test_a_paren_at_the_lines_end_joins_the_last_token(self):
        assert _shown("hey (", "hey", "hey") == ["hey("]
        assert _shown(") hey", "hey", "hey") == [")hey"]

    def test_a_word_the_aligner_dropped_leaves_the_others_on_their_own_tokens(self):
        assert _shown("(I can't help) Falling", "I can't help Falling", "I", "help", "Falling") == [
            "(I",
            "help)",
            "Falling",
        ]

    def test_an_echo_of_the_leads_word_takes_each_form_in_order(self):
        assert _shown("oh (oh)", "oh oh", "oh", "oh") == ["oh", "(oh)"]
        assert _shown("(oh) oh", "oh oh", "oh", "oh") == ["(oh)", "oh"]

    def test_a_word_with_no_token_left_keeps_its_text(self):
        assert _shown("(oh) hey", "oh hey", "oh", "hey", "yeah") == ["(oh)", "hey", "yeah"]

    def test_a_line_whose_display_equals_its_align_text_is_left_alone(self):
        line = _line(0, "(heeyyy]", "hey")
        [out] = show_parens([line], ["(heeyyy] hey"], ["(heeyyy] hey"])
        assert out is line

    def test_a_line_with_no_words_is_left_alone(self):
        interp = {"line_id": 0, "text": "", "words": [], "start": 4.0, "end": 5.0}
        assert show_parens([interp], ["(oh) hey"], ["oh hey"]) == [interp]

    def test_a_line_that_does_not_pair_keeps_its_text(self):
        assert _shown("Hello (oh) there", "Hello there", "Hello", "there") == ["Hello", "there"]
        assert _shown("(oh) there", "ah there", "ah", "there") == ["ah", "there"]

    def test_lines_are_found_by_their_line_id(self):
        lines = [_line(2, "hey"), _line(0, "oh")]
        out = show_parens(lines, ["(oh)", "x", "(hey)"], ["oh", "x", "hey"])
        assert [o["words"][0]["word"] for o in out] == ["(hey)", "(oh)"]
