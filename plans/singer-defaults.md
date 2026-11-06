Model: Claude Opus 5.5 (author, 2026-11-06). Executor: Claude Sonnet 5.5.

# Singer defaults: key and vocal volume per guest

## Goal

When a guest joins, they're asked for their name, their vocal volume and their key. Every song
they sing starts at those values with nobody touching the Now Playing controls. Clicking their
name in the top bar opens the same form to change any of the three. Everything is forgotten
when the app stops, so the next party starts clean.

Base: `dev` at `4497f4d`. Branch `singer_defaults` (made by the author, 2026-11-06).

## Rulings (Ken, 2026-11-06)

1. **Stored on the server, by name.** One lookup when a song starts covers every way a song
   enters the queue.
2. **Read when the song starts.** Changing your settings also changes songs you've already
   queued.
3. **One key for every song.** No per-song memory (a possible follow-up).
4. **Now Playing controls apply to the current song only**, as today. They never change
   anyone's saved settings.
5. **One form for joining**: name, a vocal volume slider starting at the house default (Info
   page, 40%), and a key control starting at 0. It replaces the browser name prompt and shows
   the first time a phone opens any page.
6. **A session is one run of the app.** Names and settings live in memory only and clear when
   the app stops. A phone that joined in an earlier run is asked again. Returning guests type
   their name again each party, as intended.
7. **Names are unique within a session.** The form refuses a name already in use (Ken chose
   this over sharing, and over two guests with the same name: two people's songs merging is
   worse than one person having two names). The same person on a second phone joins as a
   second guest.
8. **Renaming moves your songs** (queued, held for a download or processing, and the one
   playing now) to the new name. Renaming to a name already in use is refused.
9. **Clicking your name opens the same form** with your current values. It replaces the
   rename prompt.
10. **Self-service only.** No admin list of guests.
11. **The form's key range is -3 to +3**, because the distortion is pronounced beyond that.
    The Now Playing slider stays at -12 to +12 (see Follow-ups).

Assumptions stated to Ken on 2026-11-06, not objected to:

- Songs from the Randomizer, or from a name with no saved settings, use the house defaults.
- The form always saves both values as shown. If the admin changes the house vocal volume
  mid-party, guests who already joined keep what they saved.
- A blank name becomes `Anon-XXXX`, as today, with whatever settings were picked.
- Vocal volume 0-100%, like the Info page. The key field is hidden when pitch shifting isn't
  available. Vocal volume does nothing on songs without separated stems.
- Guests can't take the names the app uses itself, `Pikaraoke` and `Randomizer`.

## What the code does today (read 2026-11-06 at `4497f4d`)

- **A guest is a name in a cookie** (`user`, set by `setUserCookie()` in `base.html` with a
  `window.prompt`, called on first search or add from `search.html` and `files.html`). The
  server has no list of guests and trusts the posted or cookie name for ownership:
  `routes/queue.py` `_verify_ownership` and `user_pause`, `routes/processing.py`
  `user_cancel_item` and `processing_status`, and `home.html` showing the Now Playing controls
  when `Cookies.get("user") === np.now_playing_user`. The navbar link `#current-user` opens a
  rename prompt (`initUsernameHandler` in `static/spa-navigation.js`). A rename today leaves
  the old name's songs behind.
