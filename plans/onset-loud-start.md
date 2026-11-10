Model: Claude Fable 5.2 (author; ran Phases 0 and 1, 2026-11-10). Judge at GATE S: Ken's
ear; Claude Opus 5.5 reads his labels off. Phases 2-4 are loose, get their spec after the
gate, and go to Claude Sonnet 5.5.

# Onset snap: a loud start is not always this line's voice

**Status: Phase 1 built 2026-11-10 (Results row 4): the listening sheet and ten after-files
are written. Stopped for Ken's listening at GATE S. No production code has changed.**

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

## Phases 2-4 (loose)

2. `snap_line_onsets` takes the heard words; the on-time exit searches and keeps a move the
   heard word agrees with. New counter beside `n_fired`. The stage passes
   `capture_transcribe_words`. CPU check: the probe's replay with the new code moves
   exactly the Phase 1 lines.
3. `SCHEMA_VERSION` 12; Ken's regen on Windows.
4. Land on `dev`; strike the `plans/open-issues.md` entry.

## Results log

| # | Date | Phase | What ran | Raw result |
|---|---|---|---|---|
| 1 | 2026-11-10 | 0 | Fable, CPU on the VM. `onset_loud_start_probe.py --folder /home/ken/shared-drives/D:/Shared/pikaraoke-songs`, library as of 2026-11-10 (159 bundles, all schema 11: 147 cue-align, 12 joint) | Block R1 below |
| 2 | 2026-11-10 | 0 | Fable, scratch (not kept): over the skipped lines with a rise, the longest run of frames under `ref - SUSTAIN_NEAR_DB` between the claimed start and the rise | Block R2 below |
| 3 | 2026-11-10 | 0 | Fable, scratch (not kept): the rule as production would run it, any heard word equal to the line's first word within the tolerance of the rise (no cue anchor) | Block R3 below |
| 4 | 2026-11-10 | 1 | Fable, CPU on the VM. `onset_loud_start_probe.py --folder /home/ken/shared-drives/D:/Shared/pikaraoke-songs --out /home/ken/shared-drives/D:/Shared/onset_loud_start --listen`. Out folder (`D:\Shared\onset_loud_start` on Windows): `report.md`, `rows.json`, `listening-sheet.html`, `env/` | Tables A-C equal R1; Table B's new row and Table D in block R4. 133 of 133 replayed songs regenerate their shipped `.ass` exactly. Over those songs 593 lines move and 955 Dialogue lines differ, each one a moved line or the worded line before one (scratch check). 10 `.onsetfix.ass` files written to the library's `karaoke/` |

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
