"""Song library management: scan, delete, rename, and display name operations."""

import contextlib
import logging
import os
import re

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.get_platform import is_windows
from pikaraoke.lib.karaoke_database import KaraokeDatabase
from pikaraoke.lib.library_scanner import build_song_record
from pikaraoke.lib.metadata_parser import regex_tidy, youtube_id_suffix
from pikaraoke.lib.song_list import SongList

# Characters illegal in Windows filenames
_WINDOWS_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(name: str) -> str:
    """Remove characters that are illegal in filenames on the current platform."""
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

    def _get_companion_files(self, song_path: str) -> list[str]:
        """Return paths to companion files (.ass, vocal/nonvocal) that exist alongside a song.

        ASS subtitle files are expected in a 'subtitles' subfolder.
        Audio separator files are expected in 'vocal/' and 'nonvocal/' subfolders.
        """
        dirpath = os.path.dirname(song_path)
        base = os.path.splitext(os.path.basename(song_path))[0]
        companions = []

        # ASS subtitles live in the subtitles/ subfolder
        subtitles_dir = os.path.join(dirpath, "subtitles")
        for ext in (".ass", ".ASS", ".Ass"):
            ass_path = os.path.join(subtitles_dir, base + ext)
            if os.path.exists(ass_path):
                companions.append(ass_path)
                break

        # Audio separator files live in vocal/ and nonvocal/ subfolders
        for subdir, suffix in (("vocal", "---vocal"), ("nonvocal", "---nonvocal")):
            sep_dir = os.path.join(dirpath, subdir)
            for ext in (".m4a", ".M4A"):
                sep_path = os.path.join(sep_dir, base + suffix + ext)
                if os.path.exists(sep_path):
                    companions.append(sep_path)
                    break

        return companions

    def delete(self, song_path: str) -> None:
        """Delete a song from disk, SongList, and DB."""
        logging.info(f"Deleting song: {song_path}")
        companions = self._get_companion_files(song_path)
        with contextlib.suppress(FileNotFoundError):
            os.remove(song_path)
        for companion in companions:
            with contextlib.suppress(FileNotFoundError):
                os.remove(companion)
        self.songs.remove(song_path)
        self._db.delete_by_path(song_path)
        if self._events:
            self._events.emit("song_deleted", song_path)

    def rename(self, song_path: str, new_name: str) -> str:
        """Rename a song on disk, in SongList, and in DB. Returns new path.

        Args:
            song_path: Full path to the current song file.
            new_name: New filename (without extension).
        """
        new_name = sanitize_filename(new_name)
        logging.info(f"Renaming song: '{song_path}' to: {new_name}")
        companions = self._get_companion_files(song_path)
        base, ext = os.path.splitext(os.path.basename(song_path))
        new_path = os.path.join(self.download_path, new_name + ext)
        os.rename(song_path, new_path)
        for companion in companions:
            companion_dir = os.path.dirname(companion)
            tail = os.path.basename(companion)[len(base) :]  # e.g. ".ass", "---vocal.m4a"
            os.rename(companion, os.path.join(companion_dir, new_name + tail))
        self.songs.rename(song_path, new_path)
        self._db.update_path(song_path, new_path)
        return new_path

    def register_download(self, song_path: str) -> None:
        """Register a newly downloaded song in SongList and DB."""
        self.songs.add_if_valid(song_path)
        self._db.insert_songs([build_song_record(song_path)])
