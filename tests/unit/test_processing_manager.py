"""Unit tests for ProcessingManager (thin adapter over PipelineOrchestrator)."""

import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from pikaraoke.lib import lrclib
from pikaraoke.lib import processing_manager as pm
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.library_regen import Plan, RegenError, RegenJob, SongJob
from pikaraoke.lib.pipeline_tracker import PipelineTracker
from pikaraoke.lib.processing_manager import (
    PreparePtyStage,
    ProcessingManager,
    _ActiveJob,
)
from pikaraoke.lib.song_list import SongList
from pikaraoke.pipeline.config import PipelineConfig
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
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    @patch("pikaraoke.lib.processing_manager.WhisperWorker")
    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.PipelineOrchestrator")
    def test_start_leaves_song_downloaded_to_the_caller(
        self,
        mock_orch_cls,
        mock_sw_cls,
        mock_ww_cls,
        mock_pt_cls,
        mock_gtd,
        mock_iw,
        events,
        preferences,
    ):
        """start() does not subscribe song_downloaded: karaoke.py wires enqueue()
        after the tracker, so the tracker sees the song path first."""
        mock_orch_cls.return_value = MagicMock()
        mock_sw_cls.return_value = MagicMock()
        mock_ww_cls.return_value = MagicMock()

        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()
        try:
            events.emit("song_downloaded", "/songs/Test---abc123.mp4")
            assert mgr.pending_jobs == []
        finally:
            mgr.stop()

    @patch("pikaraoke.lib.processing_manager.is_windows", return_value=True)
    @patch("pikaraoke.lib.processing_manager.get_temp_directory", return_value="/tmp/pk")
    @patch("pikaraoke.lib.processing_manager.ProcessTerminal")
    @patch("pikaraoke.lib.processing_manager.WhisperWorker")
    @patch("pikaraoke.lib.processing_manager.StemWorker")
    @patch("pikaraoke.lib.processing_manager.PipelineOrchestrator")
    def test_start_subscribes_song_deleted(
        self,
        mock_orch_cls,
        mock_sw_cls,
        mock_ww_cls,
        mock_pt_cls,
        mock_gtd,
        mock_iw,
        events,
        preferences,
    ):
        mock_orch_cls.return_value = MagicMock()
        mgr = ProcessingManager(events=events, preferences=preferences)
        mgr.start()
        try:
            assert mgr._on_song_deleted in events._handlers["song_deleted"]
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

    def test_cancel_pending_on_active_path_not_recorded(self, manager):
        """cancelling 'pending' for the path that is actually the active job must
        NOT seed _cancelled_paths: the loop never re-dequeues an active job, so the
        entry would leak forever and silently skip a later re-enqueue."""
        path = "/songs/Song---abc123.mp4"
        token = CancelToken(event=threading.Event())
        manager._active = _ActiveJob(song_path=path, cancel_token=token)
        manager.cancel_pending(path)
        assert path not in manager._cancelled_paths

    def test_reenqueue_after_active_cancel_pending_not_skipped(self, manager):
        """Consequence of the fix above: a path cancel_pending'd while active can be
        re-enqueued cleanly (no stale _cancelled_paths entry to discard it at dequeue)."""
        path = "/songs/Song---abc123.mp4"
        token = CancelToken(event=threading.Event())
        manager._active = _ActiveJob(song_path=path, cancel_token=token)
        manager.cancel_pending(path)
        manager._active = None
        manager.enqueue(path)
        assert path not in manager._cancelled_paths
        assert path in manager.pending_jobs

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

    def test_cancel_active_fires_orchestrator_under_state_lock(self, manager, mock_orchestrator):
        """orchestrator.cancel_active() is invoked while _state_lock is held so the
        active job cannot rotate to the next song in the validate->cancel window."""
        manager._orchestrator = mock_orchestrator
        locked_during = []
        mock_orchestrator.cancel_active.side_effect = lambda: locked_during.append(
            manager._state_lock.locked()
        )
        token = CancelToken(event=threading.Event())
        path = "/songs/Song---abc123.mp4"
        manager._active = _ActiveJob(song_path=path, cancel_token=token)
        manager.cancel_active(path)
        assert locked_during == [True]


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


class TestGetActivePhase:
    def test_returns_none_when_idle(self, manager):
        assert manager.get_active_phase() is None

    def test_returns_none_when_no_phase_set(self, manager):
        token = CancelToken(event=threading.Event())
        manager._active = _ActiveJob(song_path="/songs/Active---abc.mp4", cancel_token=token)
        assert manager.get_active_phase() is None

    def test_returns_phase_value_when_set(self, manager):
        from pikaraoke.pipeline.context import Phase

        token = CancelToken(event=threading.Event())
        token.phase = Phase.STEM_SEPARATION
        manager._active = _ActiveJob(song_path="/songs/Active---abc.mp4", cancel_token=token)
        assert manager.get_active_phase() == "stem_separation"

    def test_returns_extract_phase(self, manager):
        from pikaraoke.pipeline.context import Phase

        token = CancelToken(event=threading.Event())
        token.phase = Phase.EXTRACT
        manager._active = _ActiveJob(song_path="/songs/Active---abc.mp4", cancel_token=token)
        assert manager.get_active_phase() == "extract"

    def test_returns_transcode_phase(self, manager):
        from pikaraoke.pipeline.context import Phase

        token = CancelToken(event=threading.Event())
        token.phase = Phase.TRANSCODE
        manager._active = _ActiveJob(song_path="/songs/Active---abc.mp4", cancel_token=token)
        assert manager.get_active_phase() == "transcode"


