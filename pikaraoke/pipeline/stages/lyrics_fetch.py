"""Lyrics fetch stage: resolve the lyrics source for the job.

Runs first after ``PreparePtyStage`` so Genius failures surface before
expensive audio extraction.  Sets:

- ``ctx.artifacts["lyrics_path"]``: ``Path | None``
- ``ctx.artifacts["lyrics_origin"]``: ``"genius"`` | ``"srt"`` | ``"none"`` | ``"override"``

Three branches:

a) Explicit Genius selection → fetch from Genius → write ``lyrics.txt``
   to ``ctx.tmp_dir``, set ``lyrics_path``, delete the choice file.
b) Explicit raw selection → ``lyrics_path = None`` (force transcribe).
c) No choice file → look for existing SRT, or fall through to
   transcription.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pikaraoke.lib import lrclib, youtube_dl, ytasr
from pikaraoke.lib.ffmpeg import probe_duration
from pikaraoke.lib.genius import (
    GeniusClient,
    GeniusSong,
    GeniusUnavailable,
    delete_choice,
    read_choice,
)
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.lib.srt_provenance import is_generated
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import StageContext
from pikaraoke.pipeline.stages.base import BaseStage

logger = logging.getLogger(__name__)


class LyricsFetchStage(BaseStage):
    """Resolve the lyrics source for the job and populate ctx.artifacts."""

    name = "lyrics_fetch"

    def __init__(self, genius: GeniusClient, config: PipelineConfig) -> None:
        """``genius`` is always a :class:`GeniusClient` instance (Design Decision 2).

        When the token is empty, its methods degrade gracefully:
        ``search()`` returns ``[]``, ``fetch_lyrics()`` raises
        :class:`GeniusUnavailable`.
        """
        self._genius = genius
        self._config = config

    def run(self, ctx: StageContext) -> None:
        # Test-override short-circuit: the orchestrator pre-populates
        # ctx.artifacts["lyrics_path"] when run_one_async is called with
        # an explicit lyrics_path kwarg.  Respect it.
        # IMPORTANT: the orchestrator always sets
        # ctx.artifacts["lyrics_path"] = lyrics_path (even to None) at
        # line 212, so we must check "is not None", not "in"
        # (Design Decision 5).
        if ctx.artifacts.get("lyrics_path") is not None:
            ctx.artifacts.setdefault("lyrics_origin", "override")
            return

        yt_id = self._extract_yt_id(ctx.song_path)
        choice = read_choice(yt_id) if yt_id else None

        # Branch a: explicit Genius selection
        if choice and "genius_id" in choice:
            try:
                song = self._genius.fetch_song(int(choice["genius_id"]))
                lyrics_path = ctx.tmp_dir / "lyrics.txt"
                lyrics_path.write_text(song.text, encoding="utf-8")
                ctx.artifacts["lyrics_path"] = lyrics_path
                ctx.artifacts["lyrics_origin"] = "genius"
                # Persist the Genius identity for the debug bundle so a later
                # regen can re-fetch the lyrics deterministically instead of
                # re-prompting for an artist-title search.
                ctx.artifacts["genius"] = {
                    "id": int(choice["genius_id"]),
                    "title": song.title,
                    "artist": song.artist,
                }
                delete_choice(yt_id)
                logger.info(
                    "Lyrics: Genius — %r by %r (genius #%s)",
                    song.title,
                    song.artist,
                    choice["genius_id"],
                )
                self._resolve_ytasr(ctx)
                if self._config.lrclib_fill:
                    self._resolve_lrclib(ctx, song)
                return
            except GeniusUnavailable as e:
                logger.warning("Genius fetch failed for %s: %s — falling back", yt_id, e)
                # Do NOT delete the choice file — re-runs can retry.
                # Fall through.

        # Branch b: explicit raw selection
        if choice and choice.get("mode") == "raw":
            ctx.artifacts["lyrics_path"] = None
            ctx.artifacts["lyrics_origin"] = "none"
            delete_choice(yt_id)
            logger.info("Lyrics: user chose to transcribe — skipping subtitles")
            return

        # Branch b2: explicit YouTube SRT selection
        if choice and choice.get("mode") == "srt":
            srt_path = self._find_srt(ctx.song_path)
            ctx.artifacts["lyrics_path"] = srt_path
            ctx.artifacts["lyrics_origin"] = "srt" if srt_path else "none"
            delete_choice(yt_id)
            if srt_path:
                logger.info("Lyrics: YouTube SRT, user-selected (%s)", srt_path.name)
            else:
                logger.warning("Lyrics: SRT selected but none found — will transcribe")
            return

        # Branch c: SRT fallback (current behaviour)
        srt_path = self._find_srt(ctx.song_path)
        ctx.artifacts["lyrics_path"] = srt_path
        ctx.artifacts["lyrics_origin"] = "srt" if srt_path else "none"
        if srt_path:
            logger.info("Lyrics: YouTube SRT (%s)", srt_path.name)
        else:
            logger.info("Lyrics: no subtitles found — will transcribe from audio")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_ytasr(self, ctx: StageContext) -> None:
        """Adopt an on-disk YouTube ASR caption as the joint matcher's 3rd source.

        Genius-origin only (called from Branch a). Reuses the
        ``subtitles/<stem>.en.asr.json3`` fetched at download time — the live
        pipeline never fetches (Design Decision 3; the regen tool is the
        on-demand download path). Parses + quality-gates it
        (:func:`ytasr.is_usable`) and, on success, stashes
        ``ctx.artifacts["ytasr"]`` (json3 path + word-count / wpm provenance)
        for the align stage and the debug bundle. Absent or gated-out → no
        stash → the matcher runs plain two-source. Never raises.
        """
        try:
            rel = f"subtitles/{ctx.song_path.stem}{youtube_dl.ASR_JSON3_SUFFIX}"
            asr_path = ctx.song_path.parent / rel
            if not asr_path.is_file():
                logger.info("YTASR: no on-disk ASR caption — aligning two-source")
                return

            media_dur = probe_duration(ctx.song_path)
            if media_dur is not None:
                ctx.artifacts["media_duration_s"] = media_dur

            words, word_seg_frac = ytasr.parse_json3(asr_path.read_text(encoding="utf-8"))
            if not ytasr.is_usable(words, word_seg_frac, media_dur):
                logger.info("YTASR: on-disk caption failed the quality gate — aligning two-source")
                return

            wpm = round(len(words) / (media_dur / 60.0), 1) if media_dur else None
            ctx.artifacts["ytasr"] = {"asr_file": rel, "n_words": len(words), "wpm": wpm}
            logger.info("YTASR: adopted %d words (%s wpm) as the 3rd source", len(words), wpm)
        except Exception:
            logger.exception("YTASR: resolve failed — aligning two-source")

    def _resolve_lrclib(self, ctx: StageContext, song: GeniusSong) -> None:
        """Fetch an LRCLIB synced variant for the E1 gated-fill path.

        Genius-origin only (called from Branch a). Resolves
        ``lyrics/<stem>.lrc`` via :func:`lrclib.ensure_lrc` -- reused on
        disk, else fetched, selected and persisted. No ``ctx.artifacts``
        stash: :class:`~pikaraoke.pipeline.stages.lyric_align.LyricAlignStage`
        re-reads the file from disk. Never raises; a miss just means no fill
        source for this song (the fill hook no-ops with no ``.lrc`` on disk).
        """
        try:
            sheet_lines = [item["text"] for item in parse_lyric_lines(song.text)]
            media_dur = ctx.artifacts.get("media_duration_s")
            if media_dur is None:
                media_dur = probe_duration(ctx.song_path)
            path = lrclib.ensure_lrc(ctx.song_path, song.title, song.artist, sheet_lines, media_dur)
            if path is not None:
                logger.info("LRCLIB: variant available for fill (%s)", path.name)
            else:
                logger.info("LRCLIB: no synced variant found — fill unavailable")
        except Exception:
            logger.exception("LRCLIB: resolve failed — fill unavailable")

    @staticmethod
    def _extract_yt_id(song_path: Path) -> str | None:
        """Extract the 11-char YouTube ID from the filename.

        Delegates to :func:`pikaraoke.lib.metadata_parser.extract_youtube_id`
        (Design Decision 6).  Returns ``None`` for files without a
        recognisable ID (manually-added library files).
        """
        return extract_youtube_id(str(song_path))

    @staticmethod
    def _find_srt(song_path: Path) -> Path | None:
        """Look for ``subtitles/<stem>.en.srt`` then ``subtitles/<stem>.srt``.

        Pure lookup; the calling branch logs the resolved source so the message
        can say whether the SRT was user-selected or an automatic fallback.
        """
        subs_dir = song_path.parent / "subtitles"
        for name in (f"{song_path.stem}.en.srt", f"{song_path.stem}.srt"):
            candidate = subs_dir / name
            if candidate.is_file() and not is_generated(candidate):
                return candidate
        return None
