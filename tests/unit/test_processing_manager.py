"""Unit tests for ProcessingManager (thin adapter over PipelineOrchestrator)."""

import threading
from unittest.mock import MagicMock, call, patch

import pytest

from pikaraoke.lib import processing_manager as pm
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.library_regen import Plan, RegenError, RegenJob, SongJob
from pikaraoke.lib.processing_manager import (
    PreparePtyStage,
    ProcessingManager,
    _ActiveJob,
)
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

        def fake_regen(regen):
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

        assert mgr._take_regen_job() is other  # skipped over the playing song's job
        assert mgr._take_regen_job() is None  # still held back, still queued
        assert str(on_air.song.song_path) in mgr.pending_jobs

        playing["path"] = None
        assert mgr._take_regen_job() is on_air

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

        assert manager._regen_jobs == [kept]
        assert manager.pending_jobs == [str(kept.song.song_path)]

    def test_a_download_waiting_for_the_same_path_is_left_alone(self, manager):
        manager.enqueue("/songs/Song---abc123.mp4")
        manager._on_song_deleted("/songs/Song---abc123.mp4")
        assert manager.pending_jobs == ["/songs/Song---abc123.mp4"]


class TestProcessRegen:
    def _run(self, events, preferences, orchestrator, tmp_path, regen, song_manager=None):
        mgr = _runnable_manager(events, preferences, orchestrator, tmp_path, song_manager)
        mgr._run_job(str(regen.song.song_path), lambda: mgr._process_regen(regen), regen)
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
        finish.assert_called_once_with(regen.song)
        assert done == [{"song_path": path, "lyric_method": "genius+joint"}]

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
        mgr._process_song("/songs/A---abc.mp4")
        mgr._process_regen(_regen_job(tmp_path))

        assert seen == ["download", "regen"]
