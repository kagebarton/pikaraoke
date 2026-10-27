"""A confirmed lyric sheet as timed units: one per Han character, one per Latin word.

Everything else on a line (spaces, punctuation, brackets) is untimed text kept so the
display is the sheet exactly as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from corpus import CONFIRMED_DIR, HAN_RE

UNIT_RE = re.compile(f"{HAN_RE.pattern}|[A-Za-z]+(?:'[A-Za-z]+)*")


@dataclass(frozen=True)
class Unit:
    text: str
    line: int  # 0-based among the sheet's non-blank lines
    kind: str  # "han" or "latin"
    pre: str  # untimed text between the previous unit on the line and this one


@dataclass(frozen=True)
class Sheet:
    video_id: str
    lines: tuple[str, ...]
    units: tuple[Unit, ...]
    tails: tuple[str, ...]  # untimed text after each line's last unit

    def line_units(self, line: int) -> list[Unit]:
        return [u for u in self.units if u.line == line]


def parse_sheet(video_id: str, text: str) -> Sheet:
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    units: list[Unit] = []
    tails: list[str] = []
    for n, line in enumerate(lines):
        cursor = 0
        for m in UNIT_RE.finditer(line):
            kind = "han" if HAN_RE.fullmatch(m.group()) else "latin"
            units.append(Unit(m.group(), n, kind, line[cursor : m.start()]))
            cursor = m.end()
        tails.append(line[cursor:])
        rebuilt = "".join(u.pre + u.text for u in units if u.line == n) + tails[-1]
        assert rebuilt == line, (video_id, n, line, rebuilt)
    return Sheet(video_id, lines, tuple(units), tuple(tails))


def load_sheet(video_id: str) -> Sheet:
    path = CONFIRMED_DIR / f"{video_id}.txt"
    return parse_sheet(video_id, path.read_text(encoding="utf-8"))
