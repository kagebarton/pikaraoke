"""Lift a search's original-artist official uploads, video first and then audio, to the top.

YouTube buries the official upload among lyric videos, covers and re-uploads. Which artist is
the original is not known, so it is voted from the results: the rows YouTube vouches for (a
verified channel, or a label-distributed "art track") name the artist in their titles and
channels. Every rule errs toward lifting nothing, because a miss costs only YouTube's own order.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Literal

from pikaraoke.lib.youtube_dl import SearchResult

OfficialKind = Literal["video", "audio"]

# An artist needs this many trusted credits to be picked, and must beat the runner-up.
_MIN_CREDITS = 2

_SEPARATOR = re.compile(r"\s+[-–—|]\s+|\s*[–—|]\s*")
_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]|【[^】]*】")
_COLLAB = re.compile(
    r"\s*(?:,|&|\bx\b|\bft\b\.?|\bfeat\b\.?|\bfeaturing\b|\bwith\b|\band\b)\s*", re.I
)
_CHANNEL_NOISE = re.compile(r"\b(official|vevo|music|videos?|records|topic|channel|tv)\b", re.I)
# Uploads that are about the song but are not the record: the app overlays its own lyrics, and
# live, remix or acapella audio does not match the record. A mark the query holds is the song's
# own name ("Live and Let Die") or the version asked for, so only marks beyond the query's count.
_NOT_THE_RECORD = re.compile(
    r"\b(lyrics?|sing[- ]?along|live|concert|cover|karaoke|remix|instrumental|acoustic|"
    r"trailer|reaction|behind the|choreography|tutorial|lesson|sped up|slowed|8d|"
    r"multi[- ]language|scene|clip|a ?cappella|acapella)\b",
    re.I,
)
_AUDIO = re.compile(r"\baudio\b", re.I)
_OFFICIAL = re.compile(r"\bofficial\b|\bmusic video\b", re.I)


def _words(text: str) -> list[str]:
    """Lowercase ASCII words of ``text``; apostrophes vanish, so "Don't" is "dont"."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+", ascii_text.replace("'", "").replace("’", ""))


def _has_letters_without_ascii(text: str) -> bool:
    """Kana, hangul, Cyrillic and the like: letters that ``_words`` drops, so no match sees them."""
    return any(
        char.isalpha() and not unicodedata.normalize("NFKD", char).encode("ascii", "ignore")
        for char in text
    )


def _marks(text: str) -> Counter[str]:
    """Each not-the-record mark in ``text`` ("live", "lyric", "sing along"), counted."""
    return Counter(" ".join(_words(match.group())) for match in _NOT_THE_RECORD.finditer(text))


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


def _title_artists(title: str, query_words: Sequence[str]) -> set[str]:
    """The artists a title credits: the side of "A - B" that is not the song.

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


def _credited_artists(result: SearchResult, query_words: Sequence[str]) -> set[str]:
    """The artists a row credits: its title's, plus its channel's for an art track (whose title
    is only the song) and for a title that names no one."""
    artists = _title_artists(result.title, query_words)
    if _is_art_track(result) or not artists:
        artists = artists | {_channel_artist(result)}
    return {artist for artist in artists if artist}


def pick_artist(results: Sequence[SearchResult], query: str) -> str | None:
    """The compact name of the original artist, or None when the results do not settle it.

    Counts credits over the trusted rows. The winner needs at least two and strictly more than
    the runner-up. The caller passes only the first page: over more rows the vote drifts to
    whoever uploaded the most variants of the song.

    Also None for a query in a script the song check cannot read ("夜に駆ける", "BTS 봄날"):
    with no song words left to match, every upload of the artist's would pass as the song.
    """
    if _has_letters_without_ascii(query):
        return None
    query_words = _words(query)
    votes = Counter(
        artist
        for result in results
        if _is_trusted(result)
        for artist in _credited_artists(result, query_words)
    )
    ranked = votes.most_common(2)
    if not ranked:
        return None
    artist, credits = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    return artist if credits >= _MIN_CREDITS and credits > runner_up else None


def _is_the_song(title: str, query_words: Sequence[str], artist: str) -> bool:
    """Whether the title, outside brackets, holds most of the query words that are not part of
    the artist's name. Loose on purpose: a typo falls back to YouTube's order rather than
    lifting the wrong song (Queen's "Another One Bites the Dust" for "queen bohemian rhapsody").
    """
    song_words = [word for word in query_words if word not in artist]
    if not song_words:
        return True
    return _share_found(song_words, _BRACKETED.sub(" ", title)) > 0.5


def official_kind(result: SearchResult, query: str, artist: str | None) -> OfficialKind | None:
    """Whether ``result`` is the ``artist``'s own official video or audio of the song.

    ``channel_is_verified`` alone cannot say so: it is on for lyric channels, karaoke channels,
    the Muppets and a movie trailer, and an unverified fan channel can title its re-upload
    "(official music video)". So the row must also credit the artist and come from them: an art
    track, a trusted channel named for the artist, or a verified label channel (DisneyMusicVEVO)
    whose title says it is official.
    """
    if not artist or _marks(result.title) - _marks(query):
        return None
    query_words = _words(query)
    if not _is_the_song(result.title, query_words, artist):
        return None
    if artist not in _credited_artists(result, query_words):
        return None
    art_track = _is_art_track(result)
    artists_own_channel = _is_trusted(result) and artist in _channel_artist(result)
    labels_upload = result.channel_verified and bool(
        _OFFICIAL.search(result.title) or _AUDIO.search(result.title)
    )
    if not (art_track or artists_own_channel or labels_upload):
        return None
    return "audio" if art_track or _AUDIO.search(result.title) else "video"


def official_first(
    results: Sequence[SearchResult], query: str, artist: str | None
) -> list[tuple[SearchResult, OfficialKind | None]]:
    """The artist's official videos, then their official audio, then the rest.

    Stable: each group keeps YouTube's order.
    """
    ranked = [(result, official_kind(result, query, artist)) for result in results]
    return [pair for group in ("video", "audio", None) for pair in ranked if pair[1] == group]
