"""Unit tests for the joint alignment DP matcher."""

from pikaraoke.lib.joint_match import (
    _align_line_object,
    _alpha_weight,
    _best_tiling_by_time,
    _build_align_candidates,
    _build_ytasr_candidates,
    _line_align_ranges,
    _range_agreement,
    _tokenise_lines,
    _transcribe_match_and_count_in_window,
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.token_align import _normalize_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aw(word: str, start: float, end: float | None = None) -> dict:
    """Build an align/transcribe word dict."""
    return {"word": word, "start": start, "end": end if end is not None else start + 0.5}


def _aw_seq(*tokens: str, t0: float = 0.0, dt: float = 1.0, word_dur: float = 0.5) -> list[dict]:
    """Build a uniform-spacing align/transcribe word stream."""
    return [_aw(tok, t0 + i * dt, t0 + i * dt + word_dur) for i, tok in enumerate(tokens)]


def _ytw_seq(*tokens: str, t0: float = 0.0, dt: float = 1.0, word_dur: float = 0.5) -> list[dict]:
    """Build a uniform-spacing ytasr word stream (adds the ``norm`` key
    ``ytasr.parse_json3`` emits, on top of ``_aw_seq``'s word/start/end shape)."""
    return [
        {**w, "norm": _normalize_token(w["word"])}
        for w in _aw_seq(*tokens, t0=t0, dt=dt, word_dur=word_dur)
    ]


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
        assert ranges[0] == {"t0": 0.0, "t1": 1.5, "word_idx": [0, 1]}
        assert ranges[1] == {"t0": 2.0, "t1": 3.5, "word_idx": [2, 3]}

    def test_empty_line(self):
        line_tokens = _tokenise_lines(["one", "", "two"])
        align_words = _aw_seq("one", "two")
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0]["t0"] == 0.0
        assert ranges[1] is None
        assert ranges[2]["t0"] == 1.0

    def test_dropped_word_leaves_neighbours_exact(self):
        # The aligner dropped "four". The old cursor walk shifted every
        # later line's slice; the text-verified assignment keeps lines 0
        # and 2 exact and gives line 1 its surviving word.
        line_tokens = _tokenise_lines(["one two", "three four", "five six"])
        align_words = _aw_seq("one", "two", "three", "five", "six", t0=0.0, dt=1.0)
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0] == {"t0": 0.0, "t1": 1.5, "word_idx": [0, 1]}
        assert ranges[1] == {"t0": 2.0, "t1": 2.5, "word_idx": [2, None]}
        assert ranges[2] == {"t0": 3.0, "t1": 4.5, "word_idx": [3, 4]}

    def test_whole_line_dropped_maps_to_none(self):
        # Zero matched words — honest abstention: no align belief, no range.
        line_tokens = _tokenise_lines(["one two", "three four", "five six"])
        align_words = _aw_seq("one", "two", "five", "six", t0=0.0, dt=1.0)
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0] == {"t0": 0.0, "t1": 1.5, "word_idx": [0, 1]}
        assert ranges[1] is None
        assert ranges[2] == {"t0": 2.0, "t1": 3.5, "word_idx": [2, 3]}

    def test_empty_norm_word_skipped(self):
        # The aligner emitted a word for the "&" the tokeniser dropped; it
        # can never equal a token norm, so nothing shifts.
        line_tokens = _tokenise_lines(["one two", "three & four"])
        align_words = [
            _aw("one", 0.0),
            _aw("two", 1.0),
            _aw("three", 2.0),
            _aw("&", 2.5),
            _aw("four", 3.0),
        ]
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0] == {"t0": 0.0, "t1": 1.5, "word_idx": [0, 1]}
        assert ranges[1] == {"t0": 2.0, "t1": 3.5, "word_idx": [2, 4]}

    def test_twin_lines_anchor_arbitration(self):
        # Two identical "na na boom" lines; the first line's second "na"
        # was dropped. The boom anchors pin each line to its own occurrence
        # — line 1 must not steal line 2's words across the anchor.
        line_tokens = _tokenise_lines(["na na boom", "na na boom"])
        align_words = _aw_seq("na", "boom", t0=0.0, dt=1.0) + _aw_seq(
            "na", "na", "boom", t0=10.0, dt=1.0
        )
        ranges = _line_align_ranges(line_tokens, align_words)
        assert ranges[0] == {"t0": 0.0, "t1": 1.5, "word_idx": [0, None, 1]}
        assert ranges[1] == {"t0": 10.0, "t1": 12.5, "word_idx": [2, 3, 4]}


