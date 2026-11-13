# Genius search accuracy: find the right song, and default to it

Model: not assigned (see "Where Fable is needed"). Evaluation by Claude Fable 5.2, 2026-11-11
and 2026-11-13. No spec yet.

Status: **evaluation only, no code changed. Rerun on the second computer done and ruled on
2026-11-13; the spec is next.** Branch `genius_search_accuracy`, split on
2026-11-12 (at Ken's request, the two halves being unrelated) from `lyric_search_accuracy`,
which was cut from `dev` at `1016e20` to carry the combined plan between computers. The LRCLIB
half was closed with no build on 2026-11-13 and is kept at `archive/lrclib_search_accuracy`
(`plans/lrclib-search-accuracy.md`); the combined plan is kept at
`archive/lyric_search_accuracy`. This branch holds no code. Before code starts it is
rebased onto `dev` after `search_official_captions` lands (see Rulings).

## Pick up here

1. Done 2026-11-13: the rerun on the second computer, on raw YouTube titles ("Rerun on the
   second computer"). The library there is 248 songs, 206 with a YouTube ID.
2. Done 2026-11-13: Ken's rulings on the builder and on C ("Rulings (Ken, 2026-11-13)").
3. Next: the spec, by Fable ("Where Fable is needed" says why and what it has to settle).
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
- **C. Film recordings: measure first** (done, see "Genius: film year rule"; ruled 2026-11-13,
  below).
  Ken's note: the library's file names are the 11-08 standardized names, not the YouTube
  titles. So the year exists only where a curated file name exists (library tools); a new
  download on the search page has no year to compare.
- **D. Extra requests: accepted.** Up to three Genius calls on the search page, two elsewhere,
  stopping early on a full match.
- **Fixtures: commit the Genius answers and the song-name truth list** (no lyric text).

## Rulings (Ken, 2026-11-13)

In chat, after the rerun ("Rerun on the second computer"), on the author's four numbered
points.

- **Raw YouTube titles only.** "you don't need to tune for today's filenames, as they are
  renamed after going through the pipeline, and the search improvements are meant to improve
  the inputs to the pipeline". The curated-name replay of "What the spec is judged on" is no
  longer a check the spec has to pass.
- **The spec takes the new builder's rules** ("What the new builder does differently") in
  place of the 11-11 prototype's: "yes, take the new builder". The recommendation he answered
  came with "the unseen-titles fixtures added to the spec's tests so it is not judged on your
  library alone".
  - The author's reading, not ruled in words: this brings the channel name into phase 1,
    where "Item 3" above had left channel out. The official-artist vote stays out.
- **C ratified** as recommended: the year is used when the video title carries one, as part of
  phase 1's order; there is no separate film-year phase; the year and the artist line shown
  per hit (item 6) stay. So ruling A's phase 2 is item 6 alone.
- **The LRCLIB half is closed with no build** and its branch retired as
  `archive/lrclib_search_accuracy`.

## Where Fable is needed

Ken, 2026-11-13: note where Fable's extra intelligence would be needed.
`plans/lrclib-shift-check.md` (branch `lrclib_fit_pick`) gives Fable as available to
2026-11-16.

**Fable: the spec.** It is the one step here that is design, and these are the points a
weaker spec would get wrong:

1. **Which of `builder.py`'s rules become contract.** It holds about thirty patterns, shaped
   on the library's 206 titles and then on the misses of the 176 unseen ones. Both sets are
   now spent as tests of it. The spec has to say which rules are pinned by fixtures, which are
   a word list anyone may extend, and what fresh titles a later gate is read on.
2. **The order of the merged hits (rule 6).** Its levels trade against each other: the
   ablation row shows the same change fixing Hakuna Matata and losing Savages and Take Me or
   Leave Me, and no order tried gets both the Lion King songs and the KPop Demon Hunters
   songs. A change made to pass one title breaks another, and only the by-eye film read shows
   it.
3. **What reads as an artist's channel.** `builder.py` uses a word list (`NOT_ARTIST`).
   `official_rank.py` on `search_official_captions` already tells label channels from an
   act's own and votes on the artist. The two need one definition, across two branches with a
   ruled landing order.
4. **What each entry point is given.** The search page has the title and the channel. A
   direct link, a playlist row and `add_songs` have what the download returns. Library tools
   and Repair have a file name, where `|`, `/`, `"`, `:` and `?` were replaced and nothing
   keeps the channel. Whether the title and channel are stored at download is a design call
   that touches "the app itself looks nothing up".
5. **A gate that can fail.** The answer key passes a film-named song on its title alone, so a
   replay count cannot show a wrong recording. The spec has to pre-register what is read by
   eye and what number stops the build.

**Opus, by the standing rule, with Fable only if Opus is unsure:** the read of that gate after
the build. The part most likely to need Fable is telling the recordings apart (film cast,
stage cast, the pop single, a dub) for the film-named first hits.

**Sonnet:** everything after the spec: the builder as app code, the four entry points, the
year and artist line per hit, the repair prefill, tests from the fixtures. One executor rule
for the spec to carry: a title that fails is a STOP for the judge, never a new pattern added
to make it pass.

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

## Rerun on the second computer (2026-11-13, Fable 5.2)

Library `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`: 248 songs, 206 with a YouTube
ID. Scripts, the answer key and the cached Genius answers are in
`plans/genius-search-accuracy/run2/`. The first run's scripts were not rerun: they read the
song's identity from a curated file name, and 97 of this library's 206 YouTube files still
carry their YouTube title.

Ken, 2026-11-13, in chat: "you don't need to tune for today's filenames, as they are renamed
after going through the pipeline, and the search improvements are meant to improve the inputs
to the pipeline". So every row below replays the **raw YouTube title**; nothing replays a
file name. The 42 files without an ID (movie splits) stay out.

### Method

- Titles and channel names: YouTube's public oEmbed, one lookup per ID (`yt_meta.py`,
  `yt_meta.json`). All 206 answered; the titles equal Ken's `youtube_titles.txt`.
- Answer key (`truth_build.py`, `truth_names.json`): title and artist per song, parsed from
  the file name where it is curated, written by hand where it is not (50 overrides, Chinese
  titles included with both scripts). 163 artist-named, 43 film-named (a film or cast where
  the artist would be). 54 bundles record the Genius song picked.
- A hit is right when it is the recorded pick, or its title equals the key's (brackets
  ignored) and, for artist-named songs, it shares an artist word. Chinese titles are compared
  as written, so no by-eye pass was needed for them.
