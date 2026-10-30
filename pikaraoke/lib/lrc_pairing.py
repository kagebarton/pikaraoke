"""Pairing a lyric sheet's lines with an LRC's, to give the sheet the LRC's times.

A mixed-language song's Genius page is romanized where LRCLIB writes the original
script. The page's text with the LRC's line times needs each page line matched to an
LRC line. Lines pair by text first (:func:`lrclib.map_lines_to_cues`, fuzzy and
order-keeping), which anchors on the Latin words both sides share. Between two text
pairs the lines pair by position, but only when both sides hold the same number of
them: two sources split a line differently, and a stretch with unequal counts has no
safe pairing, so it is refused.
"""

from dataclasses import dataclass
from datetime import timedelta

import srt

from pikaraoke.lib.lrclib import map_lines_to_cues


@dataclass(frozen=True)
class Stretch:
    """Sheet lines beside LRC lines, each as a half-open range of line indexes."""

    sheet: tuple[int, int]
    lrc: tuple[int, int]


@dataclass(frozen=True)
class Pairing:
    """How a sheet's lines pair with an LRC's.

    ``by_text`` maps a sheet line to its LRC line. ``by_position`` are the stretches
    between text pairs with equal counts, paired in order. ``refused`` are those with
    unequal counts (one side may be empty): their lines have no pair.
    """

    by_text: dict[int, int]
    by_position: tuple[Stretch, ...]
    refused: tuple[Stretch, ...]

    def line_map(self) -> dict[int, int]:
        """Every paired sheet line to its LRC line, text pairs and position pairs."""
        paired = dict(self.by_text)
        for stretch in self.by_position:
            paired.update(zip(range(*stretch.sheet), range(*stretch.lrc)))
        return paired


def pair_lines(sheet: list[str], lrc_lines: list[str]) -> Pairing:
    """Pair ``sheet``'s lines with ``lrc_lines``, by text and then by position."""
    by_text = map_lines_to_cues(sheet, lrc_lines)
    by_position: list[Stretch] = []
    refused: list[Stretch] = []
    next_sheet = next_lrc = 0
    # The closing pair past both ends walks the stretch after the last text pair.
    for sheet_line, lrc_line in [*sorted(by_text.items()), (len(sheet), len(lrc_lines))]:
        stretch = Stretch((next_sheet, sheet_line), (next_lrc, lrc_line))
        n_sheet, n_lrc = sheet_line - next_sheet, lrc_line - next_lrc
        if n_sheet != n_lrc:
            refused.append(stretch)
        elif n_sheet:
            by_position.append(stretch)
        next_sheet, next_lrc = sheet_line + 1, lrc_line + 1
    return Pairing(by_text, tuple(by_position), tuple(refused))


def timed_sheet_srt(sheet: list[str], spans: list[tuple[float, float]], pairing: Pairing) -> str:
    """``sheet`` as SRT text, each line on the span of the LRC line it pairs with.

    ``spans`` are the LRC lines' ``(start, end)`` seconds, indexed as ``pairing``
    indexes them. Raises ``ValueError`` when a stretch was refused: a line with no
    time is no sheet.
    """
    if pairing.refused:
        raise ValueError("A refused stretch leaves sheet lines with no time.")
    lrc_of = pairing.line_map()
    cues = []
    for line, text in enumerate(sheet):
        start, end = spans[lrc_of[line]]
        cues.append(
            srt.Subtitle(
                index=0, start=timedelta(seconds=start), end=timedelta(seconds=end), content=text
            )
        )
    return srt.compose(cues)
