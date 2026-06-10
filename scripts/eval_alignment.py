#!/usr/bin/env python3
"""Score matcher timing against YouTube manual-caption ground truth.

For songs whose lyric source was the YouTube SRT, the matcher consumed
the SRT text while the cue timings were discarded — so the cue timings
are a held-out, text-identical timing reference. This script replays
the joint matcher from each song's alignment-debug bundle (cached
whisper words; no GPU) at the given knob values, fits one display-lead
offset per song, and reports residual metrics per song and pooled.

Eligibility per song:
  * ``alignment_debug/<stem>.json`` bundle with ``lyrics.source_kind == "srt"``
  * upstream manual EN captions verified via yt-dlp (cached in
    ``alignment_debug/yt_subtitle_provenance.json``; queried on miss)
  * cached ``words`` + ``transcribe_words`` in the bundle (replay mode)

Run from the repo root::

    python scripts/eval_alignment.py [--folder PATH] [--alpha A] [--as-run]
                                     [--json OUT] [--songs FILTER] [--offline]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# Allow running as ``python scripts/eval_alignment.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.alignment_eval import (  # noqa: E402
    SongScore,
    map_lines_to_cues,
    parse_reference_cues,
    placed_starts_from_line_objects,
    replay_joint_from_bundle,
    score_song,
)
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402

DEFAULT_FOLDER = "/home/ken/pikaraoke-songs"
PROVENANCE_FILE = "yt_subtitle_provenance.json"
_VIDEO_ID_RE = re.compile(r"---([\w-]{11})$")


# ---------------------------------------------------------------------------
# Provenance: upstream manual-caption verification
# ---------------------------------------------------------------------------


def load_provenance(debug_dir: Path) -> dict:
    path = debug_dir / PROVENANCE_FILE
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_provenance(debug_dir: Path, prov: dict) -> None:
    (debug_dir / PROVENANCE_FILE).write_text(
        json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def query_manual_subs(video_id: str) -> dict | None:
    """Ask YouTube (via yt-dlp) whether this video has manual EN captions."""
    try:
        raw = subprocess.check_output(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "-J",
                "--skip-download",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            stderr=subprocess.DEVNULL,
            timeout=90,
        )
        info = json.loads(raw)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as e:
        print(f"  ! provenance query failed for {video_id}: {e}")
        return None
    langs = sorted((info.get("subtitles") or {}).keys())
    return {
        "manual_en": any(l == "en" or l.startswith(("en-", "en.")) for l in langs),
        "manual_langs": langs,
        "checked_at": date.today().isoformat(),
        "title": (info.get("title") or "")[:60],
    }


def verify_provenance(stem: str, debug_dir: Path, prov: dict, offline: bool) -> bool | None:
    """True/False = verified manual-caption status; None = unverifiable."""
    m = _VIDEO_ID_RE.search(stem)
    if not m:
        return None
    vid = m.group(1)
    if vid not in prov:
        if offline:
            return None
        entry = query_manual_subs(vid)
        if entry is None:
            return None
        prov[vid] = entry
        save_provenance(debug_dir, prov)
    return bool(prov[vid]["manual_en"])


# ---------------------------------------------------------------------------
# Per-song evaluation
# ---------------------------------------------------------------------------


def evaluate_bundle(
    bundle: dict,
    srt_path: Path,
    *,
    as_run: bool,
    knobs: dict,
) -> SongScore | str:
    """Score one bundle; returns a SongScore or a skip-reason string."""
    lines = bundle["lyrics"]["lines"]
    cue_texts, cue_starts = parse_reference_cues(srt_path.read_text(encoding="utf-8"))
    mapping = map_lines_to_cues(lines, cue_texts)
    if not mapping:
        return "no lines mapped to reference cues"
    cue_starts_by_line = {lid: cue_starts[ci] for lid, ci in mapping.items()}

    if as_run:
        placed = {
            t["line_id"]: t["start"]
            for t in bundle.get("output_line_timings") or []
            if t.get("n_words", 0) > 0 and t.get("start") is not None
        }
        if not placed:
            return "no as-run output_line_timings"
    else:
        try:
            line_objects, _stats = replay_joint_from_bundle(bundle, **knobs)
        except (KeyError, ValueError) as e:
            return f"replay impossible: {e}"
        placed = placed_starts_from_line_objects(line_objects)

    return score_song(
        song=bundle["song_stem"],
        placed_starts=placed,
        cue_starts_by_line=cue_starts_by_line,
        line_texts=lines,
        n_lines=len(lines),
    )


def find_reference_srt(bundle: dict, song_dir: Path) -> Path | None:
    """Resolve the SRT the lyrics came from.

    Tries the bundle's recorded path, then the bundle stem, then a
    video-ID glob — songs renamed since capture keep their 11-char ID.
    """
    rel = bundle.get("lyrics", {}).get("source_path")
    if rel:
        cand = song_dir / rel
        if cand.is_file():
            return cand
    cand = song_dir / "subtitles" / f"{bundle['song_stem']}.srt"
    if cand.is_file():
        return cand
    m = _VIDEO_ID_RE.search(bundle["song_stem"])
    if m:
        hits = sorted((song_dir / "subtitles").glob(f"*{m.group(1)}*.srt"))
        if hits:
            return hits[0]
    return None


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(
    scores: list[SongScore], skipped: list[tuple[str, str]], knobs: dict | None
) -> dict:
    """Print the per-song table + pooled summary; return the summary dict."""
    header = (
        f"{'song':<42} {'lines':>5} {'mapped':>6} {'scored':>6} "
        f"{'offset':>7} {'med|Δ|':>7} {'≤0.5s':>6} {'≤1.0s':>6} {'gross':>5}"
    )
    print(header)
    print("-" * len(header))
    for s in scores:
        print(
            f"{s.song[:42]:<42} {s.n_lines:>5} {s.n_mapped:>6} {s.n_scored:>6} "
            f"{s.offset_s:>6.2f}s {s.median_abs_residual_s:>6.2f}s "
            f"{s.pct_within_half_s:>5.1f}% {s.pct_within_one_s:>5.1f}% {s.gross_count:>5}"
        )
        for w in s.worst:
            text = " / ".join(w["text"].splitlines())
            print(f"{'':>10} !{w['residual_s']:+8.2f}s  L{w['line_id']:<3} {text[:60]}")

    total_scored = sum(s.n_scored for s in scores)
    pooled = {
        "songs": len(scores),
        "n_scored": total_scored,
        "pct_within_half_s": (
            round(100.0 * sum(s.n_within_half_s for s in scores) / total_scored, 1)
            if total_scored
            else 0.0
        ),
        "pct_within_one_s": (
            round(100.0 * sum(s.n_within_one_s for s in scores) / total_scored, 1)
            if total_scored
            else 0.0
        ),
        "gross_count": sum(s.gross_count for s in scores),
        "median_of_medians_s": (
            round(
                sorted(s.median_abs_residual_s for s in scores)[len(scores) // 2],
                3,
            )
            if scores
            else 0.0
        ),
        "knobs": knobs,
    }
    print("-" * len(header))
    print(
        f"{'POOLED (' + str(pooled['songs']) + ' songs)':<42} "
        f"{'':>5} {'':>6} {pooled['n_scored']:>6} {'':>7} "
        f"{pooled['median_of_medians_s']:>6.2f}s "
        f"{pooled['pct_within_half_s']:>5.1f}% {pooled['pct_within_one_s']:>5.1f}% "
        f"{pooled['gross_count']:>5}"
    )
    if skipped:
        print()
        for stem, reason in skipped:
            print(f"skipped: {stem[:60]} — {reason}")
    return pooled


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    cfg = PipelineConfig()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--folder", default=DEFAULT_FOLDER, help="song library folder")
    p.add_argument("--alpha", type=float, default=cfg.joint_alpha)
    p.add_argument("--margin-s", type=float, default=cfg.joint_margin_s)
    p.add_argument("--max-edit-ratio", type=float, default=cfg.joint_max_edit_ratio)
    p.add_argument("--no-anchor-fallback", action="store_true")
    p.add_argument(
        "--as-run",
        action="store_true",
        help="score the bundle's as-run output_line_timings instead of replaying",
    )
    p.add_argument("--songs", default=None, help="substring filter on song stem")
    p.add_argument("--offline", action="store_true", help="skip provenance queries on cache miss")
    p.add_argument("--json", dest="json_out", default=None, help="write results JSON here")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    song_dir = Path(args.folder)
    debug_dir = song_dir / "alignment_debug"
    if not debug_dir.is_dir():
        print(f"no alignment_debug dir under {song_dir}")
        return 1

    knobs = {
        "alpha": args.alpha,
        "margin_s": args.margin_s,
        "max_edit_ratio": args.max_edit_ratio,
        "anchor_fallback": not args.no_anchor_fallback,
    }
    prov = load_provenance(debug_dir)

    scores: list[SongScore] = []
    skipped: list[tuple[str, str]] = []
    for path in sorted(debug_dir.glob("*.json")):
        if path.name == PROVENANCE_FILE:
            continue
        bundle = json.loads(path.read_text(encoding="utf-8"))
        stem = bundle.get("song_stem", path.stem)
        if args.songs and args.songs.lower() not in stem.lower():
            continue
        if bundle.get("lyrics", {}).get("source_kind") != "srt":
            continue
        verified = verify_provenance(stem, debug_dir, prov, args.offline)
        if verified is None:
            skipped.append((stem, "provenance unverifiable"))
            continue
        if not verified:
            skipped.append((stem, "no manual EN captions upstream"))
            continue
        srt_path = find_reference_srt(bundle, song_dir)
        if srt_path is None:
            skipped.append((stem, "reference SRT missing"))
            continue
        result = evaluate_bundle(bundle, srt_path, as_run=args.as_run, knobs=knobs)
        if isinstance(result, str):
            skipped.append((stem, result))
            continue
        scores.append(result)

    if not scores:
        print("no eligible songs scored")
        for stem, reason in skipped:
            print(f"skipped: {stem[:60]} — {reason}")
        return 1

    # Replay knobs don't apply to as-run scoring; don't report them as if they did.
    pooled = print_report(scores, skipped, None if args.as_run else knobs)

    if args.json_out:
        payload = {
            "mode": "as-run" if args.as_run else "replay",
            "pooled": pooled,
            "songs": [dataclasses.asdict(s) for s in scores],
            "skipped": [{"song": s, "reason": r} for s, r in skipped],
        }
        Path(args.json_out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
