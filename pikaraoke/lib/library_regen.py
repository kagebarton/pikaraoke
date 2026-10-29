"""Library regen core: plans, caption gate, backup/wipe and per-song pipeline prep.

Shared by the CLI (``scripts/regen_alignment_bundles.py``) and the web UI, so a
song is planned, backed up and prepared the same way from either.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from collections.abc import Callable, Collection
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import srt

from pikaraoke.lib import lrclib, ytasr
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.ffmpeg import probe_duration
from pikaraoke.lib.genius import GeniusClient, GeniusUnavailable, write_choice
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
from pikaraoke.lib.get_platform import get_temp_directory
from pikaraoke.lib.metadata_parser import (
    clean_search_query,
    extract_youtube_id,
    youtube_id_suffix,
)
from pikaraoke.lib.song_list import SongList
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.lib.srt_provenance import clear_generated_marker, is_generated
from pikaraoke.lib.youtube_dl import (
    ASR_JSON3_SUFFIX,
    CaptionDownloadFailed,
    download_manual_en_subs,
)
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import StageContext
from pikaraoke.pipeline.stages.base import BaseStage
from pikaraoke.pipeline.stages.ffmpeg_extract import FFmpegExtractStage
from pikaraoke.pipeline.stages.ffmpeg_transcode import FFmpegTranscodeStage
from pikaraoke.pipeline.stages.load_vocal import LoadVocalFromM4aStage
from pikaraoke.pipeline.stages.loudnorm_analyze import LoudnormAnalyzeStage
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage
from pikaraoke.pipeline.stages.lyrics_fetch import LyricsFetchStage
from pikaraoke.pipeline.stages.stem_separation import StemSeparationStage

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
        local .srt, or the custom lyric sheet .txt) or ``lyrics_lines`` (written
        to a temp .txt) and inject ``seed`` via :class:`SeedArtifactsStage`.
      * ``sidecar``    -> a fresh Genius selection: write the choice sidecar
        and run :class:`LyricsFetchStage` (re-fetches lyrics + resolves YTASR).
      * ``fetch``      -> placeholder for a song whose video caption may be
        downloadable: the run phase tries yt-dlp and, on success + length gate,
        becomes a seed-srt plan, else reverts to :attr:`fallback`.
      * ``transcribe`` -> no lyrics; transcription mode (writes no bundle).
      * ``skip``       -> drop the song.
      * ``prompt``     -> placeholder until the interactive pass resolves it.

    ``lrclib_record`` / ``lrclib_skip`` carry an admin's LRCLIB choice (a
    chosen record, or no match at all); see :func:`apply_lrclib_choice`.
    ``custom_text`` is a custom lyric sheet (of any kind) the admin just saved,
    which the run writes before it reads it; see :func:`apply_custom_choice`.
    """

    kind: str
    lyrics_path: Path | None = None
    lyrics_lines: list[str] | None = None
    seed: dict = field(default_factory=dict)
    genius_id: int | None = None
    label: str = ""
    fallback: "Plan | None" = None
    lrclib_record: dict | None = None
    lrclib_skip: bool = False
    custom_text: str | None = None


@dataclass
class SongJob:
    """One song's regen. ``replaces_custom`` marks an admin's repair to another
    source, the one job that removes the song's custom lyric sheet."""

    song_path: Path
    bundle: dict | None
    stale_reason: str
    plan: Plan | None = None
    replaces_custom: bool = False


# The bundle's ``lyrics.origin`` for each kind. ``"srt"`` already means a YouTube
# caption, and History reads origins from old bundles where no file says the kind.
CUSTOM_ORIGIN = "custom"
MOVIE_ORIGIN = "movie_srt"
LRC_ORIGIN = "lrclib_srt"


def is_genius_reuse(plan: Plan | None) -> bool:
    """Whether ``plan`` replays the Genius lyrics a bundle already holds."""
    return plan is not None and plan.kind == "seed" and plan.seed.get("lyrics_origin") == "genius"


def is_custom_plan(plan: Plan | None) -> bool:
    """Whether ``plan`` times the song from its typed custom lyric sheet."""
    return (
        plan is not None and plan.kind == "seed" and plan.seed.get("lyrics_origin") == CUSTOM_ORIGIN
    )


# ---------------------------------------------------------------------------
# Scan + select
# ---------------------------------------------------------------------------


def bundle_path(folder: Path, stem: str) -> Path:
    """Where the song ``stem`` in ``folder`` keeps its alignment bundle."""
    return folder / "alignment_debug" / f"{stem}.json"


def read_bundle(folder: Path, stem: str) -> dict | None:
    path = bundle_path(folder, stem)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Ignoring unreadable bundle %s: %s", path, e)
        return None


