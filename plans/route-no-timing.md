# Joint matcher catch-all refit

Model: Claude Sonnet 5 (executor). Plan drafted by Claude Fable 5.

> **START HERE — the live build lane as of 2026-09-10.** Ken ceased work
> on the line route (S-1 withdrawn; `plans/route-line-timing.md` closing
> entry), so every song without an uploader SRT lands here permanently
> and this plan is the only build lane left. State of the phases:
> **1.1 CANCELLED** (keep the LRCLIB fill — see the note there),
> **1.2 DONE** (`2516ca8`), **4 CLOSED** (GATE P NO-GO), **2a RAN
> 2026-09-08 and GATE J1 is NO-GO** — whisper stays the joint aligner,
> so **2b and GATE V are skipped entirely** and **GATE J2 cleared
> nothing** (Appendix D unchanged). **3 RAN 2026-09-10 and GATE T is
> READ the same day: the alpha/beta knobs are inert on this corpus and
> stay at their shipped 2.0/2.0 — no config default moved and no commit
> carries a knob change.** The one production change out of the phase is
> the **ytasr candidate ratio at 0.45** (`ytasr.CANDIDATE_MAX_EDIT_RATIO`,
> eyeballed and shipped the same day). **Phase 5 is the live head of the
> queue and is now DESIGNED — the design pass ran 2026-09-10 (Opus) and
> pre-registered the mechanism, the constants, six offline cells, the
> tables and the read-off as GATE G. What is owed is an executor session
> to build it and run the cells, then Ken's eyeball.** Then **Phase 6**
> (CTC post-selection interior refinement, design owed), then GATE L
> when the Mandarin corpus exists. Sequencing lives in
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
  ~~3 → GATE T~~ → 5. *(2026-09-08: 1.1 cancelled, 1.2 done, 4 closed at
  GATE P; Phase 5 added; 2a ran and GATE J1 came back NO-GO, so 2b and
  GATE V are struck and Phase 3 became the head of the queue. 2026-09-10:
  **Phase 3 ran and GATE T was read the same day — knobs unchanged, no
  commit. Phase 5 is the head of the queue, designed the same day and
  gated as GATE G**.)* Phase 4
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
  tables only, **no verdicts**. Gates are read off by Opus, Ken rules
  (`PROGRAM.md` §"Model switching", revised 2026-09-10); stop and alert
  at every GATE.
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

*Status (2026-09-10): **RAN, and GATE T is READ — the knobs stay at the
shipped `joint_alpha` 2.0 / `joint_beta` 2.0, no config default moves,
no commit carries a knob change.** The grid is inert on this corpus (7
placed lines move across all 15 points, and every song above 90%
coverage is identical at every point), so the hard criterion cannot
fail and the clean-tail roster flagged below turned out **not** to be a
prerequisite. **One production change came out of the phase**: the ytasr
candidate ratio ships at 0.45, eyeballed by Ken on the two lines it adds
and recorded in the read-off. Read-off by Claude Opus 5 at Ken's request
(Fable credits short), ruling by Ken — see the read-off entry in the
Results log. The run record follows.*

*Run status: All four steps executed
on all 18 genius-origin bundles; raw tables in the Results log below.
Two deviations, both recorded there: step 2's "best 3 grid points" was
run as **the full grid at each of the three ratios** on the
ytasr-carrying subset, which is strictly more data and avoids the
executor picking the three points; and the tables are the **full
per-song x per-combo grid** rather than the chassis' one-best-combo-per-song
output, whose `min()` tie-break is the recorded sweep-reading trap. No
combo is selected here and no config default is changed. ~~**One input
GATE T's hard criterion needs does not exist yet: the clean-tail roster
has never been written down as a list**~~ — the record names Stay Gold
and In Summer as clean tail and Bloodstream and HUNTR/X as
version-drift, leaving 14 songs unclassified. **Superseded by the
read-off: the roster is not a prerequisite for this gate**, because no
song that could plausibly be called clean tail moves anywhere in the
grid, so the criterion is satisfied by every combo. The struck claim is
kept because it was the executor's flag at hand-off and the correction
belongs beside it. Assigning the 14 is still Ken's if Phase 5 wants
them.*

## Phase 5 — line timing as a fill source (designed 2026-09-10; GATE G)

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
   word sidecars contribute their line `ts`/`te`), under the
   fill-only contract. Source precedence when both exist is a design
   question; do not answer it by intuition. **Not under the same
   gates** — see 2 below.
2. **Per-gap gate (Fable, 2026-09-10; design owed, not ratified).**
   The shipped fill's eligibility is a *per-song* offset+slope fit,
   which carries the warp gate's verified blind spot: a global fit's
   population never sees the unsung sections, so a cut section is
   invisible to it. Today the damage is capped by never overriding a
   placed line, but that cap does not cover the one case this phase
   creates — a run of *unplaced* lines after a structural discrepancy
   on a song that passes the global gate. Collision only checks placed
   spans, so where the matcher hid the region there is nothing to
   collide with and the fill can land a cut section's lines over audio
   singing something else. Named candidate on the numbers already on
   file: Bloodstream (clears both global gates, STRUCTURAL by the
   fallback's shape diagnostic, EDIT by M7-a, seven-line unplaced
   block; its arm-A MAD is not on file). Widening the source to a
   population M7-a says is majority wrong-edit, under the gate that
   earned 16/0 on a population it was validated on, is where that
   record gets tested and can fail.
   **The proposed form:** gate each unplaced line on its *bracketing
   corroborated anchors* (the ones `plan_fills` already computes) —
   fill only if the audio gap and the sidecar gap agree in length
   within a tolerance, place at the local offset (slope 1), and never
   extrapolate past the anchor envelope, which generalises "never fill
   past the media ends" and is what refuses Domino. Rationale: a cut
   verse or an added repeat is a multi-second gap disagreement while
   anchor jitter is sub-second — a trough, unlike the per-song signals
   that failed. Tolerance in **absolute seconds, not a slope ratio**
   (a ratio on a short gap with normal anchor error rejects
   everything). Substituted content of equal length (Da-dum) still
   passes; nothing timing-based catches that and the fill study said
   so. Relation to the shape diagnostic: same quantity, undiluted —
   that diagnostic caught 2 of 5 because one cut is diluted across a
   whole-song fit. That is a testable difference in resolving power,
   not a relabel; it is what the probe in item 5 measures.
3. Never fill past the media ends, never over an audio-placed line —
   the two ways the withdrawn route crammed.
4. Capture: fill source and per-song gate outcome into the debug
   bundle, so the eyeball can be attributed.
