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

## Addendum: review fixes (2026-10-28)

Executor: Claude Sonnet 5.5. Same branch, `similar_song_flag`, on top of
`141749f`.

`/code-review` of `c543c02..141749f` returned 10 findings. Ken ruled on them
the same day:

- **Every video starts ticked**, in both kinds of group. A group is a warning,
  never a default to skip.
- **Fix the rules** for the misses (rules A-D below), written here first.
- **Small fixes:** the `$.map` row bug and the search page's ID exclusion. The
  quote and fullwidth-bar fixes are rules C and D.
- **Not done:** caching the library index. Last.fm is still out.

### Rules A-D (`song_match.py`)

Prototyped in a copy of `song_match.py` (scratchpad
`/tmp/claude-1000/-home-ken-projects-pikaraoke/b71840c8-bcb9-4da3-b950-cba2d727ff9e/scratchpad/addendum/song_match_new.py`;
it may be gone, and this section is the source of truth). All 29 tests in
`test_song_match.py` pass under A-D unchanged.

**A. The lead rule ignores a shared lead only when the titles differ
elsewhere.** A part that leads both titles is ignored only when *each* title
has a segment the other lacks. Segments here are every non-empty normalized
segment, short ones included. A segment that normalizes to nothing (pure
noise: `Karaoke`, `Official Video`) doesn't count. This needs a new
`TitleParts.segments: frozenset[str]` (for a quoted title, the kept quotes).

```python
and not (part == a.lead == b.lead and a.segments - b.segments and b.segments - a.segments)
```

Why short segments count: in `Snow Patrol - Run` the segment "run" is dropped
from `parts` (under 4 chars). If it were also dropped from the comparison, the
title would look like the bare artist and match every Snow Patrol song.

**B. A part is common (artist or film) when it appears alongside 3+
*different* other-part sets, not in 3+ titles.** For each title containing the
part, take the set of that title's other parts. Skip the empty set and count
the distinct sets. Keep the threshold, `COMMON_PART_COUNT = 3`. Keep the split
from step 3:

- title vs title counts over library + playlist, as a union of the sets, not a
  sum of counts;
- title vs library counts over the library only.

```python
def _count_parts(titles):
    seen = {}
    for title in titles:
        for part in title.parts:
            if others := title.parts - {part}:
                seen.setdefault(part, set()).add(others)
    return Counter({part: len(sets) for part, sets in seen.items()})
# similar_groups: playlist_frequency = _count_parts([*library.titles.values(), *parsed])
```

B only ever makes a part *less* common than today, never more: identical
uploads of one song collapse to one set, and a title holding the part alone
adds nothing. So it can only add matches.

**C. A quote closes only with its own kind of mark, runs to the last closer
in its segment, and is ignored when shorter than 4 chars.**

- Closers pair with openers: `'...'`, `"..."`, `‘...’`, `“...”`.
- The match is greedy and found per separator segment, so it never crosses a
  ` - `.
- A quote that normalizes to under 4 chars is not a quote; the title is parsed
  by segments.

```python
_QUOTED = re.compile(r"(?<!\w)(?:'(.+)'|\"(.+)\"|‘(.+)’|“(.+)”)(?!\w)")
segments = _SEPARATOR.split(_BRACKETED.sub(" ", title))
quoted = [_normalize("".join(m)) for seg in segments for m in _QUOTED.findall(seg)]
quoted = [q for q in quoted if len(q) >= MIN_PART_LENGTH]
```

Timed on pathological titles (6000 chars of quotes and apostrophes): under
3 ms each.

**D. `_SEPARATOR` also splits on the fullwidth bar `｜` (U+FF5C)**, which
`metadata_parser._split_query_parts` already handles.

Comments and docstrings to update: `COMMON_PART_COUNT`, `TitleParts.lead`,
`similar_groups` (frequency wording). Update the comment on
`test_titles_meeting_the_same_library_song_group_though_the_playlist_hides_their_match`
too: under B the two Mirrors uploads also match each other directly. Rename it
if the name no longer holds.

Prototype results (`old` = `141749f`). Each row is a test case for step 5.
Library titles carry a `---ID` suffix in the test.

