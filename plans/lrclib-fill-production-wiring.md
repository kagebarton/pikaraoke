# LRCLIB gated fill — production wiring (E1)

Model: Claude Sonnet (implementer). Design: Claude Fable 5, 2026-07-17.

Implements the E1 = GO verdict of `plans/lrclib-fill-absence-study.md`
(Phase L4 consolidated verdict, 2026-07-17). This is the "separate
production-wiring plan" that study's Phase L4 mandates. The study file is
the authoritative record for every number cited here; do not re-run or
re-derive study phases.

## What the GO licenses (and nothing more)

A song processed on the **joint route** (txt/genius lyrics) may have its
**matcher-unplaced lines** filled at LRCLIB-cue-plus-offset times, iff every
gate below passes. Adjudicated evidence: 16 good / 0 bad surviving fills
across the 17-song corpus (GATE L2 eyeball + re-run by derivation,
lid-for-lid match).

Out of scope — do not implement any of these:

- **E2 / absence-evidence demotion** — descoped by Ken pre-execution.
- **LRCLIB as a matcher/DP candidate source or snap prior** — still banned
  (see `matcher-accuracy-hardening.md` "Explicitly rejected"). Fill-only:
  a placed line is never moved or removed by this feature.
- **Arm-B warped placement** (Theil-Sen-warped fill times) — rejected in
  GATE L2; the slope is used as a *gate* only, never to compute times.
- **Cross-variant timing check** — needs a held-out reference; study-only.
- **Onset-snapping the fills** — fills ship with the exact even-paced
  construction Ken eyeballed (see ordering, Deliverable 3).
- **Negative-result caching of LRCLIB searches** — the study's L0 bug class
  (`search()` returns `[]` on *failure* too; a persisted empty result bakes
  in a transient timeout). Persist only successful selections.

## Architecture at a glance

```
download time            process time (LyricsFetchStage)      process time (LyricAlignStage, joint route)
─────────────            ────────────────────────────────     ───────────────────────────────────────────
(no change)              Branch a (Genius) additionally:      after joint match + windowed realign:
                         resolve lyrics/<stem>.lrc            read lyrics/<stem>.lrc from disk
                         (on-disk first; else LRCLIB          plan fills on PRE-veto, PRE-snap objects
                         search → select → persist)           … veto … snap …
                                                              splice accepted fills in AFTER snap
regen tool: backfill lyrics/<stem>.lrc for genius reuse plans (its own fetch leg, as with SRT/json3)
```

