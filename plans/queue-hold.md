# Queue hold: a searched song takes its queue slot at the click

Model: Claude Opus 5.5 (2026-10-27), written for a Claude Sonnet executor.
Phase 5.1 (review fixes) added 2026-10-27 by Claude Opus 5.5 after the
`/code-review` of Phases 1-4.

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
2. **A singer's ready song takes their earliest held turn.** When a held song's
   turn comes up and its singer has a later ready song, the two swap places:
   the ready one plays in that turn and the held one moves back to the ready
   one's slot. This applies with round-robin on or off. (Wording corrected
   2026-10-27. The first wording, "when the next song to play has an earlier
   held song", led to Phase 1's swap, which never changes what plays; Phase
   5.1a replaces it.)
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
| `processing_cancelled` (`song_path`) | delete the held item, no toast (from Phase 5.1c it also fires when the tracker cancels a job that is still waiting) |
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
   **Superseded by Phase 5.1a.** Every item before the first playable one is
   already skipped, so this swap never changes which song plays; it only
   reorders held songs among themselves. Plan error, not an executor one.
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

### Phase 5.1: review fixes (after the `/code-review` of Phases 1-4)

The review (2026-10-27, three finder angles) found seven defects, and Ken
ruled that all seven are fixed. Each step below is one commit, with its tests
in the same commit, in this order. The general rules above still apply. Run
the full suite before each commit.

| step | finding | fix |
| --- | --- | --- |
| 5.1a | the swap never changes what plays (ruling 2 not delivered) | a held song's turn goes to its singer's later ready song; "up next" uses the same selection |
| 5.1b | no lock: a worker thread's scan can miss an item mid-move and lose its release | one queue lock (an `RLock`) taken by every queue change and by `QueueHold`; `queue_clear` emits outside it |
| 5.1c | cancelling a processing job that is still waiting announces nothing, so a held song is stuck | the tracker emits `processing_cancelled` for it |
| 5.1d | a manual Add can hold a song after its release event has already fired | `QueueHold.settle` re-reads the state after the hold |
| 5.1e | a download that crashes, or whose file is missing, leaves the slot held or removes it silently; `_execute_download` keeps dead parameters | crash: `download_error` plus a red toast; missing file: red toast instead of green; drop `enqueue`/`user` from `_execute_download` |
| 5.1f | titles and singer names go into the page as raw HTML | one `escapeHtml` in `base.html`, used on the queue and home pages |
| 5.1g | - | close out |

#### 5.1a: a ready song plays in its singer's held turn (`queue_manager.py`, `karaoke.py`)

1. In `QueueManager`, replace the body of `pop_next` and delete
   `_earliest_held_turn`. Add `upcoming` and `_take_next`:

   ```python
   def pop_next(self) -> dict[str, Any] | None:
       """Remove and return the next song to play from the queue.

       Paused and held songs stay in place; see _take_next for how a held
       song's turn is used. Returns None if no remaining song is playable.

       Does not emit queue_update to avoid UI flicker during song transitions.
       The playback system emits now_playing events which trigger queue UI updates.
       """
       song = self._take_next(self.queue)
       if song is not None:
           logging.info(f"Popped song from queue: {song['title']}")
       return song

   def upcoming(self, count: int) -> list[dict[str, Any]]:
       """The next ``count`` songs in the order pop_next will play them, as the queue stands."""
       remaining = list(self.queue)
       songs: list[dict[str, Any]] = []
       while len(songs) < count and (song := self._take_next(remaining)) is not None:
           songs.append(song)
       return songs

   @staticmethod
   def _take_next(queue: list[dict[str, Any]]) -> dict[str, Any] | None:
       """Remove and return the song that plays next from ``queue``.

       Turns are taken in queue order. A playable song plays in its own turn.
       An unpaused held song's turn goes to its singer's first later playable
       song, which swaps places with it: turns belong to singers, so the ready
       song plays now and the held one moves back to its slot.
       """
       for turn, item in enumerate(queue):
           if QueueManager.is_playable(item):
               return queue.pop(turn)
           if item.get("waiting") and not item.get("paused", False):
               later = next(
                   (
                       idx
                       for idx in range(turn + 1, len(queue))
                       if queue[idx]["user"] == item["user"]
                       and QueueManager.is_playable(queue[idx])
                   ),
                   None,
               )
               if later is not None:
                   queue[turn], queue[later] = queue[later], queue[turn]
                   return queue.pop(turn)
       return None
   ```

