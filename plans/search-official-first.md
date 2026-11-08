# Search: 30 results, the original artist's official uploads first, Show more

Model: Claude Sonnet 5.5 (spec by Claude Opus 5.5, 2026-11-08)

Branch `search_official_first` off `dev` at `225da7b`, worktree
`.claude/worktrees/search_official_first` (inside the main checkout, gitignored via
`.claude/`; `models/` is symlinked in). Work and run everything from the worktree; another
session is using the main checkout.

## Goal

- The search page shows 30 YouTube results instead of 10.
- The song's original artist's official video(s) move to the top, then their official
  audio. Everything else keeps YouTube's order.
- A **Show more** button under the results loads results 31-60 once, then goes away.

## Decisions (Ken, 2026-11-08)

1. Lift both video and audio; video first.
2. Original artist only. A cover artist's own official video (Pentatonix, Bohemian
   Rhapsody) stays where YouTube put it.
3. No background or streamed fetching. The same yt-dlp call the app makes, timed on this box:
   10 results 1.25-1.79 s, 30 results 2.00-2.06 s, 60 results 2.89-3.39 s (3 songs). Streaming
   could save at most ~0.5 s, and it would fight the reorder: a late official result would jump
   to the top under the user's finger.
4. 30 is fixed (no preference). Show more fetches one more page (31-60) and then stops.

## Open decisions (Ken's call; the spec below assumes the first option)

- **A. Which "original".** The rule picks the artist that the most trusted results credit. For
  musicals and remakes, that is the current dominant version: Defying Gravity lifts Cynthia
  Erivo's film recording, not Idina Menzel's Broadway original (4 credits to 3). Getting the
  literal first recording would need an outside lookup, and Genius and Last.fm both rank by
  popularity too. Options: accept / add a lookup (new plan).
- **B. Official but not the record.** Official lyric videos, sing-alongs, live, karaoke, remix and
  acapella uploads are not lifted. The app overlays its own lyrics, and live or remix audio does
  not match the record. Example: ABBA's "Official Lyric Video" stays at #2. Options: accept / lift
  lyric videos after audio.

## What exists (checked 2026-11-08)

- `pikaraoke/lib/youtube_dl.py:205` `get_search_results(query)`: hardcoded `num_results = 10`,
  runs `yt-dlp -j --no-playlist --flat-playlist [--impersonate] ytsearch10:"<query>"`, returns
  `list[list[str]]` positional `[title, url, id, channel, duration]`.
- `pikaraoke/routes/search.py:71` `search()`: appends `existing_path` (library file with that
  YouTube ID) to each row, and computes `_library_copies` for the "Already in the library" note
  (capped by `MAX_SIMILAR_SONGS = 3`).
- `pikaraoke/templates/search.html:1128` unpacks the 6-tuple. `tests/unit/test_search_render.py`'s
  docstring records a past 500 from exactly this positional unpack, which is the reason for
  named fields below.
- `pikaraoke/karaoke.py:41` imports `get_search_results` and never uses it.
- Card click handlers are delegated (`$(document).on("click.search", ...)` at search.html:615 and
  :965, `$("#search-results").on("click.search", ".img-wrapper", ...)` at :962), so appended cards
  need no rebinding.
- `data-index="{{loop.index0}}"` on each card is read by nothing.
- search.html:390-404 saves `#container_search_result`'s `outerHTML` to sessionStorage and
  restores it on a bare `/search` visit.
- Macro convention: `templates/info_tip.html` holds a macro other templates import.
- Fork-added strings are plain English, not `{% trans %}` (e.g. "Already in the library:").
- `showNotification(message, categoryClass)` is in base.html:82.
- Flat search rows carry `title`, `url`, `id`, `channel` (fallback `uploader`), `duration`
  (seconds), `channel_is_verified` (`true` or `null`), `description` (a snippet). Label-distributed
  "art tracks" have a description starting `Provided to YouTube by`. Their snippet runs the label,
  song, artist and album together, so read the artist from the channel, not the snippet.

## Design

### Data: named results

In `youtube_dl.py`:

```python
@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    id: str
    channel: str
    duration: str  # "M:SS", or "" when YouTube gives none
    channel_verified: bool
    description: str  # YouTube's snippet; art tracks start "Provided to YouTube by"

def get_search_results(query: str, count: int) -> list[SearchResult]: ...
def _parse_search_line(line: str) -> SearchResult | None: ...  # one yt-dlp JSON line
```

`get_search_results` keeps today's command and error handling; only the count, the parsing
helper and the return type change. The fixtures go through `_parse_search_line`, so the
ranking tests also cover parsing.

The route hands the template one row type per card, e.g. a frozen dataclass
`SearchRow(result: SearchResult, existing_path: str | None, official: str | None)`, so the
template reads attributes, not a tuple.

