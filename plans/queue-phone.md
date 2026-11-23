# Queue page for phones

Model: Claude Opus 5.5 (decisions and spec). Executor: Claude Sonnet 5.5, Phases 1-3; Opus judges
review findings.

Branch `queue_phone` off `dev` at `764df44`, worktree `.claude/worktrees/queue_phone`. Sibling of
`browse_phone` (`plans/browse-phone.md` there); the Processing page will get its own branch later.

Mockup (private to Ken): https://claude.ai/artifact/8nSQUuVfMQ3cKNnRY31C9p, row "Queue v2 (draft)"
(six screens). Today's Queue page is the "Queue today" row on the same canvas. Where this file and
the mockup differ, this file wins.

## Decided (Ken, 2026-11-17)

1. Own branch, not `browse_phone`: Queue is nearly all `templates/queue.html` and can land before
   Browse's name-source test. Queue lands first and creates the shared row style (two-line rows,
   coloured status slot, 40 px square buttons) in one stylesheet; Browse and Processing reuse it.
2. Rows: singer's name on top, 17 px bold; "song · artist" 13 px grey under it.
3. Left slot: place in line, 60 px (S1, below; was 52). Two looks only: solid grey for ready, dashed grey outline for
   not playable. Not playable covers paused and every held kind (downloading, processing, waiting
   for lyrics), since `queue_hold` never plays a held song. The slot keeps a word saying which
   ("paused" / "processing"), but the colour is the same so the page shows one signal, not three.
   Not-playable rows fade to 40%; the delete button on them stays full strength.
4. Now playing is its own card at the top (bars, singer, song · artist; admins get a gear). The
   bars and the NOW label are neutral grey; the singer's name stays green like every row.
5. Guests: a large "Pause my songs (BRB)" button pinned to the bottom of the screen (stays visible
   while the list scrolls under it), only when they have songs queued. Teal (the site's link
   colour; grey off and blue on since L9, below): outlined while active, filled when it flips to
   "I'm back: unpause my songs". Their own
   rows get a red delete button instead of the gear; other rows get nothing.
6. Delete asks to confirm (dialog: Keep it / Remove).
7. Admins: drag handle, gear on every row and on Now playing, same menus as today. No pause button.
   Footer: Add random songs (how many beside it), Clear the whole queue.
8. Your own songs are marked by tinted rows (option A; B "YOU" label and C green outlined name
   were not picked). Admins see their own rows tinted too.

## Phone pages: one look (Ken, 2026-11-18)

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Queue: admin",
"Queue: guest, with a failed row", "Queue: guest after BRB", "Queue: guest, delete confirm" and
"Reference palette". For colours and buttons it wins over this branch's mockup; this file wins
over both.

- **L9. BRB is a grey button while off and blue `#375a7f` while on** (was teal). Changes
  decision 5's colours: teal is for links and the current nav icon only (L3). The canvas draws
  it off as `#434d4e` with a `#5e6d6f` border (L15) and on as `#375a7f`, white text both ways.
- **L14. Processing is the admin's only.** This branch owns both halves, in this order (Ken
  placed the nav half here on 2026-11-18, so the order stays inside one branch):
  1. **The failed row first.** A guest's own song that fails processing stays on Queue as a red
     "failed" row with a short reason and Dismiss, until dismissed. Today queue hold takes it
     off with a passing notice (`_on_processing_error`, `queue_hold.py:157`). No step detail on
     Queue rows: Ken, guests prefer less information.
  2. **Then the nav icon.** The Processing nav icon (`#processing`, `base.html`) is hidden from
     guests. The page still opens by its address, as Now Playing's hidden controls do. That
     frees an icon's width for the name pill (`singer_defaults`, L6). Check that nothing a guest
     sees links to Processing.
- The shared stylesheet (decision 1) uses L1 (one green, one amber), L15 (grey fill `#434d4e`)
  and L16 (disabled: no fill, a faded border, a `#8c9b9d` label, no opacity fade) from
  `bulma-dark.css`. They land on `singer_defaults`, its Phase 5; take them from `dev` once that
  lands rather than restating the values here.
- The review's "small gaps" for the shared stylesheet are ruled: S1-S4, below.
- The Search page's restyle (L12) waits for this branch to land with its shared stylesheet.

## Rulings (Ken, 2026-11-18): the shared style and the failed row

Proposed by Opus, accepted by Ken ("agreed", 2026-11-18).

- **S1. The state slot is 60 px on every page** (was 52 here, 60 on Browse and Processing).
  Their slots carry words ("processing", "cancelling") that are tight at 52.
- **S2. Solid means a tap, dashed means a state, on every page.** A processing song stays a
  green Queue button on Browse (it can be queued, L8) and a dashed slot on Queue and Processing
  (nothing to tap). One rule, not a gap: it goes in the shared stylesheet's header comment.
- **S3. A gear opens a menu, a chevron expands the row.** Queue's gear stays. Browse's admin
  button becomes a gear, since its menu is the same kind as Queue's (recorded in
  `plans/browse-phone.md`, decision 6). Processing keeps its chevron.
