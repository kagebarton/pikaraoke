"""Render test for the /search results page.

Guards the contract between the search route and search.html. The route enriches
each YouTube result into a 6-tuple (title, url, id, channel, duration,
existing_path — the last from songs.find_by_id), but the master-era template
unpacked only 5 names in its results loop, raising ValueError (too many values
to unpack) -> 500 the moment a search returned results. The bare /search page
rendered fine, so a test that actually submits a query is required to catch it.
"""

import os
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

# What get_search_results returns: [title, url, id, channel, duration] per row.
_RAW_RESULTS = [
    [
        "Never Gonna Give You Up",
        "https://youtu.be/dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
        "Rick Astley",
        "3:33",
    ],
    ["Africa", "https://youtu.be/FTQbiNvZqaY", "FTQbiNvZqaY", "Toto", "4:55"],
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
    k.download_path = "/songs"
    # No local match -> existing_path is None (the 6th tuple element).
    k.song_manager.songs.find_by_id.return_value = None
    return k


@patch("pikaraoke.routes.search.get_search_results", return_value=_RAW_RESULTS)
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


def _result(title: str, video_id: str) -> list[str]:
    return [title, f"https://youtu.be/{video_id}", video_id, "Some Channel", "3:00"]


def _karaoke_with_library(paths: list[str], by_id: dict[str, str] | None = None):
    """Mock Karaoke whose library holds ``paths``; ``by_id`` maps video id -> its file."""
    k = _mock_karaoke()
    k.song_manager.songs.__iter__.side_effect = lambda: iter(paths)
    k.song_manager.songs.find_by_id.side_effect = lambda _dir, video_id: (by_id or {}).get(video_id)
    return k


def _search_body(client, mock_get, results, karaoke) -> str:
    mock_get.return_value = karaoke
    with patch("pikaraoke.routes.search.get_search_results", return_value=results):
        with patch("pikaraoke.routes.search.get_site_name", return_value="PiKaraoke"):
            resp = client.get("/search?search_string=karaoke")
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
    k = _karaoke_with_library([_MIRRORS], by_id={"uuZE_IRwLNI": _MIRRORS})

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
def test_no_note_for_a_file_find_by_id_misses(mock_get, client, path):
    """find_by_id sees only top-level ---ID files; the note must still skip this result's file."""
    results = [_result("Justin Timberlake - Mirrors (Lyrics)", "uuZE_IRwLNI")]
    k = _karaoke_with_library([path])  # find_by_id finds nothing

    assert "Already in the library:" not in _search_body(client, mock_get, results, k)


@patch("pikaraoke.routes.search.get_karaoke_instance")
def test_note_lists_at_most_three_library_copies(mock_get, client):
    titles = ["Rainbow Road", "Silver Lining", "Golden Hour", "Midnight Train"]
    library = [f"/songs/Singer {n} - {t}---{n:0>11}.mp4" for n, t in enumerate(titles)]
    results = [_result(f"{t} (Lyrics)", f"{n:a>11}") for n, t in enumerate(titles)]

    body = _search_body(client, mock_get, results, _karaoke_with_library(library))

    assert body.count('similar-song-enqueue" data-file-path=') == 3
