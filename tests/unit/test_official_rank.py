"""Tests for lifting an original act's official uploads to the top of a search.

The fixtures are real ``ytsearch`` captures (``tests/unit/data/youtube_search``): 14 from
2026-11-08, 30 from 2026-11-11, six held-out searches from 2026-11-16 and 20 searches for an
act's name alone from 2026-11-27, frozen because YouTube's live results differ from day to day.
Each is loaded through ``_parse_search_line``, so these tests also cover parsing a real yt-dlp
row. The expected tables were read off the captures, ranking their first page.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from pikaraoke.lib.official_rank import (
    Acts,
    _named_song,
    official_first,
    official_kind,
    read_first_page,
)
from pikaraoke.lib.youtube_dl import SearchResult, _parse_search_line

_FIXTURES = Path(__file__).parent / "data" / "youtube_search"

# The first page of every capture: the rows the app ranks and votes over.
_FIRST_PAGE = 30

# query, the originals the vote picks, official videos in lifted order, official audio in
# YouTube's order (it is lifted only when no video is)
_LIFTED = [
    ("bad guy", ("billieeilish",), ["DyDfgMOUjCI"], ["2pnXjQCegVc"]),
    ("bohemian rhapsody", ("queen",), ["fJ9rUzIMcZQ"], ["0TF3hFevWE8"]),
    ("dancing queen", ("abba",), ["xFrGuyw1V8s"], ["P5AqvKYYQEE"]),
    ("defying gravity", ("cynthiaerivo",), [], ["HxkLt1GXVsw"]),
    ("dont stop believin", ("journey",), [], ["_wXLKQCTuD0"]),
    ("hallelujah", ("leonardcohen",), [], ["ttEMYvpoR-k"]),
    ("hello", ("adele",), ["YQHsXMglC9A"], ["T1tl66trXTQ"]),
    ("let it go frozen", ("idinamenzel",), ["YVVTZgwYwVo"], ["FnpJBkAMk44"]),
    (
        "never gonna give you up",
        ("rickastley",),
        ["dQw4w9WgXcQ", "LLFhKaqnWwk", "RrESvSRNpeo"],
        ["3BFTio5296w"],
    ),
    ("queen bohemian rhapsody", ("queen",), ["fJ9rUzIMcZQ"], ["0TF3hFevWE8"]),
    ("rolling in the deep", ("adele",), ["rYEDA3JcQqw"], ["bDtjO-R0QSo"]),
    ("seasons of love rent", ("anthonyrapp",), [], ["1xGUTW3C3gE", "HLEPfySbfxQ"]),
    ("shallow lady gaga", ("ladygaga",), ["bo_efYhYU2A"], ["BpIf43m2ZQI"]),
    ("someone like you", ("adele",), ["hLQl3WQQoQ0"], ["22c3_LoIfZQ"]),
    ("bts butter", ("bts",), ["WMweEpGlu_U"], []),
    ("jung kook seven", ("jungkook",), ["QU9c0053UAU"], ["Vs64cZbeY88", "zj0O6-YvLhg"]),
    (
        "a whole new world aladdin",
        ("menamassoud", "menamassoudnaomiscott", "naomiscott"),
        ["eitDnP0_83k"],
        ["atc8RAtl-Ms"],
    ),
    (
        "part of your world",
        ("jodibenson", "thelittlemermaid"),
        ["SXKlJuO07eM"],
        ["sg1Y6Vxl6Nk", "ZYcV5oXlccc", "totRu4FjI74"],
    ),
    ("speechless aladdin", ("naomiscott",), ["mw5VIEIvuMI"], ["DwTogmKwYWo", "J8CVHdMvv30"]),
    ("how far ill go moana", ("auliicravalho",), ["cPAbx5kgCJo"], ["keGr19WWwoA"]),
    ("circle of life lion king", ("thelionking",), [], []),
    ("youre welcome moana", ("dwaynejohnson", "moana"), ["79DijItQXMM"], ["khg-OuAtt5E"]),
    ("backstreet boys shape of my heart", ("backstreetboys",), ["OT5msu-dap8"], []),
    ("john legend all of me", ("johnlegend",), ["450p7goxZqg", "xwsYvBYZcx4"], []),
    (
        "colbie caillat realize",
        ("colbiecaillat",),
        ["GlZxZ2n2zpw", "pwpHhN-vtRI", "u5Exxrl7frA"],
        [],
    ),
    (
        "kelly clarkson because of you",
        ("kellyclarkson",),
        ["Ra-Om7UMSJc", "o0oenkCT8EY"],
        ["C-IgZrOsEag"],
    ),
    ("britney spears oops i did it again", ("britneyspears",), ["CduA0TULnow"], ["OO0aTOIU_3w"]),
    ("ne-yo so sick", ("neyo",), ["IxszlJppRQI", "ub3y1Baw0ak"], []),
    ("eminem lose yourself", ("eminem",), ["xFYQQPAOz7Y"], []),
    (
        "justin timberlake suit and tie",
        ("justintimberlake",),
        ["IsUsVbTj2AY", "7tWvTW16atE"],
        ["cJzRZ0T5ewc", "0S0vamqBlek"],
    ),
    ("adele someone like you", ("adele",), ["hLQl3WQQoQ0"], ["22c3_LoIfZQ"]),
    ("tenacious d tribute", ("tenaciousd",), ["_lK4cX5xGiQ"], []),
    ("ed sheeran perfect", ("edsheeran",), ["2Vv-BfVoq4g"], ["817P8W8-mGE"]),
    (
        "backstreet boys i want it that way",
        ("backstreetboys",),
        ["4fndeDfaWCg", "VVB6FI8QTFg", "mAGGPgxl6qU", "GJhTjyc7A3Y"],
        ["z6Wq59qrdB0", "-aKJE1lanQk"],
    ),
    ("because of you", ("kellyclarkson",), ["Ra-Om7UMSJc", "o0oenkCT8EY"], ["C-IgZrOsEag"]),
    ("perfect", ("edsheeran",), ["2Vv-BfVoq4g"], ["817P8W8-mGE"]),
    ("let it go", ("idinamenzel",), ["YVVTZgwYwVo"], ["FnpJBkAMk44"]),
    ("mirrors", ("justintimberlake",), ["uuZE_IRwLNI"], ["U41KPUfOSFk"]),
    ("tribute", (), [], []),
    ("the lonely island threw it on the ground", ("thelonelyisland",), ["gAYL5H46QnQ"], []),
    ("vitamin c graduation", ("vitaminc",), [], []),
    ("the philosopher kings cry", ("thephilosopherkings",), ["EUW0eDhKoxw"], []),
    ("golden kpop demon hunters", ("huntrx",), [], []),
    (
        "celine dion my heart will go on",
        ("celinedion",),
        ["9bFHsd3o1w0", "bf-HGyke89Y"],
        ["mNsm2P0l_7Y", "cJnSrovvM74"],
    ),
    ("adele send my love", ("adele",), ["fk4BbF7B29w"], ["Fq-AHPOshKc"]),
    (
        "under the sea little mermaid",
        ("samuelewright", "underthesea"),
        ["GC_mV1IpjWA"],
        ["ChNJ_FMtSnk", "b32vFD5Acrc", "ZhFwcueYEKE"],
    ),
    ("we dont talk about bruno encanto", ("wedonttalkaboutbruno",), [], []),
    ("do you want to build a snowman", ("frozen",), [], []),
    ("justin timberlake sexyback", ("justintimberlake",), ["3gOHvDP_vCs", "-oqXwnXjgDE"], []),
    ("be our guest beauty and the beast", ("thebeast",), [], []),
]

# query -> another act's videos on a label channel (a film song's second cast), in YouTube's
# order. They lift after the originals' videos; every other fixture has none.
_OTHER_ACTS_VIDEOS = {
    "part of your world": ["kf7Dss2gCe0"],
    "how far ill go moana": ["_nVJl4-o2XA", "IhZI-a1eiCg"],
    "circle of life lion king": ["GibiNy4d4gc", "IwH9YvhPN7c"],
    "youre welcome moana": ["0DLzyvT4eUo"],
    "hello": ["LnET4RKXx5k"],
    "under the sea little mermaid": ["Wbv_huklr5E", "Uki_W4nYbr4"],
    "we dont talk about bruno encanto": ["bvWRMAU6V-c", "-QOSz9G1GnY"],
    "do you want to build a snowman": ["1APv9t_LyOY"],
}

# query, id of a row that looks official but must stay where YouTube put it, without a badge
_STAYS_PUT = [
    pytest.param("bohemian rhapsody", "ojRj2JK5oCI", id="cover-artists-own-video"),
    pytest.param("queen bohemian rhapsody", "LlPcnOjSByU", id="unverified-reupload"),
    pytest.param("queen bohemian rhapsody", "rY0WxgSXdEE", id="another-song"),
    pytest.param("hello", "mHONNcZbwDY", id="another-artist-same-title"),
    pytest.param("dancing queen", "-sVB91NTa4A", id="official-lyric-video"),
    pytest.param("rolling in the deep", "tW626Q6CFcI", id="acapella-on-page-2"),
    pytest.param("bts butter", "HbkBVxU5K5A", id="show-performance"),
    pytest.param("bts butter", "5dWxvUcEUEY", id="performance-rehearsal"),
    pytest.param("jung kook seven", "1QYBiNRu1ok", id="official-performance-video"),
    pytest.param("backstreet boys shape of my heart", "v1Q5SsHIuBY", id="arena-concert"),
    pytest.param("john legend all of me", "ftGQLvUwzjY", id="vevo-go-shows"),
    pytest.param("colbie caillat realize", "jDt2u2eJk3Q", id="aol-sessions"),
    pytest.param("kelly clarkson because of you", "P8dtX_t9mJc", id="soundcheck"),
    pytest.param("britney spears oops i did it again", "MHfCJT6hkZ4", id="vevo-footnotes"),
    pytest.param("ne-yo so sick", "XLtinWelxkE", id="making-of"),
    pytest.param("eminem lose yourself", "jNYR1ioecJY", id="fan-channel-live-set"),
    pytest.param("justin timberlake suit and tie", "8fWBQtknJdA", id="reupload-by-title"),
    pytest.param("adele someone like you", "il-NdjTtUAI", id="cover-music-video"),
    pytest.param("tenacious d tribute", "W4uqbxvOK2A", id="fan-compilation"),
    pytest.param("tenacious d tribute", "qSf6JznfdkY", id="demo-version"),
    pytest.param("ed sheeran perfect", "eiDiKwbGfIY", id="perfect-symphony"),
    pytest.param("ed sheeran perfect", "fgcwFILyTVo", id="backstage-rehearsal"),
    pytest.param("backstreet boys i want it that way", "nUhVJBCpPSM", id="cover-art-track"),
    pytest.param("part of your world", "azpDUgf2RLc", id="cover-art-track-of-a-film-song"),
    pytest.param("youre welcome moana", "5CQLqMebytM", id="fan-channel-music-video"),
    pytest.param("vitamin c graduation", "tz_NxOF7RB4", id="label-only-by-title"),
    pytest.param("golden kpop demon hunters", "hohuFW0zQUw", id="regional-channel-music-video"),
    pytest.param("adele send my love", "0put0_a--Ng", id="another-song-on-a-label"),
    pytest.param("adele send my love", "9IzKueQ2ZxY", id="another-song-as-art-track"),
    pytest.param("do you want to build a snowman", "-9ZWF8vxmzM", id="behind-the-scenes"),
    pytest.param("do you want to build a snowman", "KKP0Txebobg", id="stage-cast-audio-only"),
    pytest.param("be our guest beauty and the beast", "Lt1Fck9DDp8", id="fan-channel-typo-title"),
]

_SIXTY_ROW_FIXTURES = ["bohemian rhapsody", "hallelujah", "let it go frozen", "rolling in the deep"]

# The 2026-11-27 captures: a search for an act's name alone. Query, whether the page is read as
# an act search, the originals the vote picks, then the 1-based lines of the capture that are
# official videos in lifted order and official audio in YouTube's order (lifted only when no
# video is). "bts" (an act with no channel of its own on the page) and the film names "frozen"
# and "moana" are not act searches and are read as they always were.
_ACT_SEARCHES = [
    (
        "abba",
        True,
        ("abba",),
        [2, 3, 5, 6, 7, 10, 11, 12, 16, 17, 18, 19, 20, 21, 23, 25, 27, 28],
        [22, 26],
    ),
    ("adele", True, ("adele",), [2, 6, 12, 15, 18, 19, 23, 28], [14, 16, 30]),
    (
        "backstreet boys",
        True,
        ("backstreetboys",),
        [3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 21, 23, 24, 25, 26, 30],
        [27],
    ),
    ("blackpink", True, ("blackpink",), [3, 5, 6, 8, 11, 12, 14, 16, 17, 19, 21, 24, 28], []),
    ("bts", False, ("bts",), [1, 4, 7, 12, 13, 14, 15, 18, 20, 21, 22, 25, 30], []),
    (
        "celine dion",
        True,
        ("celinedion",),
        [1, 2, 11, 12, 14, 15, 16, 18, 20, 28, 29],
        [25, 26, 27],
    ),
    (
        "ed sheeran",
        True,
        ("edsheeran",),
        [2, 3, 5, 7, 8, 9, 12, 13, 14, 15, 18, 19, 20, 22, 23, 27, 28, 29],
        [],
    ),
    (
        "eminem",
        True,
        ("eminem",),
        [
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            9,
            10,
            12,
            13,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            25,
            27,
            28,
            29,
            30,
        ],
        [],
    ),
    ("frozen", False, ("idinamenzel",), [], []),
    ("idina menzel", True, ("idinamenzel",), [7, 12, 14, 17, 30], []),
    ("journey", True, ("journey",), [3, 6, 8, 9, 10, 11, 13, 14, 15, 19, 23, 28], [2, 20, 21, 24]),
    (
        "justin timberlake",
        True,
        ("justintimberlake",),
        [8, 9, 10, 12, 13, 14, 15, 16, 18, 19, 21, 22, 25, 27, 29, 30],
        [17],
    ),
    (
        "lady gaga",
        True,
        ("ladygaga",),
        [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 19, 20, 21, 22, 25, 26, 27, 28, 30],
        [13, 17],
    ),
    ("moana", False, ("auliicravalho", "dwaynejohnson"), [11], []),
    (
        "queen",
        True,
        ("queen",),
        [2, 3, 7, 10, 11, 12, 13, 15, 16, 18, 20, 21, 24, 25, 27, 28, 29, 30],
        [],
    ),
    (
        "rick astley",
        True,
        ("rickastley",),
        [1, 2, 7, 9, 10, 11, 12, 13, 14, 15, 17, 21, 22, 23, 24, 26, 27],
        [25],
    ),
    (
        "simon and garfunkel",
        True,
        ("simonandgarfunkel",),
        [],
        [8, 9, 11, 12, 13, 15, 16, 17, 18, 20, 22, 23, 24, 25, 26, 29],
    ),
    (
        "taylor swift",
        True,
        ("taylorswift",),
        [3, 6, 9, 10, 11, 12, 13, 15, 18, 19, 21, 22, 23, 24, 25, 26, 27, 29],
        [],
    ),
    (
        "the beatles",
        True,
        ("thebeatles",),
        [8, 11, 12, 13, 14, 15, 17, 20, 21, 23, 24, 25, 26, 27],
        [9, 16],
    ),
    (
        "the weeknd",
        True,
        ("theweeknd",),
        [1, 2, 3, 4, 6, 7, 8, 11, 14, 15, 16, 17, 18, 20, 23, 25, 26, 30],
        [9, 21, 24, 27, 28, 29],
    ),
]


def _raw(query: str) -> list[SearchResult]:
    """Every row of the capture, channel rows included."""
    path = _FIXTURES / f"{query.replace(' ', '_')}.jsonl"
    results = [_parse_search_line(line) for line in path.read_text().splitlines()]
    assert None not in results, f"{path.name} has a row the parser drops"
    return results


def _load(query: str) -> list[SearchResult]:
    """The capture's videos: the routes drop a channel row before they rank."""
    return [row for row in _raw(query) if row.is_video]


