#!/usr/bin/env python3
"""Regenerate alignment-debug bundles by re-driving the pipeline.

Re-runs the lyric-alignment stage over songs in a library so each
``<song>/alignment_debug/<stem>.json`` reflects the current matcher and
schema.  The expensive inputs are reused, not recomputed: cached
``vocal/<stem>---vocal.m4a`` is decoded back to WAV (separation skipped),
and a reverb-washed song's de-reverb stem is cached to
``dereverb/<stem>---dereverb.m4a`` and reused on later runs.  Whisper still
re-runs (align + transcribe) — that is how the bundle's word lists are
produced.

Two modes:

  * default -> trust the existing bundles and on-disk artifacts.  Only songs
    whose bundle is missing or older than the current ``SCHEMA_VERSION`` are
    touched; each reuses its recorded lyric source (an srt-origin caption, or a
    Genius identity replaying the YTASR 3rd source from the persisted
    ``.asr.json3``).  A song with no reusable source falls back to downloading
    the video's manual English caption, and to a Genius prompt when none exists.

  * ``--reset`` -> rebuild every song's lyric source from scratch, ignoring the
    recorded provenance.  The subtitles/karaoke/lyrics folders are wiped after
    the backup (the pipeline rebuilds them, so no stale file survives), then for
    each video YouTube's manual English caption is downloaded and used; when
    none exists, a Genius pick is prompted.  Stems are still reused — only the
    lyric/caption resolution is reset.

Fetched captions are gated by a fixed words-per-minute floor so a dialog-only
track is sent to the Genius prompt instead of aligned as lyrics.

Before overwriting outputs, the ``subtitles/``, ``karaoke/``, ``lyrics/`` and
``alignment_debug/`` folders are copied once into ``<folder>/regen_backup_<UTC>/``.

With ``--song``, only the selected songs run, and the backup and the ``--reset``
wipe touch only those songs' own files.

Run from the repo root::

    python scripts/regen_alignment_bundles.py [folder] [--reset] [--song PATTERN]... [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Allow running as ``python scripts/regen_alignment_bundles.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import lrclib  # noqa: E402
from pikaraoke.lib.genius import GeniusClient  # noqa: E402
from pikaraoke.lib.get_platform import (  # noqa: E402
    get_default_dl_dir,
    get_platform,
    get_temp_directory,
)
from pikaraoke.lib.library_regen import (  # noqa: E402
    Plan,
    SongJob,
    backfill_lrc,
    backup_text_folders,
    build_stages,
    clear_output_folders,
    default_query,
    fetch_caption,
    find_local_srt,
    finish_regen_job,
    is_genius_reuse,
    list_videos,
    prepare_lyrics,
    put_back_lrc,
    resolve_plan,
    scan_folder,
)
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402
from pikaraoke.pipeline.workers.stem_worker import StemWorker  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402
from scripts.song_select import select_songs  # noqa: E402

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(jobs: list[SongJob], folder: Path, reset: bool, selected: bool = False) -> None:
    if selected:
        scope = "selected songs (reset)" if reset else "selected songs"
    elif reset:
        scope = "all songs (reset)"
    else:
        scope = "missing/stale bundles"
    print(f"\nScanned: {folder}")
    print(f"Selection: {scope}")
    print(f"Songs to regenerate: {len(jobs)}\n")
    if not jobs:
        return
    width = max(len(j.song_path.name) for j in jobs)
    print(f"{'song':<{width}}  {'bundle':<8}  plan")
    print(f"{'-' * width}  {'-' * 8}  {'-' * 30}")
    for j in jobs:
        plan_label = j.plan.label if j.plan else "?"
        print(f"{j.song_path.name:<{width}}  {j.stale_reason:<8}  {plan_label}")
    print()


# ---------------------------------------------------------------------------
# Interactive Genius prompt (only for kind == "prompt")
# ---------------------------------------------------------------------------


def prompt_jobs(jobs: list[SongJob], genius: GeniusClient) -> None:
    """Resolve every ``kind == "prompt"`` job in place via a Genius search."""
    needs = [j for j in jobs if j.plan and j.plan.kind == "prompt"]
    if not needs:
        return
    print("=" * 60)
    print(f"Genius search for {len(needs)} song(s) without a usable video caption.")
    print("Choose a numbered hit, or [s]=local SRT, [t]=transcribe, [k]=skip song.")
    print("=" * 60)
    for job in needs:
        job.plan = _prompt_one(job.song_path, genius)


def _prompt_one(song: Path, genius: GeniusClient) -> Plan:
    print(f"\n{song.name}")
    default_q = default_query(song)
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
            srt = find_local_srt(song)
            if srt is None:
                print("  no local SRT found; will transcribe")
                return Plan(kind="transcribe", label="prompt -> transcribe")
            return Plan(
                kind="seed", lyrics_path=srt, seed={"lyrics_origin": "srt"}, label="prompt -> srt"
            )
        if ans in ("t", "transcribe"):
            return Plan(kind="transcribe", label="prompt -> transcribe")
        if ans in ("k", "skip", "q"):
            return Plan(kind="skip", label="prompt -> skip")
        if ans.isdigit() and hits and 1 <= int(ans) <= len(hits):
            return Plan(kind="sidecar", genius_id=hits[int(ans) - 1].id, label="prompt -> genius")
        if ans:
            # Any other non-empty answer is a re-search query.
            default_q = ans
            continue
        # Empty answer with no hits: re-prompt for a query.


# ---------------------------------------------------------------------------
# Caption downloads and LRCLIB backfill (real run only)
# ---------------------------------------------------------------------------


def execute_fetches(jobs: list[SongJob]) -> None:
    """Resolve every ``kind == "fetch"`` job by downloading the video caption.

    One network call per song, on a real pass only (after the backup); see
    :func:`fetch_caption`.
    """
    targets = [j for j in jobs if j.plan and j.plan.kind == "fetch"]
    if not targets:
        return
    print(f"Fetching video captions for {len(targets)} song(s) via yt-dlp...")
    for job in targets:
        fetch_caption(job)


def execute_lrclib_backfill(jobs: list[SongJob], config: PipelineConfig) -> None:
    """Resolve ``lyrics/<stem>.lrc`` for every genius reuse plan (see :func:`backfill_lrc`)."""
    if not config.lrclib_fill:
        return
    targets = [j for j in jobs if is_genius_reuse(j.plan)]
    if not targets:
        return
    print(f"Backfilling LRCLIB variants for {len(targets)} genius-origin song(s)...")
    for job in targets:
        backfill_lrc(job, config)


# ---------------------------------------------------------------------------
# Execute pipeline per song
# ---------------------------------------------------------------------------


def run_jobs(
    jobs: list[SongJob], config: PipelineConfig, genius: GeniusClient
) -> tuple[int, int, int]:
    """Run each job's pipeline serially. Returns (succeeded, failed, skipped)."""
    config.cache_dereverb_stem = True

    stem_worker = StemWorker(
        model_dir=config.separator_model_dir,
        model_name=config.separator_model_name,
    )
    whisper_worker = WhisperWorker(config.whisper)

    # Holds reused-lyric .txt files for the run; run_one validates the path
    # exists, so it must outlive each job.
    lyrics_dir = Path(tempfile.mkdtemp(prefix="regen_lyrics_", dir=config.intermediate_dir or None))

    runnable = [j for j in jobs if j.plan and j.plan.kind != "skip"]
    skipped = sum(1 for j in jobs if j.plan and j.plan.kind == "skip")
    succeeded = failed = 0
    try:
        # Both workers always start: the de-reverb retry can fire on any song.
        stem_worker.start()
        whisper_worker.start()

        for i, job in enumerate(runnable, 1):
            song = job.song_path
            print(f"\n[{i}/{len(runnable)}] {song.name} — {job.plan.label}")
            lrc_before = lrclib.snapshot_lrc(lrclib.lrc_path(song))
            lyrics_path, lyric_stage = prepare_lyrics(job, genius, lyrics_dir, config)
            stages = build_stages(song, lyric_stage, whisper_worker, config, stem_worker)
            orch = PipelineOrchestrator(stages, stem_worker, whisper_worker, config)
            try:
                ctx = orch.run_one(song, lyrics_path)
                finish_regen_job(song, ctx.artifacts.get("lyric_method"))
                print(f"  OK: {song.name}")
                succeeded += 1
            except Exception as e:
                print(f"  FAILED: {song.name}: {e}")
                put_back_lrc(song, lrc_before)
                failed += 1
    finally:
        shutil.rmtree(lyrics_dir, ignore_errors=True)
        stem_worker.stop()
        whisper_worker.stop()

    return succeeded, failed, skipped


