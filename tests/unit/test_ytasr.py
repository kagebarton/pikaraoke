"""Tests for the YouTube auto-caption (ASR) parse/gate/map helpers (lib/ytasr.py)."""

import json

from pikaraoke.lib import ytasr
from pikaraoke.lib.token_align import _normalize_token


def _seg(text, offset=None):
    seg = {"utf8": text}
    if offset is not None:
        seg["tOffsetMs"] = offset
    return seg


def _json3(events):
    return json.dumps({"events": events})


def _words_from(tokens, step=0.5):
    """Synthetic word stream: evenly spaced, norms from the real tokenizer."""
    return [
        {"word": t, "norm": _normalize_token(t), "start": i * step, "end": i * step + step}
        for i, t in enumerate(tokens)
    ]


class TestParseJson3:
    def test_offset_math_and_word_spans(self):
        # First word carries no tOffsetMs (sits at the event start); the second
        # is offset 500ms into the event.
        events = [{"tStartMs": 1000, "segs": [_seg("hello"), _seg(" world", 500)]}]
        words, frac = ytasr.parse_json3(_json3(events))

        assert [w["word"] for w in words] == ["hello", "world"]
        assert words[0]["start"] == 1.0
        assert words[1]["start"] == 1.5
        # end = next word's start; the last word holds LAST_WORD_HOLD_S.
        assert words[0]["end"] == 1.5
        assert words[1]["end"] == 1.5 + ytasr.LAST_WORD_HOLD_S

    def test_word_seg_fraction_counts_offset_segs(self):
        # 3 non-empty segs, 2 carry tOffsetMs -> 2/3.
        events = [{"tStartMs": 0, "segs": [_seg("a"), _seg(" b", 100), _seg(" c", 200)]}]
        _, frac = ytasr.parse_json3(_json3(events))
        assert frac == 2 / 3

    def test_filters_music_notes_and_parens(self):
        events = [
            {
                "tStartMs": 1000,
                "segs": [
                    _seg("[Music]", 0),
                    _seg("♪", 100),
                    _seg("(applause)", 200),
                    _seg(" hello", 300),
                ],
            }
        ]
        words, frac = ytasr.parse_json3(_json3(events))

        assert [w["word"] for w in words] == ["hello"]
        # The fraction is measured on raw segs (before the filter), so a track
        # whose tags carry offsets isn't flattered into looking line-level.
        assert frac == 1.0

    def test_whitespace_only_segs_skipped(self):
        # The "\n" roll-up separators must not count toward the seg total.
        events = [{"tStartMs": 0, "segs": [_seg("\n"), _seg("hello", 0), _seg("\n")]}]
        words, frac = ytasr.parse_json3(_json3(events))
        assert [w["word"] for w in words] == ["hello"]
        assert frac == 1.0

    def test_word_end_capped_across_gaps(self):
        # end is inferred from the next word's start, so the word before an
        # instrumental break would otherwise inherit the whole gap.
        events = [
            {"tStartMs": 1000, "segs": [_seg("hello", 0)]},
            {"tStartMs": 31000, "segs": [_seg("again", 0)]},
        ]
        words, _ = ytasr.parse_json3(_json3(events))
        assert words[0]["end"] == 1.0 + ytasr.MAX_WORD_DUR_S

    def test_dedupes_consecutive_rollup(self):
        # Same word at the same start repeated by the rolling window collapses;
        # the same word at a later start is kept.
        events = [
            {"tStartMs": 1000, "segs": [_seg("hello", 0)]},
            {"tStartMs": 1000, "segs": [_seg("hello", 0)]},
            {"tStartMs": 2000, "segs": [_seg("hello", 0)]},
        ]
        words, _ = ytasr.parse_json3(_json3(events))
        assert [w["start"] for w in words] == [1.0, 2.0]


class TestIsUsable:
    def test_rejects_line_level_track(self):
        # 0% word-seg fraction == manual-mirrored / line-level.
        words = _words_from(["a", "b", "c"])
        assert ytasr.is_usable(words, 0.0, media_dur=180) is False

    def test_rejects_sparse_music_degeneracy(self):
        # 5 real words over a 5-minute song == 1 wpm, well under the floor.
        words = _words_from(["a", "b", "c", "d", "e"])
        assert ytasr.is_usable(words, 0.8, media_dur=300) is False

    def test_accepts_dense_real_asr(self):
        # 100 words over 5 minutes == 20 wpm, above MIN_CAPTION_WPM.
        words = _words_from(["w"] * 100)
        assert ytasr.is_usable(words, 0.8, media_dur=300) is True

    def test_rejects_when_duration_unknown(self):
        # Without a duration the density gate can't run, so bail (drop ytasr)
        # rather than adopt a possibly-degenerate caption unchecked.
        words = _words_from(["a", "b"])
        assert ytasr.is_usable(words, 0.8, media_dur=None) is False
        assert ytasr.is_usable(words, 0.8, media_dur=0) is False


class TestNormalizeWords:
    def test_drops_punctuation_only_tokens(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "--", "start": 0.5, "end": 0.6},
            {"word": "world", "start": 0.6, "end": 1.0},
        ]
        out = ytasr.normalize_words(words)
        assert [w["norm"] for w in out] == [_normalize_token("Hello"), _normalize_token("world")]
        assert out[0]["start"] == 0.0 and out[0]["end"] == 0.5

    def test_missing_end_defaults_to_start(self):
        out = ytasr.normalize_words([{"word": "hi", "start": 1.0}])
        assert out == [{"norm": _normalize_token("hi"), "start": 1.0, "end": 1.0}]


class TestCueSpansForLines:
    def test_maps_lines_and_leaves_unmatched_uncued(self):
        words = _words_from("when I see someone than wonderful".split())
        align_lines = ["when I see someone", "than wonderful", "not in this stream"]
        spans = ytasr.cue_spans_for_lines(words, align_lines)

        assert set(spans) == {0, 1}
        assert spans[0] == (words[0]["start"], words[3]["end"])
        assert spans[1] == (words[4]["start"], words[5]["end"])

    def test_monotonic_drops_backward_line(self):
        # The stream orders the words opposite to the lyric lines; keeping line 0
        # forbids line 1 from mapping to an earlier start.
        words = _words_from(["second", "first"])
        spans = ytasr.cue_spans_for_lines(words, ["first", "second"])
        assert set(spans) == {0}

    def test_tied_repeat_keeps_only_first_line(self):
        # Two identical lyric lines whose best hit is the same ASR occurrence
        # (equal score -> earliest-start tie-break) must not both claim it:
        # the second line gets no cue instead of a duplicate span.
        words = _words_from(["hakuna", "matata"])
        spans = ytasr.cue_spans_for_lines(words, ["hakuna matata", "hakuna matata"])
        assert set(spans) == {0}

    def test_tied_start_evicts_weaker_claimant(self):
        # A refrain line that is also the prefix of the following full line
        # ties on start index but with a lower matched-token score; the
        # occurrence belongs to the stronger (full-line) claimant.
        words = _words_from("hakuna matata what a wonderful phrase".split())
        spans = ytasr.cue_spans_for_lines(
            words, ["hakuna matata", "hakuna matata what a wonderful phrase"]
        )
        assert set(spans) == {1}
        assert spans[1] == (words[0]["start"], words[5]["end"])

    def test_none_when_nothing_maps(self):
        assert ytasr.cue_spans_for_lines([], ["anything"]) is None
        assert ytasr.cue_spans_for_lines(_words_from(["xyz"]), ["completely other words"]) is None
