# Full-mix whisper passes: experiment plan

Model: Claude Fable 5

## Question

Both production alignment paths run every stable-ts pass on the separated
vocal stem only. Would additional passes on the **full mix** (the original
audio) buy accuracy, and where do they belong?

Cost frame (user-stated): transcribe and align passes are near-negligible
clock-time next to refine. So every mix pass in this plan is **transcribe
(no refine)** or a **short slice align** — refine stays stem-only. Refining
against the mix is explicitly out of scope: it is the expensive pass, and
accompaniment onsets bias the token-probability peaks refine maximizes.

## Why we expect a win

- **YTASR is already a full-mix ASR source** — YouTube's recognizer runs on
  the mix — and it verdicted *win* as a third joint-DP stream (overlap ~0,
  6 MAD wins, 2 bail-recoveries; `plans/ytasr-third-source-experiment.md`
  on `pathed_align`). A local mix transcribe is the same signal class,
  available for **every** song instead of only gated-caption songs.
- The stem's known failure modes are exactly what the mix does not share:
  separator-starved passages (quiet vocals, masked words, suppressed
  backing/harmony lines), reverb-washed stems (the de-reverb gate exists
  because of this), separation leakage/garbling.
- Where the mix is *worse* (loud accompaniment masking vocals), its
  candidates simply lose on scoring / fail containment — asymmetric upside,
  provided mix evidence is never treated as truth.

Counter-risk to watch: mix-transcribe and stem-transcribe are the **same
model** (unlike YTASR), so their mishearings correlate. Mix words must only
ever enter through the gated corroboration bonus, never the base
`transcribe_match`, and the 2-of-3 rescue must not let (stem-transcribe,
mix-transcribe) — one model voting twice — outvote align + ytasr. See
design notes.

## Current state (branch `fullmix`)

- Non-SRT route: `lyric_align._run_joint` — de-reverb gate (stem transcribe,
  no refine) → align+refine on stem → 3-source joint DP
  (`joint_match.match_words_to_lines_joint_with_stats`: align + transcribe
  + optional ytasr, `alpha`/`beta`) → windowed re-align on stem slices.
- SRT route: `lyric_align._run_cue_align` — de-reverb gate →
  `cue_align.align_song` with injected `_slice_align` on the stem: sections
  → split → offset/re-section → `repace_bad_lines` (per-line realign rescue
  → cue-paced fill).
- Capture: bundle schema v7 (`alignment_capture.py`); carries `words`
  (align/refine), `transcribe_words`, ytasr ref, `joint_stats` incl.
  `windowed_realign.spans` and `pass1_line_timings`. Policy: **additive
  fields don't bump the version**.
- Corpus: song library at the default download dir — 16 non-SRT songs (the
  ytasr sweep set) + 13 SRT songs.
- Mix audio availability: live pipeline has `ctx.artifacts["extracted_wav"]`
  alive through lyric_align (tmp_dir outlives the stage). The regen path
  (`LoadVocalFromM4aStage`) does not — decode `ctx.song_path` lazily.
- Prior harnesses live on `pathed_align`, not this branch:
  `scripts/replay_alignment_from_bundle.py`,
  `scripts/replay_ytasr_third_source.py`, `scripts/cue_align_song.py`,
  `scripts/cue_align_corpus.py`. Port + adapt (note `srt_prior` →
  `srt_cues` rename; priors no longer exist here).

## Experiments overview

| ID | Route | Change under test | Cost | Gate to build |
|----|-------|-------------------|------|---------------|
| A | joint (non-SRT) | mix transcribe as extra corroboration stream in the DP | 1 whole-song transcribe/song | none — primary experiment |
| B | cue-align (SRT) | mix slice retry in the bad-line rescue ladder | seconds/song, failures only | none — cheap + structurally safe |
| C | windowed re-align | mix slice fallback when the stem slice fails | ~0 (rare) | bundle inventory shows it would ever fire |
| D | de-reverb gate | mix-vs-stem yield ratio as gate signal | 0 (reuses A0 capture) | analysis only, no build |

Shared principle: **capture first, replay offline, wire scoring last** —
the same playbook that settled ytasr.

---

## Phase A0 — capture mix transcribe words (both routes)

Goal: every bundle gains the mix word stream so all of A (and D) runs
offline afterwards, and B0's inventory comes from the same regen.