- **S4. The sub-line grey `#b5bfc0` becomes a `bulma-dark.css` token** on this branch, as the
  canvas palette says.
- **F1. A failed row keeps its place.** It never plays, so it holds nobody up. It takes no
  place number and isn't counted in "Up next" (canvas board "Queue: guest, with a failed row"). It has no turn, as a paused song has none: the next
  song in line plays and the failed row stays where it is. *(Amended by Ken 2026-11-21 from
  the review of `08556079^..de80acd9`, finding 2, option a. It said the turn passed to the
  same singer's next ready song, as a held song's does; that made the numbers disagree with
  the play order and slid the failed row back a place at each such turn.)*
- **F2. A retry from Processing that works brings the row back** in its place: the retry runs
  the held-song path (queued for processing, then ready). No new code for this; Phase 1 tests
  it.
- **F3. Its owner and admins see the red row**, with the reason and Dismiss. Other guests see
  it as a faded row with a dashed "failed" slot, no reason and no button.
- **F4. The reason is one fixed sentence**, not the error: "Couldn't be prepared. The host can
  retry it." (Ken may reword.) The error itself is technical; admins read it on Processing.
- **F5. Processing failures only.** A failed or cancelled download still frees its slot as
  today (`_on_download_failed`, `queue_hold.py`); the download dialog reports it. The canvas's
  sample reason, "Couldn't download the video", is a download failure; this file wins.
- **Pause route:** `/queue/user/pause` drops its unused `song` field rather than the page
  sending a placeholder.
- A restart empties the queue (it lives in memory only), failed rows with it; nothing to
  persist.

Assumptions in this spec, not asked (Ken may overrule):

- **Dismiss doesn't confirm** (the song can't play anyway). Every Remove does (decision 6): a
  guest's red button and the admin menu's "Remove from Queue" alike.
- **The failure notice stays, reworded** to "%s couldn't be processed", since a guest on
  another page would not see the row. Today's text says the song was taken off the queue.
- **Pausing your songs (BRB) leaves failed rows out** of the all-paused check, on the server
  and in the button's label alike, so the label never disagrees with what a tap does. The
  tap still flips them with the rest, so a retry that works while the singer is away comes
  back paused. *(Flip amended by Ken 2026-11-21, review finding 1.)*
- **Names, until GATE N rules** (below): the file-name split, Browse's source (a).

## Names on the rows

Decision 2's "song · artist" needs the split that Browse's GATE N is testing
(`plans/browse-phone.md` on `browse_phone`, "Where the names come from"). Queue lands first,
so it creates the one function that turns a title into artist and song, and Browse reuses it.

- Until GATE N rules: Browse's source (a), split at the first " - " into artist (left) and
  song (right), each trimmed. Ken called (a) the acceptable fallback. A title with no " - ", or
  an empty side, gives no split, and the sub-line shows the whole title.
- If GATE N has ruled when Phase 1 runs and picked (a) or (b), use that. If it picked (c),
  ship (a) here; Browse's Phase 2 changes the function.
- The split runs on the server only. The page never splits a title.

## What the code does today (read 2026-11-18 at `dev` `017b6fb`)

- `templates/queue.html` (577 lines): a striped Bulma table, rebuilt from `/get_queue` and
  `/now_playing` on every `queue_update` and `now_playing` socket event (`queuePage_getQueue`).
  Now playing is the table's first row (`disabled-sort`), so Sortable's indices carry an offset
  of one. Rows: number, drag handle (admins), singer and title, "paused" or waiting tags
  (`WAITING_LABELS`), and a gear. The admin's gear opens `#song-options-modal` (Play Next, Move
  Up, Move Down, Move to Bottom, Pause, Remove from Queue); a guest's gear on their own rows
  opens `#user-song-options-modal` (the BRB toggle, Remove). Admin footer: Add N random songs
  (`/queue/addrandom/<n>`, `#randomNumberInput`), Clear all (`.confirm-clear`, which
  `spa-navigation.js` confirms). An inline `<style>` fades not-playable rows to 0.5.
- `/get_queue` (`routes/queue.py`) dumps `queue_manager.queue` as is; only `queue.html` calls
  it. An item holds `user`, `file`, `title`, `semitones` (removed on `singer_defaults`),
  `paused` and `waiting` (`"download"`, `"processing"`, `"pick"` or None). `title` is the
  tidied file name, or the YouTube title for a held download.
- `QueueHold._on_processing_error` (`queue_hold.py`) removes the held item and broadcasts
  "%s couldn't be processed and was taken off the queue". `settle()` calls it when a manual
  Add races a failure. `_held()` finds any item whose `waiting` is set, which is what the
  retry path in F2 rides on: `_on_processing_queued`, `_on_needs_pick`, `_release` and `_drop`
  (song deleted, processing cancelled) all reach a failed item too.
