# Pipeline Tracking: Robustness & Scalability Fixes

Model: Claude Haiku 4.5

## Overview

Evaluation of the `ProcessingManager` refactor and `PipelineTracker` implementation against plan objectives. Identified 6 bugs, 5 robustness concerns, and 3 architectural improvements. Fixes are small and low-risk; ready to implement immediately.

---

## Critical Bugs (Fix Now)

### B1: Download matched by order, not by URL ID — fragile pairing

**File:** `pikaraoke/lib/pipeline_tracker.py:191-200`

**Problem:**
```python
for item in self._items:
    if item.download_status in ("pending", "active"):
        item.song_path = song_path
        item.download_status = "complete"
        break
```

The comment claims "Match by checking if the song_path contains the video URL ID" but the code grabs the **first** pending/active item. This works only because downloads are strictly FIFO and serial. Any reorder, skipped item, or out-of-order event would associate the `song_path` with the wrong tracker entry.

**Fix:**
Extract video ID from both `song_path` (filename) and `item.url`, match by ID:
```python
from pikaraoke.lib.youtube_dl import get_youtube_id_from_path, get_youtube_id_from_url

def _on_song_downloaded(self, song_path: str) -> None:
    video_id = get_youtube_id_from_path(song_path)
    if not video_id:
        logging.warning(f"Could not extract video ID from {song_path}")
        return
    
    with self._lock:
        for item in self._items:
            item_id = get_youtube_id_from_url(item.url)
            if item_id and item_id == video_id and item.download_status in ("pending", "active"):
                item.song_path = song_path
                item.download_status = "complete"
                item.download_progress = 100.0
                break
```

**Risk:** Low. Requires importing existing helpers; no API changes.

---

### B2: `ProcessingManager.enqueue()` mutates `pending_jobs` without lock

**File:** `pikaraoke/lib/processing_manager.py:112-132`

**Problem:**
```python
def enqueue(self, song_path: str) -> None:
    # ... filter logic ...
    self.pending_jobs.append(song_path)  # <-- outside lock
    try:
        self._pending_queue.put(song_path)
    except Exception:
        self.pending_jobs.remove(song_path)  # <-- outside lock
```

Every other access to `pending_jobs` (`cancel_pending`, `_orchestrator_loop`, `get_status`) is guarded by `_state_lock`. This inconsistency means concurrent readers (UI polling `get_status`) can observe transient states. CPython's GIL prevents crashes, but the invariant is broken.

**Fix:**
```python
def enqueue(self, song_path: str) -> None:
    # ... filter logic ...
    with self._state_lock:
        self.pending_jobs.append(song_path)
    try:
        self._pending_queue.put(song_path)
    except Exception:
        with self._state_lock:
            self.pending_jobs.remove(song_path)
        logging.warning(f"Failed to enqueue: {Path(song_path).name}")
        return
    logging.info(f"Queued for stem separation: {Path(song_path).name}")
```

**Risk:** Low. Lock is already used everywhere else; same pattern.

---

### B3: `StemWorker.start()` leaks old pipe file descriptors on restart

**File:** `pikaraoke/lib/stem_worker.py:54-73`

**Problem:**
```python
def start(self) -> None:
    job_recv, job_send = Pipe(duplex=False)
    self._job_send = job_send  # <-- old _job_send is lost, not closed
    self._job_recv = job_recv
    ...
```

On worker crash → eager restart, the old pipe connections are overwritten without closing. Python's GC will eventually close them, but under repeated crash cycles you leak file descriptors. After ~1000 cycles, the process hits the OS ulimit.

**Fix:**
Call `kill()` (which closes all connections) before creating new ones:
```python
def start(self) -> None:
    # Close any old connections from a previous start/restart
    if self._process is not None and self._process.is_alive():
        self._process.terminate()  # request graceful exit
    if any(conn is not None for conn in (self._job_send, self._job_recv, self._result_send, self._result_recv)):
        self.kill()  # closes all old connections
    
    job_recv, job_send = Pipe(duplex=False)
    # ... rest of start logic
```

