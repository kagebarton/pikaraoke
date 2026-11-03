"""Phase 1b-ii: what language does whisper say a vocal stem is, and can that route a song?

Loads the app's large-v3-turbo.pt and, on the vocal stem of each pilot song and of four English
control songs, cuts consecutive 30 s windows and runs whisper's language detection on each. Per
window it saves the stem RMS (dBFS), the top three languages with probabilities, p(zh), p(yue) and
the whole distribution. Per song it saves two guesses:
  stock      the first window only, as whisper's own ``transcribe`` decides when given no language
  aggregate  the language with the highest summed log-probability over the windows whose RMS is
             within LOUD_WITHIN_DB of the song's loudest window
On each Chinese song's confirmed sheet it also counts the characters of a fixed list of colloquial
Cantonese. That count is a raw number next to the guess, not a router and not part of any gate.

Saved under <PROBE_ROOT>/phase1b/: lang/<video_id>.json per song, lang_songs.txt (one row per
song) and lang_windows.txt (one row per window). Raw output only. Run with the app closed (one GPU
job at a time).

Run (PowerShell, from the repo root):
  $env:PYTHONUTF8 = "1"
  uv run python scripts/zh_probe/phase1b_lang.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))

from arms import DEVICE, SAMPLE_RATE  # noqa: E402
from corpus import (  # noqa: E402
    CONFIRMED_DIR,
    PILOT,
    PROBE_ROOT,
    WHISPER_PATH,
    han_chars,
)
from phase0c_gpu import rms_db  # noqa: E402
from phase1_run import load_stem  # noqa: E402

OUT_DIR = PROBE_ROOT / "phase1b"
WINDOW_S = 30  # whisper's own window
LOUD_WITHIN_DB = 20
COLLOQUIAL = "嘅咗唔佢冇啲喺嚟嘢睇哋嗰噉㗎"
# Songs with a vocal/ stem in the library whose lyrics are English; the executor's choice, picked
# to differ in how the voice sounds: sparse ballad, fast rap, harmonised choir, rhythmic pop.
ENGLISH_CONTROLS = (
    ("hLQl3WQQoQ0", "Adele - Someone Like You"),
    ("xFYQQPAOz7Y", "Eminem - Lose Yourself"),
    ("fJ9rUzIMcZQ", "Queen - Bohemian Rhapsody"),
    ("JGwWNGJdvx8", "Ed Sheeran - Shape of You"),
)
SONGS = [(s.video_id, s.lang, f"#{s.num} {s.title}") for s in PILOT] + [
    (video_id, "en", title) for video_id, title in ENGLISH_CONTROLS
]
P_FLOOR = 1e-30  # a probability that underflowed to zero must not break the log


def detect_windows(model, audio: np.ndarray) -> list[dict]:
    """Language detection on each consecutive 30 s window of the stem, as ``transcribe`` does it.

    The log-mel is computed once over the whole stem and sliced, the way ``transcribe`` slices
    its segments, so the first window is exactly the one whisper would look at.
    """
    from whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim

    mel = log_mel_spectrogram(audio, model.dims.n_mels, padding=N_SAMPLES)
    dtype = torch.float16 if DEVICE == "cuda" else torch.float32
    windows = []
    for k in range(math.ceil(len(audio) / N_SAMPLES)):
        chunk = audio[k * N_SAMPLES : (k + 1) * N_SAMPLES]
        segment = pad_or_trim(mel[:, k * N_FRAMES : (k + 1) * N_FRAMES], N_FRAMES)
        _, probs = model.detect_language(segment.to(model.device).to(dtype))
        probs = {lang: float(p) for lang, p in probs.items()}
        top3 = sorted(probs.items(), key=lambda kv: -kv[1])[:3]
        windows.append(
            {
                "index": k,
                "start_s": k * WINDOW_S,
                "len_s": round(len(chunk) / SAMPLE_RATE, 2),
                "rms_dbfs": round(rms_db(chunk), 2),
                "top3": [[lang, round(p, 4)] for lang, p in top3],
                "p_zh": round(probs.get("zh", 0.0), 4),
                "p_yue": round(probs.get("yue", 0.0), 4),
                "probs": probs,
            }
        )
    return windows


def stock_guess(windows: list[dict]) -> dict:
    lang, p = windows[0]["top3"][0]
    return {"language": lang, "p": p}


def aggregate_guess(windows: list[dict]) -> dict:
    """Highest summed log-probability over the windows near the song's loudest; marks them counted."""
    loudest = max(w["rms_dbfs"] for w in windows)
    for w in windows:
        w["counted"] = w["rms_dbfs"] >= loudest - LOUD_WITHIN_DB
    counted = [w for w in windows if w["counted"]]
    sums = {
        lang: sum(math.log(max(w["probs"][lang], P_FLOOR)) for w in counted)
        for lang in counted[0]["probs"]
    }
    top3 = sorted(sums.items(), key=lambda kv: -kv[1])[:3]
    return {
        "language": top3[0][0],
        "windows": len(windows),
        "windows_counted": len(counted),
        "loudest_rms_dbfs": loudest,
        "top3_log_prob_sums": [[lang, round(s, 3)] for lang, s in top3],
    }


