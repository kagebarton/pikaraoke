"""FFmpeg utilities for media processing and transcoding."""

import subprocess
from pathlib import Path


def get_ffmpeg_version() -> str:
    """Get the installed FFmpeg version string.

    Returns:
        Version string, or an error message if FFmpeg is not installed
        or version cannot be parsed.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        first_line = result.stdout.split("\n")[0]
        version_info = first_line.split(" ")[2]
        return version_info
    except FileNotFoundError:
        return "FFmpeg is not installed"
    except IndexError:
        return "Unable to parse FFmpeg version"


def is_transpose_enabled() -> bool:
    """Check if FFmpeg has the rubberband filter for pitch shifting.

    Returns:
        True if rubberband filter is available, False otherwise.
    """
    try:
        filters = subprocess.run(["ffmpeg", "-filters"], capture_output=True)
    except FileNotFoundError:
        return False
    except IndexError:
        return False
    return "rubberband" in filters.stdout.decode()


def probe_duration(media_path: Path) -> float | None:
    """Media duration in seconds via ffprobe, or None if it can't be read.

    Used as the LRCLIB candidate-selection tiebreak; a missing duration just
    drops the tiebreak, never fails processing.
    """
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(media_path),
            ],
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return float(out.strip())
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def is_ffmpeg_installed() -> bool:
    """Check if FFmpeg is installed and accessible.

    Returns:
        True if FFmpeg is installed, False otherwise.
    """
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True)
    except FileNotFoundError:
        return False
    return True