- `QueueManager` (`queue_manager.py`): `is_playable` is false for any `waiting`; `_take_next`
  passes an unpaused held song's turn to its singer's first later ready song;
  `toggle_pause_user` pauses all of a user's items if any is unpaused, else unpauses all;
  `is_user_limited` counts every item.
- `/queue/user/pause` uses `UserQueueActionForm` (`song` and `user`, both required); the
  handler reads `user` only.
- `karaoke.py` `get_now_playing()` merges `playback_controller.get_now_playing()` (whose
  `now_playing` is the title) with up-next fields; it is also the `now_playing` socket payload.
- `base.html` has no admin flag (no context processor; each route passes `admin` to its own
  template). `#processing` sits in `.navbar-brand`; `spa-navigation.js` marks it active.
  The other links to Processing (song info, edit words, library run, playlist, pick pass) are
  all on admin-only routes.
- `bulma-dark.css` tokens: `--dark-bg-primary/-secondary/-tertiary` (`#1f2424`, `#282f2f`,
  `#343c3d`), `--dark-text-muted` `#8c9b9d`, `--dark-text-light` `#dbdee0`, `--dark-border`
  `#5e6d6f`, and the colours. `#b5bfc0` and the red text `#f17a6b` are not tokens.
- ui-check's fake job (`.claude/skills/ui-check/run_app.py`, local, untracked) always
  completes; nothing in it can fail a song.

## Design

### Server (Phase 1)

- **Failed:** `_on_processing_error` sets the held item's `waiting` to `"failed"` instead of
  removing it, and emits the reworded notice (danger). The module docstring and `enqueue`'s
  list "failed" among the waiting values. Nothing else changes for it to stay unplayable and
  pass its turn on.
- **BRB:** `toggle_pause_user` leaves items waiting as `"failed"` out of its check and flips
  them with the rest (amended 2026-11-21, review finding 1).
- **Pause route:** a schema with `user` only.
- **Names:** one function, title in, artist and song out or nothing (name and home are spec
  choices; somewhere Browse can import without Flask, such as beside `filename_from_path` in
  `song_manager.py`). `/get_queue` returns each item with `song` and `artist` added (artist
  empty when there is no split), built on copies, never written into the live queue. The Now
  card needs the same two for the playing song: add them to `get_now_playing()`, or have
  `/get_queue` return them (spec choice; pick the one that touches fewer readers).

### The shared stylesheet (Phase 2)

A new stylesheet in `static/` (name a spec choice, e.g. `phone-rows.css`), linked from
`queue.html` the way `processing.html` links `library-pages.css`. Its header comment states
S2. Values from the canvas's Queue boards:

- **Row:** min-height 60 px; top line 17 px bold, sub-line 13 px in the S4 token; every other
  row shaded `rgb(50, 55, 55)`; your own rows tinted green `#2ecc71` at 14%; a failed row
  tinted red `#e74c3c` at 12%.
- **State slot:** 60 x 44 px, 6 px corners. Ready: `--dark-bg-secondary` fill, white 17 px
  bold number. Not playable: 1 px dashed `#8c9b9d`, no fill, the number over a 10 px word.
  Failed: 1 px solid `#e74c3c`, `#f17a6b` text, a "!" over "failed", no number.
- **Square button:** 40 x 40 px, 6 px corners, L15's grey (the gear). Red variant for delete:
  `#e74c3c` border, `#f17a6b` icon, same grey fill.
- **Fading:** a not-playable row fades its text to 40%; the slot and the button stay at full
  strength (decision 3). A failed row doesn't fade for its owner and admins.
- **Tokens:** the S4 grey and the red text go in `bulma-dark.css` (names spec choices). L1,
  L15 and L16 come from `dev` (`singer_defaults` Phase 5): use its tokens, never restate them.

### The page (Phase 2)

Rebuilt per decisions 2-8, L9, L14, S1-S3 and F1-F5, drawn on the canvas boards "Queue:
admin", "Queue: guest, with a failed row", "Queue: guest after BRB" and "Queue: guest, delete
confirm". Keeps the data flow (socket event, then `/get_queue` and `/now_playing`, then a
rebuild), the `.queue` click namespace for SPA re-runs, and Sortable on the drag handle for
admins.

- **Now card** above the list, outside Sortable (the index offset goes): static grey bars and
  "NOW", the singer in green, "song · artist". Admins get a gear that opens today's
  now-playing menu (Restart, Pause, Skip).
- **"Up next · N songs"** over the list, N counting rows that aren't failed.
- **Rows:** drag handle (admins), state slot, singer over "song · artist" (or the whole
  title), then the button: the admin's gear with today's menu; a guest's red delete on their
  own rows; a 40 px blank on everyone else's. Numbers skip failed rows, and so does the
  instant renumber after a drag.