def list_videos(folder: Path) -> list[Path]:
    """Every video file directly in ``folder``, sorted."""
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS)


def scan_folder(folder: Path, include_all: bool, songs: list[Path] | None = None) -> list[SongJob]:
    """Return jobs for the videos in scope.

    Default: bundle missing or ``schema_version < SCHEMA_VERSION``.
    ``include_all``: every video, regardless of bundle state.
    ``songs``: only these videos (from :func:`select_songs`), regardless of
    bundle state or ``include_all`` -- each job gets ``stale_reason="selected"``.
    """
    if songs is not None:
        return [
            SongJob(song_path=p, bundle=read_bundle(folder, p.stem), stale_reason="selected")
            for p in songs
        ]
    jobs: list[SongJob] = []
    for path in list_videos(folder):
        bundle = read_bundle(folder, path.stem)
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
# Resolve a lyric plan (no prompting, no network)
# ---------------------------------------------------------------------------


def find_local_srt(song: Path) -> Path | None:
    """Return ``subtitles/<stem>.en.srt`` then ``<stem>.srt``, or None."""
    subs = song.parent / "subtitles"
    for name in (f"{song.stem}.en.srt", f"{song.stem}.srt"):
        candidate = subs / name
        if candidate.is_file() and not is_generated(candidate):
            return candidate
    return None


# The admin's own lyrics for a song, kept in the library's ``lyrics/`` folder in one
# of three kinds: the typed lines (``.custom.txt``), movie subtitles pasted as an
# SRT with clip times (``.custom.srt``), or an LRCLIB match's lines fitted to the
# clip as an SRT (``.lrclib.srt``); the last two are timed on the cue route. The
# file is the one record that the song uses them: a bundle's provenance is ignored
# by a reset and a transcribe run deletes the bundle. A song keeps one sheet,
# whichever kind.
CUSTOM_TEXT_SUFFIX = ".custom.txt"
CUSTOM_SRT_SUFFIX = ".custom.srt"
LRC_SRT_SUFFIX = ".lrclib.srt"
CUSTOM_SHEET_SUFFIXES = (CUSTOM_TEXT_SUFFIX, CUSTOM_SRT_SUFFIX, LRC_SRT_SUFFIX)


def custom_sheet_file(song: Path, suffix: str) -> Path:
    """Where ``song``'s custom sheet of the kind ``suffix`` lives, whether or not it exists."""
    return song.parent / "lyrics" / f"{song.stem}{suffix}"


def _sheet_files(song: Path) -> list[Path]:
    return [custom_sheet_file(song, suffix) for suffix in CUSTOM_SHEET_SUFFIXES]


def custom_sheet_path(song: Path) -> Path | None:
    """The custom lyric sheet ``song`` has on disk, whichever kind, or None."""
    return next((sheet for sheet in _sheet_files(song) if sheet.is_file()), None)


# The kind each sheet suffix names: the status field, and the repair page's source.
_SHEET_KINDS = {CUSTOM_TEXT_SUFFIX: "custom", CUSTOM_SRT_SUFFIX: "movie", LRC_SRT_SUFFIX: "lrclib"}


def sheet_kind(sheet: Path | None) -> str | None:
    """The kind of the custom sheet at ``sheet`` (``"custom"``, ``"movie"`` or ``"lrclib"``), or None.

    The only place a sheet's suffix is tested; ``None`` in, for a song with no sheet, gives None.
    """
    if sheet is None:
        return None
    return next(
        (kind for suffix, kind in _SHEET_KINDS.items() if sheet.name.endswith(suffix)), None
    )


def _sheet_plan(song: Path, suffix: str, origin: str, label: str, text: str | None) -> Plan:
    """The plan that times ``song`` from its custom sheet of the kind ``suffix``.

    ``text`` is a sheet the admin just saved, for the run to write first.
    """
    return Plan(
        kind="seed",
        lyrics_path=custom_sheet_file(song, suffix),
        seed={"lyrics_origin": origin},
        custom_text=text,
        label=label,
    )


def custom_sheet_plan(song: Path, text: str | None = None) -> Plan:
    """The plan that times ``song`` from its typed custom sheet."""
    return _sheet_plan(song, CUSTOM_TEXT_SUFFIX, CUSTOM_ORIGIN, "custom sheet", text)


def movie_sheet_plan(song: Path, text: str | None = None) -> Plan:
    """The plan that times ``song`` from its movie-subtitles sheet, on the cue route."""
    return _sheet_plan(song, CUSTOM_SRT_SUFFIX, MOVIE_ORIGIN, "movie subtitles", text)


