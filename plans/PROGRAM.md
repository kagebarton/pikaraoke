Model: Claude Fable 5 (design, locked 2026-07-18); judge Opus; executor Sonnet 5

# Timing-route program — the map

Entry point for the whole timing-source routing effort. This file owns the
routing picture, the sequencing, and the shared ground rules. **It owns no
probes and no verdicts** — those live in the lane files, one per timing
source.

## The two pictures, and why they differ

The single most useful thing to hold in your head: **the ladder below is
the target, not the code.** The shipped matcher has *two* routes; the
ladder has three rungs. Confusing the two is the main way these plans
mislead.

### What ships today

`LyricAlignStage.run` (`pikaraoke/pipeline/stages/lyric_align.py`):

```
                    ┌─ lyrics_path is None ──────────────► TRANSCRIBE mode
                    │                                      (no sheet at all;
                    │                                       whisper writes the
                    │                                       lines it hears)
   song ────────────┤
                    │                    ┌─ cue_spans ────► CUE-ALIGN  (SRT)
                    └─ sheet exists ─────┤   non-empty      route-srt.md
                                         │
                                         └─ else ─────────► JOINT DP
                                                            route-no-timing.md
```

That is the entire routing decision: one `if cue_spans:` at
`lyric_align.py:145`. A song with LRCLIB line timing but no SRT takes the
**joint DP branch** — LRCLIB enters only as a gated post-pass *fill*
(`lrclib_fill.plan_fills`, applied at `lyric_align.py:257`), never as a
routing tier.

### What the ladder targets

| Rung | Source | Route | State |
| --- | --- | --- | --- |
| 1 | word timing (Musixmatch richsync) | verify, then render the provider's own words | **NO-GO as it stands** — `route-word-timing.md` |
| 2a | uploader SRT | cue-align, cues trusted as-is | **shipped** — `route-srt.md` |
| 2b | line timing (LRCLIB / MXM-line / NetEase) | same driver, cues **warped** first | **licensed, unbuilt (F2)** — `route-line-timing.md` |
| 3 | nothing usable | joint DP on the Genius sheet | **shipped**, being refit — `route-no-timing.md` |

The gap between the pictures is exactly rung 2b. Until F2 is built, rung
2b's population sits in rung 3.

## Demotion gates — what actually rejects a fuzzy source

Two different things in these plans are called a "gate", and mixing them
up costs hours:

- **GATE C / O / R / S / P / L** — decision points in *this program*. Ken
  rules on them. They fire once, in a session, and get written into a
  Results log.
- **The thresholds below** — *runtime* code, firing per song, deciding
  whether a source is trusted, demoted, or dropped.

| Threshold | Module | Value | What it rejects |
| --- | --- | --- | --- |
| `is_generated` | `srt_provenance` | marker file | The pipeline's own earlier SRT, so it can't be re-adopted as an uploader caption |
| `cue_spans` empty? | `lyric_align._load_lyrics` | — | **The route fork itself** — SRT vs joint |
| `WORD_SEG_MIN_FRAC` | `ytasr` | 0.5 | Line-level/manual captions posing as word-level ASR |
| `MIN_CAPTION_WPM` | `ytasr` | 15.0 | `[Music]` degeneracy. Unknown duration → reject outright |
| `CANDIDATE_MAX_EDIT_RATIO` | `ytasr` | 0.34 | A per-line ASR candidate too garbled to admit |
| **`WRONG_SONG_MAP_RATE`** | **`timing_fetch`** | **0.5** | **The wrong-song floor for Musixmatch/NetEase sidecars** |
| `_MAP_MIN_RATIO` | `lrclib` | 0.85 | A per-line text mapping too weak to use |
| `FILL_MAX_SLOPE_DEV` | `lrclib_fill` | 0.01 | Song not fill-eligible unless its Theil-Sen slope is within 1% of unity |
| `WARP_MIN_ANCHORS` / `WARP_MAD_GATE_S` | `lrclib_fill`, `cue_align` | 5 / 2.0 s | A slope estimate with too few anchors or too much residual |
| `COLLISION_TOL_S` | `lrclib_fill` | 0.2 | A fill landing on top of an already-placed line |
| `MIN_REF_DB` | `evidence_veto` ← `onset_snap` | −45.0 dB | A line placed in silence |

