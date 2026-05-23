# Joint Alignment DP — One Matcher, Two Signals

Model: Claude Opus 4.7

## Motivation

Every lyric-alignment failure we've debugged shares one structural cause: **the
pipeline uses align+walk as both the matcher and its own quality judge.** Each
new failure mode has forced us to invent another self-judge gate (fail_ratio,
collapse_ratio, concentration, coverage_cap, the proposed walk-content gate),
and a novel failure keeps slipping past whichever gate is current.

The Hakuna Matata case is the proof: walk fuzzy-matched lyrics 31-39 against
dialogue audio at 118-130s while the actual sung reprise sat at 200-220s
completely uncovered. `max_loss_run=0`, no collapse, no signal walk could
emit. The structural problem is that walk only looks at *the lyric text* —
it cannot judge whether the audio it matched against was the right audio,
because it never consulted the audio independently of the lyrics.

`transcribe()` is exactly that independent consultation: it hears the audio
without knowing the lyrics. Today we only invoke it as an emergency reroute
for known-failed sections. That keeps transcribe quarantined from the
default path and leaves clean-song failure modes (Hakuna) undetectable.

The fix is to make `transcribe` a first-class input alongside `align`, and
let one matcher reconcile both against the lyric file in a single DP — no
gating, no mode-flipping, no per-failure rerouting. The lyric file is the
state sequence to decode through; align and transcribe are two emission
distributions. The natural decoder is Viterbi / interval-scheduling DP.

The existing tiling matcher is one step from this — it already does
non-overlapping ordered candidate selection. It just only consumes one
signal. Extend it to consume both and the entire routing layer collapses
into a single algorithm.

## Architecture

```
align()    ─── per-lyric-token timings (forced; precise when right) ─┐
                                                                       ├─→ joint-DP matcher ─→ line_objects
transcribe (no internal refine) ─── ASR words + word_timestamps   ─┘                          (per-word timed)
        ↑                                                                                ↑
        independent of lyrics                                                            per-word timings come
                                                                                          from the source that won
                                                                                          each line
refine_from_cached()  whole-song refine on the align result (today's call, unchanged — sharpens align's per-word
                       timings, which is where the majority of lines read their per-word timing from)
```

No routing layer. No `match_method` trichotomy. No repair path. No gates.
One matcher, one pass.

## Inputs to the matcher

- `lyrics_lines: list[str]` — display lines (existing).
- `align_lines: list[str]` — normalized lines for matching (existing).
- `align_words: list[dict]` — refined per-token timings from forced alignment.
- `transcribe_words: list[dict]` — unrefined ASR words with `word_timestamps`.

The matcher returns `line_objects` and `joint_stats` (the new capture).

## Candidate generation per lyric line

For each lyric line `l_k`:

1. **Align candidate.** Read align_words for `l_k`'s tokens and take the
   span `[t_a_start(l_k), t_a_end(l_k)]`. One candidate. If align placed
   every token at one timestamp (the "Next Ten Minutes" collapse), the span
   is degenerate (near-zero width) — that candidate then conflicts with
   any other line's candidate at the same place under the non-overlap
   constraint, so the DP naturally rejects it.
2. **Transcribe candidates.** Reuse `tiling_match.find_candidates` /
   `find_anchor_candidates` to find positions in `transcribe_words` where
   `l_k`'s text fuzzy-matches. Zero, one, or many candidates per line.

Every candidate carries `(line_id, t0, t1, source, scores)` where `source`
is `"align" | "transcribe"`.

## Scoring (the one knob α)

For a candidate `c = (l_k, t0, t1)` from either source:

```
transcribe_match(c) = matched_token_count(l_k, transcribe_words ∩ [t0-m, t1+m])
align_agreement(c)  = 1 if c is an align candidate, OR
                      penalty in [0, 1] reflecting |window − align_predicted(l_k)| / line_duration
                      (used so transcribe candidates near align's predicted time still get a small bonus,
                       not just align candidates)

score(c) = transcribe_match(c)  +  α · align_agreement(c)
```