| # | Case | Library | Title(s) | old | A-D |
| --- | --- | --- | --- | --- | --- |
| 1 | F3, no separator (A) | Bohemian Rhapsody | Bohemian Rhapsody (Official Video) | miss | match |
| 2 | F3, noise segment (A) | Shape of You - Ed Sheeran | Shape of You \| Karaoke | miss | match |
| 3 | A with a common artist | 3 Justin Timberlake songs + Mirrors - Justin Timberlake (Lyrics) | Mirrors - Justin Timberlake [HD] | 1 of 2 Mirrors | both Mirrors |
| 4 | A guard: short song name | Snow Patrol - Chasing Cars | Snow Patrol - Run | none | none |
| 5 | A: short song name, same song | Snow Patrol - Run | Snow Patrol - Run (Official Video) | miss | match |
| 6 | A guard: two songs, one artist | Backstreet Boys - Incomplete | Backstreet Boys - Larger Than Life | none | none |
| 7 | F4, playlist only (B) | — | Shape of You - Ed Sheeran; Ed Sheeran - Shape of You (Lyrics); Shape of You \| Karaoke | [0,1] on "ed sheeran" | [0,1,2] on "shape of you" |
| 8 | B guard: artist-heavy playlist | — | Mirrors / Selfish / Rock Your Body - Justin Timberlake | none | none |
| 9 | F6, double quote (C) | Guns N' Roses - Sweet Child O' Mine | Guns N' Roses "Sweet Child O' Mine" (Official) | miss | match |
| 10 | F6, single quote (C) | Bobby Day - Rockin' Robin | Bobby Day 'Rockin' Robin' | miss | match |
| 11 | C: `'n'` is not a quote | KISS - Rock 'n' Roll All Nite | Kiss 'Rock 'n' Roll All Nite' | miss (library title had no parts) | match |
| 12 | C: curly quotes | — | parse `“Rockin’ Robin” - Bobby Day` | {rockin} | {rockin robin} |
| 13 | F7 (D) | Ed Sheeran - Perfect | Perfect ｜ Ed Sheeran | miss | match |
| 14 | No regression | the real 33-song library vs itself | — | AWNW x2, For Good x2 | same |
| 15 | No regression | both A Whole New World copies | Aladdin - A Whole New World (Lyrics) (+ Disney - ... \| Karaoke) | both copies | same |

Still unchanged, by design (log them; no more rules):

- **F1 and F2, the same-artist ambiguity.** "Perfect - Ed Sheeran" vs
  "Shape of You - Ed Sheeran" has the same structure as "Mena Massoud - A Whole
  New World" vs "ZAYN - A Whole New World": a shared part, every other part
  different. Titles alone can't tell an artist with several songs from a song
  with several artists. The obvious fix for F1 was tried: count the playlist in
  title-vs-library matches. It clears F1 but loses both rows of case 15 and
  fails `test_a_title_groups_with_the_library_songs_it_looks_like`. Because
  everything starts ticked, such a group is noise, not a dropped song, and its
  heading names the artist.
- `'Run' - Snow Patrol` (quote too short, so parsed by segments) matches Snow
  Patrol's other songs: same family as F2.
- A medley `'Song A' & 'Song B'` is one part (C is greedy).
- `Let It Go - Frozen` vs `Let It Go - Idina Menzel`: both titles have a
  segment the other lacks, so A still ignores the shared lead. Non-Latin
  titles. The index is rebuilt on every request.

Found by the second review (2026-10-28), also by design (Ken: log, no rules):

- A quoted title has one part, so B never counts it as common: three
  `'Frozen' ...` songs in the library and `'Frozen' Let It Go` matches all
  three (it matched none before B).
- B stops duplicate uploads counting toward an artist, so F1 fires more:
  library `Adele - Hello`, `Adele - Hello (Lyrics)`, `Skyfall - Adele`, and
  `Rolling in the Deep - Adele` matches all three (none before B).
- A bare artist title matches that artist's songs: `Ed Sheeran (Official
  Video)` vs `Ed Sheeran - Perfect` / `- Happier` (none before A). It has the
  same shape as `Run` vs `Snow Patrol - Run`, which A exists to match.
- C runs to the last closer, so an apostrophe after the quote joins it:
  `'Daydream' The Lovin' Spoonful` -> `{daydream lovin}`, missing `The Lovin'
  Spoonful - Daydream` (matched before C). Mirror image of `'Rockin' Robin'`.
- Pre-existing, unchanged by A-D: three song-first covers (`Shape of You -
  Boyce Avenue` / `- Madilyn Bailey` / `- Ed Sheeran`) make the song common and
  never group; `Snow Patrol - Run - Live Lounge` vs `Snow Patrol - Run | Sing
  King` misses (short song name, both titles have an extra segment).

