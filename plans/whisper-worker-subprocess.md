Model: Claude Opus 4.7

# Move WhisperWorker out-of-process

## Goal

Run stable-ts / WhisperX in a dedicated subprocess, mirroring the
StemWorker architecture, so that an unrecoverable CUDA fault in whisper
(OOM, segfault, wedged stream) cannot hang or kill the karaoke server.
The current in-process design has been the dominant cause of "OOMs hang
the program" reports.

Prerequisite work already in place: stem worker exits on OOM
(`041e144`) and auto-restarts the next job (`8463af8`). This plan
extends the same pattern to whisper.

## Non-goals

- Adding a hard wall-clock timeout on inference (option (c) from the
  earlier audit). Tracked separately.
- Caching intermediate `WhisperResult` to disk for re-render. Possible
  follow-up; out of scope here.
- Moving ASS/SRT generation into the worker. Stays in `LyricAlignStage`
  — it is pure formatting, not inference.

## Current state

`WhisperWorker` runs in the main pipeline thread. Model is loaded once
at orchestrator `start()`. `LyricAlignStage` calls three methods on it:

- `align(vocal_path, lyrics_text, cancel_event) -> WhisperResult`
- `transcribe(vocal_path, cancel_event) -> WhisperResult`
- `refine(vocal_path, result, cancel_event) -> WhisperResult`

