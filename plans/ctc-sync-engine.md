Model: Claude Fable 5

# CTC sync engine — production build plan

## Role of this file

The build half of the 2026-07-18 evidence/build split: successor to
`plans/timing-source-pillars.md`'s production phases. **That file owns
probes, comparisons, and GATE rulings; this file owns all production
implementation.** Every build phase below names the evidence-plan GATE
that licenses it; no build phase starts before its license exists
(exception: E0, architecture-neutral). This plan **replaces the
existing non-SRT matcher stack via a parallel path and a gated
cutover** — it does not modify the existing stack in place. The
existing pipeline keeps producing output untouched until the cutover
GATE flips routing.

Two mutually exclusive build branches, selected by the evidence plan's
S-5 ruling:

- **Engine branch (E1–E4):** one CTC sync engine under every non-SRT
  route — emission oracle + score gate + guided windowed CTC align,
  with external timing (richsync / line LRC) as trust-ranked structure
  priors and anchors-densify windows when no external timing exists.
  Requires GATE O = O-1 (or O-1′, the evidence plan's rescue read-off
  — counts as O-1 everywhere in this plan) and S-5 = engine.
- **Fallback branch (F1–F2):** the scaffold-first tiers exactly as
  originally planned (warped scaffold → `align_song`; verified-richsync
  word route). Runs when O-2 (confirmed at GATE O′) or S-5 =
  scaffold-first.

Either branch ends at E5 (closeout). E0 runs regardless.

## Architecture (engine branch)

- **Emission oracle:** MMS_FA emission computed once per song on the
  vocal stem (chunked, cached), then reused everywhere — full-song
  align, windowed aligns as trellis restrictions (slice the emission,
  never re-slice audio), and per-line/per-word scoring of any
  hypothesized timing (richsync claims, scaffold spans, final output).
- **Score gate:** per-line scores (statistic + band from GATE O, or
  GATE O′ if the gate statistic was rescued) separate
  trusted lines from desynced/phantom ones. Trusted lines ship as
  aligned; failing sections enter the repair loop.
- **Structure priors, trust-ranked:** uploader SRT (not this plan's
  target — see carve-out) > richsync word timing > provider/LRCLIB
  line timing > sheet + audio anchors (YTASR ∪ transcribe, densified).
  Priors supply text, line structure, and window locations — never
  output timing; CTC supplies the on-clock timing.
- **Repair loop:** failing sections re-align in scaffold-derived
  windows (Theil-Sen fit over trusted lines warps the prior onto the
  audio clock); emission-sliced windows make multiple candidate
  windows per bad line affordable; best-scoring result wins, a line
  nothing places falls back to warped-prior pacing (honest fill,
  provenance-tagged).
- **Whisper's remaining role:** transcribe only — independent evidence
  for anchors, verification cross-checks, and the no-lyrics
  transcription mode (untouched). The whisper *align* passes have no
  role in the engine branch.
- **No tier 3:** a song with no external timing still runs the engine
  (sheet text + anchor windows) — that is literally what the Phase 1
  eyeball did to all 33 songs. The joint matcher becomes a deletion
  target at cutover, not a route.

**Carve-out (binding):** the SRT cue-align path is not a replacement
target. It is proven (13/13 clean) and already windowed; at most its
`slice_align` swaps to CTC on a clear S-C win (S-2 ruling). SRT-origin
songs must behave byte-identically through E3 (regression-tested), any
aligner swap being its own commit after.

## Decisions carried forward (Ken, 2026-07-18 — do not re-litigate)

The four rulings recorded in the evidence plan (SRT-vs-richsync decided
at GATE R; provider text renders on the word route; NetEase wired as
line-only fallback; derived-query changes only — no UI changes, no
timing fetch without a Genius pick), plus GATE C's verdicts (C-1 YES,
C-2 YES-for-the-aligner, C-3 constraints: Latin-only, numeral
expansion). The build split itself: replacement path + gated cutover,
never in-place modification.

