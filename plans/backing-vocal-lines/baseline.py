"""Phase 0 step 5: today's timings and rescue status of every line a kept parenthetical could
touch, for Phase 2 to diff against.

    PYTHONPATH=. python plans/backing-vocal-lines/baseline.py ~/pikaraoke-songs plans/backing-vocal-lines/out

Lines covered: every line with a `sung` or `unsure` inline parenthetical (it would gain words),
and every line in the same section as such a line or as a `sung`/`unsure` paren-only cue (one
that would be added; its section is found by inserting its span and re-sectioning). That is a
superset of what any heard-test variant keeps: none keeps a labelled direction.
Writes out/baseline.json (timings and line ids only, no lyric text).
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from pikaraoke.lib.cue_align import segment_by_gaps

TAG_RE = re.compile(r"\{\\(kf|k)(\d+)\}")
TIME_RE = re.compile(r"(\d+):(\d+):(\d+\.\d+)")


def ass_words(path: Path) -> list[list[tuple[float, float]]]:
    """Each Dialogue's word (start, end), in file order, from its \\k gaps and \\kf words."""
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        fields = raw.split(",", 9)
        h, m, s = TIME_RE.match(fields[1]).groups()
        t = int(h) * 3600 + int(m) * 60 + float(s)
        words = []
        for kind, cs in TAG_RE.findall(fields[9]):
            d = int(cs) / 100
            if kind == "kf":
                words.append((round(t, 2), round(t + d, 2)))
            t += d
        lines.append(words)
    return lines


def sections_of(spans: list[list[float]], duration: float) -> list[tuple[int, int]]:
    return [
        (s.lid_lo, s.lid_hi) for s in segment_by_gaps([tuple(x) for x in spans], duration=duration)
    ]


def mates(sections: list[tuple[int, int]], lid: int) -> list[int]:
    return next(list(range(lo, hi + 1)) for lo, hi in sections if lo <= lid <= hi)


def main(lib: Path, out: Path) -> None:
    rows = [
        r for r in json.loads((out / "heard.json").read_text()) if r["label"] in ("sung", "unsure")
    ]
    songs = {s["key"]: s for s in json.loads((out / "songs.json").read_text())}
    by_song = defaultdict(list)
    for r in rows:
        by_song[r["song"]].append(r)
    result = {}
    for key, rs in sorted(by_song.items()):
        song = songs[key]
        b = json.loads((lib / "alignment_debug" / song["bundle"]).read_text())
        spans = b["cue_inputs"]["spans"]
        duration = b["media_duration_s"]
        sections = sections_of(spans, duration)
        shift = b["joint_stats"]["offset_s"] if b["joint_stats"]["resectioned"] else 0.0
        roles: dict[int, set[str]] = defaultdict(set)
        added = []
        for r in rs:
            if r["kind"] == "inline":
                roles[r["line_id"]].add("gains")
                for lid in mates(sections, r["line_id"]):
                    if lid != r["line_id"]:
                        roles[lid].add("mate_of_gain")
            else:
                # Insert the cue after its previous line and re-section.
                pos = 0 if r["prev_line"] is None else r["prev_line"] + 1
                new = (
                    spans[:pos]
                    + [[max(0.0, r["start"] + shift), max(0.0, r["end"] + shift)]]
                    + spans[pos:]
                )
                new_sections = sections_of(new, duration)
                mate_ids = [lid - (lid > pos) for lid in mates(new_sections, pos) if lid != pos]
                added.append(
                    {"cue": r["cue"], "after_line": r["prev_line"], "section_mates": mate_ids}
                )
                for lid in mate_ids:
                    roles[lid].add("mate_of_added")
        rep = b["joint_stats"]["repace"]
        snap = b["joint_stats"].get("edge_snap") or {}
        onset = {s["line_id"]: s["shift_s"] for s in (snap.get("onset") or {}).get("snaps", [])}
        extends = defaultdict(list)
        for e in (snap.get("end") or {}).get("extends", []):
            extends[e["line_id"]].append(e)
        timing = {t["line_id"]: t for t in b["output_line_timings"]}
        section_words = {o["line_id"]: o for o in b["cue_inputs"]["sections"]}
        ass_path = lib / "karaoke" / song["bundle"].replace(".json", ".ass")
        dialogues = ass_words(ass_path) if ass_path.exists() else []
        shown = [lid for lid in sorted(timing) if timing[lid]["n_words"]]
        ass_ok = len(dialogues) == len(shown) and all(
            d and abs(d[0][0] - timing[lid]["start"]) <= 0.011 for d, lid in zip(dialogues, shown)
        )
        final_words = dict(zip(shown, dialogues)) if ass_ok else {}
        lines = {}
        for lid in sorted(roles):
            sw = section_words.get(lid) or {}
            lines[lid] = {
                "roles": sorted(roles[lid]),
                "section": next([lo, hi] for lo, hi in sections if lo <= lid <= hi),
                "start": timing[lid]["start"],
                "end": timing[lid]["end"],
                "n_words": timing[lid]["n_words"],
                "final_words": final_words.get(lid),
                "section_words": [[w["start"], w["end"]] for w in sw.get("words", [])],
                "source": sw.get("source"),
                "realigned": lid in rep.get("realigned_line_ids", []),
                "repaced": lid in rep.get("repaced_line_ids", []),
                "guessed_words": lid in rep.get("guessed_word_line_ids", []),
                "crammed": lid in rep.get("crammed_line_ids", []),
                "widened": lid in rep.get("windows_widened_line_ids", []),
                "onset_snap_s": onset.get(lid),
                "end_extends": [[e["word_idx"], e.get("extend_s")] for e in extends[lid]],
            }
        result[key] = {
            "bundle": song["bundle"],
            "captured_at": b["captured_at"],
            "origin": song["origin"],
            "n_sections_bundle": b["joint_stats"]["n_sections"],
            "n_sections_recomputed": len(sections),
            "ass_words_match": ass_ok,
            "added": added,
            "lines": lines,
        }
    (out / "baseline.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
