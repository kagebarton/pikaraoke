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

Default executor is Opus. Fable's extra depth pays off where the work is
design-shaped rather than spec-shaped: contract changes that radiate through
the matcher, and analysis where numbers must be judged, not just produced.

| Section | Model |
| --- | --- |
| Phase 0, Phase 1a | Opus |
| Phase 1b - Phase 2a | Opus from the locked specs (Appendices B/C); Fable on spec failure |
| Phase 2b - Phase 5 | Opus |
| Phase 6 checkpoint | **Fable** |

The design-sensitive content of Phases 1b and 2a was executed by Fable in the
planning session (2026-07-06) and locked as Appendix B (1b implementation
blueprint) and Appendix C (2a pre-registered analysis protocol). Implementing
from those specs is Opus work; the specs themselves are not to be redesigned
by the executor.

Switch points are marked inline with **MODEL BREAK** blocks. At each break,
STOP: do not continue into the next step. Tell Ken the plan calls for a model
switch (`/model`), and wait — the switch is his to make; if he declines,
proceed on the current model and note that in the Results log.

Beyond the marked breaks, recommend an escalation to Fable whenever:

- a GATE's numbers contradict the plan's stated expectations,
- Phase 0's bit-faithful replay check cannot be made to pass quickly, or
- a needed change goes beyond the letter of a spec into scoring/DP semantics
  (`_best_tiling_by_time`, `_alpha_weight` / `_corroboration_weight`).

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

> **MODEL CHECK — 2b through Phase 5 is Opus territory.** If the session is
> currently on Fable (an escalation, or Ken ran 1b there by choice), ask Ken
> to switch back to Opus here. Return to Fable only per the escalation rules
> in "Model switching".

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

Commits: `feat(windowed-realign): ytasr third source in span replays`;
`fix(windowed-realign): protect corroborated pass-1 lines in the merge`.

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

> **MODEL BREAK — ask Ken to switch to Fable for this checkpoint.** Weighing
> the settled corpus numbers against the cost of a new tuning surface — and,
> on a "go", designing the transition-cost shape, the stanza-metadata
> plumbing, and the sweep protocol as a follow-up plan — is design work, not
> execution.

After Phases 1-4 settle the corpus numbers, decide with Ken whether to plan
the bigger refactor as its own experiment: transition costs in
`_best_tiling_by_time` (`joint_match.py:699-743` already iterates all legal
predecessor pairs — a gap/tempo-plausibility penalty `g(cj, ci)` is
structurally a few lines, but a large tuning surface), plus the prerequisite
of preserving stanza breaks and `[Verse]/[Chorus]` headers through
`parse_lyric_lines` (`pikaraoke/lib/genius_lyrics.py:76-104`) as line
metadata. Nothing in this plan builds it; the review's section 6 (Appendix)
is the design sketch.

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
