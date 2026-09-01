# Joint matcher catch-all refit

Model: Claude Sonnet 5 (executor). Plan drafted by Claude Fable 5.

## Context

Routing (per `complete-matcher-wiring.md` + the engine plans' ladder)
makes the joint matcher the bottom catch-all: songs with no YT SRT
(cue-align route) and no matching LRCLIB/syncedlyrics timing (scaffold
warp route), plus S-3 warp-rejects. Expected population: Genius-only
sheets — live/remix version mismatches (extra audio in the video,
extra text in the sheet, possibly out-of-order sections) — and a clean
tail of songs that merely lack synced-lyrics coverage. The refit
targets that population without gutting the clean tail.

### Inherited rulings (not re-litigated here)

- **S-3 rider** (`ctc-sync-engine.md`): the joint route may adopt CTC
  as its aligner and be refactored to target the
  warp-reject/version-mismatch class. This plan is that refactor.
- **GATE O**: emission self-policing FAILED (band + phantom). CTC
  swaps the *witness* (align-candidate source), never the *judge* —
  the multi-witness DP scoring (transcribe/ytasr/energy corroboration)
  stays. `s_tx_roll5` is licensed as an advisory demote-only signal;
  it is NOT in this plan's default scope.
- **GATE C / GATE S**: CTC timing is the best in the project (33/33
  eyeball; 0.47s vs 1.61s mean overlap; 7.1% vs 17.5% re-pace; GATE C
  recorded CTC edge timing as already better than the snap's). Snap
  applicability on CTC-timed routes is the engine plan's Appendix D
  decision — GATE J2 below feeds it.

### Hypotheses under test (Ken, 07-19)

- **H-resync**: CTC re-syncs after a mismatch region better than
  whisper align (which drifts or collapses, e.g. DG 470→3).
- **H-snap**: if CTC timing is tight at line edges, edge snap retires
  on CTC-won lines of the joint route.

## Execution discipline (read first)

- Branch: `joint_catchall_refit` off the `timing_pillars` tip. Never
  commit to `master`.
- Phase order: 1 → 4 → 2a → **STOP** (GATES J1/J2) → 2b → GATE V →
  3 → GATE T. Phase 4 before 2a because it is cheap and fills the
  gate-reading queue.
- Probe *outputs* (emission `.pt` caches, per-line score tables,
  corpus CSVs) live in the session scratchpad, **never committed**
  (mirror of `timing-source-pillars.md` ground rules). The two CTC
  probe *drivers* are the exception Ken carved out: committed with
  this plan as `scripts/phase1b_score_oracle.py` (MMS_FA
  model/emission/align recipe) and `scripts/sb_ctc_adapter.py`
  (the `slice_align` adapter that ran S-B) — they are the reference
  implementation for Phase 2a's CTC arm and the eventual
  `ctc_align.py` port, so they earn a durable home. New per-phase
  drivers (Phase 4's telemetry replay, Phase 2a's A/B harness) stay
  scratchpad unless a later ruling promotes them the same way. Raw
  tables are appended to this plan's Results log via docs commits —
  tables only, **no verdicts**. Gates are read off by Ken/Fable;
  stop and alert at every GATE.
- **Cross-plan sequencing (Ken, 2026-09-01):** this plan's Phase 4
  (GATE P) and Phase 2a (GATE J1/J2) are steps 1 and 3 of the
  measurement block in `plans/timing-source-pillars.md`, "Remaining
  execution order" — Phase 4 runs first of everything on either plan
  (cheapest, no GPU, and a material GATE P commissions a section-level
  DP that breaks the 1:1 `line_objects` contract). Phase 1's code
  changes are not part of the measurement block and land on this
  plan's own schedule. Note 1.1 preserves `.lrc` persistence
  deliberately: that is F2's line source in the build plan.
- The SRT/cue route must stay byte-identical throughout. Fork
  maintenance: new logic in new files; upstream files change only at
  the call sites this plan names.
- Env: conda `pik`. Tests:
  `/home/ken/miniconda3/envs/pik/bin/python -m pytest`. Pre-commit
  scoped to changed files (`--files`), never `--all-files`.
- Batch qualifying logic commits for `/code-review`; alert Ken at
  phase checkpoints (never auto-launch). Docs/table commits don't
  qualify.
- Library root: `/home/ken/pikaraoke-songs`. Per song:
  `vocal/<stem>---vocal.m4a` (wet stem),
  `dereverb/<stem>---dereverb.m4a` (present iff the gate ever fired —
  when present, it is the stem alignment ran on; prefer it),
  `alignment_debug/<stem>.json` (bundle), `lyrics/<stem>.txt` (Genius
  sheet), `lyrics/<stem>.lrc` (held-out LRCLIB variant, when any),
  `subtitles/<stem>.en.asr.json3` (YTASR).

## Phase 1 — dead weight + input hardening

### 1.1 Delete the LRCLIB fill path

The catch-all route only receives songs whose LRCLIB match was
rejected or absent; a `lyrics/<stem>.lrc` found here is a
wrong-version text, and filling from it is harmful. **Scope: the fill
machinery only.** LRC *persistence* stays — the `.lrc` variant is the
held-out tuning reference (Phase 3) and future scaffold-route data.

1. `pikaraoke/pipeline/stages/lyric_align.py`: delete the fill
   planning block (the `fills`/`capture_lrclib_ref` section between
   the env decode and the veto), the `apply_fills` call after the
   snap, `_find_lrclib_lrc`, the `lrclib_ref` parameter and its
   `lyrics["lrclib"]` write in `_write_debug_capture`, the
   `"lrclib_fill"` entry in `config_snapshot`, and the now-unused
   `lrclib`/`lrclib_fill` imports.
2. `pikaraoke/pipeline/config.py`: rename `lrclib_fill` →
   `lrclib_persist` and rewrite its comment: it now gates only the
   `.lrc` resolve/persist legs. Update the two remaining consumers:
   `lyrics_fetch.py` (`_resolve_lrclib` gate) and
   `scripts/regen_alignment_bundles.py` (backfill leg + the
   `_prepare_lyrics` no-YouTube-id leg).
3. Delete `pikaraoke/lib/lrclib_fill.py` and
   `tests/unit/test_lrclib_fill.py`. Trim fill-specific cases from
   `test_lyric_align.py`; adjust knob-name uses in
   `test_lyrics_fetch.py` / `test_regen_alignment_bundles.py`.
4. `pikaraoke/lib/alignment_capture.py`: update the
   `joint_stats.lrclib_fill` / `config_snapshot.lrclib_fill` schema
   comments (historical bundles keep the keys; new bundles simply
   omit them). **Do NOT bump `SCHEMA_VERSION`** — omission is
   additive-compatible and a bump would trigger a full-library regen.
5. `scripts/replay_ytasr_third_source.py` reads
   `joint_stats.lrclib_fill.filled_lids` with an `or []` default —
   works on both old and new bundles; leave it.

Commit: `refactor(joint): drop LRCLIB fill from the catch-all route`.

### 1.2 Harden `parse_lyric_lines` against wrapped-bracket dirt

GATE S production fix-item: 5/17 sheets carry section headers wrapped
across physical lines (`[SHANG &` ⏎ `SOLDIERS]`, `[CITIZENS OF OZ &`
⏎ `…]`), which defeat the single-line `_HEADER_RE` and
`_BRACKET_CONTENT_RE` filters and leak as sung text.

1. `pikaraoke/lib/genius_lyrics.py`: add a pre-pass in
   `parse_lyric_lines` that joins physical lines into logical lines
   when a line has an *unclosed* `[` (more `[` than `]` at
   end-of-line): append following lines (space-joined) until the
   bracket closes, bounded at 3 continuation lines. If it never
   closes within the bound, leave the lines untouched (today's
   behavior). The joined logical line then flows through the existing
   filters: a bracket-only join dies at `_HEADER_RE`, an inline wrap
   (`la la [CHORUS` ⏎ `HOOK] more words`) is cleaned by
   `_BRACKET_CONTENT_RE` inside `normalize_lyric_line`, keeping the
   surrounding words.
2. Tests (`tests/unit/test_genius_lyrics.py`): two-line wrapped
   header dropped; three-line wrapped header dropped; inline wrap
   keeps surrounding text; unclosed-beyond-bound left as-is;
   single-line headers and normal sheets byte-identical.
3. Corpus validation (scratchpad script, not committed): for every
   `lyrics/*.txt` under the library root, diff
   `parse_lyric_lines` old vs new (`text` lists). Expected: diffs
   only on wrap-dirt sheets (the GATE S five incl. Man Out of You,
   Defying Gravity), all diffs are dirt removals/joins, zero sung
   lines lost elsewhere. Append the diff table to the Results log.

Commit: `fix(genius): join wrapped bracket headers in parse_lyric_lines`.

**GATE 1** (light): diff review + corpus parse table. Proceed unless
the table surprises; flag anything ambiguous rather than deciding.

## Phase 4 — out-of-order probe (stats only, zero behavior change)

Runs before Phase 2 because it is cheap and independent. The
monotonic DP deliberately fights reordering (chorus-steal defense);
this phase only measures what that costs.

1. `pikaraoke/lib/joint_match.py`: in
   `match_words_to_lines_joint_with_stats`, after `selected` is
   computed, add two stats blocks computed from `all_candidates` +
   `selected` (no change to any placement):
   - `monotone_discard`: per line,
     `best_unconstrained = max(score)` over that line's candidates;
     `gap = best_unconstrained - selected_score` (selected_score = 0
     when unplaced). Record `sum_gap`, `n_lines_with_gap`
     (gap > 0.5), and for those lines
     `{line_id, gap, best_t0, selected_t0|None}`.
   - `inversions`: over lines whose unconstrained argmax candidate
     scores ≥ 4.0 (matched-token units; `ANCHOR_MIN_TOKENS`
     precedent), walk adjacent pairs in line_id order and count pairs
     where the later line's argmax starts > 1.0s *before* the earlier
     line's argmax start. Record `n_inversions`,
     `max_inversion_span_s`, and the offending pairs.
2. Tests (`test_joint_match.py`): synthetic reordered transcribe
   stream → nonzero inversions + discard mass; monotone stream →
   zeros; keys always present. Stats keys are additive — no
   `SCHEMA_VERSION` bump.
3. Corpus run (scratchpad driver on the
   `replay_ytasr_third_source.py` chassis — replay-only, no GPU):
   every genius-origin bundle; table: song | n_lines | sum_gap |
   n_lines_with_gap | n_inversions | max_span_s. Append to Results
   log.

Commit: `feat(joint): monotone-discard + inversion telemetry`.

**GATE P** (Ken): prevalence material → commission a section-level DP
design (own plan; sheet sections permute/repeat, monotonic within a
section; breaks the 1:1 line_objects contract). Otherwise record
NO-GO and keep the monotonic DP as-is.

## Phase 2a — CTC-in-joint offline A/B (scratchpad; gates the swap)

No repo changes except the Results-log docs commit. The CTC recipe is
already committed as `scripts/phase1b_score_oracle.py` (model +
`get_emission` + `align_words`) and `scripts/sb_ctc_adapter.py` (the
`slice_align` wrapper) — import from those, do not re-copy. Emission
`.pt` caches land under `<temp>/ctc_probe/emissions/`; a previous
session's caches (if the scratchpad at
`/tmp/claude-1000/-home-ken-pikaraoke/fe1b017e-*/scratchpad/emissions/`
survives) can be copied there to skip the forward passes, but the
drivers recompute on a miss so this is an optimization only. The
recipe is also restated below so the plan is self-contained.

### CTC recipe (restated so the probe survives scratchpad loss)

- Model: `torchaudio.pipelines.MMS_FA` (`bundle.get_model()`,
  `get_tokenizer()`, `get_aligner()`), CUDA.
- Audio: ffmpeg-decode the stem to mono 16 kHz s16 WAV; read via
  `soundfile` (this torchaudio build's default backend needs
  torchcodec, not installed).
- Emission: chunked forward passes (`CHUNK_S = 20.0`), concatenated;
  `ratio = num_wave_samples / emission.size(0)`; cache per song as
  `{"emission": Tensor, "ratio": float}` `.pt` in the scratchpad.
- Words: `normalize_word` = lowercase, ASCII-fold apostrophes, drop
  chars outside the MMS_FA charset; tokens normalizing to "" are
  dropped from tokenizer input but tracked so surviving words map
  back to raw text. `aligner(emission_slice, tokenizer(norm_words))`
  → per-word frame spans → seconds via `ratio / SR`, offset by slice
  start. `RuntimeError` from the aligner → return None (caller
  degrades), matching the S-B contract.

### Harness

Scratchpad driver on the `replay_ytasr_third_source.py` chassis (it
already: loads genius-origin bundles, replays
`match_words_to_lines_joint_with_stats` + windowed-realign
`replay_span`/`merge_spans` from captured words, and scores
placements vs held-out LRCLIB via `analyze_pass1` +
`srt_cues.offset_mad_against_cues`). Extend it with:

1. **Arm A** — exact replay: bundle's captured whisper `words`
   (refine) as `align_words`. Current defaults for all knobs.
2. **Arm B** — CTC arm: `align_words` produced by full-song CTC
   forced align of the bundle's `align_lines` flat token stream over
   the song's stem (dereverb stem when `dereverb/` cache exists, else
   wet vocal). One timed word per surviving token; joint matcher
   **unchanged** — `_line_align_ranges` absorbs the OOV-dropped
   tokens exactly as it absorbs whisper drops. Same knobs as Arm A.