1. **Mix WAV helper** in `lyric_align.py`: return
   `ctx.artifacts["extracted_wav"]` when present, else decode
   `ctx.song_path` → `ctx.tmp_dir/<stem>_mix.wav` (16 kHz mono s16 — whisper
   resamples to 16k mono anyway; keeps tmp small). Reuse `run_ffmpeg` /
   `Phase.EXTRACT`. Decode lazily, once per song.
2. **Knob**: `PipelineConfig.capture_mix_transcribe: bool` (default False in
   production, forced True by the regen script). While the knob only
   *captures*, the run's output must remain byte-identical to shipped —
   A0 bundles are simultaneously the experiment's **baseline**.
3. **Run the pass** in both `_run_joint` and `_run_cue_align`, after the
   de-reverb gate (the gate never touches the mix):
   `transcribe_words(mix_wav, refine=False)` under `Phase.TRANSCRIBE`.
   Failure is logged and captured as absent — never fails the song.
4. **Bundle**: top-level `mix_transcribe_words` (sibling of
   `transcribe_words`), additive → **no schema bump**. Record the knob in
   `config_snapshot`.
5. **Regen tooling**: `regen_alignment_bundles.py` gains `--all` — the
   existing `scan_folder(include_all=...)` exposed without `--reset`
   (reuses recorded lyric sources; no re-prompting). Needed because
   additive fields don't make v7 bundles "stale".
6. **Run**: `python scripts/regen_alignment_bundles.py --all --yes` over the
   corpus (29 songs). Whisper re-runs regardless on regen; the added mix
   transcribe is the negligible pass. Stems and de-reverb caches are reused.

Tests: bundle round-trip includes the field; helper prefers
`extracted_wav`; capture failure doesn't fail the stage; output ASS
unchanged with knob on (golden-file or line_objects equality with a stub
worker).

Exit criteria: 29/29 bundles carry `mix_transcribe_words`;
`output_line_timings` identical to the pre-change bundles (byte-level diff
of the timing arrays, since this regen is also the baseline snapshot).

---

## Experiment A — mix transcribe as a joint-DP corroboration stream

### A1 — offline sweep

1. **Port the harness pair** from `pathed_align`
   (`replay_alignment_from_bundle.py` as the baseline replayer, and a new
   `scripts/replay_fullmix_source.py` modeled on
   `replay_ytasr_third_source.py`). Adaptations: `srt_cues` import; the
   baseline is the shipped 3-source no-prior route; re-align spans replay
   from `joint_stats.windowed_realign.spans` via
   `windowed_realign.replay_span + merge_spans` with the swept knobs
   threaded through (the old sweep's flat-alpha bug — knobs must reach the
   replayed sub-matches).
