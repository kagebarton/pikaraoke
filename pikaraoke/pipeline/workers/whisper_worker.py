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
``pikaraoke.lib.joint_match.match_words_to_lines_joint_with_stats``.

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

import contextlib
import gc
import logging
import os
import subprocess
import sys
import threading
import time
import warnings
from dataclasses import asdict
from multiprocessing import Pipe
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Optional

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
    """Flatten WhisperResult into [{word, start, end, probability?}, ...].

    Drops words with ``probability < min_word_probability``. These are
    silent-region hallucinations: stable-ts emits them when forced to
    transcribe an unintelligible region, clustered at a single
    zero-duration timestamp. Letting the matcher anchor to them collapses
    whole lines to that timestamp. Pass 0 to disable the filter.

    Surviving words keep their probability (when whisper provides one)
    so the joint matcher can weight match scores by word confidence.
    """
    all_words = []
    dropped = 0
    for segment in result.segments:
        for word in segment.words:
            prob = getattr(word, "probability", None)
            if prob is not None and prob < min_word_probability:
                dropped += 1
                continue
            entry = {
                "word": word.word.strip(),
                "start": word.start,
                "end": word.end,
            }
            if prob is not None:
                entry["probability"] = round(prob, 4)
            all_words.append(entry)
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
    align_refine(vocal_path, lyrics_text, cancel_event) — align → refine,
        returns flat words (the joint matcher's align-candidate source)
    transcribe_words(vocal_path, cancel_event, refine=) — transcribe →
        regroup → (optionally) refine, returns flat words (the joint
        matcher's transcribe pass; refine=False on that route)
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

    def align_refine(
        self,
        vocal_path: Path,
        lyrics_text: str,
        cancel_event: Optional[threading.Event] = None,
        *,
        quiet: bool = False,
    ) -> list[dict]:
        """Run align() then refine(), returning a flat refined word list.

        One subprocess job: forced-align the lyrics to the audio, then
        refine the resulting word timestamps. Returns one entry per lyric
        token, in lyric order — the joint matcher's align-candidate source.

        ``quiet`` suppresses stable-ts's per-pass progress bars for this
        job — set it on the many short slice-aligns (cue-align sections,
        windowed re-align spans) whose bars would otherwise scroll the log,
        and leave it off for the one whole-song pass whose bar is useful.

        Raises:
            AlignmentCancelledError: If align or refine was cancelled.
            WorkerDiedError: If the subprocess dies during the job.
            RuntimeError: If the subprocess reports an error.
        """
        return self._run_job(
            ("align_refine", str(vocal_path), lyrics_text, quiet),
            cancel_event,
        )

    def transcribe_words(
        self,
        vocal_path: Path,
        cancel_event: Optional[threading.Event] = None,
        *,
        refine: bool = True,
    ) -> list[dict]:
        """Run transcribe → regroup → (optionally) refine, returning a flat word list.

        Same heavy pipeline as ``transcribe_refine`` but flattened to a
        word list rather than line_objects.

        The joint matcher passes ``refine=False``: its align-won lines use
        align's already-refined per-word timings, and transcribe is only
        consulted for line *placement*, so whisper's word_timestamps
        precision is enough for the lines where transcribe wins. ``refine``
        defaults to True for the transcription-only callers that want
        refined word timestamps.
        """
        return self._run_job(
            ("transcribe_words", str(vocal_path), refine),
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
        forwarder_done: threading.Event | None = None
        if cancel_event is not None and self._cancel_send is not None:
            forwarder_done = threading.Event()
            threading.Thread(
                target=forward_cancel,
                args=(cancel_event, self._cancel_send, forwarder_done),
                daemon=True,
            ).start()

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
            if forwarder_done is not None:
                forwarder_done.set()
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
    it runs the requested inference (align_refine, transcribe_words, or
    transcribe_refine) with per-encoder-pass cancellation via forward
    pre-hook.

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
    _demote_alignment_warnings(worker_log)
    worker_log.info("Whisper worker process started (PID %d)", os.getpid())

    # Must be set before torch initializes CUDA: expandable segments let the
    # caching allocator grow/shrink instead of pinning fixed blocks, which
    # avoids fragmentation OOM when this process shares a small GPU with the
    # stem worker and mpv. setdefault so an externally set conf wins.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

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
                if kind == "align_refine":
                    _, vocal_path, lyrics_text, quiet = item
                    words = _do_align_refine(
                        model,
                        encoder_module,
                        vocal_path,
                        lyrics_text,
                        cancel_recv,
                        config,
                        worker_log,
                        quiet=quiet,
                    )
                    result_send.send(("ok", words))
                elif kind == "transcribe_words":
                    # 2-tuple legacy form: ("transcribe_words", path) → refine=True
                    # 3-tuple new form:   ("transcribe_words", path, refine)
                    _, vocal_path, *rest = item
                    refine = rest[0] if rest else True
                    words = _do_transcribe_words(
                        model,
                        encoder_module,
                        vocal_path,
                        cancel_recv,
                        config,
                        worker_log,
                        refine=refine,
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


def _do_align_refine(
    model,
    encoder_module,
    vocal_path: str,
    lyrics_text: str,
    cancel_recv: Connection,
    config: WhisperModelConfig,
    worker_log: logging.Logger,
    *,
    quiet: bool = False,
) -> list[dict]:
    """Run align() then refine(), post-process, and flatten to a word list.

    One entry per lyric token, in lyric order — the joint matcher's
    align-candidate source. ``quiet`` silences the per-pass progress bars.
    """
    with _quiet_progress(quiet):
        aligned = _align_pass(
            model, encoder_module, vocal_path, lyrics_text, cancel_recv, config, worker_log
        )
        refined = _refine_pass(
            model, encoder_module, vocal_path, aligned, cancel_recv, config, worker_log
        )
        _apply_post_process(refined, config.align_post_process)
    return _extract_words(refined, config.align_post_process.min_word_probability)


@contextlib.contextmanager
def _quiet_progress(active: bool):
    """Disable stable-ts's Align/Adjustment/Refine tqdm bars while ``active``.

    stable-ts gates its Align and Refine bars on ``verbose``, but the
    Adjustment bar is hardwired on (``disable=self.options.progress is not
    None``, which is always True), so no public flag silences all three.
    Force-disabling the tqdm class itself is the only reliable lever. Scoped to
    one align_refine job and restored in ``finally``; the worker runs jobs
    serially, so the class-level patch never races another bar.
    """
    if not active:
        yield
        return
    from tqdm import std as tqdm_std

    original_init = tqdm_std.tqdm.__init__

    def _disabled_init(self, *args, **kwargs):
        kwargs["disable"] = True
        original_init(self, *args, **kwargs)

    tqdm_std.tqdm.__init__ = _disabled_init
    try:
        yield
    finally:
        tqdm_std.tqdm.__init__ = original_init


def _do_transcribe_words(
    model,
    encoder_module,
    vocal_path: str,
    cancel_recv: Connection,
    config: WhisperModelConfig,
    worker_log: logging.Logger,
    *,
    refine: bool = True,
) -> list[dict]:
    """Run transcribe → regroup → (optionally) refine and return a flat word list.

    The joint matcher passes ``refine=False`` — it relies on align's
    refined per-word timings for align-won lines, so refining transcribe a
    second time is wasted whole-song decode for marginal benefit on a
    minority of lines. ``refine=True`` (the default) serves the
    transcription-only callers.
    """
    result = _transcribe_pass(model, encoder_module, vocal_path, cancel_recv, config, worker_log)
    if config.regroup:
        worker_log.info(f"Regrouping transcription segments: {config.regroup}")
        result.regroup(config.regroup)
    if refine:
        result = _refine_pass(
            model, encoder_module, vocal_path, result, cancel_recv, config, worker_log
        )
    else:
        worker_log.info("Skipping refine pass (refine=False)")
    _apply_post_process(result, config.transcribe_post_process)
    return _extract_words(result, config.transcribe_post_process.min_word_probability)


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


def _demote_alignment_warnings(worker_log: logging.Logger) -> None:
    """Route stable_whisper's per-pass alignment warnings to DEBUG.

    The aligner warns on every partially-aligned pass ("N/M segments failed to
    align", "Failed to align the last N/M words"), but the joint matcher
    recovers those lines and prints its own authoritative "Joint match: ..."
    summary, so the raw warnings are noise at INFO. Demote them to DEBUG — they
    reappear under ``-v`` when alignment quality is under investigation — and
    leave every other warning (deprecations, our own stream warning) untouched.
    """
    default_showwarning = warnings.showwarning

    def showwarning(message, category, filename, lineno, file=None, line=None):
        if category is UserWarning and "stable_whisper" in filename and "alignment" in filename:
            worker_log.debug("stable_whisper align: %s", message)
            return
        default_showwarning(message, category, filename, lineno, file, line)

    warnings.showwarning = showwarning
