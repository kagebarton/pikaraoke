Model: Claude Opus 5.5 (author, 2026-11-06). Executor: Claude Sonnet 5.5.
Phase 2.1 added by Claude Opus 5.5 on 2026-11-06 from the `/code-review` of Phases 1-2. The
Design sections it changes are rewritten in place and marked (2.1). Phase 2.2 added by Claude
Opus 5.5 on 2026-11-06 from the `/code-review` of Phase 2.1, marked (2.2) the same way. Phase
3.1 added by Claude Opus 5.5 on 2026-11-06 from the `/code-review` of Phase 3, marked (3.1).

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
NAME_LIMIT = 30  # (2.1)

@dataclass(frozen=True)
class SingerSettings:
    semitones: int
    vocal_volume: float  # 0.0-1.0

class SingerRegistry:
    """The guests who joined during this run of the app; forgotten when it stops."""
    def __init__(self, preferences: PreferenceManager,
                 on_rename: Callable[[str, str], None]) -> None: ...  # (2.1)
    def save(self, token: str | None, name: str,
             settings: SingerSettings) -> tuple[str, str]:  # (name, token)  (2.1)
    def lookup(self, token: str | None) -> tuple[str, SingerSettings] | None:  # (2.1)
    def settings_for(self, name: str) -> SingerSettings:
    def house_defaults(self) -> SingerSettings:  # (2.1)
```

- **A phone is its token (2.1).** Each guest has a random token (`secrets.token_urlsafe`),
  stored in the phone's `singer_token` cookie next to the `user` cookie. `save` and `lookup`
  find the guest by the token alone, never by the name cookie: scan the guests with
  `secrets.compare_digest` (a party is tens of guests). So a phone whose name cookie is out
  of date (a save whose reply was lost, or a second save sent before the first one's reply)
  still finds its own guest. A token from an earlier run finds nobody (the registry is
  empty). This replaces a separate session ID.
- `save` raises a `NameTaken` error (one exception class, carrying the translated message)
  when the name is reserved or already held by another guest. Compare names
  case-insensitively, after stripping whitespace and normalizing to Unicode NFC (2.1), so
  `mike` and `Mike` count as the same name, and so do the two encodings of `José`. The stored
  spelling is NFC too (2.1). The reserved names are compared with the same key (2.2). A blank
  name becomes `Anon-` plus 4 random letters/digits, picked again until free.
- **`save` (2.1)**: a token that belongs to a guest updates that guest; anything else joins.
  One lock acquisition covers the check and the change, so there is no separate ownership
  test and no "not a guest" error. An update with a blank name keeps the current name. When
  the spelling changes (a case change included, because the queue, tracker and ownership
  checks compare names exactly) the registry changes first (name and settings set; the entry
  re-keyed only when the key changes, 2.2), then calls `on_rename(old, new)` **while still
  holding the registry lock**, so nobody can join as the old name before the songs have
  moved. **`on_rename` must not raise (2.2):** the moves are in-memory loops, and
  `Karaoke.rename_singer` catches a failing notification. If a move did raise, the songs not
  yet moved would stay under the old name, which is free again. Lock order: registry, then
  queue, tracker or playback. Nothing takes the registry lock while holding one of those (the
  play loop calls
  `settings_for` after `pop_next` returns), and nothing called from `on_rename` may call the
  registry (its lock is not reentrant), so this cannot deadlock. Keep it that way.
- `lookup(token)` returns the guest's name as the registry holds it, and their settings, or
  `None` (2.1).
- `settings_for(name)` returns the guest's settings only for the guest's exact spelling (2.1),
  as the queue, tracker and ownership checks compare exactly. Any other name (Randomizer, the
  admin's default user, a stale name, another case) gets `house_defaults()`:
  `SingerSettings(0, preferences.get_or_default("vocal_volume"))`. This is the only place the
  house default is resolved.
- All state under one `threading.Lock`.
- Validation of the ranges (`-KEY_LIMIT..KEY_LIMIT`, `0..1`) and of the name's length
  (`NAME_LIMIT`, 2.1) lives in the route schema, not here.

`QueueManager.is_user_limited` uses `RESERVED_NAMES` instead of its literal tuple.

### Playback reads the singer's settings when the song starts

- `Karaoke.__init__` makes `self.singers = SingerRegistry(self.preferences,
  self.rename_singer)` (the callback since 2.1).
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

`Karaoke.rename_singer(old: str, new: str)` is the `on_rename` callback. **It moves every
copy of the name first, then tells the pages (2.1)**, so a notification that raises can't leave
songs split between two names, and can't fail the save (2.2):

- `QueueManager.rename_user(old, new)` (`@_locked`): sets `item["user"] = new` on every item
  of `old`, held items included. Returns whether anything moved; emits nothing (2.1).
- `PipelineTracker.rename_user(old, new)`: under its lock, every item of `old`; then
  `_notify_change()` if something moved. It keeps its own push because `_notify_change`
  already catches and logs a failing callback, so it can't stop the moves after it.
- `PlaybackController.rename_singer(old, new)`: under `_playback_lock`, if
  `now_playing_user == old`, set it. Returns whether it moved; refreshes nothing (2.1).
- Then `Karaoke.rename_singer` emits `queue_update` if the queue moved, calls
  `playback_controller.refresh_overlays()` if the playing song moved (the TV shows the new
  name), and emits `now_playing_update` once if either moved (Up Next and Now Playing show
  the singer).
- These notifications run under the registry lock, after every move. Releasing the lock
  first would need a second callback to save a few milliseconds; the long wait under the
  lock is the `_playback_lock` wait (Phase 2 results, "Known property").
- **The notifications run in one `try` (2.2).** An exception from any of them is logged with
  its traceback (`logging.exception`, naming the old and new name) and not raised, so a save
  whose songs all moved always returns the new name to the phone. The handlers are arbitrary
  callables and `EventSystem.emit` doesn't catch, so this catches `Exception`, as
  `PipelineTracker._notify_change` does. The notifications after the failing one are skipped:
  the TV overlay re-renders on its own poll within half a second, and the pages catch up on
  their next push or reload.

### Route and page state

New blueprint `pikaraoke/routes/singer.py` (`singer_bp`), registered with the internal
blueprints in `app.py`.

- `POST /singer`, form fields `name` (`fields.String(validate=Length(max=NAME_LIMIT))`, 2.1),
  `semitones` (`fields.Integer(validate=Range(-KEY_LIMIT, KEY_LIMIT))`), `vocal_volume`
  (`fields.Float(validate=Range(0, 1))`). It is one call, `k.singers.save(cookie
  singer_token, name, settings)` (2.1). Returns `{"success": true, "name": ..., "token": ...}`,
  or `{"success": false, "error": ...}` with 409 on `NameTaken`. The route sets no cookies.
  The page does, the same way it does today. The route reads only the token cookie, never
  the name cookie (2.1).
- A context processor (`singer_bp.app_context_processor`) gives every template `singer`:
  `{"joined": bool, "name", "semitones", "vocal_volume", "name_limit", "key_limit",
  "transpose_enabled"}` (2.1: `house_vocal_volume` dropped, `name_limit` added; 3.1:
  `key_limit` added, so the form's key control has no copy of the limit), from one
  `k.singers.lookup(token)` call. A phone that hasn't joined gets `name` `""` and
  `house_defaults()`, so its `vocal_volume` is the house default the join form starts at.
  `base.html` writes the state into its head script as `window.singer = {{ singer | tojson
  }}`. Since SPA navigation re-runs that script, every navigation picks up fresh state,
  including after a restart. Guard the template for apps without the processor (`{{ (singer
  or {}) | tojson }}` or equivalent) so `test_search_render.py` keeps passing.
- **`GET /singer` (3.1)** returns the same state as JSON, built by the same function as the
  context processor's. The form loads it when the guest opens edit mode, because the page's
  copy is only as fresh as its last navigation.

### The form

- A Bulma modal in `base.html`, **outside `.box`** so SPA navigation never swaps it. Fields:
  name (text), vocal volume (range 0-100, with a % label, starting at the guest's value or
  the house default), key (- and + buttons around a label from `getSemitonesLabel`, from
  `-key_limit` to `+key_limit` of the state the form opened with (3.1), starting at the
  guest's value or 0, hidden when `transpose_enabled` is false). The form fills its fields from
  the state it is opened with, so the markup carries no default values of its own (3.1).
- **Join mode** opens on any page when the phone has no guest. It has no close button, no
  Cancel, and the background doesn't close it: Save is the only way out. **Edit mode** opens
  from `#current-user`, prefilled, with Cancel.
