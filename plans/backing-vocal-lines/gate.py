"""GATE A3, A4 and the unsure rows, from out/heard.json.

PYTHONPATH=. python plans/backing-vocal-lines/gate.py ~/pikaraoke-songs plans/backing-vocal-lines/out <rule> [<rule> ...]
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


def a3(rows: list[dict], rule: str) -> list[str]:
    """Songs where one text is kept in one place and dropped in another."""
    by = defaultdict(list)
    for r in rows:
        by[(r["song"], r["label_key"])].append(r["kept"][rule])
    return [
        f'{song} "{key}" {sum(v)}/{len(v)}'
        for (song, key), v in sorted(by.items())
        if 0 < sum(v) < len(v)
    ]


def a4(lib: Path, rows: list[dict], songs: dict, rule: str) -> dict:
    """Kept paren-only cues: how many overlap a line's cue window, and how many overlap a
    neighbouring line's on-screen time today (bundle output, cue window moved by the offset)."""
    kept = [r for r in rows if r["kind"] == "paren_only" and r["kept"][rule]]
    out = {"kept": len(kept), "cue overlap": 0, "screen overlap": 0, "screen list": []}
    bundles = {}
    for r in kept:
        out["cue overlap"] += bool(r["overlaps"])
        if r["song"] not in bundles:
            bundles[r["song"]] = json.loads(
                (lib / "alignment_debug" / songs[r["song"]]["bundle"]).read_text()
            )
        b = bundles[r["song"]]
        shift = b["joint_stats"].get("offset_s") or 0.0
        s0, s1 = r["start"] + shift, r["end"] + shift
        timing = {t["line_id"]: t for t in b["output_line_timings"]}
        hits = [
            (lid, round(min(s1, t["end"]) - max(s0, t["start"]), 2))
            for lid in (r["prev_line"], r["next_line"])
            if lid is not None
            and (t := timing.get(lid))
            and t["start"] is not None
            and min(s1, t["end"]) - max(s0, t["start"]) > 0
        ]
        if hits:
            out["screen overlap"] += 1
            out["screen list"].append(f"{r['song']} {r['start']:.1f}s \"{r['text']}\" {hits}")
    return out


def main(lib: Path, out: Path, rules: list[str]) -> None:
    rows = json.loads((out / "heard.json").read_text())
    songs = {s["key"]: s for s in json.loads((out / "songs.json").read_text())}
    for rule in rules:
        print(f"\n## {rule}")
        lst = a3(rows, rule)
        print(f"A3: {len(lst)} song-texts split")
        for x in lst:
            print("   ", x)
        res = a4(lib, rows, songs, rule)
        print(
            f"A4: {res['kept']} paren-only kept; cue-window overlap {res['cue overlap']}; "
            f"screen overlap with a neighbour line {res['screen overlap']}"
        )
        for x in res["screen list"]:
            print("   ", x)
    print("\n## unsure")
    by = defaultdict(list)
    for r in rows:
        if r["label"] == "unsure":
            by[(r["label_key"], r["origin"], r["kind"])].append(r)
    for (key, origin, kind), rs in sorted(by.items()):
        cells = [f"{rule}: {sum(r['kept'][rule] for r in rs)}/{len(rs)}" for rule in rules]
        print(f"{key} ({origin}, {kind}, {rs[0]['song']}): " + "; ".join(cells))


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]), sys.argv[3:])
