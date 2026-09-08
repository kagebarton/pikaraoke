Model: Claude Fable 5 (design, locked 2026-07-18); judge Opus; executor Sonnet 5

# Timing-route program — the map

Entry point for the whole timing-source routing effort. This file owns the
routing picture, the sequencing, and the shared ground rules. **It owns no
probes and no verdicts** — those live in the lane files, one per timing
source.

**Read Part 1 and Part 2 as two different things.** Part 1 is what the
code does today; Part 2 is what the locked rulings specify it should do.
They were not the same shape — today's matcher has two routes and the
target had four — until 2026-09-08, when Ken ceased work on the line
route and the target collapsed back onto the shipped two routes plus a
widened fill (Part 2). Reading a plan's rung vocabulary as if it
described shipped behaviour is still the main way these documents
mislead. **A new session starts on `route-no-timing.md`** — see
"Remaining execution order".

## Part 1 — As shipped today

What the code does right now. Nothing here is aspirational; every box is
reachable on the current branch.

### Routing

`LyricAlignStage.run` (`pikaraoke/pipeline/stages/lyric_align.py`). The
entire routing decision is one `if cue_spans:` at line 145:

```
                    ┌─ lyrics_path is None ──────────────► TRANSCRIBE mode
                    │                                      no sheet at all;
                    │                                      whisper writes the
                    │                                      lines it hears
   song ────────────┤
                    │                    ┌─ cue_spans ────► CUE-ALIGN  (SRT)
                    └─ sheet exists ─────┤   non-empty      whisper slice_align
                                         │                  route-srt.md
                                         │
                                         └─ else ─────────► JOINT DP
                                                            whisper + transcribe
                                                            + ytasr
                                                            route-no-timing.md
```

**Two routes, not three.** A song with LRCLIB line timing but no SRT
takes the **joint branch** — LRCLIB enters only as a gated post-pass
*fill* (`lrclib_fill.plan_fills`, applied at `lyric_align.py:257`), never
as a routing tier. Rung 2b of the ladder has zero production miles.

### Demotion gates in force

Two different things in these plans are called a "gate", and mixing them
up costs hours:

- **GATE C / O / R / S / P / L** — decision points in *this program*. Ken
  rules on them. They fire once, in a session, and land in a Results log.
- **The thresholds below** — *runtime* code, firing per song, deciding
  whether a source is trusted, demoted, or dropped.

| Threshold | Module | Value | What it rejects |
| --- | --- | --- | --- |
| `is_generated` | `srt_provenance` | marker file | The pipeline's own earlier SRT, so it can't be re-adopted as an uploader caption |
| `cue_spans` empty? | `lyric_align._load_lyrics` | — | **The route fork itself** — SRT vs joint |
| `WORD_SEG_MIN_FRAC` | `ytasr` | 0.5 | Line-level/manual captions posing as word-level ASR |
| `MIN_CAPTION_WPM` | `ytasr` | 15.0 | `[Music]` degeneracy. Unknown duration → reject outright |
| `CANDIDATE_MAX_EDIT_RATIO` | `ytasr` | 0.34 | A per-line ASR candidate too garbled to admit |
| **`WRONG_SONG_MAP_RATE`** | **`timing_fetch`** | **0.5** | **The wrong-song floor for Musixmatch/NetEase sidecars** |
| `_MAP_MIN_RATIO` | `lrclib` | 0.85 | A per-line text mapping too weak to use |
| `FILL_MAX_SLOPE_DEV` | `lrclib_fill` | 0.01 | Song not fill-eligible unless its Theil-Sen slope is within 1% of unity |
| `WARP_MIN_ANCHORS` / `WARP_MAD_GATE_S` | `lrclib_fill`, `cue_align` | 5 / 2.0 s | A slope estimate with too few anchors or too much residual |
| `COLLISION_TOL_S` | `lrclib_fill` | 0.2 | A fill landing on top of an already-placed line |
| `MIN_REF_DB` | `evidence_veto` ← `onset_snap` | −45.0 dB | A line placed in silence |

