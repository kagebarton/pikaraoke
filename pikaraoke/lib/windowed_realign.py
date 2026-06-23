"""Windowed re-align: second-pass repair for the joint matcher.

After the joint DP places lines (pass 1), lines it placed with strong
transcribe corroboration pin "anchor" points. The audio between
consecutive anchors is re-aligned in isolation — the slice plus only
that span's lyric lines go back through stable-ts align — and the joint
matcher re-runs on each span as a sub-problem. Interior lines merge
back under a conservative policy:

* Only spans whose interior contains a *suspect* pass-1 line (unplaced,
  interpolated, or weakly corroborated) are re-aligned at all. This is
  both the quality gate and the GPU cost gate (~40% of spans on the
  eval corpus).
* A line pass-1 left unplaced is only newly placed when the span replay
  selected it from the transcribe stream — independent corroboration.
  Pass-1 placements may always be replaced or dropped; un-placing an
  uncorroborated line is honest (hidden beats 20-seconds-wrong).

Corpus-measured (Phase 3, 23 songs):
gross misplacements 77 -> 58, lines within 1.0 s 84.5% -> 85.7%.

This module is pure logic: anchor/suspect analysis, span construction,
span replay, and merge. Audio slicing and the stable-ts calls live in
the lyric_align stage, which feeds the slice's refined words back in
absolute song time.
"""

from collections import Counter

