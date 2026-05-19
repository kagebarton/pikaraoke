"""Whisper worker: stable-ts subprocess with per-encoder-pass cancellation.

Runs stable-ts in a dedicated subprocess, mirroring StemWorker architecture.
This isolates the main process from CUDA faults (OOM, segfault, wedged
stream) and enables auto-restart on failure.

The model is loaded once and stays loaded across jobs. If alignment is
cancelled, the exception unwinds cleanly and the model weights survive.

Conversion helpers (``_extract_words``, ``_segments_to_line_objects``)
live here so they are available to the subprocess entry point without
importing from the stage module. Word-to-line matching for alignment
mode is the caller's responsibility — see
``pikaraoke.lib.word_alignment.match_words_to_lines``.

PTY routing: when ``pty_slave_path`` is provided, the worker opens
that PTY device and redirects stdout/stderr to it via fd-level dup2 at
subprocess entry. This captures C-level writes (CTranslate2,
stable-ts) that Python-level redirects would miss. The path (rather
than an inherited fd) is required because the worker is spawned, not
forked, and spawn'd children cannot inherit file descriptors from the
parent.

AudioLoader FFmpeg subprocess cleanup:
On cancellation, the Aligner's while loop exits via exception, skipping
the normal audio_loader.terminate() cleanup. The orphaned FFmpeg process
would produce "Broken pipe" stderr messages when eventually killed by GC.
We prevent this by:
1. Monkey-patching AudioLoader._audio_loading_process() to redirect
FFmpeg stderr to /dev/null (harmless muxer errors never reach terminal).
2. Explicitly terminating orphaned AudioLoaders in the cancel handler.
"""

import gc
import logging
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import warnings
from dataclasses import asdict
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Optional

from pikaraoke.pipeline.config import (
    AlignKwargs,
    LoadModelKwargs,
    PostProcessKwargs,
    RefineKwargs,
    TranscribeKwargs,
    WhisperModelConfig,
)
from pikaraoke.pipeline.workers._ipc import (
    WORKER_CONTEXT,
    WorkerDiedError,
    drain_pipe,
    forward_cancel,
)

logger = logging.getLogger(__name__)

# Timeout for waiting for the whisper subprocess to become ready after
# model load. On the target hardware, large-v3-turbo loads in ~10s, so
# 60s gives ~6× headroom.
WHISPER_LOAD_TIMEOUT_SEC = 60

# stable-ts emits "<n>/<m> segments failed to align." as a UserWarning at
# the end of Aligner.align(). align_check captures this so the stage can
# decide whether align()'s forced word placement is trustworthy before
# spending time on refine().
_ALIGN_FAILURE_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s+segments failed to align")


def _extract_align_failure_ratio(caught_warnings, worker_log: logging.Logger) -> float:
    """Scan captured warnings for stable-ts's 'N/M segments failed to align'
    message and return N/M. Every captured warning is re-emitted via
    ``worker_log`` so capturing doesn't silently swallow them. Returns 0.0
    if no failure warning is present or the message couldn't be parsed.
    """
    ratio = 0.0
    for w in caught_warnings:
        msg = str(w.message)
        m = _ALIGN_FAILURE_RE.search(msg)
        if m:
            failed, total = int(m.group(1)), int(m.group(2))
            if total > 0:
                ratio = failed / total
        worker_log.warning("%s: %s", w.category.__name__, msg)
    return ratio


class _CancelledInsideEncoder(Exception):
    """Raised by the forward pre-hook when cancel is detected.

    This exception unwinds through: pre_hook() → nn.Module.__call__() →
    encoder.forward() → inference_func() → _compute_timestamps() → while
    loop → Aligner.align() → model.align()  or: pre_hook() →
    nn.Module.__call__() → encoder.forward() → inference_func() →
    Refiner.get_prob() → while loop → Refiner._refine() → model.refine()

    The model weights survive because they're nn.Parameter attributes on the
    Whisper nn.Module (stored on GPU/CPU), not stack locals that get destroyed
    during unwinding.

    Must remain at module scope — the cancel hook closure inside
    _run_with_cancel_hook captures it from the enclosing module scope,
    not from the function body.
    """


class AlignmentCancelledError(Exception):
    """Raised when alignment was cancelled mid-computation (model still loaded)."""


# ============================================================================
# Config helpers
# ============================================================================


