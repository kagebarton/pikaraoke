# Processing Page Implementation Plan

Model: Claude Opus 4.6

## Context

The user wants a dedicated web UI page to monitor the download-and-stem-separation pipeline. Currently, download progress is buried at the bottom of the Queue page, and processing (stem separation) has zero UI visibility. This page gives users a single place to see what's happening, cancel unwanted jobs, and queue completed songs.

This plan has been updated to reflect the refactored `ProcessingManager` (orchestrator thread + `StemWorker` subprocess with Pipe-based IPC) and to cover additional UX objectives around icon layout and song deletion.

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
processing_status: str # "waiting" | "pending" | "active" | "complete" | "error" | "cancelling"
download_progress: float  # 0-100
cancelling: bool      # True while waiting for delayed cancel to finish (during stemming)
```

**Status derivation strategy** (avoids cross-process event complexity):
- Download status: read directly from `download_manager.active_download` and `pending_downloads`
- Processing status: derived from `processing_manager.pending_jobs` + `get_active_job()`:
  - `song_path is None` (download still in progress) → "waiting"
  - `processing_manager.get_active_job() == song_path` → "active"
  - `song_path in processing_manager.pending_jobs` but not active → "pending"
  - Not in `pending_jobs` and not active and download was complete → "complete"

No `_drain_results()` call is needed — the refactored `ProcessingManager` uses a real orchestrator thread that mutates `pending_jobs` and `_active_state` directly under `_state_lock`, so the list is always fresh.

**Event hooks needed:**
- `download_queued` (event from `DownloadManager`) → create `PipelineItem`
- `song_downloaded` → set `song_path`, mark download complete
- `download_error` (event from `DownloadManager`) → mark download error
- `processing_complete` (event from `ProcessingManager`) → mark processing complete
- `processing_cancelled` (event from `ProcessingManager`) → remove item, delete song file from library
- `processing_error` (event from `ProcessingManager`) → mark processing error
- `song_deleted` (event from `SongManager`) → remove matching tracker items by `song_path`

**Thread safety:** `threading.Lock` guards the items list. The orchestrator thread, gevent download worker greenlet, and Flask request handlers all touch the tracker. Critical discipline: all I/O operations (file deletion, song_manager calls) happen *outside* the lock to prevent deadlock with gevent polling. Lock is held only for state mutations (set flags, add/remove items).

---

## Files to Create

### 1. `pikaraoke/lib/pipeline_tracker.py`
- `PipelineTracker` class with items list, lock, event subscriptions
- `get_status()` enriches items with live download progress + derived processing status
- `cancel(item_id)` delegates to the appropriate manager based on current state
- `enqueue(item_id)` queues completed song for playback via `queue_manager`
- `remove(item_id)` removes item from tracker list (for completed/errored items)
- `_on_song_deleted(song_path)` removes any tracker item whose `song_path` matches

### 2. `pikaraoke/routes/processing.py`
- Blueprint: `processing_bp = Blueprint("processing", __name__)`
- `GET /processing` — render page template
- `GET /processing/status` — JSON status of all pipeline items
- `POST /processing/<item_id>/cancel` — cancel and clean up
- `POST /processing/<item_id>/enqueue` — queue completed song
- `POST /processing/<item_id>/remove` — remove completed/errored item from tracker

### 3. `pikaraoke/templates/processing.html`
- Extends `base.html`, follows queue.html patterns
- JS polls `/processing/status` every 1s
- Socket events `download_started` / `download_stopped` trigger immediate refresh
- Each row: **title (flex-grow, truncated)** | **icon group (download, separation, action) — tight, right-aligned, fixed-width**
- Icon states via CSS classes: `.step-pending` (grey), `.step-active` (flashing teal), `.step-complete` (solid teal), `.step-error` (solid red)
- Cancel button (`icon-cancel-circled-1`) for in-progress items
- Queue button (`icon-list-add`) for completed items
- Trash button (`icon-trash-empty`) for errored/stale items (calls `/remove`)
- Empty state message when no items
- **Icon legend** in the upper-right of the page header explaining icon/color meanings (download icon, separation icon, pending vs active vs complete vs error states)

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

**Already refactored** — the orchestrator thread + `StemWorker` subprocess architecture is in place, and all cancellation surface the tracker needs already exists:
- `pending_jobs: list[str]` — public, mutated under `_state_lock`
- `cancel_pending(song_path)` — removes from queue, adds to `_cancelled_paths`
- `cancel_active(song_path)` — targets active step (FFmpeg `kill()` or `StemWorker.kill()`)
- `get_active_job() → str | None` — returns current active `song_path`
- Emits `processing_complete` / `processing_error` events

**No further changes required** for the tracker to function. The earlier version of this plan described methods that have since been implemented as part of the orchestrator refactor.

### 6. `pikaraoke/lib/song_manager.py`

Current state: `delete(song_path)` removes the file, companions, SongList entry, and DB row. Does not emit an event.

Changes needed:
- Accept an optional `EventSystem` in `__init__` (or wire via existing mechanism used elsewhere)
- Emit `song_deleted` event with `song_path` at the end of `delete()`
- The `PipelineTracker` subscribes to this event and drops any matching item so the Processing page immediately stops showing deleted songs

If `SongManager` does not already receive `EventSystem`, prefer a direct `events` injection in `karaoke.py` over a global — matches the pattern used by the other managers.

### 7. `pikaraoke/karaoke.py`

Current state: instantiates `DownloadManager` and `ProcessingManager` sequentially near the end of `__init__`. Event wiring (e.g., `song_downloaded → song_manager.register_download`) is done earlier.

Changes needed:
- Import `PipelineTracker`
- If needed, pass `events` to `SongManager` so it can emit `song_deleted`
- Instantiate `PipelineTracker` after both managers are created
- Pass `download_manager`, `processing_manager`, `queue_manager`, `events` to tracker
- Wire tracker event subscriptions

### 8. `pikaraoke/app.py`

Current state: has `_internal_blueprints` list containing `home_bp`, `info_bp`, `splash_bp`, `batch_song_renamer_bp`.

Changes needed:
- Import `processing_bp` from `pikaraoke.routes.processing`
- Add to `_internal_blueprints` list

### 9. `pikaraoke/templates/base.html`

Current state: navbar items are in `.navbar-brand` div. Items: home, queue, search, browse. Nav highlight JS is inline using `currentPath` checks.

Changes needed:
- Add navbar item after browse (before the burger button):
  ```html
  <a id="processing" class="navbar-item" href="{{ url_for('processing.processing') }}">
    <i class="icon icon-cog" title="Processing"></i>
    <span>{% trans %}Processing{% endtrans %}</span>
  </a>
  ```
- Add initial highlight check: `if (currentPath == "/processing") { $("#processing").addClass("is-active") }`

### 10. `pikaraoke/static/spa-navigation.js`

Current state: `updateNavHighlight()` handles `/`, `/queue`, `/search`, `/browse`, `/info`.

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
| Song Title (flex: 1 1 auto, ellipsis)        | [dl] [sep] [action] |
|                                                ^ tight, fixed width, right-aligned
```