### Playlist page (`playlist.html`)

- Delete `startUnticked()` and its call. `check()` already resets
  `state.left = {}` before the request, so nothing starts left out.
- Rewrite the `pl-tip-similar` note: drop the sentences about what starts
  ticked. Something like: "These look like the same song, judged by title
  only. Untick any you don't want."
- Line 186: `$.map(fresh, newRow)` passes the index as `withDetails`. Use
  `$.map(fresh, function (video) { return newRow(video); })`, the same shape
  as its neighbours.
- `test_library_routes.py:2058` asserts the `startUnticked` call: delete that
  assertion. Add one for the `$.map` fix in the file's style if it kills the
  bug's mutant.

### Search page (`routes/search.py`)

`_library_copies` drops songs that a result matches by ID using the
`find_by_id` path (`existing_path`). `find_by_id` sees only top-level
`---ID.` files, so a library copy saved as `Title [ID].mp4`, or in a subfolder,
shows in the note next to its own result. Instead, drop library songs whose
`extract_youtube_id(path)` (`metadata_parser`) is the ID of any result (`r[2]`
of the result row). Out of scope: the result row itself still uses
`find_by_id` (upstream) and may offer a download for such a file. Test in
`test_search_render.py`: a library file `Title [ID].mp4` and a result with
that ID produce no note.

### Order

5. Rules A-D + the table's cases in `test_song_match.py`. Mutation-check each
   rule (remove it, watch its test fail). One commit.
6. Playlist page: all ticked, the note text, the `$.map` fix. One commit.
7. Search ID exclusion + render test. One commit.

Steps 6 and 7 are independent of 5 and of each other. Write a Results log row
per commit. Translation catalogs stay untouched, as before. Step 5 rewrites
matching logic: after step 7, flag a `/code-review` as due and don't run it.

## Results log

