# Sectional Tiling Repair (windowed merge, "#2")

Model: Claude Opus 4.7

## Motivation

Escalation today is a whole-song switch: walk XOR tiling. But alignment
quality is not uniform — forced alignment fails in pockets (repetitive
sections, dialogue, key changes) while the rest of the song aligns
cleanly. The binary forces a bad trade: to fix the broken 10% we discard
the working 90%, and whole-song tiling then introduces its *own* errors in
regions walk handled perfectly.

Observed on "The Next Ten Minutes" (whole-song tiling run), all in regions
walk handled correctly:

- line 7 `Cathy` dropped (ASR heard "Kathy" → zero candidates)
- line 27 matched twice (chorus reprise pulled a duplicate)
- a `Thank you` hallucination at 363–372 (spoken outro)

**Principle:** trust forced alignment where it succeeded; fall back to free
decoding only where it failed. Repair the failed *spans* in place; keep
walk everywhere else.

We are well-positioned for this because the failure is already localized:
`walk_stats` carries `collapsed_token_indices` / `dropped_token_indices`,
and the bracketing matched anchors give the audio time window (the 38-token
solo sits cleanly between `I` ending 201.06 and `Jamie` starting 225.14).

## Scope

This plan covers **#2, the windowed merge**: transcribe the whole song
once, but tile only the failed spans against the transcribe words whose
timestamps fall in each span's audio window, then splice back by line_id.

**Seam for #3 (clip re-decode), later:** the repair routine acquires its
words through a single provider `words_for_window(t0, t1) -> list[word]`.
In #2 that provider filters the one whole-song transcribe. In #3 it becomes
a clip transcribe (`transcribe_words` over an extracted `[t0,t1]` wav).
Everything downstream (window → tile → remap → splice) is identical, so #3
is a provider swap, not a re-architecture. Keep that boundary clean.

## Decision routing (in `LyricAlignStage.run`, auto mode)

Route on **missing sections**, not whole-song ratios. The old 10–15%
`fail_ratio` / `collapse_ratio` gates over-triggered: diffuse small
collapses are handled fine by walk's interpolation (1–2 token gaps between
tight anchors interpolate accurately), so escalating for them was a net
loss. The only thing that warrants leaving walk is a *big contiguous hole*.

Computed on the **pre-refine** quick walk (cheap, before paying refine):

1. Build concentrated failed line-ranges (**merge-then-threshold** — see
   "Repair threshold floor"): map every collapsed-or-dropped token run to
   its lyric lines, merge adjacent ranges, then keep a merged range only if
   its *combined* failed-token count ≥ `concentration_escalation_run`. Two
   adjacent sub-`N` collapses thus combine instead of both being missed.
2. No ranges → **keep walk**. (Sub-threshold scattered collapses stay on
   walk; interpolation already covers them.)
3. Ranges cover > `repair_max_line_fraction` of lines → **whole-song
   tiling**. (The "broken basically everywhere" backstop — discard align,
   skip refine. This is the diffuse-ratio gate's one legitimate role,
   re-expressed as coverage instead of a token ratio.)
4. Otherwise → **repair** the ranges.

`fail_ratio` and `collapse_ratio` are **dropped as routing gates** but still
captured (telemetry), so we can retroactively check whether any kept-walk
song should have escalated and add a targeted rule if a real case appears.

`method_used` values become: `walk`, `walk+repair`, `tiling`.

## Repair threshold floor (`concentration_escalation_run`)

Two floors matter when picking `N`:

- **Mechanical floor (~2–3 tokens):** below this tiling can't form a
  candidate, so a repair attempt is a guaranteed no-op. `find_candidates`
  needs `min(2, n)` real overlap (a 2-token line needs an exact both-token
  hit); `find_anchor_candidates` needs a 3-token contiguous run
  (`min_run_floor=3`) and skips any line with `n < 3`. A sub-3-token span
  has nothing to grip — tiling finds nothing and the splice keeps walk's
  interpolation anyway. Setting `N` below ~3 only burns transcribe cost.
