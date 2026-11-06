"""Unit tests for how the run loop and Now Playing use a singer's saved key and vocal volume."""

from unittest.mock import MagicMock

import pytest

from pikaraoke.lib.playback_controller import PlaybackResult
from pikaraoke.lib.singers import SingerSettings

SONG = "/songs/Artist - Song---dQw4w9WgXcQ.mp4"


@pytest.fixture
def play_file(mock_karaoke):
    """Replace play_file so a single pass of the run loop plays one song and stops."""
    mock_karaoke.url = "http://test"
    mock_karaoke.handle_run_loop = lambda: None
    mock_karaoke.preferences.set("splash_delay", 0)

    def play_and_stop(*args) -> PlaybackResult:
        mock_karaoke.running = False
        return PlaybackResult(success=True)

    mock_karaoke.playback_controller.play_file = MagicMock(side_effect=play_and_stop)
    return mock_karaoke.playback_controller.play_file


class TestRunLoopStartsSongsAtTheSingersSettings:
    def test_a_registered_singers_settings_reach_play_file(self, mock_karaoke, play_file):
        mock_karaoke.singers.save(None, "Mike", SingerSettings(semitones=2, vocal_volume=0.7))
        mock_karaoke.queue_manager.enqueue(SONG, "Mike")

        mock_karaoke.run()

        play_file.assert_called_once_with(SONG, "Mike", 2, 0.7)

    def test_settings_changed_after_queuing_apply_when_the_song_starts(
        self, mock_karaoke, play_file
    ):
        _, token = mock_karaoke.singers.save(None, "Mike", SingerSettings(2, 0.7))
        mock_karaoke.queue_manager.enqueue(SONG, "Mike")
        mock_karaoke.singers.save(token, "Mike", SingerSettings(-1, 0.1))

        mock_karaoke.run()

        play_file.assert_called_once_with(SONG, "Mike", -1, 0.1)

    def test_a_name_that_never_joined_plays_at_the_house_defaults(self, mock_karaoke, play_file):
        mock_karaoke.preferences.set("vocal_volume", 0.55)
        mock_karaoke.queue_manager.enqueue(SONG, "Randomizer")

        mock_karaoke.run()

        play_file.assert_called_once_with(SONG, "Randomizer", 0, 0.55)


class TestNowPlayingReportsWhatIsPlaying:
    def test_vocal_volume_is_the_playback_controllers_not_the_house_default(self, mock_karaoke):
        mock_karaoke.preferences.set("vocal_volume", 0.2)
        mock_karaoke.playback_controller.now_playing_vocal_volume = 0.7

        assert mock_karaoke.get_now_playing()["vocal_volume"] == 0.7
