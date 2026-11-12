Model: Claude Sonnet 5.5 (executor, Phases 0, 1, 2, 3 and 4). Claude Fable 5.2 reads GATE F
and GATE Q while it is available (to 2026-11-16), Claude Opus 5.5 after that; then Ken.
Author: Claude Fable 5.2, 2026-11-10.

# LRCLIB timing at download: the shifted-section check

**Status: PLANNED 2026-11-10. Decisions 20-24 ruled by Ken 2026-11-12. Phase 1 executed 2026-11-12 (Sonnet 5.5), review fixes in; Phase 2 (2a-2d) executed 2026-11-12 (Sonnet 5.5), stopped at STOP 2e. Ken's two listens are in (row 6). GATE F read and ruled 2026-11-12 (Fable 5.2): bar frozen as pre-registered, no second hearing, Crazy and Reflection accepted as known holes; Quit Playing Games not yet classed by Ken. Next: Phase 3b (probe-only caption screen fix), then Phase 4.**

## Goal

Same feature as `plans/lrclib-fit-pick.md` (same branch): a first-time download with a Genius
pick is timed from an LRCLIB record when a record passes a fixed bar. That plan's bar let
seven wrong picks through at GATE P (its "GATE P read"). This plan adds one check to the bar,
re-measures the 198 songs already used, freezes the bar, and then tests it on songs nobody has
measured.

Read first: `plans/lrclib-fit-pick.md` sections "The bar and the pick", "GATE P" (the
definition of a wrong pick and of `minor`) and "GATE P read".

## What GATE P found

Six of the seven wrong picks have one cause. The video's cut differs from the record for a
stretch (a shorter gap, a spoken break, film dialog), so a run of lines sits 2 to 6 s off. The
fit calls a line mistimed only past 5 s, so the stretch passes with every word claimed.

| Song | Wrong pick | A clean record exists |
|---|---|---|
| Moana - Where You Are (`RTWhvp_OD6s`) | 28421947 | no, all 20 passing records carry the step |
| Bruno Mars - When I Was Your Man (`ekzHIouo8Q4`) | 26614056 | yes |
| The Last Five Years - A Summer in Ohio | 23648746 | no |
| The Last Five Years - Nobody Needs to Know | 4626353 | yes |
| Flight of the Conchords - Bowie | 19452078 | no |
| Britney Spears - (You Drive Me) Crazy (`Q4VK9_CfOLQ`) | 2137556 | not known: the transcriber heard none of the shifted lines |
| Christina Aguilera - Reflection (`RNprQYHenNI`) | 685756 | not known: the two shifted closing lines went unheard |

## Decisions

Decisions 1-17 of `plans/lrclib-fit-pick.md` stand, except 17 (that holdout is spent).

Ken, 2026-11-10, in chat: "I will have sonnet executor and opus will pick a fresh set of
songs."

