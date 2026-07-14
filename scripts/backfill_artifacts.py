#!/usr/bin/env python3
"""Backfill missing pipeline artifacts for songs already in the library.

Scans the song folder for video files and reports which of the three
pipeline outputs are missing per song:

  * stems     -> ``vocal/<stem>---vocal.m4a`` + ``nonvocal/<stem>---nonvocal.m4a``
  * karaoke   -> ``karaoke/<stem>.ass``
  * subtitles -> ``subtitles/<stem>.srt`` or ``subtitles/<stem>.en.srt``

For each song missing karaoke or subtitles, the user is shown an
interactive Genius search prompt up-front; the chosen lyrics source is
held on the job and resolved to a concrete file (fetched Genius lyrics,
local SRT, or none) at run time, then handed to the pipeline as an
explicit ``lyrics_path``.  Once all prompts are collected, the pipeline
runs unattended.

Only the stages needed to produce missing artifacts run.  When stems
already exist on disk the cached vocal m4a is decoded back to WAV
(``LoadVocalFromM4aStage``) so the separator pass is skipped entirely.

Run from the repo root::

    python scripts/backfill_artifacts.py [--folder PATH] [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Allow running as ``python scripts/backfill_artifacts.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.genius import (  # noqa: E402
    GeniusClient,
    GeniusHit,
    GeniusUnavailable,
)
from pikaraoke.lib.get_platform import (  # noqa: E402
    get_default_dl_dir,
    get_platform,
    get_temp_directory,
)
from pikaraoke.lib.metadata_parser import (  # noqa: E402
    clean_search_query,
    youtube_id_suffix,
)
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.lib.srt_provenance import is_generated  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402
from pikaraoke.pipeline.stages.ffmpeg_extract import FFmpegExtractStage  # noqa: E402
from pikaraoke.pipeline.stages.ffmpeg_transcode import (  # noqa: E402
    FFmpegTranscodeStage,
)
from pikaraoke.pipeline.stages.load_vocal import LoadVocalFromM4aStage  # noqa: E402
from pikaraoke.pipeline.stages.loudnorm_analyze import (  # noqa: E402
    LoudnormAnalyzeStage,
)
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402
from pikaraoke.pipeline.stages.stem_separation import StemSeparationStage  # noqa: E402
from pikaraoke.pipeline.workers.stem_worker import StemWorker  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".webm", ".mov"}

# Artifact-class names used in reports and the missing-set.
STEMS = "stems"
KARAOKE = "karaoke"
SUBTITLES = "subtitles"


@dataclass
class SongJob:
    song_path: Path
    missing: set[str] = field(default_factory=set)
    # Populated during phase 2 (Genius prompt) or by --use-bundle-lyrics:
    #   ("genius", genius_id) | ("srt",) | ("raw",) | ("skip",)
    #   | ("bundle", bundle_json_path)
    choice: tuple = ()


# ---------------------------------------------------------------------------
# Phase 1 — scan
# ---------------------------------------------------------------------------


def scan_folder(folder: Path) -> list[SongJob]:
    """Return a list of jobs, one per video file with any missing artifact."""
    jobs: list[SongJob] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
            continue
        missing = _missing_artifacts(path)
        if missing:
            jobs.append(SongJob(song_path=path, missing=missing))
    return jobs


def _missing_artifacts(song: Path) -> set[str]:
    stem = song.stem
    parent = song.parent
    missing: set[str] = set()

    vocal_m4a = parent / "vocal" / f"{stem}---vocal.m4a"
    nonvocal_m4a = parent / "nonvocal" / f"{stem}---nonvocal.m4a"
    if not (vocal_m4a.is_file() and nonvocal_m4a.is_file()):
        missing.add(STEMS)

    ass_file = parent / "karaoke" / f"{stem}.ass"
    if not ass_file.is_file():
        missing.add(KARAOKE)

    srt_file = parent / "subtitles" / f"{stem}.srt"
    en_srt = parent / "subtitles" / f"{stem}.en.srt"
    if not (srt_file.is_file() or en_srt.is_file()):
        missing.add(SUBTITLES)

    return missing


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(jobs: list[SongJob], folder: Path) -> None:
    print(f"\nScanned: {folder}")
    print(f"Songs needing work: {len(jobs)}\n")
    if not jobs:
        return
    width = max(len(j.song_path.name) for j in jobs)
    print(f"{'song':<{width}}  missing")
    print(f"{'-' * width}  {'-' * 30}")
    for j in jobs:
        ordered = [t for t in (STEMS, KARAOKE, SUBTITLES) if t in j.missing]
        print(f"{j.song_path.name:<{width}}  {', '.join(ordered)}")
    print()


# ---------------------------------------------------------------------------
# Phase 2 — interactive Genius prompt
# ---------------------------------------------------------------------------


def _default_query(song: Path) -> str:
    """Strip the YouTube ID suffix and tidy the title for a search query."""
    suffix = youtube_id_suffix(str(song))
    title = song.stem[: -len(suffix)] if suffix else song.stem
    cleaned = clean_search_query(title)
    return cleaned or title


def apply_bundle_lyric_choices(jobs: list[SongJob], bundles_dir: Path) -> int:
    """Pre-populate ``job.choice`` for any song with a cached bundle.

    With ``--use-bundle-lyrics`` we short-circuit the Genius search and
    re-use the cleaned ``lyrics.align_lines`` stored in the alignment-debug
    bundle. The pipeline still runs ``parse_lyric_lines`` on the resulting
    .txt (idempotent on already-cleaned text), so all current cleanup
    logic applies. Returns the number of jobs auto-resolved.
    """
    n = 0
    for job in jobs:
        if job.choice:
            continue
        if not (KARAOKE in job.missing or SUBTITLES in job.missing):
            continue
        bundle_path = bundles_dir / f"{job.song_path.stem}.json"
        if not bundle_path.is_file():
            continue
        job.choice = ("bundle", bundle_path)
        n += 1
    return n


def prompt_genius_choices(jobs: list[SongJob], genius: GeniusClient) -> list[SongJob]:
    """Walk each job needing lyric work; populate ``job.choice``.

    Jobs with ``job.choice`` already set (e.g. by ``--use-bundle-lyrics``)
    are kept as-is without prompting.

    Returns the kept jobs (skip choices are dropped from the run list).
    """
    needs_prompt = [
        j for j in jobs if (KARAOKE in j.missing or SUBTITLES in j.missing) and not j.choice
    ]
    if not needs_prompt:
        return jobs

    print("=" * 60)
    print(f"Genius search for {len(needs_prompt)} song(s) needing lyrics.")
    print("Choose a numbered hit, or [s]=local SRT, [t]=transcribe, [k]=skip song.")
    print("=" * 60)

    kept: list[SongJob] = []
    needs_set = {id(j) for j in needs_prompt}
    for j in jobs:
        if id(j) not in needs_set:
            kept.append(j)
            continue
        choice = _prompt_one(j, genius)
        if choice == ("skip",):
            print(f"  -> skipped: {j.song_path.name}\n")
            continue
        j.choice = choice
        kept.append(j)
    return kept


def _prompt_one(job: SongJob, genius: GeniusClient) -> tuple:
    print(f"\n{job.song_path.name}")
    default_q = _default_query(job.song_path)

    while True:
        query = input(f"  search query [{default_q}]: ").strip() or default_q
        hits = genius.search(query, limit=8)
        if not hits:
            print("  (no Genius hits)")
        else:
            for i, h in enumerate(hits, 1):
                print(f"  {i}) {h.title} - {h.artist}")

        if hits:
            prompt = f"  choose [1-{len(hits)}/s/t/k or new query]: "
        else:
            prompt = "  choose [s/t/k or new query]: "
        ans = input(prompt).strip().lower()

        if ans in ("s", "srt"):
            return ("srt",)
        if ans in ("t", "transcribe"):
            return ("raw",)
        if ans in ("k", "skip", "q"):
            return ("skip",)
        if ans.isdigit() and hits and 1 <= int(ans) <= len(hits):
            return ("genius", hits[int(ans) - 1].id)
        if ans:
            # Treat any other non-empty answer as a re-search query.
            default_q = ans
            continue
        # Empty answer with no hits: re-prompt for a query.


def _find_local_srt(song: Path) -> Path | None:
    """Return ``subtitles/<stem>.en.srt`` then ``<stem>.srt``, or None."""
    subs = song.parent / "subtitles"
    for name in (f"{song.stem}.en.srt", f"{song.stem}.srt"):
        candidate = subs / name
        if candidate.is_file() and not is_generated(candidate):
            return candidate
    return None


def resolve_lyrics_path(job: SongJob, genius: GeniusClient, lyrics_dir: Path) -> Path | None:
    """Resolve the explicit ``lyrics_path`` to hand ``run_one``, or None.

    The pipeline reads only ``ctx.artifacts["lyrics_path"]``; the
    orchestrator sets it from the ``run_one`` argument.  We resolve the
    user's phase-2 choice to a concrete file here rather than via the
    YouTube-ID-keyed choice sidecar, so songs without a YouTube ID can
    still use Genius lyrics.

      * genius -> fetch lyrics, write ``<stem>.txt``, return it
      * srt    -> existing local SRT, return it
      * bundle -> reuse cached align_lines from alignment-debug bundle,
                  write ``<stem>.txt``, return it
      * raw    -> None (force transcription)
    """
    kind = job.choice[0] if job.choice else "raw"

    if kind == "genius":
        try:
            text = genius.fetch_lyrics(job.choice[1])
        except GeniusUnavailable as e:
            print(f"  ! Genius fetch failed ({e}); transcribing instead")
            return None
        out = lyrics_dir / f"{job.song_path.stem}.txt"
        out.write_text(text, encoding="utf-8")
        return out

    if kind == "srt":
        srt_path = _find_local_srt(job.song_path)
        if srt_path is None:
            print("  ! no local SRT found; transcribing instead")
        return srt_path

    if kind == "bundle":
        bundle_path = Path(job.choice[1])
        try:
            data = json.loads(bundle_path.read_text())
            align_lines = data["lyrics"]["align_lines"]
        except (OSError, KeyError, json.JSONDecodeError) as e:
            print(f"  ! bundle read failed ({e}); transcribing instead")
            return None
        out = lyrics_dir / f"{job.song_path.stem}.txt"
        out.write_text("\n".join(align_lines), encoding="utf-8")
        return out

    return None


# ---------------------------------------------------------------------------
# Phase 3 — execute pipeline per song
# ---------------------------------------------------------------------------


def build_stages_for(missing: set[str], whisper, config: PipelineConfig, stem_worker):
    """Return only the stages needed for *missing*.

    Lyrics are resolved by the CLI (``resolve_lyrics_path``) and handed
    to ``run_one`` as an explicit path, so no LyricsFetchStage is needed.
    LoadVocalFromM4aStage decodes the cached vocal m4a back to WAV when
    the separator pass is skipped.
    """
    needs_stems = STEMS in missing
    needs_lyric = KARAOKE in missing or SUBTITLES in missing

    stages = []
    if needs_stems:
        stages.append(FFmpegExtractStage(config))
        stages.append(LoudnormAnalyzeStage(config))
        stages.append(StemSeparationStage(stem_worker))
        stages.append(FFmpegTranscodeStage(config))
    elif needs_lyric:
        stages.append(LoadVocalFromM4aStage())
    if needs_lyric:
        stages.append(LyricAlignStage(whisper, config))
    return stages


_genius_singleton: GeniusClient | None = None


def _make_genius(_config: PipelineConfig) -> GeniusClient:
    """Return the shared GeniusClient (built once from preferences)."""
    global _genius_singleton
    if _genius_singleton is None:
        prefs = PreferenceManager()
        _genius_singleton = GeniusClient(api_token=prefs.get("genius_token", ""))
    return _genius_singleton


def run_jobs(jobs: list[SongJob], config: PipelineConfig, genius: GeniusClient) -> tuple[int, int]:
    """Run each job's pipeline serially.  Returns (succeeded, failed)."""
    any_stems = any(STEMS in j.missing for j in jobs)
    any_lyric = any(KARAOKE in j.missing or SUBTITLES in j.missing for j in jobs)

    stem_worker = StemWorker(
        model_dir=config.separator_model_dir,
        model_name=config.separator_model_name,
    )
    whisper_worker = WhisperWorker(config.whisper)

    # Holds fetched Genius lyrics .txt files for the duration of the run;
    # run_one validates that lyrics_path exists, so it must outlive each job.
    lyrics_dir = Path(
        tempfile.mkdtemp(prefix="backfill_lyrics_", dir=config.intermediate_dir or None)
    )

    succeeded = failed = 0
    try:
        # Start workers inside the try so a second-worker startup failure
        # (e.g. CUDA OOM when both models contend for one GPU) still runs the
        # finally and stops whichever worker did start. stop() is a no-op on a
        # worker that never started.
        if any_stems:
            stem_worker.start()
        if any_lyric:
            whisper_worker.start()

        for i, job in enumerate(jobs, 1):
            print(f"\n[{i}/{len(jobs)}] {job.song_path.name}")
            print(f"  missing: {', '.join(sorted(job.missing))}")
            stages = build_stages_for(job.missing, whisper_worker, config, stem_worker)
            if not stages:
                print("  (nothing to do)")
                continue
            needs_lyric = KARAOKE in job.missing or SUBTITLES in job.missing
            lyrics_path = resolve_lyrics_path(job, genius, lyrics_dir) if needs_lyric else None
            orch = PipelineOrchestrator(stages, stem_worker, whisper_worker, config)
            try:
                orch.run_one(job.song_path, lyrics_path)
                print(f"  OK: {job.song_path.name}")
                succeeded += 1
            except Exception as e:
                print(f"  FAILED: {job.song_path.name}: {e}")
                failed += 1
    finally:
        shutil.rmtree(lyrics_dir, ignore_errors=True)
        if any_stems:
            stem_worker.stop()
        if any_lyric:
            whisper_worker.stop()

    return succeeded, failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "folder",
        nargs="?",
        default=default_folder,
        help=f"Song folder to scan (default: {default_folder})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report and exit without prompting or running.",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the post-report confirmation prompt.",
    )
    p.add_argument(
        "--use-bundle-lyrics",
        action="store_true",
        help=(
            "For each song missing karaoke/subtitles, if an alignment-debug "
            "bundle exists at <folder>/alignment_debug/<stem>.json, reuse "
            "its cleaned lyrics.align_lines instead of prompting for a "
            "Genius search hit. Songs without a bundle still prompt normally."
        ),
    )
    return p.parse_args()


