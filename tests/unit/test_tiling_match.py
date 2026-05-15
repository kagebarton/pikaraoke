"""Unit tests for the order-independent tiling matcher."""

from pikaraoke.lib.tiling_match import (
    _edit_distance,
    _longest_contiguous_run,
    _split_paren_units,
    _tokenize_unit,
    best_tiling,
    find_anchor_candidates,
    find_candidates,
    match_words_to_lines_tiling,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _w(word: str, start: float, end: float | None = None) -> dict:
    """Build a whisper word dict; end defaults to start + 0.1."""
    return {"word": word, "start": start, "end": end if end is not None else start + 0.1}


def _stream(*tokens: str, dt: float = 0.5) -> list[dict]:
    """Build a whisper-word stream from a token list at uniform spacing."""
    return [_w(tok, i * dt, i * dt + 0.3) for i, tok in enumerate(tokens)]


def _norms(*toks: str) -> list[str]:
    """Shorthand: already-normalized tokens for unit-test fixtures."""
    return list(toks)


# ---------------------------------------------------------------------------
# Edit distance + longest contiguous run
# ---------------------------------------------------------------------------


class TestEditDistance:
    def test_identical(self):
        assert _edit_distance(["a", "b", "c"], ["a", "b", "c"]) == 0

    def test_one_substitution(self):
        assert _edit_distance(["a", "b", "c"], ["a", "x", "c"]) == 1

    def test_insertion(self):
        assert _edit_distance(["a", "c"], ["a", "b", "c"]) == 1

    def test_empty_sequences(self):
        assert _edit_distance([], ["a"]) == 1
        assert _edit_distance(["a"], []) == 1
        assert _edit_distance([], []) == 0


class TestLongestContiguousRun:
    def test_full_overlap(self):
        assert _longest_contiguous_run(["a", "b", "c"], ["a", "b", "c"]) == 3

    def test_middle_anchor(self):
        # "b c d" appears contiguous inside both.
        assert _longest_contiguous_run(["x", "b", "c", "d", "y"], ["q", "b", "c", "d"]) == 3

    def test_no_overlap(self):
        assert _longest_contiguous_run(["a", "b"], ["c", "d"]) == 0

    def test_one_empty(self):
        assert _longest_contiguous_run([], ["a"]) == 0


# ---------------------------------------------------------------------------
# Paren unit splitting
# ---------------------------------------------------------------------------


class TestSplitParenUnits:
    def test_no_parens(self):
        assert _split_paren_units("just a line") == ["just a line"]

    def test_single_paren(self):
        assert _split_paren_units("main (backing)") == ["main", "backing"]

    def test_multiple_parens(self):
        assert _split_paren_units("a (b) c (d)") == ["a c", "b", "d"]

    def test_only_paren(self):
        # The original line is paren-only — only the paren content survives.
        assert _split_paren_units("(backing only)") == ["backing only"]

    def test_collapses_whitespace_left_by_paren_removal(self):
        # Removing the paren shouldn't leave a double-space hole.
        result = _split_paren_units("main    (back)    tail")
        assert result[0] == "main tail"


# ---------------------------------------------------------------------------
# Tokenize
# ---------------------------------------------------------------------------


class TestTokenizeUnit:
    def test_basic(self):
        assert _tokenize_unit("Hello world") == [("hello", "Hello"), ("world", "world")]

    def test_drops_punctuation_only_tokens(self):
        # "—" alone normalizes to empty.
        assert _tokenize_unit("hello — world") == [
            ("hello", "hello"),
            ("world", "world"),
        ]


# ---------------------------------------------------------------------------
# find_candidates
# ---------------------------------------------------------------------------


class TestFindCandidates:
    def test_exact_window_match(self):
        token_norms = _norms("a", "b", "c", "d")
        lyric_lines = [_norms("b", "c")]
        cands = find_candidates(token_norms, lyric_lines, max_edit_ratio=0.25)
        # At least one candidate whose window covers exactly "b c".
        spans = [(c[0], c[1]) for c in cands if c[2] == 0]
        assert (1, 3) in spans

    def test_no_match_above_threshold(self):
        # All tokens differ from the lyric — no window can pass max_edit_ratio.
        token_norms = _norms("x", "y", "z")
        lyric_lines = [_norms("a", "b", "c")]
        cands = find_candidates(token_norms, lyric_lines, max_edit_ratio=0.25)
        assert cands == []

    def test_min_overlap_floor_rejects_degenerate_fragment(self):
        # A 2-word lyric line vs a single token: a 1-wide window has
        # dist=1, score=0.5, but min_overlap=2 should reject it because
        # n - dist = 1 < 2.
        token_norms = _norms("a")
        lyric_lines = [_norms("a", "b")]
        # max_edit_ratio=0.5 alone would accept (dist=1, max_allowed=1).
        cands = find_candidates(token_norms, lyric_lines, max_edit_ratio=0.5)
        assert cands == []


class TestFindAnchorCandidates:
    def test_recovers_zero_candidate_line_via_anchor_run(self):
        # Lyric line "alpha bravo charlie delta echo" has a clean 3-word
        # anchor "bravo charlie delta" inside the whisper stream, but is
        # surrounded by garbage too noisy for find_candidates.
        token_norms = _norms("junk", "noise", "bravo", "charlie", "delta", "junk2", "noise2")
        lyric = _norms("alpha", "bravo", "charlie", "delta", "echo")
        cands = find_anchor_candidates(token_norms, [lyric], line_ids=[0])
        assert cands, "anchor fallback should find a candidate on a 3-word run"
        # Score should be anchor_run / n = 3/5 = 0.6.
        assert any(abs(c[3] - 0.6) < 1e-9 for c in cands)

    def test_too_short_line_skipped(self):
        # A 2-word line can never anchor confidently (min_run_floor=3).
        cands = find_anchor_candidates(_norms("a", "b"), [_norms("a", "b")], line_ids=[0])
        assert cands == []


# ---------------------------------------------------------------------------
# best_tiling
# ---------------------------------------------------------------------------


class TestBestTiling:
    def test_picks_non_overlapping(self):
        # Three candidates, two overlap; DP should keep the non-overlapping pair.
        # Format: (start, end, line_id, score)
        cands = [
            (0, 3, 0, 1.0),
            (2, 5, 1, 1.0),  # overlaps with both
            (4, 7, 2, 1.0),
        ]
        selected = best_tiling(cands)
        spans = [(c[0], c[1]) for c in selected]
        assert spans == [(0, 3), (4, 7)]

    def test_higher_score_wins_when_overlapping(self):
        cands = [
            (0, 5, 0, 0.5),
            (1, 4, 1, 2.0),  # higher score, but overlaps
        ]
        selected = best_tiling(cands)
        assert selected[0][2] == 1

    def test_empty(self):
        assert best_tiling([]) == []


# ---------------------------------------------------------------------------
# match_words_to_lines_tiling (public)
# ---------------------------------------------------------------------------


class TestMatchWordsToLinesTiling:
    def test_basic_match(self):
        words = _stream("hello", "world")
        lines = ["hello world"]
        result = match_words_to_lines_tiling(words, lines)
        assert len(result) == 1
        assert result[0]["text"] == "hello world"
        assert result[0]["line_id"] == 0
        assert [w["word"] for w in result[0]["words"]] == ["hello", "world"]

    def test_dropped_line_absent_from_output(self):
        # Lyric has 2 lines; whisper only sang the second.
        words = _stream("alpha", "bravo", "charlie")
        lines = ["one two three four", "alpha bravo charlie"]
        result = match_words_to_lines_tiling(words, lines)
        line_ids = [o["line_id"] for o in result]
        assert 0 not in line_ids  # first line dropped
        assert 1 in line_ids

    def test_repeated_chorus_emits_multiple_objects(self):
        # Chorus sung twice; one chorus line in the lyric.
        words = _stream(
            "verse",
            "lines",
            "here",
            "chorus",
            "here",
            "now",
            "more",
            "verse",
            "chorus",
            "here",
            "now",
        )
        lines = ["verse lines here", "chorus here now", "more verse"]
        result = match_words_to_lines_tiling(words, lines)
        chorus_objs = [o for o in result if o["line_id"] == 1]
        assert len(chorus_objs) == 2

    def test_paren_split_yields_two_objects(self):
        # "main (back)" → 2 units. Whisper transcribes both, separated.
        words = _stream(
            "main",
            "phrase",
            "here",
            "other",
            "stuff",
            "back",
            "vocal",
            "phrase",
        )
        lines = ["main phrase here (back vocal phrase)"]
        result = match_words_to_lines_tiling(words, lines)
        # Both units should land separately, both with line_id=0.
        assert len(result) == 2
        assert all(o["line_id"] == 0 for o in result)
        texts = {o["text"] for o in result}
        assert "main phrase here" in texts
        assert "back vocal phrase" in texts

    def test_per_word_timing_in_window(self):
        # Each lyric word should get the matched whisper word's start/end.
        words = [
            _w("hello", 1.0, 1.5),
            _w("world", 1.5, 2.0),
        ]
        lines = ["hello world"]
        result = match_words_to_lines_tiling(words, lines)
        assert result[0]["words"][0]["start"] == 1.0
        assert result[0]["words"][1]["end"] == 2.0

    def test_empty_words_returns_empty(self):
        assert match_words_to_lines_tiling([], ["hello world"]) == []

    def test_results_sorted_by_start_time(self):
        # Lines appear in the lyric in reverse order vs the audio.
        words = _stream("second", "line", "here", "first", "line", "here")
        lines = ["first line here", "second line here"]
        result = match_words_to_lines_tiling(words, lines)
        starts = [o["start"] for o in result]
        assert starts == sorted(starts)
