# Replace walk/tile with the joint matcher (as built)

Model: Claude Opus 4.8

Record of how the alignment subsystem developed on `jointrefine` was ported onto the
product line as a clean, joint-only history. Walk and tiling never appear; the eval/probe
scaffolding and `plans/` are dropped. `jointrefine` stays the full dev archive.

## Outcome

The work landed on **`master`** (not `next` — that decision changed late). `master`
fast-forwarded from the upstream fork point `e7bc348a` to the rewritten tip and is 60
commits ahead of `origin/master`. Verified: production tree identical to the jointrefine
oracle except one intentional refactor (below), **1204 tests pass**, pre-commit clean.

## Topology

```
master (e7bc348a, upstream fork point)
  └─ … pipeline scaffolding, Genius lyrics …
     e23a9e9d  feat(lyrics): Genius search          ← rebuild base
     ┌ f2c7fd78  walk matcher        ┐
     │ 69ad8d97  tiling matcher      │  4-commit matcher SLICE → REPLACED (never appears)
     │ 9fc40783  lyric-align stage   │
     └ 8db0ebc5  joint (opt-in)      ┘
     046eec44  stage orchestrator    ┐
     … processing UI / overlays …    │  alignment-independent → REPLAYED as-is
     120256b4 / ad082c17  config     ┘  ← origin/next tip
        └─ [jointrefine dev arc] → CURATED into 6 commits
           jointrefine tip = consistent FINAL state  ← ORACLE for all content
```

The oracle was jointrefine's tip at build time (`d3db2271`; re-SHA'd to `26826fc` when this
doc was later relocated off the matcher-refactor commit). Its tree, minus dropped
scaffolding, is the exact target for the rewritten alignment block.

## What changed from the original plan

The first plan was **faithful per-feature curation** (each feature its own commit carrying
its stage wiring). That proved mechanically infeasible and was abandoned mid-build:

1. **Entangled refactors.** The walk/tile-removal refactors (`make joint the only path`,
   `collapse align_check+refine`) land *after* the features in jointrefine and rewrite the
   same `lyric_align.py`/`config.py` regions. There is no clean "joint-only, no features"
   baseline to peel back to — reverse-applying features collided every time.
2. **Import direction.** Final `lyric_align.py` imports the feature modules, so a
   "feature adds its own wiring" commit needs a baseline stage that never existed.

Settled approach: **modules split, wiring in the stage** — standalone algorithmic modules
get their own commits; the stage commit carries all integration. Low risk (snapshots from
the oracle), walk/tile never appear.

## Final commit structure (on `master`)

```
… e23a9e9d (unchanged base) …
f2d4b41  feat(lyrics): add joint alignment DP matcher          (joint/candidate/token + tests)
1b62f63  feat(lyrics): add windowed re-align second pass        (windowed_realign + test)
3dfa976  feat(lyrics): add SRT + LRCLIB timing priors           (srt_prior + lrclib + tests)
425e4c9  feat(pipeline): joint lyric-align stage + whisper/stem workers
d14052c  refactor: wire de-reverb stem worker into the pipeline; drop matcher selector
d164751  docs: scrub references to dropped plan docs
… replay of 046eec44..origin/next (orchestrator, UI, processing, config) …
```

De-reverb has no standalone module, so it lives in the stage commit. The two `feat(config)`
commits at `origin/next`'s tip ride along in the replay (not alignment work).

## The eval-coupling extraction (the one intentional divergence)

Dropping the eval harness was blocked: production `lrclib.py` imported three LRC helpers —
`parse_lrc_lines`, `cue_spans_from_lrc`, `map_lines_to_cues` (plus `normalize_line`) — that
lived in `alignment_eval.py`. `lrclib` was their only production consumer. Resolution:
**extracted the ~62-line cluster into `lrclib.py`**, migrated its tests from
`test_alignment_eval.py` into `test_lrclib.py`, and dropped `alignment_eval.py` whole. This
is why the oracle-diff shows `lrclib.py` + `test_lrclib.py` changed — everything else
differing is dropped scaffolding.

## Mechanism (as executed)

1. **Safety:** `next-backup` = `origin/next`; `jointrefine` left intact.
2. **Rebuild base:** branch at `e23a9e9d`; build the 6 commits above by
   `git restore --source=<oracle> -- <paths>` per group, smoke-testing imports + tests at
   each step. The LRC extraction was a hand edit on top of the `lrclib` snapshot.
3. **Replay:** `git rebase --onto <C4> 8db0ebc5 origin/next` replayed orchestrator → tip.
   One modify/delete conflict (a style commit had reformatted `test_tiling_match.py`, which
   no longer exists) — resolved by `git rm`.
4. **Post-replay touch-ups:** `processing_manager.py`/`pipeline_tracker.py` and the backfill
   script/README (files created in the replay) got their alignment edits in commit C5.
5. **Gate:** `git diff --stat <tip> <oracle>` must show only dropped scaffolding + the
   `lrclib`/`test_lrclib` extraction. Then full pytest + pre-commit.
6. **Land:** `git branch -f master <tip>` (fast-forward from `e7bc348a`). Not pushed.

## Curation map — disposition of every source commit

### The 4-commit slice — REPLACED, never appears
| commit | subject | disposition |
|---|---|---|
| f2c7fd78 | walk matcher | gone (`word_alignment.py` never created) |
| 69ad8d97 | tiling matcher | gone (`tiling_match.py` never created) |
| 9fc40783 | lyric-fetch + lyric-align stages | → stage commit (final form) |
| 8db0ebc5 | joint DP matcher (opt-in) | → matcher + stage commits |

### The jointrefine dev arc
| commit | subject | disposition |
|---|---|---|
| 8cad50a4 | joint: edit gate → 0.75 | absorbed → matcher (final form) |
| 12bfda21 | matcher: ASCII-fold | absorbed → matcher (lives in `token_align.py`) |
| b9d8f789 | joint: windowed re-align | → windowed commit |
| 86fc3d9b / a0b16405 | worker cancel/GPU fixes | absorbed → stage commit (final workers) |
| ce7d7bc8 | pipeline: de-reverb retry | → stage commit |
| c3b5ee1e | joint: SRT timing prior | → priors commit |
| c7bd17af (+ snap) | joint: LRCLIB timing prior | → priors commit (LRC helpers extracted) |
| dfe97718 | default to joint + refine steps | absorbed → stage commit (config) |
| make-joint-only / dissolve-tile / strip-walk / scrub / collapse-worker | refactors | absorbed (born final) |
| 96c32273 | lyrics_fetch: log resolved source | absorbed → stage commit |
| 0872bb34 | chore: demote whisper warnings | absorbed → stage commit |
| eval: harness/probes/measurements (3604990d, 89010a7d, e60bfb0f, cbe57d46, d8ebdca4, d3827a32, ad541fad) | — | **dropped** (LRC helpers extracted into `lrclib` first) |
| plan: docs(plan) commits (29f43e75, 8cce6661, 72ae59ee, 1c221254) | — | **dropped** |

## Branch outcome
- `master` — product line (the 6 commits + replay), on the upstream fork point. Not pushed.
- `next-backup` — rollback to pre-rewrite `origin/next`.
- `jointrefine` — dev archive (this doc lives here as the porting record).
- Deleted: `next`, `next-rewrite`, `next-joint` (superseded / build artifacts).

Note: `master` now diverges hard from upstream `origin/master`, superseding the old
"never commit to master / fork-maintenance" guidance in `CLAUDE.md`.
