"""Scaffold warp for the line-timing route (closed 2026-09-08, never shipped).

Builds a dense, audio-clock cue list for a song with no uploader SRT: union
the audio anchors (:func:`merge_cue_spans`), then warp a wrong-clock external
line scaffold onto them (:func:`warp_scaffold_cues`) or, failing that, pace the
unanchored lines between anchors (:func:`densify_cue_spans`). The result feeds
the production :func:`pikaraoke.lib.cue_align.align_song`.

Probe-side only: ``scaffold_align_song.py`` drives it (and through it
``scaffold_align_corpus.py``). It lived in ``cue_align`` until the line route
closed (``plans/route-line-timing.md``); the production LRCLIB fill keeps
its own copy of the warp gate (``lrclib_fill``), which this module reuses.
"""

from __future__ import annotations

import logging
from statistics import median

from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.lrclib_fill import WARP_MAD_GATE_S, WARP_MIN_ANCHORS, _theil_sen

logger = logging.getLogger(__name__)

# Default per-token sung pace used by :func:`densify_cue_spans` when no anchored
# line yields a usable estimate (e.g. every anchor is a single word). A relaxed
# singing pace; only the unmapped-line fill leans on it.
DENSIFY_DEFAULT_PACE_S = 0.3

# Floor on an unmapped line's estimated span so a one-token line still gets a
# placeable, non-zero slot before any compression to fit a gap.
DENSIFY_MIN_LINE_DUR_S = 0.5


def densify_cue_spans(
    sparse: dict[int, tuple[float, float]],
    align_lines: list[str],
    duration: float,
    *,
    default_pace_s: float = DENSIFY_DEFAULT_PACE_S,
    min_line_dur_s: float = DENSIFY_MIN_LINE_DUR_S,
) -> list[tuple[float, float]]:
    """Fill a sparse per-line cue dict into the dense list :func:`segment_by_gaps` wants.

    An ASR/transcribe mapping only times the lyric lines it could match
    (``sparse`` keyed by line id); the windowed aligner needs a span for *every*
    line, in order. Each mapped line (an anchor) keeps its span; each run of
    unmapped lines is placed between its bracketing anchors at the song's own
    sung pace -- the median ``span / token-count`` over the anchors -- so a long
    line gets a wider slot than a short one.

    A run whose paced estimate exceeds its gap is compressed to fit (spans stay
    ordered and in-bounds); a run shorter than its gap packs against the earlier
    anchor, leaving the real silence (an instrumental break the ASR also fell
    quiet through) intact for :func:`segment_by_gaps` to split on. Leading lines
    pack back from the first anchor, clamped to 0; trailing lines run forward to
    ``duration``.

    Returns a contiguous ``(start, end)`` list, one span per line. Raises
    ``ValueError`` if ``sparse`` is empty -- there is no clock to anchor to.
    """
    if not sparse:
        raise ValueError("densify_cue_spans: no anchor cues")
    counts = [max(1, len(toks)) for toks in _tokenise_lines(align_lines)]
    # Honor only anchors whose start advances. ASR maps two identical back-to-back
    # lines (a refrain it transcribed once) to the *same* span, so a non-advancing
    # anchor is a duplicate, not a second placement. Demote it to unmapped: the
    # interior fill then pushes the repeat forward into the audio after the first
    # -- where it is actually sung again -- instead of stacking both lines on one
    # occurrence. (cue_spans_for_lines yields starts non-decreasing by line id.)
    anchors: list[int] = []
    for lid in sorted(sparse):
        if not anchors or sparse[lid][0] > sparse[anchors[-1]][0]:
            anchors.append(lid)
    paces = [
        (sparse[lid][1] - sparse[lid][0]) / counts[lid]
        for lid in anchors
        if sparse[lid][1] > sparse[lid][0]
    ]
    pace = median(paces) if paces else default_pace_s
    est = [max(counts[lid] * pace, min_line_dur_s) for lid in range(len(align_lines))]

    spans: list[tuple[float, float]] = [(0.0, 0.0)] * len(align_lines)
    for lid in anchors:
        spans[lid] = sparse[lid]

    def fill(run: range, lo: float, hi: float) -> None:
        ids = list(run)
        if not ids:
            return
        total = sum(est[lid] for lid in ids)
        # ASR anchors only guarantee monotonic starts, so a long anchor can end
        # past the next anchor's start (hi < lo); clamp the gap to 0 there so the
        # run collapses to zero-width spans at lo rather than walking backward.
        scale = min(1.0, max(0.0, hi - lo) / total) if total > 0 else 1.0
        t = lo
        for lid in ids:
            dur = est[lid] * scale
            spans[lid] = (t, t + dur)
            t += dur

    first, last = anchors[0], anchors[-1]
    lead_total = sum(est[lid] for lid in range(first))
    fill(range(first), max(0.0, sparse[first][0] - lead_total), sparse[first][0])
    for a, b in zip(anchors, anchors[1:]):
        fill(range(a + 1, b), sparse[a][1], sparse[b][0])
    fill(range(last + 1, len(align_lines)), sparse[last][1], duration)
    return spans


