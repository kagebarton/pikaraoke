#!/usr/bin/env python3
"""Edge snap Phase 7a: does a voicing trace find the lead's release earlier
than the RMS release trace, on the end snap's ``to_bound`` extensions?

``snap_line_ends`` follows the vocal stem's loudness, so a backing voice
or the next line holding the level past the lead's release drags the
extension all the way to the next line (``to_bound``). This study follows
the *pitch* that was sounding at the claimed end instead, and reports
where that contour breaks relative to the RMS bound. Study only; spec in
``plans/edge-snap-coverage-accuracy.md`` ("7a pinned").

Population is every recorded ``to_bound`` record in the corpus bundles;
each window is rebuilt from the bundle (no re-snap) and must pass the
bound fidelity check. For the 5 eyeball songs it writes
``karaoke/<stem>.voicing.ass`` (earlier records' ends cut back to the
voicing break) to A/B against the shipped ``.ass``.

Run from the repo root::

    python scripts/voicing_release_study.py --folder PATH [--song SUBSTRING]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
from edge_snap_ass import snap_stem_path
from onset_snap_ass import _fmt, parse_ass_lines

from pikaraoke.lib.onset_snap import (
    ENVELOPE_SR,
    HOP_S,
    MIN_SHIFT_S,
    MIN_WORD_DUR_S,
    NEXT_LINE_GAP_S,
)
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import generate_ass

# pYIN over C2..C#6, one frame per envelope hop.
FMIN_HZ = 65.0
FMAX_HZ = 1100.0
FRAME_LENGTH = 1024
HOP = int(HOP_S * ENVELOPE_SR)

# Analysis window around [claimed_end, bound]: the lead-in lets the voicing
# model settle before the anchor, the tail lets a break near the bound confirm.
PAD_PRE_S = 1.0
PAD_POST_S = 0.5

# Trace: anchor on the last voiced frame at most ANCHOR_S before the claimed
# end, follow f0 while it moves at most JUMP_ST per voiced frame, and call a
# break at the first run of BREAK_FRAMES off-contour frames (the RMS trace's
# own RELEASE_SUSTAIN_S).
ANCHOR_S = 0.1
JUMP_ST = 1.5
BREAK_FRAMES = 8

BOUND_TOL_S = 0.002
N_EYEBALL_SONGS = 5
N_EYEBALL_PER_SONG = 3

# delta = break - bound. Upper edges, inclusive.
DELTA_BINS = [
    (-2.0, "<=-2"),
    (-1.0, "(-2,-1]"),
    (-0.5, "(-1,-0.5]"),
    (-MIN_SHIFT_S, "(-0.5,-0.15]"),
]
AGREE_BIN = "(-0.15,0]"
BIN_ORDER = ["no_break", AGREE_BIN] + [label for _, label in reversed(DELTA_BINS)]


def decode_pcm(audio_path: Path) -> np.ndarray:
    """16 kHz mono float PCM, the same decode ``rms_envelope_db`` runs."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        str(ENVELOPE_SR),
        "-f",
        "s16le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def to_bound_windows(bundle: dict) -> list[dict]:
    """The bundle's recorded ``to_bound`` extensions as study windows.

    ``bound`` is the recorded line end (a ``to_bound`` end is the bound) and
    ``claimed_end`` is that minus the extension. ``bound_ok`` checks the
    bound against the next worded line's recorded start, which is how
    ``snap_line_ends`` derived it.
    """
    olt = bundle["output_line_timings"]
    index = {o["line_id"]: i for i, o in enumerate(olt)}
    extends = (((bundle.get("joint_stats") or {}).get("edge_snap") or {}).get("end") or {}).get(
        "extends"
    ) or []
    windows = []
    for rec in extends:
        if not rec["to_bound"]:
            continue
        i = index[rec["line_id"]]
        bound = olt[i]["end"]
        nxt = next((o for o in olt[i + 1 :] if o["n_words"]), None)
        bound_ok = nxt is not None and abs(bound - (nxt["start"] - NEXT_LINE_GAP_S)) <= BOUND_TOL_S
        windows.append(
            {
                "line_id": rec["line_id"],
                "olt_index": i,
                "start": olt[i]["start"],
                "claimed_end": bound - rec["extend_s"],
                "bound": bound,
                "extend_s": rec["extend_s"],
                "bound_ok": bound_ok,
            }
        )
    return windows


