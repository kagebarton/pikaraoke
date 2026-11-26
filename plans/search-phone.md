# Search Part 3: the phone restyle, and the duplicate-download fixes

Model: Claude Sonnet 5.5 (spec by Claude Opus 5.5, 2026-11-24)

Branch `search_phone` off `dev` at `d2ed9a3b`, worktree `.claude/worktrees/search_phone`
(inside the main checkout, gitignored via `.claude/`). Work and run everything from the worktree.
If `dev` has moved, rebase onto it before commit 1.

This is Part 3 of the search work. Parts 1, 2 and 2b were built on branch
`search_official_captions` (plan `plans/search-official-captions.md` there) and landed on `dev`
2026-11-24. That branch retires as tag `archive/search_official_captions`; read its plan with
`git show archive/search_official_captions:plans/search-official-captions.md` (or the branch
name, until it is retired) only if a ruling's history matters. Every ruling this spec relies on
is copied below.

## Goal

The Search page and its download dialog still wear Bulma's defaults (an amber Search button,
white inputs, pale-blue tags, 4 px corners). Every other phone page now has one look: the
`bulma-dark.css` greys, a `#343c3d` card, 17/13 px text, 44 px buttons with 6 px corners. This
Part gives Search that look, as the canvas draws it: badges on the thumbnail for In library and
Official, a dark In library row under a card whose song you own under another upload, the
dialog on a card. It also closes three open issues about getting a song twice, and makes the
channel-name code single-source before any of it.

## Order

1. **Phase 1: the channel cleaners** (commit 1). No behaviour change, first and on its own, so
   its "nothing moved" check is not muddied by anything else.
2. **Phase 2: duplicates and Queue's answer** (commits 2-4). Behaviour; the look follows.
3. **Phase 3: the look** (commits 5-7).
4. **Phase 4: the catalogs** (commit 8), once every new string is in.
5. **Phase 5: Ken's phone checks.**

Stop after each phase, with its Results rows committed, so Ken can `/compact`. A Review-due
checkpoint follows Phase 2 and Phase 3 (multi-file script and markup changes).

## Rulings

### Decisions (Ken, 2026-11-24, for this spec)

- **K1. The canvas drawing choices stand as drawn** (below, "Canvas drawing choices"), with
  today's wording kept: the results label still reads "Search results for '…'" and Advanced
  still reads "Direct download YouTube url:", so their translations still apply. The canvas's
  shorter "Results for '…'" and "Direct download YouTube URL" are not taken.
- **K2. The dialog's content sits on the `#343c3d` card**, like every page and Queue's confirm
  dialog. Not chosen: content on the dark backdrop, as the dialog's mockup drew it.
- **K3. The dialog's close X goes inside the card**, at its top right beside the title (Ken
  asked, once the card was drawn). A tap on the backdrop still closes it.
- **K4. The duplicate-download guard and a clean restore** (open issues "A search card you
  already own can be downloaded again", option 3, and "A restored search page can show a stuck
  card"). A video the library already has is queued from the library, never downloaded again;
  a returning visit puts back the cards exactly as the server sent them, so no live state (a
  button mid-flash) is ever saved. Not chosen: also redrawing restored cards through a new
  route so their In library state is current (costs a route and its tests); the guard alone,
  or neither.
- **K5. The dialog's Queue waits for the download's answer** before it says what happened
  (open issue "The dialog's Queue says Queued before the download is accepted"). Ken asked for
  a mockup first and approved it: canvas board "Dialog after Part 3: Queue's answers".
- **K6. Official's check emblem is always Info blue `#3298dc`** (amends L19, which gave it two
  fills). Ken: the grey `#8c9b9d` beside In library could read as "not official", since that
  grey is the disabled label's (L16). Blue beside the green folder is two small coloured icons;
  In library stays first.
- **K7. Part 3 runs on a fresh branch off `dev`** (this one), not on `search_official_captions`
  (the open "Not ruled" item in `plans/open-issues.md` "Landing order").
- **K8. The channel cleaners are unified first, with no behaviour change** (Ken's brief): the
  ranking on `tests/unit/data/youtube_search` must not move, and the Genius replay of
  `tests/unit/data/genius_search` must pass unchanged.

### Copied from `plans/search-official-captions.md` Part 3 (Ken, 2026-11-18 to 2026-11-23)

L12 and L13 are also items 12 and 13 of `plans/open-issues.md` on `dev`, "Phone pages: one look",
with items 1, 4, 15 and 16.

- **L12. The card restyle is its own pass**, after `queue_phone` lands its shared stylesheet
  (row, slot and button styles). It takes the download dialog's controls with it: the Search
  button, the list and the input, and no card behind the content (`download_modal_speed`'s
  dialog still has the Search page's Bulma look). Order: `queue_phone` lands, then this pass,
  which carries L13. Partly reverses decision 8's light tint. What it restyles, from the
  review: the amber (`is-warning`) Search button, white inputs, 4 px corners, 40 px buttons;
  the Official tag and the In library note in `is-info is-light`, the app's only light
  surfaces; a third blue `#6cb8ea` for the YouTube link and a grey `#a3b0b2` for the channel;
  titles 16 px regular, not 17 px bold.
- **L13. The In library note becomes a dark row** (option A): `#282f2f`, 6 px corners, the
  Browse folder icon, "In library" over the file name, a full-size green Queue. On a card with
  a library match, the card's own button reads "Download…" in neutral grey (L4, the fill
  `#434d4e` from L15), to steer guests to the copy they have; cards without a match keep the
  green "Queue…" (L11). The dialog's button still reads "Queue" when opened from "Download…"
  (`download_modal_speed`, L7).

L17-L20, word for word:

- **In-library songs need a more obvious highlight** (Ken, 2026-11-19, after the Part 2
  phone checks). Two cases, and L13 covers only the second: (a) a card that is itself in the
  library (`row.existing_path`) is first on the page and its button is the green Queue, but
  nothing else sets it apart from a `Queue…` card, so with "backstreet boys drowning" the
  owned official video reads as just another result; (b) the "In library" note, which L13
  already turns into a dark row with the folder icon. Candidates for (a) were an In library
  tag beside the Official tag, the same dark row, or a tinted card.
  - **L17. Ruled (Ken, 2026-11-23):** (a) gets an "In library" badge on the thumbnail's
    top-left corner: `#282f2f` chip (fill superseded by L20), 6 px corners, padding 6/12/6/10 px, a green `#2ecc71`
    18 px folder icon (the Browse icon), 15 px bold white text. Its own button stays the
    green Queue, and the lift (decision 7) keeps it first. (b) keeps L13's dark row; the two
    share the dark fill and the folder icon, not the shape. The aim is a nudge seen while
    scrolling, not text to read: no "ready now" line. Not chosen: the dark row on (a) too
    (mocked as option 1), a tinted card (green tint already means "your own rows" on Queue),
    and a pinned "Already in your library" section (decision 8 removed that box). Canvas:
    the "Search: results" artboard, first card. Lands in the Part 3 restyle with L13.
- **L18. The card's "YouTube ↗" link goes** (Ken, 2026-11-23). Upstream's, never ruled here:
  the thumbnail already opens the dialog's preview, and on a phone the link leaves the app
  for the YouTube app. Canvas: both Search boards drawn without it. After Part 2b the
  thumbnail's play button plays the video in the card itself; the reason holds.
- **L19. Official moves onto the thumbnail** (Ken, 2026-11-23, approved on the canvas).
  Guests should pick in-library songs first and official videos second, so the Official
  badge sits in the In library badge's top-left corner, after it when a card has both, and
  the order reads left to right. Same size and shape as L17's badge. Its icon is one
  verified-style check emblem (a scalloped badge with a white check) in two fills, for
  consistency (Ken): the palette's icon grey `#8c9b9d` beside In library, so green stays
  the loudest; the palette's Info `#3298dc` when Official is the only badge (Ken asked for a
  palette blue; the other, `#375a7f`, is the "chosen" blue and too dark on a badge). That
  gives Info a second job beside the running job on Processing; both are states, never
  buttons, and the palette board says so. The channel line drops the Official tag. The
  badge reads "Official video" or "Official audio", as the tag does today.
  **Amended by K6 (2026-11-24): one fill, Info blue, beside In library too.**
