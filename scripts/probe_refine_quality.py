"""Quality + cost ablation for the refine `steps` lever (plans/reduce-refine-time.md).

Answers the gating question the cost probe can't: does dropping refine work
*regress placement*? Three arms, scored against each song's timing reference
with the production eval scorer:

  * SE  — refine steps="se" (current production). FREE: the alignment-debug
          bundle's cached ``words`` are already the se-refined align words
          (``words_source == "refine"``), so this is just the existing replay.
  * S   — refine steps="s" (Lever 1). Re-run on GPU.
  * OFF — no refine (Lever 2), raw align words from ``align_check``.

One GPU pass at steps="s" yields both S (refine output) and OFF
(align_check's pre-refine words). SE needs no GPU. Per song we reuse the
bundle's cached ``transcribe_words`` (refine-independent) so the *only*
variable across arms is the align word stream — isolating refine's effect.

Cost: the S-arm align/refine wall-clock is timed per song. SE refine is
~2x S refine by construction (steps="se" sweeps starts then ends; "s" only
starts) — verified single-song in scripts/probe_refine_cost.py; not re-timed
here to save a full second GPU pass.

Run (production config, all eligible corpus songs):
    python scripts/probe_refine_quality.py
    python scripts/probe_refine_quality.py --songs Mirrors      # one song
    python scripts/probe_refine_quality.py --json out.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pikaraoke.pipeline.config import PipelineConfig, WhisperModelConfig  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import WhisperWorker  # noqa: E402


def _load_eval_module():
    """Import scripts/eval_alignment.py by path (scripts/ is not a package)."""
    path = REPO_ROOT / "scripts" / "eval_alignment.py"
    spec = importlib.util.spec_from_file_location("eval_alignment", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EV = _load_eval_module()


def score_arm(bundle: dict, align_words: list[dict], cue, knobs: dict):
    """Score one arm: inject ``align_words`` into a bundle copy, reuse the
    eval scorer (replay joint matcher + score_song). ``cue`` is the resolved
    ``(cue_texts, cue_starts, ref_kind)`` triple."""
    cue_texts, cue_starts, ref_kind = cue
    arm_bundle = {**bundle, "words": align_words}
    result = EV.evaluate_bundle(
        arm_bundle, cue_texts, cue_starts, as_run=False, knobs=knobs, ref=ref_kind
    )
    if isinstance(result, str):
        return result  # skip reason
    score, _prior = result
    return score


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--folder", default=EV.DEFAULT_FOLDER, help="song library folder")
    p.add_argument("--songs", default=None, help="substring filter on song stem")
    p.add_argument("--offline", action="store_true", help="skip provenance queries on cache miss")
    p.add_argument("--json", dest="json_out", default=None, help="write results JSON here")
    args = p.parse_args()

    song_dir = Path(args.folder)
    debug_dir = song_dir / "alignment_debug"
    vocal_dir = song_dir / "vocal"
    if not debug_dir.is_dir():
        print(f"no bundle dir: {debug_dir}")
        return 1

    cfg = PipelineConfig()
    knobs = {
        "alpha": cfg.joint_alpha,
        "margin_s": cfg.joint_margin_s,
        "max_edit_ratio": cfg.joint_max_edit_ratio,
        "anchor_fallback": True,
    }
    prov = EV.load_provenance(debug_dir)

    # steps="s" worker; everything else production. Stems are pre-separated on
    # disk, so only whisper is resident — no stem-sep VRAM contention.
    wcfg = WhisperModelConfig()
    wcfg.refine.steps = "s"
    whisper = WhisperWorker(config=wcfg)
    whisper.start()

    arms: dict[str, list] = {"SE": [], "S": [], "OFF": []}
    skipped: list[tuple[str, str]] = []
    cost: list[dict] = []
    try:
        for path in sorted(debug_dir.glob("*.json")):
            if path.name == EV.PROVENANCE_FILE:
                continue
            bundle = json.loads(path.read_text(encoding="utf-8"))
            stem = bundle.get("song_stem", path.stem)
            if args.songs and args.songs.lower() not in stem.lower():
                continue

            cue = EV.resolve_reference(
                bundle, song_dir, debug_dir, prov, args.offline, prefer_lrclib=True
            )
            if cue is None:
                continue  # not in eval corpus
            if isinstance(cue, str):
                skipped.append((stem, cue))
                continue

            vocal = vocal_dir / f"{stem}---vocal.m4a"
            if not vocal.exists():
                skipped.append((stem, "vocal stem missing"))
                continue
            if not bundle.get("words") or bundle.get("transcribe_words") is None:
                skipped.append((stem, "bundle lacks cached matcher inputs"))
                continue

            lyrics_text = "\n".join(bundle["lyrics"]["align_lines"])
            print(f"[gpu] {stem[:60]} ...", flush=True)
            t = time.monotonic()
            check = whisper.align_check(vocal_path=vocal, lyrics_text=lyrics_text)
            t_align = time.monotonic() - t
            t = time.monotonic()
            s_words = whisper.refine_from_cached(result_id=check["result_id"], vocal_path=vocal)
            t_refine = time.monotonic() - t
            cost.append(
                {"song": stem, "align_s": round(t_align, 1), "refine_s": round(t_refine, 1)}
            )
            print(f"       align {t_align:.1f}s  refine(s) {t_refine:.1f}s", flush=True)

            # SE arm reuses the cached se-refined words; S/OFF from this pass.
            for name, words in (
                ("SE", bundle["words"]),
                ("S", s_words),
                ("OFF", check["words"]),
            ):
                outcome = score_arm(bundle, words, cue, knobs)
                if isinstance(outcome, str):
                    skipped.append((f"{stem} [{name}]", outcome))
                else:
                    arms[name].append(outcome)
    finally:
        whisper.stop()

    for name in ("SE", "S", "OFF"):
        print(
            f"\n===== ARM {name} "
            f"({'steps=se, current' if name == 'SE' else 'steps=s, Lever 1' if name == 'S' else 'no refine, Lever 2'}) ====="
        )
        if arms[name]:
            EV.print_report(arms[name], skipped if name == "SE" else [], knobs)

    if cost:
        ta = sum(c["align_s"] for c in cost)
        tr = sum(c["refine_s"] for c in cost)
        print(f"\n===== COST ({len(cost)} songs) =====")
        print(
            f"  total align        {ta:7.1f}s  (median {statistics.median(c['align_s'] for c in cost):.1f}s/song)"
        )
        print(
            f"  total refine S     {tr:7.1f}s  (median {statistics.median(c['refine_s'] for c in cost):.1f}s/song)"
        )
        print(
            f"  implied refine SE  {2 * tr:7.1f}s  (~2x S by steps mechanic; see probe_refine_cost.py)"
        )
        print(
            f"  Lever 1 refine saving ≈ {tr:.1f}s/corpus (50%); Lever 2 (OFF) saves all of SE refine"
        )

    if args.json_out:
        out = {
            "arms": {name: [asdict(s) for s in scs] for name, scs in arms.items()},
            "cost": cost,
            "skipped": skipped,
            "knobs": knobs,
        }
        Path(args.json_out).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
