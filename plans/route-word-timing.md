Model: Claude Fable 5 (design); executors per the phase table in `plans/PROGRAM.md`

# Route: word timing (Musixmatch richsync)

**Ladder rung 1.** A provider sidecar carries per-word timings; the route
verifies them against audio evidence and renders the `.ass` from the
provider's own words and text, with no lyric matching.

**Status: NO-GO as the route stands (Ken, 2026-09-03) — not shipped, not
wired.** The ruling splits in two, and the halves have different futures:

- **The mechanism is GO on evidence.** Warping provider word timings and
  rendering them produces usable karaoke on 6 of 10 songs Ken eyeballed
  (4 clean, 2 singable); Colors of the Wind beat production output. All
  four failures trace to the sidecar or the fit — a wrong recording, an
  edit mismatch, a coverage hole — none to warping-and-rendering.
- **The route cannot ship.** It exists only behind a verify gate,
  Appendix C could not assemble one (R-4), and 4 of 14 sidecars would
  render wrong without it.

**Consequence, already in effect:** word sidecars demote to the
line-source pool and their `ts`/`te` keep improving scaffold ends — see
`plans/route-line-timing.md`. That demotion is existing routing
behaviour, so the ruling required no code change.

**Reversal condition:** a re-specified Appendix C that passes. This is
not a judgment that richsync word timing is unusable; it is a judgment
that good sidecars cannot yet be told from bad ones automatically. The
measurements that would reverse it are M1-M5, commissioned below.

**Open work:** R-4 (the verify criterion) and M1-M5. Sequencing lives in
`plans/PROGRAM.md`.

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
   in `plans/completed/ctc-forced-align-eyeball.md` §"Line grouping → ASS"
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


## Results log

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
  for STOP item 2. *Specification ratified 2026-09-04.* ***CLOSED
  2026-09-04: NOT VALIDATED*** — no separation at the primary tolerance,
  and no second attempt (see the R-4 closure at the end of this log).*
- **M2 — build real negative controls** by cross-pairing sidecars
  against other songs' media. Guaranteed wrong-song, no fetches, and
  many rather than 2 — which also retires the n=2 fragility behind
  every threshold. Produces the evidence for STOP item 1. *Specification
  ratified 2026-09-04.* ***CLOSED 2026-09-04*** — 32/32 collapse at the
  text-pairing floor; nothing reaches the residual family. Positive
  finding: this validates `WRONG_SONG_MAP_RATE` for wrong-song.
- ~~**M3 — re-run Appendix C's general rule** on M1's labels with M2's
  controls.~~ ***CLOSED 2026-09-04 by inspection, not run*** — zero of
  the three general-rule statistics separate Ken's labels, and M3 had
  neither a validated labeller nor a control that reaches a fit. The
  eyeball entry's analysis 1 is upheld: the residual statistics measure
  the pairing, not the render.
- **M4 — per-section pairing-coverage detector** for the
  edit/structure-mismatch class (STOP item 5). Domino and Popular are
  the known positives, the four clean songs the known negatives.
  *Re-homed 2026-09-04 to F2's warp gate — its rung-1 consumer is
  closed. Still held; its positives do not decay.*
- **M5 (small) — check whether the "slightly rushed" sweeps are
  `cue_align.MAX_WORD_DUR_S` (1.5 s) truncating sustained notes.** If
  so it is a one-constant fix rather than a design problem.
  ***CLOSED 2026-09-04: REFUTED*** — the constant does not move; see the
  M5 entry at the end of this log. The "rushed" class stays unexplained
  and now bears on M1's labelling rule.
- **M6 — re-read S-2's genius arm against the S-C reframe.** Added
  2026-09-04 by the eyeball-provenance audit, which lives in
  `plans/shared-aligner-form.md`; see that entry for the evidence and the
  sequencing constraint (after M1-M3, before any F2 build).

**Held, not commissioned:** STOP items 3 (outlier denominator) and 4
(MAD-threshold population). If the eyeball entry's analysis 1 survives
M3, both dissolve rather than resolve — a statistic that reads the
wrong thing is dropped, not tuned. STOP item 6 (arm (iv) rebuild) stays
deferred behind R-4.

### 2026-09-04 — M5 run and ruled (Ken) — `MAX_WORD_DUR_S` refuted as the cause of the "rushed" sweeps

**(Executor tables, then Ken's ruling on them in the same turn. M5 was
commissioned as a single sentence in the R-1 ruling above, so it carried
no pre-registered read-off rule. Ken ruled directly rather than spending a
judge round — see `plans/PROGRAM.md` §"When a result goes to Fable".)**

