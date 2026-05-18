Model: Claude Opus 4.7

# Alignment-debug capture for offline knob tuning

## Context

The walk matcher ([word_alignment.py](../pikaraoke/lib/word_alignment.py)) and tiling matcher ([tiling_match.py](../pikaraoke/lib/tiling_match.py)) expose a dozen-plus tunable knobs (lookaheads, confirm_matches, interp/collapse caps, edit-ratio threshold, anchor-fallback floor, window slacks). Defaults were set by intuition; we want to tune them against the real corpus pikaraoke processes. Re-running whisper for every knob value is prohibitive, so the rollout needs to capture *enough state per song* that future tuning can replay either matcher offline.

## What landed (commit `bc3f72f`)

A new `LyricAlignStage` side-effect writes one JSON bundle per song to `<song_dir>/alignment_debug/<stem>.json`. Toggled by `PipelineConfig.capture_alignment_debug: bool = True` (default on for rollout, flip off later).

### Per-song bundle (schema_version 3)

- **`config`** — `match_method`, `align_failure_escalation`, full `whisper` config via `dataclasses.asdict(cfg.whisper)` (load_model / align / transcribe / refine / post-process kwargs / regroup).
- **`lyrics`** — `origin` (`"genius" | "srt" | "override" | "none"` from `ctx.artifacts["lyrics_origin"]`), `source_path`, `source_kind`, the full `lines` and `align_lines`.
- **`pipeline_decisions`** — `align_check_fail_ratio`, `method_used` (`"walk" | "tiling" | "transcribe"`), `escalated_to_tiling`.
- **`words`** — verbatim whisper word list (`{word, start, end}`) handed to the matcher. Critical: with this + `lines` + `align_lines`, either matcher can be replayed offline at any knob values.
- **`words_source`** — `"refine"` (walk) or `"transcribe"` (tiling).
- **`walk_stats`** — only when walk ran. Knobs snapshot, aggregate counts (`matched_count`, `whisper_consumed`, `collapsed_tokens`, `dropped_tokens`), per-run length lists (`collapsed_run_lengths`, `interp_run_lengths`, `dropped_run_lengths`), parallel per-run index lists (`collapsed_token_indices`, `dropped_token_indices`) pinning the exact lyric tokens affected, raw walker `mapping: list[int | None]` (per-token whisper-word index, captured pre-demotion), and `empty_line_reasons: dict[line_id, "no_normalizable_tokens" | "all_tokens_dropped"]` distinguishing structural-junk lyric lines from interp-cap drops.
- **`tiling_stats`** — only when tiling ran. Knobs snapshot, candidate counts (`candidates_main`, `candidates_anchor`), `zero_candidate_unit_ids` + `anchor_recovered_unit_ids` (which lines failed/recovered, not just counts), per-unit distributions (`per_unit_candidate_counts_main`, `per_unit_candidate_counts_anchor`, `per_unit_best_score`) indexed by `unit_id` for spotting chorus-flood units and overlap-loss cases, `units` array mapping `unit_id` → `{line_id, text}` (resolves paren-split units), and `selected_windows: list[{unit_id, line_id, score, width, start_idx, end_idx}]` for every chosen tiling interval.
- **`output_summary`** — `line_count`, `lines_with_words`, `first_line_start`, `last_line_end`, `median_words_per_sung_line`.
- **`output_line_timings`** — per-line `{line_id, start, end, n_words}` the matcher emitted. Lets offline analysis compare against the YT SRT for songs where one exists independently of the lyric source.
- **`ground_truth_refs`** — `youtube_srt_present`, `youtube_srt_is_lyric_source` (resolved-path equality check — circular cases null out `youtube_srt_path` so analysis skips them).

### Code changes

- **New:** [pikaraoke/lib/alignment_capture.py](../pikaraoke/lib/alignment_capture.py) — `build_bundle()`, `write_bundle()`, `output_line_timings()`, `summarize_line_objects()`. Atomic write via `.tmp` → rename.
- **[word_alignment.py](../pikaraoke/lib/word_alignment.py):** extracted body into `match_words_to_lines_with_stats()` returning `(line_objects, stats)`; original `match_words_to_lines` is now a thin wrapper that drops stats. Stats include per-run length lists collected inline during the existing collapse / interp / drop loops.
- **[tiling_match.py](../pikaraoke/lib/tiling_match.py):** same pattern — `match_words_to_lines_tiling_with_stats()` returning `(line_objects, stats)`. `zero_candidate_unit_ids` always computed (even when `anchor_fallback=False`).
- **[pipeline/config.py](../pikaraoke/pipeline/config.py):** new `capture_alignment_debug: bool = True` knob.
- **[pipeline/stages/lyric_align.py](../pikaraoke/pipeline/stages/lyric_align.py):** scratchpad locals populated through both walk and tiling paths, written via new `_write_debug_capture()` after ASS/SRT promotion. Capture errors are logged and swallowed — capture failure must never fail the pipeline.

### Test status

943/943 tests pass; pre-commit clean. Existing public matcher signatures unchanged, so no test updates were needed.

## Why this shape

Three deliberate calls worth recording:

1. **Save inputs, not just outputs.** The bundle preserves the whisper word list verbatim so any future knob sweep can recompute stats offline. Saving only the as-run stats would let us evaluate the current config but not search neighboring knob values — which is the whole point of the corpus.
2. **Schema versioning, not field stability.** `SCHEMA_VERSION` is bumped on field rename/removal; additive fields are allowed without a bump. Bumped twice during this session (1 → 2 added tiling unit ids; 2 → 3 added `output_line_timings`, `empty_line_reasons`, `lyrics.origin`, full whisper config).
3. **Pointer, not copy, for YT SRT ground truth.** The bundle records `youtube_srt_path` only when the SRT is independent of the lyric source. The file is already on disk; embedding its contents would just bloat the bundle.

## What this enables

For each captured song the offline tuner can now:

- **Replay either matcher** at swept knob values against the saved `words` + `lines` to recompute stats.
- **Bucket by `lyrics.origin`** to ask questions like "does tiling escalate more often on Genius than YT-SRT lyrics?"
- **Compare per-line timings to YT SRT** when `youtube_srt_present && !youtube_srt_is_lyric_source` (3 of 4 sample captures qualify).
- **Identify width-1 false-positive selected_windows** (sample: Wicked, `line_id 90` "Down!" selected 6× scattered through the song) as concrete tuning targets for short-line suppression.
- **Distinguish lyrics-parser issues from matcher-knob issues** via `empty_line_reasons` (sample: NSYNC has 7 `no_normalizable_tokens` entries, all from `[`, `]`, `(`, `)` Genius parser artifacts — not a tuning signal).

## Out of scope (deferred)

- **Per-candidate edit-distance distribution** for tiling — replay handles this, no need to bloat the bundle.
- **Which align_check segments failed** — informs escalation tuning but requires plumbing into the whisper worker.
- **Audio duration** — inferable from `last_line_end` plus a small margin.
- **Tuner itself** — this session was about capture only. The corpus analyzer (load every bundle, sweep knobs, compute aggregates) is the next workstream.

## Commit

`bc3f72f` on branch `removediarize`: `feat(lyric-align): capture per-song alignment debug data for offline knob tuning`
