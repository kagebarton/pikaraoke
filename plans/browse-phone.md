# Browse page for phones

Model: Claude Opus 5.5 (decisions, specs, judging). Each phase names its executor and judge.

Branch `browse_phone` off `dev` at `764df44`, worktree `.claude/worktrees/browse_phone`.

Mockup (private to Ken): https://claude.ai/artifact/8nSQUuVfMQ3cKNnRY31C9p. Top row: Browse as
built today, then the first drafts ("After"). The row titled "Browse v2" (three screens: admin by
artist, admin by song, guest by song) is the agreed design. The Queue screens on the same canvas
show today's Queue page only; it has no decisions yet. Where this file and the mockup differ, this
file wins.

## Decisions (Ken, 2026-11-17)

1. **No pages, no A-Z side bar, no sort link.** One sideways-swiping strip of letters at the top,
   `#` then A-Z, 44 px targets. No "All". A letter shows every song under it, no paging. Letters
   with no songs are greyed out and can't be tapped.
2. **By artist / By song toggle** above the strip. The chosen field is the big top line of each
   row, sets the sort order and decides which letter a song is under; the other field is the small
   line under it.
3. **Two-line rows:** top line 17 px bold, bottom line 13 px grey. A name that can't be split into
   artist and song shows as one plain line and is filed under its first letter in both modes.
4. **No line numbers.**
5. **Queue button with text**, left of the title, 60 px wide.
6. **Guests see no edit or info controls.** Admins get one square button with only a gear
   (a chevron until S3, below), which opens a menu with Edit song and Song info. Edit all songs stays at the top right.
7. **Three states, shown in the Queue button's place:**
   - Ready: green Queue.
   - Processing: blue (green since L8, below) Queue with "processing" in small text under it.
     Still tappable: the queue holds the song's place (`_do_enqueue`, `routes/queue.py`). Covers
     running, in line for processing, downloading, and waiting for a lyrics pick.
   - Needs fix: a dashed box, not a button, for admins only. Covers a failed song and a song that
     never finished processing with nothing working on it, both of which `_do_enqueue` refuses.
     Song info says which and offers the fix.
8. **Guests never see needs-fix songs.**
9. **Titles wrap between words**, not mid-word (today's `break-all` goes).

## Phone pages: one look (Ken, 2026-11-18)

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Browse: admin, by
artist", "Browse: admin, by song", "Browse: guest, by song" and "Reference palette". For colours
and buttons it wins over this branch's mockup; this file wins over both.

- **L8. The "Queue / processing" button is green** `#2ecc71`, like Ready, not info blue
  `#3298dc`: the song can be queued now and plays when ready. Changes decision 7's Processing
  state.
- Every page (L2, L3): blue `#375a7f` only for a chosen option (the sort toggle, the letter),
  teal `#1abc9c` only for links and the current nav icon. The canvas draws the admin's button
  as a grey square, `#434d4e` with a `#5e6d6f` border (L15), still with a chevron (S3 makes it
  a gear).
- L1 (one green, one amber), L15 (grey fill `#434d4e`) and L16 (disabled: no fill, a faded
  border, a `#8c9b9d` label, no opacity fade) land in `bulma-dark.css` on `singer_defaults`, its
  Phase 5. This branch takes them from `dev` once that lands.
- **Empty letters take L16's disabled look** (Ken, 2026-11-18): no fill, a faded border
  (`#5e6d6f` at half strength), a `#8c9b9d` label, no opacity fade. The canvas's dimmer pill
  (`#2b3131`, label `#6b7a7c`) is not followed.
- **Ruled for the shared stylesheet** (Ken, 2026-11-18; `plans/queue-phone.md` on
  `queue_phone`, S1-S4): S1, the state slot is 60 px on every page, so this page's stays. S2,
  solid means a tap and dashed a state, so the green "Queue / processing" button stays a
  button here. S3, a gear opens a menu and a chevron expands a row, so the admin's button is a
  gear (decision 6). Take the row, slot and button styles from Queue's stylesheet once it is
  on `dev`.

## Where the names come from (ruled at GATE N, below)

The library on disk was renamed by hand to `Artist - Title`, so splitting the file name at the
first " - " works for it. Songs downloaded during a session keep their raw YouTube title, which may
have no " - " ("Bohemian Rhapsody | Queen") or have it backwards ("Hello - Adele").

Candidate sources, each falling back to a one-line row:

- **(a) File name split** at the first " - ". Ken: probably fine if (c) doesn't earn its place.
- **(b) The YouTube title parser**, `parse()` in `genius_query.py`, which pulls artist, title and
  film out of a raw title (and the channel). No network, and it can't pick a wrong song.
- **(c) The Genius match's names**, used only when they agree with the file name (the matched
  artist and title words appear in it; `_names` and `_credited` in `genius_query.py` are the
  existing checks of this kind), else fall back to (a) or (b). The lyrics stage already records
  the match (`ctx.artifacts["genius"]`, `pipeline/stages/lyrics_fetch.py`); the `songs` table has
  `artist` and `title` columns that nothing fills today.

Ruled out for now: renaming the file to `Artist - Title` at download.

Why (c) needs a test first (Ken): a wrong Genius match would label a row with the wrong song, so a
guest picks "Hello / Lionel Richie" and gets Adele. The file played is always the row's own file;
only the label can be wrong. A wrong match also means wrong lyrics, so that song needs a repair
anyway, which would fix its label too.

## Phase 0: name-source test (offline, on the VM)

Executor: Sonnet. No GPU, no network, no app code changes; a script under `scripts/` or the
scratchpad plus its saved output. Stop when the artifacts are saved: paths and raw tables, no
tallies-as-verdicts.

Inputs:

- **Set G:** the 118 raw YouTube titles in `tests/unit/data/genius_search/gate_g.jsonl`, each with
  its frozen Genius preselect (63 have one) and the hits in `gate_g_answers.json`. Two preselects
  are known wrong (5.4 `ed1RIhS7lDA`, 6.1 `mSfH2AuhXfw`). None of these videos is in the library.
  Judged on raw YouTube titles only, as GATE G was.
