"""Tests for the Genius query module.

``tests/unit/data/genius_search`` was frozen from the evaluation prototype and its cached Genius
answers: per video title, what it parses into and, for each run, the queries asked, the ids of
the hits in order and the preselect. The tests replay those rows through a fake ``search`` that
raises on any query the frozen run did not ask, so an extra call fails too. No network is used.
"""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from pikaraoke.lib import genius_query as gq
from pikaraoke.lib.genius import GeniusHit

DATA = Path(__file__).parent / "data" / "genius_search"


def _read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def library() -> list[dict]:
    return _read_jsonl("library.jsonl")


@pytest.fixture(scope="module")
def rows(library) -> list[dict]:
    return library + _read_jsonl("unseen.jsonl")


@pytest.fixture(scope="module")
def answers() -> dict[str, list[GeniusHit]]:
    raw = json.loads((DATA / "answers.json").read_text(encoding="utf-8"))
    return {q: [GeniusHit(**h) for h in hits] for q, hits in raw.items()}


class FakeSearch:
    """Answers from a table, remembers what was asked, and fails on a query not in the table."""

    def __init__(self, table: dict[str, list[GeniusHit]]):
        self.table = table
        self.asked: list[str] = []

    def __call__(self, query: str) -> list[GeniusHit]:
        self.asked.append(query)
        return self.table[query]


def _replay(row: dict, run: str, answers) -> tuple[FakeSearch, gq.Found]:
    """The frozen run again: with the channel it is three calls, without it two."""
    with_channel = run == "with_channel"
    channel = row["channel"] if with_channel else ""
    calls = gq.SEARCH_PAGE_CALLS if with_channel else gq.LIBRARY_CALLS
    search = FakeSearch(answers)
    return search, gq.find_song(search, row["yt_title"], channel=channel, max_calls=calls)


def _hit(id_: int, title: str, artist: str, *, views: int = 1000) -> GeniusHit:
    return GeniusHit(id=id_, title=title, artist=artist, primary_artist=artist, views=views)


# --- The frozen fixtures ------------------------------------------------------------------------


def test_every_title_parses_into_its_frozen_parts(rows):
    wrong = []
    for row in rows:
        got = asdict(gq.parse(row["yt_title"], row["channel"]))
        assert got.pop("raw") == row["yt_title"]
        got["alts"] = list(got["alts"])
        if got != row["parsed"]:
            wrong.append(f"{row['yt_title']!r}: {got} != {row['parsed']}")
    assert not wrong, "\n".join(wrong[:5])


def test_every_channel_reads_as_its_frozen_act(rows):
    wrong = [r["channel"] for r in rows if gq.channel_name(r["channel"]) != r["parsed"]["channel"]]
    assert len(rows) == 382
    assert not wrong, wrong[:5]


@pytest.mark.parametrize("run", ["with_channel", "no_channel"])
def test_every_run_asks_the_frozen_queries_and_gives_the_frozen_order(run, rows, answers):
    wrong, count = [], 0
    for row in (r for r in rows if run in r):
        count += 1
        search, found = _replay(row, run, answers)
        got = (search.asked, [h.id for h in found.hits], found.preselect)
        want = (row[run]["queries"], row[run]["hits"], row[run]["preselect"])
        if got != want:
            wrong.append(f"{row['yt_title']!r}: {got} != {want}")
    assert count == (382 if run == "with_channel" else 206)
    assert not wrong, "\n".join(wrong[:5])


# --- Known holes and the rows the order must keep right -----------------------------------------

# First hits the order gets wrong, by eye, on the library's 206 titles. None is preselected: the
# year and artist line the pages show let the person tell them apart. Each is pinned as it is
# today, so a change that moves one is seen. (video id, first hit's id, what that hit is, where
# the right page is, as (hit id, place)).
KNOWN_HOLES = {
    "camp_rock_2_its_on": ("fO4BmrVjqjM", 5842, "Eazy-E, 1993", (2385215, 5)),
    "lion_king_can_you_feel_the_love_tonight": ("25QyCxVkXwQ", 1743107, "1997 Broadway cast", None),
    "lion_king_hakuna_matata": ("fwLxDUQBdEg", 1743090, "1997 Broadway cast", None),
    "outsiders_stay_gold": ("XzbHPqULtdA", 5602926, "Jun Matsumoto, 2014", (10279784, 4)),
    "wicked_popular": ("22QYya-LGDY", 9152241, "The Weeknd & Madonna, 2023", None),
    "wicked_what_is_this_feeling": ("amgPXKrFZVg", 657847, "the 2003 stage recording", None),
    "nsync_thinking_of_you": ("PodgxWsZw9s", 9853604, "a version page, no views", None),
}

