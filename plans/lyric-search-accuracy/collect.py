"""Gather each library song's recorded Genius pick and LRCLIB match (read-only)."""
import json
from collections import Counter
from pathlib import Path

from pikaraoke.lib import lrclib
from pikaraoke.lib.library_regen import default_query
from pikaraoke.lib.metadata_parser import youtube_id_suffix

LIB = Path.home() / "pikaraoke-songs"
OUT = Path(__file__).parent / "truth.json"
rows = []
origins = Counter()
for song in sorted(p for p in LIB.iterdir() if p.suffix.lower() in (".mp4", ".webm", ".mkv")):
    bundle_path = LIB / "alignment_debug" / f"{song.stem}.json"
    row = {"file": song.name, "query": default_query(song)}
    if bundle_path.is_file():
        b = json.loads(bundle_path.read_text(encoding="utf-8"))
        ly = b.get("lyrics") or {}
        origins[ly.get("origin")] += 1
        row["origin"] = ly.get("origin")
        row["old_stem"] = b.get("song_stem")
        row["genius"] = ly.get("genius")
        row["lines"] = ly.get("lines") or []
        row["dur"] = b.get("media_duration_s")
    else:
        origins["(no bundle)"] += 1
    lrc = lrclib.read_song_lrc(song)
    row["lrc_state"] = lrc.state
    row["lrc"] = lrc.meta if lrc.state == "match" else None
    rows.append(row)
OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(origins)
g = [r for r in rows if r.get("genius")]
print("genius picks:", len(g), "lrc matches:", sum(1 for r in rows if r["lrc"]), "skipped:", sum(1 for r in rows if r["lrc_state"] == "skipped"))
renamed = [r for r in g if r.get("old_stem") and r["old_stem"] != Path(r["file"]).stem]
print("genius songs whose bundle stem differs from today's file:", len(renamed))
for r in g[:400]:
    old = r.get("old_stem") or ""
    suffix = youtube_id_suffix(old + ".mp4")
    print(f"- file q: {r['query']!r}\n  old   : {old[: -len(suffix)] if suffix else old!r}\n  genius: {r['genius'].get('title')!r} / {r['genius'].get('artist')!r} #{r['genius'].get('id')}  lrc={r['lrc_state']}")
