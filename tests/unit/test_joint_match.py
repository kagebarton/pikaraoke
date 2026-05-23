"""Unit tests for the joint alignment DP matcher."""

from pikaraoke.lib.joint_match import (
    _align_agreement_for_window,
    _best_tiling_by_time,
    _build_align_candidates,
    _line_align_ranges,
    _tokenise_lines,
    _transcribe_match_in_window,
    match_words_to_lines_joint_with_stats,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aw(word: str, start: float, end: float | None = None) -> dict:
    """Build an align/transcribe word dict."""
    return {"word": word, "start": start, "end": end if end is not None else start + 0.5}


def _aw_seq(*tokens: str, t0: float = 0.0, dt: float = 1.0, word_dur: float = 0.5) -> list[dict]:
    """Build a uniform-spacing align/transcribe word stream."""
    return [_aw(tok, t0 + i * dt, t0 + i * dt + word_dur) for i, tok in enumerate(tokens)]


# ---------------------------------------------------------------------------
# Tokenisation + align-range mapping
# ---------------------------------------------------------------------------


class TestTokeniseLines:
    def test_basic(self):
        toks = _tokenise_lines(["Hello world", "good night"])
        assert [t[0] for t in toks[0]] == ["hello", "world"]
        assert [t[1] for t in toks[0]] == ["Hello", "world"]
        assert [t[0] for t in toks[1]] == ["good", "night"]

    def test_drops_punctuation_only(self):
        toks = _tokenise_lines(["♪ Hello ♪"])
        # ♪ normalises to empty, dropped
        assert [t[0] for t in toks[0]] == ["hello"]


class TestLineAlignRanges:
    def test_consecutive_lines(self):
        line_tokens = _tokenise_lines(["one two", "three four"])
        align_words = _aw_seq("one", "two", "three", "four", t0=0.0, dt=1.0)
        ranges = _line_align_ranges(line_tokens, align_words)
        # word_dur=0.5, dt=1.0 → "two" at [1.0, 1.5], "four" at [3.0, 3.5]
        assert ranges[0] == {"t0": 0.0, "t1": 1.5, "token_start": 0, "token_end": 2}
        assert ranges[1] == {"t0": 2.0, "t1": 3.5, "token_start": 2, "token_end": 4}

    def test_empty_line(self):
        line_tokens = _tokenise_lines(["one", "", "two"])
        align_words = _aw_seq("one", "two")
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0]["t0"] == 0.0
        assert ranges[1] is None
        assert ranges[2]["t0"] == 1.0

    def test_align_too_short(self):
        # align dropped a token — the affected line gets None.
        line_tokens = _tokenise_lines(["one two", "three four"])
        align_words = _aw_seq("one", "two", "three")  # only 3 words
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0] is not None
        assert ranges[1] is None


# ---------------------------------------------------------------------------
# align_agreement
# ---------------------------------------------------------------------------


class TestAlignAgreement:
    def test_exact_overlap(self):
        assert _align_agreement_for_window(2.0, 4.0, {"t0": 2.0, "t1": 4.0}) == 1.0

    def test_no_overlap(self):
        assert _align_agreement_for_window(10.0, 12.0, {"t0": 2.0, "t1": 4.0}) == 0.0

    def test_partial_overlap(self):
        # 50% overlap with a 2-second align window.
        assert _align_agreement_for_window(3.0, 5.0, {"t0": 2.0, "t1": 4.0}) == 0.5

    def test_window_subsumes_align(self):
        # candidate window wider than align — full credit (capped at 1.0).
        assert _align_agreement_for_window(0.0, 10.0, {"t0": 2.0, "t1": 4.0}) == 1.0

    def test_collapsed_align(self):
        # zero-width align — candidate that brackets the instant gets full credit.
        assert _align_agreement_for_window(1.0, 3.0, {"t0": 2.0, "t1": 2.0}) == 1.0
        assert _align_agreement_for_window(5.0, 6.0, {"t0": 2.0, "t1": 2.0}) == 0.0

    def test_none_range(self):
        assert _align_agreement_for_window(1.0, 2.0, None) == 0.0


