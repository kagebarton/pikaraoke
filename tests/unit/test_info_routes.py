"""Render test for the /info (settings) page.

Guards the contract between the info route and info.html. C38 reworked the
route's render context (dropping the legacy bg-music/score-phrase/avsync vars
and adding the fork's audio-device/subtitle-delay/vocal-volume/genius controls),
but info.html lagged behind referencing the dropped vars, which 500'd /info with
an UndefinedError. A render test pins the template to the context the route
actually passes.
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
from pikaraoke.routes.info import info_bp

# Endpoints base.html and info.html resolve via url_for; stub the ones not on
# info_bp so url_for succeeds without registering every real blueprint.
_STUB_ENDPOINTS = (
    "home.home",
    "queue.queue",
    "search.search",
    "files.browse",
    "admin.auth",
    "admin.expand_fs",
    "admin.library_stats",
    "admin.logout",
    "admin.quit",
    "admin.reboot",
    "admin.shutdown",
    "admin.sync_library",
    "admin.update_ytdl",
    "images.qrcode",
    "preferences.change_preferences",
    "preferences.clear_preferences",
)

_PREF_DEFAULTS = {
    "volume": 0.85,
    "vocal_volume": 0.4,
    "subtitle_delay": 0.0,
    "audio_delay": 0.0,
    "audio_device": "auto",
    "blocked_processing_words": "",
}


@pytest.fixture
def app():
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    test_app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    test_app.register_blueprint(info_bp)
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
    k.url = "http://pikaraoke.local"
    k.platform = "linux"
    k.os_version = "Linux 6.0"
    k.ffmpeg_version = "6.0"
    k.youtubedl_version = "2024.01.01"
    k.is_transpose_enabled = True
    k.is_raspberry_pi = False
    k.hide_notifications = False
    k.hide_clock = False
    k.hide_url = False
    k.hide_now_playing_overlay = False
    k.splash_delay = 3
    k.normalize_audio = True
    k.high_quality = False
    k.limit_user_songs_by = 0
    k.enable_fair_queue = True
    k.browse_results_per_page = 500
    k.temp_dir = "/tmp/pik"
    k.preferences.get_or_default.side_effect = lambda key, *a: _PREF_DEFAULTS[key]
    k.preferences.get.side_effect = lambda key, default=None: {
        "preferred_language": "en",
        "genius_token": "",
    }.get(key, default)
    k.mpv_controller.list_audio_devices.return_value = [
        {"name": "auto", "description": "Autoselect device"}
    ]
    return k


@patch("pikaraoke.routes.info.get_platform", return_value="linux")
@patch("pikaraoke.routes.info.is_admin", return_value=True)
@patch("pikaraoke.routes.info.get_admin_password", return_value="secret")
@patch("pikaraoke.routes.info.get_site_name", return_value="PiKaraoke")
@patch("pikaraoke.routes.info.get_karaoke_instance")
def test_info_renders(mock_get, _site, _pw, _admin, _plat, client):
    """/info renders against the route's actual context (regression: was 500)."""
    mock_get.return_value = _mock_karaoke()

    resp = client.get("/info")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # The fork's settings controls the reworked context drives.
    assert "pref-audio-device" in body
    assert "subtitle_delay" in body
    assert "vocal_volume" in body
    assert "genius" in body.lower()
    assert "hide_clock" in body  # clock toggle (no longer a separate page)
