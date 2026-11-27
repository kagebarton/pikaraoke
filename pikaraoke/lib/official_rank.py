"""Lift a search's official uploads of the song to the top, videos first.

YouTube buries the official upload among lyric videos, covers, live sessions and re-uploads. Which
act is the original is not known, so it is voted from the results: the rows YouTube vouches for (a
verified channel, or a label-distributed "art track") name the act in their titles and channels.
A row lifts only when it is the song, comes from the act or its label, and says what it is. Another
act's video lifts only from a label channel, after the original's (a film song's second cast).
A query that is an act's name alone (its own channel answers it twice) names no song: every title
reads "Act - Song", any of the act's videos is the song, the song a title names explains the
title, and no other act lifts. Every other rule errs toward lifting nothing, because a miss costs
only YouTube's own order. There is no caption lookup, which is too slow for a search: the ranking
is a guess from title and channel.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal, NamedTuple

from pikaraoke.lib.youtube_dl import SearchResult

OfficialKind = Literal["video", "audio"]
_Tier = Literal["original", "other"]  # whose upload: an original's, or another act's on a label

# An act needs this many trusted credits to be an original, and a query this many rows from its
# own channel to be an act's name.
_MIN_CREDITS = 2

_SEPARATOR = re.compile(r"\s+[-–—|]\s+|\s*[–—|]\s*")
_SQUARE = re.compile(r"\[[^\]]*\]|【[^】]*】")
_ROUND = re.compile(r"\(([^)]*)\)")
_BRACKETED = re.compile(rf"\([^)]*\)|{_SQUARE.pattern}")
_UNCLOSED = re.compile(r"[(\[【][^)\]】]*$")  # a bracket the title cuts off
# A quoted song: a quote with no letter or digit before it (not the apostrophe in "Don't") that
# closes ("Don't Stop 'Til You Get Enough" quotes nothing). 「」 and 『』 are never apostrophes.
_QUOTED = re.compile(r"""(?<!\w)(?:'[^']*'|"[^"]*"|‘[^’]*’|“[^”]*”)|「[^」]*」|『[^』]*』""")
_COLLAB = re.compile(
    r"\s*(?:,|&|\bx\b|\bft\b\.?|\bfeat\b\.?|\bfeaturing\b|\bwith\b|\band\b)\s*", re.I
)
_CHANNEL_NOISE = re.compile(r"\b(official|vevo|music|videos?|records|topic|channel|tv)\b", re.I)
_CHANNEL_SUFFIX = re.compile(r"(?:official|vevo|music|tv|videos?|show)$")
_LABEL_CHANNEL = re.compile(r"vevo$|\b(?:records|recordings|labels?)\b", re.I)
# Uploads that are about the song but are not the record: the app overlays its own lyrics, and
# live, remix or acapella audio does not match the record. A mark the query holds is the song's
# own name ("Live and Let Die") or the version asked for, so only marks beyond the query's count.
_NOT_THE_RECORD = re.compile(
    r"\b(lyrics?|sing[- ]?along|live|concert|cover|karaoke|remix|instrumental|acoustic|"
    r"trailer|reaction|behind the|choreography|tutorial|lesson|sped up|slowed|8d|"
    r"multi[- ]language|scene|clip|a ?cappella|acapella|"
    r"demo|rehearsal|making of|footnotes|performs?|performance|unplugged)\b",
    re.I,
)
_AUDIO = re.compile(r"\baudio\b", re.I)
# The title says what the upload is. A bare "official" does not: "(Rosanna Pansino Official)".
_SAYS_OFFICIAL = re.compile(
    r"\bofficial\b[^()\[\]|]*\b(?:video|audio|M/?V)\b|\bmusic video\b|\bM/?V\b", re.I
)
_SAYS_VERSION = re.compile(r"\b(?:version|edition|edit|remaster(?:ed)?)\b", re.I)
# "feat. X", "with X", "from Film": guests and the film, up to the bracket or segment end.
_GUESTS_AND_FILM = re.compile(
    rf"\b(?:feat|ft|featuring|with|from)\b\.?(?:(?!{_SEPARATOR.pattern})[^()\[\]/|])*", re.I
)
# Words a title may carry beyond act and song without saying what it is.
_PLAIN_WORDS = frozenset(
    "official music video audio hd hq 4k mv explicit clean only the a an of and".split()
)


class _Lift(NamedTuple):
    tier: _Tier
    kind: OfficialKind


# Where a row goes: the originals' videos (and their audio when no video lifts), other acts'
# videos, then everything else.
_FIRST, _AFTER_FIRST, _REST = 0, 1, 2
_VIDEO_PLACE: dict[_Tier, int] = {"original": _FIRST, "other": _AFTER_FIRST}