def _at(query: str, positions: list[int]) -> list[str]:
    """The IDs at 1-based lines of the raw capture, counted before a channel row is dropped."""
    raw = _raw(query)
    return [raw[position - 1].id for position in positions]


def _ids(ranked) -> list[str]:
    return [result.id for result, _ in ranked]


def _row(
    title: str, channel: str = "A Channel", verified: bool = True, description: str = ""
) -> SearchResult:
    return SearchResult(
        title=title,
        url="https://youtu.be/aaaaaaaaaaa",
        id="aaaaaaaaaaa",
        channel=channel,
        duration="3:00",
        channel_verified=verified,
        description=description,
    )


def _art(title: str, act: str = "Alpha") -> SearchResult:
    """A label-distributed art track, which YouTube files on the act's "- Topic" channel."""
    return _row(title, channel=f"{act} - Topic", verified=False)


def _unrelated(title: str = "Unrelated upload") -> SearchResult:
    return _row(title, verified=False)


def _kind(row: SearchResult, query: str = "some song", vote: tuple = ()):
    """The kind ``row`` gets on a page of itself and the rows that vote for Alpha (two art tracks
    unless ``vote`` says otherwise)."""
    page = [row, *(vote or (_art("Some Song"), _art("Some Song")))]
    return official_kind(row, query, read_first_page(page, query))


