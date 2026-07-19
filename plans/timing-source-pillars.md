Model: Claude Fable 5

# Timing-source pillars — evidence plan (probes, comparisons, GATE verdicts)

## Role of this file (revised 2026-07-18, same day as creation)

Split per Ken: **this file owns tests, comparisons, and GATE rulings.**
All production implementation lives in `plans/ctc-sync-engine.md` (the
successor build plan), whose phases cite this file's GATEs as their
licenses. The production-design Appendices A–D moved there (same
letters); "Appendix X" in this file means that file's appendix. The
tier routing policy below stands as Ken's target; whether it is
realized as three separately-implemented tiers or as **one CTC sync
engine with trust-ranked structure sources** is itself decided by this
plan's probes (GATE O + GATE S ruling S-5).

## Goal

Measure everything needed to route the alignment flow around external
synced timing as **pillars**, not post-processing. Target router (per
Ken, 2026-07-18):

1. **Tier 1 — word timing (Musixmatch richsync):** verification/sync pass
   against audio evidence, then generate the `.ass` directly from the
   provider's word timings and text. No lyric matching.
2. **Tier 2 — line timing (uploader SRT, or LRCLIB / Musixmatch-line /
   NetEase):** the cue-align windowed driver. SRT cues are trusted as-is
   (today's path, unchanged); foreign-clock line timing enters as a
   **warped scaffold** (`warp_scaffold_cues`, ported from `pathed_align`).
   CTC (torchaudio MMS_FA) is evaluated as the section aligner.
3. **Tier 3 — no timing:** the existing joint matcher on Genius lyrics,
   unchanged. After the coverage round this is a small residual class
   (1 of 17 genius-origin corpus songs).

Evidence base, all in this repo:

- `plans/musixmatch-coverage-probe.md` + `plans/musixmatch-coverage-improvement.md`
  (executed): reference-pick + title-only + NetEase = 24/33 corpus songs
  with real timing (genius-origin segment: 16/17; word-level: 8 of those).
  `scripts/musixmatch_coverage_improve.py` is the working fetch prototype.
- `plans/ctc-forced-align-eyeball.md` (**executed 2026-07-18** — GATE C
  verdicts in the Results log below).
- `pathed_align` commit `835ba2c7` (never merged): LRC-scaffold windowed
  alignment — warp + densify + union-anchor machinery, corpus-validated
  (re-pace 40%→20%, worst-overlap 4.1s→2.2s over 10 songs).
- The hardened matcher/cue-align on this branch (`musix_ctc`, =
  `fable_matcher_refine` tip): phases 0–6 of
  `plans/matcher-accuracy-hardening.md` closed.

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
  coverage table in `plans/musixmatch-coverage-improvement.md` §Results is
  the routing ground truth for which song lands in which tier.
- Musixmatch politeness (relearn nothing): one shared provider instance,
  `CALL_SLEEP_S=2.5` / `SONG_SLEEP_S=4.0`, single 20s-backoff retry on
  401 with token-file clear, never per-call token refresh. NetEase: plain
  try/except + same pacing.
- GATE markers are hard stops: executor reports numbers, Judge reads,
  Ken rules. No proceeding past a GATE on executor judgment.

## Model switching

Same three roles as `plans/matcher-accuracy-hardening.md` §"Model
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
| 1 (CTC probe, GATE C) | `plans/ctc-forced-align-eyeball.md` | executed 2026-07-18 | done — see Results log |
| 1b (score oracle, GATE O) | locked below | Sonnet 5 | Opus + Ken |
| 2 (richsync probe, GATE R) | 2a/2b below; Appendix C locks at the GATE | Sonnet 5 | Opus + Ken eyeball |
| 3 (scaffold probe, GATE S) | below; Appendices D/E lock at the GATE | Sonnet 5 | Opus; escalate if arms conflict |

Phase dependencies: 1b, 2, 3 can interleave; 1b should complete before
2b (its scores feed 2b's verification stats) and before 3's S-B2 arm.
Build phases in `plans/ctc-sync-engine.md` consume these GATEs per its
licensing table; its E0 (fetch pillar) is architecture-neutral and may
start immediately — the sidecar format both it and Phase 2a share is
locked in that file's Appendix B (if E0 lands first, 2a's script
imports the lib instead of carrying its own writer).

## Phase 0 — port the scaffold machinery + fresh baselines

The scaffold core already exists on `pathed_align` (commit `835ba2c7`)
and was corpus-validated there; ship's `cue_align.align_song` is
already cue-source-agnostic (takes `cue_spans` + a `slice_align`
callable), so the port is three pure functions plus one helper — **not**
a driver rewrite. Read sources with `git show pathed_align:<path>`.

1. Port into ship `pikaraoke/lib/cue_align.py`:
   `densify_cue_spans`, `merge_cue_spans`, `warp_scaffold_cues`,
   `_theil_sen`, and the `DENSIFY_*` / `WARP_*` constants
   (`835ba2c7` lines ~90–370). **Drift check done at planning time
   (2026-07-18):** these functions depend only on `_tokenise_lines`,
   `median`, the new constants, and each other — all already
   imported/available in ship's module — so this is a near-verbatim
   copy-in. The port is **additive**; do not overwrite any ship
   function. Ship's `align_song` consumes `warp_scaffold_cues`' output
   list directly (same `list[tuple[float, float]]` contract as
   `cue_spans_from_srt`). Port the three functions' unit tests
   alongside, adapted to ship's test module layout.
2. Port `ytasr.cue_spans_for_lines` (on `pathed_align`'s `ytasr.py:142`;
   absent from ship) into ship `pikaraoke/lib/ytasr.py`, with tests.
   Also lift the 8-line `normalize_words` adapter (whisper-transcribe
   words → `{norm, start, end}`) from
   `pathed_align:scripts/lrc_align_song.py:67` into `ytasr.py` next to
   it (both the harness and Phase 2b's probe need it; a scripts-local
   copy would be duplicated three times).
3. New harness pair mirroring the existing cue pair's structure exactly:
   `scripts/scaffold_align_song.py` imports the reusable shims from
   `scripts/cue_align_song.py` (`_make_slice_align`, `find_vocal`,
   `artifact_metrics`, `max_line_overlap` — same `sys.path` sibling
   import `cue_align_corpus.py` already uses) and does:
   bundle + on-disk audio → anchors (`ytasr.cue_spans_for_lines` over
   YTASR words, and over bundle transcribe words via `normalize_words`)
   → `merge_cue_spans` (transcribe primary) → `warp_scaffold_cues` with
   an injected line-timing source (`--timing <sidecar|lrc>` flag) →
   `cue_align.align_song` → `karaoke/<stem>.scaffold.ass` (never the
   production name) + re-pace/overlap/flag/warp-fit report.
   `scripts/scaffold_align_corpus.py` mirrors `cue_align_corpus.py`:
   selects genius-origin bundles (`lyrics.source_kind != "srt"`), loads
   the model once, loops the single-song shim, prints the flag table.
   Design source: `pathed_align:scripts/lrc_align_song.py`.
   **Supersession note:** the matcher plan's Phase 0 banned porting that
   file as dead exploration; that ban was scoped to that plan's harness
   port and is deliberately superseded here — write the new harness
   clean against ship signatures rather than copying the dead file.
4. Baselines (paste into Results log):
   - Fresh joint-route replay over the genius-origin corpus songs at
     current HEAD (`scripts/replay_ytasr_third_source.py`) — the matcher
     has moved since the matcher plan's Phase 0 table; that table is
     stale for comparison purposes.
   - Cue corpus flag counts: reuse the 5b validation numbers if the tree
     is unchanged since, else re-run `scripts/cue_align_corpus.py`.
5. Commit: `feat(cue-align): port scaffold warp machinery from
   pathed_align` (+ separate harness commit).

## Phase 1 — CTC forced-align eyeball (GATE C) — EXECUTED

Executed 2026-07-18 per `plans/ctc-forced-align-eyeball.md`; that file
carries the run summary pointer, this file's Results log carries the
GATE C verdicts (C-1 YES, C-2 YES-for-the-aligner, C-3 calibration +
constraints). S-B, S-B2 and S-C arms unblocked.

## Phase 1b — emission score oracle probe (GATE O)

Keystone for the engine architecture in `plans/ctc-sync-engine.md`:
does the CTC emission separate synced from desynced lines? Offline
scratchpad; GPU needed only for emission forward passes (seconds per
song). Honest precedent, stated up front: whisper align-word
probabilities failed the equivalent separation test (matcher plan
Phase 2a) — a NO here is a live outcome, and the fallback branch
exists for it.

1. Recompute emissions for the 33 songs (Phase 1's chunked recipe;
   cache each song's emission tensor in the scratchpad — the same
   compute-once/slice-many contract the engine plan's Appendix E
   specifies).
2. Score the existing `ctc_review/` alignments per word and per line:
   mean and min per-word emission score over the aligned span (the
   MMS_FA aligner's `TokenSpan.score`), z-normalized per song.
3. Labels — no new eyeballing needed:
   - **Desynced:** the sections Ken identified at GATE C — Bloodstream's
     crammed 2nd hook, the Popular and Defying Gravity desync
     stretches. Ken supplies rough time ranges; the executor records
     them as line-id ranges in the Results log before computing scores
     (pre-registered labels).
   - **Synced:** the same songs' good stretches per Ken, plus 5
     well-behaved songs end-to-end (Belle, Rock Your Body + 3 more of
     Ken's choosing).
   - **Cross-check:** score the *production* `.ass` timings for 2–3
     known-bad line groups from the matcher-plan era (e.g. Defying
     Gravity's OST-only outro lines 79–88) against the same emissions —
     phantom lines should score low against audio they were never in.
4. Table: per-line score distributions for synced vs desynced labels,
   overlap region, candidate gate band.

**GATE O** — mechanical read-off (Opus executes; Ken rules the gray
zone). Compute AUC over the labeled lines for both line-score variants
(mean-word z and min-word z); the better variant is the candidate gate
statistic and both AUCs are recorded:

- **O-1 (separation clean):** best AUC ≥ 0.85, AND a cut exists with
  ≤ 10% of synced lines below it and ≤ 10% of desynced lines above it,
  AND the phantom cross-check agrees directionally (the production
  phantom group's median score < the synced group's p25). Licenses
  score-gating as a design primitive: 2b's emission-score statistics,
  Phase 3's S-B2 arm, and the engine branch (subject to S-5). The cut
  becomes the candidate gate band recorded in the build plan's
  Appendix E.
- **O-2 (separation absent):** best AUC < 0.65. The CTC-first engine
  architecture is OFF; the build plan proceeds on its fallback branch
  and this plan's remaining probes run exactly as originally written.
- **O-GRAY (anything else):** best AUC in [0.65, 0.85), or the band or
  cross-check fails. Ken decides with the table; the engine branch
  then requires his explicit GO recorded here. No model resolves the
  gray zone on its own.

## Phase 2 — richsync: fetch bodies + timing-quality probe (GATE R)

The open empirical question from the coverage round ("part b"): is
richsync word timing render-quality? Nobody has seen a richsync-timed
`.ass` yet. This phase also prototypes the tier-1 verification math and
supplies the A/B Ken will use to rule on SRT-vs-richsync precedence.

### 2a. Fetch + persist raw bodies (committed tooling)

Extend `scripts/musixmatch_coverage_improve.py` with a `--save-bodies`
mode over 17 songs: the **15 word-level rows ≥ 0.5** — Popular, Belle,
Best Part of Me, Bloodstream, Colors of the Wind, Domino, Rock Your
Body (part a's 7, skipped in a2), plus Free, More Than That, Let It Go,
Part of Your World, Like I Love You, Mirrors, Seasons of Love, Can You
Feel the Love Tonight (a2's 8) — plus the **2 negative controls**
Selfish (word 0.38) and Incomplete (word 0.296), whose sidecars 2b's
wrong-song gate test needs:

- Re-run `reference_pick` per song (track_ids weren't recorded); assert
  the winner's `map_rate >= recorded − 0.05` (one-sided — reference-pick
  finding a *better* candidate than part a's old single-pick for the 7
  skipped songs is expected, not drift), log the delta, STOP on a kind
  downgrade (word→line/none — that would mean the catalog shifted under
  us). The 2 controls are exempt from the assert (recorded as-is,
  flagged `control: true` in the sidecar).
- Persist per song to the **production sidecar format of Appendix B**
  (`lyrics/<stem>.timing.json` beside the song, raw richsync JSON body
  included) — write the format once, probe and production share it.
- First body fetched: verify the raw richsync items carry `te` (line
  end); record which fields exist. The prior LRC-conversion threw
  structure away, so this is unverified on our corpus.
- Same politeness constants as before; run backgrounded.

Commit: `feat(scripts): --save-bodies richsync persistence for
musixmatch_coverage_improve`.

### 2b. Probe: verify-fit + renders (scratchpad)

For each of the 15 songs, offline against its existing bundle:

1. Parse the sidecar richsync into provider-text line objects
   (`ts`/`te`/word offsets → `{word,start,end}` lists).
2. **Verify-fit prototype** — the same statistics Appendix C will lock:
   pair provider lines ↔ bundle transcribe words via
   `ytasr.cue_spans_for_lines(normalize_words(transcribe_words),
   provider_line_texts)` (both ported in Phase 0 — this maps the word
   stream onto the provider's lines and is the same machinery the
   scaffold path trusts; do **not** use `map_lines_to_cues` here, it
   pairs line-lists to line-lists, not to a word stream). Theil-Sen
   tempo+offset over `(provider_ts, mapped_span_start)` pairs, then
   record per song: `n_pairs`, `pair_fraction`, `slope`, `offset_s`,
   residual MAD, per-line |residual| p50/p90/max, and fraction of
   provider lines with zero transcribe evidence in their claimed
   (warped) span. **If GATE O = O-1:** additionally score the warped
   richsync timings against the Phase 1b cached emissions, per line —
   the candidate verification statistic that tests *timing* directly,
   where transcribe pairing tests text-location agreement; Appendix C
   chooses between the two families (or both) at the lock.
3. Render the `.ass` variants per song where applicable:
   (i) richsync-direct — provider text, timings warped by the fitted
   slope/offset, word sweeps capped at `MAX_WORD_DUR_S`; build
   `line_objects` and call `generate_ass` per the recipe already written
   in `plans/ctc-forced-align-eyeball.md` §"Line grouping → ASS"
   (default `PipelineConfig`);
   (ii) current production output (already on disk);
   (iii) for the 7 srt-origin songs, the existing cue-align output — this
   is the **SRT-vs-richsync A/B** Ken asked to see before deciding tier
   order;
   (iv) **if GATE O = O-1:** richsync-guided CTC align — provider text
   force-aligned by CTC inside richsync-guided windows (richsync
   supplies text, line structure and approximate location; CTC supplies
   frame-accurate on-clock timing). This is the engine plan's word-route
   candidate (its Phase E2), A/B'd here against (i).
4. Print the mpv A/B commands; table into the Results log.

**GATE R** — Ken eyeballs; Opus reads the table. Rulings produced here:

- R-1: richsync-direct render quality — GO/NO-GO for the word route.
  (NO-GO ⇒ word timing demotes to a line-level scaffold source and its
  `ts`/`te` still improve scaffold ends.)
- R-2: provider text display quality (casing, ad-libs, backing vocals) —
  confirms or reverses the provider-text-as-is decision with evidence.
- R-3: SRT-vs-richsync tier order for both-sources songs (production
  effect deferred to follow-on scope per the search-scope decision; the
  ruling is recorded here regardless).
- R-4: **the Appendix C decision procedure executed** (Opus, verbatim
  from `plans/ctc-sync-engine.md` Appendix C — the general PASS/CONTROL
  threshold rule, the clamps, the emission-family adoption rule) and
  the resulting constants recorded into that appendix. Stage wiring is
  already locked there. The assembled gate must fail both controls
  (run the verify-fit on them); any case the procedure does not cover
  is a STOP → Ken.
- R-5: word-route mechanism — **warped richsync render (i) vs
  richsync-guided CTC (iv)** from the A/B; feeds the engine plan's E2.
  Decision rule locked in the build plan's Appendix C: (iv) wins
  unless visibly worse on any song or lower line coverage; ties → (iv).

## Phase 3 — scaffold + engine corpus probe (GATE S)

GPU corpus run via the Phase 0 harness, over the genius-origin songs
with any line timing (per the coverage table: all 17 minus Girl in the
Bubble; line sources = Musixmatch line, NetEase, LRCLIB `.lrc` already
on disk from the E1 fill path, and — for word songs — richsync line
starts). Fetch line bodies for the 8 line-level winners the same
`--save-bodies` way (same sidecar format, `kind: line`, LRC text body):
Defying Gravity, Be Our Guest, I'll Make a Man Out of You, NSYNC
Paradise, Hakuna Matata, What It Sounds Like, In Summer, The Next Ten
Minutes — the last three re-fetched even though NetEase/title-only won
them in a2, so every sidecar records its winning mechanism.

Arms, in order; later arms only where earlier ones justify the GPU time:

- **S-A (required):** scaffold + whisper `slice_align`. Metrics per
  song: re-pace %, worst overlap, flags, warp fit stats
  (`n_common`, MAD, gate fired?). Compare against: (a) the Phase 0
  fresh joint baseline for the same songs — **this is the scaffold-route
  GO/NO-GO comparison**; (b) the `835ba2c7` 10-song numbers where the
  song overlaps (sanity: the port didn't lose the win).
- **S-B (GATE C-1 = yes, satisfied):** same run, CTC `slice_align`
  adapter (windowed MMS_FA over the section slice — the windowed prior
  is exactly the constraint C-3's smear pattern needs; scratchpad
  adapter reusing Phase 1's proven recipe/normalization verbatim,
  wrapped to the `(t0, t1, text, label) -> words | None` contract).
  Same metrics.
- **S-B2 (if GATE O = O-1):** the **CTC-first engine arm** — full-song
  CTC align of the sheet (Phase 1's own output, recomputed), per-line
  score gate, windowed repair only on failing sections (repair windows
  from the warped scaffold via the trusted lines' Theil-Sen fit;
  windows sliced from the cached emission, no audio re-slicing). Same
  metrics plus fraction-of-lines-repaired. This is the engine
  architecture's direct A/B against scaffold-first (S-A/S-B).
- **S-C (if S-B or S-B2 looks competitive):** CTC `slice_align` on the
  13-song SRT cue-align corpus vs the 5b whisper baseline — the direct
  "can CTC improve cue align" measurement on the proven path.
- **S-D (diagnostic, cheap, no GPU):** for warp-gate-failed songs, record
  what the fallback would be — union-anchor densify vs joint matcher —
  by comparing S-A's fallback output against the joint baseline for
  those songs.
- **S-E (optional, offline, no GPU align):** CTC words swapped in as
  the joint matcher's align stream in the replay harness over the
  genius-origin corpus, vs the Phase 0 fresh baseline — measures Ken's
  GATE C observation ("synced sections beat whisper even on mismatch
  songs") and informs the engine plan's deletion inventory.

**GATE S** — mechanical read-offs (Opus executes; Ken retains eyeball
veto everywhere and rules anything a rule leaves open):

- S-1: scaffold-route GO iff, vs the Phase 0 joint baseline over the
  same songs: mean worst-overlap strictly lower, flagged-song count no
  higher, rendered-line coverage no lower, and no single song's worst
  overlap regresses by > 1.0 s without a recorded cause Ken accepts.
  Ken's spot-eyeball vetoes any new artifact class the metrics missed.
- S-2 (aligner per path): the CTC arm is selected for a path iff it is
  at least as good as the whisper arm on all three of mean re-pace,
  mean worst-overlap, and flag count, with no song > 1.0 s worse on
  overlap; otherwise whisper (proven default). The SRT switch (S-C vs
  the 5b baseline) uses the same rule plus Ken's eyeball veto — extra
  caution on the proven path.
- S-3: warp-failure branch = densify fallback iff its flags + overlap
  on the warp-failed songs are ≤ the joint baseline's on those songs;
  tie → densify (one fewer code path).
- S-4: **Appendix D/E constants recorded** (Opus, in
  `plans/ctc-sync-engine.md` — both are already locked as
  design/procedure; this step only fills measured constants such as
  the snap re-enable exception and the gate band).
- S-5: **architecture ruling** — engine branch iff GATE O ∈ {O-1, or
  O-GRAY with Ken's explicit GO} AND S-B2 meets the S-2 comparison
  rule against the best scaffold arm AND Ken concurs on eyeball;
  anything else → scaffold-first (fully specified, lower risk).

Scoring-circularity rule (pre-registered): LRCLIB held-out MAD is **not
a metric for any scaffold-routed song** — once LRCLIB feeds the
scaffold, that oracle is circular (already noted in `835ba2c7`'s plan).
Scaffold/engine quality is judged on re-pace/overlap/flags + eyeball;
the harness's held-out scoring remains valid only for joint-matcher
replays.

## Production phases — moved to `plans/ctc-sync-engine.md`

The build phases that lived here as Phases 4–7 (timing-fetch pillar,
tier-1 route, tier-2 route, closeout) moved to the successor build
plan — the fetch pillar as its E0, the tier routes as its fallback
branch F1/F2 or engine phases E1–E2 per the S-5 ruling, closeout as
E5. This file ends at GATE verdicts; no production code is implemented
from this file beyond the Phase 0 / Phase 2a tooling noted in Ground
rules.

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

## Verification matrix (Phase 0 / 2a code)

1. Import-smoke changed modules; full unit suite on the Linux box.
2. `pre-commit run --config code_quality/.pre-commit-config.yaml --files
   <changed>`.
3. The phase's own validation (baseline diff, corpus run).
4. Self-review (correctness / simplicity / robustness), commit, alert
   Ken when a /code-review batch + /compact point is reached.

## Results log

### 2026-07-19 — Phase 0 (port + harness + baselines), Sonnet 5 executor

Branch `timing_pillars` cut off `musix_ctc` (tip `22c15e4`).

**Port** (`pikaraoke/lib/cue_align.py`): `densify_cue_spans`,
`merge_cue_spans`, `_theil_sen`, `warp_scaffold_cues` +
`DENSIFY_DEFAULT_PACE_S`/`DENSIFY_MIN_LINE_DUR_S`/`WARP_MAD_GATE_S`/
`WARP_MIN_ANCHORS`, copied verbatim from `pathed_align:835ba2c7` per the
drift check — additive only, no existing function touched. 24 ported
unit tests (`TestDensifyCueSpans`/`TestMergeCueSpans`/
`TestWarpScaffoldCues`) pass unmodified against ship's module.

`pikaraoke/lib/ytasr.py`: `cue_spans_for_lines` (ported from
`pathed_align`'s `ytasr.py:142`, reusing ship's existing
`spans_from_candidates`/`CANDIDATE_MAX_EDIT_RATIO` verbatim — only the
`find_candidates` import and the function itself were missing) +
`normalize_words` (lifted from `pathed_align:scripts/lrc_align_song.py:67`).
16 new tests (`TestCueSpansForLines` ported + 2 new `TestNormalizeWords`).

Full unit suite: **1482 passed** (was 1482 + this port's ~40 new tests
net of the pre-existing 1456 5b baseline). Import-smoke clean.
Pre-commit (`--files` scoped to the changed modules): clean.

**Harness** (`scripts/scaffold_align_song.py` + `scaffold_align_corpus.py`):
built clean against ship signatures per the plan's supersession note
(not a port of the dead `pathed_align:scripts/lrc_align_song.py`).
Single-song driver builds ASR+transcribe anchors
(`ytasr.cue_spans_for_lines` over parsed YTASR words and over
`normalize_words(bundle["transcribe_words"])`, unioned transcribe-primary
via `merge_cue_spans`), warps an external `--timing {sidecar,lrc,none}`
scaffold onto them (`warp_scaffold_cues`), and hands the dense cues to
the shared production `cue_align.align_song` — reusing
`cue_align_song.py`'s `_make_slice_align`/`find_vocal`/`_ffmpeg`/
`_wav_duration`/`report` shims rather than duplicating the ffmpeg/whisper
plumbing. Writes `karaoke/<stem>.scaffold.ass` (never the production
name). The `sidecar` mode reads the Appendix B fetch-pillar sidecar
(`lyrics/<stem>.timing.json`, not yet populated for any song this
session — Phase 2a below only *fetches and persists* it, this run
carries no sidecar-mode corpus pass); `lrc` mode mirrors the dead
script's live LRCLIB fetch. Corpus runner mirrors `cue_align_corpus.py`'s
structure (song selection, model-once loop, flag table), selecting
`lyrics.source_kind != "srt"` bundles. Neither script has unit tests,
matching the existing SRT pair's precedent (GPU-driven, validated by
corpus run + eyeball, not pytest). Import-smoke clean; pre-commit
(isort reformatted the import block, otherwise clean).

**Baseline 1 — fresh joint-route replay** (genius-origin corpus, current
HEAD): `replay_ytasr_third_source.py /home/ken/pikaraoke-songs --alpha
2.0 --beta 2.0` (production's own `PipelineConfig` defaults). 17/17
genius-origin songs replayed, matches the 07-16 Environment-note
composite table in `plans/matcher-accuracy-hardening.md` (matcher logic
unchanged since — 5b/Phase 6 touched only `cue_align.py`/docs) to
within the documented live-LRCLIB-fetch MAD jitter (e.g. Domino
0.43s/7a -> 0.39s/7a here; the 07-16 note already characterizes this as
network flake, not matcher drift, confirmed determinism-checked there
3x):

```
song                                            src        mad(best) alpha  beta crawl(rec>new)   overlap(rec>new)  placed(rec>new)   coverage
----------------------------------------------------------------------------------------------------------------------------------------------
'Defying Gravity' - Wicked 20th Anniversary Ed 3src bail:wide_spread   2.0   2.0      4->3           0.2->0.2          51->51         51/89!
'Free' _ Official Lyric Video _ Sony Animation 2src        0.20s/16a   2.0   n/a      2->1           1.0->1.0          40->40          40/41
'Popular' - Wicked 20th Anniversary Edition _  3src bail:wide_spread   2.0   2.0      3->3           0.0->0.0          51->52         52/62!
Beauty and the Beast (1991) - Be Our Guest [UH 3src        0.16s/49a   2.0   2.0      1->0           0.0->0.0          77->77          77/77
Beauty and the Beast (1991) - Belle [UHD]---ot 3src        0.39s/55a   2.0   2.0      1->1           0.0->0.0         101->101       101/110
Ed Sheeran - Best Part Of Me (feat. YEBBA) (Li 3src bail:wide_spread   2.0   2.0      2->2           0.0->0.0          37->37          37/38
Ed Sheeran & Rudimental­ - Bloodstream [Offici 3src        0.60s/11a   2.0   2.0      1->1           6.7->6.7          47->48         48/74!
HUNTR_X 'This Is What It Sounds Like' (Music V 2src bail:wide_spread   2.0   n/a      0->0           0.0->0.0          32->33         33/53!
Jessie J - Domino (Official Video)---UJtB55Mao 2src         0.39s/7a   2.0   n/a      0->0           0.0->0.1          63->63          63/67
Josh Gad - In Summer (From 'Frozen'_Sing-Along 2src        0.22s/14a   2.0   n/a      2->2           0.0->0.0          29->29          29/31
Mulan _ I'll Make a Man Out of You _ @disneyki 3src bail:wide_spread   2.0   2.0      0->0           0.0->0.0          36->36         36/47!
NSYNC - Paradise                               2src        0.27s/10a   2.0   n/a      3->2           0.7->0.7          53->53         53/65!
Pocahontas - Colors of the Wind (Blu-ray 1080p 3src        0.19s/31a   2.0   2.0      2->2           0.0->0.0          37->37          37/37
Seasons of Love (HD)---UvyHuse6buY             2src         0.52s/5a   2.0   n/a      8->3           0.0->0.0          25->25         25/34!
The Lion King - Hakuna Matata Music Video I 4K 3src         0.41s/8a   2.0   2.0      4->3           0.0->0.0          33->33         33/40!
The Next Ten Minutes Lyrics---0j8kL24ph8U      2src        0.46s/52a   2.0   n/a      5->2           0.0->0.0          67->67          67/71
Wicked - For Good  (2025) 4K - The Girl in the 3src        0.39s/15a   2.0   2.0      2->2           0.0->0.0          29->29         29/36!
```

This table, not the 07-16 one, is Phase 3's fresh joint-baseline
comparison point (S-A criterion (a)).

**Baseline 2 — cue corpus flag counts (SRT songs)**: reused per the
ground rules' explicit license ("reuse the 5b validation numbers if the
tree is unchanged since") rather than re-run — `cue_align.py`'s SRT-path
logic (`segment_by_gaps`/`align_song`/`repace_bad_lines`) is untouched
by this session's port (additive-only, new functions never called by
the SRT path), so the 5b-validated state
(`plans/matcher-accuracy-hardening.md`, "Phase 5b implement +
validation") still holds exactly: **16/16 SRT songs, 0/16 drift**
(`gapL`/`instL` both zero every song), 0 lines placed->hidden, flag
table identical to the 07-16 Phase-0-baseline table there except 5
known overlap deltas from the `MAX_SECTION_DUR_S` section-cap fix
(Mirrors 0.7->0.8, ZAYN 7.8->4.0, Mena/Scott 2.6->2.1, Beauty and the
Beast 0.2->0.1, Part of Your World 0.7->2.5s — Ken's 5b read: all but
Mirrors are genuine two-voice overlaps, not defects). No fresh GPU run
executed this session for this baseline.

**Commits**: `feat(cue-align): port scaffold warp machinery from
pathed_align` (lib + tests) and `feat(scripts): scaffold-align harness
pair` (the two new scripts), per the plan.

### 2026-07-18 — Phase 1 (CTC eyeball) run + GATE C

Run (Ken, scratchpad probe per `plans/ctc-forced-align-eyeball.md`;
source of numbers: `pikaraoke-songs/ctc_review/SUMMARY.md`): **33/33
songs aligned on plain vocal stems, zero failures, zero degenerate
flags.** Only flagged row: Seasons of Love "late start 43.16s" —
explained, not a defect (~40s piano vamp plus the OOV-skipped numeral
opener `525,600`). Chunked-emission recipe held on the 6 GB card
through the 500s Mirrors.

GATE C (Ken eyeball verdicts 2026-07-18; Fable judge read):

- **C-1: YES — S-B and S-C unblocked.** Ken: best line-start/interior/
  end syllable timing seen in this project; 1:1 text/audio songs
  "undoubtedly superior", many acceptable even *without* windowing;
  recovers lines whisper drops (the long held "Free, free" in Free).
- **C-2: YES for the aligner.** All 23 production-dereverbed songs held
  on wet stems; Girl in the Bubble (the canonical de-reverb case)
  essentially perfect — its 0.00s first word is a quietly-sung long
  note, not intro smear. Recorded nuance: the de-reverb gate's *other*
  consumers (transcribe → tier-2 anchors, tier-1 verify) may still need
  it; decided at the Appendix D lock.
- **C-3 (calibration, confirmed + extended):** version-mismatch songs
  (Bloodstream, Popular, Defying Gravity) sync/desync in sections;
  desynced lines borrow syllable-level timing from the wrong words
  (Bloodstream visibly crams the missing 2nd hook, then re-syncs at the
  2nd verse — not always that clean). Synced sections still beat
  whisper on the same songs. Two hard constraints for any production
  CTC adapter: MMS_FA is Latin-only (hangul dropped on HUNTR_X — CTC
  routes need a non-Latin fallback, relevant to What It Sounds Like in
  tier 2) and numerals need spoken-form expansion (`525,600`, `30`).

New observations recorded for later locks (not scope changes now):

- Edge/onset snap may be redundant — possibly harmful — on CTC-timed
  lines (Ken: CTC edge timing already beats the snap's). Whether the
  snap post-passes run on CTC-timed routes is an Appendix D decision
  item with S-B data.
- CTC words as a joint-matcher (tier-3) evidence/align source — Ken:
  synced sections outperform whisper even on mismatch songs. Promoted
  to the optional S-E arm (2026-07-18 revision); also informs the
  build plan's deletion inventory.

---

## Appendices A–D — moved to `plans/ctc-sync-engine.md`

Moved 2026-07-18 (same day, with the evidence/build split), same
letters, content carried verbatim plus the GATE C additions: A (router
contract), B (timing-fetch module design), C (word-route verification
skeleton — locks at GATE R), D (scaffold/aligner integration skeleton —
locks at GATE S). A new Appendix E (engine core skeleton — locks at
GATEs O+S) exists only there. "Appendix X" references in this file
resolve to that file.