def lrc_sheet_plan(song: Path, text: str | None = None) -> Plan:
    """The plan that times ``song`` from its LRCLIB timing sheet, on the cue route."""
    return _sheet_plan(song, LRC_SRT_SUFFIX, LRC_ORIGIN, "LRCLIB timing", text)


_SHEET_PLANS = {"custom": custom_sheet_plan, "movie": movie_sheet_plan, "lrclib": lrc_sheet_plan}
# The kinds of custom sheet, which are also the repair sources that save one.
SHEET_KINDS = tuple(_SHEET_PLANS)


def custom_plan(job: SongJob) -> Plan | None:
    """The plan that replays the song's custom lyric sheet, or None when it has none.

    Every plan chosen without a repair starts here, a reset included: the sheet
    wins until a repair to another source removes it.
    """
    kind = sheet_kind(custom_sheet_path(job.song_path))
    return _SHEET_PLANS[kind](job.song_path) if kind else None


def resolve_plan(job: SongJob, *, reset: bool) -> Plan:
    """Plan one song's lyric source (pure, no I/O writes, no network).

    A custom lyric sheet wins over everything, ``reset`` included. Otherwise, in
    the default mode this trusts the previous bundle: a song with recorded
    provenance is reused (see :func:`reuse_plan`), and only a song without a
    reusable source falls through to download-or-prompt. ``reset`` discards the
    recorded provenance entirely and re-resolves every song from scratch.

    The download-or-prompt fallback is deferred to the run phase: a song with a
    YouTube id becomes a ``fetch`` placeholder (resolved by :func:`fetch_caption`),
    otherwise a Genius ``prompt``.
    """
    plan = custom_plan(job) if reset else reuse_plan(job)
    return plan or fetch_or_prompt_plan(job.song_path)


def reuse_plan(job: SongJob) -> Plan | None:
    """Reuse plan from the previous bundle, or None when nothing is reusable.

    A song is reused only when its provenance is recorded — the regenerated
    schema needs that metadata anyway, so reusing bare lines with unknown
    provenance is pointless:

      * a custom lyric sheet on disk -> reuse it, whatever the bundle says.
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
    custom = custom_plan(job)
    if custom is not None:
        return custom

    bundle = job.bundle
    song = job.song_path
    if bundle is None:
        return None

    lyrics = bundle.get("lyrics") or {}
    origin = lyrics.get("origin")

    if origin == "srt":
        srt = find_local_srt(song)
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


def fetch_or_prompt_plan(song: Path) -> Plan:
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


def default_query(song: Path) -> str:
    """Strip the YouTube ID suffix and tidy the title for a search query."""
    suffix = youtube_id_suffix(str(song))
    title = song.stem[: -len(suffix)] if suffix else song.stem
    cleaned = clean_search_query(title)
    return cleaned or title


# ---------------------------------------------------------------------------
# Caption length gate
# ---------------------------------------------------------------------------


def _srt_word_count(srt_path: Path) -> int | None:
    """Cleaned-cue word count for an SRT, or None if it can't be read or parsed.

    Counts the same cleaned cue text the matcher consumes, so a dialog-only
    caption (few sung words) scores low. A caption that isn't UTF-8
    (``UnicodeDecodeError``) or holds an out-of-range timestamp
    (``OverflowError``) can't be measured, and the gate passes what it can't measure.
    """
    try:
        raw = srt_path.read_text(encoding="utf-8")
        texts, _ = cue_spans_from_srt(raw)
    except (OSError, ValueError, OverflowError, srt.SRTParseError) as e:
        logger.warning("Cannot read SRT %s: %s", srt_path, e)
        return None
    return sum(len(t.split()) for t in texts)


def media_duration(job: SongJob) -> float | None:
    """Song duration in seconds: the bundle value, else an ffprobe fallback."""
    recorded = (job.bundle or {}).get("media_duration_s")
    if isinstance(recorded, (int, float)) and recorded > 0:
        return float(recorded)
    return probe_duration(job.song_path)


def caption_wpm(srt_path: Path, job: SongJob) -> float | None:
    """Words per minute of song for ``srt_path``, or None if not measurable."""
    return _wpm(srt_path, lambda: media_duration(job), job.song_path.name)


def _wpm(srt_path: Path, duration: Callable[[], float | None], name: str) -> float | None:
    """:func:`caption_wpm` against any length; ``duration`` is read only for a readable caption."""
    words = _srt_word_count(srt_path)
    if words is None:
        return None
    seconds = duration()
    if not seconds:
        logger.warning("No duration for %s; skipping length check", name)
        return None
    return words / (seconds / 60.0)


def _caption_passes(wpm: float | None) -> bool:
    """The length gate. A caption whose length can't be measured passes."""
    return wpm is None or wpm >= MIN_CAPTION_WPM


