# Queue hold: a searched song takes its queue slot at the click

Model: Claude Opus 5.5 (2026-10-27), written for a Claude Sonnet executor.

Branch `queue_hold`, off `dev` at `e9c7922`. It assumes `search_caption_check`
has landed on `dev` first (Phase 0 checks).

## The problem

With "Add to queue once downloaded" ticked, the download worker adds the song
to the queue the moment yt-dlp finishes (`DownloadManager._execute_download`),
before processing has started. The run loop plays any non-paused queue item, so
a song can reach the front and play with the mixed audio, no vocal slider and
no word timing. Playback reads its files once at the start, so the song stays
that way even if processing finishes mid-song. The manual Add button
(`routes/queue.py::_do_enqueue`) refuses a `pending` song, but the download path
never goes through that check.

## Rulings (Ken, 2026-10-27)

1. **The slot is taken at the click**, not when the download ends. The queue
   keeps playing ready songs past a held slot, and the held song plays from
   that slot once it is ready.
2. **A singer's ready song takes their earliest held turn.** When the next song
   to play has an earlier held song by the same singer, the two swap places:
   the ready one plays and the held one moves back to its slot. This applies
   with round-robin on or off.
3. **Processing order is unchanged**: still first come, first served, with
   downloads ahead of regen jobs. Ordering processing by queue position was
   considered and left for later.
4. **The checkbox stays, relabelled "Add to queue".** Ticked (the default)
   means a held slot at the click. Unticked means a library-only download.
   Playlist adds stay library-only.
5. **Removing a held song from the queue only frees its slot.** Its download
   and processing keep running and the song still lands in the library.
   Cancelling stays on the Processing page.

Carried from the discussion that led here (not objected to):

- **Processing fails**: the song comes off the queue and the singer gets a
  notice. This matches the manual button, which refuses `failed`.
- **Blocked-words title** (processing skipped): it plays as-is, as it does today.
- **Needs a lyrics pick**: it keeps its slot and shows what it is waiting for.
- **Manual Add on a song still processing**: it gets a held slot instead of
  the 409, as long as it really is waiting on processing or on a pick.

## Design

### The held item

A queue item gains one key, `"waiting"`. It is always present (the queue JSON
goes to the browser):

| `waiting` | meaning | `file` holds |
| --- | --- | --- |
| `None` | ready; plays unless `paused` | library path |
| `"download"` | download queued or running | the video URL |
| `"processing"` | on disk, processing queued or running | library path |
| `"pick"` | on disk, waiting for the admin's lyrics pick | library path |