- **Set L:** the library (248 songs). Truth is the current hand-made file name. The raw YouTube
  title at download survives in the debug bundles (`alignment_debug/*.json`, `lyrics.source_path`
  of a caption song); 54 bundles also record a Genius match (`lyrics.genius`).

Per song, write what each source would show (top line, bottom line, or one line) for (a), (b),
and (c) with its fallback. For set L, compare against the current file name. For set G there is no
written truth; the judge marks each row right, wrong, or one-line.

What the judge reads:

- Wrong labels per source (the cost that matters most). (c) must show none from the two known
  wrong preselects.
- Rows that fall back to one line per source (the cost of being cautious).

Judge: Opus reads the tables and the wrong rows; Ken rules.

## GATE N

Ken picks the name source: (a), (b), or (c) with its fallback. If (c) shows no wrong labels and
clearly fewer one-line rows than (a) or (b), it earns Phase 2; otherwise Browse uses (a) or (b)
and Phase 2 is dropped.

**Ruled (Ken, 2026-11-18): (a), with (b) for a name (a) can't split.** Split the file name at the
first " - ". When that gives no split, take `parse()`'s artist and song, but only when it finds
both; otherwise the row is one line, the whole name. Phase 2 is dropped. The judge's read is
`plans/browse-phone-phase0/judge.md`.

- (c) failed both checks: c1 showed the two known wrong preselects; c2 saved no one-line rows
  over its fallback.
- (b) alone doesn't fit Browse, which reads the file name and has no channel: on the hand-made
  names it puts every film-named song on one line and strips what Ken added (year,
  "(Sing-Along)", the English title after a Chinese one).
- The fallback leaves every split name as it is. On the names it touches it reads 7 of the
  library's 17 one-line names and about a third of the one-line downloads, and swaps about one
  in five ("What Is This Feeling / Wicked"); it never names a different song. The guard keeps
  a parse that finds only the singer from replacing a line that still holds the song.

## Phase 1: Browse page

Executor: Sonnet. Spec: Opus, 2026-11-24, on `browse_phone` `d23631ac` (rebased onto `dev`
`d3f3bf66`, which has `queue_phone`, `singer_defaults` Phase 5 and `download_modal_speed`).
Judge of the ui-check artifacts: Opus, then Ken.

### Ruled for Phase 1 (Ken, 2026-11-24)

