"""Unit tests for the cue-anchored windowed alignment core (pure logic)."""

import pytest

from pikaraoke.lib.cue_align import (
    SOURCE,
    SOURCE_FILL,
    SOURCE_REALIGN,
    Section,
    align_song,
    densify_cue_spans,
    fit_offset,
    merge_cue_spans,
    repace_bad_lines,
    segment_by_gaps,
    split_section_to_lines,
    warp_scaffold_cues,
)


def _words(*spans: tuple[str, float, float]) -> list[dict]:
    return [{"word": w, "start": s, "end": e} for w, s, e in spans]


def _line(lid: int, text: str, *spans: tuple[str, float, float]) -> dict:
    words = _words(*spans)
    return {
        "line_id": lid,
        "text": text,
        "words": words,
        "start": words[0]["start"] if words else None,
        "end": words[-1]["end"] if words else None,
        "source": SOURCE,
    }


def _anchor_lines(n: int = 4, offset: float = 0.0) -> tuple[list[dict], list, list[str]]:
    """n cleanly-aligned two-word lines at cues (2i, 2i+1), aligned ``offset`` late."""
    objs, cues, lines = [], [], []
    for i in range(n):
        c0 = 2.0 * i
        cues.append((c0, c0 + 1.0))
        lines.append("a a")
        objs.append(
            _line(
                i,
                "a a",
                ("a", c0 + offset, c0 + offset + 0.3),
                ("a", c0 + offset + 0.4, c0 + offset + 0.8),
            )
        )
    return objs, cues, lines


class TestSegmentByGaps:
    def test_empty(self):
        assert segment_by_gaps([]) == []

    def test_single_section_when_no_wide_gap(self):
        # Three back-to-back lines (gaps < SECTION_GAP_S) stay one section.
        cues = [(0.0, 2.0), (2.3, 4.0), (4.2, 6.0)]
        sections = segment_by_gaps(cues, duration=7.0)
        assert sections == [Section(0, 2, 0.0, 6.75)]

    def test_splits_at_wide_gap(self):
        # A 5 s instrumental gap between line 1 and line 2 cuts a boundary.
        cues = [(0.0, 2.0), (2.5, 4.0), (9.0, 11.0), (11.4, 13.0)]
        sections = segment_by_gaps(cues, gap_s=1.5, pad_s=0.75, duration=14.0)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 1), (2, 3)]

    def test_pad_clamped_to_gap_midpoint(self):
        # 5 s gap (4.0 -> 9.0): each side pads only the 0.75 cap, not the half.
        cues = [(0.0, 2.0), (2.5, 4.0), (9.0, 11.0), (11.4, 13.0)]
        first, second = segment_by_gaps(cues, gap_s=1.5, pad_s=0.75, duration=14.0)
        assert first.t1 == 4.75
        assert second.t0 == 8.25
        # Adjacent sections never claim the same audio.
        assert first.t1 < second.t0

    def test_narrow_gap_pads_to_midpoint_only(self):
        # A 1 s gap (within a section) is not a boundary, but if it *were* the
        # split edge the pad would clamp to the 0.5 s midpoint. Here force the
        # split with a tiny gap_s to exercise the clamp.
        cues = [(0.0, 2.0), (3.0, 5.0)]
        first, second = segment_by_gaps(cues, gap_s=0.5, pad_s=0.75, duration=6.0)
        assert first.t1 == 2.5  # 2.0 + min(0.75, 1.0/2)
        assert second.t0 == 2.5  # 3.0 - 0.5

    def test_song_edges_use_full_pad_and_duration_clamp(self):
        cues = [(0.3, 2.0), (2.4, 4.0)]
        (only,) = segment_by_gaps(cues, pad_s=0.75, duration=4.5)
        assert only.t0 == 0.0  # max(0, 0.3 - 0.75)
        assert only.t1 == 4.5  # min(4.5, 4.0 + 0.75)

    def test_zero_gap_90s_splits_at_widest_internal_gap(self):
        # No gap reaches gap_s (1.5s default), so this is one section by the
        # phrase-gap rule alone -- but its 90s raw span forces one cap split,
        # at the wider of the two candidate gaps (1.0s beats 0.5s).
        cues = [(0.0, 40.0), (40.5, 41.0), (42.0, 90.0)]
        sections = segment_by_gaps(cues, duration=90.75)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 1), (2, 2)]
        for lo, hi in ((0, 1), (2, 2)):
            assert cues[hi][1] - cues[lo][0] <= 60.0

    def test_recursive_split_respects_cap(self):
        # One 151.8s zero-gap run needs two cuts: the first (at the wider,
        # 1.0s gap) still leaves a 100.8s half, which needs a second cut.
        cues = [(0.0, 50.0), (50.8, 100.8), (101.8, 151.8)]
        sections = segment_by_gaps(cues, duration=152.5)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 0), (1, 1), (2, 2)]
        for lo, hi in ((0, 0), (1, 1), (2, 2)):
            assert cues[hi][1] - cues[lo][0] <= 60.0

    def test_two_line_oversized_section_splits_one_and_one(self):
        cues = [(0.0, 35.0), (35.8, 70.0)]
        sections = segment_by_gaps(cues, duration=70.75)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 0), (1, 1)]

    def test_tied_widest_gap_breaks_toward_section_midpoint(self):
        # Two 1.0s gaps tie exactly for widest (binary-exact endpoints, so the
        # tie is real, not a float-rounding artifact). The first (near time
        # 10.5) sits closer to the section's 35.0s midpoint than the second
        # (near time 60.5), so it wins even though it's the less even cut.
        cues = [(0.0, 10.0), (11.0, 20.0), (20.5, 60.0), (61.0, 70.0)]
        sections = segment_by_gaps(cues, duration=70.75)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 0), (1, 3)]

    def test_cap_split_survives_stacked_cue_negative_gaps(self):
        # Stacked duet cues overlap, making inter-cue gaps negative; a first
        # gap of exactly -1.0s once collided with a widest-gap sentinel and
        # crashed the tie-break. It must split cleanly like any other value.
        cues = [(0.0, 61.0), (60.0, 62.0)]
        sections = segment_by_gaps(cues, duration=62.5)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 0), (1, 1)]

    def test_all_negative_gaps_split_at_least_negative(self):
        # Fully-overlapped oversized run: the widest gap is the least
        # negative one (-2.0s, at index 1), not the leftmost.
        cues = [(0.0, 20.0), (16.0, 40.0), (38.0, 64.0), (61.0, 90.0)]
        sections = segment_by_gaps(cues, duration=90.75)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 1), (2, 3)]

    def test_negative_gap_boundary_pads_zero_not_inverted(self):
        # A cap split inside cue overlap has no silence to share: each window
        # keeps its own cues' full span instead of inverting the pad and
        # truncating the boundary lines' audio.
        cues = [(0.0, 30.5), (30.0, 62.0)]
        first, second = segment_by_gaps(cues, duration=62.5)
        assert first.t1 == 30.5
        assert second.t0 == 30.0


