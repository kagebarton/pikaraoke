"""Replay LRCLIB query shapes for each library song and cache the trimmed record lists (read-only)."""
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from pikaraoke.lib import lrclib

HERE = Path(__file__).parent
rows = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
cache_path = HERE / "lrclib_raw.jsonl"
cache, lock = {}, threading.Lock()
if cache_path.exists():
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # a line cut short by an interrupted run
        cache[entry["key"]] = entry["records"]
KEEP = ("id", "trackName", "artistName", "albumName", "duration", "instrumental", "syncedLyrics")
FIRST_ARTIST = re.compile(r"\s*(?:,|&| and | x | with )\s*", re.I)


def trim(rec: dict) -> dict:
    out = {k: rec.get(k) for k in KEEP}
    out["plain"] = bool(rec.get("plainLyrics"))
    return out


def key_of(endpoint: str, params: dict) -> str:
    return ("GET " if endpoint == "get" else "") + json.dumps(params, sort_keys=True, ensure_ascii=False)


def fetch(endpoint: str, params: dict):
    key = key_of(endpoint, params)
    if key in cache:
        return cache[key]
    url = "https://lrclib.net/api/get" if endpoint == "get" else lrclib.SEARCH_URL
    result = None
    for attempt in range(4):
        try:
            resp = requests.get(url, params=params, headers={"User-Agent": lrclib.USER_AGENT}, timeout=40)
            if endpoint == "get" and resp.status_code == 404:
                result = []
                break
            resp.raise_for_status()
            data = resp.json()
            result = [trim(data)] if endpoint == "get" else [trim(x) for x in data]
            break
        except (requests.RequestException, ValueError) as e:
            result = {"error": str(e)}
            time.sleep(3 * (attempt + 1))
    with lock:
        cache[key] = result
        with cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "records": result}, ensure_ascii=False) + chr(10))
    time.sleep(0.3)
    return result


def identity(r: dict) -> tuple[str, str]:
    """Title and artist a search would hold: the recorded Genius pick, else the answer key."""
    g = r.get("genius") or {}
    if g.get("title"):
        return lrclib.clean_key(g["title"], g.get("artist") or "")
    return lrclib.clean_key(r["title"], r.get("perf") or r.get("artist_q") or "")


def shapes(r: dict) -> dict:
    """Every query shape tried for a song: name -> (endpoint, params)."""
    track, artist = identity(r)
    out = {"title": ("search", {"track_name": track}), "qtitle": ("search", {"q": track})}
    if artist:  # (q_build is added below for every song)
        out["field"] = ("search", {"track_name": track, "artist_name": artist})
        out["q"] = ("search", {"q": f"{artist} {track}"})
        out["get"] = ("get", {"track_name": track, "artist_name": artist, "duration": round(r["dur"])})
        first = FIRST_ARTIST.split(artist)[0]
        if first and first != artist:
            out["field_first"] = ("search", {"track_name": track, "artist_name": first})
            out["get_first"] = ("get", {"track_name": track, "artist_name": first, "duration": round(r["dur"])})
    # The fit check's own search (plans/lrclib-fit-pick.md, "The search"): title then artist, free text.
    out["q_build"] = ("search", {"q": " ".join(t for t in (track, artist) if t)})
    alt = r.get("artist_alt")
    if alt and not (r.get("genius") or {}).get("title"):
        out["field_alt"] = ("search", {"track_name": track, "artist_name": alt})
        out["q_alt"] = ("search", {"q": f"{alt} {track}"})
        out["get_alt"] = ("get", {"track_name": track, "artist_name": alt, "duration": round(r["dur"])})
    if r.get("film"):
        film = r["film"]
        out["title_album"] = ("search", {"track_name": track, "album_name": film})
        out["q_film"] = ("search", {"q": f"{film} {track}"})
        out["field_film"] = ("search", {"track_name": track, "artist_name": film})
    return out


if __name__ == "__main__":
    jobs = [job for r in rows for job in shapes(r).values()]
    todo = [j for j in jobs if key_of(*j) not in cache]
    print(len(jobs), "queries,", len(todo), "to fetch", flush=True)
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, _ in enumerate(ex.map(lambda j: fetch(*j), todo), 1):
            if i % 100 == 0:
                print(i, flush=True)
    print(len(cache), "cached,", sum(1 for v in cache.values() if isinstance(v, dict)), "errors")
