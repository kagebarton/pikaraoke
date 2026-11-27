# Artist-only search: lift the act's official videos

Model: Claude Sonnet 5.5 (spec by Opus)

Branch `artist_search` off `dev` at `cb3ea32a`, worktree `.claude/worktrees/artist_search`
(inside the main checkout, gitignored via `.claude/`). Work and run everything from the
worktree. The 20 new captures are already committed on this branch (Fixtures, below); do not
re-capture them.

Ranking history, only if a ruling's background matters: `git show
archive/search_official_captions:plans/search-official-captions.md` ("Ranking rules",
"Fixtures"). The rule numbers below are new to this plan.

## Goal

A search for an act's name alone ("backstreet boys") badges and lifts nothing, while "backstreet
boys i want it that way" works. Ken's goal (2026-11-27): every search nudges the user towards
the official videos.

Cause, measured on `dev`: in "Backstreet Boys - I Want It That Way (Official HD Video)" the left
side holds every query word and the right side does not, so `_separated_artists` takes the left
side for the song ("Song - Artist") and credits `iwantitthatway` as the act. Each of the act's
videos then votes for its own song name, one credit each, nothing reaches `_MIN_CREDITS`, and
`originals` is empty. The vote threshold is not the fault: read the right way round (rules 1
and 2), the act gets 12 to 28 trusted credits on the 17 act searches below.

## Decisions (Ken, 2026-11-27)

1. **Lift and badge**, as in a song search: the act's official videos move above the fan mixes,
   lyric and karaoke uploads, in YouTube's order. Fan, lyric and karaoke rows stay unbadged and
   keep YouTube's order below. No ordering special case.
2. **Plain titles count.** In an artist search, the song a title names counts as explained, so
   "Taylor Swift - Blank Space" on her channel lifts. Brackets must still say what they are.
   Accepted cost: the 2 wrong lifts in Measurements, both through the existing "from"/"with"
   bracket hole.
3. **Channel rows leave the results.** A search can return the act's channel itself as a row
   ("Rick Astley", "BLACKPINK"). It is not shown as a card.
4. **Exact act name only.** "adele", "the weeknd", "simon and garfunkel". "adele songs" and
   "queen greatest hits" stay as they are today, logged in `plans/open-issues.md` at landing.

Gate (Ken): 0 of the 50 captured searches and 0 of the 1146 channels change for any query that
names a song (method as `plans/search-phone.md` on `search_phone`, Results row 1).

Not taken (Opus, measured): lowering `_MIN_CREDITS` to 1. The threshold is not the cause, and at
1 a single verified lyric or karaoke upload would decide who the original is.

## What exists (checked 2026-11-27 on `dev` at `cb3ea32a`)

- `pikaraoke/lib/official_rank.py`: `_MIN_CREDITS = 2` (:27); `Acts` (:80, `originals`,
  `record_words`, `has_video`); `_separated_artists` (:155, the song-first flip at :167);
  `_title_artists` (:193); `_credited_artists` (:197); `_row_names` (:206); `_pick_originals`
  (:214); `_is_own_channel` (:260); `_is_another_cast_on_a_label` (:292); `_says_what_it_is`
  (:307); `_lift` (:320, the "other" tier at :333-335); `read_first_page` (:356).
- `pikaraoke/lib/youtube_dl.py`: `SearchResult` (:204, frozen dataclass), `_parse_search_line`
  (:219), `get_search_results` (:242, `ytsearch{count}`, flat).
- `pikaraoke/routes/search.py`: `PAGE_SIZE = 30` (:38); `_YT_ID_RE` (:41, used by
  `caption_check` :170 and `lyrics_select` :248); `search()` (:113, fetches 30, `show_more =
  len(results) >= PAGE_SIZE`); `search_more()` (:139, fetches 60, votes over `results[:30]`,
  returns cards for `results[30:]`).
- Tests: `tests/unit/test_official_rank.py` (`_load`, `_LIFTED` and friends),
  `tests/unit/test_search_render.py` (`/search` and `/search/more` with `get_search_results`
  patched; every fake ID is 11 characters, including `_ids()`'s `f"{i:a>11}"`),
  `tests/unit/test_youtube_dl.py`.
- Today a channel row is shown as a card. Its URL is `https://www.youtube.com/channel/UC…`, and
  `build_ytdl_download_command` has no `--no-playlist`, so downloading it would likely fetch
  every upload on the channel (not tried).

