# User Queue Controls — Review Findings

Reviewer: Code review against actual codebase
Date: 2026-04-24

## Summary

The plan is well-structured and aligns well with the existing codebase patterns. However, several issues ranging from critical bugs to minor gaps were found. Below they are organized by severity.

______________________________________________________________________

## Critical Issues

### 1. `up_next` / `next_user` in `get_now_playing()` reports paused songs

**Location:** `karaoke.py` lines 623–632

The existing `get_now_playing()` method unconditionally reads `queue[0]` for `up_next`:

```python
queue = self.queue_manager.queue
next_song = queue[0] if queue else None
# ...
"up_next": next_song["title"] if next_song else None,
"next_user": next_song["user"] if next_song else None,
```

After the change, `queue[0]` might be a **paused** song. The splash screen and SocketIO `now_playing` payload would then show a paused song as "up next" — confusing and misleading to users.

**Fix:** Change `get_now_playing()` to find the first *non-paused* queue item:

```python
next_song = next((item for item in queue if not item.get("paused", False)), None)
```

### 2. MPV overlay "Up Next" / queue preview shows paused songs

**Location:** `karaoke.py` line 305–308 (the `_get_queue_preview` lambda)

```python
self.playback_controller._get_queue_preview = lambda: tuple(
    QueuedSong(title=item["title"], singer=item["user"])
    for item in self.queue_manager.queue[:5]
)
```

This passes the first 5 queue items (including paused ones) to the MPV OSD overlay. The overlay's `_build_upnext_overlay` and `_build_queue_preview_overlay` render them without any paused indicator. Users on the TV/screen see paused songs listed as "up next."

**Fix:** Filter out paused items from the queue preview:

```python
self.playback_controller._get_queue_preview = lambda: tuple(
    QueuedSong(title=item["title"], singer=item["user"])
    for item in self.queue_manager.queue
    if not item.get("paused", False)
)[:5]
```

### 3. Run loop enters splash delay for a paused song, then `pop_next()` returns `None`

**Location:** `karaoke.py` lines 668–683

The plan changes the outer condition from `len(self.queue_manager.queue) > 0` to `self.queue_manager.has_playable_song()`, which correctly prevents entry when all songs are paused. But there is a **race condition**: between the `has_playable_song()` check and the `pop_next()` call, a user could pause the last playable song. When that happens:

1. `has_playable_song()` returns `True`
2. `reset_now_playing()` is called
3. Splash delay loop runs (up to `splash_delay` seconds)
4. `pop_next()` returns `None` (the song was paused in the meantime)
5. The `if not song: continue` guard (line 682–683) handles this gracefully — **no crash**, but the `reset_now_playing()` call already cleared volume/subtitle-delay state, and the splash delay wasted time.

This isn't a crash bug (the `continue` guard exists), but it is a user-facing glitch: volume/subtitle settings reset unnecessarily, and the splash delay runs for nothing. This is a pre-existing pattern (the song could also be deleted between the check and the pop), but pausing makes it more likely since pausing is a user-initiated action that can happen during the splash delay.

**Mitigation:** Consider moving `reset_now_playing()` to after the `pop_next()` succeeds, or re-checking `has_playable_song()` after the splash delay. This is optional but improves robustness.

______________________________________________________________________

## Significant Issues

### 4. Route uses `json.dumps()` + raw return instead of Flask's `jsonify`

**Location:** Plan's `routes/queue.py` new endpoints (lines 150–173)

The plan's new user endpoints return `json.dumps(...)` with bare dict returns. This is inconsistent with the existing routes which also use `json.dumps()` — so the plan matches existing convention. However, the plan returns raw tuples like:

```python
return json.dumps({"success": False, "error": "Not owner"}), 403
```

This returns a string with a 403 status but **no `Content-Type: application/json` header**. Flask defaults to `text/html; charset=utf-8` for string responses. The existing admin `queue_edit` route (line 176) has the same issue, so the plan is consistent — but both are technically wrong. The frontend `$.post()` with `JSON.parse(resp)` works because jQuery is lenient, but it's fragile.

**Recommendation:** Either use `jsonify()` (proper) or match the existing pattern (consistent but imperfect). At minimum, document this as a known quirk.

### 5. `_verify_ownership` walks the entire queue — potential index mismatch with `_find_song_index`

**Location:** Plan's `routes/queue.py` lines 142–147

The plan introduces `_verify_ownership(queue, song_path, user)` which iterates the queue to find a matching file+user pair. Meanwhile `toggle_pause_song()` uses `_find_song_index(song_path)` which finds by file path only.

If the same song path appears in the queue under different users (currently prevented by `is_song_in_queue()`, which rejects duplicates), there's no issue. But this creates a **hidden coupling**: `_verify_ownership` is correct *only because* `enqueue()` prevents duplicate file paths. If that constraint ever changes, `_verify_ownership` could match the wrong item.

