Model: Claude Opus 4.6

# Stem Processing Regression Investigation

## Problem

After commit `128dc33` (python-mpv migration), FFmpeg audio extraction in the stem processing pipeline produces only 0.23 seconds of audio instead of the full ~29 seconds. This breaks stem separation entirely. The same song processes correctly on the previous commit (`14be2f5`).

## Symptoms

- FFmpeg extraction runs but produces a tiny WAV (~0.23s)
- Hundreds of AAC decoding errors in processing log:
  - "Number of bands exceeds limit"
  - "Prediction is not allowed in AAC-LC"
  - "Too large remapped id is not implemented"
- audio-separator receives the truncated WAV (0.26s) and produces empty/useless stems
- The temp folder for stem processing is created but cleaned up quickly due to failure

## Environment

- No GPU on this machine
- FFmpeg 6.1.1-3ubuntu5 (system)
- Conda env `pik`
- Nothing is playing in mpv when processing runs (idle mode)

## What Changed in 128dc33

Files modified:

- `pikaraoke/lib/mpv_controller.py` — **complete rewrite**: subprocess mpv + JSON IPC socket replaced with in-process libmpv via python-mpv ctypes bindings
- `pikaraoke/karaoke.py` — initialization order changed: PlaybackController created before `mpv_controller.start()`; `check_playback_ended()` removed from main loop (callbacks handle it now); callback wiring added
- `pikaraoke/lib/overlay_manager.py` — minor (2 lines)
- `pikaraoke/lib/playback_controller.py` — minor (14 lines)
- `pyproject.toml` — added `python-mpv>=1.0.7`
- Tests updated, plan file added

### Key architectural change

**Before (14be2f5):** mpv runs as a separate subprocess (`subprocess.Popen`). Communication via JSON IPC socket. FFmpeg libraries are only loaded in the mpv subprocess, not in the pikaraoke process.