## Design

### Rule 1: an act search

`read_first_page`, after its non-Latin guard and before the vote, decides whether the query is
an act's name. It is when at least `_MIN_CREDITS` rows of the page come from the query's own
channel: `_is_own_channel(row, {_compact(query)})`. That test already requires a trusted row (a
verified channel or an art track). It compares the channel name stripped of " - Topic", the
noise words, a trailing VEVO/Music/Official/TV/Video(s)/Show and a leading "the" with the whole
query minus its leading "the". So "Queen Official", "EminemMusic", "The Weeknd", "journey",
"Simon & Garfunkel" and "Céline Dion" all answer their names.

New field `Acts.act_search: bool = False`. A helper `_is_act_search(results, query_words)` holds
the count. A song's name is no channel's, so a search that names a song never qualifies: 0 of
the 50 captures. An act whose page has no own-channel rows is not an act search and is read as
today ("bts": HYBE LABELS; its quoted titles already credit `bts`).

`_MIN_CREDITS`'s comment becomes: "An act needs this many trusted credits to be an original,
and a query this many rows from its own channel to be an act's name."

### Rule 2: in an act search, every title reads "Act - Song"

`_separated_artists` never takes the song-first reading in an act search: the left side of "A -
B" is the act. Add `song_first = not act_search and …` at :167. Thread an explicit `act_search:
bool` parameter through `_pick_originals`, `_credited_artists`, `_row_names`, `_title_artists`
and `_separated_artists`. The vote passes the flag `read_first_page` decided, and `_lift` passes
`acts.act_search`.

Why: the query is the act, so the side that holds it is the act's name. Without this, a label
row is credited to its song: DisneyMusicVEVO's "Idina Menzel - Let It Go (from Frozen)
(Official Video)" credits `letitgo` today. A "Song - Act" title in an act search credits the
song and lifts nothing. Reading whichever side holds the query as the act was tried and
rejected: it credits "AMRIT MAAN - JOURNEY" to `journey` and lifts it from Speed Records as the
original.

### Rule 3: in an act search, no other act lifts

`_lift` never takes the "other" tier in an act search: `found = not is_audio and not
acts.act_search and _is_another_cast_on_a_label(…)`. With no song named, "another cast of the
song" is any label upload whose title holds the act's name. Speed Records' "AMRIT MAAN - JOURNEY
(Official Video) | …" lifts for "journey" on `dev` today.

### Rule 4: in an act search, the song a title names explains it (decision 2)

New helper `_named_song(title: str) -> str`, the song a title names after its act:
- Drop brackets (`_BRACKETED`), then split on `_SEPARATOR`, keeping the sides that have words.
- With two or more sides, take the second. If it holds a quote (`_QUOTED`), keep only the
  quoted text.
- With one side, take the quote in it if there is one; otherwise return "".

In an act search, `_says_what_it_is` adds `_words(_named_song(title))` to the query words it
passes to `_unexplained`. Only that last test changes. The early passes for "says official",
"says version" and marks stand, and so does the record's own title.

- Passes: "Taylor Swift - Blank Space", "Eminem - Rap God (Explicit)", "ABBA - When All Is Said
  And Done (Video)".
- Still fails on its bracket: "Adele - Send My Love (To Your New Lover)", "The Beatles - Here
  Comes The Sun (2019 Mix)", "Queen - Killer Queen (Top Of The Pops, 1974)", "Queen - Greatest
  Hits (1) [1 hour long]".
- Fails on its words outside the quote: "BLACKPINK - 'Lovesick Girls' DANCE PRACTICE VIDEO"
  ("dance practice").

`_is_the_song` needs no change. An act search has no song words, because every query word sits
inside the credited act's name, so any title of the act is "the song". That is today's code
path whenever the query is all act.

### Rule 5: channel rows leave the results (decision 3)

- `youtube_dl.py`: `VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")`, moved here from
  `routes/search.py`'s `_YT_ID_RE`. Its two uses there become `VIDEO_ID_RE.fullmatch(yt_id)`:
  one pattern, not a second copy. `fullmatch` also refuses an ID with a trailing newline, which
  `^…$` with `match` let through.
