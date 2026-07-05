#!/usr/bin/env python3
"""Apply the line-end snap to existing karaoke .ass files.

Offline A/B tool for eyeballing ``snap_line_ends`` before it reaches the
live pipeline: parses each production ``karaoke/<stem>.ass`` back into
word timings, extends clipped line-final words against the song's vocal
stem, and writes the result alongside as ``karaoke/<stem>.endsnap.ass``
(end snap only — no onset snap — so the diff isolates the effect). Songs
where nothing extended get no output file. Play with::

    mpv "<video>" --sub-file="karaoke/<stem>.endsnap.ass"

Run from the repo root::

    python scripts/end_snap_ass.py [--folder PATH] [--song SUBSTRING]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from onset_snap_ass import SKIP_SUFFIXES, _fmt, parse_ass_lines

from pikaraoke.lib.onset_snap import snap_line_ends
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import generate_ass


def process_song(ass_path: Path, vocal_path: Path, cfg: PipelineConfig) -> tuple[list[dict], dict]:
    """Extend one song's line ends; returns (per-line records, snap stats)."""
    line_objects = parse_ass_lines(ass_path)
    extended, stats = snap_line_ends(line_objects, vocal_path)
    if stats.get("bailed"):
        print(f"  bailed ({stats['bailed']})")
        return [], stats
    # stats["extends"] is in the same order as the extended lines below,
    # so zip the two rather than re-deriving the bound flag here.
    ext_records = iter(stats["extends"])
    records = []
    for old, new in zip(line_objects, extended):
        if new is old:
            continue
        ext = next(ext_records)
        text = " ".join(w["word"] for w in old["words"][-5:])
        records.append(
            {
                "song": ass_path.stem,
                "time": old["end"],
                "text": text,
                "extend_s": ext["extend_s"],
                "to_bound": ext["to_bound"],
            }
        )
        flag = " -> next line" if ext["to_bound"] else ""
        print(
            f"  {_fmt(old['end'])} -> {_fmt(new['end'])} (+{ext['extend_s']:.2f}s)"
            f"{flag}  ... {text}"
        )
    print(
        f"  {stats['n_lines']} lines: {stats['n_low_ref']} low-ref, "
        f"{stats['n_fired']} fired, {stats['n_extended']} extended"
    )
    if stats["n_extended"]:
        out_path = ass_path.with_name(ass_path.stem + ".endsnap.ass")
        out_path.write_text(generate_ass(extended, cfg), encoding="utf-8")
        print(f"  wrote {out_path.name}")
    return records, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, default=Path("/home/ken/pikaraoke-songs"))
    parser.add_argument("--song", default="", help="only songs whose name contains this")
    args = parser.parse_args()

    cfg = PipelineConfig()
    extensions: list[dict] = []
    totals = {"songs": 0, "n_lines": 0, "n_low_ref": 0, "n_fired": 0}
    for ass_path in sorted((args.folder / "karaoke").glob("*.ass")):
        stem = ass_path.stem
        if stem.endswith(SKIP_SUFFIXES):
            continue
        if args.song.lower() not in stem.lower():
            continue
        vocal_path = args.folder / "vocal" / f"{stem}---vocal.m4a"
        if not vocal_path.exists():
            continue
        print(stem)
        records, stats = process_song(ass_path, vocal_path, cfg)
        if stats.get("bailed"):
            continue
        totals["songs"] += 1
        for key in ("n_lines", "n_low_ref", "n_fired"):
            totals[key] += stats[key]
        extensions.extend(records)

    if not totals["songs"]:
        return
    print(f"\n=== {totals['songs']} songs, {totals['n_lines']} lines ===")
    print(
        f"low-ref skipped: {totals['n_low_ref']}, fired: {totals['n_fired']}, "
        f"extended: {len(extensions)} ({sum(r['to_bound'] for r in extensions)} ran to next line)"
    )
    if extensions:
        sizes = sorted(r["extend_s"] for r in extensions)

        def pct(q: float) -> float:
            return sizes[min(int(q * len(sizes)), len(sizes) - 1)]

        print(f"extension size: median {pct(0.5):.2f}s, p90 {pct(0.9):.2f}s, max {sizes[-1]:.2f}s")
        big = sorted((r for r in extensions if r["extend_s"] >= 1.5), key=lambda r: -r["extend_s"])
        if big:
            print(f"\n{len(big)} extensions >= 1.5s (eyeball these):")
            for r in big:
                flag = " -> next line" if r["to_bound"] else ""
                print(f"  +{r['extend_s']:.2f}s{flag}  {_fmt(r['time'])}  {r['song'][:50]}")
                print(f"           ... {r['text']}")


if __name__ == "__main__":
    main()