`α` is the **one tuning knob**: weight on the align prior. Roughly the
number of "free" matched-tokens an align candidate gets credit for just by
being where align placed it.

Worked example — Hakuna line 31 ("It means no worries for the rest of your
days", 9 tokens):

| candidate | transcribe_match | align_agreement | score (α=4) |
|---|---|---|---|
| align @ 118-122s (dialogue) | 1 ("no") | 1.0 | 1 + 4 = **5** |
| transcribe @ 200-205s (sung) | 8 | 0.0 (≠ align) | 8 + 0 = **8** ✓ |

Worked example — a clean song line where both agree:

| candidate | transcribe_match | align_agreement | score (α=4) |
|---|---|---|---|
| align @ 47-50s | 6 | 1.0 | 6 + 4 = **10** ✓ |
| transcribe @ 47-50s (same window) | 6 | 0.9 | 6 + 3.6 = **9.6** |

The align candidate wins by α-bonus; DP selects align's window; per-word
timings come from align (precise). The same DP cell can subsume both.

Worked example — clean line, transcribe missed it (quiet vocal):

| candidate | transcribe_match | align_agreement | score |
|---|---|---|---|
| align @ correct time | 0 | 1.0 | α = **4** ✓ |
| transcribe | (no candidates) | — | — |

DP keeps the align candidate. Line placed at align's time. Better than
today's tiling-only path which would have dropped this line.

## DP

`best_tiling` in `tiling_match.py` already implements non-overlapping
interval scheduling by score. Reuse verbatim, fed the unified candidate
set. The non-overlap + lyric-order constraints together provide the same
monotonicity guarantee walk gave us.

For lines with no selected candidate (no transcribe match *and* align's
candidate lost or was degenerate), interpolate between bracketing selected
neighbors — same idea walk uses today for short unmatched runs, lifted to
the line level (since the DP works at line granularity).

## Per-word timing sourcing

After DP picks one window per line:

- **`source == "align"`** (the majority of lines on clean songs and on the
  agree-portion of mixed songs): read per-word timings straight from
  align_words for `l_k`'s tokens. These are the refined, precise timings
  that walk gives us today.
- **`source == "transcribe"`** (the lines where align lost): use
  `tiling_match._map_words_to_line` (existing) to map lyric words to
  transcribe words within `[t0, t1]`. Timings come from transcribe's
  `word_timestamps`. Less precise than refined-align (no refine of
  transcribe — see next section), but precise enough for karaoke
  (~100-200ms) and a vast improvement over today's Hakuna behaviour where
  those lyrics were 80 seconds wrong.

## Refine: one whole-song pass on align, none on transcribe

The current `refine_from_cached(result_id, vocal_path)` call stays
unchanged — whole-song refine on the align result. This sharpens per-word
timings exactly where the majority of lines will read from.

Transcribe runs **without internal refine**. This saves one whole-song
refine pass that today's `transcribe_words` pays inside the worker. Add a
kwarg to the existing worker method:

```python
def transcribe_words(self, vocal_path, cancel_event, refine: bool = True): ...
```

D's call site passes `refine=False`. The default stays True for any
remaining `--match-method=tiling` callers (preserving behaviour).

The small concession: refine runs over every align segment, including the
~5-15% of lines that DP will route to transcribe. That refine work is
discarded on those lines. Sectional refine becomes a future optimisation
if the corpus ever shows it matters; for now, one whole refine call is
both simpler and the same cost as today's keep-walk path.

**Total cost per song under D:** `align + refine(align) + transcribe(no
refine)`. Compared to today's `keep_walk` path: +1 transcribe. Compared
to today's `walk+repair` path: −1 refine inside transcribe (slightly
cheaper). Compared to today's `whole_tiling` path: gains an align +
refine (more expensive, but those songs were the broken ones — accuracy
matters more than the saved align).