def _originals(rows: list[SearchResult], query: str = "some song") -> frozenset[str]:
    return read_first_page(rows, query).originals


def _titles(ranked) -> list[str]:
    return [result.title for result, _ in ranked]


# Fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, originals, videos, audio", _LIFTED, ids=[query for query, *_ in _LIFTED]
)
def test_lifts_the_official_videos_and_badges_every_official_upload(
    query, originals, videos, audio
):
    results = _load(query)[:_FIRST_PAGE]
    others = _OTHER_ACTS_VIDEOS.get(query, [])
    acts = read_first_page(results, query)

    ranked = official_first(results, query, acts)

    assert acts.originals == frozenset(originals)
    assert acts.has_video == bool(videos or others)
    lifted = videos + others or audio  # audio is lifted only where no video is
    assert _ids(ranked)[: len(lifted)] == lifted
    assert {result.id: kind for result, kind in ranked if kind} == {
        **dict.fromkeys(videos + others, "video"),
        **dict.fromkeys(audio, "audio"),
    }


@pytest.mark.parametrize(
    "query, originals, videos, audio", _LIFTED, ids=[query for query, *_ in _LIFTED]
)
def test_everything_not_lifted_keeps_youtubes_order(query, originals, videos, audio):
    results = _load(query)[:_FIRST_PAGE]
    lifted = videos + _OTHER_ACTS_VIDEOS.get(query, []) or audio

    ranked = official_first(results, query, read_first_page(results, query))

    assert _ids(ranked)[len(lifted) :] == [r.id for r in results if r.id not in lifted]