**The hypothesis.** Arm (i) caps every warped provider word sweep at
`cue_align.MAX_WORD_DUR_S = 1.5 s` (scratchpad `p2b_render.py:59`; the
constant is `pikaraoke/lib/cue_align.py:80`). If that cap were truncating
sustained notes, it would explain the "slightly rushed but still singable"
defect Ken reported on More Than That and Like I Love You, and the repair
would be one constant. Note `ytasr.MAX_WORD_DUR_S = 2.0` is an unrelated
knob on the joint route; a grep hits both.

**Artifacts** — scratchpad `afed60c3-…/scratchpad/m5/`: `m5_probe.py` +
`m5_truncation.txt`, `m5b_probe.py` + `m5b_coverage.txt`, `m5c_probe.py` +
`m5c_events.txt`. All three are CPU-only, reading `p2b/verify_fit.json`
for each song's fitted slope and the provider sidecars from
`lyrics/*.timing.json`.

**Table 1 — truncation rate, all 16 cohort songs.** Fraction of provider
words whose *warped* duration exceeds the 1.5 s cap, with duration
percentiles. Sorted by rate.

```
song                                words  trunc% med_dur  p90dur  maxdur
Backstreet Boys - Incomplete (Offi    101    8.9%    0.26    1.49   30.20
The Lion King - Can You Feel The L    188    5.9%    0.17    1.23   14.41
Idina Menzel - Let It Go (from Fro    276    5.1%    0.21    0.93    8.01
Ed Sheeran - Best Part Of Me (feat    265    3.8%    0.35    0.94    3.03
Seasons of Love (HD)---UvyHuse6buY    255    3.5%    0.03    0.78    4.57
Jodi Benson - Part of Your World (    246    2.4%    0.19    0.76    9.95
'Popular' - Wicked 20th Anniversar    328    2.1%    0.15    0.70    7.31
Justin Timberlake - Mirrors (Offic    996    1.4%    0.13    0.48    3.49
'Free' _ Official Lyric Video _ So    381    1.3%    0.14    0.48    5.44
Justin Timberlake - Like I Love Yo    593    1.2%    0.12    0.43    3.44
Backstreet Boys - More Than That--    282    1.1%    0.23    0.75    1.68
Beauty and the Beast (1991) - Bell    623    0.6%    0.16    0.52    1.84
Pocahontas - Colors of the Wind (B    312    0.6%    0.26    0.73    3.08
Jessie J - Domino (Official Video)    402    0.0%    0.17    0.52    1.33
Justin Timberlake - Rock Your Body    604    0.0%    0.17    0.31    0.72
Justin Timberlake - Selfish (Offic    485    0.0%    0.19    0.50    1.41
```

**Table 2 — sweep coverage, the 10 eyeballed songs.** Fraction of each
provider line's span covered by its capped word sweeps, and the median
tail gap between the last word's end and the line end. *Provenance note:
this probe was written by the executor in service of interpreting Table 1,
and it joins probe output to Ken's eyeball labels — that is judge work
done at the executor's desk. It is recorded because it exists, not because
it was commissioned.*

```
label     song                           lines  med_cov mean_cov med_tail
bad       'Popular' - Wicked 20th Annive    61     0.63     0.61     0.00
bad       Ed Sheeran - Best Part Of Me (    39     0.83     0.82     0.00
bad       Jessie J - Domino (Official Vi    65     0.61     0.62     0.00
bad       Seasons of Love (HD)---UvyHuse    43     0.39     0.41     0.00
clean     'Free' _ Official Lyric Video     46     0.81     0.79     0.00
clean     Beauty and the Beast (1991) -    116     0.82     0.81     0.00
clean     Jodi Benson - Part of Your Wor    56     0.69     0.68     0.00
clean     Pocahontas - Colors of the Win    37     0.78     0.75     0.00
singable  Backstreet Boys - More Than Th    40     0.70     0.70     0.00
singable  Justin Timberlake - Like I Lov    81     0.82     0.81     0.00
```

**Table 3 — truncation events against the watched clips.** Tables 1 and 2
are whole-song aggregates and cannot say whether a capped word ever played
while Ken was looking, or how much sweep it lost. This one emits a row per
capped word in media time and intersects it with the clip windows recorded
in the R-1 eyeball entry above. `capd` = capped words in the song,
`in_clip` = those inside a watched window, cuts in seconds of lost sweep.

