Model: Claude Sonnet 5.5 (executor, Phases 1-4). Author: Claude Fable 5.2, 2026-11-13.
Judge at GATE H: Claude Opus 5.5, then Ken. Where Claude Fable 5.2 would earn its keep, if
Ken still has it at build time, is listed under "Where Fable would help".

# Cue-align rescue: the transcriber's words outrank the cue

**Status: planned 2026-11-13. No code. Next: Phase 1, Sonnet.**

Branch `cue_heard_rescue`, off `dev` `a7671d7`.

## Where Fable would help

Ken asked (2026-11-13) which later parts could use Fable 5.2, in case it is still
available when they come up. Sonnet executes the plan either way and Opus is the
fallback at each of these. Most useful first:

1. **GATE H.** The read judges the rules against a reference that is itself doubtful (the
   transcriber misses lines, hears echoes, and is early after a gap), has to explain
   every Table O line, and has to tell a rule D line moved onto its sung words from one
   moved onto a backing echo. The reads of GATEs P, F and Q on `lrclib_fit_pick` each
   turned up a flaw in the measurement, not only in the songs.
2. **A read of the CPU tables before Ken's GPU run (step 3b2, optional).** Tables P and O
   say whether the replay is sound. Many songs left out, or any line moving that no rule
   names, means the build is wrong and the GPU run would be wasted. Diagnosing which is
   harder than producing the tables.
3. **A diff read of 1c and 2a before the review.** 1c splits a function of 150 lines
   that must keep today's output byte for byte. 2a moves one line's cue span, and four
   things must follow it together (the window, the singing-end search, the aimed span,
   the start bound); `archive/cue_align_windows` shipped a bug of exactly that shape
   (its review finding 1). The `/code-review` at 2d looks for it too; this is a second
   pair of eyes on the two riskiest steps, not a replacement.
4. **Any STOP where the code contradicts the plan, or a rule's wording has to change.**
   The rules are pre-registered; whoever rewords one has to know what the gate still
   means afterwards.

Not needed: 1b, 1d, 2a2, 2b, 2c, the probe's table code, staging, the compare tables, the
listening sheet. Each handoff carries branch and HEAD, this file and the section, what
is done, the next step and where to stop.

## Goal

Cue align's rescue step (`cue_align.repace_bad_lines`) trusts a line's cue time over
the audio. Where the cue is seconds off (an LRCLIB record cut differently from the
video; a caption timed loosely) the rescue looks for the line in the wrong audio, or
moves a line the first pass had right back onto its wrong cue.

Every cue-route song already has the transcriber's words (the de-reverb gate hears the
whole stem before the align). The rescue does not read them. This plan makes it:

> A placement the transcriber confirms is kept, and the rescue never replaces it with
> one the transcriber does not confirm.

Ken asked (2026-11-13) whether the mechanism of `archive/cue_align_windows` (find lines
missing words, re-align them) could realign the shifted lines of `lrclib_fit_pick`
picks, and said he is open to improvements on cue align windows itself.

## What the three flawed picks showed

Ken listened on 2026-11-12 to three LRCLIB picks with known flaws, timed by cue align
(`plans/lrclib-shift-check.md` on `lrclib_fit_pick`, Results row 9; bundles in
`D:\Shared\lrclib-cue-trial\alignment_debug`). Traced 2026-11-13 from those bundles
(`cue_inputs.sections` against `output_line_timings` and `transcribe_words`); times in
seconds:

| Song | Ken heard | Line | Cue | First pass | Shipped | Transcriber | What happened |
|---|---|---|---|---|---|---|---|
| Quit Playing Games `Ug88HO2mg44` | "the late section is late in the karaoke as well" (about 1:57) | 24 | 117.3 | 113.6 | 117.0 | 113.6 | Two identical lines in a row. The first pass had both right. The rescue demands that repeated lines sit on their cue, found them 3.7 s off it, and spaced them evenly from the cue. |
| | | 25 | 118.9 | 116.8 | 118.5 | 116.9 | Same. |
| | not named | 1 | 15.4 | 14.3 | 18.5 | 14.0 | The first pass was right. A one-line re-align moved it 4 s late. |
| (You Drive Me) Crazy `Q4VK9_CfOLQ` | "line appears early in 1:51 but ends on time" | 22 | 109.6 | no words | 110.2 | 114.8 | Sung 5 s after its cue, outside its block. The one-line retry listened around the cue, found nothing, and the line was spaced from the cue. |
| Reflection `RNprQYHenNI` | "3:11 that line comes in quite early" | 36 | 190.9 | no words | 191.1 | not heard | Same as Crazy, and the transcriber did not hear the line either. |

