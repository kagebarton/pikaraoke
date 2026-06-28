"""Cue-anchored windowed alignment: word timings from trusted SRT line cues.

A standalone alternative to the global joint-matcher path, for songs whose
lyrics come from an uploader-synced SRT. The SRT already solves the matcher's
job -- line -> time, 1:1 -- so this path never places lines from audio. It
only derives per-word timing *within* the trusted cue structure, which makes
the global-placement artifacts (candidate straddle, repeat pile-up,
slow-crawl) structurally impossible rather than something to patch.

Pipeline-free by design: every function here is pure. All GPU/ffmpeg I/O
lives in ``scripts/cue_align_song.py`` and is injected (the forced aligner is
a callable). The module emits the same ``line_objects`` shape the existing
ASS/SRT generators consume, so it plugs into the renderer unchanged and is
one swap away from graduating into the pipeline.

Approach:

1. Group consecutive cues into *sections* split at real phrase gaps
   (:func:`segment_by_gaps`), so every section boundary falls in silence.
   Aligning a contiguous phrase as one slice means forced alignment never
   clips a sung word at a slice edge and never bleeds one line's words onto a
   neighbour's audio -- both are window-edge faults that vanish when the edges
   sit in silence.
2. Force-align each section's joined text once (driver), then split the
   returned words back to lines (:func:`split_section_to_lines`). The aligner
   drops words it could not time (``remove_instant_words``), so the split
   matches surviving words to lyric tokens by normalised text in order rather
   than by blind token count -- a dropped word skips its token instead of
   shifting every later line.
3. Re-pace the lines the align could not cover (:func:`repace_bad_lines`): a
   line left under-covered or with a drifted internal gap is re-built with
   even-paced words across its offset-corrected cue span. The per-song display
   lead is fit from the lines that *did* align, so the trusted SRT cue carries
   the lines the audio could not place (the gapless-section failure). Only
   already-bad lines are touched, so a sloppy offset never degrades a good one.
"""

import logging
from dataclasses import dataclass
from statistics import median

from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.token_align import _normalize_token

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

