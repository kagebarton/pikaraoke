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
   Superseded by Decision 13: the words are zero-length, not timed (rows 43, 45).
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

Ken, 2026-10-31, ratifying Opus's proposal after the replays (rows 43-46):

13. **A zero-length word counts as a missing word; a re-aligned line may not start on
    the previous line; a rescue window ends where the singing stops before the next
    line.**
    - Why: She Used To Be Mine 0:33-0:40 (Ken's "fast sweep") is not timed by the
      model. The section align puts line 6's `I used to be` and line 7's `Although` at
      one instant (36.09): 4 of line 6's 8 words, 1 of line 7's 3. "Mostly instant"
      makes a line bad only above half, so both pass as clean and are never rescued
      (rows 43, 45). Across the 10 replay songs, 92 of 478 section lines carry at least
      one such word (row 45).
    - Ruled:
      - `repace_bad_lines`: a line is complete only when it has a word of at least
        `INSTANT_WORD_DUR_S` for every token, and a re-align replaces a placed line
        only when it has more such words than the line. Nothing else about the rescue
        changes: a zero-length word stays on screen as it is (no guess replaces it),
        and "mostly instant" still makes a line bad.
      - The guard (review finding 7, row 44): after `_trim_lead_in`, a re-aligned
        line's first word may not start before the previous line's last word ends
        (the line before it in the rescue's output). If it does, the first word starts
        at that end when at least `INSTANT_WORD_DUR_S` of it is left; otherwise the
        re-align is not kept. It applies to every re-align, not only those asked
        because of zero-length words.
      - `_volume_end`: the singing stops at the quiet stretch of at least
        `RELEASE_QUIET_S` that runs into the next line's cue start, not at the first
        one. If the stretch before the next cue is shorter, or there is none, the line
        sang into the next one and the window ends at that cue's start, as today. Pad,
        midpoint and `MAX_HOLD_S` are unchanged. Why: with the audio-clock search
        (`8cc7588`) the first long-enough stretch can be a breath inside the line:
        Incomplete 0:45 is quiet 43.23-44.15 after "is", then sings "anybody's guess"
        to 46.38 (row 45). Supersedes Decision 11's "first quiet stretch" for the
        per-line window.
      - Rescue stats and log line gain `crammed_line_ids`: lines with a word for every
        token, asked for a re-align because some are zero-length.
      - Stat 1 (Song Info) is unchanged. Whether it should count zero-length words left
        on screen is for after GATE B (Phase 6).
    - Measured (rows 45-46):
      - Zero-length words counted as missing, plus the guard (CPU over the replay's
        saved results), against the committed code on the 10 songs, lines that differ
        after the snaps: first word against the transcriber's, closer 25 / within
        0.05 s 13 / further 6; last word 17 / 22 / 3; zero-length words 94 -> 49;
        lines starting before the previous line's end 13 -> 16. Without the guard:
        further starts 10, such lines 32.
      - She Used To Be Mine: line 6's last four words 36.50-38.14 (heard
        36.52-38.02); line 7 starts at line 6's end instead of 2.2 s early.
      - New window end: 4 of 113 asked windows move. Targets timed in full by the model
        16 of 18 (Incomplete 3 and Stronger 26 added); left: Miss Independent 9 and 71
        (row 33's unsung caption words).
      - Cost: 75 more one-line aligns across the 10 songs (209 aligns in all, against
        134).
      - Not measured: the guard on lines the committed code already re-aligns. The GPU
        rerun (Phase 5c) measures it.
    - Decision 9 is superseded: She Used To Be Mine joins the rerun as a tenth song.

Opus, after the row-51 review, 2026-11-02. Proposed; Ken decides at GATE B:

14. **Zero-length words a rescue does not time stay as they are (review finding 4).**
    - Finding: a crammed line whose re-align fails or is not kept keeps its zero-length
      words, and the guess pass skips any line with a word for every token, so they are
      never guessed. A partial line missing the same words gets them guessed.
    - On screen: `generate_ass` floors every word at `\kf10`, so a zero-length word is
      shown and fills in 0.1 s beside its neighbour, as before the branch (row 43, She
      Used To Be Mine L6 `{\kf10}I {\kf10}used {\kf10}to {\kf10}be`). Not dropped.
    - Options: (a) as Decision 13 rules. (b) Guess them: drop a crammed line's
      zero-length words before the guess pass so `_with_guessed_words` fills those
      tokens. Needs a fallback for a line with no timed word left (re-pace from its
      cue). Where the neighbours touch, the guesses share the neighbour's slot, often
      still under `INSTANT_WORD_DUR_S` each.
    - Proposed: (a) through GATE B. (b) needs no GPU to measure: the guess pass runs on
      the rescue's output, so a CPU replay over the rerun's `cue_inputs` (complete
      since row 53) compares (a) and (b) on all 10 songs. Ken's listening at GATE B
      says whether the leftover 0.1 s fills matter.
    - Separate, older than this branch: the `\kf10` floor's added time is never taken
      back, so a run of floored words pushes the rest of the line late until its next
      gap (row 43: overrun >= 0.1 s on 413 lines in 80 songs, >= 0.3 s on 34 in 23).
      For `plans/open-issues.md` at landing.
15. **The crammed trigger stays at one zero-length word (review finding 5).**
    - Finding: at `INSTANT_WORD_DUR_S` 0.05 a placed line with one quick word ("a",
      "I") is crammed: one more one-line align, and a re-align with one more such word
      replaces the section line even if another of its words moved.
    - Measured: row 45, 75 more one-line aligns across the 10 songs (209 against 134);
      on the lines that changed, first word against the transcriber's closer 25 /
      within 0.05 s 13 / further 6, last word 17 / 22 / 3. Row 49 crammed lines:
      Stronger 8, Castle 12, Incomplete 3. A kept re-align still passes
      `_line_in_span` against its aimed window and the previous-line guard.
    - Options: (a) as Decision 13 rules. (b) Crammed only with two or more zero-length
      words, or a zero-length share over a fraction. (c) Keep a crammed line's re-align
      only if no timed word moves more than a bound.
    - Proposed: (a) for the rerun. (b) misses Decision 13's own case: She Used To Be
      Mine L7 has 1 zero-length word of 3 (`Although`, row 43). The rerun's per-line
      compare (`crammed_line_ids`, first and last word against the transcriber, Ken's
      list) shows whether a good line got worse; (c) only if it does.

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

Steps 1-5 are done (rows 40-42; review fixes row 44). Steps 6-7 run as Phase 5c's
rerun, after Decision 13's code.

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

### Phase 5c: zero-length words, the guard, the window end -> commits -> GPU rerun -> GATE B (Ken)

Per Decision 13. Run `graphify affected` on `repace_bad_lines`, `_volume_end` and
`_trim_lead_in` first.

1. **Window end** (`_volume_end`, its docstring, and the module docstring where it
   describes the rescue window). Tests in `TestRescueWindow`: a pause of at least
   `RELEASE_QUIET_S` inside the line, then singing, then quiet into the next cue: the
   window ends a pad into that last quiet stretch (Incomplete 3's shape). A long pause
   inside the line, then singing that runs into the next cue: the next cue's start. The
   existing tests should pass unchanged (their pauses are under `RELEASE_QUIET_S`);
   record any that do not. Commit `fix(cue_align): a rescue window ends where the
   singing stops before the next line`; log a row.
2. **Zero-length words and the guard** (`repace_bad_lines`; the guard beside
   `_trim_lead_in`; `crammed_line_ids` in the stats and the rescue log line;
   docstrings). Tests: a placed line with every token, half of them zero-length, asks
   a re-align and keeps one that times more; it keeps its own words when the re-align
   times no more; a line with every token timed asks nothing; a first word starting
   before the previous line's last word ends is trimmed to that end; with under
   `INSTANT_WORD_DUR_S` left the re-align is not kept and the line keeps its own words;
   a first word after that end is untouched; `crammed_line_ids` lists only the
   zero-length-word line. Commit `fix(cue_align): words the aligner left zero-length
   are rescued like missing ones`; log a row.
3. **CPU check before each commit** (no GPU). Songs: Stronger, Castle, Incomplete. Data
   in the 39d269ea scratchpad: `cram_<yid>.json` (`sections`, `spans`, `duration`,
   `sub`, `stem`) and `alt_<yid>.json` (`realigns`: `lid`, `w0`, `w1`, raw `words`;
   `out`). Envelope: `probe_edges.load_env` (323ba938 scratchpad) of
   `~/pikaraoke-songs/<sub>/<stem>---<sub>.m4a`. Display and align lines from the
   library bundle. Call `repace_bad_lines(sections, spans, lines, align_lines,
   duration=..., env=..., realign=<the saved words for (lid, w0, w1)>)`.
   - After step 1: every window `realign` receives is one of that line's saved windows.
   - After step 2: the windows equal the saved ones call for call. With the guard
     patched out (in the check only), the output equals `alt_<yid>.json` `out` line
     for line. With it on, only lines whose first word started before the previous
     line's end differ, each trimmed or not kept per Decision 13.
   - A window with no saved words is a mismatch: record it and stop.
4. **Bundle, only if Ken agrees.** The cue route's bundle keeps the section align's line
   objects before the rescue, and every one-line re-align (`line_id`, `w0`, `w1`, the
   words it returned, or null), as a new top-level key (`cue_inputs`, with `sections`
   and `realigns`). Additive, no schema bump (Decision 6). `align_song` returns them,
   `_run_cue_align` passes them on, `build_bundle` writes them. Tests in the capture
   and stage tests. Commit `feat(alignment_capture): cue bundles keep the section words
   and re-aligns`; log a row. Why: rows 43-46 needed GPU replays only because these
   are not saved. With them, the rescue's rules and both snaps re-run over the corpus
   on CPU.
4b. **Review fixes** (row 51; rows 52-54): the window end lets the next singer come in
   early and merges a blip into the quiet; `cue_inputs` gains `spans`; the guard skips
   a fill and a caption sung over the line (`DUET_OVERLAP_S`). Findings 4 and 5 are
   Decisions 14-15, proposed for GATE B.
5. **GPU rerun**, after Ken's go with the app stopped: Phase 5b step 6, with She Used
   To Be Mine (`53GIADHxVzM`) added to Phase 5's song list. Its pre-branch bundle and
   ASS are in the library today and go into the run's backup. Dry run first. Same
   compares as step 6, plus: per song, lines with a zero-length word and lines starting
   before the previous line's end, against the pre-branch backup and this run's
   backup; `crammed_line_ids`; She Used To Be Mine 0:33-0:40 word by word against the
   transcriber; the 18 targets (expected: 16 timed in full by the model); the
   Pocahontas `.lrclib.srt` hash; Castle L1 and L29 (row 52's moved windows) when
   rescued; `cue_inputs.spans` present in every cue bundle.
6. Log raw tables; give Ken `song - m:ss - line text - what changed` for every changed
   line, targets and She Used To Be Mine first; stop at GATE B.

Steps 5-6 ran on 2026-11-02 (rows 55-61, blocks R55*). GATE B is Ken's.

### Phase 6: after GATE B

Only on Ken's word: land on `dev` (Branches and Archive Tags in `CLAUDE.md`: copy the
code commits one by one, no plan file), then in `plans/open-issues.md` on `dev`, record
what remains (e.g. any test line still guessed, the not-the-window group, the
remaining 16 songs needing a Regenerate, review findings 4, 8 and 10 from row 24,
review findings 3-4 and 6 from row 44, review findings 3, 6 and 8-10 from row 51,
Decisions 14-15 as Ken rules them, the `\kf10` floor drift (Decision 14, row 43),
Decision 12's three out-of-scope items, and Decision 13's stat 1 question; update or
close the She Used To Be Mine entry per GATE B), and retire the branch as `archive/cue_align_windows`.

Open before landing (row 44), each Ken's call:

- **Finding 5, the last line's window has no hold cap.** Kept uncapped on purpose
  (`_volume_tail`: the final note is often the longest), but outro ad-libs widen the
  window and the span the re-align is checked against. A cap needs the length of real
  final holds across the cue library first.
- **Finding 7, the lead-in trim can accept a first word on the previous line's held
  note.** A guard against overlapping the previous line's words is possible; how often
  it happens is not measured.

For `plans/open-issues.md` at landing (row 44):

- **Findings 3-4, repeated tokens.** In-order matching puts a word on the earliest
  repeat of its token; the time match puts it on a later one. The fix is one
  assignment: each word's token index carried on the line object from
  `_match_words_to_tokens`, which also removes `_assign_in_order`. Same prerequisite
  as Decision 12's unruled splice of section and re-align words.
- **Finding 6, duet ending.** The song's last line is the last by index, not the
  latest-ending one, so an earlier line held past the last cue gets no tail window
  and the last line's tail runs over that other singer's note.

## Rules for the executor

- `CLAUDE.md` applies in full: conda env `pik`, pytest with mocked I/O, pre-commit on
  changed files only, Self-Review before each commit, no debug prints, commits grouped
  by feature with their tests.
- No GPU outside Phases 5, 5b and 5c, and each rerun only after Ken says go.
- The library at `~/pikaraoke-songs` is read-only outside those reruns.
- Do not re-derive the Library facts; they are measured. She Used To Be Mine is in
  scope since Decision 13.
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
| 40 | 2026-10-31 | 5b | Sonnet, Phase 5b steps 1, 2, 4. `graphify affected` on `segment_by_gaps`, `repace_bad_lines`, `align_song`, `_with_guessed_words` first (callers: `align_song`, `_run_cue_align`, `test_cue_align.py`, `test_lyric_align.py`). Commit `faa9146` `fix(cue_align): only a line missing words gets a wider window`: `segment_by_gaps` loses `env` (caption rule, duet end of `173439c` kept); `Section.measured_end`, `Section.widened_end`, the `edges` stat and its log line removed; `repace_bad_lines` takes `env` in place of `sections`, window per line: `aim_end` = max(cue end + offset, `_singing_end`), `w0` = cue start + offset - pad, `w1` = min(duration, max(cue end + offset + pad, aim_end)), the check aims at (cue start, max(cue end, aim_end - offset)); new `_singing_end` (`_volume_tail` for the song's last line, else `_volume_end` against the next cue; `_volume_end`/`_volume_tail` params renamed `cue`/`next_cue`); new `_trim_lead_in` (first word start < cue start + offset - `PAUSE_SLACK_S` and end >= bound + `INSTANT_WORD_DUR_S` -> start = bound, run before the check); guessed-word bounds are the line's `(w0, w1)` (was section `t0`/`t1`), the `duration` min dropped (`w1` is already capped). `lyric_align.py`: docstring and comment only. Tests: `TestSegmentByVolume` (14) removed, duet-end test moved to `TestSegmentByGaps`; new `TestRescueWindow` (hold into silence, sang into the next caption, pause inside the held line, hold cap x2, stopped before the caption, silent envelope, envelope ends before the next cue, next cue starts before the search, long final hold, final hold to the end of the audio, held tail kept, same tail rejected without env, no env = today's window); lead-in trim x3 in `TestPartialLines` (kept at the bound; under `INSTANT_WORD_DUR_S` past it rejected; last word past the end bound rejected); `TestAlignSong`: section window stays 7.75 with an envelope, no `edges`; `test_lyric_align.py`: two `edges` asserts removed. Mutation checks (file restored after each): `_singing_end` always None -> 7 tests fail (6 `TestRescueWindow`, 1 `TestAlignSong`); `_trim_lead_in` call removed -> 1 fails (kept at the bound). `pre-commit` on the 4 files: black reformatted the test file, second run clean. `python -m pytest -q`: 3045 passed (row 2: 2998) | 4 files, +266 -276 |
| 41 | 2026-10-31 | 5b | Phase 5b step 3, scratch `cpu_check.py` (CPU, no library writes, d6c3ce9f scratchpad): per song, line objects from the pre-branch `before` backup ASS words (all lines), cue spans / lines / `media_duration_s` / envelope as row 38, `repace_bad_lines(..., env=env, realign=<saved b1_<id>_<lid>.json words for a target line, None otherwise>)`. `fit_offset` patched to the bundle's `repace.offset_s` (row 38's): the fit over the snapped ASS words differs, unpatched first run: Stronger +0.036 vs -0.497, All of Me +0.015 vs -0.254, Someone Like You -0.454 vs -0.525, Baby One More Time +0.145 vs -0.104, Miss Independent +0.250 vs +0.112, Pocahontas +0.230 vs -0.152, Incomplete -0.659 vs -0.686, Castle +0.010 vs -0.170, My Heart Will Go On -0.114 vs -0.377; the 18 `w0` then differed from row 38's by 0.03-0.54 s and 14 were kept (Stronger 37 not) | Patched: the (w0, w1) `realign` received equals row 38's on 18 of 18 (to the 0.01 s row 38 rounds to); kept (`SOURCE_REALIGN`) 15, the same 15 as row 38; not kept: Stronger 26 (15/15 words, guessed tail, last `go` 146.63-146.73 = window end), Miss Independent 9 (`Good` 24.61-24.71, `morning.` 24.71-25.06, `God` 25.06-25.28, `damn.` 25.28-25.51), Miss Independent 71 (`Ooh` 216.36-217.86, `yeah,` 217.94-218.4, `ooh` 218.4-218.74, `yeah` 218.74-219.08). Non-target lines asked for a re-align: Miss Independent 11 (unpatched run only) |
| 42 | 2026-10-31 | 5b | Phase 5b step 5. Commit `861dad2` `fix(cue_align): guessed words fill the tokens the aligner dropped, in order`: new `_assign_in_order` (each word takes the next token with its normalised text; a word with no token left is skipped); `_with_guessed_words` uses it, loses its `cue_span` param. Test `test_a_repeated_phrase_missing_its_tail_is_guessed_after_the_timed_words` (tokens `no more, no more`, timed `no` 8.7-8.8 and `more,` 8.9-9.0 in cue 8-9): before the change `['no', 'more,', 'no', 'more,']` (timed pair on tokens 2-3, guesses on 0-1); after: `no`, `more,` timed, `no` 9.0-9.1, `more` 9.1-9.2. First draft (timed pair at 8.0-8.5) passed under the old match too, so the test uses the late pair. `cpu_check.py` on `faa9146` (old match, scratch worktree, removed after) vs `861dad2`: output identical on all 33 lines (windows, kept set, the three guessed lines' words). `pre-commit` on the 2 files clean; `python -m pytest -q`: 3046 passed in 36.73 s | 2 files |
| 43 | 2026-10-31 | 5b | Opus, after Ken's question (wider windows for crammed lines too, e.g. She Used To Be Mine). CPU, library read only. (1) She Used To Be Mine (`53GIADHxVzM`, bundle 2026-10-30T14:57:39, `.lrclib.srt`, repace offset -0.39, realigned [41]) lines 5-8: ASS, cue span, transcriber words. (2) scratch `deficit.py` (39d269ea scratchpad): per cue-align line with words, ASS karaoke cursor end (event start + all `\k`/`\kf`) minus the bundle's `output_line_timings` end; `generate_ass` floors each word at `\kf10`, so the overrun is the time the floor added. (3) scratch `crammed.py`: lines with `\kf10` words | (1) ASS L6 `{\k80}{\kf64}I'm {\kf34}not {\k15}{\kf43}anything {\kf130}like {\kf10}I {\kf10}used {\kf10}to {\kf10}be`, bundle end 36.09, cursor end 36.48; L7 `{\k80}{\kf10}Although {\k26}{\kf282}it's {\k10}{\kf34}true`, start 36.09; edge_snap: L6, L7 not in onset snaps, L7 word 1 end-extended 1.32 to bound. Cues (SRT): L6 33.32-38.48, L7 38.48-40.82. Transcriber: `anything` 34.22-34.80, `Like` 36.35-36.52, `I` 36.52-36.84, `used` 36.84-37.34, `to` 37.34-37.62, `be` 37.62-38.02, `Although` 38.30-38.74, `it's` 38.74-39.30, `true` 39.30-39.60. Overrun L5 -0.02, L6 0.39, L7 0.10, L8 0.00. (2) 90 cue songs, 5911 lines (433 in the 9 test songs): overrun >= 0.05 s 1092 lines in 89 songs (test 65); >= 0.1 413 in 80 (test 21); >= 0.2 100 in 42 (test 2); >= 0.3 34 in 23 (test 1). (3) lines with any `\kf10` 1866; a run of >= 2 `\kf10` 286, >= 3 67; `\kf10` share >= 0.5 154, > 0.5 50 | ASS floor hides raw durations under 0.10 s; pre-snap words are not saved |
| 44 | 2026-10-31 | 5b | Opus. `/code-review faa9146^..861dad2` (files `cue_align.py`, `lyric_align.py`, `test_cue_align.py`, `test_lyric_align.py`; finders: correctness, simplicity, robustness), 10 findings: (1) `_singing_end` searched raw cue spans while `t1`, `aim_end` are cue + offset; (2) guess bounds were the line's `(w0, w1)` only, so a kept (clean, off-cue) partial line with words past `w1` got `hi` < its last word's end and zero-length guessed words; (3) `_assign_in_order` gives a word the earliest free repeat of its token (tokens `baby baby baby oh`, timed 3rd `baby` + `oh` -> timed word on token 0, tokens 1-2 guessed after it); (4) two token-assignment rules: `_match_words_to_tokens` (DP, cue-paced expected times, not offset-corrected) in `split_section_to_lines`/`_line_from_realigned`, then `_assign_in_order` again in `_with_guessed_words`; (5) last line's window: `_volume_tail`, no `MAX_HOLD_S` cap, so outro ad-libs extend `w1` and the aimed span; (6) last line = `lid == len(cue_spans) - 1`, not the latest-ending line (the section code's duet rule, `173439c`); (7) `_trim_lead_in` does not check overlap with the previous line's words; before `faa9146` such a re-align was rejected; (8) `edges` stat removed with no per-line replacement; (9) decode label `cue-align edges`; (10) `guessed[lid]` counts from the input words, `_assign_in_order` can skip a word. Commit `8cc7588` `fix(cue_align): rescue windows search the audio clock, guesses stay outside kept words` for 1, 2, 8, 9 and the docstring of 3: `audio_spans` = cue spans + offset passed to `_singing_end`; guess bounds `after = max(after, min(w0, start))`, `before = min(before, max(w1, end))`; stats `n_windows`, `windows_widened_line_ids` (`singing_end` > cue end + offset), `windows_unmeasured_line_ids` (`singing_end` None, incl. no env) and the rescue log line; label `cue-align rescue windows`. Not changed: 3-7, 10 (10: words come from the line's own tokens in order, no skip seen). Tests: `test_where_singing_stops_is_searched_on_the_audio_clock` (anchors offset -0.6, line 4 cue 8-9, next cue 10-12, env sung 7.7-9.2 and 9.4-11.4), `test_a_guessed_tail_after_a_kept_line_past_its_window_is_not_shown_for_no_time` (cue 8-9, words `ee` 9.9-10.2, `ff` 10.3-10.6), window-id asserts on two `TestRescueWindow` tests. GPU rerun of the test songs not run (Ken's word) | Against `cue_align.py` at `861dad2` (stashed, restored): 4 of the new or changed tests fail (offset window (6.65, 10.0) vs 9.4; tail `gg` zero length; 2 missing stats keys). On `8cc7588`: window (6.65, 9.4); `ff` 10.3-10.45, `gg` 10.45-10.6. `pre-commit` on the 3 files: black reformatted `test_cue_align.py`, second run clean. `python -m pytest -q`: 3048 passed in 37.28 s. Rows 38 and 41's windows used the raw-cue search; their repace offsets (-0.686 to +0.112) are all under the 0.75 pad, so none of the 9 songs was re-sectioned |
| 45 | 2026-10-31 | 5b | Opus, GPU replay on Ken's go (app stopped, GPU idle), HEAD `8cc7588`, no library writes. Scratch `replay_cram.py` (39d269ea scratchpad): the 9 test songs + She Used To Be Mine (`53GIADHxVzM`); per song `cue_align.align_song` as `_run_cue_align` calls it (cue spans from the lyric sheet, the bundle's stem choice, envelope as rows 36-38, slices as row 38), `repace_bad_lines` wrapped to save its input (section line objects, before any rescue: `cram_<yid>.json` key `sections`). A = committed code. B = `repace_bad_lines` from cue_align's own source with two expressions changed: complete = `_timed(obj) >= len(toks)`, better = `_timed(fixed) > _timed(obj)` (`_timed` = words of at least `INSTANT_WORD_DUR_S`), over A's input, re-align calls shared by (text, w0, w1). Both through `snap_line_edges`. First run stopped at the JSON save after Stronger (numpy bool); rerun with `default=o.item()`. Report `cram_report.md`; tallies `cram_tally.py`, `cram_guard.py`, `alt_window.py` (CPU) | Per song (offset; A realigned; B realigned; unique slice calls, A's in brackets; s): Stronger -0.60, [6, 32, 37], [6, 10, 18, 19, 26, 32, 35, 37], 23 (15), 139; All of Me -0.30, [22, 29, 40, 46, 49], [22, 29, 40, 46, 47, 49, 55], 21 (18), 159; Someone Like You -0.51, [16, 33, 45, 49], [1, 16, 32, 33, 34, 42, 45, 46, 49, 50], 25 (18), 161; Baby One More Time -0.12, [20, 28, 30], [1, 2, 3, 20, 27, 28, 30, 40], 23 (11), 146; Miss Independent +0.13, [5, 9, 12, 38, 72, 78], [1, 2, 3, 5, 9, 11, 12, 24, 38, 58, 72, 74, 78, 79, 81], 38 (17), 207; Pocahontas -0.15, [6, 7, 8, 36], [6, 7, 8, 9, 19, 20, 23, 27, 33, 36], 14 (8), 113; Incomplete -0.69, [], [2, 6], 22 (19), 139; Castle -0.17, [36, 46], [2, 10, 14, 16, 23, 30, 32, 36, 46, 53], 24 (12), 152; My Heart Will Go On -0.36, [3, 8, 19, 25, 26], same, 10 (10), 97; She Used To Be Mine -0.39, [41], [6, 7, 29, 41], 9 (6), 93; none re-sectioned; 24 stable-ts `Failed to align` warnings. Targets, A: every token timed by the model on 14 of 18 (re-aligned: Stronger 6, 32, 37; All of Me 29, 46, 49; Someone Like You 16, 33, 49; Baby One More Time 20, 30; Pocahontas 36 (end 190.20); Castle 46; section align 6/6: My Heart Will Go On 9); guessed words: Stronger 26 (13/15), Incomplete 3 (4/6), Miss Independent 9 (re-aligned + guessed), 71 (2/4). Incomplete 3: window (38.575, 44.492), 4 words returned, not kept; row 38's (38.58, 47.10) kept 6/6. Audio-clock cue 39.33-43.74, next cue 50.17; quiet runs from 43.23: (43.23, 44.15), (44.68, 44.80), (45.60, 45.75), (46.38, 50.18); transcriber `is` 41.98-44.18, `anybody's` 44.18-45.74, `guess` 45.74-46.04. B vs A: section lines with a zero-length word 92 of 478; B asked 75 re-aligns A did not; kept by B only 46; lines differing after the snaps 59; against the transcriber [B closer, within 0.05 s, B further]: start 25 / 15 / 10 (9 without a heard first word), end 18 / 26 / 3 (12 without); zero-length words: section 135, A 94, B 40; lines starting before the previous line's end: A 13, B 32 (19 new in B, 0.01-1.29 s). She Used To Be Mine, A -> B: L6 `I` `used` `to` `be` all 36.09-36.09 -> 36.50-36.82, 36.94-37.28, 37.28-37.62, 37.75-38.14 (heard 36.52-38.02); L7 start 36.09 -> 37.59 (`Although` 37.59-38.52, heard 38.30; previous line's end 38.14); L29 `Who` 144.65-144.67 -> 144.47-144.61. `cram_guard.py` (B + guard on finding 7: a line only B re-aligned may not start before the previous line's last word ends, pre-snap; first word trimmed to that end if >= `INSTANT_WORD_DUR_S` is left, else A's line): trimmed 10, dropped 6; lines differing from A 52; start 25 / 13 / 6, end 17 / 22 / 3; zero-length words 49; lines starting before the previous line's end 16. `alt_window.py` (window end at the quiet stretch running into the next cue's start instead of the first quiet stretch of `RELEASE_QUIET_S`; same pad, midpoint, `MAX_HOLD_S`): 113 asked lines (not the song's last), aim end differs on 4: Stronger L1 23.95 -> 25.45, Stronger L26 146.57 -> 149.38, Castle L30 158.33 -> 159.23, Incomplete L3 43.74 -> 47.12 | 10 songs |
| 46 | 2026-10-31 | 5b | Opus, GPU on Ken's go (app stopped, GPU idle), HEAD `8cc7588`. Scratch `replay_alt.py` (39d269ea scratchpad): row 45's variant B with `_volume_end` replaced by `alt_window.alt_end` (quiet stretch of at least `RELEASE_QUIET_S` ending within 2 frames of the next cue's start; none -> the next cue's start; same pad, midpoint, `MAX_HOLD_S`), over row 45's saved section output for Stronger, Castle, Incomplete; every re-align run, raw words saved (`alt_<yid>.json` key `realigns`: lid, w0, w1, words); then `snap_line_edges` | Stronger: realigned [6, 10, 18, 19, 26, 32, 35, 37] (B same), guessed [] (B [26]), 13 calls, 66 s; Castle: realigned as B, guessed [] (B []), 15 calls, 77 s; Incomplete: realigned [2, 3, 6] (B [2, 6]), guessed [] (B [3]), 4 calls, 23 s. Lines differing from B after the snaps: Stronger [26], Castle [30], Incomplete [3]. Incomplete L3: window 38.58-47.12, 6 of 6 returned; raw `is` 42.02-44.18, `anybody's` 44.18-45.76, `guess` 45.76-46.02; pre-snap `anybody's` 44.18-45.68, `guess` 45.76-46.02; after the snaps `guess` 45.76-47.20 (end snap +1.185, `to_bound` False); transcriber `anybody's` 44.18-45.74, `guess` 45.74-46.04. Stronger L26: window 140.13-149.38, 15 of 15 returned; last three B `here` 146.17-146.41 `I` 146.41-146.52 `go` 146.52-146.63 -> `here` 146.54-148.04 `I` 148.39-148.49 `go` 148.49-149.65 (end snap +0.942); zero-length `here` 143.01-143.01 in both; transcriber has no first/last match. Castle L30: window 151.20-159.23; only `Driving` changes, 152.15-153.00 -> 152.15-152.70; transcriber 152.40-157.70. Stronger L1: window 18.20-25.45, 2 of 3 returned, not kept (as B). Targets with B + this window end: every token timed by the model on 16 of 18 (row 45's 14 + Incomplete 3, Stronger 26); guessed: Miss Independent 9, 71 | 3 songs |
| 47 | 2026-10-31 | 5c | Sonnet, Phase 5c step 1. `graphify affected` on `repace_bad_lines`, `_volume_end`, `_trim_lead_in` first (`_volume_end`: callers `_singing_end`, `repace_bad_lines`; `_trim_lead_in`: `repace_bad_lines`, `align_song`, `test_cue_align.py`). Commit `5fe4ff6` `fix(cue_align): a rescue window ends where the singing stops before the next line`: `_volume_end` takes the last quiet run of `_quiet_runs(env, cue end - EDGE_SEARCH_SLACK_S, next cue start, ...)` as the release when it is at least `RELEASE_QUIET_S` long and ends within `2 * HOP_S` of the next cue's start; otherwise `stop = t1 = next cue start`; pad, midpoint, `MAX_HOLD_S` unchanged; docstring and the `RELEASE_QUIET_S` comment reworded (Incomplete: 0.9 s breath). Tests in `TestRescueWindow`: `test_a_long_breath_inside_the_line_is_not_its_end` (cue 8-9, next 14-15, sung 8.3-9.0, 10.0-11.0, 14.2-15.0: window ends 11.75), `test_a_long_breath_inside_a_line_that_sings_into_the_next_caption` (next cue 12-13, sung 8.3-9.0, 10.0-13.0: window ends 12.0). The existing `TestRescueWindow` tests passed unchanged (their pauses are under `RELEASE_QUIET_S`). Mutation check (`_volume_end` restored from `8cc7588`, file restored after): both new tests fail (obtained 9.75, expected 11.75 and 12.0). `pre-commit` on the 2 files clean; `python -m pytest -q`: 3050 passed (row 44: 3048) | 2 files, +31 -12 |
| 48 | 2026-10-31 | 5c | Sonnet, Phase 5c step 2. Commit `c032c9f` `fix(cue_align): words the aligner left zero-length are rescued like missing ones`: new `_timed_words(words)` (words of at least `INSTANT_WORD_DUR_S`; `_instant_fraction` now `(len - timed) / len`); `repace_bad_lines`: a placed line is complete when `_timed_words(obj) >= len(toks)` (was `len(obj words) >= len(toks)`), a re-align replaces a placed line when `_timed_words(fixed) > _timed_words(obj)` (was the word count); `crammed` = placed lines with `len(words) >= len(toks)` that reach the rescue (key `crammed_line_ids`, rescue log line `%d crammed line(s) asked for a re-align`); new `_start_after_previous(obj, previous_end)` after `_trim_lead_in` (previous end = `end` of the last line before it in `out` that has words; first word starting before it: start moved to it when `first end >= previous_end + INSTANT_WORD_DUR_S`, else None -> the re-align is not kept); new `_with_first_start` shared by it and `_trim_lead_in`; docstrings (module, `repace_bad_lines`) reworded. Guess-fill untouched (a zero-length word is never replaced by a guess). Tests: `TestCrammedLines` (4: zero-length words ask a re-align and keep one timing more; keeps its own words when the re-align times no more, `n_guessed_words` 0, `n_repaced` 0; every word timed asks nothing, `n_windows` 0; `crammed_line_ids` [4] only, a word-short line 5 in `guessed_word_line_ids`), `TestStartAfterPrevious` (3: first word 8.0-8.5 over previous end 8.2 -> 8.2-8.5; 8.0-8.22 -> not kept, own `ff` 8.5-8.7 unchanged, `source` `cue_align`; first word at 8.3 untouched). First draft of `TestStartAfterPrevious` made line 3 text `a a` like the anchors: an identical-text run, so line 3 was re-paced and the guard never fired; line 3 text is `bb cc`. Mutation checks (file restored after each, diff against the saved copy empty): `_timed_words` replaced by `len` at both places -> 3 fail (`test_a_line_with_zero_length_words_asks_a_realign_and_keeps_one_that_times_more`, `test_it_keeps_its_own_words_when_the_realign_times_no_more`, `test_only_the_line_with_a_word_for_every_token_is_crammed`); guard call removed -> 2 fail (starts where it ends; too little left); rejection threshold set to `previous_end - 9` -> 1 fails (too little left). `pre-commit` on the 2 files clean; `python -m pytest -q`: 3057 passed in 37.13 s | 2 files, +178 -32 |
| 49 | 2026-10-31 | 5c | Phase 5c step 3, CPU only, no library writes. Scratch `cpu_check_5c.py` and `cpu_check_5c_guard.py` (d6c3ce9f scratchpad): per song `repace_bad_lines(cram_<yid>.json `sections`, `spans`, bundle `lyrics.lines`, `lyrics.align_lines`, duration, env = `probe_edges.load_env` of the song's `<sub>/<stem>---<sub>.m4a`)`, `realign` answering from `alt_<yid>.json` `realigns` matched on (lid, w0, w1) within 0.001 s, a miss recorded and returning None. (1) After step 1 (`5fe4ff6`): Stronger offset -0.596, `realign` called for lines [6, 21, 26, 32, 37]; Castle -0.170, [36, 37, 46]; Incomplete -0.690, [3]; 9 calls, 9 windows among the line's saved windows, 0 without saved words. Realigned: Stronger [6, 26, 32, 37], Castle [36, 46], Incomplete [3]; guessed []. (2) After step 2 (`c032c9f`), `_start_after_previous` patched to return its input: calls Stronger 13 of 13 saved (lines [1, 6, 9, 10, 18, 19, 20, 21, 24, 26, 32, 35, 37]), Castle 15 of 15 ([0, 2, 4, 10, 14, 16, 23, 24, 27, 30, 32, 36, 37, 46, 53]), Incomplete 4 of 4 ([2, 3, 6, 10]); 0 windows without saved words; lines differing from `alt_<yid>.json` `out` (39, 56, 27 lines; source, word text, start and end within 0.001 s): 0, 0, 0. `crammed_line_ids`: Stronger [1, 9, 10, 18, 19, 20, 24, 35], Castle [0, 2, 4, 10, 14, 16, 23, 24, 27, 30, 32, 53], Incomplete [2, 6, 10]. (3) Guard on: windows the same; lines differing from `alt out`: Stronger [6, 18, 37], Castle [14, 16, 32, 46], Incomplete []; each differing line's alt first word started before the previous line's end in the guard-on output, no other line differs, and no line alt re-aligned with such a start is unchanged. Per line (previous line's end; alt re-align first word; result): Stronger 6 (42.92; `You` 42.47-43.82; start -> 42.92), 18 (105.04; `My` 104.20-105.45; start -> 105.04), 37 (201.69; `My` 200.87-200.87; not kept, `cue_align`, 9 words, guessed), Castle 14 (84.43; `And` 83.77-84.42; not kept), 16 (91.47; `When` 90.97-91.20; not kept), 32 (162.42; `And` 161.81-162.66; start -> 162.42), 46 (226.67; `And` 225.89-226.60; not kept, guessed). Realigned with the guard on: Stronger [6, 10, 18, 19, 26, 32, 35], guessed [37]; Castle [2, 10, 23, 30, 32, 36, 53], guessed [46]; Incomplete [2, 3, 6], guessed []. Stronger 37 and Castle 46 are two of the 18 targets; the committed code (`8cc7588`) kept both. Not measured: the guard on the other 7 songs | 3 songs |
| 50 | 2026-10-31 | 5c | Sonnet, Phase 5c step 4 (the hand-off prompt: "Ken sgrees to step 4", read as agrees). `graphify affected` on `align_song`, `_run_cue_align`, `build_bundle` first (`align_song`: `_run_cue_align`, `test_cue_align.py` x6, `test_lyric_align.py` x2 via `MagicMock(wraps=...)`; `_run_cue_align`: `run`; `build_bundle`: `_write_debug_capture`). Commit `b8a7a36` `feat(alignment_capture): cue bundles keep the section words and re-aligns`: `align_song` returns `(line_objects, stats, cue_inputs)`, `cue_inputs` = `{sections: deepcopy of the line objects after the section pass(es), before `repace_bad_lines`; realigns: [{line_id, w0, w1, words: deepcopy of slice_align's result or None}] in call order}`; `_run_cue_align` returns a fifth value; `run` holds it as `capture_cue_inputs` (None on the joint and transcribe routes), `_write_debug_capture(cue_inputs=...)`, `build_bundle(cue_inputs=None)` writes top-level `cue_inputs`; schema comment block "Additive since v11" in `alignment_capture.py`, `SCHEMA_VERSION` stays 11. The snaps build new line objects (`onset_snap.py` 325, 494) and `repace_bad_lines` builds new ones, so nothing edits the section objects in place today: the copies are a snapshot guarantee for the record, not a present need. Tests: `TestAlignSong` 3 (`test_the_rescues_inputs_come_back_with_the_song`, `test_a_failed_realign_is_recorded_as_none`, `test_the_returned_inputs_are_copies`), the 7 existing `align_song` unpackings take a third value; `test_lyric_align.py`: `test_the_bundle_keeps_the_section_words_and_the_realigns` (section words `glowing river` / `phantom`, one realign for line 1 with `phantom` 13.0 and `parade` 14.0 at absolute time), `test_the_joint_route_has_no_cue_inputs`; `test_alignment_capture.py`: `test_build_bundle_keeps_cue_inputs_and_writes_numpy_words` (np.float64 / np.float32 in realign words land as JSON, a null `words` kept, default None). Mutation checks (files restored after each, diff against the saved copies empty): sections not copied -> 1 fails (`test_the_returned_inputs_are_copies`); realign words not copied -> the same 1; realigns not recorded -> 4 fail (3 `TestAlignSong`, the stage test); stage passes `cue_inputs=None` -> 1 fails (the stage test). First `pre-commit` run: black reformatted `test_cue_align.py`, second clean; one test comment corrected and amended into the commit (it said the edge snap edits lines in place, which it does not). `python -m pytest -q`: 3063 passed in 37.05 s | 6 files, +169 -19 |
| 51 | 2026-11-02 | 5c | Opus. `/code-review 5fe4ff6^..b8a7a36` (files `cue_align.py`, `lyric_align.py`, `alignment_capture.py` and their three test files; finders: correctness, simplicity, robustness), 10 findings: (1) `_volume_end` takes only the last quiet run and needs it to end within 2 frames of the next cue's start. Probe, line cue 8-9 sung 8.3-10.6, next cue 12-13: next singer on cue 11.29; 0.3 s early 12.0; on cue plus a 50 ms blip at 11.5 12.0 (the first-long-run rule: 11.29 in all three); (2) the guard takes the end of whatever line precedes in `out`, a `SOURCE_FILL` line or a duet caption overlapping on purpose included; (3) a bad line whose re-align the guard rejects is re-paced from `t0` with no previous-line check; (4) zero-length words trigger a rescue, but the guess pass skips a line with `len(words) >= tokens`, so a failed rescue keeps them; (5) at 0.05 s any placed line with one quick word costs a re-align, and one more timed word replaces it; (6) the guard looks only backward: a rescued line's last word is never checked against the next line's first; (7) `cue_inputs` omits the spans the rescue used (offset-shifted on a re-sectioned song; `offset_s` kept to 3 decimals); (8) the guard's previous-end scan repeats the guess pass's `after` scan, and `_trim_lead_in` / `_start_after_previous` differ on too little left (obj vs None); (9) `crammed` repeats the gate above it to report it; (10) `align_song` deep-copies sections and realign words with debug capture off. Touched test files: 147 passed | Ken, 2026-11-02: fix 1, 7 and 2 (fill and overlap) now (rows 52-54); 4 and 5 written up as Decisions 14-15, proposed; 3, 6, 8-10 to `plans/open-issues.md` at landing. The scratch data of rows 45-49 (39d269ea, d6c3ce9f scratchpads) is no longer on disk, so row 49's replay was not rerun. `graphify affected` on `repace_bad_lines`, `align_song`, `_volume_end`, `_quiet_runs` was run after rows 52-54's code, not before: no callers beyond `_singing_end`, `align_song`, `_run_cue_align` and `test_cue_align.py`; `graphify update .` after |
| 52 | 2026-11-02 | 5c | Opus. Commit `214d209` `fix(cue_align): a next singer coming in early does not take a line's release`: `_volume_end` accepts the last quiet run when it is at least `RELEASE_QUIET_S` and ends within `EDGE_SEARCH_SLACK_S` (0.5) of the next cue's start (was `2 * HOP_S`); `_quiet_runs` merges runs separated by under new `QUIET_BLIP_S` 0.1. Tests in `TestRescueWindow`: `test_a_next_singer_coming_in_early_does_not_take_the_release` (sung 8.3-10.6, 11.7-13.0, next cue 12-13: window ends 11.15), `test_a_blip_inside_the_release_does_not_split_it` (sung 8.3-10.6, 11.5-11.55, 12.0-13.0: 11.3). Mutation checks (file restored after each, `cmp` clean): tolerance back to `2 * HOP_S` -> the early-singer test fails (1); merge off -> the blip test fails (1). CPU check, scratch `window_end_check.py` (4ac1adb0 scratchpad): per line of the 10 songs, `_volume_end` at `6e863c0` vs `214d209`, envelope `decode_env_db` of the bundle's stem (`dereverb/` when `joint_stats.dereverb.succeeded`, else `vocal/`), cues from `lyrics.source_path` (`\` -> `/`) plus `joint_stats.offset_s`, pad 0.75; w1 = max(cue end + 0.75, end) | 462 lines measured, 10 ends moved, 6 change w1 (old -> new): Stronger L0 12.38 -> 12.01; All of Me L54 265.73 -> 265.62; Baby One More Time L28 148.28 -> 148.08; Castle L1 38.99 -> 36.34 (next cue 38.99), L29 151.95 -> 151.30 (next cue 151.95), L38 192.83 -> 192.73. w1 unchanged: Someone Like You L22, Baby One More Time L1, Castle L37, L42. Miss Independent, Pocahontas, Incomplete, My Heart Will Go On, She Used To Be Mine: 0 moved. `pre-commit` on the 2 files clean; `python -m pytest -q`: 3065 passed in 37.47 s (row 50: 3063) |
| 53 | 2026-11-02 | 5c | Opus. Commit `cb4fc50` `feat(alignment_capture): cue bundles keep the spans the rescue was given`: `align_song`'s `cue_inputs` gains `spans` (`list(spans)`: the cue spans `repace_bad_lines` is given, offset-shifted when re-sectioned); docstring and the "Additive since v11" comment in `alignment_capture.py`; `SCHEMA_VERSION` stays 11. Tests: `test_the_rescues_inputs_come_back_with_the_song` asserts `spans == _SONG_CUES`; `test_large_display_lead_triggers_resection` asserts the cues shifted by 1.5 (abs 0.05). Mutation checks (restored, `cmp` clean): `list(cue_spans)` recorded -> the resection test fails (1); `spans` dropped -> both fail (2) | `pre-commit` on the 3 files clean (one docstring rewrapped by hand); `python -m pytest -q`: 3065 passed in 37.02 s |
| 54 | 2026-11-02 | 5c | Opus. Overlap probe (CPU, read only): consecutive cue pairs whose first cue ends after the second starts, cues from each cue bundle's `lyrics.source_path`. Commit `c47882d` `fix(cue_align): a re-align is not bounded by a fill or a caption sung over it`: new `_previous_end(out, cue_spans, lid)` (the last line in `out` with words; None when its `source` is `SOURCE_FILL`, or its cue end minus `lid`'s cue start exceeds new `DUET_OVERLAP_S` 1.0) replaces the inline scan before `_start_after_previous`; `repace_bad_lines` docstring. Tests in `TestStartAfterPrevious` (`_song` takes `cue3`): `test_a_caption_sung_over_this_one_does_not_bound_it` (line 3 cue 6.0-9.5: line 4 kept from 8.0), `test_a_caption_shown_a_little_into_this_one_still_bounds_it` (cue 6.0-8.3: not kept, `source` `cue_align`), `test_a_filled_previous_line_does_not_bound_it` (line 3 no words, cue 6.0-8.4: fill `bb` 6.0-7.2, `cc` 7.2-8.4; line 4 kept from 8.0). Mutation checks (restored, `cmp` clean): fill check removed -> the fill test fails (1); overlap check removed -> the duet test fails (1); overlap threshold 0 -> the small-overlap test fails (1) | Overlaps: 10 test songs 0 pairs. Library: 155 pairs in 5 songs, min 0.106 s, median 0.107, p90 0.322, max 4.7. Be Our Guest 67 and Belle 77 (`custom`, movie subtitles; over 0.2 s: 0.21-0.32); Part of Your World 1 (3.07); A Whole New World (Mena Massoud, Naomi Scott) 4 (1.9-4.07); A Whole New World (ZAYN, Zhavia Ward) 6 (2.83-4.7). Not measured: re-aligns in the 10 songs that follow a fill (row 49's saved re-aligns gone); the rerun measures it. `pre-commit`: black reformatted `cue_align.py` on the first run, then clean (one docstring rewrapped by hand); `python -m pytest -q`: 3068 passed |
| 55 | 2026-11-02 | 5c | Sonnet, Phase 5c step 5, HEAD `b296672` (code `c47882d`). Ken, after the hand-off said to ask him to stop the app: "App is stopped." (read as go). Dry run first (10 songs: 8 `reuse srt (from video)`, Pocahontas and She Used To Be Mine `LRCLIB timing`; GPU 6 MiB used, no `pikaraoke` process). Scratch copy of the 10 songs' `alignment_debug`, `karaoke`, `lyrics`, `subtitles` files (39 files), then the Phase 5 command plus `--song 53GIADHxVzM`, with `--yes`, no `--dry-run`, 2026-11-02 20:20:41Z to about 20:47Z. Backup the script made: `~/pikaraoke-songs/regen_backups/20261102T202041Z/{alignment_debug,karaoke,lyrics,subtitles}` (39 files; `cmp` against the scratch copy: 0 differ). Compare baselines: PRE = `regen_backups/20261031T174600Z` (9 songs) plus She Used To Be Mine from this run's backup (its pre-branch bundle and ASS, 2026-10-30); MID = this run's backup (the library as rows 29-31 left it; She Used To Be Mine = PRE); NOW = the library after the run. The compare scratch of rows 29-30 (323ba938 scratchpad) is gone; `compare.py`, `asswords.py`, `vs_heard.py`, `probe_edges.py` were recovered from that session's transcript and pointed at `pre/` and `mid/` copies (She Used To Be Mine added); new: `three.py` (summary, targets, changed, overlaps, early5, she, castle), `full.py`, `replay_now.py`, `regress.py`, `ken_list.py` (d6c3ce9f scratchpad, `rerun/`). "Heard" (the transcriber's first and last word) comes from the NOW bundle for all three states (row 30 used each state's own, so its counts differ by a line or two). Word times are the ASS's: `generate_ass` floors every word at `\kf10`, so a word the aligner left at zero length shows as 0.10 s (a genuine 0.10 s word shows the same) | Exit 0, `Done. succeeded=10 failed=0 skipped=0`. Two warnings, both as row 27: Someone Like You line 44 `slice-align failed, degrading` (`'NoneType' object has no attribute 'language'`), My Heart Will Go On `transcribe yield 22.5 wpm < 30.0` retried on the cached de-reverb stem. Pocahontas `.lrclib.srt` sha256 before and after `d56db69749f7a5d518d7182cf6acd7d55fa08e2bfbc938a0e5c63f5ce9c641dd`, identical to row 28. Stage log `cue rescue` lines in block R55 (summary) |
| 56 | 2026-11-02 | 5c | Rescue stats and `cue_inputs` of the 10 NOW bundles; `replay_now.py stats`: `repace_bad_lines` over each bundle's `cue_inputs` (`sections`, `spans`, `realigns` answered on (line, window within 0.001 s)), envelope from the song's stem (`dereverb/` when `joint_stats.dereverb.succeeded`, else `vocal/`), `lyrics.lines`, `lyrics.align_lines`, `media_duration_s` | `cue_inputs` present in 10 of 10 bundles, `spans` as long as the line count in each, `sections` one per line, `realigns` 13 / 8 / 12 / 15 / 30 / 10 / 4 / 15 / 5 / 4 (Stronger, All of Me, Someone Like You, Baby One More Time, Miss Independent, Pocahontas, Incomplete, Castle, My Heart Will Go On, She Used To Be Mine; 116 windows). `crammed_line_ids` 8 / 3 / 7 / 12 / 21 / 6 / 3 / 12 / 0 / 3 (75 lines); realigned lines 7 / 7 / 10 / 6 / 11 / 10 / 3 / 7 / 5 / 4; guessed-word lines Stronger [37], Miss Independent [9, 71], Castle [46]. Replay, guard on: every recorded window answered (0 misses), `realigned_line_ids`, `repaced_line_ids`, `guessed_word_line_ids`, `crammed_line_ids`, `n_windows` equal to the bundle's on 10 of 10. Row 49's CPU lists equal the bundle's: Stronger realigned [6, 10, 18, 19, 26, 32, 35] guessed [37], crammed [1, 9, 10, 18, 19, 20, 24, 35]; Castle realigned [2, 10, 23, 30, 32, 36, 53] guessed [46], crammed [0, 2, 4, 10, 14, 16, 23, 24, 27, 30, 32, 53]; Incomplete realigned [2, 3, 6], crammed [2, 6, 10]. Castle L1 and L29 (row 52's moved windows) were not rescued: no window, `aligned`, words equal in PRE, MID and NOW |
| 57 | 2026-11-02 | 5c | The 18 targets and She Used To Be Mine 0:33-0:40 (`three.py targets`, `she`; `full.py`: for a target, the model's words = the last kept re-align's words in `cue_inputs.realigns` when the line is in `realigned_line_ids`, else the line's `cue_inputs.sections` words; timed = at least `INSTANT_WORD_DUR_S` 0.05 s) | Lines short of their tokens, PRE / MID / NOW over the 10 songs: 18 / 0 / 0; lines with no words 0 / 0 / 0. Targets with a model word for every token: 14 of 18 (guessed: Stronger 37, Miss Independent 9 and 71, Castle 46); with every model word at least 0.05 s: 12 of 18 (Stronger 26 `here` 143.008-143.008 and `I` 145.348-145.348, 13 of 15; All of Me 49 `give` 233.117-233.137, 10 of 11); the replay with the guard patched out (row 59) re-aligns Stronger 37 and Castle 46 too: 16 of 18 with a model word per token. Target source NOW: re-aligned 13 (Stronger 6, 26, 32; All of Me 29, 46, 49; Someone Like You 16, 33, 49; Baby One More Time 20, 30; Pocahontas 36; Incomplete 3), re-aligned + guessed words 1 (Miss Independent 9), aligned + guessed words 3 (Stronger 37, Miss Independent 71, Castle 46), aligned 1 (My Heart Will Go On 9). Pocahontas 36 `wind` 183.27-190.21, line end PRE 178.87, MID 183.95, NOW 190.20 (heard last word end 184.92). She Used To Be Mine L6 NOW `like` 34.78-36.28, `I` 36.50-36.82, `used` 36.94-37.28, `to` 37.28-37.62, `be` 37.75-38.14 (transcriber `Like` 36.35, `I` 36.52-36.84, `used` 36.84-37.34, `to` 37.34-37.62, `be` 37.62-38.02); L7 `Although` 38.14-38.52, `it's` 38.52-39.30, `true` 39.30-39.60 (transcriber 38.30-38.74, 38.74-39.30, 39.30-39.60); PRE and MID L6 `I used to be` 36.08-36.18, 36.18-36.28, 36.28-36.38, 36.38-36.48, L7 `Although` 36.09-36.19; zero-length (floored) words in L6 / L7 4 / 1 -> 0 / 0. Words and sources of all targets in blocks R55t and R55s |
| 58 | 2026-11-02 | 5c | Compares, NOW against PRE and against MID (`three.py summary`, `changed`, `overlaps`, `early5`; `vs_heard.py` and `compare.py` with `BEFORE_DIR=pre` and `mid`) | Over the 10 songs (478 lines), PRE / MID / NOW: lines with a floored word 127 / 124 / 99, floored words 155 / 155 / 116; overlapping line pairs (output line start before the previous line's end) 9 / 15 / 12 (new in NOW against both: Castle 3 0.05 s, Castle 24 0.01 s, Baby One More Time 4 under 0.005 s; all three follow a re-aligned line). Changed lines (start or end moved more than 0.3 s, a word moved more than 0.3 s, word text or count, floored-word count, or source differs): against PRE 92, against MID 134; first word against the transcriber's, closer / within 0.05 s / further / no heard word: PRE 28 / 32 / 11 / 21, MID 35 / 53 / 11 / 35; last word PRE 29 / 40 / 6 / 17, MID 20 / 70 / 21 / 23. Lines starting more than 0.5 s before the heard first word PRE / MID / NOW: 54 / 59 / 58 (without She Used To Be Mine 52 / 57 / 57); lines ending more than 0.3 s before the heard last word: PRE 13, MID 9, NOW 9 (`vs_heard.py`). Row 30's five early-start lines, start minus heard first, PRE / MID / NOW: Stronger 18 -0.26 / -0.56 / -0.58, Stronger 32 +0.40 / -1.00 / -0.59, All of Me 40 -0.06 / -0.83 / -0.06, Someone Like You 48 -0.12 / -2.05 / -0.12, Miss Independent 51 +0.87 / -0.90 / +0.87. Lines in NOW that differ from PRE with no rescued line as neighbour or themselves: 11, all My Heart Will Go On (PRE has no `dereverb` key, row 27; repace offset PRE -0.19, NOW -0.361). Song Info after (`_timed_tile`, `song_status`): Stronger 97% `1 guessed · 3 words`, All of Me 100%, Someone Like You 98% `1 guessed`, Baby One More Time 100%, Miss Independent 97% `3 guessed · 3 words`, Pocahontas 100%, Incomplete 100%, Castle 98% `1 guessed · 2 words`, My Heart Will Go On 100%, She Used To Be Mine 100%; `warn` false and "Missing from the screen" note absent on all 10 (PRE: warn true on the 9 songs, 18 lines short). Raw tables: blocks R55 (summary), R55o, R55e, R55x, R55h |
| 59 | 2026-11-02 | 5c | The guard on this run's own re-aligns (`replay_now.py guard`): the replay of row 56 with `_start_after_previous` patched out against the replay with it, per song, lines whose `repace_bad_lines` output differs (source, word text, start, end within 0.001 s), with the previous line's end and the transcriber's words around the line. The lines are compared before the edge snaps | 22 lines differ (no windows differ: calls equal, 0 misses). Trimmed, first word moved to the previous line's end, re-align kept (13): Stronger 6 (42.47 -> 42.92), 18 (104.20 -> 105.04); All of Me 40 (182.32 -> 182.56), 46 (213.76 -> 213.77), 47 (220.44 -> 220.57); Miss Independent 3 (11.69 -> 11.83), 58 (180.70 -> 181.06), 78 (236.89 -> 237.02), 81 (243.85 -> 244.20); Pocahontas 23 (114.63 -> 114.72); Castle 32 (161.81 -> 162.42); My Heart Will Go On 26 (237.93 -> 238.24); She Used To Be Mine 7 (37.59 -> 38.14). Not kept (9): Stronger 37, Baby One More Time 40, Miss Independent 1, 5 (fill), 74, 79, Castle 14, 16, 46. Without the guard: Stronger realigned [6, 10, 18, 19, 26, 32, 35, 37] guessed []; Baby One More Time [2, 3, 20, 27, 28, 30, 40]; Miss Independent [1, 2, 3, 5, 9, 11, 12, 24, 38, 58, 72, 74, 78, 79, 81] guessed [9, 71]; Castle [2, 10, 14, 16, 23, 30, 32, 36, 46, 53] guessed []; Someone Like You, Incomplete: no line differs. Per line, words and transcriber in block R55g |
| 60 | 2026-11-02 | 5c | Lines NOW ends further from the transcriber than PRE by more than 0.05 s (`regress.py`: PRE, MID, NOW words, the neighbouring lines, the transcriber's words and the cue span) | 17 lines, block R55r: first word further 11 (Stronger 18, 19, 32; Someone Like You 34, 49, 50; Baby One More Time 20; Miss Independent 3; My Heart Will Go On 7, 9, 26), last word further 6 (Someone Like You 32, 46; My Heart Will Go On 3, 8, 25; She Used To Be Mine 29), none both. Re-aligned lines whose first word starts at or just after the previous line's end and before the cue: Stronger 19 `I,` 111.38 (cue 112.48, heard 112.48), Someone Like You 34 `Don't` 169.98 (cue 170.87, heard 170.62), 50 `Don't` 245.13 (heard 245.96), Baby One More Time 20 `Tell` 104.43 (heard 105.18); last word held: Someone Like You 32 `you` 161.22-163.09 (heard 161.10-161.84, next line starts 163.19); Pocahontas 36 `wind` ends 190.20, 5.28 s after the heard end (PRE 6.05 s before it, so not among the 17). Of the 17, Stronger 18, Miss Independent 3 and My Heart Will Go On 26 are lines the guard trimmed (row 59); the other 14 are not changed by it |
| 61 | 2026-11-02 | 5c | stop | GATE B reached; the list `song - m:ss - line text - what changed` handed to Ken (targets and She Used To Be Mine first, 20 + 72 lines); no code changed; Decisions 14-15 untouched. Open for Ken: the guard on every re-align (rows 49, 59: 13 trimmed, 9 not kept; Miss Independent 79: unguarded re-align `That's` 239.38-240.08, `why` 240.08-240.36 (transcriber 239.44-240.08, 240.08-240.36), kept line `That's` 240.28-240.32, `why` 240.32-240.34), review findings in `plans/open-issues.md` at landing |

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

**R55 summary** (`three.py summary`, verbatim; PRE / MID / NOW; floored = an ASS word of at most 0.10 s; overlap pairs = output line start before the previous line's end; `edge_snap` lines left out).

| song | n lines | floored lines PRE/MID/NOW | floored words PRE/MID/NOW | overlap pairs PRE/MID/NOW | short lines PRE/MID/NOW | no-word lines PRE/MID/NOW | cue_inputs |
|---|---|---|---|---|---|---|---|
| Stronger | 39 | 8/8/8 | 11/11/9 | 0/2/1 | 4/0/0 | 0/0/0 | sections 39 realigns 13 spans 39 |
| All of Me | 56 | 7/7/6 | 7/7/6 | 1/2/1 | 3/0/0 | 0/0/0 | sections 56 realigns 8 spans 56 |
| Someone Like You | 56 | 13/14/9 | 15/16/9 | 0/2/0 | 3/0/0 | 0/0/0 | sections 56 realigns 12 spans 56 |
| Baby One More Time | 46 | 20/22/18 | 23/24/20 | 0/0/1 | 2/0/0 | 0/0/0 | sections 46 realigns 15 spans 46 |
| Miss Independent | 89 | 34/32/31 | 46/48/42 | 6/7/5 | 2/0/0 | 0/0/0 | sections 89 realigns 30 spans 89 |
| Pocahontas | 37 | 13/14/7 | 15/16/7 | 0/0/0 | 1/0/0 | 0/0/0 | sections 37 realigns 10 spans 37 |
| Incomplete | 27 | 8/8/6 | 8/8/6 | 0/0/0 | 1/0/0 | 0/0/0 | sections 27 realigns 4 spans 27 |
| Castle On The Hill | 56 | 11/10/7 | 12/11/8 | 1/1/3 | 1/0/0 | 0/0/0 | sections 56 realigns 15 spans 56 |
| My Heart Will Go On | 27 | 6/2/3 | 6/2/3 | 1/1/1 | 1/0/0 | 0/0/0 | sections 27 realigns 5 spans 27 |
| She Used To Be Mine | 45 | 7/7/4 | 12/12/6 | 0/0/0 | 0/0/0 | 0/0/0 | sections 45 realigns 4 spans 45 |

**Stronger** (AJWtLf4-WWs) captured PRE 2026-10-29T23:09:26+00:00 MID 2026-10-31T17:53:47+00:00 NOW 2026-11-02T20:31:33+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 39/39
- repace PRE: {"offset_s": -0.596, "n_repaced": 1, "repaced_line_ids": [21], "n_realigned": 0, "realigned_line_ids": []}
- repace MID: {"offset_s": -0.497, "n_repaced": 2, "repaced_line_ids": [1, 21], "n_realigned": 1, "realigned_line_ids": [32], "n_guessed_words": 2, "guessed_word_line_ids": [26]}
- repace NOW: {"offset_s": -0.596, "n_repaced": 1, "repaced_line_ids": [21], "n_realigned": 7, "realigned_line_ids": [6, 10, 18, 19, 26, 32, 35], "n_guessed_words": 3, "guessed_word_line_ids": [37], "crammed_line_ids": [1, 9, 10, 18, 19, 20, 24, 35], "n_windows": 13, "windows_widened_line_ids": [1, 6, 9, 10, 18, 19, 26, 32, 37], "windows_unmeasured_line_ids": []}
- realigns NOW (13): L1[18.20,25.45], L6[42.22,50.59], L9[59.42,67.45], L10[66.70,73.20], L18[103.95,111.89], L19[111.14,117.64], L20[117.06,122.67], L21[121.17,124.04], L24[131.25,136.77], L26[140.13,149.38], L32[174.44,181.99], L35[192.30,198.14], L37[200.29,208.63]

**All of Me** (450p7goxZqg) captured PRE 2026-10-19T18:54:26+00:00 MID 2026-10-31T18:00:26+00:00 NOW 2026-11-02T20:39:10+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 56/56
- repace PRE: {"offset_s": -0.296, "n_repaced": 2, "repaced_line_ids": [22, 40], "n_realigned": 0, "realigned_line_ids": []}
- repace MID: {"offset_s": -0.254, "n_repaced": 1, "repaced_line_ids": [22], "n_realigned": 1, "realigned_line_ids": [40], "n_guessed_words": 0, "guessed_word_line_ids": []}
- repace NOW: {"offset_s": -0.296, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 7, "realigned_line_ids": [22, 29, 40, 46, 47, 49, 55], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [45, 47, 55], "n_windows": 8, "windows_widened_line_ids": [29, 40, 45, 46, 49, 55], "windows_unmeasured_line_ids": []}
- realigns NOW (8): L22[104.73,109.37], L29[130.57,140.04], L40[182.01,189.60], L45[208.01,214.51], L46[213.51,220.94], L47[220.19,225.63], L49[228.04,236.19], L55[265.90,275.88]

**Someone Like You** (hLQl3WQQoQ0) captured PRE 2026-10-19T18:12:58+00:00 MID 2026-10-31T17:48:23+00:00 NOW 2026-11-02T20:23:54+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 56/56
- repace PRE: {"offset_s": -0.509, "n_repaced": 1, "repaced_line_ids": [44], "n_realigned": 1, "realigned_line_ids": [45]}
- repace MID: {"offset_s": -0.525, "n_repaced": 1, "repaced_line_ids": [44], "n_realigned": 1, "realigned_line_ids": [45], "n_guessed_words": 4, "guessed_word_line_ids": [49]}
- repace NOW: {"offset_s": -0.509, "n_repaced": 1, "repaced_line_ids": [44], "n_realigned": 10, "realigned_line_ids": [1, 16, 32, 33, 34, 42, 45, 46, 49, 50], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [1, 27, 32, 34, 42, 46, 50], "n_windows": 12, "windows_widened_line_ids": [16, 32, 33, 42, 49], "windows_unmeasured_line_ids": []}
- realigns NOW (12): L1[20.34,25.28], L16[79.05,86.93], L27[138.53,143.31], L32[156.60,163.30], L33[162.55,170.36], L34[169.61,174.67], L42[203.57,210.17], L44[216.47,221.56] None, L45[220.06,225.06], L46[223.56,227.57], L49[237.76,245.64], L50[244.89,249.92]

**Baby One More Time** (C-u5WLJ9Yk4) captured PRE 2026-10-29T23:06:24+00:00 MID 2026-10-31T17:52:01+00:00 NOW 2026-11-02T20:29:03+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 46/46
- repace PRE: {"offset_s": -0.115, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 1, "realigned_line_ids": [28]}
- repace MID: {"offset_s": -0.104, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 1, "realigned_line_ids": [28], "n_guessed_words": 0, "guessed_word_line_ids": []}
- repace NOW: {"offset_s": -0.115, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 6, "realigned_line_ids": [2, 3, 20, 27, 28, 30], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [0, 1, 2, 3, 4, 13, 15, 16, 27, 29, 39, 40], "n_windows": 15, "windows_widened_line_ids": [0, 2, 4, 20, 28, 29, 30], "windows_unmeasured_line_ids": []}
- realigns NOW (15): L0[16.99,23.49], L1[22.10,28.60], L2[27.34,34.71], L3[34.64,39.23], L4[37.73,45.69], L13[79.23,82.58], L15[86.32,90.89], L16[89.39,92.85], L20[103.80,110.73], L27[136.03,142.37], L28[140.87,148.08], L29[151.43,161.14], L30[160.39,169.59], L39[199.93,203.35], L40[201.85,207.63]

**Miss Independent** (k6M5C-oKw9k) captured PRE 2026-10-29T23:30:17+00:00 MID 2026-10-31T18:02:51+00:00 NOW 2026-11-02T20:43:01+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 89/89
- repace PRE: {"offset_s": 0.13, "n_repaced": 4, "repaced_line_ids": [5, 7, 12, 37], "n_realigned": 3, "realigned_line_ids": [38, 72, 78]}
- repace MID: {"offset_s": 0.112, "n_repaced": 5, "repaced_line_ids": [5, 7, 12, 37, 65], "n_realigned": 4, "realigned_line_ids": [9, 38, 72, 78], "n_guessed_words": 2, "guessed_word_line_ids": [9, 71]}
- repace NOW: {"offset_s": 0.13, "n_repaced": 3, "repaced_line_ids": [5, 7, 37], "n_realigned": 11, "realigned_line_ids": [2, 3, 9, 11, 12, 24, 38, 58, 72, 78, 81], "n_guessed_words": 3, "guessed_word_line_ids": [9, 71], "crammed_line_ids": [0, 1, 2, 3, 4, 10, 11, 24, 34, 36, 39, 48, 49, 52, 58, 66, 73, 74, 79, 81, 85], "n_windows": 30, "windows_widened_line_ids": [0, 1, 2, 3, 4, 5, 7, 9, 10, 11, 12, 24, 34, 36, 37, 38, 39, 48, 49, 52, 58, 66, 71, 72, 73, 74, 78, 79, 81, 85], "windows_unmeasured_line_ids": []}
- realigns NOW (30): L0[4.25,7.81], L1[6.35,11.01], L2[9.55,12.71], L3[11.25,14.21], L4[12.75,16.61], L5[15.15,18.15], L7[18.78,22.65], L9[23.18,26.58], L10[36.05,40.41], L11[38.95,43.91], L12[42.45,48.68], L24[79.58,85.38], L34[109.95,113.41], L36[114.08,117.58], L37[116.11,119.91], L38[118.45,122.71], L39[121.25,127.01], L48[147.25,151.75], L49[150.28,155.31], L52[161.48,166.38], L58[180.45,184.48], L66[200.15,206.05], L71[216.48,220.15], L72[218.68,223.05], L73[221.58,225.88], L74[224.41,229.18], L78[235.41,240.45], L79[238.98,242.95], L81[243.45,247.05], L85[257.05,262.28]

**Pocahontas** (9ThO76peOw0) captured PRE 2026-10-30T00:36:59+00:00 MID 2026-10-31T18:04:19+00:00 NOW 2026-11-02T20:45:06+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 37/37
- repace PRE: {"offset_s": -0.146, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 3, "realigned_line_ids": [6, 7, 8]}
- repace MID: {"offset_s": -0.152, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 3, "realigned_line_ids": [6, 7, 8], "n_guessed_words": 0, "guessed_word_line_ids": []}
- repace NOW: {"offset_s": -0.146, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 10, "realigned_line_ids": [6, 7, 8, 9, 19, 20, 23, 27, 33, 36], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [9, 19, 20, 23, 27, 33], "n_windows": 10, "windows_widened_line_ids": [36], "windows_unmeasured_line_ids": []}
- realigns NOW (10): L6[19.34,33.58], L7[32.08,38.38], L8[36.88,43.33], L9[41.83,47.77], L19[87.97,103.25], L20[101.75,107.35], L23[114.07,120.17], L27[131.53,138.23], L33[161.65,168.33], L36[173.94,190.90]

**Incomplete** (WVe80iZtlYU) captured PRE 2026-10-29T17:52:54+00:00 MID 2026-10-31T17:50:29+00:00 NOW 2026-11-02T20:26:23+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 27/27
- repace PRE: {"offset_s": -0.69, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 0, "realigned_line_ids": []}
- repace MID: {"offset_s": -0.686, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 0, "realigned_line_ids": [], "n_guessed_words": 0, "guessed_word_line_ids": []}
- repace NOW: {"offset_s": -0.69, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 3, "realigned_line_ids": [2, 3, 6], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [2, 6, 10], "n_windows": 4, "windows_widened_line_ids": [2, 3, 6], "windows_unmeasured_line_ids": []}
- realigns NOW (4): L2[31.59,39.33], L3[38.58,47.12], L6[63.83,70.42], L10[106.78,111.79]

**Castle On The Hill** (K0ibBPhiaG0) captured PRE 2026-10-29T23:16:15+00:00 MID 2026-10-31T17:58:10+00:00 NOW 2026-11-02T20:36:15+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 56/56
- repace PRE: {"offset_s": -0.17, "n_repaced": 1, "repaced_line_ids": [37], "n_realigned": 1, "realigned_line_ids": [36]}
- repace MID: {"offset_s": -0.17, "n_repaced": 1, "repaced_line_ids": [37], "n_realigned": 1, "realigned_line_ids": [36], "n_guessed_words": 2, "guessed_word_line_ids": [46]}
- repace NOW: {"offset_s": -0.17, "n_repaced": 1, "repaced_line_ids": [37], "n_realigned": 7, "realigned_line_ids": [2, 10, 23, 30, 32, 36, 53], "n_guessed_words": 2, "guessed_word_line_ids": [46], "crammed_line_ids": [0, 2, 4, 10, 14, 16, 23, 24, 27, 30, 32, 53], "n_windows": 15, "windows_widened_line_ids": [0, 2, 4, 10, 14, 16, 23, 24, 27, 30, 32, 36, 37, 46, 53], "windows_unmeasured_line_ids": []}
- realigns NOW (15): L0[23.88,28.28], L2[38.24,41.78], L4[45.16,48.30], L10[66.72,70.94], L14[83.52,90.42], L16[90.72,99.55], L23[126.60,130.06], L24[128.76,135.38], L27[142.20,145.66], L30[151.20,159.23], L32[161.56,168.66], L36[179.48,185.10], L37[183.92,187.42], L46[225.64,229.66], L53[257.92,262.86]

**My Heart Will Go On** (9bFHsd3o1w0) captured PRE 2026-10-29T23:12:32+00:00 MID 2026-10-31T17:56:30+00:00 NOW 2026-11-02T20:33:30+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 27/27
- repace PRE: {"offset_s": -0.19, "n_repaced": 2, "repaced_line_ids": [10, 19], "n_realigned": 4, "realigned_line_ids": [8, 24, 25, 26]}
- repace MID: {"offset_s": -0.377, "n_repaced": 4, "repaced_line_ids": [3, 19, 25, 26], "n_realigned": 1, "realigned_line_ids": [8], "n_guessed_words": 0, "guessed_word_line_ids": []}
- repace NOW: {"offset_s": -0.361, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 5, "realigned_line_ids": [3, 8, 19, 25, 26], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [], "n_windows": 5, "windows_widened_line_ids": [26], "windows_unmeasured_line_ids": []}
- realigns NOW (5): L3[39.64,45.80], L8[78.72,88.26], L19[165.43,175.22], L25[232.18,239.18], L26[237.68,263.32]

**She Used To Be Mine** (53GIADHxVzM) captured PRE 2026-10-30T14:57:39+00:00 MID 2026-10-30T14:57:39+00:00 NOW 2026-11-02T20:46:53+00:00; method NOW cue_align, schema 11; ASS dialogues vs timings NOW 45/45
- repace PRE: {"offset_s": -0.39, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 1, "realigned_line_ids": [41]}
- repace MID: {"offset_s": -0.39, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 1, "realigned_line_ids": [41]}
- repace NOW: {"offset_s": -0.39, "n_repaced": 0, "repaced_line_ids": [], "n_realigned": 4, "realigned_line_ids": [6, 7, 29, 41], "n_guessed_words": 0, "guessed_word_line_ids": [], "crammed_line_ids": [6, 7, 29], "n_windows": 4, "windows_widened_line_ids": [], "windows_unmeasured_line_ids": []}
- realigns NOW (4): L6[32.18,38.84], L7[37.34,41.18], L29[143.51,149.79], L41[209.80,216.38]

**R55 stage log** (`regen_run.log`, in run order, 10 songs: Someone Like You, Incomplete, Baby One More Time, Stronger, My Heart Will Go On, Castle, All of Me, Miss Independent, Pocahontas, She Used To Be Mine).

```
15:21:13 INFO pikaraoke.lib.cue_align: cue-align: 56 cues -> 13 sections
15:23:30 WARNING pikaraoke.pipeline.stages.lyric_align: [lyric_align] line 44 slice-align failed, degrading: Whisper worker error: 'NoneType' object has no attribute 'language'
15:23:54 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.51s, 10 line(s) re-aligned, 1/56 re-paced from cue, 0 word(s) guessed in 0 line(s), 7 crammed line(s) asked for a re-align; 5/12 window(s) widened to the singing, 0 left unmeasured
15:24:05 INFO pikaraoke.lib.cue_align: cue-align: 27 cues -> 18 sections
15:26:23 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.69s, 3 line(s) re-aligned, 0/27 re-paced from cue, 0 word(s) guessed in 0 line(s), 3 crammed line(s) asked for a re-align; 3/4 window(s) widened to the singing, 0 left unmeasured
15:26:37 INFO pikaraoke.lib.cue_align: cue-align: 46 cues -> 8 sections
15:29:03 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.12s, 6 line(s) re-aligned, 0/46 re-paced from cue, 0 word(s) guessed in 0 line(s), 12 crammed line(s) asked for a re-align; 7/15 window(s) widened to the singing, 0 left unmeasured
15:29:14 INFO pikaraoke.lib.cue_align: cue-align: 39 cues -> 10 sections
15:31:33 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.60s, 7 line(s) re-aligned, 1/39 re-paced from cue, 3 word(s) guessed in 1 line(s), 8 crammed line(s) asked for a re-align; 9/13 window(s) widened to the singing, 0 left unmeasured
15:31:42 WARNING pikaraoke.pipeline.stages.lyric_align: [lyric_align] transcribe yield 22.5 wpm < 30.0 — vocal stem looks reverb-washed; retrying on a de-reverbed stem
15:31:53 INFO pikaraoke.lib.cue_align: cue-align: 27 cues -> 5 sections
15:33:29 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.36s, 5 line(s) re-aligned, 0/27 re-paced from cue, 0 word(s) guessed in 0 line(s), 0 crammed line(s) asked for a re-align; 1/5 window(s) widened to the singing, 0 left unmeasured
15:33:45 INFO pikaraoke.lib.cue_align: cue-align: 56 cues -> 9 sections
15:36:15 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.17s, 7 line(s) re-aligned, 1/56 re-paced from cue, 2 word(s) guessed in 1 line(s), 12 crammed line(s) asked for a re-align; 15/15 window(s) widened to the singing, 0 left unmeasured
15:36:31 INFO pikaraoke.lib.cue_align: cue-align: 56 cues -> 13 sections
15:39:10 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.30s, 7 line(s) re-aligned, 0/56 re-paced from cue, 0 word(s) guessed in 0 line(s), 3 crammed line(s) asked for a re-align; 6/8 window(s) widened to the singing, 0 left unmeasured
15:39:34 INFO pikaraoke.lib.cue_align: cue-align: 89 cues -> 8 sections
15:43:01 INFO pikaraoke.lib.cue_align: cue rescue: offset=+0.13s, 11 line(s) re-aligned, 3/89 re-paced from cue, 3 word(s) guessed in 2 line(s), 21 crammed line(s) asked for a re-align; 30/30 window(s) widened to the singing, 0 left unmeasured
15:43:13 INFO pikaraoke.lib.cue_align: cue-align: 37 cues -> 4 sections
15:45:06 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.15s, 10 line(s) re-aligned, 0/37 re-paced from cue, 0 word(s) guessed in 0 line(s), 6 crammed line(s) asked for a re-align; 1/10 window(s) widened to the singing, 0 left unmeasured
15:45:20 INFO pikaraoke.lib.cue_align: cue-align: 45 cues -> 5 sections
15:46:52 INFO pikaraoke.lib.cue_align: cue rescue: offset=-0.39s, 4 line(s) re-aligned, 0/45 re-paced from cue, 0 word(s) guessed in 0 line(s), 3 crammed line(s) asked for a re-align; 0/4 window(s) widened to the singing, 0 left unmeasured
```

**R55t targets** (`three.py targets`, verbatim).

| song | L | text | tokens | words PRE/MID/NOW | floored PRE/MID/NOW | source PRE / MID / NOW | start PRE/MID/NOW | end PRE/MID/NOW | heard first/last | timed in full NOW |
|---|---|---|---|---|---|---|---|---|---|---|
| Stronger | 6 | You might think that I won't make it on my own | 11 | 8/11/11 | 0/0/0 | aligned / aligned / re-aligned | 44.06/43.91/42.92 | 50.34/50.66/50.58 | 42.86/51.10 | yes |
| Stronger | 26 | Here I go, here I go, here I go, here I go, here I go | 15 | 13/15/15 | 4/4/2 | aligned / aligned +guessed words / re-aligned | 141.71/141.71/141.63 | 146.62/146.86/149.65 | -/- | NO |
| Stronger | 32 | I, I'm stronger than yesterday | 5 | 4/5/5 | 0/1/0 | aligned / re-aligned / re-aligned | 176.56/175.16/175.57 | 182.56/182.56/182.56 | 176.16/180.38 | yes |
| Stronger | 37 | My loneliness ain't killing me no more, no more | 9 | 6/9/9 | 0/0/0 | aligned / aligned / aligned +guessed words | 201.69/201.71/201.69 | 209.30/208.90/209.30 | 201.86/206.80 | NO |
| All of Me | 29 | I can't stop singing, it's ringing in my head for you | 11 | 9/11/11 | 0/0/0 | aligned / aligned / re-aligned | 131.72/131.72/131.70 | 137.25/139.83/139.83 | 131.40/138.98 | yes |
| All of Me | 46 | 'Cause all of me loves all of you | 8 | 6/8/8 | 0/0/0 | aligned / aligned / re-aligned | 214.53/214.53/214.53 | 220.83/220.83/220.57 | 213.78/220.70 | yes |
| All of Me | 49 | Give your all to me, I'll give my all to you | 11 | 9/11/11 | 0/1/1 | aligned / aligned / re-aligned | 229.05/229.05/229.09 | 236.10/236.10/236.10 | 229.09/235.92 | NO |
| Someone Like You | 16 | I wish nothing but the best for you, too | 9 | 7/9/9 | 0/0/1 | aligned / aligned / re-aligned | 79.19/79.19/79.30 | 86.59/86.47/86.59 | 79.22/86.44 | NO |
| Someone Like You | 33 | I wish nothing but the best for you, too | 9 | 8/9/9 | 0/0/0 | aligned / aligned / re-aligned | 161.83/161.85/163.19 | 170.82/170.78/169.84 | 162.92/170.00 | yes |
| Someone Like You | 49 | I wish nothing but the best for you, too | 9 | 8/9/9 | 1/2/1 | aligned / aligned +guessed words / re-aligned | 237.85/237.77/238.01 | 245.75/242.01/245.05 | 237.88/245.28 | NO |
| Baby One More Time | 20 | Tell me, baby, 'cause I need to know now, oh because | 11 | 9/11/11 | 0/1/0 | aligned / aligned / re-aligned | 105.25/105.26/104.44 | 110.86/110.86/110.86 | 105.18/110.64 | yes |
| Baby One More Time | 30 | I must confess, that my loneliness is killing me now | 10 | 8/10/10 | 0/1/0 | aligned / aligned / re-aligned | 161.18/161.55/161.10 | 169.50/169.48/169.50 | -/168.20 | yes |
| Miss Independent | 9 | Good morning. God damn. | 4 | 2/4/4 | 1/0/1 | aligned / re-aligned +guessed words / re-aligned +guessed words | 24.62/23.45/23.43 | 25.01/26.45/25.92 | -/- | NO |
| Miss Independent | 71 | Ooh yeah, ooh yeah | 4 | 2/4/4 | 0/0/0 | aligned / aligned +guessed words / aligned +guessed words | 216.36/216.20/216.36 | 218.40/219.08/219.08 | -/- | NO |
| Pocahontas | 36 | You can paint with all the colors of the wind | 10 | 6/10/10 | 0/0/0 | aligned / aligned / re-aligned | 174.13/174.13/174.19 | 178.87/183.95/190.20 | -/184.92 | yes |
| Incomplete | 3 | Where I'm going is anybody's guess | 6 | 4/6/6 | 0/0/0 | aligned / aligned / re-aligned | 39.69/39.69/39.62 | 43.51/47.20/47.20 | 39.20/46.04 | yes |
| Castle On The Hill | 46 | And I'm on my way | 5 | 3/5/5 | 0/0/0 | aligned / aligned +guessed words / aligned +guessed words | 226.67/226.67/226.67 | 228.80/228.80/228.80 | 226.74/228.88 | NO |
| My Heart Will Go On | 9 | And you're here in my heart | 6 | 4/6/6 | 0/0/0 | aligned / aligned / aligned | 87.15/87.11/87.09 | 92.13/92.25/92.23 | 87.87/92.26 | yes |
| She Used To Be Mine | 5 | It's not easy to know | 5 | 5/5/5 | 0/0/0 | aligned / aligned / aligned | 29.41/29.41/29.41 | 32.15/32.15/32.15 | 29.41/31.84 | yes |
| She Used To Be Mine | 6 | I'm not anything like I used to be | 8 | 8/8/8 | 4/4/0 | aligned / aligned / re-aligned | 33.23/33.23/33.30 | 36.09/36.09/38.14 | 33.31/38.02 | yes |
| She Used To Be Mine | 7 | Although it's true | 3 | 3/3/3 | 1/1/0 | aligned / aligned / re-aligned | 36.09/36.09/38.14 | 39.61/39.61/39.60 | 38.30/39.60 | yes |
| She Used To Be Mine | 8 | I was never attention sweet center | 6 | 6/6/6 | 0/0/0 | aligned / aligned / aligned | 40.60/40.60/40.60 | 44.37/44.37/44.37 | 40.67/44.28 | yes |

targets timed in full NOW (the 18, no guessed word, no floored word): 10 of 18

NOW words of the targets (ASS):
- Stronger L6 You[42.91-43.81] might[43.81-45.31] think[45.51-46.49] that[46.62-47.03] I[47.03-47.57] won't[47.57-48.09] make[48.09-48.45] it[48.63-49.19] on[49.19-49.93] my[49.93-50.19] own[50.19-50.57]
- Stronger L26 Here[141.63-141.87] I[141.87-142.05] go,[142.05-142.71] here[143.01-143.11] I[143.14-143.27] go,[143.27-144.03] here[144.13-144.25] I[144.25-144.43] go,[144.74-144.85] here[145.32-145.45] I[145.45-145.92] go,[146.02-146.21] here[146.64-148.14] I[148.49-148.59] go[148.59-149.75]
- Stronger L32 I,[175.57-177.74] I'm[177.84-178.26] stronger[179.18-179.91] than[180.01-180.26] yesterday[180.26-182.56]
- Stronger L37 My[201.69-202.55] loneliness[202.55-203.89] ain't[204.38-205.19] killing[205.19-205.72] me[205.82-206.13] no[206.13-206.63] more,[206.63-207.29] no[207.29-207.95] more[207.95-209.31]
- All of Me L29 I[131.69-131.88] can't[131.88-132.24] stop[132.24-132.76] singing,[133.13-134.18] it's[134.28-134.42] ringing[134.84-135.54] in[135.54-136.22] my[136.41-136.97] head[137.39-138.09] for[138.09-138.37] you[138.37-139.83]
- All of Me L46 'Cause[214.52-214.83] all[214.83-216.21] of[216.21-216.39] me[216.39-216.99] loves[218.13-218.29] all[218.29-220.07] of[220.17-220.31] you[220.31-220.57]
- All of Me L49 Give[229.09-229.31] your[229.31-229.61] all[230.06-230.81] to[231.12-231.65] me,[232.02-232.63] I'll[232.79-233.11] give[233.11-233.21] my[233.35-234.46] all[234.56-235.35] to[235.45-235.56] you[235.56-236.18]
- Someone Like You L16 I[79.29-80.28] wish[80.54-80.64] nothing[80.64-81.18] but[81.66-81.82] the[81.82-82.16] best[82.57-83.24] for[83.24-84.14] you,[84.3-85.18] too[85.28-86.58]
- Someone Like You L33 I[163.18-163.82] wish[163.98-164.16] nothing[164.32-164.79] but[165.23-165.37] the[165.37-165.77] best[166.14-166.75] for[167.29-167.95] you,[168.05-168.84] too[168.94-169.86]
- Someone Like You L49 I[238.0-239.13] wish[239.41-239.51] nothing[239.65-240.07] but[240.52-240.67] the[240.67-241.09] best[241.46-242.07] for[242.57-242.93] you,[243.39-243.54] too[243.99-245.05]
- Baby One More Time L20 Tell[104.43-105.29] me,[105.42-105.81] baby,[106.07-107.13] 'cause[107.13-107.47] I[107.47-107.65] need[107.75-108.05] to[108.05-108.27] know[108.27-108.83] now,[108.83-109.83] oh[109.85-110.43] because[110.43-110.85]
- Baby One More Time L30 I[161.09-161.5] must[161.5-161.88] confess,[161.88-163.12] that[163.12-163.76] my[163.87-164.18] loneliness[164.18-164.94] is[164.94-166.42] killing[166.42-166.86] me[167.0-167.41] now[167.41-169.5]
- Miss Independent L9 Good[23.43-24.66] morning.[24.66-25.24] God[25.24-25.34] damn.[25.34-25.92]
- Miss Independent L71 Ooh[216.36-217.86] yeah,[217.94-218.4] ooh[218.4-218.74] yeah[218.74-219.08]
- Pocahontas L36 You[174.19-175.1] can[175.26-175.76] paint[175.76-177.04] with[177.38-177.94] all[177.94-178.42] the[178.53-178.84] colors[179.4-180.18] of[180.28-182.23] the[182.33-182.85] wind[183.27-190.21]
- Incomplete L3 Where[39.62-39.77] I'm[39.77-40.77] going[41.23-42.0] is[42.0-43.5] anybody's[44.16-45.66] guess[45.74-47.19]
- Castle On The Hill L46 And[226.67-226.93] I'm[227.43-227.59] on[227.59-227.91] my[227.91-228.17] way[228.17-228.8]
- My Heart Will Go On L9 And[87.08-88.48] you're[88.61-89.02] here[89.02-90.04] in[90.14-90.76] my[90.9-91.32] heart[91.88-92.22]
- She Used To Be Mine L5 It's[29.4-29.58] not[29.69-30.02] easy[30.45-30.59] to[31.02-31.17] know[31.17-32.13]
- She Used To Be Mine L6 I'm[33.3-33.86] not[33.86-34.22] anything[34.36-34.78] like[34.78-36.28] I[36.5-36.82] used[36.94-37.28] to[37.28-37.62] be[37.75-38.14]
- She Used To Be Mine L7 Although[38.14-38.52] it's[38.52-39.3] true[39.3-39.6]
- She Used To Be Mine L8 I[40.6-40.81] was[40.81-41.11] never[41.22-41.55] attention[42.01-42.77] sweet[42.77-43.49] center[43.49-44.37]

**R55f targets timed in full** (`full.py`, verbatim; raw words from `cue_inputs`).

| song | L | tokens | words from | raw words >= 0.05 s | raw words < 0.05 s | guessed | timed in full |
|---|---|---|---|---|---|---|---|
| Stronger | 6 | 11 | re-align | 11 of 11 | 0 | no | yes |
| Stronger | 26 | 15 | re-align | 13 of 15 | 2 | no | NO |
| Stronger | 32 | 5 | re-align | 5 of 5 | 0 | no | yes |
| Stronger | 37 | 9 | section | 6 of 6 | 0 | yes | NO |
| All of Me | 29 | 11 | re-align | 11 of 11 | 0 | no | yes |
| All of Me | 46 | 8 | re-align | 8 of 8 | 0 | no | yes |
| All of Me | 49 | 11 | re-align | 10 of 11 | 1 | no | NO |
| Someone Like You | 16 | 9 | re-align | 9 of 9 | 0 | no | yes |
| Someone Like You | 33 | 9 | re-align | 9 of 9 | 0 | no | yes |
| Someone Like You | 49 | 9 | re-align | 9 of 9 | 0 | no | yes |
| Baby One More Time | 20 | 11 | re-align | 11 of 11 | 0 | no | yes |
| Baby One More Time | 30 | 10 | re-align | 10 of 10 | 0 | no | yes |
| Miss Independent | 9 | 4 | re-align | 3 of 3 | 0 | yes | NO |
| Miss Independent | 71 | 4 | section | 2 of 2 | 0 | yes | NO |
| Pocahontas | 36 | 10 | re-align | 10 of 10 | 0 | no | yes |
| Incomplete | 3 | 6 | re-align | 6 of 6 | 0 | no | yes |
| Castle On The Hill | 46 | 5 | section | 3 of 3 | 0 | yes | NO |
| My Heart Will Go On | 9 | 6 | section | 6 of 6 | 0 | no | yes |

timed in full by the model: 12 of 18

Lines NOW differs from PRE with no rescue on the line or its neighbours (aligned in NOW; start/end/word moved > 0.3 s or word text differs):
- My Heart Will Go On L1 0:25 I see you, I feel you: 2 word(s) moved > 0.3: I 27.72-28.30 -> 28.11-28.29, feel 28.61-29.12 -> 29.01-29.11; floored words 0 -> 1
- My Heart Will Go On L5 0:50 You have come to show you go on: 2 word(s) moved > 0.3: come 51.80-51.92 -> 51.46-51.88, show 52.63-53.08 -> 52.92-53.55; floored words 1 -> 0
- My Heart Will Go On L10 1:32 And my heart will go on and on: end 101.56 -> 100.35; source spaced -> aligned
- My Heart Will Go On L12 1:52 And last for a lifetime: 2 word(s) moved > 0.3: a 114.78-116.51 -> 114.76-116.87, lifetime 116.61-117.77 -> 116.97-117.70
- My Heart Will Go On L14 2:07 Love was when I loved you: start 128.31 -> 127.83
- My Heart Will Go On L15 2:12 One true time I hold to: end 136.73 -> 137.12
- My Heart Will Go On L16 2:17 In my life we'll always go on: start 136.73 -> 137.86
- My Heart Will Go On L17 2:28 Near, far, wherever you are: 1 word(s) moved > 0.3: you 153.16-154.27 -> 153.66-154.27
- My Heart Will Go On L21 3:00 And my heart will go on and on: 1 word(s) moved > 0.3: and 184.87-186.11 -> 185.60-185.79
- My Heart Will Go On L22 3:25 You're here, there's nothing I fear: 3 word(s) moved > 0.3: You're 205.80-207.49 -> 205.80-207.85, here, 207.59-209.34 -> 208.36-209.05, nothing 211.19-211.74 -> 211.58-211.76
- My Heart Will Go On L23 3:33 And I know that my heart will go on: 5 word(s) moved > 0.3: know 214.84-215.34 -> 214.86-215.80, that 215.52-216.76 -> 215.90-216.78, my 216.89-217.90 -> 216.90-217.28, heart 218.00-218.10 -> 217.28-218.12; floored words 1 -> 0
count: 11

**R55o overlaps** (`three.py overlaps`, verbatim).

| song | L | m:ss | prev end NOW | start NOW | overlap NOW | overlap PRE | overlap MID | captions overlap | source NOW |
|---|---|---|---|---|---|---|---|---|---|
| Stronger | 7 | 0:50 | 50.58 | 50.44 | 0.14 | - | 0.22 | no | aligned |
| Stronger | 32 | 2:55 | 175.56 | 175.57 | - | - | 0.40 | no | re-aligned |
| All of Me | 23 | 1:46 | 106.09 | 106.05 | 0.04 | 0.93 | 0.98 | no | aligned |
| All of Me | 40 | 3:03 | 182.56 | 183.07 | - | - | 0.26 | no | re-aligned |
| Someone Like You | 25 | 2:03 | 123.76 | 123.86 | - | - | 0.36 | no | aligned |
| Someone Like You | 26 | 2:10 | 130.88 | 130.98 | - | - | 0.42 | no | aligned |
| Baby One More Time | 4 | 0:38 | 38.56 | 38.55 | 0.00 | - | - | no | aligned |
| Miss Independent | 5 | 0:15 | 16.66 | 15.90 | 0.76 | 0.76 | 0.78 | no | spaced |
| Miss Independent | 6 | 0:17 | 17.40 | 17.36 | 0.03 | 0.03 | 0.01 | no | aligned |
| Miss Independent | 7 | 0:19 | 21.28 | 19.53 | 1.75 | 1.75 | 1.76 | no | spaced |
| Miss Independent | 37 | 1:57 | 117.88 | 117.13 | 0.76 | 0.76 | 0.76 | no | spaced |
| Miss Independent | 38 | 1:58 | 119.16 | 118.79 | 0.38 | 0.38 | 0.24 | no | re-aligned |
| Miss Independent | 65 | 3:20 | 199.62 | 200.52 | - | - | 0.50 | no | aligned |
| Miss Independent | 78 | 3:57 | 237.02 | 237.02 | - | 0.13 | 0.11 | no | re-aligned |
| Castle On The Hill | 3 | 0:41 | 41.22 | 41.17 | 0.05 | - | - | no | aligned |
| Castle On The Hill | 24 | 2:09 | 129.36 | 129.35 | 0.01 | - | - | no | aligned |
| Castle On The Hill | 38 | 2:58 | 186.17 | 178.92 | 7.25 | 7.25 | 7.25 | no | aligned |
| My Heart Will Go On | 20 | 2:54 | 174.55 | 174.36 | 0.19 | 0.26 | 0.07 | no | aligned |

Stronger: overlapping pairs PRE 0 MID 2 NOW 1
All of Me: overlapping pairs PRE 1 MID 2 NOW 1
Someone Like You: overlapping pairs PRE 0 MID 2 NOW 0
Baby One More Time: overlapping pairs PRE 0 MID 0 NOW 1
Miss Independent: overlapping pairs PRE 6 MID 7 NOW 5
Pocahontas: overlapping pairs PRE 0 MID 0 NOW 0
Incomplete: overlapping pairs PRE 0 MID 0 NOW 0
Castle On The Hill: overlapping pairs PRE 1 MID 1 NOW 3
My Heart Will Go On: overlapping pairs PRE 1 MID 1 NOW 1
She Used To Be Mine: overlapping pairs PRE 0 MID 0 NOW 0

**R55e early starts** (`three.py early5`, verbatim).

| song | L | text | heard first | start PRE/MID/NOW | start - heard PRE/MID/NOW |
|---|---|---|---|---|---|
| Stronger | 18 | My loneliness ain't killing me no more | 105.62 | 105.36/105.06/105.04 | -0.26/-0.56/-0.58 |
| Stronger | 32 | I, I'm stronger than yesterday | 176.16 | 176.56/175.16/175.57 | +0.40/-1.00/-0.59 |
| All of Me | 40 | 'Cause I give you all of me | 183.14 | 183.07/182.30/183.07 | -0.06/-0.83/-0.06 |
| Someone Like You | 48 | Never mind, I'll find someone like you | 232.77 | 232.65/230.72/232.65 | -0.12/-2.05/-0.12 |
| Miss Independent | 51 | She made for a boss, only a boss | 158.60 | 159.47/157.70/159.47 | +0.87/-0.90/+0.87 |

lines starting more than 0.5 s before the heard first word (count, per song: PRE/MID/NOW) and the whole-set total:
- Stronger: 10/12/13
- All of Me: 1/2/2
- Someone Like You: 7/8/8
- Baby One More Time: 10/10/11
- Miss Independent: 9/10/9
- Pocahontas: 4/4/4
- Incomplete: 2/2/2
- Castle On The Hill: 2/3/2
- My Heart Will Go On: 7/6/6
- She Used To Be Mine: 2/2/1
- total: 54/59/58

**R55s She Used To Be Mine 0:33-0:40, Castle L1 and L29** (`three.py she`, `castle`, verbatim).

```
transcriber words 32.5-40.5: I'm[33.31-33.86] not[33.86-34.22] anything[34.22-34.80] Like[36.35-36.52] I[36.52-36.84] used[36.84-37.34] to[37.34-37.62] be[37.62-38.02] Although[38.30-38.74] it's[38.74-39.30] true[39.30-39.60]

L6 I'm not anything like I used to be  [re-aligned]
  PRE: I'm[33.22-33.86] not[33.86-34.2] anything[34.35-34.78] like[34.78-36.08] I[36.08-36.18] used[36.18-36.28] to[36.28-36.38] be[36.38-36.48]  (line 33.23-36.09, floored 4)
  MID: I'm[33.22-33.86] not[33.86-34.2] anything[34.35-34.78] like[34.78-36.08] I[36.08-36.18] used[36.18-36.28] to[36.28-36.38] be[36.38-36.48]  (line 33.23-36.09, floored 4)
  NOW: I'm[33.3-33.86] not[33.86-34.22] anything[34.36-34.78] like[34.78-36.28] I[36.5-36.82] used[36.94-37.28] to[37.28-37.62] be[37.75-38.14]  (line 33.30-38.14, floored 0)

L7 Although it's true  [re-aligned]
  PRE: Although[36.09-36.19] it's[36.45-39.27] true[39.37-39.71]  (line 36.09-39.61, floored 1)
  MID: Although[36.09-36.19] it's[36.45-39.27] true[39.37-39.71]  (line 36.09-39.61, floored 1)
  NOW: Although[38.14-38.52] it's[38.52-39.3] true[39.3-39.6]  (line 38.14-39.60, floored 0)

realign L6 window 32.18-38.84: I'm[33.30-33.86] not[33.86-34.22] anything[34.36-34.78] like[34.78-36.50] I[36.50-36.82] used[36.94-37.28] to[37.28-37.62] be[37.75-38.14]

realign L7 window 37.34-41.18: Although[37.34-38.52] it's[38.52-39.30] true[39.30-39.60]
section L5: It's[29.41-29.59] not[29.70-30.03] easy[30.46-30.61] to[31.04-31.19] know[31.19-31.81]
section L6: I'm[33.23-33.87] not[33.87-34.21] anything[34.36-34.79] like[34.79-36.09] I[36.09-36.09] used[36.09-36.09] to[36.09-36.09] be[36.09-36.09]
section L7: Although[36.09-36.09] it's[36.35-37.85] true[39.27-39.61]
section L8: I[39.61-40.81] was[40.81-41.11] never[41.22-41.55] attention[42.01-42.77] sweet[42.77-43.49] center[43.49-44.37]

Castle L1 I was running from my brother and his friends: realign windows []; source NOW aligned
  PRE: I[31.9-32.04] was[32.04-32.24] running[32.34-32.64] from[32.78-33.19] my[33.31-33.67] brother[33.79-34.13] and[34.26-34.65] his[34.65-35.03] friends[35.13-35.43]
  MID: I[31.9-32.04] was[32.04-32.24] running[32.34-32.64] from[32.78-33.19] my[33.31-33.67] brother[33.79-34.13] and[34.26-34.65] his[34.65-35.03] friends[35.13-35.43]
  NOW: I[31.9-32.04] was[32.04-32.24] running[32.34-32.64] from[32.78-33.19] my[33.31-33.67] brother[33.79-34.13] and[34.26-34.65] his[34.65-35.03] friends[35.13-35.43]
Castle L29 I'm on my way: realign windows []; source NOW aligned
  PRE: I'm[148.77-149.38] on[149.38-149.66] my[149.66-150.02] way[150.02-150.68]
  MID: I'm[148.76-149.38] on[149.38-149.66] my[149.66-150.04] way[150.2-150.7]
  NOW: I'm[148.77-149.38] on[149.38-149.66] my[149.66-150.02] way[150.02-150.68]
```

**R55g guard on this run's re-aligns** (`replay_now.py guard`, verbatim; words before the edge snaps).

```
== Stronger (AJWtLf4-WWs): replay guard on: calls 13 of recorded 13, misses []; stats equal to the bundle's True
   guard off: calls 13, misses []; realigned [6, 10, 18, 19, 26, 32, 35, 37] guessed []
   lines the guard changes: [6, 18, 37]
   L6 You might think that I won't make it on my own  | previous line end (guard on) 42.92
      guard off [cue_align_line]: You[42.47-43.82] might[43.82-45.32] think[45.52-46.50] that[46.63-47.04] I[47.04-47.58] won't[47.58-48.10] make[48.10-48.46] it[48.64-49.20] on[49.20-49.94] my[49.94-50.20] own[50.20-50.58]
      guard on  [cue_align_line]: You[42.92-43.82] might[43.82-45.32] think[45.52-46.50] that[46.63-47.04] I[47.04-47.58] won't[47.58-48.10] make[48.10-48.46] it[48.64-49.20] on[49.20-49.94] my[49.94-50.20] own[50.20-50.58]
      transcriber: You[42.86-44.22] might[44.22-45.52] think[45.52-46.52] that[46.52-47.02] I[47.02-47.64] will[47.64-48.00] make[48.00-48.50] it[48.50-49.20] on[49.20-49.96] my[49.96-50.22] own[50.22-51.10] But[51.10-51.56] now[51.56-52.14]
   L18 My loneliness ain't killing me no more  | previous line end (guard on) 105.04
      guard off [cue_align_line]: My[104.20-105.45] loneliness[105.77-106.91] ain't[107.33-108.03] killing[108.03-108.63] me[109.40-109.51] no[109.68-110.01] more[110.01-110.75]
      guard on  [cue_align_line]: My[105.04-105.45] loneliness[105.77-106.91] ain't[107.33-108.03] killing[108.03-108.63] me[109.40-109.51] no[109.68-110.01] more[110.01-110.75]
      transcriber: a[103.66-103.92] mile[103.92-104.28] away[104.28-105.08] My[105.62-106.08] loneliness[106.08-106.92] ain't[106.92-107.98] killing[107.98-108.68] me[108.68-109.54] no[109.54-110.06] more[110.06-111.16]
   L37 My loneliness ain't killing me no more, no more  | previous line end (guard on) 201.69
      guard off [cue_align_line]: My[200.87-200.87] loneliness[201.34-202.84] ain't[203.75-205.17] killing[205.17-205.25] me[205.58-206.15] no[206.28-206.67] more,[206.67-207.29] no[207.51-207.67] more[207.67-207.97]
      guard on  [cue_align]: My[201.69-202.55] loneliness[202.55-203.89] ain't[204.38-205.19] killing[205.19-205.29] me[205.82-206.13] no[206.13-206.63] more,[206.63-207.29] no[207.29-207.94] more[207.94-208.60]
      transcriber: a[200.26-200.52] mile[200.52-201.08] away[201.08-201.66] My[201.86-202.46] loneliness[202.46-203.70] ain't[203.70-205.02] here[205.02-205.02] to[205.02-205.24] let[205.24-205.52] me[205.54-206.08] no[206.43-206.70] more[206.70-206.80]
== All of Me (450p7goxZqg): replay guard on: calls 8 of recorded 8, misses []; stats equal to the bundle's True
   guard off: calls 8, misses []; realigned [22, 29, 40, 46, 47, 49, 55] guessed []
   lines the guard changes: [40, 46, 47]
   L40 'Cause I give you all of me  | previous line end (guard on) 182.56
      guard off [cue_align_line]: 'Cause[182.32-183.37] I[183.37-183.57] give[183.57-183.79] you[183.79-184.09] all[184.09-185.13] of[186.35-187.85] me[188.03-188.35]
      guard on  [cue_align_line]: 'Cause[182.56-183.37] I[183.37-183.57] give[183.57-183.79] you[183.79-184.09] all[184.09-185.13] of[186.35-187.85] me[188.03-188.35]
      transcriber: lose,[181.38-181.86] I'm[182.08-182.22] winning[182.22-182.56] Cause[183.14-183.36] I[183.36-183.56] give[183.56-183.82] you[183.82-184.10] all[184.10-185.16] of[185.16-187.92] me[187.92-188.32]
   L46 'Cause all of me loves all of you  | previous line end (guard on) 213.77
      guard off [cue_align_line]: 'Cause[213.76-214.83] all[214.83-216.21] of[216.21-216.39] me[216.39-216.99] loves[218.13-218.29] all[218.29-219.23] of[220.18-220.31] you[220.31-220.57]
      guard on  [cue_align_line]: 'Cause[213.77-214.83] all[214.83-216.21] of[216.21-216.39] me[216.39-216.99] loves[218.13-218.29] all[218.29-219.23] of[220.18-220.31] you[220.31-220.57]
      transcriber: Cause[213.78-214.78] all[214.78-215.60] of[215.60-216.38] me[216.38-216.88] loves[216.88-218.30] all[218.30-219.28] of[219.28-220.26] you[220.26-220.70] Love[221.12-221.68]
   L47 Love your curves and all your edges  | previous line end (guard on) 220.57
      guard off [cue_align_line]: Love[220.44-221.57] your[221.57-222.01] curves[222.13-222.95] and[223.07-223.45] all[223.45-223.77] your[223.77-224.07] edges[224.07-224.59]
      guard on  [cue_align_line]: Love[220.57-221.57] your[221.57-222.01] curves[222.13-222.95] and[223.07-223.45] all[223.45-223.77] your[223.77-224.07] edges[224.07-224.59]
      transcriber: you[220.26-220.70] Love[221.12-221.68] your[221.68-222.14] curves[222.14-222.90] and[222.90-223.46] all[223.46-223.82] your[223.82-224.08] edges[224.08-224.52] All[225.31-225.52] your[225.52-226.00]
== Someone Like You (hLQl3WQQoQ0): replay guard on: calls 12 of recorded 12, misses []; stats equal to the bundle's True
   guard off: calls 12, misses []; realigned [1, 16, 32, 33, 34, 42, 45, 46, 49, 50] guessed []
   lines the guard changes: []
== Baby One More Time (C-u5WLJ9Yk4): replay guard on: calls 15 of recorded 15, misses []; stats equal to the bundle's True
   guard off: calls 15, misses []; realigned [2, 3, 20, 27, 28, 30, 40] guessed []
   lines the guard changes: [40]
   L40 I must confess that my loneliness  | previous line end (guard on) 203.39
      guard off [cue_align_line]: I[202.10-202.67] must[202.67-203.13] confess[203.13-203.85] that[203.85-205.19] my[205.19-205.47] loneliness[205.47-206.17]
      guard on  [cue_align]: I[203.39-203.39] must[203.39-203.39] confess[203.39-203.99] that[203.99-205.11] my[205.11-205.47] loneliness[205.47-206.17]
      transcriber: hit[201.31-201.54] me[201.60-201.86] baby,[201.86-202.42] I'm[202.64-203.02] a[203.02-203.16] sign,[203.16-203.66] I[204.26-204.46] know[204.46-204.82] that[204.82-205.20] my[205.20-205.54] loneliness[205.54-206.12] is[206.12-206.56] giving[206.56-207.08] me[207.08-208.68]
== Miss Independent (k6M5C-oKw9k): replay guard on: calls 30 of recorded 30, misses []; stats equal to the bundle's True
   guard off: calls 30, misses []; realigned [1, 2, 3, 5, 9, 11, 12, 24, 38, 58, 72, 74, 78, 79, 81] guessed [9, 71]
   lines the guard changes: [1, 3, 5, 58, 74, 78, 79, 81]
   L1 Morning. Good morning, ne-yo.  | previous line end (guard on) 7.56
      guard off [cue_align_line]: Morning.[6.73-7.59] Good[7.71-7.97] morning,[7.97-8.23] ne-yo.[8.31-8.96]
      guard on  [cue_align]: Morning.[7.86-7.86] Good[7.88-7.90] morning,[7.90-8.14] ne-yo.[8.40-8.72]
      transcriber: morning.[7.30-7.42] I'm[7.60-7.80] sorry,[7.80-8.10] Mia.[8.26-8.44] Thank[8.76-9.02] you.[9.02-9.24] What's[9.60-9.82] going[9.82-9.82] on?[9.82-10.08]
   L3 Looking good.  | previous line end (guard on) 11.83
      guard off [cue_align_line]: Looking[11.69-11.93] good.[11.93-12.65]
      guard on  [cue_align_line]: Looking[11.83-11.93] good.[11.93-12.65]
      transcriber: morning.[11.22-11.56] Looking[11.90-12.02] good,[12.02-12.24] Mia.[12.34-12.52] Thank[12.78-12.98] you.[12.98-13.34]
   L5 Good morning.  | previous line end (guard on) 16.66
      guard off [cue_align_line]: Good[15.40-16.05] morning.[16.19-17.23]
      guard on  [cue_align_fill]: Good[15.90-16.44] morning.[16.44-17.40]
      transcriber: morning.[14.62-14.96] I'm[15.12-15.24] fine.[15.24-15.44] Good[15.87-16.06] morning.[16.06-16.42] Looking[17.34-17.58] good.[17.58-17.90]
   L58 She got her own thing  | previous line end (guard on) 181.06
      guard off [cue_align_line]: She[180.70-181.37] got[181.37-181.77] her[181.77-182.25] own[182.25-182.71] thing[182.71-183.39]
      guard on  [cue_align_line]: She[181.06-181.37] got[181.37-181.77] her[181.77-182.25] own[182.25-182.71] thing[182.71-183.39]
      transcriber: a[179.72-180.30] little[180.30-180.44] time[180.44-180.96] She[181.12-181.40] got[181.40-181.84] the[181.84-182.12] wrong[182.12-182.62] thing[182.62-183.34] That's[183.70-184.30] why[184.30-184.58]
   L74 She got her own thing  | previous line end (guard on) 226.00
      guard off [cue_align_line]: She[225.93-226.03] got[226.03-226.51] her[226.51-226.93] own[226.93-227.41] thing[227.41-228.61]
      guard on  [cue_align]: She[226.00-226.00] got[226.00-226.58] her[226.58-226.78] own[226.78-227.44] thing[227.44-227.88]
      transcriber: got[225.94-226.58] nothing,[226.58-227.46] that's[228.42-228.98] why[228.98-229.22] I[229.22-229.50] love[229.50-230.04]
   L78 She got her own thing, she got, she got  | previous line end (guard on) 237.02
      guard off [cue_align_line]: She[236.89-237.23] got[237.53-237.65] her[237.65-237.89] own[237.89-238.67] thing,[238.67-238.79] she[238.79-238.79] got,[238.79-239.07] she[239.61-239.61] got[239.93-240.03]
      guard on  [cue_align_line]: She[237.02-237.23] got[237.53-237.65] her[237.65-237.89] own[237.89-238.67] thing,[238.67-238.79] she[238.79-238.79] got,[238.79-239.07] she[239.61-239.61] got[239.93-240.03]
      transcriber: that's[239.44-240.08] why[240.08-240.36] I[240.36-240.82] love[240.82-241.06]
   L79 That's why I love her  | previous line end (guard on) 240.03
      guard off [cue_align_line]: That's[239.38-240.08] why[240.08-240.36] I[240.36-240.64] love[240.64-242.14] her[242.24-242.44]
      guard on  [cue_align]: That's[240.28-240.32] why[240.32-240.34] I[240.45-240.76] love[240.76-241.06] her[241.59-242.48]
      transcriber: that's[239.44-240.08] why[240.08-240.36] I[240.36-240.82] love[240.82-241.06] her[241.06-242.21] That's[242.64-243.12] why[243.12-243.34] I'm[243.34-243.60]
   L81 Ooh, the way you shine  | previous line end (guard on) 244.20
      guard off [cue_align_line]: Ooh,[243.85-244.93] the[244.93-245.21] way[245.21-245.55] you[245.55-246.05] shine[246.05-246.51]
      guard on  [cue_align_line]: Ooh,[244.20-244.93] the[244.93-245.21] way[245.21-245.55] you[245.55-246.05] shine[246.05-246.51]
      transcriber: why[243.12-243.34] I'm[243.34-243.60] in[243.60-244.06] it.[244.06-244.50] I'm[245.56-245.92] gonna[245.92-245.92] shine,[245.92-246.82] it's[247.44-247.70]
== Pocahontas (9ThO76peOw0): replay guard on: calls 10 of recorded 10, misses []; stats equal to the bundle's True
   guard off: calls 10, misses []; realigned [6, 7, 8, 9, 19, 20, 23, 27, 33, 36] guessed []
   lines the guard changes: [23]
   L23 And for once, never wonder what they're worth  | previous line end (guard on) 114.72
      guard off [cue_align_line]: And[114.63-115.47] for[115.47-115.75] once,[115.75-116.47] never[116.65-116.87] wonder[116.87-117.43] what[117.43-117.77] they're[117.77-118.17] worth[118.17-118.87]
      guard on  [cue_align_line]: And[114.72-115.47] for[115.47-115.75] once,[115.75-116.47] never[116.65-116.87] wonder[116.87-117.43] what[117.43-117.77] they're[117.77-118.17] worth[118.17-118.87]
      transcriber: around[113.68-114.18] you[114.18-114.64] And[114.80-115.48] for[115.48-115.76] once[115.76-116.32] never[116.32-116.90] wonder[116.90-117.42] what[117.42-117.78] there[117.78-118.10] were[118.10-118.78] The[119.34-120.08]
== Incomplete (WVe80iZtlYU): replay guard on: calls 4 of recorded 4, misses []; stats equal to the bundle's True
   guard off: calls 4, misses []; realigned [2, 3, 6] guessed []
   lines the guard changes: []
== Castle On The Hill (K0ibBPhiaG0): replay guard on: calls 15 of recorded 15, misses []; stats equal to the bundle's True
   guard off: calls 15, misses []; realigned [2, 10, 14, 16, 23, 30, 32, 36, 46, 53] guessed []
   lines the guard changes: [14, 16, 32, 46]
   L14 And I miss the way you make me feel  | previous line end (guard on) 84.43
      guard off [cue_align_line]: And[83.77-84.42] I[84.56-85.00] miss[85.00-85.70] the[85.70-85.96] way[85.96-86.52] you[86.83-87.34] make[87.65-88.16] me[88.97-89.08] feel[89.24-89.72]
      guard on  [cue_align]: And[84.75-84.75] I[84.75-85.01] miss[85.18-85.69] the[85.69-85.95] way[85.95-86.43] you[86.78-87.35] make[87.35-87.97] me[88.95-89.09] feel[89.09-89.77]
      transcriber: dancer[83.44-84.16] And[84.16-84.74] I[84.74-85.04] miss[85.04-85.72] the[85.72-85.96] way[85.96-86.52] you[86.52-87.38] make[87.38-88.00] me[88.00-89.08] feel[89.08-89.76] It's[90.46-91.08]
   L16 When we watched the sunset over the castle on the hill  | previous line end (guard on) 91.47
      guard off [cue_align_line]: When[90.97-91.20] we[91.75-92.08] watched[92.08-93.08] the[93.08-93.36] sunset[93.36-94.30] over[94.30-95.52] the[96.02-96.86] castle[96.86-97.62] on[97.62-98.18] the[98.18-98.46] hill[98.46-98.80]
      guard on  [cue_align]: When[91.47-92.03] we[92.03-92.15] watched[92.15-93.07] the[93.07-93.35] sunset[93.70-94.29] over[94.87-96.15] the[96.33-96.87] castle[96.87-97.59] on[97.59-98.21] the[98.21-98.35] hill[98.35-98.37]
      transcriber: It's[90.46-91.08] true[91.08-91.46] when[91.46-91.96] we[91.96-92.16] watched[92.16-93.08] the[93.08-93.34] sunset[93.34-94.28] Over[95.14-96.12] the[96.12-96.88] castle[96.88-97.62] on[97.62-98.20] the[98.20-98.46] hill[98.46-98.80]
   L32 And I miss the way you make me feel  | previous line end (guard on) 162.42
      guard off [cue_align_line]: And[161.81-162.66] I[162.79-163.18] miss[163.18-163.92] the[163.92-164.18] way[164.18-164.74] you[165.06-165.58] make[165.58-166.22] me[167.16-167.30] feel[167.46-167.92]
      guard on  [cue_align_line]: And[162.42-162.66] I[162.79-163.18] miss[163.18-163.92] the[163.92-164.18] way[164.18-164.74] you[165.06-165.58] make[165.58-166.22] me[167.16-167.30] feel[167.46-167.92]
      transcriber: Dancer[161.62-162.46] And[162.46-162.96] I[162.96-163.22] miss[163.22-163.94] the[163.94-164.18] way[164.18-164.68] you[164.68-165.60] make[165.60-166.24] me[166.24-167.30] feel[167.30-167.94] It's[168.90-169.30]
   L46 And I'm on my way  | previous line end (guard on) 226.67
      guard off [cue_align_line]: And[225.89-226.60] I'm[226.97-227.60] on[227.60-227.86] my[227.96-228.26] way[228.69-228.84]
      guard on  [cue_align]: And[226.67-226.93] I'm[227.43-227.59] on[227.59-227.91] my[227.91-228.17] way[228.17-228.43]
      transcriber: to[225.18-225.72] go[225.72-226.10] on[226.10-226.66] And[226.74-226.94] I'm[226.94-227.60] on[227.60-227.90] my[227.90-228.26] way[228.26-228.88]
== My Heart Will Go On (9bFHsd3o1w0): replay guard on: calls 5 of recorded 5, misses []; stats equal to the bundle's True
   guard off: calls 5, misses []; realigned [3, 8, 19, 25, 26] guessed []
   lines the guard changes: [26]
   L26 My heart will go on and on  | previous line end (guard on) 238.24
      guard off [cue_align_line]: My[237.93-239.18] heart[239.28-239.96] will[239.96-240.64] go[241.21-241.66] on[241.66-243.16] and[243.67-243.98] on[243.98-244.94]
      guard on  [cue_align_line]: My[238.24-239.18] heart[239.28-239.96] will[239.96-240.64] go[241.21-241.66] on[241.66-243.16] and[243.67-243.98] on[243.98-244.94]
      transcriber: And[237.86-238.32] my[238.98-239.34] heart[239.34-239.96] will[239.97-241.14] go[241.14-241.68] on[241.68-243.16] and[243.16-244.00] on[244.00-244.42]
== She Used To Be Mine (53GIADHxVzM): replay guard on: calls 4 of recorded 4, misses []; stats equal to the bundle's True
   guard off: calls 4, misses []; realigned [6, 7, 29, 41] guessed []
   lines the guard changes: [7]
   L7 Although it's true  | previous line end (guard on) 38.14
      guard off [cue_align_line]: Although[37.59-38.52] it's[38.52-39.30] true[39.30-39.60]
      guard on  [cue_align_line]: Although[38.14-38.52] it's[38.52-39.30] true[39.30-39.60]
      transcriber: used[36.84-37.34] to[37.34-37.62] be[37.62-38.02] Although[38.30-38.74] it's[38.74-39.30] true[39.30-39.60]
```

**R55h vs_heard** (`vs_heard.py`, verbatim; tuple = lines with a heard first word, lines starting more than 0.5 s before it before, after, lines ending more than 0.3 s before the heard last word before, after; first PRE then MID as "before").

```
PRE as before:
song | lines with heard first | start >0.5 s before heard: before, after | heard last >0.3 s after end: before, after
Stronger (23, 10, 13, 1, 1)
All of Me (48, 1, 2, 3, 1)
Someone Like You (46, 7, 8, 2, 3)
Baby One More Time (40, 10, 11, 1, 1)
Miss Independent (53, 9, 9, 1, 0)
Pocahontas (31, 4, 4, 1, 0)
Incomplete (19, 2, 2, 3, 2)
Castle On The Hill (45, 2, 2, 0, 0)
My Heart Will Go On (20, 7, 6, 0, 1)
She Used To Be Mine (41, 2, 1, 1, 0)

start got earlier than heard by > 0.5 s and by 0.3 s more than before: song, L, m:ss, heard_first, start_b, start_a, start_b-heard, start_a-heard
('Stronger', 18, '1:45.04', 105.62, 105.36, 105.03800000000001, -0.26, -0.58)
('Stronger', 19, '1:51.39', 112.48, 113.372, 111.38600000000001, 0.89, -1.09)
('Stronger', 32, '2:55.57', 176.16, 176.56199999999998, 175.57299999999998, 0.4, -0.59)
('All of Me', 47, '3:40.57', 221.12, 221.645, 220.573, 0.53, -0.55)
('Someone Like You', 34, '2:49.99', 170.624, 170.917, 169.98799999999997, 0.29, -0.64)
('Someone Like You', 50, '4:05.14', 245.96, 246.196, 245.13699999999997, 0.24, -0.82)
('Baby One More Time', 20, '1:44.44', 105.18, 105.247, 104.439, 0.07, -0.74)

end got further before heard end (> 0.3 s, and 0.3 s more than before): song, L, m:ss, heard_last, end_b, end_a, heard-end_b, heard-end_a
('Someone Like You', 0, '0:14.04', 20.86, 21.433999999999997, 20.35, -0.57, 0.51)

MID as before:
song | lines with heard first | start >0.5 s before heard: before, after | heard last >0.3 s after end: before, after
Stronger (23, 12, 13, 1, 1)
All of Me (48, 2, 2, 1, 1)
Someone Like You (46, 8, 8, 1, 3)
Baby One More Time (40, 10, 11, 1, 1)
Miss Independent (53, 10, 9, 1, 0)
Pocahontas (31, 4, 4, 1, 0)
Incomplete (19, 2, 2, 2, 2)
Castle On The Hill (45, 3, 2, 0, 0)
My Heart Will Go On (20, 6, 6, 0, 1)
She Used To Be Mine (41, 2, 1, 1, 0)

start got earlier than heard by > 0.5 s and by 0.3 s more than before: song, L, m:ss, heard_first, start_b, start_a, start_b-heard, start_a-heard
('Stronger', 19, '1:51.39', 112.48, 113.372, 111.38600000000001, 0.89, -1.09)
('All of Me', 47, '3:40.57', 221.12, 221.645, 220.573, 0.53, -0.55)
('Someone Like You', 34, '2:49.99', 170.624, 170.87699999999998, 169.98799999999997, 0.25, -0.64)
('Someone Like You', 50, '4:05.14', 245.96, 246.176, 245.13699999999997, 0.22, -0.82)
('Baby One More Time', 20, '1:44.44', 105.18, 105.26400000000001, 104.439, 0.08, -0.74)

end got further before heard end (> 0.3 s, and 0.3 s more than before): song, L, m:ss, heard_last, end_b, end_a, heard-end_b, heard-end_a
('Someone Like You', 0, '0:14.04', 20.86, 21.433999999999997, 20.35, -0.57, 0.51)
('Someone Like You', 24, '1:57.21', 124.14, 124.212, 123.757, -0.07, 0.38)
('Someone Like You', 41, '3:14.06', 201.18, 201.55, 199.675, -0.37, 1.5)
```

**R55x changed lines** (`three.py changed`, verbatim; first / last err = start / end minus the transcriber's, seconds, base -> NOW).


## NOW against PRE

| song | L | m:ss | text | what changed | first err base -> NOW (verdict) | last err base -> NOW (verdict) |
|---|---|---|---|---|---|---|
| Stronger | 5 | 0:37 | I'm not your property as from today, baby | end 43.23 -> 42.92 | +0.30 -> +0.30 (tie) | - (?) |
| Stronger | 6 | 0:42 | You might think that I won't make it on my own | words 8 -> 11; start 44.06 -> 42.92; source aligned -> re-aligned | +1.20 -> +0.06 (closer) | -0.76 -> -0.52 (closer) |
| Stronger | 9 | 1:00 | My loneliness ain't killing me no more | end 68.56 -> 66.85 | -0.52 -> -0.52 (tie) | +2.26 -> +0.55 (closer) |
| Stronger | 10 | 1:06 | I, I'm stronger | start 68.66 -> 66.95; source aligned -> re-aligned | +1.42 -> -0.29 (closer) | -0.02 -> -0.04 (tie) |
| Stronger | 18 | 1:45 | My loneliness ain't killing me no more | start 105.36 -> 105.04; end 113.27 -> 111.29; source aligned -> re-aligned | -0.26 -> -0.58 (further) | +2.11 -> +0.13 (closer) |
| Stronger | 19 | 1:51 | I, I'm stronger | start 113.37 -> 111.39; source aligned -> re-aligned | +0.89 -> -1.09 (further) | +0.79 -> +0.84 (tie) |
| Stronger | 26 | 2:21 | Here I go, here I go, here I go, here I go, here I go | words 13 -> 15; end 146.62 -> 149.65; floored words 4 -> 2; source aligned -> re-aligned | - (?) | - (?) |
| Stronger | 31 | 2:49 | My loneliness ain't killing me no more | end 176.46 -> 175.56 | -0.06 -> -0.06 (tie) | +1.52 -> +0.62 (closer) |
| Stronger | 32 | 2:55 | I, I'm stronger than yesterday | words 4 -> 5; start 176.56 -> 175.57; source aligned -> re-aligned | +0.40 -> -0.59 (further) | +2.18 -> +2.18 (tie) |
| Stronger | 34 | 3:06 | My loneliness ain't killing me no more | end 193.51 -> 192.54 | -0.50 -> -0.50 (tie) | +1.53 -> +0.56 (closer) |
| Stronger | 35 | 3:12 | Now I'm stronger than yesterday | start 193.61 -> 192.64; source aligned -> re-aligned | +0.84 -> -0.13 (closer) | +0.11 -> -0.00 (closer) |
| Stronger | 37 | 3:21 | My loneliness ain't killing me no more, no more | words 6 -> 9; source aligned -> aligned +guessed words | -0.17 -> -0.17 (tie) | +2.50 -> +2.50 (tie) |
| All of Me | 22 | 1:44 | Oh | start 105.70 -> 104.98; end 106.98 -> 106.09; source spaced -> re-aligned | - (?) | - (?) |
| All of Me | 29 | 2:11 | I can't stop singing, it's ringing in my head for you | words 9 -> 11; end 137.25 -> 139.83; source aligned -> re-aligned | +0.32 -> +0.30 (tie) | -1.73 -> +0.85 (closer) |
| All of Me | 40 | 3:03 | 'Cause I give you all of me | 7 word(s) moved > 0.3: 'Cause 183.07-184.00 -> 183.07-183.36, I 184.00-184.25 -> 183.36-183.56, give 184.25-185.25 -> 183.56-183.78, you 185.25-186.00 -> 183.78-184.08; source spaced -> re-aligned | -0.06 -> -0.06 (tie) | +0.53 -> +0.56 (tie) |
| All of Me | 46 | 3:34 | 'Cause all of me loves all of you | words 6 -> 8; source aligned -> re-aligned | +0.75 -> +0.75 (tie) | +0.13 -> -0.13 (tie) |
| All of Me | 47 | 3:40 | Love your curves and all your edges | start 221.65 -> 220.57; floored words 1 -> 0; source aligned -> re-aligned | +0.53 -> -0.55 (tie) | +0.06 -> +0.07 (tie) |
| All of Me | 49 | 3:49 | Give your all to me, I'll give my all to you | words 9 -> 11; floored words 0 -> 1; source aligned -> re-aligned | -0.04 -> +0.01 (tie) | +0.18 -> +0.18 (tie) |
| All of Me | 55 | 4:26 | And you give me all of you, oh | end 270.95 -> 275.05; floored words 1 -> 0; source aligned -> re-aligned | -0.08 -> -0.08 (tie) | -2.65 -> +1.45 (closer) |
| Someone Like You | 0 | 0:14 | I heard that you're settled down | end 21.43 -> 20.35 | -0.07 -> -0.07 (tie) | +0.57 -> -0.51 (closer) |
| Someone Like You | 1 | 0:20 | That you found a girl | start 21.53 -> 20.59; floored words 1 -> 0; source aligned -> re-aligned | +0.67 -> -0.27 (closer) | +0.05 -> -0.08 (tie) |
| Someone Like You | 16 | 1:19 | I wish nothing but the best for you, too | words 7 -> 9; floored words 0 -> 1; source aligned -> re-aligned | -0.03 -> +0.08 (tie) | +0.15 -> +0.15 (tie) |
| Someone Like You | 32 | 2:37 | Never mind, I'll find someone like you | start 157.75 -> 157.24; end 161.83 -> 163.09; floored words 2 -> 0; source aligned -> re-aligned | +1.84 -> +1.33 (closer) | -0.01 -> +1.25 (further) |
| Someone Like You | 33 | 2:43 | I wish nothing but the best for you, too | words 8 -> 9; start 161.83 -> 163.19; end 170.82 -> 169.84; source aligned -> re-aligned | -1.09 -> +0.27 (closer) | +0.82 -> -0.16 (closer) |
| Someone Like You | 34 | 2:49 | Don't forget me, I begged | start 170.92 -> 169.99; floored words 2 -> 0; source aligned -> re-aligned | +0.29 -> -0.64 (further) | - (?) |
| Someone Like You | 42 | 3:24 | Never mind, I'll find someone like you | start 204.72 -> 204.37; floored words 1 -> 0; source aligned -> re-aligned | +0.30 -> -0.05 (closer) | +0.36 -> +0.26 (closer) |
| Someone Like You | 46 | 3:44 | Sometimes it lasts in love | start 225.24 -> 224.56; floored words 1 -> 0; source aligned -> re-aligned | +0.63 -> -0.05 (closer) | +0.04 -> +0.22 (further) |
| Someone Like You | 49 | 3:58 | I wish nothing but the best for you, too | words 8 -> 9; end 245.75 -> 245.05; source aligned -> re-aligned | -0.03 -> +0.13 (further) | +0.47 -> -0.23 (closer) |
| Someone Like You | 50 | 4:05 | Don't forget me, I begged | start 246.20 -> 245.14; source aligned -> re-aligned | +0.24 -> -0.82 (further) | - (?) |
| Baby One More Time | 2 | 0:28 | Oh baby, baby, how was I supposed to know | 3 word(s) moved > 0.3: baby, 29.42-29.58 -> 28.94-29.66, supposed 31.77-32.29 -> 31.76-32.66, to 32.61-33.15 -> 33.05-33.17; source aligned -> re-aligned | +0.63 -> +0.63 (tie) | +0.19 -> +0.19 (tie) |
| Baby One More Time | 3 | 0:35 | That something wasn't right here | floored words 1 -> 0; source aligned -> re-aligned | +0.23 -> -0.02 (closer) | +0.01 -> +0.02 (tie) |
| Baby One More Time | 19 | 1:40 | Show me how you want it to be | 1 word(s) moved > 0.3: be 104.08-104.54 -> 104.08-104.24 | -0.21 -> -0.21 (tie) | +0.23 -> -0.07 (closer) |
| Baby One More Time | 20 | 1:44 | Tell me, baby, 'cause I need to know now, oh because | words 9 -> 11; start 105.25 -> 104.44; source aligned -> re-aligned | +0.07 -> -0.74 (further) | +0.22 -> +0.22 (tie) |
| Baby One More Time | 26 | 2:11 | Oh baby, baby | end 136.28 -> 136.59 | - (?) | - (?) |
| Baby One More Time | 27 | 2:16 | Oh baby, baby | start 136.28 -> 136.69; end 138.62 -> 140.38; floored words 1 -> 0; source aligned -> re-aligned | -4.89 -> -4.48 (closer) | - (?) |
| Baby One More Time | 28 | 2:22 | Oh baby, baby, how was I supposed to know | 1 word(s) moved > 0.3: know 147.15-147.62 -> 146.80-147.48; floored words 2 -> 1 | - (?) | +0.17 -> +0.17 (tie) |
| Baby One More Time | 30 | 2:41 | I must confess, that my loneliness is killing me now | words 8 -> 10; source aligned -> re-aligned | - (?) | +1.30 -> +1.30 (tie) |
| Miss Independent | 1 | 0:07 | Morning. Good morning, ne-yo. | end 8.92 -> 9.70 | +0.56 -> +0.56 (tie) | - (?) |
| Miss Independent | 2 | 0:09 | Good morning. | start 9.02 -> 9.80; end 10.28 -> 11.83; source aligned -> re-aligned | -1.66 -> -0.88 (closer) | -1.28 -> +0.27 (closer) |
| Miss Independent | 3 | 0:11 | Looking good. | 1 word(s) moved > 0.3: good. 12.29-12.79 -> 11.92-12.64; source aligned -> re-aligned | -0.00 -> -0.07 (further) | +0.46 -> +0.41 (tie) |
| Miss Independent | 9 | 0:23 | Good morning. God damn. | words 2 -> 4; start 24.62 -> 23.43; end 25.01 -> 25.92; source aligned -> re-aligned +guessed words | - (?) | - (?) |
| Miss Independent | 11 | 0:39 | Ooh yeah, ooh yeah | 3 word(s) moved > 0.3: Ooh 39.29-40.03 -> 39.38-39.48, yeah, 40.03-40.13 -> 39.48-40.18, ooh 42.25-42.39 -> 41.07-42.18; source aligned -> re-aligned | - (?) | - (?) |
| Miss Independent | 12 | 0:42 | Ooh yeah, ooh yeah, ooh | start 43.20 -> 42.70; end 47.93 -> 46.38; source spaced -> re-aligned | - (?) | - (?) |
| Miss Independent | 24 | 1:21 | And she move like a boss, do what a boss do | floored words 2 -> 0; source aligned -> re-aligned | +0.91 -> +0.77 (closer) | +0.04 -> +0.02 (tie) |
| Miss Independent | 58 | 3:01 | She got her own thing | 2 word(s) moved > 0.3: own 182.64-182.76 -> 182.24-182.70, thing 183.26-183.42 -> 182.70-183.38; floored words 1 -> 0; source aligned -> re-aligned | +0.22 -> -0.06 (closer) | +0.00 -> +0.05 (tie) |
| Miss Independent | 71 | 3:36 | Ooh yeah, ooh yeah | words 2 -> 4; end 218.40 -> 219.08; source aligned -> aligned +guessed words | - (?) | - (?) |
| Miss Independent | 81 | 4:04 | Ooh, the way you shine | 3 word(s) moved > 0.3: Ooh, 244.20-245.30 -> 244.20-244.92, the 245.56-245.66 -> 244.92-245.20, way 245.66-245.80 -> 245.20-245.54; floored words 1 -> 0; source aligned -> re-aligned | - (?) | -0.10 -> +0.03 (closer) |
| Pocahontas | 9 | 0:43 | But I know every rock and tree and creature | floored words 1 -> 0; source aligned -> re-aligned | +0.19 -> +0.01 (closer) | +0.01 -> -0.01 (tie) |
| Pocahontas | 19 | 1:28 | Can you paint with all the colors of the wind | start 89.27 -> 88.93; end 103.24 -> 95.80; floored words 2 -> 0; source aligned -> re-aligned | +0.83 -> +0.49 (closer) | +8.48 -> +1.04 (closer) |
| Pocahontas | 20 | 1:43 | Come run the hidden pine trails of the forest | floored words 1 -> 0; source aligned -> re-aligned | +0.10 -> -0.07 (tie) | -0.02 -> -0.03 (tie) |
| Pocahontas | 23 | 1:55 | And for once, never wonder what they're worth | floored words 1 -> 0; source aligned -> re-aligned | +0.49 -> +0.40 (closer) | - (?) |
| Pocahontas | 27 | 2:12 | In a circle, in a hoop that never ends | 4 word(s) moved > 0.3: circle, 133.73-133.85 -> 133.25-133.97, in 134.31-134.41 -> 133.97-134.21, never 135.63-136.19 -> 135.19-135.53, ends 136.29-137.20 -> 135.53-136.91; floored words 2 -> 0; source aligned -> re-aligned | +0.69 -> +0.46 (closer) | +0.58 -> +0.48 (closer) |
| Pocahontas | 33 | 2:42 | We need to paint with all the colors of the wind | floored words 1 -> 0; source aligned -> re-aligned | - (?) | +0.41 -> +0.31 (closer) |
| Pocahontas | 36 | 2:54 | You can paint with all the colors of the wind | words 6 -> 10; end 178.87 -> 190.20; source aligned -> re-aligned | - (?) | -6.05 -> +5.28 (closer) |
| Incomplete | 2 | 0:31 | Without you, within me I can find no rest | start 32.48 -> 31.95; floored words 1 -> 0; source aligned -> re-aligned | +0.62 -> +0.09 (closer) | +0.44 -> +0.46 (tie) |
| Incomplete | 3 | 0:39 | Where I'm going is anybody's guess | words 4 -> 6; end 43.51 -> 47.20; source aligned -> re-aligned | +0.48 -> +0.42 (closer) | -2.53 -> +1.16 (closer) |
| Incomplete | 6 | 1:04 | I pray for this heart to be unbroken | 1 word(s) moved > 0.3: for 66.35-67.26 -> 66.96-67.15; floored words 1 -> 0; source aligned -> re-aligned | +1.43 -> +1.17 (closer) | +0.06 -> +0.05 (tie) |
| Castle On The Hill | 2 | 0:38 | And tasted the sweet perfume | 2 word(s) moved > 0.3: sweet 40.14-40.96 -> 40.06-40.40, perfume 41.06-41.26 -> 40.71-41.22; floored words 1 -> 0; source aligned -> re-aligned | +0.16 -> -0.00 (closer) | +0.01 -> +0.06 (tie) |
| Castle On The Hill | 10 | 1:06 | But I can't wait to go home | start 66.59 -> 66.97; source aligned -> re-aligned | -1.09 -> -0.71 (closer) | +0.07 -> +0.06 (tie) |
| Castle On The Hill | 23 | 2:07 | Take me back to when | floored words 1 -> 0; source aligned -> re-aligned | +0.23 -> -0.02 (closer) | +0.01 -> +0.02 (tie) |
| Castle On The Hill | 30 | 2:32 | Driving at 90 down those country lanes | start 153.04 -> 152.15; floored words 1 -> 0; source aligned -> re-aligned | +0.64 -> -0.25 (closer) | +0.16 -> +0.18 (tie) |
| Castle On The Hill | 31 | 2:38 | Singing to "Tiny Dancer" | end 162.88 -> 162.42 | -0.43 -> -0.43 (tie) | +0.42 -> -0.04 (closer) |
| Castle On The Hill | 32 | 2:42 | And I miss the way you make me feel | start 162.98 -> 162.42; floored words 1 -> 0; source aligned -> re-aligned | +0.52 -> -0.04 (closer) | +0.04 -> -0.02 (tie) |
| Castle On The Hill | 46 | 3:46 | And I'm on my way | words 3 -> 5; source aligned -> aligned +guessed words | -0.07 -> -0.07 (tie) | -0.08 -> -0.08 (tie) |
| Castle On The Hill | 52 | 4:15 | Hoo-ooh | end 256.74 -> 258.59 | - (?) | - (?) |
| Castle On The Hill | 53 | 4:18 | Over the castle on the hill | start 256.74 -> 258.69; source aligned -> re-aligned | - (?) | +0.04 -> -0.00 (tie) |
| My Heart Will Go On | 1 | 0:25 | I see you, I feel you | 2 word(s) moved > 0.3: I 27.72-28.30 -> 28.11-28.29, feel 28.61-29.12 -> 29.01-29.11; floored words 0 -> 1 | -1.72 -> -1.72 (tie) | +0.13 -> +0.13 (tie) |
| My Heart Will Go On | 2 | 0:31 | That is how I know you go on | start 30.31 -> 31.00 | -0.33 -> +0.36 (tie) | +1.66 -> +1.63 (tie) |
| My Heart Will Go On | 3 | 0:40 | Far across the distance | end 43.97 -> 44.55; source aligned -> re-aligned | - (?) | -0.01 -> +0.57 (further) |
| My Heart Will Go On | 4 | 0:45 | And spaces between us | start 43.97 -> 45.13; end 50.55 -> 50.23 | - (?) | +0.67 -> +0.34 (closer) |
| My Heart Will Go On | 5 | 0:50 | You have come to show you go on | 2 word(s) moved > 0.3: come 51.80-51.92 -> 51.46-51.88, show 52.63-53.08 -> 52.92-53.55; floored words 1 -> 0 | +0.57 -> +0.57 (tie) | +0.97 -> +0.92 (tie) |
| My Heart Will Go On | 7 | 1:07 | I believe that the heart does go on | 3 word(s) moved > 0.3: believe 69.38-70.39 -> 69.18-70.73, that 70.49-71.37 -> 70.83-71.36, the 71.91-72.09 -> 71.55-72.10 | -0.94 -> -1.02 (further) | +1.80 -> +1.77 (tie) |
| My Heart Will Go On | 8 | 1:19 | Once more, you open the door | 3 word(s) moved > 0.3: Once 79.50-80.89 -> 79.45-81.28, you 83.79-84.19 -> 83.78-85.02, open 84.19-86.11 -> 85.12-86.09 | - (?) | -0.13 -> -0.35 (further) |
| My Heart Will Go On | 9 | 1:27 | And you're here in my heart | words 4 -> 6 | -0.73 -> -0.79 (further) | -0.13 -> -0.03 (closer) |
| My Heart Will Go On | 10 | 1:32 | And my heart will go on and on | end 101.56 -> 100.35; source spaced -> aligned | -0.03 -> -0.03 (tie) | +2.26 -> +1.05 (closer) |
| My Heart Will Go On | 12 | 1:52 | And last for a lifetime | 2 word(s) moved > 0.3: a 114.78-116.51 -> 114.76-116.87, lifetime 116.61-117.77 -> 116.97-117.70 | -0.27 -> -0.27 (tie) | +0.64 -> +0.56 (closer) |
| My Heart Will Go On | 14 | 2:07 | Love was when I loved you | start 128.31 -> 127.83 | - (?) | +0.07 -> +0.05 (tie) |
| My Heart Will Go On | 15 | 2:12 | One true time I hold to | end 136.73 -> 137.12 | +0.30 -> +0.30 (tie) | - (?) |
| My Heart Will Go On | 16 | 2:17 | In my life we'll always go on | start 136.73 -> 137.86 | -0.71 -> +0.42 (closer) | +2.64 -> +2.59 (tie) |
| My Heart Will Go On | 17 | 2:28 | Near, far, wherever you are | 1 word(s) moved > 0.3: you 153.16-154.27 -> 153.66-154.27 | - (?) | +0.02 -> +0.02 (tie) |
| My Heart Will Go On | 18 | 2:35 | I believe that the heart does go on | 5 word(s) moved > 0.3: that 157.95-158.78 -> 157.61-158.75, the 159.27-159.44 -> 158.92-159.43, does 160.74-160.84 -> 159.99-160.81, go 161.70-162.06 -> 161.27-163.00; floored words 1 -> 0 | -0.70 -> -0.70 (tie) | - (?) |
| My Heart Will Go On | 19 | 2:46 | Once more you open the door | 6 word(s) moved > 0.3: Once 166.35-167.85 -> 166.64-168.67, more 167.86-169.36 -> 168.77-169.94, you 169.37-170.50 -> 169.94-171.40, open 170.50-172.00 -> 171.59-172.89; source spaced -> re-aligned | - (?) | +0.41 -> +0.33 (closer) |
| My Heart Will Go On | 20 | 2:54 | And you're here in my heart | 2 word(s) moved > 0.3: here 176.31-176.79 -> 176.69-176.81, in 176.89-177.69 -> 176.89-177.99 | -0.92 -> -0.94 (tie) | -0.02 -> -0.06 (tie) |
| My Heart Will Go On | 21 | 3:00 | And my heart will go on and on | 1 word(s) moved > 0.3: and 184.87-186.11 -> 185.60-185.79 | +1.05 -> +1.05 (tie) | +1.87 -> +1.87 (tie) |
| My Heart Will Go On | 22 | 3:25 | You're here, there's nothing I fear | 3 word(s) moved > 0.3: You're 205.80-207.49 -> 205.80-207.85, here, 207.59-209.34 -> 208.36-209.05, nothing 211.19-211.74 -> 211.58-211.76 | -0.03 -> -0.03 (tie) | - (?) |
| My Heart Will Go On | 23 | 3:33 | And I know that my heart will go on | 5 word(s) moved > 0.3: know 214.84-215.34 -> 214.86-215.80, that 215.52-216.76 -> 215.90-216.78, my 216.89-217.90 -> 216.90-217.28, heart 218.00-218.10 -> 217.28-218.12; floored words 1 -> 0 | -1.09 -> -1.09 (tie) | +2.01 -> +1.99 (tie) |
| My Heart Will Go On | 24 | 3:44 | We'll stay forever this way | end 233.12 -> 232.78; source re-aligned -> aligned | -0.46 -> -0.49 (tie) | +0.25 -> -0.10 (closer) |
| My Heart Will Go On | 25 | 3:53 | You are safe in my heart and | 3 word(s) moved > 0.3: safe 234.59-235.21 -> 234.42-235.84, in 235.21-236.17 -> 235.84-236.32, my 236.67-236.83 -> 236.32-236.90 | +0.26 -> +0.28 (tie) | -0.03 -> -0.08 (further) |
| My Heart Will Go On | 26 | 3:58 | My heart will go on and on | end 249.55 -> 248.55; floored words 1 -> 0 | +0.06 -> -0.18 (further) | +5.13 -> +4.13 (closer) |
| She Used To Be Mine | 6 | 0:33 | I'm not anything like I used to be | end 36.09 -> 38.14; floored words 4 -> 0; source aligned -> re-aligned | -0.09 -> -0.01 (closer) | -1.93 -> +0.12 (closer) |
| She Used To Be Mine | 7 | 0:38 | Although it's true | start 36.09 -> 38.14; floored words 1 -> 0; source aligned -> re-aligned | -2.21 -> -0.16 (closer) | +0.01 -> -0.00 (tie) |
| She Used To Be Mine | 29 | 2:24 | Who be reckless just enough | floored words 1 -> 0; source aligned -> re-aligned | - (?) | +0.01 -> +0.10 (further) |

changed lines against PRE: 92; first word vs heard {'closer': 28, 'tie': 32, 'further': 11, '?': 21}; last word vs heard {'closer': 29, 'tie': 40, 'further': 6, '?': 17}

## NOW against MID

| song | L | m:ss | text | what changed | first err base -> NOW (verdict) | last err base -> NOW (verdict) |
|---|---|---|---|---|---|---|
| Stronger | 1 | 0:19 | Oh, yeah, yeah | end 23.55 -> 22.50; floored words 0 -> 1; source spaced -> aligned | - (?) | - (?) |
| Stronger | 5 | 0:37 | I'm not your property as from today, baby | end 43.25 -> 42.92 | +0.30 -> +0.30 (tie) | - (?) |
| Stronger | 6 | 0:42 | You might think that I won't make it on my own | start 43.91 -> 42.92; source aligned -> re-aligned | +1.05 -> +0.06 (closer) | -0.44 -> -0.52 (further) |
| Stronger | 7 | 0:50 | But now I'm stronger than yesterday | 1 word(s) moved > 0.3: yesterday 55.79-55.95 -> 55.14-55.95 | -0.66 -> -0.66 (tie) | -0.00 -> -0.00 (tie) |
| Stronger | 9 | 1:00 | My loneliness ain't killing me no more | end 68.56 -> 66.85 | -0.52 -> -0.52 (tie) | +2.26 -> +0.55 (closer) |
| Stronger | 10 | 1:06 | I, I'm stronger | start 68.66 -> 66.95; source aligned -> re-aligned | +1.42 -> -0.29 (closer) | -0.02 -> -0.04 (tie) |
| Stronger | 16 | 1:35 | 'Cause now I'm stronger than yesterday | 1 word(s) moved > 0.3: yesterday 99.57-100.28 -> 99.14-100.28 | - (?) | -0.12 -> -0.12 (tie) |
| Stronger | 18 | 1:45 | My loneliness ain't killing me no more | end 113.27 -> 111.29; source aligned -> re-aligned | -0.56 -> -0.58 (tie) | +2.11 -> +0.13 (closer) |
| Stronger | 19 | 1:51 | I, I'm stronger | start 113.37 -> 111.39; source aligned -> re-aligned | +0.89 -> -1.09 (further) | +0.79 -> +0.84 (tie) |
| Stronger | 26 | 2:21 | Here I go, here I go, here I go, here I go, here I go | end 146.86 -> 149.65; floored words 4 -> 2; source aligned +guessed words -> re-aligned | - (?) | - (?) |
| Stronger | 32 | 2:55 | I, I'm stronger than yesterday | start 175.16 -> 175.57; floored words 1 -> 0 | -1.00 -> -0.59 (closer) | +2.18 -> +2.18 (tie) |
| Stronger | 34 | 3:06 | My loneliness ain't killing me no more | end 193.47 -> 192.54 | -0.55 -> -0.50 (tie) | +1.49 -> +0.56 (closer) |
| Stronger | 35 | 3:12 | Now I'm stronger than yesterday | start 193.57 -> 192.64; source aligned -> re-aligned | +0.80 -> -0.13 (closer) | +0.15 -> -0.00 (closer) |
| Stronger | 36 | 3:17 | Now it's nothing but my way | 2 word(s) moved > 0.3: my 200.26-201.38 -> 200.26-200.76, way 201.48-201.72 -> 201.11-201.70 | -0.79 -> -0.83 (tie) | - (?) |
| Stronger | 37 | 3:21 | My loneliness ain't killing me no more, no more | end 208.90 -> 209.30; source aligned -> aligned +guessed words | -0.15 -> -0.17 (tie) | +2.10 -> +2.50 (further) |
| Stronger | 38 | 3:29 | I, I'm stronger | start 209.00 -> 209.40 | -0.02 -> +0.38 (further) | +1.57 -> +1.54 (tie) |
| All of Me | 22 | 1:44 | Oh | start 105.70 -> 104.98; end 107.03 -> 106.09; source spaced -> re-aligned | - (?) | - (?) |
| All of Me | 29 | 2:11 | I can't stop singing, it's ringing in my head for you | 5 word(s) moved > 0.3: singing, 133.13-133.72 -> 133.13-134.18, it's 133.90-134.43 -> 134.28-134.42, ringing 134.43-134.95 -> 134.84-135.54, in 135.01-135.99 -> 135.54-136.22; source aligned -> re-aligned | +0.32 -> +0.30 (tie) | +0.85 -> +0.85 (tie) |
| All of Me | 39 | 2:59 | Even when I lose I'm winning | 2 word(s) moved > 0.3: Even 179.55-180.69 -> 179.55-180.00, when 180.79-180.90 -> 180.34-180.90 | -0.03 -> -0.03 (tie) | +0.00 -> +0.00 (tie) |
| All of Me | 40 | 3:03 | 'Cause I give you all of me | start 182.30 -> 183.07 | -0.83 -> -0.06 (closer) | +0.58 -> +0.56 (tie) |
| All of Me | 44 | 3:21 | Cards on the table, we're both showing hearts | 1 word(s) moved > 0.3: table, 203.46-204.24 -> 203.52-204.69 | +0.25 -> +0.25 (tie) | -0.30 -> -0.30 (tie) |
| All of Me | 45 | 3:29 | Risking it all, though it's hard | 2 word(s) moved > 0.3: it's 212.32-212.79 -> 212.63-212.79, hard 213.20-213.88 -> 212.79-213.87 | +0.20 -> -0.07 (closer) | +0.35 -> +0.35 (tie) |
| All of Me | 46 | 3:34 | 'Cause all of me loves all of you | 2 word(s) moved > 0.3: all 214.80-215.88 -> 214.83-216.21, loves 216.88-218.30 -> 218.13-218.29; source aligned -> re-aligned | +0.75 -> +0.75 (tie) | +0.13 -> -0.13 (tie) |
| All of Me | 47 | 3:40 | Love your curves and all your edges | start 221.65 -> 220.57; floored words 1 -> 0; source aligned -> re-aligned | +0.53 -> -0.55 (tie) | +0.06 -> +0.07 (tie) |
| All of Me | 49 | 3:49 | Give your all to me, I'll give my all to you | 3 word(s) moved > 0.3: my 233.21-233.77 -> 233.35-234.46, all 234.09-234.63 -> 234.56-235.35, to 234.97-235.53 -> 235.45-235.56; source aligned -> re-aligned | -0.04 -> +0.01 (tie) | +0.18 -> +0.18 (tie) |
| All of Me | 50 | 3:56 | You're my end and my beginning | 1 word(s) moved > 0.3: my 237.33-237.45 -> 236.99-237.47 | +0.37 -> +0.39 (tie) | -0.01 -> +0.01 (tie) |
| All of Me | 51 | 4:00 | Even when I lose, I'm winning | 1 word(s) moved > 0.3: Even 240.77-241.60 -> 240.47-241.60 | +0.26 -> -0.04 (closer) | +0.03 -> +0.05 (tie) |
| All of Me | 52 | 4:04 | 'Cause I give you all of me | 2 word(s) moved > 0.3: you 244.80-245.59 -> 244.80-245.04, me 249.19-249.83 -> 248.88-249.84 | - (?) | +0.41 -> +0.41 (tie) |
| All of Me | 55 | 4:26 | And you give me all of you, oh | 2 word(s) moved > 0.3: all 267.87-269.38 -> 267.85-270.09, of 269.48-270.98 -> 270.19-271.69; source aligned -> re-aligned | -0.08 -> -0.08 (tie) | +1.45 -> +1.45 (tie) |
| Someone Like You | 0 | 0:14 | I heard that you're settled down | end 21.43 -> 20.35 | -0.13 -> -0.07 (closer) | +0.57 -> -0.51 (closer) |
| Someone Like You | 1 | 0:20 | That you found a girl | start 21.53 -> 20.59; floored words 1 -> 0; source aligned -> re-aligned | +0.67 -> -0.27 (closer) | +0.09 -> -0.08 (tie) |
| Someone Like You | 2 | 0:24 | And you're married now | end 28.14 -> 28.98 | - (?) | +0.66 -> +1.50 (further) |
| Someone Like You | 3 | 0:29 | I heard that your dreams came true | start 28.24 -> 29.08 | - (?) | -0.07 -> -0.03 (tie) |
| Someone Like You | 6 | 0:43 | Old friend, why are you so shy | 2 word(s) moved > 0.3: Old 43.07-44.22 -> 43.07-44.54, friend, 44.32-45.49 -> 44.64-45.71 | -0.06 -> -0.06 (tie) | +0.74 -> +0.77 (tie) |
| Someone Like You | 16 | 1:19 | I wish nothing but the best for you, too | 5 word(s) moved > 0.3: but 81.32-81.80 -> 81.66-81.82, the 81.80-82.78 -> 81.82-82.16, best 82.88-83.30 -> 82.57-83.24, for 83.30-84.63 -> 83.24-84.14; floored words 0 -> 1; source aligned -> re-aligned | -0.03 -> +0.08 (tie) | +0.03 -> +0.15 (further) |
| Someone Like You | 24 | 1:57 | Only yesterday was the time of our lives | end 124.21 -> 123.76 | -0.19 -> -0.21 (tie) | +0.07 -> -0.38 (further) |
| Someone Like You | 25 | 2:03 | We were born and raised in a summer haze | end 131.40 -> 130.88 | -0.30 -> -0.30 (tie) | +0.60 -> +0.08 (closer) |
| Someone Like You | 32 | 2:37 | Never mind, I'll find someone like you | start 157.75 -> 157.24; end 161.85 -> 163.09; floored words 1 -> 0; source aligned -> re-aligned | +1.84 -> +1.33 (closer) | +0.01 -> +1.25 (further) |
| Someone Like You | 33 | 2:43 | I wish nothing but the best for you, too | start 161.85 -> 163.19; end 170.78 -> 169.84; source aligned -> re-aligned | -1.07 -> +0.27 (closer) | +0.78 -> -0.16 (closer) |
| Someone Like You | 34 | 2:49 | Don't forget me, I begged | start 170.88 -> 169.99; floored words 1 -> 0; source aligned -> re-aligned | +0.25 -> -0.64 (further) | - (?) |
| Someone Like You | 37 | 3:00 | But sometimes it hurts instead | 1 word(s) moved > 0.3: hurts 181.75-181.92 -> 181.42-181.92 | -0.06 -> -0.06 (tie) | +0.56 -> +0.51 (closer) |
| Someone Like You | 38 | 3:03 | Nothing compares, no worries or cares | floored words 0 -> 1 | - (?) | -0.00 -> +0.16 (further) |
| Someone Like You | 39 | 3:09 | Regrets and mistakes, they're memories made | 1 word(s) moved > 0.3: mistakes, 190.20-190.79 -> 189.87-190.81 | -0.13 -> -0.06 (closer) | +0.02 -> +0.02 (tie) |
| Someone Like You | 40 | 3:12 | Who would have known | 1 word(s) moved > 0.3: known 193.97-194.07 -> 193.67-194.05; floored words 1 -> 0 | +0.17 -> +0.17 (tie) | -0.00 -> -0.02 (tie) |
| Someone Like You | 41 | 3:14 | How bittersweet this would taste | end 201.55 -> 199.68 | -0.00 -> -0.02 (tie) | +0.37 -> -1.50 (further) |
| Someone Like You | 42 | 3:24 | Never mind, I'll find someone like you | start 204.70 -> 204.37; floored words 2 -> 0; source aligned -> re-aligned | +0.28 -> -0.05 (closer) | +0.08 -> +0.26 (further) |
| Someone Like You | 43 | 3:28 | I wish nothing but the best for you | 4 word(s) moved > 0.3: I 208.45-210.57 -> 208.73-210.23, but 212.06-212.22 -> 211.75-212.22, for 214.18-214.38 -> 213.62-214.89, you 214.38-217.10 -> 214.99-217.12 | - (?) | +1.66 -> +1.68 (tie) |
| Someone Like You | 46 | 3:44 | Sometimes it lasts in love | start 225.14 -> 224.56; floored words 1 -> 0; source aligned -> re-aligned | +0.53 -> -0.05 (closer) | +0.04 -> +0.22 (further) |
| Someone Like You | 47 | 3:46 | But sometimes it hurts instead | end 230.62 -> 231.60 | -0.09 -> -0.09 (tie) | +1.16 -> +2.14 (further) |
| Someone Like You | 48 | 3:52 | Never mind, I'll find someone like you | start 230.72 -> 232.65 | -2.05 -> -0.12 (closer) | +0.79 -> +1.03 (further) |
| Someone Like You | 49 | 3:58 | I wish nothing but the best for you, too | end 242.01 -> 245.05; floored words 2 -> 1; source aligned +guessed words -> re-aligned | -0.11 -> +0.13 (tie) | -3.27 -> -0.23 (closer) |
| Someone Like You | 50 | 4:05 | Don't forget me, I begged | start 246.18 -> 245.14; source aligned -> re-aligned | +0.22 -> -0.82 (further) | - (?) |
| Someone Like You | 52 | 4:13 | Sometimes it lasts in love | floored words 1 -> 0 | +0.08 -> +0.08 (tie) | +0.04 -> +0.04 (tie) |
| Baby One More Time | 2 | 0:28 | Oh baby, baby, how was I supposed to know | 3 word(s) moved > 0.3: baby, 29.39-29.94 -> 28.94-29.66, supposed 31.73-32.25 -> 31.76-32.66, to 32.58-33.13 -> 33.05-33.17; source aligned -> re-aligned | +0.63 -> +0.63 (tie) | +0.19 -> +0.19 (tie) |
| Baby One More Time | 3 | 0:35 | That something wasn't right here | floored words 1 -> 0; source aligned -> re-aligned | +0.23 -> -0.02 (closer) | +0.01 -> +0.02 (tie) |
| Baby One More Time | 4 | 0:38 | Oh baby, baby, I shouldn't have let you go | 2 word(s) moved > 0.3: baby, 40.09-41.05 -> 40.41-41.05, shouldn't 41.15-41.93 -> 41.45-41.95 | -0.23 -> -0.23 (tie) | +1.44 -> +1.54 (further) |
| Baby One More Time | 5 | 0:46 | And now you're out of sight, yeah | start 45.60 -> 46.05 | +0.45 -> +0.90 (further) | -0.00 -> -0.00 (tie) |
| Baby One More Time | 6 | 0:48 | Show me how you want it to be | 1 word(s) moved > 0.3: Show 48.71-49.66 -> 48.71-49.29 | -0.12 -> -0.12 (tie) | +0.36 -> +0.36 (tie) |
| Baby One More Time | 19 | 1:40 | Show me how you want it to be | 1 word(s) moved > 0.3: be 104.09-104.54 -> 104.08-104.24; floored words 1 -> 0 | -0.25 -> -0.21 (tie) | +0.23 -> -0.07 (closer) |
| Baby One More Time | 20 | 1:44 | Tell me, baby, 'cause I need to know now, oh because | start 105.26 -> 104.44; floored words 1 -> 0; source aligned -> re-aligned | +0.08 -> -0.74 (further) | +0.22 -> +0.22 (tie) |
| Baby One More Time | 26 | 2:11 | Oh baby, baby | end 136.28 -> 136.59 | - (?) | - (?) |
| Baby One More Time | 27 | 2:16 | Oh baby, baby | start 136.28 -> 136.69; end 138.62 -> 140.38; floored words 1 -> 0; source aligned -> re-aligned | -4.89 -> -4.48 (closer) | - (?) |
| Baby One More Time | 28 | 2:22 | Oh baby, baby, how was I supposed to know | 1 word(s) moved > 0.3: supposed 145.67-146.25 -> 145.31-146.20 | - (?) | +0.14 -> +0.17 (tie) |
| Baby One More Time | 29 | 2:32 | Oh pretty baby, I shouldn't have let you go | 1 word(s) moved > 0.3: I 154.24-154.66 -> 154.68-154.78; floored words 0 -> 1 | +0.87 -> +0.87 (tie) | +2.99 -> +2.99 (tie) |
| Baby One More Time | 30 | 2:41 | I must confess, that my loneliness is killing me now | start 161.55 -> 161.10; floored words 1 -> 0; source aligned -> re-aligned | - (?) | +1.28 -> +1.30 (tie) |
| Baby One More Time | 42 | 3:30 | Don't you know I still believe | 1 word(s) moved > 0.3: believe 213.37-214.55 -> 213.79-214.55 | - (?) | +0.31 -> +0.31 (tie) |
| Miss Independent | 1 | 0:07 | Morning. Good morning, ne-yo. | end 8.92 -> 9.70 | +0.56 -> +0.56 (tie) | - (?) |
| Miss Independent | 2 | 0:09 | Good morning. | start 9.02 -> 9.80; end 10.28 -> 11.83; source aligned -> re-aligned | -1.66 -> -0.88 (closer) | -1.28 -> +0.27 (closer) |
| Miss Independent | 3 | 0:11 | Looking good. | 1 word(s) moved > 0.3: good. 12.29-12.79 -> 11.92-12.64; source aligned -> re-aligned | -0.00 -> -0.07 (further) | +0.46 -> +0.41 (tie) |
| Miss Independent | 9 | 0:23 | Good morning. God damn. | end 26.45 -> 25.92; floored words 0 -> 1 | - (?) | - (?) |
| Miss Independent | 11 | 0:39 | Ooh yeah, ooh yeah | 3 word(s) moved > 0.3: Ooh 39.29-40.03 -> 39.38-39.48, yeah, 40.03-40.13 -> 39.48-40.18, ooh 42.25-42.39 -> 41.07-42.18; source aligned -> re-aligned | - (?) | - (?) |
| Miss Independent | 12 | 0:42 | Ooh yeah, ooh yeah, ooh | start 43.18 -> 42.70; end 47.91 -> 46.38; source spaced -> re-aligned | - (?) | - (?) |
| Miss Independent | 24 | 1:21 | And she move like a boss, do what a boss do | floored words 2 -> 0; source aligned -> re-aligned | +0.91 -> +0.77 (closer) | +0.04 -> +0.02 (tie) |
| Miss Independent | 38 | 1:58 | Ooh yeah, ooh yeah | end 120.79 -> 121.95; floored words 3 -> 0 | - (?) | - (?) |
| Miss Independent | 48 | 2:26 | Cause she work like a boss, play like a boss | 1 word(s) moved > 0.3: like 150.26-150.70 -> 150.60-150.71 | -0.94 -> -0.94 (tie) | +0.08 -> +0.08 (tie) |
| Miss Independent | 50 | 2:35 | And her bills are paid on time | end 157.70 -> 158.62 | +0.04 -> +0.04 (tie) | +0.10 -> +1.03 (further) |
| Miss Independent | 51 | 2:39 | She made for a boss, only a boss | start 157.70 -> 159.47 | -0.90 -> +0.87 (tie) | +0.44 -> +0.44 (tie) |
| Miss Independent | 58 | 3:01 | She got her own thing | 2 word(s) moved > 0.3: own 182.64-182.76 -> 182.24-182.70, thing 183.26-183.42 -> 182.70-183.38; floored words 1 -> 0; source aligned -> re-aligned | +0.22 -> -0.06 (closer) | +0.00 -> +0.05 (tie) |
| Miss Independent | 62 | 3:11 | Miss independent | end 193.54 -> 192.44 | - (?) | - (?) |
| Miss Independent | 63 | 3:12 | Mmm | start 193.64 -> 192.54; end 194.54 -> 193.88 | - (?) | - (?) |
| Miss Independent | 64 | 3:14 | Her favorite thing to say-- "don't worry, I've got it" | start 194.54 -> 194.97; end 199.27 -> 199.62 | - (?) | +0.37 -> +0.72 (further) |
| Miss Independent | 65 | 3:20 | Mmm | start 198.78 -> 200.52; end 200.28 -> 200.58; floored words 0 -> 1; source spaced -> aligned | - (?) | - (?) |
| Miss Independent | 71 | 3:36 | Ooh yeah, ooh yeah | 1 word(s) moved > 0.3: ooh 218.82-218.95 -> 218.40-218.74 | - (?) | - (?) |
| Miss Independent | 78 | 3:57 | She got her own thing, she got, she got | 1 word(s) moved > 0.3: got 239.81-240.40 -> 240.12-240.23; floored words 4 -> 2 | - (?) | - (?) |
| Miss Independent | 81 | 4:04 | Ooh, the way you shine | 3 word(s) moved > 0.3: Ooh, 244.20-245.30 -> 244.20-244.92, the 245.56-245.66 -> 244.92-245.20, way 245.66-245.80 -> 245.20-245.54; floored words 1 -> 0; source aligned -> re-aligned | - (?) | -0.10 -> +0.03 (closer) |
| Miss Independent | 86 | 4:22 | It's okay. You are the boss. | floored words 0 -> 1 | -0.02 -> +0.02 (tie) | -0.14 -> -0.12 (tie) |
| Pocahontas | 7 | 0:33 | You think you own whatever land you land on | floored words 1 -> 0 | -0.05 -> -0.04 (tie) | -0.02 -> -0.02 (tie) |
| Pocahontas | 9 | 0:43 | But I know every rock and tree and creature | floored words 1 -> 0; source aligned -> re-aligned | +0.19 -> +0.01 (closer) | +0.01 -> -0.01 (tie) |
| Pocahontas | 19 | 1:28 | Can you paint with all the colors of the wind | start 89.27 -> 88.93; end 103.24 -> 95.80; floored words 2 -> 0; source aligned -> re-aligned | +0.83 -> +0.49 (closer) | +8.48 -> +1.04 (closer) |
| Pocahontas | 20 | 1:43 | Come run the hidden pine trails of the forest | floored words 1 -> 0; source aligned -> re-aligned | +0.10 -> -0.07 (tie) | -0.02 -> -0.03 (tie) |
| Pocahontas | 23 | 1:55 | And for once, never wonder what they're worth | floored words 1 -> 0; source aligned -> re-aligned | +0.49 -> +0.40 (closer) | - (?) |
| Pocahontas | 27 | 2:12 | In a circle, in a hoop that never ends | 4 word(s) moved > 0.3: circle, 133.73-133.85 -> 133.25-133.97, in 134.31-134.41 -> 133.97-134.21, never 135.63-136.19 -> 135.19-135.53, ends 136.29-137.20 -> 135.53-136.91; floored words 2 -> 0; source aligned -> re-aligned | +0.69 -> +0.46 (closer) | +0.58 -> +0.48 (closer) |
| Pocahontas | 33 | 2:42 | We need to paint with all the colors of the wind | floored words 1 -> 0; source aligned -> re-aligned | - (?) | +0.41 -> +0.31 (closer) |
| Pocahontas | 36 | 2:54 | You can paint with all the colors of the wind | end 183.95 -> 190.20; source aligned -> re-aligned | - (?) | -0.97 -> +5.28 (further) |
| Incomplete | 0 | 0:17 | Empty spaces fill me up with holes | 1 word(s) moved > 0.3: fill 21.32-21.87 -> 20.97-21.85 | +1.09 -> +1.09 (tie) | +0.20 -> +0.33 (further) |
| Incomplete | 1 | 0:25 | Distant faces with no place left to go | 2 word(s) moved > 0.3: place 29.51-30.50 -> 29.35-30.09, left 30.60-30.80 -> 30.28-30.85 | -0.01 -> -0.00 (tie) | -0.08 -> +0.00 (closer) |
| Incomplete | 2 | 0:31 | Without you, within me I can find no rest | start 32.62 -> 31.95; floored words 1 -> 0; source aligned -> re-aligned | +0.76 -> +0.09 (closer) | +0.44 -> +0.46 (tie) |
| Incomplete | 3 | 0:39 | Where I'm going is anybody's guess | source aligned -> re-aligned | +0.48 -> +0.42 (closer) | +1.16 -> +1.16 (tie) |
| Incomplete | 4 | 0:50 | I tried to go on like I never knew you | 1 word(s) moved > 0.3: tried 50.63-51.97 -> 50.94-51.93 | +0.33 -> +0.33 (tie) | +0.09 -> +0.20 (further) |
| Incomplete | 6 | 1:04 | I pray for this heart to be unbroken | 1 word(s) moved > 0.3: for 66.35-67.26 -> 66.96-67.15; floored words 1 -> 0; source aligned -> re-aligned | +1.43 -> +1.17 (closer) | +0.06 -> +0.05 (tie) |
| Incomplete | 8 | 1:33 | Voices tell me I should carry on | 3 word(s) moved > 0.3: Voices 93.31-94.57 -> 93.41-94.10, tell 95.01-95.18 -> 94.50-95.16, me 95.66-95.82 -> 95.34-95.88 | +0.29 -> +0.39 (further) | +0.27 -> +0.27 (tie) |
| Incomplete | 9 | 1:40 | But I am swimming in an ocean all alone | 1 word(s) moved > 0.3: swimming 102.40-103.53 -> 101.96-103.49 | +0.58 -> +0.58 (tie) | +0.89 -> +0.89 (tie) |
| Incomplete | 18 | 2:38 | But I can't seem to let you go | 1 word(s) moved > 0.3: go 160.49-161.29 -> 160.17-161.29 | - (?) | +0.56 -> +0.56 (tie) |
| Incomplete | 19 | 2:42 | I don't wanna make you face this world alone | 2 word(s) moved > 0.3: face 163.99-164.59 -> 163.97-165.19, this 164.90-165.41 -> 165.29-165.39 | - (?) | +3.63 -> +3.61 (tie) |
| Castle On The Hill | 2 | 0:38 | And tasted the sweet perfume | 2 word(s) moved > 0.3: sweet 40.14-40.96 -> 40.06-40.40, perfume 41.06-41.26 -> 40.71-41.22; floored words 1 -> 0; source aligned -> re-aligned | +0.16 -> -0.00 (closer) | +0.01 -> +0.06 (tie) |
| Castle On The Hill | 10 | 1:06 | But I can't wait to go home | start 66.59 -> 66.97; source aligned -> re-aligned | -1.09 -> -0.71 (closer) | +0.07 -> +0.06 (tie) |
| Castle On The Hill | 23 | 2:07 | Take me back to when | source aligned -> re-aligned | +0.02 -> -0.02 (tie) | +0.01 -> +0.02 (tie) |
| Castle On The Hill | 24 | 2:09 | We found weekend jobs, and when we got paid | 1 word(s) moved > 0.3: jobs, 132.40-132.90 -> 132.10-132.94 | +0.01 -> +0.01 (tie) | -0.01 -> +0.01 (tie) |
| Castle On The Hill | 30 | 2:32 | Driving at 90 down those country lanes | start 153.04 -> 152.15; floored words 1 -> 0; source aligned -> re-aligned | +0.64 -> -0.25 (closer) | +0.16 -> +0.18 (tie) |
| Castle On The Hill | 31 | 2:38 | Singing to "Tiny Dancer" | end 162.88 -> 162.42 | -0.43 -> -0.43 (tie) | +0.42 -> -0.04 (closer) |
| Castle On The Hill | 32 | 2:42 | And I miss the way you make me feel | start 162.98 -> 162.42; floored words 1 -> 0; source aligned -> re-aligned | +0.52 -> -0.04 (closer) | +0.04 -> -0.02 (tie) |
| Castle On The Hill | 52 | 4:15 | Hoo-ooh | end 256.74 -> 258.59 | - (?) | - (?) |
| Castle On The Hill | 53 | 4:18 | Over the castle on the hill | start 256.74 -> 258.69; source aligned -> re-aligned | - (?) | +0.04 -> -0.00 (tie) |
| Castle On The Hill | 55 | 4:23 | Over the castle on the hill | 2 word(s) moved > 0.3: the 266.86-267.98 -> 267.37-267.54, castle 268.08-268.26 -> 267.72-268.26 | -0.55 -> -0.49 (closer) | +0.00 -> +0.00 (tie) |
| My Heart Will Go On | 0 | 0:22 | Every night in my dreams | start 21.40 -> 22.17 | +0.65 -> +1.42 (further) | +0.44 -> +0.41 (tie) |
| My Heart Will Go On | 1 | 0:25 | I see you, I feel you | 1 word(s) moved > 0.3: feel 28.60-29.11 -> 29.01-29.11; floored words 0 -> 1 | -1.94 -> -1.72 (closer) | +0.13 -> +0.13 (tie) |
| My Heart Will Go On | 2 | 0:31 | That is how I know you go on | 2 word(s) moved > 0.3: know 33.26-34.41 -> 33.26-33.72, you 34.51-34.62 -> 34.06-34.62 | +0.36 -> +0.36 (tie) | +1.63 -> +1.63 (tie) |
| My Heart Will Go On | 3 | 0:40 | Far across the distance | 3 word(s) moved > 0.3: Far 40.37-41.07 -> 40.50-41.40, across 41.07-42.47 -> 41.40-42.28, the 42.47-43.17 -> 42.42-42.84; source spaced -> re-aligned | - (?) | +0.69 -> +0.57 (closer) |
| My Heart Will Go On | 5 | 0:50 | You have come to show you go on | 1 word(s) moved > 0.3: show 52.61-53.05 -> 52.92-53.55 | +0.57 -> +0.57 (tie) | +0.92 -> +0.92 (tie) |
| My Heart Will Go On | 8 | 1:19 | Once more, you open the door | 3 word(s) moved > 0.3: you 83.79-84.62 -> 83.78-85.02, open 84.72-85.64 -> 85.12-86.09, the 85.82-86.36 -> 86.19-86.36 | - (?) | -0.25 -> -0.35 (further) |
| My Heart Will Go On | 10 | 1:32 | And my heart will go on and on | 2 word(s) moved > 0.3: will 94.66-95.08 -> 94.66-95.91, go 95.24-96.34 -> 96.01-96.32 | -0.01 -> -0.03 (tie) | +1.05 -> +1.05 (tie) |
| My Heart Will Go On | 12 | 1:52 | And last for a lifetime | 2 word(s) moved > 0.3: a 114.78-116.51 -> 114.76-116.87, lifetime 116.61-117.70 -> 116.97-117.70 | -0.27 -> -0.27 (tie) | +0.56 -> +0.56 (tie) |
| My Heart Will Go On | 17 | 2:28 | Near, far, wherever you are | 1 word(s) moved > 0.3: Near, 148.55-149.31 -> 148.25-149.33 | - (?) | +0.02 -> +0.02 (tie) |
| My Heart Will Go On | 18 | 2:35 | I believe that the heart does go on | 2 word(s) moved > 0.3: go 161.75-162.06 -> 161.27-163.00, on 162.06-165.43 -> 163.10-165.47 | -0.70 -> -0.70 (tie) | - (?) |
| My Heart Will Go On | 19 | 2:46 | Once more you open the door | 6 word(s) moved > 0.3: Once 166.64-167.65 -> 166.64-168.67, more 167.66-169.16 -> 168.77-169.94, you 169.17-170.30 -> 169.94-171.40, open 170.30-171.80 -> 171.59-172.89; source spaced -> re-aligned | - (?) | +0.23 -> +0.33 (further) |
| My Heart Will Go On | 20 | 2:54 | And you're here in my heart | 1 word(s) moved > 0.3: here 176.31-176.81 -> 176.69-176.81 | -0.92 -> -0.94 (tie) | -0.06 -> -0.06 (tie) |
| My Heart Will Go On | 21 | 3:00 | And my heart will go on and on | 2 word(s) moved > 0.3: heart 181.35-181.78 -> 181.65-181.80, and 185.04-185.78 -> 185.60-185.79 | +1.05 -> +1.05 (tie) | +1.85 -> +1.87 (tie) |
| My Heart Will Go On | 22 | 3:25 | You're here, there's nothing I fear | 4 word(s) moved > 0.3: You're 205.80-207.49 -> 205.80-207.85, here, 207.59-209.05 -> 208.36-209.05, there's 210.12-210.28 -> 209.46-210.28, nothing 211.24-211.82 -> 211.58-211.76 | -0.03 -> -0.03 (tie) | - (?) |
| My Heart Will Go On | 24 | 3:44 | We'll stay forever this way | 1 word(s) moved > 0.3: this 230.91-231.83 -> 231.66-231.85 | -0.49 -> -0.49 (tie) | -0.08 -> -0.10 (tie) |
| My Heart Will Go On | 25 | 3:53 | You are safe in my heart and | 4 word(s) moved > 0.3: safe 234.41-235.41 -> 234.42-235.84, in 235.41-235.91 -> 235.84-236.32, my 235.91-236.41 -> 236.32-236.90, heart 236.41-237.66 -> 236.90-237.70; source spaced -> re-aligned | +0.19 -> +0.28 (further) | +0.09 -> -0.08 (tie) |
| My Heart Will Go On | 26 | 3:58 | My heart will go on and on | end 249.83 -> 248.55; source spaced -> re-aligned | -0.03 -> -0.18 (further) | +5.41 -> +4.13 (closer) |
| She Used To Be Mine | 6 | 0:33 | I'm not anything like I used to be | end 36.09 -> 38.14; floored words 4 -> 0; source aligned -> re-aligned | -0.09 -> -0.01 (closer) | -1.93 -> +0.12 (closer) |
| She Used To Be Mine | 7 | 0:38 | Although it's true | start 36.09 -> 38.14; floored words 1 -> 0; source aligned -> re-aligned | -2.21 -> -0.16 (closer) | +0.01 -> -0.00 (tie) |
| She Used To Be Mine | 29 | 2:24 | Who be reckless just enough | floored words 1 -> 0; source aligned -> re-aligned | - (?) | +0.01 -> +0.10 (further) |

changed lines against MID: 134; first word vs heard {'closer': 35, 'tie': 53, 'further': 11, '?': 35}; last word vs heard {'closer': 20, 'tie': 70, 'further': 21, '?': 23}

**R55r lines NOW ends further from the transcriber than PRE** (`regress.py`, verbatim).

```

Stronger L18 1:45 My loneliness ain't killing me no more  (first further, last closer; source aligned -> re-aligned)
  prev NOW line 17: 100.28-105.04; next 19: 111.39-116.70
  PRE: My[105.36-105.9] loneliness[106.28-106.92] ain't[106.92-108.42] killing[108.64-109.11] me[109.21-109.52] no[109.64-110.02] more[110.17-113.28]
  MID: My[105.05-105.91] loneliness[106.3-106.95] ain't[107.35-108.01] killing[108.01-109.1] me[109.2-109.51] no[109.64-110.05] more[110.05-113.26]
  NOW: My[105.03-105.45] loneliness[105.77-106.91] ain't[107.33-108.03] killing[108.03-109.3] me[109.4-109.51] no[109.67-110.01] more[110.01-111.28]
  heard: away[104.28-105.08] My[105.62-106.08] loneliness[106.08-106.92] ain't[106.92-107.98] killing[107.98-108.68] me[108.68-109.54] no[109.54-110.06] more[110.06-111.16]
  cue span (offset-shifted, as used): 105.30-110.30

Stronger L19 1:51 I, I'm stronger  (first further, last tie; source aligned -> re-aligned)
  prev NOW line 18: 105.04-111.29; next 20: 118.55-119.47
  PRE: I,[113.37-114.57] I'm[114.99-115.71] stronger[115.86-116.65]
  MID: I,[113.37-114.57] I'm[114.99-115.71] stronger[115.86-116.65]
  NOW: I,[111.38-112.38] I'm[114.45-114.85] stronger[114.85-116.69]
  heard: I[112.48-113.20] am[113.20-114.32] stronger[114.32-115.86] Oh,[116.58-116.80]
  cue span (offset-shifted, as used): 112.48-117.48

Stronger L32 2:55 I, I'm stronger than yesterday  (first further, last tie; source aligned -> re-aligned)
  prev NOW line 31: 169.82-175.56; next 33: 182.66-186.21
  PRE: I,[176.56-177.26] I'm[177.36-178.1] stronger[178.1-178.98] than[178.98-182.56]
  MID: I,[175.16-177.9] I'm[178.24-178.34] stronger[178.34-179.4] than[179.4-180.26] yesterday[180.26-182.56]
  NOW: I,[175.57-177.74] I'm[177.84-178.26] stronger[179.18-179.91] than[180.01-180.26] yesterday[180.26-182.56]
  heard: I[176.16-176.66] ain't[176.86-177.18] stronger[177.18-178.70] than[178.70-180.22] yesterday[180.22-180.38] Now[182.78-183.04]
  cue span (offset-shifted, as used): 175.79-180.79

Someone Like You L32 2:37 Never mind, I'll find someone like you  (first closer, last further; source aligned -> re-aligned)
  prev NOW line 31: 149.56-154.73; next 33: 163.19-169.84
  PRE: Never[157.75-157.85] mind,[158.04-158.61] I'll[158.77-158.87] find[158.94-159.57] someone[160.09-160.4] like[160.7-161.2] you[161.38-161.92]
  MID: Never[157.75-157.85] mind,[158.04-158.61] I'll[158.75-158.87] find[158.94-159.55] someone[160.2-160.41] like[160.71-161.21] you[161.4-161.96]
  NOW: Never[157.24-157.76] mind,[158.17-158.3] I'll[158.64-158.8] find[158.8-159.48] someone[159.48-160.3] like[160.61-161.12] you[161.22-163.09]
  heard: mind,[157.76-158.28] I'll[158.28-158.78] find[158.78-159.42] someone[159.42-160.30] like[160.30-161.10] you[161.10-161.84] I[162.92-163.84]
  cue span (offset-shifted, as used): 157.86-162.86

Someone Like You L34 2:49 Don't forget me, I begged  (first further, last ?; source aligned -> re-aligned)
  prev NOW line 33: 163.19-169.84; next 35: 174.05-177.63
  PRE: Don't[170.91-171.01] forget[171.46-171.61] me,[171.61-172.51] I[173.01-173.11] begged[173.12-173.79]
  MID: Don't[170.87-170.99] forget[171.46-171.62] me,[171.62-172.5] I[173.02-173.12] begged[173.13-173.8]
  NOW: Don't[169.98-171.02] forget[171.16-171.58] me,[171.58-172.6] I[172.8-173.02] begged[173.02-173.62]
  heard: Don't[170.62-171.00] forget[171.00-171.60] me,[171.60-172.13] I[172.54-172.98] beg,[172.98-173.15] I'll[174.10-174.70]
  cue span (offset-shifted, as used): 170.87-174.43

Someone Like You L46 3:44 Sometimes it lasts in love  (first closer, last further; source aligned -> re-aligned)
  prev NOW line 45: 220.96-224.06; next 47: 226.99-231.60
  PRE: Sometimes[225.23-225.33] it[225.33-225.47] lasts[225.47-226.13] in[226.28-226.41] love[226.41-226.85]
  MID: Sometimes[225.13-225.23] it[225.23-225.49] lasts[225.49-226.13] in[226.28-226.41] love[226.41-226.85]
  NOW: Sometimes[224.55-224.92] it[224.92-225.32] lasts[225.32-226.02] in[226.15-226.3] love[226.3-226.94]
  heard: Sometimes[224.61-225.02] it[225.02-225.42] lasts[225.42-226.04] in[226.24-226.38] love[226.38-226.72] But[227.08-227.24] sometimes[227.24-227.66]
  cue span (offset-shifted, as used): 224.82-227.33

Someone Like You L49 3:58 I wish nothing but the best for you, too  (first further, last closer; source aligned -> re-aligned)
  prev NOW line 48: 232.65-237.91; next 50: 245.14-249.05
  PRE: I[237.85-239.12] wish[239.12-239.5] nothing[240.02-240.12] but[240.43-240.64] the[240.75-241.08] best[241.46-242.08] for[242.39-243.53] you,[243.63-245.74]
  MID: I[237.77-239.12] wish[239.12-239.5] nothing[239.98-240.08] but[240.4-240.7] the[240.7-240.8] best[240.8-241.1] for[241.1-241.4] you,[241.4-241.7] too[241.7-242.0]
  NOW: I[238.0-239.13] wish[239.41-239.51] nothing[239.65-240.07] but[240.52-240.67] the[240.67-241.09] best[241.46-242.07] for[242.57-242.93] you,[243.39-243.54] too[243.99-245.05]
  heard: I[237.88-239.12] wish[239.40-239.50] nothing[239.52-240.06] but[240.06-240.70] the[240.70-241.10] best[241.10-242.06] for[242.06-243.02] you[243.02-243.84] too[243.84-245.28]
  cue span (offset-shifted, as used): 239.02-244.02

Someone Like You L50 4:05 Don't forget me, I begged  (first further, last ?; source aligned -> re-aligned)
  prev NOW line 49: 238.01-245.05; next 51: 249.40-252.94
  PRE: Don't[246.19-246.39] forget[246.8-246.91] me,[246.91-247.83] I[248.33-248.43] begged[248.43-249.13]
  MID: Don't[246.17-246.37] forget[246.8-246.91] me,[246.91-247.85] I[248.33-248.43] begged[248.43-249.13]
  NOW: Don't[245.13-246.38] forget[246.74-246.84] me,[247.2-247.79] I[248.16-248.34] begged[248.34-249.04]
  heard: Don't[245.96-246.32] forget[246.32-246.92] me,[246.92-247.46] I[247.80-248.34] think,[248.34-248.82] I[249.36-249.72]
  cue span (offset-shifted, as used): 246.15-249.68

Baby One More Time L20 1:44 Tell me, baby, 'cause I need to know now, oh because  (first further, last tie; source aligned -> re-aligned)
  prev NOW line 19: 100.37-104.23; next 21: 110.95-114.73
  PRE: Tell[105.24-105.38] me,[105.71-105.82] baby,[106.06-106.84] 'cause[107.08-107.46] I[107.46-107.64] need[107.64-108.0] to[108.0-108.26] know[108.26-108.82] now,[109.18-110.85]
  MID: Tell[105.26-105.41] me,[105.72-106.41] baby,[106.51-107.35] 'cause[107.35-107.47] I[107.47-107.65] need[107.65-108.01] to[108.01-108.27] know[108.27-108.85] now,[108.85-109.75] oh[109.93-110.03] because[110.03-110.95]
  NOW: Tell[104.43-105.29] me,[105.42-105.81] baby,[106.07-107.13] 'cause[107.13-107.47] I[107.47-107.65] need[107.75-108.05] to[108.05-108.27] know[108.27-108.83] now,[108.83-109.83] oh[109.85-110.43] because[110.43-110.85]
  heard: be.[103.64-104.30] Tell[105.18-105.40] me,[105.40-105.68] baby,[105.76-106.46] because[107.10-107.48] I[107.48-107.66] need[107.66-108.02] to[108.02-108.30] know[108.30-108.84] now.[108.84-109.32] Because[109.98-110.64] my[110.64-111.54]
  cue span (offset-shifted, as used): 104.66-109.66

Miss Independent L3 0:11 Looking good.  (first further, last tie; source aligned -> re-aligned)
  prev NOW line 2: 9.80-11.83; next 4: 12.90-16.66
  PRE: Looking[11.89-11.99] good.[12.29-12.79]
  MID: Looking[11.89-11.99] good.[12.29-12.79]
  NOW: Looking[11.82-11.92] good.[11.92-12.64]
  heard: morning.[11.22-11.56] Looking[11.90-12.02] good,[12.02-12.24] Mia.[12.34-12.52] Thank[12.78-12.98] you.[12.98-13.34]
  cue span (offset-shifted, as used): 11.87-13.33

My Heart Will Go On L3 0:40 Far across the distance  (first ?, last further; source aligned -> re-aligned)
  prev NOW line 2: 31.00-38.75; next 4: 45.13-50.23
  PRE: Far[40.7-41.52] across[42.13-42.26] the[42.26-43.48] distance[43.58-43.96]
  MID: Far[40.37-41.07] across[41.07-42.47] the[42.47-43.17] distance[43.17-44.67]
  NOW: Far[40.5-41.4] across[41.4-42.28] the[42.42-42.84] distance[43.27-44.55]
  heard: across[41.20-42.30] the[42.30-42.96] distance[42.96-43.98] and[43.98-45.36]
  cue span (offset-shifted, as used): 40.75-45.42

My Heart Will Go On L7 1:07 I believe that the heart does go on  (first further, last tie; source aligned -> aligned)
  prev NOW line 6: 62.53-67.69; next 8: 79.45-86.91
  PRE: I[67.76-69.18] believe[69.38-70.39] that[70.49-71.37] the[71.91-72.09] heart[72.09-72.81] does[72.81-73.53] go[73.96-74.67] on[74.67-78.18]
  MID: I[67.68-69.18] believe[69.18-70.73] that[70.83-71.36] the[71.54-72.08] heart[72.08-72.66] does[72.98-73.52] go[74.15-74.66] on[74.66-78.14]
  NOW: I[67.68-69.18] believe[69.18-70.73] that[70.83-71.36] the[71.55-72.1] heart[72.1-72.66] does[72.98-73.52] go[74.15-74.66] on[74.66-78.14]
  heard: are[66.98-67.70] I[68.70-69.18] believe[69.18-69.94] That[71.07-71.34] the[71.34-72.10] heart[72.10-72.66] does[72.66-73.52] Go[73.72-74.68] on[74.68-76.38] Once[78.72-80.62]
  cue span (offset-shifted, as used): 68.67-79.83

My Heart Will Go On L8 1:19 Once more, you open the door  (first ?, last further; source re-aligned -> re-aligned)
  prev NOW line 7: 67.69-78.15; next 9: 87.09-92.23
  PRE: Once[79.5-80.89] more,[81.38-83.1] you[83.79-84.19] open[84.19-86.11] the[86.21-86.39] door[86.58-87.13]
  MID: Once[79.31-81.15] more,[81.25-82.95] you[83.79-84.62] open[84.72-85.64] the[85.82-86.36] door[86.36-87.0]
  NOW: Once[79.45-81.28] more,[81.38-82.95] you[83.78-85.02] open[85.12-86.09] the[86.19-86.36] door[86.5-86.91]
  heard: Once[78.72-80.62] more[80.62-82.34] You[83.82-84.20] open[84.20-85.68] the[85.68-86.36] door,[86.36-87.26]
  cue span (offset-shifted, as used): 79.83-87.88

My Heart Will Go On L9 1:27 And you're here in my heart  (first further, last closer; source aligned -> aligned)
  prev NOW line 8: 79.45-86.91; next 10: 92.23-100.35
  PRE: And[87.14-88.46] you're[88.46-89.04] here[89.04-89.68] in[89.68-92.12]
  MID: And[87.1-88.48] you're[88.61-89.02] here[89.02-90.04] in[90.14-90.76] my[90.9-91.32] heart[91.9-92.24]
  NOW: And[87.08-88.48] you're[88.61-89.02] here[89.02-90.04] in[90.14-90.76] my[90.9-91.32] heart[91.88-92.22]
  heard: door,[86.36-87.26] and[87.87-88.58] you'll[88.58-89.02] hear[89.02-89.94] in[89.94-90.78] my[90.78-91.32] heart,[91.32-92.26] and[92.26-92.86]
  cue span (offset-shifted, as used): 87.88-92.42

My Heart Will Go On L25 3:53 You are safe in my heart and  (first tie, last further; source re-aligned -> re-aligned)
  prev NOW line 24: 224.93-232.78; next 26: 238.80-248.55
  PRE: You[233.5-233.89] are[233.89-234.59] safe[234.59-235.21] in[235.21-236.17] my[236.67-236.83] heart[237.12-237.69] and[237.69-238.29]
  MID: You[233.42-233.66] are[233.66-234.41] safe[234.41-235.41] in[235.41-235.91] my[235.91-236.41] heart[236.41-237.66] and[237.66-238.41]
  NOW: You[233.52-233.92] are[233.92-234.42] safe[234.42-235.84] in[235.84-236.32] my[236.32-236.9] heart[236.9-237.7] and[237.7-238.24]
  heard: You[233.24-234.02] are[234.02-234.42] safe[234.42-235.84] in[235.84-236.46] my[236.46-236.88] heart[236.88-237.66] And[237.86-238.32]
  cue span (offset-shifted, as used): 233.29-238.79

My Heart Will Go On L26 3:58 My heart will go on and on  (first further, last closer; source re-aligned -> re-aligned)

  PRE: My[239.03-239.31] heart[239.45-239.93] will[239.96-240.63] go[241.02-241.67] on[241.67-243.77] and[243.87-243.97] on[243.97-249.55]
  MID: My[238.94-239.55] heart[239.55-242.3] will[242.4-243.9] go[244.68-245.82] on[245.82-246.96] and[246.96-248.46] on[248.67-249.81]
  NOW: My[238.8-239.18] heart[239.28-239.96] will[239.96-241.11] go[241.21-241.66] on[241.66-243.57] and[243.67-243.98] on[243.98-248.55]
  heard: And[237.86-238.32] my[238.98-239.34] heart[239.34-239.96] will[239.97-241.14] go[241.14-241.68] on[241.68-243.16] and[243.16-244.00] on[244.00-244.42]
  cue span (offset-shifted, as used): 238.79-250.21

She Used To Be Mine L29 2:24 Who be reckless just enough  (first ?, last further; source aligned -> re-aligned)
  prev NOW line 28: 141.87-143.77; next 30: 149.50-152.35
  PRE: Who[144.64-144.74] be[144.74-145.02] reckless[145.02-147.08] just[147.18-147.48] enough[147.89-148.57]
  MID: Who[144.64-144.74] be[144.74-145.02] reckless[145.02-147.08] just[147.18-147.48] enough[147.89-148.57]
  NOW: Who[144.46-144.6] be[144.6-145.0] reckless[145.0-146.98] just[147.08-147.4] enough[147.77-148.57]
  heard: Who'll[144.08-144.80] be[144.80-145.00] reckless[145.00-145.82] just[145.82-147.42] enough[147.42-148.48]
  cue span (offset-shifted, as used): 144.65-149.43
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

Phase 5c (Decision 13, ratified by Ken):

```
Branch cue_align_windows, HEAD 8cc7588. Plan: plans/cue-align-windows.md, Decision 13
and Phase 5c. Done, don't redo: Phases 1-5b steps 1-5, the review fixes (8cc7588),
rows 40-46. First commit the plan edits (rows 43-46, Decision 13, Phase 5c) as
docs(plan). Do Phase 5c steps 1-3 (window end, zero-length words + guard, CPU check
before each commit); step 4 only if Ken has agreed to it. Stop before step 5's GPU
rerun until Ken stops the app and says go; then stop at GATE B with Ken's list.
```

Phase 5c step 5 (after the row-51 review fixes):

```
Branch cue_align_windows, HEAD c47882d. Plan: plans/cue-align-windows.md, Phase 5c
steps 5-6, Decisions 13-15. Done, don't redo: Phase 5c steps 1-4 and 4b (rows 47-54).
Decisions 14-15 are proposals: change nothing for them. Ask Ken to stop the app and say
go; dry run first, then step 5's compares; stop at GATE B with Ken's list.
```
