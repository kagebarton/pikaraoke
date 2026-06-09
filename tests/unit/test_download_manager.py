"""Unit tests for download_manager module."""

from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.download_manager import DownloadManager
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.preference_manager import PreferenceManager


@pytest.fixture
def events():
    """Create a real EventSystem instance for testing."""
    return EventSystem()


@pytest.fixture
def preferences():
    """Create a real PreferenceManager instance for testing."""
    return PreferenceManager()


@pytest.fixture
def song_manager():
    """Create a mock SongManager."""
    mock = MagicMock()
    mock.songs = MagicMock()
    return mock


@pytest.fixture
def queue_manager():
    """Create a mock QueueManager."""
    return MagicMock()


@pytest.fixture
def download_manager(events, preferences, song_manager, queue_manager):
    """Create a DownloadManager with real Events/Prefs and mocked managers."""
    return DownloadManager(
        events=events,
        preferences=preferences,
        song_manager=song_manager,
        queue_manager=queue_manager,
        download_path="/songs",
        youtubedl_proxy=None,
        additional_ytdl_args=None,
    )


class TestDownloadManagerInit:
    """Tests for DownloadManager initialization."""

    def test_init_creates_queue(self, download_manager):
        """Test that init creates an empty queue."""
        assert download_manager.download_queue.empty()
        assert download_manager._is_downloading is False
        assert download_manager._worker_thread is None

    def test_start_creates_worker_thread(self, download_manager):
        """Test that start creates and starts a daemon thread."""
        download_manager.start()

        assert download_manager._worker_thread is not None
        assert download_manager._worker_thread.daemon is True
        assert download_manager._worker_thread.is_alive()


class TestDownloadManagerQueueDownload:
    """Tests for DownloadManager.queue_download method."""

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_queue_download_first_item(self, mock_gettext, download_manager, events):
        """Test queueing first download shows 'starting' message and emits event."""
        notifications = []
        events.on("notification", lambda msg, *args: notifications.append(msg))

        download_manager.queue_download("https://youtube.com/watch?v=test", user="TestUser")

        assert download_manager.download_queue.qsize() == 1
        assert len(notifications) == 1
        assert "Download starting" in notifications[0]

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_queue_download_with_pending(self, mock_gettext, download_manager, events):
        """Test queueing when items are pending shows queue position."""
        notifications = []
        events.on("notification", lambda msg, *args: notifications.append(msg))

        download_manager._is_downloading = True  # Simulate active download

        download_manager.queue_download("https://youtube.com/watch?v=test", user="TestUser")

        assert len(notifications) == 1
        assert "Download queued" in notifications[0]

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_queue_download_with_title(self, mock_gettext, download_manager, events):
        """Test queueing with custom title uses title in message."""
        notifications = []
        events.on("notification", lambda msg, *args: notifications.append(msg))

        download_manager.queue_download(
            "https://youtube.com/watch?v=test",
            title="My Custom Title",
            user="TestUser",
        )

        assert len(notifications) == 1
        assert "My Custom Title" in notifications[0]

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_queue_download_stores_request_data(self, mock_gettext, download_manager):
        """Test that queue stores all request data."""
        download_manager.queue_download(
            "https://youtube.com/watch?v=test123",
            enqueue=True,
            user="TestUser",
            title="Test Song",
        )

        item = download_manager.download_queue.get_nowait()
        assert item["video_url"] == "https://youtube.com/watch?v=test123"
        assert item["enqueue"] is True
        assert item["user"] == "TestUser"
        assert item["title"] == "Test Song"

    @patch("flask_babel._", side_effect=lambda x: x)
    def test_queue_download_strips_playlist_param(self, mock_gettext, download_manager):
        """Test that playlist parameter is stripped from URL."""
        download_manager.queue_download(
            "https://youtube.com/watch?v=test123&list=PLxxx",
            user="TestUser",
        )

        item = download_manager.download_queue.get_nowait()
        assert item["video_url"] == "https://youtube.com/watch?v=test123"