5. Offline first: the replay harness on the 17-song corpus plus the
   16-song word cohort, **two arms — global gate as shipped vs the
   per-gap gate of item 2** — then Ken eyeballs the filled lines.
   *(Superseded by the design below: three settings on the gate axis,
   not two. Same run, one added cell.)* Raw tables to the Results log;
   no verdicts. Pre-register before the
   run: the tolerance, the anchor definition (reuse `plan_fills`'), and
   GATE L2's bar — `bad_surviving = 0` on the eyeball, and **the 16
   existing good fills must survive unchanged**. Read off additional
   fills on the 13 non-certified songs plus Ken's verdict on each.
   **Scoring rider (Fable, 2026-09-10):** score sidecar work against
   the M7-a caption reference or structural metrics plus eyeball,
   never against the held-out LRC — "not LRCLIB" is not "independent
   of LRCLIB", since Musixmatch and LRCLIB may share provenance for a
   given song, so a sidecar scored against held-out LRC can be
   correlated without being circular by name.

### Design — pre-registered (Opus, 2026-09-10). Gate letter: **GATE G.**

Everything in this section is fixed before the run. The executor
implements it, runs it, reports the tables, and stops. No constant here
moves during execution; a case the read-off does not cover is a
**STOP → Ken**. Design-time evidence for the numbers is the Results-log
entry of 2026-09-10 ("Phase 5 design pass"), which is a **proxy** read
off bundles on disk, not a measurement of this gate.

**1. Cue sources.** Both reduce to the same `{line_id: (start, end)}`
mapping, so this is a provider swap, not a rewrite.

- *LRCLIB* — as shipped (`lrclib.cue_spans_for_lines` on the `.lrc`).
- *Sidecar* — `lyrics/<stem>.timing.json`, admitted iff
  `kind ∈ {word, line}` **and** `map_rate ≥ 0.5`
  (`timing_fetch.WRONG_SONG_MAP_RATE`, the bar the fetch stage already
  applies before it stashes an artifact — **no new constant**). Word
  bodies contribute each entry's line `ts`/`te`.
  `scripts/scaffold_align_song.py:sidecar_scaffold_cues` already builds
  this mapping for either kind and is the reference implementation;
  reuse it rather than writing a second parser.

`plan_fills` therefore takes the **mapping**, not `synced_text`. That is
the whole of item 1's widening.

**2. Anchors — unchanged.** `windowed_realign.analyze_pass1`'s anchors
as `plan_fills` already computes them (`ANCHOR_MIN_TOKENS` 4 tokens,
line text unique in the sheet, transcribe corroboration ≥
`ANCHOR_MIN_RATIO` 0.75), restricted to those that also carry a cue in
the source under test. No new anchor definition.

**3. The per-gap gate.** For an unplaced candidate line `L` with cue
start `c(L)`:

- Bracketing anchors: `A_lo` = last anchor-with-cue before `L`, `A_hi` =
  first after. **Either missing → refuse (`no_bracket`).** This is
  "never extrapolate past the anchor envelope"; it is what refuses a
  fill dangling off the last anchor, and it generalises "never fill past
  the media ends".
- `gap_audio = A_hi.start − A_lo.start`,
  `gap_cue = c(A_hi) − c(A_lo)`.
  **Refuse (`gap_disagree`) if `|gap_audio − gap_cue| > FILL_GAP_TOL_S`.**
- Otherwise place at **slope 1** with
  `local_offset = ((A_lo.start − c(A_lo)) + (A_hi.start − c(A_hi))) / 2`
  — the mean of the two bracketing residuals, which minimises worst-case
  error across the bracket and needs no fit. `t0 = c(L) + local_offset`,
  `t1 = c_end(L) + local_offset`, then `_fill_line`'s existing pace caps
  (`MAX_FILL_WORD_DUR_S`, `MIN_FILL_DUR_S`) unchanged.
- **Refuse (`outside_envelope`)** if the constructed span is not wholly
  inside `[A_lo.start, A_hi.end]`.

**4. Every shipped per-line gate still applies, unchanged**: negative
start, collision against placed spans at `COLLISION_TOL_S`, energy
`PASS`, never over a placed line, fill-only (a placed line is never
moved). The per-gap gate only ever **removes** fills relative to the
same source under the global gate — which is what makes "the 16 must
survive" a one-sided read.

**5. The tolerance.** `FILL_GAP_TOL_S = 2.0` seconds, **absolute, not a
slope ratio** (a ratio on a short gap with normal anchor error rejects
everything). Two reasons it is 2.0 and not a fitted number: it reuses
the scale already in this module (`WARP_MAD_GATE_S = 2.0`), and the
design-pass proxy found the choice barely matters — across the whole
range 1.0–3.0 s the survivor count moves on **6 of the 20 song-source
pairs that have any candidate**, by 1–4 lines, because bracket
disagreements on this corpus are either sub-second or many seconds. The executor reports the {1.0, 1.5, 2.0, 3.0} sensitivity as a
**diagnostic column**; the shipped value does not move without Ken.

**6. Source precedence** (item 1 left this open, correctly, as not to be
answered by intuition). With a per-line gate it stops being a global
choice:

- *Per-gap cells* — **per line**: consider every source that has a cue
  for `L` and clears the gate; if more than one qualifies, take the
  smaller `|gap_audio − gap_cue|`; exact tie → LRCLIB (the incumbent
  with the 16/0 record). No new constant, and the tie-break is the same
  quantity the gate already measures.
- *Global-only cells* — **per song**, since no per-line statistic
  exists there: the source with the lower arm-A MAD; tie → LRCLIB.

**7. Provenance.** `source` becomes `lrclib_fill` **or** `sidecar_fill`.
Any consumer asking "is this a fill" must test the set, never the
literal string — flagged because Phase 6 pre-registers "skip fill
lines". The per-line stats record gains `source` and the gate fields
(`bracket_lo`, `bracket_hi`, `gap_audio`, `gap_cue`, `gap_delta`,
`local_offset`) so every fill is attributable in the bundle (item 4).

#### The cells

Two axes, six cells, one offline run — replay-only, no GPU. `A0` is the
shipped path. *(This supersedes item 5's "two arms": same experiment,
one more setting on the gate axis, because the proxy says the global
gate — not the per-gap gate — is what currently withholds the prize.)*

| cell | cue source | gate |
| --- | --- | --- |
| **A0** | LRCLIB | global (shipped) — the reproduction cell |
| **A1** | LRCLIB + sidecar | global — **the named risk cell** |
| **A2** | LRCLIB | global ∧ per-gap |
| **A3** | LRCLIB + sidecar | global ∧ per-gap — **the proposal** |
| **A4** | LRCLIB | per-gap only |
| **A5** | LRCLIB + sidecar | per-gap only |

**A4/A5 drop a shipped gate**, so they are measured and reported, never
adopted inside this gate — retiring the global fit is Ken's ruling
alone. They are in the run because they cost nothing and because the
proxy suggests that is where the unreached lines live.

#### Corpus, and three provisioning traps that void the run if missed

The 18 genius-origin bundles under the library root (Windows box:
`D:/shared/pikaraoke-songs`), on the `replay_ytasr_third_source.py`
chassis at the shipped knobs (`joint_alpha` 2.0 / `joint_beta` 2.0 /
`ytasr.CANDIDATE_MAX_EDIT_RATIO` 0.45).

- **The fill needs audio.** `_energy_check` needs the envelope, and the
  replay chassis deliberately never touches audio. Decode it per song
  with `onset_snap.decode_env_db` off the stem this plan's ground rules
  name — `dereverb/` when present, else `vocal/` (CPU, no GPU). A cell
  run with `env = None` fills nothing and is not a result.
- **The LRC tier matters.** Only one song has a `.lrc` beside it on the
  Windows box; the rest are in the flat `lrclib/<stem>` cache, which is
  the harness's tier 2 (`_load_lrclib_reference`) and not the
  production resolver. Use the harness's resolution order and **record
  which tier supplied each song**, or A0 will not reproduce production.
- **Domino's LRCLIB variant is on neither tier on this box**, and Domino
  carries 1 of the 16 good fills. Provision it (the harness's tier-3
  live fetch already does this) before the run. If it cannot be
  re-fetched, the roster check runs on **15 of 16 with Domino named** —
  that is an artifact-provisioning fact, not a behaviour change, and not
  a STOP.

#### Tables the executor reports (tables only, no verdicts)

1. Per song × cell: eligible / bail reason, candidate count, fill count,
   filled lids, and the histogram of per-line refusal reasons
   (`no_bracket`, `gap_disagree`, `outside_envelope`, `negative_start`,
   `collision`, `energy`).
2. **The 16-good roster** (`plans/completed/lrclib-fill-absence-study.md`
   — Belle 5, Girl in the Bubble 5, Next Ten Minutes 3, NSYNC 2,
   Domino 1): present / absent / moved per cell, times to 3 dp.
3. Every fill in the union of cells that A0 does not already produce:
   song, lid, text, source, cells, `t0`/`t1`, bracket lids, `gap_audio`,
   `gap_cue`, `gap_delta`, collision, energy.
4. Tolerance sensitivity at {1.0, 1.5, 2.0, 3.0} — fill counts per song
   per cell, diagnostic only.
5. **Bloodstream's unplaced block**, called out separately: which cells
   fill it, at what `gap_delta`. Named risk case.
6. **Whether Bloodstream clears the global gates with real anchors.**
   The 2026-09-10 Fable round records that it does; the design-pass
   proxy (pseudo-anchors) says arm B bails `wide_spread`. Real anchors
   settle it — report the arm-A/arm-B numbers per source, do not
   reconcile the two claims in prose.

Eyeball packet: per song, a diff `.ass` rendering only the fills that
differ from A0, plus a text list of line/time/source. Ken returns
good / bad / unsure per fill.

#### The read-off (pre-registered; executed by Opus, ruled by Ken)

**Validity first.** If **A0 does not reproduce the 16-good roster**
(15 with Domino named, per the trap above), the harness is not faithful
to production and the whole read is **void → STOP → Ken**. Nothing below
is read.

A cell **PASSES** iff all three hold:

- every roster fill it should carry is present with identical times;
- `bad_surviving = 0` on Ken's eyeball of that cell's fills — GATE L2's
  bar, inherited; and
- no fill lands inside Bloodstream's unplaced block unless Ken calls
  that fill good.

Then, in order:

1. **PASS(A3) and not PASS(A1)** → adopt the widened source **with** the
   per-gap gate. This is the phase's hypothesis and its expected shape.
2. **PASS(A3) and PASS(A1)** → the per-gap gate cost nothing, so adopt
   A3 anyway — *unless* A3 loses a good fill that A1 has, which is a
   live trade → **STOP → Ken**.
3. **PASS(A1) and not PASS(A3)** → the per-gap gate dropped good fills
   and the global gate alone was clean. Report; adopting A1 is Ken's
   ruling, since A1 is the cell this phase exists to distrust.
4. **Neither A1 nor A3 passes** → the widening does not ship and the
   LRCLIB-only fill stays exactly as it is. Then, separately: if
   PASS(A2) and A2 ≠ A0 and A2 loses no good fill, the per-gap gate
   ships on the LRCLIB source alone.
5. **A4/A5** are reported for the record in every branch. Adopting
   either retires the global fit and is Ken's alone.
6. **A cell with fewer than 5 fills that A0 does not already produce is
   reported, not read** — there is nothing to see (mirrors Phase 6's
   under-8-looks rule). If that empties branches 1–3, say so plainly:
   the corpus did not exercise the question.
7. **Anything not covered above → STOP → Ken.**

**Compliance with the scoring rider (item 5).** Nothing in this read-off
scores a sidecar fill against the held-out LRC. The bar is Ken's eyeball
plus the roster check; LRCLIB appears here only as a *cue source* the
fill already ships with, never as a reference the widened source is
graded against.

#### Not in this phase

No matcher change; no DP candidacy (see the paragraph below, unchanged);
no new fetch — every sidecar this phase reads is already on disk; no
change to `source` semantics beyond the second fill tag; no knob
re-tune (GATE T closed that).

**What this phase must not do without Ken re-opening a ruling:** make
the sidecar a **DP candidate** (a witness the matcher scores against
transcribe/ytasr/energy). LRCLIB is banned from the DP because it is
the held-out tuning reference (`matcher-accuracy-hardening.md`); the
sidecar is not that reference, so the circularity argument may not
apply to it, but the ban is written source-agnostic and both Fable
rounds of 2026-09-08 named the candidate form as the un-priced next
build. Flag it at the design pass; do not assume it. **Priced
2026-09-10 (Fable) — assessment only, the ban and any ruling remain
Ken's; detail in the Results log entry of that date.** The short form:
the candidate is *downstream* of the per-song offset fit rather than an
alternative to it (raw sidecar windows land in the wrong second on most
songs even when the edit is right); where the line is sung a transcribe
candidate already exists at the same spot on the same evidence, so the
sidecar adds a window and no evidence, and out-scores that candidate
only by being **wider** — a smear that displaces an audio-placed line;
uncorroborated sidecar windows score zero and never enter the DP chain,
so the form is inert rather than harmful there; the second pass strips
sidecar-won lines as uncorroborated anyway, so making them stick means
letting a wrong-edit source define span boundaries; and the
agreement-*term* variant tips repeated-text disambiguation toward the
sidecar's edit, helping the minority of sound songs and hurting the
majority, on exactly the class GATE P found the monotonic DP currently
gets right.

**Cheap evidence already on disk, optional:** the stratified fallback's
fixed look-list (`m6/fb_looks.json` in the Build-session scratchpad)
holds 30 lines the scaffold rendered and the joint route hid on nine
dirt-free songs. Scored "sung lyric shown when sung", they are what
this phase would fill; scored "wrong time" or "filler", they are what
its gates must reject. Viewing them needs no pre-registration change.

**GATE G** (letter assigned 2026-09-10 with the design). Read off by
Opus against the pre-registered rules above; **Ken rules**, and the
eyeball is his. Hard criterion, inherited from GATE L2: no filled line
may be a cram, a duplicate, or off-sheet dialogue on the eyeballed
set.

## Phase 6 — CTC post-selection interior refinement (design owed; after GATE T)

Added 2026-09-10 on Ken's question, assessed by Fable the same day.
**Assessment only; no gate letter, no ruling, nothing built.**

**This is not GATE J1's question and must not be read as re-opening
it.** J1 tested CTC as the *aligner* — a candidate source that decides
where a line goes. This form runs strictly *after* selection: the
matcher places the line on audio corroboration, and CTC is asked only
where the word boundaries fall inside a span that is already decided.
The two J1 failure modes are global (boundary-line smear across unsung
audio; cram at collapse points) and a slice constrained to a selected
window cannot reach audio outside it. `sb_ctc_adapter.make_slice_align`
already implements this contract against the cached per-song emission,
so it is one decode per song and near-free per line.

**The population it targets.** Not align-won lines. On transcribe-won
and ytasr-won lines the rendered words are the ASR stream's own words
mapped onto sheet tokens with unmatched runs interpolated
(`_materialise_line_objects` → `_build_line_object`,
`candidate_match.py:226-271`) — the sheet tokens were never directly
timed against audio and there is no 1:1 guarantee. Those are roughly
half the placed lines in Arm A and fire the snap 21–32% vs 9–22% for
align-won. The interpolated runs inside align-won lines
(`_fill_unmatched_runs`) are the same gap in miniature.

**Prior evidence not to re-derive: S-C already ran the hard half.**
CTC was run constrained to a window with correct text (uploader cues,
16 songs, 2026-07-20, `route-srt.md:139-204`) and Ken's eyeball
rejected it for a failure that lives *inside* a correct window —
tighter word timing but worse on genuinely overlapping voices, which
whisper separates better (Mirrors; and the reframe that a CTC overlap
reading 0.0 may be under-reporting a second voice). Windowing does not
remove that mode. On this corpus it lives on the Disney ensemble
numbers and the wet-vocal songs GATE O's `s_tx` false-flagged.

**The gate form.** "Adopt only where CTC agrees with the matcher" is
self-defeating — it adopts where nothing changes and rejects where the
value is. It has to be a **bounded-disagreement band**. Granularity,
corrected by Fable against the executor's first reading: **detect per
token, act per line.** A dropped sheet token takes one frame, and no
honest sung syllable is that short — a 3–4x separation; it is
*line-level averaging* that erased the trough in J1 (a partial cram
averages back into the honest band). So the cram case is answered by
the one CTC abstention signal in this program that has a trough. What
survives is the inverse — extra *audio* inside the span forcing a
sheet token to widen, where wide tokens are also honest holds (no
trough, but harm bounded to one boundary moving by an interjection's
length on a line whose incumbent error is the same order) — plus the
S-C ensemble mode, which is displacement into the other voice's
phonemes and is what the band and the eyeball are for.

**Interior-only is the default to pre-register.** Endpoint refinement
is smear-prone *by construction* on exactly the population it targets:
the selected span on a transcribe-won line runs up to three ASR words
wider than the line's audio at the edges (the `find_candidates` slack),
`_build_line_object` starts the line at the first *matched* word, and
CTC constrained to the raw window would smear token 0 back over them.
Interior boundaries are largely immune.

**Ken's snap ruling (2026-09-10) makes interior-only the *coherent*
default, not merely the cautious one.** The edge snap stays and **owns
line edges** on every line of this route — a post-pass that does not
cover the whole song cannot retire a mechanism that does (full ruling
in the Results log entry of that date, and in `plans/PROGRAM.md`). So
the division of labour is fixed: **the snap owns edges, this phase owns
word boundaries strictly inside a line.** The two never touch the same
values, which is why no per-line snap exception is needed and why the
after-the-snap ordering below is right rather than merely safe. It also
retires the endpoint form on its own terms — with the snap permanently
owning edges, endpoint refinement would be a second mechanism fighting
it over the same numbers, not a blocked-but-attractive option. Recorded
for completeness: were it ever revisited, its ceiling is measurable
against the 16 uploader SRTs, which are human-timed line edges on our
own clock.

**Measurement.** Endpoints have a reference (those cues); **interiors
have none on this corpus** — held-out LRC is line-start only, richsync
intra-line proportions are foreign-clock and too thin to gate on
(sanity column at most, under the provenance rider above), and
structural metrics do not move under a pass that never changes
selection. The eye is the reference. Free screening statistic, not a
gate: on the ytasr-having songs, transcribe-won lines have a second
same-clock word witness, so "does refinement reduce median |word −
ytasr| on transcribe-won lines" costs nothing and is the matcher's own
epistemology.

**Pipeline position.** After the snap, before the fill splice,
`source` untouched. The veto has already run and keys on `source` plus
`evidence` — leave both alone; running after the snap makes the snapped
span the constraint window and stops the snap overwriting a refined
first interior boundary (`onset_snap.py:237-248` edits an interior
boundary when it carries duration forward). Skip `interp`, veto and
fill lines — a fill was never audio-placed. Stamp refinement
provenance in its own field and in `joint_stats`, never in `source`,
which encodes selection.

**Costs, in the order they bite.** (1) *The problem is unmeasured* —
the evidence that these interiors are poor is edge-snap fire rates
(edges) and a docstring. (2) *A zero-model competitor exists in the
bundles today*: on a transcribe-won line whose whisper align range did
not collapse and agrees, whisper's refined per-word timings are already
present — one conditional in `_materialise_line_objects`. CTC's
marginal population is then only the lines whisper *falsely* abstained
on with transcribe corroborating. Note the ambiguity to design around:
`_range_agreement` returns 1.0 for any window containing a collapsed
instant, so agreement alone does not distinguish the abstention case —
the pace guard must be consulted too. (3) MMS_FA in production — a
second model and CUDA co-residency with the whisper worker; GATE C's
C-3 constraints degrade gracefully here (OOV numeral interpolates as
today, hangul skips the line) rather than breaking lines as they did
for the aligner form. (4) `output_line_timings` carries line
start/end/n_words only, so **per-word timings are not in the bundle**
and the replay harness cannot see this pass's effect without adding
them; a run-affecting change to rendered word timing is a milestone
bump by the v8 precedent, i.e. a full-library regen.

**Probe order, with kill rules (pre-register, then run):**

1. **Population split, no GPU** (bundles): transcribe/ytasr-won lines
   partitioned into whisper-agrees (non-collapsed range, agreement ≥ τ,
   τ declared) vs whisper-abstained. Read-off: the zero-model form's
   reach and CTC's marginal population size. **Dies here** if
   whisper-agrees covers most of the population — the zero-model form
   ships and CTC is not needed.
2. **Baseline eyeball, 20 blind looks** at *current* transcribe/
   ytasr-won interiors, worse/same/fine, kill threshold N declared
   first. **Dies here** if Ken cannot see a problem in current output.
3. **Disk disagreement distributions, no eyeball.** Per-boundary and
   per-line |CTC − incumbent| on (a) the 16 SRT songs' S-C artifacts vs
   the whisper cue-align output — correct window, correct text, so
   disagreement cannot be selection error — and (b) the 18 joint
   bundles, CTC sliced to each placed line's final span vs the bundle's
   own words. Fixed quantiles plus a pre-declared bimodality statistic.
   **Dies here** if (a) is unimodal with a fat tail: even with perfect
   windows, |Δ| cannot separate correction from failure. If bimodal,
   the band is declared from (a)'s trough and (b)'s excess tail mass is
   the selection-error contribution. Also report the per-token cram
   floor's fire rate (floor declared, e.g. 0.05 s) and the ytasr
   screening statistic. Emission caches: one forward pass per song on a
   miss; the S-C caches may not survive on the Windows box.
4. **Bounded blind eyeball.** Diff `.ass` per song (only refined lines
   rendered or coloured) so Ken watches changed lines, not whole songs.
   Strata declared from step 3 *before any look*: per-line median |Δ|
   bands, "cram-flagged" as its own stratum, and every refined line on
   the ensemble songs. ~10 per stratum, ~50–60 looks, bounded like
   M7's 71. **Blind A/B per look**, current vs refined in randomised
   order with a sealed key — Ken's prior is that CTC is tighter and an
   unblinded look will confirm it. Three-class verdict (better / same /
   worse), "same" counts as not-worse. Read off per stratum at GATE
   L2's bar: adopt a band iff `worse = 0` in that stratum, and the
   band boundary is **the highest stratum that clears**, never a number
   fitted to the looks. A stratum with fewer than 8 looks is reported,
   not read.

Fixed before any run: interior-only; detect per token, act per line;
after snap, before fill; `source` untouched; τ, the band strata, the
cram floor, the look counts and the kill rules. Executor reports
tables; no verdict.

**Sequencing:** after GATE T, **not parallel** — the alpha/beta/ratio
knobs decide which lines are transcribe/ytasr-won, which is this
phase's population, so pricing it earlier prices the wrong population.

**Gate:** Ken; letter assigned when the design is written.

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

#### ~~An unresolved conflict between two pre-registered rules (Ken)~~ — RESOLVED 2026-09-10 (Ken)

*Recorded as it stood, then the ruling.*

**GATE J2 puts the burden on retirement** ("retire iff ~zero");
**Appendix D puts it on the snap** ("OFF unless a named flag class is
demonstrably fixed"). On this table J2's rule keeps the snap ON for
CTC-won joint lines and Appendix D's rule keeps it OFF. Moot today —
J1 NO-GO means there are no CTC-won joint lines in production — but the
two rules point opposite directions and this must be settled **before
Appendices C/D/E are re-locked** in the design-consolidation pass.

**RULING (Ken, 2026-09-10): the edge snap stays. Resolved by scope,
not by picking a burden.** The rules were never in genuine conflict.
Appendix D's clause disables the snap **on CTC-timed routes** — and in
the same clause keeps it on whisper-timed ones. **Phase 6 does not
create a CTC-timed route**: whisper places every line and CTC only
adjusts word boundaries inside the subset that clears the disagreement
band, so Appendix D's OFF clause never reaches this lane and its
whisper-timed clause does. Ken's reasoning, which is the durable part:
**a post-pass that does not cover the whole song cannot retire a
mechanism that does** — the snap is still needed for align-won lines,
interpolated lines, filled lines, band-rejected lines, every song CTC
never runs on, and the entire SRT route.

Consequences: the snap **owns line edges, always**, and CTC owns word
boundaries strictly inside a line, so the two never touch the same
values and **no per-line snap exception is needed**; Appendix D's
locked snap clause **does not move**; J2 is moot on this lane
*permanently*, not merely "today" as written above, since nothing on
the roadmap restores whole-song CTC coverage here; and Appendices
C/D/E are no longer gated on this item, though the re-lock still has
to happen and Appendix D's other locked decisions are untouched. The
OFF clause is **dormant, not wrong** — it wakes if a route is ever
genuinely CTC-timed end to end, and none exists or is planned.

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

### 2026-09-10 — Two Fable rounds (sidecar-as-DP-candidate; CTC post-selection refinement) — assessments, no read-off

Commissioned by Ken after he asked whether the joint matcher could be
improved by the full complement of timings now nominally available to
it — whisper align, CTC forced align, whisper transcribe, YTASR,
syncedlyrics word timings, syncedlyrics line timings — and whether the
syncedlyrics ones would confuse it given video/lyrics mismatches. Both
rounds were **read-only**; nothing was built, run, or measured. **No
gate letters assigned and no ruling taken — these are advisory
assessments and every verdict below is Ken's to make or refuse.** The
executor's framing that each round attacked is recorded with it, since
in both cases part of it was wrong and the correction is the finding.

**Standing position restated so this entry is not misread:** three of
the six sources (whisper transcribe, whisper align, YTASR) are already
DP peers; CTC as aligner is settled by GATE J1 NO-GO; the two
syncedlyrics sources are foreign-clock. So the complement contains no
unused audio witness.

#### Round 1 — sidecar as a DP candidate

Verdict *offered* (not ruled): structurally dead as a DP change, **for
reasons different from the executor's**. The mechanism is recorded in
Phase 5's "must not do" paragraph above. The two corrections that
matter, because the argument will otherwise be re-derived and found
wrong:

1. The executor argued that a sidecar candidate would convert a hidden
   line into a confidently-shown wrong one — the failure that closed
   the line route. **That is wrong.** An uncorroborated sidecar window
   scores zero and never enters the DP chain. A DP candidate has a drop
   branch by construction; the line route's lack of one was a *route*
   property, not a candidate-form property.
2. The executor argued that per-line wrong-edit detection is harder
   than the per-song detection that already failed four ways. **The
   direction is backwards.** Per-line "sung here" detection is *easier*
   — that is why the joint route wins. But it is detection of *audio
   evidence*, and the sidecar carries none, so the sharper test has
   nothing to adjudicate in the sidecar's favour. The correction does
   not rescue the DP form; it points at the per-gap fill gate, where
   per-line-ish detection does have work to do — hence Phase 5 item 2.

Also recorded: CTC as a *fourth peer* (rather than J1's substitution)
stays dead, with a second reason J1 did not name — **the joint score is
monotone non-decreasing in candidate width**, so between two candidates
for the same line at the same place the wider wins; whisper smears and
CTC does not, so a CTC peer would lose clean lines to coarser sources.
The executor's "unfilterable" was an overstatement (a crammed candidate
is roughly half-filterable depending on nearby transcribe words, which
is worse to reason about than either extreme); direction of the
conclusion unchanged. Softer peer forms assessed and rejected:
advisory/demote-only (nothing says which of two smears is right),
tie-break-only (ties already resolve to align, which is right on the
clean tail), width-only (survives in principle, but CTC's width is
wrong exactly where a width prior would bite).

If Ken wants the number rather than the argument, the round supplied a
replay-only pre-registration (sidecar spans as a fourth source, shifted
by the fill's arm-A offset; read-off on *redundant* / *phantom* /
*displacing* selections, N and M fixed by Ken; scored against the M7-a
caption reference, never held-out LRC). Fable's stated prior is that
those three classes cover ≈100% of selections, i.e. arithmetically
decisive without a judge round.

#### Round 2 — CTC post-selection interior refinement

Ken's question: use CTC's word timings only where they agree with the
matcher's output. Assessment: **does not die on mechanism**; full
detail, corrections and probe order are in Phase 6 above. Recorded here
as the round's own findings:

- The form escapes J1 for a reason the executor stated incompletely,
  and the closest existing evidence was not cited: **S-C already ran
  CTC constrained to a window with correct text and Ken's eyeball
  rejected it for a failure that lives inside a correct window**
  (overlapping voices). Windowing does not remove that mode.
- **The trough is not J1's pace finding in a different hat** — that was
  line-level *mean* pace, where a partial cram averages back into the
  honest band. Per *token*, a dropped sheet token takes one frame and
  no honest syllable is that short. So: detect per token, act per line
  — the executor's per-line-detection preference was backwards.
- **The measurement problem is the sharp one.** Interiors have no
  reference on this corpus but Ken's eye; endpoints have one (the 16
  uploader cues) but drag in GATE J2. Hence interior-only, and hence
  the blind A/B protocol.
- **A zero-model competitor exists in the bundles today** and should be
  priced first, along with 20 blind looks at current output to
  establish that the problem exists at all.
- Width monotonicity (round 1) does **not** apply to a refinement — it
  is a selection-score property. Its sibling does: the window slack
  that made width matter in selection is what makes endpoint
  refinement smear-prone.
- Sequencing corrected: **after GATE T, not parallel.**

#### Consequences recorded in this commit

No code changed. Phase 5's scope gains a per-gap gate (item 2) and a
two-arm probe; Phase 6 is added as design owed; the START HERE block
and `plans/PROGRAM.md` are updated to match. Open and Ken's: whether to
re-open the DP ban at all (round 1 says no, and the ban is his) and the
gate letters for Phases 5 and 6. *(The J2-vs-Appendix-D item was also
open at the time of this commit; Ken resolved it the same day — see the
ruling appended to the GATE J1/J2 read-off above.)*

### 2026-09-10 — Phase 3 (knob re-tune sweep), Windows box — raw tables, no read-off

Ran by a scratchpad driver on the `replay_ytasr_third_source.py`
chassis. Cohort: **all 18 genius-origin bundles** in the library (34
total; the other 16 are uploader-SRT songs on the cue-align route). No
song was skipped and none raised. Output is the tables below; **GATE T
is Ken's read-off — none is taken here.**

**What was swept.** `alpha` x `beta` over {1.0, 1.5, 2.0, 2.5, 3.0} x
{1.0, 2.0, 3.0}, the grid this plan's Phase 3 item 1 pre-registers.
Every other knob is held at each bundle's own recorded value, and all
18 bundles record the same four: `margin_s` 0.3, `max_edit_ratio` 0.75,
`lookahead` 3, `anchor_fallback` on. The shipped default point
(`alpha` 2.0, `beta` 2.0) is inside the grid, so the baseline is a grid
cell rather than a separate run. The aligner is whisper throughout —
GATE J1 NO-GO, so there is no CTC arm in this phase.

**Why the full grid is dumped rather than the chassis' sweep mode.**
The chassis reports one best combo per song, chosen by `min()` over
(fewest crawl lines, then lowest MAD). That tie-breaks to the lowest
`alpha` whenever the metrics tie, which they do constantly — the
recorded sweep-reading trap. This driver evaluates every cell and
selects nothing; the per-song x per-combo grid is the record.

**Part 2 (ytasr co-primary probe).** Item 2 pre-registers three
`ytasr.CANDIDATE_MAX_EDIT_RATIO` values at "the best 3 grid points".
The full grid was run at each of {0.34 (shipped), 0.45, 0.55} instead,
on the 10 ytasr-carrying bundles — strictly more data than the
pre-registration asks for, and it removes the executor judgment that
picking three points would have required. The constant is overridden
module-side (`ytasr.CANDIDATE_MAX_EDIT_RATIO`), which is the only
handle it has today; it is not a config knob.

**Reference.** Held-out LRCLIB, resolved by the chassis' existing three
tiers (bundle `.lrc`, then the flat `lrclib/<stem>` cache, then a live
search), scoring-only, never fed to a matcher. It is resolved once per
song and reused across all 15 cells, so no cell is scored against a
different reference than its neighbours.

**Pre-registered caveat (item 3), carried into the table header.**
Held-out LRC exists only for LRCLIB-covered songs. At the shipped point
**13 of 18 songs carry an unflagged MAD**; 5 are flagged `wide` (the
scorer's own residual-spread bail-out) and none `few`. The anchor count
behind a fit ranges from 5 (Seasons of Love) to 55 (Belle) — five songs
fit on fewer than a dozen anchors. The `*` in the MAD matrices marks a
flagged cell; **three songs flip flag state across the grid** (Best
Part Of Me, Man Out of You, Hakuna Matata), which is why the flag is
per cell and not a per-song column. The truly-dirty tail is judged by
the structural columns plus Ken's eyeball, per the same item.

**Comparability limits of the aggregate columns.** `med_mad` is the
median over that combo's *unflagged* rows only, so its population
changes between combos (13 or 14 of 18 in part 1, 5 to 7 of 10 in the
ratio arm) and the medians are not strictly like-for-like down the
column. `mad_better` / `mad_worse` / `plc_delta` count against the
shipped point (`alpha` 2.0, `beta` 2.0); in the ratio arm they count
against the shipped point *at the shipped ratio*, so those columns read
against production rather than against each ratio's own centre. A pair
where either side is flagged is not counted in better/worse at all.

**Source flags.** `3src` = the bundle carries a gate-passing YTASR
track and the candidate scan matched lines; `2src` = no YTASR track.
**8 of 18 are 2src and 10 are 3src; no song came out `asr0`** (a
gate-passing track matching no line) at any of the three ratios. For a
2src song `beta` is a no-op by construction, so the alpha axis was run
once and the row replicated across the beta columns — the flat beta
rows on those 8 songs are replication, not measurement. Their alpha
axis is real.

**Cross-check against Phase 2a.** The shipped-point row reproduces the
2026-09-08 Arm A table exactly on every column the two share — placed,
align/transcribe/ytasr-won, interp, offset, MAD and its bail flag — on
**all 18 songs**. Arm A was a different driver at the same knobs, so
this is an independent re-derivation of the production baseline, not a
re-read of a cached number.

**Determinism.** Defying Gravity's 15 cells were produced twice in
separate processes (a timing probe before the corpus run, and the
corpus run itself) and every value in every shared column matched.

**Environment.** Windows dev box (uv `.venv`), library
`d:/shared/pikaraoke-songs`. Offline throughout — no whisper, no GPU,
no re-decode; the replay consumes the bundles' captured word streams.
Runtime 1251 s for part 1 (18 songs x 15 cells) and about the same
again per extra ratio. Production code was neither changed nor
imported differently: the matcher, the span replay and the scorer are
the shipped ones.

**Fidelity limits, inherited from the chassis and unchanged here:** the
evidence veto is not replayable offline and is skipped; edge snap is
not replayed (it needs stem audio this harness never touches), so these
are pre-snap numbers throughout; windowed-realign span boundaries and
the suspect set were chosen by the original pass-1 and do not move with
the knobs.

**Flagged for the gate reader, not resolved here.** GATE T's hard
criterion is that no clean-tail song regresses materially vs current
defaults, and **the clean-tail roster has never been written down as a
list**. What the record names: Stay Gold and In Summer as clean tail
(GATE P read-off, 2026-09-01), Bloodstream and HUNTR/X as the two
lyric-version-drift songs (same entry), and Stay Gold as "GATE T's hard
criterion in miniature" (GATE J1/J2 read-off eyeball table). The other
14 songs are unclassified. Nothing here assigns them.

**Artifacts** (session scratchpad, not committed, per this plan's
ground rules): `phase3_out/grid.csv` (190 rows, part 1),
`phase3_out/ratio.csv` (450 rows, part 2), `phase3_out/report.txt`,
`phase3_run.log`, and the driver `phase3_knob_sweep.py`.

#### Part 1 — the alpha x beta grid at the shipped ytasr ratio

**Baseline: shipped defaults (alpha 2.0, beta 2.0) per song**

```
song                                          src  plc   /n algn trns ytsr intp wdls abst crwl    ovl    off_s   mad_s  bail  fit ycand
------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src   51   89   21   16   14   38    0    0    3    0.2  -75.791   7.121  wide   34   271
'Free' _ Official Lyric Video _ Sony Animati 2src   40   41    6   34    0    1    0    0    1    1.0   -0.130   0.197         16     0
'Popular' - Wicked 20th Anniversary Edition  3src   52   62   41    3    8   10    0    0    3    0.1  -16.590   1.599  wide   28   414
Beauty and the Beast (1991) - Be Our Guest [ 3src   77   77   57   10   10    0    0    0    0    0.0   -3.241   0.161         49   434
Beauty and the Beast (1991) - Belle [UHD]--- 3src  101  110   73   15   13    9    0    0    1    0.0   -4.550   0.390         55   369
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src   37   38   13    6   18    1    0    0    2    0.0   -0.690   0.790  wide   25   275
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src   48   74   26   12   10   26    0    0    1    6.7  -11.090   0.600         11   649
HUNTR_X 'This Is What It Sounds Like' (Music 2src   33   53   30    3    0   20    0    0    0    0.0   -0.270   1.605  wide   18     0
Jessie J - Domino (Official Video)---UJtB55M 2src   63   67   53   10    0    4    0    0    0    0.1   -1.614   0.432          7     0
Josh Gad - In Summer (From 'Frozen'_Sing-Alo 2src   29   31   26    3    0    2    0    0    2    0.0   -0.745   0.220         14     0
Mulan _ I'll Make a Man Out of You _ @disney 3src   36   47    3    8   25   11    0    0    0    0.0   32.565   1.006  wide   22   552
NSYNC - Paradise                             2src   53   65   13   40    0   12    0    0    2    0.7   24.045   0.270         10     0
Pocahontas - Colors of the Wind (Blu-ray 108 3src   37   37    2   14   21    0    0    0    2    0.0   -6.090   0.190         31   718
Seasons of Love (HD)---UvyHuse6buY           2src   25   34   15   10    0    9    0    0    3    0.0   18.580   0.520          5     0
Stay Gold (Official Music Video) from The Ou 2src   38   38   37    1    0    0    0    0    1    0.0   -0.094   0.048         19     0
The Lion King - Hakuna Matata Music Video I  3src   33   40   12    6   15    7    0    0    3    0.1    9.165   0.415          8   326
The Next Ten Minutes Lyrics---0j8kL24ph8U    2src   67   71   44   23    0    4    0    0    2    0.0    0.757   0.456         52     0
Wicked - For Good  (2025) 4K - The Girl in t 3src   29   36   10    5   14    7    0    0    2    0.0  -23.148   0.388         15   183
```

**Corpus aggregate per combo -- ratio 0.34 (shipped)**

```
alpha  beta  placed  crawl  ovl>0  med_mad  mad_scored  mad_better  mad_worse  plc_delta
------------------------------------------------------------------------------------------------
  1.0   1.0     847     28      9    0.361          14           1          0         -2
  1.0   2.0     847     29      9    0.310          13           4          0         -2
  1.0   3.0     842     25      9    0.320          14           5          0         -7
  1.5   1.0     848     29      9    0.402          14           0          2         -1
  1.5   2.0     848     29      9    0.330          13           2          0         -1
  1.5   3.0     847     29      9    0.320          14           5          0         -2
  2.0   1.0     849     29     10    0.399          14           0          2         +0
  2.0   2.0     849     28     10    0.388          13           0          0         +0
  2.0   3.0     849     29     10    0.375          14           2          2         +0
  2.5   1.0     849     29     10    0.384          14           1          3         +0
  2.5   2.0     849     29     10    0.360          13           1          1         +0
  2.5   3.0     849     29     10    0.310          13           2          1         +0
  3.0   1.0     849     29     10    0.360          13           2          2         +0
  3.0   2.0     849     29     10    0.360          13           1          1         +0
  3.0   3.0     849     28     10    0.340          13           2          1         +0
```

**MAD vs held-out LRCLIB (s)**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.32*  7.12*  7.12*  7.32*  7.12*  5.66*
'Free' _ Official Lyric Video _ Sony Animati 2src  0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20   0.20 
'Popular' - Wicked 20th Anniversary Edition  3src  1.60*  1.63*  1.63*  1.60*  1.60*  1.63*  1.60*  1.60*  1.63*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*
Beauty and the Beast (1991) - Be Our Guest [ 3src  0.16   0.15   0.14   0.18   0.15   0.15   0.18   0.16   0.15   0.18   0.16   0.16   0.18   0.18   0.16 
Beauty and the Beast (1991) - Belle [UHD]--- 3src  0.39   0.31   0.31   0.39   0.39   0.31   0.39   0.39   0.39   0.36   0.36   0.31   0.36   0.36   0.36 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src  0.79*  0.79*  0.72   0.79*  0.79*  0.72   0.79*  0.79*  0.72   0.93*  0.79*  0.79*  0.93*  0.79*  0.79*
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src  0.60   0.40   0.45   0.60   0.60   0.40   0.60   0.60   0.64   0.60   0.60   0.60   0.45   0.60   0.60 
HUNTR_X 'This Is What It Sounds Like' (Music 2src  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*
Jessie J - Domino (Official Video)---UJtB55M 2src  0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43   0.43 
Josh Gad - In Summer (From 'Frozen'_Sing-Alo 2src  0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22   0.22 
Mulan _ I'll Make a Man Out of You _ @disney 3src  0.74   1.01*  1.01*  0.74   1.01*  1.01*  0.74   1.01*  1.01*  0.74   1.01*  1.01*  0.74   1.01*  1.01*
NSYNC - Paradise                             2src  0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27   0.27 
Pocahontas - Colors of the Wind (Blu-ray 108 3src  0.19   0.19   0.16   0.19   0.19   0.16   0.19   0.19   0.21   0.19   0.19   0.21   0.19   0.19   0.21 
Seasons of Love (HD)---UvyHuse6buY           2src  0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52   0.52 
Stay Gold (Official Music Video) from The Ou 2src  0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05   0.05 
The Lion King - Hakuna Matata Music Video I  3src  0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.67   0.41   0.41   0.85*  0.41   0.41 
The Next Ten Minutes Lyrics---0j8kL24ph8U    2src  0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46   0.46 
Wicked - For Good  (2025) 4K - The Girl in t 3src  0.33   0.33   0.33   0.49   0.33   0.33   0.41   0.39   0.36   0.41   0.41   0.36   0.40   0.39   0.34 
```

**Crawl lines**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src     3      3      1      3      3      3      3      3      3      3      3      3      3      3      3 
'Free' _ Official Lyric Video _ Sony Animati 2src     1      1      1      1      1      1      1      1      1      1      1      1      1      1      1 
'Popular' - Wicked 20th Anniversary Edition  3src     3      3      2      3      3      3      3      3      3      3      3      3      3      3      3 
Beauty and the Beast (1991) - Be Our Guest [ 3src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Beauty and the Beast (1991) - Belle [UHD]--- 3src     1      1      1      1      1      1      1      1      1      1      1      1      1      1      1 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src     1      2      2      1      2      2      1      1      2      1      1      2      1      1      1 
HUNTR_X 'This Is What It Sounds Like' (Music 2src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Jessie J - Domino (Official Video)---UJtB55M 2src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Josh Gad - In Summer (From 'Frozen'_Sing-Alo 2src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Mulan _ I'll Make a Man Out of You _ @disney 3src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
NSYNC - Paradise                             2src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Pocahontas - Colors of the Wind (Blu-ray 108 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Seasons of Love (HD)---UvyHuse6buY           2src     3      3      3      3      3      3      3      3      3      3      3      3      3      3      3 
Stay Gold (Official Music Video) from The Ou 2src     1      1      1      1      1      1      1      1      1      1      1      1      1      1      1 
The Lion King - Hakuna Matata Music Video I  3src     3      3      2      4      3      3      4      3      3      4      4      3      4      4      3 
The Next Ten Minutes Lyrics---0j8kL24ph8U    2src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Wicked - For Good  (2025) 4K - The Girl in t 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
```

**Placed lines**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src    51     51     47     51     51     51     51     51     51     51     51     51     51     51     51 
'Free' _ Official Lyric Video _ Sony Animati 2src    40     40     40     40     40     40     40     40     40     40     40     40     40     40     40 
'Popular' - Wicked 20th Anniversary Edition  3src    51     51     51     52     52     51     52     52     52     52     52     52     52     52     52 
Beauty and the Beast (1991) - Be Our Guest [ 3src    77     77     77     77     77     77     77     77     77     77     77     77     77     77     77 
Beauty and the Beast (1991) - Belle [UHD]--- 3src   101    101    101    101    101    101    101    101    101    101    101    101    101    101    101 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src    37     37     37     37     37     37     37     37     37     37     37     37     37     37     37 
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src    48     48     48     48     48     48     48     48     48     48     48     48     48     48     48 
HUNTR_X 'This Is What It Sounds Like' (Music 2src    33     33     33     33     33     33     33     33     33     33     33     33     33     33     33 
Jessie J - Domino (Official Video)---UJtB55M 2src    63     63     63     63     63     63     63     63     63     63     63     63     63     63     63 
Josh Gad - In Summer (From 'Frozen'_Sing-Alo 2src    29     29     29     29     29     29     29     29     29     29     29     29     29     29     29 
Mulan _ I'll Make a Man Out of You _ @disney 3src    36     36     36     36     36     36     36     36     36     36     36     36     36     36     36 
NSYNC - Paradise                             2src    53     53     53     53     53     53     53     53     53     53     53     53     53     53     53 
Pocahontas - Colors of the Wind (Blu-ray 108 3src    37     37     37     37     37     37     37     37     37     37     37     37     37     37     37 
Seasons of Love (HD)---UvyHuse6buY           2src    24     24     24     24     24     24     25     25     25     25     25     25     25     25     25 
Stay Gold (Official Music Video) from The Ou 2src    38     38     38     38     38     38     38     38     38     38     38     38     38     38     38 
The Lion King - Hakuna Matata Music Video I  3src    33     33     32     33     33     33     33     33     33     33     33     33     33     33     33 
The Next Ten Minutes Lyrics---0j8kL24ph8U    2src    67     67     67     67     67     67     67     67     67     67     67     67     67     67     67 
Wicked - For Good  (2025) 4K - The Girl in t 3src    29     29     29     29     29     29     29     29     29     29     29     29     29     29     29 
```

**Max consecutive-line overlap (s)**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src   0.0    0.0    0.0    0.0    0.0    0.0    0.2    0.2    0.2    0.2    0.2    0.2    0.2    0.2    0.2 
'Free' _ Official Lyric Video _ Sony Animati 2src   1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0    1.0 
'Popular' - Wicked 20th Anniversary Edition  3src   0.3    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1 
Beauty and the Beast (1991) - Be Our Guest [ 3src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Beauty and the Beast (1991) - Belle [UHD]--- 3src   0.1    0.1    0.1    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src   6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7    6.7 
HUNTR_X 'This Is What It Sounds Like' (Music 2src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Jessie J - Domino (Official Video)---UJtB55M 2src   0.0    0.0    0.0    0.0    0.0    0.0    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1 
Josh Gad - In Summer (From 'Frozen'_Sing-Alo 2src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Mulan _ I'll Make a Man Out of You _ @disney 3src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
NSYNC - Paradise                             2src   0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7    0.7 
Pocahontas - Colors of the Wind (Blu-ray 108 3src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Seasons of Love (HD)---UvyHuse6buY           2src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Stay Gold (Official Music Video) from The Ou 2src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
The Lion King - Hakuna Matata Music Video I  3src   0.1    0.1    0.1    0.1    0.1    1.0    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1    0.1 
The Next Ten Minutes Lyrics---0j8kL24ph8U    2src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
Wicked - For Good  (2025) 4K - The Girl in t 3src   0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.0 
```

#### Part 2 — ytasr candidate-ratio arm (10 ytasr-carrying songs)

The ratio-0.34 tables are the part-1 numbers restricted to these 10
songs and are not repeated; the aggregate is, because its columns are
re-based on this subset. Candidate counts are constant across the grid
and are collapsed into one table at the end.

**Corpus aggregate per combo -- ytasr ratio 0.34 (deltas vs shipped a2.0/b2.0/r0.34)**

```
alpha  beta  placed  crawl  ovl>0  med_mad  mad_scored  mad_better  mad_worse  plc_delta
------------------------------------------------------------------------------------------------
  1.0   1.0     500     17      4    0.390           7           1          0         -1
  1.0   2.0     500     18      4    0.320           6           4          0         -1
  1.0   3.0     495     14      4    0.330           7           5          0         -6
  1.5   1.0     501     18      4    0.415           7           0          2         +0
  1.5   2.0     501     18      4    0.360           6           2          0         +0
  1.5   3.0     500     18      4    0.330           7           5          0         -1
  2.0   1.0     501     18      5    0.408           7           0          2         +0
  2.0   2.0     501     17      5    0.389           6           0          0         +0
  2.0   3.0     501     18      5    0.390           7           2          2         +0
  2.5   1.0     501     18      5    0.408           7           1          3         +0
  2.5   2.0     501     18      5    0.384           6           1          1         +0
  2.5   3.0     501     18      5    0.335           6           2          1         +0
  3.0   1.0     501     18      5    0.380           6           2          2         +0
  3.0   2.0     501     18      5    0.374           6           1          1         +0
  3.0   3.0     501     17      5    0.350           6           2          1         +0
```

**Corpus aggregate per combo -- ytasr ratio 0.45 (deltas vs shipped a2.0/b2.0/r0.34)**

```
alpha  beta  placed  crawl  ovl>0  med_mad  mad_scored  mad_better  mad_worse  plc_delta
------------------------------------------------------------------------------------------------
  1.0   1.0     502     17      4    0.321           6           2          0         +1
  1.0   2.0     500     18      4    0.320           6           5          0         -1
  1.0   3.0     494     14      4    0.320           6           5          0         -7
  1.5   1.0     503     18      4    0.362           6           1          2         +2
  1.5   2.0     503     18      4    0.320           6           3          0         +2
  1.5   3.0     502     18      4    0.355           6           4          1         +1
  2.0   1.0     503     18      5    0.359           6           1          2         +2
  2.0   2.0     503     17      5    0.349           6           1          0         +2
  2.0   3.0     503     18      5    0.335           6           3          2         +2
  2.5   1.0     503     18      4    0.359           6           1          3         +2
  2.5   2.0     503     18      5    0.337           6           1          1         +2
  2.5   3.0     503     18      5    0.312           6           2          1         +2
  3.0   1.0     503     18      4    0.310           5           1          2         +2
  3.0   2.0     503     18      5    0.327           6           1          1         +2
  3.0   3.0     503     17      5    0.302           6           2          1         +2
```

**Corpus aggregate per combo -- ytasr ratio 0.55 (deltas vs shipped a2.0/b2.0/r0.34)**

```
alpha  beta  placed  crawl  ovl>0  med_mad  mad_scored  mad_better  mad_worse  plc_delta
------------------------------------------------------------------------------------------------
  1.0   1.0     504     18      4    0.362           6           1          2         +3
  1.0   2.0     502     19      4    0.355           6           4          1         +1
  1.0   3.0     496     15      3    0.362           6           4          1         -5
  1.5   1.0     505     19      4    0.362           6           1          2         +4
  1.5   2.0     505     19      4    0.361           6           1          2         +4
  1.5   3.0     504     19      4    0.355           6           4          1         +3
  2.0   1.0     505     19      5    0.359           6           1          2         +4
  2.0   2.0     505     18      5    0.359           6           1          2         +4
  2.0   3.0     505     19      5    0.359           6           1          4         +4
  2.5   1.0     505     19      4    0.359           6           1          2         +4
  2.5   2.0     505     18      5    0.337           6           1          2         +4
  2.5   3.0     505     19      5    0.337           6           1          3         +4
  3.0   1.0     505     19      4    0.355           6           1          3         +4
  3.0   2.0     505     19      5    0.327           6           1          1         +4
  3.0   3.0     505     18      5    0.327           6           1          2         +4
```

**MAD -- ytasr ratio 0.45**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.32*  7.12*  7.12*  7.32*  7.12*  5.66*
'Popular' - Wicked 20th Anniversary Edition  3src  1.60*  1.63*  1.63*  1.60*  1.60*  1.63*  1.60*  1.60*  1.63*  1.60*  1.60*  1.60*  1.60*  1.60*  1.60*
Beauty and the Beast (1991) - Be Our Guest [ 3src  0.16   0.15   0.14   0.18   0.15   0.15   0.18   0.16   0.15   0.18   0.16   0.16   0.18   0.18   0.16 
Beauty and the Beast (1991) - Belle [UHD]--- 3src  0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.27   0.27   0.31   0.27   0.27 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src  0.83*  0.86*  0.86*  0.83*  0.86*  0.86*  0.83*  0.83*  0.86*  0.83*  0.83*  0.86*  0.83*  0.83*  0.86*
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src  0.60   0.40   0.45   0.60   0.60   0.40   0.60   0.60   0.64   0.60   0.60   0.60   0.60   0.60   0.60 
Mulan _ I'll Make a Man Out of You _ @disney 3src  1.01*  1.01*  0.98*  1.01*  1.01*  0.98*  1.01*  1.01*  0.98*  1.01*  1.01*  0.98*  1.01*  1.01*  0.98*
Pocahontas - Colors of the Wind (Blu-ray 108 3src  0.19   0.18   0.16   0.19   0.19   0.16   0.19   0.19   0.21   0.19   0.19   0.21   0.19   0.19   0.21 
The Lion King - Hakuna Matata Music Video I  3src  0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.67   0.41   0.41   0.85*  0.41   0.41 
Wicked - For Good  (2025) 4K - The Girl in t 3src  0.33   0.33   0.33   0.49   0.33   0.41   0.41   0.39   0.36   0.41   0.41   0.36   0.40   0.39   0.34 
```

**Crawl -- ytasr ratio 0.45**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src     3      3      1      3      3      3      3      3      3      3      3      3      3      3      3 
'Popular' - Wicked 20th Anniversary Edition  3src     3      3      2      3      3      3      3      3      3      3      3      3      3      3      3 
Beauty and the Beast (1991) - Be Our Guest [ 3src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Beauty and the Beast (1991) - Belle [UHD]--- 3src     1      1      1      1      1      1      1      1      1      1      1      1      1      1      1 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src     1      2      2      1      2      2      1      1      2      1      1      2      1      1      1 
Mulan _ I'll Make a Man Out of You _ @disney 3src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Pocahontas - Colors of the Wind (Blu-ray 108 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
The Lion King - Hakuna Matata Music Video I  3src     3      3      2      4      3      3      4      3      3      4      4      3      4      4      3 
Wicked - For Good  (2025) 4K - The Girl in t 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
```

**MAD -- ytasr ratio 0.55**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.12*  7.32*  7.12*  7.12*  7.32*  7.12*  5.66*
'Popular' - Wicked 20th Anniversary Edition  3src  1.60*  1.68*  1.68*  1.60*  1.62*  1.68*  1.60*  1.60*  1.68*  1.60*  1.60*  1.62*  1.60*  1.60*  1.60*
Beauty and the Beast (1991) - Be Our Guest [ 3src  0.17   0.15   0.15   0.18   0.17   0.15   0.18   0.17   0.19   0.18   0.17   0.17   0.18   0.18   0.17 
Beauty and the Beast (1991) - Belle [UHD]--- 3src  0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.31   0.27   0.27   0.31   0.27   0.27 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src  0.83*  0.83*  0.83*  1.07*  0.83*  0.83*  1.07*  0.83*  0.83*  1.07*  1.07*  0.83*  1.07*  1.07*  0.83*
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src  0.60   0.40   0.45   0.60   0.60   0.40   0.60   0.60   0.64   0.60   0.60   0.60   0.60   0.60   0.60 
Mulan _ I'll Make a Man Out of You _ @disney 3src  0.80*  0.80*  0.93*  0.80*  0.80*  0.93*  0.80*  0.80*  0.93*  0.80*  0.80*  0.93*  0.80*  0.80*  0.93*
Pocahontas - Colors of the Wind (Blu-ray 108 3src  0.19   0.18   0.16   0.19   0.19   0.16   0.19   0.19   0.21   0.19   0.19   0.21   0.19   0.19   0.21 
The Lion King - Hakuna Matata Music Video I  3src  0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.41   0.55   0.41   0.41 
Wicked - For Good  (2025) 4K - The Girl in t 3src  0.49   0.41   0.46   0.49   0.41   0.49   0.41   0.41   0.41   0.41   0.41   0.41   0.40   0.39   0.39 
```

**Crawl -- ytasr ratio 0.55**

```
song                                          src  a1b1   a1b2   a1b3  a1.5b1  a1.5b2  a1.5b3   a2b1   a2b2   a2b3  a2.5b1  a2.5b2  a2.5b3   a3b1   a3b2   a3b3 
----------------------------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary  3src     3      3      1      3      3      3      3      3      3      3      3      3      3      3      3 
'Popular' - Wicked 20th Anniversary Edition  3src     3      3      2      3      3      3      3      3      3      3      3      3      3      3      3 
Beauty and the Beast (1991) - Be Our Guest [ 3src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Beauty and the Beast (1991) - Belle [UHD]--- 3src     1      1      1      1      1      1      1      1      1      1      1      1      1      1      1 
Ed Sheeran - Best Part Of Me (feat. YEBBA) ( 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
Ed Sheeran & Rudimental­ - Bloodstream [Offi 3src     1      2      2      1      2      2      1      1      2      1      1      2      1      1      1 
Mulan _ I'll Make a Man Out of You _ @disney 3src     0      0      0      0      0      0      0      0      0      0      0      0      0      0      0 
Pocahontas - Colors of the Wind (Blu-ray 108 3src     2      2      2      2      2      2      2      2      2      2      2      2      2      2      2 
The Lion King - Hakuna Matata Music Video I  3src     3      3      2      4      3      3      4      3      3      4      3      3      4      4      3 
Wicked - For Good  (2025) 4K - The Girl in t 3src     3      3      3      3      3      3      3      3      3      3      3      3      3      3      3 
```

**ytasr candidates admitted, per song x ratio** (constant across the
alpha x beta grid, so shown once)

```
song                                           r0.34   r0.45   r0.55
--------------------------------------------------------------------
Beauty and the Beast (1991) - Be Our Guest [     434     608     953
Beauty and the Beast (1991) - Belle [UHD]---     369     576     743
'Defying Gravity' - Wicked 20th Anniversary      271     375     573
Ed Sheeran - Best Part Of Me (feat. YEBBA) (     275     506     717
Ed Sheeran & Rudimental­ - Bloodstream [Offi     649    1154    1681
Mulan _ I'll Make a Man Out of You _ @disney     552     939    1313
Pocahontas - Colors of the Wind (Blu-ray 108     718    1078    1424
'Popular' - Wicked 20th Anniversary Edition      414     615     810
The Lion King - Hakuna Matata Music Video I      326     429     725
Wicked - For Good  (2025) 4K - The Girl in t     183     292     434
```

### 2026-09-10 — GATE T read-off (Claude Opus 5, at Ken's request) — knobs stay at shipped defaults; the ytasr ratio is the one open sub-question

**Provenance, recorded because it departs from the standing rule.**
Gate read-offs go to Fable (`PROGRAM.md` ground rules:
executor reports tables, judge reads them). Ken is short on Fable
credits and asked the executor model to read the evidence and propose
next steps instead; he then took the ruling in 1 below. So: **assessment
by Claude Opus 5, ruling by Ken.** It is not a Fable round and should
not be cited as one. The tables it reads are the Phase 3 entry above,
unchanged.

*(Added 2026-09-10, after the fact: the standing rule this entry says it
departs from was revised the same day — Opus is now the judge for every
read-off, GATEs included, so this routing became the norm rather than an
exception. The entry above is left as written. See `PROGRAM.md`
§"Model switching".)*

#### Finding 1 — the alpha x beta knobs are inert on this corpus

Across all 15 grid points and all 18 songs the total movement is **7
placed lines on 4 songs** (Defying Gravity 47-51, Popular 51-52, Hakuna
Matata 32-33, Seasons of Love 24-25). Crawl moves on 4 songs, overlap on
4. **All nine songs above 90% coverage are identical in placed count and
crawl at every point in the grid** — Be Our Guest, Colors of the Wind,
Stay Gold, Free, Best Part Of Me, In Summer, Domino, The Next Ten
Minutes, Belle. Paradise, Man Out of You and HUNTR/X are invariant too.
The songs that move are the low-coverage ones.

**13 of the 14 non-baseline grid points regress at least one song** on
placed, crawl or overlap. The exception is alpha 3.0 / beta 3.0, an
exact structural wash that moves MAD by under 50 ms on three songs and
nothing on the other fifteen.

The largest MAD spreads available are Hakuna Matata (0.42-0.86) and
Bloodstream (0.40-0.64), whose fits rest on **8 and 11 anchors** — inside
the thin-fit band the Phase 3 header flags. Not a basis for a default.

#### Finding 2 — the hard criterion cannot fail, so the missing roster does not block

GATE T's hard criterion is that no clean-tail song regresses materially
vs current defaults. **No song that could plausibly be called clean tail
moves at any grid point at all** (Finding 1). The criterion is therefore
satisfied by every combo, and the clean-tail roster the Phase 3 entry
flagged as missing is **not a prerequisite for this gate**. That flag
was over-stated; it would bind only if some point traded clean-tail
quality for dirty-tail coverage, and none does. The roster may still be
wanted for Phase 5, which does touch the unplaced population.

#### Finding 3 — one strictly dominant move exists, on the ytasr axis

Ratio 0.34 → **0.45** at the shipped `alpha`/`beta`: **+2 placed, no
crawl change, no overlap change, no song regressed on any hard metric.**
The 8 songs with no ASR track are untouched by construction. Ratio 0.55
is not free — +4 placed but a crawl line on For Good and a 0.7 s overlap
on Hakuna Matata.

The whole corpus-level effect is one song. Diffed line by line at the
shipped knob point (`phase3_forgood_diff.py`), For Good gains exactly
two lines, loses none, and shifts or re-sources none:

```
line  8   29.64- 34.29  [align]   'She spins such beautiful stories'
line 35  175.36-181.90  [ytasr]   'For her bubble to pop?'
```

Worth noting the mechanism: **loosening an ytasr threshold let a
whisper-align candidate win line 8**, through the knock-on in the
selection chain — the ratio does not only admit ytasr lines.

#### What this read-off does NOT claim

- **Nothing about the dirty tail.** MAD fits on well-corroborated anchor
  lines, so it measures precision on the easy ones; the structural
  columns count lines without judging them. No eyeball has been taken.
- **Nothing about whether the 2 gained lines are right.** The harness
  cannot separate a correctly-placed new line from a wrongly-placed one
  that happens not to crawl or overlap. That is the open item in 2 below.
- **Nothing generalisable about the ratio.** The signal is n=1. "Free on
  this corpus" is not "an improvement".
- **Nothing about the defects the knobs cannot reach.** Bloodstream's
  6.7 s overlap is identical at all 45 measured points, and roughly 150
  sheet lines corpus-wide never get words at any of them.

#### Ken's ruling

1. **GATE T closed on the alpha/beta half: the knobs stay at the shipped
   `joint_alpha` 2.0 / `joint_beta` 2.0.** No config default moves and
   **no commit carries a knob change** — the gate's "config-default
   change lands as one commit" clause resolves to no commit. Ken took
   this 2026-09-10 on the assessment above.
2. ~~**Open, and Ken's: the ytasr candidate ratio.**~~ **CLOSED
   2026-09-10 — Ken eyeballed both timestamps, the singing matches at
   each, and `ytasr.CANDIDATE_MAX_EDIT_RATIO` ships at 0.45.** This is
   the one production change to come out of Phase 3. It was held to the
   burden the read-off named: free on the metrics *and* the two lines it
   adds confirmed correct by ear, because the harness cannot separate a
   correct new line from a wrong one that merely fails to crawl or
   overlap. **0.55 is not adopted** — the same sweep priced it as buying
   two further lines at the cost of a crawl line and a 0.7 s overlap.

   **Where the value lives, decided with it:** the module constant is
   edited in place rather than promoted to `PipelineConfig`. It has no
   per-song behaviour, nothing reads it at runtime, and a config knob
   nobody sets is the speculative flexibility the house rules refuse.
   The four joint knobs that *are* in config got there because the
   sweeps needed them per run; this one is overridden module-side by the
   drivers that sweep it, which is sufficient.

   **Flagged, not fixed:** the ratio is **not recorded in the bundle's
   `joint_stats.knobs`** the way `margin_s` / `max_edit_ratio` /
   `lookahead` / `anchor_fallback` are, so a bundle does not say which
   ratio produced it and a replay cannot reconstruct that from the
   artifact. Phase 3 hit this — the sweep had to override a constant the
   bundles are silent about. Adding it to the recorded knobs is a small,
   genuinely useful reproducibility fix and is **not** done here; it
   touches the stats dict that replay drivers consume, so it wants its
   own change.

   **Takes effect on new alignment runs only.** Existing bundles and
   rendered karaoke files are unchanged; songs already in the library
   keep their current timing until re-run through
   `regen_alignment_bundles.py`. No regeneration was performed.

#### Consequences

Phase 3 closes with **one** production change — the ytasr candidate
ratio at 0.45 (ruling 2 above, shipped the same day); the matcher knobs
themselves do not move. The program advances to
**Phase 5** (line timing as a fill source, per-gap gate design owed),
which this read-off's Finding 1 argues is where the remaining quality
is: the knobs cannot reach the unplaced population, and Phase 5's fill
is aimed at exactly it. **Phase 6 stays after Phase 5** — it refines word
boundaries inside lines already placed, which is polish next to lines
that never render. Recorded as the executor's recommendation on where to
spend the next design pass, not a ruling: **Phase 5's per-gap gate,
not this gate** — GATE T the data answered by itself, whereas the per-gap
gate is a live design question with a named failure mode (Bloodstream).

### 2026-09-10 — Phase 5 design pass (Opus) — disk proxy tables, no gate read

Design-time measurement taken to fix Phase 5's constants instead of
intuiting them. **Read-only**: three throwaway scripts in the session
scratchpad over `D:/shared/pikaraoke-songs`; no repo file, production
path or artifact was touched, nothing was run through the matcher, and
**no gate was read**. The design it grounds is in Phase 5 above.

**What the proxy is, and what it therefore cannot settle.** The real
gate brackets an unplaced line with `analyze_pass1` anchors —
corroborated placed lines. Deriving those needs a matcher replay, which
is executor work, so this pass substituted **every placed line in
`output_line_timings` as a pseudo-anchor**. Pseudo-anchors include
misplaced lines, so every dispersion number below is an **upper bound**
on the real anchor jitter, and any song shown bailing a global gate may
well clear it on real anchors. Line starts are post-snap; energy and
collision were not simulated. Cue mappings are the shipped ones
(`lrclib.cue_spans_for_lines`, `sidecar_scaffold_cues`).

#### Reach — the 18 genius-origin bundles

All 18 are `method_used = joint`. 164 lines carry no words. Sidecars
admitted at the shipped bar (`kind ∈ {word, line}`, `map_rate ≥ 0.5`).

| | songs | unplaced lines |
| --- | --- | --- |
| genius-origin bundles | 18 | 164 |
| with unplaced lines | 15 | 164 |
| ... and a usable sidecar | 14 | 157 |
| ... and any LRCLIB variant on the box | 9 | — |
| ... sidecar but no LRCLIB at all | 6 | 84 |

Unplaced lines that actually **map to a cue** (the true candidate
population, text-matched): **81 from sidecars across 12 songs**, 46 from
LRCLIB across 8. The rest are repeats, ad-libs and section headers that
map to nothing in either source.

| stem (trunc) | n | unplaced | sidecar kind | map_rate | source | LRC |
| --- | --- | --- | --- | --- | --- | --- |
| Defying Gravity | 89 | 38 | line | 0.685 | musixmatch | — |
| Bloodstream | 74 | 27 | line | 0.703 | musixmatch | cache |
| HUNTR/X This Is What It Sounds Like | 53 | 21 | line | 0.811 | musixmatch | — |
| NSYNC Paradise | 65 | 12 | line | 0.785 | netease | cache |
| Popular | 62 | 11 | word | 0.629 | musixmatch | — |
| Mulan Make a Man Out of You | 47 | 11 | word | 0.745 | musixmatch | cache |
| Belle | 110 | 9 | word | 0.855 | musixmatch | cache |
| Seasons of Love | 34 | 9 | word | 0.912 | musixmatch | — |
| Hakuna Matata | 40 | 7 | line | 0.625 | netease | cache |
| Girl in the Bubble | 36 | 7 | — | — | — | cache |
| Domino | 67 | 4 | word | 0.910 | musixmatch | **—** |
| Next Ten Minutes | 71 | 4 | line | 0.930 | musixmatch | cache |
| In Summer | 31 | 2 | line | 0.581 | netease | cache |
| Free | 41 | 1 | word | 0.805 | musixmatch | — |
| Best Part Of Me | 38 | 1 | word | 0.868 | musixmatch | cache |
| Be Our Guest | 77 | 0 | line | 0.688 | musixmatch | cache |
| Colors of the Wind | 37 | 0 | word | 0.946 | musixmatch | cache |
| Stay Gold | 38 | 0 | word | 0.711 | musixmatch | beside |

Two provisioning facts, recorded because they bite the executor before
any measurement does: only **Stay Gold** has a `.lrc` beside it on this
box (the other 26 are in the flat `lrclib/` harness cache), and
**Domino's LRCLIB variant is on neither tier** although Domino carries
1 of the 16 good fills.

#### Bracket disagreement `|gap_audio − gap_cue|`, sidecar sources

659 consecutive pseudo-anchor pairs, all sidecar-carrying songs:

| q50 | q75 | q90 | q95 | q99 | max |
| --- | --- | --- | --- | --- | --- |
| 0.302 | 0.872 | 2.153 | 3.992 | 19.697 | 90.480 |

Histogram (seconds, count): 0–0.25 **294**, 0.25–0.5 **125**, 0.5–0.75
**57**, 0.75–1.0 **36**, 1.0–1.5 **54**, 1.5–2.0 **22**, 2.0–3.0 **24**,
3.0–4.0 **14**, 4.0–5.0 **7**, 5.0–7.5 **6**, 7.5–10 **6**, 10–15 **4**,
15–20 **3**, 20–30 **2**, 30+ **5**.

Pooled over all pairs the shape is monotone decreasing with a heavy
tail — **no trough is visible at this granularity**, which is the one
place the proxy does not reproduce the mechanism's stated rationale.
The separation the design relies on shows up instead in the per-song
survivor counts below, where the tolerance is nearly inert across
1.0–3.0 s.

Per song, sidecar unless marked: median / p90 / max, and pairs over 1 s
/ 2 s / 5 s.

| stem | pairs | med | p90 | max | >1 | >2 | >5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Bloodstream | 35 | 1.51 | 12.86 | 83.75 | 19 | 14 | 8 |
| Bloodstream (LRC) | 27 | 0.67 | 13.28 | 42.59 | 12 | 9 | 7 |
| Hakuna Matata | 23 | 0.19 | 1.16 | 90.48 | 3 | 2 | 2 |
| Hakuna Matata (LRC) | 16 | 0.44 | 31.19 | 50.30 | 6 | 4 | 4 |
| Defying Gravity | 43 | 0.60 | 2.68 | 31.33 | 15 | 7 | 3 |
| NSYNC Paradise | 45 | 0.30 | 1.61 | 40.67 | 9 | 4 | 2 |
| Seasons of Love | 23 | 0.29 | 3.89 | 21.75 | 7 | 5 | 1 |
| Popular | 37 | 0.43 | 3.62 | 18.21 | 13 | 5 | 3 |
| Belle (LRC) | 81 | 0.49 | 2.05 | 14.65 | 18 | 9 | 2 |
| Belle | 86 | 0.20 | 0.88 | 2.83 | 8 | 1 | 0 |
| Be Our Guest | 52 | 0.41 | 1.72 | 8.66 | 13 | 5 | 1 |
| Next Ten Minutes | 61 | 0.28 | 1.48 | 8.30 | 10 | 6 | 3 |
| Domino | 56 | 0.83 | 3.30 | 8.22 | 23 | 11 | 3 |
| Best Part Of Me (LRC) | 34 | 0.33 | 2.29 | 6.96 | 6 | 4 | 1 |
| HUNTR/X | 27 | 0.18 | 0.65 | 4.18 | 2 | 2 | 0 |
| Free | 32 | 0.10 | 0.51 | 3.31 | 2 | 2 | 0 |
| Best Part Of Me | 32 | 0.55 | 2.02 | 3.20 | 7 | 4 | 0 |
| Mulan (LRC) | 32 | 0.27 | 2.21 | 3.23 | 6 | 4 | 0 |
| Mulan | 31 | 0.24 | 1.17 | 2.52 | 5 | 2 | 0 |
| remainder — In Summer / Colors / Stay Gold (sidecar); Be Our Guest / In Summer / Colors / Stay Gold / Paradise / Next Ten / Girl in the Bubble (LRC) | — | ≤0.44 | ≤1.53 | ≤23.76 | — | — | — |

#### Global gate on pseudo-anchors, and per-gap survivors by tolerance

`global` = arm A (`PRIOR_MIN_ANCHORS` 4, `PRIOR_MAX_MAD_S` 0.75) ∧ arm B
Theil-Sen (`WARP_MIN_ANCHORS` 5, `WARP_MAD_GATE_S` 2.0,
`FILL_MAX_SLOPE_DEV` 0.01). `cand` = unplaced lines with a cue.
Survivors = candidates whose bracketing pair agrees within the
tolerance, before collision and energy.

| stem | source | offset | madA | slope | madB | global | cand | 1.0 / 1.5 / 2.0 / 3.0 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Defying Gravity | sidecar | −76.98 | 9.26 | 0.788 | 6.28 | A wide_spread | 17 | 0/0/0/0 |
| Bloodstream | sidecar | −10.10 | 0.72 | 0.825 | 4.65 | B wide_spread | 16 | 0/0/0/0 |
| Bloodstream | LRC | −10.67 | 0.68 | 0.856 | 4.82 | B wide_spread | 9 | 0/0/0/0 |
| HUNTR/X | sidecar | 1.43 | 0.72 | 1.0198 | 0.47 | slope_dev | 15 | 0/0/0/0 |
| Belle | sidecar | −7.77 | 0.16 | 1.0010 | 0.15 | PASS | 7 | 7/7/7/7 |
| Belle | LRC | −4.53 | 0.42 | 0.9988 | 0.44 | PASS | 8 | 8/8/8/8 |
| NSYNC Paradise | sidecar | 24.05 | 0.12 | 0.9993 | 0.12 | PASS | 5 | 4/4/4/4 |
| NSYNC Paradise | LRC | 24.07 | 0.17 | 0.9984 | 0.18 | PASS | 6 | 2/4/4/5 |
| Next Ten Minutes | sidecar | 1.15 | 0.22 | 0.9999 | 0.23 | PASS | 4 | 4/4/4/4 |
| Next Ten Minutes | LRC | 1.16 | 0.22 | 0.9999 | 0.26 | PASS | 4 | 4/4/4/4 |
| Girl in the Bubble | LRC | −22.87 | 0.23 | 1.0024 | 0.21 | PASS | 7 | 2/4/5/5 |
| Mulan | sidecar | 30.96 | 1.01 | 0.9628 | 0.33 | A wide_spread | 3 | 1/2/2/3 |
| Mulan | LRC | 31.62 | 1.86 | 0.9572 | 0.12 | A wide_spread | 9 | 4/5/5/8 |
| Seasons of Love | sidecar | −4.07 | 1.90 | 0.9494 | 0.40 | A wide_spread | 7 | 1/2/2/2 |
| Domino | sidecar | 14.34 | 6.04 | 1.1640 | 2.91 | A wide_spread | 4 | 2/2/2/2 |
| Popular | sidecar | −7.52 | 0.77 | 1.0038 | 0.69 | A wide_spread | 1 | 0/0/0/0 |
| Hakuna Matata | sidecar | 9.26 | 0.10 | 1.0035 | 0.11 | PASS | 1 | 0/0/0/0 |
| Hakuna Matata | LRC | 9.13 | 0.21 | 0.9953 | 0.26 | PASS | 2 | 0/0/0/0 |
| In Summer | sidecar | −0.84 | 0.28 | 0.9947 | 0.13 | PASS | 1 | 1/1/1/1 |
| In Summer | LRC | −0.51 | 0.10 | 0.9978 | 0.09 | PASS | 0 | 0/0/0/0 |
| Best Part Of Me | sidecar | −0.37 | 0.44 | 0.9964 | 0.35 | PASS | 0 | 0/0/0/0 |
| Best Part Of Me | LRC | −0.62 | 0.72 | 0.9808 | 0.46 | slope_dev | 1 | 0/0/0/1 |
| Free (sidecar); Be Our Guest / Colors / Stay Gold (each source) | — | — | ≤0.32 | — | ≤0.34 | PASS | 0 | 0/0/0/0 |

One cross-check on the proxy itself, and only one is available. The
study excluded Best Part Of Me at **2.1%** slope deviation against its
LRCLIB variant; pseudo-anchors on the same variant give **1.92%**, still
excluded. The study's other excluded song, Seasons of Love at 4.2%, has
**no LRCLIB variant on this box** — its 5.06% above is the *sidecar*
fit and is not the same measurement, and its bail reason here is arm A,
not the slope. One agreement is not a validation of the method.

Three readings the executor's real-anchor run must confirm or overturn,
recorded here as the proxy's output and nothing more:

- **The tolerance is nearly inert.** Of the 20 song-source pairs that
  have any candidate, the survivor count moves across the whole
  1.0–3.0 s range on **6** — Mulan (both sources), Paradise LRC, Girl in
  the Bubble, Seasons, Best Part Of Me LRC — and by 1–4 lines. The other
  14 are identical at every tolerance.
- **The global gate, not the per-gap gate, is what withholds the
  prize.** The four songs holding the most cue-mapped candidates —
  Defying Gravity 17, Bloodstream 16, HUNTR/X 15, Seasons 7 — all bail a
  global arm here, and the per-gap gate independently refuses all of Defying
  Gravity, Bloodstream and HUNTR/X at every tolerance.
- **Bloodstream bails arm B here** (madB 4.65 sidecar / 4.82 LRC, slope
  0.83/0.86), against the 2026-09-10 Fable round's record that it clears
  both global gates. Pseudo-anchors inflate arm B, so this is exactly
  the kind of claim the proxy cannot settle — table 6 of the design
  settles it on real anchors.
