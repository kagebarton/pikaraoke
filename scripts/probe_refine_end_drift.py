"""Word-END drift between refine steps="se" and "s" (plans/reduce-refine-time.md).

The quality probe (probe_refine_quality.py) scores *line starts* and finds
SE==S by construction — both refine starts identically; only the dropped `e`
sweep moves word **ends**, which a start-based scorer can't see. This probe
fills that gap: it measures, reference-free, how far word ends move when the
`e` sweep is removed, isolating the one thing Lever 1 actually changes.

There is no word-level ground truth in the corpus (every reference is
start-only; see alignment_eval.py), so this is a *relative* measurement: how
far do `s` ends drift from `se` ends, and in which direction. It cannot say the
ends got *worse* — only how much they changed and whether the change is the
expected one (refine-of-ends pulls a word's end in off the next onset, i.e.
SE ends earlier than S).

Method — two controlled passes so the words are index-aligned:

  * Pass SE: a worker at steps="se". Per song: align_check -> refine -> SE words.
  * Pass S : a worker at steps="s".  Per song: align_check -> refine -> S words.

Pairing is by index. That is only valid if the two passes' pre-refine align
baselines agree, so each song cross-checks ``off_se`` vs ``off_s`` (same count,
matching starts) before pairing; mismatches are reported, not silently paired.
Refine never adds/removes tokens, so SE/S inherit the baseline's word count.

The passes run sequentially (one whisper model resident at a time) to stay
within VRAM. align/refine wall-clock is timed per pass — this also empirically
checks the quality probe's "se refine ~2x s refine" assumption.

Run (production config, same eligible corpus as probe_refine_quality.py):
    python scripts/probe_refine_end_drift.py
    python scripts/probe_refine_end_drift.py --songs Belle      # one song
    python scripts/probe_refine_end_drift.py --json out.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pikaraoke.pipeline.config import WhisperModelConfig  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402


def _load_eval_module():
    """Import scripts/eval_alignment.py by path (scripts/ is not a package)."""
    path = REPO_ROOT / "scripts" / "eval_alignment.py"
    spec = importlib.util.spec_from_file_location("eval_alignment", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EV = _load_eval_module()

# Baseline-agreement tolerance: the two passes' pre-refine align starts must
# match within this for index-pairing to be trustworthy. Forced alignment is
# argmax (no sampling), so deterministic up to float noise; >50ms means the
# passes diverged and the per-index drift is suspect.
_BASELINE_TOL_S = 0.05


def collect_songs(args) -> list[tuple[str, Path, str]]:
    """Resolve the eligible corpus (same filter as the quality probe): a song
    needs a timing reference, a vocal stem, and align lyrics. Returns
    ``(stem, vocal_path, lyrics_text)`` tuples; bundles are read only for the
    lyrics and corpus membership — the drift itself is reference-free."""
    song_dir = Path(args.folder)
    debug_dir = song_dir / "alignment_debug"
    vocal_dir = song_dir / "vocal"
    prov = EV.load_provenance(debug_dir)

    songs: list[tuple[str, Path, str]] = []
    for path in sorted(debug_dir.glob("*.json")):
        if path.name == EV.PROVENANCE_FILE:
            continue
        bundle = json.loads(path.read_text(encoding="utf-8"))
        stem = bundle.get("song_stem", path.stem)
        if args.songs and not any(
            tok.strip().lower() in stem.lower() for tok in args.songs.split(",")
        ):
            continue
        cue = EV.resolve_reference(
            bundle, song_dir, debug_dir, prov, args.offline, prefer_lrclib=True
        )
        if cue is None or isinstance(cue, str):
            continue  # not in eval corpus / unresolved reference
        vocal = vocal_dir / f"{stem}---vocal.m4a"
        align_lines = bundle.get("lyrics", {}).get("align_lines")
        if not vocal.exists() or not align_lines:
            continue
        songs.append((stem, vocal, "\n".join(align_lines)))
    return songs


def run_pass(steps: str, songs: list[tuple[str, Path, str]]) -> tuple[dict, list]:
    """One full corpus pass at a fixed refine ``steps``. Per song: align_check
    then refine. Returns ``{stem: {"off", "refined"}}`` plus per-song timings.
    The worker is started and stopped here so only one model is resident."""
    wcfg = WhisperModelConfig()
    wcfg.refine.steps = steps
    whisper = WhisperWorker(config=wcfg)
    whisper.start()
    out: dict[str, dict] = {}
    cost: list[dict] = []
    try:
        for stem, vocal, lyrics in songs:
            print(f"[{steps}] {stem[:60]} ...", flush=True)
            t = time.monotonic()
            check = whisper.align_check(vocal_path=vocal, lyrics_text=lyrics)
            t_align = time.monotonic() - t
            t = time.monotonic()
            refined = whisper.refine_from_cached(result_id=check["result_id"], vocal_path=vocal)
            t_refine = time.monotonic() - t
            out[stem] = {"off": check["words"], "refined": refined}
            cost.append(
                {"song": stem, "align_s": round(t_align, 1), "refine_s": round(t_refine, 1)}
            )
            print(f"       align {t_align:.1f}s  refine({steps}) {t_refine:.1f}s", flush=True)
    finally:
        whisper.stop()
    return out, cost


def _p90(abs_vals: list[float]) -> float:
    if not abs_vals:
        return 0.0
    ordered = sorted(abs_vals)
    return ordered[min(len(ordered) - 1, round(0.9 * (len(ordered) - 1)))]


def _pct(vals: list[float], keep) -> float:
    return 100.0 * sum(1 for v in vals if keep(v)) / len(vals) if vals else 0.0


def compare_song(stem: str, se: dict, s: dict) -> dict | str:
    """End-drift metrics for one song, pairing SE/S words by index. Returns a
    skip reason string if the two passes' baselines disagree (non-deterministic
    align) or refine changed the word count — either invalidates pairing."""
    off_se, off_s = se["off"], s["off"]
    se_words, s_words = se["refined"], s["refined"]
    if len(off_se) != len(off_s):
        return f"align count mismatch (se={len(off_se)} s={len(off_s)})"
    if len(se_words) != len(off_se) or len(s_words) != len(off_s):
        return f"refine changed word count (se {len(off_se)}->{len(se_words)}, s ->{len(s_words)})"
    if not off_se:
        return "no words"

    off_skew = max(abs(a["start"] - b["start"]) for a, b in zip(off_se, off_s))
    d_end = [se_words[i]["end"] - s_words[i]["end"] for i in range(len(se_words))]
    abs_end = [abs(x) for x in d_end]
    d_start_max = max(abs(se_words[i]["start"] - s_words[i]["start"]) for i in range(len(se_words)))
    return {
        "song": stem,
        "n": len(d_end),
        "med_abs_end": round(statistics.median(abs_end), 3),
        "p90_abs_end": round(_p90(abs_end), 3),
        "max_abs_end": round(max(abs_end), 3),
        "signed_med_end": round(statistics.median(d_end), 3),
        "pct_se_earlier": round(_pct(d_end, lambda v: v < -0.05), 1),
        "pct_se_later": round(_pct(d_end, lambda v: v > 0.05), 1),
        "pct_moved_250": round(_pct(abs_end, lambda v: v > 0.25), 1),
        "max_abs_start": round(d_start_max, 3),
        "baseline_skew": round(off_skew, 3),
        "_d_end": d_end,
    }


_HEADER = (
    f"{'song':<44}{'n':>6}{'med|Δe|':>9}{'p90|Δe|':>9}{'max|Δe|':>9}"
    f"{'signed':>8}{'SE<S%':>7}{'SE>S%':>7}{'>250ms':>8}{'max|Δs|':>9}"
)


def _row(r: dict) -> str:
    return (
        f"{r['song'][:43]:<44}{r['n']:>6}{r['med_abs_end']:>9.3f}{r['p90_abs_end']:>9.3f}"
        f"{r['max_abs_end']:>9.3f}{r['signed_med_end']:>+8.3f}{r['pct_se_earlier']:>7.1f}"
        f"{r['pct_se_later']:>7.1f}{r['pct_moved_250']:>8.1f}{r['max_abs_start']:>9.3f}"
    )


def report(rows: list[dict], pooled_d_end: list[float], skipped: list, cost: dict) -> None:
    print("\n===== WORD-END DRIFT (SE steps=se vs S steps=s) =====")
    print("Δe = se_end - s_end; signed<0 means SE ends EARLIER (refine pulls the end in).")
    print(_HEADER)
    print("-" * len(_HEADER))
    for r in sorted(rows, key=lambda x: x["signed_med_end"]):
        print(_row(r))
    print("-" * len(_HEADER))

    if pooled_d_end:
        abs_pooled = [abs(x) for x in pooled_d_end]
        pooled = {
            "song": f"POOLED ({len(rows)} songs)",
            "n": len(pooled_d_end),
            "med_abs_end": round(statistics.median(abs_pooled), 3),
            "p90_abs_end": round(_p90(abs_pooled), 3),
            "max_abs_end": round(max(abs_pooled), 3),
            "signed_med_end": round(statistics.median(pooled_d_end), 3),
            "pct_se_earlier": round(_pct(pooled_d_end, lambda v: v < -0.05), 1),
            "pct_se_later": round(_pct(pooled_d_end, lambda v: v > 0.05), 1),
            "pct_moved_250": round(_pct(abs_pooled, lambda v: v > 0.25), 1),
            "max_abs_start": max(r["max_abs_start"] for r in rows),
        }
        print(_row(pooled))

    worst_skew = max((r["baseline_skew"] for r in rows), default=0.0)
    print(f"\nmax baseline skew across songs: {worst_skew:.3f}s (tol {_BASELINE_TOL_S}s)")
    if worst_skew > _BASELINE_TOL_S:
        print("  WARNING: a pass's pre-refine align diverged — per-index pairing is suspect.")

    for tag, runs in cost.items():
        total = sum(c["refine_s"] for c in runs)
        med = statistics.median(c["refine_s"] for c in runs) if runs else 0.0
        print(f"refine {tag:<2} total {total:7.1f}s  (median {med:.1f}s/song)")

    if skipped:
        print("\nskipped:")
        for stem, why in skipped:
            print(f"  {stem[:50]:<50} {why}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--folder", default=EV.DEFAULT_FOLDER, help="song library folder")
    p.add_argument("--songs", default=None, help="comma-separated substring filter on song stem")
    p.add_argument("--offline", action="store_true", help="skip provenance queries on cache miss")
    p.add_argument("--json", dest="json_out", default=None, help="write results JSON here")
    args = p.parse_args()

    songs = collect_songs(args)
    if not songs:
        print("no eligible songs (need reference + vocal stem + align lyrics)")
        return 1
    print(f"{len(songs)} eligible songs; two GPU passes (se then s)\n")

    se_pass, se_cost = run_pass("se", songs)
    s_pass, s_cost = run_pass("s", songs)

    rows: list[dict] = []
    pooled_d_end: list[float] = []
    skipped: list[tuple[str, str]] = []
    for stem, _vocal, _lyrics in songs:
        if stem not in se_pass or stem not in s_pass:
            skipped.append((stem, "missing from a pass"))
            continue
        result = compare_song(stem, se_pass[stem], s_pass[stem])
        if isinstance(result, str):
            skipped.append((stem, result))
            continue
        pooled_d_end.extend(result.pop("_d_end"))
        rows.append(result)

    cost = {"se": se_cost, "s": s_cost}
    report(rows, pooled_d_end, skipped, cost)

    if args.json_out:
        out = {"songs": rows, "skipped": skipped, "cost": cost, "baseline_tol_s": _BASELINE_TOL_S}
        Path(args.json_out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
