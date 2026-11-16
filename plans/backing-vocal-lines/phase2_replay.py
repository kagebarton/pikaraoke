"""Phase 2: replay the library's songs before and after the build, on scratch copies.

The library is read-only here. From the worktree root, in order::

    PYTHONPATH=. python plans/backing-vocal-lines/phase2_replay.py select ~/pikaraoke-songs plans/backing-vocal-lines/out
    PYTHONPATH=. python plans/backing-vocal-lines/phase2_replay.py stage ~/pikaraoke-songs <scratch> plans/backing-vocal-lines/out [--role controls]
    # run scripts/regen_alignment_bundles.py <scratch>/before from the "before" worktree and
    # <scratch>/after from this one, with --song=<id> for every song (see ``run_order``)
    PYTHONPATH=. python plans/backing-vocal-lines/phase2_replay.py report <scratch> plans/backing-vocal-lines/out

``select`` writes out/phase2_songs.json: the cue songs whose sheet keeps at least one
parenthetical under the built rule, the 8 songs of "The B6 sample" and 5 controls (cue songs whose
sheet holds no "(" at all). The controls are, per origin (3 captions, 2 LRC), the paren-free
sheets nearest that origin's median audio length: typical songs, not the quickest ones.

``stage`` copies each song's own files (video, stems, sheets, ASR caption, bundle, .lrc) into
``<scratch>/before`` and ``<scratch>/after``, the same bytes in both, and nothing else.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
from pathlib import Path

from pikaraoke.lib.backing_vocals import judge
from pikaraoke.lib.srt_cues import cue_spans_from_srt, sheet_parens

# "The B6 sample" of plans/backing-vocal-lines.md: bundle names in the library, by role.
B6_SAMPLE = (
    "Bruno Mars, Anderson .Paak, Silk Sonic - After Last Night w_ Thundercat & Bootsy [Official Audio]----cy_tDQPXHk",
    "The Lonely Island - I'm On A Boat (Explicit Version) ft. T-Pain (Official Video)---avaSdC0QOUM",
    "Bruno Mars - Grenade (Official Music Video)---SR6iYWJxHqs",
    "YOLO (feat. Adam Levine & Kendrick Lamar)---z5Otla5157c",
    "Queen - Don't Stop Me Now (Official Video Remastered 4K)---HgzGwKwLmgM",
    "Justin Timberlake - SexyBack (Official HD Video) ft. Timbaland---3gOHvDP_vCs",
    "Jay Chou 周杰倫 - 晴天 (Sunny Day)---DYptgVvkVLQ",
    "Ed Sheeran & Rudimental - Bloodstream---Orq_75kFi8I",
)
CONTROLS_PER_ORIGIN = {"srt": 3, "lrclib_srt": 2}
VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v")
# The subfolders a song keeps files in; a file belongs to the song when its name starts with
# the stem followed by "." or "---<folder>" (stems).
SONG_DIRS = ("subtitles", "karaoke", "lyrics", "alignment_debug", "vocal", "nonvocal", "dereverb")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_video(lib: Path, stem: str) -> Path | None:
    hits = [lib / f"{stem}{ext}" for ext in VIDEO_EXTS if (lib / f"{stem}{ext}").is_file()]
    return hits[0] if len(hits) == 1 else None


def own_files(lib: Path, stem: str) -> list[Path]:
    """The song's video and every file in the song folders whose name the stem claims."""
    files = [find_video(lib, stem)]
    for sub in SONG_DIRS:
        folder = lib / sub
        if folder.is_dir():
            files += [
                p
                for p in sorted(folder.iterdir())
                if p.is_file()
                and (p.name.startswith(stem + ".") or p.name.startswith(stem + "---"))
            ]
    return [p for p in files if p is not None]


def kept_groups(lib: Path, song: dict) -> list[dict]:
    """The song's kept parentheticals as the built rule judges them on the library's bundle."""
    sheet = (lib / song["sheet"]).read_text(encoding="utf-8")
    bundle = read_json(lib / "alignment_debug" / song["bundle"])
    cues = sheet_parens(sheet)
    _, spans = cue_spans_from_srt(sheet)
    offset = bundle["joint_stats"].get("offset_s") or 0.0
    verdicts = judge(cues, spans, bundle["transcribe_words"], offset)
    return [{"cue": v.cue, "group": v.group, "kind": v.kind} for v in verdicts if v.kept]