## Reuse inventory (the engine takes, not rebuilds)

- `token_align.match_words_to_tokens` (twin arbitration DP) and
  `_normalize_token`.
- `cue_align`: `segment_by_gaps` + section machinery, `MAX_WORD_DUR_S`
  discipline, and the Phase 0 ports (`warp_scaffold_cues`,
  `densify_cue_spans`, `merge_cue_spans`, `_theil_sen`).
- `ytasr.cue_spans_for_lines` + `normalize_words` (Phase 0),
  `ytasr.parse_json3`/`is_usable`.
- `lrclib`: `map_lines_to_cues`, `select_candidate`, `clean_key`,
  `parse_lrc_lines`, `ensure_lrc`.
- `generate_ass` / SRT generator, `alignment_capture`, the
  harness ecosystem, `WhisperWorker` transcribe, `StemWorker`.
- The Phase 1 CTC recipe (chunking, normalization, frame→seconds).

## Deletion targets (named now, executed only at E4 after the parallel A/B)

Each deletion is its own commit, tests deleted with the code
(CLAUDE.md), only after GATE X confirms the replacement on the full
corpus:

- `windowed_realign.py` (span repair for the joint DP).
- `evidence_veto.py` (superseded by the score gate).
- `joint_match.py`'s DP as the lyric-song router (retained only if the
  fallback branch shipped, or as the S-3-chosen warp-failure fallback).
- Onset/edge snap on CTC-timed routes (Appendix D decision; the
  modules stay while any whisper-timed route remains).
- The de-reverb retry (Appendix D decision — C-2 settled the aligner;
  the transcribe-side benefit is the open half).
- `lrclib_fill` E1 gated fill (engine repair covers unplaced lines by
  construction; confirm no route still needs it).

## Licensing table

| Build phase | License (evidence-plan GATE) |
| --- | --- |
| E0 fetch pillar | none — architecture-neutral; sidecar format = Appendix B |
| E1 engine core | GATE O = O-1 (or O-1′) **and** GATE S ruling S-5 = engine |
| E2 engine routes | E1 + GATE R (R-1/R-5 for the word route) |
| E3 parallel corpus A/B | E2 complete |
| E4 cutover + deletions | GATE X (defined in E3) |
| E5 closeout | E4 (or F2 on the fallback branch) |
| F1 word route (fallback) | GATE R = GO and S-5 = scaffold-first |
| F2 scaffold route (fallback) | GATE S S-1 = GO and S-5 = scaffold-first |

## Ground rules

The evidence plan's Ground rules apply verbatim (branch, env,
commit/test/review discipline, politeness, GATE discipline). New
production modules (fork rule): `pikaraoke/lib/timing_fetch.py` (E0),
`pikaraoke/lib/ctc_emission.py` + `pikaraoke/lib/ctc_align.py` (E1),
`pikaraoke/lib/timing_verify.py` (F1, fallback branch only).

**History strategy (Ken, 2026-07-18):** working branches fork from the
`musix_ctc` tip — mandatory, not stylistic: `dev`/`master` predate
`cue_align.py`, `ytasr.py`, snap/veto/fill and the harnesses, the
corpus + baselines are measured against tip behavior, E3's parallel
A/B needs old stack + engine in one tree, and the fallback branch *is*
the current stack. The clean production history Ken wants is achieved
**at landing, not at forking**: `master` contains none of the 67
matcher-era commits, so the ship lands on it (or a `production` branch
cut from it) as consolidated squash commits — the matcher era as one
or two commits, then one per build-plan phase. Never re-fork
production work from `dev`.