Or inline the close logic if you prefer not to call `kill()` from `start()`:
```python
def start(self) -> None:
    for conn in (self._job_send, self._job_recv, self._result_recv, self._result_send):
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
    
    job_recv, job_send = Pipe(duplex=False)
    # ... rest
```

**Risk:** Low. Defensive; prevents a slow leak under repeated crashes.

---

### B4: Dead/confusing branch in `get_status`

**File:** `pikaraoke/lib/pipeline_tracker.py:109-110`

**Problem:**
```python
elif item.download_status == "error":
    item.processing_status = "complete"  # download errored, processing never ran
```

This branch is unreachable: if download errored, the earlier `if item.song_path is None` (line 99) already caught it. And if somehow reachable, labeling a failed download as `processing_status = "complete"` would be misleading in the UI.

**Fix:**
Delete the branch entirely. The logic is:
- If `song_path is None` → "waiting" (download still pending/active or error)
- Else if active → "active"
- Else if pending → "pending"
- Else → "complete" (download done, not in processing queues)

**Risk:** Trivial cleanup.

---

### B5: Errored download shows "waiting" on processing icon — misleading

**File:** `pikaraoke/lib/pipeline_tracker.py:99-104`

**Problem:**
```python
if item.song_path is None:
    if item.download_status == "error":
        item.processing_status = "waiting"  # <-- confusing
    else:
        item.processing_status = "waiting"
```

When a download errors, the item sits in the tracker showing a grey "waiting" processing icon — the same as a legitimate "waiting for download to finish" state. The UI legend doesn't explain this. The user gets a trash button (via `download_status === "error"`) to clean it up, but the icon is misleading.

**Fix:**
Introduce a "n/a" (not-applicable) processing status, or distinguish in `stepClass()`:
```python
if item.download_status == "error" and item.song_path is None:
    item.processing_status = "n/a"  # download failed, processing never started
elif item.song_path is None:
    item.processing_status = "waiting"  # download in progress
```

Update the UI (`processing.html`):
```javascript
function stepClass(status, type) {
    if (status === 'n/a') return 'step-n-a';  // lighter grey, no pulse
    if (status === 'active') return 'step-active';
    // ... rest
}
```

And CSS:
```css
.step-n-a {
    color: #999;  /* lighter grey than pending */
    opacity: 0.6;
}
```

Or simpler: just use "error" for the processing icon when download failed:
```python
if item.download_status == "error":
    item.processing_status = "error"
elif item.song_path is None:
    item.processing_status = "waiting"
```

**Risk:** Low. UI clarification; no state changes.

---

### B6: Rapid cancel clicks re-enter active-cancel branch

**File:** `pikaraoke/lib/pipeline_tracker.py:146-154`

**Problem:**
The UI polls every 1s. Between first cancel click and the next poll that shows `processing_status = "cancelling"`, the status is still `"active"`. A rapid second click re-enters the active branch, calls `cancel_active` again (idempotent, so no crash), and re-sets `item.cancelling = True` (benign).

Not a bug, but the button should be suppressed to prevent re-entry.

**Fix:**
Early-return if already cancelling:
```python
def cancel(self, item_id: str) -> bool:
    song_to_delete: str | None = None
    with self._lock:
        item = self._find_item(item_id)
        if item is None:
            return False
        
        # Already cancelling: ignore
        if item.cancelling:
            return False
        
        if item.download_status == "active":
            # ... rest
```

**Risk:** Trivial. Defensive.

---

## Robustness Concerns (Track)

### R1: `_on_song_downloaded` + `song_deleted` collision

If a user deletes a song from the edit page while it's still in the tracker mid-processing, `_on_song_deleted` removes the tracker item. The orchestrator keeps processing and eventually fires `processing_complete`, which calls `_on_processing_complete` and fails to find the item — silent no-op.

**Status:** Not a bug, but add a comment to `_on_processing_complete`:
```python
def _on_processing_complete(self, song_path: str) -> None:
    with self._lock:
        for item in self._items:
            if item.song_path == song_path:
                item.processing_status = "complete"
                break
        # Item not found: song was deleted mid-processing (user action). Silent no-op.
```