```
song                          capd in_clip max_cut sum_cut   worst cuts in clip (word @ media_t -Ns)
clean    Colors of the Wind      2       1    1.35    1.35   know @23s -1.3s
clean    Belle                   4       0    0.00    0.00   --
clean    Free                    5       1    0.76    0.76   free, @72s -0.8s
clean    Part of Your World      6       2    1.01    1.14   more @51s -1.0s; deal @48s -0.1s
singable More Than That          3       1    0.08    0.08   in @125s -0.1s
singable Like I Love You         7       3    0.24    0.29   chance @144s -0.2s; baby @98s -0.0s; you @120s -0.0s
bad      Best Part of Me        10       3    1.53    3.35   you, @206s -1.5s; Lately @212s -1.2s; Baby, @200s -0.6s
bad      Popular                 7       4    5.81   11.88   And @154s -5.8s; me! @199s -3.1s; clandestinely @177s -2.5s
bad      Domino                  0       0    0.00    0.00   --
bad      Seasons of Love         9       0    0.00    0.00   --
```

**Ruling (Ken) — M5 = REFUTED. `MAX_WORD_DUR_S` is not the cause, and it
does not move.** The evidence does not merely fail to support the
hypothesis, it points the other way, and Table 3 is what settles it. Inside
the windows Ken actually watched, the two songs he called rushed lost
**0.08 s** and **0.24 s** of sweep at worst. The songs he called *clean*
absorbed **1.35 s** (Colors of the Wind, the song he called perfect),
**1.01 s** and **0.76 s** in the windows he was watching, and he reported
nothing. A mechanism that produces a visible defect at 0.08 s while
passing unnoticed at 1.35 s is not the mechanism. The comparison carries
its own control, which is why it did not go to a judge.

**Table 1 alone could not have ruled this.** It is a whole-song rate, and
it left Like I Love You live: 7 capped words against a 3.44 s maximum
means some word loses ~1.9 s of sweep, which is a fair reading of "just a
few that seemed rushed". Only the per-event view shows those seven are
mostly outside the clip and the in-clip ones cost 0.24 s at most. Recorded
because the same shape of error — a rate standing in for the thing you
care about — is exactly what put R-4 in a STOP.

**What M5 does *not* close.** The "rushed" class remains unexplained. It
is a **sub-line** defect and, per the blind-spot note in the R-1 eyeball
entry above, no statistic in the 2b table can see it. Sweep coverage
(Table 2) does not separate the labels either: clean spans 0.69-0.82,
singable 0.70-0.82. No further probe is commissioned on it here.

**Consequence for M1 (flagged, not decided).** More Than That and Like I
Love You are 2 of the 10 validation labels M1 must reproduce. M5 removes
the render-artifact explanation for their "singable" grade, so whatever
"rushed" is, it is a property of the pairing or the fit — the same family
M1 is relabelling. M1's labelling rule has to state what it does with them
rather than inheriting "singable" unexamined.

**Observation, not interpreted.** Popular's cap truncates "And" at 154 s
by 5.81 s, inside the section Ken flagged at 2:30 as "a slow crawl", and
Popular carries the largest in-clip cut total in the cohort (11.88 s
across 4 words). Whether that is coincidence or the same underlying edit
mismatch is M4's question, not M5's.

### 2026-09-04 — M1 + M2 pre-registration (RATIFIED by Ken, before either run)

**(Executor draft, written before either measurement ran, and **ratified by
Ken as written on 2026-09-04** — so the read-off rules below were fixed in
version control while the numbers did not yet exist. Rationale: M5 was commissioned as one
sentence and the probe that actually answered it was not the probe that
sentence implied — the first table left the hypothesis live and only a
third, unplanned probe closed it. M1 and M2 feed R-4, which is the gate
itself, so their criteria are fixed in advance.)**

#### Ground rules for both

1. **One shot.** The procedure below is executed as written. If it fails its
   validation test, that is the result. The executor does not adjust the
   method and re-run. Any revision after numbers exist is a new
   pre-registration Ken ratifies.
2. **No post-hoc primary.** Where a tolerance has robustness columns, the
   primary is named here. A method that passes only at a non-primary
   tolerance is recorded as **not validated**, not as validated with a
   different constant.
3. **Executor boundary unchanged.** Both produce tables and saved artifacts.
   The verdict is Ken's, per `plans/PROGRAM.md` §"When a result goes to
   Fable".
4. **Artifacts** in the session scratchpad (`m1/`, `m2/`), never committed.

---

#### Finding that constrains M1 — the SRT corroboration arm is not available

STOP item 2 specified relabelling "by timing truth (transcribe/**SRT**
corroboration)". Checked before drafting, from each bundle's
`ground_truth_refs.youtube_srt_present`:

