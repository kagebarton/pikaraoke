"""Timing evaluation of matcher output against YouTube manual captions.

Ground-truth design: for songs whose lyric source was the YouTube SRT,
the matcher consumed the SRT *text* while the cue *timings* were held
out, making them a text-identical, pure timing reference. Since the SRT
timing prior (pikaraoke.lib.srt_prior) ships, that held-out property
only covers placements the prior left untouched — SRT-informed output
must be scored against LRCLIB instead (``--prefer-lrclib``).

Subtitle cues lead the vocal by a display margin, so raw deltas carry a
per-song systematic offset. Each song gets a single global offset fit
(median of per-line deltas); all metrics are computed on the residuals.

See ``plans/matcher-timing-eval.md`` for the corpus and roadmap;
``scripts/eval_alignment.py`` is the CLI driver.
"""

import difflib
import re
from dataclasses import dataclass, field
from statistics import median

from pikaraoke.lib.joint_match import match_words_to_lines_joint_with_stats
from pikaraoke.lib.srt_prior import cue_spans_from_srt
from pikaraoke.lib.word_alignment import fold_to_ascii

# Residuals beyond this are gross misplacements (wrong section / chorus
# instance), the error class the matcher knobs are tuned to eliminate.
GROSS_RESIDUAL_S = 2.0

# Straight/curly apostrophes, backtick, acute accent.
_APOSTROPHES = re.compile("['‘’`´]")
_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_LRC_STAMP = re.compile(r"\[(\d+):(\d{2}(?:\.\d+)?)\]")


def normalize_line(text: str) -> str:
    """Casefolded, alphanumeric-only form used to pair lyric lines with
    subtitle cues. Tolerant of cleanup drift between capture time and
    eval time (HTML tags older cleanup kept, quote styles, musical-note
    glyphs, punctuation). Apostrophes are deleted (not space-replaced)
    so "don't" == "dont". Homoglyphs/diacritics are ASCII-folded so a
    Cyrillic-watermarked line still pairs with its reference cue.
    """
    # Apostrophes must be deleted before folding: NFKD decomposes the
    # acute accent (U+00B4) into space + combining mark, which would turn
    # "don´t" into "don t" instead of "dont".
    text = _APOSTROPHES.sub("", _HTML_TAG.sub(" ", text.lower()))
    return " ".join(_NON_ALNUM.sub(" ", fold_to_ascii(text)).split())


def parse_reference_cues(srt_text: str) -> tuple[list[str], list[float]]:
    """Cleaned cue texts and their start times (seconds) from an SRT.

    Same transform as the production cue extraction
    (:func:`pikaraoke.lib.srt_prior.cue_spans_from_srt`), keeping just
    the start times the reference comparison needs.
    """
    texts, spans = cue_spans_from_srt(srt_text)
    return texts, [start for start, _end in spans]


def parse_lrc_lines(lrc_text: str) -> tuple[list[str], list[float]]:
    """Texts and start seconds from LRC synced lyrics (LRCLIB exports).

    Used as a *timing reference only* — LRCLIB text variants are too
    inconsistent to feed the matcher (no quality control), but a synced
    variant's line *deltas* are usually sound. The absolute clock often
    differs from the video (different master/edit); the per-song offset
    fit in :func:`score_song` absorbs that, so only deltas matter.

    Tolerates multiple leading ``[mm:ss.xx]`` stamps per line; skips
    metadata tags, unstamped lines, and stamps with empty text. Output
    is sorted by time.
    """
    texts: list[str] = []
    starts: list[float] = []
    for raw in lrc_text.splitlines():
        stamps = []
        pos = 0
        for m in _LRC_STAMP.finditer(raw):
            if m.start() != pos:
                break
            stamps.append(60 * int(m.group(1)) + float(m.group(2)))
            pos = m.end()
        text = raw[pos:].strip()
        if not stamps or not text:
            continue
        for t in stamps:
            texts.append(text)
            starts.append(t)
    order = sorted(range(len(starts)), key=starts.__getitem__)
    return [texts[i] for i in order], [starts[i] for i in order]


# Minimum per-line text similarity for a line/cue pair to count as a
# match in the mapping alignment. Below this, lines reworded by cleanup
# drift fall out of the mapping (and out of scoring) instead of pairing
# wrongly. Corpus-swept 2026-06-11: 0.65 admits cross-split mis-pairs
# ("a whole new world" ~ "whole new world with you"); 0.85 drops them
# while keeping g-dropping/prefix drift ("waitin'"/"waiting") paired.
_MAP_MIN_RATIO = 0.85
# Cost of skipping a line/cue in the alignment. Small but nonzero so
# contiguous diagonals beat scattered skips when total match score ties.
_MAP_GAP_COST = 0.05


