"""Resolve command-line song patterns to library videos.

Shared by ``regen_alignment_bundles.py`` and ``backfill_artifacts.py`` so a
song can be named on the command line (``--song``) instead of scanning the
whole library.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as ``python scripts/song_select.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.metadata_parser import extract_youtube_id  # noqa: E402


def select_songs(videos: list[Path], patterns: list[str]) -> list[Path]:
    """Resolve ``patterns`` to videos, deduped and in ``videos`` order.

    A pattern matches a video when it equals the video's YouTube ID or is a
    case-insensitive substring of the video's filename. Each pattern must
    match exactly one video; a pattern matching zero or several raises
    ``ValueError`` naming the pattern (and, for several, the matching files
    so the user can retype with the ID).
    """
    matched: set[Path] = set()
    for pattern in patterns:
        hits = [v for v in videos if _matches(v, pattern)]
        if not hits:
            raise ValueError(f"No song matches {pattern!r}")
        if len(hits) > 1:
            names = ", ".join(v.name for v in hits)
            raise ValueError(f"{pattern!r} matches multiple songs: {names}")
        matched.add(hits[0])
    return [v for v in videos if v in matched]


def _matches(video: Path, pattern: str) -> bool:
    if extract_youtube_id(str(video)) == pattern:
        return True
    return pattern.lower() in video.name.lower()