class TestDensifyCueSpans:
    def test_all_lines_mapped_passthrough(self):
        # Every line anchored -> the dense list is the sparse spans verbatim.
        align = ["one two", "three four"]
        sparse = {0: (0.0, 2.0), 1: (2.5, 4.0)}
        assert densify_cue_spans(sparse, align, duration=5.0) == [(0.0, 2.0), (2.5, 4.0)]

    def test_interior_unmapped_packed_after_anchor(self):
        # Anchors imply 1.0 s/word; the unmapped line packs at that pace right
        # after its left anchor, leaving the rest of the gap as real silence.
        align = ["a b", "c d", "e f"]
        sparse = {0: (0.0, 2.0), 2: (10.0, 12.0)}
        dense = densify_cue_spans(sparse, align, duration=13.0)
        assert dense == [(0.0, 2.0), (2.0, 4.0), (10.0, 12.0)]

    def test_interior_run_compressed_to_fit_gap(self):
        # Paced estimate (3 s) overflows the 1 s gap -> compress to fill it
        # exactly, keeping spans ordered and in-bounds.
        align = ["a b c", "d e f", "g h i"]
        sparse = {0: (0.0, 3.0), 2: (4.0, 7.0)}
        dense = densify_cue_spans(sparse, align, duration=8.0)
        assert dense[1] == (3.0, 4.0)

    def test_leading_packed_back_clamped_to_zero(self):
        # Leading line wants 2 s but only 1 s precedes the anchor -> clamp to 0.
        align = ["a b", "c d"]
        dense = densify_cue_spans({1: (1.0, 3.0)}, align, duration=4.0)
        assert dense == [(0.0, 1.0), (1.0, 3.0)]

    def test_leading_leaves_intro_silence_when_room(self):
        # With room to spare, the leading line packs back against the anchor,
        # leaving the intro silent rather than crawling across it.
        align = ["a b", "c d"]
        dense = densify_cue_spans({1: (10.0, 12.0)}, align, duration=13.0)
        assert dense == [(8.0, 10.0), (10.0, 12.0)]

    def test_trailing_runs_forward_from_last_anchor(self):
        align = ["a b", "c d"]
        dense = densify_cue_spans({0: (0.0, 2.0)}, align, duration=10.0)
        assert dense == [(0.0, 2.0), (2.0, 4.0)]

    def test_densified_gap_splits_into_sections(self):
        # The silence a short unmapped run leaves behind is a real section
        # boundary for segment_by_gaps -- the whole point of packing, not
        # spreading.
        align = ["a b", "c d", "e f", "g h"]
        dense = densify_cue_spans({0: (0.0, 2.0), 3: (20.0, 22.0)}, align, duration=23.0)
        sections = segment_by_gaps(dense, gap_s=1.5, pad_s=0.75, duration=23.0)
        assert [(s.lid_lo, s.lid_hi) for s in sections] == [(0, 2), (3, 3)]

    def test_overlapping_anchors_never_invert_spans(self):
        # ASR anchors guarantee only monotonic starts: anchor 0 ends (5.0) after
        # anchor 2 starts (4.0). The unmapped line between must collapse to a
        # zero-width span, never a backward-walking one.
        align = ["a b", "c d", "e f"]
        dense = densify_cue_spans({0: (0.0, 5.0), 2: (4.0, 9.0)}, align, duration=10.0)
        assert all(start <= end for start, end in dense)
        assert dense[1] == (5.0, 5.0)

    def test_trailing_anchor_past_duration_never_inverts(self):
        # Last ASR word end can exceed media duration (it holds the final word);
        # a trailing unmapped line must still not invert.
        align = ["a b", "c d"]
        dense = densify_cue_spans({0: (0.0, 12.0)}, align, duration=10.0)
        assert all(start <= end for start, end in dense)

    def test_duplicate_anchor_demoted_and_pushed_forward(self):
        # Lines 1 and 2 are an identical refrain the ASR mapped to one span. The
        # duplicate (non-advancing start) is demoted to unmapped and re-placed in
        # the audio after the first occurrence, not stacked on top of it.
        align = ["x", "rep", "rep", "y"]
        sparse = {0: (0.0, 2.0), 1: (4.0, 9.0), 2: (4.0, 9.0), 3: (20.0, 22.0)}
        dense = densify_cue_spans(sparse, align, duration=23.0)
        assert dense[1] == (4.0, 9.0)
        assert dense[2][0] == 9.0  # pushed past the first occurrence
        assert dense[1][1] <= dense[2][0]  # no overlap
        assert dense[2][0] < dense[2][1]  # given room, not zero-width

    def test_empty_sparse_raises(self):
        with pytest.raises(ValueError):
            densify_cue_spans({}, ["a b"], duration=5.0)


