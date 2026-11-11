# Refine ablation: does the whisper refine pass still earn its cost?

Model: Claude Opus 5.5

Status: **open, research only** -- nothing in the pipeline changed. Waiting on
an A/B listen (Next step). Branch `refine_ablation`, off `dev` at `1016e20`.

## Question

Ken, 2026-11-11: look at every whisper pass in every route (cue, joint, UI or
regen scripts) for passes that are extraneous or add little to alignment
accuracy, especially refine, the longest.

The last refine study (`plans/reduce-refine-time.md` on tag `archive/jointrefine`,
2026-06-22) cut `steps` from `"se"` to `"s"` and held off dropping refine: OFF
lost 1.6 points of lines within 0.5 s on align-heavy joint songs. It predates
edge snap (`onset_snap.py`) and the cue route (`cue_align.py`), and it scored
joint songs only.

## Whisper passes per route

Every route (UI processing, `scripts/regen_alignment_bundles.py`,
`scripts/backfill_artifacts.py`) goes through `LyricAlignStage`, so each pass
below has one call site in `pikaraoke/pipeline/stages/lyric_align.py`.

| route | passes |
| --- | --- |
| cue (SRT, 114/134 bundles) | whole-song transcribe, no refine (de-reverb gate; heard words for the bundle) -> [de-reverb retry: transcribe on dry stem] -> align+refine per section (median 7) -> [re-section, 7/114 songs: a second full section pass] -> align+refine per rescued line (median 7, 873 corpus-wide) |
| joint (txt / Genius / custom, 20/134) | whole-song transcribe, no refine -> [de-reverb retry] -> whole-song align+refine -> align+refine per suspect span (windowed re-align; 0-5 spans/song) |
| transcribe (no lyrics, 3 songs) | transcribe + refine |

Structural notes (no measurement needed):

- The cue route's whole-song transcribe is not consumed by the cue aligner, but
  it is the de-reverb gate's input and the song's only heard-words record (movie
  subtitle checks, LRC timing report; Ken 2026-10-29 wants heard words kept for
  every song -- open-issues "Heard words only live in the alignment bundle").
- On a re-sectioned cue song the first section pass is used only by
  `fit_offset`; its refine work is discarded.
- A rescued cue line's section-pass refine is discarded when the one-line
  re-align replaces it.
- `RefineKwargs`: `steps="s"`, `word_level=True`; stable-ts defaults otherwise
  (`precision=0.1`). stable-ts says lower precision costs more time; a coarser
  `precision` is untested.

## Method

`scripts/probe_refine_ablation.py` drives the stage's own `_run_cue_align` /
`_run_joint` with an in-process worker stand-in (stable-ts 2.19.1,
large-v3-turbo, RTX 2060 6 GB, app stopped). Each align result is cached by
(slice audio md5, text): the ON arm runs align then refine, and the OFF arm
reuses the pre-refine words, so the arms differ only by refine. Any slice the
OFF arm needs that ON never ran is aligned fresh. Transcribe words come from
each song's bundle. Post-steps mirror `run()`: evidence veto (joint) then
`snap_line_edges`. LRCLIB fill was skipped. Nothing was written to the library.

Sample: 9 cue + 5 joint songs, picked to include the June study's align-heavy
songs (In Summer, Be Our Guest, Hakuna Matata, A Whole New World) and a spread
of genres. None had a de-reverb stem.

Fidelity: ON-arm final line starts vs the song's bundle `output_line_timings`
(`bundle dmax`). 10 songs at 0.00-0.14 s. Four differ: A Whole New World 2.32,
Golden 0.98, Be Our Guest 0.46, I Want It That Way 0.45. These bundles predate
code changes since their last regen, or the runs are nondeterministic; not
chased.

Raw per-song results: `scripts/refine_ablation_results/*.json` (each holds the
song stem, both arms' pre-snap and final line/word timings, per-arm align and
refine seconds, and the bundle timings; no lyric text). Tables below:
`python scripts/probe_refine_ablation_report.py`.

## Results (2026-11-11)

### 1. Cost and movement (final timings, after edge snap)

`line d` = |ON - OFF| line start; `word d` = |ON - OFF| start of interior
words (word 0 excluded, it is the snapped line start), on lines where both arms
timed the same word count. Refine % = refine / (align + refine) seconds.

