Model: Claude Opus 5.5

# Flag songs that look like one already in the library

## Problem

A video is "in the library" today only when its 11-char YouTube ID matches a
file. A different upload of the same song (another channel, a lyric video, the
film clip) counts as new and gets downloaded again. Two surfaces hit this:

- **Playlist page** (`playlist.html`, admin): crowd-sourced playlists hold the
  same song from different uploads, both against the library and within the
  playlist itself.
- **Search page** (`search.html`, guests): a guest searches a song the library
  already has under another ID and downloads a second copy instead of queuing
  the first.

The flag never blocks anything. It puts the existing copy in front of the
person deciding.

Out of scope (already in `plans/open-issues.md` on `custom_lyrics`): the same
*ID* queued twice from two tabs (8.1f), download vs regen lane overlap (3.1i).

## Base

`custom_lyrics` lands on `dev` first. It was cut from `dev` at `8b89c17`
(library pages' (i) notes) and its tip is `96af03a`; `dev` is its ancestor, so
the merge can fast-forward. This work branches `similar_song_flag` off `dev`
*after* that merge.

Why wait: `custom_lyrics` rewrites large parts of `library_tools.py` (~150 lines
changed) and `tests/unit/test_library_tools.py` (~440), the files step 3's
server side and tests land in. `check_playlist` / `add_playlist` themselves are identical on
both branches (checked); they only move (line ~711 on `dev`, ~787 on
`custom_lyrics`). `search.py`, `search.html`, `playlist.html`,
`library_links.py` and `metadata_parser.py` are identical on both.

Phase 0 (no code):

1. `git merge-base --is-ancestor 96af03a dev` passes (custom_lyrics is in).
2. `git status` on `dev` clean apart from untracked `plans/`.
3. Baseline: `python -m pytest tests/unit/test_library_tools.py
   tests/unit/test_library_routes.py tests/unit/test_search*.py` passes; record
   the count in the Results log.
4. Cut `similar_song_flag` from `dev`. This plan file is first committed with
   step 1. Never commit to `master`.

## Matching (shared, new module `pikaraoke/lib/song_match.py`)

Title-only, local, no network. Prototyped against the 33-song library
(scratchpad scripts `dupkey3.py`, `dupsearch.py`).

1. **Parts.** Drop the `---ID` / `[ID]` suffix, drop bracketed text, split on
   ` - `, ` | `, ` _ `, ` : `. Quoted text *outside* brackets is also a part.
   Normalize each part: accents off, lowercase, `NOISE_PATTERN` and a few stop
   words (`the`, `a`, `official`, `video`, `lyrics`, ...) removed, punctuation
   gone. Keep parts of 4+ chars.
2. **Shared part = match**, except a part that
   - appears in 3+ library titles (artist or film name, e.g. "justin
     timberlake", "wicked musical"), or
   - is the *leading* part of both titles (usually the artist: two Backstreet
     Boys songs).
3. **Title with a quoted part outside brackets:** the quote is the song name and
   the only part that can match. Fixes `'Defying Gravity' - Wicked 20th
   Anniversary Edition` matching `'Popular' - Wicked 20th Anniversary Edition`.
   Quotes inside brackets (`(From 'Frozen')`) are film names and are dropped
   with the brackets.

Prototype results before rule 1's "outside brackets" and rule 3 (both untested):

| Case | Result |
| --- | --- |
| Library pairs: A Whole New World x2, For Good x2 | found |
| Library: Defying Gravity vs Popular | false match (rule 3 targets it) |
| Search "Aladdin - A Whole New World (Lyrics)" | both library versions |
| Search "Justin Timberlake - Mirrors (Lyrics)" | the library copy only |
| Search "Belle - Beauty and the Beast", "Bloodstream - Ed Sheeran ..." | found |
| Search "Frozen - Let It Go" | Let It Go + false "In Summer (From 'Frozen')" (rule 1 quote fix targets it) |
| Search for songs not in library (Can't Stop The Feeling, Shape of You, ...) | nothing |

Known miss: two titles that both *lead* with the song name and differ after it
("Let It Go - Frozen" vs "Let It Go - Idina Menzel"). Acceptable for a first
cut; the flag leans toward showing, not hiding.

Public API (sketch):

- `similar_songs(title: str, library: SongIndex) -> list[str]` — library song
  paths that look like `title`.
- `SongIndex.from_songs(paths)` — parts per library song plus part frequency,
  built once per request from `song_manager.songs` (display name via
  `filename_from_path`).
- `group_similar(titles: list[str], library: SongIndex) -> list[list[int]]` —
  within-list groups for the playlist (frequency counted over library +
  playlist).

Escalation if precision is not enough: Last.fm canonical name
(`metadata_parser.lookup_lastfm`), one call per title, rate-limited. Not in
this plan.

## Search page

All results for one query are versions of one song by construction, so no
within-results grouping. Only result vs library.

Server: `search()` in `routes/search.py` collects library songs similar to any
result, minus songs a result already matches by ID (that row already says
"Add to Queue"). Passes `similar_songs` (up to 3 paths) to the template.

Page: one note above the results, not per row (every row would repeat it):

> Already in the library: **Mena Massoud, Naomi Scott - A Whole New World**
> [Add to Queue]

The button reuses `enqueueLocalSong`. The search page does not load
`library-pages.css` / `info_tip.html` and doesn't need to: the note is one
line with no explanation to hide.

Fork note: `search.py` and `search.html` are upstream files the fork already
changed; keep the change to one context value and one template block.

## Playlist page

Server: `LibraryTools.check_playlist` adds per video `channel`, `duration`
(from the flat-playlist entry, if present; `read_playlist` passes them
through) and a `similar` group: other playlist video IDs and/or library song
paths. `add_playlist` is unchanged: it already takes only the ticked videos.

Page, built on `8b89c17`'s layout:

- A **"Possible duplicates (N)"** section above "New", rendered through the
  existing `section(title, card, tipId)` helper. Its explanation goes in an (i)
  note from a new `<template id="pl-tip-similar">` (`info_tip` macro), matching
  the other sections; no muted note rows (8b89c17 removed those).
- One card per group, headed by the shared part. Library copies are
  non-tickable rows (`listedRow`). A new video matching the library starts
  unticked; within a playlist group the first starts ticked, the rest
  unticked (open: Ken may prefer all ticked). Each row shows channel, length,
  YouTube link. Grouped videos leave the "New" list; ticks share `state.left`
  so the Go button count stays one rule.
- A yellow "N possible duplicates" pill joins the summary pills.
- Page-only styles stay in the page's `<style>` block with the `pl-` prefix;
  `library-pages.css` is for what several library pages share.

## Order

0. Phase 0 above.
1. `song_match.py` + tests (real library titles from the table as cases, both
   rule fixes covered). Commit with this plan.
2. Search page (server + note + route test). Commit.
3. Playlist server side (`read_playlist` fields, `check_playlist` groups +
   tests in `test_library_tools.py`). Commit.
4. Playlist page. Commit.

Steps 2 and 3-4 are independent after step 1.

## Results log

| Step | Commit | Tests | Notes |
| --- | --- | --- | --- |
