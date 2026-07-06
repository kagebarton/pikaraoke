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

Before overwriting outputs, the ``subtitles/``, ``karaoke/`` and ``lyrics/``
folders are copied once into ``<folder>/regen_backup_<UTC>/``.

Run from the repo root::

    python scripts/regen_alignment_bundles.py [folder] [--reset] [--dry-run] [--yes]
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
from datetime import datetime, timezone
from pathlib import Path

import srt

# Allow running as ``python scripts/regen_alignment_bundles.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.alignment_capture import SCHEMA_VERSION  # noqa: E402
from pikaraoke.lib.ffmpeg import probe_duration  # noqa: E402
from pikaraoke.lib.genius import (  # noqa: E402
    GeniusClient,
    GeniusUnavailable,
    write_choice,
)
from pikaraoke.lib.get_platform import (  # noqa: E402
    get_default_dl_dir,
    get_platform,
    get_temp_directory,
)
from pikaraoke.lib.metadata_parser import (  # noqa: E402
    clean_search_query,
    extract_youtube_id,
    youtube_id_suffix,
)
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.lib.srt_cues import cue_spans_from_srt  # noqa: E402
from pikaraoke.lib.youtube_dl import (  # noqa: E402
    ASR_JSON3_SUFFIX,
    download_manual_en_subs,
)
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.context import StageContext  # noqa: E402
from pikaraoke.pipeline.orchestrator import PipelineOrchestrator  # noqa: E402
from pikaraoke.pipeline.stages.base import BaseStage  # noqa: E402
from pikaraoke.pipeline.stages.ffmpeg_extract import FFmpegExtractStage  # noqa: E402
from pikaraoke.pipeline.stages.ffmpeg_transcode import (  # noqa: E402
    FFmpegTranscodeStage,
)
from pikaraoke.pipeline.stages.load_vocal import LoadVocalFromM4aStage  # noqa: E402
from pikaraoke.pipeline.stages.loudnorm_analyze import (  # noqa: E402
    LoudnormAnalyzeStage,
)
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402
from pikaraoke.pipeline.stages.lyrics_fetch import LyricsFetchStage  # noqa: E402
from pikaraoke.pipeline.stages.stem_separation import StemSeparationStage  # noqa: E402
from pikaraoke.pipeline.workers.stem_worker import StemWorker  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".webm", ".mov"}

# A fetched caption whose cleaned words-per-minute of song falls below this is
# treated as not-really-lyrics (e.g. a dialog-only track) and sent to the
# Genius prompt instead. Applies only to captions pulled fresh from yt-dlp; a
# caption already trusted by an srt-origin bundle is reused as-is.
MIN_CAPTION_WPM = 15.0


# ---------------------------------------------------------------------------
# Seed stage
# ---------------------------------------------------------------------------


class SeedArtifactsStage(BaseStage):
    """Pre-populate ``ctx.artifacts`` for a bundle replay.

    The orchestrator seeds only ``lyrics_path``; the reused lyric origin,
    the YTASR reference and the source duration come from the previous
    bundle and are injected here so ``LyricAlignStage`` reproduces the
    prior run without re-driving ``LyricsFetchStage``.
    """

    name = "seed_artifacts"

    def __init__(self, seed: dict) -> None:
        self._seed = seed

    def run(self, ctx: StageContext) -> None:
        ctx.artifacts.update(self._seed)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    """How to drive one song's pipeline.

    ``kind``:
      * ``seed``       -> reuse from the bundle: feed ``lyrics_path`` (a
        local .srt) or ``lyrics_lines`` (written to a temp .txt) and inject
        ``seed`` via :class:`SeedArtifactsStage`.
      * ``sidecar``    -> a fresh Genius selection: write the choice sidecar
        and run :class:`LyricsFetchStage` (re-fetches lyrics + resolves YTASR).
      * ``fetch``      -> placeholder for a song whose video caption may be
        downloadable: the run phase tries yt-dlp and, on success + length gate,
        becomes a seed-srt plan, else reverts to :attr:`fallback`.
      * ``transcribe`` -> no lyrics; transcription mode (writes no bundle).
      * ``skip``       -> drop the song.
      * ``prompt``     -> placeholder until the interactive pass resolves it.
    """

    kind: str
    lyrics_path: Path | None = None
    lyrics_lines: list[str] | None = None
    seed: dict = field(default_factory=dict)
    genius_id: int | None = None
    label: str = ""
    fallback: "Plan | None" = None


