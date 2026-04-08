"""Processing queue for splitting songs into vocal and instrumental stems."""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Process, Queue, SimpleQueue
from pathlib import Path

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.get_platform import get_temp_directory, is_windows
from pikaraoke.lib.process_terminal import ProcessTerminal

# Model for audio-separator: MelBand Roformer Karaoke — best single-model
# vocal clarity with complementary 2-stem output.
MODEL_NAME = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"

# Where audio-separator stores downloaded models (~400 MB on first run).
MODEL_DIR = "./audio-separator/models"

# Intermediate format for separation (lossless before final transcode).
SEPARATION_FORMAT = "wav"

# M4A encoding quality: "2" ≈ 128 kbps VBR AAC — transparent for karaoke.
AAC_QUALITY = "2"

FFMPEG_THREADS = "4"


class ProcessingManager:
    """Processes downloaded songs into vocal and instrumental stems.

    Subscribes to song_downloaded events and queues each song for background
    stem separation using audio-separator. Outputs are placed in vocal/ and
    nonvocal/ subdirectories beneath the song's parent folder.

    Runs in a separate process to avoid blocking the main application during
    CPU-intensive stem separation. All output (Python logging + subprocess
    stdout/stderr) is redirected to a secondary terminal window via a PTY.
    """

    def __init__(
        self, events: EventSystem, preferences: PreferenceManager, temp_dir: str = ""
    ) -> None:
        self._events = events
        self._temp_dir = temp_dir
        self._queue: Queue = Queue()
        self._result_queue: SimpleQueue = SimpleQueue()
        self._worker_process: Process | None = None
        self._process_terminal: ProcessTerminal | None = None
        self._pty_slave_fd: int | None = None
        self.pending_jobs: list[str] = []

    def start(self) -> None:
        """Start the background worker process and subscribe to events."""
        # Import audio-separator eagerly on the main thread so the heavy
        # PyTorch/numpy import doesn't hold Python's import lock later and
        # block the download thread.
        from audio_separator.separator import Separator  # noqa: F401

        self._events.on("song_downloaded", self.enqueue)

        if not is_windows():
            self._process_terminal = ProcessTerminal()
            self._process_terminal.start()
            self._pty_slave_fd = self._process_terminal.get_slave_fd()

        self._worker_process = self._make_worker_process()
        self._worker_process.start()
        logging.debug("Stem processing queue worker started")

    def stop(self) -> None:
        """Shut down the worker process and terminal gracefully."""
        if self._worker_process is not None and self._worker_process.is_alive():
            self._queue.put(None)
            self._worker_process.join(timeout=10)
            if self._worker_process.is_alive():
                self._worker_process.terminate()

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

        self._drain_results()
        if self._worker_process is not None and not self._worker_process.is_alive():
            logging.warning("Stem worker process died unexpectedly, restarting")
            self._worker_process = self._make_worker_process()
            self._worker_process.start()
        self._queue.put(song_path)
        self.pending_jobs.append(song_path)
        logging.info(f"Queued for stem separation: {Path(song_path).name}")

    def _make_worker_process(self) -> Process:
        return Process(
            target=_run_worker_process,
            args=(self._queue, self._result_queue, self._temp_dir, self._pty_slave_fd),
            daemon=False,
        )

    def _drain_results(self) -> None:
        """Remove completed jobs from pending_jobs."""
        while not self._result_queue.empty():
            try:
                self.pending_jobs.remove(self._result_queue.get())
            except ValueError:
                pass


