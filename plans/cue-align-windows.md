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

Opus, GATE A ruling, 2026-10-31 (rows 14-20):

11. **Windows only grow; the edge rule is replaced.** The Phase 2 rule (longest quiet
    run, both windows clamped to its midpoint) failed criteria 1 and 2 for two
    measured reasons: the longest run is often a pause inside the held line (Stronger
    6, Baby One More Time 30), and moving the later window's start to the run's
    midpoint left it no lead-in (row 9). Ruled instead:
    - **The later section's start never moves.** Caption starts are the one caption
      time cue align trusts, and no first word has been seen clipped (Decision 8 now
      covers every section head, not just the song's).
    - **The earlier section's end moves later, never earlier**: `t1` is the larger of
      today's caption rule and the measured end. Measured end: `SECTION_PAD_S` into the
      first quiet stretch of at least `RELEASE_QUIET_S` (0.75 s) after the caption ends,
      clamped to the stretch's midpoint; if the singing never pauses that long before
      the next line's caption start, the window ends at that caption start. Stronger 6
      shows why (row 14): "own" runs right up to the next caption's start and the
      next line's "But" begins there.
    - **A hold is at most `MAX_HOLD_S` (4 s) past its caption.** Singing that goes on
      longer without a pause is other vocals (an uncaptioned part, ad-libs), not the
      line's tail; that edge keeps today's rule and counts as a fallback. Without the
      cap, windows grew up to 28 s across instrumental breaks, and no dropped-word line
      sings more than 3.7 s past its caption (rows 16, 20).
    - **Song tail**: the window ends `SECTION_PAD_S` after the vocal stem's last sung
      frame, capped at `duration`, with no hold cap. There is no next line to take
      audio from, and the song's end is where long holds live: Pocahontas holds "wind"
      to 190.3 (row 14), 11.5 s past its caption, and Whitney Houston's last line holds
      about 12 s past its caption. Accepted cost: outro speech the captions skip goes
      into the last window (Pop, Mulan; row 17).
    - Windows may now overlap, by at most the later window's caption pad (0.75 s),
      only where the earlier line is still singing. Duet cues already overlap by up
      to 5 s, and nothing downstream assumes line times don't overlap.
    - Criterion 2 holds by construction (no window loses audio). The plan's tuning
      allowance is superseded: `MIN_QUIET_S` and `TAIL_QUIET_S` are gone;
      `RELEASE_QUIET_S` and `MAX_HOLD_S` are new.

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
(caption gaps over `SECTION_GAP_S`, then `_split_oversized`), every `t0` is unchanged,
and each section's `t1` becomes the larger of today's and the measured end (Decision
11):

- **Sung level and quiet**: the sung reference is the louder of the two lines' levels,
  each the `onset_snap.SINGLE_WORD_REF_PCT` percentile of `env` over its cue span (no
  words exist yet, so the single-word reference is the one that fits); under
  `onset_snap.MIN_REF_DB` nothing is measured. A frame is quiet when it is at least
  `QUIET_DIP_DB` (`onset_snap.SUSTAIN_NEAR_DB`, 12 dB) below that reference.
- **Between two sections** (last line `a` of one, first line `b` of the next): over
  `[cue_end(a) - EDGE_SEARCH_SLACK_S, cue_start(b)]` (slack 0.5 s), the first quiet
  stretch lasting at least `RELEASE_QUIET_S` (0.75 s) is where `a` stopped: the
  measured end is its start + `SECTION_PAD_S`, clamped to its midpoint. No such
  stretch: `a` sang up to `b`, and the measured end is `cue_start(b)`. Either one
  further than `cue_end(a) + MAX_HOLD_S` (4 s), or no sung level: no measured end
  (fallback, today's rule).
- **Song tail** (last section): the measured end is `SECTION_PAD_S` after the last
  frame from `cue_start(last)` on that is not quiet, capped at `duration`. No sung
  level: fallback.
- **Song head**: unchanged (Decision 8).

Keep the module pure (the envelope is passed in, never decoded here). New constants get
a comment saying what they guard against, as the module's existing constants do.

`align_song` passes `env` to both `align_pass` calls (the re-section pass shifts the
cues first, as today), and hands the final pass's sections to `repace_bad_lines`
(next section). `stats` gains `edges: {"n": ..., "widened": ..., "fallback": ...}` for
the final pass: section ends, ends moved later than today's, and ends the volume could
not place. Absent when `env` is None.

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

First rework Phase 2's uncommitted edge code and its `TestSegmentByVolume` tests to
Decision 11: a hold into silence; singing straight into the next caption (window ends
at its start); a pause inside the held line shorter than `RELEASE_QUIET_S` is skipped;
a hold past `MAX_HOLD_S` falls back; a release before the caption end leaves today's
window; every `t0` unchanged; the tail reaching a long hold and capped at `duration`;
no sung level falls back; `env=None` identical to today. Re-run `final_rule.py`'s
figures through the committed `segment_by_gaps` (scratch) and record them.

Then `align_song(env=...)`, the stage decode-once wiring, the `edges` stats.
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
transcriber's heard time for its first and last word; lines whose first word starts
before the previous line's last word ends, before and after (Decision 11 lets windows
overlap; a next line whose start smeared back into a now-found held tail shows up
here, e.g. Stronger 7, whose "But" sits at its window start 50.44 while the sung
"But" begins about 51.2); the new `edges` and `repace` stats; the Song Info stats.
Put the raw tables in the Results log.

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
| 6 | 2026-10-31 | 2 | code in `pikaraoke/lib/cue_align.py`: `segment_by_gaps(..., env=None)`, `_volume_edge`, `_volume_tail`, `_quiet_run`, `_loudest_sung_level` (calls `onset_snap._sung_level_ref` once per cue span as a one-word line, so the 80th-percentile reference is not re-implemented; levels under `MIN_REF_DB` count as no singing), `_section_starts` (the grouping code moved out of `segment_by_gaps`), `Section.measured_end` (`compare=False`). Constants EDGE_SEARCH_SLACK_S 0.5, QUIET_DIP_DB = `SUSTAIN_NEAR_DB` (12.0), MIN_QUIET_S 0.1, TAIL_QUIET_S 0.5. Tail: quiet found -> its start + pad; singing measured but never 0.5 s quiet -> `duration`; no singing measurable, or no `duration` -> today's rule. 16 new tests in `TestSegmentByVolume` | `pytest -q` 3027 passed in 37.01 s; pre-commit passes (black reformatted `cue_align.py`). Uncommitted in the working tree: Phase 3 commits it with the wiring |
| 7 | 2026-10-31 | 2 | read-only CPU probe, scratch (`probe_edges.py`, not committed): `PYTHONPATH=. python probe_edges.py`. 90 cue bundles; stem = `dereverb/` when `joint_stats.dereverb.succeeded` else `vocal/`; cues from `lyrics.source_path` (`\` -> `/`), shifted by `offset_s` when `resectioned`; duration = `media_duration_s`. Starting constants. Table R7 below | 90 probed, 0 errors. Interior edges 692; moved (> 0.01 s) 613; fallback 67 (9.7%). Tails measured 83/90. Overlapping window pairs 0; windows with t1 <= t0: 0. Measured edges ending before their own caption ends: 54. 68 songs have a transcript: 534 section-final lines, heard last word found for 394, outside the window old 55 -> new 34 (fixed 23, in old and out of new 2). Section-first lines 534, word found 374, outside old 97 -> new 116, in old and out of new 36. Cap-split edges (caption gap <= 1.5 s) 230, run found at 185; all cap-split edges in the 9 test songs found a run. Decode 60 s; later runs use cached envelopes, under 1 s |
| 8 | 2026-10-31 | 2 | the first probe run printed 0 for section-first lines in the old window and out of the new | cause: the comparison was `new_in is False` against numpy booleans, never true. Cast to `bool`, rerun: 36. Every first-line figure in this log is from the corrected probe; the 0 was wrong |
| 9 | 2026-10-31 | 2 | the 36 section-first lines (block R9 below). Env quiet: `env[heard_start : +4 frames].max() < loudest sung level - 12 dB` | env quiet at the heard first word: 26 of 36. New t0 within 0.3 s after `heard_start`: 29 of 36 |
| 10 | 2026-10-31 | 2 | tuning grid, in one process over the cached envelopes: slack {0.25, 0.5, 1.0} x dip {6, 9, 12, 18, 24} x min_quiet {0.05, 0.1, 0.2} x tail_quiet {0.25, 0.5, 1.0} = 135 cells (block R10 below) | criterion 1 (no target line outside): 0 cells. Criterion 2 (0 in old and out of new): 0 cells; lowest 16, at slack 0.25, dip 24, min_quiet 0.2, any tail_quiet (fallback 31.5% there). Criterion 3 (fallback <= 20%): 102 cells. Stronger 6 and Pocahontas 36 are outside in all 135 cells. Fewest target lines outside is 3, in 81 cells: Stronger 6 and Pocahontas 36 plus Baby One More Time 30 (54 cells) or Baby One More Time 20 (27 cells) |
| 11 | 2026-10-31 | 2 | envelope around the three target lines outside at the starting constants (`probe_line.py`; dB every 0.25 s; sung level ref -19.5 / -17.6 / -19.8, quiet below ref - 12) | **Pocahontas L36** (last line, cue 174.84-178.84; heard `of` 179.68-181.48, `the` 181.48-183.04, `wind` 183.04-184.92): 178.84 -21, 179.09 -42, 179.34 -26, 179.59 -31, 179.84 -36, 180.09 -40, 180.34 -54, 180.59 -66, 180.84 -31, 181.09 -30 ... 183.34 -41, 183.59 -66, 183.84 -69, 184.09 -64, 184.34 -93, 184.59 -110, 184.84 -30, 185.09 -27. Tail window ends 180.375. **Stronger L6** (cue 43.56-48.56, next cue 51.19; heard `own` 50.22-51.1, next line `But` 51.1): 48.56 -37, 48.81 -24, 49.31 -35, 49.56 -34, 49.81 -25, 50.06 -22, 50.31 -39, 50.56 -21, 51.06 -24, 51.31 -28. Window ends 49.488. **Baby One More Time L30** (cue 161.26-166.26, next cue 169.70; heard `now` 167.36-168.20, next `Don't` 169.56): 165.51 -33, 165.76 -41, 166.01 -56, 166.26 -23, then -17..-28 to 169.26, 169.51 -33. Window ends 165.962 |
| 12 | 2026-10-31 | 2 | scratch variants of the edge rule at the starting constants (`variants.py`; monkeypatched, not in the committed code; not within the plan's tuning allowance): (a) last qualifying run in R instead of the longest; (b) (a) with windows only moving outward from today's (t1 = max(new, old), t0 = min(new, old)); (c) longest run with the same outward-only rule | (a) fallback 9.7%; section-final outside old 55 -> 31 (in old and out 2); section-first outside 97 -> 161 (in old and out 76); target lines outside: Pocahontas 36 only. (b) section-final outside 55 -> 30 (1); section-first 97 -> 85 (0); target lines outside: Pocahontas 36 only; window pairs overlapping 353. (c) section-final 55 -> 33 (1); section-first 97 -> 80 (0); target lines outside: Baby One More Time 30, Stronger 6, Pocahontas 36; overlapping pairs 293 |
| 13 | 2026-10-31 | 2 | GATE A against the pass criteria, starting constants | Criterion 1: not met (Baby One More Time 30, Stronger 6, Pocahontas 36 outside; Stronger 26, Miss Independent 9 and 71: word not found by the match). Criterion 2: not met (36). Criterion 3: met (9.7%). Cap-split edges with no quiet run in the test songs: none. Stopped for Opus; Phase 3 not started; Phase 2 code left uncommitted |
| 14 | 2026-10-31 | GATE A | Opus re-reads (scratch `envdump.py`, `pocatail.py`; envelopes from row 7's cache, 0.05-0.4 s steps). **Pocahontas L36**, all three stems + mix: 182.0-183.2 vocal -31..-39 / nonvocal -52..-67; 183.6-184.4 vocal -66..-120; 184.8-190.0 vocal -26..-31, nonvocal -32..-45, mix -24..-29; 190.4 vocal -64, 191.2 on -120, nonvocal -38..-47. YouTube ASR json3: `colors` 179.2-181.2, `of` 181.52-183.52, no `the`/`wind`. LRC last line `[03:01.22]`, closing `[03:15.01]`. **Stronger L6/L7**: current ASS L6 words end `make` 48.34-48.45, `it` 48.45-50.33 (`on my own` absent); L7 `But` 50.43-51.55, `now` 51.55-52.11, `I'm` 52.27-52.75; Whisper `own` 50.22-51.1, `But` 51.1-51.56, `now` 51.56-52.14; L7 window t0 50.44 (cue 51.19 - 0.75); envelope dip -34 at 51.6, no frame below ref - 12 dB between 50.35 and 51.55. **Baby One More Time L20/L21**: envelope dips 109.9-110.0 (-28..-34), 110.3 (-39), 111.0-111.25 (-31..-35); L21 cue 110.85; Whisper `my` 110.64 | the vocal stem is louder than the nonvocal stem over 184.8-190.0 and the mix follows it; vocal ends 190.4 |
| 15 | 2026-10-31 | GATE A | scratch `rules.py` (all rules start from today's windows and only widen them; `t1 = max(old, min(run_start + pad, run_mid))`, `t0 = min(old, max(run_end - pad, run_mid))`), starting constants. Extra metric "foreign words": transcribed words starting after the line's heard last word ends, inside the new window and outside the old | last run, search to next cue + 0.5: last_out 55 -> 29 (0 broken), first_out 97 -> 85 (0 broken), targets outside Pocahontas 36, foreign +188 (today's windows hold 86). Last run, search to next cue + 0.0: 55 -> 36, targets outside BOMT 20, Stronger 6, Pocahontas 36, foreign +90. Same with t0 fixed: first_out 97 -> 97, overlaps 174. Longest run + 0.5: 55 -> 32, targets outside BOMT 30, Stronger 6, Pocahontas 36, foreign +83. Interior growth max 63.30 s (last run) |
| 16 | 2026-10-31 | GATE A | scratch `run2.py`, `branch.py`: release rule = first quiet run >= R s in [cue_end(a) - 0.5, cue_start(b)], t1 = min(start + pad, mid); else t1 = cue_start(b) ("into_b"); t1 = max(old, t1); t0 unchanged; no hold cap | R 1.0, tail "final": last_out 55 -> 20 (0 broken), targets outside none, Pocahontas tail t1 190.9, 27 of 31 section-final dropped-word lines widened, interior widened 378/692 (p50 0.73 s, p90 2.60, max 28.14; 27 over 3 s), foreign interior +138 tail +21. Else = last breath before cue_start(b): 55 -> 25, targets outside BOMT 20, Stronger 6, foreign +93. R 0.75: 55 -> 21, foreign +121. R 1.5: 55 -> 20, max growth 49.53, foreign +153. Branch split at R 1.0: release 115 widened (3 dropped-word lines, max 28.14 at Mirrors L75, caption gap 50.28), into_b 263 widened (23 dropped-word lines, all with caption gap <= 3.72 s, growth <= 2.97 s; foreign 111, of which 60 the next line's first word). into_b with caption gap > 4 s: 12 edges, 0 dropped-word lines, growth up to 17.72 (Girlfriend L44) |
| 17 | 2026-10-31 | GATE A | scratch `tails.py`: tails growing > 2 s or taking in transcribed words, rule "final" (pad after the last sung frame) | 25 songs listed. Words taken in: Pop (`Thank you.`, t1 206.1 -> 232.75), Mulan (`Tap the I in the top right-hand`..., 224.3 -> 234.4); none elsewhere. Largest growth: Pop 26.6, My Heart Will Go On 17.0 (251.0 -> 267.95), Paradise 16.1, Whitney Houston 11.1 (259.5 -> 270.6), Pocahontas 11.3 (179.6 -> 190.9) |
| 18 | 2026-10-31 | GATE A | scratch `final_rule.py`: Decision 11 (release R, hold cap H on interior edges, tail = pad after the last sung frame), slack 0.5, dip 12 | R 1.0 H 4.0: interior 692, fallback 21 (3.0%), widened 357 (p50 0.67, p90 1.92, max 3.94); tails widened 39/90 (p50 2.40, max 26.64); overlapping pairs 279 (max 0.75); last_out 55 -> 24 (in old, out of new 0); 26 of 31 section-final dropped-word lines widened; foreign interior +100, tail +21. H 3.0: fallback 6.5%, last_out 26, 24 widened, foreign +74. H 6.0: fallback 1.4%, last_out 21, 27 widened, foreign +121. R 0.75 H 4.0: fallback 2.5%, last_out 23, 27 widened, foreign +85; same target results as R 1.0. R 1.5 H 4.0: fallback 3.6%, last_out 24, 27 widened, foreign +111 |
| 19 | 2026-10-31 | GATE A | Decision 11 at R 1.0 H 4.0 against the pass criteria | Criterion 1: Incomplete 3 (t1 45.182 -> 47.1, heard 46.04), BOMT 20 (110.255 -> 110.846, 110.64), BOMT 30 (167.01 -> 169.704, 168.2), Stronger 6 (49.312 -> 51.189, 51.1), Stronger 32 (181.539 -> 182.583, 180.384), Stronger 37 (207.382 -> 209.23, 206.8), Castle 46 (229.74 -> 229.74, 228.88), Pocahontas 36 (179.59 -> 190.9, 184.92; sung to 190.4 per row 14) inside; Stronger 26, Miss Independent 9 and 71: word not found by the match. Criterion 2: no t0 moves. Criterion 3: 3.0% |
| 20 | 2026-10-31 | 3 | `RELEASE_QUIET_S` 1.0 -> 0.75 after scratch `drops_unwidened.py` (real `segment_by_gaps(env=...)` over the 90 cue bundles) showed Inconsolable L32 unwidened: cue end 147.53, next cue 154.60; envelope sung to 151.1, quiet 151.1-152.05 (~0.9 s), sung 152.0-153.1 (Whisper `Yeah` 151.76-152.24), quiet 153.2-154.4; at 1.0 the first qualifying stretch starts 153.2, past `MAX_HOLD_S`. Then `verify_committed.py` (row 18's figures through the real code) at 0.75 | fallback 17/692 (2.5%), widened 343, t0 moved 0, tails fell back 5, tails widened 39; section-final heard last word outside old 55 -> new 23, in old and out of new 0; extra heard words +85; 27 of 31 section-final dropped-word lines widened; overlapping pairs 264; cap-split edges (caption gap <= 1.5 s) 230, fallback 0. Targets as row 19. Not widened, all measured: Stronger 26, Castle 46, Miss Independent 9, Last Five Years Climbing Uphill L75 (tail). Mid-section, out of reach of window ends: My Heart Will Go On L9, Moving Too Fast L88. At 1.0: fallback 21, widened 359, 26 of 31, extra words +100 |
| 21 | 2026-10-31 | 3 | commit `d83be7f` (`feat(cue_align): block edges follow the vocal volume, not the caption gaps`): Phase 2's helper reworked to Decision 11 (`_quiet_runs`, `_volume_end`, `_volume_tail`; `MIN_QUIET_S`, `TAIL_QUIET_S` removed; `RELEASE_QUIET_S` 0.75, `MAX_HOLD_S` 4.0 added), `align_song(env=...)`, `stats.edges` `{n, widened, fallback}` (final pass; absent without env), `_run_cue_align` decodes once after the de-reverb gate and returns the envelope, `run()` skips its own decode on the cue route. `TestSegmentByVolume` 13 cases, `TestAlignSong` +1, `TestCueAlignRoute` +2. `pytest -q`; pre-commit on the 4 files | 3027 passed in 36.83 s; black reformatted `cue_align.py` and `lyric_align.py` on the first run, all hooks pass on the second |
| 22 | 2026-10-31 | 4 | commit `0f5fdd9` (`fix(cue_align): a line is never shown with words missing`): `repace_bad_lines(sections=...)`, partial lines (placed, fewer words than tokens) rescued; realign aimed at `max(cue end + offset, section t1)` for a section's last line, containment checked against that end; a partial line keeps the realign only when it times more words; `_with_guessed_words` fills every token a kept line lacks; stats `n_guessed_words`, `guessed_word_line_ids`. The widened rescue window applies to every rescued section-last line, not only partial ones (the plan's "today's path" for lines under `MIN_LINE_COVERAGE` read as the realign-then-fill order); fills stay on the cue span. `TestPartialLines` 11 cases, `TestAlignSong` +1. `pytest -q`; pre-commit on the 2 files | 3039 passed in 36.99 s; black reformatted `cue_align.py` on the first run, all hooks pass on the second |

**R7 targets** at the starting constants (slack 0.5, dip 12, min_quiet 0.1, tail_quiet 0.5). `heard_end` is the transcriber's end of the line's last word.

| Song | L | last token | heard_end | old t1 | new t1 | in old | in new |
|---|---|---|---|---|---|---|---|
| Backstreet Boys - Incomplete (Of | 3 | guess | 46.04 | 45.182 | 47.1 | False | True |
| Britney Spears - ...Baby One Mor | 20 | because | 110.64 | 110.255 | 111.15 | False | True |
| Britney Spears - ...Baby One Mor | 30 | now | 168.2 | 167.01 | 165.962 | False | False |
| Britney Spears - Stronger (Offic | 6 | own | 51.1 | 49.312 | 49.488 | False | False |
| Britney Spears - Stronger (Offic | 26 | go | word not found | 147.224 | 146.612 | None | None |
| Britney Spears - Stronger (Offic | 32 | yesterday | 180.38 | 181.539 | 181.539 | True | True |
| Britney Spears - Stronger (Offic | 37 | more | 206.8 | 207.382 | 209.075 | True | True |
| Ed Sheeran - Castle On The Hill  | 46 | way | 228.88 | 229.74 | 229.65 | True | True |
| Ne-Yo - Miss Independent [Offici | 9 | damn. | word not found | 26.45 | 25.925 | None | None |
| Ne-Yo - Miss Independent [Offici | 71 | yeah | word not found | 219.283 | 218.913 | None | None |
| Pocahontas - Colors of the Wind  | 36 | wind | 184.92 | 179.59 | 180.375 | False | False |

**R9 section-first lines** whose heard first word was inside the old window and is outside the new one, same constants (36 lines). Last column: the envelope over the 100 ms after `heard_start` sits more than 12 dB below the louder neighbouring line's sung level.

| Song | L | first token | heard_start | old t0 | new t0 | env quiet at heard_start |
|---|---|---|---|---|---|---|
| #NSYNC - This I Promise You (Off | 50 | Every | 234.56 | 234.539 | 234.725 | True |
| #OutOfOz - 'For Good' Performed  | 34 | But | 163.6 | 163.043 | 163.612 | True |
| Backstreet Boys - Drowning (Offi | 1 | Don't | 19.54 | 19.188 | 19.700 | True |
| Backstreet Boys - Everybody (Bac | 17 | Hey, | 120.0 | 119.823 | 120.025 | True |
| Backstreet Boys - Get Down (You' | 51 | 'Cause | 120.88 | 120.657 | 121.025 | False |
| Backstreet Boys - I'll Never Bre | 3 | to | 13.89 | 13.619 | 14.088 | True |
| Backstreet Boys - I'll Never Bre | 28 | To | 112.66 | 112.297 | 112.863 | True |
| Backstreet Boys - I'll Never Bre | 29 | Girl, | 118.56 | 118.410 | 118.750 | True |
| Backstreet Boys - Inconsolable ( | 21 | In | 101.22 | 100.842 | 101.438 | False |
| Backstreet Boys - Quit Playing G | 54 | Baby | 154.58 | 154.547 | 154.825 | True |
| Backstreet Boys - The Call (Offi | 12 | Let | 26.32 | 25.935 | 26.450 | True |
| Britney Spears - (You Drive Me)  | 14 | Baby, | 57.08 | 56.822 | 57.238 | True |
| Britney Spears - ...Baby One Mor | 5 | And | 45.15 | 45.057 | 45.800 | False |
| Britney Spears - ...Baby One Mor | 21 | My | 110.64 | 110.255 | 111.150 | False |
| Britney Spears - ...Baby One Mor | 29 | Oh | 151.64 | 151.547 | 151.775 | True |
| Britney Spears - Stronger (Offic | 38 | I, | 209.02 | 208.480 | 209.075 | True |
| Céline Dion - I'm Alive (Officia | 32 | And | 152.72 | 152.320 | 152.950 | True |
| Céline Dion - That's The Way It  | 12 | I | 89.76 | 89.397 | 89.800 | True |
| Céline Dion - That's The Way It  | 16 | In | 109.6 | 109.386 | 109.900 | False |
| Ed Sheeran - Perfect (Official M | 36 | Dancing | 181.88 | 181.515 | 182.225 | True |
| Ed Sheeran - Shape of You (Offic | 16 | I'm | 56.5 | 56.432 | 56.575 | True |
| Ed Sheeran - Shape of You (Offic | 24 | I'm | 79.0 | 78.830 | 79.025 | True |
| Ed Sheeran - Shape of You (Offic | 45 | I'm | 136.5 | 136.345 | 136.575 | True |
| Ed Sheeran - Shape of You (Offic | 53 | I'm | 158.98 | 158.701 | 159.025 | True |
| Ed Sheeran - Shape of You (Offic | 54 | I'm | 163.98 | 163.831 | 164.038 | True |
| Idina Menzel - Let It Go (from F | 43 | Here | 196.34 | 196.283 | 196.612 | False |
| Jodi Benson - Part of Your World | 44 | What's | 135.68 | 135.049 | 136.075 | False |
| Justin Timberlake - Like I Love  | 41 | Here | 146.72 | 146.520 | 146.788 | True |
| Justin Timberlake - Like I Love  | 61 | Ma, | 193.98 | 193.480 | 194.550 | False |
| Justin Timberlake - Like I Love  | 70 | You're | 222.86 | 222.601 | 222.938 | True |
| Justin Timberlake - Mirrors (Off | 90 | And | 378.57 | 378.292 | 378.738 | False |
| Mulan _ I'll Make a Man Out of Y | 4 | You | 16.84 | 16.170 | 16.888 | True |
| NSYNC - Bye Bye Bye (Official Vi | 34 | I | 116.12 | 115.919 | 116.275 | True |
| NSYNC - Paradise | 4 | And | 61.65 | 61.590 | 61.775 | True |
| The Lion King - Hakuna Matata Mu | 45 | Philosophy | 109.08 | 109.044 | 109.150 | True |
| “Takedown” Official Choreography | 16 | I'ma | 49.02 | 48.940 | 49.338 | False |

**R10 grid**, all 135 cells (`probe` constants: slack, dip dB, min_quiet, tail_quiet). fb% = fallback share of interior edges; last_out = section-final lines whose heard last word is outside the window, old 55 -> new; first_out likewise for section-first lines, old 97 -> new; broken = inside the old window and outside the new; tgt_fail = test-song target lines (with a transcript, word found) outside the new window.

| slack | dip | min_q | tail_q | fb% | last_out | last_broken | first_out | first_broken | cuts | tgt_fail |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 6 | 0.05 | 0.25 | 3.0 | 32 | 2 | 105 | 26 | 39 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.05 | 0.5 | 3.0 | 32 | 2 | 105 | 26 | 39 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.05 | 1.0 | 3.0 | 30 | 1 | 105 | 26 | 39 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.1 | 0.25 | 5.9 | 33 | 2 | 104 | 25 | 32 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.1 | 0.5 | 5.9 | 33 | 2 | 104 | 25 | 32 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.1 | 1.0 | 5.9 | 31 | 1 | 104 | 25 | 32 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.2 | 0.25 | 12.1 | 34 | 1 | 106 | 24 | 20 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.2 | 0.5 | 12.1 | 34 | 1 | 106 | 24 | 20 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 6 | 0.2 | 1.0 | 12.1 | 32 | 0 | 106 | 24 | 20 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.05 | 0.25 | 6.4 | 33 | 1 | 108 | 27 | 37 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.05 | 0.5 | 6.4 | 33 | 1 | 108 | 27 | 37 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.05 | 1.0 | 6.4 | 32 | 1 | 108 | 27 | 37 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.1 | 0.25 | 8.5 | 33 | 0 | 109 | 27 | 32 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.1 | 0.5 | 8.5 | 33 | 0 | 109 | 27 | 32 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.1 | 1.0 | 8.5 | 32 | 0 | 109 | 27 | 32 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.2 | 0.25 | 15.6 | 35 | 0 | 111 | 26 | 22 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.2 | 0.5 | 15.6 | 35 | 0 | 111 | 26 | 22 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 9 | 0.2 | 1.0 | 15.6 | 34 | 0 | 111 | 26 | 22 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.05 | 0.25 | 7.7 | 31 | 0 | 109 | 29 | 39 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.05 | 0.5 | 7.7 | 30 | 0 | 109 | 29 | 39 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.05 | 1.0 | 7.7 | 30 | 0 | 109 | 29 | 39 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.1 | 0.25 | 12.7 | 35 | 0 | 111 | 27 | 27 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.1 | 0.5 | 12.7 | 34 | 0 | 111 | 27 | 27 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.1 | 1.0 | 12.7 | 34 | 0 | 111 | 27 | 27 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.2 | 0.25 | 20.4 | 40 | 0 | 113 | 25 | 17 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.2 | 0.5 | 20.4 | 39 | 0 | 113 | 25 | 17 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 12 | 0.2 | 1.0 | 20.4 | 39 | 0 | 113 | 25 | 17 | C-u5:20 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.05 | 0.25 | 15.5 | 40 | 1 | 105 | 24 | 28 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.05 | 0.5 | 15.5 | 39 | 1 | 105 | 24 | 28 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.05 | 1.0 | 15.5 | 38 | 1 | 105 | 24 | 28 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.1 | 0.25 | 19.8 | 43 | 1 | 107 | 23 | 21 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.1 | 0.5 | 19.8 | 42 | 1 | 107 | 23 | 21 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.1 | 1.0 | 19.8 | 41 | 1 | 107 | 23 | 21 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.2 | 0.25 | 25.4 | 43 | 0 | 106 | 19 | 14 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.2 | 0.5 | 25.4 | 42 | 0 | 106 | 19 | 14 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 18 | 0.2 | 1.0 | 25.4 | 41 | 0 | 106 | 19 | 14 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.05 | 0.25 | 22.4 | 41 | 0 | 107 | 21 | 19 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.05 | 0.5 | 22.4 | 39 | 0 | 107 | 21 | 19 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.05 | 1.0 | 22.4 | 39 | 0 | 107 | 21 | 19 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.1 | 0.25 | 26.4 | 42 | 0 | 108 | 20 | 14 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.1 | 0.5 | 26.4 | 40 | 0 | 108 | 20 | 14 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.1 | 1.0 | 26.4 | 40 | 0 | 108 | 20 | 14 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.2 | 0.25 | 31.5 | 45 | 0 | 105 | 16 | 9 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.2 | 0.5 | 31.5 | 43 | 0 | 105 | 16 | 9 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.25 | 24 | 0.2 | 1.0 | 31.5 | 43 | 0 | 105 | 16 | 9 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.05 | 0.25 | 1.9 | 34 | 6 | 105 | 32 | 62 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.05 | 0.5 | 1.9 | 34 | 6 | 105 | 32 | 62 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.05 | 1.0 | 1.9 | 31 | 4 | 105 | 32 | 62 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.1 | 0.25 | 3.8 | 33 | 5 | 104 | 31 | 55 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.1 | 0.5 | 3.8 | 33 | 5 | 104 | 31 | 55 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.1 | 1.0 | 3.8 | 30 | 3 | 104 | 31 | 55 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.2 | 0.25 | 9.1 | 33 | 3 | 106 | 30 | 41 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.2 | 0.5 | 9.1 | 33 | 3 | 106 | 30 | 41 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 6 | 0.2 | 1.0 | 9.1 | 30 | 1 | 106 | 30 | 41 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.05 | 0.25 | 4.0 | 34 | 4 | 114 | 38 | 60 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.05 | 0.5 | 4.0 | 34 | 4 | 114 | 38 | 60 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.05 | 1.0 | 4.0 | 32 | 3 | 114 | 38 | 60 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.1 | 0.25 | 5.9 | 33 | 3 | 114 | 37 | 54 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.1 | 0.5 | 5.9 | 33 | 3 | 114 | 37 | 54 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.1 | 1.0 | 5.9 | 31 | 2 | 114 | 37 | 54 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.2 | 0.25 | 12.3 | 34 | 2 | 116 | 35 | 41 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.2 | 0.5 | 12.3 | 34 | 2 | 116 | 35 | 41 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 9 | 0.2 | 1.0 | 12.3 | 32 | 1 | 116 | 35 | 41 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.05 | 0.25 | 5.9 | 31 | 2 | 116 | 38 | 59 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.05 | 0.5 | 5.9 | 31 | 2 | 116 | 38 | 59 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.05 | 1.0 | 5.9 | 29 | 1 | 116 | 38 | 59 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.1 | 0.25 | 9.7 | 34 | 2 | 116 | 36 | 54 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.1 | 0.5 | 9.7 | 34 | 2 | 116 | 36 | 54 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.1 | 1.0 | 9.7 | 32 | 1 | 116 | 36 | 54 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.2 | 0.25 | 16.9 | 39 | 1 | 119 | 33 | 38 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.2 | 0.5 | 16.9 | 39 | 1 | 119 | 33 | 38 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 12 | 0.2 | 1.0 | 16.9 | 37 | 0 | 119 | 33 | 38 | C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.05 | 0.25 | 12.4 | 37 | 2 | 113 | 35 | 49 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.05 | 0.5 | 12.4 | 37 | 2 | 113 | 35 | 49 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.05 | 1.0 | 12.4 | 34 | 1 | 113 | 35 | 49 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.1 | 0.25 | 16.9 | 42 | 2 | 114 | 32 | 42 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.1 | 0.5 | 16.9 | 42 | 2 | 114 | 32 | 42 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.1 | 1.0 | 16.9 | 39 | 1 | 114 | 32 | 42 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.2 | 0.25 | 22.7 | 43 | 1 | 111 | 25 | 33 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.2 | 0.5 | 22.7 | 43 | 1 | 111 | 25 | 33 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 18 | 0.2 | 1.0 | 22.7 | 40 | 0 | 111 | 25 | 33 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.05 | 0.25 | 19.8 | 42 | 2 | 111 | 27 | 38 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.05 | 0.5 | 19.8 | 41 | 2 | 111 | 27 | 38 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.05 | 1.0 | 19.8 | 39 | 1 | 111 | 27 | 38 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.1 | 0.25 | 24.4 | 42 | 1 | 111 | 24 | 31 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.1 | 0.5 | 24.4 | 41 | 1 | 111 | 24 | 31 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.1 | 1.0 | 24.4 | 39 | 0 | 111 | 24 | 31 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.2 | 0.25 | 28.8 | 45 | 1 | 110 | 22 | 26 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.2 | 0.5 | 28.8 | 44 | 1 | 110 | 22 | 26 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 0.5 | 24 | 0.2 | 1.0 | 28.8 | 42 | 0 | 110 | 22 | 26 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.05 | 0.25 | 0.9 | 36 | 13 | 108 | 38 | 186 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.05 | 0.5 | 0.9 | 36 | 13 | 108 | 38 | 186 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.05 | 1.0 | 0.9 | 32 | 10 | 108 | 38 | 186 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.1 | 0.25 | 1.7 | 35 | 12 | 108 | 37 | 184 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.1 | 0.5 | 1.7 | 35 | 12 | 108 | 37 | 184 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.1 | 1.0 | 1.7 | 31 | 9 | 108 | 37 | 184 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.2 | 0.25 | 5.9 | 36 | 10 | 108 | 35 | 172 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.2 | 0.5 | 5.9 | 36 | 10 | 108 | 35 | 172 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 6 | 0.2 | 1.0 | 5.9 | 32 | 7 | 108 | 35 | 172 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.05 | 0.25 | 1.9 | 37 | 13 | 115 | 42 | 147 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.05 | 0.5 | 1.9 | 36 | 12 | 115 | 42 | 147 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.05 | 1.0 | 1.9 | 32 | 9 | 115 | 42 | 147 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.1 | 0.25 | 3.8 | 35 | 11 | 116 | 41 | 138 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.1 | 0.5 | 3.8 | 34 | 10 | 116 | 41 | 138 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.1 | 1.0 | 3.8 | 30 | 7 | 116 | 41 | 138 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.2 | 0.25 | 10.4 | 39 | 9 | 117 | 38 | 126 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.2 | 0.5 | 10.4 | 38 | 8 | 117 | 38 | 126 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 9 | 0.2 | 1.0 | 10.4 | 34 | 5 | 117 | 38 | 126 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.05 | 0.25 | 3.8 | 36 | 10 | 119 | 42 | 131 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.05 | 0.5 | 3.8 | 35 | 9 | 119 | 42 | 131 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.05 | 1.0 | 3.8 | 31 | 6 | 119 | 42 | 131 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.1 | 0.25 | 6.8 | 39 | 10 | 118 | 40 | 124 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.1 | 0.5 | 6.8 | 38 | 9 | 118 | 40 | 124 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.1 | 1.0 | 6.8 | 34 | 6 | 118 | 40 | 124 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.2 | 0.25 | 14.6 | 41 | 6 | 118 | 35 | 106 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.2 | 0.5 | 14.6 | 40 | 5 | 118 | 35 | 106 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 12 | 0.2 | 1.0 | 14.6 | 36 | 2 | 118 | 35 | 106 | C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.05 | 0.25 | 9.0 | 40 | 8 | 114 | 39 | 98 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.05 | 0.5 | 9.0 | 40 | 8 | 114 | 39 | 98 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.05 | 1.0 | 9.0 | 35 | 5 | 114 | 39 | 98 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.1 | 0.25 | 14.6 | 45 | 6 | 115 | 36 | 88 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.1 | 0.5 | 14.6 | 45 | 6 | 115 | 36 | 88 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.1 | 1.0 | 14.6 | 40 | 3 | 115 | 36 | 88 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.2 | 0.25 | 21.1 | 44 | 3 | 111 | 28 | 78 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.2 | 0.5 | 21.1 | 44 | 3 | 111 | 28 | 78 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 18 | 0.2 | 1.0 | 21.1 | 39 | 0 | 111 | 28 | 78 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.05 | 0.25 | 17.2 | 41 | 5 | 116 | 34 | 72 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.05 | 0.5 | 17.2 | 39 | 5 | 116 | 34 | 72 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.05 | 1.0 | 17.2 | 36 | 2 | 116 | 34 | 72 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.1 | 0.25 | 22.7 | 44 | 5 | 113 | 28 | 65 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.1 | 0.5 | 22.7 | 42 | 5 | 113 | 28 | 65 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.1 | 1.0 | 22.7 | 39 | 2 | 113 | 28 | 65 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.2 | 0.25 | 27.6 | 48 | 4 | 110 | 24 | 60 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.2 | 0.5 | 27.6 | 46 | 4 | 110 | 24 | 60 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |
| 1.0 | 24 | 0.2 | 1.0 | 27.6 | 43 | 1 | 110 | 24 | 60 | C-u5:20 C-u5:30 AJWt:6 9ThO:36 |

## Hand-off prompt (executor)

```
Execute plans/cue-align-windows.md on branch cue_align_windows (HEAD daf183a, plan
untracked). Read Goal, Decisions, Library facts, Design, Phases and Rules first. Start at
Phase 0, record the baseline, then Phase 1. Stop at GATE A if any pass criterion fails,
and before Phase 5's GPU run until Ken says go. Log every step in the Results log.
```
