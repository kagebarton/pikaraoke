"""Debug capture for offline tuning of lyric-alignment knobs.

Writes one JSON bundle per processed song into ``alignment_debug/`` next
to the ``karaoke/`` and ``subtitles/`` dirs. The bundle preserves the
exact matcher inputs (whisper word list + lyric lines) plus the knob
values and per-pass telemetry that came out of the run.

Why save the inputs verbatim: with them, either matcher can be re-run
offline at any future knob values to recompute stats — without paying
for whisper again. Stats alone would let us evaluate the as-run config
but not search neighboring knob values.

Schema version is bumped whenever a field is renamed/removed. New
optional fields don't bump the version.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# v7: YouTube ASR promoted from a timing prior to the joint matcher's third
#     candidate source; all timing-prior post-processing removed. A milestone
#     bump (run-affecting) — regen treats v6 bundles as stale and reprocesses.
#     Removed fields: joint_stats.{srt_prior, lrclib_prior}, lyrics.lrclib, and
#     config_snapshot.{joint_srt_prior, joint_lrclib_prior}. Added:
#   - lyrics.ytasr: for txt-sourced songs whose YouTube ASR caption was adopted
#     — {asr_file (relative path to the persisted <song>/subtitles/
#     <stem>.en.asr.json3), n_words, wpm}.
#   - config_snapshot.joint_beta: the YTASR agreement weight, symmetric to
#     joint_alpha.
#   - joint_stats gains the third-source counts the matcher emits
#     (n_ytasr_words, n_ytasr_candidates, ytasr_won) on adopted-caption runs.
# v6: walk and tiling matchers removed — the joint matcher is the sole
#     alignment path. Removed fields: walk_stats, tiling_stats (top-level),
#     and config.match_method / config.align_failure_escalation /
#     config.collapse_escalation_threshold from config_snapshot, plus
#     pipeline_decisions.align_check_fail_ratio / collapse_ratio /
#     escalated_to_tiling / escalation_trigger. joint_stats is now always
#     present on alignment-mode captures.
#     Also closes the offline-replay gaps for the post-pass-1 stages — with
#     these the whole alignment pipeline replays from the bundle alone, no
#     inference and no user input. Added:
#   - joint_stats.pass1_line_timings: line timings (line_id/start/end/
#     n_words, the shape of top-level output_line_timings) snapshotted
#     right after the pass-1 joint DP — before windowed re-align and the
#     timing priors mutate the placements. The baseline an offline pass-1
#     re-run validates against; output_line_timings holds the FINAL
#     (post-realign, post-prior) placements, which diverge whenever either
#     ran.
#   - joint_stats.windowed_realign.spans: per-span replay inputs so the
#     windowed re-align replays offline with no inference. One entry per
#     re-aligned span, in merge order: the span geometry (lid_lo/lid_hi/
#     anchor_lo/anchor_hi/t0/t1) plus align_words — the slice's refined
#     align words shifted to absolute song time, or null when the slice
#     align failed/was skipped (span kept pass-1). Feed each through
#     windowed_realign.replay_span + merge_spans (with top-level words/
#     transcribe_words) to reproduce the merged placements.
#   - joint_stats.{srt_prior,lrclib_prior}.cue_spans_by_line: the offset-
#     uncorrected per-line cue spans the prior actually consumed, keyed by
#     line id (string), values [start, end] in seconds. Makes the prior
#     replayable from the bundle alone — no re-reading the SRT/.lrc, no
#     re-running cue cleaning.
#   - lyrics.genius: for genius-origin songs, the chosen Genius identity —
#     {id, title, artist}. Lets a regen re-fetch the lyrics / re-query LRCLIB
#     deterministically instead of re-prompting for an artist-title search.
#     Absent on songs from other origins and on bundles written before this
#     field shipped.
# v5: LRCLIB timing prior shipped to production. A milestone bump even
#     though the changes are additive — it marks the first run-affecting
#     matcher change since v4. Added:
#   - lyrics.lrclib: for txt-sourced songs, the chosen LRCLIB variant —
#     {lrc_file (relative path to the persisted <song>/lyrics/<stem>.lrc),
#     record (the specific search result: id/trackName/artistName/albumName/
#     duration), query}.
#   - joint_stats.lrclib_prior: the prior's per-song stats, parallel to
#     joint_stats.srt_prior. On a successful apply: offset_s/mad_s/
#     n_anchors_fit/n_snapped/n_filled (+ snapped/filled line ids). On
#     bail-out: only n_anchors_fit + bailed (the reason), same shape as
#     srt_prior.
#   - media_duration_s: source media duration (ffprobe), the LRCLIB
#     selection tiebreak and a drift-aware-eval input.
#   - config_snapshot now records the joint/prior knobs that shape output:
#     joint_alpha, joint_margin_s, joint_max_edit_ratio, joint_srt_prior,
#     joint_lrclib_prior.
# Additive since v4 (no bump — additions only):
#   - joint_stats: stats dict from the joint matcher
#     (lib/joint_match.py:match_words_to_lines_joint_with_stats), captured
#     when pipeline_decisions.method_used == "joint".
#   - transcribe_words: the transcribe word list the joint matcher consumed
#     alongside the align words (top-level ``words`` field continues to
#     hold the align/refine words on joint runs). Both sources are saved
#     verbatim so the joint matcher can be re-run at future α values
#     without paying for whisper.
# v4: tiling scores are raw matched-token counts (n - dist), not
#     normalized ratios. Previously score in [0, 1]; now score in [0, n].
#     Affects tiling_stats.selected_windows[].score,
#     tiling_stats.per_unit_best_score[], tiling_stats.selected_score_sum.
# v3: added output_line_timings, walk_stats.empty_line_reasons,
#     lyrics.origin, full config.whisper snapshot.
# v2: added tiling per-unit fields (units, zero_candidate_unit_ids,
#     anchor_recovered_unit_ids, selected_windows replacing window_widths).
# v1: initial.
SCHEMA_VERSION = 7


def build_bundle(
    *,
    song_stem: str,
    config_snapshot: dict[str, Any],
    lyrics: dict[str, Any],
    pipeline_decisions: dict[str, Any],
    words: list[dict] | None,
    words_source: str | None,
    output_summary: dict[str, Any],
    output_line_timings: list[dict],
    ground_truth_refs: dict[str, Any],
    joint_stats: dict | None = None,
    transcribe_words: list[dict] | None = None,
    media_duration_s: float | None = None,
) -> dict[str, Any]:
    """Assemble the capture dict. Pure — no I/O.

    Returns a JSON-serialisable dict; the caller writes it.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "song_stem": song_stem,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": config_snapshot,
        "lyrics": lyrics,
        "media_duration_s": media_duration_s,
        "pipeline_decisions": pipeline_decisions,
        "words": words or [],
        "words_source": words_source,
        "joint_stats": joint_stats,
        "transcribe_words": transcribe_words,
        "output_summary": output_summary,
        "output_line_timings": output_line_timings,
        "ground_truth_refs": ground_truth_refs,
    }


