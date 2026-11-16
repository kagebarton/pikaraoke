"""GATE G collection (plans/genius-search-spec.md, "GATE G", Phase 5).

usage: collect.py            (from anywhere; run in env `pik`)

Runs the thirty fixed YouTube searches as the search page runs them, keeps up to four fresh videos
per search, reads each video through `find_song` as the search page does (three calls, the channel,
the typed search), then again without the typed term, and writes:

    youtube.json   every search's rows (and its attempts), cached; a rerun makes no YouTube call
    genius.json    Genius's answer per query, cached by query; a rerun makes no Genius call for a
                   query it has
    sheet.md       one block per video, in table order
    verdicts.md    the judge's table, empty

Counts and judges nothing. The code under test must be committed: it refuses to collect over a
dirty `pikaraoke/`, `tests/` or `scripts/`, so the HEAD it records is the code that ran.

No lyric text is committed (the Executor rules), and a lyric video's description snippet opens
with its lyrics. So the cache as YouTube gave it, and the sheet built from it, live in RAW_DIR
(~/probes, never committed); the committed `youtube.json` and `sheet.md` are the same data with
LYRIC_SPANS cut out of the kept videos' snippets (Ken, 2026-11-16) and the snippets of videos that
were not kept left out (the selection reads only ID and title).
"""

import configparser
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))  # this worktree's pikaraoke, not an editable install's
sys.path.insert(0, str(HERE.parent / "run2"))  # the prototype's `squash`, as the spec names it

import builder  # noqa: E402
from pikaraoke.lib.genius import HITS_PER_QUERY, GeniusClient, GeniusHit  # noqa: E402
from pikaraoke.lib.genius_query import SEARCH_PAGE_CALLS, find_song, parse  # noqa: E402
from pikaraoke.lib.youtube_dl import get_search_results  # noqa: E402
from pikaraoke.routes.search import PAGE_SIZE  # noqa: E402

FIXTURES = REPO / "tests" / "unit" / "data" / "genius_search"
YOUTUBE_JSON = HERE / "youtube.json"
GENIUS_JSON = HERE / "genius.json"
SHEET = HERE / "sheet.md"
VERDICTS = HERE / "verdicts.md"
# The uncommitted full data: the YouTube cache as it came, and the sheet built from it.
RAW_DIR = Path.home() / "probes" / "genius_search_accuracy_gate_g"
RAW_YOUTUBE = RAW_DIR / "youtube.json"
RAW_SHEET = RAW_DIR / "sheet.md"

# Where lyric text sits in a kept video's description snippet, by video ID: (start, end) offsets
# into the snippet as YouTube gave it, end None for "to the end". Found by reading all 120 kept
# snippets; offsets, not text, so this file holds none of it. The words around a cut stay.
CUT_MARK = "[lyrics cut]"
LYRIC_SPANS: dict[str, tuple[int, int | None]] = {
    "7oKPYe53h78": (89, None),  # 4.4
    "VH0MCjzv5QQ": (111, None),  # 6.3
    "tlsYT771gSc": (0, 28),  # 9.4
    "pW6N42hSHrY": (35, None),  # 16.3
    "QRidtXn0u7k": (57, None),  # 19.2
    "ioNng23DkIM": (30, None),  # 24.1
    "G9UQ63tWIqA": (38, None),  # 26.2
    "M7986vfxL9g": (49, None),  # 26.3
    "KgQx3Ob8l8A": (18, None),  # 27.1
    "SLbSsv_2u4A": (56, None),  # 28.2
    "WUxgIPYDQHE": (6, 30),  # 30.4
}

PER_SEARCH = 4  # videos kept per search
RERUNS = 3  # a search whose rows all lack a channel is run again, at most this often
ATTEMPTS = 4  # tries for a Genius query, or for a yt-dlp run that errors
# Genius answered HTTP 429 (a Cloudflare challenge) after 90 unpaced calls in about two minutes,
# and to three retries 3-9 s apart. Pace every call and back off long after a failure; neither
# changes what is asked or read.
PACE_S = 1.5
BACKOFF_S = 60
SNIPPET_CHARS = 300

