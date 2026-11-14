Model: Claude Sonnet 5.5 (executor, Phases 1-4). Author: Claude Fable 5.2, 2026-11-13.
Judge at GATE H: Claude Opus 5.5, then Ken. Where Claude Fable 5.2 would earn its keep, if
Ken still has it at build time, is listed under "Where Fable would help".

# Cue-align rescue: the transcriber's words outrank the cue

**Status: Phases 1 and 2 done 2026-11-14 (1: `a24348be`..`fecebdd2`; 2a `6eef9d5d`, diff-read fix `f2d305fc`, 2a2 `60789275`, 2b `65438683`, 2c `829d02d6`). Phase 3: 3a (probe `f3edd413`, fix `a0a10911`, tolerance `e23f0d60`), 3b ("Report output", rerun at `e23f0d60`) and 3b2 (Fable 5.2 read, Results log row 13) done 2026-11-14. Not started: 3c, 3c2, 3d. The review is due at 3c2, before the GPU run.**

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

**Paths on the Linux box (2026-11-14).** Phase 3 onward names the Windows share
(`/home/ken/shared-drives/D:/Shared/...`), which does not exist on this machine. Read the
paths below wherever the plan names the left column. Take the library as `--folder`; do
not hardcode any of them.

| Plan names | Use |
|---|---|
| `.../D:/Shared/pikaraoke-songs` | `~/pikaraoke-songs` (a direct copy of the other box's library; `alignment_debug/` holds 234 bundles, 177 with `cue_inputs` and `transcribe_words`) |
| `D:\Shared\lrclib-cue-trial` (3c `--from`) | `~/probes/lrclib-cue-trial` (copied from `/media/ken/Data/probes`, checked identical, 39 files) |
| `.../D:/Shared/cue-heard-trial` (3c, 3d, Phase 4) | `~/probes/cue-heard-trial` (not yet made; Ken copies it to the Windows share for the GPU run) |
| `--out` | `~/.pikaraoke/tmp/cue_heard_rescue` (unchanged) |

Stems for the probe (3a): the snap step reads `ctx.artifacts.get("aligned_stem",
vocal_wav)` (`pipeline/stages/lyric_align.py`). The library has `vocal/` stems for 248
songs and `dereverb/` for only 5, so the probe's header says how it picks a stem, and
Table P names any song whose stem is missing.

### Phase 1: the heard reference, rule A, the guard lift (Sonnet)

GPU-free, no library read.

- [x] **1a. Anchor check.** In the worktree of `cue_heard_rescue`. Confirm these exist
  as this plan uses them, else STOP: `cue_align.repace_bad_lines`, `align_song`,
  `_line_in_span`, `_line_is_good`, `_line_is_clean`, `_repeat_detection_slacks`,
  `_start_bound`, `_start_from`, `_previous_line`, `_line_from_realigned`,
  `_repace_line`, `_with_guessed_words`, `_assign_in_order`, `_timed_words`,
  `_singing_end`, `_token_expected_times`, `SOURCE_REALIGN`, `SOURCE_FILL`;
  `token_align.match_words_to_tokens`, `_normalize_token`;
  `joint_match._tokenise_lines`; `LyricAlignStage._run_cue_align` (it holds
  `transcribe_words` before it calls `align_song`); `alignment_capture.build_bundle`
  stores `transcribe_words` and `cue_inputs` on the cue route.
- [x] **1b. `heard_lines.py`** with `tests/unit/test_heard_lines.py`: a line heard in
  full; under half matched; one matched word of five; a one-word line; two identical
  lines both heard, each gets its own words; the second of two identical lines unheard
  (`run_heard` False refuses both); `confirms` with a pair 1.2 s apart; with a
  zero-length word among the pairs (ignored); `first` False when token 0 is unmatched;
  no heard words at all.
  Commit: `feat(cue_align): where the transcriber heard each lyric line`.
- [x] **1c. Rule A and the wiring.** `repace_bad_lines` and `align_song` take
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
- [x] **1d. The guard lift.** Test: the Miss Independent shape (a two-word re-align
  starting 0.9 s before the previous line's end, both words heard there: kept untrimmed;
  the same unheard: trimmed or refused as today).
  Commit: `feat(cue_align): a re-align the transcriber confirms is not cut to the previous line`.
- [x] **1e.** Full suite, pre-commit on the changed files, self-review on the three
  axes. Results log row. **STOP** (a clean point for `/compact`).

### Phase 2: rules B and D, zero-length words, rule C (Sonnet)

GPU-free, no library read.

- [x] **2a. Rule B.** Tests: the Crazy shape (a line with no first-pass words, heard
  4.6 s after its cue; the stub aligner answers only in the moved window: kept there,
  `SOURCE_REALIGN`, one align call); the heard-aimed result not confirmed (the stub
  answers 2 s off the heard words: today's cue-aimed retry runs next and today's result
  stands, two align calls); heard start 1.2 s from the cue (no heard-aimed retry); first
  token unheard (none); a heard-aimed line that is the song's last (window end from
  `_volume_tail`).
  Commit: `feat(cue_align): a rescue retry is aimed where the line was heard`.
- [x] **2a2. Rule D.** The trigger only; the retry is 2a's. Tests: a complete, clean
  line placed 3 s before its heard words, every pair 3 s off (the stub answers on the
  heard words: replaced, `SOURCE_REALIGN`, one align call); the retry's result not
  confirmed (the line is returned unchanged, object-equal to its input, one align call,
  no cue-aimed retry); only the first word 2 s early and the rest within 0.3 s (no
  retry: the `onset_loud_start` kind); pairs off in opposite directions (no retry); one
  heard word of two tokens (not heard, no retry); a line in a run of identical lines
  with one of the run unheard (no retry); a confirmed line (no retry).
  Commit: `feat(cue_align): a whole line far from where it was heard is re-aligned there`.
- [x] **2b. Zero-length words.** `_with_guessed_words` takes its per-token word list
  from the caller, so a crammed line (by index) and a partial line (by
  `_assign_in_order`) share the spacing code. Tests: a crammed line's zero-length middle
  word between two timed words with room; without room (shares the neighbour's slot, no
  word under `INSTANT_WORD_DUR_S` where the slot allows); a zero-length first and last
  word; the stats; a partial line's output unchanged.
  `library_status._cue_fields` needs no change if the stats keys it reads
  (`n_guessed_words`, `guessed_word_line_ids`) include these words; make them include
  them (Decision 11) and test the count.
  Commit: `feat(cue_align): zero-length words a rescue leaves get guessed timing`.
- [x] **2c. Rule C.** Tests: the Reflection shape (a wordless unheard line whose
  cue-aimed retry fails; the stub answers in the free stretch 5 s later: kept there); a
  stretch over 30 s (no retry); a stretch no wider than the first window (no retry); a
  result with one token untimed (refused, spaced from the cue as today); two bad lines
  in a row (the second's stretch starts at the first's kept end); `duration` None.
  Commit: `feat(cue_align): a line the retry cannot find is looked for between its neighbours`.
- [x] **2d.** Full suite, pre-commit, self-review, `graphify update .` where the graph
  exists. Results log row. **STOP: review due** (core pipeline). Hand Ken the line, do
  not launch it: `/code-review <1b's commit>~1..HEAD` on `heard_lines.py`,
  `cue_align.py`, `token_align.py`, `lyric_align.py`, `library_status.py` and their
  tests, three finders: correctness (is every A, B or D outcome that differs from today
  confirmed; does `heard_words=None` reproduce today; does a refused D retry leave the
  line untouched), simplicity (one heard match per
  song, one confirm function, no second copy of the retry), robustness (empty or
  malformed heard words, overlapping cues, the last line, `duration` None).
  Ken moved the review to 3c2, before the GPU run (2026-11-14).

### Phase 3: the library on the CPU, then the test copy (Sonnet; needs the shared drive)

Read-only on the library (`/home/ken/shared-drives/D:/Shared/pikaraoke-songs`).

- [x] **3a. Probe** `scripts/cue_heard_probe.py` with `tests/unit/test_cue_heard_probe.py`
  (made-up bundles). For every bundle on the cue route with `cue_inputs` and
  `transcribe_words`:
  - decode the snap stem's envelope once and cache it under `--out`;
  - **baseline replay**: `repace_bad_lines` over `cue_inputs` with `heard_words=None`
    and the zero-length rule and rule C off for the replay, then `snap_line_edges`; the
    saved re-aligns answer the `realign` calls. A song whose replay does not equal its
    `output_line_timings` within 0.026 s (one envelope frame; 0.011 s until the 3b2 read, Results log row 13) is left out and named;
  - **new replay**: the same with the song's `transcribe_words` and every rule on. A
    `realign` call the bundle holds no answer for returns None and is recorded: that
    line's result needs the GPU.
  A line can now have two align calls (a heard-aimed one, then the cue-aimed one), so a
  saved re-align answers a call by `(line, w0, w1)`, not by line id (from the diff read
  of 2a, 2026-11-14).
  How the two rules are switched off for the baseline is the executor's call, but it
  must not become a production option: the probe may call the split-out functions of
  1c directly.
  Tables to stdout, counts and ids only, each split caption / LRCLIB:
  **P** songs read, left out and why. **A** lines A1 keeps and lines A2 holds: song,
  line, cue start, today's start, new start, heard start, whether in a run of identical
  lines, and the column "inner gap, heard on one side only" (the line has a gap of over
  2 s between two of its words, and its heard words all lie on one side of it). **G** guard lifts. **Z** zero-length words: lines and words before, words re-
  timed, words still under 0.1 s after. **B** lines rule B would aim: the shift, the
  window, and the column "first heard word 2 s+ before the second" (the line's first
  heard word starts 2 s or more before its second). **D** lines rule D would aim: today's start, the heard start, the number of
  pairs, the smallest and largest pair offset, whether in a run of identical lines;
  and, as counts only, the complete untouched lines that are heard and unconfirmed but
  miss the trigger, split by why (first token unheard; some pair under 1.5 s; pairs off
  both ways). **C** lines rule C would try: the stretch and its length, the column "heard shift" (the
  shift rule B measures; blank when the line is not heard, its first token is not
  matched, or its run is not heard in full) and whether it is in a run of identical
  lines (as in Table A); the two columns answer Ken's open calls after the 2d
  self-review: does rule C move a line the transcriber heard on its cue, and does it
  take a twin's audio in a run. **O** every other
  line whose start or end moves more than 0.011 s, with the amount. **V** (sizing only)
  Table A's counts at `HEARD_AGREE_S` 0.5 / 1.0 / 1.5 and `HEARD_MIN_WORDS` 2 / 3.
  `--out` holds `rows.json` (one row per changed line, with lyric text) and is never
  committed.
  `--stage DIR --song ID...` copies those songs' files (`library_regen.song_files`, the
  video, stems and bundle) into a copy library; `--from DIR` names another source
  folder for a song.
  Commit: `feat(scripts): probe of the cue rescue against the heard words`.
- [x] **3b. The run.** `python scripts/cue_heard_probe.py --folder <library> --out
  ~/.pikaraoke/tmp/cue_heard_rescue > report.md`. Paste Tables P, A, G, Z, B, D, C, O,
  V raw into "Report output", no tallies beyond the tables' own, no reading. Read-only
  check: `find <library> -newer <out>/started` prints nothing of this run's. Run again at `e23f0d60` after the 3b2 read (Results log row 13); "Report output" holds that run.
- [x] **3b2. Optional read before the GPU run** (stopped 2026-11-14 on both conditions, Results log row 12; read by Fable 5.2 the same day, tolerance changed to 0.026 s, 3b rerun, Results log row 13) ("Where Fable would help", item 2). If
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
- [ ] **3c2. STOP: review due, before the GPU run** (moved here from 2d by Ken,
  2026-11-14; Phase 3 changes no pipeline code). Hand Ken the line, do not launch it:
  `/code-review medium f2d305fc~1..HEAD` on `pikaraoke/lib/cue_align.py`,
  `pikaraoke/lib/heard_lines.py`, `tests/unit/test_cue_align.py` and
  `tests/unit/test_heard_lines.py`, three finders: correctness (is every A, B or D
  outcome that differs from today confirmed; does `heard_words=None` reproduce today
  apart from rule C and zero-length words; does a refused D retry leave the line
  untouched), simplicity (one heard match per song, one confirm function, no second copy
  of the retry), robustness (empty or malformed heard words, overlapping cues, the last
  line, `duration` None). Ken may widen it to `a24348be~1` and add `token_align.py`,
  `srt_slice_fit.py`, `alignment_capture.py` and `lyric_align.py` with their tests
  (`library_status.py` has no diff). If the review's fixes change `cue_align.py` or
  `heard_lines.py`: re-run 3b, redo 3c's pick and its dry-run, new Results row, before
  3d. Go on to 3d only when Ken says the review is done.
- [ ] **3d. STOP: Ken's GPU run.** Hand him, for Windows (`C:\temp\Github\pikaraoke`,
  branch fetched from remote `vm`): `uv run python scripts/regen_alignment_bundles.py
  D:\Shared\cue-heard-trial --yes`. The library is not touched.

### Phase 4: before against after (Sonnet; after Ken's run)