Two of Ken's five spots are a different kind and are **not** this plan's: Quit Playing
Games 0:52 (line 8, a whole line starting 0.7 s early) and 2:32 (line 37, a whole
two-word line 3 s early with one word heard). Both lines have all their words, so the
rescue never looks at them. The first is `onset_loud_start`'s kind. The second has one
heard word, so it is not a heard line and rule D (Decision 2b) does not reach it. Both
are expected unchanged.

So detection already fires where it matters. What is wrong is where the retry aims and
what the rescue is willing to overwrite.

## Sizing (exploratory, 2026-11-13)

Read-only scratch script over the library's bundles (234; 177 on the cue route with
`cue_inputs` and `transcribe_words`: 149 caption songs, 28 LRCLIB-timed). A line counted
as heard when a whole-song in-order match gave it at least half its words; "confirmed"
meant a line start within 1.0 s of the heard start. Looser than the rules below (no
two-word minimum, no repeated-line condition, starts only), so the probe's tables
replace these counts.

| | Caption songs | LRCLIB-timed songs |
|---|---|---|
| Worded lines | 9440 | 1428 |
| Rescue replaced a line whose first-pass start was confirmed, with one that is not | 31 lines in 26 songs (18 end more than 1.5 s off) | 12 in 8 (5) |
| Rescued line heard more than 1.5 s from where it ended up, first pass not confirmed | 45 in 35 | 12 in 11 |
| Spaced from the cue, not heard | 119 in 48 | 21 in 7 |
| Whole lines the rescue never touched, more than 2.0 s from where heard | 181 in 92 | 25 in 15 |

The fault is not LRCLIB's alone: caption songs carry it too.

**Whole lines far from where heard (the last row), sized again for rule D.** Ken asked
what rescuing them would cost. Second scratch run, same bundles, with this plan's heard
rule (two matched words, half the tokens, the identical-run condition), over complete
lines the rescue left alone (8126 caption, 1184 LRCLIB-timed):

| | Caption songs | LRCLIB-timed songs |
|---|---|---|
| Heard and confirmed | 6075 | 924 |
| Not heard | 1118 | 129 |
| Heard, not confirmed | 933 | 131 |
| First word heard, line start 1.5 s or more from it | 278 in 110 songs | 47 in 19 |
| Of those, every paired word 1.5 s or more off | 21 in 16 (9 shown early, 12 late; 14 outside a run of identical lines) | 6 in 4 (4 early, 2 late; all 6 outside a run) |
| The same at 2.0 s / 3.0 s for the line start | 20 / 18 | 5 / 3 |

Read with that run:

- Most far-off whole lines are not displaced lines. Only the first word is early and
  the rest of the line agrees with the transcriber: Ken's "comes in early but ends on
  time". A re-align is the wrong tool for that; it is `onset_loud_start`'s work. About
  250 caption lines and 40 LRCLIB lines are of that kind.
- Whole lines displaced as a whole number about 27 in the library. Rule D is for those.
- On the three trial songs rule D would fire on no line.
- The risk it adds: these are lines the aligner placed cleanly. If the transcriber
  missed the lead and heard a backing echo of the same words a few seconds away, the
  retry lands on the echo and counts as confirmed. With about 27 lines the judge can
  read every one.
- The sizing did not require the paired words to be off the same way; the rule does, so
  the probe's count may be a little lower.

## Decisions

Ken, 2026-11-13, by question dialog:

1. **All cue-align songs.** One rule for uploader captions, Repair's LRCLIB timing and
   the automatic LRCLIB picks. No per-source switch.
