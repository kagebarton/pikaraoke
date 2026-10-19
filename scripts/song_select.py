"""Resolve command-line song patterns to library videos.

Shared by ``regen_alignment_bundles.py`` and ``backfill_artifacts.py`` so a
song can be named on the command line (``--song``) instead of scanning the
whole library.
"""

from __future__ import annotations

from pathlib import Path

from pikaraoke.lib.metadata_parser import extract_youtube_id


def select_songs(videos: list[Path], patterns: list[str]) -> list[Path]:
    """Resolve ``patterns`` to videos, deduped and in ``videos`` order.

    A pattern's exact matches win: it equals the video's YouTube ID, or its
    stem or file name case-insensitively. Only when it has none does it fall
    back to a case-insensitive substring of the file name. Each pattern must
    pick exactly one video; a pattern matching zero or several raises
    ``ValueError`` naming the pattern (and, for several, the matching files
    so the user can retype with the ID).
    """
    matched: set[Path] = set()
    for pattern in patterns:
        hits = [v for v in videos if _is_exact_match(v, pattern)] or [
            v for v in videos if pattern.lower() in v.name.lower()
        ]
        if not hits:
            raise ValueError(f"No song matches {pattern!r}")
        if len(hits) > 1:
            names = ", ".join(v.name for v in hits)
            raise ValueError(f"{pattern!r} matches multiple songs: {names}")
        matched.add(hits[0])
    return [v for v in videos if v in matched]


def _is_exact_match(video: Path, pattern: str) -> bool:
    return extract_youtube_id(str(video)) == pattern or pattern.lower() in (
        video.stem.lower(),
        video.name.lower(),
    )
