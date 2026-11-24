# Regen: move joint Genius songs to an automatic LRCLIB pick

Model: Claude Sonnet 5.5 (executor). Plan and gates: Claude Opus 5.5.

Branch `regen_lrclib_auto`, worktree `.claude/worktrees/regen_lrclib_auto`, off `dev` `d2ed9a3b`.

**Status 2026-11-24:** PLANNED, no code. Next: Phase 1.

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

Opus's calls in this plan, not ruled by Ken (GATE D puts them to him):

12. The library is the Windows one, `D:\shared\pikaraoke-songs`: the probe's tables come
    from it, and the VM reads it. The production Linux box's library is out of scope; the
    same command can run there later under conda.
13. A song Ken sends back to joint with Repair will be offered again by a later
    `--lrclib-auto` run, because nothing records the refusal. To keep it on joint for good,
    Repair it with "no LRCLIB match", which also turns off its LRCLIB fill. Nothing is built
    for this.
14. A switched song's bundle has no `pipeline_decisions.lrclib_auto` record, the same as a
    second regen of a download-picked song. The picked record's id stays in the `.lrc` header
    (`[lrclib_id:...]`), and the pick's numbers stay in the run's report (saved in Phases 2
    and 3).

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

- [ ] **1a. Code** in `scripts/regen_alignment_bundles.py`. The behaviour is script-only
  (Decision 5), so `library_regen` doesn't grow.
  - The `--lrclib-auto` flag. Its help text says what it selects, that it searches LRCLIB
    even with `--dry-run`, and that it can't be combined with `--reset` (`p.error`, exit 2).
  - Two small functions, names suggested: `lrclib_auto_refusal(job) -> str | None` (why a job
    is not eligible) and `lrclib_auto_plan(job) -> Plan` (the check and the plan). Plus the
    loop that applies them to the jobs: drops, the progress line, the lines for named songs.
  - The `main()` wiring, the `print_report` scope line (a keyword argument with a default,
    because `add_songs` calls `print_report` too), the confirm count and the backup stems.
  - The module docstring gets a paragraph for the third mode.
- [ ] **1b. Docstrings that become false.** The `SongJob` docstring in
  `pikaraoke/lib/library_regen.py` says `first_download` marks "the only kind whose Genius pick
  may be timed from an LRCLIB record" and that "every regen leaves it off". The flag part is
  still true, but the regen flag now times Genius songs from a record too: say so. The first
  line of the `pikaraoke/lib/lrc_auto_timing.py` module docstring says "The LRCLIB check of a
  first-time Genius download": add the regen flag. `lyric_align.py` is unchanged; leave it
  alone.
- [ ] **1c. Tests** in `tests/unit/test_regen_alignment_bundles.py`. Mock only the network.
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
- [ ] **1d. Checks:**
  - The full suite, `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Record the pass
    count, and any failure with its output.
  - `pre-commit run --config code_quality/.pre-commit-config.yaml --files <changed files>`.
  - `python scripts/regen_alignment_bundles.py --help` shows the flag.
  - Self-review per CLAUDE.md, and read `git diff --cached` before committing.
- [ ] **1e. Commit.** One feature commit, with the tests:
  `feat(regen): --lrclib-auto moves joint Genius songs to an automatic LRCLIB pick`. Plan
  edits (status, ticks, Results row 1) go in a separate plan-only commit.
- [ ] **1f. STOP.** Write Results row 1 (hashes, suite count). Give Ken the review line
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

- [ ] 2a. Make `<out>` and `touch <out>/started`. From the worktree:
  `/home/ken/miniconda3/envs/pik/bin/python scripts/regen_alignment_bundles.py "/home/ken/shared-drives/D:/Shared/pikaraoke-songs" --lrclib-auto --dry-run > <out>/dry_run.txt 2> <out>/dry_run.log`.
  Record the exit code.
- [ ] 2b. Read-only check: `find <library> -newer <out>/started` lists nothing the run wrote.
  Ken may be using the library; report anything listed, and undo nothing.
- [ ] 2c. Paste these raw tables under "Dry run output" below, with no tallies and no verdicts:
  - Table D: every checked song, with its name, YouTube id and label as printed.
  - Table E: for each row of "Picks Ken has heard" below, the dry run's record id for that
    song, or its skip label.
  - Table F: picks not in "Picks Ken has heard" (song, record id, the pick's numbers). Mark
    the songs whose stored sheet has CJK characters.
  - The counts as the report prints them: checked, picked, couldn't run.
- [ ] 2d. If any song's check couldn't run (LRCLIB down), rerun 2a once later the same day and
  record both runs.
- [ ] 2e. **STOP.** Write Results row 2. Hand to the judge: the Sonnet session asks Ken to
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

- [ ] 3a (session). Just before handing over the block, write `<out>/before.tsv`: the sha256
  of `alignment_debug/<stem>.json` and `karaoke/<stem>.ass` for every song in Table D. Use a
  short script in `<out>`, not committed.
- [ ] 3b (Ken). The session gives this block with the branch hash. If the branch is checked
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
  - The report lists the songs. Compare its re-time count with Phase 2's: if it differs,
    answer `n` and tell the session; otherwise answer `y`.
  - When it ends, give the session the final `Done.` line, the backup path it printed near
    the start (`Backed up ... to:`), and the lines of any song marked `FAILED`.

## Phase 4: after the run (Sonnet)

Read-only on the library.

- [ ] 4a. Table R, for every song Table D marked as picked:
  - the bundle's `lyrics.origin` and `pipeline_decisions.method_used`;
  - the `.lrc` header's `lrclib_id` against the dry-run pick;
  - the `.ass` line count before (from the backup) and after.

  For a song the run marked FAILED, confirm the put-back: the `.lrc` bytes equal the
  backup's, and there is no auto sheet.
- [ ] 4b. Table U, the songs not picked: bundle and `.ass` sha256 against `before.tsv`.
- [ ] 4c. The listen list, by the rule below, at most 10 rows: song, YouTube id, record id,
  and what Ken said about this record before, if anything.
- [ ] 4d. **STOP.** Write Results row 3 and relay the listen list to Ken.

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

Ken reports in chat. The session records his words verbatim as Results row 4, without
classifying them.

## GATE L (Opus, then Ken)

The judge reads row 4 against Decision 29's line between gross and tolerated and, for Ken:

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

## Dry run output

(Phase 2c.)
