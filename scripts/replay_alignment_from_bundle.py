#!/usr/bin/env python3
"""Replay the alignment matcher chain from captured debug bundles — no whisper.

Re-runs the *post-whisper* alignment (3-source joint match -> windowed re-align
-> optional .ass) straight from each song's ``alignment_debug/<stem>.json``,
reusing the captured align/transcribe/ytasr word lists and realign span words. A
matcher change can then be re-validated across the whole corpus in seconds, with
no GPU — the slow whisper passes are read back from the bundle.

On this branch (``fullmix``) the shipped non-SRT route is the three-source joint
DP (align + transcribe + optional YTASR) followed by the windowed re-align;
there is no timing prior. This replayer reproduces exactly that chain.

What is exact vs approximate:

  * **Joint match** replays exactly — it consumes only captured inputs
    (``words``/``transcribe_words`` and the YTASR words parsed from the bundle's
    own cached ``.en.asr.json3``).
  * **Windowed re-align** replays from each span's captured refined
    ``align_words`` via ``replay_span`` + ``merge_spans``. Exact for a re-run of
    the same matcher; for a *matcher* change it is only approximate (the span
    boundaries and suspect set were chosen from the original pass-1 and do not
    move here). Use ``--no-realign`` to compare pass-1 only when iterating.

Mirrors ``LyricAlignStage._run_joint``'s post-whisper chain; keep in sync if
that orchestration changes.

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

from pikaraoke.lib import ytasr  # noqa: E402
from pikaraoke.lib.joint_match import (  # noqa: E402
    match_words_to_lines_joint_with_stats,
)
from pikaraoke.lib.windowed_realign import merge_spans, replay_span  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402

# A placed line sweeping slower than this many seconds per lyric word reads as a
# crawl (the artifact this harness helps measure). Matches the diagnosis band:
# corpus crawls are >=1.9 s/word, legit lines <=1.3 s/word.
CRAWL_S_PER_WORD = 1.5


def load_ytasr_words(bundle: dict, song_root: Path) -> list[dict] | None:
    """Parsed YTASR word stream for the shipped 3rd source, or ``None``.

    The lyrics-fetch stage stashes a ``lyrics.ytasr`` block only for a caption
    that beat the quality gates, so its presence already means the track is
    usable — no need to re-gate here. Returns ``None`` when the song has none or
    the json3 can't be read (the matcher then runs plain two-source).
    """
    ref = bundle["lyrics"].get("ytasr")
    if not ref:
        return None
    try:
        text = (song_root / ref["asr_file"]).read_text(encoding="utf-8")
        words, _ = ytasr.parse_json3(text)
    except (OSError, ValueError, KeyError):
        return None
    return words or None


def replay_bundle(
    bundle: dict,
    *,
    realign: bool = True,
    ytasr_words: list[dict] | None = None,
) -> list[dict]:
    """Replay 3-source match -> windowed re-align from one bundle.

    Reuses the matcher knobs exactly as captured (``joint_stats.knobs``); the
    re-align step runs only when the bundle recorded spans. ``ytasr_words`` is
    the shipped third source — pass the bundle's parsed YTASR words (see
    :func:`load_ytasr_words`); ``None`` reproduces a two-source run.
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
        beta=knobs.get("beta", 2.0),
        margin_s=knobs["margin_s"],
        max_edit_ratio=knobs["max_edit_ratio"],
        lookahead=knobs["lookahead"],
        anchor_fallback=knobs["anchor_fallback"],
        ytasr_words=ytasr_words,
    )

    if realign:
        line_objects = _replay_realign(bundle, line_objects, transcribe_words, lines, align_lines)
    return line_objects


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
            ytasr_words = load_ytasr_words(bundle, bp.parent.parent)
            line_objects = replay_bundle(
                bundle, realign=not args.no_realign, ytasr_words=ytasr_words
            )
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
