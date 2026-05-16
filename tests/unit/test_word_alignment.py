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
        # Whisper inserts an extra token between two lyric tokens. The
        # whisper-skip budget lets the walker absorb it without losing
        # the lyric anchor.
        mapping = _walk_align(["hello", "world"], ["hello", "phantom", "world"])
        assert mapping == [0, 2]

    def test_unmatched_lyric_token_stays_none(self):
        # Lyric token has no whisper counterpart within the lookahead window.
        mapping = _walk_align(["hello", "missing", "world"], ["hello", "world"])
        assert mapping[0] == 0
        assert mapping[1] is None
        assert mapping[2] == 1

    def test_confirm_matches_rejects_spurious_anchor(self):
        # "i" appears in both streams but isn't the right re-sync point —
        # the next token doesn't match. With confirm_matches=2 the spurious
        # anchor is rejected.
        lyric = ["a", "b", "i", "c", "d"]
        whisper = ["i", "x", "y", "z"]
        mapping = _walk_align(
            lyric, whisper, lyric_lookahead=3, whisper_lookahead=3, confirm_matches=2
        )
        # The "i" candidate should be rejected; nothing matches confidently.
        assert mapping == [None, None, None, None, None]

    def test_absorbs_long_whisper_noise(self):
        # whisper_lookahead=10 lets the walker re-sync past a long run of
        # whisper-only tokens. Symmetric lookahead=3 wouldn't recover this.
        lyric = ["a", "b"]
        whisper = ["a", "x1", "x2", "x3", "x4", "x5", "x6", "x7", "b"]
        mapping = _walk_align(lyric, whisper)
        assert mapping == [0, 8]


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

    def test_short_unmatched_run_interpolated(self):
        # A 1-token unmatched run is below max_interp_run=5 and well above
        # min_interp_slot=0.1s, so it gets interpolated.
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 3.0, "end": 4.0},
        ]
        lines = ["hello lost world"]
        result = match_words_to_lines(words, lines)
        assert len(result[0]["words"]) == 3
        interpolated = result[0]["words"][1]
        assert interpolated["word"] == "lost"
        assert interpolated["start"] == 1.0
        assert interpolated["end"] == 3.0

    def test_long_unmatched_run_dropped(self):
        # 2 unmatched tokens > max_interp_run=1 → dropped, not interpolated.
        # Override max_interp_run instead of stuffing more lyric tokens
        # between the anchors: lyric_lookahead=3 caps how many we can
        # actually traverse, so the run-length cap is the cleaner knob to
        # exercise here.
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 30.0, "end": 31.0},
        ]
        lines = ["hello a b world"]
        result = match_words_to_lines(words, lines, max_interp_run=1)
        emitted = [w["word"] for w in result[0]["words"]]
        assert emitted == ["hello", "world"]

    def test_degenerate_interp_slot_dropped(self):
        # Two unmatched tokens bracketed by anchors 0.1s apart → per-token
        # slot 0.05s, below min_interp_slot=0.1s → drop.
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.1, "end": 2.0},
        ]
        lines = ["hello a b world"]
        result = match_words_to_lines(words, lines)
        emitted = [w["word"] for w in result[0]["words"]]
        assert emitted == ["hello", "world"]

    def test_collapsed_matched_run_demoted_and_dropped(self):
        # 12 lyric tokens all 1:1-matched to whisper words pinned at one
        # timestamp (stable-ts giving up). max_collapsed_run=8 with
        # collapse_window=0.3s → run is demoted to unmatched, then dropped
        # because the run length exceeds max_interp_run=5.
        lyric_words = [chr(ord("a") + i) for i in range(12)]
        words = [{"word": w, "start": 5.0, "end": 5.001} for w in lyric_words]
        # Bracket the collapsed run with clean anchors so the dropped run
        # has neighbors to interpolate against (the interp would still be
        # near-zero-slot, but the drop happens on length anyway).
        words = (
            [{"word": "start", "start": 0.0, "end": 1.0}]
            + words
            + [{"word": "end", "start": 10.0, "end": 11.0}]
        )
        lines = ["start " + " ".join(lyric_words) + " end"]
        result = match_words_to_lines(words, lines)
        emitted = [w["word"] for w in result[0]["words"]]
        # Only the bracketing anchors survive; the collapsed run is gone.
        assert emitted == ["start", "end"]

    def test_line_with_all_tokens_dropped_is_suppressed(self):
        # First line has only droppable tokens; should emit with words=[]
        # and start=None so the SRT/ASS generators skip it. max_interp_run=0
        # forces every unmatched run to drop, regardless of length.
        words = [
            {"word": "world", "start": 30.0, "end": 31.0},
        ]
        lines = ["a b", "world"]
        result = match_words_to_lines(words, lines, max_interp_run=0)
        assert result[0]["words"] == []
        assert result[0]["start"] is None
        assert result[1]["words"]

    def test_paren_only_line_still_inherits_when_others_drop(self):
        # Lines with no normalizable tokens (paren-only display lines)
        # MUST still inherit neighbor timing, even after the new
        # suppression logic. Distinguished from "all-dropped" via the
        # lines_with_tokens set.
        words = [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 5.0, "end": 6.0},
        ]
        lines = ["hello", "(break)", "world"]
        align_lines = ["hello", "", "world"]
        result = match_words_to_lines(words, lines, align_lines)
        assert result[1]["start"] == 1.0
        assert result[1]["end"] == 5.0

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

    def test_word_dict_has_expected_keys(self):
        words = [{"word": "hello", "start": 0.0, "end": 1.0}]
        lines = ["hello"]
        result = match_words_to_lines(words, lines)
        emitted = result[0]["words"][0]
        assert set(emitted) == {"word", "start", "end"}