# ---------------------------------------------------------------------------
# A video's manual English caption: gate it, fetch it, or just check it
# ---------------------------------------------------------------------------


def adopt_caption(job: SongJob, srt_path: Path) -> None:
    """Gate an on-disk caption and set the job's plan from it.

    Applies the words-per-minute gate (``MIN_CAPTION_WPM``): too sparse to be
    lyrics discards ``srt_path`` and reverts the job to its fallback (a Genius
    prompt). Dense enough promotes it to the playback-matched
    ``subtitles/<stem>.srt`` -- the same normalization
    ``download_manager._move_downloaded_subtitle`` applies in the live app,
    skipped when ``srt_path`` already is that file -- and sets a seed-srt plan.
    """
    song = job.song_path
    fallback = job.plan.fallback or Plan(kind="prompt", label="fetch failed -> genius")
    wpm = caption_wpm(srt_path, job)
    if not _caption_passes(wpm):
        logger.info("Fetched caption for %s too sparse (%.0f wpm); discarding", song.name, wpm)
        srt_path.unlink(missing_ok=True)
        job.plan = fallback
        return
    # Playback (_find_subtitles) and the pipeline's _should_write_srt both key
    # on subtitles/<stem>.srt.
    playback_srt = srt_path.with_name(f"{song.stem}.srt")
    if srt_path != playback_srt:
        os.replace(srt_path, playback_srt)
    clear_generated_marker(playback_srt)
    job.plan = Plan(
        kind="seed",
        lyrics_path=playback_srt,
        seed={"lyrics_origin": "srt"},
        label="fetched srt (from video)",
    )


def fetch_caption(job: SongJob) -> None:
    """Resolve a ``fetch`` job by downloading the video's manual English caption.

    Downloads into ``subtitles/<stem>.en.srt`` (one network call) and hands it
    to :func:`adopt_caption` for the length gate and promotion; with no
    downloadable caption the job reverts to its plan's fallback. Runs on a real
    pass only, after the backup, so a discarded download never clobbers a
    backed-up caption.
    """
    song = job.song_path
    try:
        result = download_manual_en_subs(
            watch_url(extract_youtube_id(str(song))), str(song.parent / "subtitles"), song.stem
        )
    except CaptionDownloadFailed as e:
        logger.warning("Caption download failed for %s: %s", song.name, e)
        result = None
    if result is None:
        logger.info("No downloadable caption for %s; will prompt", song.name)
        job.plan = job.plan.fallback or Plan(kind="prompt", label="fetch failed -> genius")
        return
    adopt_caption(job, Path(result))


def watch_url(video_id: object) -> str:
    """A video's link in the form ``queue_download`` stores, so waiting downloads compare equal."""
    return f"https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class CaptionCheck:
    found: bool  # YouTube has a manual English caption
    wpm: float | None  # None when the caption's length can't be measured
    passed: bool  # would the length gate keep it
    failed: bool = False  # the check couldn't run, so found says nothing


def check_caption(job: SongJob) -> CaptionCheck:
    """Download the manual English caption into a throwaway folder and measure it.

    Nothing in the library is written, so a preview can run before the backup.
    The song must have a YouTube id.
    """
    song = job.song_path
    video_id = extract_youtube_id(str(song))
    return _check_caption(video_id, song.stem, lambda: media_duration(job), song.name)


def check_video_caption(video_id: str, duration_s: float | None) -> CaptionCheck:
    """:func:`check_caption` for a video not downloaded yet (the search page's picker).

    ``duration_s`` is YouTube's length for the video, standing in for the file's.
    """
    return _check_caption(video_id, video_id, lambda: duration_s, video_id)


def _check_caption(
    video_id: str | None, stem: str, duration: Callable[[], float | None], name: str
) -> CaptionCheck:
    scratch = Path(tempfile.mkdtemp(prefix="caption_check_", dir=get_temp_directory()))
    try:
        try:
            result = download_manual_en_subs(watch_url(video_id), str(scratch), stem)
        except CaptionDownloadFailed as e:
            logger.warning("Caption check of %s couldn't run: %s", name, e)
            return CaptionCheck(found=False, wpm=None, passed=False, failed=True)
        if result is None:
            return CaptionCheck(found=False, wpm=None, passed=False)
        wpm = _wpm(Path(result), duration, name)
        return CaptionCheck(found=True, wpm=wpm, passed=_caption_passes(wpm))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def gate_on_disk_caption(job: SongJob) -> bool:
    """Gate the caption a download already saved (no network).

    True when the song now has a seed-srt plan. A caption too sparse to be
    lyrics is deleted, as :func:`adopt_caption` does; with no caption on disk
    the plan is left alone.
    """
    srt_path = find_local_srt(job.song_path)
    if srt_path is None:
        return False
    job.plan = fetch_or_prompt_plan(job.song_path)
    adopt_caption(job, srt_path)
    return job.plan.kind == "seed"