def _json_default(obj: Any) -> Any:
    """Coerce the numpy scalars/arrays the matcher stack leaks into the bundle.

    Word timings come off stable-ts as ``np.float64`` and propagate into every
    derived stat (a fitted offset's ``np.bool_``, line start/end floats). The
    default JSON encoder rejects those, so a stray numpy value would sink the
    best-effort capture write; ``.item()``/``.tolist()`` land native types.
    """
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_bundle(song_path: Path, bundle: dict[str, Any]) -> Path:
    """Write the bundle to ``<song_dir>/alignment_debug/<stem>.json``.

    Returns the written path. Overwrites any existing capture for this
    song so re-processing always reflects the latest run.
    """
    debug_dir = song_path.parent / "alignment_debug"
    debug_dir.mkdir(exist_ok=True)
    out = debug_dir / f"{song_path.stem}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    tmp.replace(out)
    return out


def output_line_timings(line_objects: list[dict]) -> list[dict]:
    """Per-line start/end the matcher emitted, for offline comparison
    against an independent reference (e.g. a non-circular YouTube SRT).

    Joint line_objects carry an explicit ``line_id`` field; the fallback
    to positional index keeps this robust to any line-object shape.
    """
    out: list[dict] = []
    for idx, obj in enumerate(line_objects):
        out.append(
            {
                "line_id": obj.get("line_id", idx),
                "start": obj.get("start"),
                "end": obj.get("end"),
                "n_words": len(obj.get("words", [])),
            }
        )
    return out


def summarize_line_objects(line_objects: list[dict]) -> dict[str, Any]:
    """Cheap aggregate summary of the final line_objects."""
    sung = [o for o in line_objects if o.get("words")]
    summary: dict[str, Any] = {
        "line_count": len(line_objects),
        "lines_with_words": len(sung),
        "first_line_start": sung[0]["start"] if sung else None,
        "last_line_end": sung[-1]["end"] if sung else None,
    }
    if sung:
        word_counts = sorted(len(o["words"]) for o in sung)
        summary["median_words_per_sung_line"] = word_counts[len(word_counts) // 2]
    else:
        summary["median_words_per_sung_line"] = None
    return summary