Implementation notes:
- Row is a flexbox with `align-items: center`
- Title column: `flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 0.75rem`
- Icon column: `flex: 0 0 auto; display: flex; gap: 0.25rem` — icons sit flush on the right
- `min-width: 0` on the title column is critical: without it, flex items default to `min-width: auto` which lets text expand and push icons off-row

This satisfies the objectives:
- **Title doesn't overflow into the icon area** — icon column is `flex: 0 0 auto`, title uses ellipsis once space runs out
- **Icons tightly spaced on the right** — `gap: 0.25rem` and no surrounding padding beyond the row's own

### Icon Legend (upper-right of page header)

Compact inline legend above the list, right-aligned:
```
[dl icon] Download   [sep icon] Separation   •   grey = pending   teal-pulse = active   teal = complete   red = error
```

- Lives in the page header `<div>`, `float: right` or flexbox `justify-content: space-between` with the page title on the left
- Small text (`is-size-7`), matches Bulma dark theme
- Hidden on narrow viewports (`@media (max-width: 640px) { .legend { display: none } }`) to preserve row space; legend is nice-to-have, not essential

### Icon States (CSS)

- **Pending**: grey (`#666`)
- **Active**: flashing teal (CSS `@keyframes` pulsing between `#666` and `#00d1b2`)
- **Complete**: solid teal (`#00d1b2` — Bulma's primary/teal)
- **Error**: solid red (`#f14668` — Bulma's danger)
- **Cancelling**: flashing amber (`#ffb347`, pulsing between `#666` and `#ffb347`) — shown on the processing icon when cancel is requested during stemming and the worker is finishing up before exit

### Icons

- **Nav bar**: `icon-cog`
- **Download step**: `icon-down-big`
- **Separation step**: `icon-music`
- **Cancel action**: `icon-cancel-circled-1` (red)
- **Queue action**: `icon-list-add` (green)
- **Remove action**: `icon-trash-empty` (grey)

---

## Cancellation & Removal Behavior

| State | User Action | Effect |
|-------|-------------|--------|
| Download pending | Cancel | `download_manager.cancel_pending_download(url)`, remove tracker item |
| Download active | Cancel | `download_manager.cancel_active_download()`, clean up partial files, remove tracker item |
| Processing pending | Cancel | `processing_manager.cancel_pending(song_path)` — flagged, cleaned up when orchestrator picks it up; file deleted from library |
| Processing active | Cancel | `processing_manager.cancel_active(song_path)` sets cancel flag. Orchestrator sees `_CancelledError` after current step completes, runs `_cleanup_stems`, emits `processing_cancelled`. Tracker receives event and deletes song file. During stemming, model stays loaded (delayed cancel). |
| Completed | Enqueue | `queue_manager.add(song_path, user)`, remove tracker item |
| Completed / errored | Remove | Remove tracker item only (file untouched) |
| Song deleted from edit page | (automatic) | `song_deleted` event → tracker drops matching item(s) |

**File cleanup on cancel:**
- Partial downloads: glob `download_path` for files matching the video ID
- Partial stems: `processing_manager._cleanup_stems()` already handles this (deletes `vocal/*---vocal.m4a`, `nonvocal/*---nonvocal.m4a`, and `pikaraoke_stems_*` temp dirs)

---

## Implementation Order

1. **Backend foundation**: modify `download_manager.py` (new events + cancel methods), modify `song_manager.py` (emit `song_deleted`), create `pipeline_tracker.py`
2. **Wiring**: modify `karaoke.py` to instantiate tracker and wire events
3. **API**: create `routes/processing.py`, register blueprint in `app.py`
4. **Frontend**: create `templates/processing.html` with legend + flex row layout, modify `base.html` navbar, modify `spa-navigation.js`

---

## Verification

1. Start PiKaraoke, navigate to Processing page via navbar icon
2. Verify legend appears in upper-right with icon/color key
3. Search and download a song — verify it appears with download icon flashing teal
4. After download completes, verify download icon goes solid teal and separation icon starts flashing
5. After separation completes, verify both icons are solid teal and queue button appears
6. Click queue button — verify song is added to playback queue
7. Download another song and cancel during download — verify partial files are cleaned up
8. Download a song, let it complete, then cancel during separation — verify stems are cleaned up and the worker comes back for the next job
9. Delete a song from the edit page while it is in the tracker — verify it disappears from the Processing page immediately
10. Resize the window / use long titles — verify title truncates with ellipsis and icons stay tight on the right, never overlapping the title
11. Test on mobile viewport — verify responsive layout (legend may hide, row layout remains usable)
12. Run `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
13. Run `python -m pytest` for existing tests
