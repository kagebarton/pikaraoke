"""Lyric line parsing, per-line normalization, and Genius query cleaner.

``parse_lyric_lines`` splits raw Genius lyrics text into per-line dicts,
producing a display ``text`` (parens preserved) and an ``align_text``
with bracket characters removed but their contents preserved — corpus
audit showed inline parens in Genius lyrics are almost always sung
backing vocals or call-and-response, not stage directions, so stripping
their contents was hiding real audible tokens from the matcher.

``normalize_lyric_line`` and ``clean_srt_line`` are per-line cleanups
shared by the txt and srt loaders in
:mod:`pikaraoke.pipeline.stages.lyric_align`. Both strip HTML tags,
musical-note glyphs, ``[stage directions]``, and SRT's 2-line wraps;
``clean_srt_line`` additionally drops paren-stage-directions like
``(gentle music)`` since SRT parens are noise (unlike Genius parens).

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

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BRACKET_CONTENT_RE = re.compile(r"\[[^\]]*\]")
_PAREN_CONTENT_RE = re.compile(r"\([^)]*\)")
_MUSICAL_NOTE_RE = re.compile(r"[♪♫♬♩]")
_HAS_LETTER_RE = re.compile(r"[A-Za-z]")
_CURLY_QUOTES_TABLE = str.maketrans(
    {"‘": "'", "’": "'", "“": '"', "”": '"'}
)


def normalize_lyric_line(text: str) -> str:
    """Source-agnostic per-line cleanup.

    Collapses SRT's 2-line wraps to single spaces, strips HTML tags
    (``<i>``, ``<b>``…), strips ``[stage direction]`` content, removes
    musical-note glyphs (``♪`` / ``♫``), and normalizes curly quotes to
    ASCII. Does NOT touch parens — Genius parens carry sung backing
    vocals (see :func:`parse_lyric_lines`); SRT parens are stage
    directions and should be cleaned via :func:`clean_srt_line` instead.
    """
    text = text.replace("\n", " ")
    text = _HTML_TAG_RE.sub("", text)
    text = _BRACKET_CONTENT_RE.sub("", text)
    text = _MUSICAL_NOTE_RE.sub("", text)
    text = text.translate(_CURLY_QUOTES_TABLE)
    return " ".join(text.split())


def clean_srt_line(text: str) -> str:
    """SRT-route line cleanup. Applies :func:`normalize_lyric_line`,
    then drops ``(stage direction)`` content — SRT parens in our corpus
    are exclusively non-lyric annotations (``(gentle music)``,
    ``(laughs)``). Returns ``""`` for lines that contain no letters
    after cleanup so the caller can drop them.
    """
    text = normalize_lyric_line(text)
    text = _PAREN_CONTENT_RE.sub("", text)
    text = " ".join(text.split())
    if not _HAS_LETTER_RE.search(text):
        return ""
    return text


def parse_lyric_lines(lyrics_text: str) -> list[dict]:
    """Split lyrics into per-line ``{text, align_text}`` dicts.

    - Blank lines and bracket-only lines are dropped.
    - Each line is passed through :func:`normalize_lyric_line` (drops
      HTML, musical notes, inline ``[stage directions]``, curly-quote
      normalization) — this output is the display ``text``.
    - ``align_text`` additionally removes ``(`` / ``)`` characters
      while keeping the enclosed words (e.g. ``"(I can't help) Falling
      in love"`` aligns as ``"I can't help Falling in love"``).
      Backing-vocal text in parens is sung in the audio, so the
      matcher needs those tokens too.
    - Lines that contain no letters after normalization are dropped
      (stray ``(``, ``)``, ``]``, ``'`` fragments that survive parsing
      would otherwise become empty matcher lines).
    """
    result: list[dict] = []
    for line in lyrics_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADER_RE.match(stripped):
            continue
        display = normalize_lyric_line(stripped)
        if not _HAS_LETTER_RE.search(display):
            continue
        align_text = " ".join(display.replace("(", "").replace(")", "").split())
        result.append({"text": display, "align_text": align_text})
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