- **Practical floor (~one line, 6–8 tokens):** below a full line, walk's
  interpolation is already accurate (short run between tight anchors, a
  ~2s window with little for ASR to add). Repairing there is all downside —
  tiling can drop / duplicate / mis-place a line that wasn't broken. Interp
  only loses to ASR when a run spans **more than a line**, or one line
  stretched over a large gap with internal pauses linear interp can't
  reproduce (the 38-word / 24s case).

So **~3 is the hard floor, ~6–8 is the practical floor, 10 is a safe
default.** Two things shift it:

- **Merge-then-threshold:** apply `N` to *merged* adjacent line-ranges, not
  individual runs, so two adjacent sub-`N` collapses combine instead of both
  being missed. Recommended — it closes part of the pervasive-medium-collapse
  gap (Open Questions) while keeping the "big section" intent.
- **The splice fallback makes a low `N` wasteful, not wrong:** keeping walk's
  line whenever tiling finds nothing means a too-low `N` never corrupts
  output — worst case it spends a transcribe and changes nothing. So the only
  cost of lowering `N` is compute (one whole-song transcribe under #2; a cheap
  clip under #3) plus a small risk of tiling worsening a line it *does* find
  but interp would have nailed. This is why `N` can safely drift lower once
  clip transcription lands.

## Repair algorithm

Entered only on the repair route.

1. **Refine + walk (full).** `refine_from_cached` → `words` →
   `match_words_to_lines_with_stats` → final `line_objects` (1:1 with lyric
   lines; good lines already accurate) + post-refine `walk_stats`.
   Windows come from post-refine timing, so recompute spans here rather
   than reusing the pre-refine routing estimate.

2. **Build repair ranges** from post-refine `walk_stats.loss_spans` (new
   field, below). A repair range is a maximal contiguous block of lyric
   *lines* touched by any concentrated failed token-run; adjacent failed
   spans merge. For each range `[L0, L1]`:
   - **lines** = display/align lines `L0..L1`.
   - **audio window** `[t0, t1]` = `(end of last good line < L0,
     start of first good line > L1)`. "Good line" = a line not in any
     repair range and with real (non-empty) timing. One-sided at song
     boundaries (`t0 = 0.0`, `t1 = last word end`).

3. **Transcribe once (whole song)** → `transcribe_words` (already exists).

4. **Per range, repair:**
   - `window_words = words_for_window(t0, t1)` — in #2: `[w for w in
     transcribe_words if t0 - margin <= w["start"] <= t1 + margin]`
     (small `margin`, e.g. 0.3s, to avoid clipping a boundary word).
   - `match_words_to_lines_tiling_with_stats(window_words, lines[L0:L1+1],
     align_lines[L0:L1+1])` → repair objects with line_id relative to the
     sublist; **remap** absolute = line_id + L0.
   - **splice with per-line preference:** for each absolute line_id in
     `L0..L1` — if the repair produced object(s) for it, use them; else
     keep walk's existing object for that line_id. A repair must never
     make a line *disappear* that walk had (the Cathy/Kathy case): mis-timed
     -but-present beats absent.

5. **Reassemble** `line_objects` in lyric order: walk lines `0..L0-1`, then
   the range's spliced objects (repeat objects sorted by start), then walk
   lines `L1+1..`, across all ranges. Times stay monotonic because each
   range's objects fall inside `[t0,t1]`, between its good neighbors.

## Per-file changes

### `pikaraoke/lib/word_alignment.py`

Add `loss_spans` to walk_stats: structured contiguous failed-token runs the
stage can map to lines + audio windows without re-deriving. Each entry:

```
{
  "token_start": int, "token_end": int,   # half-open token range
  "line_start": int, "line_end": int,      # inclusive lyric-line range
  "t0": float, "t1": float,                # bracketing anchor times
  "kind": "collapsed" | "dropped",
  "recovered": bool,                        # interpolated (collapsed) vs absent
}
```

The interp/drop loop already computes `prev_end` / `next_start` per run —
record them there. `line_start/line_end` from `lyric_tokens[k].line_idx`.
Keep the existing `collapsed_*` / `dropped_*` fields (additive). `loss_spans`
supersedes them for span work but the raw lists stay for telemetry.

### `pikaraoke/lib/tiling_match.py`

**No change for #2.** The stage pre-filters words and remaps line_ids;
tiling already accepts an arbitrary `words` list and `lines`/`align_lines`.
(If we later want tiling to own the time filter, add an optional
`time_window` param — but not required here.)

### `pikaraoke/pipeline/stages/lyric_align.py`

- New decision function returning one of `keep_walk | whole_tiling | repair`.
- `_repair_spans(line_objects, walk_stats, transcribe_words, lines,
  align_lines) -> line_objects` implementing window → tile → remap → splice.
- `_words_for_window(words, t0, t1, margin)` — the #3 seam.
- `_splice_range(...)` — per-line preference + reassembly.
- Capture: thread repair metadata into the bundle (below).

### `pikaraoke/pipeline/config.py`

- Reuse `concentration_escalation_run` as the span-detection threshold —
  the one routing knob now.
- New `repair_max_line_fraction: float = 0.5` — above this line coverage,
  prefer whole-song tiling over piecemeal repair.
- New `repair_window_margin_s: float = 0.3` — boundary slack for the word
  time-filter.
- `align_failure_escalation` and `collapse_escalation_threshold` are no
  longer read by routing. Keep them (still recorded in the capture config
  snapshot for telemetry) or remove once concentration-only routing is
  validated against the corpus.

### `pikaraoke/lib/alignment_capture.py`

`pipeline_decisions` gains (additive — schema stays v4):

```
"repair_ranges": [
  {"line_start", "line_end", "t0", "t1",
   "lines_repaired", "lines_kept_from_walk", "window_word_count"}
],
```

`method_used` gains the `walk+repair` value (string, additive). No bump
(rename/removal only). Note the new value in the changelog comment.

## Edge cases

- **Song-boundary range:** one-sided window (`t0=0` or `t1=last word end`).
- **Empty window / tiling finds nothing:** keep walk's (interpolated) lines
  for the whole range — never regress to absent.
- **Adjacent failed ranges:** merge before windowing.
- **Partially-failed line** (some tokens matched, some collapsed): the whole
  line is in the range and is re-tiled in full; walk's surviving fragment is
  replaced if tiling finds the line.
- **Repeated lyrics inside the window:** the window is tight, but a chorus
  line sung twice in-window yields two objects — acceptable (tiling already
  emits repeats).
- **Range covers most of the song:** routed to whole-song tiling by
  `repair_max_line_fraction` before we get here.

## Cost

- **keep walk:** align + refine. No transcribe. (unchanged)
- **whole-song tiling:** align_check + transcribe. No refine; discards
  align. (unchanged)
- **repair:** align + refine + transcribe (whole song, time-filtered per
  span). Both passes — only on concentrated-partial songs. The whole-song
  transcribe is the wasteful part #3 later removes (clip transcribe).

Clean songs (the majority) never pay for transcribe.

## Testing

Unit:
- `loss_spans` computation: collapsed run → correct token/line range, `t0/t1`
  from bracketing anchors, `recovered` flag; dropped run likewise.
- Decision routing: no ranges → keep_walk; concentrated span in healthy
  song → repair; merged ranges over coverage cap → whole_tiling.
- `_words_for_window`: inclusive bounds + margin.
- `_splice_range`: tiling-found replaces; tiling-missing keeps walk;
  in-window repeat preserved; line/temporal order after reassembly.
- End-to-end repair via mocked worker: align words with a collapsed span +
  clean transcribe words in-window → final line_objects keep walk's good
  lines and adopt tiling's timing for the repaired range.

Regression: existing escalation tests adjust — `concentration`-only trips
now route to `repair` (assert `transcribe` + splice), not whole-song tiling.

## Staging

1. Add `loss_spans` to walk_stats (+ tests). No behavior change yet.
2. Add the `words_for_window` / splice / tiling-remap helpers (+ tests),
   pure functions, no orchestration wired.
3. Rework `LyricAlignStage.run` routing + `_repair_spans` (+ tests).
4. Capture fields + config knobs + docs.
5. Switch routing to concentration-only: `concentration` selects repair,
   coverage cap selects whole-song tiling, and the `fail_ratio` /
   `collapse_ratio` routing gates are removed (kept only as captured
   telemetry).

## Open questions

All three are answerable directly from the capture bundles (their purpose).
The values below are priors to ship with, to be confirmed against the corpus.

- `concentration_escalation_run` (`N`, 10 tokens ≈ 1–2 lines) and
  `repair_max_line_fraction` (0.5). With the ratio gates gone, `N` is the
  main dial.
  **Recommendation:** keep `N=10` under #2 — every repaired song pays a
  whole-song transcribe, so only genuine multi-line holes should trip it,
  and 10 sits safely above the ~6–8 practical floor. Drop it toward ~6 once
  #3 (clip transcribe) lands: the splice fallback makes a low `N` only
  wasteful, never wrong, and a clip is cheap. For the coverage cap, if
  anything *raise* it (→0.6), don't lower it — repair is strictly safer than
  whole-song tiling (it never drops a walk line), and under #2 the compute is
  nearly identical (both pay one transcribe; repair also pays refine), so the
  cap only marks where refine is wasted, which is high. A rarely-hit
  backstop; don't over-tune it.
- **Pervasive medium collapse:** many runs each just under `N`, collectively
  large but separated by thin good slivers, so they neither merge nor clear
  the coverage cap. Concentration-only routing keeps walk (lines present but
  linearly smeared in many places) — the dropped `collapse_ratio` gate used
  to catch this. Merge-then-threshold does *not* close it (the runs aren't
  adjacent). Watch for such a capture (Pocahontas may be one — check its
  run-length distribution).
  **Recommendation:** if real, route it to **repair, not whole-song tiling**
  — the old gate's discard-and-tile was the wrong (destructive) response to a
  mostly-working walk. Signal on the *total tokens in runs ≥ a per-run floor*
  (~4–5), not the raw loss ratio (which over-triggers on benign 1-token gaps
  — why the ratio gate was dropped); if that filtered total exceeds a
  fraction (reuse `0.15` as the prior, tuned on Pocahontas), repair every
  such run (the splice fallback keeps it safe). Measure first, though: if the
  good slivers are typically one line wide, the lighter fix is to let the
  merge bridge a single good line — adjacent-modulo-one runs then combine and
  clear `N` with no new gate.
- Margin vs boundary-word clipping — validate `repair_window_margin_s` (0.3).
  **Recommendation:** leave it; it's a guard rail, not a dial. `t0`/`t1` are
  the end/start of the bracketing *good lines*, so the failed words already
  sit inside `[t0, t1]` — the margin only catches a boundary word whose
  timestamp drifted slightly past a neighbor. The real risk is a margin too
  *large* (it pulls neighbor words in, and tiling can mis-assign one for
  repeated lyrics), so keep it small (≤ 0.5s). Revisit only if a captured
  repaired range shows a clipped first/last word.

When the corpus is in hand, the analysis that settles all three: per song,
re-derive merged-range failed-token totals and the medium-run total, sweep
`N` and the coverage cap, and print the route each song would take. The knee
sets `N`; the "keeps walk but high medium-run total" rows are the
pervasive-collapse population.
