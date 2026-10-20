"""Phase 0b aid: whisper transcript of each pilot vocal stem, to help Ken narrow the lyric candidates.

Saves <PROBE_ROOT>/phase0/transcripts/<video_id>.json (segments with times) and .txt
(one segment per line). Whisper runs with the song's language and no previous-text
conditioning, so one hallucinated segment cannot steer the rest. Raw output only;
phase0b_score.py compares it with the candidate sheets. Run only while the
pipeline is idle (one GPU job at a time).

Run: uv run python scripts/zh_probe/phase0b_transcribe.py
"""

from __future__ import annotations

import gc
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))

from corpus import PILOT, PROBE_ROOT, find_in_library  # noqa: E402

OUT_DIR = PROBE_ROOT / "phase0" / "transcripts"
WHISPER_PATH = Path("c:/temp/Github/pikaraoke/models/large-v3-turbo.pt")
SAMPLE_RATE = 16000


def load_stem(video_id: str) -> np.ndarray:
    (stem,) = find_in_library(video_id, "vocal")
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(stem),
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ]  # fmt: skip
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def main() -> None:
    import stable_whisper

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model = stable_whisper.load_model(str(WHISPER_PATH), device="cuda")
    for song in PILOT:
        audio = load_stem(song.video_id)
        t0 = time.perf_counter()
        result = model.transcribe(
            audio, language=song.lang, condition_on_previous_text=False, verbose=None
        )
        wall = time.perf_counter() - t0
        segments = [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in result.segments
        ]
        record = {
            "video_id": song.video_id,
            "language": song.lang,
            "model": WHISPER_PATH.name,
            "audio_s": round(len(audio) / SAMPLE_RATE, 1),
            "wall_s": round(wall, 1),
            "segments": segments,
        }
        (OUT_DIR / f"{song.video_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        lines = [f"[{s['start']:7.2f} - {s['end']:7.2f}] {s['text']}" for s in segments]
        (OUT_DIR / f"{song.video_id}.txt").write_text("\n".join(lines), encoding="utf-8")
        print(f"#{song.num} {song.title}: {len(segments)} segments, {wall:.0f}s", flush=True)
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
