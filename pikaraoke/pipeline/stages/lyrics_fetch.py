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

from pikaraoke.lib import lrclib
from pikaraoke.lib.ffmpeg import probe_duration
from pikaraoke.lib.genius import (
    GeniusClient,
    GeniusUnavailable,
    delete_choice,
    read_choice,
)
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
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
                song = self._genius.fetch_song(int(choice["genius_id"]))
                lyrics_path = ctx.tmp_dir / "lyrics.txt"
                lyrics_path.write_text(song.text, encoding="utf-8")
                ctx.artifacts["lyrics_path"] = lyrics_path
                ctx.artifacts["lyrics_origin"] = "genius"
                # Persist the Genius identity for the debug bundle so a later
                # regen can re-fetch lyrics / re-query LRCLIB deterministically
                # instead of re-prompting for an artist-title search.
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
                self._fetch_lrclib_prior(ctx, song.title, song.artist, song.text)
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

    def _fetch_lrclib_prior(
        self, ctx: StageContext, title: str, artist: str, lyrics_text: str
    ) -> None:
        """Fetch + persist the best LRCLIB synced variant as the timing prior.

        Genius-origin only (called from Branch a), gated by
        ``config.joint_lrclib_prior``. Persists ``<song>/lyrics/<stem>.lrc`` and
        stashes ``ctx.artifacts["lrclib"]`` (the LRC file path + the chosen
        record + query) for the align stage and the debug bundle. An existing
        ``.lrc`` is reused without re-querying (offline-safe reprocess). Never
        raises: any failure or absent candidate just means no prior — the song
        processes exactly as today.
        """
        if not ctx.config.joint_lrclib_prior:
            return
        try:
            rel = f"lyrics/{ctx.song_path.stem}.lrc"
            lrc_path = ctx.song_path.parent / rel

            media_dur = probe_duration(ctx.song_path)
            if media_dur is not None:
                ctx.artifacts["media_duration_s"] = media_dur

            if lrc_path.is_file():
                _synced, record = lrclib.read_lrc(lrc_path)
                ctx.artifacts["lrclib"] = {"lrc_file": rel, "record": record, "query": None}
                logger.info("Timing prior: reusing cached LRCLIB — %s", _lrc_label(record))
                return

            track, artist_q = lrclib.clean_key(title, artist)
            records = lrclib.search(track, artist_q)
            if not records:
                logger.info(
                    "Timing prior: no LRCLIB match for %r by %r — aligning without a prior",
                    track,
                    artist_q,
                )
                return
            sheet = [item["text"] for item in parse_lyric_lines(lyrics_text)]
            chosen = lrclib.select_candidate(records, sheet, media_dur)
            if chosen is None:
                logger.info(
                    "Timing prior: %d LRCLIB record(s) for %r by %r but none matched the "
                    "lyric sheet — aligning without a prior",
                    len(records),
                    track,
                    artist_q,
                )
                return
            lrclib.write_lrc(lrc_path, chosen)
            ctx.artifacts["lrclib"] = {
                "lrc_file": rel,
                "record": lrclib.record_meta(chosen),
                "query": {"track_name": track, "artist_name": artist_q},
            }
            logger.info("Timing prior: LRCLIB — %s", _lrc_label(chosen))
        except Exception:
            logger.exception("Timing prior: LRCLIB fetch failed — aligning without a prior")

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
            if candidate.is_file():
                return candidate
        return None


def _lrc_label(record: dict) -> str:
    """Human-readable identity for an LRCLIB record: ``'Title' by 'Artist' (lrclib #id)``."""
    return (
        f"{record.get('trackName')!r} by {record.get('artistName')!r} "
        f"(lrclib #{record.get('id')})"
    )