2. **Three repairs:** keep confirmed lines (rule A), retry where heard (rule B), retry
   between neighbours (rule C). On a detector for whole lines far from where they were
   heard, his words at first: "note flag far-off whole lines for later revisit".

   2b. Later the same day, after the second sizing ("how much extra work would it be
   to rescue far-off whole lines?"; told: one small commit, about 27 lines, neither of
   his two leftover spots): "add it, along with your notes on it". It is rule D, a
   fifth rule he can drop at GATE H like the others.
3. **Better karaoke only.** The LRCLIB bar and GATE Q stay as ruled. This plan does not
   size a looser bar.
4. **Ride-alongs from cue align windows' open issues:** the guard against the
   transcriber (Miss Independent 3:59), and zero-length words left on screen.

The author's, not ruled by Ken; he may overrule any:

5. Own branch off `dev`. It does not wait on Phases 4-6 of `plans/lrclib-fit-pick.md` or
   on `onset_loud_start`. Both of those change `lyric_align.py` near the `align_song`
   call; whichever lands second is replayed onto the other.
6. Each rule is its own commit with its own stats key, so a rule Ken rules out at GATE H
   is left off `dev` without touching the others. Rule C is last for that reason. Rule
   D rides on rule B's retry: without B there is no D.
7. Rules B and D keep a heard-aimed retry only when the transcriber confirms the result.
   Otherwise the line takes today's path unchanged. So every outcome of A, B and D that
   differs from today is a placement the transcriber confirms. Rule C has no such
   reference and is judged by Ken's ear alone.
8. A one-word line is never judged by heard words: one matching word is too easy to find
   by chance.
9. In a run of identical lines, the transcriber's confirmation counts only when it
   heard every line of the run. With one of them unheard, heard words cannot say which
   line they belong to, and the standing rule (repeats sit on their cue) stays in force.
10. No `SCHEMA_VERSION` bump, no web-UI change. New stats keys are additive.
11. A zero-length word that gets guessed timing counts in Song Info's "words have
    guessed timing" line, since it now is one.
12. No lyric text in any commit, test or this plan. Tests use made-up lines.

Not in this plan: whole lines whose first word alone is early (`onset_loud_start`); a
Song Info or Tools-tab flag for shifted lines (the `plans/open-issues.md` entry "Flag
finished-karaoke lines that are shifted"); spacing a failed line across its heard words
instead of its cue; one rule for repeated-word matching
(`plans/open-issues.md`, "Repeated tokens get two assignment rules"); any change to
`lrc_auto_pick`, `srt_slice_fit` or section windows.

## The rules (pre-registered)

Fixed here before any table under this plan exists. GATE H reads these values only.
Constants (suggested names) live with the code that uses them, each with a comment
saying what it guards against.

**Heard line.** One whole-song match of the transcriber's words to the sheet's tokens:
`token_align.match_words_to_tokens`, tokens from `joint_match._tokenise_lines(align_lines)`,
each token's expected time paced evenly over its cue span plus the fitted offset (as
`split_section_to_lines` paces them), words normalised with `_normalize_token`. Each
heard word goes to at most one token. A line is *heard* when it has at least two tokens,
at least `HEARD_MIN_WORDS` (2) of them matched, and at least `MIN_LINE_COVERAGE` (half)
of them matched. Its heard words are the matched words in order; its heard start is the
first one's start. Otherwise the line is not heard.

**Confirmed.** A line object is *confirmed* when its line is heard and:

- its timed words (at least `INSTANT_WORD_DUR_S` long) are paired in order with the
  line's heard words by equal normalised text (`match_words_to_tokens` again, the line's
  word starts as the expected times);
- at least `HEARD_MIN_WORDS` pairs, and at least half the line's tokens are paired;
- every pair's two starts lie within `HEARD_AGREE_S` (1.0 s) of each other;
- if the line is in a run of identical lines (`_repeat_detection_slacks` has it), every
  line of that run is heard (Decision 9). A run is the maximal stretch of adjacent lines
  with equal normalised text.

**Rule A, keep confirmed lines.**

- A1. A line the placed test fails (`_line_in_span` for repeats, `_line_is_good`
  otherwise) counts as placed when it is confirmed.