---

### R2: `get_status()` mutates item fields — surprising API

**File:** `pikaraoke/lib/pipeline_tracker.py:72-119`

The method reads state but also writes `item.download_progress`, `item.download_status`, `item.processing_status`. Correct (lock is held), but semantically surprising for a "get" method.

**Recommendation:** Add a docstring clarifying that this is a refresh-and-return operation:
```python
def get_status(self) -> list[dict[str, Any]]:
    """Return enriched status for all pipeline items.
    
    Derives processing status from ProcessingManager state, merges live
    download progress from DownloadManager, and mutates items under lock.
    Called on each UI poll to keep items' transient state fresh.
    """
```

No code change needed; just documentation.

---

### R3: Orchestrator thread 0.5s polling timeout is unnecessary

**File:** `pikaraoke/lib/processing_manager.py:183-188`

```python
while not self._stop_event.is_set():
    try:
        song_path = self._pending_queue.get(timeout=0.5)  # <-- periodic wakeup
    except queue.Empty:
        continue
```

The shutdown sentinel (`put(None)`) already wakes the blocked `get()`. The 0.5s timeout adds a redundant wakeup every 500ms even when idle. Minor inefficiency.

**Recommendation:** Use blocking `get()` — the timeout was defensive but unnecessary:
```python
song_path = self._pending_queue.get()  # blocks until item or sentinel
```

**Trade-off:** Loses the heartbeat. If you ever want a periodic "health check" in the orchestrator (e.g., worker crash detection), keep the timeout. For now, blocking is cleaner.

---

### R4: `subprocess.Popen` has no `close_fds=True` — Windows compat edge case

**File:** `pikaraoke/lib/processing_manager.py:341`

```python
proc = subprocess.Popen(cmd, stdout=stdout_fd, stderr=stderr_fd)
```

Missing `close_fds=True`. On POSIX (Linux/macOS), it's default `True` since Python 3.7. On Windows, it's default `False`, risking fd inheritance.

**Status:** Low risk (you gate the PTY on `is_windows()` elsewhere, so Windows is already handled carefully). But for robustness:
```python
proc = subprocess.Popen(cmd, stdout=stdout_fd, stderr=stderr_fd, close_fds=True)
```

---

### R5: `cancel_pending_download` rebuilds the entire Queue

**File:** `pikaraoke/lib/download_manager.py:386-403`

```python
new_queue: Queue = Queue()
skipped = False
while not self.download_queue.empty():
    item = self.download_queue.get_nowait()
    if item["video_url"] == video_url and not skipped:
        skipped = True
        self.download_queue.task_done()
    else:
        new_queue.put(item)
self.download_queue = new_queue
```

O(n) rebuild. For realistic queue sizes (single digits), fine. But the `task_done()` call for the skipped item is necessary only if the original queue owner hasn't drained the queue fully. Edge case, probably unreachable, but fragile.

**Status:** Works in practice. Worth a comment explaining why `task_done()` is safe here:
```python
# Call task_done() for the removed item so the queue is consistent.
# The original _process_queue hasn't reached this item yet (we're removing it).
self.download_queue.task_done()
```

---

## Architectural Improvements (Defer)

### A1: Stage-based pipeline for scalability

**Why:** Current `_run_pipeline` is a hardcoded 3-step script. Adding a 4th stage (e.g., LyricWorker) requires edits to `ProcessingManager._run_pipeline`, `_active_state`, `cancel_active`, `PipelineTracker`, and the UI. A stage-based design makes new stages pluggable.

**Architecture:**

The stage-based design is purely an **orchestration refactor** — it does not change model persistence. The key insight: model sharing is about **who owns the subprocess and when it dies**, not about how the orchestrator sequences steps. As long as `StemWorker` remains a long-lived subprocess owned by `ProcessingManager` (not created per-job), the model stays loaded across all jobs regardless of how many stages are added.