```
cue_a Adele - Someone Like You                 lines= 56 bundle dmax= 0.00 | refine 133.6s align  27.1s (83%) | line d med 0.000 p90 0.367 >0.15: 11 >0.5: 5 >1: 3 | word d p90 0.480 >0.25:26%
cue_a Aladdin (2019) - A Whole New World       lines= 54 bundle dmax= 2.32 | refine 137.6s align  27.4s (83%) | line d med 0.012 p90 0.830 >0.15: 14 >0.5: 8 >1: 4 | word d p90 0.483 >0.25:30%
cue_a Backstreet Boys - I Want It That Way     lines= 59 bundle dmax= 0.45 | refine 106.4s align  22.6s (82%) | line d med 0.000 p90 0.538 >0.15: 16 >0.5: 6 >1: 1 | word d p90 0.465 >0.25:19%
cue_a Beauty and the Beast (1991) - Be Our Gue lines= 92 bundle dmax= 0.46 | refine 122.7s align  28.8s (81%) | line d med 0.000 p90 0.145 >0.15:  9 >0.5: 1 >1: 0 | word d p90 0.115 >0.25:6%
cue_a Justin Timberlake - Selfish              lines= 79 bundle dmax= 0.00 | refine  91.8s align  19.6s (82%) | line d med 0.000 p90 0.495 >0.15: 18 >0.5: 7 >1: 1 | word d p90 0.165 >0.25:9%
cue_a Ne-Yo - Miss Independent                 lines= 75 bundle dmax= 0.00 | refine  97.5s align  34.1s (74%) | line d med 0.000 p90 0.290 >0.15:  9 >0.5: 4 >1: 2 | word d p90 0.155 >0.25:8%
cue_a Rent (2005) - Seasons of Love            lines= 33 bundle dmax= 0.14 | refine  77.8s align  14.7s (84%) | line d med 0.000 p90 0.700 >0.15:  6 >0.5: 4 >1: 3 | word d p90 0.420 >0.25:24%
cue_a The Last Five Years (2014) - The Next Te lines= 58 bundle dmax= 0.05 | refine 110.4s align  23.4s (83%) | line d med 0.000 p90 0.458 >0.15:  7 >0.5: 5 >1: 4 | word d p90 0.435 >0.25:28%
cue_a The Lion King (1994) - Hakuna Matata     lines= 96 bundle dmax= 0.02 | refine 157.1s align  37.1s (81%) | line d med 0.000 p90 0.260 >0.15: 13 >0.5: 5 >1: 1 | word d p90 0.195 >0.25:9%
joint Backstreet Boys - Chances                lines= 43 bundle dmax= 0.05 | refine  42.2s align  10.6s (80%) | line d med 0.000 p90 0.000 >0.15:  2 >0.5: 1 >1: 0 | word d p90 0.100 >0.25:6%
joint Eminem - Lose Yourself                   lines= 87 bundle dmax= 0.00 | refine  58.8s align  17.0s (78%) | line d med 0.000 p90 0.000 >0.15:  1 >0.5: 0 >1: 0 | word d p90 0.000 >0.25:2%
joint Frozen (2013) - In Summer (Sing-Along)   lines= 31 bundle dmax= 0.00 | refine  36.3s align  11.5s (76%) | line d med 0.000 p90 0.020 >0.15:  2 >0.5: 0 >1: 0 | word d p90 0.160 >0.25:8%
joint KPop Demon Hunters (2025) - Golden       lines= 51 bundle dmax= 0.98 | refine  47.1s align  13.4s (78%) | line d med 0.000 p90 0.332 >0.15:  6 >0.5: 2 >1: 0 | word d p90 0.120 >0.25:5%
joint Wicked (2003) - Popular                  lines= 55 bundle dmax= 0.00 | refine  56.0s align  12.2s (82%) | line d med 0.000 p90 0.192 >0.15:  6 >0.5: 4 >1: 2 | word d p90 0.175 >0.25:8%
```

The whole-song transcribe pass was not timed (it was replayed from bundles).

### 2. Transcriber witness -- not an independent reference

For words the arms place > 0.25 s apart: distance of each arm's start to the
nearest same-text word in the bundle's `transcribe_words` (within 1.5 s).

```
POOLED cue_align: n 414 refine closer  51 off closer 356 tie 7 med err on 0.39 off 0.03
POOLED joint:     n  89 refine closer  20 off closer  68 tie 1 med err on 0.34 off 0.02
```

The OFF arm sits 0.01-0.05 s (per-song medians) from the transcriber, i.e.
align and transcribe share whisper's word-timing behaviour, and refine is the
step that departs from it. This comparison cannot tell which is right. Per-song
rows: report section 2.