```
song                     ken       uploader_srt  was_lyric_source
Colors of the Wind       clean     False         False
Belle                    clean     False         False
Free                     clean     False         False
Part of Your World       clean     True          True
More Than That           singable  True          True
Like I Love You          singable  True          True
Best Part of Me          bad       False         False
Popular                  bad       False         False
Domino                   bad       False         False
Seasons of Love          bad       False         False
Rock Your Body           --        True          True
Let It Go                --        True          True
Mirrors                  --        True          True
Can You Feel the Love    --        True          True
Selfish                  --        True          True
Incomplete               --        True          True
```

Nine of sixteen carry an uploader SRT. The other seven have an `.srt` in
`pikaraoke-songs/subtitles/` **written by our own lyric-align stage** — the
sibling `.srt.generated` marker says "Generated by PiKaraoke's lyric-align
stage; not an uploader caption". Those are disqualified as reference: they
are our output.

**Consequence.** Of Ken's 10 eyeballed songs only 3 have an uploader SRT,
and **none of the 4 he called bad do**. An SRT-referenced labeller would
have zero negatives in the validation set and could not be validated at all.
So SRT is demoted from reference to spot-check on the 3 songs that have one,
and M1's reference is built from the transcribe stream. Recorded because
STOP item 2 named SRT as a co-equal source and it is not one here.

---

#### M1 — relabel the cohort by timing truth

**Question.** Does a per-line timing-truth labeller reproduce Ken's
usable/broken split? If yes, it labels the 6 un-eyeballed songs and M3 has
trustworthy labels. If no, M3 has no labels and R-4 stays blocked.

**Independence requirement (the point of the design).** M3 tests whether
Appendix C's cheap song-level statistics separate M1's labels. That is
circular if the labeller consumes those statistics. So the labeller **may
not** read any field of a `verify_fit.json` row except `slope` and
`offset_s`, and **may not** call `ytasr.cue_spans_for_lines` — the greedy
monotone pairing the eyeball entry's analysis 1 indicts.

**Why `slope`/`offset_s` are exempt, deliberately.** They come from that
same indicted pairing. They are used anyway because M1 grades **the render
Ken watched**, and arm (i) warps by exactly that fit. If the fit is wrong
the render is wrong and M1 should label it broken. What M1 must not do is
judge the fit by its own residuals; it judges the fit's *output* against an
outside reference. That is the whole distinction between M1 and the
statistics M3 will test.

**Reference onset, per provider line.** Global Needleman-Wunsch alignment
between the sidecar's normalized provider-word sequence and the bundle's
normalized `transcribe_words` sequence (match +1, mismatch -1, gap -1;
normalization via the existing `p1b.normalize_word`). A provider line's
reference onset is the media `start` of the earliest transcribe word aligned
to any of its tokens. Lines with no aligned token get no reference and are
counted separately as `unref`.

Global alignment is used rather than greedy first-match because greedy
latching onto the wrong repeat is the named failure. It is monotone, so it
*reduces* rather than eliminates repeat mis-latching; the 3-song SRT
spot-check is what would expose residual latching.

**Per-line rule.** Line L is `placed` iff
`|slope*L.ts + offset - ref_onset(L)| <= TOL`.
**Primary TOL = 0.5 s**, chosen on perceptual grounds (a line entering
within half a second reads as on time) and not from any measured value.
Robustness columns at **0.3 s** and **0.8 s**, declared now, never primary.

**Song statistic.** `placed_fraction` = placed / referenced lines, reported
with `ref_coverage` = referenced / total provider lines.

**Validation read-off (locked — Appendix C's own separation rule).** Let
U = Ken's usable six (Colors of the Wind, Belle, Free, Part of Your World,
More Than That, Like I Love You) and B = his broken four (Best Part of Me,
Popular, Domino, Seasons of Love).

- At **primary TOL only**: if `min(placed_fraction over U) >
  max(placed_fraction over B)`, the labeller is **VALIDATED** and its
  threshold is the midpoint of those two values.
- Otherwise **NOT VALIDATED**. Report the overlapping songs and their
  values. STOP -> Ken. Do not tune, do not re-run.
- On validation only, the 6 un-eyeballed songs receive labels from that
  threshold, marked `derived`.

**What M1 does with More Than That and Like I Love You** (the question M5's
ruling left open). Both are in **U**, and M1 is **binary — `usable` /
`broken`**. It is *not* asked to reproduce clean vs singable. M5 established
that the "rushed" defect is sub-line, and the eyeball entry's blind-spot note
records that no line-level statistic can see it; a line-onset labeller
therefore cannot separate singable from clean **by construction**. Grading
both `usable` is the correct outcome, not a lucky one. If either lands on the
broken side, that is a labeller failure and counts against validation — it is
not to be read afterwards as the labeller detecting the rushing.

