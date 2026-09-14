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
> eyeballed and shipped the same day). **5 CLOSED 2026-09-11 — GATE G is
> NO-GO**: the six cells ran, the read-off went against them, and the
> gated fill stays exactly as shipped (LRCLIB source, per-song gate). The
> fetch sidecar does not become a fill source and the per-gap gate does
> not ship. **Phase 5 ends with no production change, and the per-gap
> question must not be re-opened by amending that section** — the gate
> was unwinnable as pre-registered and a re-attempt needs a fresh design
> pass and a fresh letter. **Phase 6 is the head of the queue and was
> DESIGNED 2026-09-14 (Opus) — its gate is GATE W.** CTC
> post-selection *interior* refinement: the matcher still decides
> where a line goes, and this only asks where the word boundaries
> fall inside a span already decided. Pre-registered as four steps,
> each with a kill rule that can end the phase — **the first two are
> cheap and either can stop it before a GPU runs**, which is
> deliberate. **Step 1 RAN 2026-09-14** (no GPU, no audio, bundles
> only): population-split tables are in the Results log, raw counts
> only. Opus reads W-1a/b/c next.
> **Phase 7 RAN and was READ 2026-09-14 — it is done, and it halved
> the prize.** Of the 150 unplaced lines corpus-wide, **47% are text
> that appears in no transcription of the audio at all** — closed
> permanently, unreachable by any aligner. The other 80 are present
> somewhere in the audio but **the probe cannot say whether they are
> present at their own position or only at another occurrence of the
> same repeated text**, which is the distinction the routing question
> needs. Its pre-registered validation clause fired a STOP; that was
> ruled — **the clause's premise was wrong, not the method** — and
> the same bad premise sat in the read-off rule, which is withdrawn.
> **Stop quoting ~150 as the unreached population.** One cheap
> no-GPU follow-up would close the remainder; it is specified in the
> read-off. **Phase 7b RAN and was READ 2026-09-14: the unplaced matter
> is CLOSED.** Of those 80, essentially all are text sung *somewhere
> other than where the sheet puts them* — which the matcher is correct
> to refuse. **Two lines corpus-wide are found in the gap where they
> belong**, against the pre-declared band of 20. **Stop treating the
> unplaced population as a target: it is measured and it is empty.**
> The program said twice that this was where the remaining quality sat;
> that claim is now false and is struck wherever it appears. If ever
> reopened, the lever is upstream (a lyrics sheet matching the
> recording), named at GATE P — not anything inside the matcher.
> **GATE W step 1 RAN 2026-09-14** and it is now the better target on
> evidence rather than merely what is left — tables in the Results log,
> **Opus reads W-1a/b/c next.** Then GATE L when the Mandarin corpus
> exists. Sequencing lives in `plans/PROGRAM.md`.

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

## Phase 5 — line timing as a fill source (CLOSED 2026-09-11; GATE G NO-GO)

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

**CLOSED 2026-09-11 — NO-GO. Read off by Opus, ratified by Ken; full
entry in the Results log.** The fill is not widened to the sidecar and
the per-gap gate does not ship, alone or as a guard. **Phase 5 ends with
no production change.** Two defects in the pre-registration made the
gate unwinnable as written: the envelope rule was specified to refuse
Domino while Domino is one of the 16 fills that had to survive, and item
4's "the per-gap gate only ever removes fills" is false — item 3 also
places, so the per-gap cells move fills and can collide where the
shipped path does not. **Do not re-open the per-gap question by amending
this section**; a re-attempt needs a survival bar that does not contain
its own counterexample, which is a fresh design pass and a fresh gate
letter — **and it must argue it would do better than a wash.** The
packet's new fills were never ruled on, but the read-off's one residual
uncertainty was tested: Ken eyeballed every fill the per-gap cells move
and called the placement no better than the shipped one. **So the NO-GO
rests on the mechanism buying nothing, not only on the defective bar,
and no Fable round is owed on this gate.** See the read-off's addendum.

## Phase 6 — CTC post-selection interior refinement (designed 2026-09-14; GATE W)

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