- **Failed row:** for its owner and admins, the red row, a third line with F4's sentence in
  `#f17a6b`, and a grey outline Dismiss (the palette's outline look) in place of the button.
  For other guests, F3. The owner's Dismiss posts `/queue/user/delete`; the admin's calls
  `/queue/edit?action=delete`. No confirm.
- **Remove asks first:** "Remove this song?", "<song · artist> will come out of the queue.",
  Keep it (grey) and Remove (red). Both a guest's red button and the admin menu's Remove from
  Queue open it.
- **BRB (guests):** a bar fixed to the bottom of the screen, shown when the guest has at least
  one row that isn't failed; the list gets room below so its last row clears the bar. Off: L15
  grey, a pause icon, "Pause my songs (BRB)". On, when every one of those rows is paused: blue
  `#375a7f`, a play icon, "I'm back: unpause my songs". It posts `/queue/user/pause` with
  `user` only. The guest options modal goes. Admins get no BRB (decision 7).
- **Admin footer:** a green "Add random songs" with "How many" beside it (1-99, today's
  input), and a red outline "Clear the whole queue" (keeps `.confirm-clear`).
- **Empty:** "The queue is empty" only when nothing is playing either, as today.
- The table, the inline `<style>` and `WAITING_LABELS`' tag look go.

### The nav icon (Phase 3)

- A context processor in the app setup makes the admin check available to every template;
  `base.html` renders `#processing` for admins only. `/processing` stays open by its address
  (L14).
- Check that logging in or out as admin reloads the nav (SPA navigation swaps only the page
  body); if it doesn't, those two actions do a full page load.
- Re-grep for links to Processing on pages a guest can open; today there are none besides the
  nav.
- `singer_defaults` L6 rewrites this nav bar first; edit its version.

## Phases

Before Phase 1, rebase `queue_phone` onto `dev`. Phase 1 needs nothing from `singer_defaults`
and may run now. Phases 2 and 3 wait until `singer_defaults` (its Phase 5) is on `dev`; rebase
again first. Each phase stops at its end with its Results row.

### Phase 1: the failed row and the names, server side

Executor: Sonnet. Commits, in this order:

1. `fix(queue): the pause-my-songs route asks only for the singer`. The schema; a route test
   that a post without `song` toggles the user's songs.
2. `feat(queue_hold): a song that fails processing stays on the queue as failed`. QueueHold,
   `toggle_pause_user`, docstrings, and `WAITING_LABELS` gains "failed" so today's page shows
   a tag rather than "undefined" until Phase 2 replaces it. Tests (`test_queue_hold.py`,
   `test_queue_manager.py`, real `EventSystem`):
   - a failure keeps the item, waiting "failed", and emits the new notice;
   - a failed item never plays, and its turn goes to its singer's next ready song;
   - F2: queued for processing then complete brings it back to ready in the same place; a
     skipped job makes it ready too, and a lyrics pick turns it to waiting for lyrics;
   - a deleted song or a cancelled job removes the failed row;
   - `settle()` on a song that failed meanwhile leaves a failed row;
   - `toggle_pause_user` with one failed and one paused song unpauses, and never flips the
     failed one.
3. `feat(queue): queue rows carry the song and the artist`. The split function, `/get_queue`,
   and the Now card's pair. Tests: `Artist - Song`; no " - "; several (split at the first);
   an empty side; spaces trimmed; `/get_queue` adds both keys and leaves the live queue as it
   was.

Self-review per commit. Stop after commit 3 with the Results row.

### Phase 2: the shared stylesheet and the Queue page

Executor: Sonnet, after `singer_defaults` is on `dev`.

4. `feat(ui): Queue page for phones, with the shared row stylesheet`. The stylesheet, the two
   tokens, `queue.html`. Update or replace any test that pins the old markup.

Before the checks, give ui-check's fake job a way to fail (for example `FAKE_FAIL=<part of a
song name>` makes it call `_report_failure` instead of reporting complete). The skill is local
and untracked: a plain edit, no commit.

Then **ui-check** at 390 px and 360 px, as an admin and as two guests (two name cookies), each
outcome and screenshots in the Results log:

- Admin: the Now card and its gear menu; dragging a row moves the right song (no offset); the
  gear menu; Remove asks first; the footer.
- Guest: own rows tinted with a red delete, others blank; the confirm's Keep it and Remove;
  BRB stays pinned while the list scrolls, turns blue on a tap with every own row paused, and
  a second tap unpauses.
- Failed: a held song made to fail shows its owner the red row with the sentence and Dismiss,
  no number, and "Up next" not counting it; the second guest sees the faded "failed" slot
  only; the admin sees the red row with Dismiss; Dismiss removes it. An admin Retry from
  Processing turns it to processing, then ready, in its place.
- Computed: the slot is 60 px wide; the sub-line is the token's colour; nothing scrolls
  sideways at 360 px.

**Checkpoint:** `/code-review` over commits 1-4 (Ken runs it), then fixes.

### Phase 3: the Processing icon for admins only

Executor: Sonnet.

5. `feat(ui): the Processing nav icon is the admin's only`. Tests: a page rendered for a guest
   has no `#processing`, for an admin it has; `/processing` still opens for a guest.

ui-check at 360 px: a guest's nav has no Processing icon and the name pill takes the room; an
admin's has it; logging in and out updates it. The self-review covers this commit (one
template and a context processor).

