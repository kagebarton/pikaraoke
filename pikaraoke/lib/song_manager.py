"""Song library management: scan, delete, rename, and display name operations."""

import contextlib
import logging
import os
import re
from collections.abc import Iterable
from pathlib import Path

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.get_platform import is_windows
from pikaraoke.lib.karaoke_database import KaraokeDatabase
from pikaraoke.lib.library_regen import (
    backup_files,
    backup_text_folders,
    song_files,
    song_stems,
)
from pikaraoke.lib.library_scanner import build_song_record
from pikaraoke.lib.metadata_parser import regex_tidy, youtube_id_suffix
from pikaraoke.lib.song_list import SongList

# Characters illegal in Windows filenames
_WINDOWS_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str) -> str:
    """Replace characters that are illegal in filenames on the current platform.

    ``/`` is replaced everywhere: a name holding one would name another folder.
    """
    name = name.replace("/", "-")
    if is_windows():
        name = _WINDOWS_ILLEGAL_CHARS.sub("-", name)
    return name.strip()


class SongManager:
    """Manages the song library and file operations.

    Owns the SongList instance and provides all song discovery,
    delete, rename, and display name operations.
    """

    def __init__(
        self, download_path: str, db: KaraokeDatabase, events: EventSystem | None = None
    ) -> None:
        self.download_path = download_path
        self.songs = SongList()
        self._db = db
        self._events = events

    @staticmethod
    def filename_from_path(
        file_path: str, remove_youtube_id: bool = True, tidy: bool = True
    ) -> str:
        """Extract a display name from a file path.

        Args:
            file_path: Full path to the file.
            remove_youtube_id: Strip YouTube ID suffix if present.
            tidy: Apply regex_tidy() to strip noise words and normalize.

        Returns:
            Filename without extension, optionally cleaned.
        """
        name = os.path.splitext(os.path.basename(file_path))[0]
        suffix = youtube_id_suffix(file_path)
        if remove_youtube_id and suffix:
            name = name[: -len(suffix)]
        if tidy and suffix and remove_youtube_id:
            tidied = regex_tidy(name)
            if tidied:
                name = tidied
        return name

    def delete(self, song_path: str) -> None:
        """Delete a song and every file it owns from disk, SongList, and DB.

        The song's text files (sheet, captions, bundle) are copied into
        ``regen_backups/<UTC>/`` first, so a delete can be undone for them by
        hand. A failed backup (``OSError``) deletes nothing. The video goes
        last, so a file that can't be removed leaves a song that still plays.
        """
        logging.info(f"Deleting song: {song_path}")
        song = Path(song_path)
        backup = backup_text_folders(song.parent, stems=[song.stem])
        if backup:
            logging.info(f"Backed up {song.name}'s text files to {backup}")
        for path in [*song_files(song), song]:
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)
        self.songs.remove(song_path)
        self._db.delete_by_path(song_path)
        if self._events:
            self._events.emit("song_deleted", song_path)

    def rename(self, song_path: str, new_name: str) -> str:
        """Rename a song and every file it owns, in place. Returns the new path.

        Its copies in ``regen_backups/`` move too, so its version history
        survives. Everything is checked before anything moves; a move that
        fails partway is rolled back. SongList and DB change only after every
        move succeeded.

        Args:
            song_path: Full path to the current song file.
            new_name: New filename (without extension).

        Raises:
            ValueError: The new name is blank, so nothing was moved.
            FileExistsError: The new name belongs to another song or to leftover
                files (backed-up ones included, which would mix another song's
                versions into this one's history), so nothing was moved.
            OSError: A move failed. The files are back under the old name,
                except any whose move back also failed (logged).
        """
        new_name = sanitize_filename(new_name)
        if not new_name:
            raise ValueError("A song's new name can't be empty")
        logging.info(f"Renaming song: '{song_path}' to: {new_name}")
        song = Path(song_path)
        new_song = song.parent / (new_name + song.suffix)
        if new_name in song_stems(song.parent) or song_files(new_song) or backup_files(new_song):
            raise FileExistsError(f"'{new_name}' is already taken by another song or its files")
        moves = [(song, new_song)] + [
            (f, f.parent / (new_name + f.name[len(song.stem) :]))
            for f in [*song_files(song), *backup_files(song)]
        ]
        taken = [dst for _, dst in moves if dst.exists()]
        if taken:
            raise FileExistsError(f"Can't rename onto existing file: {taken[0]}")
        self._move_all(moves)
        self.songs.rename(song_path, str(new_song))
        self._db.update_path(song_path, str(new_song))
        return str(new_song)

    @staticmethod
    def _move_all(moves: list[tuple[Path, Path]]) -> None:
        """Move every ``(src, dst)`` pair, moving the done ones back if one fails."""
        done: list[tuple[Path, Path]] = []
        try:
            for src, dst in moves:
                os.rename(src, dst)
                done.append((src, dst))
        except OSError:
            for src, dst in reversed(done):
                try:
                    os.rename(dst, src)
                except OSError:
                    logging.exception(f"Rename rollback failed: could not restore {src}")
            raise

    def register_download(self, song_path: str) -> None:
        """Register a newly downloaded song in SongList and DB."""
        self.songs.add_if_valid(song_path)
        self._db.insert_songs([build_song_record(song_path, pipeline_state="pending")])

    # ------------------------------------------------------------------
    # Pipeline state / loudnorm forwarders
    # ------------------------------------------------------------------

    def set_loudnorm_offset(self, song_path: str, offset_db: float) -> None:
        """Forwarder so callers don't reach into KaraokeDatabase directly."""
        self._db.set_loudnorm_offset(song_path, offset_db)

    def get_loudnorm_offset(self, song_path: str) -> float | None:
        """Forwarder for loudnorm_offset reads."""
        return self._db.get_loudnorm_offset(song_path)

    def set_pipeline_state(self, song_path: str, state: str) -> None:
        """Forwarder for pipeline_state writes."""
        self._db.set_pipeline_state(song_path, state)

    def get_pipeline_state(self, song_path: str) -> str | None:
        """Forwarder for pipeline_state reads."""
        return self._db.get_pipeline_state(song_path)

    def get_pipeline_states(self, paths: list[str]) -> dict[str, str]:
        """Batch forwarder: returns dict mapping file_path → pipeline_state."""
        return self._db.get_pipeline_states(paths)

    def get_paths_by_pipeline_state(self, states: Iterable[str]) -> list[str]:
        """Forwarder: the paths of songs whose pipeline_state is one of ``states``."""
        return self._db.get_paths_by_pipeline_state(states)