3. Both arms run the same replay path end-to-end (joint DP +
   windowed-realign replay + evidence-veto is NOT replayable offline
   — skip veto in both arms, note in table header).
4. **Pace telemetry** (for the 2b guard recalibration): per align
   candidate in each arm, `(t1-t0)/n_tokens`; dump the distribution
   and `_MIN_ALIGN_PACE_S` fire counts per arm.
5. **H-snap arm**: on Arm B's final line_objects, run
   `onset_snap.decode_env_db` + `snap_line_edges` against the same
   stem (CPU, cheap). Record per-line |onset Δ| and |end Δ|,
   split align-won vs transcribe/ytasr-won. Columns: median, p90,
   % > 150 ms.
6. **H-resync metric**: from Arm A's stats, dark regions = maximal
   runs (≥ 2 lines) where the selected candidate has
   `transcribe_match == 0` and `ytasr_agreement == 0.0`, or the line
   is interp/absent. For each dark region, take the first 3 following
   lines that have a held-out LRC reference cue; per arm record
   mean |placement start − reference start|. Aggregate per song.
   Songs with no LRC reference: excluded from this table; dump
   per-line offset traces (CSV, scratchpad) for DG, Hakuna Matata,
   Man Out of You for the eyeball regardless.

### Cohort + outputs