- **L20. One fill for every thumbnail badge** (Ken, 2026-11-23, approved on the canvas): In
  library, Official and the duration all sit on black at 60% (`rgba(0,0,0,0.6)`), the play
  circle's, the player bar's and Preview unavailable's. It replaces L17's solid `#282f2f`
  chip and the duration's 80%. 60% is the lightest that keeps the white text at 4.5:1 or
  better on a pure white frame (about 5.7:1; 50% gives about 3.9:1); the icons, not the fill,
  tell the badges apart. L13's In library row under a card is not a thumbnail badge and
  keeps its `#282f2f`. Being see-through, a badge reads near black on a dark thumbnail and
  mid grey on a bright one; Ken saw both on the canvas and kept it (a solid fill would look
  the same everywhere but cover the video again).

From Part 2b, word for word:

- **P5. Badges stay during the preview, clear of the player's controls.** Part 3's L17 In
  library badge (top-left) stays, smaller while the player is in the card so it covers less
  of the video (Ken, same day): canvas draws it 8 px from the corner, 4 px corners, padding
  3/7/3/5 px, a 13 px folder icon, 12 px bold text; the thumbnail keeps L17's full size.
  Approved as drawn (Ken, 2026-11-23): smaller only while the player is in the card, and
  L19's Official badge shrinks with it. Part 2b builds before Part 3, so on the card today
  only the duration badge exists; the shrink applies to L17's and L19's badges once Part 3
  adds them. The duration badge goes while the player is in the
  card (playing or paused), since the player's own time shows the length (Ken, amended the
  same day; first ruled as moved above the control bar). Drawn on the canvas board above,
  which Ken asked for in place of a ruling on whether to draw one.

  "While the player is in the card" is `playing` and `paused`, as the duration badge's rule
  already reads (`search.html`); the board draws state 1 (loading) at full size.

Still in force from Parts 2 and 2b, unchanged here: decision 7 (a card whose video is a
library file comes first; Show more lifts within its batch), decision 13 ("Queue…" means the
dialog opens first), L11 (every Queue and Queue… is green), S1/S2 (each library copy noted
once, on the first matching card, at most three, first page only), P6-P9 (only the play button
starts a preview; any tap outside its bar pauses it).

From "Phone pages: one look" (`plans/open-issues.md`), items this spec uses: 1 (one green
`#2ecc71`, one amber `#f1b70e`), 4 (other actions neutral grey: a `#434d4e` fill with a
`#5e6d6f` border and bold white text for a main action, an outline for the rest), 15 (that
grey fill, one step above the card), 16 (disabled, whatever its colour: no fill, a faded
border, a `#8c9b9d` label). All four are in `bulma-dark.css` on `dev` already.

### Canvas drawing choices (Opus, 2026-11-23; confirmed by Ken 2026-11-24 as K1)

Word for word from the old plan: Search button neutral grey (`#434d4e`, `#5e6d6f` border, bold
white), beside a dark `#282f2f` input, both 44 px with 6 px corners; Official tag a filled
`#434d4e` chip with a check icon, 12 px bold white, so it is louder than the channel and
quieter than the L17 badge (Ken's order: In library first, official second); "Search results
for…" becomes a 13 px `#b5bfc0` label, the rule above it goes; the Advanced panel is a `#282f2f`
inset with no shadow, its disabled Download in L16's look with 6 px corners, not a pill; the
page sits in the v2 `#343c3d` card under the guest nav bar.

Read with K1: the Official chip is moot (L19 put Official on the thumbnail), and the page
already sits in the `#343c3d` card (`base.html`'s `.box`), so nothing changes there.

### Canvas

https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), the reference look:

- "Search: results", "Search: Advanced open", "Search: card preview (Part 2b)" (row "Search").
  The preview board's check emblem was redrawn blue on 2026-11-24 (K6). Where it differs from
  P5-P8 (a tap on the thumbnail starts it, a 40 px bar with a fullscreen button), the rulings
  win, as in Part 2b.
- "Dialog after Part 3: caption found", "…: Genius pick", "…: search by name", "…: Queue's
  answers" (row "Download dialog after Search Part 3"), drawn and approved 2026-11-24 for
  K2, K3 and K5. The row above it ("Download dialog") is the dialog as built today.
- "Reference palette": the colours and their meanings.

Where this file and the canvas differ, this file wins.

### Assumptions (Opus, 2026-11-24, not ruled; reopen any by asking)

- **A1. The shared cleaner and its two changed names.** Measured 2026-11-24 on `dev`: one shared
  noise list gives the ranking exactly today's names on all 1146 channels of both fixture sets,
  moves no ranking on the 50 captured searches, and all 309 tests of `test_official_rank.py`,
  `test_genius_query.py` and `test_search_render.py` pass. Genius's name changes on exactly two
  channels, both from the YouTube captures and neither in its replay: "Music Topic BR" (was
  "Topic BR", now "BR") and "Vevo Music Group" (was "Vevo Group", now "Group"). Neither names an
  act either way, so this is accepted. The other way round (Genius's list shared) changes the
  ranking's names for the same two channels instead.
- **A2. The guard answers, the page queues.** `/lyrics_select` and `/download` answer "the
  library has this video" with its path and do nothing else; the page queues that path through
  `/enqueue`, exactly as an in-library card's Queue does (the queue hold, the refusal of a
  failed song and "already queued" all come from there). No new queue logic on the server.
- **A3. The guard also sits in `/lyrics_select`, before anything is written.** The lyrics stage
  reads a pending choice by video ID whenever a song with that ID is processed
  (`pipeline/stages/lyrics_fetch.py`, `read_choice`). A choice written for a video the library
  has, and then not downloaded, would be read by that song's next processing run, or by the
  run still going for a song just downloaded, and change its lyrics. So the choice is never
  written for an owned ID.
- **A4. The saved cards move to a new session key**, `pikaraoke_search_cards`. A copy under the
  old key can hold a stuck button or pre-Part 3 markup, so it is never put back; it is left to
  the tab's end.
- **A5. Card text from the shared rows.** The card's title and channel use `phone-rows.css`'s
  `.sr-title` (17 px bold) and `.sr-sub` (13 px `--dark-text-sub`), the canvas's sizes, so the
  values live in one place. Cards bleed 8 px into the page card like the rows, and the shading
  moves to even cards (`.sr-row:nth-child(even)`); the boards draw the first card unshaded.
- **A6. On the wide layout** (768 px and up, a 200 px thumbnail) both badges always take P5's
  small size and wrap to a second line if they must; at L17's full size two badges are wider
  than the thumbnail. Nothing else changes for wide screens (as P3).
- **A7. One value for the 60% black.** `--thumb-overlay: rgba(0, 0, 0, 0.6)`, declared once in
  the page's style, used by every thumbnail overlay (L20): the badges, the duration, the play
  circle, the card player's bar, Preview unavailable, and the dialog's Play and notice.
- **A8. The page's dark fields are one rule in `search.html`**: `#search-input`,
  `#direct-download-url`, `#lyrics-custom-input` and the lyrics list take `--dark-bg-secondary`
  with white text and a `--dark-border` border. Inside the Advanced inset, itself
  `--dark-bg-secondary`, the URL field takes the page's `--dark-bg-primary` so it shows (the
  board draws it so). `bulma-dark.css`'s white `.input` stays: flipping it would restyle the
  admin pages too (see Not doing).
- **A9. Advanced's Download, when enabled, is the grey fill** (L4); the board draws only its
  disabled look.
- **A10. "Searching YouTube for '…'"** takes the results label's look (13 px `--dark-text-sub`),
  Bulma's spinner kept.
- **A11. The page's hard-coded English gets translated strings**, since the catalog pass runs
  anyway: "Show more", "No more results", "Couldn't load more results.", "Could not add to the
  queue.", "Already queued". The close X's label becomes the existing "Close".
- **A12. The catalog pass regenerates only** (extract, update, compile with
  `scripts/compile_translations.py`), as every pass since 2026-06-10: new strings show in
  English until a translator fills them.