While a song downloads, `file` holds the video URL. That is deliberate: every
queue route and the queue page identify an item by `file` (`queue_edit`,
`move_to_top`, `toggle_pause_song`, `_verify_ownership`, the row's `data-file`),
so deleting, reordering and pausing a held song work with no route changes. A
URL never equals a library path, so the `is_song_in_queue` guards on
delete/rename in `routes/files.py` and `batch_song_renamer.py` are unaffected.

**Invariant:** an item becomes playable (`waiting` set to `None`) only after
`file` is a library path. When a download lands, set `file` first and then
change `waiting` from `"download"` to its next value. Both writes are plain
dict assignments and the item stays unplayable throughout. `QueueManager` has
no lock (upstream), and this ordering is what keeps the run loop from ever
popping a URL.

Round-robin needs no change. `_calculate_fair_queue_position` counts every
item by user, held ones included, so a held song holds its singer's round and
later songs fill in around it. The per-user limit (`is_user_limited`) also
counts held items, which is correct because each one is a request.

### Who does what

- **`QueueManager`** (upstream, smallest change):
  - `enqueue` takes `waiting` and `title`.
  - New `is_playable(item)`. It is the one check that `pop_next`,
    `has_playable_song` and `karaoke.py`'s two up-next readers use.
  - The swap from ruling 2 goes in `pop_next`.
- **`QueueHold`** (new, `pikaraoke/lib/queue_hold.py`). It owns the lifecycle
  of a held item: it listens to download and processing events and edits
  queue items.
- **`DownloadManager`** (upstream) stops adding to the queue. Its
  `queue_manager` dependency becomes dead and is removed.
- **`PipelineTracker`** (fork) announces download cancels, which today emit
  nothing.
- **`routes/queue.py::_do_enqueue`** (upstream) holds a `pending` song that is
  really waiting, instead of returning 409.

### Event map for `QueueHold`

| event (payload) | action |
| --- | --- |
| `download_queued` (`{video_url, enqueue, user, title}`) | if `enqueue`: `enqueue(video_url, user, waiting="download", title=title)`; on `[False, msg]` emit `notification` `msg` `"warning"` (the download still runs, library-only) |
| `song_downloaded` (`song_path`) | find the `"download"` item whose URL's video ID matches the path's; if another item already has `file == song_path`, delete the held one and notify "already in the queue"; else `file = song_path`, then `waiting = "processing"` |
| `needs_pick` (`song_path`) | held item at that path -> `waiting = "pick"` |
| `processing_queued` (`song_path`) | held item at that path -> `waiting = "processing"` (after a pick) |
| `processing_complete` (`{song_path, ...}`) | release: `waiting = None` |
| `processing_skipped` (`song_path`) | release |
| `processing_error` (`{song_path, error}`) | delete the held item; notify the singer, `"danger"` |
| `processing_cancelled` (`song_path`) | delete the held item, no toast |
| `song_deleted` (`song_path`) | delete the held item, no toast |
| `download_error` (`{url, error}`) | delete the held item with `file == url`; no toast (`DownloadManager` already toasted) |
| `download_cancelled` (`{url}`) (new) | delete the held item with `file == url`, no toast |

"Held item" always means an item whose `waiting` is not `None`. Never touch a
ready item, because `processing_complete` also fires for regen jobs of songs
already in the queue. Delete through `queue_manager.queue_edit(file, "delete")`,
which emits `queue_update` and `now_playing_update`. A release or a `waiting`
change emits both events itself.

**Wiring order matters.** `LibraryTools.on_song_downloaded` can emit
`processing_skipped`, `needs_pick` or `processing_queued` synchronously, inside
the `song_downloaded` dispatch. `QueueHold`'s `song_downloaded` handler must run
before it, or those events arrive while the item still holds a URL and match
nothing. In `karaoke.py`, construct `QueueHold` after `LibraryTools` and before
the line `self.events.on("song_downloaded", self.library_tools.on_song_downloaded)`.

## Phases

General rules for the executor:

- Quoted code is the anchor. A line-number offset alone is not a STOP; a quote
  that is not found is.
- Tests: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Use real
  `EventSystem` and `PreferenceManager` instances, as in CLAUDE.md.
- One commit per phase (Phase 5 is plan-only). Run the full suite before each
  commit, then read `git diff --cached`.
- Do not touch translation catalogues. New strings are wrapped in `_()` or
  `{% trans %}` and nothing more.
- Do not start on processing order (ruling 3).

### Phase 0: base

1. `git log dev --format=%s` must show the four `search_caption_check` code
   commits (cherry-picked, so the hashes differ):
   - `feat(search): check the caption before the picker offers it`
   - `fix(library): gate a picker caption choice after the download`
   - `fix(search): no note when the caption check finds no caption`
   - `refactor(library): one watch_url for library_regen and library_tools`

   If any is missing, **STOP**: Ken has not landed it, and Phase 4 edits the
   same template.
2. `git rebase dev` (this branch holds only this plan).
3. Run the full suite and note the pass count for the Results log. Known
   pre-existing failures are not this plan's concern, but record them.

### Phase 1: the queue can hold an item (`queue_manager.py`, `karaoke.py`)

1. `QueueManager.enqueue`: add the keyword parameters `waiting: str | None = None`
   and `title: str | None = None`. Use `title` when given, else
   `self._resolve_title(song_path)`. Add `"waiting": waiting` to the
   `queue_item` dict (anchor: `queue_item = {` ... `"paused": False,`).
   Everything else in `enqueue` is unchanged.
2. Add:

   ```python
   @staticmethod
   def is_playable(item: dict[str, Any]) -> bool:
       """Neither paused by its singer nor held for download or processing."""
       return not item.get("paused", False) and not item.get("waiting")
   ```

   Use it in `has_playable_song` and `pop_next` in place of
   `not item.get("paused", False)`.
3. The swap from ruling 2, in `pop_next`. After finding the first playable
   index `idx`, look for the earliest `j < idx` with
   `self.queue[j]["user"] == self.queue[idx]["user"]`, `self.queue[j].get("waiting")`
   truthy, and not paused. If found, swap the two entries and pop at `j`
   instead. Extend the docstring by one sentence on why (turns belong to
   singers). Paused items never swap.
4. `karaoke.py`: the two readers that filter on `paused` use
   `QueueManager.is_playable` instead:
   - `_get_queue_preview`, anchor `if not item.get("paused", False)` inside the
     `QueuedSong(...)` generator.
   - `get_now_playing`, anchor
     `next_song = next((item for item in queue if not item.get("paused", False)), None)`.
5. Tests in `tests/unit/test_queue_manager.py`:
   - `pop_next` and `has_playable_song` skip a held item and leave it in place.
   - The swap fires with round-robin on and off; it does not fire for another
     singer's held item or for a paused item; with two held items by the same
     singer, the earliest one moves.
   - Round-robin counts a held item in its singer's round.
   - `enqueue(..., title=...)` uses the given title.
   - Every new item has `"waiting"`.

Commit: `feat(queue): queue items can be held until ready`.

### Phase 2: hold the slot at the click

1. **`download_manager.py`**
   - In `_execute_download`'s success branch, delete the final
     `if enqueue:` block that calls `self._queue_manager.enqueue(...)`.
     Replace its `else` (song file not found) with an emit of
     `download_error` (`{"url": video_url, "error": "Downloaded file not found"}`),
     so the tracker row and any held slot both end, whether or not `enqueue`
     was set.
   - The success toast before it collapses to the single
     `_("Downloaded: %s")`. The "Downloaded and queued" branch goes, because
     the song was queued at the click.
   - Remove the now-unused `queue_manager` constructor parameter, its
     `self._queue_manager`, its import and its docstring line. Update the
     `DownloadManager(...)` call in `karaoke.py` and the test fixtures.
   - The `enqueue` argument stays: it rides on `download_queued`. Update its
     docstrings to "hold a playback-queue slot for the song".
2. **`pipeline_tracker.py`**: in `cancel()`, the `download_status == "active"`
   and `"pending"` branches emit `download_cancelled` (`{"url": item.url}`).
   Collect the URL under the lock and emit after it, as the method already
   does for file I/O. `remove()` routes through `cancel()`, so it is covered.
3. **`pikaraoke/lib/queue_hold.py`**: class `QueueHold(queue_manager, events,
   library_tools)` with a module docstring that states the invariant and the
   wiring-order requirement in one sentence each.
   - Subscribe to the event map in its constructor.
   - Match a download by video ID: `get_youtube_id_from_url(item["file"])`
     against `extract_youtube_id(song_path)`. Both helpers exist; do not write
     a third.
   - Notification strings:
     - processing error: `_("%s couldn't be processed and was taken off the queue")`
     - duplicate download: `_("Already in the queue: %s")`
   - No lock (see the invariant). A handler that finds no held item returns
     quietly.
4. **`karaoke.py`**: `self.queue_hold = QueueHold(...)` between the
   `LibraryTools(...)` construction and the
   `self.events.on("song_downloaded", self.library_tools.on_song_downloaded)`
   line. Rewrite the comment above that line to say that the tracker and the
   queue hold both hear `song_downloaded` before LibraryTools.
5. **Tests**:
   - New `tests/unit/test_queue_hold.py`: a real `EventSystem`, a real
     `QueueManager` and a real `PreferenceManager`; mock `library_tools`. Emit
     each event in the map and assert the item's `file` and `waiting`, or that
     it is gone, plus the toast where the map has one.
   - The ordering case: subscribe a stand-in for `on_song_downloaded`
     *after* `QueueHold` that emits `processing_skipped` synchronously, and
     assert the item is released.
   - `download_queued` with `enqueue=False` adds nothing; a user at their limit
     gets the warning and no item.
   - `test_download_manager.py`: the enqueue-after-download tests
     (`test_execute_download_with_enqueue`,
     `test_execute_download_enqueue_without_path`,
     `test_execute_download_special_characters_enqueue`) are superseded.
     Rewrite them to assert no queue call is made, that the file-not-found case
     emits `download_error`, and that special-character filenames still emit
     `song_downloaded` with the right path. Delete what no longer tests
     anything.
   - Tracker test: cancelling a pending and an active download emits
     `download_cancelled` with the URL.

Commit: `feat(queue): a searched song holds its queue slot from the click`.

### Phase 3: the manual Add button holds a song still processing

1. `library_tools.py`: add public `is_waiting_for_pick(song_path) -> bool`
   (reads `_needs_pick` under `_state_lock`).
2. `QueueHold.waiting_for(song_path) -> str | None`:
   - `"pick"` when `library_tools.is_waiting_for_pick`
   - `"processing"` when `library_tools.is_busy`
   - else `None`

   Check pick first: a picked song is busy *and* still listed until it finishes.
3. `routes/queue.py::_do_enqueue`: split the gate. `"failed"` still returns
   409. `"pending"` asks `k.queue_hold.waiting_for(song)`: on `None` it returns
   the same 409 as today (a pending song nothing will finish); otherwise it
   calls `enqueue(song, user, waiting=...)`. Update the gate comment.
4. Tests in `test_queue_routes.py`:
   - The existing `test_pending_song_rejected_with_409` keeps its meaning with
     `waiting_for` returning `None`.
   - Add a pending song waiting on processing (held, 200) and one waiting on a
     pick (held as `"pick"`).
   - Add `QueueHold.waiting_for` unit cases to `test_queue_hold.py`.

Commit: `feat(queue): Add holds a song that is still processing`.

### Phase 4: what people see (`queue.html`, `search.html`)

1. `queue.html::generateQueueRow`: when `e.waiting`, add a tag after the
   title, next to the `paused` one and in its style but `is-info is-light`:
   - `"download"`: `{{ _("downloading") }}`
   - `"processing"`: `{{ _("processing") }}`
   - `"pick"`: `{{ _("waiting for lyrics") }}`

   Give the row a `row-waiting` class with the same rules as `row-paused`:
   add `.row-waiting` to the existing `.row-paused` selectors. Do not invent a
   second style. The options buttons are unchanged (they key on `file`).
2. `search.html`: both checkbox labels change from
   `Add to queue once downloaded` to `Add to queue` (the `#add-to-queue-direct`
   and `#add-to-queue-search` labels). Update the restore comment's wording.
   **Keep the cookie name `add-to-queue-on-download`**; renaming it would reset
   every guest's saved choice.

No test for the templates beyond the existing render tests passing. If a
render test asserts the old label, update it.

Commit: `feat(queue): show held songs in the queue; relabel the search checkbox`.

### Phase 5: close out

1. Run pre-commit (`pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`)
   and the full suite. Fix only what this branch introduced.
2. Self-review the whole branch diff on the three CLAUDE.md axes. Check in
   particular:
   - Nothing reads `item["file"]` as a path without `is_playable` or a
     `waiting` check first.
   - No `paused`-only filter is left in `queue_manager.py` or `karaoke.py`
     (`grep -n 'get("paused"'`).
   - `download_manager.py` has no `queue_manager` left.
3. Fill the Results log below (one row per code commit, plus suite counts)
   and commit it plan-only: `docs(plan): record the queue hold build`.
4. **Stop and report.** This is a multi-file change touching the core queue
   and threads, so per CLAUDE.md a `/code-review` is now pending. Say so and
   do not run it. Flag this as a good `/compact` point.

## Behaviour changes worth knowing

- **Two toasts at the click.** A queued search download shows "Download
  starting" and then "<user> added to the queue". The completion toast is now
  just "Downloaded".
- **A held song can sit at the front of the queue.** The queue plays past it,
  and the TV's "up next" names the next playable song, not the held one.
- **A song waiting for a pick holds its slot until an admin picks or someone
  removes it.**
- **Round-robin is unchanged.** Held songs count toward a singer's round and
  toward the per-user limit.
- **A restart drops held slots**, along with the rest of the queue (it is in
  memory, as today).
- **A successful download whose file cannot be found** now marks its
  Processing-page row as an error. Before, the row was left waiting forever.

## Test plan (manual)

- [ ] Ticked, search and download a new song while another song plays: it
  appears in the queue at once tagged "downloading", then "processing", and
  the queue plays past it.
- [ ] When it finishes processing it plays from its slot, with the vocal
  slider and word timing.
- [ ] Round-robin on, two singers: A's first song is held and A's second (a
  library song) comes up first. A's library song plays in A's earlier turn and
  the held one moves back.
- [ ] Unticked: the song downloads and processes but is not queued.
- [ ] Remove a held song from the queue (as its singer and as admin): the
  download and processing carry on and the song lands in the library.
- [ ] Cancel a held song's download on the Processing page: it leaves the
  queue.
- [ ] A download that needs a lyrics pick shows "waiting for lyrics" and plays
  after the pick and processing.
- [ ] Add a library song that is still processing via the file browser: it is
  held (no "song is pending" error).

## Results log

| date | commit | what |
| --- | --- | --- |
| 2026-10-27 | (Phase 0) | `dev` carries the four caption-check commits (`640a661`, `dadecd0`, `7b07fc8`, `f4aa97b`); rebased onto `c48a3ea`; baseline 2298 passed, 0 failed |
| 2026-10-27 | `8e72f27` | Phase 1: `waiting` key, `is_playable`, the swap in `pop_next`, the two up-next readers; 2316 passed (+18) |
| 2026-10-27 | `12d539c` | Phase 2: hold at the click, `QueueHold`, `download_cancelled`, `DownloadManager` off the queue; 2345 passed (+29) |
| 2026-10-27 | `a94441d` | Phase 3: manual Add holds a song still processing or waiting for a pick; 2354 passed (+9) |
| 2026-10-27 | `17a5844` | Phase 4: held-row tag and dimming, "Add to queue" label; 2354 passed (templates only, no test change) |

Final: full suite 2354 passed, 0 failed. `pre-commit --all-files` clean on this branch's files.

### Where the build departs from the text above

- **`scripts/add_songs.py`** also built a `DownloadManager` (with
  `queue_manager=None`); that argument was removed with the parameter.
- **`_execute_download` keeps `enqueue` and `user`** (unused there now). The
  plan did not list them for removal, and `scripts/add_songs.py` and its test
  stub call the four-argument form.
- **`LibraryTools.is_waiting_for_pick` is "listed and not yet picked"**, not
  just "listed". A picked song stays listed while its job waits or runs, so a
  plain listed check would have labelled a processing song "waiting for
  lyrics". It reuses the existing `_is_picked`; the pick-first order in
  `QueueHold.waiting_for` is as planned.
- **Phase 2 duplicate toast** uses level `"warning"` (the plan gave no level).

### Left for the review

- `queue.html` puts `e.title` and `e.user` into the page unescaped. A held
  item's title is now the title the browser posted with the download, not one
  derived from the filename.
- A manual Add of a pending song reads `waiting_for` and then enqueues. If
  processing finishes between the two, the item is held with nothing left to
  release it. The window is a few microseconds.
- `pre-commit --all-files` on `dev` rewrites `pikaraoke/lib/args.py` (an unused
  `os` import) and `plans/open-issues.md` (a re-wrapped list). Not from this
  branch; reverted, not committed.
