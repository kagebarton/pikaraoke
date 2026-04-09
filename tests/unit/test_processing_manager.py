"""Unit tests for processing_manager module."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.processing_manager import ProcessingManager


@pytest.fixture
def events():
    """Create a real EventSystem instance for testing."""
    return EventSystem()


@pytest.fixture
def preferences():
    """Create a mock PreferenceManager."""
    mock = MagicMock()
    mock.get_or_default.return_value = ""  # no blocked words
    return mock


@pytest.fixture
def manager(events, preferences):
    """Create a ProcessingManager without starting the worker."""
    return ProcessingManager(events=events, preferences=preferences)


class TestProcessingManagerInit:
    """Tests for ProcessingManager initialization."""

    def test_init_sets_state(self, manager):
        assert manager.pending_jobs == []
        assert manager._active_state is None
        assert manager._cancelled_paths == set()

    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    def test_start_subscribes_to_song_downloaded(self, mock_pt, mock_sw, events, preferences):
        mock_sw_instance = MagicMock()
        mock_sw.return_value = mock_sw_instance

        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()
        try:
            # The event subscription should route song_downloaded to enqueue.
            events.emit("song_downloaded", "/songs/Test---abc123.mp4")
            assert "/songs/Test---abc123.mp4" in mgr.pending_jobs
        finally:
            mgr.stop()


class TestProcessingManagerEnqueue:
    """Tests for enqueue behavior."""

    def test_enqueue_adds_to_queue_and_pending(self, manager):
        manager.enqueue("/songs/Song---abc123.mp4")
        assert manager.pending_jobs == ["/songs/Song---abc123.mp4"]
        assert manager._pending_queue.qsize() == 1

    def test_enqueue_multiple(self, manager):
        manager.enqueue("/songs/Song1---aaa111.mp4")
        manager.enqueue("/songs/Song2---bbb222.mp4")
        assert len(manager.pending_jobs) == 2
        assert manager._pending_queue.qsize() == 2

    def test_enqueue_blocked_word(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo,sample"
        mgr = ProcessingManager(events=events, preferences=prefs)
        mgr.enqueue("/songs/Demo Song---abc123.mp4")
        assert mgr.pending_jobs == []
        assert mgr._pending_queue.qsize() == 0


class TestProcessingManagerCancelPending:
    """Tests for cancel_pending behavior."""

    def test_cancel_pending_removes_from_list(self, manager):
        path = "/songs/Song---abc123.mp4"
        manager.enqueue(path)
        manager.cancel_pending(path)
        assert path not in manager.pending_jobs
        assert path in manager._cancelled_paths


class TestProcessingManagerCancelActive:
    """Tests for cancel_active behavior (mocked StemWorker)."""

    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    def test_cancel_active_stemming_kills_stem_worker(self, mock_pt, mock_sw, events, preferences):
        mock_sw_instance = MagicMock()
        mock_sw.return_value = mock_sw_instance

        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()

        # Manually set up an active state simulating the stemming step.
        from pikaraoke.lib.processing_manager import _JobState, _Step

        mgr._active_state = _JobState(song_path="/songs/Test---abc.mp4", step=_Step.STEMMING)

        mgr.cancel_active("/songs/Test---abc.mp4")
        mock_sw_instance.kill.assert_called_once()

        # Active state should be marked cancelled.
        assert mgr._active_state.cancelled is True

        mgr.stop()

    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    def test_cancel_active_extracting_kills_ffmpeg(self, mock_pt, mock_sw, events, preferences):
        mock_sw_instance = MagicMock()
        mock_sw.return_value = mock_sw_instance

        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()

        from pikaraoke.lib.processing_manager import _JobState, _Step

        mock_ffmpeg = MagicMock()
        mgr._active_state = _JobState(
            song_path="/songs/Test---abc.mp4",
            step=_Step.EXTRACTING,
            ffmpeg_process=mock_ffmpeg,
        )

        mgr.cancel_active("/songs/Test---abc.mp4")
        mock_ffmpeg.kill.assert_called_once()
        mock_sw_instance.kill.assert_not_called()

        mgr.stop()

    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    def test_cancel_active_non_active_is_noop(self, mock_pt, mock_sw, events, preferences):
        mock_sw_instance = MagicMock()
        mock_sw.return_value = mock_sw_instance

        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()
        mgr._active_state = None

        mgr.cancel_active("/songs/NotActive---xyz.mp4")
        mock_sw_instance.kill.assert_not_called()

        mgr.stop()


class TestProcessingManagerGetActiveJob:
    """Tests for get_active_job."""

    def test_get_active_job_returns_none_when_idle(self, manager):
        assert manager.get_active_job() is None

    def test_get_active_job_returns_path_when_active(self, manager):
        from pikaraoke.lib.processing_manager import _JobState, _Step

        manager._active_state = _JobState(song_path="/songs/Active---abc.mp4", step=_Step.STEMMING)
        assert manager.get_active_job() == "/songs/Active---abc.mp4"


class TestProcessingManagerCleanupStems:
    """Tests for _cleanup_stems helper."""

    def test_cleanup_removes_partial_stems(self, tmp_path, events, preferences):
        song = tmp_path / "Song---abc123.mp4"
        song.write_bytes(b"fake video")

        vocal_dir = tmp_path / "vocal"
        nonvocal_dir = tmp_path / "nonvocal"
        vocal_dir.mkdir()
        nonvocal_dir.mkdir()
        (vocal_dir / "Song---abc123---vocal.m4a").write_bytes(b"partial")
        (nonvocal_dir / "Song---abc123---nonvocal.m4a").write_bytes(b"partial")

        mgr = ProcessingManager(events=events, preferences=preferences, temp_dir=str(tmp_path))
        mgr._cleanup_stems(str(song))

        assert not (vocal_dir / "Song---abc123---vocal.m4a").exists()
        assert not (nonvocal_dir / "Song---abc123---nonvocal.m4a").exists()

    def test_cleanup_noop_when_no_stems(self, tmp_path, events, preferences):
        song = tmp_path / "Song---abc123.mp4"
        song.write_bytes(b"fake video")

        mgr = ProcessingManager(events=events, preferences=preferences, temp_dir=str(tmp_path))
        mgr._cleanup_stems(str(song))  # should not raise


class TestProcessingManagerOrchestratorIntegration:
    """Integration tests for the full orchestrator loop (with mocks)."""

    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    @patch("pikaraoke.lib.processing_manager.subprocess.Popen")
    def test_orchestrator_runs_full_pipeline_and_emits_complete(
        self, mock_popen, mock_pt, mock_sw, tmp_path, events, preferences
    ):
        """End-to-end: enqueue → orchestrator runs pipeline → event emitted."""

        song = tmp_path / "Test---abc123.mp4"
        song.write_bytes(b"fake video")
        wav_path = tmp_path / "Test---abc123_input.wav"
        vocal_wav = tmp_path / "Test---abc123_vocals.wav"
        inst_wav = tmp_path / "Test---abc123_instrumental.wav"
        (vocal_dir := tmp_path / "vocal").mkdir()
        (nonvocal_dir := tmp_path / "nonvocal").mkdir()

        # FFmpeg Popen mock: first call (extract) creates the WAV,
        # subsequent calls (transcode) succeed.
        call_count = 0

        def mock_popen_side(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            proc = MagicMock()
            proc.wait.return_value = 0
            if call_count == 1:
                # Extract step: write the input WAV
                wav_path.write_bytes(b"fake wav")
            return proc

        mock_popen.side_effect = mock_popen_side

        mock_sw_instance = MagicMock()
        mock_sw.return_value = mock_sw_instance
        mock_sw_instance.separate.return_value = (vocal_wav, inst_wav)
        mock_sw_instance.is_alive.return_value = True

        mgr = ProcessingManager(events=events, preferences=preferences, temp_dir=str(tmp_path))
        mgr.start()

        received_events = []

        def on_complete(path):
            received_events.append(("complete", path))

        events.on("processing_complete", on_complete)

        # Enqueue the song and wait for the orchestrator to finish.
        mgr.enqueue(str(song))
        deadline = time.monotonic() + 10
        while not received_events and time.monotonic() < deadline:
            time.sleep(0.1)

        mgr.stop()

        assert len(received_events) == 1
        assert received_events[0][0] == "complete"
        assert received_events[0][1] == str(song)
        # Verify full pipeline: extract (1) + 2 transcodes = 3 Popen calls.
        assert call_count == 3
        mock_sw_instance.separate.assert_called_once()

    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    @patch("pikaraoke.lib.processing_manager.subprocess.Popen")
    def test_cancel_during_extract_skips_stemming(
        self, mock_popen, mock_pt, mock_sw, tmp_path, events, preferences
    ):
        """Cancel during extract should not call separate()."""

        song = tmp_path / "Test---cancel1.mp4"
        song.write_bytes(b"fake video")

        cancel_happened = threading.Event()
        extract_happened = threading.Event()
        complete_received = threading.Event()

        def mock_popen_side(*args, **kwargs):
            extract_happened.set()
            # Wait for cancel to happen before returning.
            cancel_happened.wait(timeout=5)
            proc = MagicMock()
            proc.wait.return_value = -9  # killed
            return proc

        mock_popen.side_effect = mock_popen_side

        mock_sw_instance = MagicMock()
        mock_sw.return_value = mock_sw_instance
        mock_sw_instance.is_alive.return_value = True

        mgr = ProcessingManager(events=events, preferences=preferences, temp_dir=str(tmp_path))
        mgr.start()
        mgr.enqueue(str(song))

        # Wait for extract to start, then cancel.
        extract_happened.wait(timeout=5)
        mgr.cancel_active(str(song))
        cancel_happened.set()

        # Wait for processing to finish (cancel or complete).
        deadline = time.monotonic() + 10
        while not complete_received.is_set() and time.monotonic() < deadline:
            time.sleep(0.1)

        mgr.stop()

        # separate() should never have been called.
        mock_sw_instance.separate.assert_not_called()