# (number, search typed as is, the video's title must carry, kind) -- the spec's table, as written.
# `kind` is why the search is here; the sheet does not print it.
SEARCHES = [
    (1, "remember me coco", "Remember Me", "film"),
    (2, "i dreamed a dream les miserables", "I Dreamed a Dream", "film, stage"),
    (3, "music of the night phantom of the opera", "Music of the Night", "film, stage"),
    (4, "you're the one that i want grease", "You're the One That I Want", "film, stage"),
    (5, "the winner takes it all mamma mia", "The Winner Takes It All", "film, act"),
    (6, "you will be found dear evan hansen", "You Will Be Found", "film, stage"),
    (7, "a million dreams greatest showman", "A Million Dreams", "film, cover"),
    (8, "go the distance hercules", "Go the Distance", "film, single, stage"),
    (9, "kiss the girl little mermaid", "Kiss the Girl", "two films"),
    (10, "friend like me aladdin", "Friend Like Me", "two films, stage"),
    (11, "i just can't wait to be king lion king", "I Just Can't Wait to Be King", "two films, stage"),
    (12, "the wizard and i wicked", "The Wizard and I", "film, stage"),
    (13, "memory cats", "Memory", "film, stage"),
    (14, "and i am telling you dreamgirls", "And I Am Telling You", "film, stage"),
    (15, "my shot hamilton", "My Shot", "stage only"),
    (16, "taylor swift love story", "Love Story", "act, re-recording"),
    (17, "whitney houston greatest love of all", "Greatest Love of All", "act"),
    (18, "bon jovi livin on a prayer", "Livin' on a Prayer", "act"),
    (19, "billie jean michael jackson", "Billie Jean", "act, title first"),
    (20, "olivia rodrigo drivers license", "drivers license", "act"),
    (21, "bruno mars uptown funk", "Uptown Funk", "act, featured not primary"),
    (22, "the weeknd blinding lights", "Blinding Lights", "act"),
    (23, "linkin park numb", "Numb", "act"),
    (24, "blackpink how you like that", "How You Like That", "act, K-pop"),
    (25, "bts dynamite", "Dynamite", "act, K-pop, shared title"),
    (26, "周杰倫 告白氣球", "告白氣球", "act, CJK"),
    (27, "陳奕迅 浮誇", "浮誇", "act, CJK"),
    (28, "creep", "Creep", "title only"),
    (29, "yesterday", "Yesterday", "title only"),
    (30, "imagine", "Imagine", "title only"),
]


def stop(message: str) -> None:
    raise SystemExit(f"STOP: {message}")


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --- YouTube ------------------------------------------------------------------------------------


def run_search(term: str) -> dict:
    """One search as the search page runs it. Run again only when every row came back without a
    channel (YouTube does that to about 1 search in 12); the first answer with channels is kept,
    the last one if none has. A yt-dlp run that errors gives no answer and is retried apart."""
    attempts: list[dict] = []
    rows: list = []
    errors = 0
    while len(attempts) <= RERUNS:
        try:
            rows = get_search_results(term, PAGE_SIZE)
        except subprocess.CalledProcessError as e:
            errors += 1
            attempts.append({"error": f"yt-dlp exit {e.returncode}"})
            if errors >= ATTEMPTS:
                stop(f"yt-dlp failed {errors} times for {term!r}")
            time.sleep(5 * errors)
            continue
        with_channel = sum(1 for r in rows if r.channel)
        attempts.append({"rows": len(rows), "with_channel": with_channel})
        print(f"  {term!r}: {len(rows)} rows, {with_channel} with a channel", flush=True)
        if with_channel:
            break
    return {"attempts": attempts, "rows": [asdict(r) for r in rows]}


def load_youtube() -> dict:
    """The thirty searches' rows, running whatever the cache lacks. The raw cache is read when it
    is there, else the committed one (a clone: same selection, the lyrics already cut); new
    searches are written to the raw cache."""
    source = next((p for p in (RAW_YOUTUBE, YOUTUBE_JSON) if p.exists()), None)
    if source:
        cache = json.loads(source.read_text(encoding="utf-8"))
    else:
        if git("status", "--porcelain", "--untracked-files=no", "--", "pikaraoke", "tests", "scripts"):
            stop("pikaraoke/, tests/ or scripts/ differ from HEAD: the code is not frozen")
        cache = {"head": git("rev-parse", "HEAD"), "date": date.today().isoformat(), "searches": {}}
    for number, term, _carries, _kind in SEARCHES:
        if term not in cache["searches"]:
            print(f"YouTube search {number}", flush=True)
            cache["searches"][term] = run_search(term)
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            write_json(RAW_YOUTUBE, cache)
    return cache