# The other way round: first hits that are right and that some order which fixes the Lion King
# pair loses (Savages and Take Me or Leave Me when the artist-line levels go; the KPop Demon
# Hunters songs under every order tried).
KEPT_RIGHT = {
    "savages": ("1YiAzyCzZzw", 578649),
    "take_me_or_leave_me": ("DcbEr7Cd_Cc", 4246125),
    "kpop_golden": ("yebNIHKAC4A", 12026309),
    "kpop_soda_pop": ("983bBbJx0Mk", 12026311),
    "kpop_takedown": ("j5itLHDMJsE", 11872003),
    "kpop_your_idol": ("fGyTN5UjnL4", 12026313),
}


def _library_run(library, answers, video_id: str) -> gq.Found:
    row = next(r for r in library if r["id"] == video_id)
    return _replay(row, "with_channel", answers)[1]


@pytest.mark.parametrize("name", KNOWN_HOLES)
def test_known_hole_is_pinned_as_it_is(name, library, answers):
    video_id, first_id, _what, right = KNOWN_HOLES[name]
    found = _library_run(library, answers, video_id)
    assert found.hits[0].id == first_id
    assert found.preselect is None
    if right:
        hit_id, place = right
        assert found.hits[place - 1].id == hit_id


@pytest.mark.parametrize("name", KEPT_RIGHT)
def test_row_the_order_must_keep_right(name, library, answers):
    video_id, first_id = KEPT_RIGHT[name]
    assert _library_run(library, answers, video_id).hits[0].id == first_id


# --- Reading titles -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,query",
    [
        # as YouTube titles are saved: '/' and '|' as '_', '"' as ''', ':' as ' -'
        (
            "Cast of Camp Rock 2 - It's On (From 'Camp Rock 2 - The Final Jam'_Sing-Along)",
            "Cast of Camp Rock 2 It's On",
        ),
        (
            "'Golden' Official Lyric Video _ KPop Demon Hunters _ Sony Animation",
            "KPop Demon Hunters Golden",
        ),
        # as the library names a song once it is renamed
        ("Adele - Rolling in the Deep", "Adele Rolling in the Deep"),
        ("Titanic (1997) - My Heart Will Go On", "Titanic My Heart Will Go On"),
        ("Celine Dion - My Heart Will Go On (Titanic, 1997)", "Celine Dion My Heart Will Go On"),
        # nothing reads: the text itself
        ("Official Video", "Official Video"),
    ],
)
def test_start_query_is_the_first_query_of_the_ladder(text, query):
    assert gq.start_query(text) == query


def test_channel_name_keeps_an_act_and_drops_a_studio():
    assert gq.channel_name("BackstreetBoysVEVO") == "Backstreet Boys"
    assert gq.channel_name("Adele - Topic") == "Adele"
    assert gq.channel_name("Disney Music VEVO") == ""
    assert gq.channel_name("") == ""


def test_the_channel_stands_in_for_the_act_a_title_does_not_name():
    parsed = gq.parse("Bohemian Rhapsody (Official Video)", "QueenVEVO")
    assert gq.ladder(parsed) == ["Queen Bohemian Rhapsody", "Bohemian Rhapsody"]


# --- find_song ----------------------------------------------------------------------------------

QUEEN = (
    "Queen - Bohemian Rhapsody"  # ladder: 'Queen Bohemian Rhapsody', 'Bohemian Rhapsody', 'Queen'
)


def test_a_sure_first_hit_is_preselected_and_stops_the_ladder():
    search = FakeSearch({"Queen Bohemian Rhapsody": [_hit(1, "Bohemian Rhapsody", "Queen")]})
    found = gq.find_song(search, QUEEN, max_calls=3)
    assert search.asked == ["Queen Bohemian Rhapsody"]
    assert (found.preselect, found.query) == (1, "Queen Bohemian Rhapsody")


