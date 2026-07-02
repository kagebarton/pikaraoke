#!/usr/bin/env python
"""Drive cue-anchored windowed alignment for one song and write a .ass to eyeball.

A standalone harness for the fresh path in ``pikaraoke.lib.cue_align`` -- it
touches nothing in the production pipeline. Given a song that has an
uploader-synced SRT and a separated vocal stem on disk, it:

  1. reads the SRT into 1:1 line cues,
  2. groups them into silence-bounded sections,
  3. force-aligns each section's slice via the real WhisperWorker,
  4. splits the words back to lines and renders a karaoke ``.ass``,

writing to ``<songdir>/karaoke/<stem>.cuealign.ass`` (a distinct name -- it
never clobbers the production ``.ass``) and printing an overlap/pace report so
you can tell whether the crawls are gone without playing all of them.

All GPU/ffmpeg I/O lives here; the cue_align module stays pure. The per-song
work is :func:`align_song` (worker injected, so a batch runner loads the model
once). Needs the ``pik`` conda env and a local GPU. Example::

    python scripts/cue_align_song.py "/path/to/Song [dQw4w9WgXcQ].mp4"
"""

import argparse
import logging
import subprocess
import sys
import wave
from pathlib import Path

from pikaraoke.lib.cue_align import (
    SOURCE_FILL,
    SOURCE_REALIGN,
    fit_offset,
    repace_bad_lines,
    segment_by_gaps,
    split_section_to_lines,
)
from pikaraoke.lib.get_platform import get_temp_directory
from pikaraoke.lib.srt_prior import cue_spans_from_srt
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

logger = logging.getLogger("cue_align_song")

MEDIA_EXTS = (".mp4", ".webm", ".mkv")


def build_config() -> PipelineConfig:
    """PipelineConfig for the cue-align path -- production whisper defaults.

    Instant-word removal stays on (the default): the aligner drops the words it
    could not time, the normalised split tolerates the gaps, and
    ``repace_bad_lines`` rebuilds the affected lines from their cues. Keeping
    failed words instead only re-introduced parked-tail drift and tripped
    refine on the zero-duration words.
    """
    return PipelineConfig()


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


# A word shorter than this is a failed forced-alignment (zero-duration, parked
# by stable-ts); a line that is mostly these is an alignment failure.
INSTANT_DUR_S = 0.05

# An internal silent gap wider than this inside a single line is the "parked
# tail" drift signature (stable-ts dumps unaligned words at the slice end).
GAP_FLAG_S = 3.0


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


def section_drift(
    sections, cue_spans: list[tuple[float, float]], line_objects: list[dict]
) -> list[dict]:
    """Per-section drift, for correlating drift with section size.

    For each section: its size (``n_lines``, ``dur``), how many placed lines
    drifted (internal gap over :data:`GAP_FLAG_S`), the worst internal gap, and
    ``max_cue_gap`` -- the widest gap between consecutive cues *inside* the
    section, i.e. the best place a more aggressive split could have cut it. A
    small ``max_cue_gap`` on a drifted section means there is no silence to
    split on (a hard size cap would be needed instead).
    """
    by_id = {o["line_id"]: o for o in line_objects}
    rows: list[dict] = []
    for idx, s in enumerate(sections):
        lids = list(s.line_ids)
        cue_gaps = [cue_spans[b][0] - cue_spans[a][1] for a, b in zip(lids, lids[1:])]
        max_gap = 0.0
        n_drift = 0
        n_placed = 0
        for lid in lids:
            o = by_id.get(lid)
            if not o or not o["words"]:
                continue
            n_placed += 1
            gap = max(
                (b["start"] - a["end"] for a, b in zip(o["words"], o["words"][1:])),
                default=0.0,
            )
            max_gap = max(max_gap, gap)
            if gap > GAP_FLAG_S:
                n_drift += 1
        rows.append(
            {
                "idx": idx,
                "n_lines": len(lids),
                "dur": round(s.t1 - s.t0, 1),
                "n_placed": n_placed,
                "max_gap": round(max_gap, 1),
                "n_drift": n_drift,
                "max_cue_gap": round(max(cue_gaps), 2) if cue_gaps else 0.0,
            }
        )
    return rows


def _ffmpeg(args: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
    )


