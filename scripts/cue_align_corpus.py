#!/usr/bin/env python
"""Run cue-anchored windowed alignment over every SRT-sourced song in the corpus.

Selects the songs whose lyric source was an uploader (video) SRT -- read from
the alignment-debug bundles (``lyrics.source_kind == "srt"``), so pipeline
*generated* SRTs on genius/txt songs are excluded -- loads the whisper model
once, cue-aligns each, and prints a table comparing the new path's max
inter-line overlap against the shipped pipeline's (from each bundle's
``output_line_timings``). Overlap is the slow-crawl signature this path aims
to eliminate.

Writes each song's ``karaoke/<stem>.cuealign.ass`` (never clobbers the
production ``.ass``). Needs the ``pik`` conda env and a local GPU. Example::

    python scripts/cue_align_corpus.py
    python scripts/cue_align_corpus.py --only Mirrors --gap 1.5
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
    align_song,
    artifact_metrics,
    build_config,
    find_srt,
    find_vocal,
    max_line_overlap,
    section_drift,
)

from pikaraoke.lib.cue_align import SOURCE_FILL  # noqa: E402
from pikaraoke.lib.srt_prior import cue_spans_from_srt  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

logger = logging.getLogger("cue_align_corpus")


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
    ap.add_argument("--gap", type=float, default=1.5, help="section-split gap threshold (s)")
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

    config = build_config()
    worker = WhisperWorker(config.whisper)
    worker.start()
    rows: list[dict] = []
    all_sections: list[dict] = []
    try:
        for media, _bundle in songs:
            srt_path = find_srt(media)
            vocal = find_vocal(media)
            if srt_path is None or vocal is None:
                logger.warning("skip %s: missing srt/vocal", media.stem[:40])
                continue
            ass_path = media.parent / "karaoke" / f"{media.stem}.cuealign.ass"
            try:
                line_objects, sections = align_song(
                    media,
                    srt_path,
                    vocal,
                    worker=worker,
                    config=config,
                    gap=args.gap,
                    pad=args.pad,
                    out=ass_path,
                )
            except Exception:
                logger.exception("cue-align failed for %s", media.stem[:40])
                continue
            new_overlap, _ = max_line_overlap(line_objects)
            placed = sum(1 for o in line_objects if o["words"])
            art = artifact_metrics(line_objects)
            _, spans = cue_spans_from_srt(srt_path.read_text(encoding="utf-8"))
            sec_rows = section_drift(sections, spans, line_objects)
            for sr in sec_rows:
                sr["song"] = media.stem
            all_sections.extend(sec_rows)
            rows.append(
                {
                    "name": media.stem,
                    "media": media,
                    "ass": ass_path,
                    "lines": len(line_objects),
                    "placed": placed,
                    "hidden": len(line_objects) - placed,
                    "repaced": sum(1 for o in line_objects if o["source"] == SOURCE_FILL),
                    "max_gap": art["max_gap"],
                    "n_gap": art["n_gap"],
                    "n_instant": art["n_instant"],
                    "ovl": new_overlap,
                }
            )
    finally:
        worker.stop()

    # Sort worst-first by the drift signature (parked-tail lines, then gap size).
    rows.sort(key=lambda r: (r["n_gap"], r["max_gap"], r["n_instant"]), reverse=True)
    print(
        f"\n{'song':42} {'plc':>4} {'hid':>4} {'rep':>4} "
        f"{'maxgap':>7} {'gapL':>4} {'instL':>5} {'ovl':>6}"
    )
    print("-" * 85)
    for r in rows:
        print(
            f"{r['name'][:42]:42} {r['placed']:4d} {r['hidden']:4d} {r['repaced']:4d} "
            f"{r['max_gap']:6.1f}s {r['n_gap']:4d} {r['n_instant']:5d} {r['ovl']:5.1f}s"
        )
    tot_gap = sum(r["n_gap"] for r in rows)
    tot_inst = sum(r["n_instant"] for r in rows)
    songs_hit = sum(1 for r in rows if r["n_gap"] or r["n_instant"])
    print(
        f"\nprevalence: {songs_hit}/{len(rows)} songs show drift; "
        f"{tot_gap} parked-tail line(s), {tot_inst} mostly-instant line(s) total"
    )

    print(f"\nwrote {len(rows)} cue-align .ass file(s) (alongside production .ass):")
    for r in rows:
        print(f"  {r['ass']}")
    if rows:
        r = rows[0]
        print("\neyeball one (cue-align subs over the video):")
        print(f'  mpv "{r["media"]}" --sub-file="{r["ass"]}"')
        print(
            "compare against production by swapping --sub-file to "
            f'"{r["media"].parent / "karaoke" / (r["media"].stem + ".ass")}"'
        )

    _print_size_correlation(all_sections)
    dump = Path(
        "/tmp/claude-1000/-home-ken-pikaraoke/e8ca55e5-4653-44b2-9300-245d2d09186c/"
        f"scratchpad/cuealign_sections_g{args.gap}.json"
    )
    dump.write_text(json.dumps(all_sections, indent=1), encoding="utf-8")
    print(f"\nper-section data: {dump}")
    return 0


def _print_size_correlation(sections: list[dict]) -> None:
    """Does drift rise with section size? Bin sections by line count and by
    duration, showing the fraction that contain a drifted line."""
    if not sections:
        return

    def bucket(label: str, edges: list[tuple], key) -> None:
        print(f"\ndrift vs {label}:")
        print(f"  {'bin':>10} {'sections':>9} {'w/drift':>8} {'rate':>6} {'meanMaxGap':>11}")
        for lo, hi, name in edges:
            grp = [s for s in sections if lo <= key(s) < hi]
            if not grp:
                continue
            drifted = [s for s in grp if s["n_drift"]]
            mean_gap = sum(s["max_gap"] for s in grp) / len(grp)
            print(
                f"  {name:>10} {len(grp):9d} {len(drifted):8d} "
                f"{len(drifted)/len(grp):5.0%} {mean_gap:10.1f}s"
            )

    bucket(
        "section size (lines)",
        [(1, 4, "1-3"), (4, 7, "4-6"), (7, 10, "7-9"), (10, 9999, "10+")],
        key=lambda s: s["n_lines"],
    )
    bucket(
        "section duration",
        [(0, 15, "<15s"), (15, 30, "15-30s"), (30, 45, "30-45s"), (45, 1e9, "45s+")],
        key=lambda s: s["dur"],
    )

    # For drifted sections, was there an internal cue-gap a tighter split could
    # have used? (vs. genuinely gapless -> needs a hard size cap.)
    drifted = [s for s in sections if s["n_drift"]]
    if drifted:
        splittable = sum(1 for s in drifted if s["max_cue_gap"] >= 1.0)
        print(
            f"\nof {len(drifted)} drifted sections, {splittable} have an internal "
            f"cue-gap >=1.0s (a tighter gap threshold would split them); "
            f"{len(drifted) - splittable} are near-gapless (need a size cap)"
        )


if __name__ == "__main__":
    sys.exit(main())