@pytest.mark.parametrize("query, video_id", _STAYS_PUT)
def test_an_upload_that_is_not_the_acts_record_is_not_badged(query, video_id):
    results = _load(query)
    acts = read_first_page(results[:_FIRST_PAGE], query)
    assert acts.originals  # else None would pass vacuously
    row = next(r for r in results if r.id == video_id)

    assert official_kind(row, query, acts) is None


@pytest.mark.parametrize("query", _SIXTY_ROW_FIXTURES)
def test_a_second_page_is_ranked_by_the_first_pages_vote_and_lifts_nothing(query):
    results = _load(query)
    assert len(results) == 2 * _FIRST_PAGE
    second_page = results[_FIRST_PAGE:]

    acts = read_first_page(results[:_FIRST_PAGE], query)

    assert acts.originals
    assert official_first(second_page, query, acts) == [(r, None) for r in second_page]


@pytest.mark.parametrize(
    "query, first_page_originals, all_rows_originals",
    [
        ("hallelujah", {"leonardcohen"}, {"oct2026"}),
        ("let it go frozen", {"idinamenzel"}, {"letitgo"}),
    ],
)
def test_the_vote_over_sixty_rows_drifts_so_it_is_taken_over_the_first_page(
    query, first_page_originals, all_rows_originals
):
    results = _load(query)

    assert read_first_page(results[:_FIRST_PAGE], query).originals == first_page_originals
    assert read_first_page(results, query).originals == all_rows_originals


# The vote (rules 1 and 2)
# ---------------------------------------------------------------------------


def test_a_tie_names_every_act_that_shares_the_most_credits():
    rows = [
        _row("Alpha - Some Song"),
        _row("Alpha - Some Song"),
        _row("Beta - Some Song"),
        _row("Beta - Some Song"),
    ]

    assert _originals(rows) == {"alpha", "beta"}


def test_one_trusted_credit_is_not_enough():
    assert _originals([_row("Alpha - Some Song")]) == frozenset()


def test_no_trusted_rows_names_no_one_and_changes_no_order():
    rows = [_row(f"Alpha - Some Song {i}", verified=False) for i in range(5)]
    acts = read_first_page(rows, "some song")

    assert acts == Acts()
    assert official_first(rows, "some song", acts) == [(r, None) for r in rows]


@pytest.mark.parametrize(
    "titles, originals",
    [
        pytest.param(
            ["Some Song - Alpha", "Some Song - Alpha"],
            {"alpha"},
            id="song-first-title-credits-right",
        ),
        pytest.param(
            ["Alpha ft. Beta - Some Song", "Alpha - Some Song", "Alpha & Beta - Some Song"],
            {"alpha"},
            id="collaborators-are-credited-separately",
        ),
        pytest.param(
            ["Featherstone - Some Song", "Featherstone - Some Song"],
            {"featherstone"},
            id="feat-inside-a-word-is-not-a-split",
        ),
        pytest.param(
            ["Alpha - Some Song (Official Video)", "Alpha - Some Song [HD]"],
            {"alpha"},
            id="bracketed-text-is-ignored",
        ),
    ],
)
def test_the_vote_reads_the_act_out_of_a_title(titles, originals):
    assert _originals([_row(title) for title in titles]) == originals


@pytest.mark.parametrize(
    "title, credited",
    [
        pytest.param("Alpha (Beta) 'Some Song' Official MV", {"alpha", "beta"}, id="bracket-alias"),
        pytest.param("[MV] Alpha 'Some Song'", {"alpha"}, id="square-bracket-before-the-quote"),
        pytest.param("Alpha “Some Song” Official", {"alpha"}, id="curly-quotes"),
        pytest.param("Alpha 'Some Song' (From \"Some Film\")", {"alpha"}, id="film-is-bracketed"),
        pytest.param('Some Song (From "Some Film")', {"gamma"}, id="film-quote-credits-no-one"),
        pytest.param("Don't Stop Me Now", {"gamma"}, id="apostrophe-is-no-quote"),
        pytest.param("'Some Song' Official MV", {"gamma"}, id="nothing-before-the-quote"),
        pytest.param("Don't Stop 'Til The End", {"gamma"}, id="a-quote-that-never-closes"),
        pytest.param("Zoé's Song, Zoé's Way", {"gamma"}, id="apostrophe-after-an-accent"),
        pytest.param("Alpha「Some Song」MUSIC VIDEO", {"alpha"}, id="corner-bracket-after-a-letter"),
        pytest.param('Some Song (From "Some Film"', {"gamma"}, id="unclosed-round-bracket"),
        pytest.param('Some Song [From "Some Film"', {"gamma"}, id="unclosed-square-bracket"),
    ],
)
def test_a_title_with_a_quoted_song_credits_the_text_before_the_quote(title, credited):
    assert _originals([_row(title, channel="Gamma")] * 2) == credited