# ---------------------------------------------------------------------------
# transcribe_match scoring
# ---------------------------------------------------------------------------


class TestTranscribeMatchInWindow:
    def test_perfect_match(self):
        tnorms = ["no", "worries", "for", "the", "rest"]
        tstarts = [10.0, 11.0, 12.0, 13.0, 14.0]
        n = _transcribe_match_in_window(
            ["no", "worries", "for"], tnorms, tstarts, 10.0, 13.0, margin_s=0.5, max_edit_ratio=0.25
        )
        assert n == 3

    def test_no_overlap(self):
        tnorms = ["other", "stuff"]
        tstarts = [10.0, 11.0]
        # window way outside transcribe range
        n = _transcribe_match_in_window(
            ["no", "worries", "for"],
            tnorms,
            tstarts,
            100.0,
            103.0,
            margin_s=0.3,
            max_edit_ratio=0.25,
        )
        assert n == 0

    def test_empty_window(self):
        n = _transcribe_match_in_window(
            ["a", "b"], [], [], 0.0, 1.0, margin_s=0.3, max_edit_ratio=0.25
        )
        assert n == 0


# ---------------------------------------------------------------------------
# Align candidate construction
# ---------------------------------------------------------------------------


class TestBuildAlignCandidates:
    def test_one_per_line_with_range(self):
        line_norms = [["a", "b"], ["c", "d"]]
        align_ranges = [
            {"t0": 0.0, "t1": 1.0, "token_start": 0, "token_end": 2},
            {"t0": 2.0, "t1": 3.0, "token_start": 2, "token_end": 4},
        ]
        transcribe_words = _aw_seq("a", "b", "c", "d", t0=0.0, dt=1.0)
        transcribe_norms = ["a", "b", "c", "d"]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
        )
        assert len(cands) == 2
        assert {c["source"] for c in cands} == {"align"}
        # transcribe corroborates both lines → t_match should be 2 → score 2 + 4 = 6
        assert all(c["transcribe_match"] == 2 for c in cands)
        assert all(c["score"] == 6.0 for c in cands)

    def test_collapsed_align_is_padded(self):
        # All tokens forced to one timestamp — t1 - t0 ≈ 0.
        line_norms = [["a", "b"]]
        align_ranges = [{"t0": 5.0, "t1": 5.0, "token_start": 0, "token_end": 2}]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            [],
            [],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
        )
        assert len(cands) == 1
        c = cands[0]
        assert c["t1"] - c["t0"] >= 0.099  # min width ≈ 0.1s
        # collapsed centred on 5.0
        assert abs((c["t0"] + c["t1"]) / 2 - 5.0) < 1e-6

    def test_no_align_range_skipped(self):
        line_norms = [["a", "b"], ["c", "d"]]
        align_ranges = [None, {"t0": 1.0, "t1": 2.0, "token_start": 0, "token_end": 2}]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            [],
            [],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
        )
        assert len(cands) == 1
        assert cands[0]["line_id"] == 1


# ---------------------------------------------------------------------------
# DP: best_tiling_by_time
# ---------------------------------------------------------------------------