- A2. A one-line re-align replaces a confirmed line only when the re-align is confirmed
  too (on top of today's "times more words").

**Guard lift (ride-along).** A re-align that is confirmed as the aligner returned it is
not held to the previous line's end: `_start_bound`'s previous-line part is skipped, the
lead-in part stays.

**Rule B, retry where heard.** For a line that reaches the retry (bad, partial or
crammed), is heard with its first token among the matched, and whose heard start is
`HEARD_SHIFT_S` (1.5 s) or more from `cue start + offset`: the retry is first aimed at
the line's cue span moved by that difference (window, singing-end search, aimed span and
start bound all from the moved span). The result is kept when it passes today's checks
against the moved span and is confirmed. Otherwise the line takes today's path
unchanged, cue-aimed retry included.

**Rule D, whole lines far from where heard.** For a line the rescue would leave alone
(placed, a timed word for every token) that is heard with its first token among the
matched and is not confirmed: pair its words with its heard words as the confirmed test
does. When there are at least `HEARD_MIN_WORDS` pairs, at least half the line's tokens
are paired, and every pair's starts are `HEARD_SHIFT_S` or more apart, all the same way
(all early or all late), the line gets rule B's heard-aimed retry: its cue span moved to
start at its heard start. The result replaces the line when it passes rule B's checks
(the moved span, confirmed). Otherwise the line stays exactly as it is; there is no
second retry, because the line was never bad. In a run of identical lines the
confirmed test's run condition applies, so a line of a run the transcriber did not hear
in full is never replaced.

**Rule C, retry between neighbours.** For a bad line (not placed) that rule B did not
aim, whose retry was not kept: before it is spaced from its cue, one more retry over the
free stretch from the end of the last line already output that has words and is not a
fill (0.0 when none) to the start of the next first-pass line that `_line_is_clean`
(`duration` when none; no retry when `duration` is None). Only when the stretch reaches
`HEARD_SHIFT_S` or more beyond the first window on at least one side and is at most
`GAP_RETRY_MAX_S` (30 s) long. Kept when every token is timed, `_line_is_clean` holds,
and the line lies inside the stretch (a first word before the stretch's start is cut to
it by `_start_from`, as the guard does). Tagged `SOURCE_REALIGN`.

**Zero-length words (ride-along).** After the rescue, a kept line with a word for every
token, some under `INSTANT_WORD_DUR_S`, has those words re-timed as guessed words by
`_with_guessed_words`' spacing rules. Tokens map to words by index (the line has one
word per token), so `_assign_in_order` is not consulted for these lines. Every kept line
has at least half its words timed (the placed tests and the re-align check all require
it), so no line is left without a timed word to pace from.

**Without heard words** (`heard_words=None`, an empty list, or a song where no line is
heard) rules A, B, D and the guard lift never fire. Rule C and the zero-length rule do
not depend on heard words.

## Design

- **`pikaraoke/lib/heard_lines.py`** (new, pure). `heard_lines(align_lines, spans,
  heard_words) -> list[HeardLine | None]` (`spans` already on the audio clock) and
  `confirms(obj, n_tokens, heard, run_heard: bool) -> bool`. `HeardLine` is a frozen
  dataclass: `words` (the matched heard words, in order) and `first` (token 0 matched);
  `start` is a property. It must not import `cue_align` (which imports it):
  `_token_expected_times` moves to `token_align` as the shared pacing helper and both
  import it from there.