- **A13. Search's new style rules are scoped under its own ids** (`#search-form`,
  `#advanced-settings`, `#container_search_result`, `#search-results`, `#modal-js-example`).
  A page loaded first keeps its styles on every page tapped to after it (open issue "The first
  page's own styles stay on every page tapped to after it"), so unscoped rules would leak.
- **A14. Both failures show in the dialog.** A failed lyric save and a failed download each put
  their message in a red line under Queue (the board draws the download's). The page's notice
  sits under the dialog's backdrop, so it is used only when the dialog has closed or been
  replaced meanwhile.
- **A15. The search row pins to the top, through a shared class** (Ken, 2026-11-25). Only the
  search box and its Search button pin; Clear, Advanced and the Advanced panel scroll away
  (seldom used). Processing and Queue will pin too, later and on their own branches, so
  Browse's `.bp-pin` moves now to one `.pin-top` class in `phone-rows.css` (every phone page
  links it) rather than waiting for a third copy. It is Browse's rule unchanged, so Browse
  looks the same: sticky at the top, z-index 10, bleeding to the card's edges on the card's
  background; the pinned content sets its own side inset. Its `top` is 0 here; when
  `ui_tweaks` pins the nav bar it moves to below the nav in this one place. A shared class is
  not a leak under A13: it styles only what carries it.

## What exists (checked 2026-11-24 on `dev` at `d2ed9a3b`)

Line numbers are `dev`'s; they drift as commits land.

- `pikaraoke/lib/official_rank.py`: `_CHANNEL_NOISE` (line 40, separate words official, vevo,
  music, video(s), records, topic, channel, tv), `_CHANNEL_SUFFIX` (41, glued trailing noise and
  "show"), `_LABEL_CHANNEL` (42). `_channel_artist(result)` (139: drop " - Topic", the noise
  words, then `_compact`) is the credit name; `_channel_name(result)` (145: `_channel_artist`
  minus glued suffixes and a leading "the") is the own-channel name. `_compact` and `_words`
  keep ASCII letters and digits only.
- `pikaraoke/lib/genius_query.py`: `NOT_AN_ACT` (60), `CHANNEL_NOISE` (65: "- topic" and "vevo"
  at the end, glued or not; official, video(s), channel, music, tv as words; 官方專屬頻道),
  `_tidy` (122), `channel_name(channel)` (194: "" on `NOT_AN_ACT`, else noise out, CamelCase
  split, `_tidy`). Nothing outside the module reads `CHANNEL_NOISE`.
- `tests/unit/test_official_rank.py` loads the 50 captures in `tests/unit/data/youtube_search`;
  `tests/unit/test_genius_query.py` replays `tests/unit/data/genius_search` (queries, hit order,
  preselect; line 120 checks every row's frozen channel name).
- `pikaraoke/routes/search.py`: `_search_rows` builds `{video_id: path}` from the song list
  (lines 105-106, with the comment on why not `find_by_id`); `/download` (183-196) queues
  `k.download_manager.queue_download(song, queue, user, title)` and answers
  `{"status": "ok"}`; `/lyrics_select` (from 234) validates, calls `write_choice(yt_id,
  payload)` and answers 204. `get_youtube_id_from_url` (`lib/youtube_dl.py:80`) keeps everything
  after `v=` up to a `?`, so `watch?v=ID&list=…` gives `ID&list=…`.
- `pikaraoke/routes/queue.py`: `GET /enqueue?song=&user=` (217) → `_do_enqueue` answers
  `{"song", "success": [ok, message]}`, or 409 for a song the queue refuses.
- `pikaraoke/templates/search_result.html` (39 lines): the card macro. The Official tag sits in
  the channel line (`tag is-info is-light`, line 21), the "YouTube ↗" link at 22, the buttons
  at 24-28 (`search_result_items_enqueue` "Queue" for an owned card,
  `search_result_items_select` "Queue…" otherwise, both `is-success`), the library copy note at
  30-36 (`notification is-info is-light library-copy`, one msgid "In library:
  <strong>%(name)s</strong>", a small green `library-copy-enqueue`).
- `pikaraoke/templates/search.html` (1472 lines):
  - Styles inline in `{% block scripts %}` (6-331): the card list (odd cards shaded), the card
    preview (85-204), the dialog (206-330), `.duration-badge` (256, 80% black).
  - Script: the save and restore of the cards (340-383, key `pikaraoke_search_results`; the
    save copies the live `#container_search_result` through `DOMParser` and scrubs the
    preview; it runs after a submitted search and after Show more); `downloadSong` (456, the
    direct URL's `/download` with its own button flashes); `postDownload` (498, the dialog's
    `/download`, a notice on failure); `enqueueLocalSong` (516, `/enqueue` with flashes and two
    hard-coded English strings); Show more (558-585, hard-coded "No more results" and
    "Couldn't load more results."); `TEXT` (632-650); the dialog's Queue (926-966: disables,
    posts `/lyrics_select`, then on success shows Queued or Added, fades, and posts
    `/download` without waiting); the card preview (968-1156); the dialog's open and close
    (1158-1276, `.modal-close` bound in `openPreviewModal`).
  - Markup: the search form (1292-1310, `field has-addons`, amber `#search-link`), Clear and
    Advanced (1311-1319), `#advanced-settings` (1322-1350, `box has-background-black-bis`,
    `is-rounded is-primary` Download), `<hr />` (1353), the loader (1355), the results
    (1363-1380, a Bulma `label`, hard-coded "Show more"), the dialog (1384-1449, Bulma
    `.modal-close` at 1448 outside `.modal-content`, the amber `#lyrics-custom-btn`), the card
    player (1454-1470).
- `pikaraoke/static/phone-rows.css`: `.sr-title`, `.sr-sub`, `.sr-row:nth-child(even)` shading.
  `pikaraoke/static/bulma-dark.css`: tokens `--dark-bg-primary` `#1f2424`,
  `--dark-bg-secondary` `#282f2f`, `--dark-bg-tertiary` `#343c3d`, `--dark-bg-raised`
  `#434d4e`, `--dark-text-sub` `#b5bfc0`, `--dark-text-muted` `#8c9b9d`, `--dark-border`
  `#5e6d6f`, `--dark-danger-text` `#f17a6b`, `--dark-info` and `--dark-success`; `.input` is
  white (192-200); the disabled rule (182) skips `.is-loading` and `.is-flash`.
- `base.html`: every page sits in `.box` (327); the notice `#notification-alt` (322) sits in the
  page, so an open dialog's backdrop covers it. Browse's nav icon is fontello's
  `icon-folder-open-empty` (271). Queue and Browse link `phone-rows.css` from
  `{% block styles %}`; an SPA move loads a new page's stylesheets
  (`spa-navigation.js` `loadExternalResources`).
- `tests/unit/test_search_render.py` (37 tests): library note tests (381-501) assert the "In
  library: <strong>" line; the button test (511) pins `is-success search_result_items_select">
  Queue…`; badge tests (346, 749, 832) find "Official video"/"Official audio" in a card.
  `tests/unit/test_search_routes.py` has no `/download` test.
- Catalogs were last regenerated 2026-11-18 (`ee7062af`). "Play preview", "Preview
  unavailable", "Mute", "Unmute", "Seek" and every dialog string from `download_modal_speed`
  are in none of them.

## Design

### Phase 1: one channel cleaner

New module `pikaraoke/lib/youtube_channel.py`:

```python
CHANNEL_NOISE = re.compile(
    r"\s*-\s*topic$|\b(?:official|vevo|music|videos?|records|topic|channel|tv)\b|官方專屬頻道", re.I
)

def channel_words(channel: str) -> str:
    """The channel's name without the words YouTube channels add to an act's name."""
    return CHANNEL_NOISE.sub(" ", channel)
```

The docstring also says why the callers differ: noise glued to a name ("AdeleVEVO") is left to
each caller, and so is which names stand for no act. The ranking keeps a glued VEVO in its
credit name on purpose (see "A different song of the same name can still lift" in
`plans/open-issues.md`).

- `official_rank.py`: `_CHANNEL_NOISE` goes; `_channel_artist` becomes
  `_compact(channel_words(result.channel))` (the `removesuffix(" - Topic")` goes with it, the
  pattern's first branch does that). `_channel_name`, `_CHANNEL_SUFFIX` and `_LABEL_CHANNEL`
  stay.
- `genius_query.py`: `CHANNEL_NOISE` goes; `channel_name` keeps its `NOT_AN_ACT` check, then
  `_tidy(channel_words(channel))`, then drops a glued trailing VEVO (`re.sub(r"vevo$", "", …,
  flags=re.I)`), then the CamelCase split and `_tidy` as today. Its docstring keeps the "a
  trailing VEVO is not a label sign here" reason.

That is the variant measured for A1. Any other shape needs the gate below run again.

### Phase 2: duplicates and Queue's answer

**Server (`routes/search.py`, `lib/youtube_dl.py`).**

- `_library_ids(songs) -> dict[str, str]`, the `{video_id: path}` map `_search_rows` builds
  today, moved out with its comment; `_search_rows` calls it.
- `/lyrics_select`: after validation and before `write_choice`, if `yt_id` is a library file's
  ID, answer 200 `{"status": "in_library", "song_path": path}` and write nothing (A3).
  Otherwise as today (204).
- `/download`: read the ID with `get_youtube_id_from_url(song_url)`; if it is a library file's,
  answer 200 `{"status": "in_library", "song_path": path}` and queue nothing. Otherwise queue
  and answer `{"status": "ok"}` as today. The docstring says why: a stale page or a pasted
  link must not store a song twice.
- `get_youtube_id_from_url` stops at `&` as well as `?`, so a link with `&list=` or `&t=`
  gives the bare ID. Check its callers first (`graphify affected get_youtube_id_from_url`);
  stopping there can only correct them.
- Not guarded: a video still waiting in the download queue or downloading (Not doing).

**Page script (`search.html`).**

- `enqueueFile(path)`: the `/enqueue` call `enqueueLocalSong` makes today, split out. It
  resolves `{queued: true}` or `{queued: false, message}` (the queue's own refusal, e.g.
  already queued) and rejects with a message on a 409 or a network failure.
  `enqueueLocalSong` keeps its button flashes on top of it.
- `requestDownload(url, title, queue)`: the one `/download` call, replacing `postDownload` and
  the copy inside `downloadSong`. It resolves an outcome: `"queued"` (accepted, box ticked),
  `"added"` (accepted, box unticked), `"in-library"` (the library has it, box unticked),
  `"already-queued"` (the library has it, the box is ticked, and the queue said no, which
  today means already queued, as the card's Queue already shows it); on `in_library` with the
  box ticked it calls `enqueueFile(path)` and resolves `"queued"` when that queued it. Every
  failure, a 409 from `/enqueue` included, rejects with the message to show.
- The dialog's Queue: at the tap it takes everything it sends, as today, hides
  `#lyrics-send-error`, disables the list, and shows Bulma's spinner (`is-loading`) on the
  button until the outcome. It posts `/lyrics_select`; on `in_library` it skips `/download`
  and goes the in-library way (`enqueueFile` when ticked); otherwise it calls
  `requestDownload`. Then the button shows the outcome as the "Queue's answers" board draws
  it, and the dialog fades as today (`fadeOutPreviewModal(d, 1000)`):
  - `queued`: green, check icon, "Queued";
  - `added`: grey, check icon, "Added";
  - `in-library`: grey, the folder icon in green, "In library";
  - `already-queued`: amber (`is-warning`), "Already queued".
  - A failure, at either step: red "!" for 3 s, then Queue comes back for another tap; the
    message stays in `#lyrics-send-error` (a red 13 px line under Queue, `--dark-danger-text`)
    until the next tap or the dialog closes. If the dialog has closed or been replaced
    meanwhile (`isCurrent(d)` false), `showNotification(message, "is-danger")` instead (A14).
- Advanced's Download (`downloadSong`): `requestDownload`, and the same outcomes in its own
  button for 3 s: the check icon for `queued` and `added` (as today), the folder icon and "In
  library", amber "Already queued", red "!" with the notice for a failure.
- `TEXT` gains `inLibrary` ("In library", the same msgid as the badge), `alreadyQueued`,
  `couldNotQueue` ("Could not add to the queue."). `enqueueLocalSong`'s English strings move
  to `TEXT`.
- The flow comment's step 4 says Queue now waits for both answers.

**The saved cards (`search.html`), K4 and A4.**

- The saved copy is only ever built from what the server sent, never from the live cards.
  After a submitted search the page saves `#container_search_result`'s HTML at load, before
  anything can be tapped. After Show more, the new cards' HTML (as received and filtered,
  taken as strings before they are inserted) and the page's end state (the Show more button
  gone, or the "No more results" line) are written into the saved copy, parsed with
  `DOMParser`; the live page is not read.
