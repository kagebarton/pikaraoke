"""LRCLIB synced-lyrics fetch + selection for the txt-sourced timing prior.

Genius-origin (txt) songs reach the matcher with no per-line cue times, so the
timing prior that repairs/fills SRT-sourced songs has nothing to work with.
LRCLIB (https://lrclib.net) hosts community synced lyrics; this module fetches
the best-matching synced variant at processing time and persists it as a
``.lrc`` beside the song, so the prior (``pikaraoke/lib/srt_prior.py``) can
repair gross-misplaced lines and fill lines the audio could not place.

Selection is reference-free: rank candidates by how well their text maps to our
lyric sheet (``map_lines_to_cues``), with the video duration as a tiebreak. The
shipped anchor-MAD gate inside the prior vets the *timing* at match time, so a
right-text/wrong-sync variant bails safely rather than mis-repairing.
"""

from __future__ import annotations

import difflib
import logging
import re
import time
from pathlib import Path

import requests

from pikaraoke.lib.token_align import fold_to_ascii

logger = logging.getLogger(__name__)


# Straight/curly apostrophes, backtick, acute accent.
_APOSTROPHES = re.compile("['‘’`´]")
_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_LRC_STAMP = re.compile(r"\[(\d+):(\d{2}(?:\.\d+)?)\]")


def normalize_line(text: str) -> str:
    """Casefolded, alphanumeric-only form used to pair lyric lines with
    reference cues. Tolerant of cleanup drift (HTML tags older cleanup
    kept, quote styles, musical-note glyphs, punctuation). Apostrophes
    are deleted (not space-replaced) so "don't" == "dont".
    Homoglyphs/diacritics are ASCII-folded so a Cyrillic-watermarked line
    still pairs with its reference cue.
    """
    # Apostrophes must be deleted before folding: NFKD decomposes the
    # acute accent (U+00B4) into space + combining mark, which would turn
    # "don´t" into "don t" instead of "dont".
    text = _APOSTROPHES.sub("", _HTML_TAG.sub(" ", text.lower()))
    return " ".join(_NON_ALNUM.sub(" ", fold_to_ascii(text)).split())