def colloquial_count(video_id: str) -> dict:
    text = (CONFIRMED_DIR / f"{video_id}.txt").read_text(encoding="utf-8")
    by_char = {c: text.count(c) for c in COLLOQUIAL if c in text}
    return {"total": sum(by_char.values()), "by_char": by_char, "han_chars": len(han_chars(text))}


def write_tables(records: list[dict]) -> None:
    """The two TSV tables, built from the same records as the JSON files."""

    def tsv(header: list[str], rows: list[list]) -> str:
        return "\n".join("\t".join(str(c) for c in r) for r in [header, *rows]) + "\n"

    songs, windows = [], []
    for rec in records:
        agg, stock, colloquial = rec["aggregate"], rec["stock"], rec["colloquial"]
        songs.append(
            [
                rec["title"], rec["label"], rec["audio_s"], agg["windows"], agg["windows_counted"],
                agg["loudest_rms_dbfs"], stock["language"], stock["p"], agg["language"],
                "; ".join(f"{lang} {s}" for lang, s in agg["top3_log_prob_sums"]),
                "" if colloquial is None else colloquial["total"],
            ]
        )  # fmt: skip
        for w in rec["windows"]:
            top = [f"{lang} {p}" for lang, p in w["top3"]]
            windows.append(
                [rec["title"], w["index"], w["start_s"], w["len_s"], w["rms_dbfs"], w["counted"],
                 *top, w["p_zh"], w["p_yue"]]
            )  # fmt: skip
    (OUT_DIR / "lang_songs.txt").write_text(
        tsv(
            ["song", "label", "audio_s", "windows", "counted", "loudest_rms_dbfs", "stock",
             "stock_p", "aggregate", "aggregate_top3_log_prob_sums", "colloquial_chars"],
            songs,
        ),
        encoding="utf-8",
    )  # fmt: skip
    (OUT_DIR / "lang_windows.txt").write_text(
        tsv(
            ["song", "window", "start_s", "len_s", "rms_dbfs", "counted", "top1", "top2", "top3",
             "p_zh", "p_yue"],
            windows,
        ),
        encoding="utf-8",
    )  # fmt: skip


def main() -> None:
    import stable_whisper

    (OUT_DIR / "lang").mkdir(parents=True, exist_ok=True)
    device = torch.cuda.get_device_name(0) if DEVICE == "cuda" else "cpu"
    print(f"device {device}, torch {torch.__version__}", flush=True)
    model = stable_whisper.load_model(str(WHISPER_PATH), device=DEVICE)

    records = []
    for video_id, label, title in SONGS:
        audio = load_stem(video_id)
        t0 = time.perf_counter()
        windows = detect_windows(model, audio)
        record = {
            "video_id": video_id,
            "label": label,
            "title": title,
            "model": WHISPER_PATH.name,
            "device": device,
            "audio_s": round(len(audio) / SAMPLE_RATE, 1),
            "wall_s": round(time.perf_counter() - t0, 1),
            "stock": stock_guess(windows),
            "aggregate": aggregate_guess(windows),
            "colloquial": None if label == "en" else colloquial_count(video_id),
            "windows": windows,
        }
        records.append(record)
        (OUT_DIR / "lang" / f"{video_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        agg = record["aggregate"]
        print(
            f"{title} [{label}]: stock {record['stock']['language']} "
            f"({record['stock']['p']}), aggregate {agg['language']} over "
            f"{agg['windows_counted']}/{agg['windows']} windows, {record['wall_s']} s",
            flush=True,
        )
    write_tables(records)
    print(f"wrote lang/*.json, lang_songs.txt and lang_windows.txt in {OUT_DIR}")


if __name__ == "__main__":
    main()
