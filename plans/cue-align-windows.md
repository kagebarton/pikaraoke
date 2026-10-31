Model: Claude Opus 5.5 (author, 2026-10-31). Executor: Claude Sonnet 5.5. GATE A: the
executor, against its pass criteria; Opus if any criterion fails. GATE B: Ken.

# Cue-align windows and quality stats

## Goal

Cue align loses the end of a line when the singer holds it past the window the
aligner is given. Ken heard two: Colors of the Wind's last line shows "You can paint
with all the" (no "colors of the wind"), and Incomplete at 0:45 shows "Where I'm going
is" (no "anybody's guess"). The same thing happens on 33 lines across 25 songs (Library
facts). Ken wants:

1. **Windows as correct as possible**, so the aligner finds the words itself, rather
   than post-processing guessing them.
2. **Two quality stats on Song Info for cue-align songs**, replacing the "Timed 100%"
   that every cue song shows today:
   - **stat 1**: words shown without measured timing (today: words missing from the
     screen);
   - **stat 2**: how each line was timed (aligned, re-aligned on its own, or evenly
     spaced from its caption).

## Decisions

Ken, 2026-10-31:

1. **Stats 1 and 2 now.** The squeezed-words stat and the agreement-with-transcription
   stat are out of scope (the latter waits on the heard-words file in
   `plans/open-issues.md`).
2. **Windows from the audio, not assumed.** Block edges are placed using the vocal
   stem's volume, so the aligner sees the whole held note.
3. **If the aligner still cannot time a word, show it**, with guessed timing, counted
   by stat 1. Never drop a word from the screen.
4. **Check on a GPU subset only**: the 9 songs in "Test songs", not the library.
5. **Consider a bigger 0.75 s pad, if it does not hurt the rescue lines.** Ruled
   (Opus, this plan): `SECTION_PAD_S` stays 0.75 s but is now measured from where the
   singing stops instead of from the caption's end time. The one-line rescue window
   keeps 0.75 s too: a wider one-line slice takes in more of the neighbouring lines'
   singing, so more rescues would land on the wrong audio, be rejected by the
   "landed where aimed" check and end up evenly spaced. That is reasoning, not a
   measurement. Revisit only if GATE A shows many edges falling back to the old rule.
   The re-section threshold (`align_song`, `abs(offset) > pad_s`) stays tied to
   `SECTION_PAD_S`; raising the pad would have stopped re-sectioning Drowning and
   That's The Way It Is (leads -0.92 s and -0.91 s).

Opus, this plan, stated so the executor need not re-derive them:

6. **No schema bump.** New bundle keys are additive and read with `.get`; bumping
   `SCHEMA_VERSION` would mark every song `behind`.
7. **Stat 2 counts evenly spaced lines as guessed.** `SongStatus.guessed` for a
   cue-align song becomes lines with no words plus `joint_stats.repace.n_repaced`. On
   today's bundles this moves one song onto the `poor` list (Your Idol, 9 of 59 paced,
   15.3% against `POOR_GUESSED_SHARE` 0.15). Get Down (17 of 114, 14.9%) stays off.
8. **The song's head edge is unchanged.** All 33 drops are line tails; nothing shows
   a clipped first word. The first section keeps `start - pad`.
9. **She Used To Be Mine 0:35 is a different bug** (the aligner ran ~2 s ahead
   mid-block with every word timed). Out of scope; its open-issues entry stays.
10. **Pocahontas keeps its current sheet for the test.** Its `.lrclib.srt` (built
    2026-10-29, before `8dabf55`) ends the last cue after a 4 s hold instead of at the
    LRC's 3:15 closing stamp. Re-making the sheet would mask whether the window fix
    works. Do not Repair it during this plan.

## Library facts (2026-10-31, `dev` at `daf183a`)

