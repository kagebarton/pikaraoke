#!/usr/bin/env python3
"""Replay the alignment matcher chain from captured debug bundles — no whisper.

Re-runs the *post-whisper* alignment (joint match -> windowed re-align -> timing
prior -> optional .ass) straight from each song's
``alignment_debug/<stem>.json``, reusing the captured align/transcribe word
lists, realign span words, and inlined cue spans. A matcher/prior code change can
then be re-validated across the whole corpus in seconds, with no GPU — the slow
whisper passes are read back from the bundle instead of recomputed.

What is exact vs approximate:

  * **Joint match** and the **timing prior** replay exactly — both consume only
    captured inputs (``words``/``transcribe_words`` and the prior's inlined
    ``cue_spans_by_line``), and the prior re-derives its own offset/MAD gate.
  * **Windowed re-align** replays from each span's captured refined ``align_words``
    via ``replay_span`` + ``merge_spans``. This is exact for prior-only changes.
    For a *matcher* change it is only approximate: the span boundaries and suspect
    set were chosen from the original pass-1, so they do not move here (faithfully
    re-deriving them would need fresh audio slices). Use ``--no-realign`` to
    compare pass-1 only when iterating on the matcher.

Mirrors ``LyricAlignStage._run_joint``'s post-whisper chain; keep in sync if that
orchestration changes.

Run from the repo root::

    python scripts/replay_alignment_from_bundle.py [PATH] [--write] [--no-realign]

``PATH`` is a song-library folder (scans ``<PATH>/alignment_debug/*.json``) or a
single bundle ``.json``. Default prints a before/after summary; ``--write``
regenerates ``karaoke/<stem>.ass`` (the existing file is backed up alongside it).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as ``python scripts/replay_alignment_from_bundle.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.joint_match import (  # noqa: E402
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.srt_prior import apply_srt_prior  # noqa: E402
from pikaraoke.lib.windowed_realign import merge_spans, replay_span  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402

# A placed line sweeping slower than this many seconds per lyric word reads as a
# crawl (the artifact this harness exists to measure). Matches the diagnosis
# band: corpus crawls are >=1.9 s/word, legit lines <=1.3 s/word.
CRAWL_S_PER_WORD = 1.5

# Bundle prior key -> the provenance tag apply_srt_prior stamps.
_PRIOR_SOURCES = {"srt_prior": "srt", "ytasr_prior": "ytasr", "lrclib_prior": "lrclib"}


def replay_bundle(bundle: dict, *, realign: bool = True) -> list[dict]:
    """Replay match -> re-align -> prior from one bundle; return line objects.

    Args:
        bundle: a parsed ``alignment_debug/<stem>.json``.
        realign: replay the captured re-align spans (skip for matcher iteration).

    Reuses the matcher knobs exactly as captured (``joint_stats.knobs``); the
    re-align and prior steps run only when the bundle recorded them.
    """
    transcribe_words = bundle["transcribe_words"]
    lines = bundle["lyrics"]["lines"]
    align_lines = bundle["lyrics"]["align_lines"]
    knobs = bundle["joint_stats"]["knobs"]

    line_objects, _stats = match_words_to_lines_joint_with_stats(
        bundle["words"],
        transcribe_words,
        lines,
        align_lines,
        alpha=knobs["alpha"],
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
        lookahead=knobs["lookahead"],
        anchor_fallback=knobs["anchor_fallback"],
    )

    if realign:
        line_objects = _replay_realign(bundle, line_objects, transcribe_words, lines, align_lines)

    return _replay_prior(bundle, line_objects, transcribe_words, lines, align_lines, knobs)


def _replay_realign(bundle, line_objects, transcribe_words, lines, align_lines):
    """Replay captured re-align spans over pass-1 via replay_span + merge_spans."""
    spans = (bundle["joint_stats"].get("windowed_realign") or {}).get("spans")
    if not spans:
        return line_objects
    knobs = bundle["joint_stats"]["knobs"]
    results = []
    for span in spans:
        span_words = span.get("align_words")
        if span_words is None:
            results.append(None)
            continue
        results.append(
            replay_span(
                span,
                span_words,
                transcribe_words,
                lines,
                align_lines,
                alpha=knobs["alpha"],
                margin_s=knobs["margin_s"],
                max_edit_ratio=knobs["max_edit_ratio"],
            )
        )
    return merge_spans(line_objects, spans, results, len(lines), bundle["words"])


def _replay_prior(bundle, line_objects, transcribe_words, lines, align_lines, knobs):
    """Re-apply whichever timing prior the bundle recorded, from its inlined cues.

    Returns the prior's output, or ``line_objects`` unchanged when the bundle
    recorded no prior (or no cue spans to replay).
    """
    js = bundle["joint_stats"]
    prior_key = next((k for k in _PRIOR_SOURCES if k in js), None)
    if prior_key is None:
        return line_objects
    serial = js[prior_key].get("cue_spans_by_line")
    if not serial:
        return line_objects
    cue_spans = {int(lid): tuple(span) for lid, span in serial.items()}
    out, _stats = apply_srt_prior(
        line_objects,
        transcribe_words,
        lines,
        align_lines,
        cue_spans,
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
        source=_PRIOR_SOURCES[prior_key],
    )
    return out


def summarize(line_objects: list[dict]) -> dict:
    """Crawl/overlap metrics for a set of placed line objects."""
    placed = sorted((o for o in line_objects if o.get("words")), key=lambda o: o["start"])
    overlaps = [placed[i]["end"] - placed[i + 1]["start"] for i in range(len(placed) - 1)]
    crawls = [o for o in placed if (o["end"] - o["start"]) / len(o["words"]) > CRAWL_S_PER_WORD]
    return {
        "n_placed": len(placed),
        "max_overlap": max(overlaps, default=0.0),
        "n_crawl": len(crawls),
    }


def _old_summary(bundle: dict) -> dict:
    """Crawl/overlap metrics from the bundle's recorded final timings."""
    olt = [e for e in bundle["output_line_timings"] if e["n_words"] > 0]
    olt.sort(key=lambda e: e["start"])
    overlaps = [olt[i]["end"] - olt[i + 1]["start"] for i in range(len(olt) - 1)]
    crawls = [e for e in olt if (e["end"] - e["start"]) / e["n_words"] > CRAWL_S_PER_WORD]
    return {"n_placed": len(olt), "max_overlap": max(overlaps, default=0.0), "n_crawl": len(crawls)}