18. The feature goes on under this plan with a tighter bar and a fresh holdout. The bar of
    `plans/lrclib-fit-pick.md` is not shipped. (The author's reading of the words above.)
19. Sonnet executes. Opus chooses the fresh songs. (Changed 2026-11-12: Sonnet lists them,
    Decision 25.)

Ken, 2026-11-12, in chat, ruling on the author's defaults:

20. Fable reads both gates while it is available (to 2026-11-16). After that Opus reads
    them, and Fable is only suggested if Opus is unsure. (The author's default was Opus.)
21. Accepted. The fresh holdout is 50 songs: 20 that take a Genius pick, judged by Ken's ear, and 30 with
    uploader English captions, judged against their captions with no listening. They go in the
    library as the last thirty did; Ken deletes what he does not want afterwards.
22. Accepted. `minor` (one missing lead line, or one line 3 to 5 s off) does not count as
    wrong. Grenade and Into the Unknown stay picks.
23. Accepted. A wrong record that no check on heard words can reach is put to Ken at GATE F as a known
    hole, as Decision 12 was. He accepts it or stops. Expected: Reflection, and Crazy unless
    the second hearing reaches it.
24. Accepted. Same branch, `lrclib_fit_pick`. The Phase 1 code of the earlier plan is reused.
25. Sonnet lists the fresh songs under Phase 0's rules (Ken asked whether Sonnet could; the
    rules are mechanical and Phase 4a checks every song's set).

Ken, 2026-11-12, in chat, ruling on the Phase 1 code review ("yes to #3, otherwise
ratified"):

26. The second hearing uses an auto-caption only when the pipeline would adopt it
    (`ytasr.is_usable`: word-level, dense enough over the song). A line-level caption puts
    every word at its line's start and would read as shifted lines. This narrows "has an
    auto-caption file" in the candidate rule; nothing was measured under the old wording.
27. The rest of the review's triage stands: the caption screen is moved onto the heard
    words' clock, Table V calls the bar itself, and a missed opening word (review finding 1)
    is checked at GATE F, not fixed before it (the offset definition is pre-registered and
    the limits were sized with it).

## The bar (pre-registered)

The bar of `plans/lrclib-fit-pick.md`, unchanged, plus one condition. A record passes when its
fit against the transcribe stream has all of:

- status `fits`;
- `speed == 1.0`;
- at most 1 mistimed line;
- longest unclaimed run of at most 12 heard words;
- **shift run of at most 2 lines.**

**Shift run.** Take the fit's lines inside the clip, in order (`SliceFit.lines`). A line's
*offset* is what `_flagged_lines` already compares: the start of the heard word that anchors
the line, minus the line's start on the clip. A line is *off* when it is heard and its offset
is 1.5 s or more either way. The shift run is the longest stretch of neighbouring lines that
are all off the same way (all early or all late). An unheard line ends a stretch. So does a
line less than 1.5 s off, and so does a change of direction.

**The pick, the search:** unchanged. The new condition is checked last, so the earlier refusal
reasons keep their meaning. Its refusal reason is `shifted`.

**Not in the bar until GATE F says so:** the second hearing (below).

## The second hearing (a candidate, measured in Phase 2)

Crazy and Reflection pass every check on the transcriber's words because the transcriber
heard nothing where they are wrong. YouTube's auto captions (`subtitles/<stem>.en.asr.json3`,
the `asr` stream of `heard_streams`) are a second hearing of the same audio.

**The candidate rule, fixed here:** when the song has an auto-caption file the pipeline would
adopt (Decision 26) and the record's fit
against the `asr` stream alone has status `fits`, the record also fails when that fit's shift
run is over 2 lines. A song without the file, or a record whose `asr` fit does not fit, is
judged on the transcribe stream alone.

Phase 2 measures the rule on the 198 used songs. GATE F reads what it catches and what it
costs. It enters the bar only by Ken's ruling there, and only as written here.

## Where the check came from (sizing, 2026-11-10)

Not a gate read. Scratch scripts outside the repo, on the saved outputs of the earlier holdout
run (`~/.pikaraoke/tmp/lrclib_fit_pick_holdout`), read after every verdict was known. The
limits were chosen with these results in sight.

- Over the 105 picks, the shift run as defined marks exactly five: the five wrong picks whose
  shifted lines were heard. At 2.0 s in place of 1.5 s it marks the same five.
- A looser form, where an unheard line does not end a stretch, also marks Quit Playing Games
  and KPop Demon Hunters - Takedown (Ken: good). Takedown's marked lines are three separate
  lines with unheard lines between them (22 of its 54 lines are unheard), not a section.
- With the check in the bar and the pick order unchanged:
  - Where You Are, Bowie and A Summer in Ohio have no pick (every passing record is marked:
    20 of 20, 20 of 20, 2 of 2).
  - When I Was Your Man moves to 15816725: 46 lines, all heard, none 1.5 s off.
  - Nobody Needs to Know moves to 17631826: 58 lines, none 1.5 s off against the captions.
  - No other pick changes. Songs with a pick: `picks` 23 of 28 (unchanged), the earlier new
    songs 20 of 29 (was 21), `caption` 59 of 112 (was 61).
- 59 of the 1363 passing records are marked, on 11 songs.
- Crazy and Reflection are not marked. A limit on unheard lines does not separate them from
  good picks. Crazy's longest unheard stretch is 13 lines; Jessie J - Flashlight has 19 and
  Ken heard it as good. Reflection ends on 4 unheard lines; Suit & Tie ends on 7, and
  Graduation, one of Ken's Repair picks, on 4.

So what is unproven: the two limits were fitted to five wrong picks and about a hundred others
on songs whose answers were known. Phases 0 and 4 test them on songs nobody has measured.

## Phase 0: the fresh songs (Sonnet lists, Ken adds; any time before Phase 4)

- **Used songs, done 2026-11-10:** `~/.pikaraoke/tmp/lrclib_shift_check/baseline_ids.txt`, 198
  lines, sha256 `1a764ddb9f814bbfb477c4cd67ae29edea1bd7fdcea9f44991adff4770dc777c`. Every
  song the earlier holdout run read. A song not in it is *new*.
- **Sonnet lists 50 songs** in a table here (song, YouTube id, set, kind), in a plan-only commit,
  and gives Ken the Windows `add_songs` commands in batches of about ten.
  - **Set E, 20 songs:** the upload has no uploader English captions, so the song takes a
    Genius pick. Ken judges these picks by ear.
  - **Set C, 30 songs:** the upload has uploader English captions. Judged against the
    captions.
  - Check captions per video with `yt-dlp --list-subs` from the VM: uploader subtitles, not
    automatic captions, decide the set.
  - **Kinds.** At least 8 of Set E and 12 of Set C are film clips, sing-alongs, or official
    videos with a spoken part or a cut that differs from the album track. Those kinds are
    behind six of the seven wrong picks. The rest are plain official uploads.
  - Artists and kinds of song Ken already has, English lyrics, the studio recording. No live
    versions, covers or remixes.
  - Not a song already in the library under any upload, and no id in the baseline file.
  - **LRCLIB is not consulted** for any of them, by anyone, before Phase 4 runs.
- Ken adds them with `add_songs`, taking the Genius pick at each prompt for Set E. They time as
  today.
- Adding songs does not wait for GATE F. The probe does not read a new song before the bar is
  frozen (Phase 2 runs with `--skip-new`).

**The fifty, listed 2026-11-12 (Sonnet 5.5 began, Opus 5.5 finished).** Candidates came from
YouTube searches by the artists of the earlier holdout's title column and from targeted film
searches. Every id is in the top 3 of `ytsearch3:<song>`. The set is from `--list-subs`
uploader subtitles only (`en*` code = C). Exclusions checked: the baseline ids, every song in
the holdout's title column, every song file in the library. Kind is judged from the upload's
title, channel and length (a `video cut` runs well away from the album track's length), not by
listening. LRCLIB was not consulted.

| # | Song | YouTube id | Set | Kind |
|---|---|---|---|---|
| 1 | Camp Rock 2 - It's On | `fO4BmrVjqjM` | E | sing-along |
| 2 | Frozen - Fixer Upper | `IyO-vdsgq1s` | E | sing-along |
| 3 | Frozen 2 - Some Things Never Change | `nVW9QOIeqQg` | E | sing-along |
| 4 | Pocahontas - Savages | `1YiAzyCzZzw` | E | film clip |
| 5 | Rent (2005) - Take Me or Leave Me | `DcbEr7Cd_Cc` | E | film clip |
| 6 | Rent (2005) - Over the Moon | `pXNd2V88d60` | E | film clip |
| 7 | Tenacious D - Kickapoo | `hvvjiE4AdUI` | E | film clip |
| 8 | Wicked (2024) - What Is This Feeling | `amgPXKrFZVg` | E | film clip |
| 9 | Wicked (2024) - Dancing Through Life | `jniq78mKKcM` | E | film clip |
| 10 | Justin Timberlake - SexyBack | `3gOHvDP_vCs` | E | video cut |
| 11 | Britney Spears - I'm A Slave 4 U | `Mzybwwf2HoQ` | E | plain |
| 12 | Colbie Caillat - Fallin' For You | `GPCRbuL4Oh8` | E | plain |
| 13 | Jason Mraz, Colbie Caillat - Lucky | `acvIVA9-FMQ` | E | plain |
| 14 | Kelly Clarkson - Behind These Hazel Eyes | `yipoOY56MbM` | E | plain |
| 15 | Kelly Clarkson - Catch My Breath | `HEValZuFYRU` | E | plain |
| 16 | Michelle Branch - All You Wanted | `Cbo2n2MzxxE` | E | plain |
| 17 | Michelle Branch - Are You Happy Now? | `Uxb6RFh3BCw` | E | plain |
| 18 | NSYNC - Here We Go | `zqVejtQ2qCk` | E | plain |
| 19 | Queen - Don't Stop Me Now | `HgzGwKwLmgM` | E | plain |
| 20 | S Club - Natural | `A4Kba6v5fdg` | E | plain |
| 21 | Justin Timberlake - Can't Stop the Feeling! | `ru0K8uYEZWw` | C | video cut |
| 22 | ZAYN - Dusk Till Dawn | `tt2k8PGm-TI` | C | video cut |
| 23 | Whitney Houston - I Wanna Dance With Somebody | `eH3giaIzONA` | C | video cut |
| 24 | Tenacious D - Wonderboy | `FL4HSiGvk68` | C | video cut |
| 25 | Eminem - Without Me | `YVkUvmDQ3HY` | C | video cut |
| 26 | Eminem - The Real Slim Shady (clean) | `eJO5HU_7_1w` | C | video cut |
| 27 | Aladdin (2019) - Prince Ali | `eGLSPyGszjo` | C | film clip |
| 28 | Encanto - Waiting On A Miracle | `jKKrfr4To14` | C | film clip |
| 29 | High School Musical - Breaking Free | `0qj67KE5VXI` | C | film clip |
| 30 | Camp Rock 3 - Play My Music | `jQ-Pqxl1BlI` | C | film clip |
| 31 | Camp Rock 3 - One Beat Away | `tESZ92ugf7g` | C | film clip |
| 32 | Moana - Along The Way | `D_dOXTpwV5s` | C | film clip |
| 33 | Adele - Rolling in the Deep | `rYEDA3JcQqw` | C | plain |
| 34 | Adele - Send My Love | `fk4BbF7B29w` | C | plain |
| 35 | Ariana Grande - Almost Is Never Enough | `b87dBaL4qI0` | C | plain |
| 36 | Britney Spears - Toxic | `LOZuxwVk7TU` | C | plain |
| 37 | Silk Sonic - Smokin Out The Window | `GG7fLOmlhYg` | C | plain |
| 38 | Christina Aguilera - Genie In A Bottle | `kIDWgqDBNXA` | C | plain |
| 39 | Colbie Caillat - Bubbly | `AWGqoCNbsvM` | C | plain |
| 40 | Ed Sheeran - Bad Habits | `orJSJGHjBLI` | C | plain |
| 41 | Ed Sheeran - Shivers | `Il0S8BoucSA` | C | plain |
| 42 | Jessie J - Who You Are | `j2WWrupMBAE` | C | plain |
| 43 | John Legend - Love Me Now | `NmCFY1oYDeM` | C | plain |
| 44 | Kelly Clarkson - Breakaway | `c-3vPxKdj6o` | C | plain |
| 45 | Lewis Capaldi - Before You Go | `Jtauh8GcxBY` | C | plain |
| 46 | NSYNC - Tearin' Up My Heart | `_ZcmuKsyvzg` | C | plain |
| 47 | Ne-Yo - Closer | `z_aC5xPQ2f4` | C | plain |
| 48 | Sara Bareilles - Brave | `QUQsqBqxoR4` | C | plain |
| 49 | Westlife - My Love | `ulOb9gIGGd0` | C | plain |
| 50 | S Club - Bring It All Back | `GLQ0biK-ZgA` | C | plain |

Spares, same checks passed, not added: E `kijpcUv-b8M` (Queen - Somebody To Love, video cut),
`Do5TwE_jYnE` (Pocahontas - Just Around the Riverbend, film clip), `PTOFEgJ9zzI`, `lLYrTPE9dOE`;
C `PstrAfoMKlc`, `GXoZLPSw8U8`, `QZLxVvLyKTo`, `FxYw0XPEoKE`, `H4BB9eGUEaE`. A spare replaces a
song only if its download fails, same set and kind where possible, recorded here.

## Phase 1: the check and the probe (Sonnet)

No library access needed. No GPU.

**1a. Anchors.** Confirm these exist as used here; STOP if not: `srt_slice_fit._flagged_lines`,
`SliceFit.lines`, `heard_streams`, `ASR`, `sheet_stream`; `lrc_auto_pick.refusal`, `REFUSALS`,
`evaluate`; in `scripts/lrc_fit_pick_probe.py`: `add_references`, `reference_flags`,
`candidate_row`, `sheet_rows`, `search_records`, `read_baseline`, `table_v`, `table_k`.

**1b. `SliceFit.shift_run`** (`fits` only, 0 otherwise), computed where `_flagged_lines` has
the anchors and clip starts, as "Shift run" defines it. The 1.5 s is a named constant in
`srt_slice_fit`. Tests: a stretch of three lines late; three lines with an unheard line in the
middle (run of 1); a change of direction; a line 1.4 s off ending a stretch; a record with no
line off.

**1c. The bar.** In `lrc_auto_pick`: `MAX_SHIFT_RUN = 2`, the refusal `shifted`, checked after
`unclaimed`. Tests ride with it.

**1d. The probe** (`scripts/lrc_fit_pick_probe.py`):

- Per record in `candidates.tsv`: `shift_run`; `ref_shift_run` (the reference fit's shift
  run); when the song has the auto-caption file, `asr_status`, `asr_shift_run`,
  `asr_mistimed_n`, `asr_unheard_n` from `fit_slice(srt, {ASR: words}, length)`.
- A new reference flag `ref_shift_run` when the reference fit's shift run is over 2.
- Per song in `songs.tsv`: `has_asr`; `pick_shift_run`; `asr_pick_id`, the pick when the
  second-hearing rule is also applied (empty when none).
- Sheets: each `L` row carries the line's offset against the heard words and, on a caption
  song, against the captions, in seconds, blank when unheard. The judge then needs no scratch
  script.
- `--skip-new`: songs not in the baseline are not read at all. `--new-only`: only songs not in
  the baseline are read. Each needs `--baseline`.
- **Table G**, shaped like Table K: the seven GATE P wrong records above, each with its
  refusal under this bar, shift run, the `asr` columns, and whether it is the pick.
- **Table A:** every song whose pick differs between the bar and the bar with the
  second-hearing rule: group, song, both pick ids (or none), `ref_flags` of each.
- **Table C:** every song whose pick differs from the pick in a run named by
  `--compare <songs.tsv>`: both ids, or none.
- **Table V** gains rows for the shift limits: 1.0, 1.5 and 2.0 s by runs of 2, 3 and 4.
- Tests for the new columns, flags and options.

**1e.** Full test suite, pre-commit on changed files, self-review on the three axes. Commits:
1b, 1c, 1d, each with its tests. Results row with hashes.

**STOP 1f.** Checkpoint for Ken. Review due: `ddefad8`, `71c916f`, `810665f`, `f96db34` (never
reviewed) and this phase's commits, in one `/code-review`.

## Phase 2: the used songs again (Sonnet; needs the shared drive mounted)

**2a.** Copy the earlier records so no search runs:
`cp -r ~/.pikaraoke/tmp/lrclib_fit_pick_holdout/cache ~/.pikaraoke/tmp/lrclib_shift_check/cache`.

**2b.** First check the baseline's sha256 against Phase 0. Then run
`python scripts/lrc_fit_pick_probe.py --folder
"/home/ken/shared-drives/D:/Shared/pikaraoke-songs" --out ~/.pikaraoke/tmp/lrclib_shift_check
--baseline ~/.pikaraoke/tmp/lrclib_shift_check/baseline_ids.txt --skip-new --old-cache
~/.pikaraoke/tmp/lrclib_auto_timing/cache --compare
~/.pikaraoke/tmp/lrclib_fit_pick_holdout/songs.tsv --listen-dir
"/home/ken/shared-drives/D:/Shared/lrclib-listen/shift-check" > <out>/report.md`.
(A subfolder: the earlier runs' listen files stay in `lrclib-listen` and are not cleared.)
Read-only check as before: `find <library> -newer <out>/started` lists nothing the probe
could have written (new song folders and files are Ken's import).

**2c. Expected, from the sizing.** Table C lists five songs and no others: Where You Are,
Bowie and A Summer in Ohio lose their pick; When I Was Your Man moves to 15816725; Nobody
Needs to Know moves to 17631826. Table G: five records refused `shifted`; 2137556 and 685756
pass and are picked. If Table C or Table G differs, record the difference raw and STOP. Do
not adjust a limit.

**2d.** Tables P, S, K, G, A, C, V and L pasted raw under "Report output: used songs". No
tallies, no reading. Plan-only commit.

**STOP 2e.** Handoff to the judge (Decision 20) for GATE F. Ken listens to When I Was Your Man's new pick and to
Quit Playing Games (`Ug88HO2mg44`, 33413907, never ruled; about 1:57 to 2:05), from the listen
folder.

## GATE F: freeze the bar (the judge of Decision 20, then Ken)

Read-only. Inputs: the Phase 2 report and files, Ken's two verdicts.

1. **Tables K and G.** No GATE M wrong record is a pick. No GATE P wrong record is a pick
   except those the sizing expects (2137556, 685756).
2. **Changed picks.** Every song in Table C that still has a pick gets a verdict: against the
   captions on a caption song, Ken's ear otherwise. Quit Playing Games has Ken's verdict. Any
   wrong pick: STOP for Ken.
3. **The second hearing.** From Tables G and A: which wrong records the rule refuses, and what
   it costs (picks lost or changed, and which of those Ken heard as good or the captions bear
   out). The judge recommends adding it or not. A changed pick it would cause needs a verdict
   before the rule is added.
4. **Known holes.** Name every GATE P wrong record that is still a pick under the bar Ken is
   about to freeze. Ken accepts each as a known hole or stops (Decisions 8 and 23).
5. **Missed opening words.** For each record refused `shifted` that Ken heard as good or the
   captions bear out, read its sheet: are the off lines ones whose opening words are not in
   `words.txt`, so the line's offset was taken from a later word and reads late by those
   words' length? List each such record. A different offset definition is a new plan, not a
   change at this gate.
6. **Ken rules:** the bar as pre-registered, or with the second-hearing rule, or stop. The
   judge writes the frozen bar and the ruling under "Frozen bar" in this file with the date.
   No limit changes at this gate. A different limit is a new plan.

## Phase 3: the second hearing in the bar (Sonnet; only if GATE F adds it)

**Not run: GATE F left the second hearing out (ruling 2).**

`lrc_auto_pick.evaluate` and `pick` take the `asr` stream as an optional argument and apply
the rule as "The second hearing" writes it. Tests. The probe passes the stream. One commit.
Results row.

## Phase 3b: the caption screen (Sonnet; probe only; before Phase 4)

Ruled at GATE F (ruling 3; the finding is in "GATE F read"). `scripts/lrc_fit_pick_probe.py`
and its tests only. `lrc_auto_pick` and `srt_slice_fit` are not touched: the bar is frozen.

- **Caption offsets from the anchors.** For a reference line `j` that `match_lines` gives fit
  line `i`: `ref.lines[j][1] + ref.offsets[j] - fit.lines[i][1]`, None when the caption did
  not hear the line. A fit line with no match is None. One function; the sheet's
  `caption_offset` and `ref_shift_run` (`longest_shift_run` over these, in fit line order;
  the `candidates.tsv` column and the flag) both read it. The `ref.shift_s - fit.shift_s`
  form goes.
- **A flag `ref_speed`** in `reference_flags` when `ref.speed != 1.0`, and a `ref_speed`
  column in `candidates.tsv`.
- **Tests:** a reference fit at another speed raises `ref_speed`; a record with a step
  against the caption that the reference fit takes up as speed still reads a `ref_shift_run`
  over 2; with both fits at speed 1.0 the offsets equal what the old form gave.
- **Check on one used song, not a rerun:** copy `Q4VK9_CfOLQ.json` from
  `~/.pikaraoke/tmp/lrclib_shift_check/cache` into the `cache` of a scratch `--out`, then run
  the probe with `--only Q4VK9_CfOLQ`, `--baseline`, `--skip-new`, a scratch `--listen-dir`.
  Expected for 2137556: `ref_speed` and `ref_shift_run` among its flags, `ref_shift_run` 15.
  Anything else: STOP. The Phase 2 folder is not written.
- **Expected side effect, not a STOP:** on a rerun three Rent picks (Another Day, I Should
  Tell You, What You Own) would read a `ref_shift_run` of 4 or 5 from cues that hold two
  singers' lines. A flag is a screen; the judge reads the sheet.
- Full suite, pre-commit on the changed files, self-review. One commit. Results row. STOP
  for Ken; Phase 4 follows.

## Phase 4: the fresh songs (Sonnet; after GATE F and Phase 0; needs the shared drive)

**4a.** A dry look: the songs not in the baseline are exactly Phase 0's fifty, and each is in
its set (`joint` for Set E, `caption` for Set C). List any that is not, with the reason. Do not
swap songs.

**4b.** Run the probe as in 2b with `--out ~/.pikaraoke/tmp/lrclib_shift_check_holdout`,
`--new-only` in place of `--skip-new`, no `--compare`, a fresh cache and a live search. One
run. A rerun only for songs LRCLIB was unavailable for. The same read-only check.

**4c.** Tables P, S, X, V and L pasted raw under "Report output: fresh songs". No tallies, no
reading. Plan-only commit.

**STOP 4d.** Ken listens to every Set E pick (about ten a session, Table L order). Handoff to
the judge (Decision 20) for GATE Q once his verdicts are in.

## GATE Q (the judge of Decision 20, then Ken)

Read-only. Inputs: the Phase 4 report and files, Ken's verdicts. A wrong pick and `minor` are
as `plans/lrclib-fit-pick.md` "GATE P" defines them, with Decision 22.

1. **The frozen bar only.** Table V is for sizing.
2. **A verdict for every pick.**
   - Set E: Ken's ear. The gate is not read while one is missing.
   - Set C: every pick with a reference flag is read from its sheet. Of the unflagged ones, in
     youtube_id order every third until 10 are read. Ken's ear overrides a sheet read.
3. **Zero wrong picks** passes. Any wrong pick: STOP for Ken (Decision 8). There is no third
   bar without a new ruling from him.
4. **Coverage**, reported: songs with a pick in each set, and by kind.
5. **Exposure**, from Table X: songs where a record ruled wrong passes and only the pick order
   kept it out.
6. **Report to Ken**, plainly, with the caveats:
   - Zero wrong among n picks still allows a true rate of about 3 in n. With about 30 picks
     that is one song in ten.
   - Set C is judged from sheets, not by ear.
   - The check shows line times, not finished karaoke.
   - The known holes Ken accepted at GATE F.
   Ken rules go or stop. Record the read and the ruling here.

## After GATE Q

On a go, the build is Phases 4-6 of `plans/lrclib-fit-pick.md` ("the pipeline switch", "source
type, labels, lists", "Ken's checks") with their open points. They get their spec then.

## Executor rules

- Stop at every STOP. If a step contradicts the code, stop and say so.
- No library writes, no GPU, no lyric text in any commit or in this plan. The listen folder and
  the `<out>` folders hold lyric text and stay off the repo.
- No verdicts: tables go in raw. Do not say whether the bar held.
- The fresh songs are not probed, fitted or searched on LRCLIB before GATE F is ruled. Phase 2
  runs with `--skip-new`.
- No limit is changed after seeing a table. A result that seems to call for one is a STOP.
- Branch `lrclib_fit_pick`. Plan edits in their own commits.
- Each handoff prompt carries: branch and HEAD, this file and the section to read, the `<out>`
  paths, "do not rerun the probe", and where Ken's verdicts are recorded.

## Results log

| # | Date | Phase | What was done | Outputs |
|---|---|---|---|---|
| 1 | 2026-11-10 | plan | Sizing on the saved outputs of the earlier holdout run, read-only, scratch scripts outside the repo ("Where the check came from"). Baseline of the 198 used songs written, ids only. Share not mounted: no library read, no auto-caption file read. | `~/.pikaraoke/tmp/lrclib_shift_check/baseline_ids.txt` |
| 2 | 2026-11-12 | 0 | Fifty fresh songs listed (Set E 20: 10 film/sing-along/video cut; Set C 30: 12). yt-dlp 2026.10.26 metadata only; no LRCLIB, no probe, no library writes. Baseline sha256 rechecked, unchanged. Ken adds them with `add_songs`. | table in Phase 0 |
| 3 | 2026-11-12 | 1 | Phase 1 (1a-1e), no library read, no probe run on the library, no GPU. **1a:** every anchor exists as the plan uses it. **1b** `fd5ec5d`: `SliceFit.offsets` (each line's heard start minus fitted start, None when unheard) and `longest_shift_run(offsets, limit_s)` in `srt_slice_fit`; `SliceFit.shift_run` is a property of `offsets` (the plan said a field; `offsets` is kept so the probe can print them and count at other limits without a second copy of the logic); `SHIFT_OFFSET_S = 1.5`. **1c** `478bcf7`: `MAX_SHIFT_RUN = 2`, refusal `shifted` after `unclaimed`, `REFUSALS` has five names. **1d** `f5e11a2`: probe columns (`shift_run`, `ref_shift_run`, `asr_status`, `asr_shift_run`, `asr_mistimed_n`, `asr_unheard_n` in `candidates.tsv`; `pick_shift_run`, `has_asr`, `asr_pick_id` in `songs.tsv`; `Shift_run` in Table S), flag `ref_shift_run`, sheet columns `offset` and `caption_offset` (signed seconds, blank when unheard), `--skip-new`, `--new-only` (both need `--baseline`), `--compare`, Tables G, A, C, and a second table under Table V for offset limits 1.0/1.5/2.0 s by run limits 2/3/4 (other limits at the bar's). Table V's first table now also applies the shift condition at the bar's limits. Table G's seven records are keyed by song id (file stem for the three songs with no YouTube id). The second-hearing rule is read by the probe only (`Rec.asr_refuses`, `SongResult.asr_pick`); the bar does not see it. **1e:** full suite 3692 passed; pre-commit clean on the changed files; self-review on the three axes done. `main()` smoke-run on an empty scratch folder only (every table prints; `--skip-new` without `--baseline` errors). | commits `fd5ec5d`, `478bcf7`, `f5e11a2` |
| 4 | 2026-11-12 | 1 (review) | `/code-review` of `ddefad8~1..HEAD` on the six Phase 1 files, 10 findings, triage ratified by Ken (Decisions 26, 27). Fixed in `48472dc`: `lrc_auto_pick.refusal` takes the four limits as arguments (defaults the bar's) and `passes_at` calls it; `read_asr(song, length)` applies `ytasr.is_usable` and `ASR_JSON3_SUFFIX`, so `has_asr` now means a caption the pipeline would adopt; `judge_reference` adds `caption.shift_s` to the caption stream before `add_references`, so `ref_shift` and every ref flag compare on the heard words' clock; sheet `caption_offset` is `ref.offsets[j] + ref.shift_s - fit.shift_s`; `make_recs` compares ids with `<=` (no KeyError when a timing has no int id); four long lines rewrapped. Not fixed: finding 1 (GATE F item 5), 2 (ruled under "Where the check came from"), 5 (Phase 2b now writes listen files to a subfolder), 6 (Phase 2 reuses the cache on purpose), 9 (probe-only refactor). Full suite 3696 passed; pre-commit clean. | commit `48472dc` |
| 5 | 2026-11-12 | 2 | Phase 2 (2a-2d) on `lrclib_fit_pick` (HEAD `57b1854`), VM, read-only on the library, while Ken's Phase 0 import was running. **2a:** `lrclib_fit_pick_holdout/cache` copied to `<out>/cache` (173 files). **2b:** baseline sha256 `1a764ddb…777c` checked first, 198 lines, equal to the one Phase 0 records. Command as written (`--skip-new`, `--old-cache`, `--compare`, listen files to `lrclib-listen/shift-check`), stdout to `<out>/report.md`, progress log to the scratchpad; started 10:16:18, finished 10:20:40, exit 0; 198 songs read, none `lrclib_unavailable`, no rerun. **One live search ran, against the plan's "no search runs":** `YRpvIiz9G8A` (Encanto - We Don't Talk About Bruno) is a baseline song with no cache file, because the earlier holdout run read it as `out_of_scope` `no_bundle`; Ken regenerated it at 14:05 on 2026-11-10, after that run (14:00), so it now has a bundle and is `joint` (15 records, 10 timings, 0 passing, no pick). Its record file is the one new file in `<out>/cache` (174 files). The earlier run had no pick for it either, so it is not in Table C. **Phase 0 import, seen not touched:** all 198 baseline songs are still in the library, and the 10 songs outside the baseline are Phase 0 #1-#10 (videos dated 09:45-09:49), none read (`--skip-new`). **Read-only check:** `find <library> -newer <out>/started` printed the directories `nonvocal/` and `vocal/` and two files, `---nonvocal.m4a` and `---vocal.m4a` of `pXNd2V88d60` (Phase 0 #6, Rent - Over the Moon), written 10:17:02-15: Ken's import. No file of a baseline song changed. **2c, as the plan defines it:** Table C lists exactly the five songs and ids the plan expects (Where You Are, Bowie and A Summer in Ohio no pick; When I Was Your Man 15816725; Nobody Needs to Know 17631826) and no others; Table G has five records refused `shifted`, and 2137556 and 685756 pass and are picked. No difference to record, no STOP. **2d:** Tables P, S, K, G, A, C, V and L pasted raw below, headings one level down, no tallies, no reading (Table A has no rows; Table X is in `report.md`, the plan does not list it for this phase). The listen folder holds 93 `.srt`, one per Table L row. **STOP 2e:** handoff to the judge for GATE F; Ken's two listens (When I Was Your Man's new pick 15816725; Quit Playing Games `Ug88HO2mg44`, 33413907, about 1:57 to 2:05) not yet done. | Outputs `~/.pikaraoke/tmp/lrclib_shift_check/` (`report.md`, `songs.tsv`, `candidates.tsv`, `sheets/`, `cache/`, `started`); listen files `D:\Shared\lrclib-listen\shift-check` (`/home/ken/shared-drives/D:/Shared/lrclib-listen/shift-check` on the VM). Lyric text; not committed. |
| 6 | 2026-11-12 | 2 (STOP 2e) | Ken's two listens, given in chat to the executor after the STOP, recorded in his words and not classified (the wrong / `minor` / good call is GATE F item 2's). When I Was Your Man, pick 15816725 (the new pick; the compared run picked 26614056): "bruno mars is good now". Quit Playing Games, pick 33413907 (never ruled before; the pick is the same in both runs): "backstreet boys have a few lines that are slightly early or late, but otherwise more than singable". The second verdict does not say how many lines or how far off; the judge may ask Ken before ruling it against Decision 22. | Ken, chat, 2026-11-12. |
| 7 | 2026-11-12 | GATE F | Read by Fable 5.2 on HEAD `137b36d`, read-only; the probe not rerun; no library write, no GPU, no fresh song read. Single records re-fitted from `<out>/cache` by scratch scripts for item 5 and the caption check. Ken ruled by question dialog: holes accepted, second hearing left out, caption screen fixed first; Quit Playing Games open. Phase 3b added. | "Frozen bar": "GATE F read", "Ruling". |

## Frozen bar

Frozen 2026-11-12 as pre-registered; the ruling and the bar's text are at the end of this
section, after the read. One item is open with Ken (Quit Playing Games' class).

### GATE F read (Fable, 2026-11-12)

Read-only, on HEAD `137b36d`. Inputs: "Report output: used songs", `report.md` (Table X),
`songs.tsv`, `candidates.tsv`, `cache/` and `sheets/` under
`~/.pikaraoke/tmp/lrclib_shift_check`, the earlier run's `songs.tsv`, and Ken's two listens
(row 6). The probe was not rerun. Tallies were recomputed from the two `.tsv` files and agree
with Tables P, G, A and C. Sheets exist only for picks and for flagged passing records, so for
item 5 and for the caption check below single records were re-fitted from `cache/` against
the library's bundles and caption files (read-only scratch scripts in the session scratchpad,
calling `fit_slice` as the probe does); every re-fit reproduced its `candidates.tsv` row
(shift run, mistimed, unclaimed run).

Offsets below are in seconds, in the sheets' sense: positive means the heard (or caption) word
comes after the line's fitted start, so the line is shown early; negative, shown late.

**Item 1, Tables K and G: met.** No GATE M wrong record is a pick (the seven Drowning records
pass and are not picked; the rest are refused `unclaimed`; Stronger and That's The Way It Is
have no pick). Of the seven GATE P wrong records five are refused `shifted`; 2137556 and
685756 pass and are picked, as the sizing expects.

**Item 2, changed picks.** Table C equals the difference recomputed against the earlier
`songs.tsv`: five songs, no others. 102 songs have a pick (was 105): `picks` 23 of 28, `joint`
20 of 34, `caption` 59 of 112.

| Song | Pick | Judged by | Verdict |
|---|---|---|---|
| Bruno Mars - When I Was Your Man (`ekzHIouo8Q4`) | 15816725 (was 26614056) | Ken (row 6) | good |
| The Last Five Years - Nobody Needs to Know | 17631826 (was 4626353) | sheet | good: 58 lines, all heard; every line starts within about 1 s of its caption cue from first to last (the one caption offset over 1.5, the two-word last line, starts 0.7 from its cue); no caption cue without a line; no unclaimed run of 5 words. Its one `mistimed` line by heard words (fitted 208 s) is on its cue by the caption. |
| Where You Are, Bowie, A Summer in Ohio | none | | no pick, nothing to judge |

**Quit Playing Games (`Ug88HO2mg44`, 33413907; the pick in both runs, the song's only passing
record): Ken's words are in row 6; the class is his to give, asked below.** What the sheet
shows, for his ruling:

- Second chorus, fitted 117-125 s (about 1:57 to 2:05): five lines in a row shown late, by
  the caption -3.9, -2.6, -2.1, -2.2 and -1.5; by heard words -3.7 and -2.0, two unheard,
  then -2.4. The caption's cue starts say the same without the fit (the two lines of that
  chorus that are not the repeated title line start 2.2 and 1.9 after their cues).
- Elsewhere: by the caption 14 of the 62 lines are 1.5 or more off in all. Outside the second
  chorus they stand alone or in pairs: the first chorus line (fitted 52 s) about 4 early (3.1
  by heard words); lines at 15, 152 and 175 s about 3 early; two refrain-syllable lines at
  169-172 s about 2 late.
- The other chorus passes (59-73 s and 190-207 s) are within about 1.2 s.
- By the bar its shift run is 2, the limit: the two unheard lines end the stretch. This is
  the shape of When I Was Your Man's wrong record (four lines in a row 1.4 to 4.1 late),
  passed for the reason Crazy passes.

**Item 3, the second hearing.** 18 of the 174 probed songs have an auto caption the pipeline
would adopt (`caption` 2 of 112, `joint` 8 of 34, `picks` 8 of 28).

- What it refuses: of the seven GATE P wrong records only 26614056 (When I Was Your Man) is
  on a song with one; its auto-caption shift run is 4, and the bar already refuses it. Crazy
  and Reflection have no auto-caption file at all, so the rule cannot reach either. Eleven
  records on four songs have an auto-caption shift run over 2; the bar refuses all eleven
  already (8 `mistimed`, 2 `shifted`, 1 `speed`).
- What it costs: nothing. Table A is empty. Of the 167 records that pass the bar on those 18
  songs, 166 fit the auto caption and none has an auto-caption shift run over 1.
- **Recommendation: do not add it.** On these songs it never once decided anything: no wrong
  record caught that the bar misses, no good record lost. It was proposed to reach Crazy and
  Reflection and reaches neither. Adding it would put a rule in the shipped bar that no
  measurement has seen act, and GATE Q could not tell whether it helped. Against that: the
  measured cost is nil with margin, and it is the only check proposed so far that could see
  lines the transcriber missed, on the quarter of Genius-pick songs that have the file. If
  Ken adds it, no pick changes, so no verdict is owed first.

**Item 4, known holes (Decisions 8 and 23).** GATE P wrong records still picked under the bar
as pre-registered, with or without the second hearing:

- **Britney Spears - (You Drive Me) Crazy (`Q4VK9_CfOLQ`), 2137556.** After the video's
  spoken break, fifteen lines in a row (fitted 129-190 s) are 1.7 to 5.5 early by the
  caption, most of them 2.5 to 2.9. The transcriber heard two of the fifteen, the first and
  the last. The song's only passing record.
- **Christina Aguilera - Reflection (`RNprQYHenNI`), 685756.** The last two lines (fitted
  191 and 196 s) are 5.1 and 6.4 early by the caption; both unheard. All 20 records pass. Six
  of the seven timings carry the caption's flag (Table X). The seventh is one record,
  40258746, unflagged and not read (it has no sheet); the pick order puts the twelve-record
  timing first, so it does not help as the bar stands.
- Quit Playing Games joins this list if Ken rules it wrong.

What accepting them means for GATE Q, for Ken to weigh: these are 2 (3 with Quit Playing
Games) of 59 `caption` picks, each a stretch the transcriber did not hear. The fresh run has
30 caption songs, about half of which should get a pick, so a pick of the same kind among
them is roughly an even chance. GATE Q rule 3 stops on any wrong pick; accepting a hole here
does not accept one there.

**Item 5, missed opening words.** 59 records are refused `shifted`, on 11 songs. 48 carry the
five wrong timings' songs (Where You Are 20, Bowie 20, Nobody Needs to Know 4, A Summer in
Ohio 2, When I Was Your Man 2). The other eleven, none a pick in either run, on six songs
that all keep their pick:

| Song | Records | Reference | The run that refuses it | Anchor of each off line |
|---|---|---|---|---|
| Backstreet Boys - Shape Of My Heart (`OT5msu-dap8`) | 39824663, 13563645 | captions bear the record out (caption shift run 0 and 1, no flag) | the three opening lines (fitted 8-21 s), -1.8 to -3.6 by heard words, -0.1 to +1.1 by the caption | the line's first word |
| Rent - One Song Glory | 11061005 | captions bear the record out (run 1, no flag) | three lines (fitted 95-108 s) of one to four words on one repeated word, -2.4 to -3.2 by heard words, +0.7 to +3.6 by the caption | the line's first word |
| Justin Timberlake - Suit & Tie (`IsUsVbTj2AY`) | 37912453, 16431444, 14357227, 35648481, 28278766 | captions agree with the refusal (caption shift run 3, `ref_shift_run`) | three lines (fitted 177-180 s), -1.8 to -3.1 by heard words, -1.4 to -3.0 by the caption | the line's first word |
| Queen - Bohemian Rhapsody (`fJ9rUzIMcZQ`) | 18087267 | captions agree the passage is late (lines at 224-229 s are -3.0 to -4.4 by the caption; its run is 2 only because unheard lines sit between them) | three lines (fitted 229-231 s), -1.6 to -3.0 by heard words | the line's first word |
| I Just Had Sex (`lQlIhraqL7o`) | 14631666 | none, not heard by Ken (he heard the pick, another timing) | three lines (fitted 89-91 s), -1.6 to -3.7 | the line's first word |
| Jessie J - Flashlight (`DzwkcbTQ7ZE`) | 4031863 | none, not heard by Ken | three lines (fitted 136-143 s), -2.0 to -2.1 | the line's first word |

- **No record is refused because of a missed opening word.** A missed opening word can only
  move an offset later (positive). All eleven refusing runs are negative, and every line in
  them is anchored on its first word.
- Three records the captions bear out are refused all the same (Shape Of My Heart twice, One
  Song Glory), for another reason: the transcriber's times for slow opening lines, and a
  repeated word matched to an earlier instance. They cost no pick.
- The missed-opening effect itself is real and about the size of the limit. On these eleven
  records there are lines 1.5 or more off whose anchor is a later word of the line (Shape Of
  My Heart 13563645: three lines +1.8 to +2.8, of which 1.6 to 2.3 is the missed words; I
  Just Had Sex: two; each Suit & Tie record: two). Each stands alone between lines within
  1.5, so none built a run. A different offset definition stays a new plan (item 5).

**Found outside the items: the caption screen can hide a shifted stretch (probe only, not the
bar).** `reference_flags` does not look at the reference fit's speed, and the sheet's
`caption_offset` leaves the speed out. On Crazy the record's fit to the caption takes speed
1.016, which turns the 2.5 s step into a slope: `ref_shift_run` reads 2 where the caption's
anchors, compared with the line starts directly, give a run of fifteen. Crazy is still
flagged only because one line is also `ref_mistimed`.

- 7 of the 57 `caption` picks with a reference have a reference speed other than 1.0
  (Drowning, I Want It That Way, Incomplete, Crazy, This I Promise You, I Should Tell You,
  What You Own).
- All 57 were compared again from the anchors (caption anchor minus the line's fitted start,
  no speed). Runs of three or more: Quit Playing Games (five, above), Crazy (fifteen), and
  three Rent picks (Another Day 6156119, I Should Tell You 6191521, What You Own 28181941)
  whose sheets were then read: on all three the lines start within 0.4 s of their caption
  cues, and the offsets come from cues that hold two singers' lines or a doubled line, so the
  caption's words are spread late. No pick's GATE P verdict changes.
- What it touches is GATE Q rule 2, which rules Set C picks from the flags and the sheets. As
  the probe stands, a Set C pick of Crazy's kind could come out unflagged with a quiet
  `caption_offset` column. Proposed, for Ken's ruling, before Phase 4 runs: a probe-only
  commit (Sonnet) that adds a flag when the reference fit's speed is not 1.0 and takes
  `caption_offset` and `ref_shift_run` from the anchors against the fit's own line starts.
  No limit of the bar is involved. Without it, the GATE Q judge compares every Set C pick's
  `L` and `C` rows by hand.

**Also noted, no action:** 9 of the 102 picks have a shift run of exactly 2 (Quit Playing
Games, Shape Of My Heart, 3D, I Should Tell You, What You Own, Without You, Nobody Needs to
Know, The Next Ten Minutes, Grenade). Table V's second table: moving the offset between 1.0
and 2.0 s or the run between 2 and 4 changes the songs with a pick by at most two in a group.

### Ruling

Ken, 2026-11-12, by question dialog after the read (his choices quoted):

1. **Known holes:** "Accept both, go on." Crazy 2137556 and Reflection 685756 are accepted
   as known holes (Decision 23).
2. **The second hearing:** "Leave it out." It is not in the bar. Phase 3 as written does not
   run.
3. **The caption screen:** "Fix it first." A probe-only commit before Phase 4 (Phase 3b).
4. **Quit Playing Games: not yet classed.** Ken, in place of a choice: "those last 3 are
   indeed off bit about 2-3 s, what's the consequence of it staying a pick? do we know how
   badly it'll compromise cue align?" Answered in chat, in short: not measured (this plan
   checks line times, and the aligner needs the GPU). By the code, cue align cuts the pick's
   back-to-back lines into blocks (here six, 34 to 39 s each) and times words from the audio
   inside each, so a line a few seconds off inside its block can be pulled to where it is
   sung, and one sung outside its block cannot. A block edge falls at 121 s, inside the late
   stretch: the line after it is sung about 2 s before its block starts. Open with Ken: not
   wrong and it stays a pick, or wrong and a third known hole (accepted, or stop).

**The frozen bar, 2026-11-12.** As pre-registered in "The bar", no limit changed. A record
passes when its fit against the transcribe stream has all of: status `fits`; `speed == 1.0`;
at most 1 mistimed line; longest unclaimed run of at most 12 heard words; shift run of at
most 2 lines, a line being off at 1.5 s, as "Shift run" defines it. The pick and the search
are unchanged. No second hearing. In code this is `lrc_auto_pick` as of `48472dc`
(`MAX_MISTIMED = 1`, `MAX_UNCLAIMED_RUN = 12`, `MAX_SHIFT_RUN = 2`; `SHIFT_OFFSET_S = 1.5` in
`srt_slice_fit`); no code has changed since.

Neither answer to item 4 changes a limit. Only a stop on it would undo the freeze.

Known holes on the used songs: Crazy 2137556, Reflection 685756 (and Quit Playing Games
33413907 if Ken rules it wrong).

## Report output: used songs

Bar in force: mistimed <= 1, unclaimed run <= 12, shift run <= 2 (a line is off at 1.5 s), speed 1.0. 198 songs in /home/ken/shared-drives/D:/Shared/pikaraoke-songs; output in /home/ken/.pikaraoke/tmp/lrclib_shift_check; listen files in /home/ken/shared-drives/D:/Shared/lrclib-listen/shift-check.

### Table P: groups and skip reasons

| Group | Songs | no_length | lrclib_unavailable | No synced record | With a pick |
|---|---|---|---|---|---|
| picks | 28 | 0 | 0 | 0 | 23 |
| joint | 34 | 0 | 0 | 1 | 20 |
| caption | 112 | 0 | 0 | 1 | 59 |
| new | 0 | 0 | 0 | 0 | 0 |

| out_of_scope reason | Songs |
|---|---|
| custom | 3 |
| movie_srt | 7 |
| no_bundle | 14 |
| no_words | 0 |
| edited | 0 |
| no_caption_file | 0 |
| other | 0 |

### Table S: songs

| Group | New | youtube_id | Title | Skipped | Records | Timings | Passing | no_fit/speed/mistimed/unclaimed/shifted | Pick | Mistimed | Unclaimed | Shift_run | Timing_size | ref_ok | Reference_flags | On_disk_id | On_disk_refusal | Pick_has_disk_timing | Needs_verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| joint | 0 | jeRu6h4XbUU | A-Lin - 幸福在歌唱 (Happiness Is Singing) |  | 2 | 1 | 0 | 2/0/0/0/0 |  |  |  |  |  |  |  | 38356656 | no_fit |  |  |
| caption | 0 | hLQl3WQQoQ0 | Adele - Someone Like You |  | 20 | 13 | 19 | 0/1/0/0/0 | 23116607 | 0 | 2 | 1 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | eitDnP0_83k | Aladdin (2019) - A Whole New World |  | 16 | 10 | 0 | 5/5/0/6/0 |  |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | mw5VIEIvuMI | Aladdin (2019) - Speechless |  | 13 | 12 | 10 | 0/1/1/1/0 | 19793188 | 0 | 3 | 0 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | axySrE0Kg6k | Ariana Grande & John Legend - Beauty and |  | 20 | 11 | 19 | 0/1/0/0/0 | 31988497 | 0 | 5 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | WMweEpGlu_U | BTS 방탄소년단 - Butter |  | 19 | 12 | 15 | 0/0/0/4/0 | 32156281 | 0 | 7 | 0 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | pj6FCKm8dhM | Backstreet Boys - All I Have To Give |  | 18 | 7 | 0 | 1/0/17/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 0Gl2QnHNpkA | Backstreet Boys - As Long As You Love Me |  | 20 | 11 | 7 | 11/0/2/0/0 | 3722851 | 0 | 8 | 1 | 3 | 1 | none |  |  |  | yes |
| picks | 0 | W5kM5wAwRug | Backstreet Boys - Chances (Official Vide |  | 19 | 11 | 12 | 6/1/0/0/0 | 2031559 | 1 | 3 | 1 | 8 |  | no reference | 33832441 | passes | yes | no |
| caption | 0 | GZXHBgjQjNM | Backstreet Boys - Drowning |  | 20 | 9 | 18 | 1/1/0/0/0 | 14595571 | 0 | 6 | 1 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | 6M6samPEMpM | Backstreet Boys - Everybody (Backstreet' |  | 20 | 17 | 0 | 0/2/0/18/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 0LSYuZRSGcY | Backstreet Boys - Get Down (You're The O |  | 20 | 11 | 20 | 0/0/0/0/0 | 1124886 | 0 | 5 | 0 | 6 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | 4fndeDfaWCg | Backstreet Boys - I Want It That Way |  | 20 | 15 | 19 | 0/1/0/0/0 | 11268019 | 0 | 6 | 1 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | kDcCSiakaU4 | Backstreet Boys - I'll Never Break Your  |  | 20 | 10 | 0 | 0/0/20/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | WVe80iZtlYU | Backstreet Boys - Incomplete |  | 20 | 10 | 17 | 0/3/0/0/0 | 19180415 | 1 | 4 | 1 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | qGDF_QcsKVI | Backstreet Boys - Inconsolable |  | 14 | 6 | 14 | 0/0/0/0/0 | 35522789 | 0 | 6 | 0 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | MEb2CecR11I | Backstreet Boys - Larger Than Life (Offi |  | 20 | 6 | 0 | 17/3/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 1OwfYjemrYw | Backstreet Boys - More Than That |  | 20 | 11 | 20 | 0/0/0/0/0 | 36314729 | 0 | 4 | 0 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | Ug88HO2mg44 | Backstreet Boys - Quit Playing Games (Wi |  | 20 | 11 | 1 | 3/2/0/14/0 | 33413907 | 0 | 5 | 2 | 1 | 1 | ref_shift_run |  |  |  | yes |
| caption | 0 | OT5msu-dap8 | Backstreet Boys - Shape Of My Heart |  | 20 | 12 | 13 | 0/5/0/0/2 | 22503174 | 0 | 6 | 2 | 6 | 1 | none |  |  |  | yes |
| joint | 0 | aBt8fN7mJNg | Backstreet Boys - Show Me The Meaning Of |  | 20 | 7 | 20 | 0/0/0/0/0 | 19923333 | 0 | 4 | 1 | 11 |  | no reference | 7255301 | passes | no | yes |
| caption | 0 | wMOkm57vu0k | Backstreet Boys - The Call |  | 20 | 11 | 0 | 0/0/20/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Q4VK9_CfOLQ | Britney Spears - (You Drive Me) Crazy |  | 20 | 9 | 1 | 14/5/0/0/0 | 2137556 | 1 | 7 | 1 | 1 | 1 | ref_mistimed |  |  |  | yes |
| caption | 0 | C-u5WLJ9Yk4 | Britney Spears - ...Baby One More Time |  | 20 | 10 | 16 | 4/0/0/0/0 | 32110280 | 0 | 4 | 1 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | CduA0TULnow | Britney Spears - Oops!...I Did It Again |  | 20 | 16 | 0 | 3/1/0/16/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | AJWtLf4-WWs | Britney Spears - Stronger |  | 19 | 9 | 0 | 2/0/0/17/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | SR6iYWJxHqs | Bruno Mars - Grenade (Official Music Vid |  | 19 | 11 | 9 | 1/9/0/0/0 | 38953751 | 0 | 2 | 2 | 2 |  | no reference | 3851492 | speed | no | yes |
| picks | 0 | luotSpkyCVU | Bruno Mars - I Just Might |  | 20 | 6 | 0 | 0/0/0/20/0 |  |  |  |  |  |  |  | 26520597 | unclaimed |  |  |
| joint | 0 | LjhCEhWiKXk | Bruno Mars - Just The Way You Are (Offic |  | 20 | 13 | 10 | 0/7/3/0/0 | 9888181 | 0 | 7 | 0 | 2 |  | no reference | 7470259 | passes | no | yes |
| joint | 0 | e-fA-gBCkj0 | Bruno Mars - Locked Out Of Heaven (Offic |  | 20 | 12 | 3 | 0/17/0/0/0 | 6936310 | 0 | 7 | 1 | 2 |  | no reference | 12586557 | speed | no | yes |
| joint | 0 | fLexgOxsZu0 | Bruno Mars - The Lazy Song (Official Mus |  | 20 | 12 | 20 | 0/0/0/0/0 | 6706711 | 0 | 10 | 1 | 6 |  | no reference | 8097183 | passes | yes | yes |
| joint | 0 | ekzHIouo8Q4 | Bruno Mars - When I Was Your Man (Offici |  | 19 | 16 | 17 | 0/0/0/0/2 | 15816725 | 0 | 7 | 0 | 2 |  | no reference | 7076945 | passes | no | yes |
| joint | 0 | -cy_tDQPXHk | Bruno Mars, Anderson .Paak, Silk Sonic - |  | 20 | 10 | 0 | 0/0/0/20/0 |  |  |  |  |  |  |  | 9680068 | unclaimed |  |  |
| picks | 0 | 6HCUoMgviwU | Camp Rock (2008) - This Is Me (Sing-Alon |  | 19 | 13 | 1 | 3/0/15/0/0 | 17015895 | 0 | 9 | 0 | 1 |  | no reference | 28926432 | passes | no | yes |
| caption | 0 | RNprQYHenNI | Christina Aguilera - Reflection (Mulan,  |  | 20 | 7 | 20 | 0/0/0/0/0 | 685756 | 0 | 3 | 1 | 12 | 1 | ref_mistimed |  |  |  | yes |
| caption | 0 | GlZxZ2n2zpw | Colbie Caillat - Realize |  | 19 | 9 | 16 | 1/1/1/0/0 | 37946467 | 0 | 12 | 1 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | CX11yw6YL1w | Céline Dion - Ashes (Deadpool 2, 2018) |  | 20 | 9 | 0 | 0/3/0/17/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | NJsa6-y4sDs | Céline Dion - I'm Alive (Stuart Little 2 |  | 20 | 9 | 19 | 0/1/0/0/0 | 28130840 | 0 | 3 | 1 | 6 | 0 | no reference |  |  |  | yes |
| caption | 0 | 9bFHsd3o1w0 | Céline Dion - My Heart Will Go On (Titan |  | 19 | 11 | 12 | 2/4/1/0/0 | 22553995 | 0 | 3 | 1 | 9 | 0 | no reference |  |  |  | yes |
| caption | 0 | T6wbugWrfLU | Céline Dion - That's The Way It Is |  | 20 | 11 | 0 | 0/0/1/19/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | 62llzl7iKkE | Demi Lovato, Joe Jonas - Wouldn't Change |  | 16 | 10 | 15 | 0/1/0/0/0 | 33991259 | 0 | 7 | 0 | 3 |  | no reference | 25091390 | passes | yes | yes |
| joint | 0 | -7jWt3JvJto | Donna Murphy - Mother Knows Best (From ' |  | 20 | 4 | 0 | 3/0/17/0/0 |  |  |  |  |  |  |  | 36177014 | mistimed |  |  |
| picks | 0 | wGyh_53ecgg | Ed Sheeran - Best Part Of Me (feat. YEBB |  | 20 | 10 | 0 | 0/20/0/0/0 |  |  |  |  |  |  |  | 28383401 | speed |  |  |
| caption | 0 | K0ibBPhiaG0 | Ed Sheeran - Castle On The Hill |  | 20 | 11 | 18 | 2/0/0/0/0 | 23335586 | 0 | 2 | 1 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | iWZmdoY1aTE | Ed Sheeran - Happier |  | 20 | 11 | 19 | 1/0/0/0/0 | 29277988 | 0 | 6 | 1 | 5 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | 2Vv-BfVoq4g | Ed Sheeran - Perfect |  | 20 | 10 | 15 | 0/4/0/1/0 | 19853882 | 1 | 2 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | JGwWNGJdvx8 | Ed Sheeran - Shape of You |  | 19 | 12 | 18 | 0/1/0/0/0 | 22081383 | 0 | 6 | 0 | 4 | 1 | none |  |  |  | yes |
| caption | 0 | UAWcs5H-qgQ | Ed Sheeran - The A Team |  | 20 | 9 | 19 | 0/0/0/1/0 | 19121007 | 0 | 3 | 1 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | lp-EO5I60KA | Ed Sheeran - Thinking Out Loud |  | 20 | 13 | 18 | 1/1/0/0/0 | 20756048 | 1 | 3 | 1 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | xFYQQPAOz7Y | Eminem - Lose Yourself (8 Mile, 2002) |  | 15 | 4 | 15 | 0/0/0/0/0 | 18835951 | 0 | 3 | 1 | 11 |  | no reference | 19680363 | passes | yes | no |
| joint | 0 | YRpvIiz9G8A | Encanto - Cast - We Don't Talk About Bru |  | 15 | 10 | 0 | 3/0/0/12/0 |  |  |  |  |  |  |  | 31787551 | unclaimed |  |  |
| caption | 0 | Flight of the Conchords (2007) - Bowie | Flight of the Conchords (2007) - Bowie |  | 20 | 1 | 0 | 0/0/0/0/20 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Business Time | Flight of the Conchords (2007) - Busines |  | 20 | 5 | 0 | 6/0/14/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Carol Brown | Flight of the Conchords (2007) - Carol B |  | 20 | 5 | 0 | 2/0/0/18/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Foux du Fafa | Flight of the Conchords (2007) - Foux du |  | 20 | 4 | 0 | 20/0/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | Flight of the Conchords (2007) - Hiphopo |  | 20 | 5 | 0 | 0/0/0/20/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Hurt Feelings | Flight of the Conchords (2007) - Hurt Fe |  | 20 | 4 | 0 | 0/0/0/20/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Inner City Pressure | Flight of the Conchords (2007) - Inner C |  | 20 | 4 | 0 | 0/0/0/20/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Ladies of the World | Flight of the Conchords (2007) - Ladies  |  | 20 | 2 | 0 | 0/0/0/20/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Robots | Flight of the Conchords (2007) - Robots |  | 20 | 5 | 0 | 19/1/0/0/0 |  |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - Sugalumps | Flight of the Conchords (2007) - Sugalum |  | 8 | 3 | 0 | 2/0/6/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | Flight of the Conchords (2007) - The Mos |  | 14 | 7 | 0 | 4/0/10/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | TeQ_TTyLGMs | Frozen (2013) - Do You Want to Build a S |  | 16 | 10 | 12 | 3/1/0/0/0 | 3514723 | 1 | 4 | 1 | 3 |  | no reference | 35805385 | passes | no | yes |
| picks | 0 | 9tcaM06eGrY | Frozen (2013) - In Summer (Sing-Along) |  | 13 | 8 | 8 | 2/0/0/3/0 | 3630452 | 0 | 11 | 1 | 3 |  | no reference | 36231531 | passes | no | yes |
| caption | 0 | YVVTZgwYwVo | Frozen (2013) - Let It Go |  | 9 | 9 | 2 | 7/0/0/0/0 | 15035688 | 0 | 3 | 1 | 1 | 1 | none |  |  |  | yes |
| picks | 0 | kQDw88hEr2c | Frozen (2013) - Love Is an Open Door (Si |  | 18 | 10 | 18 | 0/0/0/0/0 | 14494965 | 0 | 2 | 1 | 7 |  | no reference | 32050687 | passes | yes | no |
| joint | 0 | lQlIhraqL7o | I Just Had Sex (feat. Akon) |  | 20 | 10 | 19 | 0/0/0/0/1 | 11579404 | 0 | 7 | 1 | 5 |  | no reference | 13910631 | passes | no | yes |
| joint | 0 | mzhv_dg_UBA | Idina Menzel, AURORA - Into the Unknown  |  | 20 | 7 | 16 | 1/1/0/2/0 | 36372778 | 0 | 2 | 1 | 10 |  | no reference | 31283528 | passes | yes | yes |
| joint | 0 | nrZxwPwmgrw | Idina Menzel, Evan Rachel Wood - Show Yo |  | 19 | 10 | 0 | 0/0/0/19/0 |  |  |  |  |  |  |  | 16764056 | unclaimed |  |  |
| joint | 0 | vpMI8Qu5fsc | Ingrid Michaelson 'Be OK' (Official Vide |  | 19 | 11 | 3 | 2/14/0/0/0 | 326004 | 0 | 5 | 1 | 2 |  | no reference | 29819320 | speed | no | yes |
| picks | 0 | Vh74KE3o4Bs | Ingrid Michaelson - The Way I Am |  | 19 | 6 | 18 | 1/0/0/0/0 | 1781541 | 0 | 1 | 0 | 8 |  | no reference | 3161577 | passes | no | yes |
| picks | 0 | XdEN1b-dwlw | Ingrid Michaelson - You and I |  | 16 | 5 | 14 | 0/2/0/0/0 | 10035896 | 0 | 3 | 0 | 11 |  | no reference | 29026140 | passes | yes | no |
| joint | 0 | GI6CfKcMhjY | Jack Sparrow (feat. Michael Bolton) |  | 19 | 6 | 16 | 3/0/0/0/0 | 22000139 | 0 | 5 | 0 | 7 |  | no reference | 20031525 | passes | yes | yes |
| joint | 0 | DYptgVvkVLQ | Jay Chou 周杰倫 - 晴天 (Sunny Day) |  | 19 | 3 | 0 | 19/0/0/0/0 |  |  |  |  |  |  |  | 22847808 | no_fit |  |  |
| caption | 0 | RPWDeLqsN0g | Jay Chou 周杰倫 - 龍捲風 (Tornado) |  | 2 | 2 | 0 | 2/0/0/0/0 |  |  |  |  |  | 0 |  |  |  |  |  |
| joint | 0 | X-NH1uUfr0U | Jessica Darrow - Surface Pressure (From  |  | 20 | 12 | 0 | 4/0/0/16/0 |  |  |  |  |  |  |  | 2261532 | unclaimed |  |  |
| picks | 0 | UJtB55MaoD0 | Jessie J - Domino |  | 18 | 9 | 15 | 2/1/0/0/0 | 28220836 | 0 | 2 | 1 | 8 |  | no reference | 37465712 | passes | no | yes |
| joint | 0 | DzwkcbTQ7ZE | Jessie J - Flashlight (from Pitch Perfec |  | 19 | 10 | 10 | 0/1/5/2/1 | 37730119 | 0 | 3 | 1 | 3 |  | no reference | 9244184 | mistimed | no | yes |
| joint | 0 | qMxX-QOV9tI | Jessie J - Price Tag ft. B.o.B |  | 19 | 12 | 10 | 1/0/8/0/0 | 6900889 | 0 | 6 | 1 | 2 |  | no reference | 6900889 | passes | yes | yes |
| caption | 0 | 450p7goxZqg | John Legend - All of Me |  | 19 | 12 | 19 | 0/0/0/0/0 | 22517354 | 0 | 1 | 1 | 6 | 1 | none |  |  |  | yes |
| joint | 0 | _8jNbZIsBQU | Jonathan Groff - Lost in the Woods (From |  | 20 | 5 | 0 | 0/0/0/20/0 |  |  |  |  |  |  |  | 23363506 | unclaimed |  |  |
| caption | 0 | Z3x9i7njCCo | Jung Kook 정국 - 3D (feat. Jack Harlow) (L |  | 20 | 12 | 8 | 9/0/3/0/0 | 8987220 | 0 | 6 | 2 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | 1QYBiNRu1ok | Jung Kook 정국 - Seven (feat. Latto) |  | 20 | 13 | 18 | 0/0/2/0/0 | 31432999 | 0 | 4 | 0 | 4 |  | no reference | 33562631 | passes | no | yes |
| caption | 0 | 6q0JnftlH-I | Jung Kook 정국 - Standing Next to You |  | 18 | 10 | 0 | 0/1/17/0/0 |  |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | FQ3slUz7Jo8 | Justin Timberlake - Like I Love You |  | 19 | 7 | 17 | 1/0/0/1/0 | 19983370 | 0 | 4 | 1 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | uuZE_IRwLNI | Justin Timberlake - Mirrors |  | 20 | 7 | 0 | 0/0/1/19/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | TSVHoHyErBQ | Justin Timberlake - Rock Your Body |  | 20 | 8 | 0 | 0/0/17/3/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | je0roKRn3nY | Justin Timberlake - Selfish |  | 20 | 9 | 20 | 0/0/0/0/0 | 5659554 | 0 | 2 | 0 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | IsUsVbTj2AY | Justin Timberlake - Suit & Tie (feat. JA |  | 15 | 10 | 8 | 1/0/1/0/5 | 30120287 | 0 | 11 | 1 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | KPop Demon Hunters (2025) - Free | KPop Demon Hunters (2025) - Free |  | 17 | 10 | 0 | 4/0/0/13/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | yebNIHKAC4A | KPop Demon Hunters (2025) - Golden |  | 14 | 8 | 4 | 5/4/0/1/0 | 23163059 | 0 | 8 | 0 | 3 |  | no reference | 31005537 | passes | no | yes |
| caption | 0 | KPop Demon Hunters (2025) - How It's Done | KPop Demon Hunters (2025) - How It's Don |  | 14 | 7 | 0 | 0/0/0/14/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | 983bBbJx0Mk | KPop Demon Hunters (2025) - Soda Pop |  | 19 | 8 | 0 | 19/0/0/0/0 |  |  |  |  |  |  |  | 36713302 | no_fit |  |  |
| picks | 0 | j5itLHDMJsE | KPop Demon Hunters (2025) - Takedown |  | 20 | 8 | 19 | 0/1/0/0/0 | 30356707 | 0 | 8 | 1 | 3 |  | no reference | 22746532 | passes | no | yes |
| caption | 0 | KPop Demon Hunters (2025) - What It Sounds Like | KPop Demon Hunters (2025) - What It Soun |  | 15 | 7 | 0 | 0/15/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | fGyTN5UjnL4 | KPop Demon Hunters (2025) - Your Idol |  | 18 | 9 | 16 | 1/0/1/0/0 | 23310716 | 1 | 8 | 1 | 4 |  | no reference | 37123328 | passes | no | yes |
| caption | 0 | Ra-Om7UMSJc | Kelly Clarkson - Because Of You |  | 19 | 8 | 15 | 0/4/0/0/0 | 18765707 | 0 | 2 | 0 | 9 | 1 | none |  |  |  | yes |
| joint | 0 | ZrX1XKtShSI | Kristen Bell, Idina Menzel - For the Fir |  | 20 | 7 | 18 | 2/0/0/0/0 | 14589928 | 0 | 2 | 1 | 7 |  | no reference | 7840239 | passes | yes | yes |
| caption | 0 | zABLecsR5UE | Lewis Capaldi - Someone You Loved |  | 20 | 13 | 19 | 0/1/0/0/0 | 27564454 | 0 | 4 | 0 | 4 | 1 | none |  |  |  | yes |
| joint | 0 | ILRs2r6lcHY | Mandy Moore, Zachary Levi - I See the Li |  | 20 | 8 | 0 | 20/0/0/0/0 |  |  |  |  |  |  |  | 34228750 | no_fit |  |  |
| joint | 0 | HLCasyAh7ic | Michelle Branch - Everywhere [Official M |  | 17 | 8 | 14 | 3/0/0/0/0 | 19297649 | 0 | 6 | 1 | 8 |  | no reference | 30723998 | passes | yes | yes |
| caption | 0 | cPAbx5kgCJo | Moana (2016) - How Far I'll Go |  | 14 | 13 | 2 | 11/0/0/1/0 | 3292118 | 0 | 2 | 1 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | 93lrosBEW-Q | Moana (2016) - Shiny |  | 13 | 7 | 0 | 1/0/11/1/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | 79DijItQXMM | Moana (2016) - You're Welcome |  | 5 | 4 | 0 | 1/0/0/4/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | -fxh7jAJR8U | NSYNC - (God Must Have Spent) A Little M |  | 20 | 13 | 4 | 1/8/7/0/0 | 28155617 | 0 | 11 | 1 | 3 | 1 | ref_unclaimed |  |  |  | yes |
| caption | 0 | Eo-KmOd3i7s | NSYNC - Bye Bye Bye |  | 20 | 13 | 0 | 13/2/0/5/0 |  |  |  |  |  | 0 |  |  |  |  |  |
| caption | 0 | saxnXiBKEaY | NSYNC - Girlfriend |  | 18 | 9 | 0 | 0/0/17/1/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | IbRwSI8yi1o | NSYNC - Gone |  | 20 | 12 | 15 | 4/0/0/1/0 | 32643931 | 0 | 7 | 1 | 4 | 1 | none |  |  |  | yes |
| joint | 0 | n-2C2wOFavc | NSYNC - I Want You Back (US Version - Of |  | 16 | 9 | 2 | 1/0/0/13/0 | 6955667 | 0 | 3 | 0 | 1 |  | no reference | 32016974 | unclaimed | no | yes |
| caption | 0 | GQMlWwIXg3M | NSYNC - It's Gonna Be Me |  | 20 | 14 | 20 | 0/0/0/0/0 | 13572204 | 0 | 5 | 1 | 4 | 1 | none |  |  |  | yes |
| picks | 0 | NSYNC - Paradise | NSYNC - Paradise |  | 18 | 5 | 18 | 0/0/0/0/0 | 9488086 | 1 | 6 | 1 | 9 |  | no reference | 27903107 | passes | yes | no |
| caption | 0 | TWZKw_MgUPI | NSYNC - Pop |  | 20 | 12 | 0 | 0/0/20/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | PodgxWsZw9s | NSYNC - Thinking Of You (I Drive Myself  |  | 20 | 9 | 0 | 0/7/0/13/0 |  |  |  |  |  |  |  | 36176943 | unclaimed |  |  |
| caption | 0 | 6thmPrTxBtI | NSYNC - This I Promise You |  | 20 | 10 | 8 | 3/2/7/0/0 | 23889061 | 0 | 5 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | atz_aZA3rf0 | Ne-Yo - Because Of You |  | 20 | 9 | 0 | 0/2/4/14/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | k6M5C-oKw9k | Ne-Yo - Miss Independent |  | 20 | 10 | 0 | 0/0/0/20/0 |  |  |  |  |  |  |  | 12997477 | unclaimed |  |  |
| caption | 0 | 6tpl9LtkRRw | Ne-Yo - One In A Million |  | 20 | 9 | 0 | 0/0/7/13/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | IxszlJppRQI | Ne-Yo - So Sick |  | 18 | 11 | 14 | 0/2/2/0/0 | 16652439 | 0 | 7 | 1 | 3 | 1 | none |  |  |  | yes |
| picks | 0 | 9ThO76peOw0 | Pocahontas (1995) - Colors of the Wind |  | 11 | 6 | 1 | 6/4/0/0/0 | 34484694 | 0 | 4 | 1 | 1 |  | no reference | 35708272 | passes | no | yes |
| caption | 0 | fJ9rUzIMcZQ | Queen - Bohemian Rhapsody |  | 19 | 12 | 16 | 0/0/2/0/1 | 21655132 | 0 | 7 | 1 | 8 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Another Day | Rent (2005) - Another Day |  | 12 | 5 | 9 | 0/3/0/0/0 | 6156119 | 0 | 9 | 0 | 6 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - I Should Tell You | Rent (2005) - I Should Tell You |  | 20 | 7 | 15 | 1/4/0/0/0 | 6191521 | 0 | 3 | 2 | 10 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - I'll Cover You | Rent (2005) - I'll Cover You |  | 17 | 4 | 14 | 3/0/0/0/0 | 6191556 | 0 | 3 | 0 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Light My Candle | Rent (2005) - Light My Candle |  | 15 | 5 | 3 | 0/0/0/12/0 | 36678024 | 0 | 4 | 1 | 2 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - One Song Glory | Rent (2005) - One Song Glory |  | 20 | 6 | 16 | 0/3/0/0/1 | 6932651 | 0 | 3 | 1 | 15 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Out Tonight | Rent (2005) - Out Tonight |  | 20 | 6 | 14 | 0/6/0/0/0 | 6932715 | 0 | 5 | 1 | 9 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Santa Fe | Rent (2005) - Santa Fe |  | 20 | 7 | 0 | 6/0/4/10/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Rent (2005) - Seasons of Love | Rent (2005) - Seasons of Love |  | 12 | 7 | 10 | 0/0/0/2/0 | 36786874 | 0 | 6 | 0 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Today 4 U | Rent (2005) - Today 4 U |  | 4 | 2 | 0 | 0/0/0/4/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | Rent (2005) - What You Own | Rent (2005) - What You Own |  | 14 | 5 | 5 | 0/9/0/0/0 | 28181941 | 0 | 2 | 2 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Without You | Rent (2005) - Without You |  | 17 | 7 | 12 | 0/5/0/0/0 | 6934735 | 1 | 2 | 2 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | Rent (2005) - Your Eyes | Rent (2005) - Your Eyes |  | 19 | 8 | 9 | 0/10/0/0/0 | 21412032 | 0 | 1 | 0 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | WB9_sf6oV1o | S Club 7 - Never Had A Dream Come True |  | 20 | 8 | 20 | 0/0/0/0/0 | 32607617 | 0 | 2 | 1 | 11 | 1 | none |  |  |  | yes |
| joint | 0 | rEXhAMtbaec | Sara Bareilles - Gravity (Official HD Vi |  | 19 | 8 | 13 | 1/5/0/0/0 | 36844599 | 0 | 4 | 1 | 8 |  | no reference | 29516072 | passes | yes | yes |
| joint | 0 | eR7-AUmiNcA | Sara Bareilles - King of Anything (Offic |  | 19 | 5 | 0 | 0/0/0/19/0 |  |  |  |  |  |  |  | 7856460 | unclaimed |  |  |
| picks | 0 | 53GIADHxVzM | Sara Bareilles - She Used To Be Mine |  | 19 | 9 | 14 | 1/4/0/0/0 | 12564402 | 0 | 3 | 0 | 6 |  | no reference | 9845205 | passes | no | yes |
| picks | 0 | wIyNAsmGrl0 | Silk Sonic (Bruno Mars & Anderson .Paak) |  | 20 | 12 | 0 | 1/0/5/14/0 |  |  |  |  |  |  |  | 1952973 | unclaimed |  |  |
| picks | 0 | CEw-7cMnBDY | Silk Sonic (Bruno Mars & Anderson .Paak) |  | 20 | 8 | 20 | 0/0/0/0/0 | 11390531 | 0 | 7 | 0 | 8 |  | no reference | 14315468 | passes | yes | no |
| picks | 0 | kRXmAIHYQR4 | Tangled (2010) - When Will My Life Begin |  | 18 | 10 | 18 | 0/0/0/0/0 | 24795512 | 0 | 2 | 1 | 3 |  | no reference | 13183578 | passes | no | yes |
| joint | 0 | zi5Z6rNU9Hw | Tangled - Cast - I've Got a Dream (From  |  | 20 | 8 | 17 | 0/3/0/0/0 | 29290799 | 0 | 4 | 0 | 5 |  | no reference | 29201073 | passes | no | yes |
| caption | 0 | _lK4cX5xGiQ | Tenacious D - Tribute |  | 20 | 5 | 0 | 0/0/0/20/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - A Miracle Would Happen & When You Come Home to Me | The Last Five Years (2014) - A Miracle W |  | 9 | 4 | 0 | 2/0/7/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - A Summer in Ohio | The Last Five Years (2014) - A Summer in |  | 10 | 5 | 0 | 0/5/3/0/2 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Climbing Uphill | The Last Five Years (2014) - Climbing Up |  | 15 | 4 | 0 | 7/3/5/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Goodbye Until Tomorrow & I Could Never Rescue You | The Last Five Years (2014) - Goodbye Unt |  | 9 | 5 | 0 | 4/0/5/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - I Can Do Better Than That | The Last Five Years (2014) - I Can Do Be |  | 12 | 5 | 6 | 0/6/0/0/0 | 4179244 | 0 | 10 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - I'm a Part of That | The Last Five Years (2014) - I'm a Part  |  | 0 | 0 | 0 | 0/0/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - If I Didn't Believe in You | The Last Five Years (2014) - If I Didn't |  | 10 | 5 | 0 | 1/3/0/6/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Moving Too Fast | The Last Five Years (2014) - Moving Too  |  | 11 | 5 | 0 | 7/0/4/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Nobody Needs to Know | The Last Five Years (2014) - Nobody Need |  | 16 | 5 | 3 | 6/3/0/0/4 | 17631826 | 1 | 3 | 2 | 3 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - See I'm Smiling | The Last Five Years (2014) - See I'm Smi |  | 19 | 9 | 0 | 19/0/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Shiksa Goddess | The Last Five Years (2014) - Shiksa Godd |  | 11 | 5 | 0 | 5/0/6/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | The Last Five Years (2014) - Still Hurting | The Last Five Years (2014) - Still Hurti |  | 17 | 8 | 6 | 3/8/0/0/0 | 4188091 | 0 | 1 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - The Next Ten Minutes | The Last Five Years (2014) - The Next Te |  | 17 | 6 | 8 | 3/6/0/0/0 | 4189082 | 0 | 6 | 2 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | The Last Five Years (2014) - The Schmuel Song | The Last Five Years (2014) - The Schmuel |  | 13 | 6 | 0 | 4/1/3/5/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | GibiNy4d4gc | The Lion King (1994) - Circle of Life |  | 9 | 6 | 0 | 1/4/0/4/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | SXKlJuO07eM | The Little Mermaid (1989) - Part of Your |  | 14 | 10 | 2 | 10/2/0/0/0 | 30097702 | 0 | 2 | 1 | 1 | 1 | none |  |  |  | yes |
| caption | 0 | GC_mV1IpjWA | The Little Mermaid (1989) - Under the Se |  | 17 | 8 | 0 | 3/14/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | kHwpS0LakeU | The Lonely Island - Here I Go (feat. Cha |  | 0 | 0 | 0 | 0/0/0/0/0 |  |  |  |  |  |  |  |  |  |  |  |
| joint | 0 | avaSdC0QOUM | The Lonely Island - I'm On A Boat (Expli |  | 20 | 7 | 0 | 0/0/0/20/0 |  |  |  |  |  |  |  | 36394001 | unclaimed |  |  |
| picks | 0 | 68LBPvFhMx0 | The Lonely Island - Jose & Mark |  | 5 | 2 | 5 | 0/0/0/0/0 | 2554162 | 0 | 5 | 1 | 4 |  | no reference | 17370761 | passes | no | yes |
| picks | 0 | hj4e709GYf4 | The Lonely Island - Let's Bash |  | 7 | 1 | 7 | 0/0/0/0/0 | 1116686 | 0 | 3 | 0 | 7 |  | no reference | 17273734 | passes | yes | no |
| picks | 0 | gAYL5H46QnQ | The Lonely Island - Threw It On The Grou |  | 20 | 10 | 20 | 0/0/0/0/0 | 35338143 | 0 | 2 | 1 | 6 |  | no reference | 39765748 | passes | no | yes |
| picks | 0 | XzbHPqULtdA | The Outsiders (2024) - Stay Gold |  | 13 | 7 | 4 | 9/0/0/0/0 | 27305964 | 0 | 2 | 1 | 4 |  | no reference | 34445486 | passes | yes | no |
| caption | 0 | EUW0eDhKoxw | The Philosopher Kings - Cry |  | 5 | 1 | 5 | 0/0/0/0/0 | 28361150 | 0 | 9 | 1 | 5 | 1 | none |  |  |  | yes |
| caption | 0 | 6X4bhT1FWjI | The Philosopher Kings - Hurts To Love Yo |  | 4 | 2 | 0 | 4/0/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| caption | 0 | AI7F8qlN44E | The Philosopher Kings - You Don't Love M |  | 6 | 2 | 0 | 0/0/0/6/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| picks | 0 | tz_NxOF7RB4 | Vitamin C - Graduation (Friends Forever) |  | 20 | 7 | 1 | 2/0/17/0/0 | 9980085 | 1 | 10 | 1 | 1 |  | no reference | 9980085 | passes | yes | no |
| joint | 0 | vKPGxGCFgTs | Westlife - Flying Without Wings (Officia |  | 20 | 9 | 17 | 0/3/0/0/0 | 1512603 | 0 | 3 | 0 | 8 |  | no reference | 7834744 | passes | no | yes |
| joint | 0 | RTWhvp_OD6s | Where You Are (From 'Moana'_Sing-Along) |  | 20 | 6 | 0 | 0/0/0/0/20 |  |  |  |  |  |  |  | 4490148 | shifted |  |  |
| caption | 0 | 3JWTaaS7LdU | Whitney Houston - I Will Always Love You |  | 20 | 9 | 11 | 4/5/0/0/0 | 29741730 | 0 | 1 | 1 | 7 | 1 | none |  |  |  | yes |
| caption | 0 | TZ0pXUb5jVU | Wicked (2003) - For Good |  | 17 | 6 | 0 | 8/9/0/0/0 |  |  |  |  |  | 1 |  |  |  |  |  |
| joint | 0 | z5Otla5157c | YOLO (feat. Adam Levine & Kendrick Lamar |  | 19 | 10 | 19 | 0/0/0/0/0 | 1019299 | 0 | 6 | 0 | 5 |  | no reference | 17904967 | passes | no | yes |
| caption | 0 | rg_zwK_sSEY | ZAYN & Zhavia Ward - A Whole New World ( |  | 20 | 9 | 20 | 0/0/0/0/0 | 7428207 | 0 | 9 | 1 | 5 | 1 | none |  |  |  | yes |

### Table K: GATE M LRC-wrong records

| youtube_id | lrclib_id | Source | In_pool | Status | Speed | Mistimed | Unclaimed | Refusal | Picked | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| GZXHBgjQjNM | 20242140 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 21912586 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 27023721 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 31535578 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 32140003 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 35793714 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| GZXHBgjQjNM | 36228137 | pool | yes | fits | 1.0000 | 1 | 6 | passes | no |  |
| AJWtLf4-WWs | 6800151 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| AJWtLf4-WWs | 28307055 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| AJWtLf4-WWs | 34352818 | pool | yes | fits | 1.0000 | 1 | 14 | unclaimed | no |  |
| UAWcs5H-qgQ | 12572148 | pool | yes | fits | 1.0000 | 0 | 89 | unclaimed | no |  |
| T6wbugWrfLU | 35468507 | pool | yes | fits | 1.0000 | 0 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 3458703 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 6335685 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 7720552 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 9641374 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12149023 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12377831 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 12515974 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 15413449 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 17099666 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 20411476 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 23305471 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 24586049 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 24809544 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 31956521 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 32182355 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 32691192 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 33133897 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |
| T6wbugWrfLU | 34902348 | pool | yes | fits | 1.0000 | 1 | 20 | unclaimed | no |  |

### Table G: GATE P wrong records

| youtube_id | lrclib_id | Found | Status | Mistimed | Unclaimed | Shift_run | Refusal | Picked | Asr_status | Asr_shift_run | Asr_mistimed | Asr_unheard | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RTWhvp_OD6s | 28421947 | yes | fits | 0 | 10 | 13 | shifted | no |  |  |  |  |  |
| ekzHIouo8Q4 | 26614056 | yes | fits | 0 | 7 | 3 | shifted | no | fits | 4 | 1 | 1 |  |
| The Last Five Years (2014) - A Summer in Ohio | 23648746 | yes | fits | 0 | 10 | 12 | shifted | no |  |  |  |  |  |
| The Last Five Years (2014) - Nobody Needs to Know | 4626353 | yes | fits | 1 | 4 | 4 | shifted | no |  |  |  |  |  |
| Flight of the Conchords (2007) - Bowie | 19452078 | yes | fits | 1 | 10 | 3 | shifted | no |  |  |  |  |  |
| Q4VK9_CfOLQ | 2137556 | yes | fits | 1 | 7 | 1 | passes | yes |  |  |  |  |  |
| RNprQYHenNI | 685756 | yes | fits | 0 | 3 | 1 | passes | yes |  |  |  |  |  |

### Table A: picks the second-hearing rule changes

| Group | youtube_id | Title | Pick | Pick_flags | Asr_pick | Asr_pick_flags |
|---|---|---|---|---|---|---|

### Table C: picks that differ from /home/ken/.pikaraoke/tmp/lrclib_fit_pick_holdout/songs.tsv

| Group | youtube_id | Title | Compared_pick | Pick |
|---|---|---|---|---|
| joint | ekzHIouo8Q4 | Bruno Mars - When I Was Your Man (Offici | 26614056 | 15816725 |
| caption | Flight of the Conchords (2007) - Bowie | Flight of the Conchords (2007) - Bowie | 19452078 | none |
| caption | The Last Five Years (2014) - A Summer in Ohio | The Last Five Years (2014) - A Summer in | 23648746 | none |
| caption | The Last Five Years (2014) - Nobody Needs to Know | The Last Five Years (2014) - Nobody Need | 4626353 | 17631826 |
| joint | RTWhvp_OD6s | Where You Are (From 'Moana'_Sing-Along) | 28421947 | none |

### Table V: songs with a pick at other limits

| Group | Mistimed <= | Songs | Unclaimed <= 8 | Unclaimed <= 10 | Unclaimed <= 12 | Unclaimed <= 15 | Unclaimed <= 20 |
|---|---|---|---|---|---|---|---|
| picks | 0 | 28 | 16 | 17 | 18 | 18 | 19 |
| picks | 1 | 28 | 20 | 22 | 23 | 23 | 24 |
| joint | 0 | 34 | 19 | 20 | 20 | 20 | 22 |
| joint | 1 | 34 | 19 | 20 | 20 | 21 | 23 |
| caption | 0 | 112 | 48 | 50 | 53 | 55 | 59 |
| caption | 1 | 112 | 54 | 56 | 59 | 62 | 67 |
| new | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| new | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

| Group | Shift offset >= s | Songs | Shift run <= 2 | Shift run <= 3 | Shift run <= 4 |
|---|---|---|---|---|---|
| picks | 1.0 | 28 | 23 | 23 | 23 |
| picks | 1.5 | 28 | 23 | 23 | 23 |
| picks | 2.0 | 28 | 23 | 23 | 23 |
| joint | 1.0 | 34 | 20 | 20 | 20 |
| joint | 1.5 | 34 | 20 | 20 | 20 |
| joint | 2.0 | 34 | 20 | 21 | 21 |
| caption | 1.0 | 112 | 58 | 60 | 60 |
| caption | 1.5 | 112 | 59 | 60 | 60 |
| caption | 2.0 | 112 | 59 | 60 | 60 |
| new | 1.0 | 0 | 0 | 0 | 0 |
| new | 1.5 | 0 | 0 | 0 | 0 |
| new | 2.0 | 0 | 0 | 0 | 0 |

### Table L: the listen list

| Rank | Group | New | Title | youtube_id | lrclib_id | Why | Listen_file |
|---|---|---|---|---|---|---|---|
| 1 | picks | 0 | Frozen (2013) - In Summer (Sing-Along) | 9tcaM06eGrY | 3630452 | no reference | Frozen (2013) - In Summer (Sing-Along)---9tcaM06eGrY.3630452.srt |
| 2 | joint | 0 | Bruno Mars - The Lazy Song (Official Mus | fLexgOxsZu0 | 6706711 | no reference | Bruno Mars - The Lazy Song (Official Music Video)---fLexgOxsZu0.6706711.srt |
| 3 | picks | 0 | Camp Rock (2008) - This Is Me (Sing-Alon | 6HCUoMgviwU | 17015895 | no reference | Camp Rock (2008) - This Is Me (Sing-Along)---6HCUoMgviwU.17015895.srt |
| 4 | picks | 0 | KPop Demon Hunters (2025) - Your Idol | fGyTN5UjnL4 | 23310716 | no reference | KPop Demon Hunters (2025) - Your Idol---fGyTN5UjnL4.23310716.srt |
| 5 | picks | 0 | KPop Demon Hunters (2025) - Takedown | j5itLHDMJsE | 30356707 | no reference | KPop Demon Hunters (2025) - Takedown---j5itLHDMJsE.30356707.srt |
| 6 | picks | 0 | KPop Demon Hunters (2025) - Golden | yebNIHKAC4A | 23163059 | no reference | KPop Demon Hunters (2025) - Golden---yebNIHKAC4A.23163059.srt |
| 7 | joint | 0 | Demi Lovato, Joe Jonas - Wouldn't Change | 62llzl7iKkE | 33991259 | no reference | Demi Lovato, Joe Jonas - Wouldn't Change a Thing (From 'Camp Rock 2 - The Final Jam'_Sing-Along)---62llzl7iKkE.33991259.srt |
| 8 | joint | 0 | Bruno Mars - Just The Way You Are (Offic | LjhCEhWiKXk | 9888181 | no reference | Bruno Mars - Just The Way You Are (Official Music Video)---LjhCEhWiKXk.9888181.srt |
| 9 | joint | 0 | Bruno Mars - Locked Out Of Heaven (Offic | e-fA-gBCkj0 | 6936310 | no reference | Bruno Mars - Locked Out Of Heaven (Official Music Video)---e-fA-gBCkj0.6936310.srt |
| 10 | joint | 0 | Bruno Mars - When I Was Your Man (Offici | ekzHIouo8Q4 | 15816725 | no reference | Bruno Mars - When I Was Your Man (Official Music Video)---ekzHIouo8Q4.15816725.srt |
| 11 | joint | 0 | I Just Had Sex (feat. Akon) | lQlIhraqL7o | 11579404 | no reference | I Just Had Sex (feat. Akon)---lQlIhraqL7o.11579404.srt |
| 12 | joint | 0 | Michelle Branch - Everywhere [Official M | HLCasyAh7ic | 19297649 | no reference | Michelle Branch - Everywhere [Official Music Video]---HLCasyAh7ic.19297649.srt |
| 13 | joint | 0 | Jessie J - Price Tag ft. B.o.B | qMxX-QOV9tI | 6900889 | no reference | Jessie J - Price Tag ft. B.o.B---qMxX-QOV9tI.6900889.srt |
| 14 | joint | 0 | YOLO (feat. Adam Levine & Kendrick Lamar | z5Otla5157c | 1019299 | no reference | YOLO (feat. Adam Levine & Kendrick Lamar)---z5Otla5157c.1019299.srt |
| 15 | picks | 0 | The Lonely Island - Jose & Mark | 68LBPvFhMx0 | 2554162 | no reference | The Lonely Island - Jose & Mark---68LBPvFhMx0.2554162.srt |
| 16 | joint | 0 | Jack Sparrow (feat. Michael Bolton) | GI6CfKcMhjY | 22000139 | no reference | Jack Sparrow (feat. Michael Bolton)---GI6CfKcMhjY.22000139.srt |
| 17 | joint | 0 | Ingrid Michaelson 'Be OK' (Official Vide | vpMI8Qu5fsc | 326004 | no reference | Ingrid Michaelson 'Be OK' (Official Video)---vpMI8Qu5fsc.326004.srt |
| 18 | picks | 0 | Frozen (2013) - Do You Want to Build a S | TeQ_TTyLGMs | 3514723 | no reference | Frozen (2013) - Do You Want to Build a Snowman (Sing-Along)---TeQ_TTyLGMs.3514723.srt |
| 19 | picks | 0 | Jung Kook 정국 - Seven (feat. Latto) | 1QYBiNRu1ok | 31432999 | no reference | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok.31432999.srt |
| 20 | picks | 0 | Pocahontas (1995) - Colors of the Wind | 9ThO76peOw0 | 34484694 | no reference | Pocahontas (1995) - Colors of the Wind---9ThO76peOw0.34484694.srt |
| 21 | joint | 0 | Backstreet Boys - Show Me The Meaning Of | aBt8fN7mJNg | 19923333 | no reference | Backstreet Boys - Show Me The Meaning Of Being Lonely (Official Video)---aBt8fN7mJNg.19923333.srt |
| 22 | joint | 0 | Sara Bareilles - Gravity (Official HD Vi | rEXhAMtbaec | 36844599 | no reference | Sara Bareilles - Gravity (Official HD Video)---rEXhAMtbaec.36844599.srt |
| 23 | joint | 0 | Tangled - Cast - I've Got a Dream (From  | zi5Z6rNU9Hw | 29290799 | no reference | Tangled - Cast - I've Got a Dream (From 'Tangled'_Sing-Along)---zi5Z6rNU9Hw.29290799.srt |
| 24 | picks | 0 | Sara Bareilles - She Used To Be Mine | 53GIADHxVzM | 12564402 | no reference | Sara Bareilles - She Used To Be Mine---53GIADHxVzM.12564402.srt |
| 25 | caption | 0 | Céline Dion - My Heart Will Go On (Titan | 9bFHsd3o1w0 | 22553995 | no reference | Céline Dion - My Heart Will Go On (Titanic, 1997)---9bFHsd3o1w0.22553995.srt |
| 26 | joint | 0 | Jessie J - Flashlight (from Pitch Perfec | DzwkcbTQ7ZE | 37730119 | no reference | Jessie J - Flashlight (from Pitch Perfect 2) (Official Video)---DzwkcbTQ7ZE.37730119.srt |
| 27 | caption | 0 | Céline Dion - I'm Alive (Stuart Little 2 | NJsa6-y4sDs | 28130840 | no reference | Céline Dion - I'm Alive (Stuart Little 2, 2002)---NJsa6-y4sDs.28130840.srt |
| 28 | joint | 0 | NSYNC - I Want You Back (US Version - Of | n-2C2wOFavc | 6955667 | no reference | NSYNC - I Want You Back (US Version - Official Video)---n-2C2wOFavc.6955667.srt |
| 29 | joint | 0 | Westlife - Flying Without Wings (Officia | vKPGxGCFgTs | 1512603 | no reference | Westlife - Flying Without Wings (Official Video)---vKPGxGCFgTs.1512603.srt |
| 30 | joint | 0 | Bruno Mars - Grenade (Official Music Vid | SR6iYWJxHqs | 38953751 | no reference | Bruno Mars - Grenade (Official Music Video)---SR6iYWJxHqs.38953751.srt |
| 31 | picks | 0 | Jessie J - Domino | UJtB55MaoD0 | 28220836 | no reference | Jessie J - Domino---UJtB55MaoD0.28220836.srt |
| 32 | joint | 0 | Kristen Bell, Idina Menzel - For the Fir | ZrX1XKtShSI | 14589928 | no reference | Kristen Bell, Idina Menzel - For the First Time in Forever (From 'Frozen'_Sing-Along)---ZrX1XKtShSI.14589928.srt |
| 33 | picks | 0 | The Lonely Island - Threw It On The Grou | gAYL5H46QnQ | 35338143 | no reference | The Lonely Island - Threw It On The Ground---gAYL5H46QnQ.35338143.srt |
| 34 | picks | 0 | Tangled (2010) - When Will My Life Begin | kRXmAIHYQR4 | 24795512 | no reference | Tangled (2010) - When Will My Life Begin (Sing-Along)---kRXmAIHYQR4.24795512.srt |
| 35 | joint | 0 | Idina Menzel, AURORA - Into the Unknown  | mzhv_dg_UBA | 36372778 | no reference | Idina Menzel, AURORA - Into the Unknown (From 'Frozen 2'_Sing-Along)---mzhv_dg_UBA.36372778.srt |
| 36 | picks | 0 | Ingrid Michaelson - The Way I Am | Vh74KE3o4Bs | 1781541 | no reference | Ingrid Michaelson - The Way I Am---Vh74KE3o4Bs.1781541.srt |
| 37 | caption | 0 | NSYNC - (God Must Have Spent) A Little M | -fxh7jAJR8U | 28155617 | flagged: ref_unclaimed | NSYNC - (God Must Have Spent) A Little More Time On You----fxh7jAJR8U.28155617.srt |
| 38 | caption | 0 | Britney Spears - (You Drive Me) Crazy | Q4VK9_CfOLQ | 2137556 | flagged: ref_mistimed | Britney Spears - (You Drive Me) Crazy---Q4VK9_CfOLQ.2137556.srt |
| 39 | caption | 0 | Ed Sheeran - Happier | iWZmdoY1aTE | 29277988 | flagged: ref_unclaimed | Ed Sheeran - Happier---iWZmdoY1aTE.29277988.srt |
| 40 | caption | 0 | Backstreet Boys - Get Down (You're The O | 0LSYuZRSGcY | 1124886 | flagged: ref_unclaimed | Backstreet Boys - Get Down (You're The One For Me)---0LSYuZRSGcY.1124886.srt |
| 41 | caption | 0 | Backstreet Boys - Quit Playing Games (Wi | Ug88HO2mg44 | 33413907 | flagged: ref_shift_run | Backstreet Boys - Quit Playing Games (With My Heart)---Ug88HO2mg44.33413907.srt |
| 42 | caption | 0 | Christina Aguilera - Reflection (Mulan,  | RNprQYHenNI | 685756 | flagged: ref_mistimed | Christina Aguilera - Reflection (Mulan, 2020)---RNprQYHenNI.685756.srt |
| 43 | caption | 0 | Colbie Caillat - Realize | GlZxZ2n2zpw | 37946467 | unflagged | Colbie Caillat - Realize---GlZxZ2n2zpw.37946467.srt |
| 44 | caption | 0 | Justin Timberlake - Suit & Tie (feat. JA | IsUsVbTj2AY | 30120287 | unflagged | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY.30120287.srt |
| 45 | caption | 0 | The Last Five Years (2014) - I Can Do Be | The Last Five Years (2014) - I Can Do Better Than That | 4179244 | unflagged | The Last Five Years (2014) - I Can Do Better Than That.4179244.srt |
| 46 | caption | 0 | The Philosopher Kings - Cry | EUW0eDhKoxw | 28361150 | unflagged | The Philosopher Kings - Cry---EUW0eDhKoxw.28361150.srt |
| 47 | caption | 0 | Rent (2005) - Another Day | Rent (2005) - Another Day | 6156119 | unflagged | Rent (2005) - Another Day.6156119.srt |
| 48 | caption | 0 | ZAYN & Zhavia Ward - A Whole New World ( | rg_zwK_sSEY | 7428207 | unflagged | ZAYN & Zhavia Ward - A Whole New World (End Title) (Aladdin, 2019)---rg_zwK_sSEY.7428207.srt |
| 49 | caption | 0 | Backstreet Boys - As Long As You Love Me | 0Gl2QnHNpkA | 3722851 | unflagged | Backstreet Boys - As Long As You Love Me---0Gl2QnHNpkA.3722851.srt |
| 50 | caption | 0 | NSYNC - Gone | IbRwSI8yi1o | 32643931 | unflagged | NSYNC - Gone---IbRwSI8yi1o.32643931.srt |
| 51 | caption | 0 | Ne-Yo - So Sick | IxszlJppRQI | 16652439 | unflagged | Ne-Yo - So Sick---IxszlJppRQI.16652439.srt |
| 52 | caption | 0 | BTS 방탄소년단 - Butter | WMweEpGlu_U | 32156281 | unflagged | BTS 방탄소년단 - Butter---WMweEpGlu_U.32156281.srt |
| 53 | caption | 0 | Queen - Bohemian Rhapsody | fJ9rUzIMcZQ | 21655132 | unflagged | Queen - Bohemian Rhapsody---fJ9rUzIMcZQ.21655132.srt |
| 54 | caption | 0 | Backstreet Boys - I Want It That Way | 4fndeDfaWCg | 11268019 | unflagged | Backstreet Boys - I Want It That Way---4fndeDfaWCg.11268019.srt |
| 55 | caption | 0 | Backstreet Boys - Drowning | GZXHBgjQjNM | 14595571 | unflagged | Backstreet Boys - Drowning---GZXHBgjQjNM.14595571.srt |
| 56 | caption | 0 | Ed Sheeran - Shape of You | JGwWNGJdvx8 | 22081383 | unflagged | Ed Sheeran - Shape of You---JGwWNGJdvx8.22081383.srt |
| 57 | caption | 0 | Backstreet Boys - Shape Of My Heart | OT5msu-dap8 | 22503174 | unflagged | Backstreet Boys - Shape Of My Heart---OT5msu-dap8.22503174.srt |
| 58 | caption | 0 | Rent (2005) - Seasons of Love | Rent (2005) - Seasons of Love | 36786874 | unflagged | Rent (2005) - Seasons of Love.36786874.srt |
| 59 | caption | 0 | The Last Five Years (2014) - The Next Te | The Last Five Years (2014) - The Next Ten Minutes | 4189082 | unflagged | The Last Five Years (2014) - The Next Ten Minutes.4189082.srt |
| 60 | caption | 0 | Jung Kook 정국 - 3D (feat. Jack Harlow) (L | Z3x9i7njCCo | 8987220 | unflagged | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo.8987220.srt |
| 61 | caption | 0 | Backstreet Boys - Inconsolable | qGDF_QcsKVI | 35522789 | unflagged | Backstreet Boys - Inconsolable---qGDF_QcsKVI.35522789.srt |
| 62 | caption | 0 | NSYNC - This I Promise You | 6thmPrTxBtI | 23889061 | unflagged | NSYNC - This I Promise You---6thmPrTxBtI.23889061.srt |
| 63 | caption | 0 | NSYNC - It's Gonna Be Me | GQMlWwIXg3M | 13572204 | unflagged | NSYNC - It's Gonna Be Me---GQMlWwIXg3M.13572204.srt |
| 64 | caption | 0 | Rent (2005) - Out Tonight | Rent (2005) - Out Tonight | 6932715 | unflagged | Rent (2005) - Out Tonight.6932715.srt |
| 65 | caption | 0 | Ariana Grande & John Legend - Beauty and | axySrE0Kg6k | 31988497 | unflagged | Ariana Grande & John Legend - Beauty and the Beast (Beauty and the Beast, 2017)---axySrE0Kg6k.31988497.srt |
| 66 | caption | 0 | Backstreet Boys - Incomplete | WVe80iZtlYU | 19180415 | unflagged | Backstreet Boys - Incomplete---WVe80iZtlYU.19180415.srt |
| 67 | caption | 0 | Backstreet Boys - More Than That | 1OwfYjemrYw | 36314729 | unflagged | Backstreet Boys - More Than That---1OwfYjemrYw.36314729.srt |
| 68 | caption | 0 | Britney Spears - ...Baby One More Time | C-u5WLJ9Yk4 | 32110280 | unflagged | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4.32110280.srt |
| 69 | caption | 0 | Justin Timberlake - Like I Love You | FQ3slUz7Jo8 | 19983370 | unflagged | Justin Timberlake - Like I Love You---FQ3slUz7Jo8.19983370.srt |
| 70 | caption | 0 | Rent (2005) - Light My Candle | Rent (2005) - Light My Candle | 36678024 | unflagged | Rent (2005) - Light My Candle.36678024.srt |
| 71 | caption | 0 | Lewis Capaldi - Someone You Loved | zABLecsR5UE | 27564454 | unflagged | Lewis Capaldi - Someone You Loved---zABLecsR5UE.27564454.srt |
| 72 | caption | 0 | The Last Five Years (2014) - Nobody Need | The Last Five Years (2014) - Nobody Needs to Know | 17631826 | unflagged | The Last Five Years (2014) - Nobody Needs to Know.17631826.srt |
| 73 | caption | 0 | Ed Sheeran - Thinking Out Loud | lp-EO5I60KA | 20756048 | unflagged | Ed Sheeran - Thinking Out Loud---lp-EO5I60KA.20756048.srt |
| 74 | caption | 0 | Rent (2005) - I Should Tell You | Rent (2005) - I Should Tell You | 6191521 | unflagged | Rent (2005) - I Should Tell You.6191521.srt |
| 75 | caption | 0 | Rent (2005) - I'll Cover You | Rent (2005) - I'll Cover You | 6191556 | unflagged | Rent (2005) - I'll Cover You.6191556.srt |
| 76 | caption | 0 | Rent (2005) - One Song Glory | Rent (2005) - One Song Glory | 6932651 | unflagged | Rent (2005) - One Song Glory.6932651.srt |
| 77 | caption | 0 | Ed Sheeran - The A Team | UAWcs5H-qgQ | 19121007 | unflagged | Ed Sheeran - The A Team---UAWcs5H-qgQ.19121007.srt |
| 78 | caption | 0 | Frozen (2013) - Let It Go | YVVTZgwYwVo | 15035688 | unflagged | Frozen (2013) - Let It Go---YVVTZgwYwVo.15035688.srt |
| 79 | caption | 0 | Aladdin (2019) - Speechless | mw5VIEIvuMI | 19793188 | unflagged | Aladdin (2019) - Speechless---mw5VIEIvuMI.19793188.srt |
| 80 | caption | 0 | Ed Sheeran - Perfect | 2Vv-BfVoq4g | 19853882 | unflagged | Ed Sheeran - Perfect---2Vv-BfVoq4g.19853882.srt |
| 81 | caption | 0 | Rent (2005) - Without You | Rent (2005) - Without You | 6934735 | unflagged | Rent (2005) - Without You.6934735.srt |
| 82 | caption | 0 | Ed Sheeran - Castle On The Hill | K0ibBPhiaG0 | 23335586 | unflagged | Ed Sheeran - Castle On The Hill---K0ibBPhiaG0.23335586.srt |
| 83 | caption | 0 | Kelly Clarkson - Because Of You | Ra-Om7UMSJc | 18765707 | unflagged | Kelly Clarkson - Because Of You---Ra-Om7UMSJc.18765707.srt |
| 84 | caption | 0 | Rent (2005) - What You Own | Rent (2005) - What You Own | 28181941 | unflagged | Rent (2005) - What You Own.28181941.srt |
| 85 | caption | 0 | The Little Mermaid (1989) - Part of Your | SXKlJuO07eM | 30097702 | unflagged | The Little Mermaid (1989) - Part of Your World---SXKlJuO07eM.30097702.srt |
| 86 | caption | 0 | S Club 7 - Never Had A Dream Come True | WB9_sf6oV1o | 32607617 | unflagged | S Club 7 - Never Had A Dream Come True---WB9_sf6oV1o.32607617.srt |
| 87 | caption | 0 | Moana (2016) - How Far I'll Go | cPAbx5kgCJo | 3292118 | unflagged | Moana (2016) - How Far I'll Go---cPAbx5kgCJo.3292118.srt |
| 88 | caption | 0 | Adele - Someone Like You | hLQl3WQQoQ0 | 23116607 | unflagged | Adele - Someone Like You---hLQl3WQQoQ0.23116607.srt |
| 89 | caption | 0 | Justin Timberlake - Selfish | je0roKRn3nY | 5659554 | unflagged | Justin Timberlake - Selfish---je0roKRn3nY.5659554.srt |
| 90 | caption | 0 | Whitney Houston - I Will Always Love You | 3JWTaaS7LdU | 29741730 | unflagged | Whitney Houston - I Will Always Love You (The Bodyguard, 1992)---3JWTaaS7LdU.29741730.srt |
| 91 | caption | 0 | John Legend - All of Me | 450p7goxZqg | 22517354 | unflagged | John Legend - All of Me---450p7goxZqg.22517354.srt |
| 92 | caption | 0 | Rent (2005) - Your Eyes | Rent (2005) - Your Eyes | 21412032 | unflagged | Rent (2005) - Your Eyes.21412032.srt |
| 93 | caption | 0 | The Last Five Years (2014) - Still Hurti | The Last Five Years (2014) - Still Hurting | 4188091 | unflagged | The Last Five Years (2014) - Still Hurting.4188091.srt |

