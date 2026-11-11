"""Reference prototype of the revised official-first ranking (2026-11-11).

Not the module. It is a working statement of the rules in plans/search-official-captions.md,
there to settle ambiguity and to produce that plan's expected tables. It borrows the helpers
that do not change from the current pikaraoke.lib.official_rank (imported as ``old``); the
module rewrite keeps those and replaces the rest.

    python plans/search-official-captions/proto_rank2.py <folder of .jsonl searches> [--no-other]

``--no-other`` leaves out the other acts' tier, which is the state after commit 2.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pikaraoke.lib import official_rank as old
from pikaraoke.lib.youtube_dl import SearchResult, _parse_search_line

_MIN_CREDITS = 2

# An opening quote, not the apostrophe inside "Don't".
_OPENING_QUOTE = re.compile(r"""(?<![A-Za-z0-9])['"‘“「『]""")
_SQUARE = re.compile(r"\[[^\]]*\]|【[^】]*】")
_ROUND = re.compile(r"\(([^)]*)\)")
# "feat. X", "with X", "from Film": guests and the film, up to the bracket or segment end.
_GUESTS_AND_FILM = re.compile(r"\b(?:feat|ft|featuring|with|from)\b\.?[^()\[\]/|]*", re.I)
# The title says what the upload is. A bare "official" does not: "(Rosanna Pansino Official)".
_SAYS_OFFICIAL = re.compile(
    r"\bofficial\b[^()\[\]|]*\b(?:video|audio|M/?V)\b|\bmusic video\b|\bM/?V\b", re.I
)
_SAYS_VERSION = re.compile(r"\b(?:version|edition|remaster(?:ed)?)\b", re.I)
_CHANNEL_SUFFIX = re.compile(r"(?:official|vevo|music|tv|videos?)$")
_LABEL_CHANNEL = re.compile(r"vevo$|\b(?:records|recordings|labels?)\b", re.I)
# Words a title may carry beyond artist and song without saying what it is.
_PLAIN_WORDS = frozenset(
    "official music video audio hd hq 4k mv explicit clean only the a an of and".split()
)
# Added to the module's _NOT_THE_RECORD list.
_MORE_MARKS = re.compile(r"\b(demo|rehearsal|making of|footnotes|performs?|performance)\b", re.I)


@dataclass(frozen=True)
class Acts:
    """What the first page says about who is who: the original artist's names, and the acts
    whose own channel has an official video of the song on that page."""

    originals: frozenset[str] = frozenset()
    own_channel: frozenset[str] = frozenset()


def marks(text: str) -> Counter[str]:
    more = Counter(" ".join(old._words(m.group())) for m in _MORE_MARKS.finditer(text))
    return old._marks(text) + more


def channel_name(result: SearchResult) -> str:
    """The channel's compact name without "- Topic", noise words, a trailing "VEVO" or "Music"
    ("EminemMusic", "PhilosopherKingsVEVO") and a leading "the"."""
    name = old._channel_artist(result)
    while (match := _CHANNEL_SUFFIX.search(name)) and match.start() > 0:
        name = name[: match.start()]
    return name.removeprefix("the")


def same_act(name: str, channel: str) -> bool:
    """Equal, not contained: "eminem" is not the fan channel "eproteamsupportforeminem...". """
    return bool(name) and name.removeprefix("the") == channel


def title_artists(title: str, query_words: Sequence[str]) -> set[str]:
    """As today for "A - B". For a title with no separator but a quoted song
    ("BTS (방탄소년단) 'Butter' Official MV"): the text before the quote, and each round-bracket alias
    in it ("정국 (Jung Kook) 'Seven'" credits jungkook)."""
    artists = old._title_artists(title, query_words)
    if artists:
        return artists
    quote = _OPENING_QUOTE.search(title)
    if not quote or not quote.start():
        return set()
    head = _SQUARE.sub(" ", title[: quote.start()])
    names = {old._compact(_ROUND.sub(" ", head))} | {old._compact(g) for g in _ROUND.findall(head)}
    return {name for name in names if name}


def credited_artists(result: SearchResult, query_words: Sequence[str]) -> set[str]:
    """Who votes credit: as today, on top of the new ``title_artists``."""
    artists = title_artists(result.title, query_words)
    if old._is_art_track(result) or not artists:
        artists = artists | {old._channel_artist(result)}
    return {artist for artist in artists if artist}


def row_acts(result: SearchResult, query_words: Sequence[str]) -> set[str]:
    """Whose upload a row is, for lifting. A "- Topic" channel is named for its act and its
    title is only the song (or a cover's "Song - Film"), so there the channel alone says."""
    if result.channel.endswith(" - Topic"):
        return {old._channel_artist(result)} - {""}
    return credited_artists(result, query_words)


def pick_originals(results: Sequence[SearchResult], query: str) -> frozenset[str]:
    """Every name tied for the most trusted credits, or none below two credits. A tie is a
    duet's two singers and the pair, or two casts of a film song; both are lifted."""
    query_words = old._words(query)
    votes = Counter(
        artist
        for result in results
        if old._is_trusted(result)
        for artist in credited_artists(result, query_words)
    )
    top = max(votes.values(), default=0)
    if top < _MIN_CREDITS:
        return frozenset()
    return frozenset(name for name, count in votes.items() if count == top)


def is_the_song(title: str, song_words: Sequence[str]) -> bool:
    """More than half the song words anywhere in the title, at least one outside brackets, so
    "Speechless (from Aladdin)" is "speechless aladdin" and "Another One Bites the Dust (from
    Bohemian Rhapsody)" is not "bohemian rhapsody"."""
    if not song_words:
        return True
    outside = old._share_found(song_words, old._BRACKETED.sub(" ", title))
    return outside > 0 and old._share_found(song_words, title) > 0.5


def unexplained(title: str, query_words: Sequence[str], acts: set[str]) -> list[str]:
    """Title words that are not the query's, an artist's, a guest's or the film's. Loose on
    purpose (a word inside an artist's name passes): it only has to catch "(O2 Arena)"."""
    text = _GUESTS_AND_FILM.sub(" ", title)
    known = set(query_words) | _PLAIN_WORDS
    return [
        word
        for word in old._words(text)
        if word not in known and not any(word in name for name in acts)
    ]


def lift(result: SearchResult, query: str, acts: Acts, other: bool = True):
    """(tier, kind, source) or None. tier "original" | "other"; kind "video" | "audio";
    source "art" | "own" | "label" (source is for reading the prototype's output only)."""
    query_words = old._words(query)
    if marks(result.title) - marks(query):
        return None
    credited = row_acts(result, query_words)
    if not credited:
        return None
    tier = "original" if credited & acts.originals else "other"
    art = old._is_art_track(result)
    says_official = bool(_SAYS_OFFICIAL.search(result.title))
    label_channel = result.channel_verified and bool(_LABEL_CHANNEL.search(result.channel))
    is_audio = art or bool(old._AUDIO.search(result.title))

    channel = channel_name(result)
    own = old._is_trusted(result) and any(same_act(name, channel) for name in credited)
    if tier == "original":
        song_words = [w for w in query_words if not any(w in name for name in acts.originals)]
        if not is_the_song(result.title, song_words):
            return None
    else:
        # Another act's upload: only a label channel's video (a film song's other cast on
        # DisneyMusicVEVO), never the act's own channel, which would lift every other song by
        # this name; and only when the query names nothing the row lacks, so "queen bohemian
        # rhapsody" keeps covers out.
        if not other or is_audio or own or not label_channel:
            return None
        if old._share_found(query_words, result.title + " " + result.channel) < 1.0:
            return None
        if not is_the_song(result.title, query_words):
            return None

    # A label's upload. For the original, a verified channel whose title says official will do
    # (RHINO, Netflix); for any other act the channel itself must read as a label's. Either
    # way not when the act's own channel has the video on this page: then it is a re-upload.
    by_title = tier == "original" and result.channel_verified and (says_official or is_audio)
    label = (label_channel or by_title) and not (credited & acts.own_channel)
    if art:
        source = "art"
    elif own:
        source = "own"
    elif label:
        source = "label"
    else:
        return None

    # A video whose title carries more than artist and song must say what it is: "(O2 Arena)"
    # and "@ The Tonight Show" are live, "(2025 Version)" and "(Official HD Video)" are not.
    # Audio is left alone: it is the fallback, and never captioned either way. So is a title
    # with a mark, which got this far only because the query asked for it ("bohemian rhapsody
    # live" wants "(Live Aid 1985)").
    says_what_it_is = says_official or bool(_SAYS_VERSION.search(result.title))
    if not (is_audio or marks(result.title) or says_what_it_is):
        if unexplained(result.title, query_words, credited):
            return None
    return tier, ("audio" if is_audio else "video"), source


def read_first_page(results: Sequence[SearchResult], query: str) -> Acts:
    """Vote the originals, then note which acts have their own channel's video on the page.
    Nothing for a query in a script the song check cannot read, as today."""
    if old._has_letters_without_ascii(query):
        return Acts()
    originals = pick_originals(results, query)
    first = Acts(originals)
    query_words = old._words(query)
    own_channel = frozenset(
        name
        for result in results
        if (found := lift(result, query, first)) and found[1:] == ("video", "own")
        for name in row_acts(result, query_words)
        if same_act(name, channel_name(result))
    )
    return Acts(originals, own_channel)


_ORDER = {("original", "video"): 0, ("other", "video"): 1, ("original", "audio"): 2}


def official_first(results: Sequence[SearchResult], query: str, acts: Acts, other: bool = True):
    """The original's videos, other acts' official videos, the original's audio, the rest.
    Stable. Nothing is lifted when the query's script cannot be read."""
    if old._has_letters_without_ascii(query):
        return [(result, None) for result in results]
    lifted = [(result, lift(result, query, acts, other)) for result in results]
    keyed = sorted(
        enumerate(lifted), key=lambda item: (_ORDER[item[1][1][:2]] if item[1][1] else 3, item[0])
    )
    return [pair for _, pair in keyed]


def main() -> None:
    folder = Path(sys.argv[1])
    other = "--no-other" not in sys.argv
    for path in sorted(folder.glob("*.jsonl")):
        query = path.stem.replace("_", " ")
        results = [r for r in map(_parse_search_line, path.read_text().splitlines()) if r][:30]
        acts = read_first_page(results, query)
        print(f"\n== {query} | originals={sorted(acts.originals)}")
        for result, found in official_first(results, query, acts, other):
            if found:
                position = results.index(result) + 1
                print(
                    f"   {found[0][:5]:5} {found[1]} {found[2]:5} #{position:2} "
                    f"[{result.channel[:22]}] {result.title[:88]} ({result.id})"
                )


if __name__ == "__main__":
    main()
