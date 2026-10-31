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

Opus, after Ken's GATE B notes and his steer, 2026-10-31 (rows 33-39). Proposed; Phase 5b waits on Ken:

12. **Only a line missing words gets a wider window; section windows go back to the
    caption rule.** Ken's steer: the window change is there to bring back missing words,
    timed by the model rather than guessed; edge timing is the snaps' job. Decision 11's
    measurement of where the singing stops stands; it is applied per line, to the
    one-line re-align, instead of to sections.
    - Why not widen sections: a wider section changes how the aligner spreads words over
      the whole section, not only the held tail. All five lines whose first word now
      starts early (row 30) are the last or second-to-last line of a widened section
      (row 37). In four of them the first word lands on the previous line's held note,
      which the onset snap takes as on time (row 36).
    - Ruled:
      - `segment_by_gaps` keeps the caption rule, with `173439c`'s duet end. No section
        end moves, so every line the section align times in full comes out as it would
        without this branch.
      - A bad or partial line's one-line re-align window ends at the larger of today's
        end (cue end + offset + `SECTION_PAD_S`) and where its own singing stops:
        `_volume_end` against the next line's cue, `_volume_tail` for the song's last
        line, capped at `duration`. The "landed where aimed" check aims at the same end.
        This replaces the section-last special case of Phase 4.
      - A re-aligned first word that starts before `cue start + offset - PAUSE_SLACK_S`
        and still has at least `INSTANT_WORD_DUR_S` after it is cut to start at that
        bound, before the check. One with less after the bound sits on the audio
        before the line and is rejected, as today. The end side is unchanged: a last
        word parked past the end bound is the aligner's failure sign (the
        `PAUSE_SLACK_S` comment). The slice's lead-in gives the aligner context; the
        aligner drags first-word starts back into it (rows 34-35).
      - The re-align replaces the line when it lands where aimed and times more words
        (Phase 4's rule). Its first word's start is then the onset snap's to repair,
        as for every line. Guessed words stay the last resort (Decision 3).
      - `_with_guessed_words` matches a line's words to its tokens in order (each word
        to the next token with its text) instead of by expected time. The time match
        hands a line's last word to a later repeat of its token (row 39: pre-branch
        Stronger 37 "no", Pocahontas 36 "the"), so the guesses fill the wrong tokens.
        In order is right for every drop seen: stable-ts drops the words after the
        last one it can place (row 38's warnings), and all 33 library drops are tails
        (Decision 8).
    - Measured (row 38, the 18 target lines through the one-line re-align with these
      windows): 15 timed in full by the model, against 13 with widened sections (row
      29). Left: Stronger 26 (its last "I go" is not found by the transcriber either),
      Miss Independent 9 and 71 (caption words the video does not sing, row 33); all
      three show guessed words today as well. 6 of the 15 pass the check only with the
      clamp.
    - Costs, on the 15 (row 39): after the onset snap, the re-aligned first word starts
      more than 0.5 s earlier than the section align's on 5 lines (Stronger 6, 32 and
      37, Baby One More Time 20, Castle 46) and 1.0 s later on 1 (Someone Like You 33).
      Against the transcriber's first word, on the 4 lines that have one: 2 closer
      (Stronger 6, Someone Like You 33), 1 further (Stronger 37), 1 the same (All of
      Me 29). The re-align results carry 4 words under `INSTANT_WORD_DUR_S` in 3 lines.
    - Not ruled: keeping the section's words and taking only the missing ones from the
      re-align. The head evidence above is mixed, and splicing two aligns needs each
      word's token carried through the line objects. Revisit if GATE B hears worse
      line starts.
    - Out of scope, recorded in `plans/open-issues.md` at Phase 6:
      - **The onset snap's on-time skip**: a first word placed on the previous line's
        still-sounding note is taken as on time (row 36), and the end snap then stops
        that note just before it (Someone Like You 3:48 "instead"). Shared by every
        timing source and older than this branch; changing it needs its own probe over
        the library.
      - **Pocahontas "wind"**: the window holds the whole note (to 190.9), but both the
        section align and the one-line re-align place "wind" before the singer's 1.2 s
        pause (182.84-183.94 and 182.86-184.36; sung 184.8-190.4; rows 14, 29, 38). The
        line has every word, so nothing flags it.
      - **Miss Independent's caption words that are not sung** ("God damn", "ooh" for
        "yeah"). Decision 3 stands: every caption word is shown and stat 1 counts the
        guessed ones. The fix for a caption that does not match the video is the
        song's lyric sheet.
    - Decision 11 is superseded where it widens sections, along with
      `Section.measured_end`, `Section.widened_end` and the `edges` stat.
    - GATE B stays Ken's, on the branch as a whole after Phase 5b.

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

### Phase 5b: windows only for lines missing words -> commits -> GPU rerun -> GATE B (Ken)

Only after Ken agrees to Decision 12. Run `graphify affected` on `segment_by_gaps`,
`repace_bad_lines`, `align_song` and `_with_guessed_words` first.

1. **Code** (`pikaraoke/lib/cue_align.py`), per Decision 12: `segment_by_gaps` loses
   `env`; `Section.measured_end`, `Section.widened_end` and the `edges` stat go;
   `_volume_end` and `_volume_tail` stay, documented per line. `repace_bad_lines` takes
   `env` and builds each bad or partial line's window from its measured end (exactly
   row 38's slices); guessed-word bounds use that window's end instead of the
   section's `t1`. The clamp. Module docstring and `repace_bad_lines` docstring
   updated. `pikaraoke/pipeline/stages/lyric_align.py` still decodes the envelope once
   on the cue route and passes it on.
2. **Tests** (`tests/unit/test_cue_align.py`, `tests/unit/test_lyric_align.py`):
   `TestSegmentByVolume` becomes tests of the per-line window (held into silence, sang
   into the next caption, hold cap, song tail, no envelope = today's window); a
   section's window no longer depends on the envelope; the clamp (first word in the
   lead-in kept at the bound; under `INSTANT_WORD_DUR_S` past it still rejected; a
   last word past the end bound still rejected).
3. **CPU check before committing**: the 18 saved results (`b1_<id>_<lid>.json` in the
   323ba938 scratchpad) through the changed `repace_bad_lines`, with the pre-branch
   words of row 39 as the partial lines and `realign` returning the saved words: the
   windows `realign` receives equal row 38's slices, and the same 15 are kept.
4. Commit the window change and the clamp as one commit; log a row.
5. **Guess-fill matching** (`_with_guessed_words`, in order, per Decision 12) with a
   test: tokens "no more, no more", line words "no" and "more," -> guesses for the
   last "no more", after them. Its own `fix(cue_align)` commit; log a row.
6. **GPU rerun**: ask Ken (app stopped), then Phase 5's command, dry run first.
   Pocahontas `.lrclib.srt` hash as row 28. Compare (`compare.py`, `vs_heard.py`)
   against the pre-branch backup (`~/pikaraoke-songs/regen_backups/20261031T174600Z`)
   and against this run's backup (the library as rows 29-31 measured it). Also:
   every line whose source changed, with words before and after; the 18 targets; the
   five early-start lines of row 30; lines starting > 0.5 s before the heard first
   word (52 pre-branch, 58 now). Expected, to be checked: lines not re-aligned match
   the pre-branch bundles, except where a re-aligned neighbour moved their end snap
   or where the pre-branch bundle predates `daf183a`'s pipeline (All of Me and
   Someone Like You, 2026-10-19).
7. Log raw tables; give Ken `song - m:ss - line text - what changed` for every changed
   line, targets first; stop at GATE B.

### Phase 6: after GATE B

