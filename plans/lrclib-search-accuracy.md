# LRCLIB search accuracy: bring back the right records

Model: not assigned. Evaluation by Claude Fable 5.2, 2026-11-11. No spec yet.

Status: **evaluation only, no code changed.** Branch `lrclib_search_accuracy`, split on
2026-11-12 (at Ken's request, the two halves being unrelated) from `lyric_search_accuracy`,
which was cut from `dev` at `1016e20` to carry the combined plan between computers. The Genius
half lives on `genius_search_accuracy` (`plans/genius-search-accuracy.md`); the combined plan
is kept at `archive/lyric_search_accuracy`. This branch holds no code. Before code starts it is
rebased onto `dev` after `search_official_captions` lands (see Rulings).

## Pick up here

1. On Ken's other computer: rerun the LRCLIB replay against that library ("Rerun on the other
   computer"). Its library is about 30 songs larger; the LRCLIB cache is not copied over.
2. Read the LRCLIB fit-check feature (on that computer, not on origin as of 2026-11-11) and
   answer "Needed from the fit-check branch" below.
3. Then the spec, which needs step 2.
4. Stop before any code until the spec exists.

Evidence (replay scripts) is in `plans/lrclib-search-accuracy/`. Committed: the scripts.
Gitignored there, local to each computer: `truth.json` (with lyric lines) and
`lrclib_raw.jsonl` (84 MB, full lyrics). See "Reproduce".

Every count in the Results log is for the first computer's library as of 2026-11-11 (157
songs). That library's truth list without lyric lines is committed on the Genius half, and
kept at `archive/lyric_search_accuracy:plans/lyric-search-accuracy/truth_names.json`.

## Rulings (Ken, 2026-11-11)

- **A. Scope and order** (ruled for the combined plan): LRCLIB was phase 3, after the two
  Genius phases: the search (see "LRCLIB scope after the rulings"). Since the split it is this
  plan's only phase.
- **Landing order: `search_official_captions` lands on `dev` first**, as ruled for the
  combined plan. Ken confirmed on 2026-11-12, after the split, that this half still waits for
  it, though that branch edits `routes/search.py` and the vote in `official_rank.py`, which no
  LRCLIB item touches.
- **E. LRCLIB floor: reframed, not ruled.** A separate feature is tightening the repair page's
  LRCLIB fit check and looking for a bar above which an LRCLIB record can scaffold a song
  automatically. That is why Ken wants the search refined: what matters is the set of records
  the query brings back, not the single pick.
- **Existing LRCLIB files on disk: left alone.** New rules apply to new searches only. Ken
  placed most of the 34 by hand.
- **Fixtures.** The LRCLIB cache holds full lyrics and stays local; LRCLIB tests use small
  made-up records.

## LRCLIB scope after the rulings

- This plan owns what the search brings back. The fit-check feature owns the judgment: which
  record is good enough, the bar, and automatic scaffolding.
- LRCLIB items 3 (pick rule) and 4 (floor) leave this plan; they are the fit check's job.
- The measure changes from "is the pick right" to "does the returned set hold a synced record
  at the video's length whose text matches" (see "LRCLIB: the returned set").

### Needed from the fit-check branch

1. What the fit check takes in: one record, or the whole list with a score per record.
2. Where it runs: repair page only, or also unattended in the pipeline.
3. Whether it covers caption-origin songs. If so the query's title and artist come from the
   file name, and film-named songs have no artist.
4. Its fit score, to replace the 60% line-match stand-in used in the replay here.
5. What it does with "a file on disk stops any later search" (`ensure_lrc`).
6. Which functions in `lrclib.py`, `library_tools.py` and `song_repair.html` it edits.

## What exists (read 2026-11-11)

