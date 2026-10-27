"""Phase 1: Ken's review sheets and the raw run table, from the JSONs phase1_run.py saved.

CPU only and re-runnable. Writes into <PROBE_ROOT>/phase1/:
  review_<video_id>.csv  one row per sheet line, each arm's start time, blank columns for Ken
  commands.txt           the mpv command for every song and arm (and the app's existing .ass)
  runs.txt               wall time, peak VRAM and unit counts per song and arm, no tallies

Run: uv run python scripts/zh_probe/phase1_review.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from corpus import PILOT, PROBE_ROOT, find_in_library  # noqa: E402
from sheet import load_sheet  # noqa: E402
from track import ARM_NAMES  # noqa: E402

OUT_DIR = PROBE_ROOT / "phase1"
VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm"}
CALLS = "singable as is / singable with a few bad lines / not singable"


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def load_records(video_id: str) -> dict[str, dict]:
    """Saved arm records for a song, in ARM_NAMES order."""
    records = {}
    for name in ARM_NAMES:
        path = OUT_DIR / video_id / f"{name}.json"
        if path.exists():
            records[name] = json.loads(path.read_text(encoding="utf-8"))
    return records


def line_starts(record: dict) -> dict[int, float]:
    starts: dict[int, float] = {}
    for unit in record["units"]:
        starts.setdefault(unit["line"], unit["start"])
    return starts


def write_review(video_id: str, records: dict[str, dict]) -> None:
    sheet = load_sheet(video_id)
    arms = list(records)
    starts = {name: line_starts(rec) for name, rec in records.items()}
    path = OUT_DIR / f"review_{video_id}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        out = csv.writer(f)
        out.writerow(
            ["line", "sheet line"]
            + [f"{a} start" for a in arms]
            + [f"{a} bad (x)" for a in arms]
            + ["note"]
        )
        for n, text in enumerate(sheet.lines):
            out.writerow(
                [n + 1, text] + [mmss(starts[a][n]) for a in arms] + [""] * len(arms) + [""]
            )
        out.writerow([])
        out.writerow(["", f"OVERALL call per arm ({CALLS}):"] + [""] * (2 * len(arms) + 1))


def write_commands() -> None:
    lines = []
    for song in PILOT:
        videos = [p for p in find_in_library(song.video_id) if p.suffix in VIDEO_SUFFIXES]
        (video,) = videos
        lines.append(f"# #{song.num} {song.title} ({song.lang})")
        for name in load_records(song.video_id):
            ass = OUT_DIR / song.video_id / f"{name}.ass"
            lines.append(f'{name:4} mpv "{video}" --sub-file="{ass}"')
        if song.num in (1, 2):
            (baseline,) = [
                p for p in find_in_library(song.video_id, "karaoke") if p.suffix == ".ass"
            ]
            lines.append(
                f'base mpv "{video}" --sub-file="{baseline}"  # the app as it is, contrast only'
            )
        lines.append("")
    (OUT_DIR / "commands.txt").write_text("\n".join(lines), encoding="utf-8")


def write_runs() -> None:
    header = [
        "song", "arm", "model", "device", "load_s", "load_peak_alloc_mb", "load_peak_reserved_mb",
        "align_s", "align_peak_alloc_mb", "align_peak_reserved_mb", "units", "shared",
        "interpolated", "zero_duration", "frames",
    ]  # fmt: skip
    rows = [header]
    for song in PILOT:
        for name, rec in load_records(song.video_id).items():
            run, units = rec["run"], rec["units"]
            rows.append(
                [
                    f"#{song.num}", name, rec["model"], run["device"],
                    run["load"]["wall_s"], run["load"]["peak_allocated_mb"],
                    run["load"]["peak_reserved_mb"], run["align"]["wall_s"],
                    run["align"]["peak_allocated_mb"], run["align"]["peak_reserved_mb"],
                    len(units),
                    sum(u.get("note") == "shared" for u in units),
                    sum(u.get("note") == "interpolated" for u in units),
                    sum(u["end"] <= u["start"] for u in units),
                    run.get("frames", ""),
                ]
            )  # fmt: skip
    (OUT_DIR / "runs.txt").write_text(
        "\n".join("\t".join(str(c) for c in row) for row in rows) + "\n", encoding="utf-8"
    )


def main() -> None:
    for song in PILOT:
        records = load_records(song.video_id)
        if records:
            write_review(song.video_id, records)
    write_commands()
    write_runs()
    print(f"wrote review sheets, commands.txt and runs.txt in {OUT_DIR}")


if __name__ == "__main__":
    main()