class TestMergeCueSpans:
    def test_union_primary_wins(self):
        primary = {0: (1.0, 2.0), 2: (5.0, 6.0)}
        secondary = {0: (1.5, 2.5), 1: (3.0, 4.0)}
        merged = merge_cue_spans(primary, secondary)
        assert merged == {0: (1.0, 2.0), 1: (3.0, 4.0), 2: (5.0, 6.0)}


class TestWarpScaffoldCues:
    def test_empty_scaffold_falls_back_to_densify(self):
        anchors = {0: (0.0, 2.0), 1: (2.0, 4.0)}
        align = ["a b", "c d"]
        assert warp_scaffold_cues(anchors, {}, align, 6.0) == densify_cue_spans(anchors, align, 6.0)

    def test_clean_warp_fills_anchor_gap_and_preserves_silence(self):
        # Same clock (slope 1), 5 shared lines to fit on. The anchors miss line 3
        # (a wide instrumental gap 4s->30s); the dense scaffold places it inside
        # the gap, and the surrounding silence survives.
        align = ["a", "b", "c", "d", "e", "f"]
        anchors = {0: (0.0, 1.0), 1: (2.0, 3.0), 2: (4.0, 5.0), 4: (30.0, 31.0), 5: (32.0, 33.0)}
        scaffold = {
            0: (0.0, 0.5),
            1: (2.0, 2.5),
            2: (4.0, 4.5),
            3: (6.0, 6.5),
            4: (30.0, 30.5),
            5: (32.0, 32.5),
        }
        out = warp_scaffold_cues(anchors, scaffold, align, 35.0)
        assert abs(out[3][0] - 6.0) < 0.5  # scaffold placed the anchor-missed line
        assert out[4][0] - out[3][1] > 1.5  # the instrumental gap is preserved
        assert all(out[i][0] <= out[i + 1][0] for i in range(5))  # monotonic

    def test_linear_tempo_difference_warps_cleanly(self):
        # A 10x-compressed-but-linear scaffold fits exactly -> not gated.
        align = ["a", "b", "c", "d", "e", "f"]
        anchors = {i: (i * 10.0, i * 10.0 + 1) for i in range(6)}
        scaffold = {i: (float(i), i + 0.1) for i in range(6)}
        out = warp_scaffold_cues(anchors, scaffold, align, 60.0)
        assert all(abs(out[i][0] - i * 10.0) < 1.0 for i in range(6))

    def test_gate_rejects_structurally_inconsistent_scaffold(self):
        # Scaffold order-preserving but non-linear vs the audio (a jump): the
        # tempo+offset fit can't reconcile it -> fall back to the anchors alone.
        align = ["a", "b", "c", "d", "e", "f"]
        anchors = {i: (i * 10.0, i * 10.0 + 1) for i in range(6)}
        scaffold = {
            0: (0.0, 0.5),
            1: (1.0, 1.5),
            2: (2.0, 2.5),
            3: (100.0, 100.5),
            4: (101.0, 101.5),
            5: (102.0, 102.5),
        }
        out = warp_scaffold_cues(anchors, scaffold, align, 120.0)
        assert out == densify_cue_spans(anchors, align, 120.0)

    def test_scaffold_clamped_into_duration(self):
        # A scaffold whose lines run past the video end stay in-bounds.
        align = ["a", "b", "c", "d", "e"]
        anchors = {i: (i * 10.0, i * 10.0 + 1) for i in range(5)}
        scaffold = {i: (i * 12.0, i * 12.0 + 0.5) for i in range(5)}  # last at 48s
        out = warp_scaffold_cues(anchors, scaffold, align, 45.0)
        assert all(0.0 <= s <= 45.0 and s <= e <= 45.0 for s, e in out)