- `SearchResult.is_video`, a property: `VIDEO_ID_RE.fullmatch(self.id) is not None`. A channel's
  ID is 24 characters (`UC…`); a playlist's is longer than 11.
- `routes/search.py`: `_videos(results)` keeps the rows that are videos.
  - `/search` votes and ranks `_videos(results)`. `show_more` still counts the fetched rows
    (`len(results) >= PAGE_SIZE`), so a dropped row does not hide Show more.
  - `/search/more` slices first, then drops: `read_first_page(_videos(results[:PAGE_SIZE]), …)`
    and `_search_rows(…, _videos(results[PAGE_SIZE:]), …)`. Both routes vote over the same rows
    and no row is skipped between pages.
- Not in `_parse_search_line` or `get_search_results`: either would make a 30-row fetch return
  29, hide Show more, and shift `/search/more`'s second page by one row (fetched row 31 never
  shown).

### Module docstring

After "Another act's video lifts only from a label channel, after the original's (a film song's
second cast).", insert: "A query that is an act's name alone (its own channel answers it twice)
names no song: every title reads "Act - Song", any of the act's videos is the song, the song a
title names explains the title, and no other act lifts." Then change "Every rule errs toward
lifting nothing, because a miss costs only YouTube's order." to "Every other rule errs toward
lifting nothing, because a miss costs only YouTube's order." `Acts`'s docstring gains "and
whether the query is an act's name".

## Fixtures