## Per-file changes

### `pikaraoke/lib/joint_match.py` (new)

```
match_words_to_lines_joint_with_stats(
    align_words, transcribe_words, lines, align_lines,
    *, alpha: float = 4.0, margin_s: float = 0.3,
) -> tuple[list[dict], dict]
```

Single entry point. Internally:
1. Build per-line candidate set (align candidate + tiling candidates).
2. Score each candidate via `score = transcribe_match + α · align_agreement`.
3. Run `best_tiling` (imported from `tiling_match`).
4. For selected windows, sourcing-aware per-word timing.
5. Line-level interpolation for unplaced lines.
6. Return `line_objects` and `joint_stats`:
   - `n_candidates_per_line`
   - `selected_source_per_line` (`"align" | "transcribe" | "interp" | "absent"`)
   - `align_won_fraction`
   - `transcribe_won_fraction`
   - `interpolated_line_ids`
   - `alpha_used`

### `pikaraoke/pipeline/workers/whisper_worker.py`

- Add `refine: bool = True` kwarg to `transcribe_words`. Default preserves
  today's behaviour. D passes `refine=False`. The flag flows into
  `_run_job` and the worker's transcribe handler — skip the `Refiner` step
  when False.

### `pikaraoke/pipeline/stages/lyric_align.py`

Substantial cleanup. The `LyricAlignStage.run` becomes:

```
align_check → refine_from_cached → transcribe_words(refine=False) →
    match_words_to_lines_joint_with_stats(...) → line_objects
```

No `_decide_route`, no `_build_repair_ranges`, no `_repair_spans`, no
`_splice_range`, no `_make_clip_provider`, no `_make_whole_song_provider`,
no `WordsForWindow`, no `_words_for_window`, no `keep_walk`/`repair`/
`whole_tiling` trichotomy. Net deletion is large.

`--match-method=walk` (forced) and `--match-method=tiling` (forced) survive
as escape hatches for offline comparison: the stage dispatches to walk or
tiling-only matchers in those modes. Default `match_method` becomes
`"joint"`.

### `pikaraoke/pipeline/config.py`

Removed:
- `align_failure_escalation`
- `collapse_escalation_threshold`
- `concentration_escalation_run`
- `repair_max_line_fraction`
- `repair_window_margin_s`
- `repair_clip_transcribe`
- `repair_clip_min_duration_s`

Added:
- `joint_alpha: float = 4.0` (the one knob — set from corpus sweep).
- `joint_margin_s: float = 0.3` (margin around candidate windows for
  word-set inclusion; reuses today's `repair_window_margin_s` value).

`match_method` default becomes `"joint"`. Allowed values:
`"joint" | "walk" | "tiling"` (the latter two for forced-mode testing).

### `pikaraoke/lib/alignment_capture.py`

Schema bumps to **v5** (renames/removals — bump required):
- `pipeline_decisions` loses `align_check_fail_ratio`, `collapse_ratio`,
  `max_loss_run`, `escalation_trigger`, `escalated_to_tiling`,
  `repair_ranges`, `repair_words_source`. Method values are now
  `"joint" | "walk" | "tiling"`.
- New: `joint_stats` top-level field with the fields listed above.
- `walk_stats` / `tiling_stats` remain present *only* when the forced
  walk-/tiling-only modes ran (otherwise null).

### Files removed entirely

- `pikaraoke/lib/word_alignment.py` if walk is retired (Phase 3 below).
  Initially keep — the `--match-method=walk` escape hatch uses it.

### Tests

- `tests/unit/test_joint_match.py` (new): candidate generation, scoring,
  DP selection, sourcing, interpolation, the Hakuna-shaped synthetic case
  (align candidate at wrong time + transcribe candidate at right time →
  transcribe wins), the chorus-repetition case.
- `tests/unit/test_lyric_align.py`: replaced the routing tests with
  joint-mode tests (one happy path, one Hakuna-shape, one all-clean).
- `tests/unit/test_word_alignment.py`: kept (covers the `match_method=walk`
  escape hatch).

## What gets deleted

This is the headline simplification:

- Walk's interp/collapse/loss_spans machinery (the `loss_spans` field on
  `walk_stats`, the collapse-demotion logic with its `max_collapsed_run` /
  `collapse_window` / `max_interp_run` / `min_interp_slot` knobs) survives
  only for the `--match-method=walk` escape hatch. The default path no
  longer cares.