# ---------------------------------------------------------------------------
# _resolve_lyrics_path() — REMOVED; logic now in LyricsFetchStage._find_srt
# ---------------------------------------------------------------------------


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

        assert received == [{"song_path": "/songs/Song---abc123.mp4", "lyric_method": None}]
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

        assert received == [{"song_path": "/songs/Song---abc123.mp4", "lyric_method": None}]
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
    def test_process_song_registers_active_under_lock(self, events, preferences, mock_orchestrator):
        """run_one_async() and the _active assignment happen under one lock hold,
        so a cancel_active() arriving in that window can't be dropped as non-active."""
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx

        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=None)
        mgr._orchestrator = mock_orchestrator
        locked_during = []

        def fake_run(_path):
            locked_during.append(mgr._state_lock.locked())
            return CancelToken(event=threading.Event())

        mock_orchestrator.run_one_async.side_effect = fake_run
        mgr._process_song("/songs/Song---abc123.mp4")
        assert locked_during == [True]

    def test_success_emits_processing_complete(self, events, preferences, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"loudnorm_target_offset": "-3.2", "lyric_method": "genius+walk"}
        mock_orchestrator.join.return_value = ctx

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = ProcessingManager(events=events, preferences=preferences, song_manager=sm)
        mgr._orchestrator = mock_orchestrator

        received = []
        events.on("processing_complete", received.append)
        mgr._process_song("/songs/Song---abc123.mp4")

        assert received == [
            {"song_path": "/songs/Song---abc123.mp4", "lyric_method": "genius+walk"}
        ]

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
    """An error raises out of the job; the loop's ``_run_job`` reports it."""

    def test_error_emits_processing_error(self, events, preferences, mock_orchestrator, tmp_path):
        mock_orchestrator.join.side_effect = RuntimeError("ffmpeg exploded")

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)

        received = []
        events.on("processing_error", received.append)
        _run_download(mgr, "/songs/Song---abc123.mp4")

        assert len(received) == 1
        assert received[0]["song_path"] == "/songs/Song---abc123.mp4"
        assert "ffmpeg exploded" in received[0]["error"]

    def test_error_sets_pipeline_state_failed(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        mock_orchestrator.join.side_effect = RuntimeError("bad")

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        _run_download(mgr, "/songs/Song---abc123.mp4")

        sm.set_pipeline_state.assert_called_once_with("/songs/Song---abc123.mp4", "failed")

    def test_error_does_not_emit_complete(self, events, preferences, mock_orchestrator, tmp_path):
        mock_orchestrator.join.side_effect = RuntimeError("bad")

        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)

        received = []
        events.on("processing_complete", received.append)
        _run_download(mgr, "/songs/Song---abc123.mp4")

        assert received == []

    def test_error_no_song_manager_does_not_raise(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        mock_orchestrator.join.side_effect = RuntimeError("bad")
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path)
        # Should complete without AttributeError
        _run_download(mgr, "/songs/Song---abc123.mp4")


# ---------------------------------------------------------------------------
# Regen lane
# ---------------------------------------------------------------------------


def _regen_job(folder, label="Repair", stem="Song---abc123", kind="transcribe") -> RegenJob:
    song = SongJob(
        song_path=folder / f"{stem}.mp4",
        bundle=None,
        stale_reason="selected",
        plan=Plan(kind=kind),
    )
    return RegenJob(song=song, reset=False, label=label)


def _runnable_manager(
    events, preferences, orchestrator, tmp_path, song_manager=None, is_playing=None
):
    """A manager that can run jobs without start(): workers and config stand-ins."""
    mgr = ProcessingManager(
        events=events,
        preferences=preferences,
        song_manager=song_manager,
        is_playing=is_playing,
    )
    mgr._orchestrator = orchestrator
    mgr._config = PipelineConfig(intermediate_dir=str(tmp_path))
    mgr._stem_worker = MagicMock()
    mgr._whisper_worker = MagicMock()
    mgr._pty_slave_fd = None
    mgr._genius = MagicMock()
    return mgr


def _run_download(mgr, song_path: str) -> None:
    """Run one download the way the loop does, so a failure is reported."""
    mgr._run_job(song_path, lambda: mgr._process_song(song_path))


@pytest.fixture
def prepared(monkeypatch):
    """prepare_regen_job and build_stages stubbed out; yields the prepare mock."""
    prepare = MagicMock(return_value=(None, None))
    monkeypatch.setattr(pm, "prepare_regen_job", prepare)
    monkeypatch.setattr(pm, "build_stages", MagicMock(return_value=["lyric-align"]))
    return prepare


def _drive_loop(mgr, finished: threading.Event, during=None):
    """Run the manager's loop on a thread until ``finished`` is set."""
    thread = threading.Thread(target=mgr._run_loop, daemon=True)
    thread.start()
    try:
        if during is not None:
            during()
        assert finished.wait(timeout=5), "the loop did not get through its jobs"
    finally:
        mgr._stop_event.set()
        mgr._pending_queue.put(None)
        thread.join(timeout=5)


