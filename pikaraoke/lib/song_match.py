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
# A part seen beside this many different other parts names an artist or film, not a song.
COMMON_PART_COUNT = 3

_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_SEPARATOR = re.compile(r"\s[-|–—_:]\s")
# A quote opens after a non-word character, closes with its own kind of mark before one, and
# runs to the last closer, so the apostrophes of "Don't Stop Believin'" and "Rockin' Robin" do
# not end it early.
_QUOTED = re.compile(r"(?<!\w)(?:'(.+)'|\"(.+)\"|‘(.+)’|“(.+)”)(?!\w)")
# NOISE_PATTERN already covers official/video/lyrics/music/audio/hd.
_STOP_WORDS = frozenset({"the", "a", "an", "4k", "uhd"})


@dataclass(frozen=True)
class TitleParts:
    """The comparable pieces of one title."""

    parts: frozenset[str]
    # Every non-empty normalized segment, short ones too. Tells a different song by the same
    # artist from a different upload of the same song. Read only beside a shared lead, so empty
    # for a quoted title.
    segments: frozenset[str]
    # The first segment, normally the artist. A lead shared by two titles is ignored only when
    # each title has a segment the other lacks (two songs by one artist). Empty for a quoted
    # title, whose quote is the song name.
    lead: str


@dataclass(frozen=True)
class SongIndex:
    """Library titles parsed once, with how many different partners each part has."""

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
    """For each part, how many different sets of other parts it appears beside.

    In "Artist - Song" titles an artist sits beside a different song each time, while
    another upload of a song sits beside the same artist, so the song stays below the
    common threshold. Song-first covers ("Song - Singer") give the song a new partner
    each time, so three of them make it common.
    """
    beside: dict[str, set[frozenset[str]]] = {}
    for title in titles:
        for part in title.parts:
            if others := title.parts - {part}:
                beside.setdefault(part, set()).add(others)
    return Counter({part: len(sets) for part, sets in beside.items()})


def parse_title(title: str) -> TitleParts:
    """Split a display title (no ID suffix) into its comparable parts.

    Bracketed text is dropped: "(From 'Frozen')" names a film, not the song.
    A quote of 4+ characters outside brackets is the song name and the only part kept.
    """
    # NFKC first, so fullwidth separators ("｜", "－", "：") split like their ASCII forms.
    segments = _SEPARATOR.split(_BRACKETED.sub(" ", unicodedata.normalize("NFKC", title)))
    quoted = [
        _normalize("".join(match)) for segment in segments for match in _QUOTED.findall(segment)
    ]
    if kept := frozenset(quote for quote in quoted if len(quote) >= MIN_PART_LENGTH):
        return TitleParts(kept, frozenset(), lead="")
    normalized = [_normalize(segment) for segment in segments]
    parts = frozenset(part for part in normalized if len(part) >= MIN_PART_LENGTH)
    return TitleParts(parts, frozenset(filter(None, normalized)), lead=normalized[0])


def _shared_parts(a: TitleParts, b: TitleParts, frequency: Counter[str]) -> set[str]:
    return {
        part
        for part in a.parts & b.parts
        if frequency[part] < COMMON_PART_COUNT
        and not (part == a.lead == b.lead and a.segments - b.segments and b.segments - a.segments)
    }


def similar_songs(title: str, library: SongIndex) -> list[str]:
    """Library song paths that look like ``title``, in the index's order."""
    wanted = parse_title(title)
    return [
        path
        for path, song in library.titles.items()
        if _shared_parts(wanted, song, library.frequency)
    ]


@dataclass(frozen=True)
class SimilarGroup:
    """Titles that look like each other, with the library songs they look like."""

    titles: list[int]  # indexes into the titles given, in order
    songs: list[str]  # library song paths
    part: str  # the shared part(s) most matches agree on, to head the group


def similar_groups(titles: list[str], library: SongIndex) -> list[SimilarGroup]:
    """Group ``titles`` that look like each other or like the same library songs.

    Titles that match nothing are omitted. Between titles a part's frequency
    counts the library and ``titles`` together, so an artist heavy in the
    playlist does not glue its songs into one group; against the library it
    counts the library alone, as in :func:`similar_songs`.
    """
    parsed = [parse_title(title) for title in titles]
    # One count over both lists: summing two counts would count a set of other parts twice.
    playlist_frequency = _count_parts([*library.titles.values(), *parsed])

    # A node is a title's index (int) or a library song's path (str).
    matches: list[tuple[int | str, int | str, set[str]]] = []
    for i, title in enumerate(parsed):
        for j in range(i + 1, len(parsed)):
            if shared := _shared_parts(title, parsed[j], playlist_frequency):
                matches.append((i, j, shared))
        for path, song in library.titles.items():
            if shared := _shared_parts(title, song, library.frequency):
                matches.append((i, path, shared))

    root: dict[int | str, int | str] = {}

    def find(node: int | str) -> int | str:
        root.setdefault(node, node)
        while root[node] != node:
            root[node] = root[root[node]]
            node = root[node]
        return node

    for first, second, _ in matches:
        root[find(second)] = find(first)

    matches_by_group: dict[int | str, list] = {}
    for match in matches:
        matches_by_group.setdefault(find(match[0]), []).append(match)

    groups = []
    for group_matches in matches_by_group.values():
        nodes = dict.fromkeys(
            node for first, second, _ in group_matches for node in (first, second)
        )
        part_counts = Counter(part for *_, shared in group_matches for part in shared)
        top_count = max(part_counts.values())
        # Tied parts (a pair sharing artist and song) are all named: a set has no order to pick by.
        top_parts = sorted(part for part, count in part_counts.items() if count == top_count)
        groups.append(
            SimilarGroup(
                titles=sorted(node for node in nodes if isinstance(node, int)),
                songs=[node for node in nodes if isinstance(node, str)],
                part=" / ".join(top_parts),
            )
        )
    return sorted(groups, key=lambda group: group.titles[0])
