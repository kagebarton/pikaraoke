"""Candidate shared query builder: read a video title (or file name) into title, artist and film,
then a short ladder of Genius queries and an order for the merged hits. Evaluation prototype."""
import re
import unicodedata
from dataclasses import dataclass, field

from pikaraoke.lib.metadata_parser import EMOJI_PATTERN

STRONG = (
    r"official|video|audio|lyrics?|visuali[sz]er|mv|m/v|hd|hq|uhd|4k|\d{3,4}p|\d+fps|remaster(?:ed)?|blu-?ray|"
    r"karaoke|choreography|movieclips|sing-?along|uncensored|subtitled|film-?cut|soundtrack|vevo|ytmas|anniversary|edition|"
    r"官方|完整版|主題曲|電影"
)
WEAK = r"music|ultra|performance|full|scene|clip|explicit|clean|ver\.?|version|live|\d+th|motion picture|i"
JUNK = re.compile(rf"\b(?:{STRONG}|{WEAK})\b|官方|完整版|主題曲|電影", re.I)
STRONG_RE = re.compile(rf"\b(?:{STRONG})\b|官方|完整版|主題曲|電影", re.I)
LABEL = re.compile(r"^(?:sony|animation|netflix|warner|records|vault|movieclips|pictures|\W)+$", re.I)
BRACKET = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
CJK_QUOTE = re.compile(r"[【《]([^】》]*)[】》]")
QUOTED = re.compile(r"(?:(?<=\s)|^)(?:\"([^\"]{2,}?)\"|“([^”]{2,}?)”|[‘']([^\"”’']{2,}?)[’'])(?=[\s:,]|$)")
FROM = re.compile(r"^\s*from\s+(?:(?:.*?\s)?[\"“'‘]([^\"”'’]+)[\"”'’]|([^/_|:–]+))", re.I)
FEAT = re.compile(r"(?:\b(?:feat|ft|featuring)\b\.?|\bw[/_])\s*.*$", re.I)
BY = re.compile(r"\b(?:performed|sung)\s+by\b", re.I)
DASH = re.compile(r"\s+[-–—]\s+|\s+[-–—](?=\S)(?=.*[㐀-鿿])")
COLON = re.compile(r"\s*:\s+|\s+:\s*")
YEAR = re.compile(r"^(?:19|20)\d\d$")
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
CJK_JUNK = re.compile(r"官方|完整版|主題曲|電影")
CJK_RUN = re.compile(r"[぀-ヿ㐀-鿿가-힯][぀-ヿ㐀-鿿가-힯\s]*")
CHANNEL_NOISE = re.compile(r"\s*-\s*topic$|vevo$|\bofficial\b|\bvideos?\b|\bchannel\b|\bmusic\b|\btv\b|官方專屬頻道", re.I)
NOT_ARTIST = re.compile(r"disney|netflix|sony|warner|movieclips|records|pictures|studios|newline|rhino|labels|唱片|娛樂|天碟|timeless|musical|movie|lion ?king", re.I)
VARIANT = re.compile(
    r"\b(parody|instrumental|karaoke|acapella|a cappella|remix|cover|commentary|translation|medley|radio edit|"
    r"live|demo|version|mix|edit|reprise|sped up|slowed|multilingual|suite|skit|snippet|mashup|acoustic)\b",
    re.I,
)
STOP = {"the", "a", "an", "and", "of", "in", "to", "from", "feat", "ft", "with", "cast", "x", "by"}
YEAR_MARK = "\x00"


@dataclass
class Parsed:
    raw: str = ""
    title: str = ""
    alts: list[str] = field(default_factory=list)  # the title's translation, when the video gives one
    swap: str = ""  # "dash": 'A - B' read as artist then title, the reverse is possible but less likely; "pipe": 'A | B', either way round
    artist: str = ""  # artist, or a film or show named where the artist would be
    film: str = ""
    year: int | None = None
    channel: str = ""  # the artist the channel stands for, when it reads as one


def tidy(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" -–—|_.,:/")


def clean(s: str) -> str:
    """Tidy, without the year marker and without a word said twice ('Wicked WICKED the Musical')."""
    seen, out = set(), []
    for w in tidy(s.replace(YEAR_MARK, " ")).split():
        if w.lower() not in seen or len(w) < 4:
            out.append(w)
        seen.add(w.lower())
    return " ".join(out)