def _setup_processing_logger() -> None:
    """Configure the module logger to write only to stderr (no disk file).

    The stderr fd will have been dup2'd to the PTY slave by the worker, so
    all log output flows to the secondary terminal. On the main process side,
    stderr goes to the main process stderr (normal behaviour).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    processing_logger = logging.getLogger("pikaraoke.lib.processing_manager")
    processing_logger.handlers = []
    processing_logger.addHandler(handler)
    processing_logger.propagate = False
    processing_logger.setLevel(logging.DEBUG)

    sep_logger = logging.getLogger("audio_separator")
    sep_logger.handlers = []
    sep_logger.addHandler(handler)
    sep_logger.setLevel(logging.DEBUG)
    sep_logger.propagate = False

    return processing_logger


def _run_worker_process(
    queue: Queue, result_queue: SimpleQueue, temp_dir: str = "", pty_slave_fd: int | None = None
) -> None:
    """Entry point for the stem processing worker process.

    This runs in a separate process to avoid blocking the main application
    during CPU-intensive stem separation. Exits cleanly when None is received.
    """
    # Redirect stdout/stderr to the PTY slave so all output (including
    # subprocess stderr from ffmpeg) appears in the secondary terminal.
    if pty_slave_fd is not None:
        os.dup2(pty_slave_fd, 1)
        os.dup2(pty_slave_fd, 2)
        os.close(pty_slave_fd)

    processing_logger = _setup_processing_logger()
    processing_logger.info("Stem worker process started")

    from audio_separator.separator import Separator

    separator = Separator(
        model_file_dir=MODEL_DIR,
        output_format=SEPARATION_FORMAT,
    )
    separator.load_model(model_filename=MODEL_NAME)
    processing_logger.info("Audio separator model loaded")

    try:
        while True:
            song_path = queue.get()
            if song_path is None:
                break
            processing_logger.info(f"Processing: {song_path}")

            try:
                _process_song_in_worker(song_path, separator, temp_dir, processing_logger)
            except Exception as e:
                processing_logger.error(f"Stem separation failed for {song_path}: {e}")
            finally:
                result_queue.put(song_path)
    finally:
        del separator
        try:
            import torch

            torch.cuda.empty_cache()
        except ImportError:
            pass
        processing_logger.info("Audio separator model unloaded")


def _process_song_in_worker(
    song_path: str, separator, temp_dir: str = "", logger: logging.Logger | None = None
) -> None:
    """Run the full stem separation pipeline for a single song."""
    if logger is None:
        logger = logging.getLogger("pikaraoke.lib.processing_manager")

    video = Path(song_path)
    if not video.exists():
        raise FileNotFoundError(f"Song file not found: {song_path}")

    vocal_dir = video.parent / "vocal"
    nonvocal_dir = video.parent / "nonvocal"
    vocal_dir.mkdir(exist_ok=True)
    nonvocal_dir.mkdir(exist_ok=True)

    vocal_out = vocal_dir / f"{video.stem}---vocal.m4a"
    nonvocal_out = nonvocal_dir / f"{video.stem}---nonvocal.m4a"

    # Skip if both stems already exist
    if vocal_out.exists() and nonvocal_out.exists():
        logger.info(f"Stems already exist, skipping: {video.name}")
        return

    logger.info(f"Processing stems: {video.name}")

    resolved_temp_dir = get_temp_directory(temp_dir) if temp_dir else None
    tmp_dir = tempfile.mkdtemp(prefix="pikaraoke_stems_", dir=resolved_temp_dir)
    try:
        # Step 1: Extract audio to WAV
        audio_wav = _extract_audio(video, tmp_dir)

        # Step 2: Separate into vocal + instrumental WAV stems
        logger.info("Separating stems")
        vocals_wav, instrumental_wav = _separate_stems(audio_wav, tmp_dir, separator)

        # Step 3: Transcode both stems to M4A
        logger.info("Transcoding stems")
        _wav_to_m4a(vocals_wav, vocal_out)
        _wav_to_m4a(instrumental_wav, nonvocal_out)

        logger.info(f"Stem separation complete: {video.name}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_audio(video_path: Path, tmp_dir: str) -> Path:
    """Extract audio from video file to a temporary WAV."""
    wav_path = Path(tmp_dir) / f"{video_path.stem}_input.wav"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-sample_fmt",
        "s16",
        str(wav_path),
    ]
    # No capture_output: stderr inherits the PTY so progress bars render.
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed (exit code {result.returncode})")
    return wav_path


def _separate_stems(audio_path: Path, tmp_dir: str, separator) -> tuple[Path, Path]:
    """Run audio-separator and return (vocals_wav, instrumental_wav)."""
    separator.output_dir = tmp_dir
    if separator.model_instance:
        separator.model_instance.output_dir = tmp_dir
    output_paths = separator.separate(str(audio_path))

    vocals_wav = None
    instrumental_wav = None
    for p in output_paths:
        full_path = Path(tmp_dir) / Path(p).name
        lower = full_path.name.lower()
        if "vocal" in lower and "no_vocal" not in lower and "instrumental" not in lower:
            vocals_wav = full_path
        elif "instrumental" in lower or "no_vocal" in lower:
            instrumental_wav = full_path

    if not vocals_wav or not instrumental_wav:
        raise RuntimeError(f"Could not identify vocal/instrumental stems in output: {output_paths}")
    return vocals_wav, instrumental_wav


def _wav_to_m4a(wav_path: Path, output_path: Path) -> None:
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
    # No capture_output: stderr inherits the PTY so progress bars render.
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg transcode failed (exit code {result.returncode})")
