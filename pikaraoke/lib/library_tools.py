"""The app service behind the web library tools.

Song Info and the song lists read bundles through :mod:`library_status`;
regenerate and repair queue a job in the processing manager. Song paths here
are the library's own strings (``song_manager.songs``), which is what the
processing queue, the playing check and the database key on.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from pikaraoke.lib import lrclib
from pikaraoke.lib.genius import GeniusClient, GeniusSong, GeniusUnavailable
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
from pikaraoke.lib.library_regen import (
    VIDEO_EXTS,
    CaptionCheck,
    Plan,
    RegenError,
    RegenJob,
    SongJob,
    backup_text_folders,
    check_caption,
    media_duration,
    read_bundle,
    resolve_plan,
    reuse_plan,
)
from pikaraoke.lib.library_status import (
    SONG_LISTS,
    HistoryEntry,
    SongStatus,
    length_gap_s,
    library_statuses,
    overview_counts,
    song_history,
    song_status,
)
from pikaraoke.lib.processing_manager import ProcessingManager
from pikaraoke.lib.song_manager import SongManager

logger = logging.getLogger(__name__)

BUSY_MESSAGE = "This song has a regen waiting or running."

# Fetched Genius songs kept, so a repair's preview, its LRCLIB step and the
# final queue scrape the page once.
GENIUS_CACHE_SIZE = 20

# LRCLIB records the repair page's searches listed (a search lists up to about
# 20), so a repair queues the picked one without asking LRCLIB again.
LRCLIB_CACHE_SIZE = 100


def _remember(cache: dict, key: object, value: object, size: int) -> None:
    """Store ``value`` as the newest entry of ``cache``, dropping the oldest past ``size``."""
    cache.pop(key, None)
    cache[key] = value
    while len(cache) > size:
        del cache[next(iter(cache))]


class LibraryTools:
    def __init__(
        self,
        processing_manager: ProcessingManager,
        song_manager: SongManager,
        download_path: str,
        genius_client: GeniusClient,
    ) -> None:
        self._processing = processing_manager
        self._song_manager = song_manager
        self._folder = Path(download_path)
        self._genius = genius_client
        self._genius_songs: dict[int, GeniusSong] = {}
        self._genius_lock = threading.Lock()
        self._lrclib_records: dict[int, dict] = {}
        self._lrclib_lock = threading.Lock()

    @staticmethod
    def is_video(song_path: str) -> bool:
        """Lyrics tools work on video songs only (not .mp3 or CDG .zip)."""
        return Path(song_path).suffix.lower() in VIDEO_EXTS

    def status(self, song_path: str) -> SongStatus:
        return song_status(Path(song_path))

    def history(self, song_path: str) -> list[HistoryEntry]:
        return song_history(Path(song_path))

    def overview(self) -> dict[str, int]:
        return overview_counts(library_statuses(self._folder))

    def songs_in_list(self, name: str) -> list[tuple[str, SongStatus]]:
        """The songs of one of :data:`SONG_LISTS`, by display name.

        Each song comes with its path as the library spells it, so a link built
        from it passes the routes' library check. A video on disk the library
        has not picked up yet is left out.
        """
        in_list = SONG_LISTS[name]
        spelling = {Path(path): path for path in self._song_manager.songs}
        rows = [
            (spelling[status.path], status)
            for status in library_statuses(self._folder)
            if in_list(status) and status.path in spelling
        ]
        return sorted(rows, key=lambda row: self._song_manager.filename_from_path(row[0]).lower())

    def is_busy(self, song_path: str) -> bool:
        """Whether a download or a regen of this song is running or waiting."""
        return (
            self._processing.get_active_job() == song_path
            or song_path in self._processing.pending_jobs
        )

    def attention_rows(self, tracked: set[str]) -> list[dict]:
        """Songs the database says never finished processing, for the Attention list.

        The database remembers what the tracker (memory only) forgets: a song
        left half-processed by an earlier session, or failed and then dismissed
        from the Jobs list. A song with a tracker row, or one waiting or
        running, is already shown there. Failed songs come first, each group
        by display name.
        """
        rows = []
        for db_state, state in (("failed", "failed"), ("pending", "unfinished")):
            paths = self._song_manager.get_paths_by_pipeline_state([db_state])
            titled = [
                (self._song_manager.filename_from_path(path), path)
                for path in paths
                if path in self._song_manager.songs
                and path not in tracked
                and not self.is_busy(path)
            ]
            rows += [
                {
                    "song_path": path,
                    "title": title,
                    "state": state,
                    "actions": ["retry", "song_info", "delete"],
                }
                for title, path in sorted(titled, key=lambda pair: pair[0].lower())
            ]
        return rows

    def can_regenerate(self, song_path: str) -> bool:
        """Whether :meth:`regenerate` has lyrics to work from (busy or not)."""
        return self.is_video(song_path) and self._regen_job(song_path) is not None

    def regenerate(self, song_path: str) -> None:
        """Queue a regen that reuses the song's recorded lyric pick.

        The song's files are backed up first. Raises :class:`RegenError`, with
        a message for the admin, when the song can't be queued.
        """
        if not self.is_video(song_path):
            raise RegenError("Lyrics tools work on video songs only.")
        if self.is_busy(song_path):
            raise RegenError(BUSY_MESSAGE)
        job = self._regen_job(song_path)
        if job is None:
            raise RegenError("Pick lyrics with Repair lyrics first.")
        self._queue(job, reset=False, label="Regenerate")

    def genius_song(self, genius_id: int) -> GeniusSong:
        """A Genius song's lyrics and canonical title and artist, from the last few fetched.

        Raises :class:`~pikaraoke.lib.genius.GeniusUnavailable` when Genius
        can't return it.
        """
        with self._genius_lock:
            song = self._genius_songs.get(genius_id)
        if song is not None:
            return song
        song = self._genius.fetch_song(genius_id)
        with self._genius_lock:
            _remember(self._genius_songs, genius_id, song, GENIUS_CACHE_SIZE)
        return song

    def caption_check(self, song_path: str) -> CaptionCheck:
        """Whether the video's YouTube caption could serve as the lyrics.

        One yt-dlp call; nothing in the library is written.
        """
        if not self.is_video(song_path):
            raise RegenError("Lyrics tools work on video songs only.")
        job = self._song_job(song_path)
        self._caption_plan(job)
        return check_caption(job)

    def lrclib_candidates(self, song_path: str, genius_id: int, title: str, artist: str) -> dict:
        """LRCLIB's synced matches for the admin's search terms, scored against a Genius song.

        Each candidate says how many of the Genius lyrics' lines it maps to, how
        far its length is from the video's, whether the selection rule would
        pick it (``best``) and whether it is the match on disk (``current``).
        The listed records are remembered for :meth:`repair`. Raises
        :class:`~pikaraoke.lib.genius.GeniusUnavailable` when the Genius lyrics
        can't be fetched.
        """
        sheet = [item["text"] for item in parse_lyric_lines(self.genius_song(genius_id).text)]
        video_s = media_duration(self._song_job(song_path))
        records = [r for r in lrclib.search(title, artist) if r.get("syncedLyrics")]
        with self._lrclib_lock:
            for record in records:
                # Only an integer id can come back in a repair request.
                if isinstance(record.get("id"), int):
                    _remember(self._lrclib_records, record["id"], record, LRCLIB_CACHE_SIZE)
        best = lrclib.select_candidate(records, sheet, video_s)
        current_id = self._lrc_record_id(Path(song_path))
        candidates = []
        for record in records:
            cue_texts, _ = lrclib.parse_lrc_lines(record["syncedLyrics"])
            candidates.append(
                {
                    **lrclib.record_meta(record),
                    "duration_diff_s": length_gap_s(record.get("duration"), video_s),
                    "mapped": len(lrclib.map_lines_to_cues(sheet, cue_texts)),
                    "sheet_lines": len(sheet),
                    "best": record is best,
                    "current": current_id is not None and record.get("id") == current_id,
                    "syncedLyrics": record["syncedLyrics"],
                }
            )
        return {"video_duration_s": video_s, "candidates": candidates}

    def repair(
        self,
        song_path: str,
        source: str,
        genius_id: int | None = None,
        lrclib_id: int | None = None,
        lrclib_skip: bool = False,
    ) -> None:
        """Queue a regen that replaces the song's lyric pick.

        ``source`` is ``caption`` (the video's YouTube caption), ``genius`` (the
        Genius song ``genius_id``) or ``transcribe``. For Genius the LRCLIB
        match is the record ``lrclib_id``, or none at all with ``lrclib_skip``
        (which wins over an id); with neither, the automatic rule applies. The
        song's files are backed up first, and the run wipes its old outputs.
        Raises :class:`RegenError`, with a message for the admin, when the song
        can't be queued; nothing has changed on disk by then.
        """
        if not self.is_video(song_path):
            raise RegenError("Lyrics tools work on video songs only.")
        if self.is_busy(song_path):
            raise RegenError(BUSY_MESSAGE)
        job = self._song_job(song_path)
        if source == "caption":
            job.plan = self._caption_plan(job)
        elif source == "genius":
            job.plan = self._genius_plan(genius_id, lrclib_id, lrclib_skip)
        elif source == "transcribe":
            job.plan = self._transcribe_plan()
        else:
            raise RegenError("Unknown lyric source.")
        self._queue(job, reset=True, label="Repair")

    @staticmethod
    def _caption_plan(job: SongJob) -> Plan:
        """The plan that fetches the video's caption; only a song with a YouTube ID has one."""
        plan = resolve_plan(job, reset=True)
        if plan.kind != "fetch":
            raise RegenError("This song has no YouTube ID.")
        return plan

    def _genius_plan(self, genius_id: int | None, lrclib_id: int | None, lrclib_skip: bool) -> Plan:
        if genius_id is None:
            raise RegenError("Pick a Genius song first.")
        try:
            self.genius_song(genius_id)
        except GeniusUnavailable as e:
            logger.warning("Genius pick %s refused: %s", genius_id, e)
            raise RegenError("Genius didn't return that song's lyrics. Try again.") from e
        plan = Plan(kind="sidecar", genius_id=genius_id, label="genius pick")
        if lrclib_skip:
            plan.lrclib_skip = True
        elif lrclib_id is not None:
            # The record a search listed; after a restart, LRCLIB's copy.
            with self._lrclib_lock:
                record = self._lrclib_records.get(lrclib_id)
            if record is None:
                record = lrclib.get_record(lrclib_id)
            if record is None:
                raise RegenError("LRCLIB didn't return that match. Try again.")
            if not record.get("syncedLyrics"):
                raise RegenError("That LRCLIB match has no synced lyrics.")
            plan.lrclib_record = record
        return plan

    def _queue(self, job: SongJob, *, reset: bool, label: str) -> None:
        """Back up the song's files, then queue its regen job."""
        song = job.song_path
        try:
            backup_text_folders(song.parent, stems=[song.stem])
        except OSError as e:
            logger.error("Backup before queueing %s failed: %s", song.name, e)
            raise RegenError(f"Could not back up this song's lyric files: {e}") from e
        if not self._processing.enqueue_regen(RegenJob(job, reset=reset, label=label)):
            raise RegenError(BUSY_MESSAGE)

    @staticmethod
    def _song_job(song_path: str) -> SongJob:
        """The song's job with its bundle read and no plan yet."""
        song = Path(song_path)
        return SongJob(
            song_path=song, bundle=read_bundle(song.parent, song.stem), stale_reason="selected"
        )

    @staticmethod
    def _transcribe_plan() -> Plan:
        return Plan(kind="transcribe", label="no lyrics -> transcribe")

    def _regen_job(self, song_path: str) -> SongJob | None:
        """The song's job with the plan a plain regenerate uses, or None without one.

        A song with a recorded pick reuses it; one whose only output is a
        transcription (no bundle, a karaoke file) transcribes again.
        """
        job = self._song_job(song_path)
        if song_status(job.song_path).category == "no_lyrics":
            job.plan = self._transcribe_plan()
        else:
            job.plan = reuse_plan(job)
        return job if job.plan is not None else None

    @staticmethod
    def _lrc_record_id(song: Path) -> int | str | None:
        """The LRCLIB id the song's ``.lrc`` on disk records (a skip marker has none)."""
        try:
            return lrclib.read_lrc(lrclib.lrc_path(song))[1].get("id")
        except (OSError, UnicodeDecodeError):
            return None