def strip_junk_tail(s: str) -> str:
    """Junk words at the end go, also when a kept bracket follows them ('Shallow Sing-Along (Lady Gaga)')."""
    m = re.match(r"^(.*?)((?:\s*\([^()]*\))+)\s*$", s)
    if m and m.group(1).strip():
        head = _strip_tail_words(m.group(1))
        return (head + m.group(2)) if head == m.group(1) or head else s
    return _strip_tail_words(s)


def _strip_tail_words(s: str) -> str:
    """Drop trailing junk words ('Official MV', 'Music Video I 4K Ultra HD'); a lone weak word stays."""
    words = s.split()
    cut = len(words)
    while cut and (JUNK.fullmatch(words[cut - 1].strip(".,")) or not any(c.isalnum() for c in words[cut - 1].replace(YEAR_MARK, "1"))):
        cut -= 1
    return " ".join(words[:cut]) if cut and any(STRONG_RE.search(w) or w.lower() in ("scene", "clip") for w in words[cut:]) else s


def channel_artist(channel: str | None) -> str:
    """The artist a channel name stands for, or '' when it reads as a label or studio."""
    if not channel or NOT_ARTIST.search(channel):
        return ""
    name = CHANNEL_NOISE.sub(" ", channel)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)  # BackstreetBoys -> Backstreet Boys
    return tidy(name)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’‘`´]", "", s)
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def squash(s: str) -> str:
    return fold(s).replace(" ", "")


def words(s: str) -> set[str]:
    return {t for t in fold(s).split() if t not in STOP and len(t) > 1}


def bare(s: str) -> str:
    """The text without its brackets."""
    return tidy(BRACKET.sub(" ", s))


def parse(raw: str, channel: str | None = None) -> Parsed:
    p = Parsed(raw=raw, channel=channel_artist(channel))
    t = EMOJI_PATTERN.sub("", re.sub(r"[│┃｜]", " | ", raw)).replace("\xad", "")
    t = re.sub(r"[#@]\w+:?", " ", t)
    t = re.sub(r"\s_\s|_\s|\s_|(?<=')_|\s//\s", " | ", t)  # a pipe or slash, as file names store it
    loose_from = re.search(r"[)\]]\s+from\s+(.+)$", t)  # 'Stay Gold (Official Music Video) from The Outsiders – ...'
    if loose_from:
        p.film = tidy(re.split(r"\s[-–—|]\s", loose_from.group(1))[0])
        t = t[: loose_from.start() + 1]

    def bracket(m):
        inner = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
        frm = FROM.match(inner)
        if frm:
            p.film = p.film or tidy(strip_junk_tail(frm.group(1) or frm.group(2)))
            return " "
        if YEAR.match(inner):
            p.year = int(inner)
            return YEAR_MARK
        film_year = re.match(r"^(.+),\s*((?:19|20)\d\d)$", inner)  # curated '(Titanic, 1997)'
        if film_year:
            p.film, p.year = p.film or film_year.group(1), int(film_year.group(2))
            return " "
        if not inner or STRONG_RE.search(inner) or JUNK.fullmatch(inner) or FEAT.match(inner) or re.fullmatch(r"[\d/ ]+", inner):
            return " "
        if CJK.search(inner) and len(inner) <= 3 or re.search(r"\b(?:version|ver\.?|live)\b", inner, re.I):
            return " "
        return "\x01" + inner + "\x02"  # kept: part of the title or an artist's other name

    quoted_title = ""
    for m in CJK_QUOTE.finditer(t):  # 周杰倫 Jay Chou【晴天 Sunny Day】, 《明年今日》; 電影《X》 names a film instead
        if not t[: m.start()].rstrip().endswith("電影"):
            quoted_title = quoted_title or BRACKET.sub(" ", m.group(1))
    t = CJK_QUOTE.sub(" | ", t)
    prev = None
    while prev != t:
        prev = t
        t = BRACKET.sub(bracket, t)
    t = t.replace("\x01", "(").replace("\x02", ")")
    q = QUOTED.search(t)
    if q and not quoted_title:
        quoted_title = q.group(1) or q.group(2) or q.group(3)
        t = t.replace(q.group(0), " | ")
    segments = [tidy(s) for s in t.split("|")]
    segments = [s for s in segments if clean(JUNK.sub(" ", s)) and not LABEL.match(s) and "：" not in s and not CJK_JUNK.search(s)]
    head, rest = (segments[0] if segments else ""), [tidy(strip_junk_tail(s)) for s in segments[1:]]
    year_side = None
    if quoted_title:
        p.title = clean(FEAT.sub("", quoted_title))
        p.artist = clean(BY.sub(" ", " ".join([tidy(strip_junk_tail(FEAT.sub("", head)))] + rest)))
    else:
        raw_parts = DASH.split(FEAT.sub("", segments[0] if segments else ""))
        if len(raw_parts) < 2:
            raw_parts = COLON.split(raw_parts[0])
        year_side = next((i for i, x in enumerate(raw_parts) if YEAR_MARK in x), None)
        parts = [(i, clean(strip_junk_tail(tidy(x)))) for i, x in enumerate(raw_parts)]
        parts = [(i, x) for i, x in parts if x and x.lower() != "cast"]
        real = [(i, x) for i, x in parts if clean(JUNK.sub(" ", bare(x)))]  # '- Uncensored Version', '- Lyrics (The Little Mermaid)'
        if len(real) >= 2:  # junk words inside a part ('Frozen lyrics') go too
            real = [(i, clean(STRONG_RE.sub(" ", x)) if clean(STRONG_RE.sub(" ", bare(x))) else x) for i, x in real]
        parts = real or parts
        if len(parts) >= 2:
            (li, left), (ri, right) = parts[0], parts[-1]
            ch = squash(p.channel)
            if ch and squash(bare(right)) == ch and squash(bare(left)) != ch:
                left, right = right, left  # 'Title - Artist'
            elif year_side == ri and not p.film:
                left, right = right, left  # 'Title - Film (2005)'
            p.artist, p.title, p.swap = left, right, "dash"
        else:
            p.title = parts[0][1] if parts else ""
            if rest:  # 'Mulan | Title', '風繼續吹 | 張國榮 Leslie Cheung': either side may be the title
                p.artist, p.swap = clean(" ".join(rest)), "pipe"
    m = re.match(r"^(.*\S)\s+((?:19|20)\d\d)$", p.artist)  # 'RENT 2005'
    if m:
        p.artist, p.year = m.group(1), int(m.group(2))
    if p.year and p.artist and not p.film:
        p.film, p.artist = p.artist, ""  # a year beside the left part marks a film
    p.title, p.artist, p.film = clean(p.title), clean(p.artist), clean(p.film)
    if p.film and squash(p.artist) == squash(p.film):  # 'Encanto - Cast - Title (From "Encanto")': no artist named
        p.artist = ""
    run = CJK_RUN.search(p.title)
    if run and re.search(r"[A-Za-z]{2}", p.title):  # '晴天 Sunny Day': the title and its translation
        other = tidy(p.title.replace(run.group(0), " "))
        p.title, p.alts = tidy(run.group(0)), [other]
    return p


def flat(s: str) -> str:
    """Brackets opened: their words stay, the marks go."""
    return tidy(re.sub(r"[()\[\]]", " ", s))


def ladder(p: Parsed) -> list[str]:
    """Queries to try in order, most specific first."""
    title, artist = bare(p.title), bare(p.artist)
    out = [f"{flat(p.artist)} {flat(p.title)}", f"{artist} {title}"] if p.artist else []
    if not p.artist and not p.film and p.channel:
        out.append(f"{p.channel} {title}")
    if p.film and squash(p.film) not in squash(p.artist):
        out.append(f"{p.film} {title}")
    out.append(title)
    if p.swap == "pipe":  # either side may be the title: the longer one first
        out[-1:] = sorted([title, artist], key=len, reverse=True)
    elif p.swap == "dash":
        out.append(artist)
    seen, res = set(), []
    for q in out:
        q = tidy(re.sub(r"\s[-–—&]\s", " ", q))
        if q and q.lower() not in seen:
            seen.add(q.lower())
            res.append(q)
    return res


def usable(h: dict) -> bool:
    a = h["artist"].lower()
    return h["type"] == "song" and ("genius" not in a or "romaniz" in a) and "deleted artist" not in a and not h.get("instrumental")


def same_title(hit_title: str, wanted: str) -> bool:
    got = squash(bare(hit_title)) or squash(hit_title)
    if not got or not squash(wanted):
        return False
    if got in (squash(bare(wanted)), squash(wanted)) or squash(hit_title) == squash(wanted):
        return True
    return bool(CJK.search(wanted)) and squash(wanted) in squash(hit_title)


STAGE = re.compile(r"\b(?:broadway|west end|musical|stage|tour)\b", re.I)
SCREEN = re.compile(r"\b(?:movie|film|motion picture)\b", re.I)
DUB = re.compile(r"\bOST\b")
WHO_TIERS = True  # replay switch: False orders hits without a named artist by page views alone


def names(h_artist: str, *sources: str) -> bool:
    """The hit's artist line shares a word with one of the sources (a film's name counts)."""
    have, have_sq = words(h_artist), squash(h_artist)
    return any(src and (words(src) & have or len(squash(src)) >= 4 and (squash(src) in have_sq or have_sq in squash(src))) for src in sources)


def credited(h: dict, *sources: str) -> bool:
    """The hit's own primary artist is named by one of the sources.

    'Britney Spears' for 'Britney Spears - Toxic'. A cast page that only carries the film's name
    ('Original Broadway Cast of Frozen' for 'Frozen') does not count.
    """
    primary = h.get("primary") or h["artist"]
    parts = [bare(primary), *(m.group(1) or m.group(2) for m in BRACKET.finditer(primary))]
    target = " ".join(src for src in sources if src)
    have, have_sq = words(target), squash(target)
    return any(part and (words(part) and words(part) <= have or len(squash(part)) >= 4 and squash(part) in have_sq) for part in parts)


def match(h: dict, p: Parsed) -> tuple[int, bool, bool]:
    """(how the title matches, the primary artist is named, the artist line shares any name).

    Title: 2 a likely title, 1 the shorter side of a pipe, 0 no match.
    """
    inner = [m.group(1) or m.group(2) for m in BRACKET.finditer(p.title)]  # 'Thinking Of You (I Drive Myself Crazy)'
    readings = [(2, t, p.artist) for t in [p.title, *p.alts, *inner]]
    if p.swap == "dash" and p.artist:  # 'Title - Artist' and 'Title - Film' uploads: equal unless an artist is named
        readings.append((2, p.artist, p.title))
    elif p.swap and p.artist:  # of two pipe-separated sides the longer is the likelier title
        level = 2 if len(p.artist) > len(p.title) else 1
        readings = [(lv if level == 1 else 1, t, w) for lv, t, w in readings] + [(level, p.artist, p.title)]
    best = (0, False, False)
    for level, title, who in readings:
        if same_title(h["title"], title):
            found = (level, credited(h, who, p.channel), names(h["artist"], who, p.channel, p.film))
            best = max(best, found, key=lambda m: (m[1], m[0], m[2]))
    return best


def variant(h: dict, p: Parsed) -> bool:
    """Another version than the video's: a remix or parody by its title, a stage cast or dub by its artist line."""
    if VARIANT.search(h["title"]) and not VARIANT.search(p.raw):
        return True
    a = h["artist"]
    if DUB.search(a) and not DUB.search(p.raw):
        return True
    if STAGE.search(a) and not STAGE.search(p.raw):
        return True
    return bool(SCREEN.search(a) and STAGE.search(p.raw) and not SCREEN.search(p.raw))


def order_key(h: dict, p: Parsed) -> tuple:
    """Title match; a named artist on a page people read; the year; a named artist on an unread page;
    not another version; the film's name in the artist line of a page people read; page views."""
    title, strong, weak = match(h, p)
    near = p.year is not None and h.get("year") is not None and abs(h["year"] - p.year) <= 1
    views = h.get("views") or 0
    if not WHO_TIERS:
        return (title > 0, strong and views > 0, title, near, not variant(h, p), views)
    return (title > 0, strong and views > 0, title, near, strong, not variant(h, p), weak and views > 0, views)


def confident(h: dict, p: Parsed) -> bool:
    """Ruling B: preselect only when title and artist both match. Also what stops the ladder."""
    title, strong, _ = match(h, p)
    return title == 2 and strong and bool(h.get("views"))


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    rows = json.loads((Path(__file__).parent / "truth.json").read_text(encoding="utf-8"))
    key = sys.argv[1] if len(sys.argv) > 1 else "yt_title"
    for r in rows:
        if r.get(key):
            p = parse(r[key], r.get("channel") if key == "yt_title" else None)
            print(f"{r[key][:60]:60} T={p.title!r} alts={p.alts} A={p.artist!r} F={p.film!r} Y={p.year} C={p.channel!r} {'swap' if p.swap else ''} || {ladder(p)}")
