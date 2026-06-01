# Alignment-Capture Schema — Session Briefing

Model: Claude Opus 4.7

Self-contained reference covering the alignment-debug bundle schema, the
v3→v4 work + later additive enrichments done in this session, and the
offline scripts that produce/consume bundles. Paste into a fresh session
to resume schema-related work without re-deriving the state from scratch.

---

## 1. What the bundles are

One JSON file per processed song at:

```
/home/ken/pikaraoke-songs/alignment_debug/<song_stem>.json
```

Written by `pikaraoke/lib/alignment_capture.py:write_bundle()` at the end
of `LyricAlignStage.run()` when `PipelineConfig.capture_alignment_debug`
is True. Purpose: **preserve the matcher inputs verbatim** so either the
walk, tiling, or joint matcher can be re-run offline at future knob
values without paying for whisper inference again.

Backups taken during enrichment runs sit at
`/home/ken/pikaraoke-songs/alignment_debug.bak.*` — multiple snapshots
from different enrichment passes.

---

## 2. Schema version 4 (current) and history

`SCHEMA_VERSION = 4` in `pikaraoke/lib/alignment_capture.py`.

| Version | What it added (per the in-file changelog) |
|---|---|
| **v1** | initial |
| **v2** | tiling per-unit fields: `units`, `zero_candidate_unit_ids`, `anchor_recovered_unit_ids`, `selected_windows` (replacing `window_widths`) |
| **v3** | `output_line_timings`, `walk_stats.empty_line_reasons`, `lyrics.origin`, full `config.whisper` snapshot |
| **v4** | tiling scores are raw matched-token counts `n − dist` (not normalized ratios). Affects `tiling_stats.selected_windows[].score`, `per_unit_best_score[]`, `selected_score_sum`. Score range went from `[0, 1]` to `[0, n]`. |

**Policy.** Renames/removals bump the version. Additive new fields don't.

---

## 3. Additive fields since v4 (no bump)

Added during this session's work — schema_version stays 4 because each
is a brand-new optional field that pre-existing consumers can safely
ignore.

### From the corpus-enrichment passes (pre-joint-matcher)

- `walk_stats.loss_spans` — structured failed-token runs, populated by
  the current walk matcher in `lib/word_alignment.py`. Each entry is
  `{token_start, token_end, line_start, line_end, t0, t1, kind, recovered}`.
  Originally added on the now-superseded sectional-tiling-repair branch;
  enrichment regenerated it for every bundle so all 23 carry current-code
  loss spans.
- `walk_stats.align_words` *(only on the 7 tiling-method bundles)* — the
  align word list captured by an offline `align_check` rerun. Production
  tiling runs don't normally produce these; the offline backfill added
  them so the joint matcher can route those songs.
- `walk_stats.align_fail_ratio` *(only on the 7 above)* — fail-ratio
  from the offline align rerun.
- `walk_stats.walk_input_words_source` — string pointing to where the
  matcher should read its align words from for this bundle:
  - `"bundle.words"` for the 16 walk-method bundles
  - `"walk_stats.align_words"` for the 7 tiling-method bundles
- `walk_stats.recheck_provenance` — human-readable note describing how
  this `walk_stats` was produced (current matcher regen, offline align
  recheck, etc.).
- `pipeline_decisions.tiling_recheck_provenance` *(only on Mulan and
  Pocahontas)* — recorded when `finalize_v4.py` regenerated their
  `tiling_stats` from saved transcribe words using the current matcher
  (v3 normalized scores → v4 raw counts). For Pocahontas specifically
  this also shifted the line count 38 → 37 due to the DP selection
  change.

### From the joint-matcher work (this session, later)

Added in `pikaraoke/pipeline/stages/lyric_align.py` commit `7b17cb2`,
threaded through `alignment_capture.build_bundle()`:

- `pipeline_decisions.joint_alpha` — the α value the joint matcher ran
  with (e.g. `2.0` after corpus tuning). Set only when
  `pipeline_decisions.method_used == "joint"`.
- **top-level `joint_stats`** — the `joint_stats` dict from
  `lib/joint_match.py::match_words_to_lines_joint_with_stats()`. Contains
  `selected_source` (per-line `"align" | "transcribe" | "interp" | "absent"`),
  per-line candidate counts, `align_won`, `transcribe_won`,
  `interpolated_line_ids`, `absent_line_ids`, `selected_score_sum`, and
  the knobs that ran.
- **top-level `transcribe_words`** — the transcribe word list the joint
  matcher consumed alongside align. Stored separately so on joint runs
  both align AND transcribe words are saved verbatim (top-level `words`
  continues to hold the align/refine words).