- **Edit mode opens from the server's current state (3.1).** Clicking the name loads `GET
  /singer` (with `cache: false`) and opens the form from what comes back. If the phone has no
  guest any more (the app restarted since this page loaded), the join form opens instead and
  the navbar name is hidden. If the load fails, edit mode opens from the page's state as
  before. The page's own state (`window.singer`) is not overwritten by the load: it says what
  this page's copies of the name were loaded with, which the reload rule below needs.
- **While the form is open, nothing behind it can be reached (3.1):** `body > .container`
  (the navbar and `.box`) is `inert`, so neither a click nor the Tab key reaches an Add link
  behind the join form. Closing the form lifts it. `.container` is never swapped by SPA
  navigation, so this holds across one.
- Save posts to `/singer`. A 409 shows the error under the name field and keeps the modal
  open. On success, the `user` and `singer_token` cookies are set from the reply (the token is
  only valid for this run anyway), through one head-script helper that both this and the
  put-back below use, so the two can't drift (3.1).
- **Reload only when the page's copies of the name are wrong (3.1).** After a join, or when
  the reply's name differs from `window.singer.name`, `location.reload()` so every page-level
  copy of the name (`queue.html`'s `currentUser`, `search.html`'s `.song_added_by`) is fresh.
  A save that keeps the name closes the form and leaves the page as it is, so unsaved work on
  it (lyric edits, a playlist being built, search results) stays.
- Bind the handlers once with delegation in `spa-navigation.js`, replacing
  `initUsernameHandler`. The head script re-runs on each navigation, so binding there would
  stack handlers.
- **One function applies the guest state to the page (3.1)**, called by the head script's
  ready handler with `window.singer` and by the edit-mode load with what came back. Joined:
  the navbar shows the registry's name (not the raw cookie), and a join form left open
  closes. Not joined: the navbar name is hidden and join mode opens. **Opening the form in
  the mode it is already open in does nothing (3.1)**, so a navigation (a back swipe) keeps
  what the guest typed and keeps Save disabled while a save is in flight.
- **Keep the name cookie in step with the registry (2.1).** As the head script loads, right
  after it sets `window.singer` (Phase 3 results, deviation 1), when `window.singer.joined`
  and `Cookies.get("user") !== window.singer.name`, set the `user` cookie to
  `window.singer.name`. The add, delete and pause routes post the cookie's name, so this
  makes them use the registry's spelling after a save whose reply was lost.
- The name field has `maxlength` set from `window.singer.name_limit` (2.1). The server
  answers a longer name with a 422.
- **Edit mode sends the name only when the guest changed it (2.2).** If the name field still
  holds the value it was prefilled with, Save posts `name` as `""`, which keeps the current
  name. So a tab opened before a rename can't rename the guest back (and move their songs
  back) when they change only the key there, and a stored name the length check would refuse
  (see Accepted edges) can still be saved. Join mode posts what was typed. Since edit mode
  opens from the server's state (3.1), the rule still matters for a rename on another tab
  between opening the form and saving it, and for the long stored name.
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
- **An add in flight during a rename** (review of Phases 1-2, 2026-11-06): a search-add or
  download posted under the old name that reaches the queue or the tracker after the rename
  moved them lands under the old name, plays at the house defaults, and belongs to whoever
  takes that name next. Same class as the case above: the window is one request's processing
  time, during the guest's own rename. The same holds when a guest joins as, or renames to, a
  name that has songs but no guest (2.2): the check for a free name looks at the registry, not
  the queue or the tracker.
- **Ownership checks trust the name the phone carries (2.2).** The Processing page's "mine"
  and guest cancel read the `user` cookie; the queue's guest delete and pause take the name
  the page posts. After a save whose reply was lost, that name is stale until the next page
  load, where the cookie is put back to the registry's spelling (The form, 2.1). Reading the
  token in the Processing routes alone would leave two rules for "is this yours", and moving
  the queue routes to the token too needs the page scripts changed (they post the name, and
  the route schema refuses unknown fields). Not built unless Ken asks.
- **Names that look alike (2.2)**: the spelling rule is strip, case and NFC. A name with an
  invisible character (`Mike` plus a zero-width space) or full-width letters is a different
  name, so two singers can both show as `Mike`, and an invisible-only name is kept instead of
  becoming an Anon name. Guests at a party don't do this by accident.
- **The length limit counts the raw form value (2.1 results, 2.2)**: before the strip and
  before NFC, so a few scripts whose letters NFC splits can store a name longer than the limit.
  Edit mode's unchanged name posts blank (The form, 2.2), so such a guest can still save.
- **A lost reply to a phone's first join (3.1)**: the server made the guest, but no token
  reached the phone. Saving again is a new join, and the name is taken by the guest the lost
  reply made, so it is refused for the rest of the run. The guest can join under another
  name. The fix would be the phone making its own token before it joins, so a retry finds the
  guest it already made; that changes where tokens come from, for a reply lost in the moment
  between the server answering and the phone hearing it, once per guest. Not built unless Ken
  asks.
- **A join form left open on another tab (3.1)**: if the guest joins on tab B and then fills
  in the join form still open on tab A without navigating there, the save carries tab B's
  token, so it updates that guest with what was typed on A (a new name renames them). Those
  are the values the guest just picked. A navigation on tab A closes the form instead (The
  form, 3.1).
- **A rename still reloads the page (3.1)**: unsaved work on the page is lost, as before 3.1.
  Only a save that keeps the name keeps the page.

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

### Phase 2.1: review fixes (server only)

From the `/code-review` of `4497f4d..731d5ec` (Phases 1-2, 2026-11-06, 15 findings). Ken
accepted targeted fixes over the review's root-cause suggestion (store a guest ID in the queue,
tracker and playback, and look the name up when shown). That would touch about 40 places in 7
files plus the page scripts that compare the name cookie to the Now Playing singer, and would
put two kinds of identity in the queue's `user` field (guest IDs for joined phones, plain
names for the admin and the Randomizer). Ruling 8 stands.

Build the Design sections marked (2.1). Review findings, by number in the review's list:

| # | Finding | Fix |
| - | ------- | --- |
| 1 | A failed `on_rename` leaves songs moved but the registry under the old name | Registry changes first; moves before notifications |
| 2 | A stale name cookie with a good token joins as a new guest, or 409s on its own name | Token lookup |
| 3 | `settings_for` ignores case, the rename moves don't | Exact spelling in `settings_for` |
| 4 | Processing routes read the name cookie undecoded (pre-existing) | Decode there |
| 5 | Page state echoes the cookie's spelling | `lookup` returns the registry's |
| 6 | An add in flight during a rename lands under the old name | Accepted edge (Design) |
| 7 | Registry lock held through the `_playback_lock` wait | Already a known property (Phase 2 results) |
| 8 | No name length limit; a long name overflows the 4 KB cookie | `NAME_LIMIT` in the schema |
| 9 | Ownership checked twice; `PermissionError` as "not a guest" | One `save`; delete both |
| 10 | Context processor rebuilds house defaults, takes the lock twice | `lookup` + `house_defaults` |
| 11 | Root cause: the name is the identity | Not taken (above) |
| 12 | Two `now_playing_update` per rename; config read per render | One push; only unjoined phones read it now |
| 13 | `play_file` test mocks preferences; run-loop test can hang | Fix both |
| 14 | No Unicode normalization | NFC |
| 15 | `save_singer` has no type hints | Add them |

1. **Processing reads the name cookie decoded (4).** One private reader in
   `routes/processing.py` (`unquote(request.cookies.get("user", ""))`, the same decode Phase 2
   used), used by `/processing/status` and `user_cancel_item`. This settles the Phase 2 "Ken's
   call". Tests: a guest `Mary Ann` with the encoded cookie sees their row as `mine`, and their
   cancel succeeds.
2. **A phone is its token (2, 5, 9, 10, 15).** `save`, `lookup`, `house_defaults` and the
   constructor's `on_rename`, as in Design. Delete `join`, `update`, `owns`, the
   `PermissionError`, the route's 403 branch, the route's name-cookie read and `NAME_COOKIE`,
   and `house_vocal_volume`. Annotate `save_singer`. Tests (rewrite the `test_singers.py`
   tests of the deleted methods against `save`, keeping their coverage of taken, reserved and
   Anon names):
   - `save` with no token, or an unknown one, joins; with a guest's token it updates that
     guest and keeps the token; a blank name keeps the current name.
   - Two saves with the same token, the second carrying the first's new name: one guest,
     no `NameTaken`.
   - A guest's token with a name another guest holds raises `NameTaken` and changes nothing.
   - `on_rename` runs once on a rename and not on a settings-only save. One that raises
     leaves the registry under the new name with the new settings, and the error propagates.
   - `lookup`: `None` for no token and an unknown one; the registry's name and settings for
     a guest.
   - Route: a good token with a stale name cookie updates the same guest, both with a blank
     name and with the registry's name (200, not 409; one guest). Page state reports the
     registry's spelling whatever the name cookie says, has `name_limit` and no
     `house_vocal_volume`, and an unjoined phone gets the house vocal volume. Delete the 403
     test and the two encoded-name-cookie tests (this route no longer reads that cookie).
3. **A rename moves every copy before it tells anyone (1, 12).** The queue and playback
   moves return whether they moved and emit nothing; `Karaoke.rename_singer` notifies, as in
   Design. Tests: update the Phase 2 queue and playback tests that assert emits (they now
   assert the return value and no emit). In `test_karaoke_rename_singer.py`: with a
   `queue_update` handler that raises, a queued song, a held one, a tracker row and the
   playing song all carry the new name and the registry holds it; one `now_playing_update`
   when a queued song and the playing song both move; overlays refreshed only when the
   playing song moved.
4. **One spelling rule for names, and a length limit (3, 8, 14).** NFC in `_key` and in the
   stored spelling; exact spelling in `settings_for`; `NAME_LIMIT = 30` and the schema's
   `Length`. 30 is the author's pick; Ken can change it. Tests: composed and decomposed
   `José` collide (`NameTaken`) and the stored name is NFC; `settings_for("MIKE")` gets the
   house defaults while `Mike` is a guest; a name of `NAME_LIMIT` characters is accepted, one
   longer gets 422.
5. **Tests (13).** The `play_file` test uses the real `PreferenceManager` with
   `vocal_volume` set to another value (a `tmp_path` config if `set` needs a writable file)
   and asserts the passed value reaches mpv. The run-loop fixture's `handle_run_loop` counts
   passes and sets `running = False` after 20, so a regression fails the assertion instead
   of hanging.

Commits: `fix(processing): read the guest's name cookie decoded` (step 1);
`fix(singers): a phone is found by its token alone` (step 2);
`fix(singers): a rename moves every copy before telling the pages` (step 3);
`fix(singers): one spelling rule for names, and a length limit` (step 4);
`test(singers): real preferences in the play_file test, and a run loop that can't hang`
(step 5).

