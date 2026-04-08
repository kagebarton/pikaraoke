# Processing Page Implementation Plan

Model: Claude Opus 4.6

## Context

The user wants a dedicated web UI page to monitor the download-and-stem-separation pipeline. Currently, download progress is buried at the bottom of the Queue page, and processing (stem separation) has zero UI visibility. This page gives users a single place to see what's happening, cancel unwanted jobs, and queue completed songs.

---

## Architecture

### New: Pipeline Tracker (`pikaraoke/lib/pipeline_tracker.py`)

A lightweight event-driven tracker that maintains an ordered list of songs moving through the pipeline. Neither manager currently retains completed items, so a unified tracker is required.

**Data model per item:**
```python
id: str               # UUID for stable client-side identity
title: str            # display title
song_path: str | None # set after download completes
url: str              # video URL
user: str             # who initiated download
download_status: str  # "pending" | "active" | "complete" | "error"
processing_status: str # "waiting" | "pending" | "active" | "complete"
download_progress: float  # 0-100
```

**Status derivation strategy** (avoids cross-process event complexity):
- Download status: read directly from `download_manager.active_download` and `pending_downloads`
- Processing status: derived from `processing_manager.pending_jobs` list position:
  - Not yet in list (download still in progress) -> "waiting"
  - First in list + worker alive -> "active"
  - In list but not first -> "pending"
  - No longer in list + download was complete -> "complete"
- Call `processing_manager._drain_results()` before checking to ensure fresh state

**Event hooks needed:**
- `download_queued` (new event from DownloadManager) -> create PipelineItem
- `song_downloaded` -> set `song_path`, mark download complete
- `download_error` (new event from DownloadManager) -> mark download error

**Thread safety:** `threading.Lock` around items list (gevent greenlets are cooperative, but download worker is a real thread).

---

## Files to Create

### 1. `pikaraoke/lib/pipeline_tracker.py`
- `PipelineTracker` class with items list, lock, event subscriptions
- `get_status()` method that enriches items with live download progress and derived processing status
- `cancel(item_id)` delegates to appropriate manager
- `enqueue(item_id)` queues completed song for playback
- `remove(item_id)` removes item from tracker list

### 2. `pikaraoke/routes/processing.py`
- Blueprint: `processing_bp = Blueprint("processing", __name__)`
- `GET /processing` - render page template
- `GET /processing/status` - JSON status of all pipeline items
- `POST /processing/<item_id>/cancel` - cancel and clean up
- `POST /processing/<item_id>/enqueue` - queue completed song

