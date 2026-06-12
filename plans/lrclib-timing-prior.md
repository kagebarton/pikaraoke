# LRCLIB timing prior for txt-sourced songs

Model: Claude Fable 5

Status: **plan only — measurement-first, nothing started.** Sketched
2026-06-12 after the SRT prior shipped (plans/srt-timing-prior.md).
Steps 1–2 are offline measurement against data already on disk and do
NOT require deciding the constraint question below; step 3 does.

## Constraint to re-open (user's call, not before step 3)

Standing constraint: LRCLIB is verification-only — "they will not be
available to the matcher or the deployed project." This plan's end
state would relax that: LRCLIB cues become a matcher input for
txt-sourced songs, fetched at processing time (architecturally similar
to the existing Genius fetch: free public API, no key, cache the
choice). Steps 1–2 only measure; the decision is deferred until their
numbers exist.

## Motivation

After the SRT prior, the corpus' remaining 50 gross live mostly in
txt-sourced songs (Bloodstream 11, Belle 7, Bubble 5, Next Ten Minutes
5, Best Part of Me 4, Hakuna Matata 3 — roughly 35–40 of 50). The
prior machinery is already cue-source-agnostic: `apply_srt_prior`
takes `cue_spans_by_line` and never asks where they came from. The
missing pieces are (a) getting trustworthy cues out of LRCLIB
automatically and (b) an honest way to measure the result.

## Why this is riskier than the SRT prior

- **Different clock.** SRT cues live on the video's own timeline — one
  constant display lead. LRCLIB syncs target studio masters. Constant
  master offset is absorbed by the offset fit (step-2 vetting saw
  ±20 s absorb cleanly), but *structural* edit differences (Hakuna
  Matata's dialogue insert, extended intros, end-title cuts) break
  cue+offset for everything past the edit point. The anchor-MAD
  bail-out catches these (anchors straddling the edit disagree), but
  the expected hit rate is below the SRT prior's 9-for-9 — and the
  bailed songs may be exactly the messy ones holding the gross.
- **Tempo-skewed masters.** Hand-vetted variants showed drift ≈ 0, but
  auto-fetched ones may include sped-up masters (PAL-style ~4%). MAD
  catches it (residuals spread linearly), at the cost of a bail-out; a
  drift-capable fit (`alignment_eval._fit_offset_and_drift`, Theil–Sen,
  already written) is the contingency if step 2 shows bails that a
  linear fit would rescue.
- **Variant quality.** LRCLIB hosts many variants per song with no
  quality control; the hand-vetting that took a day for 24 files must
  become automatic (see the gate below).
- **Search sensitivity.** LRCLIB search is brittle against noisy
  queries; video titles ("… (Official Video)---uuZE_IRwLNI") will
  miss. For txt-sourced songs we hold a better key: the lyrics came
  through the Genius fetch, and the chosen `GeniusHit` carries
  canonical `title` and `artist` (pikaraoke/lib/genius.py) — search
  with those, rank with LRCLIB's `duration` field.
- **Eval circularity with no escape hatch.** txt songs have no second
  timing reference; feeding them LRCLIB makes the current eval grade
  the prior against its own input — and variants share lineage, so
  variant-vs-variant is not independent. The honest testbed is the
  srt-sourced songs (step 2).

## Automatic variant vetting (reuses shipped machinery)

Two computed numbers replace the hand-vet:

1. **Mapping rate** — `map_lines_to_cues` (fuzzy NW, 0.85 ratio floor)
   of the candidate's synced lines against *our actual lyric sheet*.
   Junk/wrong-language/divergent-edit variants score low and are
   rejected; fetch top-k, keep the best. Threshold TBD from step-1
   data (hand-picked variants ranged 30/79 … 36/39 — the floor must
   tolerate coarse-but-correct syncs).
2. **Anchor MAD** — the prior's own offset-fit spread (0.75 s
   threshold, ≥4 anchors) vets the winner's *timing* at match time.
   A good-text/garbage-sync variant bails exactly like sloppy captions.

Unmapped lines are fail-safe: no cue, never touched.

## Step 1 — search-quality probe (offline, no matcher code)

Ground truth already exists: the 24 hand-fetched files in
`<songs>/lrclib/`.

- Script: for each corpus song, query the LRCLIB API
  (`GET /api/search`, `track_name` + `artist_name`; identify with a
  User-Agent per their guidelines). Query keys: Genius canonical
  artist/title where lyrics_origin == "genius"; for srt-sourced songs
  (no Genius hit) a cleaned title parse — these songs only need to
  work for step 2's testbed.
- For each hit list: does any candidate's `syncedLyrics` match the
  hand-fetched file (same variant or equivalent timing)? Record hit
  rate, rank of the correct variant, and the mapping-rate gate's
  verdict on the top-ranked candidate vs the hand-picked one.
- Output: keep/kill decision on auto-search, and the mapping-rate
  threshold measured rather than guessed.

## Step 2 — LRCLIB-as-input ceiling on the srt-sourced testbed

The 8 srt-sourced songs with LRCLIB files have two *independent*
references; use one as input, the other as judge:

- Replay pass-1 from bundles (no GPU), apply the prior with
  **LRCLIB-derived cue spans** as input (LRC adapter: stamps are
  starts; end = next stamp, last line start + ~4 s), score against the
  **YT SRT** (same clock as the audio — honest).
- Use step-1's auto-fetched top candidate, not the hand-picked file:
  this measures the *whole pipeline* (search + vet + prior), not just
  the prior.
- Report per song: bail-out (and which gate), offset/MAD, snapped/
  filled, gross delta vs the pass-1-vs-SRT baseline. Pooled: did any
  song regress; hit rate (songs improved / songs attempted).
- Decision gate: ship-shaped only if no song regresses and the
  bail-out behavior looks safe (bails on real mismatches, not on
  repairable ones). If structural-edit bails dominate, evaluate the
  piecewise/drift fit contingency before going further.

## Step 3 — production shape (only after 1–2, and the constraint call)

- Fetch lives in the lyrics-fetch stage alongside the Genius call
  (origin "genius" only); persist the chosen variant beside the
  lyrics (like the genius choice file) so reprocessing is
  deterministic and offline-safe; no fetch → no cues → prior is a
  no-op, song processes exactly as today.
- Conservative first ship: **fill-only** (no snap) — fills cannot
  break a correct audio placement; snap promotion only if step-2
  numbers support it (the SRT prior's snap was justified by a 2.6%
  cue-side gross rate; LRCLIB's equivalent must be measured).
- `joint_lrclib_prior` config knob, default per step-2 verdict.
- Eval after shipping: txt songs lose LRCLIB as an honest reference.
  Claims stay on the srt-sourced testbed (input LRCLIB / judge SRT);
  txt-song improvements are reported as coverage/render deltas only,
  or judged by ear, unless a second reference appears (YT manual
  captions on a txt-sourced song's video — empty set in today's
  corpus, worth re-checking as the library grows).

## Open questions

- Multi-variant ensembling (median cue time across top-k variants)
  vs single-best: probably overkill; revisit only if step 1 shows
  near-ties with disagreeing timing.
- Whether srt-sourced songs should *also* consult LRCLIB when both
  exist: no — SRT is same-clock and already shipped; two priors would
  fight. LRCLIB input is for songs with no SRT, full stop.
- Album-version mismatch (radio edit vs album cut) where text maps
  fine but a verse is missing: mapping gate passes, MAD likely
  catches the post-cut shift; confirm with step-2 data.