def main() -> int:
    # Match processing_manager: reduce CUDA allocator fragmentation so the
    # separator and whisper models can coexist on a single GPU.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Pipeline stages are chatty; trim to WARNING for the noisiest ones.
    logging.getLogger("pikaraoke.pipeline.stages.lyric_align").setLevel(logging.INFO)

    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2

    jobs = scan_folder(folder)
    print_report(jobs, folder)
    if not jobs:
        return 0

    if args.dry_run:
        return 0

    if not args.yes:
        reply = input(f"Proceed with {len(jobs)} song(s)? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 0

    config = PipelineConfig()
    config.intermediate_dir = get_temp_directory()
    genius = _make_genius(config)
    if not genius._token:
        print(
            "WARNING: no genius_token in preferences; Genius searches will "
            "return no hits. Use [t] (transcribe) or [s] (local SRT) only.\n"
        )

    if args.use_bundle_lyrics:
        n_bundle = apply_bundle_lyric_choices(jobs, folder / "alignment_debug")
        if n_bundle:
            print(f"Reusing bundle lyrics for {n_bundle} song(s); skipping their Genius prompts.")

    jobs = prompt_genius_choices(jobs, genius)
    if not jobs:
        print("No songs left after prompts.")
        return 0

    succeeded, failed = run_jobs(jobs, config, genius)
    print(f"\nDone. succeeded={succeeded} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