class TestAlignLineObject:
    def test_clean_mapping_takes_word_timings_verbatim(self):
        toks = _tokenise_lines(["one two three"])[0]
        align_words = _aw_seq("one", "two", "three", t0=0.0, dt=1.0)
        align_range = {"t0": 0.0, "t1": 2.5, "word_idx": [0, 1, 2]}
        obj = _align_line_object(0, "one two three", toks, align_words, align_range)
        assert obj["words"] == [
            {"word": "one", "start": 0.0, "end": 0.5},
            {"word": "two", "start": 1.0, "end": 1.5},
            {"word": "three", "start": 2.0, "end": 2.5},
        ]
        assert obj["start"] == 0.0
        assert obj["end"] == 2.5

    def test_dropped_word_interpolated_inside_own_range(self):
        # "two" was dropped; it must be paced between "one" and "three"
        # rather than borrowing a neighbouring line's word.
        toks = _tokenise_lines(["one two three"])[0]
        align_words = _aw_seq("one", "three", t0=0.0, dt=2.0)
        align_range = {"t0": 0.0, "t1": 2.5, "word_idx": [0, None, 1]}
        obj = _align_line_object(0, "one two three", toks, align_words, align_range)
        assert obj["words"][0] == {"word": "one", "start": 0.0, "end": 0.5}
        assert obj["words"][2] == {"word": "three", "start": 2.0, "end": 2.5}
        assert obj["words"][1] == {"word": "two", "start": 0.5, "end": 2.0}

    def test_none_range_yields_wordless_line(self):
        toks = _tokenise_lines(["one two"])[0]
        obj = _align_line_object(0, "one two", toks, [], None)
        assert obj["words"] == []
        assert obj["start"] is None
        assert obj["end"] is None


# ---------------------------------------------------------------------------
# range_agreement
# ---------------------------------------------------------------------------


class TestRangeAgreement:
    def test_exact_overlap(self):
        assert _range_agreement(2.0, 4.0, {"t0": 2.0, "t1": 4.0}) == 1.0

    def test_no_overlap(self):
        assert _range_agreement(10.0, 12.0, {"t0": 2.0, "t1": 4.0}) == 0.0

    def test_partial_overlap(self):
        # 50% overlap with a 2-second align window.
        assert _range_agreement(3.0, 5.0, {"t0": 2.0, "t1": 4.0}) == 0.5

    def test_window_subsumes_align(self):
        # candidate window wider than align — full credit (capped at 1.0).
        assert _range_agreement(0.0, 10.0, {"t0": 2.0, "t1": 4.0}) == 1.0

    def test_collapsed_align(self):
        # zero-width align — candidate that brackets the instant gets full credit.
        assert _range_agreement(1.0, 3.0, {"t0": 2.0, "t1": 2.0}) == 1.0
        assert _range_agreement(5.0, 6.0, {"t0": 2.0, "t1": 2.0}) == 0.0

    def test_none_range(self):
        assert _range_agreement(1.0, 2.0, None) == 0.0


# ---------------------------------------------------------------------------
# transcribe_match scoring
# ---------------------------------------------------------------------------


