# LRCLIB timing prior for txt-sourced songs

Model: Claude Fable 5

Status: **steps 1–3 done. Step 3 shipped 2026-06-22 (fill-only,
default-on): LRCLIB is now a live matcher input for Genius-origin
songs.** Steps 1–2 were offline measurement (no regressions, safe
bails); step 3 productionized the prior after the constraint call below.

## Constraint — RESOLVED (relaxed 2026-06-22)

The standing constraint (LRCLIB verification-only — "not available to
the matcher or the deployed project") is **relaxed**: with steps 1–2
ship-shaped, the user authorized making LRCLIB cues a matcher input for
txt-sourced songs, fetched at processing time (architecturally like the
existing Genius fetch: free public API, no key). The chosen variant is
persisted as a real `.lrc` beside the song so reprocessing is
deterministic and offline-safe. See step 3.

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
   rejected; fetch top-k, keep the best. Step 1 measured the floor at
   ~38% (the Selfish 30/79 case, as predicted) — but found mapping
   rate separates only *right song* from wrong song: same-song
   variants with wrong timing still map up to 86%, so anchor MAD
   (below), not mapping rate, makes the timing cut.
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

### Step 1 results (2026-06-16) — KEEP

Tooling (both untracked under `scripts/`):
`capture_lrclib_keys.py` interactively captures canonical Genius
title/artist (the production lyric-choice sidecars are ephemeral and
were absent; mirrors `backfill_artifacts.py`, writes
`<songs>/lrclib/genius_keys.json`); `probe_lrclib_search.py` runs the
offline, cached LRCLIB queries and classifies each song. Keys captured
for the 16 non-SRT ground-truth songs; the 8 SRT-sourced fall back to a
title parse.

Of 24 songs: **22 HIT, 1 SAFE-SKIP, 1 SEARCH-MISS.** A *HIT* is a
returned synced variant whose timing matches the hand-fetched reference
(≥4 lines mapped, offset+drift residual MAD ≤0.5 s).

- **SAFE-SKIP — Bloodstream.** Search found the right song (album
  version, 76% mapping) but the awards video drops verses, so no
  variant matches its edited timing (MAD 10.4 s). Anchor MAD bails →
  prior no-ops → safe. The hand-fetched ref was a hard-won edit-
  matching variant a real user wouldn't find; auto-search correctly
  returns the album cut.
- **SEARCH-MISS — Best Part of Me**, a fixable key bug:
  `track_name="Best Part of Me (Live At Abbey Road)"` +
  `artist_name="Ed Sheeran (Ft. Yebba)"` → 0 records; cleaned to
  `Best Part of Me` / `Ed Sheeran` → 20 synced. **Step 3 must strip
  parenthetical/feature qualifiers before the structured query.**

Findings carried into step 3:

- **Mapping rate finds the song, not the timing** (see the vetting
  note above): the load-bearing timing gate is anchor MAD.
- **Duration ranking is unreliable but was harmless here.** Video↔
  soundtrack gaps are large (Colors of the Wind −173 s, Mulan −39 s),
  yet the video-duration-closest synced candidate was the timing match
  21/22 times — only because each song's pool is homogeneous (all
  soundtrack variants). Rank by mapping rate; duration is a tiebreak at
  most.
- Movie-clip predictions held: Hakuna Matata mapped 24/40 (the 16
  dialogue lines correctly got no cue — fail-safe) at MAD 0.24 s; Girl
  in the Bubble 36/36 at MAD 0.00 s.

Caveat bounding the claim: a HIT means "search found the soundtrack
sync we hand-vetted," scored against the hand-fetched reference. For
structurally edited videos, matching the soundtrack ref does not prove
the variant matches the video's own audio past the edit — that only
surfaces against the video clock, which is exactly what step 2 tests.

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

### Step 2 results (2026-06-17) — ship-shaped

Built into `scripts/eval_alignment.py` as `--lrclib-prior` (mutually
exclusive with `--srt-prior`): for an SRT-sourced song it auto-fetches
the top LRCLIB variant — same cached search as step 1, picked
reference-free by `select_lrclib_candidate` (mapping rate vs our sheet,
duration tiebreak), never the hand file — adapts its stamps to spans
(`alignment_eval.cue_spans_from_lrc`: end = next start, last + 4 s),
applies the shipped `apply_srt_prior`, and scores against the held-out
YT SRT. Run offline (`--offline` now also gates the LRCLIB fetch):

```
eval_alignment.py --folder <dir> --offline            # baseline
eval_alignment.py --folder <dir> --offline --lrclib-prior
```

