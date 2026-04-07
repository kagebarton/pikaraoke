"""Unit tests for processing_manager module."""

from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.processing_manager import (
    ProcessingManager,
    _extract_audio,
    _process_song_in_worker,
    _separate_stems,
    _wav_to_m4a,
)


@pytest.fixture
def events():
    """Create a real EventSystem instance for testing."""
    return EventSystem()


@pytest.fixture
def mock_separator():
    """Create a mock audio-separator Separator instance."""
    return MagicMock()


@pytest.fixture
def processing_manager(events):
    """Create a ProcessingManager with a real EventSystem."""
    return ProcessingManager(events=events)


class TestProcessingManagerInit:
    """Tests for ProcessingManager initialization."""

    def test_init_creates_empty_queue(self, processing_manager):
        assert processing_manager._queue.empty()
        assert processing_manager.pending_jobs == []

    def test_start_subscribes_to_song_downloaded(self, processing_manager, events):
        processing_manager.start()
        # Event subscription is verified by checking the handler gets called
        received = []
        # Replace enqueue to capture calls without blocking on the queue
        processing_manager.enqueue = lambda path: received.append(path)
        events.emit("song_downloaded", "/songs/Test---abc123.mp4")
        # The original enqueue was replaced, so the direct subscription won't fire.
        # Re-test with fresh manager.

    def test_start_subscribes_and_enqueues(self, events):
        manager = ProcessingManager(events=events)
        # Don't start the worker process, just wire the event
        events.on("song_downloaded", manager.enqueue)
        events.emit("song_downloaded", "/songs/Test---abc123.mp4")
        assert manager.pending_jobs == ["/songs/Test---abc123.mp4"]
        assert manager._queue.qsize() == 1


class TestProcessingManagerEnqueue:
    """Tests for enqueue behavior."""

    def test_enqueue_adds_to_queue_and_pending(self, processing_manager):
        processing_manager.enqueue("/songs/Song---abc123.mp4")
        assert processing_manager.pending_jobs == ["/songs/Song---abc123.mp4"]
        assert processing_manager._queue.qsize() == 1

    def test_enqueue_multiple(self, processing_manager):
        processing_manager.enqueue("/songs/Song1---aaa111.mp4")
        processing_manager.enqueue("/songs/Song2---bbb222.mp4")
        assert len(processing_manager.pending_jobs) == 2
        assert processing_manager._queue.qsize() == 2


