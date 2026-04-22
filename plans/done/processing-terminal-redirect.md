Model: Claude Opus 4.6

# Redirect ProcessingManager Output to Secondary Terminal

## Context

ProcessingManager currently logs to a disk file (`processing_manager.log`). Subprocess
output (ffmpeg, audio-separator progress bars) is captured and discarded. The goal is to
remove disk logging and redirect ALL output -- Python logging and subprocess
stdout/stderr -- to a secondary terminal window that opens on startup and closes on exit.
Progress bars must render in real time, which requires a PTY so `isatty()` returns True.

## Architecture

```
Worker Process (multiprocessing.Process)
  |-- os.dup2(pty_slave, stdout/stderr)
  |-- ffmpeg / audio-separator inherit PTY -> progress bars enabled
  |-- Python logging -> StreamHandler(stderr) -> PTY
  \-- (PTY master read by relay thread in main process)

Main Process
  \-- ProcessTerminal
        |-- PTY master fd -> relay thread -> Unix domain socket
        \-- spawns terminal emulator running reader script

Secondary Terminal
  \-- process_terminal_reader.py: connects to socket -> raw write to stdout
```

## New Files

### 1. `pikaraoke/lib/process_terminal.py` (~150 lines)

**Class `ProcessTerminal`:**

- `__init__(socket_path: str | None = None)` -- defaults to `~/.pikaraoke/processing.sock`
  (via `get_data_directory()`)
- `start() -> None` -- creates PTY pair, starts relay thread, spawns terminal emulator
- `stop() -> None` -- closes socket, PTY fds, terminates terminal process, joins relay thread
- `get_slave_fd() -> int | None` -- returns PTY slave fd, or `None` on Windows / failure

**Relay thread (`_relay_loop`):**

- Binds Unix domain socket at `self._socket_path`
- Accepts one connection (with timeout)
- Reads from PTY master in a loop (`select.select` with 0.1s timeout + `os.read` 4096 bytes)
- Sends bytes to connected client
- On broken pipe or no client: falls back to stderr of main process
- Exits when shutdown `threading.Event` is set
- Cleans up stale socket file on start and on stop

**Terminal spawning (`_spawn_terminal`):**

- Auto-detect using `shutil.which()`:
  - Linux: `gnome-terminal`, `xterm`, `lxterminal`, `x-terminal-emulator` (in order)
  - Raspberry Pi: `lxterminal` first
  - macOS: `open -a Terminal.app` with a temp shell script
  - Windows: skip (no PTY support)
- Command: `<terminal> -e python3 -m pikaraoke.lib.process_terminal_reader <socket_path>`
- Stores `subprocess.Popen` handle for cleanup

**Fd inheritance:** call `os.set_inheritable(slave_fd, True)` before forking the worker
process, since `os.openpty()` sets `O_CLOEXEC` by default.

### 2. `pikaraoke/lib/process_terminal_reader.py` (~50 lines)

Standalone script, runnable as `python3 -m pikaraoke.lib.process_terminal_reader <socket_path>`.

- Connects to Unix domain socket (retry up to 5x with 0.5s backoff)
- Reads bytes in a loop, writes raw to `sys.stdout.buffer`, flushes
- Prints header line on connect: `"--- PiKaraoke Processing Output ---"`
- On broken pipe / connection lost: prints message, exits cleanly
- Only stdlib imports: `sys`, `socket`, `time`, `os`

## Changes to Existing Files

### 3. `pikaraoke/lib/processing_manager.py`

**Remove disk logging:**

- Delete module globals `_processing_log_handler`, `_processing_log_file`
- Delete `_get_log_handler()` function
- In `__init__`: replace FileHandler setup with `StreamHandler(sys.stderr)` (same formatter)
- In `_run_worker_process`: replace `_get_log_handler()` with `StreamHandler(sys.stderr)`

**Accept PTY slave fd:**

- Add `pty_slave_fd: int | None = None` parameter to `_run_worker_process()`
- At top of worker function: if `pty_slave_fd is not None`, `os.dup2` it onto fds 1 and 2,
  then close the original
- `_make_worker_process()`: pass `self._pty_slave_fd` as additional arg

**Let subprocess output flow to PTY:**

- `_extract_audio()`: remove `capture_output=True`, add `stderr=subprocess.PIPE` only for
  error reporting, but pipe stdout to DEVNULL. Actually: remove `capture_output=True`
  entirely so stderr inherits the PTY. Change error message to
  `f"ffmpeg extraction failed (exit code {result.returncode})"` since stderr is on the
  terminal.
- `_wav_to_m4a()`: same change.

**Integrate ProcessTerminal lifecycle:**

- `__init__`: create `ProcessTerminal`, call `.start()`, store slave fd
- `stop()`: after stopping worker, call `ProcessTerminal.stop()`
- Store `self._process_terminal` and `self._pty_slave_fd`

### 4. `pikaraoke/karaoke.py` -- No changes needed

ProcessingManager already owns its full lifecycle (`__init__` -> `start()` -> `stop()`).
The terminal spawning fits inside ProcessingManager's existing lifecycle.

## Fallback Behavior

When no terminal emulator is available (headless, SSH, Windows):

- `_spawn_terminal` logs a warning and returns without spawning
- Relay thread has no client connected
- Falls back to writing to main process stderr
- Processing continues normally

## Edge Cases

- **Worker dies and restarts** (in `enqueue()`): new worker gets same PTY slave fd; relay
  thread and terminal persist
- **Reader disconnects**: relay catches broken pipe, falls back to stderr
- **Socket path length**: `~/.pikaraoke/processing.sock` is well under the ~104-byte macOS limit
- **PTY buffer**: relay thread continuously drains master side via `select` loop

## Verification

1. Run PiKaraoke on Linux -- secondary terminal should open automatically
2. Queue a song for download -- verify stem separation progress bars render in the
   secondary terminal with real-time updates
3. Verify main terminal has NO processing output (only app-level logs)
4. Kill the secondary terminal mid-processing -- verify processing continues, output
   falls back to main stderr
5. Stop PiKaraoke -- verify secondary terminal closes
6. Run headless (no DISPLAY) -- verify warning logged and output falls back to main stderr
7. Run existing tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`
