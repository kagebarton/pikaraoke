"""Processing manager: orchestrator + persistent StemWorker.

Coordinates the 3-step pipeline (FFmpeg extract → stem separation → FFmpeg
transcode) in a real threading.Thread, delegating the actual separation work
to a :class:`StemWorker` subprocess that holds the model loaded across songs.
"""

import enum
import glob
import logging
import os
import queue
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.get_platform import get_temp_directory, is_windows
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.process_terminal import ProcessTerminal
from pikaraoke.lib.stem_worker import StemWorker, WorkerDiedError

# M4A encoding quality: "2" ≈ 128 kbps VBR AAC — transparent for karaoke.
AAC_QUALITY = "2"

FFMPEG_THREADS = "4"


class _Step(enum.Enum):
    EXTRACTING = "extracting"
    STEMMING = "stemming"
    TRANSCODING = "transcoding"


@dataclass
class _JobState:
    song_path: str
    step: _Step
    ffmpeg_process: subprocess.Popen | None = None
    cancelled: bool = False


class _CancelledError(Exception):
    """Raised when a running job has been cancelled."""


class ProcessingManager:
    """Orchestrates stem processing with surgical cancellation.

    Runs a real-thread orchestrator loop that:
    1. Calls FFmpeg to extract audio (in-thread)
    2. Submits the WAV to a persistent ``StemWorker`` subprocess
    3. Calls FFmpeg to transcode stems to M4A (in-thread)

    ``cancel_active()`` targets only the relevant subprocess (FFmpeg Popen
    or StemWorker) based on the current pipeline step, so the model stays
    loaded unless cancel lands during actual stemming.
    """

    def __init__(
        self, events: EventSystem, preferences: PreferenceManager, temp_dir: str = ""
    ) -> None:
        self._events = events
        self._preferences = preferences
        self._temp_dir = temp_dir
        self._stem_worker: StemWorker
        self._pending_queue: queue.Queue[str | None] = queue.Queue()
        self.pending_jobs: list[str] = []  # public, derived
        self._active_state: _JobState | None = None
        self._state_lock = threading.Lock()
        self._cancelled_paths: set[str] = set()
        self._orchestrator_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._process_terminal: ProcessTerminal | None = None
        self._pty_slave_fd: int | None = None

    def start(self) -> None:
        """Start PTY, StemWorker, orchestrator thread, subscribe to events."""
        self._events.on("song_downloaded", self.enqueue)

        if not is_windows():
            self._process_terminal = ProcessTerminal()
            self._process_terminal.start()
            self._pty_slave_fd = self._process_terminal.get_slave_fd()

        self._stem_worker = StemWorker(
            pty_slave_fd=self._pty_slave_fd,
            temp_dir=self._temp_dir,
        )
        self._stem_worker.start()

        self._orchestrator_thread = threading.Thread(target=self._orchestrator_loop, daemon=True)
        self._orchestrator_thread.start()

    def stop(self) -> None:
        """Shut down orchestrator thread, StemWorker, PTY gracefully."""
        self._stop_event.set()
        try:
            self._pending_queue.put(None)  # shutdown sentinel
        except Exception:
            pass
        if self._orchestrator_thread is not None and self._orchestrator_thread.is_alive():
            self._orchestrator_thread.join(timeout=10)

        self._stem_worker.stop()
        if self._process_terminal is not None:
            self._process_terminal.stop()

    def enqueue(self, song_path: str) -> None:
        """Add a song to the stem processing queue."""
        blocked_str = self._preferences.get_or_default("blocked_processing_words")
        if blocked_str:
            name = Path(song_path).stem.lower()
            blocked = [w.strip().lower() for w in blocked_str.split(",") if w.strip()]
            if any(w in name for w in blocked):
                logging.info(
                    f"Skipping stem processing (title matches blocked word): {Path(song_path).name}"
                )
                return

        self.pending_jobs.append(song_path)
        try:
            self._pending_queue.put(song_path)
        except Exception:
            # Queue may be shut down — remove from pending_jobs to stay consistent.
            self.pending_jobs.remove(song_path)
            logging.warning(f"Failed to enqueue: {Path(song_path).name}")
            return
        logging.info(f"Queued for stem separation: {Path(song_path).name}")

    def cancel_pending(self, song_path: str) -> None:
        """Remove a song from the pending processing queue."""
        with self._state_lock:
            if song_path in self.pending_jobs:
                self.pending_jobs.remove(song_path)
            self._cancelled_paths.add(song_path)
        logging.info(f"Cancelled pending job: {Path(song_path).name}")

    def cancel_active(self, song_path: str) -> None:
        """Cancel the currently active processing job, targeting the active step.

        Safe to call from gevent context: only sends signals and sets flags,
        never joins a subprocess. The orchestrator thread observes the
        cancelled flag on its next ``_check_cancelled()`` and raises
        ``_CancelledError``.
        """
        with self._state_lock:
            state = self._active_state
            if state is None or state.song_path != song_path:
                logging.warning(f"Cancel requested for non-active job: {Path(song_path).name}")
                return
            state.cancelled = True
            step = state.step
            ffmpeg_proc = state.ffmpeg_process

        logging.info(f"Cancelling active job ({step.value}): {Path(song_path).name}")

        if step in (_Step.EXTRACTING, _Step.TRANSCODING):
            if ffmpeg_proc is not None:
                try:
                    ffmpeg_proc.kill()
                except ProcessLookupError:
                    pass
        elif step is _Step.STEMMING:
            self._stem_worker.kill()

    def get_active_job(self) -> str | None:
        """Return the path of the currently active processing job, or None."""
        with self._state_lock:
            if self._active_state is not None:
                return self._active_state.song_path
        return None

    # -- Orchestrator loop --------------------------------------------------

    def _orchestrator_loop(self) -> None:
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
                    if song_path in self.pending_jobs:
                        self.pending_jobs.remove(song_path)
                    continue
                self._active_state = _JobState(song_path=song_path, step=_Step.EXTRACTING)

            try:
                self._run_pipeline(song_path)
                self._events.emit("processing_complete", song_path)
                logging.info(f"Processing complete: {Path(song_path).name}")
            except _CancelledError:
                self._cleanup_stems(song_path)
                logging.info(f"Processing cancelled: {Path(song_path).name}")
            except Exception as e:
                logging.error(f"Processing failed for {Path(song_path).name}: {e}")
                self._events.emit(
                    "processing_error",
                    {"song_path": song_path, "error": str(e)},
                )
                self._cleanup_stems(song_path)
            finally:
                with self._state_lock:
                    if song_path in self.pending_jobs:
                        self.pending_jobs.remove(song_path)
                    self._active_state = None
                # Eager restart: if cancel or crash killed the worker, bring
                # it back before the next job arrives.
                if not self._stem_worker.is_alive():
                    try:
                        self._stem_worker.start()
                    except Exception as e:
                        logging.error(f"Failed to restart stem worker: {e}")

    # -- Pipeline execution -------------------------------------------------

    def _run_pipeline(self, song_path: str) -> None:
        video = Path(song_path)
        if not video.exists():
            raise FileNotFoundError(f"Song file not found: {song_path}")

        vocal_out, nonvocal_out = self._stem_output_paths(video)
        if vocal_out.exists() and nonvocal_out.exists():
            logging.info(f"Stems already exist, skipping: {video.name}")
            return

        resolved_temp_dir = get_temp_directory(self._temp_dir) if self._temp_dir else None
        tmp_dir = Path(tempfile.mkdtemp(prefix="pikaraoke_stems_", dir=resolved_temp_dir))
        try:
            # Step 1: FFmpeg extract (in orchestrator thread)
            logging.debug(f"[pipeline] extracting: {video.name}")
            wav_in = self._ffmpeg_extract(video, tmp_dir)
            logging.debug(f"[pipeline] extract done: {wav_in}")
            self._check_cancelled()

            # Step 2: Stem separation (in StemWorker subprocess)
            self._set_step(_Step.STEMMING)
            if not self._stem_worker.is_alive():
                self._stem_worker.start()
            logging.debug(f"[pipeline] calling separate: {video.name}")
            try:
                vocal_wav, instrumental_wav = self._stem_worker.separate(wav_in, tmp_dir)
            except WorkerDiedError:
                self._check_cancelled()  # re-raises _CancelledError if cancelled
                raise RuntimeError("Stem worker died unexpectedly during separation")
            logging.debug(
                f"[pipeline] separate returned: vocal={vocal_wav}, instrumental={instrumental_wav}"
            )
            self._check_cancelled()

            # Step 3: FFmpeg transcode x2 (in orchestrator thread)
            self._set_step(_Step.TRANSCODING)
            logging.debug(f"[pipeline] starting transcode")
            vocal_out.parent.mkdir(exist_ok=True)
            nonvocal_out.parent.mkdir(exist_ok=True)
            logging.debug(f"[pipeline] transcode vocal: {vocal_out.name}")
            self._ffmpeg_transcode(vocal_wav, vocal_out)
            logging.debug(f"[pipeline] vocal transcode done")
            self._check_cancelled()
            logging.debug(f"[pipeline] transcode instrumental: {nonvocal_out.name}")
            self._ffmpeg_transcode(instrumental_wav, nonvocal_out)
            logging.debug(f"[pipeline] instrumental transcode done")
            self._check_cancelled()
        finally:
            logging.debug(f"[pipeline] cleanup tmp: {tmp_dir}")
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _stem_output_paths(video: Path) -> tuple[Path, Path]:
        """Return (vocal_output_path, nonvocal_output_path)."""
        vocal_dir = video.parent / "vocal"
        nonvocal_dir = video.parent / "nonvocal"
        vocal_out = vocal_dir / f"{video.stem}---vocal.m4a"
        nonvocal_out = nonvocal_dir / f"{video.stem}---nonvocal.m4a"
        return vocal_out, nonvocal_out

    def _set_step(self, step: _Step) -> None:
        with self._state_lock:
            if self._active_state is not None:
                self._active_state.step = step
                self._active_state.ffmpeg_process = None

    def _check_cancelled(self) -> None:
        with self._state_lock:
            if self._active_state is not None and self._active_state.cancelled:
                raise _CancelledError()

    # -- FFmpeg wrappers ----------------------------------------------------

    def _ffmpeg_extract(self, video: Path, tmp_dir: Path) -> Path:
        """Extract audio from video to a temporary WAV."""
        wav_path = tmp_dir / f"{video.stem}_input.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ]
        self._run_ffmpeg(cmd, "audio extraction")
        return wav_path

    def _ffmpeg_transcode(self, wav_path: Path, output_path: Path) -> None:
        """Transcode a WAV stem to AAC-in-M4A."""
        cmd = [
            "ffmpeg",
            "-y",
            "-threads",
            FFMPEG_THREADS,
            "-i",
            str(wav_path),
            "-c:a",
            "aac",
            "-q:a",
            AAC_QUALITY,
            str(output_path),
        ]
        self._run_ffmpeg(cmd, "transcode")

    def _run_ffmpeg(self, cmd: list[str], label: str) -> None:
        stdout_fd = self._pty_slave_fd if self._pty_slave_fd is not None else subprocess.DEVNULL
        stderr_fd = self._pty_slave_fd if self._pty_slave_fd is not None else subprocess.DEVNULL
        proc = subprocess.Popen(cmd, stdout=stdout_fd, stderr=stderr_fd)
        with self._state_lock:
            if self._active_state is not None:
                self._active_state.ffmpeg_process = proc
        try:
            rc = proc.wait()
        finally:
            with self._state_lock:
                if self._active_state is not None:
                    self._active_state.ffmpeg_process = None
        if rc != 0:
            with self._state_lock:
                cancelled = self._active_state is not None and self._active_state.cancelled
            if cancelled:
                raise _CancelledError()
            raise RuntimeError(f"ffmpeg {label} failed (exit code {rc})")

    # -- Cleanup ------------------------------------------------------------

    def _cleanup_stems(self, song_path: str) -> None:
        """Clean up partial stem files for a given song."""
        import tempfile as _tempfile

        video = Path(song_path)
        stem_base = video.stem
        for stem_dir_name in ("vocal", "nonvocal"):
            stem_dir = video.parent / stem_dir_name
            if stem_dir.is_dir():
                for f in stem_dir.glob(f"{stem_base}---*"):
                    try:
                        f.unlink()
                        logging.debug(f"Cleaned up partial stem: {f}")
                    except OSError as e:
                        logging.warning(f"Failed to clean partial stem {f}: {e}")
        resolved_temp = get_temp_directory(self._temp_dir) if self._temp_dir else None
        search_dir = resolved_temp if resolved_temp else _tempfile.gettempdir()
        for d in glob.glob(os.path.join(search_dir, "pikaraoke_stems_*")):
            try:
                shutil.rmtree(d, ignore_errors=True)
                logging.debug(f"Cleaned up temp dir: {d}")
            except OSError:
                pass
