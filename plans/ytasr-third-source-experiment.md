Model: Claude Sonnet 5 (initial run); Claude Fable 5 (review-fix re-sweep, final verdict)

# YTASR as a 3rd joint-DP candidate source (experiment)

## Goal

Test whether feeding YouTube auto-caption (YTASR) words into the joint DP as a
genuine 3rd peer candidate source — instead of using YTASR/LRCLIB only as
post-hoc "snap + fill" timing priors — beats today's shipped 2-source-DP +
prior scheme, on the 16 corpus songs with no independent YouTube manual-caption
reference (Genius/txt-sourced lyrics).

## What was built

- `pikaraoke/lib/joint_match.py`: `ytasr_words`/`beta` params, new
  `_build_ytasr_candidates` (mirrors `_build_transcribe_candidates`'s
  every-fuzzy-hit-is-a-candidate shape, not align's one-per-line shape — YTASR
  has no 1:1 token guarantee with the lyric line). Score generalizes to
  `transcribe_match + weight * (alpha * align_agreement + beta * ytasr_agreement)`.
  Fully additive: `ytasr_words=None` reproduces today's matcher bit-for-bit
  (tested directly).
- `pikaraoke/lib/windowed_realign.py`: `analyze_pass1` didn't recognize
  "ytasr" as an anchor-eligible source (found during code review, not part of
  the original plan) — a ytasr-won line would always be marked "suspect,"
  triggering re-align on a 2-source-only sub-problem that already failed to
  place it, and biasing this experiment's own scoring (`analyze_pass1` is
  reused below).
