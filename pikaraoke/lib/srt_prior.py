"""SRT timing prior: repair + coverage fill from uploader-synced captions.

For songs whose lyrics were sourced from the YouTube SRT, every lyric
line already carries an uploader-synced cue time on disk that the
matcher discards. The SRT clock has an unknown display lead, so raw cue
times cannot be trusted directly — the audio calibrates the clock:

1. Pass-1 joint DP (and the windowed re-align, when it ran) place lines
   from audio as today.
2. The per-song display lead is fit as the robust median of
   ``placed_start - cue_start`` over trusted anchor lines (the windowed
   re-align's anchor criteria, reused verbatim). Few anchors or a wide
   residual spread (variable lead, sloppy captions) bails out — the
   prior must never degrade a song it cannot calibrate.
3. Placed lines disagreeing with ``cue + offset`` by more than the snap
   threshold are by construction the gross-error population (wrong
   chorus instance, drifted interp) — they snap to ``cue + offset``,
   keeping their word spacing.
4. Unplaced lines (interp/absent) gain even-paced words across their
   offset-corrected cue span, so lines audio fundamentally cannot place
   (lead vocal over chant) finally render.

Cue+offset is gross-repair quality, not sub-second polish (two corpus
songs have ~0.5 s-sloppy captions): repairs snap, but well-corroborated
audio placements are never blended toward cues.
"""

import logging
from statistics import median

import srt

from pikaraoke.lib.genius_lyrics import clean_srt_line
from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.windowed_realign import analyze_pass1

logger = logging.getLogger(__name__)

# Fewer trusted anchors than this and the offset median is not robust;
# bail out and change nothing.
PRIOR_MIN_ANCHORS = 4

# Median absolute deviation of anchor residuals above this means the
# captions have a variable lead (or the anchors are unreliable); a
# single constant offset would mis-repair, so bail out. The corpus-wide
# anchor-residual MAD is well under this on every song with accurate
# captions.
PRIOR_MAX_MAD_S = 0.75

# A placed line disagreeing with cue+offset by more than this is
# treated as a gross error and snapped. The SRT-vs-LRCLIB ceiling puts
# the cue-side gross rate at 2.6%, so snapping a >2 s disagreement to
# cue+offset is overwhelmingly likely to improve it.
SNAP_DISAGREE_S = 2.0


def cue_spans_from_srt(srt_text: str) -> tuple[list[str], list[tuple[float, float]]]:
    """Cleaned cue texts and their ``(start, end)`` spans in seconds.

    Applies the same per-cue cleanup as the lyric-align stage's SRT
    load (clean + drop empty), so the returned texts are positionally
    identical to the lyric lines the matcher consumed — the spans are
    the timing that load step throws away.
    """
    texts: list[str] = []
    spans: list[tuple[float, float]] = []
    for sub in srt.parse(srt_text):
        cleaned = clean_srt_line(sub.content)
        if cleaned:
            texts.append(cleaned)
            spans.append((sub.start.total_seconds(), sub.end.total_seconds()))
    return texts, spans


