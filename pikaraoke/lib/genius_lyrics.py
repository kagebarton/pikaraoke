"""Genius.com lyrics parser and query cleaner.

Full port of ``genius_diarize/genius.py:parse_genius_sections`` + supporting
functions (Design Decision 7).  The ``align_text`` field (with inline parens
stripped) is the text that stable-ts aligns to; ``text`` (display, with
parens preserved) is for future display/consumers.  This distinction matters
for lines like ``"(I can't help) Falling in love"`` — aligning to
``"Falling in love"`` works better than aligning to the full string.

Also contains :func:`clean_genius_query` — a light query cleaner for the
``/lyrics_search`` route that preserves parenthetical and bracketed content
(Design Decision 8), unlike :func:`regex_tidy` which strips it.
"""

from __future__ import annotations

import logging
import re

from pikaraoke.lib.metadata_parser import EMOJI_PATTERN, NOISE_PATTERN

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section-header regex (from prototype)
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^\[([^\]]+)\]\s*$")

# Strip trailing section number for fuzzy carry-forward ("Verse 2" → "Verse")
_SEC_NUM_RE = re.compile(r"\s+\d+$")

# Known song-section keywords. A colon-less bracket whose first word matches
# is treated as a section name ("[Verse 2]"); anything else is treated as a
# speaker-only attribution ("[Glinda]", "[Glinda & Elphaba]").
_SECTION_KEYWORDS = frozenset(
    {
        "verse",
        "chorus",
        "pre-chorus",
        "prechorus",
        "post-chorus",
        "postchorus",
        "bridge",
        "intro",
        "outro",
        "refrain",
        "hook",
        "interlude",
        "breakdown",
        "coda",
        "instrumental",
        "spoken",
        "drop",
    }
)


def _section_base(name: str) -> str:
    """Return the section name with trailing numbers stripped."""
    return _SEC_NUM_RE.sub("", name).strip()


def _is_section_keyword_header(content: str) -> bool:
    """True if the bracket content begins with a song-section keyword."""
    parts = content.split()
    if not parts:
        return False
    return parts[0].lower() in _SECTION_KEYWORDS


# ---------------------------------------------------------------------------
# Attribution-rule resolver
# ---------------------------------------------------------------------------


def _resolve_attribution(
    groups: list[list[str]] | None,
) -> tuple[str | None, str | None, bool]:
    """Apply attribution rules to a parsed list of groups.

    Args:
        groups: list of groups, each a list of names, as returned by
            :func:`split_groups`.  ``None`` means no attribution (header
            has no ``:``).

    Returns:
        ``(speaker_label, dominant_speaker, is_ensemble)`` — see
        :func:`parse_genius_sections` schema.

    Rules:
    - 0 groups / no attribution → ensemble
    - first name is "All" → ensemble
    - otherwise → color by first name of first group
    """
    if groups is None:
        return None, None, True

    group_count = len(groups)
    if group_count == 0:
        return None, None, True

    # "All" as the first name → ensemble; otherwise color by first name
    if groups[0][0] == "All":
        return None, None, True

    return _resolve_first_group(groups[0])


def _resolve_first_group(
    first_group: list[str],
) -> tuple[str | None, str | None, bool]:
    """Return ``(speaker_label, dominant_speaker, is_ensemble)`` for a named group."""
    if len(first_group) == 1:
        name = first_group[0]
        return name, name, False
    # Named pair / duet
    pair_label = " & ".join(first_group)
    dominant = first_group[0]
    return pair_label, dominant, False


# ---------------------------------------------------------------------------
# Public API: parse_genius_sections (full port, Design Decision 7)
# ---------------------------------------------------------------------------