class TestSplitSectionToLines:
    def test_splits_words_to_lines_by_token_count(self):
        section = Section(0, 1, 0.0, 4.0)
        display = ["hello world", "goodbye now"]
        aligned = _words(
            ("hello", 0.1, 0.5),
            ("world", 0.6, 1.0),
            ("goodbye", 2.0, 2.5),
            ("now", 2.6, 3.0),
        )
        objs = split_section_to_lines(section, aligned, display, display, [(0.0, 1.0), (2.0, 3.0)])
        assert [o["line_id"] for o in objs] == [0, 1]
        assert [w["word"] for w in objs[0]["words"]] == ["hello", "world"]
        assert [w["word"] for w in objs[1]["words"]] == ["goodbye", "now"]
        assert objs[0]["start"] == 0.1 and objs[0]["end"] == 1.0
        assert objs[1]["start"] == 2.0 and objs[1]["end"] == 3.0
        assert objs[0]["source"] == "cue_align"

    def test_display_text_comes_from_display_line_not_aligned_word(self):
        # align_lines may differ from display_lines (bracket stripping); the
        # rendered word text follows the lyric sheet, timing follows the audio.
        section = Section(0, 0, 0.0, 2.0)
        objs = split_section_to_lines(
            section,
            _words(("oh", 0.1, 0.4), ("yeah", 0.5, 0.9)),
            display_lines=["Oh yeah"],
            align_lines=["oh yeah"],
            cue_spans=[(0.0, 1.0)],
        )
        assert objs[0]["text"] == "Oh yeah"
        assert [w["word"] for w in objs[0]["words"]] == ["oh", "yeah"]

    def test_word_sweep_capped(self):
        section = Section(0, 0, 0.0, 30.0)
        # A 10 s "forever" sweep is clamped, anchored at its start.
        objs = split_section_to_lines(
            section,
            _words(("forever", 5.0, 15.0)),
            ["forever"],
            ["forever"],
            [(5.0, 15.0)],
            max_word_dur=1.5,
        )
        word = objs[0]["words"][0]
        assert word["start"] == 5.0
        assert word["end"] == 6.5

    def test_low_coverage_line_is_hidden(self):
        # Only 1 of 4 tokens aligned -> below the 0.5 gate -> hidden.
        section = Section(0, 0, 0.0, 4.0)
        objs = split_section_to_lines(
            section,
            _words(("the", 0.1, 0.3)),
            ["the quick brown fox"],
            ["the quick brown fox"],
            [(0.0, 4.0)],
            min_coverage=0.5,
        )
        assert objs[0]["words"] == []
        assert objs[0]["start"] is None and objs[0]["end"] is None

    def test_display_only_line_has_no_words(self):
        # A line with no alignable tokens (e.g. punctuation) is hidden, and
        # consumes no aligned words so the next line still maps correctly.
        section = Section(0, 1, 0.0, 3.0)
        objs = split_section_to_lines(
            section,
            _words(("real", 1.0, 1.4), ("line", 1.5, 1.9)),
            display_lines=["...", "real line"],
            align_lines=["...", "real line"],
            cue_spans=[(0.0, 0.5), (1.0, 2.0)],
        )
        assert objs[0]["words"] == []
        assert [w["word"] for w in objs[1]["words"]] == ["real", "line"]

    def test_dropped_interior_word_does_not_shift_later_lines(self):
        # The aligner dropped "world" (a failed/instant word). The normalised
        # match skips that token instead of letting every later word slide up
        # by one, so line 2 still gets its own words.
        section = Section(0, 1, 0.0, 4.0)
        display = ["hello big world", "goodbye now"]
        aligned = _words(
            ("hello", 0.1, 0.5),
            ("big", 0.6, 1.0),
            # "world" missing
            ("goodbye", 2.0, 2.5),
            ("now", 2.6, 3.0),
        )
        objs = split_section_to_lines(section, aligned, display, display, [(0.0, 1.2), (2.0, 3.0)])
        assert [w["word"] for w in objs[0]["words"]] == ["hello", "big"]
        assert [w["word"] for w in objs[1]["words"]] == ["goodbye", "now"]

    def test_unmatchable_word_does_not_stall_later_lines(self):
        # The aligner emitted a standalone "-" whose token the tokeniser
        # dropped (normalises to empty). Greedy head-matching would stall on
        # it and hide every later line; the assignment just skips it.
        section = Section(0, 1, 0.0, 4.0)
        display = ["hello world", "goodbye now"]
        aligned = _words(
            ("hello", 0.1, 0.5),
            ("world", 0.6, 1.0),
            ("-", 1.4, 1.5),
            ("goodbye", 2.0, 2.5),
            ("now", 2.6, 3.0),
        )
        objs = split_section_to_lines(section, aligned, display, display, [(0.0, 1.0), (2.0, 3.0)])
        assert [w["word"] for w in objs[0]["words"]] == ["hello", "world"]
        assert [w["word"] for w in objs[1]["words"]] == ["goodbye", "now"]

    def test_dropped_repeat_line_does_not_steal_twins_words(self):
        # Lines 0 and 1 are the same refrain; the aligner dropped ALL of line
        # 0's words. Text-only greedy matching would hand line 1's words to
        # line 0 and shift every later repeat up a line; the time tiebreak
        # keeps them on line 1 and leaves line 0 for the cue rescue.
        section = Section(0, 1, 0.0, 6.0)
        display = ["la la", "la la"]
        aligned = _words(("la", 3.1, 3.5), ("la", 3.9, 4.4))
        objs = split_section_to_lines(section, aligned, display, display, [(0.0, 2.0), (3.0, 5.0)])
        assert objs[0]["words"] == []
        assert [w["start"] for w in objs[1]["words"]] == [3.1, 3.9]


