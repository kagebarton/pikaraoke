# Genius search: the spec

Model: Claude Sonnet 5.5 executes. Spec by Claude Fable 5.2, 2026-11-13. GATE G is read by
Opus, then Ken (Fable only if Opus is unsure which recording a hit is).

Status: **spec written, no code.** Blocked on `search_official_captions` landing on `dev`;
Phase 0 starts with the rebase onto it.

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
3. **One function says what act a channel's name stands for**, and it lives in
   `official_rank.py`, which lands first and already owns the idea. The Genius module adds
   only its own list of studio and brand names whose channels never stand for an artist.
   The two lists stay separate on purpose: the search ranking keeps its label list short
   (a miss costs only YouTube's order), the Genius module keeps its list wide (a miss puts
   a studio's name in a query). Details under "Channel names".
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

After `search_official_captions` lands, `official_rank.py` works out a channel's act name in
two steps (its `_channel_artist`, then the trailing words its rule 7 strips). Phase 0 turns
that into one public function there:

```python
def channel_act_name(channel: str) -> str
    """The channel's name without "- Topic", "Official", "VEVO", "Music", "TV", "Videos"
    and the like, CamelCase split into words: "BackstreetBoysVEVO" -> "Backstreet Boys"."""
```

`official_rank` compares the compact form of it (`_compact(channel_act_name(...))`);
`genius_query` uses the words. The Genius module then holds one list of its own,
`NOT_AN_ACT`: `official_rank`'s label words (Records, Recordings, Labels) plus the studio and
brand names from the prototype's `NOT_ARTIST`. A channel matching it stands for no artist.

"Ends in VEVO" marks a label only in `official_rank`, which has the row's credited names to
tell `DisneyMusicVEVO` from the act's own `BackstreetBoysVEVO`. The Genius module has no
such names, so it reads `NameVEVO` as `Name` and relies on `NOT_AN_ACT` for the studios.
The verified tick is not used here: the library pages do not have it and nothing was
measured with it.

This is the one place the port may differ from the prototype's text, so it is checked both
ways in Phase 0: `official_rank`'s own tests pass unchanged, and all 382 fixture channels
give the same act name as the prototype's `channel_artist`. The shared function's noise
words are the union of the two modules' lists as they stand, nothing more. If either check
fails with that union, STOP and write up the rows that differ; do not add or drop a word to
force it.

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
not cached**: it makes no Genius call. It runs on the VM, where `run2/truth.json` is.

Written to `tests/unit/data/genius_search/`:

- `library.jsonl`, 206 rows: YouTube title and channel (from `run2/yt_meta.json`), then
  what the prototype gives: the parsed parts, and for each of two runs (three calls with
  the channel; two calls without it) the queries asked, the ids of the hits in order, and
  the preselect.
- `unseen.jsonl`, 176 rows, the videos `holdout.py` selects from
  `tests/unit/data/youtube_search` (on `dev` once `search_official_captions` lands): the
  same fields, one run (three calls with the channel).
- `answers.json`: query to hits, only the queries those runs ask, each hit cut to
  `GeniusHit`'s fields and already past the prototype's `usable` filter.

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

**Phase 0: rebase and reconcile.** No behaviour change.
1. Rebase this branch onto `dev` once `search_official_captions` is on it. Read
   `official_rank.py` as landed; if its channel handling is not what "Channel names"
   describes, STOP and report before writing anything.
2. `refactor(official_rank)`: `channel_act_name` public, `official_rank` using it, its
   tests unchanged and passing.

**Phase 1: the module.**
1. `test(genius_query)`: `freeze.py` and the three fixture files. Record the row counts
   and the commit of `builder.py` they came from in the Results log.
2. `feat(genius_query)`: the module and its tests, the typed term included. The channel
   check of "Channel names" (382 channels) is part of this step.

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
