"""LRCLIB gated fill: fill matcher-unplaced lines from LRCLIB cue times (E1).

Implements the E1 = GO verdict of ``plans/lrclib-fill-absence-study.md``
(Phase L4). A song processed on the joint route may have its
matcher-unplaced lines filled at LRCLIB-cue-plus-offset times, gated on
tempo/arrangement consistency between the audio and the LRCLIB variant
(arm A's constant-offset fit + arm B's Theil-Sen slope, used only as a
gate — never to compute a fill time). Fill-only: a placed line is never
moved or removed.

All gate/fill mechanics below are ported verbatim from the study's
measured implementation (``D:/shared/pikaraoke-songs/lrclib_study/
lrclib_study.py``, itself sourced from ``git show
835ba2c7:pikaraoke/lib/cue_align.py`` and ``git show
pathed_align:pikaraoke/lib/srt_prior.py``) — do not redesign, retune, or
"improve" any constant or formula; see
``plans/lrclib-fill-production-wiring.md``.
"""

from __future__ import annotations

import logging
from statistics import median

import numpy as np

from pikaraoke.lib import lrclib, onset_snap
from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.srt_cues import offset_mad_against_cues
from pikaraoke.lib.windowed_realign import analyze_pass1, selected_sources

logger = logging.getLogger(__name__)

# Provenance tag stamped on every fill's line object.
FILL_SOURCE = "lrclib_fill"

# Fill construction caps (srt_prior port): a filled line's per-word pace is
# capped at MAX_FILL_WORD_DUR_S so a wide LRCLIB cue (it infers a line's end
# as the next line's start, so it balloons across instrumental gaps) doesn't
# smear the karaoke sweep into a crawl; MIN_FILL_DUR_S floors a short/zero
# span so a one- or two-word fill is still readable.
MAX_FILL_WORD_DUR_S = 0.7
MIN_FILL_DUR_S = 1.2

# Phase L2 step 3: a fill overlapping a placed line's span by more than this
# is rejected rather than rendered on top of it.
COLLISION_TOL_S = 0.2

# Arm B gate (warp_scaffold_cues port, git show 835ba2c7:pikaraoke/lib/
# cue_align.py): fewer than WARP_MIN_ANCHORS (cue_start, placed_start) pairs,
# or a residual MAD above WARP_MAD_GATE_S, means the slope estimate is not
# trustworthy.
WARP_MIN_ANCHORS = 5
WARP_MAD_GATE_S = 2.0

# GATE L2 adopted gate (Ken, 2026-07-16): a song is fill-eligible iff arm A
# passes AND its arm-B Theil-Sen slope sits within this deviation of unity.
# Separates the eyeballed bad_surviving songs (Best Part Of Me 2.1% dev,
# Seasons of Love 4.2% dev) from the eyeballed-good set (worst case Domino
# at 0.51% dev) -- see plans/lrclib-fill-absence-study.md GATE L2.
FILL_MAX_SLOPE_DEV = 0.01


