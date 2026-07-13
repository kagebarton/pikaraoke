Model: Claude Fable 5

# Matcher accuracy hardening (joint + cue paths)

## Goal

Execute the fixes from the 2026-07-06 matcher review (full text in the
Appendix): raise line coverage and cut erroneous placements of lines that do
not exist in this mix (different lyric-source version), **without fetching any
new online timing sources**. Every proposal uses data already on disk: the
refined align words (with per-word probabilities), the transcribe stream, the
downloaded YTASR json3, the vocal stem's energy envelope, and the SRT cues.

Phases are ordered by the review's "suggested order". Each phase is
independently commit-able and independently measurable; later phases assume
earlier ones landed. GATE markers are decision points — stop and report to Ken
with the numbers; do not proceed past a GATE on your own judgment.

## Ground rules

- Environment: Linux box runs tests directly
  (`/home/ken/miniconda3/envs/pik/bin/python -m pytest`) and
  `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`.
  Windows/uv has 4 known baseline test failures (pipe + sidecar I/O) — not
  regressions. GPU legs run on whichever box you are on.
- The working tree currently carries in-flight changes (`pyproject.toml`,
  `uv.lock`, `scripts/onset_snap_ass.py`, `scripts/regen_alignment_bundles.py`,
  new `scripts/edge_snap_ass.py`). Start this plan from a clean checkpoint —
  those must be committed or stashed by Ken first; never mix them into this
  plan's commits.
- Never commit to `master`. One feature per commit; tests ride with the code
  they exercise. Import-smoke before committing; read `git diff --cached`.
- Self-review every diff on the three CLAUDE.md axes (correctness /
  simplicity / robustness). Batch /code-review-qualifying commits and alert
  Ken at clean checkpoints — never launch /code-review unprompted.
- Fork rule: new features go in new files where possible; smallest change to
  existing modules.
- Offline replays (the harness re-running the matcher on captured bundle
  words) need no GPU. Fresh cue-align corpus runs and live spot-checks need
  the GPU worker.
- Bundle corpus lives in the song library's `alignment_debug/` directories
  (see `scripts/README.md` and each harness's `--help` for paths/args).
- Throwaway measurement scripts go in the session scratchpad, never
  committed. Paste result tables into this file (plans/ is pre-commit-exempt)
  under a "## Results log" section you create on first use.

## Model switching

The remaining work is spec-shaped: every design-sensitive decision is locked
in an appendix. Three roles apply from here forward and are not to blend:

- **Design** — Fable (Opus may draft if Fable is unavailable, but Ken
  reviews it before it locks). Fable's extra depth is spent here — the
  appendices are its output; once an appendix locks it is a contract, not a
  suggestion, and no executor redesigns it, on any model.
- **Implement, prototype, run** — Sonnet 5, the default executor since
  2026-07-12. Writes the code, writes and runs the scratch measurement
  scripts, executes the pre-registered harness sweeps, starts/runs the unit
  suite and pre-commit. Stops at the numbers: this role's output at a GATE
  is a table, never a verdict.
- **Judge results** — Opus by default; escalate to Fable only if Opus's own
  read is ambiguous, or the data hints at a confound the pre-registered
  criterion wasn't built to catch. Takes the executor's table plus the
  appendix's pre-registered criterion and produces the actual
  interpretation: which branch of the criterion applies, whether anything
  in the data undercuts its assumptions, what the recommendation is.
  Precedent for why this role exists: the Phase 3b GATE outcome (Results
  log, 2026-07-13) — the initial live-validation table read as a clean
  pass, and only a second, deeper look caught that the "kept" lines were
  phantoms the silence test was never built to see. This does not move
  Ken's authority at GATEs (see "Ground rules" above) — it means what
  reaches him is a considered read, not a pass-through of the executor's
  table.

| Phase | Design | Implement/run | Judge results |
| --- | --- | --- | --- |
| Phases 0-3b (executed — see Results log) | Fable (Appendices B/C/D) | Opus | Ken directly; Fable retroactively at the Phase 3b GATE outcome |
| Phase 4 | Fable (Appendix E) | Sonnet 5 | Opus; escalate to Fable if ambiguous |
| Phase 4.5 | Fable (Appendix G) | Sonnet 5 | Opus; escalate to Fable if ambiguous |
| Phase 5 | inline in phase text (no appendix) | Sonnet 5 | Opus; escalate to Fable if ambiguous |
| Phase 6 checkpoint | Fable (Appendix F) | Sonnet 5 | Opus; escalate to Fable if ambiguous |

Two sibling plans execute alongside this one and are not phases here:

- `plans/lrclib-fill-absence-study.md` (offline study, no production code):
  slot it after the Phase 3b GATE — ideally after Phase 4 lands, since Phase 4
  shifts the unplaced population it measures — and before the Phase 6 probe,
  whose F2 criterion 4 reads its E2 verdict. Phase 4.5's G2 labels also read
  E2 (secondary corroboration; 4.5a degrades to manual-gold-only without
  it), so prefer it before 4.5a when feasible. Untracked on disk by design.
- `plans/edge-snap-coverage-accuracy.md`: independent parallel track on its
  own branch (`edge_snap_refine` off `89d28c46`), runnable at any point — the
  replay harness here excludes edge-snap, so this plan's corpus numbers are
  insulated from it. The only coupling is a small
  `onset_snap.py`/`lyric_align.py` merge at branch integration, noted in that
  plan.

The design-sensitive content of Phases 1b and 2a was executed by Fable in the
planning session (2026-07-06) and locked as Appendix B (1b implementation
blueprint) and Appendix C (2a pre-registered analysis protocol). Phase 2b was
skipped at the 2a GATE (see Results log). The remaining design-sensitive
content — Phase 3b's evidence/threshold contract and Phase 4's replay/merge
revision — was locked by Fable on 2026-07-07 as Appendix D (3b decisions) and
Appendix E (Phase 4 blueprint). The Phase 6 checkpoint got the same treatment
on 2026-07-12: Appendix F pre-registers its go/no-go probe and locks the
contingent transition-cost design, so no phase requires Fable by default.
The Phase 3b GATE outcome (2026-07-13) opened Phase 4.5; its pre-registered
study protocol and contingent veto-v2 design were locked the same day as
Appendix G.
Implementing from these specs is executor work; the specs themselves are not
to be redesigned by the executor, whatever the model.

Design switch points are marked inline with **MODEL BREAK** blocks. At each
break, STOP: do not continue into the next step. Tell Ken the plan calls for
a model switch (`/model`), and wait — the switch is his to make; if he
declines, proceed on the current model and note that in the Results log.
GATE judgment gets no inline marker of its own — every GATE already implies
the handoff above: the executor stops with the table, Opus (then Ken) reads
it before the plan proceeds past the GATE.

### Implementation escalation (Sonnet 5 → Opus → Fable)

Distinct from judging results (above): this ladder is for trouble
implementing, not for interpreting what got measured. Recommend an
escalation (Opus first; Fable only if still available) whenever:

- Phase 0's bit-faithful replay check cannot be made to pass quickly, or
- a needed change goes beyond the letter of a spec into scoring/DP semantics
  (`_best_tiling_by_time`, `_alpha_weight` / `_corroboration_weight`).

### Executor discipline (Sonnet 5, added 2026-07-12)

The appendices assume a literal executor. These rules bind any executor, but
they exist because a smaller model is likelier to bridge a gap than to stop
at one:

- Specs are contracts. When code reality differs from a spec in any detail —
  a name, a signature, a key, an anchor that will not re-anchor by symbol —
  STOP and report the exact mismatch. Never bridge it with your own design,
  and never improve a spec while implementing it.
- GATEs and MODEL BREAKs are hard stops even when the verdict looks obvious
  from the numbers. Hand the table to Opus/Fable for judgment (the "Judge
  results" role above); never write your own verdict or recommendation into
  the Results log.
- Every number written into the Results log comes from a command actually
  run in that session, with the invocation recorded (mirror the existing
  entries, e.g. `replay_ytasr_third_source.py <corpus> --alpha 2.0
  --beta 2.0`). Never reconstruct a number from memory, a prior entry, or
  expectation.
- "Byte-identical" / "unchanged" claims require a real `diff` of saved
  outputs from both runs, not an eyeballed table.
- Pre-registered protocols (Appendices C, F) run exactly as written: the
  stated statistic, the stated constants, the stated bars. A threshold is
  never adjusted after seeing results; an ambiguous criterion is an
  escalation, not a choice.
- A failing or flaky test at the verification matrix is a STOP, not a
  retry-until-green; so is any corpus delta the phase text does not predict.
- No scope beyond the phase text: no extra error handling, no drive-by
  refactors, no constants or knobs the spec does not name.

## Phase 0 — port the tuning harnesses to this branch

Everything after this phase is measured with these tools; they currently live
only on `pathed_align`. This is Phase F2 of `plans/two-path-matcher-ship.md`,
done early.

Files on `pathed_align` (read them with
`git show pathed_align:scripts/<name>.py`):

- `scripts/replay_ytasr_third_source.py` (388 lines) — the alpha/beta tuning
  harness: replays captured bundles through the matcher offline, scores
  against held-out LRCLIB.
- `scripts/cue_align_song.py` (410 lines) + `scripts/cue_align_corpus.py`
  (231 lines) — cue-path single-song and corpus drivers.
- `pikaraoke/lib/lrclib.py` (362 lines) + `tests/unit/test_lrclib.py` — the
  held-out scorer the replay harness uses. **Held-out scoring only**: LRCLIB
  is permanently out of production; no production module may import it.
- `scripts/lrc_align_song.py` and `scripts/replay_alignment_from_bundle.py`
  are dead exploration — **never bring these files over**.

Steps:

1. Copy `pikaraoke/lib/lrclib.py` and `tests/unit/test_lrclib.py` from
   `pathed_align` unchanged (it imports only `token_align.fold_to_ascii` +
   stdlib + requests).
2. Port `scripts/replay_ytasr_third_source.py`, refit:
   - It does `import replay_alignment_from_bundle as old_harness` and uses
     exactly two helpers: `old_harness.replay_bundle(bundle, realign=True)`
     and `old_harness.summarize(objs)` (call sites around lines 331-344).
     Inline those two functions (plus only their private dependencies) from
     `pathed_align:scripts/replay_alignment_from_bundle.py` into the ported
     script as local helpers. No import of the dead harness may remain.
   - `from pikaraoke.lib.srt_prior import offset_mad_against_cues` →
     `from pikaraoke.lib.srt_cues import ...` (the ship rename).
   - Check the inlined `replay_bundle` against ship's current
     `joint_match` / `windowed_realign` signatures (beta, ytasr_words) and
     bundle schema — the ship bundles carry `joint_beta`, ytasr candidate
     stats, `pass1_line_timings`, and windowed-realign `spans` with
     `align_words`. Fix drift; the harness must replay a ship bundle
     bit-faithfully at the bundle's own knobs before any sweep is trusted.
3. Port `scripts/cue_align_song.py` + `scripts/cue_align_corpus.py`, refit:
   - `srt_prior` → `srt_cues` imports.
   - The `pathed_align` versions predate the C1 driver graduation. Ship's
     `cue_align.align_song` now owns sectioning/offset/re-pace; the script
     becomes a thin shim per the two-path plan: build cue spans
     (`cue_spans_from_srt`), provide a `slice_align` callable (ffmpeg slice
     via `get_temp_directory()` + `WhisperWorker.align_refine`), call
     `align_song`, print the report. `cue_align_corpus.py` loops the shim
     over the corpus and aggregates flags.
4. Import-smoke: run each script with `--help`. Run the unit suite +
   pre-commit.
5. Grep gates: `lrclib` imported only by `scripts/replay_ytasr_third_source.py`
   and its test; no `replay_alignment_from_bundle` or `srt_prior` reference
   anywhere.
6. Commit: `chore(scripts): port tuning harnesses to the ship branch`.
7. **Baseline runs** (paste tables into Results log):
   - `replay_ytasr_third_source.py` over the 16-song non-SRT corpus at
     alpha=2.0 / beta=2.0 → per-song MAD / overlap / placed counts. This
     table is the reference every later phase diffs against.
   - HARD ORDERING: capture this baseline **before landing Phase 1b** — the
     harness replays through the checked-out matcher, so once 1b merges the
     pre-fix baseline can only be reproduced by checking out an older commit.
     (The bundles themselves stay valid across all phases: the harness
     replays from captured inference words, which matcher changes never
     touch.)
   - Optional now, required before Phase 5: `cue_align_corpus.py` over the
     SRT corpus (GPU) → flag counts baseline.

## Phase 1 — align-words 1:1 desync: measure, then fix

### The bug (review finding 1)

`_line_align_ranges` (`pikaraoke/lib/joint_match.py:357-393`) walks a cursor
assuming one align word per lyric token. The align route runs stable-ts with
`remove_instant_words=True` (`pikaraoke/pipeline/config.py:49`), which drops
words it could not time — `pikaraoke/lib/cue_align.py:250-252` documents this
for the same worker call. One mid-song drop shifts every downstream line's
align range; the overrun guard only catches the stream running out at the end.
Corrupted ranges feed align candidates (still scoring `alpha` with
`align_agreement=1.0`), per-word render timings (`_align_line_object`), and
`_range_agreement` references for the other two sources. Span replays inherit
the same walk. Second vector: `_tokenise_lines` drops tokens that normalize to
empty (standalone `&`, `—`) while the aligner may still emit a word for them.

### 1a. Measure (scratchpad, no commit)

Script over all joint-method bundles: per song compute
`n_tokens = sum(len(t) for t in _tokenise_lines(bundle align_lines))` vs
`len(words)` (the captured refine words); where they differ, run a
normalized-equality verify walk to find the first desync index and its time.
Report: songs affected, drops per song, first-desync position (early drops
corrupt more). GATE: report the table to Ken. Proceed with 1b regardless
(the fix is correct-by-construction and cheap); the numbers set expectations
for 1c.

> **MODEL BREAK (resolved 2026-07-06) — design already done by Fable.**
> Implement 1b exactly per **Appendix B**; the contract redesign,
> helper-extraction, and tiebreak decisions are locked there. Opus proceeds
> without a switch. Ask Ken to switch to Fable only on spec failure: the t1
> regression test cannot be made to pass, cue tests cannot stay green via
> the B1 adapter, or a consumer of the removed fields turns up that
> Appendix B's grep step doesn't cover.

### 1b. Fix

**Execute per Appendix B (locked design).** The numbered steps below are the
summary; where they and Appendix B differ in detail, Appendix B wins.

1. Generalize `cue_align._match_words_to_tokens`
   (`pikaraoke/lib/cue_align.py:176-235`) and move it to
   `pikaraoke/lib/token_align.py` (the shared token-primitives home;
   `joint_match` cannot import from `cue_align` — that would be circular).
   New signature takes plain sequences:
   `match_words_to_tokens(token_norms, token_times, word_norms, word_times)`
   — same DP (max matches, then min total |word_time − token_time| deviation),
   no dict access inside. Update the two cue_align call sites
   (`split_section_to_lines`, `_line_from_realigned`) to pass
   `[_normalize_token(w["word"]) ...]` / `[w["start"] ...]`; keep cue tests
   green unchanged in behavior.
2. In `joint_match`, replace the cursor walk: assign align words to the flat
   token stream via the shared function with **index-space pseudo-times** —
   `token_times = [float(k)]` over flat token index, `word_times = [float(j)]`
   over word index. Rationale: both streams are the same text in the same
   order modulo sparse drops; index deviation is the correct twin-arbitration
   tiebreak (there is no external clock on this path).
3. `_line_align_ranges` returns, per line, `{t0, t1, word_idx}` where
   `word_idx` is the per-token `list[int | None]` mapping into `align_words`,
   and `t0`/`t1` come from the line's first/last *matched* word. A line with
   zero matched words → `None` (no align candidate — the aligner dropped the
   whole line; honest abstention). Remove the `token_start`/`token_end` slice
   fields and their uses.
4. `_align_line_object` (`joint_match.py:791-819`) builds words from the
   mapping: matched tokens take their word's start/end; unmatched runs are
   linearly interpolated between surrounding anchors. That interpolation
   logic already exists in `candidate_match._build_line_object`
   (`pikaraoke/lib/candidate_match.py:224-246`) — extract it into a shared
   helper in `candidate_match` and reuse (single source of truth).
5. Add `n_align_word_drops` (tokens − matched words) to `joint_stats`.
6. Words whose norm is empty (the `&` case) can never match a token — the DP
   skips them by construction; add a test proving no shift.

Tests (`tests/unit/test_joint_match.py`):
- Clean 1:1 stream → ranges identical to the old implementation (regression).
- One word dropped mid-song → downstream lines' ranges unchanged/correct.
- A whole line's words dropped → that line has no align candidate; neighbors
  unaffected.
- Extra empty-norm word in the stream → no shift.
- Span-replay path (windowed_realign) picks up the fix without changes.

### 1c. Validate offline

Re-run the replay harness over the bundle corpus; diff per-song summaries
against the Phase 0 baseline. Expected: byte-identical placements on songs 1a
found clean; improvements (or at minimum shifts toward the SRT/LRCLIB
reference) on drop-affected songs; no regressions elsewhere. GATE: numbers to
Ken.

Commit: `fix(joint-match): text-verified align-word assignment survives
aligner word drops` (plus the token_align refactor either inside it or as a
preceding `refactor(token-align)` commit — prefer two commits).

## Phase 2 — align word probability as align-candidate evidence

### Rationale (review finding 2a)

The worker keeps per-word `probability` explicitly for the matcher
(`pikaraoke/pipeline/workers/whisper_worker.py:154-156`) but nothing reads it.
Forced alignment's word probability measures how well the audio matched the
forced token — a phantom line's align words should have distinctly low
probabilities. Today the align candidate's self-evidence is a flat 1.0 behind
a near-useless binary gate (stopword `any_overlap`).

### 2a. Measure separation first (scratchpad, no commit)

**Execute per Appendix C (pre-registered protocol — metrics, labels, and the
GATE criterion are fixed there; do not adjust them after seeing data).** The
C1 prerequisite check (probabilities present in bundle words) can run on the
first regenerated bundle, before the corpus finishes.

Using the Phase 1 mapping offline, compute each placed line's mean align-word
probability from bundles. Compare distributions across three proxies:

- Songs with an independent uploader SRT
  (`ground_truth_refs.youtube_srt_present && !youtube_srt_is_lyric_source`):
  lines whose text has no fuzzy match among the SRT cue texts ≈ absent lines.
- The 16-song harness corpus: lines with placement error > 2 s vs < 0.5 s
  against the held-out reference.
- Manual spot-check on known different-mix songs (Bloodstream 4:07 cut,
  In Summer, HUNTR_X).

GATE: show Ken the distributions. Proceed only if absent/wrong lines separate
clearly from present/correct ones (non-overlapping medians, usable threshold
region). If separation is weak, skip 2b entirely and note it in the Results
log — Phase 3 still proceeds.

> **MODEL CHECK (moot) — 2b was skipped at the GATE above (see Results
> log), so this note never triggered.** Superseded regardless by the
> 2026-07-12 default-Sonnet change and the design/implement/judge roles in
> "Model switching"; kept only as a historical marker of the plan's
> original model assignment for this stretch.

### 2b. Implement

In `_build_align_candidates` (`pikaraoke/lib/joint_match.py:506-561`): the
align candidate's `align_agreement` becomes the mean probability of the
line's matched align words when probabilities are present, else 1.0
(backward-compatible with old bundles and probability-less outputs). The
corroboration rescue (`_corroboration_weight`) composes unchanged —
`min(a_agree, y_agree)` now reflects graded align self-trust. Expose the
value as `align_prob` on the candidate dict and in capture stats. No new
config knob — the alpha re-sweep does the calibration.

Do **not** touch `_range_agreement`'s use of align ranges as references for
other candidates in this phase.

Tests: score reflects mean probability; missing `probability` → flat 1.0;
rescue path uses the graded value.

### 2c. Re-sweep and decide

Run the harness alpha × beta grid over the 16-song corpus; diff against
baseline (and against the post-Phase-1 table). GATE: Ken picks whether the
graded evidence and any new alpha/beta defaults land.

Commit: `feat(joint-match): grade align self-evidence by align word
probability`.

## Phase 3 — energy veto + crammed-candidate rejection

Two independent, small changes; separate commits. Both target phantom
renders directly (review findings 2b and 3).

### 3a. Crammed align-candidate rejection (do this first — smaller)

In `_build_align_candidates`: before the min-width pad, drop any align
candidate whose pre-pad pace is implausible:
`(t1 - t0) / n_tokens < _MIN_ALIGN_PACE_S = 0.06` (named constant with a
comment: ~17 tokens/s is faster than any real singing; a crammed range is the
aligner's give-up signature, not a belief — entering it into the DP lets one
phantom per crammed stack render as a flash line). Keep `_MIN_ALIGN_WIDTH_S`
padding for surviving candidates. The line's transcribe/ytasr candidates (or
honest interp) decide instead.

Tests: a crammed multi-line stack yields zero align candidates and the lines
fall through to other sources/interp; a genuine 1-token 0.3 s line is
unaffected. Corpus replay diff vs baseline. Commit:
`feat(joint-match): drop implausible-pace align candidates`.

### 3b. Vocal-energy veto for uncorroborated placements

**Execute per Appendix D (locked design).** The bullets below are the
summary; where they and Appendix D differ in detail — notably: evidence
rides on the line objects, not in a `joint_stats` map, because the veto runs
after windowed re-align can replace objects — Appendix D wins.

New file `pikaraoke/lib/evidence_veto.py` (fork rule):

- Prereq inside `joint_match`: record per-line selected evidence in
  `joint_stats` (e.g. `selected_evidence[lid] = {transcribe_match,
  ytasr_agreement}` from the winning candidate). Note: transcribe candidates
  have `transcribe_match > 0` and ytasr candidates `ytasr_agreement > 0` by
  construction, so only align-won lines can be zero-evidence.
- `veto_uncorroborated_lines(line_objects, joint_stats, envelope) ->
  (line_objects, stats)`: for lines with source `align`,
  `transcribe_match == 0` and `ytasr_agreement == 0`, test the stem's RMS
  envelope over `[start, end]`; if the line's median level is near-silent
  relative to the song's vocal reference level, demote it: `words=[]`,
  keep `start`/`end` for debug, `source="veto"` — ASS/SRT generators already
  skip word-less lines. Never veto a corroborated line. Derive the silence
  threshold from `onset_snap`'s existing floor/relative constants (read
  `pikaraoke/lib/onset_snap.py` and reuse its conventions; named constant +
  comment).
