"""Cue-anchored windowed alignment: word timings from trusted SRT line cues.

The production path for SRT songs (the joint matcher handles txt/genius).
The SRT already solves the matcher's job -- line -> time, 1:1 -- so this path
never places lines from audio. It only derives per-word timing *within* the
trusted cue structure, which makes the global-placement artifacts (candidate
straddle, repeat pile-up, slow-crawl) structurally impossible rather than
something to patch.

Pipeline-agnostic by design: every function here is pure. :func:`align_song`
is the driver, but all GPU/ffmpeg I/O is injected as its ``slice_align``
callable, so the caller owns the audio. ``LyricAlignStage`` routes SRT songs
here, injecting its forced aligner; the module emits the same ``line_objects``
shape the existing ASS/SRT generators consume.

Approach:

1. Group consecutive cues into *sections* split at real phrase gaps
   (:func:`segment_by_gaps`), so every section boundary falls in silence.
   Aligning a contiguous phrase as one slice means forced alignment never
   clips a sung word at a slice edge and never bleeds one line's words onto a
   neighbour's audio -- both are window-edge faults that vanish when the edges
   sit in silence.
2. Force-align each section's joined text once (driver), then split the
   returned words back to lines (:func:`split_section_to_lines`). The aligner
   drops words it could not time (``remove_instant_words``), so the split is a
   monotone assignment (:func:`_match_words_to_tokens`): maximise matched
   words, break ties by closeness to each token's cue-expected time. Text
   equality alone would let one unmatchable word stall the scan and let a
   dropped repeated line steal its twin's words; the time tiebreak uses the
   trusted cue structure to prevent both.
3. Rescue the lines the align could not cover (:func:`repace_bad_lines`): the
   per-song display lead is fit from the cleanly-aligned lines
   (:func:`fit_offset`), each bad line gets one narrow per-line align attempt
   over its offset-corrected cue window (the injected ``realign``), and only
   if that also fails is it re-built with paced words across the window. Only
   already-bad lines are touched, so a sloppy offset never degrades a good
   one. The driver also re-sections the whole song on offset-shifted cues
   when the fitted lead exceeds the slice pad -- past that, every section
   window provably clips its leading words.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from statistics import median

from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.token_align import _normalize_token, match_words_to_tokens

logger = logging.getLogger(__name__)

# Silent gap to the next cue, above which a section boundary is cut. Karaoke
# lines run back-to-back (<0.5 s apart); a breath/phrase gap is ~1-2 s. Cutting
# here puts every section edge in silence, so the slice never bisects a sung
# word.
SECTION_GAP_S = 1.5

# How far a section's slice extends into the flanking silence so the first/last
# sung word is never clipped. Clamped to the gap midpoint (below) so adjacent
# sections never claim the same audio.
SECTION_PAD_S = 0.75

# A section's raw cue-to-cue span (before padding) is capped to this. Most
# songs' gaps already fall under SECTION_GAP_S, but some SRTs caption
# continuously with no gap at all (Phase 5a corpus survey: 2/16 SRT songs
# collapse to one 170-220 s section) -- an oversized single slice is the same
# whole-song-drift risk segment_by_gaps exists to prevent, just triggered by
# dense authoring instead of a missing gap. A section over the cap is split at
# its widest internal gap even though that gap is by definition under
# SECTION_GAP_S: a boundary outside true silence still beats none, and the
# pad/clamp/repace machinery already bounds the damage from an imperfect one.
MAX_SECTION_DUR_S = 60.0

# A single aligned word's sweep is capped to this, anchored at its start, so a
# held note or a mis-stretched edge word cannot crawl. Set above the legit slow
# line band (corpus crawls are >=1.9 s/word, legit lines <=1.3 s/word -- see
# plans/alignment-crawl-overlap-fixes.md) and well under the ~1.3 s crawl
# perception threshold's safety margin, so real durations pass through.
MAX_WORD_DUR_S = 1.5

# A line whose aligned words cover less than this fraction of its tokens is
# treated as not placed by the align and handed to the cue re-pace fallback.
MIN_LINE_COVERAGE = 0.5

# An internal silent gap wider than this between two consecutive words of one
# line is the forced-align drift signature (the aligner lost sync mid-section
# and parked the rest). Such a line is re-paced from its cue. Set tighter than
# the driver's report flag (3 s) so drift is repaired before it is report-worthy
# and well above any legitimate within-line breath.
DRIFT_GAP_S = 2.0

# A word shorter than this is a failed forced-alignment the aligner could not
# place but did not drop (only exact-zero-duration words are removed). A line
# that is mostly these has a broken sweep and is re-paced from its cue.
INSTANT_WORD_DUR_S = 0.05
MAX_INSTANT_FRACTION = 0.5

# Fewer cleanly-aligned lines than this and the per-song display-lead median is
# not robust; fall back to a zero offset (raw cue times -- an uploader SRT's
# lead is small, so re-pacing on raw cues still beats leaving a line drifted).
CUE_MIN_ANCHORS = 4

# A wide internal word-gap is exonerated (a legit long mid-line pause, not
# drift) only when the whole line still sits inside its offset-corrected cue
# span, within this slack. Kept under SECTION_PAD_S so a tail parked at a
# slice edge (cue end + pad) is never mistaken for a covered pause.
PAUSE_SLACK_S = 0.5

# Default per-token sung pace used by :func:`densify_cue_spans` when no anchored
# line yields a usable estimate (e.g. every anchor is a single word). A relaxed
# singing pace; only the unmapped-line fill leans on it.
DENSIFY_DEFAULT_PACE_S = 0.3

# Floor on an unmapped line's estimated span so a one-token line still gets a
# placeable, non-zero slot before any compression to fit a gap.
DENSIFY_MIN_LINE_DUR_S = 0.5

# A dense external scaffold (LRCLIB) warps onto the audio anchors above this
# anchor-residual MAD only when it is a structurally different recording (a
# different master/edit with extra repeats); fall back to the anchors alone
# there. Sub-second on every cleanly-warping song in the corpus.
WARP_MAD_GATE_S = 2.0

# Fewer lines shared between scaffold and anchors than this and the tempo+offset
# fit is not robust; fall back to the anchors alone.
WARP_MIN_ANCHORS = 5

SOURCE = "cue_align"
# Provenance for a line whose timing came from the cue re-pace fallback rather
# than the audio align (mirrors the SRT prior's "filled" tag).
SOURCE_FILL = "cue_align_fill"
# Provenance for a bad line recovered by a narrow per-line re-align over its
# offset-corrected cue window -- real audio timing, unlike SOURCE_FILL.
SOURCE_REALIGN = "cue_align_line"


@dataclass(frozen=True)
class Section:
    """A contiguous run of lines plus the audio window to align them in.

    ``lid_lo``/``lid_hi`` are inclusive line ids; ``t0``/``t1`` is the slice
    window in seconds (already padded into the flanking silence).
    """

    lid_lo: int
    lid_hi: int
    t0: float
    t1: float

    @property
    def line_ids(self) -> range:
        return range(self.lid_lo, self.lid_hi + 1)


def _widest_internal_gap(lo: int, hi: int, cue_spans: list[tuple[float, float]]) -> int:
    """Index ``i`` (``lo <= i < hi``) of the widest gap between cues ``i``/``i+1``.

    The caller has already established this section needs a split; ties break
    toward the gap nearest the section's time midpoint, for the most even cut.
    Gaps can be negative (stacked duet cues overlap, to about -5 s in this
    corpus), so the argmax runs over the raw values with no sentinel floor.
    """
    mid = (cue_spans[lo][0] + cue_spans[hi][1]) / 2
    return max(
        range(lo, hi),
        key=lambda i: (
            cue_spans[i + 1][0] - cue_spans[i][1],
            -abs((cue_spans[i][1] + cue_spans[i + 1][0]) / 2 - mid),
        ),
    )


def _split_oversized(
    lo: int, hi: int, cue_spans: list[tuple[float, float]], max_dur_s: float
) -> list[int]:
    """Line ids that must start a new section to keep every raw span under ``max_dur_s``.

    Recurses on both halves after each cut -- an uneven split can still leave
    one side oversized. A single-line section (``lo == hi``) is left alone
    regardless of its own duration; there is nothing left to split.
    """
    if hi == lo or cue_spans[hi][1] - cue_spans[lo][0] <= max_dur_s:
        return []
    split = _widest_internal_gap(lo, hi, cue_spans)
    return (
        _split_oversized(lo, split, cue_spans, max_dur_s)
        + [split + 1]
        + _split_oversized(split + 1, hi, cue_spans, max_dur_s)
    )


def segment_by_gaps(
    cue_spans: list[tuple[float, float]],
    *,
    gap_s: float = SECTION_GAP_S,
    pad_s: float = SECTION_PAD_S,
    duration: float | None = None,
) -> list[Section]:
    """Group 1:1 cue spans into sections split at phrase gaps.

    ``cue_spans`` is the per-line ``(start, end)`` list in line order. The
    spans need not be offset-corrected -- only the *relative* gaps between
    consecutive cues drive the split, and those survive an unknown constant
    display lead. A boundary is cut wherever the silent gap to the next cue
    exceeds ``gap_s``; a section still longer than :data:`MAX_SECTION_DUR_S`
    after that (a densely-captioned run with no qualifying gap) is further
    split at its widest internal gap, recursively, via :func:`_split_oversized`.

    Each section's window extends ``pad_s`` into the flanking silence, clamped
    to the gap midpoint (so neighbouring sections never overlap-claim silent
    audio) and to ``[0, duration]`` when ``duration`` is known. A cap split can
    land inside cue overlap (negative gap) where there is no silence to share:
    each window then keeps its own cues' full span, unpadded.
    """
    if not cue_spans:
        return []
    n = len(cue_spans)
    # Line ids that start a new section: 0, plus every line after a wide gap.
    starts = [0] + [i + 1 for i in range(n - 1) if cue_spans[i + 1][0] - cue_spans[i][1] > gap_s]
    bounds = starts + [n]
    split_starts = [
        s
        for lo, nxt in zip(bounds, bounds[1:])
        for s in _split_oversized(lo, nxt - 1, cue_spans, MAX_SECTION_DUR_S)
    ]
    if split_starts:
        # Split points are strictly interior to their section, so the lists
        # are disjoint; sorting interleaves them into the boundary order.
        starts = sorted(starts + split_starts)
        bounds = starts + [n]
    sections: list[Section] = []
    for lo, nxt in zip(bounds, bounds[1:]):
        hi = nxt - 1
        start = cue_spans[lo][0]
        end = cue_spans[hi][1]
        if lo == 0:
            t0 = max(0.0, start - pad_s)
        else:
            # Share the preceding gap with the previous section at its
            # midpoint; a negative gap (cap split inside cue overlap) pads
            # zero rather than inverting into the boundary line's audio.
            t0 = start - min(pad_s, max(0.0, (start - cue_spans[lo - 1][1]) / 2))
        if hi == n - 1:
            t1 = end + pad_s
            if duration is not None:
                t1 = min(duration, t1)
        else:
            t1 = end + min(pad_s, max(0.0, (cue_spans[hi + 1][0] - end) / 2))
        sections.append(Section(lo, hi, round(max(0.0, t0), 3), round(t1, 3)))
    return sections


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


def _theil_sen(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Robust ``(slope, intercept)`` for ``y ~= slope*x + intercept``.

    Median of pairwise slopes, then median intercept -- tolerates the handful of
    mis-mapped points a fuzzy anchor set carries. None if no two points differ
    in ``x``.
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


def _token_expected_times(n: int, t0: float, t1: float) -> list[float]:
    """Even-paced expected start for each of ``n`` tokens across ``[t0, t1]``."""
    return [t0 + (k + 0.5) * (t1 - t0) / n for k in range(n)]


def _match_words_to_tokens(
    token_norms: list[str],
    token_times: list[float],
    aligned_words: list[dict],
) -> list[int | None]:
    """Adapter: unpack aligned-word dicts for the shared assignment DP.

    See :func:`token_align.match_words_to_tokens` for the contract. Here the
    expected times are cue-derived, so the deviation tiebreak arbitrates
    repeats on the trusted cue structure; a constant display lead shifts
    every deviation equally and cannot flip a correct assignment.
    """
    return match_words_to_tokens(
        token_norms,
        token_times,
        [_normalize_token(w["word"]) for w in aligned_words],
        [w["start"] for w in aligned_words],
    )


def split_section_to_lines(
    section: Section,
    aligned_words: list[dict],
    display_lines: list[str],
    align_lines: list[str],
    cue_spans: list[tuple[float, float]],
    *,
    max_word_dur: float = MAX_WORD_DUR_S,
    min_coverage: float = MIN_LINE_COVERAGE,
) -> list[dict]:
    """Map a section's aligned words back to its individual lines.

    ``aligned_words`` are the section slice's forced-align words in *absolute
    song time*, in order. The aligner drops words it could not time, so the
    stream is a subsequence of the section's lyric tokens, not a 1:1 list.
    Words are assigned to tokens by :func:`_match_words_to_tokens`, with each
    token's expected time paced across its line's cue span -- the cue
    structure arbitrates which twin a repeated word belongs to.

    Each kept word's sweep is capped to ``max_word_dur`` (anchored at its
    start). A line whose covered-token fraction falls below ``min_coverage`` is
    emitted with no words -- left for :func:`repace_bad_lines` to fill from the
    cue rather than rendered from too little timing.

    Returns one line object per section line, in line order, in the canonical
    ``line_objects`` shape (``words=[]`` and ``start/end=None`` for a line with
    no usable timing).
    """
    line_toks = _tokenise_lines([align_lines[lid] for lid in section.line_ids])
    token_norms: list[str] = []
    token_raws: list[str] = []
    token_times: list[float] = []
    for toks, lid in zip(line_toks, section.line_ids):
        c0, c1 = cue_spans[lid]
        expected = _token_expected_times(len(toks), c0, c1)
        for (norm, raw), t in zip(toks, expected):
            token_norms.append(norm)
            token_raws.append(raw)
            token_times.append(t)
    assign = _match_words_to_tokens(token_norms, token_times, aligned_words)
    out: list[dict] = []
    ti = 0
    for toks, lid in zip(line_toks, section.line_ids):
        n = len(toks)
        words: list[dict] = []
        for _ in toks:
            wi = assign[ti]
            if wi is not None:
                w = aligned_words[wi]
                words.append(
                    {
                        "word": token_raws[ti],
                        "start": w["start"],
                        "end": min(w["end"], w["start"] + max_word_dur),
                    }
                )
            ti += 1
        if n and len(words) / n < min_coverage:
            words = []
        out.append(_line_object(lid, display_lines[lid], words))
    return out


def repace_bad_lines(
    line_objects: list[dict],
    cue_spans: list[tuple[float, float]],
    display_lines: list[str],
    align_lines: list[str],
    *,
    drift_gap_s: float = DRIFT_GAP_S,
    min_anchors: int = CUE_MIN_ANCHORS,
    max_word_dur: float = MAX_WORD_DUR_S,
    duration: float | None = None,
    realign: Callable[[int, float, float], list[dict] | None] | None = None,
) -> tuple[list[dict], dict]:
    """Rescue the lines the align could not place, from their cue spans.

    A line is *bad* if it has no usable words (under-covered), is mostly
    instant words, or holds an internal word-gap over ``drift_gap_s`` while
    overrunning its offset-corrected cue span (a wide gap *inside* the span is
    a caption-covered pause, not drift -- see :func:`_line_is_good`). Lines in
    a run of identical text skip that clean-trust: a repeat displaced onto a
    neighbouring occurrence comes back internally clean, so detection demands
    containment there, with slack widened to half the repeat period
    (:func:`_repeat_detection_slacks`). The display-lead offset comes from
    :func:`fit_offset` over the clean lines.

    Each bad line is rescued in two steps: ``realign(lid, t0, t1)`` -- an
    injected narrow per-line forced align over the offset-corrected window,
    returning absolute-time words or None -- is tried first, and its result is
    kept only if it comes back covered and *inside the window it was aimed
    at* (:func:`_line_in_span`; tagged :data:`SOURCE_REALIGN`). Otherwise the line is rebuilt with paced words
    across the window (tagged :data:`SOURCE_FILL`), clamped to ``duration``
    when known. Because only bad lines are rewritten, a coarse offset can
    never degrade a well-aligned line.

    Returns ``(line_objects, stats)``. ``cue_spans`` is indexed by ``line_id``.
    """
    offset = fit_offset(
        line_objects, cue_spans, align_lines, drift_gap_s=drift_gap_s, min_anchors=min_anchors
    )
    line_toks = _tokenise_lines(align_lines)
    repeat_slacks = _repeat_detection_slacks(line_toks, cue_spans)
    out: list[dict] = []
    repaced: list[int] = []
    realigned: list[int] = []
    for obj in line_objects:
        lid = obj["line_id"]
        if lid >= len(cue_spans):
            out.append(obj)
            continue
        if lid in repeat_slacks:
            good = _line_in_span(obj, cue_spans[lid], offset, slack=repeat_slacks[lid])
        else:
            good = _line_is_good(obj, cue_spans[lid], offset, drift_gap_s)
        if good:
            out.append(obj)
            continue
        toks = line_toks[lid]
        if not toks:  # display-only line (no alignable tokens)
            out.append(obj)
            continue
        cue_start, cue_end = cue_spans[lid]
        t0 = max(0.0, cue_start + offset)
        t1 = cue_end + offset
        if duration is not None and t1 > duration:
            # SRT overruns the media: keep the fill inside the audio, pinning
            # a cue that starts past the end to the last half-second.
            t1 = duration
            if t0 >= t1:
                t0 = max(0.0, t1 - 0.5)
        if realign is not None:
            raw_words = realign(lid, t0, t1)
            fixed = (
                _line_from_realigned(lid, display_lines[lid], toks, t0, t1, raw_words, max_word_dur)
                if raw_words
                else None
            )
            if fixed is not None and _line_in_span(fixed, cue_spans[lid], offset):
                out.append(fixed)
                realigned.append(lid)
                continue
        out.append(_repace_line(lid, display_lines[lid], toks, t0, t1, max_word_dur))
        repaced.append(lid)
    stats = {
        "offset_s": round(offset, 3),
        "n_repaced": len(repaced),
        "repaced_line_ids": repaced,
        "n_realigned": len(realigned),
        "realigned_line_ids": realigned,
    }
    logger.info(
        "cue rescue: offset=%+.2fs, %d line(s) re-aligned, %d/%d re-paced from cue",
        offset,
        len(realigned),
        len(repaced),
        len(line_objects),
    )
    return out, stats


def _instant_fraction(words: list[dict]) -> float:
    """Fraction of words the aligner emitted as near-zero-duration sweeps."""
    return sum(1 for w in words if w["end"] - w["start"] < INSTANT_WORD_DUR_S) / len(words)


def _line_is_clean(obj: dict, drift_gap_s: float) -> bool:
    """A cleanly-aligned line -- strict enough to serve as an offset anchor.

    False if it has no words, holds an internal gap over ``drift_gap_s``, or
    is mostly instant words (a crammed sweep the aligner failed to place but
    did not drop).
    """
    words = obj["words"]
    if not words:
        return False
    gap = max((b["start"] - a["end"] for a, b in zip(words, words[1:])), default=0.0)
    if gap > drift_gap_s:
        return False
    return _instant_fraction(words) <= MAX_INSTANT_FRACTION


def _line_is_good(
    obj: dict, cue_span: tuple[float, float], offset: float, drift_gap_s: float
) -> bool:
    """Clean, or the only fault is a wide internal gap while the whole line
    sits inside its offset-corrected cue span.

    Clean lines are trusted even outside their cue span: caption cue times
    carry per-line authoring jitter well past :data:`PAUSE_SLACK_S`, and
    demoting every such line to a paced fill replaces real audio timing
    wholesale (a 5x flag-rate blowup on the SRT corpus). Only a per-line
    re-align's *result* is gated on containment alone (:func:`_line_in_span`),
    because there displacement is the failure mode being screened for --
    and lines in identical-text runs never reach this clean-trust path
    (:func:`_repeat_detection_slacks`).
    """
    if _line_is_clean(obj, drift_gap_s):
        return True
    return _line_in_span(obj, cue_span, offset)


def _line_in_span(
    obj: dict, cue_span: tuple[float, float], offset: float, slack: float = PAUSE_SLACK_S
) -> bool:
    """Has words, is not mostly instant, and sits inside its offset-corrected
    cue span (within ``slack``).

    A wide internal gap *inside* the span is a caption-covered pause, not
    drift, while a parked tail overruns the span and fails. Containment is
    the only tell for a tightly-packed re-align result that landed wholly
    outside its window: a one-word line has no internal gap for a drift test
    to catch.
    """
    words = obj["words"]
    if not words:
        return False
    if _instant_fraction(words) > MAX_INSTANT_FRACTION:
        return False
    c0, c1 = cue_span
    return obj["start"] >= c0 + offset - slack and obj["end"] <= c1 + offset + slack


def _repeat_detection_slacks(
    line_toks: list[list[tuple[str, str]]],
    cue_spans: list[tuple[float, float]],
) -> dict[int, float]:
    """Containment slack per line in a run of identical text, else absent.

    A repeat the section align displaced onto a neighbouring occurrence comes
    back internally clean, so clean-trust cannot see it -- and the displacement
    is a whole repeat period, not caption-jitter scale. For these lines only,
    detection requires containment, with slack at half the distance to the
    nearest identical neighbour's cue start (the aliasing decision boundary),
    never tighter than :data:`PAUSE_SLACK_S` so ordinary jitter still passes.
    """
    norms = [" ".join(norm for norm, _raw in toks) for toks in line_toks]
    slacks: dict[int, float] = {}
    n = min(len(norms), len(cue_spans))
    for lid in range(n):
        if not norms[lid]:
            continue
        periods = [
            abs(cue_spans[nbr][0] - cue_spans[lid][0])
            for nbr in (lid - 1, lid + 1)
            if 0 <= nbr < n and norms[nbr] == norms[lid]
        ]
        if periods:
            slacks[lid] = max(PAUSE_SLACK_S, min(periods) / 2)
    return slacks


def fit_offset(
    line_objects: list[dict],
    cue_spans: list[tuple[float, float]],
    align_lines: list[str] | None = None,
    *,
    drift_gap_s: float = DRIFT_GAP_S,
    min_anchors: int = CUE_MIN_ANCHORS,
) -> float:
    """Median display lead ``aligned_start - cue_start`` over the clean lines.

    With ``align_lines``, anchors are narrowed to full-coverage lines (every
    token got a word) when enough exist: a line whose leading words were
    dropped starts late, biasing its residual. 0.0 when too few lines aligned
    to fit robustly. Public because the driver uses the fitted lead to decide
    whether to re-section the song on shifted cues.
    """
    anchors = [
        obj
        for obj in line_objects
        if obj["line_id"] < len(cue_spans) and _line_is_clean(obj, drift_gap_s)
    ]
    if align_lines is not None:
        counts = [len(toks) for toks in _tokenise_lines(align_lines)]
        full = [obj for obj in anchors if len(obj["words"]) == counts[obj["line_id"]]]
        if len(full) >= min_anchors:
            anchors = full
    residuals = [obj["start"] - cue_spans[obj["line_id"]][0] for obj in anchors]
    if len(residuals) < max(1, min_anchors):
        return 0.0
    return median(residuals)


def _line_from_realigned(
    lid: int,
    display_text: str,
    toks: list[tuple[str, str]],
    t0: float,
    t1: float,
    raw_words: list[dict],
    max_word_dur: float,
) -> dict | None:
    """Line object from a per-line re-align's absolute-time words, or None if
    the result covers too little of the line to trust."""
    norms = [norm for norm, _raw in toks]
    assign = _match_words_to_tokens(norms, _token_expected_times(len(toks), t0, t1), raw_words)
    words: list[dict] = []
    for (_norm, raw), wi in zip(toks, assign):
        if wi is None:
            continue
        w = raw_words[wi]
        words.append(
            {"word": raw, "start": w["start"], "end": min(w["end"], w["start"] + max_word_dur)}
        )
    if len(words) / len(toks) < MIN_LINE_COVERAGE:
        return None
    return _line_object(lid, display_text, words, source=SOURCE_REALIGN)


def _repace_line(
    lid: int,
    display_text: str,
    toks: list[tuple[str, str]],
    t0: float,
    t1: float,
    max_word_dur: float,
) -> dict:
    """Line object with paced words across ``[t0, t1]``, each capped to
    ``max_word_dur``. Slots are weighted by normalised token length (a cheap
    syllable proxy) so a long word sweeps longer than a short one."""
    if t1 <= t0:
        t1 = t0 + 0.5
    weights = [max(1, len(norm)) for norm, _raw in toks]
    total = sum(weights)
    words: list[dict] = []
    t = t0
    for (_norm, raw), weight in zip(toks, weights):
        dur = (t1 - t0) * weight / total
        words.append({"word": raw, "start": t, "end": t + min(dur, max_word_dur)})
        t += dur
    return _line_object(lid, display_text, words, source=SOURCE_FILL)


def _line_object(lid: int, text: str, words: list[dict], *, source: str = SOURCE) -> dict:
    """Canonical line object; ``start/end`` are None for a hidden line."""
    return {
        "line_id": lid,
        "text": text,
        "words": words,
        "start": words[0]["start"] if words else None,
        "end": words[-1]["end"] if words else None,
        "source": source,
    }


def align_song(
    cue_spans: list[tuple[float, float]],
    display_lines: list[str],
    align_lines: list[str],
    duration: float | None,
    slice_align: Callable[[float, float, str, str], list[dict] | None],
    *,
    pad_s: float = SECTION_PAD_S,
    progress: Callable[[list[Section]], Iterable[Section]] | None = None,
) -> tuple[list[dict], dict]:
    """Windowed-align one song from its 1:1 per-line cue spans.

    The cue-align driver: segment the cues into silence-bounded sections
    (:func:`segment_by_gaps`), force-align each section's window once via the
    injected ``slice_align`` (``(t0, t1, text, label) -> absolute-time words or
    None``), split the words back to lines (:func:`split_section_to_lines`), fit
    the display lead (:func:`fit_offset`) and -- when it exceeds ``pad_s``, past
    which every section window clips its leading words -- re-section once on
    offset-shifted cues, then re-pace the lines the align could not place
    (:func:`repace_bad_lines`, with a narrow per-line ``slice_align`` rescue).

    ``duration`` clamps the section/fill windows to the audio; ``None`` (an
    unreadable stem) drops the clamp and the song degrades to cue-paced timing.
    All GPU/ffmpeg I/O lives behind ``slice_align``, so this stays pure and
    ``test_cue_align`` can drive it with a stub aligner. Display is injected the
    same way: ``progress`` wraps the per-pass section list (e.g. ``tqdm``) so
    the caller owns the terminal; ``None`` iterates silently.

    Returns ``(line_objects, stats)``; ``stats`` carries the section count, the
    fitted offset, whether a re-section fired, and the repace sub-stats.
    """
    show_progress = progress or (lambda sections: sections)

    def align_pass(spans: list[tuple[float, float]]) -> tuple[list[dict], int]:
        sections = segment_by_gaps(spans, duration=duration)
        logger.info("cue-align: %d cues -> %d sections", len(spans), len(sections))
        objs: list[dict] = []
        for section in show_progress(sections):
            sub_text = "\n".join(align_lines[lid] for lid in section.line_ids)
            words = slice_align(
                section.t0, section.t1, sub_text, f"section lines {section.lid_lo}-{section.lid_hi}"
            )
            objs.extend(
                split_section_to_lines(section, words or [], display_lines, align_lines, spans)
            )
        return objs, len(sections)

    line_objects, n_sections = align_pass(cue_spans)
    spans = cue_spans
    offset = fit_offset(line_objects, cue_spans, align_lines)
    resectioned = abs(offset) > pad_s
    if resectioned:
        # Beyond the pad, every section window provably clips its leading
        # words; shift the cues onto the audio clock and re-align once.
        logger.info(
            "cue-align: display lead %+.2fs exceeds pad %.2fs; re-sectioning", offset, pad_s
        )
        spans = [
            (max(0.0, c0 + offset), max(0.0, c0 + offset, c1 + offset)) for c0, c1 in cue_spans
        ]
        line_objects, n_sections = align_pass(spans)

    def realign_line(lid: int, t0: float, t1: float) -> list[dict] | None:
        """Narrow per-line forced align over a bad line's offset-corrected window."""
        w0 = max(0.0, t0 - pad_s)
        w1 = t1 + pad_s if duration is None else min(duration, t1 + pad_s)
        if w1 - w0 < 0.2:
            return None
        return slice_align(w0, w1, align_lines[lid], f"line {lid}")

    line_objects, repace_stats = repace_bad_lines(
        line_objects, spans, display_lines, align_lines, duration=duration, realign=realign_line
    )
    stats = {
        "n_sections": n_sections,
        "offset_s": round(offset, 3),
        "resectioned": resectioned,
        "repace": repace_stats,
    }
    return line_objects, stats