- [ ] **4a.** `--compare <copy>`: each staged song's new bundle against its source
  bundle. Tables, raw: per rule (the new stats ids), each line's start before, after and
  heard, and for A, B and D lines whether the new start is closer to, within 0.05 s of,
  or further from the heard start; for every D line tried, kept or not, its start and
  end before and after and the previous and next lines' times, so the judge can read
  each one, and whether it is in `guessed_word_line_ids` (the guess pass added words, so
  the re-align timed fewer than the line it replaced; the CPU probe cannot show this,
  the heard-aimed re-align has no saved answer); for rule C lines, Table C's two
  columns; Table O again (other lines that moved, with amounts);
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
   and explained before anything is ruled. From the 3b2 read (Results log row 13), two
   lines got worse because the neighbour was freed: Love Me Now line 53 (now a
   cue-spaced fill) and Love Is an Open Door line 18 (squeezed into 0.16 s); name them
   and put them to Ken's ear.
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
| 3 | 2026-11-14 | plan | Checked the plan's data against the Linux box: code anchors all present; share paths absent; library found at `~/pikaraoke-songs`; trial bundles copied to `~/probes/lrclib-cue-trial` ("Paths on the Linux box"). | this file |
| 4 | 2026-11-14 | 1 | Phase 1 built on `cue_heard_rescue`: 1b `a24348be`, 1c `b51130d7`, 1d `fecebdd2`. 1a: every named anchor present. Differences from the plan's Design: `heard_lines.py` also has `runs_heard(line_toks, heard)` (Decision 9's run flag); `MIN_LINE_COVERAGE`, `INSTANT_WORD_DUR_S` and `_token_expected_times` moved to `token_align.py` (`heard_lines` may not import `cue_align`, and needs the first two as well); `srt_slice_fit.py` imported `_token_expected_times` from `cue_align` and now imports it from `token_align`; stale "cue route doesn't use" comments edited in `alignment_capture.py` and `test_lyric_align.py`. `repace_bad_lines` split into `_Rescue` (per-song state, placed test, one line's retry), `_guess_missing_words` and the driver. New `repace` stats: `n_heard_lines`, `heard_kept_line_ids`, `heard_held_line_ids`, `guard_lifted_line_ids`. Full suite 3608 passed (3596 before 1b); `test_cue_align.py` existing cases pass unedited. Differential fuzz outside the repo, `repace_bad_lines` at `732f5e6c` against HEAD with `heard_words=None`, 4000 random songs: 0 differences in line objects, stats (new keys aside) or `realign` call order; the 4000 held 6546 re-paced, 4818 re-aligned, 2156 crammed, 5032 widened-window and 3525 guessed-word lines. Mutation checks: `confirms` forced False fails the three tests that need rule A; the lift disabled fails the three that need it. No library read. | `a24348be`, `b51130d7`, `fecebdd2` |
| 5 | 2026-11-14 | 2a | Rule B built: `6eef9d5d`. `HEARD_SHIFT_S` (1.5) in `cue_align`. In `_Rescue`: `heard_shift` (the trigger), `heard_aimed_line` (the moved retry: confirm, adopt the window, stats), `retry` (the one-line re-align with the span and more-words checks, shared by `realigned_line` and `heard_aimed_line`), `window(lid, shift)` (no longer records), `adopt(lid, win)` (records the window a line is rescued in: the moved one when rule B keeps the line, else the cue one), `can_realign`. `_Window` gained `singing_end`; `_start_bound` and `start_bounded` take `shift`. New stats `heard_aimed_line_ids` (the trigger held, an aligner was given and the slice was 0.2 s or more) and `heard_aimed_kept_line_ids`; a kept line is also in `realigned_line_ids` and `n_realigned`. Differences from the plan's wording: the trigger tests heard, first token matched and the 1.5 s shift, not the run condition (the rule has none), so a line in a run of identical lines that was not heard in full is tried and cannot be kept (its result is never confirmed); the more-words check sits in the shared `retry`, so 2a2 has to skip it for rule D's complete lines. 13 new tests (`TestHeardAimedRetry`); full suite 3621 passed (3608 before); the existing `test_cue_align.py` cases pass unedited. Differential fuzz as in row 4, `heard_words=None`, 4000 songs: 0 differences in line objects, stats (new keys aside, all empty) or `realign` call order; same counts as row 4 (6546 re-paced, 4818 re-aligned, 2156 crammed, 5032 widened-window, 3525 guessed-word lines). Robustness fuzz, outside the repo (random heard words, stub aligner, 4000 songs): 2418 lines tried, 282 kept, 14492 heard lines; every kept line passes `confirms` as the aligner returned it; 6 of the 282 no longer pass it after the guess pass adds words to them; no line has more than 2 align calls; the set of kept ids is inside the set of tried ids and of `realigned_line_ids`. Mutation checks, each fails the tests named: window unmoved (6), singing end read from unmoved spans (the last-line test), `aimed` unmoved (the heard-before-cue test only: its end is the larger of `cue_end + shift` and the window's aim end, and the aim end is never earlier except under a `duration` clamp), start bound unmoved (2), confirmed not required (the fall-back test), `>` for `>=` (the 1.5 s case), first token not required (the first-unheard test), more-words check dropped (3). No library read. | `6eef9d5d` |
| 6 | 2026-11-14 | 2a, 2a2 | Diff read of 1c and 2a by Fable 5.2 (report relayed by Ken in chat; read-only on `~/pikaraoke-songs`, 177 cue-route bundles, first-pass lines, no aligner). 1c: no path found where output, stats or align-call order differ without heard words. 2a: window, aimed span and the guess pass's window follow the move; the start bound and the singing-end search follow it in part. Counts it reported: rule B would aim 57 lines in 44 songs (47 heard earlier than their cue, 10 later); for 33 of the 47 early ones the duet test in `_start_bound` fired on the move alone; every rule B test had the aimed line last in the song; 2 lines are in a run not heard in full and were still tried; for 8 of the 10 later-heard lines the singing-end search stops at the next line's unmoved cue, which the moved span has already passed; in 27 of the 47 early-heard lines the first heard word starts 2 s or more before the line's second; A1 keeps 27 lines, 18 with an inner gap over 2 s, 8 of those with the heard words all on one side (today those 8 are re-aligned); 1 line is moved past its neighbour (the next line's own re-align is then refused and it becomes a fill; a guessed last word on the moved line comes out zero-length), both reproduced with a stub. Fix `f2d305fc`: the duet test reads the two captions as written (the unmoved cue start), the lead-in stays on the moved start. 3 new tests: a dragged first word cut to the previous line's end when not confirmed as returned (2 cases of one parametrized test: kept untrimmed and listed in `guard_lifted_line_ids` when confirmed) and a heard-aimed line with a line after it (singing end found from the moved span, w1 about 15.6, line 5 unchanged). Mutations: duet test on the moved start fails the 2 new start-bound cases; singing end from unmoved spans fails the last-line test and the line-after test. Differential fuzz as in row 4, 4000 songs: 0 differences; same counts as row 4. Rule D `60789275`: `heard_lines.pair_offsets` (the pairing `confirms` did, shared; signed offsets, None when not heard or too few pairs), in `_Rescue` `aimable` (heard, first token matched, run heard in full), `heard_shift` (B; now through `aimable`, so a line in a run not heard in full is not tried), `whole_shift` (D's trigger: every pair 1.5 s or more apart, all the same way; the shift is heard start minus cue start on the audio clock), `process_whole`, and `heard_aimed_line(shift, *, must_gain, whole)` (D passes `whole`: its own id lists and no more-words check; `retry` takes `must_gain`). New stats `whole_aimed_line_ids`, `whole_aimed_kept_line_ids`; a kept D line is also in `realigned_line_ids` and `n_realigned`. Differences from the plan's wording: the not-confirmed test is not made separately (pairs 1.5 s apart cannot be within `HEARD_AGREE_S`, 1.0 s); B's run skip is Ken's instruction after the read, and the rule text for B has no run condition. 21 new tests (3 for the fix; 18 for 2a2: 14 in `test_cue_align.py`, 4 for `pair_offsets`); full suite 3642 passed (3621 before `f2d305fc`); the cases that predate 2a pass unedited (the test helpers `_song` and `_rescue` of 2a's own class gained a parameter each). Mutations on rule D, each fails the tests named: trigger never fires (5), more-words check kept for D (4), run condition dropped (2, after a first version of the D run test that passed vacuously because the one heard set matched the second twin), first token not required (the rule B first-unheard test), mixed directions accepted (1), one far pair enough (2), threshold 1.0 s (2), D ids written to B's lists (5), result not required to be confirmed (2), kept D line not in `realigned_line_ids` (2), shift measured from the placed start (1, after adding a case placed 1 s after its cue start). Differential fuzz, 4000 songs, `heard_words=None`: 0 differences in line objects, stats (new keys aside, all empty) or `realign` call order; counts as row 4. Robustness fuzz (random heard words, stub aligner, 4000 songs): rule B tried 1862, kept 281 (2418 and 282 before the run skip; the stub's answers come from one random stream, so fewer calls change later answers; with D disabled in the same run: tried 1862, kept 284); rule D tried 2230, kept 413; every D line has exactly one align call; every D line tried was complete, heard with its first token matched, and in a run heard in full; every D line tried and not kept equals its input; every D line kept is `SOURCE_REALIGN` and passes `confirms` as returned except 5, all of which the guess pass added words to; 139 of the 413 kept D lines were given guessed words (the re-align timed fewer words than the line it replaced). No library read by this run. | `f2d305fc`, `60789275` |
| 7 | 2026-11-14 | 2b | Zero-length words built: `65438683`. `_timed_slots(words, toks)` gives one entry per token (a line with a word for every token: by index, a word under `INSTANT_WORD_DUR_S` is an empty slot; else `_assign_in_order`, a zero-length word among the assigned keeps its slot); `_with_guessed_words(obj, toks, slots, after, before, max_word_dur)` takes the slots from its caller and paces from the filled ones; `_guess_missing_words` counts `slots.count(None)` and leaves a line with no filled slot as it is (a fill whose cue is too short for its words) and a line with more words than tokens as before. `n_guessed_words` and `guessed_word_line_ids` include these words; `library_status.py` unchanged (`_cue_fields` reads those two keys; `poor` does not read them). 5 new tests (middle word with room; touching neighbours; first and last word; a partial line's zero-length word left; a fill too short); 2 existing tests changed because the behaviour they pinned is superseded: `test_it_keeps_its_own_words_when_the_realign_times_no_more` (the crammed line's zero-length words are now re-timed in the 0.3 s slot of "ee": 8.0-8.1, 8.1-8.2, 8.2-8.3) and `test_only_the_line_with_a_word_for_every_token_is_crammed` (`guessed_word_line_ids` [4, 5], was [5]). Mutations, each fails the tests named: zero-length words keep their slot (5), no guard for an all-untimed line (1), pace from all words (2), count as before (2), complete lines skipped as before (5), partial lines also drop their zero-length words (18). Differential fuzz against `732f5e6c`, 4000 songs, `heard_words=None`, with a comparator written for this change (every other stats key equal, `realign` call order equal, the first differing line is a complete line with a zero-length word, `n_guessed_words` differs by exactly the zero-length words of those lines, word texts and counts equal): 0 differences. In the 4000: 2222 songs hold such a line, 3337 lines re-timed (4194 words); 3300 of them have no word under 0.05 s afterwards, 4 have fewer, 27 the same number, 6 more (in each, the next line's first word or the window's end falls inside the line's last timed word, and the existing sharing rule narrows that word with the guessed ones); 4 lines after a re-timed line differ (the previous line's end moved). Full suite 3647 passed. No library read. | `65438683` |
| 8 | 2026-11-14 | 2c | Rule C built: `829d02d6`. `GAP_RETRY_MAX_S` (30.0); `MIN_SLICE_S` (0.2, the literal `can_realign` had). In `_Rescue`: `clean_starts` (first-pass clean lines' starts), `free_stretch` (the stretch and the 30 s / 0.2 s / 1.5 s-beyond tests), `gap_retry_line` (the retry and its keep tests), `aligned_line` (the align-and-build step, now shared with `retry`). `process` calls it for a not-placed line whose `realigned_line` returned None. New stats `gap_retry_line_ids`, `gap_retry_kept_line_ids`; a kept line is also in `realigned_line_ids`, `n_realigned` and `cue_inputs.realigns` (each gap retry is one more record: a line can have two). Differences from the plan's wording, as I read it: "that rule B did not aim" is a line not in `heard_aimed` (B tried it), so a line B tried and failed gets no rule C; "the first window" is the padded slice `[w0, w1]` the cue-aimed retry was given; the stretch also has to be at least `MIN_SLICE_S` long. 19 new tests (`TestGapRetry`); 2 existing `align_song` tests changed because they counted the aligner's calls: `test_unplaceable_section_repaces_from_cues` (1 + 4 became 1 + 4 x 2, and the two gap-retry ids) and `test_a_failed_realign_is_recorded_as_none` (`realigns` line ids [0, 1, 2, 3] became [0, 0, 1, 1, 2, 2, 3, 3], the second of each over (0.0, 8.0)). Mutations, each fails the tests named: C never fires (12), no 30 s cap (1), any stretch reaches (2), reach needs both sides (11), reach 0 s (2), untimed tokens allowed (1), unclean allowed (1), past the next line allowed (1), no cut to the stretch start (1), a fill starts the stretch (3), rule B lines retried too (1), placed lines retried too (11), duration ignored (3), kept line not in `realigned_line_ids` (10), kept not recorded (4), tried not recorded (7), slice not the stretch (8); one survived (the audio's end used even when a clean line follows), a test was added for it and it now fails (1). Differential fuzz as in row 7 with rule C switched off in the new code, 4000 songs: 0 differences; same counts as row 7. Rule C on against off, 4000 songs, `heard_words=None`, a stub aligner whose answer depends only on the call (line, window): rule C tried 5812 lines, kept 540; 493 songs differ; every tried line made exactly 2 align calls and no line more than 2; the first differing line of each song is a kept line, or (5 songs) an earlier line whose guessed words end where a kept line now starts; 15 lines after a kept line differ; every kept line has a timed word for every token, is `_line_is_clean`, lies between the end of the last non-fill line before it and the start of the next clean first-pass line (or `duration`), in a stretch of at most 30 s; no line is in both `heard_aimed_line_ids` and `gap_retry_line_ids`. Full suite 3666 passed. No library read. | `829d02d6` |
| 9 | 2026-11-14 | 2d | End of Phase 2 checks at `829d02d6`. Full suite 3666 passed. `pre-commit` clean on the 9 Python files changed since `a24348be~1` (`alignment_capture.py`, `cue_align.py`, `heard_lines.py`, `srt_slice_fit.py`, `token_align.py`, `lyric_align.py`, and the tests `test_cue_align.py`, `test_heard_lines.py`, `test_lyric_align.py`); `library_status.py` is unchanged since `dev`. `graphify update .` run. Fuzz at HEAD, 4000 songs each: differential with rule C off against `732f5e6c` (comparator as in row 7): 0 differences; rule C on against off: as in row 8; robustness with random heard words: rule B tried 1862, kept 287, rule D tried 2230, kept 396, 268 of those 396 were given guessed words by the guess pass (the stub drops 15% of a result's words at random), 9 kept lines no longer pass `confirms` after the guess pass and all 9 were given guessed words, every D line has exactly one align call, every D line tried and not kept equals its input; the same with overlapping cues added (16017 overlapping cue pairs in the 4000 songs): rule B tried 2016, kept 349, rule D tried 2577, kept 529, no crash, every word ends no earlier than it starts, the id lists keep their subset relations. Self-review on the three axes, what it turned up. Correctness: rule C does not look at the heard words except to leave out a line rule B tried, so a line the transcriber heard on its cue whose cue-aimed retry failed can be moved by rule C to anywhere in the stretch (at most 30 s); a bad line in a run of identical lines gets rule C without the run test rule A, B and D have, and can take a neighbouring twin's audio from the stretch; a rule D result may time fewer words than the line it replaces (no more-words check; the guess pass fills the rest). Simplicity: `heard_aimed_line` carries two flags (`must_gain`, `whole`) for the two rules sharing it; `process` is 35 lines; the three retries (cue-aimed, heard-aimed, gap) share `aligned_line`, `start_bounded` and the keep tests are not shared (rule C has its own set, by design). Robustness: a bad line that neither retry keeps now costs a second align call over a stretch of up to 30 s (two calls for every line in a song where nothing aligns); with `duration` None and no clean line after, rule C does not run. From the diff read and not changed (3a columns and Table B/A cover them): the singing-end search of a later-heard line stops at the next line's unmoved cue (8 of the 10 library lines Fable counted); a line moved past its neighbour (1 library line) refuses the neighbour's own re-align and gets a guessed last word that comes out zero-length. | `829d02d6` |
| 10 | 2026-11-14 | plan | Ken, after the 2d report and the three open calls of row 9 (rule C on lines heard on their cue; rule C in a run of identical lines; rule D replacing a line with one that times fewer words), asked for columns that measure them and for the review before the GPU run instead of at 2d. Edits: Table C gains "heard shift" and "in a run of identical lines" (3a); the "timed fewer words" count is not a 3a column, because rule D's heard-aimed re-align has no saved answer in a bundle, so it is in 4a as membership of `guessed_word_line_ids` for every D line tried, and 4a gives rule C lines Table C's two columns; new step 3c2 (STOP: review due, `/code-review medium f2d305fc~1..HEAD` on `cue_align.py`, `heard_lines.py` and their tests), before 3d; 2d notes the move; Status line. No code changed. | this file |
| 11 | 2026-11-14 | 3a | Probe built: `scripts/cue_heard_probe.py` and `tests/unit/test_cue_heard_probe.py`, `f3edd413`; fix `a0a10911`. Each cue-route bundle (`cue_inputs` and `transcribe_words` not None; caption = origin `srt` or `movie_srt`, LRCLIB = origin `lrclib_srt`) is replayed twice, rescue then `snap_line_edges` as the stage runs it (`doubted_sources={SOURCE_REALIGN}`): the baseline (`heard_words=None`) and the new run (the song's `transcribe_words`, every rule). The baseline switches rule C and the zero-length rule off by patching `_Rescue.gap_retry_line` and `cue_align._timed_slots` inside a context manager in the probe (`repace_bad_lines` gained no option); the baseline must equal `output_line_timings` (start, end, word count) within 0.011 s or the song is left out and named in Table P. Saved re-aligns answer a `realign` call by `(line, w0, w1)` within 1e-6; a call with no saved answer returns None and is recorded as unanswered (`Answered` column). Snap stem: `dereverb/` when `joint_stats.dereverb.succeeded`, else `vocal/`; the stem is decoded to a 44.1 kHz stereo WAV as `LoadVocalFromM4aStage` does, the envelope and duration (`_wav_duration`) are read from that, cached under `<out>/env`. Decoding the m4a straight to 16 kHz mono (first try, scratch script) left 20 of 177 songs out; the WAV route left 16. Differences from the plan's wording: Table D's not-aimed counts have three more reasons than the three named ("run not heard in full", "too few pairs", "trigger held, not aimed") so the counts account for every candidate; Tables B, D and C gain `Answered` and `Kept` columns and Table P a `Why` column; Table Z lists every kept line that had a word for every token with some zero-length, as the baseline rescue left it, first-pass or re-aligned (first version listed first-pass lines only: found by a read of the first run's Table O, whose 82 lines fell to 51 after the fix); a file with no YouTube id is named by its whole stem in the tables, and `--song` takes an id or a whole stem (the library has such files: Rent, The Last Five Years, Flight of the Conchords); `--from` is repeatable and a song is taken from the first `--from` folder that has it, else from `--folder`. The 3c pick is not a probe option: `rows.json` holds every table row (with lyric text, never committed) and the pick is counted from it. 50 tests (made-up bundles, a silent envelope, no audio); mutation checks, each fails the tests named: rule C not patched out (1), zero-length not patched out (1), answer by line only (1), unanswered recorded as answered (1), de-reverb stem ignored (1), Table C heard shift blanked (1), run flag false (1), Table V thresholds not applied (1), baseline given heard words (1), Table O includes rule lines (1), cache never stale (1), Table Z from first-pass lines (1), label always short (1), staging by id only (1), and five that first survived and got tests (tolerance 0.03, `--from` order, Table B window from the last call, inner-gap test, Table D reason order). Full suite 3716 passed (3666 before 3a); pre-commit clean on both files; `graphify update .` run. | `f3edd413`, `a0a10911` |
| 12 | 2026-11-14 | 3b | Probe run over `~/pikaraoke-songs` at `a0a10911` (`--out ~/.pikaraoke/tmp/cue_heard_rescue`; report in "Report output", `rows.json` and `report.md` in `<out>`). 177 bundles read (149 caption, 28 LRCLIB); 161 replayed; 16 left out, all caption, none for a missing or unreadable stem: 11 differ by 0.025 s on one line edge (one envelope frame), 5 by 0.061, 0.167, 0.190, 0.277 and 2.993 s. The cause of the one-frame cases is not established. Rows: Table A 58, G 303, Z 1008, B 54, D 20, C 86, O 51. Table O: 51 lines, 30 over 0.3 s, largest 3.236 s; for each of those 30 a line directly before or after it is in Tables A, G, Z, B, D or C (scratch count over `rows.json`: 25 move the end only, 1 the start only, 4 both). The first run, before `a0a10911`, is discarded: Table Z had 857 rows, Table O 82 lines of which 38 over 0.3 s, and songs with no YouTube id were labelled `?`; Table P was the same 16. Read-only check: `find ~/pikaraoke-songs -newer ~/.pikaraoke/tmp/cue_heard_rescue/started` printed nothing. **STOP at 3b2 on both of its conditions** (Table P leaves out more than 10 songs; Table O has a line moving more than 0.3 s). 3c, 3c2 and 3d not started. | this file, `<out>` |
| 13 | 2026-11-14 | 3b2, 3b | Read of Tables P and O by Fable 5.2 (report relayed by Ken in chat; scratch replays from the probe's cached envelopes, library and `<out>` untouched, probe not rerun). **Table P, first run (16 out):** 14 songs the rescue reproduces exactly, every mismatched edge being one the edge snap moved: in 11 the snap landed one frame over; in 3 (Eminem, Sugalumps, Tribute) the snap fired here and not in the bundle, or the reverse, on a single edge. 2 songs (both The Last Five Years) have a library stem about 3.2 s shorter than the audio the bundle was made from; the last line's saved window runs past the stem's end, so its re-align has no answer. The envelope decoded here is not bit-identical to the bundle's (whether the lossy m4a copy of the stem or a different ffmpeg is not established); adding 0.1 dB of noise to the envelope moves an edge in about half the songs. No mismatch lies between 0.025 and 0.061 s. **Table O, first run (51 lines):** 46 lines the rescue left unchanged, only the end moved (the snap stretches an end no further than 0.1 s before the next line's first word, and the next line is a Table A, G or Z line whose start moved: 25 Z, 21 A or G); 5 lines (all among the 30) whose own re-align came out differently because the line before moved (four after a guard lift, one after an A1 keep): Rent "I Should Tell You" lines 25 and 40 and Hiphopopotamus line 35 now keep a re-align that was cut off; Love Me Now line 53 becomes a cue-spaced fill; Love Is an Open Door line 18 is squeezed into 0.16 s. The new replay makes no unanswered aligner call outside Tables B, D and C; all 160 tries in B, D and C had no saved answer, so the CPU replay shows no effect of those three rules. **Change:** `TOLERANCE_S` 0.011 to 0.026 s in `scripts/cue_heard_probe.py` (Fable's recommendation, passed on by Ken), `e23f0d60`; Table O keeps its own 0.011 s threshold (`MOVED_S`, both replays read the same envelope), as the plan words it; the test that pins the tolerance now checks 0.025 s inside and 0.027 s outside, and a Table O test checks that 0.02 s is listed; mutation checks (tolerance back to 0.011, to 0.03, Table O using the tolerance) each fail one test. 50 tests pass; pre-commit clean on both files; `graphify update .` run. **Rerun** at `e23f0d60` (`python scripts/cue_heard_probe.py --folder ~/pikaraoke-songs --out ~/.pikaraoke/tmp/cue_heard_rescue > report.md`; report in "Report output"): 177 read, 172 replayed (144 caption, 28 LRCLIB), 5 left out, all caption, none for a missing or unreadable stem: Eminem line 69 start off by 0.277 s, Sugalumps line 20 end 0.190 s, Tribute line 34 end 0.167 s, The Last Five Years "A Miracle Would Happen & When You Come Home to Me" line 92 end 2.993 s, "Climbing Uphill" line 75 end 0.061 s; the same five songs the read predicted. Rows: Table A 63, G 320, Z 1058, B 54, D 20, C 94, O 54 (first run: 58, 303, 1008, 54, 20, 86, 51). Against the first run (scratch comparison of the two `rows.json`): no row removed, 83 added, B and D unchanged, no Table O line changed its amount. Table O: 54 lines, 31 over 0.3 s, largest 3.236 s; the 3 new lines are Bad Habits line 44 (0.553 s), Cast Along the Way line 42 (0.203 s), The Philosopher Kings Hurts line 10 (0.284 s), each end only, each directly before a Table Z, G or A line. Scratch copy of the read's per-line attribution script (outside the repo) over the new run: of the 54 Table O lines, 49 have the rescue's output unchanged and only the end moved (next line in Table Z 26, A 15, G 8; for 5 of them the next line's first-pass start is unchanged and its final start moved, and the zero-length rule alone reproduces the move), and 5 have their own re-align different (the five named above). B, D and C: 168 tries (B 54, D 20, C 94), all without a saved answer, none kept. One unanswered call outside B, D and C, which is also unanswered in the baseline. Read-only check: `find ~/pikaraoke-songs -newer ~/.pikaraoke/tmp/cue_heard_rescue/started` printed nothing. | `e23f0d60`, this file, `<out>` |


## Report output

### Phase 3b: CPU replay of the library

`python scripts/cue_heard_probe.py --folder ~/pikaraoke-songs --out ~/.pikaraoke/tmp/cue_heard_rescue > report.md`
at `e23f0d60` (2026-11-14), unedited. The first run, at `a0a10911`, is summarised in Results log row 12.

### Table P: songs read, replayed and left out
A song is left out when its stem is missing or unreadable, or its baseline replay differs from the bundle's output_line_timings by more than 0.026 s.

| Src | Read | Replayed | Left out |
|---|---|---|---|
| caption | 149 | 144 | 5 |
| LRCLIB | 28 | 28 | 0 |

| Src | Song | Why |
|---|---|---|
| caption | Eminem - The Real Slim Shady ( eJO5HU_7_1w | baseline replay differs: line 69 start off by 0.277 s |
| caption | Flight of the Conchords (2007) - Sugalumps | baseline replay differs: line 20 end off by 0.190 s |
| caption | Tenacious D - Tribute _lK4cX5xGiQ | baseline replay differs: line 34 end off by 0.167 s |
| caption | The Last Five Years (2014) - A Miracle Would Happen & When You Come Home to Me | baseline replay differs: line 92 end off by 2.993 s |
| caption | The Last Five Years (2014) - Climbing Uphill | baseline replay differs: line 75 end off by 0.061 s |

### Table A: lines rule A1 keeps and rule A2 holds
Starts in seconds on the cue clock (cue) and the audio clock (the rest). Run: in a run of identical lines. Gap one side: an inner gap over 2 s with every heard word on one side of it.

caption: 46 lines in 36 songs; LRCLIB: 17 lines in 11 songs

| Src | Song | Line | Rule | Cue | Today | New | Heard | Run | Gap one side |
|---|---|---|---|---|---|---|---|---|---|
| caption | Adele - Someone Like You hLQl3WQQoQ0 | 32 | A2 | 157.861 | 157.242 | 157.421 | 155.910 |  |  |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 0 | A2 | 10.324 | 10.590 | 10.332 | 9.460 |  |  |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 55 | A2 | 207.694 | 208.372 | 208.309 | 206.840 |  |  |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 55 | A1 | 179.690 | 179.718 | 179.410 | 179.180 | yes |  |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 12 | A2 | 53.312 | 53.387 | 53.525 | 52.210 |  |  |
| caption | Backstreet Boys - Incomplete WVe80iZtlYU | 6 | A2 | 65.272 | 64.675 | 64.562 | 63.510 |  |  |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 37 | A2 | 167.641 | 166.855 | 167.573 | 168.020 |  |  |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 2 | A1 | 17.999 | 18.702 | 18.375 | 13.984 |  |  |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 4 | A2 | 20.187 | 20.200 | 20.871 | 16.980 |  |  |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 44 | A2 | 95.808 | 97.125 | 97.975 | 96.540 |  |  |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 89 | A2 | 201.514 | 201.768 | 201.768 | 201.860 |  |  |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 62 | A1 | 141.127 | 141.094 | 139.964 | 140.780 |  |  |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 32 | A2 | 175.789 | 175.573 | 176.562 | 176.160 |  |  |
| caption | Colbie Caillat - Bubbly (Offic AWGqoCNbsvM | 27 | A2 | 88.838 | 88.750 | 86.680 | 86.760 |  |  |
| caption | Céline Dion - Ashes (Deadpool  CX11yw6YL1w | 1 | A2 | 21.187 | 20.950 | 20.889 | 21.024 |  |  |
| caption | Céline Dion - Ashes (Deadpool  CX11yw6YL1w | 21 | A2 | 181.181 | 181.125 | 181.125 | 178.350 | yes |  |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 53 | A2 | 258.840 | 258.569 | 256.740 | 257.160 |  |  |
| caption | Flight of the Conchords (2007) - Carol Brown | 47 | A1 | 152.696 | 153.834 | 151.946 | 154.220 |  | yes |
| caption | John Legend - All of Me 450p7goxZqg | 46 | A2 | 214.559 | 214.525 | 214.525 | 213.780 |  |  |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 24 | A2 | 121.447 | 121.102 | 120.495 | 119.520 |  |  |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 3 | A1 | 9.782 | 9.575 | 9.575 | 9.780 |  | yes |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 36 | A1 | 127.130 | 127.276 | 125.582 | 126.140 |  |  |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 14 | A2 | 38.690 | 38.475 | 38.626 | 38.520 |  |  |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 0 | A2 | 18.818 | 18.710 | 18.568 | 17.030 |  |  |
| caption | KPop Demon Hunters (2025) - Free | 13 | A2 | 42.083 | 42.098 | 42.089 | 40.680 |  |  |
| caption | KPop Demon Hunters (2025) - Free | 42 | A2 | 124.499 | 124.378 | 124.378 | 124.480 |  |  |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 0 | A2 | 18.208 | 17.467 | 17.438 | 15.680 |  |  |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 9 | A1 | 51.208 | 50.625 | 50.625 | 48.280 |  |  |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 27 | A2 | 135.458 | 134.800 | 135.038 | 132.940 |  |  |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 73 | A1 | 155.366 | 155.065 | 157.463 | 157.560 | yes |  |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 62 | A1 | 231.397 | 231.113 | 231.300 | 227.860 |  |  |
| caption | Rent (2005) - Another Day | 51 | A1 | 183.345 | 184.418 | 181.751 | 182.040 |  |  |
| caption | The Last Five Years (2014) - Shiksa Goddess | 61 | A1 | 230.456 | 230.475 | 226.764 | 227.160 |  |  |
| caption | The Lion King (1994) - Can You 25QyCxVkXwQ | 21 | A2 | 58.263 | 58.150 | 57.953 | 57.020 |  |  |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 72 | A1 | 182.493 | 182.575 | 181.743 | 182.080 |  |  |
| caption | The Philosopher Kings - Cry EUW0eDhKoxw | 10 | A2 | 79.192 | 79.800 | 79.727 | 78.550 |  |  |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 11 | A2 | 92.492 | 91.353 | 91.637 | 90.440 |  |  |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 26 | A2 | 185.852 | 185.900 | 185.909 | 185.664 |  |  |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 37 | A1 | 237.237 | 236.098 | 234.162 | 234.846 | yes |  |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 31 | A1 | 129.062 | 128.625 | 128.625 | 128.720 | yes | yes |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 13 | A2 | 41.128 | 40.926 | 40.721 | 39.690 |  |  |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 35 | A2 | 124.270 | 124.036 | 124.000 | 123.020 |  |  |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 3 | A1 | 41.415 | 40.691 | 36.765 | 37.140 |  |  |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 62 | A1 | 261.361 | 260.467 | 260.467 | 260.620 |  | yes |
| caption | ZAYN & Zhavia Ward - A Whole N rg_zwK_sSEY | 53 | A1 | 203.766 | 204.760 | 202.650 | 203.170 | yes |  |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 42 | A2 | 151.200 | 151.608 | 151.483 | 150.420 |  |  |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 29 | A2 | 133.370 | 133.701 | 132.586 | 132.580 |  |  |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 5 | A1 | 25.036 | 24.288 | 21.740 | 25.160 |  | yes |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 15 | A1 | 46.120 | 45.975 | 46.370 | 46.620 | yes |  |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 16 | A1 | 46.870 | 46.225 | 47.230 | 48.040 | yes |  |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 17 | A1 | 47.600 | 47.455 | 48.530 | 48.820 | yes |  |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 35 | A1 | 79.220 | 78.700 | 77.922 | 78.420 | yes |  |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 36 | A1 | 80.880 | 80.735 | 79.410 | 79.800 | yes |  |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 42 | A1 | 98.960 | 99.090 | 99.090 | 99.060 | yes |  |
| LRCLIB | Ingrid Michaelson - The Way I  Vh74KE3o4Bs | 4 | A2 | 48.693 | 49.125 | 49.125 | 49.216 |  |  |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 17 | A2 | 53.530 | 53.338 | 51.360 | 52.280 |  |  |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 10 | A2 | 24.510 | 25.050 | 25.030 | 22.580 |  |  |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 8 | A2 | 39.310 | 39.650 | 39.520 | 39.744 |  |  |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 11 | A1 | 62.230 | 62.600 | 60.120 | 62.480 |  | yes |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 35 | A2 | 69.845 | 69.965 | 69.875 | 68.680 |  |  |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 33 | A2 | 119.114 | 118.950 | 119.034 | 117.400 |  |  |
| LRCLIB | The Outsiders (2024) - Stay Go XzbHPqULtdA | 22 | A1 | 117.486 | 117.500 | 117.500 | 118.080 |  | yes |
| LRCLIB | The Outsiders (2024) - Stay Go XzbHPqULtdA | 45 | A1 | 217.926 | 219.150 | 219.150 | 219.560 |  | yes |

### Table G: starts the guard lift freed of the previous line
Previous end: the previous line's end in the new replay.

caption: 282 lines in 99 songs; LRCLIB: 38 lines in 18 songs

| Src | Song | Line | Cue | Today | New | Heard | Previous end |
|---|---|---|---|---|---|---|---|
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 18 | 82.379 | 82.350 | 82.350 | 82.200 | 81.895 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 19 | 84.541 | 84.206 | 83.706 | 84.500 | 84.475 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 20 | 87.040 | 87.050 | 87.050 | 86.860 | 86.496 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 49 | 218.816 | 218.775 | 218.775 | 219.040 | 218.566 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 33 | 113.138 | 112.628 | 112.556 | 112.450 | 112.628 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 55 | 188.871 | 188.509 | 188.059 | 189.100 | 188.509 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 61 | 206.592 | 206.509 | 206.120 | 206.820 | 206.509 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 25 | 102.317 | 102.875 | 102.875 | 102.400 | 102.775 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 26 | 104.782 | 104.860 | 104.625 | 104.880 | 105.170 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 45 | 171.700 | 172.675 | 171.872 | 172.640 | 172.203 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 46 | 175.500 | 176.200 | 176.200 | 176.060 | 175.766 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 47 | 179.333 | 180.025 | 180.025 | 180.040 | 179.925 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 5 | 20.577 | 20.694 | 20.169 | 20.980 | 20.694 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 16 | 46.948 | 46.975 | 46.975 | 47.000 | 46.778 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 17 | 49.497 | 49.525 | 49.525 | 49.568 | 49.180 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 18 | 52.467 | 52.425 | 52.425 | 52.480 | 52.269 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 25 | 66.727 | 66.800 | 66.800 | 66.860 | 66.700 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 37 | 95.949 | 95.897 | 95.451 | 96.120 | 95.897 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 46 | 124.251 | 124.706 | 124.023 | 124.440 | 124.023 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 68 | 165.869 | 165.526 | 165.371 | 165.520 | 165.526 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 32 | 118.716 | 118.604 | 118.244 | 118.300 | 118.604 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 39 | 143.819 | 144.275 | 144.275 | 144.180 | 143.991 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 48 | 172.242 | 172.410 | 171.770 | 172.340 | 172.410 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 59 | 185.856 | 186.125 | 186.125 | 186.040 | 185.775 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 1 | 6.030 | 5.863 | 5.746 | 5.460 | 5.863 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 2 | 7.830 | 8.066 | 7.296 | 8.060 | 8.066 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 44 | 203.288 | 203.685 | 202.754 | 203.552 | 203.685 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 80 | 336.833 | 337.210 | 336.575 | 337.120 | 337.130 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 85 | 347.309 | 347.070 | 347.350 | 347.040 | 347.250 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 87 | 349.590 | 349.720 | 349.425 | 349.780 | 349.720 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 19 | 57.149 | 57.614 | 56.803 | 57.140 | 57.294 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 36 | 95.697 | 95.787 | 95.481 | 95.920 | 95.587 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 63 | 140.315 | 140.737 | 140.519 | 140.160 | 140.737 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 78 | 176.900 | 177.050 | 177.050 | 177.020 | 176.950 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 48 | 175.079 | 175.633 | 174.875 | 175.180 | 175.193 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 10 | 58.567 | 58.675 | 58.675 | 58.980 | 58.190 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 13 | 70.464 | 70.700 | 70.700 | 70.360 | 70.258 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 29 | 134.081 | 133.882 | 133.700 | 133.170 | 133.882 |
| caption | Backstreet Boys - Larger Than  MEb2CecR11I | 24 | 162.100 | 161.743 | 161.150 | 162.080 | 161.743 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 57 | 163.934 | 164.450 | 164.450 | 164.260 | 164.227 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 71 | 199.725 | 200.162 | 199.370 | 200.040 | 200.162 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 82 | 223.382 | 223.527 | 223.027 | 222.880 | 224.822 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 39 | 177.138 | 178.039 | 176.396 | 178.520 | 178.039 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 9 | 18.701 | 19.308 | 18.808 | 19.220 | 19.228 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 11 | 22.786 | 23.768 | 23.183 | 23.660 | 23.438 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 18 | 39.883 | 40.975 | 40.180 | 41.180 | 40.935 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 24 | 56.663 | 57.555 | 57.500 | 57.500 | 57.555 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 36 | 90.489 | 91.425 | 91.425 | 91.400 | 91.325 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 37 | 93.853 | 94.286 | 94.270 | 95.220 | 94.286 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 68 | 185.822 | 186.149 | 186.063 | 186.640 | 186.149 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 23 | 52.928 | 52.391 | 52.328 | 52.400 | 52.391 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 53 | 119.274 | 118.698 | 118.674 | 118.920 | 118.698 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 16 | 56.297 | 56.242 | 55.913 | 56.320 | 56.242 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 17 | 57.368 | 57.373 | 57.325 | 57.360 | 57.373 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 22 | 64.973 | 65.050 | 65.025 | 65.120 | 65.050 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 39 | 98.283 | 98.457 | 97.750 | 98.460 | 98.457 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 41 | 101.175 | 100.950 | 100.950 | 100.940 | 100.850 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 43 | 103.639 | 103.367 | 103.475 | 103.460 | 103.367 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 47 | 110.172 | 110.457 | 109.638 | 110.280 | 110.197 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 57 | 127.524 | 127.386 | 126.990 | 127.480 | 127.386 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 68 | 172.081 | 172.100 | 172.100 | 171.510 | 171.547 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 78 | 199.715 | 200.473 | 199.575 | 200.240 | 200.333 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 79 | 201.429 | 200.953 | 200.895 | 200.820 | 201.031 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 88 | 217.066 | 216.770 | 216.532 | 216.300 | 216.665 |
| caption | Britney Spears - (You Drive Me Q4VK9_CfOLQ | 25 | 98.940 | 99.325 | 98.724 | 99.420 | 99.162 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 2 | 9.660 | 10.350 | 10.207 | 10.112 | 10.270 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 3 | 11.070 | 11.470 | 11.475 | 11.620 | 11.227 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 10 | 27.450 | 27.810 | 27.377 | 27.760 | 27.810 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 49 | 175.260 | 175.575 | 175.575 | 175.220 | 175.361 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 50 | 177.060 | 177.400 | 177.400 | 177.100 | 177.127 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 6 | 43.562 | 42.919 | 42.466 | 42.860 | 42.919 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 24 | 120.808 | 121.099 | 120.371 | 121.380 | 121.099 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 41 | 188.487 | 188.451 | 188.439 | 188.660 | 188.451 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 26 | 108.808 | 108.736 | 108.225 | 108.680 | 108.736 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 47 | 108.399 | 108.419 | 107.799 | 107.960 | 108.419 |
| caption | Christina Aguilera - Genie In  kIDWgqDBNXA | 38 | 118.163 | 117.800 | 117.224 | 118.120 | 117.800 |
| caption | Christina Aguilera - Genie In  kIDWgqDBNXA | 67 | 197.563 | 196.884 | 196.863 | 197.020 | 196.884 |
| caption | Christina Aguilera - Reflectio RNprQYHenNI | 31 | 132.700 | 133.100 | 132.652 | 132.980 | 132.911 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 14 | 84.440 | 84.750 | 83.773 | 84.160 | 84.430 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 16 | 91.640 | 91.470 | 90.972 | 91.460 | 91.470 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 32 | 162.480 | 162.420 | 161.812 | 162.460 | 162.420 |
| caption | Ed Sheeran - Happier iWZmdoY1aTE | 7 | 49.299 | 49.348 | 48.684 | 49.480 | 49.348 |
| caption | Ed Sheeran - Perfect 2Vv-BfVoq4g | 33 | 167.835 | 168.725 | 168.725 | 168.680 | 168.379 |
| caption | Ed Sheeran - Perfect 2Vv-BfVoq4g | 44 | 227.728 | 228.482 | 228.625 | 228.460 | 228.482 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 58 | 176.343 | 176.271 | 175.931 | 176.360 | 176.271 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 9 | 50.616 | 49.690 | 49.566 | 50.300 | 49.690 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 20 | 73.172 | 72.830 | 72.492 | 72.940 | 72.830 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 41 | 123.856 | 123.416 | 123.416 | 123.360 | 122.952 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 63 | 174.507 | 174.036 | 174.175 | 174.180 | 174.036 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 3 | 13.600 | 14.596 | 14.579 | 14.560 | 14.596 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 17 | 58.166 | 58.543 | 58.341 | 58.680 | 58.543 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 37 | 99.700 | 100.123 | 99.585 | 100.100 | 100.123 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 55 | 138.333 | 139.140 | 138.425 | 138.780 | 139.080 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 64 | 157.266 | 157.640 | 157.301 | 157.640 | 157.640 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 65 | 159.600 | 159.781 | 159.525 | 159.800 | 159.781 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 80 | 189.533 | 190.426 | 190.300 | 189.660 | 190.200 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 81 | 191.266 | 191.626 | 191.181 | 191.640 | 191.648 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 89 | 208.500 | 208.786 | 208.745 | 208.780 | 208.786 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 90 | 210.633 | 211.175 | 210.648 | 211.120 | 211.175 |
| caption | Flight of the Conchords (2007) - Bowie | 37 | 138.431 | 138.749 | 138.800 | 138.840 | 138.749 |
| caption | Flight of the Conchords (2007) - Bowie | 39 | 143.973 | 144.425 | 144.425 | 144.600 | 144.050 |
| caption | Flight of the Conchords (2007) - Carol Brown | 40 | 135.211 | 135.944 | 135.579 | 135.920 | 135.944 |
| caption | Flight of the Conchords (2007) - Carol Brown | 51 | 171.648 | 172.314 | 172.275 | 172.380 | 172.314 |
| caption | Flight of the Conchords (2007) - Carol Brown | 61 | 203.413 | 203.838 | 203.301 | 203.940 | 204.185 |
| caption | Flight of the Conchords (2007) - Carol Brown | 64 | 208.585 | 209.725 | 209.250 | 209.360 | 209.458 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 54 | 122.784 | 123.318 | 123.250 | 123.380 | 123.318 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 57 | 128.659 | 129.098 | 128.579 | 129.080 | 129.098 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 10 | 27.927 | 28.179 | 27.911 | 28.200 | 28.179 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 34 | 94.385 | 95.468 | 95.009 | 94.980 | 94.946 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 8 | 23.666 | 24.284 | 24.001 | 24.280 | 24.112 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 9 | 25.735 | 26.504 | 25.560 | 26.360 | 26.321 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 14 | 38.548 | 38.864 | 38.743 | 38.880 | 38.864 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 48 | 145.421 | 145.527 | 145.246 | 145.480 | 145.527 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 50 | 149.659 | 150.132 | 150.125 | 150.160 | 150.132 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 30 | 72.202 | 72.610 | 72.098 | 72.620 | 72.610 |
| caption | Flight of the Conchords (2007) - Robots | 1 | 1.571 | 1.900 | 1.718 | 1.800 | 1.800 |
| caption | Flight of the Conchords (2007) - Robots | 14 | 29.197 | 29.650 | 29.650 | 29.500 | 29.400 |
| caption | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | 17 | 51.231 | 51.500 | 51.500 | 51.480 | 51.340 |
| caption | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | 24 | 70.981 | 71.325 | 71.325 | 71.360 | 70.783 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 37 | 142.280 | 142.390 | 141.990 | 141.820 | 142.390 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 38 | 144.640 | 144.880 | 144.880 | 144.880 | 144.880 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 14 | 83.131 | 83.150 | 83.150 | 83.100 | 83.050 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 52 | 221.959 | 221.401 | 220.901 | 221.360 | 221.716 |
| caption | Jung Kook 정국 - Standing Next t 6q0JnftlH-I | 7 | 54.788 | 55.101 | 54.216 | 54.840 | 54.861 |
| caption | Jung Kook 정국 - Standing Next t 6q0JnftlH-I | 17 | 79.110 | 78.741 | 78.500 | 79.000 | 78.741 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 10 | 24.900 | 24.410 | 24.550 | 24.400 | 24.410 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 15 | 36.049 | 36.410 | 35.309 | 35.840 | 36.410 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 33 | 80.399 | 80.620 | 80.075 | 80.240 | 80.620 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 59 | 148.920 | 149.049 | 148.180 | 148.280 | 149.049 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 63 | 156.911 | 157.129 | 156.525 | 156.810 | 157.129 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 67 | 165.499 | 165.269 | 165.025 | 165.220 | 165.269 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 8 | 29.353 | 29.300 | 29.300 | 29.460 | 28.590 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 27 | 91.827 | 91.650 | 91.650 | 91.840 | 91.550 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 45 | 158.963 | 159.320 | 158.881 | 159.160 | 159.320 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 2 | 35.788 | 35.686 | 35.641 | 35.860 | 35.686 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 10 | 62.139 | 62.100 | 62.100 | 62.100 | 61.909 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 18 | 82.924 | 83.129 | 82.925 | 82.880 | 82.909 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 22 | 97.754 | 97.645 | 97.700 | 97.260 | 97.645 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 46 | 170.088 | 170.392 | 170.175 | 170.180 | 170.212 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 47 | 174.888 | 174.850 | 174.850 | 174.440 | 174.381 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 50 | 185.248 | 185.188 | 184.975 | 184.540 | 185.188 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 52 | 191.605 | 191.448 | 191.200 | 191.296 | 191.448 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 72 | 266.235 | 266.226 | 265.578 | 265.730 | 266.226 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 18 | 47.512 | 47.246 | 47.025 | 47.380 | 47.246 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 36 | 81.308 | 81.150 | 81.150 | 81.460 | 80.712 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 6 | 35.168 | 34.908 | 34.680 | 34.900 | 34.908 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 29 | 100.366 | 100.450 | 100.450 | 100.440 | 100.350 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 28 | 98.404 | 98.195 | 97.851 | 98.600 | 98.195 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 29 | 100.807 | 100.871 | 100.900 | 100.920 | 100.871 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 52 | 173.691 | 173.628 | 173.088 | 173.700 | 173.628 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 53 | 176.192 | 176.408 | 176.175 | 175.840 | 176.058 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 56 | 185.501 | 185.528 | 185.175 | 185.660 | 185.528 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 66 | 210.732 | 210.750 | 210.750 | 210.900 | 210.311 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 76 | 235.728 | 235.321 | 235.005 | 235.680 | 235.321 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 90 | 267.827 | 267.808 | 267.334 | 268.040 | 267.808 |
| caption | KPop Demon Hunters (2025) - Free | 15 | 45.628 | 45.569 | 45.600 | 45.660 | 45.569 |
| caption | KPop Demon Hunters (2025) - Free | 38 | 114.113 | 114.152 | 114.150 | 114.060 | 114.152 |
| caption | KPop Demon Hunters (2025) - Free | 41 | 121.371 | 121.350 | 121.350 | 121.184 | 120.892 |
| caption | KPop Demon Hunters (2025) - How It's Done | 17 | 44.127 | 44.134 | 44.038 | 44.260 | 44.134 |
| caption | KPop Demon Hunters (2025) - How It's Done | 34 | 95.261 | 96.067 | 95.212 | 95.940 | 95.767 |
| caption | KPop Demon Hunters (2025) - How It's Done | 39 | 110.777 | 110.927 | 110.975 | 110.940 | 110.927 |
| caption | KPop Demon Hunters (2025) - How It's Done | 46 | 128.419 | 128.567 | 128.310 | 128.340 | 128.310 |
| caption | KPop Demon Hunters (2025) - How It's Done | 62 | 177.093 | 176.897 | 176.883 | 176.820 | 176.897 |
| caption | KPop Demon Hunters (2025) - What It Sounds Like | 21 | 61.102 | 61.291 | 61.275 | 61.360 | 61.291 |
| caption | KPop Demon Hunters (2025) - What It Sounds Like | 35 | 99.891 | 100.111 | 100.200 | 99.920 | 100.111 |
| caption | KPop Demon Hunters (2025) - What It Sounds Like | 51 | 138.429 | 138.522 | 138.550 | 138.220 | 138.522 |
| caption | KPop Demon Hunters (2025) - What It Sounds Like | 52 | 142.475 | 142.492 | 141.908 | 142.380 | 142.492 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 25 | 87.897 | 87.620 | 87.074 | 87.900 | 87.620 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 38 | 139.743 | 139.214 | 139.170 | 139.140 | 139.214 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 55 | 211.591 | 211.200 | 211.138 | 211.240 | 211.200 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 53 | 243.541 | 243.050 | 243.050 | 242.810 | 242.621 |
| caption | Moana (2016) - How Far I'll Go cPAbx5kgCJo | 25 | 87.366 | 87.496 | 87.200 | 87.660 | 87.496 |
| caption | Moana (2016) - How Far I'll Go cPAbx5kgCJo | 36 | 121.500 | 122.030 | 121.180 | 122.040 | 122.030 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 50 | 127.033 | 127.490 | 127.575 | 127.640 | 127.490 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 20 | 42.566 | 42.600 | 42.600 | 41.940 | 42.443 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 17 | 47.839 | 47.700 | 47.700 | 47.040 | 47.200 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 43 | 125.250 | 124.850 | 124.309 | 124.840 | 124.547 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 58 | 172.297 | 171.727 | 171.875 | 171.760 | 171.727 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 68 | 191.691 | 191.234 | 190.884 | 191.100 | 191.234 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 70 | 196.404 | 195.925 | 195.925 | 195.270 | 195.714 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 77 | 210.335 | 209.514 | 209.394 | 210.100 | 209.514 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 91 | 245.536 | 245.692 | 245.325 | 244.940 | 245.632 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 43 | 193.040 | 192.599 | 192.147 | 193.520 | 192.599 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 47 | 209.159 | 209.099 | 208.816 | 209.780 | 209.099 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 31 | 125.400 | 125.525 | 125.525 | 125.720 | 125.125 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 48 | 171.153 | 171.250 | 171.250 | 171.020 | 171.150 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 49 | 174.364 | 173.805 | 173.396 | 174.320 | 173.805 |
| caption | NSYNC - Gone IbRwSI8yi1o | 12 | 81.938 | 82.050 | 82.050 | 81.920 | 81.725 |
| caption | NSYNC - Gone IbRwSI8yi1o | 64 | 252.015 | 253.397 | 251.361 | 252.240 | 251.997 |
| caption | NSYNC - Gone IbRwSI8yi1o | 76 | 285.053 | 285.550 | 285.550 | 284.600 | 285.175 |
| caption | NSYNC - Gone IbRwSI8yi1o | 79 | 291.682 | 292.425 | 291.875 | 291.680 | 292.126 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 47 | 165.273 | 165.326 | 164.930 | 165.520 | 165.703 |
| caption | NSYNC - Pop TWZKw_MgUPI | 3 | 6.540 | 6.525 | 6.145 | 6.560 | 6.525 |
| caption | NSYNC - Pop TWZKw_MgUPI | 5 | 9.030 | 9.108 | 8.975 | 9.340 | 9.068 |
| caption | NSYNC - Pop TWZKw_MgUPI | 14 | 33.204 | 32.743 | 32.589 | 33.080 | 32.743 |
| caption | NSYNC - Pop TWZKw_MgUPI | 32 | 60.974 | 61.101 | 60.875 | 60.800 | 61.041 |
| caption | NSYNC - Pop TWZKw_MgUPI | 49 | 101.993 | 101.704 | 101.628 | 101.800 | 101.704 |
| caption | NSYNC - Pop TWZKw_MgUPI | 57 | 113.225 | 113.244 | 112.610 | 112.960 | 113.244 |
| caption | NSYNC - Pop TWZKw_MgUPI | 75 | 184.640 | 184.205 | 184.025 | 183.900 | 184.205 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 14 | 66.421 | 65.736 | 65.656 | 66.160 | 65.736 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 37 | 168.368 | 168.000 | 167.576 | 168.360 | 168.000 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 38 | 155.029 | 154.762 | 153.964 | 154.220 | 154.722 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 62 | 200.867 | 200.961 | 200.927 | 201.180 | 200.961 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 71 | 223.123 | 223.013 | 222.653 | 223.120 | 223.013 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 23 | 59.268 | 59.388 | 58.459 | 59.420 | 59.089 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 52 | 137.112 | 137.230 | 136.832 | 137.280 | 137.230 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 73 | 199.708 | 199.600 | 199.600 | 199.240 | 198.910 |
| caption | Ne-Yo - So Sick IxszlJppRQI | 16 | 49.215 | 48.836 | 48.466 | 49.100 | 48.836 |
| caption | Ne-Yo - So Sick IxszlJppRQI | 26 | 71.988 | 71.756 | 71.689 | 71.780 | 71.756 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 7 | 30.460 | 30.425 | 30.425 | 29.980 | 30.325 |
| caption | Rent (2005) - Another Day | 61 | 223.251 | 223.425 | 223.425 | 223.540 | 223.325 |
| caption | Rent (2005) - I Should Tell You | 24 | 89.848 | 91.920 | 90.050 | 89.860 | 91.920 |
| caption | Rent (2005) - I Should Tell You | 36 | 132.691 | 133.210 | 132.975 | 133.056 | 132.580 |
| caption | Rent (2005) - I Should Tell You | 39 | 141.199 | 142.850 | 141.575 | 141.568 | 142.850 |
| caption | Rent (2005) - I'll Cover You | 11 | 42.404 | 42.771 | 42.225 | 42.560 | 42.771 |
| caption | Rent (2005) - I'll Cover You | 23 | 85.847 | 85.691 | 85.525 | 85.520 | 85.691 |
| caption | Rent (2005) - I'll Cover You | 27 | 95.724 | 95.825 | 95.825 | 92.896 | 95.550 |
| caption | Rent (2005) - I'll Cover You | 29 | 103.031 | 103.352 | 102.900 | 102.400 | 102.537 |
| caption | Rent (2005) - I'll Cover You | 30 | 108.470 | 108.725 | 108.725 | 108.400 | 108.367 |
| caption | Rent (2005) - I'll Cover You | 34 | 119.514 | 119.512 | 119.020 | 119.340 | 119.512 |
| caption | Rent (2005) - I'll Cover You | 36 | 123.986 | 123.612 | 123.700 | 123.760 | 123.612 |
| caption | Rent (2005) - I'll Cover You | 38 | 129.858 | 130.104 | 130.125 | 129.720 | 129.965 |
| caption | Rent (2005) - Out Tonight | 48 | 203.516 | 203.590 | 203.650 | 203.740 | 203.590 |
| caption | Rent (2005) - Out Tonight | 49 | 206.920 | 207.075 | 207.075 | 207.168 | 206.782 |
| caption | Rent (2005) - Santa Fe | 2 | 13.752 | 14.270 | 14.052 | 14.100 | 14.230 |
| caption | Rent (2005) - Santa Fe | 33 | 145.350 | 145.520 | 145.138 | 145.860 | 145.520 |
| caption | Rent (2005) - Seasons of Love | 4 | 69.093 | 69.200 | 69.250 | 69.240 | 69.200 |
| caption | Rent (2005) - Today 4 U | 10 | 47.478 | 47.555 | 47.048 | 47.620 | 47.555 |
| caption | Rent (2005) - What You Own | 25 | 117.190 | 117.710 | 117.400 | 116.260 | 117.050 |
| caption | Rent (2005) - What You Own | 26 | 120.627 | 121.110 | 120.617 | 120.540 | 120.617 |
| caption | Rent (2005) - What You Own | 33 | 151.291 | 151.528 | 150.961 | 150.840 | 150.961 |
| caption | Rent (2005) - What You Own | 37 | 172.078 | 172.138 | 172.200 | 172.400 | 172.100 |
| caption | Rent (2005) - What You Own | 41 | 190.129 | 190.526 | 189.799 | 190.420 | 190.629 |
| caption | Rent (2005) - Will I | 13 | 85.385 | 85.420 | 84.906 | 85.540 | 85.420 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 22 | 60.034 | 59.691 | 59.150 | 59.800 | 59.691 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 37 | 90.466 | 90.014 | 89.825 | 90.080 | 90.014 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 67 | 157.801 | 157.413 | 156.917 | 157.120 | 157.413 |
| caption | Sara Bareilles - Brave (Offici QUQsqBqxoR4 | 31 | 114.029 | 113.725 | 113.725 | 113.800 | 113.348 |
| caption | Sara Bareilles - Brave (Offici QUQsqBqxoR4 | 57 | 201.637 | 201.253 | 201.245 | 201.320 | 201.253 |
| caption | Sara Bareilles - Brave (Offici QUQsqBqxoR4 | 58 | 203.737 | 203.085 | 203.015 | 203.360 | 203.085 |
| caption | Sara Bareilles - Brave (Offici QUQsqBqxoR4 | 59 | 206.016 | 205.709 | 205.725 | 205.800 | 205.709 |
| caption | The Last Five Years (2014) - A Summer in Ohio | 34 | 122.075 | 122.525 | 121.925 | 122.460 | 122.225 |
| caption | The Last Five Years (2014) - If I Didn't Believe in You | 45 | 184.625 | 184.550 | 184.625 | 184.620 | 184.550 |
| caption | The Last Five Years (2014) - If I Didn't Believe in You | 51 | 204.425 | 204.470 | 204.450 | 204.260 | 204.470 |
| caption | The Last Five Years (2014) - Moving Too Fast | 2 | 4.530 | 4.860 | 4.104 | 4.740 | 4.740 |
| caption | The Last Five Years (2014) - Moving Too Fast | 88 | 325.130 | 325.184 | 325.175 | 325.300 | 325.184 |
| caption | The Last Five Years (2014) - See I'm Smiling | 43 | 197.138 | 197.700 | 197.198 | 197.380 | 197.248 |
| caption | The Last Five Years (2014) - See I'm Smiling | 45 | 208.458 | 208.548 | 208.498 | 208.600 | 208.548 |
| caption | The Last Five Years (2014) - Shiksa Goddess | 22 | 87.894 | 88.125 | 88.125 | 88.000 | 87.775 |
| caption | The Last Five Years (2014) - Shiksa Goddess | 23 | 89.654 | 90.300 | 89.574 | 90.660 | 89.794 |
| caption | The Last Five Years (2014) - Still Hurting | 9 | 74.741 | 75.331 | 74.347 | 75.080 | 75.191 |
| caption | The Last Five Years (2014) - The Schmuel Song | 1 | 2.417 | 2.625 | 2.625 | 2.020 | 2.290 |
| caption | The Last Five Years (2014) - The Schmuel Song | 30 | 93.057 | 92.932 | 92.562 | 93.000 | 92.932 |
| caption | The Last Five Years (2014) - The Schmuel Song | 50 | 159.017 | 159.242 | 158.972 | 159.200 | 159.242 |
| caption | The Last Five Years (2014) - The Schmuel Song | 102 | 346.537 | 346.287 | 346.042 | 346.660 | 346.287 |
| caption | The Lion King (1994) - Can You 25QyCxVkXwQ | 9 | 12.217 | 11.968 | 11.522 | 12.360 | 11.968 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 33 | 82.059 | 81.921 | 81.561 | 81.800 | 81.921 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 43 | 104.248 | 104.123 | 104.120 | 104.240 | 104.123 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 48 | 117.761 | 117.724 | 117.263 | 117.820 | 117.724 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 49 | 119.054 | 118.933 | 118.925 | 118.920 | 118.933 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 60 | 143.996 | 143.791 | 143.800 | 143.860 | 143.791 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 77 | 203.847 | 204.130 | 203.349 | 202.940 | 204.130 |
| caption | The Little Mermaid (1989) - Pa SXKlJuO07eM | 36 | 104.733 | 105.703 | 105.350 | 104.340 | 105.643 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 2 | 4.600 | 4.823 | 4.460 | 4.740 | 4.723 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 4 | 8.566 | 9.123 | 9.175 | 9.100 | 9.123 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 13 | 36.066 | 36.163 | 35.926 | 35.960 | 36.163 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 39 | 100.700 | 101.083 | 100.560 | 100.900 | 101.083 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 63 | 169.733 | 170.343 | 169.593 | 170.320 | 170.343 |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 33 | 218.918 | 218.950 | 218.950 | 218.500 | 218.313 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 32 | 132.866 | 132.775 | 132.775 | 133.220 | 136.024 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 33 | 113.133 | 113.643 | 113.323 | 113.840 | 113.643 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 1 | 3.840 | 3.750 | 3.750 | 3.540 | 3.520 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 3 | 7.853 | 7.680 | 7.547 | 7.620 | 7.660 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 44 | 203.114 | 202.594 | 202.248 | 203.020 | 202.594 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 52 | 233.701 | 233.400 | 233.400 | 233.480 | 232.834 |
| caption | Wicked (2003) - For Good TZ0pXUb5jVU | 14 | 79.106 | 78.950 | 78.950 | 78.600 | 78.600 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 44 | 151.733 | 151.533 | 151.410 | 151.440 | 151.533 |
| caption | ZAYN & Zhavia Ward - A Whole N rg_zwK_sSEY | 17 | 81.366 | 81.830 | 81.394 | 81.920 | 81.830 |
| caption | ZAYN & Zhavia Ward - A Whole N rg_zwK_sSEY | 19 | 86.700 | 87.243 | 86.728 | 87.280 | 87.243 |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 5 | 36.000 | 36.525 | 36.525 | 36.448 | 35.784 |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 39 | 141.800 | 142.075 | 142.075 | 141.560 | 141.643 |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 76 | 259.633 | 259.582 | 259.511 | 260.420 | 259.582 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 20 | 102.900 | 103.125 | 103.125 | 102.960 | 102.620 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 22 | 110.580 | 110.420 | 110.375 | 110.580 | 110.420 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 26 | 125.210 | 125.180 | 124.985 | 125.700 | 125.120 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 8 | 35.940 | 35.796 | 35.538 | 36.040 | 35.796 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 54 | 203.600 | 203.740 | 203.600 | 202.950 | 203.740 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 15 | 76.723 | 76.526 | 76.625 | 76.860 | 76.526 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 26 | 144.401 | 144.750 | 144.750 | 144.580 | 144.200 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 22 | 94.990 | 95.075 | 95.075 | 94.900 | 94.975 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 24 | 98.750 | 98.750 | 98.220 | 98.320 | 98.750 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 47 | 157.360 | 157.090 | 156.830 | 157.080 | 157.090 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 72 | 224.650 | 224.600 | 224.120 | 224.600 | 224.600 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 80 | 249.770 | 249.620 | 249.370 | 249.620 | 249.620 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 10 | 38.864 | 38.954 | 38.802 | 38.600 | 38.954 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 53 | 170.444 | 170.175 | 170.175 | 170.220 | 170.014 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 36 | 100.605 | 100.575 | 100.055 | 100.780 | 100.575 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 37 | 102.225 | 102.075 | 102.150 | 102.240 | 102.075 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 56 | 142.115 | 141.905 | 141.885 | 142.180 | 141.905 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 61 | 152.145 | 152.175 | 152.300 | 152.260 | 152.175 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 71 | 173.735 | 173.535 | 173.165 | 173.740 | 173.535 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 25 | 77.500 | 77.650 | 77.130 | 77.740 | 77.440 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 16 | 40.090 | 40.020 | 39.810 | 40.120 | 40.020 |
| LRCLIB | NSYNC - Paradise | 25 | 163.880 | 164.025 | 164.025 | 163.780 | 163.430 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 9 | 42.240 | 42.202 | 42.027 | 42.340 | 42.270 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 33 | 125.150 | 124.490 | 124.452 | 125.420 | 124.490 |
| LRCLIB | Pocahontas (1995) - Colors of  9ThO76peOw0 | 23 | 114.970 | 115.200 | 115.200 | 114.800 | 114.720 |
| LRCLIB | Sara Bareilles - She Used To B 53GIADHxVzM | 7 | 38.480 | 38.140 | 38.200 | 38.300 | 38.140 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 13 | 42.515 | 42.145 | 41.645 | 42.460 | 42.335 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 14 | 46.325 | 46.225 | 46.225 | 46.180 | 45.775 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 8 | 41.780 | 41.810 | 41.525 | 42.040 | 41.810 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 15 | 75.220 | 75.750 | 74.750 | 75.340 | 75.690 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 13 | 34.990 | 35.075 | 35.075 | 35.100 | 34.920 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 18 | 35.215 | 35.000 | 35.000 | 35.220 | 34.800 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 31 | 59.355 | 59.215 | 58.807 | 59.200 | 59.215 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 27 | 99.464 | 99.584 | 99.725 | 99.640 | 99.584 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 27 | 120.840 | 120.700 | 120.516 | 121.120 | 120.700 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 28 | 123.620 | 123.880 | 123.026 | 123.640 | 123.956 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 43 | 189.830 | 189.694 | 189.626 | 189.700 | 189.694 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 49 | 207.740 | 207.456 | 207.226 | 208.200 | 207.456 |

### Table Z: zero-length words re-timed
Zero-length: words under 0.05 s in the line as the baseline rescue left it. Re-timed: words whose times the zero-length rule changed. Short after: words under 0.1 s in the snapped line.

caption: 904 lines in 127 songs; LRCLIB: 154 lines in 23 songs

| Src | Song | Line | Tokens | Zero-length | Re-timed | Short after |
|---|---|---|---|---|---|---|
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 11 | 9 | 1 | 1 | 0 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 21 | 11 | 1 | 1 | 0 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 29 | 8 | 1 | 2 | 0 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 33 | 8 | 1 | 2 | 0 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 41 | 6 | 2 | 2 | 0 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 49 | 10 | 2 | 3 | 2 |
| caption | Adele - Rolling in the Deep (O rYEDA3JcQqw | 50 | 6 | 3 | 3 | 4 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 1 | 8 | 1 | 1 | 0 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 20 | 7 | 1 | 1 | 0 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 41 | 6 | 1 | 1 | 0 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 45 | 6 | 1 | 1 | 0 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 59 | 9 | 1 | 2 | 0 |
| caption | Adele - Send My Love (To Your  fk4BbF7B29w | 63 | 9 | 1 | 2 | 0 |
| caption | Adele - Someone Like You hLQl3WQQoQ0 | 27 | 10 | 1 | 1 | 0 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 34 | 6 | 2 | 0 | 2 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 35 | 3 | 1 | 1 | 0 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 41 | 4 | 2 | 3 | 3 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 42 | 4 | 1 | 2 | 0 |
| caption | Aladdin (2019) - A Whole New W eitDnP0_83k | 43 | 5 | 1 | 0 | 1 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 2 | 7 | 1 | 1 | 0 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 16 | 7 | 1 | 1 | 1 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 19 | 6 | 1 | 1 | 0 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 31 | 5 | 1 | 1 | 0 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 36 | 7 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 26 | 5 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 38 | 5 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 39 | 5 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 40 | 5 | 1 | 2 | 2 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 43 | 8 | 1 | 1 | 1 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 45 | 4 | 1 | 2 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 47 | 10 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 55 | 5 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 62 | 8 | 1 | 1 | 0 |
| caption | BTS 방탄소년단 - Butter WMweEpGlu_U | 63 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 14 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 43 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 48 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 54 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 56 | 8 | 1 | 2 | 0 |
| caption | Backstreet Boys - All I Have T pj6FCKm8dhM | 61 | 9 | 4 | 5 | 0 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 31 | 3 | 1 | 0 | 2 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 45 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 49 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 56 | 6 | 3 | 4 | 4 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 0 | 2 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 5 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 8 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 13 | 9 | 1 | 1 | 1 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 15 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 19 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 33 | 6 | 2 | 3 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 34 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 36 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 40 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 48 | 9 | 3 | 4 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 50 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 54 | 5 | 1 | 1 | 1 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 56 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 60 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 61 | 8 | 2 | 3 | 3 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 62 | 9 | 1 | 1 | 1 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 64 | 11 | 4 | 4 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 65 | 7 | 3 | 4 | 0 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 68 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 3 | 10 | 1 | 1 | 4 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 5 | 5 | 2 | 3 | 3 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 20 | 8 | 1 | 2 | 0 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 30 | 6 | 1 | 1 | 1 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 41 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 51 | 6 | 1 | 1 | 1 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 78 | 8 | 1 | 1 | 2 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 81 | 8 | 1 | 1 | 1 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 82 | 11 | 1 | 1 | 1 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 83 | 6 | 3 | 4 | 4 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 84 | 6 | 1 | 1 | 0 |
| caption | Backstreet Boys - Everybody (B 6M6samPEMpM | 86 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 4 | 4 | 2 | 3 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 5 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 9 | 9 | 1 | 1 | 1 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 20 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 24 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 35 | 6 | 1 | 1 | 2 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 37 | 7 | 2 | 3 | 2 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 38 | 7 | 2 | 3 | 1 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 39 | 6 | 1 | 1 | 1 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 41 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 42 | 6 | 1 | 1 | 2 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 43 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 49 | 4 | 1 | 2 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 53 | 6 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 54 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 56 | 4 | 2 | 3 | 3 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 58 | 5 | 1 | 2 | 1 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 59 | 3 | 1 | 2 | 2 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 74 | 4 | 2 | 2 | 3 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 79 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 80 | 3 | 1 | 1 | 1 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 82 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 83 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 85 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 91 | 2 | 1 | 1 | 1 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 93 | 7 | 2 | 3 | 2 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 97 | 7 | 2 | 3 | 0 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 105 | 7 | 2 | 2 | 1 |
| caption | Backstreet Boys - I Want It Th 4fndeDfaWCg | 22 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - I Want It Th 4fndeDfaWCg | 39 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - I Want It Th 4fndeDfaWCg | 41 | 5 | 1 | 2 | 2 |
| caption | Backstreet Boys - I Want It Th 4fndeDfaWCg | 54 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - I Want It Th 4fndeDfaWCg | 56 | 11 | 4 | 5 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 6 | 7 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 7 | 5 | 1 | 1 | 1 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 9 | 7 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 14 | 9 | 1 | 2 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 19 | 11 | 2 | 3 | 4 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 20 | 7 | 2 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 21 | 5 | 2 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 22 | 6 | 3 | 4 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 23 | 11 | 5 | 6 | 5 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 24 | 7 | 2 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 30 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 34 | 7 | 2 | 3 | 3 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 38 | 6 | 1 | 2 | 2 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 42 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 44 | 8 | 2 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 46 | 4 | 1 | 2 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 47 | 5 | 2 | 3 | 1 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 52 | 10 | 4 | 4 | 4 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 55 | 10 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 56 | 5 | 1 | 2 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 57 | 5 | 1 | 2 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 59 | 6 | 2 | 3 | 2 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 61 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 62 | 7 | 3 | 5 | 3 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 63 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 65 | 6 | 3 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 68 | 8 | 2 | 2 | 1 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 71 | 8 | 2 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 72 | 8 | 3 | 5 | 2 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 73 | 12 | 2 | 3 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 78 | 5 | 2 | 2 | 1 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 79 | 7 | 3 | 4 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 80 | 4 | 2 | 4 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 81 | 6 | 1 | 2 | 0 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 82 | 4 | 1 | 1 | 1 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 83 | 6 | 1 | 2 | 3 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 84 | 5 | 2 | 3 | 0 |
| caption | Backstreet Boys - Incomplete WVe80iZtlYU | 10 | 3 | 1 | 1 | 1 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 0 | 4 | 1 | 1 | 0 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 28 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 43 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 45 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Larger Than  MEb2CecR11I | 1 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Larger Than  MEb2CecR11I | 7 | 6 | 1 | 1 | 0 |
| caption | Backstreet Boys - Larger Than  MEb2CecR11I | 18 | 10 | 1 | 1 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 9 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 12 | 7 | 1 | 1 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 14 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 18 | 6 | 1 | 1 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 22 | 7 | 1 | 1 | 1 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 29 | 8 | 1 | 1 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 33 | 7 | 1 | 2 | 0 |
| caption | Backstreet Boys - More Than Th 1OwfYjemrYw | 37 | 7 | 1 | 1 | 1 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 17 | 2 | 1 | 1 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 21 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 40 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 48 | 2 | 1 | 1 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 57 | 7 | 1 | 2 | 1 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 58 | 6 | 2 | 2 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 59 | 6 | 1 | 2 | 2 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 60 | 5 | 1 | 1 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 68 | 5 | 1 | 2 | 1 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 79 | 6 | 2 | 3 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 80 | 6 | 1 | 1 | 0 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 81 | 7 | 3 | 3 | 1 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 83 | 6 | 3 | 3 | 5 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 20 | 2 | 1 | 1 | 0 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 26 | 12 | 4 | 4 | 4 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 37 | 11 | 2 | 3 | 0 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 41 | 8 | 2 | 2 | 2 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 43 | 10 | 1 | 2 | 3 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 44 | 11 | 5 | 6 | 0 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 45 | 7 | 3 | 3 | 3 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 5 | 3 | 1 | 1 | 0 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 27 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 40 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 47 | 4 | 1 | 2 | 0 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 63 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 69 | 9 | 1 | 1 | 0 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 81 | 9 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 13 | 6 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 24 | 3 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 26 | 4 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 42 | 6 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 61 | 7 | 1 | 2 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 64 | 7 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 68 | 6 | 1 | 1 | 1 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 69 | 8 | 2 | 2 | 1 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 72 | 4 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  MiraOCjABn8 | 76 | 7 | 2 | 2 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 14 | 3 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 15 | 3 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 28 | 8 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 42 | 6 | 1 | 1 | 2 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 52 | 9 | 1 | 2 | 2 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 67 | 5 | 2 | 3 | 4 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 75 | 7 | 1 | 1 | 1 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 80 | 6 | 1 | 1 | 2 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 90 | 3 | 1 | 1 | 2 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 91 | 5 | 2 | 3 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 98 | 6 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 99 | 7 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 100 | 9 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 102 | 7 | 1 | 1 | 0 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 103 | 8 | 2 | 4 | 2 |
| caption | Britney Spears - (You Drive Me Q4VK9_CfOLQ | 26 | 9 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 0 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 1 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 2 | 9 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 4 | 9 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 13 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 15 | 5 | 1 | 1 | 1 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 16 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 28 | 9 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 29 | 9 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 39 | 6 | 1 | 1 | 0 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 40 | 6 | 2 | 3 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 8 | 4 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 13 | 5 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 14 | 5 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 17 | 8 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 19 | 6 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 22 | 5 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 29 | 6 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 31 | 6 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 36 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 44 | 5 | 2 | 2 | 1 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 45 | 5 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 58 | 8 | 1 | 2 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 60 | 5 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 63 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 67 | 5 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 70 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 71 | 6 | 1 | 1 | 0 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 1 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 9 | 7 | 1 | 1 | 0 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 20 | 3 | 1 | 1 | 0 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 24 | 7 | 1 | 1 | 1 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 26 | 15 | 2 | 2 | 0 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 7 | 7 | 1 | 1 | 0 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 11 | 7 | 1 | 2 | 0 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 32 | 7 | 1 | 2 | 0 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 35 | 10 | 1 | 1 | 3 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 40 | 7 | 1 | 1 | 1 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 42 | 7 | 1 | 1 | 0 |
| caption | Britney Spears - Toxic (Offici LOZuxwVk7TU | 45 | 7 | 1 | 2 | 2 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 11 | 11 | 1 | 1 | 2 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 16 | 6 | 1 | 1 | 0 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 20 | 12 | 2 | 2 | 0 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 25 | 6 | 1 | 1 | 0 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 36 | 8 | 1 | 1 | 0 |
| caption | Cast of Camp Rock - One Beat A tESZ92ugf7g | 3 | 10 | 2 | 2 | 0 |
| caption | Cast of Camp Rock - One Beat A tESZ92ugf7g | 6 | 8 | 1 | 1 | 1 |
| caption | Cast of Camp Rock - One Beat A tESZ92ugf7g | 25 | 8 | 2 | 2 | 0 |
| caption | Cast of Camp Rock - One Beat A tESZ92ugf7g | 28 | 5 | 1 | 1 | 1 |
| caption | Cast of Camp Rock - One Beat A tESZ92ugf7g | 59 | 2 | 1 | 1 | 0 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 3 | 2 | 1 | 0 | 1 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 34 | 4 | 1 | 1 | 0 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 44 | 4 | 1 | 1 | 0 |
| caption | Christina Aguilera - Genie In  kIDWgqDBNXA | 2 | 5 | 1 | 1 | 0 |
| caption | Colbie Caillat - Bubbly (Offic AWGqoCNbsvM | 36 | 10 | 1 | 1 | 0 |
| caption | Colbie Caillat - Bubbly (Offic AWGqoCNbsvM | 39 | 2 | 1 | 2 | 0 |
| caption | Colbie Caillat - Realize GlZxZ2n2zpw | 8 | 8 | 1 | 1 | 0 |
| caption | Colbie Caillat - Realize GlZxZ2n2zpw | 16 | 6 | 2 | 2 | 0 |
| caption | Colbie Caillat - Realize GlZxZ2n2zpw | 23 | 8 | 1 | 1 | 0 |
| caption | Colbie Caillat - Realize GlZxZ2n2zpw | 43 | 3 | 1 | 1 | 0 |
| caption | Colbie Caillat - Realize GlZxZ2n2zpw | 44 | 3 | 1 | 1 | 0 |
| caption | Céline Dion - Ashes (Deadpool  CX11yw6YL1w | 12 | 13 | 1 | 1 | 0 |
| caption | Céline Dion - Ashes (Deadpool  CX11yw6YL1w | 31 | 19 | 1 | 1 | 5 |
| caption | Céline Dion - I'm Alive (Stuar NJsa6-y4sDs | 41 | 7 | 1 | 1 | 1 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 0 | 4 | 1 | 1 | 1 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 3 | 11 | 1 | 1 | 0 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 9 | 10 | 1 | 1 | 0 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 12 | 8 | 1 | 1 | 3 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 21 | 9 | 1 | 1 | 0 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 30 | 8 | 2 | 3 | 2 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 33 | 8 | 1 | 1 | 1 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 45 | 8 | 2 | 2 | 0 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 48 | 8 | 1 | 1 | 0 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 0 | 10 | 1 | 1 | 0 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 4 | 5 | 1 | 1 | 0 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 24 | 9 | 1 | 1 | 0 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 27 | 4 | 1 | 1 | 0 |
| caption | Ed Sheeran - Happier iWZmdoY1aTE | 34 | 7 | 1 | 1 | 2 |
| caption | Ed Sheeran - Perfect 2Vv-BfVoq4g | 4 | 5 | 1 | 1 | 0 |
| caption | Ed Sheeran - Perfect 2Vv-BfVoq4g | 6 | 11 | 1 | 1 | 0 |
| caption | Ed Sheeran - Perfect 2Vv-BfVoq4g | 21 | 5 | 1 | 1 | 0 |
| caption | Ed Sheeran - Perfect 2Vv-BfVoq4g | 22 | 5 | 1 | 1 | 1 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 8 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 10 | 6 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 14 | 6 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 15 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 35 | 12 | 2 | 2 | 1 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 37 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 38 | 8 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 39 | 6 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 58 | 7 | 1 | 2 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 59 | 7 | 1 | 1 | 1 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 60 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 61 | 7 | 1 | 1 | 2 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 62 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 63 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 64 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 65 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 74 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 76 | 7 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shape of You JGwWNGJdvx8 | 79 | 5 | 1 | 2 | 2 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 16 | 10 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 23 | 10 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 45 | 10 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 61 | 6 | 1 | 1 | 0 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 65 | 6 | 1 | 1 | 1 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 67 | 10 | 1 | 1 | 1 |
| caption | Ed Sheeran - Shivers [Official Il0S8BoucSA | 79 | 10 | 1 | 1 | 0 |
| caption | Ed Sheeran - The A Team UAWcs5H-qgQ | 1 | 4 | 1 | 1 | 0 |
| caption | Ed Sheeran - The A Team UAWcs5H-qgQ | 18 | 9 | 1 | 1 | 0 |
| caption | Ed Sheeran - The A Team UAWcs5H-qgQ | 46 | 8 | 1 | 1 | 0 |
| caption | Ed Sheeran - The A Team UAWcs5H-qgQ | 52 | 5 | 1 | 1 | 0 |
| caption | Ed Sheeran - The A Team UAWcs5H-qgQ | 60 | 9 | 1 | 1 | 2 |
| caption | Ed Sheeran - Thinking Out Loud lp-EO5I60KA | 4 | 6 | 1 | 1 | 0 |
| caption | Ed Sheeran - Thinking Out Loud lp-EO5I60KA | 11 | 11 | 1 | 2 | 0 |
| caption | Ed Sheeran - Thinking Out Loud lp-EO5I60KA | 25 | 4 | 1 | 1 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 4 | 6 | 2 | 2 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 13 | 6 | 1 | 1 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 14 | 6 | 1 | 1 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 19 | 7 | 1 | 2 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 33 | 9 | 1 | 1 | 1 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 41 | 9 | 2 | 3 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 50 | 6 | 1 | 1 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 59 | 7 | 1 | 1 | 0 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 78 | 8 | 1 | 1 | 1 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 79 | 8 | 1 | 1 | 1 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 83 | 12 | 1 | 2 | 3 |
| caption | Eminem - Without Me (Official  YVkUvmDQ3HY | 86 | 6 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Bowie | 2 | 6 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Bowie | 38 | 11 | 1 | 1 | 2 |
| caption | Flight of the Conchords (2007) - Bowie | 43 | 3 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Bowie | 46 | 10 | 1 | 2 | 0 |
| caption | Flight of the Conchords (2007) - Business Time | 1 | 6 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Business Time | 16 | 12 | 2 | 4 | 2 |
| caption | Flight of the Conchords (2007) - Business Time | 17 | 8 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Business Time | 42 | 11 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Business Time | 63 | 10 | 1 | 1 | 2 |
| caption | Flight of the Conchords (2007) - Business Time | 82 | 8 | 1 | 1 | 3 |
| caption | Flight of the Conchords (2007) - Carol Brown | 14 | 10 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Carol Brown | 51 | 10 | 1 | 2 | 0 |
| caption | Flight of the Conchords (2007) - Carol Brown | 52 | 9 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Carol Brown | 65 | 5 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 8 | 8 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 35 | 3 | 1 | 2 | 0 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 36 | 6 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 40 | 7 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Foux du Fafa | 41 | 6 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 0 | 11 | 1 | 2 | 2 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 1 | 9 | 1 | 1 | 2 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 2 | 10 | 1 | 1 | 2 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 3 | 12 | 1 | 1 | 3 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 9 | 7 | 1 | 1 | 2 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 10 | 10 | 1 | 3 | 0 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 13 | 8 | 1 | 2 | 0 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 17 | 5 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 19 | 9 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 23 | 8 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 37 | 6 | 1 | 2 | 0 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 2 | 7 | 1 | 1 | 3 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 5 | 14 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 20 | 12 | 2 | 3 | 4 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 21 | 8 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 33 | 10 | 1 | 2 | 1 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 43 | 9 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 49 | 9 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 52 | 6 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 58 | 5 | 1 | 1 | 2 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 1 | 13 | 1 | 1 | 3 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 20 | 2 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 24 | 7 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 45 | 6 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 52 | 2 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Ladies of the World | 0 | 7 | 1 | 2 | 3 |
| caption | Flight of the Conchords (2007) - Ladies of the World | 2 | 4 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Ladies of the World | 22 | 4 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Ladies of the World | 48 | 8 | 1 | 2 | 0 |
| caption | Flight of the Conchords (2007) - Robots | 5 | 6 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Robots | 23 | 6 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - Robots | 32 | 7 | 1 | 1 | 1 |
| caption | Flight of the Conchords (2007) - Robots | 40 | 4 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | 15 | 6 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | 19 | 3 | 1 | 1 | 0 |
| caption | Flight of the Conchords (2007) - The Most Beautiful Girl (In the Room) | 37 | 9 | 1 | 2 | 0 |
| caption | Frozen (2013) - Let It Go YVVTZgwYwVo | 12 | 4 | 1 | 1 | 0 |
| caption | Frozen (2013) - Let It Go YVVTZgwYwVo | 15 | 6 | 1 | 1 | 0 |
| caption | Frozen (2013) - Let It Go YVVTZgwYwVo | 41 | 6 | 1 | 1 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 1 | 6 | 1 | 2 | 2 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 3 | 7 | 1 | 2 | 1 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 5 | 6 | 2 | 3 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 6 | 5 | 2 | 3 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 7 | 5 | 1 | 2 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 8 | 5 | 2 | 3 | 3 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 18 | 10 | 2 | 4 | 2 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 19 | 6 | 2 | 3 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 20 | 10 | 1 | 2 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 22 | 6 | 1 | 1 | 2 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 23 | 8 | 1 | 2 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 24 | 11 | 5 | 8 | 1 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 26 | 7 | 3 | 5 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 29 | 8 | 2 | 3 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 30 | 8 | 4 | 4 | 5 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 31 | 7 | 2 | 3 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 33 | 10 | 2 | 4 | 2 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 34 | 6 | 2 | 3 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 35 | 10 | 2 | 3 | 1 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 37 | 10 | 1 | 2 | 3 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 39 | 10 | 4 | 5 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 41 | 10 | 2 | 2 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 46 | 8 | 1 | 2 | 0 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 50 | 8 | 2 | 3 | 3 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 51 | 11 | 3 | 4 | 5 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 53 | 6 | 1 | 2 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 0 | 3 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 1 | 2 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 6 | 5 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 18 | 6 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 20 | 9 | 2 | 2 | 1 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 21 | 6 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 26 | 5 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 43 | 6 | 1 | 1 | 0 |
| caption | Jessie J - Who You Are j2WWrupMBAE | 54 | 3 | 1 | 1 | 0 |
| caption | John Legend - All of Me 450p7goxZqg | 45 | 6 | 1 | 1 | 0 |
| caption | John Legend - All of Me 450p7goxZqg | 49 | 11 | 1 | 1 | 0 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 5 | 9 | 1 | 1 | 0 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 12 | 10 | 1 | 1 | 0 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 17 | 9 | 3 | 5 | 2 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 18 | 6 | 1 | 2 | 1 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 22 | 5 | 1 | 2 | 0 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 42 | 11 | 1 | 1 | 0 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 51 | 9 | 3 | 3 | 0 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 26 | 10 | 1 | 1 | 1 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 37 | 4 | 1 | 2 | 0 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 51 | 7 | 1 | 2 | 0 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 66 | 5 | 1 | 1 | 0 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 67 | 6 | 1 | 1 | 0 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 82 | 8 | 1 | 2 | 0 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 91 | 6 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 9 | 10 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 20 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 21 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 25 | 5 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 37 | 11 | 1 | 1 | 1 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 39 | 11 | 2 | 2 | 1 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 50 | 7 | 1 | 1 | 1 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 51 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 53 | 5 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 58 | 8 | 2 | 0 | 2 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 77 | 5 | 2 | 2 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 78 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 106 | 6 | 3 | 4 | 0 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 110 | 2 | 1 | 1 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 0 | 4 | 1 | 1 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 10 | 8 | 1 | 1 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 18 | 7 | 1 | 1 | 1 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 20 | 5 | 1 | 2 | 2 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 39 | 6 | 1 | 1 | 1 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 41 | 8 | 2 | 2 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 42 | 6 | 2 | 3 | 2 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 52 | 10 | 1 | 1 | 2 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 53 | 10 | 2 | 2 | 2 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 56 | 8 | 1 | 2 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 57 | 10 | 1 | 1 | 2 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 58 | 9 | 2 | 3 | 1 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 60 | 6 | 2 | 2 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 61 | 10 | 2 | 3 | 1 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 62 | 8 | 1 | 1 | 1 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 64 | 6 | 2 | 3 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 71 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 73 | 3 | 1 | 2 | 2 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 81 | 6 | 1 | 1 | 1 |
| caption | Justin Timberlake - Like I Lov FQ3slUz7Jo8 | 83 | 3 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 24 | 10 | 1 | 2 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 32 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 33 | 8 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 58 | 13 | 1 | 1 | 1 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 59 | 6 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 76 | 9 | 3 | 3 | 1 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 77 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 78 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 80 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 82 | 9 | 2 | 2 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 83 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 84 | 9 | 1 | 1 | 2 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 89 | 12 | 1 | 1 | 1 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 90 | 12 | 1 | 1 | 2 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 104 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 105 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 106 | 9 | 1 | 1 | 1 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 108 | 9 | 2 | 2 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 109 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 110 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 111 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 114 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 116 | 9 | 2 | 2 | 2 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 118 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 119 | 9 | 1 | 1 | 0 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 9 | 3 | 1 | 2 | 2 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 38 | 5 | 1 | 1 | 1 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 65 | 11 | 1 | 2 | 2 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 67 | 6 | 1 | 2 | 3 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 68 | 11 | 4 | 6 | 6 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 69 | 6 | 1 | 2 | 0 |
| caption | Justin Timberlake - Rock Your  TSVHoHyErBQ | 92 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 12 | 10 | 1 | 1 | 0 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 20 | 4 | 1 | 1 | 0 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 68 | 4 | 1 | 1 | 1 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 74 | 4 | 1 | 2 | 1 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 59 | 7 | 1 | 1 | 0 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 90 | 12 | 1 | 3 | 1 |
| caption | Justin Timberlake - Suit & Tie (feat. JAY-Z)---IsUsVbTj2AY | 91 | 7 | 1 | 2 | 0 |
| caption | KPop Demon Hunters (2025) - Free | 29 | 9 | 1 | 1 | 0 |
| caption | KPop Demon Hunters (2025) - Free | 36 | 13 | 1 | 1 | 0 |
| caption | KPop Demon Hunters (2025) - How It's Done | 2 | 7 | 1 | 2 | 2 |
| caption | KPop Demon Hunters (2025) - How It's Done | 4 | 4 | 1 | 1 | 1 |
| caption | KPop Demon Hunters (2025) - How It's Done | 5 | 3 | 1 | 1 | 1 |
| caption | KPop Demon Hunters (2025) - How It's Done | 13 | 12 | 1 | 1 | 2 |
| caption | KPop Demon Hunters (2025) - How It's Done | 16 | 8 | 1 | 1 | 0 |
| caption | KPop Demon Hunters (2025) - How It's Done | 20 | 11 | 1 | 2 | 2 |
| caption | KPop Demon Hunters (2025) - How It's Done | 35 | 10 | 1 | 2 | 0 |
| caption | KPop Demon Hunters (2025) - How It's Done | 45 | 8 | 2 | 3 | 0 |
| caption | KPop Demon Hunters (2025) - How It's Done | 49 | 10 | 4 | 5 | 1 |
| caption | KPop Demon Hunters (2025) - How It's Done | 50 | 8 | 1 | 1 | 0 |
| caption | KPop Demon Hunters (2025) - How It's Done | 52 | 11 | 2 | 3 | 1 |
| caption | KPop Demon Hunters (2025) - How It's Done | 57 | 11 | 1 | 1 | 1 |
| caption | KPop Demon Hunters (2025) - How It's Done | 60 | 5 | 1 | 1 | 0 |
| caption | KPop Demon Hunters (2025) - How It's Done | 61 | 6 | 1 | 1 | 1 |
| caption | KPop Demon Hunters (2025) - How It's Done | 63 | 6 | 1 | 2 | 0 |
| caption | KPop Demon Hunters (2025) - What It Sounds Like | 39 | 4 | 1 | 1 | 0 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 2 | 7 | 1 | 1 | 0 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 21 | 8 | 1 | 1 | 0 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 42 | 7 | 1 | 1 | 0 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 47 | 8 | 1 | 1 | 0 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 1 | 9 | 1 | 1 | 1 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 25 | 7 | 1 | 1 | 1 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 37 | 6 | 1 | 1 | 0 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 49 | 10 | 1 | 1 | 3 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 50 | 8 | 1 | 1 | 2 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 51 | 9 | 1 | 1 | 4 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 52 | 7 | 1 | 1 | 0 |
| caption | Lewis Capaldi - Someone You Lo zABLecsR5UE | 0 | 6 | 1 | 1 | 0 |
| caption | Lewis Capaldi - Someone You Lo zABLecsR5UE | 19 | 6 | 1 | 1 | 0 |
| caption | Lewis Capaldi - Someone You Lo zABLecsR5UE | 43 | 5 | 1 | 1 | 0 |
| caption | Moana (2016) - How Far I'll Go cPAbx5kgCJo | 6 | 8 | 1 | 1 | 1 |
| caption | Moana (2016) - How Far I'll Go cPAbx5kgCJo | 24 | 10 | 1 | 2 | 1 |
| caption | Moana (2016) - How Far I'll Go cPAbx5kgCJo | 35 | 9 | 1 | 1 | 1 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 15 | 5 | 1 | 1 | 0 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 22 | 2 | 1 | 2 | 0 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 30 | 6 | 1 | 1 | 3 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 38 | 7 | 1 | 1 | 0 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 49 | 8 | 1 | 1 | 0 |
| caption | Moana (2016) - Shiny 93lrosBEW-Q | 66 | 5 | 1 | 1 | 0 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 0 | 9 | 2 | 3 | 3 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 6 | 2 | 1 | 1 | 0 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 29 | 6 | 1 | 1 | 0 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 43 | 8 | 1 | 1 | 2 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 55 | 7 | 1 | 1 | 1 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 63 | 9 | 2 | 2 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 11 | 8 | 1 | 1 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 25 | 9 | 1 | 1 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 54 | 8 | 1 | 2 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 59 | 8 | 1 | 2 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 62 | 7 | 1 | 2 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 89 | 6 | 2 | 2 | 0 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 90 | 6 | 2 | 2 | 1 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 0 | 8 | 4 | 6 | 7 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 24 | 10 | 1 | 1 | 0 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 30 | 11 | 1 | 2 | 1 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 42 | 11 | 2 | 3 | 0 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 43 | 11 | 1 | 3 | 1 |
| caption | Mulan (1998) - I'll Make a Man vGfJeW_CcFY | 47 | 11 | 1 | 2 | 1 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 1 | 2 | 1 | 1 | 0 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 23 | 4 | 1 | 1 | 0 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 46 | 7 | 2 | 2 | 0 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 47 | 7 | 1 | 0 | 1 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 48 | 7 | 3 | 4 | 3 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 49 | 7 | 3 | 4 | 2 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 66 | 7 | 2 | 3 | 2 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 67 | 4 | 1 | 2 | 0 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 69 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 15 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 20 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 37 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 42 | 4 | 1 | 2 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 47 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 55 | 6 | 1 | 2 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 61 | 6 | 1 | 2 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 63 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 68 | 4 | 1 | 1 | 1 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 9 | 6 | 1 | 1 | 0 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 18 | 6 | 1 | 2 | 2 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 24 | 6 | 1 | 1 | 0 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 41 | 7 | 1 | 1 | 0 |
| caption | NSYNC - Girlfriend saxnXiBKEaY | 59 | 6 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 5 | 5 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 8 | 5 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 16 | 11 | 1 | 2 | 2 |
| caption | NSYNC - Gone IbRwSI8yi1o | 23 | 3 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 27 | 7 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 34 | 6 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 44 | 11 | 1 | 2 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 45 | 4 | 2 | 3 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 47 | 4 | 1 | 2 | 1 |
| caption | NSYNC - Gone IbRwSI8yi1o | 55 | 7 | 1 | 1 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 62 | 4 | 1 | 1 | 1 |
| caption | NSYNC - Gone IbRwSI8yi1o | 66 | 6 | 1 | 2 | 0 |
| caption | NSYNC - Gone IbRwSI8yi1o | 70 | 11 | 4 | 6 | 4 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 4 | 2 | 1 | 1 | 0 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 15 | 8 | 1 | 1 | 1 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 22 | 10 | 1 | 1 | 0 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 28 | 8 | 1 | 1 | 1 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 35 | 5 | 1 | 1 | 0 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 42 | 4 | 1 | 1 | 0 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 48 | 8 | 1 | 1 | 1 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 55 | 8 | 1 | 1 | 2 |
| caption | NSYNC - It's Gonna Be Me GQMlWwIXg3M | 56 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 30 | 5 | 1 | 2 | 2 |
| caption | NSYNC - Pop TWZKw_MgUPI | 34 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 50 | 3 | 1 | 2 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 55 | 8 | 1 | 2 | 2 |
| caption | NSYNC - Pop TWZKw_MgUPI | 61 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 65 | 4 | 2 | 2 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 68 | 6 | 2 | 3 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 69 | 5 | 1 | 2 | 0 |
| caption | NSYNC - Pop TWZKw_MgUPI | 79 | 4 | 1 | 1 | 1 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 5 | 4 | 1 | 1 | 0 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 18 | 2 | 1 | 1 | 0 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 28 | 9 | 1 | 1 | 1 |
| caption | NSYNC - This I Promise You 6thmPrTxBtI | 20 | 4 | 1 | 2 | 0 |
| caption | NSYNC - This I Promise You 6thmPrTxBtI | 38 | 8 | 3 | 4 | 0 |
| caption | NSYNC - This I Promise You 6thmPrTxBtI | 39 | 7 | 1 | 2 | 2 |
| caption | NSYNC - This I Promise You 6thmPrTxBtI | 52 | 4 | 1 | 1 | 0 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 2 | 6 | 2 | 2 | 2 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 3 | 6 | 2 | 2 | 1 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 4 | 7 | 2 | 4 | 2 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 10 | 13 | 1 | 1 | 1 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 14 | 13 | 1 | 2 | 0 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 24 | 4 | 1 | 1 | 0 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 27 | 10 | 1 | 1 | 0 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 28 | 11 | 1 | 1 | 0 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 31 | 13 | 2 | 3 | 2 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 37 | 12 | 3 | 3 | 4 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 45 | 6 | 1 | 1 | 0 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 46 | 10 | 2 | 3 | 0 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 7 | 6 | 1 | 0 | 1 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 12 | 7 | 1 | 1 | 0 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 20 | 7 | 1 | 2 | 0 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 25 | 2 | 1 | 1 | 0 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 53 | 6 | 1 | 2 | 1 |
| caption | Ne-Yo - So Sick IxszlJppRQI | 7 | 7 | 1 | 1 | 0 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 21 | 4 | 1 | 1 | 0 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 43 | 9 | 2 | 2 | 0 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 49 | 11 | 4 | 7 | 3 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 50 | 4 | 2 | 3 | 3 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 51 | 7 | 1 | 2 | 3 |
| caption | Queen - Bohemian Rhapsody fJ9rUzIMcZQ | 52 | 10 | 1 | 1 | 0 |
| caption | Rent (2005) - Another Day | 2 | 8 | 1 | 1 | 0 |
| caption | Rent (2005) - Another Day | 9 | 7 | 1 | 1 | 0 |
| caption | Rent (2005) - Another Day | 10 | 4 | 1 | 1 | 0 |
| caption | Rent (2005) - Another Day | 36 | 9 | 1 | 1 | 0 |
| caption | Rent (2005) - Another Day | 56 | 9 | 2 | 3 | 1 |
| caption | Rent (2005) - Another Day | 59 | 12 | 3 | 4 | 4 |
| caption | Rent (2005) - Another Day | 60 | 15 | 7 | 8 | 0 |
| caption | Rent (2005) - Another Day | 61 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - Another Day | 62 | 8 | 2 | 3 | 1 |
| caption | Rent (2005) - Another Day | 68 | 9 | 1 | 1 | 1 |
| caption | Rent (2005) - Another Day | 72 | 6 | 1 | 1 | 0 |
| caption | Rent (2005) - I Should Tell You | 14 | 6 | 2 | 2 | 0 |
| caption | Rent (2005) - I Should Tell You | 16 | 4 | 1 | 2 | 0 |
| caption | Rent (2005) - I Should Tell You | 21 | 4 | 1 | 1 | 0 |
| caption | Rent (2005) - I Should Tell You | 22 | 6 | 1 | 2 | 0 |
| caption | Rent (2005) - I Should Tell You | 23 | 6 | 2 | 1 | 1 |
| caption | Rent (2005) - I Should Tell You | 26 | 4 | 1 | 2 | 0 |
| caption | Rent (2005) - I Should Tell You | 27 | 6 | 2 | 2 | 0 |
| caption | Rent (2005) - I Should Tell You | 28 | 6 | 3 | 4 | 0 |
| caption | Rent (2005) - I Should Tell You | 29 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - I Should Tell You | 30 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - I Should Tell You | 31 | 6 | 3 | 4 | 0 |
| caption | Rent (2005) - I Should Tell You | 32 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - I Should Tell You | 33 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - I Should Tell You | 34 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - I Should Tell You | 35 | 4 | 1 | 2 | 1 |
| caption | Rent (2005) - I Should Tell You | 38 | 6 | 1 | 0 | 2 |
| caption | Rent (2005) - I Should Tell You | 43 | 4 | 1 | 1 | 0 |
| caption | Rent (2005) - I Should Tell You | 45 | 4 | 1 | 1 | 0 |
| caption | Rent (2005) - I'll Cover You | 10 | 10 | 4 | 0 | 4 |
| caption | Rent (2005) - I'll Cover You | 12 | 14 | 5 | 4 | 5 |
| caption | Rent (2005) - I'll Cover You | 14 | 4 | 1 | 1 | 0 |
| caption | Rent (2005) - I'll Cover You | 15 | 6 | 1 | 1 | 0 |
| caption | Rent (2005) - I'll Cover You | 16 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - I'll Cover You | 17 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - I'll Cover You | 19 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - I'll Cover You | 22 | 10 | 4 | 0 | 4 |
| caption | Rent (2005) - I'll Cover You | 24 | 14 | 7 | 9 | 9 |
| caption | Rent (2005) - I'll Cover You | 25 | 14 | 6 | 8 | 8 |
| caption | Rent (2005) - I'll Cover You | 26 | 4 | 2 | 2 | 1 |
| caption | Rent (2005) - I'll Cover You | 27 | 6 | 2 | 4 | 0 |
| caption | Rent (2005) - I'll Cover You | 28 | 8 | 3 | 4 | 4 |
| caption | Rent (2005) - I'll Cover You | 29 | 12 | 4 | 5 | 0 |
| caption | Rent (2005) - I'll Cover You | 34 | 9 | 1 | 3 | 0 |
| caption | Rent (2005) - I'll Cover You | 36 | 8 | 1 | 3 | 3 |
| caption | Rent (2005) - I'll Cover You | 37 | 4 | 1 | 1 | 0 |
| caption | Rent (2005) - I'll Cover You | 38 | 6 | 2 | 4 | 3 |
| caption | Rent (2005) - I'll Cover You | 41 | 6 | 1 | 2 | 0 |
| caption | Rent (2005) - Light My Candle | 21 | 12 | 1 | 1 | 1 |
| caption | Rent (2005) - Light My Candle | 27 | 2 | 1 | 1 | 0 |
| caption | Rent (2005) - Light My Candle | 46 | 11 | 2 | 3 | 4 |
| caption | Rent (2005) - Light My Candle | 49 | 4 | 1 | 1 | 1 |
| caption | Rent (2005) - Light My Candle | 55 | 8 | 1 | 1 | 0 |
| caption | Rent (2005) - Out Tonight | 2 | 10 | 1 | 1 | 0 |
| caption | Rent (2005) - Out Tonight | 3 | 7 | 1 | 1 | 1 |
| caption | Rent (2005) - Out Tonight | 33 | 6 | 1 | 1 | 1 |
| caption | Rent (2005) - Santa Fe | 9 | 9 | 1 | 1 | 0 |
| caption | Rent (2005) - Santa Fe | 16 | 5 | 1 | 1 | 0 |
| caption | Rent (2005) - Santa Fe | 25 | 6 | 1 | 1 | 0 |
| caption | Rent (2005) - Seasons of Love | 26 | 10 | 1 | 1 | 0 |
| caption | Rent (2005) - Seasons of Love | 28 | 6 | 2 | 2 | 0 |
| caption | Rent (2005) - Today 4 U | 1 | 11 | 1 | 1 | 3 |
| caption | Rent (2005) - Today 4 U | 3 | 7 | 1 | 1 | 0 |
| caption | Rent (2005) - Today 4 U | 12 | 11 | 1 | 1 | 1 |
| caption | Rent (2005) - What You Own | 21 | 8 | 3 | 3 | 0 |
| caption | Rent (2005) - What You Own | 24 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - What You Own | 27 | 12 | 5 | 5 | 5 |
| caption | Rent (2005) - What You Own | 28 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - What You Own | 29 | 12 | 5 | 6 | 0 |
| caption | Rent (2005) - What You Own | 30 | 10 | 5 | 6 | 0 |
| caption | Rent (2005) - What You Own | 31 | 8 | 2 | 3 | 3 |
| caption | Rent (2005) - What You Own | 32 | 4 | 2 | 3 | 0 |
| caption | Rent (2005) - What You Own | 34 | 10 | 1 | 2 | 0 |
| caption | Rent (2005) - What You Own | 36 | 8 | 3 | 4 | 0 |
| caption | Rent (2005) - What You Own | 38 | 14 | 4 | 5 | 6 |
| caption | Rent (2005) - What You Own | 39 | 16 | 7 | 8 | 8 |
| caption | Rent (2005) - What You Own | 40 | 9 | 3 | 3 | 2 |
| caption | Rent (2005) - What You Own | 44 | 8 | 2 | 4 | 0 |
| caption | Rent (2005) - What You Own | 45 | 10 | 4 | 5 | 0 |
| caption | Rent (2005) - What You Own | 46 | 12 | 5 | 6 | 0 |
| caption | Rent (2005) - What You Own | 47 | 12 | 5 | 6 | 0 |
| caption | Rent (2005) - What You Own | 49 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - What You Own | 50 | 6 | 1 | 1 | 0 |
| caption | Rent (2005) - Will I | 1 | 5 | 2 | 3 | 2 |
| caption | Rent (2005) - Will I | 12 | 8 | 4 | 4 | 3 |
| caption | Rent (2005) - Will I | 13 | 6 | 2 | 3 | 0 |
| caption | Rent (2005) - Will I | 15 | 8 | 4 | 0 | 4 |
| caption | Rent (2005) - Will I | 17 | 7 | 3 | 4 | 4 |
| caption | Rent (2005) - Will I | 18 | 8 | 3 | 5 | 0 |
| caption | Rent (2005) - Will I | 21 | 7 | 2 | 3 | 3 |
| caption | Rent (2005) - Will I | 22 | 7 | 2 | 2 | 0 |
| caption | Rent (2005) - Will I | 24 | 8 | 3 | 3 | 1 |
| caption | Rent (2005) - Will I | 25 | 3 | 2 | 0 | 3 |
| caption | Rent (2005) - Will I | 29 | 5 | 2 | 3 | 3 |
| caption | Rent (2005) - Without You | 32 | 8 | 3 | 4 | 4 |
| caption | Rent (2005) - Without You | 34 | 4 | 2 | 4 | 4 |
| caption | Rent (2005) - Without You | 35 | 3 | 1 | 2 | 1 |
| caption | Rent (2005) - Without You | 47 | 6 | 2 | 2 | 0 |
| caption | Rent (2005) - Without You | 49 | 6 | 2 | 2 | 2 |
| caption | Rent (2005) - Without You | 50 | 6 | 2 | 3 | 2 |
| caption | Rent (2005) - Without You | 54 | 4 | 1 | 1 | 0 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 25 | 7 | 2 | 3 | 3 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 26 | 6 | 1 | 2 | 2 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 28 | 3 | 1 | 2 | 1 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 51 | 7 | 1 | 2 | 2 |
| caption | S Club 7 - Never Had A Dream C WB9_sf6oV1o | 21 | 8 | 1 | 1 | 0 |
| caption | S Club 7 - Never Had A Dream C WB9_sf6oV1o | 33 | 3 | 1 | 1 | 0 |
| caption | Sara Bareilles - Brave (Offici QUQsqBqxoR4 | 38 | 5 | 1 | 1 | 0 |
| caption | Stephanie Beatriz - Waiting On jKKrfr4To14 | 15 | 7 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - A Summer in Ohio | 11 | 3 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - A Summer in Ohio | 26 | 4 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - A Summer in Ohio | 28 | 5 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - Goodbye Until Tomorrow & I Could Never Rescue You | 64 | 6 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - I Can Do Better Than That | 18 | 11 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - I Can Do Better Than That | 29 | 8 | 1 | 2 | 0 |
| caption | The Last Five Years (2014) - I Can Do Better Than That | 34 | 3 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - If I Didn't Believe in You | 0 | 9 | 2 | 4 | 5 |
| caption | The Last Five Years (2014) - If I Didn't Believe in You | 2 | 9 | 1 | 2 | 2 |
| caption | The Last Five Years (2014) - If I Didn't Believe in You | 3 | 5 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - If I Didn't Believe in You | 26 | 7 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - Moving Too Fast | 0 | 9 | 2 | 3 | 2 |
| caption | The Last Five Years (2014) - Moving Too Fast | 1 | 8 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - Moving Too Fast | 13 | 9 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - Moving Too Fast | 17 | 11 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - Moving Too Fast | 43 | 8 | 1 | 1 | 3 |
| caption | The Last Five Years (2014) - Moving Too Fast | 47 | 6 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - Moving Too Fast | 53 | 9 | 2 | 2 | 1 |
| caption | The Last Five Years (2014) - Moving Too Fast | 54 | 8 | 1 | 1 | 2 |
| caption | The Last Five Years (2014) - Moving Too Fast | 77 | 10 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - Moving Too Fast | 86 | 5 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - See I'm Smiling | 28 | 10 | 2 | 2 | 1 |
| caption | The Last Five Years (2014) - See I'm Smiling | 41 | 13 | 1 | 1 | 4 |
| caption | The Last Five Years (2014) - See I'm Smiling | 43 | 12 | 2 | 3 | 2 |
| caption | The Last Five Years (2014) - See I'm Smiling | 50 | 5 | 2 | 3 | 3 |
| caption | The Last Five Years (2014) - See I'm Smiling | 55 | 8 | 1 | 2 | 1 |
| caption | The Last Five Years (2014) - See I'm Smiling | 58 | 9 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - See I'm Smiling | 61 | 9 | 3 | 3 | 4 |
| caption | The Last Five Years (2014) - See I'm Smiling | 62 | 5 | 2 | 2 | 1 |
| caption | The Last Five Years (2014) - Shiksa Goddess | 25 | 10 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Next Ten Minutes | 43 | 10 | 2 | 3 | 0 |
| caption | The Last Five Years (2014) - The Next Ten Minutes | 45 | 6 | 2 | 3 | 0 |
| caption | The Last Five Years (2014) - The Next Ten Minutes | 50 | 11 | 3 | 5 | 4 |
| caption | The Last Five Years (2014) - The Schmuel Song | 1 | 7 | 1 | 2 | 2 |
| caption | The Last Five Years (2014) - The Schmuel Song | 12 | 5 | 1 | 2 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 13 | 8 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 20 | 7 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 22 | 12 | 2 | 3 | 2 |
| caption | The Last Five Years (2014) - The Schmuel Song | 31 | 7 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 48 | 11 | 1 | 1 | 2 |
| caption | The Last Five Years (2014) - The Schmuel Song | 51 | 7 | 2 | 3 | 1 |
| caption | The Last Five Years (2014) - The Schmuel Song | 54 | 7 | 1 | 1 | 1 |
| caption | The Last Five Years (2014) - The Schmuel Song | 80 | 10 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 94 | 8 | 1 | 1 | 2 |
| caption | The Last Five Years (2014) - The Schmuel Song | 115 | 8 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 116 | 6 | 1 | 1 | 0 |
| caption | The Last Five Years (2014) - The Schmuel Song | 117 | 12 | 2 | 3 | 0 |
| caption | The Lion King (1994) - Can You 25QyCxVkXwQ | 0 | 4 | 2 | 2 | 4 |
| caption | The Lion King (1994) - Can You 25QyCxVkXwQ | 33 | 4 | 1 | 1 | 0 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 0 | 7 | 3 | 5 | 7 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 3 | 6 | 1 | 1 | 0 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 17 | 6 | 2 | 2 | 0 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 50 | 7 | 1 | 1 | 0 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 57 | 12 | 1 | 1 | 2 |
| caption | The Little Mermaid (1989) - Pa SXKlJuO07eM | 0 | 11 | 1 | 2 | 2 |
| caption | The Little Mermaid (1989) - Pa SXKlJuO07eM | 18 | 7 | 1 | 1 | 0 |
| caption | The Little Mermaid (1989) - Pa SXKlJuO07eM | 23 | 3 | 1 | 1 | 1 |
| caption | The Little Mermaid (1989) - Pa SXKlJuO07eM | 31 | 6 | 1 | 1 | 0 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 0 | 11 | 5 | 6 | 6 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 1 | 8 | 1 | 1 | 0 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 5 | 12 | 1 | 1 | 0 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 38 | 2 | 1 | 0 | 1 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 44 | 10 | 1 | 2 | 0 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 50 | 8 | 1 | 1 | 1 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 51 | 10 | 1 | 1 | 0 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 54 | 4 | 1 | 1 | 0 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 71 | 10 | 1 | 1 | 0 |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 12 | 6 | 1 | 1 | 1 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 2 | 7 | 1 | 1 | 0 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 9 | 11 | 1 | 2 | 0 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 13 | 9 | 1 | 2 | 2 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 14 | 9 | 2 | 4 | 2 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 33 | 9 | 1 | 2 | 3 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 36 | 7 | 1 | 1 | 1 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 43 | 9 | 2 | 3 | 2 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 44 | 9 | 3 | 4 | 3 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 45 | 10 | 1 | 0 | 1 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 9 | 7 | 1 | 1 | 0 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 23 | 5 | 1 | 1 | 0 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 24 | 3 | 1 | 1 | 0 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 34 | 4 | 1 | 1 | 0 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 49 | 6 | 1 | 1 | 0 |
| caption | Troy, Gabriella - Breaking Fre 0qj67KE5VXI | 51 | 5 | 1 | 1 | 0 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 5 | 7 | 1 | 2 | 1 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 6 | 10 | 3 | 5 | 4 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 8 | 6 | 1 | 2 | 2 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 16 | 2 | 1 | 1 | 0 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 20 | 6 | 2 | 2 | 0 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 24 | 5 | 1 | 1 | 0 |
| caption | Westlife - My Love (Official V ulOb9gIGGd0 | 38 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 16 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 18 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 22 | 6 | 1 | 1 | 1 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 26 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 32 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 34 | 6 | 1 | 1 | 1 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 36 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 42 | 4 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 48 | 6 | 1 | 1 | 1 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 50 | 6 | 1 | 1 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 52 | 6 | 1 | 2 | 0 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 58 | 3 | 1 | 1 | 1 |
| caption | Whitney Houston - I Will Alway 3JWTaaS7LdU | 11 | 2 | 1 | 2 | 0 |
| caption | Wicked (2003) - For Good TZ0pXUb5jVU | 7 | 9 | 1 | 1 | 0 |
| caption | Wicked (2003) - For Good TZ0pXUb5jVU | 44 | 7 | 3 | 4 | 5 |
| caption | Wicked (2003) - For Good TZ0pXUb5jVU | 45 | 5 | 1 | 2 | 2 |
| caption | Wicked (2003) - For Good TZ0pXUb5jVU | 46 | 6 | 3 | 5 | 0 |
| caption | Wicked (2003) - For Good TZ0pXUb5jVU | 47 | 7 | 1 | 2 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 7 | 8 | 1 | 1 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 17 | 7 | 1 | 1 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 20 | 5 | 1 | 1 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 29 | 8 | 2 | 3 | 2 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 30 | 5 | 1 | 2 | 1 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 36 | 5 | 1 | 1 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 40 | 7 | 1 | 2 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 46 | 8 | 1 | 2 | 2 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 50 | 8 | 2 | 4 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 54 | 4 | 1 | 1 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 62 | 6 | 2 | 2 | 0 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 66 | 10 | 2 | 3 | 4 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 70 | 7 | 1 | 2 | 2 |
| caption | Will Smith - Prince Ali (From  eGLSPyGszjo | 71 | 2 | 1 | 2 | 0 |
| caption | ZAYN & Zhavia Ward - A Whole N rg_zwK_sSEY | 26 | 6 | 3 | 5 | 0 |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 33 | 4 | 1 | 1 | 0 |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 90 | 8 | 1 | 2 | 1 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 30 | 6 | 1 | 1 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 7 | 11 | 2 | 2 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 9 | 11 | 2 | 2 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 15 | 10 | 1 | 1 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 20 | 4 | 1 | 1 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 24 | 5 | 2 | 2 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 25 | 7 | 1 | 1 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 26 | 12 | 1 | 1 | 2 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 28 | 11 | 2 | 2 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 29 | 13 | 1 | 1 | 2 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 36 | 5 | 1 | 1 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 40 | 10 | 1 | 1 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 42 | 12 | 1 | 1 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 46 | 10 | 1 | 1 | 1 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 51 | 10 | 1 | 1 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 53 | 4 | 2 | 2 | 0 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 56 | 4 | 1 | 1 | 0 |
| LRCLIB | Camp Rock (2008) - This Is Me  6HCUoMgviwU | 0 | 7 | 1 | 1 | 0 |
| LRCLIB | Camp Rock (2008) - This Is Me  6HCUoMgviwU | 25 | 8 | 1 | 1 | 0 |
| LRCLIB | Camp Rock (2008) - This Is Me  6HCUoMgviwU | 31 | 8 | 1 | 1 | 0 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 10 | 7 | 1 | 1 | 0 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 23 | 6 | 1 | 1 | 0 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 30 | 10 | 1 | 1 | 0 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 36 | 9 | 2 | 0 | 2 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 37 | 8 | 1 | 2 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 9 | 15 | 1 | 1 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 21 | 6 | 1 | 2 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 26 | 12 | 1 | 1 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 35 | 11 | 1 | 1 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 38 | 5 | 1 | 1 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 42 | 10 | 2 | 3 | 3 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 50 | 7 | 1 | 1 | 0 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 51 | 9 | 1 | 2 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 62 | 10 | 1 | 1 | 0 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 69 | 9 | 1 | 1 | 2 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 76 | 24 | 1 | 2 | 0 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 78 | 10 | 1 | 1 | 1 |
| LRCLIB | Eminem - Lose Yourself (8 Mile xFYQQPAOz7Y | 81 | 13 | 1 | 1 | 2 |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 0 | 10 | 1 | 2 | 0 |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 1 | 9 | 1 | 1 | 0 |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 12 | 7 | 1 | 1 | 0 |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 15 | 12 | 1 | 2 | 0 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 0 | 8 | 2 | 2 | 1 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 1 | 4 | 2 | 2 | 2 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 2 | 13 | 1 | 1 | 0 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 4 | 8 | 1 | 1 | 1 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 43 | 2 | 1 | 2 | 0 |
| LRCLIB | Ingrid Michaelson - You and I XdEN1b-dwlw | 14 | 7 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 9 | 4 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 11 | 6 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 13 | 4 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 17 | 4 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 39 | 4 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 52 | 8 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 55 | 7 | 1 | 1 | 0 |
| LRCLIB | Jessie J - Domino UJtB55MaoD0 | 58 | 8 | 1 | 1 | 1 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 17 | 9 | 1 | 1 | 0 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 32 | 6 | 1 | 1 | 0 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 50 | 9 | 1 | 2 | 1 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 51 | 7 | 1 | 1 | 1 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 52 | 10 | 1 | 1 | 4 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 54 | 8 | 1 | 1 | 2 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 56 | 8 | 1 | 3 | 4 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 57 | 8 | 1 | 1 | 1 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 61 | 6 | 1 | 2 | 0 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 62 | 6 | 1 | 1 | 0 |
| LRCLIB | Jung Kook 정국 - Seven (feat. Latto)---1QYBiNRu1ok | 76 | 9 | 1 | 1 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 0 | 7 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 10 | 7 | 2 | 2 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 20 | 7 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 30 | 8 | 2 | 2 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 32 | 5 | 1 | 1 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 33 | 7 | 3 | 3 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 35 | 5 | 1 | 1 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Go yebNIHKAC4A | 36 | 7 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 1 | 4 | 2 | 2 | 2 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 4 | 12 | 1 | 1 | 5 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 6 | 12 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 19 | 3 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 44 | 12 | 1 | 1 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 48 | 3 | 1 | 2 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 12 | 6 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 17 | 12 | 1 | 1 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 20 | 7 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 26 | 4 | 1 | 2 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 28 | 8 | 1 | 1 | 2 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 30 | 9 | 1 | 1 | 1 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 32 | 8 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 36 | 10 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 38 | 7 | 1 | 1 | 0 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 57 | 4 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Paradise | 5 | 10 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Paradise | 15 | 6 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Paradise | 21 | 10 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Paradise | 22 | 13 | 2 | 3 | 0 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 38 | 5 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 39 | 5 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 40 | 4 | 1 | 1 | 0 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 46 | 4 | 2 | 2 | 0 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 0 | 4 | 2 | 3 | 0 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 1 | 4 | 2 | 1 | 1 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 26 | 8 | 1 | 0 | 1 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 40 | 11 | 1 | 1 | 1 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 58 | 6 | 1 | 1 | 2 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 64 | 4 | 1 | 2 | 0 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 68 | 8 | 1 | 2 | 0 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 69 | 5 | 1 | 0 | 1 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 72 | 7 | 1 | 1 | 0 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 73 | 2 | 1 | 1 | 0 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 74 | 5 | 2 | 2 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 0 | 6 | 2 | 2 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 22 | 8 | 1 | 1 | 1 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 34 | 10 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 50 | 7 | 1 | 2 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 0 | 4 | 1 | 2 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 9 | 5 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 14 | 4 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 21 | 13 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 24 | 5 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 25 | 7 | 1 | 1 | 1 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 26 | 11 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 30 | 5 | 1 | 1 | 1 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 32 | 3 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 35 | 7 | 1 | 1 | 0 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 40 | 6 | 1 | 1 | 0 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 0 | 6 | 1 | 1 | 0 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 11 | 8 | 1 | 2 | 0 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 22 | 6 | 1 | 1 | 0 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 23 | 4 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 2 | 11 | 1 | 1 | 2 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 3 | 11 | 1 | 2 | 2 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 19 | 11 | 1 | 2 | 2 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 27 | 7 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 28 | 7 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Jose & Mar 68LBPvFhMx0 | 38 | 5 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 0 | 9 | 1 | 2 | 2 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 1 | 10 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 27 | 6 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 29 | 12 | 1 | 1 | 1 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 34 | 12 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 53 | 5 | 1 | 1 | 1 |
| LRCLIB | The Lonely Island - Let's Bash hj4e709GYf4 | 54 | 6 | 1 | 2 | 0 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 0 | 7 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 7 | 7 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 10 | 10 | 1 | 1 | 0 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 21 | 5 | 1 | 1 | 1 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 31 | 9 | 1 | 1 | 1 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 4 | 11 | 1 | 1 | 0 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 9 | 9 | 1 | 1 | 1 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 12 | 11 | 1 | 1 | 0 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 13 | 12 | 1 | 1 | 1 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 24 | 9 | 1 | 1 | 0 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 58 | 6 | 2 | 3 | 2 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 61 | 6 | 2 | 3 | 6 |

### Table B: lines rule B aimed where they were heard
Cue: start + offset. Shift: heard start - cue. Window: the heard-aimed align's slice. Lone first: the first heard word starts 2 s or more before the second. Answered: the bundle holds this align's result; if not, the line needs the GPU.

caption: 36 lines in 29 songs; LRCLIB: 18 lines in 12 songs

| Src | Song | Line | Cue | Heard | Shift | Window | Lone first | Answered | Kept | Today | New |
|---|---|---|---|---|---|---|---|---|---|---|---|
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 34 | 133.841 | 131.950 | -1.891 | 131.200-137.856 |  |  |  | 132.950 | 132.950 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 56 | 212.566 | 208.720 | -3.846 | 207.970-215.596 | yes |  |  | 213.438 | 213.438 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 4 | 19.945 | 16.980 | -2.965 | 16.230-22.063 | yes |  |  | 20.200 | 20.871 |
| caption | Backstreet Boys - Shape Of My  OT5msu-dap8 | 41 | 184.887 | 186.700 | 1.813 | 185.950-191.174 |  |  |  | 185.199 | 185.199 |
| caption | Britney Spears - ...Baby One More Time---C-u5WLJ9Yk4 | 40 | 202.597 | 204.260 | 1.663 | 203.510-209.293 |  |  |  | 203.394 | 203.394 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 21 | 121.919 | 116.580 | -5.339 | 115.830-120.275 | yes |  |  | 121.919 | 121.919 |
| caption | Colbie Caillat - Bubbly (Offic AWGqoCNbsvM | 27 | 88.604 | 86.760 | -1.844 | 86.010-92.608 | yes |  |  | 88.750 | 86.680 |
| caption | Céline Dion - Ashes (Deadpool  CX11yw6YL1w | 21 | 180.890 | 178.350 | -2.540 | 177.600-191.612 | yes |  |  | 181.125 | 181.125 |
| caption | Céline Dion - My Heart Will Go 9bFHsd3o1w0 | 19 | 166.064 | 164.330 | -1.734 | 163.580-174.356 | yes |  |  | 166.650 | 166.650 |
| caption | Céline Dion - That's The Way I T6wbugWrfLU | 38 | 216.718 | 219.320 | 2.602 | 218.570-223.976 |  |  |  | 217.280 | 217.280 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 53 | 258.672 | 257.160 | -1.512 | 256.410-262.752 |  |  |  | 258.569 | 256.740 |
| caption | Flight of the Conchords (2007) - Business Time | 59 | 167.328 | 162.300 | -5.028 | 161.550-169.000 | yes |  |  | 167.442 | 167.442 |
| caption | Flight of the Conchords (2007) - Business Time | 81 | 223.203 | 220.120 | -3.083 | 219.370-226.036 | yes |  |  | 223.203 | 223.203 |
| caption | Flight of the Conchords (2007) - Hurt Feelings | 58 | 173.608 | 170.160 | -3.448 | 169.410-172.978 | yes |  |  | 174.075 | 174.075 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 51 | 217.686 | 213.580 | -4.106 | 212.830-218.045 |  |  |  | 217.236 | 217.236 |
| caption | Jung Kook 정국 - 3D (feat. Jack Harlow) (Live)---Z3x9i7njCCo | 47 | 149.919 | 147.500 | -2.419 | 146.750-153.500 |  |  |  | 149.419 | 149.419 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 100 | 409.932 | 408.360 | -1.572 | 407.610-416.414 |  |  |  | 409.802 | 409.802 |
| caption | Justin Timberlake - Selfish je0roKRn3nY | 0 | 18.660 | 17.030 | -1.630 | 16.280-21.495 |  |  |  | 18.710 | 18.568 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 0 | 17.757 | 15.680 | -2.077 | 14.930-21.590 | yes |  |  | 17.467 | 17.438 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 27 | 135.007 | 132.940 | -2.067 | 132.190-137.924 | yes |  |  | 134.800 | 135.038 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 56 | 127.732 | 124.160 | -3.572 | 123.410-129.832 | yes |  |  | 127.700 | 127.700 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 67 | 245.381 | 242.060 | -3.321 | 241.310-247.862 | yes |  |  | 246.038 | 246.038 |
| caption | NSYNC - Gone IbRwSI8yi1o | 51 | 199.807 | 198.200 | -1.607 | 197.450-202.976 |  |  |  | 200.097 | 200.097 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 5 | 27.800 | 25.030 | -2.770 | 24.280-31.675 | yes |  |  | 28.256 | 28.256 |
| caption | NSYNC - Tearin' Up My Heart (O _ZcmuKsyvzg | 18 | 86.293 | 84.320 | -1.973 | 83.570-88.710 | yes |  |  | 86.425 | 86.593 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 40 | 163.060 | 161.440 | -1.620 | 160.690-167.356 |  |  |  | 162.560 | 162.560 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 14 | 56.353 | 54.160 | -2.193 | 53.410-60.290 | yes |  |  | 56.531 | 56.531 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 25 | 85.816 | 88.020 | 2.204 | 87.270-90.613 |  |  |  | 85.814 | 85.814 |
| caption | Rent (2005) - I'll Cover You | 27 | 95.730 | 92.896 | -2.834 | 92.146-100.401 |  |  |  | 95.825 | 95.825 |
| caption | Rent (2005) - I'll Cover You | 40 | 135.603 | 133.840 | -1.763 | 133.090-138.773 | yes |  |  | 135.603 | 135.603 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 55 | 128.734 | 121.160 | -7.574 | 120.410-123.937 |  |  |  | 128.734 | 128.734 |
| caption | The Last Five Years (2014) - See I'm Smiling | 72 | 276.048 | 273.620 | -2.428 | 272.870-277.825 | yes |  |  | 276.418 | 276.418 |
| caption | The Last Five Years (2014) - The Next Ten Minutes | 43 | 207.555 | 203.500 | -4.055 | 202.750-209.131 | yes |  |  | 209.107 | 209.107 |
| caption | The Lion King (1994) - Circle  GibiNy4d4gc | 13 | 117.351 | 118.976 | 1.625 | 118.226-125.892 |  |  |  | 118.905 | 118.905 |
| caption | The Little Mermaid (1989) - Un GC_mV1IpjWA | 0 | 1.893 | 0.200 | -1.693 | 0.000-3.626 |  |  |  | 0.783 | 0.783 |
| caption | The Philosopher Kings - Cry EUW0eDhKoxw | 18 | 113.889 | 112.340 | -1.549 | 111.590-116.994 | yes |  |  | 114.500 | 114.500 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 32 | 143.335 | 141.040 | -2.295 | 140.290-148.115 |  |  |  | 143.425 | 143.425 |
| LRCLIB | Bruno Mars - I Just Might luotSpkyCVU | 18 | 72.976 | 70.120 | -2.856 | 69.370-74.438 |  |  |  | 73.125 | 73.125 |
| LRCLIB | Camp Rock (2008) - This Is Me  6HCUoMgviwU | 25 | 82.858 | 84.660 | 1.802 | 83.910-89.480 |  |  |  | 84.650 | 84.650 |
| LRCLIB | Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 34 | 207.962 | 204.340 | -3.622 | 203.590-216.194 | yes |  |  | 208.125 | 208.125 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 20 | 63.520 | 60.580 | -2.940 | 59.830-63.730 |  |  |  | 63.020 | 63.020 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 48 | 163.420 | 161.780 | -1.640 | 161.030-166.300 |  |  |  | 163.054 | 163.054 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 10 | 24.200 | 22.580 | -1.620 | 21.830-27.380 | yes |  |  | 25.050 | 25.030 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 36 | 106.630 | 108.800 | 2.170 | 108.050-114.420 |  |  |  | 108.920 | 108.920 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 46 | 150.550 | 142.800 | -7.750 | 142.050-145.430 | yes |  |  | 151.025 | 151.025 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 39 | 152.202 | 154.100 | 1.898 | 153.350-166.960 |  |  |  | 152.350 | 152.350 |
| LRCLIB | Ne-Yo - Miss Independent k6M5C-oKw9k | 74 | 249.330 | 250.860 | 1.530 | 250.110-270.600 |  |  |  | 257.725 | 257.725 |
| LRCLIB | Pocahontas (1995) - Colors of  9ThO76peOw0 | 6 | 20.094 | 18.580 | -1.514 | 17.830-32.070 | yes |  |  | 20.649 | 20.649 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 29 | 127.720 | 125.880 | -1.840 | 125.130-132.650 |  |  |  | 126.225 | 126.225 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 31 | 137.010 | 134.980 | -2.030 | 134.230-139.470 |  |  |  | 137.550 | 137.550 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 32 | 139.470 | 137.664 | -1.806 | 136.914-140.700 |  |  |  | 139.470 | 139.470 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 21 | 80.892 | 79.160 | -1.732 | 78.410-83.875 | yes |  |  | 81.624 | 81.624 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 33 | 119.062 | 117.400 | -1.662 | 116.650-122.962 |  |  |  | 118.950 | 119.034 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 42 | 177.616 | 186.656 | 9.040 | 185.906-199.526 |  |  |  | 186.974 | 186.974 |

### Table D: lines rule D aimed where they were heard
Smallest and largest: signed pair offsets (heard - placed).

caption: 15 lines in 10 songs; LRCLIB: 5 lines in 3 songs

| Src | Song | Line | Today | Heard | Pairs | Smallest | Largest | Run | Answered | Kept | New |
|---|---|---|---|---|---|---|---|---|---|---|---|
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 33 | 141.046 | 138.740 | 2 | -2.306 | -2.154 |  |  |  | 141.046 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 38 | 178.920 | 185.460 | 3 | 6.494 | 6.900 |  |  |  | 178.920 |
| caption | Ed Sheeran - Thinking Out Loud lp-EO5I60KA | 43 | 237.725 | 226.370 | 3 | -11.373 | -10.993 |  |  |  | 237.725 |
| caption | Flight of the Conchords (2007) - Robots | 44 | 116.965 | 149.000 | 2 | 32.035 | 42.675 |  |  |  | 116.965 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 75 | 188.471 | 214.060 | 4 | 25.529 | 25.589 |  |  |  | 188.471 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 46 | 150.809 | 167.250 | 4 | 16.441 | 17.201 | yes |  |  | 150.809 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 51 | 168.208 | 171.640 | 5 | 3.432 | 4.016 | yes |  |  | 168.208 |
| caption | Ne-Yo - Closer [Official Video z_aC5xPQ2f4 | 52 | 171.900 | 175.580 | 5 | 2.539 | 3.859 | yes |  |  | 171.900 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 52 | 124.293 | 116.860 | 3 | -7.933 | -7.433 |  |  |  | 124.293 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 54 | 126.593 | 119.040 | 7 | -8.653 | -7.553 | yes |  |  | 126.593 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 56 | 130.353 | 121.900 | 7 | -8.453 | -7.053 | yes |  |  | 130.353 |
| caption | S Club - Bring It All Back GLQ0biK-ZgA | 64 | 150.833 | 125.200 | 4 | -25.653 | -25.553 |  |  |  | 150.833 |
| caption | The Last Five Years (2014) - Goodbye Until Tomorrow & I Could Never Rescue You | 33 | 171.535 | 177.536 | 3 | 3.616 | 6.001 |  |  |  | 171.535 |
| caption | The Last Five Years (2014) - Moving Too Fast | 76 | 281.571 | 285.500 | 2 | 3.929 | 4.249 |  |  |  | 281.571 |
| caption | The Last Five Years (2014) - The Next Ten Minutes | 55 | 267.367 | 273.460 | 2 | 2.725 | 6.093 |  |  |  | 267.367 |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 20 | 98.936 | 101.344 | 2 | 1.504 | 2.408 |  |  |  | 98.936 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 33 | 106.255 | 93.620 | 4 | -12.730 | -11.760 |  |  |  | 106.255 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 49 | 161.990 | 165.540 | 4 | 3.550 | 4.590 |  |  |  | 161.990 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 50 | 162.930 | 169.220 | 2 | 6.290 | 6.810 |  |  |  | 162.930 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 59 | 218.875 | 216.940 | 3 | -2.755 | -1.697 |  |  |  | 218.875 |

Complete lines the rescue left alone, heard and not confirmed, that rule D did not aim, by why:

| Src | first token unheard | run not heard in full | too few pairs | some pair under 1.5 s | pairs off both ways | trigger held, not aimed |
|---|---|---|---|---|---|---|
| caption | 33 | 25 | 0 | 716 | 1 | 0 |
| LRCLIB | 8 | 0 | 0 | 100 | 0 | 0 |

### Table C: lines rule C looked for between their neighbours
Heard shift: heard start - cue start on the audio clock; blank when the line is not heard, its first token is not matched or its run is not heard in full.

caption: 76 lines in 37 songs; LRCLIB: 18 lines in 7 songs

| Src | Song | Line | Cue | Stretch | Length | Heard shift | Run | Answered | Kept | Today | New |
|---|---|---|---|---|---|---|---|---|---|---|---|
| caption | Adele - Someone Like You hLQl3WQQoQ0 | 44 | 217.216 | 215.176-225.239 | 10.063 | -0.476 |  |  |  | 217.216 | 217.216 |
| caption | Ariana Grande & John Legend -  axySrE0Kg6k | 50 | 204.791 | 202.457-213.502 | 11.045 |  | yes |  |  | 204.791 | 204.791 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 81 | 182.983 | 183.364-189.440 | 6.076 |  | yes |  |  | 182.983 | 182.983 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 84 | 189.155 | 188.887-194.480 | 5.593 |  | yes |  |  | 189.155 | 189.155 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 95 | 209.263 | 209.240-214.380 | 5.140 |  | yes |  |  | 209.263 | 209.263 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 98 | 212.886 | 216.900-217.735 | 0.835 |  | yes |  |  | 212.886 | 212.886 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 100 | 214.552 | 214.369-218.620 | 4.251 |  | yes |  |  | 214.552 | 214.552 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 102 | 217.051 | 221.160-222.220 | 1.060 |  | yes |  |  | 217.051 | 217.051 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 104 | 218.717 | 218.614-223.500 | 4.886 |  | yes |  |  | 218.717 | 218.717 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 106 | 221.232 | 225.420-226.460 | 1.040 |  | yes |  |  | 221.232 | 221.232 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 107 | 222.065 | 225.420-226.660 | 1.240 |  | yes |  |  | 222.065 | 222.065 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 64 | 209.594 | 209.897-215.377 | 5.480 |  |  |  |  | 209.594 | 209.594 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 66 | 212.798 | 218.257-218.757 | 0.500 |  |  |  |  | 212.798 | 212.798 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 89 | 267.947 | 267.814-277.711 | 9.897 |  |  |  |  | 267.947 | 267.947 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 22 | 106.799 | 103.556-110.522 | 6.966 | -0.219 |  |  |  | 106.799 | 106.799 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 54 | 155.212 | 151.023-155.907 | 4.884 |  |  |  |  | 155.475 | 155.475 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 93 | 226.137 | 226.226-229.970 | 3.744 |  | yes |  |  | 226.137 | 226.137 |
| caption | Britney Spears - (You Drive Me Q4VK9_CfOLQ | 1 | 6.460 | 3.685-7.025 | 3.340 |  | yes |  |  | 6.875 | 6.875 |
| caption | Britney Spears - (You Drive Me Q4VK9_CfOLQ | 2 | 10.837 | 3.685-18.325 | 14.640 |  | yes |  |  | 11.625 | 11.625 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 4 | 0.317 | 0.760-2.900 | 2.140 |  |  |  |  | 0.317 | 0.317 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 6 | 0.400 | 0.860-2.900 | 2.040 |  |  |  |  | 0.400 | 0.400 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 7 | 0.442 | 0.860-2.900 | 2.040 |  |  |  |  | 0.442 | 0.442 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 8 | 0.483 | 0.860-2.900 | 2.040 |  |  |  |  | 0.483 | 0.483 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 9 | 0.525 | 0.860-2.900 | 2.040 |  | yes |  |  | 0.525 | 0.525 |
| caption | Christina Aguilera - Reflectio RNprQYHenNI | 34 | 148.395 | 144.846-154.123 | 9.277 | 0.065 |  |  |  | 148.395 | 148.395 |
| caption | Céline Dion - That's The Way I T6wbugWrfLU | 32 | 192.049 | 188.737-194.857 | 6.120 | -1.149 |  |  |  | 192.049 | 192.049 |
| caption | Ed Sheeran - Thinking Out Loud lp-EO5I60KA | 42 | 222.619 | 213.114-237.529 | 24.415 |  |  |  |  | 222.900 | 222.900 |
| caption | Flight of the Conchords (2007) - Inner City Pressure | 55 | 165.143 | 160.781-167.973 | 7.192 |  |  |  |  | 165.600 | 165.600 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 44 | 201.319 | 201.082-211.122 | 10.040 |  |  |  |  | 201.319 | 201.319 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 45 | 204.514 | 201.082-211.122 | 10.040 |  |  |  |  | 204.675 | 204.675 |
| caption | Jay Chou 周杰倫 - 龍捲風 (Tornado) RPWDeLqsN0g | 47 | 211.094 | 214.962-218.782 | 3.820 |  | yes |  |  | 211.094 | 211.094 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 33 | 155.375 | 154.900-164.155 | 9.255 |  | yes |  |  | 155.375 | 155.375 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 34 | 156.208 | 154.900-164.155 | 9.255 |  |  |  |  | 156.208 | 156.208 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 35 | 159.763 | 154.900-165.115 | 10.215 |  | yes |  |  | 159.763 | 159.763 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 36 | 161.227 | 154.900-166.735 | 11.835 |  | yes |  |  | 161.227 | 161.227 |
| caption | Jung Kook 정국 - Standing Next t 6q0JnftlH-I | 48 | 181.628 | 178.921-202.357 | 23.436 |  | yes |  |  | 181.628 | 181.628 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 69 | 173.981 | 170.069-173.971 | 3.902 |  |  |  |  | 173.981 | 173.981 |
| caption | Justin Timberlake - CAN'T STOP ru0K8uYEZWw | 101 | 260.401 | 253.634-260.631 | 6.997 |  |  |  |  | 260.401 | 260.401 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 81 | 345.179 | 345.234-351.446 | 6.212 |  | yes |  |  | 345.179 | 345.179 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 117 | 475.876 | 476.169-500.413 | 24.244 |  | yes |  |  | 475.876 | 475.876 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 0 | 0.647 | 0.000-5.500 | 5.500 |  | yes |  |  | 0.825 | 0.825 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 1 | 2.814 | 0.000-18.940 | 18.940 |  | yes |  |  | 3.050 | 3.050 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 4 | 11.835 | 12.237-18.940 | 6.703 |  | yes |  |  | 12.025 | 12.025 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 27 | 97.194 | 93.600-100.967 | 7.367 |  | yes |  |  | 97.564 | 97.564 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 28 | 99.546 | 93.600-106.787 | 13.187 |  | yes |  |  | 99.800 | 99.800 |
| caption | Kelly Clarkson - Breakaway (Of c-3vPxKdj6o | 29 | 101.719 | 93.600-106.787 | 13.187 |  |  |  |  | 102.075 | 102.075 |
| caption | Lewis Capaldi - Before You Go  Jtauh8GcxBY | 26 | 128.048 | 124.965-135.428 | 10.463 | -0.938 |  |  |  | 128.048 | 128.048 |
| caption | NSYNC - Bye Bye Bye Eo-KmOd3i7s | 4 | 30.863 | 27.767-32.168 | 4.401 | 0.757 |  |  |  | 31.050 | 31.050 |
| caption | Ne-Yo - One In A Million 6tpl9LtkRRw | 50 | 131.697 | 132.012-140.445 | 8.433 | 0.643 |  |  |  | 131.697 | 131.697 |
| caption | Ne-Yo - So Sick IxszlJppRQI | 0 | 3.880 | 0.000-4.559 | 4.559 |  | yes |  |  | 4.200 | 4.200 |
| caption | Ne-Yo - So Sick IxszlJppRQI | 1 | 6.466 | 0.000-7.113 | 7.113 |  | yes |  |  | 6.725 | 6.725 |
| caption | Rent (2005) - I Should Tell You | 41 | 150.331 | 148.543-157.490 | 8.947 |  | yes |  |  | 150.331 | 150.331 |
| caption | Rent (2005) - I Should Tell You | 42 | 153.834 | 148.543-160.779 | 12.236 |  | yes |  |  | 153.834 | 153.834 |
| caption | Rent (2005) - I Should Tell You | 44 | 160.340 | 158.881-168.210 | 9.329 |  | yes |  |  | 160.340 | 160.340 |
| caption | Rent (2005) - I'll Cover You | 13 | 46.948 | 47.451-53.091 | 5.640 |  |  |  |  | 46.948 | 46.948 |
| caption | Rent (2005) - Light My Candle | 15 | 73.840 | 70.917-77.233 | 6.316 | 0.400 |  |  |  | 74.175 | 74.175 |
| caption | Rent (2005) - Will I | 16 | 101.132 | 101.798-115.578 | 13.780 |  |  |  |  | 101.132 | 101.132 |
| caption | Rent (2005) - Will I | 20 | 116.620 | 118.534-138.738 | 20.204 |  |  |  |  | 116.620 | 116.620 |
| caption | Rent (2005) - Will I | 23 | 129.688 | 128.717-138.738 | 10.021 | -0.868 |  |  |  | 129.688 | 129.688 |
| caption | Rent (2005) - Will I | 26 | 142.128 | 144.418-170.620 | 26.202 |  |  |  |  | 142.128 | 142.128 |
| caption | Rent (2005) - Will I | 27 | 145.993 | 144.418-170.620 | 26.202 |  |  |  |  | 145.993 | 145.993 |
| caption | Rent (2005) - Will I | 28 | 168.643 | 144.418-170.620 | 26.202 |  |  |  |  | 168.643 | 168.643 |
| caption | Rent (2005) - Will I | 29 | 170.214 | 144.418-170.620 | 26.202 |  |  |  |  | 170.214 | 170.146 |
| caption | Rent (2005) - Without You | 33 | 164.102 | 164.997-173.461 | 8.464 | 0.597 |  |  |  | 164.102 | 164.102 |
| caption | S Club 7 - Never Had A Dream C WB9_sf6oV1o | 41 | 186.626 | 184.121-188.701 | 4.580 | -0.696 |  |  |  | 186.626 | 186.626 |
| caption | Tenacious D - Wonderboy (Offic FL4HSiGvk68 | 4 | 64.725 | 63.048-74.510 | 11.462 |  |  |  |  | 64.950 | 64.950 |
| caption | Tenacious D - Wonderboy (Offic FL4HSiGvk68 | 22 | 144.426 | 142.499-154.114 | 11.615 |  |  |  |  | 144.426 | 144.426 |
| caption | Tenacious D - Wonderboy (Offic FL4HSiGvk68 | 33 | 212.484 | 194.244-221.757 | 27.513 |  |  |  |  | 212.484 | 212.484 |
| caption | The Lion King (1994) - Can You 25QyCxVkXwQ | 49 | 172.724 | 159.935-174.637 | 14.702 |  |  |  |  | 172.724 | 172.724 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 82 | 216.696 | 213.090-220.270 | 7.180 |  | yes |  |  | 216.696 | 216.696 |
| caption | The Lion King (1994) - Hakuna  fwLxDUQBdEg | 84 | 219.949 | 219.541-226.230 | 6.689 |  | yes |  |  | 219.949 | 219.949 |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 39 | 239.667 | 239.622-249.823 | 10.201 | 0.253 | yes |  |  | 239.667 | 239.667 |
| caption | The Philosopher Kings - You Do AI7F8qlN44E | 0 | -0.047 | 0.000-11.568 | 11.568 |  |  |  |  | 0.000 | 0.000 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 54 | 240.982 | 239.943-253.330 | 13.387 | 0.498 |  |  |  | 241.475 | 241.475 |
| caption | Whitney Houston - I Will Alway 3JWTaaS7LdU | 54 | 238.167 | 218.616-245.479 | 26.863 |  | yes |  |  | 238.450 | 238.450 |
| caption | ZAYN - Dusk Till Dawn (Official Video) ft. Sia---tt2k8PGm-TI | 29 | 115.698 | 110.445-123.472 | 13.027 |  |  |  |  | 115.698 | 115.698 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 42 | 183.455 | 181.755-196.952 | 15.197 |  |  |  |  | 183.675 | 183.675 |
| LRCLIB | Frozen (2013) - Do You Want to TeQ_TTyLGMs | 0 | 5.710 | 0.000-5.940 | 5.940 |  |  |  |  | 5.710 | 5.710 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 35 | 113.750 | 111.110-118.110 | 7.000 | -0.550 |  |  |  | 113.750 | 113.750 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 1 | 2.620 | 2.680-9.120 | 6.440 |  | yes |  |  | 3.025 | 3.025 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 2 | 4.780 | 2.680-23.300 | 20.620 |  | yes |  |  | 4.780 | 4.780 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 3 | 7.730 | 2.680-23.300 | 20.620 |  | yes |  |  | 7.730 | 7.730 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 4 | 10.140 | 2.680-23.300 | 20.620 |  | yes |  |  | 10.140 | 10.140 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 5 | 12.940 | 2.680-23.300 | 20.620 |  | yes |  |  | 12.940 | 12.940 |
| LRCLIB | KPop Demon Hunters (2025) - Yo fGyTN5UjnL4 | 6 | 16.590 | 2.680-23.300 | 20.620 |  | yes |  |  | 16.590 | 16.590 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Leave the Door Open---wIyNAsmGrl0 | 39 | 163.215 | 159.801-167.605 | 7.804 |  |  |  |  | 163.215 | 163.215 |
| LRCLIB | Tangled (2010) - When Will My  kRXmAIHYQR4 | 30 | 132.650 | 128.190-147.331 | 19.141 | -1.470 |  |  |  | 132.650 | 132.650 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 35 | 157.476 | 156.580-164.000 | 7.420 |  | yes |  |  | 157.476 | 157.476 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 36 | 158.506 | 156.580-164.000 | 7.420 |  | yes |  |  | 158.506 | 158.506 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 37 | 159.436 | 156.580-166.520 | 9.940 |  | yes |  |  | 159.436 | 159.436 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 39 | 161.446 | 168.300-187.046 | 18.746 |  | yes |  |  | 161.446 | 161.446 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 40 | 162.796 | 168.300-187.046 | 18.746 |  | yes |  |  | 162.796 | 162.796 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 59 | 267.726 | 262.790-263.570 | 0.780 |  |  |  |  | 267.726 | 267.726 |
| LRCLIB | Vitamin C - Graduation (Friend tz_NxOF7RB4 | 61 | 268.966 | 268.590-282.842 | 14.252 |  |  |  |  | 268.966 | 268.913 |

### Table O: other lines whose start or end moved
Lines outside Tables A, G, Z, B, D and C.

caption: 45 lines in 36 songs; LRCLIB: 9 lines in 8 songs

| Src | Song | Line | Start today | Start new | End today | End new | Moved |
|---|---|---|---|---|---|---|---|
| caption | Adele - Someone Like You hLQl3WQQoQ0 | 26 | 130.980 | 130.980 | 139.337 | 139.037 | 0.300 |
| caption | Aladdin (2019) - Speechless mw5VIEIvuMI | 44 | 168.583 | 168.583 | 172.575 | 172.203 | 0.372 |
| caption | Backstreet Boys - As Long As Y 0Gl2QnHNpkA | 44 | 164.807 | 164.807 | 166.771 | 167.287 | 0.516 |
| caption | Backstreet Boys - Drowning GZXHBgjQjNM | 7 | 40.475 | 40.475 | 43.275 | 43.242 | 0.033 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 18 | 55.900 | 55.900 | 57.514 | 57.294 | 0.220 |
| caption | Backstreet Boys - Get Down (Yo 0LSYuZRSGcY | 52 | 123.850 | 123.850 | 125.537 | 125.277 | 0.260 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 29 | 119.025 | 119.025 | 124.540 | 124.260 | 0.280 |
| caption | Backstreet Boys - I'll Never B kDcCSiakaU4 | 67 | 214.525 | 214.525 | 218.657 | 218.457 | 0.200 |
| caption | Backstreet Boys - Inconsolable qGDF_QcsKVI | 36 | 161.734 | 161.734 | 166.755 | 167.473 | 0.718 |
| caption | Backstreet Boys - Quit Playing Ug88HO2mg44 | 39 | 116.790 | 116.790 | 119.283 | 119.263 | 0.020 |
| caption | Backstreet Boys - The Call wMOkm57vu0k | 10 | 21.125 | 21.125 | 23.668 | 23.438 | 0.230 |
| caption | Beauty and the Beast (1991) -  otxTf5hZ0Yw | 61 | 137.175 | 137.175 | 140.775 | 139.964 | 0.811 |
| caption | Britney Spears - Oops!...I Did It Again---CduA0TULnow | 18 | 72.034 | 72.034 | 78.100 | 78.119 | 0.019 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 19 | 111.386 | 111.386 | 116.700 | 116.336 | 0.364 |
| caption | Britney Spears - Stronger AJWtLf4-WWs | 31 | 169.825 | 169.825 | 175.564 | 176.462 | 0.898 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 15 | 61.949 | 61.949 | 65.768 | 64.549 | 1.219 |
| caption | Bruno Mars, Anderson .Paak, Silk Sonic - Smokin Out The Window [Official Music Video]---GG7fLOmlhYg | 35 | 146.968 | 146.968 | 149.270 | 149.090 | 0.180 |
| caption | Cast of Camp Rock - Play My Mu jQ-Pqxl1BlI | 33 | 72.850 | 72.850 | 79.099 | 78.559 | 0.540 |
| caption | Colbie Caillat - Bubbly (Offic AWGqoCNbsvM | 26 | 84.194 | 84.194 | 87.675 | 86.686 | 0.989 |
| caption | Ed Sheeran - Bad Habits [Offic orJSJGHjBLI | 44 | 208.190 | 208.190 | 211.993 | 211.440 | 0.553 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 13 | 80.950 | 80.950 | 84.650 | 84.430 | 0.220 |
| caption | Ed Sheeran - Castle On The Hil K0ibBPhiaG0 | 52 | 255.850 | 255.850 | 258.469 | 256.740 | 1.729 |
| caption | Ed Sheeran - The A Team UAWcs5H-qgQ | 0 | 32.075 | 32.075 | 34.550 | 34.800 | 0.251 |
| caption | Flight of the Conchords (2007) - Carol Brown | 46 | 148.684 | 148.684 | 153.734 | 151.846 | 1.888 |
| caption | Flight of the Conchords (2007) - Carol Brown | 63 | 207.918 | 207.918 | 209.625 | 209.458 | 0.167 |
| caption | Flight of the Conchords (2007) - Hiphopopotamus vs. Rhymenoceros | 35 | 97.366 | 96.619 | 99.806 | 99.789 | 0.747 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 23 | 115.850 | 115.850 | 121.002 | 120.395 | 0.607 |
| caption | John Legend - Love Me Now (Off NmCFY1oYDeM | 53 | 222.961 | 223.455 | 224.322 | 224.564 | 0.494 |
| caption | Justin Timberlake - Mirrors uuZE_IRwLNI | 107 | 444.640 | 444.640 | 448.174 | 448.024 | 0.150 |
| caption | KPop Demon Hunters (2025) - How It's Done | 15 | 39.054 | 39.054 | 41.794 | 41.634 | 0.160 |
| caption | Moana (2016) - You're Welcome 79DijItQXMM | 5 | 8.523 | 8.523 | 9.602 | 9.253 | 0.349 |
| caption | Moana - Cast - Along The Way ( D_dOXTpwV5s | 42 | 121.307 | 121.307 | 124.750 | 124.547 | 0.203 |
| caption | NSYNC - (God Must Have Spent)  -fxh7jAJR8U | 68 | 247.338 | 247.338 | 252.918 | 253.674 | 0.756 |
| caption | NSYNC - Gone IbRwSI8yi1o | 22 | 111.046 | 111.046 | 112.575 | 112.278 | 0.297 |
| caption | NSYNC - Gone IbRwSI8yi1o | 78 | 290.000 | 290.000 | 292.325 | 292.126 | 0.199 |
| caption | Ne-Yo - Because Of You atz_aZA3rf0 | 23 | 87.332 | 87.332 | 91.792 | 92.248 | 0.456 |
| caption | Rent (2005) - Another Day | 50 | 177.225 | 177.225 | 183.025 | 181.651 | 1.374 |
| caption | Rent (2005) - I Should Tell You | 25 | 94.700 | 93.500 | 97.295 | 96.550 | 1.200 |
| caption | Rent (2005) - I Should Tell You | 40 | 146.694 | 146.434 | 150.026 | 149.650 | 0.376 |
| caption | The Last Five Years (2014) - A Summer in Ohio | 33 | 116.765 | 116.765 | 122.425 | 122.225 | 0.200 |
| caption | The Last Five Years (2014) - Moving Too Fast | 16 | 52.750 | 52.750 | 54.672 | 54.514 | 0.158 |
| caption | The Last Five Years (2014) - Shiksa Goddess | 60 | 224.424 | 224.424 | 229.900 | 226.664 | 3.236 |
| caption | The Last Five Years (2014) - The Next Ten Minutes | 44 | 213.369 | 213.369 | 217.607 | 217.267 | 0.340 |
| caption | The Philosopher Kings - Hurts  6X4bhT1FWjI | 10 | 87.825 | 87.825 | 91.253 | 91.537 | 0.284 |
| caption | Whitney Houston - I Wanna Danc eH3giaIzONA | 33 | 159.066 | 159.066 | 161.700 | 161.486 | 0.214 |
| LRCLIB | Backstreet Boys - Chances (Off W5kM5wAwRug | 28 | 129.680 | 129.680 | 133.601 | 132.486 | 1.115 |
| LRCLIB | Frozen (2013) - In Summer (Sin 9tcaM06eGrY | 4 | 18.240 | 18.240 | 23.175 | 21.740 | 1.435 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 18 | 48.200 | 49.030 | 49.390 | 49.390 | 0.830 |
| LRCLIB | Frozen (2013) - Love Is an Ope kQDw88hEr2c | 34 | 76.070 | 76.070 | 78.325 | 77.822 | 0.503 |
| LRCLIB | KPop Demon Hunters (2025) - Ta j5itLHDMJsE | 16 | 49.140 | 49.140 | 53.238 | 51.360 | 1.878 |
| LRCLIB | NSYNC - Paradise | 14 | 110.225 | 110.225 | 112.890 | 112.450 | 0.440 |
| LRCLIB | NSYNC - Thinking Of You (I Dri PodgxWsZw9s | 37 | 145.584 | 145.584 | 149.810 | 149.385 | 0.425 |
| LRCLIB | Silk Sonic (Bruno Mars & Anderson .Paak) - Skate---CEw-7cMnBDY | 10 | 56.500 | 56.500 | 62.500 | 60.120 | 2.380 |
| LRCLIB | The Lonely Island - Threw It O gAYL5H46QnQ | 9 | 36.874 | 36.874 | 41.875 | 42.034 | 0.159 |

### Table V: Table A's counts at other thresholds (sizing only)

| HEARD_AGREE_S | HEARD_MIN_WORDS | caption A1 kept | caption A2 held | LRCLIB A1 kept | LRCLIB A2 held |
|---|---|---|---|---|---|
| 0.500 | 2 | 10 | 119 | 7 | 20 |
| 1.000 | 2 | 17 | 29 | 10 | 7 |
| 1.500 | 2 | 31 | 11 | 14 | 1 |
| 0.500 | 3 | 5 | 107 | 3 | 19 |
| 1.000 | 3 | 12 | 25 | 4 | 6 |
| 1.500 | 3 | 22 | 11 | 6 | 1 |

(Phase 4c pastes its tables here.)