- **The name is carried in three places of state:** queue items (`item["user"]`, including held
  slots created by `QueueHold` from the `download_queued` event), `PipelineTracker` items
  (`PipelineItem.user`, used for "mine" on the Processing page, the guest cancel, and the
  enqueue after processing), and `PlaybackController.now_playing_user` (Now Playing, the TV
  overlay's singer name). `DownloadManager.pending_downloads` also has a `"user"` key, but
  nothing reads it after the `download_queued` event, so a rename can skip it.
- **The play loop** (`Karaoke.run`) pops the next song and calls
  `playback_controller.play_file(song["file"], song["user"], song["semitones"])`.
  `play_file` reads the vocal volume from the `vocal_volume` preference.
- **The queue's `semitones` field is always 0.** `QueueManager.enqueue` takes a `semitones`
  argument that no production caller passes. Only tests use it.
- **Vocal volume has two live copies.** `PlaybackController.now_playing_vocal_volume` is what
  plays. `Karaoke.vocal_volume` is reset to the preference by `reset_now_playing`, written by
  `set_vocal_volume`, and overrides the controller's value in `Karaoke.get_now_playing`
  (`"vocal_volume": self.vocal_volume` after `**playback_state`). With per-guest values, the
  Now Playing slider would show the house value while the guest's value plays. The attribute
  itself must stay: `Karaoke._load_preferences` (through `PreferenceManager.apply_all`) sets
  one attribute per preference on the Karaoke instance.
- **SPA navigation** (`static/spa-navigation.js`) swaps the `.box` content and re-runs every
  inline script of the fetched page, `base.html`'s head script included (see the comment in
  `connectSocket`). Markup outside `.box` (navbar, notification) stays from the first load.
- **The queue limit** (`QueueManager.is_user_limited`) exempts the literal names `Pikaraoke`
  and `Randomizer`.
