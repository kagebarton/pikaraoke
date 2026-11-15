Model: Claude Fable 5.2 (author; ran Phases 0 and 1, 2026-11-10). Judge at GATE S: Ken's
ear; Claude Opus 5.5 reads his labels off. Phases 2-4: spec by Claude Opus 5.5
(2026-11-14), read by Claude Fable 5.2, built by Claude Sonnet 5.5.

# Onset snap: a loud start is not always this line's voice

**Status: GATE S passed 2026-11-10 (Results row 5). Phases 2-4 specced 2026-11-14. O1
ruled the same day: (a), transcribe-timed lines are left out of the new exit (Results row
7). Fable's read of "Uncertain" done and ruled by Ken 2026-11-15 ("Read and ruling",
Results row 8): four changes, all written into 2a-2c below. Next: Sonnet builds the
reference dump, 2a, 2b, 2b2 and 2c, then stops. No production code has changed. The ten
`.onsetfix.ass` files are still in the library (2b moves them out once its check
passes).**

## Goal

Fewer lines whose fill starts before the singer does. Today about one line in six on the
caption-timed songs starts more than 0.3 s before the transcriber heard its first word.

## Why starts stay early while ends got fixed

- The end snap asks whether a voice still sounds past the claimed end. Any voice counts,
  so it extends.
- The onset snap asks whether the sound at the claimed start is this line's first word. It
  takes a loud start as yes (`snap_line_onsets`, the "on time" exit) and leaves the line.
- On back-to-back lines the aligner puts the next line's first word where the previous
  line's last word ends, on the still-sounding held note. Loud, so skipped.
- The end snap then extends that held note to `NEXT_LINE_GAP_S` before the early start.
  Over the library's bundles 2383 of 4092 end extensions are `to_bound`.

The skip exists for a real case and must keep covering it: an on-time first word followed
by a pause, which a search would move to the second word
(`test_on_time_word_before_pause_untouched`).

## Decisions

Ken, 2026-11-10:

1. **Own branch, run alongside `lrclib_fit_pick` and `defer_timing`.** Files this branch
   will touch: `pikaraoke/lib/onset_snap.py`, the one `snap_line_edges` call in
   `pikaraoke/pipeline/stages/lyric_align.py`, `SCHEMA_VERSION` in
   `pikaraoke/lib/alignment_capture.py`, their tests. `lrclib_fit_pick` touches
   `lrc_auto_pick.py` and `srt_slice_fit.py`; `defer_timing` adds a path in
   `lyric_align.py` that skips the snap and rules "no `SCHEMA_VERSION` bump" for itself.
   Both routes they add are cue-align songs, which this change covers.
2. **First rule to try: a skipped line moves only where the transcriber agrees.** The
   line is searched for a rise as a doubted line is today; the move is kept only when a
   heard word equal to the line's first word starts within 0.25 s of the new start. The
   transcriber's words are already computed on both lyric routes
   (`capture_transcribe_words` in `LyricAlignStage.run`).
3. **Ken's ear judges it**, on a sheet of about 20 moved lines, before and after.

## What the transcriber reference can and cannot do

It sizes; it does not judge. By it, 601 of the 1710 snaps that ship today are "further"
(Table C), the same share as searching every skipped line (356 of 1032, Table B). The
transcriber's own first word after a gap is early, which is the fault the snap repairs.

- `plans/open-issues.md` "Onset snap" quoted 13 of 47 further on ten songs as the cost of a
  bypass. That is this reference's floor, not a cost.
- The agreement rule is selected on the same reference, so its "closer" count in Table B
  is true by construction. Only the moved count and the early lines it reaches are
  measurements.

## Ruled out or already closed

- **A quiet stretch before the rise as the test** (the old note must release for 0.1, 0.2
  or 0.3 s first). It shrinks the moved set and leaves the further share where it was
  (Results row 2). It cannot tell a held note ending from an on-time word and a pause.
- **Pitch or voicing to tell whose voice rose**: Phase 7a on `archive/edge_snap_refine`,
  closed by Ken 2026-09-21.
- **LRCLIB times as an onset reference**: they carry a variable display lead.
- **Envelope refinement inside a line**: ruled dead on mechanism, 2026-09-17.

## Out of reach of this rule

Of the 954 early lines the snap skipped (Results row 1): 381 have no rise to move to, and
53 have their heard first word after word 2's claimed start. The 103 early lines on the
"no rise" exit are a separate matter (7b, the step floor, on `archive/edge_snap_refine`).

## Open questions (Ken)

Ken, 2026-11-10: "defaults" to all six. They are decisions now.

1. **How he listens.** Default: for each sheet song a second subtitle file
   `karaoke/<stem>.onsetfix.ass` beside the shipped one, as the `.edgesnap.ass` and
   `.p6ends.ass` renders were, and an HTML sheet listing song, time and both starts.
2. **What passes GATE S.** Default: each line labelled better / same / worse; pass at no
   more than 2 worse of 20 and at least 12 better. A worse line that starts late counts
   double, since Ken ruled a late start the worse of the two wrong answers (2026-09-17).
3. **Which lines go on the sheet.** Default: chosen by the script, not by hand: the ten
   songs with the most moved lines, two lines each, the largest move and the median one.
4. **The 381 early lines with no rise.** Default: out of this branch.
5. **The joint route** (12 songs, not replayable from a bundle without the old harness).
   Default: the rule is built for every route, measured on the cue route only.
6. **After landing**: a `SCHEMA_VERSION` bump to 12 and a regen of the library on the
   Windows box, as Phase 6 of the edge snap did. Default: yes.

## Phase 0: the probe (done)

`scripts/onset_loud_start_probe.py`, tests in `tests/unit/test_onset_loud_start_probe.py`.
CPU only. It replays each cue-route bundle (`repace_bad_lines` over `cue_inputs`, then the
edge snap), leaves out any song whose replay does not equal the bundle's recorded output,
and prints Tables A-C. It writes nothing to the library.

    python scripts/onset_loud_start_probe.py --folder <library> [--out DIR] > DIR/report.md

- Needs the library's `alignment_debug/`, `vocal/` and `dereverb/`, and ffmpeg. The first
  run decodes each stem (a few minutes); later runs read `<out>/env/` and take under a
  minute.
- `<out>/rows.json` holds one row per line (before, after, exit, heard word, rise) and
  lyric text. Never commit `--out`.
- The library on the VM is `/home/ken/shared-drives/D:/Shared/pikaraoke-songs`; on the
  Windows box `D:\Shared\pikaraoke-songs` (`uv run python ...` there).

## Phase 1: the listening sheet (built)

`onset_loud_start_probe.py --listen`, same script and tests.

- **The rule** as production would run it: a line the snap skipped as on time, with a rise,
  moves when any heard word equal to its first word starts within 0.25 s of the rise (no
  cue anchor). Row field `agreed`; Table B's fourth row.