- Stage wiring (`pikaraoke/pipeline/stages/lyric_align.py`): run on the joint
  route only, after windowed re-align, before `snap_line_edges`. Share one
  envelope decode with the snap — `onset_snap` already has an
  envelope-injection pattern internally (`rms_envelope_db` at
  `onset_snap.py:79`, injected-envelope variant near line 183); extend
  `snap_line_edges` minimally to accept a precomputed envelope rather than
  decoding twice. Veto stats go into `joint_stats["evidence_veto"]`.

Tests: zero-evidence align line over silence → vetoed; same line over energy
→ kept; corroborated line over silence → kept; transcribe mode and cue route
untouched; envelope decoded once.

Validation: harness replays don't carry envelopes, so validate live: run 2-3
known phantom-heavy songs (Bloodstream, HUNTR_X) end-to-end and diff which
lines render; corpus replay to confirm placement metrics elsewhere unchanged
(the veto only demotes; it never moves lines). GATE: line lists to Ken.

Commit: `feat(pipeline): vocal-energy veto for uncorroborated align
placements`.

## Phase 4 — windowed re-align revision

Two changes, separate commits, one corpus evaluation (review findings 4a/4b).

> **MODEL BREAK (resolved 2026-07-07; executor reassigned 2026-07-13) —
> design already done by Fable.** Implement 4a/4b exactly per **Appendix
> E**; the replay-contract, merge-policy, and protection-semantics
> decisions are locked there. Sonnet 5 proceeds without a switch (the
> 2026-07-12 default-executor change supersedes this block's original
> "Opus proceeds" — see "Model switching"). Ask Ken to escalate
> implementation — Opus first, Fable if still needed — only on spec
> failure: the Girl in the Bubble acceptance run cannot be made to recover
> the 51-89s span, existing windowed-realign tests cannot stay green via
> the E1/E3 default parameters, or a needed change reaches inside the
> sub-match's scoring rather than the replay/merge layer. The E7 GATE
> itself still gets Opus's judgment before Ken rules, per the "Judge
> results" role.

### 4a. YTASR as a third source in span replays

`replay_span` (`pikaraoke/lib/windowed_realign.py:171-213`) currently runs
2-source sub-matches — deliberate at experiment time, now worth testing.
Thread the already-parsed ytasr words through: stage `_realign_windows` →
`_realign_one_span` → `replay_span(..., ytasr_words, beta)`; inside, filter
ytasr words to the span window with the same `TRANSCRIBE_PAD_S` pad used for
transcribe words, and pass `beta=cfg.joint_beta` into the sub-match.

Merge policy update (`merge_spans`): a line pass-1 left unplaced may be newly
placed when the replay selected it from `{"transcribe", "ytasr"}` — both are
independent of the span's align. Update the module docstring's merge-policy
paragraph.

### 4b. Protect corroborated interior lines in the merge

`analyze_pass1` computes each placed line's corroboration ratio and discards
it after the suspect test (`windowed_realign.py:96-108`); inside a replayed
span, *every* non-anchor pass-1 line is currently exposed to being moved or
dropped by a lower-context replay (`windowed_realign.py:243-251`). Changes:

- `analyze_pass1` additionally returns `ratios: dict[int, float]` for placed
  lines.
- `replay_span` attaches each placed replay object's own corroboration ratio
  (computed with `_transcribe_match_and_count_in_window` over its window
  words — the pad covers the span, note this in a comment) as
  `obj["corrob_ratio"]`.