**The one under active repair is `WRONG_SONG_MAP_RATE`.** It is a *text*
map-rate standing in for a *timing* judgment, and GATE R proved it
mislabels in both directions: Selfish's sidecar scored 0.38 — below the
floor — but was the right song, correctly timed (the low score was an
SRT-segmentation artifact), while 5 of 14 sidecars that passed the floor
time a different recording or edit. M1 and M2 exist to replace it with
labels derived from timing truth.

## Part 2 — Target

What the locked rulings specify. Source of truth is **Appendix A** (route
contract) and **Appendix D** (aligner + post-pass policy) in
`plans/ctc-sync-engine.md`; both are locked. This section is a reading of
those, not a second spec — if the two disagree, the appendices win.

### Target routing

Appendix A's precedence, first match wins. Routing is decided in
`LyricAlignStage` from artifacts `lyrics_fetch` sets; `lyrics_fetch` never
routes, it only resolves sources.

```
  1  lyrics_origin == "srt" ─────────────────► SRT CUE-ALIGN
                                               whisper (S-2 SRT arm)
                                               snap ON
                                               ── shipped, unchanged ──

  2  genius + kind=="word" + GATE R = GO ────► WORD ROUTE (F1)
     │                                         renders PROVIDER text
     │                                         ┌──────────────────────┐
     │                                         │ CLOSED 2026-09-04    │
     │                                         │ R-4 retired the gate │
     │                                         │ struck by the        │
     │                                         │ consolidation pass   │
     │                                         └──────────────────────┘
     └─ verify FAIL ──┐
                      ▼
  3  genius + any line source ────────────────► LINE ROUTE (F2)
     (sidecar line, word-route demotion,        warped scaffold
      or lyrics/<stem>.lrc)                     CTC (S-2 genius arm)
     │                                          snap OFF
     │                                          ── NOT BUILT ──
     └─ warp-gate failure ──┐                   ✗ WITHDRAWN 2026-09-08 (Ken)
                            │                     work ceased; falls to 4
                            ▼
  4  otherwise ────────────────────────────────► JOINT MATCHER
                                                unchanged from today
                                                whisper; CTC pending J1
```

**Target as of 2026-09-08 (Ken): routes 1 and 4 only.** Route 2 closed
2026-09-04 (R-4) and route 3 was withdrawn 2026-09-08 — S-1 withdrawn,
work ceased, F2 never built. Fetched timing (word or line sidecar,
`.lrc`) reaches production through one door: the joint route's gated
fill, today LRCLIB-only, to be widened to the sidecar sources
(`route-no-timing.md`, Phase 5). Per-song admission gates on fetched
timing are retired twice over (R-4; the warp gate's verified blind
spot), so timing enters per line and loses per line.

**Display text:** every route renders the Genius sheet, as today. (The
word route would have rendered provider text; it is closed.)

**Failure containment:** every fetch/verify/warp/score failure degrades
one route, never fails the song. With the network down, a song processes
exactly as it does today.

### What changes vs. shipped

| | Shipped | Target |
| --- | --- | --- |
| Routes | 2 (+transcribe) | **2** (+transcribe) — F1 closed 2026-09-04, F2 withdrawn 2026-09-08 |
| Line timing, no SRT | joint DP; LRCLIB as post-pass fill | joint DP; fill widened to the fetched sidecar (Phase 5, design owed) |
| Word timing | nothing — sidecar unused for routing | same door: sidecar line `ts`/`te` as a fill source, never a route |
| Scaffold aligner | n/a | n/a — route withdrawn; M6-d moot |
| Evidence veto | joint route | joint route only (unchanged) |
| LRCLIB fill | joint route | joint route; **kept** — refit Phase 1.1 cancelled 2026-09-08 |

### Target demotion gates

Snap policy is settled; the word-route verify is retired; the warp gate
is moot as of 2026-09-08; `map_rate` stays as the fetch-time wrong-song
check only.

