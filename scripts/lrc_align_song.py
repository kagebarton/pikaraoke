#!/usr/bin/env python3
"""Drive LRCLIB-scaffold windowed alignment for one non-SRT song; write a .ass.

For songs with no uploader SRT (the Genius-lyric group). LRCLIB is the dominant
signal: a dense, correctly-ordered cue scaffold fetched by the Genius
artist/title. Its absolute clock often differs from the video (a different
master), so it is *warped* onto the audio clock using ASR + whisper-transcribe
anchors, then the shared windowed driver (``align_with_cues``) sections the song
at silences, force-aligns each slice, and re-paces the unplaceable.

Scaffold sources, in order of trust (see ``cue_align.warp_scaffold_cues``):

  1. **LRCLIB** -- dense + ordered, warped onto the audio anchors. The dominant
     factor: it places nearly every line in the right order.
  2. **ASR + transcribe** -- calibrate the warp and fill lines LRCLIB misses.
  3. A structurally different LRCLIB recording (warp residual too high), or no
     LRCLIB match, falls back to the ASR+transcribe scaffold alone.

Reads the Genius lyrics + Genius id/title/artist + whisper transcribe words from
the song's alignment-debug bundle; the ASR ``.json3`` and vocal stem from disk;
LRCLIB live over the network. Writes ``<songdir>/karaoke/<stem>.lrcalign.ass`` (a
distinct name -- never clobbers the production ``.ass`` or the SRT path's
``.cuealign.ass``) and prints the overlap/pace report. Touches nothing in the
production pipeline. Needs the ``pik`` conda env, a local GPU, and network. E.g.::

    python scripts/lrc_align_song.py "/path/to/Song [dQw4w9WgXcQ].mp4"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Sibling import: reuse the SRT harness's I/O driver + helpers. The repo's
# editable install already puts ``pikaraoke`` on the path; only ``scripts`` needs
# adding so ``cue_align_song`` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cue_align_song import (  # noqa: E402
    align_with_cues,
    build_config,
    find_vocal,
    report,
)

from pikaraoke.lib import lrclib, ytasr  # noqa: E402
from pikaraoke.lib.cue_align import merge_cue_spans, warp_scaffold_cues  # noqa: E402
from pikaraoke.lib.token_align import _normalize_token  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

logger = logging.getLogger("lrc_align_song")


def find_bundle(song: Path) -> Path | None:
    cand = song.parent / "alignment_debug" / f"{song.stem}.json"
    return cand if cand.is_file() else None


def find_asr(song: Path) -> Path | None:
    cand = song.parent / "subtitles" / f"{song.stem}.en.asr.json3"
    return cand if cand.is_file() else None


def normalize_words(words: list[dict]) -> list[dict]:
    """Whisper-transcribe words -> ``{norm, start, end}`` for cue_spans_for_lines.

    Transcribe words carry ``word``/``start``/``end`` but no normalised form;
    drop tokens that normalise to empty (punctuation).
    """
    out: list[dict] = []
    for w in words:
        norm = _normalize_token(w["word"])
        if norm:
            out.append({"norm": norm, "start": w["start"], "end": w.get("end", w["start"])})
    return out


def fetch_lrclib_cues(genius: dict, display_lines: list[str], duration: float | None) -> dict:
    """Live LRCLIB fetch keyed by the Genius artist/title -> per-line cue spans.

    Mirrors the production fetcher (search -> reference-free select -> map onto our
    lyric sheet). Returns ``{}`` on no match or no Genius keys.
    """
    if not genius or not genius.get("title") or not genius.get("artist"):
        return {}
    records = lrclib.search(genius["title"], genius["artist"])
    chosen = lrclib.select_candidate(records, display_lines, duration)
    if not chosen:
        logger.info("LRCLIB: no synced match for %r / %r", genius["title"], genius["artist"])
        return {}
    logger.info(
        "LRCLIB: %r by %r (id %s, %ss)",
        chosen.get("trackName"),
        chosen.get("artistName"),
        chosen.get("id"),
        chosen.get("duration"),
    )
    return lrclib.cue_spans_for_lines(chosen.get("syncedLyrics", ""), display_lines) or {}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("song", type=Path, help="song media file (the .mp4/.webm)")
    ap.add_argument("--vocal", type=Path, help="vocal stem (default: vocal/<stem>---vocal.m4a)")
    ap.add_argument("--asr", type=Path, help="ASR json3 (default: subtitles/<stem>.en.asr.json3)")
    ap.add_argument(
        "--bundle", type=Path, help="debug bundle (default: alignment_debug/<stem>.json)"
    )
    ap.add_argument("--gap", type=float, default=1.5, help="section-split gap threshold (s)")
    ap.add_argument("--pad", type=float, default=0.75, help="slice pad into silence (s)")
    ap.add_argument("--out", type=Path, help="output .ass (default: karaoke/<stem>.lrcalign.ass)")
    args = ap.parse_args(argv)

    if not args.song.is_file():
        ap.error(f"song not found: {args.song}")
    bundle_path = args.bundle or find_bundle(args.song)
    if bundle_path is None:
        ap.error("no alignment-debug bundle found; pass --bundle")
    asr_path = args.asr or find_asr(args.song)
    if asr_path is None:
        ap.error("no ASR json3 found; pass --asr")
    vocal = args.vocal or find_vocal(args.song)
    if vocal is None:
        ap.error("no vocal stem found; pass --vocal")

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    lyrics = bundle["lyrics"]
    display_lines = lyrics["lines"]
    align_lines = lyrics["align_lines"]
    duration = bundle.get("media_duration_s")
    if not duration:
        ap.error("bundle has no media_duration_s; cannot place trailing lines")

    # Audio-clock anchors: whisper transcribe (primary) unioned with YouTube ASR.
    asr_words, _frac = ytasr.parse_json3(asr_path.read_text(encoding="utf-8"))
    asr_cues = ytasr.cue_spans_for_lines(asr_words, align_lines) or {}
    tx_cues = (
        ytasr.cue_spans_for_lines(normalize_words(bundle["transcribe_words"]), align_lines) or {}
    )
    anchors = merge_cue_spans(tx_cues, asr_cues)
    if not anchors:
        logger.error("no ASR/transcribe anchors; nothing to calibrate against")
        return 1

    # LRCLIB scaffold (dominant), warped onto the anchors; gate falls back to them.
    lrc_cues = fetch_lrclib_cues(lyrics.get("genius"), display_lines, duration)
    logger.info(
        "%s: anchors=%d (asr=%d tx=%d) lrclib=%d/%d lines",
        args.song.stem[:40],
        len(anchors),
        len(asr_cues),
        len(tx_cues),
        len(lrc_cues),
        len(align_lines),
    )
    cue_spans = warp_scaffold_cues(anchors, lrc_cues, align_lines, duration)

    out = args.out or (args.song.parent / "karaoke" / f"{args.song.stem}.lrcalign.ass")
    config = build_config()
    worker = WhisperWorker(config.whisper)
    worker.start()
    try:
        line_objects, _sections = align_with_cues(
            args.song,
            display_lines=display_lines,
            align_lines=align_lines,
            cue_spans=cue_spans,
            vocal=vocal,
            worker=worker,
            config=config,
            out=out,
            tag="lrcalign",
            gap=args.gap,
            pad=args.pad,
        )
    finally:
        worker.stop()
    report(line_objects)
    return 0


if __name__ == "__main__":
    sys.exit(main())
