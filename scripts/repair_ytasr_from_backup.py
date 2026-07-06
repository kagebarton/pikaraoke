#!/usr/bin/env python3
"""Repair genius songs whose YouTube-ASR 3rd source was lost to a regen --reset.

``regen_alignment_bundles.py --reset`` backs up ``subtitles/`` and then wipes it.
The persisted ``<stem>.en.asr.json3`` YouTube-ASR captions are download-time
artifacts that live in ``subtitles/`` but are never re-downloaded by the regen
tool, so a reset run can't find them: every genius song re-aligns two-source
(``ytasr_won=0``) instead of adopting the caption as the joint matcher's third
source, the way the live pipeline did on first add.

This restores the backed-up ``.asr.json3`` captions into ``subtitles/`` and
re-runs only the affected genius songs, reusing each song's cached stems and its
current bundle's genius lyrics — so the sole change from the current bundle is
the re-adopted YTASR source. Whisper re-runs (align + transcribe + windowed
re-align): the re-align span set is derived from the pass-1 placements, which
shift once the third source enters, so the reset run's captured two-source slices
can't be trusted. Stem separation is skipped (cached ``vocal/`` stems; a cached
``dereverb/`` stem is reused too).

A caption that fails the ytasr quality gate (:func:`ytasr.is_usable`) is one the
live pipeline would also have run two-source, so its song is left untouched.

Run from the repo root::

    python scripts/repair_ytasr_from_backup.py [folder] [--backup NAME] [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path

# Allow running as ``python scripts/repair_ytasr_from_backup.py`` from repo root,
# and import the regen tool's run harness as a sibling module.
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS.parent))
sys.path.insert(0, str(_SCRIPTS))

from regen_alignment_bundles import Plan, SongJob, _make_genius, run_jobs  # noqa: E402

from pikaraoke.lib import youtube_dl, ytasr  # noqa: E402
from pikaraoke.lib.ffmpeg import probe_duration  # noqa: E402
from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402

logger = logging.getLogger(__name__)

VIDEO_EXTS = (".mp4", ".mkv", ".avi", ".webm", ".mov")


def _find_video(folder: Path, stem: str) -> Path | None:
    for ext in VIDEO_EXTS:
        candidate = folder / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _latest_backup(folder: Path) -> Path | None:
    """Most recent ``regen_backup_<UTC>/`` dir (timestamp names sort chronologically)."""
    backups = sorted(folder.glob("regen_backup_*"))
    return backups[-1] if backups else None


def _read_bundle(folder: Path, stem: str) -> dict | None:
    path = folder / "alignment_debug" / f"{stem}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Ignoring unreadable bundle %s: %s", path, e)
        return None


def _build_job(folder: Path, backup_asr: Path) -> tuple[SongJob | None, str]:
    """Resolve one backed-up caption to a runnable seed job, or a skip reason.

    Requires a genius-origin bundle with a recorded identity and lyric lines and
    a caption that clears the ytasr gate — the exact conditions under which the
    live pipeline adopts the caption as the joint matcher's third source.
    """
    stem = backup_asr.name[: -len(youtube_dl.ASR_JSON3_SUFFIX)]
    video = _find_video(folder, stem)
    if video is None:
        return None, "no video file"

    bundle = _read_bundle(folder, stem)
    if bundle is None:
        return None, "no bundle"
    lyrics = bundle.get("lyrics") or {}
    if lyrics.get("origin") != "genius":
        return None, f"origin={lyrics.get('origin')} (not genius)"
    genius = lyrics.get("genius")
    lines = lyrics.get("lines") or lyrics.get("align_lines")
    if not (genius and lines):
        return None, "bundle missing genius identity or lines"

    duration = probe_duration(video)
    words, word_seg_frac = ytasr.parse_json3(backup_asr.read_text(encoding="utf-8"))
    if not ytasr.is_usable(words, word_seg_frac, duration):
        wpm = round(len(words) / (duration / 60.0), 1) if duration else None
        return None, f"ytasr fails gate ({len(words)} words, {wpm} wpm)"

    rel = f"subtitles/{stem}{youtube_dl.ASR_JSON3_SUFFIX}"
    wpm = round(len(words) / (duration / 60.0), 1) if duration else None
    seed = {
        "lyrics_origin": "genius",
        "genius": genius,
        "media_duration_s": duration,
        # Same shape lyrics_fetch._resolve_ytasr stashes; the align stage reads
        # asr_file (relative to the song dir) to load the restored caption.
        "ytasr": {"asr_file": rel, "n_words": len(words), "wpm": wpm},
    }
    plan = Plan(kind="seed", lyrics_lines=list(lines), seed=seed, label="reuse genius+ytasr")
    return SongJob(song_path=video, bundle=bundle, stale_reason="ytasr", plan=plan), ""


def restore_captions(backup: Path, folder: Path) -> int:
    """Copy backed-up ``.asr.json3`` captions into ``subtitles/`` (skip existing).

    These are download-time artifacts the reset wiped; restoring them is correct
    regardless of which songs get reprocessed. Returns the number copied.
    """
    subs = folder / "subtitles"
    subs.mkdir(exist_ok=True)
    copied = 0
    for src in sorted((backup / "subtitles").glob(f"*{youtube_dl.ASR_JSON3_SUFFIX}")):
        dst = subs / src.name
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        copied += 1
    return copied


def clear_generated_srt(folder: Path, jobs: list[SongJob]) -> None:
    """Delete each target's reset-generated ``subtitles/<stem>.srt``.

    A genius song has no real YouTube caption, so the ``<stem>.srt`` on disk is
    the reset run's two-source output. Left in place it makes ``_should_write_srt``
    skip regeneration and mislabels the caption as a real one; deleting it lets
    the re-run write a fresh 3-source SRT. ``<stem>.en.srt`` (a real caption) is
    never touched — its presence would have made the song srt-origin, not genius.
    """
    for job in jobs:
        (folder / "subtitles" / f"{job.song_path.stem}.srt").unlink(missing_ok=True)


def print_report(jobs: list[SongJob], skips: list[tuple[str, str]], folder: Path, backup: Path):
    print(f"\nLibrary: {folder}")
    print(f"Backup:  {backup.name}")
    print(f"Songs to repair (genius + usable ASR): {len(jobs)}\n")
    if jobs:
        width = max(len(j.song_path.name) for j in jobs)
        for j in jobs:
            print(f"  {j.song_path.name:<{width}}  {j.plan.label}")
    if skips:
        print(f"\nSkipped ({len(skips)}):")
        width = max(len(s) for s, _ in skips)
        for stem, reason in skips:
            print(f"  {stem:<{width}}  {reason}")
    print()


def parse_args() -> argparse.Namespace:
    default_folder = PreferenceManager().get("download_path", "") or "."
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("folder", nargs="?", default=default_folder, help="Song library folder")
    p.add_argument("--backup", help="regen_backup_<UTC> dir name (default: latest)")
    p.add_argument("--dry-run", action="store_true", help="Report and exit without changes")
    p.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    return p.parse_args()


def main() -> int:
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2

    backup = (folder / args.backup) if args.backup else _latest_backup(folder)
    if backup is None or not backup.is_dir():
        print(f"No backup found in {folder}", file=sys.stderr)
        return 2

    jobs: list[SongJob] = []
    skips: list[tuple[str, str]] = []
    for asr in sorted((backup / "subtitles").glob(f"*{youtube_dl.ASR_JSON3_SUFFIX}")):
        job, reason = _build_job(folder, asr)
        if job is not None:
            jobs.append(job)
        else:
            skips.append((asr.name[: -len(youtube_dl.ASR_JSON3_SUFFIX)], reason))

    print_report(jobs, skips, folder, backup)
    if not jobs:
        return 0
    if args.dry_run:
        return 0
    if not args.yes:
        reply = input(f"Restore captions and re-run {len(jobs)} song(s)? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 0

    copied = restore_captions(backup, folder)
    print(f"Restored {copied} ASR caption(s) into subtitles/.")
    clear_generated_srt(folder, jobs)

    config = PipelineConfig()
    config.intermediate_dir = get_temp_directory()
    genius = _make_genius()

    succeeded, failed, skipped = run_jobs(jobs, config, genius)
    print(f"\nDone. succeeded={succeeded} failed={failed} skipped={skipped}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