- **There is no TV web page** in this fork (the TV is mpv's overlay), so "any page" means
  every page that extends `base.html`.
- **Some tests render `base.html` on a bare `Flask` app** (`tests/unit/test_search_render.py`),
  without the app's context processors.

## Design

### `pikaraoke/lib/singers.py`: the session's guests

```python
RESERVED_NAMES = ("Pikaraoke", "Randomizer")
KEY_LIMIT = 3

@dataclass
class SingerSettings:
    semitones: int
    vocal_volume: float  # 0.0-1.0

class SingerRegistry:
    """The guests who joined during this run of the app; forgotten when it stops."""
    def __init__(self, preferences: PreferenceManager) -> None: ...
    def join(self, name: str, settings: SingerSettings) -> tuple[str, str]:  # (name, token)
    def update(self, old_name: str, token: str, new_name: str, settings: SingerSettings,
               on_rename: Callable[[str, str], None]) -> str:  # the name now held
    def owns(self, name: str | None, token: str | None) -> bool:
    def settings_for(self, name: str) -> SingerSettings:
```

- Each guest has a random token (`secrets.token_urlsafe`), stored in the phone's
  `singer_token` cookie next to the `user` cookie. `owns(name, token)` is the one test for
  "this phone joined as this name during this run". It answers no after a restart (the
  registry is empty) and no for a stale phone whose name someone else took since. This
  replaces a separate session ID.
- `join` and `update` raise a `NameTaken` error (one exception class, carrying the
  translated message) when the name is reserved or already held by another guest. Compare names
  case-insensitively (`casefold`), after stripping whitespace, so `mike` and `Mike` count as
  the same name. A blank name becomes `Anon-` plus 4 random letters/digits, picked again
  until free.
- `update` with the guest's own name (a case change included) only saves the settings and
  the spelling. A new name moves the entry, token included, and calls `on_rename(old, new)`
  **while still holding the registry lock**, so nobody can join as the old name before the
  songs have moved. Lock order: registry, then queue, tracker or playback. Nothing takes the
  registry lock while holding one of those (the play loop calls `settings_for` after
  `pop_next` returns), so this cannot deadlock. Keep it that way.
- `settings_for(name)` returns the guest's settings, or the house defaults
  (`SingerSettings(0, preferences.get_or_default("vocal_volume"))`) for a name that isn't
  registered (Randomizer, the admin's default user, a stale name). This is the only place the
  house default is resolved for playback.
- All state under one `threading.Lock`. The check and the insert in `join` happen under it.
- Validation of the ranges (`-KEY_LIMIT..KEY_LIMIT`, `0..1`) lives in the route schema, not
  here.

`QueueManager.is_user_limited` uses `RESERVED_NAMES` instead of its literal tuple.

### Playback reads the singer's settings when the song starts

- `Karaoke.__init__` makes `self.singers = SingerRegistry(self.preferences)`.
- The play loop: `singer = self.singers.settings_for(song["user"])`, then
  `play_file(song["file"], song["user"], singer.semitones, singer.vocal_volume)`.
- `PlaybackController.play_file` takes `vocal_volume: float` as a parameter and stops reading
  the preference.
- **Delete the queue's `semitones` field**: the `enqueue` parameter, the item key, and the
  tests that set it (`test_queue_manager.py`, `test_karaoke_queue.py`,
  `test_karaoke_delegation.py`, `test_queue_routes.py`). It is always 0 today, and after this
  change it would contradict the key the song actually plays at.
- **One live vocal volume**: `Karaoke.get_now_playing` stops overriding `vocal_volume`, so the
  controller's value (the one playing) is reported. `Karaoke.set_vocal_volume` and
  `reset_now_playing` stop writing `self.vocal_volume`. Leave the attribute and the
  preference skip-list in `PreferenceManager.set` alone (the attribute is set by
  `Karaoke._load_preferences`). Update `tests/conftest.py`'s mock if it relies on it.
- Now Playing controls (`/transpose`, `/vocal_volume`) are unchanged: they change only the
  current song.

### Renaming moves the guest's songs

`Karaoke.rename_singer(old: str, new: str)` is the `on_rename` callback:

- `QueueManager.rename_user(old, new)` (`@_locked`): sets `item["user"] = new` on every item
  of `old`, held items included. Emits `queue_update` and `now_playing_update` (Up Next shows
  the singer) once, only if something moved.
- `PipelineTracker.rename_user(old, new)`: under its lock, every item of `old`; then
  `_notify_change()` if something moved.
- `PlaybackController.rename_singer(old, new)`: under `_playback_lock`, if
  `now_playing_user == old`, set it and call `refresh_overlays()` so the TV shows the new
  name. Then `Karaoke.update_now_playing_socket()`.

### Route and page state

New blueprint `pikaraoke/routes/singer.py` (`singer_bp`), registered with the internal
blueprints in `app.py`.

- `POST /singer`, form fields `name`, `semitones`
  (`fields.Integer(validate=Range(-KEY_LIMIT, KEY_LIMIT))`), `vocal_volume`
  (`fields.Float(validate=Range(0, 1))`). If `owns(cookie user, cookie singer_token)`, it is
  an `update` with `on_rename=k.rename_singer`. Otherwise it is a `join`. Returns
  `{"success": true, "name": ..., "token": ...}`, or `{"success": false, "error": ...}` with
  409 on `NameTaken`. The route sets no cookies. The page does, the same way it does today.
- A context processor (`singer_bp.app_context_processor`) gives every template `singer`:
  `{"joined": bool, "name", "semitones", "vocal_volume", "house_vocal_volume",
  "transpose_enabled"}`, computed from the request's cookies, the registry,
  the `vocal_volume` preference and `k.is_transpose_enabled`. `base.html` writes it into its head
  script as `window.singer = {{ singer | tojson }}`. Since SPA navigation re-runs that
  script, every navigation picks up fresh state, including after a restart. Guard the
  template for apps without the processor (`{{ (singer or {}) | tojson }}` or equivalent) so
  `test_search_render.py` keeps passing.

### The form

- A Bulma modal in `base.html`, **outside `.box`** so SPA navigation never swaps it. Fields:
  name (text), vocal volume (range 0-100, with a % label, starting at the guest's value or
  the house default), key (- and + buttons around a label from `getSemitonesLabel`, -3 to +3,
  starting at the guest's value or 0, hidden when `transpose_enabled` is false).
- **Join mode** opens on any page when `window.singer.joined` is false. It has no close
  button, no Cancel, and the background doesn't close it: Save is the only way out. **Edit
  mode** opens from `#current-user`, prefilled, with Cancel.
- Save posts to `/singer`. A 409 shows the error under the name field and keeps the modal
  open. On success: `Cookies.set("user", name, { expires: 3650, path: '/' })`, the same for
  `singer_token` (the token is only valid for this run anyway), then `location.reload()` so
  every page-level copy of the name (`queue.html`'s `currentUser`, `search.html`'s
  `.song_added_by`) is fresh.
- Bind the handlers once with delegation in `spa-navigation.js`, replacing
  `initUsernameHandler`. The head script re-runs on each navigation, so binding there would
  stack handlers. Open join mode from the head script's ready handler, after it reads
  `window.singer`.
- The navbar shows `window.singer.name` when joined (not the raw cookie).
- **Delete:** `setUserCookie()` and its calls in `files.html` and `search.html` (the form now
  runs on page load), `generateRandomString` (the server makes Anon names now),
  `window.i18n.promptChangeUsername` and the fallback text in `spa-navigation.js`.
- New strings get `_()` and a `{# MSG: ... #}` comment per `pikaraoke/_TRANSLATION.md`.
  Don't regenerate the catalogs (that's done in occasional batches).

### Accepted edges

- **A phone left open across a crash** keeps its old cookies until its next navigation or
  reload. Before then it can still add songs under its old name, because the enqueue and
  download routes trust the posted name as they do today. If someone else has taken that
  name in the new run, the songs merge. This needs a crash, a name collision, and an add with
  no navigation in between. Closing it would mean a join check on every add route. Not built
  unless Ken asks.
- **Rename between `pop_next` and `play_file`**: the song that just left the queue starts
  under the old name with the house defaults. The window is the gap between two lines of the
  play loop.

## Phases

Stop after each phase: relay a short summary, give the checkpoint prompts (CLAUDE.md
Checkpoints), and let Ken `/compact` before the next.

### Phase 1: registry and playback (server only)

1. `lib/singers.py` with tests (`tests/unit/test_singers.py`, real `PreferenceManager`):
   join, taken (case-insensitive), reserved, blank gets a unique Anon name, `owns` with a
   wrong token and with an unknown name, update keeps the token, update renames and calls
   `on_rename` once, update to a taken name raises and moves nothing, `settings_for` falls
   back to the house default and follows a changed preference.
2. The play loop lookup, `play_file(vocal_volume=...)`, the queue `semitones` deletion, and
   the single live vocal volume, with their tests updated. Add one test that a registered
   singer's settings reach `play_file`, and one that `get_now_playing` reports the
   controller's vocal volume.
3. `is_user_limited` uses `RESERVED_NAMES`.

Commits: `feat(singers): session registry of guests and their settings` (step 1 + 3);
`feat(playback): a song starts at its singer's key and vocal volume` (step 2).

### Phase 2: route, rename moves, page state

1. `QueueManager.rename_user`, `PipelineTracker.rename_user`,
   `PlaybackController.rename_singer`, `Karaoke.rename_singer`, each with a test (held queue
   items move; other guests' items don't; events fire once; the now-playing name changes only
   when it matches).
2. `routes/singer.py`: route and context processor, tests on a bare Flask app as in
   `test_queue_routes.py`: join adds the guest and returns their name and token; 409 on taken
   and reserved; out-of-range key gets 422; update by the owner; a wrong token on a known name is
   treated as a join (and so gets 409); rename calls `rename_singer`; the context processor's
   `joined` for no cookie, a good token and a stale token.

Commits: `feat(singers): renaming moves the guest's songs`;
`feat(singers): join and settings route`.

### Phase 3: the form

1. The modal, handlers, deletions, and navbar change described above.
2. Verify with the local `ui-check` skill on the VM (phone viewport):
   - A fresh browser gets the join form on `/`, can't dismiss it, and a taken name shows the
     error.
   - After joining, add a song. When it plays, the Now Playing key and vocal volume sliders
     show the saved values. Use a dual-stem song for vocal volume. If the fake library has none,
     check only the key and say so.
   - Clicking the name opens edit mode, prefilled. A rename moves a queued song and a held
     download to the new name, and the Processing page still marks the row as the guest's.
   - SPA navigation doesn't stack handlers (one POST per Save).
   - Restart the app: the next navigation shows the join form again.

Commit: `feat(ui): join form for name, key and vocal volume`.

### Phase 4: Ken's checks

Ken runs the test plan below at a real party or a rehearsal on his box. No code unless he
finds something.

## Test plan (manual, for the PR)

- [ ] A new phone gets the form on first page open, and can't skip it.
- [ ] Join with key +2 and vocal volume 70%. Your next song starts at +2 and 70% with nobody
      touching anything, and the TV overlay shows +2.
- [ ] Change the key on Now Playing mid-song: your next song starts at your saved key again.
- [ ] Change your settings while a song of yours is queued: it plays at the new values.
- [ ] A second phone can't take your name.
- [ ] Rename while you have a song queued: it shows your new name, and you can still delete
      or pause it.
- [ ] Restart the app: every phone is asked to join again.
- [ ] Randomizer songs play at key 0 and the house vocal volume.

## Follow-ups (not in this plan)

- **Limit the Now Playing key slider to -3..+3 as well** (Ken, 2026-11-06: the distortion
  is pronounced beyond that). Listed in `plans/open-issues.md` on `dev`.
- Per-song key memory (singer + song), if wanted (ruling 3).

## Results log

(Executor: one row per phase: commit hashes, test counts, ui-check outcome, anything that
deviated from this plan and why.)

### Phase 1: registry and playback (executed 2026-11-06, Claude Sonnet 5.5)

- **Commits:** `5c0fdc2` `feat(singers): session registry of guests and their settings` (step 1
  + 3); `0c70ac0` `feat(playback): a song starts at its singer's key and vocal volume` (step 2).
- **Tests:** full suite 3354 passed before, 3397 after (+40 `test_singers.py`, +3 run-loop and
  +1 Now Playing in `test_karaoke_singer_playback.py`, +1 in `test_playback_controller.py`,
  -2 queue `semitones` tests deleted). Pre-commit clean on every changed file.
- **ui-check:** not applicable (server only; Phase 3).
- **Deviations from the plan:**
  1. `update` calls `on_rename` for a case-only change too (plan: only save the spelling).
     The ownership checks (`_verify_ownership`, `user_cancel_item`, the Processing page's
     "mine") compare names exactly, so songs left under `mike` would be stranded once the
     cookie says `Mike`. Phase 2's `rename_user` must therefore move a case-only rename.
  2. `update` raises `PermissionError` when the name and token do not match a guest of this run
     (plan silent). The route checks `owns` first; this is the re-check under the lock.
  3. `update` with a blank new name keeps the current name (plan silent).
  4. `SingerSettings` is frozen, so a settings object handed out cannot change the registry.
  5. One `NameTaken` message covers reserved and in-use names.
  6. `play_file(file_path, user, semitones, vocal_volume)`: both required, no defaults, so a
     caller that forgets the vocal volume fails loudly instead of playing at the wrong level.
     The 8 existing test calls now pass `0, 0.4`.
  7. `MockKaraoke` in `tests/conftest.py` gained `singers` and the real `Karaoke.run`, so the
     run-loop test drives the real loop; its dead `vocal_volume` attribute is gone and
     `MockPlaybackController` reports `vocal_volume`.
- **Behavior change to know about:** with nothing playing, `get_now_playing` now reports
  `vocal_volume` 0.0 (the controller's idle value) where it used to report the house default.
  `home.html` only reads it when `dual_stem` is true, so nothing visible changes.
- **Not done:** `graphify update .` (no `graphify-out/` on this box).
