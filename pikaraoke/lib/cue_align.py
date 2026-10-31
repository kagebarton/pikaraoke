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
   sit in silence. Captions often end before the singing does, so given the
   vocal stem's envelope each window's end moves out to where the singing
   actually stops; starts stay on the trusted cue starts.
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
   if that also fails is it re-built with paced words across the window. A
   line missing only some of its words is rescued too: the re-align (aimed out
   to the section's end for a section's last line, where a held tail lies)
   replaces it only if it times more of them, and any word still untimed is
   shown with guessed timing at the line's own pace -- a lyric word is never
   dropped from the screen. Only bad or partial lines are touched, so a sloppy
   offset never degrades a good one. The driver also re-sections the whole
   song on offset-shifted cues when the fitted lead exceeds the slice pad --
   past that, every section window provably clips its leading words.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from statistics import median

import numpy as np

from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.onset_snap import HOP_S, MIN_REF_DB, SUSTAIN_NEAR_DB, _sung_level_ref
from pikaraoke.lib.token_align import _normalize_token, match_words_to_tokens

logger = logging.getLogger(__name__)

# Silent gap to the next cue, above which a section boundary is cut. Karaoke
# lines run back-to-back (<0.5 s apart); a breath/phrase gap is ~1-2 s. Cutting
# here puts every section edge in silence, so the slice never bisects a sung
# word.
SECTION_GAP_S = 1.5

# How far a section's slice extends into the flanking silence so the first/last
# sung word is never clipped. Clamped to the gap midpoint (below) so adjacent
# sections never claim the same audio -- unless the vocal envelope shows the
# earlier line still singing past it (see EDGE_SEARCH_SLACK_S).
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

# Window ends follow the vocal stem's volume where an envelope is given. A
# caption often ends before the singing does (a held note, a line timed short);
# the aligner can only time words it is handed, so a window ending at the
# caption drops the tail of the line. A window's end therefore moves out to
# where the singing stops, never in, and its start stays on the caption: cue
# starts are the trusted times. The search for the stop begins this far before
# the caption's end, so a release that began just before it is measured whole
# rather than mistaken for a short pause.
EDGE_SEARCH_SLACK_S = 0.5

# A frame is quiet when it sits this far below the louder neighbouring line's
# sung level (the same distance onset_snap uses to call a note still sustained),
# so reverb decaying off a held note counts as quiet but a sung word does not.
QUIET_DIP_DB = SUSTAIN_NEAR_DB

# The singing has stopped at the first quiet stretch this long. Pauses inside a
# line held past its caption run to ~0.5 s (Baby One More Time, Stronger); a
# line that never pauses this long before the next caption sang straight into it.
RELEASE_QUIET_S = 0.75

# A line's singing runs on at most this far past its caption. Vocals that go on
# longer without a pause are not its tail (an uncaptioned part, ad-libs over a
# break), so that end keeps the caption rule. No line in the library that drops
# words sings more than 3.7 s past its caption. The song's last line is exempt:
# nothing follows it, and final notes are held longest.
MAX_HOLD_S = 4.0

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
    # t1 was measured from the vocal volume (it is never earlier than the caption
    # gap's). Left out of equality: two windows with the same edges are the same window.
    measured_end: bool = field(default=False, compare=False)

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


def _section_starts(cue_spans: list[tuple[float, float]], gap_s: float) -> list[int]:
    """Line ids that start a section: 0, every line after a gap over ``gap_s``, and every
    cap split of a section still longer than :data:`MAX_SECTION_DUR_S`."""
    n = len(cue_spans)
    starts = [0] + [i + 1 for i in range(n - 1) if cue_spans[i + 1][0] - cue_spans[i][1] > gap_s]
    bounds = starts + [n]
    split_starts = [
        s
        for lo, nxt in zip(bounds, bounds[1:])
        for s in _split_oversized(lo, nxt - 1, cue_spans, MAX_SECTION_DUR_S)
    ]
    # Split points are strictly interior to their section, so the lists are
    # disjoint; sorting interleaves them into the boundary order.
    return sorted(starts + split_starts)