- All routing knobs (`align_failure_escalation`,
  `collapse_escalation_threshold`, `concentration_escalation_run`,
  `repair_max_line_fraction`).
- The entire repair pipeline (`_repair_spans`, `_build_repair_ranges`,
  `_splice_range`, `_make_clip_provider`, `_make_whole_song_provider`,
  `_words_for_window`, `WordsForWindow`, `Phase.CLIP_EXTRACT`,
  `_extract_clip_wav`, `_pad_to_min_duration`, the
  `repair_clip_transcribe` / `repair_clip_min_duration_s` /
  `repair_window_margin_s` knobs).
- The `escalation_trigger` axis on `pipeline_decisions` and its
  `"concentration" | "coverage_cap" | "collapse_ratio" | "fail_ratio"`
  enumeration.

## Cost analysis

| route | today's cost | D's cost | delta |
|---|---|---|---|
| clean song (today: walk) | align + refine | align + refine + transcribe(no refine) | + 1 transcribe |
| concentrated failure (today: repair) | align + refine + transcribe(+refine) | align + refine + transcribe(no refine) | − 1 refine |
| broken everywhere (today: whole_tiling) | transcribe(+refine) (discards align) | align + refine + transcribe(no refine) | + align, ± refine wash |

The corpus split (23 songs): 12 clean / 8 repair / 3 broken-everywhere. So
net across the corpus: about +12 transcribes and −8 refines and +3 align
runs. Given transcribe and align are "short compared to refine" (your
words) and refine is the dominant cost, **D is roughly cost-neutral
overall**, while gaining structural correctness on Hakuna-class failures.

## Tuning α from the corpus

The 23 bundles already carry:
- `walk_stats.align_words` (for the 7 tiling-method songs we backfilled
  with offline align)
- top-level `words` for the rest (refined align words for walk bundles)
- `lyrics.lines` / `lyrics.align_lines`

We still need **transcribe words** for the 16 walk songs whose bundles
were captured before transcribe ran. Offline transcribe of their cached
vocal stems mirrors the offline-align backfill (`/tmp/enrich_bundles.py`
in the previous corpus work) — one more GPU pass, then every bundle has
both inputs to the joint DP.

Then sweep α in `{1, 2, 4, 6, 8, 12, 16}`:
- For each (song, α): run the joint matcher offline and record per-line
  `selected_source` (align vs transcribe).
- Compare to a labelled "correct route per line" derived from the
  cross-checked output we now have on disk for the 5 test-set songs.
- Pick the α that minimises misroute count.

The shape we expect: at low α, transcribe noise wins on clean songs
(regression). At high α, Hakuna-style failures stick to align. The
plateau between sets α.

## Open questions

- **Initial α.** Prior: 4.0 — gives an align candidate the credit of ~4
  matched tokens just for being where align placed it, which is roughly
  one short line. Loose enough that an 8-token transcribe candidate
  overpowers it (the Hakuna shape); tight enough that single-token
  transcribe noise in a clean region can't dethrone align. **Confirm via
  the sweep above before flipping the default `match_method`.**
- **Chorus repetition.** The DP's non-overlap + ordered selection
  constrains repeats the same way today's tiling does. The α-bonus on
  align candidates means align's monotonic prediction for chorus
  instance #3 actively pulls toward instance #3 even when instance #1's
  transcribe match is equally strong. Likely resolved; the test should
  include a synthetic chorus case and one corpus chorus song (e.g.
  Bloodstream — multiple "I think I might've inhaled you" repeats).
