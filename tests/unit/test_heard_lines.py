"""Unit tests for the transcriber-as-reference helpers (made-up lines only)."""

from pikaraoke.lib.heard_lines import HeardLine, confirms, heard_lines, runs_heard
from pikaraoke.lib.joint_match import _tokenise_lines


def _heard(*words: tuple[str, float]) -> list[dict]:
    """Transcriber words of 0.3 s each."""
    return [{"word": w, "start": s, "end": s + 0.3} for w, s in words]


def _line(*words: tuple[str, float, float]) -> dict:
    """A line object from ``(word, start, end)`` triples."""
    return {"words": [{"word": w, "start": s, "end": e} for w, s, e in words]}


def _hl(*words: tuple[str, float], first: bool = True) -> HeardLine:
    return HeardLine(tuple(_heard(*words)), first=first)


class TestHeardLines:
    def test_a_line_heard_in_full(self):
        heard = heard_lines(
            ["zim zam zoom"], [(10.0, 13.0)], _heard(("zim", 10.1), ("zam", 11.1), ("zoom", 12.1))
        )
        (line,) = heard
        assert [w["word"] for w in line.words] == ["zim", "zam", "zoom"]
        assert line.first and line.start == 10.1

    def test_a_line_under_half_matched_is_not_heard(self):
        # Two of five tokens: enough words, too small a share of the line.
        heard = heard_lines(
            ["zim zam zoom flub blip"], [(10.0, 15.0)], _heard(("zim", 10.1), ("zam", 11.1))
        )
        assert heard == [None]

    def test_one_matched_word_of_five_is_not_heard(self):
        heard = heard_lines(["zim zam zoom flub blip"], [(10.0, 15.0)], _heard(("zim", 10.1)))
        assert heard == [None]

    def test_a_one_word_line_is_never_heard(self):
        assert heard_lines(["zim"], [(10.0, 11.0)], _heard(("zim", 10.1))) == [None]

    def test_it_is_heard_without_its_first_token(self):
        heard = heard_lines(["blip zim zam"], [(10.0, 13.0)], _heard(("zim", 11.1), ("zam", 12.1)))
        (line,) = heard
        assert not line.first and line.start == 11.1

    def test_punctuation_and_case_do_not_hide_a_match(self):
        heard = heard_lines(["Zim, zam!"], [(10.0, 12.0)], _heard((" zim", 10.1), ("ZAM.", 11.1)))
        assert heard[0] is not None

    def test_two_identical_lines_each_get_their_own_words(self):
        heard = heard_lines(
            ["zim zam", "zim zam"],
            [(10.0, 12.0), (14.0, 16.0)],
            _heard(("zim", 10.1), ("zam", 11.1), ("zim", 14.2), ("zam", 15.1)),
        )
        assert [line.start for line in heard] == [10.1, 14.2]

    def test_the_second_of_two_identical_lines_unheard(self):
        line_toks = _tokenise_lines(["zim zam", "zim zam", "flub blip"])
        heard = heard_lines(
            ["zim zam", "zim zam", "flub blip"],
            [(10.0, 12.0), (14.0, 16.0), (18.0, 20.0)],
            _heard(("zim", 10.1), ("zam", 11.1), ("flub", 18.1), ("blip", 19.1)),
        )
        assert heard[0] is not None and heard[1] is None and heard[2] is not None
        # The run is not fully heard, so neither of its lines may be confirmed; the line
        # outside the run is unaffected.
        assert runs_heard(line_toks, heard) == [False, False, True]

    def test_repeats_that_are_not_adjacent_are_not_a_run(self):
        line_toks = _tokenise_lines(["zim zam", "flub blip", "zim zam"])
        heard = [_hl(("zim", 10.1), ("zam", 11.1)), None, None]
        assert runs_heard(line_toks, heard) == [True, True, True]

    def test_no_heard_words(self):
        spans = [(10.0, 12.0), (14.0, 16.0)]
        assert heard_lines(["zim zam", "flub blip"], spans, None) == [None, None]
        assert heard_lines(["zim zam", "flub blip"], spans, []) == [None, None]

    def test_a_line_without_a_span_is_not_heard(self):
        heard = heard_lines(
            ["zim zam", "flub blip"],
            [(10.0, 12.0)],
            _heard(("zim", 10.1), ("zam", 11.1), ("flub", 14.1), ("blip", 15.1)),
        )
        assert heard[0] is not None and heard[1] is None


class TestConfirms:
    HEARD = _hl(("zim", 10.1), ("zam", 11.1), ("zoom", 12.1))

    def test_a_line_on_its_heard_words(self):
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.5), ("zoom", 12.0, 12.5))
        assert confirms(obj, 3, self.HEARD, True)

    def test_a_pair_1_2_s_apart_refuses(self):
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.5), ("zoom", 13.3, 13.8))
        assert not confirms(obj, 3, self.HEARD, True)

    def test_a_zero_length_word_is_ignored_not_held_against_the_line(self):
        # "zam" is a failed alignment parked 5 s away: it neither pairs nor contradicts.
        obj = _line(("zim", 10.0, 10.5), ("zam", 16.0, 16.0), ("zoom", 12.0, 12.5))
        assert confirms(obj, 3, self.HEARD, True)

    def test_zero_length_words_do_not_count_toward_the_minimum(self):
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.0), ("zoom", 12.0, 12.0))
        assert not confirms(obj, 3, self.HEARD, True)

    def test_under_half_the_line_paired_refuses(self):
        # Two pairs, but of five tokens.
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.5))
        assert not confirms(obj, 5, self.HEARD, True)

    def test_a_line_that_was_not_heard_refuses(self):
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.5))
        assert not confirms(obj, 2, None, True)

    def test_a_run_not_fully_heard_refuses(self):
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.5), ("zoom", 12.0, 12.5))
        assert not confirms(obj, 3, self.HEARD, False)

    def test_a_line_with_no_words_refuses(self):
        assert not confirms(_line(), 3, self.HEARD, True)

    def test_the_first_token_need_not_be_heard(self):
        heard = _hl(("zam", 11.1), ("zoom", 12.1), first=False)
        obj = _line(("zim", 10.0, 10.5), ("zam", 11.0, 11.5), ("zoom", 12.0, 12.5))
        assert confirms(obj, 3, heard, True)
