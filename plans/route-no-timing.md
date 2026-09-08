# Joint matcher catch-all refit

Model: Claude Sonnet 5 (executor). Plan drafted by Claude Fable 5.

> **START HERE — the live build lane as of 2026-09-08.** Ken ceased work
> on the line route (S-1 withdrawn; `plans/route-line-timing.md` closing
> entry), so every song without an uploader SRT lands here permanently
> and this plan is the only build lane left. State of the phases:
> **1.1 CANCELLED** (keep the LRCLIB fill — see the note there),
> **1.2 DONE** (`2516ca8`), **4 CLOSED** (GATE P NO-GO), **2a RAN
> 2026-09-08 and GATE J1 is NO-GO** — whisper stays the joint aligner,
> so **2b and GATE V are skipped entirely** and **GATE J2 cleared
> nothing** (Appendix D unchanged). **Phase 3 → GATE T is NEXT**, on
> the whisper matcher, then **Phase 5** (line timing as a fill source),
> then GATE L when the Mandarin corpus exists. Sequencing lives in
> `plans/PROGRAM.md`.

## Context

Routing (per `complete-matcher-wiring.md` + the engine plans' ladder)
makes the joint matcher the bottom catch-all: every song with no YT
SRT (cue-align route). *As drafted this excluded songs with matching
LRCLIB/syncedlyrics timing, which were to take a scaffold warp route;
that route was withdrawn 2026-09-08, so those songs stay here and their
timing enters only through the gated fill.* Expected population:
Genius-only sheets — live/remix version mismatches (extra audio in the
video, extra text in the sheet, possibly out-of-order sections) — and a
clean tail of songs that merely lack synced-lyrics coverage, plus the
songs whose fetched timing describes a different edit (M7-a: most of
them). The refit targets that population without gutting the clean
tail.

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
- Phase order: ~~1 → 4 → 2a → **STOP** (GATES J1/J2) → 2b → GATE V →~~
  3 → GATE T → 5. *(2026-09-08: 1.1 cancelled, 1.2 done, 4 closed at
  GATE P; Phase 5 added; 2a ran and GATE J1 came back NO-GO, so 2b and
  GATE V are struck and **Phase 3 is the head of the queue**.)* Phase 4
  ran before 2a because it was cheap and filled the gate-reading queue.
- Probe *outputs* (emission `.pt` caches, per-line score tables,
  corpus CSVs) live in the session scratchpad, **never committed**
  (mirror of `PROGRAM.md` ground rules). The two CTC
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
  measurement block in `plans/PROGRAM.md`, "Remaining
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

### 1.1 ~~Delete the LRCLIB fill path~~ — CANCELLED 2026-09-08 (Ken)

**Do not delete the fill.** The rationale below was conditional on the
line route existing: only then would an `.lrc` reaching this route be,
by construction, a rejected or wrong-version source. With that route
withdrawn, the fill is the *only* door through which fetched line
timing reaches production, and it is the shipped precursor of Phase 5:
line timing fills the holes the audio could not place, the audio owns
every line it did place, a wrong-edit source is bounded to the lines it
fills, and its eyeballed record is 16 good / 0 bad on the 17-song
corpus (`plans/completed/lrclib-fill-absence-study.md`, GATE L2). The
steps below are kept as the record of what would have been removed.

*Original rationale:* The catch-all route only receives songs whose
LRCLIB match was rejected or absent; a `lyrics/<stem>.lrc` found here
is a wrong-version text, and filling from it is harmful. **Scope: the
fill machinery only.** LRC *persistence* stays — the `.lrc` variant is
the held-out tuning reference (Phase 3) and future scaffold-route data.

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

### 1.2 Harden `parse_lyric_lines` against wrapped-bracket dirt — DONE 2026-09-08 (`2516ca8`)

**Built with a different mechanism than specified below:** Genius wraps
one logical line across physical lines at the edges of an annotated
span, so the fix rejoins on an unclosed `[` or `(` bounded by the
stanza blank line rather than by a 3-line count, and the existing
bracket defences then fire. Corpus table (5 of 17 sheets change; the
only letters removed are the two attributions) is in
`plans/route-line-timing.md`, entry "Lyric-parser wrap fix". GATE 1 was
Ken's ruling that the fix sits inside measure-first. Spec kept as
record.

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

*Status (2026-09-01): **NO-GO** — read off by Fable, recorded in the
Results log below. The monotonic DP stands unchanged and no
section-level DP plan is commissioned. Phase 4 is closed; the
telemetry stays in the matcher as a standing instrument.*

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

*Status (2026-09-08): **NO-GO** — read off by Fable, recorded in the
Results log below. Whisper stays the joint aligner. Phase 2b is
skipped entirely and GATE V never fires; Phase 3 sweeps the whisper
matcher instead. The 2b pace-guard constant is moot and, per the same
read-off, not selectable from this telemetry anyway. The S-3 rider is
unexercised, not withdrawn.*

**GATE J2** (feeds engine-plan Appendix D): retire edge snap on
CTC-won joint lines iff the H-snap deltas are ~zero/negative. Snap
stays for transcribe/ytasr-won lines unless the same table clears
them too.

*Status (2026-09-08): **neither population cleared** — read off by
Fable, recorded below. Appendix D does not move. Two cautions carried
forward: the criterion is partly tautological against the snap's
minimum shift, and J2's burden ("retire iff ~zero") points opposite to
Appendix D's ("OFF unless a named fix"). That conflict is Ken's and
must be settled before Appendices C/D/E are re-locked.*

## Phase 2b — production integration (only on GATE J1 GO)

> **SKIPPED 2026-09-08 — GATE J1 NO-GO.** Never built; GATE V never
> fires. Kept as the record of what a GO would have commissioned. Its
> step 3 ("set the CTC-calibrated constant chosen at GATE J1") is
> additionally recorded as *not executable* from the Phase 2a
> telemetry — see the read-off.

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
`replay_ytasr_third_source.py` sweep mode. **The surviving matcher is
the whisper one (GATE J1 NO-GO, 2026-09-08), so this phase sweeps
whisper align words. It is the program's next spend.**

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

## Phase 5 — line timing as a fill source (design owed; after GATE J1)

Added 2026-09-08 when Ken closed the line route. This is where the line
route's one surviving asset lands: **where the fetched sidecar is right,
its timing is good** (R-1 eyeball: 6 of 10 usable, one better than
production; M7-a: the sound ones certify within a fraction of a second),
but it is right for a minority of songs (4 of 17) and **no per-song
test separates the sound from the wrong-edit** (R-4; the warp gate's
verified blind spot; the fallback's shape diagnostic; the duration
signal). So the timing must enter **per line and lose per line**, and
the shipped mechanism that already does exactly that is the gated fill
(`pikaraoke/lib/lrclib_fill.py`): matcher-unplaced lines only, cue time
plus a constant offset, per-song offset-consistency and unity-slope
gates, per-line collision rejection, a placed line never moved, an
eyeballed 16 good / 0 bad record.

**Scope (to be designed once J1 has picked the aligner, not before):**

1. Widen `plan_fills`' source from `lyrics/<stem>.lrc` to the fetch
   pillar's sidecar `lyrics/<stem>.timing.json` (`kind` word or line;
   word sidecars contribute their line `ts`/`te`), under the **same
   gates and the same fill-only contract**. Source precedence when both
   exist is a design question; do not answer it by intuition.
