"""Pick the right Genius song for a video title.

Reads the title into parts (song, act, film, year), asks Genius a short ladder of queries, orders
the merged hits and says whether the first is safe to preselect. One module serves every place
that picks a Genius song so they cannot drift apart.

``tests/unit/data/genius_search`` pins the behaviour per title: what a title parses into, the
queries asked, the order of the hits and the preselect. The regexes below may be rewritten while
every fixture row still holds; the word lists may be extended with one new fixture title that
shows why. Changing a structural rule (the ladder, the order, when to preselect) is a judgement
call, read on titles collected after the change.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pikaraoke.lib.genius import GeniusHit
from pikaraoke.lib.metadata_parser import EMOJI_PATTERN

SEARCH_PAGE_CALLS = 3
LIBRARY_CALLS = 2
MAX_HITS = 8

# --- Word lists ---------------------------------------------------------------------------------

_STRONG = (
    r"official|video|audio|lyrics?|visuali[sz]er|mv|m/v|hd|hq|uhd|4k|\d{3,4}p|\d+fps|"
    r"remaster(?:ed)?|blu-?ray|karaoke|choreography|movieclips|sing-?along|uncensored|subtitled|"
    r"film-?cut|soundtrack|vevo|ytmas|anniversary|edition|官方|完整版|主題曲|電影"
)
# "i" is the separator in 'Music Video I 4K Ultra HD'; measured with it, so it stays.
_WEAK = (
    r"music|ultra|performance|full|scene|clip|explicit|clean|ver\.?|version|live|\d+th|"
    r"motion picture|i"
)
_CJK_JUNK_WORDS = "官方|完整版|主題曲|電影"
# Studio, label and brand names: a channel or title segment that is only these names no act.
_LABEL_WORDS = "sony|animation|netflix|warner|records|vault|movieclips|pictures"
_NOT_AN_ACT_WORDS = (
    "disney|netflix|sony|warner|movieclips|records|pictures|studios|newline|rhino|labels|唱片|娛樂|"
    "天碟|timeless|musical|movie|lion ?king"
)
_VARIANT_WORDS = (
    "parody|instrumental|karaoke|acapella|a cappella|remix|cover|commentary|translation|medley|"
    "radio edit|live|demo|version|mix|edit|reprise|sped up|slowed|multilingual|suite|skit|snippet|"
    "mashup|acoustic"
)
_STOP_WORDS = frozenset(
    {"the", "a", "an", "and", "of", "in", "to", "from", "feat", "ft", "with", "cast", "x", "by"}
)

# --- Patterns -----------------------------------------------------------------------------------

JUNK = re.compile(rf"\b(?:{_STRONG}|{_WEAK})\b|{_CJK_JUNK_WORDS}", re.I)
STRONG_RE = re.compile(rf"\b(?:{_STRONG})\b|{_CJK_JUNK_WORDS}", re.I)
CJK_JUNK = re.compile(_CJK_JUNK_WORDS)
LABEL = re.compile(rf"^(?:{_LABEL_WORDS}|\W)+$", re.I)
NOT_AN_ACT = re.compile(_NOT_AN_ACT_WORDS, re.I)
VARIANT = re.compile(rf"\b({_VARIANT_WORDS})\b", re.I)
STAGE = re.compile(r"\b(?:broadway|west end|musical|stage|tour)\b", re.I)
SCREEN = re.compile(r"\b(?:movie|film|motion picture)\b", re.I)
DUB = re.compile(r"\bOST\b")
CHANNEL_NOISE = re.compile(
    r"\s*-\s*topic$|vevo$|\bofficial\b|\bvideos?\b|\bchannel\b|\bmusic\b|\btv\b|官方專屬頻道", re.I
)

BRACKET = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
CJK_QUOTE = re.compile(r"[【《]([^】》]*)[】》]")
QUOTED = re.compile(
    r"(?:(?<=\s)|^)(?:\"([^\"]{2,}?)\"|“([^”]{2,}?)”|[‘']([^\"”’']{2,}?)[’'])(?=[\s:,]|$)"
)
FROM = re.compile(r"^\s*from\s+(?:(?:.*?\s)?[\"“'‘]([^\"”'’]+)[\"”'’]|([^/_|:–]+))", re.I)
FEAT = re.compile(r"(?:\b(?:feat|ft|featuring)\b\.?|\bw[/_])\s*.*$", re.I)
BY = re.compile(r"\b(?:performed|sung)\s+by\b", re.I)
DASH = re.compile(r"\s+[-–—]\s+|\s+[-–—](?=\S)(?=.*[㐀-鿿])")
COLON = re.compile(r"\s*:\s+|\s+:\s*")
YEAR = re.compile(r"^(?:19|20)\d\d$")
TRAILING_YEAR = re.compile(r"^(.*\S)\s+((?:19|20)\d\d)$")
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
CJK_RUN = re.compile(r"[぀-ヿ㐀-鿿가-힯][぀-ヿ㐀-鿿가-힯\s]*")
YEAR_MARK = "\x00"  # stands where a '(2005)' bracket was, so the year's side of a dash is known
KEPT_OPEN, KEPT_CLOSE = "\x01", "\x02"  # a bracket that stays part of the title


@dataclass(frozen=True)
class Parsed:
    """A video title read into parts."""

    title: str
    alts: tuple[str, ...]  # the title's translation, when the video gives one
    artist: str  # the act, or a film or show named where the act would be
    film: str
    year: int | None
    channel: str  # the act the channel stands for, when it reads as one
    swap: Literal["", "dash", "pipe"]  # 'A - B': A is the act, B less likely; 'A | B': either
    raw: str


@dataclass(frozen=True)
class Found:
    hits: list[GeniusHit]  # at most MAX_HITS, in the order to list them
    preselect: int | None  # hits[0].id when it is safe to preselect, else None
    query: str  # what a search box shows: the first query asked


@dataclass
class _Draft:
    """What a title has been read into so far; becomes a Parsed."""

    title: str = ""
    alts: tuple[str, ...] = ()
    artist: str = ""
    film: str = ""
    year: int | None = None
    swap: Literal["", "dash", "pipe"] = ""


# --- Text helpers -------------------------------------------------------------------------------


def _tidy(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" -–—|_.,:/")


def _clean(s: str) -> str:
    """Tidy, without the year marker and without a word said twice ('Wicked WICKED the Musical')."""
    seen: set[str] = set()
    out: list[str] = []
    for w in _tidy(s.replace(YEAR_MARK, " ")).split():
        if w.lower() not in seen or len(w) < 4:
            out.append(w)
        seen.add(w.lower())
    return " ".join(out)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’‘`´]", "", s)
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def _squash(s: str) -> str:
    return _fold(s).replace(" ", "")


def _word_set(s: str) -> set[str]:
    return {t for t in _fold(s).split() if t not in _STOP_WORDS and len(t) > 1}


def _folded_words(s: str) -> frozenset[str]:
    """Every folded word, stop words too: two queries are the same when these sets are."""
    return frozenset(_fold(s).split())


def _bare(s: str) -> str:
    """The text without its brackets."""
    return _tidy(BRACKET.sub(" ", s))


def _flat(s: str) -> str:
    """Brackets opened: their words stay, the marks go."""
    return _tidy(re.sub(r"[()\[\]]", " ", s))


def _strip_tail_words(s: str) -> str:
    """Drop trailing junk words ('Official MV', 'Music Video I 4K'); a lone weak word stays."""
    tokens = s.split()
    cut = len(tokens)
    while cut and (
        JUNK.fullmatch(tokens[cut - 1].strip(".,"))
        or not any(c.isalnum() for c in tokens[cut - 1].replace(YEAR_MARK, "1"))
    ):
        cut -= 1
    dropped = tokens[cut:]
    if cut and any(STRONG_RE.search(w) or w.lower() in ("scene", "clip") for w in dropped):
        return " ".join(tokens[:cut])
    return s


def _strip_junk_tail(s: str) -> str:
    """Junk words at the end go, also before a kept bracket ('Shallow Sing-Along (Lady Gaga)')."""
    m = re.match(r"^(.*?)((?:\s*\([^()]*\))+)\s*$", s)
    if m and m.group(1).strip():
        head = _strip_tail_words(m.group(1))
        return head + m.group(2) if head else s
    return _strip_tail_words(s)


# --- Channel ------------------------------------------------------------------------------------


def channel_name(channel: str) -> str:
    """The act a channel's name stands for, or "" when it reads as a studio, label or brand.

    "BackstreetBoysVEVO" -> "Backstreet Boys", "Disney Music VEVO" -> "". A trailing VEVO is not
    a label sign here: this module has no credited names to tell a studio's VEVO from an act's,
    so it reads ``NameVEVO`` as ``Name`` and leaves studios to NOT_AN_ACT.
    """
    if not channel or NOT_AN_ACT.search(channel):
        return ""
    name = CHANNEL_NOISE.sub(" ", channel)
    return _tidy(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name))  # BackstreetBoys -> Backstreet Boys


# --- Reading a title ----------------------------------------------------------------------------


def _prepare(raw: str, draft: _Draft) -> str:
    """Emoji, hashtags and handles gone, pipes and slashes as file names store them made real."""
    t = EMOJI_PATTERN.sub("", re.sub(r"[│┃｜]", " | ", raw)).replace("\xad", "")
    t = re.sub(r"[#@]\w+:?", " ", t)
    t = re.sub(r"\s_\s|_\s|\s_|(?<=')_|\s//\s", " | ", t)
    # 'Stay Gold (Official Music Video) from The Outsiders – ...'
    loose_from = re.search(r"[)\]]\s+from\s+(.+)$", t)
    if loose_from:
        draft.film = _tidy(re.split(r"\s[-–—|]\s", loose_from.group(1))[0])
        t = t[: loose_from.start() + 1]
    return t


def _cjk_quoted_title(t: str) -> str:
    """周杰倫 Jay Chou【晴天 Sunny Day】, 《明年今日》: the first quoted phrase; 電影《X》 names a film."""
    title = ""
    for m in CJK_QUOTE.finditer(t):
        if not t[: m.start()].rstrip().endswith("電影"):
            title = title or BRACKET.sub(" ", m.group(1))
    return title


def _open_brackets(t: str, draft: _Draft) -> str:
    """Resolve every bracket: a film or a year is recorded, junk goes, the rest stays."""

    def resolve(m: re.Match) -> str:
        inner = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
        frm = FROM.match(inner)
        if frm:
            draft.film = draft.film or _tidy(_strip_junk_tail(frm.group(1) or frm.group(2)))
            return " "
        if YEAR.match(inner):
            draft.year = int(inner)
            return YEAR_MARK
        film_year = re.match(r"^(.+),\s*((?:19|20)\d\d)$", inner)  # curated '(Titanic, 1997)'
        if film_year:
            draft.film = draft.film or film_year.group(1)
            draft.year = int(film_year.group(2))
            return " "
        junk = not inner or STRONG_RE.search(inner) or JUNK.fullmatch(inner) or FEAT.match(inner)
        if junk or re.fullmatch(r"[\d/ ]+", inner):
            return " "
        short_cjk = CJK.search(inner) and len(inner) <= 3
        if short_cjk or re.search(r"\b(?:version|ver\.?|live)\b", inner, re.I):
            return " "
        return KEPT_OPEN + inner + KEPT_CLOSE  # part of the title or an act's other name

    prev = None
    while prev != t:
        prev = t
        t = BRACKET.sub(resolve, t)
    return t.replace(KEPT_OPEN, "(").replace(KEPT_CLOSE, ")")


def _segments(t: str) -> list[str]:
    """The pipe-separated pieces that say something, not junk-only or label-only ones.

    A segment holding a full-width colon is dropped whole; that is how the prototype read the
    titles it was measured on.
    """
    pieces = [_tidy(s) for s in t.split("|")]
    return [
        s
        for s in pieces
        if _clean(JUNK.sub(" ", s))
        and not LABEL.match(s)
        and "：" not in s
        and not CJK_JUNK.search(s)
    ]


def _read_dash(head: str, rest: list[str], act: str, draft: _Draft) -> None:
    """No quoted title: 'Artist - Title', 'Title - Film (2005)', 'Mulan | Title' and the like."""
    raw_parts = DASH.split(FEAT.sub("", head))
    if len(raw_parts) < 2:
        raw_parts = COLON.split(raw_parts[0])
    year_side = next((i for i, x in enumerate(raw_parts) if YEAR_MARK in x), None)
    parts = [(i, _clean(_strip_junk_tail(_tidy(x)))) for i, x in enumerate(raw_parts)]
    parts = [(i, x) for i, x in parts if x and x.lower() != "cast"]
    # '- Uncensored Version', '- Lyrics (The Little Mermaid)' are junk parts
    real = [(i, x) for i, x in parts if _clean(JUNK.sub(" ", _bare(x)))]
    if len(real) >= 2:  # junk words inside a part ('Frozen lyrics') go too
        real = [
            (i, _clean(STRONG_RE.sub(" ", x)) if _clean(STRONG_RE.sub(" ", _bare(x))) else x)
            for i, x in real
        ]
    parts = real or parts
    if len(parts) >= 2:
        (_, left), (right_index, right) = parts[0], parts[-1]
        act_key = _squash(act)
        if act_key and _squash(_bare(right)) == act_key and _squash(_bare(left)) != act_key:
            left, right = right, left  # 'Title - Artist'
        elif year_side == right_index and not draft.film:
            left, right = right, left  # 'Title - Film (2005)'
        draft.artist, draft.title, draft.swap = left, right, "dash"
        return
    draft.title = parts[0][1] if parts else ""
    if rest:  # 'Mulan | Title', '風繼續吹 | 張國榮 Leslie Cheung': either side may be the title
        draft.artist, draft.swap = _clean(" ".join(rest)), "pipe"


def _settle(draft: _Draft) -> None:
    """Fix up what was read: a year beside the left part marks a film, a translation splits off."""
    m = TRAILING_YEAR.match(draft.artist)  # 'RENT 2005'
    if m:
        draft.artist, draft.year = m.group(1), int(m.group(2))
    if draft.year and draft.artist and not draft.film:
        draft.film, draft.artist = draft.artist, ""
    draft.title, draft.artist, draft.film = (
        _clean(draft.title),
        _clean(draft.artist),
        _clean(draft.film),
    )
    if draft.film and _squash(draft.artist) == _squash(draft.film):
        draft.artist = ""  # 'Encanto - Cast - Title (From "Encanto")': no act named
    run = CJK_RUN.search(draft.title)
    has_latin = re.search(r"[A-Za-z]{2}", draft.title)
    if run and has_latin:  # '晴天 Sunny Day': the title and its translation
        other = _tidy(draft.title.replace(run.group(0), " "))
        draft.title, draft.alts = _tidy(run.group(0)), (other,)


def parse(text: str, channel: str = "") -> Parsed:
    """Read a video title or file name into parts; the channel, when known, helps."""
    draft = _Draft()
    act = channel_name(channel)
    t = _prepare(text, draft)
    quoted_title = _cjk_quoted_title(t)
    t = _open_brackets(CJK_QUOTE.sub(" | ", t), draft)
    quoted = QUOTED.search(t)
    if quoted and not quoted_title:
        quoted_title = quoted.group(1) or quoted.group(2) or quoted.group(3)
        t = t.replace(quoted.group(0), " | ")
    segments = _segments(t)
    head = segments[0] if segments else ""
    rest = [_tidy(_strip_junk_tail(s)) for s in segments[1:]]
    if quoted_title:
        draft.title = _clean(FEAT.sub("", quoted_title))
        artist = " ".join([_tidy(_strip_junk_tail(FEAT.sub("", head)))] + rest)
        draft.artist = _clean(BY.sub(" ", artist))
    else:
        _read_dash(head, rest, act, draft)
    _settle(draft)
    return Parsed(
        title=draft.title,
        alts=draft.alts,
        artist=draft.artist,
        film=draft.film,
        year=draft.year,
        channel=act,
        swap=draft.swap,
        raw=text,
    )


# --- The ladder ---------------------------------------------------------------------------------


def ladder(parsed: Parsed) -> list[str]:
    """Queries to try in order, most specific first, duplicates dropped."""
    title, artist = _bare(parsed.title), _bare(parsed.artist)
    out = (
        [f"{_flat(parsed.artist)} {_flat(parsed.title)}", f"{artist} {title}"]
        if parsed.artist
        else []
    )
    if not parsed.artist and not parsed.film and parsed.channel:
        out.append(f"{parsed.channel} {title}")
    if parsed.film and _squash(parsed.film) not in _squash(parsed.artist):
        out.append(f"{parsed.film} {title}")
    out.append(title)
    if parsed.swap == "pipe":  # either side may be the title: the longer one first
        out[-1:] = sorted([title, artist], key=len, reverse=True)
    elif parsed.swap == "dash":
        out.append(artist)
    seen: set[str] = set()
    queries: list[str] = []
    for q in out:
        q = _tidy(re.sub(r"\s[-–—&]\s", " ", q))
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
    return queries


def _queries(parsed: Parsed) -> list[str]:
    """The ladder, or the text itself when nothing in it reads as a song: what a search box
    starts with is then what is searched."""
    return ladder(parsed) or [q for q in [parsed.raw.strip()] if q]


def start_query(text: str) -> str:
    """The first query for a title, for a search box to start with; the text when nothing reads."""
    return next(iter(_queries(parse(text))), "")


# --- Matching and order -------------------------------------------------------------------------


def _same_title(hit_title: str, wanted: str) -> bool:
    got = _squash(_bare(hit_title)) or _squash(hit_title)
    if not got or not _squash(wanted):
        return False
    if got in (_squash(_bare(wanted)), _squash(wanted)) or _squash(hit_title) == _squash(wanted):
        return True
    return bool(CJK.search(wanted)) and _squash(wanted) in _squash(hit_title)


def _names(hit_artist: str, *sources: str) -> bool:
    """The hit's artist line shares a word with one of the sources (a film's name counts)."""
    have, have_sq = _word_set(hit_artist), _squash(hit_artist)
    return any(
        src
        and (
            _word_set(src) & have
            or (len(_squash(src)) >= 4 and (_squash(src) in have_sq or have_sq in _squash(src)))
        )
        for src in sources
    )


def _credited(hit: GeniusHit, *sources: str) -> bool:
    """The hit's own primary artist is named by one of the sources.

    'Britney Spears' for 'Britney Spears - Toxic'. A cast page that only carries the film's name
    ('Original Broadway Cast of Frozen' for 'Frozen') does not count.
    """
    primary = hit.primary_artist or hit.artist
    parts = [_bare(primary), *(m.group(1) or m.group(2) for m in BRACKET.finditer(primary))]
    target = " ".join(src for src in sources if src)
    have, have_sq = _word_set(target), _squash(target)
    return any(
        part
        and (
            (_word_set(part) and _word_set(part) <= have)
            or (len(_squash(part)) >= 4 and _squash(part) in have_sq)
        )
        for part in parts
    )


def _match(hit: GeniusHit, parsed: Parsed) -> tuple[int, bool, bool]:
    """(how the title matches, the primary artist is named, the artist line shares any name).

    Title: 2 a likely title, 1 the shorter side of a pipe, 0 no match.
    """
    inner = [m.group(1) or m.group(2) for m in BRACKET.finditer(parsed.title)]
    readings = [(2, t, parsed.artist) for t in [parsed.title, *parsed.alts, *inner]]
    if parsed.swap == "dash" and parsed.artist:  # 'Title - Artist' uploads read either way round
        readings.append((2, parsed.artist, parsed.title))
    elif parsed.swap and parsed.artist:
        # of two pipe-separated sides the longer is the likelier title
        level = 2 if len(parsed.artist) > len(parsed.title) else 1
        readings = [(lv if level == 1 else 1, t, w) for lv, t, w in readings]
        readings.append((level, parsed.artist, parsed.title))
    best = (0, False, False)
    for level, title, who in readings:
        if _same_title(hit.title, title):
            found = (
                level,
                _credited(hit, who, parsed.channel),
                _names(hit.artist, who, parsed.channel, parsed.film),
            )
            best = max(best, found, key=lambda m: (m[1], m[0], m[2]))
    return best


def _variant(hit: GeniusHit, parsed: Parsed) -> bool:
    """Another version than the video's: a remix or parody by its title, a stage cast or a dub
    by its artist line."""
    if VARIANT.search(hit.title) and not VARIANT.search(parsed.raw):
        return True
    if DUB.search(hit.artist) and not DUB.search(parsed.raw):
        return True
    if STAGE.search(hit.artist) and not STAGE.search(parsed.raw):
        return True
    return bool(
        SCREEN.search(hit.artist) and STAGE.search(parsed.raw) and not SCREEN.search(parsed.raw)
    )


def _order_key(hit: GeniusHit, parsed: Parsed) -> tuple:
    """Highest first, each level breaking ties in the one above: the title matches at all; the
    act is named, on a page people read; the title match is the likely reading; the year is
    within one of the title's; the act is named, on an unread page; not another version; the
    film's or act's name in the artist line, on a page people read; page views."""
    title, strong, weak = _match(hit, parsed)
    near = parsed.year is not None and hit.year is not None and abs(hit.year - parsed.year) <= 1
    read = hit.views > 0
    return (
        title > 0,
        strong and read,
        title,
        near,
        strong,
        not _variant(hit, parsed),
        weak and read,
        hit.views,
    )


def _confident(hit: GeniusHit, parsed: Parsed) -> bool:
    """Safe to preselect, and what stops the ladder: title and act match, page has views."""
    title, strong, _ = _match(hit, parsed)
    return title == 2 and strong and hit.views > 0


# --- Finding the song ---------------------------------------------------------------------------


def find_song(
    search: Callable[[str], list[GeniusHit]],
    text: str,
    *,
    channel: str = "",
    typed: str = "",
    max_calls: int,
) -> Found:
    """Ask the ladder's queries in order, at most ``max_calls``, stopping after the first that
    returns a hit safe to preselect; then order the merged hits. A title with nothing in it
    that reads as a song asks the title itself, as ``start_query`` shows it.

    ``typed`` is the search the guest ran on YouTube: one more query after the title's own,
    asked only when a call is left, nothing has stopped the ladder and it is not a rewording of
    a query already asked. The title stays what hits are matched against.
    """
    parsed = parse(text, channel)
    asked: list[str] = []
    merged: dict[int, GeniusHit] = {}

    def ask(query: str) -> bool:
        asked.append(query)
        hits = search(query)
        for hit in hits:
            merged.setdefault(hit.id, hit)
        return any(_confident(hit, parsed) for hit in hits)

    for query in _queries(parsed)[:max_calls]:
        if ask(query):
            break
    else:
        typed_words = _folded_words(typed)
        repeats = typed_words in [_folded_words(q) for q in asked]
        if typed_words and len(asked) < max_calls and not repeats:
            ask(typed.strip())
    ordered = sorted(merged.values(), key=lambda h: _order_key(h, parsed), reverse=True)
    hits = ordered[:MAX_HITS]
    preselect = hits[0].id if hits and _confident(hits[0], parsed) else None
    return Found(hits=hits, preselect=preselect, query=asked[0] if asked else text)