- **`cue_align.repace_bad_lines(..., heard_words: list[dict] | None = None)`** computes
  the heard lines once from `cue_spans` plus the fitted offset and applies the rules
  above. `align_song(..., heard_words=None)` passes it through.
  `repace_bad_lines` is already past 150 lines: split it while touching it (the placed
  test, one line's retry, the guess pass) so that each rule lands in a function of its
  own. Rules B and D share one heard-aimed retry function; D adds only its trigger.
  Behaviour with `heard_words=None` and rule C and the zero-length rule aside must
  stay byte-for-byte: the existing tests of `test_cue_align.py` pass unedited through
  Phase 1.
- **Stats** (`repace`): `n_heard_lines` (a count; the ids are not stored),
  `heard_kept_line_ids` (A1), `heard_held_line_ids` (A2: a re-align refused because the
  line was confirmed and the re-align was not), `guard_lifted_line_ids`,
  `heard_aimed_line_ids` (B tried) and `heard_aimed_kept_line_ids` (B kept),
  `whole_aimed_line_ids` (D tried) and `whole_aimed_kept_line_ids` (D kept),
  `gap_retry_line_ids` (C tried) and `gap_retry_kept_line_ids` (C kept),
  `zero_length_guessed_line_ids`. The log line gains the counts.
- **`cue_inputs.realigns`** already records every one-line align with its window, so the
  new retries are captured with no change.
- **`LyricAlignStage._run_cue_align`** passes the gate's `transcribe_words` to
  `align_song`. Its docstring's "which the cue route doesn't use" goes.
- **Module docstring** of `cue_align.py`, "Approach" step 3: say that heard words
  outrank the cue in the rescue.

## Phases

Stop at every STOP. If a step contradicts the code, stop and say what differs. Conda env
`pik`. Tests ride with the code they exercise. Plan edits in their own commits. Never
launch `/code-review`; hand Ken the line. No verdicts in the Results log: tables go in
raw.

### Phase 1: the heard reference, rule A, the guard lift (Sonnet)

GPU-free, no library read.

- [ ] **1a. Anchor check.** In the worktree of `cue_heard_rescue`. Confirm these exist
  as this plan uses them, else STOP: `cue_align.repace_bad_lines`, `align_song`,
  `_line_in_span`, `_line_is_good`, `_line_is_clean`, `_repeat_detection_slacks`,
  `_start_bound`, `_start_from`, `_previous_line`, `_line_from_realigned`,
  `_repace_line`, `_with_guessed_words`, `_assign_in_order`, `_timed_words`,
  `_singing_end`, `_token_expected_times`, `SOURCE_REALIGN`, `SOURCE_FILL`;
  `token_align.match_words_to_tokens`, `_normalize_token`;
  `joint_match._tokenise_lines`; `LyricAlignStage._run_cue_align` (it holds
  `transcribe_words` before it calls `align_song`); `alignment_capture.build_bundle`
  stores `transcribe_words` and `cue_inputs` on the cue route.
- [ ] **1b. `heard_lines.py`** with `tests/unit/test_heard_lines.py`: a line heard in
  full; under half matched; one matched word of five; a one-word line; two identical
  lines both heard, each gets its own words; the second of two identical lines unheard
  (`run_heard` False refuses both); `confirms` with a pair 1.2 s apart; with a
  zero-length word among the pairs (ignored); `first` False when token 0 is unmatched;
  no heard words at all.
  Commit: `feat(cue_align): where the transcriber heard each lyric line`.
- [ ] **1c. Rule A and the wiring.** `repace_bad_lines` and `align_song` take
  `heard_words`; the stage passes them. Tests in `test_cue_align.py` (stub aligner,
  made-up lines): the Quit Playing Games shape (two identical lines the first pass put
  3 s before their cues, both heard there: kept, not spaced from the cue); the same with
  one of the two unheard (today's result); a non-repeat line with a 2.5 s inner pause
  starting before its cue, heard there (kept, no re-align asked); A2 (a confirmed
  crammed line whose re-align times more words 2 s later: the line is kept, and listed
  in `heard_held_line_ids`); A2 with a confirmed re-align (replaced, as today);
  `heard_words=None` reproduces today's output on every existing case. One test in
  `test_lyric_align.py`: the stage hands the gate's words to `align_song`.
  Commit: `feat(cue_align): the rescue keeps a line the transcriber confirms`.
- [ ] **1d. The guard lift.** Test: the Miss Independent shape (a two-word re-align
  starting 0.9 s before the previous line's end, both words heard there: kept untrimmed;
  the same unheard: trimmed or refused as today).
  Commit: `feat(cue_align): a re-align the transcriber confirms is not cut to the previous line`.
- [ ] **1e.** Full suite, pre-commit on the changed files, self-review on the three
  axes. Results log row. **STOP** (a clean point for `/compact`).

### Phase 2: rules B and D, zero-length words, rule C (Sonnet)

GPU-free, no library read.

- [ ] **2a. Rule B.** Tests: the Crazy shape (a line with no first-pass words, heard
  4.6 s after its cue; the stub aligner answers only in the moved window: kept there,
  `SOURCE_REALIGN`, one align call); the heard-aimed result not confirmed (the stub
  answers 2 s off the heard words: today's cue-aimed retry runs next and today's result
  stands, two align calls); heard start 1.2 s from the cue (no heard-aimed retry); first
  token unheard (none); a heard-aimed line that is the song's last (window end from
  `_volume_tail`).
  Commit: `feat(cue_align): a rescue retry is aimed where the line was heard`.
- [ ] **2a2. Rule D.** The trigger only; the retry is 2a's. Tests: a complete, clean
  line placed 3 s before its heard words, every pair 3 s off (the stub answers on the
  heard words: replaced, `SOURCE_REALIGN`, one align call); the retry's result not
  confirmed (the line is returned unchanged, object-equal to its input, one align call,
  no cue-aimed retry); only the first word 2 s early and the rest within 0.3 s (no
  retry: the `onset_loud_start` kind); pairs off in opposite directions (no retry); one
  heard word of two tokens (not heard, no retry); a line in a run of identical lines
  with one of the run unheard (no retry); a confirmed line (no retry).
  Commit: `feat(cue_align): a whole line far from where it was heard is re-aligned there`.
- [ ] **2b. Zero-length words.** `_with_guessed_words` takes its per-token word list
  from the caller, so a crammed line (by index) and a partial line (by
  `_assign_in_order`) share the spacing code. Tests: a crammed line's zero-length middle
  word between two timed words with room; without room (shares the neighbour's slot, no
  word under `INSTANT_WORD_DUR_S` where the slot allows); a zero-length first and last
  word; the stats; a partial line's output unchanged.
  `library_status._cue_fields` needs no change if the stats keys it reads
  (`n_guessed_words`, `guessed_word_line_ids`) include these words; make them include
  them (Decision 11) and test the count.
  Commit: `feat(cue_align): zero-length words a rescue leaves get guessed timing`.
- [ ] **2c. Rule C.** Tests: the Reflection shape (a wordless unheard line whose
  cue-aimed retry fails; the stub answers in the free stretch 5 s later: kept there); a
  stretch over 30 s (no retry); a stretch no wider than the first window (no retry); a
  result with one token untimed (refused, spaced from the cue as today); two bad lines
  in a row (the second's stretch starts at the first's kept end); `duration` None.
  Commit: `feat(cue_align): a line the retry cannot find is looked for between its neighbours`.
- [ ] **2d.** Full suite, pre-commit, self-review, `graphify update .` where the graph
  exists. Results log row. **STOP: review due** (core pipeline). Hand Ken the line, do
  not launch it: `/code-review <1b's commit>~1..HEAD` on `heard_lines.py`,
  `cue_align.py`, `token_align.py`, `lyric_align.py`, `library_status.py` and their
  tests, three finders: correctness (is every A, B or D outcome that differs from today
  confirmed; does `heard_words=None` reproduce today; does a refused D retry leave the
  line untouched), simplicity (one heard match per
  song, one confirm function, no second copy of the retry), robustness (empty or
  malformed heard words, overlapping cues, the last line, `duration` None).

### Phase 3: the library on the CPU, then the test copy (Sonnet; needs the shared drive)

Read-only on the library (`/home/ken/shared-drives/D:/Shared/pikaraoke-songs`).

- [ ] **3a. Probe** `scripts/cue_heard_probe.py` with `tests/unit/test_cue_heard_probe.py`
  (made-up bundles). For every bundle on the cue route with `cue_inputs` and
  `transcribe_words`:
  - decode the snap stem's envelope once and cache it under `--out`;
  - **baseline replay**: `repace_bad_lines` over `cue_inputs` with `heard_words=None`
    and the zero-length rule and rule C off for the replay, then `snap_line_edges`; the
    saved re-aligns answer the `realign` calls. A song whose replay does not equal its
    `output_line_timings` within 0.011 s is left out and named;
  - **new replay**: the same with the song's `transcribe_words` and every rule on. A
    `realign` call the bundle holds no answer for returns None and is recorded: that
    line's result needs the GPU.
  How the two rules are switched off for the baseline is the executor's call, but it
  must not become a production option: the probe may call the split-out functions of
  1c directly.
  Tables to stdout, counts and ids only, each split caption / LRCLIB:
  **P** songs read, left out and why. **A** lines A1 keeps and lines A2 holds: song,
  line, cue start, today's start, new start, heard start, whether in a run of identical
  lines. **G** guard lifts. **Z** zero-length words: lines and words before, words re-
  timed, words still under 0.1 s after. **B** lines rule B would aim: the shift, the
  window. **D** lines rule D would aim: today's start, the heard start, the number of
  pairs, the smallest and largest pair offset, whether in a run of identical lines;
  and, as counts only, the complete untouched lines that are heard and unconfirmed but
  miss the trigger, split by why (first token unheard; some pair under 1.5 s; pairs off
  both ways). **C** lines rule C would try: the stretch and its length. **O** every other
  line whose start or end moves more than 0.011 s, with the amount. **V** (sizing only)
  Table A's counts at `HEARD_AGREE_S` 0.5 / 1.0 / 1.5 and `HEARD_MIN_WORDS` 2 / 3.
  `--out` holds `rows.json` (one row per changed line, with lyric text) and is never
  committed.
  `--stage DIR --song ID...` copies those songs' files (`library_regen.song_files`, the
  video, stems and bundle) into a copy library; `--from DIR` names another source
  folder for a song.
  Commit: `feat(scripts): probe of the cue rescue against the heard words`.
