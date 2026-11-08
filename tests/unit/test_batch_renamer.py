"""Unit tests for batch_song_renamer route-level logic."""

from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.routes.batch_song_renamer import _names_match, batch_song_renamer_bp

SONG = "/songs/Artist - Song---abc123def45.mp4"


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(batch_song_renamer_bp)
    Babel(app)
    return app.test_client()


class TestNamesMatch:
    """Tests for the _names_match comparison function."""

    def test_identical_names_match(self):
        assert _names_match("Artist - Song", "Artist - Song") is True

    def test_case_insensitive(self):
        assert _names_match("artist - song", "Artist - Song") is True

    def test_dash_variants_match(self):
        assert _names_match("Artist \u2013 Song", "Artist - Song") is True

    def test_whitespace_normalized(self):
        assert _names_match("Artist  -  Song", "Artist - Song") is True

    def test_accent_insensitive(self):
        assert _names_match("C\u00e9line Dion - Song", "Celine Dion - Song") is True

    def test_none_correct_name(self):
        assert _names_match("Artist - Song", None) is False

    def test_different_names(self):
        assert _names_match("Artist - Song A", "Artist - Song B") is False

    def test_empty_strings(self):
        assert _names_match("", "") is True


@patch("pikaraoke.routes.batch_song_renamer.is_admin", return_value=False)
@patch("pikaraoke.routes.batch_song_renamer.get_karaoke_instance")
def test_a_guest_cannot_rename_a_song(mock_get, _admin, client):
    k = MagicMock()
    k.queue_manager.is_song_in_queue.return_value = False
    mock_get.return_value = k

    resp = client.post(
        "/batch-song-renamer/rename-song", data={"old_name": SONG, "new_name": "Stolen Name"}
    )

    assert resp.get_json()["success"] is False
    k.song_manager.rename.assert_not_called()