- **Unattended (pipeline, Genius-origin songs only)**:
  [lyrics_fetch.py](../pikaraoke/pipeline/stages/lyrics_fetch.py) `_resolve_lrclib` ->
  `ensure_lrc` ([lrclib.py:503](../pikaraoke/lib/lrclib.py#L503)). Sends the Genius title and
  artist, cleaned by `clean_key` (drops feature credits and trailing brackets), as a
  title-field + artist-field search. Picks with `select_candidate`
  ([lrclib.py:295](../pikaraoke/lib/lrclib.py#L295)): most lyric lines matched, video length
  only as the tie-break. Saves whatever wins; a file on disk stops any later search.
  Runs only when the `lrclib_fill` setting is on, and the saved record only fills lines the
  matcher leaves unplaced (`plans/open-issues.md`: LRCLIB as an automatic scaffold was
  withdrawn, S-1, 2026-09-08).
- **Repair page**: all-fields `q=` search from one box
  ([library_tools.py:676](../pikaraoke/lib/library_tools.py#L676)); the same pick rule marks
  "best" and that one is preselected. For custom lyrics the box is prefilled; **for a Genius
  pick it starts empty** and nothing is searched until the admin types.
- LRCLIB's search returns at most 20 records. Its `/api/get` takes title, artist and a length
  and returns one record at that length; the app does not call it with a length.

## Method

- Ground truth: the 157 library songs, whose file names Ken curated on 11-08 as
  `Artist - Title` (87 songs) or `Film (Year) - Title` (70 songs). 17 bundles also record the
  Genius song the admin picked; 34 songs have an LRCLIB match on disk.
- LRCLIB replay: title-field + artist-field search, `q=` search, and title-only (film-named
  songs), with the Genius title and artist where a bundle records them, else the curated
  names. **For film-named songs without a Genius record this sends the film as the artist,
  which the pipeline never does**; those rows are marked.
- "LRCLIB: the returned set" used curated names only (checked 2026-11-11).

## Results log (2026-11-11)

### LRCLIB

Coverage of the first search (songs with at least one synced record / none):

| Search | Artist-named (87) | Film-named (70) | Returned the full 20 |
|---|---|---|---|
| Title field + artist field | 84 / 3 | 63 / 7 | 76 artist, 45 film |
| `q=` all fields | 85 / 2 | 69 / 1 | 76 artist, 59 film |
| Title field only (film-named) | n/a | 68 / 1 (1 not fetched) | 66 film |

No synced record on the field search: Eason Chan 明年今日, Sun Yan-Zi 遇見, The Lonely Island
Here I Go, and (film sent as artist) six Last Five Years songs and The Girl in the Bubble.

The 34 matches on disk against the field search: 13 listed, 21 not.

| Song | Origin | Records returned | On-disk record (artist / album) | Disk length minus video, s | Film sent as artist |
|---|---|---|---|---|---|
| Ed Sheeran & Rudimental - Bloodstream | custom | 20 | Ed Sheeran & Rudimental / BRIT Awards 2016 | 0 | |
| Ed Sheeran - Best Part Of Me | lrclib_srt | 20 | Ed Sheeran; YEBBA / Ed Sheeran Singles | -1 | |
| Eminem - Lose Yourself | genius | 20 | Eminem / Top 100 Schweizer Single-Charts | -1 | |
| Frozen - In Summer | genius | 20 | Josh Gad / Disney Summer Songs | 1 | |
| Jessie J - Domino | lrclib_srt | 20 | Jessie J / weekend vibes | -1 | |
| Jung Kook - Seven | lrclib_srt | 20 | Jung Kook / Seven | -14 | |
| KPop Demon Hunters - Golden | genius | 20 | HUNTR/X / soundtrack | -4 | |
| KPop Demon Hunters - Soda Pop | genius | 20 | Saja Boys / soundtrack | 0 | |
| NSYNC - Paradise | lrclib_srt | 10 | Justin Timberlake / General | -38 | |
| NSYNC - Thinking Of You | lrclib_srt | 20 | *NSYNC | 1 | |
| Ne-Yo - Miss Independent | lrclib_srt | 20 | Ne-Yo | 0 | |
| Vitamin C - Graduation | lrclib_srt | 20 | Vitamin C / Vitamin C Songs | 0 | |
| Beauty and the Beast - Be Our Guest | movie_srt | 20 | Angela Lansbury | 7 | yes |
| Beauty and the Beast - Belle | movie_srt | 20 | Paige O'Hara | 5 | yes |
| Camp Rock - This Is Me | lrclib_srt | 7 | Demi Lovato / Camp Rock | 3 | yes |
| KPop Demon Hunters - Takedown | lrclib_srt | 20 | HUNTR/X | -10 | yes |
| KPop Demon Hunters - Your Idol | lrclib_srt | 20 | Saja Boys | -14 | yes |
| Mulan - I'll Make a Man Out of You | movie_srt | 20 | Donny Osmond / Mulan | -22 | yes |
| Pocahontas - Colors of the Wind | lrclib_srt | 20 | Judy Kuhn / Pocahontas (Score) | 8 | yes |
| Wicked - Defying Gravity | custom | 20 | Chenoweth & Menzel / Original Broadway Cast | 97 | yes |
| Wicked For Good - The Girl in the Bubble | movie_srt | 0 | Ariana Grande | 26 | yes |

Of the 12 rows sent with a real artist: 11 came back at the full 20, and 10 on-disk records are
within 5 s of the video.

Exact-length lookup (`/api/get` with title, artist, and the video's length; no album needed,
checked live): run for the 65 songs whose field search listed no record within 2 s of the video.

| Outcome | Songs |
|---|---|
| Search already lists a record within 2 s (not looked up) | 69 |
| Lookup returns a synced record, matches at least 60% of the lyric lines | 10 |
| Lookup returns a synced record, matches under 60% | 6 |
| Lookup returns an unsynced record | 2 |
| No record at the video's length | 47 |

The 16 synced finds (search had returned the full 20 for every one): Backstreet Boys Drowning
0.83, Everybody 0.55, I'll Never Break Your Heart 0.41, Inconsolable 0.88, More Than That 0.92,
The Call 0.46; Be Our Guest 0.67 (film as artist); Britney Spears Stronger 0.90; Colbie Caillat
Realize 0.94; Bloodstream 0.66; Thinking Out Loud 0.72; Jessie J Domino 0.74; Justin Timberlake
Mirrors 0.88; NSYNC It's Gonna Be Me 0.53; Ne-Yo Because Of You 0.60; Tenacious D Tribute 0.32.
(Number = share of the bundle's lyric lines the record matches. Most of these songs are
caption-origin, so their lines are split as the caption splits them.)

The pick rule replayed on the field search (124 songs with synced records and lyric lines):

| Outcome | Songs |
|---|---|
| Pick is within 5 s of the video | 55 |
| Pick is more than 5 s off; no listed record near the video's length matches comparably | 40 |
| Pick is more than 5 s off; a record within 5 s matches within 10 points | 3 |
| Pick matches under half the lyric lines | 28 |

The three: Ed Sheeran Shape of You (pick 0.96 match, 29 s off; other 0.94, 0 s), Justin
Timberlake Suit & Tie (0.80, 61 s; other 0.79, 4 s), KPop Demon Hunters Soda Pop (0.73, 19 s;
other 0.72, 0 s).

Against the 34 matches on disk the replayed pick is the same record for 12 and a different one
for 21 (one song had no lyric lines to score).

### LRCLIB: the returned set (2026-11-11, after the rulings)

Scores the set each query shape returns, not the pick. From the cache, no new calls
(`lrclib_set.py`). 134 songs have lyric lines and a length. "Near" = a synced record within
2 s of the video. "Near and matching" = such a record matching at least 60% of the bundle's
lyric lines.

Real artist sent (87 songs: artist-named, plus film-named with a recorded Genius pick):

| Set | Any synced | Near | Near and matching |
|---|---|---|---|
| Title field + artist field (today, unattended) | 86 | 61 | 36 |
| `q=` all fields (today, repair page) | 86 | 76 | 48 |
| Exact-length lookup alone | 15 | 14 | 8 |
| Field + `q=` | 86 | 76 | 48 |
| Field + exact-length lookup | 86 | 75 | 44 |
| All of the above + title field only | 86 | 77 | 49 |

Film sent as artist (47 songs; the pipeline never sends this):

| Set | Any synced | Near | Near and matching |
|---|---|---|---|
| Title field + artist field | 40 | 8 | 4 |
| `q=` all fields | 46 | 11 | 9 |
| Title field only | 45 | 10 | 5 |
| All merged | 46 | 15 | 10 |

Median synced records per song: field 20, `q=` 19, field + `q=` 30, all merged 36.

Songs where only a wider set than the field search holds a near and matching record (19):
Aladdin Speechless (q); Backstreet Boys Drowning, Inconsolable, More Than That (q, lookup),
Get Down (q); Britney Spears Stronger (q, lookup); Camp Rock This Is Me (q); Bloodstream
(lookup only); Thinking Out Loud (q, lookup); Jessie J Domino (q, lookup); Justin Timberlake
Mirrors (q, lookup), Suit & Tie (q); KPop Demon Hunters Takedown (q); Kelly Clarkson Because Of
You (q); NSYNC (God Must Have Spent) A Little More Time On You (q); The Last Five Years A
Summer in Ohio, Shiksa Goddess (q, title), See I'm Smiling (title); Vitamin C Graduation (q).

Limits of this table: the lookup was only fetched for the 65 songs whose field search listed
no record within 2 s, so its rows are a floor; 95 songs are caption-origin with caption-split
lines; the 60% line is a stand-in for the fit check's own score.

## Proposed work (candidates, not specced)

Items 3 and 4 have left this plan for the fit check (see "LRCLIB scope after the rulings");
they are kept here as the record of what was proposed.

1. **Exact-length lookup first**, merged with the search results.
2. **Get past the 20 cap**: merge a second query (all-fields, or with the album) by record id.
3. **Pick rule**: among records close on text, prefer the nearest length, instead of length
   only breaking exact ties.
4. **A floor** on the unattended pick so a poor match is not saved and does not block a retry
   (decision E).
5. **Repair step 2**: prefill the box from the Genius pick and run the search on arrival.

## Not measured

- The exact-length lookup for the 69 songs whose field search already listed a near record.
- The pick rule on Genius-origin songs alone. 95 of the replayed songs are caption-origin,
  where the pipeline never runs the LRCLIB search and the lyric lines are caption-split. The
  "under half" count (28) is not split by origin, so it does not size decision E.
- LRCLIB with the album field, or how LRCLIB orders its 20.
- Whether a better LRCLIB pick changes alignment output. This measures search only.
- Songs outside this library: no other languages beyond the four Chinese and four Korean-artist
  songs, no live or remix requests.

## Corrections to the chat summary of 2026-11-11

- LRCLIB: "21 on-disk matches missing from the pipeline's search, 18 capped, 11 within 5 s" was
  a replay with curated names, and 9 of the 21 sent the film as the artist. With a real artist:
  12 missing, 11 capped, 10 within 5 s.

## Related entries in `plans/open-issues.md`

- "`routes/song_info._typed` ... sends title and artist uncapped": same code as LRCLIB item 5.

## Reproduce

From the repo root, with the `pik` env. All scripts are read-only on the library and cache
every service answer beside themselves, so a rerun makes no calls unless a query is new.

```bash
cd plans/lrclib-search-accuracy
PY=/home/ken/miniconda3/envs/pik/bin/python
$PY collect.py              # library -> truth.json (names, recorded picks, lyric lines)
$PY lrclib_probe.py         # LRCLIB searches -> lrclib_raw.jsonl (about 10 minutes uncached)
$PY lrclib_eval.py -v       # coverage, on-disk recall, pick rule
$PY lrclib_get.py           # exact-length lookup
$PY lrclib_set.py -v        # the returned set per query shape (cache only)
```

`collect.py` reads `~/pikaraoke-songs`, so a rename since 11-11 changes the truth set.

### Rerun on the other computer

Ruled 2026-11-11: do not copy `lrclib_raw.jsonl` over. That library is about 30 songs larger,
and the cache is keyed by query, so a copy would cover only the songs both libraries share
under the same names. Run the probe there instead.

Check first:

- The scripts import `pikaraoke`; the env there must have the repo installed or on the path.
- `collect.py` hardcodes `~/pikaraoke-songs`. Point `LIB` at that computer's library if it
  lives elsewhere.
- **Whether the 11-08 standardized names were applied to that library.** Every script splits
  the file name on ` - ` and reads `Film (Year)` from the left part. On unrenamed files the
  truth names and the film/artist split are wrong.

Then run the Reproduce block top to bottom. Calls made there: LRCLIB for every song (two or
three searches each, about 0.3 s apart plus LRCLIB's own 1.5 s or so per answer), then the
lookups in `lrclib_get.py`.

Recording the rerun:

- Log it as a second dated run under the Results log with that library's song count. Do not
  merge its counts into the 157-song tables.
- Never `git add -f` the two ignored files.
