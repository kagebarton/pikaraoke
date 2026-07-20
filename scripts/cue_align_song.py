#!/usr/bin/env python
"""Drive cue-anchored windowed alignment for one SRT song and write a .ass to eyeball.

A thin GPU/ffmpeg shim over the production driver in ``pikaraoke.lib.cue_align``
(:func:`align_song`, which owns sectioning / offset-fit / re-pace). Given a song
with an uploader-synced SRT and a separated vocal stem on disk, it:

  1. reads the SRT into 1:1 line cues (:func:`cue_spans_from_srt`),
  2. builds a ``slice_align`` callable that ffmpeg-slices the stem and
     force-aligns each window via the real ``WhisperWorker``,
  3. hands both to :func:`cue_align.align_song`, and
  4. renders the placed lines to ``<songdir>/karaoke/<stem>.cuealign.ass``
     (a distinct name -- it never clobbers the production ``.ass``),

then prints an overlap/pace/drift report so you can tell whether the crawls are
gone without playing all of them.

All GPU/ffmpeg I/O lives here; the cue_align module stays pure (so a batch
runner loads the model once, and ``test_cue_align`` drives it with a stub).
Needs the ``pik`` conda env and a local GPU. Example::

    python scripts/cue_align_song.py "/path/to/Song [dQw4w9WgXcQ].mp4"
"""

import argparse
import importlib.util
import itertools
import logging
import subprocess
import sys
import wave
from pathlib import Path

from pikaraoke.lib.cue_align import SOURCE_FILL, SOURCE_REALIGN, align_song
from pikaraoke.lib.get_platform import get_temp_directory
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

logger = logging.getLogger("cue_align_song")

# A word shorter than this is a failed forced-alignment (zero-duration, parked
# by stable-ts); a line that is mostly these is an alignment failure.
INSTANT_DUR_S = 0.05

# An internal silent gap wider than this inside a single line is the "parked
# tail" drift signature (stable-ts dumps unaligned words at the slice end).
GAP_FLAG_S = 3.0


def find_srt(song: Path) -> Path | None:
    subs = song.parent / "subtitles"
    for name in (f"{song.stem}.en.srt", f"{song.stem}.srt"):
        cand = subs / name
        if cand.is_file():
            return cand
    return None


def find_vocal(song: Path) -> Path | None:
    cand = song.parent / "vocal" / f"{song.stem}---vocal.m4a"
    return cand if cand.is_file() else None


def max_line_overlap(timings: list[dict]) -> tuple[float, tuple[int, int] | None]:
    """Largest ``prev_end - cur_start`` over time-sorted placed lines.

    Works on both cue-align line objects and a bundle's
    ``output_line_timings`` (both carry ``line_id``/``start``/``end``); lines
    with no start (hidden / no words) are skipped. A line still sweeping when
    the next one starts is the crawl signature.
    """
    placed = sorted((t for t in timings if t.get("start") is not None), key=lambda t: t["start"])
    worst_overlap = 0.0
    worst_pair: tuple[int, int] | None = None
    for prev, cur in zip(placed, placed[1:]):
        overlap = prev["end"] - cur["start"]
        if overlap > worst_overlap:
            worst_overlap = overlap
            worst_pair = (prev.get("line_id"), cur.get("line_id"))
    return worst_overlap, worst_pair


def artifact_metrics(line_objects: list[dict]) -> dict:
    """Count the within-section drift artifacts the overlap metric misses.

    ``max_gap`` is the worst internal word-gap in any line; ``n_gap`` the
    number of lines holding a gap over :data:`GAP_FLAG_S` (a parked tail);
    ``n_instant`` the number of lines that are mostly failed (instant) words.
    """
    max_gap = 0.0
    n_gap = 0
    n_instant = 0
    for o in line_objects:
        words = o["words"]
        if not words:
            continue
        gap = max((b["start"] - a["end"] for a, b in zip(words, words[1:])), default=0.0)
        max_gap = max(max_gap, gap)
        if gap > GAP_FLAG_S:
            n_gap += 1
        instant = sum(1 for w in words if w["end"] - w["start"] < INSTANT_DUR_S)
        if instant / len(words) > 0.5:
            n_instant += 1
    return {"max_gap": max_gap, "n_gap": n_gap, "n_instant": n_instant}


def _ffmpeg(args: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
    )


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def _make_slice_align(vocal_wav: Path, tmp: Path, stem: str, worker: WhisperWorker):
    """Build the ``slice_align`` callable ``cue_align.align_song`` drives.

    Each call ffmpeg-slices ``[t0, t1]`` from the master wav, force-aligns
    ``text`` over it, and returns the words shifted to absolute song time.
    ``None`` on failure: stable-ts gives up on a slice it cannot align (a
    worker RuntimeError), and ffmpeg can fail on the slice itself -- either
    way ``align_song``'s cue fallback carries the affected lines. A dead
    worker (WorkerDiedError) still propagates.
    """
    counter = itertools.count()

    def slice_align(t0: float, t1: float, text: str, label: str) -> list[dict] | None:
        slice_wav = tmp / f"{stem}__cuealign_{next(counter):04d}.wav"
        try:
            _ffmpeg(["-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", str(vocal_wav), str(slice_wav)])
            words = worker.align_refine(slice_wav, text)
        except (RuntimeError, subprocess.CalledProcessError) as e:
            logger.warning("%s failed to align: %s; re-pacing from cue", label, e)
            return None
        finally:
            slice_wav.unlink(missing_ok=True)
        for w in words:
            w["start"] += t0
            w["end"] += t0
        return words

    return slice_align