def test_a_hit_on_a_page_nobody_reads_is_not_preselected():
    table = {
        q: [_hit(1, "Bohemian Rhapsody", "Queen", views=0)] for q in gq.ladder(gq.parse(QUEEN))
    }
    search = FakeSearch(table)
    found = gq.find_song(search, QUEEN, max_calls=3)
    assert len(search.asked) == 3
    assert (found.hits[0].id, found.preselect) == (1, None)


def test_at_most_eight_hits_are_kept():
    hits = [_hit(i, "Bohemian Rhapsody", "Someone", views=i) for i in range(1, 13)]
    found = gq.find_song(FakeSearch({"Bohemian Rhapsody": hits}), "Bohemian Rhapsody", max_calls=2)
    assert [h.id for h in found.hits] == [12, 11, 10, 9, 8, 7, 6, 5]


def test_a_title_with_nothing_that_reads_asks_the_title_as_its_box_shows_it():
    hits = [_hit(1, "Official Video", "Someone", views=0)]
    search = FakeSearch({"Official Video": hits, "official video someone": []})
    found = gq.find_song(search, "  Official Video ", typed="official video someone", max_calls=3)
    assert search.asked == ["Official Video", "official video someone"]
    assert search.asked[0] == gq.start_query("  Official Video ")
    assert ([h.id for h in found.hits], found.preselect) == ([1], None)


@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_title_asks_nothing(text):
    search = FakeSearch({})
    found = gq.find_song(search, text, max_calls=3)
    assert (search.asked, found.hits, found.preselect) == ([], [], None)
    assert gq.start_query(text) == ""


# --- The typed term -----------------------------------------------------------------------------

TITLE_ONLY = "Bohemian Rhapsody"  # ladder: 'Bohemian Rhapsody'; never sure, no act is named


def test_the_typed_term_is_asked_last_when_nothing_matched_for_sure():
    search = FakeSearch({TITLE_ONLY: [], "bohemian rhapsody queen": []})
    gq.find_song(search, TITLE_ONLY, typed="bohemian rhapsody queen", max_calls=3)
    assert search.asked == [TITLE_ONLY, "bohemian rhapsody queen"]


def test_the_typed_term_is_not_asked_after_a_sure_match():
    search = FakeSearch({"Queen Bohemian Rhapsody": [_hit(1, "Bohemian Rhapsody", "Queen")]})
    gq.find_song(search, QUEEN, typed="queen bohemian rhapsody lyrics", max_calls=3)
    assert search.asked == ["Queen Bohemian Rhapsody"]


def test_the_typed_term_is_not_asked_past_the_call_limit():
    unsure = [_hit(1, "Bohemian Rhapsody", "Queen", views=0)]
    table = {q: unsure for q in gq.ladder(gq.parse(QUEEN))}
    search = FakeSearch(table)
    gq.find_song(search, QUEEN, typed="not in the table", max_calls=3)
    assert len(search.asked) == 3 and "not in the table" not in search.asked
    search = FakeSearch({TITLE_ONLY: []})
    gq.find_song(search, TITLE_ONLY, typed="not in the table", max_calls=1)
    assert search.asked == [TITLE_ONLY]


def test_the_typed_term_is_skipped_when_it_rewords_a_query_already_asked():
    search = FakeSearch({TITLE_ONLY: []})
    gq.find_song(search, TITLE_ONLY, typed="  RHAPSODY, bohemian! ", max_calls=3)
    assert search.asked == [TITLE_ONLY]


@pytest.mark.parametrize("typed", ["", "   ", "?!"])
def test_a_typed_term_with_no_words_is_not_asked(typed):
    search = FakeSearch({TITLE_ONLY: []})
    gq.find_song(search, TITLE_ONLY, typed=typed, max_calls=3)
    assert search.asked == [TITLE_ONLY]


def test_the_typed_terms_hits_merge_and_can_be_first():
    unread = _hit(1, "Bohemian Rhapsody", "Queen", views=0)
    read = _hit(2, "Bohemian Rhapsody", "Queen", views=900)
    table = {q: [unread] for q in gq.ladder(gq.parse(QUEEN))}
    table["queen bohemian rhapsody lyrics"] = [unread, read]
    found = gq.find_song(
        FakeSearch(table), QUEEN, typed="queen bohemian rhapsody lyrics", max_calls=4
    )
    assert [h.id for h in found.hits] == [2, 1]  # merged by id, the typed term's page first
    assert found.preselect == 2