class TestRepaceBadLines:
    def test_hidden_line_is_repaced_across_offset_corrected_cue(self):
        # Four good lines fix the offset; one hidden line is filled from its cue.
        cue_spans = [(0.0, 1.0), (2.0, 3.0), (4.0, 5.0), (6.0, 7.0), (8.0, 10.0)]
        lines = ["a a", "b b", "c c", "d d", "ee ff"]
        # Good lines aligned 0.5s after their cue starts -> offset = +0.5.
        objs = [
            {
                "line_id": 0,
                "text": "a a",
                "words": _words(("a", 0.5, 0.8), ("a", 0.85, 1.1)),
                "start": 0.5,
                "end": 1.1,
                "source": SOURCE,
            },
            {
                "line_id": 1,
                "text": "b b",
                "words": _words(("b", 2.5, 2.8), ("b", 2.85, 3.1)),
                "start": 2.5,
                "end": 3.1,
                "source": SOURCE,
            },
            {
                "line_id": 2,
                "text": "c c",
                "words": _words(("c", 4.5, 4.8), ("c", 4.85, 5.1)),
                "start": 4.5,
                "end": 5.1,
                "source": SOURCE,
            },
            {
                "line_id": 3,
                "text": "d d",
                "words": _words(("d", 6.5, 6.8), ("d", 6.85, 7.1)),
                "start": 6.5,
                "end": 7.1,
                "source": SOURCE,
            },
            {
                "line_id": 4,
                "text": "ee ff",
                "words": [],
                "start": None,
                "end": None,
                "source": SOURCE,
            },
        ]
        out, stats = repace_bad_lines(objs, cue_spans, lines, lines)
        assert stats["offset_s"] == 0.5
        assert stats["n_repaced"] == 1
        filled = out[4]
        assert filled["source"] == SOURCE_FILL
        # Cue (8.0, 10.0) shifted by +0.5 -> words span [8.5, 10.5].
        assert filled["start"] == 8.5
        assert filled["end"] == 10.5
        assert [w["word"] for w in filled["words"]] == ["ee", "ff"]
        # Good lines are untouched (passed through by identity).
        assert out[0] is objs[0]

    def test_drifted_line_is_repaced(self):
        # A parked tail: a 5 s internal gap whose far word overruns the cue
        # span. That is drift -> re-paced.
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("gg hh")
        objs.append(_line(4, "gg hh", ("gg", 8.0, 8.3), ("hh", 13.5, 13.8)))  # 5.2 s gap
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert stats["n_repaced"] == 1
        assert out[4]["source"] == SOURCE_FILL
        gaps = [b["start"] - a["end"] for a, b in zip(out[4]["words"], out[4]["words"][1:])]
        assert all(g < 2.0 for g in gaps)

    def test_mostly_instant_line_is_repaced(self):
        # A line of near-zero-duration words has no big gap but a broken sweep.
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("ii jj")
        objs.append(_line(4, "ii jj", ("ii", 8.0, 8.01), ("jj", 8.02, 8.03)))  # both instant
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert stats["n_repaced"] == 1
        assert out[4]["source"] == SOURCE_FILL
        # Re-paced words have real (non-instant) durations.
        assert all(w["end"] - w["start"] > 0.05 for w in out[4]["words"])

    def test_offset_falls_back_to_zero_with_too_few_anchors(self):
        cue_spans = [(0.0, 1.0), (5.0, 7.0)]
        lines = ["a a", "bb cc"]
        objs = [
            {
                "line_id": 0,
                "text": "a a",
                "words": _words(("a", 0.9, 1.1), ("a", 1.15, 1.4)),
                "start": 0.9,
                "end": 1.4,
                "source": SOURCE,
            },
            {
                "line_id": 1,
                "text": "bb cc",
                "words": [],
                "start": None,
                "end": None,
                "source": SOURCE,
            },
        ]
        out, stats = repace_bad_lines(objs, cue_spans, lines, lines, min_anchors=4)
        assert stats["offset_s"] == 0.0  # one anchor < 4 -> no offset
        assert out[1]["start"] == 5.0  # raw cue start

    def test_display_only_bad_line_stays_hidden(self):
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 9.0))
        lines.append("...")
        objs.append(_line(4, "..."))
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert stats["n_repaced"] == 0
        assert out[4]["words"] == []  # no alignable tokens -> nothing to sweep

    def test_covered_pause_is_not_drift(self):
        # A 5 s internal gap *inside* the line's cue span is a caption-covered
        # pause: the aligned timing is right, re-pacing would smear the words
        # evenly across it.
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 15.0))
        lines.append("gg hh")
        objs.append(_line(4, "gg hh", ("gg", 8.0, 8.3), ("hh", 13.5, 13.8)))
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert stats["n_repaced"] == 0
        assert out[4] is objs[4]

    def test_repace_clamped_to_duration(self):
        objs, cues, lines = _anchor_lines(4, offset=0.5)
        cues.append((8.0, 10.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff"))
        out, _stats = repace_bad_lines(objs, cues, lines, lines, duration=9.2)
        # Cue end 10.0 + offset 0.5 clamps to the 9.2 s song end.
        assert out[4]["end"] == pytest.approx(9.2)

    def test_fill_weights_longer_tokens_longer(self):
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 11.0))
        lines.append("hi wonderful")
        objs.append(_line(4, "hi wonderful"))
        out, _stats = repace_bad_lines(objs, cues, lines, lines)
        hi, wonderful = out[4]["words"]
        # "wonderful" (9 chars) gets the lion's share of the 3 s span.
        assert wonderful["start"] - hi["start"] == pytest.approx(3.0 * 2 / 11)
        assert wonderful["end"] - wonderful["start"] > hi["end"] - hi["start"]

    def test_realign_rescues_before_fill(self):
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff"))
        calls = []

        def realign(lid, t0, t1):
            calls.append((lid, t0, t1))
            return _words(("ee", 8.1, 8.5), ("ff", 8.6, 9.0))

        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=realign)
        assert calls == [(4, 8.0, 10.0)]
        assert out[4]["source"] == SOURCE_REALIGN
        assert [w["start"] for w in out[4]["words"]] == [8.1, 8.6]
        assert stats["n_realigned"] == 1 and stats["n_repaced"] == 0

    def test_realign_failure_falls_back_to_fill(self):
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff"))
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda lid, t0, t1: None)
        assert out[4]["source"] == SOURCE_FILL
        assert stats["n_realigned"] == 0 and stats["n_repaced"] == 1

    def test_realign_bad_result_rejected(self):
        # The per-line align parked "ff" far past the cue span -- the same
        # drift the rescue exists to fix. Keep the paced fill instead.
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff"))

        def parked(lid, t0, t1):
            return _words(("ee", 8.1, 8.4), ("ff", 19.5, 19.8))

        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=parked)
        assert out[4]["source"] == SOURCE_FILL
        assert stats["n_realigned"] == 0 and stats["n_repaced"] == 1

    def test_realign_displaced_tight_result_rejected(self):
        # A tightly-packed re-align result parked wholly past the cue end has
        # no internal gap for a drift test to catch -- containment alone must
        # reject it.
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff"))

        def displaced(lid, t0, t1):
            return _words(("ee", 10.7, 10.75), ("ff", 10.8, 10.9))

        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=displaced)
        assert out[4]["source"] == SOURCE_FILL
        assert stats["n_realigned"] == 0 and stats["n_repaced"] == 1

    def test_displaced_tight_split_line_is_trusted(self):
        # A cleanly-aligned line sitting a second past its cue span stays:
        # caption cue times carry per-line jitter, and the audio timing wins.
        # (Only a re-align *result* is gated on containment.)
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 10.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff", ("ee", 11.0, 11.3), ("ff", 11.4, 11.8)))
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert out[4] is objs[4]
        assert stats["n_repaced"] == 0 and stats["n_realigned"] == 0

    def test_displaced_identical_repeat_is_flagged(self):
        # Six identical chant lines; line 2's words landed two repeat periods
        # late (on line 4's occurrence). It is internally clean, so clean-trust
        # would keep it stacked on its twin -- identical-text runs demand
        # containment instead, and the line falls to the cue fill.
        objs, cues, lines = _anchor_lines(6)
        objs[2] = _line(2, "a a", ("a", 8.0, 8.3), ("a", 8.4, 8.8))
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert out[2]["source"] == SOURCE_FILL
        assert out[2]["start"] == pytest.approx(4.0)
        assert out[2]["end"] == pytest.approx(5.0)
        assert stats["n_repaced"] == 1
        assert out[1] is objs[1]  # correctly-placed repeats untouched

    def test_jittered_identical_repeat_stays_trusted(self):
        # Within a repeat run the containment slack is half the repeat period
        # (1.0 s here), not PAUSE_SLACK_S: a line 0.7 s past its cue is
        # ordinary caption jitter, far from the aliasing boundary, and stays.
        objs, cues, lines = _anchor_lines(6)
        objs[2] = _line(2, "a a", ("a", 4.7, 5.0), ("a", 5.1, 5.5))
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        assert out[2] is objs[2]
        assert stats["n_repaced"] == 0 and stats["n_realigned"] == 0

    def test_fill_for_cue_past_duration_stays_inside_audio(self):
        # SRT cue starts after the media ends (trimmed video): the fill must
        # not emit words past the real song end.
        objs, cues, lines = _anchor_lines(4)
        cues.append((100.0, 101.0))
        lines.append("ee ff")
        objs.append(_line(4, "ee ff"))
        out, _stats = repace_bad_lines(objs, cues, lines, lines, duration=95.0)
        assert out[4]["start"] == pytest.approx(94.5)
        assert out[4]["end"] == pytest.approx(95.0)


