"""Tests for lifting the original artist's official uploads to the top of a search.

The fixtures are real ``ytsearch60`` captures from 2026-11-08 (``tests/unit/data/youtube_search``),
frozen because YouTube's live results differ from day to day. Each is loaded through
``_parse_search_line``, so these tests also cover parsing a real yt-dlp row. The expected tables
were read off those captures, ranking their first page.
"""

from pathlib import Path

import pytest

from pikaraoke.lib.official_rank import official_first, official_kind, pick_artist
from pikaraoke.lib.youtube_dl import SearchResult, _parse_search_line

_FIXTURES = Path(__file__).parent / "data" / "youtube_search"

# The first page of every capture: the rows the app ranks and votes over.
_FIRST_PAGE = 30

# query, original artist, official videos in lifted order, official audio in lifted order
_LIFTED = [
    ("bad guy", "billieeilish", ["DyDfgMOUjCI"], ["2pnXjQCegVc"]),
    ("bohemian rhapsody", "queen", ["fJ9rUzIMcZQ"], ["0TF3hFevWE8"]),
    ("dancing queen", "abba", ["xFrGuyw1V8s"], ["P5AqvKYYQEE"]),
    ("defying gravity", "cynthiaerivo", [], ["HxkLt1GXVsw"]),
    ("dont stop believin", "journey", [], ["_wXLKQCTuD0"]),
    ("hallelujah", "leonardcohen", [], ["ttEMYvpoR-k"]),
    ("hello", "adele", ["YQHsXMglC9A"], ["T1tl66trXTQ"]),
    ("let it go frozen", "idinamenzel", ["YVVTZgwYwVo"], ["FnpJBkAMk44"]),
    (
        "never gonna give you up",
        "rickastley",
        ["dQw4w9WgXcQ", "LLFhKaqnWwk", "RrESvSRNpeo"],
        ["3BFTio5296w"],
    ),
    ("queen bohemian rhapsody", "queen", ["fJ9rUzIMcZQ"], ["0TF3hFevWE8"]),
    ("rolling in the deep", "adele", ["rYEDA3JcQqw"], ["bDtjO-R0QSo"]),
    ("seasons of love rent", "anthonyrapp", [], ["1xGUTW3C3gE", "HLEPfySbfxQ"]),
    ("shallow lady gaga", "ladygaga", ["bo_efYhYU2A"], ["BpIf43m2ZQI"]),
    ("someone like you", "adele", ["hLQl3WQQoQ0"], ["22c3_LoIfZQ"]),
]

# query, artist the vote picks, id of a row that looks official but must stay where YouTube put it
_STAYS_PUT = [
    pytest.param("bohemian rhapsody", "queen", "ojRj2JK5oCI", id="cover-artists-own-video"),
    pytest.param("queen bohemian rhapsody", "queen", "LlPcnOjSByU", id="unverified-reupload"),
    pytest.param("queen bohemian rhapsody", "queen", "rY0WxgSXdEE", id="another-song"),
    pytest.param("hello", "adele", "mHONNcZbwDY", id="another-artist-same-title"),
    pytest.param("dancing queen", "abba", "-sVB91NTa4A", id="official-lyric-video"),
    pytest.param("rolling in the deep", "adele", "tW626Q6CFcI", id="acapella-on-page-2"),
]


def _load(query: str) -> list[SearchResult]:
    path = _FIXTURES / f"{query.replace(' ', '_')}.jsonl"
    results = [_parse_search_line(line) for line in path.read_text().splitlines()]
    assert None not in results, f"{path.name} has a row the parser drops"
    return results


def _ids(ranked) -> list[str]:
    return [result.id for result, _ in ranked]


def _row(title: str, channel: str = "A Channel", verified: bool = True) -> SearchResult:
    return SearchResult(
        title=title,
        url="https://youtu.be/aaaaaaaaaaa",
        id="aaaaaaaaaaa",
        channel=channel,
        duration="3:00",
        channel_verified=verified,
        description="",
    )


@pytest.mark.parametrize("query, artist, videos, audio", _LIFTED, ids=[q for q, *_ in _LIFTED])
def test_lifts_the_original_artists_official_video_then_audio(query, artist, videos, audio):
    results = _load(query)[:_FIRST_PAGE]

    assert pick_artist(results, query) == artist
    ranked = official_first(results, query, artist)

    lifted = videos + audio
    assert _ids(ranked)[: len(lifted)] == lifted
    assert [kind for _, kind in ranked[: len(lifted)]] == ["video"] * len(videos) + ["audio"] * len(
        audio
    )
    assert {kind for _, kind in ranked[len(lifted) :]} == {None}