2. `karaoke.py`: both up-next readers use `upcoming`, so "up next" names the
   song that will actually play.
   - `_get_queue_preview`: build the tuple from
     `self.queue_manager.upcoming(5)` (anchor
     `if QueueManager.is_playable(item)` inside the `QueuedSong(...)`
     generator). The `[:5]` slice goes.
   - `get_now_playing`: anchor
     `next_song = next((item for item in queue if QueueManager.is_playable(item)), None)`.
     Replace it with `upcoming = self.queue_manager.upcoming(1)` and
     `next_song = upcoming[0] if upcoming else None`. Drop
     `queue = self.queue_manager.queue` if nothing else uses it.
3. Tests in `tests/unit/test_queue_manager.py`:
   - **Rewrite** `test_ready_song_takes_the_singers_earliest_held_turn`, which
     asserts the old behaviour. Queue `[held(User1), b1(User2), a2(User1)]`:
     the first pop is `a2`, then the queue is `[b1, held]`.
   - Round-robin on, as `test_round_robin_counts_a_held_item_in_its_singers_round`
     builds it, plus a third singer: A's ready song plays first, and the held
     one ends up in that song's old slot.
   - A held song with no later ready song by its singer: the next singer's
     song plays and the held song stays first.
   - `upcoming(n)` on a mixed queue (two singers, one paused song, one held
     song with a later ready song, one held song without) equals the songs that
     repeated `pop_next` calls return on a copy, and leaves `queue` unchanged.
   - `test_held_song_moves_back_to_the_ready_songs_slot`,
     `test_the_earliest_of_two_held_items_moves`,
     `test_no_swap_for_another_singers_held_item` and
     `test_no_swap_for_a_paused_held_item` should pass unchanged. If one fails,
     STOP and report it; do not edit it to pass.
   - `tests/unit/test_karaoke_utils.py`, next to
     `test_get_now_playing_with_queue`: with a held song by A first, then B's
     song, then A's ready song, `up_next` is A's ready song.

Commit: `fix(queue): a ready song plays in its singer's held turn`.

#### 5.1b: one queue lock (`queue_manager.py`, `queue_hold.py`)

1. `queue_manager.py`: in `__init__`, add `self.lock = threading.RLock()` with
   a one-line comment saying that QueueHold changes items from worker threads.
   Add a module-level decorator:

   ```python
   def _locked(method: Callable[..., Any]) -> Callable[..., Any]:
       """Run a queue change under the queue lock.

       QueueHold changes held items from the download and processing threads
       while routes and the run loop change the queue.
       """

       @functools.wraps(method)
       def locked(self: QueueManager, *args: Any, **kwargs: Any) -> Any:
           with self.lock:
               return method(self, *args, **kwargs)

       return locked
   ```

   Put `@_locked` on exactly these methods: `enqueue`, `reorder`,
   `move_to_top`, `move_to_bottom`, `pop_next`, `upcoming`,
   `toggle_pause_song`, `toggle_pause_user`, `queue_edit`. Use one decorator
   line each and do not re-indent the bodies; that keeps the upstream diff
   small. `queue_add_random` changes the queue only through `enqueue`, and the
   read-only methods stay unlocked.

   `queue_clear` gets no decorator. Wrap only its `self.queue = []` line in
   `with self.lock:`, keeping the `notification` emit before it and the
   `queue_update`, `now_playing_update` and `skip_requested` emits after it,
   in today's order. Reason: `skip_requested` runs `PlaybackController.skip`,
   which takes `_playback_lock`. `play_file` holds `_playback_lock` while it
   refreshes the overlay, and the refresh reads `upcoming`. Emitting
   `skip_requested` under the queue lock would deadlock a Clear that lands
   while a song is starting.

   (Revised 2026-10-27 by Claude Opus 5.5. The first version decorated
   `queue_clear` as a whole. The executor's step 3 check stopped on that
   deadlock before any 5.1b code was written. Options considered: leave
   `queue_clear` unlocked, which lets a `pop_next` that is mid-way through the
   old list play a song from a cleared queue; make the preview readers
   lock-free, which still leaves a Clear holding the queue lock for the
   seconds `play_file` takes; emit `skip_requested` from a separate thread,
   which adds a thread for no gain over locking only the assignment.)
