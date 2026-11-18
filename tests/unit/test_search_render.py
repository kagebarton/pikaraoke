"""Render test for the /search results page.

Guards the contract between the search route and search.html. The route wraps
each YouTube result in a SearchRow (the result and existing_path — the library
file carrying that ID). The master-era template unpacked a positional tuple and
was a name short, raising ValueError (too many values to unpack) -> 500 the
moment a search returned results. The bare /search page rendered fine, so a test
that actually submits a query is required to catch it.
"""

import json
import os
import re
import subprocess
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

import pikaraoke
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.youtube_dl import SearchResult
from pikaraoke.routes.search import search_bp

# Endpoints base.html / search.html resolve via url_for but are not on search_bp.
_STUB_ENDPOINTS = (
    "home.home",
    "queue.queue",
    "files.browse",
    "info.info",
    "processing.processing",
    "queue.enqueue",
)


def _result(
    title: str,
    video_id: str,
    channel: str = "Some Channel",
    duration: str = "3:00",
    channel_verified: bool = False,
    description: str = "",
) -> SearchResult:
    return SearchResult(
        title=title,
        url=f"https://youtu.be/{video_id}",
        id=video_id,
        channel=channel,
        duration=duration,
        channel_verified=channel_verified,
        description=description,
    )


_RESULTS = [
    _result("Never Gonna Give You Up", "dQw4w9WgXcQ", "Rick Astley", "3:33"),
    _result("Africa", "FTQbiNvZqaY", "Toto", "4:55"),
]


@pytest.fixture
def app():
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    test_app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    test_app.register_blueprint(search_bp)
    for endpoint in _STUB_ENDPOINTS:
        test_app.add_url_rule(
            f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda *a, **k: ""
        )
    Babel(test_app)
    test_app.jinja_env.globals.update(
        filename_from_path=SongManager.filename_from_path, url_escape=quote
    )
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


def _mock_karaoke():
    k = MagicMock()
    # Empty library -> every row's existing_path is None.
    k.song_manager.songs.__iter__.side_effect = lambda: iter([])
    return k


@patch("pikaraoke.routes.search.get_search_results", return_value=_RESULTS)
@patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_search_with_results_renders(mock_get, _site, _results, client):
    """A query that returns results renders the cards (regression: was 500)."""
    mock_get.return_value = _mock_karaoke()

    resp = client.get("/search?search_string=karaoke")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Never Gonna Give You Up" in body
    assert "Africa" in body
    assert "search_result_items" in body  # the results list rendered


@patch("pikaraoke.routes.search.get_search_results", return_value=_RESULTS)
@patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_the_saved_search_term_is_a_script_string_of_the_query(mock_get, _site, _results, client):
    """A backslash or quote in the query must not break out of the script's string literal."""
    mock_get.return_value = _mock_karaoke()
    query = 'say "hi" </script> back\\'

    body = client.get(f"/search?search_string={quote(query)}").get_data(as_text=True)

    saved = re.search(r'setItem\("pikaraoke_search_term", (.*)\);', body).group(1)
    assert json.loads(saved) == query
    assert "</script>" not in saved


@patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_bare_search_renders(mock_get, _site, client):
    """The search page with no query renders (the case that masked the 500)."""
    mock_get.return_value = _mock_karaoke()

    resp = client.get("/search")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# The search box: a plain GET form
# ---------------------------------------------------------------------------


def _search_input(body: str) -> str:
    return re.search(r"<input[^>]*name=\"search_string\"[^>]*>", body).group(0)


@patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_the_bare_page_has_a_plain_get_search_form(mock_get, _site, client):
    mock_get.return_value = _mock_karaoke()

    body = client.get("/search").get_data(as_text=True)

    form = next(tag for tag in re.findall(r"<form[^>]*>", body) if 'action="/search"' in tag)
    assert 'method="get"' in form
    box = _search_input(body)
    assert 'type="text"' in box
    assert 'autocomplete="off"' in box  # no past-searches list for a guest to tap by accident
    assert 'value=""' in box
    assert "selectize" not in body.lower()


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_results_page_fills_the_box_with_the_query(mock_get, client):
    query = 'say "hi" <b>'

    body = _search_body(client, mock_get, _RESULTS, _karaoke_with_library([]), query=query)

    assert 'value="say &#34;hi&#34; &lt;b&gt;"' in _search_input(body)


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_the_library_autocomplete_route_is_gone(mock_get, client):
    mock_get.return_value = _mock_karaoke()

    assert client.get("/autocomplete?q=mirrors").status_code == 404