# ---------------------------------------------------------------------------
# LRCLIB variants for genius reuse plans (E1 gated fill)
# ---------------------------------------------------------------------------


def backfill_lrc(job: SongJob, config: PipelineConfig) -> None:
    """Resolve ``lyrics/<stem>.lrc`` for one genius reuse plan; never raises.

    Reuse plans (``kind == "seed"``, ``lyrics_origin == "genius"``) replay
    via :class:`SeedArtifactsStage` and bypass ``LyricsFetchStage``
    entirely, so without this leg an existing song never gains a ``.lrc``.
    Sidecar plans (a fresh Genius selection) get the resolve when they
    run — from ``LyricsFetchStage`` itself, or from :func:`prepare_lyrics`
    for a song with no YouTube id (which bypasses the stage) — one call
    site per plan kind; ``ensure_lrc``'s on-disk check would make a
    duplicate call harmless, but there is no need to make one.

    A failure is logged and swallowed: a missing variant must not stop the
    song or the batch it belongs to.
    """
    if not config.lrclib_fill:
        return
    try:
        genius = job.plan.seed["genius"]
        lrclib.ensure_lrc(
            job.song_path,
            genius["title"],
            genius["artist"],
            job.plan.lyrics_lines,
            media_duration(job),
        )
    except Exception:
        logger.exception("LRCLIB backfill failed for %s; continuing", job.song_path.name)


# ---------------------------------------------------------------------------
# Per-song pipeline prep
# ---------------------------------------------------------------------------


def _stems_present(song: Path) -> bool:
    vocal = song.parent / "vocal" / f"{song.stem}---vocal.m4a"
    nonvocal = song.parent / "nonvocal" / f"{song.stem}---nonvocal.m4a"
    return vocal.is_file() and nonvocal.is_file()


def _dereverb_cache(song: Path) -> Path:
    return song.parent / "dereverb" / f"{song.stem}---dereverb.m4a"


def build_stages(song: Path, lyric_stage, whisper, config: PipelineConfig, stem_worker):
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


def apply_lrclib_choice(job: SongJob) -> None:
    """Make ``lyrics/<stem>.lrc`` say which LRCLIB match the run should use.

    ``ensure_lrc`` reuses any ``.lrc`` on disk and a reset keeps it, so the
    file is the choice:

      * ``lrclib_skip`` -> a skip marker (no fetch; the fill finds no cues);
      * ``lrclib_record`` -> that record;
      * a ``sidecar`` plan for a different Genius song than the bundle
        recorded -> no file, so the automatic fetch runs for the new song
        instead of reusing the old song's match;
      * anything else leaves the file alone.
    """
    plan = job.plan
    lrc = lrclib.lrc_path(job.song_path)
    if plan.lrclib_skip:
        lrclib.write_skip_marker(lrc)
    elif plan.lrclib_record is not None:
        lrclib.write_lrc(lrc, plan.lrclib_record)
    elif plan.kind == "sidecar":
        recorded = (((job.bundle or {}).get("lyrics") or {}).get("genius") or {}).get("id")
        if plan.genius_id != recorded:
            lrc.unlink(missing_ok=True)


def apply_custom_choice(job: SongJob) -> None:
    """Make the song's custom sheet match the job: written, kept or removed.

    A plan that carries ``custom_text`` writes the admin's sheet of its kind and
    removes the other kinds, and a repair to another source
    (:attr:`SongJob.replaces_custom`) removes them all; the backup taken before the
    run still holds them. Every other job keeps what is there, so a plan that
    missed the sheet costs one run, never the admin's lyrics.
    """
    plan = job.plan
    if plan.custom_text is not None:
        lrclib.write_text_atomic(plan.lyrics_path, plan.custom_text)
        kept = plan.lyrics_path.name
    elif job.replaces_custom:
        kept = None
    else:
        return
    for sheet in _sheet_files(job.song_path):
        if sheet.name != kept:
            sheet.unlink(missing_ok=True)


def snapshot_lyric_files(song: Path) -> dict[Path, bytes | None]:
    """The bytes of the files a regen rewrites or deletes: the ``.lrc`` and both
    kinds of custom sheet (None: no such file). Taken before anything is changed."""
    return {
        path: lrclib.snapshot_file(path) for path in (lrclib.lrc_path(song), *_sheet_files(song))
    }