```
ProcessingManager (main process, orchestration + worker lifecycle)
├── StemWorker (persistent subprocess — owned by ProcessingManager)
│   ├── loads stem model at startup, stays loaded across jobs
│   ├── receives (wav_path, tmp_dir) via Pipe
│   ├── runs separate(), returns paths via Pipe
│   └── eagerly restarted on crash (model reload only on actual death)
├── LyricWorker (persistent subprocess, future — owned by ProcessingManager)
│   ├── loads lyric model at startup, stays loaded across jobs
│   ├── receives audio paths via Pipe
│   └── same crash/restart discipline as StemWorker
├── Pipeline stages (stateless, instantiated once, reused every job)
│   ├── FFmpegExtractStage        — spawns ffmpeg Popen, waits
│   ├── StemSeparationStage       — thin adapter → StemWorker.separate()
│   ├── LyricExtractionStage      — thin adapter → LyricWorker.extract() (future)
│   └── FFmpegTranscodeStage      — spawns ffmpeg Popen, waits
└── Orchestrator thread (real threading.Thread, one loop)
    ├── pulls next song from pending queue
    ├── builds per-job StageContext (tmp_dir, artifacts, cancel flag)
    ├── runs stages sequentially, passing context forward
    ├── checks cancel flag between stages (_CancelledError)
    └── on cancel:
        ├── FFmpeg stages  → kill the active Popen (instant exit)
        └── Worker stages  → set flag only; worker finishes current call,
                              orchestrator raises _CancelledError after return
                              (model stays loaded)
```

**Design sketch:**
```python
class PipelineStage(Protocol):
    name: str
    def run(self, ctx: StageContext) -> None: ...
    def cancel(self, ctx: StageContext) -> None: ...  # optional; flag-only default

class StageContext:
    song_path: Path
    tmp_dir: Path
    artifacts: dict[str, Path]  # "wav_in", "vocal_wav", "instrumental_wav", ...
    cancelled: threading.Event

# Concrete stages:
class FFmpegExtractStage(PipelineStage):
    def run(self, ctx): ...  # spawns ffmpeg, captures wav_in

class StemSeparationStage(PipelineStage):
    def __init__(self, stem_worker: StemWorker) -> None:
        self._worker = stem_worker  # injected, not owned — stays across jobs
    def run(self, ctx):
        vocal, instrumental = self._worker.separate(ctx.artifacts["wav_in"], ctx.tmp_dir)
        ctx.artifacts["vocal_wav"] = vocal
        ctx.artifacts["instrumental_wav"] = instrumental
    def cancel(self, ctx): pass  # delayed cancel — let separate() finish

class LyricExtractionStage(PipelineStage):  # future
    def __init__(self, lyric_worker: LyricWorker) -> None:
        self._worker = lyric_worker
    def run(self, ctx): ...

class FFmpegTranscodeStage(PipelineStage):
    def run(self, ctx): ...  # spawns ffmpeg for vocal + instrumental
```

Then:
```python
def __init__(self, ...):
    self._stem_worker = StemWorker(...)
    self._lyric_worker = None  # None until LyricWorker is added
    self._stages = [
        FFmpegExtractStage(),
        StemSeparationStage(self._stem_worker),
        # LyricExtractionStage(self._lyric_worker),  # add when LyricWorker is ready
        FFmpegTranscodeStage(),
    ]

def _run_pipeline(self, song_path: str) -> None:
    ctx = StageContext(...)
    for stage in self._stages:
        self._set_stage(stage.name)
        stage.run(ctx)
        self._check_cancelled()

def cancel_active(self, song_path: str) -> None:
    with self._state_lock:
        state = self._active_state
        if state and state.song_path == song_path:
            state.cancelled = True
            if self._active_stage:
                self._active_stage.cancel(ctx)
```

**Model persistence invariant:**

As long as these four rules hold, model sharing is preserved:

