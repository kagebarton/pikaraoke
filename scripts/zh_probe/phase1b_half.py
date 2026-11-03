"""Phase 1b-i: H and Hal at full and at half precision, next to the app's resident models.

Run it with PiKaraoke open on this machine (whisper and stem workers loaded, a song playing in
mpv, no song processing), so that the card holds what it holds in use. For each arm (H on the
Mandarin pilot songs, Hal on the Cantonese ones) and each precision (fp32 as in Phase 1, then fp16:
weights and inputs in half, emissions cast back to fp32 before log_softmax and forced_align) it
loads the model, aligns the songs and records wall time, the torch peaks and the device-wide peak
of used memory, which nvidia-smi reports for the whole card, polled through the load and through
each align. The device-wide figure from before the probe loads anything is recorded too.

Saved under <PROBE_ROOT>/phase1b/: half/<video_id>/<arm>.{json,ass} for fp16 runs only (the
fp32 artifacts exist from Phase 1), half_runs.json and half_runs.txt (the raw run table, one row
per song, arm and precision, failures included), and commands.txt (mpv, for Ken's overall call on
each fp16 .ass). An out-of-memory failure is recorded as such and not retried. Raw output only.

Run (PowerShell, from the repo root; PYTHONUTF8 keeps Chinese text out of cp1252 trouble):
  $env:PYTHONUTF8 = "1"
  uv run --with transformers --with huggingface_hub --with opencc-python-reimplemented `
    python scripts/zh_probe/phase1b_half.py [--arms H,Hal] [--songs 1,2,9,11]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))

from arms import DEVICE, free_memory, make_arm  # noqa: E402
from corpus import PILOT, PROBE_ROOT, find_in_library  # noqa: E402
from phase1_review import VIDEO_SUFFIXES  # noqa: E402
from phase1_run import load_stem, measure  # noqa: E402
from sheet import load_sheet  # noqa: E402
from track import track_record, write_ass, write_json  # noqa: E402

OUT_DIR = PROBE_ROOT / "phase1b"
ARMS = ("H", "Hal")
PRECISIONS = (("fp32", False), ("fp16", True))
SMI = [
    "nvidia-smi", "--id=0", "--query-gpu=memory.used,memory.total",
    "--format=csv,noheader,nounits",
]  # fmt: skip
COLUMNS = (
    "song", "arm", "precision", "status", "stage", "message",
    "device_before_load_mb", "device_total_mb",
    "load_s", "load_alloc_mb", "load_reserved_mb", "device_load_peak_mb", "device_after_load_mb",
    "align_s", "align_alloc_mb", "align_reserved_mb", "device_align_peak_mb", "device_samples",
    "frames", "nonfinite",
)  # fmt: skip


class DeviceMonitor:
    """Device-wide used memory (MB) from nvidia-smi, polled back to back on a thread.

    The rate is whatever one nvidia-smi call takes, so every peak is reported with its sample
    count. Torch's caching allocator keeps what it took until emptied, which is what lets a poll
    this coarse see the probe's own peak. Without nvidia-smi (the CPU dev VM) it reports None.
    """

    def __init__(self) -> None:
        self.samples: list[int] = []
        self.total_mb: int | None = None
        self.failure: Exception | None = None
        try:
            self._sample()
        except (OSError, subprocess.CalledProcessError, ValueError):
            if DEVICE == "cuda":
                raise
            return
        threading.Thread(target=self._poll, daemon=True).start()

    def _sample(self) -> None:
        out = subprocess.run(SMI, check=True, capture_output=True, text=True).stdout
        used, total = (int(field) for field in out.split(","))
        self.total_mb = total
        self.samples.append(used)

    def _poll(self) -> None:
        while self.failure is None:
            try:
                self._sample()
            except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                self.failure = exc

    def _wait_for_new_reading(self, count: int) -> None:
        deadline = time.monotonic() + 5
        while len(self.samples) <= count and self.failure is None and time.monotonic() < deadline:
            time.sleep(0.02)

    def reading(self) -> int | None:
        """A reading taken after this call, not the last one polled (None without nvidia-smi)."""
        if not self.samples:
            return None
        self._wait_for_new_reading(len(self.samples))
        return self.samples[-1]

    @contextlib.contextmanager
    def watch(self):
        """Yield a dict that holds the peak and sample count seen while the block ran."""
        seen: dict[str, int | None] = {"device_peak_mb": None, "device_samples": 0}
        if not self.samples:
            yield seen
            return
        first = len(self.samples) - 1  # the reading from just before the block opens it
        try:
            yield seen
        finally:
            self._wait_for_new_reading(len(self.samples))  # one more, taken after the work
            window = self.samples[first:]
            seen["device_peak_mb"], seen["device_samples"] = max(window), len(window)


def attempt(fn):
    """(value, None) when fn returns; (None, failure) when it raises what a run can survive."""
    try:
        return fn(), None
    except (ValueError, RuntimeError) as exc:  # torch.OutOfMemoryError is a RuntimeError
        text = str(exc)
        oom = "out of memory" in text.lower() or "ALLOC_FAILED" in text
        if not oom:
            traceback.print_exc()
        message = (text.splitlines() or [type(exc).__name__])[0][:200]
        return None, {"status": "oom" if oom else "error", "message": message}


def run_step(monitor: DeviceMonitor, fn):
    """(value, stats, failure): fn's value, measure()'s stats plus the device peak, any failure."""
    with monitor.watch() as device:
        result, failure = attempt(lambda: measure(fn))
    value, stats = result if result else (None, {})
    return value, {**stats, **device}, failure


def align_song(monitor, arm, song, sheets, stems, shared, *, save: bool) -> dict:
    """One run-table row for ``song``; with ``save`` (fp16) a good run also writes its JSON and .ass."""
    video_id = song.video_id
    result, stats, failure = run_step(
        monitor, lambda: arm.align(stems[video_id], sheets[video_id], song.lang)
    )
    row = {
        **shared,
        "song": f"#{song.num}",
        "status": "ok",
        "stage": "",
        "message": "",
        "align_s": stats.get("wall_s"),
        "align_alloc_mb": stats.get("peak_allocated_mb"),
        "align_reserved_mb": stats.get("peak_reserved_mb"),
        "device_align_peak_mb": stats["device_peak_mb"],
        "device_samples": stats["device_samples"],
    }
    if failure:
        return {**row, **failure, "stage": "align"}
    timings, info = result
    row.update(frames=info["frames"], nonfinite=info["nonfinite"])
    if save:
        record = track_record(
            sheets[video_id], timings,
            arm=arm.arm, model=arm.model_id, lang=song.lang, run=row,
        )  # fmt: skip
        out = OUT_DIR / "half" / video_id
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / f"{arm.arm}.json", record)
        write_ass(out / f"{arm.arm}.ass", sheets[video_id], timings)
    return row


def write_table(rows: list[dict]) -> None:
    """The run table in both forms: JSON (every field) and TSV (the columns above)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "half_runs.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    lines = ["\t".join(COLUMNS)]
    lines += ["\t".join("" if r.get(c) is None else str(r[c]) for c in COLUMNS) for r in rows]
    (OUT_DIR / "half_runs.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_rows() -> list[dict]:
    """Rows from an earlier run, so that a rerun of one arm keeps the other's."""
    path = OUT_DIR / "half_runs.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def upsert(rows: list[dict], row: dict) -> None:
    key = (row["song"], row["arm"], row["precision"])
    rows[:] = [r for r in rows if (r["song"], r["arm"], r["precision"]) != key] + [row]


def write_commands() -> None:
    lines = []
    for song in PILOT:
        for name in ARMS:
            ass = OUT_DIR / "half" / song.video_id / f"{name}.ass"
            if song.lang in make_arm(name).languages and ass.exists():
                (video,) = [p for p in find_in_library(song.video_id) if p.suffix in VIDEO_SUFFIXES]
                lines.append(f"# #{song.num} {song.title} ({song.lang}), {name} at fp16")
                lines.append(f'{name:4} mpv "{video}" --sub-file="{ass}"')
                lines.append("")
    (OUT_DIR / "commands.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--songs", default=",".join(str(s.num) for s in PILOT))
    args = parser.parse_args()
    songs = [s for s in PILOT if str(s.num) in args.songs.split(",")]

    monitor = DeviceMonitor()  # before anything touches the card, so its first reading is clean
    before_probe = monitor.reading()
    device = torch.cuda.get_device_name(0) if DEVICE == "cuda" else "cpu"
    print(
        f"device {device}, torch {torch.__version__}; device-wide memory used before the probe "
        f"loads anything: {before_probe} of {monitor.total_mb} MB",
        flush=True,
    )

    sheets = {s.video_id: load_sheet(s.video_id) for s in songs}
    stems = {s.video_id: load_stem(s.video_id) for s in songs}
    rows = load_rows()
    for name in args.arms.split(","):
        for precision, half in PRECISIONS:
            arm = make_arm(name, half=half)
            todo = [s for s in songs if s.lang in arm.languages]
            if not todo:
                continue
            before_load = monitor.reading()
            _, load_stats, failure = run_step(monitor, arm.load)
            shared = {
                "device": device,
                "arm": name,
                "precision": precision,
                "device_before_load_mb": before_load,
                "device_total_mb": monitor.total_mb,
                "load_s": load_stats.get("wall_s"),
                "load_alloc_mb": load_stats.get("peak_allocated_mb"),
                "load_reserved_mb": load_stats.get("peak_reserved_mb"),
                "device_load_peak_mb": load_stats["device_peak_mb"],
                "device_after_load_mb": None if failure else monitor.reading(),
            }
            print(f"{name} {precision} load: {shared} {failure or ''}", flush=True)
            for song in todo:
                if failure:
                    row = {**shared, "song": f"#{song.num}", **failure, "stage": "load"}
                else:
                    row = align_song(monitor, arm, song, sheets, stems, shared, save=half)
                upsert(rows, row)
                write_table(rows)
                print(f"#{song.num} {name} {precision}: {row}", flush=True)
            if not failure:
                arm.unload()
            del arm
            free_memory()
    write_table(rows)
    write_commands()
    if monitor.failure:
        print(f"WARNING: nvidia-smi polling stopped early: {monitor.failure!r}", flush=True)
    print(f"wrote half_runs.json, half_runs.txt and commands.txt in {OUT_DIR}")


if __name__ == "__main__":
    main()