- `merge_spans` new rule for a pass-1 placed line with
  `ratios[lid] >= SUSPECT_RATIO` (non-suspect): if the replay leaves it
  unplaced → keep pass-1 (no honest-unplace for corroborated lines); if the
  replay moves it → adopt only when the replay object's `corrob_ratio >=
  ratios[lid]`. Suspect lines keep today's behavior exactly.

Tests: corroborated interior line kept when replay drops it; replacement
adopted only at ≥ ratio; suspect line still replaceable/droppable; ytasr-
sourced new placement adopted within edge tolerance; 2-source behavior
byte-identical when `ytasr_words=None`.

Validation: offline — span replays reuse captured span `align_words` and the
on-disk json3, and the span set is unchanged, so the harness replays this
without GPU. Diff gross misplacements / MAD / placed counts vs baseline.
GATE: adopt only on favorable corpus deltas; otherwise revert the merge-policy
commit and keep 4a or 4b independently per their own numbers.

**Acceptance case (added 2026-07-07): Girl in the Bubble** (last row of the
Phase 0 table, placed 26 of 36 lines). A live dev-vs-ship A/B showed 10 lines
missing from the shipped .ass; diagnosis (Results log, "Girl in the Bubble
coverage regression") confirmed it is exactly this phase's mechanism: pass-1
ytasr placements destroyed by the 2-source span replay + merge pop. 4a must
recover the 51-89s span on the existing bundle, fully offline — expect placed
26 → ~31-33. Lines 32/33/35 stay absent by design (no on-disk source covers
them; only the removed LRCLIB fill ever timed them).

Harness amendment (ride with 4a): add a coverage column (`placed/n_lines`) to
the replay summary and flag songs below a threshold (~85%, Ken calibrates) —
26/36 sat unflagged in the Phase 0 baseline because the harness only scores
MAD over placed anchors and never compares coverage against dev.

Commits: `feat(windowed-realign): ytasr third source in span replays`;
`fix(windowed-realign): protect corroborated pass-1 lines in the merge`.

## Phase 4.5 — counter-evidence veto for zero-evidence align lines

Opened by the Phase 3b GATE outcome (Results log, 2026-07-13), not by the
review: the energy veto's silence test structurally cannot catch a phantom
line smeared over *non-lyric singing*. Defying Gravity's outro renders six
OST-only dialogue lines (79/81/85-88) over the live version's belted
vocalise + crowd (median −12.5 to −15.6 dB — nowhere near the −45 dB
floor). Target class: align-won, zero corroboration (`evidence` zero-zero),
loud span. This extends 3b with a second, independent demotion tier; the
silence rule is untouched.

Sequencing (binding):

- **After Phase 4 lands and re-baselines.** 4a threads ytasr into span
  replays, and Defying Gravity replays its tail span (lines 78-88,
  202-257 s) where ytasr heard the "bring me down" riffs — Phase 4 will
  reshuffle the exact placements this phase studies; measuring first would
  be confounded. Same argument as the LRCLIB study's slot.
- **Before the Phase 6 probe**, so F1 measures the residual landscape.
  Appendix F is untouched: its criterion-4 "veto-ineligible" class is
  defined by the `evidence` key, not by what the veto catches, so v2 does
  not change it.
- Prefer the LRCLIB study first when feasible — its E2 strong-absence
  verdict is 4.5a's secondary label source (G2); without it 4.5a runs
  manual-gold-only.

### 4.5a. Study (scratchpad, offline, no commit)

**Execute per Appendix G (pre-registered protocol — metrics, labels, and
GATE criteria are fixed there; do not adjust them after seeing data).**
Enumerate the corpus-wide zero-evidence class from harness replays (no
GPU), label it (manual gold primary — the class is small: the 3b live runs
saw 16 such lines across 3 songs), and measure the three pre-registered
discriminators: lexical counter-evidence (CE), ASR-silent probability
floor (PF), tail overhang (TO). GATE: read-off per G4; Ken reviews the
labeled table.

Known coverage limits, stated up front from the Defying Gravity data: CE
catches 79/81 (ytasr heard different words under them) but cannot catch
86-88 (both ASR streams are empty in their spans); PF is the only on-disk
signal for those, and it must overcome 2a's no-separation verdict on the
narrower class (G3 states the 2a-lock boundary); line 85 is expected to
survive everything (its align words match the sung riff at p≈0.84-0.93).
Partial coverage is an acceptable GATE outcome — the study reports which
sub-class each discriminator covers, with counts, and names the residual.

### 4.5b. Implement (contingent on the G4 GATE)

Second demotion tier in `pikaraoke/lib/evidence_veto.py` per G5: evaluated
only on the silence rule's survivors, demote-only (`words=[]`,
`source="veto"`, `start`/`end` kept), stats record which rule fired. Live
validation mirrors the 3b GATE protocol (G6): regen Defying Gravity +
Bloodstream, pre-registered line-list expectations, byte-check that
demoted lines did not move.

Commit: `feat(pipeline): counter-evidence veto for zero-evidence align
placements`.

## Phase 5 — cue path: section-duration cap

### 5a. Survey first (scratchpad, no commit)

Over the SRT corpus: per song, the max/median inter-cue gap and the section
lengths `segment_by_gaps` currently produces. Count songs whose SRT has no
gap > `SECTION_GAP_S` (padded-cue authoring) and the resulting single-section
durations. GATE: implement only if the class is non-trivial (Ken judges).

### 5b. Implement

`MAX_SECTION_DUR_S = 60.0` in `cue_align.py`. Restructure `segment_by_gaps`
so boundary selection and window computation are separable: compute `starts`
from gaps as today, then iteratively split any section longer than the cap at
its **widest internal inter-cue gap** (ties → the gap nearest the section
midpoint; a section needs ≥ 2 lines to split), then run the existing
window/pad/midpoint-clamp loop once over the final boundary list. Comment the
tradeoff: a sub-`SECTION_GAP_S` boundary is not guaranteed silence — the
midpoint clamp and the repace rescue bound the damage, and whole-song
single-slice drift is the greater evil.

Tests: zero-gap 90 s cue list splits at its widest gap into ≤ 60 s sections;
a normally-gapped song is unchanged; recursive splitting respects the cap;
2-line oversized section splits 1+1.

Validation: `cue_align_corpus.py` (GPU) vs the Phase 0 cue baseline —
flag/overlap counts must not regress on normal songs and should improve on
the zero-gap class. Commit: `feat(cue-align): cap section duration for
zero-gap SRTs`.

(Optional 5c, only if the corpus run shows displacement aliasing on
non-adjacent repeats: widen `_repeat_detection_slacks`' neighbor scan from
lid±1 to the nearest identical line within ±3. Otherwise skip — don't add
unrequested robustness.)

## Phase 6 — checkpoint: transition-cost DP (decide, don't build)

> **MODEL BREAK (resolved 2026-07-12) — design already done by Fable.** The
> checkpoint's judgment is pre-registered as an offline probe with read-off
> GATE criteria, and the transition-cost design is locked contingent on a
> GO, as Appendix F. Execute on Sonnet 5; escalate per the "Model
> switching" rules.

After Phases 1-4.5 settle the corpus numbers, run the Appendix F probe and
GATE. The mechanism under decision: transition costs in
`_best_tiling_by_time` (`joint_match.py:724-768` already iterates all legal
predecessor pairs — a gap-plausibility penalty `g(cj, ci)` is structurally
a few lines, but a large tuning surface), plus the prerequisite of
preserving stanza breaks through `parse_lyric_lines`
(`pikaraoke/lib/genius_lyrics.py:76-104`) as line metadata. Nothing in this
plan builds it before a GO at the F2 GATE; Appendix F supersedes the
review's section 6 sketch with the locked shape. Sequencing: run the LRCLIB
study (`plans/lrclib-fill-absence-study.md`) first when feasible — F2
criterion 4 excludes lines its E2 verdict already covers, and the criterion
degrades to no E2 exclusion when the verdict does not exist.

## Explicitly rejected (do not implement)

- Rendering interp lines to raise coverage: measured interp population is
  ~57 correct drops vs ~22 real-but-unplaced — blanket filling is wrong ~70%
  of the time. Convert the 22 via Phases 1 and 4 instead.
- LRCLIB in production, or any new online timing source. LRCLIB is held-out
  scoring only.

## Verification matrix (every phase)

1. Import-smoke changed modules; run the unit suite (Linux conda; Windows has
   the 4 known baseline failures).
2. `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`.
3. Offline corpus replay diff vs the Phase 0 baseline table (phases 1-4);
   cue corpus run (phase 5); live phantom-song spot-checks (phase 3b).
4. Self-review the diff (correctness / simplicity / robustness), then commit.
5. At each phase boundary: alert Ken that a /code-review-qualifying batch is
   ready (never self-launch), and flag the boundary as a good /compact point.

---

## Appendix A — matcher accuracy review (2026-07-06, Claude Fable 5)

Scope: both matcher paths (joint DP for txt/Genius; cue-align for SRT), the
stage driver, the worker output contract, and the token layer. Goal axis:
maximize coverage while minimizing erroneous placements of lines that may not
exist in this mix. Constraint: no new online timing sources.

### TL;DR

One genuine correctness bug (the joint matcher's 1:1 align-words assumption
is violated by the worker's own config, silently corrupting align candidates
on exactly the hard songs), and one structural gap that is the root of the
phantom-line risk (the DP has no abstention bar — any positive-score candidate
that fits gets placed, and an align candidate scores >= alpha even over pure
instrumental). Both have concrete, offline-measurable fixes using data already
on hand. The cue path is structurally sound for the phantom concern; its
residual risks are pacing-level.

### 1. Correctness bug: `align_words` is not 1:1 with the lyric token stream (joint path)

The joint matcher's foundation is the cursor walk in `_line_align_ranges`
(`pikaraoke/lib/joint_match.py:357-393`), which assumes forced alignment emits
exactly one word per lyric token (`joint_match.py:99-101`). But the align
route runs with `remove_instant_words: True`
(`pikaraoke/pipeline/config.py:49`), which drops words stable-ts could not
time — and the cue path documents this exact fact: "The aligner drops words
it could not time (remove_instant_words), so the stream is a subsequence of
the section's lyric tokens, not a 1:1 list"
(`pikaraoke/lib/cue_align.py:250-252`). The two modules assert contradictory
contracts about the same `align_refine` worker call; the cue path's is the
correct one.

When a drop happens mid-song, every subsequent line's align range shifts by
one word — and drops accumulate. Consequences: (a) align candidates for all
downstream lines sit on partially wrong audio yet still carry the full
`alpha` bonus and `align_agreement = 1.0`; (b) `_align_line_object` renders
align-won lines with word timings borrowed from neighboring tokens (visible
sweep corruption); (c) the guard at `joint_match.py:374-376` only notices
when the stream runs out, so cumulative drops surface as the *last* lines
losing their align candidates entirely, while everything in between is
silently wrong. The drop rate is highest precisely on different-mix songs,
where the aligner is forced to place words for lines that don't exist — so
the bug concentrates on the songs that matter. The same assumption is
inherited by every span replay in windowed re-align. A second latent vector:
`_tokenise_lines` drops tokens that normalize to empty (a standalone `&` or
`—`) while the aligner may still emit a word for them; and enabling
`min_word_probability` on the align path
(`pikaraoke/pipeline/workers/whisper_worker.py:162`) would break the contract
the same way.

Fix: replace the blind cursor walk with a text-verified monotone assignment —
exactly the tool `_match_words_to_tokens` (`cue_align.py:176-235`) already is
(match on normalized equality, monotone, tolerant of dropped words). Verify
first, cheaply: the debug bundles store the refined align words and
`align_lines`, so a one-off script can count desyncs across the existing
corpus with no GPU.

### 2. Structural gap: no evidence bar for placement (the phantom-line vector)

`_best_tiling_by_time` (`joint_match.py:699-743`) maximizes total score with
no per-placement cost, so any non-conflicting candidate with positive score
is always placed. Every line with an align range gets an align candidate
scoring at least `alpha` (2.0), because `align_agreement` is 1.0 by
construction and the gate almost never zeroes it:

- In silence/instrumental, the gate *cannot* fire (`count < 2` keeps weight
  1.0, by documented design at `joint_match.py:461-466`). A surplus line the
  aligner parked over an instrumental gap is placed and rendered purely on
  align's say-so.
- Over sung audio, `any_overlap` is set-intersection including stopwords
  (`joint_match.py:687`) — two different lyric lines of the same song nearly
  always share an "I"/"the"/"you", so the gate has very low specificity for
  phantoms. It was built to catch Hakuna's *dialogue* (zero shared tokens);
  between lyric lines it rarely fires.

The repeat-pileup diagnosis showed surplus lines mostly do drop out — but
that's because crammed zero-width stacks conflict under the min-width pad and
lose to real neighbors. The survivors are exactly: one line per crammed
stack, plus anything parked in a gap wide enough not to conflict. Three
mechanisms, in recommended order (all offline-sweepable via the replay
harness):

- **2a. Use align word probabilities — the data is already flowing and
  already captured.** The worker keeps per-word `probability` explicitly "so
  the joint matcher can weight match scores by word confidence"
  (`whisper_worker.py:154-156`), but nothing in `pikaraoke/lib` ever reads
  it. Forced alignment's word probability directly measures how well the
  audio matched the forced token — a phantom line's align words should have
  distinctly low probabilities. Grading the align candidate's self-evidence
  by mean word probability (instead of a flat 1.0 behind a binary gate)
  attacks phantoms with zero new inputs, and the separation hypothesis is
  testable on existing captures before writing matcher code. It would also
  demote whisper hallucination-loop candidates if extended to the transcribe
  side.
- **2b. Vocal-energy veto for zero-corroboration placements.** A line placed
  with `transcribe_match == 0`, `ytasr_agreement == 0`, and an empty
  transcribe window is rendered on align's testimony alone; if the vocal
  stem's RMS envelope over its span is near-silent, no line should render
  there at all. `onset_snap.rms_envelope_db` (`onset_snap.py:79`) already
  decodes exactly this envelope in the same stage. Near-zero coverage risk:
  truly quiet-but-real vocals still show energy.
- **2c. A placement-cost knob (`joint_lambda`).** Subtracting a constant from
  every candidate score implements "place only if it earns more than λ"
  without changing any pairwise comparison — a one-parameter abstention
  control, default 0, sweepable on the corpus. Blunter than 2a/2b (a
  garbled-but-real line and a phantom both score exactly `alpha`), so it's
  the fallback, not the lead.

Related: the stopword-weak gate could be sharpened (require a content token,
or two distinct overlapping types when the window heard >= 4 words) — but if
2a lands, the binary gate matters much less.

### 3. Degenerate crammed align candidates: reject, don't pad

`_MIN_ALIGN_WIDTH_S` padding (`joint_match.py:73-79`) makes collapsed stacks
conflict so the DP keeps at most one — but that survivor is usually itself a
phantom, rendered as a sub-second flash line. An align candidate whose
pre-pad width implies impossible pace (under ~60 ms per token — faster than
any real singing) is an aligner give-up artifact, not a belief worth entering
into the DP; dropping it entirely lets the line's transcribe/ytasr candidates
(or honest interp) decide instead. Keep the pad for mild cases.

### 4. Windowed re-align: two asymmetries

- **4a. Span replays are 2-source** (`windowed_realign.py:197-205`) —
  deliberate, matching the experiment. But a line pass-1 left unplaced can
  only be rescued via transcribe corroboration, and the songs that need
  rescue most are those where transcribe is weakest. Threading the
  (window-filtered, same-clock) ytasr words plus `beta` into `replay_span` is
  low-effort and uses already-downloaded data. Needs a corpus re-run since it
  changes merge outcomes.
- **4b. Well-corroborated interior lines are exposed to lower-context
  overwrites.** Suspects gate *which spans* replay, but inside a chosen span
  every non-anchor pass-1 line can be replaced or dropped by the replay
  (`windowed_realign.py:243-251`) — including a strongly-corroborated line
  that merely missed anchor criteria (repeated text, or 3 tokens).
  `analyze_pass1` already computes each line's corroboration ratio and throws
  it away after the set test (`windowed_realign.py:96-108`); returning it and
  protecting high-ratio lines from being un-placed unless the replay meets
  the same bar reuses existing computation and closes a real "repair pass
  made it worse" hole.

### 5. Cue path (SRT)

Structurally this path already solves the phantom concern — placements are
bounded by uploader cues, and every line renders (fill guarantees coverage).
Two real items:

- **5a. No maximum section length.** `segment_by_gaps`
  (`cue_align.py:126-168`) splits only at gaps > 1.5 s. SRTs authored with
  padded cue ends (each cue stretched to meet the next) have zero gaps,
  producing one whole-song section — a single giant forced-align slice, the
  drift-prone regime windowing was built to avoid; the per-line rescue then
  repaces failures to cue timing, losing word-level accuracy wholesale.
  Capping section duration (~45-60 s, splitting at the widest available
  inter-cue gap) bounds this.
- **5b. Repeat-displacement detection only sees adjacent duplicates.**
  `_repeat_detection_slacks` (`cue_align.py:461-487`) checks `lid ± 1`, so
  "Hey! / other line / Hey!" alternating patterns bypass the containment
  requirement and get clean-trust. The cue-expected-time tiebreak protects
  most cases; extending the neighbor scan to the nearest identical line
  within a few positions is cheap insurance. Minor.

### 6. Bigger lever (major refactor): a transition-cost chain DP

The DP is pure interval scheduling: it knows order, but nothing about
plausibility of the gaps between placements. Consecutive stanza-internal
lines placed 40 s apart cost nothing; a phantom placed far from both its
lyric neighbors costs nothing. The loop at `joint_match.py:724-735` already
iterates all legal predecessor pairs — adding a transition penalty
`g(cj, ci)` (penalizing large audio gaps between lyric-adjacent lines, and
implausible implied tempo) is structurally a few lines, and it attacks the
phantom, pileup, and compression families in one principled mechanism. The
catch is the tuning surface, but the offline replay harness + corpus + MAD
metrics make it sweepable. Prerequisite worth doing regardless:
`parse_lyric_lines` (`genius_lyrics.py:76-104`) currently discards blank-line
stanza breaks and `[Verse]/[Chorus]` headers — real structural information
(where gaps are expected, which blocks are repeats) thrown away at parse
time.

### Recommended against

Rendering interp lines to raise coverage. Measured interp population is ~57
correct drops vs ~22 real-but-unplaced — blanket filling would be wrong ~70%
of the time, the opposite of the stated priority. The honest-abstention
design is right; convert the 22 via better rescue (4a) and the desync fix
(1), not fills. An energy-gated single-line fill could flip those odds
someday, but only with measurement.

### Suggested order (as executed by this plan)

1. Measure finding 1's frequency on existing bundles, then fix
   `_line_align_ranges` with a monotone text-verified assignment — it's a
   bug, and everything else sits on top of it.
2. Validate the align-probability separation (2a) on existing bundles; if it
   separates, fold it into the align candidate's evidence and re-sweep
   alpha/beta.
3. The energy veto post-pass (2b) and crammed-candidate rejection (3) —
   small, independent, each directly kills a phantom-render class.
4. 4a/4b together as a windowed-realign revision, corpus re-run.
5. 5a after checking the SRT corpus for zero-gap files.
6. Decide on the transition-cost DP (6) once 1-4 have settled the baseline.

Logistics note: the tuning harnesses (`replay_ytasr_third_source.py`,
`cue_align_corpus.py`) had not landed on this branch at review time (two-path
plan Phase F2) — hence Phase 0 of this plan.

---

## Appendix B — Phase 1b design spec (locked, Fable, 2026-07-06)

Implementation blueprint for the text-verified align-word assignment. The
executor implements this as written; deviations only via the "Model
switching" escalation rules. Design constraints honored throughout: no
import cycle (`token_align` imports nothing from the matchers; `cue_align`
already imports from `joint_match`, so `joint_match` may never import from
`cue_align`); behavior byte-identical to today whenever the aligner dropped
nothing; the correctness fix carries **no** evidence-policy change.

### B1. `token_align.match_words_to_tokens` (moved + generalized)

Move the DP out of `cue_align._match_words_to_tokens`
(`pikaraoke/lib/cue_align.py:176-235`) into `pikaraoke/lib/token_align.py`
as a public function with a sequence-only signature:

```python
def match_words_to_tokens(
    token_norms: list[str],
    token_times: list[float],
    word_norms: list[str],
    word_times: list[float],
) -> list[int | None]:
```

- The body is the existing DP verbatim — rolling rows, per-row `bytes`
  choice record, lexicographic `(matches, -total_deviation)` maximization,
  backtrack — with `word_norms`/`word_times` as parameters instead of being
  derived from `aligned_words` dicts inside.
- Matching stays **plain normalized equality**, not `_match_simple`: on both
  call paths the word stream was produced by forced alignment of the same
  text, so contraction/homoglyph divergence cannot arise; strict equality is
  the correctness check.
- Docstring keeps the max-matches / min-time-deviation contract and names
  both callers: the cue split (cue-expected times) and the joint align-range
  assignment (index pseudo-times, see B2).
- `cue_align` keeps a private adapter with the old name and old signature so
  its two call sites (`split_section_to_lines`, `_line_from_realigned`) and
  the cue tests are untouched:

```python
def _match_words_to_tokens(token_norms, token_times, aligned_words):
    return match_words_to_tokens(
        token_norms,
        token_times,
        [_normalize_token(w["word"]) for w in aligned_words],
        [w["start"] for w in aligned_words],
    )
