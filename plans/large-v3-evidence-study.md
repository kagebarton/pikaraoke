# Large-v3 evidence study — are the stubborn non-SRT lines evidence-starved?

Model: Claude Sonnet 5 (executor); Claude Fable 5 (judge)
Branch: `fable_matcher_refine` (hook + drivers + docs all commit here)
Status: Phase 0 executed (Sonnet) — awaiting GATE S0 judge read (Fable)

## Question

On the current refined matcher, does upgrading the local whisper legs
(align + transcribe) from large-v3-turbo to large-v3 materially fix the
residual misplaced/unplaced lines on the evidence-weak non-SRT songs —
or are those residuals structural (lyric-version mismatch,
identical-repeat ambiguity), i.e. gate territory?

## Decision this informs

- Triage policy for the next stubborn line: write a gate (structural)
  vs park on evidence (serialization / bigger GPU).
- Whether jointrefine's "large-v3 = first knob to flip if a bigger GPU
  lands" still holds post-refinement, with a quantified payoff.
- Free side product: a flag-gated fp16-weights load hook, also usable
  to shrink turbo's worker footprint ~1.5 GB at identical output.
  Shipping that for turbo is a separate decision, out of scope here.

## Prior art (executor: read before starting)

- jointrefine `plans/matcher-timing-eval.md`, Phase 2c results
  (2026-06-12): large-v3 fp16 vs turbo on the OLD matcher — gross
  77→60, ≤0.5 s 64.7→72.0%, peak 4605 MiB standalone, 3-4x wall-clock.
  Caution: its biggest per-song wins (Mirrors 22→12, CYFTLT 3→1, More
  Than That) are all SRT/cue-path songs now — expect no carryover
  there; that is exactly why this study scopes to non-SRT.
- fp16 recipe re-verified 2026-07-16 against installed whisper
  20250625 (memory `project_large_v3_fp16_trick.md`). The original
  eval2c implementation was never committed and is lost with /tmp —
  this study commits every driver it writes.
- Full-mix study (fullmix branch) — the adjudication precedent: "more
  evidence" moved plenty of lines but filled only 2/172 true gaps.
  Re-timings of already-placed lines do NOT count as wins.
- 07-16 Linux-box baselines: `plans/matcher-accuracy-hardening.md`
  §"Environment note — Linux-box fresh-corpus harness baselines"
  (commit `afcf7c0`). Those tables are this study's reference point;
  the corpus behind them is an input to three other phases and must
  not be touched.

## The fp16 load recipe (spec for the Phase 0 hook)

Stock `whisper.load_model` builds the module in fp32 and upcasts the
checkpoint into it — large-v3 becomes 6.2 GB and OOMs the 2060 at
load. But `models/large-v3.pt`'s state dict is pure fp16 on disk
(verified 07-16), and whisper's `Linear`/`Conv1d` subclasses cast
weights to the *input's* dtype per call, so fp16-stored weights are
numerically identical under fp16 decoding. The one trap: whisper's
`LayerNorm` upcasts its input to fp32 internally, so halved norm
weights raise a dtype error — norms must be restored to fp32
(~160K params, negligible).

Sequence: `stable_whisper.load_model(path, device='cpu')` →
`model.half()` → every `nn.LayerNorm` module `.float()` →
`model.to('cuda')`. Expected peak ≈ 4.6 GB standalone during align.