- With no live copy ever saved, the preview scrub in `saveSearchResults` goes, and so does
  the restore's removal of an old copy's own dialog (no copy under the new key can hold one).
- The key is `pikaraoke_search_cards`; `forgetSearchResults` removes it.

### Phase 3: the look

Numbers are the canvas's unless a ruling says otherwise. Colours are `bulma-dark.css` tokens,
never restated hex values. Every new rule is scoped under Search's ids (A13).

**The page (`search.html`), commit 5.**

- The pin (A15): `search.html` links `phone-rows.css` from a `{% block styles %}`, as Queue and
  Browse do (moved here from commit 6). `#search-form` is wrapped in a `.pin-top` div with a
  20 px side inset; the Clear / Advanced row and everything below stay outside it. Browse's
  `.bp-pin` rule and class go; its pin div takes `.pin-top`.
- Search form: one flex row, gap 8 px. `#search-input` dark (A8), 44 px, 6 px corners, 0 12 px
  padding. `#search-link` a plain `.button` (grey), 44 px, 6 px corners, 15 px bold, 0 16 px
  padding; `is-warning` goes. Its `is-loading` wait state stays.
- Clear: `--dark-danger-text`, 15 px, a 44 px tap height. Advanced's tick label
  `--dark-text-light`, 44 px tall.
- `#advanced-settings`: the inset, `--dark-bg-secondary`, 6 px corners, 16 px padding, no shadow
  (`box has-background-black-bis` goes). Its rule a 1 px `--dark-bg-raised` line. The URL label
  13 px `--dark-text-sub` (same text, K1). The URL field `--dark-bg-primary` (A8). Download a
  plain grey `.button`, 44 px, 6 px corners, 15 px bold, right-aligned; disabled it takes L16
  from the theme. `is-rounded is-primary` go.
- The `<hr />` above the results goes. The results label becomes a 13 px `--dark-text-sub`
  line, margin 0 0 8 px, with its `{% trans %}` block's text unchanged, so the msgid holds
  (K1). The loader takes the same look (A10).
- Show more: 44 px, 6 px corners, grey, full width; "Show more", "No more results" and
  "Couldn't load more results." become translated strings (A11), the two script ones in
  `TEXT`.

**The card (`search_result.html`, `search.html`), commit 6.**

- `--thumb-overlay` (A7) replaces each `rgba(0, 0, 0, 0.6)` on the page and the duration's 80%.
- Thumbnail: `.img-frame` gets 6 px corners and clips (`overflow: hidden`), so the card player
  inside it is clipped too.
- Badges: one `.card-badges` row at the frame's top left (10 px in), gap 6 px, `flex-wrap`,
  `pointer-events: none`, above the player (z-index 3, as the duration). In library first,
  then Official; each a `.card-badge`: `--thumb-overlay` fill, 6 px corners, padding
  6/12/6/10 px, 15 px bold white, a 7 px gap after an 18 px icon.
  - In library, only on a card with `row.existing_path`: fontello `icon-folder-open-empty` in
    `--dark-success`, "In library".
  - Official, only with `row.official`: the check emblem as an inline SVG (the board's two
    paths, `aria-hidden`), its scallop filled `--dark-info` (K6), and "Official video" or
    "Official audio" as two translated strings (replacing `Official {{ row.official }}`).
  - Small (P5), on `li[data-preview="playing"]` and `li[data-preview="paused"]`, and always at
    768 px and up (A6): 8 px in, gap 4 px; padding 3/7/3/5 px, 4 px corners, 12 px bold, line
    height 1.2, a 4 px gap after a 13 px icon.
- Duration: `--thumb-overlay`, 6 px from the bottom right, 12 px, padding 1px 5px, 3 px corners.
  Its hide rule for `playing`/`paused` stays.
- Text: the title in `.sr-title`, the channel in `.sr-sub` (A5); the channel line carries no
  Official tag (L19); the "YouTube ↗" link goes (L18).
- Card: padding 12 px 8 px, margin 0 -8 px, gap 12 px between thumbnail and text; shading on
  even cards (A5).
- The card's button, 44 px tall, at least 60 px wide, 0 12 px padding, 6 px corners, 15 px
  bold:
  - an owned card (`existing_path`): green "Queue" (`search_result_items_enqueue`), as today;
  - a card with `row.library_copies`: grey "Download…" (`search_result_items_select`, no
    `is-success`), one new string (U+2026) (L13);
  - any other card: green "Queue…" (`search_result_items_select is-success`), as today.
