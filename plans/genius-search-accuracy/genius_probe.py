"""Replay each song's starting Genius query and dump the raw hit list (read-only)."""
import configparser
import json
import time
from pathlib import Path

import lyricsgenius

from pikaraoke.lib.genius_lyrics import clean_genius_query
from pikaraoke.lib.metadata_parser import youtube_id_suffix

HERE = Path(__file__).parent
cfg = configparser.ConfigParser()
cfg.read(Path.home() / ".pikaraoke" / "config.ini")
token = next(cfg[s]["genius_token"] for s in cfg.sections() if "genius_token" in cfg[s])
g = lyricsgenius.Genius(token, timeout=15)
rows = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
cache_path = HERE / "genius_raw.json"
cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}


def raw(query: str) -> list[dict]:
    if query not in cache:
        for attempt in range(4):
            try:
                data = g.search(query, per_page=20, type_="song")
                break
            except Exception as e:  # scratch probe: retry any transient drop
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        hits = (data.get("sections") or [{}])[0].get("hits", [])
        cache[query] = [
            {
                "type": h.get("type"),
                "id": h["result"]["id"],
                "title": h["result"]["title"],
                "artist": h["result"].get("artist_names") or h["result"]["primary_artist"]["name"],
                "primary": h["result"]["primary_artist"]["name"],
                "state": h["result"].get("lyrics_state"),
                "views": (h["result"].get("stats") or {}).get("pageviews"),
            }
            for h in hits
        ]
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.4)
    return cache[query]


for r in rows:
    old = r.get("old_stem") or ""
    suffix = youtube_id_suffix(old + ".mp4")
    old_title = old[: -len(suffix)] if suffix else old
    r["old_title"] = old_title
    for q in {clean_genius_query(r["query"]), clean_genius_query(old_title) if old_title else ""}:
        if q:
            raw(q)
(HERE / "truth.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
# The committed copy: the same rows without their lyric lines (truth.json itself is gitignored).
names = [{k: v for k, v in r.items() if k != "lines"} for r in rows]
(HERE / "truth_names.json").write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(cache), "queries cached")