- Populated *outside the live pipeline too* by the α-sweep script — for
  the 16 walk-method bundles that lacked transcribe, the sweep ran
  offline `transcribe_words(refine=False)` and persisted the result back
  under this field. Idempotent — subsequent sweep runs read the cached
  words instead of re-decoding.

---

## 4. Top-level bundle structure (current)

```json
{
  "schema_version": 4,
  "song_stem": "...",
  "captured_at": "2026-05-23T12:34:56+00:00",
  "config": { ... },                   // config snapshot incl. whisper kwargs
  "lyrics": {
    "origin": "genius" | "srt" | "unknown",
    "source_path": "...",
    "source_kind": "txt" | "srt" | ...,
    "lines": [...],                    // display text per lyric line
    "align_lines": [...]               // paren-stripped per lyric line
  },
  "pipeline_decisions": {
    "align_check_fail_ratio": float | null,
    "collapse_ratio":         float | null,
    "method_used": "walk" | "tiling" | "joint" | "transcribe" | "walk+repair",
    "escalated_to_tiling":   bool,
    "escalation_trigger":    str | null,
    "joint_alpha":           float | null,   // additive, joint runs only
    "tiling_recheck_provenance": str | null  // additive, only on regenerated tiling bundles
  },
  "words":         [...],              // refined align words (walk/joint) or transcribe words (tiling)
  "words_source":  "refine" | "transcribe",
  "walk_stats":    { ... } | null,     // populated on walk/joint routes
  "tiling_stats":  { ... } | null,     // populated on tiling route
  "joint_stats":   { ... } | null,     // additive, joint runs only
  "transcribe_words": [...] | null,    // additive, joint runs (or cached by enrichment)
  "output_summary":      { ... },
  "output_line_timings": [...],
  "ground_truth_refs":   { ... }       // YouTube SRT presence/path/is-lyric-source
}
```

### `walk_stats` sub-structure (current)

```json
{
  "knobs": { lyric_lookahead, whisper_lookahead, confirm_matches, ... },
  "n_words": int,
  "n_lines": int,
  "n_tokens": int,
  "matched_count": int,
  "whisper_consumed": int,
  "collapsed_tokens": int,
  "dropped_tokens": int,
  "collapsed_run_lengths": [int, ...],
  "interp_run_lengths":    [int, ...],
  "dropped_run_lengths":   [int, ...],
  "collapsed_token_indices": [[int, ...], ...],
  "dropped_token_indices":   [[int, ...], ...],
  "mapping": [int, ...],               // token → whisper-word index
  "lines_with_words": int,
  "empty_line_reasons": { "<line_id>": "all_tokens_dropped" | ... },
  "early_return": bool,
  "loss_spans": [                       // additive since v4
    {"token_start", "token_end", "line_start", "line_end",
     "t0", "t1", "kind", "recovered"}, ...
  ],
  "align_words": [...] | null,         // additive, tiling-bundle enrichment
  "align_fail_ratio": float | null,    // additive, tiling-bundle enrichment
  "walk_input_words_source": str,      // additive enrichment
  "recheck_provenance": str            // additive enrichment
}
```

### `joint_stats` sub-structure (added this session)

```json
{
  "knobs": { alpha, margin_s, max_edit_ratio, lookahead, anchor_fallback },
  "n_lines": int,
  "n_align_words": int,
  "n_transcribe_words": int,
  "n_main_candidates": int,
  "n_anchor_candidates": int,
  "n_align_candidates": int,
  "n_selected": int,
  "selected_source": ["align" | "transcribe" | "interp" | "absent", ...],
  "align_won": int,
  "transcribe_won": int,
  "interpolated_line_ids": [int, ...],
  "absent_line_ids": [int, ...],
  "selected_score_sum": float
}
```

---

## 5. Bundle enrichment scripts (in `/tmp`, scratch only)

These existed when the 23-song corpus was being prepared. Reproducible
if someone wants to redo any enrichment — but the bundles on disk
already carry the outputs.

