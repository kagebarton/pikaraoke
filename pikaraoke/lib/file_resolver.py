"""File resolution and temporary file management utilities."""

import logging
import os
import shutil
import tempfile
import time
from sys import maxsize

from pikaraoke.lib.ffmpeg import get_media_duration
from pikaraoke.lib.get_platform import get_temp_directory


def get_tmp_dir(base_dir: str = "") -> str:
    """Get the temporary directory path scoped to this process.

    Args:
        base_dir: Optional base directory for temp files. If provided,
                  uses os.path.join(base_dir, pid). Otherwise uses
                  the system temp directory.

    Returns:
        Path to the process-specific temporary directory.
    """
    pid = os.getpid()  # for scoping tmp directories to this process
    if base_dir:
        tmp_dir = os.path.join(base_dir, f"{pid}")
    else:
        tmp_dir = os.path.join(tempfile.gettempdir(), f"{pid}")
    return tmp_dir


def create_tmp_dir(base_dir: str = "") -> None:
    """Create the temporary directory if it doesn't exist.

    Args:
        base_dir: Optional base directory for temp files.
    """
    tmp_dir = get_tmp_dir(base_dir)
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)


def delete_tmp_dir(base_dir: str = "") -> None:
    """Delete the temporary directory and all its contents.

    Args:
        base_dir: Optional base directory for temp files.
    """
    tmp_dir = get_tmp_dir(base_dir)
    if os.path.exists(tmp_dir):
        # On Windows, files may still be locked briefly after process termination
        # Use error handler to ignore permission errors on individual files
        def handle_remove_error(func, path, exc_info):
            """Error handler for shutil.rmtree - ignores permission errors on Windows"""
            import logging

            if isinstance(exc_info[1], PermissionError):
                logging.debug(
                    f"Could not delete {path}: file in use, will be cleaned up on next run"
                )
            else:
                logging.warning(f"Error deleting {path}: {exc_info[1]}")

        shutil.rmtree(tmp_dir, onerror=handle_remove_error)


def string_to_hash(s: str) -> int:
    """Convert a string to a positive integer hash.

    Args:
        s: String to hash.

    Returns:
        Positive integer hash value.
    """
    return hash(s) % ((maxsize + 1) * 2)


def is_transcoding_required(file_path: str) -> bool:
    """Check if a file requires transcoding for browser playback.

    MP4 and WebM files can be played natively; others need transcoding.

    Args:
        file_path: Path to the media file.

    Returns:
        True if transcoding is required, False otherwise.
    """
    file_extension = os.path.splitext(file_path)[1].casefold()
    return file_extension != ".mp4" and file_extension != ".webm"


class FileResolver:
    """Resolves media files for playback.

    Processes a given file path and determines the file format and paths.

    Attributes:
        file_path: Path to the main media file.
        file_extension: Lowercase file extension of the input file.
        tmp_dir: Temporary directory for extracted files.
        stream_uid: Unique identifier for the stream based on file path hash.
        output_file: Path where the transcoded output will be written.
        segment_pattern: Pattern for HLS segment filenames.
        init_filename: Filename for HLS initialization segment.
        streaming_format: Video streaming format ('hls' or 'mp4').
        duration: Duration of the media file in seconds.
    """

    file_path: str | None = None
    file_extension: str | None = None
    ass_file_path: str | None = None

    def __init__(self, file_path: str, streaming_format: str = "hls", temp_dir: str = "") -> None:
        """Initialize the FileResolver with a media file path.

        Args:
            file_path: Path to the media file to resolve.
            streaming_format: Video streaming format ('hls' or 'mp4').
            temp_dir: Optional base directory for temporary files.
        """
        create_tmp_dir(temp_dir)
        self.tmp_dir = get_tmp_dir(temp_dir)
        self.resolved_file_path = self.process_file(file_path)
        # Include timestamp to ensure unique stream UIDs for repeated plays
        unique_string = f"{file_path}_{time.time()}"
        self.stream_uid = string_to_hash(unique_string)
        self.streaming_format = streaming_format

        # Set output file extension based on streaming format
        if streaming_format == "mp4":
            self.output_file = f"{self.tmp_dir}/{self.stream_uid}.mp4"
        else:  # hls
            self.output_file = f"{self.tmp_dir}/{self.stream_uid}.m3u8"

        self.segment_pattern = f"{self.tmp_dir}/{self.stream_uid}_segment_%03d.m4s"
        self.init_filename = f"{self.stream_uid}_init.mp4"

    def get_current_stream_size(self) -> int:
        """Get the size of files belonging to this stream in the temporary directory.

        Only counts files containing the stream_uid in their filename.
        Primarily used for HLS mode to check if the buffer is full before starting playback.
        """
        stream_uid_str = str(self.stream_uid)
        return sum(
            os.path.getsize(os.path.join(self.tmp_dir, f))
            for f in os.listdir(self.tmp_dir)
            if stream_uid_str in f
        )

    def handle_aegissub_subtile(self, file_path: str) -> bool:
        """Find and set subtitle file paths for a media file.

        Checks the 'subtitles' subfolder for an ASS file (karaoke subtitle).
        Sets ass_file_path if found.

        Args:
            file_path: Path to the media file.

        Returns:
            True if a subtitle file was found, False otherwise.
        """
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        subtitles_dir = os.path.join(os.path.dirname(file_path), "subtitles")
        found = False

        for ext in (".ass", ".ASS", ".Ass"):
            ass_path = os.path.join(subtitles_dir, base_name + ext)
            if os.path.exists(ass_path):
                self.file_path = file_path
                self.ass_file_path = ass_path
                logging.debug(f"ASS subtitle file found: {ass_path}")
                found = True
                break

        return found

    def process_file(self, file_path: str) -> None:
        """Process a file path and set up resolution.

        Args:
            file_path: Path to the media file.
        """

        file_extension = os.path.splitext(file_path)[1].casefold()
        self.file_extension = file_extension
        self.file_path = file_path
        # If there is an aegissub subtitle file found, set the path to it
        self.handle_aegissub_subtile(file_path)
        if not self.file_path:
            raise ValueError("File path is required to process file")
        self.duration = get_media_duration(self.file_path)
