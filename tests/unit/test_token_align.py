"""Unit tests for token primitives: normalization + the lockstep aligner."""

from pikaraoke.lib.token_align import (
    _match_simple,
    _normalize_token,
    _walk_align,
    match_words_to_tokens,
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

    def test_folds_cyrillic_homoglyphs(self):
        # Lyric-site watermark: "wеre" with U+0435 CYRILLIC SMALL LETTER IE.
        assert _normalize_token("wеre") == "were"

    def test_folds_diacritics(self):
        # Whisper transcribes accented words unaccented.
        assert _normalize_token("soufflé") == "souffle"

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
        # Token equivalence is strict — no Levenshtein, no phonetic fallback.
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
# Monotone assignment DP
# ---------------------------------------------------------------------------


class TestMatchWordsToTokens:
    def test_max_matches_beats_deviation(self):
        # Two matches at huge time deviation beat one match at zero
        # deviation — deviation is a tiebreak, never a gate.
        assign = match_words_to_tokens(["a", "b"], [0.0, 1.0], ["a", "b"], [50.0, 51.0])
        assert assign == [0, 1]

    def test_deviation_tiebreak_on_repeated_token(self):
        # One "na" word, two "na" tokens: equal match count either way, so
        # the word goes to the token whose expected time it sits closest to.
        assign = match_words_to_tokens(["na", "na"], [0.0, 10.0], ["na"], [9.8])
        assert assign == [None, 0]

    def test_unmatched_tokens_padded_none(self):
        assign = match_words_to_tokens(["a", "x", "b"], [0.0, 1.0, 2.0], ["a", "b"], [0.0, 2.0])
        assert assign == [0, None, 1]

    def test_extra_words_skipped(self):
        # A word matching no token must not stall the scan.
        assign = match_words_to_tokens(["a", "b"], [0.0, 1.0], ["a", "zzz", "b"], [0.0, 0.5, 1.0])
        assert assign == [0, 2]

    def test_empty_inputs(self):
        assert match_words_to_tokens([], [], ["a"], [0.0]) == []
        assert match_words_to_tokens(["a"], [0.0], [], []) == [None]
