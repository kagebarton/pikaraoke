"""One-off probe: how much of the joint matcher's align+refine pass is
refine, and how much does the refine `steps` knob save?

The joint route runs align_check (model.align) then refine_from_cached
(model.refine(steps="se", word_level=True)) per song, plus once per suspect
span in windowed re-align. Refine re-runs the encoder once per step char
("se" = starts then ends), so it's the long pole. This splits the two and
compares steps variants.

Run for each variant:
  .venv/Scripts/python.exe scripts/probe_refine_cost.py se
  .venv/Scripts/python.exe scripts/probe_refine_cost.py s
  .venv/Scripts/python.exe scripts/probe_refine_cost.py e

Times align_check (= align) and refine_from_cached (= refine) separately.
Synthetic 20 s slice with VAD off (align force-aligns the text); refine does
real per-word encoder passes, so the align/refine split is representative for
a ~60-word span. Confirm absolute numbers on a real song via the eval harness.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from pikaraoke.lib.get_platform import get_temp_directory
from pikaraoke.pipeline.config import WhisperModelConfig
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker

SLICE_SECONDS = 20.0
N = 4

LYRICS = """When the lights go down and the music starts to play
I can hear your voice calling out my name
Every single moment feels so far away
But I know that nothing will ever be the same
Hold me close and never let me go
Through the rain and all the tears we know"""


def make_slice(path: Path) -> None:
    sr = 44100
    n = int(SLICE_SECONDS * sr)
    t = np.linspace(0, SLICE_SECONDS, n, endpoint=False)
    rng = np.random.default_rng(0)
    sig = sum(np.sin(2 * np.pi * f * t) / 4 for f in (110, 220, 440, 660))
    sig = sig + 0.1 * rng.standard_normal(n)
    sig = (sig / np.max(np.abs(sig)) * 0.7).astype(np.float32)
    sf.write(str(path), np.stack([sig, sig], axis=1), sr)


def med(xs: list[float]) -> float:
    return statistics.median(xs)


def main() -> None:
    steps = sys.argv[1] if len(sys.argv) > 1 else "se"
    real_wav = sys.argv[2] if len(sys.argv) > 2 else None
    real_lyrics = sys.argv[3] if len(sys.argv) > 3 else None
    tmp = Path(get_temp_directory()) / "probe_refine_cost"
    tmp.mkdir(parents=True, exist_ok=True)

    wcfg = WhisperModelConfig()
    if real_wav:
        # Real full-song vocal stem + lyrics: production config (VAD on —
        # clean vocals, so VAD gates correctly). N small (a full song is slow).
        vocal = Path(real_wav)
        lyrics_text = Path(real_lyrics).read_text(encoding="utf-8")
        n_iter = 2
        print(f"=== REAL SONG steps='{steps}'  {vocal.name} ===", flush=True)
        print(
            f"    lines={len(lyrics_text.splitlines())} words={len(lyrics_text.split())}",
            flush=True,
        )
    else:
        # Synthetic slice: VAD off (tones don't pass VAD).
        vocal = tmp / "slice.wav"
        make_slice(vocal)
        lyrics_text = LYRICS
        for sect in (wcfg.align, wcfg.transcribe):
            sect.vad = False
            sect.only_voice_freq = False
            sect.suppress_silence = False
        wcfg.align.nonspeech_skip = None
        n_iter = N
        print(f"=== SYNTHETIC steps='{steps}' ===", flush=True)
    wcfg.refine.steps = steps

    whisper = WhisperWorker(config=wcfg)
    whisper.start()

    align_t: list[float] = []
    refine_t: list[float] = []
    for i in range(n_iter + 1):  # +1 warmup
        s = time.monotonic()
        chk = whisper.align_check(vocal_path=vocal, lyrics_text=lyrics_text)
        a = time.monotonic() - s
        s = time.monotonic()
        whisper.refine_from_cached(result_id=chk["result_id"], vocal_path=vocal)
        r = time.monotonic() - s
        if i == 0:
            print(f"  warmup: align {a:.1f}s refine {r:.1f}s", flush=True)
            continue
        align_t.append(a)
        refine_t.append(r)
        print(f"  iter {i}: align {a:.1f}s  refine {r:.1f}s", flush=True)

    ma, mr = med(align_t), med(refine_t)
    print(
        f"\nMEDIAN  align {ma:.1f}s  refine {mr:.1f}s  total {ma + mr:.1f}s  "
        f"refine share {100 * mr / (ma + mr):.0f}%",
        flush=True,
    )
    whisper.stop()


if __name__ == "__main__":
    main()
