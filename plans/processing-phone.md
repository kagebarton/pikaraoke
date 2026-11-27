# Processing page for phones

Model: Claude Sonnet 5.5 (spec by Claude Opus 5.5, 2026-11-27; GATE V judged by Opus).

Branch `processing_phone`, worktree `.claude/worktrees/processing_phone`. Opened off `dev` at
`764df44`, rebased onto `dev` at `cb3ea32a` on 2026-11-27 (plan commits only). Sibling of
`browse_phone` and `queue_phone`, both landed (plans on tags `archive/browse_phone` and
`archive/queue_phone`). Queue created the shared row style, `static/phone-rows.css`, which
Processing reuses (`queue-phone.md`, decision 1).

Mockup (private to Ken): https://claude.ai/artifact/Mn2PoVbRJd5BKmPSXBZx11. Top row "Today" is the
page as built on `dev` (`templates/processing.html`); bottom row "After" is draft 1, each screen
under its Today twin (admin Jobs, admin with a row opened, admin Library tools, guest). Where this
file and the mockup differ, this file wins.

## Goal

The Processing page becomes the admin's phone page in the look the other phone pages share. The
Jobs / Library tools toggle and the filter chips stay pinned at the top. The jobs form one flat
list, each row with a colour strip and three lines. The running job is a Now card with three
steps. Rows open in place. Library tools gets the same look. The guest view, the Add to queue
action and the guest-only server code go, and a finished row says "(edited)" as Song Info does.

## Order

1. **Phase 1** (commits 1-3): server, plus the page edits that the removals force. Can run now.
2. **Phase 2** (commit 4): the Jobs view. **Precondition:** `search_phone` has landed on `dev`,
   because it adds the shared `.pin-top` rule to `phone-rows.css`. Rebase onto `dev` first. If
   `dev`'s `phone-rows.css` has no `.pin-top`, stop after Phase 1 and tell Ken. Do not add
   `.pin-top` on this branch.
3. **Phase 3** (commit 5): Library tools. Then the `ui-check` run for Phases 2-3 and **stop for
   GATE V**: Opus, read-only, compares the screenshots and computed styles with the canvas boards
   and returns a pass or a fix list. Then Ken runs `/code-review` (the checkpoint gives the line).
4. **Phase 4** (commit 6): the catalogs, after the review fixes.
5. **Phase 5**: Ken's checks on a phone.

Stop after every phase, so Ken can `/compact`.

## Rulings

### Decided (Ken, 2026-11-17)

1. **The filter chips stay**: All, Active, Attention, Finished, each with its count, as today.
   Draft 1 had replaced them with section headings; Ken restored them.
2. **Chips are drawn as the Browse v2 letter pills**: 44 px tall, fully rounded, grey, the picked
   one blue (`#375a7f`). Sized to fit one row on a phone (14 px bold, 8 px side padding, 4 px gaps,
   each chip stretching to share the row), but **allowed to wrap** to a second row rather than
   squeeze or clip.

### Phone pages: one look (Ken, 2026-11-18)

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Processing: Jobs",
"Processing: a failed job opened", "Processing: Library tools" and "Reference palette" (files
`project/ProcJobs.dc.html`, `ProcOpen.dc.html`, `ProcTools.dc.html`). Since 2026-11-26 its three
Processing boards are draft 2, and Ken accepted all of draft 2 on 2026-11-27 (K3). The canvas wins
over this branch's mockup; this file wins over both.

- **L10. Buttons are neutral grey.** Retry, Preview and Check playlist are a row's main action:
  filled grey with a `#5e6d6f` border and bold white text (L4), the fill `#434d4e` (L15). Song
  info and Repair are a grey outline. Red outline stays for delete. Info blue `#3298dc` stays
  only for the running job's spinner and step bar.
- **L14. Processing is the admin's only.** Its nav icon is hidden from guests (the page still
  opens by its address), and nothing a guest sees links here. This branch's guest view is
  dropped. A guest's own failed song shows on Queue instead, as a red "failed" row with Dismiss.
  The failed row and the nav change are both `queue_phone`'s (landed).
- L1 (one green, one amber), L15 and L16 (disabled: no fill, a faded border, a `#8c9b9d` label,
  no opacity fade) are in `bulma-dark.css` on `dev` (from `singer_defaults` Phase 5).

### Decided (Ken, 2026-11-26)

These answer the draft 1 open questions (group order, headings, the step strip) and rule on its
rows. Canvas boards "Processing: Jobs" and "Processing: a failed job opened" draw them.

3. **Order under All: Attention, then Active, then Finished.** The running job's Now card sits
   above the list, under the pinned area.
4. **One flat list, no group headings.** The chips do the sorting.
5. **Pinned while the page scrolls: the Jobs / Library tools toggle and the filter chips**, as
   Browse pins its toggle and letter row (`.bp-pin` in `files.html`: sticky, top 0). The
   "Processing" heading scrolls away. On Library tools only the toggle is pinned. The running
   job's card is not pinned (too tall on a phone), nor is "Clear N finished" (it already ends the
   list, under the finished rows it clears).
6. **The running job shows three steps: Download, Vocals, Lyrics.** Vocals covers extract,
   loudnorm, stem_separation and transcode. Lyrics covers align, transcribe and dereverb. In one
   Windows run (`D:\Shared\whisper_regen\win\w0_run.log`) extract took about 2 s, loudnorm 14 s,
   stem separation 68 s and transcode 21 s, so steps of their own would only flicker. The large
   line still names the exact phase. A regen that skips download and separation shows those
   two steps already ticked. `dereverb` has no label in `T.phases` today (it falls back to
   "processing"): give it one.