| Step | Commit | Tests | Notes |
| --- | --- | --- | --- |
| 0 | `96af03a` (base) | 537 | Branched `similar_song_flag` off `custom_lyrics`, not `dev` (Ken's call: `custom_lyrics` was not on `dev`, so the Base section's wait did not happen). Baseline = `test_library_tools` + `test_library_routes` + `test_search*`. |
| 1 | `c543c02` | 563 | +26 in `test_song_match.py`, on the real 33-song library. Prototype scripts were still on disk; output matched row for row apart from the two rule fixes. Rule 1 (quote outside brackets only): `Frozen - Let It Go` now returns Let It Go alone. Rule 3 (quote is the song name): Defying Gravity x Popular no longer pair; the only library pairs are A Whole New World x2 and For Good x2. Each rule was mutation-checked (removed, test fails). Library titles are parsed with `filename_from_path(tidy=False)`: tidy turns yt-dlp's ` _ ` into spaces, which erased the Mulan and Movieclips separators. Quote detection needs a non-word char before the opener and after the closer, so `Don't Stop Believin'` is not a quote (curly vs straight apostrophes would otherwise differ). Observed limits, unchanged: (a) artist-trailing titles flag the artist's other library songs: `I Want It That Way - Backstreet Boys (Karaoke Version)` returns both Backstreet Boys songs; (b) non-Latin titles normalize to nothing and never match; (c) `group_similar` frequency counts library + playlist, so a playlist pair groups only when the song is not in the library, and three uploads never group; each still matches the library through `similar_songs`, so step 3 must union playlist videos that share a library hit. |
| 2 | `b1d49da` | 2552 (full suite; affected set 567) | +4 render tests in `test_search_render.py` (copies offered; none for an unrelated result; none for a song a result matches by ID; capped at 3), each mutation-checked. Route: helper `_library_copies` + one context value. Index build + 10 result lookups measured on a synthetic 5000-song library: 64 ms + 17 ms. Not driven in a real browser (search needs live yt-dlp); the click handler is the existing enqueue path with the file path read from the button. |
| 3 | `deb9ac6` | 2561 (full suite) | `read_playlist` passes `channel` (falls back to `uploader`) and `duration` (seconds; a non-number is `None`); `check_playlist` adds both per video and a top-level `groups` list: `{part, videos: [ids], songs: [{song, title}]}`. Deviations from the plan, both forced by the page's needs: (1) one top-level `groups` list instead of a per-video `similar` field, so a group lives in one place; (2) `group_similar` replaced by `similar_groups`, because the limit (c) from step 1 (a playlist pair of a song already in the library never grouped) is closed by linking videos to library songs inside the same union-find: two uploads that only meet through one library copy land in one group. Frequency: video-to-video counts library + playlist, video-to-library counts the library alone (as search does). Only `new` videos are grouped; a video already in the library shows as one of the group's `songs`. A video still downloading (`waiting`) is not in the library index, so a new twin of it is not flagged. Tied heading parts are all named (`justin timberlake / mirrors`), because a set has no order to pick by and string hashing is randomized per run (tests pass under 5 hash seeds). 11 new tests + updated exact-dict check; 8 mutants killed. 220 titles x 5000-song library: 349 ms. |
| 4 | `10fe590` | 2564 (full suite) | Page: "Possible duplicates (N)" section above "New" through `section()` with a new `pl-tip-similar` (i) note; one card per group headed by `part` (CSS-capitalized, so `Ed Sheeran / Shape Of You`); library copies via `listedRow` tagged "In library"; new videos via `newRow(video, true)` with channel, length (`m:ss` / `h:mm:ss`) and a "YouTube ↗" link. Ticks: `startUnticked()` seeds `state.left` after each check (library-matched group: none ticked; playlist-only group: first only). **Open choice, built as "only the first ticked"** and stated in the commit message; the whole rule is `startUnticked()`. Grouped videos keep status `new`, so `takenNew()` / the Go count are untouched; `add_playlist` unchanged. Pills: "N new" and the "New" section now count ungrouped videos only, so the pills split the playlist without overlap; the new pill uses `is-warning is-light`, the same yellow as "not processed" (plan said yellow; the text tells them apart). +3 page-script presence tests in `test_library_routes.py` (file's convention; 7 mutants killed after pinning the section guard and pill line). Behaviour verified separately in headless Chromium (throwaway script, not committed) against the real `LibraryTools` with `read_playlist` canned, 420px viewport: tick defaults, toggling, Go count 2->3->2->3->2, (i) note opens, a link click leaves the boxes alone, no page errors. Translation catalogs not touched (the playlist page's strings are in none; the repo regenerates them in batches). |
| 5 | `52327f8` | 2583 (full suite; `test_song_match` 29 -> 48) | Rules A-D as written in the addendum, ported by hand from the scratchpad prototype (the only code difference was `TitleParts.segments`, `_count_parts`, `_QUOTED`, `_SEPARATOR`, the `parse_title` quote branch, and `similar_groups`' frequency line). All 29 existing tests passed unchanged under A-D before any new test was added. **All 15 table rows reproduced as written; nothing stopped.** Rows 14 and 15 and row 8's titles are carried by existing tests (real library against itself; the Aladdin search; the artist-heavy playlist test); row 15 gains the `Disney - A Whole New World \| Karaoke` search as a parametrize entry. Added beyond the table: a quote under 4 chars is parsed by segments (`'Run' - Snow Patrol` -> `{snow patrol}`); quotes are found per segment (`'Defying Gravity' - Wicked 'Popular'` -> both); a quote closes only with its own kind of mark (`'Til Tuesday "Voices Carry"`); a bare title adds no partner to B's count; the same partner in library and playlist counts once; and two uploads that meet only through one library copy still group (see below). `test_titles_meeting_the_same_library_song_group_though_the_playlist_hides_their_match` renamed `test_two_uploads_of_a_library_song_group_with_it`: under B the two Mirrors uploads match each other directly, so the old premise (the playlist hides their match) no longer held. **Mutation check**, 12 mutants (A1-A4, B1-B3, C1-C4, D1): 10 killed on the first pass; 2 survived. B3 (`library.frequency + _count_parts(parsed)` instead of one union count): a search over 20 000 random small title sets found 700 where it changes the groups, so not equivalent; the test is `library = Shape of You - Sing King`, titles `Shape of You - Pop Hits`, `Shape of You`, `Shape of You \| Sing King` -> `[[0, 1, 2]]` (summed: `[[1, 2]]`). C1 (any closing mark closes any opener): killed by `'Til Tuesday "Voices Carry"`. A third check, outside the rules: removing the library as a bridge between titles (`root[find(second)] = find(first)` only for title-title edges) survived all tests, because the renamed Mirrors test no longer isolates it; added `Shape of You - Ed Sheeran` + `Shape of You - Sing King` against library `Ed Sheeran - Shape of You` (both lead with the song name so the lead rule keeps them apart; the library copy matches each) -> no groups without the library, `[0, 1]` with it; that mutant now fails. All 13 killed. `parse_title` on 6000-12 000 chars of quotes and apostrophes: 0.1-3.1 ms. **Unchanged by design, as the addendum lists:** F1 and F2 (a shared part with every other part different cannot tell an artist with several songs from a song with several artists); `'Run' - Snow Patrol` matches Snow Patrol's other songs (same family); a medley `'Song A' & 'Song B'` is one part; `Let It Go - Frozen` vs `Let It Go - Idina Menzel` still does not match; non-Latin titles; the index is rebuilt on every request. |
| 6 | `00ede86` | 2584 (full suite) | `startUnticked()` and its call deleted (`check()` already sets `state.left = {}` before the request, so nothing is seeded); `pl-tip-similar` reads "These look like the same song, judged by title only. Untick any you don't want."; `$.map(fresh, newRow)` -> `$.map(fresh, function (video) { return newRow(video); })` (jQuery passes `(item, index)`, so every New row after the first got `withDetails` truthy). `test_library_routes.py`: the `startUnticked` assertion test is now `test_every_video_starts_ticked_and_grouped_ones_count_toward_the_button` (asserts `state.left` does not appear in the check's `.done` handler, and keeps the two lines about grouped videos counting toward the Go button); new `test_the_new_list_does_not_pass_the_index_as_the_details_flag`. Mutants: re-adding a `state.left = ...` line in `.done`, and the bare `newRow` callback; both killed. Driven in headless Chromium (throwaway script, not committed) against the real `LibraryTools` with `read_playlist` canned, 8 videos, 420px viewport: every box starts ticked, Go reads `Download 7` (4 grouped + 3 ungrouped), only group rows show channel/length/link, the three New rows show none, unticking one drops Go to `Download 6`, the (i) note shows the new text, no page errors. |
| 7 | `4efded4` | 2586 (full suite) | `_library_copies` drops library songs whose `extract_youtube_id(path)` is the ID of any result (`result[2]`), replacing the `find_by_id` path set. `extract_youtube_id` reads the basename's `---ID` or `[ID]` suffix, so a `Title [ID].mp4` file and a file in a subfolder are both excluded. +2 render tests (parametrized: `bracketed-id`, `subfolder`), where `find_by_id` finds nothing; the existing by-ID test still passes. Mutants: restoring the `find_by_id`-path exclusion (both new cases fail) and dropping the exclusion (three fail); both killed. Out of scope as planned: the result row itself still uses `find_by_id` and may offer a download for such a file. Not driven in a real browser (search needs live yt-dlp), as before. **`/code-review` is due** (step 5 rewrites matching logic) and was not run. |
| 8 | `90ff741` | 2588 (full suite) | Second review (3 axes, report only; 8 findings, verified by hand against the `141749f` matcher). Its one regression: step 7 dropped `[ID]` / subfolder files from the note while the row's `find_by_id` still missed them, so such a file showed nowhere. Ken: fix the row. `search()` now maps each song-list path's `extract_youtube_id` to the path and gives the row `library_ids.get(r[2])`; `find_by_id` no longer used by search. `_library_copies` unchanged. The parametrized `bracketed-id` / `subfolder` test now also asserts the row's own `data-file-path`; mock `find_by_id` / `download_path` removed. Against the `d71f304` route, 3 of the 8 render tests fail. Possible gap: a file on disk but not yet in the song list is no longer found by its row (`find_by_id` read the disk). |
| 9 | `0c43af1` | 2588 (full suite; `test_song_match` 48 -> 50) | Tidy-ups Ken picked. `parse_title` NFKC-folds the title before splitting; `｜` dropped from `_SEPARATOR`; fullwidth bar / hyphen / colon parametrized (all 3 fail without NFKC). Quoted titles get `segments=frozenset()` (only read beside a shared lead, and their lead is `""`); `_count_parts` docstring now says song-first covers make the song common. **Reusing the library's partner sets (Ken's third tidy-up) was built, then removed**: identical groups over 500 random cases, but 220 titles x 5000 songs measured 462 ms before vs 469 ms after; the library rescan is 26 ms of that and the rest is the title-vs-song comparisons, so the extra index field bought nothing. Second-review side effects logged above under "Found by the second review". |