| Gate | Decides | Status |
| --- | --- | --- |
| `map_rate` at fetch (`WRONG_SONG_MAP_RATE`) | whether a sidecar is admitted at all | **adequate for wrong-song** (M2: 32/32 cross-paired controls collapse at the text-pairing floor). **Wrong-*edit*: M7-a asked it directly 2026-09-08 and the evidence says `map_rate` does not catch it** — all 17 cohort sidecars cleared the floor, yet only 4 track our recording; on Let It Go the text agrees 1.00 against a sidecar spanning 117 s of a 201 s video. Raw tables in `route-line-timing.md`. **Ruling is Ken's; no gate has been changed.** |
| ~~Word-route verify (Appendix C)~~ | ~~precedence 2 vs demotion to 3~~ | **RETIRED 2026-09-04 (R-4 closed)** — no per-song gate is constructible from this evidence family; demotion to 3 is permanent |
| Warp gate (`WARP_MIN_ANCHORS` 5 / `WARP_MAD_GATE_S` 2.0 s) | precedence 3 vs fall to 4 | **moot 2026-09-08** — route withdrawn. Its verified blind spot (fit population excludes unsung sections; duration clamp crams) is on record in `route-line-timing.md`; do not reuse it as a per-song admission test |
| Snap policy (Appendix D) | post-pass per route | locked: OFF on CTC-timed routes, ON on whisper-timed; "re-enable exception: none" |