2. Never fill past the media ends, never over an audio-placed line —
   the two ways the withdrawn route crammed.
3. Capture: fill source and per-song gate outcome into the debug
   bundle, so the eyeball can be attributed.
4. Offline first: the replay harness on the 17-song corpus plus the
   16-song word cohort, then Ken eyeballs the filled lines. Raw tables
   to the Results log; no verdicts.

**What this phase must not do without Ken re-opening a ruling:** make
the sidecar a **DP candidate** (a witness the matcher scores against
transcribe/ytasr/energy). LRCLIB is banned from the DP because it is
the held-out tuning reference (`matcher-accuracy-hardening.md`); the
sidecar is not that reference, so the circularity argument may not
apply to it, but the ban is written source-agnostic and both Fable
rounds of 2026-09-08 named the candidate form as the un-priced next
build. Flag it at the design pass; do not assume it.

**Cheap evidence already on disk, optional:** the stratified fallback's
fixed look-list (`m6/fb_looks.json` in the Build-session scratchpad)
holds 30 lines the scaffold rendered and the joint route hid on nine
dirt-free songs. Scored "sung lyric shown when sung", they are what
this phase would fill; scored "wrong time" or "filler", they are what
its gates must reject. Viewing them needs no pre-registration change.

**Gate:** Ken; letter assigned when the design is written. Hard
criterion, inherited from GATE L2: no filled line may be a cram, a
duplicate, or off-sheet dialogue on the eyeballed set.

## Out of scope

- Section-level DP build (gated behind GATE P, own plan).
- S-C SRT aligner switch (`route-srt.md` / `ctc-sync-engine.md` own
  it; `ctc_align.py` is written so the S-C switch can consume it — one
  CTC implementation, two consumers). Scaffold-route work is not out of
  scope but **closed** (2026-09-08); its one surviving idea is Phase 5.
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
box was not reachable this session. Full suite under `uv run python -m
pytest`: **1512 passed, 4 failed, 2 skipped**; all four
failures reproduce with this phase's changes stashed
(`test_genius.py::test_write_overwrites_existing`, two
`test_pipeline_stem_worker.py` cases, one `test_whisper_worker.py`
case) and are Windows-platform issues — file-overwrite semantics and
multiprocessing pipe teardown. `test_joint_match.py`: 62 passed (59
pre-existing unmodified + 3 new). Pre-commit on the two changed files:
clean.

