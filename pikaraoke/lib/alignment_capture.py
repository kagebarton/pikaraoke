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

logger = logging.getLogger(__name__)

# v6: walk and tiling matchers removed — the joint matcher is the sole
#     alignment path. Removed fields: walk_stats, tiling_stats (top-level),
#     and config.match_method / config.align_failure_escalation /
#     config.collapse_escalation_threshold from config_snapshot, plus
#     pipeline_decisions.align_check_fail_ratio / collapse_ratio /
#     escalated_to_tiling / escalation_trigger. joint_stats is now always
#     present on alignment-mode captures.
# v5: LRCLIB timing prior shipped to production (plans/lrclib-timing-prior.md,
#     step 3). A milestone bump even though the changes are additive — it
#     marks the first run-affecting matcher change since v4. Added:
#   - lyrics.lrclib: for txt-sourced songs, the chosen LRCLIB variant —
#     {lrc_file (relative path to the persisted <song>/lyrics/<stem>.lrc),
#     record (the specific search result: id/trackName/artistName/albumName/
#     duration), query}.
#   - joint_stats.lrclib_prior: the prior's per-song stats, parallel to
#     joint_stats.srt_prior. On a successful apply: offset_s/mad_s/
#     n_anchors_fit/n_snapped/n_filled/snap_enabled. On bail-out: only
#     n_anchors_fit + bailed (the reason), same shape as srt_prior.
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
SCHEMA_VERSION = 6


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


def write_bundle(song_path: Path, bundle: dict[str, Any]) -> Path:
    """Write the bundle to ``<song_dir>/alignment_debug/<stem>.json``.

    Returns the written path. Overwrites any existing capture for this
    song so re-processing always reflects the latest run.
    """
    debug_dir = song_path.parent / "alignment_debug"
    debug_dir.mkdir(exist_ok=True)
    out = debug_dir / f"{song_path.stem}.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
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
