"""Processing queue for splitting songs into vocal and instrumental stems."""

import logging
import os
import shutil
import subprocess
import tempfile
from multiprocessing import Process, Queue, SimpleQueue
from pathlib import Path

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.get_platform import get_temp_directory

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

_processing_log_handler: logging.FileHandler | None = None
_processing_log_file: str = ""


def _get_log_handler(temp_dir: str = "") -> logging.FileHandler:
    """Return the shared FileHandler for processing logs (created once)."""
    global _processing_log_handler, _processing_log_file

    resolved_temp_dir = get_temp_directory(temp_dir) if temp_dir else ""
    log_file_path = (
        os.path.join(resolved_temp_dir, "processing_manager.log")
        if resolved_temp_dir
        else "processing_manager.log"
    )

    if _processing_log_handler is None or _processing_log_file != log_file_path:
        if _processing_log_handler is not None:
            _processing_log_handler.close()
        _processing_log_handler = logging.FileHandler(log_file_path)
        _processing_log_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        _processing_log_file = log_file_path
    return _processing_log_handler


class ProcessingManager:
    """Processes downloaded songs into vocal and instrumental stems.

    Subscribes to song_downloaded events and queues each song for background
    stem separation using audio-separator. Outputs are placed in vocal/ and
    nonvocal/ subdirectories beneath the song's parent folder.

    Runs in a separate process to avoid blocking the main application during
    CPU-intensive stem separation.
    """

    def __init__(self, events: EventSystem, temp_dir: str = "") -> None:
        self._events = events
        self._temp_dir = temp_dir
        self._queue: Queue = Queue()
        self._result_queue: SimpleQueue = SimpleQueue()
        self._worker_process: Process | None = None
        self.pending_jobs: list[str] = []

        handler = _get_log_handler(temp_dir)

        processing_logger = logging.getLogger(__name__)
        processing_logger.addHandler(handler)
        processing_logger.propagate = False

        sep_logger = logging.getLogger("audio_separator")
        sep_logger.addHandler(handler)
        sep_logger.setLevel(logging.DEBUG)
        sep_logger.propagate = False

    def start(self) -> None:
        """Start the background worker process and subscribe to events."""
        # Import audio-separator eagerly on the main thread so the heavy
        # PyTorch/numpy import doesn't hold Python's import lock later and
        # block the download thread.
        from audio_separator.separator import Separator  # noqa: F401

        self._events.on("song_downloaded", self.enqueue)
        self._worker_process = self._make_worker_process()
        self._worker_process.start()
        logging.debug("Stem processing queue worker started")

    def stop(self) -> None:
        """Shut down the worker process gracefully."""
        if self._worker_process is None or not self._worker_process.is_alive():
            return
        self._queue.put(None)
        self._worker_process.join(timeout=10)
        if self._worker_process.is_alive():
            self._worker_process.terminate()

    def enqueue(self, song_path: str) -> None:
        """Add a song to the stem processing queue."""
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
            args=(self._queue, self._result_queue, self._temp_dir),
            daemon=False,
        )

    def _drain_results(self) -> None:
        """Remove completed jobs from pending_jobs."""
        while not self._result_queue.empty():
            try:
                self.pending_jobs.remove(self._result_queue.get())
            except ValueError:
                pass


def _run_worker_process(queue: Queue, result_queue: Queue, temp_dir: str = "") -> None:
    """Entry point for the stem processing worker process.

    This runs in a separate process to avoid blocking the main application
    during CPU-intensive stem separation. Exits cleanly when None is received.
    """
    # Configure logging in the worker process
    handler = _get_log_handler(temp_dir)
    processing_logger = logging.getLogger(__name__)
    processing_logger.addHandler(handler)
    processing_logger.setLevel(logging.DEBUG)

    sep_logger = logging.getLogger("audio_separator")
    sep_logger.addHandler(handler)
    sep_logger.setLevel(logging.DEBUG)

    logging.info("Stem worker process started")

    from audio_separator.separator import Separator

    separator = Separator(
        model_file_dir=MODEL_DIR,
        output_format=SEPARATION_FORMAT,
    )
    separator.load_model(model_filename=MODEL_NAME)
    logging.info("Audio separator model loaded")

    try:
        while True:
            song_path = queue.get()
            if song_path is None:
                break
            logging.info(f"Processing: {song_path}")

            try:
                _process_song_in_worker(song_path, separator, temp_dir)
            except Exception as e:
                logging.error(f"Stem separation failed for {song_path}: {e}")
            finally:
                result_queue.put(song_path)
    finally:
        del separator
        try:
            import torch

            torch.cuda.empty_cache()
        except ImportError:
            pass
        logging.info("Audio separator model unloaded")


def _process_song_in_worker(song_path: str, separator, temp_dir: str = "") -> None:
    """Run the full stem separation pipeline for a single song."""
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
        logging.info(f"Stems already exist, skipping: {video.name}")
        return

    logging.info(f"Processing stems: {video.name}")

    resolved_temp_dir = get_temp_directory(temp_dir) if temp_dir else None
    tmp_dir = tempfile.mkdtemp(prefix="pikaraoke_stems_", dir=resolved_temp_dir)
    try:
        # Step 1: Extract audio to WAV
        audio_wav = _extract_audio(video, tmp_dir)

        # Step 2: Separate into vocal + instrumental WAV stems
        logging.info("Separating stems")
        vocals_wav, instrumental_wav = _separate_stems(audio_wav, tmp_dir, separator)

        # Step 3: Transcode both stems to M4A
        logging.info("Transcoding stems")
        _wav_to_m4a(vocals_wav, vocal_out)
        _wav_to_m4a(instrumental_wav, nonvocal_out)

        logging.info(f"Stem separation complete: {video.name}")
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg transcode failed: {result.stderr}")