- **The after-file** is the real snap's output with each agreed line marked doubted
  (`with_rule`), so the line before a moved line extends into the freed room as it will in
  production. Written with `generate_ass` and the default `PipelineConfig`.
- **Eligible songs**: those whose replayed lines regenerate the shipped
  `karaoke/<stem>.ass` byte for byte, so the two files differ only by the rule.
- **Sheet lines**: the ten eligible songs with the most agreed lines (ties by name), two
  each: the largest move and the median one.
- **Writes**: `karaoke/<stem>.onsetfix.ass` for the ten sheet songs (the only library
  writes), and `<out>/listening-sheet.html` with a play command for each file per line.

## GATE S

Ken plays each sheet line with the shipped file, then the fixed one, and labels it better,
same or worse, noting when a worse line starts late.

- Pass: at least 12 better, and no more than 2 worse counting a late worse line twice.
- Nothing is built for production before it.
- After the gate, delete the ten `.onsetfix.ass` files from the library's `karaoke/`.

**Ruling, 2026-11-10: pass.** Ken's labels (Results row 5), read off by Opus 5.5: 19
better, 0 same, 1 worse. The worse line (#12) starts late and counts twice, so the worse
score is 2, at the limit. One line shows no pattern; the rule stands as built.

## Phases 2-4

Spec by Opus 5.5, 2026-11-14, for Sonnet 5.5; amended 2026-11-15 from Fable's read, as
Ken ruled it ("Read and ruling"). Order: the reference dump, 2a, 2b (the check passes at
593, then the after-files move out), 2b2 (the guard; the check then reads 589), 2c, stop.
Phase 3 is Ken's; Phase 4 follows it.

2b must run before any regen touches `~/pikaraoke-songs`: its pass needs the 147
cue-align bundles of 11-10 as they are (all unchanged on 2026-11-15).

### The rule, as GATE S passed it

The probe's `rise_start`, `heard_near` and `with_rule`, moved into the snap unchanged:

- A line the onset snap skips as on time (not doubted, loud at its claimed start and over
  word 1's span) is searched the way a doubted line is: the same `_detect_rise` over
  `[word1.start, bound]`, the same `SNAP_MARGIN_S`, the same clamp to
  `bound - MIN_WORD_DUR_S`, the same `MIN_SHIFT_S` floor.
- It moves only when a heard word whose `_normalize_token` equals the first word's starts
  within 0.25 s of the new start, either side, inclusive. No cue anchor, no other
  condition.
- It moves the way a doubted line does: same new start, same word-1 end rule, a copy of
  the line. The end snap then runs as today, so the line before may extend into the room
  that frees (the 955 changed Dialogue lines of Results row 4).
- Nothing else changes. Doubted lines, lines that fail the on-time test, and every
  existing counter come out as at schema 11 on the same input. Given no heard words, the
  pass is today's.

2a and 2b build this rule exactly, so the check can tie it to the 11-10 record. 2b2 then
adds the one condition ruled on 2026-11-15 (a first word also heard earlier).

### Before 2a: the reference dump

Scratch, not committed; run at the commit before 2a, with `onset_snap.py` untouched. It
closes the one place 2b would compare the new code with itself: `with_rule` calls the real
snap, which 2a refactors, so a moved line's word-1 end and the line before it would
otherwise be checked only by the ten after-files, at centisecond resolution.

- Copy the cache as in 2b. For every cue-route bundle with an envelope in the copy
  (`np.load` only, never a decode): `replay_song`, and for each song it returns,
  `with_rule(before, song_rows(bundle, env, before, after), env)`.
- Write, by song stem in sorted order, each line's `line_id`, `start`, `end` and each
  word's `start` and `end` to
  `~/.pikaraoke/tmp/onset_loud_start_check/reference_before.json` (`json.dumps`). Expect
  133 songs.
- After 2b's commit, run the same script to `reference_after.json`. `cmp` must find the
  two equal. Log both runs in one Results row. On a difference, stop and report.

### 2a. The on-time exit searches and keeps a move the transcriber hears

Files: `pikaraoke/lib/onset_snap.py`, `tests/unit/test_onset_snap.py`. Commit
`feat(onset_snap): a loud start moves when the transcriber hears the first word at the rise`.

- `HEARD_AGREE_S = 0.25` beside the other constants, its comment naming GATE S.
- `snap_line_onsets` and `snap_line_edges` take `heard_words: list[dict] | None = None`:
  the transcriber's words (`word`, `start`, ...) in song time. `snap_line_edges` passes it
  through as it does `doubted_sources`. None or empty means no on-time line is searched.
- Both also take `heard_timed_sources: frozenset[str] = frozenset()`, the line sources
  whose word times were taken from `heard_words` (O1). A line with such a source never
  takes the new exit, because its first word would agree with itself. It still goes
  through the on-time test and the existing search exactly as today. `snap_line_edges`
  passes it through beside `heard_words`.
- Normalise the heard words once per call into `(start, token)` pairs, not once per line.
  `_heard_near(pairs, first_word, t)` is the probe's `heard_near`; an empty token is
  false. Its test is `abs(start - t) <= HEARD_AGREE_S`, written that way, with `t` the new
  start exactly as the search returns it. No range test, bisect or rounding: on the record
  11 heard copies lie 0.25 s from the new start to within float rounding, 10 of them
  agreeing (block R8), so another form of the test changes the 593.
- Keep one copy of the search and the move. The fired path now does the rise, clamp,
  shift floor and moved copy inline. Factor them into helpers both paths call: one
  returns the exit (no rise, below the floor, or the new start), one builds the moved
  line. Keep every arithmetic expression as it is now: 2b compares floats exactly.
- Counters. The on-time path never touches `n_fired`, `n_no_rise`, `n_below_min_shift`,
  `n_undetectable`, `n_snapped` or `snaps`. It gets its own `heard_snaps` (records shaped
  like `snaps`: `line_id`, `shift_s`) and `n_heard_snapped = len(heard_snaps)`. The
  existing invariant comment stays true as written. Add `n_heard_snapped ==
  len(heard_snaps)` beside it. The `logger.info` line counts both lists.
- Docstrings: the module docstring's "an on-time line is never made worse" and
  `snap_line_onsets`'s on-time paragraph say that a loud start still counts as on time
  unless the transcriber heard the first word at a later rise.

Tests (synthetic envelopes as in the file; `_line` names its words `w0`, `w1`, ...). Place
each heard word relative to the start the same line gets when doubted, computed in the
test, never at the exact 0.25 s edge:

1. The `test_doubted_source_is_searched_past_a_loud_start` envelope, line not doubted, a
   heard `w0` 0.2 s after the doubted start: the same start as the doubted line;
   `n_heard_snapped == 1`, `heard_snaps[0]["line_id"]` set, `n_snapped == 0`,
   `n_fired == 0`.
2. The same with the heard `w0` 0.3 s after: untouched (`out[0] is obj`).
3. A heard `w1` at the doubted start: untouched.
4. A heard `"W0,"`: agrees, as in test 1.
5. `test_on_time_word_before_pause_untouched` kept unchanged. Add a twin with a heard `w0`
   at the claimed start (1.2 s): untouched. The skip exists for this case.
6. Heard words None and `[]` on test 1's envelope: untouched, stats equal to a call
   without the argument.
7. A doubted line with no agreeing heard word still moves, counted in `n_snapped`.
8. A line whose source is in `heard_timed_sources`, with a heard `w0` 0.2 s after the
   doubted start: untouched (`out[0] is obj`), `n_heard_snapped == 0`.
9. `snap_line_edges`: with heard words, the line before a moved line ends later than
   without, as the probe's `TestWithRule` shows.
10. `snap_line_edges` on test 9's lines with the moved line's source in
    `heard_timed_sources`: equal to the call without heard words.
11. Test 1's line with the heard `w0` 0.2 s before the doubted start: moves, as in test 1.
    Tests 1-4 all place the heard word after the new start.

Mutation checks, file restored after each. Each must fail at least one test: tolerance
0.35; token comparison dropped; the on-time path counting into `n_snapped`;
`snap_line_edges` not passing `heard_words` on; the `heard_timed_sources` exclusion
removed; `snap_line_edges` not passing `heard_timed_sources` on; the heard test made
one-sided (`start - t` in place of `abs(start - t)`).

### 2b. The CPU check

Files: `scripts/onset_loud_start_probe.py`, `tests/unit/test_onset_loud_start_probe.py`.
Commit `feat(scripts): the onset probe checks the snap's new exit against its rule`.

- New flag `--check`, in an argparse mutually exclusive group with `--listen`.
  `--listen` rewrites the ten after-files the check reads.
- Under `--check` nothing is decoded. A cue-route bundle with no envelope in `<out>/env`
  is not replayed, and is counted and named on its own line of Table E, apart from the
  songs left out. The library has grown past the record: on 2026-11-15 it holds 177
  cue-route bundles, 147 with an envelope in the record's cache (the 133 and the 14) and
  30 without (all written 2026-11-12). Decoding those here would add songs the record
  does not have, on this box's decode.
- For each song replayed exactly, run the new code:
  `onset_snap.snap_line_edges(before, "", env=env, doubted_sources=DOUBTED,
  heard_words=bundle.get("transcribe_words"), heard_timed_sources=HEARD_TIMED)`, where
  `HEARD_TIMED = frozenset({"transcribe"})` sits beside `DOUBTED` as the probe's copy of
  what the stage passes. No cue-route line has that source, so it changes no count here.
  Compare its output with `with_rule(before, song, env)`. They are equal when every
  line's `line_id`, `start`, `end` and each word's `start` and `end` match exactly
  (`source` differs by construction). When `karaoke/<stem>.onsetfix.ass` exists, compare
  `generate_ass(output, config)` with that file's text.
- Print Table E, counts and stems only:
  - songs compared
  - songs whose lines equal the probe's rule
  - lines the new code moved (`n_heard_snapped` summed)
  - agreed lines (`agreed` summed)
  - songs where those two differ, named
  - after-files found, and how many equal
  - cue-route bundles with no envelope in the cache, not replayed, named
- `replay_song`, `rise_start`, `heard_near`, `with_rule` and `AGREE_S` stay as they are.
  They are the reference this check compares against, as `onset_branch` is for the gates.
  `replay_song` passes no heard words, so it still reproduces schema-11 bundles, and
  "replayed exactly: 133" doubles as the check that the default is today's pass. Add one
  docstring line: the probe measures schema-11 bundles, made before this exit shipped.
- Test: on the `TestWithRule` fixture, the check finds the two equal. With `with_rule`
  monkeypatched to shift one line, it finds and names the difference.

Run it on this Linux box, CPU only, never decoding. The 11-10 envelopes are the reference:
`cue_heard_rescue` Results row 13 found that this box's decode is not bit-identical to
the bundles'. The record is `/media/ken/Data/probes/onset_loud_start/`; that drive is not
always mounted, so read its local copy, `~/probes/onset_loud_start/` (made 2026-11-14,
`diff -r` finds the two equal). Copy the cache; never write into either record folder:

    mkdir -p ~/.pikaraoke/tmp/onset_loud_start_check
    cp -r ~/probes/onset_loud_start/env ~/.pikaraoke/tmp/onset_loud_start_check/
    python scripts/onset_loud_start_probe.py --folder ~/pikaraoke-songs \
        --out ~/.pikaraoke/tmp/onset_loud_start_check --check \
        > ~/.pikaraoke/tmp/onset_loud_start_check/report.md

Pass, all of:

- Replayed exactly: 133, with the same 14 left out (R1). Tables A-C and Table B's fourth
  row equal R1 and R4. `cmp` finds the new `rows.json` equal to
  `~/probes/onset_loud_start/rows.json`.
- Table E: 133 compared, 133 equal, 593 moved, 593 agreed, none differing; 10 after-files
  found, 10 equal; 30 bundles with no envelope, not replayed (more if songs were added
  after 2026-11-15; none may be a bundle written before 2026-11-10 12:00).
- The reference dump: `reference_after.json` equal to `reference_before.json`.

Results row 6 already shows that this replay, with that cache, reproduces the record's
593 lines and rises. So a failure here is in the build, not the inputs. On a failure,
stop and report; don't loosen the check.

Once it passes, the gate's cleanup. Steps 1 and 2 write to `/media/ken/Data`. If it is not
mounted, log the check, leave the after-files where they are and report the cleanup as
owed:

1. Move the ten after-files from `~/pikaraoke-songs/karaoke/` to
   `/media/ken/Data/probes/onset_loud_start/onsetfix/`.
2. `cmp` the copies in `/media/ken/Data/pikaraoke-songs/karaoke/` against the moved files,
   then delete those copies.
3. Leave the after-file copies under `~/probes/`; they belong to other branches' staged
   trials.
   Any in `D:\Shared\pikaraoke-songs\karaoke\` on Windows are Ken's to delete (Phase 3).
4. Rerunning `--check` afterwards finds 0 after-files; that is expected.

### 2b2. A first word also heard earlier keeps its start

Ruled by Ken 2026-11-15 ("Read and ruling"). Built only after 2b's check has passed at
593 and the after-files have been compared. Files: `pikaraoke/lib/onset_snap.py`,
`tests/unit/test_onset_snap.py`, `scripts/onset_loud_start_probe.py`,
`tests/unit/test_onset_loud_start_probe.py`. Commit
`feat(onset_snap): a first word the transcriber also heard earlier keeps its start`.

Why: on the record 4 of the 593 moves pass an earlier heard copy of the first word and
are agreed by a later one (block R8). All four are lines whose second word is the first
word again; the move leaves the first word a sliver before the second. None was on the
GATE S sheet. The guard only takes moves away, so those lines keep the start that ships
today.

- The rule: an on-time line with a rise and an agreeing heard word does not move when
  some heard word equal to its first word starts at or after the claimed start, before
  the new start, and does not itself agree:
  `w1s <= start < new_start and not abs(start - new_start) <= HEARD_AGREE_S`. The
  agreement expression is 2a's, so one test decides both.
- `onset_snap`: `_heard_earlier(pairs, first_word, w1s, t)` beside `_heard_near`, called
  on the on-time path only. A held line is appended untouched and counted in
  `n_heard_earlier`, a new stat beside `n_heard_snapped`. Doubted lines and the fired path
  never consult it. The on-time paragraph of `snap_line_onsets`'s docstring says so.
- The probe: its own copy, `heard_earlier(transcribe_words, first_word, start, t)`,
  beside `heard_near`. `song_rows`'s `agreed` becomes `rise is not None and
  heard_near(...) and not heard_earlier(...)`. Table B's fourth row is named "a heard
  first word within 0.25 s of the rise and none earlier, no cue anchor". Table E gains
  "lines held by an earlier heard copy" (`n_heard_earlier` summed). `heard_near`,
  `rise_start`, `with_rule` and `replay_song` stay as they are. The module docstring's
  sentence on the rule under test gains the condition.

Tests in `test_onset_snap.py`, continuing 2a's numbering. Tests 12-14 use
`test_on_time_word_before_pause_untouched`'s envelope and spans with word 2 given word
1's text (build the words by hand; `_line` names them `w0`, `w1`). The start the line
gets when doubted is computed in the test, as in 2a:

12. One heard copy, at word 2's start: the line moves to the doubted start. This is the
    fault, and shows tests 13-14 are not passing for want of a move.
13. That copy and one 0.1 s after the claimed start: untouched (`out[0] is obj`),
    `n_heard_earlier == 1`, `n_heard_snapped == 0`.
14. The copy at word 2's start and one 0.3 s before the claimed start: moves. The
    previous line's word does not hold this one.
15. Test 1's line with two heard `w0`, 0.2 s before and 0.2 s after the doubted start:
    moves. A copy before the new start that agrees does not hold it.

Mutation checks, as in 2a: the guard removed (fails 13); its lower bound dropped (fails
14); "does not itself agree" dropped (fails 15).

Probe test: a `song_rows` row whose line has an earlier heard copy and an agreeing one
has `agreed` false; without the earlier copy, true.

Then rerun 2b's command. Pass, all of:

- Replayed exactly: 133, the same 14 left out. Tables A-C equal R1. Table B's fourth row:
  589 moved, 589 with heard, 519 closer, 24 same, 46 further, 407 early now within 0.3 s.
- Table E: 133 compared, 133 equal, 589 moved, 589 agreed, none differing, 4 held by an
  earlier heard copy.
- `rows.json` differs from `~/probes/onset_loud_start/rows.json` only in `agreed`, on four
  rows (a scratch compare, logged): Backstreet Boys - Quit Playing Games (With My Heart)
  `Ug88HO2mg44` line 58; Jessie J - Domino `UJtB55MaoD0` lines 17 and 60; Queen - Bohemian
  Rhapsody `fJ9rUzIMcZQ` line 33.
- After-files: 0 found. If 2b's cleanup is still owed (drive not mounted): 10 found, 9
  equal, and Bohemian Rhapsody's differs, since it holds line 33's move.

The reference dump is not rerun: `with_rule` and the snap's search are as 2b left them.

### 2c. The stage passes the heard words; schema 12

Files: `pikaraoke/pipeline/stages/lyric_align.py`, `pikaraoke/lib/alignment_capture.py`,
`tests/unit/test_lyric_align.py`. Commit
`feat(lyric_align): the edge snap checks a loud start against the heard words, schema 12`.

- The one `snap_line_edges` call passes `heard_words=capture_transcribe_words` and
  `heard_timed_sources=frozenset({"transcribe"})`, the literal as `joint_match` spells
  it, on every route. A line keeps that source through windowed re-align (a replayed line
  carries its own sub-match's source), so the final `source` is the right key.
  `capture_transcribe_words` is None in transcription mode, so that route is unchanged.
  Update the comment above the call.
- Two sentences go stale: `_run_cue_align`'s docstring and the `transcribe_words` note in
  `alignment_capture.py` both say the cue route doesn't use the heard words. The edge
  snap now does. `cue_heard_rescue` rewrites the same two sentences; whichever branch
  lands second keeps both uses.
- `SCHEMA_VERSION = 12`, with a `# v12:` block above `# Additive since v11` worded like
  v11's: a milestone bump (run-affecting), no field renamed or removed;
  `output_line_timings` move, so regen treats v11 bundles as stale. Say what changed: the
  onset snap moves a line it took as on time when the transcriber heard its first word
  within 0.25 s of a later rise and did not also hear it earlier in the line (this plan).
  Additive: `joint_stats.edge_snap.onset` gains `n_heard_snapped`, `heard_snaps` and
  `n_heard_earlier`. The bump rides with the wiring, so no `dev` commit writes the new
  output under the old number.

Tests:

- The three `MagicMock` snap stand-ins (`test_lyric_align.py` 632, 646, 707) take the new
  keywords.
- Cue route: the snap gets the gate's words, using the words from
  `test_the_gates_transcribe_words_reach_the_bundle`. That test's docstring loses "The
  cue route doesn't use them".
- Joint route: the snap gets the words and `frozenset({"transcribe"})`.
- Transcription mode: `heard_words` is None.
- Nothing pins 11. The bundle test at 874 reads `SCHEMA_VERSION`, and
  `test_processing_routes.py`'s literal 11 doesn't depend on the version.

Mutation check: the stage passing `heard_words=None` fails the cue test.

Close of Phase 2:

- Full suite.
- `pre-commit` on the changed files.
- `graphify update .`
- Results rows.
- The CLAUDE.md checkpoint with a Review due line (multi-file, core pipeline).

Then stop.

### 3. Ken's regen on Windows, then a read

- Before it, Ken deletes any `.onsetfix.ass` from `D:\Shared\pikaraoke-songs\karaoke\` and
  checks out the branch on the Windows box.
- Regenerate from this branch as cut: it does not hold `backing_vocal_lines`. Schema 12
  makes every bundle stale, so a regen on a base that holds that branch adds its backing
  lines to every affected song, ahead of its GATE B regen decision, and mixes them into
  this read. If the order does flip, the read splits cue songs by whether the v12 bundle
  has a kept group in `joint_stats.backing` (that plan's "Landing order" carries the same
  note).
- `uv run python scripts/regen_alignment_bundles.py D:\Shared\pikaraoke-songs --dry-run`
  should list every bundle as `v11` (234 in this box's library on 11-14). Then run it with
  `--yes`. Old files go under `regen_backups/<UTC>/`.
- The read: Sonnet or Opus, CPU, read-only, scratch not kept. Per route, from the new
  bundles and the backup's v11 bundles, tabulate:
  - songs and lines
  - `n_snapped` at v11 and at v12
  - `n_heard_snapped` and `n_heard_earlier` at v12
  - the ten songs with the most heard moves
- Logged as a Results row with the raw table.
- What to expect: a fresh whisper run moves a different exact set, but the cue route
  should sit near the 11-10 rate (593 over 133 songs), with `n_snapped` near v11.
- The joint route's numbers are its first measurement (Decision 5). A route far off the
  cue rate goes to Ken before landing.

### 4. Land on `dev`

- Copy onto `dev`, in order, with their messages: `b054f918`, `ad8b51af`, then 2a, 2b,
  2b2, 2c and any fix commits. Leave out the plan-only commits (`02906b91`, `a817be32`,
  `56dce3c7`, and this spec's).
- If `cue_heard_rescue` landed first, the two stale-sentence edits conflict: keep both
  uses. Its `align_song(..., heard_words=...)` change sits near this branch's snap call.
  Replay this branch onto it, then rerun the full suite on `dev`.
- `scripts/cue_heard_probe.py` on `cue_heard_rescue` replays bundles through
  `snap_line_edges` with no heard words. Whichever branch lands second gives that call the
  bundle's `transcribe_words` and the stage's `heard_timed_sources`; without them its
  replay cannot reproduce a v12 bundle that has a heard move.
- `plans/open-issues.md`, in its own commit on `dev`: strike the "Onset snap" entry with
  `~~ ~~` and add a line pointing at `archive/onset_loud_start`.
- Push `dev`. Retire the branch as `archive/onset_loud_start` per CLAUDE.md.

### O1 (ruled 2026-11-14)

**O1. Joint lines timed from the transcriber's own words.**

**Ruling: (a). Fable 5.2, 2026-11-14, on Ken's hand-off.** Transcribe-timed lines are left
out of the new exit; align-won and ytasr-won joint lines take it as cue-route lines do.

- A transcribe-won line starts on a heard word's own start (`_build_line_object` copies
  it): all 641 in the scratch replay do, 575 on the first word itself. A move of 0.25 s or
  less is then agreed by that same word, so the check confirms nothing there.
- Align-won and ytasr-won lines take their times from the forced aligner and from
  YouTube's captions. The transcriber only picks which candidate wins and where a
  re-align slice opens, seconds wide; it sets no start. The check is as independent
  there as on the cue route, which GATE S passed, so (c) is not needed.
- Over the 45 joint songs that replay (Results row 7), 143 lines move under (b): 135
  align-won, 3 ytasr-won, 5 transcribe-won. (a) gives up the 5, four of them agreed only
  by their own word; (c) would give up all 143.

As it stood before the ruling:

- On the joint route, a line whose winning candidate is the transcriber's (`source ==
  "transcribe"`) takes its first word's start from a heard word. Any move of 0.25 s or
  less is then agreed by that same word.
- In this library, 824 of the 3053 joint lines (57 bundles) were transcribe-won in pass 1
  (Results row 6).
- Decision 5 (build for every route) was ruled before this was seen.

Options:

- **(a) Exclude those lines** (`heard_timed_sources`). Costs one parameter. The cue route
  never has that source, so 2b is unaffected. Recommended. **Taken.**
- **(b) As ruled:** no exclusion.
- **(c) Cue route only.** Simplest; the joint route keeps today's early starts.

### Uncertain (for Fable's read)

1. **O1, and whether joint align-won lines are independent of the transcriber.** Answered
   under O1: they are, in the sense the check needs. One residue, shared with the cue
   route: the aligner and the transcriber are the same model on the same stem, so their
   times cluster (block R7, last table).
2. **Heard words nearer the shipped start.** In 57 of the 593 moves, every agreeing heard
   word is nearer the shipped start than the new one; in 19 it sits at or before the
   shipped start (Results row 6). One of the 57 is on the sheet (Table D row 6), labelled
   better; the worse line (row 12) is not among them. The spec keeps the rule as passed.
3. **Row 12 is out of the reference's reach.** The reference puts its new start 0.05 s
   after the heard word, so the transcriber is late there too. Of the 593, 6 end more than
   0.3 s after the reference's word, against 1 before the move.
4. **The counting.** Heard moves appear only in new fields, so every v11 field is equal on
   v11 input. A future reader that takes `n_snapped` as "lines moved" would undercount;
   only the probe reads it today.
5. **The check's independence.** The probe's own copies are the reference, and the ten
   after-files and the record's `rows.json` tie it to 11-10. Does any part of 2b compare
   the new code with itself?
6. **Regen before landing** (this spec) or after.

### Read and ruling (2026-11-15)

Fable 5.2's read of O1, the six items above, 2a-2c for exactness, and the contact with
`backing_vocal_lines`. Read-only; counts in Results row 8 / block R8. Ken ruled the same
day: all four changes taken.

By item:

1. **Holds.** An align-won line's word times are copied from the forced aligner's words
   (`_align_line_object`). The transcriber scores which candidate wins and where a
   re-align span opens, and a re-aligned line keeps its own sub-match's source.
   `cue_heard_rescue` adds no line source. No change.
2. **Kept as passed.** An agreeing word is within 0.25 s of the new start by construction,
   so these moves are at most that far past where the transcriber heard the word. 6 of
   the 57 are in the after-file songs; none of the 19.
3. **Holds.** Row 12's first word is not repeated and no heard copy is passed over, so
   nothing in the transcript marks it. No change.
4. **Holds.** Only the probe reads `n_snapped`. One reader to fix at landing:
   `cue_heard_probe.py` (Phase 4).
5. **Partly self-comparing.** A moved line's start is checked against the probe's own
   `rise_start`, and unmoved lines against the record's `rows.json`. A moved line's
   word-1 end and the extension of the line before it pass through the refactored code on
   both sides. Change 3.
6. **Regen before landing, kept.** Results row 7 already gives the joint route a first
   figure (138 moves over 45 songs).

The four changes (Ken: take all four):

1. **2b skips a bundle with no envelope in the cache.** Without it the check decodes 30
   songs the record does not have and cannot report 133. Written into 2b.
2. **The repeated-first-word guard**, as its own commit after 2b passes at 593. Written
   as 2b2. Bohemian Rhapsody line 33 can be heard with its after-file at about 3:06 until
   2b's cleanup; the guard does not wait on that.
3. **The reference dump before 2a.** Written as "Before 2a".
4. **A heard word before the new start agrees** (2a test 11, and its mutation check).

Also written in: the exact form of the heard test (2a), since 10 of the 593 turn on float
rounding at the 0.25 s edge.

From the code only, for `backing_vocal_lines` (written into that plan's "Landing order",
`backing_vocal_lines` branch, same day):

- An echo line after its lead is not agreed by the lead's heard copy in normal placement:
  the lead's first word starts a line earlier, and a copy more than 0.1 s before the
  echo's claimed start cannot agree with any start the search returns. It can only when
  the echo was placed on top of its lead.
- A line that starts with an echo of its own next word is 2b2's case. The guard holds it
  only when the transcriber heard both copies.
- An echo the transcriber never heard, with a loud claimed start, is never moved by this
  exit. It is searched only if its start is quiet or its source is doubted.
- The regen order: see Phase 3.

## Results log

| # | Date | Phase | What ran | Raw result |
|---|---|---|---|---|
| 1 | 2026-11-10 | 0 | Fable, CPU on the VM. `onset_loud_start_probe.py --folder /home/ken/shared-drives/D:/Shared/pikaraoke-songs`, library as of 2026-11-10 (159 bundles, all schema 11: 147 cue-align, 12 joint) | Block R1 below |
| 2 | 2026-11-10 | 0 | Fable, scratch (not kept): over the skipped lines with a rise, the longest run of frames under `ref - SUSTAIN_NEAR_DB` between the claimed start and the rise | Block R2 below |
| 3 | 2026-11-10 | 0 | Fable, scratch (not kept): the rule as production would run it, any heard word equal to the line's first word within the tolerance of the rise (no cue anchor) | Block R3 below |
| 4 | 2026-11-10 | 1 | Fable, CPU on the VM. `onset_loud_start_probe.py --folder /home/ken/shared-drives/D:/Shared/pikaraoke-songs --out /home/ken/shared-drives/D:/Shared/onset_loud_start --listen`. Out folder (`D:\Shared\onset_loud_start` on Windows): `report.md`, `rows.json`, `listening-sheet.html`, `env/` | Tables A-C equal R1; Table B's new row and Table D in block R4. 133 of 133 replayed songs regenerate their shipped `.ass` exactly. Over those songs 593 lines move and 955 Dialogue lines differ, each one a moved line or the worded line before one (scratch check). 10 `.onsetfix.ass` files written to the library's `karaoke/` |
| 5 | 2026-11-10 | GATE S | Ken's ear on Windows; labels in the sheet's artifact database (`https://claude.ai/artifact/RLMm6PcTbWzFHcedjqHGVK`, collection `labels`), read by Opus 5.5 | Block R5 below |
| 6 | 2026-11-14 | spec | Opus 5.5, scratch (not kept), CPU on the Linux box (`kenskaraoke`): the probe's `replay_song` and `song_rows` over `~/pikaraoke-songs`, reading a copy of `/media/ken/Data/probes/onset_loud_start/env/` (no decode), restricted to the 133 songs in that folder's `rows.json`; agreeing heard words are those equal by `_normalize_token` to the line's first word and within `AGREE_S` of `rise`. Joint counts from every joint bundle's `joint_stats.{transcribe,align,ytasr}_won` | Block R6 below |
| 7 | 2026-11-14 | O1 | Fable 5.2, scratch (not kept), CPU on the Linux box, library read-only. Each joint bundle replayed: pass 1 by `match_words_to_lines_joint_with_stats` over the bundle's `words`, `transcribe_words`, knobs and the adopted ASR json3 (found by video id), checked against `selected_source` and `pass1_line_timings`; windowed re-align by `replay_span` + `merge_spans` over the captured spans; the veto; `snap_line_edges`. A song counts when every worded line's start and end fall within 0.011 s of `output_line_timings` (LRCLIB-filled lines left out), word counts are equal and `n_snapped` is equal. Envelopes decoded on this box from the library's stems, so not the bundles' decode. Then the probe's `onset_branch`, `rise_start` and `heard_near` on each worded line before the snap, by its final `source` | Block R7 below |
| 8 | 2026-11-15 | read | Fable 5.2, scratch (not kept), CPU on the Linux box, library and record read-only (`/media/ken/Data` not mounted; a copy of `~/probes/onset_loud_start/` `env/` and `rows.json` was read). No replay: counts are over the record's `rows.json` rows joined to each song's bundle in `~/pikaraoke-songs/alignment_debug` (`transcribe_words`, `lyrics.align_lines`), tokens by `_normalize_token`; a heard copy is a transcribe word equal to the line's first word. Library inventory from the bundles' `method_used`, file mtimes and the cache's file names | Block R8 below |

**R1** (the probe's stdout, verbatim)

Songs replayed exactly: 133. Left out: 14 (not diagnosed: five Flight of the Conchords,
four Rent, three The Last Five Years, Tenacious D - Tribute, The Philosopher Kings - Hurts
To Love You).

Worded lines 7988; with a heard first word 6553; early (start more than 0.3 s before it)
1174; late 1429.

Table A, lines by the onset snap's exit

| exit | lines | with heard | early | late |
|---|---|---|---|---|
| on_time | 3969 | 3224 | 954 | 530 |
| snapped | 1973 | 1710 | 46 | 543 |
| below_min_shift | 1031 | 874 | 44 | 170 |
| no_rise | 577 | 421 | 103 | 69 |
| narrow | 356 | 273 | 8 | 107 |
| low_ref | 82 | 51 | 19 | 10 |

Skipped as on time and early: 954; starting at the previous line's end 678; with a rise to
move to 573; heard word after word 2's start 53.

Table B, rules for searching a line skipped as on time

| rule | moved | with heard | closer | same | further | early now within 0.3 s |
|---|---|---|---|---|---|---|
| every skipped line | 1213 | 1032 | 637 | 39 | 356 | 431 |
| starts at the previous line's end | 858 | 722 | 464 | 27 | 231 | 306 |
| heard word within 0.25 s of the rise | 585 | 585 | 517 | 24 | 44 | 407 |

Table C, the snaps that ship today, by the same reference: snapped lines with a heard word
1710: closer 1025, same 84, further 601.

Scratch figures from the same rows: early skipped lines are early by p25 0.43, median
0.64, p75 1.01, p90 1.70 s; word 1's claimed length on them p25 0.72, median 1.00, p75
1.45 s, against 0.20, 0.32, 0.53 s on skipped lines within 0.15 s of the heard word.

**R2** (quiet before the rise; "end past" = new start more than 0.2 s after the heard word)

| rule | moved | with heard | closer | same | further | end past | early now within 0.3 s |
|---|---|---|---|---|---|---|---|
| every skipped line | 1213 | 1032 | 637 | 39 | 356 | 459 | 431 |
| quiet >= 0.1 s | 879 | 754 | 494 | 24 | 236 | 327 | 361 |
| quiet >= 0.2 s | 587 | 514 | 344 | 16 | 154 | 236 | 273 |
| quiet >= 0.3 s | 386 | 342 | 233 | 13 | 96 | 167 | 188 |
| at previous end, quiet >= 0.2 s | 421 | 361 | 245 | 11 | 105 | 167 | 192 |

**R3** (the rule without a cue anchor)

| tolerance | moved | songs | closer | same | further | early now within 0.3 s | at previous end | move p25 / median / p75 |
|---|---|---|---|---|---|---|---|---|
| 0.15 s | 441 | 121 | 423 | 10 | 8 | 315 | 321 | 0.28 / 0.46 / 0.78 |
| 0.25 s | 593 | 125 | 519 | 24 | 50 | 407 | 436 | 0.27 / 0.48 / 0.79 |
| 0.35 s | 691 | 127 | 562 | 29 | 100 | 431 | 501 | 0.27 / 0.47 / 0.78 |

At 0.25 s: 282 moves of 0.5 s or more, 169 under 0.3 s. Songs with the most moved lines:
Aladdin (2019) - Speechless 13, The Last Five Years - A Summer in Ohio 13, The Last Five
Years - The Schmuel Song 12, Rent - Another Day 11, Backstreet Boys - The Call 10, Beauty
and the Beast (1991) - Belle 10, Flight of the Conchords - Business Time 10, Lewis Capaldi -
Someone You Loved 10, Queen - Bohemian Rhapsody 10, Backstreet Boys - I Want It That Way 9.

**R4** (the probe's stdout, verbatim; a song without a video id is a movie clip named by title)

Table B, added row

| rule | moved | with heard | closer | same | further | early now within 0.3 s |
|---|---|---|---|---|---|---|
| a heard first word within 0.25 s of the rise, no cue anchor | 593 | 593 | 519 | 24 | 50 | 407 |

Table D, the listening sheet (20 lines; a song is eligible when its replay regenerates the
shipped subtitle file exactly: 133 songs)

| # | song | line | shipped start | fixed start | lines moved in song | Dialogue lines changed in song |
|---|---|---|---|---|---|---|
| 1 | mw5VIEIvuMI | 33 | 130.06 | 132.03 | 13 | 21 |
| 2 | mw5VIEIvuMI | 26 | 107.55 | 108.10 | 13 | 21 |
| 3 | The Last Five Years (2014) - A Summer in Ohio | 33 | 116.76 | 119.13 | 13 | 19 |
| 4 | The Last Five Years (2014) - A Summer in Ohio | 24 | 86.42 | 86.85 | 13 | 19 |
| 5 | The Last Five Years (2014) - The Schmuel Song | 46 | 144.19 | 145.70 | 12 | 17 |
| 6 | The Last Five Years (2014) - The Schmuel Song | 33 | 100.47 | 100.70 | 12 | 17 |
| 7 | Rent (2005) - Another Day | 20 | 72.06 | 73.10 | 11 | 19 |
| 8 | Rent (2005) - Another Day | 7 | 27.61 | 27.95 | 11 | 19 |
| 9 | wMOkm57vu0k | 38 | 96.00 | 96.73 | 10 | 16 |
| 10 | wMOkm57vu0k | 16 | 36.49 | 36.93 | 10 | 16 |
| 11 | otxTf5hZ0Yw | 97 | 236.71 | 238.05 | 10 | 16 |
| 12 | otxTf5hZ0Yw | 100 | 248.53 | 248.95 | 10 | 16 |
| 13 | Flight of the Conchords (2007) - Business Time | 76 | 205.91 | 207.10 | 10 | 14 |
| 14 | Flight of the Conchords (2007) - Business Time | 22 | 71.41 | 71.85 | 10 | 14 |
| 15 | zABLecsR5UE | 8 | 33.22 | 33.68 | 10 | 14 |
| 16 | zABLecsR5UE | 45 | 133.40 | 133.78 | 10 | 14 |
| 17 | fJ9rUzIMcZQ | 12 | 48.40 | 49.55 | 10 | 15 |
| 18 | fJ9rUzIMcZQ | 20 | 93.53 | 94.43 | 10 | 15 |
| 19 | 4fndeDfaWCg | 5 | 26.02 | 27.88 | 9 | 18 |
| 20 | 4fndeDfaWCg | 29 | 102.43 | 103.18 | 9 | 18 |

**R5** (Ken's labels, by Table D row; no notes were left on any line)

| # | label | late |
|---|---|---|
| 1 | better | |
| 2 | better | |
| 3 | better | |
| 4 | better | |
| 5 | better | |
| 6 | better | |
| 7 | better | |
| 8 | better | |
| 9 | better | |
| 10 | better | |
| 11 | better | |
| 12 | worse | yes |
| 13 | better | |
| 14 | better | |
| 15 | better | |
| 16 | better | |
| 17 | better | |
| 18 | better | |
| 19 | better | |
| 20 | better | |

**R6** (spec-time, scratch)

- Library on 11-14: 234 bundles, all schema 11 (177 cue-align, 57 joint). The 147
  cue-align bundles captured before 2026-11-10 12:00 are the record's; 30 cue-align and 50
  joint were added or redone after it.
- Replay of the record's 133 songs: the agreed set equals `rows.json` (593 lines, the same
  songs and line ids), and every `rise` is equal.
- Agreeing heard words on the 593:

| condition | lines |
|---|---|
| every agreeing heard word nearer the shipped start than the new start | 57 |
| every agreeing heard word at or before the shipped start | 19 |
| an agreeing heard word within 1 ms of the shipped start | 2 |

- The 57's moves: min 0.16, median 0.21, max 0.48 s; 9 of 0.3 s or more. Table D lines
  among them: row 6 (The Schmuel Song line 33).
- Against the record's `heard` (the reference word nearest the cue anchor), on the 593:

| | before the move | after |
|---|---|---|
| more than 0.3 s late | 1 | 6 |
| more than 0.3 s early | 410 | 2 |

- Table D row 12: shipped 248.53, fixed 248.95, `heard` 248.90.
- Joint bundles: 57, 3053 lines. Pass-1 winners: transcribe 824, align 1621, ytasr 349.

**R7** (O1, scratch)

- Joint bundles 57; replayed 45. Left out 12, each on a final line time that differs from
  the bundle (not diagnosed): A-Lin - Happiness Is Singing, Backstreet Boys - Show Me The
  Meaning Of Being Lonely, Bruno Mars - Grenade, Donna Murphy - Mother Knows Best, Ingrid
  Michaelson - Be OK, Jessie J - Flashlight, Kristen Bell & Idina Menzel - For the First
  Time in Forever, Mandy Moore & Zachary Levi - I See the Light, NSYNC - Here We Go, Sara
  Bareilles - King of Anything, Tenacious D - Kickapoo, Westlife - Flying Without Wings.
- Worded lines before the snap, by the line's final `source`:

| | align | transcribe | ytasr |
|---|---|---|---|
| lines | 1302 | 641 | 280 |
| start equal to a heard word's start, any word | 64 | 641 | 4 |
| start equal to a heard word's start, the line's first word | 50 | 575 | 4 |
| the first word heard within 0.25 s of the start | 577 | 575 | 165 |
| exit on_time | 783 | 327 | 189 |
| exit snapped | 262 | 121 | 7 |
| exit below_min_shift | 91 | 121 | 69 |
| exit narrow | 98 | 48 | 5 |
| exit no_rise | 62 | 22 | 6 |
| exit low_ref | 6 | 2 | 4 |
| on_time with a rise | 259 | 60 | 21 |
| agreed: moves with no exclusion (b) | 135 | 5 | 3 |
| agreed, move of 0.25 s or less | 29 | 4 | 2 |
| agreed, move over 0.25 s | 106 | 1 | 1 |
| agreed only by the heard word at the line's own start | 1 | 4 | 0 |
| every agreeing heard word at or before the start | 1 | 4 | 1 |
| every agreeing heard word nearer the start than the new start | 9 | 4 | 2 |

- Moves: 143 under (b), in 36 of the 45 songs; 138 under (a). Move min / median / max:
  align 0.15 / 0.46 / 9.42 s, transcribe 0.16 / 0.22 / 0.74 s, ytasr 0.16 / 0.18 / 0.40 s.
- Align-won lines, the heard first word's start minus the line's start, counted in 20 ms
  steps out to 60 ms:

| step | -3 | -2 | -1 | 0 | +1 | +2 | +3 |
|---|---|---|---|---|---|---|---|
| heard words | 14 | 24 | 27 | 70 | 36 | 29 | 18 |

**R8** (the read, scratch)

- Library on 11-15: 234 bundles, all schema 11; 177 cue-align. Cue-align bundles by file
  date: 11-05 24, 11-06 64, 11-07 19, 11-08 7, 11-09 33, 11-12 30. With an envelope in
  the record's cache: 147 (the record's 133 and 14 others); without: 30. Record songs
  whose bundle was written after 2026-11-10 12:00: 0. After-files in
  `~/pikaraoke-songs/karaoke/`: 10.
- Heard copies 0.25 s from the rise, over the 1213 on-time lines with a rise (within 1e-9
  s of the edge: 11; no other copy is within 2 ms of it). `agrees` is
  `abs(start - rise) <= 0.25` as the probe computes it:

| song | line | heard start | rise | `abs(start - rise)` | agrees |
|---|---|---|---|---|---|
| `pj6FCKm8dhM` | 37 | 134.2 | 134.45 | 0.25 | yes |
| `0LSYuZRSGcY` | 72 | 162.2 | 161.95 | 0.25 | yes |
| `6HCUoMgviwU` | 7 | 24.8 | 25.05 | 0.25 | yes |
| `6HCUoMgviwU` | 26 | 87.9 | 88.15 | 0.25 | yes |
| `K0ibBPhiaG0` | 25 | 134.84 | 135.09 | 0.25 | yes |
| Flight of the Conchords (2007) - Business Time | 51 | 149.3 | 149.54999999999998 | 0.24999999999997158 | yes |
| `uuZE_IRwLNI` | 68 | 253.7 | 253.95 | 0.25 | yes |
| KPop Demon Hunters (2025) - What It Sounds Like | 11 | 33.7 | 33.95 | 0.25 | yes |
| `Eo-KmOd3i7s` | 15 | 64.7 | 64.95 | 0.25 | yes |
| NSYNC - Paradise | 11 | 98.3 | 98.55000000000001 | 0.2500000000000142 | no |
| `gAYL5H46QnQ` | 43 | 147.1 | 147.35 | 0.25 | yes |

- The 593 agreed lines, by their words:

| condition | lines |
|---|---|
| word 2 equal to word 1 | 9 |
| word 2 or word 3 equal to word 1 | 21 |
| one-word line | 5 |
| new start within 0.1 s of word 2's start | 5 |
| every agreeing heard copy at or after word 2's start less 0.1 s | 16 |
| the same, and word 2 equal to word 1 | 2 |
| every agreeing copy nearer the shipped start (row 6's 57), in an after-file song | 6 |
| every agreeing copy at or before the shipped start (row 6's 19), in an after-file song | 0 |

- Agreed lines with a heard copy that does not agree and starts before the new start, by
  where the copy may start from:

| the copy starts | lines | of them, word 2 equal to word 1 |
|---|---|---|
| after the claimed start | 4 | 4 |
| at or after the claimed start | 4 | 4 |
| from 0.10 s before the claimed start | 4 | 4 |
| from 0.25 s before the claimed start | 4 | 4 |

- The four lines, the same under each row:

| song | line | shipped start | new start | word 2's start | earlier heard copies | agreeing heard copy | Table B verdict |
|---|---|---|---|---|---|---|---|
| Backstreet Boys - Quit Playing Games (With My Heart) `Ug88HO2mg44` | 58 | 166.127 | 166.85 | 167.07 | 166.18, 166.48 | 167.06 | further |
| Jessie J - Domino `UJtB55MaoD0` | 17 | 51.624 | 52.00 | 52.27 | 51.66 | 52.08 | further |
| Jessie J - Domino `UJtB55MaoD0` | 60 | 194.584 | 195.65 | 195.86 | 194.64 | 195.62 | further |
| Queen - Bohemian Rhapsody `fJ9rUzIMcZQ` | 33 | 190.65 | 191.55 | 191.67 | 190.97 | 191.66 | further |

- None of the four is a Table D line. Bohemian Rhapsody is the one after-file song among
  them. Its transcript there: the word at 190.97-191.52 and again at 191.66-192.32.
- Table B's fourth row with the four left out: 589 moved, 589 with heard, 519 closer, 24
  same, 46 further, 407 early now within 0.3 s. Songs with a moved line: 125, as before.
- Table D row 12 (`otxTf5hZ0Yw` line 100): word 2's start 249.07; first word not repeated;
  no heard copy between the shipped start and the new one.
- Other readers of the snap: `n_snapped` and `snaps` are read by this probe only.
  `scripts/cue_heard_probe.py` on `cue_heard_rescue` calls `snap_line_edges` (line 298).
  `generate_ass` does not read `source`. The cue route's line sources are `cue_align`,
  `cue_align_fill` and `cue_align_line`, on this branch and on `cue_heard_rescue`.
