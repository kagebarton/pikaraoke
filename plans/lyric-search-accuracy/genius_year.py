"""Film-named songs: does preferring the hit whose release year matches the file name's year pick
the film's recording? Re-fetches the two prototype queries with the release year (read-only)."""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import genius_probe as gp
from genius_variants import norm, parts
from pikaraoke.lib.lrclib import normalize_line

# Copied from genius_sim.py, which runs its replay on import.
VARIANT = re.compile(
    r"\b(parody|instrumental|karaoke|acapella|a cappella|remix|cover|commentary|translation|medley|"
    r"radio edit|live|demo|version|mix|edit|reprise|sped up|slowed|multilingual|suite|skit|snippet|mashup)\b",
    re.I,
)
STOP = {"the", "a", "an", "and", "of", "in", "to", "from", "feat", "ft", "with"}


def toks(s):
    return [t for t in normalize_line(s).split() if t not in STOP]


HERE = Path(__file__).parent
cache_path = HERE / "genius_year_raw.json"
cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}


def raw(query: str) -> list[dict]:
    if query not in cache:
        for attempt in range(4):
            try:
                data = gp.g.search(query, per_page=20, type_="song")
                break
            except Exception:  # scratch probe: retry any transient drop
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
                "state": h["result"].get("lyrics_state"),
                "instrumental": h["result"].get("instrumental"),
                "views": (h["result"].get("stats") or {}).get("pageviews"),
                "year": (h["result"].get("release_date_components") or {}).get("year"),
            }
            for h in hits
        ]
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.4)
    return cache[query]


def keep(hits):
    return [
        h
        for h in hits
        if h["type"] == "song"
        and ("genius" not in h["artist"].lower() or "romaniz" in h["artist"].lower())
        and "deleted artist" not in h["artist"].lower()
        and not h.get("instrumental")
    ]


def rank(hits, title, context, year, use_year):
    def key(h):
        full = norm(h["title"]) == norm(title)
        variant = bool(VARIANT.search(h["title"])) and not VARIANT.search(" ".join(context))
        near = h.get("year") is not None and abs(h["year"] - year) <= 1
        artist = any(t in set(context) for t in toks(h["artist"]))
        views = h["views"] or 0
        return (full, near, artist, not variant, views) if use_year else (full, artist, not variant, views)

    return sorted(hits, key=key, reverse=True)


with_year = without_year = 0
for r in gp.rows:
    left, title, movie = parts(r)
    if not movie:
        continue
    year = int(re.search(r"\((\d{4})\)", r["file"]).group(1))
    merged, seen = [], set()
    for q in (f"{left} {title}", title):
        for h in keep(raw(q)):
            if h["id"] not in seen:
                seen.add(h["id"])
                merged.append(h)
    context = toks(f"{left} {title}")
    full = [h for h in merged if norm(h["title"]) == norm(title)]
    with_year += sum(h.get("year") is not None for h in full)
    without_year += sum(h.get("year") is None for h in full)
    a = rank(merged, title, context, year, use_year=True)
    b = rank(merged, title, context, year, use_year=False)
    pick = a[0] if a else None
    old = b[0] if b else None

    def show(h):
        return f"{h['title'][:26]} / {h['artist'][:44]} ({h.get('year')}, {h['views'] or 0})" if h else "-"

    flag = " " if pick and old and pick["id"] == old["id"] else "*"
    print(f"{flag} {left[:20]:20} {year} | {title[:30]:30} | YEAR: {show(pick):84} | PROTO: {show(old)}")
print(f"\nfull-title hits carrying a year: {with_year}; without: {without_year}")