@pytest.mark.parametrize("query", [None, "karaoke"], ids=["bare", "results"])
@patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_one_ticked_add_to_queue_box_leads_advanced_with_or_without_results(
    mock_get, _site, client, query
):
    """Both downloads read it, so it must be on the page whether or not results are showing."""
    mock_get.return_value = _mock_karaoke()
    with patch("pikaraoke.routes.search.get_search_results", return_value=_RESULTS):
        url = "/search" if query is None else f"/search?search_string={query}"
        body = client.get(url).get_data(as_text=True)

    assert body.count('id="add-to-queue"') == 1
    assert re.search(r'<input[^>]*checked[^>]*id="add-to-queue"', body)
    assert (
        body.index('id="advanced-settings"')
        < body.index('id="add-to-queue"')
        < body.index('id="direct-download-url"')
    )
    assert "add-to-queue-search" not in body
    assert "add-to-queue-direct" not in body


# ---------------------------------------------------------------------------
# Library songs: cards first, and a copy under another YouTube ID noted on its card
# ---------------------------------------------------------------------------

_MENA_WNW = (
    "/songs/Mena Massoud, Naomi Scott - A Whole New World "
    "(from Aladdin) (Official Video)---eitDnP0_83k.mp4"
)
_ZAYN_WNW = "/songs/ZAYN, Zhavia Ward - A Whole New World (End Title)---rg_zwK_sSEY.mp4"
_MIRRORS = "/songs/Justin Timberlake - Mirrors (Official Video)---uuZE_IRwLNI.mp4"


def _karaoke_with_library(paths: list[str]):
    k = _mock_karaoke()
    k.song_manager.songs.__iter__.side_effect = lambda: iter(paths)
    return k


def _search_body(client, mock_get, results, karaoke, query="karaoke") -> str:
    mock_get.return_value = karaoke
    with patch("pikaraoke.routes.search.get_search_results", return_value=results):
        with patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke"):
            resp = client.get(f"/search?search_string={quote(query)}")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _cards(body: str) -> list[str]:
    return re.findall(r"<li data-ytID=.*?</li>", body, re.S)


def _card_ids(body: str) -> list[str]:
    return [re.search(r'data-ytID="(\w+)"', card).group(1) for card in _cards(body)]


_NEVER = "never gonna give you up"


def _rick_lyrics(video_id="lyricsaaaaa"):
    return _result("Rick Astley - Never Gonna Give You Up (Lyrics)", video_id)


def _rick_audio():
    return _result(
        "Never Gonna Give You Up",
        "audioaaaaaa",
        channel="Rick Astley - Topic",
        description="Provided to YouTube by RCA Records",
    )


def _rick_video():
    return _result(
        "Rick Astley - Never Gonna Give You Up (Official Video)",
        "videoaaaaaa",
        channel="Rick Astley",
        channel_verified=True,
    )


def _rick_library(*video_ids: str) -> list[str]:
    return [f"/songs/Rick Astley - Never Gonna Give You Up---{i}.mp4" for i in video_ids]


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_song_in_the_library_comes_above_the_official_video(mock_get, client):
    results = [_rick_lyrics(), _rick_audio(), _rick_video()]
    k = _karaoke_with_library(_rick_library("lyricsaaaaa"))

    body = _search_body(client, mock_get, results, k, query=_NEVER)

    assert _card_ids(body) == ["lyricsaaaaa", "videoaaaaaa", "audioaaaaaa"]
    assert "Official video" in _cards(body)[1]  # the badge stays with the video


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_songs_in_the_library_keep_the_rankings_order_among_themselves(mock_get, client):
    """YouTube had the lyrics first; the ranking lifts the video, and both are in the library."""
    other = _result("Unrelated upload", "otheraaaaaa")
    results = [other, _rick_lyrics(), _rick_audio(), _rick_video()]
    k = _karaoke_with_library(_rick_library("lyricsaaaaa", "videoaaaaaa"))

    body = _search_body(client, mock_get, results, k, query=_NEVER)

    assert _card_ids(body) == ["videoaaaaaa", "lyricsaaaaa", "otheraaaaaa", "audioaaaaaa"]


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_more_puts_a_second_page_song_in_the_library_first_in_its_batch(mock_get, client):
    results = (
        _filler(30)
        + _filler(10, 30)
        + [_result("Justin Timberlake - Mirrors", "uuZE_IRwLNI")]
        + _filler(19, 41)
    )
    mock_get.return_value = _karaoke_with_library([_MIRRORS])
    with patch("pikaraoke.routes.search.get_search_results", return_value=results):
        body = client.get("/search/more?search_string=mirrors").get_data(as_text=True)

    assert _card_ids(body)[0] == "uuZE_IRwLNI"
    assert f'data-file-path="{_MIRRORS}"' in _cards(body)[0]