- [ ] **3b. The run.** `python scripts/cue_heard_probe.py --folder <library> --out
  ~/.pikaraoke/tmp/cue_heard_rescue > report.md`. Paste Tables P, A, G, Z, B, D, C, O,
  V raw into "Report output", no tallies beyond the tables' own, no reading. Read-only
  check: `find <library> -newer <out>/started` prints nothing of this run's.
- [ ] **3b2. Optional read before the GPU run** ("Where Fable would help", item 2). If
  Ken wants it, STOP here with a handoff: branch and HEAD, this file's "Report output",
  `<out>`, "do not rerun the probe", and the question: do Tables P and O show a sound
  replay (few songs left out, each for a reason unrelated to this branch; no line in
  Table O that the rules' own knock-ons do not explain)? Without the read, the executor
  goes on to 3c unless Table P leaves out more than 10 songs or Table O has a line
  moving more than 0.3 s; either is a STOP.
- [ ] **3c. The test songs**, by this rule, no judgement:
  - the three trial songs from `D:\Shared\lrclib-cue-trial` (`--from`; their bundles
    there are the "before");
  - from the library, by stem order within ties: the 5 songs with the most Table A
    lines, the 5 with the most Table B lines, the 5 with the most Table C lines, the 5
    with the most Table D lines;
  - Miss Independent `k6M5C-oKw9k` and She Used To Be Mine (the zero-length case of
    `archive/cue_align_windows` Decision 13), if not already in.
  Stage them to `/home/ken/shared-drives/D:/Shared/cue-heard-trial`. A `--dry-run` of
  `scripts/regen_alignment_bundles.py` on the copy must list every staged song with the
  lyric source its bundle has; else STOP.
- [ ] **3d. STOP: Ken's GPU run.** Hand him, for Windows (`C:\temp\Github\pikaraoke`,
  branch fetched from remote `vm`): `uv run python scripts/regen_alignment_bundles.py
  D:\Shared\cue-heard-trial --yes`. The library is not touched.

