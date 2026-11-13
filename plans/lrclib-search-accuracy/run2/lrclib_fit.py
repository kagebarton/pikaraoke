"""Which query shapes bring back a record that passes the fit check's frozen bar? (cache only)

Runs branch lrclib_fit_pick's own code (`lrc_auto_pick`, `srt_slice_fit`) on the cached record
lists against each bundle's transcribe words. Pass that branch's tree as argv[1].
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from pikaraoke.lib import lrc_auto_pick  # noqa: E402
from pikaraoke.lib.srt_slice_fit import TRANSCRIBE, fit_slice, heard_streams, lrc_to_srt  # noqa: E402

import lrclib_probe as lp  # noqa: E402

LIB = Path("/home/ken/shared-drives/D:/Shared/pikaraoke-songs")
HERE = Path(__file__).parent
SETS = {
    "build (q)": ["q_build"],
    "q + exact length": ["q_build", "get", "get_first", "get_alt"],
    "q + fields": ["q_build", "field", "field_first", "field_alt"],
    "q + fields + exact length": ["q_build", "field", "field_first", "field_alt", "get", "get_first", "get_alt"],
    "+ title only": ["q_build", "field", "field_first", "field_alt", "get", "get_first", "get_alt", "title", "qtitle"],
    "everything": None,
}
fits_path = HERE / "fits.json"
fits = json.loads(fits_path.read_text(encoding="utf-8")) if fits_path.exists() else {}
verbose = "-v" in sys.argv


def verdict(song_key: str, rec: dict, words: list[dict], dur: float) -> dict:
    """The bar's verdict on one record for one song, cached (the fit is the slow part)."""
    key = f"{song_key}|{rec['id']}"
    if key not in fits:
        fit = fit_slice(lrc_to_srt(rec["syncedLyrics"]), {TRANSCRIBE: words}, dur)
        fits[key] = {"refusal": lrc_auto_pick.refusal(fit), "mistimed": len(fit.mistimed)}
    return fits[key]


def pick(recs: list[dict], song_key: str, words, dur):
    """(number passing, the picked record) by the frozen pick order over this set."""
    sizes = Counter(lrc_auto_pick.timing_key(r["syncedLyrics"]) for r in recs)
    passing = [r for r in recs if verdict(song_key, r, words, dur)["refusal"] is None]
    order = lambda r: (verdict(song_key, r, words, dur)["mistimed"], -sizes[lrc_auto_pick.timing_key(r["syncedLyrics"])],
                       len(r.get("trackName") or ""), len(r.get("albumName") or ""), r["id"])
    return len(passing), (min(passing, key=order) if passing else None)


tally = {s: Counter() for s in SETS}
sizes_by_set = {s: [] for s in SETS}
gains, changes, lost_disk = [], [], Counter()
for n, r in enumerate(lp.rows):
    bundle_path = LIB / "alignment_debug" / f"{Path(r['file']).stem}.json"
    if not bundle_path.is_file():
        continue
    words = heard_streams(json.loads(bundle_path.read_text(encoding="utf-8")), None).get(TRANSCRIBE, [])
    if not words:
        continue
    # "genius pick": the title and artist the pipeline really held. The rest use the answer key's
    # names as a stand-in, and a film-named song without a recorded pick has no artist to send.
    group = "genius pick" if (r.get("genius") or {}).get("title") else "stand-in, artist" if lp.identity(r)[1] else "stand-in, no artist"
    shapes = lp.shapes(r)
    got = {}
    for name, job in shapes.items():
        recs = lp.cache.get(lp.key_of(*job))
        got[name] = [x for x in recs if x.get("syncedLyrics")] if isinstance(recs, list) else []
    row = {}
    for s, names in SETS.items():
        merged = {x["id"]: x for name in (names or got) for x in got.get(name, [])}
        count, chosen = pick(list(merged.values()), r["file"], words, r["dur"])
        row[s] = (count, chosen, merged)
        tally[s][(group, "songs")] += 1
        tally[s][(group, "pick")] += chosen is not None
        sizes_by_set[s].append(len(merged))
        disk = (r.get("lrc") or {}).get("id")
        if disk is not None:
            tally[s][(group, "disk")] += 1
            tally[s][(group, "disk listed")] += disk in merged
    base = row["build (q)"]
    for s in list(SETS)[1:]:
        if row[s][1] and not base[1]:
            gains.append(f"{group:19} {r['name'][:48]:48} first in: {s:26} {row[s][1]['artistName'][:22]} / {row[s][1]['trackName'][:26]} dur {row[s][1]['duration']:.0f} vs {r['dur']:.0f}")
            break
    wide = row["q + fields + exact length"]
    if base[1] and wide[1] and base[1]["id"] != wide[1]["id"]:
        same = lrc_auto_pick.timing_key(base[1]["syncedLyrics"]) == lrc_auto_pick.timing_key(wide[1]["syncedLyrics"])
        changes.append(f"{group:19} {r['name'][:48]:48} {base[1]['id']} -> {wide[1]['id']} {'(same timing text)' if same else '(different timing)'}")
    if n % 20 == 0:
        fits_path.write_text(json.dumps(fits), encoding="utf-8")
fits_path.write_text(json.dumps(fits), encoding="utf-8")

for group in ("genius pick", "stand-in, artist", "stand-in, no artist"):
    print(f"\n{group}: {tally['everything'][(group, 'songs')]} songs with heard words")
    print(f"{'set':28} {'with a pick':>11} {'on-disk record listed':>22} {'median synced':>14}")
    for s in SETS:
        t = tally[s]
        print(f"{s:28} {t[(group, 'pick')]:11} {t[(group, 'disk listed')]:>12} of {t[(group, 'disk')]:<6} {sorted(sizes_by_set[s])[len(sizes_by_set[s]) // 2]:14}")
print(f"\nsongs with no pick from the build's search that a wider set picks ({len(gains)}):")
print("\n".join(gains))
print(f"\nsongs whose pick changes between the build's search and q + fields + exact length ({len(changes)}):")
print({g: (sum(1 for c in changes if c.startswith(g)), sum(1 for c in changes if c.startswith(g) and "different" in c)) for g in ("genius pick", "stand-in, artist", "stand-in, no artist")}, "(changed, of which a different timing)")
if verbose:
    print("\n".join(changes))