@pytest.mark.parametrize(
    "query, band, song, originals",
    [
        pytest.param(
            "the sound of silence",
            "Simon & Garfunkel",
            "The Sound of Silence",
            {"simonandgarfunkel"},
            id="ampersand",
        ),
        pytest.param(
            "september earth wind and fire",
            "Earth, Wind & Fire",
            "September",
            {"earthwindandfire"},
            id="and-in-the-query-is-the-titles-ampersand",
        ),
        pytest.param(
            "lil nas x old town road", "Lil Nas X", "Old Town Road", {"lilnasx"}, id="x-in-the-name"
        ),
    ],
)
def test_a_band_named_like_a_collaboration_is_credited_whole(query, band, song, originals):
    rows = [
        _row(f"{band} - {song} (Official Video)", channel=band),
        _row(f"{band} - {song} (Official Audio)", channel=band),
        _row(song, channel=f"{band} - Topic", verified=False),
    ]
    acts = read_first_page(rows, query)

    assert acts.originals == originals
    assert [kind for _, kind in official_first(rows, query, acts)] == ["video", "audio", "audio"]


def test_the_song_with_a_tied_name_does_not_hide_the_other_originals_video():
    """ "Some Song - Film" art tracks tie the song's own name with Alpha in the vote; Alpha's video
    must still pass the song check, which strikes only the names the row itself credits."""
    page = [
        _row("Some Song - Film", channel="Gamma"),
        _row("Some Song - Film", channel="Gamma"),
        _row("Alpha - Some Song (from Film) (Official Video)", channel="AlphaVEVO"),
        _row("Alpha - Some Song (from Film) (Official Video)", channel="AlphaVEVO"),
    ]
    acts = read_first_page(page, "some song film")

    assert acts.originals == {"somesong", "alpha"}
    assert official_kind(page[2], "some song film", acts) == "video"


# Which row is the song (rule 6)
# ---------------------------------------------------------------------------


def test_a_song_word_inside_a_bracket_only_does_not_make_the_song():
    """ "Another One Bites the Dust (from Bohemian Rhapsody)" is not "bohemian rhapsody"."""
    title = "Alpha - Other Song (From Some Film)"

    assert _kind(_row(title, channel="Alpha"), "some film") is None
    assert _kind(_art(title), "some film") is None


def test_a_film_in_brackets_is_part_of_the_song_search():
    assert _kind(_row("Song (from Film)", channel="Alpha"), "song film") == "video"


def test_a_title_with_a_word_of_its_own_is_another_song_when_it_lacks_a_song_word():
    """ "Make You Feel My Love" is not "send my love": two of three words match, one is its own."""
    query = "alpha send my love"

    assert _kind(_row("Alpha - Make You Feel My Love (Official Video)", "Alpha"), query) is None
    assert _kind(_art("Make You Feel My Love"), query) is None
    assert _kind(_row("Alpha - Send My Love (Official Video)", "Alpha"), query) == "video"


def test_the_query_may_say_more_than_the_title_but_a_misspelt_word_lifts_nothing():
    art_track = _art("Some Long Song")
    video = _row("Alpha - Some Long Song (Official Video)", channel="Alpha")

    assert _kind(art_track, "alpha some long song film") == "audio"
    assert (
        _kind(_row("Alpha - Other Long Song (Official Video)", "Alpha"), "alpha some long song")
        is None
    )
    assert _kind(art_track, "alpha some long sogn") is None
    assert _kind(video, "alpha some long sogn") is None


# Whose upload, and from where (rules 3 and 7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "channel, kind",
    [
        pytest.param("Alpha", "video", id="own-channel"),
        pytest.param("AlphaMusic", "video", id="music-suffix"),
        pytest.param("AlphaVEVO", "video", id="vevo-suffix"),
        pytest.param("Alpha Fans United", None, id="fan-channel-is-not-the-acts"),
        pytest.param("Gamma Channel", None, id="verified-channel-of-someone-else"),
        pytest.param("Beta Records", "video", id="label-by-name"),
    ],
)
def test_a_video_must_come_from_the_act_or_a_label_by_name(channel, kind):
    row = _row("Alpha - Some Song (Official Video)", channel=channel)

    assert _kind(row) == kind


def test_a_verified_channel_is_no_label_however_the_title_reads_with_or_without_the_acts_own():
    reupload = _row("Alpha - Some Song (Official Music Video)", channel="Gamma Channel")
    own = _row("Alpha - Some Song (Official Video)", channel="Alpha")

    assert _kind(reupload) is None
    assert _kind(reupload, vote=(own, _art("Some Song"))) is None


def test_the_act_is_found_with_or_without_a_leading_the():
    row = _row("The Alpha - Some Song (Official Video)", channel="Alpha")
    vote = (_art("Some Song", "The Alpha"), _art("Some Song", "The Alpha"))

    assert _kind(row, vote=vote) == "video"


def test_an_unverified_channel_is_not_the_acts_own():
    assert _kind(_row("Alpha - Some Song (Official Video)", "Alpha", verified=False)) is None


def test_a_cover_art_track_is_its_channels_alone_whoever_its_title_credits():
    """Alpha's cover of a song, titled "Original Artist - Song", is Alpha's, not the original's."""
    cover = _art("Beta - Some Song", act="Alpha")
    vote = (_row("Beta - Some Song (Official Video)", channel="Beta"),) * 2

    acts = read_first_page([cover, *vote], "some song")

    assert acts.originals == {"beta"}
    assert official_kind(cover, "some song", acts) is None


def test_a_band_channel_that_adds_show_to_its_name_is_the_bands_own():
    """ "celebration kool and the gang": the vote finds the band split and whole, and the channel
    "KoolandthegangShow" is the band's."""
    query = "celebration kool and the gang"
    video = _row("Kool & The Gang - Celebration (Official Video)", channel="KoolandthegangShow")
    page = [_unrelated(), video, video]

    acts = read_first_page(page, query)

    assert acts.originals == {"kool", "thegang", "koolandthegang"}
    assert [kind for _, kind in official_first(page, query, acts)] == ["video", "video", None]


def test_a_channel_whose_name_reads_as_nothing_is_no_ones_own():
    """ "Official Music" strips to nothing, and so does the act "The" once its "the" is dropped."""
    rows = [_row("The 'Some Song' (Official Video)", channel="Official Music")] * 2

    acts = read_first_page(rows, "some song")

    assert acts.originals == {"the"}
    assert official_first(rows, "some song", acts) == [(r, None) for r in rows]