class TestBestTilingByTime:
    def test_empty(self):
        assert _best_tiling_by_time([]) == []

    def test_non_overlapping_all_kept(self):
        cands = [
            {"line_id": 0, "source": "align", "t0": 0.0, "t1": 2.0, "score": 5.0},
            {"line_id": 1, "source": "align", "t0": 3.0, "t1": 5.0, "score": 5.0},
            {"line_id": 2, "source": "align", "t0": 6.0, "t1": 8.0, "score": 5.0},
        ]
        sel = _best_tiling_by_time(cands)
        assert [c["line_id"] for c in sel] == [0, 1, 2]

    def test_overlap_picks_highest_score(self):
        cands = [
            {"line_id": 0, "source": "align", "t0": 0.0, "t1": 5.0, "score": 3.0},
            {"line_id": 1, "source": "transcribe", "t0": 1.0, "t1": 4.0, "score": 7.0},
        ]
        sel = _best_tiling_by_time(cands)
        assert len(sel) == 1
        assert sel[0]["line_id"] == 1

    def test_touching_intervals_both_kept(self):
        # end == next start — non-overlapping.
        cands = [
            {"line_id": 0, "source": "align", "t0": 0.0, "t1": 2.0, "score": 3.0},
            {"line_id": 1, "source": "align", "t0": 2.0, "t1": 4.0, "score": 3.0},
        ]
        sel = _best_tiling_by_time(cands)
        assert len(sel) == 2


# ---------------------------------------------------------------------------
# End-to-end happy paths
# ---------------------------------------------------------------------------


class TestEndToEndCleanSong:
    """A song where align and transcribe agree on every line — joint matcher
    should produce per-line timings sourced from align (the precise one)."""

    def test_clean_song_align_wins(self):
        lines = ["hello world", "good night"]
        align_lines = lines
        align_words = _aw_seq("hello", "world", "good", "night", t0=0.0, dt=1.0)
        transcribe_words = _aw_seq("hello", "world", "good", "night", t0=0.0, dt=1.0)

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )

        assert len(objs) == 2
        assert stats["selected_source"] == ["align", "align"]
        assert stats["align_won"] == 2
        assert stats["transcribe_won"] == 0
        # Per-word timings come from align (precise — equal to align_words timing).
        assert objs[0]["words"][0]["start"] == 0.0
        assert objs[0]["words"][0]["end"] == 0.5
        assert objs[1]["words"][1]["start"] == 3.0


# ---------------------------------------------------------------------------
# End-to-end: Hakuna-shape (align misplaced, transcribe correct)
# ---------------------------------------------------------------------------


class TestEndToEndHakunaShape:
    """Align places a long line at the wrong audio (dialogue); transcribe
    correctly heard the line at its actual sung time. The transcribe
    candidate should win for that line, while clean neighbours stay on align.
    """

    def test_misplaced_long_line_routes_to_transcribe(self):
        # Two clean lines + one misplaced line ("the long one").
        lines = [
            "intro line here",
            "no worries for the rest of your days",
            "ending line here",
        ]
        align_lines = lines
        # Align places:
        #   intro at 0-3s, the long misplaced line at 3-9s (where dialogue is),
        #   ending at 9-12s (correctly).
        align_words = (
            _aw_seq("intro", "line", "here", t0=0.0, dt=1.0)
            + _aw_seq("no", "worries", "for", "the", "rest", "of", "your", "days", t0=3.0, dt=0.75)
            + _aw_seq("ending", "line", "here", t0=9.0, dt=1.0)
        )
        # Transcribe hears:
        #   intro line here at 0-3s (clean),
        #   dialogue garbage at 3-9s (no match for the long line),
        #   the long line actually sung at 15-19s,
        #   ending line at 9-12s.
        transcribe_words = (
            _aw_seq("intro", "line", "here", t0=0.0, dt=1.0)
            + _aw_seq("hello", "what", "are", "you", "doing", "here", t0=3.0, dt=1.0)
            + _aw_seq("ending", "line", "here", t0=9.0, dt=1.0)
            + _aw_seq("no", "worries", "for", "the", "rest", "of", "your", "days", t0=15.0, dt=0.5)
        )

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )

        assert len(objs) == 3
        # Intro + ending: align wins (transcribe corroborates align's placement).
        assert stats["selected_source"][0] == "align"
        assert stats["selected_source"][2] == "align"
        # The misplaced line should go to transcribe — placed at ~15s, not 3s.
        assert stats["selected_source"][1] == "transcribe"
        assert objs[1]["start"] >= 14.5  # near the transcribe location, not 3.0
        assert objs[1]["start"] <= 16.0


