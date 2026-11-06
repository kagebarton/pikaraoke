"""Unit tests for a guest's rename reaching every place their name is kept."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pikaraoke.karaoke import Karaoke
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.pipeline_tracker import PipelineItem, PipelineTracker
from pikaraoke.lib.playback_controller import PlaybackController
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.queue_manager import QueueManager
from pikaraoke.lib.singers import NameTaken, SingerRegistry, SingerSettings

SONG = "/songs/Artist - Song---dQw4w9WgXcQ.mp4"
HELD = "/songs/Other - Held---aaaaaaaaaaa.mp4"


@pytest.fixture
def party(tmp_path):
    """A registry wired to a real queue, tracker and playback controller, the way Karaoke wires
    them, with Mike's songs in every place a name is kept."""
    events = EventSystem()
    preferences = PreferenceManager(config_file_path=str(tmp_path / "config.ini"))
    mpv = MagicMock()
    playback = PlaybackController(
        preferences, events, lambda path, remove_youtube_id=True: path, mpv
    )
    queue = QueueManager(preferences=preferences, events=events)
    tracker = PipelineTracker(MagicMock(), MagicMock(), queue, MagicMock(), events)
    # A real Karaoke would own these; rename_singer only needs the collaborators and the events.
    karaoke = SimpleNamespace(
        queue_manager=queue, pipeline_tracker=tracker, playback_controller=playback, events=events
    )
    karaoke.rename_singer = lambda old, new: Karaoke.rename_singer(karaoke, old, new)

    singers = SingerRegistry(preferences, karaoke.rename_singer)
    name, token = singers.save(None, "Mike", SingerSettings(2, 0.7))
    queue.enqueue(SONG, "Mike", log_action=False)
    queue.enqueue(HELD, "Mike", waiting="download", log_action=False)
    tracker._items.append(PipelineItem(title="Processing", url="https://x/1", user="Mike"))
    playback.is_playing = True
    playback.now_playing_user = "Mike"
    return SimpleNamespace(
        karaoke=karaoke,
        singers=singers,
        name=name,
        token=token,
        playback=playback,
        events=events,
        mpv=mpv,
    )


def rename(party, new_name):
    return party.singers.save(party.token, new_name, SingerSettings(2, 0.7))


def where_the_name_is_kept(party):
    queue = [item["user"] for item in party.karaoke.queue_manager.queue]
    tracker = [item.user for item in party.karaoke.pipeline_tracker._items]
    return queue, tracker, party.playback.now_playing_user


class TestRenameSinger:
    def test_the_new_name_replaces_the_old_in_the_queue_the_tracker_and_the_playing_song(
        self, party
    ):
        rename(party, "Michael")

        assert where_the_name_is_kept(party) == (["Michael", "Michael"], ["Michael"], "Michael")

    def test_a_case_only_rename_moves_them_too(self, party):
        rename(party, "MIKE")

        assert where_the_name_is_kept(party) == (["MIKE", "MIKE"], ["MIKE"], "MIKE")

    def test_a_refused_name_moves_nothing(self, party):
        party.singers.save(None, "Sue", SingerSettings(0, 0.4))

        with pytest.raises(NameTaken):
            rename(party, "sue")

        assert where_the_name_is_kept(party) == (["Mike", "Mike"], ["Mike"], "Mike")

    def test_only_the_renamed_guests_songs_move(self, party):
        party.karaoke.queue_manager.enqueue("/songs/Sue Song---bbbbbbbbbbb.mp4", "Sue")

        rename(party, "Michael")

        queue, _, _ = where_the_name_is_kept(party)
        assert queue == ["Michael", "Michael", "Sue"]

    def test_the_songs_settings_follow_the_guest_to_the_new_name(self, party):
        rename(party, "Michael")

        assert party.singers.settings_for("Michael") == SingerSettings(2, 0.7)


class TestEveryCopyMovesBeforeAnyoneIsTold:
    def test_a_notification_that_raises_still_saves_with_every_copy_moved_and_logs_it(
        self, party, caplog
    ):
        def fail(*_args):
            raise RuntimeError("socket gone")

        party.events.on("queue_update", fail)

        held = rename(party, "Michael")

        assert held == ("Michael", party.token)
        assert where_the_name_is_kept(party) == (["Michael", "Michael"], ["Michael"], "Michael")
        assert party.singers.lookup(party.token) == ("Michael", SingerSettings(2, 0.7))
        [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert "'Mike' -> 'Michael'" in record.getMessage()
        assert record.exc_info is not None and "socket gone" in str(record.exc_info[1])


class TestNotifications:
    @pytest.fixture
    def pushed(self, party):
        names = []
        party.events.on("queue_update", lambda: names.append("queue_update"))
        party.events.on("now_playing_update", lambda: names.append("now_playing_update"))
        return names

    def test_the_queue_and_the_playing_song_moving_send_one_of_each(self, party, pushed):
        rename(party, "Michael")

        assert pushed == ["queue_update", "now_playing_update"]

    def test_only_the_queue_moving_sends_both(self, party, pushed):
        party.playback.now_playing_user = "Sue"

        rename(party, "Michael")

        assert pushed == ["queue_update", "now_playing_update"]

    def test_only_the_playing_song_moving_sends_now_playing_alone(self, party, pushed):
        party.karaoke.queue_manager.queue.clear()

        rename(party, "Michael")

        assert pushed == ["now_playing_update"]

    def test_nothing_moving_sends_nothing(self, party, pushed):
        party.karaoke.queue_manager.queue.clear()
        party.playback.now_playing_user = "Sue"

        rename(party, "Michael")

        assert pushed == []

    def test_the_tv_overlay_refreshes_when_the_playing_song_moved(self, party):
        rename(party, "Michael")

        party.mpv.tick_overlays.assert_called_once_with()

    def test_the_tv_overlay_is_left_alone_when_another_guest_is_playing(self, party):
        party.playback.now_playing_user = "Sue"

        rename(party, "Michael")

        party.mpv.tick_overlays.assert_not_called()