Self-review: steps 2 and 3 are multi-file concurrency again, so track the review as pending
for the checkpoint after this phase.

### Phase 2.2: review fixes of 2.1 (server only)

From the `/code-review` of `731d5ec..8322831` (Phase 2.1, 2026-11-06, 11 findings). No
deadlock found; every copy of the name moves. Build the Design sections marked (2.2) that are
on the server; the form's (2.2) rule is Phase 3's. Review findings, by number in the review's
list:

| # | Finding | Fix |
| - | ------- | --- |
| 1 | A notification that raises after every move fails the save (500) | Step 1 |
| 2 | Processing ownership reads the name cookie, not the token | Accepted edge (Design), with the queue routes |
| 3 | A tab opened before a rename renames the guest back | Phase 3: edit mode sends the name only when changed |
| 4 | `save`'s docstring says a raising `on_rename` leaves the registry consistent | Step 1 |
| 5 | The length limit counts the raw value, before strip and NFC | Accepted edge (Design); Phase 3's rule from #3 |
| 6 | `MockKaraoke`'s `on_rename` silently moves nothing | Step 1 |
| 7 | Settings-only saves re-key the entry; reserved names use their own rule | Step 2 |
| 8 | The tracker pushes before the playing song moves; its failures log at debug | Accepted (2.1 Design): the Processing page doesn't show the playing song; the debug log is pre-existing |
| 9 | Look-alike and invisible names count as different guests | Accepted edge (Design) |
| 10 | Joining a name that still has songs takes them | Accepted edge (Design), extends "An add in flight" |
| 11 | Every page render scans the tokens under the registry lock | Known property (Phase 2 results); a party is tens of guests |