### Phase 4: before against after (Sonnet; after Ken's run)

- [ ] **4a.** `--compare <copy>`: each staged song's new bundle against its source
  bundle. Tables, raw: per rule (the new stats ids), each line's start before, after and
  heard, and for A, B and D lines whether the new start is closer to, within 0.05 s of,
  or further from the heard start; for every D line tried, kept or not, its start and
  end before and after and the previous and next lines' times, so the judge can read
  each one; Table O again (other lines that moved, with amounts);
  the three target spots of "What the three flawed picks showed", and line 1 of Quit
  Playing Games.
- [ ] **4b. Listening sheet** `<out>/listening-sheet.html`, at most 22 spots, in this
  order: the three target spots and Quit Playing Games line 1; then rule C kept lines,
  largest move first, at most 2 a song, up to 8; rule D kept lines up to 3; rule B up
  to 4; rule A up to 2; one zero-length line. Each row: song, m:ss (4 s before the earlier start), rule, before
  and after. Ken plays the copy in an isolated app (`APPDATA` `C:\temp\p8\appdata`), as
  on 2026-11-12.
- [ ] **4c.** Tables into "Report output". Results log row. **STOP: GATE H.** Handoff
  prompt to Opus carries: branch and HEAD, this file and "GATE H", `<out>` and the copy
  folder, "do not rerun the probe", and that Ken's verdicts arrive in chat.

