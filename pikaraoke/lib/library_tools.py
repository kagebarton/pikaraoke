"""The app service behind the web library tools.

Song Info and the song lists read bundles through :mod:`library_status`;
regenerate queues a job in the processing manager. Song paths here are the
library's own strings (``song_manager.songs``), which is what the processing
queue, the playing check and the database key on.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pikaraoke.lib.library_regen import (
    VIDEO_EXTS,
    Plan,
    RegenError,
    RegenJob,
    SongJob,
    backup_text_folders,
    read_bundle,
    reuse_plan,
)
from pikaraoke.lib.library_status import (
    SONG_LISTS,
    HistoryEntry,
    SongStatus,
    library_statuses,
    overview_counts,
    song_history,
    song_status,
)
from pikaraoke.lib.processing_manager import ProcessingManager
from pikaraoke.lib.song_manager import SongManager

logger = logging.getLogger(__name__)

BUSY_MESSAGE = "This song has a regen waiting or running."


class LibraryTools:
    def __init__(
        self,
        processing_manager: ProcessingManager,
        song_manager: SongManager,
        download_path: str,
    ) -> None:
        self._processing = processing_manager
        self._song_manager = song_manager
        self._folder = Path(download_path)

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
        song = job.song_path
        try:
            backup_text_folders(song.parent, stems=[song.stem])
        except OSError as e:
            logger.error("Backup before regenerating %s failed: %s", song.name, e)
            raise RegenError(f"Could not back up this song's lyric files: {e}") from e
        if not self._processing.enqueue_regen(RegenJob(job, reset=False, label="Regenerate")):
            raise RegenError(BUSY_MESSAGE)

    @staticmethod
    def _regen_job(song_path: str) -> SongJob | None:
        """The song's job with the plan a plain regenerate uses, or None without one.

        A song with a recorded pick reuses it; one whose only output is a
        transcription (no bundle, a karaoke file) transcribes again.
        """
        song = Path(song_path)
        job = SongJob(
            song_path=song, bundle=read_bundle(song.parent, song.stem), stale_reason="selected"
        )
        if song_status(song).category == "no_lyrics":
            job.plan = Plan(kind="transcribe", label="no lyrics -> transcribe")
        else:
            job.plan = reuse_plan(job)
        return job if job.plan is not None else None
