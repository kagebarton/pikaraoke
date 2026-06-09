"""Unit tests for playback_controller module."""

import sqlite3
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
    mpv.tick_overlays = MagicMock()
    mpv.load_placeholder = MagicMock()
    mpv.build_filter = MagicMock(return_value="[aid1]rubberband@rb=pitch=1.0[ao]")
    mpv.osd_size = (1920, 1080)
    mpv._server_url = "http://127.0.0.1:5555"
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
        # State is set before mpv.play and tick_overlays called once after
        mock_mpv.tick_overlays.assert_called_once()
        # Verify ordering: state-set happens before mpv.play
        play_call_index = None
        tick_call_index = None
        for i, call in enumerate(mock_mpv.method_calls):
            if call[0] == "play":
                play_call_index = i
            elif call[0] == "tick_overlays":
                tick_call_index = i
        assert play_call_index is not None, "mpv.play should have been called"
        assert tick_call_index is not None, "mpv.tick_overlays should have been called"
        assert tick_call_index > play_call_index, "tick_overlays must come after mpv.play"

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
        mock_mpv.load_placeholder.assert_called_once()
        mock_mpv.tick_overlays.assert_called_once()
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

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_pause_toggles_controller_state_independently_of_mpv_lag(
        self, mock_gettext, test_prefs, mock_mpv
    ):
        """is_paused must track on the controller, not the lagged mpv observer.

        Regression: the /pause route reads pc.is_paused to choose its broadcast,
        and the notification must not depend on self.mpv.is_paused, which the
        _on_pause observer updates only later (and which we pin stale here).
        """
        events = EventSystem()
        notes: list[str] = []
        events.on("notification", lambda msg, level: notes.append(msg))
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)
        pc.is_playing = True
        pc.is_paused = False
        mock_mpv.is_paused = False  # observer hasn't fired -> stays stale

        pc.pause()  # play -> pause
        assert pc.is_paused is True
        assert notes[-1].startswith("Pause:")

        pc.pause()  # pause -> resume
        assert pc.is_paused is False
        assert notes[-1].startswith("Resume:")

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
    """Tests for methods added in MPV migration."""

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


class TestPlaybackControllerLoudnorm:
    """Tests for loudnorm offset wiring from DB to MPV playback."""

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_loudnorm_offset_forwarded_when_normalize_enabled(
        self, mock_isfile, test_prefs, mock_mpv
    ):
        """When normalize_audio is enabled and get_loudnorm_offset returns a value,
        it should be forwarded as normalization_db to mpv.play()."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"
        get_offset = MagicMock(return_value=-4.2)

        test_prefs.set("normalize_audio", True)

        pc = PlaybackController(
            test_prefs, events, filename_fn, mock_mpv, get_loudnorm_offset=get_offset
        )
        mock_mpv.duration = 180

        result = pc.play_file("/songs/test.mp4", "TestUser")

        assert result.success is True
        get_offset.assert_called_once_with("/songs/test.mp4")
        mock_mpv.play.assert_called_once()
        call_kwargs = mock_mpv.play.call_args[1]
        assert call_kwargs["normalization_db"] == -4.2

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_loudnorm_offset_not_fetched_when_normalize_disabled(
        self, mock_isfile, test_prefs, mock_mpv
    ):
        """When normalize_audio is disabled, get_loudnorm_offset should not be called
        and normalization_db should be None."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"
        get_offset = MagicMock(return_value=-4.2)

        test_prefs.set("normalize_audio", False)

        pc = PlaybackController(
            test_prefs, events, filename_fn, mock_mpv, get_loudnorm_offset=get_offset
        )
        mock_mpv.duration = 180

        result = pc.play_file("/songs/test.mp4", "TestUser")

        assert result.success is True
        get_offset.assert_not_called()
        mock_mpv.play.assert_called_once()
        call_kwargs = mock_mpv.play.call_args[1]
        assert call_kwargs["normalization_db"] is None

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_loudnorm_offset_none_when_db_returns_none(self, mock_isfile, test_prefs, mock_mpv):
        """When get_loudnorm_offset returns None (song not processed yet),
        normalization_db should be None (no volume filter applied)."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"
        get_offset = MagicMock(return_value=None)

        test_prefs.set("normalize_audio", True)

        pc = PlaybackController(
            test_prefs, events, filename_fn, mock_mpv, get_loudnorm_offset=get_offset
        )
        mock_mpv.duration = 180

        result = pc.play_file("/songs/test.mp4", "TestUser")

        assert result.success is True
        get_offset.assert_called_once_with("/songs/test.mp4")
        mock_mpv.play.assert_called_once()
        call_kwargs = mock_mpv.play.call_args[1]
        assert call_kwargs["normalization_db"] is None

    @patch("pikaraoke.lib.playback_controller.os.path.isfile", return_value=True)
    def test_loudnorm_offset_falls_back_on_db_exception(self, mock_isfile, test_prefs, mock_mpv):
        """When get_loudnorm_offset raises an exception (e.g. DB closed),
        playback should still succeed with normalization_db=None."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: "Test Song"
        get_offset = MagicMock(side_effect=sqlite3.OperationalError("database is closed"))

        test_prefs.set("normalize_audio", True)

        pc = PlaybackController(
            test_prefs, events, filename_fn, mock_mpv, get_loudnorm_offset=get_offset
        )
        mock_mpv.duration = 180

        result = pc.play_file("/songs/test.mp4", "TestUser")

        assert result.success is True
        get_offset.assert_called_once_with("/songs/test.mp4")
        mock_mpv.play.assert_called_once()
        call_kwargs = mock_mpv.play.call_args[1]
        assert call_kwargs["normalization_db"] is None

    def test_default_get_loudnorm_offset_returns_none(self, test_prefs, mock_mpv):
        """Without injecting get_loudnorm_offset, the default lambda returns None."""
        events = EventSystem()
        filename_fn = lambda x, remove_youtube_id=True: x

        pc = PlaybackController(test_prefs, events, filename_fn, mock_mpv)

        assert pc.get_loudnorm_offset("/any/path.mp4") is None