class TestFitOffset:
    def test_prefers_full_coverage_anchors(self):
        # Four full-coverage lines aligned +0.5 late; four partial lines whose
        # dropped first word makes them start +2.0 late. With align_lines the
        # partials are excluded from the fit; without, they drag the median.
        cues = [(2.0 * i, 2.0 * i + 1.0) for i in range(8)]
        lines = ["a b"] * 8
        objs = []
        for i in range(4):
            c0 = cues[i][0]
            objs.append(_line(i, "a b", ("a", c0 + 0.5, c0 + 0.8), ("b", c0 + 0.9, c0 + 1.2)))
        for i in range(4, 8):
            c0 = cues[i][0]
            objs.append(_line(i, "a b", ("b", c0 + 2.0, c0 + 2.3)))
        assert fit_offset(objs, cues, lines) == 0.5
        assert fit_offset(objs, cues) == pytest.approx(1.25)

    def test_zero_when_too_few_anchors(self):
        cues = [(0.0, 1.0)]
        objs = [_line(0, "a", ("a", 0.4, 0.7))]
        assert fit_offset(objs, cues, ["a"]) == 0.0


def _stub_aligner(words_for):
    """Injectable slice_align that records its calls and returns ``words_for``."""
    calls: list[tuple] = []

    def slice_align(t0, t1, text, label):
        calls.append((t0, t1, text, label))
        return words_for(t0, t1, text, label)

    slice_align.calls = calls
    return slice_align


