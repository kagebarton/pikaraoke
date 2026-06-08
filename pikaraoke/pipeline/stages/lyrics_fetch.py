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

from pikaraoke.lib.genius import (
    GeniusClient,
    GeniusUnavailable,
    delete_choice,
    read_choice,
)
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.pipeline.context import StageContext
from pikaraoke.pipeline.stages.base import BaseStage

logger = logging.getLogger(__name__)


class LyricsFetchStage(BaseStage):
    """Resolve the lyrics source for the job and populate ctx.artifacts."""

    name = "lyrics_fetch"

    def __init__(self, genius: GeniusClient) -> None:
        """``genius`` is always a :class:`GeniusClient` instance (Design Decision 2).

        When the token is empty, its methods degrade gracefully:
        ``search()`` returns ``[]``, ``fetch_lyrics()`` raises
        :class:`GeniusUnavailable`.
        """
        self._genius = genius

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
                text = self._genius.fetch_lyrics(int(choice["genius_id"]))
                lyrics_path = ctx.tmp_dir / "lyrics.txt"
                lyrics_path.write_text(text, encoding="utf-8")
                ctx.artifacts["lyrics_path"] = lyrics_path
                ctx.artifacts["lyrics_origin"] = "genius"
                delete_choice(yt_id)
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
            return

        # Branch b2: explicit YouTube SRT selection
        if choice and choice.get("mode") == "srt":
            srt_path = self._find_srt(ctx.song_path)
            ctx.artifacts["lyrics_path"] = srt_path
            ctx.artifacts["lyrics_origin"] = "srt" if srt_path else "none"
            delete_choice(yt_id)
            return

        # Branch c: SRT fallback (current behaviour)
        srt_path = self._find_srt(ctx.song_path)
        ctx.artifacts["lyrics_path"] = srt_path
        ctx.artifacts["lyrics_origin"] = "srt" if srt_path else "none"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

        Logic moved verbatim from
        ``processing_manager._resolve_lyrics_path``.
        """
        subs_dir = song_path.parent / "subtitles"
        for name in (f"{song_path.stem}.en.srt", f"{song_path.stem}.srt"):
            candidate = subs_dir / name
            if candidate.is_file():
                logger.info("Found lyrics for alignment: %s", candidate.name)
                return candidate
        logger.debug("Lyrics candidate not found: %s", candidate)
        logger.info(
            "No subtitle found for alignment — will transcribe: %s",
            song_path.name,
        )
        return None