- The In library row (L13), one per noted copy, replacing the notification: `.library-copy`,
  `--dark-bg-secondary`, 6 px corners, padding 8/8/8/12 px, gap 10 px; the folder icon (18 px,
  `--dark-text-sub`); a column of "In library" (13 px `--dark-text-sub`, the badge's msgid)
  over the file name (`<strong>`, 15 px, escaped, `filename_from_path(path)`); the green Queue
  at the card button's size (`library-copy-enqueue`, `data-file-path`). "In library:
  <strong>%(name)s</strong>" goes. Each new string gets a `MSG:` note for translators.

**The dialog (`search.html`), commit 7.** As the four "Dialog after Part 3" boards draw it.

- `#modal-js-example .modal-content`: the card, `--dark-bg-tertiary`, 8 px corners, 16 px
  padding (width and the 20 px top margin as today).
- The close X (K3): Bulma's `.modal-close` goes. `#modal-video-head` becomes a flex row: the
  title and channel line, then `<button type="button" id="modal-close">` with
  `aria-label` `_("Close")`, a 16 px white X (inline SVG, `aria-hidden`), 44 x 44 px, no fill,
  6 px corners, pulled into the card's corner (`margin: -12px -12px 0 0`).
  `openPreviewModal` focuses it and binds it where it bound `.modal-close`; the backdrop
  still closes.
- The channel line, `.lyrics-hint` and "Other lyrics…" take `--dark-text-sub` (was `#a3b0b2`);
  "Other lyrics…" keeps a 44 px tap height.
- The video box: 6 px corners and clipped; `#modal-thumb-layer` `--dark-bg-secondary` (the card
  is `--dark-bg-tertiary` now); `#modal-preview-unavailable` 6 px corners on `--thumb-overlay`.
- The list (`#lyrics-select-wrap select`): dark (A8), 48 px as today, 6 px corners; the teal
  arrow stays.
- "Search for other lyrics…": an outline, transparent, `--dark-border`, 44 px, 6 px corners,
  15 px white.
- The typed search: `field has-addons` becomes a flex row, gap 8 px; `#lyrics-custom-input`
  dark (A8), 44 px, 6 px corners, its 17.6 px font kept (iOS zooms below 16 px);
  `#lyrics-custom-btn` the page's grey Search (`is-warning` goes), 15 px bold.
- Queue: 48 px, 6 px corners. Its answer looks are commit 3's; this commit only checks them
  against the board.

## Not doing

- **The m:ss clock's third copy.** Home's `fmtTime`, Playlist's `clock` and Search's `clock`
  want one shared formatter, which reaches Home and Playlist for a few lines; not a Search
  change.
- **Leaving Search mid-preview keeps the clip loaded.** Closing it needs a "page leaving"
  signal in `spa-navigation.js`, answered in every page's script.
- **A JavaScript test setup.** Its own plan (open issue "Nothing tests what the search dialog's
  script does"); Phase 2 and 3's script is covered by `ui-check` runs, as before.
- **The dialog's caption check reads the preview link's client.** Download side, not the look.
- **The other `official_rank` ranking-quality entries** in "Search results (on `dev`)". Each
  needs a re-measure, which would muddy Phase 1's "nothing moved" check.
- **Redrawing restored cards** (not chosen in K4). A song downloaded from the page since the
  search still shows Queue… and no In library badge on a restored page, until the next search;
  its Queue now queues the library copy instead of downloading it again.
- **A video waiting or downloading, asked for again.** The guard checks the library only.
  Within the download window a second tap still queues a second download, and its lyric choice
  overwrites the first one's. Closing it needs `DownloadManager.queue_download` to check and
  add under one lock (it is also called from `library_tools.py`). For `plans/open-issues.md`
  at landing.
- **A lyric choice left by a failed download** (pre-existing): if `/download` fails after
  `/lyrics_select` succeeded and the guest gives up, the choice stays for that video ID until
  someone downloads it. The retry path overwrites it.
- **One dark field style for every page.** `bulma-dark.css`'s `.input` stays white; making it
  dark would restyle the admin pages (edit, info, batch rename) and Processing's playlist box.
  Search keeps its own rule (A8). Worth an open-issues entry at landing.
- **The page card's own corners and padding** (`base.html`'s `.box`, 8 px and 20 px; the
  boards draw 6 and 16). Every page shares it.
- **The tap highlight** ("The brief flash after a tap is square", app-wide, its own change).
- **Filling translations** (A12).

## Commits

Per-commit routine: `pre-commit run --config code_quality/.pre-commit-config.yaml --files
<changed files>`; the unit suite (`/home/ken/miniconda3/envs/pik/bin/python -m pytest
tests/unit -q`); an import smoke of the changed modules; a read of `git diff --cached` against
the commit's section; the CLAUDE.md self-review; then a Results row in a separate plan-only
commit (`docs(plans): search-phone results, commit N`). Tests ride with the code they check.
Stop where marked.

### Phase 1

**1. `refactor(search): one channel-name cleaner for the ranking and the Genius search`.**
`lib/youtube_channel.py` (new), `lib/official_rank.py`, `lib/genius_query.py`,
`tests/unit/test_youtube_channel.py` (new).

- Gate, before any edit: a snapshot script in the session scratchpad (not committed) writes,
  for every channel in `tests/unit/data/youtube_search/*.jsonl` and
  `tests/unit/data/genius_search/*.jsonl` (1146 distinct on `d2ed9a3b`), the three names
  (`official_rank._channel_artist`, `official_rank._channel_name`, `genius_query.channel_name`),
  and, for every capture in `youtube_search`, the ranked rows as `/search` ranks them
  (`read_first_page(rows[:PAGE_SIZE], query)`, then `official_first(rows, query, acts)`, as
  `(id, kind)` pairs), plus `/search/more`'s second page for the captures with 60 rows. Run it
  on `dev`, then after the edit; diff the two. Pass: the ranking's names and every order and
  kind are identical; Genius's names differ on exactly the two channels in A1. Anything else
  is a stop: report it and do not touch the lists to make it pass.
- `test_official_rank.py`, `test_genius_query.py` and their data pass with no edits.
- `test_youtube_channel.py`: one parametrized test of `channel_words`: separate noise words go
  ("Adele Official" → "Adele"), "- Topic" at the end goes, a glued VEVO stays
  ("BackstreetBoysVEVO"), 官方專屬頻道 goes, a name with none is unchanged.
- Results row: the snapshot diff (counts and the two names), the suite count.

**Stop after Phase 1.**

### Phase 2

**2. `fix(search): a video the library already has is queued from the library, not downloaded
again`.** `routes/search.py`, `lib/youtube_dl.py`, `tests/unit/test_search_routes.py`, a
test for `get_youtube_id_from_url` where its tests live (`graphify explain
get_youtube_id_from_url`).

- Tests, `/download`: an owned ID answers `in_library` with its path and does not call
  `queue_download`, with `queue` true and false, for each name form (`Title---ID.mp4`,
  `Title [ID].mp4`, a file in a subfolder); an unowned ID calls `queue_download(url, queue,
  user, title)` and answers `ok`; a link with `&list=` to an owned ID is caught too.
- Tests, `/lyrics_select`: an owned `yt_id` answers `in_library` with its path and does not call
  `write_choice`; an unowned one writes and answers 204 as today (the existing tests, given a
  library).
- `get_youtube_id_from_url`: `watch?v=ID&list=X` and `watch?v=ID&t=30` give `ID`.

**3. `fix(search): Queue and Download wait for the answer and queue the copy the library has`.**
`search.html` (script, `TEXT`, and `#lyrics-send-error` in the dialog's markup),
`test_search_render.py`.

- Test: the dialog has one hidden `#lyrics-send-error` inside `#lyrics-section`, after
  `#lyrics-queue-btn`.
- `ui-check` (recipe below), with Playwright routes answering `/lyrics_select`, `/download` and
  `/enqueue`, some answers held until released:
  1. Dialog, box ticked, `/download` held: the button shows the spinner and the list is
     disabled until release; then "Queued", green, and the dialog fades.
  2. Box unticked: "Added", grey.
  3. `/lyrics_select` answers `in_library`: no `/download` request; with the box ticked one
     `/enqueue` for that path and "Queued"; unticked, no `/enqueue` and "In library".
  4. `/download` answers `in_library`, box ticked, `/enqueue` answers already queued: amber
     "Already queued".
  5. `/download` answers 500: "!" for 3 s, the red line reads "Could not start the download.",
     then Queue is back and enabled; a second tap hides the line and tries again (two
     `/lyrics_select` and two `/download` requests in all).
  6. `/lyrics_select` answers 500: the same with its own message; no `/download` request.
  7. `/download` held, the dialog closed, then 500: the page's notice shows the message.
  8. Advanced's Download with a typed link: `ok` → the check icon; `in_library` with the box
     ticked → one `/enqueue` and the check icon; unticked → "In library"; 500 → "!" and the
     notice.
  9. A card's own Queue and a library row's Queue still enqueue and flash as before.

**4. `fix(search): a returning visit puts back the cards as the server sent them`.**
`search.html` (script), `test_search_render.py`.

- Test: the page's script names `pikaraoke_search_cards` and not `pikaraoke_search_results`.
- `ui-check`:
  1. A search, then SPA to Queue and back: the same 30 cards and the term.
  2. Show more with an owned card's Queue mid-flash (its `/enqueue` held), then SPA away and
     back: 60 cards, and that card's button reads "Queue", not loading or disabled.
  3. A preview playing, Show more (from script), SPA away and back: no card has
     `data-preview`, no `<video>` in the results.
  4. On a restored page, Show more appends 30 once (60 in the saved copy, not 90).
  5. "No more results" survives a restore.
  6. Clear removes the key; an old `pikaraoke_search_results` copy put in `sessionStorage` by
     hand is never restored.

**Stop after Phase 2.** Review due (commits 2-4: two routes, a script flow rewrite).

### Phase 3

**5. `feat(search): the search box pins to the top and the page takes the phone look`.**
`search.html`, `files.html`, `phone-rows.css`, `test_search_render.py`.

- Tests: `#search-form` sits inside a `.pin-top` element and `#clear-search` does not; the page
  links `phone-rows.css`; Browse renders a `.pin-top` and no `bp-pin`; `#search-link` has no
  `is-warning`; `#advanced-settings` has no `box` class; no `<hr`
  between the search form and the results; the results label and Advanced's URL label keep
  their text (K1); Show more reads "Show more".
- Existing form and add-to-queue tests pass unchanged.

**6. `feat(search): result cards show In library and Official on the thumbnail and drop the
YouTube link`.** `search_result.html`, `search.html`, `test_search_render.py`.

- Rewrite the note tests (381-501) for the row: "In library" label, the file name escaped in
  its `<strong>` (keep the escape test), `library-copy-enqueue` with the path; the "In library:"
  line is gone.
- New tests, on cards from `/search` and `/search/more`:
  - an owned card has one In library badge inside its `.img-frame`; no other card has one;
  - an official card has one Official badge inside its frame reading "Official video" or
    "Official audio", and its channel line has no tag; an owned official card has both, In
    library first;
  - no card has a `youtube.com/watch` link or "YouTube ↗";
  - a card with a library copy has a `search_result_items_select` reading "Download…" without
    `is-success`; other unowned cards read "Queue…" with `is-success`; owned cards keep
    `search_result_items_enqueue` "Queue";
  - the title is in `.sr-title`, the channel in `.sr-sub`.
- Mutation check (not committed): the YouTube link back, the badge outside the frame, the
  Official tag back in the channel line, "Download…" green: each fails a test.

**7. `feat(search): the download dialog sits on a card with its close button inside`.**
`search.html`, `test_search_render.py`.

- Tests: exactly one close button in the dialog, inside `.modal-content`, `type="button"` with an
  `aria-label`; no `modal-close` anywhere on the page; `#lyrics-custom-btn` has no `is-warning`.
- `ui-check` for Phase 3 (after commit 7): screenshots at 390 x 844 (`Pixel 7`) of the results,
  Advanced open, a playing and a paused preview on an owned official card, the dialog's three
  lyric states and each of Queue's answers, set beside the canvas boards; at 1100 px wide, the
  owned official card with both badges (small, inside the 200 px thumbnail). Computed styles
  checked, not eyeballed: 44 px heights and 6 px corners on the Search button, the search box,
  Download, the card buttons, Show more and the typed search; the badge fill
  `rgba(0, 0, 0, 0.6)`; the emblem's fill the Info blue beside In library and alone; the dialog
  card's background `--dark-bg-tertiary`. The X closes the dialog and gets focus on open; a
  backdrop tap closes it. Nothing on the page is white but text. The pin (A15): scrolled to the
  tenth card, the search row's top is at 0 and the cards pass under it (a playing card
  preview too); Clear has scrolled away; the open dialog sits above the pin. Browse, before
  and after commit 5, at the same scroll: the toggle and letter strip pin at the same place,
  with the same computed styles.

**Stop after Phase 3.** Review due (commits 5-7: markup and styles across three templates and `phone-rows.css`).

### Phase 4

**8. `i18n: regenerate translation catalogs for the search page`.** From `pikaraoke/`:

```shell
pybabel extract -F babel.cfg -o messages.pot --add-comments="MSG:" --strip-comment-tags --sort-by-file .
pybabel update -i messages.pot -d translations
python ../scripts/compile_translations.py
```

Never `pybabel compile`. Check in `messages.pot` and each `.po`: every string this Part added
(In library, Official video, Official audio, Download…, Already queued, Could not add to the
queue., Show more, No more results, Couldn't load more results.) and "Play preview", "Preview
unavailable", "Mute", "Unmute", "Seek" are present; "In library: <strong>%(name)s</strong>" is
gone (obsolete). Say in the commit message whether the compiled `.mo` files changed (they
should not: nothing new is translated, A12).

**Stop after Phase 4.**

## `ui-check` recipe

The `ui-check` skill on the VM, this worktree as `CHECKOUT`, a port nobody uses (confirm the
listener is yours: `launch.sh` kills whatever holds its port). A fake search, as Parts 2 and
2b ran it (their scripts were in old session scratchpads, so rebuild it): a wrapper that patches
`routes.search.get_search_results` to build 30 rows (60 for Show more) with fixed 11-character
IDs, one row carrying a library file's ID, one official (verified channel, "(Official Video)"
title, the act's channel), one owned and official, and one titled like another library song so
it gets a note. A `p.devices["Pixel 7"]` context and `page.tap`. Join as a guest by
`POST /singer` and set the `user` and `singer_token` cookies; `new_page`'s `user` cookie alone
leaves `#singer-modal` over the page. Thumbnails and `/caption_check` answered by Playwright
routes (Part 2b's recipe: a local WebM served with `Range` support for previews). Keep the
scripts in the session scratchpad and name them in the Results row.

## Manual checks (Ken, on a phone), Phase 5

- [ ] The page looks like "Search: results" and "Search: Advanced open": grey Search beside a
      dark box, red Clear, the dark Advanced inset, the small grey results line, no rule.
- [ ] Scroll down the results: the search box and Search stay at the top, Clear and Advanced
      scroll away. Browse's toggle and letter strip still pin as before.
- [ ] A video you own: first, an In library badge on its thumbnail (green folder), green Queue.
- [ ] An official video: an "Official video" badge with a blue check; an owned official video:
      both badges, In library first, the check blue too.
- [ ] A song you own under another upload: that card's button reads Download… in grey, with the
      dark In library row under it; the row's Queue queues your file; Download… opens the
      dialog, whose button reads Queue.
- [ ] No YouTube link on any card.
- [ ] A preview playing and paused: the badges shrink and the duration goes; stopped, full size.
- [ ] The dialog sits on a card; its X (top right, inside) and a tap on the backdrop both close
      it. The list and the lyric search box are dark, Search sits beside the box, Search for
      other lyrics… is an outline.
- [ ] Queue in the dialog: a spinner, then Queued, then it fades. With Advanced's box unticked:
      Added.
- [ ] Download a song, let it finish, go to Queue and back to Search (the page comes back from
      memory): its card still says Queue…; the dialog's Queue says Queued and the queue gets
      your library copy, with no new download on Processing. Box unticked: "In library".
- [ ] Advanced, a link to a video you own: Download answers without downloading it again.
- [ ] The server stopped (or the phone offline) when you tap the dialog's Queue: "!", the red
      line, then Queue comes back.
- [ ] Show more, tap an owned card's Queue and leave Search at once; come back: no stuck
      spinner.
- [ ] The labels read as before where they existed (Search results for '…', Direct download
      YouTube url:).

## At landing (not Sonnet's)

- Copy the code commits onto `dev` in order, without the plan.
- `plans/open-issues.md` on `dev`: strike "Unify the channel cleaners", "A search card you
  already own can be downloaded again", "The dialog's Queue says Queued before the download is
  accepted"; rewrite "A restored search page can show a stuck card" to its remaining half (the
  stale library state, now harmless: K4); add the in-flight duplicate and the one dark field
  style (Not doing); the landing order's Search Part 3 line and its "Not ruled" item (K7).
  Also add, from the Phase 2 review (finding 3): "A lyric choice can be left for a song the
  library has. `/lyrics_select` and `/download` each check the library; a download of the same
  video that lands between the two calls lets the first write the choice and the second answer
  `in_library`, so that song's next lyrics run reads it. Fix: `/download` deletes the choice
  when it answers `in_library`, or one route checks once. Narrow window; not ruled."
- Phase 2 review, kept as built: a queue refusal still shows amber "Already queued" for the
  per-user limit too (the queue's message beside it says which); the old
  `pikaraoke_search_results` key is not removed, since commit 4's test bars naming it and
  `sessionStorage` dies with the tab.
- Canvas: retitle the "after Part 3" dialog row as built, the Search note's owner.
- Retire `search_official_captions` as a tag, if not done already, and repoint its references.

## Results log

| Commit | Hash | Suite | Notes |
|---|---|---|---|
| 1 | `205c78b6` | 4555 passed (`tests/unit`), 318 in the four files that matter: `test_youtube_channel.py` (9, new), `test_official_rank.py`, `test_genius_query.py`, `test_search_render.py`; the other 309 pass with no edits | Gate, run on `7d111ce9` (`dev`'s code, before any edit) and again after, scripts `/tmp/claude-1000/-home-ken-projects-pikaraoke/9094a28e-87c9-4bcd-8075-bbb059f41ebd/scratchpad/channel_snapshot.py` and `channel_diff.py` (not committed); the base snapshot was run twice and is identical. 1146 distinct channels, 50 captures, 54 ranked pages (50 first pages, 4 second pages). `official_rank._channel_artist` 0 of 1146 changed; `_channel_name` 0 of 1146; ranking (order and kind of every row, and the voted originals, record words and has-video flag per capture) 0 of 50 captures changed. `genius_query.channel_name` 2 of 1146 changed, the two A1 names: `'Music Topic BR'` `'Topic BR'` -> `'BR'`; `'Vevo Music Group'` `'Vevo Group'` -> `'Group'`. Pre-commit clean on the four files. |
| 2 | `29b6a880` | 4573 passed (`tests/unit`); `test_search_routes.py` 23 -> 38 with the owned and unowned `/download` and `/lyrics_select` cases, `test_youtube_dl.py` 73 -> 76 | `/download` and `/lyrics_select` answer 200 `{"status": "in_library", "song_path"}` for an owned ID and do nothing else; `_library_ids` moved out of `_search_rows`; `get_youtube_id_from_url` stops at `&`, its four other callers (`download_manager` x2, `queue_hold`, `pipeline_tracker`) only compare or clean up by the bare ID. The route-test fixture now carries a one-song library, so the existing `/lyrics_select` tests run the guard's not-owned path. Mutation check (not committed): guard removed from `/download` fails 10 tests, moved after `write_choice` in `/lyrics_select` fails 1. Pre-commit clean on the four files. |
| 3 | `a9f8041d` | 4574 passed (`tests/unit`); `test_search_render.py` 44 -> 45 (the one hidden `#lyrics-send-error` after `#lyrics-queue-btn`, inside `#lyrics-section`) | `ui-check` 36 of 36 pass, scenarios 1-9 of the plan, Pixel 7 context, Chromium. Scripts `/tmp/claude-1000/-home-ken-projects-pikaraoke/f68ca82f-5b7a-4294-870f-0951011c1197/scratchpad/uicheck/search_app.py` (the real app, a fake karaoke, 30 fake rows, a library of two files), `common.py`, `check3.py` and `shots3.py` (not committed); port 5133; `/lyrics_select`, `/download`, `/enqueue`, `/caption_check`, `/lyrics_search` and thumbnails answered by Playwright routes, `/download` held and released where the scenario needs it. Settled colours read from computed styles: Queued `rgb(46, 204, 113)`, Added and In library `rgb(67, 77, 78)` with a `rgb(94, 109, 111)` border, Already queued `rgb(241, 183, 14)`, "!" `rgb(231, 76, 60)`, the red line `rgb(241, 122, 107)` at 13 px. Found by screenshot and fixed before commit: the answer's label was a bare text node, so Bulma's lone-icon margins pulled the folder 9 px into the "I" of "In library" (the old check icon had the same overlap); the label is now a `<span>`, 4.4 px between icon and label. Two changes beyond the spec text: Advanced's Download for "added" is now grey with the check (it was green for both outcomes, the dialog's table has it grey), and a button's restore puts back its saved class attribute instead of removing the classes the answer added, so a green card Queue keeps its green. Screenshots in `/tmp/claude-1000/-home-ken-projects-pikaraoke/f68ca82f-5b7a-4294-870f-0951011c1197/scratchpad/uicheck/out3/`. Pre-commit clean on the two files. |
| 4 | `04e0079e` | 4575 passed (`tests/unit`); `test_search_render.py` 45 -> 46 (the script names `pikaraoke_search_cards` and not `pikaraoke_search_results`) | `ui-check` 22 of 22 pass, scenarios 1-6 of the plan, same harness as commit 3 plus `/tmp/claude-1000/-home-ken-projects-pikaraoke/f68ca82f-5b7a-4294-870f-0951011c1197/scratchpad/uicheck/check4.py` and a 30 s test clip (`clip.webm`, served with Range support) for scenario 3 (not committed); commit 3's `check3.py` re-run on the final template, 36 of 36. Run against the pre-commit-4 template (`HEAD`) the same script fails the stuck-button case (scenario 2: the owned card's Queue comes back `is-loading` and disabled, as the open issue says) and the key checks of 4 and 6; scenario 3 passes there too, since the old scrub already removed preview state, so its value is that the new code needs no scrub. In the new code scenario 3's saved copy holds no `data-preview` and no `<video>` while the live page still shows the preview. Scenario 2 taps Queue first and then Show more, as the plan reads; run the other way round the old code saves before the tap and passes. Pre-commit clean on the two files. |
| Review (Phase 2) | `dc35a68e` | 4587 passed (`tests/unit`); `test_youtube_dl.py` +6 (`/v/`, `#t=`, `feature=…&v=`, `m.youtube.com/?v=`, 10- and 12-char IDs), `test_search_routes.py` +6 (three link forms to an owned video, four non-object bodies to `/lyrics_select`); `test_download_manager.py`'s `test_execute_download_success` fixture moved from `abc123` to an 11-char ID, which the pattern now requires | `/code-review high 29b6a880~1..04e0079e`, 10 findings: fixed 1 (limit read as already queued), 2 (second tap mid-answer), 4 (link forms), 6 (non-object body), 7 (storage write throws), 8 (unreadable `/enqueue`), 9 (stale comment only), 10 (duplicate answer logic); 3 (choice race) to open-issues at landing; 5 (in-flight duplicate) already there. New `ui-check` `/tmp/claude-1000/-home-ken-projects-pikaraoke/38093c9b-cdbb-409c-8fb0-5c0d59cd3e1b/scratchpad/uicheck/check5.py` (harness copied from commit 3's scratchpad, not committed): 17 of 17 on the fix; on `04e0079e`'s template 7 of 14 fail, every scenario (A limit line, B notice after close, C stuck Download, D hung spinner, E green under amber, F handlers dead after a storage throw). `check3.py` 36 of 36, `check4.py` 22 of 22 on the fix. New test-only fact: Bulma's `is-loading` drops pointer events, so the second tap can only land during the 3 s answer. Pre-commit clean on the six files. |
| 5 | `b600007a` | 4591 passed (`tests/unit`); `test_search_render.py` 46 -> 49 (the pin holds the box and button, not Clear or Advanced, and the page links `phone-rows.css`; no amber Search, no `box`, no `<hr>` above the results; the labels keep their text and Show more reads "Show more"), `test_files_routes.py` +1 (Browse's toggle and strip share one `.pin-top`, no `bp-pin`) | Mutation check (not committed): the amber button back, `box` back, the `<hr>` back, the pin div gone, Clear inside the pin: each fails exactly one test. `ui-check` scripts `/tmp/claude-1000/-home-ken-pikaraoke/5b954dbf-ce67-47d8-869b-d28d2b0e9618/scratchpad/uicheck/search_app.py` (the real app, `run_app.py`'s patches, a fake `get_search_results`: 30 rows, 60 for Show more, four library files of 0 bytes), `launch_search.sh`, `common.py`, `check5.py`, `shots5.py` (not committed); `check5.py` 10 of 10, `shots5.py` 12 of 12; Pixel 7 context, port 5733 on this worktree and 5734 on `dev`'s checkout for Browse's "before". Browse's pin, `.bp-pin` on `dev` against `.pin-top` here: the same computed style on the pin (sticky, top 0, z-index 10, margin -12px -20px 0, padding 12px 0 16px, `rgb(52, 60, 61)`), the toggle and the strip, the same box at scroll 0 (top 130) and at scroll 600 (top 0). Search, scrolled to the tenth card: the pin's top is 0, Clear's bottom is above the screen, a point inside the pin hits the pin and not a card, the form has the card's 20px side inset. Computed: search box, Search, Download and Show more all 44px high with 6px corners; the box `rgb(40, 47, 47)` with white text, the URL field `rgb(31, 36, 36)`, the inset `rgb(40, 47, 47)` with 6px corners; Search `rgb(67, 77, 78)` with a `rgb(94, 109, 111)` border; Clear `rgb(241, 122, 107)`, 44px; Download disabled has no fill and a `rgb(140, 155, 157)` label, enabled the grey fill. Two things seen: the grey buttons' label is the theme's `rgb(236, 238, 239)`, not pure white, and was left (an `#id` colour would also beat the disabled and result colours); the unticked Advanced box is the browser's white native checkbox (`bulma-dark.css` `.checkbox` sets only its accent), the theme's, not this page's: it bears on phase 3's "nothing on the page is white but text" check. Screenshots in `{SP}/out/` (`c5_*.png`). Pre-commit clean on the five files (Black reformatted the test file once). |
| 6 | `a6b9e6cf` | 4600 passed (`tests/unit`); `test_search_render.py` 49 -> 58 (nine new, on `/search` and `/search/more`: one In library badge in the frame of an owned card and none elsewhere; Official video and Official audio in the frame with no tag in the channel line, both badges in order on an owned official card; no `<a>` in any card; Download… grey, Queue… and Queue green; `.sr-title` and `.sr-sub`) | The note tests (381-501) now read the row: "In library" label, the name escaped in its `<strong>`, `library-copy-enqueue` with the path, the old "In library:" line absent; they count the row by its markup, since the page's own style block names the class. A card is a `phone-rows.css` `.sr-row` (even shading and the 8px bleed come from there), so the card's own `nth-child(odd)` rule went. Mutation check (not committed): the YouTube link back (2 tests fail), the badges outside the frame (4), the Official tag back in the channel line (2), Download… green (1). `ui-check`, `/tmp/claude-1000/-home-ken-pikaraoke/5b954dbf-ce67-47d8-869b-d28d2b0e9618/scratchpad/uicheck/check6.py` 28 of 28 (Pixel 7, then a 1100px context), port 5733; `search_app.py` changed from commit 5's: the ranking lifts only rows that are the searched song and needs two credits for the act, so the fake answers two queries ("never gonna give you up": the owned official video, an official audio, an ordinary owned card, a library copy noted on a card; "together forever": an official video that is not owned). Computed: cards padding 12px 8px, margin 0 -8px, gap 12px, touching (0px between), even cards `rgb(50, 55, 55)` and the first unshaded; frame 6px corners and clipped; badge row 10px in, gap 6px, z 3, `pointer-events: none`; badge `rgba(0, 0, 0, 0.6)`, padding 6/12/6/10, 6px corners, 15px bold, 7px gap, the folder `rgb(46, 204, 113)` at 18px; the emblem's scallop `rgb(50, 152, 220)` beside In library and alone, the check white; duration 12px, 1/5 padding, 3px corners, 60% black, 6px from the corner; the play circle 60% black; Queue, Queue… and Download… 44px, at least 60px wide, 0 12px, 6px corners, 15px bold, fills green, green and `rgb(67, 77, 78)`; the library row `rgb(40, 47, 47)`, 6px corners, padding 8/8/8/12, gap 10, 13px label and 15px name and 18px folder in `rgb(181, 191, 192)`, its Queue 44px; title 17px bold, channel 13px. At 1100px: both badges at the small size (padding 3/7/3/5, 4px corners, 12px), side by side on one line inside the 200px thumbnail. One addition the spec text lacks: `margin-top: 0` on a card, since Bulma's `li + li` gave every card after the first a 4px gap (a dark stripe between shaded cards). The playing/paused small size is checked by its rule in commit 7's `ui-check` against a real preview. Board details read from the canvas file (`SearchAfter`, `SearchPreview`): the board draws the folder as an inline SVG, the spec says the fontello Browse icon, which was kept; the check emblem's two paths are the board's. Screenshots in `/tmp/claude-1000/-home-ken-pikaraoke/5b954dbf-ce67-47d8-869b-d28d2b0e9618/scratchpad/uicheck/out/` (`c6_*.png`). Pre-commit clean on the three files (Black reformatted the test file once). |
| 7 | `76336074` | 4602 passed (`tests/unit`); `test_search_render.py` 58 -> 60 (one labelled `type="button"` close button inside `.modal-content`, the only `modal-close` id on the page, no `modal-close` class and no `.modal-close` in the script, the backdrop still there; the typed search is one `#lyrics-custom-row` with a plain button and no `has-addons` in the dialog) | Mutation check (not committed): Bulma's class back on the X, a second close button, the amber typed Search back, the X outside the card: each fails exactly one test. **Phase 3 `ui-check`** (Pixel 7 context, Chromium, port 5733 on this worktree): `/tmp/claude-1000/-home-ken-pikaraoke/5b954dbf-ce67-47d8-869b-d28d2b0e9618/scratchpad/uicheck/check7.py` 38 of 38, with `wire.py` (Playwright routes for `/caption_check`, `/lyrics_search`, `/lyrics_select`, `/download`, `/enqueue`, and a 30 s WebM, `clip.webm`, served with `Range`); `check5.py` 10 of 10, `shots5.py` 12 of 12 and `check6.py` 28 of 28 re-run on the final templates. Dialog, caption found: the X has focus on open, 44x44 with 6px corners, no fill, inside the card at its top right (its right edge 4px short of the card's, its top 4px below); card `rgb(52, 60, 61)` with 8px corners and 16px padding; video box 6px corners and clipped; thumbnail layer `rgb(40, 47, 47)`; Play `rgba(0, 0, 0, 0.6)`; Queue 48px with 6px corners; Other lyrics… and the channel line `rgb(181, 191, 192)`, Other lyrics… 44px tall. The X closes the dialog; a tap at the backdrop's edge closes it. Genius pick: the list `rgb(40, 47, 47)` with white text, 6px corners, 48px; Search for other lyrics… transparent with a `rgb(94, 109, 111)` border, 44px, 6px corners, 15px white; the typed box `rgb(40, 47, 47)`, 44px, 6px corners, 17.6px; its Search `rgb(67, 77, 78)`, 44px, 15px bold, 8px beside the box on one row. With no caption and no hits the typed box opens by itself. Queue's answers, read once the colour has settled: Queued `rgb(46, 204, 113)`, Added and In library `rgb(67, 77, 78)` (the folder `rgb(46, 204, 113)`), Already queued `rgb(241, 183, 14)`, "!" `rgb(231, 76, 60)` with the line `Could not start the download.` at 13px `rgb(241, 122, 107)` under it; every one 48px with 6px corners. Previews on the owned official card: playing, the badges are small (8px in, gap 4px, padding 3/7/3/5, 4px corners, 12px bold, 13px icon) and the duration is gone; paused, the same; started on another card, back to full size. The bar is `rgba(0, 0, 0, 0.6)`. The pin with the playing card scrolled under it: the pin's top is 0 and a point inside it hits the pin, not the player. Scrolled to the tenth card with the pin stuck, the open dialog sits above it. At 1100px the owned official card has both badges small. Light surfaces: a scan of every visible element on the page card for a near-white fill found none. Not light: the browser's native checkboxes (Advanced, Add to queue), which is the theme's and was noted in commit 5's row; and base.html's join form, whose name field `#singer-name` is white (not this page, hidden unless the phone has not joined). The plan's 390 x 844 is not Pixel 7's size: the context is 412 x 915 as `p.devices` gives it. Screenshots in `{SP}/out/` (`c7_*.png`), the dialog and answers beside the boards `DialogP3Caption`, `DialogP3Genius`, `DialogP3Search`, `DialogP3Queue`. Pre-commit clean on both files. |
| Review (Phase 3) | `91b16ea2` | 4602 passed (`tests/unit`); `test_search_render.py` 60, unchanged count | From `/code-review high b600007a~1..76336074` (6 nits). Fixed: #3 the typed-search box joins the field size rule (padding 0 12px, was Bulma's), the button's duplicate 44px rule dropped; #4 `.video-container` (+ `video`), `.lyrics-hint` under `#modal-js-example`, `.duration-badge`, `.search_result_items_meta`, `li.sr-row` under `#search-results`; #5 `_FormAncestors` and `_Ancestors` removed, `_ancestor_ids`/`_ancestor_classes` walk `_Fragment`'s parents; #6 the no-tag check reads `.search_result_items_meta`'s elements and `.sr-sub`'s children. Dropped: #1 (commit 6's and 7's `ui-check` at 1100px measured both badges on one line), #2 (sharing the small badge values across the media query needs a second variable layer of the same length). Mutation check (not committed): a `tag` span in the channel line (2 fail), `pin-top` renamed (1), `#singer-modal` wrapped in `.container` (2). `check6.py` 28 of 28, `check7.py` 38 of 38 on the final template, port 5733; probe: `#lyrics-custom-input` padding 12/12, 44px, flex 1; `#lyrics-custom-btn` 16/16, 44px; the dialog's video box still clipped, the duration still absolute. Pre-commit clean (Black reformatted the test file once). |