All genius-origin bundles in the library (the catch-all population).
Main table per song × arm: placed / align-won / transcribe-won /
ytasr-won / interp / absent | median offset + MAD vs held-out LRC |
consecutive-line overlap count | pace-guard fires. Plus the H-resync
table, the H-snap table, and the pace distributions. Append all raw
to the Results log; **no verdicts**. STOP.

**GATE J1** (Ken/Fable): adopt CTC-in-joint iff Arm B wins or ties
everywhere material and H-resync shows the claimed recovery; eyeball
on the dirty cohort. NO-GO → skip 2b entirely; Phase 3 tunes the
whisper-align matcher instead. The 2b pace-guard constant is also set
at this read-off from the pace telemetry.

**GATE J2** (feeds engine-plan Appendix D): retire edge snap on
CTC-won joint lines iff the H-snap deltas are ~zero/negative. Snap
stays for transcribe/ytasr-won lines unless the same table clears
them too.

## Phase 2b — production integration (only on GATE J1 GO)

Replacement path + gated cutover, never in-place (house rule).

1. **New module `pikaraoke/lib/ctc_align.py`** (port of the recipe
   above; no scratchpad imports): `load_model()`,
   `compute_emission(model, wav)` (chunked), and
   `ctc_align_words(vocal_wav, align_lines) -> tuple[list[dict],
   list[dict | None]]` returning (words 1:1 with surviving tokens,
   per-line `{t0, t1, word_idx}` ranges built positionally from the
   trellis — no fuzzy re-derivation). No on-disk emission cache in
   production (one forward pass per song, seconds on the 2060).
   Load the model on demand and release + `torch.cuda.empty_cache()`
   after the align — whisper worker stays resident in its subprocess;
   VRAM co-residency is a GATE V watch item (`nvidia-smi` during the
   regen).