SOURCE = "cue_align"
# Provenance for a line whose timing came from the cue re-pace fallback rather
# than the audio align (mirrors the SRT prior's "filled" tag).
SOURCE_FILL = "cue_align_fill"


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
    exceeds ``gap_s``.

    Each section's window extends ``pad_s`` into the flanking silence, clamped
    to the gap midpoint (so neighbouring sections never overlap-claim the same
    audio) and to ``[0, duration]`` when ``duration`` is known.
    """
    if not cue_spans:
        return []
    n = len(cue_spans)
    # Line ids that start a new section: 0, plus every line after a wide gap.
    starts = [0] + [i + 1 for i in range(n - 1) if cue_spans[i + 1][0] - cue_spans[i][1] > gap_s]
    bounds = starts + [n]
    sections: list[Section] = []
    for lo, nxt in zip(bounds, bounds[1:]):
        hi = nxt - 1
        start = cue_spans[lo][0]
        end = cue_spans[hi][1]
        if lo == 0:
            t0 = max(0.0, start - pad_s)
        else:
            # Share the preceding gap with the previous section at its midpoint.
            t0 = start - min(pad_s, (start - cue_spans[lo - 1][1]) / 2)
        if hi == n - 1:
            t1 = end + pad_s
            if duration is not None:
                t1 = min(duration, t1)
        else:
            t1 = end + min(pad_s, (cue_spans[hi + 1][0] - end) / 2)
        sections.append(Section(lo, hi, round(max(0.0, t0), 3), round(t1, 3)))
    return sections


def split_section_to_lines(
    section: Section,
    aligned_words: list[dict],
    display_lines: list[str],
    align_lines: list[str],
    *,
    max_word_dur: float = MAX_WORD_DUR_S,
    min_coverage: float = MIN_LINE_COVERAGE,
) -> list[dict]:
    """Map a section's aligned words back to its individual lines.

    ``aligned_words`` are the section slice's forced-align words in *absolute
    song time*, in order. The aligner drops words it could not time, so the
    stream is a subsequence of the section's lyric tokens, not a 1:1 list. Each
    word is matched to the next lyric token with the same normalised form (a
    forward scan); a token with no surviving word is simply skipped, so one
    dropped word no longer shifts the split for every later line.

    Each kept word's sweep is capped to ``max_word_dur`` (anchored at its
    start). A line whose covered-token fraction falls below ``min_coverage`` is
    emitted with no words -- left for :func:`repace_bad_lines` to fill from the
    cue rather than rendered from too little timing.

    Returns one line object per section line, in line order, in the canonical
    ``line_objects`` shape (``words=[]`` and ``start/end=None`` for a line with
    no usable timing).
    """
    line_toks = _tokenise_lines([align_lines[lid] for lid in section.line_ids])
    word_norms = [_normalize_token(w["word"]) for w in aligned_words]
    out: list[dict] = []
    wi = 0
    for toks, lid in zip(line_toks, section.line_ids):
        n = len(toks)
        words: list[dict] = []
        for norm, raw in toks:
            if wi < len(aligned_words) and word_norms[wi] == norm:
                w = aligned_words[wi]
                words.append(
                    {
                        "word": raw,
                        "start": w["start"],
                        "end": min(w["end"], w["start"] + max_word_dur),
                    }
                )
                wi += 1
            # else: this token's word was dropped by the aligner -- skip it.
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
) -> tuple[list[dict], dict]:
    """Re-pace the lines the align could not place, from their cue spans.

    A line is *bad* if it has no usable words (under-covered) or holds an
    internal word-gap over ``drift_gap_s`` (the aligner drifted). Each bad line
    is rebuilt with even-paced words across its offset-corrected cue span; good
    lines pass through untouched. The display-lead offset is the median of
    ``aligned_start - cue_start`` over the *good* lines (below ``min_anchors``,
    a zero offset is used). Because only bad lines are rewritten, a coarse
    offset can never degrade a well-aligned line.

    Returns ``(line_objects, stats)``; re-paced lines are tagged
    :data:`SOURCE_FILL`. ``cue_spans`` is indexed by ``line_id``.
    """
    offset = _fit_offset(line_objects, cue_spans, drift_gap_s, min_anchors)
    out: list[dict] = []
    repaced: list[int] = []
    for obj in line_objects:
        lid = obj["line_id"]
        if lid >= len(cue_spans) or _line_is_good(obj, drift_gap_s):
            out.append(obj)
            continue
        cue_start, cue_end = cue_spans[lid]
        filled = _repace_line(
            lid,
            display_lines[lid],
            align_lines[lid],
            max(0.0, cue_start + offset),
            cue_end + offset,
            max_word_dur,
        )
        if filled is None:  # display-only line (no alignable tokens)
            out.append(obj)
        else:
            out.append(filled)
            repaced.append(lid)
    stats = {"offset_s": round(offset, 3), "n_repaced": len(repaced), "repaced_line_ids": repaced}
    logger.info(
        "cue re-pace: offset=%+.2fs, %d/%d line(s) re-paced from cue",
        offset,
        len(repaced),
        len(line_objects),
    )
    return out, stats


def _line_is_good(obj: dict, drift_gap_s: float) -> bool:
    """A cleanly-aligned line -- usable as an offset anchor and left untouched
    by the re-pace.

    Bad if it has no words, holds a drifted internal gap over ``drift_gap_s``,
    or is mostly instant words (a crammed sweep the aligner failed to place but
    did not drop).
    """
    words = obj["words"]
    if not words:
        return False
    gap = max((b["start"] - a["end"] for a, b in zip(words, words[1:])), default=0.0)
    if gap > drift_gap_s:
        return False
    instant = sum(1 for w in words if w["end"] - w["start"] < INSTANT_WORD_DUR_S)
    return instant / len(words) <= MAX_INSTANT_FRACTION


def _fit_offset(
    line_objects: list[dict],
    cue_spans: list[tuple[float, float]],
    drift_gap_s: float,
    min_anchors: int,
) -> float:
    """Median ``aligned_start - cue_start`` over the cleanly-aligned lines, or
    0.0 when too few lines aligned to fit it robustly."""
    residuals = [
        obj["start"] - cue_spans[obj["line_id"]][0]
        for obj in line_objects
        if obj["line_id"] < len(cue_spans) and _line_is_good(obj, drift_gap_s)
    ]
    if len(residuals) < min_anchors:
        return 0.0
    return median(residuals)


def _repace_line(
    lid: int,
    display_text: str,
    align_line: str,
    t0: float,
    t1: float,
    max_word_dur: float,
) -> dict | None:
    """Line object with even-paced words across ``[t0, t1]``, each capped to
    ``max_word_dur``. None for a display-only line with no alignable tokens."""
    toks = _tokenise_lines([align_line])[0]
    if not toks:
        return None
    if t1 <= t0:
        t1 = t0 + 0.5
    step = (t1 - t0) / len(toks)
    words = [
        {
            "word": raw,
            "start": t0 + i * step,
            "end": t0 + i * step + min(step, max_word_dur),
        }
        for i, (_norm, raw) in enumerate(toks)
    ]
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