The review also called the outer NFC in `_key` redundant. It isn't: `casefold` can return
decomposed text (`ǰ`, U+01F0, casefolds to `j` plus U+030C, and NFC puts it back). Keep it.

1. **A rename whose songs all moved always saves (1, 4, 6).**
   - `Karaoke.rename_singer`: the notifications in one `try`, as in Design.
   - `SingerRegistry`: the `save` docstring drops "an `on_rename` that raises leaves the
     registry consistent with the songs" and says `on_rename` must not raise, and why (as in
     Design). The class docstring's lock paragraph stays.
   - `tests/conftest.py`: `MockKaraoke`'s `on_rename` raises `AssertionError` with a message
     pointing at the `party` fixture in `test_karaoke_rename_singer.py`, so a test that renames
     through the mock fails instead of passing with nothing moved. No current test renames
     through it.
   - Tests in `test_karaoke_rename_singer.py`: rewrite
     `test_a_notification_that_raises_leaves_every_copy_moved_and_the_registry_in_step` so
     the save returns `("Michael", token)` with no exception, every copy and the registry say
     `Michael`, and the failure is logged at ERROR with its traceback (`caplog`). Keep the
     `test_singers.py` test that a raising `on_rename` propagates out of `save` (the registry
     doesn't catch; the callback must not raise).
2. **One key rule for reserved names, and no re-key on a settings save (7).** `_RESERVED_KEYS`
   built with `_key`; `_update` moves the dict entry only when `_key(new) != _key(old)`. No new
   tests: the existing taken, reserved, settings-only and case-only tests cover both.

Commits: `fix(singers): a rename whose songs all moved always saves` (step 1);
`refactor(singers): one key rule for reserved names, and no re-key on a settings save`
(step 2).

Self-review covers both: step 1 adds a catch after the moves and no lock or path; step 2 is a
refactor.

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
     Use a name with a space and an accent (2.1).
   - Set the `user` cookie to another spelling by hand and navigate: the navbar shows the
     registry's name and the cookie is put back (2.1).
   - Open a second tab, rename in the first, then in the second tab change only the key and
     save: the guest keeps the new name and their queued song stays under it (2.2).
   - SPA navigation doesn't stack handlers (one POST per Save).
   - Restart the app: the next navigation shows the join form again.

Commit: `feat(ui): join form for name, key and vocal volume`.

### Phase 3.1: review fixes of Phase 3 (the form)

From the `/code-review` of `f6e9aab^..f6e9aab` (Phase 3, 2026-11-06, 15 findings). None loses
songs; the form, the cookie put-back and the 2.2 two-tab rule work as designed. Build the Design
sections marked (3.1). Review findings, by number in the review's list:

| # | Finding | Fix |
| - | ------- | --- |
| 1 | After a restart, an edit-mode save with the name unchanged posts a blank name with an unknown token, so the guest becomes an Anon name | Step 1 |
| 2 | A lost reply to a first join leaves the name taken by a guest no phone can reach | Accepted edge (Design) |
| 3 | Edit mode posts the key and vocal volume a stale tab holds, undoing another tab's | Step 1 |
| 4 | A navigation that finds the phone joined leaves a join form open | Step 1; without a navigation, accepted edge (Design) |
| 5 | Every save reloads, losing unsaved work and re-running a search | Step 2; a rename still reloads (accepted edge) |
| 6 | A navigation re-opens an open join form: clears the typed name, re-enables Save mid-request | Step 1 |
| 7 | The Tab key reaches the Add links behind the join form; the song queues as `undefined` | Step 3 |
| 8 | `queue.html`'s unscoped `.modal-background` click binding stacks on the guest form per visit | Step 3 |
| 9 | A navigation that finds the phone not joined leaves the old name in the navbar | Step 1 |
| 10 | The key limit is copied into the markup (Phase 3 results, deviation 2) | Step 4 |
| 11 | The key label from `getSemitonesLabel` is English only (`+1 semitones`) | Follow-up: the helper predates the branch and Now Playing shows the same text |
| 12 | Markup defaults the script always overwrites (`value="40"`, `40%`, `value="0"`, `name=`) | Step 4 |
| 13 | `EventSystem` imported and unused in `test_singer_page.py` | Step 4 |
| 14 | Two page tests repeat `TestPageState` | Step 4 |
| 15 | The cookie options and the burger-menu close are each written twice | Step 4 |

1. **The form opens from the server's current state (1, 3, 4, 6, 9).**
   - `routes/singer.py`: one function builds the state dict. The context processor returns
     `{"singer": <it>}`, and a new `GET /singer` returns it as JSON.
   - `spa-navigation.js`:
     - `openSingerForm(mode, state)` fills the fields from `state` and keeps it for the key
       control. It returns at once when the form is already open in `mode`.
     - `applySingerState(state)`, on `window`: joined: the navbar name from `state.name`,
       shown, and a form open in join mode closes. Not joined: the navbar name hidden, then
       `openSingerForm('join', state)`.
     - The `#current-user` click: close the burger menu, then `$.ajax({ url: '/singer', cache:
       false })`. Done: `applySingerState(state)`, then `openSingerForm('edit', state)` if
       `state.joined`. Fail: `openSingerForm('edit', window.singer)`. It never assigns
       `window.singer`.
   - `base.html`: the ready handler's if/else becomes `applySingerState(window.singer)`.
   - Tests in `test_singer_routes.py`: `GET /singer` returns the same state as the context
     processor (the `/state` route) for a new phone, a joined phone, and a token nobody holds.
2. **A save that keeps the name keeps the page (5).** In `saveSingerForm`'s success, after the
   cookies are set: when the mode is edit and `reply.name === window.singer.name`, close the
   form and stop; otherwise reload. No server change.
3. **Nothing behind the guest form can be reached (7, 8).**
   - `openSingerForm` sets `inert` on `body > .container`; `closeSingerForm` removes it.
   - `queue.html`: the background-click binding becomes `$('.box .modal-background')`, so it
     binds only the queue's own pop-ups, which navigation replaces.
4. **One key limit, and the form's dead code out (10, 12-15).**
   - `key_limit: KEY_LIMIT` in the state. `setSingerKey` clamps with the open state's
     `key_limit`; `data-min` and `data-max` are deleted. `TestPageState`'s exact-dict test
     gains `key_limit`.
   - Markup: delete `value="40"`, the `40%` label text, the hidden key input's `value="0"`, and
     the `name=` attributes of the three inputs.
   - Head script: one helper that sets a cookie with `{ expires: 3650, path: '/' }`, used by the
     put-back and by `saveSingerForm`. Write it as a `function` declaration: the head script
     re-runs on every navigation, and a top-level `const` would throw the second time.
   - `spa-navigation.js`: `closeBurgerMenu()`, used by `navigateTo` and the name click.
   - `test_singer_page.py`: delete the two state tests (`TestPageState` and step 1's tests cover
     the dict) and the unused import. Keep the script-tag test; it already proves the line is
     written and reads back.
5. Verify with the local `ui-check` skill on the VM (phone viewport):
   - Restart the app with a page left open and not navigated: clicking the name opens the
     join form with no Cancel, hides the navbar name, and sends no POST. Joining under the old
     name works (1, 9).
   - Restart, then an SPA navigation: the join form opens and the navbar name is hidden (9).
   - Two tabs: tab 1 saves key +2 and 70%. Tab 2, opened before and not navigated, clicks the
     name: the form shows +2 and 70%. Rename there: the settings stay +2 and 70% (3).
   - Join form open on tab A, join on tab B, then navigate on tab A: the form closes and the
     navbar shows the name (4).
   - Join form: type a name, then `history.back()`: the typed name stays. With the POST held
     (Playwright `page.route`), go back: Save stays disabled, and one POST in total (6).
   - Join form open: the Tab key never focuses anything outside the form, and a click where an
     Add link is does nothing (7).
   - After three SPA visits to `/queue`, the guest form's background carries no click handler
     (`$._data(el, 'events')`) (8).
   - On `/search` with results, change only the key: the form closes, the page doesn't load
     again (a marker set on `window` survives), and no new search request goes out. A rename
     there reloads (5).
   - The key stops at -3 and +3 (10).
   - Phase 3's two-tab rename check and its one-POST-per-Save check, again.

Commits: `fix(ui): the guest form opens from the server's current state` (step 1);
`fix(ui): a save that keeps the name keeps the page` (step 2);
`fix(ui): nothing behind the guest form can be reached` (step 3);
`refactor(ui): the key limit from the server, and the guest form's dead code out` (step 4).

Self-review: step 1 changes how the form gets its state on both paths (navigation and the
name click) and adds a route, so track its review as pending for the checkpoint after this
phase. Steps 2-4 are covered by self-review.

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
- [ ] Join with a name that has a space and an accent: the Processing page marks your
      download as yours, and you can cancel it.
- [ ] Rename on one tab, then change only your key on a tab you opened before: you keep the
      new name.
- [ ] Restart the app, then click your name without changing page first: you get the join
      form, not an Anon name.
- [ ] Change only your key while Search shows results: the results stay.

## Follow-ups (not in this plan)

- **Limit the Now Playing key slider to -3..+3 as well** (Ken, 2026-11-06: the distortion
  is pronounced beyond that). Listed in `plans/open-issues.md` on `dev`.
- Per-song key memory (singer + song), if wanted (ruling 3).
- **The key label is English only** (`+1 semitones`, also the wrong plural) on the guest form
  and on Now Playing, from `getSemitonesLabel`, which predates this branch (review of Phase 3,
  #11). For `plans/open-issues.md` on `dev`.

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

### Phase 2: route, rename moves, page state (executed 2026-11-06, Claude Sonnet 5.5)

- **Commits:** `f0c4fb9` `feat(singers): renaming moves the guest's songs`; `32137ec`
  `feat(singers): join and settings route`.
- **Tests:** full suite 3397 passed before, 3451 after (+20 for the rename moves: 6 queue, 5
  tracker, 4 playback controller, 5 end-to-end in `test_karaoke_rename_singer.py`; +34 in
  `test_singer_routes.py`). Pre-commit clean on every changed file. The real `pikaraoke.app`
  object was also smoke-tested: it lists `/singer`, has `inject_singer` among its context
  processors, joins a guest, and answers an out-of-range key with a JSON 422.
- **ui-check:** not applicable (server only; Phase 3).
- **Deviations from the plan:**
  1. `PlaybackController.rename_singer` emits `now_playing_update` itself (the event
     `set_pitch` uses, which `Karaoke` already turns into the socket push) instead of
     `Karaoke.rename_singer` calling `update_now_playing_socket`. It sets the name under
     `_playback_lock` and refreshes the overlays after releasing it.
  2. **The route and the context processor decode the `user` cookie** (`urllib.parse.unquote`).
     `js-cookie` stores a space or an accent percent-encoded (`Mary%20Ann`) and Werkzeug does
     not decode it, so without this a guest named `Mary Ann` would never count as joined and
     would get a 409 on their own name.
  3. `PermissionError` from `update` is a 403 JSON `{"success": false}`: it happens when a
     second save already in flight carries the name the first save just renamed.
  4. `semitones` and `vocal_volume` are required form fields (plan silent), so Phase 3's form
     must always send both, 0 for the key when the key control is hidden.
  5. `base.html`'s `window.singer = ...` line is **not** in this phase. Nothing reads it until
     the form exists, so it goes in Phase 3 with its consumer (guard it as
     `{{ (singer or {}) | tojson }}` for `test_search_render.py`).
- **Found, not fixed (pre-existing, not from this feature):** `routes/processing.py` reads the
  raw `user` cookie (`/processing/status` and `user_cancel_item`), so for a name with a space
  or an accent the Processing page never marks a row as the guest's and the guest cancel is
  refused. Phase 3's ui-check step "the Processing page still marks the row as the guest's"
  fails for such a name unless those two reads decode too. Ken's call: fix in Phase 3 (two
  lines, same decode as `routes/singer.py`) or leave.
- **Known property:** a rename that lands while a song is starting waits for `play_file` to
  release `_playback_lock` (the `mpv.play` wait, a few seconds), and every page render waits
  behind it on the registry lock. Rare and brief; the lock order has no cycle.
- **Self-review:** the two commits are multi-file concurrency (registry lock held across
  three other locks), so the review is tracked as pending for the checkpoint after this phase.
- **Not done:** `graphify update .` (no `graphify-out/` on this box).

### Phase 2.1: review fixes (executed 2026-11-06, Claude Sonnet 5.5)

- **Commits:** `522f946` `docs(plans): singer-defaults Phase 2.1 review fixes` (the plan edit,
  see deviation 1); step 1 `93f29a9` `fix(processing): read the guest's name cookie decoded`;
  step 2 `af169a3` `fix(singers): a phone is found by its token alone`; step 3 `90726dc`
  `fix(singers): a rename moves every copy before telling the pages`; step 4 `c227083`
  `fix(singers): one spelling rule for names, and a length limit`; step 5 `8322831`
  `test(singers): real preferences in the play_file test, and a run loop that can't hang`.
- **Tests:** full suite 3451 passed before. After step 2: 3466; after step 3: 3473; after step
  4: 3483; after step 5: 3483 (step 1 ran `test_processing_routes.py` alone, 146 passed, +4:
  the encoded-cookie tests; two of them fail without the fix). Pre-commit clean on every
  changed file (black reformatted `test_singers.py` twice; re-run clean).
- **ui-check:** not applicable (server only; Phase 3).
- **Review findings** (numbers from the 2.1 table): 1, 2, 3, 4, 5, 8, 9, 10, 12, 13, 14, 15
  fixed in steps 1-5; 6 and 7 accepted as written in the plan (Design "Accepted edges", Phase 2
  "Known property"); 11 not taken (ruling 8). Step 1 settles the Phase 2 "Found, not fixed" and
  Ken's call there.
- **Checked beyond the new tests:**
  - With the old move order (queue emits inside `rename_user`), two new tests in
    `test_karaoke_rename_singer.py` fail (songs split when a `queue_update` handler raises; two
    `now_playing_update` where one is wanted).
  - With `play_file` reading the `vocal_volume` preference again, the `play_file` test fails
    (`0.9 == 0.15`).
  - The capped run loop ends an empty-queue run after 20 passes (a scratch test, deleted).
  - The real `pikaraoke.app` object: a join, a 422 on `semitones` 9, and a rename sent with
    the token cookie alone gives 200, keeps the token, and calls `rename_singer("Mary Ann",
    "Mary Anne")` once.
- **Deviations from the plan:**
  1. **The plan edit was not committed.** Ken's prompt named the Phase 2.1 plan commit as HEAD,
     but HEAD was `731d5ec` and `plans/singer-defaults.md` was modified in the working tree.
     I committed it unchanged as `522f946` before step 1, so the code commits carry no plan
     edits.
  2. **The `name_limit` page-state key and its test moved from step 2 to step 4.** Step 2's
     list asks for the key, but `NAME_LIMIT` is step 4's constant, and a key advertising a
     limit nothing enforces would not stand alone in the step 2 commit.
  3. **One more route test deleted in step 2.** "A phone whose name someone else took has not
     joined" duplicates "a token nobody holds has not joined" now that the phone is its token.
     "A wrong token on a known name" is kept (a join, so 409), renamed.
  4. **`test_singers.py` was rewritten, not patched**: `join` and `update` tests became
     `save` tests with the same coverage of taken, reserved and Anon names, plus new `lookup`,
     `house_defaults`, stale-token and `on_rename`-raises tests, and a Unicode section in step
     4.
- **Known properties (new):**
  - The rename's notifications (`queue_update`, the overlay refresh, `now_playing_update`) now
    run under the registry lock, after every move. Their handlers only `socketio.emit` the Now
    Playing data, so none reaches the registry; a handler that rendered a page would deadlock
    on the non-reentrant lock. Documented on `SingerRegistry`.
  - The `NAME_LIMIT` check counts the characters of the raw form value, before the strip and
    before NFC. A 30-character name with trailing spaces gets 422, and so does a 30-letter
    name sent with decomposed accents (each accent counts). The form's `maxlength` (Phase 3)
    counts UTF-16 units, so it is never looser than the server.
- **Self-review:** steps 2 and 3 are multi-file concurrency again (registry lock held across
  the queue, tracker and playback locks and now the notifications), so the review stays
  tracked as pending for the checkpoint after this phase.
- **Not done:** `graphify update .` (no `graphify-out/` on this box).

### Phase 2.2: review fixes of 2.1 (executed 2026-11-06, Claude Sonnet 5.5)

- **Commits:** `95a9567` `docs(plans): singer-defaults Phase 2.2 review fixes` (the plan edit,
  uncommitted at the start as the prompt said, committed alone first); step 1 `407f1b6`
  `fix(singers): a rename whose songs all moved always saves`; step 2 `474d332`
  `refactor(singers): one key rule for reserved names, and no re-key on a settings save`.
- **Tests:** full suite 3483 passed before and after both steps (step 1 rewrote one test, so
  no net new). Pre-commit clean on every changed file.
- **ui-check:** not applicable (server only).
- **Review findings** (numbers from the 2.2 table): 1, 4 and 6 fixed in step 1; 7 fixed in step
  2; 2, 5, 9 and 10 written into Design "Accepted edges" by the plan edit; 3 is Phase 3's
  (edit mode sends the name only when changed, with its check and Ken's check added to the
  plan); 8 and 11 accepted as the table says. Nothing else to build here.
- **Checked beyond the new tests:** with the catch removed from `Karaoke.rename_singer`, the
  rewritten test fails (`RuntimeError: socket gone` reaches the caller of `save`); with it,
  the save returns `("Michael", token)`, every copy and the registry say `Michael`, and one
  ERROR record names `'Mike' -> 'Michael'` and carries the traceback.
- **Not checked:** `MockKaraoke`'s new refusing `on_rename` is not exercised by any test (no
  current test renames through the mock, as the plan says); step 2 was not mutation-checked,
  only run against the existing taken, reserved, settings-only and case-only tests, as the
  plan chose.