2. `queue_hold.py`: wrap the bodies of `_on_song_downloaded`, `_set_waiting`,
   `_on_processing_error` and `_drop` in `with self._queue_manager.lock:`.
   Each find-and-change is then one step for the other threads.
   `_on_download_queued` needs nothing, because `enqueue` locks itself. Delete
   the "No lock (see the invariant)" wording wherever it appears in
   `queue_hold.py`. The module docstring's invariant stays, since the run loop
   still relies on it.
3. **Lock-order check (STOP if any fails).** Nothing that runs while the
   queue lock is held may take another lock. Confirm each of these by reading
   the code:
   - the `get_now_playing_user` lambda in `karaoke.py` only reads an attribute;
   - `Karaoke.get_now_playing` -> `PlaybackController.get_now_playing` takes
     no lock;
   - `update_now_playing_socket` and the `queue_update` lambda in `karaoke.py`
     only emit over Socket.IO;
   - inside its locked blocks, `QueueHold` calls only `QueueManager` methods
     and `events.emit`;
   - no `@_locked` method emits `skip_requested` (only `queue_clear` emits it,
     after its lock is released), and no handler of `notification`,
     `queue_update` or `now_playing_update` takes `_playback_lock`.

   Holders of `_playback_lock` (`play_file`, `skip`, the mpv song-end
   callback) may reach the queue lock through the overlay preview or a
   `now_playing_update`. That is the only allowed direction: nothing may hold
   the queue lock and then wait for `_playback_lock`.
4. Tests:
   - `test_queue_manager.py`: while the test holds `qm.lock`, a `pop_next`
     started on another thread does not finish (`threading.Event`, wait 0.1 s);
     once the lock is released it finishes (wait 1 s).
   - `test_queue_manager.py`, in `TestQueueManagerClear`: `skip_requested`
     fires with the queue lock free. The probe runs on another thread because
     the lock lets its own holder take it again:

     ```python
     def test_queue_clear_emits_skip_requested_after_releasing_the_lock(self, queue_manager):
         """skip_requested takes the playback lock, so the queue lock must be free by then."""
         lock_free = []

         def probe():
             acquired = queue_manager.lock.acquire(blocking=False)
             if acquired:
                 queue_manager.lock.release()
             lock_free.append(acquired)

         def on_skip():
             thread = threading.Thread(target=probe)
             thread.start()
             thread.join()

         queue_manager._events.on("skip_requested", on_skip)
         queue_manager.enqueue("/songs/song1---abc.mp4", "User1")

         queue_manager.queue_clear()

         assert lock_free == [True]
     ```
   - `test_queue_hold.py`: the same pattern for a `processing_complete`
     release.

Commit: `fix(queue): one lock for the queue and the held items`.

#### 5.1c: cancelling a waiting processing job frees its slot (`pipeline_tracker.py`)

1. In `PipelineTracker.cancel()`, take the branch anchored at
   `elif item.song_path and item.processing_status == "pending":`. Collect
   `item.song_path` into a new local `cancelled_song` under the lock, beside
   `cancelled_download_url`. After the lock, and after the `_delete_song` call,
   emit `self._events.emit("processing_cancelled", cancelled_song)`. Update the
   docstring sentence on what is done outside the lock so it covers both
   cancel events.
