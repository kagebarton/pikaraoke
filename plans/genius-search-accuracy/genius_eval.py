"""Score the cached Genius hit lists against each song's curated name."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from pikaraoke.lib.genius_lyrics import clean_genius_query
from pikaraoke.lib.lrclib import normalize_line
from pikaraoke.lib.metadata_parser import youtube_id_suffix

HERE = Path(__file__).parent
rows = json.loads((HERE / "truth.json").read_text(encoding="utf-8"))
cache = json.loads((HERE / "genius_raw.json").read_text(encoding="utf-8"))
PAREN = re.compile(r"\s*[(\[][^)\]]*[)\]]")


def norm(s):
    return normalize_line(PAREN.sub("", s))


def app_filter(hits, query):
    blocked = "translation" if "genius" in query.lower() else "genius"
    out = []
    for h in hits:
        if h["type"] != "song":
            continue
        a = h["artist"].lower()
        if blocked in a and "romaniz" not in a:
            continue
        out.append(h)
    return out[:8]


def truth(r):
    stem = Path(r["file"]).stem
    suffix = youtube_id_suffix(r["file"])
    name = stem[: -len(suffix)] if suffix else stem
    left, _, right = name.partition(" - ")
    return left, right or left


def correct(h, artist, title, genius):
    if genius and h["id"] == genius.get("id"):
        return True
    ht, t = norm(h["title"]), norm(title)
    if not ht or not t:
        return h["title"].strip() and h["title"].split("(")[0].strip() in title
    return ht == t


def rank(hits, artist, title, genius):
    for i, h in enumerate(hits, 1):
        if correct(h, artist, title, genius):
            return i
    return None


verbose = "-v" in sys.argv
for label, key in (("today's file name", "query"), ("original YouTube title", "old_title")):
    tally = Counter()
    notes = []
    for r in rows:
        src = r.get(key)
        if not src:
            continue
        q = clean_genius_query(src)
        hits = cache.get(q, [])
        artist, title = truth(r)
        shown = app_filter(hits, q)
        rk, raw_rk = rank(shown, artist, title, r.get("genius")), rank(hits, artist, title, r.get("genius"))
        bucket = "first" if rk == 1 else "listed 2-8" if rk else "filtered or past 8" if raw_rk else "absent" if hits else "no hits"
        tally[bucket] += 1
        if bucket != "first":
            notes.append((bucket, r["file"], q, rk, raw_rk, shown[:4], len(hits)))
    print(f"\n== {label}: {sum(tally.values())} songs ==")
    for k, v in tally.most_common():
        print(f"  {k}: {v}")
    if verbose:
        for bucket, file, q, rk, raw_rk, shown, n in notes:
            print(f"\n[{bucket}] {file}\n   q={q!r} rank={rk} raw_rank={raw_rk} raw_n={n}")
            for h in shown:
                print(f"     {h['title']} — {h['artist']} ({h['state']}, {h['views']})")