```

- If `test_cue_align.py` has direct `_match_words_to_tokens` tests they stay
  green via the adapter. Add direct tests for the moved function to the
  token_align test module (create `tests/unit/test_token_align.py` if there
  is none): max-match priority over deviation, deviation tiebreak on a
  repeated token, empty token/word inputs, unmatched tokens padded None.

### B2. `joint_match._line_align_ranges` — new contract

Replace the blind cursor walk with a whole-song flat assignment:

```python
def _line_align_ranges(line_tokens, align_words):
    flat_norms = [norm for toks in line_tokens for norm, _raw in toks]
    assign = match_words_to_tokens(
        flat_norms,
        [float(k) for k in range(len(flat_norms))],
        [_normalize_token(w["word"]) for w in align_words],
        [float(j) for j in range(len(align_words))],
    )
    # split `assign` back per line; build one range dict (or None) per line
```

Per-line value: `{"t0": float, "t1": float, "word_idx": list[int | None]}`
where `word_idx[k]` indexes `align_words` for the line's k-th token.
`t0` = start of the line's first matched word, `t1` = end of its last
matched word, clamped `t1 = max(t0, t1)` as today. A line maps to `None`
when it has no tokens (unchanged) or **zero matched words** (new: honest
abstention — the aligner dropped the whole line, so it gets no align
candidate and is placed by transcribe/ytasr or falls to interp).

Decisions locked here:

- **Index-space pseudo-times on both sides** (`token_times = 0..N-1`,
  `word_times = 0..M-1`). There is no external clock on this path; index
  deviation is the twin-arbitration tiebreak, and a global index offset
  (from cumulative drops) cancels when comparing local alternatives — the
  same constant-shift argument the cue path's docstring makes for display
  lead. Known and accepted ambiguity: within a run of *identical* tokens the
  unmatched position is arbitrary (the tiebreak biases it toward run ends);
  the error is bounded by one word and inherent to indistinguishable tokens.
- Empty-norm words (the aligner emitting a word for `&`/`—` tokens that
  `_tokenise_lines` dropped) can never equal a non-empty token norm, so the
  DP skips them — desync vector (b) from the review is fixed for free, and
  needs its own test (t4).
- `token_start`/`token_end` disappear from the range dict **and** from the
  align-candidate dicts built in `_build_align_candidates`
  (`joint_match.py:557-558`). They are write-only today
  (`_align_line_object` reads `align_ranges[line_id]`, not the candidate),
  but grep the repo — including tests, `alignment_capture`, and the Phase 0
  harness — before deleting, and update any test that asserts on them.

### B3. `_align_line_object` — per-token mapping + shared interpolation

Extract the unmatched-run interpolation from
`candidate_match._build_line_object` (`candidate_match.py:221-246`: the
`win_start`/`win_end` anchoring, the `while k < n` run-filling loop, and the
`next_start < prev_end` clamp) into a module-level helper in
`candidate_match`:

```python
def _fill_unmatched_runs(
    tw: list[dict | None],
    line_toks: list[tuple[str, str]],
    win_start: float,
    win_end: float,
) -> list[dict]:
```

`_build_line_object` calls it (behavior byte-identical — its existing tests
are the guard). `_align_line_object` becomes:

```python
def _align_line_object(line_id, text, toks, align_words, align_range):
    if align_range is None:
        return {..., "words": [], "start": None, "end": None}  # unchanged
    tw: list[dict | None] = [None] * len(toks)
    for k, (_norm, raw) in enumerate(toks):
        wi = align_range["word_idx"][k]
        if wi is not None:
            w = align_words[wi]
            tw[k] = {"word": raw, "start": w["start"], "end": w["end"]}
    words = _fill_unmatched_runs(tw, toks, align_range["t0"], align_range["t1"])
    return {"text": text, "line_id": line_id, "words": words,
            "start": words[0]["start"], "end": words[-1]["end"]}
```

When nothing was dropped, `word_idx` is fully populated and contiguous and
the output equals the old zip exactly — asserted by t1.

### B4. Stats

`joint_stats["n_align_word_drops"] = n_flat_tokens - n_matched` (counts from
the flat assignment). Additive key only; `joint_stats` is serialized as-is
into the capture bundle, so no schema change.

### B5. Non-goals (locked)

- No evidence-policy change: a line with >= 1 matched word keeps its align
  candidate and today's flat `align_agreement = 1.0`. Evidence grading is
  Phases 2-3; mixing it into the correctness fix would confound the 1c
  corpus diff.
- `_MIN_ALIGN_WIDTH_S` padding, `_alpha_weight`, `_corroboration_weight`,
  and the DP scoring are untouched.
- `windowed_realign.replay_span` inherits the fix through the shared
  function; no edits there.
- The public signature of `match_words_to_lines_joint_with_stats` is
  unchanged.

### B6. Performance

One O(N x M) DP per joint run and per span replay (N, M in the hundreds);
the existing candidate scans and the O(M^2) interval DP dominate. No
optimization, no early exits.

### B7. Tests (`tests/unit/test_joint_match.py` unless noted)

- **t1 regression, clean 1:1**: 3 lines of distinct tokens, words exactly
  1:1 → ranges and `_align_line_object` outputs equal the old zip behavior;
  `n_align_word_drops == 0`.
- **t2 mid-stream drop**: drop one word inside line 2 of 3 → lines 1 and 3
  ranges/words exact (the old code shifted them); line 2's range spans its
  remaining matched words with the missing token interpolated inside
  `[t0, t1]`; `n_align_word_drops == 1`. Include one end-to-end
  `match_words_to_lines_joint_with_stats` run asserting line 3 is align-won
  with exact word timings.
- **t3 whole line dropped**: that line's range is `None`, it gets no align
  candidate, the matcher still completes (line placed by transcribe or
  interp); neighbors exact; `n_align_word_drops == 3`.
- **t4 empty-norm extra word**: a `"&"` word in the stream between lines →
  all ranges exact, no shift, `n_align_word_drops == 0`.
- **t5 twins with anchor**: two identical lines `"na na boom"`, one word
  dropped from the first → line 2's `word_idx` still points at line 2's own
  words (assert via word times), i.e. the tiebreak does not let line 1
  steal across the anchor.
- **t6** direct tests for the moved `match_words_to_tokens` (see B1).
- **t7** `_fill_unmatched_runs` extraction: existing `_build_line_object`
  tests stay green; add one direct interpolation test only if none exercise
  an unmatched run today.

### B8. Commits

1. `refactor(token-align): move match_words_to_tokens out of cue_align` —
   B1 (move + adapter + t6); cue tests green, zero behavior change.
2. `fix(joint-match): text-verified align-word assignment survives aligner
   word drops` — B2-B4 + t1-t5, t7, with the `_fill_unmatched_runs`
   extraction riding along (split a `refactor(candidate-match)` commit out
   first only if the diff reads poorly).

Reminder (Phase 0 hard ordering): neither commit lands on the working branch
until the pre-fix baseline table is captured.

---

## Appendix C — Phase 2a analysis protocol (locked, Fable, 2026-07-06)

Pre-registered so the GATE is a read-off, not a judgment formed after seeing
the data. Scratchpad scripts only, nothing committed; tables and the verdict
go into the Results log.

### C1. Prerequisite checks (run on the FIRST regenerated bundle)

- Bundle `words` entries carry `probability` (the align/refine path
  preserves it via `_extract_words`; the capture must not strip it). If
  absent: STOP and fix the capture before the corpus finishes regenerating —
  the study is dead without it.
- Bundle has `lyrics.align_lines`, `joint_stats.selected_source`, and the
  output line timings (all present in the current schema).

### C2. Per-line metric

For each joint-method bundle, run the B2 assignment offline on
(`align_lines` tokens, captured refine words). If 1b has not landed yet,
import from the worktree implementation or inline a copy of the DP in the
scratch script — it is throwaway code. Per placed line (`selected_source`
in {align, transcribe, ytasr}):

- `p_mean`, `p_median`, `p_min` over the line's matched align words'
  probabilities (compute all three; the winner becomes 2b's discriminator).
- `n_matched / n_tokens` (align-evidence coverage).
- Lines with zero matched align words are excluded from the distributions
  and counted separately — they carry no align evidence at all.

### C3. Labels — three proxies

- **P1, independent SRT**: songs where
  `ground_truth_refs.youtube_srt_present` and not
  `youtube_srt_is_lyric_source`. Normalize cue texts through the same
  pipeline (`clean_srt_line` + `_tokenise_lines`). A lyric line is PRESENT
  if some single cue — or some concatenation of two adjacent cues (lyric
  lines can span cue splits) — contains >= 2/3 of the line's tokens by
  edit-distance overlap (`n - dist >= ceil(2n/3)`); else ABSENT. Per-song
  sanity: if fewer than 50% of a song's lines are PRESENT, the segmentation
  mismatch is too large — exclude the song rather than trust its labels.
- **P2, held-out timing error** (16-song corpus; needs the Phase 0
  harness): per line, error = |placed start - reference start| against the
  held-out reference. WRONG if error > 2.0 s, RIGHT if < 0.5 s, unlabeled
  between.
- **P3, manual gold**: Bloodstream (4:07 cut), In Summer, HUNTR_X — mark
  known-absent lyric lines from the known shorter mixes (Ken confirms).
  Small sample, highest label quality.

### C4. Statistics and GATE criterion (pre-registered)

- Per proxy: class medians + IQRs, rank AUC (hand-rolled Mann-Whitney over
  ranks — no new dependencies), and a per-song breakdown table.
- **Proceed to 2b iff AUC >= 0.75 on P2 (primary, largest clean sample) AND
  P1/P3 agree directionally** (no proxy shows inverted separation).
  AUC 0.60-0.75: take the tables to Ken as a judgment call. Below 0.60:
  skip 2b, record the outcome in the Results log; Phase 3 proceeds
  regardless.
- Interpretation caveat to carry into the report: low align probability may
  also mark correctly-placed-but-quietly-sung lines; P2's RIGHT-class
  distribution and the per-song breakdown bound that confound.

### C5. Outputs

One Results-log entry containing: the metric definitions actually used, the
per-proxy AUC table, the per-song table, the GATE verdict, and — if
proceeding — which aggregation (`p_mean`/`p_median`/`p_min`) 2b should use.

---

## Appendix D — Phase 3b design decisions (locked, Fable, 2026-07-07)

Contract decisions for the vocal-energy veto. The executor implements this
as written; deviations only via the "Model switching" escalation rules.
Phase 3a needs no appendix — its phase text is already the full spec.

### D1. Evidence rides on the line object, not in joint_stats

The phase sketch said `joint_stats["selected_evidence"][lid]`. That is wrong
in one detail the sketch missed: the veto runs **after** windowed re-align,
and `merge_spans` can replace a pass-1 line object with a span replay's — a
stats map keyed from pass-1's winning candidates would then describe
candidates that no longer produced the objects (stale evidence). Instead:

- `_materialise_line_objects` (`joint_match.py`) attaches the winning
  candidate's evidence to every object it builds:
  `obj["evidence"] = {"transcribe_match": cand["transcribe_match"],
  "ytasr_agreement": cand["ytasr_agreement"]}`.
- Span replays run the same matcher, so replay-produced objects carry their
  own sub-match evidence automatically and `merge_spans` passes objects
  through untouched — evidence stays in sync with whichever pass produced
  the placement, with zero merge/stats plumbing.
- Interp placeholders and cue-path objects never get the key; a missing
  `evidence` key means "never veto" (belt-and-braces — the stage gate in D3
  already keeps the veto off those routes).

Zero-evidence is `transcribe_match == 0 and ytasr_agreement == 0.0`; by
construction (transcribe candidates carry their own positive `t_score`,
ytasr candidates their own `y_agree`) only align-won objects can be
zero-zero, so the `source == "align"` check below is documentation, not a
filter.

### D2. `pikaraoke/lib/evidence_veto.py`

```python
from pikaraoke.lib.onset_snap import HOP_S, MIN_REF_DB