*Correction (same day):* this entry first recorded `libmpv` as absent
on this box, with the suite run under an `mpv` import stub. That was
wrong. `libmpv-2.dll` is hand-placed at `.venv/Scripts/` (118 MB, lost
on a `.venv` rebuild); invoking `.venv/Scripts/python.exe` directly
fails at collection because `python-mpv` reads `%PATH%` at import and
only `uv run` puts `.venv/Scripts` on it. The stub was unnecessary.
The counts above are unchanged and were re-verified stub-free under
`uv run`.

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

### 2026-09-01 — GATE P read-off (Fable) — NO-GO, monotonic DP stands

**(Fable executing the GATE P read-off against the Phase 4 table above
plus the driver's per-song pair/gap-line detail. Recorded here at Ken's
instruction.)**

**Verdict: NO-GO — keep the monotonic DP as-is.** The headline numbers
look prevalence-material at first glance (211/1010 lines with gap >
0.5, 57 inversions, 15/18 songs carrying at least one), but the detail
record shows the mass is not produced by sheet-section reordering. It
comes from two mechanisms a section-level DP would not fix — and one it
would actively make worse.

**1. The dominant signature is repeat cross-attraction, not
permutation.** In song after song the "better" unconstrained candidate
for a late line is an earlier occurrence of the same repeated text —
exactly the chorus-steal the monotonic DP exists to refuse.

- *Free*: the flagged lines' argmax sits at a near-constant offset
  before their selected times — two clusters at ~69 s and ~96 s, i.e.
  chorus-to-chorus spacing. The gaps are tiny (~2.0), meaning the two
  occurrences score nearly identically, which is what duplicate text
  looks like.
- *Belle*'s 251.84 s "inversion" is the final reprise line matching the
  opening occurrence (argmax 33.86 s vs selected 289.94 s). *Defying
  Gravity*'s closing lines (85, 88) point back to the ~57 s hook.
- Many distinct lines collide on a *single* argmax timestamp: eight Man
  Out of You lines all argmax at 77.68 s (the chant), HUNTR/X lines
  33/35/37 all at 54.54 s, Bloodstream lines repeatedly at
  133.84/160.39/222.92 s. Many-lines-to-one-moment is repeat pileup
  (the existing diagnosis), not a coherent relocated section.
- The inversion count is inflated by this: Man Out of You logs the
  *identical* pair (210.08 → 141.44) three times at different line_ids,
  and Bloodstream logs 222.92 → 113.079 twice — repeated sheet text
  re-triggering the same argmax pair. The distinct-event count is well
  under 57.

**2. The big gap mass sits on the two known drift-signature songs.**
Bloodstream (164.38) and HUNTR/X (127.00) alone carry 43% of the corpus
gap total, and both were already flagged by the S-B arm for
lyric-version drift. Their unplaced blocks (Bloodstream 44–50, HUNTR/X
40–52) are sheets that do not match the audio version — the lever there
is upstream lyric-version/length matching per the repeat-pileup
diagnosis, not DP ordering. A section-level DP cannot place a section
the audio does not contain.

**3. No case fits the pattern a section-level DP is for.** A genuine
permutation would show a contiguous block whose alternatives form a
coherent monotone run at another location with decisively better
scores. Nothing in the detail matches that; the closest candidates
(NSYNC Paradise 11–12 vs 31–38, Girl in the Bubble 11–12 vs 29–30) are
*symmetric* cross-pointing between two occurrences of repeated text —
the repeat signature, not a swap. Meanwhile the clean tail (Stay Gold
0/0, In Summer 1.0/0) shows the monotonic DP costs essentially nothing
where the sheet matches the audio.

**Framing point recorded with the verdict:** the probe's "gap" is
measured against the unconstrained argmax, which on repeated text is
frequently the *wrong* occurrence — so much of the measured "cost" is
the defence working correctly, and the totals are an upper bound on
real cost.

**Caveats carried forward, none verdict-changing:** the 17-vs-18
denominator discrepancy the executor flagged remains uninvestigated;
and the inversion walk's filtered-adjacency reading counts *more* pairs
than the alternative reading, which only strengthens NO-GO.

**Consequences.** Phase 4 closes with no code change beyond the
telemetry already committed (`feat(joint): monotone-discard + inversion
telemetry`), which stays in as a standing instrument. No section-level
DP plan is commissioned; the 1:1 `line_objects` contract is not
disturbed. The measurement block advances to step 2, Phase 2b / GATE R
in `plans/PROGRAM.md`. Recorded as a lever this probe
points at, not commissioned here: upstream lyric-version/length
matching for the drift-signature songs.

