# End-snap: code review and review fixes

Model: Claude Opus 4.8

Working record for the session that code-reviewed the line-end snap
(`snap_line_ends` / `snap_line_edges`, committed on `onset_snap_on_ship`) and
folded the accepted fixes back into the feature commit.

## What end-snap is

`pikaraoke/lib/onset_snap.py` — `snap_line_ends(line_objects, vocal_path, env=None)`,
the mirror of the line-initial onset snap for line ends, wired into
`LyricAlignStage.run()` via `snap_line_edges` (onsets then ends, one envelope
decode) right before ASS generation.

**Artifact it fixes:** the last word of a line is clipped short. Whisper
truncates a held line-final word once its phonetic content stops (nothing
anchors the end through a sustained vowel), so the karaoke fill finishes while
the note still sounds — 29% of corpus line-ends (527/1788) show clip evidence.

**Detector:** for each line still near its own sung level at the claimed end
(clip evidence), trace the voiced run forward to its first *sustained* fall
(below `ref - SUSTAIN_NEAR_DB` for `RELEASE_SUSTAIN_S`) and push the end there.
Gated on clip evidence and then tracing an already-voiced run, it needs no
model of hold duration. Extensions are **extend-only** and bounded by the next
line's first word, so a correctly ended line is never made worse — and the
detector structurally cannot recreate the clipped-short artifact.

## The review

`/code-review` at xhigh: 4 finder agents (2 correctness, robustness,
simplicity/conventions) → 17 verified candidates (3-state vote) → a gap sweep
that added 2. 13 findings reported, most-severe first.

## Fixes applied (folded into the feature commit)

### 1. Wet-stem exposure (top finding, gap-sweep)

`run()` binds `vocal_wav = ctx.artifacts["vocal_wav"]` (the wet stem) once. The
de-reverb gate's dry-stem substitution happens inside `_run_joint` /
`_run_cue_align` and never propagated back, so on a gate-tripped song alignment
used the *dry* stem while the edge snap read the *wet* one. The onset rise
detector tolerated this — a reverb tail decays monotonically and cannot fake a
rise — but the release detector needs a `SUSTAIN_NEAR_DB` *fall*, which a
reverb tail defeats: held ends would extend through the tail toward the bound.
This exposure was new with end-snap.

Fix: `_dereverb_gate` now records `ctx.artifacts["aligned_stem"] = <adopted
stem>` at its single decision point, and `run()` snaps against
`ctx.artifacts.get("aligned_stem", vocal_wav)`. Transcribe mode never gates, so
`aligned_stem` stays unset and it falls back to the wet stem it transcribed.

### 2. Full-window release trace (two findings, one change)

The release window `env[i : i + release_frames]` was not clipped at the bound
`b`, so windows near `b` read up to 0.175 s of the *next* line's audio (masking
a genuine release into an extend-to-bound), and on the song's last line the
window truncated to as few as one frame (degenerating the "sustained 0.2 s
below ref" test so a single tail fade-dip registered as a release).

Fix: `for i in range(e, b - release_frames + 1)` — only full-length windows
that stay within `[e, b]` are tested. A line whose next line starts within
~0.35 s can't fit a full release window and safely extends to the bound rather
than trusting a truncated one.

**Corpus impact** (isolated end-snap A/B, `scripts/end_snap_ass.py`, 33 songs /
1788 lines): to-bound 178 → 242, extended 413 → 431. Both moves are the fix
working: near-boundary releases that can't be confirmed with a full window now
extend safely (extend-only) to the bound. Extension-size median / p90 / max are
unchanged (0.53 / 1.98 / 5.95 s) — the real belted holds are untouched.

### 3. Capture schema bump v7 → v8

The commit renamed `joint_stats.onset_snap` → `joint_stats.edge_snap` and
reshaped it to `{onset, end}` without bumping `SCHEMA_VERSION`, contra the
module's own policy ("bumped whenever a field is renamed/removed") and the v7
precedent that treated `joint_stats` sub-keys as bump-worthy. Left as-is, the
regen staleness gate would treat pre-end-snap v7 bundles (old key, un-extended
ends) as current. Fixed: `SCHEMA_VERSION = 8` with a v8 changelog entry.

### 4. Deduplication (CLAUDE.md refactor-when-touching)

- `_decode_env(vocal_path, label)` collapses the decode-or-bail block that had
  reached three copies (onsets / ends / edges), differing only in log prefix.
- `_sung_level_ref(env, words)` collapses the byte-identical words-2..n median
  reference that both snaps compute; the cross-pass invariant was a comment.

### 5. Offline-script cleanups

- The lib records `extends[].to_bound = (new_end == bound)`; the script reads it
  instead of re-deriving the flag with a magic 0.03 s tolerance (dropped the
  `NEXT_LINE_GAP_S` import).
- `main()` no longer counts a bailed (decode-failed) song in `totals["songs"]`.
- `SKIP_SUFFIXES` and `_fmt` are shared from the sibling `onset_snap_ass.py`
  (whose stale list was missing `.endsnap`/`.fullmix` — un-staled).
- E731 lambda → `def pct`; `chmod +x` to match the sibling's 100755 mode.

## Skipped (agreed with the user)

- **MIN_REF_DB bleed gap** — the -45 dB floor catches lines misplaced over
  near-silence but not over steady instrumental bleed above the floor, where
  the same ref-relative degeneration drags the end to the bound. No absolute
  envelope floor can catch bleed, and a dynamic-range heuristic without corpus
  evidence risks suppressing real extensions. This is the upstream
  line-misplacement problem (the Belle / Next Ten Minutes class). Only the
  comment was narrowed to stop claiming "instrumental" coverage.
- **Per-song exception isolation and the `-OO` docstring crash** in the offline
  script — impossible states for the pipeline's own callers, and both match the
  pre-existing sibling.

## Refuted with evidence (not acted on)

- **Line-ordering assumption** — every producer emits time-monotonic
  lines-with-words (joint DP tiling is non-overlapping + monotonic;
  interpolated placeholders carry `words: []` and are skipped; realign is
  containment-gated). The bound scan's first-following-line-with-words is safe.
- **ASS event overlap from to-bound extensions** — 81% of adjacent line pairs
  already overlap pre-commit via the 0.8 s lead-in; Normal collision stacking
  is this renderer's standard two-line display, held for each event's lifetime.
- **Truncated-stem clamp scenario** — unreachable: the `MIN_SHIFT_S` guard plus
  same-audio timestamps make it arithmetically impossible.
- **edge_snap bail-shape duality** — the capture field is write-only telemetry;
  no code reads it back, and the shape matches the pre-existing onset contract.

## Verification

1315 tests (+1 regression: tail fade-dip at the envelope end must not read as a
release). Pre-commit clean on all six files. Corpus A/B re-run succeeded.

The feature + fixes are one coherent commit on `onset_snap_on_ship`. Remaining
roadmap item: fold `onset_snap_on_ship` into `pathed_align_ship`.
