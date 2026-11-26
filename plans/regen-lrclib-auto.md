# Regen: move joint Genius songs to an automatic LRCLIB pick

Model: Claude Sonnet 5.5 (executor). Plan and gates: Claude Opus 5.5.

Branch `regen_lrclib_auto`, worktree `.claude/worktrees/regen_lrclib_auto`, off `dev` `d2ed9a3b`.

**Status 2026-11-26:** Phase 1 built (`2a0afe1d`, Results row 1). Phase 2 dry run done (Results
row 2, Tables D-F under "Dry run output"). `/code-review` ran; its fixes are in `d13e8484`
(Results row 3). GATE D judged; Ken's answers are Results row 4. Phase 3a done (`before.tsv`,
row 5). Ken ran 3b (2026-11-26). Phase 4 done (Results row 6, tables under "After-run output").
Ken's listen (Phase 5) is in, all 10 songs of the listen list (row 7). Next: GATE L (Opus, then
Ken).

## Goal

`scripts/regen_alignment_bundles.py --lrclib-auto` checks every library song that the joint
matcher still times from a Genius sheet against LRCLIB, with the bar and the pick a
first-time download uses (`lrc_auto_pick`). It re-times the songs a record passes from that
record, on the cue route. A song that no record passes is left exactly as it is.

Why: the automatic pick landed on `dev` 2026-11-18 for new downloads only (Decision 3 of
`plans/lrclib-fit-pick.md`). On 2026-11-24 the library holds 66 Genius songs on joint, the
route that makes the most timing errors. The shift-check probe's saved tables give 30 of them
a pick.

## Decisions

Ken, 2026-11-24, by question dialog:

1. This lifts Decision 3 of `plans/lrclib-fit-pick.md` ("New downloads only. Regenerate, bulk
   runs and Repair never switch a song") for this opt-in script flag only.
2. The pick is made before the GPU run, from the words each song's bundle already stores.
   `--dry-run` lists which songs switch and to which record, with no GPU. The real run
   re-times only those songs, each from exactly the record its own report lists. A song that
   no record passes is not touched.
3. Chinese and Cantonese songs are included, although the bar was never measured on them. Of
   the 16 among the 66, 14 had no bundle when the probe ran, and the 2 that were measured got
   no pick. (The question put to Ken said 12 unmeasured; corrected to 14 when the plan was
   written.)
4. After the run Ken listens to about 10 of the switched songs (rule in Phase 4).

Stated by Opus with the questions, 2026-11-24, not contested:

5. Script only. The web UI's Regenerate, Reset and bulk runs still never switch a song.
6. The flag selects every Genius song still on joint, and `--song` narrows it. It can't be
   combined with `--reset`.
7. The bar, its limits and the pick order are `lrc_auto_pick`'s, unchanged.
8. A song on joint with a custom sheet (typed or edited, 3 today) stays on joint (Decision 4
   of `plans/lrclib-fit-pick.md`).
9. A song whose `.lrc` is a skip marker (an admin's "no LRCLIB match") or unreadable
   (hand-placed) is left alone. None of the 66 has either today.
10. When LRCLIB can't be reached, the song is left untouched and listed, and a later run
    checks it again.
11. The usual backup, of the switched songs' files only. The picked record replaces the
    song's old `.lrc`. Repair to Genius puts a song back on joint.

Opus's calls in this plan (12 and 14 as Ken ruled them at GATE D, Results row 4; 13 is still
Opus's):

12. The library is the Windows one, `D:\shared\pikaraoke-songs`: the probe's tables come
    from it, and the VM reads it. There is no run on the production Linux box. Ken syncs the
    two libraries himself, and only after the Phase 3 run prints `Done.`.
13. A song Ken sends back to joint with Repair will be offered again by a later
    `--lrclib-auto` run, because nothing records the refusal. To keep it on joint for good,
    Repair it with "no LRCLIB match", which also turns off its LRCLIB fill. Nothing is built
    for this.
14. A switched song's bundle has no `pipeline_decisions.lrclib_auto` record, the same as a
    second regen of a download-picked song. The picked record's id stays in the `.lrc` header
    (`[lrclib_id:...]`). The dry run's saved report (`dry_run.txt`, Phase 2) is the record of
    each pick's numbers; Phase 3's console report is not saved. A pick whose id changed in
    the real run is named in 4a and goes first on the listen list.

## What is already there (code read, `dev` `d2ed9a3b`)

- `LyricAlignStage` already runs the check when armed (`auto_lrc_timing=True`), and
  `run_jobs` arms it only for `job.first_download`. This plan does not arm it: arming would
  decide during the GPU run on fresh words (Decision 2 rules that out) and would re-run every
  refused song on joint for nothing.
- Repair's LRCLIB route builds `sheet_plan(song, "lrclib", fit.srt)` and sets
  `plan.lrclib_record = record` (`LibraryTools._lrc_repair_plan`). `prepare_lyrics` then
  writes the sheet (`apply_custom_choice`) and the `.lrc` (`apply_lrclib_choice`) inside the
  run, after `snapshot_lyric_files`, so a song that fails gets both put back
  (`put_back_lyric_files`). The `"lrclib_auto"` sheet kind exists in `SHEETS`, and
  `prepare_lyrics` already adds the bundle's Genius identity to a `LRC_AUTO_ORIGIN` seed.
  The switch is therefore the same plan with kind `"lrclib_auto"`. The same file, re-run
  later, is replayed by `custom_plan` like any download-picked song.
- `lrc_auto_timing.check(genius, words, clip_length)` takes the Genius identity (`title`,
  `artist`), the transcribe words "as the bundle stores them" (top-level `transcribe_words`)
  and the clip length (`library_regen.media_duration(job)`). It never raises. The probe that
  set the bar read the same stored words (`scripts/lrc_fit_pick_probe.py`), so the dry run
  checks songs the way the bar was measured.
- `plans/whisper-input-fresh-vs-regen.md` (branch `whisper_input_fresh_vs_regen`) found that
  a regen, which reads the saved AAC stem, can hear slightly different words than a fresh
  download. That doesn't touch this plan: the GPU run doesn't check again.
- The open issue "A pick does not look at what is already in `lyrics/`" (`plans/open-issues.md`,
  "LRCLIB timing picked at download") can't happen here. A song with a custom sheet, a skip
  marker or an unreadable `.lrc` is not eligible (Decisions 8, 9), and `apply_custom_choice`
  removes every other sheet kind when it writes this one.

## What the option does

Selection (pure, no network):

- `scan_folder(folder, include_all=True, songs=selected)`, then `resolve_plan(job,
  reset=False)` as today.
- A job is eligible when all of these hold:
  - `is_genius_reuse(job.plan)`. This already excludes custom sheets, captions, LRCLIB songs
    and transcribed songs.
  - Its `.lrc` state (`lrclib.read_song_lrc`) is neither `"skipped"` nor `"unreadable"`.
  - Its bundle has a non-empty `transcribe_words`.
  - `media_duration(job)` is known.
- Ineligible jobs are dropped. With `--song`, each dropped song prints one line saying why, so
  a pattern that hits the wrong song isn't silent.

The check (network, read-only, before the report, so `--dry-run` runs it too):

- One `lrc_auto_timing.check(job.plan.seed["genius"], job.bundle["transcribe_words"],
  media_duration(job))` per eligible song, with a progress line (`[i/N] <song>`), because 66
  searches take a while.
- `PICKED`: `plan = sheet_plan(song, "lrclib_auto", entry.fit.srt)`,
  `plan.lrclib_record = entry.record`, and a label naming the record and the pick's numbers.
- Any other outcome gives `Plan(kind="skip", label=...)` saying why: no record passed (with
  the record count and the refusal counts), no synced record, or the check couldn't run
  (rerun later).
- Labels take their numbers from `AutoCheck.record()`, the one place they are counted.
  Suggested forms:
  - `LRCLIB (auto) 15816725: When I Was Your Man · Bruno Mars · 3:33 (mistimed 0, unclaimed
    run 2, shift run 0, on 7 records)`
  - `stays on joint: no record passed (20 records; no_fit 12, unclaimed 8)`
  - `stays on joint: no synced LRCLIB record`
  - `stays on joint: LRCLIB check could not run (search_failed); rerun later`

Report and run:

- `print_report` lists every checked song with its label. Its scope line says it is the
  LRCLIB check of Genius songs on joint, and how many of the checked songs will be re-timed.
- `--dry-run` stops after the report. With zero picks the script prints "Nothing to
  re-time.", exits 0 and makes no backup.
- The confirm prompt counts the picked songs only. The backup covers the picked songs' files
  only (`backup_text_folders(folder, stems=<picked stems>)`).
- Then `resolve_and_run(jobs)` runs unchanged. No fetch, backfill or prompt applies to these
  plans. `run_jobs` runs the picked songs on the cue route (the stage skips its own check on
  a cue sheet) and counts the rest as skipped. `first_download` stays False.

## Phase 1: the option (Sonnet)

- [x] **1a. Code** in `scripts/regen_alignment_bundles.py`. The behaviour is script-only
  (Decision 5), so `library_regen` doesn't grow.
  - The `--lrclib-auto` flag. Its help text says what it selects, that it searches LRCLIB
    even with `--dry-run`, and that it can't be combined with `--reset` (`p.error`, exit 2).
  - Two small functions, names suggested: `lrclib_auto_refusal(job) -> str | None` (why a job
    is not eligible) and `lrclib_auto_plan(job) -> Plan` (the check and the plan). Plus the
    loop that applies them to the jobs: drops, the progress line, the lines for named songs.
  - The `main()` wiring, the `print_report` scope line (a keyword argument with a default,
    because `add_songs` calls `print_report` too), the confirm count and the backup stems.
  - The module docstring gets a paragraph for the third mode.
- [x] **1b. Docstrings that become false.** The `SongJob` docstring in
  `pikaraoke/lib/library_regen.py` says `first_download` marks "the only kind whose Genius pick
  may be timed from an LRCLIB record" and that "every regen leaves it off". The flag part is
  still true, but the regen flag now times Genius songs from a record too: say so. The first
  line of the `pikaraoke/lib/lrc_auto_timing.py` module docstring says "The LRCLIB check of a
  first-time Genius download": add the regen flag. `lyric_align.py` is unchanged; leave it
  alone.
- [x] **1c. Tests** in `tests/unit/test_regen_alignment_bundles.py`. Mock only the network.
  Build a passing record the way `tests/unit/test_lrc_auto_timing.py` does (`_sung`, `_lrc`,
  `_record`, `patch.object(lrclib, "search_query", ...)`), so the real `check` and `evaluate`
  run. If those helpers would get a third copy, move them to a shared test helper instead.
  - An eligible song with a passing record gets a plan whose `lyrics_path` is
    `lrc_auto_timing.sheet_path(song)`, with seed origin `LRC_AUTO_ORIGIN`, `custom_text` the
    fitted sheet and `lrclib_record` the record. The search used the bundle's Genius title
    and artist.
  - No record passes, no synced record, or `LrclibUnavailable`: a skip plan whose label says
    why, and nothing in `lyrics/` changes.
  - Never checked (search not called) and dropped: a caption song, a Genius bundle with a
    `.custom.txt` beside it, a skip-marker `.lrc`, an unreadable `.lrc`, a Genius bundle
    without `transcribe_words`. With `--song`, the reason is printed.
  - `main`:
    - `--lrclib-auto --reset` exits 2.
    - `--dry-run` searches but makes no backup and never calls `resolve_and_run`.
    - A real run backs up the picked songs' stems only and hands the jobs to
      `resolve_and_run`.
    - Zero picks: no backup, exit 0.
  - Through the real `prepare_lyrics` on a tmp library: a picked plan writes
    `lyrics/<stem>.lrclib-auto.srt` (the fitted sheet), replaces the old `.lrc` with the
    record (header `[lrclib_id:<id>]`), and its seed carries the bundle's Genius identity.
  - Through `run_jobs` with a fake orchestrator that raises: after the failure there is no
    auto sheet, and the old `.lrc` bytes are back.
- [x] **1d. Checks:**
  - The full suite, `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Record the pass
    count, and any failure with its output.
  - `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed files>`.
  - `python scripts/regen_alignment_bundles.py --help` shows the flag.
  - Self-review per CLAUDE.md, and read `git diff --cached` before committing.
- [x] **1e. Commit.** One feature commit, with the tests:
  `feat(regen): --lrclib-auto moves joint Genius songs to an automatic LRCLIB pick`. Plan
  edits (status, ticks, Results row 1) go in a separate plan-only commit.
- [x] **1f. STOP.** Write Results row 1 (hashes, suite count). Give Ken the review line
  (CLAUDE.md "Review due"):
  `/code-review <base>..<commit>`, with these files in scope:
  `scripts/regen_alignment_bundles.py`, `pikaraoke/lib/library_regen.py`,
  `pikaraoke/lib/lrc_auto_timing.py` and the test files touched. Its three angles:
  - Correctness: eligibility, a plan identical to what a download pick produces, and a failed
    song put back.
  - Simplicity: reuse of `sheet_plan`, `AutoCheck.record` and `resolve_and_run`, with no
    second count of the pick's numbers.
  - Robustness: LRCLIB down, an unreadable or skip `.lrc`, a song named twice, Unicode names
    in the report.

  Phase 2 is read-only and may run before the review. Phase 3 waits for the review's fixes.

## Phase 2: dry run on the VM (Sonnet)

Read-only on the library. The RDP session must be connected, because the library is at
`/home/ken/shared-drives/D:/Shared/pikaraoke-songs`. `<out>` is
`~/.pikaraoke/tmp/regen_lrclib_auto`.

- [x] 2a. Make `<out>` and `touch <out>/started`. From the worktree:
  `/home/ken/miniconda3/envs/pik/bin/python scripts/regen_alignment_bundles.py "/home/ken/shared-drives/D:/Shared/pikaraoke-songs" --lrclib-auto --dry-run > <out>/dry_run.txt 2> <out>/dry_run.log`.
  Record the exit code.
- [x] 2b. Read-only check: `find <library> -newer <out>/started` lists nothing the run wrote.
  Ken may be using the library; report anything listed, and undo nothing.
- [x] 2c. Paste these raw tables under "Dry run output" below, with no tallies and no verdicts:
  - Table D: every checked song, with its name, YouTube id and label as printed.
  - Table E: for each row of "Picks Ken has heard" below, the dry run's record id for that
    song, or its skip label.
  - Table F: picks not in "Picks Ken has heard" (song, record id, the pick's numbers). Mark
    the songs whose stored sheet has CJK characters.
  - The counts as the report prints them: checked, picked, couldn't run.
- [x] 2d. If any song's check couldn't run (LRCLIB down), rerun 2a once later the same day and
  record both runs.
- [x] 2e. **STOP.** Write Results row 2. Hand to the judge: the Sonnet session asks Ken to
  `/model` to Opus.

## GATE D (Opus, then Ken)

The judge reads Tables D-F and answers these for Ken:

1. Do the picks match the probe's expectation (Table E)? Name every difference with its
   likely cause (LRCLIB gained or lost records, a query difference). A difference the code
   can't explain stops the run until it can.
2. Name every pick on a Chinese or Cantonese song (Decision 3: included, unmeasured). Ken may
   keep it, and it then heads the listen list. Or he may keep the song on joint with
   Repair's "no LRCLIB match" (Decision 13) before Phase 3. Also say whether the
   `chinese_karaoke` probe reads that song's bundle.
3. Decisions 12-14 (Opus's calls), for Ken to accept or change.

Then Ken says go for Phase 3.

## Phase 3: the run (Ken, Windows)

- [x] 3a (session). Just before handing over the block, write `<out>/before.tsv`: the sha256
  of `alignment_debug/<stem>.json` and `karaoke/<stem>.ass` for every song in Table D. Use a
  short script in `<out>`, not committed.
- [x] 3b (Ken). The session gives this block with the branch hash. If the branch is checked
  out in a Windows worktree, `cd` into that worktree and run
  `git fetch vm; git merge --ff-only vm/regen_lrclib_auto` instead of the checkout line.

  ```powershell
  cd C:\temp\Github\pikaraoke
  git fetch vm; git checkout -B regen_lrclib_auto vm/regen_lrclib_auto
  $env:PYTHONIOENCODING = "utf-8"
  uv run python scripts/regen_alignment_bundles.py D:\shared\pikaraoke-songs --lrclib-auto
  ```

  - Run it in the console with no pipe and no `Tee-Object`: a PowerShell pipe garbles the
    Chinese song names.
  - The report lists the songs, then a count line (`Songs checked: ...; to re-time: ...;
    could not check: ...`). If its re-time count differs from Phase 2's, or "could not check"
    is not 0, answer `n` and tell the session; otherwise answer `y`.
  - When it ends, give the session the final `Done.` line, the backup path it printed near
    the start (`Backed up ... to:`), and the lines of any song marked `FAILED`.

## Phase 4: after the run (Sonnet)

Read-only on the library.

- [x] 4a. Table R, for every song Table D marked as picked:
  - the bundle's `lyrics.origin` and `pipeline_decisions.method_used`;
  - the `.lrc` header's `lrclib_id` against the dry-run pick;
  - the `.ass` line count before (from the backup) and after.

  For a song the run marked FAILED, confirm the put-back: the `.lrc` bytes equal the
  backup's, and there is no auto sheet.

  The real run searches LRCLIB again, so a pick can change after GATE D with the count
  unchanged. Any song whose `lrclib_id` differs from its dry-run pick is named in the relay
  and heads the listen list; Ken then keeps it or has its files put back from the backup.
- [x] 4b. Table U, the songs not picked: bundle and `.ass` sha256 against `before.tsv`.
- [x] 4c. The listen list, by the rule below, at most 10 rows: song, YouTube id, record id,
  and what Ken said about this record before, if anything.
- [x] 4d. **STOP.** Write the next Results row and relay the listen list to Ken.

**Listen list rule** (pre-registered). Fill in this order and stop at 10:

1. Picks not in "Picks Ken has heard" (a different record than the one he heard, or a song
   not listed), Chinese and Cantonese songs first.
2. The heard picks he flagged (the table's last column), with his earlier words as the spot
   to listen at.
3. The remaining heard picks, closest to the bar first: more mistimed lines, then a longer
   shift run, then a longer unclaimed run, then Table D order.

Ken listens to the finished karaoke in the app, the whole song. The question for each song:
is it right, and is anything gross? Gross means more than five lines in a row 2 s or more
off, or sung lead lines never shown (Decision 29 of `plans/lrclib-shift-check.md`).

## Phase 5: Ken's listen

Ken reports in chat. The session records his words verbatim as the next Results row, without
classifying them.

## GATE L (Opus, then Ken)

The judge reads Ken's listen row against Decision 29's line between gross and tolerated and,
for Ken:

- Each gross song: send it back with Repair to Genius in the web UI (Decision 13 says how to
  keep it there), and add an entry to `plans/open-issues.md` under "LRCLIB timing picked at
  download".
- Each tolerated flaw: an open-issues entry only if it is a new kind, not one of that
  section's existing entries.
- Whether the switched songs nobody has heard as finished karaoke need another session. That
  is Ken's call; Decision 4 asked for about 10.

## Landing

After GATE L, on Ken's word:

- Cherry-pick the code commits onto `dev` one by one with their messages. Plan-only commits
  stay behind; open-issues commits from GATE L land.
- Run the full suite on `dev`, and push when Ken says.
- Retire the branch as `archive/regen_lrclib_auto` per CLAUDE.md "Branches and Archive Tags".
- Update `plans/open-issues.md` "Landing order".

## Picks Ken has heard

Source: the probe tables `~/.pikaraoke/tmp/lrclib_shift_check/songs.tsv` and
`~/.pikaraoke/tmp/lrclib_shift_check_holdout/songs.tsv` (the frozen bar, 2026-11-12),
restricted to songs that are genius + joint on 2026-11-24 and have a pick.

"Heard" means the same record id appears in one of Ken's verdicts:

- Set E (`plans/lrclib-shift-check.md` on tag `archive/lrclib_fit_pick`, "Set E verdicts").
- GATE P's `new` picks (`plans/lrclib-fit-pick.md`, "Rule 2: verdicts"; the `new` rows of
  `~/.pikaraoke/tmp/lrclib_fit_pick_holdout/songs.tsv`).
- When I Was Your Man's moved pick (`plans/lrclib-shift-check.md`, Results row 6).

He heard each one as the record's sheet against the video, not as finished karaoke. Names are
the bundles' Genius identities.

| Song | YouTube id | Record | Heard at | Ken flagged (his words) |
|---|---|---|---|---|
| \*NSYNC - Here We Go | `zqVejtQ2qCk` | 19116608 | Set E | |
| \*NSYNC - I Want You Back | `n-2C2wOFavc` | 6955667 | GATE P | |
| Britney Spears - I'm a Slave 4 U | `Mzybwwf2HoQ` | 36592252 | Set E | "1:17 'I won't deny it' and the 2 'oh baby' lines are late, 2:12 2 'baby' lines are late" |
| Bruno Mars - Grenade | `SR6iYWJxHqs` | 38953751 | GATE P | "opening line comes in early and leaves early" |
| Bruno Mars - Just the Way You Are | `LjhCEhWiKXk` | 9888181 | GATE P | |
| Bruno Mars - Locked Out of Heaven | `e-fA-gBCkj0` | 6936310 | GATE P | |
| Bruno Mars - The Lazy Song | `fLexgOxsZu0` | 6706711 | GATE P | |
| Bruno Mars - When I Was Your Man | `ekzHIouo8Q4` | 15816725 | GATE F (row 6) | |
| Demi Lovato - It's On | `fO4BmrVjqjM` | 7140272 | Set E | |
| Demi Lovato - Wouldn't Change a Thing | `62llzl7iKkE` | 33991259 | GATE P | |
| Idina Menzel - Into the Unknown | `mzhv_dg_UBA` | 36372778 | GATE P | "the opening few lines of siren chant chant don't line up but the rest of the lyrics do" |
| Ingrid Michaelson - Be OK | `vpMI8Qu5fsc` | 326004 | GATE P | |
| Jason Mraz - Lucky | `acvIVA9-FMQ` | 20759539 | Set E | |
| Jessie J - Flashlight | `DzwkcbTQ7ZE` | 37730119 | GATE P | |
| Jessie J - Price Tag | `qMxX-QOV9tI` | 6900889 | GATE P | |
| Kelly Clarkson - Behind These Hazel Eyes | `yipoOY56MbM` | 33411593 | Set E | |
| Kristen Bell - For the First Time in Forever | `ZrX1XKtShSI` | 14589928 | GATE P | |
| Maia Wilson - Fixer Upper | `IyO-vdsgq1s` | 2263859 | Set E | |
| Mandy Moore - I've Got a Dream | `zi5Z6rNU9Hw` | 29290799 | GATE P | |
| Michelle Branch - All You Wanted | `Cbo2n2MzxxE` | 3617844 | Set E | |
| Michelle Branch - Are You Happy Now? | `Uxb6RFh3BCw` | 5593856 | Set E | |
| Michelle Branch - Everywhere | `HLCasyAh7ic` | 19297649 | GATE P | |
| S Club - Natural | `A4Kba6v5fdg` | 12518942 | Set E | |
| Sara Bareilles - Gravity | `rEXhAMtbaec` | 36844599 | GATE P | |
| Tenacious D - Kickapoo | `hvvjiE4AdUI` | 34637521 | Set E | |
| The Lonely Island - I Just Had Sex | `lQlIhraqL7o` | 11579404 | GATE P | |
| The Lonely Island - Jack Sparrow | `GI6CfKcMhjY` | 22000139 | GATE P | |
| The Lonely Island - YOLO | `z5Otla5157c` | 1019299 | GATE P | |
| Westlife - Flying Without Wings | `vKPGxGCFgTs` | 1512603 | GATE P | |
| Wicked Movie Cast - What Is This Feeling? (Sing-Along) | `amgPXKrFZVg` | 16623226 | Set E | |

The 36 genius + joint songs not in this table had no pick in the probe tables, had no
bundle then (14 of the 16 CJK songs), or were never in them (`#OutofOz - 'Defying Gravity'`,
checked at its download: no pick).

## Executor rules

- Stop at each STOP with the artifacts saved: paths and raw tables, no tallies, no verdicts.
  Opus judges every gate, and a Sonnet session asks Ken to `/model` to Opus.
- Read-only on the library except Phase 3, which is Ken's run.
- No lyric text in this file. Titles, ids and numbers are fine.
- Work from the worktree. The VM has no GPU, and the dry run loads no model.
- A step that can't run as written stops and reports; it isn't improvised around.

## Results log

| Row | Date | Phase | What was done | Artifacts |
|---|---|---|---|---|
| 1 | 2026-11-24 | 1 | `--lrclib-auto` built as planned, plus these differences. `confirm()` and `back_up()` lifted out of `main()` (shared by both modes; `main()` was past 50 lines). Progress `[i/N]` goes to stderr, so stdout is the report only. Pick label has no record duration (`record_meta`'s `duration` is not formatted anywhere public). `add_songs.py` has its own `print_report`; it never calls this one, so the new keyword argument is for the tests' existing calls only. Tests reuse `tests/unit/movie_slices.py` (`heard_words`, `lrc_slice`, `CLIP_S`) instead of copying `test_lrc_auto_timing.py`'s helpers. The `LRC_ORIGINS` comment in `library_regen.py` also updated. 24 new tests; seven injected bugs (no skip-marker refusal, backup of all stems, hand-over of picks only, no `--reset` refusal, dry run proceeding, wrong sheet kind, no record on the plan) each failed one of them. Full suite 4570 passed. pre-commit clean (black reformatted two files, rerun clean). `--help` shows the flag. Smoke run of `--lrclib-auto --dry-run` and `--lrclib-auto --reset` (exit 2) on a one-song tmp library. | code `2a0afe1d` (off plan commit `57c9faf8`); review range `57c9faf8..2a0afe1d` |
| 2 | 2026-11-24 | 2 | Dry run of `--lrclib-auto --dry-run` on the Windows library via the VM, as written in 2a-2d: exit 0, report and `[i/N]` log split as planned (`dry_run.txt` report only, `dry_run.log` 66 progress lines). 2b listed nothing written. 2d: no check failed to run, no rerun. Tables D-F and the printed counts are under "Dry run output". The report prints no couldn't-run count; the plan's third count is the number of labels that say so, counted from the file. `plan.seed["genius"]` holds no sheet text, so the CJK mark reads `bundle["lyrics"]["lines"]`. No code touched. Stopped at 2e: no judging, GATE D not started. | `~/.pikaraoke/tmp/regen_lrclib_auto/` (`dry_run.txt`, `dry_run.log`, `dry_run.exit`, `tables.md`, `cjk_flags.py`, `cjk_flags.tsv`, `build_tables.py`) |
| 3 | 2026-11-24 | review | `/code-review high 57c9faf8..2a0afe1d` (three angles: correctness, simplicity, robustness): 10 findings, none critical. Fixed in `d13e8484`: a check that could not run is counted on a count line printed after the list (`could not check: N`) and the mode exits 1 (#4); the count is made once (#8); only an unreachable LRCLIB says "rerun later", a failed check says "see the log" (#3); the length is looked up once per song (#5); `confirm()` moved to `scripts/song_select.py`, used by `backfill_artifacts.py` too, closed input aborts (#1, #9); refusal docstring matches Decision 9 (#6). #2 (real run re-searches) handled in the plan: Phase 3 checks the could-not-check count, 4a names any changed record id. Dropped: #7 (Phase 3 already sets UTF-8 and runs without a pipe), #10 (`lrclib_fill` is hard-wired on). Pick logic untouched, so the Phase 2 dry run's picks stand; its report's count line and failure wording predate the fix. 5 new tests; full unit suite 4574 passed; pre-commit clean. | `d13e8484` |
| 4 | 2026-11-26 | GATE D | GATE D judged by Opus. Ken's answers, verbatim: "Decision 2: keep as built (real run acts on its own search; no library regen before Phase 3)." "月亮代表我的心: keep the pick (it heads the listen list)." "Decision 12: Ken syncs the two libraries, so no Linux run; sync only after the run prints Done." "Decision 14: the dry run's saved report is the record of each pick's numbers; a pick whose id changed is named in 4a and goes first on the listen list." Decisions 12 and 14 reworded to match. Decision 13 is not among the answers recorded here and stays as written. | Decisions 12 and 14 above |
| 5 | 2026-11-26 | 3a | `before.tsv` written for the 66 songs of Table D, read from the library at `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`: columns `stem`, `bundle_sha256` (`alignment_debug/<stem>.json`), `ass_sha256` (`karaoke/<stem>.ass`). No file missing. `find <library> -newer <out>/started` listed nothing, so the library has not changed since the dry run. Script `before_hashes.py` in `<out>`, not committed. Phase 3b handed to Ken. | `~/.pikaraoke/tmp/regen_lrclib_auto/before.tsv`, `before_hashes.py` |
| 6 | 2026-11-26 | 4 | Lane: LRCLIB-record timing on the cue route, for songs that were on joint from a Genius sheet. Ken ran 3b ("results are in"); the session got no `Done.` line, backup path or `FAILED` line, so it read the library directly (4a-4c, read-only). Backup read: newest folder `regen_backups/20261126T144615Z`, 32 songs. 4a: Table R, the 32 dry-run picks. Every `.lrc` id equals its dry-run pick, so no pick changed between the dry run and the run. All 32 have the auto sheet, origin `lrclib_auto_srt`, method `cue_align` and a changed bundle; none is in a put-back state. Two `.lrc` files are byte-identical to the backup (their old id was already the pick). 4b: Table U, the 34 songs not picked: bundle and `.ass` sha256 equal `before.tsv` for every one. Writes in the four output folders since the dry run: 192 files, all belonging to the 32 picked songs, none stray; first 14:46:49Z, last 16:46:16Z (the last song written is 月亮代表我的心), nothing newer when read at 16:49Z. 4c: listen list of 10 by the pre-registered rule, no record id changed so it starts with the two songs not heard before (CJK first), then the three Ken flagged, then five by closeness to the bar. Stopped at 4d: no verdicts. No code touched. | `~/.pikaraoke/tmp/regen_lrclib_auto/after_run.py`, `after_tables.md`; tables under "After-run output" |
| 7 | 2026-11-26 | 5 | Ken's listen of the 10 songs on the listen list, finished karaoke in the app, his words verbatim, not classified: "月亮代表我的心, feels like most of the lines are even paced fills"; "Sara Bareilles - King of Anything, "oh"s throughout the song have the know repeated word struggle, otherwise good"; "Britney Spears - I'm a Slave 4 U, cue rescued 1:17, but not 2:12 (late but caught up quickly), otherwise good"; "Bruno Mars - Grenade, opening line is fine, good"; "Jessie J - Price Tag, good except for repeated "ahh"s"; "NSYNC - Here We Go, opening line is late, otherwise good"; "Idina Menzel - Into the Unknown, "ah" and "oh" repeats are off, otherwise good"; "Bruno Mars - The Lazy Song, good"; "Camp Rock 2 - It's On, good"; "I Just Had Sex, good". | Ken, in chat |

## Dry run output

Phase 2c, run 2026-11-24 on the VM from the worktree at `d0dc08a1`, library
`/home/ken/shared-drives/D:/Shared/pikaraoke-songs` (the Windows library over RDP). Artifacts in
`~/.pikaraoke/tmp/regen_lrclib_auto/`: `dry_run.txt` (the report), `dry_run.log` (the 66 `[i/N]`
progress lines, nothing else), `dry_run.exit`, `tables.md` (the tables below), `cjk_flags.py` and
`cjk_flags.tsv` (the CJK mark), `build_tables.py`.

- 2a: exit code 0. One run.
- 2b: `find <library> -newer <out>/started` listed nothing, checked right after the run and again
  after the CJK read.
- 2d: no label says the check couldn't run, so no rerun.

Counts as the report prints them (it prints no couldn't-run count; the last line is the number of
labels that say "could not run", counted from `dry_run.txt`):

```
Songs checked: 66; to re-time: 32
labels saying the check could not run: 0
```

The CJK mark in Table F is `cjk_flags.py`: it reads each song's stored sheet
(`bundle["lyrics"]["lines"]`; `plan.seed["genius"]` holds only the Genius id, title and artist)
and tests for Han, kana or Hangul characters. It flags 17 of the 66 songs; the plan text
elsewhere says 16.

**Table D: every checked song (name, YouTube id, label as printed)**

| # | Song | YouTube id | Label |
|---|---|---|---|
| 1 | #OutofOz - 'Defying Gravity' WICKED Studio Sessions _ WICKED the Musical | `EFbuID1QG0Y` | stays on joint: no record passed (19 records; no_fit 19) |
| 2 | A-Lin - 幸福在歌唱 (Happiness Is Singing) | `jeRu6h4XbUU` | stays on joint: no record passed (8 records; no_fit 8) |
| 3 | Beyond - 海闊天空 (Boundless Oceans, Vast Skies) | `qu_FSptjRic` | stays on joint: no record passed (20 records; no_fit 20) |
| 4 | Britney Spears - I'm A Slave 4 U (Official 4K Video) | `Mzybwwf2HoQ` | LRCLIB (auto) 36592252: im a slave 4 u · britney spears (mistimed 0, unclaimed run 6, shift run 2, on 6 records) |
| 5 | Bruno Mars - Grenade (Official Music Video) | `SR6iYWJxHqs` | LRCLIB (auto) 38953751: Bruno Mars - Grenade (Official Music Video) · Bruno Mars (mistimed 0, unclaimed run 2, shift run 2, on 2 records) |
| 6 | Bruno Mars - Just The Way You Are (Official Music Video) | `LjhCEhWiKXk` | LRCLIB (auto) 9888181: Just The Way You Are · Bruno Mars (mistimed 0, unclaimed run 7, shift run 0, on 2 records) |
| 7 | Bruno Mars - Locked Out Of Heaven (Official Music Video) | `e-fA-gBCkj0` | LRCLIB (auto) 6936310: Bruno Mars - Locked Out Of Heaven (Official Music Video) · Bruno Mars (mistimed 0, unclaimed run 3, shift run 1, on 2 records) |
| 8 | Bruno Mars - The Lazy Song (Official Music Video) | `fLexgOxsZu0` | LRCLIB (auto) 6706711: The Lazy Song · Bruno Mars (mistimed 0, unclaimed run 10, shift run 1, on 6 records) |
| 9 | Bruno Mars - When I Was Your Man (Official Music Video) | `ekzHIouo8Q4` | LRCLIB (auto) 15816725: bruno mars  when i was your man · bruno mars (mistimed 0, unclaimed run 7, shift run 0, on 2 records) |
| 10 | Bruno Mars, Anderson .Paak, Silk Sonic - After Last Night w_ Thundercat & Bootsy [Official Audio] | `-cy_tDQPXHk` | stays on joint: no record passed (20 records; unclaimed 20) |
| 11 | Cast of Camp Rock 2 - It's On (From 'Camp Rock 2 - The Final Jam'_Sing-Along) | `fO4BmrVjqjM` | LRCLIB (auto) 7140272: It's On · Demi Lovato (mistimed 0, unclaimed run 6, shift run 1, on 4 records) |
| 12 | Colbie Caillat - Fallin' For You | `GPCRbuL4Oh8` | stays on joint: no record passed (19 records; no_fit 2, unclaimed 17) |
| 13 | Demi Lovato, Joe Jonas - Wouldn't Change a Thing (From 'Camp Rock 2 - The Final Jam'_Sing-Along) | `62llzl7iKkE` | LRCLIB (auto) 33991259: wouldnt change a thing · demi lovato (mistimed 0, unclaimed run 7, shift run 0, on 3 records) |
| 14 | Donna Murphy - Mother Knows Best (From 'Tangled'_Sing-Along) | `-7jWt3JvJto` | stays on joint: no record passed (20 records; no_fit 3, mistimed 17) |
| 15 | Eason Chan 陳奕迅 - 明年今日 (This Day Next Year) | `8NJVNkzhJM4` | stays on joint: no record passed (19 records; no_fit 19) |
| 16 | Encanto - Cast - We Don't Talk About Bruno (From 'Encanto'_Sing-Along) | `YRpvIiz9G8A` | stays on joint: no record passed (15 records; no_fit 3, unclaimed 12) |
| 17 | I Just Had Sex (feat. Akon) | `lQlIhraqL7o` | LRCLIB (auto) 11579404: I Just Had Sex · The Lonely Island feat. Akon (mistimed 0, unclaimed run 12, shift run 1, on 5 records) |
| 18 | Idina Menzel, AURORA - Into the Unknown (From 'Frozen 2'_Sing-Along) | `mzhv_dg_UBA` | LRCLIB (auto) 36372778: Into the Unknown · Idina Menzel (mistimed 0, unclaimed run 2, shift run 1, on 10 records) |
| 19 | Idina Menzel, Evan Rachel Wood - Show Yourself (From 'Frozen 2'_ Sing-Along) | `nrZxwPwmgrw` | stays on joint: no record passed (19 records; unclaimed 19) |
| 20 | Ingrid Michaelson 'Be OK' (Official Video) | `vpMI8Qu5fsc` | LRCLIB (auto) 326004: Be OK (Acoustic) · Ingrid Michaelson (mistimed 0, unclaimed run 5, shift run 1, on 2 records) |
| 21 | Jack Sparrow (feat. Michael Bolton) | `GI6CfKcMhjY` | LRCLIB (auto) 22000139: Jack Sparrow · The Lonely Island (mistimed 0, unclaimed run 6, shift run 1, on 7 records) |
| 22 | Jason Mraz - Lucky (feat. Colbie Caillat) [Official Video] [HD Remaster] | `acvIVA9-FMQ` | LRCLIB (auto) 20759539: Lucky · Jason Mraz (mistimed 0, unclaimed run 3, shift run 0, on 8 records) |
| 23 | Jay Chou 周杰倫 - 晴天 (Sunny Day) | `DYptgVvkVLQ` | stays on joint: no record passed (19 records; no_fit 19) |
| 24 | Jessica Darrow - Surface Pressure (From 'Encanto'_Sing-Along) | `X-NH1uUfr0U` | stays on joint: no record passed (20 records; no_fit 4, unclaimed 16) |
| 25 | Jessie J - Flashlight (from Pitch Perfect 2) (Official Video) | `DzwkcbTQ7ZE` | LRCLIB (auto) 37730119: Flashlight · Jessie J (mistimed 0, unclaimed run 6, shift run 1, on 3 records) |
| 26 | Jessie J - Price Tag ft. B.o.B | `qMxX-QOV9tI` | LRCLIB (auto) 6900889: Price Tag · Jessie J (mistimed 0, unclaimed run 9, shift run 1, on 2 records) |
| 27 | Jonathan Groff - Lost in the Woods (From 'Frozen 2'_Sing-Along) | `_8jNbZIsBQU` | stays on joint: no record passed (20 records; unclaimed 20) |
| 28 | KPop Demon Hunters (2025) - Soda Pop | `983bBbJx0Mk` | stays on joint: no record passed (20 records; no_fit 20) |
| 29 | Kelly Clarkson - Behind These Hazel Eyes (Official Video) | `yipoOY56MbM` | LRCLIB (auto) 33411593: Behind These Hazel Eyes · Kelly Clarkson (mistimed 0, unclaimed run 6, shift run 1, on 11 records) |
| 30 | Kristen Bell, Idina Menzel - For the First Time in Forever (From 'Frozen'_Sing-Along) | `ZrX1XKtShSI` | LRCLIB (auto) 14589928: For The First Time In Forever · Kristen Bell (mistimed 0, unclaimed run 2, shift run 1, on 7 records) |
| 31 | Maia Wilson, Cast of Frozen - Fixer Upper (From 'Frozen'_Sing-Along) | `IyO-vdsgq1s` | LRCLIB (auto) 2263859: Fixer Upper · Maia Wilson (mistimed 0, unclaimed run 4, shift run 1, on 13 records) |
| 32 | Mandy Moore, Zachary Levi - I See the Light (From 'Tangled'_Sing-Along) | `ILRs2r6lcHY` | stays on joint: no record passed (20 records; no_fit 20) |
| 33 | Michelle Branch - All You Wanted (Official Music Video) _ Warner Records | `Cbo2n2MzxxE` | LRCLIB (auto) 3617844: All You Wanted · Michelle Branch (mistimed 0, unclaimed run 5, shift run 0, on 6 records) |
| 34 | Michelle Branch - Are You Happy Now (Official Music Video) _ Warner Vault | `Uxb6RFh3BCw` | LRCLIB (auto) 5593856: Are You Happy Now · Michelle Branch (mistimed 0, unclaimed run 4, shift run 1, on 5 records) |
| 35 | Michelle Branch - Everywhere [Official Music Video] | `HLCasyAh7ic` | LRCLIB (auto) 19297649: Everywhere · Michelle Branch (mistimed 0, unclaimed run 6, shift run 1, on 8 records) |
| 36 | NSYNC - Here We Go (Official Video) | `zqVejtQ2qCk` | LRCLIB (auto) 19116608: Here We Go · nsync (mistimed 0, unclaimed run 7, shift run 1, on 14 records) |
| 37 | NSYNC - I Want You Back (US Version - Official Video) | `n-2C2wOFavc` | LRCLIB (auto) 6955667: I Want You Back (radio edit) · *NSYNC (mistimed 0, unclaimed run 3, shift run 0, on 1 records) |
| 38 | Pocahontas 'Savages' 1080p HD | `1YiAzyCzZzw` | stays on joint: no record passed (16 records; mistimed 1, unclaimed 15) |
| 39 | Queen - Don't Stop Me Now (Official Video Remastered 4K) | `HgzGwKwLmgM` | stays on joint: no record passed (20 records; unclaimed 20) |
| 40 | RENT 2005  - Over The Moon (Film-Cut) [HD] | `pXNd2V88d60` | stays on joint: no synced LRCLIB record |
| 41 | S Club - Natural | `A4Kba6v5fdg` | LRCLIB (auto) 12518942: Natural · S Club (mistimed 0, unclaimed run 3, shift run 0, on 2 records) |
| 42 | Sara Bareilles - Gravity (Official HD Video) | `rEXhAMtbaec` | LRCLIB (auto) 36844599: Gravity · Sara Bareilles (mistimed 0, unclaimed run 4, shift run 1, on 8 records) |
| 43 | Sara Bareilles - King of Anything (Official Video) | `eR7-AUmiNcA` | LRCLIB (auto) 9035250: King of Anything · Sara Bareilles (mistimed 0, unclaimed run 6, shift run 1, on 7 records) |
| 44 | Some Things Never Change (From 'Frozen 2'_Sing-Along) | `nVW9QOIeqQg` | stays on joint: no record passed (20 records; speed 1, unclaimed 19) |
| 45 | Sun Yan-Zi 孫燕姿 - 遇見 (Encounter) | `m4nu_F_9dWU` | stays on joint: no record passed (20 records; no_fit 20) |
| 46 | TENACIOUS D - Kickapoo | `hvvjiE4AdUI` | LRCLIB (auto) 34637521: TENACIOUS D - Kickapoo · NewLine (mistimed 0, unclaimed run 5, shift run 0, on 1 records) |
| 47 | Take Me Or Leave Me - Rent (2005) (Subtitled) | `DcbEr7Cd_Cc` | stays on joint: no synced LRCLIB record |
| 48 | Tangled - Cast - I've Got a Dream (From 'Tangled'_Sing-Along) | `zi5Z6rNU9Hw` | LRCLIB (auto) 29290799: I've Got a Dream · Mandy Moore (mistimed 0, unclaimed run 4, shift run 0, on 5 records) |
| 49 | The Lonely Island - Here I Go (feat. Charli xcx) | `kHwpS0LakeU` | stays on joint: no synced LRCLIB record |
| 50 | The Lonely Island - I'm On A Boat (Explicit Version) ft. T-Pain (Official Video) | `avaSdC0QOUM` | stays on joint: no record passed (20 records; unclaimed 20) |
| 51 | Twins《下一站天后》[Official MV] | `cPKfUWDmNbo` | stays on joint: no record passed (16 records; no_fit 16) |
| 52 | Westlife - Flying Without Wings (Official Video) | `vKPGxGCFgTs` | LRCLIB (auto) 1512603: Flying Without Wings · Westlife (mistimed 0, unclaimed run 3, shift run 0, on 8 records) |
| 53 | Where You Are (From 'Moana'_Sing-Along) | `RTWhvp_OD6s` | stays on joint: no record passed (20 records; shifted 20) |
| 54 | Wicked (2024) 4K - Dancing Through Life _ Movieclips | `jniq78mKKcM` | stays on joint: no record passed (12 records; no_fit 12) |
| 55 | Wicked _ What Is This Feeling | `amgPXKrFZVg` | LRCLIB (auto) 16623226: What Is This Feeling? · Wicked Movie Cast Feat. Ariana Grande & Cynthia Erivo (mistimed 0, unclaimed run 4, shift run 1, on 1 records) |
| 56 | YOLO (feat. Adam Levine & Kendrick Lamar) | `z5Otla5157c` | LRCLIB (auto) 1019299: Yolo · The Lonely Island feat. Adam Levine & Kendrick Lamar (mistimed 0, unclaimed run 6, shift run 0, on 5 records) |
| 57 | 周杰倫 Jay Chou【千里之外 Far Away (feat.費玉清 Fei Yu-ching)】-Official Music Video | `ocDo3ySyHSI` | stays on joint: no record passed (18 records; no_fit 18) |
| 58 | 周杰倫 Jay Chou【雙截棍 Nunchucks】Official MV | `OR-0wptI_u0` | stays on joint: no record passed (17 records; no_fit 17) |
| 59 | 富士山下 | `7qeShSmmsNg` | stays on joint: no record passed (20 records; no_fit 20) |
| 60 | 愛情轉移 | `RIq7Tz9nYD8` | stays on joint: no record passed (20 records; no_fit 20) |
| 61 | 月亮代表我的心 | `IgvDMB5fR-8` | LRCLIB (auto) 31215515: 月亮代表我的心 · Teresa Teng (mistimed 1, unclaimed run 4, shift run 1, on 2 records) |
| 62 | 林子祥 George Lam  -《男兒當自強》Official MV (電影《黃飛鴻之二》主題曲) | `U_EgeFUTbW4` | stays on joint: no record passed (19 records; no_fit 19) |
| 63 | 楊千嬅 Miriam Yeung - 少女的祈禱 (Official Music Video) | `CvKvXNiXQZc` | stays on joint: no record passed (17 records; no_fit 17) |
| 64 | 王菲 - 容易受傷的女人 (粵語版) (Official Music Video) | `tDw_ULjZWA8` | stays on joint: no record passed (20 records; no_fit 20) |
| 65 | 陳奕迅 Eason Chan《十年(國) [OT  - 明年今日]》[Official MV] | `JM9rx_hN1Ko` | stays on joint: no record passed (20 records; no_fit 20) |
| 66 | 風繼續吹_ 電影《縱橫四海》主題曲 _ 張國榮 Leslie Cheung _ Official Music Video _ 曲：Uzaki Ryudo _ 詞：Aki Yoko | `UmTB6E5mU5w` | stays on joint: no record passed (16 records; no_fit 16) |

**Table E: the dry run's answer for each "Picks Ken has heard" row**

| Song | YouTube id | Probe record | Dry run |
|---|---|---|---|
| *NSYNC - Here We Go | `zqVejtQ2qCk` | 19116608 | 19116608 |
| *NSYNC - I Want You Back | `n-2C2wOFavc` | 6955667 | 6955667 |
| Britney Spears - I'm a Slave 4 U | `Mzybwwf2HoQ` | 36592252 | 36592252 |
| Bruno Mars - Grenade | `SR6iYWJxHqs` | 38953751 | 38953751 |
| Bruno Mars - Just the Way You Are | `LjhCEhWiKXk` | 9888181 | 9888181 |
| Bruno Mars - Locked Out of Heaven | `e-fA-gBCkj0` | 6936310 | 6936310 |
| Bruno Mars - The Lazy Song | `fLexgOxsZu0` | 6706711 | 6706711 |
| Bruno Mars - When I Was Your Man | `ekzHIouo8Q4` | 15816725 | 15816725 |
| Demi Lovato - It's On | `fO4BmrVjqjM` | 7140272 | 7140272 |
| Demi Lovato - Wouldn't Change a Thing | `62llzl7iKkE` | 33991259 | 33991259 |
| Idina Menzel - Into the Unknown | `mzhv_dg_UBA` | 36372778 | 36372778 |
| Ingrid Michaelson - Be OK | `vpMI8Qu5fsc` | 326004 | 326004 |
| Jason Mraz - Lucky | `acvIVA9-FMQ` | 20759539 | 20759539 |
| Jessie J - Flashlight | `DzwkcbTQ7ZE` | 37730119 | 37730119 |
| Jessie J - Price Tag | `qMxX-QOV9tI` | 6900889 | 6900889 |
| Kelly Clarkson - Behind These Hazel Eyes | `yipoOY56MbM` | 33411593 | 33411593 |
| Kristen Bell - For the First Time in Forever | `ZrX1XKtShSI` | 14589928 | 14589928 |
| Maia Wilson - Fixer Upper | `IyO-vdsgq1s` | 2263859 | 2263859 |
| Mandy Moore - I've Got a Dream | `zi5Z6rNU9Hw` | 29290799 | 29290799 |
| Michelle Branch - All You Wanted | `Cbo2n2MzxxE` | 3617844 | 3617844 |
| Michelle Branch - Are You Happy Now? | `Uxb6RFh3BCw` | 5593856 | 5593856 |
| Michelle Branch - Everywhere | `HLCasyAh7ic` | 19297649 | 19297649 |
| S Club - Natural | `A4Kba6v5fdg` | 12518942 | 12518942 |
| Sara Bareilles - Gravity | `rEXhAMtbaec` | 36844599 | 36844599 |
| Tenacious D - Kickapoo | `hvvjiE4AdUI` | 34637521 | 34637521 |
| The Lonely Island - I Just Had Sex | `lQlIhraqL7o` | 11579404 | 11579404 |
| The Lonely Island - Jack Sparrow | `GI6CfKcMhjY` | 22000139 | 22000139 |
| The Lonely Island - YOLO | `z5Otla5157c` | 1019299 | 1019299 |
| Westlife - Flying Without Wings | `vKPGxGCFgTs` | 1512603 | 1512603 |
| Wicked Movie Cast - What Is This Feeling? (Sing-Along) | `amgPXKrFZVg` | 16623226 | 16623226 |

**Table F: picks not in "Picks Ken has heard"**

| Song | YouTube id | Record | Numbers as printed | CJK sheet |
|---|---|---|---|---|
| Sara Bareilles - King of Anything (Official Video) | `eR7-AUmiNcA` | 9035250 | mistimed 0, unclaimed run 6, shift run 1, on 7 records | no |
| 月亮代表我的心 | `IgvDMB5fR-8` | 31215515 | mistimed 1, unclaimed run 4, shift run 1, on 2 records | yes |

## After-run output

Phase 4, read 2026-11-26 from the VM, read-only, library `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`.
Backup read: `regen_backups/20261126T144615Z` (the newest folder; 32 songs' files in `alignment_debug`,
`karaoke`, `lyrics`, `subtitles`). The session was not given the run's `Done.` line, the backup path
or any `FAILED` line; the backup was found as the newest folder, and every picked song's disk state
is in Table R. Artifacts in `~/.pikaraoke/tmp/regen_lrclib_auto/`: `after_run.py`, `after_tables.md`.

- The two songs whose `.lrc` has the same bytes as the backup's (Price Tag, What Is This Feeling)
  carried the record already: the backup's `[lrclib_id:...]` is 6900889 and 16623226, the same as
  their dry-run picks.
- `.ass` columns count `Dialogue:` lines in the file, before from the backup.
- 4a put-back: no picked song shows a failed state on disk. All 32 have the auto sheet, origin
  `lrclib_auto_srt`, method `cue_align`, and a bundle that differs from `before.tsv`.

**Table R: every song the dry run picked**

| # | Song | YouTube id | Dry-run pick | `.lrc` id now | origin | method | `.lrc` changed vs backup | auto sheet | `.ass` Dialogue before | after | bundle changed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | Britney Spears - I'm A Slave 4 U (Official 4K Video) | `Mzybwwf2HoQ` | 36592252 | 36592252 | lrclib_auto_srt | cue_align | yes | yes | 52 | 55 | yes |
| 5 | Bruno Mars - Grenade (Official Music Video) | `SR6iYWJxHqs` | 38953751 | 38953751 | lrclib_auto_srt | cue_align | yes | yes | 48 | 49 | yes |
| 6 | Bruno Mars - Just The Way You Are (Official Music Video) | `LjhCEhWiKXk` | 9888181 | 9888181 | lrclib_auto_srt | cue_align | yes | yes | 48 | 54 | yes |
| 7 | Bruno Mars - Locked Out Of Heaven (Official Music Video) | `e-fA-gBCkj0` | 6936310 | 6936310 | lrclib_auto_srt | cue_align | yes | yes | 49 | 51 | yes |
| 8 | Bruno Mars - The Lazy Song (Official Music Video) | `fLexgOxsZu0` | 6706711 | 6706711 | lrclib_auto_srt | cue_align | yes | yes | 48 | 48 | yes |
| 9 | Bruno Mars - When I Was Your Man (Official Music Video) | `ekzHIouo8Q4` | 15816725 | 15816725 | lrclib_auto_srt | cue_align | yes | yes | 44 | 46 | yes |
| 11 | Cast of Camp Rock 2 - It's On (From 'Camp Rock 2 - The Final Jam'_Sing-Along) | `fO4BmrVjqjM` | 7140272 | 7140272 | lrclib_auto_srt | cue_align | yes | yes | 78 | 75 | yes |
| 13 | Demi Lovato, Joe Jonas - Wouldn't Change a Thing (From 'Camp Rock 2 - The Final Jam'_Sing-Along) | `62llzl7iKkE` | 33991259 | 33991259 | lrclib_auto_srt | cue_align | yes | yes | 43 | 49 | yes |
| 17 | I Just Had Sex (feat. Akon) | `lQlIhraqL7o` | 11579404 | 11579404 | lrclib_auto_srt | cue_align | yes | yes | 58 | 60 | yes |
| 18 | Idina Menzel, AURORA - Into the Unknown (From 'Frozen 2'_Sing-Along) | `mzhv_dg_UBA` | 36372778 | 36372778 | lrclib_auto_srt | cue_align | yes | yes | 35 | 54 | yes |
| 20 | Ingrid Michaelson 'Be OK' (Official Video) | `vpMI8Qu5fsc` | 326004 | 326004 | lrclib_auto_srt | cue_align | yes | yes | 32 | 34 | yes |
| 21 | Jack Sparrow (feat. Michael Bolton) | `GI6CfKcMhjY` | 22000139 | 22000139 | lrclib_auto_srt | cue_align | yes | yes | 64 | 84 | yes |
| 22 | Jason Mraz - Lucky (feat. Colbie Caillat) [Official Video] [HD Remaster] | `acvIVA9-FMQ` | 20759539 | 20759539 | lrclib_auto_srt | cue_align | yes | yes | 37 | 39 | yes |
| 25 | Jessie J - Flashlight (from Pitch Perfect 2) (Official Video) | `DzwkcbTQ7ZE` | 37730119 | 37730119 | lrclib_auto_srt | cue_align | yes | yes | 48 | 56 | yes |
| 26 | Jessie J - Price Tag ft. B.o.B | `qMxX-QOV9tI` | 6900889 | 6900889 | lrclib_auto_srt | cue_align | no (same bytes) | yes | 75 | 75 | yes |
| 29 | Kelly Clarkson - Behind These Hazel Eyes (Official Video) | `yipoOY56MbM` | 33411593 | 33411593 | lrclib_auto_srt | cue_align | yes | yes | 52 | 54 | yes |
| 30 | Kristen Bell, Idina Menzel - For the First Time in Forever (From 'Frozen'_Sing-Along) | `ZrX1XKtShSI` | 14589928 | 14589928 | lrclib_auto_srt | cue_align | yes | yes | 52 | 59 | yes |
| 31 | Maia Wilson, Cast of Frozen - Fixer Upper (From 'Frozen'_Sing-Along) | `IyO-vdsgq1s` | 2263859 | 2263859 | lrclib_auto_srt | cue_align | yes | yes | 58 | 49 | yes |
| 33 | Michelle Branch - All You Wanted (Official Music Video) _ Warner Records | `Cbo2n2MzxxE` | 3617844 | 3617844 | lrclib_auto_srt | cue_align | yes | yes | 36 | 36 | yes |
| 34 | Michelle Branch - Are You Happy Now (Official Music Video) _ Warner Vault | `Uxb6RFh3BCw` | 5593856 | 5593856 | lrclib_auto_srt | cue_align | yes | yes | 42 | 47 | yes |
| 35 | Michelle Branch - Everywhere [Official Music Video] | `HLCasyAh7ic` | 19297649 | 19297649 | lrclib_auto_srt | cue_align | yes | yes | 45 | 45 | yes |
| 36 | NSYNC - Here We Go (Official Video) | `zqVejtQ2qCk` | 19116608 | 19116608 | lrclib_auto_srt | cue_align | yes | yes | 104 | 59 | yes |
| 37 | NSYNC - I Want You Back (US Version - Official Video) | `n-2C2wOFavc` | 6955667 | 6955667 | lrclib_auto_srt | cue_align | yes | yes | 44 | 43 | yes |
| 41 | S Club - Natural | `A4Kba6v5fdg` | 12518942 | 12518942 | lrclib_auto_srt | cue_align | yes | yes | 36 | 39 | yes |
| 42 | Sara Bareilles - Gravity (Official HD Video) | `rEXhAMtbaec` | 36844599 | 36844599 | lrclib_auto_srt | cue_align | yes | yes | 32 | 34 | yes |
| 43 | Sara Bareilles - King of Anything (Official Video) | `eR7-AUmiNcA` | 9035250 | 9035250 | lrclib_auto_srt | cue_align | yes | yes | 50 | 59 | yes |
| 46 | TENACIOUS D - Kickapoo | `hvvjiE4AdUI` | 34637521 | 34637521 | lrclib_auto_srt | cue_align | yes | yes | 41 | 54 | yes |
| 48 | Tangled - Cast - I've Got a Dream (From 'Tangled'_Sing-Along) | `zi5Z6rNU9Hw` | 29290799 | 29290799 | lrclib_auto_srt | cue_align | yes | yes | 66 | 65 | yes |
| 52 | Westlife - Flying Without Wings (Official Video) | `vKPGxGCFgTs` | 1512603 | 1512603 | lrclib_auto_srt | cue_align | yes | yes | 36 | 36 | yes |
| 55 | Wicked _ What Is This Feeling | `amgPXKrFZVg` | 16623226 | 16623226 | lrclib_auto_srt | cue_align | no (same bytes) | yes | 19 | 66 | yes |
| 56 | YOLO (feat. Adam Levine & Kendrick Lamar) | `z5Otla5157c` | 1019299 | 1019299 | lrclib_auto_srt | cue_align | yes | yes | 59 | 95 | yes |
| 61 | 月亮代表我的心 | `IgvDMB5fR-8` | 31215515 | 31215515 | lrclib_auto_srt | cue_align | yes | yes | 21 | 18 | yes |

**Table U: every song the dry run did not pick, against `before.tsv`**

| # | Song | YouTube id | bundle sha256 | `.ass` sha256 |
|---|---|---|---|---|
| 1 | #OutofOz - 'Defying Gravity' WICKED Studio Sessions _ WICKED the Musical | `EFbuID1QG0Y` | same | same |
| 2 | A-Lin - 幸福在歌唱 (Happiness Is Singing) | `jeRu6h4XbUU` | same | same |
| 3 | Beyond - 海闊天空 (Boundless Oceans, Vast Skies) | `qu_FSptjRic` | same | same |
| 10 | Bruno Mars, Anderson .Paak, Silk Sonic - After Last Night w_ Thundercat & Bootsy [Official Audio] | `-cy_tDQPXHk` | same | same |
| 12 | Colbie Caillat - Fallin' For You | `GPCRbuL4Oh8` | same | same |
| 14 | Donna Murphy - Mother Knows Best (From 'Tangled'_Sing-Along) | `-7jWt3JvJto` | same | same |
| 15 | Eason Chan 陳奕迅 - 明年今日 (This Day Next Year) | `8NJVNkzhJM4` | same | same |
| 16 | Encanto - Cast - We Don't Talk About Bruno (From 'Encanto'_Sing-Along) | `YRpvIiz9G8A` | same | same |
| 19 | Idina Menzel, Evan Rachel Wood - Show Yourself (From 'Frozen 2'_ Sing-Along) | `nrZxwPwmgrw` | same | same |
| 23 | Jay Chou 周杰倫 - 晴天 (Sunny Day) | `DYptgVvkVLQ` | same | same |
| 24 | Jessica Darrow - Surface Pressure (From 'Encanto'_Sing-Along) | `X-NH1uUfr0U` | same | same |
| 27 | Jonathan Groff - Lost in the Woods (From 'Frozen 2'_Sing-Along) | `_8jNbZIsBQU` | same | same |
| 28 | KPop Demon Hunters (2025) - Soda Pop | `983bBbJx0Mk` | same | same |
| 32 | Mandy Moore, Zachary Levi - I See the Light (From 'Tangled'_Sing-Along) | `ILRs2r6lcHY` | same | same |
| 38 | Pocahontas 'Savages' 1080p HD | `1YiAzyCzZzw` | same | same |
| 39 | Queen - Don't Stop Me Now (Official Video Remastered 4K) | `HgzGwKwLmgM` | same | same |
| 40 | RENT 2005  - Over The Moon (Film-Cut) [HD] | `pXNd2V88d60` | same | same |
| 44 | Some Things Never Change (From 'Frozen 2'_Sing-Along) | `nVW9QOIeqQg` | same | same |
| 45 | Sun Yan-Zi 孫燕姿 - 遇見 (Encounter) | `m4nu_F_9dWU` | same | same |
| 47 | Take Me Or Leave Me - Rent (2005) (Subtitled) | `DcbEr7Cd_Cc` | same | same |
| 49 | The Lonely Island - Here I Go (feat. Charli xcx) | `kHwpS0LakeU` | same | same |
| 50 | The Lonely Island - I'm On A Boat (Explicit Version) ft. T-Pain (Official Video) | `avaSdC0QOUM` | same | same |
| 51 | Twins《下一站天后》[Official MV] | `cPKfUWDmNbo` | same | same |
| 53 | Where You Are (From 'Moana'_Sing-Along) | `RTWhvp_OD6s` | same | same |
| 54 | Wicked (2024) 4K - Dancing Through Life _ Movieclips | `jniq78mKKcM` | same | same |
| 57 | 周杰倫 Jay Chou【千里之外 Far Away (feat.費玉清 Fei Yu-ching)】-Official Music Video | `ocDo3ySyHSI` | same | same |
| 58 | 周杰倫 Jay Chou【雙截棍 Nunchucks】Official MV | `OR-0wptI_u0` | same | same |
| 59 | 富士山下 | `7qeShSmmsNg` | same | same |
| 60 | 愛情轉移 | `RIq7Tz9nYD8` | same | same |
| 62 | 林子祥 George Lam  -《男兒當自強》Official MV (電影《黃飛鴻之二》主題曲) | `U_EgeFUTbW4` | same | same |
| 63 | 楊千嬅 Miriam Yeung - 少女的祈禱 (Official Music Video) | `CvKvXNiXQZc` | same | same |
| 64 | 王菲 - 容易受傷的女人 (粵語版) (Official Music Video) | `tDw_ULjZWA8` | same | same |
| 65 | 陳奕迅 Eason Chan《十年(國) [OT  - 明年今日]》[Official MV] | `JM9rx_hN1Ko` | same | same |
| 66 | 風繼續吹_ 電影《縱橫四海》主題曲 _ 張國榮 Leslie Cheung _ Official Music Video _ 曲：Uzaki Ryudo _ 詞：Aki Yoko | `UmTB6E5mU5w` | same | same |

Files in alignment_debug, karaoke, lyrics, subtitles newer than the dry run: 192; first 2026-11-26 14:46:49Z, last 2026-11-26 16:46:16Z. Not belonging to a picked song: 0.


**Listen list (rule of Phase 4)**

| # | Song | YouTube id | Record | Why | What Ken said before |
|---|---|---|---|---|---|
| 1 | 月亮代表我的心 | `IgvDMB5fR-8` | 31215515 | not heard before (CJK) |  |
| 2 | Sara Bareilles - King of Anything (Official Video) | `eR7-AUmiNcA` | 9035250 | not heard before |  |
| 3 | Britney Spears - I'm A Slave 4 U (Official 4K Video) | `Mzybwwf2HoQ` | 36592252 | heard, Ken flagged it | Ken's words: see "Picks Ken has heard" |
| 4 | Bruno Mars - Grenade (Official Music Video) | `SR6iYWJxHqs` | 38953751 | heard, Ken flagged it | Ken's words: see "Picks Ken has heard" |
| 5 | Idina Menzel, AURORA - Into the Unknown (From 'Frozen 2'_Sing-Along) | `mzhv_dg_UBA` | 36372778 | heard, Ken flagged it | Ken's words: see "Picks Ken has heard" |
| 6 | I Just Had Sex (feat. Akon) | `lQlIhraqL7o` | 11579404 | heard, closest to the bar |  |
| 7 | Bruno Mars - The Lazy Song (Official Music Video) | `fLexgOxsZu0` | 6706711 | heard, closest to the bar |  |
| 8 | Jessie J - Price Tag ft. B.o.B | `qMxX-QOV9tI` | 6900889 | heard, closest to the bar |  |
| 9 | NSYNC - Here We Go (Official Video) | `zqVejtQ2qCk` | 19116608 | heard, closest to the bar |  |
| 10 | Cast of Camp Rock 2 - It's On (From 'Camp Rock 2 - The Final Jam'_Sing-Along) | `fO4BmrVjqjM` | 7140272 | heard, closest to the bar |  |

Tie-break columns for the 'closest to the bar' rows (mistimed, shift run, unclaimed run, Table D #):

- lQlIhraqL7o: 0, 1, 12, #17
- fLexgOxsZu0: 0, 1, 10, #8
- qMxX-QOV9tI: 0, 1, 9, #26
- zqVejtQ2qCk: 0, 1, 7, #36
- fO4BmrVjqjM: 0, 1, 6, #11
- GI6CfKcMhjY: 0, 1, 6, #21
- DzwkcbTQ7ZE: 0, 1, 6, #25
- yipoOY56MbM: 0, 1, 6, #29
