Model: Claude Opus 5 (design + judge); executor Sonnet 5 (design locked 2026-07-18 by Claude Fable 5; role passed to Opus 2026-09-10)

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

**Update 2026-09-18: the design-consolidation pass ran** (see
"Design-consolidation pass" under "Remaining execution order").
- The build plan is closed into `completed/`, and Part 2 is now its own
  source of truth.
- The inert synced-timing fetch is out of the pipeline.
- No measurement phase and no design item is live on the routing
  program. GATE L waits on its corpus.

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

- **GATE C / O / R / S / P / L / G** — decision points in *this
  program*. Ken rules on them. They fire once, in a session, and land in
  a Results log.
- **The thresholds below** — *runtime* code, firing per song, deciding
  whether a source is trusted, demoted, or dropped.

| Threshold | Module | Value | What it rejects |
| --- | --- | --- | --- |
| `is_generated` | `srt_provenance` | marker file | The pipeline's own earlier SRT, so it can't be re-adopted as an uploader caption |
| `cue_spans` empty? | `lyric_align._load_lyrics` | — | **The route fork itself** — SRT vs joint |
| `WORD_SEG_MIN_FRAC` | `ytasr` | 0.5 | Line-level/manual captions posing as word-level ASR |
| `MIN_CAPTION_WPM` | `ytasr` | 15.0 | `[Music]` degeneracy. Unknown duration → reject outright |
| `CANDIDATE_MAX_EDIT_RATIO` | `ytasr` | 0.45 | A per-line ASR candidate too garbled to admit (0.34 → 0.45 at GATE T, 2026-09-10) |
| ~~`WRONG_SONG_MAP_RATE`~~ | ~~`timing_fetch`~~ | ~~0.5~~ | ~~The wrong-song floor for Musixmatch/NetEase sidecars~~ — **out of production 2026-09-18** (`efd3559`): the fetch no longer runs in the pipeline; the module is `scripts/timing_fetch.py` |
| `_MAP_MIN_RATIO` | `lrclib` | 0.85 | A per-line text mapping too weak to use |
| `FILL_MAX_SLOPE_DEV` | `lrclib_fill` | 0.01 | Song not fill-eligible unless its Theil-Sen slope is within 1% of unity |
| `WARP_MIN_ANCHORS` / `WARP_MAD_GATE_S` | `lrclib_fill` (`cue_align`'s copy moved to `scripts/scaffold_warp.py` 2026-09-18, `28a118d`) | 5 / 2.0 s | A slope estimate with too few anchors or too much residual |
| `COLLISION_TOL_S` | `lrclib_fill` | 0.2 | A fill landing on top of an already-placed line |
| `MIN_REF_DB` | `evidence_veto` ← `onset_snap` | −45.0 dB | A line placed in silence |

**The one under active repair is `WRONG_SONG_MAP_RATE`.** It is a *text*
map-rate standing in for a *timing* judgment, and GATE R proved it
mislabels in both directions: Selfish's sidecar scored 0.38 — below the
floor — but was the right song, correctly timed (the low score was an
SRT-segmentation artifact), while 5 of 14 sidecars that passed the floor
time a different recording or edit. M1 and M2 exist to replace it with
labels derived from timing truth. **Moot 2026-09-18:** no shipped code
applies it now that the fetch is out of the pipeline.

## Part 2 — Target

What the locked rulings specify. ~~Source of truth is **Appendix A** (route
contract) and **Appendix D** (aligner + post-pass policy) in
`plans/completed/ctc-sync-engine.md`; both are locked. This section is a reading of
those, not a second spec — if the two disagree, the appendices win.~~
**Since the 2026-09-18 consolidation pass, this section is the source of
truth.** The build plan is closed, so its Appendices A and D survive only
as record. Every live ruling they held is carried below.

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
                                                whisper (GATE J1
                                                NO-GO 2026-09-08)
```

**Target as of 2026-09-08 (Ken): routes 1 and 4 only.** Route 2 closed
2026-09-04 (R-4) and route 3 was withdrawn 2026-09-08 — S-1 withdrawn,
work ceased, F2 never built. Fetched timing (word or line sidecar,
`.lrc`) reaches production through one door: the joint route's gated
fill, which stays **LRCLIB-only** — the widening to the sidecar sources
was refused 2026-09-11 (`route-no-timing.md`, Phase 5, GATE G NO-GO), so
that door is open for LRCLIB and shut for the fetch sidecar. Per-song
admission gates on fetched timing are retired twice over (R-4; the warp
gate's verified blind spot), so timing enters per line and loses per
line.

**Display text:** every route renders the Genius sheet, as today. (The
word route would have rendered provider text; it is closed.)

**Failure containment:** every fetch/verify/warp/score failure degrades
one route, never fails the song. With the network down, a song processes
exactly as it does today.

### What changes vs. shipped

| | Shipped | Target |
| --- | --- | --- |
| Routes | 2 (+transcribe) | **2** (+transcribe) — F1 closed 2026-09-04, F2 withdrawn 2026-09-08 |
| Line timing, no SRT | joint DP; LRCLIB as post-pass fill | **same — unchanged** (GATE G NO-GO 2026-09-11; fill not widened, per-song gate kept) |
| Word timing | nothing — sidecar unused for routing | **nothing — unchanged** (the fill-source door was tried and refused at GATE G) |
| Synced-timing fetch (Musixmatch/NetEase sidecar) | **none** — taken out of the pipeline 2026-09-18 (`efd3559`); it ran at add time and nothing read its output | **none** (Ken, 2026-09-18, consolidation pass). Probes fetch on demand via `scripts/timing_fetch.py` |
| De-reverb retry | transcribe-side gate, every route | **same — unchanged** (its retirement was a build-plan E4 review; E4 never runs) |
| Non-Latin lines | whisper path, as every line | **same** — GATE L (`route-no-timing.md`) is the only open question, re-posed against whisper |
| Scaffold aligner | n/a | n/a — route withdrawn; M6-d moot |
| Joint aligner | whisper align | **whisper align — unchanged** (GATE J1 NO-GO 2026-09-08; CTC not adopted) |
| Word boundaries inside a placed line | joint matcher's words | **same — unchanged** (GATE W closed 2026-09-15, Ken: interior refinement not adopted) |
| Evidence veto | joint route | joint route only (unchanged) |
| LRCLIB fill | joint route | joint route; **kept** — refit Phase 1.1 cancelled 2026-09-08 |
| Lyric text into the aligner | source text as fetched — an all-caps caption stays in capitals; Cyrillic watermark lookalikes (from Genius, and some captions) and primes pass through to whisper | **normalized at ingest** (Ken, 2026-09-21; `5f81ac0`..`587fe1a`, copied from `dev`): an all-caps caption is recased to sentence case; watermark lookalikes are folded, line-aware so real Cyrillic is untouched; primes read as apostrophes. **On the SRT route the caption text is both the aligner's input and the karaoke's word text, so any display edit is a timing change.** Recasing Someone You Loved moved 27 of 63 lines by >0.15 s, against 2 of 63 for a plain rerun of the old code; every line placed by the aligner in both. Ken eyeballed it and ruled the recased timing tighter |

### Target demotion gates

Snap policy is settled; the word-route verify is retired; the warp gate
is moot as of 2026-09-08; `map_rate` stays as the fetch-time wrong-song
check only.

| Gate | Decides | Status |
| --- | --- | --- |
| `map_rate` at fetch (`WRONG_SONG_MAP_RATE`) | whether a sidecar is admitted at all | **adequate for wrong-song** (M2: 32/32 cross-paired controls collapse at the text-pairing floor). **Wrong-*edit*: M7-a asked it directly 2026-09-08 and the evidence says `map_rate` does not catch it** — all 17 cohort sidecars cleared the floor, yet only 4 track our recording; on Let It Go the text agrees 1.00 against a sidecar spanning 117 s of a 201 s video. Raw tables in `route-line-timing.md`. **Ruling is Ken's; no gate has been changed.** **Moot 2026-09-18:** nothing fetches a sidecar in production any more. |
| ~~Word-route verify (Appendix C)~~ | ~~precedence 2 vs demotion to 3~~ | **RETIRED 2026-09-04 (R-4 closed)** — no per-song gate is constructible from this evidence family; demotion to 3 is permanent |
| Warp gate (`WARP_MIN_ANCHORS` 5 / `WARP_MAD_GATE_S` 2.0 s) | precedence 3 vs fall to 4 | **moot 2026-09-08** — route withdrawn. Its verified blind spot (fit population excludes unsung sections; duration clamp crams) is on record in `route-line-timing.md`; do not reuse it as a per-song admission test |
| Snap policy (Appendix D) | post-pass per route | locked: OFF on CTC-timed routes, ON on whisper-timed; "re-enable exception: none". **Unchanged by GATE J2 (2026-09-08): neither population cleared, and with J1 NO-GO no CTC-timed route survives, so the carve-out is inert until one does.** ~~Ken owes one ruling before Appendices C/D/E re-lock — J2's burden and D's burden point opposite ways~~ **Ruled 2026-09-10 (Ken, `f3d7f91`): a scope mismatch, not a conflict; the snap stays on every shipped route. The OFF clause is dormant, and the 2026-09-18 consolidation pass closed the appendix as record** |

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
- ~~**GATE J1/J2**~~ — **BOTH READ OFF 2026-09-08 (Fable), NO-GO.**
  Phase 2a ran the offline A/B; CTC is not adopted in the joint
  matcher, so precedence 4's aligner stays whisper, Phase 2b is skipped
  entirely and GATE V never fires. J2 cleared neither CTC-won nor
  transcribe/ytasr-won lines, so **Appendix D's snap exception does not
  move.** The mechanism on record: whisper fails on unsung sheet text
  by collapsing to zero width, which the align-pace guard reads,
  while CTC cannot abstain and instead crams or smears those tokens —
  invisible to that guard. Detail and the eyeball list in
  `route-no-timing.md`. ~~**One item stays open and is Ken's:** J2's
  burden ("retire iff ~zero") points opposite to Appendix D's ("OFF
  unless a named fix"), and that must be settled before Appendices
  C/D/E are re-locked.~~ **RESOLVED 2026-09-10 (Ken) — by scope, not
  by burden.** See the entry below.
- **GATE L** — non-Latin form. Re-homed 2026-09-08 to the joint route's
  aligner, which J1 settled the same day as **whisper**; additive,
  blocks nothing but the Mandarin corpus. Note the read-off's rider:
  with whisper retained, the romanized-form question loses its MMS_FA
  motivation for this route and is worth re-posing when the corpus
  exists.
- ~~**GATE G**~~ — **READ AND CLOSED 2026-09-11: NO-GO.** The gated
  fill is **not** widened to the fetch sidecar and the per-gap gate does
  not ship, neither as a guard on the widened source nor alone on
  LRCLIB. **Phase 5 ended with no production change.** Every cell lost
  or moved fills the shipped path already produces, so the bar failed
  before quality was reached and the eyeball was never used. Two defects
  in the pre-registration made it unwinnable as written — the envelope
  rule was specified to refuse Domino while Domino is one of the 16
  fills that had to survive, and the claim that the per-gap gate "only
  ever removes" fills is false, since it also re-places them. **Do not
  re-open by amending Phase 5**; a re-attempt needs a survival bar that
  does not contain its own counterexample — a fresh design pass and a
  fresh letter — **and it must argue it would do better than a wash**,
  because Ken eyeballed every fill the per-gap cells move and called the
  placement no better than the shipped one. That settles the read-off's
  one residual uncertainty, so **no Fable round is owed on this gate**.
  Read off by Opus, **ratified by Ken**; full entry in
  `route-no-timing.md`.
- ~~**GATE W**~~ — **CLOSED 2026-09-15 (Ken) at step 2: no production
  change, no GPU pass spent.** Designed 2026-09-14 (Opus); step 1
  RAN and was READ the same day — no kill rule fired, both arms proceed.
  Step 2 RAN and was READ 2026-09-15 — W-2a did not fire, W-2b did:
  Ken's blind looks found target interiors clearly off 3 of 20 against
  the align-won controls' 0 of 8, a gap inside W-2b's 0.20. **Ken called
  it a wash and closed the phase rather than re-pose it.** Word
  boundaries inside a line stay as shipped; neither CTC nor the
  zero-model form is adopted. A re-attempt needs a fresh design and
  letter, and must argue it beats a wash.
  Phase 6's gate: does refining word boundaries *inside* an already
  placed line beat what ships today. Four pre-registered steps, each
  with a kill rule, and **the two cheapest come first on purpose** —
  step 1 prices a zero-model competitor already sitting in the
  bundles and can retire the second model outright (**it did not**:
  whisper agrees on under half the target lines, so the zero-model
  form goes forward as its own step-4 stratum beside CTC, not instead
  of it), step 2 asks Ken
  whether the defect is visible at all and can end the phase before
  a GPU runs (**it did not end it, but its control check fired**:
  the gap between target and control looks was too small to
  say the phase points at its own population, so the design handed the
  framing back to Ken, who closed it). What it cannot do: change which line renders, touch
  line edges (the snap owns those, Ken 2026-09-10), or re-open GATE
  J1 — this runs strictly after selection. Price if it ships,
  stated before the spend: a milestone bump and a full-library
  regen, since rendered word timing changes. Design in
  `route-no-timing.md` Phase 6.
- **R-3** — SRT-first *stands*, but Appendix A flags that a later ruling
  could reorder precedence 1 against 2.
- ~~**GATE T**~~ — **READ 2026-09-10. The `alpha`/`beta` knobs stay at
  their shipped 2.0 / 2.0; no config default moved and no commit
  carries a knob change.** Phase 3's grid is inert on this corpus: 7
  placed lines move across all 15 points, every song above 90% coverage
  is identical at every point, and 13 of the 14 non-baseline points
  regress at least one song. The hard criterion therefore cannot fail,
  which also retired the clean-tail-roster prerequisite the run entry
  had flagged. **Provenance: assessment by Claude Opus 5 at Ken's
  request (Fable credits short), ruling by Ken — not a Fable round.**
  **The ytasr candidate ratio closed the same day and is the phase's one
  production change:** `ytasr.CANDIDATE_MAX_EDIT_RATIO` ships at **0.45**
  (was 0.34). It is strictly dominant on the tables (+2 placed, nothing
  regressed on any song on any hard metric) *and* Ken eyeballed the two
  lines it adds — both required, because the harness cannot tell a
  correct new line from a wrong one that merely fails to crawl or
  overlap. 0.55 was measured and rejected: two more lines, but a crawl
  line and a 0.7 s overlap with them. The value stays a module constant
  rather than moving to `PipelineConfig` — nothing sets it per song, and
  the drivers that sweep it override it module-side. **Flagged, not
  fixed:** the ratio is absent from the bundle's recorded
  `joint_stats.knobs`, so a bundle cannot say which ratio produced it;
  adding it wants its own change.
- ~~**Phase 5's gate form**~~ — **SETTLED 2026-09-11 at GATE G: the
  per-gap gate does not ship and the fill keeps its per-song gate.**
  The question was real — a global offset+slope fit never sees the
  unsung sections, and the "never overrides a placed line" cap does not
  cover a run of *unplaced* lines after a structural discrepancy on a
  song that passes the gate — but the probe could not answer it,
  because the pre-registered survival bar contained a counterexample to
  its own mechanism. **What the run did settle:** the sidecar widening
  is refused; Bloodstream (the named risk case) was held by the shipped
  energy check in every cell, not by anything new; and on Ken's eyeball
  the per-gap placement is **a wash** against the shipped one wherever
  the two differ, so the mechanism bought nothing even where it applied.
  Detail in `route-no-timing.md` Phase 5 and its GATE G entry.
- **The DP ban** — assessed 2026-09-10, **still Ken's and unchanged**.
  The same round priced sidecar-as-DP-candidate as structurally dead
  (redundant with the transcribe candidate that already exists where a
  line is sung; wins only by being wider, which displaces an
  audio-placed line; stripped by the second pass as uncorroborated;
  the agreement-term variant tips repeated-text disambiguation toward
  the sidecar's edit). Two arguments previously offered for the ban are
  **withdrawn as wrong** and should not be re-used: that the DP would
  show a confidently-wrong line (it scores zero and never enters the
  chain — a DP candidate has a drop branch by construction), and that
  per-line detection is harder than per-song (it is easier; the
  sidecar simply carries no audio evidence for it to adjudicate).
- **Phase 6's letter** — NEW 2026-09-10, Ken's. Interior-only is the
  pre-registered default. Its **endpoint** form is not merely blocked
  but incoherent under the snap ruling below: if the snap permanently
  owns line edges, endpoint refinement is a second mechanism fighting
  it over the same values. ~~Letter still unassigned.~~ **Assigned GATE
  W 2026-09-14; closed 2026-09-15 (Ken) — see GATE W above.**

~~**J2 vs Appendix D.**~~ **RESOLVED 2026-09-10 — Ken's ruling: the
edge snap stays.** The two rules were never in genuine conflict; they
have different *scopes*. Appendix D disables the snap **on CTC-timed
routes** (and in the same clause says whisper-timed routes keep it).
**Phase 6 does not create a CTC-timed route** — whisper places every
line and CTC only adjusts word boundaries inside the subset that passes
the disagreement band, so the OFF clause never reaches the joint lane
and the whisper-timed clause does. Ken's reasoning, which is the part
to keep: **a post-pass that does not cover the whole song cannot retire
a mechanism that does.** The snap is still needed for align-won lines,
interpolated lines, filled lines, band-rejected lines, every song CTC
never runs on, and the whole SRT route.

Consequences: (1) **the snap owns line edges, always, unchanged**, and
CTC owns word boundaries strictly inside a line — the two never touch
the same numbers, so **no per-line snap exception is needed anywhere**
(Phase 6 closed 2026-09-15 without shipping, so nothing adjusts
interior boundaries today; the snap half of this stands unchanged);
(2) Appendix D's locked snap clause **does not move** and never had to;
(3) J2 is moot on this lane *permanently*, not just "today" as the
read-off put it, because nothing on the roadmap restores whole-song CTC
coverage here; (4) Appendices C/D/E are no longer gated on this item —
though the re-lock still has to happen and Appendix D's **other**
locked decisions (the de-reverb retry retirement among them) are
untouched by this ruling. **The OFF clause is dormant, not wrong:** it
wakes up if any route is ever genuinely CTC-timed end to end. None
exists and none is planned (CTC was rejected on the SRT path at S-2).

Not open, do not re-litigate: engine branch E1–E4 is **OFF** (GATE O =
O-GRAY); no section-level DP (GATE P); densify rejected (S-3); CTC
rejected on the SRT path (S-2, SRT arm); **CTC in the joint matcher
(GATE J1 NO-GO 2026-09-08 — the S-3 rider is unexercised, not
withdrawn; a re-attempt needs an abstention mechanism pre-registered
before it runs, never the same probe again)**; **CTC as a fourth DP
peer** (2026-09-10 — same abstention defect as J1, plus the joint
score being monotone in candidate width, so CTC's tighter windows lose
clean lines to coarser sources; advisory, tie-break and width-only
variants assessed and rejected with it); the line route itself (S-1
withdrawn 2026-09-08 — re-open only with a per-line design, never with a
per-song gate).

**Scope rider on the J1 NO-GO (2026-09-10).** J1 settled CTC as a
*witness that decides where a line goes*. It did not settle CTC as a
**post-selection timing refinement** on spans the matcher has already
placed — a different question, because abstention is a selection
problem and a slice cannot smear outside its window. That form is
`route-no-timing.md` Phase 6, **designed 2026-09-14 and gated as
GATE W**. Citing J1 against it is a misreading; the live objections to
it are S-C's within-window ensemble failure, the absence of an interior
reference, and a zero-model competitor already in the bundles — and
the design answers each rather than arguing past it: the ensemble
songs are a veto stratum, the eye is named as the only interior
reference there is, and the zero-model competitor is priced at step 1
where it could retire the second model before a GPU runs. **Priced
2026-09-14, and it does not:** it covers under half the target lines,
so it proceeds alongside CTC rather than replacing it. **Phase 6 then
closed 2026-09-15 at step 2 (Ken: a wash), so neither form ships.**
This rider still stands as the reason J1 must not be cited against a
future interior-refinement design.

## Which file owns what

| File | Owns |
| --- | --- |
| `PROGRAM.md` | this map, sequencing, ground rules, model switching |
| `GLOSSARY.md` | ASS/CTC/MMS_FA/emission/melisma/richsync — read before guessing at an acronym |
| `route-word-timing.md` | rung 1 (**CLOSED 2026-09-04**); GATE R, R-1 ruling, M1-M5, the R-4 closure |
| `route-srt.md` | rung 2a; the shipped cue-align route, S-C |
| `route-line-timing.md` | rung 2b (**CLOSED 2026-09-08** — S-1 withdrawn); GATE S scaffold arms, M6, M7, the fallback; GATE L re-homed to rung 3 |
| `route-no-timing.md` | rung 3 — **the live build lane**; the joint catch-all refit, GATE P/J1/J2/T, Phase 5 + **GATE G** (CLOSED 2026-09-11, NO-GO — fill not widened), **Phase 7 + 7b (RAN + READ 2026-09-14 — the unplaced population is CLOSED: ~2 winnable lines corpus-wide)**, **Phase 6 + GATE W (CLOSED 2026-09-15 at step 2, Ken — a wash; no production change)**, GATE L |
| `shared-aligner-form.md` | GATE C, GATE O, Phase 0 harness, ruling-provenance audit |
| `completed/ctc-sync-engine.md` | build phases + appendices — **CLOSED 2026-09-18** by the consolidation pass: nothing left to build; only E0 was ever built, and it is out of the pipeline |
| `edge-snap-coverage-accuracy.md` | the edge snap post-pass track, **not a routing lane**: onset silence gate, one-word lines, stem-end and end-reference fixes, interior run edges — **Phases 0-5 and 5.1 accepted 2026-09-18**; production code goes to Ken's user-test branch before `master`. Phase 6 NOT PINNED (Ken's call); Phase 7 studies gated |
| `completed/` | closed plans, kept for their Results logs |

Rule of thumb: **a probe belongs to a lane if its outcome changes what
happens for one timing source only.** If it changes the aligner or the
architecture for every source, it is cross-cutting and belongs in
`shared-aligner-form.md`.

## Branch lineage

`master` (upstream) → `fable_matcher_refine` (= `musix_ctc`) →
`timing_pillars` → **`joint_catchall_refit`** (current). `pathed_align`
holds the pre-port scaffold-warp history; its machinery ~~is now ported into
shipped `cue_align.py`, so it is not dead-end history~~ moved out of
`cue_align.py` to `scripts/scaffold_warp.py` on 2026-09-18, because the
production path never called it.

**Since 2026-09-15:** `joint_catchall_refit` → **`edge_snap_refine`**
(the edge snap track plus the consolidation pass). Production lands on
`master` by Ken's 2026-09-18 ruling:
- the development commits are replayed in order, with `plans/` and the
  probe scripts filtered out, not squashed;
- the replay goes to a test branch first, for Ken to user-test before
  `master`;
- the full history stays on `edge_snap_refine`.

## Remaining execution order (Ken, 2026-09-01) — measure first, lock once

> **START HERE (2026-09-10, updated after GATE T was read).** The
> line route is closed (step 4) and **GATE J1 came back NO-GO**, so
> whisper stays the joint aligner and Phase 2b never gets built.
> **Phase 3 ran and GATE T was read and closed the same day: the matcher
> knobs are inert on this corpus and stay at their shipped values. One
> production change came out of it — the ytasr candidate ratio at 0.45,
> eyeballed and shipped.**
> **Phase 5 is CLOSED 2026-09-11 — GATE G is NO-GO.** It was designed
> 2026-09-10 (Opus), built and run 2026-09-11 (Sonnet), read off and
> ratified the same day. The gated fill stays exactly as shipped: LRCLIB
> cue source, per-song gate. The fetch sidecar does not become a fill
> source, the per-gap gate does not ship, and **the phase ends with no
> production change**. The gate was unwinnable as pre-registered (two
> design defects, recorded at the gate), so this is not the corpus
> ruling against the per-gap idea — but **do not re-open it by amending
> Phase 5**: that needs a fresh design pass and a fresh letter.
> ~~**Phase 6 is now the head of the queue.**~~ **Phase 6**
> (CTC post-selection *interior* refinement) was added the same day as
> design owed; GATE T no longer gates it, but it stays **after Phase 5**
> on value — it refines word boundaries inside lines already placed,
> ~~which is polish next to the ~150 sheet lines that never render~~.
> **That comparison is dead as of 2026-09-14: Phase 7 + 7b measured
> the unreached population and it holds about two winnable lines, so
> GATE W is the better target on evidence, not merely what is left.**
> It is not GATE J1's question and does not re-open it. **Phase 6's
> gate letter is GATE W (assigned 2026-09-14).** **Phase 6 CLOSED
> 2026-09-15 (Ken) at GATE W step 2 — a wash, no production change.
> No measurement phase is live now: what remains is GATE L (blocked on
> the Mandarin corpus) and the design-consolidation pass.** **The
> consolidation pass ran 2026-09-18 (see below), so only GATE L is left.**
> Outside the routing program, the edge snap track
> (`edge-snap-coverage-accuracy.md`) ~~is live as of 2026-09-15: refreshed,
> not started~~ has Phases 0-5.1 accepted as of 2026-09-18.

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
5. ~~**Joint plan Phase 2a → GATE J1/J2**~~ — **RAN AND CLOSED
   2026-09-08. J1 NO-GO, J2 cleared nothing.** Whisper stays the joint
   aligner; Appendix D unchanged ("re-enable exception: none" stands).
   **2b and GATE V are struck.** **This step is now CLOSED: Phase 3 ran
   2026-09-10 and GATE T was read and closed the same day — the matcher
   knobs are inert on this corpus and stay at their shipped values; the
   phase's one production change is the ytasr candidate ratio at 0.45.**
   Raw tables and both read-offs in `route-no-timing.md`. What remains
   of the step was **Phase 5 (line timing as a fill source)**, and that
   recommendation was taken: designed 2026-09-10, built and run
   2026-09-11, **GATE G read and ratified NO-GO the same day**. The fill
   is unchanged and the step is now closed entirely. Phase 3's
   recommendation that the next spend go to the unplaced population
   **was tried and did not land** — the ~150 sheet lines that never get
   words are still unreached, and no mechanism on file reaches them.
   **Phase 7 ran and was read 2026-09-14, and it changes this
   paragraph's premise.** Of those ~150 lines, **70 (47%) are text
   that appears in no transcription of the audio** — closed
   permanently; no design pass from any model reaches them. The
   other 80 are present in the audio somewhere, but the probe
   cannot tell *present at this line's position* from *present
   only at another occurrence of the same repeated text*, and the
   evidence leans toward the latter (the concentrations sit on the
   songs GATE P already diagnosed as repeat pile-up). **So: stop
   quoting ~150 as the unreached population.** Ken commissioned the
   follow-up the same day as **Phase 7b**, and **it ran and was read
   2026-09-14: the matter is CLOSED.** Of the 80, essentially all
   are text sung *somewhere other than where the sheet puts them*,
   which the matcher is correct to refuse; **two lines corpus-wide**
   are found in the gap where they belong, against a band of 20
   declared before the data. **Spend nothing further there — no
   design pass, no Fable credits, no third probe.** If ever
   reopened, the lever is upstream and was named at GATE P: a
   lyrics sheet that matches the recording. Nothing inside the
   matcher reaches this. Detail, the resolved STOP and two recorded
   design defects are in `route-no-timing.md`'s Results log.
   ~~**Live now: Phase 6 → GATE W**~~ (designed 2026-09-14) — interior
   word boundaries on lines already placed. Phase 7 and 7b ran first
   precisely to test whether something better existed to aim at.
   **They found there is not**, which promoted GATE W from "what is
   left" to the best available target on measured evidence. **Step 1
   was read 2026-09-14: no kill rule fired, both arms proceed. Step 2
   was read 2026-09-15: W-2b fired, STOP → Ken. Ken closed Phase 6 the
   same day as a wash: no GPU pass, no production change.**
6. ~~**S-E**~~ — **not run.** This is the *line* route's Phase 3
   optional arm, not the joint plan's Phase 3, and it closed with that
   route: `route-line-timing.md`'s status block records "S-E is not
   run" among what Ken's 2026-09-08 closure settled. Struck here
   2026-09-10 as bookkeeping on that ruling, not a new decision. Its
   original scope: an offline, no-GPU-align arm informing the deletion
   inventory and testing Ken's GATE C observation.
7. **Phase 4 → GATE L** — whenever the Mandarin corpus exists. Blocks
   nothing and nothing blocks it but the corpus.

Then **one design-consolidation pass**: re-lock the build plan's
Appendices C, D and E with the real constants in a single revision.
**DONE 2026-09-18 — see the entry below.**

### Design-consolidation pass (Opus, 2026-09-18; commissioned by Ken)

**Outcome: there was nothing left to re-lock, so the build plan closed.**
Each appendix governed a build that will not happen:
- C, the word-route verify, was retired at R-4.
- D's scaffold route was withdrawn at S-1, and its CTC-timed post-pass
  policy has no route to apply to.
- E's engine was OFF from GATE O, and CTC then lost both aligner seats
  (S-C, GATE J1).

Filling constants into procedures that cannot fire would be bookkeeping
with no reader. `ctc-sync-engine.md` moves to `completed/` with a closing
block that says what became of each part, and Part 2 above becomes the
source of truth.

**What the pass carried forward** (all already shipped behaviour; Part 2
now says so directly):
- **Routes 1 and 4 only:** SRT → cue-align, otherwise the joint matcher.
  Appendix A's precedences 2 and 3 never fire.
- **Snap ON on both shipped routes**, since both are whisper-timed. D's
  OFF-on-CTC clause is dormant, per Ken's 2026-09-10 scope ruling.
- **De-reverb unchanged on every route.** Its retirement lived only in
  E4's deletion review.
- **Non-Latin lines take the whisper path.** GATE L stays in
  `route-no-timing.md`, already re-posed against whisper at J1. D's
  non-Latin bullet and E's alignment-form amendment go with the closed
  plan.
- **The build plan's deletion inventory is void.** Veto, windowed
  realign, the joint DP, the snap, de-reverb and the LRCLIB fill all
  stay.

**What the pass removed from production (Ken, 2026-09-18):**
- **The synced-timing fetch (E0, `efd3559`).** It ran on every Genius
  song at add time, with several 2.5 s politeness pauses and 20 s on a
  401. It wrote a sidecar nothing read: its intended readers were the
  word route (closed), the line route (withdrawn) and the fill widening
  (GATE G NO-GO). The module moved to `scripts/timing_fetch.py`, where
  the Musixmatch batch probe still uses it.
- **The line-route warp helpers (`28a118d`).** They moved from
  `cue_align` to `scripts/scaffold_warp.py`. The production SRT path
  never reached them, and `cue_align`'s Theil-Sen copy duplicated the
  one the LRCLIB fill ships.

Neither change moves any song's timing output.

**Open item left by the pass (Ken's):** `pyproject.toml` and
`requirements.txt` still declare `syncedlyrics` as a runtime dependency.
Only probe scripts import it now. The edit is held because
`pyproject.toml` carries someone else's uncommitted changes.
**Resolved 2026-09-18 (`1f98dab`):** the uncommitted edits turned out to
be Ken's own manual yt-dlp bump. `syncedlyrics` moved to the dev
dependencies, and the stale lockfile was regenerated, keeping that bump.

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
  production implementation in `plans/completed/ctc-sync-engine.md`, built as a
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

Three roles, binding on this file and on every plan it maps.
**Revised 2026-09-10 (Ken): Opus owns design and verdicts; Fable leaves
the routine loop.** This section is now self-contained — it no longer
binds by reference to `plans/completed/matcher-accuracy-hardening.md`
§"Model switching", which stays as written because it is the record of
how the completed work was judged, not live policy.

- **Design** — Opus. The 2026-07-18 design (this document and the build
  plan's Appendices A–E) is locked, with every formerly lock-at-GATE
  item converted to a pre-registered decision procedure, and Opus owns
  design work from here. **Phase 6 was designed 2026-09-14 and gated
  as GATE W**, and closed by Ken 2026-09-15 at step 2. ~~**The one design item
  left is the consolidation pass** (re-lock Appendices C/D/E)~~ **The
  consolidation pass ran 2026-09-18 and closed the build plan; no design
  item is left**; GATE L
  waits on its corpus. Phase 5's per-gap gate
  closed at GATE G 2026-09-11. At each GATE the judge
  *executes* the relevant procedure verbatim and records the resulting
  constants; no model on any tier invents a threshold or extends a
  procedure — an uncovered case is a STOP → Ken.
- **Implement / prototype / run** — Sonnet 5. Output at a GATE is a
  table, never a verdict. **Unchanged: a Sonnet session stops when the
  artifacts exist** and asks Ken to `/model` to Opus; it does not read
  its own result.
- **Judge results** — Opus, executing the pre-registered read-off rules
  below. Opus renders the verdict on every result, GATEs included.

### When a result goes to Fable (revised by Ken, 2026-09-10)

One trigger, and it is Opus's own uncertainty. When Opus cannot resolve
a read against the pre-registered rule — the findings admit more than
one reading it cannot choose between, or something surfaced during the
run that it cannot price — it says so plainly and **suggests** Ken
escalate to Fable. That is a recommendation to Ken, never a switch Opus
takes itself, and it is the only path to Fable.

Two rules from the 2026-09-04 version are retired:

- **GATEs no longer escalate on principle.** A GATE Opus can read, Opus
  reads. Difficulty is the only thing that routes a read-off now.
- **The direct-to-Ken shortcut is gone.** Every result gets an Opus
  round, including arithmetically decisive ones — the round no longer
  costs a billed pass, so there is nothing to save by skipping it.

Judge separation is unchanged and still binds: the executor reports
paths and raw tables and does not write the verdict; Ken rules on top
of every verdict Opus renders. Ken asking directly for an opinion is
not an escalation.

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
| 3 (scaffold probe, GATE S) | below; Appendices D/E lock at the GATE | Sonnet 5 | Opus (suggests Fable only if the conflicting arms leave it unsure) |
| 4 (non-Latin form, GATE L) | below; Appendix D's carve-out amends at L-3 | Sonnet 5 | Opus + Ken eyeball |

Phase dependencies: 1b, 2, 3 can interleave; 1b should complete before
2b (its scores feed 2b's verification stats) and before 3's S-B2 arm.
Phase 4 (GATE L) depends on nothing but its own Mandarin corpus (Ken's
action) and blocks nothing; "Remaining execution order" below sequences
it against the joint plan's probes.
Build phases in `plans/completed/ctc-sync-engine.md` consume these GATEs per its
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