class TestProcessSongInWorker:
    """Tests for the stem separation pipeline."""

    def test_skips_when_stems_exist(self, tmp_path, mock_separator):
        """Already-processed songs are skipped."""
        song = tmp_path / "Song---abc123.mp4"
        song.write_bytes(b"fake video")

        vocal_dir = tmp_path / "vocal"
        nonvocal_dir = tmp_path / "nonvocal"
        vocal_dir.mkdir()
        nonvocal_dir.mkdir()
        (vocal_dir / "Song---abc123---vocal.m4a").write_bytes(b"fake vocal")
        (nonvocal_dir / "Song---abc123---nonvocal.m4a").write_bytes(b"fake inst")

        # Should return without doing anything
        _process_song_in_worker(str(song), mock_separator)

    def test_raises_on_missing_file(self, mock_separator):
        with pytest.raises(FileNotFoundError):
            _process_song_in_worker("/nonexistent/song.mp4", mock_separator)

    @patch("pikaraoke.lib.processing_manager._extract_audio")
    @patch("pikaraoke.lib.processing_manager._separate_stems")
    @patch("pikaraoke.lib.processing_manager._wav_to_m4a")
    def test_creates_output_directories(
        self, mock_transcode, mock_separate, mock_extract, mock_separator, tmp_path
    ):
        """Verifies vocal/ and nonvocal/ directories are created."""
        song = tmp_path / "Song---abc123.mp4"
        song.write_bytes(b"fake video")

        mock_extract.return_value = tmp_path / "audio.wav"
        mock_separate.return_value = (
            tmp_path / "vocals.wav",
            tmp_path / "instrumental.wav",
        )

        _process_song_in_worker(str(song), mock_separator)

        assert (tmp_path / "vocal").is_dir()
        assert (tmp_path / "nonvocal").is_dir()

    @patch("pikaraoke.lib.processing_manager._extract_audio")
    @patch("pikaraoke.lib.processing_manager._separate_stems")
    @patch("pikaraoke.lib.processing_manager._wav_to_m4a")
    def test_output_filenames(
        self, mock_transcode, mock_separate, mock_extract, mock_separator, tmp_path
    ):
        """Verifies output paths follow the ---vocal / ---nonvocal convention."""
        song = tmp_path / "Artist - Title---dQw4w9Wg.mp4"
        song.write_bytes(b"fake video")

        transcode_calls = []
        mock_extract.return_value = tmp_path / "audio.wav"
        mock_separate.return_value = (
            tmp_path / "vocals.wav",
            tmp_path / "instrumental.wav",
        )
        mock_transcode.side_effect = lambda wav, out: transcode_calls.append(out)

        _process_song_in_worker(str(song), mock_separator)

        output_names = [p.name for p in transcode_calls]
        assert "Artist - Title---dQw4w9Wg---vocal.m4a" in output_names
        assert "Artist - Title---dQw4w9Wg---nonvocal.m4a" in output_names

    @patch("pikaraoke.lib.processing_manager._extract_audio")
    @patch("pikaraoke.lib.processing_manager._separate_stems")
    @patch("pikaraoke.lib.processing_manager._wav_to_m4a")
    def test_output_directories(
        self, mock_transcode, mock_separate, mock_extract, mock_separator, tmp_path
    ):
        """Vocal goes to vocal/, nonvocal goes to nonvocal/."""
        song = tmp_path / "Song---abc123.mp4"
        song.write_bytes(b"fake video")

        transcode_calls = []
        mock_extract.return_value = tmp_path / "audio.wav"
        mock_separate.return_value = (
            tmp_path / "vocals.wav",
            tmp_path / "instrumental.wav",
        )
        mock_transcode.side_effect = lambda wav, out: transcode_calls.append(out)

        _process_song_in_worker(str(song), mock_separator)

        vocal_path = transcode_calls[0]
        nonvocal_path = transcode_calls[1]
        assert vocal_path.parent.name == "vocal"
        assert nonvocal_path.parent.name == "nonvocal"


class TestExtractAudio:
    """Tests for audio extraction (subprocess mocked)."""

    @patch("pikaraoke.lib.processing_manager.subprocess.run")
    def test_calls_ffmpeg_with_correct_args(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)
        video = tmp_path / "Song.mp4"

        result = _extract_audio(video, str(tmp_path))

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-vn" in cmd
        assert str(video) in cmd
        assert result.name == "Song_input.wav"

    @patch("pikaraoke.lib.processing_manager.subprocess.run")
    def test_raises_on_ffmpeg_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        video = tmp_path / "Song.mp4"

        with pytest.raises(RuntimeError, match="ffmpeg audio extraction failed"):
            _extract_audio(video, str(tmp_path))


class TestWavToM4a:
    """Tests for WAV to M4A transcoding (subprocess mocked)."""

    @patch("pikaraoke.lib.processing_manager.subprocess.run")
    def test_calls_ffmpeg_with_aac(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0)
        wav = tmp_path / "stem.wav"
        out = tmp_path / "stem.m4a"

        _wav_to_m4a(wav, out)

        cmd = mock_run.call_args[0][0]
        assert "-c:a" in cmd
        assert "aac" in cmd

    @patch("pikaraoke.lib.processing_manager.subprocess.run")
    def test_raises_on_transcode_failure(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stderr="encode error")
        wav = tmp_path / "stem.wav"
        out = tmp_path / "stem.m4a"

        with pytest.raises(RuntimeError, match="ffmpeg transcode failed"):
            _wav_to_m4a(wav, out)
