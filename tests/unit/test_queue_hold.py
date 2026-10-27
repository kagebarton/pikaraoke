"""Unit tests for QueueHold: a searched song's queue slot from the click until it is ready."""

from unittest.mock import MagicMock

import pytest

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.queue_hold import QueueHold
from pikaraoke.lib.queue_manager import QueueManager

URL = "https://www.youtube.com/watch?v=abc12345678"
SONG = "/songs/New Song---abc12345678.mp4"


def extract_title(path: str, *args) -> str:
    return path.split("/")[-1].split("---")[0]


@pytest.fixture
def events():
    return EventSystem()


@pytest.fixture
def preferences(tmp_path):
    return PreferenceManager(config_file_path=str(tmp_path / "config.ini"))


@pytest.fixture
def queue_manager(preferences, events):
    return QueueManager(
        preferences=preferences,
        events=events,
        get_now_playing_user=lambda: None,
        filename_from_path=extract_title,
    )


@pytest.fixture
def hold(queue_manager, events):
    return QueueHold(queue_manager, events, MagicMock())


@pytest.fixture
def toasts(events):
    """Every notification as (message, level)."""
    captured = []
    events.on("notification", lambda message, level="info": captured.append((message, level)))
    return captured


@pytest.fixture
def queue_events(events):
    """Names of the queue events emitted after this fixture is requested."""
    captured = []
    events.on("queue_update", lambda: captured.append("queue_update"))
    events.on("now_playing_update", lambda: captured.append("now_playing_update"))
    return captured


def click(events, enqueue=True, user="Alice", title="New Song"):
    events.emit(
        "download_queued",
        {"video_url": URL, "enqueue": enqueue, "user": user, "title": title},
    )


def hold_item(queue_manager, waiting, file=SONG, user="Alice"):
    queue_manager.enqueue(file, user, waiting=waiting, title="New Song", log_action=False)
    return queue_manager.queue[-1]


class TestWaitingFor:
    @pytest.mark.parametrize(
        "waiting_for_pick,busy,expected",
        [(True, False, "pick"), (False, True, "processing"), (False, False, None)],
    )
    def test_names_what_the_song_is_waiting_on(
        self, queue_manager, events, waiting_for_pick, busy, expected
    ):
        library_tools = MagicMock()
        library_tools.is_waiting_for_pick.return_value = waiting_for_pick
        library_tools.is_busy.return_value = busy

        assert QueueHold(queue_manager, events, library_tools).waiting_for(SONG) == expected

    def test_the_pick_is_checked_before_busy(self, queue_manager, events):
        library_tools = MagicMock()
        library_tools.is_waiting_for_pick.return_value = True
        library_tools.is_busy.return_value = True

        assert QueueHold(queue_manager, events, library_tools).waiting_for(SONG) == "pick"


class TestDownloadQueued:
    def test_holds_a_slot_keyed_by_the_url(self, hold, queue_manager, events):
        click(events)

        [item] = queue_manager.queue
        assert (item["file"], item["waiting"]) == (URL, "download")
        assert (item["user"], item["title"]) == ("Alice", "New Song")

    def test_a_library_only_download_adds_nothing(self, hold, queue_manager, events):
        click(events, enqueue=False)

        assert queue_manager.queue == []

    def test_a_user_at_their_limit_gets_the_warning_and_no_item(
        self, hold, queue_manager, preferences, events, toasts
    ):
        preferences.set("limit_user_songs_by", 1)
        queue_manager.enqueue("/songs/Other---zzz11111111.mp4", "Alice")
        del toasts[:]

        click(events)

        assert [item["file"] for item in queue_manager.queue] == ["/songs/Other---zzz11111111.mp4"]
        [(message, level)] = toasts
        assert "limit" in message
        assert level == "warning"


class TestSongDownloaded:
    def test_the_item_takes_the_library_path_and_waits_for_processing(
        self, hold, queue_manager, events, queue_events
    ):
        click(events)
        del queue_events[:]

        events.emit("song_downloaded", SONG)

        [item] = queue_manager.queue
        assert (item["file"], item["waiting"]) == (SONG, "processing")
        assert queue_events == ["queue_update", "now_playing_update"]

    def test_a_download_nobody_holds_a_slot_for_changes_nothing(self, hold, queue_manager, events):
        click(events)

        events.emit("song_downloaded", "/songs/Else---zzz11111111.mp4")

        assert [(i["file"], i["waiting"]) for i in queue_manager.queue] == [(URL, "download")]

    def test_a_path_with_no_video_id_matches_nothing(self, hold, queue_manager, events):
        click(events)

        events.emit("song_downloaded", "/songs/No Id.mp4")

        assert queue_manager.queue[0]["file"] == URL

    def test_a_song_already_in_the_queue_frees_the_held_slot(
        self, hold, queue_manager, events, toasts
    ):
        click(events)
        queue_manager.enqueue(SONG, "Bob")
        del toasts[:]

        events.emit("song_downloaded", SONG)

        assert [(i["file"], i["user"]) for i in queue_manager.queue] == [(SONG, "Bob")]
        assert toasts == [("Already in the queue: New Song", "warning")]


