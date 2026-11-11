#!/usr/bin/env python3
"""Summarise a refine-on vs refine-off ablation (``probe_refine_ablation.py``).

Three tables, one row per song:

1. Cost and movement: refine vs align seconds, and how far the final (post
   edge-snap) line starts and interior word starts move between the arms.
   ``bundle dmax`` checks the ON arm against the song's own bundle, i.e. that
   the probe reproduced production.
2. Transcriber witness: for words the arms place > 0.25 s apart, which arm sits
   closer to the transcribe pass's same word. NOT an independent reference --
   align-only words sit ~0.03 s from it, so it is biased toward the OFF arm.
3. Direction and captions: the signed refine shift of moved words, and (cue
   route) for lines moved > 0.3 s, which arm is closer to the uploader cue
   start plus the fitted display lead.

Reads the library bundles for transcribe words, align lines and cue spans.
Prints counts and timings only, never lyric text. Run from the repo root::

    python scripts/probe_refine_ablation_report.py [results_dir]
"""

import glob
import json
import re
import statistics as st
import sys
from pathlib import Path

LIB = Path.home() / "pikaraoke-songs"
DEFAULT_DIR = Path(__file__).resolve().parent / "refine_ablation_results"


def _norm(s: str) -> str:
    return re.sub(r"[^\w']", "", s.lower())


