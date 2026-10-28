"""Title-only matching for songs that look like one already in the library.

A different upload of the same song has a different YouTube ID, so an ID lookup
calls it new. Here two titles match when they share a distinctive part (usually
the song name). No network; the flag it feeds never blocks anything, so the
rules lean toward showing a match rather than hiding one.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from pikaraoke.lib.metadata_parser import NOISE_PATTERN
from pikaraoke.lib.song_manager import SongManager

MIN_PART_LENGTH = 4
# A part found in this many titles names an artist or film, not a song.
COMMON_PART_COUNT = 3

_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_SEPARATOR = re.compile(r"\s[-|–—_:]\s")
# A quote opens after a non-word character and closes before one, so the
# apostrophes of "Don't Stop Believin'" are not a quote.
_QUOTED = re.compile(r"(?<!\w)['\"‘“](.+?)['\"’”](?!\w)")
# NOISE_PATTERN already covers official/video/lyrics/music/audio/hd.
_STOP_WORDS = frozenset({"the", "a", "an", "4k", "uhd"})


@dataclass(frozen=True)
class TitleParts:
    """The comparable pieces of one title."""

    parts: frozenset[str]
    # The first segment, normally the artist: two titles that merely lead with
    # the same name are two songs by one artist. Empty for a quoted title, whose
    # quote is the song name.
    lead: str


@dataclass(frozen=True)
class SongIndex:
    """Library titles parsed once, with how many titles each part appears in."""

    titles: dict[str, TitleParts]
    frequency: Counter[str]

    @classmethod
    def from_songs(cls, paths: Iterable[str]) -> "SongIndex":
        # Untidied: regex_tidy turns the " _ " that yt-dlp writes for "|" into
        # spaces, which would erase a separator this module splits on.
        titles = {
            path: parse_title(SongManager.filename_from_path(path, tidy=False)) for path in paths
        }
        return cls(titles, _count_parts(titles.values()))


def _normalize(text: str) -> str:
    """Lowercase ASCII words with noise, stop words and punctuation removed."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    ascii_text = NOISE_PATTERN.sub(" ", ascii_text.replace("'", ""))
    words = re.findall(r"[a-z0-9]+", ascii_text)
    return " ".join(word for word in words if word not in _STOP_WORDS)


def _count_parts(titles: Iterable[TitleParts]) -> Counter[str]:
    return Counter(part for title in titles for part in title.parts)


def parse_title(title: str) -> TitleParts:
    """Split a display title (no ID suffix) into its comparable parts.

    Bracketed text is dropped: "(From 'Frozen')" names a film, not the song.
    A quote outside brackets is the song name and the only part kept.
    """
    bare = _BRACKETED.sub(" ", title)
    quoted = _QUOTED.findall(bare)
    segments = quoted or _SEPARATOR.split(bare)
    normalized = [_normalize(segment) for segment in segments]
    parts = frozenset(part for part in normalized if len(part) >= MIN_PART_LENGTH)
    return TitleParts(parts, lead="" if quoted else normalized[0])


def _shared_parts(a: TitleParts, b: TitleParts, frequency: Counter[str]) -> set[str]:
    return {
        part
        for part in a.parts & b.parts
        if frequency[part] < COMMON_PART_COUNT and not (part == a.lead == b.lead)
    }


def similar_songs(title: str, library: SongIndex) -> list[str]:
    """Library song paths that look like ``title``, in the index's order."""
    wanted = parse_title(title)
    return [
        path
        for path, song in library.titles.items()
        if _shared_parts(wanted, song, library.frequency)
    ]


def group_similar(titles: list[str], library: SongIndex) -> list[list[int]]:
    """Group indexes of ``titles`` that look alike; titles matching nothing are omitted.

    A part's frequency counts the library and ``titles`` together, so an artist
    heavy in the playlist does not glue its songs into one group.
    """
    parsed = [parse_title(title) for title in titles]
    frequency = library.frequency + _count_parts(parsed)

    root = list(range(len(parsed)))

    def find(i: int) -> int:
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    for i, first in enumerate(parsed):
        for j in range(i + 1, len(parsed)):
            if _shared_parts(first, parsed[j], frequency):
                root[find(j)] = find(i)

    groups: dict[int, list[int]] = {}
    for i in range(len(parsed)):
        groups.setdefault(find(i), []).append(i)
    return [members for members in groups.values() if len(members) > 1]