**The one under active repair is `WRONG_SONG_MAP_RATE`.** It is a *text*
map-rate standing in for a *timing* judgment, and GATE R proved it
mislabels in both directions: Selfish's sidecar scored 0.38 — below the
floor — but was the right song, correctly timed (the low score was an
SRT-segmentation artifact), while 5 of 14 sidecars that passed the floor
time a different recording or edit. M1 and M2 exist to replace it with
labels derived from timing truth.

## Which file owns what

| File | Owns |
| --- | --- |
| `PROGRAM.md` | this map, sequencing, ground rules, model switching |
| `GLOSSARY.md` | ASS/CTC/MMS_FA/emission/melisma/richsync — read before guessing at an acronym |
| `route-word-timing.md` | rung 1; GATE R, R-1 ruling, M1-M5 |
| `route-srt.md` | rung 2a; the shipped cue-align route, S-C |
| `route-line-timing.md` | rung 2b; GATE S scaffold arms, GATE L, S-E, M6 |
| `route-no-timing.md` | rung 3; the joint catch-all refit, GATE P/J1/J2 |
| `shared-aligner-form.md` | GATE C, GATE O, Phase 0 harness, ruling-provenance audit |
| `ctc-sync-engine.md` | build phases + locked appendices; each licensed by a GATE above |
| `completed/` | closed plans, kept for their Results logs |

Rule of thumb: **a probe belongs to a lane if its outcome changes what
happens for one timing source only.** If it changes the aligner or the
architecture for every source, it is cross-cutting and belongs in
`shared-aligner-form.md`.

## Branch lineage

`master` (upstream) → `fable_matcher_refine` (= `musix_ctc`) →
`timing_pillars` → **`joint_catchall_refit`** (current). `pathed_align`
holds the pre-port scaffold-warp history; its machinery is now ported into
shipped `cue_align.py`, so it is not dead-end history.

## Remaining execution order (Ken, 2026-09-01) — measure first, lock once

Ken's sequencing ruling: run the remaining measurement program to
completion, then consolidate the build design once, rather than amending
locked appendices as results trickle in. The dependency check that
licenses this: **no remaining probe needs production code.** Only the
V-gates (the build plan's V1/V2, the joint plan's V) are validation *of*
shipped code, which is tautological.

Order — cheapest and highest overturn-risk first:

1. ~~**Joint plan Phase 4 → GATE P**~~ — **CLOSED 2026-09-01, NO-GO.**
   The gap and inversion mass is repeat cross-attraction plus
   lyric-version drift, not sheet permutation, so the monotonic DP
   stands and no section-level DP is commissioned. The redesign risk
   this step existed to price is retired.
2. ~~**Phase 2b → GATE R**~~ — **run 2026-09-03; R-1 ruled the same
   day.** R-1 NO-GO as the route stands, mechanism GO on evidence. R-2
   and R-3 settled (provider text as-is; SRT-first). **R-4 remains
   open** — STOP → Ken. R-5 no award. Detail in
   `plans/route-word-timing.md`.
3. **M1-M5** — the R-4 re-specification, commissioned with the R-1
   ruling. All offline, no GPU, data already on disk. M1 relabel by
   timing truth; M2 build real negative controls by cross-pairing;
   M3 re-run Appendix C on M1 labels + M2 controls; M4 per-section
   pairing-coverage detector; M5 check whether rushed sweeps are
   `cue_align.MAX_WORD_DUR_S` truncating sustained notes.
4. **M6** — re-read S-2's genius arm against the S-C reframe. Added
   2026-09-04 by the eyeball-provenance audit. **Sequenced after M1-M3
   and before any F2 build**, since F2 builds on the path S-2 chose the
   aligner for. See `plans/route-line-timing.md`.
