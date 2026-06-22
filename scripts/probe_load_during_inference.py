"""One-off probe: does a separator model LOAD contend with whisper
inference the way two concurrent inferences do?

Background: probe_concurrent_vram.py showed concurrent demix+refine inference
is 6-11x SLOWER than sequential (WDDM time-slicing contention). But the
shipped design deliberately overlaps the stem worker's eager model *restore*
(a drop+reload, ~900 MB to GPU) with whisper align+refine in the other
process. A load is mostly H2D memcpy + allocation, not SM compute, so it may
contend far less. This probe measures that directly.

Separator side: a spawn'd subprocess that repeatedly drop+reloads the roformer
(exactly StemWorker._swap_model: instance=None -> gc -> empty_cache ->
load_model -> empty_cache), timing each load. No demix.
Whisper side: the real WhisperWorker running align_check + refine_from_cached.

Phases:
  LOAD_ONLY    - N roformer reloads, whisper idle
  INFER_ONLY   - N align+refine, separator idle  [the long pole]
  CONCURRENT   - both at once -> is each op slower than standalone?

Run:  .venv/Scripts/python.exe scripts/probe_load_during_inference.py [sep_model.ckpt]
"""

from __future__ import annotations

import logging
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from pikaraoke.lib.get_platform import get_temp_directory
from pikaraoke.pipeline.config import WhisperModelConfig
from pikaraoke.pipeline.workers._ipc import WORKER_CONTEXT
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

PROXY = "vocals_mel_band_roformer.ckpt"
MODELS_DIR = str(Path(__file__).resolve().parents[1] / "models")
SLICE_SECONDS = 20.0
N_LOAD = 6
N_INFER = 4
PRODUCTION_CARD_MIB = 6144
MPV_RESERVE_MIB = 300

LYRICS = """When the lights go down and the music starts to play
I can hear your voice calling out my name
Every single moment feels so far away
But I know that nothing will ever be the same
Hold me close and never let me go
Through the rain and all the tears we know"""