def put_back_lyric_files(snapshot: dict[Path, bytes | None]) -> None:
    """Restore the files of :func:`snapshot_lyric_files` after a regen that didn't finish.

    The choices rewrite or delete them before the run (D3) and the run can write
    a new ``.lrc``, while a failed run leaves the old bundle in place: the
    admin's earlier skip, pick or sheet would be gone, or the new song's match
    would sit next to the old song's bundle. Never raises, so it can't hide the
    job's own error.
    """
    for path, data in snapshot.items():
        try:
            lrclib.restore_file(path, data)
        except OSError as e:
            logger.warning("Could not put back %s: %s", path.name, e)


def _ytasr_seed(song: Path) -> dict:
    """The seed artifacts a Genius run's lyrics stage sets from the on-disk caption."""
    record, duration = ytasr.resolve_on_disk(song)
    seed: dict = {}
    if record is not None:
        seed["ytasr"] = record
    if duration is not None:
        seed["media_duration_s"] = duration
    return seed


def prepare_lyrics(job: SongJob, genius: GeniusClient, lyrics_dir: Path, config: PipelineConfig):
    """Resolve a job's plan to ``(lyrics_path, lyric_stage)`` for the run.

    Applies the LRCLIB and custom-sheet choices first, then writes the temp .txt
    for reused Genius lyrics and the choice sidecar for a fresh Genius
    selection. A Genius pick on a song without a YouTube id can't use the
    sidecar, so it degrades to explicit lyrics with no YTASR 3rd source (logged).
    A custom sheet is read in place and takes the on-disk YouTube auto-caption as
    a 3rd source, as a Genius song does, resolved afresh on every run.
    """
    apply_lrclib_choice(job)
    apply_custom_choice(job)
    plan = job.plan
    song = job.song_path

    if plan.kind == "seed":
        seed = plan.seed
        if plan.lyrics_lines is not None:
            lyrics_path = lyrics_dir / f"{song.stem}.txt"
            # Blank-line separated: these lines are already parsed, and a
            # blank line stops the pipeline's wrap-join from reading one
            # stored line into the next (see `_join_wrapped_lines`).
            lyrics_path.write_text("\n\n".join(plan.lyrics_lines), encoding="utf-8")
        else:
            lyrics_path = plan.lyrics_path
        if is_custom_plan(plan):
            # The cue route a movie sheet takes never reads the third source.
            seed = {**seed, **_ytasr_seed(song)}
        return lyrics_path, SeedArtifactsStage(seed)

    if plan.kind == "sidecar":
        yt_id = extract_youtube_id(str(song))
        if yt_id:
            write_choice(yt_id, {"genius_id": plan.genius_id})
            return None, LyricsFetchStage(genius, config)
        # No YouTube id — sidecar can't be keyed. Fetch the text directly.
        try:
            gsong = genius.fetch_song(plan.genius_id)
        except GeniusUnavailable as e:
            logger.warning("Genius fetch failed (%s); transcribing instead", e)
            return None, None
        lyrics_path = lyrics_dir / f"{song.stem}.txt"
        lyrics_path.write_text(gsong.text, encoding="utf-8")
        logger.warning("No YouTube id for %s; YTASR 3rd source unavailable", song.name)
        if config.lrclib_fill:
            # This path bypasses LyricsFetchStage (and its LRCLIB leg), so
            # resolve the variant here, where the Genius identity first exists.
            try:
                sheet_lines = [item["text"] for item in parse_lyric_lines(gsong.text)]
                lrclib.ensure_lrc(song, gsong.title, gsong.artist, sheet_lines, media_duration(job))
            except Exception:
                logger.exception("LRCLIB resolve failed for %s; continuing", song.name)
        seed = {
            "lyrics_origin": "genius",
            "genius": {"id": plan.genius_id, "title": gsong.title, "artist": gsong.artist},
        }
        return lyrics_path, SeedArtifactsStage(seed)

    # transcribe: no lyrics, no lyric stage.
    return None, None


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


# The regenerable per-song output folders: wiped up front in reset mode (the
# pipeline rebuilds them, so nothing stale lingers).
OUTPUT_DIRS = ("subtitles", "karaoke", "lyrics")

# Folders backed up before any run. Includes alignment_debug (the bundles the
# regen overwrites) in addition to OUTPUT_DIRS, but alignment_debug is never
# cleared in reset mode: a failed regen should leave the prior bundle in place
# rather than lose it outright.
BACKUP_DIRS = OUTPUT_DIRS + ("alignment_debug",)