2. **Variants**, per non-SRT bundle:
   - **Baseline** — replay as shipped (recorded alpha/beta, ytasr words when
     the bundle has them).
   - **M1 substitute** — only for songs *without* ytasr: mix words fed into
     the existing ytasr slot, beta swept. Zero matcher changes; measures
     effect size where the third source is currently absent.
   - **M2 fourth source** — matcher extension (see design notes): score =
     `transcribe_match + weight * (alpha*align_agr + beta*ytasr_agr +
     gamma*mix_agr)`. Sweep `gamma ∈ {0.5, 1, 1.5, 2, 3}` with alpha/beta
     pinned at shipped defaults first; widen to a coarse joint grid only if
     the pinned sweep is promising but noisy.
   - Mix candidate generation: same `find_candidates` machinery as
     transcribe/ytasr. `max_edit_ratio`: start at ytasr's strict
     `CANDIDATE_MAX_EDIT_RATIO` (0.34 — same rationale: the ASR text is a
     candidate's only evidence for existing), sweep {0.34, 0.5} if mix
     candidates look starved.
3. **Scoring** (identical to the ytasr harness, all non-circular):
   - Primary: held-out LRCLIB cue MAD via `srt_cues.offset_mad_against_cues`
     over each scheme's own trusted anchors (`analyze_pass1`). LRCLIB is
     production-dead but stays a *scoring reference*: bundle `.lrc` → flat
     cache `<root>/lrclib/<stem>` → live fetch, as before.
   - Secondary: crawl-line count, max inter-line overlap, `n_mix_won`
     per-line source shifts.
   - Guardrail: baseline-clean songs must stay put (MAD delta ≤ 0.05 s, no
     new crawl/overlap).
4. **Eyeball artifacts**: `--write-ass` renders winning combos to
   `karaoke/<stem>.fullmix.ass` (never clobbers production `.ass`).

### A2 — verdict

Success criteria, fixed now:

- ≥ 3 MAD wins (≥ 0.05 s) **or** ≥ 1 bail-recovery on the 16-song set;
- 0 new crawl lines; overlap stays ~0;
- regressions ≤ 0.05 s MAD unless explicitly accepted (In Summer precedent);
- user eyeball confirms every changed song (the Mirrors lesson: metrics
  missed what the eyeball caught — eyeball is the falsifier of record).

Shape decision from the data:

- **M1 wins, M2 flat where ytasr present** → production shape is "mix words
  fill the third-source slot when ytasr is absent". No score-formula
  change; smallest diff.
- **M2 wins broadly** → generalize the matcher to a corroborator-stream
  list (each stream = words + weight + max_edit_ratio); ytasr and mix
  become two entries.
- **Neither** → document the negative result in this file, keep the capture
  field (cheap, useful for D and future work), drop the matcher work.

Write the verdict into this doc (or a sibling
`full-mix-experiment-verdict.md`) in the ytasr-doc table format: per song —
src flags, old MAD → new MAD (best), winning gamma, crawl, overlap.

### A3 — production fold-in (only on a win)

- `_run_joint` runs the mix transcribe (knob promotes from capture-only to
  live), matcher change per the A2 shape, defaults from the sweep.
- Capture gains `joint_stats` mix counts (`n_mix_words`,
  `n_mix_candidates`, `mix_won`) — additive.
- Windowed re-align interplay: `analyze_pass1`'s anchor/suspect
  classification keeps using **stem transcribe only** for now (mix
  corroboration of anchors is a separate lever; note as follow-up, don't
  bundle).
- Tests mirror the ytasr ones: matcher reduces exactly to the 3-source
  result when mix words are absent; capture/replay round-trip.
- `/code-review` at the checkpoint (batch with whatever else is pending).

### Design notes (settle in A1/A2, defaults chosen now)

- **Same-model correlation**: mix words never contribute to the base
  `transcribe_match`; they live only inside the weighted bonus. The
  `_corroboration_weight` 2-of-3 rescue keeps its current witness pair
  (align, ytasr) — mix does **not** join the rescue in v1, because
  transcribe+mix agreeing is one model voting twice. Revisit only if A1
  shows missed rescues attributable to this.
- **No clock offset**: mix and stem decode from the same media — unlike
  ytasr there is no serving-side lag to calibrate. Verify via the
  harness's per-song median-offset column (should straddle 0).
- **Timestamp lag under masking**: whisper word times on the mix can run
  late where accompaniment masks onsets; `joint_margin_s` (0.3) absorbs
  small lag, and mix-won lines take their own words' timings — watch the
  eyeball pass for late first words on mix-won lines.
- **Hallucination profile**: instrumental-section hallucinations differ
  between stem and mix — that difference is the point. The existing
  `min_word_probability` filter applies unchanged (same worker path).

---

## Experiment B — mix retry in the cue-align rescue ladder

The SRT route's philosophy holds: cues place lines; audio only times words.
The mix therefore enters **only** where the stem already failed — bad lines
headed for cue-paced fill, and (B2 option) sections whose whole slice-align
failed. Good lines are structurally untouchable.

### B0 — baseline inventory (free, from the A0 regen)

From the 13 SRT bundles' cue-align stats (`joint_stats.repace`): per song
`n_repaced` / `repaced_line_ids` / `n_realigned`. These filled lines are
the entire target population — expect roughly the 15–20 corpus-wide fills
seen in the last hardening rounds. Known hard spots to keep on the eyeball
list: Mirrors chant block, More Than That line 28, the duet-overlap songs
(ZAYN, Aladdin — their overlaps are benign and must stay).

If B0 shows ~0 fills corpus-wide, B shrinks to the B2 section-failure
retry only, or is dropped.

### B1 — implement behind the existing injection seam

1. `cue_align.repace_bad_lines` / `align_song` accept an optional second
   rescue callable, `realign_mix` (same signature as `realign`). Ladder
   per bad line becomes: stem realign → containment check → **mix realign
   → same containment check** → cue-paced fill. Acceptance is identical
   and strict (`_line_from_realigned` + `_line_in_span`, repeat-aware
   slacks unchanged); only the audio differs.
2. New source tag `SOURCE_REALIGN_MIX = "cue_align_line_mix"` so stats and
   eyeball can attribute every converted line.
3. Stage side: `_run_cue_align` binds a second `_slice_align` closure over
   the mix WAV (A0's helper; lazy decode — songs with zero bad lines never
   pay it). Knob: `PipelineConfig.cue_mix_rescue: bool`.
4. `repace` stats gain `n_realigned_mix` / `realigned_mix_line_ids` and a
   mix-attempt/acceptance count (rejected-by-containment is the safety
   signal to watch).
5. **B2 option, gated separately**: when a section's `slice_align` returns
   None (the stable-ts give-up → RuntimeError degrade) or yields all-empty
   lines, retry the whole section window on the mix before its lines fall
   to the rescue ladder. Only fires on failed sections (NSYNC's last
   section is the known instance).

Tests: ladder ordering (stem accepted → mix never called; stem rejected +
mix accepted → mix tag; both rejected → fill); containment applies to mix
results; stub-aligner determinism; stats fields.

### B2 — corpus A/B + verdict

1. Port `cue_align_song.py` / `cue_align_corpus.py` from `pathed_align`,
   adapted to the production `align_song` signature. They write
   `karaoke/<stem>.cuealign.ass` side-by-side — production `.ass` untouched.
2. Run all 13 songs twice: rescue-mix off vs on (same model load).
3. Metrics per song:
   - fills converted to accepted mix realigns (`n_repaced` delta,
     `n_realigned_mix`);
   - mix acceptance rate (attempts vs containment-passes);
   - structural metrics all clean: drift/parked-tail/instant/hidden = 0,
     `max_line_overlap` unchanged (duet overlaps intact);
   - **non-bad lines byte-identical** between the two runs (diff the ASS
     events outside the repaced/realigned id sets — should be exact).
4. Eyeball every converted line (small count by construction).

Success criteria: ≥ 30 % of baseline fills convert to accepted realigns
corpus-wide, zero structural regressions, zero changes outside bad lines.
The bar is deliberately modest — the feature is cheap and the containment
gate makes a bad conversion structurally hard.

### B3 — hybrid slice audio (conditional, likely skip)

Only if B2 shows mix attempts failing containment on lines where the stem
also failed: try stem + attenuated mix (`ffmpeg amix`, mix at ~-16 dB) as
the retry audio for exactly those lines. One-variable A/B on that line set.
Do not build speculatively.

---

## Experiment C — mix fallback for windowed re-align (joint route)

Data check first, from the A0 bundles (no code): count spans with
`align_words == null` in `joint_stats.windowed_realign.spans` plus
`n_spans_kept_pass1` across the 16 songs.

- **~0 corpus-wide → skip C entirely** (don't build a fallback that never
  fires).
- Otherwise: in `_realign_one_span`, when the stem `_slice_align` returns
  None, retry the slice on the mix before keeping pass-1; telemetry
  `n_mix_span_attempts` / `n_mix_span_recovered`. Same replay/merge path,
  no matcher changes. Fold results into the A verdict doc.

---

## Experiment D — de-reverb gate cross-check (analysis only)

With A0 captured, compute per song: stem transcribe wpm vs mix transcribe
wpm. Question: does the *ratio* separate the known reverb-washed case from
genuinely sparse songs (long instrumentals) more cleanly than the current
absolute `dereverb_yield_wpm` threshold? Pure offline analysis in the
harness report. No production change unless a corpus case demands it —
the current gate works.

---

## Ordering and budget

1. **A0** capture change + regen `--all` — one GPU corpus pass (~previous
   regen wall time; the extra transcribe is negligible). Also produces the
   baseline bundles and B0/C/D inventories.
2. **B0 / C-gate / D** — free, offline, same afternoon as the regen.
3. **A1 → A2** — offline sweep (CPU), verdict + eyeball.
4. **B1 → B2** — small GPU run (13 songs, slices only), verdict + eyeball.
5. **C** — only if gated in.
6. **A3** production fold-in per verdicts; `/code-review` checkpoint.

Hardware: RTX 2060 6 GB; no new models, no co-residency change — mix passes
are extra jobs on the existing whisper worker.

Fork policy: every touched file is ours (`lyric_align.py`, `joint_match.py`,
`cue_align.py`, `alignment_capture.py`, `config.py`, `scripts/`) — no
upstream changes.

## Out of scope (explicit)

- Refine on the mix (cost + likely worse boundaries).
- Mix forced-align as a *primary* placement source.
- Merging mix words into the stem transcribe stream (near-duplicate words
  double-count in `find_candidates` and break the monotone scan).
- Transcription-only mode (no lyrics): stem transcribe is already the best
  single pass; mix WER is worse.
- LRCLIB in any production role (scoring reference only).
- `analyze_pass1` anchor corroboration from mix words (follow-up candidate
  after A3, not part of this round).
