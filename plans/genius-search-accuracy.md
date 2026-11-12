# Genius search accuracy: find the right song, and default to it

Model: not assigned. Evaluation by Claude Fable 5.2, 2026-11-11. No spec yet.

Status: **evaluation only, no code changed.** Branch `genius_search_accuracy`, split on
2026-11-12 (at Ken's request, the two halves being unrelated) from `lyric_search_accuracy`,
which was cut from `dev` at `1016e20` to carry the combined plan between computers. The LRCLIB
half lives on `lrclib_search_accuracy` (`plans/lrclib-search-accuracy.md`); the combined plan
is kept at `archive/lyric_search_accuracy`. This branch holds no code. Before code starts it is
rebased onto `dev` after `search_official_captions` lands (see Rulings).

## Pick up here

1. On Ken's other computer: rerun the Genius replay against that library ("Rerun on the other
   computer"). Its library is about 30 songs larger.
2. Ken rules on C with the film-year results in hand ("Genius: film year rule").
3. Then the spec: the Genius phases need nothing more.
4. Stop before any code until the spec exists.

Evidence (replay scripts and cached service answers) is in `plans/genius-search-accuracy/`.
Committed: the scripts, the Genius answers (`genius_raw.json`, `genius_year_raw.json`) and
`truth_names.json` (the truth list without lyric lines). Gitignored there, local to each
computer: `truth.json` (with lyric lines). See "Reproduce".

Every count in the Results log is for the first computer's library as of 2026-11-11 (157
songs).

## Rulings (Ken, 2026-11-11)

- **A. Scope and order: one plan, three phases** (ruled for the combined plan; the split of
  2026-11-12 moved phase 3 to `plans/lrclib-search-accuracy.md`).
  1. Genius: shared query builder, ladder and ranking on all four entry points, plus the
     repair page prefill (Genius items 1, 2, 4, 7).
  2. Genius: film recordings and the year shown per hit (items 5, 6).
- **Item 3 (channel, vote, typed term).** The typed search term goes into phase 1 as a ladder
  rung. Channel and official-artist vote are not in phases 1-2.
- **Landing order: `search_official_captions` lands on `dev` first** (Claude's recommendation,
  asked for by Ken; the assumption for the rest of this plan). It is specced with fixtures
  committed and Sonnet has not started; it edits `routes/search.py` and rewrites the vote in
  `official_rank.py`. This branch is cut from `dev` after it lands.
- **B. Default pick: preselect only when title and artist both match**, on all four entry
  points. The search page stops preselecting whatever is first. Film-named songs have no
  artist to match; their default follows C.
- **C. Film recordings: measure first** (done, see "Genius: film year rule"; ruling pending).
  Ken's note: the library's file names are the 11-08 standardized names, not the YouTube
  titles. So the year exists only where a curated file name exists (library tools); a new
  download on the search page has no year to compare.
- **D. Extra requests: accepted.** Up to three Genius calls on the search page, two elsewhere,
  stopping early on a full match.
- **Fixtures: commit the Genius answers and the song-name truth list** (no lyric text).

## What the spec is judged on (Ken, 2026-11-11)

- **Phase 1 is judged on the YouTube-title replay for every entry point.** The shared query
  builder gets the same input everywhere and the raw title is the hard case. The curated-name
  replay is kept as a check that renamed songs do not get worse.
- Original titles for that replay: the bundle's recorded name first, then a lookup by YouTube
  ID for songs whose bundle no longer holds it. Songs without an ID stay out of it.
- The app itself looks nothing up: an entry point searches from the file name it is given,
  which is the YouTube title on a fresh download and the curated name after a rename.
- **Phase 2 (film year) only helps renamed songs**; a fresh download has no year. To weigh in
  ruling C.

## What exists (read 2026-11-11)