Read-only probes over `~/pikaraoke-songs/alignment_debug/*.json` (scratch scripts by
Opus, not committed; Phase 2's probe reproduces what matters).

- 90 bundles are `method_used == "cue_align"`. 22 of them have no `transcribe_words`:
  processed before `ddb1dcc` (2026-10-29), which started saving the cue route's
  transcript. A Regenerate fills them.
- **Dropped words**: 33 lines in 25 songs show fewer words than their lyric line
  tokenises to (`output_line_timings[].n_words` against
  `joint_match._tokenise_lines(lyrics.align_lines)`). In every one the missing words
  are the line's tail. 31 of 33 are the last line of their section
  (`segment_by_gaps` re-run on the bundle's cue spans); 2 are mid-section (My Heart
  Will Go On L9, Moving Too Fast L88).
- Mechanism: `split_section_to_lines` keeps a line whose aligned words cover
  `>= MIN_LINE_COVERAGE` (0.5) of its tokens, rendering only the matched words;
  `repace_bad_lines` never sees it as bad (`_line_is_clean` checks gaps and instant
  words, not coverage). The section window ends at cue end + `SECTION_PAD_S`, so a
  word sung past that has no audio to align to.
- Three groups, from the transcript where one exists:
  - **Held into silence** (gap after the line > 1.5 s): Pocahontas L36 (heard last
    word ends 5.3 s past the window), Incomplete L3 (+0.9 s), Inconsolable L32
    (+2.4 s), Stronger L6 (+1.8 s), Baby One More Time L30 (+1.2 s), Girlfriend L54
    (+0.9 s). Half the gap would not have covered Stronger, Girlfriend or Baby One
    More Time, so a bigger fixed pad is not enough.
  - **Tight gap or 60 s cap split** (gap <= 1.5 s, singing runs to the next line):
    Shape Of My Heart L29 ("my heart" heard to 132.96, window ends 132.44, next line
    133.27), plus 8 more lines.
  - **Not the window**: Castle On The Hill L46 ("my way" heard 227.9-228.9 inside a
    window ending 229.74), One In A Million L7 (third "come on" inside the window),
    My Heart Will Go On L9 (mid-section; "my heart" ends the line and starts the next,
    and the word split gave the words to L10).
- `edge_snap.end` (`onset_snap.snap_line_ends`) runs after cue align on every route
  and extends a line-final word to the measured vocal release, bounded by the next
  line's first word. Phase 4's guessed words rely on it.

## Test songs (GPU subset, Phase 5)

The 18 cut-off lines across these 9 songs are the targets; every other line in them
is the regression check. Pattern for `--song` is the YouTube ID.

| Song | ID | Cut-off lines (L = line id) | Group | Transcript |
|---|---|---|---|---|
| Britney Spears - Stronger | `AJWtLf4-WWs` | 6, 26, 32, 37 (9 words) | held into silence | yes |
| John Legend - All of Me | `450p7goxZqg` | 29, 46, 49 (6 words) | held into silence | no |
| Adele - Someone Like You | `hLQl3WQQoQ0` | 16, 33, 49 (4 words) | held into silence; same line text 3 times | no |
| Britney Spears - ...Baby One More Time | `C-u5WLJ9Yk4` | 20 (cap split), 30 | both | yes |
| Ne-Yo - Miss Independent | `k6M5C-oKw9k` | 9, 71 (cap split) | both | yes |
| Pocahontas - Colors of the Wind | `9ThO76peOw0` | 36 (last line, 4 words) | held into silence; Ken heard it | yes |
| Backstreet Boys - Incomplete | `WVe80iZtlYU` | 3 | held into silence; Ken heard it | yes |
| Ed Sheeran - Castle On The Hill | `K0ibBPhiaG0` | 46 | not the window | yes |
| Céline Dion - My Heart Will Go On | `9bFHsd3o1w0` | 9 (mid-section) | not the window | yes |

## Design

### Stats (`pikaraoke/lib/library_status.py`, `pikaraoke/routes/song_info.py`, `pikaraoke/templates/song_info.html`)

`SongStatus` gains, for `method == "cue_align"` only (None otherwise):

- `cue_lines: dict | None`: `{"aligned", "realigned", "paced"}` from
  `joint_stats.repace` (`n_realigned`, `n_repaced`; aligned = lines with words minus
  both).
- `words_guessed: int | None` and `words_guessed_lines: int | None`: from
  `joint_stats.repace.n_guessed_words` / `guessed_word_line_ids` when present (bundles
  written after Phase 4).
- `words_missing: int | None` and `words_missing_lines: int | None`: for older bundles
  only, derived as above (tokens minus `n_words`, lines with words only). After
  Phase 4 this is always 0, so a bundle carries one or the other.

`guessed` (Decision 7) adds `cue_lines["paced"]` for cue songs.

Song Info:

- **Timed tile** (`_timed_tile`): percent from `line_count - guessed` as today; the
  sub-line keeps "n guessed" and adds "· m words" when words are missing or guessed.
  Warn when words are missing (old bundle) as well as when `poor`.
- **Alignment tab** (`_alignment`): cue songs get three segments instead of one
  "Timed": "Aligned", "Re-aligned" ("timed again on its own"), "Spaced from caption"
  (`_GUESSED_COLOR`). Beneath the bar, one line when non-zero: "m words in n lines are
  missing from the screen. Regenerate to show them." (old bundles) or "m words in n
  lines have guessed timing." (new). Reuse the existing segment colours; add none
  unless a segment would otherwise share a colour with a neighbour.
- Tokenising for `words_missing` uses `joint_match._tokenise_lines`, the same function
  cue align used, so the counts agree with what was aligned.

### Block edges from the vocal volume (`pikaraoke/lib/cue_align.py`)

`segment_by_gaps` and `align_song` gain `env: np.ndarray | None` (a dB envelope from
`onset_snap.rms_envelope_db`, one value per `onset_snap.HOP_S`). With `env=None`
everything behaves exactly as today. With an envelope, section *grouping* is unchanged
(caption gaps over `SECTION_GAP_S`, then `_split_oversized`); only the window edges
move:

- **Between two sections** (last line `a` of one, first line `b` of the next): search
  `R = [cue_end(a) - EDGE_SEARCH_SLACK_S, cue_start(b) + EDGE_SEARCH_SLACK_S]`
  (start at 0.5 s). The sung reference is the louder of `a`'s and `b`'s, each the
  `onset_snap.SINGLE_WORD_REF_PCT` percentile of `env` over its cue span (no words
  exist yet, so the single-word reference is the one that fits). A frame is quiet when
  it is at least `QUIET_DIP_DB` below that reference (start at
  `onset_snap.SUSTAIN_NEAR_DB`, 12 dB). Take the longest run of consecutive quiet
  frames lasting at least `MIN_QUIET_S` (start 0.1 s). Then the earlier section's `t1`
  is the run's start + `SECTION_PAD_S`, the later section's `t0` is the run's end -
  `SECTION_PAD_S`, each clamped to the run's midpoint so windows never overlap. No
  qualifying run: today's rule for that edge (count it as a fallback).
- **Song tail** (last section): from `cue_end(last) - EDGE_SEARCH_SLACK_S` to
  `duration`, the first quiet run lasting at least `TAIL_QUIET_S` (start 0.5 s); `t1`
  is its start + `SECTION_PAD_S`, capped at `duration`. None: `duration`.
- **Song head**: unchanged (Decision 8).

Put the edge search in one helper used by both cases; keep the module pure (the
envelope is passed in, never decoded here). New constants get a comment saying what
they guard against, as the module's existing constants do.

`align_song` passes `env` to both `align_pass` calls (the re-section pass shifts the
cues first, as today), and hands the final pass's sections to `repace_bad_lines`
(next section). `stats` gains `edges: {"n": ..., "measured": ..., "fallback": ...}`.

### Stage wiring (`pikaraoke/pipeline/stages/lyric_align.py`)

`_run_cue_align` decodes the envelope with `decode_env_db` from the stem the de-reverb
gate chose (the same file the edge snap later uses: `ctx.artifacts["aligned_stem"]`
after the gate) and passes it to `align_song`. The decode at `lyric_align.py:197`
reuses that envelope instead of decoding the file again; one decode per song, as now.
A failed decode passes `env=None` (today's windows) and is logged, as the snap's
decode is.

### Partial lines (`repace_bad_lines`, `pikaraoke/lib/cue_align.py`)

- A line with tokens is **bad** when it has fewer words than tokens, in addition to
  today's tests. It goes through the existing rescue: one-line re-align
  (`realign_line`) first.
- **Rescue window**: as today (offset-corrected cue span, padded by `SECTION_PAD_S` in
  `realign_line`), except that for the last line of a section the window's end is at
  least that section's `t1`, so a held tail is inside the slice. The "landed where
  aimed" check (`_line_in_span`) tests against the window actually aimed at, so a
  correctly found held tail is not rejected for overrunning its caption.
- **Keep the better line**: the rescued line replaces the original only if it covers
  more tokens and passes the check; a rescued line covering every token is tagged
  `SOURCE_REALIGN` as today.
- **Guessed words (Decision 3)**: any token still without a word in a kept line gets
  one, placed between its timed neighbours in the line. A missing tail starts at the
  last timed word's end and is spaced at the line's own pace (its timed words' median
  duration, each capped at `MAX_WORD_DUR_S`), ending no later than the next line's
  first word or the section's `t1`, whichever is earlier; the edge snap then extends
  the last word to the measured release. A missing head mirrors that, starting no
  earlier than the previous line's last word. Display text keeps the lyric's own words
  (the token's raw form, as `split_section_to_lines` does).
- Lines under `MIN_LINE_COVERAGE` keep today's path (re-align, else even spacing from
  the cue).
- `repace` stats gain `n_guessed_words` and `guessed_word_line_ids`.
- Update the module docstring's "Approach" step 3 to say partial lines are rescued.

## Phases

### Phase 0: branch and baseline

Branch `cue_align_windows` off `dev` at `daf183a` (created by Opus, with this plan
untracked). Baseline suite: 2998 passed in 37.78 s. Record both in the Results log.

### Phase 1: stats 1 and 2 -> commit

Build "Stats". Tests in `tests/unit/test_library_status.py` and the Song Info route
tests (`tests/unit/test_library_routes.py` holds Song Info today): a cue bundle with
paced and re-aligned lines; an old bundle with missing words (counts and the warn);
a bundle with `n_guessed_words`; a joint bundle unchanged; the `poor` threshold
with paced lines. Smoke: `overview_counts(library_statuses(~/pikaraoke-songs))` read
only, and record the `poor` list before and after (expect Your Idol to join, nothing
else). Commit: `feat(song_info): cue-align songs show how each line was timed and
words missing`.

### Phase 2: edge placement + CPU probe -> GATE A

Write the edge helper and `segment_by_gaps(env=...)` with unit tests on synthetic
envelopes (numpy arrays): a hold past the caption into silence; a 0.3 s breath
between back-to-back lines; continuous singing (no quiet run -> fallback, today's
windows); the song tail; quiet runs never overlapping; `env=None` identical to today
on the existing tests.

Then a **read-only CPU probe** (scratch script, not committed; no GPU, no writes to
the library). For every cue-align bundle: decode the stem (`dereverb/<stem>---dereverb.m4a`
when `joint_stats.dereverb.succeeded`, else `vocal/<stem>---vocal.m4a`) with
`rms_envelope_db`; rebuild the cue spans from `lyrics.source_path` (replace `\` with
`/`: Windows-written bundles) with `cue_spans_from_srt`, shifted by `offset_s` when
`resectioned`; compute old and new sections. Report per song: edges, edges moved,
fallbacks, and, for songs with a transcript, each section-final line whose heard last
word (match its last token in `transcribe_words` within the cue span to the next cue)
ends outside the window, old vs new; and each section-first line whose heard first
word starts outside, old vs new.

**GATE A pass criteria** (the executor rules; stop for Opus if any fails):

1. Every section-final cut-off line in the test songs that has a transcript
   (Stronger 6, 26, 32, 37; Baby One More Time 20, 30; Miss Independent 9, 71;
   Pocahontas 36; Incomplete 3; Castle 46) has its heard last word inside the new
   window. Where the probe's word match cannot find the word, say so; that line is
   not a failure.
2. Across the library, no section-first line whose heard first word was inside the
   old window falls outside the new one.
3. Fallback edges are at most 20% of all interior edges.

Tuning allowed before ruling: the four starting constants (`EDGE_SEARCH_SLACK_S`,
`QUIET_DIP_DB`, `MIN_QUIET_S`, `TAIL_QUIET_S`), within a factor of two of their start
values. Record every value tried and its counts in the Results log. If a criterion
still fails, or if cap-split edges in the test songs show no quiet run at all (the
cap chose a split point inside continuous singing), stop for Opus: choosing the cap
split by volume is the candidate next step, not built here.

### Phase 3: wire the edges in -> commit

`align_song(env=...)`, the stage decode-once wiring, the `edges` stats.
`tests/unit/test_cue_align.py`: `align_song` with a stub aligner and an envelope moves
the tail window and records the stats; `env=None` unchanged. `tests/unit/test_lyric_align.py`:
the cue route decodes once and passes the envelope; a failed decode passes None and
the song still completes. Commit (with Phase 2's helper and tests): `feat(cue_align):
block edges follow the vocal volume, not the caption gaps`.

### Phase 4: partial lines -> commit

Build "Partial lines". Tests: a line missing its tail at a section end is re-aligned
over a window reaching the section's `t1` and kept when it covers more; a re-align
covering less is discarded and the original kept with guessed words; guessed tail,
head and middle words (placement, cap, bounds); a fully covered rescued line is tagged
`SOURCE_REALIGN`; stats counts; a line under `MIN_LINE_COVERAGE` takes today's path;
a display-only line untouched. Update `library_status` tests if Phase 1 needs the new
key's real shape. Commit: `fix(cue_align): a line is never shown with words missing`.

### Phase 5: GPU subset -> GATE B (Ken)

Ask Ken before starting (the app must be stopped: the CLI runs its own GPU workers).
Then, from the repo root:

```bash
/home/ken/miniconda3/envs/pik/bin/python scripts/regen_alignment_bundles.py \
  --song AJWtLf4-WWs --song 450p7goxZqg --song hLQl3WQQoQ0 --song C-u5WLJ9Yk4 \
  --song k6M5C-oKw9k --song 9ThO76peOw0 --song WVe80iZtlYU --song K0ibBPhiaG0 \
  --song 9bFHsd3o1w0 --dry-run
```

Read the dry run, then run without `--dry-run`. The script backs up the 9 songs'
files into `regen_backup_<UTC>/` first: that is the "before". Confirm Pocahontas's
`lyrics/<stem>.lrclib.srt` is byte-identical before and after (Decision 10).

Compare (scratch script, not committed), per song: target lines' words shown before
and after, and their timing source (aligned / re-aligned / guessed words); every
other line whose start or end moved more than 0.3 s, with before, after, and the
transcriber's heard time for its first and last word; the new `edges` and `repace`
stats; the Song Info stats. Put the raw tables in the Results log.

**GATE B (Ken)**: Ken plays the 18 target lines and a sample of moved lines. Give him
a list as `song - m:ss - line text - what changed`, targets first. Ken's ruling goes
in Decisions.

### Phase 6: after GATE B

Only on Ken's word: land on `dev` (Branches and Archive Tags in `CLAUDE.md`: copy the
code commits one by one, no plan file), then in `plans/open-issues.md` on `dev`, record
what remains (e.g. any test line still guessed, the not-the-window group, the
remaining 16 songs needing a Regenerate), and retire the branch as
`archive/cue_align_windows`.

## Rules for the executor

- `CLAUDE.md` applies in full: conda env `pik`, pytest with mocked I/O, pre-commit on
  changed files only, Self-Review before each commit, no debug prints, commits grouped
  by feature with their tests.
- No GPU outside Phase 5, and Phase 5 only after Ken says go.
- The library at `~/pikaraoke-songs` is read-only until Phase 5.
- Do not re-derive the Library facts; they are measured. Do not touch the
  She Used To Be Mine issue (Decision 9).
- Results log rows are raw: commands, counts, constants, hashes. No verdicts; a
  surprise is recorded as what was seen.
- `graphify affected "<symbol>"` before changing `repace_bad_lines`,
  `segment_by_gaps`, `align_song` and `SongStatus`, to find callers and tests; run
  `graphify update .` after code changes.
- Stop and ask when the code contradicts this plan; record the contradiction.

## Checkpoints

After each commit, per `CLAUDE.md`. A review is due after Phase 4 (multi-file, core
pipeline): offer the `/code-review` line with the range from the Phase 1 commit's
parent to HEAD, files `pikaraoke/lib/cue_align.py`,
`pikaraoke/pipeline/stages/lyric_align.py`, `pikaraoke/lib/library_status.py`,
`pikaraoke/routes/song_info.py`, `pikaraoke/templates/song_info.html` and their tests,
and three finders: correctness (window edges never overlap and never clip a sung word;
guessed-word bounds), simplicity (one edge helper, no duplicate reference-level code
beside `onset_snap`), robustness (decode failure, empty or short envelopes, a song
whose last cue overruns the media). Never launch it unprompted.

## Results log

| Row | Date | Phase | What | Result |
|---|---|---|---|---|
| 1 | 2026-10-31 | 0 | `git branch --show-current`; `git rev-parse dev`; `git status --short` | branch `cue_align_windows`, HEAD = `dev` = `daf183a`; only `plans/cue-align-windows.md` untracked |
| 2 | 2026-10-31 | 0 | baseline: `/home/ken/miniconda3/envs/pik/bin/python -m pytest -q` | 2998 passed in 36.73 s |
| 3 | 2026-10-31 | 1 | probe `~/pikaraoke-songs/alignment_debug/*.json` (read only): cue bundles, `output_line_timings` entries with `n_words` 0, cue songs with `line_count != lines_with_words`, lines with `n_words` < tokens (`joint_match._tokenise_lines`) | 90 cue bundles; 0 entries with `n_words` 0; 0 cue songs with `line_count != lines_with_words`; 33 lines short, 65 words, in 24 songs (the plan's Library facts say 25 songs; lines match at 33) |
| 4 | 2026-10-31 | 1 | smoke: `library_statuses(~/pikaraoke-songs)`, `poor` by the old rule (`line_count - lines_timed`) vs the new `SongStatus.poor` | 103 songs. `poor` before 1, after 2; joined: Your Idol (9 paced of 59 = 0.1525). Left: none. Next highest: Get Down 17/114 = 0.1491, I'll Never Break Your Heart 13/91 = 0.1429, both stay off. `overview_counts`: behind 0, poor 2, no_lyrics 2, caption 76, movie 7, lrc 7, genius 8, custom 3, no_timed_source 1, all 103. Cue songs: 60 with paced lines (191 paced lines in all), 120 re-aligned lines; `words_missing` > 0 in 24 songs, 65 words in 33 lines |
| 5 | 2026-10-31 | 1 | `pytest -q tests/unit/test_library_status.py tests/unit/test_library_routes.py`, then full suite; `pre-commit run --config code_quality/.pre-commit-config.yaml --files <5 files>` | 499 passed; full suite 3011 passed in 37.10 s (+13 over baseline); black reformatted `song_info.py` and `test_library_status.py` on the first run, all hooks pass on the second. `test_a_caption_song` changed: its cue legend reads "Aligned 39", not "Timed 39" |

## Hand-off prompt (executor)

```
Execute plans/cue-align-windows.md on branch cue_align_windows (HEAD daf183a, plan
untracked). Read Goal, Decisions, Library facts, Design, Phases and Rules first. Start at
Phase 0, record the baseline, then Phase 1. Stop at GATE A if any pass criterion fails,
and before Phase 5's GPU run until Ken says go. Log every step in the Results log.
```
