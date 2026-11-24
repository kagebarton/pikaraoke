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

Three modes:

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

  * ``--lrclib-auto`` -> check every song the joint matcher still times from a
    Genius sheet against LRCLIB (the check a first-time download runs, on the
    words each bundle already stores), then re-time the songs a record passes
    from that record, on the cue route.  The pick is made before any GPU time is
    spent, so ``--dry-run`` lists which songs would switch and to which record.
    A song no record passes, and one whose ``.lrc`` is a skip marker or unreadable,
    is left as it is.

Fetched captions are gated by a fixed words-per-minute floor so a dialog-only
track is sent to the Genius prompt instead of aligned as lyrics.

Before overwriting outputs, the ``subtitles/``, ``karaoke/``, ``lyrics/`` and
``alignment_debug/`` folders are copied once into ``<folder>/regen_backup_<UTC>/``.

With ``--song``, only the selected songs run, and the backup and the ``--reset``
wipe touch only those songs' own files.  With ``--lrclib-auto`` the backup covers
only the songs a record passes.

Run from the repo root::

    python scripts/regen_alignment_bundles.py [folder] [--reset | --lrclib-auto] [--song PATTERN]... [--dry-run] [--yes]
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

from pikaraoke.lib import lrc_auto_timing, lrclib  # noqa: E402
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
    fetch_caption,
    find_local_srt,
    finish_regen_job,
    is_genius_reuse,
    list_videos,
    media_duration,
    prepare_lyrics,
    put_back_lyric_files,
    resolve_plan,
    scan_folder,
    sheet_plan,
    snapshot_lyric_files,
)
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402
from pikaraoke.pipeline.workers.stem_worker import StemWorker  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402
from scripts.genius_prompt import HELP as GENIUS_HELP  # noqa: E402
from scripts.genius_prompt import ask_lyrics_source  # noqa: E402
from scripts.song_select import select_songs  # noqa: E402

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(
    jobs: list[SongJob],
    folder: Path,
    reset: bool,
    selected: bool = False,
    lrclib_auto: bool = False,
) -> None:
    if lrclib_auto:
        scope = "Genius songs on joint, checked against LRCLIB"
        scope += " (selected songs)" if selected else ""
    elif selected:
        scope = "selected songs (reset)" if reset else "selected songs"
    elif reset:
        scope = "all songs (reset)"
    else:
        scope = "missing/stale bundles"
    print(f"\nScanned: {folder}")
    print(f"Selection: {scope}")
    if lrclib_auto:
        retimed = sum(1 for j in jobs if j.plan.kind != "skip")
        print(f"Songs checked: {len(jobs)}; to re-time: {retimed}\n")
    else:
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
    print(GENIUS_HELP)
    print("=" * 60)
    for job in needs:
        job.plan = _prompt_one(job.song_path, genius)


def _prompt_one(song: Path, genius: GeniusClient) -> Plan:
    choice = ask_lyrics_source(song, genius)
    if choice[0] == "genius":
        return Plan(kind="sidecar", genius_id=choice[1], label="prompt -> genius")
    if choice[0] == "skip":
        return Plan(kind="skip", label="prompt -> skip")
    if choice[0] == "srt":
        srt = find_local_srt(song)
        if srt is not None:
            return Plan(
                kind="seed", lyrics_path=srt, seed={"lyrics_origin": "srt"}, label="prompt -> srt"
            )
        print("  no local SRT found; will transcribe")
    return Plan(kind="transcribe", label="prompt -> transcribe")


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
# --lrclib-auto: the LRCLIB check of songs the joint matcher times from Genius
# ---------------------------------------------------------------------------


def lrclib_auto_refusal(job: SongJob) -> str | None:
    """Why the LRCLIB check does not apply to ``job``, or None when it does.

    Only a song the joint matcher still times from its Genius lyrics is checked: a custom
    sheet, a caption, an LRCLIB timing or a transcription is not. A skip marker or a
    hand-placed ``.lrc`` is someone's call, and the check needs the words the transcriber
    heard and the clip length.
    """
    if not is_genius_reuse(job.plan):
        return f"it is not a Genius song on joint ({job.plan.label})"
    state = lrclib.read_song_lrc(job.song_path).state
    if state == "skipped":
        return "its .lrc is a no-match marker"
    if state == "unreadable":
        return "its .lrc can't be read"
    if not job.bundle.get("transcribe_words"):
        return "its bundle holds no transcribe words"
    if media_duration(job) is None:
        return "its length is unknown"
    return None


def lrclib_auto_plan(job: SongJob) -> Plan:
    """The plan for one eligible song: its LRCLIB pick on the cue route, or a skip saying why.

    The check is a first-time download's, run on the words the bundle already stores, so
    the pick is made before any GPU time is spent. A pick is the plan Repair builds for an
    LRCLIB record, with the automatic sheet's kind.
    """
    auto = lrc_auto_timing.check(
        job.plan.seed["genius"], job.bundle["transcribe_words"], media_duration(job)
    )
    counts = auto.record()
    if auto.entry is None:
        return Plan(kind="skip", label=_stays_label(counts))
    plan = sheet_plan(job.song_path, "lrclib_auto", auto.entry.fit.srt)
    plan.lrclib_record = auto.entry.record
    plan.label = _pick_label(counts["pick"])
    return plan


