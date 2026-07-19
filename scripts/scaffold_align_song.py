#!/usr/bin/env python
"""Drive scaffold windowed alignment for one genius-origin song; write a .ass.

Tier-2 counterpart to ``cue_align_song.py`` for songs with no uploader SRT: no
1:1 cue source exists, so one is *built* from audio-clock anchors (YouTube ASR
+ whisper-transcribe, unioned via :func:`cue_align.merge_cue_spans`) and,
where available, densified/warped against an external line-timing scaffold
(``--timing sidecar`` for the Appendix B fetch-pillar sidecar, ``--timing lrc``
for a live LRCLIB fetch) via :func:`cue_align.warp_scaffold_cues`. The dense
cue list then drives the same production :func:`cue_align.align_song` the SRT
path uses.

Reads the Genius lyrics + genius id/title/artist + whisper transcribe words
from the song's alignment-debug bundle; the ASR ``.json3`` and vocal stem from
disk; the timing scaffold from a sidecar on disk or LRCLIB live over the
network. Writes ``<songdir>/karaoke/<stem>.scaffold.ass`` (a distinct name --
never the production ``.ass`` or the SRT path's ``.cuealign.ass``) and prints
the overlap/pace/flag/warp-fit report. Touches nothing in the production
pipeline. Needs the ``pik`` conda env, a local GPU, and (for ``--timing lrc``)
network. E.g.::

    python scripts/scaffold_align_song.py "/path/to/Song [dQw4w9WgXcQ].mp4"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Sibling import: reuse the SRT harness's I/O shims. The repo's editable
# install already puts ``pikaraoke`` on the path; only ``scripts`` needs
# adding so ``cue_align_song`` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cue_align_song import (  # noqa: E402
    _ffmpeg,
    _make_slice_align,
    _wav_duration,
    find_vocal,
    report,
)

from pikaraoke.lib import lrclib, ytasr  # noqa: E402
from pikaraoke.lib.cue_align import (  # noqa: E402
    align_song,
    merge_cue_spans,
    warp_scaffold_cues,
)
from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

logger = logging.getLogger("scaffold_align_song")


def find_bundle(song: Path) -> Path | None:
    cand = song.parent / "alignment_debug" / f"{song.stem}.json"
    return cand if cand.is_file() else None


def find_asr(song: Path) -> Path | None:
    cand = song.parent / "subtitles" / f"{song.stem}.en.asr.json3"
    return cand if cand.is_file() else None


def find_timing_sidecar(song: Path) -> Path | None:
    cand = song.parent / "lyrics" / f"{song.stem}.timing.json"
    return cand if cand.is_file() else None


def sidecar_scaffold_cues(
    sidecar_path: Path, align_lines: list[str]
) -> dict[int, tuple[float, float]]:
    """Per-line scaffold cues from the Appendix B fetch-pillar sidecar.

    ``kind == "line"`` bodies are LRC text, mapped by :func:`lrclib.cue_spans_for_lines`
    (text match against ``align_lines``). ``kind == "word"`` bodies are the raw
    Musixmatch richsync JSON (a list of ``{ts, te, l: [{c, o}]}`` entries); only
    each entry's line start/end and joined word text are needed for a scaffold
    (word-level detail is the word-route's job, not this one), so entries are
    reduced to LRC-shaped ``(text, (start, end))`` pairs and mapped the same
    way. Empty on ``kind == "none"`` or an unparseable sidecar.
    """
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("unreadable timing sidecar %s: %s", sidecar_path, e)
        return {}
    kind = sidecar.get("kind")
    body = sidecar.get("body")
    if kind == "line" and body:
        return lrclib.cue_spans_for_lines(body, align_lines) or {}
    if kind == "word" and body:
        entries = json.loads(body) if isinstance(body, str) else body
        cue_texts = ["".join(w.get("c", "") for w in entry.get("l", [])) for entry in entries]
        spans = [(entry["ts"], entry.get("te", entry["ts"])) for entry in entries]
        mapping = lrclib.map_lines_to_cues(align_lines, cue_texts)
        return {lid: spans[ci] for lid, ci in mapping.items()}
    return {}


def fetch_lrclib_cues(
    genius: dict | None, display_lines: list[str], duration: float | None
) -> dict[int, tuple[float, float]]:
    """Live LRCLIB fetch keyed by the Genius artist/title -> per-line cue spans.

    Mirrors the production fetcher (search -> reference-free select -> map
    onto our lyric sheet). Returns ``{}`` on no match or no Genius keys.
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


def run_song(
    song: Path,
    bundle: dict,
    asr_path: Path,
    vocal: Path,
    *,
    worker: WhisperWorker,
    config: PipelineConfig,
    timing: str,
    pad: float = 0.75,
    out: Path | None = None,
) -> tuple[list[dict], dict, dict]:
    """Scaffold-align one genius-origin song with an already-started ``worker``.

    Builds audio-clock anchors (ASR + transcribe), a scaffold from ``timing``
    (``"sidecar"`` or ``"lrc"``, ``"none"`` to skip and align on anchors alone),
    warps them together, then hands the dense cue list to the shared
    :func:`cue_align.align_song`. Returns ``(line_objects, align_stats,
    scaffold_stats)``.
    """
    lyrics = bundle["lyrics"]
    display_lines = lyrics["lines"]
    align_lines = lyrics["align_lines"]
    duration = bundle.get("media_duration_s")
    if not duration:
        raise ValueError(f"{song.stem}: bundle has no media_duration_s")

    asr_words, _frac = ytasr.parse_json3(asr_path.read_text(encoding="utf-8"))
    asr_cues = ytasr.cue_spans_for_lines(asr_words, align_lines) or {}
    tx_words = ytasr.normalize_words(bundle.get("transcribe_words") or [])
    tx_cues = ytasr.cue_spans_for_lines(tx_words, align_lines) or {}
    anchors = merge_cue_spans(tx_cues, asr_cues)
    if not anchors:
        raise ValueError(f"{song.stem}: no ASR/transcribe anchors to calibrate against")

    scaffold: dict[int, tuple[float, float]] = {}
    if timing == "sidecar":
        sidecar_path = find_timing_sidecar(song)
        if sidecar_path is not None:
            scaffold = sidecar_scaffold_cues(sidecar_path, align_lines)
    elif timing == "lrc":
        scaffold = fetch_lrclib_cues(lyrics.get("genius"), display_lines, duration)

    cue_spans = warp_scaffold_cues(anchors, scaffold, align_lines, duration)
    scaffold_stats = {
        "n_asr": len(asr_cues),
        "n_tx": len(tx_cues),
        "n_anchors": len(anchors),
        "n_scaffold": len(scaffold),
        "n_lines": len(align_lines),
    }

    tmp = Path(get_temp_directory())
    vocal_wav = tmp / f"{song.stem}__scaffold_vocal.wav"
    _ffmpeg(["-i", str(vocal), "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(vocal_wav)])
    try:
        wav_dur = _wav_duration(vocal_wav)
        slice_align = _make_slice_align(vocal_wav, tmp, song.stem, worker)
        line_objects, align_stats = align_song(
            cue_spans, display_lines, align_lines, wav_dur, slice_align, pad_s=pad
        )
    finally:
        vocal_wav.unlink(missing_ok=True)

    ass = LyricAlignStage(worker, config)._generate_ass(line_objects)
    out = out or (song.parent / "karaoke" / f"{song.stem}.scaffold.ass")
    out.parent.mkdir(exist_ok=True)
    out.write_text(ass, encoding="utf-8")
    logger.info("wrote %s", out)
    return line_objects, align_stats, scaffold_stats


def report_scaffold(scaffold_stats: dict) -> None:
    print(
        f"scaffold: anchors={scaffold_stats['n_anchors']} "
        f"(asr={scaffold_stats['n_asr']} tx={scaffold_stats['n_tx']}) "
        f"external={scaffold_stats['n_scaffold']}/{scaffold_stats['n_lines']} lines"
    )


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("song", type=Path, help="song media file (the .mp4/.webm)")
    ap.add_argument("--vocal", type=Path, help="vocal stem (default: vocal/<stem>---vocal.m4a)")
    ap.add_argument("--asr", type=Path, help="ASR json3 (default: subtitles/<stem>.en.asr.json3)")
    ap.add_argument(
        "--bundle", type=Path, help="debug bundle (default: alignment_debug/<stem>.json)"
    )
    ap.add_argument(
        "--timing",
        choices=("sidecar", "lrc", "none"),
        default="sidecar",
        help="external line-timing scaffold source (default: sidecar)",
    )
    ap.add_argument("--pad", type=float, default=0.75, help="slice pad into silence (s)")
    ap.add_argument("--out", type=Path, help="output .ass (default: karaoke/<stem>.scaffold.ass)")
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

    config = PipelineConfig()
    worker = WhisperWorker(config.whisper)
    worker.start()
    try:
        line_objects, align_stats, scaffold_stats = run_song(
            args.song,
            bundle,
            asr_path,
            vocal,
            worker=worker,
            config=config,
            timing=args.timing,
            pad=args.pad,
            out=args.out,
        )
    finally:
        worker.stop()
    report_scaffold(scaffold_stats)
    report(line_objects, align_stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