Hook placement: the load site in
`pikaraoke/pipeline/workers/whisper_worker.py` (~line 667), gated by a
new `LoadModelKwargs` field (`fp16_weights: bool = False`; default off
= today's behavior byte-for-byte). Smallest possible upstream change
per CLAUDE.md fork rules. The field must survive the worker's
config-dict round-trip (`_rebuild_config`, whisper_worker.py ~line
106-114) — the worker is a spawn (not fork) subprocess, so a
driver-side monkeypatch will NOT reach it; the flag must ride the
config.

## Scope — 8 songs, non-SRT path only

Baseline rows from the `afcf7c0` composite table
(`crawl`/`overlap` are rec>new; coverage `!` = notably short):

| song | why in scope | baseline |
| --- | --- | --- |
| Defying Gravity (Wicked 20th Anniv) | bail:wide_spread | crawl 4→3, 51/89! (also a known LRCLIB-flake song) |
| Popular (Wicked 20th Anniv) | bail:wide_spread | crawl 3→3, 52/62! |
| Ed Sheeran - Best Part Of Me | bail:wide_spread | 37/38 |
| HUNTR/X - This Is What It Sounds Like | bail:wide_spread (2src) | 33/53! |
| Mulan - I'll Make a Man Out of You | bail:wide_spread | 36/47! |
| Ed Sheeran & Rudimental - Bloodstream | worst overlap | overlap 6.7, 48/74! |
| Seasons of Love | worst crawl | crawl 8→3, 25/34! (LRCLIB-flake song) |
| The Next Ten Minutes | carryover probe (old A/B 5→1 gross) | crawl 5→2, 67/71 |

The five bail songs are the core hypothesis: their ytasr third source
bailed, so they run on the local align+transcribe legs alone — exactly
the two legs large-v3 upgrades, on exactly the songs with the weakest
evidence.

**Out of scope:** the SRT/cue path (16/16 clean at baseline; the cue
scaffold dominates placement there), the other healthy non-SRT songs,
production promotion, the turbo-fp16 ship decision, porting
jointrefine's reference-scored eval (flag counts + per-line
adjudication suffice here).

## Method

### Phase 0 — hook + loader validation → GATE S0

1. Salvage previous-session artifacts into the study records dir
   before anything else (/tmp is volatile):
   `/tmp/claude-1000/-home-ken-pikaraoke/1ec24196-19d8-4966-b5f6-80fedb599b81/scratchpad/`
   → `run_regen_all.py` (the proven all-33 regen driver pattern),
   `ytasr_baseline_composite.txt`, `ytasr_baseline_linux*.txt`.
   (Fable already copied these to
   `/home/ken/pikaraoke-study-l3v/salvage/` on 07-16 as insurance —
   verify they are there; re-salvage from the session scratchpad only
   if not.)
2. Implement the fp16 hook per the recipe spec above: new
   `LoadModelKwargs.fp16_weights` field + flag-gated branch at the
   worker load site. Compile-smoke, run the existing whisper-worker
   tests. Commit. **Checkpoint: this commit adds logic to a production
   file — flag it to Ken as /code-review-qualifying per house policy
   (never auto-launch).**
3. Identity check (the recipe's correctness gate, run before burning
   GPU time on large-v3): one short in-scope song (Seasons of Love),
   align + transcribe legs, turbo-fp32 vs turbo-fp16 (same checkpoint,
   halved via the hook). Pass = identical word *sequences* on both
   legs; word timing deltas ≤ 0.02 s for ≥99% of words (the embedding
   add rounds once differently — bit-exactness is not required).
   Record VRAM peak both ways (expect ~1.6 GB saved).
4. large-v3 fp16 smoke: load + one align pass on the same song, no
   OOM, record peak (expect ≈ 4.6 GB) and wall-clock.

**GATE S0 (Fable, hard stop):** review the hook diff + identity-check
artifacts. Any structural divergence in the identity check =
investigate before Phase 1, do not proceed on a "close enough" call.

### Phase 1 — study copy + large-v3 regen

1. Copy the 8 song folders from `/home/ken/pikaraoke-songs` →
   `/home/ken/pikaraoke-study-l3v/songs/` (everything: stems/vocal,
   dereverb if present, subtitles, lyrics, karaoke, `.asr.json3`,
   `alignment_debug`). Verify the copy (folder count + bundle
   presence) before running anything against it.
2. Study driver (committed, `scripts/` — pattern from the salvaged
   `run_regen_all.py`, which mirrors `regen_alignment_bundles.main()`
   in-process): run the regen machinery against the **copy**,
   `reset=False`; assert all 8 resolve to `plan.kind == "seed"` and
   abort otherwise (no network, no Genius prompt); config:
   `load_model.model_path = models/large-v3.pt`,
   `fp16_weights = True`. Keep the `__main__` guard — the workers
   spawn subprocesses that re-import the driver (bit the regen driver
   once already).
3. Record per-song wall-clock + peak VRAM (`nvidia-smi` poll or
   `torch.cuda.max_memory_allocated` from the worker log). Confirm all
   8 variant bundles carry the current `SCHEMA_VERSION`.
4. Evidence-density table: per song, align-word and transcribe-word
   counts, baseline bundle vs variant bundle. If the starved songs
   show no density gain, the causal premise is already in trouble —
   record that observation and continue (the replay still settles it).

### Phase 2 — replay + flag-table diff → GATE S1