- **Deviations from the plan:** none.
- **Known properties (changed):** `on_rename` must not raise. If a move ever did, the exception
  reaches the caller of `save` and the songs not yet moved stay under the old name, which is
  free again. Written on the `save` docstring. The notifications are the only part that can
  fail in practice, and they are caught.
- **Self-review:** step 1 adds a catch after the moves and no lock or path; step 2 is a
  refactor. Both covered by the self-review above, so no review is pending from this phase
  (the review of Phase 2.1 has run; it produced this phase).
- **Not done:** `graphify update .` (no `graphify-out/` on this box).

### Phase 3: the form (executed 2026-11-06, Claude Sonnet 5.5)

- **Commits:** `f6e9aab` `feat(ui): join form for name, key and vocal volume`.
- **Tests:** full suite 3483 passed before, 3486 after (+3 in the new
  `tests/unit/test_singer_page.py`, see deviation 5). Pre-commit clean on every changed file.
  `test_search_render.py` (base.html on a bare `Flask` app, no context processor) still passes
  with the guarded `window.singer` line.
- **ui-check:** 55 checks passed on a phone viewport (390x844) against the real app, in one
  scripted run. Names used: `María José` (renamed to `María Josefa`, then `Marta Ñu`) and
  `Bob Ünal`. By plan item:
  - Fresh phone: the join form opens on `/`; titled "Join the party"; no Cancel; a background
    click and Escape leave it open; the nav links can't be clicked behind it; the vocal volume
    starts at the house 40% and the key at 0; typing stops at 30 characters; the key stops at
    +3. One POST for the join, then the navbar shows the name, the `user` cookie holds the
    decoded name and `singer_token` is set.
  - A taken name keeps the form open with the server's message under the name field and no
    reload: another case (`maría josé`), `Pikaraoke`, and the decomposed accents of the first
    name.
  - Add a song as `María José` (from Browse): it plays under that name with the key at +2, and
    the Now Playing key slider reads +2 and the controls show for the singer.
  - Edit mode (name opened through the burger menu on the phone): prefilled name, 70%, +2,
    Cancel; Cancel closes with no POST. Renaming to `María Josefa` posts once and moves the
    queued song, the held download, the Processing row and the playing song. The Processing
    row is still marked as the guest's (`mine`).
  - The `user` cookie set by hand to `maría josefa`, then to `somebody else`: the navbar shows
    the registry's name and the cookie is put back, after an SPA navigation and after a full
    load.
  - Two tabs: tab 1 renames to `Marta Ñu`; tab 2 (still holding `María Josefa`) changes only
    the key to +3 and saves. It posted `name=` (blank), the guest kept `Marta Ñu`, the queued
    songs stayed under it, the key saved as +3 and the cookie held the new name.
  - After six SPA navigations: one key click moves the key by exactly one, and one Save sends
    one POST.
  - App restarted: the next SPA navigation opens the join form (empty name, `joined` false)
    and joining again works in the new run.