### 2026-09-08 — Program redirect (Ken) — the line route is closed; this lane is the live build; 1.1 cancelled, 1.2 done, Phase 5 added

Ken ceased work on the scaffold/line route on 2026-09-08 after a Fable
assessment (recorded in full as the closing entry of
`plans/route-line-timing.md`). Consequences for this plan, all recorded
in the sections above: Phase 1.1 is cancelled and the LRCLIB fill stays
(its deletion rationale was conditional on the line route); Phase 1.2
was built as `2516ca8`; Phase 2a → GATE J1/J2 is the program's next
spend; Phase 5 (line timing as a fill source) is added, design owed
after J1; GATE L is re-homed here from the line route. No code changed
in this commit. Nothing about GATE J1's read-off rules changed.

### 2026-09-08 — Phase 2a (CTC-in-joint offline A/B), Windows box — raw tables, no read-off

Ran by a scratchpad driver on the `replay_ytasr_third_source.py`
chassis, extended per this plan's Harness section. Cohort: **all 18
genius-origin bundles** in the library (34 total; the other 16 are
uploader-SRT songs that run the cue-align route). No song was skipped
and no song raised. Output is the tables below; **GATE J1 and GATE J2
are Ken's/Fable's read-off — none is taken here.**

**Arms.** Both arms differ in exactly one input, the align word
stream; transcribe stream, ytasr stream, spans and knobs are the
bundle's throughout. All 18 bundles carry identical recorded knobs
(alpha 2.0, beta 2.0, margin 0.3, max_edit_ratio 0.75, lookahead 3,
anchor_fallback on), so no sweep was run and the arms are compared at
the shipped defaults.

- **Arm A** — the bundle's captured whisper `words` (refine output).
- **Arm B** — full-song MMS_FA forced align of the bundle's
  `align_lines` flat token stream, one timed word per surviving token.
  Recipe imported from the committed `phase1b_score_oracle.py`
  (model / `get_emission` / align) with `sb_ctc_adapter.py`'s dual
  bookkeeping, so an OOV token drops from the tokenizer input but every
  surviving token keeps its raw text and `_line_align_ranges` re-derives
  the line mapping by text exactly as it does for whisper. Stem:
  dereverb where cached, else wet vocal — **17 of 18 ran on the wet
  vocal**, only *Wicked — For Good* had a dereverb cache. Emission cache
  keyed by stem *and* stem kind so a wet emission cannot serve a
  dereverb request.

**Fidelity limits, both this plan's own rulings, applying to both
arms equally:** the evidence veto is not replayable offline and is
skipped in both arms; the windowed re-align spans replay from their
captured whisper span words in both arms, because emission-slice
re-decode inside the re-align is out of scope for Phase 2a. Span
boundaries and the suspect set were chosen from the original pass-1 and
do not move here.

**Reference.** Held-out LRCLIB, resolved by the chassis's existing
three tiers (bundle `.lrc`, then the flat `lrclib/<stem>` cache, then a
live search). It is scoring-only and never enters either matcher. The
`bail` column carries the LRCLIB scorer's own reliability flag; two
songs are flagged in one arm only (*HUNTR_X* in A, *Seasons of Love* in
B), so those two rows are not arm-comparable at all.

**Companion column (flagged for Ken, not pre-registered).** The
H-resync table's `*_raw` columns are the pre-registered metric. The
`*_corr` columns repeat it with that arm's own median offset from the
same LRCLIB fit subtracted, and inherit that fit's bail flag. Both are
kept in the record. *(The J1/J2 read-off below recommends keeping the
companion, labelled and never promoted: it is the only column that
measures the hypothesis' quantity against a reference with a constant
lead, and it is what exposed the Paradise region.)*

**Environment.** Windows dev box (uv `.venv`, RTX A2000), library
`d:/shared/pikaraoke-songs`, synced with the Linux box by Ken this
session. No production code was changed or read differently by this
run: the pace figures are recomputed harness-side from the production
`_line_align_ranges` over each arm's own token stream, which is the
same quantity `_build_align_candidates` tests. The run is
deterministic — it was executed twice (the second time only to add the
`bail` column to the rendering) and reproduced every figure.

**Artifacts** (session scratchpad, not committed, per this plan's
ground rules): `phase2a_out/main.csv`, `pace.csv`, `hsnap.csv`,
`hresync.csv`, `traces.csv` (per-line offset traces for Defying
Gravity, Hakuna Matata and Man Out of You), `report.txt`, and the
driver `phase2a_ctc_joint_ab.py`.

**Main: per song x arm**

bail: the LRCLIB scorer's own reliability flag on that row's fit -- 'wide' = residual spread past its bail-out, 'few' = too few anchors carried a cue. A flagged mad_s/off_s is not comparable across arms; a row flagged in one arm only is not comparable at all.