- **Film-named songs pass on the title alone**, so each strategy's film count is a ceiling.
  The new builder's 43 film first hits were read by eye; the other strategies' were not.
- Up to three Genius calls a song, stopping early as each strategy defines.

### Right hit's position, 206 YouTube titles

| Strategy | Artist-named (163): first / 2-8 / not listed | Film-named (43): first / 2-8 / not listed | Calls a song |
|---|---|---|---|
| Search page today (`clean_genius_query`) | 119 / 1 / 43 | 4 / 0 / 39 | 1 |
| Library tools today (`clean_search_query`) | 150 / 1 / 12 | 24 / 1 / 18 | 1 |
| The 11-11 prototype (`genius_sim.py`'s ladder and order) | 157 / 1 / 5 | 32 / 0 / 11 | 1.41 |
| New builder (`builder.py`) | 163 / 0 / 0 | 43 / 0 / 0 | 1.33 |

Of today's 83 search-page misses, 80 are queries Genius answers with no hits at all; of the
library-tools cleaner's 32, 28.

New builder, read by eye: 7 first hits have the right title and are the wrong recording, so
199 of 206.

| Song (video) | New builder's first hit |
|---|---|
| Camp Rock 2: It's On | Eazy-E, 1993 (the cast page is 5th) |
| The Lion King: Can You Feel The Love Tonight | 1997 Broadway cast |
| The Lion King: Hakuna Matata | 1997 Broadway cast |
| The Outsiders: Stay Gold | Jun Matsumoto, 2014 (the cast page is 4th) |
| Wicked the Musical: Popular | The Weeknd & Madonna, 2023 |
| Wicked (channel "Wicked Movie"): What Is This Feeling | Chenoweth & Menzel, 2003, the stage recording |
| *NSYNC: Thinking Of You (I Drive Myself Crazy) | an *NSYNC page of that title with a version suffix, no page views |

None of the seven is preselected.

### The default pick (ruling B)

"Preselected" = the strategy's own test for "title and artist both match" holds for its first
hit.

| Strategy | Preselected | of which not the right hit | Left open | of which the first hit was right |
|---|---|---|---|---|
| Search page today | 206 (always the first hit) | 83 | 0 | |
| Prototype | 173 | 8 | 33 | 24 |
| New builder | 163 | 0 (by eye too) | 43 | 43 by the key, 36 by eye |

The prototype's eight: Camp Rock 3 One Beat Away and Play My Music, Into the Unknown,
Breaking Free, Where You Are, Prince Ali, ZAYN A Whole New World, Here I Go. In seven its
quote rule took the film inside `(From "Frozen 2"/Sing-Along)` for the song's title and
searched for the film alone.

### What the new builder does differently

`builder.py`, written during this rerun while looking at these 206 titles (see "Unseen
titles" for what that costs).

1. **Reads the title into parts first**: title, artist, film, year. A `(From "Film")` bracket
   names a film; a quoted or 【】/《》 phrase is the title; junk brackets, junk tail words,
   hashtags, handles and label names go; of `A - B` or `A | B` either side may be the title.
2. **Ladder from the parts**: artist + title with its brackets' words, artist + bare title,
   film + title, title alone.
3. **The channel stands in for the artist** when the title names none and the channel does
   not read as a label or studio (`I Just Might` on channel "Bruno Mars").
4. **"Artist matches" means the hit's primary artist is named** by the title or the channel.
   A cast credit that only carries the film's name ("Original Broadway Cast of Frozen" for a
   Frozen video) is not an artist match.
5. **The ladder stops, and the hit is preselected, only on such a match on a page with page
   views.** Otherwise the title-alone query is always added.
6. **Order of the merged hits**: title matches; a named artist on a viewed page; the year,
   when the title carries one; a named artist on an unviewed page; not another version (remix
   and the like by title; a stage cast, a dub, or a film cast against a title that says
   "Musical", by artist line); the film's name in the artist line of a viewed page; page
   views.
7. Dropped before ordering: "Deleted Artist" pages and pages flagged instrumental.

Ablations on the 206 (the key's counts):

| Variant | Artist-named first | Film-named first | Preselected |
|---|---|---|---|
| New builder | 163 | 43 | 163 |
| Without the channel name | 162 (Here I Go 2nd) | 43 | 153 |
| Step 6 without "film's name in the artist line" and "named artist on an unviewed page" | 158 | 43 by the key; by eye it fixes Hakuna Matata, puts Elton John's single first for Can You Feel The Love Tonight, and loses Savages (Young Pappy) and Take Me or Leave Me (the stage cast) | 163 |

At two calls a song, the limit ruling D sets away from the search page: 163 and 41 by the
key (Breaking Free and It's On are not listed), 1.24 calls; without the channel name 162 and
41. The library tools and Repair have no channel to use.

### Unseen titles

The builder was shaped on the library's titles, so it was also run on titles it had not
seen: the frozen YouTube searches of branch `search_official_captions`
(`tests/unit/data/youtube_search`, 44 searches). Per search the first four results whose
title carries the searched song's title and that are not in the library: 176 videos (official
uploads, lyric videos, fan clips, live clips, covers, and some videos that are not the song).
`holdout.py`. "Right title first" checks the title only; 116 of the videos come from a
search that names an act.

| Strategy | Right title first | No hits at all | Named act: its page first | Preselected | of which another act's page | Calls |
|---|---|---|---|---|---|---|
| Search page today | 92 | 83 | 60 of 116 | | | 1 |
| Prototype | 143 | 20 | 87 | 91 | 7 | 1.41 |
| New builder, first pass | 138 | 21 | 89 | 79 | 4 | 1.56 |
| New builder, after one round of fixes | 152 | 12 | 95 | 86 | 4 | 1.65 |

The first pass is the clean number. The fixes were read off its misses, so the last row is no
longer a test on unseen titles. They were: the other side of a dash counts as a title equally
when no artist is named (`Seasons of Love - Rent`); `//` and `│` separate like a pipe; a
double- or curly-quoted title may hold an apostrophe (`“You're Welcome”`); junk words go
before a trailing bracket and inside a part (`Shallow Sing-Along (Lady Gaga ...)`, `Frozen
lyrics`); `Scene` and `Clip` end a title. The 206-song rows above are from the builder after
those fixes (before them: 206 by the key, 1.29 calls).

The new builder's four "another act's page": 2Pac - Bad Guy, Ed Sheeran - Perfect Symphony,
overtonight - mirrors demo, Van Morrison - Someone Like You. Each is the video's own song,
returned by a search for a different song of that name. The prototype's seven are those four
plus Dancing Queen (page "King & Queen") and Bohemian Rhapsody twice (page "LEE HI x BOHEMIAN
RHAPSODY").

### The film year (ruling C) on raw titles

6 of the 43 film-named YouTube titles carry a year (`Beauty and the Beast (1991) - ...` twice,
`RENT 2005 : ...`, `... - Rent (2005)`, `Wicked (2024) 4K - ...`, `Wicked: For Good (2025)
...`), and one artist-named title does (`Reflection (2020)`). The builder uses it in step 6;
the other 37 film-named titles have none. A curated year exists only after a rename, which
Ken's 11-13 note puts outside what the search is for.

### Not done in this rerun

- The typed search term and the search page's voted artist: neither is recorded. The channel
  name is the nearest thing measured.
- A by-eye read of the prototype's and today's film first hits.
- Videos without an ID, and any replay of a file name.

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

(As of 2026-11-11. The first two items were measured on 2026-11-13, see "Rerun on the second
computer".)

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

### The second computer's run (2026-11-13)

```bash
cd plans/genius-search-accuracy/run2
PY=/home/ken/miniconda3/envs/pik/bin/python
$PY yt_meta.py              # title and channel per YouTube ID -> yt_meta.json (206 lookups uncached)
$PY truth_build.py          # the answer key -> truth.json, truth_names.json
$PY today.py -v             # today's two cleaners on each YouTube title
$PY run.py proto yt_title 3 -v           # the 11-11 prototype
$PY run.py new yt_title 3 -v -film       # the new builder; -film lists each film first hit
$PY run.py new yt_title 2 -v             # the two-call limit
$PY run.py new-nochannel yt_title 3      # ablation: no channel name
$PY run.py new-views yt_title 3 -film    # ablation: page views alone below a named artist
git archive origin/search_official_captions tests/unit/data/youtube_search | tar -x -C <dir>
$PY holdout.py <dir>/tests/unit/data/youtube_search -v   # unseen titles
```

`truth_build.py` and `yt_meta.py` hold this computer's library path. Every Genius answer is
cached in `run2/genius_raw.json` (1,400 queries or so, about 2 s each uncached); do not run
two of these scripts at once, each rewrites that file. Gitignored there: `truth.json` (lyric
lines) and logs.

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