1. `replay_ytasr_third_source.py /home/ken/pikaraoke-study-l3v/songs
   --alpha 2.0 --beta 2.0`, run 3 times — same methodology as the
   baseline: matcher-computed columns must be identical across runs;
   best-of-3 composite for live-fetch MAD (Defying Gravity and Seasons
   of Love are known LRCLIB-timeout flake songs on this box).
2. Produce the variant composite table and a side-by-side per-song
   diff against the 8 baseline rows (crawl, overlap, placed, coverage,
   src/bail status, MAD/anchors).

**GATE S1 (Fable, hard stop):** re-derive the diff programmatically
from the raw run outputs — not from the executor's summary — and check
the flake handling ("verified programmatically, not by eye").

### Phase 3 — per-line adjudication (Fable) + verdict

1. Executor produces a movers artifact per song: lines newly placed,
   lines newly unplaced, and lines with |Δstart| > 0.5 s — each with
   its evidence (anchor words per source, whether the song's held-out
   LRCLIB reference has a timing for that line, before/after
   placements).
2. Fable adjudicates **every** mover: true fix / re-timing /
   regression / ambiguous (full-mix discipline). Held-out LRCLIB line
   deltas where available; anchor density, monotonicity, and flag
   context otherwise. Executor claims are input, not evidence.
3. Verdict against the pre-registered criteria below, recorded in this
   plan.

### Phase 4 — wrap-up

