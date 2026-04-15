# ProcessingManager Refactor: Orchestrator + StemWorker Architecture

Model: Claude Opus 4.6

## Context

The current `ProcessingManager` runs the entire pipeline — FFmpeg extract, stem
separation, FFmpeg transcode — inside a single `multiprocessing.Process` worker.
Cancellation works by hard-terminating that process (SIGTERM → SIGKILL), which:

1. **Unnecessarily kills FFmpeg work.** A cancel during the extract or transcode
   step tears down the loaded 400MB model even though the model isn't doing any
   work, forcing a ~5s reload.
2. **Terminates unreliably.** The worker can be inside a blocking C/CUDA call
   that doesn't respond to SIGTERM quickly; the fallback SIGKILL + queue
   feeder-thread state can leave the shared `Queue`/`SimpleQueue` in an
   undefined state across restarts (queues are created once at init and reused).
3. **Doesn't scale.** Adding a future `LyricWorker` would require either a
   second monolithic worker or bolting more responsibility into the existing
   one.

This refactor splits the single worker into two pieces:

- **`StemWorker`** — a persistent subprocess whose sole job is loading the
  model and running `separator.separate()` on WAV inputs. It can be SIGKILL'd
  independently and restarted cheaply (queues are recreated per spawn).
- **Orchestrator thread** — inside `ProcessingManager`, runs the 3-step
  pipeline sequentially: calls FFmpeg directly via `subprocess.Popen`, submits
  WAVs to the `StemWorker`, and tracks which step each job is currently in.

Cancel becomes **surgical**: it looks at the current pipeline step and kills
only the relevant thing (the FFmpeg `Popen` handle, or the `StemWorker`
subprocess). The model stays loaded unless cancel lands during actual stemming.

Pipeline tracking (`pipeline_tracker.py`) is out of scope and will be revisited
after this refactor lands.

______________________________________________________________________

## Scope

**In scope:**

- New file: `pikaraoke/lib/stem_worker.py` — `StemWorker` class encapsulating
  the subprocess lifecycle.
- Rewrite: `pikaraoke/lib/processing_manager.py` — orchestrator thread with
  per-job state tracking and surgical cancellation.
- Preserved public API: no changes to call sites in `karaoke.py`, routes, or
  `pipeline_tracker.py`.

**Out of scope:**

- `pipeline_tracker.py` changes (deferred).
- `download_manager.py` changes.
- Any UI or route changes.
- Future `LyricWorker` (design fits the pattern, but not implemented).

______________________________________________________________________

## Architecture

### New: `StemWorker` (`pikaraoke/lib/stem_worker.py`)

A thin subprocess wrapper. Owns the stem model lifecycle and nothing else.

**Responsibilities:**

- Spawn a `multiprocessing.Process` that loads `audio_separator.Separator` and
  loops on an input `Queue`, returning results via `multiprocessing.Pipe`.
- Fresh IPC channels per spawn (critical — solves the queue-orphan bug and
  gevent monkey-patching interference).
- Redirect worker stdout/stderr to the PTY slave fd on spawn (same as today).
- Provide a synchronous `separate(wav_path) → (vocal_wav, instrumental_wav)`
  that blocks until the worker returns a result, with liveness polling so a
  killed worker unblocks the caller.
- Provide `kill()` (SIGKILL + discard IPC channels) and `stop()` (sentinel +
  graceful join).

**Public API:**

```python
class StemWorker:
    def __init__(self, pty_slave_fd: int | None, temp_dir: str) -> None: ...
    def start(self) -> None:
        """Spawn the subprocess with fresh queues. Blocks until the model is loaded."""

    def is_alive(self) -> bool: ...
    def separate(self, wav_path: Path, output_dir: Path) -> tuple[Path, Path]:
        """Submit a WAV, block for result. Raises WorkerDiedError if killed mid-job."""

    def kill(self) -> None:
        """SIGKILL the subprocess and discard queues. Does not restart."""

    def stop(self) -> None:
        """Graceful shutdown: send sentinel, join, fall back to kill on timeout."""
```

**Worker protocol (IPC message shapes):**

- Input queue (`Queue`): job payload `(wav_path: str, output_dir: str)` tuple, or
  `None` sentinel for graceful shutdown.