2. **Config**: `PipelineConfig.joint_ctc_align: bool = False`. In
   `lyric_align._run_joint`, when True, call `ctc_align_words` in a
   `Phase.ALIGN` activity scope instead of `worker.align_refine`; the
   transcribe pass and de-reverb gate are untouched (transcribe is
   still the witness). Record `joint_stats["aligner"] =
   "ctc" | "whisper"`.
3. **`joint_match` surface**: add keyword-only
   `align_ranges: list[dict | None] | None = None` to both public
   functions; when provided, skip `_line_align_ranges`. Whisper path
   passes None (unchanged). Pace guard: keep the guard; set the
   CTC-calibrated constant chosen at GATE J1 (module constant beside
   `_MIN_ALIGN_PACE_S`, selected by aligner). Corroboration gates,
   veto, DP: untouched.
4. **Windowed re-align**: unchanged (still whisper slice-align). Its
   suspect/span counts under CTC are a GATE V measurement; the
   emission-slice re-decode replacement is a recorded follow-up, not
   built here.
5. Tests: `ctc_align` unit-tested with a stubbed
   model/tokenizer/aligner (no GPU in CI); `align_ranges` bypass
   path; flag routing (True → worker.align_refine not called);
   pace-guard constant selection; SRT route untouched (existing
   regression tests must pass unmodified).