**The Appendix C hole is why rung 1 does not exist — and as of
2026-09-04 it is why rung 1 is closed.** The procedure was pre-locked in
2026-07-18 and was supposed to have its constants filled in at GATE R.
Executed verbatim it produced **zero** discriminative statistics against a
required two. M1–M3 re-specified the cohorts and controls and it still
separates nothing: M1's purpose-built independent labeller did not
reproduce Ken's labels, M2's 32 controls all collapse before reaching the
residual family, and M3 closed by inspection. **R-4 is closed and the
per-song gate is retired**; the demotion to rung 3 is permanent. The
finding is narrow — *no per-song admission gate is constructible from this
evidence family*, not "richsync word timing is unusable", since 6 of 10
songs eyeballed usable and one beat production. Word sweeps re-enter, if
ever, as a **per-line** choice inside F2 (R-5's arm (i) vs (iv)), which is
a new mechanism on rung 2b rather than rung 1 returning. Detail in
`plans/route-word-timing.md`.

### Open decisions that could still move the target

- ~~**R-4 / M1–M4** — the verify criterion.~~ **CLOSED 2026-09-04**:
  the per-song gate is retired, precedence 2 never fires, and the
  demotion to the line pool is permanent. M5 refuted, M3 closed by
  inspection, M4 re-homed to F2's warp gate and held.
- ~~**S-1 — the route's own licence.**~~ **WITHDRAWN 2026-09-08 (Ken):
  work on the line route has ceased.** The GO had stood as a ruling but
  not as a finding since the 2026-09-04 re-read; M7-a's stop rule closed
  the reference path; the stratified fallback stopped at its own sign
  guard; and a Fable assessment on 2026-09-08 found that no per-song
  admission test for a wrong-edit source is constructible from what is
  on disk (M7-a: 4 of 17 sound; the warp gate accepted 5 of 6 wrong-edit
  songs; the shape diagnostic catches 2 of those 5; the duration signal
  that would catch Domino also rejects Colors of the Wind). Ken ruled
  the route not worth the remaining spend. The S-3 extension is **moot**
  with the route; the principle it would have affirmed is recorded in
  `route-line-timing.md`'s closing entry so nobody re-derives it. The
  lyric-parser fix (`2516ca8`) stands on its own as route-independent.
- ~~**M6 / S-2's genius arm**~~ — **MOOT 2026-09-08**: the aligner
  selection for a withdrawn route. The M6 raw tables and Ken's M6-d
  observations stay on record in `route-line-timing.md`.
- **GATE J1/J2** — CTC in the joint matcher, and whether edge snap
  retires on CTC-won lines. Changes precedence 4's aligner and Appendix
  D's snap exception.
- **GATE L** — non-Latin form. Re-homed 2026-09-08 to the joint route's
  aligner (whichever J1 selects), since F2 is withdrawn; additive, blocks
  nothing but the Mandarin corpus.
- **R-3** — SRT-first *stands*, but Appendix A flags that a later ruling
  could reorder precedence 1 against 2.

Not open, do not re-litigate: engine branch E1–E4 is **OFF** (GATE O =
O-GRAY); no section-level DP (GATE P); densify rejected (S-3); CTC
rejected on the SRT path (S-2, SRT arm); the line route itself (S-1
withdrawn 2026-09-08 — re-open only with a per-line design, never with a
per-song gate).

## Which file owns what

| File | Owns |
| --- | --- |
| `PROGRAM.md` | this map, sequencing, ground rules, model switching |
| `GLOSSARY.md` | ASS/CTC/MMS_FA/emission/melisma/richsync — read before guessing at an acronym |
| `route-word-timing.md` | rung 1 (**CLOSED 2026-09-04**); GATE R, R-1 ruling, M1-M5, the R-4 closure |
| `route-srt.md` | rung 2a; the shipped cue-align route, S-C |
| `route-line-timing.md` | rung 2b (**CLOSED 2026-09-08** — S-1 withdrawn); GATE S scaffold arms, M6, M7, the fallback; GATE L re-homed to rung 3 |
| `route-no-timing.md` | rung 3 — **the live build lane**; the joint catch-all refit, GATE P/J1/J2, Phase 5 (line timing as a fill source), GATE L |
| `shared-aligner-form.md` | GATE C, GATE O, Phase 0 harness, ruling-provenance audit |
| `ctc-sync-engine.md` | build phases + locked appendices; each licensed by a GATE above |
| `completed/` | closed plans, kept for their Results logs |

Rule of thumb: **a probe belongs to a lane if its outcome changes what
happens for one timing source only.** If it changes the aligner or the
architecture for every source, it is cross-cutting and belongs in
`shared-aligner-form.md`.

## Branch lineage

`master` (upstream) → `fable_matcher_refine` (= `musix_ctc`) →
`timing_pillars` → **`joint_catchall_refit`** (current). `pathed_align`
holds the pre-port scaffold-warp history; its machinery is now ported into
shipped `cue_align.py`, so it is not dead-end history.

## Remaining execution order (Ken, 2026-09-01) — measure first, lock once

> **START HERE (2026-09-08).** The line route is closed (step 4). The
> next spend is the **joint plan, Phase 2a → GATE J1/J2** (step 5), in
> `plans/route-no-timing.md`. Its Phase 1.1 is cancelled and 1.2 is
> done; after J1, Phase 5 there (line timing as a fill source) is the
> design that inherits everything the line route learned.

Ken's sequencing ruling: run the remaining measurement program to
completion, then consolidate the build design once, rather than amending
locked appendices as results trickle in. The dependency check that
licenses this: **no remaining probe needs production code.** Only the
V-gates (the build plan's V1/V2, the joint plan's V) are validation *of*
shipped code, which is tautological.

Order — cheapest and highest overturn-risk first:

1. ~~**Joint plan Phase 4 → GATE P**~~ — **CLOSED 2026-09-01, NO-GO.**
   The gap and inversion mass is repeat cross-attraction plus
   lyric-version drift, not sheet permutation, so the monotonic DP
   stands and no section-level DP is commissioned. The redesign risk
   this step existed to price is retired.
2. ~~**Phase 2b → GATE R**~~ — **run 2026-09-03; R-1 ruled the same
   day.** R-1 NO-GO as the route stands, mechanism GO on evidence. R-2
   and R-3 settled (provider text as-is; SRT-first). **R-4 remains
   open** — STOP → Ken. R-5 no award. Detail in
   `plans/route-word-timing.md`.
3. ~~**M1-M5** — the R-4 re-specification~~ — **CLOSED 2026-09-04.**
   M1 ran and was NOT VALIDATED (no separation at the primary
   tolerance); M2 ran, 32/32 controls collapsing at the text-pairing
   floor; M3 closed by inspection; **R-4 closed and rung 1 closed with
   it**. M4 re-homes to F2's warp gate and is held. Original scope:
   M1 relabel by timing truth; M2 cross-paired negative controls;
   M3 re-run Appendix C on M1 labels + M2 controls; M4 per-section
   pairing-coverage detector; ~~M5 check whether rushed sweeps are
   `cue_align.MAX_WORD_DUR_S` truncating sustained notes~~ — **CLOSED
   2026-09-04, REFUTED**: the songs Ken called clean absorbed larger
   in-clip sweep truncations than the two he called rushed, so the
   constant stays at 1.5 s. The "rushed" class is still unexplained and
   feeds M1's labelling rule.
4. ~~**M6**~~ — **ran 2026-09-04; both arms reproduce, and it escalated
   past its own question to S-1. The whole step CLOSED 2026-09-08: S-1
   withdrawn (sub-item 3).** M6-d could not be read off its commissioned
   pair. The order that replaced this step, from the S-1 re-read, kept
   as the record of how it closed:
   1. ~~**Lyric-parser fix** (wrap dirt)~~ — **DONE 2026-09-08**
      (`2516ca8`). Cause was Genius wrapping one logical line across
      physical lines, not unterminated brackets; rejoining makes the
      existing bracket defences fire. 5 of 17 songs change and the only
      letters removed corpus-wide are the two attributions. Of the ten
      songs cleared for step 2, only **Free** needs regenerated bundles
      — but Free has no route-independent reference, so for M7 that
      regeneration is moot; the two songs M7 actually needs re-run are
      **Defying Gravity and Man Out of You**.
      A whitespace-wrap residual on Paradise is left unfixed by choice.
   2. **M7 — re-derive S-1 against a route-independent reference.**
      **Approach and read-off rules both RATIFIED by Ken 2026-09-08.
      M7-a RAN 2026-09-08: 2 of 10 corpus songs certify, so the
      pre-registered stop rule fires and M7-b is not run — the fallback
      replaces it. Raw tables in `route-line-timing.md`; no read-off
      taken, S-1 still open.**
      `timing_fetch` writes `lyrics/<stem>.timing.json` at add time and
      **no router consumes it**, so it is independent of both routes.
      **M7-a** first asks whether it tracks *our* recording, against a
      caption reference timed to our video — this is the wrong-*edit*
      question the demotion-gate table left open — and certifies each
      song individually. **M7-b** scores both routes on the lines the
      certified reference covers, counting a hidden line as a miss and
      giving a filled line no credit for merely existing, so neither
      contract can win by construction. **M7-c** is the eyeball,
      narrowed to the residual. If too few songs certify, the fallback
      is a shared-lines-only comparison plus a signed judgment on each
      route's exclusive lines.

      The pre-registration corrects the commissioning entry's cohort:
      **18 of the 34 `.srt` are PiKaraoke's own output** (they carry a
      `.srt.generated` marker), so the usable reference cohort is **17
      library-wide, 10 in the corpus, 6 in the cleared eyeball ten** —
      not 26. Every corpus reference is YouTube ASR; every uploader
      caption is on a non-corpus song, because the corpus was selected
      for having no SRT source. Detail and the read-off rules in
      `plans/route-line-timing.md`.

      **Fallback pre-work 2026-09-08 (structural only, no rules drafted,
      no statistic computed).** Sizing the population first: the joint
      route's hidden lines are its *wordless* ones — `absent_line_ids`
      is empty on all 17 songs and unplaced lines are interpolated
      without words, which the ASS writer then skips — so the scaffold
      renders every sheet line, joint-only lines are 0 everywhere, and
      the exclusive set is 157 lines in scope, 41 inside the cleared
      ten. Both of the fallback's example signs live in that one set.
      Second, **the scaffold arm's own scaffold source is the sidecar
      M7-a just impeached** (`--timing sidecar` default, reading
      `lyrics/<stem>.timing.json`): of the 6 corpus songs M7-a
      attributed to a genuine edit difference, the warp gate rejected
      **1** and accepted **5**. The affine warp absorbs offset and rate
      by construction but cannot express a cut verse or an added
      repeat, and which shape those 5 are is **not** established — the
      cross-tab is two recorded tables, not a measurement.
      `synced_timing` is inert in the shipped pipeline, so no shipped
      route is touched; what is touched is the arm M6 and S-1's
      evidence were produced on, and F2's designed scaffold source.
      **Fable judge round 2026-09-08, commissioned by Ken, path
      accepted.** It identified the mechanism: the cram is the
      **duration clamp**, and the gate cannot see the condition that
      produces it — the fit population is built only from lines that
      both the source and the audio place, so a section the video never
      sings never enters the check meant to catch it, and every line
      warping past the end is pinned to one timestamp and re-paced at
      the floor. Executor verified the code claims and found the same
      clamp firing at the front as well. **This reframes the open S-3
      item: it is not "does the principle extend to warp-accepted
      songs" but "the gate does not implement the principle Ken
      ruled" — a code fact, rulable without any measurement and prior
      to the fallback.** The round's other unruled findings: the
      fetch stage already holds a duration signal it uses only as a
      map-rate tie-break (verified); the fallback's two motivating
      examples both sit outside its bounded eyeball and one no longer
      exists post-`2516ca8`; the cleared ten is the easy set for both
      routes; and if S-1 falls, the evidence points at the fetched
      timing entering the **joint matcher as one per-line candidate**
      rather than at a per-song route — a J1-adjacent build the
      program has never priced.

      **Stratified fallback pre-registration RATIFIED 2026-09-08; RAN
      and STOPPED the same day at its declared sign guard.** A GPU-free
      shape diagnostic labels
      each song REJECTED / STRUCTURAL / AFFINE from the arm's own
      inputs; the shared-line and exclusive-line read-off is then taken
      **per stratum**, the AFFINE stratum reading on S-1 and the
      STRUCTURAL stratum labelled S-3-extension evidence instead. The
      arithmetic only *selects* what Ken looks at — there is no
      reference, so the eye scores. Bounded at 71 looks in one sitting.
      Declared limit: the sitting is one arm, so unlike M7-b this
      cannot show the conclusion survives either resolution of S-2.
      Rules in `plans/route-line-timing.md`. Parts 1 and 2 ran: the
      diagnostic reproduced arm W on all 17, and within the cleared ten
      only one song is STRUCTURAL, so that stratum falls under the
      declared 4-song floor and cannot be read. **The guard against S-2
      then fired** — the two arms' per-song medians differ in sign on 6
      of the 9 readable songs against a threshold of 3 — so the
      read-off is suspended before the eyeball and goes to Ken. The
      look-list is fixed and saved; the sitting has not been run.
      **No gate has been changed and no verdict on S-1 is recorded.**
   3. ~~**Ken rules S-1 and the S-3 extension.**~~ **RULED 2026-09-08:
      S-1 WITHDRAWN, work on the line route ceased; the S-3 extension
      is moot.** Fable's assessment and the ruling are the closing entry
      of `route-line-timing.md`. The stacked-row sitting is not run; its
      fixed look-list stays on disk as optional evidence for Phase 5 of
      the joint plan (the 30 scaffold-only lines are that question in
      miniature) and needs no pre-registration change to be viewed.
   4. ~~**M6-d re-posed**, if the route survives.~~ MOOT.
   5. ~~**F2.**~~ WITHDRAWN, never built.
