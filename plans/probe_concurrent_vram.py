"""One-off probe: can the de-reverb roformer and whisper inference run
concurrently within the 6 GB VRAM budget, and does the overlap actually
save wall-clock?

Answers the open question on optimization #3 of the per-span de-reverb plan
(plans/matcher-timing-eval.md). Drives the *real* StemWorker (loaded directly
with the anvuew de-reverb model) and WhisperWorker, so the model-load and
inference paths match production exactly.

Three phases, each K iterations on the same ~20 s slice:
  S_ONLY      - de-reverb demix only (whisper idle)
  W_ONLY      - align_check + refine_from_cached only (stem idle)  [the long pole]
  CONCURRENT  - both at once, in parallel parent threads

Device VRAM is sampled (~10 Hz) via nvidia-smi throughout. Because this host
is a shared desktop, the desktop baseline (D) is subtracted to isolate the
workload footprint; the production-equivalent peak is reported as
(workload delta + mpv ~300 MiB) against the 6144 MiB card.

Run:  .venv/Scripts/python.exe plans/probe_concurrent_vram.py
"""

from __future__ import annotations

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
from pikaraoke.pipeline.workers.stem_worker import StemWorker
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

ANVUEW = "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt"
MODELS_DIR = str(Path(__file__).resolve().parents[1] / "models")
SLICE_SECONDS = 20.0
K = 3  # iterations per phase
PRODUCTION_CARD_MIB = 6144
MPV_RESERVE_MIB = 300

LYRICS = """When the lights go down and the music starts to play
I can hear your voice calling out my name
Every single moment feels so far away
But I know that nothing will ever be the same
Hold me close and never let me go
Through the rain and all the tears we know
We were dancing in the fading glow
This is everything I wanted you to know"""


# --------------------------------------------------------------------------
# VRAM sampler
# --------------------------------------------------------------------------
class VramSampler(threading.Thread):
    def __init__(self, interval: float = 0.1) -> None:
        super().__init__(daemon=True)
        self._interval = interval
        self._stop = threading.Event()
        self._phase = "init"
        self._lock = threading.Lock()
        self.samples: list[tuple[float, int, str]] = []

    def set_phase(self, label: str) -> None:
        with self._lock:
            self._phase = label

    def run(self) -> None:
        while not self._stop.is_set():
            used = _query_used_mib()
            if used is not None:
                with self._lock:
                    phase = self._phase
                self.samples.append((time.monotonic(), used, phase))
            time.sleep(self._interval)

    def stop(self) -> None:
        self._stop.set()

    def peak(self, phase: str) -> int:
        vals = [u for _, u, p in self.samples if p == phase]
        return max(vals) if vals else 0

    def median(self, phase: str) -> float:
        vals = [u for _, u, p in self.samples if p == phase]
        return statistics.median(vals) if vals else 0.0


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


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------
def make_slice(path: Path) -> None:
    """A non-trivial stereo 44.1 kHz slice: stacked tones + noise so neither
    model degenerates on silence. Content is irrelevant to VRAM (chunk-shaped)
    and to align timing (text is forced)."""
    sr = 44100
    n = int(SLICE_SECONDS * sr)
    t = np.linspace(0, SLICE_SECONDS, n, endpoint=False)
    rng = np.random.default_rng(0)
    sig = 0.0
    for f in (110, 220, 440, 660):
        sig = sig + np.sin(2 * np.pi * f * t) / 4
    sig = sig + 0.1 * rng.standard_normal(n)
    sig = (sig / np.max(np.abs(sig)) * 0.7).astype(np.float32)
    stereo = np.stack([sig, sig], axis=1)
    sf.write(str(path), stereo, sr)