@pytest.mark.parametrize("query, artist, videos, audio", _LIFTED, ids=[q for q, *_ in _LIFTED])
def test_everything_not_lifted_keeps_youtubes_order(query, artist, videos, audio):
    results = _load(query)[:_FIRST_PAGE]
    lifted = set(videos + audio)

    rest = _ids(official_first(results, query, artist))[len(lifted) :]

    assert rest == [r.id for r in results if r.id not in lifted]


@pytest.mark.parametrize("query, artist, video_id", _STAYS_PUT)
def test_an_upload_that_is_not_the_artists_record_is_not_lifted(query, artist, video_id):
    results = _load(query)
    assert pick_artist(results[:_FIRST_PAGE], query) == artist  # else None would pass vacuously
    row = next(r for r in results if r.id == video_id)

    assert official_kind(row, query, artist) is None


@pytest.mark.parametrize(
    "query, first_page_artist, all_rows_artist",
    [
        ("hallelujah", "leonardcohen", "oct2026"),
        ("let it go frozen", "idinamenzel", "letitgo"),
    ],
)
def test_the_vote_over_sixty_rows_drifts_so_it_is_taken_over_the_first_page(
    query, first_page_artist, all_rows_artist
):
    results = _load(query)
    assert len(results) == 2 * _FIRST_PAGE

    assert pick_artist(results[:_FIRST_PAGE], query) == first_page_artist
    assert pick_artist(results, query) == all_rows_artist


def test_a_tie_between_artists_picks_none():
    results = [
        _row("Alpha - Some Song"),
        _row("Alpha - Some Song"),
        _row("Beta - Some Song"),
        _row("Beta - Some Song"),
    ]

    assert pick_artist(results, "some song") is None


def test_one_trusted_credit_is_not_enough():
    assert pick_artist([_row("Alpha - Some Song")], "some song") is None


def test_no_trusted_rows_picks_none_and_changes_no_order():
    results = [_row("Alpha - Some Song", verified=False) for _ in range(5)]

    assert pick_artist(results, "some song") is None
    assert official_first(results, "some song", None) == [(r, None) for r in results]


@pytest.mark.parametrize(
    "titles, artist",
    [
        pytest.param(
            ["Some Song - Alpha", "Some Song - Alpha"], "alpha", id="song-first-title-credits-right"
        ),
        pytest.param(
            ["Alpha ft. Beta - Some Song", "Alpha - Some Song", "Alpha & Beta - Some Song"],
            "alpha",
            id="collaborators-are-credited-separately",
        ),
        pytest.param(
            ["Featherstone - Some Song", "Featherstone - Some Song"],
            "featherstone",
            id="feat-inside-a-word-is-not-a-split",
        ),
        pytest.param(
            ["Alpha - Some Song (Official Video)", "Alpha - Some Song [HD]"],
            "alpha",
            id="bracketed-text-is-ignored",
        ),
    ],
)
def test_pick_artist_reads_the_artist_out_of_a_title(titles, artist):
    results = [_row(title) for title in titles]

    assert pick_artist(results, "some song") == artist


@pytest.mark.parametrize(
    "query, band, song, artist",
    [
        pytest.param(
            "the sound of silence",
            "Simon & Garfunkel",
            "The Sound of Silence",
            "simongarfunkel",
            id="ampersand",
        ),
        pytest.param(
            "lil nas x old town road", "Lil Nas X", "Old Town Road", "lilnasx", id="x-in-the-name"
        ),
    ],
)
def test_a_band_named_like_a_collaboration_is_credited_whole(query, band, song, artist):
    results = [
        _row(f"{band} - {song} (Official Video)", channel=band),
        _row(f"{band} - {song} (Official Audio)", channel=band),
        _row(song, channel=f"{band} - Topic", verified=False),
    ]

    assert pick_artist(results, query) == artist
    assert [kind for _, kind in official_first(results, query, artist)] == [
        "video",
        "audio",
        "audio",
    ]


@pytest.mark.parametrize("query", ["夜に駆ける", "yoasobi 夜に駆ける"])
def test_a_query_the_song_check_cannot_read_picks_none(query):
    results = [
        _row("YOASOBI「夜に駆ける」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI「アイドル」Official Music Video", channel="YOASOBI"),
        _row("YOASOBI - Idol (Official Music Video)", channel="YOASOBI"),
    ]

    assert pick_artist(results, query) is None


def test_accented_latin_is_still_read():
    results = [_row("Beyoncé - Halo"), _row("Beyoncé - Halo (Official Video)")]

    assert pick_artist(results, "beyoncé halo") == "beyonce"