def veto_uncorroborated_lines(
    line_objects: list[dict],
    env: np.ndarray,
) -> tuple[list[dict], dict]:
```

(Signature deviates from the phase sketch: with D1, `joint_stats` is not an
input; the stage stores the returned stats — see D3.)

- Veto candidates: `words` non-empty, `source == "align"`, `evidence`
  present with `transcribe_match == 0` and `ytasr_agreement == 0.0`.
- Silence test: median of `env[int(start / HOP_S) : int(end / HOP_S) + 1]`
  (slice clamped to `[0, len(env))`; an empty slice — a line past the
  envelope end — is *not* silence evidence, skip it) below the floor →
  veto.
- Threshold (locked): **absolute floor only, reusing
  `onset_snap.MIN_REF_DB` (-45.0 dB)** — the exact level onset_snap already
  treats as "not singing anywhere in the claimed span; an upstream
  misplacement problem" (`onset_snap.py:71-76`). The veto *is* that
  upstream fix, so the two features share one calibrated constant (import
  it; never copy the value). No relative-to-song-reference tier in v1: a
  relative bar risks vetoing quietly-sung real lines (the Phase 2a confound
  in energy form), and the phase GATE's live line-list review can catch a
  too-timid veto far more easily than a too-eager one. Record per-line
  `median_db` in the stats so the GATE data supports raising the floor
  later if -45 proves too timid.
- Demotion: replace with a copy — `words=[]`, keep `start`/`end`,
  `source="veto"`; never mutate in place (onset_snap's copy discipline).
  ASS/SRT generators already skip word-less lines.
- Stats: `{"n_zero_evidence", "n_vetoed", "lines": [{"line_id",
  "median_db", "vetoed"}]}` — one entry per zero-evidence line whether
  vetoed or kept; the kept-with-energy ones are the GATE's evidence about
  where the threshold sits.

### D3. Envelope sharing (stage wiring)

- Rename `onset_snap._decode_env` → `onset_snap.decode_env_db` (public;
  three internal call sites update; zero behavior change). onset_snap is
  our own module, so the fork rule does not apply.
- `snap_line_edges(line_objects, vocal_path, env=None)` — new optional
  parameter mirroring `snap_line_onsets`/`snap_line_ends`; `None` keeps
  today's internal decode-and-bail.
- `lyric_align.run()`: decode once before the snap block —
  `env = decode_env_db(snap_stem, "edge snap")`. On the joint route only
  (`capture_method_used == "joint"`) and only when `env is not None`, run
  the veto first and store its stats as
  `capture_joint_stats["evidence_veto"]`; when `env is None` store
  `{"bailed": "decode_failed"}` instead. Then
  `snap_line_edges(line_objects, snap_stem, env=env)` — a None env
  re-attempts the decode internally and bails with its own stats (the
  pathological path may log the failure twice; accepted). Cue route and
  transcribe mode: no veto call, snap unchanged.

### D4. Tests

- Veto module (`tests/unit/test_evidence_veto.py`, real numpy envelopes):
  zero-evidence align line over a silent span → vetoed (words emptied,
  start/end kept, `source="veto"`); same line over sung-level energy →
  kept; `transcribe_match > 0` over silence → kept; `ytasr_agreement > 0`
  over silence → kept; missing `evidence` key → kept; stats shape.
- Evidence attach (`test_joint_match.py`): objects from all three sources
  carry `evidence` matching their winning candidate's terms.
- Stage (`test_lyric_align.py`): veto runs on the joint route between the
  re-align merge and the snap; envelope decoded once (mock
  `decode_env_db`); transcribe mode and cue route never call the veto.
- onset_snap (`test_onset_snap.py`): `snap_line_edges` with a precomputed
  `env` skips the decode; existing tests stay green unchanged.

### D5. Non-goals (locked)

- No transcribe-side veto (the review's "extended to the transcribe side"
  is future work), no relative threshold tier, no config knob.
- The veto only demotes: it never moves, restores, or re-times a line.

### D6. Commit

One commit: `feat(pipeline): vocal-energy veto for uncorroborated align
placements` — evidence attach + onset_snap env param/rename + veto module +
stage wiring + tests. Split a `refactor(onset-snap)` commit out first only
if the diff reads poorly.

---

## Appendix E — Phase 4 implementation blueprint (locked, Fable, 2026-07-07)

Design constraints honored throughout: `replay_span(..., ytasr_words=None)`
and `merge_spans(..., pass1_ratios=None)` are byte-identical to today (all
existing tests stay green unmodified); the span set, suspect analysis, and
anchor criteria are untouched; nothing changes inside the sub-match's
scoring — the revision lives entirely in the replay/merge layer.

### E1. `replay_span` — third source + beta (4a)

New keyword-only parameters, defaults preserving today's behavior:

```python
def replay_span(
    span, span_words, transcribe_words, lines, align_lines, *,
    alpha, margin_s, max_edit_ratio,
    beta: float = 2.0,
    ytasr_words: list[dict] | None = None,
) -> tuple[dict[int, dict], dict[int, str]] | None:
```

- Filter ytasr words to the span with the same pad as transcribe words:
  `window_ytasr = [w for w in ytasr_words if span["t0"] - TRANSCRIBE_PAD_S
  <= w["start"] <= span["t1"] + TRANSCRIBE_PAD_S]`. Pass
  `ytasr_words=window_ytasr or None` and `beta=beta` into the sub-match
  (one comment: same pad, same rationale — boundary lines straddle).
- Index consistency: the sub-match's `ytasr_idx_*` index the **filtered**
  list and its materialisation slices from the list it was handed — pass
  `window_ytasr` itself into the sub-match; never re-slice from the
  caller's full list.

### E2. Merge policy for new placements (4a)

The `merge_spans` new-placement rule (`windowed_realign.py:244`) becomes
`sources2.get(lid) not in ("transcribe", "ytasr")`: a pass-1-unplaced line
may be newly placed when the replay selected it from either source
independent of the span's own align. Update the module docstring's second
merge-policy bullet accordingly ("transcribe or ytasr — independent
corroboration").

### E3. Corroborated-line protection (4b)

- `analyze_pass1` returns `(anchors, suspects, ratios)`.
  `ratios: dict[int, float]` holds `matched / len(seq)` for exactly the
  lines that reach the ratio computation today (placed by
  align/transcribe/ytasr with a start; display-only and unplaced lines
  absent). Callers updated: `lyric_align._realign_windows` (uses ratios),
  harness `_score_against_lrclib` (unpacks, ignores), six
  `test_windowed_realign.py` call sites (unpack).
- `replay_span` attaches to each placed replay object its own transcribe
  corroboration:
  `obj["corrob_ratio"] = matched / len(seq)` via
  `_transcribe_match_and_count_in_window(seq, window_norms, window_starts,
  obj["start"], obj["end"], margin_s, max_edit_ratio)` over the span's
  padded `window_words` (comment: the pad covers the span, so window words
  suffice). Empty token seq → 0.0 (defensive; placed objects always carry
  tokens).
- `merge_spans` gains keyword-only
  `pass1_ratios: dict[int, float] | None = None`; `None` disables
  protection (today's behavior — keeps existing positional-call tests
  green). New rule, after the edge-tolerance check, before the pop:

```python
protected = (
    pass1_ratios is not None
    and lid in placed1
    and pass1_ratios.get(lid, 0.0) >= SUSPECT_RATIO
)
if protected and (cand is None or cand.get("corrob_ratio", 0.0) < pass1_ratios[lid]):
    continue  # non-suspect pass-1 line: the replay must meet its bar
```

  - Replay leaves a protected line unplaced → pass-1 kept (no
    honest-unplace for corroborated lines).
  - Replay moves it → adopted only at `corrob_ratio >= ratios[lid]` AND
    within the existing edge tolerance.
  - Suspect lines (`< SUSPECT_RATIO`) and lines absent from `ratios` keep
    today's behavior exactly.
- **Locked: the protection ratio stays transcribe-based.** Do not fold
  ytasr agreement into it. The Girl in the Bubble lines (ytasr-placed,
  transcribe-silent) sit below `SUSPECT_RATIO` by construction — they are
  deliberately unprotected here; their rescue is E1/E2 (the 3-source replay
  re-places them from the same ytasr evidence). Widening the ratio would
  change the meaning of the suspect set and confound the corpus diff; this
  guard's only job is review finding 4b's "strongly corroborated line that
  missed anchor criteria" class.

### E4. Stage plumbing

`_run_joint` already parses `ytasr_words` — pass them into
`_realign_windows`, which threads them through `_realign_one_span` into
`replay_span`; `beta=self._config.joint_beta` is read at the `replay_span`
call site, like alpha. `_realign_windows` already calls `analyze_pass1` —
capture `ratios` there and hand them to `merge_spans`. No new worker calls;
no capture-schema change (spans are captured as today; ytasr words come
from the persisted json3 both live and offline).

### E5. Harness updates (ride with the 4a commit)

- `_replay_spans_at_alpha(bundle, alpha)` →
  `_replay_spans(bundle, ytasr_words, alpha, beta)`, called inside the beta
  loop — the "one replay per alpha serves the whole beta row" caching is
  dead once the sub-match consumes beta. Replays are CPU-cheap; nothing
  replaces the caching. The `n_ytasr_candidates == 0` beta-shortcut in
  `main` is unaffected.
- `_replay_output`: compute `ratios` by calling `analyze_pass1` on the
  pass-1 replay output (its `stats` already carry `selected_source`), then
  pass `pass1_ratios=ratios` to `merge_spans` — mirroring the stage
  exactly.
- Coverage column (the Phase 4 harness amendment): per song print
  `n_placed/n_lines` (`n_lines = len(bundle["lyrics"]["lines"])`), suffixed
  `!` when coverage falls below `--min-coverage` (new arg, default 0.85 —
  Ken calibrates). This flags what the Phase 0 baseline missed: Girl in the
  Bubble sat unflagged at 26/36 (0.72).

### E6. Tests (`tests/unit/test_windowed_realign.py`)

- t1: `ytasr_words=None` + `pass1_ratios=None` → all existing tests green
  unmodified (that *is* the 2-source regression suite; add no copy).
- t2: new placement from ytasr — pass-1-unplaced line, replay selects it
  from ytasr within edge tolerance → adopted.
- t3: window filter — a ytasr word outside span±`TRANSCRIBE_PAD_S`
  contributes no candidate.
- t4: protected line, replay leaves it unplaced → pass-1 kept.
- t5: protected line, replay moves it — `corrob_ratio` below pass-1's →
  kept; at/above → adopted.
- t6: suspect line still replaceable and droppable (today's behavior).
- t7: `corrob_ratio` attached to placed replay objects, computed over the
  padded window words.
- Stage wiring: ytasr words, beta, and ratios reach
  `replay_span`/`merge_spans` (extend the existing wiring test in
  `test_lyric_align.py`).

### E7. Acceptance + validation protocol

Fully offline (span `align_words` are captured; json3 is on disk):

1. Re-run the harness at alpha=2.0/beta=2.0 over the 16-song corpus; diff
   against the Phase 0/1c tables. No placed-count regression, no MAD
   worsening, no new large overlap.
2. **Girl in the Bubble acceptance**: placed 26 → expect ~31-33; lines
   13/14/16/17/19 placed (13 also depends on Phase 3a, which lands first
   per plan order); 8/15/18 best-effort; 32/33/35 stay absent by design.
3. GATE per the phase text: adopt on favorable deltas; the two commits are
   independently revertable (E1/E2 vs E3 judged on their own numbers).

### E8. Commits

1. `feat(windowed-realign): ytasr third source in span replays` — E1 + E2 +
   the E4 ytasr/beta threading + E5 + t2/t3.
2. `fix(windowed-realign): protect corroborated pass-1 lines in the merge`
   — E3 + the remaining ratio plumbing (stage + harness) + t4-t7.

---

## Appendix F — Phase 6 checkpoint protocol + contingent transition-cost design (locked, Fable, 2026-07-12)

Phase 6 was a MODEL BREAK to Fable because it mixed judgment (do the settled
numbers justify a new tuning surface?) with design (what exactly would be
built?). This appendix removes both needs: the judgment is pre-registered as
an offline probe with read-off criteria (F1-F2 — the same treatment Appendix
C gave Phase 2a), and the design is locked contingent on a GO (F3-F4). Sonnet
5 executes the probe (per "Model switching"); escalate implementation — Opus
first, Fable if still needed — only if a criterion is ambiguous on real data
or the probe cannot be computed as specified. The F2 GATE itself still gets
Opus's read before Ken rules, per the "Judge results" role.

### F1. Pre-registered reachability probe (offline, scratchpad, no commit)

The transition-cost DP only pays if wrong placements actually look
transition-implausible while correct ones don't. That is measurable on the
post-Phase-4 corpus before building anything.

Data: the then-current replay-harness run at α=2.0/β=2.0 over the 17-song
corpus (the post-Phase-4 baseline table), final merged placements. Labels:
P2 exactly per Appendix C.3 (offset-corrected error vs the held-out
reference; RIGHT < 0.5 s, WRONG > 2.0 s, bail songs excluded). Note the
probe measures final placements rather than DP chains — an approximation in
the permissive direction: if the statistic cannot separate labels on final
output, a DP-internal penalty has no separation to exploit either.

Statistic — for each consecutive placed pair (j, i) in a song's final
line-id-ordered chain, using F3's constants (`G0 = 8.0`, `A = 6.0`,
`RAMP_S = 10.0`):

```
gap     = max(0.0, start_i - end_j)     # merged output may graze-overlap
k       = line_id_i - line_id_j         # >= 1
allowed = G0 + (k - 1) * A
p(j,i)  = 0                              if a stanza break lies in
                                          (line_id_j, line_id_i]
        = min(1.0, max(0.0, gap - allowed) / RAMP_S)   otherwise