@dataclass(frozen=True)
class Acts:
    """What the first page says: the original acts' names, the words of the record's own title,
    whether that page lifts any video, and whether the query is an act's name. ``Acts()`` is
    "nothing known"."""

    originals: frozenset[str] = frozenset()
    record_words: frozenset[str] = frozenset()
    has_video: bool = False
    act_search: bool = False


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
    spells into its name ("EminemMusic", "PhilosopherKingsVEVO", "KoolandthegangShow"), and
    without a leading "the"."""
    name = _channel_artist(result)
    while (match := _CHANNEL_SUFFIX.search(name)) and match.start() > 0:
        name = name[: match.start()]
    return name.removeprefix("the")


def _sides(title: str) -> list[str]:
    """The parts of "A - B" that have words, brackets dropped."""
    return [side for side in _SEPARATOR.split(_BRACKETED.sub(" ", title)) if _words(side)]


def _separated_artists(title: str, query_words: Sequence[str], act_search: bool) -> set[str]:
    """The artists "A - B" credits: the side that is not the song.

    "Artist - Song" unless the left side holds every query word and the right one does not
    ("Song - Artist"); an act search has no song in its query, so it is always "Artist - Song".
    Collaborators on that side each count, and so does the whole side: the split cannot tell
    "Simon & Garfunkel" or "Lil Nas X" from a duet, and whole, the name matches the band's
    channel.
    """
    sides = _sides(title)
    if len(sides) < 2:
        return set()
    left, right = sides[0], sides[1]
    song_first = (
        not act_search
        and _share_found(query_words, left) == 1.0
        and _share_found(query_words, right) < 1.0
    )
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
    quote = _QUOTED.search(outside)
    if quote is None:
        return set()
    head = _SQUARE.sub(" ", title[: quote.start()])
    names = {_compact(_ROUND.sub(" ", head))} | {_compact(alias) for alias in _ROUND.findall(head)}
    return {name for name in names if name}


def _title_artists(title: str, query_words: Sequence[str], act_search: bool) -> set[str]:
    return _separated_artists(title, query_words, act_search) or _quoted_song_artists(title)


def _credited_artists(
    result: SearchResult, query_words: Sequence[str], act_search: bool
) -> set[str]:
    """The artists a row credits: its title's, plus its channel's for an art track (whose title
    is only the song) and for a title that names no one."""
    artists = _title_artists(result.title, query_words, act_search)
    if _is_art_track(result) or not artists:
        artists = artists | {_channel_artist(result)}
    return {artist for artist in artists if artist}


def _row_names(result: SearchResult, query_words: Sequence[str], act_search: bool) -> set[str]:
    """The acts a row is an upload of. A "- Topic" channel is named for its act and its title is
    only the song (or a cover's "Song - Film"), so there the channel alone says."""
    if result.channel.endswith(" - Topic"):
        return {_channel_artist(result)} - {""}
    return _credited_artists(result, query_words, act_search)


def _pick_originals(
    results: Sequence[SearchResult], query_words: Sequence[str], act_search: bool
) -> frozenset[str]:
    """Every name tied for the most trusted credits, or none below ``_MIN_CREDITS``.

    A tie is a duet's two singers and the pair, or two casts of a film song; both are lifted.
    """
    votes = Counter(
        artist
        for result in results
        if _is_trusted(result)
        for artist in _credited_artists(result, query_words, act_search)
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


def _is_own_channel(result: SearchResult, names: set[str]) -> bool:
    """A trusted channel named for one of the row's acts. Equal, not contained: the fan channel
    "ePro Team: Support for Eminem" is not Eminem's. A channel whose name reads as nothing
    ("Official Music") is no one's."""
    channel = _channel_name(result)
    return (
        bool(channel)
        and _is_trusted(result)
        and any(name.removeprefix("the") == channel for name in names)
    )


def _is_act_search(results: Sequence[SearchResult], query_words: Sequence[str]) -> bool:
    """Whether the query is an act's name alone: its own channel answers it on the page. A song's
    name is no channel's, so a query that names a song never is."""
    act = {"".join(query_words)}
    return sum(_is_own_channel(result, act) for result in results) >= _MIN_CREDITS


def _is_label_channel(result: SearchResult) -> bool:
    """A verified channel whose name ends in "VEVO" or says Records, Recordings or Label. Only the
    name makes a channel a label's: the verified fan channel "Disney¡Fan!" titles its re-uploads
    "Official Music Video"."""
    return result.channel_verified and bool(_LABEL_CHANNEL.search(result.channel))


def _is_the_originals_upload(
    result: SearchResult, query_words: Sequence[str], names: set[str], credited: set[str]
) -> bool:
    """The song, from the act itself (art track or own channel) or its label. ``credited`` are
    the originals the row names."""
    # Only those names are struck from the song words. Striking every original's would strike
    # the song itself when its name tied the vote ("under the sea").
    song_words = [word for word in query_words if not any(word in name for name in credited)]
    return _is_the_song(result.title, song_words, query_words, names) and (
        _is_art_track(result) or _is_own_channel(result, names) or _is_label_channel(result)
    )


def _is_another_cast_on_a_label(
    result: SearchResult, query_words: Sequence[str], names: set[str]
) -> bool:
    """Another act's video of the song on a label channel (DisneyMusicVEVO's second cast of a
    film song). Never from the act's own channel, which would lift every other song of that
    name, and only when the query names nothing the row lacks, so "queen bohemian rhapsody"
    keeps covers out."""
    return (
        _is_label_channel(result)
        and not _is_own_channel(result, names)
        and _share_found(query_words, f"{result.title} {result.channel}") == 1.0
        and _is_the_song(result.title, query_words, query_words, names)
    )


def _named_song(title: str) -> str:
    """The song a title names after its act, or "": the second side of "Act - Song", narrowed to
    its quote ("Act - 'Song' DANCE PRACTICE"); or, in a title with one side, the quote in it."""
    sides = _sides(title)
    if not sides:
        return ""
    side = sides[1] if len(sides) > 1 else sides[0]
    quote = _QUOTED.search(side)
    if quote:
        return quote.group()
    return side if len(sides) > 1 else ""


def _says_what_it_is(
    result: SearchResult, query_words: Sequence[str], names: set[str], acts: Acts
) -> bool:
    """A video whose title carries more than act and song must say what it is: "(O2 Arena)" and
    "@ The Tonight Show" are live, "(2025 Version)" and "(Official HD Video)" are not. The record's
    own title is explained ("(To Your New Lover)"), and so is a mark, which got this far only
    because the query asked for it ("bohemian rhapsody live" wants "(Live Aid 1985)"). In an act
    search the song the title names is explained too: the query has none."""
    title = result.title
    if _SAYS_OFFICIAL.search(title) or _SAYS_VERSION.search(title) or _marks(title):
        return True
    known = [*query_words, *_words(_named_song(title))] if acts.act_search else query_words
    return not _unexplained(title, known, names) - acts.record_words


def _lift(result: SearchResult, query: str, acts: Acts) -> _Lift | None:
    """Whose official video or audio of the song ``result`` is, or None."""
    if _has_letters_without_ascii(query) or _marks(result.title) - _marks(query):
        return None
    query_words = _words(query)
    names = _row_names(result, query_words, acts.act_search)
    if not names:
        return None
    is_audio = _is_art_track(result) or bool(_AUDIO.search(result.title))
    credited = names & acts.originals
    if credited:
        tier: _Tier = "original"
        found = _is_the_originals_upload(result, query_words, names, credited)
    else:
        # No song is named in an act search, so "another cast of the song" is any label upload
        # whose title holds the act's name.
        tier = "other"
        found = (
            not is_audio
            and not acts.act_search
            and _is_another_cast_on_a_label(result, query_words, names)
        )
    if not found:
        return None
    if is_audio:
        return _Lift(tier, "audio")
    return _Lift(tier, "video") if _says_what_it_is(result, query_words, names, acts) else None


def official_kind(result: SearchResult, query: str, acts: Acts) -> OfficialKind | None:
    """Whether ``result`` is an official video or audio of the song, and which.

    ``channel_is_verified`` alone cannot say so: it is on for lyric channels, karaoke channels,
    the Muppets and a movie trailer, and an unverified fan channel can title its re-upload
    "(official music video)". So the row must be the song, come from the act or a label, and, as
    a video, say what it is. Audio is spared that last test (it is never captioned either way),
    and only an original's audio is ever lifted or badged.
    """
    lift = _lift(result, query, acts)
    return lift.kind if lift else None


def read_first_page(results: Sequence[SearchResult], query: str) -> Acts:
    """Decide whether the query is an act's name, vote the originals, read the record's title off
    their art tracks, and note whether the page lifts any video. Each step needs the one before.

    Pass only the first page: over more rows the vote drifts to whoever uploaded the most
    variants of the song. A query the matching cannot read knows nothing.
    """
    if _has_letters_without_ascii(query):
        return Acts()
    query_words = _words(query)
    act_search = _is_act_search(results, query_words)
    acts = Acts(_pick_originals(results, query_words, act_search), act_search=act_search)
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
    """The rows in display order with their kinds: the originals' videos, other acts' videos,
    then YouTube's order. A kind is a badge, not a promise that the row moved.

    The originals' audio goes first only when no video is lifted, here or on the first page: it
    is almost never captioned, so beside a video it keeps its place. Stable.
    """
    lifts = [_lift(result, query, acts) for result in results]
    video_lifted = acts.has_video or any(lift and lift.kind == "video" for lift in lifts)

    def place(lift: _Lift | None) -> int:
        if lift is None:
            return _REST
        if lift.kind == "video":
            return _VIDEO_PLACE[lift.tier]
        return _REST if video_lifted else _FIRST

    order = sorted(range(len(results)), key=lambda i: (place(lifts[i]), i))
    return [(results[i], lifts[i].kind if lifts[i] else None) for i in order]