**After (128dc33):** mpv runs in-process via python-mpv ctypes bindings (`mpv.MPV(...)`). This loads `libmpv.so` (and transitively all of mpv's dependencies, including its own copies of libavcodec, libavformat, etc.) directly into the pikaraoke process's address space.

### Initialization order (after)

1. `MpvController()` created
2. `PlaybackController()` created
3. Callbacks wired via `set_callbacks()`
4. `mpv_controller.start()` — creates `mpv.MPV(idle=True, force_window=True, ...)` which loads libmpv into process
5. ProcessingManager starts (line 267-270 in karaoke.py), creates PTY, spawns StemWorker subprocess, starts orchestrator thread

## Investigation

### Ruled Out

- **Different FFmpeg binary or library versions** — same `ffmpeg` binary, same shared libs
- **Conda env differences** — same environment
- **LD_LIBRARY_PATH issues** — checked
- **File corruption** — same file works on previous commit
- **`-fflags +discardcorrupt`** — attempted as workaround in `_ffmpeg_extract`, linter reverted the change (needs to be re-applied properly if pursued)

### Simulation Test (`/tmp/sim_test.py`)

Created a comprehensive simulation that matches the real pikaraoke setup:

- Loads libmpv in-process via `mpv.MPV(idle=True, force_window=True, ...)`
- Creates PTY pair with `os.openpty()`, sets inheritable
- Spawns a `multiprocessing.Process` worker (simulating StemWorker fork)
- Runs FFmpeg with stdout/stderr redirected to PTY slave fd

**Result: Could NOT reproduce the bug.** FFmpeg produced the correct 5,115,982 byte output with no AAC errors. The simulation works perfectly.

### What the Simulation Doesn't Capture

The simulation is a minimal reproduction. The real pikaraoke process has:

- Flask/SocketIO web server running
- Multiple event system subscriptions
- PreferenceManager, SongManager, and other subsystems initialized
- YouTube-dl integration
- Multiple threads (orchestrator, Flask, SocketIO, overlay tick, etc.)
- The full `karaoke.py` initialization sequence

## Hypotheses (Unexplored)

### H1: libmpv's FFmpeg symbols interfere with subprocess FFmpeg (MOST LIKELY)

When python-mpv loads `libmpv.so` via ctypes, libmpv transitively loads its own FFmpeg shared libraries (libavcodec, libavformat, etc.). On Linux with `fork()` semantics, `subprocess.Popen` does `fork + exec`. The `exec` should give FFmpeg a clean address space... BUT:

- If there's any `LD_PRELOAD` or `LD_LIBRARY_PATH` contamination inherited through the fork
- If libmpv registers any signal handlers or atexit handlers that interfere with forked children
- If the PTY fd state is somehow different when libmpv is loaded

The simulation test DID load libmpv, so this hypothesis is weakened but not eliminated — the simulation doesn't have the full set of threads and subsystems running.

### H2: File descriptor leak or contamination

The real pikaraoke process has many more open file descriptors than the simulation:

- Flask server socket
- SocketIO connections
- Multiple pipe pairs (StemWorker IPC)
- PTY master/slave pair
- Logging file handlers

If any of these fds leak into the FFmpeg subprocess (especially if one happens to collide with an fd FFmpeg expects to use), it could cause corruption. The `subprocess.Popen` `close_fds` parameter defaults to `True` on POSIX, which should close non-stdin/stdout/stderr fds... but the PTY slave fd is explicitly passed as stdout/stderr, so it stays open.

### H3: Timing / race condition

The initialization order changed. ProcessingManager.start() now runs after libmpv is fully initialized (including its internal threads for video output, event handling, etc.). If there's a race between libmpv's threads and the fork in StemWorker.start(), the forked child could inherit inconsistent state.

### H4: Memory pressure on no-GPU machine

Loading libmpv in-process (vs as a subprocess) increases the main process's memory footprint. On a machine with no GPU, if memory is tight, FFmpeg might be getting killed or truncated by OOM.

## Recommended Next Steps

1. **Add instrumentation to the real pikaraoke process** — Before the `subprocess.Popen` call in `_run_ffmpeg`, log:

   - `os.listdir('/proc/self/fd')` (open file descriptors)
   - `os.environ` relevant vars (LD_LIBRARY_PATH, LD_PRELOAD)
   - Memory usage (`/proc/self/status` VmRSS)
   - Check if any libmpv signal handlers are installed

2. **Test with `close_fds=True` explicitly and `env={}` override** — Pass a clean environment to FFmpeg subprocess to rule out env contamination.

3. **Test spawning FFmpeg before mpv_controller.start()** — If extraction works before libmpv is loaded but fails after, that confirms the libmpv hypothesis.

4. **Check if `multiprocessing.set_start_method('spawn')` fixes it** — Using 'spawn' instead of 'fork' for the StemWorker would give it a clean address space, but FFmpeg extraction happens in the main process's orchestrator thread, not in the worker.

5. **Re-apply `-fflags +discardcorrupt`** — As a pragmatic workaround (not a fix), properly formatted for the linter.

## Attempted Fixes

### Fix 2: Minimal environment + -fflags +discardcorrupt

- **Date**: 2026-04-17
- **Change**:
  - Pass minimal environment (only PATH, HOME, USER, LANG) to FFmpeg subprocess
  - Add `-fflags +discardcorrupt` to FFmpeg extraction command to skip corrupted frames
- **Result**: **FAILED** - Same AAC decode errors still occur
- **Analysis**: The issue is deeper than environment variables - possibly file descriptor inheritance or PTY-specific

### Fix 3: Bypass PTY (stdout/stderr=DEVNULL)

- **Date**: 2026-04-17
- **Result**: **FAILED** - Still 41kb WAV, same AAC errors
- **Analysis**: PTY is not the cause

### Fix 4: Debug probe — FFmpeg before vs after mpv.MPV() init

- **Date**: 2026-04-17
- **Result**: BEFORE_MPV produces correct 7.6MB WAV, AFTER_MPV produces 37KB WAV
- **Analysis**: Confirmed libmpv loading is the cause

### Fix 5: stdin=subprocess.DEVNULL (ROOT CAUSE FOUND)

- **Date**: 2026-04-17
- **Result**: **SUCCESS** - Full 7,696,462 byte WAV produced correctly
- **Root cause**: libmpv takes over the process stdin (fd 0). When FFmpeg inherits
  this corrupted/repurposed stdin via fork+exec, its AAC decoder misreads the
  bitstream. Adding `stdin=subprocess.DEVNULL` gives FFmpeg a clean `/dev/null`
  stdin and extraction works perfectly.
- **Isolation test results**:
  - `close_fds=True` only: 41,038 bytes (FAILED)
  - `stdin=subprocess.DEVNULL` only: 7,696,462 bytes (SUCCESS)
  - neither (original): 36,942 bytes (FAILED)
- **Fix applied**: Added `stdin=subprocess.DEVNULL` to `subprocess.Popen` call
  in `ProcessingManager._run_ffmpeg()` (processing_manager.py line 342)

## Key Files

- [processing_manager.py](pikaraoke/lib/processing_manager.py) — `_run_ffmpeg` (line 339), `_ffmpeg_extract` (line 302)
- [stem_worker.py](pikaraoke/lib/stem_worker.py) — StemWorker subprocess, fork semantics
- [process_terminal.py](pikaraoke/lib/process_terminal.py) — PTY creation
- [mpv_controller.py](pikaraoke/lib/mpv_controller.py) — libmpv initialization
- [karaoke.py](pikaraoke/karaoke.py) — initialization order, ProcessingManager.start()