def apply_srt_prior(
    line_objects: list[dict],
    transcribe_words: list[dict],
    lines: list[str],
    align_lines: list[str],
    cue_spans_by_line: dict[int, tuple[float, float]],
    *,
    margin_s: float,
    max_edit_ratio: float,
    source: str = "srt",
) -> tuple[list[dict], dict]:
    """Repair and coverage-fill ``line_objects`` from SRT cue times.

    ``line_objects`` must be the matcher's final 1:1 output (every line
    present, each carrying a ``source``). ``cue_spans_by_line`` maps
    line ids to offset-uncorrected cue ``(start, end)`` spans; lines
    without a cue are never touched.

    ``source`` is the provenance tag stamped on repaired/filled lines
    (``"srt"`` for the SRT prior, ``"lrclib"`` for the LRCLIB path) so
    downstream consumers can attribute each cue to its origin.

    Returns ``(line_objects, prior_stats)``. On bail-out the input list
    is returned unchanged and ``prior_stats["bailed"]`` names the
    reason; otherwise repaired/filled lines are replaced by copies
    tagged with ``source``.
    """
    sources = ["absent"] * len(lines)
    for obj in line_objects:
        sources[obj["line_id"]] = obj.get("source") or "absent"
    anchors, _suspects = analyze_pass1(
        align_lines,
        line_objects,
        {"selected_source": sources},
        transcribe_words,
        margin_s=margin_s,
        max_edit_ratio=max_edit_ratio,
    )

    residuals = [
        a["start"] - cue_spans_by_line[a["lid"]][0]
        for a in anchors
        if a["lid"] in cue_spans_by_line
    ]
    stats: dict = {"n_anchors_fit": len(residuals), "bailed": None}
    if len(residuals) < PRIOR_MIN_ANCHORS:
        stats["bailed"] = "few_anchors"
        logger.info(
            "%s prior bailed: %d anchor(s) with cues < %d",
            source.upper(),
            len(residuals),
            PRIOR_MIN_ANCHORS,
        )
        return line_objects, stats

    offset = median(residuals)
    mad = median(abs(r - offset) for r in residuals)
    stats["offset_s"] = round(offset, 3)
    stats["mad_s"] = round(mad, 3)
    if mad > PRIOR_MAX_MAD_S:
        stats["bailed"] = "wide_spread"
        logger.info(
            "%s prior bailed: anchor residual MAD %.2fs > %.2fs", source.upper(), mad, PRIOR_MAX_MAD_S
        )
        return line_objects, stats

    snapped: list[int] = []
    filled: list[int] = []
    out: list[dict] = []
    for obj in line_objects:
        lid = obj["line_id"]
        cue = cue_spans_by_line.get(lid)
        if cue is None:
            out.append(obj)
            continue
        # A negative caption lead can push early cues below t=0; clamp —
        # negative word times floor-divide into garbage ASS timestamps.
        target = max(0.0, cue[0] + offset)
        if obj.get("words") and obj.get("start") is not None:
            if abs(obj["start"] - target) > SNAP_DISAGREE_S:
                out.append(_shift_line(obj, target - obj["start"], source))
                snapped.append(lid)
            else:
                out.append(obj)
        else:
            fill = _fill_line(lid, lines[lid], align_lines[lid], target, cue[1] + offset, source)
            if fill is not None:
                out.append(fill)
                filled.append(lid)
            else:
                out.append(obj)

    stats["n_snapped"] = len(snapped)
    stats["n_filled"] = len(filled)
    stats["snapped_line_ids"] = snapped
    stats["filled_line_ids"] = filled
    logger.info(
        "%s prior applied: offset=%+.2fs (MAD %.2fs over %d anchors), %d snapped, %d filled",
        source.upper(),
        offset,
        mad,
        len(residuals),
        len(snapped),
        len(filled),
    )
    return out, stats


def _shift_line(obj: dict, delta: float, source: str) -> dict:
    """Copy of ``obj`` with all word timings shifted by ``delta``."""
    shifted = dict(obj)
    shifted["words"] = [
        {**w, "start": w["start"] + delta, "end": w["end"] + delta} for w in obj["words"]
    ]
    shifted["start"] = obj["start"] + delta
    shifted["end"] = obj["end"] + delta
    shifted["source"] = source
    return shifted


def _fill_line(
    lid: int, text: str, align_line: str, t0: float, t1: float, source: str
) -> dict | None:
    """Line object with even-paced words across ``[t0, t1]``.

    None for display-only lines with no alignable tokens — there is
    nothing to sweep a karaoke cursor over.
    """
    toks = _tokenise_lines([align_line])[0]
    if not toks:
        return None
    if t1 <= t0:
        t1 = t0 + 0.5
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