def select(lib: Path, out: Path) -> None:
    cue_songs = [s for s in read_json(out / "songs.json") if "skipped" not in s]
    rows: list[dict] = []
    free: dict[str, list[dict]] = {origin: [] for origin in CONTROLS_PER_ORIGIN}
    for song in cue_songs:
        bundle = read_json(lib / "alignment_debug" / song["bundle"])
        row = {
            "key": song["key"],
            "stem": Path(song["bundle"]).stem,  # songs.json's "stem" predates a rename
            "origin": song["origin"],
            "audio_s": bundle["media_duration_s"],
        }
        kept = kept_groups(lib, song)
        if kept:
            rows.append(
                {
                    **row,
                    "role": "keep",
                    "kept": len(kept),
                    "kept_inline": sum(k["kind"] == "inline" for k in kept),
                    "kept_paren_only": sum(k["kind"] == "paren_only" for k in kept),
                }
            )
        elif "(" not in (lib / song["sheet"]).read_text(encoding="utf-8"):
            free[song["origin"]].append(row)

    for origin, n in CONTROLS_PER_ORIGIN.items():
        median = statistics.median(r["audio_s"] for r in free[origin])
        nearest = sorted(free[origin], key=lambda r: (abs(r["audio_s"] - median), r["key"]))[:n]
        rows += [{**r, "role": "control"} for r in nearest]

    for name in B6_SAMPLE:
        bundle = read_json(lib / "alignment_debug" / f"{name}.json")
        key = name[-11:]
        rows.append(
            {
                "key": key,
                "stem": name,
                "origin": bundle["lyrics"]["origin"],
                "audio_s": bundle["media_duration_s"],
                "role": "b6",
            }
        )

    for row in rows:
        row["video"] = bool(find_video(lib, row["stem"]))
    (out / "phase2_songs.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    for role in ("keep", "control", "b6"):
        mine = [r for r in rows if r["role"] == role]
        print(f"{role}: {len(mine)} songs, {sum(r['audio_s'] for r in mine) / 60:.0f} min audio")
    missing = [r["stem"] for r in rows if not r["video"]]
    print(f"songs with no video in the library: {missing}")
    print(f"free-of-parens candidates: { {o: len(v) for o, v in free.items()} }")


def stage(
    lib: Path,
    scratch: Path,
    out: Path,
    roles: list[str] | None,
    keys: list[str] | None,
    sides: tuple[str, ...] = ("before", "after"),
) -> None:
    """Copy each selected song's files into the scratch folder's side folders."""
    if scratch.resolve().is_relative_to(lib.resolve()) or lib.resolve().is_relative_to(
        scratch.resolve()
    ):
        raise SystemExit(f"scratch {scratch} and the library {lib} must not contain each other")
    rows = [
        r
        for r in read_json(out / "phase2_songs.json")
        if (not roles or r["role"] in roles) and (not keys or r["key"] in keys)
    ]
    for side in sides:
        for row in rows:
            for src in own_files(lib, row["stem"]):
                dest = scratch / side / src.relative_to(lib)
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
    print(f"staged {len(rows)} songs into {scratch} ({', '.join(sides)})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("select")
    p.add_argument("library", type=Path)
    p.add_argument("out", type=Path)
    p = sub.add_parser("stage")
    p.add_argument("library", type=Path)
    p.add_argument("scratch", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--role", action="append", choices=["keep", "control", "b6"])
    p.add_argument("--key", action="append", help="only the song with this YouTube id")
    p.add_argument("--side", action="append", choices=["before", "after"])
    args = parser.parse_args()
    if args.cmd == "select":
        select(args.library.expanduser(), args.out)
    elif args.cmd == "stage":
        stage(
            args.library.expanduser(),
            args.scratch,
            args.out,
            args.role,
            args.key,
            tuple(args.side or ("before", "after")),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
