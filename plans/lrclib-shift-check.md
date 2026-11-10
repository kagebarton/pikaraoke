Model: Claude Sonnet 5.5 (executor, Phases 1, 2, 3 and 4). Claude Opus 5.5 chooses the fresh
songs (Phase 0) and reads GATE F and GATE Q, then Ken. Author: Claude Fable 5.2, 2026-11-10.

# LRCLIB timing at download: the shifted-section check

**Status: PLANNED 2026-11-10. Nothing executed. Open for Ken before Phase 0: Decisions 20-24
are the author's defaults and he may overrule them.**

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
19. Sonnet executes. Opus chooses the fresh songs.

The author's defaults, not yet ruled by Ken:

20. Opus reads both gates (Ken's standing rule for judges). Fable is called only if Opus is
    unsure.
21. The fresh holdout is 50 songs: 20 that take a Genius pick, judged by Ken's ear, and 30 with
    uploader English captions, judged against their captions with no listening. They go in the
    library as the last thirty did; Ken deletes what he does not want afterwards.
22. `minor` (one missing lead line, or one line 3 to 5 s off) does not count as wrong. Grenade
    and Into the Unknown stay picks.
23. A wrong record that no check on heard words can reach is put to Ken at GATE F as a known
    hole, as Decision 12 was. He accepts it or stops. Expected: Reflection, and Crazy unless
    the second hearing reaches it.
24. Same branch, `lrclib_fit_pick`. The Phase 1 code of the earlier plan is reused.

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

**The candidate rule, fixed here:** when the song has an auto-caption file and the record's fit
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

## Phase 0: the fresh songs (Opus chooses, Ken adds; any time before Phase 4)

- **Used songs, done 2026-11-10:** `~/.pikaraoke/tmp/lrclib_shift_check/baseline_ids.txt`, 198
  lines, sha256 `1a764ddb9f814bbfb477c4cd67ae29edea1bd7fdcea9f44991adff4770dc777c`. Every
  song the earlier holdout run read. A song not in it is *new*.
- **Opus lists 50 songs** in a table here (song, YouTube id, set, kind), in a plan-only commit,
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
"/home/ken/shared-drives/D:/Shared/lrclib-listen" > <out>/report.md`.
Read-only check as before: `find <library> -newer <out>/started` lists nothing the probe
could have written (new song folders and files are Ken's import).

**2c. Expected, from the sizing.** Table C lists five songs and no others: Where You Are,
Bowie and A Summer in Ohio lose their pick; When I Was Your Man moves to 15816725; Nobody
Needs to Know moves to 17631826. Table G: five records refused `shifted`; 2137556 and 685756
pass and are picked. If Table C or Table G differs, record the difference raw and STOP. Do
not adjust a limit.

**2d.** Tables P, S, K, G, A, C, V and L pasted raw under "Report output: used songs". No
tallies, no reading. Plan-only commit.

**STOP 2e.** Handoff to Opus for GATE F. Ken listens to When I Was Your Man's new pick and to
Quit Playing Games (`Ug88HO2mg44`, 33413907, never ruled; about 1:57 to 2:05), from the listen
folder.

## GATE F: freeze the bar (Opus, then Ken)

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
5. **Ken rules:** the bar as pre-registered, or with the second-hearing rule, or stop. The
   judge writes the frozen bar and the ruling under "Frozen bar" in this file with the date.
   No limit changes at this gate. A different limit is a new plan.

## Phase 3: the second hearing in the bar (Sonnet; only if GATE F adds it)

`lrc_auto_pick.evaluate` and `pick` take the `asr` stream as an optional argument and apply
the rule as "The second hearing" writes it. Tests. The probe passes the stream. One commit.
Results row.

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
Opus for GATE Q once his verdicts are in.

## GATE Q (Opus, then Ken)

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

## Frozen bar

Not yet frozen (GATE F).
