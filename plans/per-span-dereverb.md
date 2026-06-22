# Per-Span De-Reverb Exploration — MEASURED, REJECTED

Model: Claude Opus 4.8

Status: **rejected 2026-06-22.** Both forms below were measured against
the corpus and buy nothing (or regress). Mirrors-class failures are not
reverb-starved *sections* — they are whisper misses on overlapped/buried
audio that de-reverb does not address. Repeated-chant / buried-backing
lines belong to the text-timing prior, not an audio retry.

## Hypothesis (what this set out to fix)

The shipped whole-song gate (`dereverb_yield_wpm`, default 30) fires only
when the *entire* stem starves transcribe (Bubble: 14.4 wpm). Mirrors
transcribes at 76 wpm overall — above the gate — yet its outro chant
blocks desync. Whole-song de-reverb fixes Mirrors but regresses 8
previously-clean songs (de-reverb removes real content on dry stems),
which is why it's gated, not defaulted. The hypothesis: a *per-span*
de-reverb retry could recover Mirrors-class failures without touching
clean audio — de-reverb only the suspect spans the windowed re-align
already isolates.

## What was measured

Two forms, both built on the existing windowed re-align (which already
slices suspect spans between trusted anchors and re-aligns them):

1. **de-reverb + align** — de-reverb the suspect slice, then
   `align_check` + `refine` on the dry slice (the original "no new
   whisper" design: corroborate against the whole-song `transcribe_words`
   windowed to the span).
2. **de-reverb + re-transcribe** — de-reverb the suspect slice, then
   *re-transcribe* it (new whisper) to regenerate the section-local
   corroboration the windowed re-align needs where the wet transcribe
   starved.

Both were driven against the real pipeline code (`windowed_realign.py`,
`whisper_worker.py`) using the pre-rendered whole-song de-reverb stems in
`pikaraoke-songs/dereverb/`, scored on the `eval_alignment.py` harness.
(Throwaway probe scripts; deleted after measuring.)

## Findings

### Form 1 (de-reverb + align): net-negative

- **Mirrors:** dry-vs-wet windowed re-align moved 1 line by 80 ms; gross
  1 → 1. The failing chant lines are unplaced by audio in *both* arms.
- **Corpus sweep (16 songs):** pooled gross **20 → 21**, ≤1.0 s **90.1%
  → 89.8%**. One marginal win (Speechless gross 2→1), two regressions
  (Hakuna gross 3→4; ZAYN gross 1→2, 19 lines moved), the rest unchanged.
  De-reverb strips real content at slice scale — the same mechanism that
  gated whole-song de-reverb, now leaking in per-span.

### Form 2 (de-reverb + re-transcribe): recovers nothing

Probed the 5 most suspect-heavy corpus songs (Mirrors, Beauty and the
Beast, Mulan, Mena — A Whole New World, Hakuna Matata). For every suspect
span with placeable-but-unplaced lyric lines, compared how many of those
lines' words a fresh **wet** vs **dry** slice transcribe recovers:

- De-reverb recovered **zero** additional lyric lines on any span across
  all five songs (max Δ +1 word, within noise). Unrecovered lines stay
  unrecovered wet *and* dry.
- **Hakuna tell:** its span heard *more* words dry (188 → 207) yet
  recovered the *same* lyric content (2/5). De-reverb manufactures
  spurious non-lyric words that then mismatch the sheet — exactly why it
  regresses.
- Fresh slice transcribe doesn't even beat the status quo: the windowed
  whole-song transcribe (today's corroboration source) generally yields
  *more* words than a fresh slice transcribe.

### Root cause: suspect ≠ reverb

Direct evidence from the Mirrors outro: a fresh transcribe of the
*de-reverbed* chant section hears the **lead** vocal ("my reflection in
everything I do"), not the backing **chant** ("you are the love of my
life"). The chant is acoustically subordinate within the same stem — a
source-separation / overlap problem, not reverb. De-reverb (and any
re-transcribe) leaves it untouched. The same pattern holds across the
other four songs: the unplaced lines are buried / overlapped / ambiguous
(repeated identical lines, instrumental-over-vocal), never reverb-washed.

## Verdict

Rejected. Per-span de-reverb solves a problem the corpus doesn't have.
The whole-song gate stays the only de-reverb path — it fires only when
the *entire* stem starves transcribe (a genuine reverb failure);
section-level misses are a different failure mode.

Repeated-chant / buried-vocal outros belong to the SRT/LRCLIB text-timing
prior, which already places them by text position. The only audio lever
that could move them is true vocal sub-separation (lead vs backing) — a
separate, much larger effort, out of scope here.
