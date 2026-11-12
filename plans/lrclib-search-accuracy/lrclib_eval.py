"""Score the cached LRCLIB result lists: coverage, recall of the match on disk, and the default pick."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import lrclib_probe as lp
from pikaraoke.lib import lrclib

verbose = "-v" in sys.argv
cov = {v: Counter() for v in ("field", "q", "title")}
disk = {v: Counter() for v in ("field", "q", "title")}
sel = Counter()
notes = []
for r in lp.rows:
    left, title, movie = lp.parts(r)
    kind = "movie" if movie else "artist"
    sheet, dur = r.get("lines") or [], r.get("dur")
    disk_id = (r.get("lrc") or {}).get("id")
    for v, params in lp.queries(r).items():
        recs = lp.cache.get(json.dumps(params, sort_keys=True, ensure_ascii=False))
        if recs is None:
            cov[v][(kind, "not fetched")] += 1
            continue
        if isinstance(recs, dict):
            cov[v][(kind, "error")] += 1
            continue
        synced = [x for x in recs if x.get("syncedLyrics")]
        cov[v][(kind, "synced" if synced else "unsynced only" if recs else "nothing")] += 1
        if len(recs) >= 20:
            cov[v][(kind, "hit the 20 cap")] += 1
        if disk_id is not None:
            disk[v]["listed" if any(x.get("id") == disk_id for x in synced) else "not listed"] += 1
        if v != "field" or not synced or not sheet:
            continue
        # how the unattended pick behaves
        scored = []
        for x in synced:
            texts, _ = lrclib.parse_lrc_lines(x["syncedLyrics"])
            rate = len(lrclib.map_lines_to_cues(sheet, texts)) / len(sheet) if texts else 0.0
            gap = abs(float(x.get("duration") or 0) - dur) if dur else None
            scored.append((rate, gap, x))
        best = lrclib.select_candidate(synced, sheet, dur)
        brate, bgap = next((s[0], s[1]) for s in scored if s[2] is best)
        near_alt = [s for s in scored if s[1] is not None and s[1] <= 5 and s[0] >= brate - 0.10 and s[0] >= 0.6]
        if brate < 0.5:
            sel["pick maps under half the sheet"] += 1
        elif bgap is not None and bgap > 5 and near_alt:
            sel["pick is >5s off; a near-length one maps within 10 points"] += 1
            a = max(near_alt, key=lambda s: s[0])
            notes.append(f"{r['file'][:55]:55} pick: map {brate:.2f} gap {bgap:.0f}s | alt: map {a[0]:.2f} gap {a[1]:.0f}s | n={len(synced)}")
        elif bgap is not None and bgap > 5:
            sel["pick is >5s off; no near-length alternative"] += 1
        else:
            sel["pick within 5s"] += 1
        if disk_id is not None:
            sel["disk: same as pick" if best.get("id") == disk_id else "disk: differs from pick"] += 1
for v in cov:
    print(f"\n[{v}] coverage:", dict(sorted(cov[v].items())))
    print(f"[{v}] match on disk:", dict(disk[v]))
print("\nunattended pick (field search):", dict(sel))
if verbose:
    print("\n".join(notes))
