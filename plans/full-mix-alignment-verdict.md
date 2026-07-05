# Full-mix whisper passes: experiment verdict

Model: Claude Fable 5

Companion to `plans/full-mix-alignment-experiments.md` (the plan this
verdicts). Both experiments ran to completion on `fullmix`; the answer to
the plan's question is **no** for both.

## Verdict

**Experiment A (mix as 4th joint-DP source): NO.**
**Experiment B (mix retry in the cue-align rescue ladder): NO.**

Both knobs (`capture_mix_transcribe`, `cue_mix_rescue`) stay off. Nothing
ships and nothing needs reverting — the matcher and cue-align changes are
inert unless a caller opts in, so the harness and the (unused) production
hooks stay committed as a documented negative result. Bundles keep
`mix_transcribe_words`, so re-testing this question later is a free
offline replay, no GPU required.

## What was built and run

Commits on `fullmix`:

- `dd40c5d` — A0 capture (`capture_mix_transcribe`) + Experiment B cue
  rescue rung (`cue_mix_rescue`) + harness scripts.
- `991b253` — Experiment A matcher extension (mix as a 4th joint-DP
  source, weight `gamma`) + sweep harness.
- `7cfdb23` — harness fix: select Experiment A songs by
  `lyrics.source_kind`, not `ground_truth_refs.youtube_srt_present` (that
  flag is true for the whole corpus, not just SRT-sourced songs — the
  original sweep selection silently matched zero songs).
- `976e899` — regen fix: `regen_alignment_bundles.py` never seeded
  `ctx.artifacts["ytasr"]` for reused genius-origin songs (that seed phase
  existed on a prior branch, not on `fullmix`'s lineage), so every regen
  silently ran the joint matcher two-source and shipped 2-source `.ass`
  files for those songs. Ported the seed phase forward. Independent of the
  mix verdict, but discovered while validating the Experiment A baseline —
  keeps value regardless.

Regenerated the full 33-song corpus (17 non-SRT / txt+genius, 16
SRT-sourced) twice — once before the YTASR-seed fix (void baseline, 2-source),
once after (the real 3-source baseline these results are measured against).
All 33 bundles now carry `mix_transcribe_words`; 10 of the 17 non-SRT songs
have an on-disk YTASR caption and got the real 3-source route.

## Experiment A: sweep results

Per non-SRT song: shipped baseline (align + transcribe + optional ytasr, no
mix) vs. **M2** (mix as a genuine 4th source, gamma swept 0.5–3.0, alpha/beta
pinned at shipped defaults) vs. **M1** (mix substituted into the ytasr slot,
only for songs without a real ytasr caption, beta swept). Scored by MAD of
each scheme's own trusted anchors (`align`/`transcribe`/`ytasr` only — mix-won
lines are excluded from scoring by construction, so this stays non-circular)
against held-out LRCLIB cues.