def _pick_label(pick: dict) -> str:
    return (
        f"LRCLIB (auto) {pick['id']}: {pick['trackName']} · {pick['artistName']} "
        f"(mistimed {pick['mistimed']}, unclaimed run {pick['unclaimed_run']}, "
        f"shift run {pick['shift_run']}, on {pick['timing_size']} records)"
    )


def _stays_label(counts: dict) -> str:
    outcome = counts["outcome"]
    if outcome == lrc_auto_timing.NO_PICK:
        refused = ", ".join(f"{why} {n}" for why, n in counts["refusals"].items())
        return f"stays on joint: no record passed ({counts['records']} records; {refused})"
    if outcome == lrc_auto_timing.NO_RECORDS:
        return "stays on joint: no synced LRCLIB record"
    return f"stays on joint: LRCLIB check could not run ({outcome}); rerun later"


def check_lrclib_auto(jobs: list[SongJob], named: bool) -> list[SongJob]:
    """Keep the jobs the LRCLIB check applies to, each with its plan set by the check.

    ``named``: the songs were chosen with ``--song``, so each one dropped says why. The
    progress goes to stderr, which leaves stdout the report.
    """
    eligible = []
    for job in jobs:
        reason = lrclib_auto_refusal(job)
        if reason is None:
            eligible.append(job)
        elif named:
            print(f"{job.song_path.name}: not checked, {reason}")
    for i, job in enumerate(eligible, 1):
        print(f"[{i}/{len(eligible)}] {job.song_path.name}", file=sys.stderr, flush=True)
        job.plan = lrclib_auto_plan(job)
    return eligible


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
            files_before = None
            try:
                # Inside the try: one song whose files can't be read fails alone.
                files_before = snapshot_lyric_files(song)
                lyrics_path, lyric_stage = prepare_lyrics(job, genius, lyrics_dir, config)
                stages = build_stages(
                    song,
                    lyric_stage,
                    whisper_worker,
                    config,
                    stem_worker,
                    auto_lrc_timing=job.first_download,
                )
                orch = PipelineOrchestrator(stages, stem_worker, whisper_worker, config)
                ctx = orch.run_one(song, lyrics_path)
                finish_regen_job(song, ctx.artifacts.get("lyric_method"))
                print(f"  OK: {song.name}")
                succeeded += 1
            except Exception as e:
                print(f"  FAILED: {song.name}: {e}")
                if files_before is not None:
                    put_back_lyric_files(files_before)
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
        "--lrclib-auto",
        action="store_true",
        help="Check every song the joint matcher still times from a Genius sheet "
        "against LRCLIB, with the bar a first-time download uses, and re-time the "
        "songs a record passes from that record on the cue route. A song no record "
        "passes is left as it is. The check searches LRCLIB even with --dry-run, "
        "which then lists the songs that would switch and stops. Can't be combined "
        "with --reset. With --song, narrows the check to those songs.",
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
    args = p.parse_args()
    if args.lrclib_auto and args.reset:
        p.error("--lrclib-auto can't be combined with --reset")
    return args


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


def confirm(count: int) -> bool:
    """Ask whether to run ``count`` songs; an answer other than yes aborts."""
    reply = input(f"Proceed with {count} song(s)? [y/N] ").strip().lower()
    if reply in ("y", "yes"):
        return True
    print("Aborted.")
    return False


def back_up(folder: Path, stems: list[str] | None, scope_note: str) -> None:
    """Snapshot the output folders (only ``stems``' own files when given) and say where."""
    backup = backup_text_folders(folder, stems=stems)
    if backup is not None:
        print(f"Backed up subtitles/karaoke/lyrics/alignment_debug{scope_note} to: {backup}\n")
    else:
        print(f"No subtitles/karaoke/lyrics/alignment_debug folders to back up{scope_note}.\n")


def run_lrclib_auto(
    args: argparse.Namespace, folder: Path, jobs: list[SongJob], named: bool
) -> int:
    """The ``--lrclib-auto`` mode after the scan: check, report, then re-time the picks.

    The songs no record passes stay in the run as skips, so its final line counts them.
    """
    jobs = check_lrclib_auto(jobs, named)
    print_report(jobs, folder, False, selected=named, lrclib_auto=True)
    picked = [j for j in jobs if j.plan.kind != "skip"]
    if not picked:
        print("Nothing to re-time.")
        return 0
    if args.dry_run:
        return 0
    if not args.yes and not confirm(len(picked)):
        return 0
    back_up(folder, [j.song_path.stem for j in picked], " for the re-timed songs")
    return resolve_and_run(jobs)


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

    jobs = scan_folder(folder, args.reset or args.lrclib_auto, songs=selected)
    for job in jobs:
        job.plan = resolve_plan(job, reset=args.reset)
    if args.lrclib_auto:
        return run_lrclib_auto(args, folder, jobs, named=selected is not None)
    print_report(jobs, folder, args.reset, selected=selected is not None)
    if not jobs:
        return 0

    if args.dry_run:
        return 0

    if not args.yes and not confirm(len(jobs)):
        return 0

    stems = [p.stem for p in selected] if selected is not None else None
    scope_note = " for the selected songs" if stems is not None else ""

    # Back up before any destructive step (folder wipe, caption download, regen).
    back_up(folder, stems, scope_note)

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