Cancellation: a `threading.Event` checked by a `register_forward_pre_hook`
on `model.encoder` ([whisper_worker.py:388-394](../pikaraoke/pipeline/workers/whisper_worker.py#L388-L394)).
On detection the hook raises `_CancelledInsideEncoder`, which unwinds
through stable-ts and is translated to `AlignmentCancelledError`, then
to `PipelineCancelled` by `_model_call` in [lyric_align.py:357-370](../pikaraoke/pipeline/stages/lyric_align.py#L357-L370).

`LyricAlignStage` reads `WhisperResult` fields directly between calls:
calls `result.regroup(...)`, walks `result.segments[i].words[j]` to
build `line_objects`, and passes the same `result` back into `refine()`.

## Target state

```
+-- main process ---------------------------+      +-- whisper subprocess --+
|                                           |      |                        |
|  LyricAlignStage                          |      |  _worker_main          |
|     |                                     |      |     |                  |
|     | line_objects (list[dict])           |      |     | model.align/     |
|     v                                     |      |     |   transcribe/    |
|  WhisperWorker (parent facade)            |      |     |   refine         |
|     |        |             |              |      |     | + regroup        |
|     | jobs   | results     | cancel       |      |     | + line_objects   |
|     v        ^             v              |      |     v                  |
|  +-- Pipe ---+  +-- Pipe --+   +-- Pipe -+|      |   stable_whisper       |
|  |   send    |  |  recv    |   |  send   ||      |                        |
|  +-----------+  +----------+   +---------+|      |                        |
|                                           |      |                        |
+-------------------------------------------+      +------------------------+
```

The whisper subprocess owns:
- the loaded stable-ts model,
- `stable_whisper` import,
- AudioLoader / FFmpeg children spawned during inference,
- the encoder pre-hook for cancellation,
- regroup,
- conversion of `WhisperResult` into the parent-friendly `line_object`
  list.

The parent owns:
- the `WhisperWorker` facade (subprocess lifecycle + IPC),
- forwarding `threading.Event` cancellation onto the cancel Pipe,
- ASS/SRT generation from `line_objects`,
- final-file promotion to `karaoke/` and `subtitles/`.

The parent never imports `stable_whisper`.

## Public API changes

### Parent-side WhisperWorker facade

```python
class WhisperWorker:
    def __init__(
        self,
        config: WhisperModelConfig | None = None,
        pty_slave_fd: int | None = None,
    ) -> None: ...

    # Lifecycle (parallels StemWorker)
    def start(self) -> None: ...      # spawn subprocess, wait for ready
    def stop(self) -> None: ...       # graceful sentinel + join, fallback kill
    def kill(self) -> None: ...
    def is_alive(self) -> bool: ...

    # Inference (coarser than today)
    def align_refine(
        self,
        vocal_path: Path,
        lyrics_text: str,
        cancel_event: threading.Event | None = None,
    ) -> list[dict]:
        """Run align then refine. Returns line_objects."""

    def transcribe_refine(
        self,
        vocal_path: Path,
        cancel_event: threading.Event | None = None,
    ) -> list[dict]:
        """Run transcribe (with optional regroup spec from config) then refine.
        Returns line_objects."""
```

`load_model()` and `unload_model()` are removed from the public surface;
the subprocess loads the model on startup and unloads on shutdown. The
orchestrator calls `start()` instead of `load_model()`.

### Exception class locations after the move

To prevent confusion during implementation:

- **`AlignmentCancelledError`** stays in `whisper_worker.py` (which
  becomes the parent-side façade module). Raised by the parent's
  `_run_job` on receipt of `("cancelled",)`. Imported by
  `lyric_align.py` exactly as today — no caller-side change.
- **`_CancelledInsideEncoder`** stays as a module-level class in
  `whisper_worker.py`, used only by the subprocess code path. Must
  remain at module scope (not nested in a function) so the encoder
  pre-hook closure can capture it from the enclosing module — same
  constraint already documented for `_CancelledInsideDemix` at
  [stem_worker.py:285-296](../pikaraoke/pipeline/workers/stem_worker.py#L285-L296).
- **`WorkerDiedError`** moves from `stem_worker.py` to `_ipc.py` (see
  the "Shared IPC module" section below). Both worker modules import
  it from there.

### line_object contract (worker -> parent)

Sole data type that crosses the IPC boundary as inference output. Plain
JSON-serializable types (lists, dicts, str, int, float). One element per
karaoke line:

```python
LineObject = TypedDict(
    "LineObject",
    {
        "text": str,
        "start": float,        # seconds
        "end": float,          # seconds
        "words": list[Word],
    },
)

Word = TypedDict(
    "Word",
    {
        "word": str,
        "start": float,
        "end": float,
        "is_segment_first": bool,
    },
)
```

This is exactly the shape `LyricAlignStage._generate_ass` and
`_generate_srt` consume today; codifying it as the IPC contract avoids
breaking either side.

## Subprocess design

### Entry point

`pikaraoke/pipeline/workers/whisper_worker.py` gets a module-level
function (mirroring `stem_worker._worker_main`):

```python
def _worker_main(
    job_recv: Connection,
    result_send: Connection,
    cancel_recv: Connection,
    config_dict: dict,           # WhisperModelConfig fields
    log_level: int,
    pty_slave_fd: int | None,
) -> None: ...
```

Why `config_dict` instead of the dataclass: `multiprocessing.Process`
pickles args; passing a plain dict avoids depending on whether
`WhisperModelConfig` stays trivially picklable. The subprocess
reconstructs the dataclass on entry.

### Subprocess startup sequence

1. PTY dup2 (if `pty_slave_fd is not None`).
2. Configure logger (mirror `stem_worker._setup_worker_logger`).
3. `import stable_whisper` and `import torch`.
4. Resolve OOM exception types tuple `(torch.cuda.OutOfMemoryError, MemoryError)`.
5. Patch `AudioLoader._audio_loading_process` for FFmpeg stderr suppression
   (existing logic from [whisper_worker.py:183-286](../pikaraoke/pipeline/workers/whisper_worker.py#L183-L286)) —
   moved as-is, runs once.
6. `stable_whisper.load_model(...)` per `config_dict`.
7. Cache `encoder_module = model.encoder`.
8. Send `("ready",)` on `result_send` so the parent's `start()` can
   block until the model is up. (StemWorker doesn't use a ready signal
   today — its first `separate()` call eats the load latency. We adopt a
   ready signal for whisper because the orchestrator's `start()` already
   blocks on `load_model()` today; preserving that property avoids a
   surprise where the first lyric_align call balloons in latency.)
9. Enter the job loop.

### Job loop

```python
while True:
    item = job_recv.recv()
    if item is None:
        break

    kind = item[0]
    cancel_recv_drain()  # safety net; mirror stem worker

    try:
        if kind == "align_refine":
            _, vocal_path, lyrics_text = item
            line_objects = _do_align_refine(
                model, encoder_module, vocal_path, lyrics_text, cancel_recv, config
            )
            result_send.send(("ok", line_objects))
        elif kind == "transcribe_refine":
            _, vocal_path = item
            line_objects = _do_transcribe_refine(
                model, encoder_module, vocal_path, cancel_recv, config
            )
            result_send.send(("ok", line_objects))
        else:
            result_send.send(("error", f"unknown job kind: {kind}"))
    except _CancelledInsideEncoder:
        worker_log.info("Cancelled mid-encoder; model still loaded")
        _terminate_orphaned_audioloaders()
        _clear_gpu_state()
        result_send.send(("cancelled",))
    except oom_exc_types as e:
        # Same posture as stem_worker after 041e144: report and exit.
        worker_log.error(f"OOM during {kind}: {e}")
        try:
            result_send.send(("error", f"OOM during whisper {kind}: {e}"))
        except (OSError, BrokenPipeError):
            pass
        return  # subprocess exits via finally
    except Exception as e:
        worker_log.exception(f"Whisper {kind} failed")
        result_send.send(("error", str(e)))
    finally:
        _drain_cancel_recv(cancel_recv)
```

Outer `finally` deletes the model and clears the GPU cache before exit,
parallel to the stem worker's outer `finally` at [stem_worker.py:372-375](../pikaraoke/pipeline/workers/stem_worker.py#L372-L375).

### Inference helpers

`_do_align_refine` and `_do_transcribe_refine` are subprocess-local
helpers. Both end with line-object extraction performed against the
**post-refine** WhisperResult (so refined word timestamps are the ones
that reach the ASS generator).

`_do_align_refine` (alignment mode):
1. Register the encoder forward pre-hook on `model.encoder`. Removed in
   a `finally` after `model.align()` returns or raises.
2. Run `model.align(vocal_path, lyrics_text, ...)`.
3. Re-register the pre-hook (fresh handle for the second call). Run
   `model.refine(vocal_path, aligned_result, ...)`. Remove handle.
4. Extract `line_objects = _match_words_to_lines(_extract_words(refined_result), lyric_lines)`.
5. Return `line_objects`.

`_do_transcribe_refine` (transcription mode):
1. Register pre-hook. Run `model.transcribe(vocal_path, ...)`. Remove handle.
2. **If `config.regroup` is set, call `result.regroup(config.regroup)`
   before refine.** Regroup mutates segment boundaries; running it
   before refine ensures (a) refine sees the post-regroup structure,
   and (b) `is_segment_first` flags computed in step 4 reflect the
   final segmentation that the ASS/SRT will use.
3. Re-register pre-hook. Run `model.refine(vocal_path, regrouped_result, ...)`.
   Remove handle.
4. Extract `line_objects = _segments_to_line_objects(refined_result)`.
   The `is_segment_first` field on each `Word` is set from the index
   within its post-regroup segment.
5. Return `line_objects`.

Both helpers port the conversion functions from
[lyric_align.py:181-250](../pikaraoke/pipeline/stages/lyric_align.py#L181-L250):
- `_extract_words(result) -> list[Word]`
- `_match_words_to_lines(words, lines) -> list[LineObject]` (alignment)
- `_segments_to_line_objects(result) -> list[LineObject]` (transcription)

Hook body:

```python
def cancel_pre_hook(module, inputs):
    if cancel_recv.poll(0):
        try:
            cancel_recv.recv()
        except (EOFError, OSError):
            pass
        raise _CancelledInsideEncoder()
    encode_counter[0] += 1
```

Identical structure to `stem_worker._separate_with_cancel_check`'s
pre-hook. The hook is registered in the subprocess against the
subprocess's `model.encoder`; the exception unwinds locally and is
caught by the job loop.

### Pipe message protocol

Job pipe (parent -> subprocess):
- `("align_refine", str_vocal_path, lyrics_text)`
- `("transcribe_refine", str_vocal_path)`
- `None` — graceful shutdown sentinel

Result pipe (subprocess -> parent):
- `("ready",)` — sent once after model load
- `("ok", list[LineObject])` — successful job
- `("cancelled",)` — encoder hook fired
- `("error", message: str)` — anything else (including OOM)

Cancel pipe (parent -> subprocess):
- single-byte non-zero send to signal cancel; receiver drains.

This matches the stem worker's protocol idioms (`("ok", ...)`,
`("cancelled",)`, `("error", ...)`) so debugging muscle memory transfers.

## Parent-side facade implementation

```python
class WhisperWorker:
    def start(self) -> None:
        self._close_all_connections()

        job_recv, job_send = Pipe(duplex=False)
        result_recv, result_send = Pipe(duplex=False)
        cancel_recv, cancel_send = Pipe(duplex=False)

        self._job_send = job_send
        self._result_recv = result_recv
        self._cancel_send = cancel_send
        # ... store inner ends too for cleanup

        self._process = Process(
            target=_worker_main,
            args=(job_recv, result_send, cancel_recv,
                  asdict(self._config), self._log_level, self._pty_fd),
            daemon=True,
        )
        self._process.start()

        # Block until ready or death. WHISPER_LOAD_TIMEOUT_SEC = 60 — on
        # the target hardware large-v3-turbo loads in ~10 s and the stem
        # separator in ~7 s, so 60 s gives ~6× headroom. If we hit it,
        # something is genuinely wrong (corrupted weights, wedged CUDA
        # init, swap thrashing) and failing loudly is correct.
        deadline = time.monotonic() + WHISPER_LOAD_TIMEOUT_SEC
        while True:
            if result_recv.poll(0.5):
                try:
                    msg = result_recv.recv()
                except EOFError:
                    # Subprocess died and closed its end of the pipe before
                    # sending ("ready",). Convert to WorkerDiedError so the
                    # orchestrator surfaces a clean failure.
                    raise WorkerDiedError(
                        f"Whisper worker pipe closed during model load "
                        f"(exit={self._process.exitcode})"
                    )
                if msg == ("ready",):
                    logger.info("Whisper worker ready")
                    return
                raise RuntimeError(f"Unexpected boot message: {msg}")
            if not self._process.is_alive():
                raise WorkerDiedError(
                    f"Whisper worker died during model load "
                    f"(exit={self._process.exitcode})"
                )
            if time.monotonic() > deadline:
                self.kill()
                raise TimeoutError("Whisper worker did not become ready in time")
```

`align_refine` and `transcribe_refine` share a private `_run_job(...)`
method that mirrors `StemWorker.separate()`:

1. Auto-restart if `proc is not None and not proc.is_alive()`
   (preserves the OOM-recovery property landed in `8463af8`). Calling
   `self.start()` here blocks for up to `WHISPER_LOAD_TIMEOUT_SEC`
   while the new subprocess loads the model.
2. **Fast-fail on cancel-during-restart**: immediately after `start()`
   returns, check `cancel_event.is_set()`. If True, raise
   `AlignmentCancelledError("cancelled during whisper worker restart")`
   without sending the job. Avoids round-tripping a freshly-loaded
   subprocess just to throw away the result. The cancel signal is not
   *lost* without this check (the `_forward_cancel` thread spawned in
   step 4 wakes immediately and the byte reaches the next encoder
   hook), but failing fast is cheaper.
3. Drain stale cancel signals via `_ipc.drain_pipe(self._cancel_recv)`.
4. Send the job tuple.
5. Spawn `_ipc.forward_cancel(cancel_event, cancel_send)` daemon thread
   if `cancel_event is not None`.
6. Loop: `rq.poll(0.5)` -> `recv` on data, else `proc.is_alive()` check.
7. On `("ok", line_objects)`: return.
8. On `("cancelled",)`: raise `AlignmentCancelledError(...)` (kept as the
   public exception name so `_model_call` keeps working unchanged).
9. On `("error", msg)`: raise `RuntimeError(f"Whisper worker error: {msg}")`.

`stop()` and `kill()` are byte-identical to StemWorker's; same with
`_close_all_connections`, `_drain_cancel_pipe`, `is_alive`.

## LyricAlignStage changes

The stage shrinks. After the move, `lyric_align.py:51-161` becomes:

```python
def run(self, ctx: StageContext) -> None:
    lyrics_path = ctx.artifacts.get("lyrics_path")
    vocal_wav = ctx.artifacts.get("vocal_wav")
    if vocal_wav is None:
        raise RuntimeError(...)

    if lyrics_path is not None:
        lyrics_text, lyrics_format = self._load_lyrics(lyrics_path)
        ctx.artifacts["lyrics_text"] = lyrics_text
        ctx.artifacts["lyrics_format"] = lyrics_format

        line_objects = _model_call(
            ctx, Phase.ALIGN,  # phase name choice discussed below
            lambda: self._worker.align_refine(
                vocal_path=vocal_wav,
                lyrics_text=lyrics_text,
                cancel_event=ctx.cancel.event if ctx.cancel else None,
            ),
        )
        write_srt = lyrics_format == "txt"
    else:
        line_objects = _model_call(
            ctx, Phase.TRANSCRIBE,
            lambda: self._worker.transcribe_refine(
                vocal_path=vocal_wav,
                cancel_event=ctx.cancel.event if ctx.cancel else None,
            ),
        )
        write_srt = True

    ass_content = self._generate_ass(line_objects)
    srt_content = self._generate_srt(line_objects) if write_srt else None
    # ... existing tmp-write + shutil.move logic unchanged ...
```

Methods deleted from the stage (now living in the worker subprocess):
- `_extract_words`
- `_match_words_to_lines`
- `_segments_to_line_objects`

Methods that stay (pure CPU formatting):
- `_load_lyrics`
- `_generate_ass`
- `_generate_srt`
- `_seconds_to_ass_time`

### Phase naming

Today the stage marks three phases (`Phase.ALIGN`, `Phase.TRANSCRIBE`,
`Phase.REFINE`) so the cancel UI can show a finer-grained label. After
the move, align+refine and transcribe+refine are atomic from the
parent's perspective.

**Decision**: collapse to two phases on the parent side. `Phase.ALIGN`
covers align+refine; `Phase.TRANSCRIBE` covers transcribe+refine.
Simpler IPC (no phase-update messages on the result pipe) and simpler
activity scoping in `_model_call`.

**Cancel during refine still works fully.** The encoder forward pre-hook
is the cancellation mechanism, not `Phase`. Inside the worker, the hook
is registered fresh for each of `model.align()`, `model.transcribe()`,
and `model.refine()` calls. A cancel signal arriving during refine is
caught by refine's hook on the next encoder pass — same as today. This
matters because refine is the *long* sub-phase (~1.5 min for a 5 min
song; align is 10-20 s), so cancellation responsiveness during refine
is the actual user requirement.

UI consequence: while a song is in `align_refine`, the processing page
will show `aligning lyrics` for the whole ~2 min duration, where it
previously showed `aligning lyrics` briefly then `refining lyrics`.
Acceptable per user direction ("UI not as important").

Cleanup tasks:
- Delete `Phase.REFINE` from [pipeline/context.py:33](../pikaraoke/pipeline/context.py#L33).
- Delete the `case 'refine':` branch from [processing.html:119](../pikaraoke/templates/processing.html#L119).
- Mark the orphaned `refining lyrics` msgid obsolete across all 15
  `.po` files by running `pybabel extract` followed by
  `pybabel update -i <messages.pot> -d <translations-dir>`. Do **not**
  hand-edit the `.po` files — `pybabel update` marks unused msgids as
  `#~` (obsolete) automatically and keeps the files consistent.
  Recompile via `pybabel compile -d <translations-dir>`.

## Orchestrator changes

`orchestrator.py:58-71`:

```python
def start(self) -> None:
    if self._workers_started:
        return
    logger.info("Starting stem worker...")
    self._stem_worker.start()
    logger.info("Starting whisper worker...")
    self._whisper_worker.start()           # was: load_model()
    self._workers_started = True

def stop(self) -> None:
    if not self._workers_started:
        return
    logger.info("Stopping stem worker...")
    try:
        self._stem_worker.stop()
    except Exception as e:
        logger.warning(...)
    logger.info("Stopping whisper worker...")
    try:
        self._whisper_worker.stop()        # was: unload_model()
    except Exception as e:
        logger.warning(...)
    self._workers_started = False
```

Module docstring lines 13-14 ("Both workers are started eagerly so GPU
OOM surfaces at startup rather than mid-queue on a subsequent song")
remain accurate — both are still started eagerly, just both as
subprocesses now.

## Cancellation flow (end to end)

1. User clicks cancel -> `cancel_token.cancel()` -> `threading.Event.set()`.
2. Inside `_run_job`, the daemon `_ipc.forward_cancel` thread sees
   `event.wait()` return, sends 1 byte on `cancel_send`.
3. Subprocess's encoder pre-hook polls `cancel_recv` before the next
   forward pass, sees data, drains, raises `_CancelledInsideEncoder`.
4. Exception unwinds through stable-ts. Job loop catches it, terminates
   orphaned AudioLoaders, clears GPU state, sends `("cancelled",)`.
5. Parent `_run_job` reads the message, raises `AlignmentCancelledError`.
6. `_model_call` translates to `PipelineCancelled(phase)`.
7. Orchestrator unwinds the pipeline thread, `tmp_dir` is rm'd in
   `_run_pipeline`'s `finally`.

Latency end-to-end: cancel-set -> hook-detect is dominated by the
duration of the in-flight encoder pass (no change from today). The
extra hops (event -> pipe -> hook poll) add sub-millisecond overhead.

### Why one-shot byte send is sufficient across align+refine

`forward_cancel` sends a single byte and exits — same as the stem
worker's pattern. For the two-phase whisper jobs this is still
correct because the cancel pipe is *persistent*: the byte sits there
until consumed, and the consumer is whichever encoder pre-hook fires
next. Three cases:

- **Cancel during align**: align's hook drains the byte and raises
  `_CancelledInsideEncoder`. `_do_align_refine` exits via the cancel
  branch — refine is never invoked. The drained byte is irrelevant
  because there is no subsequent phase to signal.
- **Cancel after align finished, during the inter-phase conversion
  gap (~ms)**: byte sits in the pipe untouched (no hook is
  registered). Refine starts, registers its fresh hook, fires on the
  first encoder pre-pass, drains the byte, raises.
- **Cancel during refine**: refine's hook drains the byte on the next
  pre-pass, raises.

The only scenario where a cancel could "miss" is if refine completes
zero encoder passes — i.e., the user cancels but refine returns
before any forward pass occurs. In that case the cancel signal is
indistinguishable from a cancel issued *after* the job already
finished, which is benign. Same boundary as the in-process design.

## OOM handling (mirror stem)

- Subprocess catches `(torch.cuda.OutOfMemoryError, MemoryError)`,
  reports `("error", "OOM during whisper ...")`, returns from
  `_worker_main`. Outer `finally` deletes model + clears cache.
- Parent's `_run_job` raises `RuntimeError`. Stage propagates. Pipeline
  records the song as failed.
- Next call to `align_refine` / `transcribe_refine` hits the
  auto-restart path (proc not alive -> `self.start()` -> fresh
  subprocess, fresh model load).

The model-reload latency on auto-restart is roughly 10 s on the target
hardware. Acceptable given the alternative is a wedged server.

### Diagnostics on each OOM-triggered restart

Before sending `("error", ...)`, the subprocess logs a one-line summary
of GPU memory state so a persistent OOM scenario is debuggable from
logs alone. The diagnostic is wrapped in its own try/except: after an
OOM the CUDA context can be in any state, and a failed `memory_*()`
query must not block the `("error", ...)` message from reaching the
parent.

```python
try:
    worker_log.error(
        "OOM during whisper %s for %s: %s | "
        "allocated=%.1fGB reserved=%.1fGB max=%.1fGB",
        kind, vocal_path, e,
        torch.cuda.memory_allocated() / 1e9,
        torch.cuda.memory_reserved() / 1e9,
        torch.cuda.max_memory_allocated() / 1e9,
    )
except Exception as diag_err:
    worker_log.error(
        "OOM during whisper %s for %s: %s "
        "(memory query failed: %s)", kind, vocal_path, e, diag_err
    )
```

No circuit-breaker. If a death-spiral pattern (every song OOMs and
restarts the worker) appears in real-world logs, a counter +
"refuse new whisper jobs after N consecutive failures" can be added
later. Current evidence does not justify designing for that case
ahead of time.

## AudioLoader / FFmpeg cleanup

Today: `_terminate_orphaned_audioloaders` uses `gc.get_objects()` to
find live `AudioLoader` instances in the main process and kills their
FFmpeg subprocesses. This stays — but now runs inside the subprocess.

Side benefit: when the subprocess dies (graceful shutdown, OOM exit,
SIGKILL), POSIX delivers `SIGHUP`/`SIGPIPE` to its FFmpeg children,
so they exit too. The gc walk becomes a "tidy promptly" optimization
on the cancellation path; it is no longer the only line of defense
against orphan FFmpeg.

The `AudioLoader._audio_loading_process` monkeypatch ([whisper_worker.py:200-286](../pikaraoke/pipeline/workers/whisper_worker.py#L200-L286))
must be applied in the subprocess after `stable_whisper` import but
before the first inference call. Move it as-is into `_worker_main`.

## PTY routing

Same shape as stem worker. Parent passes `pty_slave_fd` via `Process`
args. Subprocess does `os.dup2` over fds 1 and 2 at the very top of
`_worker_main` — permanent redirection for the life of the subprocess.

**The `_route_to_pty` context manager is dropped from the subprocess
code path.** In the in-process design it scoped *which* output got
redirected to the PTY (only inference-time chatter; other Python
output stayed on the main stdout). In the subprocess, every line of
output is whisper-related, so the entry-level `dup2` covers it
completely and the context manager would be a no-op (saving the
already-redirected fd, dup2'ing it to itself, restoring).

`_do_align_refine` and `_do_transcribe_refine` therefore call
`self._model.align(...)`, `self._model.transcribe(...)`, and
`self._model.refine(...)` directly — no `with _route_to_pty(...)`
wrapper. The `_route_to_pty` helper itself can be deleted from the
post-move codebase along with the in-process inference methods.

## Shared IPC module (`_ipc.py`)

The whisper move forces several primitives to be shared with the stem
worker. Rather than copy-paste, introduce
`pikaraoke/pipeline/workers/_ipc.py` as a required deliverable of this
work. Contents:

```python
# pikaraoke/pipeline/workers/_ipc.py

import multiprocessing as mp
import threading
from multiprocessing.connection import Connection


# Always use 'spawn' for worker subprocesses. fork-after-CUDA is
# unsafe: any prior torch.cuda.* call in the parent (intentional or
# not) leaves the child with a duplicated, broken CUDA context.
# Using a dedicated context here ensures both workers are immune
# regardless of what the parent process does.
WORKER_CONTEXT = mp.get_context("spawn")


class WorkerDiedError(Exception):
    """Raised when a worker subprocess dies during a job or boot."""


def forward_cancel(event: threading.Event, cancel_send: Connection) -> None:
    """Daemon-thread target: wait for event, send one byte to the cancel pipe."""
    event.wait()
    try:
        cancel_send.send(1)
    except (OSError, BrokenPipeError):
        pass


def drain_pipe(conn: Connection) -> None:
    """Non-blocking: read and discard any pending messages."""
    while conn.poll(0):
        try:
            conn.recv()
        except (EOFError, OSError):
            break
```

Both `stem_worker.py` and `whisper_worker.py` import from this module.
The existing `WorkerDiedError` and `_forward_cancel` in
`stem_worker.py` are replaced by re-exports / imports from `_ipc.py`
in the same PR that introduces the new module.

`SubprocessWorkerBase` is **not** introduced. The two workers have
meaningfully different boot sequences (stem registers per-call hooks,
whisper uses a ready signal and patches AudioLoader). A shared base
class would devolve into stem-vs-whisper branches; better to keep two
focused worker files that import the same primitive helpers.

### Subprocess start method

All `Process(...)` constructions in `stem_worker.py` and
`whisper_worker.py` use `WORKER_CONTEXT.Process(...)` (i.e.,
`multiprocessing.get_context("spawn").Process(...)`), not
bare `multiprocessing.Process`.

This is a **retroactive change for StemWorker** that ships in the
same PR as `_ipc.py`. StemWorker today happens to work under `fork`
because the parent never imports torch at module level — but the
moment a future change adds a `torch.*` reference to the parent (e.g.,
a stray `torch.cuda.is_available()` somewhere in pipeline setup),
fork-after-CUDA breaks silently. Forcing spawn now eliminates the
trap.

Spawn cost: each worker subprocess pays a fresh interpreter startup
(~100-300 ms), which is dwarfed by model load time (7-10 s). Negligible.

After this lands, also remove the module-level `import torch` from
[whisper_worker.py:44](../pikaraoke/pipeline/workers/whisper_worker.py#L44)
— after the move, the parent-side façade has no need for it.

## Test changes

### Tests to update

- `tests/unit/test_processing_manager.py:81` mocks
  `pikaraoke.lib.processing_manager.StemWorker`. Same file likely
  mocks `WhisperWorker` indirectly via processing_manager — audit and
  update mock return shapes to `list[LineObject]` instead of objects
  with `.segments[i].words[j]`.
- Any lyric_align tests that exercise `_extract_words`,
  `_segments_to_line_objects`, `_match_words_to_lines` need to either
  move to a worker-side test module or be reframed against the
  subprocess boundary (mock the worker, assert on the
  parent-side ASS/SRT generation).

### New tests

- `tests/unit/test_whisper_worker.py`:
  - `start()` blocks until `("ready",)` is received.
  - `start()` raises `WorkerDiedError` if subprocess dies during load.
  - `start()` raises `TimeoutError` after `WHISPER_LOAD_TIMEOUT_SEC`.
  - `align_refine` returns line_objects on `("ok", ...)`.
  - `align_refine` raises `AlignmentCancelledError` on `("cancelled",)`.
  - `align_refine` raises `RuntimeError` on `("error", ...)`.
  - Auto-restart path: pre-poison `_process` to a dead `Process`,
    call `align_refine`, assert `start()` was invoked.
  - Cancel forwarder: set the event, assert a byte appears on
    `cancel_send`.

  All using a fake `_worker_main` and stub Pipes — no real
  stable_whisper. Mirrors how `tests/unit/test_processing_manager.py`
  mocks `StemWorker`.

- A higher-fidelity smoke test (gated, opt-in) that actually spawns
  the real worker against a tiny clip in CI. Mark with a custom
  pytest marker so it is skipped by default.

## Migration order

0. **Establish a test baseline** — before any refactor, add
   characterization tests for the conversion helpers that will move
   subprocess-side: `_extract_words`, `_match_words_to_lines`, and
   `_segments_to_line_objects`. Use fixed `WhisperResult`-shaped
   fixtures (mocks or pickled real outputs from a known clip) so the
   tests assert on `LineObject` lists, not on stable-ts internals.
   These same assertions become the worker-side correctness tests
   after the move — same inputs, same outputs, different boundary.
1. **Introduce `_ipc.py`** with `WORKER_CONTEXT`, `WorkerDiedError`,
   `forward_cancel`, `drain_pipe`. Switch StemWorker to import
   `WorkerDiedError` and `_forward_cancel` from `_ipc.py`, and to
   construct its `Process` via `WORKER_CONTEXT.Process(...)`. Verify
   stem path still works (existing tests pass, manual song
   processing). Independent PR — no whisper changes.
2. **Add new APIs alongside old** — keep `align/refine/transcribe` on
   the in-process worker, add `align_refine` / `transcribe_refine`
   that internally still run in-process. Update `LyricAlignStage`
   to call the new methods. Move conversion helpers into the worker
   module as private module-level functions. Land + verify, no
   behavior change.
3. **Add subprocess plumbing alongside in-process** — guarded by a
   feature flag (env var or config). Both code paths exist briefly so
   regressions can be A/B compared. Wire spawn via
   `WORKER_CONTEXT.Process(...)`. Remove the module-level
   `import torch` from `whisper_worker.py` parent-side.
4. **Switch the default to subprocess**. Run the full song-processing
   smoke test, the cancel-mid-align test, the cancel-mid-refine test,
   and a deliberate OOM (force a too-large `whisper_model` on a small
   GPU) to confirm OOM no longer hangs the server.
5. **Delete the in-process path** and the feature flag. Remove
   `load_model` / `unload_model` from the public API. Remove
   `_route_to_pty` helper.

Each step is an independent PR with its own test plan.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `WhisperResult` regroup behavior changes between stable-ts versions and the worker-side regroup spec stops working | Pin stable-ts version, add a smoke test that verifies regroup on a known clip yields the expected segment count |
| Pickle of `LineObject` lists is slow for very long songs (10k+ words) | Measure first; if real, switch the result pipe to a length-prefixed JSON write to a `multiprocessing.shared_memory` block. Almost certainly unnecessary |
| `_terminate_orphaned_audioloaders` relies on `gc.get_objects()` — cheaper in subprocess but not free | Already runs only on cancel, so cost is bounded |
| Model-load latency on auto-restart adds 5-30 s before the next song processes | Acceptable; same posture as stem. Surface in logs so the user knows what happened |
| `Phase.REFINE` removal might break UI code that displays the current phase | Search for `Phase.REFINE` references; adjust UI labels to fold refine under align/transcribe |
| Multiprocessing start method (fork vs spawn) interacts with CUDA initialization | Resolved by `_ipc.WORKER_CONTEXT = mp.get_context("spawn")`. Both workers use this context; StemWorker switches over in step 1 |
| `_route_to_pty` redundancy in subprocess after entry-level dup2 | Resolved: `_route_to_pty` is removed from subprocess code paths. Entry-level dup2 alone covers PTY routing |

## Resolved decisions

1. **Phase collapse**: `Phase.ALIGN` covers align+refine,
   `Phase.TRANSCRIBE` covers transcribe+refine. `Phase.REFINE` is
   removed. Cancel during refine still works because the encoder
   forward pre-hook is the cancellation mechanism, not the phase
   label — verified against [whisper_worker.py:462-470](../pikaraoke/pipeline/workers/whisper_worker.py#L462-L470).
2. **Model-load timeout**: 60 s. Target hardware loads large-v3-turbo
   in ~10 s, so ~6× headroom. Not configurable.
3. **OOM recovery**: auto-restart, matching stem worker. Each restart
   logs a GPU memory summary line. No circuit-breaker.

## Estimated effort

- Step 0 (characterization tests for conversion helpers): 2-3 hours
- Step 1 (`_ipc.py` + StemWorker spawn switch): 1-2 hours
- Step 2 (API rename + move conversion helpers into worker module): 2 hours
- Step 3 (subprocess plumbing behind flag): 4-6 hours
- Step 4 (smoke testing, OOM verification, cancel-mid-refine verification): 2-3 hours
- Step 5 (delete in-process path, remove `_route_to_pty`): 1 hour
- New subprocess tests (`test_whisper_worker.py`): 2-3 hours

Total: roughly 1-1.5 focused days of implementation, plus a half-day
of testing against real OOM scenarios on the target GPU.