def _splat(section) -> dict:
    """Return section's fields as kwargs, dropping None values so
    stable-ts defaults apply for unset options."""
    return {k: v for k, v in asdict(section).items() if v is not None}


def _rebuild_config(d: dict) -> WhisperModelConfig:
    """Reconstruct WhisperModelConfig from its asdict() form.

    asdict() flattens nested dataclasses to nested dicts; this rebuilds
    each section back into its dataclass so attribute access works in
    the subprocess.
    """
    return WhisperModelConfig(
        load_model=LoadModelKwargs(**d["load_model"]),
        align=AlignKwargs(**d["align"]),
        transcribe=TranscribeKwargs(**d["transcribe"]),
        refine=RefineKwargs(**d["refine"]),
        align_post_process=PostProcessKwargs(**d["align_post_process"]),
        transcribe_post_process=PostProcessKwargs(**d["transcribe_post_process"]),
        regroup=d["regroup"],
    )


def _apply_post_process(result, pp: PostProcessKwargs) -> None:
    """Apply WhisperResult post-processing steps in-place.

    Each field controls a separate stable-ts call; None disables.
    """
    if pp.adjust_gaps_threshold is not None:
        result.adjust_gaps(duration_threshold=pp.adjust_gaps_threshold)
    if pp.merge_by_gap_min is not None:
        result.merge_by_gap(min_gap=pp.merge_by_gap_min)


# ============================================================================
# Conversion helpers: WhisperResult → line_objects (JSON-serializable)
# ============================================================================
#
# These functions convert stable-ts WhisperResult objects into plain
# list[dict] structures that cross the subprocess boundary via Pipe
# (pickle). They are the IPC contract between the worker subprocess and
# LyricAlignStage.


def _extract_words(result, min_word_probability: float) -> list[dict]:
    """Flatten WhisperResult into [{word, start, end}, ...].

    Drops words with ``probability < min_word_probability``. These are
    silent-region hallucinations: stable-ts emits them when forced to
    transcribe an unintelligible region, clustered at a single
    zero-duration timestamp. Letting the matcher anchor to them collapses
    whole lines to that timestamp. Pass 0 to disable the filter.
    """
    all_words = []
    dropped = 0
    for segment in result.segments:
        for word in segment.words:
            prob = getattr(word, "probability", None)
            if prob is not None and prob < min_word_probability:
                dropped += 1
                continue
            all_words.append(
                {
                    "word": word.word.strip(),
                    "start": word.start,
                    "end": word.end,
                }
            )
    if dropped:
        logger.info(
            "Dropped %d low-probability whisper words (< %.4f)",
            dropped,
            min_word_probability,
        )
    return all_words


def _segments_to_line_objects(result) -> list[dict]:
    """Build line objects directly from stable-ts segments (transcription mode).

    Each segment becomes one subtitle line; its words are used for karaoke
    timing. Segments with no words are skipped.
    """
    line_objects = []
    for segment in result.segments:
        if not segment.words:
            continue
        words = [
            {
                "word": w.word.strip(),
                "start": w.start,
                "end": w.end,
            }
            for w in segment.words
        ]
        line_objects.append(
            {
                "text": segment.text.strip(),
                "words": words,
                "start": words[0]["start"],
                "end": words[-1]["end"],
            }
        )
    return line_objects


# ============================================================================
# WhisperWorker — parent-side façade
# ============================================================================