| Script | What it did |
|---|---|
| `/tmp/corpus_route_analysis.py` | Re-ran walk matcher on saved align words for the 16 walk-method bundles; printed per-song loss profile and routing under various thresholds. |
| `/tmp/align_recheck.py` | First pass at offline `align_check()` for the 7 tiling-method bundles (no walk_stats originally). Recorded route under the old routing logic. Did *not* persist align words. |
| `/tmp/corpus_combined.py` | Combined the 16 walk-bundle re-runs + 7 align-recheck results to print the unified routing picture across α/cap sweeps. |
| `/tmp/enrich_bundles.py` | **The big enrichment pass.** Backed up `alignment_debug/`, then for every bundle (1) regenerated `walk_stats` via the current matcher with `loss_spans`; (2) for the 7 tiling-method bundles, ran offline `align_check` again and persisted `align_words`, `align_fail_ratio`, `walk_input_words_source`, `recheck_provenance` into `walk_stats`. Schema stays v4 (additive). |
| `/tmp/finalize_v4.py` | Brought all bundles to `schema_version=4`. For walk bundles (tiling_stats=None): nominal version bump 3→4. For v3 tiling bundles (Mulan, Pocahontas): regenerated `tiling_stats` + `output_line_timings` + `output_summary` via the current matcher (v4 raw-count scoring). Added `tiling_recheck_provenance` to `pipeline_decisions`. Pocahontas's tiling output shifted 38 → 37 lines under the new DP. |
| `/tmp/joint_alpha_sweep.py` | α-sweep for the joint matcher. Loads every bundle, derives `align_words` + `transcribe_words` (offline-transcribes the 16 walk-method bundles to populate top-level `transcribe_words` — first run is GPU, subsequent runs read the cached field). Then for each α ∈ {1,2,4,6,8,12,16} runs `match_words_to_lines_joint_with_stats` per song and prints corpus totals + per-song flip counts + a Hakuna-specific diagnostic. |

After all enrichment passes:

- **All 23 original bundles** at schema_version 4
- **16 walk-method bundles** carry refined align in top-level `words` and have `transcribe_words` populated by the sweep
- **7 tiling-method bundles** carry transcribe in top-level `words`, plus `walk_stats.align_words` from the offline align rerun

---

## 6. Dual-word-list convention (joint matcher)

The bundle has historically had one `words` slot + a `words_source`
discriminator. Joint matching needs both align and transcribe words.
The convention now:

- **For walk/joint routes**: top-level `words` = refined align;
  `words_source = "refine"`. The additive `transcribe_words` field
  carries the transcribe pass.
- **For tiling routes**: top-level `words` = transcribe (production
  tiling input); `words_source = "transcribe"`. The 7 enriched bundles
  also have `walk_stats.align_words` for completeness.

A reader code path that wants align words for the joint matcher should
read whichever of `walk_stats.align_words` or top-level `words` is
populated for that bundle. `joint_alpha_sweep.py:derive_align_transcribe()`
shows the resolver:

```python
def derive_align_transcribe(b):
    ws = b.get("walk_stats") or {}
    align = ws.get("align_words") or b.get("words")
    transcribe = b.get("transcribe_words")
    if transcribe is None and b.get("words_source") == "transcribe":
        transcribe = b["words"]
    return align, transcribe
```

This dual-storage approach is the additive-field route to avoid bumping
the schema while supporting the joint matcher's requirement. If/when
walk and tiling matchers are retired (joint becomes the only matcher),
a v5 bump can unify the structure (`words` → `align_words`, top-level
`transcribe_words` becomes mandatory).

---

## 7. When to bump the version

- **No bump** when adding a new optional top-level or nested field.
  Document under "Additive since vN" in `alignment_capture.py`.
- **Bump** when renaming, removing, or changing the semantics of an
  existing field. Add a new section to the in-file changelog comment.

Past examples:
- v3 → v4 was bumped because tiling-stat *scores* changed semantics (the
  consumer-facing meaning of `score` flipped from a ratio in `[0, 1]`
  to a raw count in `[0, n]`).
- v4 → v4 (additive) covered the loss_spans + repair_ranges + joint_stats
  + transcribe_words additions in this session.

---

## 8. Open items related to schema

- **Possible v5 bump** when the joint matcher becomes the default and
  walk/tiling are retired. Likely refactor: rename top-level `words` to
  `align_words` for clarity; make `transcribe_words` mandatory; drop
  `words_source` (becomes implicit). Defer until that retirement happens.
- **Pocahontas tiling regen note**: the on-disk bundle's tiling output
  differs from the original production `.ass` for that song (38→37 lines)
  because v4 raw-count scoring changes DP selection. This is documented
  in the bundle's `pipeline_decisions.tiling_recheck_provenance`. If the
  user re-processes Pocahontas, the new `.ass` will match the v4 output.

---

## 9. Quick-reference: dump a bundle's shape

```bash
/home/ken/miniconda3/envs/pik/bin/python -c "
import json, glob
b = json.load(open(sorted(glob.glob('/home/ken/pikaraoke-songs/alignment_debug/*.json'))[0]))
def shape(x, depth=0):
    pre = '  ' * depth
    if isinstance(x, dict):
        for k, v in x.items():
            if isinstance(v, (dict, list)):
                t = type(v).__name__
                n = len(v)
                print(f'{pre}{k}: {t}[{n}]')
                if depth < 1 and isinstance(v, dict):
                    shape(v, depth+1)
            else:
                print(f'{pre}{k}: {type(v).__name__} = {repr(v)[:50]}')
shape(b)
"
```

---

This briefing is itself committed in `plans/alignment-capture-schema.md`.