7. **No Queue button on finished rows, and no Add to queue in the opened row.** Today Add to
   queue is offered on every finished download (`pipeline_tracker.py`, `actions.append("enqueue")`),
   even when the song already holds its queue slot from the download dialog, so a tap queues it
   twice. Songs downloaded without queueing are queued from Browse or Search. The enqueue
   action, its route and their tests go.
8. **A narrow strip replaces the 60 px slot on every row**, active ones and the Now card included.
   This is Processing's exception to the shared rule that every page uses a 60 px slot, solid for
   a tap and dashed for a state (`plans/queue-phone.md` S1-S4, on tag `archive/queue_phone`).
   Processing is admin-only, so the shared look matters less here, and the strip gives the song
   name the width. The strip is 6 px wide, full row height. Its colours: red failed or
   cancelling, amber needs a pick or unfinished, grey downloading or waiting, green done, info
   blue the running job. A colour on every row, not only on rows that need the host (ratified
   2026-11-26). The state is always in words on the row too, so colour is never the only sign.
9. **Pick lyrics moves into the opened row.** Rows open from a tap anywhere on them, as well as
   from the chevron (which still expands the row, per S1-S4).
10. **Three lines per row, grouped by what each line answers:**
    - the song, 17 px bold;
    - the artist, who or what started it (a guest's name, playlist, update, regenerate), and
      when: 13 px grey;
    - what happened, then what to do: 15 px. Bold red or amber when the row needs the host
      ("Processing failed: retry or delete", "Download failed: retry or delete", "No usable
      caption: pick lyrics", "Didn't finish: reprocess or delete"), plain light grey otherwise
      ("Downloading", "2nd in line", "Cancelling", "Done · Genius"). A finished row's lyric source
      sits here, with any guessed-lines warning in amber beside it.
    The action words are text, not buttons: they name what the opened row offers. The failure
    line says only "Download failed" or "Processing failed": the row has nothing shorter than
    the raw `error_message`, which shows in full when the row opens. "No usable caption" is
    always true of a pick row (`_on_needs_pick`). Draft 1's "caption too sparse" is not something
    the server reports, and is dropped.
11. **Sizes:** the action line at 15 px (above), the step names under the bar at 13 px, the
    opened row's error text at 13 px. The song name and the artist line keep the shared 17 / 13 px.

Checked: a failed download shows as Failed. `_on_download_error` sets `processing_status` to
`error` as well as `download_status`, and `statusOf()` reads that.

Corrected 2026-11-27 (Opus, reading the code for the spec): the server does report "caption too
sparse". A song that waits for a pick carries `reason` `sparse_caption` or `no_caption`
(`library_tools._pick_reason`), and the Attention list's `needs_pick_subline` words it. Ruling
10's line is still right, because "No usable caption" is true of both reasons; only its reason
for dropping the draft's words was wrong. The "Download failed: retry or delete" example is
replaced by K2.

### Decided (Ken, 2026-11-27, for this spec)

- **K1. A guest who opens `/processing` by its address gets one line and nothing else:** "This
  page is for the host. Your songs show on Queue while they are prepared." The guest-only server
  code goes with the guest view: `/processing/user/cancel`, `get_item_user`, the row's `mine`,
  the guest row filter in `get_status`, and `_cookie_user`. A guest can then no longer cancel their
  own download anywhere. Ken accepted that knowing it.
- **K2. A failed download's line reads "Download failed: dismiss".** It has no file, so its
  opened row offers only Dismiss (no Retry, no Delete). Nothing retries a download; the host
  searches again.
- **K3. Draft 2's four unruled parts are accepted as drawn** (12-15 below), with two changes Opus
  proposed and Ken accepted: the Now card's second line drops "started 4 min ago", since the large
  line's time is already the whole job's (`get_active_elapsed_s` counts from the job's start); and
  Reset all's Preview is a grey outline, not red, because red is for delete (L10).
- **K4. Fold in the open issue "A Processing job row never says 'edited'"**: a finished row's
  source reads "(edited)" when the run timed an admin's word edit, as Song Info does.

Draft 2's parts, ruled by K3:

12. **The Now card:** the song in Queue v2's card (a `#375a7f` outline on the `#282f2f` inset) with
    its blue strip and chevron. Under it, a spinner beside a large line naming the phase and the
    job's time ("Separating vocals · 1 min 42 s"), and the three-step bar under that.
13. **The opened row:** a framed box, the error in a dark box, then the buttons in two columns:
    Retry (grey fill, L10), Song info, Dismiss, Delete song (red outline). Cancel and Delete
    confirm in place (Cancel job / Keep it).
14. **The Jobs / Library tools toggle** takes Browse v2's By artist / By song look.
15. **Library tools:** each list is a row with its count in a 60 px slot (dashed red for Looks
    poor; dashed amber for Behind and No timed source), its explanation in a sub-line and in (i)
    tips, and a Preview button on each Regenerate row. The count slots stay there and do not become
    strips: there the number is the information.

### Assumptions (Opus, 2026-11-27, not ruled; reopen any by asking)

- **A1. Line 3's action words follow what the opened row offers.** "Retry or delete" appears only
  when the row offers Delete. A failed regen, reprocess or process row reads "Processing failed:
  retry", because the tracker offers no delete for those kinds and the song stays in the library.
  The unfinished row's main button reads "Reprocess", in ruling 10's word, where today it reads
  "Retry". It posts to the same route.
- **A2. Cancelling is only ever the running job.** `cancel()` drops a waiting row at once and
  marks only the active job, so a cancelling job shows in the Now card (red strip, large line
  "Cancelling"), never as a list row. The board's faded Cancelling row in the list cannot happen,
  so no fade is built.
- **A3. "Nth in line" counts by the row's `position`, as today.** The active download keeps
  position 1 and reads "Downloading", so the next row reads "2nd in line" (as drawn). Ordinals
  come from `Intl.PluralRules(locale, {type: 'ordinal'})` and four msgids (`one`, `two`, `few`,
  `other`: st / nd / rd / th in English). Any other category falls back to `other`. The page is
  given the Babel locale.
- **A4. Line 2's "who"** is the row's `user` for a download (a guest's name, or `Playlist`, which is
  the user name the playlist import uses) and today's label word for a regen or process row
  (Update, Reprocess, Reset, Repair, Regenerate, Process). These stay capitalized as they are now;
  the board lowercases them, but that would add strings. A database row waiting for a pick shows
  its source word (Playlist, Download). Other database rows show none. "When" appears only on
  attention and finished rows, as today. A line 2 with nothing in it is left out.
- **A5. Before the running job enters its first phase** (phase `null`), Download is ticked,
  Vocals and Lyrics are not lit, and the large line reads "Processing".
- **A6. Phase words:** `stem_separation` reads "separating vocals" as the board draws it,
  `dereverb` "removing reverb", and the others keep today's words, capitalized first.
- **A7. The cancel confirm** says "Cancel this job? The download is dropped." on a download row and
  "Cancel this job?" on any other. The board names the guest; that is dropped to avoid
  "Playlist's download". Buttons: "Cancel job" (solid red) and "Keep it". The delete confirm keeps
  today's words, with "Delete song" (solid red) and "Keep it".
- **A8. The Jobs tab's (i)** ("Tap a row to open its details and actions.") goes. The board draws
  none, and every row has a chevron.
- **A9. Library tools' header reads "Library"**, without the board's "· 186 songs": the All songs
  slot shows that count, and a count in prose needs plural forms in the script. For the same
  reason the Regenerate rows keep their count on the Preview button as today ("Preview 14"), and
  their sub-lines are today's (i) texts. Section (i)s: Library keeps lines 1-3 of today's tip; By
  lyric source gets line 4 (cue align and joint), moved from Library; Regenerate keeps its own.
- **A10. A count slot is dashed red or amber only when its count is above 0.** At 0, and while
  loading ("…"), it is the plain slot.
- **A11. The toggle and the chips are page CSS in `processing.html`**, second copies of Browse's
  `.bp-toggle` and `.bp-letter` values. CLAUDE.md says to extract at the third copy. The pin is the
  shared `.pin-top`, whose third user this page is (after Browse and Search).
- **A12. The playlist field is dark** like Search's URL field (`--dark-bg-primary` fill, white
  text, `--dark-border`, 44 px, 6 px corners), as page CSS: the theme's `.input` is white.
- **A13. The Attention route stops sending `subline`.** Processing words a pick row from its
  `source`. `needs_pick_subline` stays, because the pick page uses it.

## What exists (checked 2026-11-27 on `dev` at `cb3ea32a`)

- `templates/processing.html` (980 lines): one template for both views. Admin markup 69-185, guest
  markup 186-201; the script's admin rows 469-614, guest rows 616-666. `syncList` (444-467)
  rebuilds only rows whose state key changed; keep it. Timers and the socket listener are
  SPA-safe (317-321, 862, 962-977); keep them.
- `routes/processing.py`: `_cookie_user` 24-26, page render 29-44 (still passes `admin=`), status
  47-55, attention 58-72 (adds `subline` to pick rows), user cancel 93-113, enqueue 128-133.
- `lib/pipeline_tracker.py`: `get_status(admin, user)` 122-157 (skips non-download rows for a
  guest); `_in_display_order` 196-263 (a pick row is attention only for an admin, and its guest
  case is `active_rank`'s rank 5); `enqueue` 361-371, the only user of `_queue_manager` (import
  18, parameter 92, attribute 99); `get_item_user` 355-359; `_poor_lines` 662-675 (reads
  `song_status`, never raises); `_item_to_dict` 724-795 (`is_owner`, `can_operate`, `mine`,
  `enqueue` 765-772, `guessed` for admins only).
- `PipelineTracker(...)` is built in `karaoke.py:298` and in tests: by keyword in
  `test_processing_page.py:66` and `test_processing_routes.py:38, 1014, 1274`; **by position** in
  `test_processing_manager.py:1394, 1539` and `test_karaoke_rename_singer.py:32`.
- `library_status.song_status(path)` has `.edited` (the run timed an admin's word edit of its cue
  sheet) beside `.poor`, `.guessed` and `.line_count`.
- `source_names.qualified_name(name, origin=..., edited=...)` gives "LRCLIB (auto, edited)".
- `song_manager.split_title(title) -> (artist, song)` is the shared rule; `routes/queue.py:76`
  applies it to queue rows. A tracker row's `title` is the download's YouTube title, or the file
  name for a regen or process row.
- `routes/admin.py` `inject_admin` gives every template `admin`. `test_processing_page.py`'s
  `get()` patches only `routes.processing.is_admin`. When the render stops passing `admin=`, the
  test app must register `admin_bp` and patch `pikaraoke.routes.admin.is_admin` too
  (`plans/open-issues.md`, "Two routes still pass `admin=`...").
- `library_tools.PLAYLIST_USER = "Playlist"` is the `user` of a playlist import's downloads.
- `attention_rows` gives database rows with `actions` `["retry", "song_info", "delete"]`
  (failed, unfinished) or `["pick", "song_info", "delete"]` (pick, with `source` and `reason`).
- Theme (`bulma-dark.css`): `.button` is the grey fill `#434d4e` with a `--dark-border` border;
  `[disabled]` is L16's look; tokens `--dark-bg-primary` `#1f2424`, `--dark-bg-secondary`
  `#282f2f`, `--dark-bg-tertiary` `#343c3d`, `--dark-text-sub` `#b5bfc0`, `--dark-text-muted`
  `#8c9b9d`, `--dark-text-light` `#dbdee0`, `--dark-danger-text` `#f17a6b`, `--dark-border`
  `#5e6d6f`, `--dark-border-light` `#8c9b9d`, `--dark-primary`, `--dark-info`, `--dark-danger`,
  `--dark-success`, `--dark-warning`.
- `phone-rows.css`: `.sr-row` (60 px min, 6/8 padding, 8 px bleed, even rows shaded), `.sr-main`,
  `.sr-title`, `.sr-sub`, `.sr-slot`, `.sr-num`, `.sr-btn` (40 x 40 grey). On `search_phone`
  (`b600007a`), not yet on `dev`: `.pin-top`.
- Nothing else calls `/processing/status`, `/processing/user/cancel`, `/processing/<id>/enqueue`,
  `PipelineTracker.enqueue`, `get_item_user` or `get_status` outside the routes and tests.
  `/library/songs` is read only by this page.

## Design

### Phase 1: the server

**Commit 1: Add to queue goes (ruling 7).**

- `pipeline_tracker.py`: delete `enqueue()`, the `enqueue` block in `_item_to_dict`, and the
  `queue_manager` parameter, attribute and import.
- `karaoke.py`: drop `queue_manager=` from the tracker's construction.
- `routes/processing.py`: delete `enqueue_item`.
- `processing.html`: delete the `enqueue` URL, `T.addToQueue`, the opened row's Add to queue
  button, the guest row's "+" button and `runAction`'s `enqueue` case.
- Tests: delete `TestEnqueueStaysOpen` and every `enqueue` assertion. Drop the third argument
  from every tracker construction. Where a test passes it by position, the arguments after it
  shift: check each one. No new test, since what is checked is an absence.

**Commit 2: the page is the admin's (K1), and the render takes `admin` from the context
processor.**

- `routes/processing.py`: the render stops passing `admin=`. `processing_status` answers
  `jsonify([])` to a guest, as `processing_attention` does, and otherwise returns
  `k.pipeline_tracker.get_status()`. Delete `user_cancel_item`, `_cookie_user`, and the imports
  nothing uses after that (`unquote`, `request`: check).
- `pipeline_tracker.py`: `get_status()` takes no arguments, and every row is shown.
  `_in_display_order` loses `admin`: a pick row is always attention, and `active_rank`'s pick
  branch and the docstring's guest lines go. `_item_to_dict(item, elapsed_s)` loses `admin`,
  `user`, `is_owner`, `can_operate` and `mine`; the actions are today's admin set, and `guessed`
  and `line_count` are sent unconditionally. Delete `get_item_user`. In `rename_user`'s docstring
  the reason becomes "so its rows show the new name".
- `processing.html`: `{% if admin %}` keeps the page; `{% else %}` is one paragraph with K1's
  words. The scripts block renders only for an admin. Delete the guest markup, `guestIcon`,
  `guestRow`, `renderGuest`, `isAdmin` and every branch on it (including `statusOf`'s pick case
  and `refresh`'s), the `userCancel` URL, the `{% if admin %}` inside `URLS`, and `T.you`,
  `T.addedBy`, `T.readyToSing`, `T.downloadFailed` and `T.processingFailed`.
- Tests:
  - `test_processing_page.py`: `get()` registers `admin_bp` and patches
    `pikaraoke.routes.admin.is_admin` as well. The guest tests are replaced by one: a guest gets
    200 with the note, and no toggle, chips, rows container or page script. Keep `queue_phone`'s
    check that the nav icon is absent.
  - `test_processing_routes.py`: delete `TestGetItemUser`, `TestUserCancelEndpoint`,
    `TestEncodedNameCookie`, and every guest read (`admin=False`) and `mine` assertion. Calls of
    `get_status(admin=..., user=...)` become `get_status()`, here and in
    `test_processing_manager.py`. `TestRenameUser` asserts the row's `user` rather than `mine`.
    New: a guest's `GET /processing/status` answers `[]` while the tracker holds rows.

**Commit 3: rows carry song and artist, and a finished row knows whether its words were edited
(K4).**

- `pipeline_tracker.py`: `_poor_lines` becomes `_finished_status(song_path)`, which returns
  `(poor, edited)`: `poor` is `(guessed, line_count)` or `None` as before, and `edited` is
  `status.edited`. It has the same one `song_status` call, the same caught exceptions and the
  same never-raise contract, and returns `(None, False)` on a read error.
  `PipelineItem.lyric_edited: bool = False` is set in `_on_processing_complete`, and the row dict
  gains `"edited"`.
- `routes/processing.py`: one helper adds `artist` and `song` from `split_title(row["title"])` to
  each row, used by both `processing_status` and `processing_attention`. The render passes
  `lyric_sources_edited`, `{origin: qualified_name(name, origin=origin, edited=True)}`, beside
  `lyric_sources`.
- `processing.html`: `lyricLabel(method, edited)` takes the name from the edited map when the row
  says `edited`, and the state key includes `edited`. Nothing else changes on the page yet.
- Tests (routes): a regen row for `Artist - Song---abcdefghijk.mp4` reads artist "Artist", song
  "Song"; a title with no split reads artist "" and the whole title as song; an attention row
  carries both too. Tracker: with `song_status` patched to `edited=True`, the finished row reads
  `edited: True`; by default `False`; when the bundle read raises, `False` and the row still
  completes (beside `TestPoorSongNumbers`). Page: the edited map is in the script, as
  `test_a_job_row_names_its_lyric_source_by_origin_as_song_info_does` checks the plain one.

### Phase 2: the Jobs view (commit 4)

Rebase onto `dev` first (see Order). Boards: `ProcJobs`, `ProcOpen`. Values below come from the
boards, written as theme tokens.

**Markup** (admin branch of `processing.html`; the page links `phone-rows.css`):

```html
<div id="pr-root">
  <div class="pin-top">
    <div class="pr-toggle" role="group" aria-label="View">
      <button type="button" data-tab="jobs" aria-pressed="true">Jobs</button>
      <button type="button" data-tab="tools" aria-pressed="false">Library tools</button>
    </div>
    <div class="pr-chips" role="group" aria-label="Show">  <!-- hidden on Library tools -->
      <button type="button" data-filter="all" aria-pressed="true">All <span class="pr-chip-n">0</span></button>
      ... active, attention, finished ...
    </div>
  </div>
  <div id="pr-jobs"> #pr-now, #pr-rows, the two empty lines, #pr-clear </div>
  <div id="pr-tools" class="is-hidden"> (Phase 3 restyles it) </div>
</div>
```

The `Processing` heading stays in `{% block header %}` and scrolls away. The `has-tip` toggle on
the Jobs tab goes (A8).

**CSS** (page `<style>`; nothing restated from `phone-rows.css` or the theme):

- `.pr-toggle`: Browse's `.bp-toggle` values (flex, gap 4, padding 4, margin 0 20px 12px, radius
  10, `--dark-bg-secondary`). Its buttons: flex 1, height 40, radius 7, no border, transparent,
  15 px, `--dark-text-light`. Pressed: `--dark-primary`, `--dark-text-primary`, bold. The margin
  below is 0 on Library tools, where the chips are hidden.
- `.pr-chips`: flex, wrap, gap 4, padding 0 20px. A chip: flex `1 1 auto`, height 44, padding
  0 8px, radius 22, no border, `--dark-bg-secondary`, `--dark-text-primary`, 14 px bold, no wrap.
  Pressed: `--dark-primary`.
- `.pr-strip`: flex none, width 6, `align-self: stretch`, radius 3. Colours: `.is-red`
  `--dark-danger`, `.is-amber` `--dark-warning`, `.is-grey` `--dark-border`, `.is-green`
  `--dark-success`, `.is-blue` `--dark-info`.
- A row is `.sr-row.pr-row`, holding the strip and a `.pr-body` (flex 1, min-width 0, column). In
  the body: `.pr-line` (flex, align center, gap 10) with `.sr-main` and the chevron, then the
  opened detail. The `.sr-row` must be the element `syncList` keys, so the even-row shading
  still applies. Adjust `syncList` so it no longer wraps each entry in another `div`.
- `.sr-main` holds `.sr-title` (the song), `.sr-sub` (line 2) and `.pr-state` (15 px, line-height
  1.3, `--dark-text-light`). `.pr-state.is-red`: bold `--dark-danger-text`. `.pr-state.is-amber`:
  bold `--dark-warning`. The guessed warning is a `--dark-warning` span inside it.
- The chevron is `.button.sr-btn.pr-chev` with `icon-angle-down` and `aria-label` "Options for
  <song>". Open (`aria-expanded="true"`): `--dark-primary` fill, `--dark-text-primary`, a
  `--dark-border-light` border, the icon turned 180 degrees.
- `.pr-row.is-open`: `--dark-bg-secondary`, 1 px `--dark-border`, radius 8, above the even
  shading. Its strip takes a 6 px top and bottom margin.
- `.pr-detail`: padding 4px 12px 14px 0, column, gap 12. `.pr-error`: padding 10px 12px, radius
  6, `--dark-bg-primary`, `--dark-danger-text`, monospace 13 px, line-height 1.45,
  `overflow-wrap: anywhere`, `max-height: 16.8em`, scrolls. `.pr-buttons`: a 2-column grid, gap 8.
- `.pr-btn`: height 44, radius 6, 16 px. The main action is a plain `.button` (the theme's grey)
  with bold `--dark-text-primary`. `.is-outline`: transparent, `--dark-text-light`, weight 400.
  `.is-delete`: transparent, `--dark-danger` border, `--dark-danger-text`. A confirm's yes is
  `.button.is-danger`, bold.
- `.pr-now`: padding 12, radius 8, `--dark-bg-secondary`, 1 px `--dark-primary`, margin-bottom 16,
  column, gap 12. Its top line has the same strip, `.sr-main` and chevron as a row. The large
  line: flex, gap 10, a 20 px spinner (3 px ring, `--dark-info` at 30 % with a full `--dark-info`
  top), and text at 20 px bold, line-height 1.3, `--dark-text-primary`, breathing (opacity
  1 to .55 and back over 2.4 s). With `prefers-reduced-motion`: no breathing, and the spinner
  turns once in 6 s. The steps: a 3-column grid, gap 4; each step is a 6 px bar (radius 3) over
  a 13 px name. Done: bar and name `--dark-text-sub`. Current: bar `--dark-info`, name
  `--dark-text-primary` bold. Not yet: bar `--dark-bg-tertiary`, name `--dark-text-muted`.
- `#pr-clear`: `.pr-btn.is-outline`, full width, margin-top 16.
- Delete `.pr-tabs`, `.pr-chip` (the old one), `.pr-card`, `.pr-line`, `.pr-pos`, `.pr-tag`,
  `.pr-grow`, `.pr-g*`, `.pr-you`, and every rule nothing uses any more.

**Script:**

- `groups.all` is `attention.concat(active, finished)` (ruling 3).
- One function gives each row its strip colour, its line 3 and that line's style, replacing
  `statusOf`, `TAG_CLASS` and `tagHtml`:

  | Row | Strip | Line 3 | Style |
  |---|---|---|---|
  | running job (Now card) | blue | (large line: phase · time) | |
  | running job, cancelling | red | (large line: "Cancelling") | |
  | active, `download_status` `active` | grey | Downloading | plain |
  | other active | grey | Nth in line (A3) | plain |
  | tracker error, `download_status` `error` | red | Download failed: dismiss | red |
  | tracker error, offers delete | red | Processing failed: retry or delete | red |
  | tracker error, no delete | red | Processing failed: retry | red |
  | tracker `needs_pick` | amber | No usable caption: pick lyrics | amber |
  | database `failed` | red | Processing failed: retry or delete | red |
  | database `unfinished` | amber | Didn't finish: reprocess or delete | amber |
  | database `needs_pick` | amber | No usable caption: pick lyrics | amber |
  | `complete` | green | Done[ · source][ · N of M lines guessed, amber] | plain |

  "Offers delete" is today's `offers(row, 'delete')`.
- Line 1 is `row.song || row.title`. Line 2 is `[row.artist, who(row), when(row)]`, with the empty
  ones dropped, joined by " · " (A4). The Now card's line 2 has no "when" (K3).
- Buttons in the opened row, by what the row offers, in this order:

  | Action | Look | Label |
  |---|---|---|
  | `retry` | main | Retry ("Reprocess" on a database `unfinished` row, A1) |
  | `pick` | main, a link to the pick page | Pick lyrics |
  | `song_info` | outline, a link | Song info |
  | `cancel` | outline | Cancel |
  | `dismiss` | outline | Dismiss |
  | `remove` or `delete` | delete | Delete song |

  Confirms replace the buttons in place, as today, with A7's words.
- A tap anywhere on a row or on the Now card toggles it open, except a tap that lands inside its
  `.pr-detail`. The chevron is the row's only focusable control.
- Steps: Download is always done. Vocals is current for `extract`, `loudnorm`, `stem_separation`
  and `transcode`; Lyrics for `align`, `transcribe` and `dereverb`. Steps before the current one
  are done, steps after it not yet. With phase `null`, A5 applies.
- `T.phases` gains `dereverb` "removing reverb", and `stem_separation` becomes "separating vocals"
  (A6). The large line reads `upperFirst(phase word) + ' · ' + elapsed`. `#pr-now-elapsed` stays
  the ticking part.
- Ordinals: the render passes `locale`, `str(flask_babel.get_locale() or "en")` with `_` turned
  into `-`. The script builds one `Intl.PluralRules(LOCALE, {type: 'ordinal'})` and falls back to
  `'en'` if the constructor throws. `T.inLine` holds the four forms, each with a `{# MSG: #}`
  comment that says which English ordinal ending it carries.
- Line 1 now uses the song alone, so the row's `title` attribute (its tooltip) shows the full
  title, as today.
- The state key adds `song`, `artist`, `edited` and the line 3 words.
- The toggle's `showTab` sets `aria-pressed`, shows one panel, and hides `.pr-chips` on Library
  tools. The `#jobs` / `#tools` hash behaviour stays (the pick, run and playlist pages link to it).
- `routes/processing.py`: the attention route drops `subline` (A13). Delete the import of
  `needs_pick_subline` if nothing else here uses it, and the test of the subline.
- Delete every `T` entry that nothing reads any more (`now`, `kindRegen`, `kindProcess`,
  `waiting`, `failed`, `unfinished`, `needsPick`, `dbUnfinished`, `dbFailed`, and others), and
  every helper that no longer has a caller.
- Strings added: the four `inLine` forms; "Download failed: dismiss"; "Processing failed: retry or
  delete"; "Processing failed: retry"; "No usable caption: pick lyrics"; "Didn't finish:
  reprocess or delete"; "Cancel this job? The download is dropped."; "Vocals"; "Lyrics";
  "separating vocals"; "removing reverb"; and the source words (`Playlist` and `Download` exist
  already). "Keep it" already exists as a msgid.

**Tests** (`test_processing_page.py`, markup and script text, the way the file already tests):
the pin holds the toggle and the chips, and the `<h1>` is outside it; the toggle's buttons carry
`aria-pressed` and there is no `tabs` class; the script has a phase word for each `Phase` value
(read the enum, so a new phase without a word fails); the chips' four filters; the strings of
the line 3 table are in the script; no `enqueue`; no `subline` read. Rewrite or delete the tests
the old markup broke (tabs, tags, `.pr-line`). Behaviour goes to `ui-check`.

### Phase 3: Library tools (commit 5)

Board: `ProcTools`. Same CSS conventions as Phase 2; the toggle is pinned alone (ruling 5).

- **Section headers** `.pr-sec`: 13 px `--dark-text-sub`, sentence case (no uppercase, no letter
  spacing), margin 24px 0 8px (the first 0 0 8px), an (i) where A9 puts one: Library, By lyric
  source, Regenerate. Add playlist has none.
- **List rows** (Library: behind, poor, no_lyrics, all; By lyric source: caption, movie, lrc,
  lrc_auto, genius, custom, no_timed_source): an `.sr-row` with an `.sr-slot.pr-count` holding the
  count in `.sr-num` ("…" until loaded), an `.sr-main` (`.sr-title`, `.sr-sub`) and the chevron.
  The whole row taps, as on Jobs. `.pr-count.is-bad`: no fill, 1 px dashed `--dark-danger`,
  `--dark-danger-text`. `.is-warn`: the same in `--dark-warning`. Each is applied only when the
  count is above 0 (A10). Titles and sub-lines:

  | List | Title | Sub-line | Count |
  |---|---|---|---|
  | behind | Behind current version | Made on older code | warn |
  | poor | Looks poor | Many lines guessed | bad |
  | no_lyrics | No lyrics | Words from what is heard | |
  | all | All songs | The whole library | |
  | caption, movie, lrc, lrc_auto | `lyric_sources[...]` (as today, without "· cue align") | Cue align | |
  | genius, custom | `lyric_sources[...]` | Joint | |
  | no_timed_source | No timed source | Nothing to align to | warn |

- **An opened list** takes the opened-row frame (`.is-open`), with the chevron blue. Inside,
  `.pr-songs` (padding 0 12px 8px) holds song rows. Each song row: min-height 52, a 1 px
  `--dark-bg-tertiary` top rule, flex, gap 10. On the left, a link to Song Info with the song at
  15 px bold (`row.song || row.name`) and, at 12 px `--dark-text-sub`, `row.artist` and the
  server's `subline` joined by " · " (the `subline` in `--dark-warning` on the poor list). On the
  right, Repair: an outline link, height 40, padding 0 12px, radius 6, 14 px bold,
  `--dark-text-light`, `--dark-border`. One list open at a time, as today.
- **`/library/songs`** rows gain `artist` and `song` from `split_title(name)`. This lives in
  `routes/library.py`, and its route test gets one case.
- **Regenerate**: three cards in a column, gap 8. Each card: `--dark-bg-secondary`, radius 8,
  padding 10px 12px, flex, align center, gap 12. On the left the title (17 px bold) and a sub-line
  (13 px `--dark-text-sub`, today's (i) text). On the right a Preview `.pr-btn` (height 44,
  padding 0 16px, 15 px) with its count as today: Update stale songs main; Reprocess all and Reset
  all outline (K3). Disabled until loaded and at 0, as today.
- **The open-run banner** takes the same card look. Continue is the main action (it was
  `is-primary`, L10) and Discard is an outline. The confirm is "Discard run" (solid red) and
  "Keep it".
- **Add playlist**: a card (`--dark-bg-secondary`, radius 8, padding 12, column, gap 10). The
  label is 15 px `--dark-text-light`, then the field `.pr-url` (A12), then Check playlist as the
  main action across the full width (it was `is-primary`), disabled until there is a link.
- Delete the old `.pr-link`, `.pr-list`, `.pr-chev`, `.pr-song*`, `.pr-run*` and `.pr-banner`
  rules and whatever else nothing uses.
- **Tests:** each list id is still on the page, with its count hook; the source lists are still
  named by `lyric_sources` (update `test_the_source_lists_name_their_source_as_the_job_rows_do`);
  "By lyric source" has an (i) that holds the cue-align line, and Library's no longer does;
  Reset all's Preview is not `is-danger`; Continue and Check playlist are not `is-primary`.

### Phase 4: the catalogs (commit 6)

After the review fixes, and after `search_phone`'s catalog commit is on `dev`, since both
regenerate `messages.pot`. From `pikaraoke/`:

```shell
pybabel extract -F babel.cfg -o messages.pot --add-comments="MSG:" --strip-comment-tags --sort-by-file .
pybabel update -i messages.pot -d translations
python ../scripts/compile_translations.py
```

Never `pybabel compile`. Check `messages.pot`: every string Phases 2-3 added is present once; the
removed guest strings ("YOU", "added by %(user)s", "Ready to sing", "The download failed. Try
another video of this song.", "This song couldn't be prepared. The host can retry it.", "Add to
queue" if no other page uses it) are obsolete. Say in the commit message whether any `.mo`
changed, and how.

## Not doing

- Retrying a failed download (K2).
- A guest cancelling their own download anywhere (K1).
- Pinning the nav bar ("Keep the top blue nav bar on screen", open issues); `.pin-top` already
  says where its `top` would change.
- Extracting the toggle and chip CSS (A11).
- "A failed song stays 'needs fix' while its retry runs" (open issues): Browse's and Queue's.

## Commits

1. `refactor(processing): job rows drop Add to queue`
2. `refactor(processing): the page is the admin's; a guest gets one line`
3. `feat(processing): job rows carry song and artist and say when the words were edited`
4. `feat(processing): the Jobs view takes the phone look`
5. `feat(processing): Library tools take the phone look`
6. `i18n: regenerate translation catalogs for the Processing page`

Each commit, before committing: the full suite (`/home/ken/miniconda3/envs/pik/bin/python -m
pytest tests/unit`), pre-commit on the changed files, `git diff --cached` read against this plan.
Commits 4 and 5 also run the `ui-check` scenarios that touch them. Write a Results row per commit
(hash, suite count and changed test counts, `ui-check` script paths and pass counts, anything
done beyond the spec).

## `ui-check` recipe

The `ui-check` skill (`/home/ken/pikaraoke/.claude/skills/ui-check/`), this worktree as
`CHECKOUT`, a port nobody uses. `launch.sh` kills whatever listens on its port, so confirm the
listener is yours. Relaunch after each template commit. The launch has no admin password, so the
page is the admin's. Join by `POST /singer` and set the `user` and `singer_token` cookies, since
`new_page`'s `user` cookie alone leaves `#singer-modal` over the page. Use a `p.devices["Pixel 7"]`
context and `page.tap`. Keep the scripts in the session scratchpad and name them in the Results
row.

Fixture states come from Playwright routes answering `/processing/status`,
`/processing/attention`, `/library/overview`, `/library/songs` and `/library/run_status`, with
rows shaped as the real routes answer. One fixture draws the board's fifteen rows plus a running
job. One real run uses `FAKE_JOB_S=20` and `uihelpers.retry`.

Phase 2 scenarios:

1. The board fixture under All: order Attention, Active, Finished; each row's strip colour, line 3
   words, weight and colour (computed); line 2 as A4; chip counts. Screenshots at the top and
   scrolled, beside `ProcJobs`.
2. Scrolled: the pin's top is 0 and holds the toggle and chips; the heading and the Now card have
   scrolled away; a point inside the pin hits the pin. On Library tools only the toggle is pinned.
3. A tap on a row's text opens it; the chevron is blue and turned; a second tap closes it; a tap
   on a button inside the detail does not close it.
4. The failed processing row opened: the error box, Retry, Song info, Dismiss and Delete song in
   two columns (computed fills and borders as L10). Delete asks in place; Keep it puts the buttons
   back. A failed download opened offers Dismiss only. Screenshot beside `ProcOpen`.
5. The Now card with phase `extract`, `stem_separation`, `align`, `dereverb` and `null`, a regen
   at `align`, and a cancelling job: steps and large line as the spec says; red strip and
   "Cancelling" for the last.
6. The real run: the Now card appears, its time ticks once a second, and the job ends as a green
   Finished row. Then move by SPA to Queue and back twice: still one tick a second, one
   `pipeline_updated` listener, no console errors.
7. Each chip filters; an empty filter shows "No songs in this list."; Clear N finished sits under
   the finished rows.
8. `/processing#tools` opens Library tools (the pick page's back link).
9. "Nth in line" with an English locale gives 2nd, 3rd, 4th, 11th, 12th, 13th, 21st, 22nd.

Phase 3 scenarios:

10. The Library tools fixture with counts above 0 and at 0: slot styles (A10), titles and
    sub-lines, an opened list framed with its song rows and Repair, the Regenerate cards with
    Preview disabled at 0, the open-run banner and its discard confirm, Check playlist disabled
    until a link and the field dark. Screenshots beside `ProcTools`.

For GATE V, stop with the screenshot paths and the computed-style tables. Give no verdicts.

## Manual checks (Ken, on a phone), Phase 5

- [ ] Jobs looks like "Processing: Jobs": the toggle and chips stay at the top while the list
      scrolls; the heading scrolls away.
- [ ] A real download: its row reads Downloading, then the Now card shows Download ticked, Vocals
      lit while it separates, Lyrics lit while it aligns, the phase and time in the large line.
- [ ] It ends as a green row, "Done" with its lyric source. No Queue or Add to queue anywhere.
- [ ] A regen of a song whose sheet you edited ends reading "(edited)" as on Song Info.
- [ ] A download with no usable caption: amber, "No usable caption: pick lyrics"; opened, Pick
      lyrics goes to the pick page.
- [ ] Open a failed row by tapping its name: the error in its box, the four buttons; Delete asks
      first.
- [ ] Cancel the running job: the card turns red and says Cancelling, then goes.
- [ ] Library tools looks like "Processing: Library tools": counts in slots, lists open in place,
      Repair, Preview opens the run page, Check playlist opens the playlist page.
- [ ] On a guest phone: no Processing icon, and the address shows only the one line.

## At landing (not Sonnet's)

- Copy the code commits onto `dev` in order, without the plan.
- `plans/open-issues.md` on `dev`: strike "A Processing job row never says 'edited'"; rewrite
  "Two routes still pass `admin=`..." to `home.py` alone; update the landing order's
  `processing_phone` line.
- Retire the branch as `archive/processing_phone` and repoint references.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