# Four "a a" lines at cues 1 s apart -> a single section (gaps < SECTION_GAP_S).
_SONG_CUES = [(0.0, 1.0), (2.0, 3.0), (4.0, 5.0), (6.0, 7.0)]
_SONG_LINES = ["a a", "a a", "a a", "a a"]


def _on_cue_words(shift: float = 0.0) -> list[dict]:
    """Two words per line placed inside each (shifted) cue span."""
    return _words(
        *[
            (tok, c0 + shift + 0.5 * k, c0 + shift + 0.5 * k + 0.4)
            for c0, _c1 in _SONG_CUES
            for k, tok in enumerate(("a", "a"))
        ]
    )


class TestAlignSong:
    """The cue-align driver: sectioning, offset re-section, and re-pace, with
    the forced aligner injected so the orchestration is exercised purely."""

    def test_clean_song_uses_aligned_words_one_pass(self):
        aligner = _stub_aligner(lambda *_: _on_cue_words())
        objs, stats = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 8.0, aligner)

        assert [o["line_id"] for o in objs] == [0, 1, 2, 3]
        assert all(o["source"] == SOURCE for o in objs)
        assert stats["n_sections"] == 1
        assert stats["resectioned"] is False
        assert stats["repace"]["n_repaced"] == 0
        assert stats["repace"]["n_realigned"] == 0
        # One section pass, no per-line rescue; label names the section.
        assert len(aligner.calls) == 1
        assert "section" in aligner.calls[0][3]

    def test_large_display_lead_triggers_resection(self):
        # Aligner reports every line ~1.5 s late (> SECTION_PAD_S): the driver
        # re-sections once on offset-shifted cues, after which the words match.
        aligner = _stub_aligner(lambda *_: _on_cue_words(shift=1.5))
        objs, stats = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 12.0, aligner)

        assert stats["resectioned"] is True
        assert stats["offset_s"] == pytest.approx(1.5, abs=0.05)
        # Two section passes (initial + re-section), no per-line rescue needed.
        assert len(aligner.calls) == 2
        assert all(o["source"] == SOURCE for o in objs)

    def test_unplaceable_section_repaces_from_cues(self):
        # Aligner can place nothing: every line is rescued by a per-line realign
        # (also None) and then filled from its cue span.
        aligner = _stub_aligner(lambda *_: None)
        objs, stats = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 8.0, aligner)

        assert all(o["source"] == SOURCE_FILL for o in objs)
        assert stats["repace"]["n_repaced"] == 4
        # One section pass + one per-line realign attempt for each of 4 lines.
        assert len(aligner.calls) == 1 + 4
        assert any("line" in c[3] for c in aligner.calls)

    def test_unreadable_duration_still_produces_output(self):
        # duration=None (stem duration unreadable) must not crash; the fill
        # windows simply lose their audio-end clamp.
        aligner = _stub_aligner(lambda *_: None)
        objs, stats = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, None, aligner)

        assert [o["line_id"] for o in objs] == [0, 1, 2, 3]
        assert all(o["source"] == SOURCE_FILL for o in objs)