_WNW_LYRICS = "Aladdin - A Whole New World (Lyrics)"


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_library_copy_is_noted_inside_the_card_it_matched(mock_get, client):
    results = [
        _result("Ed Sheeran - Shape of You", "shapeaaaaaa"),
        _result(_WNW_LYRICS, "aaaaaaaaaaa"),
    ]
    k = _karaoke_with_library([_MENA_WNW, _ZAYN_WNW, _MIRRORS])

    body = _search_body(client, mock_get, results, k)

    shape, wnw = _cards(body)
    assert "In library:" not in shape
    assert "In library: <strong>Mena Massoud, Naomi Scott - A Whole New World" in wnw
    assert f'library-copy-enqueue" data-file-path="{_MENA_WNW}">Queue</button>' in wnw
    assert f'library-copy-enqueue" data-file-path="{_ZAYN_WNW}"' in wnw
    assert "Mirrors" not in body
    assert "Already in the library" not in body


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_copy_matching_several_cards_is_noted_on_the_first_only(mock_get, client):
    results = [
        _result(_WNW_LYRICS, "aaaaaaaaaaa"),
        _result("Aladdin - A Whole New World (Karaoke)", "bbbbbbbbbbb"),
    ]

    body = _search_body(client, mock_get, results, _karaoke_with_library([_MENA_WNW]))

    first, second = _cards(body)
    assert f'library-copy-enqueue" data-file-path="{_MENA_WNW}"' in first
    assert "In library:" not in second


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_card_in_the_library_is_skipped_and_the_copy_goes_to_the_next_match(mock_get, client):
    results = [
        _result("Aladdin - A Whole New World (Karaoke)", "bbbbbbbbbbb"),
        _result(_WNW_LYRICS, "aaaaaaaaaaa"),
    ]
    own = "/songs/Aladdin - A Whole New World (Lyrics)---aaaaaaaaaaa.mp4"

    body = _search_body(client, mock_get, results, _karaoke_with_library([_MENA_WNW, own]))

    own_card, matched = _cards(body)
    assert f'data-file-path="{own}"' in own_card
    assert "In library:" not in own_card
    assert f'library-copy-enqueue" data-file-path="{_MENA_WNW}"' in matched
    assert body.count('library-copy-enqueue" data-file-path=') == 1


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_no_note_when_nothing_in_the_library_looks_like_a_result(mock_get, client):
    results = [_result("Ed Sheeran - Shape of You", "aaaaaaaaaaa")]
    k = _karaoke_with_library([_MENA_WNW, _MIRRORS])

    assert "In library:" not in _search_body(client, mock_get, results, k)


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_no_note_for_a_song_a_result_already_matches_by_id(mock_get, client):
    """A result's own card says Queue; another card would repeat that song as a note."""
    results = [
        _result("Justin Timberlake - Mirrors (Lyrics)", "uuZE_IRwLNI"),
        _result("Justin Timberlake - Mirrors (Karaoke)", "bbbbbbbbbbb"),
    ]
    k = _karaoke_with_library([_MIRRORS])

    body = _search_body(client, mock_get, results, k)

    assert "In library:" not in body
    assert f'data-file-path="{_MIRRORS}"' in _cards(body)[0]  # the row's own button


