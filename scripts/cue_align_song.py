#!/usr/bin/env python
"""Drive cue-align on one SRT song, optionally with the full-mix rescue rung.

A standalone harness for Experiment B (plans/full-mix-alignment-experiments.md):
it runs the *production* cue-align driver (``pikaraoke.lib.cue_align.align_song``)
on a real song and writes ``<songdir>/karaoke/<stem>.cuealign.ass`` (a distinct
name -- it never clobbers the production ``.ass``), printing an overlap/rescue
report so you can tell whether the mix rung converted any cue-fills to real
audio timing without playing them all.

With ``--mix-rescue`` a second forced aligner is injected over the full mix
(``slice_align_mix``): a bad line the stem re-align cannot recover is retried on
the mix before falling to the cue-paced fill, tagged ``cue_align_line_mix``. All
GPU/ffmpeg I/O lives here; the cue_align module stays pure. Needs the ``pik``
conda env and a local GPU. Example::

    python scripts/cue_align_song.py "/path/Song [dQw4w9WgXcQ].mp4" --mix-rescue
"""

import argparse
import itertools
import logging
import subprocess
import sys
import wave
from pathlib import Path

from pikaraoke.lib.cue_align import (
    SOURCE_FILL,
    SOURCE_REALIGN,
    SOURCE_REALIGN_MIX,
    align_song,
)
from pikaraoke.lib.get_platform import get_temp_directory
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

logger = logging.getLogger("cue_align_song")

MEDIA_EXTS = (".mp4", ".webm", ".mkv")


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

    Lines with no start (hidden / no words) are skipped. A line still sweeping
    when the next one starts is the crawl signature.
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


# A word shorter than this is a failed forced-alignment (parked by stable-ts); a
# line that is mostly these is an alignment failure.
INSTANT_DUR_S = 0.05
# An internal silent gap wider than this inside a single line is the "parked
# tail" drift signature.
GAP_FLAG_S = 3.0


def artifact_metrics(line_objects: list[dict]) -> dict:
    """Count the within-section drift artifacts the overlap metric misses.

    ``max_gap`` is the worst internal word-gap in any line; ``n_gap`` the number
    of lines holding a gap over :data:`GAP_FLAG_S` (a parked tail); ``n_instant``
    the number of lines that are mostly failed (instant) words.
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
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def _decode_to_wav(src: Path, out: Path) -> None:
    """Decode any media to 16 kHz mono s16 WAV (whisper's native input)."""
    _ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(out)])


def _make_slice_align(master_wav: Path, tmp: Path, tag: str, worker: WhisperWorker):
    """Build a ``slice_align`` closure over ``master_wav`` for the cue-align driver.

    Slices ``[t0, t1]`` from the master WAV, force-aligns ``text`` over it, and
    returns the words shifted to absolute song time. Empty on failure (a slice
    stable-ts can't align at all, or an ffmpeg error) so the cue fallback carries
    the affected lines and the run continues.
    """
    counter = itertools.count()

    def slice_align(t0: float, t1: float, text: str, label: str) -> list[dict]:
        slice_wav = tmp / f"{tag}_s{next(counter):04d}.wav"
        try:
            _ffmpeg(["-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", str(master_wav), str(slice_wav)])
            words = worker.align_refine(slice_wav, text, quiet=True)
        except (RuntimeError, subprocess.CalledProcessError) as e:
            logger.warning("%s failed to align: %s; degrading", label, e)
            return []
        finally:
            slice_wav.unlink(missing_ok=True)
        for w in words:
            w["start"] += t0
            w["end"] += t0
        return words

    return slice_align