def cut_lyrics(video_id: str, description: str) -> str:
    """The snippet with its lyric span, if it has one, replaced by CUT_MARK."""
    span = LYRIC_SPANS.get(video_id)
    if span is None or CUT_MARK in description:
        return description
    start, end = span
    after = description[end:] if end is not None else ""
    return " ".join(p for p in (description[:start].strip(), CUT_MARK, after.strip()) if p)


def committed_cache(cache: dict, kept: dict[int, list[dict]]) -> dict:
    """The cache as it is committed: a kept video's snippet with its lyrics cut, every other
    row without a snippet."""
    kept_ids = {row["id"] for rows in kept.values() for row in rows}

    def committed_row(row: dict) -> dict:
        if row["id"] in kept_ids:
            return {**row, "description": cut_lyrics(row["id"], row["description"])}
        return {k: v for k, v in row.items() if k != "description"}

    searches = {
        term: {**s, "rows": [committed_row(r) for r in s["rows"]]}
        for term, s in cache["searches"].items()
    }
    return {**cache, "searches": searches}


def known_ids() -> set[str]:
    """The videos already spent as fixtures: the library's 206 and the 176 unseen."""
    ids: set[str] = set()
    for name in ("library.jsonl", "unseen.jsonl"):
        for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
            ids.add(json.loads(line)["id"])
    return ids


def select(cache: dict) -> dict[int, list[dict]]:
    """Per search, the first four rows in YouTube's order whose folded title holds the carried
    title's, not a fixture's video and not kept by an earlier search. Never topped up."""
    taken = known_ids()
    kept: dict[int, list[dict]] = {}
    for number, term, carries, _kind in SEARCHES:
        want = builder.squash(carries)
        picked: list[dict] = []
        for row in cache["searches"][term]["rows"]:
            if len(picked) == PER_SEARCH:
                break
            if row["id"] in taken or want not in builder.squash(row["title"]):
                continue
            picked.append(row)
            taken.add(row["id"])
        kept[number] = picked
    return kept


# --- Genius -------------------------------------------------------------------------------------


class CachedGenius:
    """`GeniusClient.search(q, limit=HITS_PER_QUERY)` behind a cache by query. The client reads any
    failure as an empty answer; a failed call is told by the warning it logs, and is not cached
    (a dropped connection would otherwise read as "Genius has nothing")."""

    def __init__(self) -> None:
        if GENIUS_JSON.exists():
            data = json.loads(GENIUS_JSON.read_text(encoding="utf-8"))
        else:
            data = {"calls": 0, "failed_calls": [], "answers": {}}
        self.calls: int = data["calls"]
        self.failed_calls: list[str] = data["failed_calls"]
        self.answers: dict[str, list[dict]] = data["answers"]
        self.calls_this_run = 0
        self._client: GeniusClient | None = None
        self._warned = False
        logger = logging.getLogger("pikaraoke.lib.genius")
        handler = logging.Handler(level=logging.WARNING)
        handler.emit = lambda record: setattr(self, "_warned", True)  # type: ignore[method-assign]
        logger.addHandler(handler)

    def _client_with_token(self) -> GeniusClient:
        if self._client is None:
            cfg = configparser.ConfigParser()
            cfg.read(Path.home() / ".pikaraoke" / "config.ini")
            token = next(
                (cfg[s]["genius_token"] for s in cfg.sections() if cfg[s].get("genius_token")), ""
            )
            if not token:
                stop("no genius_token in ~/.pikaraoke/config.ini")
            self._client = GeniusClient(api_token=token, timeout=15.0)
        return self._client

    def save(self) -> None:
        write_json(
            GENIUS_JSON,
            {"calls": self.calls, "failed_calls": self.failed_calls, "answers": self.answers},
        )

    def search(self, query: str) -> list[GeniusHit]:
        if query not in self.answers:
            for attempt in range(1, ATTEMPTS + 1):
                self._warned = False
                self.calls += 1
                self.calls_this_run += 1
                time.sleep(PACE_S)
                hits = self._client_with_token().search(query, limit=HITS_PER_QUERY)
                if not self._warned:
                    break
                self.failed_calls.append(query)
                self.save()
                if attempt == ATTEMPTS:
                    stop(f"Genius failed {ATTEMPTS} times for {query!r}")
                time.sleep(BACKOFF_S * attempt)
            self.answers[query] = [asdict(h) for h in hits]
            if self.calls_this_run % 10 == 0:
                self.save()
        return [GeniusHit(**h) for h in self.answers[query]]