def trace_voicing(
    times: np.ndarray, f0: np.ndarray, voiced: np.ndarray, claimed_end: float, bound: float
) -> dict:
    """Where the pitch contour sounding at ``claimed_end`` breaks.

    Returns ``{"category": "no_anchor"}``, ``{"category": "no_break",
    "anchor_f0": ...}`` or ``{"category": "break", "anchor_f0", "break_t",
    "kind"}``. A break is the first frame after ``claimed_end`` (and before
    ``bound``) that starts :data:`BREAK_FRAMES` consecutive off-contour
    frames; ``kind`` says whether most of them were unvoiced or a voiced
    jump to another pitch.
    """
    in_anchor = (times >= claimed_end - ANCHOR_S) & (times <= claimed_end) & voiced
    if not in_anchor.any():
        return {"category": "no_anchor"}
    anchor = int(np.flatnonzero(in_anchor)[-1])

    on = np.zeros(len(times), dtype=bool)
    f_last = f0[anchor]
    for j in range(anchor + 1, len(times)):
        if voiced[j] and abs(12.0 * np.log2(f0[j] / f_last)) <= JUMP_ST:
            on[j] = True
            f_last = f0[j]

    for i in range(anchor + 1, len(times) - BREAK_FRAMES + 1):
        if times[i] <= claimed_end:
            continue
        if times[i] >= bound:
            break
        if not on[i : i + BREAK_FRAMES].any():
            n_unvoiced = int((~voiced[i : i + BREAK_FRAMES]).sum())
            return {
                "category": "break",
                "anchor_f0": float(f0[anchor]),
                "break_t": float(times[i]),
                "kind": "unvoiced" if n_unvoiced > BREAK_FRAMES // 2 else "jump",
            }
    return {"category": "no_break", "anchor_f0": float(f0[anchor])}


def delta_bin(delta: float) -> str:
    """Histogram label for a break's ``delta = break - bound``."""
    for upper, label in DELTA_BINS:
        if delta <= upper:
            return label
    return AGREE_BIN


def study_window(pcm: np.ndarray, win: dict) -> dict:
    """Run pYIN over one record's padded window and trace it."""
    s0 = max(int(round((win["claimed_end"] - PAD_PRE_S) * ENVELOPE_SR)), 0)
    s1 = min(int(round((win["bound"] + PAD_POST_S) * ENVELOPE_SR)), len(pcm))
    f0, voiced, _ = librosa.pyin(
        pcm[s0:s1],
        fmin=FMIN_HZ,
        fmax=FMAX_HZ,
        sr=ENVELOPE_SR,
        frame_length=FRAME_LENGTH,
        hop_length=HOP,
        center=True,
    )
    times = s0 / ENVELOPE_SR + np.arange(len(f0)) * HOP_S
    return trace_voicing(times, f0, voiced, win["claimed_end"], win["bound"])


def worded_ass_lines(ass_path: Path, bundle: dict) -> list[dict] | None:
    """Shipped ``.ass`` lines keyed by ``output_line_timings`` index.

    Positional: the writer emits one event per worded line, in order.
    None when the counts disagree (the ``.ass`` is from another run).
    """
    parsed = parse_ass_lines(ass_path)
    worded = [i for i, o in enumerate(bundle["output_line_timings"]) if o["n_words"]]
    if len(parsed) != len(worded):
        return None
    by_index = [None] * len(bundle["output_line_timings"])
    for i, line in zip(worded, parsed):
        by_index[i] = line
    return by_index


def hist_bins(rows: list[dict]) -> Counter:
    """Histogram counts over anchored rows (``no_anchor`` has no delta)."""
    return Counter(
        "no_break" if r["category"] == "no_break" else delta_bin(r["delta"])
        for r in rows
        if r["category"] != "no_anchor"
    )