class WhisperWorker:
    """Whisper inference worker with subprocess isolation.

    Runs stable-ts in a dedicated subprocess, mirroring StemWorker
    architecture. This isolates the main process from CUDA faults (OOM,
    segfault, wedged stream) and enables auto-restart on failure.

    The subprocess model is loaded on ``start()`` and stays loaded across
    jobs. On cancellation, the encoder hook fires, the exception unwinds
    cleanly, and the model weights survive.

    Public API:
    start() / stop() / kill() / is_alive() — lifecycle
    align_check(vocal_path, lyrics_text, cancel_event) — align only, returns
        {"fail_ratio": float, "result_id": str} so the caller can gate on
        the failure ratio before paying for refine
    refine_from_cached(result_id, vocal_path, cancel_event) — refine an
        align result previously cached by align_check
    discard_cached(result_id) — evict a cached align result without refining
    transcribe_words(vocal_path, cancel_event) — transcribe → regroup →
        refine, returns flat words (for the tiling matcher)
    transcribe_refine(vocal_path, cancel_event) — transcribe → regroup →
        refine, returns line_objects (transcription-only mode)
    """

    def __init__(
        self,
        config: Optional[WhisperModelConfig] = None,
        pty_slave_path: str | None = None,
    ) -> None:
        self._config = config or WhisperModelConfig()
        self._pty_slave_path = pty_slave_path

        # --- Subprocess state ---
        self._process = None
        self._job_send: Optional[Connection] = None
        self._job_recv: Optional[Connection] = None
        self._result_recv: Optional[Connection] = None
        self._result_send: Optional[Connection] = None
        self._cancel_send: Optional[Connection] = None
        self._cancel_recv: Optional[Connection] = None

    # ------------------------------------------------------------------
    # Subprocess lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the subprocess with fresh IPC channels, wait for ready.

        Blocks until the subprocess loads the model and sends ("ready",),
        or until WHISPER_LOAD_TIMEOUT_SEC, or until the subprocess dies.

        Raises:
            WorkerDiedError: If the subprocess dies during model load.
            TimeoutError: If the subprocess doesn't become ready in time.
        """
        self._close_all_connections()

        job_recv, job_send = Pipe(duplex=False)
        self._job_send = job_send
        self._job_recv = job_recv

        result_recv, result_send = Pipe(duplex=False)
        self._result_recv = result_recv
        self._result_send = result_send

        cancel_recv, cancel_send = Pipe(duplex=False)
        self._cancel_send = cancel_send
        self._cancel_recv = cancel_recv

        self._process = WORKER_CONTEXT.Process(
            target=_worker_main,
            args=(
                job_recv,
                result_send,
                cancel_recv,
                asdict(self._config),
                logger.getEffectiveLevel(),
                self._pty_slave_path,
            ),
            daemon=True,
        )
        self._process.start()
        logger.info("Whisper worker subprocess started (PID %d)", self._process.pid)

        # Block until ready or death.
        deadline = time.monotonic() + WHISPER_LOAD_TIMEOUT_SEC
        while True:
            if self._result_recv.poll(0.5):
                try:
                    msg = self._result_recv.recv()
                except EOFError:
                    # Subprocess died and closed its end of the pipe before
                    # sending ("ready",). Convert to WorkerDiedError so the
                    # orchestrator surfaces a clean failure.
                    raise WorkerDiedError(
                        f"Whisper worker pipe closed during model load "
                        f"(exit={self._process.exitcode})"
                    )
                if msg == ("ready",):
                    logger.info("Whisper worker ready (subprocess PID %d)", self._process.pid)
                    return
                raise RuntimeError(f"Unexpected boot message: {msg}")
            if not self._process.is_alive():
                raise WorkerDiedError(
                    f"Whisper worker died during model load " f"(exit={self._process.exitcode})"
                )
            if time.monotonic() > deadline:
                self.kill()
                raise TimeoutError("Whisper worker did not become ready in time")

    def stop(self) -> None:
        """Graceful shutdown: send sentinel, join, fall back to kill."""
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
        self._close_all_connections()

    def kill(self) -> None:
        """SIGKILL the subprocess and discard IPC channels."""
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
        self._close_all_connections()

    def is_alive(self) -> bool:
        """Return True if the subprocess is running."""
        return self._process is not None and self._process.is_alive()

    # ------------------------------------------------------------------
    # Public inference methods
    # ------------------------------------------------------------------

    def transcribe_refine(
        self,
        vocal_path: Path,
        cancel_event: Optional[threading.Event] = None,
    ) -> list[dict]:
        """Run transcribe() then refine(), returning line_objects.

        Sends job to subprocess, blocks for result.

        Returns: list[LineObject] — JSON-serializable dicts.

        Raises:
            AlignmentCancelledError: If either phase was cancelled.
            WorkerDiedError: If the subprocess dies during the job.
            RuntimeError: If the subprocess reports an error.
        """
        return self._run_job(
            ("transcribe_refine", str(vocal_path)),
            cancel_event,
        )

    def align_check(
        self,
        vocal_path: Path,
        lyrics_text: str,
        cancel_event: Optional[threading.Event] = None,
    ) -> dict:
        """Run align() only; return {"fail_ratio": float, "result_id": str,
        "words": list[dict]}.

        ``words`` is the pre-refine word list extracted from the cached
        align result. Refine only nudges timestamps; it never adds or
        removes tokens. So the caller can run the walk matcher against
        these words to compute a collapse-ratio escalation signal
        *before* paying for refine — catching the failure mode where
        stable-ts force-places long runs of tokens at a single timestamp
        (segments don't fail, but the timing is garbage).

        The aligned WhisperResult stays cached in the subprocess under
        ``result_id`` so the caller can either follow up with
        ``refine_from_cached`` or discard it via ``discard_cached``.

        Raises:
            AlignmentCancelledError: If align was cancelled. No result is
                cached in this case.
            WorkerDiedError, RuntimeError: As for align_refine.
        """
        return self._run_job(
            ("align_check", str(vocal_path), lyrics_text),
            cancel_event,
        )

    def refine_from_cached(
        self,
        result_id: str,
        vocal_path: Path,
        cancel_event: Optional[threading.Event] = None,
    ) -> list[dict]:
        """Refine a cached align result and return a flat word list.

        Raises:
            RuntimeError: If ``result_id`` is not in the cache (worker
                restart between align_check and refine_from_cached, or a
                discard_cached call already evicted it). The caller should
                treat this as a hard failure — do not silently re-align.
        """
        return self._run_job(
            ("refine_from_cached", result_id, str(vocal_path)),
            cancel_event,
        )

    def discard_cached(self, result_id: str) -> None:
        """Evict a cached align result without refining. Fast; no cancel.

        Returns silently if ``result_id`` is unknown (already evicted, or
        the subprocess restarted) — the goal is freeing memory, not
        confirming presence.
        """
        self._run_job(("discard_cached", result_id), cancel_event=None)

    def transcribe_words(
        self,
        vocal_path: Path,
        cancel_event: Optional[threading.Event] = None,
    ) -> list[dict]:
        """Run transcribe → regroup → refine, returning a flat word list.

        Same heavy pipeline as ``transcribe_refine`` but flattened for the
        tiling matcher (which does its own line segmentation).
        """
        return self._run_job(
            ("transcribe_words", str(vocal_path)),
            cancel_event,
        )

    # ------------------------------------------------------------------
    # Subprocess job dispatch
    # ------------------------------------------------------------------

    def _run_job(
        self,
        job: tuple,
        cancel_event: Optional[threading.Event],
    ) -> list[dict]:
        """Send a job to the subprocess and wait for the result.

        Mirrors StemWorker.separate() with auto-restart and cancel
        forwarding.

        Args:
            job: Tuple to send on the job pipe.
            cancel_event: Optional threading.Event from the orchestrator.

        Returns:
            list[dict]: line_objects on success.

        Raises:
            AlignmentCancelledError: On ("cancelled",) from subprocess.
            RuntimeError: On ("error", msg) from subprocess.
            WorkerDiedError: If subprocess dies during the job.
        """
        proc = self._process

        if proc is None:
            raise WorkerDiedError("Whisper worker is not running")

        # Auto-restart if the subprocess died between jobs (e.g. after OOM).
        if not proc.is_alive():
            logger.warning(
                "Whisper worker subprocess (PID %s) is not alive; restarting before next job",
                proc.pid,
            )
            self.start()
            proc = self._process
            if proc is None:
                raise WorkerDiedError("Whisper worker failed to restart")

            # Fast-fail: if the cancel event was already set before we
            # even send the job, don't bother round-tripping the
            # freshly-loaded subprocess.
            if cancel_event is not None and cancel_event.is_set():
                raise AlignmentCancelledError("Cancelled during whisper worker restart")

        rq = self._result_recv
        js = self._job_send

        if rq is None or js is None:
            raise WorkerDiedError("Whisper worker IPC channels are not available")

        # Clear any stale cancel signal from a prior job.
        if self._cancel_recv is not None:
            drain_pipe(self._cancel_recv)

        js.send(job)

        # Forward threading.Event → cancel Pipe via a daemon thread.
        cancel_forwarder: threading.Thread | None = None
        if cancel_event is not None and self._cancel_send is not None:
            cancel_forwarder = threading.Thread(
                target=forward_cancel,
                args=(cancel_event, self._cancel_send),
                daemon=True,
            )
            cancel_forwarder.start()

        # Block until result.
        try:
            while True:
                if rq.poll(0.5):
                    try:
                        msg = rq.recv()
                    except EOFError:
                        raise WorkerDiedError(
                            f"Whisper worker pipe closed during job "
                            f"(exit={self._process.exitcode if self._process else '?'})"
                        )
                    break
                if not proc.is_alive():
                    raise WorkerDiedError(
                        f"Whisper worker died during job " f"(exit={proc.exitcode})"
                    )
        finally:
            if self._cancel_recv is not None:
                drain_pipe(self._cancel_recv)

        tag = msg[0]
        if tag == "ok":
            return msg[1]
        if tag == "cancelled":
            raise AlignmentCancelledError("Alignment cancelled (model still loaded)")
        raise RuntimeError(f"Whisper worker error: {msg[1]}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _close_all_connections(self) -> None:
        for conn in (
            self._job_send,
            self._job_recv,
            self._result_recv,
            self._result_send,
            self._cancel_send,
            self._cancel_recv,
        ):
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
        self._job_send = None
        self._job_recv = None
        self._result_recv = None
        self._result_send = None
        self._cancel_send = None
        self._cancel_recv = None


# ============================================================================
# Subprocess entry point
# ============================================================================


def _worker_main(
    job_recv: Connection,
    result_send: Connection,
    cancel_recv: Connection,
    config_dict: dict,
    log_level: int = logging.INFO,
    pty_slave_path: str | None = None,
) -> None:
    """Entry point for the whisper worker subprocess.

    Loads the stable-ts model, then loops on job_recv. For each job,
    it runs the requested inference (align_check, refine_from_cached,
    transcribe_words, or transcribe_refine)
    with per-encoder-pass cancellation via forward pre-hook.

    Results sent on result_send:
    - ("ready",) once after model load
    - ("ok", line_objects) on success
    - ("cancelled",) when cancelled between encoder passes
    - ("error", message) on failure (including OOM)
    """
    # Route output to secondary terminal if a PTY path was provided.
    # The worker is spawn'd, so it must open the slave by path rather
    # than rely on inherited file descriptors. Permanent redirection
    # for the subprocess lifetime.
    if pty_slave_path is not None:
        try:
            pty_fd = os.open(pty_slave_path, os.O_WRONLY)
            os.dup2(pty_fd, 1)
            os.dup2(pty_fd, 2)
            os.close(pty_fd)
        except OSError:
            # Fall back to the parent's stdout/stderr if the PTY can't
            # be opened (e.g. parent already tore the terminal down).
            pass

    # Belt-and-suspenders: if anything in this function raises, write the
    # traceback to a known log file before the subprocess dies. The PTY
    # closes too quickly to read the error otherwise.
    try:
        _whisper_worker_main_inner(job_recv, result_send, cancel_recv, config_dict, log_level)
    except BaseException:
        import traceback

        from pikaraoke.lib.get_platform import get_temp_directory

        try:
            crash_log = os.path.join(get_temp_directory(), "whisper_worker_crash.log")
            with open(crash_log, "a") as f:
                f.write(f"--- whisper worker crash (pid {os.getpid()}) ---\n")
                traceback.print_exc(file=f)
        except OSError:
            pass
        raise


def _whisper_worker_main_inner(
    job_recv: Connection,
    result_send: Connection,
    cancel_recv: Connection,
    config_dict: dict,
    log_level: int,
) -> None:
    worker_log = _setup_worker_logger(log_level)
    worker_log.info("Whisper worker process started (PID %d)", os.getpid())

    import stable_whisper
    import torch

    # Resolve OOM exception types once.
    oom_exc_types: tuple[type[BaseException], ...] = (
        getattr(torch.cuda, "OutOfMemoryError", RuntimeError),
        MemoryError,
    )

    # Reconstruct config from dict.
    config = _rebuild_config(config_dict)

    device = config.load_model.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    worker_log.info(f"Loading whisper model: {config.load_model.model_path} on {device}")
    start = time.time()

    model = stable_whisper.load_model(
        config.load_model.model_path,
        device=device,
    )
    encoder_module = model.encoder

    elapsed = time.time() - start
    worker_log.info(f"Whisper model loaded in {elapsed:.1f}s (device={device})")

    # Patch AudioLoader in the subprocess too.
    _patch_audioloader_stderr_in_subprocess(worker_log)

    # Result-cache for the split align_check → refine_from_cached flow.
    # Single-entry; a new align_check evicts the previous result, and
    # refine_from_cached pops on use. Crossing the IPC boundary with a
    # WhisperResult would require pickling stable-ts internals — keeping
    # the result here means the parent only ever sees an opaque id.
    cached_results: dict[str, Any] = {}

    # Signal ready so the parent's start() can return.
    result_send.send(("ready",))

    try:
        while True:
            item = job_recv.recv()
            if item is None:
                break

            kind = item[0]

            # Drain any stale cancel signals before starting the job.
            drain_pipe(cancel_recv)

            try:
                if kind == "align_check":
                    _, vocal_path, lyrics_text = item
                    raw_result, fail_ratio = _do_align_only(
                        model,
                        encoder_module,
                        vocal_path,
                        lyrics_text,
                        cancel_recv,
                        config,
                        worker_log,
                    )
                    # Extract pre-refine words so the stage can compute a
                    # collapse-ratio escalation signal without paying for
                    # refine. No probability filter — collapse detection
                    # cares about timestamps, not word confidence.
                    raw_words = _extract_words(raw_result, 0.0)
                    result_id = uuid.uuid4().hex
                    cached_results.clear()
                    cached_results[result_id] = raw_result
                    result_send.send(
                        (
                            "ok",
                            {
                                "fail_ratio": fail_ratio,
                                "result_id": result_id,
                                "words": raw_words,
                            },
                        )
                    )
                elif kind == "refine_from_cached":
                    _, result_id, vocal_path = item
                    cached = cached_results.pop(result_id, None)
                    if cached is None:
                        result_send.send(("error", f"stale or unknown result_id: {result_id}"))
                    else:
                        words = _do_refine_from_cached(
                            model,
                            encoder_module,
                            vocal_path,
                            cached,
                            cancel_recv,
                            config,
                            worker_log,
                        )
                        result_send.send(("ok", words))
                elif kind == "discard_cached":
                    _, result_id = item
                    cached_results.pop(result_id, None)
                    result_send.send(("ok", None))
                elif kind == "transcribe_words":
                    _, vocal_path = item
                    words = _do_transcribe_words(
                        model,
                        encoder_module,
                        vocal_path,
                        cancel_recv,
                        config,
                        worker_log,
                    )
                    result_send.send(("ok", words))
                elif kind == "transcribe_refine":
                    _, vocal_path = item
                    line_objects = _do_transcribe_refine(
                        model,
                        encoder_module,
                        vocal_path,
                        cancel_recv,
                        config,
                        worker_log,
                    )
                    result_send.send(("ok", line_objects))
                else:
                    result_send.send(("error", f"unknown job kind: {kind}"))
            except _CancelledInsideEncoder:
                worker_log.info("Cancelled mid-encoder; model still loaded")
                _terminate_orphaned_audioloaders()
                result_send.send(("cancelled",))
            except oom_exc_types as e:
                # Same posture as stem_worker: report and exit.
                # OOM leaves CUDA in unsafe condition; fresh subprocess
                # is the only reliable recovery.
                try:
                    worker_log.error(
                        "OOM during whisper %s for %s: %s | "
                        "allocated=%.1fGB reserved=%.1fGB max=%.1fGB",
                        kind,
                        vocal_path,
                        e,
                        torch.cuda.memory_allocated() / 1e9,
                        torch.cuda.memory_reserved() / 1e9,
                        torch.cuda.max_memory_allocated() / 1e9,
                    )
                except Exception as diag_err:
                    worker_log.error(
                        "OOM during whisper %s for %s: %s " "(memory query failed: %s)",
                        kind,
                        vocal_path,
                        e,
                        diag_err,
                    )
                try:
                    result_send.send(("error", f"OOM during whisper {kind}: {e}"))
                except (OSError, BrokenPipeError):
                    pass
                return  # subprocess exits via finally
            except Exception as e:
                worker_log.exception(f"Whisper {kind} failed")
                result_send.send(("error", str(e)))
            finally:
                # Free PyTorch's CUDA cache after every job — success,
                # cancellation, or error — so the next inference starts
                # with maximal free GPU memory. CTranslate2 owns its own
                # memory; this only releases the PyTorch-side cache.
                _clear_gpu_state()
                drain_pipe(cancel_recv)
    finally:
        del model
        _clear_gpu_cache()
        worker_log.info("Whisper model unloaded")


# ============================================================================
# Subprocess inference helpers
# ============================================================================


def _run_with_cancel_hook(encoder_module, cancel_recv, worker_log, label, fn):
    """Run ``fn()`` with a fresh forward pre-hook on the encoder that
    raises ``_CancelledInsideEncoder`` between encoder passes when a
    cancel signal arrives on ``cancel_recv``. The hook is always removed.
    """
    encode_counter = [0]

    def cancel_hook(module, inputs):
        if cancel_recv.poll(0):
            try:
                cancel_recv.recv()
            except (EOFError, OSError):
                pass
            worker_log.info(
                f"Cancel detected before {label} pass #{encode_counter[0] + 1} — aborting"
            )
            raise _CancelledInsideEncoder()
        encode_counter[0] += 1

    handle = encoder_module.register_forward_pre_hook(cancel_hook)
    try:
        return fn()
    finally:
        try:
            handle.remove()
        except Exception:
            pass


def _align_pass(model, encoder_module, vocal_path, lyrics_text, cancel_recv, config, worker_log):
    align_kwargs = _splat(config.align)
    return _run_with_cancel_hook(
        encoder_module,
        cancel_recv,
        worker_log,
        "align",
        lambda: model.align(vocal_path, lyrics_text, **align_kwargs),
    )


def _refine_pass(model, encoder_module, vocal_path, result, cancel_recv, config, worker_log):
    refine_kwargs = _splat(config.refine)
    return _run_with_cancel_hook(
        encoder_module,
        cancel_recv,
        worker_log,
        "refine",
        lambda: model.refine(vocal_path, result, **refine_kwargs),
    )


def _transcribe_pass(model, encoder_module, vocal_path, cancel_recv, config, worker_log):
    transcribe_kwargs = _splat(config.transcribe)
    return _run_with_cancel_hook(
        encoder_module,
        cancel_recv,
        worker_log,
        "transcribe",
        lambda: model.transcribe(vocal_path, **transcribe_kwargs),
    )


def _do_align_only(
    model,
    encoder_module,
    vocal_path: str,
    lyrics_text: str,
    cancel_recv: Connection,
    config: WhisperModelConfig,
    worker_log: logging.Logger,
):
    """Run align() only, capturing stable-ts's segment-failure ratio.

    Returns ``(WhisperResult, fail_ratio)``. The caller decides whether to
    follow up with refine_from_cached (good alignment) or discard the
    result and escalate to the tiling pipeline (bad alignment).
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = _align_pass(
            model, encoder_module, vocal_path, lyrics_text, cancel_recv, config, worker_log
        )
    fail_ratio = _extract_align_failure_ratio(caught, worker_log)
    return result, fail_ratio


def _do_refine_from_cached(
    model,
    encoder_module,
    vocal_path: str,
    cached_result,
    cancel_recv: Connection,
    config: WhisperModelConfig,
    worker_log: logging.Logger,
) -> list[dict]:
    """Refine an already-aligned WhisperResult, post-process, and flatten
    to a word list. Mirrors the back half of the old align_refine path.
    """
    refined = _refine_pass(
        model, encoder_module, vocal_path, cached_result, cancel_recv, config, worker_log
    )
    _apply_post_process(refined, config.align_post_process)
    return _extract_words(refined, config.align_post_process.min_word_probability)


def _do_transcribe_words(
    model,
    encoder_module,
    vocal_path: str,
    cancel_recv: Connection,
    config: WhisperModelConfig,
    worker_log: logging.Logger,
) -> list[dict]:
    """Run transcribe → regroup → refine and return a flat word list.

    Used by the tiling matcher, which needs flat tokens (not line_objects)
    over the IPC boundary because tiling does its own line segmentation.
    """
    result = _transcribe_pass(model, encoder_module, vocal_path, cancel_recv, config, worker_log)
    if config.regroup:
        worker_log.info(f"Regrouping transcription segments: {config.regroup}")
        result.regroup(config.regroup)
    refined = _refine_pass(
        model, encoder_module, vocal_path, result, cancel_recv, config, worker_log
    )
    _apply_post_process(refined, config.transcribe_post_process)
    return _extract_words(refined, config.transcribe_post_process.min_word_probability)


def _do_transcribe_refine(
    model,
    encoder_module,
    vocal_path: str,
    cancel_recv: Connection,
    config: WhisperModelConfig,
    worker_log: logging.Logger,
) -> list[dict]:
    """Run transcribe → regroup → refine and return line_objects.

    Transcription mode (no lyrics file) — one segment becomes one line.
    """
    result = _transcribe_pass(model, encoder_module, vocal_path, cancel_recv, config, worker_log)
    if config.regroup:
        worker_log.info(f"Regrouping transcription segments: {config.regroup}")
        result.regroup(config.regroup)
    refined = _refine_pass(
        model, encoder_module, vocal_path, result, cancel_recv, config, worker_log
    )
    _apply_post_process(refined, config.transcribe_post_process)
    return _segments_to_line_objects(refined)


# ============================================================================
# Module-level helpers (used by subprocess)
# ============================================================================


def _terminate_orphaned_audioloaders() -> None:
    """Terminate any orphaned AudioLoader FFmpeg subprocesses.

    Used by both the in-process WhisperWorker method and the subprocess
    _worker_main cancel handler.
    """
    try:
        from stable_whisper.audio import AudioLoader
    except ImportError:
        return

    terminated_count = 0
    for obj in gc.get_objects():
        if isinstance(obj, AudioLoader):
            process = getattr(obj, "_process", None)
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                terminated_count += 1

            extra_process = getattr(obj, "_extra_process", None)
            if extra_process is not None and extra_process.poll() is None:
                try:
                    extra_process.terminate()
                    extra_process.wait(timeout=2)
                except Exception:
                    try:
                        extra_process.kill()
                    except Exception:
                        pass
                terminated_count += 1

    if terminated_count > 0:
        logging.getLogger(__name__).debug(
            f"Terminated {terminated_count} orphaned FFmpeg subprocess(es)"
        )


def _patch_audioloader_stderr_in_subprocess(worker_log: logging.Logger) -> None:
    """Monkey-patch AudioLoader._audio_loading_process() in the subprocess."""
    try:
        from stable_whisper.audio import AudioLoader
    except ImportError:
        worker_log.debug("Could not import AudioLoader — skipping stderr patch")
        return

    original_audio_loading_process = AudioLoader._audio_loading_process

    def _quiet_audio_loading_process(self_loader):
        """Patched _audio_loading_process that redirects FFmpeg stderr."""
        if not isinstance(self_loader.source, str) or not self_loader._stream:
            return original_audio_loading_process(self_loader)

        from stable_whisper.audio.utils import load_source

        only_ffmpeg = False
        source = load_source(
            self_loader.source,
            verbose=self_loader.verbose,
            only_ffmpeg=only_ffmpeg,
            return_dict=True,
        )
        if isinstance(source, dict):
            info = source
            source = info.pop("popen")
        else:
            info = None

        if info and info.get("duration"):
            self_loader._duration_estimation = info["duration"]
        if not self_loader._stream and info and info.get("is_live"):
            import warnings

            warnings.warn(
                "The audio appears to be a continuous stream but "
                "setting was set to `stream=False`."
            )

        if isinstance(source, subprocess.Popen):
            self_loader._extra_process = source
            stdin = source.stdout
        else:
            stdin = None

        try:
            cmd = [
                "ffmpeg",
                "-loglevel",
                "error",
                "-nostdin",
                "-threads",
                "0",
                "-i",
                self_loader.source if stdin is None else "pipe:",
                "-f",
                "s16le",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                "-ar",
                str(self_loader._sr),
                "-",
            ]
            out = subprocess.Popen(
                cmd,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to load audio: {e}") from e

        return out

    AudioLoader._audio_loading_process = _quiet_audio_loading_process
    worker_log.debug(
        "Patched AudioLoader._audio_loading_process() to suppress " "FFmpeg broken-pipe stderr"
    )


def _clear_gpu_state() -> None:
    """Clear intermediate GPU state after every inference run."""
    _clear_gpu_cache()


def _clear_gpu_cache() -> None:
    """Clear PyTorch GPU cache on worker shutdown."""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _setup_worker_logger(log_level: int = logging.INFO) -> logging.Logger:
    """Configure the worker subprocess logger."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    )
    worker_logger = logging.getLogger("pikaraoke.pipeline.workers.whisper_worker")
    worker_logger.handlers = []
    worker_logger.addHandler(handler)
    worker_logger.propagate = False
    worker_logger.setLevel(log_level)

    # Also configure stable_whisper's logger to suppress its noisy defaults.
    sw_logger = logging.getLogger("stable_whisper")
    sw_logger.handlers = []
    sw_logger.addHandler(handler)
    sw_logger.setLevel(log_level)
    sw_logger.propagate = False

    return worker_logger