```
song                                         arm  plc algn trns ytsr intp   off_s   mad_s  bail  fit  ovl  cand pace!
---------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary    A   51   21   16   14   38 -75.791   7.121  wide   34    1    89    41
'Defying Gravity' - Wicked 20th Anniversary    B   51   20   15   16   38 -76.170   7.500  wide   34    1    89     2
'Free' _ Official Lyric Video _ Sony Animati   A   40    6   34    0    1  -0.130   0.197         16    2    41    24
'Free' _ Official Lyric Video _ Sony Animati   B   41   23   18    0    0   0.055   0.157         16    1    41     0
'Popular' - Wicked 20th Anniversary Edition    A   52   41    3    8   10 -16.590   1.599  wide   28    2    62     7
'Popular' - Wicked 20th Anniversary Edition    B   51   19    9   23   11 -16.160   1.616  wide   28    2    62     0
Beauty and the Beast (1991) - Be Our Guest [   A   77   57   10   10    0  -3.241   0.161         49    0    77     0
Beauty and the Beast (1991) - Be Our Guest [   B   77   47    9   21    0  -3.030   0.150         49    1    77     0
Beauty and the Beast (1991) - Belle [UHD]---   A  101   73   15   13    9  -4.550   0.390         55    2   110     1
Beauty and the Beast (1991) - Belle [UHD]---   B  101   59   24   18    9  -4.416   0.463         52    2   110     0
Ed Sheeran - Best Part Of Me (feat. YEBBA) (   A   37   13    6   18    1  -0.690   0.790  wide   25    0    38     1
Ed Sheeran - Best Part Of Me (feat. YEBBA) (   B   37   12    7   18    1  -0.540   0.770  wide   24    0    38     0
Ed Sheeran & Rudimental­ - Bloodstream [Offi   A   48   26   12   10   26 -11.090   0.600         11    1    74    17
Ed Sheeran & Rudimental­ - Bloodstream [Offi   B   47   14   14   19   27 -10.110   0.420         11    6    74     0
HUNTR_X 'This Is What It Sounds Like' (Music   A   33   30    3    0   20  -0.270   1.605  wide   18    1    43     8
HUNTR_X 'This Is What It Sounds Like' (Music   B   32   15   17    0   21  -0.093   0.553         17    0    53     1
Jessie J - Domino (Official Video)---UJtB55M   A   63   53   10    0    4  -1.614   0.432          7    2    66     1
Jessie J - Domino (Official Video)---UJtB55M   B   61   50   11    0    6  -0.356   0.200          7    2    67     0
Josh Gad - In Summer (From 'Frozen'_Sing-Alo   A   29   26    3    0    2  -0.745   0.220         14    2    31     0
Josh Gad - In Summer (From 'Frozen'_Sing-Alo   B   29   17   12    0    2  -0.485   0.135         14    1    31     0
Mulan _ I'll Make a Man Out of You _ @disney   A   36    3    8   25   11  32.565   1.006  wide   22    0    47    23
Mulan _ I'll Make a Man Out of You _ @disney   B   42   14    5   23    5  32.295   0.974  wide   22    0    47     2
NSYNC - Paradise                               A   53   13   40    0   12  24.045   0.270         10    1    65    27
NSYNC - Paradise                               B   56   27   29    0    9  23.920   0.300         10    1    65     2
Pocahontas - Colors of the Wind (Blu-ray 108   A   37    2   14   21    0  -6.090   0.190         31    0    37    19
Pocahontas - Colors of the Wind (Blu-ray 108   B   37    3   12   22    0  -6.030   0.120         31    0    37     0
Seasons of Love (HD)---UvyHuse6buY             A   25   15   10    0    9  18.580   0.520          5    0    29     3
Seasons of Love (HD)---UvyHuse6buY             B   26   18    8    0    8  18.754   0.961  wide    5    1    34     0
Stay Gold (Official Music Video) from The Ou   A   38   37    1    0    0  -0.094   0.048         19    0    38     0
Stay Gold (Official Music Video) from The Ou   B   38   27   11    0    0  -0.041   0.093         19    0    38     0
The Lion King - Hakuna Matata Music Video I    A   33   12    6   15    7   9.165   0.415          8    2    40     2
The Lion King - Hakuna Matata Music Video I    B   33   12    6   15    7   9.165   0.414          8    1    40     0
The Next Ten Minutes Lyrics---0j8kL24ph8U      A   67   44   23    0    4   0.757   0.456         52    0    71    10
The Next Ten Minutes Lyrics---0j8kL24ph8U      B   70   33   37    0    1   1.130   0.270         51    1    71     0
Wicked - For Good  (2025) 4K - The Girl in t   A   29   10    5   14    7 -23.148   0.388         15    0    30    15
Wicked - For Good  (2025) 4K - The Girl in t   B   33   12    6   15    3 -22.986   0.116         15    0    36     0
```