### Ranking: `pikaraoke/lib/official_rank.py` (new)

Public API:

```python
OfficialKind = Literal["video", "audio"]
def pick_artist(results: Sequence[SearchResult], query: str) -> str | None: ...
def official_kind(result: SearchResult, query: str, artist: str | None) -> OfficialKind | None: ...
def official_first(results, query, artist) -> list[tuple[SearchResult, OfficialKind | None]]:
    """Stable: the artist's videos, then their audio, then the rest in YouTube's order."""
```

The rules come from `plans/search-official-first/proto_rank.py`, a reference prototype
tested on the 14 captured searches. Write the module cleanly; the prototype is there to resolve
ambiguity, not to be copied line for line.

1. **Text.** NFKD to ASCII, lowercase, drop apostrophes, words are `[a-z0-9]+`. The "compact"
   form joins the words without spaces, so the channel `lionelrichie` equals "Lionel Richie".
2. **Art track.** Description starts `Provided to YouTube by`, or channel ends ` - Topic`.
3. **Trusted row.** An art track, or `channel_verified`.
4. **Who a row credits.** Strip bracketed text (`()`, `[]`, `【】`) and split on separators
   (` - `, `–`, `—`, `|`). The left segment is the artist side ("Artist - Song"), unless the left
   segment contains every query word and the right one does not ("Song - Artist"). Split the
   artist side on `,` `&` `x` `ft` `feat` `featuring` `with` `and`. Art tracks, and rows with no
   separator, also credit the channel's artist: the channel name minus ` - Topic` and the words
   official/vevo/music/video(s)/records/topic/channel/tv.
5. **Pick the artist.** Count credits over the trusted rows among the **first 30** results only.
   The winner needs at least 2 credits and strictly more than the runner-up; otherwise there is
   no artist and nothing moves. Page 2 also picks from the first 30 of its 60-row fetch. At 60 the
   vote drifts: Hallelujah picks "oct2026" (one channel's eight "HALLELUJAH CHALLENGE || OCT 2026"
   uploads) and Let It Go picks "letitgo".
6. **Official kind of a row, given the artist.** It gets no kind when:
   - the title matches the exclude list: lyric(s), sing-along, live, concert, cover, karaoke,
     remix, instrumental, acoustic, trailer, reaction, behind the, choreography, tutorial, lesson,
     sped up, slowed, 8d, multi-language, scene, clip, acapella / a cappella;
   - the song check fails. Of the query words not inside the artist's compact name, more than
     half must appear in the title outside brackets. This keeps "Queen - Another One Bites the
     Dust" out of "queen bohemian rhapsody". It is deliberately loose, so typos fall back to
     YouTube's order rather than lifting the wrong thing;
   - the row does not credit the artist (rule 4).

   Otherwise it must come from the artist, by any one of: an art track; a trusted channel whose
   compact name contains the artist; or a verified channel whose title says "official", "music
   video" or "audio" (label channels like DisneyMusicVEVO). It is "audio" if it is an art track or
   the title says "audio", and "video" otherwise.
7. **Why not `channel_is_verified` alone.** It is on for lyric channels (7clouds), karaoke channels
   (Sing King), the Muppets and a movie trailer. And "Queen Music videos", an unverified fan
   channel, titles its re-upload "(official music video)".

### Routes (`routes/search.py`)

- `PAGE_SIZE = 30`.
- `/search?search_string=q`: fetch `PAGE_SIZE`, pick the artist from those rows, render rows in
  `official_first` order. The "Already in the library" note keeps reading page-1 results only.
- `/search/more?search_string=q` (new): fetch `2 * PAGE_SIZE`, pick the artist from
  `results[:PAGE_SIZE]`, rank `results[PAGE_SIZE:]`, and return only the cards' HTML (no page
  shell), rendered with the same macro via `flask.get_template_attribute`. On
  `subprocess.CalledProcessError`, log it and return 502.
- Extract the `video_id -> path` library map into one helper used by both routes.

### Page (`templates/search.html`, new `templates/search_result.html`)

- Move the card `<li>` into a macro `result_card(row)` in `search_result.html`; search.html
  imports it and loops. Drop the unused `data-index`.
- Lifted cards show a small tag, "Official video" or "Official audio", beside the channel line.
- Thumbnails get `loading="lazy"`; 30 cards would otherwise fetch 30 images up front.
- A **Show more** button after `#search-results`, inside `#container_search_result` so it is part
  of the saved snapshot. It carries `data-search-string="{{ search_string }}"`, so a restored
  snapshot still knows the query. Render it only when page 1 returned a full `PAGE_SIZE`.
- A delegated click handler disables the button and fetches `/search/more`. It drops returned
  cards whose `data-ytID` is already on the page (YouTube can reshuffle between the two
  fetches), appends the rest, removes the button and re-saves the sessionStorage snapshot. If
  nothing new is left, it says "No more results" instead. On error it calls
  `showNotification("Couldn't load more results.", "is-danger")` and re-enables the button.