# Every backup is a ``<UTC>`` subfolder of this one, keeping the library root tidy.
BACKUP_ROOT = "regen_backups"


def _all_stems(folder: Path) -> set[str]:
    """Every song file's stem in ``folder``, regardless of selection or staleness.

    Counts every file type the app plays (``.mp3`` and ``.zip`` too, not just
    videos), so a song regen never processes still owns its own files.
    """
    return {
        p.stem
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SongList.VALID_EXTENSIONS
    }


def _claims(stem: str, name: str) -> bool:
    """Whether ``stem`` claims the folder entry ``name``.

    ``name`` equals the stem or starts with ``stem + "."`` (catching
    ``<stem>.srt.generated``).
    """
    return name == stem or name.startswith(stem + ".")


def _owner(name: str, all_stems: set[str]) -> str | None:
    """The song stem a folder entry named ``name`` belongs to, or None.

    The longest claiming stem owns it, so ``Song.live`` owns ``Song.live.srt``
    and ``Song`` never claims a file that belongs to ``Song.live``.
    """
    claimants = [s for s in all_stems if _claims(s, name)]
    return max(claimants, key=len, default=None)


def _owned_by_any(name: str, stems: Collection[str], all_stems: set[str]) -> bool:
    """Whether ``name`` belongs to one of ``stems``.

    The same answer as ``_owner(name, all_stems) in stems``, since the owner
    always claims ``name``, but a name no selected stem claims is rejected
    without scanning every stem in the library.
    """
    return any(_claims(s, name) for s in stems) and _owner(name, all_stems) in stems


def backup_text_folders(folder: Path, stems: list[str] | None = None) -> Path | None:
    """Snapshot the regenerable output folders into ``regen_backups/<UTC>/``.

    ``stems``: copy only those songs' own files (see :func:`_owner`) from
    each folder instead of the whole folder.

    Returns the backup root, or None when nothing was copied.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = folder / BACKUP_ROOT / ts
    copied: list[str] = []

    if stems is None:
        for sub in BACKUP_DIRS:
            src = folder / sub
            if src.is_dir():
                shutil.copytree(src, backup_root / sub)
                copied.append(sub)
        return backup_root if copied else None

    all_stems = _all_stems(folder)
    for sub in BACKUP_DIRS:
        src = folder / sub
        if not src.is_dir():
            continue
        entries = [e for e in src.iterdir() if _owned_by_any(e.name, stems, all_stems)]
        if not entries:
            continue
        dest = backup_root / sub
        dest.mkdir(parents=True, exist_ok=True)
        for e in entries:
            if e.is_dir():
                shutil.copytree(e, dest / e.name)
            else:
                shutil.copy2(e, dest / e.name)
        copied.append(sub)
    return backup_root if copied else None


# Non-regenerable inputs a reset keeps inside the folders it otherwise wipes --
# fetched once and reused, not outputs the pipeline rebuilds:
#
# - ``subtitles/<stem>.en.asr.json3`` YouTube-ASR captions (fetched by the
#   download manager on first add). Wiping them would silently drop the joint
#   matcher's third source from every genius song on the next run.
# - ``lyrics/<stem>.lrc`` LRCLIB variants (fetched by :func:`backfill_lrc` /
#   ``LyricsFetchStage``, per E1's gated fill). Wiping them would force a
#   re-fetch of every genius song's variant on the next run for no benefit --
#   ``ensure_lrc`` already reuses an on-disk file unconditionally.
# - ``lyrics/<stem>.custom.txt`` / ``.custom.srt`` / ``.lrclib.srt`` an admin's own
#   lyric sheet, typed, pasted from a movie or fitted from an LRCLIB match. It is
#   hand-made, so a reset must not lose it; only a repair to another source
#   removes it.
KEEP_ON_RESET = {"subtitles": ASR_JSON3_SUFFIX, "lyrics": (".lrc", *CUSTOM_SHEET_SUFFIXES)}


def clear_output_folders(folder: Path, stems: list[str] | None = None) -> None:
    """Delete the regenerable output folders (reset mode, after the backup).

    The pipeline rebuilds subtitles/karaoke/lyrics for every song reset
    reprocesses, so wiping them first guarantees no stale file (e.g. an old
    generated SRT) survives. Stems and bundles live elsewhere and are untouched.
    :data:`KEEP_ON_RESET` names what survives inside ``subtitles/`` and
    ``lyrics/``. A file it can't remove raises ``OSError``.

    ``stems``: scope the wipe to those songs' own files (see :func:`_owner`)
    instead of clearing whole folders -- the folders themselves are never
    removed and every other song's files are untouched.
    """
    all_stems = _all_stems(folder) if stems is not None else set()

    def selected(name: str) -> bool:
        return stems is None or _owned_by_any(name, stems, all_stems)

    for sub in OUTPUT_DIRS:
        keep_suffix = KEEP_ON_RESET.get(sub)
        if stems is None and keep_suffix is None:
            _remove(folder / sub)
        else:
            _clear_dir(folder / sub, keep_suffix, selected)


def _clear_dir(
    dir_path: Path, keep_suffix: str | tuple[str, ...] | None, selected: Callable[[str], bool]
) -> None:
    """Remove the ``selected`` entries of ``dir_path`` (never the folder itself).

    Files ending in ``keep_suffix`` (or in any one of a tuple of them) are kept.
    """
    if not dir_path.is_dir():
        return
    for entry in list(dir_path.iterdir()):
        if keep_suffix and entry.is_file() and entry.name.endswith(keep_suffix):
            continue
        if selected(entry.name):
            _remove(entry)


def _remove(path: Path) -> None:
    """Delete a file or a directory tree.

    A file that can't be removed raises, so a reset never goes on past a stale
    caption. A tree that can't be fully removed is warned about.
    """
    if not path.is_dir():
        path.unlink(missing_ok=True)
        return
    try:
        shutil.rmtree(path)
    except OSError as e:
        logger.warning("Could not fully remove %s: %s", path, e)


# ---------------------------------------------------------------------------
# A regen job for the app's processing queue
# ---------------------------------------------------------------------------


@dataclass
class RegenJob:
    """One song's regeneration, queued behind downloads in the processing queue.

    ``reset`` wipes the song's regenerable outputs first; ``label`` is the row's
    kind word (Update, Reprocess, Reset, Repair, Regenerate).
    """

    song: SongJob
    reset: bool
    label: str


class RegenError(Exception):
    """A regen job can't start; the message is for the admin."""


