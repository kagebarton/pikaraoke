# Reduce Refine Time Exploration

Model: Claude Opus 4.8

Goal: cut whisper **refine** inference time in the joint matcher. Refine is the
dominant GPU cost on full songs (measured 71% of the align+refine pass), and it
cannot be hidden behind other GPU work (concurrent inference is 3.6-11x slower
— see `matcher-timing-eval.md`), so the only way down is doing less refine work
or fewer refines.

## Where refine runs

`pikaraoke/pipeline/stages/lyric_align.py`, joint route: `align_check`
(`model.align`) → `refine_from_cached` (`model.refine(steps="se",
word_level=True)`) once per song, **plus once per suspect span** in windowed
re-align (`_realign_one_span`). The de-reverb retry re-runs the same legs on
the dry stem. Config lives in `RefineKwargs` (`config.py`).

Refine works by re-running the encoder per word-boundary per step: `steps="se"`
= refine starts then ends — two sweeps over all words. That per-word, per-step
scaling is why refine dominates on long songs (align is a single forced pass).

## Measured cost (2026-06-22, large-v3-turbo, probe_refine_cost.py)

Real song — Mirrors de-reverbed stem, 159 lines / 1203 words, production config:

| `steps` | align | refine | total | refine share |
| --- | --- | --- | --- | --- |
| `"se"` (current) | 63.3 s | 153.8 s | 217.1 s | **71%** |
| `"s"` (starts) | 63.8 s | 77.1 s | 140.8 s | 55% |

Synthetic 20 s / 60-word slice for contrast: refine only 39% (`se` 2.8 s) —
refine scales far worse with word count than align, so short slices badly
underestimate it. Always measure refine on a **full** song.

## Levers

### Lever 1 (primary): `steps` "se" → "s"

`RefineKwargs.steps` at `config.py:110`. Measured: refine 153.8 → 77.1 s
(**-50%**), whole align+refine pass 217 → 141 s (**-35%**, ~76 s/song). And it
compounds — windowed re-align refines every suspect span, so suspect-heavy
songs save again per span.

Low-risk *for karaoke specifically*: `"s"` keeps word **start** timing (what
drives line highlight/advance); only word-**end** precision degrades to
align-only, which karaoke barely uses (a line's end is usually defined by the
next line's start). But "low-risk" must be confirmed — refine-of-ends does
nudge timings. One-line change.

### Lever 2 (bigger, riskier): drop refine entirely (align-only)

Refine is 26-71% of the pass; the joint matcher already has align's word
timestamps and refine only nudges them. Dropping refine saves the full
77-154 s. Question: are align-only word timings good enough? This is a clean
eval ablation — disable `refine_from_cached` on the joint route and compare
placement metrics. If the metric delta is small, this is the biggest win.

### Lever 3 (secondary): attack align — now the floor

After Lever 1, align (~63 s) becomes the floor and refine (~77 s) is still the
long pole. Align levers: `token_step` (already raised to 150 — fewer alignment
passes), VAD coverage (`vad`, `only_voice_freq` gate the audio whisper sees).
Less promising than refine levers; revisit only if refine is minimized and
align dominates.

### Non-lever: parallelism

Cannot overlap refine with anything — concurrent GPU inference is 3.6-11x
slower on this card (no MPS on Windows). Ruled out by measurement.

## Validation plan

Run the corpus eval harness with `steps` variants (`"se"` baseline vs `"s"`,
and a refine-off arm for Lever 2). Compare:

- **Quality**: gross misplacements, median error, ≤1.0 s fraction, placed
  count — must not regress materially.
- **Cost**: per-phase wall-clock (`Phase.ALIGN_CHECK` vs `Phase.REFINE` are
  already separate scopes, so a real run surfaces the split).

Acceptance for Lever 1: corpus metrics hold within noise while refine wall-clock
roughly halves. If quality holds, also evaluate Lever 2 as the larger win.

## Implementation

Lever 1 is a one-line default change (`RefineKwargs.steps = "s"`). Lever 2 is a
route flag to skip `refine_from_cached`. Both gated behind the eval above —
ship nothing without corpus confirmation.

## Open questions

- Does `"s"` regress any song's placement (especially within-line word wipe
  timing)? Per-song eval, not just pooled. *(Answered: see Word-end drift —
  starts identical, end drift is tail-only with no clear regression.)*
- Is refine's marginal contribution to the metrics even worth its cost (Lever
  2)? If align-only is within noise, prefer it over `"s"`.
- Does `"e"`-only ever help a song `"s"` hurts? (Probe showed `s` and `e`
  equal cost; quality may differ.)

## Results (2026-06-22, corpus eval, large-v3-turbo)