### Not doing

- Background or streamed fetching (decision 3). A preference for the count (decision 4).
- An outside lookup of the original artist (open decision A).
- Feeding page 2 into the "Already in the library" note, or changing its cap.
- Changing `/search`'s existing behaviour on a yt-dlp failure (it raises today).

## Fixtures

`tests/unit/data/youtube_search/<query>.jsonl`, already in the worktree and **uncommitted**:
commit them with the ranking tests (commit 2). Each file stem is the query exactly as searched,
with `_` for spaces. They are real `ytsearch60` captures from 2026-11-08, cut to `id, url,
title, channel, uploader, channel_is_verified, duration, description[:40]`. bohemian_rhapsody,
hallelujah, let_it_go_frozen and rolling_in_the_deep keep 60 rows; the other 10 keep 30.
YouTube's live results will differ from these. That is why they are frozen.

Expected, ranking the first 30 rows (position = YouTube's, 1-based):

| query | artist | videos, in order | audio, in order |
|---|---|---|---|
| bad guy | billieeilish | `DyDfgMOUjCI` (#1) | `2pnXjQCegVc` (#6) |
| bohemian rhapsody | queen | `fJ9rUzIMcZQ` (#1) | `0TF3hFevWE8` (#9) |
| dancing queen | abba | `xFrGuyw1V8s` (#1) | `P5AqvKYYQEE` (#16) |
| defying gravity | cynthiaerivo | none | `HxkLt1GXVsw` (#9) |
| dont stop believin | journey | none | `_wXLKQCTuD0` (#20) |
| hallelujah | leonardcohen | none | `ttEMYvpoR-k` (#8) |
| hello | adele | `YQHsXMglC9A` (#1) | `T1tl66trXTQ` (#16) |
| let it go frozen | idinamenzel | `YVVTZgwYwVo` (#1) | `FnpJBkAMk44` (#2) |
| never gonna give you up | rickastley | `dQw4w9WgXcQ` (#1), `LLFhKaqnWwk` (#3), `RrESvSRNpeo` (#7) | `3BFTio5296w` (#5) |
| queen bohemian rhapsody | queen | `fJ9rUzIMcZQ` (#1) | `0TF3hFevWE8` (#6) |
| rolling in the deep | adele | `rYEDA3JcQqw` (#1) | `bDtjO-R0QSo` (#5) |
| seasons of love rent | anthonyrapp | none | `1xGUTW3C3gE` (#5), `HLEPfySbfxQ` (#14) |
| shallow lady gaga | ladygaga | `bo_efYhYU2A` (#1) | `BpIf43m2ZQI` (#5) |
| someone like you | adele | `hLQl3WQQoQ0` (#1) | `22c3_LoIfZQ` (#17) |

Thin margins (winner vs runner-up credits): hallelujah 3-2, let it go 3-2, defying gravity 4-3,
seasons of love 2-1. On a tie nothing moves, so a miss costs only today's order.

Must stay unlifted (the rule each one guards):

| query | id (#) | what | rule |
|---|---|---|---|
| bohemian rhapsody | `ojRj2JK5oCI` (#21) | Pentatonix (Official Video) | not the original artist |
| queen bohemian rhapsody | `LlPcnOjSByU` (#9) | unverified "Queen Music videos" re-upload | trusted channel |
| queen bohemian rhapsody | `rY0WxgSXdEE` (#25) | Queen - Another One Bites the Dust (Official Video) | song check |
| hello | `mHONNcZbwDY` (#13) | Lionel Richie - Hello (Official Music Video) | not the picked artist |
| dancing queen | `-sVB91NTa4A` (#2) | ABBA (Official Lyric Video) | exclude list |
| rolling in the deep | `tW626Q6CFcI` (#38) | Adele, Rolling in the Deep (Acapella), page 2 | exclude list |

Page-2 drift: `pick_artist` over all 60 rows gives `oct2026` for hallelujah and `letitgo` for
let it go frozen; over the first 30 it gives the table's artists.

## Commits

Each commit: `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed>`,
`/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit -q`, an import smoke, and a read of
`git diff --cached`. Do the CLAUDE.md self-review before each one, and fill this plan's Results
log row in a separate plan-only commit, so landing can drop it cleanly.

1. **`refactor(search): named search results and one card macro`.** `SearchResult`,
   `_parse_search_line`, the `count` parameter (call site passes 10, so behaviour is unchanged),
   the `SearchRow` the template reads, the `result_card` macro, dropping `data-index`, and
   deleting the dead import in `karaoke.py`. Update `test_search_render.py` and
   `test_youtube_dl.py` to the new types. The page must render the same cards (whitespace aside)
   apart from `data-index`.
2. **`feat(search): 30 results with the original artist's official uploads first`.**
   `official_rank.py`, `PAGE_SIZE = 30`, the badge, lazy thumbnails, the fixtures, and
   `tests/unit/test_official_rank.py`: parametrized over the expected table (artist plus lifted
   IDs in order, by loading each fixture through `_parse_search_line`), the must-stay-unlifted
   table, page-2 drift, a tie gives `None`, no trusted rows gives `None`, and stable order of the
   unlifted rest. Add a render test: lifted rows come first and carry the badge.
3. **`feat(search): Show more loads results 31-60 once`.** The `/search/more` route, the button
   and its JS, and route tests: it returns cards only (no `<html`), picks the artist from the
   first 30 of the fetch, ranks rows 31-60, returns 502 on `CalledProcessError`, and page 1
   renders no button when YouTube gave fewer than 30.

**Stop after commit 3** (and its Results row). Don't land, push or retire anything. Report a
Review-due checkpoint per CLAUDE.md for commits 1-3. This is multi-file with a new algorithm,
so it is due.

## Manual checks (PR test plan)

Run from the worktree: `/home/ken/miniconda3/envs/pik/bin/python -m pikaraoke.app`. Only one
instance can run at a time; stop the main one first.

- [ ] "dont stop believin": Journey's official audio is first (YouTube has a lyrics channel there).
- [ ] "bohemian rhapsody": Queen's video, then Queen's audio, then YouTube's order; Pentatonix
      not lifted.
- [ ] Badges show on lifted cards only.
- [ ] Show more: about 30 more cards, no duplicates, button gone. Leave Search and come back:
      all cards are still there and there is no button.
- [ ] Show more with the network down: error toast, button usable again.
- [ ] Preview, Select and Add to Queue work on a card from page 2.

## Results log

| commit | hash | tests | notes |
|---|---|---|---|
| 1 `refactor(search): named search results and one card macro` | `5e8b0d3` | `tests/unit` 3366 passed; pre-commit clean on the 5 changed Python files | Rendered `/search` from a `git archive` of `225da7b` and from the commit (3 rows: escaped title, empty channel and duration, one library copy): identical after whitespace and `data-index`. `test_youtube_dl.py` had no search tests, so `TestParseSearchLine` and `TestGetSearchResults` are new there; `test_search_render.py` also gained a card test. `PAGE_SIZE = 10` is introduced here as a named constant (commit 2 sets 30). The template variable is `search_rows`. The `video_id -> path` helper waits for commit 3, when a second route needs it. |
| 2 `feat(search): 30 results with the original artist's official uploads first` | `81e57b3` | `tests/unit` 3410 passed; pre-commit clean on the 4 changed Python files | All 14 expected rows and all 6 must-stay-unlifted rows hold; page-2 drift is `oct2026` / `letitgo` over 60 rows. Two departures from `proto_rank.py`: the collab split uses `\bft\b\.?` and `\bfeat\b\.?` (the prototype's `\bft\.?` / `\bfeat\.?` split "Featherstone" into "herstone"; test `feat-inside-a-word-is-not-a-split`), and the song check drops `compact(w) not in artist`, which equals `w not in artist` for a normalised word. Live `get_search_results(q, 30)` through the new code: "dont stop believin" lifts Journey's art track to #1; "bohemian rhapsody" gives Queen video, Queen audio, then YouTube's order. In 12 live runs of the app's own command, 1 returned all 30 rows with no `channel`, `uploader`, `channel_is_verified` or `description` (YouTube-side; `channel_url` was present), and 1 returned only 6 verified rows and 25 descriptions; the empty one finds no trusted rows, so nothing is lifted and the channel line is absent, as it is today. The "Already in the library" note still reads the page-1 results in YouTube's order, not the lifted order. |
| 3 `feat(search): Show more loads results 31-60 once` | `a610196` | `tests/unit` 3417 passed; pre-commit clean on the 2 changed Python files | Route tests are in `test_search_render.py` (its app has the real templates). Mutation check: voting over all 60 rows instead of the first 30 fails `test_more_picks_the_artist_from_the_first_page_and_ranks_the_second`. The `video_id -> path` map moved into `_search_rows`, which both routes call. Browser check in headless Chrome against the real templates and routes over canned results (throwaway server on a spare port, not the app): 30 cards and the button; one click appends 29 (one repeated card dropped), no repeated IDs, button gone; the saved snapshot holds 59 cards and no button; a bare `/search` visit restores all 59 with no button; Select on a page-2 card opens the preview modal; a 502 shows the error toast, re-enables the button and leaves 30 cards; a second page of only repeats says "No more results"; no page errors. Not run: the real app (`python -m pikaraoke.app`), so the Manual checks below are still open. |