class TestTranscribeMatchInWindow:
    def test_perfect_match(self):
        tnorms = ["no", "worries", "for", "the", "rest"]
        tstarts = [10.0, 11.0, 12.0, 13.0, 14.0]
        n, _, _ = _transcribe_match_and_count_in_window(
            ["no", "worries", "for"], tnorms, tstarts, 10.0, 13.0, margin_s=0.5, max_edit_ratio=0.25
        )
        assert n == 3

    def test_no_overlap(self):
        tnorms = ["other", "stuff"]
        tstarts = [10.0, 11.0]
        # window way outside transcribe range
        n, _, _ = _transcribe_match_and_count_in_window(
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
        n, _, _ = _transcribe_match_and_count_in_window(
            ["a", "b"], [], [], 0.0, 1.0, margin_s=0.3, max_edit_ratio=0.25
        )
        assert n == 0


class TestTranscribeMatchAndCountInWindow:
    """The 3-tuple form drives the alpha-weight gate via ``any_overlap``."""

    def test_any_overlap_on_partial_lexical_hit(self):
        # Lyric: "spinnin now for time"; transcribe heard "spinning out the time".
        # find_candidates rejects this (edit ratio > 0.25 over 4 tokens) so
        # matched_score == 0, but "time" overlaps lexically — gate must not fire.
        line_norms = ["spinnin", "now", "for", "time"]
        tnorms = ["spinning", "out", "the", "time"]
        tstarts = [10.0, 10.5, 11.0, 11.5]
        matched, any_overlap, count = _transcribe_match_and_count_in_window(
            line_norms, tnorms, tstarts, 10.0, 12.0, margin_s=0.3, max_edit_ratio=0.25
        )
        assert matched == 0
        assert any_overlap is True
        assert count == 4

    def test_no_overlap_unrelated_speech(self):
        # Hakuna-shape: lyric is sung lyrics but window has dialogue.
        line_norms = ["no", "worries", "for", "the", "rest"]
        tnorms = ["hello", "what", "are", "you", "doing"]
        tstarts = [10.0, 10.5, 11.0, 11.5, 12.0]
        matched, any_overlap, count = _transcribe_match_and_count_in_window(
            line_norms, tnorms, tstarts, 10.0, 12.5, margin_s=0.3, max_edit_ratio=0.25
        )
        assert matched == 0
        assert any_overlap is False
        assert count == 5

    def test_empty_window_returns_false_overlap(self):
        matched, any_overlap, count = _transcribe_match_and_count_in_window(
            ["a", "b"], [], [], 0.0, 1.0, margin_s=0.3, max_edit_ratio=0.25
        )
        assert matched == 0
        assert any_overlap is False
        assert count == 0


class TestAlphaWeightGate:
    def test_unrelated_speech_zeros_bonus(self):
        # Hakuna case: substantial transcribe speech, zero lyric overlap.
        assert _alpha_weight(any_overlap=False, count=5) == 0.0

    def test_partial_overlap_keeps_bonus(self):
        # Bloodstream case: mistranscribed lyric with at least one token match.
        assert _alpha_weight(any_overlap=True, count=5) == 1.0

    def test_silent_window_keeps_bonus(self):
        # count below gate threshold — instrumental / silent region.
        assert _alpha_weight(any_overlap=False, count=1) == 1.0
        assert _alpha_weight(any_overlap=False, count=0) == 1.0


# ---------------------------------------------------------------------------
# Align candidate construction
# ---------------------------------------------------------------------------


class TestBuildAlignCandidates:
    def test_one_per_line_with_range(self):
        line_norms = [["a", "b"], ["c", "d"]]
        align_ranges = [
            {"t0": 0.0, "t1": 1.0, "word_idx": [0, 1]},
            {"t0": 2.0, "t1": 3.0, "word_idx": [2, 3]},
        ]
        transcribe_words = _aw_seq("a", "b", "c", "d", t0=0.0, dt=1.0)
        transcribe_norms = ["a", "b", "c", "d"]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            [None, None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert len(cands) == 2
        assert {c["source"] for c in cands} == {"align"}
        # transcribe corroborates both lines → t_match should be 2 → score 2 + 4 = 6
        assert all(c["transcribe_match"] == 2 for c in cands)
        assert all(c["score"] == 6.0 for c in cands)

    def test_narrow_align_is_padded(self):
        # A single short word timed to a sub-min-width but plausible-pace
        # window survives the pace check and is padded up to the min width.
        line_norms = [["oh"]]
        align_ranges = [{"t0": 4.96, "t1": 5.04, "word_idx": [0]}]  # 0.08s, 1 tok
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            [],
            [],
            [None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert len(cands) == 1
        c = cands[0]
        assert c["t1"] - c["t0"] >= 0.099  # padded to min width ≈ 0.1s
        assert abs((c["t0"] + c["t1"]) / 2 - 5.0) < 1e-6  # centred on 5.0

    def test_crammed_stack_dropped(self):
        # A give-up stack: three lines' tokens pinned to near-zero-width
        # windows at 17+ tokens/s. None is a placeable belief, so all are
        # dropped and the lines fall through to transcribe/ytasr or interp.
        line_norms = [["a", "b"], ["c", "d", "e"], ["f", "g"]]
        align_ranges = [
            {"t0": 5.0, "t1": 5.0, "word_idx": [0, 1]},  # 0.0 / 2 tok
            {"t0": 5.0, "t1": 5.02, "word_idx": [2, 3, 4]},  # 0.007 s/tok
            {"t0": 5.02, "t1": 5.05, "word_idx": [5, 6]},  # 0.015 s/tok
        ]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            [],
            [],
            [None, None, None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert cands == []

    def test_genuine_short_line_kept(self):
        # A real one-token line sung over 0.3 s is well above the pace floor.
        line_norms = [["oh"]]
        align_ranges = [{"t0": 10.0, "t1": 10.3, "word_idx": [0]}]  # 0.3 s/tok
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            [],
            [],
            [None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert len(cands) == 1
        assert cands[0]["line_id"] == 0

    def test_no_align_range_skipped(self):
        line_norms = [["a", "b"], ["c", "d"]]
        align_ranges = [None, {"t0": 1.0, "t1": 2.0, "word_idx": [0, 1]}]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            [],
            [],
            [None, None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert len(cands) == 1
        assert cands[0]["line_id"] == 1

    def test_mistranscribed_lyric_keeps_alpha_bonus(self):
        # Bloodstream-shape: align placed the line correctly, but whisper
        # mistranscribed enough words that find_candidates rejects the slice.
        # At least one lyric token still appears in the window, so the gate
        # must NOT fire — align preserves its α bonus.
        line_norms = [["spinnin", "now", "for", "time"]]
        align_ranges = [{"t0": 10.0, "t1": 12.0, "word_idx": [0, 1, 2, 3]}]
        transcribe_words = _aw_seq("spinning", "out", "the", "time", t0=10.0, dt=0.5)
        transcribe_norms = ["spinning", "out", "the", "time"]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            [None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert len(cands) == 1
        c = cands[0]
        assert c["transcribe_match"] == 0  # find_candidates still rejects
        assert c["alpha_weight"] == 1.0  # gate did NOT fire — partial overlap saved it
        assert c["score"] == 4.0  # 0 + 4.0 * 1.0 * 1.0

    def test_unrelated_speech_zeros_alpha_bonus(self):
        # Hakuna-shape: align placed the line into a dialogue region whose
        # transcribe content has no lyric-token overlap at all. Gate fires.
        line_norms = [["no", "worries", "for", "the", "rest"]]
        align_ranges = [{"t0": 10.0, "t1": 13.0, "word_idx": [0, 1, 2, 3, 4]}]
        transcribe_words = _aw_seq("hello", "what", "are", "you", "doing", t0=10.0, dt=0.5)
        transcribe_norms = ["hello", "what", "are", "you", "doing"]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            [None],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=0.0,
        )
        assert len(cands) == 1
        c = cands[0]
        assert c["transcribe_match"] == 0
        assert c["alpha_weight"] == 0.0
        assert c["score"] == 0.0

    def test_dissent_rescued_by_ytasr_endorsement(self):
        # Same dissenting-transcribe window, but ytasr independently maps
        # the line onto align's exact range: 2-of-3 keeps the full bonus.
        line_norms = [["no", "worries", "for", "the", "rest"]]
        align_ranges = [{"t0": 10.0, "t1": 13.0, "word_idx": [0, 1, 2, 3, 4]}]
        transcribe_words = _aw_seq("hello", "what", "are", "you", "doing", t0=10.0, dt=0.5)
        transcribe_norms = ["hello", "what", "are", "you", "doing"]
        cands = _build_align_candidates(
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            [{"t0": 10.0, "t1": 13.0}],
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=4.0,
            beta=2.0,
        )
        c = cands[0]
        assert c["transcribe_match"] == 0
        assert c["alpha_weight"] == 1.0
        assert c["score"] == 0.0 + 1.0 * (4.0 * 1.0 + 2.0 * 1.0)


class TestBuildYtasrCandidates:
    def test_scored_like_align_plus_own_agreement_term(self):
        # ytasr proposes one hit for line 0, coinciding exactly with align's
        # window; transcribe corroborates it too.
        ytasr_words = _ytw_seq("a", "b", t0=10.0, dt=0.5)
        line_norms = [["a", "b"]]
        align_ranges = [{"t0": 10.0, "t1": 11.0}]
        transcribe_words = _aw_seq("a", "b", t0=10.0, dt=0.5)
        transcribe_norms = ["a", "b"]
        tiling_cands = [(0, 2, 0, 2.0)]  # (start_idx, end_idx, line_id, y_score)
        cands = _build_ytasr_candidates(
            tiling_cands,
            ytasr_words,
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=2.0,
            beta=3.0,
        )
        assert len(cands) == 1
        c = cands[0]
        assert c["source"] == "ytasr"
        assert c["ytasr_agreement"] == 1.0
        assert c["align_agreement"] == 1.0  # windows coincide exactly
        assert c["transcribe_match"] == 2  # transcribe corroborates both tokens
        assert c["alpha_weight"] == 1.0
        assert c["score"] == 2.0 + 1.0 * (2.0 * 1.0 + 3.0 * 1.0)  # 7.0

    def test_no_align_range_zeros_align_agreement_only(self):
        ytasr_words = _ytw_seq("a", "b", t0=10.0, dt=0.5)
        line_norms = [["a", "b"]]
        align_ranges = [None]
        transcribe_words = _aw_seq("a", "b", t0=10.0, dt=0.5)
        transcribe_norms = ["a", "b"]
        tiling_cands = [(0, 2, 0, 2.0)]
        cands = _build_ytasr_candidates(
            tiling_cands,
            ytasr_words,
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=2.0,
            beta=3.0,
        )
        c = cands[0]
        assert c["align_agreement"] == 0.0
        assert c["ytasr_agreement"] == 1.0  # own term unaffected
        assert c["score"] == 2.0 + 1.0 * (2.0 * 0.0 + 3.0 * 1.0)  # 5.0

    def test_partial_hit_grades_self_evidence(self):
        # A 2-of-3 token hit carries ytasr_agreement 2/3, not a flat 1.0 —
        # a fragment must not collect the same beta bonus as an exact match.
        ytasr_words = _ytw_seq("a", "b", t0=10.0, dt=0.5)
        line_norms = [["a", "b", "c"]]
        align_ranges = [None]
        transcribe_words = _aw_seq("a", "b", t0=10.0, dt=0.5)
        transcribe_norms = ["a", "b"]
        tiling_cands = [(0, 2, 0, 2.0)]
        cands = _build_ytasr_candidates(
            tiling_cands,
            ytasr_words,
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=2.0,
            beta=3.0,
        )
        c = cands[0]
        assert c["ytasr_agreement"] == 2 / 3
        assert c["transcribe_match"] == 2
        assert c["score"] == 2.0 + 1.0 * (2.0 * 0.0 + 3.0 * (2 / 3))

    def test_unrelated_transcribe_zeros_terms_when_unpartnered(self):
        # Transcribe heard substantial unrelated speech in ytasr's proposed
        # window and align places the line elsewhere: the candidate stands
        # alone against the dissent, so the gate fires with no 2-of-3 rescue.
        ytasr_words = _ytw_seq("a", "b", t0=10.0, dt=0.5)
        line_norms = [["a", "b"]]
        align_ranges = [{"t0": 30.0, "t1": 31.0}]
        transcribe_words = _aw_seq("x", "y", t0=10.0, dt=0.5)
        transcribe_norms = ["x", "y"]
        tiling_cands = [(0, 2, 0, 2.0)]
        cands = _build_ytasr_candidates(
            tiling_cands,
            ytasr_words,
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=2.0,
            beta=3.0,
        )
        c = cands[0]
        assert c["transcribe_match"] == 0
        assert c["alpha_weight"] == 0.0
        assert c["score"] == 0.0

    def test_transcribe_dissent_rescued_at_align_pair_strength(self):
        # Transcribe dissents, but align partially endorses ytasr's window:
        # the bonus survives at min(align endorsement, ytasr solidity) —
        # graded, not binary. Here align overlaps a third of its range.
        ytasr_words = _ytw_seq("a", "b", t0=10.0, dt=0.5)
        line_norms = [["a", "b"]]
        align_ranges = [{"t0": 10.5, "t1": 12.0}]  # overlap 0.5 of 1.5
        transcribe_words = _aw_seq("x", "y", t0=10.0, dt=0.5)
        transcribe_norms = ["x", "y"]
        tiling_cands = [(0, 2, 0, 2.0)]
        cands = _build_ytasr_candidates(
            tiling_cands,
            ytasr_words,
            line_norms,
            align_ranges,
            transcribe_words,
            transcribe_norms,
            margin_s=0.3,
            max_edit_ratio=0.25,
            alpha=2.0,
            beta=3.0,
        )
        c = cands[0]
        assert c["transcribe_match"] == 0
        assert c["alpha_weight"] == 1 / 3
        assert c["score"] == 0.0 + (1 / 3) * (2.0 * (1 / 3) + 3.0 * 1.0)


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
        # Intro at 0-3s; the long line that align misplaces; ending line
        # genuinely AFTER the long line's correct location (we now enforce
        # lyric-monotonic order, so line 2 must come after line 1).
        lines = [
            "intro line here",
            "no worries for the rest of your days",
            "ending line here",
        ]
        align_lines = lines
        # Align places line 1 at 3-9s (the dialogue region — wrong),
        # then ending at 9-12s (also wrong — align thought the song was
        # already over).
        align_words = (
            _aw_seq("intro", "line", "here", t0=0.0, dt=1.0)
            + _aw_seq("no", "worries", "for", "the", "rest", "of", "your", "days", t0=3.0, dt=0.75)
            + _aw_seq("ending", "line", "here", t0=9.0, dt=1.0)
        )
        # Transcribe hears the true audio: intro at 0-3s, dialogue at 3-9s,
        # the long line actually sung at 15-19s, ending line at 20-23s.
        transcribe_words = (
            _aw_seq("intro", "line", "here", t0=0.0, dt=1.0)
            + _aw_seq("hello", "what", "are", "you", "doing", "here", t0=3.0, dt=1.0)
            + _aw_seq("no", "worries", "for", "the", "rest", "of", "your", "days", t0=15.0, dt=0.5)
            + _aw_seq("ending", "line", "here", t0=20.0, dt=1.0)
        )

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )

        assert len(objs) == 3
        # Intro: align wins (transcribe corroborates align's placement).
        assert stats["selected_source"][0] == "align"
        # The misplaced long line should go to transcribe — placed near 15s.
        assert stats["selected_source"][1] == "transcribe"
        assert 14.5 <= objs[1]["start"] <= 16.0
        # The ending line should route to transcribe (the real audio at 20s),
        # since align placed it at 9-12s which would violate monotonic order
        # after line 1's 15-19s win.
        assert stats["selected_source"][2] == "transcribe"
        assert objs[2]["start"] >= 19.5


# ---------------------------------------------------------------------------
# End-to-end: ytasr as a 3rd source recovers what align + transcribe miss
# ---------------------------------------------------------------------------


class TestEndToEndYtasrWins:
    """Align misplaces a line into unrelated dialogue and transcribe never
    hears it at all; YTASR correctly captured the line's real audio
    position. The ytasr candidate should win where neither of the other
    two sources can support the line.
    """

    def test_align_and_transcribe_miss_ytasr_recovers(self):
        lines = ["intro line here", "no worries today"]
        align_lines = lines
        # Align: intro correct at 0-3s; the second line placed at the wrong
        # (dialogue) time, 3-6s.
        align_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "no", "worries", "today", t0=3.0, dt=1.0
        )
        # Transcribe hears the intro correctly, then unrelated dialogue in
        # the window align (wrongly) chose for line 1 — and never mentions
        # "no worries today" anywhere, so it produces zero candidates for
        # that line.
        transcribe_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "hello", "there", "friend", t0=3.0, dt=1.0
        )
        # YTASR correctly captured line 1's real audio position, later in
        # the song, where transcribe said nothing at all (silence, not
        # contradiction — the corroboration gate only fires on substantial
        # *unrelated* speech, not on silence).
        ytasr_words = _ytw_seq("no", "worries", "today", t0=15.0, dt=1.0)

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words,
            transcribe_words,
            lines,
            align_lines,
            alpha=4.0,
            beta=4.0,
            ytasr_words=ytasr_words,
        )

        assert len(objs) == 2
        assert stats["selected_source"] == ["align", "ytasr"]
        assert stats["align_won"] == 1
        assert stats["ytasr_won"] == 1
        assert stats["transcribe_won"] == 0
        assert stats["n_ytasr_candidates"] > 0
        # Per-word timings for line 1 come from ytasr's stream (~15s), not
        # align's wrong 3s guess.
        assert objs[1]["start"] >= 14.5

    def test_transcribe_hallucination_survived_by_align_ytasr_pair(self):
        # Transcribe hallucinated unrelated words over line 1's true window
        # while align and ytasr both nominate it. Under the transcribe-only
        # gate every candidate for the line scored 0 and the DP dropped it;
        # the 2-of-3 rescue keeps align's placement (and its refined
        # per-word timings) at full bonus.
        lines = ["intro line here", "no worries today"]
        align_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "no", "worries", "today", t0=15.0, dt=1.0
        )
        transcribe_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "blah", "bleh", "blub", t0=15.0, dt=1.0
        )
        ytasr_words = _ytw_seq("no", "worries", "today", t0=15.0, dt=1.0)

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words,
            transcribe_words,
            lines,
            lines,
            alpha=4.0,
            beta=4.0,
            ytasr_words=ytasr_words,
        )

        assert stats["selected_source"] == ["align", "align"]
        assert objs[1]["start"] >= 14.5

    def test_ytasr_scan_uses_own_stricter_ratio(self):
        # A half-garbled ASR rendering ("a b y z" for "a b c d") clears the
        # transcribe knob (0.75 allows 3 errors on 4 tokens) but not ytasr's
        # own CANDIDATE_MAX_EDIT_RATIO (0.34 allows 1): the ytasr scan must
        # use the latter, so ASR text this weak generates no candidate at
        # all, no matter how loose the transcribe knob is set.
        lines = ["a b c d"]
        align_words = _aw_seq("a", "b", "c", "d", t0=0.0, dt=1.0)
        ytasr_words = _ytw_seq("a", "b", "y", "z", t0=10.0, dt=1.0)

        _, stats = match_words_to_lines_joint_with_stats(
            align_words,
            [],
            lines,
            lines,
            max_edit_ratio=0.75,
            ytasr_words=ytasr_words,
        )
        assert stats["n_ytasr_candidates"] == 0

    def test_ytasr_words_none_is_bit_identical_to_two_source(self):
        # The hard backward-compatibility requirement: omitting ytasr_words
        # must reproduce the plain two-source matcher exactly.
        lines = ["hello world", "good night"]
        align_lines = lines
        align_words = _aw_seq("hello", "world", "good", "night", t0=0.0, dt=1.0)
        transcribe_words = _aw_seq("hello", "world", "good", "night", t0=0.0, dt=1.0)

        objs_default, stats_default = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0
        )
        objs_explicit, stats_explicit = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, align_lines, alpha=4.0, ytasr_words=None
        )

        assert objs_default == objs_explicit
        assert stats_default == stats_explicit
        assert stats_default["ytasr_won"] == 0
        assert stats_default["n_ytasr_candidates"] == 0


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
# End-to-end: aligner word drops (the desync fix)
# ---------------------------------------------------------------------------