class TestDownloadManagerExecuteDownload:
    """Tests for DownloadManager._execute_download method."""

    @patch("flask_babel._", side_effect=lambda x: x)
    @patch("subprocess.Popen")
    @patch("pikaraoke.lib.download_manager.build_ytdl_download_command")
    def test_execute_download_success(
        self, mock_build_cmd, mock_popen, mock_gettext, download_manager, song_manager, events
    ):
        """Test successful download execution."""
        notifications = []
        events.on("notification", lambda msg, *args: notifications.append(msg))

        mock_build_cmd.return_value = ["yt-dlp", "-o", "/songs/", "url"]

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("Starting download...", None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock find_by_id to return a path
        song_manager.songs.find_by_id.return_value = "/songs/Artist - Song---abc123.mp4"

        # Mock Path.mkdir to avoid filesystem operations
        with patch("pathlib.Path.mkdir"):
            rc = download_manager._execute_download(
                "https://youtube.com/watch?v=abc123", False, "User", "Title"
            )

        assert rc == 0
        song_manager.songs.find_by_id.assert_called_once_with("/songs", "abc123")
        # add_if_valid is no longer called directly; a "song_downloaded" event is emitted instead
        assert any("Downloaded" in n for n in notifications)

    @patch("flask_babel._", side_effect=lambda x: x)
    @patch("subprocess.Popen")
    @patch("pikaraoke.lib.download_manager.build_ytdl_download_command")
    def test_execute_download_with_enqueue(
        self,
        mock_build_cmd,
        mock_popen,
        mock_gettext,
        download_manager,
        song_manager,
        queue_manager,
    ):
        """Test download with enqueue adds to queue."""
        mock_build_cmd.return_value = ["yt-dlp", "url"]

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("Starting download...", None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock find_by_id
        song_manager.songs.find_by_id.return_value = "/songs/Song---abc.mp4"
        song_manager.songs.add_if_valid.return_value = True

        # Mock Path.mkdir to avoid filesystem operations
        with patch("pathlib.Path.mkdir"):
            download_manager._execute_download(
                "https://youtube.com/watch?v=abc", True, "TestUser", "Title"
            )

        queue_manager.enqueue.assert_called_once_with(
            "/songs/Song---abc.mp4", "TestUser", log_action=False
        )

    @patch("flask_babel._", side_effect=lambda x: x)
    @patch("subprocess.Popen")
    @patch("pikaraoke.lib.download_manager.build_ytdl_download_command")
    def test_execute_download_failure(
        self, mock_build_cmd, mock_popen, mock_gettext, download_manager, events
    ):
        """Test download failure is handled without retry."""
        notifications = []
        events.on("notification", lambda msg, cat="info": notifications.append((msg, cat)))

        mock_build_cmd.return_value = ["yt-dlp", "url"]

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", None)
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        rc = download_manager._execute_download("url", False, "User", "Title")

        assert rc == 1
        # Should have "Error downloading" message with danger category
        assert any("Error downloading" in msg and cat == "danger" for msg, cat in notifications)

    @patch("flask_babel._", side_effect=lambda x: x)
    @patch("subprocess.Popen")
    @patch("pikaraoke.lib.download_manager.build_ytdl_download_command")
    def test_execute_download_enqueue_without_path(
        self, mock_build_cmd, mock_popen, mock_gettext, download_manager, song_manager, events
    ):
        """Test enqueue fails gracefully when path can't be parsed."""
        notifications = []
        events.on("notification", lambda msg, cat="info": notifications.append((msg, cat)))

        mock_build_cmd.return_value = ["yt-dlp", "url"]

        mock_process = MagicMock()
        mock_process.communicate.return_value = ("No parseable path in output", None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        # Mock find_by_id to return None (file not found)
        song_manager.songs.find_by_id.return_value = None

        download_manager._execute_download("https://youtube.com/watch?v=abc", True, "User", "Title")

        # Should log error about queueing
        assert any("Error queueing" in msg and cat == "danger" for msg, cat in notifications)


class TestDownloadManagerSpecialCharacters:
    """Tests for handling special characters in downloaded filenames.

    These tests prevent regressions where special characters in song titles
    (common in non-English songs) break the enqueue functionality.
    See commit f399b57 for the original fix.
    """

    @pytest.mark.parametrize(
        "video_id,file_path",
        [
            ("abc12345678", "/songs/Babymetal - ギミチョコ---abc12345678.mp4"),
            ("xyz98765432", "/songs/BTS - 봄날---xyz98765432.mp4"),
            ("def456789ab", "/songs/Tom & Jerry - What's Up---def456789ab.mp4"),
        ],
        ids=["japanese", "korean", "special_chars"],
    )
    @patch("flask_babel._", side_effect=lambda x: x)
    @patch("subprocess.Popen")
    @patch("pikaraoke.lib.download_manager.build_ytdl_download_command")
    def test_execute_download_special_characters_enqueue(
        self,
        mock_build_cmd,
        mock_popen,
        mock_gettext,
        video_id,
        file_path,
        download_manager,
        song_manager,
        queue_manager,
    ):
        """Test enqueue works with special characters in filename."""
        mock_build_cmd.return_value = ["yt-dlp", "url"]
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("Done", None)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process

        song_manager.songs.find_by_id.return_value = file_path
        song_manager.songs.add_if_valid.return_value = True

        # Mock Path.mkdir to avoid filesystem operations
        with patch("pathlib.Path.mkdir"):
            download_manager._execute_download(
                f"https://youtube.com/watch?v={video_id}",
                enqueue=True,
                user="TestUser",
                title="Test",
            )

        queue_manager.enqueue.assert_called_once_with(file_path, "TestUser", log_action=False)

    def test_move_downloaded_subtitle_bracketed_title(self, download_manager, tmp_path):
        """Subtitle move must handle glob metacharacters in the title (e.g. [Live]).

        Regression: an unescaped glob on video.stem treats '[Live]' as a character
        class, so the .srt is never found/moved and the alignment pipeline gets nothing.
        """
        stem = "Song [Live]---abc12345678"
        video = tmp_path / f"{stem}.mp4"
        video.write_text("x")
        srt = tmp_path / f"{stem}.en.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")

        download_manager._move_downloaded_subtitle(str(video))

        moved = tmp_path / "subtitles" / f"{stem}.srt"
        assert moved.exists(), "subtitle should move into subtitles/ even with [brackets] in title"
        assert not srt.exists(), "original subtitle should be removed after the move"


class TestCancelActiveDownload:
    """Tests for cancelling the in-flight download (process kill + partial cleanup)."""

    def test_cancel_kills_process_and_cleans_only_matching_partials(
        self, download_manager, tmp_path
    ):
        """Cancel must kill yt-dlp and delete the active song's partials, leaving the
        rest of the library intact — including songs whose titles contain glob
        metacharacters like '[Live]'.

        Regression: cleanup keyed on a bracketed ``[VIDEOID]`` would be read as a glob
        character class and could match (and unlink) unrelated songs. Matching on the
        bare 11-char ID keeps it literal-safe.
        """
        download_manager._download_path = str(tmp_path)
        active_id = "dQw4w9WgXcQ"
        active_url = f"https://www.youtube.com/watch?v={active_id}"

        active_partials = [
            tmp_path / f"Cancelled Song [{active_id}].mp4.part",
            tmp_path / f"Cancelled Song---{active_id}.webm",
        ]
        keepers = [
            tmp_path / "Keeper [oHg5SJYRHA0].mp4",
            tmp_path / "Live At [Live] [9bZkp7q19f0].mp4",
        ]
        for f in active_partials + keepers:
            f.write_text("x")

        proc = MagicMock()
        download_manager._active_process = proc
        download_manager.active_url = active_url
        download_manager._is_downloading = True

        download_manager.cancel_active_download(active_url)

        proc.kill.assert_called_once()
        assert download_manager._active_process is None
        assert download_manager.active_url is None
        assert download_manager._is_downloading is False
        for f in active_partials:
            assert not f.exists(), f"active partial {f.name} should be cleaned up"
        for f in keepers:
            assert f.exists(), f"unrelated library file {f.name} must survive cancel"

    def test_cancel_cleans_partials_in_separate_temp_dir(self, download_manager, tmp_path):
        """With a separate temp_dir, yt-dlp writes .part/merge intermediates there via
        ``--paths temp:``; cancel must sweep that directory too, keyed on the active id,
        or the partials orphan (unrelated temp files must survive)."""
        songs_dir = tmp_path / "songs"
        temp_dir = tmp_path / "temp"
        songs_dir.mkdir()
        temp_dir.mkdir()
        download_manager._download_path = str(songs_dir)
        download_manager._temp_dir = str(temp_dir)
        active_id = "dQw4w9WgXcQ"
        active_url = f"https://www.youtube.com/watch?v={active_id}"

        temp_partials = [
            temp_dir / f"Cancelled Song [{active_id}].mp4.part",
            temp_dir / f"Cancelled Song---{active_id}.f137.mp4",
        ]
        temp_keeper = temp_dir / "Other [oHg5SJYRHA0].mp4.part"
        for f in temp_partials + [temp_keeper]:
            f.write_text("x")

        download_manager._active_process = MagicMock()
        download_manager.active_url = active_url
        download_manager._is_downloading = True

        download_manager.cancel_active_download(active_url)

        for f in temp_partials:
            assert not f.exists(), f"temp partial {f.name} should be cleaned up"
        assert temp_keeper.exists(), "an unrelated download's temp partial must survive"

    def test_cancel_with_mismatched_url_is_noop(self, download_manager, tmp_path):
        """A stale cancel (target URL no longer the active one) must not kill the
        process or touch the library — the active download has moved on."""
        download_manager._download_path = str(tmp_path)
        active_id = "dQw4w9WgXcQ"
        active_url = f"https://www.youtube.com/watch?v={active_id}"
        partial = tmp_path / f"Now Playing [{active_id}].mp4.part"
        partial.write_text("x")

        proc = MagicMock()
        download_manager._active_process = proc
        download_manager.active_url = active_url
        download_manager._is_downloading = True

        download_manager.cancel_active_download("https://www.youtube.com/watch?v=oHg5SJYRHA0")

        proc.kill.assert_not_called()
        assert download_manager._active_process is proc
        assert download_manager.active_url == active_url
        assert download_manager._is_downloading is True
        assert partial.exists(), "a mismatched cancel must not clean another download's files"
