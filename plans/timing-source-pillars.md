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
4. Rescue statistics (pre-registered 2026-07-19, Ken-directed) —
   computed in the **same run** whatever the primary read-off comes to,
   so a GATE O failure costs no second probe. Precedent motivating
   them: whisper's align *probabilities* failed the separation test,
   but the transcribe *cross-check* worked — so the rescues are
   categorical/relative tests, not more confidence scores. Every
   statistic is oriented higher = more synced, and every statistic
   (including step 2's two span-score variants) is computed both
   per-line and as a 5-line centered rolling median within its song
   (clamped at song edges) — the rolling variant targets the
   *sectional* shape of the GATE C desyncs:
   - **S-decode (decode agreement):** slice the cached emission over
     the line's aligned span (first word's start frame → last word's
     end frame); CTC greedy decode it (per-frame argmax, collapse
     repeats, drop blanks, MMS_FA charset); statistic =
     `difflib.SequenceMatcher(None, decoded, expected).ratio()` over
     space-stripped normalized character strings, where expected = the
     line's normalized alignment text. Asks "is this text actually
     there," which is immune to the quiet-but-correct trap (Girl in
     the Bubble's opener) that sinks confidence scores.
   - **S-shift (free-realign displacement):** re-align the line's
     tokens alone against the emission slice of its span padded
     ±5.0 s each side (clamped to song bounds; emission slicing, no
     audio recompute); statistic = −|realigned line midpoint −
     current line midpoint| in seconds. A synced line stays put; a
     desynced line jumps to where its text really is. Realign
     returning `None` → assign the labeled-set minimum; count these.
   - **S-tx (transcribe corroboration):** from the bundle's
     `transcribe_words` (verified present for 17/33 songs — including
     all three desync-labeled songs and Belle; SRT-era songs have
     `null`): window = line span padded ±2.0 s; statistic = |multiset
     intersection of the line's normalized tokens with the normalized
     transcribe tokens whose midpoints fall inside the window| /
     (line token count). Lines from songs without `transcribe_words`
     are excluded from S-tx only (record per-class coverage); S-tx is
     read off only if both label classes retain ≥ 10 lines.
5. Table: per-line distributions for synced vs desynced labels for
   **all ten variants** — {mean-word z, min-word z, S-decode, S-shift,
   S-tx} × {per-line, rolling-5} — each row with its AUC, overlap
   region, and candidate gate band. Ten AUCs is a multiple-comparisons
   exposure; the guard is that qualification below requires the
   conjunctive O-1 bars (band + phantom cross-check), never AUC alone.

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

A primary read-off of O-2 or O-GRAY is **not final** until GATE O′
below has been read — the rescue statistics were computed in the same
run, so the read-off is free.

**GATE O′ — rescue read-off (mechanical; Opus executes; runs only when
the primary read-off is O-2 or O-GRAY).** Apply O-1's exact bars —
AUC ≥ 0.85, AND a cut with ≤ 10% synced lines below / ≤ 10% desynced
lines above, AND the phantom cross-check directional (phantom group
scored with the *same* statistic against the production timings,
median < synced p25) — to each of the eight rescue variants (the
non-span-score rows of the table):

- **O-1′ (rescued separation):** at least one rescue variant clears
  all three bars. Adopt the highest-AUC qualifier; ties break
  S-decode > S-shift > S-tx (emission-internal preferred — no
  gate-time dependency on a transcribe pass having run). **O-1′
  counts as O-1 for every downstream license**: the engine branch,
  Phase 3's S-B2 arm, 2b's emission-score statistics, the build
  plan's licensing table, and Appendix C's emission-family rule. The
  adopted statistic, variant, and band are recorded in the build
  plan's Appendix E exactly as O-1's would have been.
- **O-2 (confirmed):** no rescue variant reaches AUC ≥ 0.65 either.
  The engine architecture is OFF; the build plan proceeds on its
  fallback branch exactly as originally written.
- **O′-GRAY (anything else):** Ken decides with the full ten-row
  table; the engine branch then requires his explicit GO recorded
  here. No model resolves it alone.

*Status (2026-07-19): read off — primary = O-GRAY, rescue = O′-GRAY
(no variant clears the band; five clear the 0.65 floor). Ken ruled:
engine branch OFF on this evidence — no explicit GO; scaffold-first
with the S-B windowed-CTC arm next. See the Results-log entry for the
verification, the ruling's riders (s_tx_roll5 kept as an optional
advisory demote-only signal; S-shift pad artifact noted, no
re-probe), and its consequences.*

If S-tx is the adopted gate statistic: whisper transcribe — already
retained in the engine branch for anchors — becomes a gate-time input;
a song with no transcribe output runs **ungated** on that route (lines
ship as aligned; containment per build-plan Appendix A, never a song
failure). The asymmetric-evidence requirement for corroboration
(agreement confirms sync; disagreement only demotes) is satisfied
structurally: the engine's score gate only ever routes lines into the
repair/fill loop (build-plan Appendix E) and never blocks a song.

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

*Amendment (2026-07-19):* Bloodstream demoted to the line-source pool
by design ruling (see Results log, Phase 2a STOP entry) — the word
cohort for 2b is **14** songs, and Bloodstream is exempted from the
word-kind guard on resume.

### 2b. Probe: verify-fit + renders (scratchpad)

For each of the 15 songs (14 after the 2026-07-19 Bloodstream
demotion — see Results log), offline against its existing bundle:

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
   (warped) span. **Emission family — eligible (Ken, 2026-09-01):**
   additionally score the warped richsync timings against the Phase 1b
   cached emissions, per line — the candidate verification statistic
   that tests *timing* directly, where transcribe pairing tests
   text-location agreement; Appendix C chooses between the two families
   (or both) at the lock. *(Amended: this read "If GATE O = O-1".
   GATE O came out GRAY — neither O-1 nor a confirmed O-2 — leaving
   Appendix C's "only if GATE O ≠ O-2" clause undefined. Ken ruled the
   family eligible: Appendix C's adoption rule already self-guards, so
   the procedure decides on 2b's cohorts. Phase 1b emissions are
   cached; the arm adds no forward passes.)*
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
   (iv) **runs (Ken, 2026-09-01):** richsync-guided CTC align — provider
   text force-aligned by CTC inside richsync-guided windows (richsync
   supplies text, line structure and approximate location; CTC supplies
   frame-accurate on-clock timing). A/B'd here against (i) under
   Appendix C's R-5 rule. *(Amended: this arm was gated on GATE O = O-1,
   written when (iv) meant engine machinery — emission oracle plus score
   gate. What the arm actually needs is a windowed CTC align, which
   GATE S selected on evidence (S-2) and `scripts/sb_ctc_adapter.py`
   already implements. Ken ruled the arm runs, so R-5 applies as locked
   instead of resolving to (i) by precondition failure.)*
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

