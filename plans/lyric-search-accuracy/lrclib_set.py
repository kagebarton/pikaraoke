"""How complete is the LRCLIB candidate set per query shape? Scores the set, not the pick (cache only)."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lrclib_probe as lp
from pikaraoke.lib import lrclib

NEAR_S, GOOD = 2.0, 0.6
SETS = ("field", "q", "title", "get", "field+q", "field+get", "all")
verbose = "-v" in sys.argv


def cached(params, get_dur=None):
    key = json.dumps(params if get_dur is None else {**params, "duration": get_dur}, sort_keys=True, ensure_ascii=False)
    got = lp.cache.get(("GET " if get_dur is not None else "") + key)
    if isinstance(got, list):
        return got
    if isinstance(got, dict) and got.get("id"):
        return [got]
    return []


def grade(recs, sheet, dur):
    """(any synced, synced near length, synced near length and a good text match, best near rate)."""
    synced = {x["id"]: x for x in recs if x.get("syncedLyrics")}
    near = [x for x in synced.values() if abs(float(x.get("duration") or 0) - dur) <= NEAR_S]
    best = 0.0
    for x in near:
        texts, _ = lrclib.parse_lrc_lines(x["syncedLyrics"])
        if texts:
            best = max(best, len(lrclib.map_lines_to_cues(sheet, texts)) / len(sheet))
    return bool(synced), bool(near), best >= GOOD, best, len(synced)


tally = {s: Counter() for s in SETS}
sizes = {s: [] for s in SETS}
gained = []
for r in lp.rows:
    sheet, dur = r.get("lines") or [], r.get("dur")
    if not sheet or not dur:
        continue
    left, title, movie = lp.parts(r)
    film_as_artist = movie and not (r.get("genius") or {}).get("title")
    kind = "film-as-artist" if film_as_artist else "real artist"
    qs = lp.queries(r)
    parts = {
        "field": cached(qs["field"]),
        "q": cached(qs["q"]),
        "title": cached(qs["title"]),
        "get": cached(qs["field"], round(dur)),
    }
    parts["field+q"] = parts["field"] + parts["q"]
    parts["field+get"] = parts["field"] + parts["get"]
    parts["all"] = parts["field"] + parts["q"] + parts["title"] + parts["get"]
    row = {}
    for s in SETS:
        anyv, near, good, best, n = grade(parts[s], sheet, dur)
        row[s] = (near, good, best)
        tally[s][(kind, "songs")] += 1
        tally[s][(kind, "synced")] += anyv
        tally[s][(kind, "near")] += near
        tally[s][(kind, "near+good")] += good
        sizes[s].append(n)
    if row["all"][1] and not row["field"][1]:
        src = [s for s in ("q", "title", "get") if row[s][1]]
        gained.append(f"{kind:14} {r.get('origin') or '-':10} {r['file'][:52]:52} via {','.join(src)} ({row['all'][2]:.2f})")

for kind in ("real artist", "film-as-artist"):
    print(f"\n{kind}: {tally['field'][(kind, 'songs')]} songs with lyric lines and a length")
    print(f"{'set':10} {'synced':>7} {'near 2s':>8} {'near+>=60%':>11}")
    for s in SETS:
        t = tally[s]
        print(f"{s:10} {t[(kind, 'synced')]:7} {t[(kind, 'near')]:8} {t[(kind, 'near+good')]:11}")
print("\nmedian synced records per set:", {s: sorted(v)[len(v) // 2] for s, v in sizes.items()})
print(f"\nsongs where only a wider set holds a near-length good match ({len(gained)}):")
if verbose:
    print("\n".join(gained))
