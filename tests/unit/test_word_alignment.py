"""Unit tests for the Needleman-Wunsch word-to-line matcher.

Tests ported from mpv/genius_diarize/word_extraction.py and expanded
to cover the public API of pikaraoke.lib.word_alignment.
"""

import pytest

from pikaraoke.lib.word_alignment import (
    _BAND_MIN_LENGTH,
    _levenshtein,
    _needleman_wunsch,
    _needleman_wunsch_banded,
    _needleman_wunsch_unbanded,
    _normalize_token,
    _score,
    match_words_to_lines,
)

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalizeToken:
    def test_lowercase(self):
        assert _normalize_token("Hello") == "hello"

    def test_strips_punctuation(self):
        assert _normalize_token("Hello!") == "hello"

    def test_nfkc_normalization(self):
        # NFKC should normalize full-width chars
        result = _normalize_token("Ｈｅｌｌｏ")
        assert result == "hello"

    def test_empty(self):
        assert _normalize_token("!") == ""


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScore:
    def test_exact_long_match(self):
        # >= 6 chars gets anchor bonus
        assert _score("hellooo", "hellooo") == 3

    def test_exact_short_match(self):
        assert _score("hi", "hi") == 2

    def test_anchor_bonus_only_at_six_chars(self):
        # 5 chars exact -> +2; 6 chars exact -> +3
        assert _score("falli", "falli") == 2
        assert _score("fallin", "fallin") == 3

    def test_contraction(self):
        # _score works on normalized tokens (no apostrophes)
        assert _score("dont", "dont") == 2

    def test_contraction_split_lyric_to_whisper(self):
        # lyric "dont" -> _CONTRACTIONS expansion "do not";
        # whisper says "do" alone -> still scores +2.
        assert _score("dont", "do") == 2
        assert _score("dont", "not") == 2

    def test_contraction_split_whisper_to_lyric(self):
        # Reverse direction: whisper says "dont", lyric says "do".
        assert _score("do", "dont") == 2

    def test_phonetic_equiv(self):
        assert _score("mmm", "mm") == 1
        assert _score("ooh", "oo") == 1

    def test_fuzzy_single_edit(self):
        # Levenshtein-1 fires only when both tokens are >= 3 chars
        assert _score("helo", "hello") == 1

    def test_below_min_length_no_fuzzy(self):
        # Short tokens that differ by one char are NOT scored as fuzzy —
        # too easy to false-positive on common short words.
        assert _score("do", "to") == 0
        assert _score("of", "oh") == 0

    def test_mismatch(self):
        assert _score("abc", "xyz") == 0


# ---------------------------------------------------------------------------
# Levenshtein
# ---------------------------------------------------------------------------


class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("hello", "hello") == 0

    def test_one_insertion(self):
        assert _levenshtein("helo", "hello") == 1

    def test_one_deletion(self):
        assert _levenshtein("hello", "helo") == 1

    def test_one_substitution(self):
        assert _levenshtein("hello", "hallo") == 1

    def test_too_far_early_exit(self):
        # More than 1 char length difference triggers early exit returning 2
        assert _levenshtein("a", "xyz") == 2


# ---------------------------------------------------------------------------
# Needleman-Wunsch (private API)
# ---------------------------------------------------------------------------


class TestNeedlemanWunsch:
    def test_simple_alignment(self):
        lyric = ["hello", "world"]
        whisper = ["hello", "world"]
        alignment = _needleman_wunsch(lyric, whisper)
        # Each pair should be a direct match
        assert all(l == w for l, w in alignment if l is not None and w is not None)

    def test_with_gap(self):
        lyric = ["hello", "world"]
        whisper = ["hello", "there", "world"]
        alignment = _needleman_wunsch(lyric, whisper)
        # "there" should be a gap in lyric (w_idx but no l_idx)
        gaps = [w for l, w in alignment if l is None and w is not None]
        assert len(gaps) == 1

    def test_free_whisper_prefix(self):
        # Extra whisper words before any lyric token should be free —
        # all lyric tokens still match.
        lyric = ["hello", "world"]
        whisper = ["one", "two", "three", "hello", "world"]
        alignment = _needleman_wunsch(lyric, whisper)
        matched_l = {l for l, w in alignment if l is not None and w is not None}
        assert matched_l == {0, 1}

    def test_free_whisper_suffix(self):
        # Extra whisper words after the last lyric token should also be free.
        lyric = ["hello", "world"]
        whisper = ["hello", "world", "outro", "ad", "lib"]
        alignment = _needleman_wunsch(lyric, whisper)
        matched_l = {l for l, w in alignment if l is not None and w is not None}
        assert matched_l == {0, 1}

    def test_lyric_gap_when_word_missing(self):
        # If a lyric token has no whisper counterpart, NW emits a (l_idx, None) pair.
        lyric = ["hello", "missing", "world"]
        whisper = ["hello", "world"]
        alignment = _needleman_wunsch(lyric, whisper)
        l_gaps = [l for l, w in alignment if l is not None and w is None]
        assert l_gaps == [1]