# Does it say what it is (rules 5, 8, 9)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bracket, kind",
    [
        pytest.param("(Official Video)", "video", id="official-video"),
        pytest.param("(Official HD Video)", "video", id="official-hd-video"),
        pytest.param("[Official MV]", "video", id="official-mv"),
        pytest.param("(Music Video)", "video", id="music-video"),
        pytest.param("[M/V]", "video", id="mv"),
        pytest.param("(2025 Version)", "video", id="version"),
        pytest.param("(Millennium 20 Edition)", "video", id="edition"),
        pytest.param("(Edit)", "video", id="edit"),
        pytest.param("(Someone Official)", None, id="a-bare-official-says-nothing"),
        pytest.param("(O2 Arena)", None, id="venue"),
        pytest.param("@ The Tonight Show", None, id="show"),
    ],
)
def test_a_video_with_more_than_act_and_song_must_say_what_it_is(bracket, kind):
    row = _row(f"Alpha - Some Song {bracket}", channel="Alpha")

    assert _kind(row) == kind


def test_a_bare_title_needs_no_explanation():
    assert _kind(_row("Alpha - Some Song", channel="Alpha")) == "video"


@pytest.mark.parametrize(
    "query, title, kind",
    [
        pytest.param("some song", "Alpha ft. Beta - Some Song", "video", id="a-guest-is-explained"),
        pytest.param(
            "some song", "Alpha ft. Beta - Some Song @ The Tonight Show", None, id="guest-first"
        ),
        pytest.param(
            "dance with me", "Alpha - Dance With Me - O2 Arena London 2019", None, id="with-in-song"
        ),
    ],
)
def test_a_guest_or_film_is_dropped_only_to_the_end_of_its_segment(query, title, kind):
    assert _kind(_row(title, channel="Alpha"), query) == kind


@pytest.mark.parametrize(
    "bracket",
    ["(Behind-the-Scenes)", "(The Making-Of)", "(Demo)", "(Performance)", "(MTV Unplugged)"],
)
def test_marks_hide_hyphens_and_the_new_words_exclude_a_row(bracket):
    row = _row(f"Alpha - Some Song {bracket} (Official Video)", channel="Alpha")

    assert _kind(row) is None


def test_the_records_own_title_explains_its_subtitle():
    row = _row("Alpha - Some Song (Its Subtitle)", channel="Alpha")
    titled_so = (_art("Alpha - Some Song (Its Subtitle)"), _art("Some Song"))
    titled_plain = (_art("Some Song"), _art("Some Song"))

    assert _kind(row, vote=titled_so) == "video"
    assert _kind(row, vote=titled_plain) is None


def test_audio_is_spared_the_what_is_it_test():
    audio = _row("Alpha - Some Song (O2 Arena Audio)", channel="Alpha")

    assert _kind(audio) == "audio"


@pytest.mark.parametrize(
    "query, title, channel, kind",
    [
        pytest.param(
            "live your life",
            "T.I. - Live Your Life ft. Rihanna (Official Video)",
            "T.I.",
            "video",
            id="mark-in-the-song-name",
        ),
        pytest.param(
            "live and let die",
            "Paul McCartney & Wings - Live And Let Die (Live)",
            "Paul McCartney",
            None,
            id="a-mark-beyond-the-song-name-still-excludes",
        ),
        pytest.param(
            "bohemian rhapsody live",
            "Queen - Bohemian Rhapsody (Live Aid 1985)",
            "Queen Official",
            "video",
            id="the-version-the-query-asks-for",
        ),
    ],
)
def test_only_marks_beyond_the_querys_exclude_a_row(query, title, channel, kind):
    row = _row(title, channel=channel)
    vote = (_row(title, channel=channel),) * 2

    assert _kind(row, query, vote=vote) == kind


# Other acts' videos (rule 11)
# ---------------------------------------------------------------------------


def _another_cast(channel: str = "Gamma Records") -> SearchResult:
    return _row("Beta - Some Song (Official Video)", channel=channel)


def test_another_acts_video_on_a_label_channel_lifts_after_the_originals_videos():
    original = _row("Alpha - Some Song (Official Video)", channel="Alpha")
    rows = [_unrelated(), _another_cast(), original, _art("Some Song"), _art("Some Song (Second)")]

    ranked = official_first(rows, "some song", read_first_page(rows, "some song"))

    assert _titles(ranked)[:3] == [original.title, rows[1].title, "Unrelated upload"]
    assert [kind for _, kind in ranked] == ["video", "video", None, "audio", "audio"]


def test_the_originals_audio_keeps_its_place_beside_another_acts_lifted_video():
    rows = [_unrelated(), _art("Some Song"), _art("Some Song (Second)"), _another_cast()]

    ranked = official_first(rows, "some song", read_first_page(rows, "some song"))

    assert _titles(ranked) == [rows[3].title, "Unrelated upload", "Some Song", "Some Song (Second)"]
    assert [kind for _, kind in ranked] == ["video", None, "audio", "audio"]


@pytest.mark.parametrize(
    "channel, kind",
    [
        pytest.param("Gamma Records", "video", id="label-by-name"),
        pytest.param("GammaVEVO", "video", id="vevo-label"),
        pytest.param("Beta", None, id="the-acts-own-channel"),
        pytest.param("BetaVEVO", None, id="the-acts-own-vevo-channel"),
        pytest.param("BetaMusic", None, id="the-acts-own-music-channel"),
    ],
)
def test_another_acts_video_lifts_only_from_a_label_channel_that_is_not_the_acts_own(channel, kind):
    assert _kind(_another_cast(channel)) == kind


def test_a_query_that_names_the_original_lifts_no_other_act():
    assert _kind(_another_cast(), "some song") == "video"
    assert _kind(_another_cast(), "alpha some song") is None


def test_another_acts_video_must_be_the_song_not_another_song_that_names_the_film():
    other_song = _row("Beta - Other Song (From Some Film) (Official Video)", "Gamma Records")

    assert _kind(other_song, "some film") is None


def test_another_acts_audio_on_a_label_channel_is_not_lifted():
    audio = _row("Beta - Some Song (Official Audio)", channel="Gamma Records")

    assert _kind(audio) is None
    assert _kind(_art("Some Song", "Beta")) is None


