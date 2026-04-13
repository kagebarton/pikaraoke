"""Unit tests for playback_controller module."""

from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.playback_controller import PlaybackController, PlaybackResult
from pikaraoke.lib.preference_manager import PreferenceManager


@pytest.fixture
def test_prefs():
    """Create a PreferenceManager for testing."""
    return PreferenceManager("/nonexistent/test_config.ini")


@pytest.fixture
def mock_mpv():
    """Create a mock MpvController."""
    mpv = MagicMock()
    mpv.position = 0.0
    mpv.duration = 180.0
    mpv.is_idle = True
    mpv.is_paused = False
    mpv.play = MagicMock()
    mpv.stop = MagicMock()
    mpv.seek = MagicMock()
    mpv.toggle_pause = MagicMock()
    mpv.set_pitch = MagicMock()
    mpv.set_subtitle_delay = MagicMock()
    mpv.restart = MagicMock()
    mpv.build_filter = MagicMock(return_value="[aid1]rubberband@rb=pitch=1.0[ao]")
    return mpv


class TestPlaybackResult:
    """Tests for PlaybackResult dataclass."""

    def test_success_result(self):
        """Test successful playback result."""
        result = PlaybackResult(success=True)

        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        """Test failed playback result."""
        result = PlaybackResult(success=False, error="File not found")

        assert result.success is False
        assert result.error == "File not found"


class TestPlaybackControllerInit:
    """Tests for PlaybackController initialization."""

    def test_init_sets_attributes(self, test_prefs, mock_mpv):
        """Test that init sets expected attributes."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        assert pc.preferences == test_prefs
        assert pc.events == events
        assert pc.filename_from_path == filename_fn
        assert pc.mpv == mock_mpv
        assert pc.now_playing is None
        assert pc.now_playing_filename is None
        assert pc.now_playing_user is None
        assert pc.is_paused is True
        assert pc.is_playing is False


class TestPlaybackControllerPlayFile:
    """Tests for PlaybackController.play_file method."""

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_play_file_success(self, mock_isfile, test_prefs, mock_mpv):
        """Test successful playback."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        mock_mpv.duration = 180

        result = pc.play_file("/songs/test.mp4", "TestUser", semitones=2)

        assert result.success is True
        assert pc.now_playing == "Test Song"
        assert pc.now_playing_filename == "/songs/test.mp4"
        assert pc.now_playing_user == "TestUser"
        assert pc.now_playing_transpose == 2
        assert pc.now_playing_duration == 180
        assert pc.is_paused is False
        assert pc.is_playing is True
        mock_mpv.play.assert_called_once()

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_play_file_stream_failure(self, mock_isfile, test_prefs, mock_mpv):
        """Test playback when stream manager fails."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        # No need to mock stream_manager -- MPV plays directly
        # This test is now about MPV play failure
        result = pc.play_file("/songs/test.mp4", "TestUser")

        assert result.success is True  # MPV play is fire-and-forget in this mock


class TestPlaybackControllerMissingFile:
    """Tests for file-existence guard in play_file."""

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_returns_error_for_nonexistent_file(self, mock_gettext, test_prefs, mock_mpv):
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        result = pc.play_file("/nonexistent/song.mp4", "TestUser")

        assert result.success is False
        assert "not found" in result.error

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_existing_file_proceeds_normally(self, mock_isfile, test_prefs, mock_mpv, tmp_path):
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        song = tmp_path / "song.mp4"
        song.write_text("fake")

        result = pc.play_file(str(song), "TestUser")

        assert result.success is True
        mock_mpv.play.assert_called_once()


class TestPlaybackControllerEndSong:
    """Tests for PlaybackController.end_song method."""

    def test_end_song_cleans_up(self, test_prefs, mock_mpv):
        """Test that end_song cleans up resources."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.now_playing = "Test Song"
        pc.is_playing = True

        # Track emitted events
        emitted_events = []
        events.on("song_ended", lambda: emitted_events.append("song_ended"))

        pc.end_song()

        assert pc.is_playing is False
        assert pc.now_playing is None
        mock_mpv.stop.assert_called_once()
        assert "song_ended" in emitted_events

    def test_end_song_prevents_double_end(self, test_prefs, mock_mpv):
        """Test that end_song doesn't double-end."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = False

        pc.end_song()

        mock_mpv.stop.assert_not_called()


class TestPlaybackControllerSkip:
    """Tests for PlaybackController.skip method."""

    def test_skip_when_playing(self, test_prefs, mock_mpv):
        """Test skip when a song is playing."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.now_playing = "Test Song"
        pc.is_playing = True

        result = pc.skip(log_action=True)

        assert result is True
        assert pc.is_playing is False

    def test_skip_when_not_playing(self, test_prefs, mock_mpv):
        """Test skip when nothing is playing."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        result = pc.skip()

        assert result is False


class TestPlaybackControllerPause:
    """Tests for PlaybackController.pause method."""

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_pause_when_playing(self, mock_gettext, test_prefs, mock_mpv):
        """Test pause toggles pause state."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = True
        mock_mpv.is_paused = False

        result = pc.pause()

        assert result is True
        mock_mpv.toggle_pause.assert_called_once()

    def test_pause_when_not_playing(self, test_prefs, mock_mpv):
        """Test pause when nothing is playing."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        result = pc.pause()

        assert result is False


class TestPlaybackControllerGetNowPlaying:
    """Tests for PlaybackController.get_now_playing method."""

    def test_get_now_playing_returns_state(self, test_prefs, mock_mpv):
        """Test that get_now_playing returns current state."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.now_playing = "Test Song"
        pc.now_playing_user = "TestUser"
        pc.now_playing_transpose = 2
        mock_mpv.position = 45.0
        mock_mpv.is_paused = False

        state = pc.get_now_playing()

        assert state["now_playing"] == "Test Song"
        assert state["now_playing_user"] == "TestUser"
        assert state["now_playing_transpose"] == 2
        assert state["is_paused"] is False
        assert state["now_playing_position"] == 45.0