class TestBanding:
    def _diag_seq(self, n: int) -> list[str]:
        # Build a clean lyric sequence long enough to trigger banding.
        return [f"word{i:04d}" for i in range(n)]

    def test_short_dispatches_unbanded(self):
        # max(m, n) <= _BAND_MIN_LENGTH stays unbanded
        n = _BAND_MIN_LENGTH
        seq = self._diag_seq(n)
        a = _needleman_wunsch(seq, seq)
        b = _needleman_wunsch_unbanded(seq, seq)
        assert a == b

    def test_long_uses_banded_and_matches_unbanded(self):
        # Above the band threshold, the dispatcher uses banded NW.
        # On clean diagonal input, the result must equal unbanded NW.
        n = _BAND_MIN_LENGTH + 50
        seq = self._diag_seq(n)
        banded = _needleman_wunsch_banded(seq, seq)
        unbanded = _needleman_wunsch_unbanded(seq, seq)
        assert banded == unbanded

    def test_banded_falls_back_when_degenerate(self):
        # If the band clips the true alignment so badly that the score
        # falls below the floor, banded NW should re-run unbanded and
        # still match every token.
        n = _BAND_MIN_LENGTH + 100
        lyric = self._diag_seq(n)
        # Reverse the whisper sequence so the diagonal is unreachable
        # from the band -> fallback path triggers.
        whisper = list(reversed(lyric))
        banded = _needleman_wunsch_banded(lyric, whisper)
        unbanded = _needleman_wunsch_unbanded(lyric, whisper)
        assert banded == unbanded


# ---------------------------------------------------------------------------
# match_words_to_lines (public API)
# ---------------------------------------------------------------------------


class TestMatchWordsToLines:
    def test_basic_match(self):
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
        ]
        lines = ["Hello world"]
        result = match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 1.0

    def test_multiline_match(self):
        words = [
            {"word": "A", "start": 0.0, "end": 0.5},
            {"word": "B", "start": 0.5, "end": 1.0},
            {"word": "C", "start": 1.0, "end": 1.5},
        ]
        lines = ["A B", "C"]
        result = match_words_to_lines(words, lines)
        assert len(result) == 2
        assert result[0]["text"] == "A B"
        assert result[1]["text"] == "C"

    def test_empty_lines_get_interpolated(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
        ]
        lines = ["hello", "", "world"]
        result = match_words_to_lines(words, lines)
        assert len(result) == 3
        assert result[0]["start"] == 0.0
        assert result[2]["start"] == result[1]["end"]

    def test_with_align_lines(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
        ]
        lines = ["hello (bonus)"]
        align_lines = ["hello"]
        result = match_words_to_lines(words, lines, align_lines)
        assert len(result) == 1
        assert result[0]["text"] == "hello (bonus)"

    def test_no_words_returns_empty(self):
        words = []
        lines = ["hello"]
        result = match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["words"] == []

    def test_no_lyrics_returns_empty(self):
        words = [{"word": "hello", "start": 0.0, "end": 1.0}]
        lines = []
        result = match_words_to_lines(words, lines)
        assert result == []

    def test_deduplicates_while_preserving_order(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
        ]
        lines = ["hello world hello"]
        result = match_words_to_lines(words, lines)
        # "hello" appears twice in lyric but should map to same whisper word (index 0)
        assert len(result) == 1
        # Should only have 2 unique words
        assert len(result[0]["words"]) == 2

    def test_punctuation_difference_still_matches(self):
        words = [
            {"word": "hello,", "start": 0.0, "end": 0.5},
            {"word": "world!", "start": 0.5, "end": 1.0},
        ]
        lines = ["Hello world"]
        result = match_words_to_lines(words, lines)
        assert len(result[0]["words"]) == 2

    def test_hallucination_silently_dropped(self):
        # An extra whisper token with no lyric counterpart shouldn't
        # appear in any line's words list.
        words = [
            {"word": "hello", "start": 0.0, "end": 0.5},
            {"word": "phantom", "start": 0.5, "end": 0.51},
            {"word": "world", "start": 0.6, "end": 1.0},
        ]
        lines = ["hello world"]
        result = match_words_to_lines(words, lines)
        words_emitted = [w["word"] for w in result[0]["words"]]
        assert "phantom" not in words_emitted
        assert words_emitted == ["hello", "world"]

    def test_contraction_split_no_cascade(self):
        # Lyric says "I don't know"; whisper splits as ["I", "do", "n't", "know"].
        # The count-based matcher would mis-slice every following line.
        # NW should still align every lyric token.
        words = [
            {"word": "I", "start": 0.0, "end": 0.1},
            {"word": "do", "start": 0.1, "end": 0.2},
            {"word": "n't", "start": 0.2, "end": 0.3},
            {"word": "know", "start": 0.3, "end": 0.5},
            {"word": "anymore", "start": 0.5, "end": 1.0},
        ]
        lines = ["I don't know", "anymore"]
        result = match_words_to_lines(words, lines)
        assert len(result) == 2
        # Second line must still anchor on "anymore"
        assert any(w["word"] == "anymore" for w in result[1]["words"])

    def test_pass_through_extra_word_fields(self):
        # speaker / dominant_speaker initialized in _extract_words must
        # survive the round-trip through NW into the line_obj's words list.
        words = [
            {
                "word": "hello",
                "start": 0.0,
                "end": 1.0,
                "speaker": None,
                "dominant_speaker": None,
            }
        ]
        lines = ["hello"]
        result = match_words_to_lines(words, lines)
        assert "speaker" in result[0]["words"][0]
        assert "dominant_speaker" in result[0]["words"][0]
