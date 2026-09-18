"""Unit tests for scripts/scaffold_warp.py (the closed line route's cue builder)."""

import importlib.util
import sys
from pathlib import Path

import pytest

from pikaraoke.lib.cue_align import segment_by_gaps

# scripts/ is not a package — load the module straight from its file.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "scaffold_warp.py"
_spec = importlib.util.spec_from_file_location("scaffold_warp", _SCRIPT)
scaffold_warp = importlib.util.module_from_spec(_spec)
sys.modules["scaffold_warp"] = scaffold_warp
_spec.loader.exec_module(scaffold_warp)

densify_cue_spans = scaffold_warp.densify_cue_spans
merge_cue_spans = scaffold_warp.merge_cue_spans
warp_scaffold_cues = scaffold_warp.warp_scaffold_cues


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

    def test_affine_clean_scaffold_unchanged_by_rescue_tier(self):
        # The 14-song affine-clean case: identical to test_linear_tempo_
        # difference_warps_cleanly -- the new offset-rescue path is only
        # reached when the affine fit itself misses its gate, so a clean
        # affine fit here must produce the exact same result as before.
        align = ["a", "b", "c", "d", "e", "f"]
        anchors = {i: (i * 10.0, i * 10.0 + 1) for i in range(6)}
        scaffold = {i: (float(i), i + 0.1) for i in range(6)}
        out = warp_scaffold_cues(anchors, scaffold, align, 60.0)
        assert all(abs(out[i][0] - i * 10.0) < 1.0 for i in range(6))

    def test_contaminated_common_points_rescued_by_constant_offset(self):
        # Paradise-shaped: 9 common points, 6 agreeing on a clean +24s constant
        # offset and 3 mis-mapped onto a repeated line (residuals +46/+72/+72
        # against that offset). The mis-mapped third of the points contaminate
        # enough Theil-Sen pairwise slopes that the affine fit misses the
        # mad_gate (slope ~1.91, MAD ~9.1), but the fixed-slope offset model
        # -- median(anchor - scaffold) over the same points -- lands exactly
        # on the true +24s offset with 0 residual on the 6 clean points, so
        # the scaffold is rescued rather than discarded for densify.
        align = [str(i) for i in range(9)]
        anchors = {i: (i * 10.0 + 24.0, i * 10.0 + 24.5) for i in range(6)}
        anchors[6] = (60.0 + 24.0 + 46.0, 60.0 + 24.0 + 46.5)
        anchors[7] = (70.0 + 24.0 + 72.0, 70.0 + 24.0 + 72.5)
        anchors[8] = (80.0 + 24.0 + 72.0, 80.0 + 24.0 + 72.5)
        scaffold = {i: (i * 10.0, i * 10.0 + 0.4) for i in range(9)}
        out = warp_scaffold_cues(anchors, scaffold, align, 200.0)
        # Rescued: every scaffold line warps onto the audio clock at +24s,
        # not the densify fallback's anchors-only placement.
        assert out != densify_cue_spans(anchors, align, 200.0)
        for i in range(9):
            assert abs(out[i][0] - (i * 10.0 + 24.0)) < 1.0

    def test_offset_model_also_fails_stays_on_densify(self):
        # Defying-Gravity-shaped: a structurally different recording (a real
        # tempo delta, slope ~0.79, plus enough scatter that even the affine
        # fit misses its own gate). The fixed-slope offset model fails too
        # (MAD ~5.95 > the 2.0 gate) -- neither warp model reconciles it, so
        # this must still fall back to densify, exactly as before the rescue
        # tier existed.
        align = [str(i) for i in range(6)]
        xs = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
        noise = [0.0, 6.0, -6.0, 8.0, -8.0, 3.0]
        scaffold = {i: (x, x + 0.5) for i, x in enumerate(xs)}
        anchors = {i: (x * 0.79 + n, x * 0.79 + n + 0.5) for i, (x, n) in enumerate(zip(xs, noise))}
        out = warp_scaffold_cues(anchors, scaffold, align, 60.0)
        assert out == densify_cue_spans(anchors, align, 60.0)

    def test_scaffold_clamped_into_duration(self):
        # A scaffold whose lines run past the video end stay in-bounds.
        align = ["a", "b", "c", "d", "e"]
        anchors = {i: (i * 10.0, i * 10.0 + 1) for i in range(5)}
        scaffold = {i: (i * 12.0, i * 12.0 + 0.5) for i in range(5)}  # last at 48s
        out = warp_scaffold_cues(anchors, scaffold, align, 45.0)
        assert all(0.0 <= s <= 45.0 and s <= e <= 45.0 for s, e in out)