class TestEndToEndAlignWordDrops:
    def test_clean_stream_reports_zero_drops(self):
        lines = ["aaa bbb", "ccc ddd"]
        align_words = _aw_seq("aaa", "bbb", "ccc", "ddd", t0=0.0, dt=1.0)
        _, stats = match_words_to_lines_joint_with_stats(align_words, [], lines, lines, alpha=4.0)
        assert stats["n_align_word_drops"] == 0

    def test_mid_stream_drop_keeps_later_line_exact(self):
        # "ddd" dropped from line 2; the old cursor walk would have shifted
        # line 3's timings by one word. Line 3 must stay exact and align-won.
        lines = ["aaa bbb", "ccc ddd", "eee fff"]
        align_words = _aw_seq("aaa", "bbb", "ccc", "eee", "fff", t0=0.0, dt=1.0)
        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, [], lines, lines, alpha=4.0
        )
        assert stats["n_align_word_drops"] == 1
        assert stats["selected_source"] == ["align", "align", "align"]
        assert objs[2]["words"] == [
            {"word": "eee", "start": 3.0, "end": 3.5},
            {"word": "fff", "start": 4.0, "end": 4.5},
        ]
        # The surviving word of line 2 keeps its own timing; "ddd" is
        # interpolated inside line 2's range, never borrowed from line 3.
        assert objs[1]["words"][0] == {"word": "ccc", "start": 2.0, "end": 2.5}
        assert objs[1]["words"][1]["word"] == "ddd"
        assert objs[1]["words"][1]["start"] < objs[2]["words"][0]["start"]

    def test_whole_line_dropped_completes_and_leaves_neighbours_exact(self):
        # All of line 2's words dropped: it gets no align belief, is placed
        # by interpolation, and both neighbours stay exact. drops == 3.
        lines = ["aaa bbb", "ccc ddd eee", "fff ggg"]
        align_words = _aw_seq("aaa", "bbb", t0=0.0, dt=1.0) + _aw_seq("fff", "ggg", t0=10.0, dt=1.0)
        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, [], lines, lines, alpha=4.0
        )
        assert stats["n_align_word_drops"] == 3
        assert len(objs) == 3
        assert stats["selected_source"][0] == "align"
        assert stats["selected_source"][2] == "align"
        assert stats["selected_source"][1] != "align"
        assert objs[0]["words"][0]["start"] == 0.0
        assert objs[2]["words"] == [
            {"word": "fff", "start": 10.0, "end": 10.5},
            {"word": "ggg", "start": 11.0, "end": 11.5},
        ]


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
        # Interp placeholders carry no evidence key — the veto never sees them.
        assert "evidence" not in objs[1]


