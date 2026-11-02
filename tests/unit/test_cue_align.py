"""Unit tests for the cue-anchored windowed alignment core (pure logic)."""

import numpy as np
import pytest

from pikaraoke.lib.cue_align import (
    SOURCE,
    SOURCE_FILL,
    SOURCE_REALIGN,
    Section,
    align_song,
    fit_offset,
    repace_bad_lines,
    segment_by_gaps,
    split_section_to_lines,
)
from pikaraoke.lib.onset_snap import HOP_S


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

    def test_a_duet_sections_end_follows_its_latest_ending_line(self):
        # Line 0 (singer A, held to 6.0) outlasts line 1 (singer B).
        first, _ = segment_by_gaps([(0.0, 6.0), (1.0, 3.0), (10.0, 12.0)], duration=13.0)
        assert first.t1 == 6.75


def _env(duration_s: float, sung: list[tuple[float, float]]) -> np.ndarray:
    """A dB envelope that is sung (-20) inside ``sung`` and silent (-70) elsewhere."""
    env = np.full(int(duration_s / HOP_S) + 1, -70.0)
    for a, b in sung:
        env[int(a / HOP_S) : int(b / HOP_S)] = -20.0
    return env


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
        assert calls == [(4, 7.25, 10.75)]  # the cue window, padded
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


