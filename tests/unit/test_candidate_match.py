"""Unit tests for the joint matcher's candidate generation + timing helpers."""

from pikaraoke.lib.candidate_match import (
    _build_line_object,
    _edit_distance,
    _longest_contiguous_run,
    best_candidate_per_line,
    find_anchor_candidates,
    find_candidates,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _w(word: str, start: float, end: float | None = None) -> dict:
    """Build a whisper word dict; end defaults to start + 0.1."""
    return {"word": word, "start": start, "end": end if end is not None else start + 0.1}


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


class TestBestCandidatePerLine:
    def test_keeps_highest_score_per_line(self):
        cands = [(0, 2, 0, 1.0), (5, 7, 0, 3.0), (10, 12, 1, 2.0)]
        best = best_candidate_per_line(cands)
        assert best == {0: (5, 7, 3.0), 1: (10, 12, 2.0)}

    def test_ties_break_toward_earliest_start(self):
        cands = [(5, 7, 0, 2.0), (0, 2, 0, 2.0)]
        best = best_candidate_per_line(cands)
        assert best[0] == (0, 2, 2.0)

    def test_empty_input(self):
        assert best_candidate_per_line([]) == {}


class TestFindAnchorCandidates:
    def test_recovers_zero_candidate_line_via_anchor_run(self):
        # Lyric line "alpha bravo charlie delta echo" has a clean 3-word
        # anchor "bravo charlie delta" inside the whisper stream, but is
        # surrounded by garbage too noisy for find_candidates.
        token_norms = _norms("junk", "noise", "bravo", "charlie", "delta", "junk2", "noise2")
        lyric = _norms("alpha", "bravo", "charlie", "delta", "echo")
        cands = find_anchor_candidates(token_norms, [lyric], line_ids=[0])
        assert cands, "anchor fallback should find a candidate on a 3-word run"
        # Score is the raw anchor-run length (matches main-pass scoring).
        assert any(abs(c[3] - 3.0) < 1e-9 for c in cands)

    def test_too_short_line_skipped(self):
        # A 2-word line can never anchor confidently (min_run_floor=3).
        cands = find_anchor_candidates(_norms("a", "b"), [_norms("a", "b")], line_ids=[0])
        assert cands == []


# ---------------------------------------------------------------------------
# _build_line_object — per-word timing within a selected window
# ---------------------------------------------------------------------------


class TestBuildLineObject:
    def test_per_word_timing_from_matched_words(self):
        # Each lyric word inherits the matched whisper word's start/end.
        line_toks = [("hello", "hello"), ("world", "world")]
        win_words = [_w("hello", 1.0, 1.5), _w("world", 1.5, 2.0)]
        obj = _build_line_object("hello world", 3, line_toks, win_words, lookahead=3)
        assert obj["text"] == "hello world"
        assert obj["line_id"] == 3
        assert [w["word"] for w in obj["words"]] == ["hello", "world"]
        assert obj["words"][0]["start"] == 1.0
        assert obj["words"][1]["end"] == 2.0
        assert obj["start"] == 1.0
        assert obj["end"] == 2.0

    def test_unmatched_token_interpolated_between_neighbors(self):
        # Whisper dropped "b"; it should be interpolated between the
        # surrounding matched anchors rather than dropped from the line.
        line_toks = [("a", "a"), ("b", "b"), ("c", "c")]
        win_words = [_w("a", 0.0, 1.0), _w("c", 3.0, 4.0)]
        obj = _build_line_object("a b c", 0, line_toks, win_words, lookahead=3)
        assert [w["word"] for w in obj["words"]] == ["a", "b", "c"]
        # "b" fills the [1.0, 3.0] gap left by its anchors.
        assert obj["words"][1]["start"] == 1.0
        assert obj["words"][1]["end"] == 3.0