def _loudest_sung_level(env: np.ndarray, spans: list[tuple[float, float]]) -> float | None:
    """The louder of the spans' sung levels in ``env``, or None when none is singing.

    A span's level is :data:`onset_snap.SINGLE_WORD_REF_PCT` percentile of its frames: no
    words exist yet, so the single-word reference is the one that fits. Below
    :data:`onset_snap.MIN_REF_DB` the audio is not singing and every relative test is moot.
    """
    levels = [_sung_level_ref(env, [{"start": c0, "end": c1}]) for c0, c1 in spans]
    best = max((level for level in levels if level is not None), default=None)
    return best if best is not None and best >= MIN_REF_DB else None


def _quiet_runs(
    env: np.ndarray, lo_s: float, hi_s: float, sung_db: float
) -> list[tuple[float, float]]:
    """Each stretch of ``env`` within ``[lo_s, hi_s]`` at least :data:`QUIET_DIP_DB`
    below ``sung_db``, as ``(start_s, end_s)`` in time order."""
    i0 = max(0, int(lo_s / HOP_S))
    i1 = min(len(env), int(hi_s / HOP_S) + 1)
    if i1 <= i0:
        return []
    quiet = np.concatenate(([False], env[i0:i1] < sung_db - QUIET_DIP_DB, [False]))
    changes = np.flatnonzero(quiet[1:] != quiet[:-1])
    pairs = zip(changes[::2].tolist(), changes[1::2].tolist())
    return [((i0 + a) * HOP_S, (i0 + b) * HOP_S) for a, b in pairs]


def _volume_end(
    env: np.ndarray, last: tuple[float, float], nxt: tuple[float, float], pad_s: float
) -> float | None:
    """Where a section's window should end, from where its last line's singing stops.

    ``last``/``nxt`` are the cue spans of the section's latest-ending line (with duet
    overlap, not always its last) and the next section's first. The singing stops at
    the first quiet stretch of :data:`RELEASE_QUIET_S`; the window reaches ``pad_s``
    into it, no further than its midpoint. A line that never
    pauses that long before ``nxt`` starts sang straight into it, and the window ends at
    ``nxt``'s caption start. None when there is no singing to measure, the envelope ends
    before ``nxt``, ``nxt`` starts before the search would (overlapping cues leave no
    stretch to measure), or the stop lies more than :data:`MAX_HOLD_S` past the caption.
    """
    if nxt[0] <= last[1] - EDGE_SEARCH_SLACK_S:
        return None
    sung_db = _loudest_sung_level(env, [last, nxt])
    if sung_db is None or nxt[0] > len(env) * HOP_S:
        return None
    runs = _quiet_runs(env, last[1] - EDGE_SEARCH_SLACK_S, nxt[0], sung_db)
    release = next((run for run in runs if run[1] - run[0] >= RELEASE_QUIET_S), None)
    if release is None:
        stop = t1 = nxt[0]
    else:
        stop, t1 = release[0], min(release[0] + pad_s, sum(release) / 2)
    return t1 if stop <= last[1] + MAX_HOLD_S else None


def _volume_tail(
    env: np.ndarray, last: tuple[float, float], pad_s: float, duration: float | None
) -> float | None:
    """Where the song's last window should end: ``pad_s`` after the stem's last sung frame.

    Not capped by :data:`MAX_HOLD_S`: nothing follows to take the audio from, and a
    song's final note is often its longest. None when the last line has no singing to
    measure.
    """
    sung_db = _loudest_sung_level(env, [last])
    if sung_db is None:
        return None
    i0 = max(0, int(last[0] / HOP_S))
    # Never empty: the level is a percentile of frames at and after i0.
    sung = np.flatnonzero(env[i0:] >= sung_db - QUIET_DIP_DB)
    t1 = (i0 + int(sung[-1]) + 1) * HOP_S + pad_s
    return t1 if duration is None else min(duration, t1)