class TestPartialLines:
    """A line the align timed only partly is rescued, and never shown with words missing."""

    def _song(self, *words: tuple[str, float, float], text: str = "ee ff gg"):
        """Four anchors plus line 4 (cue 8-9) with ``words`` timed out of ``text``."""
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 9.0))
        lines.append(text)
        objs.append(_line(4, text, *words))
        return objs, cues, lines

    def test_a_realign_timing_fewer_words_keeps_the_line_and_guesses_the_rest(self):
        objs, cues, lines = self._song(
            ("ee", 8.0, 8.3), ("ff", 8.4, 8.7), ("gg", 8.8, 9.1), text="ee ff gg hh"
        )

        def realign(lid, t0, t1):
            return _words(("ee", 8.0, 8.3), ("ff", 8.4, 8.7))

        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=realign)
        assert out[4]["source"] == SOURCE
        assert [w["word"] for w in out[4]["words"]] == ["ee", "ff", "gg", "hh"]
        assert out[4]["words"][3]["start"] == pytest.approx(9.1)  # runs on from "gg"
        assert stats["n_realigned"] == 0 and stats["n_repaced"] == 0
        assert stats["n_guessed_words"] == 1 and stats["guessed_word_line_ids"] == [4]

    def test_a_guessed_tail_keeps_the_lines_pace(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), text="ee ff gg")
        out, _stats = repace_bad_lines(objs, cues, lines, lines)
        _ee, ff, gg = out[4]["words"]
        assert (ff["start"], ff["end"]) == pytest.approx((8.3, 8.6))
        assert (gg["start"], gg["end"]) == pytest.approx((8.6, 8.9))
        assert out[4]["end"] == pytest.approx(8.9)

    def test_a_guessed_tail_ends_by_the_next_lines_first_word(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), text="ee ff gg")
        cues.append((8.7, 9.5))
        lines.append("a a")
        objs.append(_line(5, "a a", ("a", 8.7, 9.0), ("a", 9.1, 9.4)))
        out, _stats = repace_bad_lines(objs, cues, lines, lines)
        _ee, ff, gg = out[4]["words"]
        assert (ff["start"], gg["start"], gg["end"]) == pytest.approx((8.3, 8.5, 8.7))

    def test_a_guessed_tail_ends_by_the_lines_window(self):
        # Cue 8.0-8.4: its window ends a pad after, at 9.15, short of the tail's 9.5.
        objs, cues, lines = self._song(("ee", 8.0, 8.3), text="ee ff gg hh ii")
        cues[4] = (8.0, 8.4)
        out, _stats = repace_bad_lines(objs, cues, lines, lines)
        assert out[4]["end"] == pytest.approx(9.15)

    def test_a_guessed_word_is_capped_at_the_longest_word(self):
        objs, cues, lines = self._song(("ee", 8.0, 9.0), text="ee ff")
        cues[4] = (8.0, 12.0)
        out, _stats = repace_bad_lines(objs, cues, lines, lines, max_word_dur=0.6)
        ff = out[4]["words"][1]
        assert ff["end"] - ff["start"] == pytest.approx(0.6)

    def test_a_guessed_head_runs_back_no_further_than_the_previous_line(self):
        objs, cues, lines = self._song(("ff", 8.3, 8.6), ("gg", 8.7, 9.0), text="ee ff gg")
        ee = repace_bad_lines(objs, cues, lines, lines)[0][4]["words"][0]
        assert (ee["start"], ee["end"]) == pytest.approx((8.0, 8.3))
        lines[3] = "b b"  # its own text, so no repeat-run containment applies
        objs[3] = _line(3, "b b", ("b", 6.0, 6.3), ("b", 6.4, 8.2))  # held to 8.2
        ee = repace_bad_lines(objs, cues, lines, lines)[0][4]["words"][0]
        assert (ee["start"], ee["end"]) == pytest.approx((8.2, 8.3))

    def test_a_guessed_middle_word_sits_between_its_neighbours(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), ("gg", 8.8, 9.0), text="ee ff gg")
        out, _stats = repace_bad_lines(objs, cues, lines, lines)
        ff = out[4]["words"][1]
        assert ff["word"] == "ff"
        assert 8.3 <= ff["start"] and ff["end"] <= 8.8

    def test_a_guessed_middle_word_between_touching_neighbours_shares_the_first(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), ("gg", 8.3, 8.6), text="ee ff gg")
        ee, ff, gg = repace_bad_lines(objs, cues, lines, lines)[0][4]["words"]
        assert (ee["start"], ee["end"]) == pytest.approx((8.0, 8.15))
        assert (ff["start"], ff["end"]) == pytest.approx((8.15, 8.3))
        assert (gg["start"], gg["end"]) == (8.3, 8.6)

    def test_a_guessed_tail_past_a_timed_word_overrunning_the_bound_shares_its_slot(self):
        # A duet partner's line starts at 8.7, while "ff" is still held to 8.9.
        objs, cues, lines = self._song(("ee", 8.0, 8.3), ("ff", 8.4, 8.9), text="ee ff gg hh")
        cues.append((8.7, 9.5))
        lines.append("a a")
        objs.append(_line(5, "a a", ("a", 8.7, 9.0), ("a", 9.1, 9.4)))
        words = repace_bad_lines(objs, cues, lines, lines)[0][4]["words"]
        assert [w["word"] for w in words] == ["ee", "ff", "gg", "hh"]
        assert [w["start"] for w in words[1:]] == pytest.approx([8.4, 8.5, 8.6])
        assert all(w["end"] - w["start"] == pytest.approx(0.1) for w in words[1:])
        assert words[-1]["end"] == pytest.approx(8.7)

    def test_a_guessed_head_before_a_word_at_the_previous_lines_end_shares_its_slot(self):
        objs, cues, lines = self._song(("ff", 8.2, 8.6), ("gg", 8.7, 9.0), text="ee ff gg")
        lines[3] = "b b"
        objs[3] = _line(3, "b b", ("b", 6.0, 6.3), ("b", 6.4, 8.2))  # held to ff's start
        ee, ff, _gg = repace_bad_lines(objs, cues, lines, lines)[0][4]["words"]
        assert (ee["start"], ee["end"]) == pytest.approx((8.2, 8.4))
        assert (ff["start"], ff["end"]) == pytest.approx((8.4, 8.6))

    def test_a_repeated_phrase_missing_its_tail_is_guessed_after_the_timed_words(self):
        # "no more" twice, the second pair untimed, and the timed pair late in the cue.
        # Matched by expected time the timed words take the second pair's tokens, and the
        # guesses fill the first pair ahead of them; in order, they are the first pair.
        objs, cues, lines = self._song(
            ("no", 8.7, 8.8), ("more,", 8.9, 9.0), text="no more, no more"
        )
        out, stats = repace_bad_lines(objs, cues, lines, lines)
        words = out[4]["words"]
        assert [w["word"] for w in words] == ["no", "more,", "no", "more"]
        assert [(w["start"], w["end"]) for w in words[:2]] == [(8.7, 8.8), (8.9, 9.0)]
        assert words[2]["start"] == pytest.approx(9.0)
        assert words[3]["end"] == pytest.approx(9.2)
        assert stats["n_guessed_words"] == 2

    def test_a_guessed_tail_after_a_kept_line_past_its_window_is_not_shown_for_no_time(self):
        # A clean line sung 1.9 s after its cue is kept off-cue; its words end past the
        # window (9.75), so the window alone would leave "gg" no room at all.
        objs, cues, lines = self._song(("ee", 9.9, 10.2), ("ff", 10.3, 10.6))
        _ee, ff, gg = repace_bad_lines(objs, cues, lines, lines)[0][4]["words"]
        assert (ff["start"], ff["end"]) == pytest.approx((10.3, 10.45))
        assert (gg["start"], gg["end"]) == pytest.approx((10.45, 10.6))

    def test_guessed_words_keep_the_lyrics_own_spelling(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), text="ee Ff,")
        out, _stats = repace_bad_lines(objs, cues, lines, lines)
        assert out[4]["words"][1]["word"] == "Ff,"

    def test_an_unplaced_line_is_filled_over_its_cue_not_its_window(self):
        objs, cues, lines = self._song(text="ee ff")
        env = _env(14.0, [(8.3, 10.6)])
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: None, env=env)
        assert out[4]["source"] == SOURCE_FILL
        assert (out[4]["start"], out[4]["end"]) == pytest.approx((8.0, 9.0))
        assert stats["n_guessed_words"] == 0

    def test_a_first_word_dragged_into_the_lead_in_is_cut_to_the_bound(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), ("ff", 8.4, 8.8))
        dragged = _words(("ee", 7.0, 7.9), ("ff", 8.0, 8.4), ("gg", 8.5, 9.0))
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: dragged)
        assert out[4]["source"] == SOURCE_REALIGN
        first = out[4]["words"][0]
        assert (first["start"], first["end"]) == pytest.approx((7.5, 7.9))  # cue start - slack
        assert out[4]["start"] == pytest.approx(7.5)
        assert stats["n_realigned"] == 1

    def test_a_first_word_with_too_little_left_past_the_bound_is_still_rejected(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), ("ff", 8.4, 8.8))
        before_the_line = _words(("ee", 7.0, 7.52), ("ff", 8.0, 8.4), ("gg", 8.5, 9.0))
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: before_the_line)
        assert out[4]["source"] == SOURCE
        assert stats["n_realigned"] == 0

    def test_a_last_word_past_the_end_bound_is_still_rejected(self):
        objs, cues, lines = self._song(("ee", 8.0, 8.3), ("ff", 8.4, 8.8))
        parked = _words(("ee", 8.0, 8.3), ("ff", 8.4, 8.8), ("gg", 9.6, 10.2))
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: parked)
        assert out[4]["source"] == SOURCE
        assert stats["n_realigned"] == 0 and stats["n_guessed_words"] == 1