def read_video(genius: CachedGenius, row: dict, term: str) -> dict:
    """The search page's read of one video, and the same read with no typed term."""
    asked: list[str] = []

    def search(query: str) -> list[GeniusHit]:
        asked.append(query)
        return genius.search(query)

    def read(typed: str):
        asked.clear()
        found = find_song(
            search, row["title"], channel=row["channel"], typed=typed, max_calls=SEARCH_PAGE_CALLS
        )
        return found, list(asked)

    with_typed, queries = read(term)
    without_typed, plain_queries = read("")
    if queries[: len(plain_queries)] != plain_queries or len(queries) - len(plain_queries) > 1:
        stop(f"the typed run and the plain run disagree on {row['id']}: {queries} / {plain_queries}")
    return {
        "parsed": parse(row["title"], row["channel"]),
        "queries": queries,
        "typed_asked": len(queries) > len(plain_queries),
        "with_typed": with_typed,
        "without_typed": without_typed,
    }


# --- The sheet ----------------------------------------------------------------------------------


def one_line(text: str) -> str:
    return " ".join(text.split())


def hit_line(place: int, hit: GeniusHit, preselect: int | None) -> str:
    year = hit.year if hit.year else "no year"
    mark = "   <- PRESELECT" if hit.id == preselect else ""
    return f"  {place}. {hit.title} — {hit.artist} ({year}, {hit.views:,} views){mark}"


def hit_lines(found) -> list[str]:
    if not found.hits:
        return ["  (no hits)"]
    return [hit_line(i, h, found.preselect) for i, h in enumerate(found.hits, 1)]


def block(number: str, term: str, row: dict, read: dict) -> str:
    parsed = read["parsed"]
    snippet = one_line(row["description"])
    if len(snippet) > SNIPPET_CHARS:
        snippet = snippet[:SNIPPET_CHARS] + "…"
    queries = [
        f"  {i}. `{q}`" + ("   (the typed term)" if read["typed_asked"] and i == len(read["queries"]) else "")
        for i, q in enumerate(read["queries"], 1)
    ]
    lines = [
        f"### {number}",
        "",
        f"- YouTube title: {row['title']}",
        f"- Channel: {row['channel'] or '(none)'}",
        f"- ID: {row['id']}   Length: {row['duration'] or '(none)'}",
        f"- Description snippet: {snippet or '(none)'}",
        f"- Search: `{term}`",
        f"- Parsed: title={parsed.title!r} alts={list(parsed.alts)!r} artist={parsed.artist!r} "
        f"film={parsed.film!r} year={parsed.year!r} channel={parsed.channel!r} swap={parsed.swap!r}",
        "- Queries asked:",
        *queries,
        "- Hits:",
        *hit_lines(read["with_typed"]),
    ]
    if read["typed_asked"]:
        lines += ["- Hits without the typed term:", *hit_lines(read["without_typed"])]
    return "\n".join(lines) + "\n"