- **Checked beyond the passes:**
  - With edit mode sending the typed name always, the two-tab checks fail (4 of them: the blank
    name, the kept name, the queued songs, the cookie), because tab 2 renames the guest back.
  - With the cookie put-back inside the ready handler instead of straight after
    `window.singer`, the full-load `/queue` check fails (that page's script read `somebody
    else`).
  - With `window.singer` written as a raw dict dump instead of `tojson`, the new test of a
    name that closes the script tag fails.
- **Deviations from the plan:**
  1. **The cookie put-back runs as the head script loads, not in its ready handler.** On a full
     load, a page script that reads the cookie while it loads (`queue.html`'s `currentUser`)
     runs before the ready handler, so it would still read the old spelling on that first
     page. The plan's purpose (the routes post the registry's spelling) holds better this way.
  2. **The key limit (-3 to +3) is in the markup** (`data-min` and `data-max` on the key field),
     not in the page state, which is fixed. The server still refuses beyond 3 with a 422.
     The number now lives in two places.
  3. **A hidden key control posts the key as it was** (the guest's saved key, 0 for a new
     guest), not a literal 0. Same result for every guest today.
  4. **Strings:** new: "Join the party", "Your name and settings", "Your name", "Key", the
     help line under the name field and "Could not save. Please try again.". Reused: "Vocal
     Volume", "Save", "Cancel". The help line is a new short text, so the old "Please enter
     your name. This will show up..." and the rename prompt texts are now unused in the
     catalogs (catalogs not regenerated, as the plan says).
  5. **Added, not in the plan:** `tests/unit/test_singer_page.py` (3 tests of the real
     `base.html` with the real context processor: the state line for a new phone and a joined
     one, and a name that closes the script tag stays inert). A name now reaches an inline
     script, which it never did before. Also two small fixes found in the phone screenshots:
     the burger menu closes when the name is clicked (it stayed open behind the form), and a
     gap between Save and Cancel.
- **Not checked:**
  - The vocal volume on Now Playing: the fake library has no stems (`dual_stem` false), so only
    the key was checked, as the plan allows. The form's vocal slider saved and came back as
    0.7 in the page state, and the playing song's controller reported 0.7.
  - A save whose reply is lost (the stale cookie was simulated by setting it by hand), the
    "Could not save" message (nothing produced a failure other than the 409), and a 422 (the
    field's `maxlength` stops it first).
  - The Info page and the login page (the form opens on every page that extends `base.html`,
    but only Home, Queue, Search, Browse and Processing were driven), a desktop-width window,
    and a real phone keyboard. Only the Home, Processing and join screenshots were looked at.
  - The held download was checked only in its download hold; a hold waiting on processing was
    not made.
  - The fake download is a scratch stub, not the real downloader: `run_app_held.py` in the
    session scratchpad is the skill's `run_app.py` plus a `sleep` in place of yt-dlp, so the
    check needed no network. The skill itself is unchanged; it could gain the stub if wanted.
- **Self-review:** four templates and scripts plus a test, a new UI flow around cookies and the
  SPA script re-run, so the review is tracked as pending for the checkpoint after this phase.
- **Not done:** `graphify update .` (no `graphify-out/` on this box).