def _query_used_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(out.stdout.strip().splitlines()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None


class VramSampler(threading.Thread):
    def __init__(self, interval: float = 0.1) -> None:
        super().__init__(daemon=True)
        self._interval = interval
        self._stop = threading.Event()
        self._phase = "init"
        self._lock = threading.Lock()
        self.samples: list[tuple[int, str]] = []

    def set_phase(self, label: str) -> None:
        with self._lock:
            self._phase = label

    def run(self) -> None:
        while not self._stop.is_set():
            used = _query_used_mib()
            if used is not None:
                with self._lock:
                    phase = self._phase
                self.samples.append((used, phase))
            time.sleep(self._interval)

    def stop(self) -> None:
        self._stop.set()

    def peak(self, phase: str) -> int:
        vals = [u for u, p in self.samples if p == phase]
        return max(vals) if vals else 0


def make_slice(path: Path) -> None:
    sr = 44100
    n = int(SLICE_SECONDS * sr)
    t = np.linspace(0, SLICE_SECONDS, n, endpoint=False)
    rng = np.random.default_rng(0)
    sig = sum(np.sin(2 * np.pi * f * t) / 4 for f in (110, 220, 440, 660))
    sig = sig + 0.1 * rng.standard_normal(n)
    sig = (sig / np.max(np.abs(sig)) * 0.7).astype(np.float32)
    sf.write(str(path), np.stack([sig, sig], axis=1), sr)


def banner(msg: str) -> None:
    print(f"\n{'=' * 64}\n{msg}\n{'=' * 64}", flush=True)


# --------------------------------------------------------------------------
# Separator-load subprocess: pure drop+reload, no demix
# --------------------------------------------------------------------------
def _sep_loader_main(conn, model_dir: str, model_name: str) -> None:
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    import gc

    import torch
    from audio_separator.separator import Separator

    sep = Separator(model_file_dir=model_dir, output_format="wav", log_level=logging.WARNING)
    sep.load_model(model_filename=model_name)
    torch.cuda.empty_cache()
    conn.send(("ready",))

    while True:
        cmd = conn.recv()
        if cmd is None:
            break
        if cmd[0] == "reload":
            times = []
            for _ in range(cmd[1]):
                s = time.monotonic()
                sep.model_instance = None  # StemWorker._swap_model, verbatim
                gc.collect()
                torch.cuda.empty_cache()
                sep.load_model(model_filename=model_name)
                torch.cuda.empty_cache()
                times.append(time.monotonic() - s)
            conn.send(("done", times))


class SepLoader:
    def __init__(self, model_dir: str, model_name: str) -> None:
        self._parent, child = WORKER_CONTEXT.Pipe()
        self._proc = WORKER_CONTEXT.Process(
            target=_sep_loader_main, args=(child, model_dir, model_name), daemon=True
        )

    def start(self) -> None:
        self._proc.start()
        assert self._parent.recv() == ("ready",)

    def reload(self, n: int) -> list[float]:
        self._parent.send(("reload", n))
        tag, times = self._parent.recv()
        assert tag == "done"
        return times

    def stop(self) -> None:
        try:
            self._parent.send(None)
            self._proc.join(timeout=10)
        except OSError:
            pass
        if self._proc.is_alive():
            self._proc.kill()


def summarize(times: list[float]) -> str:
    return f"median {statistics.median(times):.1f}s  all={[f'{x:.1f}' for x in times]}"


def main() -> None:
    sep_model = sys.argv[1] if len(sys.argv) > 1 else PROXY
    tmp = Path(get_temp_directory()) / "probe_load_during_inference"
    tmp.mkdir(parents=True, exist_ok=True)
    slice_wav = tmp / "slice.wav"
    make_slice(slice_wav)

    sampler = VramSampler()
    sampler.set_phase("desktop")
    sampler.start()
    time.sleep(2.0)
    desktop = sampler.peak("desktop")
    print(f"Desktop baseline: {desktop} MiB", flush=True)

    wcfg = WhisperModelConfig()
    for sect in (wcfg.align, wcfg.transcribe):
        sect.vad = False
        sect.only_voice_freq = False
        sect.suppress_silence = False
    wcfg.align.nonspeech_skip = None

    banner(f"Loading: SepLoader={sep_model}, WhisperWorker=large-v3-turbo")
    sampler.set_phase("loading")
    sep = SepLoader(MODELS_DIR, sep_model)
    whisper = WhisperWorker(config=wcfg)
    sep.start()
    whisper.start()
    sampler.set_phase("resident")
    time.sleep(2.0)
    print(f"Co-residency peak: {sampler.peak('resident')} MiB", flush=True)

    def infer(n: int) -> list[float]:
        times = []
        for _ in range(n):
            s = time.monotonic()
            chk = whisper.align_check(vocal_path=slice_wav, lyrics_text=LYRICS)
            whisper.refine_from_cached(result_id=chk["result_id"], vocal_path=slice_wav)
            times.append(time.monotonic() - s)
        return times

    # --- LOAD_ONLY ---
    banner(f"LOAD_ONLY: {N_LOAD} roformer reloads (whisper idle)")
    sampler.set_phase("load_only")
    load_solo = sep.reload(N_LOAD)
    print(f"load: {summarize(load_solo)}", flush=True)

    time.sleep(1.0)

    # --- INFER_ONLY ---
    banner(f"INFER_ONLY: {N_INFER} align+refine (separator idle)")
    sampler.set_phase("infer_only")
    infer_solo = infer(N_INFER)
    print(f"infer: {summarize(infer_solo)}", flush=True)

    time.sleep(1.0)

    # --- CONCURRENT ---
    banner(f"CONCURRENT: {N_LOAD} reloads || {N_INFER} align+refine")
    sampler.set_phase("concurrent")
    box: dict = {}
    barrier = threading.Barrier(2)

    def load_thread() -> None:
        barrier.wait()
        try:
            box["load"] = sep.reload(N_LOAD)
        except Exception as exc:
            box["load_err"] = repr(exc)

    def infer_thread() -> None:
        barrier.wait()
        try:
            box["infer"] = infer(N_INFER)
        except Exception as exc:
            box["infer_err"] = repr(exc)

    th_l = threading.Thread(target=load_thread)
    th_i = threading.Thread(target=infer_thread)
    t = time.monotonic()
    th_l.start()
    th_i.start()
    th_l.join()
    th_i.join()
    concurrent_wall = time.monotonic() - t

    sampler.set_phase("done")
    time.sleep(0.5)
    sampler.stop()

    # --- Report ---
    banner("RESULTS")
    p_l = sampler.peak("load_only")
    p_i = sampler.peak("infer_only")
    p_c = sampler.peak("concurrent")
    print(f"VRAM peak LOAD_ONLY   : {p_l} MiB (delta {p_l - desktop})")
    print(f"VRAM peak INFER_ONLY  : {p_i} MiB (delta {p_i - desktop})")
    print(f"VRAM peak CONCURRENT  : {p_c} MiB (delta {p_c - desktop})")
    print(
        f"Production-equiv peak : {(p_c - desktop) + MPV_RESERVE_MIB} MiB "
        f"vs {PRODUCTION_CARD_MIB} card"
    )

    banner("CONTENTION: per-op time standalone vs concurrent")
    load_conc = box.get("load")
    infer_conc = box.get("infer")
    if load_conc:
        ls, lc = statistics.median(load_solo), statistics.median(load_conc)
        print(f"LOAD  median: standalone {ls:.1f}s -> concurrent {lc:.1f}s  ({lc / ls:.2f}x)")
        print(f"      {summarize(load_conc)}")
    if infer_conc:
        is_, ic = statistics.median(infer_solo), statistics.median(infer_conc)
        print(f"INFER median: standalone {is_:.1f}s -> concurrent {ic:.1f}s  ({ic / is_:.2f}x)")
        print(f"      {summarize(infer_conc)}")
    print(f"\nCONCURRENT wall: {concurrent_wall:.1f}s")
    if box.get("load_err") or box.get("infer_err"):
        print(f"!! errors: load={box.get('load_err')} infer={box.get('infer_err')}")

    sep.stop()
    whisper.stop()
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
