#!/usr/bin/env python3
"""Phase 1 step 1: copy the 8 in-scope songs into the large-v3 study copy.

Copies every live per-song artifact (video, vocal/nonvocal stems, dereverb
cache if present, subtitles, karaoke, cached lrclib file if present, the
``alignment_debug`` bundle) by exact stem-prefix match, so Phase 1's regen
driver can run against ``/home/ken/pikaraoke-study-l3v/songs/`` without ever
touching ``/home/ken/pikaraoke-songs``. Read-only against the source library.

Run from the repo root::

    python scripts/l3v_copy_study_songs.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SOURCE = Path("/home/ken/pikaraoke-songs")
DEST = Path("/home/ken/pikaraoke-study-l3v/songs")

# The 8 in-scope songs (plans/large-v3-evidence-study.md, "Scope" table), by
# YouTube id so filenames never need to be hand-retyped (several contain
# apostrophes / non-ASCII dashes).
SONG_IDS = [
    "AoON1CyhQAM",  # Defying Gravity (Wicked 20th Anniv)
    "22QYya-LGDY",  # Popular (Wicked 20th Anniv)
    "wGyh_53ecgg",  # Ed Sheeran - Best Part Of Me
    "hI-y5anGcUA",  # HUNTR/X - This Is What It Sounds Like
    "vGfJeW_CcFY",  # Mulan - I'll Make a Man Out of You
    "Orq_75kFi8I",  # Ed Sheeran & Rudimental - Bloodstream
    "UvyHuse6buY",  # Seasons of Love
    "0j8kL24ph8U",  # The Next Ten Minutes
]

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".webm", ".mov"}
SUBDIRS = ("alignment_debug", "karaoke", "vocal", "nonvocal", "dereverb", "subtitles", "lrclib")


def _find_video(song_id: str) -> Path:
    matches = [
        p
        for p in SOURCE.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS and p.stem.endswith(f"---{song_id}")
    ]
    if len(matches) != 1:
        raise SystemExit(f"ABORT: expected exactly 1 video for id {song_id}, found {len(matches)}")
    return matches[0]


def _copy_song(song_id: str) -> tuple[str, int]:
    video = _find_video(song_id)
    stem = video.stem
    shutil.copy2(video, DEST / video.name)
    n_files = 1
    for sub in SUBDIRS:
        src_dir = SOURCE / sub
        if not src_dir.is_dir():
            continue
        # Literal prefix match, not glob: some titles contain '[', ']', which
        # Path.glob() treats as a character-class wildcard (bit Bloodstream).
        matches = sorted(p for p in src_dir.iterdir() if p.is_file() and p.name.startswith(stem))
        if not matches:
            continue
        dest_dir = DEST / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src_file in matches:
            shutil.copy2(src_file, dest_dir / src_file.name)
            n_files += 1
    return stem, n_files


def _verify(stem: str) -> list[str]:
    """Return a list of problems (empty = clean) for one copied song."""
    problems = []
    if not (DEST / "alignment_debug" / f"{stem}.json").is_file():
        problems.append("missing alignment_debug bundle")
    if not (DEST / "vocal" / f"{stem}---vocal.m4a").is_file():
        problems.append("missing vocal stem")
    if not (DEST / "nonvocal" / f"{stem}---nonvocal.m4a").is_file():
        problems.append("missing nonvocal stem")
    return problems


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    total_files = 0
    all_problems: dict[str, list[str]] = {}
    for song_id in SONG_IDS:
        stem, n_files = _copy_song(song_id)
        total_files += n_files
        problems = _verify(stem)
        all_problems[stem] = problems
        status = "OK" if not problems else f"PROBLEMS: {', '.join(problems)}"
        print(f"{stem} ({n_files} files): {status}")

    print(f"\nSongs copied: {len(SONG_IDS)}")
    print(f"Total files copied: {total_files}")
    print(f"Dest folder count (top-level videos): {len(list(DEST.glob('*.mp4')))}")

    if any(all_problems.values()):
        print("\nABORT: one or more songs failed verification (see PROBLEMS above).")
        return 1
    print("\nVerification clean: all 8 songs have bundle + vocal + nonvocal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