**Pace distribution, per arm (s/token; guard fires below 0.06)**

```
  arm A: n=988 p5=0.000 p25=0.206 med=0.395 p75=0.590 p95=1.273 min=0.0000 guard_fires=199
  arm B: n=1010 p5=0.110 p25=0.294 med=0.408 p75=0.578 p95=1.522 min=0.0200 guard_fires=7
```

**H-snap: Arm B, |edge delta| the snap would still apply**

```
group                            n   median      p90  %>150ms
align-won onset                422    0.000    0.000      9.2
align-won end                  422    0.000    0.519     22.5
transcribe/ytasr-won onset     440    0.000    0.400     20.9
transcribe/ytasr-won end       440    0.000    0.740     32.3
```

**H-resync: mean |placement start - reference start| after dark regions**

`*_corr` subtracts that arm's median offset from the same LRCLIB fit as the main table, so where that row is bail-flagged there, the correction inherits the flag.

```
song                                         region  nf   A_raw   B_raw  A_corr  B_corr
'Defying Gravity' - Wicked 20th Annivers       0-20   3  68.753  68.753   7.038   7.417
'Defying Gravity' - Wicked 20th Annivers      32-33   3  72.514  72.809   3.277   3.361
'Defying Gravity' - Wicked 20th Annivers      45-46   3  78.164  78.330   2.373   2.160
'Defying Gravity' - Wicked 20th Annivers      56-64   3 122.271 122.251  46.480  46.081
'Popular' - Wicked 20th Anniversary Edit        0-4   3  11.278  11.278   5.312   4.882
'Popular' - Wicked 20th Anniversary Edit      51-54   3  35.378  35.485  18.788  19.325
'Popular' - Wicked 20th Anniversary Edit      59-60   1  40.020  40.020  23.430  23.860
Beauty and the Beast (1991) - Be Our Gue      62-72   3   3.277   2.843   0.396   0.187
Beauty and the Beast (1991) - Belle [UHD      80-87   3   6.110   6.110   1.560   1.694
Beauty and the Beast (1991) - Belle [UHD      93-95   3   5.225   5.225   0.675   0.809
Beauty and the Beast (1991) - Belle [UHD      97-99   3   4.773   4.064   0.417   0.821
Ed Sheeran & Rudimental­ - Bloodstream [        0-1   3  11.225  10.653   0.135   0.543
Ed Sheeran & Rudimental­ - Bloodstream [      27-30   3  50.880  51.550  39.790  41.440
Ed Sheeran & Rudimental­ - Bloodstream [      43-50   1       -       -       -       -
Ed Sheeran & Rudimental­ - Bloodstream [      57-63   1       -       -       -       -
Jessie J - Domino (Official Video)---UJt      41-48   3   0.821   0.821   1.659   0.740
Josh Gad - In Summer (From 'Frozen'_Sing        5-6   3   0.783   0.689   0.485   0.270
Mulan _ I'll Make a Man Out of You _ @di      19-21   3  30.095  31.295   2.470   1.000
NSYNC - Paradise                                0-1   3  23.987  22.984   0.525  15.510
NSYNC - Paradise                              21-22   3  23.797  24.102   0.382   0.182
NSYNC - Paradise                              51-52   3  23.355  23.355   0.690   0.565
Seasons of Love (HD)---UvyHuse6buY            25-26   3  15.086  12.950   3.494   5.804
The Next Ten Minutes Lyrics---0j8kL24ph8      63-66   3   1.350   1.320   0.593   0.190
Wicked - For Good  (2025) 4K - The Girl       32-33   2  21.922  22.442   1.226   0.544
```

### 2026-09-08 — GATE J1/J2 read-off (Fable) — J1 NO-GO, J2 clears nothing; whisper stays the joint aligner

**(Fable executing the J1/J2 read-off against the Phase 2a tables above,
plus per-song re-cuts of the CSVs and bundles. Commissioned by Ken and
recorded here at his instruction. Read-only round: nothing in the repo,
the plan or the artifacts was modified by the judge.)**

Fable first verified the harness against this plan's Harness section —
the arms differ in exactly the align word stream, pace is recomputed
from the production `_line_align_ranges`, H-snap runs the production
`snap_line_edges`, and H-resync's dark regions are read off Arm A as
specified — and found it faithful. Where the results mislead, the
finding is against the pre-registration, not the run.

#### GATE J1 — NO-GO. The plan's NO-GO branch is selected.