# ---------------------------------------------------------------------------
# Genius client
# ---------------------------------------------------------------------------


_genius_singleton: GeniusClient | None = None


def _make_genius() -> GeniusClient:
    """Return the shared GeniusClient (built once from preferences)."""
    global _genius_singleton
    if _genius_singleton is None:
        prefs = PreferenceManager()
        _genius_singleton = GeniusClient(api_token=prefs.get("genius_token", ""))
    return _genius_singleton


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def setup_process() -> None:
    """Process-wide setup both CLIs' ``main()`` run first: allocator env, logging."""
    # Match processing_manager: reduce CUDA allocator fragmentation so the
    # separator and whisper models can coexist on a single GPU.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pikaraoke.pipeline.stages.lyric_align").setLevel(logging.INFO)


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
        "--reset",
        action="store_true",
        help="Rebuild every song's lyric source from scratch (ignore the "
        "recorded provenance): wipe subtitles/karaoke/lyrics after the backup, "
        "download each video's manual English caption, and prompt for a Genius "
        "pick when none exists. With --song, the backup and the wipe touch only "
        "the selected songs' files. Default touches only missing/stale bundles "
        "and reuses their recorded source.",
    )
    p.add_argument(
        "--song",
        action="append",
        metavar="PATTERN",
        help="Limit to one song: a YouTube ID, the file name, or part of it; "
        "an exact match wins. Repeatable. Each pattern must match exactly one "
        "song. Selected songs run even if their bundle is current.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report and exit without backing up, prompting or running.",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the post-report confirmation prompt.",
    )
    return p.parse_args()


