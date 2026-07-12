# Edge snap: coverage and accuracy improvements

Model: Claude Sonnet 5 (executor, 2026-07-12 — was Opus 4.8; escalate to
Opus on any spec mismatch, see the executor-discipline bullet under Process)

Execution plan for extending the edge snap feature (`pikaraoke/lib/onset_snap.py`)
to more cases — single-word lines, interior run edges — and improving its
accuracy, folding in the six findings from the user's review in
`plans/edge-snap-review-interleaved.md`. Designed and validated (corpus scan +
17-song reference study) in a prior session; this doc is written so it can be
executed phase by phase without re-deriving the analysis.

All file/line anchors are valid as of commit `89d28c46` (tip of
`onset_snap_on_ship`). If the file has drifted, re-anchor by symbol name, not
line number.

Note (2026-07-12): `fable_matcher_refine`'s Phase 3b commit (`5625d855`) also
touched `onset_snap.py` — `_decode_env` renamed to public `decode_env_db`,
`snap_line_edges` gained an optional `env=` parameter — and the veto in
`lyric_align.run()` calls it. Off `89d28c46` those changes are absent, so
this plan's anchors hold; expect a small `onset_snap.py`/`lyric_align.py`
merge when the two branches integrate, and keep both signatures additive so
it stays mechanical.

## Context

The edge snap repairs two systematic whisper errors against the vocal stem's
RMS envelope, wired into `LyricAlignStage.run()` at
`pikaraoke/pipeline/stages/lyric_align.py:192-197` via `snap_line_edges`
(onsets first, then ends, one envelope decode):

- **Onset snap** (`snap_line_onsets`): whisper smears a line-opening word's
  start back into the preceding instrumental gap; the detector finds the first
  qualifying energy rise in `[word1.start, word2.start]` and pulls the start
  forward to it. Forward-only, bounded by word 2.
- **End snap** (`snap_line_ends`): whisper clips a held line-final word when
  its phonetic content stops; when the voice is still near sung level at the
  claimed end (clip evidence), the detector traces the voiced run to its first
  sustained fall. Extend-only, bounded by the next line's first word.

Both gate on a per-line sung-level reference: `_sung_level_ref` = median
envelope level over words 2..n (word 1 excluded because its span is the thing
being repaired).

### Measured ground truth (do not re-derive; re-measure only in Phase 0)

Corpus scan over `/home/ken/pikaraoke-songs` (1791 lines):

- **64 single-word lines** are skipped on both edges by the `len(words) < 2`
  gates. Median duration 1.04s, max 5.62s; 35 are >= 1s held notes — the
  exact shape both snaps exist to repair. This is the headline coverage gap.
- **114 multi-word lines** are skipped by `w2s - w1s < MIN_WORD_DUR_S`. Not
  worth chasing: the clamp `new_start <= w2s - MIN_WORD_DUR_S` caps any shift
  below `MIN_SHIFT_S` by construction, so the skip is exact, not conservative.
- **388 interior words** sit after an intra-line gap >= 0.5s. The ASS writer
  re-anchors at every inter-word gap, so these show the same smear/clip
  artifacts; they are out of scope only because the walk visits line edges.

Reference study (17-song sample, 909 multi-word lines, 36 single-word lines),
comparing the current reference (median over words 2..n) against an 80th
percentile over ALL word spans:

- On multi-word lines the percentile sits median **+2.2 dB** above the current
  reference, p90 +5.3 dB, and **7.2% of lines differ by > 6 dB**. A blanket
  swap would silently retune `NEAR_SUNG_DB` / `SUSTAIN_NEAR_DB` / `MIN_REF_DB`
  corpus-wide. **Rejected** as a global change; used only where the current
  reference cannot exist.
- On single-word lines, the percentile of the word's own span yields a usable
  reference (>= `MIN_REF_DB`) for **35 of 36**; the one rejection is a
  genuinely misplaced line landing at the floor — the correct outcome. The
  percentile is robust to the defect being repaired because smeared gap frames
  are *low* outliers: as long as >= 20% of the claimed span is truly sung, the
  80th percentile lands inside the sung level.

### Do not do (already analyzed and rejected)

- **Blanket percentile reference for multi-word lines** — retunes every
  threshold (see study above). Fallback for single-word lines only.