def parse_lrc_lines(lrc_text: str) -> tuple[list[str], list[float]]:
    """Texts and start seconds from LRC synced lyrics (LRCLIB exports).

    Used as a *timing reference only* — LRCLIB text variants are too
    inconsistent to feed the matcher (no quality control), but a synced
    variant's line *deltas* are usually sound. The absolute clock often
    differs from the video (different master/edit), so only the deltas
    are used.

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


# LRCLIB synced lines carry only a start stamp; the timing prior needs a
# span. End each line at the next line's start and hold the final line
# this long — long enough to re-space a sung line's words, which is all
# the fill path does with the end (no later cue bounds it).
LRC_LAST_LINE_HOLD_S = 4.0


def cue_spans_from_lrc(lrc_text: str) -> tuple[list[str], list[tuple[float, float]]]:
    """Cleaned cue texts and ``(start, end)`` spans from LRC synced lyrics.

    The LRC adapter for :func:`pikaraoke.lib.srt_prior.apply_srt_prior`,
    parallel to :func:`pikaraoke.lib.srt_prior.cue_spans_from_srt`:
    LRCLIB exports stamp only starts, so each line ends at the next
    start, and the last line holds ``LRC_LAST_LINE_HOLD_S`` seconds.
    """
    texts, starts = parse_lrc_lines(lrc_text)
    spans = [
        (starts[i], starts[i + 1] if i + 1 < len(starts) else starts[i] + LRC_LAST_LINE_HOLD_S)
        for i in range(len(starts))
    ]
    return texts, spans


# Minimum per-line text similarity for a line/cue pair to count as a
# match in the mapping alignment. Below this, lines reworded by cleanup
# drift fall out of the mapping instead of pairing wrongly. Corpus-swept
# 2026-06-11: 0.65 admits cross-split mis-pairs ("a whole new world" ~
# "whole new world with you"); 0.85 drops them while keeping
# g-dropping/prefix drift ("waitin'"/"waiting") paired.
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


SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "pikaraoke (https://github.com/vicwomg/pikaraoke)"
_REQUEST_TIMEOUT_S = 30.0
# Politeness delay after a live query, per LRCLIB's API guidelines.
_POLITE_SLEEP_S = 0.3

# Trailing feature credits ("(Ft. Yebba)", "feat. X") and trailing
# parenthetical/bracket qualifiers ("(Live At Abbey Road)") that make LRCLIB's
# structured track/artist search miss the canonical recording (step-1
# SEARCH-MISS, plans/lrclib-timing-prior.md). Feature credits first (they often
# sit inside the parens). Only *trailing* groups are stripped — a leading
# parenthetical is usually part of the title ("(I Can't Get No) Satisfaction").
_FEAT_RE = re.compile(r"\s*[(\[]?\s*(?:feat\.?|ft\.?|featuring)\b.*$", re.IGNORECASE)
_TRAILING_PAREN_RE = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*$")

# Header ID tags written into / read back from the persisted .lrc. Maps the
# tag name to the LRCLIB record field it carries.
_TAG_TO_FIELD = {"ti": "trackName", "ar": "artistName", "al": "albumName", "lrclib_id": "id"}
_ID_TAG_RE = re.compile(r"^\[(\w+):(.*)\]$")

_RECORD_FIELDS = ("id", "trackName", "artistName", "albumName", "duration")


def clean_key(track_name: str, artist_name: str) -> tuple[str, str]:
    """Tidy a Genius title/artist into an LRCLIB structured-search key.

    Drops feature credits and trailing parenthetical/bracket qualifiers so a
    ``track_name`` + ``artist_name`` search reaches the canonical recording.
    Falls back to the original (stripped) value if cleaning empties a field.
    """
    track = _strip_trailing_parens(_FEAT_RE.sub("", track_name))
    artist = _strip_trailing_parens(_FEAT_RE.sub("", artist_name))
    return track or track_name.strip(), artist or artist_name.strip()


def _strip_trailing_parens(text: str) -> str:
    """Remove all trailing parenthetical/bracket groups (e.g. multiple
    ``(Remastered) (Live)`` qualifiers); leave a leading group intact."""
    prev = None
    while prev != text:
        prev = text
        text = _TRAILING_PAREN_RE.sub("", text).strip()
    return text


def search(track_name: str, artist_name: str, *, timeout: float = _REQUEST_TIMEOUT_S) -> list[dict]:
    """``GET /api/search`` for synced candidates. Returns ``[]`` on any failure.

    Inputs are cleaned with :func:`clean_key` (idempotent), so callers may pass
    raw or pre-cleaned keys.
    """
    track, artist = clean_key(track_name, artist_name)
    try:
        resp = requests.get(
            SEARCH_URL,
            params={"track_name": track, "artist_name": artist},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
        records = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("LRCLIB search failed for %r / %r: %s", track, artist, e)
        return []
    time.sleep(_POLITE_SLEEP_S)
    return records if isinstance(records, list) else []


def select_candidate(records: list[dict], sheet: list[str], media_dur: float | None) -> dict | None:
    """Reference-free pick: the synced candidate whose text best maps to our
    lyric ``sheet``, ties broken toward the media's duration.

    No timing ground truth is consulted — this is the choice production makes;
    the prior's anchor-MAD gate makes the timing cut afterward.
    """
    best: dict | None = None
    best_key: tuple[float, float] | None = None
    for r in records:
        synced = r.get("syncedLyrics")
        if not synced:
            continue
        cand_texts, _ = parse_lrc_lines(synced)
        if not cand_texts:
            continue
        map_rate = len(map_lines_to_cues(sheet, cand_texts)) / len(sheet) if sheet else 0.0
        try:
            dur = float(r.get("duration") or 0.0)
        except (TypeError, ValueError):
            dur = 0.0
        dur_key = -abs(dur - media_dur) if media_dur is not None else 0.0
        key = (map_rate, dur_key)
        if best_key is None or key > best_key:
            best, best_key = r, key
    return best


def cue_spans_for_lines(
    synced_text: str, lines: list[str]
) -> dict[int, tuple[float, float]] | None:
    """Map a variant's LRC cue spans onto our lyric ``lines`` by text.

    Returns ``{line_id: (start, end)}`` for the lines that mapped, or ``None``
    when nothing maps (the prior then no-ops).
    """
    cue_texts, spans = cue_spans_from_lrc(synced_text)
    mapping = map_lines_to_cues(lines, cue_texts)
    return {lid: spans[ci] for lid, ci in mapping.items()} or None


def record_meta(record: dict) -> dict:
    """The provenance subset of an LRCLIB record (no syncedLyrics body)."""
    return {field: record.get(field) for field in _RECORD_FIELDS}


def write_lrc(path: Path, record: dict) -> None:
    """Persist ``record``'s synced lyrics to ``path`` with a provenance header.

    The header uses standard LRC ID tags plus ``[lrclib_id:...]``;
    :func:`parse_lrc_lines` ignores any line without a leading ``[mm:ss]``
    stamp, so the header never leaks into the cue parse.
    """
    header = []
    for tag, field in (("ti", "trackName"), ("ar", "artistName"), ("al", "albumName")):
        value = record.get(field)
        if value:
            header.append(_format_tag(tag, value))
    length = _length_tag(record.get("duration"))
    if length:
        header.append(f"[length:{length}]")
    if record.get("id") is not None:
        header.append(f"[lrclib_id:{record['id']}]")

    body = record.get("syncedLyrics") or ""
    text = "".join(f"{line}\n" for line in header) + body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_lrc(path: Path) -> tuple[str, dict]:
    """Return ``(synced_text, record_meta)`` from a persisted ``.lrc``.

    ``synced_text`` is the full file (its header tags are harmless to the cue
    parser); ``record_meta`` reconstructs provenance from the ID-tag header.
    """
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    for line in text.splitlines():
        m = _ID_TAG_RE.match(line.strip())
        if not m:
            continue
        tag, value = m.group(1), m.group(2)
        field = _TAG_TO_FIELD.get(tag)
        if field:
            meta[field] = value
        elif tag == "length":
            meta["duration"] = _length_to_seconds(value)
    if "id" in meta:
        try:
            meta["id"] = int(meta["id"])
        except ValueError:
            pass
    return text, meta


def _format_tag(tag: str, value: object) -> str:
    """An LRC ID tag with the value sanitised so it can't break the brackets."""
    safe = str(value).replace("\n", " ").replace("]", ")")
    return f"[{tag}:{safe}]"


def _length_tag(duration: object) -> str | None:
    """``mm:ss`` length tag from a duration in seconds, or None if absent."""
    try:
        total = int(round(float(duration)))
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return f"{total // 60:02d}:{total % 60:02d}"


def _length_to_seconds(length: str) -> float | None:
    """Inverse of :func:`_length_tag`: ``mm:ss`` → seconds (whole-second
    precision; sub-second detail is lost in the round-trip)."""
    try:
        minutes, seconds = length.split(":")
        return float(int(minutes) * 60 + int(seconds))
    except (ValueError, AttributeError):
        return None