class TestIsBlocked:
    def test_a_title_with_a_blocked_word(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo, sample"
        mgr = ProcessingManager(events=events, preferences=prefs)
        assert mgr.is_blocked("/songs/A Sample Song---abc123.mp4") is True

    def test_a_title_without_one(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo"
        mgr = ProcessingManager(events=events, preferences=prefs)
        assert mgr.is_blocked("/songs/Song---abc123.mp4") is False

    def test_no_preference_blocks_nothing(self, manager):
        assert manager.is_blocked("/songs/Song---abc123.mp4") is False


class TestProcessingQueuedEvent:
    def test_enqueue_emits_it_once_the_song_is_queued(self, events, preferences):
        mgr = ProcessingManager(events=events, preferences=preferences)
        seen = []
        events.on("processing_queued", lambda path: seen.append((path, list(mgr.pending_jobs))))
        mgr.enqueue("/songs/Song---abc123.mp4")
        assert seen == [("/songs/Song---abc123.mp4", ["/songs/Song---abc123.mp4"])]

    def test_a_blocked_song_is_not_announced_as_queued(self, events):
        prefs = MagicMock()
        prefs.get_or_default.return_value = "demo"
        mgr = ProcessingManager(events=events, preferences=prefs)
        seen = []
        events.on("processing_queued", seen.append)
        mgr.enqueue("/songs/Demo Song---abc123.mp4")
        assert seen == []


class TestEnqueueRegen:
    def test_queues_the_job_and_announces_it(self, events, manager, tmp_path):
        seen = []
        events.on("regen_queued", seen.append)
        regen = _regen_job(tmp_path, "Update")

        assert manager.enqueue_regen(regen) is True

        path = str(regen.song.song_path)
        assert manager.pending_jobs == [path]
        assert seen == [{"song_path": path, "label": "Update", "job": regen}]
        # The regen lane is separate: nothing went into the download queue.
        assert manager._pending_queue.qsize() == 0

    def test_refuses_a_path_already_pending(self, manager, tmp_path):
        assert manager.enqueue_regen(_regen_job(tmp_path, "first")) is True
        assert manager.enqueue_regen(_regen_job(tmp_path, "second")) is False
        assert len(manager._regen_jobs) == 1

    def test_refuses_a_path_waiting_in_the_download_lane(self, manager, tmp_path):
        regen = _regen_job(tmp_path)
        manager.enqueue(str(regen.song.song_path))
        assert manager.enqueue_regen(regen) is False

    def test_refuses_the_active_path(self, manager, tmp_path):
        regen = _regen_job(tmp_path)
        token = CancelToken(event=threading.Event())
        manager._active = _ActiveJob(song_path=str(regen.song.song_path), cancel_token=token)
        assert manager.enqueue_regen(regen) is False

    def test_a_refused_job_announces_nothing(self, events, manager, tmp_path):
        manager.enqueue_regen(_regen_job(tmp_path))
        seen = []
        events.on("regen_queued", seen.append)
        manager.enqueue_regen(_regen_job(tmp_path))
        assert seen == []


class TestRegenLaneOrder:
    def test_a_download_queued_after_two_regen_jobs_runs_before_the_second(
        self, events, preferences, mock_orchestrator, tmp_path, monkeypatch
    ):
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path)
        order: list[str] = []
        first_running = threading.Event()
        release_first = threading.Event()
        finished = threading.Event()

        def fake_regen(regen, song_path):
            order.append(regen.label)
            if regen.label == "A":
                first_running.set()
                assert release_first.wait(timeout=5)
            if len(order) == 3:
                finished.set()

        def fake_song(song_path):
            order.append("download")
            if len(order) == 3:
                finished.set()

        monkeypatch.setattr(mgr, "_process_regen", fake_regen)
        monkeypatch.setattr(mgr, "_process_song", fake_song)
        mgr.enqueue_regen(_regen_job(tmp_path, "A", stem="A---aaa111"))
        mgr.enqueue_regen(_regen_job(tmp_path, "B", stem="B---bbb222"))

        def queue_the_download():
            assert first_running.wait(timeout=5)
            mgr.enqueue("/songs/New---ccc333.mp4")
            release_first.set()

        _drive_loop(mgr, finished, during=queue_the_download)

        assert order == ["A", "download", "B"]

    def test_a_regen_job_for_the_playing_song_waits_for_it_to_stop(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        playing = {"path": None}
        mgr = _runnable_manager(
            events,
            preferences,
            mock_orchestrator,
            tmp_path,
            is_playing=lambda path: path == playing["path"],
        )
        on_air = _regen_job(tmp_path, "on-air", stem="OnAir---aaa111")
        other = _regen_job(tmp_path, "other", stem="Other---bbb222")
        playing["path"] = str(on_air.song.song_path)
        mgr.enqueue_regen(on_air)
        mgr.enqueue_regen(other)

        assert mgr._take_regen_job() == (
            str(other.song.song_path),
            other,
        )  # skipped the playing one
        assert mgr._take_regen_job() is None  # still held back, still queued
        assert str(on_air.song.song_path) in mgr.pending_jobs

        playing["path"] = None
        assert mgr._take_regen_job() == (str(on_air.song.song_path), on_air)

    def test_cancel_pending_on_a_regen_path_leaves_the_download_cancel_set_alone(
        self, events, preferences, mock_orchestrator, tmp_path, monkeypatch
    ):
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path)
        regen = _regen_job(tmp_path)
        path = str(regen.song.song_path)
        mgr.enqueue_regen(regen)

        mgr.cancel_pending(path)

        assert mgr._cancelled_paths == set()
        assert mgr._regen_jobs == []
        assert mgr.pending_jobs == []

        # A real download of the same song still runs.
        ran = threading.Event()
        monkeypatch.setattr(mgr, "_process_song", lambda song_path: ran.set())
        mgr.enqueue(path)
        _drive_loop(mgr, ran)


class TestSongDeletedDropsRegenJobs:
    def test_a_queued_regen_job_for_the_deleted_song_is_dropped(self, manager, tmp_path):
        gone = _regen_job(tmp_path, stem="Gone---aaa111")
        kept = _regen_job(tmp_path, stem="Kept---bbb222")
        manager.enqueue_regen(gone)
        manager.enqueue_regen(kept)

        manager._on_song_deleted(str(gone.song.song_path))

        assert manager._regen_jobs == [(str(kept.song.song_path), kept)]
        assert manager.pending_jobs == [str(kept.song.song_path)]

    def test_a_download_waiting_for_the_same_path_is_left_alone(self, manager):
        manager.enqueue("/songs/Song---abc123.mp4")
        manager._on_song_deleted("/songs/Song---abc123.mp4")
        assert manager.pending_jobs == ["/songs/Song---abc123.mp4"]


class TestProcessRegen:
    def _run(self, events, preferences, orchestrator, tmp_path, regen, song_manager=None):
        mgr = _runnable_manager(events, preferences, orchestrator, tmp_path, song_manager)
        song_path = str(regen.song.song_path)
        mgr._run_job(song_path, lambda: mgr._process_regen(regen, song_path), regen)
        return mgr

    def test_launches_the_pipeline_with_its_own_stage_list(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path)
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        prepared.return_value = (tmp_path / "lyrics.txt", "lyric-stage")

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        (song_path, lyrics_path, stages), _ = mock_orchestrator.run_one_async.call_args
        assert song_path == regen.song.song_path
        assert lyrics_path == tmp_path / "lyrics.txt"
        assert isinstance(stages[0], PreparePtyStage)
        assert stages[1:] == ["lyric-align"]

    def test_the_run_keeps_the_dereverb_stem_without_changing_the_shared_config(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path)
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx

        mgr = self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert prepared.call_args.args[2].cache_dereverb_stem is True
        assert mgr._config.cache_dereverb_stem is False

    def test_a_successful_regen_sets_ready_and_finishes_the_job(
        self, events, preferences, mock_orchestrator, tmp_path, prepared, monkeypatch
    ):
        regen = _regen_job(tmp_path)
        path = str(regen.song.song_path)
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"loudnorm_target_offset": "-2.5", "lyric_method": "genius+joint"}
        mock_orchestrator.join.return_value = ctx
        finish = MagicMock()
        monkeypatch.setattr(pm, "finish_regen_job", finish)
        sm = MagicMock()
        done = []
        events.on("processing_complete", done.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen, sm)

        sm.set_pipeline_state.assert_called_once_with(path, "ready")
        sm.set_loudnorm_offset.assert_called_once_with(path, -2.5)
        finish.assert_called_once_with(regen.song.song_path, "genius+joint")
        assert done == [{"song_path": path, "lyric_method": "genius+joint"}]

    def test_a_genius_pick_that_ends_up_transcribing_drops_the_old_bundle(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        # The plan says sidecar, but Genius was unavailable and the run
        # transcribed: it wrote no bundle, so the old one has to go.
        regen = _regen_job(tmp_path, kind="sidecar")
        bundle = tmp_path / "alignment_debug" / f"{regen.song.song_path.stem}.json"
        bundle.parent.mkdir()
        bundle.write_text("{}", encoding="utf-8")
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"lyric_method": "transcribe"}
        mock_orchestrator.join.return_value = ctx

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert not bundle.exists()

    def test_a_run_with_lyrics_keeps_the_old_bundle_whatever_the_plan(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path, kind="transcribe")
        bundle = tmp_path / "alignment_debug" / f"{regen.song.song_path.stem}.json"
        bundle.parent.mkdir()
        bundle.write_text("{}", encoding="utf-8")
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {"lyric_method": "genius+joint"}
        mock_orchestrator.join.return_value = ctx

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert bundle.exists()

    def test_a_failed_regen_leaves_pipeline_state_as_it_was(
        self, events, preferences, mock_orchestrator, tmp_path, prepared, monkeypatch
    ):
        regen = _regen_job(tmp_path)
        mock_orchestrator.join.side_effect = RuntimeError("whisper fell over")
        finish = MagicMock()
        monkeypatch.setattr(pm, "finish_regen_job", finish)
        sm = MagicMock()
        errors = []
        events.on("processing_error", errors.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen, sm)

        sm.set_pipeline_state.assert_not_called()
        finish.assert_not_called()
        assert errors == [{"song_path": str(regen.song.song_path), "error": "whisper fell over"}]

    def test_a_cancelled_regen_emits_cancelled_and_leaves_state_alone(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path)
        mock_orchestrator.join.side_effect = PipelineCancelled()
        sm = MagicMock()
        cancelled = []
        events.on("processing_cancelled", cancelled.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen, sm)

        assert cancelled == [str(regen.song.song_path)]
        sm.set_pipeline_state.assert_not_called()

    def test_a_regen_error_is_reported_with_its_message_and_runs_no_pipeline(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path)
        prepared.side_effect = RegenError("Use Repair lyrics on Song Info to pick lyrics.")
        sm = MagicMock()
        errors = []
        events.on("processing_error", errors.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen, sm)

        assert errors == [
            {
                "song_path": str(regen.song.song_path),
                "error": "Use Repair lyrics on Song Info to pick lyrics.",
            }
        ]
        mock_orchestrator.run_one_async.assert_not_called()
        sm.set_pipeline_state.assert_not_called()

    def test_any_other_preparation_failure_is_reported_too(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path)
        prepared.side_effect = OSError("disk full")
        errors = []
        events.on("processing_error", errors.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert errors[0]["error"] == "disk full"
        mock_orchestrator.run_one_async.assert_not_called()

    def test_the_temporary_lyrics_folder_is_removed(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen = _regen_job(tmp_path)
        seen = {}

        def prepare(regen_job, genius, config, lyrics_dir):
            seen["dir"] = lyrics_dir
            assert lyrics_dir.is_dir()
            return None, None

        prepared.side_effect = prepare
        mock_orchestrator.join.side_effect = RuntimeError("fail")

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert not seen["dir"].exists()


class TestLaunchFailures:
    """A song file that is gone raises when the job is launched, before any
    pipeline thread exists; that must fail the job, not end the run loop."""

    def test_a_missing_file_fails_a_download_and_the_loop_runs_the_next(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        token = CancelToken(event=threading.Event())
        mock_orchestrator.run_one_async.side_effect = [FileNotFoundError("gone"), token]
        sm = MagicMock()
        sm.get_pipeline_state.return_value = "pending"
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        errors, done = [], threading.Event()
        events.on("processing_error", errors.append)
        events.on("processing_complete", lambda data: done.set())

        def queue_both():
            mgr.enqueue("/songs/Gone---aaa111.mp4")
            mgr.enqueue("/songs/Next---bbb222.mp4")

        _drive_loop(mgr, done, during=queue_both)

        assert [e["song_path"] for e in errors] == ["/songs/Gone---aaa111.mp4"]
        assert "gone" in errors[0]["error"]
        sm.set_pipeline_state.assert_any_call("/songs/Gone---aaa111.mp4", "failed")
        sm.set_pipeline_state.assert_any_call("/songs/Next---bbb222.mp4", "ready")

    def test_a_missing_file_fails_a_regen_and_the_loop_runs_the_next(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        token = CancelToken(event=threading.Event())
        mock_orchestrator.run_one_async.side_effect = [FileNotFoundError("gone"), token]
        sm = MagicMock()
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        gone = _regen_job(tmp_path, "Gone", stem="Gone---aaa111")
        nxt = _regen_job(tmp_path, "Next", stem="Next---bbb222")
        errors, done = [], threading.Event()
        events.on("processing_error", errors.append)
        events.on("processing_complete", lambda data: done.set())
        mgr.enqueue_regen(gone)
        mgr.enqueue_regen(nxt)

        _drive_loop(mgr, done)

        assert [e["song_path"] for e in errors] == [str(gone.song.song_path)]
        # The failed regen left its song's state alone; the next one set ready.
        sm.set_pipeline_state.assert_called_once_with(str(nxt.song.song_path), "ready")


class TestSetupFailures:
    """An error while setting a job up fails that job; it must not end the run
    loop, or every later job stays pending until a restart."""

    def _two_regen_jobs(self, mgr, tmp_path):
        broken = _regen_job(tmp_path, "Broken", stem="Broken---aaa111")
        nxt = _regen_job(tmp_path, "Next", stem="Next---bbb222")
        mgr.enqueue_regen(broken)
        mgr.enqueue_regen(nxt)
        return broken, nxt

    def _finishing_ctx(self, mock_orchestrator):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        mock_orchestrator.run_one_async.return_value = CancelToken(event=threading.Event())

    def test_build_stages_failing_fails_the_regen_and_the_loop_runs_the_next(
        self, events, preferences, mock_orchestrator, tmp_path, monkeypatch
    ):
        # build_stages deletes the old de-reverb file, which is a PermissionError
        # on Windows while the file is open.
        self._finishing_ctx(mock_orchestrator)
        monkeypatch.setattr(pm, "prepare_regen_job", MagicMock(return_value=(None, None)))
        monkeypatch.setattr(
            pm,
            "build_stages",
            MagicMock(side_effect=[PermissionError("dereverb file in use"), ["lyric-align"]]),
        )
        sm = MagicMock()
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        errors, done = [], threading.Event()
        events.on("processing_error", errors.append)
        events.on("processing_complete", lambda data: done.set())
        broken, nxt = self._two_regen_jobs(mgr, tmp_path)

        _drive_loop(mgr, done)

        assert errors == [
            {"song_path": str(broken.song.song_path), "error": "dereverb file in use"}
        ]
        sm.set_pipeline_state.assert_called_once_with(str(nxt.song.song_path), "ready")
        assert mgr.pending_jobs == []
        assert mgr.get_active_job() is None

    def test_mkdtemp_failing_fails_the_regen_and_the_loop_runs_the_next(
        self, events, preferences, mock_orchestrator, tmp_path, prepared, monkeypatch
    ):
        self._finishing_ctx(mock_orchestrator)
        real_mkdtemp = pm.tempfile.mkdtemp
        calls = []

        def flaky_mkdtemp(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("no space left on device")
            return real_mkdtemp(*args, **kwargs)

        monkeypatch.setattr(pm.tempfile, "mkdtemp", flaky_mkdtemp)
        sm = MagicMock()
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        errors, done = [], threading.Event()
        events.on("processing_error", errors.append)
        events.on("processing_complete", lambda data: done.set())
        broken, nxt = self._two_regen_jobs(mgr, tmp_path)

        _drive_loop(mgr, done)

        assert errors == [
            {"song_path": str(broken.song.song_path), "error": "no space left on device"}
        ]
        mock_orchestrator.run_one_async.assert_called_once()  # only the next job ran
        sm.set_pipeline_state.assert_called_once_with(str(nxt.song.song_path), "ready")

    def test_a_download_whose_state_lookup_fails_is_marked_failed_and_the_loop_goes_on(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        self._finishing_ctx(mock_orchestrator)
        sm = MagicMock()
        sm.get_pipeline_state.side_effect = [RuntimeError("database is locked"), "pending"]
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        errors, done = [], threading.Event()
        events.on("processing_error", errors.append)
        events.on("processing_complete", lambda data: done.set())

        def queue_both():
            mgr.enqueue("/songs/Locked---aaa111.mp4")
            mgr.enqueue("/songs/Next---bbb222.mp4")

        _drive_loop(mgr, done, during=queue_both)

        assert errors == [
            {"song_path": "/songs/Locked---aaa111.mp4", "error": "database is locked"}
        ]
        sm.set_pipeline_state.assert_any_call("/songs/Locked---aaa111.mp4", "failed")
        sm.set_pipeline_state.assert_any_call("/songs/Next---bbb222.mp4", "ready")
        assert mgr.pending_jobs == []


class TestLaunchAndReportResult:
    def test_reports_true_when_the_run_succeeded(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path)

        result = mgr._launch_and_report(
            "/songs/A---abc.mp4", lambda: CancelToken(threading.Event())
        )

        assert result is True

    def test_reports_false_when_the_run_was_cancelled(
        self, events, preferences, mock_orchestrator, tmp_path
    ):
        mock_orchestrator.join.side_effect = PipelineCancelled()
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path)

        result = mgr._launch_and_report(
            "/songs/A---abc.mp4", lambda: CancelToken(threading.Event())
        )

        assert result is False


class TestCancelWhilePreparing:
    """A regen job counts as the active job from the moment it is taken, so a
    cancel during its setup (the caption fetch, the Genius and LRCLIB calls)
    stops it before the pipeline runs."""

    @pytest.fixture
    def scene(self, events, preferences, mock_orchestrator, tmp_path, monkeypatch):
        """A real manager and tracker with one regen job held inside its setup."""
        sm = MagicMock()
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, sm)
        tracker = PipelineTracker(MagicMock(), mgr, MagicMock(), sm, events)
        scene = SimpleNamespace(
            mgr=mgr,
            tracker=tracker,
            sm=sm,
            regen=_regen_job(tmp_path),
            preparing=threading.Event(),
            release=threading.Event(),
            setup_error=None,
            setup_effect=None,
        )
        scene.path = str(scene.regen.song.song_path)

        def held_in_setup(regen, genius, config, lyrics_dir):
            if scene.setup_effect is not None:
                scene.setup_effect()
            scene.preparing.set()
            assert scene.release.wait(timeout=5)
            if scene.setup_error is not None:
                raise scene.setup_error
            return None, None

        monkeypatch.setattr(pm, "prepare_regen_job", held_in_setup)
        monkeypatch.setattr(pm, "build_stages", MagicMock(return_value=["lyric-align"]))
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        mgr.enqueue_regen(scene.regen)
        return scene

    def test_the_job_is_the_active_one_with_no_phase_while_it_prepares(
        self, events, scene, mock_orchestrator
    ):
        finished = threading.Event()
        events.on("processing_complete", lambda data: finished.set())
        seen = {}

        def look_while_preparing():
            assert scene.preparing.wait(timeout=5)
            seen["job"] = scene.mgr.get_active_job()
            seen["phase"] = scene.mgr.get_active_phase()
            seen["row"] = scene.tracker.get_status(admin=True)[0]
            seen["requeue"] = scene.mgr.enqueue_regen(scene.regen)
            scene.release.set()

        _drive_loop(scene.mgr, finished, during=look_while_preparing)

        assert seen["job"] == scene.path
        assert seen["phase"] is None
        assert seen["row"]["processing_status"] == "active"
        assert seen["row"]["processing_phase"] is None
        assert seen["requeue"] is False
        # Not cancelled, so the run launched on the existing job.
        mock_orchestrator.run_one_async.assert_called_once()

    def test_a_cancel_while_preparing_stops_the_job_before_any_stage_runs(
        self, events, scene, mock_orchestrator
    ):
        cancelled = threading.Event()
        events.on("processing_cancelled", lambda path: cancelled.set())
        seen = {}

        def cancel_while_preparing():
            assert scene.preparing.wait(timeout=5)
            row = scene.tracker.get_status(admin=True)[0]
            seen["cancel_accepted"] = scene.tracker.cancel(row["id"])
            seen["status"] = scene.tracker.get_status(admin=True)[0]["processing_status"]
            scene.release.set()

        _drive_loop(scene.mgr, cancelled, during=cancel_while_preparing)

        assert seen == {"cancel_accepted": True, "status": "cancelling"}
        mock_orchestrator.run_one_async.assert_not_called()
        mock_orchestrator.cancel_active.assert_not_called()
        assert scene.tracker.get_status(admin=True) == []
        scene.sm.delete.assert_not_called()
        scene.sm.set_pipeline_state.assert_not_called()
        assert scene.mgr._cancelled_paths == set()
        assert scene.mgr.pending_jobs == []
        assert scene.mgr.get_active_job() is None

    def test_a_later_process_of_that_song_runs(self, events, scene, monkeypatch):
        cancelled, ran = threading.Event(), threading.Event()
        events.on("processing_cancelled", lambda path: cancelled.set())
        monkeypatch.setattr(scene.mgr, "_process_song", lambda song_path: ran.set())

        def cancel_then_process_again():
            assert scene.preparing.wait(timeout=5)
            row = scene.tracker.get_status(admin=True)[0]
            assert scene.tracker.cancel(row["id"])
            scene.release.set()
            assert cancelled.wait(timeout=5)
            scene.mgr.enqueue(scene.path)

        _drive_loop(scene.mgr, ran, during=cancel_then_process_again)

    def test_a_cancel_while_preparing_puts_the_lrc_back(self, events, scene):
        lrc = lrclib.lrc_path(scene.regen.song.song_path)
        lrc.parent.mkdir()
        lrc.write_text("[lrclib_id:1]\n[00:01.00]old\n", encoding="utf-8")
        scene.setup_effect = lrc.unlink  # a new Genius id drops the .lrc
        cancelled = threading.Event()
        events.on("processing_cancelled", lambda path: cancelled.set())

        def cancel_while_preparing():
            assert scene.preparing.wait(timeout=5)
            row = scene.tracker.get_status(admin=True)[0]
            assert scene.tracker.cancel(row["id"])
            assert not lrc.exists()
            scene.release.set()

        _drive_loop(scene.mgr, cancelled, during=cancel_while_preparing)

        assert lrc.read_text(encoding="utf-8") == "[lrclib_id:1]\n[00:01.00]old\n"

    def test_a_setup_error_after_a_cancel_leaves_a_plain_error_row(self, events, scene):
        errored = threading.Event()
        events.on("processing_error", lambda data: errored.set())
        scene.setup_error = RegenError("The YouTube caption has gone.")

        def cancel_while_preparing():
            assert scene.preparing.wait(timeout=5)
            row = scene.tracker.get_status(admin=True)[0]
            assert scene.tracker.cancel(row["id"])
            scene.release.set()

        _drive_loop(scene.mgr, errored, during=cancel_while_preparing)

        (row,) = scene.tracker.get_status(admin=True)
        assert row["processing_status"] == "error"
        assert row["error_message"] == "The YouTube caption has gone."
        assert "retry" in row["actions"] and "dismiss" in row["actions"]
        assert "cancel" not in row["actions"]


class TestAFailedRowWhileTheJobCleansUp:
    """``processing_error`` goes out before the loop stops naming the job as the
    active one; a status read and a cancel landing in between must leave the
    row as an error that can be retried."""

    def test_the_row_stays_an_error_and_a_cancel_is_refused(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        prepared.side_effect = RegenError("no captions")
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path, MagicMock())
        tracker = PipelineTracker(MagicMock(), mgr, MagicMock(), MagicMock(), events)
        in_window, release, done = threading.Event(), threading.Event(), threading.Event()

        def hold(_data):  # runs after the tracker's own handler
            in_window.set()
            assert release.wait(timeout=5)
            done.set()

        events.on("processing_error", hold)
        mgr.enqueue_regen(_regen_job(tmp_path))
        seen = {}

        def read_and_cancel_in_the_window():
            assert in_window.wait(timeout=5)
            seen["active"] = mgr.get_active_job()
            row = tracker.get_status(admin=True)[0]
            seen["status"] = row["processing_status"]
            seen["cancel_accepted"] = tracker.cancel(row["id"])
            release.set()

        _drive_loop(mgr, done, during=read_and_cancel_in_the_window)

        assert seen["active"] is not None  # the window is real
        assert (seen["status"], seen["cancel_accepted"]) == ("error", False)
        (row,) = tracker.get_status(admin=True)
        assert row["processing_status"] == "error"
        assert "retry" in row["actions"]


class TestCancelActiveBeforeTheRun:
    def test_it_flags_the_job_and_leaves_the_orchestrator_alone(self, manager):
        manager._orchestrator = MagicMock()
        manager._active = _ActiveJob(
            song_path="/songs/A---abc.mp4", cancel_token=None, kind="regen"
        )

        manager.cancel_active("/songs/A---abc.mp4")

        assert manager._active.cancelling is True
        manager._orchestrator.cancel_active.assert_not_called()


class TestLibrarySpelling:
    """The library keeps the separators its root was given (``d:/songs\\X.mp4``)
    while ``str(Path(...))`` normalises them, so a regen job built from a ``Path``
    must be keyed by the library's own string or the playing check, the
    duplicate check, ``song_deleted`` and the database rows all miss."""

    @pytest.fixture
    def song(self, tmp_path):
        """One file under two spellings: ``Path``'s and the library's."""
        library = str(tmp_path) + "//X---dQw4w9WgXcQ.mp4"
        regen = _regen_job(tmp_path, stem="X---dQw4w9WgXcQ")
        assert str(regen.song.song_path) != library
        assert regen.song.song_path == Path(library)
        return SimpleNamespace(regen=regen, library=library)

    def _manager(self, events, preferences, orchestrator, tmp_path, song, is_playing=None):
        sm = MagicMock()
        sm.songs = SongList()
        sm.songs.add(song.library)
        return _runnable_manager(events, preferences, orchestrator, tmp_path, sm, is_playing)

    def test_a_path_is_looked_up_in_the_song_list(
        self, events, preferences, mock_orchestrator, tmp_path, song
    ):
        mgr = self._manager(events, preferences, mock_orchestrator, tmp_path, song)
        other = tmp_path / "Other---aaaaaaaaaaa.mp4"

        assert mgr._library_spelling(song.regen.song.song_path) == song.library
        assert mgr._library_spelling(Path(song.library)) == song.library
        assert mgr._library_spelling(other) == str(other)  # not in the library

    def test_a_manager_without_a_song_list_uses_the_plain_string(self, manager, tmp_path):
        path = tmp_path / "X---dQw4w9WgXcQ.mp4"
        assert manager._library_spelling(path) == str(path)

    def test_the_queued_event_and_the_pending_list_carry_the_library_spelling(
        self, events, preferences, mock_orchestrator, tmp_path, song
    ):
        mgr = self._manager(events, preferences, mock_orchestrator, tmp_path, song)
        seen = []
        events.on("regen_queued", seen.append)

        assert mgr.enqueue_regen(song.regen) is True

        assert [e["song_path"] for e in seen] == [song.library]
        assert mgr.pending_jobs == [song.library]

    def test_the_playing_check_gets_the_library_spelling(
        self, events, preferences, mock_orchestrator, tmp_path, song
    ):
        mgr = self._manager(
            events,
            preferences,
            mock_orchestrator,
            tmp_path,
            song,
            is_playing=lambda path: path == song.library,
        )
        mgr.enqueue_regen(song.regen)

        assert mgr._take_regen_job() is None  # held back: this song is playing
        assert mgr.pending_jobs == [song.library]

    def test_a_download_waiting_under_the_library_spelling_blocks_the_regen(
        self, events, preferences, mock_orchestrator, tmp_path, song
    ):
        mgr = self._manager(events, preferences, mock_orchestrator, tmp_path, song)
        mgr.enqueue(song.library)

        assert mgr.enqueue_regen(song.regen) is False

    def test_song_deleted_with_the_library_spelling_drops_the_job(
        self, events, preferences, mock_orchestrator, tmp_path, song
    ):
        mgr = self._manager(events, preferences, mock_orchestrator, tmp_path, song)
        mgr.enqueue_regen(song.regen)

        mgr._on_song_deleted(song.library)

        assert mgr._regen_jobs == []
        assert mgr.pending_jobs == []

    def test_a_successful_run_marks_the_song_ready_under_the_library_spelling(
        self, events, preferences, mock_orchestrator, tmp_path, song, prepared
    ):
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx
        mgr = self._manager(events, preferences, mock_orchestrator, tmp_path, song)
        completed, done = [], threading.Event()
        events.on("processing_complete", lambda data: (completed.append(data), done.set()))
        mgr.enqueue_regen(song.regen)

        _drive_loop(mgr, done)

        mgr._song_manager.set_pipeline_state.assert_called_once_with(song.library, "ready")
        assert [c["song_path"] for c in completed] == [song.library]
        # File work still goes by the Path.
        assert mock_orchestrator.run_one_async.call_args.args[0] == song.regen.song.song_path


class TestLrcPutBackWhenTheRegenDoesNotFinish:
    """The LRCLIB choice is ``lyrics/<stem>.lrc`` (D3): setup rewrites or deletes
    it and the run can write a new one, while a regen that doesn't finish leaves
    the old bundle, so the file has to go back with it."""

    OLD = "[ti:Old]\n[lrclib_id:1]\n[00:01.00]old\n"
    NEW = "[ti:New]\n[lrclib_id:2]\n[00:01.00]new\n"

    def _regen_with_lrc(self, tmp_path, before):
        regen = _regen_job(tmp_path, kind="sidecar")
        lrc = lrclib.lrc_path(regen.song.song_path)
        if before is not None:
            lrc.parent.mkdir(exist_ok=True)
            lrc.write_text(before, encoding="utf-8")
        return regen, lrc

    def _run(self, events, preferences, orchestrator, tmp_path, regen):
        mgr = _runnable_manager(events, preferences, orchestrator, tmp_path, MagicMock())
        song_path = str(regen.song.song_path)
        mgr._run_job(song_path, lambda: mgr._process_regen(regen, song_path), regen)

    def test_a_new_genius_pick_whose_run_fails_gets_the_old_lrc_back(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen, lrc = self._regen_with_lrc(tmp_path, self.OLD)

        def drop_for_the_new_song(regen_job, genius, config, lyrics_dir):
            lrc.unlink()
            return None, None

        prepared.side_effect = drop_for_the_new_song
        mock_orchestrator.join.side_effect = RuntimeError("whisper fell over")

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert lrc.read_text(encoding="utf-8") == self.OLD

    def test_a_skip_marker_comes_back_when_the_re_pick_is_cancelled_during_the_run(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen, lrc = self._regen_with_lrc(tmp_path, None)
        lrclib.write_skip_marker(lrc)

        def drop_for_the_new_song(regen_job, genius, config, lyrics_dir):
            lrc.unlink()
            return None, None

        prepared.side_effect = drop_for_the_new_song
        mock_orchestrator.join.side_effect = PipelineCancelled()

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert lrclib.is_skip_marker(lrc)

    def test_an_lrc_written_by_a_run_that_then_fails_is_removed(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen, lrc = self._regen_with_lrc(tmp_path, None)

        def run_that_writes_then_fails():
            lrc.parent.mkdir(exist_ok=True)
            lrc.write_text(self.NEW, encoding="utf-8")
            raise RuntimeError("alignment failed")

        mock_orchestrator.join.side_effect = run_that_writes_then_fails

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert not lrc.exists()

    def test_a_successful_run_keeps_the_new_file(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        regen, lrc = self._regen_with_lrc(tmp_path, self.OLD)

        def rewrite_for_the_new_pick(regen_job, genius, config, lyrics_dir):
            lrc.write_text(self.NEW, encoding="utf-8")
            return None, None

        prepared.side_effect = rewrite_for_the_new_pick
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}
        mock_orchestrator.join.return_value = ctx

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert lrc.read_text(encoding="utf-8") == self.NEW

    def test_a_failed_restore_does_not_hide_the_jobs_own_error(
        self, events, preferences, mock_orchestrator, tmp_path, prepared, monkeypatch
    ):
        regen, _ = self._regen_with_lrc(tmp_path, self.OLD)
        mock_orchestrator.join.side_effect = RuntimeError("whisper fell over")
        monkeypatch.setattr(lrclib, "restore_lrc", MagicMock(side_effect=PermissionError("locked")))
        errors = []
        events.on("processing_error", errors.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert [e["error"] for e in errors] == ["whisper fell over"]

    def test_an_lrc_that_cannot_be_read_fails_the_job_before_anything_changes(
        self, events, preferences, mock_orchestrator, tmp_path, prepared, monkeypatch
    ):
        regen, _ = self._regen_with_lrc(tmp_path, self.OLD)
        monkeypatch.setattr(
            lrclib, "snapshot_lrc", MagicMock(side_effect=PermissionError("locked"))
        )
        errors = []
        events.on("processing_error", errors.append)

        self._run(events, preferences, mock_orchestrator, tmp_path, regen)

        assert [e["error"] for e in errors] == ["locked"]
        prepared.assert_not_called()


class TestActiveJobTiming:
    def test_no_elapsed_time_when_idle(self, manager):
        assert manager.get_active_elapsed_s() is None

    def test_elapsed_time_counts_from_when_the_job_became_active(self, manager):
        token = CancelToken(event=threading.Event())
        job = _ActiveJob(song_path="/songs/A---abc.mp4", cancel_token=token)
        job.started_at -= 30.0
        manager._active = job
        assert 30.0 <= manager.get_active_elapsed_s() < 60.0

    def test_a_job_records_which_lane_it_came_from(
        self, events, preferences, mock_orchestrator, tmp_path, prepared
    ):
        mgr = _runnable_manager(events, preferences, mock_orchestrator, tmp_path)
        seen = []
        ctx = MagicMock(spec=StageContext)
        ctx.artifacts = {}

        def capture():
            seen.append(mgr._active.kind)
            return ctx

        mock_orchestrator.join.side_effect = capture
        _run_download(mgr, "/songs/A---abc.mp4")
        regen = _regen_job(tmp_path)
        mgr.enqueue_regen(regen)
        song_path, taken = mgr._take_regen_job()
        mgr._run_job(song_path, lambda: mgr._process_regen(taken, song_path), taken)

        assert seen == ["download", "regen"]
