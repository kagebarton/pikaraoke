#!/usr/bin/env python
"""Run cue-anchored windowed alignment over every SRT-sourced song in the corpus.

Selects the songs whose lyric source was an uploader (video) SRT -- read from
the alignment-debug bundles (``lyrics.source_kind == "srt"``), so pipeline
*generated* SRTs on genius/txt songs are excluded -- loads the whisper model
once, cue-aligns each via the shared single-song shim, and prints a flag table
comparing the cue path's max inter-line overlap and within-line drift against
the shipped pipeline's (from each bundle's ``output_line_timings``). Overlap
and parked-tail drift are the slow-crawl signatures this path aims to remove.

Writes each song's ``karaoke/<stem>.cuealign.ass`` (never clobbers the
production ``.ass``). Needs the ``pik`` conda env and a local GPU. Example::

    python scripts/cue_align_corpus.py
    python scripts/cue_align_corpus.py --only Mirrors
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Import the sibling single-song shim (shared per-song logic + helpers).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cue_align_song import (  # noqa: E402
    artifact_metrics,
    find_srt,
    find_vocal,
    max_line_overlap,
    run_song,
)

from pikaraoke.lib.cue_align import SOURCE_FILL, SOURCE_REALIGN  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

logger = logging.getLogger("cue_align_corpus")

MEDIA_EXTS = (".mp4", ".webm", ".mkv")


def _resolve_media(root: Path, stem: str) -> Path | None:
    for ext in MEDIA_EXTS:
        cand = root / f"{stem}{ext}"
        if cand.is_file():
            return cand
    return None


def srt_sourced_songs(debug_dir: Path, root: Path) -> list[tuple[Path, dict]]:
    """(media_path, bundle) for every song whose lyric source was a video SRT."""
    out: list[tuple[Path, dict]] = []
    for bundle_path in sorted(debug_dir.glob("*.json")):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if bundle.get("lyrics", {}).get("source_kind") != "srt":
            continue
        media = _resolve_media(root, bundle_path.stem)
        if media is None:
            logger.warning("no media for bundle %s", bundle_path.stem[:40])
            continue
        out.append((media, bundle))
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--songs-root", type=Path, default=Path("/home/ken/pikaraoke-songs"))
    ap.add_argument("--debug-dir", type=Path, help="default: <songs-root>/alignment_debug")
    ap.add_argument("--pad", type=float, default=0.75, help="slice pad into silence (s)")
    ap.add_argument("--only", help="substring filter on the song filename")
    args = ap.parse_args(argv)

    root: Path = args.songs_root
    debug_dir = args.debug_dir or (root / "alignment_debug")
    if not debug_dir.is_dir():
        ap.error(f"alignment_debug dir not found: {debug_dir}")

    songs = srt_sourced_songs(debug_dir, root)
    if args.only:
        songs = [s for s in songs if args.only.lower() in s[0].name.lower()]
    if not songs:
        ap.error("no matching SRT-sourced songs")
    logger.info("cue-aligning %d SRT-sourced song(s)", len(songs))

    config = PipelineConfig()
    worker = WhisperWorker(config.whisper)
    worker.start()
    rows: list[dict] = []
    try:
        for media, bundle in songs:
            srt_path = find_srt(media)
            vocal = find_vocal(media)
            if srt_path is None or vocal is None:
                logger.warning("skip %s: missing srt/vocal", media.stem[:40])
                continue
            ass_path = media.parent / "karaoke" / f"{media.stem}.cuealign.ass"
            try:
                line_objects, stats = run_song(
                    media, srt_path, vocal, worker=worker, config=config, pad=args.pad, out=ass_path
                )
            except Exception:
                logger.exception("cue-align failed for %s", media.stem[:40])
                continue
            new_overlap, _ = max_line_overlap(line_objects)
            old_overlap, _ = max_line_overlap(bundle["output_line_timings"])
            placed = sum(1 for o in line_objects if o["words"])
            art = artifact_metrics(line_objects)
            rows.append(
                {
                    "name": media.stem,
                    "ass": ass_path,
                    "media": media,
                    "lines": len(line_objects),
                    "placed": placed,
                    "hidden": len(line_objects) - placed,
                    "repaced": sum(1 for o in line_objects if o["source"] == SOURCE_FILL),
                    "realigned": sum(1 for o in line_objects if o["source"] == SOURCE_REALIGN),
                    "resectioned": stats["resectioned"],
                    "max_gap": art["max_gap"],
                    "n_gap": art["n_gap"],
                    "n_instant": art["n_instant"],
                    "old_ovl": old_overlap,
                    "ovl": new_overlap,
                }
            )
    finally:
        worker.stop()

    # Sort worst-first by the drift signature (parked-tail lines, then gap size).
    rows.sort(key=lambda r: (r["n_gap"], r["max_gap"], r["n_instant"]), reverse=True)
    print(
        f"\n{'song':42} {'plc':>4} {'hid':>4} {'rea':>4} {'rep':>4} {'rsec':>4} "
        f"{'maxgap':>7} {'gapL':>4} {'instL':>5} {'ovl(old>new)':>14}"
    )
    print("-" * 100)
    for r in rows:
        print(
            f"{r['name'][:42]:42} {r['placed']:4d} {r['hidden']:4d} {r['realigned']:4d} "
            f"{r['repaced']:4d} {('yes' if r['resectioned'] else '-'):>4} "
            f"{r['max_gap']:6.1f}s {r['n_gap']:4d} {r['n_instant']:5d} "
            f"{r['old_ovl']:5.1f}->{r['ovl']:<5.1f}s"
        )
    tot_gap = sum(r["n_gap"] for r in rows)
    tot_inst = sum(r["n_instant"] for r in rows)
    songs_hit = sum(1 for r in rows if r["n_gap"] or r["n_instant"])
    print(
        f"\nprevalence: {songs_hit}/{len(rows)} songs show drift; "
        f"{tot_gap} parked-tail line(s), {tot_inst} mostly-instant line(s) total"
    )

    print(f"\nwrote {len(rows)} cue-align .ass file(s) (alongside production .ass).")
    if rows:
        r = rows[0]
        prod_ass = r["media"].parent / "karaoke" / f"{r['media'].stem}.ass"
        print("eyeball the worst (cue-align subs over the video):")
        print(f'  mpv "{r["media"]}" --sub-file="{r["ass"]}"')
        print(f'  (compare production by swapping --sub-file to "{prod_ass}")')
    return 0


if __name__ == "__main__":
    sys.exit(main())