5. **Joint plan Phase 2a → GATE J1/J2** (GPU, scratchpad). J2 feeds
   Appendix D's snap policy, which currently records "re-enable
   exception: none".
6. **S-E** (Phase 3's unrun optional arm; offline, no GPU align). Cheap
   add-on: informs the deletion inventory and tests Ken's GATE C
   observation.
7. **Phase 4 → GATE L** — whenever the Mandarin corpus exists. Blocks
   nothing and nothing blocks it but the corpus.

Then **one design-consolidation pass**: re-lock the build plan's
Appendices C, D and E with the real constants in a single revision.

**Carve-out — F2 is a zero-regret build at any point in this sequence,
with one caveat added 2026-09-04.** Checked against every pending
outcome: an R-1 NO-GO only sends more songs into F2's line-source pool
(Appendix A already specifies that demotion); GATE P and GATE J1 are
rung-3 questions; GATE L is an additive per-line romanizer inside F2's
aligner. The single coupling was GATE J2 possibly flipping snap policy on
CTC-timed routes — a post-pass wiring flag, not a redesign. **The caveat:
M6 now gates F2**, because F2 builds on the aligner S-2's genius arm
selected and that selection is under re-read. The argument for pulling F2
forward otherwise stands: rung 2b has zero production miles, so every
number on it comes from harnesses.

## Decisions already made by Ken (2026-07-18 session — do not re-litigate)

- **SRT vs richsync when both exist:** decided at the Phase 2 GATE R with
  the A/B renders in hand — not pre-decided here.
- **Tier-1 display text:** the provider's own text renders. The Genius/SRT
  sheet is used only for candidate selection (map_rate) and verification.
- **NetEase:** wired in, exactly as the probe ran it — fallback only when
  Musixmatch comes up empty or at 0.0, line-level only, scaffold tier only.
- **Search scope:** derived-query changes only. No UI changes; no
  production timing fetch for songs without a Genius pick (srt/raw-origin
  songs keep today's routes). If GATE R rules richsync-first for SRT+word
  songs, that ruling is **recorded as follow-on scope**, not implemented
  in this plan.
- **Evidence/build split** (this revision): probes and verdicts here;
  production implementation in `plans/ctc-sync-engine.md`, built as a
  replacement path beside the existing matcher with a gated cutover,
  not as in-place modification.


## Ground rules

- Branch: new branch off `musix_ctc` (current tip `22c15e42`), e.g.
  `timing_pillars`. Never commit to `master`. The untracked/modified
  `plans/*.md` files in the working tree are Ken's; never mix them into
  this plan's commits.
- Environment: conda `pik`. Tests
  `/home/ken/miniconda3/envs/pik/bin/python -m pytest`; pre-commit
  `pre-commit run --config code_quality/.pre-commit-config.yaml --files
  <changed files>` (scope to `--files`; `--all-files` drags in `plans/`).
- One feature per commit; tests ride with the code they exercise;
  import-smoke + read `git diff --cached` before committing. Self-review
  every diff on the CLAUDE.md axes. Batch /code-review-qualifying commits
  and alert Ken at clean checkpoints — never self-launch. Flag phase
  boundaries as good /compact points.
- Fork rule: new behavior in new files; smallest possible touches to
  existing modules.
- Probes and measurement scripts: scratchpad only, never committed — with
  two named exceptions: `scripts/musixmatch_coverage_improve.py` (already
  in-repo per Ken; Phase 2a extends it) and the Phase 0 harness port
  (measurement infrastructure, committed like the matcher plan's Phase 0).
  Result tables paste into this file under `## Results log`.
- Corpus: the 33 bundles in `pikaraoke-songs/alignment_debug/`. The
  coverage table in `plans/completed/musixmatch-coverage-improvement.md` §Results is
  the routing ground truth for which song lands in which tier.
- Musixmatch politeness (relearn nothing): one shared provider instance,
  `CALL_SLEEP_S=2.5` / `SONG_SLEEP_S=4.0`, single 20s-backoff retry on
  401 with token-file clear, never per-call token refresh. NetEase: plain
  try/except + same pacing.
- GATE markers are hard stops: executor reports numbers, Judge reads,
  Ken rules. No proceeding past a GATE on executor judgment.


## Model switching

Same three roles as `plans/completed/matcher-accuracy-hardening.md` §"Model
switching", binding here identically:

- **Design** — Fable, completed 2026-07-18 (**Fable unavailable from
  2026-07-19 — succession locked**): this document and the build
  plan's Appendices A–E are locked, with every formerly
  lock-at-GATE item converted to a pre-registered decision procedure.
  At each GATE the judge *executes* the relevant procedure verbatim
  and records the resulting constants; no model on any tier invents a
  threshold or extends a procedure — an uncovered case is a STOP →
  Ken.
- **Implement / prototype / run** — Sonnet 5. Output at a GATE is a
  table, never a verdict.
- **Judge results** — Opus, executing the pre-registered read-off
  rules below; escalations that previously said "to Fable" go to Ken.

Executor discipline: the matcher plan's §"Executor discipline (Sonnet 5,
added 2026-07-12)" applies verbatim — specs are contracts, mismatches are
STOPs, numbers come from commands actually run, thresholds never move
after data.

| Phase | Design | Implement/run | Judge |
| --- | --- | --- | --- |
| 0 (port + baselines) | locked below | Sonnet 5 | — (infrastructure) |
| 1 (CTC probe, GATE C) | `plans/completed/ctc-forced-align-eyeball.md` | executed 2026-07-18 | done — see Results log |
| 1b (score oracle, GATE O) | locked below | Sonnet 5 | Opus + Ken |
| 2 (richsync probe, GATE R) | 2a/2b below; Appendix C locks at the GATE | Sonnet 5 | Opus + Ken eyeball |
| 3 (scaffold probe, GATE S) | below; Appendices D/E lock at the GATE | Sonnet 5 | Opus; escalate if arms conflict |
| 4 (non-Latin form, GATE L) | below; Appendix D's carve-out amends at L-3 | Sonnet 5 | Opus + Ken eyeball |

Phase dependencies: 1b, 2, 3 can interleave; 1b should complete before
2b (its scores feed 2b's verification stats) and before 3's S-B2 arm.
Phase 4 (GATE L) depends on nothing but its own Mandarin corpus (Ken's
action) and blocks nothing; "Remaining execution order" below sequences
it against the joint plan's probes.
Build phases in `plans/ctc-sync-engine.md` consume these GATEs per its
licensing table; its E0 (fetch pillar) is architecture-neutral and may
start immediately — the sidecar format both it and Phase 2a share is
locked in that file's Appendix B (if E0 lands first, 2a's script
imports the lib instead of carrying its own writer).


## Explicitly out of scope / rejected (for this file's probes)

- UI changes to the Genius search flow; production timing fetch for
  songs without a Genius pick (both per Ken's scope ruling).
- Joint-matcher production changes (S-E only measures a stream swap in
  the offline replay harness). The NO-GO on transition-cost DP (matcher
  plan Phase 6) stands. Any joint-matcher retirement happens in the
  build plan's gated cutover phase, never here.
- NetEase as a word-level source (library returns line-only; recheck
  only on a `syncedlyrics` upgrade) and any provider beyond
  Musixmatch/NetEase/LRCLIB.
- LRCLIB held-out scoring for scaffold-routed songs (circular — see
  Phase 3). **Reconciliation:** the matcher plan's "no new online timing
  sources" constraint was that plan's scope, and its "LRCLIB permanently
  out of production" rejection was already narrowed by the E1 fill;
  this effort, Ken-directed, supersedes both for the timing routes. The
  E1 fill's survival is a build-plan (Appendix A / cutover) decision.
- Transcription-mode (no-lyrics) songs: untouched throughout.
