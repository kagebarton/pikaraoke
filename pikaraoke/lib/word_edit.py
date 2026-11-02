"""Editing the words of a cue-timed song, line by line, keeping each line's time.

The cue route times a song from an SRT whose cues are its lyric lines. An edit
rewrites those lines and writes the SRT again at the same spans, so only the words
change. A save is checked against the sheet as the server reads it now, because the
admin's page may be stale. It is also checked against the route's own cleaning, which
runs on every line the route loads: a line the cleaning would change is refused with
its cleaned text, never saved as typed and shown differently.
"""

from dataclasses import dataclass

from pikaraoke.lib.library_regen import RegenError
from pikaraoke.lib.srt_cues import clean_cue_texts, cues_to_srt

# The longest line a save takes. Sung lines are a few dozen characters.
EDIT_LINE_MAX_CHARS = 300

STALE_MESSAGE = "This song's lyrics changed since the page opened. Reload the page."


@dataclass(frozen=True)
class WordSheet:
    """A cue sheet's lines as the cue route times them, with where each one is sung."""

    kind: str  # the edited sheet kind a save writes
    lines: list[str]  # cleaned
    spans: list[tuple[float, float]]  # each line's (start, end), clip seconds
    edited: bool = False  # the sheet read is already an edit, not the source's own


class WordsCleaned(RegenError):
    """A save the cleaning would change.

    ``cleaned`` maps the index (in the page's numbering, counting cleared lines) of
    each such line to its cleaned text, ``""`` when the cleaning drops it.
    """

    def __init__(self, cleaned: dict[int, str]):
        super().__init__("The lyric cleaning would change some lines. Check them and save again.")
        self.cleaned = cleaned


def edited_srt(sheet: WordSheet, original: object, lines: object) -> str:
    """The SRT of ``sheet`` with its words replaced by ``lines``, every kept line at its span.

    ``original`` is the lines the admin's page opened with, ``lines`` the page's boxes,
    one per original line; a cleared box (empty) drops its line. Raises
    :class:`~pikaraoke.lib.library_regen.RegenError`, with a message for the admin, for a
    stale page, a malformed save, a line too long, nothing changed or every line
    cleared, and :class:`WordsCleaned` for lines the cleaning would change. "Line N"
    messages count from 1; ``WordsCleaned`` indexes from 0.
    """
    if not (
        isinstance(original, list)
        and original == sheet.lines
        and isinstance(lines, list)
        and len(lines) == len(sheet.lines)
        and all(isinstance(line, str) for line in lines)
    ):
        raise RegenError(STALE_MESSAGE)
    lines = [" ".join(line.split()) for line in lines]
    for number, line in enumerate(lines, start=1):
        if len(line) > EDIT_LINE_MAX_CHARS:
            raise RegenError(f"Line {number} is too long.")
    if lines == sheet.lines:
        raise RegenError("No line was changed.")
    kept = [index for index, line in enumerate(lines) if line]
    if not kept:
        raise RegenError("Every line is cleared. To replace the lyrics, use Repair lyrics.")
    kept_lines = [lines[index] for index in kept]
    cleaned = {
        index: text
        for index, line, text in zip(kept, kept_lines, clean_cue_texts(kept_lines))
        if text != line
    }
    if cleaned:
        raise WordsCleaned(cleaned)
    return cues_to_srt(kept_lines, [sheet.spans[index] for index in kept])