6. Cutover: after GATE V, one commit flips the default to True.

Commits: `feat(lib): MMS_FA CTC aligner module`,
`feat(joint): CTC align-candidate source behind joint_ctc_align`,
cutover commit after GATE V.

**GATE V** (live): regen the genius-origin corpus songs with the flag
on (`scripts/regen_alignment_bundles.py`); compare the standard table
vs Phase 2a Arm B (should reproduce) and vs Arm A; VRAM watch; Ken
eyeballs the dirty cohort. Snap wiring change (if GATE J2 retired it
on CTC-won lines) rides here: skip `snap_line_edges` for
`source == "align"` objects when the CTC flag is on — guarded,
single call site in `lyric_align.run`.

## Phase 3 — knob re-tune on the catch-all population

Strictly after GATE J1 (tune the surviving matcher). Base:
`replay_ytasr_third_source.py` sweep mode, CTC or whisper align words
per the J1 outcome.

1. Sweep `alpha × beta` ∈ {1.0, 1.5, 2.0, 2.5, 3.0} × {1.0, 2.0,
   3.0} at fixed `margin_s`/`max_edit_ratio`; cohort = all
   genius-origin bundles; metrics = the harness's standard MAD /
   overlap / placed vs held-out LRC.
2. **ytasr co-primary probe**: on the ytasr-having subset, re-run the
   best 3 grid points at `ytasr.CANDIDATE_MAX_EDIT_RATIO` ∈ {0.34,
   0.45, 0.55} (module constant override in the driver, not a config
   knob yet). Rationale: on live/remix songs ytasr transcribes the
   actual video; the strict ratio was tuned when ytasr was a minor
   third source.
3. Caveat recorded in the table header: held-out LRC exists only for
   LRCLIB-covered songs; the truly-dirty tail is judged by structural
   metrics (overlap, placed/absent) + Ken's eyeball.
4. Raw tables to Results log; no verdicts. STOP.

**GATE T** (Ken): pick knobs. Hard criterion: no clean-tail song
regresses materially vs current defaults (clean tail still lands on
this route). Config-default change lands as one commit with the gate
reference.

## Out of scope

- Section-level DP build (gated behind GATE P, own plan).
- S-C SRT aligner switch and scaffold-route work
  (`ctc-sync-engine.md` owns them; `ctc_align.py` is written so the
  S-C switch can consume it — one CTC implementation, two consumers).
- De-reverb retry retirement (engine-plan Appendix D; joint still
  consumes transcribe as a witness).
- Windowed re-align emission-slice re-decode (follow-up iff J1 GO
  and GATE V still shows spans worth owning).
- `s_tx_roll5` advisory demote (licensed but not default scope; only
  on explicit GATE J1 read-off instruction).

## Results log

(append raw tables here; one docs commit per phase)

### 2026-09-01 — Phase 4 (monotone-discard + inversion telemetry), Windows box — raw table, no verdict

Instrument committed as `feat(joint): monotone-discard + inversion
telemetry`; corpus replayed by a scratchpad driver on the
`replay_ytasr_third_source.py` chassis (replay-only, no GPU, no
whisper). Output is the table; **GATE P is Ken's read-off.**