from pikaraoke.lib.joint_match import (
    _interpolate_missing,
    _tokenise_lines,
    _transcribe_match_and_count_in_window,
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.token_align import _normalize_token

# Anchor criteria: placed by align/transcribe, lyric-sheet-unique token
# sequence of at least this many tokens, transcribe corroboration at or
# above this ratio. Corpus diagnostic: 19 gross / 616 anchors; the span
# structure + careful merge absorb the residue, so no stricter filter.
ANCHOR_MIN_TOKENS = 4
ANCHOR_MIN_RATIO = 0.75

# Pass-1 corroboration below this marks a line suspect (span gate).
SUSPECT_RATIO = 0.5

# Audio slack around a span's anchor boundaries when slicing.
SLICE_PAD_S = 0.75

# Transcribe words this far outside the span window still participate
# in the span replay (anchor-edge lines straddle the boundary).
TRANSCRIBE_PAD_S = 2.0

# Adopted interior placements may intrude at most this far into an edge
# anchor's pass-1 window. Adjacent sung lines legitimately overlap a
# little (backing vocals); anything deeper means the span replay
# disagreed with an anchor we chose to keep, so its opinion on that
# line is distrusted.
MERGE_EDGE_TOL_S = 0.5


def analyze_pass1(
    align_lines: list[str],
    line_objects: list[dict],
    stats: dict,
    transcribe_words: list[dict],
    *,
    margin_s: float,
    max_edit_ratio: float,
) -> tuple[list[dict], set[int]]:
    """Classify pass-1 lines into span anchors and suspects.

    Returns ``(anchors, suspect_line_ids)``. Anchors are dicts with
    ``lid``/``start``/``end``, in line order. Display-only lines with no
    normalizable tokens are neither anchors nor suspects — they inherit
    timing and carry no evidence.
    """
    toks = _tokenise_lines(align_lines)
    norm_seqs = [tuple(norm for norm, _raw in t) for t in toks]
    seq_count = Counter(seq for seq in norm_seqs if seq)
    t_norms = [_normalize_token(w["word"]) for w in transcribe_words]
    t_starts = [w["start"] for w in transcribe_words]
    obj_by_id = {o["line_id"]: o for o in line_objects}

    anchors: list[dict] = []
    suspects: set[int] = set()
    for lid, src in enumerate(stats["selected_source"]):
        seq = norm_seqs[lid]
        if not seq:
            continue
        obj = obj_by_id[lid]
        if src not in ("align", "transcribe") or obj.get("start") is None:
            suspects.add(lid)
            continue
        matched, _, _ = _transcribe_match_and_count_in_window(
            list(seq),
            t_norms,
            t_starts,
            obj["start"],
            obj["end"],
            margin_s,
            max_edit_ratio,
        )
        ratio = matched / len(seq)
        if ratio < SUSPECT_RATIO:
            suspects.add(lid)
        if len(seq) >= ANCHOR_MIN_TOKENS and seq_count[seq] == 1 and ratio >= ANCHOR_MIN_RATIO:
            anchors.append({"lid": lid, "start": obj["start"], "end": obj["end"]})
    return anchors, suspects


def build_spans(
    anchors: list[dict],
    n_lines: int,
    duration: float,
    *,
    pad_s: float = SLICE_PAD_S,
) -> list[dict]:
    """Anchor-to-anchor spans, including virtual song-start/end edges.

    Span lines run edge-anchor to edge-anchor inclusive so the anchors
    give the sub-align context; only interior lines merge back. Spans
    with no interior lines are skipped.
    """
    edges: list[dict] = (
        [{"lid": -1, "start": 0.0, "end": 0.0}]
        + anchors
        + [{"lid": n_lines, "start": duration, "end": duration}]
    )
    spans = []
    for lo_edge, hi_edge in zip(edges, edges[1:]):
        if hi_edge["lid"] - lo_edge["lid"] < 2:
            continue
        t0 = max(0.0, (lo_edge["start"] if lo_edge["lid"] >= 0 else 0.0) - pad_s)
        t1 = min(duration, (hi_edge["end"] if hi_edge["lid"] < n_lines else duration) + pad_s)
        spans.append(
            {
                "lid_lo": max(lo_edge["lid"], 0),
                "lid_hi": min(hi_edge["lid"], n_lines - 1),
                "anchor_lo": lo_edge["lid"] if lo_edge["lid"] >= 0 else None,
                "anchor_hi": hi_edge["lid"] if hi_edge["lid"] < n_lines else None,
                "t0": t0,
                "t1": t1,
            }
        )
    return spans


def interior_range(span: dict) -> tuple[int, int]:
    """Inclusive line-id range a span may rewrite (edge anchors excluded)."""
    lo = span["lid_lo"] if span["anchor_lo"] is None else span["anchor_lo"] + 1
    hi = span["lid_hi"] if span["anchor_hi"] is None else span["anchor_hi"] - 1
    return lo, hi


def span_needs_realign(span: dict, suspects: set[int]) -> bool:
    """True when the span's interior contains a suspect pass-1 line."""
    lo, hi = interior_range(span)
    return any(lid in suspects for lid in range(lo, hi + 1))


def span_align_lines(span: dict, align_lines: list[str]) -> list[str] | None:
    """The span's lyric lines for the slice align; None if nothing alignable."""
    sub = align_lines[span["lid_lo"] : span["lid_hi"] + 1]
    if not any(_tokenise_lines(sub)):
        return None
    return sub


def replay_span(
    span: dict,
    span_words: list[dict],
    transcribe_words: list[dict],
    lines: list[str],
    align_lines: list[str],
    *,
    alpha: float,
    margin_s: float,
    max_edit_ratio: float,
) -> tuple[dict[int, dict], dict[int, str]] | None:
    """Joint-match one span as a sub-problem.

    ``span_words`` are the slice's refined align words shifted to
    absolute song time. Returns ``(placed, sources)`` keyed by absolute
    line id — ``placed`` maps to full line objects ready to merge — or
    None when the slice align produced no words.
    """
    if not span_words:
        return None
    lo, hi = span["lid_lo"], span["lid_hi"]
    window_words = [
        w
        for w in transcribe_words
        if span["t0"] - TRANSCRIBE_PAD_S <= w["start"] <= span["t1"] + TRANSCRIBE_PAD_S
    ]
    local_objects, local_stats = match_words_to_lines_joint_with_stats(
        span_words,
        window_words,
        lines[lo : hi + 1],
        align_lines[lo : hi + 1],
        alpha=alpha,
        margin_s=margin_s,
        max_edit_ratio=max_edit_ratio,
    )
    placed: dict[int, dict] = {}
    for obj in local_objects:
        if obj.get("words") and obj.get("start") is not None:
            shifted = dict(obj)
            shifted["line_id"] = lo + obj["line_id"]
            placed[shifted["line_id"]] = shifted
    sources = {lo + k: src for k, src in enumerate(local_stats["selected_source"])}
    return placed, sources


def merge_spans(
    line_objects: list[dict],
    spans: list[dict],
    span_results: list[tuple[dict[int, dict], dict[int, str]] | None],
    n_lines: int,
    align_words: list[dict],
) -> list[dict]:
    """Apply span replays' interior placements over pass-1.

    ``spans``/``span_results`` are parallel; a None result (slice align
    failed or yielded nothing) keeps pass-1 for that span. Unplaced
    lines are re-interpolated against the merged neighbours, restoring
    the matcher's 1:1 line-object contract.
    """
    placed1 = {
        o["line_id"]: o for o in line_objects if o.get("words") and o.get("start") is not None
    }
    merged = dict(placed1)
    for span, result in zip(spans, span_results):
        if result is None:
            continue
        placed2, sources2 = result
        lo, hi = interior_range(span)
        lo_obj = placed1.get(span["anchor_lo"]) if span["anchor_lo"] is not None else None
        hi_obj = placed1.get(span["anchor_hi"]) if span["anchor_hi"] is not None else None
        lo_t = lo_obj["end"] - MERGE_EDGE_TOL_S if lo_obj else float("-inf")
        hi_t = hi_obj["start"] + MERGE_EDGE_TOL_S if hi_obj else float("inf")
        for lid in range(lo, hi + 1):
            if lid not in placed1 and sources2.get(lid) != "transcribe":
                continue
            cand = placed2.get(lid)
            if cand is not None and not (lo_t <= cand["start"] and cand["end"] <= hi_t):
                continue  # intrudes into a kept edge anchor: keep pass-1
            merged.pop(lid, None)
            if cand is not None:
                merged[lid] = cand
    return _interpolate_missing(list(merged.values()), n_lines, align_words)
