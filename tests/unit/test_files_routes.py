"""Render tests for the /browse (files) page.

These guard the contract between the browse route and files.html: the route
enriches each song into a dict ({path, pipeline_state, tracker_status,
is_active}) and the template must consume that shape. A regression here
previously 500'd /browse for any non-empty library, because the template still
treated each song as a bare path string. The empty-library case rendered fine,
so a test with actual songs is required to catch it.
"""

import os
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

import pikaraoke

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.song_manager import SongManager
from pikaraoke.routes.files import files_bp

SONGS = [
    "/songs/Artist - Song One---abc123def45.mp4",
    "/songs/Band - Failed Track---mno345pqr67.mp4",
    "/songs/Queued - Waiting---ghi789stu90.mp4",
    "/songs/Live - Now Processing---jkl012vwx34.mp4",
]


@pytest.fixture
def app():
    """A Flask app that can render files.html end to end.

    files.html extends base.html, which resolves several blueprints via
    url_for; stub the endpoints the templates reference so url_for succeeds
    without pulling in every real blueprint.
    """
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    test_app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    test_app.register_blueprint(files_bp)
    for endpoint in (
        "home.home",
        "queue.queue",
        "search.search",
        "info.info",
        "processing.processing",
        "queue.enqueue",
        "batch_song_renamer.browse",
    ):
        test_app.add_url_rule(f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda: "")

    # Babel wires both the route's flask_babel.gettext and the template {% trans %}.
    Babel(test_app)
    test_app.jinja_env.globals.update(
        filename_from_path=SongManager.filename_from_path, url_escape=quote
    )
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


def _mock_karaoke(songs, *, pipeline_states=None, tracker=None, active_job=None):
    k = MagicMock()
    k.song_manager.songs = list(songs)
    k.song_manager.filename_from_path = SongManager.filename_from_path
    k.song_manager.get_pipeline_states.return_value = pipeline_states or {}
    k.pipeline_tracker.get_status.return_value = tracker or []
    k.processing_manager.get_active_job.return_value = active_job
    k.browse_results_per_page = 500
    return k


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_browse_renders_song_rows(mock_get, _site, _admin, client):
    """A non-empty library renders the song table without a 500."""
    mock_get.return_value = _mock_karaoke(SONGS)

    resp = client.get("/browse")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Artist - Song One" in body
    # One add-to-queue link per song row.
    assert body.count("add-song-link") == len(SONGS) + 1  # +1 for the JS handler binding


@patch("pikaraoke.routes.files.is_admin", return_value=True)
@patch("pikaraoke.routes.files.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_browse_renders_status_badges(mock_get, _site, _admin, client):
    """Pipeline/tracker status surfaces as badges, with is_active taking precedence."""
    mock_get.return_value = _mock_karaoke(
        SONGS,
        pipeline_states={
            SONGS[1]: "failed",
            SONGS[2]: "pending",
            SONGS[3]: "pending",
        },
        tracker=[
            {"song_path": SONGS[2], "processing_status": "waiting"},
            {"song_path": SONGS[3], "processing_status": "active"},
        ],
        active_job=SONGS[3],
    )

    body = client.get("/browse").get_data(as_text=True)

    assert ">failed<" in body
    assert ">waiting<" in body
    # SONGS[3] is both is_active and tracker "active"; is_active wins -> "processing".
    assert ">processing<" in body


@patch("pikaraoke.routes.files.is_admin", return_value=False)
@patch("pikaraoke.routes.files.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.files.get_karaoke_instance")
def test_browse_empty_library_renders(mock_get, _site, _admin, client):
    """An empty library still renders (the case that masked the regression)."""
    mock_get.return_value = _mock_karaoke([])

    resp = client.get("/browse")

    assert resp.status_code == 200