- **The 114 narrow-window lines** — max possible shift is below `MIN_SHIFT_S`.
- **Moving the end-side `n_fired += 1` below the `MIN_SHIFT_S` gate** (one of
  review #2's two options) — that would make `n_fired` identically equal to
  `n_extended` and thus useless. Add an `n_below_min_shift` counter instead
  (the review's other option).

## Process

- Branch: `git checkout -b edge_snap_refine 89d28c46`. Commit this plan first
  (`docs(plan): edge snap coverage and accuracy plan`). Never commit to
  `master`.
- Environment: conda env `pik`. Tests:
  `/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/ -q`
  (~1315 tests; `tests/unit/test_onset_snap.py` has 28 and is where all new
  tests go). Pre-commit:
  `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
  (`plans/` is excluded by policy).
- Corpus harness: `/home/ken/miniconda3/envs/pik/bin/python
  scripts/edge_snap_ass.py` from the repo root (takes a few minutes; decodes
  every vocal stem). Save stdout to the session scratchpad after every phase
  that changes behavior and diff against the previous phase's stdout.
- Public signatures of `snap_line_onsets`, `snap_line_ends`,
  `snap_line_edges` must not change — `lyric_align.py:195` and the three
  `scripts/*_snap_ass.py` harnesses call them. `_sung_level_ref` is private
  and may gain parameters.
- Test style: use the existing `_env` / `_line` helpers and `use_env` fixture
  in `tests/unit/test_onset_snap.py:23-48`. `_env` floor is -60 dB. For every
  new test, compute the expected snap/extend values from the constants
  (arithmetic given per phase below), then confirm by running — the release
  trace triggers on a *windowed mean*, so releases land a few frames before
  the visual edge (worked example in Phase 4).
- One commit per phase, tests riding with the code. After Phase 5, stop and
  alert the user that the batch is ready for `/code-review` (policy: reviews
  are batched at checkpoints, never auto-launched).
- Keep a Results log at the bottom of this file: per phase, the harness totals
  and the diff summary vs the previous phase.
- Executor discipline (Sonnet 5, added 2026-07-12): the phases assume a
  literal executor. If a stated anchor, constant, expected value, or worked
  example does not match the code or corpus — STOP and report the exact
  mismatch; never bridge it with your own design, and never tune a constant
  the phase does not name. Every Results-log number comes from a
  harness/test run in that session with the invocation recorded;
  "unchanged" claims come from a real diff of the saved stdout files, not
  an eyeballed table. A failing test is a STOP, not a retry-until-green.
  Phase 7 items are study-only — each ends at STOP + report, and 7d is
  design work that goes to the user before any implementation regardless
  of what telemetry shows.

## Phase 0 — Baseline

No code changes. Run the full test suite (must be green) and the harness; save
stdout as the baseline artifact and record the totals line (expected order of
magnitude from prior sessions: ~400 onset snaps, ~520 fired / ~410 extended,
~240 `to_bound`, out of ~1790 lines — re-measure, don't trust these numbers).

## Phase 1 — Symmetric silence gate on the onset path (review #4)

**Prerequisite for Phase 4**: the single-word design leans on `MIN_REF_DB`
rejecting floor-level references, and the onset path has no such gate today.

**Change** (`snap_line_onsets`, after the `ref is None` check at
`onset_snap.py:203-206`, *before* the on-time guard at `218-225`):

```python
if ref < MIN_REF_DB:
    n_low_ref += 1
    out.append(obj)
    continue
```

Initialize `n_low_ref = 0` alongside `snaps`, add `"n_low_ref"` to the onset
stats dict. Placement before the guard matters: over near-silence the
reference drags to the floor and the guard becomes trivially true — the gate
must own that rejection, not the guard.

**Test** — `test_line_in_silence_untouched` in `TestSnapLineOnsets`
(mirror the end-side test at `test_onset_snap.py:314`). Construction where the
guard does NOT fire and a rise WOULD be accepted without the gate, so the test
actually discriminates:

- `_env(8.0, [(2.5, 3.0, -48.0), (3.2, 4.0, -50.0)])`
- line `_line((2.0, 3.0), (3.2, 3.5), (3.6, 4.0))`
- ref = median over words 2..3 spans = -50 < `MIN_REF_DB` (-45) → gated.
- Without the gate: guard start check is -60 >= ref - 8 = -58 → False, guard
  passes it through; the -60→-48 bump at 2.5s is a 12 dB step landing above
  ref - 8 = -58 with a passing continuity median, so it would snap to 2.45.
- Assert: line untouched, `stats["n_low_ref"] == 1`, `n_snapped == 0`.

**Harness**: add onset `n_low_ref` to the per-song and totals prints in
`scripts/edge_snap_ass.py` (per-song line at `62-66`, totals at `112-117`).

**Verify**: suite green; harness diff vs Phase 0 — snap records should be
identical or nearly so (the gate mostly claims lines the guard already
skipped); record the onset `n_low_ref` total.

Commit: `fix(onset-snap): reject low-reference lines on the onset path too`

## Phase 2 — Telemetry symmetry (reviews #2 and #6, plus sizing counters)

All counters, no behavior change. These make every later phase's tuning
data-driven and give Phase 7 its GO/NO-GO numbers.

**End path** (`snap_line_ends`): add `n_below_min_shift`, incremented in the
`new_end - w_end < MIN_SHIFT_S` rejection at `onset_snap.py:342-344`. Leave
`n_fired` where it is (`326`) — its meaning stays "clip evidence present".
Resulting invariant to state in a comment and assert in tests:
`n_fired == n_extended + n_below_min_shift`.

**Onset path** (`snap_line_onsets`): mirror the end path's counters —

- `n_fired`: incremented when a line passes the on-time guard (i.e., shows
  smear evidence and reaches rise detection).
- `n_no_rise`: `_detect_rise` returned None.
- `n_below_min_shift`: the `new_start - w1s < MIN_SHIFT_S` rejection at
  `233-235`.
- `n_undetectable`: among fired lines, those where the step detector cannot
  possibly qualify a rise: `ref - p20(window) < STEP_DB`, with
  `p20 = float(np.percentile(env[int(w1s / HOP_S) : int(w2s / HOP_S)], 20))`
  (clamp indices into the envelope; the window is >= `MIN_WORD_DUR_S` = 4
  frames, so it is non-empty). Count and continue — do NOT skip the line;
  this is a measurement for Phase 7b, not a gate.
- Invariant: `n_fired == n_snapped + n_no_rise + n_below_min_shift`.

**Both paths**: add `n_single_word`, counting lines with exactly one word
(currently skipped at the `len(words) < 2` gates; Phase 4 re-purposes the
counter to "single-word lines seen", same definition).

**Tests**: extend existing tests with stats assertions rather than writing new
ones — `test_shift_below_jitter_threshold_untouched` asserts onset
`n_fired == 1`, `n_below_min_shift == 1`; `test_no_rise_untouched` asserts
`n_no_rise == 1`; end-side `test_sub_jitter_extension_untouched` asserts
`n_fired == 1`, `n_below_min_shift == 1`, `n_extended == 0`.

**Harness**: print the new onset counters (`fired / no-rise / below-min-shift
/ undetectable / single-word`) and end `n_below_min_shift` in per-song and
totals lines.

**Verify**: suite green; harness — snap/extend records byte-identical to
Phase 1 output (counters only); record all totals, especially
`n_undetectable` (sizes Phase 7b) and `n_single_word` (should be 64).

Commit: `feat(edge-snap): symmetric onset/end telemetry counters`

## Phase 3 — Stem-end truncation split in `_detect_rise` (review #1)

The trust branch at `onset_snap.py:170` accepts a rise when the remaining run
is shorter than the sustain window, but cannot tell *word-2 proximity* (the
intended exception) from *the envelope running out* (a truncation artifact).
Single-word lines cluster in outros and fades, so Phase 4 will feed this
branch more near-stem-end cases — fix it first.

**Change**: compute the two bounds separately and trust only the word-2 case:

```python
b_word2 = int(t1 / HOP_S)
b_env = len(env) - EDGE_FRAMES
b = min(b_word2, b_env)
...
        if b - i < sustain_frames:
            # Continuity with word 2 is trustworthy; the envelope running
            # out is not — onsets near the stem end are unreliable.
            if b_word2 <= b_env:
                return i * HOP_S
            continue
        if float(np.median(env[i:b])) >= ref_db - SUSTAIN_NEAR_DB:
            return i * HOP_S
```

`continue` (not `return None`): later candidates in the same scan hit the same
truncated-window branch and fall out naturally. `b_word2 == b_env` counts as
word-2 proximity (word 2 genuinely starts there).

**Test** — `test_rise_truncated_by_stem_end_rejected` in
`TestSnapLineOnsets`. Construction (envelope ends at 5.0s → `len(env) = 200`,
`b_env = 197`):

- `_env(5.0, [(4.7, 5.0, -20.0)])`
- line `_line((3.0, 4.6), (4.95, 5.4))` — word 2 starts at 4.95 →
  `b_word2 = 198 > b_env = 197`, so the window is env-truncated; word 2's
  span keeps 2 in-envelope frames at -20, so ref = -20 (no `ref is None`
  bail).
- Rise at 4.7s (frame 188): `b - i = 9 < sustain_frames = 16` → trust branch.
  Pre-change: snaps to 4.65. Post-change: rejected, line untouched.
- Assert untouched, and that the existing
  `test_soft_rise_just_before_word2_accepted` (`:173`) still passes — that is
  the intended-trust case this change must not break.

**Verify**: suite green; harness diff vs Phase 2 — expect a handful of snaps
near song ends to disappear; list them in the Results log and spot-check one
with mpv (command in the harness docstring).

Commit: `fix(onset-snap): reject rises truncated by the stem end`

## Phase 4 — Single-word line support (the headline coverage gap)

**Design.** The only structural blocker on both edges is the reference;
everything else generalizes with a one-variable change of bound.

**4a. Reference** (`_sung_level_ref`, `onset_snap.py:127-141`): new module
constant

```python
# Single-word lines have no words 2..n to reference. A high percentile of
# the word's own claimed span works instead: smeared gap frames are LOW
# outliers, so with >= ~20% of the span genuinely sung the percentile lands
# at the sung level; a span lying wholly in a gap yields a floor-level
# reference that MIN_REF_DB rejects. Validated at 35/36 usable on corpus.
SINGLE_WORD_REF_PCT = 80.0
```

and inside `_sung_level_ref`: when `len(words) == 1`, return
`float(np.percentile(env[span_idx], SINGLE_WORD_REF_PCT))` over word 1's own
span (same index construction and bounds filter as today; a sub-frame span
still yields >= 1 frame, no extra guard needed). Update the docstring — the
"word 1 is excluded" rationale now applies only to the multi-word case.

**4b. Onset path** (`snap_line_onsets`): replace the `len(words) < 2` gate
(`194-196`) with `if not words:` + `n_single_word` counting (now "seen", not
"skipped" — update the Phase 2 label). Then generalize the bound:

```python
bound = words[1]["start"] if len(words) >= 2 else words[0]["end"]
```

and use `bound` everywhere `w2s` is used today: the narrow-window skip
(`199`), the `_detect_rise` call (`227`), and the clamp (`232`,
`bound - MIN_WORD_DUR_S`). For a single-word line the end-carry branch at
`240-243` is unreachable (the clamp keeps `new_start <= w1e -
MIN_WORD_DUR_S`), so no special-casing — the existing
`[{**words[0], ...}] + words[1:]` construction is already correct for a
1-element list.

Known, accepted limitation (note in the docstring): `_detect_rise`'s
continuity check now demands the voice hold to the *claimed end*. For held
notes (the case that matters — whisper clips their ends early, so claimed end
is inside the true run) this is correct; a staccato word with a wildly long
claimed span won't snap. That is the safe direction.

**4c. End path** (`snap_line_ends`): replace the `len(words) < 2` gate
(`292-294`) with `if not words:` + counter. Nothing else changes — the bound
search, `MIN_REF_DB` gate, clip evidence, and release trace never reference
word 2. Note the ordering dividend in the docstring: ends run after onsets,
so a single-word line's reference at end-snap time is computed over the
already-snapped (cleaner) span.

**4d. Tests.** Rework the two `test_short_lines_skipped` tests (`196`, `343`):
keep the empty-words object as `test_empty_words_skipped` in each class; the
one-word cases move to the new tests below. Compute expected values from the
constants; for release traces the trigger is the first frame `i` where the
`RELEASE_SUSTAIN_S` (8-frame) window *mean* drops below `ref -
SUSTAIN_NEAR_DB` — with a -20 dB run hitting a -60 floor that is when <= 5
loud frames remain, i.e. 5 frames (0.125s) before the visual edge. Crib from
`test_clipped_held_note_extends_to_release` (`:235`).

1. `test_single_word_smeared_start_snaps`:
   `_env(8.0, [(3.5, 5.0, -20.0)])`, line `_line((2.0, 5.0))`.
   ref = pct80 over [2.0, 5.0] = -20 (61 of 121 frames sung); guard fails at
   -60; rise at 3.5s; expect start 3.45, end unchanged 5.0, `n_snapped == 1`.
2. `test_single_word_on_time_untouched`:
   `_env(8.0, [(2.0, 4.0, -20.0)])`, line `_line((2.0, 4.0))` — guard fires,
   untouched.
3. `test_single_word_clipped_end_extends`:
   `_env(10.0, [(2.0, 6.0, -20.0)])`, line `_line((2.0, 3.0))`, no next line.
   Clip evidence at 3.0 (-20 >= -28); release window arithmetic gives
   new_end = 5.875 (verify at runtime); assert `n_fired == 1`,
   `n_extended == 1`.
4. `test_single_word_in_silence_untouched`: word `(6.0, 7.0)` over floor with
   singing elsewhere, e.g. `_env(12.0, [(1.0, 4.0, -28.0)])` — pct80 = -60 <
   `MIN_REF_DB` → both paths skip via their `n_low_ref` gates (Phase 1 made
   the onset side explicit).
5. `test_single_word_both_edges` (in `TestSnapLineEdges`, monkeypatching like
   `:372`): `_env(10.0, [(3.5, 6.5, -20.0)])`, line `_line((2.0, 4.5))`.
   Onset pass snaps start to 3.45; end pass then re-derives ref over the
   snapped span, sees clip evidence at 4.5, traces to ~6.375 (verify at
   runtime). This is the held-"Oooh" showcase: both edges envelope-derived.

**Verify**: suite green; harness vs Phase 3 — **multi-word lines'
snap/extend records must be byte-identical** (diff the stdouts; the only new
records may come from single-word lines). Record how many of the 64 fire, and
eyeball the two or three largest single-word moves with mpv.

Commit: `feat(edge-snap): single-word line support via own-span percentile
reference`

## Phase 5 — End-path reference includes word 1 (review #3)

The end snap borrows the onset snap's "exclude word 1" rule but has no
onset-smear problem to defend against, and by the time ends run, onsets have
already been repaired. On lines that are mostly one long held note plus short
words, the tail-only median misstates the sung level.

**Change**: `_sung_level_ref(env, words, end=False)`. For `len(words) >= 2`:
include `words[0]`'s span when `end` is true and
`words[0]["end"] - words[0]["start"] > MIN_WORD_DUR_S`; otherwise slice
`words[1:]` as today. (The `len(words) == 1` percentile path from Phase 4 is
independent of `end`.) `snap_line_ends` passes `end=True` at `:310`; the
onset call stays `end=False`. Rewrite the docstring — "both snaps gate on
this same reference" is no longer the contract.

**Test** — `test_end_ref_includes_long_word1` in `TestSnapLineEnds`:

- `_env(10.0, [(1.0, 3.0, -20.0), (3.2, 5.5, -34.0)])`
- line `_line((1.0, 3.0), (3.2, 3.4), (3.6, 4.0))`
- Old ref (words 2..3 only) = -34: clip evidence at 4.0 fires
  (-34 >= -42) and the line extends along the -34 patch to ~5.4.
- New ref (word 1's 81 frames dominate the median) = -20: clip evidence
  fails (-34 < ref - 8 = -28) — the last word has already fallen 14 dB from
  the line's true sung level, i.e. it already released. Assert untouched,
  `n_fired == 0`.

**Verify**: suite green; harness vs Phase 4 — expect a small number of
end-extend changes concentrated on lines with a long first word; Phase 2's
invariants must still hold. List changed lines in the Results log and eyeball
one.

Commit: `fix(end-snap): include a substantial word 1 in the end-path sung
reference`

## Phase 6 — Run-edge generalization (interior gaps)

Biggest coverage multiplier: 388 interior words follow an intra-line gap
>= 0.5s and show the same artifacts, because the ASS writer re-anchors the
karaoke fill at every inter-word gap. Reframe both snaps from "line edge" to
"run edge": split each line's words into voiced runs at large gaps; onset-snap
each run's first word; end-snap each run's last word. A line without interior
gaps is one run (today's behavior); a single-word line is one run of one word
(Phase 4's machinery).

**Constants**:

```python
# Intra-line gaps at least this long split a line into separate voiced
# runs; each run's edges get the same repair as line edges (the ASS
# writer re-anchors the fill at every inter-word gap).
RUN_GAP_S = 0.5
```

**Structure** (keep public signatures; refactor internals):

- `_split_runs(words) -> list[tuple[int, int]]` — inclusive (first, last)
  word-index pairs, split where `words[k]["start"] - words[k-1]["end"] >=
  RUN_GAP_S`.
- `snap_line_onsets`: per line, compute ref once (unchanged semantics), then
  for each run apply the existing per-line onset logic to the run's first
  word `k`. Bound: `words[k+1]["start"]` if `k+1` is inside the same run,
  else `words[k]["end"]` (the Phase 4 single-word rule — never search across
  the gap toward the next run). The on-time guard evaluates at word `k`'s
  claimed start/span exactly as it does for word 0 today.
- `snap_line_ends`: per run, apply the existing end logic to the run's last
  word. Bound: next run's first-word start minus `NEXT_LINE_GAP_S` when the
  next run is in the same line; the existing next-line scan (`297-302`)
  for the line's final run. The two-pass onsets-then-ends order already
  guarantees a run's end bound sees the next run's *snapped* start.
- Stats: snap/extend records gain `"word_idx"`; add `n_runs` to both stats
  dicts. Expect interior candidates to die on `MIN_SHIFT_S` at a higher rate
  than line edges (whisper's interior timestamps are better) — that is the
  telemetry confirming the expansion is safe, not a bug.

**Tests**:

1. Interior smeared word: gap of 1.5s mid-line, word after the gap claimed
   early over the floor, singing resumes later — expect it snapped to the
   rise; words before the gap untouched.
2. Interior clipped end: held note before a 1.5s gap, still at sung level at
   its claimed end — expect extended, and capped at next run's start minus
   `NEXT_LINE_GAP_S`.
3. Sub-threshold gap (0.4s): line stays one run; an interior "smeared" word
   is NOT touched (regression pin for `RUN_GAP_S`).
4. No-gap regression: reuse the construction of an existing multi-word test
   and assert output equality with the single-run path (behavior identical to
   Phase 5 for gap-free lines).

**Verify**: suite green; harness vs Phase 5 — lines without interior gaps
byte-identical; record how many of the ~388 interior candidates fire vs die
on `MIN_SHIFT_S`; eyeball 2-3 songs with interior snaps end to end (this is
the phase most worth watching in mpv before trusting).

Commit: `feat(edge-snap): snap interior run edges, not just line edges`

**Checkpoint**: stop here. Alert the user that Phases 1-6 are ready for
`/code-review`, with the Results log filled in.

## Phase 7 — Gated offline experiments (each: study first, STOP, report)

None of these touch production code without an explicit GO decision from the
user. Each produces a script under `scripts/` plus a Results-log entry.

**7a. Voicing trace for the harmony blind spot.** The release trace follows
RMS, so backing harmonies that hold the level past the lead's release drag
extensions to the bound (`to_bound` records, ~240 suspects at baseline).
Study: per `to_bound` line, compute a frame-rate autocorrelation f0/voicing
track from the same 16 kHz mono PCM over `[claimed_end, bound]`; find where
the pitch track that is active at the claimed end breaks; compare against the
RMS bound. Report the distribution of (voicing break − RMS end) and eyeball 5
songs. GO gate: voicing finds an earlier, plausible release for >= half the
suspects and the eyeballs agree.

**7b. Adaptive step floor.** Only if Phase 2's `n_undetectable` is material
(rule of thumb: > 5% of fired lines). Prototype in the harness:
`required_step = max(5.0, min(STEP_DB, 0.6 * (ref - p20(window))))`; diff
which new snaps appear; eyeball before proposing production adoption.

**7c. Sub-frame attack refinement (review #5).** Replace `SNAP_MARGIN_S`
with a real attack locator: keep the decoded PCM available (extend
`rms_envelope_db` or add a sibling helper), and inside the detected rise
frame find the amplitude crossing between the pre/post levels; snap there.
Deletes the margin constant and the two-frame empty lead-in. Update
`test_reverb_tail_start_snaps_to_rise` (asserts 2.15 for a rise at 2.2) with
a comment per the review — it is a deliberate tuning knob, change it loudly.

**7d. Backward onset search (late starts).** Forward-only snapping cannot fix
a word whisper placed late (voice already at sung level before `w1s`). A
bounded backward search breaks the "never make an on-time line worse"
invariant if it misfires, so: only design it after Phases 1-6 telemetry shows
the case is common, and bring the design to the user before implementing.

## Results log

(append per phase: harness totals, diff vs previous phase, eyeball notes)