def _write_ass(bundle_path: Path, song_root: Path, line_objects: list[dict]) -> Path:
    """Regenerate karaoke/<stem>.ass, backing up any existing file."""
    stem = bundle_path.stem
    stage = LyricAlignStage(whisper_worker=None, config=PipelineConfig())
    ass = stage._generate_ass(line_objects)
    out = song_root / "karaoke" / f"{stem}.ass"
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        shutil.copy2(out, out.with_suffix(f".ass.bak.{ts}"))
    out.write_text(ass, encoding="utf-8")
    return out


def _iter_bundles(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    debug_dir = path / "alignment_debug" if path.name != "alignment_debug" else path
    return sorted(debug_dir.glob("*.json"))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("path", type=Path, help="song-library folder or a single bundle .json")
    ap.add_argument(
        "--write", action="store_true", help="regenerate karaoke/<stem>.ass (backs up the old file)"
    )
    ap.add_argument(
        "--no-realign",
        action="store_true",
        help="pass-1 only; skip the re-align replay (matcher iteration)",
    )
    args = ap.parse_args()

    bundles = _iter_bundles(args.path)
    if not bundles:
        print(f"No bundles found under {args.path}", file=sys.stderr)
        return 1

    print(f"{'song':46s} {'overlap':>14s} {'crawls':>9s}  {'placed':>9s}")
    print("-" * 84)
    for bp in bundles:
        bundle = json.loads(bp.read_text(encoding="utf-8"))
        try:
            line_objects = replay_bundle(bundle, realign=not args.no_realign)
        except Exception as exc:  # diagnostic tool: report and continue
            print(f"{bp.stem[:46]:46s}  ERROR: {exc}")
            continue
        new, old = summarize(line_objects), _old_summary(bundle)
        mark = (
            "  <-"
            if new["max_overlap"] < old["max_overlap"] - 0.5 or new["n_crawl"] < old["n_crawl"]
            else ""
        )
        print(
            f"{bp.stem[:46]:46s} {old['max_overlap']:5.1f}->{new['max_overlap']:5.1f}s "
            f"{old['n_crawl']:3d}->{new['n_crawl']:<3d} {old['n_placed']:4d}->{new['n_placed']:<4d}{mark}"
        )
        if args.write:
            _write_ass(bp, bp.parent.parent, line_objects)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