def test_a_label_channel_whose_name_cannot_be_read_names_no_act_and_lifts_nothing():
    """A title that credits no one credits its channel; here the channel reads as nothing."""
    assert _kind(_row("Some Song", channel="하이브 Records")) is None


def test_a_query_the_song_check_cannot_read_lifts_no_other_act_either():
    query = "idol 夜に駆ける"
    rows = [
        _row("YOASOBI「夜に駆ける」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI「アイドル」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI - Idol (Official Music Video)", channel="YOASOBI"),
        _row("Beta - Idol (Official Video)", channel="Gamma Records"),
    ]

    acts = read_first_page(rows, query)

    assert not acts.has_video
    assert official_first(rows, query, acts) == [(r, None) for r in rows]


# Order (rule 12)
# ---------------------------------------------------------------------------


def _page_with_audio_and_a_video() -> list[SearchResult]:
    return [
        _unrelated(),
        _art("Some Song"),
        _row("Alpha - Some Song (Official Video)", channel="Alpha"),
        _art("Some Song (Second)"),
    ]


def test_audio_beside_a_lifted_video_keeps_its_place_and_its_badge():
    rows = _page_with_audio_and_a_video()

    ranked = official_first(rows, "some song", read_first_page(rows, "some song"))

    assert _titles(ranked) == [
        "Alpha - Some Song (Official Video)",
        "Unrelated upload",
        "Some Song",
        "Some Song (Second)",
    ]
    assert [kind for _, kind in ranked] == ["video", None, "audio", "audio"]


def test_audio_with_no_video_is_first_in_youtubes_order():
    rows = [_unrelated(), _art("Some Song"), _art("Some Song (Second)")]

    ranked = official_first(rows, "some song", read_first_page(rows, "some song"))

    assert _titles(ranked) == ["Some Song", "Some Song (Second)", "Unrelated upload"]
    assert [kind for _, kind in ranked] == ["audio", "audio", None]


def test_a_second_page_with_audio_and_no_video_keeps_its_order_when_page_one_lifted_a_video():
    with_video = [_row("Alpha - Some Song (Official Video)", channel="Alpha"), _art("Some Song")]
    no_video = [_art("Some Song"), _art("Some Song")]
    second_page = [_unrelated(), _art("Some Song (Second)")]

    after_a_video = read_first_page(with_video + no_video, "some song")
    after_none = read_first_page(no_video, "some song")

    assert after_a_video.has_video and not after_none.has_video
    kept = official_first(second_page, "some song", after_a_video)
    assert _titles(kept) == ["Unrelated upload", "Some Song (Second)"]
    assert [kind for _, kind in kept] == [None, "audio"]
    lifted = official_first(second_page, "some song", after_none)
    assert _titles(lifted) == ["Some Song (Second)", "Unrelated upload"]


def test_a_second_page_with_its_own_video_puts_it_before_its_audio():
    """Page one lifted no video, but these rows hold the original's: the audio keeps its place."""
    after_none = read_first_page([_art("Some Song"), _art("Some Song")], "some song")
    rows = _page_with_audio_and_a_video()

    ranked = official_first(rows, "some song", after_none)

    assert not after_none.has_video
    assert _titles(ranked) == [
        "Alpha - Some Song (Official Video)",
        "Unrelated upload",
        "Some Song",
        "Some Song (Second)",
    ]


@pytest.mark.parametrize("query", ["夜に駆ける", "yoasobi 夜に駆ける"])
def test_a_query_the_song_check_cannot_read_lifts_nothing(query):
    rows = [
        _row("YOASOBI「夜に駆ける」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI「アイドル」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI - Idol (Official Music Video)", channel="YOASOBI"),
    ]

    acts = read_first_page(rows, query)

    assert acts == Acts()
    assert official_first(rows, query, acts) == [(r, None) for r in rows]


def test_accented_latin_is_still_read():
    rows = [_row("Beyoncé - Halo"), _row("Beyoncé - Halo (Official Video)")]

    assert _originals(rows, "beyoncé halo") == {"beyonce"}


# An act's name alone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query, act_search, originals, videos, audio",
    _ACT_SEARCHES,
    ids=[query for query, *_ in _ACT_SEARCHES],
)
def test_an_artist_search_lifts_the_acts_videos_and_badges_its_audio(
    query, act_search, originals, videos, audio
):
    results = _load(query)[:_FIRST_PAGE]
    acts = read_first_page(results, query)

    ranked = official_first(results, query, acts)

    video_ids, audio_ids = _at(query, videos), _at(query, audio)
    assert acts.act_search is act_search
    assert acts.originals == frozenset(originals)
    lifted = video_ids or audio_ids  # audio is lifted only where no video is
    assert _ids(ranked)[: len(lifted)] == lifted
    assert {result.id: kind for result, kind in ranked if kind} == {
        **dict.fromkeys(video_ids, "video"),
        **dict.fromkeys(audio_ids, "audio"),
    }


@pytest.mark.parametrize(
    "query, act_search, originals, videos, audio",
    _ACT_SEARCHES,
    ids=[query for query, *_ in _ACT_SEARCHES],
)
def test_in_an_artist_search_everything_not_lifted_keeps_youtubes_order(
    query, act_search, originals, videos, audio
):
    results = _load(query)[:_FIRST_PAGE]
    lifted = _at(query, videos) or _at(query, audio)

    ranked = official_first(results, query, read_first_page(results, query))

    assert _ids(ranked)[len(lifted) :] == [r.id for r in results if r.id not in lifted]


def _capture_row(query: str, video_id: str) -> tuple[SearchResult, Acts]:
    """The row, and what the capture's first page says."""
    acts = read_first_page(_load(query)[:_FIRST_PAGE], query)
    assert acts.act_search  # else the rows below would be read as a song search's
    return next(row for row in _raw(query) if row.id == video_id), acts