### Phase 4: Ken's checks

On his phones, at a party or a rehearsal: the guest and admin views, BRB, a delete, and a
song that fails (or the Results log's screenshots where none fails).

## Accepted edges

- A failed row counts toward the per-guest song limit until it is dismissed.
- With no admin password everyone is an admin, so nobody sees BRB; the same as today.
- Other guests learn that a song failed (the slot says so), not why.
- The new strings show in English until Ken's next catalog regen.

## Pending

- `singer_defaults` changes three lines of `queue.html` (modal background scope); the rebuild
  supersedes them.
- `singer_defaults` L6 rewrites the nav bar in `base.html`; Phase 3 runs after it lands.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
| 2026-11-18 | 1 | `4451eaf8` | Rebased onto `dev` `17ac3fc2` first (the four plan commits are now `70c00eae`..`04390388`). Pause route: new one-field `UserForm` (`user`); `UserQueueActionForm` now extends it and adds `song` for `/queue/user/delete`. The three pause route tests post `user` only (422 before the change). Also edited `queue.html`'s `executeUserAction` to send `song` for delete only: a form with an unknown field is rejected with 422 (probed with a throwaway schema), so today's BRB tap would have broken until Phase 2. `tests/unit/test_queue_routes.py`: 23 passed. |
| 2026-11-18 | 1 | `0f0ca990` | `_on_processing_error` sets `waiting` "failed", emits `_changed()` and the notice "%s couldn't be processed" (danger). Added, not in the spec: it ignores a row already "failed", because `settle()` can run after the real event and would otherwise notify twice (mutation check: without the guard `test_a_second_error_event_changes_nothing` and `test_a_failure_the_event_already_reported_is_not_reported_twice` fail). `toggle_pause_user` leaves "failed" out of both check and flip (`item.get("waiting")`); a user with only failed songs gets False. `WAITING_LABELS` gains `failed`. Docstrings: module, `enqueue`, `is_playable`, `toggle_pause_user`. Tests (real `EventSystem`): failure keeps the item and emits the new notice; a failed item never plays and its turn goes to its singer's next ready song; F2 (queued then complete = ready in the same slot of three; skipped = ready; pick = waiting for lyrics; a second failure after a retry notifies again); cancel and delete remove a failed row quietly; `settle()` leaves a failed row; `toggle_pause_user` failed+paused unpauses and never flips the failed one. Two superseded tests replaced. Suite after this commit: 4099 passed. |
| 2026-11-18 | 1 | `b80647d4` | `split_title(title) -> (artist, song)` in `song_manager.py`, module level beside `filename_from_path`: first " - ", each side trimmed. Differs from the spec's "or nothing": no usable split (no " - ", or an empty side) returns `("", title)`, so both callers show the title as the song with no fallback of their own; GATE N had not ruled (Browse's results log is empty), so source (a). `/get_queue` returns each item with `artist` and `song` on copies; live queue untouched (test). The Now card's pair is on `get_now_playing()` as `now_playing_artist` and `now_playing_song` (None when idle), not on `/get_queue`: `/get_queue` is a bare list read by `queue.html` only, and `get_now_playing()` gets two additive keys from one writer. Tests: `Artist - Song`, no " - ", `Jay-Z`, several (first wins), four empty-side titles, trimming; `/get_queue` keys and the live queue; `get_now_playing` split, no split, idle. Suite: 4113 passed. |
| 2026-11-18 | 1 | (stop) | Phase 1 stops here. Self-review: commits 1 and 3 are covered by the three-axis read-through; commit 2 touches the queue-hold failure path and its lock, so it rides to the checkpoint `/code-review` already due after Phase 2 (commits 1-4). Phases 2-3 wait for `singer_defaults` on `dev`. |
| 2026-11-21 | 2 | (rebase) | Rebased onto `dev` `e1ac8adf` (singer_defaults landed). One conflict, in `karaoke.py`'s imports: kept dev's `SingerRegistry` and this branch's `split_title`. `queue.html` had no conflict: dev changed 5 lines of it, and the rebuild replaces them. Phase 1's commits are renumbered: `4451eaf8` is now `08556079`, `0f0ca990` is `4fed9078`, `b80647d4` is `3afe2808`, and the Phase 1 results commit `51e4a2f0` is `ec26d676`; the Phase 1 rows above keep the old hashes. `origin/queue_phone` still holds the old ones, so the next push needs `--force-with-lease`; not pushed. The 286 Phase 1 tests passed again after the rebase. |
| 2026-11-21 | 2 | `4bdee8f7` | `phone-rows.css` (row, 60 x 44 slot, 40 x 40 square button, tints, the 40% fade; header states S2), `--dark-text-sub` `#b5bfc0` and `--dark-danger-text` `#f17a6b` in `bulma-dark.css` (S4), `queue.html` rebuilt with no table, no inline fade styles, no guest options modal. Green and red tints are built from the colour parts (`--bulma-success-h/s/l`, `--bulma-danger-h/s/l`) at 14% and 12%; nothing restates L1, L15 or L16. No existing test pinned the old markup (grepped `tests/`): nothing replaced. New `tests/unit/test_queue_page.py` (4 tests): an admin gets the song menus, Now menu, footer and no BRB bar; a guest gets the BRB bar and none of the admin controls; both get the remove dialog and the stylesheet; with no admin password everyone is an admin. Suite after this commit: 4291 passed. Pre-commit on the four files: clean. Not in the spec, chosen while building (the canvas boards are private to Ken and I could not open them, so values the spec text does not give are mine): the slot word for a song waiting on a lyrics pick is "lyrics" ("waiting for lyrics" does not fit 60 px at 10 px); a row that is both paused and waiting shows the waiting word; the Now card is `--dark-bg-secondary` with its slot a step lighter (`--dark-bg-tertiary`) and three static grey bars; "Up next" is sentence case with "1 song" singular; the admin's failed row keeps its drag handle; BRB ignores a second tap while the first request is out; the remove dialog is a title, the sentence and two equal 48 px buttons. New strings (NOW, lyrics, the BRB labels, the dialog, Dismiss, the reason, "Up next", "Add random songs", "How many", "Clear the whole queue") show in English until the catalog regen. Self-review: three axes read over the diff; found and removed a no-op `.sr-list` rule and a duplicated row-index lookup. |
| 2026-11-21 | 2 | (ui-check) | **The ui-check skill is not on this machine.** There is no `.claude/skills/` in the main checkout or any worktree, nothing under `~/.claude`, and the skill list has no `ui-check`; so there was no fake job to add `FAKE_FAIL` to. Replaced with a throwaway harness (not committed): `check_app.py` runs the app's real routes, templates, `QueueManager`, `QueueHold`, `SingerRegistry` and `EventSystem` around a fake karaoke; a "job" is a thread that reports `download_queued`, `song_downloaded`, `processing_queued` and then `processing_complete`, or `processing_error` when the title contains `FAKE_FAIL` (run with `FAKE_FAIL="Bad Song"`). `run_checks.py` drives it with Playwright 1.61, Chromium, touch emulation, DPR 2, at 390 and 360 px wide: Host (admin cookie) and two guests, Alice and Bella (two `user` cookies and two singer tokens, each in its own browser context). Scripts and 32 screenshots: `.claude/ui-check/queue_phone/` in this worktree (untracked, goes with the worktree); `results.json` has every check's outcome. **112 checks, 56 per width, all pass.** Admin: Now card ("Cara", "Bohemian Rhapsody · Queen", bars and NOW `#8c9b9d`, name `#2ecc71`) and its gear menu (Restart / Pause / Skip); a handle on every row, a gear on every row but the failed one, Dismiss on the failed one; numbers 1..N skip it; "Up next · N songs" does not count it; a touch drag of the last row to the top (CDP touch events, 300 ms hold) leaves the queue as [that song] + the rest in order, so no index offset, and the numbers read 1..N straight after; the gear menu on the first row hides Play Next and Move Up; Remove asks ("Remove this song?", "<song · artist> will come out of the queue."), Keep it keeps the song, Remove removes that song; Dismiss removes the failed row with no dialog; the admin's own row is tinted and keeps its gear; no BRB bar; footer: green Add random songs (adds 3), How many = 3, red outline Clear the whole queue. Guest (Alice): her 3 rows tinted `rgba(46,204,113,0.14)` with a red delete (`#e74c3c` border, `#f17a6b` icon, grey fill), the other 5 rows a blank, no gear, no handle, no footer; a paused row has a dashed slot, "paused", text at opacity 0.4; a processing row says "processing" and shows the whole title when it has no " - "; the rows themselves are not faded; delete opens the dialog, Keep it keeps, Remove removes only her song; BRB bottom edge is the viewport's bottom at scrollY 0 and at 400, its top stays at y 750 of 844, and at the end of the page the last row ends above it; one tap pauses all her songs (server state) and the button reads "I'm back: unpause my songs" with a play icon and `rgb(55, 90, 127)` once the tap's hover is cleared; a second tap unpauses and it is grey again (`rgb(67, 77, 78)`). Failed: Bella's own failed song (made to fail by the job) is the red row (`rgba(231,76,60,0.12)`) with "Couldn't be prepared. The host can retry it.", Dismiss, "!" over "failed", no number; Alice sees it faded with a dashed "failed" slot, no reason, no button, no number; Bella's BRB pauses her ready song, leaves the failed row alone and reads "I'm back"; Bella's Dismiss removes the row with no dialog and Alice's page drops it too; empty queue with nothing playing shows "The queue is empty", no BRB and no "Up next". Retry: the harness emits what a retry that works emits (`processing_queued`, then `processing_complete`), not a tap on Processing's Retry button, because the harness has no `ProcessingManager`: failed, then a dashed numbered "processing" slot, then ready, at row index 1 each time. Computed: the slot is 60 px wide; the sub-line is `rgb(181, 191, 192)`; the gear is 40 x 40; `scrollWidth` equals `innerWidth` at both widths for all three people; no page errors. Two things seen: right after a tap the BRB button wears Bulma's hover shade (`rgb(63, 103, 145)`) because a touch leaves `:hover` on it, as it does on every `.button`; and the dialog screenshots taken straight after a tap show Chromium's tap highlight (`-webkit-tap-highlight-color` `rgba(51,181,229,0.4)`) over the tapped button, a square that is gone after 1.5 s, so those shots wait 1.2 s. |
| 2026-11-21 | 2 | `de80acd9` | Ken shared the canvas (https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL) after the rows above were written, so I read its four Queue boards (`QueueV2Admin`, `QueueV2Guest`, `QueueV2GuestPaused`, `QueueV2GuestConfirm`) and compared. The rows above say the canvas could not be opened and some values were mine; `4bdee8f7` is as that note describes, and this commit replaces those guesses. Fixed to the canvas: rows bleed 8 px into the card (`margin: 0 -8px`, padding 6 x 8, gap 10) with square corners and no gap between name and song line; a long title wraps (`overflow-wrap: anywhere`) instead of an ellipsis; a dashed slot's number and word are both `--dark-text-sub` (were white and `#8c9b9d`); the failed slot's "!" is drawn (SVG, 14 px, 2.2 stroke) not typed; the Now card has a 1 px `--dark-primary` border, padding 12, gap 12, five bars and an uppercase "Now" label in `--dark-text-sub` and no slot fill (the label reuses Processing's existing "Now" string, so "NOW" is no longer a new string); "Up next" is regular weight in `--dark-text-sub` with 8 px under it, none above; the drag handle column is 20 px; Dismiss is 15 px regular weight in `--dark-text-light` (Bulma's buttons are weight 500, which the canvas does not draw: Dismiss, Clear and Keep it set 400); the BRB bar is solid `--dark-bg-primary` with a 1 px `--dark-bg-tertiary` top line, `0 -8px 16px rgba(0,0,0,.45)` shadow and 12 / 20 / 20 padding (89 px tall with the line), the list's bottom room is 108 px; the admin footer is 44 px buttons without icons, "How many" on the same line left of a dark 48 x 44 input, Clear a regular-weight red outline in `--dark-danger-text`, 24 px above and 10 px between; the remove dialog is a 330 px card (328 at 360 px) with a `--dark-border` outline, 10 px corners, a 15 px `--dark-text-light` line and two 48 px buttons, Keep it regular and Remove bold. Differences left on purpose: the slot is 60 px, the canvas draws 52 (ruling S1); the sample reason on the failed board is the download sentence, the plan's fixed sentence wins (F4, F5); the green "Add random songs" label is the theme's `rgb(8, 33, 18)`, the canvas's `#1f2424` (the theme defines that button, and the two are within a shade of each other); the gear, trash, play and pause icons are the app's fontello glyphs, the canvas draws SVGs of the same shapes. Not on the canvas, so unchanged from `4bdee8f7`: the gear menu and Now menu, which are today's modals. The harness now pins the canvas values (14 more checks): **132 checks, 66 per width, all pass**; the 32 screenshots in `.claude/ui-check/queue_phone/` are from this run, so the earlier set is gone. Suite: 4291 passed. Pre-commit clean. |
| 2026-11-21 | 2 | (stop) | Phase 2 stops here. Commit 4 is a multi-file rewrite of the page (about 860 lines of `queue.html`), so its self-review does not stand alone: it rides to the checkpoint `/code-review` over commits 1-4 (Ken runs it), as commit 2 already does. Phase 3 not started. |
| 2026-11-21 | 2 | `c00a2821` | Review fixes after `/code-review high 08556079^..de80acd9` (10 findings; Ken took the triage with option a for finding 2). **1:** `toggle_pause_user` flips failed items with the rest, still leaves them out of the all-paused check; test `..._never_pauses_a_failed_song` replaced by `..._pauses_a_failed_song_with_the_rest` (ends with the retry clearing `waiting` and `pop_next()` returning None). **2 (a):** `_take_next` gives a failed item no turn (`waiting != "failed"` beside the paused test); `test_a_failed_item_never_plays_and_its_turn_goes_to_its_singers_next_ready_song` replaced by `test_a_failed_item_never_plays_has_no_turn_and_keeps_its_place`. F1 and the BRB ruling amended above. **4:** `/get_queue` copies under `queue_manager.lock`. **6:** `/queue/edit` drops `unquote` (Flask already decodes); new route test with `100%25 Hits`. **3:** `queuePage_getQueue` numbers each fetch and only the latest draws; an older one's promise waits on the latest; it returns that promise; `toggleBrb` clears `brbBusy` only when a fetch sent after the POST answered has settled. Socket listeners wrap the call so their argument is not taken for `force`. **8:** `previousQueue`/`previousNowPlaying` gone; comparison is against `queue`/`nowPlaying`; a `forceDraw` flag set by `force` holds until a draw, so a newer fetch that overtakes a forced one still draws (the first load and the drag pass `true`). Net state: two fields out, three in (`fetchSeq`, `latestFetch`, `forceDraw`). **9:** `isFailed(e)` used by the row, the place counter and BRB. **5:** the dialog's replace takes a function. **10:** "Up next" hides when no row is numbered; the plural rule went to `plans/open-issues.md`. **7:** dropped (catalogs are ours; every waiting state has a word). Harness (`.claude/ui-check/queue_phone/harness/`, untracked): Bella's BRB check now expects the failed row paused; a `tap_brb` helper waits for `brbBusy` false before a tap (the page ignores taps until the post-tap fetch draws); `/__check/upcoming` added; new `run_review_fixes` (failed row first, then Alice, then Bella: row 1 is the song `upcoming()` plays first; BRB on, retry, the song comes back paused and BRB still reads "I'm back"; a `Ca$$h $& Co - Money $' Talks` title reads as written in the dialog). First run caught `queuePage_getQueue` not returning its promise (BRB stuck busy); fixed before the commit. **140 checks, 70 per width, all pass.** Suite: 4292 passed. Pre-commit clean. |
| 2026-11-23 | 3 | `006e92ff` | `base.html` wraps `#processing` in `{% if admin %}`. The flag comes from a context processor, `inject_admin` in `routes/admin.py` on `admin_bp` (`@admin_bp.app_context_processor`, the way `singer_bp` hands every page `singer`), not from `app.py` as the plan words it: registering with the blueprint means a test app that registers `admin_bp` runs the production path, and nothing in `app.py` can be left out. `is_admin()` is the one check; a route's own `admin=` still wins with the same value. Left alone on purpose: the five page routes that pass `admin=is_admin()` to their template (home, files, info, queue, processing) now duplicate it; `processing_status`'s `get_status(admin=...)` is not a render and stays. Removing them is not free: the Processing tests patch `routes.processing.is_admin` per route, and the other page tests' apps don't register `admin_bp`. SPA check: logging in is the Info page's plain form POST to `/auth` and logging out is the Log out link, which `spa-navigation.js` excludes (`/logout`, `/auth`); both are full page loads (a `window` marker set before the click is gone after), so the nav is rebuilt and nothing needed changing. Re-grep: Processing is linked from `playlist.html`, `library_run.html`, `pick_pass.html`, `song_info.html`, `song_edit_words.html`; every route that renders them is behind `is_admin()`, so no guest page links to it besides the nav. Tests: `test_queue_page.py` (its app now registers `admin_bp`): a page whose route passes no `admin` (a bare `base.html` render) has `#processing` for the admin cookie and not for a guest; with no admin password everyone gets it; the Queue page's guest has none, its admin has it. `test_processing_page.py`: a guest still gets 200 on `/processing` without the icon, an admin gets it. Mutation checks: without the decorator the first two fail; without the template gate the bare-page, Queue and Processing tests fail. Suite: 4296 passed. Pre-commit clean. |
| 2026-11-23 | 3 | (ui-check) | **The stand-in harness named in the handoff is not on this machine**: no `.claude/ui-check/` in this worktree or the main checkout, and no `run_checks.py` or `check_app.py` anywhere on the VM (the Phase 2 row's harness and 32 screenshots live wherever that run was). Used the VM's `ui-check` skill instead (the real app, `launch.sh` on port 5733 from this worktree, listener's `PYTHONPATH` confirmed, fake jobs, config with `admin_password`) and a new script, `.claude/ui-check/queue_phone/phase3/check_nav.py` (untracked; it and 5 screenshots and `results.json` are in that folder), Playwright 1.64.1 Chromium, 360 x 740, DPR 2, touch, a joined guest per context (`POST /singer`, token cookie). **29 checks, all pass.** Guest: no `#processing` in the DOM on `/queue`, `/`, `/search`, `/browse`, `/info`, nor after SPA taps on queue, search, browse and home; the name pill shows; the nav row sits on one line inside 360 px (home, queue, search, browse at 44 px, pill at x 236..309, 73 px wide); no sideways scroll; `/processing` by address answers 200 and draws its content with no nav icon. Admin, through the real forms: before login none; the Login button is a full load; after it the icon is in the row (five 44 px items, pill 71 px, x 238..309, one line, no sideways scroll); tapping it opens `/processing` with the icon active; it stays through SPA taps on queue and home; the Log out link is a full load and the icon is gone. Pill room: the same long name ("Carolina Mariposa") is 118 px wide for a guest and 74 px for an admin, so the pill takes the room the icon left. Not from this commit: a guest on `/info` gets 403 from `/info/stats` and `/library_stats` (`info.html`'s own admin-only calls, it logs "Failed to fetch system stats"); the script clears those before its page-error checks, and no other page error appeared. |
| 2026-11-23 | 3 | (stop) | Phase 3 stops here. Self-review covers the commit (one template, one three-line processor). Phase 4 is Ken's. Not pushed. |