```

Per placed line: `T = max(p(prev, line), p(line, next))` (chain edges use
the one existing side). Two arms:

- **metadata arm (the decision arm)**: stanza breaks recovered offline from
  the song's raw lyric text — run the extended `parse_lyric_lines` (F3) on
  the on-disk lyric source and verify the parsed line texts equal the
  bundle's `lyrics.lines`; a song failing recovery drops to the no-metadata
  arm and is flagged in the table.
- **no-metadata arm**: all-False breaks. Reported for context only —
  mid-stanza instrumental gaps will fire here; that is expected, not
  disqualifying.

Report per song and corpus-wide: T distributions by label; AUC
(rank/Mann-Whitney, hand-rolled, same convention as C4); count of RIGHT
lines with T >= 0.5 (collateral); count of WRONG lines with T >= 0.5 split
by the object-carried `evidence` key — zero-evidence align lines are the
shipped 3b veto's class (`evidence_veto.veto_uncorroborated_lines` demotes
the near-silent subset of exactly these), so the DP's marginal value is the
corroborated wrongs; and, when the LRCLIB study
(`plans/lrclib-fill-absence-study.md`) has run, which of those
lines its E2 strong-absence set already covers.

Predictions to check at the GATE (written blind to the probe, 2026-07-12,
against post-3a numbers): Bloodstream's residual 4:07-cut surplus repeats
(the pile-up minus the 3 flash lines 3a already dropped) carry high T in
the metadata arm; the no-metadata arm shows materially worse RIGHT
collateral; transcribe/ytasr-won RIGHT lines sit at T ≈ 0. (Defying
Gravity, the other known overhang, is a bail song — excluded from P2 labels
by construction, so it cannot appear in these tables.)

### F2. GATE criteria (pre-registered; Ken may adjust only before unblinding)

Read in order; the first failure stops the phase:

1. **Volume bar**: labeled WRONG placements >= 15 corpus-wide post-Phase-4
   (context: 34 at the 2a study — 15 means Phases 3-4 killed less than
   half). Below 15: NO-GO — the residual mass no longer justifies a new
   tuning surface; record the count and close Phase 6.
2. **Separation bar** (metadata arm): AUC(T; WRONG vs RIGHT) >= 0.75 → GO.
   0.60-0.75 → tables to Ken as a judgment call. < 0.60 → NO-GO.
3. **Collateral bound**: RIGHT lines with T >= 0.5 must be < 5% of RIGHT.
   Breach → NO-GO regardless of AUC (or Ken re-scopes `G0`/`A` upward once,
   stating the new constants before unblinding the re-run).
4. **Marginal value**: of the WRONG ∧ T >= 0.5 lines, at least 5 must be
   veto-ineligible (carrying non-zero `evidence` corroboration — the
   shipped 3b veto only demotes zero-evidence align lines) and outside the
   LRCLIB E2 demotion set (when that verdict exists). The DP must kill
   something nothing else reaches.

### F3. Locked design (build only on a GO)

**Penalty.** In `_best_tiling_by_time`, transitions only — `dp[i]`'s
initialisation as a fresh chain start is untouched, and no chain-end cost.
The relaxation (`joint_match.py:757`) becomes:

```python
candidate_score = dp[j] + ci["score"] - g(cj, ci)
```

with `g` as in F1 times `lam`:
`g(cj, ci) = lam * p(cj, ci)`, `gap = max(0.0, ci["t0"] - cj["t1"])`,
`allowed = G0 + (ci["line_id"] - cj["line_id"] - 1) * A`.

Constants: `RAMP_S = 10.0` and `A = 6.0` fixed (shape parameters,
second-order); `lam` and `G0` are the sweep surface (F4), defaults
`lam = 0.0`, `G0 = 8.0`. `lam == 0.0` or `stanza_breaks is None` disables
the term exactly — replays of old bundles and production-before-adoption are
byte-identical by construction. Saturation is the safety argument: a
transition can lose at most `lam <= alpha`, so a corroborated real chain
(per-line scores >= 3) survives any gap, while an uncorroborated phantom
(score exactly `alpha`) is fully cancelled by a saturated implausible gap —
precisely the target class. Precompute a cumulative stanza-break count per
line so the crossing test is O(1); the DP stays O(M²).

**Stanza metadata.** `parse_lyric_lines` gains `stanza_break_before: bool`
on each returned line dict: True iff the nearest preceding raw line was
blank or a `_HEADER_RE` header (first line: False). The stage threads a
parallel `stanza_breaks: list[bool]` from `_load_lyrics` into the matcher's
new keyword `stanza_breaks: list[bool] | None = None`;
`windowed_realign.replay_span` slices it `[lo : hi + 1]` alongside
`lines`/`align_lines` and passes it into the sub-match (post-Phase-4 it
joins Appendix E1's keyword-only group, default `None` — byte-identical
when absent, same convention). Capture: additive `lyrics.stanza_breaks`
key + `schema_version` bump. The cue route is not threaded — cue placements
are bounded by uploader cues; out of scope.

**Harness.** `replay_ytasr_third_source.py` gains `--lambda`/`--g0`
pass-throughs and the F1 stanza-recovery helper (bundles predating the
schema bump recover breaks from the on-disk lyric text; a song failing
recovery replays with `stanza_breaks=None` and is flagged).

**Tests** (ride with the DP commit): `lam=0` / no metadata → byte-identical
selection on an existing end-to-end construction; a zero-corroboration
phantom candidate parked in a wide same-stanza gap is no longer selected
(falls to interp) once `lam` saturates; the same candidate across a stanza
break is kept; a corroborated chain spanning a long mid-stanza instrumental
gap survives (score margin > `lam`); `replay_span` slicing keeps
local/absolute break indices consistent.

### F4. Sweep + adoption protocol (on a GO)

- Grid: `lam ∈ {0.5, 1.0, 2.0} × G0 ∈ {4, 8, 12}` s over the 17-song corpus
  at α=β=2.0. Per-cell metrics: WRONG removed-or-corrected; RIGHT lines lost
  (a RIGHT line unplaced or moved > 0.5 s); placed counts; MAD; overlap.
- Pre-registered selection: maximize WRONG removed subject to RIGHT lost
  <= 1 corpus-wide; ties → smaller `lam`, then larger `G0` (gentler).
  Robustness: the winning cell's grid neighbours must retain >= 70% of its
  net win — an isolated spike on 17 songs is not adoptable; take it to Ken
  instead.
- GATE: table + `.ass` render diffs of changed songs to Ken. On adoption the
  chosen constants land as `PipelineConfig.joint_transition_lambda` /
  `joint_transition_g0_s`, wired like `joint_alpha`. (Named to avoid
  collision with the review's 2c placement-cost `joint_lambda` — a
  different, still-rejected mechanism.)
- Commits: `feat(genius-lyrics): preserve stanza breaks as line metadata`;
  `feat(joint-match): transition-cost penalty in the tiling DP` (kwargs +
  harness flags + tests, defaults off); `chore(config): adopt swept
  transition-cost defaults` (only after the GATE).

### F5. Non-goals (locked)

- No tempo/implied-pace transition term — Phase 3a's shipped
  `_MIN_ALIGN_PACE_S` rejection owns the pathological case; a mild-tempo
  penalty is a second knob with no measured target class.
- No chain-start/-end boundary costs.
- No fold-in of the 2c placement-cost knob — orthogonal mechanism, stays in
  the review as the fallback.
- No cue-path changes; no revisiting 2a (align word probability stays out of
  the score — measured, no separation).

---

## Appendix G — Phase 4.5 study protocol + contingent veto-v2 design (locked, Fable, 2026-07-13)

Same treatment as Appendices C (pre-registered study) and D (contract): the
G1-G4 study runs exactly as written; G5-G6 are built only on a G4 adopt
verdict, and only for the discriminators G4 adopts.

### G1. Class enumeration (offline)

Replay the harness (post-Phase-4 matcher, α=2.0/β=2.0) over the 17-song
joint corpus; collect every final placed line whose object carries
`evidence == {transcribe_match: 0, ytasr_agreement: 0.0}` and non-empty
words. That is the veto class (only align-won objects can be zero-zero).
Envelope medians are not available offline — the subset the shipped silence
rule already demotes is known only for the three 2026-07-13 live-regen
songs (their bundles carry `evidence_veto.lines`); mark those, leave the
rest unmarked. In production v2 sees only silence-rule survivors, so a
line the silence rule would also demote appearing in the study is double
coverage, not conflict.

### G2. Labels

- **Primary — manual gold**: Ken labels every enumerated line PRESENT
  (sung in this mix, however garbled) or ABSENT (not in this mix).
  Corpus-wide expect tens of lines, not hundreds — one sitting. Labels
  already given, carried in: Defying Gravity 79/81/85-88 ABSENT (Ken,
  2026-07-13, the GATE finding — 85 "Bring me down" is ABSENT despite the
  sung riff; the riff is not this lyric line); Bloodstream's zero-evidence
  members of lines 39-64 PRESENT (the pre-fade repeats).
- **Secondary — LRCLIB E2 strong-absence** (when that study has run):
  corroboration only, never overrides manual gold; disagreements go in the
  report.
- P2 timing-error labels are NOT usable here: absence is not a timing
  error, and the class concentrates on P2's excluded bail songs (Defying
  Gravity is one).

### G3. Discriminators (exact formulas; compute all three per line)

Shared window convention: a stream's words whose `start` lies in
`[start − margin_s, end + margin_s)`, `margin_s = 0.3`, `bisect_left` on
starts — the `_transcribe_match_and_count_in_window` convention exactly.
Lexical overlap = non-empty set intersection of normalized tokens, the
`_alpha_weight` `any_overlap` convention.

- **CE (counter-evidence)** — per stream S in {transcribe, ytasr}:
  `fires_S = (count_S >= 2) and no lexical overlap between the line's
  tokens and S's in-window words`. CE fires iff either stream fires. This
  is `_alpha_weight`'s gate re-applied to the *final* placement window
  with ytasr as a second lexical witness — new information on both axes:
  scoring-time gates never read ytasr lexically, and realign/merge can
  move a window after scoring.
- **PF (probability floor)** — evaluated only when neither stream has
  `count >= 2` (ASR-silent; CE cannot fire): `p_med` = median
  `probability` over the line's align-built words that carry the key.
  2a-lock boundary (Appendix F5): probability stays out of candidate
  *scores*; a veto tier over the zero-evidence class is a narrower
  question — but it inherits 2a's burden of proof: adopt only on G4
  numbers, never on the Defying Gravity anecdote (2a measured phantom
  p_mean scattering 0.13-0.88 on Bloodstream). Sweep the threshold over
  {0.1, 0.2, 0.3}; G4 picks at most one.
- **TO (tail overhang)** — the line's `line_id` is greater than the last
  line whose `evidence` shows any corroboration AND its `start` is later
  than that line's `end`. Measured for the table; adoptable only under
  G4's stricter bar — it is the bluntest instrument and the likeliest to
  hit real align-only outros.

### G4. GATE criteria (pre-registered; read in order)

Per discriminator, on the manually-labeled class: `caught` = ABSENT lines
it fires on; `collateral` = PRESENT lines it fires on.

1. Adopt CE iff `collateral == 0` and `caught >= 2`. Exactly one
   collateral → judgment call to Ken with the lines shown; two or more →
   reject.
2. Adopt PF (at the single best swept threshold) iff `collateral == 0`
   and `caught >= 3` — stricter than CE because 2a already failed once on
   a wider class. Any collateral → reject outright (no judgment band).
3. Adopt TO only if it catches >= 3 ABSENT lines that no adopted
   discriminator covers, with `collateral == 0`.
4. If nothing is adoptable: record the study, close the phase with no
   code, and carry the residual class size into the Phase 6 probe report.

Composition on adoption: a silence-rule survivor is demoted iff ANY
adopted discriminator fires. No thresholds re-tuned after unblinding
(the C4/F2 convention).

### G5. Contingent implementation contract

- `evidence_veto.veto_uncorroborated_lines` gains keyword-only
  `transcribe_words: list[dict] | None = None` and
  `ytasr_words: list[dict] | None = None`. A `None` stream means that CE
  arm never fires; both `None` (and PF/TO unadopted) reduces exactly to
  the silence rule — existing tests stay green unmodified.
- Rule order per line: silence rule first (unchanged, including its
  stats); v2 evaluated only for kept zero-evidence lines.
