#!/usr/bin/env python3
"""Exact pre-snap replay of the joint route -- the second half of the
edge-snap harness pair (see ``edge_snap_ass.py``, which re-snaps already-
snapped shipped files).

Rebuilds each joint-route bundle's pre-snap line objects exactly as
production built them -- the captured 3-source DP plus windowed
re-align, replayed at the bundle's own recorded knobs (reusing
``replay_ytasr_third_source``'s chassis) -- runs the evidence veto, then
runs the checked-out ``onset_snap.snap_line_edges`` against production's
own aligned stem (:func:`edge_snap_ass.snap_stem_path`). Because this
input has never been snapped, it is the only one of the harness pair
that can show a phase that changes a line production already moved
(Phases 1, 3 and 5).

Cue-route bundles (``pipeline_decisions.method_used != "joint"``) are
skipped silently: they need whisper re-run per cue slice, which this
offline harness cannot do.

``--guard`` swaps the per-song snap output for a fidelity check against
that bundle's own recorded veto, snap records and final line timings --
run it on unmodified snap code before trusting any diff built on this
harness. ``--write-ass`` renders each replayed song to
``karaoke/<stem>.edgereplay.ass`` for eyeballing, never the shipped file.

Run from the repo root::

    python scripts/edge_snap_replay.py --folder PATH [--song SUBSTRING]
        [--multi-word-only] [--write-ass] [--guard]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

from edge_snap_ass import _stats_line, snap_stem_path
from replay_ytasr_third_source import _load_ytasr_words, _replay_output, _replay_spans

from pikaraoke.lib import alignment_capture
from pikaraoke.lib.evidence_veto import veto_uncorroborated_lines
from pikaraoke.lib.onset_snap import rms_envelope_db, snap_line_edges
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import generate_ass


def _replay_song(bundle_path: Path, folder: Path, bundle: dict, multi_word_only: bool) -> dict:
    """Rebuilds one joint bundle's pre-snap line objects and runs the
    checked-out snap on them against production's own aligned stem.

    Returns a dict with ``objs`` (post-veto, pre-snap, multi-word-only
    filtered), ``veto_stats``, ``final`` (post-snap) and ``edge_stats``;
    or ``{"skipped": ...}`` / ``{"bailed": ...}`` on a missing stem file
    or a decode failure.
    """
    stem = bundle_path.stem
    knobs = bundle["joint_stats"]["knobs"]
    ytasr_words = _load_ytasr_words(bundle, folder)
    realign = _replay_spans(bundle, ytasr_words, knobs["alpha"], knobs["beta"])
    objs, _ = _replay_output(bundle, ytasr_words, knobs["alpha"], knobs["beta"], realign)

    stem_path = snap_stem_path(folder, stem, bundle)
    if not stem_path.exists():
        return {"skipped": "no_stem"}
    try:
        env = rms_envelope_db(stem_path)
    except (subprocess.CalledProcessError, OSError) as exc:
        return {"bailed": f"decode_failed: {exc}"}

    objs, veto_stats = veto_uncorroborated_lines(objs, env)
    if multi_word_only:
        objs = [o for o in objs if len(o.get("words") or []) != 1]

    final, edge_stats = snap_line_edges(objs, stem_path, env=env)
    return {"objs": objs, "veto_stats": veto_stats, "final": final, "edge_stats": edge_stats}


def _first_diff_line_id(recorded: list[dict], replay: list[dict]) -> int | str:
    """The ``line_id`` at the first index where two record lists differ.

    Callers only reach this once they already know the lists differ, so
    the ``"n/a"`` fallback should be unreachable.
    """
    for i in range(max(len(recorded), len(replay))):
        rec = recorded[i] if i < len(recorded) else None
        rep = replay[i] if i < len(replay) else None
        if rec != rep:
            return (rec or rep)["line_id"]
    return "n/a"


def _guard_check(bundle: dict, veto_stats: dict, edge_stats: dict, final: list[dict]) -> str | None:
    """Checks the four fidelity conditions Phase 0 pins for this replay.

    Returns ``None`` when the replay reproduces the bundle's recorded
    veto, snap records, output timings and fill-free-ness exactly, else
    a ``"<check> first_line_id=<id>"`` failure description.
    """
    joint_stats = bundle["joint_stats"]

    recorded_veto = joint_stats.get("evidence_veto") or {}
    recorded_vetoed = {e["line_id"] for e in recorded_veto.get("lines", []) if e["vetoed"]}
    replay_vetoed = {e["line_id"] for e in veto_stats.get("lines", []) if e["vetoed"]}
    if (
        veto_stats.get("n_vetoed") != recorded_veto.get("n_vetoed")
        or replay_vetoed != recorded_vetoed
    ):
        diff = sorted(recorded_vetoed ^ replay_vetoed)
        return f"veto first_line_id={diff[0] if diff else 'n/a'}"

    recorded_onset = (joint_stats.get("edge_snap") or {}).get("onset") or {}
    recorded_end = (joint_stats.get("edge_snap") or {}).get("end") or {}
    replay_onset = edge_stats["onset"]
    replay_end = edge_stats["end"]
    if replay_onset.get("snaps") != recorded_onset.get("snaps"):
        first = _first_diff_line_id(
            recorded_onset.get("snaps") or [], replay_onset.get("snaps") or []
        )
        return f"onset_snaps first_line_id={first}"
    if replay_end.get("extends") != recorded_end.get("extends"):
        first = _first_diff_line_id(
            recorded_end.get("extends") or [], replay_end.get("extends") or []
        )
        return f"end_extends first_line_id={first}"
    for k, v in recorded_onset.items():
        if replay_onset.get(k) != v:
            return f"onset_stats:{k} first_line_id=n/a"
    for k, v in recorded_end.items():
        if replay_end.get(k) != v:
            return f"end_stats:{k} first_line_id=n/a"

    recorded_olt = bundle["output_line_timings"]
    replay_olt = alignment_capture.output_line_timings(final)
    if len(recorded_olt) != len(replay_olt):
        return "output_timings_length first_line_id=n/a"
    for rec, rep in zip(recorded_olt, replay_olt):
        if rec["line_id"] != rep["line_id"] or rec["n_words"] != rep["n_words"]:
            return f"output_timings first_line_id={rec['line_id']}"
        for key in ("start", "end"):
            rv, pv = rec[key], rep[key]
            if (rv is None) != (pv is None):
                return f"output_timings first_line_id={rec['line_id']}"
            if rv is not None and abs(rv - pv) > 1e-6:
                return f"output_timings first_line_id={rec['line_id']}"

    filled = (joint_stats.get("lrclib_fill") or {}).get("filled_lids")
    if filled:
        return "lrclib_fill first_line_id=n/a"

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--song", default="", help="only songs whose name contains this")
    parser.add_argument(
        "--multi-word-only",
        action="store_true",
        help="drop one-word line objects before snapping",
    )
    parser.add_argument(
        "--write-ass",
        action="store_true",
        help="write karaoke/<stem>.edgereplay.ass per replayed song",
    )
    parser.add_argument(
        "--guard",
        action="store_true",
        help="check replay fidelity against each bundle's recorded output, instead of snap stats",
    )
    args = parser.parse_args()

    cfg = PipelineConfig()
    debug_dir = args.folder / "alignment_debug"
    n_songs = 0
    total_onset: Counter = Counter()
    total_end: Counter = Counter()
    any_guard_fail = False

    for bundle_path in sorted(debug_dir.glob("*.json")):
        stem = bundle_path.stem
        if args.song.lower() not in stem.lower():
            continue
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if (bundle.get("pipeline_decisions") or {}).get("method_used") != "joint":
            continue
        print(stem)

        result = _replay_song(bundle_path, args.folder, bundle, args.multi_word_only)
        if result.get("skipped"):
            print(f"  skipped ({result['skipped']})")
            continue
        if result.get("bailed"):
            print(f"  bailed ({result['bailed']})")
            continue

        if args.guard:
            fail = _guard_check(bundle, result["veto_stats"], result["edge_stats"], result["final"])
            if fail is None:
                print("  GUARD PASS")
            else:
                print(f"  GUARD FAIL {fail}")
                any_guard_fail = True
            continue

        words_by_id = {o.get("line_id"): len(o.get("words") or []) for o in result["objs"]}
        for rec in result["edge_stats"]["onset"]["snaps"]:
            tag = "[1w] " if words_by_id.get(rec["line_id"]) == 1 else ""
            print(f"  rec onset {tag}L{rec['line_id']} +{rec['shift_s']:.3f}")
        for rec in result["edge_stats"]["end"]["extends"]:
            tag = "[1w] " if words_by_id.get(rec["line_id"]) == 1 else ""
            flag = " to_bound" if rec["to_bound"] else ""
            print(f"  rec end {tag}L{rec['line_id']} +{rec['extend_s']:.3f}{flag}")

        print(_stats_line("onset", result["edge_stats"]["onset"]))
        print(_stats_line("end", result["edge_stats"]["end"]))

        if args.write_ass:
            out_path = args.folder / "karaoke" / f"{stem}.edgereplay.ass"
            out_path.write_text(generate_ass(result["final"], cfg), encoding="utf-8")
            print(f"  wrote {out_path.name}")

        n_songs += 1
        for k, v in result["edge_stats"]["onset"].items():
            if isinstance(v, int) and not isinstance(v, bool):
                total_onset[k] += v
        for k, v in result["edge_stats"]["end"].items():
            if isinstance(v, int) and not isinstance(v, bool):
                total_end[k] += v

    if args.guard:
        return 1 if any_guard_fail else 0

    if not n_songs:
        return 0
    print(f"total songs={n_songs}")
    print("total onset " + " ".join(f"{k}={v}" for k, v in sorted(total_onset.items())))
    print("total end " + " ".join(f"{k}={v}" for k, v in sorted(total_end.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