# ---------------------------------------------------------------------------
# End-to-end: chorus repetition
# ---------------------------------------------------------------------------


class TestEndToEndChorus:
    """Three identical chorus lines, each appearing 3x in audio; the align
    prior should pull each lyric line_id to its respective occurrence.
    """

    def test_chorus_repeats_aligned_in_order(self):
        # Lyric file lists the chorus three times.
        lines = ["hakuna matata", "hakuna matata", "hakuna matata"]
        align_lines = lines
        # Align places each at distinct times (it knows the order).
        align_words = (
            _aw_seq("hakuna", "matata", t0=0.0, dt=1.0)
            + _aw_seq("hakuna", "matata", t0=10.0, dt=1.0)
            + _aw_seq("hakuna", "matata", t0=20.0, dt=1.0)
        )
        # Transcribe also heard all three.
        transcribe_words = (
            _aw_seq("hakuna", "matata", t0=0.0, dt=1.0)
            + _aw_seq("hakuna", "matata", t0=10.0, dt=1.0)
            + _aw_seq("hakuna", "matata", t0=20.0, dt=1.0)
        )

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )

        assert len(objs) == 3
        # Each line_id placed at its respective chorus instance, in order.
        assert objs[0]["start"] < 1.0
        assert 9.0 <= objs[1]["start"] <= 11.0
        assert 19.0 <= objs[2]["start"] <= 21.0


# ---------------------------------------------------------------------------
# End-to-end: align-only (transcribe missed everything)
# ---------------------------------------------------------------------------


class TestEndToEndAlignOnly:
    def test_no_transcribe_candidates_align_wins(self):
        lines = ["foo bar"]
        align_lines = lines
        align_words = _aw_seq("foo", "bar", t0=0.0, dt=1.0)
        # Transcribe heard something totally different — no fuzzy match.
        transcribe_words = _aw_seq("zzz", "qqq", t0=0.0, dt=1.0)

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )

        assert len(objs) == 1
        assert stats["selected_source"] == ["align"]
        # Per-word timings still from align.
        assert objs[0]["words"][0]["start"] == 0.0


# ---------------------------------------------------------------------------
# End-to-end: empty transcribe
# ---------------------------------------------------------------------------


class TestEndToEndNoTranscribe:
    def test_empty_transcribe_words(self):
        lines = ["foo bar"]
        align_lines = lines
        align_words = _aw_seq("foo", "bar", t0=0.0, dt=1.0)
        transcribe_words: list[dict] = []
        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )
        assert len(objs) == 1
        assert stats["selected_source"] == ["align"]
        # transcribe_match is 0 but align still placed it.
        assert stats["align_won"] == 1


# ---------------------------------------------------------------------------
# Interpolation of missing lines
# ---------------------------------------------------------------------------


class TestInterpolation:
    def test_middle_line_with_no_tokens_interpolated(self):
        # Three lines; the middle line has zero normalisable tokens (just
        # symbols), so it gets no align range AND no transcribe match —
        # interpolated between its bracketing placed neighbours.
        lines = ["first line", "♪ ♪", "last line"]
        align_lines = lines
        align_words = _aw_seq("first", "line", t0=0.0, dt=1.0) + _aw_seq(
            "last", "line", t0=10.0, dt=1.0
        )
        transcribe_words = _aw_seq("first", "line", t0=0.0, dt=1.0) + _aw_seq(
            "last", "line", t0=10.0, dt=1.0
        )

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )

        assert len(objs) == 3
        assert stats["selected_source"][1] == "interp"
        # Interpolated line lives between line 0's end and line 2's start.
        assert objs[1]["start"] >= objs[0]["end"]
        assert objs[1]["end"] <= objs[2]["start"]