def map_lines_to_cues(bundle_lines: list[str], cue_texts: list[str]) -> dict[int, int]:
    """Map matcher line_id -> reference cue index by fuzzy sequence alignment.

    Order-preserving global alignment (Needleman-Wunsch) on normalized
    text with per-pair similarity scoring. Exact-equality block matching
    (difflib) mis-paired repeated sections: when a chorus appears twice
    on both sides but the first instances differ slightly (line-split or
    "waitin'"/"waiting" drift), the longest *exact* block pairs sheet
    instance 2 with reference instance 1, shifting every cue by a whole
    chorus. Fuzzy per-line similarity keeps near-equal lines on the
    diagonal, so each instance aligns to its own cues.
    """
    a = [normalize_line(t) for t in bundle_lines]
    b = [normalize_line(t) for t in cue_texts]
    n, m = len(a), len(b)
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        if not a[i]:
            continue
        sm = difflib.SequenceMatcher(autojunk=False)
        sm.set_seq2(a[i])
        for j in range(m):
            if not b[j]:
                continue
            sm.set_seq1(b[j])
            if sm.real_quick_ratio() < _MAP_MIN_RATIO or sm.quick_ratio() < _MAP_MIN_RATIO:
                continue
            r = sm.ratio()
            if r >= _MAP_MIN_RATIO:
                sim[i][j] = r

    # H[i][j]: best score aligning a[:i] with b[:j].
    h = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = h[i - 1][j - 1] + sim[i - 1][j - 1] if sim[i - 1][j - 1] else None
            skip = max(h[i - 1][j], h[i][j - 1]) - _MAP_GAP_COST
            h[i][j] = skip if best is None or skip > best else best

    mapping: dict[int, int] = {}
    i, j = n, m
    while i > 0 and j > 0:
        if sim[i - 1][j - 1] and h[i][j] == h[i - 1][j - 1] + sim[i - 1][j - 1]:
            mapping[i - 1] = j - 1
            i -= 1
            j -= 1
        elif h[i - 1][j] >= h[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return mapping


@dataclass
class SongScore:
    song: str
    n_lines: int  # lyric lines the matcher saw
    n_mapped: int  # lines paired with a reference cue
    n_scored: int  # paired lines the matcher actually placed
    offset_s: float  # fitted display-lead offset (median delta)
    median_abs_residual_s: float
    n_within_half_s: int  # raw counts so corpus pooling stays exact
    n_within_one_s: int
    pct_within_half_s: float
    pct_within_one_s: float
    gross_count: int  # |residual| > GROSS_RESIDUAL_S
    worst: list[dict] = field(default_factory=list)  # top offenders, for diagnosis
    ref: str = "yt-srt"  # timing reference kind: "yt-srt" or "lrclib"
    drift_s_per_min: float = 0.0  # fitted reference-clock drift (lrclib only)


def _fit_offset_and_drift(cue_starts: list[float], deltas: list[float]) -> tuple[float, float]:
    """Robust linear fit ``delta ≈ offset + drift * cue_start`` (Theil–Sen).

    Used for references whose clock is untrusted (LRCLIB synced to a
    different master): a constant tempo difference shows up as smooth
    drift in the deltas, which is reference artifact, not matcher error.
    Median-of-pairwise-slopes keeps structural breaks (inserted dialog
    sections) out of the fit so they still surface as gross residuals.
    """
    pts = sorted(zip(cue_starts, deltas))
    slopes = [
        (d2 - d1) / (t2 - t1)
        for i, (t1, d1) in enumerate(pts)
        for t2, d2 in pts[i + 1 :]
        if t2 > t1
    ]
    if not slopes:
        return median(deltas), 0.0
    drift = median(slopes)
    offset = median(d - drift * t for t, d in pts)
    return offset, drift


def score_song(
    song: str,
    placed_starts: dict[int, float],
    cue_starts_by_line: dict[int, float],
    line_texts: list[str],
    n_lines: int,
    worst_n: int = 5,
    ref: str = "yt-srt",
    fit_drift: bool = False,
) -> SongScore:
    """Score one song's placed line starts against its reference cues.

    Args:
        placed_starts: line_id -> matcher start time, placed lines only.
        cue_starts_by_line: line_id -> reference cue start time, mapped
            lines only.
        line_texts: full lyric line list (indexed by line_id) for the
            worst-offender report.
        n_lines: total lyric line count (denominator context).
        ref: timing-reference kind label carried into the score.
        fit_drift: also fit a linear reference-clock drift term (for
            references synced to a different master than the video).
    """
    scored_ids = sorted(set(placed_starts) & set(cue_starts_by_line))
    deltas = {lid: placed_starts[lid] - cue_starts_by_line[lid] for lid in scored_ids}
    if not scored_ids:
        return SongScore(
            song=song,
            n_lines=n_lines,
            n_mapped=len(cue_starts_by_line),
            n_scored=0,
            offset_s=0.0,
            median_abs_residual_s=0.0,
            n_within_half_s=0,
            n_within_one_s=0,
            pct_within_half_s=0.0,
            pct_within_one_s=0.0,
            gross_count=0,
            ref=ref,
        )
    offset = median(deltas.values())
    drift = 0.0
    residuals = {lid: d - offset for lid, d in deltas.items()}
    if fit_drift and len(scored_ids) >= 2:
        # Model selection: keep the drift fit only when it actually fits
        # better than a constant offset. Tempo-mismatch references improve
        # a lot; structural-break references (inserted dialog sections)
        # would drag the slope and must fall back to the constant fit.
        d_offset, d_drift = _fit_offset_and_drift(
            [cue_starts_by_line[lid] for lid in scored_ids],
            [deltas[lid] for lid in scored_ids],
        )
        d_residuals = {
            lid: d - (d_offset + d_drift * cue_starts_by_line[lid]) for lid, d in deltas.items()
        }
        if median(abs(r) for r in d_residuals.values()) < median(
            abs(r) for r in residuals.values()
        ):
            offset, drift, residuals = d_offset, d_drift, d_residuals
    abs_res = sorted(abs(r) for r in residuals.values())
    n = len(abs_res)
    worst_ids = sorted(residuals, key=lambda lid: abs(residuals[lid]), reverse=True)[:worst_n]
    worst = [
        {
            "line_id": lid,
            "residual_s": round(residuals[lid], 2),
            "text": line_texts[lid] if lid < len(line_texts) else "",
        }
        for lid in worst_ids
        if abs(residuals[lid]) > GROSS_RESIDUAL_S
    ]
    n_half = sum(1 for r in abs_res if r <= 0.5)
    n_one = sum(1 for r in abs_res if r <= 1.0)
    return SongScore(
        song=song,
        n_lines=n_lines,
        n_mapped=len(cue_starts_by_line),
        n_scored=n,
        offset_s=round(offset, 3),
        median_abs_residual_s=round(median(abs_res), 3),
        n_within_half_s=n_half,
        n_within_one_s=n_one,
        pct_within_half_s=round(100.0 * n_half / n, 1),
        pct_within_one_s=round(100.0 * n_one / n, 1),
        gross_count=sum(1 for r in abs_res if r > GROSS_RESIDUAL_S),
        worst=worst,
        ref=ref,
        drift_s_per_min=round(60.0 * drift, 2),
    )


def placed_starts_from_line_objects(line_objects: list[dict]) -> dict[int, float]:
    """line_id -> start for lines the matcher placed with real words.

    Interp/absent lines carry no words and are excluded — they never
    render, so they have no timing to evaluate.
    """
    return {
        obj["line_id"]: obj["start"]
        for obj in line_objects
        if obj.get("words") and obj.get("start") is not None
    }


def replay_joint_from_bundle(
    bundle: dict,
    *,
    alpha: float,
    margin_s: float,
    max_edit_ratio: float = 0.75,
    lookahead: int = 3,
    anchor_fallback: bool = True,
) -> tuple[list[dict], dict]:
    """Re-run the joint matcher from a debug bundle's cached inputs.

    Uses the bundle's ``lyrics.lines`` / ``lyrics.align_lines`` verbatim
    (NOT a re-cleaned version of the source SRT): the cached align words
    correspond 1:1 to the flat token stream of the *capture-time*
    align_lines, and that correspondence must be preserved. Re-cleaning
    is only ever applied on the reference-cue side of the eval.

    Raises KeyError/ValueError if the bundle lacks the cached inputs.
    """
    align_words = bundle["words"]
    transcribe_words = bundle["transcribe_words"]
    if not align_words or transcribe_words is None:
        raise ValueError(f"bundle {bundle.get('song_stem', '?')!r} lacks cached matcher inputs")
    lyrics = bundle["lyrics"]
    return match_words_to_lines_joint_with_stats(
        align_words,
        transcribe_words,
        lyrics["lines"],
        lyrics["align_lines"],
        alpha=alpha,
        margin_s=margin_s,
        max_edit_ratio=max_edit_ratio,
        lookahead=lookahead,
        anchor_fallback=anchor_fallback,
    )