def sheet_text(
    cache: dict,
    kept: dict[int, list[dict]],
    reads: dict[str, dict],
    genius: CachedGenius,
    *,
    cut: bool,
) -> str:
    notes = [
        "| Search | Term | Rows | Kept | Attempts |",
        "|---|---|---|---|---|",
    ]
    for number, term, _carries, _kind in SEARCHES:
        search = cache["searches"][term]
        attempts = ", ".join(
            a.get("error") or f"{a['rows']} rows / {a['with_channel']} with channel"
            for a in search["attempts"]
        )
        notes.append(f"| {number} | {term} | {len(search['rows'])} | {len(kept[number])} | {attempts} |")
    blocks = [
        block(f"{number}.{k}", term, row, reads[row["id"]])
        for number, term, _carries, _kind in SEARCHES
        for k, row in enumerate(kept[number], 1)
    ]
    head = [
        "# GATE G sheet",
        "",
        f"Collected {cache['date']} at frozen HEAD `{cache['head']}` by `gate_g/collect.py`.",
        f"YouTube: `get_search_results(term, {PAGE_SIZE})` as `/search` runs it (the term quoted in",
        "the yt-dlp query, YouTube's order). Genius: `find_song` with the row's channel, the typed",
        f"term and {SEARCH_PAGE_CALLS} calls; `Hits` is that read, `Hits without the typed term` the same read",
        "with no typed term (shown only when the typed term was asked). A video's number is",
        "`search.place`. Hit form: `Title — artist line (year, views)`.",
        "",
        f"{sum(len(v) for v in kept.values())} videos from {len(SEARCHES)} searches; "
        f"{genius.calls} Genius calls ({len(genius.failed_calls)} failed), "
        f"{len(genius.answers)} distinct queries.",
        "",
        *(cut_note(kept) if cut else []),
        *notes,
        "",
    ]
    return "\n".join(head) + "\n" + "\n".join(blocks)


def cut_note(kept: dict[int, list[dict]]) -> list[str]:
    """The sheet's header lines saying which snippets had lyric text cut."""
    cut = [
        f"{number}.{k}"
        for number, *_ in SEARCHES
        for k, row in enumerate(kept[number], 1)
        if row["id"] in LYRIC_SPANS
    ]
    return [
        "Description snippets are YouTube's (140 characters at most). No lyric text is committed:",
        f"in {', '.join(cut)} the lyric text was cut out and marked `{CUT_MARK}`. The sheet",
        f"with every snippet whole is in `~/probes/{RAW_DIR.name}/sheet.md`, uncommitted.",
        "",
    ]


VERDICTS_HEAD = """# GATE G verdicts

Filled by the judge (plans/genius-search-spec.md, "What is read by eye"). One row per video in
the sheet's order; a row read as not a song, or unsure, goes in `what` and is left out of every
count.

- `what`: the song and its recording (an act's own upload, a cover of whose song, a film cast and
  its year, a stage cast, a pop single, a dub), or not a song, or unsure.
- `first`: right / right song, wrong recording / wrong song / no hits.
- `listed`: the right hit's place among the hits, or none.
- `preselect`: none / right / wrong.
- `typed`: not asked / no change / helped / hurt.

| # | what | first | listed | preselect | typed |
|---|---|---|---|---|---|
"""


def main() -> None:
    cache = load_youtube()
    kept = select(cache)
    committed = committed_cache(cache, kept)
    committed_kept = select(committed)
    if {n: [r["id"] for r in v] for n, v in committed_kept.items()} != {
        n: [r["id"] for r in v] for n, v in kept.items()
    }:
        stop("the committed cache selects other videos than the raw one")
    write_json(YOUTUBE_JSON, committed)
    genius = CachedGenius()
    reads: dict[str, dict] = {}
    try:
        for number, term, _carries, _kind in SEARCHES:
            for row in kept[number]:
                reads[row["id"]] = read_video(genius, row, term)
            print(f"Genius, search {number}: {len(kept[number])} videos", flush=True)
    finally:
        genius.save()
    SHEET.write_text(sheet_text(committed, committed_kept, reads, genius, cut=True), encoding="utf-8")
    if RAW_YOUTUBE.exists():  # else `cache` is the committed one and has no whole snippets to show
        RAW_SHEET.write_text(sheet_text(cache, kept, reads, genius, cut=False), encoding="utf-8")
    rows = [f"| {n}.{k} | | | | | |" for n, *_ in SEARCHES for k, _ in enumerate(kept[n], 1)]
    VERDICTS.write_text(VERDICTS_HEAD + "\n".join(rows) + "\n", encoding="utf-8")
    short = [n for n, *_ in SEARCHES if len(kept[n]) < PER_SEARCH]
    print(f"videos {sum(len(v) for v in kept.values())}; searches short of four: {short}")
    print(f"Genius calls: {genius.calls} in all, {genius.calls_this_run} this run, "
          f"{len(genius.failed_calls)} failed; {len(genius.answers)} distinct queries")


if __name__ == "__main__":
    main()
