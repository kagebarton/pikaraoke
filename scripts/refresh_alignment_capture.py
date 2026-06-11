#!/usr/bin/env python3
"""Re-capture joint-matcher whisper inputs for the timing-eval corpus.

Phase 2b of ``plans/matcher-timing-eval.md``: the joint matcher can
weight transcribe matches by whisper word probability, but bundles
captured before the worker retained probabilities can't replay that
knob. This driver re-runs the two model passes the joint matcher
consumes — align + refine, and transcribe without refine — against each
corpus song's cached vocal stem, and writes fresh minimal bundles (with
probabilities) for ``eval_alignment.py --debug-dir``.

The song library itself is untouched: no pipeline stages run, no
.ass/.srt outputs are written.

Run from the repo root::

    python scripts/refresh_alignment_capture.py [--folder PATH]
        [--out-dir PATH] [--songs FILTER] [--force]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Allow running as ``python scripts/refresh_alignment_capture.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_alignment import (  # noqa: E402
    _VIDEO_ID_RE,
    DEFAULT_FOLDER,
    PROVENANCE_FILE,
    find_reference_lrc,
    find_reference_srt,
)

from pikaraoke.lib.alignment_eval import parse_reference_cues  # noqa: E402
from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402


def find_vocal_m4a(song_dir: Path, stem: str) -> Path | None:
    """Cached vocal stem for ``stem``, falling back to a video-ID glob."""
    cand = song_dir / "vocal" / f"{stem}---vocal.m4a"
    if cand.is_file():
        return cand
    m = _VIDEO_ID_RE.search(stem)
    if m:
        hits = sorted((song_dir / "vocal").glob(f"*{m.group(1)}*---vocal.m4a"))
        if hits:
            return hits[0]
    return None


def decode_vocal(vocal_m4a: Path, wav_path: Path) -> None:
    """Decode the cached vocal stem to WAV with the pipeline's ffmpeg args."""
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-i",
            str(vocal_m4a),
            "-ac",
            "2",
            "-ar",
            "44100",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        check=True,
    )


def collect_jobs(song_dir: Path, debug_dir: Path, songs_filter: str | None) -> list[dict]:
    """One job dict per corpus song with resolvable inputs.

    SRT-sourced songs re-read lyrics from the YouTube SRT (today's
    cleaning, matching what production would feed align). Other songs
    need an LRCLIB timing reference to be in the corpus, and reuse the
    bundle's capture-time lines verbatim — their original lyric source
    files lived in temp dirs and are gone.
    """
    jobs = []
    for path in sorted(debug_dir.glob("*.json")):
        if path.name == PROVENANCE_FILE:
            continue
        bundle = json.loads(path.read_text(encoding="utf-8"))
        stem = bundle.get("song_stem", path.stem)
        if songs_filter and songs_filter.lower() not in stem.lower():
            continue
        lyrics = bundle.get("lyrics", {})
        if lyrics.get("source_kind") == "srt":
            srt_path = find_reference_srt(bundle, song_dir)
            if srt_path is None:
                print(f"skip {stem[:60]} — reference SRT missing")
                continue
            stem = srt_path.stem
            lines, _starts = parse_reference_cues(srt_path.read_text(encoding="utf-8"))
            align_lines = list(lines)
            source_kind = "srt"
            source_path = f"subtitles/{srt_path.name}"
        else:
            if find_reference_lrc(bundle, song_dir) is None:
                print(f"skip {stem[:60]} — no LRCLIB timing reference")
                continue
            lines = lyrics.get("lines") or []
            align_lines = lyrics.get("align_lines") or list(lines)
            if not lines:
                print(f"skip {stem[:60]} — bundle lacks cached lyric lines")
                continue
            source_kind = lyrics.get("source_kind", "txt")
            source_path = lyrics.get("source_path")
        vocal = find_vocal_m4a(song_dir, stem)
        if vocal is None:
            print(f"skip {stem[:60]} — vocal stem missing")
            continue
        jobs.append(
            {
                "stem": stem,
                "lines": lines,
                "align_lines": align_lines,
                "vocal": vocal,
                "source_kind": source_kind,
                "source_path": source_path,
            }
        )
    return jobs


def capture_song(worker: WhisperWorker, job: dict, wav_path: Path) -> dict:
    """Run align+refine and transcribe(no refine); return the bundle dict."""
    lyrics_text = "\n".join(job["align_lines"])

    check = worker.align_check(vocal_path=wav_path, lyrics_text=lyrics_text)
    align_words = worker.refine_from_cached(check["result_id"], wav_path)
    transcribe_words = worker.transcribe_words(wav_path, refine=False)

    return {
        "schema": "eval-refresh-v1",
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "song_stem": job["stem"],
        "words": align_words,
        "transcribe_words": transcribe_words,
        "lyrics": {
            "source_kind": job["source_kind"],
            "source_path": job["source_path"],
            "lines": job["lines"],
            "align_lines": job["align_lines"],
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--folder", default=DEFAULT_FOLDER, help="song library folder")
    p.add_argument(
        "--out-dir",
        default=None,
        help="bundle output dir (default: <folder>/alignment_debug_probs)",
    )
    p.add_argument("--songs", default=None, help="substring filter on song stem")
    p.add_argument("--force", action="store_true", help="re-capture songs already in out-dir")
    args = p.parse_args()

    song_dir = Path(args.folder)
    debug_dir = song_dir / "alignment_debug"
    out_dir = Path(args.out_dir) if args.out_dir else song_dir / "alignment_debug_probs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Carry the provenance cache over so eval runs against out_dir
    # don't re-query YouTube.
    prov = debug_dir / PROVENANCE_FILE
    if prov.is_file():
        shutil.copy2(prov, out_dir / PROVENANCE_FILE)

    jobs = collect_jobs(song_dir, debug_dir, args.songs)
    if not jobs:
        print("no eligible songs")
        return 1
    print(f"{len(jobs)} songs to capture -> {out_dir}")

    tmp_dir = Path(get_temp_directory()) / "refresh_alignment_capture"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig()
    worker = WhisperWorker(config.whisper)
    print("loading whisper model...")
    worker.start()
    try:
        for i, job in enumerate(jobs, 1):
            stem = job["stem"]
            out_path = out_dir / f"{stem}.json"
            if out_path.is_file() and not args.force:
                print(f"[{i}/{len(jobs)}] exists, skipping: {stem[:60]}")
                continue
            print(f"[{i}/{len(jobs)}] {stem[:60]}", flush=True)
            wav_path = tmp_dir / f"{stem}_vocal.wav"
            decode_vocal(job["vocal"], wav_path)
            try:
                bundle = capture_song(worker, job, wav_path)
            finally:
                wav_path.unlink(missing_ok=True)
            out_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            tw = bundle["transcribe_words"]
            with_prob = sum(1 for w in tw if "probability" in w)
            print(
                f"    {len(bundle['words'])} align words, {len(tw)} transcribe words "
                f"({with_prob} with probability)"
            )
    finally:
        worker.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