- Result pipe (`multiprocessing.Pipe`, `Connection.send()`): `("ok", vocal_wav: str, instrumental_wav: str)` or `("error", error_message: str)`. Pipe is used instead
  of Queue to avoid interference from gevent monkey-patching in the parent process
  (see "IPC Implementation Detail" section below).
- Serializing the exception class itself is brittle across processes; a string
  message is enough for the orchestrator to wrap in a local `RuntimeError`.

**`separate()` liveness-polling pattern:**

```python
def separate(self, wav_path: Path, output_dir: Path) -> tuple[Path, Path]:
    rq = self._result_recv  # Connection from Pipe(duplex=False)
    jq = self._job_queue
    proc = self._process
    if rq is None or jq is None or proc is None:
        raise WorkerDiedError("Stem worker is not running")

    jq.put((str(wav_path), str(output_dir)))
    while True:
        if rq.poll(0.5):  # Connection.poll(timeout)
            msg = rq.recv()  # Connection.recv()
            break
        if not proc.is_alive():
            raise WorkerDiedError("Stem worker died during separation")

    tag = msg[0]
    if tag == "ok":
        return Path(msg[1]), Path(msg[2])
    raise RuntimeError(f"Stem worker error: {msg[1]}")
```

Local references (`rq`, `jq`, `proc`) mean a concurrent `kill()` clearing the
instance attributes doesn't race into an `AttributeError`. `Connection.poll(timeout)`
and `Connection.recv()` are used instead of `Queue.get()` to avoid gevent
monkey-patching issues (see section below).

**Worker main function** is essentially the current `_run_worker_process`
trimmed to just model load + separation loop (no FFmpeg, no pipeline). It
moves into `stem_worker.py`.

______________________________________________________________________

### Rewritten: `ProcessingManager` (orchestrator)

`ProcessingManager` becomes a gevent-facing facade + a real-thread
orchestrator loop. The drain-thread pattern stays (still needed because any
blocking on `multiprocessing.Process` state from a gevent greenlet can
deadlock) but is renamed/repurposed into the orchestrator loop.

**New instance state:**

```python
class _Step(Enum):
    EXTRACTING = "extracting"
    STEMMING = "stemming"
    TRANSCODING = "transcoding"


@dataclass
class _JobState:
    song_path: str
    step: _Step
    ffmpeg_process: subprocess.Popen | None = None
    cancelled: bool = False
```

```python
self._stem_worker: StemWorker
self._pending_queue: queue.Queue[
    str | None
]  # internal, consumed by orchestrator thread
self.pending_jobs: list[str]  # public, derived from pending_queue + active
self._active_state: _JobState | None  # current in-flight job, None if idle
self._state_lock: threading.Lock  # guards pending_jobs + _active_state
self._cancelled_paths: set[str]  # pending cancels resolved before pickup
self._orchestrator_thread: threading.Thread
self._stop_event: threading.Event
```

**Preserved public API** (signatures unchanged — no call-site changes needed
in `karaoke.py`, routes, or `pipeline_tracker.py`):

- `start()` — starts PTY, `StemWorker`, orchestrator thread, subscribes to
  `song_downloaded`.
- `stop()` — stops orchestrator thread, `StemWorker`, PTY.
- `enqueue(song_path)` — applies blocked-words filter (reuse existing logic),
  appends to `pending_jobs`, puts on `_pending_queue`.
- `cancel_pending(song_path)` — remove from `pending_jobs`, add to
  `_cancelled_paths`.
- `cancel_active(song_path)` — surgical cancel (see below).
- `get_active_job()` — returns `self._active_state.song_path` or `None`.
- `pending_jobs: list[str]` — kept as public attribute for backwards compat.

**Orchestrator thread loop:**