@dataclass
class SongJob:
    song_path: Path
    bundle: dict | None
    stale_reason: str
    plan: Plan | None = None


# ---------------------------------------------------------------------------
# Phase 1 — scan + select
# ---------------------------------------------------------------------------


def _read_bundle(folder: Path, stem: str) -> dict | None:
    path = folder / "alignment_debug" / f"{stem}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Ignoring unreadable bundle %s: %s", path, e)
        return None


def scan_folder(folder: Path, include_all: bool) -> list[SongJob]:
    """Return jobs for the videos in scope.

    Default: bundle missing or ``schema_version < SCHEMA_VERSION``.
    ``include_all``: every video, regardless of bundle state.
    """
    jobs: list[SongJob] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTS:
            continue
        bundle = _read_bundle(folder, path.stem)
        if include_all:
            reason = "all"
        elif bundle is None:
            reason = "missing"
        elif bundle.get("schema_version", 0) < SCHEMA_VERSION:
            reason = f"v{bundle.get('schema_version', 0)}"
        else:
            continue  # current bundle — nothing to do
        jobs.append(SongJob(song_path=path, bundle=bundle, stale_reason=reason))
    return jobs


# ---------------------------------------------------------------------------
# Phase 2 — resolve a lyric plan (no prompting, no network)
# ---------------------------------------------------------------------------


def _find_local_srt(song: Path) -> Path | None:
    """Return ``subtitles/<stem>.en.srt`` then ``<stem>.srt``, or None."""
    subs = song.parent / "subtitles"
    for name in (f"{song.stem}.en.srt", f"{song.stem}.srt"):
        candidate = subs / name
        if candidate.is_file():
            return candidate
    return None


def resolve_plan(job: SongJob, *, reset: bool) -> Plan:
    """Plan one song's lyric source (pure, no I/O writes, no network).

    In the default mode this trusts the previous bundle: a song with recorded
    provenance is reused (see :func:`_reuse_plan`), and only a song without a
    reusable source falls through to download-or-prompt. ``reset`` discards the
    recorded provenance entirely and re-resolves every song from scratch.

    The download-or-prompt fallback is deferred to the run phase: a song with a
    YouTube id becomes a ``fetch`` placeholder (resolved by :func:`execute_fetches`),
    otherwise a Genius ``prompt``.
    """
    if not reset:
        reuse = _reuse_plan(job)
        if reuse is not None:
            return reuse
    return _fetch_or_prompt_plan(job.song_path)


def _reuse_plan(job: SongJob) -> Plan | None:
    """Reuse plan from the previous bundle, or None when nothing is reusable.

    A song is reused only when its provenance is recorded — the regenerated
    schema needs that metadata anyway, so reusing bare lines with unknown
    provenance is pointless:

      * ``origin == "srt"`` + an on-disk caption -> reuse it.
      * recorded Genius identity (``lyrics.genius``) + lines -> reuse the
        bundled lyrics, replaying the YTASR 3rd source when the persisted
        ``.asr.json3`` is on disk.

    The on-disk SRT is never trusted for a non-srt origin:
    ``ground_truth_refs.youtube_srt_present`` is unreliable — the pipeline
    writes its own generated SRT to ``subtitles/<stem>.srt`` and a
    genius/transcribe run with no real caption flags the field off its own
    output.
    """
    bundle = job.bundle
    song = job.song_path
    if bundle is None:
        return None

    lyrics = bundle.get("lyrics") or {}
    origin = lyrics.get("origin")

    if origin == "srt":
        srt = _find_local_srt(song)
        if srt is not None:
            return Plan(
                kind="seed",
                lyrics_path=srt,
                seed={"lyrics_origin": "srt"},
                label="reuse srt (from video)",
            )
        return None

    # Non-srt origin: reuse only when the identity metadata the schema needs
    # is present (Genius id/title/artist).
    genius = lyrics.get("genius")
    lines = lyrics.get("lines") or lyrics.get("align_lines") or []
    if not (genius and lines):
        return None

    seed: dict = {"lyrics_origin": "genius", "genius": genius}
    media = bundle.get("media_duration_s")
    if media is not None:
        seed["media_duration_s"] = media
    label = "reuse genius"
    ytasr = lyrics.get("ytasr")
    if ytasr:
        asr_rel = ytasr.get("asr_file")
        if asr_rel and (song.parent / asr_rel).is_file():
            seed["ytasr"] = ytasr
            label = "reuse genius+ytasr"
        else:
            label = "reuse genius (ytasr json3 missing; two-source)"
    return Plan(kind="seed", lyrics_lines=list(lines), seed=seed, label=label)


