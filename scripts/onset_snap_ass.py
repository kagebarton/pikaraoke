#!/usr/bin/env python3
"""Apply the line-initial onset snap to existing karaoke .ass files.

Offline A/B tool for eyeballing ``pikaraoke.lib.onset_snap`` before it
reaches the live pipeline: parses each production ``karaoke/<stem>.ass``
back into word timings, runs the same ``snap_line_onsets`` post-pass
against the song's vocal stem, and writes the result alongside as
``karaoke/<stem>.onsetsnap.ass``. Songs where nothing snapped get no
output file. Play with::

    mpv "<video>" --sub-file="karaoke/<stem>.onsetsnap.ass"

Run from the repo root::

    python scripts/onset_snap_ass.py [--folder PATH] [--song SUBSTRING]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from pikaraoke.lib.onset_snap import snap_line_onsets
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import generate_ass

# Experiment outputs living next to production .ass files. Shared by the
# sibling A/B scripts (end_snap_ass, edge_snap_ass import this).
SKIP_SUFFIXES = (
    ".cuealign",
    ".jointalign",
    ".ytasr3src",
    ".asralign",
    ".onsetsnap",
    ".endsnap",
    ".edgesnap",
    ".fullmix",
)

K_TAG = re.compile(r"\{\\kf?(\d+)\}([^{]*)")


def _parse_ass_time(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_ass_lines(ass_path: Path) -> list[dict]:
    """Recover line objects (word start/end) from a generated karaoke .ass."""
    line_objects = []
    for raw in ass_path.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        fields = raw.split(",", 9)
        cursor = _parse_ass_time(fields[1])
        words = []
        for dur_cs, text in K_TAG.findall(fields[9]):
            dur = int(dur_cs) / 100.0
            if text.strip():
                words.append({"word": text.strip(), "start": cursor, "end": cursor + dur})
            cursor += dur
        if words:
            line_objects.append(
                {"words": words, "start": words[0]["start"], "end": words[-1]["end"]}
            )
    return line_objects


def _fmt(t: float) -> str:
    return f"{int(t) // 60}:{t % 60:05.2f}"


def process_song(ass_path: Path, vocal_path: Path, cfg: PipelineConfig) -> None:
    line_objects = parse_ass_lines(ass_path)
    snapped, stats = snap_line_onsets(line_objects, vocal_path)
    if stats.get("bailed") or not stats["n_snapped"]:
        print(f"  0 snaps{' (' + stats['bailed'] + ')' if stats.get('bailed') else ''}")
        return
    for old, new in zip(line_objects, snapped):
        if new is old:
            continue
        shift = new["start"] - old["start"]
        text = " ".join(w["word"] for w in old["words"][:5])
        print(f"  {_fmt(old['start'])} -> {_fmt(new['start'])} (+{shift:.2f}s)  {text} ...")
    out_path = ass_path.with_name(ass_path.stem + ".onsetsnap.ass")
    out_path.write_text(generate_ass(snapped, cfg), encoding="utf-8")
    print(f"  wrote {out_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, default=Path("/home/ken/pikaraoke-songs"))
    parser.add_argument("--song", default="", help="only songs whose name contains this")
    args = parser.parse_args()

    cfg = PipelineConfig()
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
        process_song(ass_path, vocal_path, cfg)


if __name__ == "__main__":
    main()
