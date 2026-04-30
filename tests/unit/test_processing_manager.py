"""Unit tests for ProcessingManager (thin adapter over PipelineOrchestrator)."""

import threading
from unittest.mock import MagicMock, call, patch

import pytest

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.processing_manager import ProcessingManager, _ActiveJob
from pikaraoke.pipeline.context import CancelToken, PipelineCancelled, StageContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def events():
    """Real EventSystem — keeps handler behaviour honest."""
    return EventSystem()


@pytest.fixture
def preferences():
    """Mock PreferenceManager with no blocked words."""
    mock = MagicMock()
    mock.get_or_default.return_value = ""
    return mock


@pytest.fixture
def song_manager():
    """Mock SongManager."""
    return MagicMock()


@pytest.fixture
def mock_orchestrator():
    """Mock PipelineOrchestrator — avoids spawning real threads/workers."""
    orch = MagicMock()
    token = CancelToken(event=threading.Event())
    orch.run_one_async.return_value = token
    return orch


@pytest.fixture
def manager(events, preferences):
    """ProcessingManager without start() — orchestrator replaced by mock after construction."""
    return ProcessingManager(events=events, preferences=preferences)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_pending_jobs_empty(self, manager):
        assert manager.pending_jobs == []

    def test_active_none(self, manager):
        assert manager._active is None

    def test_cancelled_paths_empty(self, manager):
        assert manager._cancelled_paths == set()

    def test_pending_queue_empty(self, manager):
        assert manager._pending_queue.qsize() == 0


# ---------------------------------------------------------------------------
# start() — event subscription
# ---------------------------------------------------------------------------


class TestStart:
    @patch("pikaraoke.lib.processing_manager.is_windows", return_value=True)
    @patch("pikaraoke.lib.processing_manager.get_temp_directory", return_value="/tmp/pk")
    @patch("pikaraoke.lib.processing_manager.build_whisper_config")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    @patch("pikaraoke.lib.processing_manager.WhisperWorker")
    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.PipelineOrchestrator")
    def test_start_subscribes_song_downloaded(
        self,
        mock_orch_cls,
        mock_sw_cls,
        mock_ww_cls,
        mock_pt_cls,
        mock_bwc,
        mock_gtd,
        mock_iw,
        events,
        preferences,
    ):
        """song_downloaded event routes to enqueue(), putting path in pending_jobs."""
        mock_orch_inst = MagicMock()
        mock_orch_cls.return_value = mock_orch_inst
        mock_sw_cls.return_value = MagicMock()
        mock_ww_cls.return_value = MagicMock()

        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()
        try:
            events.emit("song_downloaded", "/songs/Test---abc123.mp4")
            assert "/songs/Test---abc123.mp4" in mgr.pending_jobs
        finally:
            mgr.stop()


# ---------------------------------------------------------------------------
# enqueue()
# ---------------------------------------------------------------------------