def print_hist(label: str, counts: Counter, order: list[str]) -> None:
    print(f"hist {label} " + " ".join(f"{b}={counts[b]}" for b in order))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--song", default="", help="only songs whose name contains this")
    args = parser.parse_args()

    rows: list[dict] = []
    ass_by_song: dict[str, tuple[Path, list[dict] | None]] = {}
    n_bound_fail = n_text_mismatch = 0

    for bundle_path in sorted((args.folder / "alignment_debug").glob("*.json")):
        stem = bundle_path.stem
        if args.song.lower() not in stem.lower():
            continue
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        route = (bundle.get("pipeline_decisions") or {}).get("method_used")
        windows = to_bound_windows(bundle)
        print(f"{stem}  route={route} to_bound={len(windows)}")
        if not windows:
            continue

        ass_path = args.folder / "karaoke" / f"{stem}.ass"
        ass_lines = worded_ass_lines(ass_path, bundle) if ass_path.exists() else None
        if ass_lines is None:
            print("  ass unmatched (missing, or event count differs from worded lines)")
        ass_by_song[stem] = (ass_path, ass_lines)
        pcm = decode_pcm(snap_stem_path(args.folder, stem, bundle))

        for win in windows:
            if not win["bound_ok"]:
                n_bound_fail += 1
                print(f"  BOUND FAIL L{win['line_id']} bound={win['bound']:.3f}")
                continue
            res = study_window(pcm, win)
            line = ass_lines[win["olt_index"]] if ass_lines else None
            text = ""
            if line is not None:
                if abs(line["start"] - win["start"]) > 0.05:
                    n_text_mismatch += 1
                text = " ".join(w["word"] for w in line["words"][-5:])
            row = {"song": stem, "route": route, **win, **res}
            if res["category"] == "break":
                row["delta"] = res["break_t"] - win["bound"]
            rows.append(row)

            head = (
                f"  rec L{win['line_id']} {_fmt(win['start'])} "
                f"ce={_fmt(win['claimed_end'])} bound={_fmt(win['bound'])} "
                f"ext=+{win['extend_s']:.2f}"
            )
            if res["category"] == "no_anchor":
                body = "no_anchor"
            elif res["category"] == "no_break":
                body = f"f0={res['anchor_f0']:.0f} no_break"
            else:
                body = (
                    f"f0={res['anchor_f0']:.0f} brk={_fmt(res['break_t'])} "
                    f"delta={row['delta']:+.2f} kind={res['kind']}"
                )
            print(f"{head} {body}  ... {text}")

    earlier = [r for r in rows if r["category"] == "break" and r["delta"] <= -MIN_SHIFT_S]
    agree = [r for r in rows if r["category"] == "break" and r["delta"] > -MIN_SHIFT_S]
    print(
        f"total n_suspects={len(rows) + n_bound_fail} n_bound_fail={n_bound_fail} "
        f"n_no_anchor={sum(r['category'] == 'no_anchor' for r in rows)} "
        f"n_no_break={sum(r['category'] == 'no_break' for r in rows)} "
        f"n_agree={len(agree)} n_earlier={len(earlier)} n_text_mismatch={n_text_mismatch}"
    )

    print_hist("all", hist_bins(rows), BIN_ORDER)
    for route in sorted({r["route"] for r in rows}):
        print_hist(f"route={route}", hist_bins([r for r in rows if r["route"] == route]), BIN_ORDER)
    for kind in ("unvoiced", "jump"):
        subset = [r for r in rows if r.get("kind") == kind]
        print_hist(f"kind={kind}", hist_bins(subset), BIN_ORDER[1:])

    per_song = Counter(r["song"] for r in earlier)
    picks = sorted(per_song, key=lambda s: (-per_song[s], s))[:N_EYEBALL_SONGS]
    cfg = PipelineConfig()
    for song in picks:
        song_earlier = [r for r in earlier if r["song"] == song]
        listed = sorted(song_earlier, key=lambda r: r["delta"])[:N_EYEBALL_PER_SONG]
        print(f"eyeball {song}  n_earlier={per_song[song]}")
        ass_path, ass_lines = ass_by_song[song]
        for r in listed:
            line = ass_lines[r["olt_index"]] if ass_lines else None
            text = " ".join(w["word"] for w in line["words"]) if line else ""
            print(
                f"  L{r['line_id']} line={_fmt(r['start'])} ce={_fmt(r['claimed_end'])} "
                f"voicing_end={_fmt(r['break_t'])} shipped_end={_fmt(r['bound'])} "
                f"kind={r['kind']}  {text}"
            )
        if ass_lines is None:
            print("  no render (ass unmatched)")
            continue
        out_lines = [line for line in ass_lines if line is not None]
        for r in song_earlier:
            line = ass_lines[r["olt_index"]]
            last = line["words"][-1]
            new_end = max(r["break_t"], r["claimed_end"], last["start"] + MIN_WORD_DUR_S)
            line["words"][-1] = {**last, "end": new_end}
            line["end"] = new_end
        out_path = ass_path.with_name(ass_path.stem + ".voicing.ass")
        out_path.write_text(generate_ass(out_lines, cfg), encoding="utf-8")
        print(f"  wrote {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
