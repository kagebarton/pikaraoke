# Genius search: the spec

Model: Claude Sonnet 5.5 executes. Spec by Claude Fable 5.2, 2026-11-13; GATE G, the
executor rules and the Results log by Claude Opus 5.5, 2026-11-15, reviewed by Fable the
same day. GATE G is read by Opus, then Ken (Fable only if Opus is unsure which recording a
hit is, and only while Fable is available, to 2026-11-16: "Rulings on the gate", 5).

Status: **Phases 0-2 done 2026-11-16 (Results log rows 2-8); Phase 3 is next.** Does not
wait for `search_official_captions` (Ken, 2026-11-15). Ken ruled the review's four gate
questions on 2026-11-15 ("Rulings on the gate").

The evidence and the rulings behind every choice here are in `plans/genius-search-accuracy.md`
(the evaluation, closed; do not rerun it). The reference implementation is
`plans/genius-search-accuracy/run2/builder.py` with the replay loop in `run2/run.py`
(`replay`). The prototype settles any ambiguity in this spec's wording; it is not imported by
app code.

## What gets built

One module that reads a video title into parts, asks Genius a short ladder of queries, orders
the merged hits and says whether the first one is safe to preselect. All four places that pick
a Genius song use it: the search page, the pick pass page, the command-line prompt and the
Repair page. Each hit also shows its year.

Measured on raw YouTube titles (evaluation, "Rerun on the second computer"): the right hit is
first for 199 of 206 library songs by eye; today's search page gets 123 by the answer key,
which is a ceiling. Nothing the builder preselected was wrong.

## Calls this spec makes

The five points "Where Fable is needed" asked for, each with what was chosen and why. The
ones marked **Ken's to overturn** were not ruled in words; say so before Phase 1 if any is
wrong.