def prepare_regen_job(
    regen: RegenJob, genius: GeniusClient, config: PipelineConfig, lyrics_dir: Path
) -> tuple[Path | None, BaseStage | None]:
    """The per-song file work before a regen run, in the order the CLI does it.

    Returns ``(lyrics_path, lyric_stage)`` for the run, as :func:`prepare_lyrics`
    does. Raises :class:`RegenError` when the job can't start.

    Works on a copy of the song job and never changes the queued one: the
    caption fetch turns a ``fetch`` plan into "use the .srt just fetched", and
    a retry of the queued job must start from ``fetch`` again, because its
    reset wipe deletes that .srt first.

    A Genius pick is fetched first, before anything is changed: when Genius
    doesn't answer, the pipeline's fetch would fall back to a caption or
    transcribe, and the run would replace the song's lyrics with that.
    """
    job = replace(regen.song)
    song = job.song_path

    if job.plan.kind == "sidecar":
        try:
            genius.fetch_song(job.plan.genius_id)
        except GeniusUnavailable as e:
            logger.warning("Genius pick %s for %s refused: %s", job.plan.genius_id, song.name, e)
            raise RegenError(
                "Genius didn't return this song's lyrics, so nothing was changed. "
                "Retry when Genius answers."
            ) from e

    if regen.reset:
        try:
            clear_output_folders(song.parent, stems=[song.stem])
        except OSError as e:
            raise RegenError(
                f"A file of this song is in use: {e}. Close the player and retry."
            ) from e

    if job.plan.kind == "fetch":
        fetch_caption(job)
        if job.plan.kind != "seed":
            raise RegenError(
                "No usable YouTube caption: none could be downloaded, or it is too "
                "short to be lyrics. Try again later, or pick lyrics with Repair "
                "lyrics on Song Info."
            )

    if is_genius_reuse(job.plan):
        backfill_lrc(job, config)

    return prepare_lyrics(job, genius, lyrics_dir, config)


def finish_regen_job(song: Path, lyric_method: str | None) -> None:
    """After a successful run: one that transcribed removes the song's old bundle.

    ``lyric_method`` is the run's ``ctx.artifacts["lyric_method"]``.
    ``LyricAlignStage`` sets it to ``transcribe`` exactly when it had no lyrics,
    which is exactly when it writes no bundle. A transcribe *plan* is not the
    test: a Genius pick also ends up transcribing when Genius is unavailable.
    The old bundle would otherwise stay: Song Info would show the old lyrics,
    and the next reuse run would bring them back. The backup holds the removed
    bundle.
    """
    if lyric_method == "transcribe":
        bundle_path(song.parent, song.stem).unlink(missing_ok=True)
