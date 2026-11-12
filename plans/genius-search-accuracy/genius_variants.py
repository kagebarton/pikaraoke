"""Compare query shapes for the curated 'Left - Title' names against Genius."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import genius_probe as gp  # reuses its cache + raw()
from pikaraoke.lib.lrclib import normalize_line
from pikaraoke.lib.metadata_parser import youtube_id_suffix

PAREN = re.compile(r"\s*[(\[][^)\]]*[)\]]")
STOP = {"the", "and", "a", "of", "cast", "feat", "ft"}


def norm(s):
    return normalize_line(PAREN.sub("", s))


def parts(r):
    stem = Path(r["file"]).stem
    suffix = youtube_id_suffix(r["file"])
    name = stem[: -len(suffix)] if suffix else stem
    left, _, right = name.partition(" - ")
    movie = bool(re.search(r"\(\d{4}\)", left))
    return PAREN.sub("", left).strip(), PAREN.sub("", right or left).strip(), movie


def app_filter(hits):
    return [h for h in hits if h["type"] == "song" and ("genius" not in h["artist"].lower() or "romaniz" in h["artist"].lower())]


def correct(h, left, title, movie, genius):
    if genius and h["id"] == genius.get("id"):
        return True
    if norm(h["title"]) != norm(title) or not norm(title):
        return False
    if movie:
        return True
    want = set(normalize_line(left).split()) - STOP
    have = set(normalize_line(h["artist"]).split())
    return bool(want & have) or not want


VARIANTS = {
    "Left - Title (today)": lambda l, t: f"{l} - {t}",
    "Left Title": lambda l, t: f"{l} {t}",
    "Title Left": lambda l, t: f"{t} {l}",
    "Title only": lambda l, t: t,
}
which = sys.argv[1] if len(sys.argv) > 1 else "all"
res = {}
for name, build in VARIANTS.items():
    for kind in ("artist", "movie"):
        res[(name, kind)] = Counter()
detail = []
for r in gp.rows:
    left, title, movie = parts(r)
    if not title or left == title:
        continue
    kind = "movie" if movie else "artist"
    line = [r["file"][:60]]
    for name, build in VARIANTS.items():
        shown = app_filter(gp.raw(build(left, title)))
        rk = next((i for i, h in enumerate(shown, 1) if correct(h, left, title, movie, r.get("genius"))), None)
        b = "first" if rk == 1 else "2-8" if rk and rk <= 8 else "miss"
        res[(name, kind)][b] += 1
        line.append(f"{rk or '-'}")
    detail.append((kind, line))
for (name, kind), c in res.items():
    print(f"{kind:6} {name:22} first={c['first']:3} 2-8={c['2-8']:3} miss={c['miss']:3}")
if "-v" in sys.argv:
    for kind, line in detail:
        if len(set(line[1:])) > 1 or line[1] != "1":
            print(kind, " | ".join(line))