- Demotion identical to the silence rule (copy, `words=[]`,
  `source="veto"`, `start`/`end` kept). Stats: each `lines[]` entry gains
  `"rule": "silence" | "counter_evidence" | "prob_floor" | "tail" | None`
  (None = kept) plus the computed per-line inputs (`ce` per stream,
  `p_med` when evaluated) so the next GATE can audit; additive
  `n_vetoed_v2` alongside `n_vetoed`.
- PF plumbing (only if PF adopted): `_align_line_object` copies
  `probability` onto the word dicts it builds when the align word carries
  it (additive key; generators ignore it; interpolated fill words carry
  none). Lines whose words lack the key skip PF — the 2b
  backward-compatibility convention for old bundles and probability-less
  outputs.
- Stage wiring: `lyric_align` already holds `transcribe_words` and parses
  `ytasr_words` on the joint route — pass both at the existing veto call
  site. Cue route and transcribe mode: no veto call today, still none.
- Tests (`test_evidence_veto.py`, wiring in `test_lyric_align.py`): CE
  fires on a zero-evidence line with >= 2 non-overlapping ytasr words in
  window; a single overlapping token → kept; ASR-silent line → CE cannot
  fire; PF per its adoption; silence-rule demotions and stats
  byte-identical when both streams are `None`; corroborated lines never
  evaluated; the stage passes both word streams on the joint route only.

### G6. Live validation (mirrors the 3b GATE protocol)

Regen Defying Gravity and Bloodstream via `regen_alignment_bundles.py`
(single-song schema-bump trick, full backups, as on 2026-07-13).
Pre-registered expectations: Defying Gravity 79/81 demoted by CE, plus
whatever G4 adopted for 86-88; line 85 expected to survive (documented
residual against Ken's ABSENT label); Bloodstream lines 39-64 all kept —
zero v2 demotions (the precision check); the silence rule's prior
demotions unchanged. Byte-check `start`/`end` on every demoted line
(demotes-never-moves, live).

### G7. Non-goals (locked)

- No candidate-score changes of any kind — the 2a/F5 lock stands; PF, if
  adopted, exists only inside the veto tier.
- No upstream lyric-version trimming or absence prediction from lyric
  structure: the repeat-pileup lever is real but a different, larger
  project.
- No new online sources; no cue-path changes; the veto still never moves,
  restores, or re-times a line.
- The `.srt` self-adoption hazard (Results log, 2026-07-13 GATE outcome)
  is out of scope — it needs its own decision, not a rider here.

### G8. Commit

One commit on adoption: `feat(pipeline): counter-evidence veto for
zero-evidence align placements` (PF word-probability plumbing rides
inside it; split a `refactor` out first only if the diff reads poorly).

---

## Results log

### Phase 0 — harness port + pre-fix non-SRT baseline (2026-07-06)

Branch `fable_matcher_refine` (off ship tip `89d28c46`, **pre-1b-fix** — the 1b
align-word-drop fix `4d38bc1a` lives only on `1b_align`; confirmed absent here:
no `n_align_word_drops` in `joint_match.py`). Harness port committed `a9aa3a8`.

The port diverged from this plan's step-2 wording because ship had moved past
`pathed_align`: the post-hoc timing prior is gone (`srt_cues` has no
`apply_srt_prior`), YTASR is folded in as a 3rd DP source, and edge-snap
(`snap_line_edges`, audio-dependent) now runs after re-align. So the harness's
old "old-scheme (2-source + prior) vs new-scheme" framing is obsolete — it now
replays ship's single scheme (3-source DP + windowed re-align, **no edge-snap**)
and scores that against held-out LRCLIB. The dead `replay_bundle`/prior path was
not inlined; the bundle's recorded (post-edge-snap) output is a sanity column.

Corpus: freshly regenerated by Ken this afternoon (schema v8, captured
14:15–16:52 UTC) with the current pre-fix matcher — 17 non-SRT (txt) + 16 SRT.

**Bit-faithfulness check (the step-2 gate):** at the bundles' own knobs
(α=2.0/β=2.0), the snap-free replay reproduces the recorded output's **placed
count and max-overlap for all 17 songs**. The only divergence is crawl count,
always rec ≥ new (e.g. Seasons 8→3, Next Ten Minutes 6→2) — the exact signature
of the omitted end-snap lengthening line-final words past the crawl threshold.
Divergence is fully attributable to edge-snap; the matcher replay is faithful.

**Reproducibility:** two consecutive runs were byte-identical. Reference tiers:
11/17 score against the reproducible flat cache `pikaraoke-songs/lrclib/<stem>`
(t2); 6 fall to a live LRCLIB fetch (t3, marked ↯) — but of those, 4 bail
`wide_spread` (a categorical outcome, MAD unused), leaving only Free / Domino /
Seasons with a live-fetched MAD number (all stable across the two runs).

Pre-fix baseline — `replay_ytasr_third_source.py <corpus> --alpha 2.0 --beta 2.0`.
`placed` is identical rec→new for every song (shown once). `bail:wide_spread` =
the held-out LRCLIB variant disagrees with the sung timing beyond the MAD gate,
not a placement failure. Overlap rec→new = 0.0 everywhere except Defying Gravity
(7.8s, unchanged).

| Song | src | MAD α2/β2 | crawl rec→new | placed | ref |
|------|-----|-----------|---------------|--------|-----|
| 'Defying Gravity' (Wicked 20th) | 3src | bail:wide_spread | 4→3 | 51 | ↯ |
| 'Free' (Sony Animation) | 2src | 0.20s / 16a | 2→1 | 40 | ↯ |
| 'Popular' (Wicked 20th) | 3src | bail:wide_spread | 3→3 | 52 | ↯ |
| Be Our Guest (B&tB 1991) | 3src | 0.16s / 49a | 1→0 | 77 | t2 |
| Belle (B&tB 1991) | 3src | 0.39s / 55a | 1→1 | 101 | t2 |
| Best Part Of Me (Ed Sheeran) | 3src | bail:wide_spread | 2→2 | 37 | t2 |
| Bloodstream (Ed Sheeran) | 3src | 0.58s / 11a | 1→1 | 51 | t2 |
| This Is What It Sounds Like (HUNTR/X) | 2src | bail:wide_spread | 0→0 | 33 | ↯ |
| Domino (Jessie J) | 2src | 0.43s / 7a | 0→0 | 62 | ↯ |
| In Summer (Josh Gad) | 2src | 0.36s / 14a | 2→2 | 29 | t2 |
| I'll Make a Man Out of You (Mulan) | 3src | bail:wide_spread | 0→0 | 36 | t2 |
| Paradise (NSYNC) | 2src | 0.27s / 10a | 4→2 | 55 | t2 |
| Colors of the Wind (Pocahontas) | 3src | 0.17s / 31a | 2→2 | 37 | t2 |
| Seasons of Love | 2src | 0.52s / 5a | 8→3 | 26 | ↯ |
| Hakuna Matata (Lion King) | 3src | 0.35s / 8a | 3→2 | 33 | t2 |
| The Next Ten Minutes | 2src | 0.46s / 52a | 6→2 | 68 | t2 |
| For Good – Girl in the Bubble (Wicked 2025) | 3src | 0.40s / 15a | 0→0 | 26 | t2 |

`src`: 3src = a usable YTASR track fed the DP a 3rd source; 2src = none, plain
align+transcribe (β is a no-op, shown `n/a` in the raw output).

**Cue-path (SRT) baseline:** deferred — optional now, required before Phase 5.
Run `cue_align_corpus.py` (GPU) over the 16 SRT songs for a flag-count baseline.

**Hard-ordering status:** the pre-fix baseline now exists in this log, so the
1b fix (`4d38bc1a`) is cleared to land on `fable_matcher_refine`. Phase 1c
re-runs the command above post-fix and diffs this table.

### Phase 1c — post-fix non-SRT replay diff (2026-07-06)

1b landed (`8ab2b71`+`72fe939`); harness+1b batch inline-reviewed (no blocking
findings). Re-ran `replay_ytasr_third_source.py <corpus> --alpha 2.0 --beta 2.0`
on the **same** schema-v8 corpus, post-fix. Reproducible (two runs identical,
including the live-fetch ↯ songs).

**15 of 17 songs byte-identical** to the Phase 0 table — same MAD, crawl,
placed, overlap. Confirms the fix leaves the clean 1:1 align case untouched and
does not perturb any already-placed line's timing.

**2 of 17 changed — both strictly additive align-word-drop recoveries** (the
predicted outcome):

| Song | src | change | MAD | note |
|------|-----|--------|-----|------|
| 'Defying Gravity' | 3src | placed 51→52, crawl 3→4 | bail:wide_spread (unchanged) | recovers a previously-dropped line; it is slow → +1 crawl. Overlap 7.8 unchanged. |
| Domino | 2src | placed 62→63, overlap 0.0→0.1 | 0.43s / 7a (unchanged) | recovered line grazes its neighbour by 0.1s (sub-frame). |

No regressions corpus-wide: no MAD worsened, no placed count dropped, no new
large overlap. The fix is purely additive — recovers 2 lines the aligner-word-
drop bug had silently discarded, every other line keeps its exact prior timing.
The 0.1s Domino overlap is the only cosmetic side effect, negligible.

### Phase 2a — align word-probability separation study (2026-07-06)

Pre-registered per Appendix C. Scratchpad only, nothing committed. **GATE verdict:
SKIP 2b** (P2 AUC below the 0.60 floor). Phase 3 proceeds regardless.

**Metric actually used:** fully offline, no matcher re-run. Per placed line whose
recorded `selected_source ∈ {align, transcribe, ytasr}`, ran the B2 assignment
(`_line_align_ranges` over `align_lines` tokens + captured refine `words`) and
took `p_mean`/`p_median`/`p_min` over the line's matched align words. Placement
start/source read from the shipped `output_line_timings`/`selected_source`.
Corpus: 17 joint songs; 149 interp/absent lines out of scope; only **4** placed
lines had zero matched align words (counted separately).

**C1 prerequisite:** PASS — every joint bundle's `words` carry `probability`.

**Proxy labels:**
- **P1 (independent SRT):** EMPTY — no qualifying song. Every SRT song in the
  corpus is `youtube_srt_is_lyric_source=True` (cue-path lyric source); no
  joint-path song carries an independent, non-lyric-source caption track.
- **P2 (held-out LRCLIB timing error, PRIMARY):** offset-corrected each non-bail
  song by its anchor median (same math as `offset_mad_against_cues`), then per
  line `err=|start-cue_start-offset|`; RIGHT `<0.5s`, WRONG `>2.0s`, unlabeled
  between. 5 bail songs excluded (wide_spread/few-anchor). Labeled: 363 RIGHT,
  34 WRONG.
- **P3 (manual gold):** per-line dump for Bloodstream / In Summer / HUNTR_X (not
  hand-labeled — P2 already decides the gate).

**Per-proxy AUC (rank / Mann-Whitney, RIGHT vs WRONG; ≥0.75 to proceed):**

| subset | p_mean | p_median | p_min |
|--------|--------|----------|-------|
| P2 all placed (R=363, W=34) | **0.500** | 0.456 | 0.488 |
| P2 align-sourced only (R=176, W=16) | **0.589** | 0.475 | 0.586 |

Class medians barely differ (all-placed RIGHT p_mean 0.772 vs WRONG 0.78;
align-only RIGHT 0.841 vs WRONG 0.79). No proxy shows inverted separation; there
is simply almost none.

**Why it fails (two confounds, both visible in the data):**
1. Low align prob is confounded by *winning source* — transcribe/ytasr-won songs
   (Free, Paradise, Colors of the Wind) have correct placements yet median align
   `p_mean` ≈ 0.1, because align was not the evidence that placed them.
2. Even isolating align-sourced lines, the forced aligner emits confident-looking
   words on mis-timed/phantom lines too (both classes' `p_min` IQR reach ~0.00).
   P3 corroborates: Bloodstream's phantom repeat pile-up (the 4:07-cut lines)
   scatters `p_mean` from 0.13 to 0.88 with no usable threshold.

This confirms the C4 caveat: a phantom line's align words are *not* reliably
low-probability. Align word probability is not a usable phantom discriminator, so
2b (grading `align_agreement` by align word probability) is dropped. The lever
for phantom/repeat lines remains upstream lyric-version over-count, per
[[project-alignment-repeat-pileup-diagnosis]]. Phase 3 (energy veto + crammed-
candidate rejection) is unaffected and proceeds.

Scratch script (throwaway, uncommitted): `phase2a_prob_separation.py`.

### 2026-07-07 — Girl in the Bubble coverage regression (field report, no code change)

Ken A/B'd shipped output against dev for 'For Good – Girl in the Bubble':
this branch renders 26 of 36 lines, dev rendered all 36. Diagnosed from the
debug bundles + `windowed_realign.py`; **not a new failure mode** — it is
review findings 4a/4b (plus 3a for one line), and Phase 4a is the fix.

Mechanism: pass 1 placed lines 13/14/16/17/19 from ytasr (transcribe is
nearly silent over 51-89s — 1 word). That same transcribe silence put their
corroboration below `SUSPECT_RATIO`, so the span replayed — but `replay_span`
is 2-source (no ytasr), so the replay left them unplaced, and `merge_spans`
pops every pass-1 interior placement in favor of the replay's result
(`windowed_realign.py:243-251`). The lower-context replay thus destroyed
pass-1's correct ytasr placements; they re-interpolated word-less into one
degenerate shared span (62.73-88.34) and never rendered. Line 13 was
re-placed by the replay as a zero-width crammed align candidate (3 words, 0 s
span) and dropped at render — finding 3a's class exactly.

The same collapse occurs on dev (identical `16/16 ... interp=6` replay log);
dev's LRCLIB prior fill ("16 filled") then repaired the damage post-hoc.
Removing LRCLIB exposed the bug, it did not cause it. Note 4b alone would
not protect these lines — its guard keys off transcribe corroboration, which
is precisely what is absent here; 4a is the load-bearing fix.

Per-line disposition of the 10 missing lines:

- 13/14/16/17/19 — recoverable via 4a (+3a for 13); ytasr json3 has
  near-verbatim words over 51-89s and pass 1 already placed them from it.
- 8/15/18 — marginal: ytasr garbles them ("She's been such beautiful
  stories", "of seeing it in"; "Eventually" lost to a `[music]` tag). 4a's
  new-placement merge rule gives them a shot; no guarantee.
- 32/33/35 — unrecoverable from on-disk sources (align, transcribe, and
  ytasr all garbage there); absent by design. Only LRCLIB ever timed them.

Why nothing alerted: the song sat in the Phase 0 baseline at placed 26 — the
harness diffs ship-vs-ship and scores MAD over placed anchors only, so a
coverage regression vs dev was invisible. Hence the Phase 4 harness
amendment (coverage column + flag) and the Phase 4a acceptance case.

### Phase 3a — crammed align-candidate rejection (2026-07-07)

`_MIN_ALIGN_PACE_S = 0.06` (~17 tok/s) added to `_build_align_candidates`:
before the min-width pad, an align candidate whose pre-pad pace
`(t1 - t0) / n_tokens` is below the floor is dropped outright (the aligner's
give-up signature, not a placement). Unit tests: crammed multi-line stack →
zero candidates; genuine 1-token 0.3 s line → kept; a sub-min-width but
plausible-pace 1-token line still pads to the min width (rewritten from the
superseded `test_collapsed_align_is_padded`, which used a 2-token zero-width
range that the pace check now drops). 56/56 `test_joint_match.py` green;
`test_windowed_realign` / `test_lyric_align` / `test_candidate_match` green.

**Validation method (isolation on current bundles).** The corpus was in flux
during the commit — Ken was swapping the Girl in the Bubble bundle mid-session.
So rather than diff against the stale Phase 0/1c table, isolated 3a directly:
replayed the **same** on-disk bundles once with the pre-3a matcher checked out
(parent `f416d8a`) and once with 3a applied. All 17 `rec` values match between
the two runs, so the diff is 3a's effect alone. `--alpha 2.0 --beta 2.0`.

**Re-confirmed on the standardized corpus (post-commit).** Ken then regenerated
the Girl in the Bubble bundle with the `onset_snap_on_ship` matcher so it is
internally consistent with the rest of the corpus. Re-ran the same isolation
(pre-3a `f416d8a` vs post-3a HEAD) on those standardized bundles: the diff below
reproduces **byte-identically** — Girl in the Bubble still 26 → 24, MAD
0.40 → 0.38, no crawl, no overlap. The regeneration does not change 3a's story.

Clean 3a diff (pre-3a `new` → post-3a `new`):

| Song | placed | MAD | overlap | crawl |
|------|--------|-----|---------|-------|
| 'Defying Gravity' | 52 → 51 | bail:wide_spread (=) | 7.8 → 2.2 | 4 → 3 |
| Bloodstream | 51 → 48 | 0.58s/11a (=) | 0.0 (=) | 1 (=) |
| Seasons of Love | 26 → 25 | 0.52s/5a (=) | 0.0 (=) | 3 (=) |
| The Next Ten Minutes | 68 → 67 | 0.46s/52a (=) | 0.0 (=) | 2 (=) |
| Girl in the Bubble | 26 → 24 | 0.40s → 0.38s/15a | 0.0 (=) | 0 (=) |
| (other 12 songs) | unchanged | unchanged | unchanged | unchanged |

**Verdict: favorable, purely subtractive of phantoms.** 12 of 17 byte-identical.
The 5 changed songs each shed 1-3 crammed align candidates. Quality signals all
point the right way: **no MAD worsened on any song** (unchanged on 16, improved
0.40→0.38 on Girl in the Bubble), **no new overlap anywhere** (Defying's dropped
7.8→2.2 — the crammed-stack-removal signature — and its slow flash line stopped
crawling, 4→3). By construction a line only loses placement when its align
candidate is >17 tok/s *and* neither transcribe nor ytasr covered it, i.e. an
align-only sub-second flash — a phantom, not a real anchored line (the untouched
MAD confirms every held-out anchor kept its timing). Bloodstream (-3) is the
known 4:07-cut phantom-repeat pile-up; those are exactly the flash lines 3a
targets. Commit `feat(joint-match): drop implausible-pace align candidates`.

Note for Phase 4: the current Girl in the Bubble bundle is the
`onset_snap_on_ship` regeneration (`3src`, 26 placed), now consistent with the
rest of the corpus — not the Phase 0 v8 capture nor the earlier troubleshoot
`2src`/36 one. Still re-confirm the 4a acceptance target (placed 26 → ~31-33)
against whatever bundle is on disk when Phase 4 runs, in case it is refreshed
again before then.

### Phase 3b GATE — vocal-energy veto live validation (2026-07-13)

Code landed `5625d85` (prior session). This entry is the plan's required
validation: bundles carry no vocal envelope, so the veto itself can only be
exercised by a real run, paired with a deterministic corpus replay to prove
the supporting refactor left everything else untouched.

**Live validation (GPU, real vocal-stem envelope).** Forced exactly
Bloodstream and HUNTR_X through `regen_alignment_bundles.py
"D:\shared\pikaraoke-songs"` — temporarily marked just those two bundles
stale (`schema_version` 8→0) so the other 31 library songs were scanned and
skipped untouched; both reused their recorded genius(+ytasr) lyric source, no
network fetch, no Genius prompt. Original bundles preserved (session
scratchpad) before the run.

| Song | n_zero_evidence | n_vetoed | vetoed line |
|------|------------------|----------|-------------|
| Bloodstream | 9 | 1 | line 65 "Callin' out across the line (Brokenhearted)" @ 226.99-232.33s, median −49.2 dB |
| HUNTR_X | 1 | 1 | line 32 "(Oh)" @ 150.01-151.03s, median −53.7 dB |

Both demotions hold up on inspection, not just the threshold number:

- **Bloodstream line 65** is the *last* of an 8x alternating repeat
  ("Callin' out across the line (Brokenhearted)" / "...(And I saw scars upon
  her)", lines 39-65), which continues as further word-fragment repeats into
  lines 66-73 — the extended-cut outro vamp this 4:07 official-video mix
  fades out before finishing. This is exactly the "4:07-cut phantom-repeat
  pile-up" flagged in Phase 2a/3a. The other 7 alternating repeats (lines
  39-64 — real corroboration or real energy) were correctly left alone; only
  the truly silent tail repeat was vetoed.
- **HUNTR_X line 32** is a lone `"(Oh)"` backing ad-lib, 1.0 s wide — the only
  zero-evidence align line in the whole song.

`start`/`end` are byte-identical before vs after on both vetoed lines —
confirms "demotes, never moves" live, not just in unit tests.

Full before/after diff of every `output_line_timings` entry (not just the
veto's own list): HUNTR_X changed exactly 1 line (the veto). Bloodstream
changed 11 — the veto line, plus 10 others (line 1, line 59, interpolation
ripple on 66-73) that are **not** in the veto's zero-evidence set. These
track to ordinary run-to-run whisper variance, not to 3b's code: captured
align/transcribe/ytasr word *counts* are identical both runs (461/326/231),
but a few word timestamps shifted enough to flip one borderline crammed-pace
decision (line 1: align-won 1-word zero-width → no align candidate → interp)
and ripple into its interpolated neighbors. That's the expected cost of
validating live against a fresh GPU run rather than a byte-identical replay —
exactly why the corpus replay below is the control.

**Offline corpus replay (deterministic, snap-free, no envelope)** —
`replay_ytasr_third_source.py <corpus> --alpha 2.0 --beta 2.0`: 15 of the 17
non-SRT songs replayed (Bloodstream and HUNTR_X excluded — see caveat below);
all 15 are **byte-identical** to the post-3a baseline (same MAD, crawl,
overlap, placed, every song). Confirms 3b's supporting refactor (evidence
attached to candidate dicts, `_decode_env` → public `decode_env_db`,
`snap_line_edges`'s new optional `env` param) changed nothing on the path the
harness/veto don't touch — the veto is purely additive.

**Caveat (pre-existing, unrelated to 3b) — `.srt` does not refresh on regen.**
`LyricAlignStage._should_write_srt` (`lyric_align.py:423-425`) skips SRT
generation whenever `subtitles/<stem>.srt` already exists, to avoid clobbering
a real uploader caption. Both songs already had one from the 2026-07-06 run,
so this regen rewrote `karaoke/<stem>.ass` (and the bundle) but silently left
`subtitles/<stem>.srt` untouched — confirmed on disk: Bloodstream's `.srt`
still contains "Callin' out across the line (Brokenhearted)" as a cue at
~227s (the `.ass` does not), and HUNTR_X's `.srt` still contains "(Oh)" (the
`.ass` does not). The `.ass` is what the app actually renders, so the veto's
live behavior is correctly reflected there; the `.srt` sidecar is just stale.
Same mechanism explains the `ground_truth_refs` wrinkle: since `wrote_srt` was
False, the stage re-probed the filesystem, found that same pre-existing SRT,
and — unable to tell "our own prior output" from "an uploader caption" (the
code's own comment at `lyric_align.py:318-322` names this exact ambiguity) —
recorded `youtube_srt_present: True` (`youtube_srt_is_lyric_source` correctly
stayed False; the live log confirms both songs ran the joint DP, not cue).
The replay harness's SRT-sourced filter (`replay_ytasr_third_source.py:339`)
reads that flag and skipped both songs on this run. Not a bug introduced by
3b — a known, by-design tradeoff of one-shot SRT generation, just not one
previously observed on a second live regen of an already-processed song.
Noted for awareness; no fix in scope here.

**Third song — Defying Gravity (a true-negative check — superseded; see
the GATE outcome entry below: the six kept lines are OST-only phantoms).**
Same live-regen
treatment, alone (schema-bump just this one bundle). This song is the
corpus's densest windowed-realign case (89 lines, 6/7 spans replayed, 37
anchors/46 suspects) and the biggest beneficiary of 3a's crammed-candidate
cleanup (overlap 7.8→2.2s), so it was the natural precision check: does the
veto leave real, loud, zero-corroboration lines alone?

`evidence_veto`: `n_zero_evidence=6, n_vetoed=0`. All six sit in the "No One
Mourns the Wicked" reprise crowd-chant (lines 79/81/85-88: *"I hope you're
happy"*, *"Get her!"*, *"Bring me down"*, *"So we've got to bring her"*,
*"Oh"*, *"Down!"*) — overlapping ensemble dialogue that garbles
transcribe/ytasr (hence zero corroboration) but is genuinely loud
(median −15.6 to −12.5 dB, nowhere near the −45 dB floor). Correctly left
alone: zero false-positive vetoes on real sung/shouted material.

Word counts (align/transcribe/ytasr) are again identical before/after
(470/267/233), but this song's before/after line diff is noisier than
Bloodstream/HUNTR_X's — 12 lines shifted (44-48, 82-88), none in the veto's
zero-evidence set. Same root cause as Bloodstream's line 1/59 (whisper
timestamp jitter flipping borderline windowed-realign decisions), amplified
here because this song replays 6 of 7 spans and over half its lines are
"suspect" — more replay surface for a few-millisecond jitter to tip a
decision. Not attributable to 3b's code (the veto touched nothing; the
non-veto diffs are pass-1/windowed-realign candidate selection, unchanged by
this phase). `.srt` staleness applies here too, same mechanism as above.