def _fetch_or_prompt_plan(song: Path) -> Plan:
    """Download-the-video-caption-or-Genius-prompt plan for a song.

    A song with a YouTube id becomes a ``fetch`` placeholder whose
    :attr:`Plan.fallback` is the Genius prompt; one without an id goes straight
    to the prompt.
    """
    if extract_youtube_id(str(song)):
        return Plan(
            kind="fetch",
            fallback=Plan(kind="prompt", label="genius"),
            label="check youtube caption -> srt or genius",
        )
    return Plan(kind="prompt", label="genius (no youtube id)")


# ---------------------------------------------------------------------------
# Caption length gate
# ---------------------------------------------------------------------------


def _srt_word_count(srt_path: Path) -> int | None:
    """Cleaned-cue word count for an SRT, or None if it can't be parsed.

    Counts the same cleaned cue text the matcher consumes, so a dialog-only
    caption (few sung words) scores low.
    """
    try:
        raw = srt_path.read_text(encoding="utf-8")
        texts, _ = cue_spans_from_srt(raw)
    except (OSError, srt.SRTParseError) as e:
        logger.warning("Cannot read SRT %s: %s", srt_path, e)
        return None
    return sum(len(t.split()) for t in texts)


def _media_duration(job: SongJob) -> float | None:
    """Song duration in seconds: the bundle value, else an ffprobe fallback."""
    recorded = (job.bundle or {}).get("media_duration_s")
    if isinstance(recorded, (int, float)) and recorded > 0:
        return float(recorded)
    return probe_duration(job.song_path)


def _caption_wpm(srt_path: Path, job: SongJob) -> float | None:
    """Words per minute of song for ``srt_path``, or None if not measurable."""
    words = _srt_word_count(srt_path)
    if words is None:
        return None
    duration = _media_duration(job)
    if not duration:
        logger.warning("No duration for %s; skipping length check", job.song_path.name)
        return None
    return words / (duration / 60.0)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(jobs: list[SongJob], folder: Path, reset: bool) -> None:
    scope = "all songs (reset)" if reset else "missing/stale bundles"
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
# Phase 3 — interactive Genius prompt (only for kind == "prompt")
# ---------------------------------------------------------------------------


def _default_query(song: Path) -> str:
    """Strip the YouTube ID suffix and tidy the title for a search query."""
    suffix = youtube_id_suffix(str(song))
    title = song.stem[: -len(suffix)] if suffix else song.stem
    cleaned = clean_search_query(title)
    return cleaned or title


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
    default_q = _default_query(song)
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
            srt = _find_local_srt(song)
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
# Phase 3b — download a video's manual English caption (real run only)
# ---------------------------------------------------------------------------


def execute_fetches(jobs: list[SongJob]) -> None:
    """Resolve every ``kind == "fetch"`` job by downloading the video caption.

    For each fetch-marked song this downloads YouTube's manual English caption
    into ``subtitles/<stem>.en.srt`` (one network call per song). The caption is
    adopted as a seed-srt reuse only when it exists and is dense enough to be
    lyrics (``MIN_CAPTION_WPM``); an adopted caption is promoted to the
    playback-matched ``subtitles/<stem>.srt``. Otherwise the song reverts to its
    fallback (a Genius prompt). Runs on a real pass only, after the backup, so a
    discarded download never clobbers a backed-up caption.
    """
    targets = [j for j in jobs if j.plan and j.plan.kind == "fetch"]
    if not targets:
        return
    print(f"Fetching video captions for {len(targets)} song(s) via yt-dlp...")
    for job in targets:
        song = job.song_path
        fallback = job.plan.fallback or Plan(kind="prompt", label="fetch failed -> genius")
        yt_id = extract_youtube_id(str(song))
        url = f"https://www.youtube.com/watch?v={yt_id}"
        result = download_manual_en_subs(url, str(song.parent / "subtitles"), song.stem)
        if result is None:
            logger.info("No downloadable caption for %s; will prompt", song.name)
            job.plan = fallback
            continue
        srt_path = Path(result)
        wpm = _caption_wpm(srt_path, job)
        if wpm is not None and wpm < MIN_CAPTION_WPM:
            logger.info("Fetched caption for %s too sparse (%.0f wpm); discarding", song.name, wpm)
            srt_path.unlink(missing_ok=True)
            job.plan = fallback
            continue
        # Promote yt-dlp's <stem>.en.srt to the playback-matched <stem>.srt — the
        # same normalization download_manager._move_downloaded_subtitle applies in
        # the live app. Playback (_find_subtitles) and the pipeline's
        # _should_write_srt both key on subtitles/<stem>.srt.
        playback_srt = srt_path.with_name(f"{song.stem}.srt")
        os.replace(srt_path, playback_srt)
        job.plan = Plan(
            kind="seed",
            lyrics_path=playback_srt,
            seed={"lyrics_origin": "srt"},
            label="fetched srt (from video)",
        )


