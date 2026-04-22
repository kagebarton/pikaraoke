Model: Claude Sonnet 4.6

# Plan: Remove gevent and monkeypatch, switch to threading mode

## Motivation

`gevent` + `monkey.patch_all()` globally replaces Python's I/O, threading, and
socket primitives at import time. This has caused recurring crash bugs in this
project, particularly around `multiprocessing` (stem_worker had to use raw
`Pipe` instead of `Queue` to work around it). The pattern is antiquated for a
Flask-SocketIO app serving a handful of clients.

Flask-SocketIO supports `async_mode="threading"` natively, which uses standard
library threads and requires no monkeypatching. For PiKaraoke's concurrency
profile (a few WebSocket clients, one run loop, occasional background tasks),
threading mode is more than sufficient.

## Scope

**Files modified:**
- `pikaraoke/app.py` — bulk of the changes
- `pikaraoke/lib/stem_worker.py` — docstring cleanup only
- `pikaraoke/lib/processing_manager.py` — comment cleanup only
- `pyproject.toml` — remove `gevent` dependency

**Files NOT modified (no code changes needed):**
- `pikaraoke/karaoke.py` — `run()` loop uses `time.sleep()`, works identically
  under threading
- `pikaraoke/lib/process_terminal.py` — "spawn" in this file refers to
  subprocess spawning, not gevent
- All route files, socket_events, etc. — Flask-SocketIO's API is identical
  across async modes

## Steps

### Step 1: Rewrite `app.py` imports and server startup

**Remove** (lines 3-5):
```python
from gevent import monkey, spawn
monkey.patch_all()
```

**Remove** (line 47):
```python
from gevent.pywsgi import WSGIServer
```

**Add** at top of file (after existing stdlib imports):
```python
from threading import Thread
```

**Change** SocketIO init (line 50):
```python
# Before:
socketio = SocketIO(async_mode="gevent", cors_allowed_origins=args.url)

# After:
socketio = SocketIO(async_mode="threading", cors_allowed_origins=args.url)
```

### Step 2: Replace `gevent.spawn` with `threading.Thread`

**Change** (line 213):
```python
# Before:
spawn(upgrade_youtubedl)

# After:
Thread(target=upgrade_youtubedl, daemon=True).start()
```

### Step 3: Restructure server startup to use `socketio.run()`

This is the one structural change. Currently:
```python
server = WSGIServer(("0.0.0.0", int(args.port)), app, log=None, error_log=logging.getLogger())
server.start()        # non-blocking (gevent greenlet)
k.run()               # blocks main thread
k.stop()
# cleanup...
```

With threading mode, `socketio.run()` blocks. The karaoke run loop also blocks.
One of them must move to a background thread.

**Decision: run `k.run()` in a daemon thread.** Rationale:
- `k.run()` is a simple polling loop (`time.sleep(0.5)` per iteration) — safe
  to run in any thread.
- `socketio.run()` expects to be the main-thread signal handler for clean
  shutdown (catches KeyboardInterrupt/SIGINT). Keeping it on the main thread is
  the standard Flask-SocketIO pattern.
- `k.stop()` must still be called on shutdown.

**New startup code:**
```python
Thread(target=upgrade_youtubedl, daemon=True).start()

if args.enable_swagger:
    logging.info(f"Swagger API docs enabled at {k.url}/apidocs")

# Run the karaoke polling loop in a background thread
karaoke_thread = Thread(target=k.run, daemon=True)
karaoke_thread.start()

try:
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(args.port),
        log_output=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
finally:
    k.stop()

    import shutil
    if k.temp_dir and os.path.exists(k.temp_dir):
        shutil.rmtree(k.temp_dir, ignore_errors=True)
```

Notes on `socketio.run()` arguments:
- `log_output=False` — suppresses Werkzeug per-request logs (matches current
  `WSGIServer(log=None)` behavior)
- `use_reloader=False` — we're not in dev mode
- `allow_unsafe_werkzeug=True` — Flask-SocketIO in threading mode uses
  Werkzeug's dev server under the hood. This flag acknowledges that. For a LAN
  karaoke app this is fine. (Without it, Flask-SocketIO prints a warning.)

### Step 4: Remove `gevent` from dependencies

**In `pyproject.toml`**, delete:
```
"gevent>=24.11.1",
```

Then reinstall: `conda activate pik && pip install -e .`

### Step 5: Clean up gevent-related comments/docstrings

**`pikaraoke/lib/stem_worker.py`** — update docstrings that reference gevent:

Module docstring (lines 4-8): remove the gevent explanation. The `Pipe` design
is still valid (it's simpler than Queue for this use case), but the *reason* is
no longer "gevent workaround."

Class docstring (lines 37-39): same — remove the gevent-specific reasoning.

**`pikaraoke/lib/processing_manager.py`** (line 146): remove "Safe to call from
gevent context" — replace with something accurate like "Thread-safe" or just
remove the line.

### Step 6: Run tests and manual verification

```bash
# Unit tests
/home/ken/miniconda3/envs/pik/bin/python -m pytest

# Pre-commit
pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
```

**Manual test plan:**
- [ ] App starts without gevent import errors
- [ ] Web UI loads, WebSocket connection establishes (check browser console)
- [ ] Queue a song via YouTube search — download completes, song plays
- [ ] Queue multiple songs — queue advances correctly after each song
- [ ] Pause/resume/skip from web UI
- [ ] Volume control works
- [ ] Stem separation (if enabled) completes without hanging
- [ ] Ctrl+C in terminal cleanly shuts down (no zombie processes)
- [ ] Test on Raspberry Pi if available (gevent C-extension build was a pain
  point there — confirm it's no longer needed)

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `socketio.run()` + Werkzeug can't handle concurrent WebSocket clients | Low — PiKaraoke serves <10 clients | Monitor; if issues arise, add `simple-websocket` or `gevent-websocket` back as a transport-only dependency (no monkeypatching) |
| `k.run()` thread + Flask request threads cause race conditions | Low — `k.run()` reads state, Flask routes mutate it, existing locks cover this | Existing `_state_lock` in processing_manager and queue_manager already handle thread safety |
| `allow_unsafe_werkzeug=True` concerns | None for this use case — LAN-only karaoke app | Document in code comment |
| Some downstream code implicitly depends on gevent's cooperative scheduling | Very low — grep shows no other gevent imports | Test thoroughly |

## What this does NOT change

- No changes to the karaoke run loop, queue management, playback, or any
  business logic
- No changes to SocketIO event names or payloads
- No changes to the frontend
- No async/await rewrite — everything stays synchronous
- stem_worker stays with `Pipe` (it works, no reason to change to Queue)
