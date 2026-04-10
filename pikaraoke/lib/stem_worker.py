"""Persistent subprocess worker for stem separation.

Owns the audio-separator model lifecycle. Runs in a ``multiprocessing.Process``
that loads the model once and processes separation jobs via a ``Pipe``.

Both job and result channels use ``multiprocessing.Pipe()`` (direct OS pipe
write, no feeder thread) so that gevent monkey-patching in the parent process
does not interfere with IPC in either direction.
"""

import logging
import os
import sys
from multiprocessing import Pipe, Process
from multiprocessing.connection import Connection
from pathlib import Path

# Model for audio-separator: MelBand Roformer Karaoke — best single-model
# vocal clarity with complementary 2-stem output.
MODEL_NAME = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"

# Where audio-separator stores downloaded models (~400 MB on first run).
MODEL_DIR = "./audio-separator/models"

# Intermediate format for separation (lossless before final transcode).
SEPARATION_FORMAT = "wav"


class WorkerDiedError(Exception):
    """Raised when the stem worker subprocess dies during a job."""


class StemWorker:
    """A persistent subprocess that holds the stem separation model.

    The worker process is spawned on ``start()``, loads the model, and then
    loops on an input pipe connection. Both job and result channels use
    ``Pipe()`` (direct OS pipe write, no feeder thread) to avoid gevent
    monkey-patching interference with ``Queue``'s ``QueueFeederThread``.

    Pipes are created fresh on every ``start()`` so that ``kill()`` + restart
    doesn't leave orphan IPC state.
    """

    def __init__(self, pty_slave_fd: int | None, temp_dir: str) -> None:
        self._pty_slave_fd = pty_slave_fd
        self._temp_dir = temp_dir
        self._process: Process | None = None
        self._job_send: Connection | None = None
        self._job_recv: Connection | None = None
        self._result_recv: Connection | None = None
        self._result_send: Connection | None = None

    def start(self) -> None:
        """Spawn the subprocess with fresh IPC channels.

        Closes any existing connections before creating new ones to prevent
        fd leaks on repeated crash + restart cycles.
        """
        for conn in (self._job_send, self._job_recv, self._result_recv, self._result_send):
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
        self._job_send = None
        self._job_recv = None
        self._result_recv = None
        self._result_send = None

        job_recv, job_send = Pipe(duplex=False)
        self._job_send = job_send
        self._job_recv = job_recv
        result_recv, result_send = Pipe(duplex=False)
        self._result_recv = result_recv
        self._result_send = result_send
        self._process = Process(
            target=_stem_worker_main,
            args=(
                self._job_recv,
                self._result_send,
                self._temp_dir,
                self._pty_slave_fd,
            ),
            daemon=True,
        )
        self._process.start()

    def is_alive(self) -> bool:
        """Return True if the subprocess is running."""
        return self._process is not None and self._process.is_alive()

    def separate(self, wav_path: Path, output_dir: Path) -> tuple[Path, Path]:
        """Submit a WAV for separation. Blocks until the worker returns a result.

        Raises ``WorkerDiedError`` if the worker dies mid-job.
        """
        rq = self._result_recv
        js = self._job_send
        proc = self._process
        if rq is None or js is None or proc is None:
            raise WorkerDiedError("Stem worker is not running")

        js.send((str(wav_path), str(output_dir)))
        while True:
            if rq.poll(0.5):
                msg = rq.recv()
                break
            if not proc.is_alive():
                raise WorkerDiedError("Stem worker died during separation")

        tag = msg[0]
        if tag == "ok":
            return Path(msg[1]), Path(msg[2])
        raise RuntimeError(f"Stem worker error: {msg[1]}")

    def kill(self) -> None:
        """SIGKILL the subprocess and discard IPC channels. Does not restart."""
        if self._process is not None and self._process.is_alive():
            try:
                self._process.kill()
            except OSError:
                pass
            try:
                self._process.join(timeout=3)
            except OSError:
                pass
        self._process = None
        for conn in (self._job_send, self._job_recv, self._result_recv, self._result_send):
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
        self._job_send = None
        self._job_recv = None
        self._result_recv = None
        self._result_send = None

    def stop(self) -> None:
        """Graceful shutdown: send sentinel, join, fall back to kill on timeout."""
        if self._process is None or not self._process.is_alive():
            return
        js = self._job_send
        if js is not None:
            try:
                js.send(None)
            except OSError:
                pass
        try:
            self._process.join(timeout=10)
        except OSError:
            pass
        if self._process is not None and self._process.is_alive():
            try:
                self._process.kill()
            except OSError:
                pass
            try:
                self._process.join(timeout=3)
            except OSError:
                pass


def _setup_processing_logger() -> logging.Logger:
    """Configure the module logger to write only to stderr (no disk file).

    The stderr fd will have been dup2'd to the PTY slave by the worker, so
    all log output flows to the secondary terminal. On the main process side,
    stderr goes to the main process stderr (normal behaviour).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    processing_logger = logging.getLogger("pikaraoke.lib.stem_worker")
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


def _stem_worker_main(
    job_recv: Connection,
    result_send: Connection,
    temp_dir: str = "",
    pty_slave_fd: int | None = None,
) -> None:
    """Entry point for the stem separation worker subprocess.

    Redirects stdout/stderr to the PTY slave, loads the model, then loops
    on ``job_recv``. Results are sent on ``result_send`` as:
    - ``("ok", vocal_path, instrumental_path)`` on success.
    - ``("error", message)`` on failure.
    """
    # Redirect stdout/stderr to the PTY slave.
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
            item = job_recv.recv()
            if item is None:
                break
            wav_path_str, output_dir_str = item
            wav_path = Path(wav_path_str)
            output_dir = Path(output_dir_str)
            processing_logger.info(f"Separating: {wav_path.name}")

            try:
                vocal_wav, instrumental_wav = _separate_in_worker(
                    wav_path, output_dir, separator, processing_logger
                )
                result_send.send(("ok", str(vocal_wav), str(instrumental_wav)))
            except Exception as e:
                processing_logger.error(f"Stem separation failed for {wav_path}: {e}")
                result_send.send(("error", str(e)))
    finally:
        del separator
        try:
            import torch

            torch.cuda.empty_cache()
        except ImportError:
            pass
        processing_logger.info("Audio separator model unloaded")


def _separate_in_worker(
    audio_path: Path,
    tmp_dir: Path,
    separator,
    logger: logging.Logger,
) -> tuple[Path, Path]:
    """Run audio-separator and return (vocals_wav, instrumental_wav)."""
    separator.output_dir = str(tmp_dir)
    if separator.model_instance:
        separator.model_instance.output_dir = str(tmp_dir)
    output_paths = separator.separate(str(audio_path))

    vocals_wav = None
    instrumental_wav = None
    for p in output_paths:
        full_path = Path(tmp_dir) / Path(p).name
        lower = full_path.name.lower()
        # "no vocal" / "no_vocal" must be excluded from the vocals match
        no_vocal = "no vocal" in lower or "no_vocal" in lower
        if "vocal" in lower and not no_vocal and "instrumental" not in lower:
            vocals_wav = full_path
        elif "instrumental" in lower or no_vocal:
            instrumental_wav = full_path

    if not vocals_wav or not instrumental_wav:
        raise RuntimeError(
            f"Could not identify vocal/instrumental stems in output: {output_paths}"
        )
    return vocals_wav, instrumental_wav