def _wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def align_with_cues(
    song: Path,
    *,
    display_lines: list[str],
    align_lines: list[str],
    cue_spans: list[tuple[float, float]],
    vocal: Path,
    worker: WhisperWorker,
    config: PipelineConfig,
    out: Path,
    tag: str,
    gap: float = 1.5,
    pad: float = 0.75,
) -> tuple[list[dict], list]:
    """Windowed-align one song from a dense per-line cue list; write the .ass.

    The cue-source-agnostic core shared by the SRT path (:func:`align_song`) and
    the ASR path (``scripts/asr_align_song.py``). ``cue_spans`` is the 1:1
    per-line ``(start, end)`` list: it is segmented into silence-bounded sections,
    each section's vocal slice is force-aligned once via ``worker``, the words are
    split back to lines, and the lines the align could not place are re-paced from
    their cues. ``tag`` names the scratch WAVs and the default output suffix, so
    the two paths never clobber each other's files.

    When the fitted display lead exceeds ``pad`` the whole song is re-aligned
    once on offset-shifted cues -- past that, every section window clips its
    leading sung words, so no per-line repair can recover them.

    Returns ``(line_objects, sections)`` so a caller can score overlap/coverage
    and correlate drift with section size. The worker lifecycle is the caller's.
    """
    if not cue_spans:
        raise ValueError(f"{song.stem}: no cues")

    tmp = Path(get_temp_directory())
    vocal_wav = tmp / f"{song.stem}__{tag}_vocal.wav"
    # 16 kHz mono is whisper's native input; anything more just costs decode.
    _ffmpeg(["-i", str(vocal), "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(vocal_wav)])
    try:
        duration = _wav_duration(vocal_wav)

        def align_pass(spans: list[tuple[float, float]]) -> tuple[list[dict], list]:
            sections = segment_by_gaps(spans, gap_s=gap, pad_s=pad, duration=duration)
            logger.info("%s: %d cues -> %d sections", song.stem[:40], len(spans), len(sections))
            objs: list[dict] = []
            for i, section in enumerate(sections):
                slice_wav = tmp / f"{song.stem}__{tag}_s{i:03d}.wav"
                _ffmpeg(
                    [
                        "-ss",
                        f"{section.t0:.3f}",
                        "-to",
                        f"{section.t1:.3f}",
                        "-i",
                        str(vocal_wav),
                        str(slice_wav),
                    ]
                )
                try:
                    sub_text = "\n".join(align_lines[lid] for lid in section.line_ids)
                    words = worker.align_refine(slice_wav, sub_text)
                except RuntimeError as e:
                    # stable-ts gives up on a slice it cannot align at all
                    # (returns None internally), surfaced here as a worker
                    # error. That is the ultimate "align failed" -- leave the
                    # section's words empty so repace_bad_lines carries every
                    # line from its cue. The worker stays alive, so the next
                    # section proceeds.
                    logger.warning(
                        "section %d (lines %d-%d) failed to align: %s; re-pacing from cue",
                        i,
                        section.lid_lo,
                        section.lid_hi,
                        e,
                    )
                    words = []
                finally:
                    slice_wav.unlink(missing_ok=True)
                for w in words:
                    w["start"] += section.t0
                    w["end"] += section.t0
                objs.extend(
                    split_section_to_lines(section, words, display_lines, align_lines, spans)
                )
            return objs, sections

        line_objects, sections = align_pass(cue_spans)
        spans = cue_spans
        offset = fit_offset(line_objects, cue_spans, align_lines)
        if abs(offset) > pad:
            # Beyond the pad, every section window provably clips its leading
            # words; shift the cues onto the audio clock and re-align once.
            logger.info(
                "%s: display lead %+.2fs exceeds pad %.2fs; re-sectioning on shifted cues",
                song.stem[:40],
                offset,
                pad,
            )
            spans = [
                (max(0.0, c0 + offset), max(0.0, c0 + offset, c1 + offset)) for c0, c1 in cue_spans
            ]
            line_objects, sections = align_pass(spans)

        def realign_line(lid: int, t0: float, t1: float) -> list[dict] | None:
            """Narrow per-line forced align over a bad line's cue window."""
            w0, w1 = max(0.0, t0 - pad), min(duration, t1 + pad)
            if w1 - w0 < 0.2:
                return None
            slice_wav = tmp / f"{song.stem}__{tag}_l{lid:03d}.wav"
            _ffmpeg(["-ss", f"{w0:.3f}", "-to", f"{w1:.3f}", "-i", str(vocal_wav), str(slice_wav)])
            try:
                words = worker.align_refine(slice_wav, align_lines[lid])
            except RuntimeError as e:
                logger.warning("line %d re-align failed: %s; re-pacing from cue", lid, e)
                return None
            finally:
                slice_wav.unlink(missing_ok=True)
            for w in words:
                w["start"] += w0
                w["end"] += w0
            return words

        # Rescue lines the align could not place: one narrow per-line re-align
        # each, then a paced fill across the cue window for whatever remains.
        line_objects, _repace_stats = repace_bad_lines(
            line_objects,
            spans,
            display_lines,
            align_lines,
            duration=duration,
            realign=realign_line,
        )
    finally:
        vocal_wav.unlink(missing_ok=True)

    # Reuse the production ASS renderer for a byte-faithful A/B against the
    # pipeline's own .ass -- it only reads config, mutates nothing.
    ass = LyricAlignStage(worker, config)._generate_ass(line_objects)
    out.parent.mkdir(exist_ok=True)
    out.write_text(ass, encoding="utf-8")
    logger.info("wrote %s", out)
    return line_objects, sections


def align_song(
    song: Path,
    srt_path: Path,
    vocal: Path,
    *,
    worker: WhisperWorker,
    config: PipelineConfig,
    gap: float = 1.5,
    pad: float = 0.75,
    out: Path | None = None,
) -> tuple[list[dict], list]:
    """Cue-align one SRT song with an already-started ``worker``; write the .ass.

    Thin loader over :func:`align_with_cues`: reads the uploader SRT into 1:1
    line cues, then hands them to the shared windowed driver. SRT has no
    align/display distinction, so ``align_lines`` mirrors the cue texts.
    """
    display_lines, cue_spans = cue_spans_from_srt(srt_path.read_text(encoding="utf-8"))
    out = out or (song.parent / "karaoke" / f"{song.stem}.cuealign.ass")
    return align_with_cues(
        song,
        display_lines=display_lines,
        align_lines=list(display_lines),
        cue_spans=cue_spans,
        vocal=vocal,
        worker=worker,
        config=config,
        out=out,
        tag="cuealign",
        gap=gap,
        pad=pad,
    )


def report(line_objects: list[dict]) -> None:
    placed = [o for o in line_objects if o["words"]]
    hidden = len(line_objects) - len(placed)
    repaced = sum(1 for o in line_objects if o["source"] == SOURCE_FILL)
    realigned = sum(1 for o in line_objects if o["source"] == SOURCE_REALIGN)
    overlap, worst = max_line_overlap(line_objects)
    widest = max((o["end"] - o["start"]) / len(o["words"]) for o in placed) if placed else 0.0
    print("\n--- cue-align report ---")
    print(
        f"lines: {len(line_objects)} placed={len(placed)} hidden={hidden} "
        f"(re-aligned={realigned}, re-paced={repaced})"
    )
    print(f"max inter-line overlap: {overlap:.2f}s" + (f" (lines {worst})" if worst else ""))
    print(f"widest line pace: {widest:.2f}s/word")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("song", type=Path, help="song media file (the .mp4/.webm)")
    ap.add_argument("--vocal", type=Path, help="vocal stem (default: vocal/<stem>---vocal.m4a)")
    ap.add_argument("--srt", type=Path, help="SRT cues (default: subtitles/<stem>.srt)")
    ap.add_argument("--gap", type=float, default=1.5, help="section-split gap threshold (s)")
    ap.add_argument("--pad", type=float, default=0.75, help="slice pad into silence (s)")
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

    config = build_config()
    worker = WhisperWorker(config.whisper)
    worker.start()
    try:
        line_objects, _sections = align_song(
            args.song,
            srt_path,
            vocal,
            worker=worker,
            config=config,
            gap=args.gap,
            pad=args.pad,
            out=args.out,
        )
    finally:
        worker.stop()
    report(line_objects)
    return 0


if __name__ == "__main__":
    sys.exit(main())
