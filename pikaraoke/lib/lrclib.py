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
right-text/wrong-sync variant bails safely rather than mis-repairing. See
``plans/lrclib-timing-prior.md``.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import requests

from pikaraoke.lib.alignment_eval import (
    cue_spans_from_lrc,
    map_lines_to_cues,
    parse_lrc_lines,
)

logger = logging.getLogger(__name__)

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