**Outputs.** `m1/m1_probe.py`, `m1/m1_labels.txt` — one row per song:
`stem, video_id, ken_label, n_lines, ref_coverage, placed@0.3, placed@0.5,
placed@0.8, derived_label`. CPU only, no GPU, no fetches.

---

#### M2 — negative controls by cross-pairing

**Question.** With many guaranteed-wrong controls instead of two, which
Appendix C statistics still separate PASS from CONTROL?

**Construction (deterministic, no RNG).** Order the 16 songs by `video_id`.
For shift k in {1, 8}: control = sidecar of song *i* against the media and
`transcribe_words` of song *(i+k) mod 16*. **32 controls.** All 16 titles are
distinct, so every pair is genuinely wrong-song; the probe still reports any
pair whose normalized titles match (expected: none) rather than assuming it.

**Computed per control.** The same transcribe-family row as
`verify_fit.json` — `n_pairs`, `pair_fraction`, `slope`, `offset_s`,
`residual_mad`, `res_p50/p90/max`, `zero_evidence_fraction` — with provider
lines from A and transcribe words from B. CPU only.

**Emission family — second pass.** Same 32 controls, scored against B's
cached Phase 1b emission over A's warped spans. Needs the GPU but **no
forward passes** (emissions are cached). Run after the CPU table is saved,
so a GPU-unavailable moment cannot block the CPU half. Included because
Appendix C tests that family and M3 needs control values for it.

**Degenerate fits, handled in advance.**

- `n_pairs < 2` -> no fit; slope/offset/residual statistics do not exist;
  recorded `nofit`.
- `n_pairs < 5` -> caught by Appendix C's locked `n_pairs` floor; recorded
  `floor_caught`.
- `nofit` controls are excluded from "best over CONTROL" for the statistics
  that need a fit, **because those values do not exist**, and the excluded
  count is reported. No control is silently dropped.

**Pre-registered headline (the STOP item 1 answer).** The primary number is
`floor_caught` out of 32. If the `n_pairs` floor alone catches all 32, then
the residual family has no surviving negative to be tested against, and that
is recorded as a fact about the verify design rather than interpreted here.

**Outputs.** `m2/m2_probe.py`, `m2/m2_controls.json` (32 rows, verify_fit
schema plus `sidecar_id`, `media_id`, `shift`, `status`), `m2/m2_table.txt`.

---

#### Flagged for M3, not decided here

Moving from 2 controls to 32 makes "best over CONTROL" an extreme order
statistic, so it gets systematically stronger with n. A statistic that was
discriminative at n=2 can fail at n=32 from sample size alone. M3's read-off
must state **in advance** whether it applies Appendix C verbatim (strict
best-over-CONTROL) or a declared robust alternative. M3 is separately
commissioned; this is Ken's call when M3 is pre-registered, not a change to
Appendix C here.

#### Not pre-registered by this entry

M3, M4 and M6 read-off rules; any gate threshold (Appendix C owns those);
any change to `MAX_WORD_DUR_S`, arm (i), or the shipped routes.

### 2026-09-04 — M1 + M2 run — raw tables, no read-off beyond the pre-registered ones

