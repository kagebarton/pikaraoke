# Browse page for phones

Model: Claude Opus 5.5 (decisions). Phase 0's executor and judge are named in that phase.

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

## Where the names come from (open until GATE N)

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

## Phase 1: Browse page (after GATE N)

To be specified after GATE N. Known scope from today's code:

- `routes/files.py` `browse()`: drop `flask_paginate`, `sort=date` and `page`; keep `letter`
  (`numeric` stands for `#`) and add the artist/song mode. Default letter: the first non-empty one.
- `templates/files.html`: rebuilt per decisions 1-9.
- `browse_results_per_page` (preference, `karaoke.py`, `info.html` setting, tests) has no use left
  and goes.
- States: today's tags (`is_active`, tracker `waiting`/`pending`/`active`, pipeline
  `pending`/`failed`) map onto decision 7's three.

## Phase 2: stored names (only if GATE N picks (c))

To be specified after GATE N: fill `songs.artist` and `songs.title` from the Genius match at
download (and after a lyrics repair), with the agreement check; backfill the library from the
debug bundles.

## Not in this plan

- The Queue page. Its mockups show today's page; changes get their own decisions.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