These 20 files were added to `tests/unit/data/youtube_search/` in this branch's first commit.
They are live `ytsearch30` captures from 2026-11-27 on the VM (yt-dlp 2026.11.23), cut to the
existing fields (`id, url, title, channel, uploader, channel_is_verified, duration,
description[:40]`). The file stem is the query with `_` for spaces. `the_beatles.jsonl` is a
second fetch: the first came back with no channel fields on any row (open issue "YouTube
sometimes drops the channel fields").

Positions are 1-based lines of the capture file, counted before the channel row is dropped.
"Videos lifted" lists the badged videos in lifted order, which is YouTube's order. Audio is
badged in place, and lifted first only where no video lifts (Simon & Garfunkel). "Badged on dev"
is the count of badged rows on `cb3ea32a`. Every capture is ranked over its 30 rows, as
`/search` does. Produced by the Opus prototype (Measurements); the build must reproduce it
exactly.

| Capture | Act search | Originals | Videos lifted, in order (positions) | Audio badged (positions) | Badged on dev |
|---|---|---|---|---|---|
| `abba.jsonl` | yes | abba | 18: 2 3 5 6 7 10 11 12 16 17 18 19 20 21 23 25 27 28 | 2: 22 26 | 2 |
| `adele.jsonl` | yes | adele | 8: 2 6 12 15 18 19 23 28 | 3: 14 16 30 | 4 |
| `backstreet_boys.jsonl` | yes | backstreetboys | 20: 3 4 5 7 8 9 10 11 12 13 15 16 17 18 21 23 24 25 26 30 | 1: 27 | 0 |
| `blackpink.jsonl` (row 29 dropped) | yes | blackpink | 13: 3 5 6 8 11 12 14 16 17 19 21 24 28 | 0: - | 0 |
| `bts.jsonl` | no | bts | 13: 1 4 7 12 13 14 15 18 20 21 22 25 30 | 0: - | 13 |
| `celine_dion.jsonl` | yes | celinedion | 11: 1 2 11 12 14 15 16 18 20 28 29 | 3: 25 26 27 | 0 |
| `ed_sheeran.jsonl` | yes | edsheeran | 18: 2 3 5 7 8 9 12 13 14 15 18 19 20 22 23 27 28 29 | 0: - | 0 |
| `eminem.jsonl` | yes | eminem | 25: 1 2 3 4 5 6 7 9 10 12 13 15 16 17 18 19 20 21 22 23 25 27 28 29 30 | 0: - | 0 |
| `frozen.jsonl` | no | idinamenzel | 0: - | 0: - | 0 |
| `idina_menzel.jsonl` | yes | idinamenzel | 5: 7 12 14 17 30 | 0: - | 1 |
| `journey.jsonl` | yes | journey | 12: 3 6 8 9 10 11 13 14 15 19 23 28 | 4: 2 20 21 24 | 1 |
| `justin_timberlake.jsonl` | yes | justintimberlake | 16: 8 9 10 12 13 14 15 16 18 19 21 22 25 27 29 30 | 1: 17 | 0 |
| `lady_gaga.jsonl` | yes | ladygaga | 22: 2 3 4 5 6 7 8 9 10 11 14 15 16 19 20 21 22 25 26 27 28 30 | 2: 13 17 | 0 |
| `moana.jsonl` | no | auliicravalho, dwaynejohnson | 1: 11 | 0: - | 1 |
| `queen.jsonl` | yes | queen | 18: 2 3 7 10 11 12 13 15 16 18 20 21 24 25 27 28 29 30 | 0: - | 0 |
| `rick_astley.jsonl` (row 3 dropped) | yes | rickastley | 17: 1 2 7 9 10 11 12 13 14 15 17 21 22 23 24 26 27 | 1: 25 | 0 |
| `simon_and_garfunkel.jsonl` | yes | simonandgarfunkel | 0: - | 16: 8 9 11 12 13 15 16 17 18 20 22 23 24 25 26 29 | 7 |
| `taylor_swift.jsonl` | yes | taylorswift | 18: 3 6 9 10 11 12 13 15 18 19 21 22 23 24 25 26 27 29 | 0: - | 0 |
| `the_beatles.jsonl` | yes | thebeatles | 14: 8 11 12 13 14 15 17 20 21 23 24 25 26 27 | 2: 9 16 | 8 |
| `the_weeknd.jsonl` | yes | theweeknd | 18: 1 2 3 4 6 7 8 11 14 15 16 17 18 20 23 25 26 30 | 6: 9 21 24 27 28 29 | 0 |

Rows the tests name (file, position, ID, title, channel):

| File | Pos | ID | Title | Channel | Expected |
|---|---|---|---|---|---|
| `backstreet_boys` | 1 | `6lmXkezVBI8` | Best of Backstreet Boys \| Backstreet Boys Greatest Hits Full Album Playlist 2025… | Timeless Love Songs | unbadged, below the 20 videos |
| `idina_menzel` | 7 | `YVVTZgwYwVo` | Idina Menzel - Let It Go (from Frozen) (Official Video) | DisneyMusicVEVO | video, lifted first (an original's, rule 2) |
| `journey` | 18 | `tGbKhMg0ijA` | AMRIT MAAN - JOURNEY (Official Video) \| … | Speed Records | unbadged (rule 3); badged video on dev |
| `journey` | 2 | `1k8craCGpgs` | Journey - Don't Stop Believin' (Official Audio) | journey | audio, keeps its place |
| `taylor_swift` | 9 | `e-ORhEE9VVg` | Taylor Swift - Blank Space | Taylor Swift | video (rule 4) |
| `eminem` | 1 | `xFYQQPAOz7Y` | Eminem - Lose Yourself | EminemMusic | video (rule 4) |
| `abba` | 11 | `BshxCIjNEjY` | ABBA - Super Trouper | ABBA | video (rule 4) |
| `the_beatles` | 14 | `2Q_ZzBGPdqE` | The Beatles - Help! | The Beatles | video (rule 4) |
| `adele` | 15 | `0put0_a--Ng` | Adele - Make You Feel My Love (Official Video) | XL Recordings | video, 4th in YouTube's order among Adele's (an original's, not the "other" tier) |
| `adele` | 7 | `fk4BbF7B29w` | Adele - Send My Love (To Your New Lover) | Adele | unbadged (bracket unexplained) |
| `adele` | 4 | `X-yIEMduRXk` | Adele - Easy On Me (Official Lyric Video) | Adele | unbadged (mark) |
| `queen` | 1, 4 | `j440-D5JhjI`, `_Uu12zY01ts` | Queen - Greatest Hits (2) [1 hour 20 minutes long]; (1) [1 hour long] | Queen Official | unbadged |
| `queen` | 9 | `2ZBtPf7FOoM` | Queen - Killer Queen (Top Of The Pops, 1974) | Queen Official | unbadged |
| `blackpink` | 27 | `YxksUfnuEbI` | BLACKPINK - 'Lovesick Girls' DANCE PRACTICE VIDEO | BLACKPINK | unbadged (outside the quote) |
| `blackpink` | 28 | `Is0iob8lz4w` | BLACKPINK - '24/365 with BLACKPINK' EP.12 | BLACKPINK | video: known wrong ("with" drops to the segment end) |
| `celine_dion` | 20 | `gMOovDrWWiI` | Céline Dion - Because You Loved Me (from "These Are Special Times" TV Special) | Céline Dion | video: known wrong ("from" drops to the bracket end) |
| `rick_astley` | 3 | `UCuAXFkgsw1L7xaCfnd5JJOw` | Rick Astley (a channel row, `/channel/` URL) | Rick Astley | not a card (rule 5); badged video if it reached the ranking |
| `blackpink` | 29 | `UCOmHUn--16B90oW2L6FRR3A` | BLACKPINK (a channel row) | BLACKPINK | not a card (rule 5) |

Other badges in the table, recorded and not judged: `rick_astley` 10, 13 and 21 are
"【日本語字幕】Rick Astley - …" uploads on his own channel (10, `RrESvSRNpeo`, is already lifted
by the existing "never gonna give you up" fixture). `celine_dion` 29 is "My Heart Will Go On
(1998 "These are Special Times" TV special) (Official HD Video)", lifted by its "Official HD
Video".

## Gate

A snapshot script in the session scratchpad (not committed). Run it on `cb3ea32a`'s code with
this branch's fixtures before any edit, again after commit A, and again after commit B. Diff each
run against the first.

- **Channels.** For every distinct channel in the 50 old captures (every file in
  `tests/unit/data/youtube_search/` except the 20 above) and in `tests/unit/data/genius_search/`
  (1146 distinct), record `official_rank._channel_artist`, `official_rank._channel_name` and
  `genius_query.channel_name`.
- **The 50 song searches.** Rank each one as the routes do. Rows via `_parse_search_line`, then
  `_videos` per page from commit A on (a no-op on these 50: none has a non-video row). Record
  `read_first_page(rows[:30], query)` (originals, record words, has-video), then
  `official_first(rows[:30], query, acts)` as `(id, kind)` pairs. For the captures with 60 rows,
  also record `official_first(rows[30:60], query, acts)` (54 ranked pages in all).
- **After B:** `act_search` is False on all 50.
- **Pass:** channels 0 of 1146 changed; the 50 captures' votes, orders and kinds 0 of 50 changed;
  the 20 new captures match the Fixtures table exactly (act search, originals, both position
  lists).
- **Anything else is a stop:** report it with the rows, and do not tune a rule to make it pass.

## Commits

Per-commit routine:
- `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed files>`.
- The unit suite: `/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit -q`.
- An import smoke of the changed modules.
- The gate (above).
- A read of `git diff --cached` against the commit's section, and the CLAUDE.md self-review.
- A Results row in a separate plan-only commit (`docs(plans): artist-search results, commit N`).

Tests ride with the code they check.

Already on the branch (Opus): `test(search): twenty artist-only search captures` (data only)
and this plan.

**A. `fix(search): a channel in the search results is not a card`.** Files:
`lib/youtube_dl.py`, `routes/search.py`, `tests/unit/test_youtube_dl.py`,
`tests/unit/test_search_render.py`. Rule 5.
- `test_youtube_dl.py`: `is_video` is true for an 11-character ID and false for a 24-character
  channel ID and a 34-character playlist ID (one parametrized test).
- `test_search_render.py`:
  - `/search`, with 30 fetched rows of which one is a channel row (ID `UC` plus 22 characters,
    URL `https://www.youtube.com/channel/<id>`): no card carries its ID or title, 29 cards
    render, and Show more is still offered.
  - `/search/more`, with 60 fetched rows and a channel row on the first page: the cards are
    exactly fetched rows 31-60, none skipped.
  - `/search/more`, with a channel row on the second page: that row has no card.
- The existing `caption_check` and `lyrics_select` ID tests pass unedited (11 accepted, 12
  rejected).

**B. `feat(search): an artist-only search lifts the act's official videos`.** Files:
`lib/official_rank.py`, `tests/unit/test_official_rank.py`. Rules 1-4 and the docstrings.
- `_load` keeps only `is_video` rows (a no-op for the 50 old captures; it drops `rick_astley`
  row 3 and `blackpink` row 29). The module docstring of the test file gains the 20 captures
  of 2026-11-27.
- `_ACT_SEARCHES`: one parametrized table over all 20 new captures, as the Fixtures table:
  query, act search, originals, video positions in lifted order, audio positions. A small
  helper maps positions (1-based lines of the raw capture) to IDs. Assert `read_first_page`'s
  `act_search` and `originals`, the kinds of every row, and the lifted order.
- Named tests, one behaviour each, on the rows in the second Fixtures table:
  - The label channel's video of the act lifts as the act's (`idina_menzel` 7).
  - No other act lifts in an act search (`journey` 18).
  - A plain title on the act's own channel lifts (`taylor_swift` 9, `eminem` 1).
  - A bracket must still say what it is (`adele` 7; `queen` 1, 4, 9).
  - Only a title's quoted song is explained (`blackpink` 27).
  - Known wrong lifts through a "from" or "with" bracket (`blackpink` 28, `celine_dion` 20),
    pinned so a fix of that hole shows here.
- `test_a_search_that_names_a_song_is_never_an_artist_search`: `act_search` is False for every
  old capture.
- Synthetic (with `_art`, `_row`-style helpers):
  - One row from the query's own channel is not an act search, two are.
  - In an act search a "Song - Act" title credits the song and is not badged.

Then **stop**, with both Results rows committed. Review due (CLAUDE.md Checkpoints): A and B
are multi-file and change the ranking rules.

## Not doing

- Lowering `_MIN_CREDITS` (Decisions).
- An act plus browsing words ("adele songs", "queen greatest hits", "taylor swift karaoke").
  Captured 2026-11-27 (scratchpad, not committed): the vote finds the act on each, and 0 rows
  are badged, because the extra word reads as a song word. Decision 4. Open-issues entry at
  landing.
- "Song - Act" titles in an act search. Song searches keep the open issue "A 'Song - Artist'
  title is read the wrong way round": the gate forbids changing song searches.
- The "from"/"with" bracket hole. Two new wrong lifts go through it (the table). Its open-issues
  entry gains them at landing.
- Sinking lyric, karaoke or fan rows (decision 1).
- Acts with no own channel on the page (`bts`) and film names (`frozen`, `moana`): not act
  searches, unchanged.
- The ranking's repeated work (open issue). Rule 1 adds one pass over 30 rows.
- The other 11-character patterns (`library_links.py`, `metadata_parser.py`): not touched.

## At landing (not Sonnet's)

- Cherry-pick the fixtures commit, A and B onto `dev`, in order. The plan stays on the branch.
- `search_phone` touches the same files. If it lands first, expect conflicts in:
  - `youtube_dl.py`: both add `import re`; `search_phone` also rewrites
    `get_youtube_id_from_url`.
  - `routes/search.py`: imports, and `_library_ids` around `_search_rows`.
  - `official_rank.py`: its `channel_words` import and `_channel_artist`; this branch edits
    neither, only nearby lines.

  Resolve by hand and re-run the gate.
- `plans/open-issues.md`, "Search results":
  - A new entry for act plus browsing words.
  - The two known wrong lifts added to the "from"/"with" entry.
  - A line on the "Song - Artist" entry that act searches now read "Act - Song".
  - The `the_beatles` empty fetch added to the dropped-channel-fields entry.

## Manual checks (Ken, on a phone, after B)

1. "backstreet boys": the first cards are the band's own videos, badged "Official video"; the
   "Best of" mixes come after them.
2. "taylor swift": "Blank Space" is badged.
3. "rick astley": no card for his channel; Show more is offered and its cards follow on.
4. "journey": the Punjabi "JOURNEY" video has no badge.
5. A song search, "adele hello": unchanged, the official video first.

## Measurements (Opus, 2026-11-27)

Live captures and prototypes in
`/tmp/claude-1000/-home-ken-pikaraoke/5d85b894-e843-4f80-9459-971b31f1149a/scratchpad/`
(`captures/`, `captures_extra/`, `proto/`; not committed). Every variant monkeypatched `dev`'s
`official_rank` at `cb3ea32a`.

| Variant | What it changes | 50 old captures changed | 20 new captures changed | Seen wrong |
|---|---|---|---|---|
| Per-row | the song-first flip is skipped when the left side is the row's own channel | 0 | 16 | "AMRIT MAAN - JOURNEY" (Speed Records) lifted as another act; channel rows "Rick Astley", "BLACKPINK" lifted as videos; DisneyMusicVEVO's "Idina Menzel - Let It Go" lifted as another act, after her own |
| Page-level (rules 1-3) | act search by own-channel count; no flip; no other tier; channel rows dropped | 0 | 16 | none of the above |
| Rules 1-4 (this plan) | plus the named song explains the title | 0 | 17 (`the_beatles` too) | +47 badged videos over rules 1-3, of which 2 wrong (`blackpink` 28, `celine_dion` 20) |

Act search is on for 0 of the 50 old captures, and off for 3 of the 20 new ones (`bts`,
`frozen`, `moana`). The rejected rule 2 variant (whichever side holds the whole query is the
act, `holdside.py`) credits `journey` 18 to `journey` and badges it as the original's video. On the 17 act searches, rules 1-3 leave 109 of the act's rows from its own channel, a
label channel or an art track unbadged: 49 for a mark (lyric, live, concert, performance, making
of and the like), 60 for unexplained words. Rule 4 badges 47 of the 60. Top vote per act search
under rules 1-2: abba 26, adele 18, backstreet boys 25, blackpink 17, celine dion 23, ed sheeran
25, eminem 28, idina menzel 12, journey 24, justin timberlake 22, lady gaga 28, queen 23, rick
astley 21, simon and garfunkel 17, taylor swift 24, the beatles 22, the weeknd 27.

## Results log

| Commit | Hash | Suite | Notes |
|---|---|---|---|
| A | `c4168896` | 4617 passed (`tests/unit`); `test_youtube_dl.py` +6 (`is_video`: 11-character IDs, a dash-led one, a 24-character channel ID, a 34-character playlist ID, 10 characters, a trailing newline), `test_search_render.py` +3 (`/search`: 30 fetched rows with one channel row gives 29 cards, no card or text with its ID, Show more offered; `/search/more`: a channel row on page one leaves cards exactly fetched rows 31-60, a channel row on page two gets no card); the existing `caption_check` and `lyrics_select` ID tests unedited | Gate, scripts `/tmp/claude-1000/-home-ken-pikaraoke/965d7a19-29d2-4fa5-8786-3bd6c5104837/scratchpad/gate_snapshot.py` and `gate_diff.py` (not committed). Base run on `61dbaa99` (`dev`'s code, before any edit) twice, byte-identical; its "badged" count for the 20 new captures equals the Fixtures table's "Badged on dev" column on 20 of 20. Base: 1146 distinct channels (50 old captures plus `genius_search`), 50 captures, 54 ranked pages (50 first pages, 4 second pages). After A: `official_rank._channel_artist`, `_channel_name` and `genius_query.channel_name` 0 of 1146 changed; votes, orders and kinds 0 of 50 captures changed (54 pages); non-video rows in the 50 old captures 0; rows dropped from the 20 new captures: `blackpink` 29 and `rick_astley` 3, no others. `act_search` does not exist yet. Mutation check (not committed): `_videos` keeping every row fails 2 tests, `/search/more` dropping before it slices fails 1, `show_more` counting the videos fails 1. Pre-commit clean on the four files (Black reformatted `routes/search.py` once). |
| B | `3324be12` | 4687 passed (`tests/unit`); `test_official_rank.py` 221 -> 291 (+70: `_ACT_SEARCHES` run by two tests, 20 each: act search, originals, kinds of every badged row, lifted order, and everything else in YouTube's order; named rows 15: label video lifts as the act's own x2, `journey` 18 x1, plain title x4, bracket must say what it is x5, quoted song x1, known wrong from/with x2; every old capture is not an act search x1; own-channel count 5 cases; synthetic "Act - Song" x1 and "Song - Act" x1; `_named_song` 7 cases) | Gate, same scripts as row A (`/tmp/claude-1000/-home-ken-pikaraoke/965d7a19-29d2-4fa5-8786-3bd6c5104837/scratchpad/gate_snapshot.py`, `gate_diff.py`, not committed), run against the base snapshot of `61dbaa99` after the code and again on the final files (output byte-identical across four runs of the code, the last after the test files and docstrings settled). `_channel_artist`, `_channel_name` and `genius_query.channel_name` 0 of 1146 changed; votes, orders and kinds 0 of 50 captures changed (54 ranked pages); `act_search` true on 0 of the 50; the 20 new captures match the Fixtures table on 20 of 20 (act search, originals, video positions in lifted order, audio positions), on the first run, with no rule edited to get there. The table's "Badged on dev" column equals the base run's badged count on 20 of 20. Checker itself: a tampered copy (one video position dropped, one `act_search` flipped, one old-capture kind changed, one channel name changed) is reported on each, 18 of 20 then match. Named rows: `journey` 18 (`tGbKhMg0ijA`) is `None` and is `"video"` under `replace(acts, act_search=False)`, so the test pins rule 3 itself; `idina_menzel` 7 is first of the lifted videos and `adele` 15 is fourth, in YouTube's order among Adele's. Mutation check (not committed), `test_official_rank.py` failures: no song-first guard 43, other tier allowed 3, named song not explained 26, own-channel threshold of 1 row 2, `act_search` never set 51. Two things beyond the plan text: `_sides(title)` (the side split, brackets dropped) is shared by `_separated_artists` and `_named_song` so the expression has one copy; `read_first_page`'s docstring names the act-search decision as its first step. `_ACT_SEARCHES`'s `eminem` row is written one position per line (Black's split of a 25-number list). Pre-commit clean on both files (Black reformatted the test file once). |
