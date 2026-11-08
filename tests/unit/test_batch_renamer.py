"""Unit tests for batch_song_renamer route-level logic."""

from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.song_manager import SongManager
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


def _admin_karaoke():
    k = MagicMock()
    k.queue_manager.is_song_in_queue.return_value = False
    k.song_manager.filename_from_path = SongManager.filename_from_path
    k.library_tools.is_busy.return_value = False
    k.library_tools.is_waiting_for_pick.return_value = False
    return k


def _rename(client, new_name):
    return client.post(
        "/batch-song-renamer/rename-song", data={"old_name": SONG, "new_name": new_name}
    ).get_json()


@patch("pikaraoke.routes.batch_song_renamer.is_admin", return_value=True)
@patch("pikaraoke.routes.batch_song_renamer.get_karaoke_instance")
def test_rename_returns_the_path_the_manager_made(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.rename.return_value = "/songs/Musicals/Better---abc123def45.mp4"

    result = _rename(client, "Better---abc123def45")

    k.song_manager.rename.assert_called_once_with(SONG, "Better---abc123def45")
    assert result == {"success": True, "new_file_name": "/songs/Musicals/Better---abc123def45.mp4"}


@patch("pikaraoke.routes.batch_song_renamer.is_admin", return_value=True)
@patch("pikaraoke.routes.batch_song_renamer.get_karaoke_instance")
def test_a_case_only_rename_goes_through_a_temp_name_the_manager_chose(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.rename.side_effect = ["/songs/Sub/tmp.mp4", "/songs/Sub/artist - song.mp4"]

    result = _rename(client, "artist - song---abc123def45")

    (_, first), (second_old, second_new) = (c.args for c in k.song_manager.rename.call_args_list)
    assert first.startswith("artist - song---abc123def45_temp_")
    assert (second_old, second_new) == ("/songs/Sub/tmp.mp4", "artist - song---abc123def45")
    assert result["new_file_name"] == "/songs/Sub/artist - song.mp4"


@patch("pikaraoke.routes.batch_song_renamer.is_admin", return_value=True)
@patch("pikaraoke.routes.batch_song_renamer.get_karaoke_instance")
def test_rename_onto_a_taken_name_says_it_exists(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.rename.side_effect = FileExistsError("taken")

    result = _rename(client, "Taken")

    assert result["success"] is False
    assert "Filename already exists" in result["message"]


@patch("pikaraoke.routes.batch_song_renamer.is_admin", return_value=True)
@patch("pikaraoke.routes.batch_song_renamer.get_karaoke_instance")
def test_a_failed_rename_is_reported_not_raised(mock_get, _admin, client):
    mock_get.return_value = k = _admin_karaoke()
    k.song_manager.rename.side_effect = PermissionError("locked")

    result = _rename(client, "Better")

    assert result["success"] is False
    assert "locked" in result["message"]


@pytest.mark.parametrize("reason", ["is_busy", "is_waiting_for_pick"])
@patch("pikaraoke.routes.batch_song_renamer.is_admin", return_value=True)
@patch("pikaraoke.routes.batch_song_renamer.get_karaoke_instance")
def test_rename_refuses_a_song_still_processing(mock_get, _admin, client, reason):
    mock_get.return_value = k = _admin_karaoke()
    getattr(k.library_tools, reason).return_value = True

    result = _rename(client, "Better")

    assert result["success"] is False
    assert SONG in result["message"]
    k.song_manager.rename.assert_not_called()
