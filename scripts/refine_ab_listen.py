"""Blind A/B listen for the refine on/off ablation (``plans/refine-ablation.md``).

``build`` turns a probe run (``probe_refine_ablation.py --ass-dir``) into a
session: per song, the two arms as ``track1.ass`` / ``track2.ass`` in a random
order, plus a jump list of the lines where the arms' timings differ most. The
track-to-arm key goes to ``key.json``; leave it unread until the verdicts are in.
``play`` opens one song in a libmpv window with both tracks loaded.

The .ass files carry lyric text: keep the session out of the repo and the
library. Run from the repo root::

    python scripts/refine_ab_listen.py build <results_dir> <ass_dir> <session_dir>
    python scripts/refine_ab_listen.py play <session_dir> <song number>

Keys in the window: ``j`` / ``J`` switch subtitle track, ``n`` / ``b`` next /
previous jump point, ``q`` quit.
"""

import argparse
import json
import random
import shutil
from pathlib import Path

LIB = Path.home() / "pikaraoke-songs"
MIN_DIVERGENCE_S = 0.25  # the ablation plan's "word moved" threshold
MAX_JUMPS = 15
JUMP_LEAD_S = 2.0  # land this long before the line so its entrance is heard


def divergence(on: dict, off: dict) -> float:
    """Largest start-time gap between the arms over a line's start and its words."""
    pairs = [(on["start"], off["start"])]
    if len(on["words"]) == len(off["words"]):
        pairs += [(a[0], b[0]) for a, b in zip(on["words"], off["words"])]
    gaps = [abs(a - b) for a, b in pairs if a is not None and b is not None]
    return max(gaps, default=0.0)


def pick_jumps(on_lines: list[dict], off_lines: list[dict]) -> list[float]:
    """Seek targets for the most divergent lines, in song order."""
    scored = [
        (divergence(on, off), min(on["start"], off["start"]))
        for on, off in zip(on_lines, off_lines, strict=True)
        if on["start"] is not None and off["start"] is not None
    ]
    top = sorted((s for s in scored if s[0] >= MIN_DIVERGENCE_S), reverse=True)[:MAX_JUMPS]
    return sorted(round(max(0.0, start - JUMP_LEAD_S), 2) for _, start in top)


def build(results_dir: Path, ass_dir: Path, session: Path) -> None:
    rng = random.SystemRandom()
    results = sorted(
        (json.loads(p.read_text()) for p in results_dir.glob("*.json")), key=lambda r: r["song"]
    )
    manifest, key = [], {}
    for n, res in enumerate(results, 1):
        song_dir = session / f"{n:02d}"
        song_dir.mkdir(parents=True, exist_ok=True)
        order = ["on", "off"]
        rng.shuffle(order)
        for k, arm in enumerate(order, 1):
            shutil.copyfile(ass_dir / f"{res['song']}.{arm}.ass", song_dir / f"track{k}.ass")
        jumps = pick_jumps(res["arms"]["on"]["final"], res["arms"]["off"]["final"])
        manifest.append({"n": n, "video": str(LIB / f"{res['song']}.mp4"), "jumps": jumps})
        key[f"{n:02d}"] = {f"track{k}": arm for k, arm in enumerate(order, 1)}
        print(f"{n:02d}  {Path(manifest[-1]['video']).stem}: {len(jumps)} jump points")
    (session / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (session / "key.json").write_text(json.dumps(key, indent=1))
    print(f"session written to {session} (key.json holds the track-to-arm key)")


def play(session: Path, n: int) -> None:
    import mpv  # deferred: only play needs libmpv

    entry = json.loads((session / "manifest.json").read_text())[n - 1]
    song_dir = session / f"{n:02d}"
    jumps = entry["jumps"]
    at = {"i": -1}

    def jump(step: int) -> None:
        at["i"] = (at["i"] + step) % len(jumps)
        player.command("seek", jumps[at["i"]], "absolute+exact")
        player.show_text(f"jump {at['i'] + 1}/{len(jumps)}", 1500)

    player = mpv.MPV(
        input_default_bindings=True, input_vo_keyboard=True, osc=True, force_window="yes"
    )
    try:
        player.message_handler("ab-next")(lambda *_: jump(1))
        player.message_handler("ab-prev")(lambda *_: jump(-1))
        player.command("keybind", "n", "script-message ab-next")
        player.command("keybind", "b", "script-message ab-prev")
        player.play(entry["video"])
        player.wait_until_playing()
        player.command("sub-add", str(song_dir / "track1.ass"), "select", "Track 1")
        player.command("sub-add", str(song_dir / "track2.ass"), "auto", "Track 2")
        print("j/J switch track, n/b next/previous jump point, q quit")
        player.wait_for_shutdown()
    finally:
        player.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("results_dir", type=Path)
    b.add_argument("ass_dir", type=Path)
    b.add_argument("session_dir", type=Path)
    p = sub.add_parser("play")
    p.add_argument("session_dir", type=Path)
    p.add_argument("n", type=int)
    args = parser.parse_args()
    if args.cmd == "build":
        build(args.results_dir, args.ass_dir, args.session_dir)
    else:
        play(args.session_dir, args.n)


if __name__ == "__main__":
    main()
