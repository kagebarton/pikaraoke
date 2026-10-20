"""Phase 0b: fetch every lyric source for the pilot songs and save each raw, side by side.

Writes, per song, <PROBE_ROOT>/phase0/sheets_raw/<video_id>/ with one file per
source hit plus a sources.txt that stacks every source's text under a header so
they can be compared in one editor window. Ken picks or hand-edits one sheet and
saves it as <PROBE_ROOT>/sheets/<video_id>.txt; nothing here chooses.

Run: uv run --with syncedlyrics python scripts/zh_probe/fetch_sheets.py
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

from corpus import LRC_STAMP_RE, PILOT, RAW_DIR, Song  # noqa: E402

from pikaraoke.lib import lrclib  # noqa: E402
from pikaraoke.lib.genius import GeniusClient, GeniusUnavailable  # noqa: E402

logger = logging.getLogger("zh_probe.fetch_sheets")

GENIUS_FETCH_LIMIT = 4
LRCLIB_ATTEMPTS = 3
NETEASE_LYRIC_URL = "https://music.163.com/api/song/lyric"


def genius_token() -> str:
    cfg = configparser.ConfigParser()
    cfg.read(Path(os.environ["APPDATA"]) / "pikaraoke" / "config.ini", encoding="utf-8")
    return cfg.get("USERPREFERENCES", "genius_token", fallback="")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def fetch_genius(song: Song, out: Path, client: GeniusClient) -> list[dict]:
    seen: dict[int, dict] = {}
    for query in song.genius_queries:
        for hit in client.search(query, limit=GENIUS_FETCH_LIMIT):
            seen.setdefault(hit.id, {"id": hit.id, "title": hit.title, "artist": hit.artist})
    rows = []
    for hit in list(seen.values())[: GENIUS_FETCH_LIMIT * 2]:
        row = dict(hit, source="genius")
        try:
            row["text"] = client.fetch_lyrics(hit["id"])
            row["file"] = f"genius_{hit['id']}.txt"
            write(out / row["file"], row["text"])
        except GeniusUnavailable as e:
            row["error"] = str(e)
        rows.append(row)
    return rows


def search_lrclib(track: str, artist: str) -> list[dict]:
    """lrclib.search returns [] on a 503 as well as on no match, so an empty answer is retried."""
    for attempt in range(LRCLIB_ATTEMPTS):
        records = lrclib.search(track, artist)
        if records:
            return records
        time.sleep(2 * (attempt + 1))
    return []


def fetch_lrclib(song: Song, out: Path) -> list[dict]:
    """Keep records whose track name carries one of the song's titles.

    LRCLIB's artist+track search also returns the artist's other songs; the
    dropped ids are listed in a ``lrclib_dropped`` row so nothing vanishes silently.
    """
    titles = {track.casefold() for track, _ in song.keys}
    seen: dict[int, dict] = {}
    for track, artist in song.keys:
        for record in search_lrclib(track, artist):
            seen.setdefault(record["id"], record)
    kept = {
        rid: r
        for rid, r in seen.items()
        if any(t in (r.get("trackName") or "").casefold() for t in titles)
    }
    rows = [
        {
            "source": "lrclib_dropped",
            "n": len(seen) - len(kept),
            "ids": [rid for rid in seen if rid not in kept],
        }
    ]
    for record in kept.values():
        row = {"source": "lrclib", **lrclib.record_meta(record)}
        stem = f"lrclib_{record['id']}"
        plain, synced = record.get("plainLyrics"), record.get("syncedLyrics")
        if plain:
            write(out / f"{stem}.txt", plain)
            row["file"] = f"{stem}.txt"
            row["text"] = plain
        if synced:
            write(out / f"{stem}.lrc", synced)
            row["synced_file"] = f"{stem}.lrc"
            row.setdefault("text", LRC_STAMP_RE.sub("", synced))
        rows.append(row)
    return rows


def fetch_netease(song: Song, out: Path) -> list[dict]:
    from syncedlyrics.providers.netease import NetEase

    provider = NetEase()
    seen: dict[int, dict] = {}
    for track, artist in song.keys:
        try:
            hit = provider.search_track(f"{track} {artist}")
        except (requests.RequestException, ValueError) as e:
            logger.warning("NetEase search failed for %r %r: %s", track, artist, e)
            continue
        if hit:
            seen.setdefault(hit["id"], hit)
    for track_id in song.netease_ids:
        seen.setdefault(track_id, {"id": track_id, "name": None, "artists": []})
    rows = []
    for track_id, hit in seen.items():
        row = {
            "source": "netease",
            "id": track_id,
            "title": hit.get("name"),
            "artist": (hit.get("artists") or [{}])[0].get("name"),
            "by_hand_id": track_id in song.netease_ids,
        }
        try:
            data = provider.session.get(
                NETEASE_LYRIC_URL, params={"id": track_id, "lv": 1, "kv": 1, "tv": -1, "yv": 1}
            ).json()
        except (requests.RequestException, ValueError) as e:
            row["error"] = str(e)
            rows.append(row)
            continue
        lrc = (data.get("lrc") or {}).get("lyric") or ""
        if lrc:
            row["synced_file"] = f"netease_{track_id}.lrc"
            write(out / row["synced_file"], lrc)
            row["text"] = LRC_STAMP_RE.sub("", lrc)
        # yrc is the current word-timed format, klyric the older one; keep both
        # when offered, as possible Phase 3 references.
        for key, ext in (("yrc", "yrc"), ("klyric", "klyric")):
            body = (data.get(key) or {}).get("lyric") or ""
            row[f"has_{key}"] = bool(body)
            if body:
                row[f"{key}_file"] = f"netease_{track_id}.{ext}"
                write(out / row[f"{key}_file"], body)
        rows.append(row)
    return rows


def write_side_by_side(song: Song, out: Path, rows: list[dict]) -> None:
    parts = [f"# #{song.num} {song.title} [{song.video_id}] lang={song.lang}\n"]
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(re.sub(r"\s+", "", row.get("text") or ""), []).append(row)
    for key, group in groups.items():
        metas = [{k: v for k, v in r.items() if k not in ("text", "error")} for r in group]
        header = "\n".join(json.dumps(m, ensure_ascii=False) for m in metas)
        parts.append(f"\n{'=' * 70}\n{header}\n{'=' * 70}\n")
        parts.append(group[0].get("text") or f"(no text: {group[0].get('error', 'empty')})")
    write(out / "sources.txt", "\n".join(parts))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    client = GeniusClient(genius_token())
    for song in PILOT:
        out = RAW_DIR / song.video_id
        out.mkdir(parents=True, exist_ok=True)
        rows = fetch_genius(song, out, client) + fetch_lrclib(song, out) + fetch_netease(song, out)
        write(
            out / "index.json",
            json.dumps(
                [{k: v for k, v in r.items() if k != "text"} for r in rows],
                ensure_ascii=False,
                indent=1,
            ),
        )
        write_side_by_side(song, out, rows)
        logger.info("#%d %s: %d source hits", song.num, song.title, len(rows))


if __name__ == "__main__":
    main()