2. Why this is safe, so it is not re-checked: the only listeners are
   `QueueHold._drop` and the tracker's own `_on_processing_cancelled`. The
   tracker's handler matches only rows marked `cancelling`, and this row has
   already been removed, so it only refreshes. A `download` row's song
   deletion also fires `song_deleted`, and a second drop finds nothing.
   `ProcessingManager.cancel_pending` must not emit it itself, because the
   tracker calls it while holding `_lock` and the tracker's handler takes
   `_lock`.
3. Tests, next to the existing tracker cancel tests in
   `tests/unit/test_processing_routes.py` (where `download_cancelled` is
   tested): cancelling a waiting `process` row emits `processing_cancelled`
   with its path. In `test_queue_hold.py` or the same file, with a real
   `QueueHold` wired: a song held as `"processing"` (manual Add) leaves the
   queue when its waiting job is cancelled.

Commit: `fix(queue): cancelling a waiting job frees its held slot`.

#### 5.1d: a manual Add that races processing settles (`queue_hold.py`, `routes/queue.py`, `karaoke.py`)

1. `QueueHold.__init__` takes `song_manager: SongManager` (stored as
   `self._song_manager`). Pass `song_manager=self.song_manager` in
   `karaoke.py`, and update the test fixtures.
2. Add:

   ```python
   def settle(self, song_path: str) -> None:
       """Release or drop a song a manual Add has just held, if its event came first.

       The Add reads the song's state and then holds it. Processing can finish
       or fail in between, and its event then finds nothing to change.
       """
       state = self._song_manager.get_pipeline_state(song_path)
       if state == "failed":
           self._on_processing_error({"song_path": song_path})
       elif state != "pending":
           self._release(song_path)
   ```

3. `routes/queue.py::_do_enqueue`: right after
   `rc = k.queue_manager.enqueue(song, user, waiting=waiting)`, add
   `if waiting and rc[0]: k.queue_hold.settle(song)`.
4. Do **not** make `settle` drop a `pending` song that nothing seems to be
   finishing. During a pick (`picking` is set and the job is not yet queued),
   a song is neither waiting for a pick nor busy, but it is about to be
   processed.
5. Tests:
   - `test_queue_hold.py`: `settle` with the state `"ready"` releases, with
     `"skipped"` releases, with `"failed"` removes the song and sends the
     danger toast, and with `"pending"` leaves it held.
   - `test_queue_routes.py`: a pending, busy song whose state reads
     `"pending"` and then `"ready"` (`side_effect`) ends up in the queue
     released.

Commit: `fix(queue): a manual Add that races processing does not strand the song`.

#### 5.1e: a failed download says so and frees its slot (`download_manager.py`)

1. `_process_queue`: in the `except Exception as e:` branch after
   `self._execute_download(...)`, keep the log line and add two lines: a
   danger toast with the existing msgid, and the error event.

   ```python
   # MSG: Message shown after the download process is completed but the song is not found
   self._events.emit(
       "notification",
       _("Error downloading song: ") + (download_request["title"] or video_url),
       "danger",
   )
   self._events.emit("download_error", {"url": video_url, "error": str(e)})
   ```

   Import `_` locally, the way `queue_download` and `_execute_download` do
   (`from flask_babel import _`). The tracker marks the row as an error and
   QueueHold frees the slot. If the exception came after `song_downloaded`,
   both find nothing to change.
2. `_execute_download`'s success branch: move the
   `_("Downloaded: %s")` success toast (and its `# MSG:` comment) inside
   `if song_path:`, as its first statement. In the `else` branch, before the
   `download_error` emit, send the danger toast
   `_("Error downloading song: ") + displayed_title`, reusing that existing
   msgid and its `# MSG:` comment. The QueueHold docstring "the download side
   has told the user" is then true; leave it.
