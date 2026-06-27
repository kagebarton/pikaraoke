# Fix slow-sweep / concurrent-line karaoke artifacts

Model: Claude Opus 4.8

## Context

After the 2026-06-26 bundle regen, many songs render a line that **appears on
time but sweeps very slowly while the next, correctly-timed line shows
concurrently**. In the rendered `.ass` the karaoke `\kf` fills are stretched to
fill the whole line span, so an over-long line span *is* a slow crawl (there is
no static linger). The visible signature is inter-line overlap well beyond the
normal ~1s `\k80` lead-in.

**Affected (overlap-confirmed, strong tier):** Ariana/John Legend Beauty and the
Beast (worst — a 32.8s line), Bloodstream, Defying Gravity, 'Free', Backstreet
Incomplete, Girl in the Bubble, Mulan, Mirrors, The Next Ten Minutes, Lion King
Can You Feel, Mena/Naomi A Whole New World. Clean control set (must stay clean):
Domino, Hakuna Matata, HUNTR_X, Josh Gad In Summer, NSYNC Paradise, Selfish,
Backstreet More Than That.

### Root cause: one missing constraint, three doors

Nothing in the pipeline caps a line/word to a plausible sung duration; every
timing step spreads the sweep evenly across whatever span it is handed
([candidate_match.py `_build_line_object`](../pikaraoke/lib/candidate_match.py#L167)
interpolation, [srt_prior.py `_fill_line`](../pikaraoke/lib/srt_prior.py#L195)).
A too-wide span enters via three doors:

| Door | Mechanism | Songs |
|---|---|---|
| **1. Matcher window straddles a time gap** | [`find_candidates`](../pikaraoke/lib/candidate_match.py#L64) scores fuzzy windows by token edit-distance over token *indices* (`n-2..n+3` wide), never checking the matched tokens are temporally close. "True as it can be" matched a window grabbing a spurious `Thank/you`@0.3s **plus** `as it can be`@30s — same score as the tight window → 31.8s line. Same function derives the YTASR cue spans, and `windowed_realign` re-runs the joint matcher, so it leaks into both. | B&B Ariana, Incomplete, Mirrors, Mena, Lion King CYF (via pass-1 + SNAP); Bloodstream, Girl in Bubble (via wide YTASR cue + FILL); Mulan (stacking) |
| **2. Prior propagates the wide span** | [`apply_srt_prior`](../pikaraoke/lib/srt_prior.py#L75): SNAP shifts a placed line to `cue+offset` but **keeps** its (matcher-broken) width; FILL spreads an unplaced line's words evenly across the **full** external cue, uncapped ("Forever" over 19.7s). | (snap) all door-1 songs; (fill) Bloodstream, Girl in Bubble, Next Ten Min |
| **3. `windowed_realign` repeat-pileup** | re-align stretches one instance of a repeated chant across a span. | Defying Gravity, 'Free' |

**This plan fixes doors 1 and 2** — the two mechanical, high-leverage changes.
Door 3 (repeat-pileup) is the upstream lyric-version-match lever tracked in the
existing repeat-pileup investigation and is **out of scope here**; the door-1 fix
reaches `windowed_realign` (it re-runs the matcher) and should *help* Defying /
'Free', but if duplicate placements survive they remain a door-3 follow-up.

### Prior amplification, measured (per active song)

FILL excess = crawl-seconds the prior *paints from its own cues* (its own
imprecision); SNAP excess = matcher-origin width it merely *relocates*.

| Prior | songs | FILL excess/song | max fill | max cue | why |
|---|--:|--:|--:|--:|---|
| **SRT** | 13 | 0.4s | 5.9s | 12s | tight — `cue_spans_from_srt` has explicit per-cue **ends** |
| **LRCLIB** | 4 | **4.6s** (~11×) | 19.7s | 64s | `cue_spans_from_lrc` infers each end as the **next line's start** → balloons across gaps |
| YTASR | 9 | 3.8s | 16.6s | 27s | word-level but coarsest cue count (Bloodstream alone: 10 cues ≥10s) |

LRCLIB is structurally the loosest FILL source; SRT shows up in more visible
crawls only as a faithful **relay** of the door-1 matcher fault, not its own
imprecision. Conclusion (validated): do **not** delete LRCLIB (its SNAP uses the
reliable LRC *start* and gives gross-error repair + coverage on clean songs;
deleting it leaves the identical YTASR FILL bug live and discards coverage on
Domino/Josh Gad/HUNTR_X), and do **not** drop SNAP (it creates no width; once
door 1 is fixed it only repositions correctly-sized lines). Fix the shared
`_fill_line` instead.

## Scope

- **In:** door 1 (`find_candidates` time-compactness) and door 2 (cap
  `_fill_line`). Both correct under the current architecture and under the
  planned YTASR-as-source change.
- **Out:** door 3 repeat-pileup (Defying, 'Free'); the YTASR-as-source promotion
  (documented below as a sequenced follow-on, gated on door 1); removing any
  prior; touching SNAP.

## Status (2026-06-27): door 2 shipped; door 1 deferred

Door 2 is implemented and validated (fixes the 3 FILL-origin songs). Door 1 (a
candidate filter in the matcher) was **tried and backed out** — see "Door 1
findings" below. Per user decision, work **stops at door 2 for now**; the
recommended door-1 replacement (render-time line clamp) is documented in §1′ but
deferred until the regenerated bundles are eyeballed.

## Changes

### 1. Time-compactness for fuzzy candidate windows — TRIED, BACKED OUT

Implemented a per-candidate span reject in
[`_build_transcribe_candidates`](../pikaraoke/lib/joint_match.py) and
[`ytasr.cue_spans_for_lines`](../pikaraoke/lib/ytasr.py), iterated through two
criteria (max-internal-gap, then span-per-lyric-word). Replayed the **fixed**
matcher over all captured bundles (no GPU — the bundle stores the matcher's
`align_words`/`transcribe_words` inputs verbatim).

**Door 1 findings — why it was backed out:**

- **Overfit to B&B.** Only Beauty and the Beast's wide line is an actual
  transcribe-window mis-anchor (its 31.8s line dropped to 2.1s). The replay
  showed the *other* wide pass-1 lines are **not** transcribe-window problems:
  Mirrors and Lion King CYF are **align-sourced** (forced-alignment stretch, a
  path the candidate filter never touches); Incomplete (1.3 s/word) and Mena
  (1.15 s/word) are **genuinely spread** with no tighter alternative.
- **A hard reject perturbs the global DP.** Removing a wide candidate re-tiles
  the interval scheduler and flips *other* lines from placed → `interp` (0 words,
  dropped from render): B&B "Unexpectedly" and a Hakuna chorus line vanished.
  That is a **coverage loss**, not a fix. Net over the corpus: 3 wide lines
  improved, 2 lines silently dropped.
- A soft score-penalty avoids the coverage loss but needs careful calibration
  (negative scores can still drop a line) and still only reaches the B&B-style
  case — low leverage for high risk.

**Conclusion:** the matcher DP is the wrong place. The wide-line crawl is best
neutralized where it is rendered, uniformly across all sources, which also covers
the align-sourced and realign (door 3) cases the matcher filter never could.

### 1′. Recommended replacement — render-time line clamp (not yet built)

A post-placement pass over `line_objects` (after the prior, before
`_generate_ass`), sibling to door 2's `_fill_line` cap: for any line whose span /
lyric-token-count exceeds a threshold (~1.5–1.8 s/word), re-pace its words evenly
across `[start, start + n_tokens * cap]`, anchored at the (correct) start. No DP
perturbation, no coverage loss; covers the 5 SNAP-relocated cases (B&B,
Incomplete, Mirrors, Mena, Lion King), both realign cases (Defying, 'Free'), and
Mulan's stacked pair. **Trade-off:** even re-pacing discards real interior word
timing — acceptable for the crawl cases (their interior timing is already wrong),
but the threshold must stay above legit slow lines (corpus crawls are ≥1.9 s/word
mis-anchored vs ≤1.3 s/word legit, so the band is clean).

### 2. Cap `_fill_line` width — SHIPPED

[srt_prior.py `_fill_line`](../pikaraoke/lib/srt_prior.py#L195) currently does
`step = (t1 - t0) / len(toks)` with no bound. Clamp the rendered width, anchored
at the **reliable** cue start `t0`:

```
width = min(t1 - t0, len(toks) * MAX_WORD_DUR_S + FILL_FLOOR_S)
```

so a 19.7s single-token "Forever" fill collapses to a normal-paced ~2s sweep that
still *starts* correctly, rather than a crawl — strictly better than both the
crawl and dropping the line. Serves SRT + LRCLIB (and YTASR until/unless it is
promoted out of the prior, per below). `MAX_WORD_DUR_S` ≈ 2–2.5s; reuse / align
with `PipelineConfig.max_word_dur` (5.0) sensibilities but tighter for fills.

## Tests

- **Unit, door 1:** synthetic transcribe stream with a 30s mid-window gap — the
  matching line's candidate is rejected (or out-scored by the compact window);
  a held-note window (one 6s word, no inter-word gap) is **kept**.
- **Unit, door 2:** `_fill_line` with a 20s cue and a 1-token line clamps to
  ≤ cap and keeps `start == t0`; a normal 3s cue is unchanged.
- **Integration:** re-run the affected bundles; assert max inter-line `.ass`
  overlap drops under threshold for B&B, Mirrors, Bloodstream, Next Ten Min,
  Girl in Bubble; assert the control set's line timings are byte-unchanged.

## Verification (manual)

- Fast corpus check, no GPU: `scripts/replay_alignment_from_bundle.py <library>`
  replays match → re-align → prior from the captured bundles and prints a
  per-song before/after overlap + crawl summary (exact for prior-only changes
  like door 2; `--no-realign` for matcher iteration). `--write` regenerates the
  `.ass` for eyeball/playback. Use this before paying for a full whisper regen.
- [ ] Regen bundles for the 11 affected songs (`scripts/regen_alignment_bundles.py`).
- [ ] Re-run the overlap scan; confirm strong-tier songs fall to the clean band.
- [ ] Confirm control set (Domino, Hakuna, Selfish, …) unchanged.
- [ ] Eyeball-play B&B Ariana, Mirrors, Bloodstream, The Next Ten Minutes — no
      slow-sweep line overlapping a correctly-timed one.
- [ ] Spot-check Defying / 'Free' (door 3) — expect improvement from the
      realign cascade, not necessarily a full fix.

## Follow-on (separate, sequenced): promote YTASR to a 3rd matcher source

YTASR is same-clock and word-level — structurally a second transcribe stream, so
it can become a real matcher source (align / transcribe / **ytasr**) instead of a
post-hoc prior, drawing per-word times from the ASR timestamps and competing in
the DP per line. SRT and LRCLIB stay priors (not same-clock / not word-level).

**Gated on door 1** — a YTASR source routes through `find_candidates`, so it
needs the time-compactness fix first or it stretches identically. **Narrows door
2** — YTASR FILL crawls (Bloodstream, Girl in Bubble) then resolve inside the DP;
the `_fill_line` cap would serve SRT + LRCLIB only. Also collapses today's
`ytasr.cue_spans_for_lines` bolt-on (a mini-matcher already calling
`find_candidates`) back into the one matcher.

Untested; do **not** bundle with the two fixes above. Before adopting, the
experiment must show, on the corpus:

1. **Coverage** — lines the prior FILL used to render (even garbled, painted
   across the cue) are not *lost* to `_interpolate_missing` (dropped) when YTASR
   only places what `find_candidates` matches. Capture before/after line counts.
2. **Bad-track rejection** — DP corroboration rejects a garbled/wrong-sync ASR
   track as well as the prior's MAD≤0.75 bail did (Hakuna Matata is the test).
3. **3-way scoring** — a YTASR term in `transcribe_match + alpha*align_agreement`,
   alpha re-swept.