def _theil_sen(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Robust ``(slope, intercept)`` for ``y ~= slope*x + intercept``.

    Median of pairwise slopes, then median intercept. None if no two points
    differ in ``x``. Source: ``git show 835ba2c7:pikaraoke/lib/cue_align.py``.
    """
    slopes = [
        (points[j][1] - points[i][1]) / (points[j][0] - points[i][0])
        for i in range(len(points))
        for j in range(i + 1, len(points))
        if points[j][0] != points[i][0]
    ]
    if not slopes:
        return None
    slope = median(slopes)
    return slope, median(y - slope * x for x, y in points)


def _fill_line(
    lid: int, text: str, align_line: str, t0: float, t1: float, source: str
) -> dict | None:
    """Line object with even-paced words across ``[t0, t1]``.

    None for display-only lines with no alignable tokens — there is nothing
    to sweep a karaoke cursor over. Source: ``git show
    pathed_align:pikaraoke/lib/srt_prior.py`` (``_fill_line``), ported
    verbatim.
    """
    toks = _tokenise_lines([align_line])[0]
    if not toks:
        return None
    if t1 <= t0:
        t1 = t0 + 0.5
    max_dur = max(MAX_FILL_WORD_DUR_S * len(toks), MIN_FILL_DUR_S)
    if t1 - t0 > max_dur:
        t1 = t0 + max_dur
    step = (t1 - t0) / len(toks)
    words = [
        {"word": raw, "start": t0 + i * step, "end": t0 + (i + 1) * step}
        for i, (_norm, raw) in enumerate(toks)
    ]
    return {
        "line_id": lid,
        "text": text,
        "words": words,
        "start": t0,
        "end": t1,
        "source": source,
    }


def _collision(t0: float, t1: float, placed_spans: list[tuple[float, float]]) -> bool:
    """True when ``[t0, t1]`` overlaps a placed line's span by more than
    :data:`COLLISION_TOL_S`."""
    return any(min(t1, p1) - max(t0, p0) > COLLISION_TOL_S for p0, p1 in placed_spans)


def _energy_check(env: np.ndarray | None, ref: float | None, t0: float, t1: float) -> str:
    """``'PASS' | 'bail' | 'void'`` — is there singing in ``[t0, t1]``?

    Deliberately stricter than ``evidence_veto``'s absolute floor (the fill
    gate asks "is there singing here", the veto asks "is this dead silent")
    — do not unify. Index bounds are clamped: a large negative offset can
    place ``t0`` before the song start, which would otherwise wrap a numpy
    slice from the array's tail instead of raising.
    """
    if env is None or ref is None or ref < onset_snap.MIN_REF_DB:
        return "void"
    lo = max(0, int(t0 / onset_snap.HOP_S))
    hi = max(lo + 1, int(t1 / onset_snap.HOP_S))
    window = env[lo:hi]
    if window.size == 0:
        return "void"
    med = float(np.median(window))
    return "PASS" if med >= max(ref - onset_snap.SOFT_NEAR_DB, onset_snap.MIN_REF_DB) else "bail"


def _slope_fit(anchors: list[dict], cue_spans_by_line: dict[int, tuple[float, float]]) -> dict:
    """Arm B: Theil-Sen tempo+offset fit over the same ``(cue_start,
    placed_start)`` anchor pairs arm A used — a gate only, never used to
    compute a fill time.

    Returns ``{"n_anchors", "bailed", "slope"?, "intercept"?, "mad_s"?}``.
    ``bailed`` is ``"few_anchors"`` (< :data:`WARP_MIN_ANCHORS` pairs),
    ``"degenerate_fit"`` (all x-values identical), ``"wide_spread"``
    (residual MAD > :data:`WARP_MAD_GATE_S`), or ``None`` when trustworthy.
    """
    common = [
        (cue_spans_by_line[a["lid"]][0], a["start"])
        for a in anchors
        if a["lid"] in cue_spans_by_line
    ]
    stats: dict = {"n_anchors": len(common), "bailed": None}
    if len(common) < WARP_MIN_ANCHORS:
        stats["bailed"] = "few_anchors"
        return stats
    fit = _theil_sen(common)
    if fit is None:
        stats["bailed"] = "degenerate_fit"
        return stats
    slope, intercept = fit
    mad = median(abs(y - (slope * x + intercept)) for x, y in common)
    stats["slope"] = round(slope, 4)
    stats["intercept"] = round(intercept, 3)
    stats["mad_s"] = round(mad, 3)
    if mad > WARP_MAD_GATE_S:
        stats["bailed"] = "wide_spread"
    return stats


def _eligibility(arm_a: dict, slope: dict) -> tuple[bool, str | None]:
    """GATE L2 adopted gate: arm-A pass AND arm-B slope within
    :data:`FILL_MAX_SLOPE_DEV` of unity (arm-B bail -> ineligible)."""
    if arm_a["bailed"] is not None:
        return False, "arm_a_bail"
    if slope["bailed"] is not None:
        return False, "slope_bail"
    if abs(slope["slope"] - 1) > FILL_MAX_SLOPE_DEV:
        return False, "slope_dev"
    return True, None


def _stats(
    n_cues_mapped: int,
    arm_a: dict | None,
    slope_fit: dict | None,
    eligible: bool,
    reason: str | None,
    n_candidates: int,
    fills: list[dict],
    filled_lids: list[int],
) -> dict:
    return {
        "n_cues_mapped": n_cues_mapped,
        "arm_a": arm_a,
        "slope_fit": slope_fit,
        "eligible": eligible,
        "reason": reason,
        "n_candidates": n_candidates,
        "fills": fills,
        "filled_lids": filled_lids,
    }


def plan_fills(
    line_objects: list[dict],
    lyrics_lines: list[str],
    align_lines: list[str],
    transcribe_words: list[dict],
    synced_text: str,
    env: np.ndarray | None,
    *,
    margin_s: float,
    max_edit_ratio: float,
) -> tuple[list[dict], dict]:
    """Plan gated LRCLIB fills for a joint-route song's unplaced lines.

    Candidates are lines the matcher left with empty ``words`` whose line id
    maps to an LRCLIB cue. A candidate's fill span is the cue span shifted by
    arm A's constant offset (never arm B's warp). Eligibility, per-candidate
    gates and the returned stats shape are documented in
    ``plans/lrclib-fill-production-wiring.md`` Deliverable 1.

    Returns ``(accepted_fill_objects, stats)``. ``line_objects`` is not
    mutated; the caller splices ``accepted_fill_objects`` in via
    :func:`apply_fills`.
    """
    cue_spans_by_line = lrclib.cue_spans_for_lines(synced_text, lyrics_lines)
    if cue_spans_by_line is None:
        return [], _stats(0, None, None, False, "no_mapping", 0, [], [])

    n_lines = len(lyrics_lines)
    sources = selected_sources(line_objects, n_lines)
    anchors, _suspects, _ratios = analyze_pass1(
        align_lines,
        line_objects,
        {"selected_source": sources},
        transcribe_words,
        margin_s=margin_s,
        max_edit_ratio=max_edit_ratio,
    )
    arm_a = offset_mad_against_cues(anchors, cue_spans_by_line)
    slope = _slope_fit(anchors, cue_spans_by_line)
    n_cues_mapped = len(cue_spans_by_line)

    eligible, reason = _eligibility(arm_a, slope)
    if not eligible:
        return [], _stats(n_cues_mapped, arm_a, slope, False, reason, 0, [], [])

    offset_s = arm_a["offset_s"]
    placed_spans = [
        (o["start"], o["end"])
        for o in line_objects
        if o.get("words") and o.get("start") is not None
    ]
    placed_words = [w for o in line_objects for w in (o.get("words") or [])]
    ref = onset_snap._sung_level_ref(env, placed_words) if env is not None else None

    candidates = sorted(
        o["line_id"]
        for o in line_objects
        if not (o.get("words") or []) and o["line_id"] in cue_spans_by_line
    )

    fills: list[dict] = []
    records: list[dict] = []
    for lid in candidates:
        cue_start, cue_end = cue_spans_by_line[lid]
        t0, t1 = cue_start + offset_s, cue_end + offset_s
        if t0 < 0:
            records.append(
                {
                    "lid": lid,
                    "t0": t0,
                    "t1": t1,
                    "collision": None,
                    "energy": None,
                    "applied": False,
                    "reason": "negative_start",
                }
            )
            continue
        fill_obj = _fill_line(lid, lyrics_lines[lid], align_lines[lid], t0, t1, FILL_SOURCE)
        if fill_obj is None:
            continue
        collision = _collision(fill_obj["start"], fill_obj["end"], placed_spans)
        energy = _energy_check(env, ref, fill_obj["start"], fill_obj["end"])
        applied = (not collision) and energy == "PASS"
        records.append(
            {
                "lid": lid,
                "t0": round(fill_obj["start"], 3),
                "t1": round(fill_obj["end"], 3),
                "collision": collision,
                "energy": energy,
                "applied": applied,
                "reason": None,
            }
        )
        if applied:
            fills.append(fill_obj)

    if fills:
        logger.info("LRCLIB fill: %d/%d candidate line(s) filled", len(fills), len(candidates))
    return fills, _stats(
        n_cues_mapped,
        arm_a,
        slope,
        True,
        None,
        len(candidates),
        records,
        [fo["line_id"] for fo in fills],
    )


def apply_fills(line_objects: list[dict], fills: list[dict]) -> list[dict]:
    """Splice accepted ``fills`` into ``line_objects``, positionally.

    Only replaces a filled lid whose ``words`` are still empty — the
    evidence veto runs between planning and splice, but a veto-demoted lid
    was placed at planning time (never a fill candidate), so this guard is
    defensive, not load-bearing.
    """
    by_lid = {f["line_id"]: f for f in fills}
    return [
        by_lid[obj["line_id"]] if obj["line_id"] in by_lid and not (obj.get("words") or []) else obj
        for obj in line_objects
    ]