3. Drop the dead `enqueue` and `user` parameters from `_execute_download`.
   Its body has not read them since Phase 2. The signature becomes
   `_execute_download(self, video_url: str, title: str | None) -> int`.
   Remove their two `Args:` lines, then update every caller to the
   two-argument form:
   - `_process_queue`: pass `download_request["video_url"]` and
     `download_request["title"]`. The request dict keeps `enqueue` and `user`,
     because `download_queued` carries them.
   - `scripts/add_songs.py`: `dm._execute_download(watch_url, None)`.
   - `tests/unit/test_add_songs.py`: the stub
     `def _execute_download(self, video_url, enqueue, user, title)`.
   - `tests/unit/test_download_manager.py`: every direct call. This includes
     `test_execute_download_without_path_emits_download_error`, whose
     `enqueue` parametrization now tests nothing (drop the parametrization and
     the fixture argument), and the `fake_execute(video_url, enqueue, user, title)`
     stub.

   `grep -rn "_execute_download" --include=*.py .` must then show only the
   two-argument form. `queue_download` keeps its `enqueue` and `user`; it is
   the public entry point and puts them on the event.
4. Tests in `tests/unit/test_download_manager.py`:
   - The file-not-found case: a danger toast and no `"Downloaded:"` toast.
     Extend `test_execute_download_without_path_emits_download_error`.
   - The found case: the success toast is still sent.
   - A crash: patch `_execute_download` to raise, `start()` the worker,
     `queue_download(...)`, then `download_queue.join()`. Assert
     `download_error` with the URL and a danger toast.

Commit: `fix(download): a failed download says so and frees its queue slot`.

#### 5.1f: escape titles and names (`base.html`, `queue.html`, `home.html`)

1. `base.html`: in the inline `<script>` beside `isEqual` and `debounce`, add

   ```js
   function escapeHtml(str) {
     return String(str).replace(/[&<>"']/g, function (c) {
       return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
     });
   }
   ```

2. Wrap each of these in `escapeHtml(...)`, and nothing else:
   - `queue.html::generateQueueRow`: `e.user` (the `has-text-success` span)
     and `e.title` (the two title spans).
   - `queue.html`, the now-playing row: `np.now_playing_user` and
     `np.now_playing` twice.
   - `home.html`: in the now-playing template literal, `${np.now_playing}` and
     `${np.now_playing_user}`; in the up-next one, `${np.up_next}` and
     `${np.next_user}`.

   Leave the `data-file`/`data-title` attributes alone, because
   `escape()` (`encodeURIComponent`) already covers them. Leave the
   `Cookies.get("user") === np.now_playing_user` comparison alone too.
3. No new test. The existing render tests must pass.

Commit: `fix(ui): escape song titles and singer names on the queue and home pages`.

#### 5.1g: close out

1. Run pre-commit and the full suite. Fix only what this phase introduced.
2. Self-review the Phase 5.1 diff on the three axes. Check in particular that
   `grep -n "_earliest_held_turn\|is_playable(item)" pikaraoke/karaoke.py pikaraoke/lib/queue_manager.py`
   shows no leftover reader that bypasses `upcoming` or `_take_next`.
3. Results log: one row per code commit with suite counts, plus any
   departures under "Where the build departs". Commit it plan-only:
   `docs(plan): record the queue hold review fixes`.
4. **Stop and report.** Report paths, suite counts and the commit list. 5.1a
   and 5.1b change the core queue's selection and threading, so a
   `/code-review` of Phase 5.1 is pending. Say so and do not run it. This is a
   `/compact` point.

**Known and left (not part of 5.1):**
- **A song held as `"processing"` can still be stranded if** a
  `song_downloaded` handler after QueueHold's raises (LibraryTools already
  catches its lyrics check), **or if** an admin cancels the running job in the
  instant a manual Add lands.