def parse_genius_sections(lyrics_text: str) -> list[dict]:
    """Parse Genius-formatted lyrics into per-line attribution.

    Returns a list of dicts in document order, one per non-blank,
    non-fully-parenthesized lyric line.  Header lines are consumed
    (not emitted).

    Each dict::

        {
            "text": str,            # lyric text (display; includes parens)
            "align_text": str,      # text with inline parens stripped (for whisper)
            "section": str,         # "Verse 1", "Chorus", ...
            "speaker_label": str|None,   # "Brian", "Kevin & AJ", or None
            "dominant_speaker": str|None, # first individual name, or None
            "is_ensemble": bool,    # True iff unlabeled by rule
        }
    """
    lines = lyrics_text.split("\n")
    result: list[dict] = []

    current_section = ""
    current_groups: list[list[str]] | None = None  # None = no attribution yet
    section_history: dict[str, list[list[str]]] = {}  # exact name → last groups
    section_base_history: dict[str, list[list[str]]] = {}  # base name → last groups

    # Regex for inline parentheses like "(I can't help)" within a lyric line
    _inline_paren_re = re.compile(r"\([^)]*\)")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        header_match = _HEADER_RE.match(stripped)
        if header_match:
            bracket_content = header_match.group(1)
            # Split on first ':' to separate section from attribution
            if ":" in bracket_content:
                section_part, attr_part = bracket_content.split(":", 1)
                current_section = section_part.strip()
                current_groups = split_groups(attr_part.strip())
                section_history[current_section] = current_groups
                section_base_history[_section_base(current_section)] = current_groups
            else:
                current_section = bracket_content.strip()
                # Exact-name carry-forward first; fall back to section family
                # (e.g. "[Verse 2]" inherits from "[Verse 1: Brian]").
                current_groups = section_history.get(current_section)
                if current_groups is None:
                    base = _section_base(current_section)
                    current_groups = section_base_history.get(base)
                    if current_groups is not None:
                        logger.debug(
                            "Section '%s' inheriting attribution from section family '%s'",
                            current_section,
                            base,
                        )
                # Speaker-only header like "[Glinda]" or "[Glinda & Elphaba]":
                # the bracket has no colon, no carry-forward match, and doesn't
                # start with a section keyword. Parse the content as attribution.
                if current_groups is None and not _is_section_keyword_header(current_section):
                    parsed = split_groups(current_section)
                    if parsed:
                        current_groups = parsed
                        section_history[current_section] = current_groups
                        section_base_history[_section_base(current_section)] = current_groups
            continue

        # Build align_text: strip inline parenthesized fragments for alignment
        align_text = _inline_paren_re.sub("", stripped).strip()
        # If stripping parens leaves an empty line, skip it entirely
        if not align_text:
            continue

        # Non-header, non-blank — emit a line dict
        speaker_label, dominant_speaker, is_ensemble = _resolve_attribution(current_groups)

        result.append(
            {
                "text": stripped,
                "align_text": align_text,
                "section": current_section,
                "speaker_label": speaker_label,
                "dominant_speaker": dominant_speaker,
                "is_ensemble": is_ensemble,
            }
        )

    return result


def genius_singer_mode(genius_lines: list[dict]) -> str:
    """Detect whether to run speaker assignment.

    Returns:
        ``"solo"`` — no line has a non-None speaker_label (all ensemble
        or no attribution).  Skip speaker assignment; output plain karaoke.
        ``"multi"`` — at least one line has speaker_label != None.

    Note: an all-ensemble file (e.g., every header is ``[Chorus: All]``)
    yields ``"solo"`` — there is nothing to label.
    """
    for gl in genius_lines:
        if gl["speaker_label"] is not None:
            return "multi"
    return "solo"


def split_groups(attribution: str) -> list[list[str]]:
    """Parse an attribution string into groups of names.

    Splits on ``,`` first (groups), then ``&`` within each group.
    Each name is stripped of whitespace.

    Examples::

        "Brian" → [["Brian"]]
        "Kevin & AJ" → [["Kevin", "AJ"]]
        "Nick, All" → [["Nick"], ["All"]]
        "Brian & AJ, Nick" → [["Brian", "AJ"], ["Nick"]]
        "All" → [["All"]]

    Returns:
        List of groups; each group is a list of name strings.
    """
    groups: list[list[str]] = []
    for group_str in attribution.split(","):
        group_str = group_str.strip()
        if not group_str:
            continue
        names = [n.strip() for n in group_str.split("&") if n.strip()]
        if names:
            groups.append(names)
    return groups


# ---------------------------------------------------------------------------
# Query cleaner (Design Decision 8)
# ---------------------------------------------------------------------------


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