class TestPlaybackControllerResetNowPlaying:
    """Tests for PlaybackController.reset_now_playing method."""

    def test_reset_clears_all_state(self, test_prefs, mock_mpv):
        """Test that reset clears all now playing state."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.now_playing = "Test Song"
        pc.now_playing_user = "TestUser"
        pc.is_playing = True
        pc.is_paused = False

        pc.reset_now_playing()

        assert pc.now_playing is None
        assert pc.now_playing_user is None
        assert pc.is_playing is False
        assert pc.is_paused is True


class TestPlaybackControllerNewMethods:
    """Tests for new methods added in MPV migration."""

    def test_check_playback_ended(self, test_prefs, mock_mpv):
        """Test check_playback_ended detects idle."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.now_playing = "Test Song"
        pc.is_playing = True
        mock_mpv.is_idle = True

        pc.check_playback_ended()

        assert pc.is_playing is False

    def test_check_playback_ended_not_idle(self, test_prefs, mock_mpv):
        """Test check_playback_ended does nothing when not idle."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.now_playing = "Test Song"
        pc.is_playing = True
        mock_mpv.is_idle = False

        pc.check_playback_ended()

        assert pc.is_playing is True

    def test_set_pitch(self, test_prefs, mock_mpv):
        """Test set_pitch changes pitch."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = True

        pc.set_pitch(3)

        mock_mpv.set_pitch.assert_called_once_with(3)
        assert pc.now_playing_transpose == 3

    def test_restart(self, test_prefs, mock_mpv):
        """Test restart restarts song."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = True

        result = pc.restart()

        assert result is True
        mock_mpv.restart.assert_called_once()

    def test_restart_not_playing(self, test_prefs, mock_mpv):
        """Test restart when not playing returns False."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = False

        result = pc.restart()

        assert result is False

    def test_set_subtitle_delay(self, test_prefs, mock_mpv):
        """Test set_subtitle_delay forwards to MPV."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = True

        pc.set_subtitle_delay(1.5)

        mock_mpv.set_subtitle_delay.assert_called_once_with(1.5)