- A held search download keeps the browser-posted title after it lands,
  instead of the filename-derived title other rows show.

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
- [ ] (5.1a) Round-robin off: A's held song is first, B's song second, A's
  library song third. A's library song plays first, the TV and home page name
  it as "up next" beforehand, and A's held song ends up third.
- [ ] (5.1c) Add a song whose processing job is still waiting, then cancel
  that job on the Processing page: the song leaves the queue.
- [ ] (5.1e) Download a video whose download fails: a red toast, and its held
  slot leaves the queue.
- [ ] (5.1f) Set the singer name to `<b>x</b>` and queue a song: the queue and
  home pages show the name as literal text, not bold.
- [ ] (Review of 5.1, fix 7a) The Processing page draws every kind of row
  (queued, running, done, error, waiting for a pick) and its filters as
  before, and a download row queued by `<b>x</b>` reads "by <b>x</b>" as
  literal text.

## Results log

| date | commit | what |
| --- | --- | --- |
| 2026-10-27 | (Phase 0) | `dev` carries the four caption-check commits (`640a661`, `dadecd0`, `7b07fc8`, `f4aa97b`); rebased onto `c48a3ea`; baseline 2298 passed, 0 failed |
| 2026-10-27 | `8e72f27` | Phase 1: `waiting` key, `is_playable`, the swap in `pop_next`, the two up-next readers; 2316 passed (+18) |
| 2026-10-27 | `12d539c` | Phase 2: hold at the click, `QueueHold`, `download_cancelled`, `DownloadManager` off the queue; 2345 passed (+29) |
| 2026-10-27 | `a94441d` | Phase 3: manual Add holds a song still processing or waiting for a pick; 2354 passed (+9) |
| 2026-10-27 | `17a5844` | Phase 4: held-row tag and dimming, "Add to queue" label; 2354 passed (templates only, no test change) |
| 2026-10-27 | `2538e62` | 5.1a: a held song's turn goes to its singer's later ready song; `upcoming` feeds both "up next" readers; 2359 passed (+5) |
| 2026-10-27 | `71e9f7f` | 5.1b: one `RLock` for the queue and `QueueHold`; `queue_clear` locks only its assignment and emits outside it; the lock-order check passed (all five items); 2362 passed (+3) |
| 2026-10-27 | `8660828` | 5.1c: the tracker emits `processing_cancelled` for a cancelled waiting job; 2364 passed (+2) |
| 2026-10-27 | `8dda735` | 5.1d: `QueueHold.settle`, called by `_do_enqueue` after a hold; 2370 passed (+6) |
| 2026-10-27 | `a295e92` | 5.1e: a crashed download emits `download_error` and a danger toast; a missing file sends the red toast, not the green one; `_execute_download(video_url, title)`; 2370 passed (+1 crash test, -1 dropped parametrization) |
| 2026-10-27 | `e083e90` | 5.1f: `escapeHtml` in `base.html`, used on the queue and home pages; 2370 passed (templates only, no test change) |
| 2026-10-27 | `0cf6c6f` | 5.1 review fix 1 + 4: `settle` drops a held song with no state row (deleted), and on `pending` re-reads `waiting_for` and relabels; 2373 passed (+3) |
| 2026-10-27 | `9aa92f0` | 5.1 review fix 3 + 7b: `_report_download_failure` sends the toast and `download_error` for all three failure paths; the catch-all logs the traceback and names an exception with no message by its type; 2374 passed (+1) |
| 2026-10-27 | `e76d2ee` | 5.1 review fix 7a: the Processing page uses the shared `escapeHtml`, which now renders a missing value as empty text; 2374 passed (one page-test string updated) |

Final: full suite 2354 passed, 0 failed. `pre-commit --all-files` clean on this branch's files.

Final after Phase 5.1: full suite 2370 passed, 0 failed. `pre-commit --all-files` clean on this phase's files (the same two unrelated files as before were rewritten and reverted; see below).

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

Phase 5.1:

- **5.1b**: `queue_hold.py` had no "No lock (see the invariant)" wording to
  delete; its module docstring is unchanged.