**Phase 2b is skipped entirely, GATE V never fires, and Phase 3 sweeps
alpha × beta on whisper align words.** Phase 5 is designed with whisper
as the joint aligner. GATE L re-homes to whisper. Appendix D does not
move. **The verdict is independent of Ken's eyeball**: the criterion is
a conjunction, and the eyeball cannot rescue a conjunction whose first
two terms already fail.

*Conjunct 1 — "wins or ties everywhere material": fails.* The LRCLIB
scorer disowned its fit on six songs, two of them in one arm only, so
12 songs are MAD-comparable; on those, Arm B is better on 7, worse on
3, tied on 2. Not "everywhere" — though whether the three losses are
*material* turns on a tie band **the plan never fixed** (ambiguity
flagged, not resolved; it does not decide the gate). The structural
column does decide it: **consecutive-line overlaps rose 16 → 20**, and
Bloodstream went 1 → 6 with its worst overlap 6.7 s → 13.45 s. GATE C's
C-3 entry had already recorded that song visibly cramming its missing
second hook; Phase 2a reproduced the cram inside the DP. Arm B places
13 more lines and drops interp 161 → 148, but under "hidden beats
wrong" that is a win only if the new lines are right, which this table
does not establish.

*Conjunct 2 — "H-resync shows the claimed recovery": fails.* Of the 24
regions, 2 are unscorable and 9 sit on bail-flagged songs; the 13 that
remain split B 5 / A 3 / tie 5 — parity, not recovery. **Defying
Gravity, the song the hypothesis was written for, is line-for-line
identical in both arms across all four of its dark regions.** CTC
removed whisper's zero-pace collapse signature there, and the DP still
produced the same 38 interp lines, because those regions are sheet text
the video never sings: forced alignment cannot re-sync to audio that is
not there.

*A finding against the pre-registration itself.* On this reference
population the pre-registered `*_raw` metric does not measure the
hypothesis. It is the absolute sum of the reference's constant lead and
the resync error, so wherever that lead dominates it ranks the arms by
*signed* error — an arm can "win" by being wrong in the other
direction. Only three songs have a lead small enough for `*_raw` to
mean what the Harness intended.

#### The 2b pace-guard constant

**Moot on NO-GO, and unselectable anyway.** The plan pre-registers no
selection rule — "set at this read-off from the pace telemetry" is an
instruction to choose, not a procedure — which under the model-switching
rule is an uncovered case and therefore Ken's. What the telemetry does
license: **the shipped whisper guard is well placed; change nothing.**
Arm A's distribution is bimodal with a trough exactly where the
constant sits.