- `scripts/replay_ytasr_third_source.py`: replays each non-SRT bundle two ways
  (today's shipped scheme via the existing `replay_alignment_from_bundle`
  harness, unchanged; and the new 3-source/no-prior scheme) and scores both
  against a held-out LRCLIB reference — fetched for comparison only, never fed
  into either scheme. Scoring excludes prior-touched lines from each scheme's
  "anchors" (non-circular: 5 songs' old-scheme prior source *is* LRCLIB).

## Fixes landed after the first dry run

The first run's numbers (kept in git history at `9b135ca`) predate these and
are superseded:

- **B1** — `ytasr.parse_json3` word ends capped at `MAX_WORD_DUR_S=2.0`
  (were ballooning across instrumental gaps into 10-20s "words").
- **B2** — tied cue starts in the monotonic reduction arbitrated by score
  (repeated identical lines were collapsing onto the first ASR occurrence).
- **B3** — ytasr DP candidates generated at `ytasr.CANDIDATE_MAX_EDIT_RATIO`
  (0.34) instead of the transcribe knob (0.75); reference spans derived from
  the same single scan (`ytasr.spans_from_candidates`).
- **B4** — ytasr self-evidence graded as matched-token fraction instead of a
  flat 1.0 (junk fragments no longer collect full beta).
- **I1** — 2-of-3 corroboration rescue: on transcribe dissent the alpha/beta
  bonus survives at `min(align endorsement, ytasr endorsement)` instead of
  zeroing, so one witness can't veto the other two.
- **Harness** — alpha now swept as a grid alongside beta AND threaded into
  the replayed re-align sub-matches (they previously re-ran at the bundle's
  recorded alpha and overwrote swept lines, distorting per-song best-alpha);
  flat `<root>/lrclib/<stem>` reference cache tier (reproducible held-out
  scoring for ytasr-prior songs — this also shifts some *old*-scheme MAD
  numbers vs the first run, e.g. Bloodstream/Belle/Girl in the Bubble,
  because those songs previously live-fetched a different LRCLIB variant or
  had none); `asr0` labeling for gate-passing tracks whose candidate scan
  matches nothing.

## Results (16-song non-SRT corpus, 5×5 alpha×beta grid, best combo by crawl-then-MAD)

10 songs have a usable cached YTASR track (3src); 6 fall back to the plain
2-source DP. MAD is against the held-out LRCLIB reference over the scheme's
own trusted-anchor count; `bail:wide_spread` = the anchor-residual gate
rejected calibration entirely.

| song | src | old MAD | new MAD (best) | α | β | crawl | overlap |
|---|---|---|---|---|---|---|---|
| Defying Gravity | 3src | bail:wide_spread | bail:wide_spread | 0.5 | 0.5 | 4→2 | 10.7→0.1s |
| Free | 2src | 0.20s/16a | 0.20s/16a | 0.5 | n/a | 1→1 | 7.0→0.0s |
| Popular | 3src | bail:wide_spread | bail:wide_spread | 1.5 | 2.0 | 3→3 | 2.5→0.0s |
| Be Our Guest | 3src | 0.18s/48a | **0.15s/49a** | 0.5 | 1.0 | 0→0 | 2.7→0.0s |
| Belle | 3src | 0.30s/55a | **0.28s/55a** | 3.0 | 0.5 | 1→1 | 2.5→0.0s |
| Best Part Of Me | 3src | bail:wide_spread | **0.72s/24a** | 0.5 | 2.0 | 3→2 | 3.5→0.0s |
| Bloodstream | 3src | 0.46s/11a | **0.40s/11a** | 0.5 | 1.0 | 1→1 | 8.4→0.0s |
| HUNTR/X | 2src | bail:wide_spread | bail:wide_spread | 0.5 | n/a | 0→0 | 0.0→0.0s |
| Domino | 2src | 0.43s/7a | 0.43s/7a | 0.5 | n/a | 0→0 | 1.2→0.0s |
| In Summer | 2src | 0.15s/13a | 0.36s/14a | 0.5 | n/a | 2→1 | 0.0→0.0s |
| Mulan | 3src | 0.70s/21a | 0.74s/22a | 0.5 | 0.5 | 0→0 | 5.3→0.0s |
| NSYNC - Paradise | 2src | 0.27s/10a | 0.27s/10a | 1.0 | n/a | 2→2 | 0.0→0.0s |
| Colors of the Wind | 3src | 0.29s/32a | **0.13s/31a** | 0.5 | 3.0 | 1→2 | 3.8→0.0s |
| Hakuna Matata | 3src | bail:wide_spread | **0.35s/8a** | 0.5 | 3.0 | 3→0 | 0.0→0.0s |
| Next Ten Minutes | 2src | 0.47s/50a | **0.44s/52a** | 0.5 | n/a | 2→2 | 5.2→0.0s |
| Girl in the Bubble | 3src | 0.41s/15a | **0.33s/15a** | 0.5 | 2.0 | 1→0 | 0.2→0.0s |

## Verdict: win — overlap eliminated, MAD net-positive, beta now meaningful

**Overlap**: ~0.0s max on every song (10.7s worst-case before), including the
2src fallbacks — confirming the old prior's snap/fill, not the DP, drove
residual overlaps.

**MAD/bails**: 6 wins, 2 bail-recoveries (Hakuna Matata; Best Part Of Me —
the live Abbey Road recording, exactly the differs-from-studio class this
roadmap keeps YTASR for), 2 regressions: In Summer (2src; the accepted cost
of dropping the LRCLIB prior — LRCLIB is permanently out per the roadmap
decision) and Mulan (0.70→0.74, soft; was the first run's biggest win at
0.57 — B3's stricter ratio likely culled its garbled ASR candidates, its
best combo is the flat-surface default, worth a targeted look but a fair
trade against two bail recoveries).

**Beta is now signal**: with self-evidence graded (B4), winning betas spread
1.0-3.0 precisely on the songs where ytasr carries the load (first run: "low
beta always wins" — an artifact of flat self-evidence amplifying junk).
Alpha's near-uniform 0.5 remains mostly the min() first-grid-value tie-break
on flat surfaces (Belle's 3.0 excepted); don't read it as "alpha wants 0.5".

**I1 (2-of-3 rescue)** is byte-identical on this corpus (both sweeps produce
identical tables; instrumented: the rescue condition fires with positive
weight only on Hakuna Matata, 3 candidate scorings, max weight 0.69, no DP
selection change). Transcribe-dissent windows exist on every song, but align
and ytasr almost never both back them — consistent with dissent mostly
marking align-wrong placements, which must stay gated. Kept as tested,
zero-cost insurance against the transcribe-hallucination-over-clean-line
failure mode this corpus happens not to contain.

## Recommendation

Fold into production per the decided roadmap: non-SRT songs get this
3-source matcher with the priors removed; manual-caption (SRT) songs get the
cue-align windowed path (`scripts/cue_align_song.py`); a quick transcribe
pass runs first for dereverb triage; LRCLIB is not reintroduced. Remaining
before/alongside fold-in:

1. Pick production defaults from this sweep — keep today's 2-source alpha
   default (the sweep gives no reason to move it) and take beta ≈ 2.0 (the
   1.0-3.0 winners' middle; per-song best varies but surfaces are flat).
2. Targeted look at Mulan (why B3 culled its wins; likely garbled ASR right
   at the 0.34 boundary).
3. Widen the corpus past 16 songs before trusting win/loss counts further.
4. Idea still queued: pre-DP ytasr clock-offset calibration (the old prior
   calibrated; the DP path uses raw timestamps) — measure per-song lag via
   the harness before building anything.

## Critical files

- `pikaraoke/lib/joint_match.py`
- `pikaraoke/lib/ytasr.py` (`MAX_WORD_DUR_S`, `spans_from_candidates`)
- `pikaraoke/lib/windowed_realign.py`
- `pikaraoke/lib/srt_prior.py` (`offset_mad_against_cues`)
- `pikaraoke/lib/candidate_match.py` (`best_candidate_per_line`)
- `scripts/replay_ytasr_third_source.py`
