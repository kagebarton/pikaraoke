# Edge snap: code review (interleaved mechanism + code view)

Two passes over the edge snap feature in `pikaraoke/lib/onset_snap.py`
(`snap_line_edges` / `snap_line_onsets` / `snap_line_ends`, wired into
`LyricAlignStage.run()` via `snap_line_edges` on the `onset_snap_on_ship`
branch). The first pass is written in mechanism terms; the second is the
code-level detail the mechanism maps to. Each numbered section pairs the two
so a reader can move freely between "what it does" and "where it lives."

## What the feature is

After whisper places word timings, the edge snap walks every lyric line and
repairs two systematic whisper errors using the vocal stem's loudness curve
(one decoded envelope, onsets first then ends so a pushed-forward start
widens the room the previous line's end may grow into):

- **Onset snap** — whisper smears an opening word's start back into the
  preceding instrumental gap. The detector finds the first genuine energy
  *rise* inside the smeared window and pulls the word start forward to it.
  Shifts are forward-only and bounded by word 2, so an on-time line is never
  damaged.
- **End snap** — whisper clips a sustained final word the moment its phonetic
  content stops while the singer still holds the note. The detector only
  acts when the voice is still loud at the claimed end (clip evidence), then
  follows the held note forward to where it actually fades. Extensions are
  forward-only and bounded by the next line's first word.

A rise qualifies only if it lands near the line's own sung level (so a quiet
reverb-tail bump mid-gap can't impersonate the voice); a soft-onset pickup
("I'm doing…") still counts if it then sustains at a steady level, while a
breath bump or reverb tail dies inside a couple frames and is rejected. The
line's sung-level reference is the median loudness over words 2..n — word 1
is excluded because its own span is the thing being repaired.

## 1. Stem-end truncation is indistinguishable from word-2 continuity

**Mechanism.** When a detected rise is too close to the end of the run, the
detector accepts it on trust — but it can't tell whether "too close" means
*continuous with the next word* (the intended exception, so a soft pickup
landing right against word 2 isn't rejected) or *the loudness curve itself
ran out* (a truncation artifact near the stem's end). Near-stem-end onsets
occasionally snap forward on that trust for the wrong reason.

**Code.** `onset_snap.py:170` —
```python
if b - i < sustain_frames or float(np.median(env[i:b])) >= ref - SUSTAIN_NEAR_DB:
    return i * HOP_S
```
`b` is `min(len(env) - EDGE_FRAMES, int(t1 / HOP_S))`: a short line near the
stem's end collapses `b` to `len(env) - EDGE_FRAMES` and the same "trust it"
branch fires. `test_soft_rise_just_before_word2_accepted` documents the
intended case but not the truncation case. Split the two: a collapse from
proximity to word 2 → trust on continuity grounds; a collapse from the
envelope running out → reject (onsets near stem-end are unreliable anyway).

## 2. End-side `n_fired` overcounts

**Mechanism.** A line that shows clip evidence but releases within whisper's
natural jitter is counted as "fired" yet produces no extension record, so
the telemetry reads "more lines fired than extended" with no explanation —
which makes tuning the jitter threshold from production data harder.

**Code.** `onset_snap.py:326` increments `n_fired` before the `MIN_SHIFT_S`
rejection at `342-344`. A correctly ended staccato line that fired on clip
evidence but whose release landed under the jitter threshold yields a fired
count with no `extends` entry. Move the increment below the `MIN_SHIFT_S`
gate, or add a `n_below_min_shift` counter — useful for tuning
`MIN_SHIFT_S` since `edge_snap_ass.py` already routes end-stats counters to
stdout (`62-66`).

## 3. End-snap sung-level reference excludes word 1 unnecessarily

**Mechanism.** The end snap borrows the onset snap's "exclude word 1" rule
for the sung-level reference, but the end snap has no onset-smear problem to
defend against — it could safely include word 1's span. That matters when a
line is mostly a long held final note with short preceding words: the
reference is then averaged over the clipped-but-still-singing tail alone.

**Code.** `onset_snap.py:310` calls `_sung_level_ref(env, words)` (`127`),
which slices `words[1:]` (`136`). Word 1's *end* is trustworthy — the onset
smear only stretches it backward (`onset_snap.py:237-243` carries end
forward precisely because the tail is fine) — so an `end=True` variant
including `words[0]` when `w1e - w1s > MIN_WORD_DUR_S` would be a strictly
better reference for the end path.

## 4. The silence-floor guard is asymmetric between the two edges

**Mechanism.** Only the end snap rejects lines mis-placed over digital
silence, where "near sung level" would be trivially true and every relative
check degenerates. The onset snap relies on its on-time guard coincidentally
firing to skip the same case, which works today but not for the documented
reason — a symmetric gate would make both paths reject silence on purpose
and surface a clear "low-reference" count on the onset side too.

**Code.** `onset_snap.py:314-317` checks `if ref < MIN_REF_DB` on the end
path only. The onset path's on-time guard (`220-225`) partly compensates
(skip when near sung level at the claimed start and across the span) but
that's safe by luck, not design — over near-silence the reference drags to
the floor and the guard becomes trivially true. Add the same `MIN_REF_DB`
gate to `snap_line_onsets`; `n_low_ref` already exists in end stats, onset
stats needs its own.

## 5. The pre-onset lead margin can light up empty silence

**Mechanism.** The karaoke cue is snapped a bit *before* the detected rise so
the highlight catches the attack, but the rise is already detected via a
3-frame averaging window before the candidate frame, so the margin can push
the cue into frames where no energy has arrived yet — a brief empty lit-up
word at the line start.

**Code.** `onset_snap.py:53` (`SNAP_MARGIN_S = 0.05`) and the clamp at
`232` (`min(max(onset - SNAP_MARGIN_S, w1s), w2s - MIN_WORD_DUR_S)`). With a
25 ms hop and 50 ms margin that's two frames of empty lead-in past the
already-smoothed `_detect_rise` window (`158-159` uses a 3-frame mean
before `i` as `pre`). Consider a single-frame margin or snapping to
`i * HOP_S` directly. `test_reverb_tail_start_snaps_to_rise` asserts
`2.15` (rise at 2.2) — it's a deliberate tuning knob, so change it via a
comment in the test, not silently.

## 6. Telemetry is one-sided across the two edges

**Mechanism.** The offline A/B tool reports fired/extended and low-reference
counts for the end snap but only a snapped count for the onset snap, so the
onset side's on-time-vs-silence-skip breakdown is invisible when tuning
thresholds available in both paths.

**Code.** `edge_snap_ass.py:62-66` prints `n_low_ref`/`n_fired`/`n_extended`
for ends but only `n_lines`/`n_snapped` for onsets. Onset stats
(`onset_snap.py:251-258`) lack the `n_fired`/`n_low_ref` symmetry the end
path has. Mirroring the end-side counters would make offline tuning of
`NEAR_SUNG_DB`/`MIN_REF_DB` data-driven instead of eyeballed.

## Priority

1. **#4** (symmetric silence gate) — clear safety improvement, smallchange.
2. **#1** (split the `b - i < sustain_frames` short-circuit) — real
   correctness near stem end.
3. **#2** (`n_fired` overcount) — telemetry accuracy for tuning.
4. **#3** (end-snap reference could include word 1) — accuracy on
   melisma-heavy lines.
5. The rest are polish/telemetry.

## Bottom line

The design is sound and the failure-mode tests are thorough (reverb tails,
breath bumps, melismas, tremolo dips, envelope-end truncation). None of the
items above are show-stoppers; the biggest correctness risk today is #1's
stem-end collapse being indistinguishable from the intended word-2
continuity case, and #4's asymmetric silence gate being safe by luck rather
than by design.
