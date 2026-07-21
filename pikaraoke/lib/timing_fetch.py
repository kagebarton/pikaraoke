"""Synced-timing fetch pillar: Musixmatch richsync/line + NetEase fallback.

The timing-source pillars router's fetch pillar (``plans/ctc-sync-engine.md``
Appendix A/B). Unlike LRCLIB (``pikaraoke.lib.lrclib``, used as a *fill*
source), Musixmatch richsync is word-level timing that can drive a line
directly, and Musixmatch/NetEase line timing is a denser, same-recording-rate
scaffold than LRCLIB's community submissions. Selection is reference-free,
mirroring ``lrclib.select_candidate``: rank each candidate by how well its
text maps to our lyric sheet (``lrclib.map_lines_to_cues``), tie-broken by
track length, so a right-text/wrong-sync (or wrong-song) candidate scores
low rather than winning blind.

Mechanism, in order (probed in ``plans/musixmatch-coverage-probe.md`` +
``plans/musixmatch-coverage-improvement.md``):

1. Musixmatch ``track.search`` on the full ``"title artist"`` query;
   richsync fetched first per candidate, subtitle (line) fetch as fallback.
   Title-only retried only when the full query yields nothing confident
   (below :data:`WRONG_SONG_MAP_RATE`) — saves the second round of API
   calls on the common case.
2. NetEase (line-only; ``syncedlyrics``' provider never surfaces word-level
   ``yrc``) only when Musixmatch comes up completely empty or scores 0.0.

Persists one sidecar per song (:func:`ensure_timing`'s disk-first contract,
mirroring ``lrclib.ensure_lrc``) so a re-add never re-queries. Never raises;
every failure degrades to no confident timing, logged.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import syncedlyrics
from syncedlyrics.providers import Musixmatch
from syncedlyrics.utils import get_cache_path

from pikaraoke.lib.lrclib import clean_key, map_lines_to_cues, parse_lrc_lines

logger = logging.getLogger(__name__)

SIDECAR_SCHEMA_VERSION = 1

# Pacing that survived a full 33-song corpus run without a persistent
# lockout (plans/musixmatch-coverage-improvement.md) -- see that plan's
# Robustness section before tightening either value. SONG_SLEEP_S (the
# between-*songs* pause) is deliberately absent here: fetch happens once
# per song at add time, so only the between-*call* pacing below applies;
# a batch tool iterating many songs adds its own SONG_SLEEP_S.
CALL_SLEEP_S = 2.5
BACKOFF_SLEEP_S = 20.0

# Below this map_rate a hit is not "confident" -- the wrong-song floor.
# Also the trigger for a title-only retry and for the NetEase-if-zero rule
# below it (a stricter subset: exactly 0.0, not just "below the bar").
WRONG_SONG_MAP_RATE = 0.5

TOKEN_PATH = get_cache_path("syncedlyrics", False) / "musixmatch_token.json"

# One shared instance for the process lifetime: both the token-throttle fix
# the probes needed and the guard against syncedlyrics' LRCProvider.__init__
# logging footgun (unconditional addHandler per instantiation -- a
# long-running server constructing one per song would pile up duplicate
# handlers). Created lazily so import alone never touches the network.
_client: Musixmatch | None = None


def _get_client() -> Musixmatch:
    global _client
    if _client is None:
        _client = Musixmatch(enhanced=False)
    return _client


def _mm_get(client: Musixmatch, action: str, params: list[tuple]) -> dict | None:
    """One Musixmatch call, with a single 401-triggered backoff+retry (fresh
    token). Any other non-200 (404 = no content for this track, etc.) is a
    clean miss, not a throttle -- return ``None`` immediately."""
    response = client._get(action, list(params))  # pylint: disable=protected-access
    code = response.json().get("message", {}).get("header", {}).get("status_code")
    if code == 401:
        logger.info(
            "Timing fetch: %s -> 401, backing off %ss + fresh token", action, BACKOFF_SLEEP_S
        )
        time.sleep(BACKOFF_SLEEP_S)
        TOKEN_PATH.unlink(missing_ok=True)
        client.token = None
        response = client._get(action, list(params))  # pylint: disable=protected-access
        code = response.json().get("message", {}).get("header", {}).get("status_code")
    return response.json() if code == 200 else None


def candidate_lyrics(client: Musixmatch, track_id: int) -> tuple[str, object | None]:
    """``(kind, body)`` for one Musixmatch candidate: richsync first, else
    line-level subtitle. ``body`` is the raw richsync entry list (``kind ==
    "word"``) or the LRC subtitle text (``kind == "line"``) -- the exact
    shape the sidecar persists (Appendix B), so no lossy conversion happens
    between fetch and disk.
    """
    data = _mm_get(client, "track.richsync.get", [("track_id", track_id)])
    if data and data["message"]["body"].get("richsync"):
        entries = json.loads(data["message"]["body"]["richsync"]["richsync_body"])
        return "word", entries
    time.sleep(CALL_SLEEP_S)
    data = _mm_get(
        client, "track.subtitle.get", [("track_id", track_id), ("subtitle_format", "lrc")]
    )
    if data and data["message"]["body"]:
        return "line", data["message"]["body"]["subtitle"]["subtitle_body"]
    return "none", None


def _richsync_cue_texts(entries: list[dict]) -> list[str]:
    """Per-entry joined word text, for mapping richsync lines onto our sheet."""
    return ["".join(w.get("c", "") for w in entry.get("l", [])) for entry in entries]


def _map_rate_for(kind: str, body: object | None, sheet: list[str]) -> float:
    if not body or not sheet:
        return 0.0
    if kind == "word":
        cue_texts = _richsync_cue_texts(body)
    elif kind == "line":
        cue_texts, _ = parse_lrc_lines(body)
    else:
        return 0.0
    if not cue_texts:
        return 0.0
    return len(map_lines_to_cues(sheet, cue_texts)) / len(sheet)


def best_by_reference(
    client: Musixmatch, term: str, sheet: list[str], media_dur: float | None
) -> dict | None:
    """Best-scoring viable Musixmatch candidate for one query term, or
    ``None``. Skips instrumental/no-lyrics candidates without spending a
    lyrics-fetch call on them."""
    data = _mm_get(client, "track.search", [("q", term), ("page_size", "5"), ("page", "1")])
    if not data:
        return None
    best_key: tuple[float, float] | None = None
    best_row: dict | None = None
    for entry in data["message"]["body"].get("track_list", []):
        track = entry["track"]
        if track.get("instrumental") or not (
            track.get("has_subtitles") or track.get("has_richsync")
        ):
            continue
        time.sleep(CALL_SLEEP_S)
        kind, body = candidate_lyrics(client, track["track_id"])
        rate = _map_rate_for(kind, body, sheet)
        length = track.get("track_length") or 0
        dur_key = -abs(length - media_dur) if media_dur else 0.0
        key = (rate, dur_key)
        row = {
            "track_id": track["track_id"],
            "track_name": track["track_name"],
            "artist_name": track["artist_name"],
            "track_length": length,
            "kind": kind,
            "body": body,
            "map_rate": round(rate, 3),
        }
        if best_key is None or key > best_key:
            best_key, best_row = key, row
    return best_row


def reference_pick(
    client: Musixmatch, title: str, artist: str, sheet: list[str], media_dur: float | None
) -> dict | None:
    """Best Musixmatch candidate across query variants, tagged with the
    winning ``term``/``variant``.

    Full ``"title artist"`` first; the title-only retry only fires when the
    full query came back with nothing confident (below
    :data:`WRONG_SONG_MAP_RATE`), so the common (already-confident) case
    costs one query round, not two.
    """
    full = f"{title} {artist}".strip()
    time.sleep(CALL_SLEEP_S)
    pick = best_by_reference(client, full, sheet, media_dur)
    if pick is not None and pick["map_rate"] >= WRONG_SONG_MAP_RATE:
        return {**pick, "term": full, "variant": "full"}
    if title and title != full:
        time.sleep(CALL_SLEEP_S)
        title_pick = best_by_reference(client, title, sheet, media_dur)
        if title_pick is not None and (pick is None or title_pick["map_rate"] > pick["map_rate"]):
            return {**title_pick, "term": title, "variant": "title-only"}
    return {**pick, "term": full, "variant": "full"} if pick is not None else None


def _netease_fallback(term: str, sheet: list[str]) -> dict | None:
    """NetEase as a last resort: line-only (the installed ``syncedlyrics``
    provider never surfaces word-level ``yrc``)."""
    body = syncedlyrics.search(term, providers=["NetEase"], synced_only=True)
    if not body:
        return None
    rate = _map_rate_for("line", body, sheet)
    return {
        "track_id": None,
        "track_name": None,
        "artist_name": None,
        "track_length": None,
        "kind": "line",
        "body": body,
        "map_rate": round(rate, 3),
        "term": term,
        "variant": "netease",
    }


def _sidecar_path(song_path: Path) -> Path:
    return song_path.parent / "lyrics" / f"{song_path.stem}.timing.json"


def _empty_sidecar(term: str) -> dict:
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "query": {"term": term, "variant": "full"},
        "source": "none",
        "kind": "none",
        "map_rate": 0.0,
        "track": {},
        "body": None,
    }


def _fetch_and_build_sidecar(
    title: str, artist: str, sheet: list[str], media_dur: float | None
) -> dict:
    client = _get_client()
    pick = reference_pick(client, title, artist, sheet, media_dur)
    if pick is None or pick["map_rate"] == 0.0:
        netease = _netease_fallback(f"{title} {artist}".strip(), sheet)
        if netease is not None and (pick is None or netease["map_rate"] > pick["map_rate"]):
            pick = netease
    if pick is None:
        return _empty_sidecar(f"{title} {artist}".strip())
    source = "netease" if pick["variant"] == "netease" else "musixmatch"
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "query": {"term": pick["term"], "variant": pick["variant"]},
        "source": source,
        "kind": pick["kind"],
        "map_rate": pick["map_rate"],
        "track": {
            "track_id": pick["track_id"],
            "track_name": pick["track_name"],
            "artist_name": pick["artist_name"],
            "track_length": pick["track_length"],
        },
        "body": pick["body"],
    }


def _load_sidecar(path: Path) -> dict | None:
    """Parsed sidecar, or ``None`` if unreadable/missing ``schema_version``
    (the corrupt-sidecar case: caller treats this as absent and refetches)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "schema_version" in data else None