- **Per-word timings inside transcribe-won windows.** The lyric→
  transcribe-word mapping inside a selected window (today done by tiling)
  is correct when the transcribe text closely matches the lyric — fuzzy
  match on a 9-token line with 7/9 transcribe-word matches. If transcribe
  badly misheard most words inside the chosen window, per-word timings
  fall back to interpolation across the window. Acceptable; the same
  failure exists today on the repair path.
- **Walk retirement.** Phase 3 question. If the corpus shows joint mode
  never loses to walk on clean songs, walk and `word_alignment.py` can be
  deleted entirely. Keep until we have that evidence.

## Testing

Unit:
- Candidate generation: align candidate's window matches align_words'
  span; transcribe candidates reuse tiling's existing finders.
- Scoring: documented formula; α=0 reduces to tiling-only behaviour; α=∞
  reduces to align-only behaviour (with monotonicity from DP).
- DP selection: Hakuna synthetic (align at wrong time, transcribe at
  right time, transcribe wins); clean synthetic (align and transcribe
  agree, align wins via bonus); align-only synthetic (no transcribe
  candidates, align wins).
- Per-word timing source: align-won line reads align_words timings;
  transcribe-won line reads transcribe_words timings.
- Interpolation: unmatched line between two placed neighbors gets
  interpolated start/end.

Integration (mocked worker):
- joint route end-to-end on a Hakuna-shape input; assert the late lyric
  lines are placed in the sung-reprise region, not the dialogue region.
- `--match-method=walk` still works (regression guard for the escape
  hatch).
- `--match-method=tiling` still works.

Corpus regression:
- Re-run all 5 test songs (Best Part of Me, Popular, Bloodstream,
  Pocahontas, Hakuna Matata) under D; compare `.ass` dialogue counts
  against today's outputs. Hakuna should now place the late lyric lines
  at 200-240s (the sung reprise) rather than crammed at 124-130s. The
  others should match or exceed today's line counts.

## Staging

1. **Joint matcher in isolation.** Add `pikaraoke/lib/joint_match.py`
   and its unit tests. No stage integration yet. Validate on the corpus
   offline: load each bundle's align + transcribe words (backfilling
   transcribe for the 16 walk songs that lack it), run the matcher,
   sweep α, print per-song agree/disagree fractions.

2. **Worker refine kwarg.** Add `refine: bool = True` to
   `transcribe_words`. Default preserves behaviour. One small worker
   change, isolated test.

3. **Stage integration (behind config).** Add `match_method="joint"`
   as a non-default option. `LyricAlignStage` dispatches to the joint
   matcher when `match_method == "joint"`. Backfill the 5 test songs
   with `match_method=joint`, compare outputs.

4. **Flip the default.** `match_method="joint"` becomes the default.
   Remove the routing knobs and repair-path code. Schema bump to v5.
   Update capture and tests.

5. **(Future) Sectional refine.** If profiling shows refine cost is
   pressing, slice the align WhisperResult to selected-align-window
   segments before refining. Defer until measured.

6. **(Future) Walk retirement.** Once joint mode is the corpus-validated
   default, delete `word_alignment.py` and the walk escape hatch.

## Why this is the right size of change

- Smaller code than today's routing+repair layer (large net deletion).
- One tuning knob (α) replaces four (`align_failure_escalation`,
  `collapse_escalation_threshold`, `concentration_escalation_run`,
  `repair_max_line_fraction`).
- Covers every failure mode we've debugged (Next Ten Minutes, Hakuna,
  Bloodstream-broken-anchors) with one mechanism.
- Reuses the tiling DP we already have; doesn't invent new infrastructure.
- The corpus we curated is exactly the validation set.
- The cost shift is small and in the direction you've already said is
  affordable.