*Status (2026-09-03): read off by Fable, then R-1 ruled by Ken — see the
Results log. **R-1 = NO-GO as the route stands** (gate-driven; the
mechanism is GO on Ken's eyeball, 6 of 10 songs usable), with the
Appendix A demotion applying and the R-4 re-specification measurements
M1-M5 commissioned. **R-4 is a
STOP → Ken**: zero statistics came out discriminative (the procedure needs
≥ 2), the assembled clamp set cannot fail both controls, and the outlier
rule's denominator is unspecified. R-1 **ruled by Ken the same day** as NO-GO as the
route stands, gate-driven rather than mechanism-driven, reversing if a
re-specified Appendix C passes; Appendix A's demotion applies meanwhile. R-2 confirmed.
R-3 SRT-first stands. R-5 no award — arm (iv) carries a window-edge smear
artifact and re-runs after a fix. Seven decisions are Ken's before this
gate can close.*

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

*Amendment (2026-07-19, Decision C — see Results log):* I'll Make a Man
Out of You re-fetched as `word`/0.745 (its full query now surfaces a
confident richsync, so the locked early-exit never re-queried the
title-only variant that won a2). The line-bodies fixture set is **7**;
the song participates in Phase 3 as a word song via the
richsync-line-starts source above, and is exempted from the
recorded-map_rate regression assert on resume.

*Amendment 2 (2026-07-19, Ken-ratified — warp offset-rescue tier; see
the Results log's "S-A warp diagnostic" entry):* `warp_scaffold_cues`
gains a constant-offset rescue tier — when the affine Theil-Sen fit
fails its MAD gate, fit `offset = median(anchor_start −
scaffold_start)` with slope fixed at 1.0 over the same common lines,
accepted iff its residual MAD clears the same `WARP_MAD_GATE_S` and
the same `WARP_MIN_ANCHORS` floor; otherwise densify fallback exactly
as before. Reuses the locked constants — no new thresholds. S-A
re-runs on the amended machinery *before* S-B is built and run, so
both arms and the S-1 re-read share one warp.

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
  *(Does not run — GATE O′ ruled engine OFF, 2026-07-19.)*
- **S-C (if S-B or S-B2 looks competitive):** CTC `slice_align` on the
  SRT cue-align corpus vs the 5b whisper baseline — the direct
  "can CTC improve cue align" measurement on the proven path.
  *Amendment (2026-07-20, Ken-ruled): this bullet's original "13-song"
  figure never matched the corpus (16/16 SRT-sourced songs per
  Baseline 2 and the current on-disk count, confirmed on the Windows
  box after the machine move). Ken confirmed all 16 have proper
  uploader SRTs — S-C runs the full 16, not a 13-song subset.*
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
  *Status (2026-07-19, final): **GO on the S-B arm** — mean PASS
  (0.47 vs 0.54), coverage PASS, flag count PASS (Ken ratified the
  any-defensible-mapping reading), per-song cap PASS (Ken accepted
  both causes: Defying Gravity = correctly-gated structural mismatch,
  Man Out of You = genuine two-voice overlap on baseline-hidden
  lines). See the GATE S final-rulings entry.*
- S-2 (aligner per path): the CTC arm is selected for a path iff it is
  at least as good as the whisper arm on all three of mean re-pace,
  mean worst-overlap, and flag count, with no song > 1.0 s worse on
  overlap; otherwise whisper (proven default). The SRT switch (S-C vs
  the 5b baseline) uses the same rule plus Ken's eyeball veto — extra
  caution on the proven path.
  *Status (2026-07-19): CTC SELECTED for the non-SRT scaffold path —
  strictly better on all three metrics, cap holds (worst worsening
  +0.6). S-C has not run; the SRT switch stays open. Ken intent
  (2026-07-19): S-C **will eventually run** — unordered, not a
  sequenced phase (the SRT route is fully separate; no gate depends
  on it, its GATE C-1 license is already satisfied). Motivation: CTC
  may give tighter word timings on the SRT route and eliminate the
  need for edge snapping (consistent with GATE C's finding and
  Appendix D's snap-off-on-CTC default). Same rule + Ken's eyeball
  veto when it runs; the S-B adapter already proves the slice_align
  contract — the SRT harness just needs the same pluggable hook the
  scaffold harness got.*
- S-3: warp-failure branch = densify fallback iff its flags + overlap
  on the warp-failed songs are ≤ the joint baseline's on those songs;
  tie → densify (one fewer code path).
  *Status (2026-07-19, final): **joint-matcher routing** — densify
  FAILS on Defying Gravity (2.6 vs 0.2 s, robust to arm choice) and
  Ken accepted the coverage trade (crammed interpolated dialog is
  unacceptable for karaoke). Scope: warp-failed = MAD-gate reject
  only. See the GATE S final-rulings entry.*
- S-4: **Appendix D/E constants recorded** (Opus, in
  `plans/ctc-sync-engine.md` — both are already locked as
  design/procedure; this step only fills measured constants such as
  the snap re-enable exception and the gate band).
- S-5: **architecture ruling** — engine branch iff GATE O ∈ {O-1, or
  O-GRAY with Ken's explicit GO} AND S-B2 meets the S-2 comparison
  rule against the best scaffold arm AND Ken concurs on eyeball;
  anything else → scaffold-first (fully specified, lower risk).
  *Status (2026-07-19): the GATE O condition is now unmeetable
  (O′-GRAY ruled, no GO) — S-5 = scaffold-first by rule; what stays
  live at GATE S is S-1/S-2/S-3 on the best scaffold arm.*

Scoring-circularity rule (pre-registered): LRCLIB held-out MAD is **not
a metric for any scaffold-routed song** — once LRCLIB feeds the
scaffold, that oracle is circular (already noted in `835ba2c7`'s plan).
Scaffold/engine quality is judged on re-pace/overlap/flags + eyeball;
the harness's held-out scoring remains valid only for joint-matcher
replays.

## Phase 4 — non-Latin alignment form (GATE L)

Commissioned by Ken 2026-09-01. Rung 2 (the line route) silently drops
every line it cannot romanize: `sb_ctc_adapter.make_slice_align` builds
`kept = [(raw, normalize_word(raw)) ...]` and filters the empties, so a
Hanzi line normalizes to nothing, `kept` empties, and the adapter
returns `None` — the whole line re-paces from its cue. Appendix D's
non-Latin carve-out was locked 2026-07-18 as data-independent design
caution, **not** as a measured finding: no CJK audio has ever been put
through MMS_FA in this project. This phase measures it.

**Scope: Mandarin only.** One character = one syllable = one pinyin
token, so timing-to-character back-mapping is 1:1, without the sub-word
ambiguity the Latin path carries. Japanese (mixed kana/kanji), Korean,
Thai and Arabic do not share that property and stay on the whisper
rescue, untouched. Appendix D's rule is already per-line and
majority-based, so the romanizer gates on majority-CJK lines and
nothing else changes.

**Display text is not at stake.** Appendix A locks the line route to
render the sheet, and the adapter already carries `raw` beside the
alignment form into its returned word list. The romanization is an
internal alignment form only; the singer reads the original script by
construction. No display work is in this phase.

**Prerequisite (Ken's action, blocks the phase):** a Mandarin corpus
with Genius sheets or uploader SRTs, sized like S-C's. No arm runs
until it exists; nothing else in this plan waits on it.

Arms, in order; later arms only where earlier ones justify the cost:

- **L-0 (diagnostic, cheap, no GPU):** on one Mandarin song, dump the
  uroman-style alignment form beside `pypinyin` + `jieba` and record
  heteronym and segmentation damage (多音字 — 长 chang/zhang, 了
  le/liao, 行 xing/hang are common in lyrics; uroman converts
  char-by-char with no context, so it picks wrong readings and runs
  syllables together). Establishes which failure mode is live before
  any GPU time is spent — romanizer quality, or emission quality.
- **L-A:** `pypinyin` + `jieba` word segmentation as the alignment
  form, MMS_FA unchanged, per-character back-map. Adapter delta is one
  function (`normalize_word` → a pluggable alignment-form callable).
  Stated hypothesis: MMS_FA was itself trained on uroman-ized text
  across its 1000+ languages including Mandarin, so its emissions are
  not inherently blind to romanized Chinese — the model has seen it.
  Tones are lost; forced alignment does not need them.
- **L-B (only if L-A fails GATE L):** a second CTC bundle with a Hanzi
  vocabulary, routed on majority-CJK lines.
  `torchaudio.functional.forced_align` is model-agnostic — it takes any
  emission matrix plus token ids — so the emission-slicing recipe
  carries over unchanged. Candidates: character-level CTC fine-tunes
  emitting Hanzi directly from a ~3–5k character vocab
  (`jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn`, the
  TencentGameMate `chinese-wav2vec2` fine-tunes). Out-of-vocab
  characters fall into the existing OOV-skip bookkeeping. Per-character
  timing is what Chinese karaoke wants anyway, one char being one sung
  syllable. Costs: a second model download and VRAM (~1.2 GB for the
  large variant; smaller exist) plus a routing switch on majority-CJK
  lines. The singing-vs-speech domain gap applies, but it is the same
  gap MMS_FA already tolerates on the Latin path. (Charsiu, a
  purpose-built Mandarin forced aligner, is noted and not adopted: its
  frame-classification API does not slot into the emission recipe.)

**GATE L** — the S-2 rule restated on the Mandarin corpus, no new
threshold invented: the romanized-CTC arm is selected iff it is at
least as good as the whisper arm on all three of mean re-pace, mean
worst-overlap and flag count, with no song > 1.0 s worse on overlap;
otherwise whisper (proven default) and Appendix D's carve-out stands as
written. Ken retains the eyeball veto. Rationale for reusing S-2
verbatim: whisper fallback is already acceptable on rung 2, so a
romanized CTC arm only earns its place if it beats whisper on the
failure modes CTC was brought in for — melisma robustness and line-edge
sharpness.

Rulings produced here:

- L-1: romanized alignment form GO/NO-GO (the S-2 restatement above).
- L-2: which romanizer — L-A's `pypinyin`+`jieba`, or L-B's Hanzi-vocab
  bundle. L-B is only reached if L-A fails L-1.
- L-3: **Appendix D's non-Latin bullet amended** with the resulting
  constant, recorded there the way S-2 was.

**Dependencies if L-A ships:** `pypinyin` (pure Python, small) and
`jieba` (~5 MB dictionary) become runtime dependencies, needed only on
the F2 path. Fork rule: the alignment-form callable lands in a new
`pikaraoke/lib/align_form.py`, not as edits to `token_align.py`.

## Remaining execution order (Ken, 2026-09-01) — measure first, lock once

Ken's sequencing ruling: run the remaining measurement program to
completion, then consolidate the build design once, rather than
amending locked appendices as results trickle in. The dependency check
that licenses this: **no remaining probe needs production code.** Only
the V-gates (the build plan's V1/V2, the joint plan's V) are validation
*of* shipped code, which is tautological.

Order — cheapest and highest overturn-risk first:

1. **Joint plan Phase 4 → GATE P** (telemetry only, no GPU). Cheapest
   probe on the list and the highest redesign ceiling: material
   reordering prevalence commissions a section-level DP as its own
   plan, which breaks the 1:1 `line_objects` contract. Measuring that
   late would be the expensive mistake. — ***CLOSED 2026-09-01: GATE P
   = NO-GO*** (Fable's read-off in the joint plan's Results log). Ran
   over 18 genius-origin bundles; the gap and inversion mass is repeat
   cross-attraction plus lyric-version drift, not permutation, so the
   monotonic DP stands and no section-level DP is commissioned. The
   redesign risk this step existed to price is retired.
2. **Phase 2b → GATE R** (this file; four arms per the 2026-09-01
   rulings). Largest blast radius on the routing ladder — R-3 can
   reorder rung 0 against rung 1, and R-1 decides whether the word
   route exists at all. — ***RUN 2026-09-03; GATE R read off, not
   closed***: R-4 STOP → Ken (see the Results log). R-2 and R-3 are
   settled (provider text as-is; SRT-first). ***R-1 ruled 2026-09-03: NO-GO as the route
   stands, mechanism GO*** — the re-specification measurements M1-M5 are
   commissioned in the Results log. R-5 still hangs on Ken's
   remaining decisions — the controls and cohort labels, two constants, the
   edit/structure-mismatch class, an arm (iv) rebuild, and whether the
   R-1 eyeball proceeds now.
3. **Joint plan Phase 2a → GATE J1/J2** (GPU, scratchpad). J2 feeds
   Appendix D's snap policy directly, which currently records
   "re-enable exception: none".
4. **S-E** (Phase 3's unrun optional arm; offline, no GPU align). Cheap
   add-on: informs the build plan's deletion inventory and tests Ken's
   GATE C observation.
5. **Phase 4 → GATE L** (above) — whenever the Mandarin corpus exists.
   Blocks nothing and nothing blocks it but the corpus.

Then **one design-consolidation pass**: re-lock the build plan's
Appendices C, D and E with the real constants in a single revision.

**Carve-out — F2 is a zero-regret build at any point in this
sequence.** Checked against every pending outcome: an R-1 NO-GO only
sends more songs into F2's line-source pool (Appendix A already
specifies that demotion); GATE P and GATE J1 are rung-3 questions;
GATE L is an additive per-line romanizer inside F2's aligner. The
single coupling is GATE J2 possibly flipping snap policy on CTC-timed
routes — a post-pass wiring flag, not a redesign. Build it before or
after the block at Ken's discretion; the argument for pulling it
forward is that rung 2 currently has zero production miles, so every
number on it comes from harnesses.

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

### 2026-07-19 — Phase 2a (--save-bodies) — STOPPED at song 4/17, Sonnet 5 executor

Ran after Build plan Phase E0 (`feat(pipeline): synced-timing fetch
pillar`, committed) landed, per this file's note that E0's lib becomes
the sidecar writer once it exists — `scripts/musixmatch_coverage_improve.py
--save-bodies` now calls `timing_fetch.ensure_timing` per song (real
media path, real `lyrics/<stem>.timing.json` sidecar) instead of
carrying its own writer; the script supplies only the 17-song batch
loop, the recorded-map_rate regression assert, and the control-flag
post-write.

**First body fetched (Popular, `22QYya-LGDY`) — `te` field confirmed
present**, resolving the plan's open question ("the prior LRC-conversion
threw structure away, so this is unverified on our corpus"): richsync
entries carry `ts` (line start, s), `te` (line end, s), `l` (word list,
each `{c: text incl. leading space, o: offset from ts, s}`), `x` (full
line text). Sample entry: `{"ts": 7.25, "te": 15.74, "l": [{"c":
"Whenever", "o": 0}, ...], "x": "Whenever I see someone less fortunate
than I"}` — 61 word-timed lines total for this song.

**3/17 songs completed clean**, both checks passing (kind stayed
`word`, rate within the one-sided 0.05 tolerance):

| song | recorded | new | delta | kind | source |
| --- | --- | --- | --- | --- | --- |
| Popular | 0.630 | 0.629 | -0.001 | word | musixmatch |
| Belle | 0.860 | 0.855 | -0.005 | word | musixmatch |
| Best Part of Me | 0.870 | 0.868 | -0.002 | word | musixmatch |

**STOPPED at song 4/17 (Bloodstream, `Orq_75kFi8I`)** — the pre-registered
kind-downgrade guard fired: `reference_pick` this run picked a *different*
Musixmatch candidate than part (a)'s unrecorded original —
`track_id=82646350`, **"Bloodstream (Arty Remix)" by "Ed Sheeran feat.
Rudimental"** — whose text maps to our sheet *better* than the original
0.50 boundary-case pick (**new map_rate 0.703**, comfortably clearing the
0.05 tolerance) but which has **no richsync on Musixmatch, only a line
subtitle** (`kind: "line"`). Reference-pick's scoring key is
`(map_rate, -|length_delta|)` with no term for `kind` (matching part
(a2)'s original design), so a better-text/worse-timing remix candidate
legitimately outscores a worse-text/better-timing original-recording
candidate. Sidecar persisted as-fetched (line, 0.703, this remix's
track info) — the STOP halts the *batch*, not the write, so this one
song's real result is on disk, just flagged rather than silently
accepted into the word-level cohort.

This is judged a genuine reference-pick finding, not an implementation
bug: part (a)'s own probe table already flagged Bloodstream as "74-line
sheet, boundary case but a real match (checked)" at exactly the 0.50
floor — the most fragile row in the 15-song cohort by construction, and
a boundary case is exactly where a re-run's candidate-list churn (new
remixes indexed, ranking ties) is most likely to flip the winner. Not
re-run further or bridged (per this plan's Model-switching discipline:
STOP and report, not decide) — **remaining 13/17 songs not attempted**.

**Open question for Ken/Opus**: should the word-route selection key
weight `kind` (prefer richsync even at a lower text-map_rate, within
some band) for songs Phase 2a specifically wants word-level for, or is
"best text match, whatever its kind" correct and Bloodstream simply
demotes to the line-level scaffold pool (as Appendix A's routing
precedence already handles: word-route FAIL/absent → the sidecar's line
starts join the line-source pool)? Note this is a **probe-script
question, not an E0 bug** — `ensure_timing`'s production selection logic
is unchanged and behaves identically for any Genius-origin song hitting
this same ambiguity.

**Design ruling (Fable, 2026-07-19) — Decision A resolved: no `kind`
term; the Appendix B key stays locked as-is.** Root cause is genuine
reference-pick ambiguity at a by-construction fragile row (the 0.50
floor boundary case, independently GATE-C-flagged as the C-3
version-mismatch song), not a design gap: the key found genuinely
better text (0.703 vs 0.50) and the guard surfaced the cohort change
instead of swallowing it — both mechanisms worked. A kind-preference
band is ruled out: it would buy word granularity at the cost of text
identity (the matcher-era failure class — Bloodstream's word candidate
is the known crammed-hook offender, "wrong words, precisely timed");
timing quality is adjudicated downstream (Appendix C verify,
`WARP_MAD_GATE_S`, Appendix A routing), where line-kind demotion is a
first-class route; and any band constant would be invented from n=1
(one wide enough to flip this case, ≥ 0.21, lets materially worse
text win across all production genius-origin songs).

**Bloodstream disposition:** the persisted line sidecar (0.703, Arty
Remix track info) stands as-fetched and is authoritative per
reuse-on-disk. Bloodstream exits the 2b word cohort (**15 → 14**) and
joins the line-source/scaffold pool — its sidecar is already the
shape Phase 3's line arm consumes. Appendix C impact: none structural
(the threshold rule is cohort-size-agnostic) and mildly beneficial —
worst-over-PASS is no longer set by a known version-mismatch song.
Phase 1b untouched (its desync labels come from the GATE C renders,
not the 2b cohort).

**Resume (remaining 13 songs):** not as-is — on re-run, disk-first
`ensure_timing` returns Bloodstream's line sidecar and the word-kind
guard would re-fire. The executor exempts Bloodstream from the
word-kind assert via the same mechanism the two controls use
(recorded as-is, flagged), citing this ruling as provenance. The
guard stays armed for the remaining 13 songs.

**2026-07-19 — resume executed, 17/17 clean, 0 STOPs.** Implemented
both rulings first: `clean_key` applied at `ensure_timing`'s entry
(separate commit, gates E0 sign-off per the ruling — see that entry
below) and `SAVE_BODIES_SONGS` gained a `kind_exempt` flag independent
of `control` (Bloodstream is not a wrong-song fixture, so it gets its
own `kind_demoted_ruling` sidecar field rather than being mislabeled
`control: true`). Re-ran `--save-bodies`: the 4 already-fetched songs
(Popular, Belle, Best Part of Me, Bloodstream) reused their on-disk
sidecars unchanged (disk-first, no refetch — Bloodstream's `line`/0.703
now carries `kind_demoted_ruling` on top, added on this pass); the
remaining 13 fetched clean, both guards passing on every one:

| song | recorded | new | delta | kind |
| --- | --- | --- | --- | --- |
| Colors of the Wind | 0.950 | 0.946 | -0.004 | word |
| Domino | 0.670 | 0.910 | +0.240 | word |
| Rock Your Body | 0.980 | 0.981 | +0.001 | word |
| Free | 0.805 | 0.805 | +0.000 | word |
| More Than That | 0.923 | 0.923 | +0.000 | word |
| Let It Go | 0.702 | 0.702 | +0.000 | word |
| Part of Your World | 0.704 | 0.704 | +0.000 | word |
| Like I Love You | 0.869 | 0.869 | +0.000 | word |
| Mirrors | 0.883 | 0.883 | +0.000 | word |
| Seasons of Love | 0.912 | 0.912 | +0.000 | word |
| Can You Feel the Love Tonight | 0.875 | 0.875 | +0.000 | word |
| Incomplete (control) | 0.296 | 0.296 | +0.000 | word |
| Selfish (control) | 0.380 | 0.380 | +0.000 | word |

Notable: **Domino jumped 0.670 → 0.910** (`reference_pick` landed a
materially better-matching candidate than part (a)'s original pick —
the one-sided tolerance is for exactly this case, not drift). The 8
songs newly fetched this pass (not reused) all matched their a2-recorded
rate to 3 decimals, confirming `reference_pick`'s selection is
deterministic against an unchanged catalog when the original candidate
is still the best one. Both controls landed exactly on their recorded
wrong-song rate, `kind: word`, `control: true` written — 2b's
negative-control fixtures are ready. **17/17 sidecars now on disk in
`pikaraoke-songs/lyrics/`, Phase 2a complete.**

Commits: `fix(timing-fetch): apply clean_key at ensure_timing entry`
(Decision B), `fix(scripts): exempt Bloodstream from the --save-bodies
kind guard` (Decision A), `feat(scripts): --save-bodies richsync
persistence for musixmatch_coverage_improve` (original script — the
persisted sidecars live in `pikaraoke-songs/lyrics/`, outside this git
repo, per how every other song-library artifact in this project is
handled).

### 2026-07-19 — Phase 3 setup (--save-line-bodies) — STOPPED at song 3/8; Decision C

Sonnet's line-bodies fetch (the Phase 3 list of 8, same `ensure_timing`
path as `--save-bodies`) ran 2/8 clean, then STOPPED at I'll Make a Man
Out of You (`vGfJeW_CcFY`): the full query now returns a richsync
candidate that clears the confidence bar on its own (track 84351940,
"I'll Make A Man Out Of You" / "Donny Osmond feat. Disney Characters",
`word`, map_rate 0.745), so `reference_pick`'s locked early-exit
returned it without ever re-querying title-only — the variant that
produced a2's recorded `line`/0.851 (that run's full query came back
unconfident, firing the retry). The one-sided map_rate regression guard
fired (0.851 → 0.745); the kind *upgrade* itself was already an
accepted outcome of the line-bodies guard. Sidecar persisted as-fetched
(disk-first contract).

**Design ruling (Fable, 2026-07-19) — Decision C: the early-exit stays
as locked; word/0.745 is the conformant pick; no Appendix B amendment,
no code change; per-song guard exemption; line-bodies cohort 8 → 7.**
(Issued under the same Ken-convened window as Decisions A/B; folded at
Ken's direction.) This is neither a Bloodstream-class ranking question
nor a clean_key-class deviation: Appendix B locks the early-exit
explicitly ("title-only tried only when the full query yields nothing
confident") and today's run executed it exactly. The 0.851 line
candidate was not demoted or mis-ranked — it was **never retrieved this
run**, because a2's result was the same procedure answering different
provider state. Both runs conformant; Musixmatch's index moved
underneath. The guard did its job: surfaced cross-run drift for
adjudication instead of swallowing it. Where Bloodstream was a
*ranking* event (the key adjudicated; the guard caught a kind change),
this is a *retrieval* event (the key never adjudicated; the guard
caught provider drift) — they stress different parts of the pillar, and
both parts held.

**Why no change:** (1) both proposed kind-aware early-exits gate on the
full-query winner's kind, and the winner here is `word` — the best
achievable kind — so both would still skip the retry and change
nothing; adopting either is spec churn. (2) The only change that
recovers 0.851/line is unconditionally running both variants and
key-comparing — doubling query cost corpus-wide (the exact cost the
locked gate exists to avoid) on n=1 evidence of *provider drift*, not
of a procedure defect: Decision A's n=1 refusal again. (3) No
correctness pressure: the word candidate is the original Mulan
recording (Donny Osmond is the film's singing voice — no
Arty-Remix-style version-mismatch flag) and 0.745 clears the bar
comfortably. Had both candidates been on the table, the key would
legitimately have picked 0.851/line (line demotion is first-class per
Decision A) — but nothing obliges the procedure to go looking, and a
selection-time kind preference in either direction stays ruled out.
The 0.851 candidate is *unretrieved*, not "irrelevant because word
exists" — that framing would smuggle in the kind preference Decision A
rejected. Cross-run stability is the disk-first sidecar's job, not the
query surface's: drift only bites on forced refetches, which are
batch-tool territory with exactly this guard armed.

**Disposition:** the word/0.745 sidecar stands as-fetched. It cannot
serve as a line-bodies fixture (a richsync body is a different
artifact), so the song exits that cohort (**8 → 7**) — not orphaned
from Phase 3, whose line-source enumeration already covers it ("for
word songs — richsync line starts"); it participates as a word song
with scaffold line timing from its richsync `ts` values. It does
**not** retroactively join 2b's word cohort (pre-registered cohorts
shrink via guards, they don't grow mid-flight; 2b stays 14);
production routing is cohort-agnostic and routes it word-level per
Appendix A on its sidecar alone.

**Resume (song 3 exempted, songs 4–8 fresh):** exempt the song from
the recorded-map_rate regression assert the same flag-and-accept way
as Bloodstream's `kind_demoted_ruling` (suggested sidecar field:
`query_drift_ruling`), citing this ruling as provenance; the guard
stays armed for the remaining songs.

**2026-07-19 — resume executed, 8/8 clean, 0 STOPs.** Implemented the
exemption: `LINE_BODIES_SONGS` gained a `query_drift_exempt` flag
(mirroring `kind_exempt`'s shape, distinct name — this is a retrieval
event, not a ranking one); I'll Make a Man Out of You's already-persisted
word/0.745 sidecar was reused unchanged from disk (disk-first, no
refetch) and gained `query_drift_ruling` on top. Re-ran
`--save-line-bodies`: the 2 already-fetched songs (Defying Gravity, Be
Our Guest) reused their sidecars unchanged; the remaining 5 fetched
clean:

| song | recorded | new | delta | kind | variant |
| --- | --- | --- | --- | --- | --- |
| NSYNC Paradise | 0.785 | 0.785 | +0.000 | line | netease |
| Hakuna Matata | 0.625 | 0.625 | +0.000 | line | netease |
| What It Sounds Like | 0.811 | 0.811 | +0.000 | line | full |
| In Summer | 0.581 | 0.581 | +0.000 | line | netease |
| The Next Ten Minutes | 0.958 | 0.930 | -0.028 | line | full |

The Next Ten Minutes' -0.028 delta is inside the one-sided 0.05
tolerance (recorded-rate regression, not a STOP) — ordinary reference-pick
variance, not flagged further. All 5 matched their expected `kind: line`
and cleared the guard. **8/8 sidecars persisted (7 line-bodies fixtures
+ 1 query-drift word exemption), 0 STOPs.** `pikaraoke-songs/lyrics/`
now holds 25 sidecars total (17 from Phase 2a + these 8) — Phase 3
setup is complete; the S-A/S-B corpus run can proceed.

Commit: `feat(scripts): --save-line-bodies richsync/line persistence for
the Phase 3 corpus cohort` (script + this Results log entry together).

### 2026-07-19 — Phase 3 S-A (scaffold + whisper corpus run), Sonnet 5 executor

Ran `scripts/scaffold_align_corpus.py` (`--timing sidecar`, default) over
all 17 genius-origin bundles. First pass surfaced two real harness gaps,
neither a design decision — fixed directly (commit
`fix(scripts): scaffold harness tolerates missing YouTube ASR /
media_duration_s`), not escalated: **6/17 songs never had YouTube ASR
captions fetched** (confirmed absent from disk and every backup —
Free, What It Sounds Like, Domino, In Summer, NSYNC Paradise, The Next
Ten Minutes), so `run_song`'s `asr_path` is now `Optional`, degrading
to transcribe-only anchors instead of the corpus runner skipping the
song; **7/17 bundles have `media_duration_s: None`** (the 6 above plus
Seasons of Love), so `duration` now falls back to the vocal stem's own
probed wav length when the bundle field is absent. Verified via a
single-song smoke test (Domino, hit by both gaps) before rerunning the
full corpus.

**17/17 songs aligned clean, 0 failures, 0 hidden lines**, 6/17 show a
drift flag (gap/instant-line signature), 45 mostly-instant lines total
across the corpus (0 parked-tail gap lines):

```
song                                        plc  hid  rea  rep rsec  maxgap gapL instL   anc   scf   ovl(old>new)
----------------------------------------------------------------------------------------------------------------
Jessie J - Domino (Official Video)---UJtB5   67    0    3   20    -    2.0s    0     1    14    61   1.3->4.6  s
Seasons of Love (HD)---UvyHuse6buY           34    0    0    7    -    1.9s    0     0    13    31   5.8->0.7  s
Ed Sheeran & Rudimental­ - Bloodstream [Of   74    0    0   46    -    1.7s    0    13    23    52   9.8->2.3  s
Ed Sheeran - Best Part Of Me (feat. YEBBA)   38    0    0    4    -    1.7s    0     0    16    33   1.1->0.0  s
Wicked - For Good  (2025) 4K - The Girl in   36    0    1   19    -    1.7s    0    17    23     0  31.1->3.2  s
Beauty and the Beast (1991) - Be Our Guest   77    0    2    5    -    1.7s    0     0    61    53   0.0->3.0  s
'Popular' - Wicked 20th Anniversary Editio   62    0    0   13    -    1.6s    0     1    44    39   2.9->1.7  s
NSYNC - Paradise                             65    0    4   26    -    1.3s    0     0    12    51   6.1->5.3  s
'Defying Gravity' - Wicked 20th Anniversar   89    0    3   39    -    1.3s    0     2    43    61   8.4->4.3  s
Josh Gad - In Summer (From 'Frozen'_Sing-A   31    0    0    2    -    1.3s    0     0    24    18   1.4->1.2  s
The Next Ten Minutes Lyrics---0j8kL24ph8U    71    0    1    2    -    1.3s    0     0    63    66  13.4->0.5  s
Beauty and the Beast (1991) - Belle [UHD]-  110    0    1    5    -    1.1s    0     0    85    94   1.5->1.3  s
'Free' _ Official Lyric Video _ Sony Anima   41    0    0    0    -    1.1s    0     0    28    33   4.6->0.0  s
HUNTR_X 'This Is What It Sounds Like' (Mus   53    0    0   22    -    1.1s    0    11    15    43   5.5->0.5  s
Mulan _ I'll Make a Man Out of You _ @disn   47    0    0    7    -    1.0s    0     0    22    35   1.7->2.4  s
Pocahontas - Colors of the Wind (Blu-ray 1   37    0    0    2    -    0.9s    0     0    35    35   0.0->0.0  s
The Lion King - Hakuna Matata Music Video    40    0    0    2    -    0.7s    0     0    19    25   0.0->2.8  s
```

`ovl(old>new)` here is `max_line_overlap` on the bundle's stored
`output_line_timings` (today's persisted production output for that
song) vs. this run's scaffold output — **not** the same measurement as
Phase 0's fresh joint-route replay table above (that table's own
`overlap(rec>new)` column is the joint matcher's internal metric,
computed offline, never written back to the bundle). The two are
different instruments on different routes; reconciling them into the
S-1 GO/NO-GO comparison (mean worst-overlap, flagged-song count,
rendered-line coverage vs. the Phase 0 baseline, same songs) is Opus's
mechanical read-off, not this executor's call — this entry reports the
raw table per the Model-switching discipline ("Output at a GATE is a
table, never a verdict"), it does not rule on S-1.

Per the plan text, Girl in the Bubble is excluded from the S-1
comparison (no line timing at all — `n_scaffold=0` above confirms it,
`n_anchors=23` from ASR+transcribe only); it ran in this table for
completeness since the harness now handles it identically to every
other song, not because it's in scope for S-1.

S-B (CTC `slice_align`, licensed by GATE C-1=yes) has not been run —
it needs a new scratchpad windowed-CTC adapter (Phase 1's recipe,
wrapped to the `(t0, t1, text, label) -> words | None` contract) that
doesn't exist yet, a distinct build step from S-A. Stopping here to
report S-A rather than starting it without a checkpoint.

### 2026-07-19 — GATE S-1 read-off (S-A arm) — NO-GO

**GATE S-1 read-off (Fable executing the locked rule, 2026-07-19) —
S-1: NO-GO on the S-A arm's evidence. Two of the four conjuncts fail
decisively; one passes decisively; one is not mechanically decidable
and goes to Ken (moot for this verdict).** (The Model-switching table
assigns this read-off to Opus; executed by Fable at the requester's
direction in the same convened window as Decisions A–C. Nothing here
trades on design authority — the rule was applied as locked, no
thresholds invented, and Opus re-executing the arithmetic will
reproduce it.)

*Reconciliation recorded (the S-A entry left this to the read-off):*
the Phase 0 table's `overlap(rec>new)` right value and the S-A table's
`ovl(old>new)` right value are different instruments, but both report
the same physical quantity — that route's worst rendered-line overlap
in seconds — so the mechanical pairing is right-value vs right-value
per song, over the 16 in-scope songs (Girl in the Bubble excluded per
the plan text; `scf=0` confirms). Cross-check that the instruments are
comparable enough: on the two songs where both routes render the
identical full sheet, the instruments agree exactly where nothing
changed (Colors of the Wind 0.0 → 0.0) and disagree only where the
scaffold genuinely regressed (Be Our Guest 0.0 → 3.0).

- **Mean worst-overlap strictly lower: FAIL.** Scaffold 1.91 s vs
  baseline 0.54 s (needed < 0.54). Not a gray-zone margin — 3.5× the
  bar in the wrong direction.
- **No song regresses > 1.0 s without a recorded cause Ken accepts:
  FAIL.** Nine songs regress: NSYNC Paradise +4.6, Domino +4.5,
  Defying Gravity +4.1, Be Our Guest +3.0, Hakuna Matata +2.8, Man
  Out of You +2.4, Popular +1.7, Belle +1.3, In Summer +1.2. The S-A
  entry records no causes, so none exist for Ken to have accepted.
  Improvements for the record: Bloodstream 6.7 → 2.3 and Free
  1.0 → 0.0.
- **Rendered-line coverage no lower: PASS decisively.** Scaffold
  renders the full sheet with zero hidden lines on all 16; strictly
  higher than baseline on 14, equal on 2 (Be Our Guest, Colors of the
  Wind).
- **Flagged-song count no higher: NOT MECHANICALLY DECIDABLE → Ken.**
  The baseline flag marks coverage shortfall (8 in-scope songs carry
  the `!` marker); the S-A flag marks drift signature (5 in-scope:
  Domino, Bloodstream, Popular, Defying Gravity, HUNTR_X — the
  entry's 6th, Girl in the Bubble, is excluded). These measure
  different failure modes on different routes — one of which the
  scaffold structurally cannot exhibit (it always renders everything)
  and one the joint route doesn't emit. A naive 5 ≤ 8 favors the
  scaffold, but the rule defines no cross-system mapping and the
  read-off declines to invent one. Moot: the conjunction already
  fails twice.

*What the verdict does and doesn't mean:* the rule's conjunction was
built exactly for this trade — the scaffold bought total coverage at
the price of overlap, and the locked rule says that trade is not GO.
Two things are Ken's, not the read-off's: (1) whether "overlap on
lines the baseline never rendered" is an acceptable recorded cause
for some of the nine regressions — noting it cannot excuse all of
them, since Be Our Guest regresses +3.0 s on an identical 77/77
rendered set, and Domino/Belle/In Summer regress on near-identical
sets; (2) whether the mean clause should ever be recomputed on a
common rendered set — that is a rule amendment, not a read-off.
Procedurally, NO-GO here binds the S-A arm's showing only: S-1
governs the scaffold route, S-B (CTC `slice_align`) has not run, and
the route's final S-1 standing should be re-derived on the best
scaffold arm once S-B lands — consistent with S-2/S-5 already
waiting on it.

**Regression diagnosis (Ken eyeball → mechanism, 2026-07-19).** Ken
eyeballed the nine regressions (scaffold `.ass` vs the joint `.ass`,
same clips). On NSYNC Paradise ~3:25 the overlapping lines are not a
local over-hold — they are from *different sections of the sheet*
(pre-hook and chorus rendering concurrently). That ruled out "the
scaffold just paces line ends too long" and prompted a mechanism
trace (`warp_scaffold_cues` reproduced offline, no GPU — it is pure
text-match + Theil-Sen). The nine split cleanly into two unrelated
failure modes; neither is fixed by changing scaffold selection.

```
song            Δovl  anchors  MAD    mode
NSYNC Paradise  +4.6  12/65    3.28   1: scaffold DISCARDED -> densify fallback
Defying Gravity +4.1  43/89    5.80   1: scaffold DISCARDED -> densify fallback
Domino          +4.5  14/67    0.19   2: warp used; align displaces a repeat
Be Our Guest    +3.0  61/77    0.17   2: warp used; align displaces a line
Hakuna Matata   +2.8  19/40    0.12   2: warp used (signature)
Man Out of You  +2.4  22/47    0.30   2: warp used (signature)
Popular         +1.7  44/62    0.43   2: warp used (signature)
Belle           +1.3  85/110   0.12   2: warp used (signature)
In Summer       +1.2  24/31    0.06   2: warp used (signature)
```

*Mode 1 — scaffold discarded, densify fallback (Paradise, Defying
Gravity).* The MAD gate fired (Paradise 3.28 s over 9 common lines;
Defying Gravity 5.80 s): the external master's clock genuinely does
not fit the audio (Paradise fit slope 1.25 ≈ 25 % tempo delta), so the
scaffold is *correctly* rejected. The route then densifies the anchors
alone — and Paradise has no YouTube ASR, so whisper-transcribe placed
only 12/65 sheet lines, clustered at line-ids 2–12 plus a lone 41.
`densify_cue_spans` linearly interpolates across the 29-line hole
(id 12→41), spreading whole sheet sections across a span they aren't
sung in; that interpolation ramp is why unrelated sections render
concurrently. Root cause is upstream — a sheet/audio version mismatch
(only 12/65 lines even transcribe-match). The warp gate did its job;
the damage is the fallback, which owns to **GATE S-3** (densify-fallback
branch) and **Appendix A routing**: version-mismatch songs should route
to the joint matcher or flag, not densify sparse clustered anchors.
*(Correction, later same day: Paradise's half of this reading is
superseded — the gate firing was anchor contamination, not a version
mismatch or tempo delta; Ken's ground truth + the offline refit are in
the S-A warp diagnostic entry below. The Defying Gravity half stands.)*

*Mode 2 — warp clean, overlap enters at the align stage (the other
seven).* Theil-Sen fit MAD ≤ 0.43 on all seven; the scaffold is
accepted and the warp cue_spans are monotonic and non-overlapping.
Verified on two, including the read-off's strongest counter-case:
Domino's warp cues place L29 "…tension" [1:31.15–1:34.70] then L30
"Now I'm breathin'" [1:34.70–1:38.48] in order, but the `.ass` pulls
L30 (a repeat — the same line also sits at L5) back to 1:29.82, swapped
before L29 and overrunning it; Be Our Guest's warp cues place L69 "Let
us help you…" [3:08.12–3:09.77] then L70 "Course by course…"
[3:09.77–3:11.42] in order, but the `.ass` pulls L70 back to 3:05.79,
before L69, fully containing it. In both the overlap is introduced by
`align_song`'s windowed whisper pass displacing a line several seconds
outside its (correct) cue window — the repeat-line displacement class
the SRT cue-align path already hardened against, re-exposed here because
warp cue windows are looser at repeats than tight SRT cues. Downstream
of a healthy warp; independent of the scaffold decision.

*What this settles for the read-off.* (1) The eyeball **confirms** the
NO-GO — genuine artifacts, not the metric mis-scoring a fine render.
(2) The acceptable-cause question the read-off left to Ken — whether
"overlap on lines the baseline never rendered" excuses some regressions
— does **not** apply to the seven Mode-2 songs: their overlaps are
same-line align displacements, not new-line artifacts (Be Our Guest,
+3.0 on an identical 77/77 set, is the proof), so that excuse is
unavailable for exactly the songs the read-off flagged it couldn't
cover. (3) The two modes are separately owned — Mode 1 → S-3 /
Appendix A, Mode 2 → an `align_song` repeat-displacement fix portable
from the cue-align path — and weighting the scaffold differently fixes
neither.

### 2026-07-19 — S-A warp diagnostic (Paradise) + Ken-ratified amendment: constant-offset rescue tier

Trigger: Ken supplied ground truth on NSYNC Paradise — he made the
video himself: the studio track prepended with live-concert dialog
footage, so the correct scaffold model is a *constant offset*, not a
tempo change. That contradicts the regression diagnosis above, whose
Mode-1 reading for Paradise ("fit slope 1.25 ≈ 25% tempo delta …
sheet/audio version mismatch; the warp gate did its job") is hereby
superseded; the Defying Gravity half of Mode 1 stands.

**Mechanism (offline reproduction, no GPU — Fable).** Paradise ran on
12 transcribe-only anchors (no YouTube ASR); 9 are common with the
51-line sidecar scaffold, and 3 of the 9 are mis-mapped onto repeated
lyric lines (residuals +46 s, +72 s, +72 s — chorus text matched to
the wrong occurrence). Theil-Sen draws slopes from point *pairs*, so
3-of-9 bad points contaminate 21 of 36 pairwise slopes (58%) — the
affine fit came out slope 1.248 / MAD 3.28 s, fired the 2.0 s gate,
and the 51-line scaffold was discarded for densify over the same 12
anchors (3 of them wrong): the actual source of the +4.6 s
regression. Fixing the slope at 1.0 and taking `offset =
median(anchor − scaffold)` gives +24.24 s with residual MAD 0.47 s —
the 6 clean anchors agree to under a second. The mis-mapped repeat
anchors themselves are the known upstream lyric-repeat lever, out of
scope; the offset tier contains their damage.

**All-16 sweep (same offline harness).** 14/16 songs fit affine with
slope 0.99–1.02 and MAD ≤ 0.45 s — the warp is not their problem, and
all seven Mode-2 regressions sit in this group (overlap enters at the
align stage; owned as recorded above — the S-B/S-2 comparison
measures whether the CTC arm removes it before any
repeat-displacement port is considered). The only other gate-firer is
Defying Gravity, where rejection is *correct*: slope 0.79 / MAD
5.80 s, and the offset-only model also fails (MAD 10.27 s) — a
structurally different recording. Discrimination is clean on exactly
this corpus. Residual-trimming the affine fit was considered and
**rejected**: it "rescues" Defying Gravity onto 5 cherry-picked
points (MAD 0.27 — would wrongly accept a bad scaffold) while leaving
Paradise below the 5-anchor floor (4 survivors).

**Ratified change (Ken, 2026-07-19).** `warp_scaffold_cues` gains a
constant-offset rescue tier, tried only when the affine path fails
(fit `None` or MAD > gate) and `len(common) ≥ WARP_MIN_ANCHORS`:
`offset = median(anchor_start − scaffold_start)` over the common
lines; accept iff `median(|residual|) ≤ WARP_MAD_GATE_S`; on accept,
proceed through the existing warp body with `slope = 1.0, intercept =
offset`; on reject, densify fallback unchanged. Both constants are
the locked existing ones — no new thresholds. Strictly additive: the
14 affine-clean songs cannot reach the new code path.

**Execution (Sonnet, sequenced before S-B):** implement + unit tests
(a Paradise-shaped contaminated-common case rescued; a
Defying-Gravity-shaped case still densifies; an affine-clean case
untouched), log which warp path each song takes, re-run S-A over all
17. Expected: Paradise is the only rescue; Defying Gravity stays
densify; any *other* song changing path = STOP → Ken. Output is the
raw table, never a verdict; the S-1 re-read happens on the best
scaffold arm after S-B runs.

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

### 2026-07-19 — Phase 1b pre-registered labels (Ken time ranges → line-id ranges), Sonnet 5 executor

Ken supplied rough time ranges (2026-07-19) for 6 songs' desync
sections plus 4 additional well-behaved end-to-end songs. Per step 3's
instruction ("Ken supplies rough time ranges; the executor records
them as line-id ranges... before computing scores"), each range is
mapped here against that song's bundle `output_line_timings` (line
included iff its `[start, end]` span overlaps Ken's range at all;
boundary lines noted). No scores computed yet — this is the label
registration only.

**Desynced (line-id ranges, per song):**

| song | Ken's range | line-ids | note |
| --- | --- | --- | --- |
| Bloodstream | start–0:06 | 0–1 | line1 (hummed intro) extends to 0:11.26, only its head is in-range |
| Bloodstream | 1:55–2:00 (crammed 2nd hook) | 26–31 | lines 27–30 are 4 repeats collapsed onto one identical [1:57.94–1:58.84] span — the cram signature itself |
| Bloodstream | 2:20–2:40 | 36–38 | lines 36/37 are concurrent duplicate spans |
| Bloodstream | 2:58–end | 51–73 | includes the fully-collapsed zero-width block 66–73 [3:52.33–4:02.17] shared by 8 lines |
| Popular | start–0:04 | 0–5 | lines 0–4 are spoken dialog collapsed to [0:00.00–0:02.92] |
| Popular | 2:28–2:32 | 50–51 | |
| Popular | 2:45–2:51 | 59–61 | |
| Defying Gravity | 0:07–0:56 | 0–31 | lines 0–20 are the pre-song dialog block collapsed to [0:00.00–0:08.36] |
| Defying Gravity | 1:38–1:41 | 44–46 | |
| Defying Gravity | 2:19–2:36 | 55–66 | includes the 9-line collapsed dialog block 56–64 [2:26.67–2:30.59] |
| Defying Gravity | 3:29–end | 78–88 | **= the matcher-plan-era known-bad OST-only outro group (79–88)** — reuse directly as step 3's phantom cross-check fixture, no separate list needed; line80 is zero-width |
| Hakuna Matata | 0:30–0:48 | 3–4 | line4 nominally ends 0:35.32; the described "drag" is the 14.4s unfilled gap to line5 at 0:49.72, not a sheet line — flag as a fallback/interpolation artifact, not a scored line span |
| Hakuna Matata | 1:55–end | 29–39 | line28 ends 1:53.98, just before Ken's 1:55 mark, so it's excluded by the overlap rule; lines 34–39 are zero-width (the dialog swallowed them to nothing — expected desync signature) |
| Rock Your Body | 2:28–3:10 | 68–72 | ~31.5s unfilled gap after (2:40.73→3:12.24) — the quiet-outro/adlib stretch Ken flagged has no sheet line to score at all |
| Rock Your Body | 4:00–end | 95–102 | ~18.3s unfilled gap before (3:57.65→4:15.99), same signature |
| Zayn | 1:55–2:05 | 28–33 | lines 32/33 overlap out of chronological order in the production timing itself (line33 starts 2:03.86, before line32's 2:04.28) — the "overlapping vocals" Ken described |
| Zayn | 3:30–end | 55–59 | |

**Synced — same songs' good stretches:** the complement of the above
ranges within each of the 6 songs (e.g. Bloodstream lines 2–25, 32–35,
39–50, 74 is n/a since 73 is last — i.e. everything not listed above).
Zero-width lines inside a "good" complement (none found outside the
ranges above) would be excluded the same way at scoring time.

**Synced — well-behaved end-to-end:** Belle (110 lines), Girl in the
Bubble (36 lines), John Legend/Ariana Grande Beauty and the Beast (56
lines), Incomplete (27 lines). **Only 4, not the plan's target of 5**
— Rock Your Body was the plan's other suggested pick, but Ken's own
data for it (above) shows two real desync stretches, so it no longer
qualifies as end-to-end clean and was not substituted into this set.
Flagging for Ken/Opus visibility, not blocking: the labeled pool is
already large (6 partial + 4 full songs) and step 5's read-off doesn't
require exactly 5 end-to-end songs, but a 5th is Ken's to add if he
wants one.

**Not yet done (at label-registration time):** emissions had not been
recomputed, no scores existed, no AUCs computed — see the follow-on
entry below for the completed run.

### 2026-07-19 — Phase 1b run (GATE O primary + GATE O′ rescue), Sonnet 5 executor

Scratchpad scripts (never committed, per ground rules — this is neither
of the two named exceptions):
`phase1b_score_oracle.py`/`phase1b_labels.py`/`phase1b_auc.py`/
`phase1b_phantom.py`/`phase1b_rescue.py`/`phase1b_rescue_auc.py`.
Emissions, line-scores, and rescue-scores caches also live in the
scratchpad, not the repo.

**Step 1–2 (emission recompute + primary score).** Re-ran the eyeball
probe's chunked ~20 s recipe (`plans/ctc-forced-align-eyeball.md` §"CTC
recipe" — that script itself was never on disk, run by Ken directly
from a scratchpad copy) over all 33 corpus songs: MMS_FA emission
cached per song, forced aligner re-run over `align_lines` to recover
per-word `TokenSpan.score` (not persisted by the original eyeball run),
grouped into per-line mean/min-word raw scores, z-normalized per song.
**33/33 clean**, no failures. One environment fix needed: this
torchaudio build's `torchaudio.load` requires `torchcodec`, not
installed in `pik`; switched to `soundfile.read` for the decoded-wav
load, no recipe change.

**Implementation-time bug caught + fixed (S-decode only, step 4):** a
raw unconstrained argmax over the emission's full 29-class output
*always* selects the star class (id 28) — checked directly:
`emission[:, 28]` is exactly `0.0` (log-prob 1.0) on every frame of
every song inspected, a constant DP-padding column the aligner appends
for its own constrained-alignment use, not a real per-frame prediction.
Greedy decode must argmax over `emission[:, :28]` only; fixed before
any S-decode numbers were recorded (caught via a targeted debug probe
on Popular line 5, where decode against the padded 29-class slice
produced an empty string every time).

**Step 3 (labels + cross-check).** Labels: the pre-registered ranges
above (140 desynced lines, 517 synced lines — the 6 partial songs'
flagged ranges + complements, plus the 4 end-to-end songs). Coverage:
100% of labeled lines scored (every line in every labeled range has at
least one alignable word — the sheet-text-driven score doesn't depend
on production's own placement, so production's degenerate/zero-width
groups don't cost coverage here). Phantom cross-check (Defying Gravity
79–88, production-placed spans, `mean_word_raw` scored directly against
those fixed spans — not the CTC's own free placement): 9/10 lines
scored (line 80 has no production span), z-normalized against Defying
Gravity's own song-level mean/sd —

```
line  span(s)              mean_word_raw   mean_word_z
 79   [210.47,214.63]         0.0549          -0.764
 81   [214.63,217.07]         0.2037          -0.026
 82   [216.47,217.17]         0.0114          -0.760   (concurrent w/ 83,84)
 83   [216.47,217.17]         0.0470          -0.673
 84   [216.47,217.17]         0.0343          -0.624
 85   [217.17,218.85]         0.1622          -0.184
 86   [218.85,219.51]         0.0104          -0.763
 87   [219.51,221.55]         0.0108          -0.760
 88   [221.55,225.25]         0.0989          -0.426
```

phantom median z = **−0.624**, vs the labeled synced pool's p25 on the
same statistic = **−0.719** (from the table below). −0.624 is *not*
below −0.719 — **the cross-check does not confirm directionally** on
the candidate primary statistic (mean_word_z).

**Steps 4–5 (rescue stats + full ten-row table).** Computed all five
statistic families for the 10 labeled songs, each per-line and as a
5-line centered rolling median (clamped at song edges): mean/min-word-z
(reused from the primary pass), S-decode (`difflib.SequenceMatcher`
ratio, decoded vs. expected normalized text over the line's own aligned
span), S-shift (`-|realigned midpoint − current midpoint|`, realigned
within the line's own span ±5.0 s, clamped to song bounds), S-tx
(normalized-token multiset-intersection fraction against
`transcribe_words` in the line's span ±2.0 s — **4/10 labeled songs
have no `transcribe_words`**: Rock Your Body, Zayn, John Legend/Ariana
Grande Beauty and the Beast, Incomplete; S-tx coverage drops to 116
desynced / 295 synced with those excluded, still ≥10 per class so it is
read off per the plan's coverage rule).

**GATE O primary table** (mean-word-z, min-word-z; AUC = P(random
synced line scores higher than random desynced line), band = does a
cut exist with ≤10% synced below it and ≤10% desynced above it):

| variant | AUC | synced p25 | band cut | synced_below | desynced_above | band_ok |
| --- | --- | --- | --- | --- | --- | --- |
| mean_word_z | 0.7162 | −0.719 | −0.260 | 38.7% | 17.9% | **False** |
| min_word_z | 0.5693 | −0.630 | −0.153 | 58.0% | 10.0% | **False** |

Best AUC (mean_word_z, 0.7162) is in [0.65, 0.85); band fails; phantom
cross-check fails directionally (above). Per-song coverage: 140/140
desynced lines scored, 517/517 synced lines scored across all 10
songs — full detail (per-song breakdown) in the scratchpad
`auc_final.txt`, reproducible via `phase1b_auc.py`.

**GATE O′ rescue table** (the 8 non-primary-per-line rows: mean/min-
word-z rolling-5, S-decode/S-shift/S-tx × {per-line, rolling-5}); O-1's
exact bars applied identically to each:

| variant | n_desync | n_sync | AUC | band cut | synced_below | desynced_above | band_ok |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mean_word_z_roll5 | 140 | 517 | 0.7536 | 0.003 | 43.7% | 10.0% | False |
| min_word_z_roll5 | 140 | 517 | 0.5931 | −0.375 | 49.1% | 13.6% | False |
| s_decode | 140 | 517 | 0.7933 | 0.358 | 33.1% | 13.6% | False |
| s_decode_roll5 | 140 | 517 | 0.8270 | 0.360 | 30.6% | 7.9% | False |
| s_shift | 140 | 517 | 0.5386 | −1.476 | 27.9% | 62.9% | False |
| s_shift_roll5 | 140 | 517 | 0.5824 | −1.476 | 14.1% | 65.0% | False |
| s_tx | 116 | 295 | 0.8767 | 0.652 | 20.3% | 7.8% | False |
| s_tx_roll5 | 116 | 295 | **0.8964** | 0.633 | 18.3% | 8.6% | False |

**No variant's band clears the ≤10%/≤10% bar** — including s_tx and
s_tx_roll5, whose AUCs alone clear the O-1 AUC bar (≥0.85). Since O-1′
requires all three bars (AUC + band + phantom) on the *same* variant,
band failure alone already disqualifies every rescue variant; the
phantom cross-check was not separately computed for the 8 rescue
variants; per the S-1 read-off's own precedent for a moot conjunct,
that check would not change the outcome once band has failed.

**Observation, not a proposed change:** S-shift's AUC (0.54/0.58, near
chance) is the weakest of the eight — plausibly because its pre-
registered ±5.0 s realign pad is narrow relative to this corpus's
actual desync spans (several run 15–60 s, e.g. Defying Gravity's dialog
blocks, Hakuna Matata's swallowed outro), so a desynced line's true
position is often outside the window the realign is allowed to search,
capping how far it can jump regardless of how wrong the current
placement is. The pad is a locked plan constant; flagging for Ken/Opus
to weigh, not adjusting it unilaterally.

**What this does and doesn't settle.** Mechanical facts only, no
verdict computed (executor discipline — Judge is Opus, escalations go
to Ken): best primary AUC (0.7162) is ≥0.65 so the primary read-off is
not O-2 by that bar; it is also not O-1 (AUC <0.85, band fails, phantom
fails). Of the 8 rescue variants, none clears all three O-1 bars
simultaneously (band is the universal blocker), but several clear the
AUC ≥0.65 floor (mean_word_z_roll5, S-decode, S-decode_roll5, S-tx,
S-tx_roll5), so the rescue read is not a clean O-2 confirmation either.
Reproducible via `phase1b_auc.py` / `phase1b_rescue_auc.py` /
`phase1b_phantom.py` against the cached scratchpad emissions.

### 2026-07-19 — GATE O + GATE O′ read-off and Ken's ruling — engine branch OFF; S-B next

**Read-off (mechanical, applied to the run entry above):** primary =
**O-GRAY** — best AUC 0.7162 (mean_word_z) lies in [0.65, 0.85), the
≤10%/≤10% band fails (38.7%/17.9% at the best cut), and the phantom
cross-check fails directionally (phantom median z −0.624 is not below
the synced p25 −0.719). Rescue = **O′-GRAY** — no rescue variant
clears all three O-1 bars (the band is the universal blocker,
including for s_tx/s_tx_roll5 whose AUCs 0.8767/0.8964 clear the AUC
bar alone), and five variants sit above the 0.65 floor
(mean_word_z_roll5, s_decode, s_decode_roll5, s_tx, s_tx_roll5), so
the rescue read is not an O-2 confirmation either. Per the locked
rule, O′-GRAY goes to Ken with the full ten-row table. Process note:
the Model-switching table assigns GATE read-offs to Opus; executed by
Fable at Ken's direction, same convened window as the S-1 read-off —
rule applied as locked, nothing interpreted.

**Verification (Fable, before advising on the ruling):** the three
headline rescue AUCs were independently recomputed from the raw
per-line score caches (`rescue_scores/*.json`), not via the AUC
scripts — exact match (s_tx_roll5 0.8964 at 116/295, s_decode_roll5
0.8270 and mean_word_z_roll5 0.7536 at 140/517). A full cut sweep on
s_tx_roll5 confirmed no threshold clears ≤10%/≤10%; the true minimax
cut (0.500) reaches 12.5% synced-below / 9.5% desynced-above. The
synced false-flag mass at that cut concentrates in Girl in the Bubble
(16 lines) and Belle (9) — wet/ensemble vocals where transcribe token
recall collapses — so the band failure is systematic (an instrument
weakness on the transcribe side), not sampling noise: a gate adopting
s_tx_roll5 would routinely route GATE C's showcase-perfect song into
repair.

**Analysis put to Ken for the gray ruling:** (1) the whisper
precedent replicated — confidence-type statistics fail (AUC
0.57–0.75) while content-corroboration statistics almost work
(0.88–0.90); the emission does not know when it is wrong, a second
engine's transcript nearly does. (2) The CTC-first engine's
distinctive premise — *emission-internal* self-policing — is
specifically what did not qualify (best emission-internal variant
s_decode_roll5, AUC 0.827, ~30% synced false-flags). (3) Every
statistic family improves under rolling-5 → the separable object is
the section, not the line, matching GATE C's C-3; sectional desync
under free whole-song alignment is exactly the failure mode a
scaffold prior with windowed alignment prevents by construction.
(4) S-1's NO-GO on the whisper-scaffold arm and this O′-GRAY point at
the same untested cell: scaffold + windowed CTC = Phase 3 S-B.

**Ken's ruling (2026-07-19):** engine branch **OFF** on this evidence
— no explicit GO; proceed scaffold-first with the S-B windowed-CTC
arm next. Consequences: S-B2 does not run; 2b's GATE-O-conditional
emission-score statistics stay off; GATE S ruling S-5's engine
condition is unmeetable, so S-5 = scaffold-first by rule (S-1, S-2,
S-3 remain live on the best scaffold arm); the build plan proceeds on
the fallback branch (F1/F2) and its Appendix E gate band stays
unfilled. Riders: **s_tx_roll5** (AUC 0.8964) is recorded as an
optional *advisory, demote-only* corroboration signal adoptable later
at Ken's discretion — its structural role already only routes lines
toward repair and never blocks a song, so the asymmetric-evidence
requirement is preserved; **S-shift** is not re-probed despite the
plausible ±5.0 s-pad artifact — a displacement statistic detects
free-alignment drift, which the windowed architecture eliminates, so
a wider-pad re-run only earns its cost if a score gate is ever
revisited. Ken also deferred the pending /code-review batch
(`2dc88a2`, `b3da6f7`, `2ef39f7`, `4c8698a`) until the production
phase begins.

### 2026-07-19 — Offset-rescue tier landed + S-A re-run on amended machinery, Sonnet 5 executor

Implemented the Ken-ratified constant-offset rescue tier
(`pikaraoke/lib/cue_align.py:warp_scaffold_cues`, commit `9b4229b`):
when the affine Theil-Sen fit misses `mad_gate` (or has no fit), a
fixed-slope offset model — `offset = median(anchor_start -
scaffold_start)` over the same common lines — is tried, accepted
under the identical `mad_gate`/`WARP_MIN_ANCHORS`; on reject, densify
fallback exactly as before. No new constants. Three unit tests added
(affine-clean unchanged, Paradise-shaped contaminated-common rescued,
DG-shaped both-models-fail still densifies) — 63/63 `test_cue_align.py`
green. Each call now logs its path (`affine-ok` / `offset-rescue` /
`densify-fallback` / `densify-fallback (no scaffold)` for the
pre-existing empty-scaffold branch, added for full per-song coverage).

Re-ran `scripts/scaffold_align_corpus.py` over all 17 genius-origin
songs on the amended machinery. Per-song warp path (run order):

| # | song | warp path |
|---|---|---|
| 1 | Defying Gravity | densify-fallback (MAD gate, both models fail) |
| 2 | Free | affine-ok (slope 0.9974) |
| 3 | Popular | affine-ok (slope 1.0074) |
| 4 | Be Our Guest | affine-ok (slope 1.0017) |
| 5 | Belle | affine-ok (slope 1.0009) |
| 6 | Best Part Of Me | affine-ok (slope 1.0002) |
| 7 | Bloodstream | affine-ok (slope 0.9939) |
| 8 | HUNTR/X | affine-ok (slope 1.0147) |
| 9 | Domino | affine-ok (slope 1.0124) |
| 10 | In Summer | affine-ok (slope 0.9975) |
| 11 | Man Out of You | affine-ok (slope 0.9881) |
| 12 | Paradise | **offset-rescue** (offset +24.241s) |
| 13 | Colors of the Wind | affine-ok (slope 0.9991) |
| 14 | Seasons of Love | affine-ok (slope 0.9542) |
| 15 | Hakuna Matata | affine-ok (slope 1.0078) |
| 16 | Next Ten Minutes | affine-ok (slope 1.0005) |
| 17 | Girl in the Bubble | densify-fallback (no scaffold found) |

Guards held exactly: Paradise is the only offset-rescue, Defying
Gravity is the only MAD-gate densify, no other song's path changed
from the pre-amendment run (Girl in the Bubble's "no scaffold" branch
is unchanged pre-existing behaviour, only newly logged). 14 affine-ok
+ 1 offset-rescue + 2 densify = 17, matching the warp diagnostic's
all-16-sweep count (14 clean + DG) plus Paradise now resolved and
Girl in the Bubble's separately-known no-sidecar case.

Full corpus metrics table (`plc`=placed, `hid`=hidden, `rea`=realigned,
`rep`=repaced, `rsec`=resectioned, `maxgap`/`gapL`/`instL`=artifact
counts, `anc`/`scf`=anchor/scaffold coverage, `ovl`=max inter-line
overlap old→new pipeline):

```
song                                        plc  hid  rea  rep rsec  maxgap gapL instL   anc   scf   ovl(old>new)
----------------------------------------------------------------------------------------------------------------
Jessie J - Domino (Official Video)---UJtB5   67    0    3   20    -    2.0s    0     1    14    61   1.3->4.6  s
Seasons of Love (HD)---UvyHuse6buY           34    0    0    7    -    1.9s    0     0    13    31   5.8->0.7  s
Ed Sheeran & Rudimental­ - Bloodstream [Of   74    0    0   46    -    1.7s    0    13    23    52   9.8->2.3  s
Ed Sheeran - Best Part Of Me (feat. YEBBA)   38    0    0    4    -    1.7s    0     0    16    33   1.1->0.0  s
Wicked - For Good  (2025) 4K - The Girl in   36    0    1   19    -    1.7s    0    17    23     0  31.1->3.2  s
Beauty and the Beast (1991) - Be Our Guest   77    0    2    5    -    1.7s    0     0    61    53   0.0->3.0  s
'Popular' - Wicked 20th Anniversary Editio   62    0    0   13    -    1.6s    0     1    44    39   2.9->1.7  s
'Defying Gravity' - Wicked 20th Anniversar   89    0    3   39    -    1.3s    0     2    43    61   8.4->4.3  s
Josh Gad - In Summer (From 'Frozen'_Sing-A   31    0    0    2    -    1.3s    0     0    24    18   1.4->1.2  s
The Next Ten Minutes Lyrics---0j8kL24ph8U    71    0    1    2    -    1.3s    0     0    63    66  13.4->0.5  s
Beauty and the Beast (1991) - Belle [UHD]-  110    0    1    5    -    1.1s    0     0    85    94   1.5->1.3  s
'Free' _ Official Lyric Video _ Sony Anima   41    0    0    0    -    1.1s    0     0    28    33   4.6->0.0  s
HUNTR_X 'This Is What It Sounds Like' (Mus   53    0    0   22    -    1.1s    0    11    15    43   5.5->0.5  s
Mulan _ I'll Make a Man Out of You _ @disn   47    0    0    7    -    1.0s    0     0    22    35   1.7->2.4  s
Pocahontas - Colors of the Wind (Blu-ray 1   37    0    0    2    -    0.9s    0     0    35    35   0.0->0.0  s
NSYNC - Paradise                             65    0    0    3    -    0.9s    0     1    12    51   6.1->0.4  s
The Lion King - Hakuna Matata Music Video    40    0    0    2    -    0.7s    0     0    19    25   0.0->2.8  s
```

Paradise: old_ovl→new_ovl 6.1s→0.4s, consistent with the diagnostic's
prediction that the rescue removes the densify-caused regression
(previously discarding the 51-line scaffold for 12 anchors, 3 of them
mis-mapped). No crashes; two per-line whisper `align_refine` errors
(pre-existing worker fallback path, "re-pacing from cue") on unrelated
lines, not warp-related. Output is the raw table, never a verdict —
the S-1 re-read happens on the best scaffold arm after S-B runs, per
the diagnostic's own sequencing.

### 2026-07-19 — Phase 3 S-B (CTC slice_align adapter + corpus run), Sonnet 5 executor

Built a CTC forced-align adapter behind the same `cue_align.align_song`
`slice_align` contract the whisper arm uses (`(t0, t1, text, label) ->
absolute-time words | None`), wrapping Phase 1's proven MMS_FA recipe
verbatim (chunked forward pass, `normalize_word` charset filter with
dual raw/normalized bookkeeping so an OOV word drops from the
tokenizer input but every surviving word keeps its real display text,
frame->seconds via the cached `ratio`) — the same recipe Phase 1b's
33/33-clean run and this plan's Phase 1 eyeball already validated, no
changes to the alignment math itself.

Adapter (`sb_ctc_adapter.py`) lives in the scratchpad only, per ground
rules. Emissions: **sliced from Phase 1b's cached full-song emissions**
(`scratchpad/emissions/<stem>.pt`, scratchpad-to-scratchpad reuse, all
17 corpus songs already cached from the 33-song Phase 1b run) rather
than a fresh per-slice GPU forward pass — one whole-song forward pass
per song, already on disk, sliced by frame index on every section/line
call. This made the corpus run essentially GPU-forward-pass-free
(seconds, not minutes).

Committed harness hook (commit `1d5a1a0`): `scaffold_align_song.run_song`
gained a `make_slice_align` parameter (default: the existing whisper
factory), and `scaffold_align_corpus.py` gained a generic
`--slice-align-module PATH` flag that dynamically loads a module's
`make_slice_align` — no scratchpad path or CTC-specific code committed,
the hook is aligner-agnostic. 63/63 `test_cue_align.py` unaffected (no
production code touched, only the two scaffold scripts); import-smoke
clean.

Ran the same 17-song corpus (`--slice-align-module
sb_ctc_adapter.py`), same metrics, same table format. Warp paths were
identical to the S-A re-run (warp is computed once from the anchors/
scaffold, independent of which forced-aligner slices the audio) —
confirms the two arms are being compared on the same cue-span
foundation, as intended.

Two songs threw a CTC-specific `RuntimeError` ("targets length is too
long for CTC") on one large multi-line section each: Bloodstream
(lines 36-73, 38 lines) and HUNTR/X (lines 33-52, 20 lines). Root-caused
before recording: in both cases the section's real time window is
degenerate (Bloodstream's is 245.65s-246.90s, ~1.25s, for 38 lines/283
words) because the underlying cue anchors themselves collapsed onto
nearly one timestamp — this is Bloodstream's already-flagged "2:58-end,
same overlap chants" desync region from Ken's Phase 1b labels, an
upstream anchor-data pathology, not an adapter defect. The existing
broad `except RuntimeError: return None` (mirroring
`_make_slice_align`'s own `except (RuntimeError, subprocess.
CalledProcessError)`) catches it exactly as designed, and
`align_song`'s cue-repace fallback takes over — both arms degrade
identically on these lines (S-A's whisper pass also repaces 46/74 and
22/53 lines on these same two songs). Not a STOP: the contract already
specifies "None on any aligner failure", and this is a new failure
*mode* under that same contract, not a new failure *case* requiring an
unspecified design choice.

**Chunk-seam validation (post-hoc, Ken's question):** reusing the
cached whole-song emission (chunked into independent, non-overlapping
20s forward passes per Phase 1b's recipe) instead of a fresh per-slice
forward pass is architecturally sound for CTC in a way it is not for
whisper — the acoustic-model step (`model(audio) -> emission`) takes
no text and is agnostic to how it will later be sliced, unlike
`stable_whisper`'s `align_refine`, which jointly aligns a given audio
window against given text and cannot be decoupled that way. The actual
alignment DP (`aligner(emission_slice, token_ids)`) still runs fresh
per `(t0, t1, text)` call; only the underlying per-frame log-probs are
reused. This is the same technique Phase 1b already ran (33/33 eyeball
clean) for word/line scoring and the S-shift rescue variant.

The one real risk this raises — a section boundary landing inside a
20s chunk seam, which a fresh un-chunked recompute wouldn't have — is
not hypothetical on this corpus: Bloodstream's "lines 6-11" section
(21.93s-40.20s) straddles the emission's chunk boundary at 40s.
Spot-checked directly: sliced-from-cache word timings vs. a fresh,
un-chunked forward pass over exactly that window agree to ≤20ms
(one frame) on 33/34 word boundaries, with the one exception (a word
ending exactly at the 40s seam) off by 100ms. Two orders of magnitude
under this pipeline's own timing tolerances (`PAUSE_SLACK_S`,
`DRIFT_GAP_S`, `MAX_WORD_DUR_S` are all ≥0.5s) — the reuse does not
threaten the table below. Script: scratchpad `chunk_seam_check.py`,
not committed.

Full corpus metrics table (same columns as the S-A table above):

```
song                                        plc  hid  rea  rep rsec  maxgap gapL instL   anc   scf   ovl(old>new)
----------------------------------------------------------------------------------------------------------------
Josh Gad - In Summer (From 'Frozen'_Sing-A   31    0    0    0    -    1.8s    0     0    24    18   1.4->0.0  s
'Defying Gravity' - Wicked 20th Anniversar   89    0    0    2    -    1.8s    0     0    43    61   8.4->2.6  s
Jessie J - Domino (Official Video)---UJtB5   67    0    0    1    -    1.4s    0     0    14    61   1.3->0.0  s
'Free' _ Official Lyric Video _ Sony Anima   41    0    0    0    -    1.4s    0     0    28    33   4.6->0.0  s
HUNTR_X 'This Is What It Sounds Like' (Mus   53    0    0   21    -    1.3s    0    11    15    43   5.5->0.5  s
'Popular' - Wicked 20th Anniversary Editio   62    0    0    1    -    1.3s    0     0    44    39   2.9->0.0  s
Ed Sheeran & Rudimental­ - Bloodstream [Of   74    0    0   38    -    1.3s    0    13    23    52   9.8->0.5  s
Wicked - For Good  (2025) 4K - The Girl in   36    0    0    1  yes    1.3s    0     1    23     0  31.1->0.0  s
The Next Ten Minutes Lyrics---0j8kL24ph8U    71    0    1    0    -    1.3s    0     0    63    66  13.4->0.0  s
Ed Sheeran - Best Part Of Me (feat. YEBBA)   38    0    0    0    -    1.3s    0     0    16    33   1.1->0.0  s
Beauty and the Beast (1991) - Belle [UHD]-  110    0    0    0    -    1.3s    0     0    85    94   1.5->0.0  s
NSYNC - Paradise                             65    0    0    2    -    1.2s    0     0    12    51   6.1->1.0  s
The Lion King - Hakuna Matata Music Video    40    0    0    1    -    1.2s    0     0    19    25   0.0->0.0  s
Seasons of Love (HD)---UvyHuse6buY           34    0    0    1    -    1.1s    0     0    13    31   5.8->0.0  s
Mulan _ I'll Make a Man Out of You _ @disn   47    0    0    3    -    1.1s    0     0    22    35   1.7->2.6  s
Beauty and the Beast (1991) - Be Our Guest   77    0    0    2    -    0.9s    0     0    61    53   0.0->0.3  s
Pocahontas - Colors of the Wind (Blu-ray 1   37    0    0    0    -    0.8s    0     0    35    35   0.0->0.0  s
```

prevalence: 3/17 songs show drift (vs the S-A re-run's 7/17); 0
parked-tail lines, 25 mostly-instant lines total. No crashes beyond
the two root-caused CTC RuntimeErrors above.

Output is the raw table, never a verdict — S-1 re-read and S-2 are
read-offs that happen after this entry, per the model-switching table
(Judge = Opus, escalations to Ken).

### 2026-07-19 — GATE S read-off (S-2, S-1 re-read, S-3) — CTC arm selected; S-1 hinges on two Ken rulings; densify fails S-3 on Defying Gravity

**(Fable executing the locked rules at Ken's direction, same convened
window; order S-2 → S-1 → S-3 per S-5's status note — the arm must be
picked before the route is re-read. Rules applied as locked, no
thresholds invented; Opus re-executing the arithmetic will reproduce
it. Both arms ran the identical warp foundation — the S-B entry
confirms per-song warp paths matched the S-A re-run exactly — so S-2
is a pure aligner comparison.)**

**S-2 — CTC (S-B) SELECTED.** Same-instrument head-to-head over the
16 in-scope songs (Girl in the Bubble excluded per the plan text,
`scf=0`; including it changes nothing — S-B is better there too,
3.2 → 0.0). Reading recorded for "mean re-pace": mean over songs of
the per-song re-paced fraction `rep/plc`; the verdict is unchanged
under the alternative total-lines reading (S-A 179/936 = 19.1 % vs
S-B 72/936 = 7.7 %).

- Mean re-pace: S-B 7.1 % vs S-A 17.5 % — **S-B better.**
- Mean worst-overlap: S-B 0.47 s vs S-A 1.61 s — **S-B better.**
- Flag count (drift signature, in-scope): S-B 2 (Bloodstream,
  HUNTR/X) vs S-A 6 (those plus Domino, Popular, Defying Gravity,
  Paradise) — **S-B better.**
- No song > 1.0 s worse on overlap: worst worsenings are Man Out of
  You +0.2 (2.4 → 2.6) and Paradise +0.6 (0.4 → 1.0), both ≤ 1.0 —
  **PASS.**

All three metrics strictly better plus the cap holds → the rule
selects CTC for the non-SRT scaffold path. (The SRT switch, S-C vs
the 5b baseline, has not run and stays open — separate decision,
extra caution per the rule.) Notable inside the comparison: CTC
removed six of the seven Mode-2 align-displacement overlaps outright
(Domino 4.6 → 0.0, Be Our Guest 3.0 → 0.3, Hakuna 2.8 → 0.0, Man Out
of You is the exception), confirming the S-B hypothesis that the
whisper repeat-displacement class dies with the aligner swap.

**S-1 re-read (S-B arm vs Phase 0 joint baseline)** — same
reconciliation as the `658d052` precedent: Phase 0 `overlap(rec>new)`
right value vs scaffold `ovl(old>new)` right value, per song, 16
in-scope songs.

- **Mean worst-overlap strictly lower: PASS.** S-B 0.47 s vs baseline
  0.54 s. The margin is real but thin (0.075 s) and driven by
  Bloodstream 6.7 → 0.5; recorded so no one mistakes it for a rout.
- **Rendered-line coverage no lower: PASS decisively.** Full sheet,
  zero hidden lines on all 16; strictly higher than baseline on 14,
  equal on 2 (Be Our Guest, Colors of the Wind).
- **Flagged-song count no higher: NOT MECHANICALLY DECIDABLE → Ken**
  (precedent followed: baseline `!` = coverage shortfall, 8 in-scope;
  S-B drift signature = 2; different failure modes, no cross-system
  mapping in the rule, and the read-off again declines to invent
  one). Unlike the precedent this conjunct is now load-bearing, so it
  needs Ken's ratification — noting that every defensible mapping
  passes (2 ≤ 8; totals including Girl in the Bubble, 3 ≤ 9; the
  scaffold structurally cannot exhibit the baseline's flag class
  since it renders everything).
- **No song regresses > 1.0 s without a recorded cause Ken accepts:
  FAIL as it stands — exactly two songs, both → Ken.** Defying
  Gravity 0.2 → 2.6 (+2.4): a recorded cause exists (warp diagnostic:
  structurally different recording, both warp models correctly
  rejected, MAD 5.80/10.27; the damage is the densify fallback — i.e.
  precisely the S-3 question below) but Ken has not formally accepted
  it. Man Out of You 0.0 → 2.6 (+2.6): **no recorded cause** — the
  S-A Mode-2 diagnosis (whisper repeat displacement) does not carry,
  because CTC removed the other six Mode-2 overlaps but not this one;
  the "overlap on lines the baseline never rendered" excuse is
  plausibly available (baseline rendered 36/47, S-B renders 47/47)
  but establishing it requires a diagnostic or Ken's eyeball, not
  this read-off.

**Verdict: mechanically not GO as it stands — but this is not the
S-A NO-GO.** Nothing fails on numbers where the rule is
self-contained; the conjunction hinges entirely on two open Ken
items: (1) cause-acceptance for Defying Gravity and Man Out of You,
(2) the flag-count mapping. If S-3 resolves to routing warp-failures
back to the joint matcher, Defying Gravity exits the scaffold route
in production and its regression becomes moot — the two rulings
interlock. Paradise, the original NO-GO's headline regression
(+4.6), is resolved by the offset rescue: S-A amended 0.7 → 0.4,
S-B 0.7 → 1.0, both inside the cap.

**S-3 (warp-failure branch) — densify FAILS the rule on Defying
Gravity's evidence.** Scope call recorded: "warp-failed" = the
MAD-gate reject only, i.e. **Defying Gravity alone** — Girl in the
Bubble never reaches the warp decision (no scaffold exists; densify
is the only possible path, no branch to rule on) and is excluded from
scaffold comparisons plan-wide. (For completeness: including it would
not change the outcome — its overlap ties 0.0 = 0.0 and naive flags
tie 1 = 1 → tie → densify, per the rule's tie-break.) On Defying
Gravity: densify overlap 2.6 s (best arm; 4.3 s on the whisper arm —
robust to arm choice) vs baseline 0.2 s → **not ≤** → the rule says
the warp-failure branch should *not* be densify; the alternative is
Appendix A routing (send warp-rejected songs back to the joint
matcher), consistent with the Mode-1 diagnosis already recorded. Left
open for Ken: the rule ignores the coverage trade (baseline renders
51/89 with its 0.2 s; densify renders 89/89 with 2.6 s) — accepting
joint routing means accepting the 38 dropped lines on such songs.

### 2026-07-19 — GATE S final rulings (Ken) — S-1 GO; S-3 = joint routing; wrapped-header artifact class; S-4 constants recorded

**Ken's rulings, closing everything the read-off left open:**

1. **Cause-acceptance (S-1 per-song cap): both accepted.** Defying
   Gravity's cause "is clear" (correctly-gated structural mismatch;
   the damage is the fallback — the S-3 question). Man Out of You:
   Ken's eyeball found it "actually fine" except a square-bracket
   line at ~2:10 and minor end-of-song wobble.
2. **Flag-count mapping: ratified** — Ken accepted the
   any-defensible-mapping reading (every reading passes, 2 ≤ 8; the
   conjunct's PASS rests on this ruling, not an invented threshold).
3. **S-3: joint-matcher routing for warp-rejected songs.** Ken keeps
   the joint route for DG-like songs — crammed interpolated dialog
   lines are unacceptable for karaoke; hiding unplaceable lines is
   the lesser harm. Direction for the production phase (recorded in
   the build plan): the joint route may adopt CTC as its aligner and
   be refactored to target exactly this warp-reject/version-mismatch
   class.

**⇒ S-1 = GO on the S-B arm** (all four conjuncts now pass). With
S-2 = CTC and S-5 = scaffold-first, GATE S is complete; F2's license
in the build plan is satisfied. F1 still awaits GATE R (2b unrun).
S-C (the SRT switch) never ran; the SRT path keeps whisper by the
rule's default.

**Man Out of You decomposition (Fable verification of Ken's
eyeball, S-B output confirmed by mtime):** the 2.6 s metric and the
2:10 artifact are different things. (a) The measured max overlap is
the *final-chorus* "Be a man" chant under "With all the strength of
a raging fire" (~3:33) — a genuine two-voice overlap on lines the
baseline never rendered (baseline 36/47, chants hidden; scaffold
47/47), the same class Ken ruled genuine at 5b. (b) The 2:10
artifact is sheet dirt: the stored genius-origin `.txt` wraps the
section header across two lines (`line[19]='[SHANG &'`,
`line[20]='SOLDIERS'`); `genius_lyrics.py`'s `_HEADER_RE` /
`_BRACKET_CONTENT_RE` both require the matched bracket pair on one
physical line, so the wrapped header survives as two "lyric" lines —
invisible on the joint route (unmatched → hidden), surfaced by the
render-everything scaffold route, contributing only ~1.0 s pairs
(not the 2.6 s driver). (c) End-of-song wobble = dense
call-and-response chant sequencing, nothing structural.

**Corpus scan of the artifact class:** 5/17 stored genius sheets
carry wrap dirt (15 lines). Rendering header fragments: Man Out of
You (`[SHANG &`/`SOLDIERS`) and Defying Gravity (`[CITIZENS OF OZ
&`/`ELPHABA`, confirmed rendering at 3:28 in its scaffold output).
Stray lone-paren wrap fragments (HUNTR/X, Paradise, Free, DG,
ManOut) do not survive to display text. **Disposition: fix-item,
not an eyeball veto** — production fix recorded in the build plan
(harden `parse_lyric_lines` for unterminated bracket lines;
preferred over refetching, which risks wholesale lyric-version
swaps on five songs).

**S-4 executed:** the S-constants are recorded in the build plan's
Appendix D — S-2 = CTC on the genius scaffold path / whisper stays
on SRT (S-C unrun), S-3 = joint routing (Appendix A precedence 3
resolves to route 4), snap re-enable exception = none (no named
flag class the snap fixes appears in the S-arm tables; the S-B
drift flags are degenerate-anchor artifacts). Appendix E's gate
band stays unfilled (engine off).

### 2026-07-20 — Phase 3 S-C (CTC on the SRT cue-align corpus), Sonnet 5 executor, Windows box

Ken ruled the corpus for this arm is the full 16 SRT-sourced songs (see
the Phase 3 amendment above — the plan's original "13-song" figure never
matched the actual corpus). Run on the Windows dev box (uv, not conda;
first CTC/torchaudio use here — `torch 2.6.0+cu124`/`torchaudio
2.6.0+cu124`, CUDA confirmed, MMS_FA bundle freshly downloaded and
cached). Corpus presence re-verified after the machine move: all 16
songs' bundle/uploader-SRT/vocal-stem/`karaoke/<stem>.cuealign.ass`
(the on-disk 5b whisper baseline) confirmed present and stem-matched.

**Harness hook** (mirrors S-B's committed pattern exactly):
`cue_align_song.run_song` gained a `make_slice_align` parameter
(default: the existing whisper factory, `_make_slice_align`) and a
`--slice-align-module` CLI flag; `cue_align_corpus.py` gained the same
`--slice-align-module PATH` flag (dynamic `importlib` load of a
module's `make_slice_align`, identical to `scaffold_align_corpus.py`'s
loader) plus an output-suffix guard: with a module loaded, the corpus
runner writes `<stem>.cuealign.<module-stem>.ass` instead of
`<stem>.cuealign.ass`, so a probe run never overwrites the whisper
baseline files on disk (unlike the scaffold pair, this corpus script's
default output *is* the file S-C diffs against, so the collision is
real here and wasn't on the scaffold path). Import-smoke clean;
pre-commit (`--files scripts/cue_align_song.py scripts/cue_align_corpus.py`)
clean, no findings.

**Run 1 — whisper baseline refresh** (`cue_align_corpus.py --songs-root
D:/shared/pikaraoke-songs`): **16/16 placed, 0/16 drift**
(`gapL`/`instL` both zero every song) — reproduces the documented 5b
numbers almost exactly, including the five known `MAX_SECTION_DUR_S`
overlap deltas (Mirrors 0.7→0.8, ZAYN 7.8→4.1, Mena/Scott Whole New
World 2.6→2.1, Beauty and the Beast 0.2→0.1, Part of Your World
0.7→2.5 — all within rounding of the recorded figures). Confirms the
port/tree is unchanged on this box, consistent with the ground rules'
reuse license, but this is a fresh same-run table so S-2's comparison
below is apples-to-apples rather than cross-session.

**Run 2 — CTC arm** (`--slice-align-module scripts/sb_ctc_adapter.py`):
**16/16 placed, 0/16 drift**, all 16 songs completed with no
`RuntimeError`s (unlike S-B's scaffold corpus, no "targets length too
long" failures here — SRT sections are shorter/more numerous than the
scaffold path's warped sections). No emission cache existed on this
box (cold — Phase 1b's cache is scratchpad-local, box-specific), so
each song paid a fresh full-song MMS_FA forward pass; still
substantially faster wall-clock than the whisper arm (92 log lines vs.
774 — no per-slice ffmpeg+subprocess round trips).

Per-song comparison (whisper → CTC; `ovl` = worst inter-line overlap,
`rep%` = repaced-from-cue fraction of placed lines):

| song | lines | wh ovl | ctc ovl | Δovl | wh rep% | ctc rep% |
| --- | --- | --- | --- | --- | --- | --- |
| Like I Love You | 84 | 0.0 | 0.1 | +0.1 | 0.0 | 1.2 |
| Let It Go | 47 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| More Than That | 39 | 0.0 | 0.0 | 0.0 | 5.1 | 0.0 |
| Mirrors | 120 | 0.8 | 2.6 | **+1.8** | 6.7 | 16.7 |
| Selfish | 79 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| ZAYN Whole New World | 60 | 4.1 | 0.4 | -3.7 | 3.3 | 1.7 |
| Mena/Scott Whole New World | 54 | 2.1 | 1.8 | -0.3 | 0.0 | 1.9 |
| For Good | 60 | 1.7 | 0.0 | -1.7 | 8.3 | 0.0 |
| Part of Your World | 54 | 2.5 | 0.0 | -2.5 | 0.0 | 0.0 |
| Rock Your Body | 103 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Can You Feel the Love Tonight | 32 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Beauty and the Beast | 56 | 0.1 | 0.0 | -0.1 | 7.1 | 1.8 |
| Happier | 38 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Incomplete | 27 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Speechless | 49 | 0.1 | 0.0 | -0.1 | 4.1 | 0.0 |
| Bye Bye Bye | 75 | 1.3 | 0.0 | -1.3 | 1.3 | 2.7 |

S-2's three mechanical inputs, computed same-run:

- Mean re-pace %: whisper 2.25% vs CTC 1.62% (CTC lower).
- Mean worst-overlap: whisper 0.794s vs CTC 0.306s (CTC lower).
- Flag count (gapL + instL): 0 vs 0 on both arms (tie).
- Per-song cap ("no song > 1.0s worse on overlap"): **Mirrors
  violates it** — CTC's worst overlap is 1.8s worse than whisper's on
  that song (0.8s → 2.6s), the same song whose repace fraction nearly
  triples (6.7% → 16.7%). No other song comes close (next-largest
  same-direction delta is Like I Love You at +0.1s). Note for the
  read-off: Mirrors is the one song the 5b Ken-read already flagged as
  *not* a genuine two-voice overlap (unlike the other four
  `MAX_SECTION_DUR_S`-delta songs) — its whisper-arm 0.7→0.8s bump was
  already anomalous before CTC made it worse.

This is a table, not a verdict — S-2's rule requires *all three*
aggregate metrics to be at least as good AND the per-song cap to hold;
two of three aggregates favor CTC clearly but the cap fails on one
song. Left for Opus's read-off + Ken's eyeball veto (mechanical
read-off role per the model-switching table); Mirrors' `.cuealign.ass`
vs `.cuealign.sb_ctc_adapter.ass` are both on disk at
`D:/shared/pikaraoke-songs/karaoke/` for the eyeball.

### 2026-07-20 — Ken's eyeball (S-C) — CTC weak on overlapping-voice separation

Ken eyeballed Mirrors, ZAYN's Whole New World (End Title), Part of Your
World, and Bye Bye Bye (whisper vs CTC, per the mpv A/B commands
above). Verdict: **CTC has tighter word timing but struggles with
actual overlapping voices that whisper better separates.** This is the
eyeball veto S-2's SRT-arm clause calls for ("the same rule plus Ken's
eyeball veto — extra caution on the proven path") — it both explains
Mirrors' per-song cap failure mechanically (a real overlapping-vocal
passage, not a degenerate-anchor artifact) and reframes the
overlap-improvement songs: an overlap number dropping to 0.0s under
CTC is not unambiguously a fix if CTC's failure mode on overlapping
voices is to under-report rather than mis-time them — worth weighing
against the tighter-timing win rather than reading the aggregate means
at face value.

### 2026-07-20 — GATE S read-off (S-2, SRT arm / S-C) — CTC rejected on the SRT path; whisper retained by default, cap failure and eyeball veto converge

**(Opus executing the locked S-2 rule verbatim against the same-run S-C
table above; no threshold invented. Arithmetic reproduces the
executor's three inputs.)**

**S-2 SRT arm — WHISPER RETAINED (CTC not selected).** The rule
requires *all three* aggregates at least as good AND no song > 1.0 s
worse on overlap. The aggregates favor CTC (re-pace 1.62% vs 2.25%;
worst-overlap 0.306 s vs 0.794 s; flags 0 = 0 tie — "at least as good"
holds on all three). **But the per-song cap FAILS: Mirrors regresses
+1.8 s on worst-overlap (0.8 → 2.6), well past the 1.0 s bar.** One cap
violation is dispositive — the conjunction is not met. Mechanically
the rule falls to its **default clause: whisper, the proven default.**
This is objective from the table, not a judgment call.

**Ken's eyeball veto — corroborates, no daylight.** The SRT arm's rule
explicitly adds Ken's eyeball ("extra caution on the proven path"), and
it was supplied. His finding — CTC has tighter word timing but
struggles to separate genuinely overlapping voices — is not a *second,
independent* objection; it **explains why Mirrors fails the cap.** The
executor already noted Mirrors is the one 5b `MAX_SECTION_DUR_S`-delta
song Ken had flagged as *not* a genuine two-voice overlap and already
anomalous (0.7 → 0.8 pre-CTC); Ken's read reclassifies its CTC blowup
as a real overlapping-vocal passage CTC mishandles, not a
degenerate-anchor artifact. Mechanical failure and eyeball veto point
the same way. Additionally Ken's reframe — a CTC overlap dropping to
0.0 may be *under-reporting* a second voice, not resolving it —
undercuts confidence in the two aggregates that favored CTC, so even
the "2-of-3 clearly better" reading is softer than the numbers alone
suggest. This strengthens, and does not complicate, the whisper
outcome.

**STOP status — none. The rule resolves this without a fresh Ken
decision.** Unlike S-1 (whose conjuncts left load-bearing gray zones
needing ratification), S-2 here is self-contained: cap fail → default
→ whisper, and the pre-registered eyeball input landed on the same
result. No open gray-zone call remains for Ken; the veto he already
gave is the input the rule asked for, and it agrees with the mechanics.
GATE S's SRT arm is closed by execution.

**Appendix D constant (updated wording, supersedes the S-4 "S-C
unrun" line):** *S-2 = CTC on the genius-origin scaffold path; whisper
retained on the SRT cue-align path — S-C ran 2026-07-20 (16-song SRT
corpus), CTC cleared all three aggregates but failed the per-song
overlap cap on Mirrors (+1.8 s), a real overlapping-vocal passage;
Ken's eyeball veto corroborated (CTC weak on overlapping-voice
separation), so the rule defaults to whisper. Edge-snap default on the
SRT path is unaffected (stays as-is; the CTC snap-off default applies
only where CTC is the aligner).*

---

### 2026-09-01 — Ken rulings: 2b arm (iv) runs, emission family eligible; measure-first sequencing; Phase 4 (GATE L) commissioned

Three rulings, no probe run. Recorded because each resolves a case a
locked procedure did not cover (STOP → Ken per Ground rules).

**1. Phase 2b arm (iv) runs.** The arm's precondition read "if GATE
O = O-1", which never happened — but Appendix C's R-5 rule is written
unconditionally and presumes (iv) exists, so honoring the precondition
literally would have left R-5 undefined and defaulted the word route to
the foreign-clock warp by omission rather than by comparison. Ken ruled
the arm runs: the precondition was written when (iv) meant engine
machinery (emission oracle + score gate), whereas the arm needs only a
windowed CTC align — which GATE S selected on evidence (S-2) and
`scripts/sb_ctc_adapter.py` already implements. Phase 2b is a four-arm
probe; R-5 applies as locked.

**2. Appendix C's emission-score family is eligible.** Its clause read
"only if GATE O ≠ O-2"; GATE O came out GRAY — neither O-1 nor a
confirmed O-2 — leaving eligibility undefined. Ken ruled eligible on
the ground that the bullet's own adoption rule self-guards
(discriminative on 2b's cohorts → primary gate, otherwise dropped), so
the pre-registered procedure decides rather than a judgment call
pre-empting it. Phase 1b emissions are cached, so the arm adds no
forward passes.

**3. Measure first, lock once.** The remaining probe program runs to
completion before the build design is consolidated. Licensing fact
recorded: no remaining probe needs production code — only the V-gates
are validation of shipped code. Order and rationale in "Remaining
execution order" above; F2 recorded there as a zero-regret exception.

**Also commissioned: Phase 4 (GATE L)**, the non-Latin alignment-form
probe — phase text above. Motivation (Ken): multi-language support is
in the project's future, and Appendix D's non-Latin carve-out means the
CTC path abstains exactly when that content arrives. The alternative
considered and **rejected** was retiring CTC and running whisper
everywhere: S-1 passed only on the S-B (CTC) arm (0.47 s against the
0.54 s bar), while the whisper arm read 1.61 s and NO-GO, so retiring
CTC would have un-licensed F2 on this plan's own recorded evidence.
Recorded so it is not re-litigated: CTC stays, and the multi-language
question is answered by widening CTC's eligibility, not by removing it.

### 2026-09-03 — Phase 2b (verify-fit, emission family, render arms) — raw tables, no read-off

**(Sonnet 5 executor, Windows dev box. GATE R is Ken's eyeball plus the
judge's execution of Appendix C; nothing below is read off, tallied, or
thresholded here.)**

**Environment:** Windows dev box, `uv run python`, library
`d:/shared/pikaraoke-songs` (not the conda `pik` Linux box the Ground
rules name — its scratchpad had aged out, so the Phase 1b emission
cache was regenerated here). GPU: RTX A2000. The MMS_FA checkpoint was
already in the torch hub cache from the S-C run. Emissions recomputed
for all 16 cohort songs and cached under `get_temp_directory()
/ctc_probe/emissions/` — same compute-once/slice-many contract Phase 1b
wrote them under, so a re-run of 2b or of Phase 1b on this box reuses
them.

**Ken's ruling implemented first — transcribe backfill (2026-09-03).**
Appendix C's negative-control requirement was unrunnable as written:
both controls (Selfish, Incomplete) are srt-origin bundles carrying
`transcribe_words: null`, as are 7 of the 14 PASS songs — precisely the
7 srt-origin songs step 3(iii) names. Every transcribe-family statistic
is computed off `cue_spans_for_lines(normalize_words(transcribe_words),
...)`, so with no transcribe stream on either control there is no
CONTROL value for the general rule to compare against, and "the
assembled gate must fail both controls" could not be executed. Ken
ruled: run the transcribe pass on the 9 missing songs. This reproduces
what Appendix C's own locked stage wiring says the production word
route does ("the word route runs the transcribe pass only"), rather
than amending the procedure — the gap is a fixture artifact of bundles
built when those songs went the cue-align route.

Backfill matched the production de-reverb gate exactly: vocal stem,
`refine=False` (what `_dereverb_gate` uses, and what the 7 tw-present
bundles were produced with), retry on the dry stem only if yield falls
under `dereverb_yield_wpm` (30.0). **No song came near the gate, so no
retry fired and no dereverb stem was used** — the cohort is homogeneous
with the 7 existing bundles on stem, pass and refine setting.

| song | words | yield wpm | stem used |
| --- | --- | --- | --- |
| Rock Your Body | 587 | 118.3 | vocal |
| More Than That | 259 | 66.0 | vocal |
| Let It Go | 275 | 73.2 | vocal |
| Part of Your World | 263 | 83.7 | vocal |
| Like I Love You | 573 | 121.4 | vocal |
| Mirrors | 637 | 76.4 | vocal |
| Can You Feel the Love Tonight | 186 | 63.9 | vocal |
| Selfish (control) | 466 | 117.1 | vocal |
| Incomplete (control) | 204 | 52.2 | vocal |

Written to the scratchpad, never into the library bundles: a probe does
not mutate artifacts a later `regen_alignment_bundles.py` owns. The
`tw` column of the next table records which songs read their transcribe
stream from the bundle and which from this backfill.

**Step 2 — verify-fit prototype + emission family, 14 PASS + 2 CONTROL.**
Pairing is `ytasr.cue_spans_for_lines` over the provider's richsync line
texts as specified; Theil-Sen tempo+offset over `(provider_ts,
mapped_span_start)`; residuals and MAD about the median of those
residuals; `zero_ev` = fraction of provider lines whose warped
`[ts, te]` span contains no transcribe word midpoint. `emis_mean` /
`emis_min` are the emission family: per provider line, its tokens
force-aligned inside its warped span against the cached emission, taking
the mean and min per-word `TokenSpan.score`, reported as the per-song
median of those per-line values.

| song | cohort | tw | lines | pairs | pair_frac | slope | offset_s | MAD | p50 | p90 | max | zero_ev | emis_mean | emis_min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Popular | PASS | bundle | 61 | 53 | 0.869 | 1.0117 | -8.43 | 0.42 | 0.42 | 2.43 | 23.52 | 0.148 | 0.424 | 0.006 |
| Belle | PASS | bundle | 116 | 86 | 0.741 | 1.0013 | -7.93 | 0.14 | 0.14 | 0.58 | 1.88 | 0.121 | 0.306 | 0.010 |
| Best Part of Me | PASS | bundle | 39 | 12 | 0.308 | 1.0179 | -1.39 | 0.60 | 0.63 | 68.48 | 119.01 | 0.103 | 0.341 | 0.002 |
| Colors of the Wind | PASS | bundle | 37 | 36 | 0.973 | 0.9977 | -6.12 | 0.25 | 0.25 | 0.74 | 3.33 | 0.000 | 0.818 | 0.414 |
| Domino | PASS | bundle | 65 | 14 | 0.215 | 1.0159 | -0.56 | 0.24 | 0.24 | 0.57 | 143.51 | 0.200 | 0.080 | 0.001 |
| Rock Your Body | PASS | backfill | 107 | 9 | 0.084 | 1.0266 | 22.75 | 0.70 | 0.70 | 67.61 | 156.45 | 0.140 | 0.055 | 0.002 |
| Free | PASS | bundle | 46 | 33 | 0.717 | 1.0015 | -0.19 | 0.10 | 0.10 | 0.42 | 0.60 | 0.000 | 0.271 | 0.001 |
| More Than That | PASS | backfill | 40 | 15 | 0.375 | 1.0039 | 12.91 | 0.51 | 0.51 | 1.00 | 57.42 | 0.000 | 0.107 | 0.004 |
| Let It Go | PASS | backfill | 40 | 16 | 0.400 | 3.4482 | -20.56 | 5.80 | 6.30 | 50.70 | 68.08 | 0.500 | 0.275 | 0.014 |
| Part of Your World | PASS | backfill | 56 | 51 | 0.911 | 0.9804 | 0.85 | 0.26 | 0.26 | 0.87 | 1.68 | 0.000 | 0.722 | 0.330 |
| Like I Love You | PASS | backfill | 81 | 32 | 0.395 | 1.0001 | -4.19 | 0.65 | 0.66 | 2.16 | 51.87 | 0.062 | 0.074 | 0.001 |
| Mirrors | PASS | backfill | 125 | 21 | 0.168 | 0.9991 | 0.09 | 0.58 | 0.58 | 87.07 | 162.00 | 0.272 | 0.070 | 0.002 |
| Seasons of Love | PASS | bundle | 43 | 12 | 0.279 | 0.9542 | 1.23 | 0.17 | 0.22 | 3.73 | 19.26 | 0.326 | 0.034 | 0.007 |
| Can You Feel the Love Tonight | PASS | backfill | 35 | 30 | 0.857 | 0.8733 | -12.17 | 4.48 | 4.34 | 8.19 | 12.47 | 0.114 | 0.085 | 0.006 |
| Selfish | CONTROL | backfill | 61 | 15 | 0.246 | 1.0072 | 7.11 | 0.08 | 0.08 | 130.35 | 130.46 | 0.016 | 0.195 | 0.001 |
| Incomplete | CONTROL | backfill | 19 | 5 | 0.263 | 0.9915 | -6.46 | 0.32 | 0.32 | 75.20 | 75.20 | 0.000 | 0.295 | 0.013 |

**Step 3 — render arms.** (i) richsync-direct: every provider word
warped by that song's fitted slope/offset, sweeps capped. (iv)
richsync-guided CTC: `sb_ctc_adapter.make_slice_align` re-times each
line inside its padded warped window, falling back to that line's arm-(i)
words where the aligner declines, so the two arms differ only where CTC
actually produced timing. Arms (ii) production and (iii) cue-align were
already on disk and are referenced by the A/B commands, not regenerated.

| song | lines | rendered | CTC declined | (i) first/last | (iv) first/last |
| --- | --- | --- | --- | --- | --- |
| Popular | 61 | 61 | 0 | 0.0 / 200.7 | 1.2 / 203.9 |
| Belle | 116 | 116 | 0 | 16.9 / 291.6 | 16.6 / 292.2 |
| Best Part of Me | 39 | 39 | 0 | 12.5 / 235.1 | 13.8 / 233.2 |
| Colors of the Wind | 37 | 37 | 0 | 0.0 / 185.8 | 0.0 / 185.4 |
| Domino | 65 | 65 | 0 | 4.7 / 199.4 | 5.3 / 199.8 |
| Rock Your Body | 107 | 107 | 0 | 31.9 / 294.0 | 31.2 / 294.7 |
| Free | 46 | 46 | 0 | 12.9 / 180.1 | 12.9 / 180.8 |
| More Than That | 40 | 40 | 0 | 18.4 / 229.6 | 19.3 / 229.7 |
| Let It Go | 40 | 40 | 19 | 0.0 / 433.6 | 13.5 / 433.6 |
| Part of Your World | 56 | 56 | 0 | 7.0 / 165.8 | 7.2 / 167.6 |
| Like I Love You | 81 | 81 | 0 | 1.3 / 267.0 | 0.6 / 267.0 |
| Mirrors | 125 | 125 | 0 | 29.1 / 484.9 | 29.2 / 485.3 |
| Seasons of Love | 43 | 43 | 0 | 6.5 / 190.3 | 5.7 / 188.4 |
| Can You Feel the Love Tonight | 35 | 35 | 0 | 0.0 / 172.8 | 0.0 / 161.7 |

**Artifacts (session scratchpad, never committed).** `p2b/
verify_fit.json` (every row above plus the per-line emission scores and
the raw `(provider_ts, mapped_span_start)` pair list per song),
`p2b/renders.json`, `p2b/renders/<stem>.richsync.ass` and
`<stem>.richsync_ctc.ass` (28 files), `p2b/ab_commands.md` (step 4's
mpv commands, all four arms per song), `tw_backfill/<stem>.json`.
Drivers: `p2b_verify.py`, `p2b_render.py`, `tw_backfill.py`.

**Executor notes — choices a reader would otherwise have to re-derive,
and two observations, none of them read-offs.**

1. *Emission scores are raw, not z-normalized.* Phase 1b z-scored
   per song; that is deliberately not reused here, because Appendix C's
   general rule compares song-level values ACROSS the PASS and CONTROL
   cohorts and per-song normalization would erase exactly the
   between-song differences the rule reads.
2. *`MAX_WORD_DUR_S` disambiguated.* Two constants carry the name.
   `cue_align.MAX_WORD_DUR_S` (1.5) is used, as step 3(i)'s phrase
   "word sweeps capped at" matches that constant's own docstring
   ("a single aligned word's sweep is capped to this");
   `ytasr.MAX_WORD_DUR_S` (2.0) is the end-synthesis constant for a
   foreign ASR stream feeding the DP, not a render sweep cap. Flagged
   in case the judge reads the reference the other way.
3. *Arm (iv) window pad = 0.75 s per side*, the cue-align path's
   established slice pad (`scripts/cue_align_song.py --pad`). The warp
   is a whole-song fit, so a line's true edges sit near, not on, it.
4. *Rock Your Body's 9/107 pairs is a repeat collapse, not a fetch or
   backfill failure.* Its sidecar map_rate is 0.981 and its transcribe
   stream is dense (587 words, 118 wpm); the provider text matches the
   audio from the first line. The paired line ids are 0, 1, 65, 100,
   102–106 — the signature of `spans_from_candidates`' documented
   monotonic greedy on a 107-line sheet that repeats "Dance with me"
   and the title hook throughout: repeated text ties, the strongest
   claimant keeps the occurrence, and the monotone constraint discards
   the rest. The same mechanism GATE P characterized on the joint path.
5. *Let It Go's slope of 3.4482 is a different arrangement, not a fit
   bug.* Its 16 pairs are lines 0–16 contiguous and clean; the richsync
   body covers ts 0.1–131.6 s while the media's transcribe stream runs
   14.3–212.4 s, i.e. the provider timed a shorter recording than the
   one on disk. Theil-Sen then fits a slope no tempo ratio could take,
   and arm (i) stretches the render to 433.6 s — the visible
   consequence, left in rather than patched out.
6. *Pre-existing hook failure, untouched:* `pre-commit --files
   scripts/phase1b_score_oracle.py` fails
   `check-shebang-scripts-are-executable` — the file is mode 100644 in
   the index with a shebang, and so is `sb_ctc_adapter.py`. It predates
   this session's one-line change and is not fixed here.

### 2026-09-03 — GATE R read-off (Fable) — R-4 STOP → Ken; R-1 NO-GO as the route stands

**(Fable's judge round against the Phase 2b artifacts above. Recorded
here verbatim at Ken's instruction. The seven items under "Decisions
that are Ken's" are STOP items, not actions — nothing below is acted
on until he rules.)**

Judge round, read-only: no code changes, no plan edits, no re-runs. Every
number below is computed from the artifacts the Build session saved
(`p2b/verify_fit.json`, `p2b/renders.json`, the 28 `.ass` renders,
`tw_backfill/*.json`), the sidecars and bundles on `d:/shared/pikaraoke-songs`,
and the Results-log entry committed as `ccea7c9` (`--songs-root` as `cf2dca0`).
Judge scripts live beside this file (`appc.py`, `ass_compare2.py`,
`edge_pin.py`, `tw_evidence.py`, `controls_r2.py`).

Process note for the Build session: its last message (17:41 UTC) says
"Phase 2b hasn't run yet". That is a context-loss artifact — the run finished
and was committed at 12:52 UTC; nothing needs re-running.

#### Summary of rulings

| ruling | outcome |
| --- | --- |
| R-4 (Appendix C executed verbatim) | **STOP → Ken.** Zero statistics discriminative (procedure needs ≥ 2); the assembled clamp set cannot fail both controls; one clamp has an unspecified denominator. |
| R-1 (word route GO/NO-GO) | **NO-GO as the route stands** — gate-driven, not mechanism-driven. Reverses if a re-specified Appendix C passes. Appendix A demotion applies meanwhile. |
| R-2 (provider text as-is) | **Confirmed.** |
| R-3 (SRT vs richsync tier order) | **SRT-first stands** (rung 0 above rung 1). Recorded as follow-on scope; no production effect. |
| R-5 ((iv) guided CTC vs (i) warped render) | **No award.** Arm (iv) as built carries a window-edge smear artifact; A/B deferred to a re-run. (i) is the mechanism of record meanwhile; both moot until R-4 resolves. |

#### R-4 — Appendix C, executed verbatim

Cohorts as locked: PASS = the 14 word sidecars (map_rate ≥ 0.5), CONTROL =
Selfish + Incomplete.

##### General threshold rule (W = worst PASS, B = best CONTROL)

| statistic | quality direction | W (song) | B (song) | discriminative |
| --- | --- | --- | --- | --- |
| pair_fraction | higher | 0.084 (Rock Your Body) | 0.263 (Incomplete) | no |
| zero-evidence fraction | lower | 0.500 (Let It Go) | 0.000 (Incomplete) | no |
| emission mean-word (median/line) | higher | 0.034 (Seasons of Love) | 0.295 (Incomplete) | no |
| emission min-word (median/line) | higher | 0.001 (Free) | 0.013 (Incomplete) | no |

Discriminative count = **0**. The procedure's own text: fewer than 2 → STOP →
Ken, "the verify design is not viable as specified". Emission family:
non-discriminative → dropped → transcribe-family-only. (No GATE O band exists
to score against — Appendix E's band is unfilled — so the executor's
median-of-line-scores instantiation was the only available reading, and no
per-line band would rescue it: Incomplete's per-line distribution, p10 0.169
with 0% of lines below 0.05, beats 12 of the 14 PASS songs.)

Sensitivity (not a ruling): dropping the two wrong-recording PASS songs
(Let It Go, Can You Feel the Love Tonight) changes nothing — pair_fraction W
stays 0.084, zero-evidence W becomes 0.326 (Seasons of Love) vs B 0.000,
emission unchanged. The CONTROL side is what breaks the rule, not the PASS
side.

##### Clamps (data-independent or locked formulas)

| clamp | value produced |
| --- | --- |
| n_pairs floor | ≥ 5 (`WARP_MIN_ANCHORS`; code semantics are `>=`, so 5 passes) |
| slope window | PASS spans 0.873–3.448 → needed [0.868, 3.453] → **hard cap binds: [0.90, 1.10]** |
| residual MAD threshold | 1.25 × max PASS MAD (5.80) = 7.25 → **clamped to 2.0 s** |
| per-line outlier | abs(residual) > 3 × 2.0 = **6.0 s** |

Sensitivity (Ken's call, see below): "max MAD over PASS" taken verbatim over
all 14 gives 2.0 s; over only the PASS songs inside the slope window it would
be 1.25 × 0.70 = 0.88 s.

##### Per-song outcome of the clamp set (outlier share shown as of-pairs / of-lines)

| song | cohort | pairs | slope | MAD | outliers | clamp outcome |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Popular | PASS | 53/61 | 1.012 | 0.42 | 3 (6% / 5%) | pass |
| Belle | PASS | 86/116 | 1.001 | 0.14 | 0 | pass |
| Best Part of Me | PASS | 12/39 | 1.018 | 0.60 | 2 (17% / 5%) | pass |
| Colors of the Wind | PASS | 36/37 | 0.998 | 0.25 | 0 | pass |
| Domino | PASS | 14/65 | 1.016 | 0.24 | 1 (7% / 2%) | pass |
| Rock Your Body | PASS | 9/107 | 1.027 | 0.70 | 3 (33% / 3%) | **fail / pass** (denominator) |
| Free | PASS | 33/46 | 1.002 | 0.10 | 0 | pass |
| More Than That | PASS | 15/40 | 1.004 | 0.51 | 1 (7% / 3%) | pass |
| Let It Go | PASS | 16/40 | 3.448 | 5.80 | 8 | **fail** (slope, MAD) |
| Part of Your World | PASS | 51/56 | 0.980 | 0.26 | 0 | pass |
| Like I Love You | PASS | 32/81 | 1.000 | 0.65 | 3 (9% / 4%) | pass |
| Mirrors | PASS | 21/125 | 0.999 | 0.58 | 4 (19% / 3%) | pass |
| Seasons of Love | PASS | 12/43 | 0.954 | 0.17 | 1 (8% / 2%) | pass |
| Can You Feel the Love Tonight | PASS | 30/35 | 0.873 | 4.48 | 10 | **fail** (slope, MAD) |
| Selfish | CONTROL | 15/61 | 1.007 | 0.08 | 2 (13% / 3%) | **pass** (every reading) |
| Incomplete | CONTROL | 5/19 | 0.992 | 0.32 | 2 (40% / 11%) | **fail / pass** (denominator) |

##### Negative-control requirement: cannot be met

Selfish passes the clamp set under every reading, so "the assembled gate must
fail both controls" fails regardless of how the open questions resolve. This
is the second, independent STOP ground. The third: the outlier rule's "> 20%
outlier lines" has no stated denominator; paired lines vs provider lines
flips Incomplete (40% vs 11%) and Rock Your Body (33% vs 3%). Uncovered case.

##### Diagnosis (judge analysis, for Ken — not part of the procedure)

1. **The controls are not wrong-song fixtures.** Selfish's sidecar is
   "Selfish — Justin Timberlake": the media's own song, correctly timed —
   10 of 15 pairs sit within 0.13 s (13 within 2.2 s) at slope 1.007 /
   offset +7.1 s (the video intro); the two 130 s outliers are the greedy
   pairing jumping to a later chorus repeat (provider 53.0/59.0 s →
   191/197 s). Its map_rate of 0.38 is a segmentation/orthography artifact
   against the SRT-derived sheet (61 provider lines vs 79 SRT lines,
   "lettin'" vs "letting"). The gate passing it is correct behavior.
   Incomplete's sidecar is a genuine bad one — "Incomplete (Backstreet Boys
   Karaoke Tribute) — Karaoke Mix", 252 s vs a 234.5 s media, 19
   fragmentary lines with spans up to 54 s (10.1–63.9 s) — but those giant
   spans defeat the zero-evidence statistic (0.000) and its emission scores
   beat most PASS songs. Both controls were selected by text map_rate, which
   measures neither song identity nor timing.
2. **The PASS cohort is not timing-clean either.** Five of 14 sidecars time
   a different recording or edit, confirmed against the transcribe stream
   (sung time → warp time; production in brackets):
   - Let It Go — "Let It Go (Armin van Buuren Radio Edit)", 153 s track vs
     225 s media; arm (i) stretches to 433 s. Caught (slope 3.45).
   - Can You Feel the Love Tonight — "Teatro" cover, 225 s vs 175 s media.
     Caught (slope 0.87).
   - Domino — "Domino - UK Radio Edit": the fit anchors on lines 0–16 only.
     "Every second is a highlight" sung @69.4 s → warp 75.2 [68.5];
     "You strum me like a guitar" @100.9 → 86.0 [99.2]; "My heart beats out
     of time" @93.5 → 81.3 [92.9]. 20 of 31 matchable lines > 5 s off.
     **Passes under every reading — confirmed false pass.**
   - Popular — "Popular (Live)", Kristin Chenoweth: tail lines 56–60 are
     unpaired and land 20 s late ("Your disinterest / I know clandestinely"
     @154.6/157.2 → 174.1/175.4 [154.3/156.7]). **Passes**; the outlier rule
     cannot see unpaired lines.
   - Rock Your Body — warp offset +22.75 s is wrong from line 1 ("Don't be
     so quick to walk away" sung @9–10 s → warp 32.7 [SRT 9.5]); 73 of 101
     matchable lines > 5 s off. The 9 pairs (ids 0, 1, 65, 100, 102–106)
     are the repeat-collapse the executor flagged, here producing a
     self-consistent wrong fit. Fails only under the of-pairs reading.
3. **What the clamps can and cannot see.** Slope + MAD catch tempo/arrangement
   mismatches (2 of 2). A single global slope/offset cannot express a cut or
   reordered section, so edit mismatches on the same recording (Domino,
   Popular's tail) pass by construction; the outlier rule only reaches
   paired lines, and the greedy monotone pairing discards exactly the lines
   that would expose the mismatch.
4. **The emission family cannot rescue this at song level**: raw scores are
   dominated by per-song acoustics (Colors of the Wind median 0.82 vs
   Seasons of Love 0.03), and z-normalizing per song erases the between-song
   axis the general rule reads (the executor's note 1 is right).

##### Constants the procedure produced (for the Appendix C record; no gate assembled)

n_pairs ≥ 5; slope in [0.90, 1.10] (hard cap binding); MAD ≤ 2.0 s (clamp
binding); outlier > 6.0 s; pair_fraction, zero-evidence fraction and both
emission statistics recorded **non-discriminative**; discriminative count 0;
negative-control requirement **unmet** (Selfish passes).

#### R-1 — richsync-direct render quality: NO-GO as the route stands

The mechanism is GO-grade where the sidecar times the right recording: the
warped render agrees with independent references (production joint-matcher
or SRT cue-align) to a median of 0.1–0.5 s with p90 ≤ 1 s on Belle (72
matched lines, med 0.15 / p90 0.39), Free (0.09 / 0.44), Colors of the Wind
(0.31 / 0.74), Part of Your World (0.25 / 0.90), and within ~1.3–2.1 s p90 on
Mirrors (0.34 / 1.29) and More Than That (0.44 / 2.09); every render is
well-formed (0 non-monotone lines, 0 zero-duration words across 28 files).
But the word route exists only behind a verify gate, R-4 could not assemble
one, and 5 of 14 sidecars would render wrong without it (Let It Go's 433 s
stretch on a 225 s video; Domino, Popular's tail and Rock Your Body sections
6–23 s off). Per Appendix A the word sidecars' line starts join the
line-source pool and `ts`/`te` still improve scaffold ends. This NO-GO is
about the gate and reverses if a re-specified Appendix C passes.

Ken's eyeball has not happened; targets if it does: Popular 154–195 s,
Best Part of Me 205–232 s, Seasons of Love's spoken intro (0–40 s; the
richsync includes the film dialogue "New Years Eve, 1991…", production has
no lines before 42.5 s), Part of Your World (a Robin Huston cover that
happens to fit at slope 0.98 — the word sweeps are another singer's).

#### R-2 — provider text as-is: confirmed

Across the 14 sidecars: 0 ALL-CAPS lines; parenthetical backing vocals on
8 songs (Mirrors 17 lines, Like I Love You 10, Rock Your Body 6, More Than
That 5, others ≤ 2) rendering as written, e.g. "It's like you're my mirror
(oh-oh)"; 1 speaker label ("Belle: Little town"); 1 unbalanced paren
("That's nice. Marie! The baguettes! Hurry up!)"); dialogue lines carried
from film versions (Can You Feel the Love Tonight "What?" / "Who?" / "Oh",
Seasons of Love's spoken intro); hyphen-split melisma tokens (Mirrors 28,
Belle 9, Popular 3: "popu- ler... lar...", "pop- u- lar..."); "Ev'ry"-style
contractions; numerals ("525,600 minutes") as text. Nothing here reverses
the decision. Two cosmetic follow-ons Ken may or may not want: strip a
leading "Name:" label; the hyphen-split tokens are faithful to the singing
and probably right as-is.

#### R-3 — SRT vs richsync tier order: SRT-first stands

On the 7 both-source songs, the warped richsync against the SRT-based output
(cue-align arm iii; production ii is also SRT-routed): three richsync sidecars
time a different recording or edit (Rock Your Body median 24.4 s off, 79% of
lines > 1 s; Let It Go 106.9 s; Can You Feel the Love Tonight 4.3 s, 80%),
four agree within a 0.4–0.7 s median (Part of Your World 0.39, More Than
That 0.58, Mirrors 0.35, Like I Love You 0.74) with 15–33% of lines > 1 s
apart. SRT is authored for the exact video; the richsync's recording identity
is unverifiable at fetch time (Part of Your World's cover fits by luck of
tempo). Rung 0 stays above rung 1. Recorded as follow-on scope per the
search-scope decision; richsync could at most augment word timing inside SRT
cues, and S-C already retired CTC on that path, so there is no production
effect to schedule.

#### R-5 — (iv) richsync-guided CTC vs (i) warped render: no award

Line coverage ties by construction ((iv) falls back to (i) where CTC
declines; 19/40 on Let It Go, 0 elsewhere). "Visibly worse on any song" is
Ken's A/B finding, but the arm as built has a construction artifact the
eyeball would be measuring instead of CTC:

| song | (iv) last word ends at padded window edge | first word starts at window edge | line overlaps (i) → (iv) |
| --- | ---: | ---: | --- |
| Mirrors | 61% | 15% | 0 → 54 |
| Rock Your Body | 55% | 28% | 3 → 69 |
| Free | 54% | 17% | 1 → 15 |
| Like I Love You | 51% | 25% | 11 → 30 |
| More Than That | 50% | 5% | 2 → 6 |
| Domino | 37% | 23% | 13 → 42 |
| Seasons of Love | 26% | 23% | 15 → 20 |
| Belle | 25% | 12% | 10 → 56 |
| Can You Feel the Love Tonight | 23% | 9% | 14 → 18 |
| Best Part of Me | 13% | 23% | 0 → 5 |
| Popular | 11% | 11% | 11 → 23 |
| Part of Your World / Colors of the Wind / Let It Go | ≤ 11% | ≤ 5% | small |

Mechanism: `sb_ctc_adapter.slice_align` takes each word's end from its last
token span; when the ±0.75 s pad (plus warp error) puts neighbouring singing
inside the window, forced alignment stretches the first/last token across it
to the window boundary, capped only by `MAX_WORD_DUR_S` = 1.5 s. In the render
that is a last-word sweep running ≥ 0.75 s into the next line — the (i) vs
(iv) p90 first-word delta sits at exactly 0.75 s on 7 songs. The pinned
fractions are lower bounds (the 1.5 s cap hides longer smears). Where CTC is
not pinned it is at least as good as the warp (Colors of the Wind (iv) vs
production median 0.12 s against (i)'s 0.31; Best Part of Me 0.45 vs 1.03).
Ruling: (i) is the mechanism of record; (iv) re-runs after the arm is fixed
(trim sweeps at the next word's onset or the line's warped `te`, and/or a
tighter pad) before Ken's A/B is spent on it. Both arms are moot until R-4
and R-1 resolve.

#### Decisions that are Ken's (STOP items)

1. **Controls.** Re-specify as true wrong-song fixtures — cross-pairing a
   sidecar with another song's media is guaranteed wrong and costs nothing —
   or accept that Selfish is a right-song sidecar and drop it as a control.
2. **Cohort labels.** Keep text-match labels (the rule then compares the
   wrong populations) or relabel by timing truth (transcribe/SRT
   corroboration) before re-running the general rule.
3. **Outlier-rule denominator**: paired lines or provider lines.
4. **MAD-threshold population**: all PASS verbatim (2.0 s clamp) or the
   slope-window survivors (0.88 s).
5. **Edit/structure-mismatch class** (Domino, Popular's tail): outside the
   global-warp design; needs its own check (sectional fit, or pairing
   coverage per section) if the word route is to survive — a design change,
   not a constant.
6. **Arm (iv) rebuild** before the R-5 A/B.
7. Whether the R-1 eyeball proceeds now on the right-recording songs or
   waits for the re-spec.

### 2026-09-03 — R-1 eyeball (Ken), 10 songs on arm (i) — observations, R-1 not ruled

**(Ken's eyeball, executed against the arm-(i) renders copied to
`pikaraoke-songs/karaoke/<stem>.richsync.ass`. Observations are his;
the two analyses at the end are the executor's and are flagged as
untested hypotheses. R-1 is not ruled here.)**

**Method.** Clips, not whole songs — 40-60 s per song, chosen by the
executor. Round 1 took six songs; round 2 added five after the executor
found its own round-1 selection **asymmetric**: the three
expected-bad songs were pointed at their known-bad regions while the
expected-good songs got arbitrary windows, so any separation was partly
constructed. Round 2 re-checked two good songs at their *worst*
measured residual and added three songs where candidate thresholds
bind. The bias and its correction are recorded because they bound how
much the good/bad split can be trusted.

| song | clip | Ken's observation | class |
| --- | --- | --- | --- |
| Colors of the Wind | 0:40, then 0:00 | "perfect as expected" — including the opening, which carries the song's worst residual (3.33 s @ 16.9 s) | clean |
| Belle | 1:00, then 3:47 | "fine" with minor ripples in sub-word syllable timing and lead ins/outs; the late section "did great, especially since it's multi-voice rapid fire" | clean |
| Free | 0:12 | "fine", same minor ripples. Lyric video — the on-screen text is an independent reference | clean |
| Part of Your World | 0:07 | "fine, more or less in line with Belle and Free". Saw 3 of its 5 worst residuals (to 1.68 s) and did not react to them | clean |
| More Than That | 1:50 | Lines "come in on time but seem rushed, like they fell back to rescue fill timing"; "only slightly, but noticeably rushed, but still singable" | singable |
| Like I Love You | 1:37 | "didn't notice any lines being that far adrift at all" — despite three residuals near 50 s in the watched window — "just a few that seemed rushed like More Than That" | singable |
| Best Part of Me | 3:20 | Timings correct in shape, "just uniformly late" | bad |
| Popular | 2:30 | "And though you protest" is "a slow crawl and mistimes the rest of the lyrics"; the text itself "more or less a match for what's sung"; many multi-voice ad-libs from that section on | bad |
| Domino | 1:05 | "falls out of sync from 1:09", as the coverage diagnosis predicted | bad |
| Seasons of Love | 0:00 | Spoken film intro renders as karaoke text, and the song is "completely mistimed there on" | bad |

Six of ten usable (four clean, two singable), four not. Every failure
is attributable to the sidecar or the fit — wrong recording, edit
mismatch, or a coverage hole — and none to the render mechanism.

**Executor analysis 1 — the residual family appears to measure the
pairing, not the render.** Untested hypothesis, recorded because it
bears on R-4's re-specification. Three songs carry large residuals that
Ken did not perceive at all: Colors of the Wind 3.33 s (called
perfect), Belle 1.88 s (called great), Like I Love You three near 50 s
(no line noticed adrift). Residuals are computed against
`cue_spans_for_lines`' pairing of provider lines to transcribe words;
when that greedy monotone pairing latches onto the wrong repeat, a
correct render yields a large residual. If this holds, it indicts
`residual_mad`, `res_p50/p90` and the per-line outlier rule together —
three of the four statistics Appendix C tests — and Fable's
"0 discriminative" has a deeper cause than threshold placement. It
would also make decisions 3 (outlier denominator) and 4 (MAD
population) moot rather than pending: a discredited statistic is
dropped, not tuned.

A candidate `res_p90` threshold the executor floated earlier is
**withdrawn** on these labels: p90 would reject Like I Love You (2.16,
singable) and pass Domino (0.57, broken).

**Executor analysis 2 — zero-evidence fraction nearly separates the
labels.** The one Appendix C statistic not derived from residuals.
Usable songs: 0.000, 0.000, 0.000, 0.000, 0.062, 0.121. Bad songs:
0.103, 0.148, 0.200, 0.326. One overlapping pair (Belle 0.121 vs Best
Part of Me 0.103), 0.018 apart. It asks whether the audio contains
singing where a line claims to be — a property of the render. Fable
recorded it non-discriminative only because Incomplete scores 0.000:
that control's 54 s fragmentary spans are wide enough to always contain
a transcribe word. The statistic was defeated by a broken control, not
by being uninformative, which points at decisions 1 and 2 rather than
at a new statistic. **Caveat, stated plainly: n = 10 labels, and the
separation was read off after the labels were known.** This is a
hypothesis for a relabelled cohort, not a gate.

**Blind spot recorded.** "Correct line starts, slightly rushed word
sweeps" is a **sub-line** defect. Every verify-fit statistic compares a
line's start against a mapped span start; word-level sweep pacing is
invisible to all of them. Ken judged it singable, so it may never gate
anything, but no number in the 2b table can see it.

**Consequences for the seven STOP items.** 7 (whether the eyeball
proceeds) is discharged by this entry. 5 (edit/structure-mismatch
class) is corroborated — Domino's failure was predicted from coverage
and confirmed by eye. 3 and 4 may dissolve rather than resolve if
analysis 1 holds. 1, 2 and 6 stand as Fable recorded them. R-1 itself
remains Ken's to rule.

### 2026-09-03 — R-1 ruled (Ken) — NO-GO as the route stands; mechanism GO on evidence

**(Ken's ruling, taken on the eyeball entry above plus Fable's GATE R
read-off. This closes STOP item 7 and R-1; R-4 remains open.)**

**R-1 = NO-GO as the route stands.** The ruling is *gate-driven, not
mechanism-driven*, and the two halves are recorded separately because
they have different futures:

- **The mechanism is GO on evidence.** Warping provider word timings
  and rendering them produces usable karaoke on 6 of the 10 songs
  eyeballed (4 clean, 2 singable), and Colors of the Wind is better
  than the production output. All four failures trace to the sidecar
  or the fit — a wrong recording, an edit mismatch, or a coverage hole
  — and none to warping-and-rendering itself. This is the first direct
  evidence for the word route's quality; every prior statement about it
  was inference from statistics.
- **The route cannot ship.** The word route exists only behind a verify
  gate, Appendix C could not assemble one (R-4, STOP → Ken), and 4 of
  14 sidecars would render wrong without it. Shipping the mechanism
  without a gate is not on the table.

**Consequence (Appendix A, already specified).** The word sidecars
demote to the line-source pool and their `ts`/`te` continue to improve
scaffold ends, so the six usable songs keep contributing everything
except word-level sweeps. The demotion is the existing routing
behaviour, not new machinery — no code changes on this ruling.

**Reversal condition.** R-1 reverses on a re-specified Appendix C that
passes. It is not a judgment that richsync word timing is unusable; it
is a judgment that we cannot yet tell good sidecars from bad ones
automatically. The measurement that would reverse it is commissioned
below.

**Commissioned with this ruling — the R-4 re-specification measurements
(offline, no GPU, data already on disk).** Ken's call, measure-first:

- **M1 — relabel all 16 songs by timing truth** from the transcribe
  stream, replacing the text-map_rate labels. Ken's 10 eyeball labels
  are the validation set; a labeller that reproduces them can be
  trusted on the remaining 6 and on future songs. Produces the evidence
  for STOP item 2.
- **M2 — build real negative controls** by cross-pairing sidecars
  against other songs' media. Guaranteed wrong-song, no fetches, and
  many rather than 2 — which also retires the n=2 fragility behind
  every threshold. Produces the evidence for STOP item 1.
- **M3 — re-run Appendix C's general rule** on M1's labels with M2's
  controls. Tests whether zero-evidence fraction becomes
  discriminative, and tests the eyeball entry's analysis 1 by checking
  whether the residual statistics stay non-discriminative once the
  labels are corrected.
- **M4 — per-section pairing-coverage detector** for the
  edit/structure-mismatch class (STOP item 5). Domino and Popular are
  the known positives, the four clean songs the known negatives.
- **M5 (small) — check whether the "slightly rushed" sweeps are
  `cue_align.MAX_WORD_DUR_S` (1.5 s) truncating sustained notes.** If
  so it is a one-constant fix rather than a design problem.

**Held, not commissioned:** STOP items 3 (outlier denominator) and 4
(MAD-threshold population). If the eyeball entry's analysis 1 survives
M3, both dissolve rather than resolve — a statistic that reads the
wrong thing is dropped, not tuned. STOP item 6 (arm (iv) rebuild) stays
deferred behind R-4.

## Appendices A–D — moved to `plans/ctc-sync-engine.md`

Moved 2026-07-18 (same day, with the evidence/build split), same
letters, content carried verbatim plus the GATE C additions: A (router
contract), B (timing-fetch module design), C (word-route verification
skeleton — locks at GATE R), D (scaffold/aligner integration skeleton —
locks at GATE S). A new Appendix E (engine core skeleton — locks at
GATEs O+S) exists only there. "Appendix X" references in this file
resolve to that file.