def segment_by_gaps(
    cue_spans: list[tuple[float, float]],
    *,
    gap_s: float = SECTION_GAP_S,
    pad_s: float = SECTION_PAD_S,
    duration: float | None = None,
    env: np.ndarray | None = None,
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

    With ``env`` (the vocal stem's dB envelope, one value per
    :data:`onset_snap.HOP_S`) the grouping and every window start are unchanged,
    but a window's end moves later to where the audio shows its latest-ending
    line's singing stop (:func:`_volume_end`, :func:`_volume_tail`), so a note
    held past its caption stays inside its window. An end never moves earlier, so the
    window may overlap the next one where the earlier line is still singing.
    :attr:`Section.measured_end` says which ends ``env`` could measure.
    """
    if not cue_spans:
        return []
    n = len(cue_spans)
    bounds = _section_starts(cue_spans, gap_s) + [n]
    sections: list[Section] = []
    for lo, nxt in zip(bounds, bounds[1:]):
        hi = nxt - 1
        start = cue_spans[lo][0]
        # With duet overlap an earlier line can outlast the section's last one.
        last = max(cue_spans[lo : hi + 1], key=lambda span: span[1])
        end = last[1]
        if lo == 0:
            t0 = max(0.0, start - pad_s)
        else:
            # Share the preceding gap with the previous section at its
            # midpoint; a negative gap (cap split inside cue overlap) pads
            # zero rather than inverting into the boundary line's audio.
            t0 = start - min(pad_s, max(0.0, (start - cue_spans[lo - 1][1]) / 2))
        measured = None
        if hi == n - 1:
            t1 = end + pad_s
            if duration is not None:
                t1 = min(duration, t1)
            if env is not None:
                measured = _volume_tail(env, last, pad_s, duration)
        else:
            t1 = end + min(pad_s, max(0.0, (cue_spans[hi + 1][0] - end) / 2))
            if env is not None:
                measured = _volume_end(env, last, cue_spans[hi + 1], pad_s)
        if measured is not None:
            t1 = max(t1, measured)
        sections.append(Section(lo, hi, round(max(0.0, t0), 3), round(t1, 3), measured is not None))
    return sections


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
    sections: list[Section] | None = None,
    pad_s: float = SECTION_PAD_S,
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
    :func:`fit_offset` over the clean lines. A line otherwise placed but
    missing some of its words is *partial*.

    Each bad or partial line is rescued in two steps: ``realign(lid, w0, w1)``
    -- an injected narrow per-line forced align over the offset-corrected
    window padded by ``pad_s`` (clamped to ``duration``), returning
    absolute-time words or None -- is tried first, and its result is kept
    only if it comes back covered and *inside the window it was aimed at*
    (:func:`_line_in_span`; tagged :data:`SOURCE_REALIGN`), and for a partial
    line only if it times more of the words. The last line of each of
    ``sections`` is aimed out to its section's end, where a note held past the
    caption lies, and its window stops there: that end is already padded, and
    may be the next caption's start. Otherwise a bad line is rebuilt with
    paced words across its cue window (tagged :data:`SOURCE_FILL`), clamped
    to ``duration`` when known, and a partial line keeps the words it has. Because only bad and
    partial lines are rewritten, a coarse offset can never degrade a
    well-aligned line.

    Finally every word a kept line still lacks is shown with guessed timing
    (:func:`_with_guessed_words`), so no lyric word is dropped from the screen.

    Returns ``(line_objects, stats)``. ``cue_spans`` is indexed by ``line_id``.
    """
    offset = fit_offset(
        line_objects, cue_spans, align_lines, drift_gap_s=drift_gap_s, min_anchors=min_anchors
    )
    line_toks = _tokenise_lines(align_lines)
    repeat_slacks = _repeat_detection_slacks(line_toks, cue_spans)
    section_of = {lid: section for section in sections or () for lid in section.line_ids}
    out: list[dict] = []
    repaced: list[int] = []
    realigned: list[int] = []
    for obj in line_objects:
        lid = obj["line_id"]
        if lid >= len(cue_spans):
            out.append(obj)
            continue
        toks = line_toks[lid]
        if lid in repeat_slacks:
            placed = _line_in_span(obj, cue_spans[lid], offset, slack=repeat_slacks[lid])
        else:
            placed = _line_is_good(obj, cue_spans[lid], offset, drift_gap_s)
        if placed and len(obj["words"]) >= len(toks):
            out.append(obj)
            continue
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
        section = section_of.get(lid)
        at_section_end = section is not None and lid == section.lid_hi
        aim_end = max(t1, section.t1) if at_section_end else t1
        w0 = max(0.0, t0 - pad_s)
        w1 = aim_end if at_section_end else t1 + pad_s
        if duration is not None:
            w1 = min(duration, w1)
        if realign is not None and w1 - w0 >= 0.2:
            raw_words = realign(lid, w0, w1)
            fixed = (
                _line_from_realigned(
                    lid, display_lines[lid], toks, t0, aim_end, raw_words, max_word_dur
                )
                if raw_words
                else None
            )
            # The window it was aimed at, in cue time: the check adds the offset back.
            aimed = (cue_start, max(cue_end, aim_end - offset))
            if (
                fixed is not None
                and _line_in_span(fixed, aimed, offset)
                and (not placed or len(fixed["words"]) > len(obj["words"]))
            ):
                out.append(fixed)
                realigned.append(lid)
                continue
        if placed:
            out.append(obj)
            continue
        out.append(_repace_line(lid, display_lines[lid], toks, t0, t1, max_word_dur))
        repaced.append(lid)
    guessed: dict[int, int] = {}
    for i, obj in enumerate(out):
        lid = obj["line_id"]
        if lid >= len(cue_spans) or not obj["words"] or len(obj["words"]) >= len(line_toks[lid]):
            continue
        # Guessed words stay between the neighbouring lines' words and inside the window.
        after = next((prev["end"] for prev in reversed(out[:i]) if prev["words"]), 0.0)
        before = next((nxt["start"] for nxt in out[i + 1 :] if nxt["words"]), float("inf"))
        if duration is not None:
            before = min(before, duration)
        section = section_of.get(lid)
        if section is not None:
            after, before = max(after, section.t0), min(before, section.t1)
        out[i] = _with_guessed_words(
            obj, line_toks[lid], cue_spans[lid], after, before, max_word_dur
        )
        guessed[lid] = len(line_toks[lid]) - len(obj["words"])
    stats = {
        "offset_s": round(offset, 3),
        "n_repaced": len(repaced),
        "repaced_line_ids": repaced,
        "n_realigned": len(realigned),
        "realigned_line_ids": realigned,
        "n_guessed_words": sum(guessed.values()),
        "guessed_word_line_ids": list(guessed),
    }
    logger.info(
        "cue rescue: offset=%+.2fs, %d line(s) re-aligned, %d/%d re-paced from cue, "
        "%d word(s) guessed in %d line(s)",
        offset,
        len(realigned),
        len(repaced),
        len(line_objects),
        stats["n_guessed_words"],
        len(guessed),
    )
    return out, stats


def _with_guessed_words(
    obj: dict,
    toks: list[tuple[str, str]],
    cue_span: tuple[float, float],
    after: float,
    before: float,
    max_word_dur: float,
) -> dict:
    """``obj`` (some words timed, fewer than ``toks``) with a word for every untimed token.

    A guessed word keeps the line's own pace (its timed words' median duration, capped
    at ``max_word_dur``). A missing tail runs on from the last timed word and ends by
    ``before`` (the next line's first word or the window's end); a missing head runs
    back from the first timed word and starts no earlier than ``after``; a missing
    middle word shares the gap between its timed neighbours. Squeezed by a bound, the
    words are spaced evenly in what is left. With less room than an instant word each
    (touching neighbours, or a bound the timed word already reaches), the guessed words
    share their timed neighbour's own slot, so none is shown for no time or past the
    bound. The edge snap later stretches a guessed last word to the measured release.
    """
    words = obj["words"]
    # Every word is one of these tokens' raw text, so each finds its own token.
    assign = _match_words_to_tokens(
        [norm for norm, _raw in toks], _token_expected_times(len(toks), *cue_span), words
    )
    pace = min(median(w["end"] - w["start"] for w in words), max_word_dur)
    timed = [k for k, wi in enumerate(assign) if wi is not None]
    out: list[dict | None] = [words[wi] if wi is not None else None for wi in assign]

    def fill(ks: list[int], lo: float, hi: float) -> None:
        step = max(0.0, hi - lo) / len(ks)
        for j, k in enumerate(ks):
            start = lo + j * step
            out[k] = {"word": toks[k][1], "start": start, "end": start + min(step, pace)}

    def cramped(n: int, lo: float, hi: float) -> bool:
        return hi - lo < n * INSTANT_WORD_DUR_S

    first, last = timed[0], timed[-1]
    if first:
        start, slot_end = out[first]["start"], out[first]["end"]
        lo = min(start, max(after, start - first * pace))
        if cramped(first, lo, start) and slot_end > lo:
            fill(list(range(first + 1)), lo, slot_end)
        else:
            fill(list(range(first)), lo, start)
    for a, b in zip(timed, timed[1:]):
        if b - a > 1:
            lo, hi = out[a]["end"], out[b]["start"]
            if cramped(b - a - 1, lo, hi) and hi > out[a]["start"]:
                fill(list(range(a, b)), out[a]["start"], hi)
            else:
                fill(list(range(a + 1, b)), lo, hi)
    if last < len(toks) - 1:
        slot_start, end = out[last]["start"], out[last]["end"]
        n_tail = len(toks) - 1 - last
        hi = min(before, end + n_tail * pace)
        if cramped(n_tail, end, hi) and hi > slot_start:
            fill(list(range(last, len(toks))), slot_start, hi)
        else:
            fill(list(range(last + 1, len(toks))), end, hi)
    return _line_object(obj["line_id"], obj["text"], out, source=obj["source"])


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
    env: np.ndarray | None = None,
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
    ``env`` (the aligned stem's dB envelope) moves window ends out to where the
    singing stops (:func:`segment_by_gaps`); ``None`` keeps the caption windows.
    All GPU/ffmpeg I/O lives behind ``slice_align``, so this stays pure and
    ``test_cue_align`` can drive it with a stub aligner. Display is injected the
    same way: ``progress`` wraps the per-pass section list (e.g. ``tqdm``) so
    the caller owns the terminal; ``None`` iterates silently.

    Returns ``(line_objects, stats)``; ``stats`` carries the section count, the
    fitted offset, whether a re-section fired, the repace sub-stats, and with
    ``env`` the final pass's window ``edges``: section ends, ends moved later
    than the caption windows', and ends the envelope could not place.
    """
    show_progress = progress or (lambda sections: sections)

    def align_pass(spans: list[tuple[float, float]]) -> tuple[list[dict], list[Section]]:
        sections = segment_by_gaps(spans, duration=duration, env=env)
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
        return objs, sections

    line_objects, sections = align_pass(cue_spans)
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
        line_objects, sections = align_pass(spans)

    line_objects, repace_stats = repace_bad_lines(
        line_objects,
        spans,
        display_lines,
        align_lines,
        duration=duration,
        realign=lambda lid, w0, w1: slice_align(w0, w1, align_lines[lid], f"line {lid}"),
        sections=sections,
        pad_s=pad_s,
    )
    stats = {
        "n_sections": len(sections),
        "offset_s": round(offset, 3),
        "resectioned": resectioned,
        "repace": repace_stats,
    }
    if env is not None:
        caption = segment_by_gaps(spans, duration=duration)
        stats["edges"] = {
            "n": len(sections),
            "widened": sum(s.t1 > c.t1 for s, c in zip(sections, caption)),
            "fallback": sum(not s.measured_end for s in sections),
        }
        logger.info(
            "cue-align: %d/%d window end(s) widened to the singing, %d left on the caption",
            stats["edges"]["widened"],
            len(sections),
            stats["edges"]["fallback"],
        )
    return line_objects, stats