def run_song(
    song: Path,
    srt_path: Path,
    vocal: Path,
    *,
    worker: WhisperWorker,
    config: PipelineConfig,
    pad: float = 0.75,
    out: Path | None = None,
    make_slice_align=_make_slice_align,
) -> tuple[list[dict], dict]:
    """Cue-align one SRT song with an already-started ``worker``; write the .ass.

    Decodes the stem to a master wav once, builds the ``slice_align`` closure,
    and hands the SRT cues to :func:`cue_align.align_song`. SRT carries no
    align/display distinction, so ``align_lines`` mirrors the cue texts. The
    worker lifecycle is the caller's. Returns ``(line_objects, stats)``.

    ``make_slice_align`` swaps the forced-aligner backend: given
    ``(vocal_wav, tmp, stem, worker)`` it must return a
    ``(t0, t1, text, label) -> words | None`` callable (the
    :func:`cue_align.align_song` contract). Defaults to the production
    whisper backend; a probe backend (e.g. a CTC aligner) can be injected
    without touching this driver -- same parameter as
    ``scaffold_align_song.run_song``.
    """
    display_lines, cue_spans = cue_spans_from_srt(srt_path.read_text(encoding="utf-8"))
    if not cue_spans:
        raise ValueError(f"{song.stem}: no cues")

    tmp = Path(get_temp_directory())
    vocal_wav = tmp / f"{song.stem}__cuealign_vocal.wav"
    # 16 kHz mono is whisper's native input; anything more just costs decode.
    _ffmpeg(["-i", str(vocal), "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(vocal_wav)])
    try:
        duration = _wav_duration(vocal_wav)
        slice_align = make_slice_align(vocal_wav, tmp, song.stem, worker)
        line_objects, stats = align_song(
            cue_spans, display_lines, list(display_lines), duration, slice_align, pad_s=pad
        )
    finally:
        vocal_wav.unlink(missing_ok=True)

    # Reuse the production ASS renderer for a byte-faithful A/B against the
    # pipeline's own .ass -- it only reads config, mutates nothing.
    ass = LyricAlignStage(worker, config)._generate_ass(line_objects)
    out = out or (song.parent / "karaoke" / f"{song.stem}.cuealign.ass")
    out.parent.mkdir(exist_ok=True)
    out.write_text(ass, encoding="utf-8")
    logger.info("wrote %s", out)
    return line_objects, stats


def report(line_objects: list[dict], stats: dict) -> None:
    placed = [o for o in line_objects if o["words"]]
    hidden = len(line_objects) - len(placed)
    repaced = sum(1 for o in line_objects if o["source"] == SOURCE_FILL)
    realigned = sum(1 for o in line_objects if o["source"] == SOURCE_REALIGN)
    overlap, worst = max_line_overlap(line_objects)
    widest = max((o["end"] - o["start"]) / len(o["words"]) for o in placed) if placed else 0.0
    art = artifact_metrics(line_objects)
    print("\n--- cue-align report ---")
    print(
        f"lines: {len(line_objects)} placed={len(placed)} hidden={hidden} "
        f"(re-aligned={realigned}, re-paced={repaced})"
    )
    print(
        f"sections: {stats['n_sections']} offset={stats['offset_s']:+.2f}s "
        f"resectioned={stats['resectioned']}"
    )
    print(f"max inter-line overlap: {overlap:.2f}s" + (f" (lines {worst})" if worst else ""))
    print(f"widest line pace: {widest:.2f}s/word")
    print(
        f"drift: max_gap={art['max_gap']:.1f}s parked-tail lines={art['n_gap']} "
        f"mostly-instant lines={art['n_instant']}"
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("song", type=Path, help="song media file (the .mp4/.webm)")
    ap.add_argument("--vocal", type=Path, help="vocal stem (default: vocal/<stem>---vocal.m4a)")
    ap.add_argument("--srt", type=Path, help="SRT cues (default: subtitles/<stem>.srt)")
    ap.add_argument("--pad", type=float, default=0.75, help="slice pad into silence (s)")
    ap.add_argument("--out", type=Path, help="output .ass (default: karaoke/<stem>.cuealign.ass)")
    ap.add_argument(
        "--slice-align-module",
        type=Path,
        help="path to a module exposing make_slice_align(vocal_wav, tmp, stem, worker) "
        "-> slice_align, to swap the forced-aligner backend (default: whisper)",
    )
    args = ap.parse_args(argv)

    if not args.song.is_file():
        ap.error(f"song not found: {args.song}")
    srt_path = args.srt or find_srt(args.song)
    if srt_path is None:
        ap.error("no SRT found; pass --srt")
    vocal = args.vocal or find_vocal(args.song)
    if vocal is None:
        ap.error("no vocal stem found; pass --vocal")

    make_slice_align = _make_slice_align
    if args.slice_align_module:
        spec = importlib.util.spec_from_file_location(
            args.slice_align_module.stem, args.slice_align_module
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        make_slice_align = module.make_slice_align
        logger.info("using slice-align backend from %s", args.slice_align_module)

    config = PipelineConfig()
    worker = WhisperWorker(config.whisper)
    worker.start()
    try:
        line_objects, stats = run_song(
            args.song,
            srt_path,
            vocal,
            worker=worker,
            config=config,
            pad=args.pad,
            out=args.out,
            make_slice_align=make_slice_align,
        )
    finally:
        worker.stop()
    report(line_objects, stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