1. **What is contract.** Three tiers.
   - *Pinned by fixtures:* for every fixture title, what it parses into, the queries asked,
     the order of the hits and the preselect. The regexes inside are free to be rewritten as
     long as every fixture row holds.
   - *Word lists anyone may extend:* junk words, label and studio words, channel noise words,
     version words, stage/screen/dub words. Adding a word needs one new fixture title that
     shows why, and every existing row still passing.
   - *Structural rules:* the seven rules under "The module". Changing one is a judge's call,
     read on titles collected after the change is frozen. Both title sets used so far (the
     library's 206 and the 176 unseen) are spent as tests; they stay as regression fixtures
     only.
2. **The order of the hits is frozen as measured.** No order tried gets every film song
   right, and a change that fixes one title breaks another. Seven first hits are known to be
   the wrong recording ("Known holes"); they ship, because none is preselected and the year
   and artist line now shown let the person tell them apart. **Ken's to overturn.**
3. **Two channel cleaners, separate on purpose for now.** `genius_query` carries its own
   function for what act a channel's name stands for, ported from the prototype's
   `channel_artist`; `official_rank.py` keeps its own and is not touched. Ken ruled on
   2026-11-15 that this branch does not wait for `search_official_captions`, which rewrites
   `official_rank`'s channel handling, so a shared function now would be built on code
   about to change. The two also want different lists: the search ranking keeps its label
   list short (a miss costs only YouTube's order), the Genius module keeps its studio list
   wide (a miss puts a studio's name in a query). Unifying them is an open issue (Phase 1,
   step 3). Details under "Channel names".
4. **Nothing new is stored at download.** The search page passes the title, the channel and
   the typed search term. The other three places have the file name only, and run without a
   channel. Measured cost of no channel: 10 fewer songs preselected in 206, and one song a
   place lower. Storing the title and channel would add a file every rename and delete has
   to carry, for pages where an admin is already looking at each song. **Ken's to overturn.**
5. **GATE G can fail.** It is read by eye on videos collected after the code is frozen, with
   the stop numbers written down now ("GATE G").

Three more calls, each **Ken's to overturn**:

- **A query someone types goes to Genius as typed**, in Genius's own order, with nothing
  preselected. The builder's order was measured on video titles only; on free text it would
  re-sort Genius's answer by page views.
- **The typed YouTube search term is the last rung** on the search page: tried after the
  title's own queries, inside the three-call limit, when nothing has matched for sure. Today
  it is tried only when the title returns nothing at all.
- **At the command-line prompt, Enter takes the preselected hit.** Today Enter there searches
  again.

## The module: `pikaraoke/lib/genius_query.py`

A clean port of `builder.py` plus the loop in `run.py`'s `replay`. Same behaviour on every
fixture row; small typed functions, no module-level switches (`WHO_TIERS` goes, its `True`
branch is the order). Where the prototype looks odd (the one-letter junk word `i`, the
segment dropped for holding a full-width colon), port it as it is and note the oddity in the
Results log. Do not fix it: the fixtures were measured with it.

### Public surface

```python
@dataclass(frozen=True)
class Parsed:            # builder.py's Parsed, same fields
    title: str; alts: tuple[str, ...]; artist: str; film: str
    year: int | None; channel: str; swap: Literal["", "dash", "pipe"]; raw: str

@dataclass(frozen=True)
class Found:
    hits: list[GeniusHit]    # at most 8, in the order to list them
    preselect: int | None    # hits[0].id when it is safe to preselect, else None
    query: str               # what a search box shows: the first query asked

def parse(text: str, channel: str = "") -> Parsed
def ladder(parsed: Parsed) -> list[str]
def start_query(text: str) -> str      # ladder(parse(text))[0], or the text when the ladder is empty
def find_song(search: Callable[[str], list[GeniusHit]], text: str, *,
              channel: str = "", typed: str = "", max_calls: int) -> Found

SEARCH_PAGE_CALLS = 3    # ruling D
LIBRARY_CALLS = 2
```

`search` is passed in (the route gives `lambda q: client.search(q, limit=20)`), so the module
never touches the network and the tests feed it cached answers.

### The seven structural rules

In the words of the evaluation ("What the new builder does differently"); the prototype is
the exact form.

1. **Read the title into parts first**: title, artist, film, year, and a translation of the
   title when the video gives one. A `(From "Film")` bracket names a film. A quoted or
   【】/《》 phrase is the title. Junk brackets, junk tail words, hashtags, handles and label
   names go. Of `A - B` the left is the artist unless the channel or a year says otherwise;
   of `A | B` either side may be the title. A year beside the left part marks it a film.
2. **Ladder from the parts**, most specific first: artist + title with its brackets' words;
   artist + bare title; channel + title (only when the title names no artist and no film);
   film + title; title alone; then the other side of a dash or pipe. Duplicates dropped.
3. **The channel stands in for the artist** when the title names none and the channel reads
   as an act ("Channel names").
4. **"Artist matches"** means the hit's primary artist is named by the title or the channel.
   A cast credit that only carries the film's name does not count.
5. **The ladder stops, and the first hit is preselected, only on a title-and-artist match on
   a page that has page views.** Otherwise the next query is asked, up to the call limit.
6. **Order of the merged hits**, highest first, each level breaking ties in the one above:
   1. the title matches at all;
   2. the artist matches, on a page with views;
   3. the title match is the likely reading (not the shorter side of a pipe);
   4. the hit's year is within one of the title's year, when the title carries one;
   5. the artist matches, on a page without views;
   6. not another version (a remix, live cut or the like by its title; a stage cast, a dub,
      or a film cast against a title that says "Musical", by its artist line);
   7. the film's or artist's name appears anywhere in the artist line, on a page with views;
   8. page views.
7. **Dropped before ordering**: "Deleted Artist" pages and pages flagged instrumental. This
   moves into `GeniusClient.search` ("The Genius client"), so typed searches drop them too.

`find_song`, as `replay` does it: ask the ladder's queries in order, at most `max_calls`;
merge new hits by id; stop after the first query that returns a hit passing rule 5; sort by
rule 6; keep 8; preselect the first when it passes rule 5.

### The typed term (search page only)

Not in the prototype, so not in the fixtures; covered by its own tests and read at GATE G.

`typed` is the YouTube search the guest ran. It is one more query after the title's own,
asked only when a call is left and no query so far has stopped the ladder. It is skipped
when its words, folded and taken as a set, equal those of a query already asked. Its hits
merge into the same list under the same order; the title from the video stays the thing
hits are matched against. It never changes what `parse` returns.

### Channel names

`genius_query` holds its own channel function, a port of the prototype's `channel_artist`
(`builder.py`). `official_rank.py` is not touched (Calls item 3).

```python
def channel_name(channel: str) -> str
    """The act a channel's name stands for, or "" when it reads as a studio, label or brand:
    "BackstreetBoysVEVO" -> "Backstreet Boys", "Disney Music VEVO" -> ""."""
```

Same steps and same lists as the prototype. A channel matching `NOT_AN_ACT` (the
prototype's `NOT_ARTIST`: studio, label and brand names) stands for no act. Otherwise the
noise words go ("- Topic" and "VEVO" at the end; Official, Video(s), Channel, Music, TV and
官方專屬頻道 anywhere) and CamelCase splits into words. `Parsed.channel` is its answer.

"Ends in VEVO" is not a label sign here. `official_rank` can tell `DisneyMusicVEVO` from the
act's own `BackstreetBoysVEVO` because it has the row's credited names; this module has no
such names, so it reads `NameVEVO` as `Name` and relies on `NOT_AN_ACT` for the studios.
The verified tick is not used: the library pages do not have it and nothing was measured
with it.

Ported as it is, so its check is the frozen `channel` part of every fixture row (206
library and 176 unseen, 382 channels), in Phase 1 step 2. A row that differs means the
port is wrong: fix the port, never the lists.

### Known holes

First hits the order gets wrong, by eye, on the 206. None is preselected. Each is pinned in
the tests as it is today, with a comment, so a change that moves one is seen.

| Video | First hit |
|---|---|
| Camp Rock 2: It's On | Eazy-E, 1993 (the cast page is 5th) |
| The Lion King: Can You Feel The Love Tonight | 1997 Broadway cast |
| The Lion King: Hakuna Matata | 1997 Broadway cast |
| The Outsiders: Stay Gold | Jun Matsumoto, 2014 (the cast page is 4th) |
| Wicked the Musical: Popular | The Weeknd & Madonna, 2023 |
| Wicked (channel "Wicked Movie"): What Is This Feeling | the 2003 stage recording |
| *NSYNC: Thinking Of You (I Drive Myself Crazy) | an *NSYNC page with a version suffix, no views |

Pinned the other way, as rows the order must keep right: Savages, Take Me or Leave Me (both
lost when levels 5 and 7 are removed) and the KPop Demon Hunters songs (lost by every order
tried that fixes the Lion King pair).

## What each place gives the module

| Place | Text | Channel | Typed term | Calls |
|---|---|---|---|---|
| Search page | the row's YouTube title | the row's channel | the YouTube search the guest ran | 3 |
| Pick pass page | file name without the ID | none | none | 2 |
| Command-line prompt (`add_songs`, regen, backfill) | file name without the ID | none | none | 2 |
| Repair page | file name without the ID | none | none | 2 |

A direct link, a playlist row and an `add_songs` download all reach Genius through the pick
pass or the prompt, so they are the file-name rows. A fresh download's file name is the
YouTube title as it was saved (seen in this library: `/` and `|` as `_`, `"` as `'`, `:` as
` -`, `?` gone); the prototype's parser already reads those forms. A renamed file is `Artist - Title` or
`Film (Year) - Title`, which it also reads. File names are not a gate: Ken ruled the search
is judged on raw titles, and on these pages the admin sees the query and the hits.

## The Genius client (`genius.py`)

- `GeniusHit` gains `primary_artist: str`, `year: int | None`, `views: int` (0 when Genius
  gives none). Field sources as `run2/gx.py` reads them: `primary_artist.name`,
  `release_date_components.year`, `stats.pageviews`.
- `search` also drops pages whose artist line holds "Deleted Artist" and pages flagged
  `instrumental`. Its other filters and its "empty list on any failure" contract stay.
- The 8-hit default stays for typed searches; `find_song` asks for 20.
- A failed query still reads as an empty one, so the ladder moves on. That is the open issue
  "A service outage reads as no results"; it stays open and is not fixed here.

## The route (`/lyrics_search`)

Two forms, one route. Both answer `{"hits": [{id, title, artist, year}], "preselect": id or
null, "query": str}`; always 200, empty `hits` when Genius is off or finds nothing.

- `?title=...` with optional `channel` and `typed`: `find_song`. The search page always
  sends `channel` (empty when YouTube gave none), and that is how the route knows to allow
  three calls; without the parameter it allows two.
- `?q=...`: what someone typed. One Genius call with the text trimmed and otherwise as
  typed, Genius's order, `preselect` null, `query` the text.

`clean_genius_query` and its tests are deleted; nothing else calls it. `clean_search_query`
stays in `metadata_parser.py` for its other callers. `default_query` keeps its one remaining
use, the Repair page's LRCLIB box (that half is closed with no build); the three `"query"`
fields in `library_tools.py` and the prompt switch to `genius_query.start_query`.

## The four places

**Search page (`search.html`).** Each result row carries its channel (`data-ytchannel`, on
both the first page and "more" rows). Opening a video sends `title`, `channel`, `typed`.
The client-side fallback to the typed term goes; the server does it. The dropdown lists the
hits as `Title — Artist (Year)`, the year left off when Genius has none. With a preselect,
that hit is selected and Download shows, as today. Without one, a disabled first option
("Choose the lyrics") is selected and Download stays hidden until a hit or another option
is chosen (ruling B). No hits: as today, straight to Custom Search. Custom Search sends
`q`.

**Pick pass page (`pick_pass.html`).** The box starts with `song.query`, now from
`start_query`. A search with the box unchanged sends `title` (the song's file name without
the ID, which the view supplies); an edited box sends `q`. A preselect becomes
`picker.selected`. Each hit shows its year.

**Repair page (`song_repair.html`).** The Genius box starts with the same `start_query`
text instead of empty (item 7). It does not search until asked, as today. Unchanged box
sends `title`, edited sends `q`. A preselect ticks that hit's radio. Each hit shows its
year. The "current" tag on the bundle's recorded pick stays.

**Command-line prompt (`scripts/genius_prompt.py`).** The first search for a song is
`find_song` on the file name, two calls; any query the admin types is a typed search. Hits
print as `Title - Artist (Year)`. A preselected hit prints first with a mark, and Enter
takes it; with no preselect Enter does what it does today.

## Fixtures and tests

Frozen once, in Phase 1, from the prototype and the committed cache, before any port is
written. The freeze script (`plans/genius-search-accuracy/run2/freeze.py`) imports
`builder.py` and `run.replay`, reads `run2/genius_raw.json` and **fails on a query that is
not cached**: it makes no Genius call. It runs on either computer: `gx.py` reads the
committed `run2/truth_names.json` on import, and `holdout.py` uses it to keep library
videos out. That file is the answer key without its lyric lines, written by the same
`truth_build.py` run as the gitignored `run2/truth.json`, and nothing in `run2/` reads the
lines. (Amended 2026-11-15, Ken: the freeze no longer waits for the VM. Results log row 1.)

Written to `tests/unit/data/genius_search/`:

- `library.jsonl`, 206 rows: YouTube ID, title and channel (from `run2/yt_meta.json`), then
  what the prototype gives: the parsed parts (read with the channel), and for each of two
  runs (three calls with the channel; two calls without it) the queries asked, the ids of
  the hits in order, and the preselect.
- `unseen.jsonl`, 176 rows, the videos `holdout.py` selects: the same fields, one run (three
  calls with the channel). The IDs are what GATE G uses to keep these videos out of its
  fresh set.
- `answers.json`: query to hits, only the queries those runs ask, each hit cut to
  `GeniusHit`'s fields and already past the prototype's `usable` filter.

The 176 come from 44 YouTube searches: 14 already in `tests/unit/data/youtube_search` here,
and 30 that exist only on `search_official_captions`, committed there as `81875520`. The
freeze reads all 44 from a temporary copy, and the 30 are never committed on this branch:

```bash
git archive 81875520 tests/unit/data/youtube_search | tar -x -C <scratch dir>
$PY freeze.py <scratch dir>/tests/unit/data/youtube_search
```

The commit, not the branch name, so the rows do not move if that branch changes or is
retired (`81875520`'s copy of the folder is the branch tip's on 2026-11-15). The tests read
only the committed `unseen.jsonl`, never the searches.

No lyric text and no answer key go in; these files hold public titles, channel names and
Genius search results only.

Tests (`tests/unit/test_genius_query.py`, and additions to the existing client, route and
prompt tests):

- Every fixture row: `parse` gives the frozen parts; `find_song` over `answers.json` asks
  the frozen queries and returns the frozen order and preselect, for each run. A fake
  `search` that raises on an unknown query proves no extra call is made.
- The seven known holes and the rows pinned right ("Known holes"), by name.
- The typed term, on small made-up answers: asked last; not asked after a sure match; not
  asked past the call limit; skipped when it repeats a query; its hits merge and can be
  first.
- `start_query` on a fresh-download file name and on a renamed one.
- Client: the three new fields; "Deleted Artist" and instrumental pages dropped.
- Route: both forms and the answer's shape; three calls with `channel`, two without;
  Genius off gives empty `hits`.
- Prompt: Enter takes a marked hit; no mark, no change.

## Phases

One commit per numbered step unless it says otherwise; tests ride with their code. After
each phase, write its row in the Results log, stop, and say so (Ken compacts between
phases).

**Phase 0: rebase onto current `dev`.** No behaviour change, no commit of its own.
1. Rebase this branch onto `dev` as it stands (Ken, 2026-11-15: it does not wait for
   `search_official_captions`). Run the full suite; record `dev`'s hash and the count.
   Nothing in this spec needs `official_rank.py` or that branch's `/search` changes. If it
   has landed by then, nothing here changes either: its 30 searches are on `dev`, and the
   freeze still reads them from `81875520`. Whichever branch lands second meets the other's
   edits to `pikaraoke/routes/search.py` (this one `/lyrics_search`, that one `/search` and
   `/search/more`); the clash is textual only.

**Phase 1: the module.**
1. `docs(plans)`: `freeze.py`. Then `test(genius_query)`: the three fixture files it
   writes. Two commits, because the script lives under `plans/` ("Executor rules"). Record
   the row counts and the commit of `builder.py` they came from in the Results log.
2. `feat(genius_query)`: the module and its tests, the typed term included. The channel
   check of "Channel names" (382 channels) is part of this step.
3. `docs(plans)`: this entry in `plans/open-issues.md`, under "Search results (on `dev`)":

   > - **Unify the channel cleaners once `search_official_captions` lands.**
   >   `official_rank.py` and `genius_query.py` each work out what act a channel's name
   >   stands for, with their own noise words, kept apart while that branch rewrites
   >   `official_rank`'s. Once it lands: one function for the name, each module keeping
   >   its own list of names that stand for no act (the ranking's short, the Genius
   >   module's wide). Not ruled. Record: `plans/genius-search-spec.md` on branch
   >   `genius_search_accuracy`, Calls item 3 and "Channel names".

**Phase 2: client and route.**
1. `feat(genius)`: the hit's new fields and the two drops.
2. `feat(search)`: the route's two forms; `clean_genius_query` deleted.

**Phase 3: the four places.**
1. `feat(search)`: the search page (channel on the row, placeholder, preselect).
2. `feat(library_tools)`: pick pass and Repair (`start_query`, `title`/`q`, preselect).
3. `feat(scripts)`: the prompt.

**Phase 4: the year shown per hit** (ruling A's phase 2, item 6): all four places, one
commit. The route already returns it.

Then `/code-review` is due on Phases 1-4 (Ken runs it), and its fixes land before the
gate, because the gate freezes the code.

**Phase 5: GATE G collection.** Below. The executor collects and stops; it does not count
or judge.

**Phase 6: Ken's checks in the real app**, after the gate passes: a search-page download
with a preselect and one without; a title-only upload; the pick pass on a fresh download;
Repair's Genius box; the prompt through `add_songs`.

## GATE G

Read on YouTube videos no rule was shaped on, collected after the code is frozen (Phases 1-4
and the review's fixes). The library's 206 and the 176 unseen are spent: they are fixtures,
not the gate. The stop numbers were ruled by Ken on 2026-11-15, before any code, and do not
move once the collection exists.

### Where the videos come from

Thirty YouTube searches, fixed here so that neither the executor nor the judge picks titles
after seeing results. None is a song in either library or in the 44 fixture searches. Half
are film and stage songs with more than one recording on Genius (two films, a film and a
stage cast, a pop single, a dub): the case the answer key could not read. The rest name an
act, carry a CJK title, or name only a song that other songs share.

| # | Search, typed as is | The video's title must carry | Kind |
|---|---|---|---|
| 1 | remember me coco | Remember Me | film |
| 2 | i dreamed a dream les miserables | I Dreamed a Dream | film, stage |
| 3 | music of the night phantom of the opera | Music of the Night | film, stage |
| 4 | you're the one that i want grease | You're the One That I Want | film, stage |
| 5 | the winner takes it all mamma mia | The Winner Takes It All | film, act |
| 6 | you will be found dear evan hansen | You Will Be Found | film, stage |
| 7 | a million dreams greatest showman | A Million Dreams | film, cover |
| 8 | go the distance hercules | Go the Distance | film, single, stage |
| 9 | kiss the girl little mermaid | Kiss the Girl | two films |
| 10 | friend like me aladdin | Friend Like Me | two films, stage |
| 11 | i just can't wait to be king lion king | I Just Can't Wait to Be King | two films, stage |
| 12 | the wizard and i wicked | The Wizard and I | film, stage |
| 13 | memory cats | Memory | film, stage |
| 14 | and i am telling you dreamgirls | And I Am Telling You | film, stage |
| 15 | my shot hamilton | My Shot | stage only |
| 16 | taylor swift love story | Love Story | act, re-recording |
| 17 | whitney houston greatest love of all | Greatest Love of All | act |
| 18 | bon jovi livin on a prayer | Livin' on a Prayer | act |
| 19 | billie jean michael jackson | Billie Jean | act, title first |
| 20 | olivia rodrigo drivers license | drivers license | act |
| 21 | bruno mars uptown funk | Uptown Funk | act, featured not primary |
| 22 | the weeknd blinding lights | Blinding Lights | act |
| 23 | linkin park numb | Numb | act |
| 24 | blackpink how you like that | How You Like That | act, K-pop |
| 25 | bts dynamite | Dynamite | act, K-pop, shared title |
| 26 | 周杰倫 告白氣球 | 告白氣球 | act, CJK |
| 27 | 陳奕迅 浮誇 | 浮誇 | act, CJK |
| 28 | creep | Creep | title only |
| 29 | yesterday | Yesterday | title only |
| 30 | imagine | Imagine | title only |

"Kind" is why the search is here, not a label the judge scores by. Each search is run once,
as the search page runs it (`get_search_results(search, PAGE_SIZE)`, YouTube's order). From
its results keep the first four whose folded title (as `builder.squash`) contains the
carried title's, whose ID is in neither `library.jsonl` nor `unseen.jsonl`, and that no
earlier search kept: up to 120 videos. A search with fewer than four keeps what it has; the
shortfall is logged, never topped up from another search.

One reason only to run a search again: every row came back without a channel. YouTube does
that to about 1 search in 12 (`plans/open-issues.md`, "Search results"), and every title the
builder was measured on had its channel. Run it again, up to three times, keep the first
answer that has channels (the last one if none does), and log each rerun.

### What the executor collects, then stops (Phase 5)

1. Record the frozen HEAD and the full suite's count. The suite includes the seven Known
   holes and the rows pinned right; if any fails, STOP before collecting.
2. `plans/genius-search-accuracy/gate_g/collect.py`:
   - YouTube: the thirty searches, rows (ID, title, channel, length, description snippet:
     all five come back from the one search) cached in `gate_g/youtube.json`; the
     selection above.
   - Genius: per video, `find_song(search, title, channel=channel, typed=<the search>,
     max_calls=SEARCH_PAGE_CALLS)`, then again with `typed=""` on the same answers.
     `search` is `GeniusClient.search(q, limit=20)` behind a cache by query
     (`gate_g/genius.json`), so a rerun makes no call and the read can be replayed.
   - `gate_g/sheet.md`, one block per video in table order: number, YouTube title,
     channel, ID, length, description snippet, the search; the parsed parts; the queries
     asked, the typed one marked;
     the hits as `Title — artist line (year, views)` with the preselect marked; when the
     typed term was asked, the whole list without it, in the same form (the `typed` column
     needs to know whether the right hit was listed at all without it).
   - `gate_g/verdicts.md`: the judge's table, one empty row per video number, with the
     columns below.
3. `docs(plans)`: the script, both caches, the sheet and the empty verdicts. They hold
   public titles, channel names and Genius search results only.
4. The Results log row: frozen HEAD, suite count, whether the YouTube search was quoted
   (`dev` quotes it today; `search_official_captions` unquotes it), videos per search and
   in all, searches short of four, Genius calls made. Hand Ken a ready-to-paste prompt for
   the Opus read (branch, HEAD, this section, the `gate_g/` folder). Stop: do not count,
   judge, or fix anything the sheet shows.

### What is read by eye

The judge reads every video in the sheet's order and fills its row:

- `what`: what the video is: the song and its recording, read from the sheet's title,
  channel, length and description snippet. When a row is still unsure the judge may look
  that one video up by its ID (its page or `yt-dlp` on the ID, never a search) and names
  the rows it looked up.
  An act's own upload (official, lyric, live), a cover (of whose song), a film's cast
  (which film, and its year when two films share the song), a stage cast, a pop single, a
  dub; or not a song (a trailer, a reaction); or unsure. A video of another song than the
  one searched (another act's "Creep") is read as its own song, as the unseen set's were;
  searches 28-30 are there to draw them.
- The right hit, against `what`: the song's page by the act the video is (for a cover, the
  original act's page or the cover act's own page of the song); for a film or stage song,
  the page of the recording the video is. A version page (live, remix) is right only when
  the video is that version; for a live or re-recorded video the song's plain page is right
  as well.
- `first`: right; right song, wrong recording; wrong song; no hits.
- `listed`: the right hit's place among the hits, or none.
- `preselect`: none; right; wrong (anything but the right hit).
- `typed`: not asked; no change; helped (the right hit is first with it and was not
  without it, or is listed only because of it); hurt (the right hit was first without it
  and is not with it).

Rows read as not a song, or unsure, are left out of every count and named by number.
Every film and stage video's first hit has its recording read from the hit's artist line,
year and views. The judge hands Fable only the rows where it cannot tell which recording
a hit is, and says which those were. Once Fable's window has closed, those rows are left
out instead ("Rulings on the gate", 5).

### Stop numbers (Ken, 2026-11-15)

Counted over the rows left in. Any one of the four stops the build.

| # | Measure | Stops when | For scale |
|---|---|---|---|
| G1 | Wrong preselects | 2 or more | 0 of about 250 on the library and unseen sets (the unseen set's four other-act pages were each the video's own song) |
| G2 | Right song first: `first` is right, or right song with the wrong recording | below 70% of the rows | 77-78% on the clean unseen pass (title, and act where named); 52% for today's search page on the same videos |
| G3 | Videos of a film's or a stage cast's recording whose `first` is the wrong recording or a wrong song (no hits count in G2 only) | above 1 in 3 of those videos | 6 of 43 on the library (the seventh Known hole is an act's song) |
| G4 | The typed term | hurt on more videos than it helped | not measured |

A single wrong preselect does not stop the build, but the judge writes it up for Ken like a
failing row. G2 is also given for searches 1-15 and 16-30 apart, as a report only: its scale
came from a set about a quarter film (11 of 44 searches) and the gate is half, and the stop
number is the whole.

### The seven Known holes

They are not in the gate: their songs are library songs, so no search above returns them as
fresh videos. They count in two ways:

- **Held:** their pinned rows pass in the suite at the frozen HEAD (step 1).
- **As the scale for G3:** six of them are the 6 of 43 film-named library songs, on titles
  the order was shaped on (the seventh, *NSYNC, is an act's song). The same pattern on a
  new song (a stage cast first for another Lion King or Wicked song) counts in G3 like any
  other wrong first hit: the holes were accepted by name, not by pattern.

### Who reads it, and after

Opus fills `verdicts.md`, counts G1-G4 and writes the gate's Results log row: the four
counts against their stop numbers, G2 for each half, the rows left out, the rows looked up,
the rows Fable read, and every row that failed, by number and title. Then Ken reads it.

- **Pass:** Phase 6.
- **Fail:** STOP. The judge writes up the failing rows and nothing is changed to pass them
  ("Executor rules"). Ken rules: ship as it is, move the typed term back to today's
  zero-hits fallback (G4), or change a structural rule or the order (a judge's call, Calls
  item 1). A change is read at a new GATE G on new searches, and this gate's videos are
  then frozen into the fixtures the way `unseen.jsonl` was.

### Rulings on the gate (Ken, 2026-11-15)

On four questions from Fable's review of this section, each taken as recommended and
written in above. None touches the search list or the four stop numbers.

1. **G3 counts a wrong song as well as a wrong recording.** Three of the six library rows
   behind "6 of 43" are another song of the same title (Eazy-E, Jun Matsumoto, The Weeknd
   & Madonna); wrong recording alone would have made the scale 3 of 43. A video with no
   hits counts in G2 only.
2. **`what` is read from more than the title and channel:** the length and description
   snippet the search already returns, and a lookup of one video by its ID when a row is
   still unsure. The library's 6 of 43 was read knowing each video's film and year.
3. **For a live or re-recorded video the song's plain page is right**, and so is the
   version's own page. Search 16 turns on it: a Taylor's Version video preselecting the
   2008 page is not a wrong preselect.
4. **G2 is reported for each half** (searches 1-15, 16-30); the stop number stays the
   whole.

Two more, from a planning session (Opus 5.5) on Fable's availability, which ends on
Monday night 2026-11-16, before this gate is likely to be reached. The read stays
with Opus.

5. **After Fable's window, a row whose recording Opus cannot tell is left out**, as an
   unsure row is: out of every count, named by number in the gate's Results row with the
   reason. G3 is then measured on fewer film videos; the stop numbers do not move.
6. **A recordings guide, if Fable writes one before the window closes.** For the fifteen
   film and stage searches (1-15): the recordings each song has, and how Genius usually
   credits each one. It is written from memory, with no search (the executor rule on the
   thirty holds), and kept outside the repo until Phase 5, so the build is not shaped on
   it. At Phase 5 it is committed with the sheet. The judge may read it as a hint and still
   reads every hit's artist line, year and views. A guide entry never decides a row on its
   own.

## Executor rules

- **A title that fails is a STOP for the judge**, never a new pattern, word or order level
  added to make it pass. That covers a fixture row the port does not reproduce (fix the
  port toward the prototype; if the prototype's own reading is in question, STOP), a title
  tried by hand, and anything the GATE G sheet shows. The word lists Calls item 1 lets
  anyone extend are for after this build: during it, nothing is added to any list.
- **No lyric text** in any commit, test, fixture or plan. Fixtures and gate files hold
  public titles, channel names and Genius search results only. Never `git add -f` the
  ignored `run2/truth.json`.
- **No search for the gate's thirty terms or their songs**, in any wording, on YouTube or
  Genius, in the app or by hand, before Phase 5. Hand checks before then use library songs.
  Tests make no network call: they read the committed fixtures through a fake `search`.
- Conda env `pik`: `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Pre-commit on the
  changed files only (`--files`, not `--all-files`).
- Tests ride with the code they exercise, in the same commit.
- Plan edits (this file, the evaluation, `plans/open-issues.md`, the `gate_g/` files) go in
  their own `docs(plans)` commits, never in a code commit.
- `/code-review` after Phase 4: hand Ken the exact line (commit range, files in scope, one
  finder per Self-Review axis). Never launch it.
- Stop at each phase's Results log row and say so; Ken compacts between phases (kept by Ken
  on 2026-11-15, asked whether Phases 0-4 should run straight through). Push only when Ken
  asks.

## Results log

One row per step or phase, written by whoever did it: raw counts and provenance, no
verdicts. Prototype oddities ported as they are ("The module") go in the row of the step
that ported them.

| # | Date | Step | Result | Evidence |
|---|---|---|---|---|
| 1 | 2026-11-15 | spec | `run2/gx.py` reads `truth_names.json`, not `truth.json`. Dry run of the freeze's replays at `4fd21d87` on the Linux box, done in scratch, outside the repo: the 206 library rows with ID (`new` with the channel, 3 calls; `new-nochannel`, 2 calls), and `holdout.py`'s selection over the 44 searches of `81875520` (`git archive`) with `new` with the channel, 3 calls, from `truth_names.json`, with `gx.client` replaced by one that raises. 206 library rows, 44 searches, 176 unseen videos, 0 queries missing from `genius_raw.json`. No fixture written. | this file, "Fixtures and tests"; Rulings on the gate 5-6 |
| 2 | 2026-11-16 | Phase 0 | `git rebase dev` onto `6c4e9991` (13 commits ahead of the old base `1016e209`), run in the worktree; all 9 branch commits replayed, 0 conflicts, all 9 are `plans/` only. Branch head before: `7c6c2e72` (one commit past `4fd21d87`, the freeze/GATE G rulings commit); after: `73c269e3`. `origin/genius_search_accuracy` still at `6dcfb89b` (the pre-rebase "genius search spec" commit), so the branch is now ahead 22, behind 5 of it and a push would need a forced update. Full suite at `73c269e3`, env `pik`: 3629 passed, 0 failed, 0 skipped, 0 warnings, 50 s; worktree clean after. No code touched, no network, no gate song searched. | `git rev-parse dev` = `6c4e9991`; this commit |
| 3 | 2026-11-16 | Phase 1, step 1 | `freeze.py` (`7a0ea8c4`) and the fixtures it wrote (`016015bf`), run at `eb8d4be0`, env `pik`, 1.5 s, no Genius call (it replaces `gx.raw` with a cache-only lookup that exits on a missing query, and `gx.save` with nothing; `genius_raw.json` unchanged in git). Prototype sources: `builder.py` last committed here as `47b1fe58` (blob `22173577`; rebased, so hash-object is the stable name), `run.py` blob `fedbd344`, `truth_names.json` blob `a915056d`, `genius_raw.json` blob `18e6cbdb`. The 30 extra searches read from `git archive 81875520` into scratch (44 files in all), never committed. Written: `library.jsonl` 206 rows, `unseen.jsonl` 176 rows, `answers.json` 475 queries (557 KB). A second run is byte-identical. Raw counts, with the channel (3 calls) / without (2 calls): library preselected 163 / 153 of 206, calls 273 / 249, no hits 0 / 1; unseen with the channel preselected 116 of 176, calls 290, no hits 12. Choices the spec left open: (a) `queries` is the ladder cut to the calls actually made, `queries[:calls]` of `run.replay`'s return, not the whole `queries[:max_calls]` it returns (that one lists rungs never asked after an early stop); (b) one edit to the prototype tree: `holdout.py`'s `videos` entries gain `"id": v["id"]`, because two uploads share one title and channel (`Catherine Laga'aia - How Far I'll Go (From "Moana")`, DisneyMusicVEVO: `IhZI-a1eiCg`, `_nVJl4-o2XA`) so title and channel cannot give the ID back; it changes nothing `holdout.py` selects or prints; (c) a row's `parsed` leaves out `raw` (it is `yt_title`), and a `channel` of None is stored as `""`; (d) `freeze.py` imports `holdout`, which imports `clean_genius_query`, so it runs only before Phase 2 deletes that function. | this file, "Fixtures and tests"; `plans/genius-search-accuracy/run2/freeze.py` |
| 4 | 2026-11-16 | Phase 1, step 2 | `pikaraoke/lib/genius_query.py` and `tests/unit/test_genius_query.py` (`3bc6d440`). Scratch check, not committed: all 21 regexes shared with `builder.py` have the same pattern and flags; of the 382 fixture titles, 382 parse to the frozen parts, 382 channels read as the frozen act, and all 588 runs (382 with the channel, 206 without) ask the frozen queries and give the frozen hit order and preselect. Full suite at `3bc6d440`, env `pik`: 3666 passed (3629 + 37 new), 0 failed, 50 s. No word added to any list. Prototype oddities ported as they are: the one-letter junk word `i`; a `\|`-segment holding a full-width colon dropped whole; `names()` is true when a hit's artist line folds to nothing and the source has 4 or more letters (`"" in x`; every real hit has an artist line); `_cjk_quoted_title` takes the first phrase that is not empty, not the first phrase. Not as it was, same result: `strip_junk_tail`'s `head == m.group(1) or head` is written `head` (the first half implies the second); `parse` is split into helpers (a draft object stands in for the prototype's mutable `Parsed`); the merged hits are a dict by id (the prototype's list and `seen` set differ only if one query returns an id twice). Calls this step made that the spec's wording left open: the typed term's repeat test compares every folded word, stop words too; a typed term with no words in it (`""`, `"?!"`) is never asked; `Found.query` is the first query asked, or the text when none was. **Out of order against the Phases list:** `GeniusHit` gained `primary_artist`, `year`, `views` here, defaulted (`""`, `None`, `0`), because the module and its tests read them and existing callers build `GeniusHit(id, title, artist)`. Phase 2 step 1 is now only: fill them in `GeniusClient.search` and add the two drops. | this file, "The module"; `pikaraoke/lib/genius.py` |
| 5 | 2026-11-16 | Phase 1 | Steps 1-3 done: `7a0ea8c4`, `016015bf`, `3bc6d440`, and the open-issues entry "Unify the channel cleaners" under "Search results (on `dev`)" (`5a973848`, `plans/open-issues.md` only). No route, template, client search or `official_rank.py` touched. No Genius or YouTube call by any step; no search for the gate's thirty songs. Not pushed; `origin/genius_search_accuracy` is still at `6dcfb89b`. | `git log eb8d4be0..HEAD` |
| 6 | 2026-11-16 | Phase 2, step 1 | `GeniusClient.search` fills `primary_artist`, `year` and `views` and drops "Deleted Artist" pages and `instrumental` pages (`0b29217f`; amended once, unpushed, to name the constant below). Fields read as `run2/gx.py` does, but a null `primary_artist` with `artist_names` present leaves `primary_artist` `""` and keeps the hit (as before this step) instead of failing the whole answer; a missing `stats` or year reads as 0 and `None`. The "Deleted Artist" test is on the artist line, lower-cased, as `builder.usable`; both drops come before the `limit` count, as the prototype filtered before merging. Not in the spec: `HITS_PER_QUERY = 20` in `genius.py` now stands for the page size that was a bare `per_page=20`, so the route's `limit=` cannot drift from it. Scratch check, not committed: all 475 queries of `answers.json` rebuilt into Genius's response shape from `genius_raw.json` and fed through `search(q, limit=20)` with `lyricsgenius` mocked: 475 same, 0 differ (3192 hits kept of 3991 cached); none of the 475 names Genius, so the `translation` branch of the filter was not exercised. 5 new client tests. | this file, "The Genius client" |
| 7 | 2026-11-16 | Phase 2, step 2 | `/lyrics_search` answers `{hits: [{id, title, artist, year}], preselect, query}` in two forms (`00ece530`). `title` (with `channel`, `typed`) runs `find_song` over `search(q, limit=HITS_PER_QUERY)`; `"channel" in request.args` picks 3 calls, absence 2. `q` is one `search(q)` call, text trimmed, nothing else done to it, Genius's order, `preselect` null, `query` the text. Calls the spec left open: `title` wins when both are sent; an empty `title` and empty `q` answers `{"hits": [], "preselect": null, "query": ""}` with no Genius call; with Genius off the `title` form's `query` is still the first rung. `clean_genius_query` and its 7 tests deleted, with the module docstring lines and the two imports only it used (`NOISE_PATTERN`, `EMOJI_PATTERN` stay in `metadata_parser.py`, used there and in `song_match.py` and `genius_query.py`). Route tests: the old class's 6 replaced by 9. A throwaway break of each of three lines (always 2 calls, `limit=8`, typed text lower-cased) failed a test in the first two; the third passed until the typed-text test was given mixed-case, emoji input, then failed; file restored. Full suite at `00ece530`, env `pik`: 3667 passed (3666 + 5 client - 7 - 6 + 9), 0 failed, 47 s. **The three pages are not yet changed:** `search.html`, `pick_pass.html` and `song_repair.html` still read the old bare list, so on this branch their Genius dropdowns show nothing until Phase 3. **Plan scripts that import the deleted function** and no longer import: `genius-search-accuracy/genius_eval.py`, `genius_probe.py`, `genius_sim.py`, `run2/freeze.py`, `run2/holdout.py`, `run2/today.py` (closed evaluation; not touched; the fixtures `freeze.py` wrote are committed). | this file, "The route"; `git show 00ece530` |
| 8 | 2026-11-16 | Phase 2 | Steps 1-2 done: `0b29217f`, `00ece530`. No template, `library_tools.py`, prompt or `official_rank.py` touched. No Genius or YouTube call by any step or check (every Genius answer was the committed cache or a mock); no search for the gate's thirty songs. Not pushed; `origin/genius_search_accuracy` is still at `6dcfb89b`. | `git log ed611a7b..HEAD` |
