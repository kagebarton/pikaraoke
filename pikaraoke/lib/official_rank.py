"""Lift a search's official uploads of the song to the top, videos first.

YouTube buries the official upload among lyric videos, covers, live sessions and re-uploads. Which
act is the original is not known, so it is voted from the results: the rows YouTube vouches for (a
verified channel, or a label-distributed "art track") name the act in their titles and channels.
A row lifts only when it is the song, comes from the act or its label, and says what it is. Every
rule errs toward lifting nothing, because a miss costs only YouTube's own order. There is no
caption lookup, which is too slow for a search: the ranking is a guess from title and channel.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from pikaraoke.lib.youtube_dl import SearchResult

OfficialKind = Literal["video", "audio"]

# An act needs this many trusted credits to be an original.
_MIN_CREDITS = 2

_SEPARATOR = re.compile(r"\s+[-–—|]\s+|\s*[–—|]\s*")
_SQUARE = re.compile(r"\[[^\]]*\]|【[^】]*】")
_ROUND = re.compile(r"\(([^)]*)\)")
_BRACKETED = re.compile(rf"\([^)]*\)|{_SQUARE.pattern}")
_UNCLOSED = re.compile(r"\([^)]*$")  # a bracket the title cuts off
# An opening quote, which is not the apostrophe inside "Don't".
_OPENING_QUOTE = re.compile(r"""(?<![A-Za-z0-9])['"‘“「『]""")
_COLLAB = re.compile(
    r"\s*(?:,|&|\bx\b|\bft\b\.?|\bfeat\b\.?|\bfeaturing\b|\bwith\b|\band\b)\s*", re.I
)
_CHANNEL_NOISE = re.compile(r"\b(official|vevo|music|videos?|records|topic|channel|tv)\b", re.I)
_CHANNEL_SUFFIX = re.compile(r"(?:official|vevo|music|tv|videos?)$")
_LABEL_CHANNEL = re.compile(r"vevo$|\b(?:records|recordings|labels?)\b", re.I)
# Uploads that are about the song but are not the record: the app overlays its own lyrics, and
# live, remix or acapella audio does not match the record. A mark the query holds is the song's
# own name ("Live and Let Die") or the version asked for, so only marks beyond the query's count.
_NOT_THE_RECORD = re.compile(
    r"\b(lyrics?|sing[- ]?along|live|concert|cover|karaoke|remix|instrumental|acoustic|"
    r"trailer|reaction|behind the|choreography|tutorial|lesson|sped up|slowed|8d|"
    r"multi[- ]language|scene|clip|a ?cappella|acapella|"
    r"demo|rehearsal|making of|footnotes|performs?|performance)\b",
    re.I,
)
_AUDIO = re.compile(r"\baudio\b", re.I)
# The title says what the upload is. A bare "official" does not: "(Rosanna Pansino Official)".
_SAYS_OFFICIAL = re.compile(
    r"\bofficial\b[^()\[\]|]*\b(?:video|audio|M/?V)\b|\bmusic video\b|\bM/?V\b", re.I
)
_SAYS_VERSION = re.compile(r"\b(?:version|edition|edit|remaster(?:ed)?)\b", re.I)
# "feat. X", "with X", "from Film": guests and the film, up to the bracket or segment end.
_GUESTS_AND_FILM = re.compile(r"\b(?:feat|ft|featuring|with|from)\b\.?[^()\[\]/|]*", re.I)
# Words a title may carry beyond act and song without saying what it is.
_PLAIN_WORDS = frozenset(
    "official music video audio hd hq 4k mv explicit clean only the a an of and".split()
)


@dataclass(frozen=True)
class Acts:
    """What the first page says: the original acts' names, the words of the record's own title,
    and whether that page lifts any video. ``Acts()`` is "nothing known"."""

    originals: frozenset[str] = frozenset()
    record_words: frozenset[str] = frozenset()
    has_video: bool = False


def _words(text: str) -> list[str]:
    """Lowercase ASCII words of ``text``; apostrophes vanish, so "Don't" is "dont", and "&" is
    "and", so a query's "earth wind and fire" matches the title's "Earth, Wind & Fire"."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    ascii_text = ascii_text.replace("'", "").replace("&", " and ")
    return re.findall(r"[a-z0-9]+", ascii_text)


def _has_letters_without_ascii(text: str) -> bool:
    """Kana, hangul, Cyrillic and the like: letters that ``_words`` drops, so no match sees them."""
    return any(
        char.isalpha() and not unicodedata.normalize("NFKD", char).encode("ascii", "ignore")
        for char in text
    )


def _marks(text: str) -> Counter[str]:
    """Each not-the-record mark in ``text`` ("live", "lyric", "sing along"), counted. Hyphens read
    as spaces, so "Behind-the-Scenes" carries the mark "behind the"."""
    return Counter(
        " ".join(_words(match.group()))
        for match in _NOT_THE_RECORD.finditer(text.replace("-", " "))
    )


def _compact(text: str) -> str:
    """The words joined without spaces, so the channel "lionelrichie" equals "Lionel Richie"."""
    return "".join(_words(text))


def _share_found(words: Sequence[str], text: str) -> float:
    """The fraction of ``words`` that are whole words of ``text``."""
    if not words:
        return 0.0
    have = set(_words(text))
    return sum(word in have for word in words) / len(words)


def _is_art_track(result: SearchResult) -> bool:
    """A label-distributed upload (YouTube's auto-generated "Topic" channels)."""
    return result.description.startswith("Provided to YouTube by") or result.channel.endswith(
        " - Topic"
    )


def _is_trusted(result: SearchResult) -> bool:
    return _is_art_track(result) or result.channel_verified


def _channel_artist(result: SearchResult) -> str:
    """The channel's compact name without "- Topic", "Official", "VEVO" and the like."""
    name = result.channel.removesuffix(" - Topic")
    return _compact(_CHANNEL_NOISE.sub(" ", name))


def _channel_name(result: SearchResult) -> str:
    """``_channel_artist`` without a trailing "VEVO", "Music" and the like that the channel
    spells into its name ("EminemMusic", "PhilosopherKingsVEVO"), and without a leading "the"."""
    name = _channel_artist(result)
    while (match := _CHANNEL_SUFFIX.search(name)) and match.start() > 0:
        name = name[: match.start()]
    return name.removeprefix("the")


def _separated_artists(title: str, query_words: Sequence[str]) -> set[str]:
    """The artists "A - B" credits: the side that is not the song.

    "Artist - Song" unless the left side holds every query word and the right one does not
    ("Song - Artist"). Collaborators on that side each count, and so does the whole side: the
    split cannot tell "Simon & Garfunkel" or "Lil Nas X" from a duet, and whole, the name
    matches the band's channel.
    """
    sides = [side for side in _SEPARATOR.split(_BRACKETED.sub(" ", title)) if _words(side)]
    if len(sides) < 2:
        return set()
    left, right = sides[0], sides[1]
    song_first = _share_found(query_words, left) == 1.0 and _share_found(query_words, right) < 1.0
    artist_side = right if song_first else left
    collaborators = {name for part in _COLLAB.split(artist_side) if (name := _compact(part))}
    return collaborators | {_compact(artist_side)}


def _quoted_song_artists(title: str) -> set[str]:
    """The artists of a title with no separator but a quoted song: the text before the quote,
    and each round-bracket alias in it ("정국 (Jung Kook) 'Seven'" credits jungkook).

    The quote must be outside every bracket: in 'Under the Sea (From "The Little Mermaid")' it
    names the film, and the title credits no one.
    """

    def blank(match: re.Match[str]) -> str:
        return " " * len(match.group())  # positions must not move

    outside = _UNCLOSED.sub(blank, _BRACKETED.sub(blank, title))
    quote = _OPENING_QUOTE.search(outside)
    if quote is None or quote.start() == 0:
        return set()
    head = _SQUARE.sub(" ", title[: quote.start()])
    names = {_compact(_ROUND.sub(" ", head))} | {_compact(alias) for alias in _ROUND.findall(head)}
    return {name for name in names if name}


def _title_artists(title: str, query_words: Sequence[str]) -> set[str]:
    return _separated_artists(title, query_words) or _quoted_song_artists(title)


def _credited_artists(result: SearchResult, query_words: Sequence[str]) -> set[str]:
    """The artists a row credits: its title's, plus its channel's for an art track (whose title
    is only the song) and for a title that names no one."""
    artists = _title_artists(result.title, query_words)
    if _is_art_track(result) or not artists:
        artists = artists | {_channel_artist(result)}
    return {artist for artist in artists if artist}


def _row_names(result: SearchResult, query_words: Sequence[str]) -> set[str]:
    """The acts a row is an upload of. A "- Topic" channel is named for its act and its title is
    only the song (or a cover's "Song - Film"), so there the channel alone says."""
    if result.channel.endswith(" - Topic"):
        return {_channel_artist(result)} - {""}
    return _credited_artists(result, query_words)


def _pick_originals(results: Sequence[SearchResult], query_words: Sequence[str]) -> frozenset[str]:
    """Every name tied for the most trusted credits, or none below ``_MIN_CREDITS``.

    A tie is a duet's two singers and the pair, or two casts of a film song; both are lifted.
    """
    votes = Counter(
        artist
        for result in results
        if _is_trusted(result)
        for artist in _credited_artists(result, query_words)
    )
    top = max(votes.values(), default=0)
    if top < _MIN_CREDITS:
        return frozenset()
    return frozenset(name for name, count in votes.items() if count == top)


def _unexplained(title: str, query_words: Sequence[str], names: set[str]) -> set[str]:
    """Title words that are not the query's, an act's, a guest's or the film's. Loose on purpose
    (a word inside an act's name passes): it only has to catch "(O2 Arena)"."""
    known = set(query_words) | _PLAIN_WORDS
    return {
        word
        for word in _words(_GUESTS_AND_FILM.sub(" ", title))
        if word not in known and not any(word in name for name in names)
    }


def _is_the_song(
    title: str, song_words: Sequence[str], query_words: Sequence[str], names: set[str]
) -> bool:
    """More than half the song words anywhere in the title, and one outside brackets: "Speechless
    (from Aladdin)" is "speechless aladdin", "Another One Bites the Dust (from Bohemian Rhapsody)"
    is not "bohemian rhapsody". The query may say more than the title ("let it go frozen" for
    "Let It Go") or the title more than the query, but not both: a title that lacks a song word
    and carries words of its own outside brackets is another song ("Make You Feel My Love" for
    "send my love")."""
    if not song_words:
        return True
    outside = _BRACKETED.sub(" ", title)
    found = _share_found(song_words, title)
    if _share_found(song_words, outside) == 0 or found <= 0.5:
        return False
    return found == 1.0 or not _unexplained(outside, query_words, names)


def _comes_from_the_act(result: SearchResult, names: set[str]) -> bool:
    """An art track; a trusted channel named for one of the row's acts (equal, not contained: the
    fan channel "ePro Team: Support for Eminem" is not Eminem's); or a verified label channel.

    Only the channel's name makes it a label's: the verified fan channel "Disney¡Fan!" titles its
    re-uploads "Official Music Video".
    """
    channel = _channel_name(result)
    own = _is_trusted(result) and any(name.removeprefix("the") == channel for name in names)
    label = result.channel_verified and bool(_LABEL_CHANNEL.search(result.channel))
    return _is_art_track(result) or own or label


def _says_what_it_is(
    result: SearchResult, query_words: Sequence[str], names: set[str], acts: Acts
) -> bool:
    """A video whose title carries more than act and song must say what it is: "(O2 Arena)" and
    "@ The Tonight Show" are live, "(2025 Version)" and "(Official HD Video)" are not. The record's
    own title is explained ("(To Your New Lover)"), and so is a mark, which got this far only
    because the query asked for it ("bohemian rhapsody live" wants "(Live Aid 1985)")."""
    title = result.title
    if _SAYS_OFFICIAL.search(title) or _SAYS_VERSION.search(title) or _marks(title):
        return True
    return not _unexplained(title, query_words, names) - acts.record_words


def official_kind(result: SearchResult, query: str, acts: Acts) -> OfficialKind | None:
    """Whether ``result`` is an original act's official video or audio of the song.

    ``channel_is_verified`` alone cannot say so: it is on for lyric channels, karaoke channels,
    the Muppets and a movie trailer, and an unverified fan channel can title its re-upload
    "(official music video)". So the row must be the song, come from the act, and, as a video,
    say what it is. Audio is spared that last test: it is never captioned either way.
    """
    if _has_letters_without_ascii(query) or _marks(result.title) - _marks(query):
        return None
    query_words = _words(query)
    names = _row_names(result, query_words)
    credited = names & acts.originals
    if not credited:
        return None
    # Only the names this row credits are struck from the song words. Striking every original's
    # would strike the song itself when its name tied the vote ("under the sea").
    song_words = [word for word in query_words if not any(word in name for name in credited)]
    if not _is_the_song(result.title, song_words, query_words, names):
        return None
    if not _comes_from_the_act(result, names):
        return None
    if _is_art_track(result) or _AUDIO.search(result.title):
        return "audio"
    return "video" if _says_what_it_is(result, query_words, names, acts) else None


def read_first_page(results: Sequence[SearchResult], query: str) -> Acts:
    """Vote the originals, read the record's title off their art tracks, and note whether the
    page lifts any video. Each step needs the one before.

    Pass only the first page: over more rows the vote drifts to whoever uploaded the most
    variants of the song.
    """
    originals = _pick_originals(results, _words(query))
    acts = Acts(originals)
    record_words = frozenset(
        word
        for result in results
        if _is_art_track(result) and official_kind(result, query, acts)
        for word in _words(result.title)
    )
    acts = replace(acts, record_words=record_words)
    has_video = any(official_kind(result, query, acts) == "video" for result in results)
    return replace(acts, has_video=has_video)


def official_first(
    results: Sequence[SearchResult], query: str, acts: Acts
) -> list[tuple[SearchResult, OfficialKind | None]]:
    """The rows in display order with their kinds: the originals' videos first, then YouTube's
    order. A kind is a badge, not a promise that the row moved.

    The originals' audio goes first only when no video is lifted, here or on the first page: it
    is almost never captioned, so beside a video it keeps its place. Stable.
    """
    kinds = [official_kind(result, query, acts) for result in results]
    lifted = {"video"} if acts.has_video or "video" in kinds else {"video", "audio"}
    return sorted(zip(results, kinds), key=lambda pair: pair[1] not in lifted)