@pytest.mark.parametrize(
    "query, video_id, place",
    [
        pytest.param("idina menzel", "YVVTZgwYwVo", 0, id="film-label-under-her-name"),
        pytest.param("adele", "0put0_a--Ng", 3, id="label-video-of-another-song"),
    ],
)
def test_a_label_channels_video_of_the_act_lifts_as_the_acts_own(query, video_id, place):
    """Among the originals' videos in YouTube's order, not after them as another act's."""
    results = _load(query)[:_FIRST_PAGE]
    ranked = official_first(results, query, read_first_page(results, query))

    videos = [result.id for result, kind in ranked if kind == "video"]

    assert videos.index(video_id) == place


def test_no_other_act_lifts_in_an_artist_search():
    """A Punjabi singer's "JOURNEY" on a label is another act's video of a song named journey."""
    row, acts = _capture_row("journey", "tGbKhMg0ijA")

    assert official_kind(row, "journey", acts) is None
    assert official_kind(row, "journey", replace(acts, act_search=False)) == "video"


@pytest.mark.parametrize(
    "query, video_id",
    [
        pytest.param("taylor swift", "e-ORhEE9VVg", id="blank-space"),
        pytest.param("eminem", "xFYQQPAOz7Y", id="lose-yourself"),
        pytest.param("abba", "BshxCIjNEjY", id="super-trouper"),
        pytest.param("the beatles", "2Q_ZzBGPdqE", id="help"),
    ],
)
def test_a_plain_title_on_the_acts_own_channel_lifts(query, video_id):
    row, acts = _capture_row(query, video_id)

    assert official_kind(row, query, acts) == "video"


@pytest.mark.parametrize(
    "query, video_id",
    [
        pytest.param("adele", "fk4BbF7B29w", id="unexplained-bracket"),
        pytest.param("adele", "X-yIEMduRXk", id="lyric-video"),
        pytest.param("queen", "j440-D5JhjI", id="hour-long-compilation-2"),
        pytest.param("queen", "_Uu12zY01ts", id="hour-long-compilation-1"),
        pytest.param("queen", "2ZBtPf7FOoM", id="top-of-the-pops"),
    ],
)
def test_a_bracket_must_still_say_what_it_is_in_an_artist_search(query, video_id):
    row, acts = _capture_row(query, video_id)

    assert official_kind(row, query, acts) is None


def test_only_the_quoted_song_of_a_title_is_explained():
    """The quoted "Lovesick Girls" is the song; the "DANCE PRACTICE" outside it is not."""
    row, acts = _capture_row("blackpink", "YxksUfnuEbI")

    assert official_kind(row, "blackpink", acts) is None


@pytest.mark.parametrize(
    "query, video_id",
    [
        pytest.param("blackpink", "Is0iob8lz4w", id="with-blackpink-episode"),
        pytest.param("celine dion", "gMOovDrWWiI", id="from-a-tv-special"),
    ],
)
def test_known_wrong_lifts_through_a_from_or_with_bracket_are_pinned(query, video_id):
    """The words after "with" and "from" are dropped to the segment or bracket end, so the episode
    and the special read as explained. A fix of that hole fails here, which is the point."""
    row, acts = _capture_row(query, video_id)

    assert official_kind(row, query, acts) == "video"


def test_a_search_that_names_a_song_is_never_an_artist_search():
    act_searches = {query for query, *_ in _ACT_SEARCHES}
    song_searches = sorted(
        path.stem.replace("_", " ")
        for path in _FIXTURES.glob("*.jsonl")
        if path.stem.replace("_", " ") not in act_searches
    )
    assert len(song_searches) == 50

    found = [
        query
        for query in song_searches
        if read_first_page(_load(query)[:_FIRST_PAGE], query).act_search
    ]

    assert found == []


@pytest.mark.parametrize(
    "own_rows, unverified_own_rows, act_search",
    [(0, 0, False), (1, 0, False), (2, 0, True), (1, 1, False), (0, 2, False)],
    ids=["none", "one", "two", "one-and-one-unverified", "two-unverified"],
)
def test_two_rows_from_the_querys_own_trusted_channel_make_an_artist_search(
    own_rows, unverified_own_rows, act_search
):
    rows = [
        *(_row("Alpha - Song (Official Video)", channel="Alpha") for _ in range(own_rows)),
        *(
            _row("Alpha - Song (Official Video)", channel="Alpha", verified=False)
            for _ in range(unverified_own_rows)
        ),
        _unrelated(),
    ]

    assert read_first_page(rows, "alpha").act_search is act_search


def _alpha_page(*extra: SearchResult) -> list[SearchResult]:
    """An act search for "alpha": three videos on Alpha's own channel, then ``extra``."""
    return [
        *(
            _row(f"Alpha - Song {n} (Official Video)", channel="Alpha")
            for n in "One Two Three".split()
        ),
        *extra,
    ]


def test_in_an_artist_search_every_title_reads_act_dash_song():
    """The query holds the whole left side, which a song search would read as "Song - Artist"
    and credit each video's song name with one vote."""
    rows = _alpha_page()

    acts = read_first_page(rows, "alpha")

    assert acts.originals == {"alpha"}
    assert [kind for _, kind in official_first(rows, "alpha", acts)] == ["video"] * 3


def test_in_an_artist_search_a_song_dash_act_title_credits_the_song_and_is_not_badged():
    rows = _alpha_page(_row("Song Four - Alpha (Official Video)", channel="Alpha"))

    acts = read_first_page(rows, "alpha")
    ranked = official_first(rows, "alpha", acts)

    assert acts.originals == {"alpha"}
    assert [kind for _, kind in ranked] == ["video"] * 3 + [None]


@pytest.mark.parametrize(
    "title, named",
    [
        ("Taylor Swift - Blank Space", "Blank Space"),
        ("Taylor Swift | Blank Space", "Blank Space"),
        ("Adele - Send My Love (To Your New Lover)", "Send My Love"),
        ("BLACKPINK - 'Lovesick Girls' DANCE PRACTICE VIDEO", "'Lovesick Girls'"),
        ("BTS (방탄소년단) 'Dynamite' Official MV", "'Dynamite'"),
        ("Queen", ""),
        ("Queen (Official)", ""),
    ],
)
def test_the_song_a_title_names_is_the_second_side_or_the_quote_in_a_one_sided_title(title, named):
    assert _named_song(title).strip() == named
