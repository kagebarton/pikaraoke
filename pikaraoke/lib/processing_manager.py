"""Processing manager: thin adapter over PipelineOrchestrator.

Delegates all execution to ``pikaraoke.pipeline.PipelineOrchestrator`` and
keeps the same public API that ``PipelineTracker`` and ``karaoke.py`` depend
on.  The old 3-step inline pipeline (extract → stem → transcode) is replaced
by a 5-stage pipeline (extract → loudnorm → stem → transcode → lyric_align)
with phase-targeted cancellation.
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from dataclasses import dataclass
from pathlib import Path

PIPELINE_THREAD_PREFIX = "pikaraoke-pipeline"

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.genius import GeniusClient
from pikaraoke.lib.get_platform import get_temp_directory, is_windows
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.process_terminal import ProcessTerminal
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import CancelToken, PipelineCancelled, StageContext
from pikaraoke.pipeline.orchestrator import PipelineOrchestrator
from pikaraoke.pipeline.stages.base import BaseStage
from pikaraoke.pipeline.stages.ffmpeg_extract import FFmpegExtractStage
from pikaraoke.pipeline.stages.ffmpeg_transcode import FFmpegTranscodeStage
from pikaraoke.pipeline.stages.loudnorm_analyze import LoudnormAnalyzeStage
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage
from pikaraoke.pipeline.stages.lyrics_fetch import LyricsFetchStage
from pikaraoke.pipeline.stages.stem_separation import StemSeparationStage
from pikaraoke.pipeline.workers.stem_worker import StemWorker
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# _PtyHandler — routes Python log records to the PTY processing terminal
# ---------------------------------------------------------------------------


def _is_pipeline_thread(record: logging.LogRecord) -> bool:
    """True if the record was emitted on a thread driving the pipeline.

    Pipeline threads are named with :data:`PIPELINE_THREAD_PREFIX` so any
    module called from them — including new ones — routes to the processing
    terminal without needing an explicit allowlist.
    """
    return record.threadName is not None and record.threadName.startswith(PIPELINE_THREAD_PREFIX)


def _is_lifecycle(record: logging.LogRecord) -> bool:
    """True if the record is a pipeline-lifecycle event (job start/end)."""
    return getattr(record, "lifecycle", False) is True


LIFECYCLE_EXTRA = {"lifecycle": True}


class _PipelineThreadFilter(logging.Filter):
    """Route records between the main terminal and the processing terminal.

    Pipeline-lifecycle records (start/complete/cancel/fail) are duplicated
    to both so the main terminal still shows when a song begins and ends.
    """

    def __init__(self, accept: bool) -> None:
        super().__init__()
        self._accept = accept

    def filter(self, record: logging.LogRecord) -> bool:
        if self._accept:
            # PTY: emit on pipeline thread; skip non-pipeline lifecycle echoes.
            return _is_pipeline_thread(record)
        # Main stderr: emit non-pipeline records plus lifecycle events.
        return not _is_pipeline_thread(record) or _is_lifecycle(record)


class _PtyHandler(logging.Handler):
    """Write formatted log records to the PTY slave fd.

    Attached to the root logger and gated by thread name: any record emitted
    while the current thread name starts with :data:`PIPELINE_THREAD_PREFIX`
    is forwarded to the processing terminal. Records from other threads are
    dropped by the handler's filter and continue to the existing stderr
    handler — to which we add the inverse filter so pipeline-thread records
    do *not* also leak to the main terminal.
    """

    def __init__(self, pty_fd: int) -> None:
        super().__init__()
        self._pty_fd = pty_fd
        self.addFilter(_PipelineThreadFilter(accept=True))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record) + "\n"
            os.write(self._pty_fd, msg.encode("utf-8", errors="replace"))
        except OSError:
            pass

    @classmethod
    def attach(cls, pty_fd: int, formatter: logging.Formatter | None) -> "_PtyHandler":
        handler = cls(pty_fd)
        if formatter is not None:
            handler.setFormatter(formatter)

        root = logging.getLogger()
        root.addHandler(handler)
        # Keep pipeline-thread logs out of the main terminal.
        for existing in root.handlers:
            if existing is handler:
                continue
            existing.addFilter(_PipelineThreadFilter(accept=False))
        return handler

    def detach(self) -> None:
        root = logging.getLogger()
        root.removeHandler(self)
        for existing in root.handlers:
            for flt in list(existing.filters):
                if isinstance(flt, _PipelineThreadFilter) and not flt._accept:
                    existing.removeFilter(flt)


# ---------------------------------------------------------------------------
# PreparePtyStage — seeds ctx.artifacts["pty_slave_fd"] before any stage runs
# ---------------------------------------------------------------------------


class PreparePtyStage(BaseStage):
    """Tiny stage that seeds the PTY slave fd into ctx.artifacts.

    Lives inline here (not in pikaraoke/pipeline/stages/) because it is
    adapter-specific plumbing, not a pipeline concern.
    """

    name = "prepare_pty"

    def __init__(self, pty_slave_fd: int | None) -> None:
        self._fd = pty_slave_fd

    def run(self, ctx: StageContext) -> None:
        if self._fd is not None:
            ctx.artifacts["pty_slave_fd"] = self._fd


# ---------------------------------------------------------------------------
# _ActiveJob — tracks the currently running pipeline invocation
# ---------------------------------------------------------------------------


@dataclass
class _ActiveJob:
    song_path: str
    cancel_token: CancelToken  # from orchestrator.run_one_async()
    cancelling: bool = False  # vestigial: set but not read; signals intent


# ---------------------------------------------------------------------------
# ProcessingManager
# ---------------------------------------------------------------------------


class ProcessingManager:
    """Orchestrates pipeline processing with surgical cancellation.

    Runs a real-thread orchestrator loop that delegates each song through
    the 5-stage pipeline (extract → loudnorm → stem → transcode → lyric_align)
    via ``PipelineOrchestrator``.  ``cancel_active()`` targets the current
    activity scope (FFmpeg Popen or model worker) via
    ``CancelToken.cancel()``, so the model stays loaded unless cancel lands
    during actual separation.
    """

    def __init__(
        self,
        events: EventSystem,
        preferences: PreferenceManager,
        song_manager: SongManager | None = None,
        genius_client: GeniusClient | None = None,
        temp_dir: str = "",
        log_level: int = logging.INFO,
    ) -> None:
        self._events = events
        self._preferences = preferences
        self._song_manager = song_manager
        self._genius = genius_client  # may be None before start() is called
        self._temp_dir = temp_dir
        self._log_level = log_level

        # Built in start()
        self._config: PipelineConfig
        self._stem_worker: StemWorker
        self._whisper_worker: WhisperWorker
        self._orchestrator: PipelineOrchestrator

        # PTY (owned by this manager for its full lifetime)
        self._process_terminal: ProcessTerminal | None = None
        self._pty_slave_fd: int | None = None
        self._pty_log_handler: _PtyHandler | None = None

        # Queue and cancellation bookkeeping
        self._pending_queue: queue.Queue[str | None] = queue.Queue()
        self.pending_jobs: list[str] = []  # public, derived
        self._cancelled_paths: set[str] = set()
        self._active: _ActiveJob | None = None
        self._state_lock = threading.Lock()

        self._orchestrator_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API (unchanged from the old ProcessingManager)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start PTY, workers, orchestrator thread, subscribe to events."""
        self._events.on("song_downloaded", self.enqueue)

        # Reduce CUDA allocator fragmentation so stem and whisper models can
        # coexist with mpv's graphics context on a single GPU.
        import os

        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        # Build config, resolving intermediate temp dir via get_temp_directory()
        self._config = PipelineConfig()
        if self._temp_dir:
            self._config.intermediate_dir = get_temp_directory(self._temp_dir)
        else:
            self._config.intermediate_dir = get_temp_directory()

        # Spawn PTY on non-Windows
        pty_slave_path: str | None = None
        if not is_windows():
            self._process_terminal = ProcessTerminal()
            self._process_terminal.start()
            self._pty_slave_fd = self._process_terminal.get_slave_fd()
            pty_slave_path = self._process_terminal.get_slave_path()

        # Route pipeline Python log records to the processing terminal
        if self._pty_slave_fd is not None:
            root_formatter = logging.root.handlers[0].formatter if logging.root.handlers else None
            self._pty_log_handler = _PtyHandler.attach(self._pty_slave_fd, root_formatter)

        # Workers run as spawn'd subprocesses and cannot inherit fds, so
        # they receive the PTY device path and re-open it themselves.
        self._stem_worker = StemWorker(
            pty_slave_path=pty_slave_path,
            model_dir=self._config.separator_model_dir,
            model_name=self._config.separator_model_name,
            log_level=self._log_level,
        )
        self._whisper_worker = WhisperWorker(
            self._config.whisper,
            pty_slave_path=pty_slave_path,
        )

        # Build stages: PreparePtyStage first so all subsequent stages see pty_slave_fd
        stages = [
            PreparePtyStage(self._pty_slave_fd),
            LyricsFetchStage(self._genius),
            FFmpegExtractStage(self._config),
            LoudnormAnalyzeStage(self._config),
            StemSeparationStage(self._stem_worker),
            FFmpegTranscodeStage(self._config),
            LyricAlignStage(self._whisper_worker, self._config),
        ]

        self._orchestrator = PipelineOrchestrator(
            stages,
            self._stem_worker,
            self._whisper_worker,
            self._config,
            on_stage_change=lambda _name: self._events.emit("pipeline_stage_changed"),
        )
        self._orchestrator.start()  # starts stem worker only; whisper is lazy

        self._orchestrator_thread = threading.Thread(
            target=self._run_loop,
            name=f"{PIPELINE_THREAD_PREFIX}-loop",
            daemon=True,
        )
        self._orchestrator_thread.start()

    def stop(self) -> None:
        """Shut down orchestrator thread, workers, PTY gracefully."""
        self._stop_event.set()
        try:
            self._pending_queue.put(None)  # shutdown sentinel
        except Exception:
            pass
        if self._orchestrator_thread is not None and self._orchestrator_thread.is_alive():
            self._orchestrator_thread.join(timeout=10)

        self._orchestrator.stop()  # unloads whisper, stops stem worker

        if self._pty_log_handler is not None:
            self._pty_log_handler.detach()
            self._pty_log_handler = None

        # Close PTY slave fd AFTER orchestrator has joined — closing while a
        # stage still holds it open as subprocess stdout/stderr would cause EBADF.
        if self._process_terminal is not None:
            self._process_terminal.stop()

    def enqueue(self, song_path: str) -> None:
        """Add a song to the processing queue."""
        blocked_str = self._preferences.get_or_default("blocked_processing_words")
        if blocked_str:
            name = Path(song_path).stem.lower()
            blocked = [w.strip().lower() for w in blocked_str.split(",") if w.strip()]
            if any(w in name for w in blocked):
                logger.info(
                    f"Skipping pipeline (title matches blocked word): {Path(song_path).name}"
                )
                if self._song_manager is not None:
                    self._song_manager.set_pipeline_state(song_path, "skipped")
                self._events.emit("processing_skipped", song_path)
                return

        with self._state_lock:
            self.pending_jobs.append(song_path)
        try:
            self._pending_queue.put(song_path)
        except Exception:
            with self._state_lock:
                self.pending_jobs.remove(song_path)
            logging.warning(f"Failed to enqueue: {Path(song_path).name}")
            return
        logging.info(f"Queued for pipeline: {Path(song_path).name}")

    def cancel_pending(self, song_path: str) -> None:
        """Remove a song from the pending processing queue."""
        with self._state_lock:
            if song_path in self.pending_jobs:
                self.pending_jobs.remove(song_path)
            self._cancelled_paths.add(song_path)
        logging.info(f"Cancelled pending job: {Path(song_path).name}")

    def cancel_active(self, song_path: str) -> None:
        """Cancel the currently active processing job."""
        with self._state_lock:
            active = self._active
            if active is None or active.song_path != song_path:
                logging.warning(f"Cancel requested for non-active job: {Path(song_path).name}")
                return
            active.cancelling = True
        logging.info(f"Cancelling active job: {Path(song_path).name}")
        self._orchestrator.cancel_active()

    def get_active_job(self) -> str | None:
        """Return the path of the currently active processing job, or None."""
        with self._state_lock:
            return self._active.song_path if self._active else None

    def get_active_phase(self) -> str | None:
        """Return the current pipeline phase of the active job, or None.

        The phase value matches :class:`Phase` enum values (e.g. ``"extract"``,
        ``"stem_separation"``, ``"transcode"``). Returns ``None`` when no job
        is active or no phase has been entered yet.
        """
        with self._state_lock:
            if self._active is None:
                return None
            phase = self._active.cancel_token.get_phase()
            return phase.value if phase is not None else None

    # ------------------------------------------------------------------
    # Orchestrator loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                song_path = self._pending_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if song_path is None:
                return  # shutdown sentinel

            with self._state_lock:
                if song_path in self._cancelled_paths:
                    self._cancelled_paths.discard(song_path)
                    self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
                    continue

            try:
                self._process_song(song_path)
            finally:
                # In-place mutation preserves identity for external readers
                with self._state_lock:
                    self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
                    self._active = None

                # Eager restart: if a cancel or crash killed the stem worker,
                # bring it back before the next job arrives.
                if not self._stem_worker.is_alive():
                    try:
                        self._stem_worker.start()
                    except Exception as e:
                        logging.error(f"Failed to restart stem worker: {e}")

    # ------------------------------------------------------------------
    # Single-job processing
    # ------------------------------------------------------------------

    def _process_song(self, song_path: str) -> None:
        # Early-exit: already processed or admin-skipped
        if self._song_manager is not None:
            state = self._song_manager.get_pipeline_state(song_path)
            if state in ("ready", "skipped"):
                self._events.emit(
                    "processing_complete",
                    {"song_path": song_path, "lyric_method": None},
                )
                return

        logging.info(f"Processing started: {Path(song_path).name}", extra=LIFECYCLE_EXTRA)
        token = self._orchestrator.run_one_async(Path(song_path))
        with self._state_lock:
            self._active = _ActiveJob(song_path=song_path, cancel_token=token)

        try:
            ctx = self._orchestrator.join()
        except PipelineCancelled:
            # Leave state as 'pending' — user-initiated cancel, not a system
            # failure. The stale-pending badge surfaces it on next page load.
            self._events.emit("processing_cancelled", song_path)
            logging.info(
                f"Processing cancelled: {Path(song_path).name}", extra=LIFECYCLE_EXTRA
            )
            return
        except Exception as e:
            if self._song_manager is not None:
                self._song_manager.set_pipeline_state(song_path, "failed")
            logging.error(
                f"Processing failed for {Path(song_path).name}: {e}", extra=LIFECYCLE_EXTRA
            )
            self._events.emit("processing_error", {"song_path": song_path, "error": str(e)})
            return

        # Persist loudnorm offset and ready state
        offset = ctx.artifacts.get("loudnorm_target_offset")
        if self._song_manager is not None:
            if offset is not None:
                try:
                    self._song_manager.set_loudnorm_offset(song_path, float(offset))
                except Exception as e:
                    logging.warning(f"Failed to persist loudnorm offset for {song_path}: {e}")
            self._song_manager.set_pipeline_state(song_path, "ready")

        self._events.emit(
            "processing_complete",
            {"song_path": song_path, "lyric_method": ctx.artifacts.get("lyric_method")},
        )
        logging.info(f"Processing complete: {Path(song_path).name}", extra=LIFECYCLE_EXTRA)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