# ---------------------------------------------------------------------------
# Phase 4 — execute pipeline per song
# ---------------------------------------------------------------------------


def _stems_present(song: Path) -> bool:
    vocal = song.parent / "vocal" / f"{song.stem}---vocal.m4a"
    nonvocal = song.parent / "nonvocal" / f"{song.stem}---nonvocal.m4a"
    return vocal.is_file() and nonvocal.is_file()


def _dereverb_cache(song: Path) -> Path:
    return song.parent / "dereverb" / f"{song.stem}---dereverb.m4a"


def _build_stages(song: Path, lyric_stage, whisper, config: PipelineConfig, stem_worker):
    """Stem reuse/generation + the optional lyric stage + lyric-align.

    ``LyricAlignStage`` gets the stem worker so its de-reverb retry (and the
    de-reverb cache) is live — backfill omits it.
    """
    stages: list = []
    if _stems_present(song):
        stages.append(LoadVocalFromM4aStage())
    else:
        # Fresh stems: drop any stale de-reverb cache derived from an old vocal.
        _dereverb_cache(song).unlink(missing_ok=True)
        stages.append(FFmpegExtractStage(config))
        stages.append(LoudnormAnalyzeStage(config))
        stages.append(StemSeparationStage(stem_worker))
        stages.append(FFmpegTranscodeStage(config))
    if lyric_stage is not None:
        stages.append(lyric_stage)
    stages.append(LyricAlignStage(whisper, config, stem_worker))
    return stages


def _prepare_lyrics(job: SongJob, genius: GeniusClient, lyrics_dir: Path):
    """Resolve a job's plan to ``(lyrics_path, lyric_stage)`` for the run.

    Writes the temp .txt for reused Genius lyrics and the choice sidecar for
    a fresh Genius selection. A Genius pick on a song without a YouTube id
    can't use the sidecar, so it degrades to explicit lyrics with no YTASR
    3rd source (logged).
    """
    plan = job.plan
    song = job.song_path

    if plan.kind == "seed":
        if plan.lyrics_lines is not None:
            lyrics_path = lyrics_dir / f"{song.stem}.txt"
            lyrics_path.write_text("\n".join(plan.lyrics_lines), encoding="utf-8")
        else:
            lyrics_path = plan.lyrics_path
        return lyrics_path, SeedArtifactsStage(plan.seed)

    if plan.kind == "sidecar":
        yt_id = extract_youtube_id(str(song))
        if yt_id:
            write_choice(yt_id, {"genius_id": plan.genius_id})
            return None, LyricsFetchStage(genius)
        # No YouTube id — sidecar can't be keyed. Fetch the text directly.
        try:
            gsong = genius.fetch_song(plan.genius_id)
        except GeniusUnavailable as e:
            print(f"  ! Genius fetch failed ({e}); transcribing instead")
            return None, None
        lyrics_path = lyrics_dir / f"{song.stem}.txt"
        lyrics_path.write_text(gsong.text, encoding="utf-8")
        print("  ! no YouTube id; YTASR 3rd source unavailable for this song")
        seed = {
            "lyrics_origin": "genius",
            "genius": {"id": plan.genius_id, "title": gsong.title, "artist": gsong.artist},
        }
        return lyrics_path, SeedArtifactsStage(seed)

    # transcribe: no lyrics, no lyric stage.
    return None, None


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
            lyrics_path, lyric_stage = _prepare_lyrics(job, genius, lyrics_dir)
            stages = _build_stages(song, lyric_stage, whisper_worker, config, stem_worker)
            orch = PipelineOrchestrator(stages, stem_worker, whisper_worker, config)
            try:
                orch.run_one(song, lyrics_path)
                print(f"  OK: {song.name}")
                succeeded += 1
            except Exception as e:
                print(f"  FAILED: {song.name}: {e}")
                failed += 1
    finally:
        shutil.rmtree(lyrics_dir, ignore_errors=True)
        stem_worker.stop()
        whisper_worker.stop()

    return succeeded, failed, skipped


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