def merge_cue_spans(
    primary: dict[int, tuple[float, float]],
    secondary: dict[int, tuple[float, float]],
) -> dict[int, tuple[float, float]]:
    """Union of two per-line cue dicts; ``primary`` wins where both place a line.

    Combines two same-clock anchor sources (e.g. whisper-transcribe as
    ``primary``, YouTube ASR as ``secondary``): each contributes the lines it
    placed, so coverage is their union, and the more-trusted source wins a
    conflict. Where both place a line they agree to ~0.2 s in practice, so the
    tie-break rarely matters.
    """
    return {
        lid: primary.get(lid) or secondary.get(lid) for lid in primary.keys() | secondary.keys()
    }


def warp_scaffold_cues(
    anchors: dict[int, tuple[float, float]],
    scaffold: dict[int, tuple[float, float]],
    align_lines: list[str],
    duration: float,
    *,
    default_pace_s: float = DENSIFY_DEFAULT_PACE_S,
    min_line_dur_s: float = DENSIFY_MIN_LINE_DUR_S,
    mad_gate: float = WARP_MAD_GATE_S,
) -> list[tuple[float, float]]:
    """Dense audio-clock cues from a wrong-clock ``scaffold`` warped onto ``anchors``.

    ``scaffold`` is a dense, correctly-ordered external cue source (LRCLIB) whose
    *relative* structure is sound but whose absolute clock differs (a different
    master): only its per-line start is trusted. ``anchors`` are audio-clock cues
    (ASR/transcribe). A robust tempo+offset is fit (:func:`_theil_sen`) from the
    lines both place; if its residual MAD exceeds ``mad_gate`` (a structurally
    different recording) or fewer than :data:`WARP_MIN_ANCHORS` lines overlap, the
    scaffold is unusable and we fall back to :func:`densify_cue_spans` on the
    anchors alone.

    Otherwise every scaffold line is warped onto the audio clock; lines only the
    anchors place keep their cue; lines neither places are interpolated between
    placed neighbours. Each line's end is paced (capped at the next start, never
    past ``duration``) so the silences :func:`segment_by_gaps` splits on survive
    -- the scaffold's own ends are just the next line's start and carry no
    duration.

    A handful of mis-mapped common points (a fuzzy anchor matched onto the wrong
    occurrence of a repeated lyric line) can contaminate enough of Theil-Sen's
    pairwise slopes to fail the affine fit even when the true relationship is a
    constant offset (e.g. a video with concert footage prepended to the studio
    track). When the affine path fails, a fixed-slope offset model --
    ``offset = median(anchor_start - scaffold_start)`` over the same common
    lines -- is tried as a rescue, accepted under the same ``mad_gate``; this
    reuses the existing constants and adds no new threshold.

    Returns a contiguous, monotonic ``(start, end)`` list, one span per line.
    """
    if not scaffold:
        logger.info("cue-align: warp path=densify-fallback (no scaffold)")
        return densify_cue_spans(anchors, align_lines, duration)
    common = [(scaffold[lid][0], anchors[lid][0]) for lid in scaffold if lid in anchors]
    fit = _theil_sen(common) if len(common) >= WARP_MIN_ANCHORS else None
    affine_ok = (
        fit is not None and median(abs(y - (fit[0] * x + fit[1])) for x, y in common) <= mad_gate
    )
    if affine_ok:
        slope, intercept = fit
        logger.info("cue-align: warp path=affine-ok (slope=%.4f, intercept=%.3f)", slope, intercept)
    else:
        offset = median(y - x for x, y in common) if len(common) >= WARP_MIN_ANCHORS else None
        offset_ok = (
            offset is not None and median(abs(y - (x + offset)) for x, y in common) <= mad_gate
        )
        if offset_ok:
            slope, intercept = 1.0, offset
            logger.info("cue-align: warp path=offset-rescue (offset=%.3f)", offset)
        else:
            logger.info("cue-align: warp path=densify-fallback")
            return densify_cue_spans(anchors, align_lines, duration)

    n = len(align_lines)
    counts = [max(1, len(toks)) for toks in _tokenise_lines(align_lines)]
    paces = [
        (anchors[lid][1] - anchors[lid][0]) / counts[lid]
        for lid in anchors
        if anchors[lid][1] > anchors[lid][0]
    ]
    pace = median(paces) if paces else default_pace_s
    est = [max(counts[lid] * pace, min_line_dur_s) for lid in range(n)]

    starts: list[float | None] = [None] * n
    for lid in range(n):
        if lid in scaffold:
            starts[lid] = min(max(0.0, slope * scaffold[lid][0] + intercept), duration)
        elif lid in anchors:
            starts[lid] = min(max(0.0, anchors[lid][0]), duration)

    placed = [lid for lid in range(n) if starts[lid] is not None]
    if not placed:
        return densify_cue_spans(anchors, align_lines, duration)

    def interp(ids: list[int], lo: float, hi: float) -> None:
        step = (hi - lo) / (len(ids) + 1)
        for k, lid in enumerate(ids, 1):
            starts[lid] = lo + k * step

    first, last = placed[0], placed[-1]
    interp(
        list(range(first)),
        max(0.0, starts[first] - sum(est[lid] for lid in range(first))),
        starts[first],
    )
    for a, b in zip(placed, placed[1:]):
        interp(list(range(a + 1, b)), starts[a], starts[b])
    interp(list(range(last + 1, n)), starts[last], duration)

    for lid in range(1, n):
        starts[lid] = max(starts[lid], starts[lid - 1])
    out: list[tuple[float, float]] = []
    for lid in range(n):
        nxt = starts[lid + 1] if lid + 1 < n else duration
        out.append((starts[lid], min(starts[lid] + est[lid], max(starts[lid], nxt))))
    return out