**Design-role succession (Fable unavailable from 2026-07-19):** all
design content in this file is now either locked outright or expressed
as a pre-registered decision procedure (Appendices C/D/E, GATE X, the
E4 order). "Locking" an appendix at a GATE now means *executing its
procedure verbatim and recording the resulting constants* — Opus does
this as the judge role. No model, on any tier, invents a threshold or
extends a procedure: a case a procedure does not cover is a STOP →
Ken. Sonnet 5 implements; Opus judges and records; escalations that
previously said "to Fable" now go to Ken.

## Phase E0 — production pillar: timing fetch in `lyrics_fetch`

Independent of all GATEs (the artifacts are inert until a router reads
them). Execute per **Appendix B (locked)**:

1. New module `pikaraoke/lib/timing_fetch.py`: reference-pick +
   title-only fallback + NetEase fallback, lifted from
   `scripts/musixmatch_coverage_improve.py` (the script then imports the
   lib — single source of truth, script stays as the batch/regen tool).
   Politeness constants, single-retry 401 backoff, never raises.
2. Sidecar persistence + reuse-on-disk (`lyrics/<stem>.timing.json`),
   exactly the evidence plan's Phase 2a format (= Appendix B).
3. `LyricsFetchStage` Branch a (Genius) wiring per Appendix B's locked
   call site; stash `ctx.artifacts["synced_timing"]` per Appendix A's
   schema. srt/raw/none-origin songs: untouched (scope decision).
4. Dependency: `syncedlyrics` moves from the `dev` extra to a runtime
   dependency (`pyproject.toml` + `requirements.txt`).
5. Tests: mocked network — selection key ordering, title-only trigger,
   NetEase trigger, 401-backoff path, sidecar roundtrip,
   corrupt-sidecar refetch.

Commit: `feat(pipeline): synced-timing fetch pillar (Musixmatch +
NetEase)`.

## Phase E1 — engine core (license: O-1 + S-5 = engine)

Execute per **Appendix E (locked at GATE S)**. Shape (pre-registered;
detail locks with measured constants):

1. `pikaraoke/lib/ctc_emission.py`: compute-once emission per song
   (chunked with overlap per Appendix E), cache contract, frame↔seconds
   mapping, and `score_spans(...)` — per-word/per-line emission scores
   for any hypothesized timing, z-normalized per song.
2. `pikaraoke/lib/ctc_align.py`: tokenizer/normalization (display token
   kept beside alignment form; numeral expansion; OOV policy incl. the
   non-Latin fallback), full-song align, and windowed align as a
   trellis restriction over the cached emission — the engine's
   `slice_align`-shaped callable.
3. The guided driver (lives in `ctc_align.py` unless the Appendix E
   lock splits it out): prior → windows → align → score gate → repair
   loop → line objects (provenance-tagged per source: aligned /
   repaired / prior-paced). Pure over injected emission + priors, like
   `cue_align.align_song`, so tests drive it with stubs.