**(Executor. The pre-registration above was ratified and committed
(`739d3f2`) before either probe was written, so every rule applied below
was fixed in version control while the numbers did not exist. M1's
validation test and M2's `floor_caught` headline are pre-registered and are
reported as computed; the one comparison that was *not* commissioned is
flagged where it appears. Ken rules — per `plans/PROGRAM.md` §"When a result
goes to Fable", neither outcome is ambiguous enough to spend a judge round.)**

**Artifacts** — session scratchpad: `m1/m1_probe.py`, `m1/m1_labels.txt`,
`m1/m1_rows.json`, `m1/m1_srt_check.py`, `m1/m1_srt_check.txt`;
`m2/m2_probe.py`, `m2/m2_table.txt`, `m2/m2_controls.json`,
`m2/m2_emis.py`, `m2/m2_emission.txt`, `m2/m2_emission.json`.

**One spec ambiguity resolved during M1, disclosed.** The pre-registration
says a line's reference is "the earliest transcribe word **aligned** to any
of its tokens", and separately that lines with none are `unref`. Under
substitution semantics `unref` would be almost unreachable (NW scores a
mismatch -1 against -2 for two gaps, so it substitutes rather than gaps).
The `unref` clause is what settles it: "aligned" was implemented as an
*identical* matched token. Resolved from the spec's own internal evidence,
not from the numbers, which did not exist yet.

#### M1 — table

`ref_cov` = provider lines that got a reference onset; `@T` = fraction of
those landing within T seconds of it, under the song's own arm-(i) warp.

```
song                     ken   lines  n_ref ref_cov     @0.3     @0.5     @0.8
------------------------------------------------------------------------------
Free                     U        46     46   1.000    0.783    0.913    0.957
Belle                    U       116    105   0.905    0.733    0.857    0.952
Colors of the Wind       U        37     37   1.000    0.676    0.811    0.946
Part of Your World       U        56     56   1.000    0.500    0.679    0.857
More Than That           U        40     40   1.000    0.500    0.625    0.875
Mirrors                  --      125     90   0.720    0.411    0.611    0.778
Seasons of Love          B        43     25   0.581    0.400    0.520    0.520
Popular                  B        61     57   0.934    0.298    0.509    0.702
Selfish                  --       61     60   0.984    0.300    0.483    0.633
Incomplete               --       19     17   0.895    0.235    0.412    0.529
Like I Love You          U        81     81   1.000    0.235    0.407    0.691
Domino                   B        65     53   0.815    0.245    0.340    0.396
Best Part of Me          B        39     36   0.923    0.194    0.194    0.389
Let It Go                --       40     40   1.000    0.100    0.125    0.125
Can You Feel the Love    --       35     35   1.000    0.057    0.114    0.114
Rock Your Body           --      107    104   0.972    0.038    0.087    0.192
```

**Pre-registered validation read-off, at the primary tolerance only.**

```
worst usable : Like I Love You   0.407
best broken  : Seasons of Love   0.520
separated    : False
overlap      : Seasons of Love 0.520, Popular 0.509  (both >= worst usable)
```

**M1 = NOT VALIDATED.** Per the ratified rule this is a STOP -> Ken: no
threshold is derived, the 6 un-eyeballed songs receive no labels, and the
labeller is not adjusted and re-run. The robustness columns are reported as
declared and do not change this: a labeller that separated only at 0.3 or
0.8 would still be recorded as not validated, and neither does.

#### M1 — SRT spot-check (the 3 of Ken's 10 with an uploader SRT)

Commissioned by the pre-registration to expose residual repeat
mis-latching. Same labeller, same warp, same tolerances; only the reference
changes. An SRT gives one start per *cue*, so a token matched mid-cue yields
that cue's start — coarser than word-level, and it reads early where a
provider line spans two cues.

```
song                   ken   n_ref ref_cov     @0.3     @0.5     @0.8  reference
--------------------------------------------------------------------------------
Part of Your World     U        56   1.000    0.321    0.518    0.661  uploader SRT
                                56   1.000    0.500    0.679    0.857  transcribe (primary)
More Than That         U        40   1.000    0.450    0.600    0.850  uploader SRT
                                40   1.000    0.500    0.625    0.875  transcribe (primary)
Like I Love You        U        81   1.000    0.247    0.395    0.654  uploader SRT
                                81   1.000    0.235    0.407    0.691  transcribe (primary)
```

Like I Love You — the song that breaks the separation — reads 0.395 against
an independent reference and 0.407 against the transcribe stream.

#### M2 — table

32 controls, shifts {1, 8} over the video_id ordering. 0 title collisions.
The self-test passed first: recomputing k=0 reproduced all 9 transcribe-family
fields of `p2b/verify_fit.json` on all 16 songs to 1e-9, which is what
licenses the reimplemented statistics.

**Pre-registered headline.**

```
caught by the n_pairs floor (<5) : 32 / 32
of those, nofit (n_pairs < 2)    : 30
surviving to a fit               : 0
```

The only two controls that paired at all:

```
sidecar                media                   k npairs pairfrc    slope status
Justin Timberlake - Ro Jessie J - Domino (Off  1      2   0.019  11.3386 floor_caught
Jessie J - Domino (Off Ed Sheeran - Best Part  8      2   0.031   0.0145 floor_caught
```

The remaining 30 pair 0 or 1 line and take the default warp. Full table in
`m2/m2_table.txt`.

**Recorded as the pre-registration required:** the `n_pairs` floor alone
catches all 32, so the residual family (`residual_mad`, `res_p50/p90`, the
per-line outlier rule) has **no surviving negative example** to be tested
against. Stated as a fact about the verify design; not interpreted here.

#### M2 — emission family (second pass, cached emissions, no forward passes)

Applied by the exclusion rule's own stated reason: it drops `nofit` controls
"because those values do not exist", and for this family they do — a nofit
control keeps the default warp, which places song A's provider spans on song
B's audio at face-value provider times. 31 of 32 scored (the 32nd scored 0
lines). Extremes shown; full table in `m2/m2_emission.txt`.