Precedents being followed: the live Genius fetch already happens inside
`LyricsFetchStage` Branch a (the 2026-07-03 offline-pipeline decision moved
*YouTube* fetches to download time; Genius stayed in-stage because it needs
the user's choice file) — LRCLIB keys off the adopted Genius identity, so it
lives in the same branch. The align stage reads inputs from disk exactly like
`_find_youtube_srt_path` does.

## Deliverable 1 — fill module `pikaraoke/lib/lrclib_fill.py` (new file)

New file per the fork rule. All machinery below is **ported from validated
sources — do not redesign, retune, or "improve" any constant or formula.**
Sources, in priority order:

1. The study script `D:\shared\pikaraoke-songs\lrclib_study\lrclib_study.py`
   (Windows box) — the exact code the verdict was measured with.
2. The same code's own upstream refs (cited in its comments):
   `git show pathed_align:pikaraoke/lib/srt_prior.py` (tag = 1b80e985) for
   `_fill_line` + fill constants; `git show 835ba2c7:pikaraoke/lib/cue_align.py`
   for `_theil_sen`.

Keep the study script's source comments (adapted) so provenance survives.

### Constants (verbatim)

```python
FILL_SOURCE = "lrclib_fill"
MAX_FILL_WORD_DUR_S = 0.7    # srt_prior port
MIN_FILL_DUR_S = 1.2         # srt_prior port
COLLISION_TOL_S = 0.2        # study Phase L2 step 3
WARP_MIN_ANCHORS = 5         # study arm-B gate (warp_scaffold_cues port)
WARP_MAD_GATE_S = 2.0        # study arm-B gate
FILL_MAX_SLOPE_DEV = 0.01    # GATE L2 adopted gate (Ken, 2026-07-16)
```

Arm-A gate constants are NOT redefined here — reuse
`srt_cues.offset_mad_against_cues` (PRIOR_MIN_ANCHORS=4, PRIOR_MAX_MAD_S=0.75),
exactly as the study did. Energy constants come from `onset_snap`
(`HOP_S`, `SOFT_NEAR_DB`, `MIN_REF_DB`, `_sung_level_ref`) — import, never copy.

### Functions

- `_theil_sen(points) -> (slope, intercept) | None` — port from study lines
  ~82-94.
- `_fill_line(lid, text, align_line, t0, t1, source) -> dict | None` — port
  from study lines ~97-127 (uses `joint_match._tokenise_lines`). Even-paced
  words over `[t0, t1]`, span capped at
  `max(MAX_FILL_WORD_DUR_S * n_toks, MIN_FILL_DUR_S)`, `t1 <= t0` floored to
  `t0 + 0.5`.
- `_collision(t0, t1, placed_spans) -> bool` — study line ~587: any overlap
  `> COLLISION_TOL_S` with a placed line's span.
- `_energy_check(env, ref, t0, t1) -> "PASS" | "bail" | "void"` — study lines
  ~592-609, including the clamped indexing (negative t0 must not wrap the
  numpy slice) and the `max(ref - SOFT_NEAR_DB, MIN_REF_DB)` band. This is
  deliberately stricter than `evidence_veto`'s absolute floor (study A.6
  rationale: the fill gate asks "is there singing here", the veto asks "is
  this dead silent") — keep both, do not unify.
- `_slope_fit(anchors, cue_spans_by_line) -> dict` — the study's
  `_arm_b_gate` (lines ~406-426): Theil-Sen over the same
  `(cue_start, placed_start)` pairs the offset fit uses; bails
  `few_anchors` (< WARP_MIN_ANCHORS), `degenerate_fit`, or `wide_spread`
  (residual MAD > WARP_MAD_GATE_S).
- `plan_fills(line_objects, lyrics_lines, align_lines, transcribe_words,
  synced_text, env, *, margin_s, max_edit_ratio) -> tuple[list[dict], dict]`
  — the orchestrator:
  1. `cue_spans_by_line = lrclib.cue_spans_for_lines(synced_text, lyrics_lines)`;
     `None` → no-op (`eligible=False, reason="no_mapping"`).
  2. Anchors = `analyze_pass1(align_lines, line_objects,
     {"selected_source": selected_sources(line_objects, len(lyrics_lines))},
     transcribe_words, margin_s=…, max_edit_ratio=…)` (3-tuple; keep only
     anchors) — the study's `_trusted_anchors`. `selected_sources` is the
     harness's `_selected_sources`, relocated (see Deliverable 5) because a
     lib module must not import from `scripts/`.
  3. `arm_a = offset_mad_against_cues(anchors, cue_spans_by_line)`.
  4. `slope = _slope_fit(anchors, cue_spans_by_line)`.
  5. **Eligibility** (GATE L2 adopted gate): `arm_a["bailed"] is None AND
     slope["bailed"] is None AND abs(slope["slope"] - 1) <= FILL_MAX_SLOPE_DEV`.
     Ineligible → return `([], stats)` with both fits recorded.
  6. Candidates = lids whose line object has empty `words` AND
     `lid in cue_spans_by_line`. Fill span =
     `(cue_start + offset_s, cue_end + offset_s)` (constant offset — never
     the warp). Reject when `t0 < 0` (record `applied=False,
     reason="negative_start"`; on the study corpus these were all
     energy-rejects anyway, this just makes the reason explicit), on
     `_collision` against the placed spans, or on `_energy_check != "PASS"`
     (a fill past the stem end gets an empty env window → `void` → reject).
  7. Return `(accepted_fill_objects, stats)`.
- `apply_fills(line_objects, fills) -> list[dict]` — replace each filled
  lid's positional object, only if its `words` are still empty (the veto
  runs between planning and splice; a veto-demoted lid is never a fill
  candidate — it had words at planning time — and this guard keeps the
  splice safe regardless).

### Stats shape (goes into the debug bundle)

```python
{
  "n_cues_mapped": int,
  "arm_a": {...offset_mad_against_cues output...},
  "slope_fit": {...(n_anchors, bailed, slope, intercept, mad_s)...},
  "eligible": bool,
  "reason": str | None,          # "no_mapping" | "arm_a_bail" | "slope_bail" | "slope_dev" | None
  "n_candidates": int,
  "fills": [{"lid", "t0", "t1", "collision", "energy", "applied"}, ...],
  "filled_lids": [int, ...],     # the applied subset — the harness exclusion key
}
```

### Tests (`tests/unit/test_lrclib_fill.py`)