- **5.1d**: in `test_queue_routes.py`, the held-song test's `enqueue` mock now
  returns `[True, "Song added"]`, as the real method does, instead of `True`,
  and its `success` assertion follows. The route reads `rc[0]` now, and a bare
  `True` cannot be indexed. The race test calls `Babel(app)` because a real
  `QueueManager` translates its messages inside a request.
- **5.1e**: `from flask_babel import _` sits at the top of `_process_queue`,
  not inside the `except` branch.

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

### Left for the review of Phase 5.1

- `upcoming` takes the queue lock on every mpv tick (`on_tick`, then
  `tick_overlays`, then `_get_queue_preview`), and `QueueHold`'s handlers emit
  Socket.IO events while holding it. Neither takes another lock (the 5.1b
  step 3 check), so they can only delay each other.
- `pre-commit --all-files` also re-spaced the lists in this plan (`mdformat`;
  CLAUDE.md excludes `plans/` from pre-commit). Reverted, with `args.py` and
  `open-issues.md`.

### Review of Phase 5.1

`/code-review` of `d3198cd..HEAD` (plans excluded), run 2026-10-27 by Claude
Opus 5.5 with three finder angles (Correctness, Simplicity, Robustness). Findings
after verification, in the numbering Ken ruled on:

| # | file | finding | ruling |
| --- | --- | --- | --- |
| 1 | `queue_hold.py` `settle` | a song deleted between the Add's check and its hold has no state row; `settle` released it and the run loop tried to play a missing file | fixed, `0cf6c6f` |
| 2 | `download_manager.py` `_process_queue` | a `song_downloaded` handler that raises after a good download reaches the new catch-all: green "Downloaded" toast, then red "Error downloading song"; tracker row unchanged (already complete), `_drop(url)` a no-op (item already holds the path) | left |
| 3 | `download_manager.py` `_process_queue` | the catch-all logged `str(e)` only (no traceback); an exception with no message gave a blank error | fixed, `9aa92f0` |
| 4 | `queue_hold.py` `settle` | a song moved to a lyrics pick between the Add's check and its hold stayed labelled "processing" until processing completed | fixed, `0cf6c6f` |
| 5 | `pipeline_tracker.py` `cancel` | the new `processing_cancelled` emit lets the tracker's own handler remove another row for the same song that is mid-cancel (and delete a download's file); no path found that creates two rows for one song | left |
| 6 | `queue_hold.py` `_drop` | a cancel drops the singer's held song with no toast (as an active cancel already did) | left (product call, not a defect) |
| 7a | `base.html`, `processing.html` | two copies of the escape helper; `escapeHtml(null)` gave "null" | fixed, `e76d2ee` |
| 7b | `download_manager.py` | the failure toast and `download_error` written out three times; the crash path reused a translator comment for a different case | fixed, `9aa92f0` |

Overruled at verification: emit-after-unlock in every locked method (no handler
under the queue lock takes another lock; traced); the fork-maintenance size of
the `queue_manager.py` change (re-argues the settled 5.1 design); an active
cancel during an Add strands the slot (already left by Ken's ruling).

Both "Left for the review of Phase 5.1" flags were confirmed as delay only, with
no lock cycle: under the queue lock the handlers send Socket.IO messages, read
preferences (no lock), read plain fields on the playback controller and mpv, and
re-enter `upcoming(1)`.

Fix notes:

- **`settle` on `pending`** reads `waiting_for` outside the queue lock (the lock
  stays a leaf: `LibraryTools` has its own lock). An empty answer leaves the hold
  as it is: between a pick and its job's enqueue nothing claims the song.
- **5.1e departure superseded**: `_process_queue` no longer imports `_`; the
  helper does, as `_execute_download` does.

Final after the 5.1 review fixes: full suite 2374 passed, 0 failed.
`pre-commit` clean on the changed files. The new `settle` and crash tests were
each checked to fail without their fix.
