# User Queue Controls: Self-Delete and Self-Pause

Model: Claude Opus 4.7

## Context

Currently, users who queue songs have no control over them after submission — only admins can delete, reorder, or skip queued songs. This plan adds two self-service controls:

1. **Delete own song** — a user can remove their own queued song
2. **Pause own song** — a user can temporarily mark their queued song as paused (step-away mode); playback skips paused songs and plays the next non-paused song instead. If *all* remaining songs are paused, playback idles until one is unpaused.

The username is already stored in a `"user"` cookie via `js.cookie` and is retrievable client-side via `getUserCookie()` (defined in [base.html](pikaraoke/templates/base.html#L82-L102)). That same string is what's stored in each queue item's `user` field. No session/auth layer is introduced.

## Design Decisions

- **User identity = cookie string.** Anyone setting the same cookie value can act as that user. Acceptable for a home karaoke system.
- **Admins can do anything.** Admins see pause/unpause alongside their existing controls and can act on any user's song. Non-admins can only act on their own songs.
- **Paused songs keep their queue position.** Pausing is a flag on the existing queue item, not a removal. Fair queue math is unaffected (it runs at insertion time).
- **Paused songs count toward `limit_user_songs_by`.** They still hold a slot.
- **If the next song is paused, playback skips to the next non-paused song.** The only time playback idles is when *every* remaining queued song is paused — a fringe case the user won't hit in practice.
- **Fair queue interaction:** insertion-time logic is unchanged. When a user unpauses, their song plays at its existing position — no re-queuing.

## Key Files

| File | Role |
|------|------|
| [pikaraoke/lib/queue_manager.py](pikaraoke/lib/queue_manager.py) | Queue data model, fair queue, pop/edit/delete |
| [pikaraoke/karaoke.py](pikaraoke/karaoke.py) | Main run loop — where the next song is pulled |
| [pikaraoke/routes/queue.py](pikaraoke/routes/queue.py) | Flask endpoints for queue operations |
| [pikaraoke/templates/queue.html](pikaraoke/templates/queue.html) | Queue UI, modals, socket-driven refresh |
| [pikaraoke/templates/base.html](pikaraoke/templates/base.html) | `getUserCookie()` helper (already exists) |

## Implementation

### 1. `queue_manager.py`

**Add `"paused"` field to queue items** in `enqueue()` (around [line 122-127](pikaraoke/lib/queue_manager.py#L122-L127)):

```python
queue_item = {
    "user": user,
    "file": song_path,
    "title": title,
    "semitones": semitones,
    "paused": False,
}
```

**Modify `pop_next()`** (around [line 240-253](pikaraoke/lib/queue_manager.py#L240-L253)) to skip paused songs:

```python
def pop_next(self) -> dict[str, Any] | None:
    """Remove and return the next non-paused song from the queue.

    Skips over paused songs (they remain in queue in place). Returns None
    if the queue is empty or all remaining songs are paused.
    """
    for idx, item in enumerate(self.queue):
        if not item.get("paused", False):
            song = self.queue.pop(idx)
            logging.info(f"Popped song from queue: {song['title']}")
            return song
    return None
```

**Add `has_playable_song()`:**

```python
def has_playable_song(self) -> bool:
    """True if the queue has at least one non-paused song."""
    return any(not item.get("paused", False) for item in self.queue)
```

**Add `toggle_pause_song(song_path)`** — caller is responsible for authorization. Emits a user-facing notification so other clients see what happened:

```python
def toggle_pause_song(self, song_path: str) -> bool:
    """Toggle the paused flag on a queued song. Returns False if not found."""
    index = self._find_song_index(song_path)
    if index == -1:
        logging.error("Song not found in queue: " + song_path)
        return False
    item = self.queue[index]
    item["paused"] = not item.get("paused", False)
    state = "paused" if item["paused"] else "unpaused"
    logging.info(f"Song {state}: {song_path}")
    # MSG: Shown when a user pauses/unpauses their queued song
    msg = (
        _("%s paused: %s") % (item["user"], item["title"])
        if item["paused"]
        else _("%s unpaused: %s") % (item["user"], item["title"])
    )
    self._events.emit("notification", msg, "info")
    self._events.emit("queue_update")
    self._events.emit("now_playing_update")
    return True
```

**Note:** `is_user_limited()` already counts all queue items by user — no change needed; paused songs count toward the limit automatically.

### 2. `karaoke.py`

**Run loop condition** ([line 668-671](pikaraoke/karaoke.py#L668-L671)), change from:

```python
if (
    len(self.queue_manager.queue) > 0
    and not self.playback_controller.is_playing
):
```

to:

```python
if (
    self.queue_manager.has_playable_song()
    and not self.playback_controller.is_playing
):
```

This prevents the loop from spinning (calling `pop_next()` repeatedly and getting `None`) when every queued song is paused. When the queue is all-paused, the loop falls through to `handle_run_loop()` and sleeps 500ms per tick.

The existing `if not song: continue` guard at [line 682-683](pikaraoke/karaoke.py#L682-L683) already handles the race where the last playable song is paused during the splash delay — no crash, just a wasted splash cycle. Acceptable as-is.

**`get_now_playing()` must skip paused songs** ([line 623-624](pikaraoke/karaoke.py#L623-L624)). Otherwise `up_next`/`next_user` in the splash screen and `now_playing` SocketIO payload will announce a paused song. Change:

```python
queue = self.queue_manager.queue
next_song = queue[0] if queue else None
```

to:

```python
queue = self.queue_manager.queue
next_song = next((item for item in queue if not item.get("paused", False)), None)
```

**MPV overlay queue preview must skip paused songs** ([line 305-308](pikaraoke/karaoke.py#L305-L308)). The on-TV OSD overlay renders `_get_queue_preview` without any paused indicator, so paused songs would appear as "up next" on the TV. Change:

```python
self.playback_controller._get_queue_preview = lambda: tuple(
    QueuedSong(title=item["title"], singer=item["user"])
    for item in self.queue_manager.queue[:5]
)
```

to:

```python
self.playback_controller._get_queue_preview = lambda: tuple(
    QueuedSong(title=item["title"], singer=item["user"])
    for item in self.queue_manager.queue
    if not item.get("paused", False)
)[:5]
```

### 3. `routes/queue.py`

**Add `"pause"` action to existing admin `queue_edit`** (around [line 142-162](pikaraoke/routes/queue.py#L142-L162)). Add labels and a branch:

```python
success_labels = {
    ...
    "pause": _("Toggled pause on queue item"),
}
error_labels = {
    ...
    "pause": _("Error toggling pause"),
}

# In the action dispatch at line 157-162, insert BEFORE the final `else`:
elif action == "pause":
    success = k.queue_manager.toggle_pause_song(song)
```

**Important:** The existing dispatch has an `else` catch-all that routes unknown actions to `queue_edit(song, action)`. The `elif action == "pause"` branch must be inserted **before** that `else` — otherwise `"pause"` falls into `queue_edit()`, which will return `False` with "Unrecognized action." `queue_edit()` itself does not need modification.

**Add two new non-admin endpoints** at the bottom of the file:

```python
class UserQueueActionForm(Schema):
    song = fields.String(required=True)
    user = fields.String(required=True)


def _verify_ownership(queue, song_path, user):
    """Return True if `user` owns the queue item matching `song_path`."""
    for item in queue:
        if item["file"] == song_path:
            return item["user"] == user
    return False


@queue_bp.route("/queue/user/delete", methods=["POST"])
@queue_bp.arguments(UserQueueActionForm, location="form")
def user_delete(form):
    """Let a user delete their own queued song."""
    k = get_karaoke_instance()
    song = form["song"]
    user = form["user"]
    if not _verify_ownership(k.queue_manager.queue, song, user):
        return json.dumps({"success": False, "error": "Not owner"}), 403
    success = k.queue_manager.queue_edit(song, "delete")
    return json.dumps({"success": success})


@queue_bp.route("/queue/user/pause", methods=["POST"])
@queue_bp.arguments(UserQueueActionForm, location="form")
def user_pause(form):
    """Let a user toggle pause on their own queued song."""
    k = get_karaoke_instance()
    song = form["song"]
    user = form["user"]
    if not _verify_ownership(k.queue_manager.queue, song, user):
        return json.dumps({"success": False, "error": "Not owner"}), 403
    success = k.queue_manager.toggle_pause_song(song)
    return json.dumps({"success": success})
```

### 4. `queue.html`

**Read current user at the top of the script block** (after `isAdmin`):

```javascript
var currentUser = (typeof getUserCookie === 'function') ? getUserCookie() : null;
```

**Column layout:**

| Mode | Columns | colSpan for empty message |
|------|---------|--------------------------|
| Admin | number, drag, song, options | 4 |
| Non-admin with cookie | number, song, options | 3 |
| Non-admin without cookie | number, song | 2 |

Update `generateNowPlayingRow()` and `generateQueueRow()` to emit an options cell for non-admins when `currentUser` is set. The cell is empty for rows the user doesn't own; populated with a gear icon for rows they own. Update the empty-queue colspan accordingly.

**`generateQueueRow()` — owner-only options + paused styling:**

```javascript
function generateQueueRow(e, index) {
    var isPaused = !!e.paused;
    var rowClass = isPaused ? ' class="row-paused"' : '';
    var html = '<tr data-index="' + index + '"' + rowClass + '>';
    html += '<td style="width: ' + COL_WIDTH.number + '; ...">' + (index + 1) + '</td>';

    if (isAdmin) {
        html += '<td class="drag-handle" ...><i class="icon icon-braille ..."></i></td>';
    }

    html += '<td style="...">';
    html += '<div class="is-flex ...">';
    html += '<span class="has-text-success">' + e.user + '</span>';
    html += '<span class="is-hidden-mobile has-text-grey mx-2">&bull;</span>';
    html += '<span class="has-text-weight-bold is-hidden-mobile">' + e.title + '</span>';
    html += '<span class="is-size-7 has-text-weight-bold is-hidden-tablet" style="width: 100%;">' + e.title + '</span>';
    if (isPaused) {
        html += '<span class="tag is-warning is-light ml-2">{{ _("paused") }}</span>';
    }
    html += '</div></td>';

    // Options column: admin gets it always; non-admin gets it if they have a cookie
    if (isAdmin) {
        html += '<td style="..."><a class="... queue-song-options-btn" data-index="' + index + '" data-file="' + escape(e.file) + '" data-title="' + escape(e.title) + '" data-paused="' + (isPaused ? '1' : '0') + '" title="{{ _("Options") }}"><i class="icon-cog is-size-5"></i></a></td>';
    } else if (currentUser) {
        if (e.user === currentUser) {
            html += '<td style="..."><a class="... queue-song-user-btn" data-file="' + escape(e.file) + '" data-title="' + escape(e.title) + '" data-paused="' + (isPaused ? '1' : '0') + '" title="{{ _("Options") }}"><i class="icon-cog is-size-5"></i></a></td>';
        } else {
            html += '<td style="width: ' + COL_WIDTH.options + ';"></td>';
        }
    }

    html += '</tr>';
    return html;
}
```

**CSS for paused rows** (add to `<style>` or `custom.css`):

```css
.row-paused td { opacity: 0.5; }
.row-paused .tag { opacity: 1; }  /* keep the badge readable */
.row-paused .queue-song-user-btn,
.row-paused .queue-song-options-btn { opacity: 1; }  /* keep gear clickable — it's how the user unpauses */
```

**Add a new user options modal** next to the existing one:

```html
<div class="modal" id="user-song-options-modal">
  <div class="modal-background"></div>
  <div class="modal-card" style="width: 90%; max-width: 400px;">
    <header class="modal-card-head" style="padding: 15px;">
      <p class="modal-card-title is-size-6" id="user-modal-song-title" style="max-width: 95%">{{ _('Your Song') }}</p>
      <button class="delete" aria-label="close" onclick="closeUserSongOptions()"></button>
    </header>
    <section class="modal-card-body" style="padding: 0;">
        <a id="user-opt-pause" class="panel-block py-3" href="#" onclick="executeUserAction('pause'); return false;">
            <span class="icon mr-2"><i class="icon-pause"></i></span>
            <span id="user-opt-pause-label">{% trans %}Pause (I'll be right back){% endtrans %}</span>
        </a>
        <a class="panel-block py-3 has-text-danger" href="#" onclick="executeUserAction('delete'); return false;">
            <span class="icon mr-2"><i class="icon-trash-empty"></i></span>
            {% trans %}Remove from Queue{% endtrans %}
        </a>
    </section>
  </div>
</div>
```

Wrap the modal in a `{% if not admin %}` block (or always render — admins won't trigger it since the user-btn class is only emitted for non-admin rows).

**JS handlers:**

```javascript
window.currentUserSong = { file: '', title: '', paused: false };

window.openUserSongOptions = function(file, title, paused) {
    window.currentUserSong = { file: file, title: title, paused: paused };
    $('#user-modal-song-title').text(title);
    $('#user-opt-pause-label').text(paused
        ? "{{ _("I'm back (unpause)") }}"
        : "{{ _("Pause (I'll be right back)") }}");
    $('#user-song-options-modal').addClass('is-active');
};

window.closeUserSongOptions = function() {
    $('#user-song-options-modal').removeClass('is-active');
};

window.executeUserAction = function(action) {
    var endpoint = action === 'delete' ? '/queue/user/delete' : '/queue/user/pause';
    $.post(endpoint, {
        song: window.currentUserSong.file,
        user: currentUser
    }).done(function(resp) {
        var result = JSON.parse(resp);
        if (!result.success) console.error('User queue action failed:', result.error);
    }).fail(function(xhr) {
        console.error('User queue action request failed', xhr.status);
    });
    window.closeUserSongOptions();
};
```

**Click handler** (inside the existing `$(document).on('click.queue', ...)` block):

```javascript
$(document).on('click.queue', '.queue-song-user-btn', function(e) {
    e.preventDefault();
    var $btn = $(this);
    var file = decodeURIComponent($btn.data('file'));
    var title = decodeURIComponent($btn.data('title'));
    var paused = $btn.data('paused') === '1' || $btn.data('paused') === 1;
    openUserSongOptions(file, title, paused);
});

// Close modal on background click (extend existing handler)
$('.modal-background').click(function() {
    window.closeSongOptions();
    window.closeNowPlayingOptions();
    window.closeUserSongOptions();
});
```

**Admin modal: add pause option** to the existing `#song-options-modal` body:

```html
<a id="opt-pause" class="panel-block py-3" href="#" onclick="executeQueueAction('pause'); return false;">
    <span class="icon mr-2"><i class="icon-pause"></i></span>
    <span id="opt-pause-label">{% trans %}Pause{% endtrans %}</span>
</a>
```

Update `openSongOptions()` to set the pause label based on the song's current paused state (read from the button's `data-paused` attribute).

### 5. Tests

- **`test_queue_manager.py`**: cover `pop_next()` skipping paused songs, `has_playable_song()` reporting correctly, `toggle_pause_song()` flipping state and emitting `queue_update`, `now_playing_update`, and `notification` events, and enqueue initializing `paused: False`.
- **`test_queue_socketio.py`**: verify `queue_update` fires on pause toggle.
- **`test_queue_routes.py`**: update `test_get_queue_returns_required_fields` to assert the new `paused` field is present on every item. Add coverage for the new `/queue/user/delete` and `/queue/user/pause` endpoints — success path and 403-on-wrong-owner.
- **Update `test_update_now_playing_socket_includes_up_next`** (or add a new test): verify `up_next`/`next_user` skip paused songs — if `queue[0]` is paused, the payload should name `queue[1]`.

No mocks for the queue itself — the existing tests use real `EventSystem` and `PreferenceManager` instances, per CLAUDE.md.

## Test Plan

- [ ] Queue two songs as User A, two as User B. Pause User A's first song. Verify playback plays them in order: A2, B1, B2 (A1 skipped).
- [ ] Unpause A's first song. Verify it plays next when the current song ends.
- [ ] Pause every song in the queue. Verify nothing plays (splash/idle).
- [ ] Unpause one song. Verify it starts playing within one loop tick (~500ms + splash delay).
- [ ] As User A, attempt to pause User B's song via direct POST. Verify 403.
- [ ] As admin, pause/unpause any user's song via the admin modal. Verify it works.
- [ ] Verify `limit_user_songs_by` treats paused songs as counted (set limit to 2, queue 2 songs, pause one, try to queue a third — should be rejected).
- [ ] Verify fair queue: User A queues songs 1, 2, pauses song 1. User B queues song 1. Expected order after B queues: A1(paused), B1, A2. Unpausing A1 doesn't reorder.
- [ ] Mobile layout: paused tag displays correctly on narrow screens.
- [ ] Refresh the page mid-pause. Verify paused state persists (comes from queue state, not client-side).

## Out of Scope

- Persistence across restarts (the queue itself isn't persisted today).
- Pausing the currently-playing song (that's what the existing playback pause is for).
- User-initiated reorder (users can't move songs, only delete/pause).
- Timeout auto-unpause (e.g., "auto-unpause after 10 minutes").