Only on Ken's word: land on `dev` (Branches and Archive Tags in `CLAUDE.md`: copy the
code commits one by one, no plan file), then in `plans/open-issues.md` on `dev`, record
what remains (e.g. any test line still guessed, the not-the-window group, the
remaining 16 songs needing a Regenerate, review findings 4, 8 and 10 from row 24, and
Decision 12's three out-of-scope items), and retire the branch as
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
| 23 | 2026-10-31 | review | `/code-review high daf183a..4f3ece6`, files as Checkpoints, finders correctness / simplicity / robustness. Two findings probed by calling `_with_guessed_words` directly; the rest read from the code | 10 findings. (1) middle guess between touching neighbours: one 1.0-1.4, three 1.4-1.8 -> two 1.4-1.4. (2) tail guess past `before`: one 1.0-1.4, two 1.4-2.4, before 2.0 -> three, four 2.4-2.4. (3) section-last realign slice ran to `section.t1 + pad_s`; `section.t1` can be the next caption start. (4) `_volume_end` search starts at caption end - 0.5 with no display-lead correction: a short last caption with audio late by under `pad_s` finds the quiet before the line. (5) section end from `cue_spans[hi]` only; an earlier overlapping duet line can end later. (6) `_volume_tail` = last loud frame, no release rule, uncapped. (7) `align_song` re-ran `segment_by_gaps(env=None)` to count widened ends; cue route on decode failure decodes again in `snap_line_edges`. (8) `_quiet_runs` needs every frame quiet: one loud frame splits a release. (9) `_volume_end` returned `nxt[0]` (measured) when `nxt[0]` < search start. (10) every partial line now takes a per-line slice align |
| 24 | 2026-10-31 | review | commits `cdd5e5f` (findings 1, 2, 3: guessed words with less than `INSTANT_WORD_DUR_S` each share the timed neighbour's slot; `repace_bad_lines(pad_s=...)` builds the realign window, `realign(lid, w0, w1)` receives it, section-last line's `w1` = `max(t1, section.t1)` unpadded), `173439c` (findings 5, 9: section end and `_volume_end`/`_volume_tail` use the latest-ending line in the section; `_volume_end` returns None when `nxt[0] <= last[1] - EDGE_SEARCH_SLACK_S`), `ba57b7d` (finding 7: `Section.widened_end`, second grouping pass removed). Not changed: 6 (Decision 11 sets the tail as pad after the last sung frame; a first-release tail at `RELEASE_QUIET_S` 0.75 ends Pocahontas L36 near 184.35, before `wind` 184.92, row 11's 0.8 s dip at 183.6-184.4); the second decode on decode failure in 7; 4, 8, 10 deferred. Tests: +3 `TestPartialLines`, +2 `TestSegmentByVolume`, 4 realign-window asserts updated (`(4, 8.0, 10.0)` -> `(4, 7.25, 10.75)`, `(4, 8.0, 11.0)` -> `(4, 7.25, 11.0)`, `(4, 8.0, 9.0)` -> `(4, 7.25, 9.75)`, `TestAlignSong` held-note slice end 10.5 -> 9.75). Window figures of rows 20 and 21 not re-run | `pytest -q` 3044 passed in 37.37 s; pre-commit on `cue_align.py` and `test_cue_align.py` passes; on `4f3ece6`'s `cue_align.py` the 3 new `TestPartialLines` cases fail, and on `cdd5e5f`'s the 2 new `TestSegmentByVolume` cases and the added overlap `measured_end` assert fail |
| 25 | 2026-10-31 | 5 | Ken: "I've stopped the app so go". HEAD `f5639eb`, tree clean apart from Ken's `CLAUDE.md` edit. No app process; `nvidia-smi` 6 MiB of 6144 used. `sha256sum` of `lyrics/Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76peOw0.lrclib.srt` before: `d56db69749f7a5d518d7182cf6acd7d55fa08e2bfbc938a0e5c63f5ce9c641dd`. Scratch copy of the 9 songs' `alignment_debug`, `karaoke`, `lyrics`, `subtitles` files to the scratchpad `before/`. Dry run with the Phase 5 command | 9 songs: 8 `reuse srt (from video)`, Pocahontas `LRCLIB timing`; no Genius prompt. The task statement said rows from 23; rows 23-24 were already the review, so Phase 5 starts at 25 |
| 26 | 2026-10-31 | 5 | the Phase 5 command without `--dry-run`, with `--yes`, 2026-10-31 17:45:59Z to 18:04:22Z. Backup the script made: `~/pikaraoke-songs/regen_backups/20261031T174600Z/{alignment_debug,karaoke,lyrics,subtitles}` (33 files; `cmp` against the scratch copy: all identical) | exit 0, `Done. succeeded=9 failed=0 skipped=0`. Per-song stage log lines in block R26 below |
| 27 | 2026-10-31 | 5 | log warnings and bundle differences | Two `slice-align failed, degrading` warnings, each from `stable_whisper/alignment.py` `set_result_language`, `AttributeError: 'NoneType' object has no attribute 'language'`: Someone Like You line 44 (13:48:11), My Heart Will Go On line 25 (13:56:24). My Heart Will Go On: `transcribe yield 22.5 wpm < 30.0`, retried on a de-reverbed stem (retry 36.8 wpm), `joint_stats.dereverb` `{'yield_wpm': 22.5, 'succeeded': True, 'retry_yield_wpm': 36.8}` after; the before bundle has no `dereverb` key. Someone Like You before bundle: `transcribe_words` 0 (pre-`ddb1dcc`), after 336; its "heard" columns come from the after bundle. Other 7 songs: `dereverb` absent before and after |
| 28 | 2026-10-31 | 5 | `sha256sum` of the Pocahontas `.lrclib.srt` after the run | `d56db69749f7a5d518d7182cf6acd7d55fa08e2bfbc938a0e5c63f5ce9c641dd`, identical to before (Decision 10) |
| 29 | 2026-10-31 | 5 | scratch `compare.py` (before = the backup; after = the library), per song: target lines, non-target lines whose start or end moved > 0.3 s, words against tokens, overlaps, stats; word times from the ASS files (`asswords.py`: `\k` gap + `\kf` duration from the Dialogue start); `vs_heard.py`: every line's start against the transcriber's first word and end against its last word. Blocks R29 (verbatim compare output), R29w (ASS word times), R29h (vs_heard output) below | **Target lines (18)**: before, 18 lines short of their tokens in the 9 songs, 37 words (Stronger 4 lines/9 words, All of Me 3/6, Someone Like You 3/4, Baby One More Time 2/4, Miss Independent 2/4, Pocahontas 1/4, Incomplete 1/2, Castle 1/2, My Heart Will Go On 1/2); after, 0 lines short, 0 lines with no words, 0 with more words than tokens. Source of the 18 after: aligned 12; aligned + guessed words 4 (Stronger 26, Someone Like You 49, Miss Independent 71, Castle 46); re-aligned 1 (Stronger 32); re-aligned + guessed words 1 (Miss Independent 9). Target line ends, before -> after (heard last word end): Stronger 6 50.34 -> 50.66 (51.10); Stronger 32 182.56 -> 182.56 (180.38); Stronger 37 209.30 -> 208.90 (206.80); All of Me 29 137.25 -> 139.83 (138.98); Baby One More Time 20 110.86 -> 110.86 (110.64); Baby One More Time 30 169.50 -> 169.48 (168.20); Incomplete 3 43.51 -> 47.20 (46.04); Pocahontas 36 178.87 -> 183.95 (184.92); Castle 46 228.80 -> 228.80 (228.88); My Heart Will Go On 9 92.13 -> 92.25 (92.26); Someone Like You 49 245.75 -> 242.01 (245.28) |
| 30 | 2026-10-31 | 5 | same scripts, the other lines | Moved > 0.3 s, non-target lines: Stronger 4, All of Me 2, Someone Like You 7, Baby One More Time 1, Miss Independent 7, Pocahontas 0, Incomplete 0, Castle 0, My Heart Will Go On 10 (31). Overlapping line pairs (line starts before the previous line's end), before -> after: 0->2, 1->2, 0->2, 0->0, 6->7, 0->0, 0->0, 1->1, 1->1 in the order Stronger, All of Me, Someone Like You, Baby One More Time, Miss Independent, Pocahontas, Incomplete, Castle, My Heart Will Go On (9 -> 15). Pairs overlapping after and not before: Stronger 7/6 0.22 s, Stronger 32/31 0.40, All of Me 40/39 0.26, Someone Like You 25/24 0.36, Someone Like You 26/25 0.42, Miss Independent 65/64 0.50; "captions overlap" is `no` for all 15. Stronger 7: `But` 50.43-51.55 before and after; Stronger 6 now ends 50.66; Whisper `own` 50.22-51.10, `But` 51.10. `vs_heard.py` over 325 lines with a heard first word: start more than 0.5 s before the heard word, before -> after: 52 -> 58; end more than 0.3 s before the heard last word, before -> after: 12 -> 8. Lines whose start got earlier than heard by > 0.5 s and by > 0.3 s more than before: Stronger 18 (-0.56), Stronger 32 (-1.00), All of Me 40 (-0.83), Someone Like You 48 (-2.05), Miss Independent 51 (-0.90). Lines whose end got further before the heard end by > 0.3 s and by > 0.3 s more than before: Someone Like You 49 (heard 245.28, end 245.75 -> 242.01) |
| 31 | 2026-10-31 | 5 | `joint_stats.edges` and `repace` of the 9 after bundles; Song Info `_timed_tile` and `_alignment` rendered for each status (Flask test request context) | `edges` `{n, widened, fallback}`: Stronger 10/8/0, All of Me 13/13/0, Someone Like You 13/11/0, Baby One More Time 8/8/0, Miss Independent 8/5/0, Pocahontas 4/1/0, Incomplete 18/14/3, Castle 9/3/0, My Heart Will Go On 5/1/0 (total 88/64/3). `n_guessed_words` / lines: Stronger 2/1, All of Me 0/0, Someone Like You 4/1, Baby One More Time 0/0, Miss Independent 2/2, Pocahontas 0/0, Incomplete 0/0, Castle 2/1, My Heart Will Go On 0/0 (10 words, 5 lines). `n_repaced` / `n_realigned` before -> after: Stronger 1/0 -> 2/1, All of Me 2/0 -> 1/1, Someone Like You 1/1 -> 1/1, Baby One More Time 0/1 -> 0/1, Miss Independent 4/3 -> 5/4, Pocahontas 0/3 -> 0/3, Incomplete 0/0 -> 0/0, Castle 1/1 -> 1/1, My Heart Will Go On 2/4 -> 4/1. Timed tile before -> after: Stronger 97% -> 95%, All of Me 96% -> 98%, Someone Like You 98% -> 98%, Baby One More Time 100% -> 100%, Miss Independent 96% -> 94%, Pocahontas 100% -> 100%, Incomplete 100% -> 100%, Castle 98% -> 98%, My Heart Will Go On 93% -> 85% (4 of 27 guessed; `poor` false, 0.148 against 0.15). Before, all 9 songs had a "Missing from the screen" note (warn); after, 0 do. Per-song stats in block R29 |
| 32 | 2026-10-31 | 5 | stop | GATE B reached; listening list handed to Ken; no code changed in Phase 5; Phase 5 log rows 25-32 and blocks R26, R29, R29w, R29h committed as a `docs(plan)` commit |
| 33 | 2026-10-31 | 5 | GATE B: Ken's listening notes on the list (condensed) | Stronger 2:55: "I, I'm" run together, so it is catching the first I now, otherwise good. All of Me: good. Someone Like You: the overlap at 2:03 might just be the lead-in, the sweep looks sequential to Ken; asks why the 4 words at 3:57 had to be guessed. Incomplete: good. Baby One More Time: good. My Heart Will Go On: asks why the last line is guessed, "shouldn't its end window be the easiest to get right". Castle On The Hill: good. Miss Independent: "God damn" is not in the video (probably censorship); the video has "yeah yeah" where the caption has "ooh yeah". Pocahontas: "wind" first reported as coming in late and ending early, then "comes in early and ends early". Ken also said model work for these questions may use the GPU instead of the CPU. No GATE B ruling yet |
| 34 | 2026-10-31 | 5 | scratch `replay.py <id> section\|line <lid>` (GPU; `WhisperModelConfig()` defaults; `_do_align_refine` as the worker runs it; slice by `ffmpeg -ss -to`; "faithful" = the cached stem first decoded to a stereo 44.1 kHz s16 wav as `load_vocal` does, then sliced). A first CPU attempt was stopped when Ken said to use the GPU. Section replays take the window `segment_by_gaps(env=...)` gives; line replays take the window `repace_bad_lines` aims (w0 = cue start + offset - 0.75, w1 = section.t1 for a section's last line) | **Someone Like You L44-49**, window 216.975-246.146. Slice cut from the m4a: 35 of 35 tokens returned, L49 9/9. Faithful, two runs: 31 words, L49 5/9 (`I` 237.77-239.12, `wish` 239.12-239.5, `nothing` 239.98-240.08, `but` 240.4-240.7, `the` 240.7-240.8), identical in both runs and to the regen bundle. L49 rescue slice 237.743-246.146: 9 words: `I` 237.9-239.14, `best` 241.47-242.08 p 0.9988, `for` 242.60-242.94 p 0.8334, `you,` 243.31-243.44 p 0.5013, `too` 244.44-245.28 p 0.0102. **My Heart Will Go On L22-26** (dereverb stem), window 204.625-263.325: 23 of 34 tokens returned, last `safe` 234.49-234.60 p 0.0525; L22-24 full, L25 0/7, L26 0/7 (same cut from the m4a and faithful). L26 rescue slice 237.664-263.325: 7 of 7 words: `My` 237.66-239.28 p 0.1347, `heart` 239.28-239.96, `will` 239.96-240.58, `go` 240.98-241.64, `on` 241.64-243.14, `and` 243.66-243.96, `on` 243.96-244.96 |
| 35 | 2026-10-31 | 5 | scratch `inspan_check.py`: the saved rescue-slice words through `cue_align._line_from_realigned` and `_line_in_span`, with the aimed window as `repace_bad_lines` builds it (`(cue start, max(cue end, aim_end - offset))`, slack `PAUSE_SLACK_S` 0.5); then the first word's start set to the lower bound | Someone Like You L49: 9/9 words, start 237.903, end 245.283, allowed 237.993 to 246.646, `_line_in_span` False; first word's start set to 237.993: True (short by 0.090 s). My Heart Will Go On L26: 7/7 words, start 237.664, end 244.964, allowed 237.914 to 263.825, False; set to 237.914: True (short by 0.250 s). In the regen bundles: Someone Like You L49 is not in `repaced_line_ids` or `realigned_line_ids` and is in `guessed_word_line_ids` (4 words); My Heart Will Go On L26 is in `repaced_line_ids` |
| 36 | 2026-10-31 | GATE B | Opus, scratch `onset_why.py` (CPU, read only; in the 323ba938 scratchpad beside `inspan_check.py`): word times of the after library from the ASS (`asswords.py`), envelopes from row 7's cache, stem by `inspan_check.py`'s rule. (1) Each early first word of row 30: the branch `snap_line_onsets` takes on the line as shown (the shown words are already past the snap, so this is the snap's decision on a line it left in place). (2) Row 35's two saved rescues: `snap_line_onsets` on the rescue line before the check, then `_line_in_span`; and on the line with the first word's start set to the bound. Skipped as on time = level over the 3 frames at word 1's start >= ref - `NEAR_SUNG_DB` (8) and median over word 1's span >= ref - `SUSTAIN_NEAR_DB` (12). Envelope dB every 0.25 s | **Stronger L18** (vocal; heard 105.62): `My` 105.05-105.91, word 2 106.30, previous last word `way` 104.40-105.05; ref -20.6, start -22.3, span median -22.9: skipped as on time. 104.55 -20, 104.80 -19, 105.05 -23, 105.30 -24, 105.55 -30, 105.80 -21, 106.05 -36, 106.30 -19. **Stronger L32** (heard 176.16): `I,` 175.16-177.90, word 2 178.24, previous `more` 174.50-175.56; ref -19.3, start -20.0, span -20.3: on time. 174.91 -18, 175.16 -20, 175.41 -20, 175.66 -30, 175.91 -28, 176.16 -19, 176.41 -19 ... 177.66 -19, 177.91 -29, 178.16 -30, 178.41 -19. **All of Me L40** (heard 183.136): `'Cause` 182.30-183.35, word 2 183.35, previous `winning` 182.22-182.56; ref -16.3, start -15.1, span -29.2: not on time, rise 183.125, the snap moves the start to 183.07 when rerun on the shown words; the shown start is 182.30 (the snap's input in the pipeline is not saved). 182.30 -15, 182.55 -22, 182.80 -44, 183.05 -53, 183.30 -16, 183.55 -14. **Someone Like You L48** (heard 232.768): `Never` 230.71-232.21, word 2 233.18, previous `instead` 228.74-230.62 (231.60 before); ref -14.8, start -15.7, span -20.8: on time. 230.71 -17, 230.96 -16, 231.21 -19, 231.46 -21, 231.71 -34, 231.96 -49, 232.21 -50, 232.46 -34, 232.71 -54, 232.96 -12, 233.21 -16. **Miss Independent L51** (heard 158.6): `She` 157.70-159.20, word 2 159.58, previous `time` 156.94-157.69 (158.61 before); ref -14.7, start -14.8, span -19.8: on time. 157.70 -15, 157.95 -15, 158.20 -19, 158.45 -17, 158.70 -22, 158.95 -36, 159.20 -43, 159.45 -42, 159.70 -13. **Someone Like You L49 rescue** (vocal; bound 237.993; `I` 237.903-239.143, word 2 239.423; previous line's last word 237.00-237.70, aligned): snap before the check: ref -13.5, start -14.4, span -13.9, on time, start 237.90, `_line_in_span` False; clamped then snapped: on time, start 237.99. 237.40 -14, 237.65 -13, 237.90 -12, 238.15 -12, 238.40 -14, 238.65 -14, 238.90 -16, 239.15 -16, 239.40 -15. **My Heart Will Go On L26 rescue** (dereverb; bound 237.914; `My` 237.664-239.164 (capped at 1.5 s), word 2 239.284; L25 spaced from caption, last word 237.66-238.41): snap before the check: ref -18.6, start -29.3, span -33.3, fired, rise 237.65, start 237.66, `_line_in_span` False; clamped then snapped: start -16.1, span -40.6, rise 238.85, start 238.80. 237.16 -12, 237.41 -17, 237.66 -37, 237.91 -16, 238.16 -16, 238.41 -54, 238.66 -49, 238.91 -33, 239.16 -16, 239.41 -31 |
| 37 | 2026-10-31 | GATE B | Opus, scratch `early_sections.py` (CPU, read only, 323ba938 scratchpad): the section of each early-start line of row 30, `segment_by_gaps` without and with the envelope (row 7's cache) | Stronger L18: section L10-18, 67.30-111.05 -> 67.30-112.48 (+1.43). Stronger L32: L27-32, 149.22-181.54 -> 182.58 (+1.04). All of Me L40: L31-40, 146.92-188.81 -> 189.60 (+0.79). Someone Like You L48: L44-49, 216.97-244.77 -> 246.15 (+1.38). Miss Independent L51: L36-51, 114.68-162.08 -> 162.10 (+0.02). Same lines in every section with and without. Before bundles captured 2026-10-29 (Stronger, Miss Independent) and 2026-10-19 (All of Me, Someone Like You); `daf183a` is 2026-10-30 |
| 38 | 2026-10-31 | GATE B | Ken: "it's stopped, run it" (app stopped; `nvidia-smi` 6 MiB used). Scratch `b1_rescue.py` (GPU, no library writes, 323ba938 scratchpad; `WhisperModelConfig()` defaults, model loaded once in 7 s, `_do_align_refine` as the worker runs it, faithful slices as row 34). Each of the 18 target lines: w0 = cue start + `repace.offset_s` - 0.75; w1 = max(cue end + offset + 0.75, measured) capped at `media_duration_s`, measured = `_volume_end(env, cue, next cue, 0.75)`, `_volume_tail` for the song's last line; `_line_from_realigned` with aim_end = max(cue end + offset, measured); `_line_in_span` against `(cue start, max(cue end, aim_end - offset))`, raw and with Decision 12's clamp; kept = clamped check passes and more words than the pre-branch line (before-backup ASS). Output `b1_results.json`, `b1_<id>_<lid>.json`, `b1_rescue.log` | Columns: tokens / pre-branch words / words now (source now) / measured / slice / returned-matched / in span raw-clamped / kept. Stronger 6: 11/8/11 (aligned) / 51.19 / 42.31-51.19 / 11-11 / T-T / yes. Stronger 26: 15/13/15 (aligned + guessed) / 146.61 / 140.23-146.73 / 13-13 / T-T / no (13 not more than 13). Stronger 32: 5/4/5 (re-aligned) / 182.58 / 174.54-182.58 / 5-5 / T-T / yes. Stronger 37: 9/6/9 (aligned) / 209.23 / 200.38-209.23 / 9-9 / T-T / yes. All of Me 29: 11/9/11 (aligned) / 140.33 / 130.61-140.33 / 11-11 / T-T / yes. All of Me 46: 8/6/8 (aligned) / 221.24 / 213.56-221.24 / 8-8 / F-T / yes. All of Me 49: 11/9/11 (aligned) / 236.48 / 228.08-236.48 / 11-11 / T-T / yes. Someone Like You 16: 9/7/9 (aligned) / 87.44 / 79.03-87.44 / 9-9 / F-T / yes. Someone Like You 33: 9/8/9 (aligned) / 170.87 / 162.53-170.87 / 9-9 / T-T / yes. Someone Like You 49: 9/8/9 (aligned + guessed) / 246.15 / 237.74-246.15 / 9-9 / F-T / yes. Baby One More Time 20: 11/9/11 (aligned) / 110.85 / 103.81-110.85 / 11-11 / T-T / yes. Baby One More Time 30: 10/8/10 (aligned) / 169.70 / 160.41-169.70 / 10-10 / T-T / yes. Miss Independent 9: 4/2/4 (re-aligned + guessed) / 25.93 / 23.16-26.56 / 3-3 / F-F / no. Miss Independent 71: 4/2/4 (aligned + guessed) / 219.30 / 216.46-220.13 / 4-4 / F-F / no. Pocahontas 36: 10/6/10 (aligned) / 190.90 / 173.94-190.90 / 10-10 / F-T / yes (`the` 182.27-182.86, `wind` 182.86-184.36). Incomplete 3: 6/4/6 (aligned) / 47.10 / 38.58-47.10 / 6-6 / T-T / yes (`guess` 45.76-46.06; heard end 46.04). Castle 46: 5/3/5 (aligned + guessed) / 229.65 / 225.64-229.66 / 5-5 / F-T / yes (`way` 228.70-228.84; heard end 228.88). My Heart Will Go On 9: 6/4/6 (aligned) / 92.42 / 86.75-92.79 / 6-6 / F-T / yes (`heart` 91.70-92.28; heard end 92.26). Someone Like You 49 `too` 244.44-245.28 (heard end 245.28). Kept 15 of 18, 6 of them only with the clamp. Slice ends equal the current rescue's except Stronger 26 (146.73 vs 147.22), Miss Independent 9 (26.56 vs 26.45), 71 (220.13 vs 219.38), Castle 46 (229.66 vs 229.74). stable-ts warnings: `Failed to align the last 3/15 words after 00:06.480` (Stronger 26), `the last 2/4 words after 00:03.380` (Miss Independent 9) |
| 39 | 2026-10-31 | GATE B | CPU over row 38's results: (1) `snap_line_onsets` on each kept re-align line (envelope as row 36), its first-word start against the pre-branch line's (backup ASS, already past the snap) and the transcriber's first word; (2) words under `INSTANT_WORD_DUR_S` in the kept results; (3) the pre-branch words matched to the line's tokens with `_match_words_to_tokens` (expected times across the cue span, as `_with_guessed_words` does), and the re-align's word for the first unmatched token against the last matched pre-branch word | (1) pre-branch / B1 raw / B1 snapped / heard: Stronger 6 44.05 / 42.66 / 42.66 / 42.86; Stronger 32 176.56 / 175.16 / 175.16 / 176.16; Stronger 37 201.69 / 200.88 / 200.88 / 201.86; All of Me 29 131.71 / 131.49 / 131.70 / 131.40; All of Me 46 214.52 / 213.81 / 214.53 / -; All of Me 49 229.05 / 229.32 / 229.32 / -; Someone Like You 16 79.18 / 79.28 / 79.28 / -; Someone Like You 33 161.83 / 162.83 / 162.83 / 162.92; Someone Like You 49 237.85 / 237.99 / 237.99 / -; Baby One More Time 20 105.24 / 104.48 / 104.48 / -; Baby One More Time 30 161.18 / 160.85 / 161.10 / -; Pocahontas 36 174.12 / 174.19 / 174.19 / -; Incomplete 3 39.68 / 39.66 / 39.66 / -; Castle 46 226.67 / 225.89 / 225.89 / -; My Heart Will Go On 9 87.14 / 87.00 / 87.00 / -. (2) Stronger 37 `My` 200.88-200.88; All of Me 49 `Give` 229.32-229.32; Baby One More Time 20 `baby,` 106.55-106.57, `oh` 109.89-109.89. (3) pre-branch words match a token prefix in 13 of 15; Stronger 37 (6 words: `no` matched to token 7, the second `no`; tokens 5, 6, 8 unmatched) and Pocahontas 36 (6 words: `the` matched to token 8, the second `the`; tokens 5, 6, 7, 9 unmatched). In all 15 the re-align's word for the first unmatched token starts after the last matched pre-branch word starts; it starts before that word's snapped end in 11 (by 0.60-2.46 s) |

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

**R26 stage log lines per song** (`regen_run.log`, in run order; `cue-align: N cues -> S sections`; `cue rescue`; `window end(s) widened`).

| Song | cues -> sections | rescue offset | re-aligned | re-paced | guessed words (lines) | widened / sections | left on caption |
|---|---|---|---|---|---|---|---|
| Someone Like You | 56 -> 13 | -0.53 | 1 | 1/56 | 4 (1) | 11/13 | 0 |
| Incomplete | 27 -> 18 | -0.69 | 0 | 0/27 | 0 (0) | 14/18 | 3 |
| Baby One More Time | 46 -> 8 | -0.10 | 1 | 0/46 | 0 (0) | 8/8 | 0 |
| Stronger | 39 -> 10 | -0.50 | 1 | 2/39 | 2 (1) | 8/10 | 0 |
| My Heart Will Go On | 27 -> 5 | -0.38 | 1 | 4/27 | 0 (0) | 1/5 | 0 |
| Castle On The Hill | 56 -> 9 | -0.17 | 1 | 1/56 | 2 (1) | 3/9 | 0 |
| All of Me | 56 -> 13 | -0.25 | 1 | 1/56 | 0 (0) | 13/13 | 0 |
| Miss Independent | 89 -> 8 | +0.11 | 4 | 5/89 | 2 (2) | 5/8 | 0 |
| Pocahontas | 37 -> 4 | -0.15 | 3 | 0/37 | 0 (0) | 1/4 | 0 |

**R29 compare output** (`compare.py`, verbatim; `source` is from `joint_stats.repace` ids: `spaced` = in `repaced_line_ids`, `re-aligned` = in `realigned_line_ids`, `+guessed words` = in `guessed_word_line_ids`; `words b/a` in the moved tables is `n_words`/tokens; heard times are the after bundle's `transcribe_words` matched to the line's first and last token inside its cue span).

#### Stronger (AJWtLf4-WWs); lines 39; before 2026-10-29T23:09:26+00:00 -> after 2026-10-31T17:53:47+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 10, 'widened': 8, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.596, "n_repaced": 1, "repaced_line_ids": [21], "n_realigned": 0, "realigned_line_ids": []}
joint_stats.repace after: {"offset_s": -0.497, "n_repaced": 2, "repaced_line_ids": [1, 21], "n_realigned": 1, "realigned_line_ids": [32], "n_guessed_words": 2, "guessed_word_line_ids": [26]}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | You might think that I won't make it on my own | 11 | 8 | 11 | aligned | aligned | 44.06 | 43.91 | 50.34 | 50.66 | 42.86 | 51.10 |
| 26 | Here I go, here I go, here I go, here I go, here I go | 15 | 13 | 15 | aligned | aligned +guessed words | 141.71 | 141.71 | 146.62 | 146.86 | - | - |
| 32 | I, I'm stronger than yesterday | 5 | 4 | 5 | aligned | re-aligned | 176.56 | 175.16 | 182.56 | 182.56 | 176.16 | 180.38 |
| 37 | My loneliness ain't killing me no more, no more | 9 | 6 | 9 | aligned | aligned | 201.69 | 201.71 | 209.30 | 208.90 | 201.86 | 206.80 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Oh, yeah, yeah | 19.73 | 19.70 | 22.50 | 23.55 | -0.03 | +1.05 | 3/3 | 3/3 | aligned | spaced | - | - |
| 18 | My loneliness ain't killing me no more | 105.36 | 105.06 | 113.27 | 113.27 | -0.30 | +0.00 | 7/7 | 7/7 | aligned | aligned | 105.62 | 111.16 |
| 31 | My loneliness ain't killing me no more | 169.82 | 169.82 | 176.46 | 175.56 | +0.00 | -0.90 | 7/7 | 7/7 | aligned | aligned | 169.89 | 174.94 |
| 38 | I, I'm stronger | 209.40 | 209.00 | 213.30 | 213.33 | -0.40 | +0.03 | 3/3 | 3/3 | aligned | aligned | 209.02 | 211.76 |

moved non-target lines: 4

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 4 [(6, 8, 11), (26, 13, 15), (32, 4, 5), (37, 6, 9)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 0, after 2
| 7 | 6 | 0:50.44 | 50.34 | 50.66 | 50.44 | 50.44 | 0.00 | 0.22 | no |
| 32 | 31 | 2:55.16 | 176.46 | 175.56 | 176.56 | 175.16 | 0.00 | 0.40 | no |

**Song Info stats**

- before: Timed tile `97%` / `1 guessed · 9 words` warn=True; poor=False; guessed=1; cue_lines={'aligned': 38, 'realigned': 0, 'paced': 1}; words_guessed=None/None lines; words_missing=9/4 lines; bar: Aligned 38, Spaced from caption 1; note: Missing from the screen: 9 words in 4 lines. Regenerate to show them. (warn True)
- after: Timed tile `95%` / `2 guessed · 2 words` warn=False; poor=False; guessed=2; cue_lines={'aligned': 36, 'realigned': 1, 'paced': 2}; words_guessed=2/1 lines; words_missing=None/None lines; bar: Aligned 36, Re-aligned 1, Spaced from caption 2; note: Guessed timing: 2 words in 1 line. (warn False)

#### All of Me (450p7goxZqg); lines 56; before 2026-10-19T18:54:26+00:00 -> after 2026-10-31T18:00:26+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 13, 'widened': 13, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.296, "n_repaced": 2, "repaced_line_ids": [22, 40], "n_realigned": 0, "realigned_line_ids": []}
joint_stats.repace after: {"offset_s": -0.254, "n_repaced": 1, "repaced_line_ids": [22], "n_realigned": 1, "realigned_line_ids": [40], "n_guessed_words": 0, "guessed_word_line_ids": []}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 29 | I can't stop singing, it's ringing in my head for you | 11 | 9 | 11 | aligned | aligned | 131.72 | 131.72 | 137.25 | 139.83 | 131.40 | 138.98 |
| 46 | 'Cause all of me loves all of you | 8 | 6 | 8 | aligned | aligned | 214.53 | 214.53 | 220.83 | 220.83 | 213.78 | 220.70 |
| 49 | Give your all to me, I'll give my all to you | 11 | 9 | 11 | aligned | aligned | 229.05 | 229.05 | 236.10 | 236.10 | 229.09 | 235.92 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 40 | 'Cause I give you all of me | 183.07 | 182.30 | 188.85 | 188.90 | -0.77 | +0.05 | 7/7 | 7/7 | spaced | re-aligned | 183.14 | 188.32 |
| 55 | And you give me all of you, oh | 266.90 | 266.90 | 270.95 | 275.05 | +0.00 | +4.10 | 8/8 | 8/8 | aligned | aligned | 266.98 | 273.60 |

moved non-target lines: 2

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 3 [(29, 9, 11), (46, 6, 8), (49, 9, 11)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 1, after 2
| 23 | 22 | 1:46.05 | 106.98 | 107.03 | 106.05 | 106.05 | 0.93 | 0.98 | no |
| 40 | 39 | 3:02.30 | 182.56 | 182.56 | 183.07 | 182.30 | 0.00 | 0.26 | no |

**Song Info stats**

- before: Timed tile `96%` / `2 guessed · 6 words` warn=True; poor=False; guessed=2; cue_lines={'aligned': 54, 'realigned': 0, 'paced': 2}; words_guessed=None/None lines; words_missing=6/3 lines; bar: Aligned 54, Spaced from caption 2; note: Missing from the screen: 6 words in 3 lines. Regenerate to show them. (warn True)
- after: Timed tile `98%` / `1 guessed` warn=False; poor=False; guessed=1; cue_lines={'aligned': 54, 'realigned': 1, 'paced': 1}; words_guessed=0/0 lines; words_missing=None/None lines; bar: Aligned 54, Re-aligned 1, Spaced from caption 1; note: None (warn False)

#### Someone Like You (hLQl3WQQoQ0); lines 56; before 2026-10-19T18:12:58+00:00 -> after 2026-10-31T17:48:23+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 13, 'widened': 11, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.509, "n_repaced": 1, "repaced_line_ids": [44], "n_realigned": 1, "realigned_line_ids": [45]}
joint_stats.repace after: {"offset_s": -0.525, "n_repaced": 1, "repaced_line_ids": [44], "n_realigned": 1, "realigned_line_ids": [45], "n_guessed_words": 4, "guessed_word_line_ids": [49]}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 16 | I wish nothing but the best for you, too | 9 | 7 | 9 | aligned | aligned | 79.19 | 79.19 | 86.59 | 86.47 | 79.22 | 86.44 |
| 33 | I wish nothing but the best for you, too | 9 | 8 | 9 | aligned | aligned | 161.83 | 161.85 | 170.82 | 170.78 | 162.92 | 170.00 |
| 49 | I wish nothing but the best for you, too | 9 | 8 | 9 | aligned | aligned +guessed words | 237.85 | 237.77 | 245.75 | 242.01 | 237.88 | 245.28 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | And you're married now | 24.33 | 24.37 | 28.98 | 28.14 | +0.04 | -0.84 | 4/4 | 4/4 | aligned | aligned | - | 27.48 |
| 3 | I heard that your dreams came true | 29.08 | 28.24 | 34.97 | 34.93 | -0.84 | -0.04 | 7/7 | 7/7 | aligned | aligned | - | 35.00 |
| 24 | Only yesterday was the time of our lives | 117.21 | 117.23 | 123.76 | 124.21 | +0.02 | +0.45 | 8/8 | 8/8 | aligned | aligned | 117.42 | 124.14 |
| 25 | We were born and raised in a summer haze | 123.86 | 123.86 | 130.88 | 131.40 | +0.00 | +0.52 | 9/9 | 9/9 | aligned | aligned | 124.16 | 130.80 |
| 41 | How bittersweet this would taste | 194.06 | 194.08 | 199.68 | 201.55 | +0.02 | +1.88 | 5/5 | 5/5 | aligned | aligned | 194.08 | 201.18 |
| 47 | But sometimes it hurts instead | 226.99 | 226.99 | 231.60 | 230.62 | +0.00 | -0.98 | 5/5 | 5/5 | aligned | aligned | 227.08 | 229.46 |
| 48 | Never mind, I'll find someone like you | 232.65 | 230.72 | 237.75 | 237.67 | -1.93 | -0.08 | 7/7 | 7/7 | aligned | aligned | 232.77 | 236.88 |

moved non-target lines: 7

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 3 [(16, 7, 9), (33, 8, 9), (49, 8, 9)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 0, after 2
| 25 | 24 | 2:03.86 | 123.76 | 124.21 | 123.86 | 123.86 | 0.00 | 0.36 | no |
| 26 | 25 | 2:10.98 | 130.88 | 131.40 | 130.98 | 130.98 | 0.00 | 0.42 | no |

**Song Info stats**

- before: Timed tile `98%` / `1 guessed · 4 words` warn=True; poor=False; guessed=1; cue_lines={'aligned': 54, 'realigned': 1, 'paced': 1}; words_guessed=None/None lines; words_missing=4/3 lines; bar: Aligned 54, Re-aligned 1, Spaced from caption 1; note: Missing from the screen: 4 words in 3 lines. Regenerate to show them. (warn True)
- after: Timed tile `98%` / `1 guessed · 4 words` warn=False; poor=False; guessed=1; cue_lines={'aligned': 54, 'realigned': 1, 'paced': 1}; words_guessed=4/1 lines; words_missing=None/None lines; bar: Aligned 54, Re-aligned 1, Spaced from caption 1; note: Guessed timing: 4 words in 1 line. (warn False)

#### Baby One More Time (C-u5WLJ9Yk4); lines 46; before 2026-10-29T23:06:24+00:00 -> after 2026-10-31T17:52:01+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 8, 'widened': 8, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.115, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 1, "realigned_line_ids": [28]}
joint_stats.repace after: {"offset_s": -0.104, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 1, "realigned_line_ids": [28], "n_guessed_words": 0, "guessed_word_line_ids": []}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | Tell me, baby, 'cause I need to know now, oh because | 11 | 9 | 11 | aligned | aligned | 105.25 | 105.26 | 110.86 | 110.86 | 105.18 | 110.64 |
| 30 | I must confess, that my loneliness is killing me now | 10 | 8 | 10 | aligned | aligned | 161.18 | 161.55 | 169.50 | 169.48 | - | 168.20 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | And now you're out of sight, yeah | 46.05 | 45.60 | 48.72 | 48.72 | -0.45 | +0.00 | 7/7 | 7/7 | aligned | aligned | 45.15 | 48.72 |

moved non-target lines: 1

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 2 [(20, 9, 11), (30, 8, 10)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 0, after 0

**Song Info stats**

- before: Timed tile `100%` / `0 guessed · 4 words` warn=True; poor=False; guessed=0; cue_lines={'aligned': 45, 'realigned': 1, 'paced': 0}; words_guessed=None/None lines; words_missing=4/2 lines; bar: Aligned 45, Re-aligned 1; note: Missing from the screen: 4 words in 2 lines. Regenerate to show them. (warn True)
- after: Timed tile `100%` / `0 guessed` warn=False; poor=False; guessed=0; cue_lines={'aligned': 45, 'realigned': 1, 'paced': 0}; words_guessed=0/0 lines; words_missing=None/None lines; bar: Aligned 45, Re-aligned 1; note: None (warn False)

#### Miss Independent (k6M5C-oKw9k); lines 89; before 2026-10-29T23:30:17+00:00 -> after 2026-10-31T18:02:51+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 8, 'widened': 5, 'fallback': 0}
joint_stats.repace before: {"offset_s": 0.13, "n_repaced": 4, "repaced_line_ids": [5, 7, 12, 37], "n_realigned": 3, "realigned_line_ids": [38, 72, 78]}
joint_stats.repace after: {"offset_s": 0.112, "n_repaced": 5, "repaced_line_ids": [5, 7, 12, 37, 65], "n_realigned": 4, "realigned_line_ids": [9, 38, 72, 78], "n_guessed_words": 2, "guessed_word_line_ids": [9, 71]}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | Good morning. God damn. | 4 | 2 | 4 | aligned | re-aligned +guessed words | 24.62 | 23.45 | 25.01 | 26.45 | - | - |
| 71 | Ooh yeah, ooh yeah | 4 | 2 | 4 | aligned | aligned +guessed words | 216.36 | 216.20 | 218.40 | 219.08 | - | - |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 38 | Ooh yeah, ooh yeah | 118.79 | 118.91 | 121.95 | 120.79 | +0.12 | -1.16 | 4/4 | 4/4 | re-aligned | re-aligned | - | - |
| 50 | And her bills are paid on time | 155.10 | 155.10 | 158.62 | 157.70 | +0.00 | -0.92 | 7/7 | 7/7 | aligned | aligned | 155.06 | 157.60 |
| 51 | She made for a boss, only a boss | 159.47 | 157.70 | 162.70 | 162.70 | -1.76 | +0.00 | 8/8 | 8/8 | aligned | aligned | 158.60 | 162.26 |
| 62 | Miss independent | 191.28 | 191.28 | 192.44 | 193.54 | +0.00 | +1.10 | 2/2 | 2/2 | aligned | aligned | - | - |
| 63 | Mmm | 192.54 | 193.64 | 193.88 | 194.54 | +1.10 | +0.67 | 1/1 | 1/1 | aligned | aligned | - | - |
| 64 | Her favorite thing to say-- "don't worry, I've got it" | 194.97 | 194.54 | 199.62 | 199.27 | -0.43 | -0.35 | 10/10 | 10/10 | aligned | aligned | - | 198.90 |
| 65 | Mmm | 200.52 | 198.78 | 200.58 | 200.28 | -1.75 | -0.31 | 1/1 | 1/1 | aligned | spaced | - | - |

moved non-target lines: 7

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 2 [(9, 2, 4), (71, 2, 4)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 6, after 7
| 5 | 4 | 0:15.88 | 16.66 | 16.66 | 15.90 | 15.88 | 0.76 | 0.78 | no |
| 6 | 5 | 0:17.36 | 17.40 | 17.38 | 17.36 | 17.36 | 0.03 | 0.01 | no |
| 7 | 6 | 0:19.51 | 21.28 | 21.28 | 19.53 | 19.51 | 1.75 | 1.76 | no |
| 37 | 36 | 1:57.13 | 117.88 | 117.88 | 117.13 | 117.13 | 0.76 | 0.76 | no |
| 38 | 37 | 1:58.91 | 119.16 | 119.15 | 118.79 | 118.91 | 0.38 | 0.24 | no |
| 65 | 64 | 3:18.78 | 199.62 | 199.27 | 200.52 | 198.78 | 0.00 | 0.50 | no |
| 78 | 77 | 3:56.91 | 237.02 | 237.02 | 236.89 | 236.91 | 0.13 | 0.11 | no |

**Song Info stats**

- before: Timed tile `96%` / `4 guessed · 4 words` warn=True; poor=False; guessed=4; cue_lines={'aligned': 82, 'realigned': 3, 'paced': 4}; words_guessed=None/None lines; words_missing=4/2 lines; bar: Aligned 82, Re-aligned 3, Spaced from caption 4; note: Missing from the screen: 4 words in 2 lines. Regenerate to show them. (warn True)
- after: Timed tile `94%` / `5 guessed · 2 words` warn=False; poor=False; guessed=5; cue_lines={'aligned': 80, 'realigned': 4, 'paced': 5}; words_guessed=2/2 lines; words_missing=None/None lines; bar: Aligned 80, Re-aligned 4, Spaced from caption 5; note: Guessed timing: 2 words in 2 lines. (warn False)

#### Pocahontas (9ThO76peOw0); lines 37; before 2026-10-30T00:36:59+00:00 -> after 2026-10-31T18:04:19+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 4, 'widened': 1, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.146, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 3, "realigned_line_ids": [6, 7, 8]}
joint_stats.repace after: {"offset_s": -0.152, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 3, "realigned_line_ids": [6, 7, 8], "n_guessed_words": 0, "guessed_word_line_ids": []}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 36 | You can paint with all the colors of the wind | 10 | 6 | 10 | aligned | aligned | 174.13 | 174.13 | 178.87 | 183.95 | - | 184.92 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

moved non-target lines: 0

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 1 [(36, 6, 10)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 0, after 0

**Song Info stats**

- before: Timed tile `100%` / `0 guessed · 4 words` warn=True; poor=False; guessed=0; cue_lines={'aligned': 34, 'realigned': 3, 'paced': 0}; words_guessed=None/None lines; words_missing=4/1 lines; bar: Aligned 34, Re-aligned 3; note: Missing from the screen: 4 words in 1 line. Regenerate to show them. (warn True)
- after: Timed tile `100%` / `0 guessed` warn=False; poor=False; guessed=0; cue_lines={'aligned': 34, 'realigned': 3, 'paced': 0}; words_guessed=0/0 lines; words_missing=None/None lines; bar: Aligned 34, Re-aligned 3; note: None (warn False)

#### Incomplete (WVe80iZtlYU); lines 27; before 2026-10-29T17:52:54+00:00 -> after 2026-10-31T17:50:29+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 18, 'widened': 14, 'fallback': 3}
joint_stats.repace before: {"offset_s": -0.69, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 0, "realigned_line_ids": []}
joint_stats.repace after: {"offset_s": -0.686, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 0, "realigned_line_ids": [], "n_guessed_words": 0, "guessed_word_line_ids": []}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | Where I'm going is anybody's guess | 6 | 4 | 6 | aligned | aligned | 39.69 | 39.69 | 43.51 | 47.20 | 39.20 | 46.04 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

moved non-target lines: 0

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 1 [(3, 4, 6)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 0, after 0

**Song Info stats**

- before: Timed tile `100%` / `0 guessed · 2 words` warn=True; poor=False; guessed=0; cue_lines={'aligned': 27, 'realigned': 0, 'paced': 0}; words_guessed=None/None lines; words_missing=2/1 lines; bar: Aligned 27; note: Missing from the screen: 2 words in 1 line. Regenerate to show them. (warn True)
- after: Timed tile `100%` / `0 guessed` warn=False; poor=False; guessed=0; cue_lines={'aligned': 27, 'realigned': 0, 'paced': 0}; words_guessed=0/0 lines; words_missing=None/None lines; bar: Aligned 27; note: None (warn False)

#### Castle On The Hill (K0ibBPhiaG0); lines 56; before 2026-10-29T23:16:15+00:00 -> after 2026-10-31T17:58:10+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 9, 'widened': 3, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.17, "n_repaced": 1, "repaced_line_ids": [37], "n_realigned": 1, "realigned_line_ids": [36]}
joint_stats.repace after: {"offset_s": -0.17, "n_repaced": 1, "repaced_line_ids": [37], "n_realigned": 1, "realigned_line_ids": [36], "n_guessed_words": 2, "guessed_word_line_ids": [46]}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 46 | And I'm on my way | 5 | 3 | 5 | aligned | aligned +guessed words | 226.67 | 226.67 | 228.80 | 228.80 | 226.74 | 228.88 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

moved non-target lines: 0

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 1 [(46, 3, 5)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 1, after 1
| 38 | 37 | 2:58.92 | 186.17 | 186.17 | 178.92 | 178.92 | 7.25 | 7.25 | no |

**Song Info stats**

- before: Timed tile `98%` / `1 guessed · 2 words` warn=True; poor=False; guessed=1; cue_lines={'aligned': 54, 'realigned': 1, 'paced': 1}; words_guessed=None/None lines; words_missing=2/1 lines; bar: Aligned 54, Re-aligned 1, Spaced from caption 1; note: Missing from the screen: 2 words in 1 line. Regenerate to show them. (warn True)
- after: Timed tile `98%` / `1 guessed · 2 words` warn=False; poor=False; guessed=1; cue_lines={'aligned': 54, 'realigned': 1, 'paced': 1}; words_guessed=2/1 lines; words_missing=None/None lines; bar: Aligned 54, Re-aligned 1, Spaced from caption 1; note: Guessed timing: 2 words in 1 line. (warn False)

#### My Heart Will Go On (9bFHsd3o1w0); lines 27; before 2026-10-29T23:12:32+00:00 -> after 2026-10-31T17:56:30+00:00
schema before 11 after 11; method cue_align
joint_stats.edges after: {'n': 5, 'widened': 1, 'fallback': 0}
joint_stats.repace before: {"offset_s": -0.19, "n_repaced": 2, "repaced_line_ids": [10, 19], "n_realigned": 4, "realigned_line_ids": [8, 24, 25, 26]}
joint_stats.repace after: {"offset_s": -0.377, "n_repaced": 4, "repaced_line_ids": [3, 19, 25, 26], "n_realigned": 1, "realigned_line_ids": [8], "n_guessed_words": 0, "guessed_word_line_ids": []}

**Targets**

| L | text | tokens | words before | words after | source before | source after | start b | start a | end b | end a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | And you're here in my heart | 6 | 4 | 6 | aligned | aligned | 87.15 | 87.11 | 92.13 | 92.25 | 87.87 | 92.26 |

**Moved lines (start or end moved > 0.3 s), non-target**

| L | text | start b | start a | end b | end a | d start | d end | words b | words a | source b | source a | heard first | heard last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Every night in my dreams | 22.20 | 21.40 | 25.33 | 25.38 | -0.80 | +0.06 | 5/5 | 5/5 | aligned | aligned | 20.75 | 24.94 |
| 2 | That is how I know you go on | 30.31 | 31.00 | 38.78 | 38.75 | +0.69 | -0.03 | 8/8 | 8/8 | aligned | aligned | 30.68 | 37.12 |
| 3 | Far across the distance | 40.70 | 40.37 | 43.97 | 44.67 | -0.33 | +0.71 | 4/4 | 4/4 | aligned | spaced | - | 43.96 |
| 4 | And spaces between us | 43.97 | 45.13 | 50.55 | 50.23 | +1.16 | -0.32 | 4/4 | 4/4 | aligned | aligned | - | 49.86 |
| 10 | And my heart will go on and on | 92.23 | 92.25 | 101.56 | 100.35 | +0.02 | -1.21 | 8/8 | 8/8 | spaced | aligned | 92.30 | 99.36 |
| 14 | Love was when I loved you | 128.31 | 127.83 | 131.65 | 131.63 | -0.48 | -0.02 | 6/6 | 6/6 | aligned | aligned | - | 131.58 |
| 15 | One true time I hold to | 132.20 | 132.20 | 136.73 | 137.12 | +0.00 | +0.40 | 6/6 | 6/6 | aligned | aligned | 131.90 | - |
| 16 | In my life we'll always go on | 136.73 | 137.63 | 146.00 | 145.95 | +0.90 | -0.05 | 7/7 | 7/7 | aligned | aligned | 137.44 | 143.36 |
| 17 | Near, far, wherever you are | 148.16 | 148.56 | 155.18 | 155.18 | +0.40 | +0.00 | 5/5 | 5/5 | aligned | aligned | - | 155.16 |
| 24 | We'll stay forever this way | 224.96 | 224.93 | 233.12 | 232.80 | -0.04 | -0.32 | 5/5 | 5/5 | re-aligned | aligned | 225.44 | 232.70 |

moved non-target lines: 10

**Words shown vs tokens, all lines (after / before)**

lines with fewer words than tokens: before 1 [(9, 4, 6)]; after 0 []
lines with no words: before []; after []; more words than tokens after: []

**Overlaps** (line starts before the previous line's end)

| L | prev L | start | prev end b | prev end a | start b | start a | overlap b | overlap a | captions overlap |
|---|---|---|---|---|---|---|---|---|---|
overlapping pairs: before 1, after 1
| 20 | 19 | 2:54.38 | 174.63 | 174.45 | 174.38 | 174.38 | 0.26 | 0.07 | no |

**Song Info stats**

- before: Timed tile `93%` / `2 guessed · 2 words` warn=True; poor=False; guessed=2; cue_lines={'aligned': 21, 'realigned': 4, 'paced': 2}; words_guessed=None/None lines; words_missing=2/1 lines; bar: Aligned 21, Re-aligned 4, Spaced from caption 2; note: Missing from the screen: 2 words in 1 line. Regenerate to show them. (warn True)
- after: Timed tile `85%` / `4 guessed` warn=False; poor=False; guessed=4; cue_lines={'aligned': 22, 'realigned': 1, 'paced': 4}; words_guessed=0/0 lines; words_missing=None/None lines; bar: Aligned 22, Re-aligned 1, Spaced from caption 4; note: None (warn False)

**R29w ASS word times** (`asswords.py`: `word[start-end]`, seconds; per song `== <id> <line ids>`; before = the backup, after = the library).

```
== AJWtLf4-WWs 6 7 26 31 32 37
L6 before: You[44.05-44.43] might[44.43-45.53] think[45.53-46.57] that[46.57-47.03] I[47.41-47.53] won't[47.53-48.03] make[48.34-48.45] it[48.45-50.33]
L6 after:  You[43.9-44.43] might[44.43-45.53] think[45.53-46.55] that[46.55-47.03] I[47.03-47.69] won't[47.69-48.01] make[48.01-48.45] it[48.45-49.67] on[49.77-49.97] my[49.97-50.21] own[50.54-50.65]
L7 before: But[50.43-51.55] now[51.55-52.11] I'm[52.27-52.75] stronger[52.75-54.44] than[54.54-54.65] yesterday[55.14-55.95]
L7 after:  But[50.43-51.55] now[51.55-52.09] I'm[52.26-52.75] stronger[52.75-54.28] than[54.38-54.69] yesterday[55.79-55.95]
L26 before: Here[141.71-141.93] I[141.93-142.05] go,[142.44-142.57] here[143.01-143.11] I[143.11-143.23] go,[143.23-144.11] here[144.21-144.31] I[144.31-144.89] go,[144.89-144.99] here[145.15-145.62] I[145.62-145.72] go,[145.72-146.35] here[146.45-146.97]
L26 after:  Here[141.71-141.93] I[141.93-142.05] go,[142.44-142.57] here[143.01-143.11] I[143.11-143.23] go,[143.23-144.11] here[144.21-144.31] I[144.31-144.89] go,[144.89-144.99] here[145.15-145.62] I[145.62-145.72] go,[145.72-146.35] here[146.45-146.97] I[146.97-147.09] go[147.09-147.21]
L31 before: My[169.82-170.2] loneliness[170.64-171.38] ain't[171.73-172.32] killing[172.32-173.62] me[173.72-174.1] no[174.1-174.5] more[174.5-176.46]
L31 after:  My[169.82-170.2] loneliness[170.64-171.38] ain't[171.73-172.32] killing[172.32-173.62] me[173.72-174.1] no[174.1-174.5] more[174.5-175.56]
L32 before: I,[176.56-177.26] I'm[177.36-178.1] stronger[178.1-178.98] than[178.98-182.56]
L32 after:  I,[175.16-177.9] I'm[178.24-178.34] stronger[178.34-179.4] than[179.4-180.26] yesterday[180.26-182.56]
L37 before: My[201.69-202.55] loneliness[202.55-203.89] ain't[204.38-205.19] killing[205.19-205.72] me[205.82-206.13] no[206.13-209.3]
L37 after:  My[201.71-202.59] loneliness[202.59-204.2] ain't[204.3-205.21] killing[205.21-205.72] me[205.82-206.17] no[206.32-206.67] more,[206.79-207.13] no[207.55-207.67] more[207.67-208.9]
== 450p7goxZqg 29 40 46 49 55
L29 before: I[131.71-131.9] can't[131.9-132.22] stop[132.36-132.78] singing,[133.13-133.72] it's[133.9-134.43] ringing[134.43-134.95] in[135.01-135.81] my[135.81-136.73] head[136.73-137.25]
L29 after:  I[131.71-131.9] can't[131.9-132.22] stop[132.36-132.78] singing,[133.13-133.72] it's[133.9-134.43] ringing[134.43-134.95] in[135.01-135.99] my[135.99-137.13] head[137.61-138.11] for[138.11-138.35] you[138.51-139.83]
L40 before: 'Cause[183.07-184.0] I[184.0-184.25] give[184.25-185.25] you[185.25-186.0] all[186.0-186.75] of[186.75-187.25] me[187.25-188.84]
L40 after:  'Cause[182.3-183.35] I[183.35-183.55] give[183.55-183.79] you[183.79-184.09] all[184.09-186.25] of[186.35-187.85] me[187.91-188.9]
L46 before: 'Cause[214.52-214.82] all[214.82-216.12] of[216.22-216.4] me[216.4-216.9] loves[216.9-218.28] all[218.28-220.82]
L46 after:  'Cause[214.52-214.8] all[214.8-215.88] of[216.01-216.4] me[216.4-216.88] loves[216.88-218.3] all[218.3-220.03] of[220.13-220.28] you[220.28-220.82]
L49 before: Give[229.05-229.33] your[229.33-229.89] all[229.89-230.73] to[231.08-231.67] me,[232.01-232.58] I'll[232.58-232.84] give[232.84-233.14] my[233.14-233.7] all[233.86-236.09]
L49 after:  Give[229.05-229.33] your[229.33-229.89] all[229.89-230.71] to[230.83-231.67] me,[232.03-232.63] I'll[232.79-232.89] give[232.89-233.21] my[233.21-233.77] all[234.09-234.63] to[234.97-235.53] you[235.53-236.17]
L55 before: And[266.89-267.13] you[267.13-267.39] give[267.39-267.59] me[267.59-267.87] all[267.87-269.03] of[269.03-269.19] you,[269.19-269.29] oh[269.29-271.04]
L55 after:  And[266.89-267.13] you[267.13-267.39] give[267.39-267.61] me[267.61-267.87] all[267.87-269.38] of[269.48-270.98] you,[271.79-273.07] oh[273.15-275.05]
== hLQl3WQQoQ0 16 33 47 48 49
L16 before: I[79.18-80.28] wish[80.28-80.64] nothing[80.64-81.2] but[81.65-81.8] the[81.8-82.18] best[82.32-83.27] for[83.27-86.59]
L16 after:  I[79.18-80.28] wish[80.28-80.64] nothing[80.64-81.16] but[81.32-81.8] the[81.8-82.78] best[82.88-83.3] for[83.3-84.63] you,[84.73-84.92] too[85.36-86.46]
L33 before: I[161.83-163.86] wish[163.96-164.17] nothing[164.62-164.77] but[165.24-165.4] the[165.4-165.8] best[165.92-166.74] for[166.87-168.44] you,[168.54-170.83]
L33 after:  I[161.85-163.86] wish[163.96-164.17] nothing[164.62-164.77] but[164.93-165.41] the[165.41-165.79] best[166.14-166.73] for[167.1-167.71] you,[168.09-168.73] too[168.95-170.78]
L47 before: But[226.99-227.16] sometimes[227.49-227.6] it[227.91-228.02] hurts[228.2-228.74] instead[228.74-231.6]
L47 after:  But[226.99-227.14] sometimes[227.14-227.54] it[227.9-228.02] hurts[228.02-228.74] instead[228.74-230.62]
L48 before: Never[232.64-233.17] mind,[233.17-233.9] I'll[233.96-234.06] find[234.06-234.62] someone[235.51-236.2] like[236.3-237.07] you[237.17-237.76]
L48 after:  Never[230.71-232.21] mind,[233.18-233.91] I'll[233.97-234.07] find[234.07-234.71] someone[234.71-236.23] like[236.33-236.9] you[237.0-237.7]
L49 before: I[237.85-239.12] wish[239.12-239.5] nothing[240.02-240.12] but[240.43-240.64] the[240.75-241.08] best[241.46-242.08] for[242.39-243.53] you,[243.63-245.74]
L49 after:  I[237.77-239.12] wish[239.12-239.5] nothing[239.98-240.08] but[240.4-240.7] the[240.7-240.8] best[240.8-241.1] for[241.1-241.4] you,[241.4-241.7] too[241.7-242.0]
== C-u5WLJ9Yk4 20 30
L20 before: Tell[105.24-105.38] me,[105.71-105.82] baby,[106.06-106.84] 'cause[107.08-107.46] I[107.46-107.64] need[107.64-108.0] to[108.0-108.26] know[108.26-108.82] now,[109.18-110.85]
L20 after:  Tell[105.26-105.41] me,[105.72-106.41] baby,[106.51-107.35] 'cause[107.35-107.47] I[107.47-107.65] need[107.65-108.01] to[108.01-108.27] know[108.27-108.85] now,[108.85-109.75] oh[109.93-110.03] because[110.03-110.95]
L30 before: I[161.18-161.47] must[161.57-161.88] confess,[161.88-163.22] that[163.22-163.76] my[163.76-164.18] loneliness[164.18-164.92] is[164.92-166.4] killing[166.4-169.49]
L30 after:  I[161.54-161.64] must[161.64-161.98] confess,[161.98-162.83] that[163.24-163.86] my[163.86-164.3] loneliness[164.3-165.02] is[165.02-166.52] killing[166.54-167.0] me[167.13-167.54] now[167.54-169.57]
== k6M5C-oKw9k 9 50 51 64 65 71
L9 before: Good[24.61-24.71] morning.[24.71-25.06]
L9 after:  Good[23.44-24.65] morning.[24.65-25.2] God[25.23-25.83] damn.[25.83-26.43]
L50 before: And[155.09-155.37] her[155.37-155.53] bills[155.53-156.01] are[156.01-156.19] paid[156.19-156.57] on[156.57-156.83] time[156.83-158.61]
L50 after:  And[155.09-155.37] her[155.37-155.53] bills[155.53-156.01] are[156.01-156.19] paid[156.19-156.57] on[156.57-156.83] time[156.94-157.69]
L51 before: She[159.46-159.58] made[159.58-160.0] for[160.0-160.34] a[160.34-160.6] boss,[160.6-161.02] only[161.14-161.64] a[161.64-161.94] boss[161.94-162.7]
L51 after:  She[157.7-159.2] made[159.58-159.98] for[159.98-160.34] a[160.34-160.58] boss,[160.58-161.02] only[161.14-161.66] a[161.66-161.86] boss[161.86-162.7]
L64 before: Her[194.97-195.82] favorite[195.82-196.12] thing[196.12-196.5] to[196.5-196.68] say--[196.68-196.98] "don't[196.98-197.32] worry,[197.32-198.06] I've[198.12-198.42] got[198.42-198.6] it"[198.6-199.62]
L64 after:  Her[194.54-195.82] favorite[195.82-196.12] thing[196.12-196.48] to[196.48-196.68] say--[196.68-196.98] "don't[196.98-197.3] worry,[197.3-198.06] I've[198.16-198.42] got[198.42-198.62] it"[198.78-199.27]
L65 before: Mmm[200.52-200.62]
L65 after:  Mmm[198.77-200.27]
L71 before: Ooh[216.36-217.86] yeah,[217.94-218.4]
L71 after:  Ooh[216.2-217.7] yeah,[217.94-218.4] ooh[218.82-218.95] yeah[218.95-219.08]
== 9ThO76peOw0 36
L36 before: You[174.12-175.1] can[175.6-175.76] paint[175.93-176.84] with[177.77-177.96] all[178.32-178.44] the[178.54-178.85]
L36 after:  You[174.12-175.52] can[175.62-176.29] paint[176.39-176.92] with[177.77-177.94] all[178.3-178.42] the[178.52-178.84] colors[179.56-180.07] of[180.46-182.57] the[182.67-182.84] wind[182.84-183.94]
== WVe80iZtlYU 3
L3 before: Where[39.68-39.82] I'm[39.82-40.76] going[41.23-42.0] is[42.0-43.5]
L3 after:  Where[39.68-39.82] I'm[39.82-40.76] going[41.23-42.0] is[42.0-43.5] anybody's[44.16-45.66] guess[45.74-47.19]
== K0ibBPhiaG0 46
L46 before: And[226.67-226.93] I'm[227.43-227.59] on[227.59-228.8]
L46 after:  And[226.67-226.93] I'm[227.43-227.59] on[227.59-227.91] my[227.91-228.17] way[228.17-228.8]
== 9bFHsd3o1w0 9 25 26
L9 before: And[87.14-88.46] you're[88.46-89.04] here[89.04-89.68] in[89.68-92.12]
L9 after:  And[87.1-88.48] you're[88.61-89.02] here[89.02-90.04] in[90.14-90.76] my[90.9-91.32] heart[91.9-92.24]
L25 before: You[233.5-233.89] are[233.89-234.59] safe[234.59-235.21] in[235.21-236.17] my[236.67-236.83] heart[237.12-237.69] and[237.69-238.29]
L25 after:  You[233.42-233.66] are[233.66-234.41] safe[234.41-235.41] in[235.41-235.91] my[235.91-236.41] heart[236.41-237.66] and[237.66-238.41]
L26 before: My[239.03-239.31] heart[239.45-239.93] will[239.96-240.63] go[241.02-241.67] on[241.67-243.77] and[243.87-243.97] on[243.97-249.55]
L26 after:  My[238.94-239.55] heart[239.55-242.3] will[242.4-243.9] go[244.68-245.82] on[245.82-246.96] and[246.96-248.46] on[248.67-249.81]
```

**R29h vs_heard** (`vs_heard.py`; per song tuple = lines with a heard first word, lines starting > 0.5 s before it before, after, lines ending > 0.3 s before the heard last word before, after).

```
song | lines with heard first | start >0.5 s before heard: before, after | heard last >0.3 s after end: before, after
Stronger (23, 10, 12, 1, 1)
All of Me (48, 1, 2, 3, 1)
Someone Like You (46, 7, 8, 2, 1)
Baby One More Time (40, 10, 10, 1, 1)
Miss Independent (53, 9, 10, 1, 1)
Pocahontas (31, 4, 4, 1, 1)
Incomplete (19, 2, 2, 3, 2)
Castle On The Hill (45, 2, 3, 0, 0)
My Heart Will Go On (20, 7, 7, 0, 0)

start got earlier than heard by > 0.5 s and by 0.3 s more than before: song, L, m:ss, heard_first, start_b, start_a, start_b-heard, start_a-heard
('Stronger', 18, '1:45.06', 105.62, 105.36, 105.05799999999999, -0.26, -0.56)
('Stronger', 32, '2:55.16', 176.16, 176.56199999999998, 175.16199999999998, 0.4, -1.0)
('All of Me', 40, '3:02.30', 183.136, 183.075, 182.3015, -0.06, -0.83)
('Someone Like You', 48, '3:50.72', 232.768, 232.65, 230.716, -0.12, -2.05)
('Miss Independent', 51, '2:37.70', 158.6, 159.467, 157.703, 0.87, -0.9)

end got further before heard end (> 0.3 s, and 0.3 s more than before): song, L, m:ss, heard_last, end_b, end_a, heard-end_b, heard-end_a
('Someone Like You', 49, '3:57.77', 245.28, 245.75, 242.00699999999998, -0.47, 3.27)
```

## Hand-off prompt (executor)

```
Execute plans/cue-align-windows.md on branch cue_align_windows (HEAD daf183a, plan
untracked). Read Goal, Decisions, Library facts, Design, Phases and Rules first. Start at
Phase 0, record the baseline, then Phase 1. Stop at GATE A if any pass criterion fails,
and before Phase 5's GPU run until Ken says go. Log every step in the Results log.
```

Phase 5b (after Ken agrees to Decision 12):

```
Branch cue_align_windows. Plan: plans/cue-align-windows.md, Decision 12 and Phase 5b.
Done, don't redo: Phases 1-5, the review fixes, rows 25-39. Do Phase 5b steps 1-5 (per-line
windows, clamp, tests, CPU check, two commits). Stop before step 6's GPU rerun until Ken
stops the app and says go; then stop at GATE B with Ken's list of changed lines.
```