Ran the quality+cost ablation: `scripts/probe_refine_quality.py` (one GPU pass
at `steps="s"` yields the S arm and, from `align_check`'s pre-refine words,
the OFF arm; SE reuses each bundle's cached `se`-refined words). 19 eligible
songs, scored against YT-SRT/LRCLIB with the production eval scorer. Raw JSON:
`scripts/refine_quality_results.json`.

**Structural finding (no GPU, the key result).** The joint matcher takes each
line's timing from *either* the align words (refine-affected) or the transcribe
words (refine-immune). Corpus-wide only **35.4%** of placed lines are
align-won (385/1088), and they cluster: a few songs are 73-87% align (Be Our
Guest, Belle, Hakuna Matata, ZAYN/Mena A Whole New World, In Summer, Ed
Sheeran), most are ~0% (Mirrors, Selfish, Let It Go, Speechless, …). Refine can
only ever move that ~third.

**Pooled placement (≤0.5 s / ≤1.0 s / gross, 19 songs):**

| arm | ≤0.5 s | ≤1.0 s | gross | med-of-med \|Δ\| |
| --- | --- | --- | --- | --- |
| SE (`se`, current) | 67.4% | 85.8% | 44 | 0.32 s |
| S (`s`, Lever 1) | 67.6% | 85.8% | 42 | 0.32 s |
| OFF (no refine, Lever 2) | 66.0% | 85.7% | 43 | 0.32 s |

- **Lever 1 (`se`→`s`): null on placement, ship it.** SE≈S pooled (and SE≡S on
  starts *by construction* — both refine starts identically; only the `e` sweep
  moves word **ends**, which a start-based metric can't see). Saves 50% of
  refine (median 36 s/song, ~690 s/corpus) at no line-start cost. Residual
  word-**end** drift is now measured directly (see Word-end drift below):
  tail-only, cosmetic, no clear regression.
- **Lever 2 (drop refine): not free.** Pooled ≤0.5 s drops 67.6→66.0 (−1.6 pt),
  ≤1.0 s and gross ~flat. The loss is concentrated on align-dominated songs'
  tight bucket: In Summer 66.7→53.3, The Next Ten Minutes 52.4→41.3, Hakuna
  44.4→38.9, Belle 63.9→60.2, Mena 82.1→78.6. Refine earns its keep on the
  ≤0.5 s precision for ~a third of the corpus; transcribe-won songs are
  unaffected (S≡OFF).

**Cost (19 songs):** align 223 s total (median 10 s/song); refine `s` 689 s
total (median 36 s/song); implied refine `se` ~1379 s (~2x by the steps
mechanic; single-song verified in `probe_refine_cost.py`).

## Word-end drift (2026-06-22, align-heavy corpus)

The quality eval scores line *starts*, so by construction it is blind to the one
thing Lever 1 changes: the dropped `e` sweep only moves word **ends**. This
probe measures that directly. There is no word-level ground truth (every corpus
reference is start-only), so it is a *relative* measurement — how far `s` ends
drift from `se` ends, not whether they are more correct.

`scripts/probe_refine_end_drift.py` runs two controlled GPU passes (steps="se"
then "s") that re-align the same vocal and pair words by index, with a per-song
determinism cross-check on the pre-refine baselines (max baseline skew 0.000 s,
start drift 0.000 s — pairing is exact). Scope: the 7 align-heavy songs, where
align words actually drive the displayed wipe; transcribe-dominated songs render
their lines from transcribe words, so align-end drift never reaches the screen.
Raw JSON: `scripts/refine_end_drift_results.json`.

**Ends do render.** The ASS karaoke generator (`lyric_align.py`) consumes word
ends three ways: the `\kf` fill-sweep duration is `end - start` (:388), the
silent `\k` gap before the next word is `next_start - this_end` (:391), and the
line event clears at `last_word.end + lead_out` (:378). End drift is visible,
not moot.

**Result (Δe = se_end − s_end; >250 ms = a visible move):**

| song | n | med\|Δe\| | p90\|Δe\| | max\|Δe\| | signed | >250 ms |
| --- | --- | --- | --- | --- | --- | --- |
| Be Our Guest | 472 | 0.000 | 0.026 | 0.768 | +0.000 | 2.3% |
| Belle | 614 | 0.000 | 0.034 | 2.301 | +0.000 | 2.8% |
| Hakuna Matata | 187 | 0.000 | 0.034 | 1.950 | +0.000 | 3.7% |
| In Summer | 205 | 0.000 | 0.047 | 0.500 | +0.000 | 3.9% |
| Ed Sheeran (Best Part) | 266 | 0.000 | 0.212 | 1.070 | +0.000 | 7.5% |
| A Whole New World (Mena) | 230 | 0.000 | 0.228 | 1.102 | +0.000 | 8.3% |
| A Whole New World (ZAYN) | 274 | 0.000 | 0.294 | 0.858 | +0.000 | 11.3% |
| POOLED (7) | 2248 | 0.000 | 0.115 | 2.301 | +0.000 | 5.0% |

- **Starts are identical** (`max|Δs| = 0.000`): both arms refine starts, so when
  each word lights up is unchanged. Only ends differ.
- **The median word end does not move** (0.000 everywhere). The change is a
  tail: 5% of words pooled move >250 ms, splitting by song type — crisp-diction
  Disney numbers 2-4%, held-note/melismatic ballads (both A Whole New World
  duets, Ed Sheeran live) 7-11%, exactly where sustained vowels give the `e`
  sweep something to do. No systematic direction (signed median 0.000).
- **What the tail looks like on screen:** for a held note align butts the end to
  the next onset, so under `s` the `\kf` wipe creeps slowly across the held word
  with no gap; under `se` the end is pulled back, so the word fills fast then
  sits lit through a dead `\k` gap. For a sustain, `s`'s slow creep arguably
  tracks the singing better. The one mildly-worse `s` case is a line-*final*
  over-extended word: the line lingers ~1-2 s longer before clearing (the
  max|Δe| 2.3 s outlier on Belle) — cosmetic late-clear, not a mistimed start.

Cost confirms the steps mechanic corpus-wide: se-refine 498 s vs s-refine 253 s
across the 7 songs = 1.97x.

## Status

**Lever 1 (`steps="se" → "s"`): shipped** — corpus line-starts hold, word-end
drift is tail-only with no clear regression, refine halves. One-line change at
`config.py:110` (`RefineKwargs.steps`).
**Lever 2 (drop refine): hold** — measurable ≤0.5 s regression on align-heavy
songs; only worth it if tight-bucket precision is deemed non-critical.
Reusable probes: `scripts/probe_refine_cost.py` (cost), `scripts/probe_refine_quality.py`
(quality+cost ablation), `scripts/probe_refine_end_drift.py` (word-end drift).