class TestEnqueue:
    def test_adds_to_pending_jobs_and_queue(self, manager):
        manager.enqueue("/songs/Song---abc123.mp4")
        assert "/songs/Song---abc123.mp4" in manager.pending_jobs
        assert manager._pending_queue.qsize() == 1

    def test_multiple_songs(self, manager):
        manager.enqueue("/songs/A---aaa111.mp4")
        manager.enqueue("/songs/B---bbb222.mp4")
        assert len(manager.pending_jobs) == 2
        assert manager._pending_queue.qsize() == 2

    def test_blocked_word_skips_enqueue(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo,sample"
        mgr = ProcessingManager(events=events, preferences=prefs)
        mgr.enqueue("/songs/Demo Song---abc123.mp4")
        assert mgr.pending_jobs == []
        assert mgr._pending_queue.qsize() == 0

    def test_blocked_word_emits_processing_skipped(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo"
        mgr = ProcessingManager(events=events, preferences=prefs)
        received = []
        events.on("processing_skipped", received.append)
        mgr.enqueue("/songs/Demo Song---abc123.mp4")
        assert received == ["/songs/Demo Song---abc123.mp4"]

    def test_blocked_word_sets_pipeline_state_skipped(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo"
        sm = MagicMock()
        mgr = ProcessingManager(events=events, preferences=prefs, song_manager=sm)
        mgr.enqueue("/songs/Demo Song---abc123.mp4")
        sm.set_pipeline_state.assert_called_once_with("/songs/Demo Song---abc123.mp4", "skipped")

    def test_blocked_word_no_song_manager_does_not_raise(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo"
        mgr = ProcessingManager(events=events, preferences=prefs, song_manager=None)
        # Should complete without AttributeError
        mgr.enqueue("/songs/Demo Song---abc123.mp4")

    def test_non_blocked_word_does_not_emit_skipped(self, events, preferences):
        received = []
        events.on("processing_skipped", received.append)
        manager = ProcessingManager(events=events, preferences=preferences)
        manager.enqueue("/songs/Song---abc123.mp4")
        assert received == []


# ---------------------------------------------------------------------------
# cancel_pending()
# ---------------------------------------------------------------------------


class TestCancelPending:
    def test_removes_from_pending_jobs(self, manager):
        path = "/songs/Song---abc123.mp4"
        manager.enqueue(path)
        manager.cancel_pending(path)
        assert path not in manager.pending_jobs

    def test_adds_to_cancelled_paths(self, manager):
        path = "/songs/Song---abc123.mp4"
        manager.enqueue(path)
        manager.cancel_pending(path)
        assert path in manager._cancelled_paths

    def test_cancel_pending_not_in_queue_still_marks_cancelled(self, manager):
        """cancel_pending on a path not yet enqueued still adds to _cancelled_paths."""
        path = "/songs/NotQueued---xyz.mp4"
        manager.cancel_pending(path)
        assert path in manager._cancelled_paths

    def test_does_not_emit_any_event(self, events, preferences):
        received = []
        for event_name in ("processing_cancelled", "processing_complete", "processing_error"):
            events.on(event_name, lambda *a: received.append(event_name))
        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.enqueue("/songs/Song---abc123.mp4")
        mgr.cancel_pending("/songs/Song---abc123.mp4")
        assert received == []


# ---------------------------------------------------------------------------
# cancel_active()
# ---------------------------------------------------------------------------


class TestCancelActive:
    def test_cancel_active_none_is_noop(self, manager, mock_orchestrator):
        manager._orchestrator = mock_orchestrator
        manager._active = None
        manager.cancel_active("/songs/Song---abc123.mp4")
        mock_orchestrator.cancel_active.assert_not_called()

    def test_cancel_active_wrong_path_is_noop(self, manager, mock_orchestrator):
        manager._orchestrator = mock_orchestrator
        token = CancelToken(event=threading.Event())
        manager._active = _ActiveJob(song_path="/songs/Other---xyz.mp4", cancel_token=token)
        manager.cancel_active("/songs/Song---abc123.mp4")
        mock_orchestrator.cancel_active.assert_not_called()

    def test_cancel_active_matching_path_calls_orchestrator(self, manager, mock_orchestrator):
        manager._orchestrator = mock_orchestrator
        token = CancelToken(event=threading.Event())
        path = "/songs/Song---abc123.mp4"
        manager._active = _ActiveJob(song_path=path, cancel_token=token)
        manager.cancel_active(path)
        mock_orchestrator.cancel_active.assert_called_once()

    def test_cancel_active_sets_cancelling_flag(self, manager, mock_orchestrator):
        manager._orchestrator = mock_orchestrator
        token = CancelToken(event=threading.Event())
        path = "/songs/Song---abc123.mp4"
        active = _ActiveJob(song_path=path, cancel_token=token)
        manager._active = active
        manager.cancel_active(path)
        assert active.cancelling is True


# ---------------------------------------------------------------------------
# get_active_job()
# ---------------------------------------------------------------------------


class TestGetActiveJob:
    def test_returns_none_when_idle(self, manager):
        assert manager.get_active_job() is None

    def test_returns_path_when_active(self, manager):
        token = CancelToken(event=threading.Event())
        manager._active = _ActiveJob(song_path="/songs/Active---abc.mp4", cancel_token=token)
        assert manager.get_active_job() == "/songs/Active---abc.mp4"


# ---------------------------------------------------------------------------
# _resolve_lyrics_path()
# ---------------------------------------------------------------------------


class TestResolveLyricsPath:
    def test_prefers_en_srt(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
        (subs / "Song---abc123.srt").write_text("fallback")
        result = ProcessingManager._resolve_lyrics_path(str(song))
        assert result == subs / "Song---abc123.en.srt"

    def test_falls_back_to_plain_srt(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
        result = ProcessingManager._resolve_lyrics_path(str(song))
        assert result == subs / "Song---abc123.srt"

    def test_returns_none_when_no_srt(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        result = ProcessingManager._resolve_lyrics_path(str(song))
        assert result is None

    def test_returns_none_when_subtitles_dir_missing(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        result = ProcessingManager._resolve_lyrics_path(str(song))
        assert result is None


# ---------------------------------------------------------------------------
# _process_song() — early-exit when state is 'ready' or 'skipped'
# ---------------------------------------------------------------------------


class TestProcessSongEarlyExit:
    def test_ready_state_emits_complete_without_orchestrator(
        self, events, preferences, mock_orchestrator
    ):
        sm = MagicMock()
        sm.get_pipeline_state.return_value = "ready"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_complete", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == ["/songs/Song---abc123.mp4"]
        mock_orchestrator.run_one_async.assert_not_called()

    def test_skipped_state_emits_complete_without_orchestrator(
        self, events, preferences, mock_orchestrator
    ):
        sm = MagicMock()
        sm.get_pipeline_state.return_value = "skipped"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_complete", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == ["/songs/Song---abc123.mp4"]
        mock_orchestrator.run_one_async.assert_not_called()

    def test_no_song_manager_proceeds_to_orchestrator(self, events, preferences, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx

        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=None)
        mgr._orchestrator = mock_orchestrator
        mgr._process_song("/songs/Song---abc123.mp4")

        mock_orchestrator.run_one_async.assert_called_once()


# ---------------------------------------------------------------------------
# _process_song() — success path
# ---------------------------------------------------------------------------


class TestProcessSongSuccess:
    def test_success_emits_processing_complete(self, events, preferences, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"loudnorm_target_offset": "-3.2"}
        mock_orchestrator.join.return_value = ctx

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_complete", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == ["/songs/Song---abc123.mp4"]

    def test_success_sets_pipeline_state_ready(self, events, preferences, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"loudnorm_target_offset": "-3.2"}
        mock_orchestrator.join.return_value = ctx

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator
        mgr._process_song("/songs/Song---abc123.mp4")

        sm.set_pipeline_state.assert_called_once_with("/songs/Song---abc123.mp4", "ready")

    def test_success_persists_loudnorm_offset(self, events, preferences, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"loudnorm_target_offset": "-3.2"}
        mock_orchestrator.join.return_value = ctx

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator
        mgr._process_song("/songs/Song---abc123.mp4")

        sm.set_loudnorm_offset.assert_called_once_with("/songs/Song---abc123.mp4", -3.2)

    def test_success_without_loudnorm_offset_skips_set_loudnorm(
        self, events, preferences, mock_orchestrator
    ):
        """When loudnorm_target_offset is absent, set_loudnorm_offset must not be called."""
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}  # no offset key
        mock_orchestrator.join.return_value = ctx

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator
        mgr._process_song("/songs/Song---abc123.mp4")

        sm.set_loudnorm_offset.assert_not_called()
        sm.set_pipeline_state.assert_called_once_with("/songs/Song---abc123.mp4", "ready")

    def test_success_sets_active_job(self, events, preferences, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        # Capture _active mid-call via side-effect on join
        captured = []

        def capture_active():
            captured.append(mgr._active)
            return ctx

        mock_orchestrator.join.side_effect = capture_active
        mgr._process_song("/songs/Song---abc123.mp4")

        assert len(captured) == 1
        assert captured[0] is not None
        assert captured[0].song_path == "/songs/Song---abc123.mp4"


# ---------------------------------------------------------------------------
# _process_song() — cancellation path
# ---------------------------------------------------------------------------


class TestProcessSongCancellation:
    def test_cancelled_emits_processing_cancelled(self, events, preferences, mock_orchestrator):
        mock_orchestrator.join.side_effect = PipelineCancelled()

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_cancelled", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == ["/songs/Song---abc123.mp4"]

    def test_cancelled_does_not_write_pipeline_state(self, events, preferences, mock_orchestrator):
        """PipelineCancelled must leave state as 'pending' — do not write 'failed' or 'ready'."""
        mock_orchestrator.join.side_effect = PipelineCancelled()

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator
        mgr._process_song("/songs/Song---abc123.mp4")

        sm.set_pipeline_state.assert_not_called()

    def test_cancelled_does_not_emit_complete(self, events, preferences, mock_orchestrator):
        mock_orchestrator.join.side_effect = PipelineCancelled()

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_complete", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == []


# ---------------------------------------------------------------------------
# _process_song() — error path
# ---------------------------------------------------------------------------


class TestProcessSongError:
    def test_error_emits_processing_error(self, events, preferences, mock_orchestrator):
        mock_orchestrator.join.side_effect = RuntimeError("ffmpeg exploded")

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_error", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert len(received) == 1
        assert received[0]["song_path"] == "/songs/Song---abc123.mp4"
        assert "ffmpeg exploded" in received[0]["error"]

    def test_error_sets_pipeline_state_failed(self, events, preferences, mock_orchestrator):
        mock_orchestrator.join.side_effect = RuntimeError("bad")

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator
        mgr._process_song("/songs/Song---abc123.mp4")

        sm.set_pipeline_state.assert_called_once_with("/songs/Song---abc123.mp4", "failed")

    def test_error_does_not_emit_complete(self, events, preferences, mock_orchestrator):
        mock_orchestrator.join.side_effect = RuntimeError("bad")

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_complete", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == []

    def test_error_no_song_manager_does_not_raise(self, events, preferences, mock_orchestrator):
        mock_orchestrator.join.side_effect = RuntimeError("bad")
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=None)
        mgr._orchestrator = mock_orchestrator
        # Should complete without AttributeError
        mgr._process_song("/songs/Song---abc123.mp4")
