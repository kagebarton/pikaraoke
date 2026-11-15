"""Build spec counts: the shape of what the GATE A rule keeps, read from Phase 0's outputs.

Read-only over the library. From the worktree root:
    PYTHONPATH=. python plans/backing-vocal-lines/spec_counts.py ~/pikaraoke-songs plans/backing-vocal-lines/out

Reads out/heard.json and out/songs.json. Prints where kept inline groups sit in their cue,
cues mixing a kept and a dropped group, how kept paren-only cues fall against today's
sections, overlaps between kept paren-only cues, re-sectioned songs and the evidence split.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import srt

from pikaraoke.lib.cue_align import segment_by_gaps
from pikaraoke.lib.genius_lyrics import strip_markup
from pikaraoke.lib.srt_cues import clean_cue_texts

RULE = "consume none +vocables +consist"
PAREN_RE = re.compile(r"\(([^)]*)\)")


def kept(row: dict) -> bool:
    """The ruled hybrid, with a quote-opened parenthetical dropped outright."""
    return row["kept"][RULE] and not row["text"].lstrip().startswith(('"', "“"))


def main(lib: Path, out: Path) -> None:
    rows = json.loads((out / "heard.json").read_text())
    songs = {s["key"]: s for s in json.loads((out / "songs.json").read_text())}
    keep = [r for r in rows if kept(r)]
    print(
        f"kept {len(keep)}; quote-opened among the rule's keeps {sum(r['kept'][RULE] for r in rows) - len(keep)}"
    )

    by_cue: dict[tuple, list[dict]] = {}
    for r in rows:
        by_cue.setdefault((r["song"], r["cue"]), []).append(r)
    mixed = [rs for rs in by_cue.values() if 0 < sum(map(kept, rs)) < len(rs)]
    print(f"cues with a kept and a dropped group: {len(mixed)}")
    for rs in mixed:
        print(f"    {rs[0]['song']} {rs[0]['kind']}: {[(r['group'], kept(r)) for r in rs]}")

    sheets: dict[str, list] = {}
    bundles: dict[str, dict] = {}

    def cues_of(song: str) -> list:
        if song not in sheets:
            text = (lib / songs[song]["sheet"]).read_text(encoding="utf-8-sig")
            sheets[song] = list(srt.parse(text))
        return sheets[song]

    def bundle_of(song: str) -> dict:
        if song not in bundles:
            path = lib / "alignment_debug" / songs[song]["bundle"]
            bundles[song] = json.loads(path.read_text())
        return bundles[song]

    where, glued = Counter(), Counter()
    for r in keep:
        if r["kind"] != "inline":
            continue
        text = strip_markup(cues_of(r["song"])[r["cue"]].content)
        m = list(PAREN_RE.finditer(text))[r["group"]]
        before, after = text[: m.start()].strip(), text[m.end() :].strip()
        where["start" if not before else "end" if not after else "middle"] += 1
        if m.start() > 0 and not text[m.start() - 1].isspace():
            glued[f"before {text[m.start() - 1]!r}"] += 1
        if m.end() < len(text) and not text[m.end()].isspace():
            glued[f"after {text[m.end()]!r}"] += 1
    print(f"inline groups kept by position: {dict(where)}; glued to a neighbour: {dict(glued)}")

    paren_only = {
        (r["song"], r["cue"]): (r["start"], r["end"]) for r in keep if r["kind"] == "paren_only"
    }
    fall = Counter()
    for song, cue in paren_only:
        cues = cues_of(song)
        cleaned = clean_cue_texts([c.content for c in cues])
        spans = [
            (c.start.total_seconds(), c.end.total_seconds()) for c, t in zip(cues, cleaned) if t
        ]
        n = len(segment_by_gaps(spans)) - len(
            segment_by_gaps(sorted(spans + [paren_only[(song, cue)]]))
        )
        # n is sections lost: -1 a section of its own, 1 two merged; -2 a cap split moved.
        label = {-1: "own section", 0: "joins one", 1: "merges two"}.get(n, f"{-n} more sections")
        fall[label] += 1
    print(f"paren-only cues kept {len(paren_only)}, re-sectioned with them: {dict(fall)}")

    mutual = 0
    by_song: dict[str, list] = {}
    for (song, cue), span in paren_only.items():
        by_song.setdefault(song, []).append((cue, span))
    for spans in by_song.values():
        spans.sort()
        mutual += sum(
            min(a[1], b[1]) - max(a[0], b[0]) > 0 for (_, a), (_, b) in zip(spans, spans[1:])
        )
    print(f"kept paren-only cues overlapping each other: {mutual}")

    touched = {r["song"] for r in keep}
    resect = sum(bool(bundle_of(s)["joint_stats"].get("resectioned")) for s in touched)
    print(f"songs with a keep {len(touched)}, re-sectioned among them {resect}")
    evidence = Counter(
        "heard" if r["kept"]["consume none"] else "vocable" if r["vocable"] else "consistency"
        for r in keep
    )
    print(f"evidence: {dict(evidence)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