**A pace constant cannot be calibrated for CTC at all.** The aligner
gives every token at least one frame, so a full cram lands just under
the honest-fast-singing band instead of at zero, with no trough between
them. Phase 2b step 3 as written ("set the CTC-calibrated constant
chosen at GATE J1") is **not executable from this telemetry**; a CTC
re-attempt needs an abstention mechanism, not a constant. Fable also
notes there is no *maximum*-pace guard on align candidates, and Arm B's
first line of Man Out of You absorbs the whole intro.

#### GATE J2 — CTC-won lines NOT cleared; transcribe/ytasr-won NOT cleared. Appendix D unchanged.

**The criterion is partly tautological and partly impossible on this
table.** Both snaps carry a minimum shift, so a line either moves past
that floor or does not move at all — "median ~zero" holds automatically
whenever fewer than half the lines fire, and "negative" cannot occur on
absolute deltas. Only the fire rate is informative.

Even on the cleanest available population — the lines CTC placed in
pass-1, outside any replayed span — **the end snap would still move one
line in six**. That is not "~zero", so the snap is not retired on
CTC-won joint lines. Transcribe/ytasr-won lines fire far more and are
not cleared either.

**The "align-won" group is not a clean CTC-timed population**: about
two fifths of it sits inside a replayed span interior where the merge
may have substituted captured *whisper* words — this plan's own
fidelity limit, symmetric between arms but **asymmetric in meaning for
J2**. Those in-span lines fire at rates indistinguishable from the
whisper/caption-timed group, and the harness did not record which lines
the merge replaced, so the record cannot separate leakage from
hard-region difficulty.

**Why Appendix D should not move regardless.** A fire is a *move*, not
a *fix*. GATE C recorded CTC edge timing as already better than the
snap's; if that holds, a 1-in-6 end fire rate on CTC lines is harm at
that rate, not repair. H-snap carries no correctness reference, so it
can neither confirm nor refute GATE C, and Appendix D's locked position
stands untouched by this evidence.

#### An unresolved conflict between two pre-registered rules (Ken)

**GATE J2 puts the burden on retirement** ("retire iff ~zero");
**Appendix D puts it on the snap** ("OFF unless a named flag class is
demonstrably fixed"). On this table J2's rule keeps the snap ON for
CTC-won joint lines and Appendix D's rule keeps it OFF. Moot today —
J1 NO-GO means there are no CTC-won joint lines in production — but the
two rules point opposite directions and this must be settled **before
Appendices C/D/E are re-locked** in the design-consolidation pass.

#### What Ken's eyeball still settles (not contingent for J1)

Each look settles a mechanism claim that shapes Phase 3 and any future
CTC re-attempt. Arm B renders would have to be produced first; the
harness did not write them.

| Song | Look at | Question |
| --- | --- | --- |
| Man Out of You | Arm B line 0; the newly placed lines | Does line 0 sweep the whole intro (boundary absorption)? Are the new lines sung lyric shown when sung? |
| Bloodstream | Arm B's six overlapping lines | Is the cram visible, and is it the missing second hook GATE C named? |
| Paradise | Arm B's first referenced lines after the intro | Is a line displayed during the intro? |
| HUNTR/X | The drift region, both arms | The scorer disowned A but not B; the eye is the only comparator |
| Seasons of Love | The "525,600" chorus lines | B's fit went wide and every dropped token is that numeral — does the chorus visibly degrade? |
| For Good, Free | Whole song, both arms | B's clearest wins — visible, or scorer artifacts? |
| Stay Gold | Whole song | Clean tail; GATE T's hard criterion in miniature |

Defying Gravity and Hakuna Matata need no look: the arms are
near-identical.

#### What the plan did not anticipate

1. **CTC's failure mode is illegible to the guard that protects this
   route.** Whisper fails on unsung sheet text by collapsing to zero
   width, and the guard reads that signature. CTC cannot abstain: it
   compresses unsung tokens into a few frames each, which blends into
   honest fast singing, or smears the boundary line across the unsung
   audio. GATE C saw this on Bloodstream; Phase 2a built no defence.
   **This undercuts the S-3 rider's premise** that CTC is the tool for
   the version-mismatch class — an aligner that cannot say "not here"
   is poorly matched to a population defined by text the audio lacks.
   Any re-attempt must pre-register an abstention mechanism before
   running.
2. **GATE C's two hard constraints for a production CTC adapter were
   not in the 2a recipe.** Nearly all OOV-dropped tokens corpus-wide
   are the classes C-3 named — numerals and hangul — and Seasons of
   Love's one-arm-only wide flag sits on the numeral song. A re-run
   needs spoken-form expansion and a non-Latin fallback. With whisper
   retained, **GATE L's romanized-form question loses its MMS_FA
   motivation for this route** and is worth re-posing when the Mandarin
   corpus exists.
3. **The `*_corr` companion column.** Fable's recommendation: **keep it
   in the record, labelled non-pre-registered supporting evidence,
   never promoted.** It is the only column that measures the
   hypothesis' quantity against a reference with a constant lead, and
   it is what exposed the Paradise region. If H-resync is ever re-run,
   pre-register an offset-corrected form *before* the run.
4. **H-snap pre-registration gaps** for any future run: record per-line
   merge provenance, add an Arm A H-snap as the whisper baseline (none
   exists, so "does CTC need the snap less than whisper" is
   unanswerable from this table), and state a fire-rate threshold
   instead of "~zero".
5. **The arms were compared at knobs tuned on whisper align words.**
   That is the pre-registered design and does not change the verdict,
   but a re-attempt should ride with a Phase 3-style sweep rather than
   shipped defaults, or it re-runs the same handicap.
6. **MAD's reach.** Its fit uses well-corroborated anchor lines, so it
   measures precision on the *easy* lines, not the dark regions CTC was
   meant to fix, and on four comparable songs it rests on fewer than a
   dozen anchors. Directional, not decisive; the verdict does not rest
   on it.
7. **Neither fidelity limit can flip J1.** The skipped veto is
   symmetric and only demotes zero-evidence align lines over near
   silence, so it cannot improve either arm's anchored MAD nor remove
   Bloodstream's overlaps, which sit over sung audio. The captured-span
   replay makes Arm B "CTC pass-1 plus whisper re-align" — which is
   also 2b's own production design — and the decisive failures are
   pass-1 placements or regions identical in both arms. Phase 2a's
   design cannot answer the span question; only the *exposure* is cheap
   to compute, not the answer.

#### Sequencing after this ruling

`PROGRAM.md` step 5 resolves to the NO-GO branch: **Phase 3 (whisper) →
GATE T → Phase 5 design → GATE L.** The emission-slice re-decode
follow-up and the `s_tx_roll5` advisory demote stay out of scope. **The
S-3 rider is a licence, not a mandate; it is not withdrawn by this,
merely unexercised on this evidence.** A J1′ re-attempt — abstention
mechanism, numeral and non-Latin handling, provenance-recorded H-snap
with an Arm A baseline, offset-safe H-resync, knobs swept rather than
fixed — is named here as the option the evidence points at, **not
commissioned.**
