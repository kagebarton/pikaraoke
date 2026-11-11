"""Refine-on vs refine-off ablation over the real cue and joint routes.

Drives LyricAlignStage's own _run_cue_align / _run_joint with an in-process
worker stand-in. Every align result is cached by (slice audio md5, text), so
the OFF arm reuses the ON arm's pre-refine words; the only extra GPU cost is
the refine itself. Transcribe words come from each song's bundle (the cue
route ignores them; the joint matcher reads them). Writes nothing to the
library: slices, decoded stems and results go under the scratch dir.

Post-steps mirror LyricAlignStage.run: evidence veto (joint) then edge snap.
LRCLIB fill is skipped (it splices fill lines after the snap). Songs whose
bundle records an adopted de-reverb stem use the cached dry stem.

GPU: loads large-v3-turbo in-process, so stop the app first. Run from the
repo root (results already present are skipped, so a rerun resumes)::

    python scripts/probe_refine_ablation.py <out_dir> "<song stem>" ...

Then summarise with ``scripts/probe_refine_ablation_report.py <out_dir>``.
Record: ``plans/refine-ablation.md``.
"""

import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import stable_whisper  # noqa: E402

from pikaraoke.lib.cue_align import SOURCE_REALIGN  # noqa: E402
from pikaraoke.lib.evidence_veto import veto_uncorroborated_lines  # noqa: E402
from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.lib.onset_snap import decode_env_db, snap_line_edges  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.context import StageContext  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage  # noqa: E402
from pikaraoke.pipeline.workers.whisper_worker import (  # noqa: E402
    _apply_post_process,
    _extract_words,
    _splat,
)

LIB = Path.home() / "pikaraoke-songs"
OUT = Path(sys.argv[1])
SONGS = sys.argv[2:]


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ProbeWorker:
    def __init__(self, model, wcfg):
        self.model = model
        self.wcfg = wcfg
        self.refine = True
        self.cache: dict = {}
        self.calls: list[dict] = []

    def align_refine(self, vocal_path, lyrics_text, cancel_event=None, quiet=False):
        key = (md5(Path(vocal_path)), lyrics_text)
        entry = self.cache.get(key)
        rec = {"arm": "on" if self.refine else "off", "n_tok": len(lyrics_text.split())}
        if entry is None or (self.refine and "on" not in entry):
            t = time.perf_counter()
            res = self.model.align(str(vocal_path), lyrics_text, **_splat(self.wcfg.align))
            align_s = time.perf_counter() - t
            if res is None:
                raise RuntimeError("align returned None")
            _apply_post_process(res, self.wcfg.align_post_process)
            entry = {"off": _extract_words(res, 0), "align_s": align_s}
            rec["align_s"] = align_s
            if self.refine:
                t = time.perf_counter()
                res = self.model.refine(str(vocal_path), res, **_splat(self.wcfg.refine))
                rec["refine_s"] = time.perf_counter() - t
                _apply_post_process(res, self.wcfg.align_post_process)
                entry["on"] = _extract_words(res, 0)
            self.cache[key] = entry
        else:
            rec["cached"] = True
        self.calls.append(rec)
        return copy.deepcopy(entry["on" if self.refine else "off"])


def decode_wav(m4a: Path, wav: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(m4a),
            "-ac",
            "2",
            "-ar",
            "44100",
            "-sample_fmt",
            "s16",
            str(wav),
        ],
        check=True,
    )


def timings(lines):
    return [
        {
            "start": o.get("start"),
            "end": o.get("end"),
            "words": [(w["start"], w["end"]) for w in o.get("words") or []],
        }
        for o in lines
    ]


def run_song(stage, worker, cur: str, tmp: Path) -> dict:
    bundle = json.loads((LIB / "alignment_debug" / f"{cur}.json").read_text())
    old = bundle["song_stem"]
    method = bundle["pipeline_decisions"]["method_used"]
    js = bundle.get("joint_stats") or {}
    stem_m4a = LIB / "vocal" / f"{cur}---vocal.m4a"
    if js.get("dereverb", {}).get("adopted"):
        stem_m4a = LIB / "dereverb" / f"{cur}---dereverb.m4a"
    wav = tmp / "vocal.wav"
    decode_wav(stem_m4a, wav)
    tw = bundle.get("transcribe_words") or []
    stage._dereverb_gate = lambda ctx, v: (v, tw, None)
    artifacts = {}
    asr = LIB / "subtitles" / f"{cur}.en.asr.json3"
    if method == "joint" and js.get("n_ytasr_words") and asr.exists():
        artifacts["ytasr"] = {"asr_file": f"subtitles/{cur}.en.asr.json3"}
    ctx = StageContext(
        song_path=LIB / f"{cur}.mp4", tmp_dir=tmp, config=stage._config, artifacts=artifacts
    )
    out = {
        "song": cur,
        "method": method,
        "duration": bundle["media_duration_s"],
        "bundle_timings": bundle["output_line_timings"],
        "arms": {},
    }
    for arm in ("on", "off"):
        worker.refine = arm == "on"
        n0 = len(worker.calls)
        t = time.perf_counter()
        if method == "cue_align":
            src = bundle["lyrics"]["source_path"].replace("\\", "/").replace(old, cur)
            lines, align_lines, spans = stage._load_lyrics(LIB / src)
            lo, _, stats, env, _ = stage._run_cue_align(ctx, wav, lines, align_lines, spans)
        else:
            lines = bundle["lyrics"]["lines"]
            align_lines = bundle["lyrics"]["align_lines"]
            lo, _, _, stats = stage._run_joint(ctx, wav, "\n".join(align_lines), lines, align_lines)
            env = decode_env_db(wav, "probe")
            lo, _ = veto_uncorroborated_lines(lo, env)
        pre_snap = timings(lo)
        lo, _ = snap_line_edges(lo, wav, env=env, doubted_sources=frozenset({SOURCE_REALIGN}))
        calls = worker.calls[n0:]
        out["arms"][arm] = {
            "wall_s": time.perf_counter() - t,
            "align_s": sum(c.get("align_s", 0) for c in calls),
            "refine_s": sum(c.get("refine_s", 0) for c in calls),
            "n_calls": len(calls),
            "n_new_align": sum(1 for c in calls if "align_s" in c),
            "pre_snap": pre_snap,
            "final": timings(lo),
            "stats_keys": sorted(stats.keys()),
        }
        print(
            f"  {arm}: calls={len(calls)} align={out['arms'][arm]['align_s']:.1f}s "
            f"refine={out['arms'][arm]['refine_s']:.1f}s wall={out['arms'][arm]['wall_s']:.1f}s",
            flush=True,
        )
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = PipelineConfig()
    t = time.perf_counter()
    model = stable_whisper.load_model(cfg.whisper.load_model.model_path, device="cuda")
    print(f"model loaded {time.perf_counter() - t:.1f}s", flush=True)
    worker = ProbeWorker(model, cfg.whisper)
    stage = LyricAlignStage(worker, cfg, stem_worker=None)
    for cur in SONGS:
        res_path = OUT / f"{hashlib.md5(cur.encode()).hexdigest()[:10]}.json"
        if res_path.exists():
            continue
        print(f"== {cur}", flush=True)
        tmp = Path(get_temp_directory()) / "refine_ablation"
        tmp.mkdir(parents=True, exist_ok=True)
        worker.cache.clear()
        try:
            res = run_song(stage, worker, cur, tmp)
        except Exception as exc:  # probe: record and continue
            print(f"  FAILED: {exc!r}", flush=True)
            continue
        res_path.write_text(json.dumps(res))


if __name__ == "__main__":
    main()