class TestCrammedLines:
    """A word for every token is not enough: zero-length words count as missing."""

    CRAMMED = (("ee", 8.0, 8.3), ("ff", 8.3, 8.3), ("gg", 8.3, 8.3), ("hh", 8.3, 8.8))
    TIMED = (("ee", 8.0, 8.3), ("ff", 8.3, 8.5), ("gg", 8.5, 8.7), ("hh", 8.7, 8.9))

    def _song(self, *words: tuple[str, float, float]):
        """Four anchors plus line 4 (cue 8-9, "ee ff gg hh") with ``words``."""
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 9.0))
        lines.append("ee ff gg hh")
        objs.append(_line(4, "ee ff gg hh", *words))
        return objs, cues, lines

    def test_a_line_with_zero_length_words_asks_a_realign_and_keeps_one_that_times_more(self):
        objs, cues, lines = self._song(*self.CRAMMED)
        calls = []

        def realign(lid, w0, w1):
            calls.append(lid)
            return _words(*self.TIMED)

        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=realign)
        assert calls == [4]
        assert out[4]["source"] == SOURCE_REALIGN
        assert [(w["start"], w["end"]) for w in out[4]["words"]] == [
            (8.0, 8.3),
            (8.3, 8.5),
            (8.5, 8.7),
            (8.7, 8.9),
        ]
        assert stats["n_realigned"] == 1 and stats["crammed_line_ids"] == [4]

    def test_it_keeps_its_own_words_when_the_realign_times_no_more(self):
        objs, cues, lines = self._song(*self.CRAMMED)
        out, stats = repace_bad_lines(
            objs, cues, lines, lines, realign=lambda *_: _words(*self.CRAMMED)
        )
        assert out[4]["source"] == SOURCE
        assert [(w["start"], w["end"]) for w in out[4]["words"]] == [
            (8.0, 8.3),
            (8.3, 8.3),
            (8.3, 8.3),
            (8.3, 8.8),
        ]
        assert stats["n_realigned"] == 0 and stats["crammed_line_ids"] == [4]
        assert stats["n_guessed_words"] == 0 and stats["n_repaced"] == 0

    def test_a_line_with_every_word_timed_asks_nothing(self):
        objs, cues, lines = self._song(*self.TIMED)

        def realign(lid, w0, w1):
            raise AssertionError("no re-align expected")

        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=realign)
        assert out[4]["source"] == SOURCE
        assert stats["crammed_line_ids"] == [] and stats["n_windows"] == 0

    def test_only_the_line_with_a_word_for_every_token_is_crammed(self):
        objs, cues, lines = self._song(*self.CRAMMED)
        cues.append((10.0, 11.0))
        lines.append("ii jj")
        objs.append(_line(5, "ii jj", ("ii", 10.0, 10.3)))  # a word short, none zero-length
        _out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: None)
        assert stats["crammed_line_ids"] == [4]
        assert stats["guessed_word_line_ids"] == [5]