class TestProcessingEvents:
    def test_needs_pick_then_processing_queued_after_the_pick(self, hold, queue_manager, events):
        item = hold_item(queue_manager, "processing")

        events.emit("needs_pick", SONG)
        assert item["waiting"] == "pick"

        events.emit("processing_queued", SONG)
        assert item["waiting"] == "processing"

    def test_processing_complete_releases_the_item(self, hold, queue_manager, events, queue_events):
        hold_item(queue_manager, "processing")
        del queue_events[:]

        events.emit("processing_complete", {"song_path": SONG, "lyric_method": None})

        assert queue_manager.queue[0]["waiting"] is None
        assert queue_events == ["queue_update", "now_playing_update"]
        assert queue_manager.pop_next()["file"] == SONG

    def test_processing_skipped_releases_the_item(self, hold, queue_manager, events):
        hold_item(queue_manager, "processing")

        events.emit("processing_skipped", SONG)

        assert queue_manager.queue[0]["waiting"] is None

    def test_processing_error_removes_the_item_and_tells_the_singer(
        self, hold, queue_manager, events, toasts
    ):
        hold_item(queue_manager, "processing")

        events.emit("processing_error", {"song_path": SONG, "error": "boom"})

        assert queue_manager.queue == []
        assert toasts == [("New Song couldn't be processed and was taken off the queue", "danger")]

    @pytest.mark.parametrize("event", ["processing_cancelled", "song_deleted"])
    def test_cancel_and_delete_remove_the_item_quietly(
        self, event, hold, queue_manager, events, toasts
    ):
        hold_item(queue_manager, "processing")

        events.emit(event, SONG)

        assert queue_manager.queue == []
        assert toasts == []

    def test_another_songs_event_leaves_the_item_alone(self, hold, queue_manager, events):
        item = hold_item(queue_manager, "processing")

        events.emit("processing_complete", {"song_path": "/songs/Else---zzz11111111.mp4"})
        events.emit("processing_error", {"song_path": "/songs/Else---zzz11111111.mp4"})

        assert queue_manager.queue == [item]
        assert item["waiting"] == "processing"


class TestReadyItemsAreNeverTouched:
    """processing_complete also fires for regen jobs of songs already in the queue."""

    @pytest.mark.parametrize(
        "event,payload",
        [
            ("processing_complete", {"song_path": SONG, "lyric_method": None}),
            ("processing_skipped", SONG),
            ("processing_error", {"song_path": SONG, "error": "boom"}),
            ("processing_cancelled", SONG),
            ("song_deleted", SONG),
            ("needs_pick", SONG),
            ("processing_queued", SONG),
        ],
    )
    def test_a_ready_item_ignores_every_processing_event(
        self, event, payload, hold, queue_manager, events, toasts, queue_events
    ):
        item = hold_item(queue_manager, None)
        del queue_events[:]

        events.emit(event, payload)

        assert queue_manager.queue == [item]
        assert item["waiting"] is None
        assert queue_events == []
        assert toasts == []


class TestDownloadFailed:
    @pytest.mark.parametrize("event", ["download_error", "download_cancelled"])
    def test_a_failed_or_cancelled_download_removes_the_item_quietly(
        self, event, hold, queue_manager, events, toasts
    ):
        click(events)
        del toasts[:]

        payload = {"url": URL, "error": "boom"} if event == "download_error" else {"url": URL}
        events.emit(event, payload)

        assert queue_manager.queue == []
        assert toasts == []

    def test_another_urls_failure_leaves_the_item_alone(self, hold, queue_manager, events):
        click(events)

        events.emit("download_error", {"url": "https://www.youtube.com/watch?v=zzz11111111"})

        assert [i["file"] for i in queue_manager.queue] == [URL]


class TestWiringOrder:
    def test_an_event_emitted_inside_song_downloaded_finds_the_path_set(
        self, queue_manager, events
    ):
        """LibraryTools emits processing events synchronously from its song_downloaded handler."""
        QueueHold(queue_manager, events, MagicMock())
        events.on("song_downloaded", lambda path: events.emit("processing_skipped", path))
        click(events)

        events.emit("song_downloaded", SONG)

        [item] = queue_manager.queue
        assert (item["file"], item["waiting"]) == (SONG, None)