def _write_sidecar(path: Path, sidecar: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sibling tmp + rename: an interrupted write must never leave a truncated
    # sidecar for ensure_timing's is_file() check to trust (mirrors write_lrc).
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    tmp.replace(path)


def _artifact_from_sidecar(sidecar: dict, path: Path) -> dict | None:
    """Appendix A artifact dict from a sidecar, or ``None`` below the
    confidence bar (a low/no-confidence sidecar is still persisted -- see
    :func:`ensure_timing` -- but never stashed for a router to consume)."""
    if sidecar.get("kind") not in ("word", "line"):
        return None
    if sidecar.get("map_rate", 0.0) < WRONG_SONG_MAP_RATE:
        return None
    return {
        "kind": sidecar["kind"],
        "path": path,
        "source": sidecar.get("source"),
        "map_rate": sidecar["map_rate"],
        "track": sidecar.get("track", {}),
    }


def ensure_timing(
    song_path: Path,
    title: str,
    artist: str,
    sheet_lines: list[str],
    media_dur: float | None,
) -> dict | None:
    """``lyrics/<stem>.timing.json`` for ``song_path``: reuse on disk, else
    fetch + select + persist. Mirrors :func:`lrclib.ensure_lrc`'s shape.

    Returns the Appendix A artifact dict when a confident (``map_rate >=``
    :data:`WRONG_SONG_MAP_RATE`) word/line timing is available, ``None``
    otherwise -- including when a sidecar exists but never reached
    confidence (still authoritative; no refetch). An existing *parseable*
    sidecar of any source, including a ``"none"`` miss, is authoritative;
    only a corrupt/missing-schema sidecar triggers a refetch. Never raises.

    ``title``/``artist`` are cleaned via :func:`lrclib.clean_key` up front
    (idempotent, mirroring :func:`lrclib.search` -- callers may pass raw
    Genius strings or already-cleaned keys); every downstream use, including
    the exception-path empty sidecar's recorded ``query.term``, sees only
    the cleaned form.
    """
    title, artist = clean_key(title, artist)
    path = _sidecar_path(song_path)
    if path.is_file():
        sidecar = _load_sidecar(path)
        if sidecar is not None:
            return _artifact_from_sidecar(sidecar, path)
        logger.warning("Timing fetch: corrupt sidecar %s — refetching", path)
    try:
        sidecar = _fetch_and_build_sidecar(title, artist, sheet_lines, media_dur)
    except Exception:
        logger.exception("Timing fetch: failed for %r by %r", title, artist)
        sidecar = _empty_sidecar(f"{title} {artist}".strip())
    try:
        _write_sidecar(path, sidecar)
    except OSError:
        logger.exception("Timing fetch: could not persist sidecar %s", path)
        return None
    return _artifact_from_sidecar(sidecar, path)