**Recommendation:** Add a comment noting this dependency, or better, have `_verify_ownership` return the queue index so `toggle_pause_song` can use it directly (avoiding a second linear scan).

### 6. Duplicate song paths: `is_song_in_queue()` prevents same song from two users, but `_verify_ownership` doesn't account for it

The plan's design means a user can only pause/delete songs they own, which is checked via `_verify_ownership`. Since `is_song_in_queue()` prevents the same song from being queued by two different users, ownership by path is unambiguous. However, the `toggle_pause_song` method in `queue_manager.py` takes only `song_path` — it doesn't verify ownership at all. The route layer does the ownership check, but the queue manager method has no guard.

This is fine architecturally (route enforces auth, manager is a data layer), but it means any code calling `toggle_pause_song` directly (e.g., tests, future features) bypasses ownership checks. This matches the existing `queue_edit` pattern though.

### 7. Queue numbering in the UI becomes confusing with paused songs interspersed

**Location:** Plan's `queue.html` changes

The plan shows queue rows with sequential numbers (1, 2, 3...) regardless of whether songs are paused. A user sees:

```
1. UserA - Song A [paused]
2. UserB - Song B
3. UserA - Song C
```

Song B is "up next" but has number 2. The numbering reflects queue position (correct) but may confuse users who expect "up next" to always be #1. This is a UX consideration, not a bug — but worth noting.

______________________________________________________________________

## Moderate Issues

### 8. `pop_next()` change is a behavioral break for existing callers

**Location:** Plan's `queue_manager.py` lines 52–63

The current `pop_next()` (line 240–253) always returns `queue[0]` if the queue is non-empty. The plan changes it to skip paused songs, which changes the contract: `pop_next()` can now return `None` even when the queue is non-empty.

Every caller of `pop_next()` must handle this new behavior. The plan addresses the main caller in `karaoke.py`, but any other code calling `pop_next()` could break. A grep shows `pop_next` is only called in `karaoke.py` line 681, so this is safe — but it should be verified after any future refactoring.

**Recommendation:** Update the docstring prominently (the plan does this) and consider renaming to `pop_next_playable()` to make the new contract obvious.

### 9. `queue_edit` "pause" action dispatch is incomplete in the plan

**Location:** Plan's `routes/queue.py` lines 119–132

The plan shows adding `pause` to `success_labels` and `error_labels`, and a new `elif action == "pause"` branch. However, the existing code structure (lines 157–162) uses:

```python
if action == "top":
    success = k.queue_manager.move_to_top(song)
elif action == "bottom":
    success = k.queue_manager.move_to_bottom(song)
else:
    success = k.queue_manager.queue_edit(song, action)
```

The plan's `elif action == "pause"` branch needs to go **before** the `else` catch-all, otherwise "pause" falls into `queue_edit()` which doesn't handle "pause" and returns `False` with "Unrecognized action." The plan shows this correctly in isolation but the integration point is subtle.

**Recommendation:** Explicitly note that the `elif action == "pause"` must be inserted **before** the existing `else` branch, and that `queue_edit()` itself should not need modification.

### 10. `queue.html` column span logic for empty queue message

**Location:** Plan's `queue.html` section

The existing code at line 326 computes `colSpan`:

```javascript
var colSpan = isAdmin ? 4 : 2;
```

The plan adds a third case: non-admin with cookie = 3 columns. The update should be:

```javascript
var colSpan = isAdmin ? 4 : (currentUser ? 3 : 2);
```

The plan mentions this in the table (Section 4) but doesn't show the explicit JavaScript for `colSpan` computation in the `generateHTML` function. This is easy to miss during implementation.

### 11. `generateNowPlayingRow()` needs the options column for non-admins too

The plan says to update `generateNowPlayingRow()` to emit an options cell for non-admins, but doesn't show the code for it. For the now-playing row, there's no "pause queue item" action (the plan explicitly scopes out pausing the currently-playing song), so the only user action on now-playing would be... nothing? The now-playing row shouldn't get a user options gear. But the plan's column layout says non-admin-with-cookie gets 3 columns, and the now-playing row currently has 2 columns (non-admin) or 4 columns (admin). Adding a blank third column to the now-playing row for non-admins with cookies is needed for alignment but isn't shown in the plan.

______________________________________________________________________

## Minor Issues

### 12. `UserQueueActionForm` is defined inside `routes/queue.py` but the plan's indentation implies it's at module level

**Location:** Plan's `routes/queue.py` lines 137–139

The plan shows `UserQueueActionForm(Schema)` at the bottom of the file. This is fine — it's module-level like the other form classes. No issue, just confirming placement.

### 13. Jinja template strings inside JavaScript — i18n may not work as expected

**Location:** Plan's `queue.html` lines 275–277

```javascript
$('#user-opt-pause-label').text(paused
    ? "{{ _("I'm back (unpause)") }}"
    : "{{ _("Pause (I'll be right back)") }}");
```

