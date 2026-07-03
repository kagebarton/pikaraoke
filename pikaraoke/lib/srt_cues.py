"""SRT cue utilities: cleaned cue texts/spans + offset calibration.

Shared helpers for working with uploader-synced SRT cue times:

- :func:`cue_spans_from_srt` returns each cleaned cue's text and its
  ``(start, end)`` span, positionally identical to the lyric lines the
  matcher consumes — the SRT cue-align path's line->time input.
- :func:`offset_mad_against_cues` fits the robust median display lead of a
  set of audio placements against a cue reference, with a MAD bail-out when
  the anchors are too few or too spread to trust a single constant offset.
  Pure calibration math, used to score placements against a held-out cue
  reference offline (the alpha/beta tuning harness).
"""

from statistics import median

import srt

from pikaraoke.lib.genius_lyrics import clean_srt_line

# Fewer trusted anchors than this and the offset median is not robust;
# bail out and change nothing.
PRIOR_MIN_ANCHORS = 4

# Median absolute deviation of anchor residuals above this means the
# captions have a variable lead (or the anchors are unreliable); a
# single constant offset would mis-calibrate, so bail out. The corpus-wide
# anchor-residual MAD is well under this on every song with accurate
# captions.
PRIOR_MAX_MAD_S = 0.75


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


def offset_mad_against_cues(
    anchors: list[dict], cue_spans_by_line: dict[int, tuple[float, float]]
) -> dict:
    """Median offset + MAD of placed anchor starts vs cue starts.

    Pure calibration math, no mutation or logging. Scores a set of placements
    against an external cue reference (e.g. an offline held-out comparison in
    the tuning harness): the median display lead over anchor lines that have a
    cue, plus a MAD bail-out.

    Returns ``{"n_anchors_fit", "bailed", "offset_s", "mad_s"}``. ``bailed``
    is ``"few_anchors"`` when fewer than :data:`PRIOR_MIN_ANCHORS` anchors
    have a cue (``offset_s``/``mad_s`` absent), ``"wide_spread"`` when the
    residual MAD exceeds :data:`PRIOR_MAX_MAD_S` (present but unreliable),
    or ``None`` when the calibration is trustworthy.
    """
    residuals = [
        a["start"] - cue_spans_by_line[a["lid"]][0]
        for a in anchors
        if a["lid"] in cue_spans_by_line
    ]
    stats: dict = {"n_anchors_fit": len(residuals), "bailed": None}
    if len(residuals) < PRIOR_MIN_ANCHORS:
        stats["bailed"] = "few_anchors"
        return stats

    offset = median(residuals)
    mad = median(abs(r - offset) for r in residuals)
    stats["offset_s"] = round(offset, 3)
    stats["mad_s"] = round(mad, 3)
    if mad > PRIOR_MAX_MAD_S:
        stats["bailed"] = "wide_spread"
    return stats