Testbed: 10 SRT-sourced songs resolving a YT-SRT judge (the prior
engaged on 9; #OutOfOz "For Good" got no candidate → no-op). Incomplete
and Bye Bye Bye, originally not runnable offline, were re-captured into
the testbed on 2026-06-17: Incomplete had no cached vocal stem (re-
separated from its video) and no caption provenance (queried once
online: manual EN captions, valid YT-SRT judge); Bye Bye Bye only
lacked matcher inputs. Both got fresh whisper inputs via
`refresh_alignment_capture.py`. The original 8 keep their untouched
bundles, so their baseline and prior numbers are identical to the
first run (8-song subset: gross 4 → 3).

**No song regressed** (gross count and absolute ≤0.5 s / ≤1.0 s line
counts each same-or-better everywhere). Pooled YT-SRT gross 9 → 6,
within-1 s 93.4 → 93.8 %, within-0.5 s 75.9 → 76.7 %, +5 lines newly
rendered (fills). Per song:

- **Snap repaired a gross** — More Than That: offset +13.5 s (MAD
  0.33 s), 1 snap + 1 fill, gross 1 → 0. **Incomplete (new): offset
  −2.0 s (MAD 0.36 s), 2 snaps, gross 2 → 0** — clean repair, no fills,
  no collateral.
- **Fills, no harm** — Let It Go (+0.0 s), Speechless (+0.9 s), Can You
  Feel the Love Tonight (−11.9 s): one fill each, ≥ baseline.
- **Snap + fill, gross held** — Bye Bye Bye (new): offset −0.5 s (MAD
  0.26 s), 1 snap + 1 fill, ≤0.5 s and ≤1.0 s counts +1 each, gross
  3 → 3. The 3 residual gross are repeated-line ("bye bye bye") matcher
  misplacements outside the snap window — the prior left them untouched.
- **No-op offset-only** — Part of Your World (−4.0 s), Selfish
  (+0.1 s): audio already within the snap threshold.
- **Safe bail** — Mirrors: anchor-residual MAD > 0.75 s (`wide_spread`)
  → prior no-ops, scores identical to baseline. This is the
  structurally awkward song; the gate declined exactly as designed.

Large constant master offsets (+13.5 s, −11.9 s) absorbed cleanly, as
the offset fit predicted; no drift-fit contingency was needed. Watch
item: Can You Feel the Love Tonight sat at MAD 0.74 s, just under the
0.75 s bail threshold — it passed and helped, but it's the closest call.

Decision gate **met**: no regressions, the lone bail was a real
mismatch not a repairable one. Snap now has more support — 4 snaps
across 3 songs (More Than That ×1, Incomplete ×2, Bye Bye Bye ×1), each
either repairing a gross or improving within-threshold counts with zero
collateral. Incomplete is a second clean gross-repair (2 → 0); the
remaining caution is Bye Bye Bye, where snap correctly leaves
repeated-line matcher errors alone (neither helped nor harmed). The
fill-only conservative first ship still holds, with snap now a stronger
candidate for promotion than at n = 1.

## Step 3 — production shape (shipped 2026-06-22, fill-only)

What shipped:

- **Fetch + persist in the lyrics-fetch stage** (Genius branch only).
  `LyricsFetchStage._fetch_lrclib_prior` cleans the canonical Genius
  title/artist (`lrclib.clean_key` — the step-1 SEARCH-MISS fix: strips
  parenthetical/feature qualifiers), queries `lrclib.search`, picks
  reference-free with `lrclib.select_candidate` (duration tiebreak uses
  `ffmpeg.probe_duration`), and writes the chosen variant to
  **`<song>/lyrics/<stem>.lrc`** with a provenance header
  (`[ti]/[ar]/[al]/[length]/[lrclib_id]`, invisible to the cue parser).
  An existing `.lrc` is reused without re-querying (offline-safe
  reprocess). No candidate / no fetch → no cues → prior no-ops, song
  processes exactly as today.
- **Fill-only** (`apply_srt_prior(..., snap=False)`): fills lines the
  audio could not place; never overrides a placement. Snap stays
  deferred — its promotion needs a separately-measured cue-side gross
  rate for LRCLIB (the SRT prior's snap was justified by 2.6%).
- **`joint_lrclib_prior` config knob, default True.** Mutually
  exclusive with the SRT prior by origin (LRCLIB cues only exist for
  Genius-origin songs). Applied in `LyricAlignStage._apply_lrclib_prior`.
- **Schema v5** (`alignment_capture.py`): the bundle records
  `lyrics.lrclib` (the persisted `.lrc` path + the specific LRCLIB
  search result: id/track/artist/album/duration + query),
  `joint_stats.lrclib_prior` (offset/MAD/fills, `snap_enabled`),
  `media_duration_s`, and a completed `config_snapshot` (joint/prior
  knobs). The eval's `select_lrclib_candidate`/`cue_spans_for_lines`
  delegate to the shipped `lrclib` module, and its `--lrclib-prior` now
  applies the prior **fill-only** (`snap=False`), matching production.
- The production logic lives in the new `pikaraoke/lib/lrclib.py`;
  `pikaraoke/lib/alignment_eval.py` keeps the pure cue/mapping helpers
  it reuses.

### Shipped fill-only measurement (SRT testbed, 2026-06-22)

The step-2 "gross 9→6" was the snap-**on** ceiling. The shipped config
is fill-only, so it makes **no** gross repairs (those were snap-driven —
Incomplete 2→0 and More Than That 1→0 were snaps). Re-measured with
`--lrclib-prior` fill-only:

- Pooled YT-SRT gross **9 → 9** (no repair), within-0.5 s 75.9 → 76.2 %,
  within-1 s 93.4 → 93.2 %, **+5 lines rendered** (fills on More Than
  That, Let It Go, Speechless, Bye Bye Bye, Can You Feel). No song
  regressed (no fill became a gross); Mirrors safe-bailed (`wide_spread`).

So the conservative first ship buys **coverage only** on the testbed —
the gross wins need snap. Step-2 showed snap repaired those grosses with
zero collateral (4 clean snaps / 3 songs), so promoting snap is the
obvious next lever; deferred here pending the user's call, since txt
songs (the real target) can't grade snap's cue-side gross rate offline.

Eval after shipping (unchanged plan): txt songs lose LRCLIB as an
honest reference. Claims stay on the srt-sourced testbed (input LRCLIB /
judge SRT); txt-song improvements are reported as coverage/render deltas
or judged by ear, unless a second reference appears (YT manual captions
on a txt-sourced song's video — empty set in today's corpus, worth
re-checking as the library grows).

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
