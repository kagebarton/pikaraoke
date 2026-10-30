"""Pairing a lyric sheet's lines with an LRC's, to give the sheet the LRC's times.

A mixed-language song's Genius page is romanized where LRCLIB writes the original
script. The page's text with the LRC's line times needs each page line matched to an
LRC line. Lines pair by text first (:func:`lrclib.map_lines_to_cues`, fuzzy and
order-keeping), which anchors on the Latin words both sides share. Between two text
pairs the lines pair by position when both sides hold the same number of them.

Two sources split a line differently, and then the counts differ: the sheet's lines
there share the LRC lines' time, longer lines getting more. A stretch with lines on
one side only takes in the text pair beside it, so that its lines have a line of the
other side to divide.
"""

from dataclasses import dataclass
from datetime import timedelta
from itertools import accumulate

import srt

from pikaraoke.lib.lrclib import map_lines_to_cues
from pikaraoke.lib.srt_cues import cue_spans_from_srt


@dataclass(frozen=True)
class Stretch:
    """Sheet lines beside LRC lines, each as a half-open range of line indexes."""

    sheet: tuple[int, int]
    lrc: tuple[int, int]


@dataclass(frozen=True)
class Pairing:
    """How a sheet's lines pair with an LRC's.

    ``by_text`` maps a sheet line to its LRC line. ``by_position`` are the stretches
    between text pairs with equal counts, paired in order. ``shared`` are the
    stretches with unequal counts: their sheet lines divide their LRC lines' time. A
    text pair beside a one-sided stretch is part of that stretch and not in
    ``by_text``.
    """

    by_text: dict[int, int]
    by_position: tuple[Stretch, ...]
    shared: tuple[Stretch, ...]

    def line_map(self) -> dict[int, int]:
        """Every sheet line that has an LRC line of its own, text pairs and position pairs."""
        paired = dict(self.by_text)
        for stretch in self.by_position:
            paired.update(zip(range(*stretch.sheet), range(*stretch.lrc)))
        return paired


def clean_sheet_lines(lines: list[str]) -> list[str]:
    """``lines`` as the cue route reads them back from a saved sheet.

    The route cleans every line it loads and drops the ones that clean to nothing.
    Cleaning a sheet before it is paired and saved means the pairing, the saved file
    and its reload all see the same lines.
    """
    cues = [
        srt.Subtitle(
            index=i, start=timedelta(seconds=i), end=timedelta(seconds=i + 1), content=line
        )
        for i, line in enumerate(lines)
    ]
    texts, _ = cue_spans_from_srt(srt.compose(cues))
    return texts


def pair_lines(sheet: list[str], lrc_lines: list[str]) -> Pairing:
    """Pair ``sheet``'s lines with ``lrc_lines``: by text, then by position, then sharing time.

    ``sheet`` is meant to be cleaned (:func:`clean_sheet_lines`), as the LRC lines are.
    """
    by_text = dict(map_lines_to_cues(sheet, lrc_lines))
    pairs = sorted(by_text.items())
    by_position: list[Stretch] = []
    shared: list[Stretch] = []
    next_sheet = next_lrc = 0
    # The closing pair past both ends walks the stretch after the last text pair.
    for i, (sheet_line, lrc_line) in enumerate([*pairs, (len(sheet), len(lrc_lines))]):
        stretch = Stretch((next_sheet, sheet_line), (next_lrc, lrc_line))
        n_sheet, n_lrc = sheet_line - next_sheet, lrc_line - next_lrc
        next_sheet, next_lrc = sheet_line + 1, lrc_line + 1
        if n_sheet == n_lrc:
            if n_sheet:
                by_position.append(stretch)
        elif n_sheet and n_lrc:
            shared.append(stretch)
        else:
            # One side has no lines: take in the pair before (at the start, the one after).
            neighbour = pairs[i - 1] if i else (pairs[0] if pairs else None)
            if neighbour:
                # Two stretches can take in the song's first pair.
                by_text.pop(neighbour[0], None)
                stretch = _with_pair(stretch, neighbour, before=bool(i))
            if neighbour or n_sheet:
                shared.append(stretch)
    return Pairing(by_text, tuple(by_position), _merge_overlapping(shared))


def _with_pair(stretch: Stretch, pair: tuple[int, int], before: bool) -> Stretch:
    """``stretch`` widened by the text ``pair`` beside it, which lies before or after it."""
    sheet_line, lrc_line = pair
    if before:
        return Stretch((sheet_line, stretch.sheet[1]), (lrc_line, stretch.lrc[1]))
    return Stretch((stretch.sheet[0], sheet_line + 1), (stretch.lrc[0], lrc_line + 1))


def _merge_overlapping(stretches: list[Stretch]) -> tuple[Stretch, ...]:
    """Stretches in line order, those that hold the same line merged into one."""
    merged: list[Stretch] = []
    for stretch in stretches:
        last = merged[-1] if merged else None
        if last and (stretch.sheet[0] < last.sheet[1] or stretch.lrc[0] < last.lrc[1]):
            stretch = Stretch(
                (last.sheet[0], max(last.sheet[1], stretch.sheet[1])),
                (last.lrc[0], max(last.lrc[1], stretch.lrc[1])),
            )
            merged.pop()
        merged.append(stretch)
    return tuple(merged)


def line_spans(
    sheet: list[str], spans: list[tuple[float, float]], pairing: Pairing
) -> list[tuple[float, float]]:
    """Each sheet line's ``(start, end)`` seconds.

    ``spans`` are the LRC lines' spans, indexed as ``pairing`` indexes them. A line
    with an LRC line of its own takes that line's span. In a shared stretch the time
    runs from the first LRC line's start to the last one's end, and the stretch's
    sheet lines divide it in order, each in proportion to its character count (so no
    line of ``sheet`` may be empty: clean it first).
    """
    timed = {line: spans[lrc_line] for line, lrc_line in pairing.line_map().items()}
    for stretch in pairing.shared:
        timed.update(zip(range(*stretch.sheet), _shared_spans(sheet, spans, stretch)))
    return [timed[line] for line in range(len(sheet))]


def _shared_spans(
    sheet: list[str], spans: list[tuple[float, float]], stretch: Stretch
) -> list[tuple[float, float]]:
    first, end = stretch.lrc
    if first == end:
        raise ValueError("A stretch with no LRC line has no time to share.")
    start, stop = spans[first][0], spans[end - 1][1]
    lengths = [len(sheet[line]) for line in range(*stretch.sheet)]
    total = sum(lengths)
    bounds = [start + (stop - start) * done / total for done in accumulate([0, *lengths])]
    bounds[-1] = stop
    return list(zip(bounds, bounds[1:]))


def timed_sheet_srt(sheet: list[str], spans: list[tuple[float, float]], pairing: Pairing) -> str:
    """``sheet`` as SRT text, each line on the span :func:`line_spans` gives it."""
    cues = [
        srt.Subtitle(
            index=0, start=timedelta(seconds=start), end=timedelta(seconds=end), content=text
        )
        for text, (start, end) in zip(sheet, line_spans(sheet, spans, pairing))
    ]
    return srt.compose(cues)