| song | src | baseline MAD | M2 MAD (best gamma) | M1 MAD (best beta) | crawl | overlap | mix_won |
|---|---|---|---|---|---|---|---|
| Defying Gravity | y+m | bail:wide_spread | bail:wide_spread (0.5) | n/a | 3→3 | 7.8→7.8s | 1 |
| 'Free' | m | 0.20s/16a | 0.15s/4a (0.5) | 0.26s/16a (0.5) | 1→1 | 0.0→0.0s | 30 |
| 'Popular' | y+m | bail:wide_spread | bail:wide_spread (2.0) | n/a | 3→3 | 0.0→0.0s | 5 |
| Be Our Guest | y+m | 0.16s/49a | 0.18s/45a (0.5) | n/a | 0→0 | 0.0→0.1s | 9 |
| Belle | y+m | 0.39s/55a | 0.35s/48a (1.5) | n/a | 1→1 | 0.0→0.0s | 15 |
| Best Part Of Me | y+m | bail:wide_spread | **0.29s/12a (2.0)** | n/a | 2→3 | 0.0→0.0s | 16 |
| Bloodstream | y+m | 0.60s/11a | 0.60s/11a (1.0) | n/a | 1→0 | 0.0→0.0s | 2 |
| HUNTR_X | m | bail:wide_spread | **0.23s/6a (1.0)** | bail:wide_spread (1.0) | 0→0 | 0.0→0.0s | 20 |
| Domino | m | 0.43s/7a | **0.11s/6a (2.0)** | 0.20s/7a (2.0) | 0→0 | 0.1→0.1s | 1 |
| In Summer | m | 0.22s/14a | 0.20s/14a (0.5) | 0.20s/14a (0.5) | 2→2 | 0.0→0.0s | 1 |
| Mulan | y+m | bail:wide_spread | bail:wide_spread (0.5) | n/a | 0→0 | 0.0→0.0s | 3 |
| NSYNC - Paradise | m | 0.27s/10a | bail:few_anchors (0.5) | 0.32s/10a (0.5) | 1→1 | 0.0→0.0s | **40** |
| Pocahontas | y+m | 0.19s/31a | 0.29s/27a (2.0) | n/a | 2→0 | 0.0→0.0s | 9 |
| Seasons of Love | m | 0.53s/5a | 0.53s/5a (0.5) | 0.53s/5a (0.5) | 3→3 | 0.0→0.0s | 0 |
| Hakuna Matata | y+m | 0.41s/8a | 0.41s/8a (0.5) | n/a | 3→3 | 0.0→0.0s | 3 |
| The Next Ten Minutes | m | 0.46s/52a | 0.35s/37a (2.0) | 0.34s/52a (3.0) | 2→2 | 0.0→0.0s | 17 |
| For Good (Girl in the Bubble) | y+m | 0.39s/15a | 0.39s/15a (0.5) | n/a | 1→1 | 0.0→0.0s | 0 |

Surface reading: 2 bail-recoveries, one strong MAD win (Domino), two crawl
eliminations, mostly flat/mixed elsewhere. **M1 is uniformly weaker than
M2** (HUNTR_X stays bailed under M1, Paradise/Free are worse than baseline)
— slot-substitution is not a viable shape; only the gated-4th-source
treatment ever helps.

## Experiment A: why the surface reading doesn't hold up

Two follow-up checks changed the read:

**1. Line-level eyeball of the "big win" songs.** Diffing baseline vs. the
winning-gamma output line-by-line showed the actual footprint is much
smaller than the MAD deltas suggest: Domino's 0.43→0.11s win is *two lines*
at the very start of the song; Bloodstream's crawl fix is *one line*. Best
Part Of Me and HUNTR_X have real multi-line blocks that moved, but a
same-scale eyeball of Mirrors/Paradise/Defying Gravity (Experiment B's
biggest case plus two Experiment A flags) read as "not much changed" —
not worth the extra inference pass for that size of effect.

**2. Mechanism decomposition.** Every M2 mix-won line, corpus-wide, was
classified by what it displaced at the joint DP's pass-1 output (before
windowed re-align can re-place a line locally and hide its `mix` tag):

| bucket | count | share |
|---|---|---|
| filled a true gap (baseline `interp`/`absent`) | 2 | 1% |
| displaced `align` | 56 | 33% |
| displaced `transcribe` | 95 | 55% |
| displaced `ytasr` | 19 | 11% |
| **total mix-won lines** | **172** | 100% |

**Mix essentially never rescues a line with no evidence — 2 out of 172.**
Every metric win in the table above (bail-recoveries, Domino, the crawl
fixes) came from mix *outbidding* a line that already had a real
placement, over half the time outbidding `transcribe` and roughly a third
of the time outbidding `align` — normally the single most-trusted source
(refined per-word timing from forced alignment). That is a materially
weaker and riskier kind of win than "the mix caught what the stem
missed," which was the plan's working hypothesis.

Two structural reasons this was always going to be the shape:

- Most `interp` (no-evidence) lines are **lyric-version overhang** — lines
  in the fetched lyric text that the song's actual performed audio doesn't
  contain (ad-libs, repeats, arrangement differences). No audio source,
  stem or mix, can place a line that isn't sung. Defying Gravity (38
  interp lines) and Bloodstream (24) are the two starkest examples.
- Mix candidate generation runs at the strict `0.34` edit-ratio gate (same
  rationale as ytasr — the ASR text is a mix candidate's only evidence for
  existing). Mix transcribe is the *same whisper model* as stem transcribe,
  just on a noisier signal. If the looser stem-transcribe gate (`0.75`)
  already found nothing for a line, the strict mix gate essentially never
  will either.

## Experiment B: corpus results

A/B'd `cue_mix_rescue` off vs. on across all 16 SRT-sourced songs (safety
invariant checked every time: every line outside the rescue ladder must
come back byte-identical between the two runs).

| song | fills (off→on) | mix ok/attempts | gap lines | instant lines | overlap | unsafe |
|---|---|---|---|---|---|---|
| Mirrors | 7→4 | **3/7** | 0 | 0 | 2.6s | 0 |
| For Good (OutOfOz) | 3→3 | 0/3 | 0 | 0 | 1.7s | 0 |
| Beauty and the Beast (Ariana/John Legend) | 4→4 | 0/4 | 0 | 0 | 0.2s | 0 |
| Incomplete | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| More Than That | 2→2 | 0/2 | 0 | 0 | 0.0s | 0 |
| Happier | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| Let It Go | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| Part of Your World | 2→2 | 0/2 | 0 | 0 | 0.7s | 0 |
| Like I Love You | 1→1 | 0/1 | 0 | 0 | 0.0s | 0 |
| Rock Your Body | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| Selfish | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| A Whole New World (Mena/Naomi) | 0→0 | 0/0 | 0 | 0 | 2.6s | 0 |
| Bye Bye Bye | 1→1 | 0/1 | 0 | 0 | 1.3s | 0 |
| Speechless | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| Can You Feel the Love Tonight | 0→0 | 0/0 | 0 | 0 | 0.0s | 0 |
| A Whole New World (ZAYN) | 1→1 | 0/1 | 0 | 0 | 7.5s | 0 |
| **corpus total** | **21 baseline fills** | **3/21 accepted (14%)** | 0 | 0 | — | **0** |

The safety invariant held perfectly (`unsafe=0` everywhere — the rung never
touches a line outside the rescue path). But the entire yield is **3
converted lines, all on one song** (Mirrors, the corpus's known-hardest
case — stacked quiet-chant vocals). The other 18 mix attempts were
correctly rejected by containment, not silently accepted. User eyeball of
the Mirrors conversion and two Experiment A flag songs judged the visible
difference not worth an extra full-mix decode + slice-align pass per bad
line, given how few lines are actually affected.

## Disposition

- `capture_mix_transcribe` and `cue_mix_rescue` stay `False` in
  `pikaraoke/pipeline/config.py`. No production code path calls them.
- The matcher's 4th source (`joint_match.py`) and the cue rung
  (`cue_align.py`) stay committed but dormant — reduces bit-identically
  to the 3-source/no-rung behavior with the knobs off, so there is nothing
  to revert.
- `scripts/replay_fullmix_source.py`, `scripts/cue_align_song.py`, and
  `scripts/cue_align_corpus.py` stay as offline harnesses; bundles keep
  `mix_transcribe_words`, so revisiting this question later needs no new
  GPU regen.
- LRCLIB stays a scoring-only reference, not a production input.

## Follow-on insight (not part of this plan)

The dominant source of unplaced (`interp`) lines is **upstream lyric-version
mismatch** — fetched lyric text containing lines the actual performed audio
doesn't have — not a lack of audio evidence. No amount of additional
whisper passes (mix, stem, or otherwise) fixes a line that was never sung.
If unplaced-line accuracy is revisited, the higher-leverage target is
lyric-version matching before alignment ever runs, not another audio
source at alignment time.