- One search call: [genius.py:98](../pikaraoke/lib/genius.py#L98). Asks for 20 hits, keeps
  type `song`, drops Genius's own accounts (translations) except Romanizations, returns the
  first 8 in Genius's order. Returns nothing on any failure.
- Route `/lyrics_search`: [routes/search.py](../pikaraoke/routes/search.py), cleans the query
  with `clean_genius_query` ([genius_lyrics.py:200](../pikaraoke/lib/genius_lyrics.py#L200)):
  strips emoji and the noise-word list, keeps brackets.
- Four entry points, two different starting queries:
  - **Search page** ([search.html](../pikaraoke/templates/search.html), `runLyricsSearch`): the
    raw YouTube title. Falls back to the typed search term **only on zero hits**. The dropdown's
    first option (Genius's first hit) is selected by default.
  - **Pick pass, CLI prompt**: `default_query`
    ([library_regen.py:442](../pikaraoke/lib/library_regen.py#L442)) = file name minus the ID,
    then `clean_search_query` (drops all brackets, then the noise words). No preselected hit.
  - **Repair page** ([song_repair.html](../pikaraoke/templates/song_repair.html)): the Genius
    box starts empty. No preselected hit.
- The noise-word list (`NOISE_WORDS` in
  [metadata_parser.py](../pikaraoke/lib/metadata_parser.py)) is applied anywhere in the text,
  not only in brackets or at the end. The rename tidy in the same file (`_strip_trailing_junk`)
  already limits itself to trailing brackets and trailing words.
- A Genius hit also carries a release year, page views, an `instrumental` flag and a lyrics
  state. None is used or shown.

## Method

- Ground truth: the 157 library songs, whose file names Ken curated on 11-08 as
  `Artist - Title` (87 songs) or `Film (Year) - Title` (70 songs). 17 bundles also record the
  Genius song the admin picked.
- A Genius hit counts as right when its id is the recorded pick, or its title equals the
  curated title (brackets ignored) and, for artist-named songs, it shares an artist word.
  **For film-named songs only the title is checked, so a cover or another cast passes.**
- The title check cannot read Chinese titles. Those rows were read by eye and the counts
  below include that correction.
- "Search page" replay uses the name each bundle recorded at its last run as the YouTube
  title. That is the YouTube title for most songs, not all. The live page's fallback to the
  typed search term is not replayed (the typed terms are not recorded).
- **Which names each replay used** (checked 2026-11-11 after Ken's question; a download is
  saved under its YouTube title, so that is what every entry point sees until a rename):
  - Search page rows: the YouTube title for 96 songs; for 7 more the bundle had recorded the
    curated name, which stood in. 103 replayed.
  - Library tools rows: curated names only. They describe a renamed library, not a fresh
    download.
  - "Genius: film year rule": curated names only.
- **Where an original title comes from.** The bundle's `song_stem` (the file name at the
  song's last pipeline run) when it differs from today's name: 96 songs. Nothing else in the
  app keeps the YouTube title. 19 more files carry a YouTube ID but no recorded original
  title; a title lookup by ID (yt-dlp) would fill those. 42 files have no ID (movie splits)
  and never had a YouTube title.

## Results log (2026-11-11)

### Genius: right hit's position

| Path | Songs | First | Listed 2-8 | Not listed |
|---|---|---|---|---|
| Search page today, artist-named | 82 | 69 | 1 | 12 |
| Search page today, film-named | 21 | 2 | 0 | 19 |
| Search page, prototype, artist-named | 82 | 77 | 1 | 4 |
| Search page, prototype, film-named | 21 | 18 | 0 | 3 |
| Library tools today, artist-named | 87 | 86 | 1 | 0 |
| Library tools today, film-named | 70 | 45 | 7 | 18 |
| Library tools, title only, artist-named | 87 | 44 (not eye-corrected) | 26 | 17 |
| Library tools, title only, film-named | 70 | 57 | 10 | 3 |
| Library tools, prototype, artist-named | 87 | 87 | 0 | 0 |
| Library tools, prototype, film-named | 70 | 69 (title only, see below) | 0 | 1 |

Word order and the dash make no difference (`Artist - Title`, `Artist Title`, `Title Artist`
gave the same counts within one song).

Search page today, the queries that were not first (as sent after cleaning; all zero hits
unless noted):

| Query sent | Hits |
|---|---|
| `A-Lin《幸福在歌唱 Happiness Is Singing》 - 電影《陽光女子合唱團》幸福版主題曲` | 0 |
| `Ariana Grande, John Legend - Beauty and the Beast (From Beauty and the Beast - )` | 6, all "Deleted Artist 2" |
| `BTS (방탄소년단) 'Butter' MV` | 0 |
| `Céline Dion - Ashes (from 'Deadpool 2' Motion Picture Soundtrack)` | 0 |
| `Céline Dion - My Heart Will Go On ( 25th Anniversary Alternate )` | 0 |
| `Ed Sheeran & Rudimental - Bloodstream [ YTMAs]` (with soft hyphens) | 0 |
| `정국 (Jung Kook) '3D (. Jack Harlow)' Performance` | 0 |
| `정국 (Jung Kook) 'Seven (. Latto)' Performance` | 0 |
| `정국 (Jung Kook) 'Standing Next to You' MV (Choreography ver.)` | 0 |
| `#NSYNC - This I Promise You ( )` | 3, "Radio Edit" first, the song second |
| `Here I Go (. Charli xcx) - Uncensored` | 0 |
| `Whitney Houston - I Will Always Love You ( 4K )` | 0 |
| `ZAYN, Zhavia Ward - A Whole New World (End Title) (From 'Aladdin')` | 0 |
| `Mena Massoud, Naomi Scott - A Whole New World (from Aladdin) ( )` | 0 |
| `Naomi Scott - Speechless (from Aladdin) ( )` | 0 |
| `Beauty and the Beast (1991) - Be Our Guest [UHD]` | 0 |
| `Beauty and the Beast (1991) - Belle [UHD]` | 0 |
| `Demi Lovato, Joe Jonas - This Is Me (From 'Camp Rock' Sing-Along)` | 0 |
| `Josh Gad - In Summer (From 'Frozen' Sing-Along)` | 0 |
| `“Golden” KPop Demon Hunters Sony Animation` | 0 |
| `'Soda Pop' KPop Demon Hunters Sony Animation` | 0 |
| `“Takedown” Choreography KPop Demon Hunters Netflix` | 0 |
| `‘Your Idol’ KPop Demon Hunters Netflix` | 0 |
| `Mulan I'll Make a Man Out of You @disneykids` | 0 |
| `Pocahontas - Colors of the Wind (Blu-ray 1080p )` | 0 |
| `The Lion King - Hakuna Matata I 4K Ultra` | 0 |
| `Jodi Benson - Part of Your World (From 'The Little Mermaid')` | 0 |
| `Stay Gold ( ) from The Outsiders – A New Broadway Musical.` | 0 |
| `'Defying Gravity' - Wicked 20th Anniversary Edition WICKED the Musical` | 0 |
| `#OutOfOz - 'For Good' Performed Kristin Chenoweth and Idina Menzel WICKED the Musical` | 0 |
| `'Popular' - Wicked 20th Anniversary Edition WICKED the Musical` | 0 |
| `Wicked - For Good (2025) 4K - The Girl in the Bubble (7 8) Movieclips` | 0 |

Search page prototype, still not first: Mulan (title reduced to `Mulan`), NSYNC `Girlfriend`,
`Gone`, `Pop` (the upload's title is only the song name), `Here I Go` (second), The Outsiders
`Stay Gold` (zero hits), Wicked For Good `The Girl in the Bubble`, ZAYN `A Whole New World`
(Broadway cast first).

Library tools today, film-named, first hit where it was not the song:

| Query | First hit |
|---|---|
| `Frozen - Let It Go` | I'm a Hoe Frozen (Let It Go Parody) / Meadows |
| `KPop Demon Hunters - Golden` | The TikTok Poop Song (parody) / Peter Knetter |
| `KPop Demon Hunters - Your Idol` | German Version / PeachyFranny |
| `Moana - How Far I'll Go` | Moana (How Far I'll Go) / Da Tweekaz |
| `Moana - Shiny` | Time to Shine / Lil' Kim (song not listed) |
| `Mulan - I'll Make a Man Out of You` | Finnish Edition / Devastus (song not listed) |
| `Pocahontas - Colors of the Wind` | "in the style of Dvorak" / English Chamber Orchestra |
| `Wicked - Defying Gravity` | Wicked - defying gravity / Gaynor ellen |
| `Wicked - For Good` | Commentary (Wicked: For Good) / Stephen Schwartz |
| `The Last Five Years - <any of 14 songs>` | zero hits |
| `The Outsiders - Stay Gold` | zero hits |
| `Wicked For Good - The Girl in the Bubble` | zero hits |

Library tools prototype, film-named: a hit with the right title is first for 69 of 70, but
the recording behind it, read by eye:

| Song | Prototype's first hit |
|---|---|
| Frozen (2013): Let It Go, In Summer, Love Is an Open Door, Do You Want to Build a Snowman | Original Broadway Cast of Frozen |
| Moana (2016): How Far I'll Go, You're Welcome | Moana Karaoke |
| Wicked (2003): Popular | Reparto mexicano de Wicked 2013 |
| Wicked (2003): Defying Gravity | Awiting Wicked Singers |
| The Outsiders (2024): Stay Gold | Jun Matsumoto |
| Camp Rock (2008): This Is Me | Keala Settle & The Greatest Showman Ensemble |
| Aladdin (2019): A Whole New World | Original Broadway Cast of Aladdin |
| Tangled (2010): When Will My Life Begin | Disney Cruise Line cast |
| The Last Five Years (2014): 8 of 14 songs | 2002 cast (Sherie Rene Scott, Norbert Leo Butz), not the film's |
| The Last Five Years: I'm a Part of That | wrong song (Genius titles it "A Part of That") |

For comparison, Genius's own list for `Let It Go` puts Idina Menzel (2013, 1.4 M views) first;
the Broadway cast hit has no view count.

Other counts over all 805 cached Genius queries: 114 returned nothing; 4 returned only
"Deleted Artist" pages in the top three; 56 had a page whose lyrics are not marked complete in
the top eight; 262 had Genius-account hits that today's filter removes.

Cleaner behaviour, run directly:

| Input | `clean_genius_query` | `clean_search_query` |
|---|---|---|
| `Stand By Me` | `Stand Me` | `Stand Me` |
| `Live and Let Die` | `and Let Die` | `and Let Die` |
| `Music - Madonna` | `- Madonna` | `- Madonna` |
| `Remix to Ignition` | `to Ignition` | `to Ignition` |
| `정국 (Jung Kook) 'Seven (feat. Latto)' Official Performance Video` | `정국 (Jung Kook) 'Seven (. Latto)' Performance` | `정국 'Seven ' Performance` |
| `Céline Dion - My Heart Will Go On (Official 25th Anniversary Alternate Music Video)` | `... ( 25th Anniversary Alternate )` | `Céline Dion - My Heart Will Go On` |
| `周杰倫 Jay Chou【晴天 Sunny Day】-Official Music Video` | `周杰倫 Jay Chou【晴天 Sunny Day】-` | same |

No current library name loses a real word to the noise list (0 of 157).

### Genius: film year rule (2026-11-11, decision C)

The first cache did not keep the release year, so the two prototype queries (`Film Title`,
`Title`) were fetched again for the 70 film-named songs: 140 Genius calls, cached in
`genius_year_raw.json` (`genius_year.py`). Hits merged, "Deleted Artist" and instrumental
pages dropped, then ordered three ways. First hit read by eye against the film's own recording:

| Order | Film's recording first | Unsure | Other |
|---|---|---|---|
| Title match, film-name word in artist, not a variant, views (no year) | 38 | 0 | 32 |
| Title match, year within 1 of the file name's, not a variant, views | 62 | 2 | 6 |
| Title match, year within 1, film-name word in artist, not a variant, views | 64 | 0 | 6 |

Of the full-title hits, 500 carry a year and 78 do not.

Year-first order, first hit where it was not the film's recording:

| Song | First hit | Why |
|---|---|---|
| Aladdin (2019): A Whole New World | ZAYN & Zhavia, "(End Title)", 2019 | pop single, same year |
| The Lion King (1994): Can You Feel The Love Tonight | Elton John, 1994 | pop single, same year |
| Rent (2005): Another Day | Original Broadway Cast of Rent, dated 2005 on Genius | stage-cast page carries the film's year and more views than the film cast's |
| Rent (2005): I'll Cover You | film cast, "(Reprise)" | the title's own word "Cover" switched the variant test off for every hit |
| The Last Five Years (2014): I'm a Part of That | Vitamin C, I'm Not That Kind of Girl | Genius titles it "A Part of That" |
| Flight of the Conchords (2007): Hurt Feelings | Mac Miller, 2018 | the series ran 2007-2009; the song is dated 2009, 2 years off |
| Rent (2005): One Song Glory, Today 4 U (unsure) | a second 2005 page credited to the singers, more views than the film-cast page | |

Adding the film-name word fixes Hurt Feelings and the two unsure rows, and puts a dubbed page
first for Hakuna Matata ("The Lion King OST Mandarin", 1994, no views).

Not covered: the search page, where there is no curated year (Ken's note under ruling C).

## Proposed work (candidates, not specced)

1. **One query builder for every entry point**, replacing the two cleaners. Remove junk only
   inside brackets or at the end (reuse the rename tidy's rule), drop a bracket the removal
   empties, drop "from <film>" brackets, hashtags, @handles and soft hyphens, and lift a quoted
   title (`'Seven'`, `“Golden”`, `【晴天】`). Fixes the debris and the "Stand By Me" loss.
2. **A short ladder of queries**: the full cleaned name, then the title alone, results merged.
   Stop early when a rung returns a hit matching both title and artist.
3. **Use what the page already knows**: the upload's channel, the official-artist vote the
   search page already takes, and the typed search term, as extra query words and as ranking
   evidence. Covers title-only uploads (`Girlfriend`, `Gone`, `Pop`).
4. **Rank on our side** before listing: title match, then artist match, then not a variant
   (parody, karaoke, instrumental, commentary, radio edit, translation, unless the song's own
   name says so), then page views. Drop "Deleted Artist" pages and pages flagged instrumental.
5. **Film songs**: compare the file name's year with the hit's release year (decision C).
6. **Show more per hit**: year and artist line, so versions can be told apart.
7. **Prefill the repair page's Genius box** with the same starting query the pick pass uses.

### Prototype used for the "prototype" rows

In `plans/genius-search-accuracy/genius_sim.py`. Ladder: a quoted title plus the rest, the
quoted title alone, the name with junk brackets dropped, the name with all brackets dropped,
the part after ` - `; at most three calls for the search page, two for library tools. Order:
full title match, any artist word matches, not a variant, share of title words matched, page
views. It has no channel name, typed term, or year.

## Not measured

- **Library tools on a file still carrying its YouTube title** (a fresh download before any
  rename). They clean the name with `clean_search_query`, the search page with
  `clean_genius_query`, so the search page rows do not cover it. Needs about 96 new Genius
  searches on the first computer's library.
- The 19 songs with a YouTube ID but no recorded original title (see Method).
- The search page with the typed term as fallback, and with real channel names.
- The film-year rule on the search page, where no curated year exists (library tools were
  measured 2026-11-11, see "Genius: film year rule").
- Songs outside this library: no other languages beyond the four Chinese and four Korean-artist
  songs, no live or remix requests.

## Corrections to the chat summary of 2026-11-11

- Library tools, artist-named: reported as 82 first today rising to 87. The four Chinese-title
  songs were already first today; the title check could not read them in either run. Today is
  86 of 87 and the prototype's gain is one song (NSYNC, "Radio Edit" first).
- Search page: reported as 70 first today and 94 with the prototype; with 龍捲風 read by eye it
  is 71 and 95 of 103.

## Related entries in `plans/open-issues.md`

- "The pick box's starting search keeps trailing words of a long YouTube title" (Defying
  Gravity): the same cause as the zero-hit rows above.
- "A service outage reads as no results": untouched here; a ladder makes it more visible, since
  a failed rung would look like an empty one.
- "The default Genius query strips all CJK characters": Chinese text passed through both
  cleaners in these runs (emoji range changed in `63f0b7c`). Looks stale; not struck.

## Reproduce

From the repo root, with the `pik` env. All scripts are read-only on the library and cache
every service answer beside themselves, so a rerun makes no calls unless a query is new.

```bash
cd plans/genius-search-accuracy
PY=/home/ken/miniconda3/envs/pik/bin/python
$PY collect.py              # library -> truth.json (names, recorded picks, lyric lines)
$PY genius_probe.py         # Genius hits for today's two starting queries -> genius_raw.json,
                            # and truth_names.json (truth.json without the lyric lines)
$PY genius_eval.py -v       # today's position of the right hit, both paths
$PY genius_variants.py -v   # query shapes for the curated names
$PY genius_sim.py curated 2 -v   # prototype, library tools (add -top for the film first hits)
$PY genius_sim.py raw 3 -v       # prototype, search page
$PY genius_year.py          # film-year rule; 140 Genius calls uncached -> genius_year_raw.json
```

`genius_year.py` as left orders by year then film-name word (the third row of its table); the
second row is the same key without `artist`.

`genius_probe.py` reads the Genius token from `~/.pikaraoke/config.ini`; nothing in the folder
stores it. `collect.py` reads `~/pikaraoke-songs`, so a rename since 11-11 changes the truth
set.

### Rerun on the other computer

Check first:

- The scripts import `pikaraoke`; the env there must have the repo installed or on the path.
- `collect.py` hardcodes `~/pikaraoke-songs`. Point `LIB` at that computer's library if it
  lives elsewhere.
- The Genius token is in that computer's `~/.pikaraoke/config.ini`.
- **Whether the 11-08 standardized names were applied to that library.** Every script splits
  the file name on ` - ` and reads `Film (Year)` from the left part. On unrenamed files the
  truth names, the film/artist split and the film-year rule are all wrong.

Also add there, before the spec (neither is scripted yet):

- The missing baseline: library tools today on the YouTube title, i.e. Genius hits for
  `clean_search_query(old_title)` per song, scored like the other rows.
- A title lookup by YouTube ID for songs whose bundle does not hold the original title, so
  the YouTube-title replay covers every file with an ID.

Then run the Reproduce block top to bottom. Calls made there: Genius only for queries not
already in the committed caches (the roughly 30 new songs).

Recording the rerun:

- Log it as a second dated run under the Results log with that library's song count. Do not
  merge its counts into the 157-song tables.
- `genius_probe.py` rewrites `truth_names.json` for that library; the first computer's list
  stays in git history (`archive/lyric_search_accuracy`).
- The by-eye readings (Chinese titles, the film recording behind each first hit) have to be
  redone for the new songs.
- Commit the grown Genius caches and the new `truth_names.json`. Never `git add -f` the ignored
  file.
