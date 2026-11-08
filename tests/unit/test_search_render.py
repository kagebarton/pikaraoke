"""Render test for the /search results page.

Guards the contract between the search route and search.html. The route wraps
each YouTube result in a SearchRow (the result and existing_path — the library
file carrying that ID). The master-era template unpacked a positional tuple and
was a name short, raising ValueError (too many values to unpack) -> 500 the
moment a search returned results. The bare /search page rendered fine, so a test
that actually submits a query is required to catch it.
"""

import os
import re
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


@patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_bare_search_renders(mock_get, _site, client):
    """The search page with no query renders (the case that masked the 500)."""
    mock_get.return_value = _mock_karaoke()

    resp = client.get("/search")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# "Already in the library" note: a library copy under another YouTube ID
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


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_note_offers_library_copies_of_a_reuploaded_song(mock_get, client):
    results = [_result("Aladdin - A Whole New World (Lyrics)", "aaaaaaaaaaa")]
    k = _karaoke_with_library([_MENA_WNW, _ZAYN_WNW, _MIRRORS])

    body = _search_body(client, mock_get, results, k)

    assert "Already in the library:" in body
    assert "Mena Massoud, Naomi Scott - A Whole New World" in body
    assert f'similar-song-enqueue" data-file-path="{_MENA_WNW}"' in body
    assert f'similar-song-enqueue" data-file-path="{_ZAYN_WNW}"' in body
    assert "Mirrors" not in body


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_no_note_when_nothing_in_the_library_looks_like_a_result(mock_get, client):
    results = [_result("Ed Sheeran - Shape of You", "aaaaaaaaaaa")]
    k = _karaoke_with_library([_MENA_WNW, _MIRRORS])

    assert "Already in the library:" not in _search_body(client, mock_get, results, k)


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_no_note_for_a_song_a_result_already_matches_by_id(mock_get, client):
    """That row already says "Add to Queue"; the note would repeat it."""
    results = [_result("Justin Timberlake - Mirrors (Lyrics)", "uuZE_IRwLNI")]
    k = _karaoke_with_library([_MIRRORS])

    body = _search_body(client, mock_get, results, k)

    assert "Already in the library:" not in body
    assert f'data-file-path="{_MIRRORS}"' in body  # the row's own button


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

    assert "Already in the library:" not in body
    assert f'data-file-path="{path}"' in body  # the row's own button


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_note_lists_at_most_three_library_copies(mock_get, client):
    titles = ["Rainbow Road", "Silver Lining", "Golden Hour", "Midnight Train"]
    library = [f"/songs/Singer {n} - {t}---{n:0>11}.mp4" for n, t in enumerate(titles)]
    results = [_result(f"{t} (Lyrics)", f"{n:a>11}") for n, t in enumerate(titles)]

    body = _search_body(client, mock_get, results, _karaoke_with_library(library))

    assert body.count('similar-song-enqueue" data-file-path=') == 3


# ---------------------------------------------------------------------------
# Result cards
# ---------------------------------------------------------------------------


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_card_offers_add_to_queue_only_for_a_library_copy(mock_get, client):
    results = [
        _result("Justin Timberlake - Mirrors", "uuZE_IRwLNI", "JT Channel", "8:04"),
        _result("Africa", "FTQbiNvZqaY", channel="", duration=""),
    ]

    body = _search_body(client, mock_get, results, _karaoke_with_library([_MIRRORS]))

    library_card, other_card = re.findall(r"<li data-ytID=.*?</li>", body, re.S)
    assert f'data-file-path="{_MIRRORS}"' in library_card
    assert "search_result_items_enqueue" in library_card
    assert "search_result_items_select" not in library_card
    assert "8:04" in library_card
    assert "JT Channel" in library_card
    assert "data-file-path" not in other_card
    assert "search_result_items_select" in other_card
    assert "duration-badge" not in other_card  # no duration, no badge
    assert "has-text-grey" not in other_card  # no channel, no channel line
    assert "data-index" not in body


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_the_artists_official_video_and_audio_come_first_with_a_badge(mock_get, client):
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
        "audioaaaaaa",
        "lyricsaaaaa",
    ]
    assert "Official video" in cards[0]
    assert "Official audio" in cards[1]
    assert "Official" not in cards[2]