5. **Joint plan Phase 2a → GATE J1/J2** (GPU, scratchpad) — **NEXT
   SPEND as of 2026-09-08.** J2 feeds Appendix D's snap policy, which
   currently records "re-enable exception: none". Then 2b on a J1 GO,
   GATE V, Phase 3 → GATE T, and **Phase 5 (line timing as a fill
   source)**, whose design is owed once J1 has picked the aligner.
6. **S-E** (Phase 3's unrun optional arm; offline, no GPU align). Cheap
   add-on: informs the deletion inventory and tests Ken's GATE C
   observation.
7. **Phase 4 → GATE L** — whenever the Mandarin corpus exists. Blocks
   nothing and nothing blocks it but the corpus.

Then **one design-consolidation pass**: re-lock the build plan's
Appendices C, D and E with the real constants in a single revision.

**Carve-out — VOID as of 2026-09-04 (S-1 re-read); F2 WITHDRAWN
2026-09-08.** F2's licence was suspended pending Ken's re-derivation of
S-1 and then withdrawn with the route, so F2 is not a build at all; the paragraph below is kept as the
record of why it was thought zero-regret. The caveat named M6 as the
only coupling, and M6 turned out to reach the route's own licence
rather than just its aligner.

*Superseded text:* **F2 is a zero-regret build at any point in this
sequence, with one caveat added 2026-09-04.** Checked against every pending
outcome: an R-1 NO-GO only sends more songs into F2's line-source pool
(Appendix A already specifies that demotion); GATE P and GATE J1 are
rung-3 questions; GATE L is an additive per-line romanizer inside F2's
aligner. The single coupling was GATE J2 possibly flipping snap policy on
CTC-timed routes — a post-pass wiring flag, not a redesign. **The caveat:
M6 now gates F2**, because F2 builds on the aligner S-2's genius arm
selected and that selection is under re-read. The argument for pulling F2
forward otherwise stands: rung 2b has zero production miles, so every
number on it comes from harnesses.

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
  coverage table in `plans/completed/musixmatch-coverage-improvement.md` §Results is
  the routing ground truth for which song lands in which tier.
- Musixmatch politeness (relearn nothing): one shared provider instance,
  `CALL_SLEEP_S=2.5` / `SONG_SLEEP_S=4.0`, single 20s-backoff retry on
  401 with token-file clear, never per-call token refresh. NetEase: plain
  try/except + same pacing.
- GATE markers are hard stops: executor reports numbers, Judge reads,
  Ken rules. No proceeding past a GATE on executor judgment.


## Model switching

Same three roles as `plans/completed/matcher-accuracy-hardening.md` §"Model
switching", binding here identically:

- **Design** — Fable, completed 2026-07-18 (**succession locked
  2026-07-19**; Fable is available again and has read off GATE P and
  GATE R, but see the escalation rule below): this document and the build
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

### When a result goes to Fable (Ken, 2026-09-04)

Fable is billed per use, so a judge round is spent, not free. Escalate
**only** when at least one of these holds:

- **Ambiguity in the findings** — they admit more than one reading, or
  the pre-registered rule does not cover the case actually observed.
- **Significant new complexity surfaced during the run** that could
  change the verdict: a mechanism nobody priced, a control that turns
  out to be broken, an artifact that invalidates an arm.
- **The read-off is a GATE** whose outcome selects a mechanism or
  licenses a build phase. These are escalated on principle, not on
  difficulty.

Otherwise the executor reports its tables and **Ken rules directly**. A
result that is arithmetically decisive — a refutation that carries its
own control, a threshold missed by an order of magnitude — does not need
a judge round to confirm ten numbers.

This changes *who* reads, not the executor's boundary. Judge separation
still binds: the executor reports paths and raw tables and does not write
the verdict. It hands them to Ken instead of to Fable.

Executor discipline: the matcher plan's §"Executor discipline (Sonnet 5,
added 2026-07-12)" applies verbatim — specs are contracts, mismatches are
STOPs, numbers come from commands actually run, thresholds never move
after data.

| Phase | Design | Implement/run | Judge |
| --- | --- | --- | --- |
| 0 (port + baselines) | locked below | Sonnet 5 | — (infrastructure) |
| 1 (CTC probe, GATE C) | `plans/completed/ctc-forced-align-eyeball.md` | executed 2026-07-18 | done — see Results log |
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