This works because Jinja renders at template-build time, producing hardcoded JavaScript strings. However, this means the pause/unpause labels are baked in at page load and won't change if the user switches language without a page reload. This is the same pattern used elsewhere in the template, so it's consistent.

### 14. The `data-paused` attribute on the gear button needs to update on socket refresh

When a user pauses their song, the `queue_update` socket event triggers `queuePage_getQueue()`, which re-renders the table. The new HTML from `generateQueueRow()` reads `e.paused` from the queue data, so `data-paused` will be correct after refresh. No issue here — the plan handles this correctly through the existing refresh mechanism.

### 15. CSS `.row-paused` opacity affects the gear icon, making it hard to click

The plan's CSS:

```css
.row-paused td { opacity: 0.5; }
.row-paused .tag { opacity: 1; }
```

The options column's gear icon will be at 0.5 opacity, which makes it harder to see and click. The user needs to click that gear to unpause their song — a catch-22 if it's too faded to notice.

**Recommendation:** Also restore opacity on the options cell:

```css
.row-paused .queue-song-user-btn { opacity: 1; }
```

### 16. `_find_song_index` uses exact path match — URL-encoded paths from the frontend

The frontend sends `song: window.currentUserSong.file` which is the raw file path (not URL-encoded) since `data-file` was stored via `escape()` (which is `encodeURIComponent`) and decoded via `decodeURIComponent($btn.data('file'))`. This is handled correctly in the plan's click handler. No issue.

### 17. `toggle_pause_song` emits `now_playing_update` but `queue_edit` for "delete" also does

The plan's `toggle_pause_song` emits both `queue_update` and `now_playing_update`, which is consistent with the existing pattern (delete, reorder, etc. all emit both). This is correct — the "up next" display depends on `now_playing_update`.

### 18. Admin modal: the plan adds a pause option but doesn't show updating `openSongOptions()`

The plan says "Update `openSongOptions()` to set the pause label based on the song's current paused state (read from the button's `data-paused` attribute)" but doesn't provide the code. The existing `openSongOptions()` (lines 384–408) stores `index`, `file`, `title` — it needs to also store `paused` and update the label. This is straightforward but should be explicit.

### 19. The `executeQueueAction` for the admin "pause" action reuses the existing GET-based endpoint

The admin modal calls `executeQueueAction('pause')` which builds a URL: `/queue/edit?song=...&action=pause`. This hits the existing `queue_edit` GET endpoint. Since "pause" is a state-changing operation, using GET is semantically incorrect (idempotency), but it matches the existing pattern for all other queue edit actions (up, down, top, bottom, delete). Consistent, if imperfect.

______________________________________________________________________

## Missing from the Plan

### 20. Queue reorder/drag-and-drop over paused songs

The plan doesn't address what happens when an admin drags a song past paused songs. Currently, `Sortable.create()` uses DOM index positions which map to queue array indices. Paused songs remain in the array, so drag-and-drop should work correctly — paused songs are just rows with reduced opacity. No code change needed, but this should be tested (it's in the test plan implicitly).

### 21. `queue_clear()` behavior with paused songs

If an admin clears the queue, all songs (paused or not) are removed. `queue_clear()` sets `self.queue = []`, which naturally clears the paused flag. No issue.

### 22. `queue_add_random()` — should random songs start as paused?

No — they should start as `paused: False` like any other enqueue. The plan's `enqueue()` change adds `"paused": False` to the item dict, so `queue_add_random()` which calls `self.enqueue()` will automatically get the right default. Correct.

### 23. The `/get_queue` endpoint now returns `paused` field — existing API contract test

The test in `test_queue_routes.py` line 78–102 (`test_get_queue_returns_required_fields`) checks for `user`, `file`, `title`, `semitones` but not `paused`. After the change, the API will return `paused: false` on every item. This is additive (new field), so existing consumers won't break. But the API contract test should be updated to assert the new field.

### 24. SocketIO `now_playing` payload: `up_next`/`next_user` should skip paused items

Related to issue #1 — the `now_playing` SocketIO event payload includes `up_next` and `next_user` derived from `get_now_playing()`. If that method is fixed (issue #1), the socket payload is also fixed. The test `test_update_now_playing_socket_includes_up_next` should be updated to verify that paused songs are skipped.

### 25. No notification emitted when a song is paused/unpaused

The existing `toggle_pause_song` emits `queue_update` and `now_playing_update` (for UI refresh) but does **not** emit a `notification` event. Other user-facing actions like enqueue, delete, and clear all emit notifications. Consider adding one like `"UserA paused Song X"` or `"UserA unpaused Song X"` so other users on the queue page see what happened.

______________________________________________________________________

## Verdict

The plan is implementable with the issues above addressed. The **three critical issues** (#1, #2, #3) must be fixed before or during implementation — they affect the splash screen, MPV overlay, and run loop correctness. The **significant issues** (#4–#7) should be addressed for correctness and maintainability. The **moderate issues** (#8–#11) are integration details that are easy to miss during implementation.