10. **Browse reopens where this phone left it.** A plain `/browse` (the nav bar's link) shows the
    mode and letter this phone last used, kept in cookies. A remembered letter that has no songs
    now falls back to the first letter that has.
11. **The first visit is By artist**, at the first letter with songs.
12. **The By artist / By song toggle and the letter strip stay pinned together** while the list
    scrolls, with 12 px of the card's colour above the toggle rather than flush with the top edge
    (Ken's phone check, 2026-11-24, `51d0c1cc`; first ruled as the strip alone, toggle scrolling
    away).
13. **Rows show the state at page load.** No socket listener: a song that finishes or fails while
    the page is open changes on the next load (any letter tap). A tap on a song that failed in
    the meantime gets the server's refusal toast.
14. **Empty letters are disabled, in L16's look** (decision 1 and the 2026-11-18 ruling, restated).
    **The strip fades at each edge that has letters past it** (Ken asked; Opus's answer): the
    right edge on load, the left once scrolled, neither at an end.

### Checked against the code (2026-11-24)

What moved, or differs from the scope list this section replaces:

- `split_title` is on `dev` as `446baa7d` (`queue_phone`'s `b80647d4`, landed as a copy). Its
  callers are `routes/queue.py` `get_queue` and `karaoke.py` `get_now_playing`; Browse is the
  third.
- `flask_paginate` stays a dependency: `routes/batch_song_renamer.py` still pages with it. Only
  `browse()` drops it.
- `browse_results_per_page` has no CLI flag (`app.py` never passes it). Its uses:
  `PreferenceManager.DEFAULTS`, `Karaoke.__init__`'s parameter and docstring, `routes/info.py`,
  the `info.html` field (labelled "default 500"; the default is 100), three tests in
  `test_preference_manager.py`, `test_info_routes.py`, `test_files_routes.py`.
- The states need no tracker read. `_do_enqueue` (`routes/queue.py`) decides from the pipeline
  state and `QueueHold.waiting_for` (`is_waiting_for_pick`, then `is_busy`); Browse takes the same
  rule (commit 2). Two differences from today's tags follow: a ready song being reprocessed shows
  Ready (today a "processing" tag), because the queue takes it as ready; and decision 7's
  "downloading" never shows, because a song has no library file until its download lands.
- A failed song whose retry is running shows needs fix until the retry ends: its state stays
  `failed` until then, and `_do_enqueue` refuses it. That is `_do_enqueue`'s rule, not changed
  here; proposed for `plans/open-issues.md`.
- `q` does nothing today (it only set Pagination's search flag) and goes with the pages.
- The open issue "Five routes still pass `admin=`" asks this branch to drop `files.py`'s; commit 3
  does, with the test changes that entry lists.
- `phone-rows.css` has no Queue button, no needs-fix slot and no white top line (`.sr-name` is
  the singer's green): commit 3 adds them there.
- `.tabs.is-toggle` in `bulma-dark.css` paints the chosen tab teal, against L2/L3. The toggle
  takes the lyric-style buttons' chosen blue (`--button-selected-bg` in `custom.css`, which is
  `--dark-primary`) instead.
- The GATE N judge's `parse_label` showed parse's title on a one-line row; the ruling says the
  whole name. Commit 1 follows the ruling.
- The canvas draws the admin's button as a chevron and empty letters as a dim pill; S3 (a gear)
  and the 2026-11-18 ruling (L16) win, as recorded above.
- Measured on the VM: `parse()` takes about 130 µs a raw title, and the library has 17 names with
  no " - ", so the fallback costs about 2 ms a page. No cache.

### Canvas values

From the boards "Browse: admin, by artist", "Browse: admin, by song" and "Browse: guest, by
song" (read 2026-11-24), for what the decisions and rulings don't give. Use the theme token
where one exists; the hex is there to check against.

| Part | Value |
|---|---|
| Title | "Browse", 32 px regular, 20 px under it, no letter in it |
| Edit all songs (admin) | link at the card's top right (12 px down, 20 px in), 14 px, 14 px edit icon, 6 px gap |
| Toggle | on `--dark-bg-secondary`, 4 px padding and gap, 10 px corners, 12 px under it; two equal 40 px halves, 15 px; chosen `--dark-primary` `#375a7f`, white, bold; the other transparent, `--dark-text-light` |
| Strip | bleeds to the card's edges (`margin: 0 -20px; padding: 0 20px`), 6 px gap, 16 px under it; entries min 44 x 44, 6 px side padding, 22 px corners, 16 px bold; normal `--dark-bg-secondary`, white; chosen `--dark-primary` |
| Empty letter | L16, not the canvas's `#2b3131` pill: no fill, 1 px `--dark-border-faded`, `--dark-text-muted` `#8c9b9d` label, no opacity fade |
| Edge fade | 40 px, to transparent |
| List label | "B artists" / "B songs", 13 px, `--dark-text-sub` `#b5bfc0`, 8 px under it |
| Row | `.sr-row` as on Queue (the canvas draws a 12 px gap; keep `.sr-row`'s 10: one row style) |
| Top line | 17 px bold, line-height 1.25, `--dark-text-primary` |
| Bottom line | `.sr-sub` |
| One line | 16 px regular, line-height 1.3, `--dark-text-primary` |
| Queue, ready | 60 x 44, 6 px corners, `.button.is-success`'s green and label colour (as Queue's Add random songs), "Queue" 15 px bold |
| Queue, processing | the same button: "Queue" 14 px bold over "processing" 10 px, line-height 1.1 |
| Needs fix | 60 x 44, 1 px dashed `--dark-danger` `#e74c3c`, 6 px corners, no fill, "needs fix" 12 px `--dark-danger-text` `#f17a6b`, centred |
| Gear | `.sr-btn` (40 x 40, L15 grey) with `icon-cog`, as on Queue |

### Commits

Each commit: run the tests it names, pre-commit on the changed files, read `git diff --cached`
against this spec, end the message with the Co-Authored-By line. The full suite runs before
step 5. Reuse an existing msgid wherever one exists ("Queue", "processing", "Options", "Song
info" and "No songs in this list." do); new strings stay English until the next catalog regen.

**1. `feat(names): split_title reads a name the file-name split can't`**

Files: `pikaraoke/lib/song_manager.py`, `tests/unit/test_song_manager.py`.

Behaviour: `split_title(title)` splits at the first " - " as today. When that gives no usable
split, it takes `parse(title)` (`genius_query.py`, no channel) and returns `(parsed.artist,
parsed.title)` when both are non-empty; otherwise `("", title)`, the name as passed, not parse's
trimmed title. A name the split handles is never re-read, even when it is backwards ("Hello -
Adele"). Film is never used. The docstring says why the parser comes second (GATE N: the
hand-made names split; the downloads' raw titles often don't) and that Queue, Now Playing and
Browse share the rule. `genius_query` imports only `genius` and `metadata_parser` from the app,
so there is no cycle.

Tests, in `TestSplitTitle` (the six existing tests stay and pass):

- `"Bohemian Rhapsody | Queen"` gives `("Queen", "Bohemian Rhapsody")`
- `"Adele 'Hello'"` gives `("Adele", "Hello")`
- `"Twins《下一站天后》"` gives `("Twins", "下一站天后")`
- `"Hello - Adele"` gives `("Hello", "Adele")`
- `"Defying Gravity (From Wicked)"` gives `("", "Defying Gravity (From Wicked)")`: parse finds the
  song and the film, no artist

These were checked against `dev`'s `parse()` on 2026-11-24. Also run `test_queue_routes.py` and
`test_karaoke_utils.py` (the Queue and Now Playing callers): unchanged.

Stop point: committed.

**2. `refactor(queue_hold): one rule for what a manual Add does with a library song`**

Files: `pikaraoke/lib/queue_hold.py`, `pikaraoke/routes/queue.py`, `tests/unit/test_queue_hold.py`,
`tests/unit/test_queue_routes.py`.

Behaviour, unchanged for the queue: `QueueHold.add_outcome(song_path, state) -> str` returns
`"refused"` (failed, or pending with nothing to finish it), `"pick"` or `"processing"` (pending:
the Add takes a held slot), or `"ready"` (any other state, `None` included, busy or not). Body:
failed gives refused; anything not pending gives ready; else `self.waiting_for(song_path) or
"refused"`. `_do_enqueue` calls it once: refused gives the same 409 (its message still names the
state); otherwise `waiting = None if outcome == "ready" else outcome`, and the rest is as today.
Browse (commit 3) is its second caller.

Tests: in `test_queue_hold.py`, one parametrized test over its existing fixtures (real
`EventSystem`, `PreferenceManager` and `QueueManager`; `library_tools` a mock): failed, idle or
busy, is refused; pending with a pick is pick; pending and busy is processing; pending and idle
is refused; ready, skipped and `None`, idle or busy, are ready. In `test_queue_routes.py`
`TestEnqueuePipelineGate`, the three tests that mock `queue_hold.waiting_for` set
`queue_hold.add_outcome.return_value` instead (`"refused"`, the `waiting` parameter,
`"processing"`) and check it was called with `("/songs/test.mp4", "pending")`; the fourth (a real
`QueueHold`) stays as it is.

Stop point: committed.

**3. `feat(ui): Browse page for phones: one letter at a time, by artist or by song`**

Files: `pikaraoke/routes/files.py`, `pikaraoke/templates/files.html`,
`pikaraoke/static/phone-rows.css`, `tests/unit/test_files_routes.py`.

Route, `browse()`, split into small module helpers so no function passes about 50 lines:

- Mode: `request.args["by"]`, else the `browse_by` cookie; anything but `artist` or `song` gives
  `artist` (10, 11).
- Rows, one per library song (`k.song_manager.songs`): `name = filename_from_path(path)`,
  `artist, song = split_title(name)`. By artist the top line is `artist` and the bottom `song`;
  by song the reverse. With no artist the row is one line, `song` (the whole name), the same in
  both modes (decision 3).
- State: `"ready"`, unless the path is in `get_paths_by_pipeline_state(["failed"])` or
  `get_paths_by_pipeline_state(["pending"])`. Those go through
  `k.queue_hold.add_outcome(path, state)`: `"refused"` gives `"fix"`, `"pick"` and
  `"processing"` give `"processing"`. Two queries a page, not one per song. A guest's rows drop
  every `"fix"` row before anything else (decision 8), so a letter holding only those is empty
  for a guest.
- Strip: `#`, then a to z, each marked by whether any row's top line files under it
  (`browse_letter(top)`).
- Letter: `request.args["letter"]`, else the `browse_letter` cookie; `numeric` stands for `#`.
  Missing, unknown, or empty for this viewer gives the first entry that has rows; `None` when
  there are no rows at all.
- Listed rows: the ones under the letter, sorted by `(browse_key(top), browse_key(bottom), path)`.
- The response sets `browse_by` and `browse_letter` (the URL form, `numeric` for `#`) to what it
  shows, with `max_age` ten years and path `/` like `base.html`'s cookies; no letter cookie when
  there is no letter. A cookie is read like an argument: only a known value is used.
- Gone: `flask_paginate`, `sort`, `page`, `q`, the `k.browse_results_per_page` read (the setting
  goes in commit 4), the tracker and active-job reads, `filename_from_path` in the template,
  `admin=` (the context processor supplies it), and any import left unused.
- Template context: `by`, `letter` (display form), the strip (entry, URL value, has rows), the
  rows (path, top, bottom, state), and `current_url` = this mode and letter's `/browse` URL (the
  Edit song referrer, so a rename comes back here).

Template, `files.html`, rebuilt with no table:

- `{% block styles %}` links `phone-rows.css` and holds a `<style>` with only what Browse draws
  (toggle, strip, fades, label), at the canvas values above.
- Title "Browse". For an admin, Edit all songs at the card's top right
  (`batch_song_renamer.browse`; a full page load, as today).
- Toggle: `role="group"`, two links, to `?by=artist&letter=<current>` and
  `?by=song&letter=<current>`; the chosen one has `aria-current="true"`.
- Strip: a `<nav aria-label="Songs by letter">` holding 27 entries. A letter with rows is a link
  to `?by=<mode>&letter=<value>`, the chosen one `aria-current="page"`. An empty one is a
  `<span aria-disabled="true">`, so it can't be tapped (decision 1, 14). The toggle
  and the strip sit in one `.bp-pin` block, `position: sticky; top: 0` (12) with 12 px of top
  padding (a matching negative top margin keeps the unpinned layout) on the card's colour
  (`--dark-bg-tertiary`), above the rows and below Bulma's modals; if the nav bar is made sticky
  later (open issue), `top` becomes its height. Its inner row scrolls sideways (`overflow-x: auto`, scrollbar hidden).
- Fades (14): a `mask-image` gradient on the scrolling row (with `-webkit-mask-image`), 40 px at
  each edge that has letters past it, from two classes a scroll listener sets (and once on load).
  A mask rather than an overlay, so it fades over the pinned background with no colour to match.
- On load the chosen letter is moved to the middle of the strip by setting the row's
  `scrollLeft`, not `scrollIntoView`, which would scroll the page too.
- Label over the list: `"%(letter)s artists"` or `"%(letter)s songs"`, the letter in capitals.
- Each row: `.sr-row` holding the slot, `.sr-main`, then the admin's gear. Two lines are
  `.sr-title` (new) over `.sr-sub`; one line is `.sr-one` (new). Titles wrap between words
  (decision 9): `.sr-main`'s `overflow-wrap: anywhere` breaks inside a word only when the word
  can't fit a line on its own; nothing sets `break-all`.
- Slot, ready: `<a class="button is-success sr-slot sr-queue add-song-link"
  href="<enqueue>?song=...&user=">Queue</a>`. Processing: the same, "Queue" over `.sr-word`
  "processing" (L8: green; S2: a button). Needs fix, admins only: `<span class="sr-slot
  is-fix">needs fix</span>`. Keep `add-song-link`: `spa-navigation.js` excludes it from SPA
  navigation, and the page's handler sends it.
- Gear, admins only: `<button class="button sr-btn sr-gear" aria-label="Options"><i class="icon
  icon-cog"></i></button>`, opening one modal modelled on Queue's `#song-options-modal`. Its
  title is the row's text; its entries are Edit song (`files.edit_file?song=...&referrer=
  <current_url>`, out of SPA navigation by its path) and Song info (`song_info.song_info?song=...`,
  `no-spa` as today). Guests get no button and no gap.
- No rows: "No songs in this list.", and every letter disabled.
- Script: one `.browse` event namespace, with `$(document).off('click.browse')` before binding,
  because SPA navigation re-runs the inline script on every visit (Queue's pattern). The Queue
  tap is today's: a GET with `Cookies.get("user")`, a toast from the reply, the 409's `error` on
  a refusal. The old A-Z bar's scroll code goes.

`phone-rows.css`, each addition named in the header's list of row parts:

- `.sr-title`: 17 px bold, line-height 1.25, `--dark-text-primary`.
- `.sr-one`: 16 px, line-height 1.3, `--dark-text-primary`.
- `.sr-queue`: the green button in the 60 x 44 slot box. It drops `.sr-slot`'s fill and border so
  `.button.is-success` shows; 15 px bold label, `.sr-word` under it when processing.
- `.sr-slot.is-fix`: 1 px dashed `--dark-danger`, `--dark-danger-text`, no fill, 12 px (a state,
  so dashed: S2).

Nothing restates a colour that `bulma-dark.css` defines.

Tests, `test_files_routes.py`, rewritten for the new page. The test app registers `admin_bp`, and
each test patches `pikaraoke.routes.admin.is_admin` to the same value as
`pikaraoke.routes.files.is_admin` (the open issue's note). The fake karaoke is a `MagicMock` with
real parts: `song_manager.songs` a list, the real `filename_from_path`,
`get_paths_by_pipeline_state` answered from a `{path: state}` dict, and a real `QueueHold` over a
real `QueueManager` (real `EventSystem`, a `PreferenceManager` on `tmp_path`), with a mock
`library_tools` whose `is_busy` and `is_waiting_for_pick` read two sets. Check the rendered rows
and links, not CSS values. Cases:

1. By artist (the default): the top line is the artist and the bottom the song, in artist then
   song order; the label reads "B artists".
2. By song: "Queen - Bohemian Rhapsody" is under B, not Q, as "Bohemian Rhapsody" over "Queen";
   the label reads "B songs".
3. A name with no split is one line, under its first letter in both modes.
4. "Bad Romance | Lady Gaga" splits through the parser (commit 1 reaches Browse).
5. Leading symbols: "'Defying Gravity'" files under D, "Britney Spears - ...Baby One More Time"
   by song under B (the existing test's intent, kept).
6. `#` (`letter=numeric`): digits and other scripts, and the label shows "#" (kept).
7. Strip: a letter with rows is a link, an empty one a `span[aria-disabled="true"]`, the chosen
   one has `aria-current`.
8. No letter gives the first with rows; `letter=q` with no Q songs gives the first with rows;
   `by=bogus` gives by artist.
9. Cookies: `/browse?by=song&letter=c` sets both; a plain `/browse` next (the test client keeps
   cookies) shows by song at C. A remembered letter that has since emptied falls back.
10. States, admin: ready is a "Queue" link with no "processing"; pending and busy, and pending
    with a pick, are "Queue" over "processing"; failed, and pending with nothing, are "needs
    fix" with no Queue link; ready and busy is a plain "Queue".
11. Guest: no "needs fix" row; a letter whose only song is failed is disabled for the guest and a
    link for the admin; no gear, no menu, no Edit all songs, no Song info.
12. Admin: one gear per row; the menu holds the Edit song and Song info links.
13. An empty library: 200, "No songs in this list.", all 27 entries disabled.

Stop point: committed. Its Results row says the self-review does not stand alone (a multi-file
page rewrite), so it rides to the `/code-review` after Phase 1.

**4. `refactor(prefs): drop the Browse per-page setting`**

Files: `pikaraoke/lib/preference_manager.py`, `pikaraoke/karaoke.py`, `pikaraoke/routes/info.py`,
`pikaraoke/templates/info.html`, `tests/unit/test_preference_manager.py`,
`tests/unit/test_info_routes.py`.

Behaviour: `browse_results_per_page` goes from `DEFAULTS`, from `Karaoke.__init__` (the
parameter and its docstring line), from the Info render and from its field. A `config.ini` that
still has the line is left alone: `apply_all` reads only `DEFAULTS` keys, so the line does
nothing.

Tests: `test_preference_manager.py`'s clear test uses `limit_user_songs_by` instead (`"5"`,
default 0); the key list and the integer-type check drop it. `test_info_routes.py` drops
`k.browse_results_per_page`. `git grep browse_results_per_page -- ':!plans'` is empty.

Stop point: committed.

**5. Results (plan-only commit).** The full suite, then one Results log row per commit 1-4 (its
hash, what was built, anything chosen while building that this spec doesn't give, the suite
count, pre-commit), then the ui-check run below and its own row. Phase 1 stops there.

### ui-check on the VM

After commit 4, Sonnet drives the page with the `ui-check` skill (`.claude/skills/ui-check/` in the
main checkout) and saves the artifacts. The executor stops with paths and raw results, no
verdicts; Opus reads them, then Ken.

Setup:

- Port **5647**. `lsof -ti:5647 -sTCP:LISTEN` is empty before the first launch. Before any
  relaunch or kill, confirm the listener is this run's (`/proc/<pid>/environ` has this worktree
  as `PYTHONPATH`). Relaunch after any commit that changes a template or a route.
- Launch from this worktree with long jobs, so the processing row stays processing:
  `FAKE_JOB_S=900 .claude/skills/ui-check/launch.sh 5647 <scratchpad> /home/ken/pikaraoke/.claude/worktrees/browse_phone`
  (the script path is in the main checkout).
- Library: fill `<scratchpad>/lib5647` before the first launch (`launch.sh` copies its four videos
  only into an empty folder). Copy the shared library's smallest `.mp4` in once, then hard-link it
  under each name below (each `.mp4`, ID 11 characters):

| File name, before `.mp4` | State to set | For |
|---|---|---|
| `Adele - Hello---brwse000001` | ready | a ready row; queue it as a guest |
| `Backstreet Boys - I Want It That Way---brwse000002` | ready | |
| `Bee Gees - Stayin' Alive---brwse000003` | ready | an apostrophe in links |
| `Billie Eilish - Happier Than Ever---brwse000004` | pending, then a job | processing |
| `Bill Withers - Lean on Me---brwse000005` | failed | needs fix |
| `Britney Spears - ...Baby One More Time---brwse000006` | pending, no job | needs fix; by song under B |
| `Bad Romance \| Lady Gaga---brwse000007` | ready | parser split: L by artist, B by song |
| `Bohemian Rhapsody Queen Official Lyrics---brwse000008` | ready | one line, under B in both modes |
| `Queen - Bohemian Rhapsody---brwse000009` | ready | Q by artist, B by song |
| `Bon Jovi - Livin' On A Prayer---brwse000010` | ready | |
| `Bonnie Tyler - Total Eclipse of the Heart---brwse000011` | ready | |
| `Blondie - Heart of Glass---brwse000012` | ready | |
| `Bruno Mars - Just the Way You Are---brwse000013` | ready | |
| `Bryan Adams - Summer of '69---brwse000014` | ready | enough B rows to scroll |
| `Meat Loaf - I'd Do Anything for Love (But I Won't Do That)---brwse000015` | ready | wrapping (I by song) |
| `99 Luftballons---brwse000016` | ready | `#` |
| `周杰倫 Jay Chou【晴天】---brwse000017` | ready | `#`, parser split |
| `Xavier Rudd - Follow the Sun---brwse000018` | failed | X empty for a guest only |
| `Zedd - Clarity---brwse000019` | ready | Z by artist, C by song |

The `\|` in row 7 is the table's escape: the file name holds a plain `|`.

- States: launch once so the scan records every song (all `skipped`, which is ready), stop it,
  then set `pipeline_state` in `<scratchpad>/home5647/.pikaraoke/pikaraoke.db` (`UPDATE songs SET
  pipeline_state = ? WHERE file_path = ?`) for the four rows above, and add `admin_password =
  secret` under `[USERPREFERENCES]` in `<scratchpad>/home5647/config.ini`. Relaunch, then
  `uihelpers.retry(base, <Billie Eilish's path>)` starts its job.
- People, each in their own browser context: a guest with no admin cookie, and an admin with
  the `admin=secret` cookie. Each joins through `POST /singer` (`name` new per context,
  `semitones` 0, `vocal_volume` 1, `sub_mode` karaoke) and sets the `user` and `singer_token`
  cookies from the reply; `new_page`'s `user` cookie alone leaves `#singer-modal` over every tap.
- Playwright 1.64.1 headless Chromium (the skill's venv), touch, DPR 2, at 390 x 844 and
  360 x 740. Change page with `spa()` or a tapped link, so the SPA re-run path is the one tested.

Checks, recorded per width and person in `results.json` (each with the values read):

- First visit, guest: By artist is chosen, the letter is `#`, and its rows are "99 Luftballons"
  (one line) and "周杰倫 Jay Chou" over "晴天".
- Toggle and letter taps are SPA navigations (a `window` marker survives), the address updates,
  and the chosen letter sits inside the strip's visible box after each tap.
- Strip: 27 entries. For the guest X is a disabled span; for the admin it is a link. A disabled
  entry's computed background is transparent, its border `rgba(94, 109, 111, 0.5)`, its colour
  `rgb(140, 155, 157)`, its opacity 1.
- The strip scrolls sideways (`scrollWidth` > `clientWidth`), the page does not
  (`document.documentElement.scrollWidth` equals `innerWidth`).
- Fades: at the start only the right edge fades, scrolled to the end only the left, in between
  both (the classes and the computed `mask-image`).
- Pinned: on B by artist, after the window scrolls 400 px the strip's top is at 0, and the point
  at the strip's middle belongs to the strip (rows pass under it).
- B by artist, guest: rows in order Backstreet Boys, Bee Gees, Billie Eilish, Blondie, "Bohemian
  Rhapsody Queen Official" (tidied, one line), Bon Jovi, Bonnie Tyler, Bruno Mars, Bryan Adams;
  no Bill Withers, no Britney Spears; Billie Eilish is "Queue" over "processing", green.
- B by song, guest: "Bad Romance" over "Lady Gaga" and "Bohemian Rhapsody" over "Queen" are
  there, "...Baby One More Time" is not.
- Queue taps, guest: Adele's shows a success toast and `/get_queue` holds it under the guest's
  name; Billie Eilish's gives a held item (`waiting` "processing").
- Remembered: from B by song, the nav bar to Queue and back to Browse shows B by song.
- Guest: no gear, no menu, no Edit all songs, no Song info anywhere.
- Wrapping, 360 px, I by song: the Meat Loaf row is taller than 60 px, its text breaks only at
  spaces, and its computed `word-break` is not `break-all`.
- Admin, B by artist: Bill Withers and Britney Spears are dashed red "needs fix" boxes with no
  link in them; every row has a gear; Edit all songs is at the top right; X is a link and
  Xavier Rudd is needs fix.
- Admin menu: a gear opens the menu titled with the row's text; Edit song's link is
  `/files/edit?song=...&referrer=` with this mode and letter; Song info has `no-spa`; tapping
  Edit song loads the edit page.
- No page errors for either person.

Screenshots per width: guest `#` by artist, guest B by artist, guest B by song, guest B scrolled
(pinned strip), strip scrolled to the end (left fade), admin B by artist, admin B by song, admin
menu open. Artifacts in `.claude/ui-check/browse_phone/` in this worktree (untracked): the check
script, the screenshots and `results.json`.

### After Phase 1

- `/code-review` over commits 1-4 (Ken runs it), then the fixes.
- Ken's checks on his phone: the strip's swipe and fades, the pinned strip, landing back where he
  left, a guest's Queue tap, the admin's gear menu.
- Landing: commits 1-4 and their fixes are copied onto `dev` one by one (CLAUDE.md, Branches);
  this plan stays on the branch.

## Phase 2: stored names

Dropped at GATE N.

## Not in this plan

- The Queue page. Its mockups show today's page; changes get their own decisions.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
| 2026-11-18 | 0 | `9cd61fce` | Executed (Sonnet): `probe.py`, `set_g.md/.json`, `set_l.md/.json` in `plans/browse-phone-phase0/`. Set L is 205 of 249 files; the 44 split film clips have no raw title. Judged (Opus, read-only over the JSON, `probe.py` not rerun): Set G marks in `set_g.md`'s judge column; tallies, Set L wrong rows, and (b) on the current file names with no channel (not in Phase 0) in `judge.md`, reproduced by `judge.py`. |
| 2026-11-18 | GATE N | `9cd61fce` | Ken: (a), with (b) for a name (a) can't split, taken only when the parse finds both artist and song. Phase 2 dropped. |
| 2026-11-24 | 1 | (spec) | Phase 1 spec (Opus), checked against `dev` `d3f3bf66`: rulings 10-14 (Ken, this date), commits 1-4 for Sonnet, ui-check on port 5647. No code. |
| 2026-11-24 | 1.1 | `729ad280` | Executed (Sonnet): `split_title` falls to `parse()` when the " - " split gives nothing, taking it only when it finds both artist and song, else `("", title)`. The spec's five cases are tests (the three parser cases as one parametrized test). `song_manager` now imports `genius_query`, which imports `genius`, which imports `lyricsgenius` at module level, so every importer of `song_manager` loads it. `test_song_manager.py` + `test_queue_routes.py` + `test_karaoke_utils.py`: 144 passed. Pre-commit clean. Self-review covers it (one function, one read-through). |
| 2026-11-24 | 1.2 | `813d2ec6` | Executed (Sonnet): `QueueHold.add_outcome(song_path, state)` and `_do_enqueue` calling it once; the 409 text is unchanged. Not in the spec: seven route tests had to set `queue_hold.add_outcome.return_value`, not three, because every test with a `MagicMock` `queue_hold` now gets a mock back from it (the other four: failed never held, failed 409, ready, skipped; the first now sets `"refused"`, and failed-beats-busy is a row of the `add_outcome` test instead). `add_outcome` has one parametrized test of 11 rows. `test_queue_hold.py` + `test_queue_routes.py`: 82 passed. Pre-commit clean. Self-review covers it (a rule moved, no new behaviour). |
| 2026-11-24 | 1.3 | `c12ea382` | Executed (Sonnet): `browse()` split into `_song_states`, `_browse_rows`, `_chosen_letter` (module helpers in `routes/files.py`); `files.html` rebuilt with no table; `phone-rows.css` gains `.sr-title`, `.sr-one`, `.sr-queue`, `.sr-queue.is-processing`, `.sr-slot.is-fix`; `test_files_routes.py` rewritten (38 tests, 13 of them the spec's cases; the edit, rename and delete tests are unchanged). Chosen while building, not in the spec: (1) `.sr-slot`'s fill, border and colour moved to `.sr-slot:where(:not(.button))`, so the Queue slot (a `.button.is-success`) keeps Bulma's own; `.sr-queue` then sets only padding 0 and the label size. (2) The processing slot also carries `is-processing`, for its 14 px label. (3) The gear menu is built by the page script from `data-song` and `data-title` on the gear, not per row; its title is the row's top line and bottom line in the row's own order joined by " · " (Queue's own menu says "song · artist"). (4) The page style sets `.box { position: relative }` for Edit all songs. (5) `letter` goes to the template lower case with `letter_param` beside it; the template upper-cases it for the label. (6) Only known lower-case values are read from `?letter=` and the cookie, so `?letter=B` falls back to the first letter with songs. (7) `phone-rows.css`'s header has no list of row parts to name additions in; each addition has its own comment. (8) New msgids, English until the next regen: "needs fix", "%(letter)s artists", "%(letter)s songs", "By artist", "By song", "Songs by letter", "Edit song", "Could not add song to the queue." (the old script's plain fallback, now `_()`); reused: "Queue", "processing", "Options", "Song info", "No songs in this list.", "Edit all songs". (9) Tests read the page with a small `html.parser` class (bs4 is installed in `pik` but is not a declared dependency); the app fixture registers `admin_bp` and sets `ADMIN_PASSWORD` to None; each Browse test sets `files.is_admin` and `admin.is_admin` to the same value through one fixture. `flask_paginate` stays (`batch_song_renamer.py`). Pre-commit clean. The self-review does not stand alone (a multi-file page rewrite): it rides to the `/code-review` after Phase 1. |
| 2026-11-24 | 1.4 | `d86cd2d2` | Executed (Sonnet): `browse_results_per_page` out of `DEFAULTS`, `Karaoke.__init__` (parameter and docstring line), the Info render and its field; the clear test uses `limit_user_songs_by` (5, default 0). `git grep browse_results_per_page -- ':!plans'` is empty. `test_preference_manager.py` + `test_info_routes.py`: 40 passed. Pre-commit clean. Self-review: a pure delete, so skipped. Full suite on `d86cd2d2`: 4355 passed (82 s). |
| 2026-11-24 | 1 | ui-check | Executed (Sonnet) on `d86cd2d2`, port 5647, Playwright 1.64.1 headless Chromium, touch, DPR 2, 390 x 844 and 360 x 740, a guest and an admin in separate contexts, joined through `POST /singer`. Artifacts (untracked, in this worktree): `.claude/ui-check/browse_phone/check.py`, `results.json` (values read, with the spec's expectation beside each; no pass/fail field), `shots/` (17 PNGs: the eight named boards at each width, plus one extra). App state: library `lib5647` (19 hard links of one 2.8 MB video), `home5647`, `admin_password = secret`, in the session scratchpad `/tmp/claude-1000/-home-ken-pikaraoke/523a5863-cd5a-4aec-bc8c-73f13dba9d23/scratchpad/`; the app is stopped. Differences from the spec's setup: (a) `uihelpers.retry` gets a 403 once `admin_password` is set (the route is admin-only), so Billie Eilish's job was started with a POST carrying `Cookie: admin=secret`, again after the relaunch (the fake job ends with the process and the song falls back to pending with no job). (b) A first run on the uncommitted working tree before commit 3 was a smoke run and is discarded; `results.json` is the run on `d86cd2d2` after a relaunch. Raw readings worth the judge's eye, all in `results.json`: **pinned:** at the two spec viewports the page scrolls only 169 px (390 x 844) and 148 px (360 x 740), because the guest's B list has 9 rows, so `scrollY` stopped there with the strip's top at 17 and 38, not 0 (the point at the strip's middle still belongs to the strip); the 400 px the check names is not reachable. An added run at 390 x 400 (`pinned_short_viewport_addition`, `shots/390-guest-B-scrolled-short-400.png`) scrolled 400 px: strip top 0, point at its middle belongs to the strip, a row is under it. **Title gap:** the gap from the title to the toggle is 24 px on a full load and 8 px after a tap from a full-loaded Home, whose own `header.title:not(:last-child) { margin-bottom: 0.5rem }` stays in the page because SPA navigation removes only the styles it injected (Queue reads the same); the canvas says 20 px (`title_gap`). Other canvas values read for both people (`canvas_values_*`). Also read: all three SPA taps kept the `window` marker, updated the address and left the chosen letter inside the strip; the disabled letter's computed values are in `disabled_letter_style`; the fades' classes and `mask-image` at start, middle and end are in `fades`; the guest's two Queue taps and `/get_queue` after each are in `queue_taps`; the 360 px wrap row is 71 px tall in `wrap_I_by_song`; the menu closes by its X and by its background, and Edit song loads `/files/edit` (`menu`); both people's `page_errors` are empty lists. "Bohemian Rhapsody Queen Official" (a one-line row) wraps onto two text lines at both widths. |
| 2026-11-24 | 1 | judge | Read (Opus, read-only) on `b6f56f2e`: `results.json`, the shots `390-guest-B-scrolled-short-400.png`, `390-guest-B-by-artist.png`, `360-guest-B-scrolled.png`, and the code behind the two flagged readings (`files.html`'s `.bp-strip`, `base.html`'s header, `home.html`'s `header.title` rule, `spa-navigation.js` `injectInlineStyles`). **Pinned (ruling 12): passes, no change.** The spec's 400 px was not reachable with nine B rows at 844 and 740 px tall (max scroll 169 and 148; strip top 17 and 38, not yet at its pin point); the 390 x 400 run is the reading: strip top 0 at `scrollY` 400 of 439, the point at its middle is a `.bp-letter`, a row under it. Pinned, the letters sit flush with the screen's top edge (`.bp-strip` has no top padding): for Ken's phone check. A navbar kept on screen must offset `.bp-strip`'s `top: 0`; noted on the open issue "Keep the top blue nav bar on screen while scrolling" (`dev` `6a31e33f`). **Title gap: no change on this branch.** 24 px on a full load is Bulma's `.title:not(:last-child)` margin, the same on Queue; under one look Browse follows Queue, not the board's 20 px, and a change would be `base.html`'s, for every page. 8 px after a tap from a full-loaded Home is Home's own rule left in the page, because `injectInlineStyles` removes only `data-spa-injected` styles: app-wide, logged as "The first page's own styles stay on every page tapped to after it" (`dev` `6a31e33f`, "Web pages"). **The rest** reads as the spec expects at both widths for both people: first visit, 27 entries, the disabled X and its computed style, sideways scroll with no page overflow, fades at start, middle and end, row order and hidden needs-fix rows for the guest, the processing button, both Queue taps and `/get_queue`, remembered mode and letter, wrapping at spaces (71 px, `word-break: normal`), the admin's needs-fix boxes, gears, X link and menu, no page errors. Correction to the ui-check row: the one-line Bohemian Rhapsody row is one line at 390 (`390-guest-B-by-artist.png`) and wraps at a space only at 360 (`360-guest-B-scrolled.png`). Next: Ken's `/code-review` of `40560f98..d86cd2d2`. |
| 2026-11-24 | 1 review | `786cacf6`..`539c63f3` | `/code-review 40560f98..d86cd2d2` (Ken ran it): 9 findings; fixes executed by Opus. `786cacf6` gear: Queue's and Browse's row handlers scoped to `#queue-page` / `#browse-list` (finding 1); ui-check ports 5719 (fixed) and 5720 (`1dd14f9b` export), `gear_check.py` in the session scratchpad, 3 trials each: Queue then Browse gear and Browse then Queue gear; pre-fix 3/3 Browse menu not opened, console `Cannot read properties of undefined (reading 'artist')`, Queue menu opened; fixed 3/3 both menus opened, no console errors. `acab47f6` names: `_misread` rejects a parse whose split came from a colon (swap `dash`, no `DASH` match) or that kept a repeated word fewer times than the name has it (findings 2, 3); over the 317 Phase 0 titles (set L raw + names, set G raw) one split changes, G `Beat Saber: I Just Can't Wait To Be King (Lion King)` -> one line; pipe-order swaps kept (GATE N). `36bce7ba` letter lowercased, Browse tests share the `library_tools` mock (findings 6, 9). `6bd89f7c` `get_pipeline_states` deleted (finding 8). `83f66dd1` duplicate 409 queue test deleted (finding 9). `539c63f3` `admin=` dropped from the Info and Queue renders (open issue). Not fixed: finding 4 (failed song during retry, plan's accepted rule) and 5 (referrer, upstream), both logged in `plans/open-issues.md` (`dev` `c55805fa`); finding 7 (parser cost) dropped, measured and ruled no cache above. Full suite on `539c63f3`'s tree: 4360 passed. |
| 2026-11-24 | 1 | Ken's phone check | `51d0c1cc`: Ken's checks looked good except the pinning. Ruling 12 flipped: the toggle pins with the strip, and the block sits 12 px below the top edge (card-coloured padding, so rows do not show above it). `.bp-strip`'s sticky rule moved to a new .bp-pin wrapper in `files.html`; unpinned layout unchanged (toggle top 142 px on a full load, as before); pinned at 390 x 844 and 360 x 740: block top 0, toggle 12-60, strip 72-116, hit tests on the gap and the strip belong to the block, no page errors. `tests/unit/test_files_routes.py` 39 passed. Ten extra B artists added to the test library for the check (test data only). |
