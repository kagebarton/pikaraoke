# User Processing Controls: Self-Cancel and Self-Remove

Model: Claude Opus 4.7

## Context

The processing page (`/processing`) shows every song moving through the download + stem-separation pipeline. Currently:

- **Visibility**: everyone sees every row's progress. No change needed.
- **Enqueue**: everyone can queue any completed song via the green queue icon. No change needed.
- **Cancel / Remove**: the buttons are rendered for every row regardless of who submitted it, and the backend endpoints have no auth at all — anyone can cancel or remove any song.

This plan scopes cancel/remove to the submitting user (with admins retaining full control), mirroring the ownership pattern from `plans/user-queue-controls.md`.

Pipeline items already carry a `user` field: set by `PipelineItem.__init__` ([pipeline_tracker.py:42](pikaraoke/lib/pipeline_tracker.py#L42)) and emitted in the status JSON by `_item_to_dict` ([pipeline_tracker.py:294](pikaraoke/lib/pipeline_tracker.py#L294)). No tracker changes are needed.

## Design Decisions

- **User identity = cookie string.** Same model as the queue plan. Acceptable for a home karaoke system.
- **Admins keep existing behavior.** Admins can cancel or remove any item via the current endpoints. The UI shows buttons for every row when `isAdmin` is true.
- **Non-admins see cancel only for rows they own.** Rendered based on `item.user === currentUser`. Rows from other users render a blank action cell (queue cell still renders if the song is complete).
- **Remove (delete) is admin-only.** Once a song finishes processing the remove button is only shown to admins, matching the edit-song page. Non-admins have no path to delete a completed item.
- **Everyone can still enqueue any completed song.** The `/processing/<item_id>/enqueue` endpoint and its queue button stay open. Explicit per user requirement.
- **Existing admin cancel/remove endpoints get gated with `is_admin()`.** Currently they have no auth — tightening matches the queue design.
- **One new user endpoint for cancel only.** Takes `item_id` and `user` in the POST body. Ownership is verified against `PipelineTracker._find_item(item_id).user`. No user remove endpoint is added.
- **No new modal.** The processing page uses inline action buttons, not a modal. The ownership gate is a single guard at the top of `cancelCell()`.

## Key Files

| File | Role |
|------|------|
| [pikaraoke/lib/pipeline_tracker.py](pikaraoke/lib/pipeline_tracker.py) | Pipeline item model (already has `user` field) |
| [pikaraoke/routes/processing.py](pikaraoke/routes/processing.py) | Flask endpoints for processing operations |
| [pikaraoke/templates/processing.html](pikaraoke/templates/processing.html) | Processing UI, polling, action buttons |
| [pikaraoke/templates/base.html](pikaraoke/templates/base.html) | `getUserCookie()` helper (already exists) |

## Implementation

### 1. `pipeline_tracker.py`

Add a small helper so route code doesn't reach through `_find_item` (private) and doesn't need to take the lock itself:

```python
def get_item_user(self, item_id: str) -> str | None:
    """Return the user who submitted a pipeline item, or None if not found."""
    with self._lock:
        item = self._find_item(item_id)
        return item.user if item else None
```

This is the only change to the tracker. No data model change — `user` is already there.

### 2. `routes/processing.py`

**Imports** — add `request`, `is_admin`, and `_` (for error messages if desired):

```python
from flask import render_template, request
from pikaraoke.lib.current_app import get_karaoke_instance, is_admin
```

**Pass `admin` to the template** (around [line 22-28](pikaraoke/routes/processing.py#L22-L28)):

```python
@processing_bp.route("/processing")
def processing():
    """Processing pipeline monitoring page."""
    k = get_karaoke_instance()
    return render_template(
        "processing.html",
        site_title=getattr(k, "preferences", None)
        and k.preferences.get("site_name")
        or "PiKaraoke",
        title="Processing",
        admin=is_admin(),
    )
```

**Gate the existing cancel/remove endpoints with `is_admin()`** (around [line 39-60](pikaraoke/routes/processing.py#L39-L60)):

```python
@processing_bp.route("/processing/<item_id>/cancel", methods=["POST"])
def cancel_item(item_id):
    """Cancel an in-progress download or processing job (admin only)."""
    if not is_admin():
        return json.dumps({"success": False, "error": "Admin only"}), 403
    k = get_karaoke_instance()
    success = k.pipeline_tracker.cancel(item_id)
    return json.dumps({"success": success})


@processing_bp.route("/processing/<item_id>/remove", methods=["POST"])
def remove_item(item_id):
    """Remove a completed or errored item from the tracker (admin only)."""
    if not is_admin():
        return json.dumps({"success": False, "error": "Admin only"}), 403
    k = get_karaoke_instance()
    success = k.pipeline_tracker.remove(item_id)
    return json.dumps({"success": success})
```

`/processing/<item_id>/enqueue` stays open — everyone can queue completed songs.

**Add one new user endpoint** at the bottom of the file:

```python
@processing_bp.route("/processing/user/cancel", methods=["POST"])
def user_cancel_item():
    """Let a user cancel their own pipeline item."""
    k = get_karaoke_instance()
    item_id = request.form.get("id", "")
    user = request.form.get("user", "")
    owner = k.pipeline_tracker.get_item_user(item_id)
    if owner is None or owner != user:
        return json.dumps({"success": False, "error": "Not owner"}), 403
    success = k.pipeline_tracker.cancel(item_id)
    return json.dumps({"success": success})
```

No user remove endpoint — remove stays admin-only. Kept as raw `request.form` lookups to match the style of the existing processing routes.

### 3. `processing.html`

**Emit `isAdmin` and read `currentUser`** at the top of the IIFE (just after `'use strict';` around [line 41](pikaraoke/templates/processing.html#L41)):

```javascript
var isAdmin = {{ admin | tojson }};
var currentUser = (typeof getUserCookie === 'function') ? getUserCookie() : null;
```

**Gate `cancelCell()`** — the function renders both the cancel button (for in-progress items) and the remove button (for completed/errored items). Split the logic so the remove button is admin-only and the cancel button is owner-or-admin (around [line 85](pikaraoke/templates/processing.html#L85)):

```javascript
function cancelCell(item) {
    // No action while cancelling is in progress
    if (item.processing_status === 'cancelling') return '';

    var isOwner = currentUser && item.user === currentUser;

    // Remove button: admin only (matches edit-song page behaviour)
    if (item.processing_status === 'complete' || item.processing_status === 'error') {
        if (!isAdmin) return '';
        // ... render remove button unchanged
    }

    // Cancel button: owner or admin only
    if (!isAdmin && !isOwner) return '';
    // ... rest of existing cancel-button rendering unchanged
}
```

`queueCell()` is deliberately not gated — anyone can queue any completed song.

**Branch the cancel AJAX endpoint on `isAdmin`** in the cancel click handler (around [line 256-276](pikaraoke/templates/processing.html#L256-L276)):

```javascript
$(document).on('click.processing', '.pipeline-cancel-btn', function(e) {
    e.preventDefault();
    var id = $(this).data('id');
    var $row = $('tr[data-id="' + id + '"]');
    var title = $row.find('.is-truncated').text();
    var msg = (window.i18n && window.i18n.confirmCancelPipeline)
      ? window.i18n.confirmCancelPipeline.replace('SONG_TITLE', title)
      : 'Are you sure you want to cancel "' + title + '"?';
    if (!window.confirm(msg)) return;

    var procStatus = $row.attr('data-proc-status');
    var ajaxOpts = isAdmin
      ? {
          url: '{{ url_for("processing.cancel_item", item_id="ITEM_ID") }}'.replace('ITEM_ID', id),
          type: 'POST'
        }
      : {
          url: '{{ url_for("processing.user_cancel_item") }}',
          type: 'POST',
          data: { id: id, user: currentUser }
        };
    $.ajax(ajaxOpts).done(function() {
      if (procStatus !== 'active') {
        fadeAndRemove($row);
      }
      fetchStatus();
    });
});
```

**`removeItem()` is unchanged** — it already calls the admin-only `/processing/<id>/remove` endpoint. Since non-admins never see the remove button, no branching is needed here.

`enqueueItem()` is not changed — the enqueue endpoint stays open to everyone.

### 4. Tests

- **`test_processing_routes.py`** (create if absent, or extend existing route tests):
  - Non-admin without matching user cookie gets 403 on `/processing/user/cancel`.
  - Non-admin with matching user cookie successfully cancels their own item via `/processing/user/cancel`.
  - Non-admin hitting the admin `/processing/<id>/cancel` or `/processing/<id>/remove` gets 403.
  - Non-admin can still POST `/processing/<id>/enqueue` (stays open).
  - `get_item_user()` returns the user for a known item and `None` for unknown.

No mocks for the tracker itself — existing tests use real `EventSystem` and `PreferenceManager` per CLAUDE.md.

## Test Plan

- [ ] As User A, submit a YouTube URL. Verify cancel button appears on A's row. As User B (different cookie), verify cancel button does NOT appear on A's row.
- [ ] As User A, cancel A's own item during download. Verify cancellation works, row disappears.
- [ ] As User A, cancel A's own item during separation. Verify cancelling spinner shows, row eventually disappears.
- [ ] As User A, attempt to cancel User B's item via direct POST to `/processing/user/cancel` with `id=<B's item>&user=<A's name>`. Verify 403.
- [ ] As User A, attempt to hit admin endpoint `/processing/<B's item>/cancel`. Verify 403.
- [ ] As User A with a completed item, verify NO remove button appears (remove is admin-only).
- [ ] As admin, cancel/remove any user's item. Verify both work.
- [ ] As admin with a completed item, verify remove button appears and works.
- [ ] As any non-admin user, verify queue button appears on completed songs submitted by OTHERS and successfully queues them.
- [ ] Refresh the page with a pending download. Verify ownership gating survives refresh (data comes from the polled status, not client-side).
- [ ] User without a cookie (never named themselves): verify cancel buttons are absent from all rows, queue button still works.

## Out of Scope

- Per-user filtering of the list (everyone sees everything, by design).
- Editing pipeline item metadata (title, URL) after submission.
- Retrying errored items — existing flow is remove + resubmit.
- Reassigning ownership (changing cookie mid-pipeline). The user field is frozen at `_on_download_queued` time.