# ---------------------------------------------------------------------------
# Winning-candidate evidence rides on every materialised object
# ---------------------------------------------------------------------------


class TestEvidenceAttach:
    """Every placed object carries its winning candidate's evidence terms so
    the downstream vocal-energy veto can read corroboration off the object."""

    def test_uncorroborated_align_object_is_zero_evidence(self):
        # Align places the only line; no transcribe, no ytasr overlap. The
        # object is zero-zero — exactly what the veto tests against silence.
        lines = ["hello world"]
        align_words = _aw_seq("hello", "world", t0=0.0, dt=1.0)
        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, [], lines, lines, alpha=4.0
        )
        assert stats["selected_source"] == ["align"]
        assert objs[0]["evidence"] == {"transcribe_match": 0.0, "ytasr_agreement": 0.0}

    def test_align_and_ytasr_objects_carry_their_terms(self):
        # Recovery shape: transcribe corroborates the align-won intro, ytasr
        # wins line 1 on its own agreement.
        lines = ["intro line here", "no worries today"]
        align_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "no", "worries", "today", t0=3.0, dt=1.0
        )
        transcribe_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "hello", "there", "friend", t0=3.0, dt=1.0
        )
        ytasr_words = _ytw_seq("no", "worries", "today", t0=15.0, dt=1.0)

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words,
            transcribe_words,
            lines,
            lines,
            alpha=4.0,
            beta=4.0,
            ytasr_words=ytasr_words,
        )

        assert stats["selected_source"] == ["align", "ytasr"]
        assert objs[0]["evidence"]["transcribe_match"] > 0
        assert objs[1]["evidence"]["ytasr_agreement"] > 0

    def test_transcribe_won_object_carries_positive_transcribe_match(self):
        lines = ["intro line here", "no worries for the rest of your days"]
        align_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "no", "worries", "for", "the", "rest", "of", "your", "days", t0=3.0, dt=0.75
        )
        transcribe_words = _aw_seq("intro", "line", "here", t0=0.0, dt=1.0) + _aw_seq(
            "no", "worries", "for", "the", "rest", "of", "your", "days", t0=15.0, dt=0.5
        )

        objs, stats = match_words_to_lines_joint_with_stats(
            align_words, transcribe_words, lines, lines, alpha=4.0
        )

        assert stats["selected_source"][1] == "transcribe"
        assert objs[1]["evidence"]["transcribe_match"] > 0