```
sidecar                media                   k scored   med_mean    med_min
Justin Timberlake - Ro Jessie J - Domino (Off  1     12     0.3807     0.0870
The Lion King - Can Yo Pocahontas - Colors of  1     34     0.2244     0.0007
The Lion King - Can Yo Idina Menzel - Let It   8     34     0.1392     0.0026
...
Justin Timberlake - Mi Ed Sheeran - Best Part  1     71     0.0218     0.0003
Backstreet Boys - More Seasons of Love (HD)--  8     36     0.0197     0.0020
Jessie J - Domino (Off Seasons of Love (HD)--  1     61     0.0121     0.0019
control median: 0.0752
```

*Not commissioned by M2 — flagged.* The probe also printed a PASS-vs-CONTROL
comparison on `emis_median_line_mean` (worst PASS = Seasons of Love 0.0336;
best control = Rock Your Body/Domino 0.3807; separated = False). That is
Appendix C's general rule, which belongs to **M3**, run early at the
executor's desk. It is recorded because it exists, not because it was
commissioned, and M3 is not bound by it.

#### What is Ken's

M1 is a pre-registered STOP. M3 as commissioned assumes M1's labels and M2's
controls; it now has neither a validated labeller nor a control that survives
the `n_pairs` floor. Whether M3 proceeds, changes shape, or waits is Ken's
call, as is whether the M1 labeller gets a second, separately pre-registered
attempt. No further probe is commissioned by this entry, and nothing here
touches a shipped route: word sidecars continue to demote to the line pool
exactly as R-1 ruled.

### 2026-09-04 — R-4 closed and rung 1 closed (Ken) — the per-song verify gate is retired

**(Ken's ruling, taken on the M1 + M2 tables above and a Fable read-off
commissioned for *how to proceed*, not to re-rule either measurement. This
closes R-4, M3 and the word route as a per-song route. No code changes —
Appendix A already specifies the demotion, and rung 1 never shipped.)**

#### The ruling

**R-4 = CLOSED. The Appendix C per-song verify gate is retired as measured
and non-viable.** The evidence family has now been tried three ways — GATE
R with the 2b cohorts, Ken's 10 labels against every statistic in the
record, and M1's purpose-built independent reference — and separates
nothing. The failure is structural, not threshold placement.

**Rung 1 is CLOSED, and the wording is deliberately narrow.** The finding
is *not* "Musixmatch per-word timings cannot be verified". Six of ten were
usable on Ken's own eyeball and one beat production; the mechanism is GO.
The finding is that **no per-song admission gate can be built for them from
this evidence family** — global fit, transcribe pairing, emission scores,
line-onset placement. A route that needs a human to watch each song is not
a route, so precedence 2 is closed: whole-song admission, provider text on
screen, and precedence above the line route all go.

**What is retired is the route, not the data.** The sidecar is still
fetched and still admitted at `WRONG_SONG_MAP_RATE`; its line starts join
F2's line-source pool (Appendix A) and its `ts`/`te` still set scaffold
ends (Appendix D, "Richsync ends"). The narrow wording is load-bearing: the
broad one would later license dropping the sidecar fetch entirely, which
this evidence does not support.

**Reversal condition, re-worded.** The old condition — "a re-specified
Appendix C that passes" — is void. Rung 1 does not return. Any future
word-sweep work is a **new mechanism on rung 2b**: for a sheet line F2 has
already placed, choose that line's word timings between richsync-warped
words and CTC words. That is a per-line choice with a same-line reference,
which is why it is better posed than anything Appendix C attempted, and it
is R-5's arm (i) vs arm (iv) question. It cannot be asked until F2 exists
and requires its own pre-registration.

#### M3 — closed by inspection, not run

M3 as commissioned ("re-run Appendix C's general rule on M1's labels with
M2's controls") has neither a validated labeller nor a control that reaches
a fit. Its headline is determined by tables already in this log: **zero of
Appendix C's three general-rule statistics** (`pair_fraction`,
zero-evidence fraction, emission family) separate Ken's labels, and the
spoilers are spread across four different usable songs and four different
broken ones. Two songs settle the shape of it: Popular (broken) and Like I
Love You (usable) are indistinguishable by line-onset placement at every
tolerance — 0.298/0.509/0.702 against 0.235/0.407/0.691. What differs is
*where* the damage sits, which no per-song summary can encode by
construction.

**M1 gets no second attempt.** The one mechanism-justified revision —
counting unreferenced lines as unplaced — is computable from the table
above and still fails (Like I Love You 0.407 against Popular 0.475). Every
other revision is selected by which named song it moves.

#### Correction on the record — the slope clamp

