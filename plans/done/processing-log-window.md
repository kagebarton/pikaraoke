# Plan: Redirect Processing Manager Logs to Terminal Window (Revised)

## Context

`processing_manager.py` logs to `processing_manager.log` on disk. The user wants logs displayed in a separate terminal window with no disk IO. A previous attempt (plan `indexed-whistling-breeze`) failed due to:

1. **`cat /dev/fd/{r}` doesn't work across process boundaries** — xterm spawns `cat` as a grandchild; fd inheritance through terminal emulators is unreliable
2. **Anonymous pipe assumed `fork` semantics** — worker process won't inherit fds on macOS/Windows (`spawn` start method)
3. **Race condition** — parent closed read end before `cat` could open it

## Approach: Named FIFO on tmpfs

Use a named FIFO on a RAM-backed filesystem (`/run/user/{uid}/`). No data hits disk — FIFO data lives in kernel pipe buffers. The FIFO *path* is a plain string, so it works with both `fork` and `spawn` multiprocessing start methods.

**Why FIFO over anonymous pipe:** The path is a string that any process can `open()` independently — no fd inheritance needed. Terminal emulators, worker processes, etc. all just open by path.

**Why tmpfs:** `/run/user/{uid}/` is guaranteed to be a tmpfs mount on modern Linux (managed by systemd). Zero disk IO.

## Critical Files

- `pikaraoke/lib/processing_manager.py` — all changes
- `tests/unit/test_processing_manager.py` — fixture updates if worker signature changes

## Implementation Steps

### 1. Remove file-logging infrastructure

Delete:

- `PROCESSING_LOG_FILE` constant
- `_processing_log_handler` global
- `_get_log_handler()` function

Add:

- `logger = logging.getLogger(__name__)` module-level logger

### 2. Add FIFO + terminal helper functions

```python
def _find_terminal() -> str | None:
    for term in ("xterm", "lxterminal", "xfce4-terminal"):
        if shutil.which(term):
            return term
    return None


def _create_log_fifo() -> str:
    """Create a named FIFO on tmpfs. Returns the path."""
    uid = os.getuid()
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    fifo_path = os.path.join(runtime_dir, "pikaraoke_processing.fifo")
    if os.path.exists(fifo_path):
        os.unlink(fifo_path)
    os.mkfifo(fifo_path)
    return fifo_path
```

### 3. Modify `ProcessingManager.__init__`

Add instance variables:

```python
self._fifo_path: str | None = None
self._log_stream: io.TextIOWrapper | None = None
self._terminal_proc: subprocess.Popen | None = None
```

### 4. Modify `start()` — set up FIFO + terminal BEFORE starting worker

```python
terminal = _find_terminal() if os.environ.get("DISPLAY") else None
if terminal:
    self._fifo_path = _create_log_fifo()
    # Launch terminal reading from FIFO — cat will block until writer opens
    self._terminal_proc = subprocess.Popen(
        [
            terminal,
            "-title",
            "PiKaraoke: Stem Processing",
            "-e",
            "cat",
            self._fifo_path,
        ],
    )
    # Open write end — blocks until cat opens read end (self-synchronizing)
    self._log_stream = open(self._fifo_path, "w", buffering=1)
    handler: logging.Handler = logging.StreamHandler(self._log_stream)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
        )
    )
else:
    handler = logging.NullHandler()

logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False
```

**Key detail on `-e` syntax:** `xterm -e cat /path` works because xterm treats all args after `-e` as the command + args. For `lxterminal`, the syntax is `lxterminal -e "cat /path"` (single string). Need to handle this per-terminal — or just support `xterm` initially and expand later.

### 5. Modify worker to accept FIFO path

Change `_make_worker_process` to pass `self._fifo_path`:

```python
def _make_worker_process(self) -> Process:
    return Process(
        target=_run_worker_process,
        args=(self._queue, self._result_queue, self._fifo_path),
        daemon=False,
    )
```

Change `_run_worker_process` signature:

```python
def _run_worker_process(queue, result_queue, fifo_path: str | None) -> None:
```

Worker sets up its own handler by opening the FIFO path:

```python
if fifo_path:
    stream = open(fifo_path, "w", buffering=1)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(...)
else:
    handler = logging.NullHandler()

processing_logger = logging.getLogger(__name__)
processing_logger.addHandler(handler)
processing_logger.setLevel(logging.DEBUG)
processing_logger.propagate = False

sep_logger = logging.getLogger("audio_separator")
sep_logger.addHandler(handler)
sep_logger.setLevel(logging.DEBUG)
sep_logger.propagate = False
```

**Multiple writers to a FIFO are safe** — POSIX guarantees atomic writes for messages \<= PIPE_BUF (4096 bytes on Linux). Log lines are well under this limit.

### 6. Change all `logging.*` calls to `logger.*`

All direct `logging.info(...)` etc. calls become `logger.info(...)`.

### 7. Modify `stop()` — close FIFO after worker exits

```python
def stop(self) -> None:
    if self._worker_process is None or not self._worker_process.is_alive():
        return
    self._queue.put(None)
    self._worker_process.join(timeout=10)
    if self._worker_process.is_alive():
        self._worker_process.terminate()
    # Close write end -> EOF -> cat exits -> terminal closes
    if self._log_stream is not None:
        self._log_stream.close()
        self._log_stream = None
    if self._terminal_proc is not None:
        try:
            self._terminal_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._terminal_proc.terminate()
        self._terminal_proc = None
    # Clean up FIFO
    if self._fifo_path and os.path.exists(self._fifo_path):
        os.unlink(self._fifo_path)
        self._fifo_path = None
```

## Potential Pitfalls & Mitigations

### FIFO open blocking

`open(fifo_path, "w")` blocks until a reader opens the other end. Since `cat` is launched first, it should open the read end quickly. In practice this is \< 1 second. If it's a concern, we could open in a thread with a timeout — but start simple.

### Terminal `-e` syntax differences

- `xterm -e cmd arg1 arg2` — treats remaining args as command + args
- `lxterminal -e "cmd arg1 arg2"` — expects single string after -e
- `xfce4-terminal -e "cmd arg1 arg2"` — same as lxterminal

Mitigation: use `sh -c` wrapper for consistency:

```python
[
    terminal,
    "-title",
    "PiKaraoke: Stem Processing",
    "-e",
    f"sh -c 'cat {shlex.quote(self._fifo_path)}'",
]
```

### Worker dies and restarts (line 99)

When `_check_worker_health()` restarts the worker, the new worker needs the FIFO path. Since `_make_worker_process` reads `self._fifo_path`, this works automatically.

### FIFO cleanup on crash

If the process crashes without calling `stop()`, the FIFO file remains on tmpfs. Mitigated by:

1. `_create_log_fifo()` unlinks existing FIFO before creating a new one
2. tmpfs is cleared on reboot anyway

## Verification

1. `python -m pytest tests/unit/test_processing_manager.py` — all tests pass
2. Start pikaraoke on a machine with `$DISPLAY` set and `xterm` installed
3. Confirm terminal window opens titled "PiKaraoke: Stem Processing"
4. Download a song; confirm processing logs stream in the terminal window
5. Confirm no `processing_manager.log` file is created
6. Confirm no files written to disk (check `/run/user/{uid}/pikaraoke_processing.fifo` exists as a FIFO, not a regular file)
7. Exit pikaraoke; confirm terminal window closes and FIFO is cleaned up
8. Test without `$DISPLAY` — confirm no errors, logs silently discarded
