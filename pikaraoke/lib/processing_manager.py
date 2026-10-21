"""Processing manager: thin adapter over PipelineOrchestrator.

Delegates all execution to ``pikaraoke.pipeline.PipelineOrchestrator`` and
keeps the same public API that ``PipelineTracker`` and ``karaoke.py`` depend
on.  The old 3-step inline pipeline (extract → stem → transcode) is replaced
by a 5-stage pipeline (extract → loudnorm → stem → transcode → lyric_align)
with phase-targeted cancellation.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import queue
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

PIPELINE_THREAD_PREFIX = "pikaraoke-pipeline"

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.genius import GeniusClient
from pikaraoke.lib.get_platform import get_temp_directory, is_windows
from pikaraoke.lib.library_regen import (
    RegenJob,
    build_stages,
    finish_regen_job,
    prepare_regen_job,
)
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
    # From orchestrator.run_one_async(); None while a regen job prepares, before
    # its run starts (the orchestrator's token then belongs to the previous job).
    cancel_token: CancelToken | None
    # A cancel arrived. A regen still preparing reads it to skip its run.
    cancelling: bool = False
    kind: str = "download"  # which lane the job came from: "download" | "regen"
    started_at: float = field(default_factory=time.monotonic)


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
        is_playing: Callable[[str], bool] | None = None,
    ) -> None:
        self._events = events
        self._preferences = preferences
        self._song_manager = song_manager
        self._genius = genius_client  # may be None before start() is called
        self._temp_dir = temp_dir
        self._log_level = log_level
        # Cheap and non-blocking: called under _state_lock to hold back a regen
        # job for the song that is playing.
        self._is_playing = is_playing or (lambda _song_path: False)

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
        self.pending_jobs: list[str] = []  # public, derived (download and regen lanes)
        # Runs only when the download lane is empty. Each job is kept with its
        # song path as the library spells it (see _library_spelling).
        self._regen_jobs: list[tuple[str, RegenJob]] = []
        self._cancelled_paths: set[str] = set()  # download lane only
        self._active: _ActiveJob | None = None
        self._state_lock = threading.Lock()

        self._orchestrator_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API (unchanged from the old ProcessingManager)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start PTY, workers, orchestrator thread, subscribe to events.

        ``song_downloaded`` is not subscribed here: karaoke.py wires
        :meth:`enqueue` after the PipelineTracker, so the tracker sees a
        download's song path before ``processing_queued`` is emitted.
        """
        self._events.on("song_deleted", self._on_song_deleted)

        # Reduce CUDA allocator fragmentation so stem and whisper models can
        # coexist with mpv's graphics context on a single GPU.
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
            LyricsFetchStage(self._genius, self._config),
            FFmpegExtractStage(self._config),
            LoudnormAnalyzeStage(self._config),
            StemSeparationStage(self._stem_worker),
            FFmpegTranscodeStage(self._config),
            LyricAlignStage(self._whisper_worker, self._config, stem_worker=self._stem_worker),
        ]

        self._orchestrator = PipelineOrchestrator(
            stages,
            self._stem_worker,
            self._whisper_worker,
            self._config,
            on_stage_change=lambda _name: self._events.emit("pipeline_stage_changed"),
        )
        # The orchestrator's workers (and their stem/whisper model loads) are
        # started on the run-loop thread, not here, so start() returns at once
        # and the Flask server can come online before the models finish loading.
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

    def is_blocked(self, song_path: str) -> bool:
        """Whether the title matches the blocked-words preference."""
        blocked_str = self._preferences.get_or_default("blocked_processing_words")
        if not blocked_str:
            return False
        name = Path(song_path).stem.lower()
        blocked = [w.strip().lower() for w in blocked_str.split(",") if w.strip()]
        return any(w in name for w in blocked)

    def enqueue(self, song_path: str) -> None:
        """Add a song to the processing queue."""
        if self.is_blocked(song_path):
            logger.info(f"Skipping pipeline (title matches blocked word): {Path(song_path).name}")
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
        self._events.emit("processing_queued", song_path)

    def _library_spelling(self, path: Path) -> str:
        """``path`` spelled the way the song manager spells it.

        The library's paths come from ``os.walk`` plus ``os.path.join``, so they
        keep whatever separators the library root was given
        (``d:/songs\\X.mp4``), which ``str(Path(...))`` does not. The playing
        check, the duplicate check, ``song_deleted`` and the database rows all
        key on the library's own string, so a regen job must use it too.
        """
        plain = str(path)
        if self._song_manager is None:
            return plain
        songs = self._song_manager.songs
        if plain in songs:
            return plain
        return next((s for s in songs if Path(s) == path), plain)

    def enqueue_regen(self, regen: RegenJob) -> bool:
        """Queue a regen job behind the download lane.

        Returns False, queueing nothing, when the song is already running or
        waiting in either lane.
        """
        song_path = self._library_spelling(regen.song.song_path)
        with self._state_lock:
            running = self._active is not None and self._active.song_path == song_path
            if running or song_path in self.pending_jobs:
                return False
            self._regen_jobs.append((song_path, regen))
            self.pending_jobs.append(song_path)
        logging.info(f"Queued for regen ({regen.label}): {Path(song_path).name}")
        self._events.emit(
            "regen_queued", {"song_path": song_path, "label": regen.label, "job": regen}
        )
        return True

    def cancel_pending(self, song_path: str) -> None:
        """Remove a song from the pending processing queue.

        A path waiting in the regen lane is dropped from it and recorded
        nowhere else. Otherwise, only a job that has not yet become active is
        recorded in ``_cancelled_paths`` (consumed by ``_run_loop`` when it
        dequeues the path to skip it): that set belongs to the download queue,
        and an entry for a regen path would leak and later swallow a real
        download of that song. Recording an already-active path would leak the
        entry forever — the loop never re-dequeues an active job — and would
        then silently skip a later re-enqueue of the same path at the dequeue
        guard.
        """
        with self._state_lock:
            is_active = self._active is not None and self._active.song_path == song_path
            was_regen = self._drop_regen_jobs(song_path)
            if song_path in self.pending_jobs:
                self.pending_jobs.remove(song_path)
            if not is_active and not was_regen:
                self._cancelled_paths.add(song_path)
        logging.info(f"Cancelled pending job: {Path(song_path).name}")

    def _drop_regen_jobs(self, song_path: str) -> bool:
        """Remove ``song_path``'s regen jobs from the lane; True if there were any.

        Caller holds ``_state_lock`` and removes the path from ``pending_jobs``.
        """
        kept = [(path, regen) for path, regen in self._regen_jobs if path != song_path]
        dropped = len(kept) < len(self._regen_jobs)
        self._regen_jobs[:] = kept
        return dropped

    def _on_song_deleted(self, song_path: str) -> None:
        """A deleted song's queued regen job has nothing left to run on."""
        with self._state_lock:
            if self._drop_regen_jobs(song_path):
                self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]

    def cancel_active(self, song_path: str) -> None:
        """Cancel the currently active processing job.

        The cancel is fired while ``_state_lock`` is held so the active job
        cannot rotate to the next song in the validate->cancel window (which
        would otherwise cancel the wrong job). ``CancelToken.cancel()`` takes only
        the token's own lock (never ``_state_lock``), so holding ``_state_lock``
        across it cannot deadlock.
        """
        with self._state_lock:
            active = self._active
            if active is None or active.song_path != song_path:
                logging.warning(f"Cancel requested for non-active job: {Path(song_path).name}")
                return
            active.cancelling = True
            if active.cancel_token is None:
                # A regen still preparing: _launch_and_report sees the flag and
                # skips the run. The orchestrator's token is the previous job's.
                logging.info(f"Cancelling active job before its run: {Path(song_path).name}")
                return
            logging.info(f"Cancelling active job: {Path(song_path).name}")
            self._orchestrator.cancel_active()

    def get_active_job(self) -> str | None:
        """Return the path of the currently active processing job, or None."""
        with self._state_lock:
            return self._active.song_path if self._active else None

    def get_active_elapsed_s(self) -> float | None:
        """Seconds the active job has been running, or None when idle."""
        with self._state_lock:
            if self._active is None:
                return None
            return time.monotonic() - self._active.started_at

    def get_active_phase(self) -> str | None:
        """Return the current pipeline phase of the active job, or None.

        The phase value matches :class:`Phase` enum values (e.g. ``"extract"``,
        ``"stem_separation"``, ``"transcode"``). Returns ``None`` when no job
        is active or no phase has been entered yet.
        """
        with self._state_lock:
            if self._active is None:
                return None
            token = self._active.cancel_token
            phase = token.get_phase() if token is not None else None
            return phase.value if phase is not None else None

    # ------------------------------------------------------------------
    # Orchestrator loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        # Load the stem and whisper models here, on this background thread,
        # rather than in start() — keeping model loading off the startup
        # critical path so the Flask server binds immediately. Jobs enqueued
        # while the models load wait in _pending_queue until the loop below
        # begins consuming them, so no extra synchronization is needed.
        if not self._stop_event.is_set():
            try:
                self._orchestrator.start()
            except Exception as e:
                # Don't kill the loop: a worker that failed to load (e.g. a
                # transient GPU OOM) is restarted by the per-job recovery logic
                # in separate()/_run_job() and the finally block below.
                logging.error(f"Pipeline workers failed to start: {e}")

        while not self._stop_event.is_set():
            try:
                song_path = self._pending_queue.get(timeout=0.5)
            except queue.Empty:
                # A download always goes first; a regen job runs only when the
                # download lane is empty.
                taken = self._take_regen_job()
                if taken is not None:
                    song_path, regen = taken
                    self._run_job(song_path, lambda: self._process_regen(regen, song_path), regen)
                continue
            if song_path is None:
                return  # shutdown sentinel

            with self._state_lock:
                if song_path in self._cancelled_paths:
                    self._cancelled_paths.discard(song_path)
                    self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
                    continue

            self._run_job(song_path, lambda: self._process_song(song_path))

    def _take_regen_job(self) -> tuple[str, RegenJob] | None:
        """Pop the first queued regen job whose song isn't playing.

        Returns the job with its song path as the library spells it.

        A job for the playing song stays queued and is retried on the loop's
        next pass. The job counts as the active one from the moment it is
        taken, so it can be cancelled while it prepares; it has no cancel
        token until its run launches.
        """
        with self._state_lock:
            for i, (song_path, _) in enumerate(self._regen_jobs):
                if not self._is_playing(song_path):
                    self._active = _ActiveJob(song_path=song_path, cancel_token=None, kind="regen")
                    return self._regen_jobs.pop(i)
        return None

    def _run_job(
        self, song_path: str, process: Callable[[], None], regen: RegenJob | None = None
    ) -> None:
        """Run one job of either lane, then clean up after it.

        The one place where an error from a job becomes ``processing_error``,
        so an error anywhere in setting up or running a job fails that job
        and never ends the loop. ``regen`` is None for a download.
        """
        try:
            process()
        except Exception as e:
            self._report_failure(song_path, e, regen)
        finally:
            # In-place mutation preserves identity for external readers
            with self._state_lock:
                self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
                self._active = None

            # Eager restart: a cancel, crash, or failed/timed-out initial
            # load can leave a worker down; bring it back before the next
            # job. is_alive() is False after a load timeout too (kill()
            # clears the process handle), so this also recovers a worker
            # that never finished its startup model load. Restarting whisper
            # reloads its model and briefly blocks the loop, acceptable here.
            if not self._stem_worker.is_alive():
                try:
                    self._stem_worker.start()
                except Exception as e:
                    logging.error(f"Failed to restart stem worker: {e}")
            if not self._whisper_worker.is_alive():
                try:
                    self._whisper_worker.start()
                except Exception as e:
                    logging.error(f"Failed to restart whisper worker: {e}")

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
        self._launch_and_report(
            song_path, lambda: self._orchestrator.run_one_async(Path(song_path))
        )

    def _process_regen(self, regen: RegenJob, song_path: str) -> None:
        """Run one regen job: prepare its files, then drive the pipeline over them.

        ``song_path`` is the song as the library spells it, for events and the
        database; the file work uses ``regen.song.song_path``.

        A job that can't start (a ``RegenError``, or any failure while
        preparing) raises; :meth:`_run_job` reports it as a processing error
        and the song's ``pipeline_state`` is left alone either way.
        """
        job = regen.song
        logging.info(f"Regen started ({regen.label}): {job.song_path.name}", extra=LIFECYCLE_EXTRA)
        # Holds the reused-lyrics .txt for the run; the orchestrator validates
        # that the path exists, so it must outlive the job.
        lyrics_dir = Path(
            tempfile.mkdtemp(prefix="regen_lyrics_", dir=self._config.intermediate_dir or None)
        )
        try:
            # The CLI sets the same flag: keep the de-reverb stem for the next run.
            config = dataclasses.replace(self._config, cache_dereverb_stem=True)
            lyrics_path, lyric_stage = prepare_regen_job(regen, self._genius, config, lyrics_dir)
            stages = [
                PreparePtyStage(self._pty_slave_fd),
                *build_stages(
                    job.song_path, lyric_stage, self._whisper_worker, config, self._stem_worker
                ),
            ]
            self._launch_and_report(
                song_path,
                lambda: self._orchestrator.run_one_async(job.song_path, lyrics_path, stages),
                regen=regen,
            )
        finally:
            shutil.rmtree(lyrics_dir, ignore_errors=True)

    def _launch_and_report(
        self,
        song_path: str,
        launch: Callable[[], CancelToken],
        regen: RegenJob | None = None,
    ) -> bool:
        """Launch a pipeline run, wait for it, and report how it ended.

        Returns True when the run succeeded and False when it was cancelled.
        An error raises, and :meth:`_run_job` reports it. ``regen`` is None for
        a download. A failed download marks the song ``failed``; a failed regen
        leaves ``pipeline_state`` alone, because ``_do_enqueue`` refuses
        ``failed`` songs and a failed regen of a playable song must not make
        it unqueueable.
        """
        # Launch and register the active job under one lock hold: a cancel_active()
        # landing between the launch and the token assignment would otherwise be
        # dropped and the job would run to completion uncancellable.
        # run_one_async() only spawns a background thread and returns, so it does
        # not block or re-enter _state_lock. It validates its inputs on this
        # thread, so a song file that is gone raises here, before any pipeline
        # thread exists.
        with self._state_lock:
            active = self._active
            cancelled_in_setup = active is not None and active.cancelling
            if not cancelled_in_setup:
                token = launch()
                if active is None:  # a download; a regen was registered when taken
                    self._active = _ActiveJob(
                        song_path=song_path,
                        cancel_token=token,
                        kind="download" if regen is None else "regen",
                    )
                else:
                    active.cancel_token = token
        if cancelled_in_setup:
            self._report_cancelled(song_path)
            return False

        try:
            ctx = self._orchestrator.join()
        except PipelineCancelled:
            self._report_cancelled(song_path)
            return False

        # Persist loudnorm offset and ready state
        offset = ctx.artifacts.get("loudnorm_target_offset")
        if self._song_manager is not None:
            if offset is not None:
                try:
                    self._song_manager.set_loudnorm_offset(song_path, float(offset))
                except Exception as e:
                    logging.warning(f"Failed to persist loudnorm offset for {song_path}: {e}")
            self._song_manager.set_pipeline_state(song_path, "ready")

        if regen is not None:
            try:
                finish_regen_job(regen.song)
            except OSError as e:
                logging.warning(f"Could not drop the old bundle of {song_path}: {e}")

        self._events.emit(
            "processing_complete",
            {"song_path": song_path, "lyric_method": ctx.artifacts.get("lyric_method")},
        )
        logging.info(f"Processing complete: {Path(song_path).name}", extra=LIFECYCLE_EXTRA)
        return True

    def _report_cancelled(self, song_path: str) -> None:
        # Leave state as 'pending' — user-initiated cancel, not a system
        # failure. The stale-pending badge surfaces it on next page load.
        self._events.emit("processing_cancelled", song_path)
        logging.info(f"Processing cancelled: {Path(song_path).name}", extra=LIFECYCLE_EXTRA)

    def _report_failure(self, song_path: str, error: Exception, regen: RegenJob | None) -> None:
        if regen is None and self._song_manager is not None:
            self._song_manager.set_pipeline_state(song_path, "failed")
        logging.error(
            f"Processing failed for {Path(song_path).name}: {error}", extra=LIFECYCLE_EXTRA
        )
        self._events.emit("processing_error", {"song_path": song_path, "error": str(error)})
