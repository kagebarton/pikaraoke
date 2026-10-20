"""Phase 0c, GPU half: does each arm's model load on the A2000, and at what peak VRAM.

One 30 s clip of a pilot song's vocal stem per arm; each model is loaded, run
once and freed before the next so the peaks do not stack. Raw numbers only. Run
only while the pipeline is idle (one GPU job at a time).

Run: uv run --with transformers --with huggingface_hub python scripts/zh_probe/phase0c_gpu.py
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

from corpus import LIBRARY, PILOT, PROBE_ROOT, find_in_library  # noqa: E402

OUT_PATH = PROBE_ROOT / "phase0" / "phase0c_gpu.json"
WHISPER_PATH = Path("c:/temp/Github/pikaraoke/models/large-v3-turbo.pt")
SAMPLE_RATE = 16000
CLIP_START_S = 60.0
CLIP_LEN_S = 30.0
DEVICE = "cuda"

# (arm, song num, language label, model id)
H_RUNS = [
    ("H", 1, "zh", "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn"),
    ("H", 9, "yue", "scottykwok/wav2vec2-large-xlsr-cantonese"),
    ("H", 9, "yue", "alvanlii/wav2vec2-BERT-cantonese"),
]


def load_clip(song_num: int) -> np.ndarray:
    song = next(s for s in PILOT if s.num == song_num)
    (stem,) = find_in_library(song.video_id, "vocal")
    cmd = [
        "ffmpeg", "-v", "error", "-ss", str(CLIP_START_S), "-t", str(CLIP_LEN_S),
        "-i", str(stem), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ]  # fmt: skip
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def rms_db(clip: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(clip**2)) + 1e-9))


def measure(fn) -> dict:
    """Run ``fn() -> dict`` with peak VRAM and wall time recorded around it."""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    extra = fn()
    torch.cuda.synchronize()
    return {
        "wall_s": round(time.perf_counter() - t0, 2),
        "peak_allocated_mb": round(torch.cuda.max_memory_allocated() / 2**20),
        "peak_reserved_mb": round(torch.cuda.max_memory_reserved() / 2**20),
        **extra,
    }


def run_whisper(song_num: int, lang: str, clip: np.ndarray) -> dict:
    import stable_whisper

    holder = {}

    def load() -> dict:
        holder["m"] = stable_whisper.load_model(str(WHISPER_PATH), device=DEVICE)
        return {}

    def infer() -> dict:
        result = holder["m"].transcribe(clip, language=lang, verbose=None)
        return {"n_segments": len(result.segments), "text": result.text}

    out = {"arm": "W", "song": song_num, "lang": lang, "model": WHISPER_PATH.name}
    out["load"] = measure(load)
    out["infer"] = measure(infer)
    holder.clear()
    return out


def run_mms_fa(song_num: int, clip: np.ndarray) -> dict:
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    holder = {}

    def load() -> dict:
        holder["m"] = bundle.get_model(with_star=False).to(DEVICE)
        return {}

    def infer() -> dict:
        with torch.inference_mode():
            emission, _ = holder["m"](torch.from_numpy(clip)[None].to(DEVICE))
        return {"emission_shape": list(emission.shape)}

    out = {"arm": "R", "song": song_num, "model": "torchaudio MMS_FA"}
    out["load"] = measure(load)
    out["infer"] = measure(infer)
    holder.clear()
    return out


def run_ctc_hf(song_num: int, lang: str, model_id: str, clip: np.ndarray) -> dict:
    from transformers import AutoModelForCTC, AutoProcessor

    holder = {}

    def load() -> dict:
        holder["p"] = AutoProcessor.from_pretrained(model_id)
        holder["m"] = AutoModelForCTC.from_pretrained(model_id).to(DEVICE).eval()
        return {}

    def infer() -> dict:
        p, m = holder["p"], holder["m"]
        feats = p(clip, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        key = "input_values" if "input_values" in feats else "input_features"
        with torch.inference_mode():
            logits = m(feats[key].to(DEVICE)).logits
        return {
            "logits_shape": list(logits.shape),
            "greedy_text": p.batch_decode(logits.argmax(-1).cpu().numpy())[0],
        }

    out = {"arm": "H", "song": song_num, "lang": lang, "model": model_id}
    out["load"] = measure(load)
    out["infer"] = measure(infer)
    holder.clear()
    return out


def prefetch() -> None:
    """Download every model into the default caches (no GPU), so load times exclude the download."""
    import torchaudio
    from huggingface_hub import snapshot_download

    for _, _, _, model_id in H_RUNS:
        t0 = time.perf_counter()
        path = snapshot_download(model_id)
        size_mb = sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file()) / 1e6
        print(f"prefetch {model_id}: {size_mb:.0f} MB in {time.perf_counter() - t0:.0f}s")
    t0 = time.perf_counter()
    torchaudio.pipelines.MMS_FA.get_model(with_star=False)
    print(f"prefetch torchaudio MMS_FA in {time.perf_counter() - t0:.0f}s")
    print(f"torch hub dir: {torch.hub.get_dir()}")


def main() -> None:
    if "--prefetch" in sys.argv:
        prefetch()
        return
    props = torch.cuda.get_device_properties(0)
    results = [{"device": props.name, "total_mb": round(props.total_memory / 2**20)}]
    clips = {num: load_clip(num) for num in (1, 9)}
    results.append(
        {
            "clips": {
                n: {"rms_db": round(rms_db(c), 1), "s": len(c) / SAMPLE_RATE}
                for n, c in clips.items()
            }
        }
    )

    jobs = [
        lambda: run_whisper(1, "zh", clips[1]),
        lambda: run_whisper(9, "yue", clips[9]),
        lambda: run_mms_fa(1, clips[1]),
        lambda: run_mms_fa(9, clips[9]),
        *[
            (lambda n=n, lang=lang, mid=mid: run_ctc_hf(n, lang, mid, clips[n]))
            for _, n, lang, mid in H_RUNS
        ],
    ]
    for job in jobs:
        res = job()
        results.append(res)
        print(json.dumps(res, ensure_ascii=False))
        gc.collect()
        torch.cuda.empty_cache()
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