An executor verification pass of the judge's separation table reported that
`slope` separated Ken's labels 4-of-4. **That was wrong and is withdrawn.**
It applied a window of PASS ± 0.005, but Appendix C's bullet is
*widen-only*: "default window [0.97, 1.03]; **widened** only as far as
needed to cover PASS plus 0.005 margin". Ken's usable six span
[0.9804, 1.0039], entirely inside the default, so no widening fires and the
window stays [0.97, 1.03].

```
Can You Feel the Love    --        0.8733  REJECTED
Seasons of Love          broken    0.9542  REJECTED
Part of Your World       usable    0.9804  admitted
Incomplete               control   0.9915  admitted
Colors of the Wind       usable    0.9977  admitted
Mirrors                  --        0.9991  admitted
Like I Love You          usable    1.0001  admitted
Belle                    usable    1.0013  admitted
Free                     usable    1.0015  admitted
More Than That           usable    1.0039  admitted
Selfish                  --        1.0072  admitted
Popular                  broken    1.0117  admitted
Domino                   broken    1.0159  admitted
Best Part of Me          broken    1.0179  admitted
Rock Your Body           --        1.0266  admitted
Let It Go                --        3.4482  REJECTED
```

Corrected row: **slope's default window rejects one of four broken songs
and admits Rock Your Body**, whose M1 placement is the cohort's worst at
0.087. It does not separate. It also admits Incomplete, the one genuine
wrong-song control.

Two further points that keep this from being reopened. `slope` is a
**clamp** with its own construction, never one of the general-rule
statistics whose count the "fewer than 2 discriminative → STOP" test reads;
the count was zero of three throughout. And the separation had no mechanism
on the side where it appeared: the high-side margin between worst usable
and best broken is **0.0078**, under one percent of tempo, while Part of
Your World sits two percent off unity at 0.9804 and Ken called it clean.
Domino's 1.0159 and Best Part of Me's 1.0179 come from Theil-Sen fits on 14
and 12 pairs with `res_max` of 143.5 s and 119.0 s — contaminated fits
whose excess could have landed either side of unity.

**What slope is actually good at, and why it argues for the demotion.** It
detects the gross wrong-recording class — Let It Go 3.45, Can You Feel the
Love Tonight 0.87. F2's own warp gate catches those same two at MAD 5.80
and 4.48. The demotion path is therefore already protected against the
class slope detects, which is an argument for making the demotion permanent
rather than for a rung-1 gate.

#### M2's positive finding — `WRONG_SONG_MAP_RATE` is not under repair

32 of 32 cross-paired sidecars collapse at the text-pairing floor. That
**validates** the fetch-time gate for the purpose its name states: a
genuinely wrong song does not survive text matching. The mislabeling GATE R
found is a different class — same song, wrong recording or wrong edit — and
no fetch-time text statistic can see it. `plans/PROGRAM.md`'s demotion-gate
table moves from "under repair" to "adequate for wrong-song; wrong-edit is
a routing-time warp-gate question".

#### Consequences for the rest of the measurement program

- **M4** (per-section pairing-coverage detector) **re-homes to F2's warp
  gate** and stays held. Its consumer is no longer a rung-1 gate; the warp
  gate catches Let It Go and Can You Feel the Love Tonight but not Domino,
  Popular or Rock Your Body, which is the hole M4 addresses. Its positives
  and negatives do not decay, so it is held rather than spent.
- **STOP items 3 and 4** (outlier denominator, MAD-threshold population)
  **dissolve**, as the R-1 ruling anticipated: a discredited statistic is
  dropped, not tuned.
- **STOP item 6** (arm (iv) rebuild) re-homes to R-5 inside F2 and stays
  deferred.
- **Appendix C becomes record rather than spec.** Its emission-eligibility
  bullet goes with it.
- **M6 is next**, its "after M1-M3" precondition now satisfied.
- **The Selfish discrepancy stays open and recorded**: the M1 NW reference
  scores it 0.483 where the GATE R diagnosis recorded "10 of 15 pairs
  within 0.13 s, correctly timed". It bears on any future use of that
  reference and is not resolved here.

#### What the evidence will not support

Stated so a later reader does not re-litigate: any song-level admission
gate for richsync word timing, at any threshold, from any statistic in this
record; a claim that a better line-onset reference would fix M1 (Popular
and Like I Love You are indistinguishable at all three tolerances); a claim
that the emission family separates at song level; a claim that M2's
controls tested the residual family (none reached a fit); and a per-line
gate's *effect* before F2 exists.

**Nothing shipped changes.** The shipped matcher has two routes and never
consulted the word sidecar for routing. The floor here is "no change", not
"regression". The structural edits this ruling licenses — striking
precedence 2 from Appendix A, reducing the target ladder to three routes —
belong to the single design-consolidation pass, not to this entry.
