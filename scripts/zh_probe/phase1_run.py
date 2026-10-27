"""Phase 1 (pilot): run the alignment arms on the four pilot songs and save their artifacts.

Per song and arm it writes <PROBE_ROOT>/phase1/<video_id>/<arm>.json (per-character timings
and the run's wall time and peak VRAM) and <arm>.ass (one \\kf per character). Raw output only;
phase1_review.py turns the JSONs into Ken's review sheets. Every arm aligns the same
Ken-confirmed sheet in <PROBE_ROOT>/sheets/. Run only while the pipeline is idle (one GPU job
at a time).

Arms: W whisper, R romanized MMS_FA, H Mandarin character CTC, Hsk and Hal the two Cantonese
character-CTC candidates (scottykwok, alvanlii). An arm runs only on songs of its languages.

Run (PowerShell, from the repo root; PYTHONUTF8 keeps Chinese text out of cp1252 trouble):
  $env:PYTHONUTF8 = "1"
  uv run --with transformers --with huggingface_hub --with pypinyin --with jieba `
    --with ToJyutping --with opencc-python-reimplemented `
    python scripts/zh_probe/phase1_run.py [--arms W,R,H,Hsk,Hal] [--songs 1,2,9,11]
"""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))

from arms import DEVICE, SAMPLE_RATE, free_memory, make_arm  # noqa: E402
from corpus import PILOT, PROBE_ROOT, find_in_library  # noqa: E402
from sheet import load_sheet  # noqa: E402
from track import ARM_NAMES, track_record, write_ass, write_json  # noqa: E402

OUT_DIR = PROBE_ROOT / "phase1"


def load_stem(video_id: str) -> np.ndarray:
    (stem,) = find_in_library(video_id, "vocal")
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(stem),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ]  # fmt: skip
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def measure(fn):
    """Run ``fn()``; return its value and the wall time and peak VRAM (MB, None on CPU) around it."""
    gc.collect()
    cuda = DEVICE == "cuda"
    if cuda:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    value = fn()
    if cuda:
        torch.cuda.synchronize()
    stats = {
        "wall_s": round(time.perf_counter() - t0, 2),
        "peak_allocated_mb": round(torch.cuda.max_memory_allocated() / 2**20) if cuda else None,
        "peak_reserved_mb": round(torch.cuda.max_memory_reserved() / 2**20) if cuda else None,
    }
    return value, stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", default=",".join(ARM_NAMES))
    parser.add_argument("--songs", default=",".join(str(s.num) for s in PILOT))
    args = parser.parse_args()
    songs = [s for s in PILOT if str(s.num) in args.songs.split(",")]
    device = torch.cuda.get_device_name(0) if DEVICE == "cuda" else "cpu"
    print(f"device {device}, torch {torch.__version__}", flush=True)

    sheets = {s.video_id: load_sheet(s.video_id) for s in songs}
    stems = {s.video_id: load_stem(s.video_id) for s in songs}
    failures = []
    for name in args.arms.split(","):
        arm = make_arm(name)
        todo = [s for s in songs if s.lang in arm.languages]
        if not todo:
            continue
        _, load_stats = measure(arm.load)
        print(f"{name} loaded {arm.model_id}: {load_stats}", flush=True)
        for song in todo:
            try:
                (timings, info), align_stats = measure(
                    lambda: arm.align(stems[song.video_id], sheets[song.video_id], song.lang)
                )
            except (ValueError, RuntimeError):
                # one song or arm failing must not cost the rest of a GPU session
                traceback.print_exc()
                failures.append(f"#{song.num} {name}")
                continue
            run = {"device": device, "load": load_stats, "align": align_stats, **info}
            record = track_record(
                sheets[song.video_id], timings,
                arm=name, model=arm.model_id, lang=song.lang, run=run,
            )  # fmt: skip
            out = OUT_DIR / song.video_id
            out.mkdir(parents=True, exist_ok=True)
            write_json(out / f"{name}.json", record)
            write_ass(out / f"{name}.ass", sheets[song.video_id], timings)
            print(f"#{song.num} {name}: {json.dumps(run)}", flush=True)
        arm.unload()
        free_memory()
    if failures:
        sys.exit(f"failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