# The regenerable per-song output folders: backed up before any run, and wiped
# up front in reset mode (the pipeline rebuilds them, so nothing stale lingers).
OUTPUT_DIRS = ("subtitles", "karaoke", "lyrics")


def backup_text_folders(folder: Path) -> Path | None:
    """Snapshot the regenerable output folders into ``regen_backup_<UTC>/``.

    Returns the backup root, or None when none of the folders exist.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = folder / f"regen_backup_{ts}"
    copied: list[str] = []
    for sub in OUTPUT_DIRS:
        src = folder / sub
        if src.is_dir():
            shutil.copytree(src, backup_root / sub)
            copied.append(sub)
    if not copied:
        return None
    return backup_root


def clear_output_folders(folder: Path) -> None:
    """Delete the regenerable output folders (reset mode, after the backup).

    The pipeline rebuilds subtitles/karaoke/lyrics for every song reset
    reprocesses, so wiping them first guarantees no stale file (e.g. an old
    generated SRT) survives. Stems and bundles live elsewhere and are untouched.

    Exception: ``subtitles/<stem>.en.asr.json3`` YouTube-ASR captions are
    download-time artifacts (fetched by the download manager on first add), and
    nothing in the regen tool re-fetches them. Wiping them would silently drop
    the joint matcher's third source from every genius song on the next run, so
    they are kept in place while the rest of subtitles/ is cleared.
    """
    for sub in OUTPUT_DIRS:
        if sub == "subtitles":
            _clear_except_asr(folder / sub)
        else:
            shutil.rmtree(folder / sub, ignore_errors=True)


def _clear_except_asr(subtitles: Path) -> None:
    """Remove everything in ``subtitles/`` except the non-regenerable ASR captions."""
    if not subtitles.is_dir():
        return
    for entry in list(subtitles.iterdir()):
        if entry.is_file() and entry.name.endswith(ASR_JSON3_SUFFIX):
            continue
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


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
        "pick when none exists. Default touches only missing/stale bundles and "
        "reuses their recorded source.",
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


def main() -> int:
    # Match processing_manager: reduce CUDA allocator fragmentation so the
    # separator and whisper models can coexist on a single GPU.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pikaraoke.pipeline.stages.lyric_align").setLevel(logging.INFO)

    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2

    jobs = scan_folder(folder, args.reset)
    for job in jobs:
        job.plan = resolve_plan(job, reset=args.reset)
    print_report(jobs, folder, args.reset)
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
    genius = _make_genius()
    if not genius._token:
        print(
            "WARNING: no genius_token in preferences; Genius searches will "
            "return no hits. Use [t] (transcribe) or [s] (local SRT) only.\n"
        )

    # Back up before any destructive step (folder wipe, caption download, regen).
    backup = backup_text_folders(folder)
    if backup is not None:
        print(f"Backed up subtitles/karaoke/lyrics to: {backup}\n")
    else:
        print("No subtitles/karaoke/lyrics folders to back up.\n")

    # Reset rebuilds every output, so wipe the folders up front — no stale
    # caption or transcript survives to be mistaken for current.
    if args.reset:
        clear_output_folders(folder)
        print("Cleared subtitles/karaoke/lyrics (reset); the pipeline rebuilds them.\n")

    # Download captions before prompting so a fetch failure falls through to the
    # Genius prompt (and a success skips it).
    execute_fetches(jobs)

    prompt_jobs(jobs, genius)
    if not any(j.plan and j.plan.kind != "skip" for j in jobs):
        print("No songs left after prompts.")
        return 0

    succeeded, failed, skipped = run_jobs(jobs, config, genius)
    print(f"\nDone. succeeded={succeeded} failed={failed} skipped={skipped}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