```python
def _orchestrator_loop(self) -> None:
    while not self._stop_event.is_set():
        try:
            song_path = self._pending_queue.get(timeout=0.5)
        except Empty:
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
        except _CancelledError:
            self._cleanup_stems(song_path)
            self._events.emit("processing_cancelled", song_path)
            logging.info(f"Processing cancelled: {Path(song_path).name}")
        except Exception as e:
            logging.error(f"Processing failed for {Path(song_path).name}: {e}")
            self._events.emit(
                "processing_error", {"song_path": song_path, "error": str(e)}
            )
            self._cleanup_stems(song_path)
        finally:
            with self._state_lock:
                if song_path in self.pending_jobs:
                    self.pending_jobs.remove(song_path)
                self._active_state = None
            # Eager restart: if cancel or crash killed the worker, bring it
            # back before the next job arrives so separate() doesn't need
            # restart logic.
            if not self._stem_worker.is_alive():
                try:
                    self._stem_worker.start()
                except Exception as e:
                    logging.error(f"Failed to restart stem worker: {e}")
```

**Pipeline execution (`_run_pipeline`):**

```python
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
        wav_in = self._ffmpeg_extract(video, tmp_dir)
        self._check_cancelled()

        # Step 2: Stem separation (in StemWorker subprocess)
        self._set_step(_Step.STEMMING)
        if not self._stem_worker.is_alive():
            self._stem_worker.start()
        try:
            vocal_wav, instrumental_wav = self._stem_worker.separate(wav_in, tmp_dir)
        except WorkerDiedError:
            # Distinguish cancel (state.cancelled) from unexpected death.
            self._check_cancelled()
            raise RuntimeError("Stem worker died unexpectedly during separation")
        self._check_cancelled()

        # Step 3: FFmpeg transcode x2 (in orchestrator thread)
        self._set_step(_Step.TRANSCODING)
        vocal_out.parent.mkdir(exist_ok=True)
        nonvocal_out.parent.mkdir(exist_ok=True)
        self._ffmpeg_transcode(vocal_wav, vocal_out)
        self._check_cancelled()
        self._ffmpeg_transcode(instrumental_wav, nonvocal_out)
        self._check_cancelled()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _set_step(self, step: _Step) -> None:
    with self._state_lock:
        if self._active_state is not None:
            self._active_state.step = step
            self._active_state.ffmpeg_process = None


def _check_cancelled(self) -> None:
    with self._state_lock:
        if self._active_state is not None and self._active_state.cancelled:
            raise _CancelledError()
```

**FFmpeg wrappers** — same commands as today (`_extract_audio`, `_wav_to_m4a`
semantics) but use `subprocess.Popen` and register the handle in
`_active_state.ffmpeg_process` so cancel can kill it. Pass `stdout` and
`stderr` to the PTY slave fd so output still appears in the secondary
terminal. Close the PTY end in the parent? No — we keep it open because the
next FFmpeg call (and the StemWorker) will also use it. It's closed in
`ProcessingManager.stop()` via `ProcessTerminal.stop()`.

```python
def _ffmpeg_extract(self, video: Path, tmp_dir: Path) -> Path:
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
    stdout_fd = (
        self._pty_slave_fd if self._pty_slave_fd is not None else subprocess.DEVNULL
    )
    stderr_fd = (
        self._pty_slave_fd if self._pty_slave_fd is not None else subprocess.DEVNULL
    )
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
        # If cancel killed it, _check_cancelled() downstream will raise the right error.
        with self._state_lock:
            cancelled = self._active_state is not None and self._active_state.cancelled
        if cancelled:
            raise _CancelledError()
        raise RuntimeError(f"ffmpeg {label} failed (exit code {rc})")
```

**Cancellation (surgical):**

```python
def cancel_active(self, song_path: str) -> None:
    """Cancel the currently active processing job, targeting the active step.

    Safe to call from gevent context: only sends signals and sets flags,
    never joins a subprocess. The orchestrator thread observes the
    cancelled flag on its next _check_cancelled() and raises _CancelledError.
    """
    with self._state_lock:
        state = self._active_state
        if state is None or state.song_path != song_path:
            logging.warning(
                f"Cancel requested for non-active job: {Path(song_path).name}"
            )
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
    # During STEMMING: do NOT kill the worker. Let the current
    # separation finish naturally; _check_cancelled() will raise
    # _CancelledError when separate() returns and the model stays loaded.
```

`cancel_active` no longer does `join()` or waits for cancel completion. It
just sets flags and sends signals. Any blocking happens inside the
orchestrator thread, which is a real `threading.Thread`. This removes the
`_cancel_request`/`_cancel_done` indirection entirely — simpler and more
robust.