def _q(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")


def _med(xs: list[float]) -> float:
    return st.median(xs) if xs else 0.0


def _paired_words(on: list[dict], off: list[dict]):
    """(line_id, on_word, off_word) where both arms timed the line's words 1:1."""
    for lid, (a, c) in enumerate(zip(on, off)):
        if len(a["words"]) == len(c["words"]):
            for i, (x, y) in enumerate(zip(a["words"], c["words"])):
                yield lid, i, x, y


def movement(d: dict, bundle: dict) -> str:
    on, off = d["arms"]["on"], d["arms"]["off"]
    b = [
        abs(x["start"] - y["start"])
        for x, y in zip(on["final"], d["bundle_timings"])
        if x["start"] is not None and y["start"] is not None
    ]
    dl = [
        abs(a["start"] - c["start"])
        for a, c in zip(on["final"], off["final"])
        if a["start"] is not None and c["start"] is not None
    ]
    dw = [
        abs(x[0] - y[0])
        for _, i, x, y in _paired_words(on["final"], off["final"])
        if i > 0  # interior words; word 0 is the edge-snapped line start
    ]
    rf, al = on["refine_s"], on["align_s"]
    return (
        f"lines={len(dl):3} bundle dmax={max(b, default=0):5.2f} | refine {rf:5.1f}s "
        f"align {al:5.1f}s ({100 * rf / (rf + al):.0f}%) | line d med {_med(dl):.3f} "
        f"p90 {_q(dl, .9):.3f} >0.15:{sum(x > .15 for x in dl):3} >0.5:{sum(x > .5 for x in dl):2} "
        f">1:{sum(x > 1 for x in dl):2} | word d p90 {_q(dw, .9):.3f} "
        f">0.25:{100 * sum(x > .25 for x in dw) / max(1, len(dw)):.0f}%"
    )


def witness(d: dict, bundle: dict, pool: list) -> str:
    tw = [(_norm(w["word"]), w["start"]) for w in bundle["transcribe_words"]]
    al = bundle["lyrics"]["align_lines"]
    won = woff = tie = 0
    eon: list[float] = []
    eoff: list[float] = []
    on, off = d["arms"]["on"]["final"], d["arms"]["off"]["final"]
    for lid, i, x, y in _paired_words(on, off):
        toks = al[lid].split() if lid < len(al) else []
        if len(toks) != len(on[lid]["words"]) or abs(x[0] - y[0]) <= 0.25:
            continue
        mid, tok = (x[0] + y[0]) / 2, _norm(toks[i])
        cands = [s for w, s in tw if w == tok and abs(s - mid) < 1.5]
        if not cands:
            continue
        s = min(cands, key=lambda s: abs(s - mid))
        e1, e2 = abs(x[0] - s), abs(y[0] - s)
        eon.append(e1)
        eoff.append(e2)
        if abs(e1 - e2) < 0.05:
            tie += 1
        elif e1 < e2:
            won += 1
        else:
            woff += 1
    pool.append((won, woff, tie, eon, eoff))
    return (
        f"moved+witnessed={len(eon):4} refine closer {won:3} off closer {woff:3} tie {tie:2} | "
        f"med err on {_med(eon):.2f} off {_med(eoff):.2f}"
    )


def direction(d: dict, bundle: dict, pool: dict) -> str:
    on, off = d["arms"]["on"]["final"], d["arms"]["off"]["final"]
    sh = [x[0] - y[0] for _, _, x, y in _paired_words(on, off) if abs(x[0] - y[0]) > 0.25]
    pool["shifts"] += sh
    out = (
        f"words moved>0.25: {len(sh):4}, refine later "
        f"{100 * sum(s > 0 for s in sh) / max(1, len(sh)):3.0f}%, med shift {_med(sh):+.2f}s"
    )
    if d["method"] != "cue_align":
        return out
    js = bundle["joint_stats"]
    lead = 0.0 if js["resectioned"] else js["offset_s"]  # resectioned spans are pre-shifted
    eon: list[float] = []
    eoff: list[float] = []
    w = [0, 0, 0]
    for a, c, sp in zip(on, off, bundle["cue_inputs"]["spans"]):
        if a["start"] is None or c["start"] is None or abs(a["start"] - c["start"]) <= 0.3:
            continue
        ref = sp[0] + lead
        e1, e2 = abs(a["start"] - ref), abs(c["start"] - ref)
        eon.append(e1)
        eoff.append(e2)
        w[0 if e1 + 0.05 < e2 else 1 if e2 + 0.05 < e1 else 2] += 1
    pool["cue_on"] += eon
    pool["cue_off"] += eoff
    pool["cue_w"] = [i + j for i, j in zip(pool["cue_w"], w)]
    if eon:
        out += (
            f" | lines moved>0.3s: {len(eon):2} closer-to-cue on/off/tie {w[0]}/{w[1]}/{w[2]} "
            f"med err on {_med(eon):.2f} off {_med(eoff):.2f}"
        )
    return out


def main() -> None:
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    songs = []
    for f in sorted(glob.glob(str(results / "*.json"))):
        d = json.loads(Path(f).read_text())
        bundle = json.loads((LIB / "alignment_debug" / f"{d['song']}.json").read_text())
        songs.append((d, bundle))
    songs.sort(key=lambda s: (s[0]["method"], s[0]["song"]))
    label = lambda d: f"{d['method'][:5]} {d['song'][:40]:40}"  # noqa: E731

    print("== 1. Cost and movement (final, post edge snap)")
    for d, b in songs:
        print(label(d), movement(d, b))

    print("\n== 2. Transcriber witness (biased toward OFF; see docstring)")
    wpool: dict[str, list] = {"cue_align": [], "joint": []}
    for d, b in songs:
        print(label(d), witness(d, b, wpool[d["method"]]))
    for method, rows in wpool.items():
        eon = [e for r in rows for e in r[3]]
        eoff = [e for r in rows for e in r[4]]
        print(
            f"POOLED {method}: n {len(eon)} refine closer {sum(r[0] for r in rows)} "
            f"off closer {sum(r[1] for r in rows)} tie {sum(r[2] for r in rows)} "
            f"med err on {_med(eon):.2f} off {_med(eoff):.2f}"
        )

    print("\n== 3. Shift direction; cue lines vs uploader cue + fitted lead")
    dpool: dict = {"shifts": [], "cue_on": [], "cue_off": [], "cue_w": [0, 0, 0]}
    for d, b in songs:
        print(label(d), direction(d, b, dpool))
    sh = dpool["shifts"]
    print(
        f"POOLED words moved {len(sh)} later {100 * sum(s > 0 for s in sh) / len(sh):.0f}% "
        f"med {_med(sh):+.2f}s"
    )
    print(
        f"POOLED cue lines {len(dpool['cue_on'])} on/off/tie {dpool['cue_w']} "
        f"med err on {_med(dpool['cue_on']):.2f} off {_med(dpool['cue_off']):.2f}"
    )


if __name__ == "__main__":
    main()
