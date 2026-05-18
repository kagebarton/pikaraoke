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

SCHEMA_VERSION = 3


def build_bundle(
    *,
    song_stem: str,
    config_snapshot: dict[str, Any],
    lyrics: dict[str, Any],
    pipeline_decisions: dict[str, Any],
    words: list[dict] | None,
    words_source: str | None,
    walk_stats: dict | None,
    tiling_stats: dict | None,
    output_summary: dict[str, Any],
    output_line_timings: list[dict],
    ground_truth_refs: dict[str, Any],
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
        "pipeline_decisions": pipeline_decisions,
        "words": words or [],
        "words_source": words_source,
        "walk_stats": walk_stats,
        "tiling_stats": tiling_stats,
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

    Walk line_objects have implicit line_id (position == line_id) since
    they're 1:1 with the lyric line list. Tiling line_objects carry an
    explicit ``line_id`` field and may repeat or skip. Either shape is
    handled here.
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
