#!/usr/bin/env python3
"""Apply the combined onset + end edge snap to existing karaoke .ass files.

Offline A/B tool for eyeballing ``snap_line_edges`` before it reaches the
live pipeline: parses each production ``karaoke/<stem>.ass`` back into
word timings, snaps line-initial word starts to the vocal onset and
extends clipped line-final words to the vocal release against the song's
vocal stem, then writes the result alongside as
``karaoke/<stem>.edgesnap.ass``. Songs where nothing moved get no output
file. Play with::

    mpv "<video>" --sub-file="karaoke/<stem>.edgesnap.ass"

Run from the repo root::

    python scripts/edge_snap_ass.py [--folder PATH] [--song SUBSTRING]
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from onset_snap_ass import SKIP_SUFFIXES, _fmt, parse_ass_lines

from pikaraoke.lib.onset_snap import rms_envelope_db, snap_line_ends, snap_line_onsets
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import generate_ass


def process_song(ass_path: Path, vocal_path: Path, cfg: PipelineConfig) -> dict:
    """Snap one song's line onsets and ends; returns combined stats."""
    line_objects = parse_ass_lines(ass_path)
    try:
        env = rms_envelope_db(vocal_path)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"  bailed (decode_failed: {exc})")
        return {"bailed": "decode_failed"}

    onset_out, onset_stats = snap_line_onsets(line_objects, vocal_path, env)
    for old, new in zip(line_objects, onset_out):
        if new is old:
            continue
        shift = new["start"] - old["start"]
        text = " ".join(w["word"] for w in old["words"][:5])
        print(f"  {_fmt(old['start'])} -> {_fmt(new['start'])} (+{shift:.2f}s)  {text} ...")

    final_out, end_stats = snap_line_ends(onset_out, vocal_path, env)
    ext_records = iter(end_stats["extends"])
    for old, new in zip(onset_out, final_out):
        if new is old:
            continue
        ext = next(ext_records)
        text = " ".join(w["word"] for w in old["words"][-5:])
        flag = " -> next line" if ext["to_bound"] else ""
        print(
            f"  {_fmt(old['end'])} -> {_fmt(new['end'])} (+{ext['extend_s']:.2f}s)"
            f"{flag}  ... {text}"
        )

    print(
        f"  {onset_stats['n_lines']} lines: {onset_stats['n_snapped']} onset-snapped, "
        f"{end_stats['n_low_ref']} low-ref, {end_stats['n_fired']} fired, "
        f"{end_stats['n_extended']} end-extended"
    )
    if onset_stats["n_snapped"] or end_stats["n_extended"]:
        out_path = ass_path.with_name(ass_path.stem + ".edgesnap.ass")
        out_path.write_text(generate_ass(final_out, cfg), encoding="utf-8")
        print(f"  wrote {out_path.name}")

    return {"onset": onset_stats, "end": end_stats}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, default=Path("/home/ken/pikaraoke-songs"))
    parser.add_argument("--song", default="", help="only songs whose name contains this")
    args = parser.parse_args()

    cfg = PipelineConfig()
    totals = {
        "songs": 0,
        "n_lines": 0,
        "n_snapped": 0,
        "n_low_ref": 0,
        "n_fired": 0,
        "n_extended": 0,
    }
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
        stats = process_song(ass_path, vocal_path, cfg)
        if stats.get("bailed"):
            continue
        totals["songs"] += 1
        totals["n_lines"] += stats["onset"]["n_lines"]
        totals["n_snapped"] += stats["onset"]["n_snapped"]
        totals["n_low_ref"] += stats["end"]["n_low_ref"]
        totals["n_fired"] += stats["end"]["n_fired"]
        totals["n_extended"] += stats["end"]["n_extended"]

    if not totals["songs"]:
        return
    print(f"\n=== {totals['songs']} songs, {totals['n_lines']} lines ===")
    print(f"onset-snapped: {totals['n_snapped']}")
    print(
        f"end low-ref skipped: {totals['n_low_ref']}, fired: {totals['n_fired']}, "
        f"end-extended: {totals['n_extended']}"
    )


if __name__ == "__main__":
    main()