@pytest.mark.parametrize(
    "path",
    [
        "/songs/Justin Timberlake - Mirrors (Official Video) [uuZE_IRwLNI].mp4",
        "/songs/Pop/Justin Timberlake - Mirrors (Official Video)---uuZE_IRwLNI.mp4",
    ],
    ids=["bracketed-id", "subfolder"],
)
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_the_row_not_the_note_offers_a_file_find_by_id_misses(mock_get, client, path):
    """find_by_id sees only top-level ---ID files; the row must still find this one."""
    results = [_result("Justin Timberlake - Mirrors (Lyrics)", "uuZE_IRwLNI")]

    body = _search_body(client, mock_get, results, _karaoke_with_library([path]))

    assert "In library:" not in body
    assert f'data-file-path="{path}"' in body  # the row's own button


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_at_most_three_library_copies_are_noted_on_a_page(mock_get, client):
    titles = ["Rainbow Road", "Silver Lining", "Golden Hour", "Midnight Train"]
    library = [f"/songs/Singer {n} - {t}---{n:0>11}.mp4" for n, t in enumerate(titles)]
    results = [_result(f"{t} (Lyrics)", f"{n:a>11}") for n, t in enumerate(titles)]

    body = _search_body(client, mock_get, results, _karaoke_with_library(library))

    assert body.count('library-copy-enqueue" data-file-path=') == 3


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_more_notes_no_library_copy(mock_get, client):
    results = _filler(30) + [_result(_WNW_LYRICS, "aaaaaaaaaab")] + _filler(29, 31)
    mock_get.return_value = _karaoke_with_library([_MENA_WNW])
    with patch("pikaraoke.routes.search.get_search_results", return_value=results):
        body = client.get("/search/more?search_string=whole+new+world").get_data(as_text=True)

    assert "In library:" not in body
    assert "library-copy" not in body


# ---------------------------------------------------------------------------
# Result cards
# ---------------------------------------------------------------------------


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_card_offers_queue_only_for_a_library_copy_and_queue_dots_for_the_dialog(mock_get, client):
    results = [
        _result("Justin Timberlake - Mirrors", "uuZE_IRwLNI", "JT Channel", "8:04"),
        _result("Africa", "FTQbiNvZqaY", channel="", duration=""),
    ]

    body = _search_body(client, mock_get, results, _karaoke_with_library([_MIRRORS]))

    library_card, other_card = re.findall(r"<li data-ytID=.*?</li>", body, re.S)
    assert f'data-file-path="{_MIRRORS}"' in library_card
    assert re.search(r'is-success search_result_items_enqueue">Queue</button>', library_card)
    assert "search_result_items_select" not in library_card
    assert "8:04" in library_card
    assert "JT Channel" in library_card
    assert "data-file-path" not in other_card
    assert re.search(r'is-success search_result_items_select">Queue…</button>', other_card)
    assert "search_result_items_enqueue" not in other_card
    assert "duration-badge" not in other_card  # no duration, no badge
    assert "has-text-grey" not in other_card  # no channel, no channel line
    assert "data-index" not in body


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_card_carries_its_channel_for_the_lyrics_search(mock_get, client):
    """The page sends the channel with the title; a channel with a quote must not break the tag."""
    results = [
        _result("Some Song", "aaaaaaaaaaa", channel='Dave "D" Band'),
        _result("Other Song", "bbbbbbbbbbb", channel=""),
    ]

    body = _search_body(client, mock_get, results, _karaoke_with_library([]))

    first, second = re.findall(r"<li data-ytID=[^>]*>", body)
    assert 'data-ytChannel="Dave &#34;D&#34; Band"' in first
    assert 'data-ytChannel=""' in second


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_a_show_more_card_carries_its_channel_too(mock_get, client):
    results = _filler(30) + [_result("Late Song", "lateaaaaaaa", channel="Late Channel")]
    resp, _ = _more_body(client, mock_get, results)

    assert 'data-ytChannel="Late Channel"' in resp.get_data(as_text=True)


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_the_official_video_comes_first_and_audio_beside_it_keeps_its_place_with_a_badge(
    mock_get, client
):
    lyrics = _result("Rick Astley - Never Gonna Give You Up (Lyrics)", "lyricsaaaaa")
    audio = _result(
        "Never Gonna Give You Up",
        "audioaaaaaa",
        channel="Rick Astley - Topic",
        description="Provided to YouTube by RCA Records",
    )
    video = _result(
        "Rick Astley - Never Gonna Give You Up (Official Video)",
        "videoaaaaaa",
        channel="Rick Astley",
        channel_verified=True,
    )

    body = _search_body(
        client,
        mock_get,
        [lyrics, audio, video],
        _karaoke_with_library([]),
        query="never gonna give you up",
    )

    cards = re.findall(r"<li data-ytID=.*?</li>", body, re.S)
    assert [re.search(r'data-ytID="(\w+)"', c).group(1) for c in cards] == [
        "videoaaaaaa",
        "lyricsaaaaa",
        "audioaaaaaa",
    ]
    assert "Official video" in cards[0]
    assert "Official" not in cards[1]
    assert "Official audio" in cards[2]