**Environment deviation (recorded):** run on the Windows dev box (uv
`.venv`), not the conda `pik` Linux box the Ground rules name — that
box was not reachable this session. `libmpv` is absent here, so
`tests/conftest.py` cannot import the package; the suite was run with
an import stub for `mpv` on `PYTHONPATH`, outside the repo and never
committed. Full suite: **1512 passed, 4 failed, 2 skipped**; all four
failures reproduce with this phase's changes stashed
(`test_genius.py::test_write_overwrites_existing`, two
`test_pipeline_stem_worker.py` cases, one `test_whisper_worker.py`
case) and are Windows-platform issues — file-overwrite semantics and
multiprocessing pipe teardown. `test_joint_match.py`: 62 passed (59
pre-existing unmodified + 3 new). Pre-commit on the two changed files:
clean.

**Corpus:** 18 genius-origin bundles of the 34 on disk (16 srt-origin
skipped via `ground_truth_refs.youtube_srt_present`). *Discrepancy
flagged, not resolved:* the evidence plan and this plan both describe
the genius-origin segment as **17** songs; the on-disk count is 18.
Not investigated — recorded so the judge knows the denominator moved.

**Knobs:** each bundle's own recorded `joint_stats.knobs`
(alpha/beta/margin_s/max_edit_ratio/lookahead/anchor_fallback) — a
production-faithful replay, not a sweep.

**Thresholds:** gap > 0.5; inversion eligibility score >= 4.0;
inversion span > 1.0 s.

**Implementation reading recorded (the spec left it implicit):** the
inversion walk filters to score >= 4.0 lines *first*, then walks
adjacent pairs within that filtered set in line_id order. The
alternative reading — adjacent in the full line_id sequence with both
ends eligible — would count fewer pairs.

| song | n_lines | sum_gap | n_lines_with_gap | n_inversions | max_span_s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Defying Gravity (Wicked 20th) | 89 | 33.31 | 18 | 1 | 35.28 |
| Free (Sony Animation) | 41 | 13.90 | 7 | 6 | 92.66 |
| Popular (Wicked 20th) | 62 | 21.46 | 8 | 1 | 16.16 |
| Be Our Guest | 77 | 18.63 | 11 | 3 | 110.54 |
| Belle | 110 | 19.47 | 13 | 2 | 251.84 |
| Best Part Of Me | 38 | 14.16 | 8 | 1 | 1.20 |
| Bloodstream | 74 | 164.38 | 31 | 11 | 109.84 |
| HUNTR/X This Is What It Sounds Like | 53 | 127.00 | 16 | 6 | 91.86 |
| Domino | 67 | 48.44 | 15 | 4 | 154.11 |
| In Summer | 31 | 1.00 | 1 | 0 | 0.00 |
| I'll Make a Man Out of You | 47 | 45.31 | 15 | 7 | 68.80 |
| NSYNC Paradise | 65 | 43.98 | 22 | 6 | 133.87 |
| Colors of the Wind | 37 | 9.89 | 3 | 1 | 80.24 |
| Seasons of Love | 34 | 23.26 | 10 | 0 | 0.00 |
| Stay Gold | 38 | 0.00 | 0 | 0 | 0.00 |
| Hakuna Matata | 40 | 38.58 | 12 | 3 | 101.04 |
| The Next Ten Minutes | 71 | 17.73 | 8 | 1 | 18.70 |
| Girl in the Bubble (For Good 2025) | 36 | 29.15 | 13 | 4 | 80.96 |

**Totals:** sum_gap 669.66 over the corpus; 211 of 1010 lines carry a
gap > 0.5; 57 inversions across 18 songs, 15 songs carrying at least
one; largest single span 251.84 s (Belle).

**Facts a read-off may want, recorded without interpretation:** one
song is fully clean on both blocks (Stay Gold, 0.00/0); two songs carry
gap mass with zero inversions (Seasons of Love 23.26, In Summer 1.00);
the two largest gap totals (Bloodstream 164.38, HUNTR/X 127.00) are
also the two songs the S-B arm flagged for drift signature. Per-song
inversion pair lists and gap-line details were produced by the driver
and left in the session scratchpad per the probe-output rule; the table
above is the durable record.

**STOP — GATE P.** No verdict recorded here. The rule: prevalence
material → commission a section-level DP design as its own plan (breaks
the 1:1 `line_objects` contract); otherwise record NO-GO and keep the
monotonic DP as-is.