class TestStartAfterPrevious:
    """A re-aligned first word may not start while the previous line's last word still sounds."""

    def _song(self, *realigned: tuple[str, float, float]):
        """Line 3's last word ends at 8.2; line 4 (cue 8-9, "ee ff gg") has only "ff" timed.
        Returns the rescue's output for ``realign`` answering with ``realigned``."""
        objs, cues, lines = _anchor_lines(3)
        cues.append((6.0, 7.0))
        lines.append("bb cc")
        objs.append(_line(3, "bb cc", ("bb", 6.0, 6.3), ("cc", 7.0, 8.2)))
        cues.append((8.0, 9.0))
        lines.append("ee ff gg")
        objs.append(_line(4, "ee ff gg", ("ff", 8.5, 8.7)))
        return repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: _words(*realigned))

    def test_a_first_word_on_the_previous_lines_last_word_starts_where_it_ends(self):
        out, stats = self._song(("ee", 8.0, 8.5), ("ff", 8.5, 8.7), ("gg", 8.7, 8.9))
        assert out[4]["source"] == SOURCE_REALIGN and stats["n_realigned"] == 1
        first = out[4]["words"][0]
        assert (first["start"], first["end"]) == pytest.approx((8.2, 8.5))
        assert out[4]["start"] == pytest.approx(8.2)

    def test_with_too_little_of_the_word_left_the_line_keeps_its_own_words(self):
        out, stats = self._song(("ee", 8.0, 8.22), ("ff", 8.5, 8.7), ("gg", 8.7, 8.9))
        assert out[4]["source"] == SOURCE and stats["n_realigned"] == 0
        ff = next(w for w in out[4]["words"] if w["word"] == "ff")
        assert (ff["start"], ff["end"]) == (8.5, 8.7)
        assert [w["word"] for w in out[4]["words"]] == ["ee", "ff", "gg"]  # the rest guessed

    def test_a_first_word_after_the_previous_lines_end_is_untouched(self):
        out, stats = self._song(("ee", 8.3, 8.5), ("ff", 8.5, 8.7), ("gg", 8.7, 8.9))
        assert out[4]["source"] == SOURCE_REALIGN and stats["n_realigned"] == 1
        assert out[4]["words"][0]["start"] == 8.3


