#!/usr/bin/env python3
"""Phase 1 steps 2-3: run the large-v3 fp16 regen against the study copy.

Mirrors ``regen_alignment_bundles.run_jobs()``'s body (same stage-building /
lyric-reuse machinery) but adds per-song wall-clock + peak-VRAM
instrumentation, which ``run_jobs()`` does not expose. Points at the Phase 1
study copy only -- never ``/home/ken/pikaraoke-songs``.

Deliberately runs with no ``StemWorker`` (``stem_worker=None`` throughout),
unlike ``run_jobs()``: all 8 study-copy songs already have vocal+nonvocal
stems (verified at copy time), so the separator is never invoked for
separation -- but ``run_jobs()`` still starts it unconditionally "the
de-reverb retry can fire on any song", reserving ~1 GB VRAM for the whole
run. Co-resident with large-v3 fp16 (~4.6 GB, see Phase 0) that overflows
this card's ~5.6 GiB usable budget -- the exact "needs worker serialization"
gap flagged in memory project_large_v3_fp16_trick.md from the older
jointrefine study, hit here as a mid-run OOM on song 2 of the first attempt.
``LyricAlignStage``'s de-reverb gate treats ``stem_worker=None`` as a
designed no-op ("retry unavailable"), not an error (lyric_align.py
``_transcribe_yield_wpm``) -- and skipping it also holds audio input
constant across all 8 songs for this run, which is preferable for an A/B
that is supposed to isolate the whisper-model variable alone.

GPU memory is polled externally via ``nvidia-smi`` (a background thread per
song) because the model loads inside the whisper worker's spawned
subprocess, invisible to in-process ``torch.cuda`` stats in this process.

Guarded under __main__: the workers spawn (not fork) subprocesses that
re-import this file in the child.

Run from the repo root::

    python scripts/l3v_phase1_regen.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

STUDY_FOLDER = Path("/home/ken/pikaraoke-study-l3v/songs")
PRODUCTION_FOLDER = Path("/home/ken/pikaraoke-songs")
LARGE_V3_MODEL_PATH = str(Path(__file__).resolve().parents[1] / "models" / "large-v3.pt")


class _GpuPeakMonitor:
    """Polls system-wide GPU memory via nvidia-smi while active, tracks the max."""

    def __init__(self, interval_s: float = 0.25) -> None:
        self._interval_s = interval_s
        self._peak_mib = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def __enter__(self) -> "_GpuPeakMonitor":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _poll(self) -> None:
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                mib = int(out.stdout.strip().splitlines()[0])
                self._peak_mib = max(self._peak_mib, mib)
            except (subprocess.SubprocessError, ValueError, IndexError, OSError):
                pass
            self._stop.wait(self._interval_s)

    @property
    def peak_mib(self) -> int:
        return self._peak_mib


def main() -> int:
    from pikaraoke.lib.get_platform import get_temp_directory
    from pikaraoke.pipeline.config import PipelineConfig
    from pikaraoke.pipeline.orchestrator import PipelineOrchestrator
    from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker
    from scripts.regen_alignment_bundles import (
        _build_stages,
        _make_genius,
        _prepare_lyrics,
        backup_text_folders,
        print_report,
        resolve_plan,
        scan_folder,
    )

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="Write per-song timing/VRAM JSON here"
    )
    args = parser.parse_args()

    folder = STUDY_FOLDER
    assert (
        folder.resolve() != PRODUCTION_FOLDER.resolve()
    ), "refusing to run against the production library"

    jobs = scan_folder(folder, include_all=True)
    for job in jobs:
        job.plan = resolve_plan(job, reset=False)

    print_report(jobs, folder, reset=False)

    bad = [j for j in jobs if j.plan.kind != "seed"]
    if bad:
        print("ABORT: non-seed plan(s) found, refusing to run unattended:")
        for j in bad:
            print(f"  {j.song_path.name}: kind={j.plan.kind}")
        return 1

    backup = backup_text_folders(folder)
    print(f"Backed up subtitles/karaoke/lyrics/alignment_debug to: {backup}\n")

    config = PipelineConfig()
    config.intermediate_dir = get_temp_directory()
    config.whisper.load_model.model_path = LARGE_V3_MODEL_PATH
    config.whisper.load_model.fp16_weights = True
    genius = _make_genius()

    # No StemWorker: all 8 songs already have stems (verified at copy time),
    # and holding the separator resident alongside large-v3 fp16 overflows
    # this card's VRAM budget (see module docstring). stem_worker=None is a
    # designed no-op for the de-reverb-retry gate, not a hack.
    stem_worker = None
    whisper_worker = WhisperWorker(config.whisper)
    lyrics_dir = Path(
        tempfile.mkdtemp(prefix="l3v_regen_lyrics_", dir=config.intermediate_dir or None)
    )

    runnable = [j for j in jobs if j.plan and j.plan.kind != "skip"]
    per_song: list[dict] = []
    succeeded = failed = 0
    try:
        whisper_worker.start()
        for i, job in enumerate(runnable, 1):
            song = job.song_path
            print(f"\n[{i}/{len(runnable)}] {song.name} -- {job.plan.label}")
            lyrics_path, lyric_stage = _prepare_lyrics(job, genius, lyrics_dir)
            stages = _build_stages(song, lyric_stage, whisper_worker, config, stem_worker)
            orch = PipelineOrchestrator(stages, stem_worker, whisper_worker, config)

            monitor = _GpuPeakMonitor()
            start = time.time()
            ok, err = True, None
            with monitor:
                try:
                    orch.run_one(song, lyrics_path)
                    print(f"  OK: {song.name}")
                    succeeded += 1
                except Exception as e:
                    print(f"  FAILED: {song.name}: {e}")
                    failed += 1
                    ok, err = False, str(e)
            per_song.append(
                {
                    "song": song.stem,
                    "succeeded": ok,
                    "error": err,
                    "elapsed_s": round(time.time() - start, 2),
                    "peak_vram_mib": monitor.peak_mib,
                }
            )
    finally:
        shutil.rmtree(lyrics_dir, ignore_errors=True)
        whisper_worker.stop()

    print(f"\nDone. succeeded={succeeded} failed={failed}")
    for row in per_song:
        print(
            f"  {row['song']}: {row['elapsed_s']}s peak={row['peak_vram_mib']} MiB "
            f"succeeded={row['succeeded']}"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"per_song": per_song}, indent=2))
        print(f"\nResults written to {args.out}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