Pure functions, no I/O to mock except env arrays (small numpy fixtures):

- `_fill_line`: even pacing, per-token cap, MIN_FILL_DUR floor, `t1<=t0`
  floor, None on token-less display line.
- `_theil_sen`: known slope/intercept recovery; None on degenerate x.
- Eligibility: arm-A bail → ineligible; slope dev 0.021 (Best Part Of Me's
  value) → ineligible; slope dev 0.005 → eligible; `few_anchors` slope bail
  → ineligible.
- Per-fill gates: collision reject at 0.3 s overlap / accept at 0.1 s;
  energy bail below band; void on empty window (past-end and negative-t0
  paths); negative_start reject.
- `apply_fills`: splices at the right positions, preserves order, skips a
  lid whose words became non-empty, leaves non-candidates untouched.

## Deliverable 2 — fetch leg in `LyricsFetchStage` (+ `lrclib.ensure_lrc`)

Add to `pikaraoke/lib/lrclib.py` (it already owns search/select/lrc-IO):

```python
def ensure_lrc(song_path, title, artist, sheet_lines, media_dur) -> Path | None:
    """lyrics/<stem>.lrc for the song: reuse on disk, else fetch+select+persist.

    Returns the path when a variant is available, None otherwise. Persists
    only successful selections -- a failed or empty search leaves no file,
    so the next run retries (never bake a transient failure into disk state).
    """
```

- Path: `song_path.parent / "lyrics" / f"{song_path.stem}.lrc"` (the
  `c7bd17af` layout). Exists → return it, no network.
- Else `records = search(title, artist)`;
  `chosen = select_candidate(records, sheet_lines, media_dur)`; on a pick,
  `write_lrc(path, chosen)` and return the path; else log at info and
  return None.
- Build paths from `song_path` verbatim — song stems contain brackets, NBSP,
  soft hyphens; never retype or glob them.

`LyricsFetchStage` Branch a, after `self._resolve_ytasr(ctx)`: knob-gated
(`config.lrclib_fill`) call `self._resolve_lrclib(ctx, song)` which:

- derives `sheet_lines = [item["text"] for item in parse_lyric_lines(song.text)]`;
- media duration: `ctx.artifacts.get("media_duration_s")`, else
  `probe_duration(ctx.song_path)` (note `_resolve_ytasr` returns before
  probing when no json3 exists — don't assume the artifact is set);
- calls `ensure_lrc(...)` with `song.title, song.artist` (the canonical
  Genius identity; `search()` applies `clean_key` itself);
- never raises (mirror `_resolve_ytasr`'s catch-log-continue contract);
  logs adopted variant (track/artist/id) or the miss.

No `ctx.artifacts` stash is needed — the align stage reads the file from
disk (next deliverable), which also makes regen wiring trivial.

The stage needs `LyricsFetchStage.__init__` to receive the config (it
currently takes only `genius`) — thread `PipelineConfig` in from the
orchestrator the same way other stages get it.

Also in this commit: update `lrclib.py`'s module docstring — it still says
"LRCLIB is permanently out of the production pipeline and no production
module imports it". Narrow it to match the amended ruling: held-out
reference for the tuning harness AND the gated fill-only production path
per `plans/lrclib-fill-absence-study.md`; still banned as a matcher/DP
source.

### Tests (`tests/unit/test_lyrics_fetch.py` additions)

Mock `lrclib.search` / filesystem:

- Branch a with a synced candidate → `.lrc` persisted with provenance
  header, correct path.
- On-disk `.lrc` present → no search call.
- Search failure / no synced candidate → no file written, stage completes.
- Knob off → no resolve call.
- Genius fetch failure (existing fallback path) → no LRCLIB attempt.

## Deliverable 3 — fill hook in `LyricAlignStage`

The ordering is load-bearing; it reproduces the study's data plane exactly.
The study measured fits and fills on **post-merge, pre-veto, pre-snap** line
objects (the harness replay applies neither veto nor snap), and Ken
eyeballed **unsnapped** fills. Therefore:

```python
# run(), after env = decode_env_db(...), joint route only, knob on:
fills: list[dict] = []
if capture_method_used == "joint" and self._config.lrclib_fill:
    lrc_path = _find_lrclib_lrc(ctx.song_path)      # lyrics/<stem>.lrc or None
    if lrc_path is not None:
        synced_text, lrc_meta = lrclib.read_lrc(lrc_path)
        fills, fill_stats = lrclib_fill.plan_fills(
            line_objects, lyrics_lines, align_lines, capture_transcribe_words,
            synced_text, env,
            margin_s=cfg.joint_margin_s, max_edit_ratio=cfg.joint_max_edit_ratio,
        )
        capture_joint_stats["lrclib_fill"] = fill_stats

# ... existing veto ...
# ... existing snap_line_edges ...

if fills:
    line_objects = lrclib_fill.apply_fills(line_objects, fills)
```

Notes:

- `env is None` (decode failed) → skip planning entirely (no energy gate
  possible → no fills; record nothing or `reason="no_env"` — match the
  veto's `decode_failed` spirit).
- Planning **before** the veto keeps candidates = matcher-unplaced only: a
  veto-demoted line was placed at planning time, so it is not a candidate
  and stays demoted — the study never validated re-filling vetoed lines.
- Splicing **after** the snap means fills are never edge-snapped: the snap
  was tuned for whisper-placed onsets, and the eyeballed evidence is for
  the raw cue-derived construction.
- The env from `decode_env_db(snap_stem, …)` is the aligned (possibly
  de-reverbed) stem; the study used the wet vocal m4a envelope. Same
  `onset_snap` surface and units — accepted minor deviation, do not add a
  second decode.
- `_find_lrclib_lrc(song_path)`: module-level helper mirroring
  `_find_youtube_srt_path` (`lyrics/<stem>.lrc`, `is_file()`).
- ASS/SRT generators consume fills with no changes (fills carry `words`).
  `generate_ass` clamps event start ≥ 0 but not end — irrelevant here
  because negative-start fills are rejected at planning.

### Capture / bundle changes

- `capture_joint_stats["lrclib_fill"]` as above (only set when planning ran).
- `lyrics["lrclib"] = {"lrc_file": <rel path>, **lrc_meta}` in
  `_write_debug_capture` when the `.lrc` was read (mirror the `ytasr` /
  `genius` refs; relative to the song folder).
- `config_snapshot` gains `"lrclib_fill": cfg.lrclib_fill`.
- Bump `alignment_capture.SCHEMA_VERSION` 8 → 9 with a comment naming the
  new fields.

### Config

`PipelineConfig.lrclib_fill: bool = True` — the GO ships enabled; every
unsafe case is caught by the gates (that is what the study validated). One
knob covers both the fetch leg and the fill hook. Document it next to the
`joint_*` knobs.

### Tests (`tests/unit/test_lyric_align.py` additions)

Stage-level, mocked workers (follow the file's existing patterns):

- Joint route + on-disk `.lrc` + fabricated placements that pass the gates
  → fill appears in the output ASS with even pacing; stats captured;
  `filled_lids` correct.
- Gate-blocked song (slope dev too high) → no fills, stats record why.
- No `.lrc` on disk → no stats key, output byte-identical to before.
- Knob off → identical to no-`.lrc`.
- Fill lid also veto-demoted is impossible by construction — instead test
  `apply_fills` post-veto safety at the unit level (Deliverable 1).
- SRT route: assert the hook never runs (`capture_method_used != "joint"`).

## Deliverable 4 — regen backfill

`scripts/regen_alignment_bundles.py` is the on-demand fetch path for the
existing library. Genius **reuse** plans (`_reuse_plan`) bypass
`LyricsFetchStage`, so without this leg an existing song never gains a
`.lrc`.

- Where the regen tool runs its other network legs (`execute_fetches`), add:
  for genius-origin plans (reuse or sidecar), knob-gated,
  `lrclib.ensure_lrc(song, genius["title"], genius["artist"], lines,
  media_dur)` using the bundle's recorded `lyrics.genius` identity +
  `lyrics.lines` + `media_duration_s` (probe as fallback). Reuse-first
  semantics come free from `ensure_lrc`.
- Sidecar plans that go through the real `LyricsFetchStage` get the resolve
  from Deliverable 2 — don't double-fetch; `ensure_lrc`'s disk check makes
  a duplicate call harmless, but prefer one call site per plan kind.
- **Verify the `.lrc` survives regen's reset path**: `clear_output_folders`
  must treat `lyrics/<stem>.lrc` as an *input* (like the ASR json3), not an
  output to clear. Extend `backup_text_folders` if it backs up comparable
  inputs. Check both functions before assuming.

Test: unit-test the plan-building change if the file has tests; otherwise
cover via the manual test plan (regen is exercised by hand on this project).

## Deliverable 5 — harness tag-and-exclude (Phase L4 requirement)

`scripts/replay_ytasr_third_source.py` scores placements against LRCLIB
references. Production fills come FROM LRCLIB — scoring them against it is
circular and would pollute matcher metrics.

- Relocate the harness's `_selected_sources` (line ~182) to
  `pikaraoke/lib/windowed_realign.py` as a public `selected_sources(...)`;
  harness and `lrclib_fill` both import it (single source of truth; a lib
  module must not import from `scripts/`). Mechanical move, no behavior
  change — goes in the Deliverable 1 commit.
- Exclusion: wherever the harness reads a bundle's recorded final
  placements (`output_line_timings`) or otherwise scores line objects that
  could contain fills, drop lids in `joint_stats.lrclib_fill.filled_lids`
  first and report the excluded count. The harness's own replays are
  matcher-only and need no change — audit where recorded outputs enter
  scoring before editing; if they never do at HEAD, record that finding in
  the commit message and add the guard only where real.
- `pass1_line_timings` and replay legs are pre-fill — untouched.

## Commit plan

Follow CLAUDE.md: group by feature, tests ride with their code, import-smoke
+ read `git diff --cached` before each commit, inline self-review
(correctness / simplicity / robustness) every time. Work on a feature
branch; never commit to `master`. Do NOT self-launch `/code-review`; flag
commits 1 and 3 for full review at the checkpoint (they add logic; 2, 4, 5
are wiring/plumbing — inline self-review suffices unless the diff surprises
you).

1. `feat(lrclib): gated-fill planning module` — `lrclib_fill.py`,
   `selected_sources` relocation + harness import swap, unit tests.
2. `feat(pipeline): fetch LRCLIB variant for genius songs` —
   `lrclib.ensure_lrc`, `LyricsFetchStage` leg, config knob, docstring
   narrowing, tests.
3. `feat(pipeline): apply LRCLIB gated fill on the joint route` —
   `LyricAlignStage` hook, capture fields, SCHEMA_VERSION bump, tests.
4. `feat(regen): backfill LRCLIB variants for genius reuse plans` — regen
   wiring + reset-path audit.
5. `chore(harness): exclude filled lids from held-out scoring` — after 3,
   since it reads the stats shape 3 defines.

Run the full test suite and
`pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
before the final commit. Known-failing baseline tests on the Windows box are
recorded in the project memory — do not chase failures that predate the
branch.

## Manual test plan (PR checklist)

The study workspace `D:\shared\pikaraoke-songs\lrclib_study\out\l2_fills_a.json`
is the oracle for expected fills. Caveat: a fresh process re-runs whisper, so
placements (hence offsets/fills) can differ slightly from the study's
captured replay — expect the same *filled lids* with spans within ~0.5 s;
investigate qualitative divergence (different lids, unexpected eligibility)
rather than eyeballing it away.

- [ ] Regen/process Belle → 5 fills at the study's lids (incl. lid 89),
      eyeball the ASS render.
- [ ] Girl in the Bubble → 5 fills; Next Ten Minutes → 3; NSYNC → 2;
      Domino → 1.
- [ ] Seasons of Love → ineligible (`slope_dev` ≈ 4.2%), 0 fills.
- [ ] Best Part Of Me → ineligible (`slope_dev` ≈ 2.1%), 0 fills.
- [ ] Bloodstream → arm-A bail (`wide_spread`), 0 fills.
- [ ] A genius song with no LRCLIB variant → no `.lrc` persisted, clean run.
- [ ] An SRT song → no LRCLIB activity anywhere in the log.
- [ ] `lrclib_fill = false` → no fetch, no fills, bundle has no
      `lrclib_fill` stats.
- [ ] Regen reset on a song with a `.lrc` → the `.lrc` survives.
- [ ] Bundle inspection: `lyrics.lrclib`, `joint_stats.lrclib_fill`,
      `config_snapshot.lrclib_fill`, `schema_version: 9` all present.

## Decisions already made — do not relitigate during implementation

- Constant offset (arm A) computes fill times; slope is a gate only.
- Gates and constants are the study's, verbatim; no tuning.
- Fills are never snapped, never vetoed, never re-placed.
- Fetch lives in the Genius branch of `LyricsFetchStage` + the regen tool;
  no download-time leg (the Genius identity doesn't exist yet at download
  time).
- Knob default is on.
- No negative caching; persist only successful selections.

If implementation uncovers a genuine conflict with any of these (code
reality differs from what this plan assumes), stop and flag it rather than
silently adapting — same drift discipline as the study.