def resolve_and_run(jobs: list[SongJob]) -> int:
    """Resolve caption fetches and Genius prompts, then run the pipeline.

    Builds the pipeline config and the Genius client itself, so both CLIs
    share one setup. Returns the process exit code: 0 on success (including
    nothing left to run after prompts), 1 if any job failed.
    """
    config = PipelineConfig()
    config.intermediate_dir = get_temp_directory()
    genius = _make_genius()
    if not genius._token:
        print(
            "WARNING: no genius_token in preferences; Genius searches will "
            "return no hits. Use [t] (transcribe) or [s] (local SRT) only.\n"
        )

    # Download captions before prompting so a fetch failure falls through to the
    # Genius prompt (and a success skips it).
    execute_fetches(jobs)
    execute_lrclib_backfill(jobs, config)

    prompt_jobs(jobs, genius)
    if not any(j.plan and j.plan.kind != "skip" for j in jobs):
        print("No songs left after prompts.")
        return 0

    succeeded, failed, skipped = run_jobs(jobs, config, genius)
    print(f"\nDone. succeeded={succeeded} failed={failed} skipped={skipped}")
    return 0 if failed == 0 else 1


def main() -> int:
    setup_process()

    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2

    selected: list[Path] | None = None
    if args.song:
        try:
            selected = select_songs(list_videos(folder), args.song)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2

    jobs = scan_folder(folder, args.reset, songs=selected)
    for job in jobs:
        job.plan = resolve_plan(job, reset=args.reset)
    print_report(jobs, folder, args.reset, selected=selected is not None)
    if not jobs:
        return 0

    if args.dry_run:
        return 0

    if not args.yes:
        reply = input(f"Proceed with {len(jobs)} song(s)? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 0

    stems = [p.stem for p in selected] if selected is not None else None
    scope_note = " for the selected songs" if stems is not None else ""

    # Back up before any destructive step (folder wipe, caption download, regen).
    backup = backup_text_folders(folder, stems=stems)
    if backup is not None:
        print(f"Backed up subtitles/karaoke/lyrics/alignment_debug{scope_note} to: {backup}\n")
    else:
        print(f"No subtitles/karaoke/lyrics/alignment_debug folders to back up{scope_note}.\n")

    # Reset rebuilds every output, so wipe the folders up front — no stale
    # caption or transcript survives to be mistaken for current.
    if args.reset:
        try:
            clear_output_folders(folder, stems=stems)
        except OSError as e:
            print(
                f"Reset stopped: {e}. Nothing was processed. Close whatever has the "
                "file open (the app, a player) and rerun; the backup above holds the "
                "files as they were.",
                file=sys.stderr,
            )
            return 1
        print(
            f"Cleared subtitles/karaoke/lyrics{scope_note} (reset); the pipeline rebuilds them.\n"
        )

    return resolve_and_run(jobs)


if __name__ == "__main__":
    sys.exit(main())