**Verdict: PASS.** Across all three songs the veto's behavior is exactly as
designed: it caught both real phantoms offered to it (Bloodstream's silent
tail repeat, HUNTR_X's silent ad-lib) and abstained on all six real,
loud, zero-corroboration lines it was also handed (Defying Gravity's crowd
chant) — recall and precision both check out on real audio, not just unit
tests. It moves nothing, and the matcher is provably unperturbed everywhere
the veto doesn't fire. Regen wrote a full-library backup before each run
(`D:\Shared\pikaraoke-songs\regen_backup_20260713T133351Z` and
`regen_backup_20260713T135750Z`; the latter also covers `alignment_debug/`
per Ken's same-day `9b7e5d4`).

GATE: line lists above are for Ken's review before Phase 4 starts.

### Phase 3b GATE outcome — Defying Gravity's kept lines are phantoms, not true negatives (2026-07-13)

Ken reviewed the rendered .ass: every line after 3:30 is Original-Soundtrack
dialogue that is not in this live version ("nothing even remotely like those
lines are sung"). The six zero-evidence lines the veto examined and kept
(79/81/85-88) are exactly those lines. The 3b entry above called them a
true-negative precision check — that framing is wrong: the *audio* is real
and loud (the outro belt riff + crowd; ytasr even hears "bring me down" x3
at 210.5-216.7 s), but the *lyric lines* placed over it are phantoms. The
veto's own behavior is still per spec — the silence floor was never the
instrument for this class — so 3b stands as shipped; the GATE closes with
the class handed to Phase 4.5 (Appendix G).

Full diagnosis (session of 2026-07-13, Fable). Not a single-commit
regression — a structural blind spot newly exposed:

- **May 19 bundle (tiling matcher):** rendered nothing after 205 s —
  tiling required transcribe evidence to place a line at all.
- **Jun 23 bundle (joint, Linux box):** the whole-song aligner dropped the
  last 21 words (449 words vs today's 470, byte-identical whisper config —
  environment/stack difference only), so lines 82-88 had no align range;
  accidental protection. Only 79/81 leaked.
- **Jul 4 onward (current stack):** the aligner times every tail token
  (`n_align_word_drops = 0`); the tail smear enters the DP.

Why every gate passes it: transcribe is silent after 208.8 s, so
`_alpha_weight` keeps the full alpha bonus *by design* (silence keeps align
preference) — each tail align candidate scores an unopposed 2.0 and the
monotonic DP selects the whole chain. The pace gate kills the crammed
82-84 stack at 217.31 (they fall to hidden interp), but 85-88 are
plausibly paced — the aligner latched "me... down" onto the sung riff at
p≈0.84-0.93. The windowed-realign replay re-confirms pass-1 placements
(only *new* placements need transcribe corroboration, per the merge
policy). The energy veto then finds −12.5 to −15.6 dB — real singing,
wrong words — and correctly, per its spec, declines. Phase 6's
transition-cost DP cannot reach this class either: the phantom chain is
gap-free against the real block, and the song is a P2 bail song excluded
from F1's labels by construction.

Side hazard surfaced during diagnosis, out of scope for 4.5 (G7): the
stale pipeline-generated `subtitles/<stem>.srt` (documented in the 3b
entry) is also what `lyrics_fetch._find_srt` discovers — a future *live*
run of this song would adopt the pipeline's own prior output as an
uploader caption and route through cue_align on it, freezing the leaked
tail as cues. Needs its own decision (provenance marker for generated
SRTs, or a sidecar flag); flagged for Ken.