## GATE H (Opus, then Ken)

Read-only. Inputs: the Phase 3 and 4 tables, `<out>`, Ken's verdicts on the sheet.

1. **The rules as pre-registered.** Table V is for sizing.
2. **The three target spots,** by Ken's ear: Quit Playing Games about 1:57, Crazy 1:51,
   Reflection 3:11. The plan's reason to exist; each better, same or worse in his
   words. Quit Playing Games 0:52 and 2:32 are expected unchanged.
3. **Rules A, B and D and the guard lift.** By construction each changed line is
   confirmed. The judge reads: any A, B or D line "further" in 4a (it would mean the
   heard match took the wrong words); every Table A row inside a run of identical lines;
   Ken's sheet verdicts.

   **Rule D** is also read line by line, every kept line of the staged songs, not a sample:
   the aligner had placed each of these cleanly, so the question for each is whether
   the heard words it moved to are the lead or a backing echo of the same words. Signs
   of an echo: the line now overlaps or follows the next line's start; the heard words
   it took sit inside another line's span; the first pass's place has singing the
   transcriber did not put words to. Any line the judge cannot settle goes to Ken's ear
   beyond the sheet's three.
4. **Rule C,** by Ken's ear only. Kept, tried and refused counts are reported.
5. **Zero-length words:** Table Z and Ken's one listen.
6. **Table O.** Any line outside the rules' id lists that moved more than 0.3 s is named
   and explained before anything is ruled.
7. **Report to Ken** with the caveats: the transcriber's first word is itself early
   after a gap (`plans/onset-loud-start.md`, Table C), so "closer" is weak under about
   0.3 s; rule C has no reference; fifteen library songs and three trial songs were
   re-run, the rest are CPU replays that cannot show a B or C result.
   Ken rules each of A, B, D, C, the guard lift and the zero-length rule: land or leave
   out (leaving out B leaves out D). Record the read and the rulings here.

## Phase 5: after GATE H

- Rules ruled out: their commits are not replayed onto `dev` (Decision 6); if a later
  commit depends on one, STOP and say so.
- `plans/open-issues.md` (its own commit, it lands on `dev`): the "Flag finished-karaoke
  lines that are shifted" entry gains what this plan found: displaced whole lines are
  few and rule D re-aligns them (or does not, by the gate's ruling); the large group,
  about 290 lines whose first word alone is early, is `onset_loud_start`'s; the flag
  itself is still unbuilt; the cue-align-windows entries this plan closes
  (the guard at Miss Independent 3:59; zero-length words left on screen; the guessed-
  words count question) are repointed or removed; "one zero-length word makes a line
  crammed" stays.
- A `--song` batch for `regen_alignment_bundles.py` listing the library songs whose
  lines Tables A, B, C or Z name, for Ken's Windows box. Existing songs change only when
  regenerated.
- Landing as CLAUDE.md "Branches and Archive Tags"; the copy folder and `<out>` are
  deleted on Ken's say.

## Results log

| # | Date | Phase | What was done | Outputs |
|---|---|---|---|---|
| 1 | 2026-11-13 | plan | Three trial bundles traced; sizing over the library's 177 cue-route bundles, read-only, scratch scripts outside the repo ("What the three flawed picks showed", "Sizing"). Ken's Decisions 1-4 by question dialog. | this file |
| 2 | 2026-11-13 | plan | Second sizing, whole lines the rescue leaves alone, under this plan's heard rule; Ken added rule D (Decision 2b) and asked where Fable would help ("Where Fable would help", step 3b2). | this file |

## Report output

(Phase 3b and 4c paste their tables here.)
