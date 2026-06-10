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
