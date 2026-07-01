Model: Claude Sonnet 5

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

## Results (16-song non-SRT corpus, single dry run, alpha = bundle's own recorded value, beta swept over 0.5/1/1.5/2/3)

10 songs had a usable cached YTASR track (3-source test); 6 fell back to the
plain 2-source DP (no usable YTASR — the fallback case decision #2 called for,
not an error). One LRCLIB fetch hit a network timeout (`Girl in the Bubble`,
"Ariana Grande" query — a copy/paste artifact in that bundle's Genius artist
field, not this experiment's bug) and degraded to `no_reference` gracefully;
not re-run for this pass.

MAD is against the held-out LRCLIB reference, in seconds, over the scheme's
own trusted-anchor count (`n_anchors_fit`); `bail:wide_spread` means the
anchor-residual MAD gate rejected calibration entirely (no usable offset fit).

| song | src | old MAD | new MAD (best β) | best β | old→new crawl | old→new overlap |
|---|---|---|---|---|---|---|
| Defying Gravity | 3src | bail:wide_spread | bail:wide_spread | 3.0 | 4→4 | 10.7→0.0s |
| Free | 2src | 0.20s/16a | 0.20s/16a | n/a | 1→1 | 7.0→0.0s |
| Popular | 3src | bail:wide_spread | bail:wide_spread | 3.0 | 3→2 | 2.5→0.0s |
| Be Our Guest | 3src | 0.18s/48a | 0.19s/49a | 1.5 | 0→0 | 2.7→0.0s |
| Belle | 3src | 0.29s/39a | 0.29s/39a | 3.0 | 1→1 | 2.5→0.0s |
| Best Part Of Me | 3src | bail:wide_spread | bail:wide_spread | 0.5 | 3→3 | 3.5→0.0s |
| Bloodstream | 3src | bail:wide_spread | **0.32s/11a** | 0.5 | 1→1 | 8.4→0.1s |
| HUNTR/X | 2src | bail:wide_spread | bail:wide_spread | n/a | 0→0 | 0.0→0.0s |
| Domino | 2src | 0.43s/7a | 0.43s/7a | n/a | 0→0 | 1.2→0.1s |
| In Summer | 2src | 0.15s/13a | 0.32s/14a | n/a | 2→2 | 0.0→0.0s |
| Mulan | 3src | 0.70s/21a | **0.57s/21a** | 2.0 | 0→1 | 5.3→0.0s |
| NSYNC - Paradise | 2src | 0.32s/10a | 0.32s/10a | n/a | 2→2 | 0.0→0.0s |
| Colors of the Wind | 3src | 0.29s/32a | **0.08s/30a** | 0.5 | 1→1 | 3.8→0.0s |
| Hakuna Matata | 3src | bail:wide_spread | **0.35s/8a** | 1.5 | 3→1 | 0.0→0.0s |
| Next Ten Minutes | 2src | 0.47s/50a | 0.46s/52a | n/a | 2→2 | 5.2→0.0s |
| Girl in the Bubble | 3src | bail:no_reference | bail:no_reference | 0.5 | 1→1 | 0.2→0.0s |

## Verdict: partial win — clear on overlap, mixed on MAD, not ready for production

**Overlap is the standout result**: nearly every song drops to ~0.0s max
overlap in the new scheme, often from a multi-second overlap in the old one.
This shows up even on the 6 pure-2-source-fallback songs (where the *only*
change is dropping the LRCLIB-prior post-processing step), suggesting the
current prior's snap/fill logic — not the 2-source DP itself — is the source
of most residual overlaps. This is arguably more perceptually important for
actual karaoke display than sub-second MAD differences against an
approximate reference.

**MAD is genuinely mixed**, comparing the 9 songs where both schemes produced
a usable (non-bailed) number: 2 improved clearly (Mulan 0.70→0.57, Colors of
the Wind 0.29→0.08), 1 regressed clearly (In Summer 0.15→0.32 — notably, one
of the 2-source-fallback songs, so this regression comes purely from dropping
the LRCLIB prior with nothing to replace it), 1 regressed marginally (Be Our
Guest 0.18→0.19), 5 were unchanged. 2 songs recovered from a `wide_spread`
bail-out to a usable MAD (Bloodstream, Hakuna Matata) — arguably a bigger win
than a small MAD delta, since the old scheme had *no* calibration signal at
all on these. 4 songs stayed bailed regardless of scheme (a different,
unaddressed problem — likely LRCLIB match quality or genuine alignment
difficulty on those specific songs, not something this change touches).

**Net read**: encouraging, not conclusive. This is a single dry run at one
alpha value (the bundle's own recorded default) with only a 5-point beta
sweep and no alpha sweep — the same kind of tuning `alpha` itself went
through before its corpus-tuned default was trusted. The In Summer regression
shows real cost on at least one song when YTASR isn't even available to
compensate for losing the prior, so "drop the prior unconditionally" is not
obviously safe on its own; whether that's specific to In Summer or a broader
pattern needs more songs.

## Recommendation

Not ready to fold into production (`lyric_align.py`'s `_run_joint`). Before
that decision:

1. Re-run with `Girl in the Bubble`'s network timeout resolved (retry, or fix
   the stale "Ariana Grande" Genius-artist field this bundle carries).
2. Sweep `alpha` alongside `beta` rather than holding it at today's
   2-source-tuned default — a 3-source score has a different natural balance
   point.
3. Investigate the overlap finding directly: instrument *which* lines lose
   their overlap when the prior is dropped, to confirm the prior's snap/fill
   (not the 2-source DP) is the actual cause before treating "drop the prior"
   as a free win independent of adding YTASR.
4. Widen the corpus past 16 songs before trusting the MAD win/loss counts.

## Critical files

- `pikaraoke/lib/joint_match.py`
- `pikaraoke/lib/windowed_realign.py`
- `pikaraoke/lib/srt_prior.py` (`offset_mad_against_cues`)
- `pikaraoke/lib/candidate_match.py` (`best_candidate_per_line`)
- `scripts/replay_ytasr_third_source.py`