### 3. Shift direction; cue line starts vs uploader cues

Signed refine shift (ON - OFF) of words moved > 0.25 s; and, cue route only,
for lines whose start moved > 0.3 s, distance of each arm to the uploader cue
start plus the fitted display lead (`joint_stats.offset_s`; 0 when the song
re-sectioned, since its spans are pre-shifted).

```
cue_a Adele - Someone Like You                 words moved>0.25:   80, refine later  99%, med shift +0.41s | lines moved>0.3s:  8 closer-to-cue on/off/tie 6/0/2 med err on 0.15 off 1.23
cue_a Aladdin (2019) - A Whole New World       words moved>0.25:   66, refine later  85%, med shift +0.40s | lines moved>0.3s: 13 closer-to-cue on/off/tie 7/5/1 med err on 0.23 off 0.28
cue_a Backstreet Boys - I Want It That Way     words moved>0.25:   53, refine later  96%, med shift +0.47s | lines moved>0.3s: 12 closer-to-cue on/off/tie 3/8/1 med err on 0.50 off 0.19
cue_a Beauty and the Beast (1991) - Be Our Gue words moved>0.25:   32, refine later  97%, med shift +0.37s | lines moved>0.3s:  7 closer-to-cue on/off/tie 3/4/0 med err on 0.41 off 0.22
cue_a Justin Timberlake - Selfish              words moved>0.25:   49, refine later 100%, med shift +0.39s | lines moved>0.3s: 15 closer-to-cue on/off/tie 10/5/0 med err on 0.30 off 0.22
cue_a Ne-Yo - Miss Independent                 words moved>0.25:   34, refine later  88%, med shift +0.44s | lines moved>0.3s:  7 closer-to-cue on/off/tie 1/6/0 med err on 0.69 off 0.29
cue_a Rent (2005) - Seasons of Love            words moved>0.25:   48, refine later 100%, med shift +0.42s | lines moved>0.3s:  6 closer-to-cue on/off/tie 6/0/0 med err on 0.33 off 0.87
cue_a The Last Five Years (2014) - The Next Te words moved>0.25:   77, refine later  97%, med shift +0.41s | lines moved>0.3s:  6 closer-to-cue on/off/tie 4/2/0 med err on 0.47 off 0.68
cue_a The Lion King (1994) - Hakuna Matata     words moved>0.25:   37, refine later  78%, med shift +0.47s | lines moved>0.3s:  8 closer-to-cue on/off/tie 5/3/0 med err on 0.61 off 0.42
joint Backstreet Boys - Chances                words moved>0.25:   22, refine later  86%, med shift +0.38s
joint Eminem - Lose Yourself                   words moved>0.25:   13, refine later 100%, med shift +0.36s
joint Frozen (2013) - In Summer (Sing-Along)   words moved>0.25:   15, refine later  93%, med shift +0.36s
joint KPop Demon Hunters (2025) - Golden       words moved>0.25:   18, refine later  94%, med shift +0.35s
joint Wicked (2003) - Popular                  words moved>0.25:   27, refine later  96%, med shift +0.39s
POOLED words moved 571 later 94% med +0.40s
POOLED cue lines 82 on/off/tie [45, 33, 4] med err on 0.35 off 0.34
```

`onset_snap.py` documents whisper word onsets as smearing early, which is
the direction refine corrects. A consistent +0.4 s is also what an overshoot
would look like. No word-level ground truth exists in the corpus (as in June:
every reference is start-only).

## Open decision (Ken)

1. **Joint route: refine off?** Saves the per-song figure in table 1 (36-59 s
   here, plus the windowed re-align spans). Output moves little.
2. **Cue route: refine off?** Saves 78-157 s/song here, and moves word timing
   substantially, mostly later by ~0.4 s. Accuracy undecided.
3. **Untested middle:** a coarser `RefineKwargs.precision` (stable-ts default
   0.1 s) to cut refine time without dropping it.

Small, certain waste (re-sectioned songs' first-pass refine; rescued lines'
section refine) is recorded above but would need the worker to split align from
refine; not proposed.

## Next step

A/B listen: render both arms' `.ass` for 2-3 cue songs with the most movement
(Adele - Someone Like You, Rent - Seasons of Love, Backstreet Boys - I Want It
That Way) outside the library, and play each against the video. The probe keeps
timings only; rendering needs a rerun that keeps the arms' line objects (about
2-3 min GPU per song). Stop after the listen and record Ken's verdict here.
