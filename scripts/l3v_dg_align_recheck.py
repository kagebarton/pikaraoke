#!/usr/bin/env python3
"""Judge probe (Phase 1 review, large-v3 study): re-run the align leg on
Defying Gravity.

Phase 1's regen produced a 470->3 align-word collapse on this one song
(``n_align_word_drops`` 0->466). Before interpreting it, test whether the
collapse is deterministic or a transient: run ``align_refine`` twice under
the same large-v3 fp16 config in one fresh worker -- run 1 reproduces the
regen's condition for this song (fresh worker, first job), run 2 checks
within-session run-to-run determinism. Compares both runs against the
Phase 1 variant bundle's stored align words.

Read-only against the study copy; writes a witness JSON to the study
records dir; no bundle is touched.

Run from the repo root::

    python scripts/l3v_dg_align_recheck.py [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.l3v_phase1_regen import _GpuPeakMonitor  # noqa: E402

STUDY_FOLDER = Path("/home/ken/pikaraoke-study-l3v/songs")
SONG_STEM = "'Defying Gravity' - Wicked 20th Anniversary Edition _ WICKED the Musical---AoON1CyhQAM"
LARGE_V3_MODEL_PATH = str(Path(__file__).resolve().parents[1] / "models" / "large-v3.pt")
DEFAULT_OUT = Path("/home/ken/pikaraoke-study-l3v/records/phase1/dg_align_recheck.json")


def _summarize(label: str, words: list[dict]) -> None:
    print(f"  [{label}] n_words={len(words)}")
    for w in words[:5]:
        print(f"    {w}")
    if len(words) > 5:
        print(f"    ... ({len(words) - 5} more)")


def main() -> int:
    from pikaraoke.pipeline.config import PipelineConfig
    from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    vocal_path = STUDY_FOLDER / "vocal" / f"{SONG_STEM}---vocal.m4a"
    bundle_path = STUDY_FOLDER / "alignment_debug" / f"{SONG_STEM}.json"
    with open(bundle_path) as f:
        bundle = json.load(f)
    lyrics_text = "\n".join(bundle["lyrics"]["align_lines"])
    bundle_words = bundle["words"]

    print(f"Song: {SONG_STEM}")
    print(f"Vocal: {vocal_path}")
    print(f"Lyrics: {len(lyrics_text.splitlines())} lines, {len(lyrics_text.split())} tokens")
    print(f"Phase 1 variant bundle: {len(bundle_words)} align words\n")

    config = PipelineConfig()
    config.whisper.load_model.model_path = LARGE_V3_MODEL_PATH
    config.whisper.load_model.fp16_weights = True
    worker = WhisperWorker(config.whisper)

    runs: list[list[dict]] = []
    monitor = _GpuPeakMonitor()
    with monitor:
        worker.start()
        try:
            for i in (1, 2):
                start = time.time()
                words = worker.align_refine(vocal_path, lyrics_text)
                print(f"run {i}: {len(words)} words in {time.time() - start:.1f}s")
                runs.append(words)
        finally:
            worker.stop()

    print(f"peak VRAM: {monitor.peak_mib} MiB\n")
    _summarize("run 1", runs[0])
    _summarize("run 2", runs[1])
    _summarize("phase 1 bundle", bundle_words)

    run1_eq_run2 = runs[0] == runs[1]
    run1_eq_bundle = runs[0] == bundle_words
    print(f"\nrun1 == run2 (exact): {run1_eq_run2}")
    print(f"run1 == phase-1 bundle (exact): {run1_eq_bundle}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "song_stem": SONG_STEM,
                "peak_vram_mib": monitor.peak_mib,
                "n_words_bundle": len(bundle_words),
                "n_words_run1": len(runs[0]),
                "n_words_run2": len(runs[1]),
                "run1_eq_run2": run1_eq_run2,
                "run1_eq_bundle": run1_eq_bundle,
                "run1_words": runs[0],
                "run2_words": runs[1],
            },
            indent=2,
        )
    )
    print(f"Witness written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