# ---------------------------------------------------------------------------
# Show more: /search/more and the button that calls it
# ---------------------------------------------------------------------------


def _ids(n: int, start: int = 0) -> list[str]:
    return [f"{i:a>11}" for i in range(start, start + n)]


def _filler(n: int, start: int = 0) -> list[SearchResult]:
    return [_result(f"Unrelated upload {video_id}", video_id) for video_id in _ids(n, start)]


def _more_body(client, mock_get, fetch, query="some song"):
    """GET /search/more with ``get_search_results`` patched to ``fetch`` (result or exception)."""
    mock_get.return_value = _karaoke_with_library([])
    patch_kwargs = (
        {"side_effect": fetch} if isinstance(fetch, Exception) else {"return_value": fetch}
    )
    with patch("pikaraoke.routes.search.get_search_results", **patch_kwargs) as search_mock:
        resp = client.get(f"/search/more?search_string={quote(query)}")
    return resp, search_mock


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_more_returns_the_second_page_cards_without_the_page_shell(mock_get, client):
    resp, search_mock = _more_body(client, mock_get, _filler(60))

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" not in body
    assert search_mock.call_args.args == ("some song", 60)
    assert re.findall(r'<li data-ytID="(\w+)"', body) == _ids(30, start=30)


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_more_votes_the_originals_over_the_first_page_and_ranks_the_second(mock_get, client):
    """Over all 60 rows Beta would win the vote; the first page's 30 name Alpha."""
    first_page = [
        _result("Alpha - Some Song (Lyrics)", i, channel="Lyrics Co", channel_verified=True)
        for i in _ids(3)
    ] + _filler(27, start=3)
    beta = [
        _result("Beta - Some Song (Official Video)", i, channel="Beta", channel_verified=True)
        for i in _ids(6, start=30)
    ]
    alpha_video = _result(
        "Alpha - Some Song (Official Video)", "alphavideo1", channel="Alpha", channel_verified=True
    )
    second_page = beta + _filler(23, start=36) + [alpha_video]

    resp, _ = _more_body(client, mock_get, first_page + second_page)

    ids = re.findall(r'<li data-ytID="(\w+)"', resp.get_data(as_text=True))
    assert ids == ["alphavideo1"] + [r.id for r in second_page[:-1]]


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_more_leaves_second_page_audio_in_place_when_the_first_page_lifted_a_video(
    mock_get, client
):
    """Audio goes first only on a page with no official video; page two follows page one."""
    first_page = [
        _result(
            "Alpha - Some Song (Official Video)", "alphavideo1", "Alpha", channel_verified=True
        ),
        _result("Some Song", "alphaaudio1", channel="Alpha - Topic"),
        _result("Some Song", "alphaaudio2", channel="Alpha - Topic"),
    ] + _filler(27, start=3)
    second_page = _filler(29, start=30) + [
        _result("Some Song", "alphaaudio3", channel="Alpha - Topic")
    ]

    resp, _ = _more_body(client, mock_get, first_page + second_page)

    body = resp.get_data(as_text=True)
    ids = re.findall(r'<li data-ytID="(\w+)"', body)
    assert ids == [r.id for r in second_page]
    assert "Official audio" in re.findall(r"<li data-ytID=.*?</li>", body, re.S)[-1]


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_more_answers_502_when_yt_dlp_fails(mock_get, client):
    resp, _ = _more_body(client, mock_get, subprocess.CalledProcessError(1, "yt-dlp"))

    assert resp.status_code == 502


@pytest.mark.parametrize("n_results, button", [(30, True), (29, False), (0, False)])
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_page_one_offers_show_more_only_when_youtube_filled_it(mock_get, client, n_results, button):
    # a query with a quote, ampersand and angle bracket: the button must carry it intact
    query = 'Rock "n" Roll & <b>'

    body = _search_body(client, mock_get, _filler(n_results), _karaoke_with_library([]), query)

    assert ('id="show-more"' in body) is button
    if button:
        assert 'data-search-string="Rock &#34;n&#34; Roll &amp; &lt;b&gt;"' in body
