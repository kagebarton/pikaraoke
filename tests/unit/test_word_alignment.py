"""Unit tests for the two-pointer walk word-to-line matcher."""

from pikaraoke.lib.word_alignment import (
    _match_simple,
    _normalize_token,
    _walk_align,
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
        # Full-width Latin → ASCII Latin under NFKC.
        assert _normalize_token("Ｈｅｌｌｏ") == "hello"

    def test_empty(self):
        assert _normalize_token("!") == ""


# ---------------------------------------------------------------------------
# Simple equivalence
# ---------------------------------------------------------------------------


class TestMatchSimple:
    def test_exact(self):
        assert _match_simple("hello", "hello") is True

    def test_contraction_1to1(self):
        # Whisper says "do not", lyric token slice happens to be "dont".
        assert _match_simple("dont", "do") is True
        assert _match_simple("dont", "not") is True

    def test_contraction_reverse(self):
        # Reverse direction: lyric "do", whisper "dont".
        assert _match_simple("do", "dont") is True

    def test_no_fuzzy(self):
        # Walk matcher is strict — no Levenshtein, no phonetic fallback.
        assert _match_simple("helo", "hello") is False
        assert _match_simple("mm", "mmm") is False

    def test_mismatch(self):
        assert _match_simple("abc", "xyz") is False


# ---------------------------------------------------------------------------
# Walk alignment (private)
# ---------------------------------------------------------------------------


class TestWalkAlign:
    def test_clean_alignment(self):
        mapping = _walk_align(["hello", "world"], ["hello", "world"])
        assert mapping == [0, 1]

    def test_skips_hallucinated_whisper_word(self):
        # Whisper inserts an extra token between two lyric tokens.
        mapping = _walk_align(["hello", "world"], ["hello", "phantom", "world"])
        assert mapping == [0, 2]

    def test_unmatched_lyric_token_stays_none(self):
        # Lyric token has no whisper counterpart within the lookahead window.
        mapping = _walk_align(["hello", "missing", "world"], ["hello", "world"])
        assert mapping[0] == 0
        assert mapping[1] is None
        assert mapping[2] == 1

    def test_desync_past_lookahead_is_lossy(self):
        # Lookahead=3 can recover up to 3 skips; beyond that the matcher
        # advances both pointers blindly and may lose alignment.
        lyric = ["a", "b", "c", "d", "e"]
        whisper = ["x1", "x2", "x3", "x4", "x5", "a", "b", "c", "d", "e"]
        mapping = _walk_align(lyric, whisper, lookahead=3)
        # Lookahead window of 3 isn't enough to skip 5 hallucinations.
        assert mapping.count(None) > 0


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

    def test_paren_only_line_inherits_neighbor_timing(self):
        # A line with no normalizable tokens picks up bracketing timestamps.
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 2.0, "end": 3.0},
        ]
        lines = ["hello", "(instrumental)", "world"]
        align_lines = ["hello", "", "world"]
        result = match_words_to_lines(words, lines, align_lines)
        assert len(result) == 3
        assert result[1]["start"] == 1.0
        assert result[1]["end"] == 2.0

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
        words: list = []
        lines = ["hello"]
        result = match_words_to_lines(words, lines)
        assert len(result) == 1
        assert result[0]["words"] == []

    def test_no_lyrics_returns_empty(self):
        words = [{"word": "hello", "start": 0.0, "end": 1.0}]
        lines: list[str] = []
        result = match_words_to_lines(words, lines)
        assert result == []

    def test_unmatched_lyric_tokens_are_interpolated(self):
        # Walk matcher is gap-free: every reference token gets an entry,
        # even when there's no whisper anchor for it.
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 3.0, "end": 4.0},
        ]
        # "lost" has no whisper counterpart — should be interpolated
        # linearly between 1.0 and 3.0.
        lines = ["hello lost world"]
        result = match_words_to_lines(words, lines)
        assert len(result[0]["words"]) == 3
        interpolated = result[0]["words"][1]
        assert interpolated["word"] == "lost"
        assert interpolated["start"] == 1.0
        assert interpolated["end"] == 3.0

    def test_punctuation_difference_still_matches(self):
        words = [
            {"word": "hello,", "start": 0.0, "end": 0.5},
            {"word": "world!", "start": 0.5, "end": 1.0},
        ]
        lines = ["Hello world"]
        result = match_words_to_lines(words, lines)
        assert len(result[0]["words"]) == 2

    def test_hallucination_silently_dropped(self):
        # A whisper token between two lyric tokens that matches nothing
        # should not appear in any line's words list.
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
        # Walk matcher must still align every lyric token without cascading.
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
        assert any(w["word"] == "anymore" for w in result[1]["words"])

    def test_pass_through_extra_word_fields(self):
        # speaker / dominant_speaker initialized in _extract_words must
        # survive the round-trip into the line_obj's words list.
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