Verdict + consequences written into this plan; memory updated; study
copy deleted (or kept — Ken's call); the turbo-fp16 ship question
handed to Ken as a separate item. The hook stays committed either way
(flag default off, zero production effect).

## Pre-registered verdict criteria

**GO ("the evidence-starved class is real")** = at least one of:

- ≥2 of the 5 bail songs each gain ≥3 adjudicated true-fix lines
  (newly placed sung lines, or misplaced lines moved to a
  reference-corroborated position), or
- any bail→recovered flip with a clean recovered MAD (≤0.6 s), or
- Bloodstream's 6.7 s max overlap collapses below 2.0 s via
  adjudicated true fixes (not hides/re-timings).

**NO** = none of the above; or movers >70% re-timings (the full-mix
pattern); or net-negative adjudication (regressions) in ≥2 songs.

Either verdict ships nothing to production. GO's consequence is a
triage-policy line — *check evidence starvation before writing the
next gate* — plus a quantified payoff number for the worker
serialization / bigger-GPU decision. NO re-parks large-v3 permanently
on this hardware and validates gate-first triage. The Next Ten Minutes
probe is reported either way (did the old A/B's non-SRT win survive
the refined matcher?) but does not by itself decide the verdict.

## Budget

Phase 1 ≈ 25-40 min GPU (8 songs × ~2.5-4 min under large-v3; stems
reused so whisper is the only GPU tenant; GPU must be otherwise idle —
no playback, no stem jobs). Phase 0 smoke ≈ 10 min GPU. Everything
else is CPU-cheap. Executor total ≈ 2-3 h including artifacts.

## Executor discipline (Sonnet)

- Conda env pik: `/home/ken/miniconda3/envs/pik/bin/python`. Never uv.
- **Hard rule:** regen never points at `/home/ken/pikaraoke-songs`.
  Double-check the folder argument before every run-phase invocation.
  The regen machinery backs up text folders, but the backup is not the
  safety net — the folder argument is.
- Commit every driver and study script (the eval2c lesson: /tmp
  drivers are how the last implementation was lost). Raw logs and
  tables go to the study records dir and are referenced from this
  plan; key result tables get pasted into this plan verbatim.
- No production edits beyond the Phase 0 hook. Bugs found elsewhere
  during the study: report in this plan, do not fix inline.
- Stop at every GATE. Fable writes the judge-read into this plan
  before the next phase starts.
- Plan updates land as `docs(plan)` commits on `fable_matcher_refine`;
  pre-commit excludes `plans/`.

## Results log

### Phase 0 — hook + loader validation artifacts (Sonnet, 2026-07-16)

Executor stops at artifacts per this study's Sonnet-executes/Fable-judges
split; the GATE S0 verdict belongs to Fable's judge read below, not
asserted here.

**Hook commit:** `72b71ec` — `pikaraoke/pipeline/config.py`
(`LoadModelKwargs.fp16_weights: bool = False`, default off) +
`pikaraoke/pipeline/workers/whisper_worker.py` (new
`_load_whisper_model()` helper, called from the model-load site inside
`_whisper_worker_main_inner`). Config round-trip verified by hand
(`_rebuild_config` reconstructs `fp16_weights` correctly for both
`True` and `False`). Pre-commit clean. Existing tests pass unmodified:
27/27 `test_whisper_worker.py` + 17/17 `test_pipeline_config.py`
(44/44 combined).

**Driver commit:** `0d630d6` — `scripts/fp16_identity_check.py`. Runs
turbo-fp32 vs turbo-fp16 through the real `WhisperWorker` subprocess
path (`align_refine()` then `transcribe_words(refine=False)`, matching
`LyricAlignStage`'s production call shape), gated before a large-v3
fp16 smoke pass — the script aborts before touching large-v3 if the
identity check fails. VRAM measured via external `nvidia-smi` polling
(a background thread in the parent process): the model actually loads
inside the worker's spawned subprocess, invisible to in-process
`torch.cuda` stats in the caller.

**Environment:** Linux conda box (`pik` env), GPU confirmed idle
(6 MiB / 0% util, zero compute processes, no pikaraoke process running)
immediately before the run. Song: Seasons of Love (34 lyric lines,
`align_lines` reconstructed from the existing
`alignment_debug/<stem>.json` bundle's `lyrics.align_lines` —
read-only, no write into `/home/ken/pikaraoke-songs`). Vocal stem:
`vocal/Seasons of Love (HD)---UvyHuse6buY---vocal.m4a`.

**Invocation:**
`/home/ken/miniconda3/envs/pik/bin/python scripts/fp16_identity_check.py --out /home/ken/pikaraoke-study-l3v/records/phase0/identity_check_results.json`

**Artifacts saved** (outside git, in the study records dir):
- `/home/ken/pikaraoke-study-l3v/records/phase0/identity_check_console.log`
  — raw stdout/stderr, byte-for-byte.
- `/home/ken/pikaraoke-study-l3v/records/phase0/identity_check_results.json`
  — full structured output, including every word's `{word, start, end,
  probability}` for both dtypes, both legs.

**Step 3 — identity check (turbo fp32 vs turbo fp16):**

| leg | words | sequences_match | start/end diffs | max Δstart/end | probability diffs | max Δprobability | pct within 0.02s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| align | 151/151 | True | 0/151 | 0.0s | 16/151 | 0.0002 | 100.0% |
| transcribe | 175/175 | True | 0/175 | 0.0s | 0/175 | 0.0000 | 100.0% |

VRAM: fp32 peak 3637 MiB, fp16 peak 2097 MiB, saved 1540 MiB (plan
predicted ~1.6 GB, memory `project_large_v3_fp16_trick.md`). Load time:
fp32 8.03s, fp16 12.03s (the CPU round-trip + halving is one-time
overhead per worker start).

Mechanical fact for the judge, not a verdict: every align/transcribe
word's start and end timestamp is bit-identical between the two dtypes
(0/326 timing diffs total) — stronger than the plan's own tolerance
(≤0.02s for ≥99% of words). The `probability` field (not part of the
pass criterion) shows 16/151 tiny divergences on the align leg (max
0.0002) and 0/175 on transcribe — evidence the fp16 branch executed
genuinely distinct numerics on the align leg (i.e. not a silent fp32
fallback) while still landing on identical DTW/argmax timestamp
decisions for this song.

**Open item for the judge:** the transcribe leg shows zero probability
divergence at all (vs. align's 16/151) — asymmetric, and not
independently explained here. Plausibly VAD/mel feature extraction
sitting outside the half-precision path, or this song's transcribe
decode trajectory not crossing a numeric boundary either dtype
touches. Recorded as a fact, not chased further; flagging in case it
matters for how much this single-song identity check generalizes to
the 8-song Phase 1 corpus.

**Step 4 — large-v3 fp16 smoke (load + one align pass; only run because
step 3 passed both legs):**

Loaded in 24.44s, total pass 69.5s, peak VRAM 4557 MiB (plan predicted
≈4605 MiB standalone), 149 align words (vs. turbo's 151 — different
model, not compared word-for-word; this step is a load/OOM smoke test
only). No `error`/`OOM` result from the worker subprocess.

### Phase 0 — judge read (Fable, pending)

_Awaiting GATE S0 review._
