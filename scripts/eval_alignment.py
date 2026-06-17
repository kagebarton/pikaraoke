#!/usr/bin/env python3
"""Score matcher timing against YouTube manual-caption ground truth.

For songs whose lyric source was the YouTube SRT, the matcher consumed
the SRT text while the cue timings were held out — a text-identical
timing reference. This script replays the joint matcher from each
song's alignment-debug bundle (cached whisper words; no GPU) at the
given knob values, fits one display-lead offset per song, and reports
residual metrics per song and pooled.

``--srt-prior`` additionally applies the production SRT timing prior to
the replayed placement; score those runs with ``--prefer-lrclib``, since
SRT-informed placement graded against the same SRT would be circular.

Eligibility per song (bundle in the debug dir, plus a timing reference):
  * ``lyrics.source_kind == "srt"``: the YouTube SRT cue timings, gated
    on upstream manual EN captions verified via yt-dlp (cached in
    ``alignment_debug/yt_subtitle_provenance.json``; queried on miss)
  * other sources: a hand-vetted LRCLIB file at ``<folder>/lrclib/<stem>``
    (timing reference only; absolute offset absorbed by the per-song fit)
  * replay mode needs cached ``words`` + ``transcribe_words`` in the bundle

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
    cue_spans_from_lrc,
    map_lines_to_cues,
    parse_lrc_lines,
    parse_reference_cues,
    placed_starts_from_line_objects,
    replay_joint_from_bundle,
    score_song,
)
from pikaraoke.lib.srt_prior import apply_srt_prior, cue_spans_from_srt  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from scripts.capture_lrclib_keys import (  # noqa: E402
    KEYS_FILENAME,
    default_query,
    load_keys,
)
from scripts.probe_lrclib_search import (  # noqa: E402
    ffprobe_duration,
    find_media,
    lrclib_search,
)

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
    cue_texts: list[str],
    cue_starts: list[float],
    *,
    as_run: bool,
    knobs: dict,
    ref: str,
    prior_cues: dict[int, tuple[float, float]] | None = None,
) -> tuple[SongScore, dict | None] | str:
    """Score one bundle; returns ``(score, srt_prior_stats)`` or a
    skip-reason string. ``prior_cues`` applies the SRT timing prior to
    the replayed placement (replay mode only), matching production."""
    lines = bundle["lyrics"]["lines"]
    mapping = map_lines_to_cues(lines, cue_texts)
    if not mapping:
        return "no lines mapped to reference cues"
    cue_starts_by_line = {lid: cue_starts[ci] for lid, ci in mapping.items()}

    prior_stats = None
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
        if prior_cues:
            line_objects, prior_stats = apply_srt_prior(
                line_objects,
                bundle["transcribe_words"],
                lines,
                bundle["lyrics"]["align_lines"],
                prior_cues,
                margin_s=knobs["margin_s"],
                max_edit_ratio=knobs["max_edit_ratio"],
            )
        placed = placed_starts_from_line_objects(line_objects)

    score = score_song(
        song=bundle["song_stem"],
        placed_starts=placed,
        cue_starts_by_line=cue_starts_by_line,
        line_texts=lines,
        n_lines=len(lines),
        ref=ref,
        # LRCLIB clocks come from a different master; absorb constant
        # tempo drift so only structural divergence scores against us.
        fit_drift=(ref == "lrclib"),
    )
    return score, prior_stats


def prior_cues_for_bundle(bundle: dict, song_dir: Path) -> dict[int, tuple[float, float]] | None:
    """Cue spans keyed by line id for replaying the SRT timing prior.

    Production extracts the spans at lyric load; the replay
    reconstructs them from the source SRT. Positional identity holds
    unless the cleanup changed since capture — then fall back to the
    fuzzy line-to-cue mapping.
    """
    srt_path = find_reference_srt(bundle, song_dir)
    if srt_path is None:
        return None
    texts, spans = cue_spans_from_srt(srt_path.read_text(encoding="utf-8"))
    lines = bundle["lyrics"]["lines"]
    if texts == lines:
        return dict(enumerate(spans))
    mapping = map_lines_to_cues(lines, texts)
    return {lid: spans[ci] for lid, ci in mapping.items()} or None


def select_lrclib_candidate(
    records: list[dict], sheet: list[str], video_dur: float | None
) -> dict | None:
    """Production-shaped pick from a search result set: the synced
    candidate whose text best maps to our lyric sheet, ties broken toward
    the video's duration (step-1 found duration the effective selector
    among same-text variants). Reference-free — no timing ground truth is
    consulted, so this is the choice step-3 production would make."""
    best: dict | None = None
    best_key: tuple[float, float] | None = None
    for r in records:
        synced = r.get("syncedLyrics")
        if not synced:
            continue
        cand_texts, _ = parse_lrc_lines(synced)
        if not cand_texts:
            continue
        map_rate = len(map_lines_to_cues(sheet, cand_texts)) / len(sheet) if sheet else 0.0
        dur = float(r.get("duration") or 0.0)
        dur_key = -abs(dur - video_dur) if video_dur is not None else 0.0
        key = (map_rate, dur_key)
        if best_key is None or key > best_key:
            best, best_key = r, key
    return best


def prior_cues_from_lrclib(
    bundle: dict, song_dir: Path, offline: bool = False
) -> dict[int, tuple[float, float]] | None:
    """Cue spans keyed by line id from the auto-fetched top LRCLIB variant.

    Replays step-1's search (cached under ``<folder>/lrclib/probe_cache``):
    query by the captured canonical Genius key, else a cleaned title
    parse; pick a candidate with :func:`select_lrclib_candidate`; turn
    its LRC into spans and map them onto the lyric sheet by text. Returns
    None when search yields nothing usable — the prior then no-ops, as in
    production with no fetch. Measures the whole pipeline (search + vet +
    prior), not just the prior, so the hand-vetted file is never read.
    """
    stem = bundle["song_stem"]
    lrc_dir = song_dir / "lrclib"
    keys = load_keys(lrc_dir / KEYS_FILENAME)
    if stem in keys:
        params = {"track_name": keys[stem]["title"], "artist_name": keys[stem]["artist"]}
    else:
        params = {"q": default_query(stem)}
    records = lrclib_search(params, lrc_dir / "probe_cache", refresh=False, offline=offline)
    if not records:
        return None
    lines = bundle["lyrics"]["lines"]
    media = find_media(stem, song_dir)
    chosen = select_lrclib_candidate(records, lines, ffprobe_duration(media) if media else None)
    if chosen is None:
        return None
    cue_texts, spans = cue_spans_from_lrc(chosen["syncedLyrics"])
    mapping = map_lines_to_cues(lines, cue_texts)
    return {lid: spans[ci] for lid, ci in mapping.items()} or None


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


def find_reference_lrc(bundle: dict, song_dir: Path) -> Path | None:
    """Resolve a hand-vetted LRCLIB timing file for a non-SRT-sourced song.

    Files in ``<folder>/lrclib/`` are named by song stem (no extension);
    falls back to a video-ID glob for songs renamed since capture.
    """
    lrc_dir = song_dir / "lrclib"
    cand = lrc_dir / bundle["song_stem"]
    if cand.is_file():
        return cand
    m = _VIDEO_ID_RE.search(bundle["song_stem"])
    if m:
        hits = sorted(lrc_dir.glob(f"*{m.group(1)}*"))
        if hits:
            return hits[0]
    return None


def resolve_reference(
    bundle: dict,
    song_dir: Path,
    debug_dir: Path,
    prov: dict,
    offline: bool,
    prefer_lrclib: bool = False,
) -> tuple[list[str], list[float], str] | str | None:
    """Resolve a bundle's timing reference.

    Returns ``(cue_texts, cue_starts, ref_kind)``, a skip-reason string,
    or None when the song simply isn't in the eval corpus (non-SRT
    source with no LRCLIB file).

    SRT-sourced songs score against the YouTube SRT cue timings
    (provenance-gated: upstream manual captions only). Other songs score
    against hand-vetted LRCLIB synced lyrics — timing reference only;
    their absolute clock may differ from the video, which the per-song
    offset fit absorbs.

    ``prefer_lrclib`` scores SRT-sourced songs against an LRCLIB file
    when one exists (falling back to the SRT). Required once the matcher
    consumes SRT timings: scoring SRT-informed placement against the
    same SRT would grade the matcher against its own input.
    """
    stem = bundle["song_stem"]
    if bundle.get("lyrics", {}).get("source_kind") == "srt":
        if prefer_lrclib:
            lrc_path = find_reference_lrc(bundle, song_dir)
            if lrc_path is not None:
                texts, starts = parse_lrc_lines(lrc_path.read_text(encoding="utf-8"))
                if texts:
                    return texts, starts, "lrclib"
        verified = verify_provenance(stem, debug_dir, prov, offline)
        if verified is None:
            return "provenance unverifiable"
        if not verified:
            return "no manual EN captions upstream"
        srt_path = find_reference_srt(bundle, song_dir)
        if srt_path is None:
            return "reference SRT missing"
        texts, starts = parse_reference_cues(srt_path.read_text(encoding="utf-8"))
        return texts, starts, "yt-srt"
    lrc_path = find_reference_lrc(bundle, song_dir)
    if lrc_path is None:
        return None
    texts, starts = parse_lrc_lines(lrc_path.read_text(encoding="utf-8"))
    if not texts:
        return "LRC file has no synced lines"
    return texts, starts, "lrclib"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(
    scores: list[SongScore], skipped: list[tuple[str, str]], knobs: dict | None
) -> dict:
    """Print the per-song table + pooled summary; return the summary dict."""
    header = (
        f"{'song':<42} {'ref':>6} {'lines':>5} {'mapped':>6} {'scored':>6} "
        f"{'offset':>7} {'dr/min':>6} {'med|Δ|':>7} {'≤0.5s':>6} {'≤1.0s':>6} {'gross':>5}"
    )
    print(header)
    print("-" * len(header))
    for s in scores:
        drift = f"{s.drift_s_per_min:>6.2f}" if s.drift_s_per_min else f"{'':>6}"
        print(
            f"{s.song[:42]:<42} {s.ref:>6} {s.n_lines:>5} {s.n_mapped:>6} {s.n_scored:>6} "
            f"{s.offset_s:>6.2f}s {drift} {s.median_abs_residual_s:>6.2f}s "
            f"{s.pct_within_half_s:>5.1f}% {s.pct_within_one_s:>5.1f}% {s.gross_count:>5}"
        )
        for w in s.worst:
            text = " / ".join(w["text"].splitlines())
            print(f"{'':>10} !{w['residual_s']:+8.2f}s  L{w['line_id']:<3} {text[:60]}")

    def _pool(subset: list[SongScore]) -> dict:
        total = sum(s.n_scored for s in subset)
        return {
            "songs": len(subset),
            "n_scored": total,
            "pct_within_half_s": (
                round(100.0 * sum(s.n_within_half_s for s in subset) / total, 1) if total else 0.0
            ),
            "pct_within_one_s": (
                round(100.0 * sum(s.n_within_one_s for s in subset) / total, 1) if total else 0.0
            ),
            "gross_count": sum(s.gross_count for s in subset),
            "median_of_medians_s": (
                round(sorted(s.median_abs_residual_s for s in subset)[len(subset) // 2], 3)
                if subset
                else 0.0
            ),
        }

    def _print_pool(label: str, p: dict) -> None:
        print(
            f"{label:<42} "
            f"{'':>6} {'':>5} {'':>6} {p['n_scored']:>6} {'':>7} {'':>6} "
            f"{p['median_of_medians_s']:>6.2f}s "
            f"{p['pct_within_half_s']:>5.1f}% {p['pct_within_one_s']:>5.1f}% "
            f"{p['gross_count']:>5}"
        )

    pooled = _pool(scores)
    pooled["knobs"] = knobs
    print("-" * len(header))
    ref_kinds = sorted({s.ref for s in scores})
    if len(ref_kinds) > 1:
        pooled["by_ref"] = {}
        for kind in ref_kinds:
            sub = _pool([s for s in scores if s.ref == kind])
            pooled["by_ref"][kind] = sub
            _print_pool(f"POOLED {kind} ({sub['songs']} songs)", sub)
    _print_pool(f"POOLED ({pooled['songs']} songs)", pooled)
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
    p.add_argument(
        "--debug-dir",
        default=None,
        help="bundle directory (default: <folder>/alignment_debug)",
    )
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
    p.add_argument(
        "--prefer-lrclib",
        action="store_true",
        help="score SRT-sourced songs against LRCLIB when available "
        "(non-circular reference for SRT-informed matching)",
    )
    prior = p.add_mutually_exclusive_group()
    prior.add_argument(
        "--srt-prior",
        action="store_true",
        help="apply the SRT timing prior to replayed placements "
        "(matches production joint_srt_prior; use with --prefer-lrclib)",
    )
    prior.add_argument(
        "--lrclib-prior",
        action="store_true",
        help="apply the timing prior from the auto-fetched top LRCLIB variant "
        "to SRT-sourced songs, scored against the held-out YT SRT "
        "(step 2 of plans/lrclib-timing-prior.md)",
    )
    p.add_argument("--json", dest="json_out", default=None, help="write results JSON here")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    song_dir = Path(args.folder)
    debug_dir = Path(args.debug_dir) if args.debug_dir else song_dir / "alignment_debug"
    if not debug_dir.is_dir():
        print(f"no bundle dir: {debug_dir}")
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
    prior_by_song: dict[str, dict] = {}
    for path in sorted(debug_dir.glob("*.json")):
        if path.name == PROVENANCE_FILE:
            continue
        bundle = json.loads(path.read_text(encoding="utf-8"))
        stem = bundle.get("song_stem", path.stem)
        if args.songs and args.songs.lower() not in stem.lower():
            continue
        ref = resolve_reference(
            bundle, song_dir, debug_dir, prov, args.offline, prefer_lrclib=args.prefer_lrclib
        )
        if ref is None:
            continue  # not in the eval corpus
        if isinstance(ref, str):
            skipped.append((stem, ref))
            continue
        cue_texts, cue_starts, ref_kind = ref
        prior_cues = None
        if not args.as_run and bundle.get("lyrics", {}).get("source_kind") == "srt":
            if args.srt_prior:
                prior_cues = prior_cues_for_bundle(bundle, song_dir)
            elif args.lrclib_prior:
                prior_cues = prior_cues_from_lrclib(bundle, song_dir, offline=args.offline)
        result = evaluate_bundle(
            bundle,
            cue_texts,
            cue_starts,
            as_run=args.as_run,
            knobs=knobs,
            ref=ref_kind,
            prior_cues=prior_cues,
        )
        if isinstance(result, str):
            skipped.append((stem, result))
            continue
        score, prior_stats = result
        scores.append(score)
        if prior_stats is not None:
            prior_by_song[stem] = prior_stats

    if not scores:
        print("no eligible songs scored")
        for stem, reason in skipped:
            print(f"skipped: {stem[:60]} — {reason}")
        return 1

    # Replay knobs don't apply to as-run scoring; don't report them as if they did.
    pooled = print_report(scores, skipped, None if args.as_run else knobs)

    if prior_by_song:
        print(f"\n{'LRCLIB' if args.lrclib_prior else 'SRT'} prior:")
        for stem, st in prior_by_song.items():
            if st["bailed"]:
                print(
                    f"  {stem[:50]:<50} bailed: {st['bailed']} " f"(anchors={st['n_anchors_fit']})"
                )
            else:
                print(
                    f"  {stem[:50]:<50} offset={st['offset_s']:+.2f}s "
                    f"mad={st['mad_s']:.2f}s anchors={st['n_anchors_fit']} "
                    f"snapped={st['n_snapped']} filled={st['n_filled']}"
                )

    if args.json_out:
        payload = {
            "mode": "as-run" if args.as_run else "replay",
            "pooled": pooled,
            "songs": [dataclasses.asdict(s) for s in scores],
            "skipped": [{"song": s, "reason": r} for s, r in skipped],
        }
        if prior_by_song:
            payload["lrclib_prior" if args.lrclib_prior else "srt_prior"] = prior_by_song
        Path(args.json_out).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
