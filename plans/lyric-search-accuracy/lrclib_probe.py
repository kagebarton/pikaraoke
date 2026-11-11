"""Replay LRCLIB searches for each library song and cache the raw record lists (read-only)."""
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from pikaraoke.lib import lrclib
from pikaraoke.lib.metadata_parser import youtube_id_suffix

HERE = Path(__file__).parent
rows = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
cache_path = HERE / "lrclib_raw.jsonl"
cache = {}
if cache_path.exists():
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # a line cut short by an interrupted run
        cache[entry["key"]] = entry["records"]
PAREN = re.compile(r"\s*[(\[][^)\]]*[)\]]")


def parts(r):
    stem = Path(r["file"]).stem
    suffix = youtube_id_suffix(r["file"])
    name = stem[: -len(suffix)] if suffix else stem
    left, _, right = name.partition(" - ")
    movie = bool(re.search(r"\(\d{4}\)", left))
    return PAREN.sub("", left).strip(), PAREN.sub("", right or left).strip(), movie


def fetch(params: dict) -> list[dict]:
    key = json.dumps(params, sort_keys=True, ensure_ascii=False)
    if key not in cache:
        for attempt in range(4):
            try:
                resp = requests.get(lrclib.SEARCH_URL, params=params, headers={"User-Agent": lrclib.USER_AGENT}, timeout=40)
                resp.raise_for_status()
                cache[key] = resp.json()
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    cache[key] = {"error": str(e)}
                time.sleep(3 * (attempt + 1))
        with cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "records": cache[key]}, ensure_ascii=False) + chr(10))
        time.sleep(0.3)
    return cache[key]


def queries(r):
    left, title, movie = parts(r)
    g = r.get("genius") or {}
    if g.get("title"):
        track, artist = lrclib.clean_key(g["title"], g.get("artist") or "")
    else:
        track, artist = lrclib.clean_key(title, left)
    return {
        "field": {"track_name": track, "artist_name": artist},
        "q": {"q": f"{artist} {track}"},
        "title": {"track_name": track},
    }


if __name__ == "__main__":
    for i, r in enumerate(rows):
        movie = parts(r)[2]
        for name, params in queries(r).items():
            if name == "title" and not movie:
                continue  # title-only matters for film songs, whose "artist" is the film
            fetch(params)
    print(len(cache), "cached")
