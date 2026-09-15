#!/usr/bin/env python3
"""Apply the combined onset + end edge snap to shipped karaoke .ass files.

Offline A/B tool for eyeballing ``snap_line_edges`` before it reaches the
live pipeline: parses each shipped ``karaoke/<stem>.ass`` back into word
timings, snaps line-initial word starts to the vocal onset and extends
clipped line-final words to the vocal release against production's own
aligned stem (:func:`snap_stem_path` -- the de-reverbed stem when the
de-reverb gate adopted one for this song, else the vocal stem), then
writes the result alongside as ``karaoke/<stem>.edgesnap.ass``. Songs
where nothing moved get no output file. Play with::

    mpv "<video>" --sub-file="karaoke/<stem>.edgesnap.ass"

Population walks ``<folder>/alignment_debug/*.json`` (every captured
bundle) rather than globbing ``karaoke/*.ass``, so a song with a bundle
but no shipped file, or no stem audio, is reported rather than silently
dropped.

Run from the repo root::

    python scripts/edge_snap_ass.py --folder PATH [--song SUBSTRING]
        [--multi-word-only]

Fidelity limits, read before trusting an absolute count from this harness:

(i) Every shipped file is already snapped by production, so this
    harness's absolute counts are second-application artifacts: a line
    production already moved is fed back through the same detector. Only
    phase-to-phase diffs are meaningful, and only for lines production's
    own snap never touches -- one-word lines (Phase 4) and interior runs
    (Phase 6).
(ii) The ASS round-trip floors word durations at 10 cs and rounds to cs,
    so parsed word times drift from production's inside multi-word
    lines. One-word lines round-trip to within 1 cs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from onset_snap_ass import _fmt, parse_ass_lines

from pikaraoke.lib.onset_snap import rms_envelope_db, snap_line_ends, snap_line_onsets
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import generate_ass


def snap_stem_path(folder: Path, stem: str, bundle: dict) -> Path:
    """Production's ``aligned_stem`` choice for ``stem``.

    De-reverbed when the de-reverb gate adopted one for this song
    (``joint_stats.dereverb.succeeded``), else the vocal stem.
    """
    dereverb = (bundle.get("joint_stats") or {}).get("dereverb") or {}
    if dereverb.get("succeeded"):
        return folder / "dereverb" / f"{stem}---dereverb.m4a"
    return folder / "vocal" / f"{stem}---vocal.m4a"


def _stats_line(label: str, stats: dict) -> str:
    """The ``  stats <label> k=v ...`` record-view line for a stats dict.

    Every integer-valued key in sorted order, so a counter a later phase
    adds to the dict shows up with no harness edit.
    """
    parts = " ".join(
        f"{k}={v}"
        for k, v in sorted(stats.items())
        if isinstance(v, int) and not isinstance(v, bool)
    )
    return f"  stats {label} {parts}"


def process_song(
    ass_path: Path, stem_path: Path, cfg: PipelineConfig, multi_word_only: bool
) -> dict:
    """Snap one shipped song's line onsets and ends; returns combined stats."""
    line_objects = parse_ass_lines(ass_path)
    if multi_word_only:
        line_objects = [o for o in line_objects if len(o.get("words") or []) != 1]

    try:
        env = rms_envelope_db(stem_path)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"  bailed (decode_failed: {exc})")
        return {"bailed": "decode_failed"}

    onset_out, onset_stats = snap_line_onsets(line_objects, stem_path, env)
    for old, new in zip(line_objects, onset_out):
        if new is old:
            continue
        tag = "[1w] " if len(old["words"]) == 1 else ""
        shift = new["start"] - old["start"]
        text = " ".join(w["word"] for w in old["words"][:5])
        print(
            f"  rec onset {tag}{_fmt(old['start'])} -> {_fmt(new['start'])} "
            f"(+{shift:.2f}s)  {text} ..."
        )

    final_out, end_stats = snap_line_ends(onset_out, stem_path, env)
    ext_records = iter(end_stats["extends"])
    for old, new in zip(onset_out, final_out):
        if new is old:
            continue
        ext = next(ext_records)
        tag = "[1w] " if len(old["words"]) == 1 else ""
        text = " ".join(w["word"] for w in old["words"][-5:])
        flag = " to_bound" if ext["to_bound"] else ""
        print(
            f"  rec end {tag}{_fmt(old['end'])} -> {_fmt(new['end'])} "
            f"(+{ext['extend_s']:.2f}s){flag}  ... {text}"
        )

    print(_stats_line("onset", onset_stats))
    print(_stats_line("end", end_stats))

    if onset_stats["n_snapped"] or end_stats["n_extended"]:
        out_path = ass_path.with_name(ass_path.stem + ".edgesnap.ass")
        out_path.write_text(generate_ass(final_out, cfg), encoding="utf-8")
        print(f"  wrote {out_path.name}")

    return {"onset": onset_stats, "end": end_stats}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--song", default="", help="only songs whose name contains this")
    parser.add_argument(
        "--multi-word-only",
        action="store_true",
        help="drop one-word line objects before snapping",
    )
    args = parser.parse_args()

    cfg = PipelineConfig()
    debug_dir = args.folder / "alignment_debug"
    n_songs = 0
    total_onset: Counter = Counter()
    total_end: Counter = Counter()

    for bundle_path in sorted(debug_dir.glob("*.json")):
        stem = bundle_path.stem
        if args.song.lower() not in stem.lower():
            continue
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        print(stem)

        ass_path = args.folder / "karaoke" / f"{stem}.ass"
        if not ass_path.exists():
            print("  skipped (no shipped .ass)")
            continue

        stem_path = snap_stem_path(args.folder, stem, bundle)
        if not stem_path.exists():
            print("  skipped (no stem)")
            continue

        stats = process_song(ass_path, stem_path, cfg, args.multi_word_only)
        if stats.get("bailed"):
            continue
        n_songs += 1
        for k, v in stats["onset"].items():
            if isinstance(v, int) and not isinstance(v, bool):
                total_onset[k] += v
        for k, v in stats["end"].items():
            if isinstance(v, int) and not isinstance(v, bool):
                total_end[k] += v

    if not n_songs:
        return
    print(f"total songs={n_songs}")
    print("total onset " + " ".join(f"{k}={v}" for k, v in sorted(total_onset.items())))
    print("total end " + " ".join(f"{k}={v}" for k, v in sorted(total_end.items())))


if __name__ == "__main__":
    main()