class TestRescueWindow:
    """A line missing words is re-aligned over a window out to where its own singing stops."""

    def _song(self, next_cue: tuple[float, float] | None = None):
        """Four anchors, line 4 ("ee ff gg", cue 8-9) timed only in part, and optionally a
        clean line 5 after it."""
        objs, cues, lines = _anchor_lines(4)
        cues.append((8.0, 9.0))
        lines.append("ee ff gg")
        objs.append(_line(4, "ee ff gg", ("ee", 8.0, 8.3), ("ff", 8.4, 8.8)))
        if next_cue is not None:
            c0, _c1 = next_cue
            cues.append(next_cue)
            lines.append("hh ii")
            objs.append(_line(5, "hh ii", ("hh", c0 + 0.1, c0 + 0.4), ("ii", c0 + 0.5, c0 + 0.9)))
        return objs, cues, lines

    @staticmethod
    def _window(song, env=None, duration=None) -> tuple[float, float]:
        """The ``(w0, w1)`` the re-align of line 4 is handed."""
        calls = []

        def realign(lid, w0, w1):
            calls.append((lid, w0, w1))
            return None

        objs, cues, lines = song
        repace_bad_lines(objs, cues, lines, lines, realign=realign, env=env, duration=duration)
        assert [lid for lid, *_ in calls] == [4]
        return calls[0][1:]

    def test_without_an_envelope_the_window_is_the_cue_padded(self):
        assert self._window(self._song((14.0, 15.0))) == (7.25, 9.75)

    def test_a_hold_into_silence_ends_the_window_a_pad_into_the_silence(self):
        env = _env(16.0, [(8.3, 10.6), (14.2, 15.0)])
        window = self._window(self._song((14.0, 15.0)), env)
        assert window == pytest.approx((7.25, 11.35), abs=0.03)  # the hold's end + the pad

    def test_singing_straight_into_the_next_caption_ends_the_window_at_its_start(self):
        # The 0.2 s breath at 9.8 is no release, so the line sang up to the next cue.
        env = _env(14.0, [(8.3, 9.8), (10.0, 12.0)])
        window = self._window(self._song((10.0, 12.0)), env)
        assert window == pytest.approx((7.25, 10.0), abs=0.03)

    def test_where_singing_stops_is_searched_on_the_audio_clock(self):
        # The audio runs 0.6 s ahead of the captions: the next line's singing starts at
        # 9.4, not at its cue's 10.0, so the window ends there and not inside it.
        objs, cues, lines = self._song((10.0, 12.0))
        anchors, _cues, _lines = _anchor_lines(4, offset=-0.6)
        objs[:4] = anchors
        env = _env(14.0, [(7.7, 9.2), (9.4, 11.4)])
        window = self._window((objs, cues, lines), env)
        assert window == pytest.approx((6.65, 9.4), abs=0.03)

    def test_a_pause_inside_the_held_line_is_not_its_end(self):
        env = _env(16.0, [(8.3, 9.3), (9.8, 10.6), (14.2, 15.0)])  # a 0.5 s pause
        window = self._window(self._song((14.0, 15.0)), env)
        assert window == pytest.approx((7.25, 11.35), abs=0.03)

    def test_a_long_breath_inside_the_line_is_not_its_end(self):
        # Quiet 9.0-10.0 is over RELEASE_QUIET_S, but "gg" is sung after it: the singing
        # stops at 11.0, in the quiet that runs into the next cue.
        env = _env(16.0, [(8.3, 9.0), (10.0, 11.0), (14.2, 15.0)])
        window = self._window(self._song((14.0, 15.0)), env)
        assert window == pytest.approx((7.25, 11.75), abs=0.03)

    def test_a_next_singer_coming_in_early_does_not_take_the_release(self):
        # The next line is sung from 11.7, 0.3 s before its cue: the quiet before it still
        # ends this line, and the window stays out of the next line's singing.
        env = _env(16.0, [(8.3, 10.6), (11.7, 13.0)])
        window = self._window(self._song((12.0, 13.0)), env)
        assert window == pytest.approx((7.25, 11.15), abs=0.03)  # the quiet's midpoint

    def test_a_blip_inside_the_release_does_not_split_it(self):
        env = _env(16.0, [(8.3, 10.6), (11.5, 11.55), (12.0, 13.0)])
        window = self._window(self._song((12.0, 13.0)), env)
        assert window == pytest.approx((7.25, 11.3), abs=0.03)

    def test_a_long_breath_inside_a_line_that_sings_into_the_next_caption(self):
        env = _env(16.0, [(8.3, 9.0), (10.0, 13.0)])
        window = self._window(self._song((12.0, 13.0)), env)
        assert window == pytest.approx((7.25, 12.0), abs=0.03)

    @pytest.mark.parametrize(
        "sung",
        [
            [(8.3, 13.5), (20.2, 21.0)],  # stops 4.5 s past the caption
            [(8.3, 20.0)],  # never stops; the next cue is 11 s on
        ],
    )
    def test_singing_on_past_the_hold_cap_keeps_the_caption_window(self, sung):
        window = self._window(self._song((20.0, 21.0)), _env(22.0, sung))
        assert window == (7.25, 9.75)

    def test_a_line_that_stopped_before_its_caption_ended_keeps_the_caption_window(self):
        env = _env(16.0, [(8.3, 8.6), (14.2, 15.0)])
        assert self._window(self._song((14.0, 15.0)), env) == (7.25, 9.75)

    def test_a_silent_envelope_has_no_singing_to_measure(self):
        assert self._window(self._song((14.0, 15.0)), _env(16.0, [])) == (7.25, 9.75)

    def test_an_envelope_ending_before_the_next_cue_falls_back(self):
        env = _env(10.0, [(8.3, 10.0)])
        assert self._window(self._song((14.0, 15.0)), env) == (7.25, 9.75)

    def test_a_next_line_starting_before_this_one_ends_leaves_nothing_to_measure(self):
        env = _env(14.0, [(8.3, 12.0)])
        assert self._window(self._song((8.2, 12.0)), env) == (7.25, 9.75)

    def test_the_last_line_reaches_a_long_final_hold(self):
        # Past the 4 s hold cap and through a 1.2 s pause: nothing follows to take the audio.
        env = _env(20.0, [(8.3, 12.0), (13.2, 15.0)])
        window = self._window(self._song(), env, duration=20.0)
        assert window == pytest.approx((7.25, 15.75), abs=0.03)

    def test_a_final_hold_to_the_end_of_the_audio_stops_at_the_duration(self):
        env = _env(12.0, [(8.3, 12.0)])
        assert self._window(self._song(), env, duration=12.0) == pytest.approx((7.25, 12.0))

    def test_a_held_tail_inside_the_window_is_kept(self):
        env = _env(16.0, [(8.3, 10.6), (14.2, 15.0)])
        objs, cues, lines = self._song((14.0, 15.0))
        held = _words(("ee", 8.0, 8.3), ("ff", 8.4, 8.8), ("gg", 9.8, 10.6))
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: held, env=env)
        assert out[4]["source"] == SOURCE_REALIGN
        assert [w["word"] for w in out[4]["words"]] == ["ee", "ff", "gg"]
        assert stats["n_realigned"] == 1 and stats["n_guessed_words"] == 0
        assert stats["n_windows"] == 1 and stats["windows_widened_line_ids"] == [4]
        assert stats["windows_unmeasured_line_ids"] == []

    def test_the_same_tail_overruns_the_caption_window_without_an_envelope(self):
        # The check aims at the window the slice was cut to, so only a measured hold passes.
        objs, cues, lines = self._song((14.0, 15.0))
        held = _words(("ee", 8.0, 8.3), ("ff", 8.4, 8.8), ("gg", 9.8, 10.6))
        out, stats = repace_bad_lines(objs, cues, lines, lines, realign=lambda *_: held)
        assert out[4]["source"] == SOURCE
        assert stats["n_realigned"] == 0 and stats["n_guessed_words"] == 1
        assert stats["windows_widened_line_ids"] == [] and stats["windows_unmeasured_line_ids"] == [
            4
        ]


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
        objs, stats, _inputs = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 8.0, aligner)

        assert [o["line_id"] for o in objs] == [0, 1, 2, 3]
        assert all(o["source"] == SOURCE for o in objs)
        assert stats["n_sections"] == 1
        assert stats["resectioned"] is False
        assert stats["repace"]["n_repaced"] == 0
        assert stats["repace"]["n_realigned"] == 0
        # One section pass, no per-line rescue; label names the section.
        assert len(aligner.calls) == 1
        assert "section" in aligner.calls[0][3]
        assert aligner.calls[0][1] == 7.75  # the caption tail

    def test_an_envelope_leaves_the_section_window_on_the_caption(self):
        # The last line is held to 9.0, two seconds past its cue: only a rescue follows it.
        aligner = _stub_aligner(lambda *_: _on_cue_words())
        env = _env(12.0, [(0.0, 9.0)])
        _objs, stats, _inputs = align_song(
            _SONG_CUES, _SONG_LINES, _SONG_LINES, 12.0, aligner, env=env
        )

        assert len(aligner.calls) == 1
        assert aligner.calls[0][1] == 7.75
        assert "edges" not in stats

    def test_a_tail_the_section_align_missed_is_realigned_out_to_the_held_note(self):
        def words_for(t0, t1, text, label):
            if "section" in label:
                return _on_cue_words()[:-1]  # the last line's last word untimed
            return _words(("a", 6.0, 6.4), ("a", 8.5, 9.4))

        aligner = _stub_aligner(words_for)
        env = _env(12.0, [(0.0, 9.0)])
        objs, stats, _inputs = align_song(
            _SONG_CUES, _SONG_LINES, _SONG_LINES, 12.0, aligner, env=env
        )

        # The section ended at its caption (7.75); the line's own window runs out to the
        # note's end plus the pad.
        assert aligner.calls[0][1] == 7.75
        assert aligner.calls[1][:2] == pytest.approx((5.25, 9.75), abs=0.03)
        assert objs[3]["source"] == SOURCE_REALIGN
        assert objs[3]["end"] == pytest.approx(9.4)
        assert stats["repace"]["n_realigned"] == 1

    def test_the_rescues_inputs_come_back_with_the_song(self):
        held = _words(("a", 6.0, 6.4), ("a", 8.5, 9.4))

        def words_for(t0, t1, text, label):
            return _on_cue_words()[:-1] if "section" in label else held

        aligner = _stub_aligner(words_for)
        env = _env(12.0, [(0.0, 9.0)])
        objs, _stats, inputs = align_song(
            _SONG_CUES, _SONG_LINES, _SONG_LINES, 12.0, aligner, env=env
        )

        # The section's lines as they came out of the align: line 3 still a word short.
        assert [o["line_id"] for o in inputs["sections"]] == [0, 1, 2, 3]
        assert [len(o["words"]) for o in inputs["sections"]] == [2, 2, 2, 1]
        assert all(o["source"] == SOURCE for o in inputs["sections"])
        assert objs[3]["source"] == SOURCE_REALIGN and len(objs[3]["words"]) == 2
        (realign,) = inputs["realigns"]
        assert realign["line_id"] == 3
        assert (realign["w0"], realign["w1"]) == aligner.calls[1][:2]
        assert realign["words"] == held

    def test_a_failed_realign_is_recorded_as_none(self):
        aligner = _stub_aligner(lambda *_: None)
        _objs, _stats, inputs = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 8.0, aligner)

        assert [r["line_id"] for r in inputs["realigns"]] == [0, 1, 2, 3]
        assert all(r["words"] is None for r in inputs["realigns"])
        assert [o["words"] for o in inputs["sections"]] == [[], [], [], []]

    def test_the_returned_inputs_are_copies(self):
        held = _words(("a", 6.0, 6.4), ("a", 8.5, 9.4))

        def words_for(t0, t1, text, label):
            return _on_cue_words()[:-1] if "section" in label else held

        aligner = _stub_aligner(words_for)
        env = _env(12.0, [(0.0, 9.0)])
        objs, _stats, inputs = align_song(
            _SONG_CUES, _SONG_LINES, _SONG_LINES, 12.0, aligner, env=env
        )
        objs[0]["words"][0]["start"] = 99.0  # a caller editing its lines must not change the record
        held[0]["start"] = 99.0

        assert inputs["sections"][0]["words"][0]["start"] == 0.0
        assert inputs["realigns"][0]["words"][0]["start"] == 6.0

    def test_large_display_lead_triggers_resection(self):
        # Aligner reports every line ~1.5 s late (> SECTION_PAD_S): the driver
        # re-sections once on offset-shifted cues, after which the words match.
        aligner = _stub_aligner(lambda *_: _on_cue_words(shift=1.5))
        objs, stats, _inputs = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 12.0, aligner)

        assert stats["resectioned"] is True
        assert stats["offset_s"] == pytest.approx(1.5, abs=0.05)
        # Two section passes (initial + re-section), no per-line rescue needed.
        assert len(aligner.calls) == 2
        assert all(o["source"] == SOURCE for o in objs)

    def test_unplaceable_section_repaces_from_cues(self):
        # Aligner can place nothing: every line is rescued by a per-line realign
        # (also None) and then filled from its cue span.
        aligner = _stub_aligner(lambda *_: None)
        objs, stats, _inputs = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, 8.0, aligner)

        assert all(o["source"] == SOURCE_FILL for o in objs)
        assert stats["repace"]["n_repaced"] == 4
        # One section pass + one per-line realign attempt for each of 4 lines.
        assert len(aligner.calls) == 1 + 4
        assert any("line" in c[3] for c in aligner.calls)

    def test_unreadable_duration_still_produces_output(self):
        # duration=None (stem duration unreadable) must not crash; the fill
        # windows simply lose their audio-end clamp.
        aligner = _stub_aligner(lambda *_: None)
        objs, stats, _inputs = align_song(_SONG_CUES, _SONG_LINES, _SONG_LINES, None, aligner)

        assert [o["line_id"] for o in objs] == [0, 1, 2, 3]
        assert all(o["source"] == SOURCE_FILL for o in objs)
