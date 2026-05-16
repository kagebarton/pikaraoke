"""Genius lyric line parser and query cleaner.

``parse_lyric_lines`` splits raw Genius lyrics text into per-line dicts,
producing both a display ``text`` (parens preserved) and an ``align_text``
(inline parens stripped) so stable-ts aligns to the sung phrase rather
than the parenthetical backing-vocal text.

Speaker diarization from bracket headers was removed: Genius lyrics are
now fetched with ``remove_section_headers=True``, so no header parsing
is required upstream. Any stray bracket-only lines that still slip
through are silently skipped here.

Also contains :func:`clean_genius_query` — a light query cleaner for the
``/lyrics_search`` route that preserves parenthetical and bracketed
content, unlike :func:`regex_tidy` which strips it.
"""

from __future__ import annotations

import re

from pikaraoke.lib.metadata_parser import EMOJI_PATTERN, NOISE_PATTERN

_HEADER_RE = re.compile(r"^\s*\[[^\]]*\]\s*$")
_INLINE_PAREN_RE = re.compile(r"\([^)]*\)")


def parse_lyric_lines(lyrics_text: str) -> list[dict]:
    """Split lyrics into per-line ``{text, align_text}`` dicts.

    - Blank lines and bracket-only lines are dropped.
    - ``align_text`` strips inline parens (e.g. ``"(I can't help) Falling
      in love"`` aligns as ``"Falling in love"``).
    - A line that becomes empty after the paren strip is skipped
      entirely.
    """
    result: list[dict] = []
    for line in lyrics_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADER_RE.match(stripped):
            continue
        align_text = _INLINE_PAREN_RE.sub("", stripped).strip()
        if not align_text:
            continue
        result.append({"text": stripped, "align_text": align_text})
    return result


def clean_genius_query(query: str) -> str:
    """Light-clean a Genius search query, preserving parenthetical content.

    Unlike :func:`regex_tidy` (which strips parenthetical content and can
    mangle titles like ``"(I Can't Help) Falling In Love"``), this function
    only strips emoji and YouTube noise words — it preserves all
    parenthetical and bracketed content so the Genius API can match the
    full title.

    Reuses ``EMOJI_PATTERN`` and ``NOISE_PATTERN`` from
    :mod:`pikaraoke.lib.metadata_parser`.
    """
    cleaned = EMOJI_PATTERN.sub("", query)
    cleaned = cleaned.replace("_", " ")
    cleaned = NOISE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