4. Dependency + model lifecycle: declare `torchaudio` as a runtime
   dependency if it is not already (`pyproject.toml` +
   `requirements.txt` — the probe relied on it being installed in
   `pik`, which is not a declaration); MMS_FA weights download on
   first `bundle.get_model()`, so weight cache location and offline
   behavior follow Appendix E (engine unavailable degrades per
   Appendix A's failure containment, never fails the song).

## Phase E2 — engine routes (license: E1 + GATE R)

1. Word route: richsync prior, mechanism per **R-5** (guided CTC vs
   warped render — if warped wins, the verify design comes from
   Appendix C as in F1). Provider text renders (Ken's ruling), R-2
   permitting.
2. Line route: provider/LRCLIB line timing as prior (best source by the
   Appendix B selection key).
3. No-timing route: sheet + anchors-densify windows.
4. Routing per **Appendix A**; SRT-origin untouched (regression test);
   post-passes per Appendix A as amended by the Appendix D snap
   decision. Capture: route taken + gate/score stats into the debug
   bundle (`alignment_capture`) for offline replay of routing.

**GATE V** — live validation: regenerate the probe songs end-to-end;
diff vs the corresponding evidence-plan arm outputs (S-B2 / 2b arm iv);
Ken spot-eyeballs, including the 4 NetEase-sourced songs (first
production NetEase exposure).

## Phase E3 — parallel corpus A/B

Full 33-song regeneration with the engine writing alongside production
output (distinct filenames, never clobbering). Comparison table
columns (pre-registered): song | origin | route taken | gated/repaired/
fill fractions | flags (engine) | flags (production) | eyeball verdict.
**GATE X criteria (pre-registered):** (a) parity — no song where the
engine output carries a flag class the production output lacks;
(b) the version-mismatch songs (Bloodstream, Popular, Defying Gravity
class) show fewer desync/pileup flags than production; (c) zero
unexplained regressions — any engine-worse song needs a recorded cause
and Ken's explicit acceptance; (d) Ken's eyeball is final on any song
the numbers call close.

## Phase E4 — cutover + deletions (license: GATE X)

1. Flip default routing to the engine for non-SRT songs (one commit).
2. Execute the deletion inventory, one commit each, in this locked
   order, each with its test updates, a grep gate proving no remaining
   importer, and a corpus spot-check:
   (1) `evidence_veto.py` (leaf); (2) `windowed_realign.py`;
   (3) `lrclib_fill` E1 fill, after confirming no route consumes
   fills; (4) `joint_match` DP as lyric-song router — only if the
   fallback branch never shipped AND S-3 did not choose the joint
   matcher as the warp-failure branch; (5) snap modules — only if no
   whisper-timed route remains (including the SRT path per S-2);
   (6) de-reverb retry — only after a recorded review of what still
   consumes transcribe quality. A deletion whose condition fails is
   skipped and recorded, not forced.
3. SRT `slice_align` swap here iff S-2 ruled for it (own commit).

## Phase E5 — closeout (GATE F)

1. Final full-corpus regeneration at final HEAD; summary table (song |
   origin | route | stats | flags).
2. Docs: `scripts/README.md`, both plans' Results logs completed;
   memory update.
3. PR prep with test plan: fresh Genius-pick song lands each route
   correctly; SRT song unchanged (or per S-2); network-down add still
   produces a song; sidecar reuse on re-add (no refetch).

**GATE F** — Ken reviews. Follow-on decisions recorded (not
implemented): R-3's SRT-song timing fetch; NetEase word-level (`yrc`)
if `syncedlyrics` ever supports it; any remaining de-reverb-skip
action.

## Fallback branch (license: O-2, or S-5 = scaffold-first)

### F1 — word route: verify + direct `.ass` (license: GATE R GO)

Execute per **Appendix C (locked at GATE R)**:

1. New module `pikaraoke/lib/timing_verify.py` (pure): richsync sidecar →
   provider-text line objects; `verify_fit(provider_lines,
   transcribe_words) -> VerifyResult` (the locked statistics/thresholds);
   `warp_line_objects(...)` applying the fitted slope/offset with
   `MAX_WORD_DUR_S` caps. The evidence plan's 2b scratchpad is the
   reference implementation; this is its lifted, tested form.
2. `LyricAlignStage` routing: genius-origin + `synced_timing.kind ==
   "word"` → transcribe pass only (exists for the de-reverb gate, now
   feeds the verify), skip align/joint. PASS → warped provider line
   objects → post-passes per Appendix A → `generate_ass`. FAIL → log
   the failing statistic, demote richsync to a line scaffold, fall to
   F2's route (or the joint matcher pre-F2).
3. Capture verify stats + route taken into the debug bundle.
4. Tests: pass/fail routing, wrong-song sidecar fails the gate
   (negative-control fixture from 2b), provider text reaches the
   `.ass`, post-pass subset per Appendix A.

**GATE V1** — live validation: regenerate the word-route corpus songs;
line-list + route diff vs the 2b renders (match modulo snap); Ken
spot-eyeballs 2–3. Commit: `feat(pipeline): richsync verify + direct
ASS route`.

### F2 — line route: scaffold cue-align (license: GATE S S-1 GO)

Execute per **Appendix D (locked at GATE S)**:

1. `LyricAlignStage` routing: genius-origin + line timing available
   (sidecar `kind=="line"`, E1 `.lrc`, or F1 demotion) → anchors from
   the YTASR artifact + the transcribe pass → `merge_cue_spans` →
   `warp_scaffold_cues` (best source by the Appendix B selection key) →
   `cue_align.align_song` with the S-2 aligner → post-passes per
   Appendix A.
2. Warp-gate failure follows the S-3 ruling.
3. SRT-origin songs: byte-identical behavior (regression test).
4. Tests: routing, anchor assembly, source selection, gate-failure
   branch, srt-path untouched.

**GATE V2** — live validation: regenerate the line-route corpus songs;
re-pace/overlap/flags vs the S-A table (should reproduce); Ken
spot-eyeballs the 4 NetEase-sourced songs. Commit: `feat(pipeline):
scaffold cue-align route`.

## Verification matrix (every build phase)

1. Import-smoke changed modules; full unit suite on the Linux box.
2. `pre-commit run --config code_quality/.pre-commit-config.yaml --files
   <changed>`.
3. The phase's own validation (GATE V/V1/V2/X protocol).
4. Self-review (correctness / simplicity / robustness), commit, alert
   Ken when a /code-review batch + /compact point is reached.

## Results log

(build-side results; probe results live in the evidence plan)

---

## Appendix A — route contract (locked, Fable, 2026-07-18; moved from the evidence plan)

Routing is decided in `LyricAlignStage` from artifacts `lyrics_fetch`
set; `lyrics_fetch` never routes, it only resolves sources. The
precedence below is identical on both build branches — the branches
differ in the *mechanism* behind each route, not in who gets routed
where.

**Artifact schema** — `ctx.artifacts["synced_timing"]` (absent when no
timing resolved):

```python
{
  "kind": "word" | "line",
  "path": Path,            # lyrics/<stem>.timing.json sidecar
  "source": "musixmatch" | "netease",
  "map_rate": float,        # vs the Genius sheet at fetch time
  "track": {...},           # provider identity for provenance/debug
}
```

**Precedence** (first match wins):

1. `lyrics_origin == "srt"` → SRT cue-align, exactly today's path. (The
   R-3 ruling may change this later; not in this plan.)
2. genius-origin, `kind == "word"`, GATE R = GO → word route (engine
   E2 / fallback F1). Verify or score-gate FAIL → the sidecar's line
   starts join the line-source pool.
3. genius-origin, any line source (sidecar line, word-route demotion,
   or E1 `lyrics/<stem>.lrc`) → line route (engine E2 / fallback F2,
   per its license). Warp-gate failure → the S-3 branch.
4. otherwise → engine no-timing route (engine branch) / joint matcher
   (fallback branch, unchanged).

**Display text:** the word route renders provider text; all other
routes render the sheet (Genius lines) as today — scaffolds map
provider cues *onto* sheet lines (`cue_spans_for_lines` direction), so
the line route never changes what the singer reads.

**Post-pass policy:** onset/edge snap run on whisper-timed routes;
their applicability on CTC-timed routes is the Appendix D decision
(GATE C recorded CTC edge timing as already better than the snap's).
Evidence veto runs only on the joint-matcher route (fallback branch).
LRCLIB E1 fill runs only on the joint-matcher route (scaffold/engine
routes place every line by construction; word-route lines aren't sheet
lids — executor: verify the fill call site is joint-route-gated and
add the gate if it is not).

**Failure containment:** every fetch/verify/warp/score failure degrades
one route, never fails the song. A song that would have processed
yesterday processes identically with the network down (sidecar absent →
no-timing route / SRT as today).

## Appendix B — timing-fetch module design (locked, Fable, 2026-07-18; moved from the evidence plan)

`pikaraoke/lib/timing_fetch.py`, lifted from
`scripts/musixmatch_coverage_improve.py` (script becomes an importer).

- **API surface** (locked):
  `ensure_timing(song_path, title, artist, sheet_lines, media_dur)
  -> dict | None` — disk-first (existing sidecar wins), else fetch +
  persist + return the Appendix A artifact dict (`None` when no
  confident timing). Mirrors `lrclib.ensure_lrc`'s shape on purpose.
  Internal helpers keep the probe script's proven names
  (`reference_pick`, `best_by_reference`, `candidate_lyrics`).
- **Call site** (locked): `LyricsFetchStage` Branch a only, a new
  `self._resolve_timing(ctx, song)` invoked immediately after
  `self._resolve_lrclib(...)`, reusing the already-probed
  `media_duration_s` artifact and `parse_lyric_lines(song.text)` sheet
  exactly as `_resolve_lrclib` does; stashes
  `ctx.artifacts["synced_timing"]` on success. Same never-raises
  logging pattern.
- **Provider instance** (locked): one module-level shared `Musixmatch()`
  instance, created lazily on first fetch and reused for the process
  lifetime — this is both the token-throttle fix from the probes *and*
  the guard against `syncedlyrics`' `LRCProvider.__init__` logging
  footgun (it calls `addHandler` unconditionally per instantiation; a
  long-running server constructing one per song would accumulate
  duplicate handlers).
- **Query variants:** `[f"{title} {artist}", title]`, title-only tried
  only when the full query yields nothing confident (probe Mechanism 2).
  Inputs: Genius `title`/`artist` via `lrclib.clean_key` — same derived
  keys the E1 path uses; no new query surface (scope ruling).
- **Candidate selection:** per candidate, richsync-first then subtitle
  fetch; score `(map_rate, -abs(track_length - media_dur))` against the
  Genius sheet via `map_lines_to_cues` — identical key to
  `lrclib.select_candidate`. Confidence bar: `map_rate >= 0.5`; below it
  the result is recorded in the sidecar but `synced_timing` is not
  stashed (wrong-song protection; the verify/warp/score gates are the
  second line of defense).
- **NetEase:** only when Musixmatch yields none or 0.0; public
  `syncedlyrics.search(term, providers=["NetEase"], synced_only=True)`;
  always `kind: "line"`.
- **Sidecar** `lyrics/<stem>.timing.json`:

```python
{
  "schema_version": 1,
  "fetched_at": iso8601,
  "query": {"term": str, "variant": "full" | "title-only"},
  "source": "musixmatch" | "netease" | "none",
  "kind": "word" | "line" | "none",
  "map_rate": float,
  "track": {"track_id": ..., "track_name": ..., "artist_name": ...,
             "track_length": ...},        # provider-shape, provenance
  "body": {...} | str | null,  # raw richsync JSON (word) / LRC text (line)
}
```

  Reuse-on-disk: an existing *parseable* sidecar (any `source`,
  including `"none"`) is authoritative — no refetch, mirroring
  `ensure_lrc`. An unparseable/corrupt sidecar (JSON error, missing
  `schema_version`) is treated as absent: log a warning, refetch,
  overwrite — that is the behavior E0's corrupt-sidecar test locks.
  Bulk refetch is the batch script's job (`--save-bodies --force`). A
  `"none"` sidecar is still written on a miss so re-adds don't
  re-query.
- **Never raises;** all failures log + return no-timing. All sleeps/
  backoff per Ground rules. Fetch happens once per song at add time —
  the pacing exists for the batch tool, production inherits it for free.

## Appendix C — word-route verification criterion (LOCKED as decision procedure, Fable, 2026-07-18)

Fable pre-locks the *procedure*; at GATE R the judge executes it
verbatim and records the resulting constants back into this section.
No model invents a threshold — any case the procedure does not cover
is a STOP → Ken.

**Cohorts (from 2b):** PASS = the ≥0.5-map_rate word songs; CONTROL =
Selfish + Incomplete.

**General threshold rule, per statistic:** let W = the worst value
over PASS and B = the best value over CONTROL, in the statistic's
quality direction. If W is strictly better than B, the statistic is
*discriminative* and its threshold = the midpoint of [B, W] (geometric
midpoint for ratio-like statistics). Otherwise the statistic is
dropped from the gate and recorded as non-discriminative. The gate =
AND over all discriminative statistics; fewer than 2 discriminative
statistics → STOP → Ken (the verify design is not viable as
specified).

**Statistics and clamps:**

- `n_pairs`: floor locked at 5 (the `WARP_MIN_ANCHORS` class),
  cohort-independent. `pair_fraction`: general rule.
- `slope`: default window [0.97, 1.03]; widened only as far as needed
  to cover PASS plus 0.005 margin; hard cap [0.90, 1.10].
- residual MAD: threshold = 1.25 × max MAD over PASS, clamped to
  [0.75 s, 2.0 s].
- Per-line outlier (locked design, data-independent): a line with
  |residual| > 3 × the MAD threshold is an outlier; on an
  otherwise-passing song, outlier lines are per-line demoted to the
  line-source pool / repair path, never rendered from richsync; a song
  with > 20% outlier lines fails the gate entirely.
- zero-evidence-span fraction: general rule, threshold capped ≤ 0.4.
- Emission-score family (only if GATE O ≠ O-2): per-line score against
  the GATE O band. Adoption rule: if discriminative under the general
  rule on 2b's cohorts, it becomes the PRIMARY gate and the transcribe
  family retains only `n_pairs`/`pair_fraction` as a sanity floor;
  otherwise transcribe-family-only.

**R-5 mechanism rule (locked):** richsync-guided CTC (2b arm iv) is
chosen over the warped render (arm i) unless Ken's A/B finds (iv)
visibly worse on any song or its line coverage is lower; ties go to
(iv) — it retires the foreign-clock warp from the output path. Both
bad ⇒ the R-1 NO-GO path (demote to line source).

**Stage wiring (locked):** the word route runs the transcribe pass
only (align/joint skipped); verify consumes the same transcribe words
the de-reverb gate uses, downstream of any de-reverb retry (the gate's
existing behavior is unchanged and upstream of verify). Capture:
verify statistics, route taken, per-line demotions → debug bundle.

**Negative-control requirement:** the assembled gate must fail both
controls. If it cannot, STOP → Ken.

## Appendix D — scaffold/aligner integration (LOCKED, Fable, 2026-07-18; S-constants recorded at GATE S)

Data-independent decisions, locked now:

- **Snap policy:** onset/edge snap is DISABLED on CTC-timed routes by
  default (GATE C: CTC edge timing already beats the snap's — the
  burden of proof is reversed). It is re-enabled only if the S-arm
  flag tables show a specific, named flag class the snap demonstrably
  fixes, recorded at GATE S. Whisper-timed routes keep the snap
  unchanged.
- **De-reverb:** the existing transcribe-side de-reverb gate is
  untouched on every route in both branches (it feeds anchors and
  verify). The CTC aligner itself never triggers de-reverb.
  Retirement is exclusively an E4 deletion-review question.
- **Non-Latin lines (per-line, never per-song):** a line whose
  normalized alignment form is empty or majority-non-Latin after
  ASCII fold is CTC-ineligible: engine branch → prior-paced fill with
  its own provenance tag; fallback branch → the existing whisper
  realign/repace rescue.
- **Richsync ends:** when a scaffold source is a word sidecar,
  `ts`/`te` are used as span starts/ends (`te` clamped at the next
  start); line-level sources keep paced ends.
- **`slice_align` wiring:** whisper = the existing `WhisperWorker`
  shim (`cue_align_song._make_slice_align` pattern); CTC = the
  `ctc_align` adapter implementing the identical `(t0, t1, text,
  label) -> words | None` contract via emission slicing (Appendix E).
  The S-2 rule in the evidence plan's GATE S selects per path.
- **Line-source pool selection:** Appendix B's `(map_rate, dur)` key
  across sidecar-line / E1-lrc / demoted-richsync, computed against
  the sheet at routing time; ties → the sidecar (fresher provenance).

Recorded at GATE S (mechanical read-offs, rules in the evidence plan's
GATE S): S-2 aligner per path, S-3 warp-failure branch, any snap
re-enable exception with its named flag class.

## Appendix E — engine core contract (LOCKED design, Fable, 2026-07-18; only the gate band is filled later)

Everything below is locked now; the single data-dependent constant —
the score gate band — comes from the GATE O read-off and is recorded
here at that GATE.

- **Emission computation:** 20 s chunks with 1.0 s overlap at each
  interior boundary; adjacent chunk emissions spliced at the overlap
  midpoint (each chunk contributes its half), bounding any boundary
  artifact ~0.5 s from a splice. Device: CUDA else CPU; model default
  dtype. (Phase 1 used non-overlapping chunks — fine for an eyeball;
  the overlap is the production hardening.)
- **Model lifecycle:** one shared model instance per process (the
  Phase 1 load-once rule, now contract); weights download on first
  `get_model()` into the torch-hub default cache; offline/no-weights →
  engine unavailable → route degrades per Appendix A's failure
  containment, the song still processes.
- **Emission cache:** held in memory per song for the stage's
  lifetime; harnesses may spill to `get_temp_directory()` scratch;
  never a persisted library artifact (cheap to recompute; stems can
  change silently, so persistence would need invalidation machinery
  that recomputation makes unnecessary).
- **Windowed align:** window `[t0, t1]` → frame range via the
  samples/frames ratio; minimum window 0.2 s (matches the existing
  realign minimum); empty or OOV-only token range → `None`.
- **Scoring (statistics locked; band from GATE O):** word score =
  mean `TokenSpan.score` over the word's tokens; line score = both
  mean and min of its word scores (GATE O records which variant
  separated better — that variant is the gate statistic); per-song
  robust z-normalization (median/MAD over all aligned word scores).
  If the gate statistic was rescued at GATE O′, the engine implements
  that statistic instead, definition adopted verbatim from evidence
  plan Phase 1b step 4 (S-decode = greedy-decode similarity over the
  line's emission slice; S-shift = free-realign displacement in the
  ±5.0 s-padded slice; S-tx = transcribe-token corroboration in the
  ±2.0 s-padded window; rolling-5 variants computed within-song).
  S-tx only: transcribe output missing for a song → that route runs
  ungated (Appendix A containment; never a song failure).
- **Repair loop:** a below-band section re-aligns once in its
  warped-prior window padded by `SECTION_PAD_S`; if still below band,
  widen the window ×1.5 and retry once; still failing → prior-paced
  fill with provenance `ctc_fill`. Acceptance = post-repair line
  score ≥ the band. Repair triggers per contiguous failing section,
  demotes per line.
- **Normalization:** display token kept beside alignment form; ASCII
  fold; minimal local numeral expansion (comma-grouped integers, bare
  digits, trailing-punctuation strip — covers the corpus cases
  `525,600`, `30`, `20.`; hand-rolled, no new dependency); anything
  unhandled → OOV-skip with the Phase 1 index bookkeeping. Non-Latin
  per-line rule per Appendix D.
- **Caps + metrics:** `MAX_WORD_DUR_S` word-sweep caps as in
  `cue_align`; every engine harness run reports `artifact_metrics`
  plus gated-fraction, repaired-fraction, and fill-fraction per song.