**Cancel during STEMMING:** delayed cancel preserves the loaded model —
the worker keeps running, the current `separate()` call completes naturally,
and `_check_cancelled()` raises `_CancelledError` immediately after. The
caller (UI) is responsible for showing feedback (e.g., an amber "cancelling"
pulse) until the `processing_cancelled` event fires.

**`cancel_pending`** keeps its current shape: remove from `pending_jobs`,
add to `_cancelled_paths`. The orchestrator loop checks this set when it
pulls an item off the internal queue. No file cleanup needed (nothing has
started).

______________________________________________________________________

## IPC Implementation Detail: Pipe vs Queue (gevent monkey-patching issue)

**The problem:**

PiKaraoke uses gevent for its web framework. `app.py` calls `monkey.patch_all()`
at startup, which patches the Python `threading` module to use gevent greenlets
instead of OS threads. This has a critical side effect on `multiprocessing.Queue`:

1. `multiprocessing.Queue` uses a background thread (the "feeder thread") to
   serialize data and write it to the underlying OS pipe. With monkey-patching,
   this feeder thread becomes a gevent greenlet.
2. When the worker subprocess is forked (via `multiprocessing.Process`), it
   inherits the monkey-patched environment. The worker's queues ALSO have
   gevent greenlet feeder threads.
3. In the worker subprocess, the `_stem_worker_main` function runs
   `separator.separate()`, which is CPU-intensive and does not yield to gevent.
   The gevent event loop never runs.
4. When the worker calls `queue.put(result)`, the data goes into an internal
   buffer, but the feeder greenlet never gets scheduled (no event loop). The
   result never gets flushed from the buffer to the underlying OS pipe.
5. When the orchestrator thread tries to receive the result and subsequently
   kill the worker mid-job (e.g., for cancel), the greenlet feeder thread
   fails to unregister itself from `threading._active`, causing a `KeyError`.

**The solution:**

Use `multiprocessing.Pipe(duplex=False)` for both job and result channels instead
of `Queue`. `Connection.send()` and `Connection.recv()` operate directly on the OS
pipe without any background thread or buffering. Data goes immediately between
worker and orchestrator, unaffected by gevent monkey-patching.

- **Job channel** (orchestrator → worker): `Pipe(duplex=False)`, orchestrator
  sends job tuples via `job_send.send()`, worker receives via `job_recv.recv()`.
- **Result channel** (worker → orchestrator): `Pipe(duplex=False)`, worker sends
  results via `result_send.send()`, orchestrator receives via polling + `result_recv.recv()`.

**Code changes:**

- `StemWorker.__init__`: add `_job_send`, `_job_recv`, `_result_send`, `_result_recv`
  attributes for the two `Pipe()` connections.
- `StemWorker.start()`: create both pipes fresh on every spawn. This ensures
  each worker restart gets clean IPC channels (critical for avoiding queue state
  orphaning).
- `StemWorker.separate()`: use `js.send((wav_path, output_dir))` for the job
  and `rq.poll(0.5)` + `rq.recv()` for the result (no feeder thread).
- `_stem_worker_main`: parameters are `job_recv: Connection` and
  `result_send: Connection`. Job loop is `item = job_recv.recv()`, result is
  `result_send.send(msg)`.
- `StemWorker.kill()` and `stop()`: close all four connections after process
  termination to avoid orphaned pipe endpoints.
- Stem identification bug fix: in `_separate_in_worker()`, check for both
  `"no vocal"` (with space) and `"no_vocal"` (with underscore) to avoid
  misclassifying `(No Vocals)` output files as vocals.

______________________________________________________________________

## Preserved: PTY / ProcessTerminal integration

The PTY slave fd is still owned by `ProcessingManager` (same as today):

- `ProcessingManager.start()` creates `ProcessTerminal` and stores
  `self._pty_slave_fd`.
- `StemWorker.__init__` receives the fd. On `start()`, it passes it to the
  subprocess which dup2's it onto stdout/stderr (same code as
  `_run_worker_process` today, just relocated).
- FFmpeg subprocesses spawned from the orchestrator thread also pass the
  slave fd as `stdout`/`stderr` to `Popen`. This is new — today FFmpeg
  inherits from the worker's already-dup2'd stdout. In the new design FFmpeg
  runs in the main process, so we have to pass the fd explicitly.
