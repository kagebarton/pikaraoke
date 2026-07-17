#!/usr/bin/env python3
"""Phase 0 GATE S0 evidence: fp16-weight load hook correctness check.

Validates ``_load_whisper_model``'s ``fp16_weights`` branch
(``pikaraoke/pipeline/workers/whisper_worker.py``) before the
large-v3-evidence-study burns GPU time on the real 8-song regen. Two
checks, run in order:

1. **Identity check** — turbo-fp32 vs turbo-fp16 (same checkpoint,
   halved via the hook) on one song's align + transcribe legs. Pass =
   identical word sequences on both legs, and word timing deltas
   <= 0.02s for >= 99% of words. Only proceeds to (2) if this passes —
   no point burning large-v3 GPU time on an unvalidated hook.
2. **large-v3 fp16 smoke** — load + one align pass on large-v3 fp16, on
   the same song. Confirms no OOM and records peak VRAM + wall-clock.

GPU memory is polled externally via ``nvidia-smi`` (a background thread
in this parent process) because the model actually loads inside the
whisper worker's spawned subprocess. Run with the GPU otherwise idle.

Run from the repo root::

    python scripts/fp16_identity_check.py [--songs-dir PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.pipeline.config import LoadModelKwargs, WhisperModelConfig  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402

SONG_STEM = "Seasons of Love (HD)---UvyHuse6buY"
DEFAULT_SONGS_DIR = Path("/home/ken/pikaraoke-songs")
LARGE_V3_MODEL_PATH = str(Path(__file__).resolve().parents[1] / "models" / "large-v3.pt")
TIMING_TOLERANCE_S = 0.02
TIMING_PASS_FRACTION = 0.99


class _GpuPeakMonitor:
    """Polls system-wide GPU memory via nvidia-smi while active, tracks the max.

    Runs in the parent process; the model actually loads in the whisper
    worker's spawned subprocess, so in-process torch memory stats can't see
    it. nvidia-smi reports system-wide usage, which does.
    """

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


def _current_gpu_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return int(out.stdout.strip().splitlines()[0])
    except (subprocess.SubprocessError, ValueError, IndexError, OSError):
        return None


def _load_lyrics_text(songs_dir: Path, stem: str) -> str:
    bundle_path = songs_dir / "alignment_debug" / f"{stem}.json"
    with open(bundle_path) as f:
        bundle = json.load(f)
    return "\n".join(bundle["lyrics"]["align_lines"])


def _run_pass(
    model_path: str,
    fp16_weights: bool,
    vocal_path: Path,
    lyrics_text: str,
    *,
    include_transcribe: bool = True,
) -> dict:
    """Load a model via WhisperWorker and run align (+ optionally transcribe).

    Mirrors the production call shape in ``LyricAlignStage`` (``align_refine``
    then ``transcribe_words(refine=False)``) so the identity check exercises
    the real worker subprocess path, not a hand-rolled shortcut.
    """
    idle_mib = _current_gpu_mib()
    config = WhisperModelConfig(
        load_model=LoadModelKwargs(model_path=model_path, fp16_weights=fp16_weights)
    )
    worker = WhisperWorker(config=config)
    monitor = _GpuPeakMonitor()
    start = time.time()
    with monitor:
        worker.start()
        load_elapsed = time.time() - start
        try:
            align_words = worker.align_refine(vocal_path, lyrics_text)
            transcribe_words = (
                worker.transcribe_words(vocal_path, refine=False) if include_transcribe else None
            )
        finally:
            worker.stop()
    total_elapsed = time.time() - start
    return {
        "model_path": model_path,
        "fp16_weights": fp16_weights,
        "pre_pass_idle_mib": idle_mib,
        "peak_vram_mib": monitor.peak_mib,
        "load_elapsed_s": round(load_elapsed, 2),
        "total_elapsed_s": round(total_elapsed, 2),
        "align_words": align_words,
        "transcribe_words": transcribe_words,
    }


def _compare(label: str, a: list[dict], b: list[dict]) -> dict:
    seq_a = [w["word"] for w in a]
    seq_b = [w["word"] for w in b]
    sequences_match = seq_a == seq_b

    deltas = []
    if sequences_match:
        for wa, wb in zip(a, b):
            deltas.append(abs(wa["start"] - wb["start"]))
            deltas.append(abs(wa["end"] - wb["end"]))
    within_tol = sum(1 for d in deltas if d <= TIMING_TOLERANCE_S)
    pct_within_tol = (within_tol / len(deltas) * 100) if deltas else None

    diff_lines = None
    if not sequences_match:
        diff_lines = list(
            difflib.unified_diff(seq_a, seq_b, fromfile="fp32", tofile="fp16", lineterm="")
        )

    passed = (
        sequences_match
        and pct_within_tol is not None
        and pct_within_tol >= TIMING_PASS_FRACTION * 100
    )

    return {
        "label": label,
        "sequences_match": sequences_match,
        "n_words_fp32": len(a),
        "n_words_fp16": len(b),
        "max_delta_s": max(deltas) if deltas else None,
        "pct_within_tol": pct_within_tol,
        "passed": passed,
        "diff": diff_lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--songs-dir", type=Path, default=DEFAULT_SONGS_DIR)
    parser.add_argument("--out", type=Path, default=None, help="Write full JSON results here")
    parser.add_argument(
        "--skip-large-v3", action="store_true", help="Stop after the identity check (steps 3 only)"
    )
    args = parser.parse_args()

    vocal_path = args.songs_dir / "vocal" / f"{SONG_STEM}---vocal.m4a"
    if not vocal_path.exists():
        print(f"ABORT: vocal stem not found: {vocal_path}")
        return 1

    lyrics_text = _load_lyrics_text(args.songs_dir, SONG_STEM)
    turbo_model_path = LoadModelKwargs().model_path

    idle_mib = _current_gpu_mib()
    print(f"Song: {SONG_STEM}")
    print(f"Turbo model: {turbo_model_path}")
    print(f"Vocal: {vocal_path}")
    print(f"Lyrics: {len(lyrics_text.splitlines())} lines")
    print(f"GPU idle before start: {idle_mib} MiB\n")

    print("=== Step 3: identity check (turbo fp32 vs turbo fp16) ===")
    print("-- fp32 pass --")
    fp32 = _run_pass(turbo_model_path, False, vocal_path, lyrics_text)
    print(
        f"   loaded in {fp32['load_elapsed_s']}s, peak={fp32['peak_vram_mib']} MiB, "
        f"align_words={len(fp32['align_words'])}, transcribe_words={len(fp32['transcribe_words'])}"
    )

    print("-- fp16 pass --")
    fp16 = _run_pass(turbo_model_path, True, vocal_path, lyrics_text)
    print(
        f"   loaded in {fp16['load_elapsed_s']}s, peak={fp16['peak_vram_mib']} MiB, "
        f"align_words={len(fp16['align_words'])}, transcribe_words={len(fp16['transcribe_words'])}"
    )

    align_cmp = _compare("align", fp32["align_words"], fp16["align_words"])
    transcribe_cmp = _compare("transcribe", fp32["transcribe_words"], fp16["transcribe_words"])

    print("\n-- identity results --")
    for cmp in (align_cmp, transcribe_cmp):
        print(
            f"   [{cmp['label']}] sequences_match={cmp['sequences_match']} "
            f"n_words fp32={cmp['n_words_fp32']} fp16={cmp['n_words_fp16']} "
            f"max_delta_s={cmp['max_delta_s']} pct_within_{TIMING_TOLERANCE_S}s="
            f"{cmp['pct_within_tol']} passed={cmp['passed']}"
        )
        if cmp["diff"]:
            print(f"   [{cmp['label']}] DIVERGENT WORD SEQUENCE (unified diff, fp32 -> fp16):")
            for line in cmp["diff"]:
                print(f"     {line}")

    vram_saved_mib = fp32["peak_vram_mib"] - fp16["peak_vram_mib"]
    print(
        f"\nVRAM: fp32 peak={fp32['peak_vram_mib']} MiB, fp16 peak={fp16['peak_vram_mib']} MiB, saved={vram_saved_mib} MiB"
    )

    identity_passed = align_cmp["passed"] and transcribe_cmp["passed"]
    print(f"\nStep 3 verdict: {'PASS' if identity_passed else 'FAIL'}")

    results = {
        "song_stem": SONG_STEM,
        "fp32": {k: v for k, v in fp32.items() if k not in ("align_words", "transcribe_words")},
        "fp16": {k: v for k, v in fp16.items() if k not in ("align_words", "transcribe_words")},
        "align_words_fp32": fp32["align_words"],
        "align_words_fp16": fp16["align_words"],
        "transcribe_words_fp32": fp32["transcribe_words"],
        "transcribe_words_fp16": fp16["transcribe_words"],
        "align_cmp": align_cmp,
        "transcribe_cmp": transcribe_cmp,
        "vram_saved_mib": vram_saved_mib,
        "identity_step_passed": identity_passed,
        "large_v3_smoke": None,
    }

    if not identity_passed:
        print("\nABORT before large-v3: identity check failed, per gate discipline.")
        if args.out:
            args.out.write_text(json.dumps(results, indent=2))
            print(f"Results written to {args.out}")
        return 1

    if args.skip_large_v3:
        print("\n--skip-large-v3 set: stopping after step 3.")
        if args.out:
            args.out.write_text(json.dumps(results, indent=2))
            print(f"Results written to {args.out}")
        return 0

    print("\n=== Step 4: large-v3 fp16 smoke (load + one align pass) ===")
    large_v3 = _run_pass(
        LARGE_V3_MODEL_PATH, True, vocal_path, lyrics_text, include_transcribe=False
    )
    print(
        f"   loaded in {large_v3['load_elapsed_s']}s, total={large_v3['total_elapsed_s']}s, "
        f"peak={large_v3['peak_vram_mib']} MiB, align_words={len(large_v3['align_words'])}"
    )
    print("Step 4 verdict: PASS (no OOM)")
    results["large_v3_smoke"] = {k: v for k, v in large_v3.items() if k != "align_words"} | {
        "n_align_words": len(large_v3["align_words"])
    }

    if args.out:
        args.out.write_text(json.dumps(results, indent=2))
        print(f"\nResults written to {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