1. **Worker subprocess lifecycle is owned by `ProcessingManager`, not by stages.** Stages hold a reference, never create/destroy.
2. **Worker lives outside the per-job `StageContext`.** Context is per-job (`tmp_dir`, `artifacts`, cancel flag); worker references are manager-scoped.
3. **Delayed cancel semantics are preserved.** The stage's `cancel()` method sets a flag (or is a no-op) during stemming — never calls `worker.kill()`. Hard-kill is reserved for genuinely unrecoverable states (crash, shutdown).
4. **Eager-restart-on-death stays in the orchestrator.** The finally block in `_orchestrator_loop` that checks `is_alive()` and calls `start()` is manager-level, not stage-level.

Adding `LyricExtractionStage` with a new `LyricWorker` follows the same pattern — both models stay loaded across jobs, both get delayed-cancel discipline, neither reloads between songs.

**Effort:** ~150 lines of refactor code.

**When to implement:** When committing to LyricWorker. Speculative refactor is not worth the risk now.

**Note:** Keep this plan entry so the intent is clear when LyricWorker arrives. The architecture is already compatible with worker injection; LyricWorker just becomes another stage.

---

### A2: Pure event-driven tracker — no state cross-references

**Why:** Current tracker bridges manager state on each `get_status()` call (B1, B4, B5 stem from this). An alternative: make managers emit structured lifecycle events with correlation IDs, and the tracker is purely event-driven with no `get_status` cross-references.

Example events:
```
download_queued(item_id, url, title, user)
download_started(item_id, url)
download_progress(item_id, percent)
download_completed(item_id, song_path)
download_errored(item_id, url, error)

processing_queued(song_path)
processing_started(song_path)
processing_cancelled(song_path)
processing_completed(song_path)
processing_errored(song_path, error)
```

Tracker becomes:
```python
def get_status(self) -> list[dict]:
    with self._lock:
        return [self._item_to_dict(item) for item in self._items]  # no mutations
```

**Trade-off:** More events to emit; higher coupling between managers and tracker. Easier to test (each manager is independent); harder to add correlation logic later.

**When:** Aspirational. Not worth the refactor until the current approach shows real strain (e.g., B1 strikes in production).

---

### A3: Socket-driven UI refresh instead of polling

**Why:** `/processing/status` is polled every 1s, waking the server even when nothing changed. You already have Socket.IO for `download_started`/`download_stopped` — extend it.

**Design:**
```python
# In tracker, on state change:
self._events.emit("pipeline_updated", self.get_status())

# In app.py socketio handlers:
@socketio.on("connect")
def on_connect():
    socketio.emit("pipeline_status", karaoke_instance.pipeline_tracker.get_status())

# Subscribe in processing.html:
if (typeof window.socket !== 'undefined') {
    window.socket.on('pipeline_updated', function(items) {
        renderItems(items);
    });
}

// Fallback polling for browsers without socket
if (typeof window.socket === 'undefined') {
    setInterval(fetchStatus, 1000);
}
```

**Effort:** Small (~20 lines of changes).

**Trade-off:** Adds socket event traffic. 1s polling is already cheap enough that this is an optimization, not a fix. Nice-to-have.

---

## Implementation Order

1. **Immediate (all <5 min):**
   - B2: add lock to `enqueue()`
   - B3: close old pipes in `start()`
   - B4: delete dead branch
   - B6: early-return if `cancelling`

2. **Short-term (same session):**
   - B1: match downloads by video ID
   - B5: clarify errored download icon
   - R2: clarify `get_status()` docstring
   - R3: use blocking `get()` in orchestrator

3. **Nice-to-have (polish):**
   - R4: add `close_fds=True` to Popen
   - R5: comment on `task_done()` safety
   - R1: comment on delete collision

4. **Defer (implement with LyricWorker):**
   - A1: stage-based pipeline
   - A2: pure event-driven tracker
   - A3: socket-driven UI refresh

---

## Testing

After fixes, re-verify:
1. Rapid cancel clicks don't cause duplicate state mutations.
2. Download completion correctly pairs song_path to tracker entry (edge case: out-of-order events).
3. Errored downloads show appropriate icon.
4. No fd leaks after worker crashes and restarts 10x.
5. Orchestrator thread doesn't spam wakeups on idle.

Run existing pytest suite; no regressions expected.