def banner(msg: str) -> None:
    print(f"\n{'=' * 64}\n{msg}\n{'=' * 64}", flush=True)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    sep_model = sys.argv[1] if len(sys.argv) > 1 else ANVUEW
    is_proxy = sep_model != ANVUEW
    print(
        f"Separator model: {sep_model}"
        + ("  [PROXY for anvuew - same MelBand Roformer arch]" if is_proxy else "  [production de-reverb model]"),
        flush=True,
    )

    tmp = Path(get_temp_directory()) / "probe_concurrent_vram"
    tmp.mkdir(parents=True, exist_ok=True)
    slice_wav = tmp / "slice.wav"
    make_slice(slice_wav)

    sampler = VramSampler()
    sampler.set_phase("desktop")
    sampler.start()
    time.sleep(2.0)  # desktop baseline (no models loaded yet)
    desktop = sampler.median("desktop")
    print(f"Desktop baseline (no models): {desktop:.0f} MiB used", flush=True)

    banner("Loading models (StemWorker=anvuew, WhisperWorker=large-v3-turbo)")
    sampler.set_phase("loading")
    # VAD/voice-freq gating strips the synthetic probe audio to nothing
    # (align() returns None). Disable it so align force-aligns the text over
    # the full slice — heavier than production (no voiced-region gating), so
    # the align/refine timing here is a conservative upper bound. The encoder
    # + decoder GPU work and VRAM footprint (the things we measure) are
    # unchanged; only the cheap Silero pre-pass is dropped.
    wcfg = WhisperModelConfig()
    for sect in (wcfg.align, wcfg.transcribe):
        sect.vad = False
        sect.only_voice_freq = False
        sect.suppress_silence = False
    wcfg.align.nonspeech_skip = None

    stem = StemWorker(temp_dir=str(tmp), model_dir=MODELS_DIR, model_name=sep_model)
    whisper = WhisperWorker(config=wcfg)
    t0 = time.monotonic()
    stem.start()
    whisper.start()
    print(f"Both workers ready in {time.monotonic() - t0:.1f}s", flush=True)

    sampler.set_phase("resident")
    time.sleep(2.0)  # both models resident, idle
    resident = sampler.peak("resident")
    print(
        f"Co-residency peak: {resident} MiB  (workload {resident - desktop:.0f} MiB "
        f"= both model weights + 2 CUDA contexts)",
        flush=True,
    )

    results: dict[str, dict] = {}

    def run_demix() -> list[float]:
        times = []
        for _ in range(K):
            s = time.monotonic()
            stem.separate(wav_path=slice_wav, output_dir=tmp)
            times.append(time.monotonic() - s)
        return times

    def run_refine() -> list[float]:
        times = []
        for _ in range(K):
            s = time.monotonic()
            chk = whisper.align_check(vocal_path=slice_wav, lyrics_text=LYRICS)
            whisper.refine_from_cached(result_id=chk["result_id"], vocal_path=slice_wav)
            times.append(time.monotonic() - s)
        return times

    # --- S_ONLY ---
    banner(f"Phase S_ONLY: {K}x de-reverb demix (whisper idle)")
    sampler.set_phase("s_only")
    t = time.monotonic()
    demix_times = run_demix()
    results["s_only"] = {"wall": time.monotonic() - t, "iters": demix_times}
    print(f"demix per-iter: {[f'{x:.1f}' for x in demix_times]} s", flush=True)

    time.sleep(1.0)

    # --- W_ONLY ---
    banner(f"Phase W_ONLY: {K}x align_check + refine (stem idle) [long pole]")
    sampler.set_phase("w_only")
    t = time.monotonic()
    refine_times = run_refine()
    results["w_only"] = {"wall": time.monotonic() - t, "iters": refine_times}
    print(f"align+refine per-iter: {[f'{x:.1f}' for x in refine_times]} s", flush=True)

    time.sleep(1.0)

    # --- CONCURRENT ---
    banner(f"Phase CONCURRENT: {K}x demix || {K}x align+refine (parallel)")
    sampler.set_phase("concurrent")
    box: dict[str, list[float] | str] = {}
    barrier = threading.Barrier(2)

    def demix_thread() -> None:
        barrier.wait()
        try:
            box["demix"] = run_demix()
        except Exception as exc:  # worker death / OOM
            box["demix_err"] = repr(exc)

    def refine_thread() -> None:
        barrier.wait()
        try:
            box["refine"] = run_refine()
        except Exception as exc:
            box["refine_err"] = repr(exc)

    th_d = threading.Thread(target=demix_thread)
    th_r = threading.Thread(target=refine_thread)
    t = time.monotonic()
    th_d.start()
    th_r.start()
    th_d.join()
    th_r.join()
    results["concurrent"] = {
        "wall": time.monotonic() - t,
        "demix": box.get("demix"),
        "refine": box.get("refine"),
        "demix_err": box.get("demix_err"),
        "refine_err": box.get("refine_err"),
    }

    sampler.set_phase("done")
    time.sleep(0.5)
    sampler.stop()

    # --- Report ---
    banner("RESULTS")
    p_s = sampler.peak("s_only")
    p_w = sampler.peak("w_only")
    p_c = sampler.peak("concurrent")
    print(f"Desktop baseline (D)          : {desktop:.0f} MiB")
    print(f"Co-residency (weights+ctx)    : {resident} MiB  (delta {resident - desktop:.0f})")
    print(f"Peak S_ONLY  (demix)          : {p_s} MiB  (delta {p_s - desktop:.0f})")
    print(f"Peak W_ONLY  (align+refine)   : {p_w} MiB  (delta {p_w - desktop:.0f})")
    print(f"Peak CONCURRENT               : {p_c} MiB  (delta {p_c - desktop:.0f})")
    prod_peak = (p_c - desktop) + MPV_RESERVE_MIB
    print(
        f"\nProduction-equivalent peak    : {prod_peak:.0f} MiB "
        f"(workload delta + mpv {MPV_RESERVE_MIB})"
    )
    print(
        f"  vs {PRODUCTION_CARD_MIB} MiB card           : "
        f"{'FITS' if prod_peak <= PRODUCTION_CARD_MIB else 'OOM'} "
        f"(headroom {PRODUCTION_CARD_MIB - prod_peak:.0f} MiB)"
    )

    banner("WALL-CLOCK (does overlap help?)")
    s_wall = results["s_only"]["wall"]
    w_wall = results["w_only"]["wall"]
    c_wall = results["concurrent"]["wall"]
    print(f"S_ONLY wall      : {s_wall:.1f} s")
    print(f"W_ONLY wall      : {w_wall:.1f} s  (long pole)")
    print(f"sequential sum   : {s_wall + w_wall:.1f} s")
    print(f"CONCURRENT wall  : {c_wall:.1f} s")
    saved = (s_wall + w_wall) - c_wall
    print(f"overlap saved    : {saved:.1f} s  ({100 * saved / (s_wall + w_wall):.0f}% of sequential)")
    print(
        f"vs long pole     : concurrent {c_wall:.1f}s vs W_ONLY {w_wall:.1f}s "
        f"-> demix {'HIDDEN behind refine' if c_wall <= w_wall * 1.15 else 'NOT fully hidden'}"
    )
    if results["concurrent"]["demix_err"] or results["concurrent"]["refine_err"]:
        print(f"\n!! worker error during concurrent phase:")
        print(f"   demix_err : {results['concurrent']['demix_err']}")
        print(f"   refine_err: {results['concurrent']['refine_err']}")

    stem.stop()
    whisper.stop()
    print("\nWorkers stopped. Done.", flush=True)


if __name__ == "__main__":
    main()