### 3. `pikaraoke/templates/processing.html`
- Extends `base.html`, follows queue.html patterns
- JS polls `/processing/status` every 1s (less aggressive than download's 500ms since processing is slower)
- Socket events `download_started` / `download_stopped` trigger immediate refresh
- Each row: title (left) | download icon | separation icon | action button (right)
- Icon states via CSS classes: `.step-pending` (grey), `.step-active` (flashing teal), `.step-complete` (solid teal)
- Cancel button (`icon-cancel-circled-1`) for in-progress items
- Queue button (`icon-list-add`) for completed items
- Empty state message when no items

---

## Files to Modify

### 4. `pikaraoke/lib/download_manager.py`

Current state: already has `_is_downloading` flag, `active_download` dict with progress tracking, `pending_downloads` shadow queue, `download_errors` list with UUIDs, and `get_downloads_status()`. The `process` variable from `subprocess.Popen` is local to `_execute_download`.

Changes needed:
- Store `self._active_process` as an instance attribute (promote the local `process` variable in `_execute_download`)
- Emit `download_queued` event in `queue_download()` with download data dict
- Emit `download_error` event in `_execute_download()` when `rc != 0` with video URL (in addition to existing error tracking)
- Add `cancel_active_download()`: terminate `_active_process`, clear `active_download`
- Add `cancel_pending_download(video_url)`: add URL to `_cancelled_urls` set, remove from `pending_downloads`
- In `_process_queue()`: after `download_queue.get()`, skip if URL is in `_cancelled_urls`

### 5. `pikaraoke/lib/processing_manager.py`

Current state: uses `multiprocessing.Process` with a `Queue` for jobs and `SimpleQueue` for results. Has `pending_jobs` list, `_drain_results()`, `blocked_processing_words` filtering, and `ProcessTerminal` integration (PTY-based output to a secondary terminal window). Worker process runs in a separate process with stdout/stderr redirected via PTY slave fd.

Changes needed:
- Add `cancel_active(song_path)`: terminate worker process, remove from `pending_jobs`, clean up partial stems, restart worker (must re-create `ProcessTerminal` or reuse existing PTY)
- Add `cancel_pending(song_path)`: remove from `pending_jobs`, add to `_cancelled_paths` set
- In `_drain_results()`: when a cancelled path comes back, clean up its output files
- Add `get_active_job() -> str | None`: returns first item in `pending_jobs` if worker is alive

Note: cancelling the active job requires terminating the `multiprocessing.Process` (not a thread). The PTY slave fd should survive worker restart since it's owned by `ProcessTerminal`, but the worker process will need a new `Process` instance with the same slave fd passed in.

### 6. `pikaraoke/karaoke.py`

Current state: instantiates `DownloadManager` and `ProcessingManager` sequentially near the end of `__init__` (lines ~244-260). Both managers receive `events` and `preferences`. Event wiring (e.g., `song_downloaded -> song_manager.register_download`) is done earlier in `__init__`.

Changes needed:
- Import `PipelineTracker`
- Instantiate after both managers are created (after line ~260)
- Pass `download_manager`, `processing_manager`, `queue_manager`, `events` to tracker
- Wire tracker event subscriptions

### 7. `pikaraoke/app.py`

Current state: has `_internal_blueprints` list (lines 93-98) containing `home_bp`, `info_bp`, `splash_bp`, `batch_song_renamer_bp`.

Changes needed:
- Import `processing_bp` from `pikaraoke.routes.processing`
- Add to `_internal_blueprints` list

### 8. `pikaraoke/templates/base.html`

Current state: navbar items are in `.navbar-brand` div (line ~197). Items: home, queue, search, browse. Nav highlight JS is inline (lines ~114-128) using `currentPath` checks.

Changes needed:
- Add navbar item after browse (before the burger button):
  ```html
  <a id="processing" class="navbar-item" href="{{ url_for('processing.processing') }}">
    <i class="icon icon-cog" title="Processing"></i>
    <span>{% trans %}Processing{% endtrans %}</span>
  </a>
  ```
- Add initial highlight check: `if (currentPath == "/processing") { $("#processing").addClass("is-active") }`

### 9. `pikaraoke/static/spa-navigation.js`

Current state: `updateNavHighlight()` at line ~399 handles `/`, `/queue`, `/search`, `/browse`, `/info`.

Changes needed:
- Add to `updateNavHighlight()`:
  ```javascript
  } else if (path === '/processing') {
      $('#processing').addClass('is-active');
  }
  ```

---

## UI Design

### Row Layout
```
| Song Title                          | [download-icon] [separation-icon] [action-btn] |
```

### Icon States (CSS)
- **Pending**: grey (`#666`)
- **Active**: flashing teal (CSS `@keyframes` pulsing between `#666` and `#00d1b2`)
- **Complete**: solid teal (`#00d1b2` - Bulma's primary/teal color)
- **Error**: solid red (`#f14668` - Bulma's danger)

### Icons
- **Nav bar**: `icon-cog` (gear - universal "processing" symbol)
- **Download step**: `icon-down-big` (down arrow)
- **Separation step**: `icon-music` (musical note)
- **Cancel action**: `icon-cancel-circled-1` (red)
- **Queue action**: `icon-list-add` (green)

### Styling
- Dark background rows matching queue page (`has-background-dark` boxes or striped table rows)
- Responsive: title truncates with ellipsis, icons stay visible
- Matches existing Bulma dark theme aesthetic

---

## Cancellation Behavior

| State | Cancel Action |
|-------|--------------|
| Download pending | Remove from download queue, remove tracker item |
| Download active | Terminate yt-dlp subprocess (`_active_process`), clean up partial files, remove tracker item |
| Processing pending | Mark as cancelled in `_cancelled_paths`, clean up when worker finishes |
| Processing active | Terminate worker `Process`, clean up partial stems in vocal/nonvocal dirs, restart worker with existing PTY slave fd, remove tracker item |

**File cleanup on cancel:**
- Partial downloads: glob `download_path` for files matching the video ID
- Partial stems: delete `vocal/{stem}---vocal.m4a` and `nonvocal/{stem}---nonvocal.m4a` if they exist
- Temp dirs: clean up `pikaraoke_stems_*` temp directories

---

## Implementation Order

1. **Backend foundation**: `pipeline_tracker.py` (new), modify `download_manager.py`, modify `processing_manager.py`
2. **Wiring**: modify `karaoke.py` to instantiate tracker and wire events
3. **API**: `routes/processing.py` (new), modify `app.py` to register blueprint
4. **Frontend**: `templates/processing.html` (new), modify `base.html` navbar, modify `spa-navigation.js`

---

## Verification

1. Start PiKaraoke, navigate to Processing page via navbar icon
2. Search and download a song - verify it appears on Processing page with download icon flashing teal
3. After download completes, verify download icon goes solid teal and separation icon starts flashing
4. After separation completes, verify both icons are solid teal and queue button appears
5. Click queue button - verify song is added to playback queue
6. Download another song and cancel during download - verify partial files are cleaned up
7. Download a song, let it complete, then cancel during separation - verify stems are cleaned up
8. Test on mobile viewport - verify responsive layout
9. Run `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
10. Run `python -m pytest` for existing tests