def align_one(
    song: Path,
    srt_path: Path,
    vocal: Path,
    *,
    worker: WhisperWorker,
    config: PipelineConfig,
    mix_rescue: bool,
    out: Path | None = None,
) -> tuple[list[dict], dict]:
    """Cue-align one SRT song via the production driver; write the .ass.

    Decodes the vocal stem (and, with ``mix_rescue``, the song media as the full
    mix) to WAV, builds the stem/mix slice aligners, and hands them to
    ``cue_align.align_song``. Returns ``(line_objects, stats)``.
    """
    display_lines, cue_spans = cue_spans_from_srt(srt_path.read_text(encoding="utf-8"))
    if not cue_spans:
        raise ValueError(f"{song.stem}: no cues")
    out = out or (song.parent / "karaoke" / f"{song.stem}.cuealign.ass")

    tmp = Path(get_temp_directory())
    vocal_wav = tmp / f"{song.stem}__cuealign_vocal.wav"
    _decode_to_wav(vocal, vocal_wav)
    mix_wav = tmp / f"{song.stem}__cuealign_mix.wav"
    if mix_rescue:
        _decode_to_wav(song, mix_wav)
    try:
        duration = _wav_duration(vocal_wav)
        stem_align = _make_slice_align(vocal_wav, tmp, f"{song.stem}__stem", worker)
        mix_align = (
            _make_slice_align(mix_wav, tmp, f"{song.stem}__mix", worker) if mix_rescue else None
        )
        line_objects, stats = align_song(
            cue_spans,
            display_lines,
            list(display_lines),
            duration,
            stem_align,
            slice_align_mix=mix_align,
        )
    finally:
        vocal_wav.unlink(missing_ok=True)
        mix_wav.unlink(missing_ok=True)

    # Reuse the production ASS renderer for a byte-faithful A/B against the
    # pipeline's own .ass -- it only reads config, mutates nothing.
    ass = LyricAlignStage(worker, config)._generate_ass(line_objects)
    out.parent.mkdir(exist_ok=True)
    out.write_text(ass, encoding="utf-8")
    logger.info("wrote %s", out)
    return line_objects, stats


def report(line_objects: list[dict], stats: dict) -> None:
    placed = [o for o in line_objects if o["words"]]
    hidden = len(line_objects) - len(placed)
    repaced = sum(1 for o in line_objects if o["source"] == SOURCE_FILL)
    realigned = sum(1 for o in line_objects if o["source"] == SOURCE_REALIGN)
    mix_realigned = sum(1 for o in line_objects if o["source"] == SOURCE_REALIGN_MIX)
    overlap, worst = max_line_overlap(line_objects)
    widest = max((o["end"] - o["start"]) / len(o["words"]) for o in placed) if placed else 0.0
    rp = stats["repace"]
    print("\n--- cue-align report ---")
    print(
        f"lines: {len(line_objects)} placed={len(placed)} hidden={hidden} "
        f"(stem re-align={realigned}, mix re-align={mix_realigned}, re-paced={repaced})"
    )
    print(
        f"mix rung: {rp.get('n_mix_attempts', 0)} attempts, "
        f"{rp.get('n_realigned_mix', 0)} accepted, "
        f"{rp.get('n_mix_attempts', 0) - rp.get('n_realigned_mix', 0)} rejected by containment"
    )
    print(f"max inter-line overlap: {overlap:.2f}s" + (f" (lines {worst})" if worst else ""))
    print(f"widest line pace: {widest:.2f}s/word")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("song", type=Path, help="song media file (the .mp4/.webm)")
    ap.add_argument("--vocal", type=Path, help="vocal stem (default: vocal/<stem>---vocal.m4a)")
    ap.add_argument("--srt", type=Path, help="SRT cues (default: subtitles/<stem>.srt)")
    ap.add_argument("--mix-rescue", action="store_true", help="enable the full-mix rescue rung")
    ap.add_argument("--out", type=Path, help="output .ass (default: karaoke/<stem>.cuealign.ass)")
    args = ap.parse_args(argv)

    if not args.song.is_file():
        ap.error(f"song not found: {args.song}")
    srt_path = args.srt or find_srt(args.song)
    if srt_path is None:
        ap.error("no SRT found; pass --srt")
    vocal = args.vocal or find_vocal(args.song)
    if vocal is None:
        ap.error("no vocal stem found; pass --vocal")

    config = PipelineConfig()
    worker = WhisperWorker(config.whisper)
    worker.start()
    try:
        line_objects, stats = align_one(
            args.song,
            srt_path,
            vocal,
            worker=worker,
            config=config,
            mix_rescue=args.mix_rescue,
            out=args.out,
        )
    finally:
        worker.stop()
    report(line_objects, stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
