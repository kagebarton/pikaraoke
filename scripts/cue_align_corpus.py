#!/usr/bin/env python
"""A/B the full-mix cue-align rescue over every SRT-sourced corpus song.

Experiment B corpus run (plans/full-mix-alignment-experiments.md). Selects the
songs whose lyric source was an uploader (video) SRT -- read from the
alignment-debug bundles (``lyrics.source_kind == "srt"``), so pipeline-generated
SRTs are excluded -- loads the whisper model once, and cue-aligns each song
*twice*: mix-rescue off (the shipped baseline) then on. For each song it reports
how many baseline cue-fills the mix rung converted to real audio timing, the mix
acceptance rate, that the structural metrics stayed clean, and -- the safety
invariant -- that every line *outside* the rescue path is byte-identical between
the two runs (the mix rung may only ever touch already-bad lines).

Writes each song's mix-on ``karaoke/<stem>.cuealign.ass`` (never clobbers the
production ``.ass``). Needs the ``pik`` conda env and a local GPU. Example::

    python scripts/cue_align_corpus.py
    python scripts/cue_align_corpus.py --only Mirrors
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Import the sibling single-song driver (shared per-song logic + helpers).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cue_align_song import (  # noqa: E402
    MEDIA_EXTS,
    align_one,
    artifact_metrics,
    find_srt,
    find_vocal,
    max_line_overlap,
)

from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

logger = logging.getLogger("cue_align_corpus")


def _resolve_media(root: Path, stem: str) -> Path | None:
    for ext in MEDIA_EXTS:
        cand = root / f"{stem}{ext}"
        if cand.is_file():
            return cand
    return None


def srt_sourced_songs(debug_dir: Path, root: Path) -> list[Path]:
    """Media paths for every song whose lyric source was a video SRT."""
    out: list[Path] = []
    for bundle_path in sorted(debug_dir.glob("*.json")):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if bundle.get("lyrics", {}).get("source_kind") != "srt":
            continue
        media = _resolve_media(root, bundle_path.stem)
        if media is None:
            logger.warning("no media for bundle %s", bundle_path.stem[:40])
            continue
        out.append(media)
    return out


def _bad_ids(stats: dict) -> set[int]:
    """Line ids the rescue ladder touched (re-aligned on stem/mix, or filled)."""
    rp = stats["repace"]
    return (
        set(rp["repaced_line_ids"])
        | set(rp["realigned_line_ids"])
        | set(rp.get("realigned_mix_line_ids", []))
    )


def _words_key(obj: dict) -> tuple:
    """Comparable word-timing signature for a line object."""
    return tuple((w["word"], round(w["start"], 4), round(w["end"], 4)) for w in obj["words"])


def _diffs_outside_bad(objs_off: list[dict], objs_on: list[dict], bad_ids: set[int]) -> int:
    """Count lines outside ``bad_ids`` whose timing changed between the runs.

    The mix rung must only ever touch already-bad lines, so every other line --
    aligned from the same stem audio and model in both runs -- must come back
    byte-identical. A non-zero count is a safety-invariant violation.
    """
    off_by_id = {o["line_id"]: o for o in objs_off}
    on_by_id = {o["line_id"]: o for o in objs_on}
    diffs = 0
    for lid in off_by_id.keys() | on_by_id.keys():
        if lid in bad_ids:
            continue
        off_o, on_o = off_by_id.get(lid), on_by_id.get(lid)
        if off_o is None or on_o is None or _words_key(off_o) != _words_key(on_o):
            diffs += 1
    return diffs


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--songs-root", type=Path, default=Path("/home/ken/pikaraoke-songs"))
    ap.add_argument("--debug-dir", type=Path, help="default: <songs-root>/alignment_debug")
    ap.add_argument("--only", help="substring filter on the song filename")
    args = ap.parse_args(argv)

    root: Path = args.songs_root
    debug_dir = args.debug_dir or (root / "alignment_debug")
    if not debug_dir.is_dir():
        ap.error(f"alignment_debug dir not found: {debug_dir}")

    songs = srt_sourced_songs(debug_dir, root)
    if args.only:
        songs = [s for s in songs if args.only.lower() in s.name.lower()]
    if not songs:
        ap.error("no matching SRT-sourced songs")
    logger.info("A/B cue-aligning %d SRT-sourced song(s)", len(songs))

    config = PipelineConfig()
    worker = WhisperWorker(config.whisper)
    worker.start()
    scratch = Path(get_temp_directory())
    rows: list[dict] = []
    try:
        for media in songs:
            srt_path = find_srt(media)
            vocal = find_vocal(media)
            if srt_path is None or vocal is None:
                logger.warning("skip %s: missing srt/vocal", media.stem[:40])
                continue
            try:
                objs_off, stats_off = align_one(
                    media,
                    srt_path,
                    vocal,
                    worker=worker,
                    config=config,
                    mix_rescue=False,
                    out=scratch / f"{media.stem}.cuealign.off.ass",
                )
                ass_on = media.parent / "karaoke" / f"{media.stem}.cuealign.ass"
                objs_on, stats_on = align_one(
                    media,
                    srt_path,
                    vocal,
                    worker=worker,
                    config=config,
                    mix_rescue=True,
                    out=ass_on,
                )
            except Exception:
                logger.exception("cue-align failed for %s", media.stem[:40])
                continue

            bad = _bad_ids(stats_off) | _bad_ids(stats_on)
            rp_on = stats_on["repace"]
            art = artifact_metrics(objs_on)
            overlap, _ = max_line_overlap(objs_on)
            rows.append(
                {
                    "name": media.stem,
                    "ass": ass_on,
                    "base_fills": stats_off["repace"]["n_repaced"],
                    "on_fills": rp_on["n_repaced"],
                    "mix_ok": rp_on.get("n_realigned_mix", 0),
                    "mix_att": rp_on.get("n_mix_attempts", 0),
                    "n_gap": art["n_gap"],
                    "n_instant": art["n_instant"],
                    "ovl": overlap,
                    "diff_outside_bad": _diffs_outside_bad(objs_off, objs_on, bad),
                }
            )
    finally:
        worker.stop()

    rows.sort(key=lambda r: r["mix_ok"], reverse=True)
    print(
        f"\n{'song':42} {'fills':>10} {'mix_ok/att':>11} "
        f"{'gapL':>4} {'instL':>5} {'ovl':>6} {'unsafe':>6}"
    )
    print("-" * 92)
    for r in rows:
        print(
            f"{r['name'][:42]:42} {r['base_fills']:>4}->{r['on_fills']:<4} "
            f"{r['mix_ok']:>4}/{r['mix_att']:<4}  {r['n_gap']:>4} {r['n_instant']:>5} "
            f"{r['ovl']:5.1f}s {r['diff_outside_bad']:>6}"
        )

    tot_base = sum(r["base_fills"] for r in rows)
    tot_ok = sum(r["mix_ok"] for r in rows)
    tot_att = sum(r["mix_att"] for r in rows)
    tot_unsafe = sum(r["diff_outside_bad"] for r in rows)
    rate = (tot_ok / tot_base * 100) if tot_base else 0.0
    print(
        f"\ncorpus: {tot_ok}/{tot_base} baseline fills converted ({rate:.0f}%), "
        f"{tot_ok}/{tot_att} mix attempts accepted, "
        f"{tot_unsafe} line(s) changed OUTSIDE the rescue path (must be 0)"
    )
    if rows:
        r = rows[0]
        print("\neyeball the biggest mix-rescue win:")
        print(f'  mpv "{root / (r["name"] + ".mp4")}" --sub-file="{r["ass"]}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