**Probe order, with kill rules (pre-register, then run).** *(The
Fable round's sketch. Pre-registered in full by the design below,
which governs where the two differ — notably step 3's snap replay
and its fidelity guard, and step 2's control looks.)*

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

**Gate:** Ken. **Letter assigned 2026-09-14: GATE W.** The design
follows.

### Design — pre-registered (Opus, 2026-09-14). Gate letter: **GATE W.**

Everything in this section is fixed before the run. The executor
implements it, runs it, reports the tables, and stops. No constant here
moves during execution; a case the read-off does not cover is a
**STOP → Ken**. The assessment's probe order above is the Fable round's
sketch and stands as its record; where the two differ in detail, this
section governs.

**Written against GATE G's two defects so they cannot recur here.**
G's survival bar named a song the mechanism was specified to refuse —
the bar contained its own counterexample — and G's item 4 claimed the
gate "only ever removes" when item 3 also placed. Both are answered
below rather than assumed away. The bar here is `worse = 0` per
stratum on a blind A/B, and nothing in the mechanism forces a `worse`;
the strata the band *refuses* are looked at too, so a band in the wrong
place surfaces as calibration evidence instead of as a failure. And it
is stated plainly rather than left implied: **this pass moves
boundaries.** It can move one the wrong way, invert two, or shorten a
token below what the renderer wants — each has a declared refusal in
W-6.

#### The seam, verified

`pikaraoke/pipeline/stages/lyric_align.py:246-256` runs
`veto_uncorroborated_lines` → `snap_line_edges` → `apply_fills` →
`_generate_ass`. The refinement goes **between the snap and the fill**,
exactly as the assessment fixed. Two facts this verification adds:

- The RMS envelope `env` is already decoded at this seam and shared by
  the veto, the snap and the fill. The new per-song cost is the MMS_FA
  emission forward pass alone, not a decode.
- `apply_fills` already runs after the snap, so fill lines are never
  snapped and never refined — "skip fill lines" needs no new guard.

#### W-1. Step 1 — population split. No GPU, no audio, bundles only.

Cohort: the 18 joint-matcher bundles (the ones whose `joint_stats`
carries `pass1_line_timings`; the other 16 in `alignment_debug/` are
cue-route captures and are not this phase's population).

For each line, `joint_stats.selected_source[line_id]` gives
`align` / `transcribe` / `ytasr` / `interp` — it is indexed **by line
id**, length `n_lines`. Target population: `transcribe` and `ytasr`.

Recompute `_line_align_ranges(line_tokens, words)` from the bundle's
own `lyrics.lines` and `words`. Whisper's belief about each target
line falls in exactly one class:

- **abstain_none** — the range is `None` (the aligner matched no word
  to any of the line's tokens).
- **abstain_crammed** — range present but
  `(t1 - t0) / n_tokens < 0.06` (`joint_match._MIN_ALIGN_PACE_S`). This
  class exists because `_range_agreement` returns **1.0** for a
  collapsed reference instant, so agreement alone cannot see the
  aligner's give-up signature. The pace guard must be consulted first;
  this is the ambiguity the Fable round flagged, now pinned to the
  constant.
- **agrees** — range present, paced, and
  `_range_agreement(t0_line, t1_line, ar) >= 0.5`, where the line span
  is the bundle's `output_line_timings` entry.
- **disagrees** — range present, paced, agreement below 0.5.

τ = **0.5**: at that value more than half of whisper's belief about the
line lies inside the span the matcher chose, so the two are describing
the same stretch of audio. Below it they are competing *placements*,
which is a selection question and out of this phase's scope. The split
is additionally **reported** at τ ∈ {0.3, 0.5, 0.7} as a sensitivity
column; the kill rules read **τ = 0.5 only**.

Tables: per song and pooled — the four class counts over the target
population; the same four over align-won lines as context; the count of
align-won lines carrying at least one interpolated run (`_fill_
unmatched_runs`, the same gap in miniature, out of scope here and
counted so a later pass can price it); target lines as a share of all
placed lines.

**Kill rules, read at τ = 0.5, pooled over all 18 songs:**

- **W-1a — ceiling floor.** If transcribe-won plus ytasr-won placed
  lines are **under 15%** of all placed lines, **STOP → Ken**: the
  phase's ceiling is too small to justify a GPU probe and an eyeball
  sitting, whatever the mechanism does.
- **W-1b — the zero-model form wins.** If **agrees ≥ 70%** of the
  target population, **CTC is not commissioned.** Those lines already
  have whisper's own per-word timings available at
  `_materialise_line_objects` (`align_ranges` is computed for every
  line at `joint_match.py:167`, not only for align candidates), so the
  change is one conditional and no second model. The phase continues in
  that form through steps 2 and 4 only, with step 4 collapsing to a
  single stratum of every changed line, up to 50 looks.
- **W-1c — the zero-model form is moot.** If **agrees < 10%**, drop the
  zero-model arm and proceed with CTC alone.
- Between 10% and 70%, both arms proceed and step 4 carries the
  zero-model form as its own stratum (S6).

#### W-2. Step 2 — baseline eyeball. 28 looks. Ken at the screen.

The question this step answers is whether the problem exists at all.
Nothing is refined yet; Ken looks at **current shipped output**.

Sample at `seed = 20260914`, drawn across every song with the
population: **10 whisper-agrees** target lines, **10 whisper-abstained**
target lines (`abstain_none` and `abstain_crammed` pooled), and
**8 align-won lines as unlabelled controls**. Shuffled; Ken is not told
which class a look belongs to.

Render one diff `.ass` per song at `karaoke/<stem>.baseline.ass`,
carrying only the sampled lines. The shipped `<stem>.ass` is never
touched, and the file is inert unless loaded as a subtitle track.

Per look, one question: **does the word sweep track the singing inside
the line** — `fine` / `slightly off` / `clearly off`. Line placement
and line edges are explicitly *not* being judged; the snap owns edges
and selection owns placement.

**Kill rules:**

- **W-2a — the problem is not visible.** If, over the 20 target looks,
  `clearly off ≤ 2` **and** `slightly off ≤ 6`, **STOP: the phase ends
  and no mechanism is commissioned.** Refining a defect this faint is
  not worth the S-C overlapping-voices risk that the mechanism carries.
- **W-2b — the problem is not this population's.** If the controls'
  `clearly off` rate is within 0.20 of the target looks' rate, **STOP →
  Ken**: align-won interiors are as loose as the ones this phase
  targets, so the phase is aimed wrong and the framing has to be
  re-posed before anything is built. This control is why the step is 28
  looks rather than the assessment's 20 — without it the step cannot
  distinguish "these interiors are bad" from "all interiors are a bit
  loose," and that distinction decides whether the phase points at
  anything.

#### W-3. Step 3 — disagreement distributions. GPU, no eyeball.

CTC is `scripts/sb_ctc_adapter.make_slice_align` over the cached
per-song MMS_FA emission (`phase1b_score_oracle.get_emission`, cached
under `get_temp_directory()/ctc_probe/emissions`). One forward pass per
song on a cache miss, then near-free slicing by frame index. The S-C
caches may not survive on the Windows box; a miss is a cost, not a
blocker. Audio is **the same stem the snap ran on** (dereverb where
present, else the vocal stem).

An **interior boundary** is the boundary between token *k* and token
*k+1* for k = 0 … n−2. Token 0's start and token n−1's end are excluded
throughout — the snap owns them (Ken, 2026-09-10).

**Arm (a) — correct window, correct text.** The 16 uploader-cue songs.
Per cue span, `slice_align(t0, t1, cue_text)` against the shipped
cue-route incumbent for the same span. Disagreement here cannot be
selection error, which is what makes this the load-bearing arm.
*Guard:* the executor first confirms a per-word incumbent is available
for those spans; if the capture carries only line timings, re-derive
the incumbent by replaying the cue-route path over the same spans. If
neither is available, **STOP → Ken** — arm (a) is not substitutable.

**Arm (b) — the 18 joint bundles.** Replay each bundle through the
shipped matcher to final line objects, **including the edge snap**.
This is a correction to the assessment, and it is load-bearing:
`scripts/replay_ytasr_third_source.py` deliberately does *not* replay
the snap because it never touches audio, and its own docstring records
that the bundle's post-snap `output_line_timings` is therefore a sanity
column only. Step 3 already needs the stem for the emission, so the
snap replays here via `snap_line_edges(line_objects, snap_stem,
env=env)`. Without it the constraint window is wrong on precisely the
lines the snap moved — 21–32% of this population.

**Fidelity guard, before any CTC runs.** The replay's per-line
`line_id`/`start`/`end`/`n_words` must match the bundle's recorded
`output_line_timings` **exactly, on every line, on all 18 songs.** Any
mismatch is a **STOP → Ken**. GATE G was read on a harness that
reproduced only part of its own reference and the discrepancy surfaced
at the read rather than at the run; this guard is why that cannot
recur silently.

Then, for every placed line whose source is `transcribe` or `ytasr` and
which is not a fill, an `interp` placeholder, or vetoed:
`slice_align` over the line's final span with the line's sheet text,
and per-interior-boundary |Δ| against the replayed incumbent.

**Reported per arm, per song and pooled:**

- interior-boundary |Δ| at p50 / p75 / p90 / p95 / max
- per-line median |Δ| at the same quantiles
- the bimodality read below
- **cram-floor fire rate** — refined tokens whose CTC width is under
  **0.05 s**, and the share of lines carrying at least one. No honest
  sung syllable is that short; this is the one CTC abstention signal in
  this program with a trough, and it is read **per token, acted on per
  line** (a line with any crammed token is refused outright). Line-level
  averaging is what erased the trough at J1.
- **monotonicity violations** — lines whose refined boundaries are not
  non-decreasing, or where a refined token falls below
  `onset_snap.MIN_WORD_DUR_S` (0.1 s)
- **OOV** — tokens normalising to empty, which the tokenizer drops so
  CTC returns no span for them; reported per token and per line
- **ytasr screening statistic, reported and never read** — on the
  ytasr-carrying songs, median |word start − nearest ytasr word start|
  on transcribe-won lines, before and after refinement. Free, on our
  own clock, and it is the matcher's own epistemology.

**Bimodality test, declared now.** On `log10(|Δ| + 0.001)` over arm
(a)'s interior boundaries: Gaussian KDE at Scott's-rule bandwidth on a
512-point grid spanning the data. **Bimodal iff** some local minimum
has density **≤ 0.6×** the lower of its two flanking local maxima
**and** each mode's basin holds **≥ 15%** of the mass. The **band
boundary B** is that minimum's |Δ| in seconds, rounded to two decimals,
and it is frozen there.

**Kill rule:**

- **W-3a.** If arm (a) is **not bimodal** by that test, **GATE W is
  NO-GO and the phase ends.** With a correct window and correct text,
  |Δ| does not separate correction from failure — no band can be
  declared, and step 4 would have nothing to stratify.
- If bimodal, B is declared and arm (b)'s mass beyond arm (a)'s
  corresponding tail is **reported as the selection-error contribution,
  not read.**

#### W-4. Step 4 — bounded blind A/B. ~60 looks. Ken at the screen.

Strata fixed from step 3's tables **before any look**, using per-line
median |Δ| and the frozen B:

- **S1** — 0 < median ≤ B/2
- **S2** — B/2 < median ≤ B
- **S3** — median > B: *refused by the band*, looked at anyway
- **S4** — cram-flagged lines: *refused by the floor*, looked at anyway
- **S5** — every refined line on the ensemble songs, whatever the band
- **S6** — the zero-model form's changed lines (only when step 1 put
  `agrees` in [10%, 70%))

**The ensemble list is fixed here, not by the executor:** Belle, Be Our
Guest, Seasons of Love, Hakuna Matata, Defying Gravity, The Girl in the
Bubble — the joint-cohort songs with *sustained simultaneous* voices.
The Next Ten Minutes and I'll Make a Man Out of You were considered and
excluded as sequential duet and call-and-response rather than
simultaneous, recorded so the list reads as a rule and not as a fit.
Note what S-C does **not** give us: its four eyeball songs (Mirrors,
ZAYN's Whole New World, Part of Your World, Bye Bye Bye) are all
cue-route songs and none is in this cohort. S-C is a warning about a
*mechanism*, not a list of songs that carries over.

10 looks per stratum at `seed = 20260914`, ~60 total, bounded like
M7's 71. Render one diff `.ass` per song at `karaoke/<stem>.refine.ass`
carrying only the sitting's lines, current and refined as two variants
in **randomised A/B order with a sealed key** written to the scratchpad
before the sitting and not opened until every verdict is recorded.
Ken's prior is that CTC is tighter, so an unblinded look would confirm
itself.

Verdict per look: **better / same / worse**, on the interior word sweep
only. `same` counts as not-worse.

#### W-5. Read-off rules (GATE W), pre-registered

1. **Validity first.** If step 3's fidelity guard was waived, or any
   stratum's looks were drawn after B was known to the sampler, the
   read is void.
2. A stratum with **fewer than 8 looks is reported, not read.**
3. A stratum **clears** iff `worse = 0` in it.
4. **The adopted band is the higher of S1, S2 that clears.** If **S1
   does not clear, GATE W is NO-GO** — the mechanism is not better than
   the incumbent even where the two disagree least, and nothing weaker
   will be.
5. **S3 and S4 are read for calibration only.** If either clears, that
   is recorded as evidence the band or the cram floor is conservative.
   **It does not widen either.** A band fitted to the looks is the
   forbidden move; the band comes from step 3's trough or not at all.
6. **S5 is a veto, not a stratum.** If `worse > 0` on the ensemble
   songs, refinement is **refused on every song in the fixed list
   above**, whatever S1 and S2 did. This is the S-C failure mode and
   windowing does not remove it.
7. **S6 reads independently.** The zero-model form clears iff
   `worse = 0` in it, and **it can ship when the CTC form does not** —
   different mechanism, no second model, no new failure mode.
8. Anything these rules do not cover is a **STOP → Ken**.

#### W-6. What ships if a band clears

Refinement applies to a line iff **all** hold: source is `transcribe`
or `ytasr`; it is not a fill, `interp` or vetoed line; its per-line
median |Δ| is at or under the adopted band; it carries no crammed
token; its song is not vetoed by rule 6. Then:

- **Interior boundaries only.** Token 0's start and the last token's
  end keep their snapped values, untouched.
- **OOV runs keep their incumbent timing**, and the boundaries at a run's
  edges are not refined — CTC has no opinion on a token it never
  received. Non-OOV tokens either side still refine at their other
  boundaries. This is GATE C's C-3 constraint degrading gracefully:
  a numeral interpolates as it does today, hangul simply skips.
- **Monotonicity is a per-line refusal.** If the refined boundaries are
  not non-decreasing, or any refined token would fall below
  `onset_snap.MIN_WORD_DUR_S`, the whole line keeps its incumbent
  timing. Detect per token, act per line.
- **`source` is untouched.** Provenance goes in its own field on the
  line object and in `joint_stats.interior_refine`. `source` encodes
  selection and the evidence veto keys on it.

#### W-7. Price, stated before the spend, not discovered after

- Rendered word timing changes, so by the **v8 precedent this is a
  schema milestone bump and a full-library regen.** That is the real
  cost of this phase and it is owed whichever form ships.
- MMS_FA becomes a production dependency co-resident with the whisper
  worker (**CTC form only** — the zero-model form adds no model, which
  is exactly why W-1b prices it first).
- The capture gains `joint_stats.interior_refine`: per-song counts and
  per-line median |Δ|, **not** per-word timings. Enough to audit the
  pass without inflating every bundle. `output_line_timings` keeps its
  present shape.

#### W-8. Out of scope for GATE W

- **Endpoint refinement.** The snap owns line edges and this pass never
  touches them. Were it ever revisited, its ceiling is measurable
  against the 16 uploader SRTs — recorded, not commissioned.
- **Align-won lines' interpolated runs.** Counted at step 1, not
  refined. A later pass can price them; this one stays narrow, which is
  the GATE G lesson.
- **Anything touching selection.** If a refinement changes which line
  renders, that is a bug and not a result.
- **GATE J1 is not re-opened.** This runs strictly after selection,
  inside a window already decided on audio corroboration, and a slice
  cannot reach audio outside its window.

#### W-9. Order, stops, and who reads what

1 → **STOP** → 2 → **STOP** → 3 → **STOP** → 4 → **GATE W**.

Steps 1 and 3 are unattended; steps 2 and 4 need Ken at the screen and
are the scheduled items. Each step's tables go to the Results log with
**no verdict** (executor discipline, `PROGRAM.md` §"Model switching").
After each step Opus reads **that step's declared kill rule only** —
arithmetic against a pre-registered bar, not a verdict on the phase.
**GATE W is read once, after step 4**, by Opus, and Ken rules on it.

## Phase 7 — the unplaced population, diagnosed (designed 2026-09-14; stats only, no gate)

Added 2026-09-14 on Ken's call, and **sequenced ahead of Phase 6's
first step.** The program has now said twice that the sheet lines which
never render are where the remaining quality sits — Phase 3's read-off
said it, and GATE T's entry recorded it as the executor's
recommendation on where the next design pass should go. One attempt was
made at them (Phase 5) and it failed. Before a second design pass is
spent on that population — Opus's or Fable's — this probe asks the
question nobody has asked: **how much of it is reachable at all.**

**Why this is not a gate.** Nothing ships from it, no threshold is
under test, and no mechanism is being accepted or refused. Its output
routes the *next design pass*, and that routing is Ken's call. The
executor reports tables; Opus reads them; Ken decides where the spend
goes. No gate letter is assigned and none should be.

**Why it is worth running before GATE W.** GATE W refines lines that
are already placed — polish, by its own design's admission. This probe
prices the population that is not placed at all. If that population
turns out to be mostly unreachable, the program stops treating it as
the obvious next target and Phase 6 is simply the work that is left.
If a real share of it is reachable, there is a live design question
that has never been posed, and it outranks polish. Either answer
changes what the next pass is spent on, which is why it comes first.

### The discriminator — shipped code, no invented metric

The joint matcher already computes what this probe needs and then
throws it away. Before the DP runs
(`joint_match.match_words_to_lines_joint_with_stats`) it scans the
audio's own transcription for every sheet line:

- `find_candidates(transcribe_norms, line_norms, max_edit_ratio=<the
  run's `joint_max_edit_ratio`>)` — the main scan over whisper's
  unconstrained transcription of the whole song.
- `find_anchor_candidates(...)` over exactly the lines that scan left
  empty — the relaxed fallback, for lines whisper heard too badly for
  the edit-ratio threshold.
- on songs carrying a ytasr track, `find_candidates(ytasr_norms,
  line_norms, max_edit_ratio=ytasr.CANDIDATE_MAX_EDIT_RATIO)` — a
  **second, independent transcription** of the same audio, at ytasr's
  own stricter ratio and **not** the joint knob. Do not unify the two
  ratios; the ASR text is a ytasr candidate's only evidence for
  existing. The bundle stores only a *pointer* to the caption
  (`lyrics.ytasr.asr_file`), not the words — load and parse them with
  the shipped `ytasr.parse_json3` / `normalize_words`, exactly as
  `scripts/replay_ytasr_third_source.py` already does.

The matcher keeps only the aggregate counts. **The per-line fact — did
any scan find this line's words anywhere in the audio — is exactly the
question "is this line sung," and it is already being answered and
discarded.** This probe reads it out. That is the whole mechanism: no
new metric, no threshold of mine, nothing to validate.

### The population

Every sheet line the matcher did not place: `selected_source[line_id]
== "interp"`, plus anything in `absent_line_ids`. Both are in
`joint_stats`. Cohort: the **18 joint-matcher captures** (the ones
whose `joint_stats` carries `pass1_line_timings`; the other 16 in
`alignment_debug/` are cue-route and not this population).

### Classification, per unplaced line

- **U-1 — no candidate anywhere.** Neither the main scan nor the
  relaxed anchor fallback finds the line in whisper's transcription,
  **and** on ytasr-carrying songs the ytasr scan finds nothing either.
  Two independent transcriptions of the audio contain nothing
  resembling this line, anywhere in the song. **Read as: not sung —
  unreachable by any aligner, on any source, ever.** A mechanism cannot
  place a verse the recording does not contain.
- **U-2 — one source only.** Candidates exist in one transcription and
  not the other. **Read as: a transcription failure, not an absence.**
  Reachable, and reachable with sources already on the machine.
- **U-3 — candidate lost.** Candidates exist in both (or in the only
  transcription available) and the line still went unplaced: the DP had
  something and dropped it. **Reachable; the open question is why.**
  Sub-split, again from shipped structure — does the line's
  highest-scoring candidate window overlap a window the DP *did*
  select (cross-attraction / repeat pile-up, already diagnosed at
  GATE P) or not (lost on its own score)?
- **U-0 — no tokens.** A sheet line that tokenises empty. Bookkeeping
  only; it is not a miss and must not be counted as one.

On songs with **no** ytasr track, U-1 and U-2 cannot be separated by
two sources. Those lines are classed on whisper alone and **reported in
their own column**, never pooled into the two-source counts. Eight of
the eighteen carry no adopted caption and are in this state; saying so
in the table is the difference between a finding and an artifact.

### Second discriminator, independent: block structure

For each song, the run-length distribution of consecutive unplaced line
ids. **Runs of 3+ are the version-drift signature** — a cut or added
section — and isolated singles are per-line misses. Reported *alongside*
the classification and never merged into it. If the two discriminators
agree, the read is solid. **If they disagree, that disagreement is the
finding** and it goes to Ken rather than being resolved by the
executor.

### Tables

1. **Per song:** `n_lines`, `n_placed`, `n_unplaced`, U-0/U-1/U-2/U-3
   counts, the U-3 sub-split, and a `ytasr` yes/no column.
2. **Pooled corpus totals** for the same, with the no-ytasr songs
   broken out separately as above.
3. **Per song:** the unplaced run-length distribution, and unplaced
   lines sitting in a run of 3+ versus runs of 1–2.
4. **Cross-tab:** U-class × (in a 3+ run / not).
5. **The known cases, broken out.** GATE P's read named Bloodstream
   (lids 44–50) and HUNTR/X (lids 40–52) as sheets that do not match
   the audio version. Report those two songs' classifications
   separately, so the known answer checks the method instead of being
   assumed by it. ~~**If those blocks do not come back predominantly
   U-1, the method is wrong and that is a STOP → Ken**~~ — **the STOP
   fired 2026-09-14 and was ruled: the clause's premise is wrong, not
   the method.** A drift block made of *repeated* text is still sung
   elsewhere in the song, so a whole-song scan finds it; both named
   blocks are verbatim duplicates of earlier sheet lines. See the
   read-off in the Results log. The tables stand.

### Sensitivity

U-1 is the load-bearing class and its size must not rest on one
threshold. Report it at the run's own `joint_max_edit_ratio` **and** at
a looser **0.6**, as two columns. *(**Defect, found 2026-09-14 at the
read-off:** the shipped whisper ratio is 0.75, so 0.6 is **stricter**,
not looser, on the load-bearing source — the column tests the opposite
direction from the one declared. Kept as written because it is what
ran; the loosening direction is untested. Nothing in the read-off
depends on it.)* Declared now, before any data. It is
**reported, not read as a range** — the classification is the shipped
setting's; the second column exists so a reader can see whether the
answer is fragile.

### Discipline

No GPU, no audio, no inference — bundles only. Driver lives in the
session scratchpad and is **not committed**. No production file is
touched and nothing is regenerated. The executor reports the tables and
**stops**: no verdict, no tallies against any bar, no interpretation of
which class means what. The classes are mechanical; the reading is
Opus's and the routing decision is Ken's.

**Read-off, such as it is.** ~~Opus reports the reachable share
(U-2 + U-3) against the unreachable one (U-1)~~ — **this rule is
WITHDRAWN 2026-09-14 as unsound**: it assumes a candidate found
*anywhere* means the line is reachable at *its own position*, which
the run's own data disproves. What the tables support instead is in
the read-off entry. Opus says whether the two
discriminators agree, and gives Ken one recommendation: whether the
unplaced population holds a design question worth a pass, or whether it
is mostly audio that does not sing those words and the program should
stop treating it as the obvious next target. **No mechanism is
proposed at this step** — proposing one is the design pass this probe
exists to decide on.

### Phase 7b — where the found text actually sits (designed 2026-09-14; stats only, no gate)

Commissioned by Ken 2026-09-14, immediately after the Phase 7 read-off
and **before GATE W step 1**, to settle the unplaced matter rather than
leave it undetermined.

Phase 7 established that of 150 unplaced lines, 70 are text found in no
transcription of the audio — closed — and **80 are found somewhere,
position unknown.** It could not say whether those 80 are sung *where
the line belongs* or only at *another occurrence of the same repeated
text*, and that is the whole routing question. This pass answers it.

**Population: exactly Phase 7's U-2 and U-3 lines** — the 80. U-1 lines
have no candidate to locate, and U-0 is empty corpus-wide. Same 18
joint-matcher captures, same candidate pool (main + anchor + ytasr, best
by score), **same driver**, so the classification carried forward is
identical by construction and not a re-derivation.

**Still stats only. No gate letter, nothing ships, no GPU, no audio.**
Its output routes the next design pass; that routing is Ken's.

#### The bracket — what "where the line belongs" means

An unplaced line has no position of its own, but it has placed
neighbours, and the monotonic DP's own contract says it must sit
between them. So for each unplaced line take its nearest **placed**
predecessor and successor by line id, and define the bracket as
`[prev_placed.end, next_placed.start]` from the bundle's own
`output_line_timings`.

A run of consecutive unplaced lines **shares one bracket**; that is
correct and must not be worked around.

Per line, classify the **best-scoring** candidate window:

- **P-in** — the window overlaps the bracket at all. The text is sung
  in the gap where this line belongs. **This is the genuine-miss
  class: something is there and the matcher did not take it.**
- **P-out** — the window lies entirely outside the bracket. The only
  occurrence of this text is elsewhere in the song. **Unreachable at
  position, and the DP refusing it is correct**, which is the
  mechanism GATE P described.
- **P-edge** — no placed predecessor, or no placed successor (the run
  reaches a song boundary). The bracket is open on one side. **Report
  separately and never force into P-in or P-out**; an open bracket
  makes P-in trivially true and would inflate the answer.

#### Second measure, physical and independent: bracket capacity

Per **bracket** (not per line): its duration, the number of unplaced
lines sharing it, and the derived **seconds per unplaced line**.

This is the check the block-structure discriminator failed to be. A
bracket holding seven unplaced lines in four seconds cannot be singing
seven lines, whatever any candidate scan says — and unlike run-length,
repeated text does not confound it, because it is a physical
constraint rather than a textual signature.

**Declared before the data:** a bracket under **0.6 s per unplaced
line** is flagged `overpacked`. That is faster than any sung line in
this corpus and the number is fixed here, not fitted later. Flagged
brackets are **reported, not reclassified** — a P-in line inside an
overpacked bracket is still counted P-in, and the flag is what tells
the reader the count is soft.

**Its one caveat, stated now:** the bracket is only as good as the two
placed lines bounding it. If the matcher placed a neighbour wrongly,
the bracket is wrong. That is a different defect from the one being
measured, and it is why this is a second signal and not the primary.

#### Third measure, free: sheet duplication

For each of the 80, is the line's normalised text duplicated elsewhere
in its own sheet (shipped tokeniser, exact normalised match)? This is
what settled the two named blocks at the Phase 7 read-off, and it costs
one pass over text already in the bundle.

It bears on **P-out**, not P-in: a P-out line whose text is duplicated
is the wrong-occurrence case outright. A P-in line is reachable whether
or not its text repeats — some occurrence *is* sung in the bracket — so
duplication never subtracts from P-in. Reported as a cross-tab so that
claim is visible rather than asserted.

#### Tables

1. **Per song:** n in population, P-in / P-out / P-edge.
2. **Pooled**, same columns, with the 8 no-caption songs broken out as
   in Phase 7.
3. **Per bracket** (every bracket containing at least one unplaced
   line): song, line-id span, duration, n unplaced, seconds per
   unplaced line, `overpacked` flag, n P-in.
4. **Cross-tab:** P-class × (sheet-duplicated / unique).
5. **The P-in lines, listed in full** — song, line id, sheet text,
   bracket duration, whether overpacked, whether duplicated. There
   should be few enough to list; if there are more than 80 something is
   wrong. **This table is the deliverable** — it is the candidate
   population for any future mechanism, and Ken may want to look at
   some of them.
6. **The two known blocks again** (Bloodstream 44–50, HUNTR/X 40–52),
   broken out. **Pre-registered expectation, declared now: they should
   come back predominantly P-out.** *(**Defect, found 2026-09-14 at the
   read-off:** the expectation and the trigger are not the same clause.
   The trigger below keys on P-in and held; the expectation left a third
   outcome — a P-edge majority — unnamed, and HUNTR/X returned exactly
   that. It should have read "must not come back P-in; a P-edge majority
   is reported, not read." Ruled a clean pass on the trigger; see the
   read-off.)* They are verbatim repeated text and
   the read-off verified it off the sheets. **If they come back P-in,
   the bracket method is wrong and that is a STOP → Ken** — same role
   the GATE P clause played in Phase 7, but this time resting on a
   premise the data has already confirmed rather than one inferred
   from a conclusion.

#### Read-off — what Opus will recommend, declared before the data

The decision is Ken's. What is fixed here is what I will recommend at
what count, so the recommendation cannot be fitted afterwards. Read on
**P-in excluding P-edge**, pooled:

- **Under 20 lines** — recommend the unplaced matter is **closed**.
  A population that small does not justify a design pass from any
  model, and GATE W is the work that is left.
- **20 to 50** — recommend a **bounded eyeball first, not a design
  pass**: sample the P-in lines, confirm they are actually singable in
  their brackets, and only then decide. The count alone would not
  establish the lines are real.
- **Over 50** — there is a real population and a design pass is
  justified. That is the point at which spending Fable credits on it
  makes sense.

`P-edge` is reported and excluded from the count in all three cases,
because an open bracket makes P-in vacuous.

**Also read, and it can override the count downward:** the share of
P-in lines sitting in `overpacked` brackets. If most of them do, the
count is an artifact of brackets too narrow to hold the lines and the
recommendation drops one band.

#### Discipline

Bundles only, no GPU, no audio, no inference. Driver in the session
scratchpad, **not committed**; reuse Phase 7's classification code so
the population is identical. No production file touched. The executor
reports the six tables and **stops** — no verdict, no tally against the
bands above, no interpretation. Then Ken `/model`s to Opus.

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
is aimed at exactly it. ~~**Phase 6 stays after Phase 5** — it refines
word boundaries inside lines already placed, which is polish next to
lines that never render.~~ *(**Finding 1's premise is MEASURED AND
FALSE as of 2026-09-14** — Phase 7 and 7b found that the unplaced
population holds about two winnable lines corpus-wide, so "where the
remaining quality is" was wrong and the polish comparison it set up
does not hold. Left standing as the record of what was believed when
Phase 5 was commissioned; see the Phase 7b read-off.)* Recorded as the
executor's recommendation on where to spend the next design pass, not a
ruling: **Phase 5's per-gap gate,
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

### 2026-09-11 — Phase 5 executor run (Sonnet) — six-cell tables, no gate read

Built and ran the design exactly as pre-registered: cue-source swap,
per-gap gate, source precedence, all six cells, on the 18 genius-origin
bundles at the shipped chassis point (`joint_alpha` 2.0 / `joint_beta`
2.0, `ytasr.CANDIDATE_MAX_EDIT_RATIO` 0.45). No knob moved, no case
redesigned. **No gate read; the read-off below is Opus's / Ken's, not
this entry's.**

**Mechanism note, flagged for the read-off rather than decided here.**
The design's item 3 defines "the per-gap gate" as one mechanism —
refusal conditions *and* the slope-1/local-offset placement together.
Wherever a cell's gate column includes per-gap (A2/A3/A4/A5), fills
below are placed at that local offset, not the global constant offset;
A0/A1 place at the global constant offset, exactly as shipped. The
alternative reading (per-gap as a pure filter over global-offset
placement) would leave A2/A3 never exercising item 3's own placement
formula at all — flagged, not assumed past that.

**Validity note, factual, ahead of the roster table.** A0 (the shipped
`lrclib_fill.plan_fills`, called unmodified — verified byte-identical
against the shipped per-candidate loop on a held-out check before this
run) reproduces **12 of the 16** roster fills exactly; NSYNC and Next
Ten Minutes are 100%, Domino 1/1. The 4 discrepancies are both in
songs captured 2026-07-16, and trace to one already-shipped, already-
approved cause: **GATE T's ytasr candidate-ratio change (0.34→0.45,
2026-09-10)**, which this run correctly replays at (the executor brief
names it explicitly), but which post-dates these bundles' capture by
almost two months:

- **Girl in the Bubble** (lids 8, 35 of 8/15/32/33/35): both are now
  placed directly by the matcher, not unplaced — so they are no longer
  fill candidates at all. Arguably a strict improvement upstream of
  Phase 5, not a loss.
- **Belle** (lids 81, 86, 94 of 81/86/89/93/94, plus a new line 95):
  all five remain unplaced candidates, but the collision landscape
  around them shifted — line 95 no longer collides with a placed span
  and 94 now does. A swap, not a disappearance.

This is a property of replaying 2-month-old bundles at today's shipped
knobs — the same exposure Phase 3's own knob sweep carried on this
chassis — not a Phase 5 mechanism defect; both explanations were
traced to placement/collision facts in this run's own `line_objects`,
not asserted. Whether "reproduces the roster" should read against the
frozen historical roster or against what current shipped production
now does with these two lines is the read-off's call.

**Artifacts** (session scratchpad, not committed, per this plan's
ground rules): `phase5_out/results.json` (full per-song, per-cell
records), `phase5_out/tables.md` (source of the tables below),
`phase5_out/eyeball/` (per-song diff `.ass` + `.txt`, one pair per
song with a fill beyond A0: Belle, Best Part Of Me, In Summer, NSYNC
Paradise), and the drivers `phase5_mechanism.py` / `phase5_run.py` /
`phase5_tables.py`.

#### Table 0 — corpus provisioning (the three provisioning traps)

| stem (trunc) | n_lines | n_unplaced | lrc_tier | n_lrc_cues | sidecar_kind | map_rate | admitted | n_sidecar_cues | env_stem |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Annivers | 89 | 38 | live_fetch | 77 | line | 0.685 | yes | 61 | vocal |
| 'Free' _ Official Lyric Video _ Sony Ani | 41 | 1 | live_fetch | 36 | word | 0.805 | yes | 33 | vocal |
| 'Popular' - Wicked 20th Anniversary Edit | 62 | 10 | live_fetch | 42 | word | 0.629 | yes | 39 | vocal |
| Beauty and the Beast (1991) - Be Our Gue | 77 | 0 | flat_cache | 68 | line | 0.688 | yes | 53 | dereverb |
| Beauty and the Beast (1991) - Belle [UHD | 110 | 9 | flat_cache | 90 | word | 0.855 | yes | 94 | dereverb |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 38 | 1 | flat_cache | 36 | word | 0.868 | yes | 33 | dereverb |
| Ed Sheeran & Rudimental­ - Bloodstream [ | 74 | 26 | flat_cache | 37 | line | 0.703 | yes | 52 | dereverb |
| HUNTR_X 'This Is What It Sounds Like' (M | 53 | 20 | live_fetch | 43 | line | 0.811 | yes | 43 | vocal |
| Jessie J - Domino (Official Video)---UJt | 67 | 4 | live_fetch | 61 | word | 0.91 | yes | 61 | vocal |
| Josh Gad - In Summer (From 'Frozen'_Sing | 31 | 2 | flat_cache | 15 | line | 0.581 | yes | 18 | dereverb |
| Mulan _ I'll Make a Man Out of You _ @di | 47 | 11 | flat_cache | 42 | word | 0.745 | yes | 35 | dereverb |
| NSYNC - Paradise | 65 | 12 | flat_cache | 48 | line | 0.785 | yes | 51 | dereverb |
| Pocahontas - Colors of the Wind (Blu-ray | 37 | 0 | flat_cache | 35 | word | 0.946 | yes | 35 | dereverb |
| Seasons of Love (HD)---UvyHuse6buY | 34 | 9 | live_fetch | 21 | word | 0.912 | yes | 31 | vocal |
| Stay Gold (Official Music Video) from Th | 38 | 0 | bundle | 27 | word | 0.711 | yes | 27 | vocal |
| The Lion King - Hakuna Matata Music Vide | 40 | 7 | flat_cache | 19 | line | 0.625 | yes | 25 | dereverb |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 71 | 4 | flat_cache | 66 | line | 0.93 | yes | 66 | dereverb |
| Wicked - For Good  (2025) 4K - The Girl  | 36 | 5 | flat_cache | 36 | - | - | no | 0 | dereverb |

Trap 1 (audio envelope): all 18 decoded (11 off `dereverb/`, 7 off
`vocal/`); no song ran with `env=None`. Trap 2 (LRC tier): only Stay
Gold is tier 1 (`bundle`, a `.lrc` beside it); 11 are tier 2
(`flat_cache`); 6 needed tier 3 (`live_fetch`) — Defying Gravity,
Free, Popular, HUNTR/X, Domino, Seasons of Love. Trap 3 (Domino):
tier-3 live fetch succeeded (`duration=232s`, matching the absence
study's record) — the roster check below runs on **16 of 16**, not
15.

#### Table 1 — per song x cell

| stem (trunc) | cell | eligible | reason | n_candidates | n_fills | filled_lids | no_bracket | gap_disagree | outside_envelope | negative_start | collision | energy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Annivers | A0 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Defying Gravity' - Wicked 20th Annivers | A1 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Defying Gravity' - Wicked 20th Annivers | A2 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Defying Gravity' - Wicked 20th Annivers | A3 | no | no_mapping_or_global_fail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Defying Gravity' - Wicked 20th Annivers | A4 | yes | - | 30 | 0 | - | 17 | 13 | 0 | 0 | 0 | 0 |
| 'Defying Gravity' - Wicked 20th Annivers | A5 | yes | - | 30 | 0 | - | 17 | 13 | 0 | 0 | 0 | 0 |
| 'Free' _ Official Lyric Video _ Sony Ani | A0 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Free' _ Official Lyric Video _ Sony Ani | A1 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 1 | 0 |
| 'Free' _ Official Lyric Video _ Sony Ani | A2 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 1 | 0 |
| 'Free' _ Official Lyric Video _ Sony Ani | A3 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 1 | 0 |
| 'Free' _ Official Lyric Video _ Sony Ani | A4 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 1 | 0 |
| 'Free' _ Official Lyric Video _ Sony Ani | A5 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 1 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | A0 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | A1 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | A2 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | A3 | no | no_mapping_or_global_fail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | A4 | yes | - | 4 | 0 | - | 3 | 1 | 0 | 0 | 0 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | A5 | yes | - | 4 | 0 | - | 3 | 1 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | A0 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | A1 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | A2 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | A3 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | A4 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | A5 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | A0 | yes | - | 8 | 3 | 89,93,95 | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | A1 | yes | - | 7 | 7 | 81,86,87,89,93,94,95 | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | A2 | yes | - | 8 | 5 | 86,89,93,94,95 | 0 | 0 | 0 | 0 | 3 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | A3 | yes | - | 8 | 7 | 81,86,87,89,93,94,95 | 0 | 0 | 0 | 0 | 1 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | A4 | yes | - | 8 | 5 | 86,89,93,94,95 | 0 | 0 | 0 | 0 | 3 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | A5 | yes | - | 8 | 7 | 81,86,87,89,93,94,95 | 0 | 0 | 0 | 0 | 1 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | A0 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | A1 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | A2 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | A3 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | A4 | yes | - | 1 | 1 | 32 | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | A5 | yes | - | 1 | 1 | 32 | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | A0 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | A1 | yes | - | 16 | 0 | - | 0 | 0 | 0 | 0 | 4 | 12 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | A2 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | A3 | yes | - | 16 | 0 | - | 16 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | A4 | yes | - | 9 | 0 | - | 9 | 0 | 0 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | A5 | yes | - | 17 | 0 | - | 17 | 0 | 0 | 0 | 0 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (M | A0 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (M | A1 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (M | A2 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (M | A3 | no | no_mapping_or_global_fail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (M | A4 | yes | - | 15 | 0 | - | 15 | 0 | 0 | 0 | 0 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (M | A5 | yes | - | 15 | 0 | - | 15 | 0 | 0 | 0 | 0 | 0 |
| Jessie J - Domino (Official Video)---UJt | A0 | yes | - | 4 | 1 | 66 | 0 | 0 | 0 | 0 | 0 | 0 |
| Jessie J - Domino (Official Video)---UJt | A1 | yes | - | 4 | 1 | 66 | 0 | 0 | 0 | 0 | 3 | 0 |
| Jessie J - Domino (Official Video)---UJt | A2 | yes | - | 4 | 0 | - | 2 | 2 | 0 | 0 | 0 | 0 |
| Jessie J - Domino (Official Video)---UJt | A3 | yes | - | 4 | 0 | - | 2 | 2 | 0 | 0 | 0 | 0 |
| Jessie J - Domino (Official Video)---UJt | A4 | yes | - | 4 | 0 | - | 2 | 2 | 0 | 0 | 0 | 0 |
| Jessie J - Domino (Official Video)---UJt | A5 | yes | - | 4 | 0 | - | 2 | 2 | 0 | 0 | 0 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing | A0 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing | A1 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing | A2 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing | A3 | yes | - | 1 | 1 | 16 | 0 | 0 | 0 | 0 | 0 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing | A4 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing | A5 | yes | - | 1 | 1 | 16 | 0 | 0 | 0 | 0 | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | A0 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | A1 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | A2 | no | arm_a_bail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | A3 | no | no_mapping_or_global_fail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | A4 | yes | - | 9 | 0 | - | 2 | 4 | 0 | 0 | 3 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | A5 | yes | - | 9 | 0 | - | 2 | 4 | 0 | 0 | 3 | 0 |
| NSYNC - Paradise | A0 | yes | - | 6 | 2 | 1,39 | 0 | 0 | 0 | 0 | 0 | 0 |
| NSYNC - Paradise | A1 | yes | - | 5 | 1 | 39 | 0 | 0 | 0 | 0 | 4 | 0 |
| NSYNC - Paradise | A2 | yes | - | 6 | 1 | 39 | 4 | 0 | 0 | 0 | 1 | 0 |
| NSYNC - Paradise | A3 | yes | - | 7 | 2 | 39,42 | 4 | 0 | 0 | 0 | 1 | 0 |
| NSYNC - Paradise | A4 | yes | - | 6 | 1 | 39 | 4 | 0 | 0 | 0 | 1 | 0 |
| NSYNC - Paradise | A5 | yes | - | 7 | 2 | 39,42 | 4 | 0 | 0 | 0 | 1 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | A0 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | A1 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | A2 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | A3 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | A4 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray | A5 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | A0 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | A1 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | A2 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | A3 | no | no_mapping_or_global_fail | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | A4 | yes | - | 6 | 0 | - | 6 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | A5 | yes | - | 8 | 0 | - | 6 | 2 | 0 | 0 | 0 | 0 |
| Stay Gold (Official Music Video) from Th | A0 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Stay Gold (Official Music Video) from Th | A1 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Stay Gold (Official Music Video) from Th | A2 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Stay Gold (Official Music Video) from Th | A3 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Stay Gold (Official Music Video) from Th | A4 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| Stay Gold (Official Music Video) from Th | A5 | yes | - | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| The Lion King - Hakuna Matata Music Vide | A0 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| The Lion King - Hakuna Matata Music Vide | A1 | yes | - | 1 | 0 | - | 0 | 0 | 0 | 0 | 0 | 1 |
| The Lion King - Hakuna Matata Music Vide | A2 | no | slope_dev | 0 | 0 | - | 0 | 0 | 0 | 0 | 0 | 0 |
| The Lion King - Hakuna Matata Music Vide | A3 | yes | - | 1 | 0 | - | 1 | 0 | 0 | 0 | 0 | 0 |
| The Lion King - Hakuna Matata Music Vide | A4 | yes | - | 2 | 0 | - | 2 | 0 | 0 | 0 | 0 | 0 |
| The Lion King - Hakuna Matata Music Vide | A5 | yes | - | 2 | 0 | - | 2 | 0 | 0 | 0 | 0 | 0 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | A0 | yes | - | 4 | 3 | 63,64,65 | 0 | 0 | 0 | 0 | 0 | 0 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | A1 | yes | - | 4 | 3 | 63,64,65 | 0 | 0 | 0 | 0 | 0 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | A2 | yes | - | 4 | 3 | 63,64,65 | 0 | 0 | 0 | 0 | 0 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | A3 | yes | - | 4 | 3 | 63,64,65 | 0 | 0 | 0 | 0 | 0 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | A4 | yes | - | 4 | 3 | 63,64,65 | 0 | 0 | 0 | 0 | 0 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | A5 | yes | - | 4 | 3 | 63,64,65 | 0 | 0 | 0 | 0 | 0 | 1 |
| Wicked - For Good  (2025) 4K - The Girl  | A0 | yes | - | 5 | 3 | 15,32,33 | 0 | 0 | 0 | 1 | 0 | 0 |
| Wicked - For Good  (2025) 4K - The Girl  | A1 | yes | - | 5 | 3 | 15,32,33 | 0 | 0 | 0 | 1 | 1 | 0 |
| Wicked - For Good  (2025) 4K - The Girl  | A2 | yes | - | 5 | 0 | - | 3 | 0 | 0 | 0 | 2 | 0 |
| Wicked - For Good  (2025) 4K - The Girl  | A3 | yes | - | 5 | 0 | - | 3 | 0 | 0 | 0 | 2 | 0 |
| Wicked - For Good  (2025) 4K - The Girl  | A4 | yes | - | 5 | 0 | - | 3 | 0 | 0 | 0 | 2 | 0 |
| Wicked - For Good  (2025) 4K - The Girl  | A5 | yes | - | 5 | 0 | - | 3 | 0 | 0 | 0 | 2 | 0 |

#### Table 2 — the 16-good roster (Belle 5, Girl in the Bubble 5, Next Ten Minutes 3, NSYNC 2, Domino 1)

`present` = identical to A0's own time in this run; `moved` shows the
differing time; `absent` = not in that cell's filled lids. Baseline is
this run's own A0, not the historical study (see the validity note
above).

| stem (trunc) | lid | A0 time | A0 | A1 | A2 | A3 | A4 | A5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Beauty and the Beast (1991) - Belle [UHD | 81 | ABSENT-IN-A0 | absent | moved(252.260-252.459) | absent | moved(252.400-252.599) | absent | moved(252.400-252.599) |
| Beauty and the Beast (1991) - Belle [UHD | 86 | ABSENT-IN-A0 | absent | moved(255.390-255.505) | moved(255.865-256.625) | moved(255.531-255.645) | moved(255.865-256.625) | moved(255.531-255.645) |
| Beauty and the Beast (1991) - Belle [UHD | 89 | 259.550-259.720 | present | moved(257.168-257.250) | moved(259.045-259.215) | moved(257.308-257.390) | moved(259.045-259.215) | moved(257.308-257.390) |
| Beauty and the Beast (1991) - Belle [UHD | 93 | 260.890-261.690 | present | moved(259.613-259.728) | moved(260.525-261.325) | moved(259.729-259.844) | moved(260.525-261.325) | moved(259.729-259.844) |
| Beauty and the Beast (1991) - Belle [UHD | 94 | ABSENT-IN-A0 | absent | moved(260.315-260.413) | moved(261.325-261.665) | moved(260.431-260.529) | moved(261.325-261.665) | moved(260.431-260.529) |
| Jessie J - Domino (Official Video)---UJt | 66 | 222.316-226.316 | present | present | absent | absent | absent | absent |
| NSYNC - Paradise | 1 | 40.785-41.985 | present | absent | absent | absent | absent | absent |
| NSYNC - Paradise | 39 | 183.245-185.345 | present | moved(183.222-185.322) | moved(183.155-185.255) | moved(183.149-185.249) | moved(183.155-185.255) | moved(183.149-185.249) |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 63 | 330.777-332.177 | present | present | moved(331.173-332.573) | moved(331.173-332.573) | moved(331.173-332.573) | moved(331.173-332.573) |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 64 | 334.127-335.527 | present | present | moved(334.523-335.923) | moved(334.523-335.923) | moved(334.523-335.923) | moved(334.523-335.923) |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 65 | 337.167-338.567 | present | present | moved(337.563-338.963) | moved(337.563-338.963) | moved(337.563-338.963) | moved(337.563-338.963) |
| Wicked - For Good  (2025) 4K - The Girl  | 8 | ABSENT-IN-A0 | absent | absent | absent | absent | absent | absent |
| Wicked - For Good  (2025) 4K - The Girl  | 15 | 65.362-68.162 | present | present | absent | absent | absent | absent |
| Wicked - For Good  (2025) 4K - The Girl  | 32 | 143.272-146.072 | present | present | absent | absent | absent | absent |
| Wicked - For Good  (2025) 4K - The Girl  | 33 | 148.662-151.462 | present | present | absent | absent | absent | absent |
| Wicked - For Good  (2025) 4K - The Girl  | 35 | ABSENT-IN-A0 | absent | absent | absent | absent | absent | absent |

Note: lid 81/86/89/93/94 are ABSENT-IN-A0 or present per the validity
note above (81/86/94 are unplaced candidates in this run but do not
survive A0's collision check — see line 95 below); lid 8/35 are
ABSENT-IN-A0 because this run's matcher places them directly (no
longer unplaced at all).

#### Table 3 — fills beyond A0 (union of A1..A5 minus A0)

| stem (trunc) | lid | text | source | cells | t0 | t1 | bracket_lo | bracket_hi | gap_audio | gap_cue | gap_delta | collision | energy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Beauty and the Beast (1991) - Belle [UHD | 81 | Bonjour | sidecar_fill | A1 | 252.260 | 252.459 | - | - | - | - | - | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 81 | Bonjour | sidecar_fill | A3,A5 | 252.400 | 252.599 | 76 | 92 | 25.58 | 25.437 | 0.143 | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 86 | What lovely grapes | lrclib_fill | A2,A4 | 255.865 | 256.625 | 79 | 92 | 14.5 | 15.51 | -1.01 | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 86 | What lovely grapes | sidecar_fill | A1 | 255.390 | 255.505 | - | - | - | - | - | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 86 | What lovely grapes | sidecar_fill | A3,A5 | 255.531 | 255.645 | 76 | 92 | 25.58 | 25.437 | 0.143 | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 87 | Some cheese | sidecar_fill | A1 | 256.133 | 256.718 | - | - | - | - | - | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 87 | Some cheese | sidecar_fill | A3,A5 | 256.274 | 256.858 | 76 | 92 | 25.58 | 25.437 | 0.143 | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 94 | Those fish | lrclib_fill | A2,A4 | 261.325 | 261.665 | 92 | 103 | 15.26 | 13.97 | 1.29 | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 94 | Those fish | sidecar_fill | A1 | 260.315 | 260.413 | - | - | - | - | - | False | PASS |
| Beauty and the Beast (1991) - Belle [UHD | 94 | Those fish | sidecar_fill | A3,A5 | 260.431 | 260.529 | 92 | 101 | 7.74 | 7.932 | -0.192 | False | PASS |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 32 | Da-dum, da-dum, da-dum, da-dum | lrclib_fill | A4,A5 | 190.323 | 193.124 | 29 | 34 | 33.873 | 35.08 | -1.207 | False | PASS |
| Josh Gad - In Summer (From 'Frozen'_Sing | 16 | Bad-dah, da-doo, uh-bah-bah-bah-bah-bah- | sidecar_fill | A3,A5 | 53.905 | 56.005 | 15 | 17 | 8.39 | 9.44 | -1.05 | False | PASS |
| NSYNC - Paradise | 42 | Paradise | sidecar_fill | A3,A5 | 192.749 | 193.663 | 38 | 44 | 24.28 | 24.484 | -0.204 | False | PASS |

#### Table 4 — tolerance sensitivity (diagnostic only, fill counts per song per cell)

Cell A2:

| stem (trunc) | tol=1.0 | tol=1.5 | tol=2.0 | tol=3.0 |
| --- | --- | --- | --- | --- |
| Beauty and the Beast (1991) - Belle [UHD | 0 | 5 | 5 | 5 |
| NSYNC - Paradise | 1 | 1 | 1 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 3 | 3 | 3 | 3 |

Cell A3:

| stem (trunc) | tol=1.0 | tol=1.5 | tol=2.0 | tol=3.0 |
| --- | --- | --- | --- | --- |
| Beauty and the Beast (1991) - Belle [UHD | 7 | 7 | 7 | 7 |
| Josh Gad - In Summer (From 'Frozen'_Sing | 0 | 1 | 1 | 1 |
| NSYNC - Paradise | 2 | 2 | 2 | 2 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 3 | 3 | 3 | 3 |

Cell A4:

| stem (trunc) | tol=1.0 | tol=1.5 | tol=2.0 | tol=3.0 |
| --- | --- | --- | --- | --- |
| Beauty and the Beast (1991) - Belle [UHD | 0 | 5 | 5 | 5 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 0 | 1 | 1 | 1 |
| NSYNC - Paradise | 1 | 1 | 1 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 3 | 3 | 3 | 3 |

Cell A5:

| stem (trunc) | tol=1.0 | tol=1.5 | tol=2.0 | tol=3.0 |
| --- | --- | --- | --- | --- |
| Beauty and the Beast (1991) - Belle [UHD | 7 | 7 | 7 | 7 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 0 | 1 | 1 | 1 |
| Josh Gad - In Summer (From 'Frozen'_Sing | 0 | 1 | 1 | 1 |
| NSYNC - Paradise | 2 | 2 | 2 | 2 |
| Seasons of Love (HD)---UvyHuse6buY | 0 | 0 | 0 | 2 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 3 | 3 | 3 | 3 |

All other songs are flat at 0 across the whole grid (omitted). Matches
the design pass's own reading that the tolerance is nearly inert on
this corpus.

#### Table 5 — Bloodstream's unplaced block (lids 44-50)

| lid | A0 | A1 | A2 | A3 | A4 | A5 |
| --- | --- | --- | --- | --- | --- | --- |
| 44 | not_a_candidate | refused:energy | not_a_candidate | refused:no_bracket | refused:no_bracket | refused:no_bracket |
| 45 | not_a_candidate | refused:energy | not_a_candidate | refused:no_bracket | refused:no_bracket | refused:no_bracket |
| 46 | not_a_candidate | refused:energy | not_a_candidate | refused:no_bracket | refused:no_bracket | refused:no_bracket |
| 47 | not_a_candidate | refused:energy | not_a_candidate | refused:no_bracket | refused:no_bracket | refused:no_bracket |
| 48 | not_a_candidate | refused:energy | not_a_candidate | refused:no_bracket | refused:no_bracket | refused:no_bracket |
| 49 | not_a_candidate | refused:energy | not_a_candidate | refused:no_bracket | refused:no_bracket | refused:no_bracket |
| 50 | not_a_candidate | not_a_candidate | not_a_candidate | not_a_candidate | not_a_candidate | not_a_candidate |

`not_a_candidate` = no cue in that cell's source(s) at all (lid 50 has
no cue in either source; the other six have a cue only in the
sidecar, so A0/A2 — LRCLIB-only — never see them as candidates).
A1 reaches all six via the sidecar (its song-level pick, table 6) but
every one refuses on the shipped energy check (`void`) before collision
is even reached. Every per-gap cell refuses all six on `no_bracket` —
lids 44-49 fall in a stretch with no corroborated, cue-carrying anchor
on either side.

#### Table 6 — Bloodstream global arm-A/B per source (real anchors)

| source | n_cues | armA_n_anchors | armA_bail | armA_offset_s | armA_mad_s | armB(slope) | global |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lrclib | 37 | 11 | PASS | -11.09 | 0.6 | PASS slope=1.0144 mad=0.286 | ineligible(slope_dev) |
| sidecar | 52 | 11 | PASS | -10.23 | 0.28 | PASS slope=1.0036 mad=0.382 | eligible |

Settles the two conflicting prior claims without reconciling them in
prose, per the design: on real anchors, arm B's own `wide_spread` check
(`WARP_MAD_GATE_S` 2.0) **passes** for both sources (mad 0.286/0.382,
nowhere near the design-pass proxy's inflated 4.65/4.82) — so the
2026-09-10 Fable round's "clears both global gates" is closer than the
proxy's "arm B wide_spread". But LRCLIB's slope (1.0144) sits outside
`FILL_MAX_SLOPE_DEV` (0.01) of unity, so the combined `_eligibility`
check still bails, on `slope_dev` rather than either prior claim's
reason. Sidecar's slope (1.0036) clears it, which is why A1 (table 1)
is eligible for Bloodstream at the song level even though A0 is not —
and why table 5 shows the block reaching the energy check at all under
A1.

### 2026-09-11 — GATE G read-off (Opus) — NO-GO; ratified by Ken

Read against the pre-registered rules of the 2026-09-10 design section,
on the executor's tables of the same day plus `phase5_out/results.json`
and the four eyeball pairs. No cell was re-run and no table recomputed;
the checks below that go past the tables are reads of artifacts already
on disk. **Ken ratified the validity ruling and the outcome 2026-09-11.**

#### Validity — PROCEED, roster re-baselined (not void)

Two corrections to the executor's validity note first, both factual:

- **A0 reproduces 11 of the 16 roster fills, not 12.** Five roster lids
  are absent from A0: Belle 81/86/94 and Girl in the Bubble 8/35. The
  entry's own prose lists all five and sums them as four.
- **The single traced cause covers only two of the five.** GATE T's
  ytasr candidate-ratio change explains Girl in the Bubble; it does not
  explain Belle.

Girl in the Bubble 8 and 35 — **verified against the record**. GATE T's
Finding 3 diffed the ratio change line by line and names exactly `line
8` (29.64–34.29, align) and `line 35` (175.36–181.90, ytasr) as the two
lines For Good gains at 0.45. Ken eyeballed both and shipped the ratio
2026-09-10. This run's `line_objects_placed` for that song contains both
lids, so they are matcher placements now and not fill candidates at all.

Belle 81/86/94 — **not the ratio.** GATE T's own finding is that the
ratio's whole corpus-level effect is one song. The two other candidate
causes were checked and ruled out:

- the bundle is unchanged across the 2026-07-16 regen — identical placed
  set (101/110), identical `selected_source` vector, one 20 ms end shift
  on lid 105 (`regen_backup_20260716T204310Z` vs current);
- the flat-cache LRC for Belle is untouched since 2026-06-11.

What did change is the fill/anchor code path. The absence study ran
**2026-07-12** on a standalone prototype; `windowed_realign` took two
corroboration changes on **07-13** (`6a73386`) and **07-14** (`72a93d0`),
and `pikaraoke/lib/lrclib_fill.py` did not exist until **07-17**
(`6a8153d`, hardened `e355024`). The signature is in the arm-A fit —
the study recorded **39 anchors at −5.79 s**, this run has **55 anchors
at −4.54 s**. A 1.25 s shift in fill placement is what flips Belle's
collision outcomes: 81/86/94 now collide, 95 no longer does. *No single
commit was isolated by counterfactual; what is established is that the
cause is neither the ratio nor the bundle.*

**Ruling.** The validity clause tests whether the harness is faithful to
production. It is: A0 is shipped `plan_fills`, called unmodified, on
current bundles at current knobs, and reproduces what production does
**today**. What has moved is the reference — the 16-good roster is a
2026-07-12 measurement taken against code that has since been reviewed,
shipped, and in the Girl in the Bubble case eyeballed by Ken personally.
Voiding on a stale reference would discard a valid run. **Proceed, with
this run's A0 (12 fills) as the operative baseline.**

#### Mechanism note — the executor's reading is correct

Item 3 defines the per-gap gate as refusal conditions *and* slope-1
placement at the local offset, in one mechanism; its third bullet
("Otherwise place at slope 1 with `local_offset` = …") is unconditional
and the filter-only reading would make it dead text. The recorded
`local_offset` values match the formula against the per-song fits. Table
3's `t0`/`t1` are trustworthy as reported.

#### Two design defects, both pre-registered 2026-09-10 (Opus)

**D1 — the envelope rule and the survival bar are mutually
unsatisfiable.** Scope item 2, carried into design item 3, states the
envelope rule "is what refuses Domino". Scope item 5 and the PASS
criterion require that the 16 existing good fills survive unchanged, and
**Domino 66 is one of the 16**. No cell carrying the per-gap gate could
ever have passed, independent of any data. The run shows it firing as
specified: Domino 66 refuses on `no_bracket` in A2–A5.

**D2 — item 4's "only ever removes" claim is false.** Item 4 asserts the
per-gap gate only removes fills relative to the same source under the
global gate, "which is what makes 'the 16 must survive' a one-sided
read." Because item 3 also *places*, the per-gap cells move fills, and a
moved fill can newly collide: Girl in the Bubble lid 15 is clean at A0's
global offset (−23.148) and collides at the local offset (−24.16). The
per-gap cells are **not** subsets of the global cells and the roster
check is two-sided.

#### Criterion (i) — roster/A0 survival per cell

Baseline is this run's A0: Belle 89/93/95, Domino 66, NSYNC 1/39, Next
Ten 63/64/65, Girl in the Bubble 15/32/33 (12 fills).

| cell | A0 fills lost | A0 fills moved |
| --- | --- | --- |
| A1 | NSYNC 1 | Belle 89 (−2.38 s), 93 (−1.28 s, 800→115 ms), 95 (−1.13 s), NSYNC 39 (−23 ms) |
| A2 | Domino 66, NSYNC 1, Girl 15/32/33 | Belle 89/93/95 (−0.37 to −0.51 s), NSYNC 39 (−90 ms), Next Ten 63/64/65 (+396 ms) |
| A3 | Domino 66, NSYNC 1, Girl 15/32/33 | Belle 89 (−2.24 s), 93 (−1.16 s), 95 (−1.02 s), NSYNC 39 (−96 ms), Next Ten 63/64/65 (+396 ms) |
| A4 | as A2 | as A2 |
| A5 | as A3 | as A3 |

Refusal reasons for the losses: NSYNC 1 `no_bracket` (first line, no
anchor before it) in A2–A5 and `collision` in A1; Domino 66
`no_bracket` (near the end, no anchor after it); Girl in the Bubble 15
`collision` at the local offset, 32/33 `no_bracket`.

**Every cell fails criterion (i), on losses as well as on moves** — so
the result does not depend on whether "present with identical times" is
read strictly or leniently.

#### Criterion (iii) — Bloodstream: satisfied by every cell

No cell fills any of lids 44–50. A1 reaches all six through the sidecar
and every one refuses on the **shipped energy check**; every per-gap
cell refuses on `no_bracket`. The named risk case did not fire, and what
held it was the existing gate, not the new one.

#### Criterion (ii) — the eyeball: not reached

Criterion (i) fails for every cell before quality is assessed. The
13-fill packet was checked row-for-row against `results.json` and is
exactly table 3 — 7 distinct lids across 4 songs (Belle 81/86/87/94,
Best Part Of Me 32, In Summer 16, NSYNC 42), 13 rows because some lids
appear at two times under different sources. It is complete against its
own spec. It is **not** the full set of timing changes: it omits the 7
A0 fills that move and the 5 that disappear. No eyeball verdict on it
would change any branch below.

#### The branch walk

1. **Does not fire** — PASS(A3) is false.
2. **Does not fire** — PASS(A3) is false.
3. **Does not fire** — PASS(A1) is false.
4. **FIRES. Neither A1 nor A3 passes → the widening does not ship and
   the LRCLIB-only fill stays exactly as it is.** The separate
   sub-clause requires PASS(A2) *and* "A2 loses no good fill"; A2 fails
   both, losing five. **The per-gap gate does not ship on the LRCLIB
   source alone either.**
5. **A4/A5 reported.** A4 adds Belle 86/94 and Best Part Of Me 32; A5
   adds Belle 81/86/87/94, Best Part Of Me 32, In Summer 16 and NSYNC
   42. Both drop the global fit and both lose the same five good fills.
   Adopting either remains Ken's alone; nothing in these numbers argues
   for it.
6. **Fires on A1 (4 fills beyond A0), A2 (2) and A4 (3)** — under the
   5-fill line, reported not read. A3 (6) and A5 (7) clear it. Stated
   plainly as the rule requires: **even with criterion (i) waived, this
   corpus did not exercise the A1 question** — the named risk cell
   produced four new fills, all on one song.
7. **Two STOP → Ken items**, both raised and both ruled the same day:
   the validity question above, and defects D1/D2 — this gate was
   unwinnable as written, which is a design failure and not a verdict
   of the corpus against the mechanism.

#### Rulings (Ken, 2026-09-11)

1. **Validity ruling ratified.** The run is valid; the 16-good roster is
   superseded as a live reference by this run's A0.
2. **GATE G is NO-GO.** The fill's source is **not** widened to the
   fetch sidecar. `pikaraoke/lib/lrclib_fill.py` is unchanged: LRCLIB
   cue source, per-song offset+slope gate, as shipped.
3. **The per-gap gate does not ship**, neither as a guard on the widened
   source nor standing alone on LRCLIB.
4. **No production change comes out of Phase 5.** No commit carries a
   mechanism, constant or config change. The drivers
   (`phase5_mechanism.py` / `phase5_run.py` / `phase5_tables.py`) stay
   in the session scratchpad and are not committed.

#### What this read-off does NOT claim

- It does not claim the per-gap idea is wrong. D1 means the gate was
  measured against a bar it was specified to violate, so the corpus
  never got to answer whether bracketing anchors separate sound timing
  from wrong-edit timing. Re-opening it needs a survival bar that does
  not contain its own counterexample — a new design pass and a new gate
  letter, not an amendment to this one.
- It does not claim the sidecar is a bad cue source. A1's four new fills
  are below the design's own "nothing to see" line; the widening was
  refused on roster survival, never on fill quality.
- It does not re-price the DP-candidate form. That ban is untouched.

#### Loose ends recorded, not actioned

- **The 16/0 record no longer describes production.** Today's shipped
  fill produces Belle 95, which no eyeball has ever seen, and does not
  produce Belle 81/86/94. Re-taking the roster on current code is its
  own small job; it is not GATE G's and it is not blocking.
- **Table 1's A0 rows under-report refusals** — the collision and energy
  columns read 0 where the per-line records carry them (Belle 5
  collisions, Domino 3, NSYNC 4, Next Ten 1 energy bail); the
  `negative_start` column is populated. A1–A5 rows are consistent. A
  reporting gap in `phase5_tables.py`, not in the run; the underlying
  records in `results.json` are complete.

#### Addendum 2026-09-11 — the moved fills were eyeballed after all; Ken: a wash

The read-off above closed without the eyeball, and flagged one residual
uncertainty: the per-gap gate's whole claim is that a *local* offset
places better than the global one, so a re-placed roster fill might be
the mechanism succeeding while the survival bar scored it as failure.
That was the one question Opus could not resolve from the tables, and
the one place a Fable round was going to be suggested.

It was tested directly instead. Every fill the per-gap cells move was
rendered against the shipped placement — Belle 89/93/95, NSYNC Paradise
39, Next Ten Minutes 63/64/65, each line shown at the shipped time, the
per-gap time and (Belle) the per-gap-plus-sidecar time simultaneously,
so the comparison is one look rather than a remembered timestamp.
Comparison renders live beside the production ones as
`karaoke/<stem>.moved.ass`; they are inert unless loaded as a subtitle
track, and no production `<stem>.ass` was touched.

**Ken's verdict: a wash — the changes are too small to be worth the
added complexity.** The per-gap placement is neither better nor worse
than the shipped global offset on the lines where the two differ.

**Consequence.** The survival bar did not hide a result. GATE G's NO-GO
now rests on the mechanism buying nothing, not only on a bar that
contained its own counterexample, and **no Fable round is owed**. The
two design defects recorded above stand as defects — they are why the
run could not have produced a clean pass — but correcting them would
not have changed the outcome, because the fills the gate would have
saved are indistinguishable from the ones already shipping.

**Weight, stated honestly:** the eyeball covers seven lines on three
songs, which is thin. It is not evidence that local-offset placement is
worthless in general. It is evidence that on this corpus the per-gap
gate produced almost no new fills *and* no better placement of the
existing ones — so a re-attempt must argue it would do better than a
wash, not merely that the bar was wrong.

### 2026-09-14 — Phase 6 design pass (Opus) — pre-registration written, gate letter GATE W assigned; nothing run

Ken asked for the design. No probe ran, no measurement was taken, no
number below came from data — the design block sits in Phase 6 above
and this entry records only what was verified against shipped code and
the two decisions that changed the assessment's probe order.

**Verified against the tree at `joint_catchall_refit`** (read-only; all
claims the design leans on, checked rather than inherited):

| Claim | Where | Holds |
| --- | --- | --- |
| Seam is veto → snap → **here** → fill → generate | `lyric_align.py:246-256` | yes |
| `env` already decoded and shared at that seam | same | yes — new cost is the emission only |
| `apply_fills` runs after the snap | `lyric_align.py:256-257` | yes — fills are never snapped or refined |
| `align_ranges` computed for every line, not only align candidates | `joint_match.py:167` | yes — the zero-model form has reach |
| `_range_agreement` returns 1.0 on a collapsed reference instant | `joint_match.py:657-677` | yes |
| the pace guard that distinguishes it | `_MIN_ALIGN_PACE_S = 0.06`, `joint_match.py:88` | yes |
| `selected_source` is per line id, values align/transcribe/ytasr/interp | bundle `joint_stats` | yes, length `n_lines` |
| `output_line_timings` carries line start/end/n_words only | `alignment_capture.py:206-223` | yes |
| `make_slice_align` caches one emission per song, slices by frame | `scripts/sb_ctc_adapter.py:51-98` | yes |
| emission cache under `get_temp_directory()` | `phase1b_score_oracle.py:47-48` | yes |
| `MIN_WORD_DUR_S` for the monotonicity refusal | `onset_snap.py:59` = 0.1 | yes |

**Cohort, counted from disk, no measurement:** `alignment_debug/` holds
34 captures — **18 joint-matcher** (their `joint_stats` carries
`pass1_line_timings`) and **16 cue-route**. That is the split the
assessment assumed and it reproduces. All 34 songs have a vocal stem;
24 also have a dereverb stem. Eleven songs carry a `.en.asr.json3`.

**Two corrections to the assessment's probe order, both load-bearing.**

1. **Step 3 arm (b) must replay the edge snap.** The existing replay
   harness (`scripts/replay_ytasr_third_source.py`) deliberately does
   *not* — its own docstring records that it never touches the vocal
   stem, so the bundle's post-snap `output_line_timings` is a sanity
   column only. But this phase is pre-registered to run *after* the
   snap and to use the snapped span as its constraint window, so a
   snap-free replay hands CTC the wrong window on exactly the lines the
   snap moved (21–32% of this population). Step 3 already needs the
   stem for the emission, so the snap replays there at no extra decode.
   With it comes a **fidelity guard**: the replay must reproduce the
   recorded `output_line_timings` exactly on every line of all 18 songs
   before any CTC runs, else STOP. GATE G was read on a harness that
   reproduced only part of its own reference and the discrepancy
   surfaced at the read rather than at the run.
2. **Step 2 gains control looks.** The assessment's 20 looks at current
   output cannot distinguish "these interiors are bad" from "all
   interiors are a bit loose," and that distinction decides whether the
   phase is aimed at anything. Eight unlabelled align-won lines join
   the sitting (28 looks), with a declared STOP if they score as badly
   as the target population.

**One thing S-C does not give this phase.** Its four eyeball songs
(Mirrors, ZAYN's Whole New World, Part of Your World, Bye Bye Bye) are
all cue-route songs and **none is in the joint 18**, so the
overlapping-voices warning carries as a statement about the mechanism
and not as a song list. The ensemble stratum's list is therefore fixed
in the design from this cohort on a stated rule (sustained simultaneous
voices), with the two considered-and-excluded songs named so the list
reads as a rule rather than a fit.

**Also fixed in the design, and recorded here because they are the
places a later reader will ask "who chose that":** τ = 0.5 for whisper
agreement; the 15% population floor that can stop the phase at step 1
before any GPU spend; the 70% / 10% zero-model thresholds; the cram
floor at 0.05 s; the bimodality test (KDE on log|Δ|, Scott bandwidth,
trough at ≤ 0.6× the lower flanking mode with ≥ 15% mass each side);
`seed = 20260914`; the strata, the look counts and the read-off rules.
All pre-registered, none of them fitted to anything — no data exists.

**Explicitly not done here:** step 1 was **not** run, though it is
GPU-free and its inputs are all present. Running it during the design
pass would have set its kill thresholds with the answer in view, which
is the move this program forbids. The executor runs it.

**Next:** Sonnet 5 implements and runs step 1, reports the table, and
stops. Opus reads W-1a/b/c only.

### 2026-09-14 — Phase 7 executor run (Sonnet) — unplaced-population tables, GATE P validation case failed: STOP → Ken

Ran the probe designed above (§"Phase 7", this file) over the 18
joint-matcher captures in `D:/shared/pikaraoke-songs/alignment_debug/`
(bundles whose `joint_stats` carries `pass1_line_timings`; 16 cue-route
captures skipped). No GPU, no audio, no inference: the driver replays
only `pikaraoke.lib.candidate_match.find_candidates` /
`find_anchor_candidates` over each bundle's own captured
`transcribe_words` and parsed ytasr caption words, at the bundle's own
recorded `joint_max_edit_ratio` for whisper and the current shipped
`ytasr.CANDIDATE_MAX_EDIT_RATIO` (0.45) for captions — never unified,
per the design. Population (unplaced lines) is read directly from each
bundle's own captured `selected_source` / `absent_line_ids`, not
recomputed. Driver + tables generator live in the session scratchpad
(`phase7_run.py`, `phase7_tables.py`), not committed.

**Three cross-checks the design didn't ask for but that came free, all
consistent.** Eight of the 18 songs carry no adopted caption, matching
the design's own pre-stated count exactly (§"The population" above).
Pooled `n_lines` across the 18 is 610 + 400 = 1010, matching Phase 4's
own denominator ("211/1010 lines," 2026-09-01 entry above) exactly. And
the whisper-side replay (`n_main_candidates` / `n_anchor_candidates`) is
asserted equal to each bundle's own recorded count in code, hard —
the run completed with no assertion failures across all 18 songs, so
this replay is the shipped scan, not an approximation. (The ytasr-side
candidate count is not cross-checked the same way: GATE T raised
`ytasr.CANDIDATE_MAX_EDIT_RATIO` 0.34→0.45 after these bundles were
captured, and this probe is pinned to the current constant per the
design's own "shipped code" framing — a divergence from each bundle's
recorded `n_ytasr_candidates` is expected and does not affect per-line
set membership, which is all the classification uses.)

**GATE P validation case: fails by the letter of the pre-registered
rule. STOP, not resolved here.** Table 5 below is the one place the
design pre-registered a check against something already established:
"If those blocks do not come back predominantly U-1, the method is
wrong and that is a STOP → Ken." The raw result:

- Bloodstream (lids 44–50): 0/7 U-1. Six lines U-2, one U-3
  (cross-attraction).
- HUNTR/X (lids 40–52): 1/11 U-1 (two of the thirteen named lids are
  actually placed, not in the population at all). Ten of the remaining
  eleven are U-3 (cross-attraction).

That is the opposite of "predominantly U-1." Before this is read as a
plain failure, the GATE P read-off already on record above (2026-09-01
entry, "GATE P read-off (Fable)") is worth reading against it: that
entry's own diagnosis of these exact two blocks is repeat
cross-attraction, not silence — "Bloodstream lines repeatedly at
133.84/160.39/222.92 s," "HUNTR/X lines 33/35/37 all at 54.54 s," and
explicitly: "Their unplaced blocks (Bloodstream 44–50, HUNTR/X 40–52)
are sheets that do not match the audio version — the lever there is
upstream lyric-version/length matching per the repeat-pileup diagnosis,
not DP ordering." This phase's own classification text names the
identical mechanism for its U-3-cross sub-split: "cross-attraction /
repeat pile-up, already diagnosed at GATE P." Both entries are naming
the same phenomenon on the same two songs.

**What this executor is not doing:** deciding whether the pre-registered
validation rule's premise (that a lyric-version-drift block should read
as U-1) was correct, deciding whether U-3-cross should count as a pass
for a repeat-heavy drift block, or amending the rule. That is exactly
the "looks wrong → STOP, not an amendment" case from this run's own
brief. The five tables below are reported as designed regardless of
this outcome — Table 5 carries the full per-line detail behind both
counts above.

#### Table 1 — per song

| song | n_lines | n_placed | n_unplaced | ytasr | U-0 | U-1@shipped | U-1@0.6 | U-2 | U-3(cross) | U-3(own) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 89 | 51 | 38 | Y | 0 | 31 | 36 | 7 | 0 | 0 |
| 'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q | 41 | 40 | 1 | N | 0 | 0 | 0 | n/a (no ytasr) | 1 | 0 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | 62 | 53 | 9 | Y | 0 | 5 | 7 | 2 | 2 | 0 |
| Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8 | 77 | 77 | 0 | Y | 0 | 0 | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | 110 | 102 | 8 | Y | 0 | 7 | 7 | 1 | 0 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 38 | 37 | 1 | Y | 0 | 1 | 1 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 74 | 53 | 21 | Y | 0 | 1 | 2 | 12 | 8 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA | 53 | 35 | 18 | N | 0 | 4 | 5 | n/a (no ytasr) | 14 | 0 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | 67 | 63 | 4 | N | 0 | 3 | 3 | n/a (no ytasr) | 1 | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY | 31 | 29 | 2 | N | 0 | 2 | 2 | n/a (no ytasr) | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 47 | 36 | 11 | Y | 0 | 2 | 2 | 0 | 9 | 0 |
| NSYNC - Paradise | 65 | 53 | 12 | N | 0 | 7 | 8 | n/a (no ytasr) | 4 | 1 |
| Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76peOw0 | 37 | 37 | 0 | Y | 0 | 0 | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | 34 | 27 | 7 | N | 0 | 1 | 3 | n/a (no ytasr) | 6 | 0 |
| Stay Gold (Official Music Video) from The Outsiders – A New Broadway Musical.---XzbHPqULtdA | 38 | 38 | 0 | N | 0 | 0 | 0 | n/a (no ytasr) | 0 | 0 |
| The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg | 40 | 33 | 7 | Y | 0 | 2 | 2 | 0 | 5 | 0 |
| The Next Ten Minutes Lyrics---0j8kL24ph8U | 71 | 67 | 4 | N | 0 | 1 | 1 | n/a (no ytasr) | 3 | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 36 | 29 | 7 | Y | 0 | 3 | 2 | 2 | 2 | 0 |

#### Table 2 — pooled corpus totals

| group | n_songs | n_lines | n_unplaced | U-0 | U-1@shipped | U-1@0.6 | U-2 | U-3(cross) | U-3(own) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ytasr songs | 10 | 610 | 102 | 0 | 52 | 59 | 24 | 26 | 0 |
| no-ytasr songs | 8 | 400 | 48 | 0 | 18 | 22 | n/a (structural: no second source) | 29 | 1 |

#### Table 3 — unplaced run-length distribution, per song

| song | n_unplaced | run-length histogram (len x count) | lines in runs>=3 | lines in runs 1-2 |
| --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 38 | 1x1, 2x2, 3x1, 9x1, 21x1 | 33 | 5 |
| 'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q | 1 | 1x1 | 0 | 1 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | 9 | 1x2, 3x1, 4x1 | 7 | 2 |
| Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8 | 0 | - | 0 | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | 8 | 1x1, 2x2, 3x1 | 3 | 5 |
| Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 1 | 1x1 | 0 | 1 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 21 | 1x5, 4x2, 8x1 | 16 | 5 |
| HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA | 18 | 1x1, 7x1, 10x1 | 17 | 1 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | 4 | 1x4 | 0 | 4 |
| Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY | 2 | 1x2 | 0 | 2 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 11 | 1x8, 3x1 | 3 | 8 |
| NSYNC - Paradise | 12 | 1x6, 2x3 | 0 | 12 |
| Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76peOw0 | 0 | - | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | 7 | 1x1, 6x1 | 6 | 1 |
| Stay Gold (Official Music Video) from The Outsiders – A New Broadway Musical.---XzbHPqULtdA | 0 | - | 0 | 0 |
| The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg | 7 | 1x1, 6x1 | 6 | 1 |
| The Next Ten Minutes Lyrics---0j8kL24ph8U | 4 | 1x1, 3x1 | 3 | 1 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 7 | 1x5, 2x1 | 0 | 7 |

#### Table 4 — cross-tab: U-class × (in a 3+ run / not)

| U-class | in run of 3+ | not in run of 3+ |
| --- | --- | --- |
| U-1 | 41 | 29 |
| U-2 | 17 | 7 |
| U-3-cross | 36 | 19 |
| U-3-own | 0 | 1 |

#### Table 5 — the known cases (GATE P validation)

**Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I** — named lids [44, 45, 46, 47, 48, 49, 50]

| line_id | class | sub |
| --- | --- | --- |
| 44 | U-2 | - |
| 45 | U-2 | - |
| 46 | U-2 | - |
| 47 | U-2 | - |
| 48 | U-2 | - |
| 49 | U-2 | - |
| 50 | U-3 | cross_attraction |

0/7 named lines that are in the unplaced population classify U-1 (7 named total, 0 of them placed anyway).

**HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA** — named lids [40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52]

| line_id | class | sub |
| --- | --- | --- |
| 40 | placed (not in unplaced population) | - |
| 41 | U-3 | cross_attraction |
| 42 | placed (not in unplaced population) | - |
| 43 | U-3 | cross_attraction |
| 44 | U-3 | cross_attraction |
| 45 | U-3 | cross_attraction |
| 46 | U-3 | cross_attraction |
| 47 | U-3 | cross_attraction |
| 48 | U-3 | cross_attraction |
| 49 | U-3 | cross_attraction |
| 50 | U-1 | - |
| 51 | U-3 | cross_attraction |
| 52 | U-3 | cross_attraction |

1/11 named lines that are in the unplaced population classify U-1 (13 named total, 2 of them placed anyway).

**Reading notes, mechanical, ahead of the read-off:**

- U-0 (line tokenises empty) is 0 across every song in this run — the
  "not a miss" caveat doesn't change any total here.
- U-2 is structurally impossible on the 8 no-ytasr songs (shown `n/a`),
  not merely absent; their U-1/U-3 counts are pooled in a separate row
  (Table 2) rather than folded into the two-source totals, per the
  design.
- The sensitivity column (`U-1@0.6`) reruns both the whisper and ytasr
  scans at a looser 0.6 edit ratio; it is reported, not read as a
  range — it exists only to show whether the U-1 count is fragile to
  that one threshold.

**Artifacts:** driver, tables generator and raw per-song JSON in the
session scratchpad, not committed: `phase7_run.py`, `phase7_tables.py`,
`phase7_out/results.json`, `phase7_out/tables.md`, `phase7_out/run.log`.

**Next:** stop. Ask Ken to `/model` to Opus for the read-off — starting
with the GATE P validation question above, which this run's own brief
routes to Ken/Opus, not the executor.

### 2026-09-14 — Phase 7 read-off (Opus) — STOP resolved: the validation clause's premise was wrong, not the method. Tables stand; the pre-registered reachable-share rule is WITHDRAWN as sharing the same defect

Read against the executor's run above (commit `762f875`), the GATE P
read-off of 2026-09-01, and the Phase 7 design. Read-only: nothing was
re-run, no table recomputed. Two facts below were **verified from disk
rather than accepted** — they are marked where they appear.

#### 1. The STOP: ruled resolved. The clause was wrong, the discriminator was right.

Phase 7's validation clause required Bloodstream (lids 44–50) and
HUNTR/X (lids 40–52) to come back "predominantly U-1" or "the method is
wrong." They came back 0/7 and 1/11. By the letter, the method fails.

**It does not fail. The clause's premise does.** The premise was that a
lyric-version-drift block presents as *no candidate anywhere*. That
holds only when the drifted lines carry text unique to the song. It
collapses when the drifted block is **repeated text**, because the
words are still sung — at a different occurrence — and a whole-song
scan finds them there.

**Verified, not inferred.** The two named blocks were read out of the
bundles' own sheets and normalised with the shipped tokeniser:

- **Bloodstream 44–49 is one couplet repeated.** "All the voices in my
  mind" at lids 38/40/42/44/46/48 and "Callin' out across the line" at
  39/41/43/45/47/49 — *six* occurrences each in the sheet. Lid 50 is a
  further duplicate. Every line in the named block is verbatim
  duplicate text.
- **HUNTR/X 41–47 each duplicate an earlier line** (41→9, 42→10/26,
  43→11/27, 44→28, 45→29, 46→30, 47→31). Of 48–52, the three
  Korean-carrying lines are not sheet-duplicates but their English
  halves are, and 51/52 are near-duplicates of each other sharing a
  hook line with many others. Lid 50 — the one line in either block
  that is genuinely mostly non-English — is the single U-1.

So the audio sings that couplet *some* number of times and the sheet
lists it six; the surplus goes unplaced, and a scan finds its text at
the earlier occurrences. **That is the mechanism producing 0/7 and
1/11, and it is the mechanism GATE P named.** Both entries describe the
same phenomenon; there was never a conflict between them, only a
conflict between GATE P and a premise I attached to it.

**GATE P is not overturned and is not corrected.** Its entry already
carried the evidence that candidates exist for these lines — "Bloodstream
lines repeatedly at 133.84/160.39/222.92 s," "many distinct lines
collide on a *single* argmax timestamp." Its conclusion ("a section-level
DP cannot place a section the audio does not contain") remains right for
what it decided. The defect is entirely in Phase 7's clause, which read
GATE P's conclusion without its evidence.

**Consequence: the five tables stand and are read below.** No table is
amended, no number moves, and the executor's handling was correct in
every respect — including the refusal to resolve this itself.

#### 2. The same premise is in the read-off rule, so that rule is withdrawn

This is the more consequential half, and it follows from the identical
error. The design's read-off instruction was "report the reachable
share (U-2 + U-3) against the unreachable one (U-1)." That equation
assumes **a candidate found anywhere means the line is reachable at its
own position.** The Bloodstream block is a direct counterexample: six
lines with candidates, none reachable, and the matcher refusing them is
the monotonic DP working exactly as GATE P said it should.

**`reachable = U-2 + U-3` is withdrawn as unsound.** It is not an
amendment to fit the data — it is the removal of a rule that rests on a
premise the same run disproved. Nothing replaces it by fiat; what the
tables *do* support is in section 4.

A second, independent reason U-3 cannot carry that reading: `sub =
cross_attraction` was specified as "the best-scoring candidate window
overlaps a span the DP selected," which is a fact about collision and
carries no information about *where* the window sits relative to the
line's own neighbours. The driver implements the spec faithfully
(verified in source); the spec never asked the question the routing
decision needs.

#### 3. U-2 is also not clean, for a different reason

Recorded because it bounds section 4 and was not anticipated in the
design. The two scans run at deliberately different standards — the
run's own `joint_max_edit_ratio` (**0.75**, verified identical across
all 18 bundles) for whisper, `ytasr.CANDIDATE_MAX_EDIT_RATIO` (0.45)
for captions. The design was right to refuse to unify them: they are
different evidence standards. But it makes "found in one source, not
the other" conflate *only one transcription heard it* with *the
stricter scan did not clear its own bar on text the looser one
admitted*. Bloodstream 44–49 sitting in U-2 while being six-times
repeated text is that conflation visible.

#### 4. What the tables actually establish

Pooled across the 18 songs, **150 unplaced lines** — which reconciles
exactly with the "~150 sheet lines that never get words" the program
has quoted since GATE T, and with Phase 4's 1010-line denominator.

| | lines | share | reading |
| --- | --- | --- | --- |
| **U-1** — text found in *no* transcription | **70** | 47% | **Closed. Unreachable by any aligner.** |
| U-2 + U-3 — text found *somewhere* | 80 | 53% | **Present in the audio; position unknown.** |

**The one thing this probe cleanly separates is "text absent from the
audio" from "text present somewhere in it," and that split is roughly
half and half.** The 70 are closed: two independent transcriptions of
the same audio, each at its own standard, plus the relaxed anchor
fallback, found nothing resembling those lines anywhere in the song. No
mechanism reaches them — this is the class the phase was built to size,
and it is sized.

**It does not separate "present at this line's position" from "present
at another occurrence,"** and that is precisely the distinction the
routing question turns on. All 80 of the remainder are in that
undetermined state.

Two riders on the 70, in opposite directions and roughly cancelling:

- **18 of the 70 come from the 8 songs with no adopted caption**, where
  U-2 is structurally impossible and a caption-only line necessarily
  lands in U-1. That is an over-count of unknown size; the solid
  two-source figure is **52 of 102**.
- **U-1 is if anything under-counted at the margins**, because a line
  must fail a 0.75-ratio whole-song scan *and* the relaxed anchor
  fallback *and* (on 10 songs) an independent caption scan to reach it.

#### 5. The second discriminator: flat, and that is itself the finding

Block structure was designed as an independent check, with "if the two
discriminators disagree, that disagreement is the finding" written in
before the run. They disagree — not by pointing opposite ways, but by
**failing to separate at all**: lines in runs of 3+ are 59% of U-1, 71%
of U-2, 65% of U-3-cross. Essentially flat.

The reason is retrospectively obvious and should be recorded so nobody
re-derives it: **an unsung final chorus is a block of repeated text.**
Block structure cannot distinguish a section the audio never sings from
a repeat the audio does fewer times than the sheet lists. The
discriminator is not broken; it answers a question that turns out not
to be the discriminating one on this corpus.

#### 6. A defect in the design, mine, recorded

The sensitivity column was declared as "a looser **0.6**." Against a
shipped whisper ratio of **0.75**, 0.6 is *stricter* — the column tests
the opposite direction from the one declared, on the load-bearing
source. It is loosening only for captions (0.45 → 0.6). This is why
U-1 *rises* to 81 at "0.6" instead of falling: the column is measuring
what a tighter look does.

The column is still informative — tightening the whisper scan moves ~11
lines into U-1 — but **the declared direction was never tested.** No
result above depends on it: U-1's robustness rests on the shipped scan
already being very permissive at 0.75 plus the anchor fallback on top
of exactly the zero-candidate lines. Stated plainly rather than papered
over: the loosening direction is untested and I specified it wrong.

#### 7. Recommendation to Ken — routing, which is his call

**The prize is at most half what the program has been assuming, and the
remaining half is not yet shown to be a prize at all.**

1. **Stop quoting ~150 as the unreached population.** Forty-seven
   percent of it is audio that does not contain those words. That
   portion is permanently closed and no design pass, from any model,
   reaches it.
2. **Do not spend a design pass — Opus's or Fable's — on the unplaced
   population yet.** The question "is there a mechanism here" cannot be
   answered from these tables, because the 80 remaining lines are
   undetermined between *the matcher missed a line that is sung here*
   and *the only occurrence of this text is elsewhere and the DP
   correctly refused it*. On the evidence available the second is the
   better bet: the largest concentrations sit on songs GATE P already
   diagnosed as repeat pile-up, and the two blocks examined in detail
   were **entirely** repeated text.
3. **One cheap measurement closes it**, and it should run before any
   design spend. For each of the 80, does the best-scoring candidate
   window fall between the line's nearest *placed* neighbours, or
   outside them at a different occurrence? Everything it needs is
   already captured — candidate windows, placed spans, sheet text — so
   it is another no-GPU, no-audio pass of the same driver. A cheap
   companion on the same pass: whether the line's text is duplicated
   elsewhere in its own sheet, which is what settled the two named
   blocks here.
4. **GATE W is unblocked either way.** Phase 7 was sequenced first to
   test whether polish was the right next target. It has not shown the
   unplaced population to be the better target; it has halved it and
   left the rest undetermined. **Nothing here argues against starting
   GATE W step 1**, and if the follow-up in (3) is run, it can run
   alongside — they share no resource.

#### 8. What this read-off does NOT claim

- **Not** that the unplaced population holds nothing. It holds at most
  80 lines and possibly far fewer; that is a bound, not a zero.
- **Not** that U-3-cross lines are unreachable. They are *undetermined*.
  The evidence leans unreachable; it does not establish it.
- **Not** that GATE P was wrong about anything. It was right; Phase 7's
  clause misquoted its conclusion by dropping its evidence.
- **Not** a verdict on any mechanism. None was proposed, per the design.
- **Not** dependent on the sensitivity column, which measured the wrong
  direction (section 6).

#### 9. Loose ends recorded, not actioned

- ~~The follow-up in 7(3) is specified but **not commissioned**~~ —
  **COMMISSIONED by Ken the same day, ahead of GATE W step 1.** It is
  pre-registered as **Phase 7b** above, with its bands declared before
  the data.
- `U-3-own` is 1 line corpus-wide. Whatever it is, it is not a
  population.
- U-0 is 0 everywhere; the empty-line caveat never fired.
- The executor's three free cross-checks (the 8 no-caption songs
  matching the design's pre-stated count, the 1010-line denominator
  matching Phase 4, and the hard assertion that the whisper-side replay
  equals each bundle's own recorded scan counts) are the reason the
  tables can be read at all after a failed validation clause. Recorded
  as the practice that paid.

### 2026-09-14 — Phase 7b executor run (Sonnet) — found-text-location tables; the P-in trigger never fires, but HUNTR/X returns predominantly P-edge, a case the rule doesn't cover

Ran the probe designed above (§"Phase 7b", this file) over the same 18
joint-matcher captures, restricted to exactly Phase 7's U-2 and U-3 rows
(80 lines — matches the Phase 7 read-off's own count above exactly). No
GPU, no audio, no inference. Driver + tables generator live in the
session scratchpad (`phase7b_run.py`, `phase7b_tables.py`), not
committed; `phase7b_run.py` imports `phase7_run.py` directly and calls
its `process_song` for the population and class/sub assignment
unchanged (not re-derived), then calls its exact `_scan` a second time
with identical arguments to recover, per line, the best-scoring
candidate window's time span — the one fact `process_song` computes
internally but only keeps for `U-3` rows.

**Three checks came free, all silent (exit code 0, no assertion
fired).** `pass1_line_timings` has exactly `n_lines` entries on all 18
bundles (the assumption the bracket math rests on). The independently
recomputed `has_ytasr` agrees with `phase7_run`'s own result on all 18.
And every one of the 80 U-2/U-3 rows resolved a non-`None` candidate
window on the second `_scan` call — hard-asserted in code — meaning the
window-recovery pass found the same candidates the classification pass
did, for every row, not just most of them.

**Validation case (route-no-timing.md:1608–1615): the declared STOP
trigger did not fire. One case the rule doesn't address did occur.**
The pre-registered text is specific: "they should come back
predominantly P-out... If they come back P-in, the bracket method is
wrong and that is a STOP → Ken." Raw result, restricted to the named
lids that are actually in the Phase 7b population (U-2/U-3):

- **Bloodstream** (lids 44–50, all 7 in population): **0 P-in / 7
  P-out / 0 P-edge.** Matches the declared expectation exactly.
- **HUNTR/X** (lids 40–52; 40 and 42 are placed, not in the unplaced
  population at all; 50 is U-1, not in Phase 7b's U-2/U-3 population;
  10 of the 13 named lids remain): **0 P-in / 1 P-out / 9 P-edge.**

Neither song produced a P-in — the one outcome the design names as a
STOP. But HUNTR/X did not come back "predominantly P-out" either; it
came back predominantly `P-edge`. Verified, not inferred: HUNTR/X's
`n_lines` is 53 (Phase 7's own Table 1, this file), so line id 52 is
the song's last line. The run of unplaced lines from 43–52 (Table 3
below) reaches that boundary, so it has no placed successor to close a
bracket against — `P-edge` by the design's own definition ("no placed
predecessor, or no placed successor (the run reaches a song
boundary)"), not a scan failure and not a `P-in`. The design's text
declares what P-in and P-out each mean for this validation case; it is
silent on what a predominantly-`P-edge` result means for it.

**What this executor is not doing:** deciding whether a tail-of-song
`P-edge` run corroborates or undermines the repeat-pileup diagnosis,
deciding whether HUNTR/X should count as passing or failing the
validation case in the absence of a `P-in`, or tallying the pooled
P-in count (2, Table 5) against the read-off bands declared in the
design. Those are exactly Opus's read-off and Ken's call. All six
tables are reported below as designed, regardless of this question.

#### Table 1 — per song

| song | ytasr | n_pop (U-2+U-3) | P-in | P-out | P-edge |
| --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | Y | 7 | 0 | 2 | 5 |
| 'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q | N | 1 | 0 | 1 | 0 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | Y | 4 | 0 | 4 | 0 |
| Beauty and the Beast (1991) - Be Our Guest [UHD]---MiraOCjABn8 | Y | 0 | 0 | 0 | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | Y | 1 | 0 | 1 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | Y | 0 | 0 | 0 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | Y | 20 | 0 | 20 | 0 |
| HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA | N | 14 | 0 | 5 | 9 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | N | 1 | 0 | 0 | 1 |
| Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY | N | 0 | 0 | 0 | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | Y | 9 | 0 | 9 | 0 |
| NSYNC - Paradise | N | 5 | 1 | 4 | 0 |
| Pocahontas - Colors of the Wind (Blu-ray 1080p HD)---9ThO76peOw0 | Y | 0 | 0 | 0 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | N | 6 | 0 | 0 | 6 |
| Stay Gold (Official Music Video) from The Outsiders – A New Broadway Musical.---XzbHPqULtdA | N | 0 | 0 | 0 | 0 |
| The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg | Y | 5 | 0 | 1 | 4 |
| The Next Ten Minutes Lyrics---0j8kL24ph8U | N | 3 | 0 | 3 | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | Y | 4 | 1 | 2 | 1 |

#### Table 2 — pooled corpus totals

| group | n_songs | n_pop (U-2+U-3) | P-in | P-out | P-edge |
| --- | --- | --- | --- | --- | --- |
| ytasr songs | 10 | 50 | 1 | 39 | 10 |
| no-ytasr songs | 8 | 30 | 1 | 13 | 16 |

#### Table 3 — per bracket

| song | line-id span | bracket duration (s) | n unplaced | s/unplaced line | overpacked | n P-in |
| --- | --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 0-20 | - | 21 | - | - | 0 |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 32-33 | 0.00 | 2 | 0.00 | Y | 0 |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 45-46 | 3.19 | 2 | 1.59 | N | 0 |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 56-64 | 3.92 | 9 | 0.44 | Y | 0 |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 80 | 0.00 | 1 | 0.00 | Y | 0 |
| 'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM | 82-84 | 0.86 | 3 | 0.29 | Y | 0 |
| 'Free' _ Official Lyric Video _ Sony Animation---fjOeJssZX_Q | 35 | 6.80 | 1 | 6.80 | N | 0 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | 1-4 | 0.74 | 4 | 0.18 | Y | 0 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | 35 | 0.70 | 1 | 0.70 | N | 0 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | 37 | 3.38 | 1 | 3.38 | N | 0 |
| 'Popular' - Wicked 20th Anniversary Edition _ WICKED the Musical---22QYya-LGDY | 52-54 | 0.00 | 3 | 0.00 | Y | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | 86-87 | 0.96 | 2 | 0.48 | Y | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | 89 | 0.50 | 1 | 0.50 | Y | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | 93-95 | 1.60 | 3 | 0.53 | Y | 0 |
| Beauty and the Beast (1991) - Belle [UHD]---otxTf5hZ0Yw | 98-99 | 0.26 | 2 | 0.13 | Y | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBBA) (Live At Abbey Road)---wGyh_53ecgg | 32 | 9.68 | 1 | 9.68 | N | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 27-30 | 0.90 | 4 | 0.23 | Y | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 37 | 6.52 | 1 | 6.52 | N | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 43-50 | 0.00 | 8 | 0.00 | Y | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 53 | 0.18 | 1 | 0.18 | Y | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 55 | 1.90 | 1 | 1.90 | N | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 59 | 0.58 | 1 | 0.58 | Y | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 63 | 4.26 | 1 | 4.26 | N | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I | 68-71 | 0.28 | 4 | 0.07 | Y | 0 |
| HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA | 33-39 | 0.28 | 7 | 0.04 | Y | 0 |
| HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA | 41 | 0.00 | 1 | 0.00 | Y | 0 |
| HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA | 43-52 | - | 10 | - | - | 0 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | 12 | 1.54 | 1 | 1.54 | N | 0 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | 16 | 1.78 | 1 | 1.78 | N | 0 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | 58 | 2.95 | 1 | 2.95 | N | 0 |
| Jessie J - Domino (Official Video)---UJtB55MaoD0 | 66 | - | 1 | - | - | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY | 0 | - | 1 | - | - | 0 |
| Josh Gad - In Summer (From 'Frozen'_Sing-Along)---9tcaM06eGrY | 16 | 4.65 | 1 | 4.65 | N | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 19-21 | 0.00 | 3 | 0.00 | Y | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 23 | 0.00 | 1 | 0.00 | Y | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 25 | 0.00 | 1 | 0.00 | Y | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 33 | 1.81 | 1 | 1.81 | N | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 35 | 0.50 | 1 | 0.50 | Y | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 37 | 1.02 | 1 | 1.02 | N | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 40 | 0.66 | 1 | 0.66 | N | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 42 | 0.90 | 1 | 0.90 | N | 0 |
| Mulan _ I'll Make a Man Out of You _ @disneykids---vGfJeW_CcFY | 44 | 1.84 | 1 | 1.84 | N | 0 |
| NSYNC - Paradise | 1 | 49.10 | 1 | 49.10 | N | 0 |
| NSYNC - Paradise | 17 | 1.96 | 1 | 1.96 | N | 0 |
| NSYNC - Paradise | 21-22 | 1.56 | 2 | 0.78 | N | 0 |
| NSYNC - Paradise | 26 | 0.72 | 1 | 0.72 | N | 1 |
| NSYNC - Paradise | 39 | 6.02 | 1 | 6.02 | N | 0 |
| NSYNC - Paradise | 42 | 3.95 | 1 | 3.95 | N | 0 |
| NSYNC - Paradise | 51-52 | 0.00 | 2 | 0.00 | Y | 0 |
| NSYNC - Paradise | 59 | 0.24 | 1 | 0.24 | Y | 0 |
| NSYNC - Paradise | 63-64 | - | 2 | - | - | 0 |
| Seasons of Love (HD)---UvyHuse6buY | 16 | 5.72 | 1 | 5.72 | N | 0 |
| Seasons of Love (HD)---UvyHuse6buY | 28-33 | - | 6 | - | - | 0 |
| The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg | 30 | 26.08 | 1 | 26.08 | N | 0 |
| The Lion King - Hakuna Matata Music Video I 4K Ultra HD---fwLxDUQBdEg | 34-39 | - | 6 | - | - | 0 |
| The Next Ten Minutes Lyrics---0j8kL24ph8U | 7 | 22.50 | 1 | 22.50 | N | 0 |
| The Next Ten Minutes Lyrics---0j8kL24ph8U | 63-65 | 0.08 | 3 | 0.03 | Y | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 0 | - | 1 | - | - | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 8 | 7.14 | 1 | 7.14 | N | 1 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 15 | 3.36 | 1 | 3.36 | N | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 18 | 2.64 | 1 | 2.64 | N | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 32-33 | 30.48 | 2 | 15.24 | N | 0 |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 35 | - | 1 | - | - | 0 |

#### Table 4 — cross-tab: P-class × (sheet-duplicated / unique)

| P-class | sheet-duplicated | unique |
| --- | --- | --- |
| P-in | 0 | 2 |
| P-out | 36 | 16 |
| P-edge | 12 | 14 |

#### Table 5 — the P-in lines, listed in full (the deliverable)

| song | line_id | sheet text | bracket duration (s) | overpacked | duplicated |
| --- | --- | --- | --- | --- | --- |
| NSYNC - Paradise | 26 | Right here next to you (Right here next to you) | 0.72 | N | N |
| Wicked - For Good  (2025) 4K - The Girl in the Bubble (7_8) _ Movieclips---wzSeub9W4QQ | 8 | She spins such beautiful stories | 7.14 | N | N |

2 P-in lines total (population is 80; this is a subset by construction).

#### Table 6 — the known cases (bracket-method validation)

**Ed Sheeran & Rudimental­ - Bloodstream [Official Music Video­ YTMAs]---Orq_75kFi8I** — named lids [44, 45, 46, 47, 48, 49, 50]

| line_id | P-class | duplicated | Phase 7 class |
| --- | --- | --- | --- |
| 44 | P-out | Y | U-2 |
| 45 | P-out | Y | U-2 |
| 46 | P-out | Y | U-2 |
| 47 | P-out | Y | U-2 |
| 48 | P-out | Y | U-2 |
| 49 | P-out | Y | U-2 |
| 50 | P-out | Y | U-3 |

0 P-in / 7 P-out / 0 P-edge out of 7 named lines in the Phase 7b population (7 named total).

**HUNTR_X 'This Is What It Sounds Like' (Music Video) _ KPop Demon Hunters _ Netflix Philippines---hI-y5anGcUA** — named lids [40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52]

| line_id | P-class | duplicated | Phase 7 class |
| --- | --- | --- | --- |
| 40 | not in Phase 7b population (U-0/U-1/placed) | - | - |
| 41 | P-out | Y | U-3 |
| 42 | not in Phase 7b population (U-0/U-1/placed) | - | - |
| 43 | P-edge | Y | U-3 |
| 44 | P-edge | Y | U-3 |
| 45 | P-edge | Y | U-3 |
| 46 | P-edge | Y | U-3 |
| 47 | P-edge | Y | U-3 |
| 48 | P-edge | N | U-3 |
| 49 | P-edge | N | U-3 |
| 50 | not in Phase 7b population (U-0/U-1/placed) | - | - |
| 51 | P-edge | N | U-3 |
| 52 | P-edge | N | U-3 |

0 P-in / 1 P-out / 9 P-edge out of 10 named lines in the Phase 7b population (13 named total).

**Reading notes, mechanical, ahead of the read-off:**

- The population (80) and every row's `cls`/`sub` in the tables above
  is `phase7_run.py`'s own output object, read unchanged — this run
  adds only `pclass`, `bracket_duration`, `overpacked`, and
  `duplicated` on top of it.
- `overpacked` (< 0.6 s/unplaced line, declared in the design, not
  fitted here) fires on several near-zero-duration brackets (e.g.
  Bloodstream 43–50 at 0.00 s for 8 lines, Mulan 19–21/23/25 at 0.00 s):
  two placed lines with essentially no time gap between them, holding
  a multi-line unplaced run. Reported per the design, not
  reclassified — every line in those brackets above is still counted
  by its own P-class.
- `P-edge` lines still had their candidate window computed and
  hard-checked non-`None` (same discipline as `P-in`/`P-out`), but the
  window was not used for classification, per the design's "never
  force into P-in or P-out."
- Sheet duplication (Table 4) is keyed over the full sheet (every line,
  placed or not), not just the 80-line population, since a duplicate
  can sit on a line the DP did place.

**Artifacts:** driver, tables generator and raw per-song JSON in the
session scratchpad, not committed: `phase7b_run.py`, `phase7b_tables.py`
(imports `phase7_run.py` directly rather than copying it),
`phase7b_out/results.json`, `phase7b_out/tables.md`,
`phase7b_out/run.log`.

**Next:** stop. Ask Ken to `/model` to Opus for the read-off — starting
with the HUNTR/X `P-edge` question above, which this run's own brief
routes to Ken/Opus, not the executor.

### 2026-09-14 — Phase 7b read-off (Opus) — validation passes on its trigger; the unplaced matter is CLOSED at 2 in-bracket lines

Read against the executor's run above (commit `4e0b81e`), the Phase 7
read-off, and Phase 7b's own pre-registration. Read-only: nothing
re-run, no table recomputed. One figure was recomputed from the raw
records purely to test a bound and is marked where it appears.

#### 1. The validation case: passes on its trigger, with a defect in my wording

The pre-registered rule has two parts and they are not the same part.
The **expectation** was "predominantly P-out." The **trigger** was
narrower and explicit: "**If they come back P-in, the bracket method is
wrong and that is a STOP → Ken.**"

**The trigger did not fire. Neither song produced a single P-in.**
Bloodstream matched the expectation exactly (7/7 P-out). HUNTR/X came
back 0 P-in / 1 P-out / 9 P-edge.

**Ruled: this is a clean pass of the check's intent.** The failure the
check exists to catch is the bracket method claiming *this line is sung
right where it belongs* about lines independently verified as repeated
text sung elsewhere. That claim is P-in, and there is none of it —
across 17 named lines on two songs, zero. HUNTR/X's P-edge is not the
method asserting something false; it is the method **declining to
answer**, which is the design's own instruction ("never force into P-in
or P-out; an open bracket makes P-in trivially true and would inflate
the answer"). **P-edge is the conservative direction.** Had the method
been broken permissively — brackets so wide everything falls inside —
those nine lines would have been P-in. They are the opposite.

The executor's explanation is verified, not inferred: HUNTR/X's
`n_lines` is 53 (Phase 7's Table 1), so line 52 is the song's last
line, and the unplaced run 43–52 reaches it with no placed successor to
close a bracket against. That is `P-edge` by definition.

**The defect is mine and it is in the rule's wording.** The expectation
clause should have read "must not come back P-in; a P-edge majority is
reported, not read," which is what the design's own P-edge instruction
already implied everywhere else. Writing an expectation ("predominantly
P-out") that the trigger did not key on left a third outcome unnamed.
This is the third specification defect in this short sequence — the
GATE P clause's premise, the withdrawn `reachable = U-2 + U-3` rule,
and now this. The pattern is consistent and worth naming: **each one
came from stating a rule in terms of the result I expected instead of
the failure I was guarding against.** The trigger, written as a
failure, held every time.

#### 2. A real limit of the method, distinct from the wording defect

Recorded because it is not a defect and will matter if this question is
ever reopened. **26 of the 80 lines (33%) are unclassifiable by the
bracket method**, and they are systematically the song-head and
song-tail runs. A bracket needs a placed line on both sides, and
boundary runs have one side missing by construction.

The blindness is not randomly placed. **A song's head and tail are
exactly where sheet-versus-recording mismatch concentrates** — intros
the video cuts, outros that fade, extra choruses, credits text. So the
instrument is blind precisely where one of the main causes lives.

**A one-sided test is available and was not specified.** Every P-edge
line's candidate window was computed and hard-checked non-`None`; it
was simply not used. For a tail run, asking whether that window falls
after the last placed line's end — and for a head run, before the first
placed line's start — is a well-defined one-sided bracket that would
classify most of the 26. **It is not commissioned**, for the reason in
section 3: the answer cannot change the decision.

#### 3. Why the P-edge gap does not qualify the tables — a bound, not an argument

The reading below counts P-in excluding P-edge, so a third of the
population sits outside it. That is only safe if no plausible
resolution of those 26 crosses a band boundary. It does not, and this
is checkable rather than assertable:

- Table 4 splits P-edge into **12 sheet-duplicated and 14 unique**
  (confirmed against the raw per-line records). The duplicated twelve
  are the wrong-occurrence case outright — same evidence that settled
  both named blocks.
- **Adverse case: assume every one of the 14 unique-text P-edge lines
  is a genuine miss.** Total becomes 2 + 14 = **16**, still inside the
  declared "under 20 → closed" band.
- To reach the next band would require counting *all* 26 — including
  the nine HUNTR/X lines independently verified as verbatim duplicates
  of earlier sheet lines. That assumption is contradicted by the data,
  not merely unlikely.

**So the recommendation is invariant to the gap.** That is why the
one-sided test in section 2 stays uncommissioned: it would refine a
number that cannot cross its own threshold. Two probes have already
been spent on this question; a third that cannot change the answer is
not worth Ken's time or the machine's.

#### 4. The reading, against the bands declared before the data

**Pooled P-in excluding P-edge: 2.** (Population 80: P-in 2, P-out 52,
P-edge 26 — reconciles exactly with Phase 7's own 80.)

The design fixed three bands at line ~1623 before any data existed.
Executing the one that applies, verbatim:

> **Under 20 lines** — recommend the unplaced matter is **closed**. A
> population that small does not justify a design pass from any model,
> and GATE W is the work that is left.

**The overpacked override does not apply.** The design allows the
recommendation to drop one band if most P-in lines sit in overpacked
brackets; Table 5 shows neither of the two is flagged. It could only
have moved the reading downward in any case, and it is already at the
bottom band.

#### 5. The two lines, looked at rather than counted

Both are unique sheet text and neither is flagged overpacked. They are
worth naming because two is small enough to inspect, and because they
do not carry equal weight:

- **The Girl in the Bubble, line 8** — "She spins such beautiful
  stories" — in a 7.14 s bracket. Ample room, unique text, found inside
  the gap where it belongs. **This looks like a genuine miss.**
- **NSYNC Paradise, line 26** — "Right here next to you (Right here
  next to you)" — in a **0.72 s** bracket. It clears the overpacked
  flag only because that flag is seconds *per line* and this bracket
  holds one line; against the line's own length it is roughly ten words
  in three-quarters of a second. It sits just inside the matcher's own
  pace floor, so it is not impossible — but it is marginal, and the
  flag not firing is a limitation of the measure rather than a clean
  bill.

**Recorded as a measure's limit, not a defect:** `overpacked` is
seconds per unplaced line and takes no account of how long the lines
are. A short bracket holding one long line passes. It did its job here
(it fired on the near-zero-duration brackets it was built for) but a
per-token form would be sharper if this instrument is ever reused.

**So the honest count is one clear miss and one marginal one, corpus-wide,
against 1010 lines.**

#### 6. Recommendation to Ken

**The unplaced-lines matter is closed. I recommend spending nothing
further on it — no design pass, no Fable credits, no third probe.**

The arc, in one line each: the program twice called the ~150 unreached
lines its next target; Phase 7 showed 47% of them are words the audio
never sings; Phase 7b shows that of the remainder, essentially all are
text sung somewhere *other* than where the sheet puts them, which the
matcher is correct to refuse. **What survives as a mechanism's
opportunity is two lines.**

Three consequences:

1. **Retire the claim from the program's own framing.** Phase 3 and
   GATE T both recorded "the unplaced population is where the remaining
   quality sits." That is now measured and false, and the plan files
   should stop repeating it — done in this commit.
2. **GATE W is not merely what is left; it is now the better target on
   evidence.** It was sequenced with the honest caveat that it is
   polish. The comparison it was being judged against has evaporated:
   polish on lines that render beats a design pass aimed at two lines.
3. **If the question is ever reopened**, the lever is upstream and was
   named at GATE P, not here: get a lyrics sheet that matches the
   recording. Every mechanism inside the matcher has now been shown to
   be aiming at text the recording does not contain in the place the
   sheet puts it. That is a fetch-and-selection problem, not an
   alignment one.

#### 7. What this read-off does NOT claim

- **Not** that the matcher places everything it should. It claims the
  *unplaced* population holds ~2 winnable lines on this corpus.
- **Not** that the 26 P-edge lines are unreachable. They are
  unclassified; the bound in section 3 is why that does not matter for
  this decision, not a finding that they are empty.
- **Not** that Phase 7b measured quality. No line was rendered, watched
  or scored; "P-in" means text found in the right gap, not timed well.
- **Not** generalisable beyond these 18 songs. A corpus with cleaner
  sheets would have a different split, and this says nothing about what
  a future library looks like.
- **Not** a verdict on any mechanism. None was proposed, per the design.

#### 8. Loose ends recorded, not actioned

- The one-sided boundary test (section 2) is specified and
  **deliberately not commissioned**. If the unplaced question is ever
  reopened, it is the cheapest thing to run first.
- `overpacked` should be per token rather than per line if reused
  (section 5).
- The executor's three free checks — `pass1_line_timings` length on all
  18, independent `has_ytasr` agreement, and a hard assertion that
  every one of the 80 rows resolved a candidate window on the second
  scan — plus importing `phase7_run.py` rather than copying it, are why
  this run's population is identical to Phase 7's by construction
  rather than by claim. Recorded as the practice that paid, twice now.

### 2026-09-14 — Phase 6 / GATE W step 1 executor run (Sonnet) — population split tables, no verdict

Ran W-1 exactly as pre-registered: no GPU, no audio, bundles only.
Driver lives in the session scratchpad (`phase6_w1_population_split.py`),
not committed.

Cohort: the 18 joint-matcher captures in
`D:/shared/pikaraoke-songs/alignment_debug/` (bundles whose `joint_stats`
carries `pass1_line_timings`); the other 16 are cue-route and were
skipped. Pooled `n_lines` across the 18 is 1010, matching Phase 7's own
denominator exactly.

Per line, `joint_stats.selected_source[line_id]` gives the winning
source (indexed by line id, length `n_lines`). For each line in the
target population (`transcribe`/`ytasr`) and, as context, each
`align`-won line, `_line_align_ranges` was recomputed from the bundle's
own `lyrics.align_lines` and `words` — not persisted in the bundle — to
classify whisper's belief per the pre-registered rule: range absent →
`abstain_none`; paced below `_MIN_ALIGN_PACE_S` (0.06) → `abstain_crammed`;
else `_range_agreement(output_t0, output_t1, align_range) >= tau` →
`agrees`, else `disagrees`, where `(output_t0, output_t1)` is the line's
own `output_line_timings` span.

**Validity checks, before any table.** For all 18 bundles, the
align/transcribe/ytasr counts recomputed from `selected_source` were
asserted equal to the bundle's own recorded `joint_stats.align_won` /
`transcribe_won` / `ytasr_won` — hard, in code — and all 18 passed.
Separately, every align-won line's recomputed range came back present
and paced on every song (`abstain_none = abstain_crammed = 0` throughout
Table W-1.3) — the shipped code only guarantees that if this recompute
reads the same inputs the matcher itself used to build its align
candidates.

#### Table W-1.1 — target population (transcribe+ytasr-won), class split at tau=0.5

| stem (trunc) | n_lines | n_placed | n_target | target_share_of_placed | abstain_none | abstain_crammed | agrees | disagrees |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Annivers | 89 | 51 | 29 | 56.9% | 0 | 15 | 12 | 2 |
| 'Free' _ Official Lyric Video _ Sony Ani | 41 | 40 | 40 | 100.0% | 0 | 23 | 0 | 17 |
| 'Popular' - Wicked 20th Anniversary Edit | 62 | 53 | 11 | 20.8% | 0 | 0 | 11 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | 77 | 77 | 21 | 27.3% | 0 | 0 | 21 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | 110 | 102 | 28 | 27.5% | 0 | 0 | 28 | 0 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 38 | 37 | 24 | 64.9% | 0 | 1 | 20 | 3 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | 74 | 53 | 21 | 39.6% | 0 | 2 | 18 | 1 |
| HUNTR_X 'This Is What It Sounds Like' (M | 53 | 35 | 3 | 8.6% | 0 | 0 | 3 | 0 |
| Jessie J - Domino (Official Video)---UJt | 67 | 63 | 12 | 19.0% | 0 | 1 | 6 | 5 |
| Josh Gad - In Summer (From 'Frozen'_Sing | 31 | 29 | 3 | 10.3% | 0 | 0 | 3 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | 47 | 36 | 36 | 100.0% | 0 | 15 | 0 | 21 |
| NSYNC - Paradise | 65 | 53 | 52 | 98.1% | 0 | 22 | 0 | 30 |
| Pocahontas - Colors of the Wind (Blu-ray | 37 | 37 | 35 | 94.6% | 0 | 19 | 5 | 11 |
| Seasons of Love (HD)---UvyHuse6buY | 34 | 27 | 10 | 37.0% | 0 | 1 | 9 | 0 |
| Stay Gold (Official Music Video) from Th | 38 | 38 | 1 | 2.6% | 0 | 0 | 1 | 0 |
| The Lion King - Hakuna Matata Music Vide | 40 | 33 | 23 | 69.7% | 0 | 1 | 17 | 5 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 71 | 67 | 23 | 34.3% | 0 | 7 | 13 | 3 |
| Wicked - For Good  (2025) 4K - The Girl  | 36 | 29 | 21 | 72.4% | 3 | 12 | 5 | 1 |
| POOLED | 1010 | 860 | 393 | 45.7% | 3 | 119 | 172 | 99 |

#### Table W-1.2 — tau sensitivity, target population agrees/disagrees at tau in {0.3, 0.5, 0.7}

| stem (trunc) | n_paced_present | agrees@0.3 | disagrees@0.3 | agrees@0.5 | disagrees@0.5 | agrees@0.7 | disagrees@0.7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Annivers | 14 | 13 | 1 | 12 | 2 | 12 | 2 |
| 'Free' _ Official Lyric Video _ Sony Ani | 17 | 0 | 17 | 0 | 17 | 0 | 17 |
| 'Popular' - Wicked 20th Anniversary Edit | 11 | 11 | 0 | 11 | 0 | 11 | 0 |
| Beauty and the Beast (1991) - Be Our Gue | 21 | 21 | 0 | 21 | 0 | 20 | 1 |
| Beauty and the Beast (1991) - Belle [UHD | 28 | 28 | 0 | 28 | 0 | 26 | 2 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 23 | 20 | 3 | 20 | 3 | 18 | 5 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | 19 | 18 | 1 | 18 | 1 | 14 | 5 |
| HUNTR_X 'This Is What It Sounds Like' (M | 3 | 3 | 0 | 3 | 0 | 3 | 0 |
| Jessie J - Domino (Official Video)---UJt | 11 | 7 | 4 | 6 | 5 | 6 | 5 |
| Josh Gad - In Summer (From 'Frozen'_Sing | 3 | 3 | 0 | 3 | 0 | 3 | 0 |
| Mulan _ I'll Make a Man Out of You _ @di | 21 | 0 | 21 | 0 | 21 | 0 | 21 |
| NSYNC - Paradise | 30 | 0 | 30 | 0 | 30 | 0 | 30 |
| Pocahontas - Colors of the Wind (Blu-ray | 16 | 5 | 11 | 5 | 11 | 5 | 11 |
| Seasons of Love (HD)---UvyHuse6buY | 9 | 9 | 0 | 9 | 0 | 8 | 1 |
| Stay Gold (Official Music Video) from Th | 1 | 1 | 0 | 1 | 0 | 1 | 0 |
| The Lion King - Hakuna Matata Music Vide | 22 | 17 | 5 | 17 | 5 | 12 | 10 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 16 | 14 | 2 | 13 | 3 | 11 | 5 |
| Wicked - For Good  (2025) 4K - The Girl  | 6 | 6 | 0 | 5 | 1 | 5 | 1 |
| POOLED | 271 | 176 | 95 | 172 | 99 | 155 | 116 |

#### Table W-1.3 — align-won lines, same four classes, as context, tau=0.5

| stem (trunc) | n_align_won | abstain_none | abstain_crammed | agrees | disagrees |
| --- | --- | --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Annivers | 22 | 0 | 0 | 21 | 1 |
| 'Free' _ Official Lyric Video _ Sony Ani | 0 | 0 | 0 | 0 | 0 |
| 'Popular' - Wicked 20th Anniversary Edit | 42 | 0 | 0 | 40 | 2 |
| Beauty and the Beast (1991) - Be Our Gue | 56 | 0 | 0 | 56 | 0 |
| Beauty and the Beast (1991) - Belle [UHD | 74 | 0 | 0 | 73 | 1 |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 13 | 0 | 0 | 13 | 0 |
| Ed Sheeran & Rudimental­ - Bloodstream [ | 32 | 0 | 0 | 30 | 2 |
| HUNTR_X 'This Is What It Sounds Like' (M | 32 | 0 | 0 | 32 | 0 |
| Jessie J - Domino (Official Video)---UJt | 51 | 0 | 0 | 48 | 3 |
| Josh Gad - In Summer (From 'Frozen'_Sing | 26 | 0 | 0 | 25 | 1 |
| Mulan _ I'll Make a Man Out of You _ @di | 0 | 0 | 0 | 0 | 0 |
| NSYNC - Paradise | 1 | 0 | 0 | 0 | 1 |
| Pocahontas - Colors of the Wind (Blu-ray | 2 | 0 | 0 | 2 | 0 |
| Seasons of Love (HD)---UvyHuse6buY | 17 | 0 | 0 | 17 | 0 |
| Stay Gold (Official Music Video) from Th | 37 | 0 | 0 | 37 | 0 |
| The Lion King - Hakuna Matata Music Vide | 10 | 0 | 0 | 10 | 0 |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 44 | 0 | 0 | 42 | 2 |
| Wicked - For Good  (2025) 4K - The Girl  | 8 | 0 | 0 | 8 | 0 |
| POOLED | 467 | 0 | 0 | 454 | 13 |

#### Table W-1.4 — align-won lines carrying at least one interpolated run (`_fill_unmatched_runs`)

| stem (trunc) | n_align_won | n_with_interp_run | share |
| --- | --- | --- | --- |
| 'Defying Gravity' - Wicked 20th Annivers | 22 | 0 | 0.0% |
| 'Free' _ Official Lyric Video _ Sony Ani | 0 | 0 | - |
| 'Popular' - Wicked 20th Anniversary Edit | 42 | 0 | 0.0% |
| Beauty and the Beast (1991) - Be Our Gue | 56 | 0 | 0.0% |
| Beauty and the Beast (1991) - Belle [UHD | 74 | 0 | 0.0% |
| Ed Sheeran - Best Part Of Me (feat. YEBB | 13 | 0 | 0.0% |
| Ed Sheeran & Rudimental­ - Bloodstream [ | 32 | 0 | 0.0% |
| HUNTR_X 'This Is What It Sounds Like' (M | 32 | 1 | 3.1% |
| Jessie J - Domino (Official Video)---UJt | 51 | 1 | 2.0% |
| Josh Gad - In Summer (From 'Frozen'_Sing | 26 | 0 | 0.0% |
| Mulan _ I'll Make a Man Out of You _ @di | 0 | 0 | - |
| NSYNC - Paradise | 1 | 0 | 0.0% |
| Pocahontas - Colors of the Wind (Blu-ray | 2 | 0 | 0.0% |
| Seasons of Love (HD)---UvyHuse6buY | 17 | 0 | 0.0% |
| Stay Gold (Official Music Video) from Th | 37 | 0 | 0.0% |
| The Lion King - Hakuna Matata Music Vide | 10 | 0 | 0.0% |
| The Next Ten Minutes Lyrics---0j8kL24ph8 | 44 | 0 | 0.0% |
| Wicked - For Good  (2025) 4K - The Girl  | 8 | 0 | 0.0% |
| POOLED | 467 | 2 | 0.4% |

**Next:** Opus reads W-1a/b/c (the kill rules) against these tables.