- PTY slave fd survives `StemWorker.kill()` and restart. The fd lives in the
  main process; only the worker subprocess (which had its own inherited
  copy) goes away.

______________________________________________________________________

## Files to Create

### `pikaraoke/lib/stem_worker.py`

Contents:

- `WorkerDiedError` exception
- `StemWorker` class (public API above)
- `_stem_worker_main()` — process entry point, adapted from the current
  `_run_worker_process()` in `processing_manager.py` lines 313-366 minus the
  FFmpeg steps. Reuses `_setup_processing_logger` logic (move or duplicate —
  probably move into `stem_worker.py` since it's the only caller now).
- Constants `MODEL_NAME`, `MODEL_DIR`, `SEPARATION_FORMAT` move here since
  this file owns the model.

## Files to Modify

### `pikaraoke/lib/processing_manager.py`

Rewritten around the orchestrator thread design above. Keeps:

- Module-level constants for FFmpeg (`FFMPEG_THREADS`, `AAC_QUALITY`)
- `_cleanup_stems()` helper (unchanged)
- Blocked-words filter in `enqueue()` (unchanged)
- Public API surface (`start`, `stop`, `enqueue`, `cancel_pending`,
  `cancel_active`, `get_active_job`, `pending_jobs`)

Removes:

- `_run_worker_process`, `_process_song_in_worker`, `_separate_stems`,
  `_extract_audio`, `_wav_to_m4a` (extract/transcode become `_ffmpeg_extract`
  and `_ffmpeg_transcode` instance methods; `_separate_stems` moves into
  `stem_worker.py`; `_run_worker_process` split between `stem_worker.py` and
  the orchestrator)
- `_drain_loop`, `_drain_results`, `_drain_stop`, `_execute_cancel`,
  `_cancel_request`, `_cancel_done`, `_restart_worker`, `_make_worker_process`
  (replaced by orchestrator thread and `StemWorker` lifecycle)
- `_processing_active` field (replaced by `_active_state`)
- Direct `_queue`/`_result_queue`/`_worker_process` fields (moved into
  `StemWorker`)

### `pikaraoke/karaoke.py`

**No changes required.** `ProcessingManager(events, preferences, temp_dir)`
constructor signature and `.start()` / `.stop()` are preserved. Verify during
implementation.

### Routes, `pipeline_tracker.py`, tests

**No changes required** — public API is preserved. Existing callers of
`cancel_active`, `cancel_pending`, `get_active_job`, and `pending_jobs`
continue to work. Existing tests should keep passing (any that mock the
worker process will need to be updated to mock `StemWorker` instead; audit
during implementation).

______________________________________________________________________

## Concurrency & Safety Notes

1. **All `multiprocessing.Process.join()` and `.kill()` calls happen in real
   threads** — either the orchestrator thread or (for `StemWorker.stop()`)
   the main thread at shutdown. Never called from gevent greenlets.
   `cancel_active` is gevent-safe because it only sets flags and calls
   `.kill()` (signal send, non-blocking) — it never joins.

2. **Queue orphan bug fixed.** `StemWorker` creates fresh `Queue` (for jobs)
   and `Pipe` (for results) on every `start()`. After `kill()`, the old IPC
   channels are closed and dropped. A restarted worker gets a clean pair.
   Combined with the Pipe-based result channel, this avoids both queue state
   corruption and gevent monkey-patching interference.

3. **Concurrent `kill()` vs `separate()`.** `StemWorker.separate()` captures
   local references to the queues and process at entry, so a concurrent
   `kill()` that nulls instance attributes doesn't cause `AttributeError`.
   The polling loop detects the dead process via `proc.is_alive()` and
   raises `WorkerDiedError`.

4. **`_state_lock` discipline.** Held only for short reads/writes of
   `_active_state` and `pending_jobs`. Never held across subprocess calls,
   FFmpeg waits, or queue operations. This prevents cancel from stalling on
   the orchestrator.

5. **Cancel during transcode leaves partial output file.** `_cleanup_stems`
   already globs `{stem_base}---*` in both `vocal/` and `nonvocal/` dirs, so
   it catches this. No change needed.

6. **Worker death without cancel.** If the StemWorker dies (OOM, library
   bug), `separate()` raises `WorkerDiedError`. The orchestrator calls
   `_check_cancelled()` which finds no cancel flag, so it re-raises as a
   `RuntimeError`. That gets caught by the orchestrator loop's generic
   `except Exception`, emits `processing_error`, and the finally block
   eagerly restarts the worker for the next job.

7. **Shutdown ordering in `stop()`:**

   1. `self._stop_event.set()`
   2. `self._pending_queue.put(None)` (wake orchestrator thread)
   3. `self._orchestrator_thread.join(timeout=10)`
   4. `self._stem_worker.stop()` (graceful sentinel, then kill on timeout)
   5. `self._process_terminal.stop()` (closes PTY)

______________________________________________________________________

## Critical Files

- [pikaraoke/lib/processing_manager.py](pikaraoke/lib/processing_manager.py) — to rewrite
- [pikaraoke/lib/stem_worker.py](pikaraoke/lib/stem_worker.py) — new file
- [pikaraoke/lib/process_terminal.py](pikaraoke/lib/process_terminal.py) — read-only reference (PTY fd ownership unchanged)
- [pikaraoke/karaoke.py](pikaraoke/karaoke.py) — verify no changes needed at line ~264
- [pikaraoke/lib/pipeline_tracker.py](pikaraoke/lib/pipeline_tracker.py) — read-only reference; verify no signatures change

Reused helpers:

- `get_temp_directory()` from [pikaraoke/lib/get_platform.py](pikaraoke/lib/get_platform.py)
- `ProcessTerminal` from [pikaraoke/lib/process_terminal.py](pikaraoke/lib/process_terminal.py)
- `_cleanup_stems()` logic (moves with `ProcessingManager`)
- Blocked-words filter logic in `enqueue()` (moves with `ProcessingManager`)

______________________________________________________________________

## Verification

1. **Unit/integration tests:**
   `/home/ken/miniconda3/envs/pik/bin/python -m pytest` — existing
   `ProcessingManager` tests should keep passing. Update any that mock the
   internal worker process to mock `StemWorker` instead.

2. **Code quality:**
   `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`

3. **Manual pipeline verification:**
   a. Start PiKaraoke, download a song end-to-end, verify stems are produced
   in `vocal/` and `nonvocal/`.
   b. Verify the processing terminal window still receives both FFmpeg
   progress output and audio-separator log lines.
   c. Download a second song while the first is still processing — verify
   sequential processing and that `processing_started`/`processing_complete`
   events fire in order (watch the Processing page UI or log).

4. **Cancel-during-extract:**
   a. Download a long video. Immediately after download completes, cancel
   via the Processing page.
   b. Verify FFmpeg exits promptly, no stems are created, `_cleanup_stems`
   runs, and the StemWorker model is **not** reloaded (check log: no
   "Audio separator model loaded" message after cancel).

5. **Cancel-during-stemming:**
   a. Download a song, let extract finish, cancel during the separation step.
   b. Verify the StemWorker process is SIGKILL'd, orchestrator raises
   `WorkerDiedError` → `_CancelledError`, stems are cleaned up, and the
   worker is eagerly restarted (log: "Audio separator model loaded" appears
   once more before the next job).

6. **Cancel-during-transcode:**
   a. Download a song, let separation finish, cancel during the transcode
   step. Note: transcode is fast — may need a long stem or to add a brief
   artificial delay during manual testing if you want to reliably hit this
   window.
   b. Verify FFmpeg exits, partial `vocal/*.m4a` is cleaned up, model is
   **not** reloaded.

7. **Worker crash recovery:**
   a. Manually `kill -9` the stem worker subprocess while it's separating.
   b. Verify orchestrator emits `processing_error`, then successfully
   processes the next queued song (eager restart).

8. **Queue orphan regression check:**
   a. Queue 3 songs back-to-back. Cancel song 1 mid-stemming.
   b. Verify songs 2 and 3 still process correctly (no stale queue items,
   no duplicate processing).

9. **Shutdown cleanliness:**
   a. Stop PiKaraoke (Ctrl+C) while stemming is in progress.
   b. Verify no orphaned Python processes (`ps aux | grep python`), PTY
   socket file is cleaned up, and shutdown completes within ~15s.
