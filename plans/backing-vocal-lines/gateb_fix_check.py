"""GATE B fix check for ``ru0K8uYEZWw`` (plan "The fix", Results row 24). Read-only.

From the worktree root, after the fix replay in ``~/probes/backing_vocal_lines_gateb_fix``::

    PYTHONPATH=.:plans/backing-vocal-lines python plans/backing-vocal-lines/gateb_fix_check.py

Compares three sides of one song, Phase 2 before, Phase 2 after and the fix run, on the after
run's new line ids, and prints one JSON document: line 91 against its cue, the line before it,
the sung-time overlaps, every line whose word times differ between Phase 2 after and the fix,
B2's counts against before, and the rescue lists and aligner failures of each run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import phase2_report as pr

HOME = Path.home()
P2 = HOME / "probes/backing_vocal_lines_phase2"
FIX = HOME / "probes/backing_vocal_lines_gateb_fix"
STEM = (
    "Justin Timberlake - CAN'T STOP THE FEELING! (from DreamWorks Animation's 'TROLLS') "
    "(Official Video)---ru0K8uYEZWw"
)
LINE = 91
PREV_OLD = 86

sides = {
    "p2_before": pr.Side(P2 / "before", STEM),
    "p2_after": pr.Side(P2 / "after", STEM),
    "fix": pr.Side(FIX / "after", STEM),
}
notes = {
    "p2_before": pr.parse_logs(P2 / "logs", "before")[STEM],
    "p2_after": pr.parse_logs(P2 / "logs", "after")[STEM],
    "fix": pr.parse_logs(FIX / "logs", "after")[STEM],
}
for name, s in sides.items():
    assert s.ass_ok, f"{name}: .ass does not match the bundle"

out: dict = {}
pa, fx, pb = sides["p2_after"], sides["fix"], sides["p2_before"]

# 0. Same inputs? (the replay transcribes again)
out["same_inputs"] = {
    "old_line_ids": pa.old_ids == fx.old_ids,
    "backing_groups": pa.backing["groups"] == fx.backing["groups"],
    "aligned_sections": pa.backing["aligned_sections"] == fx.backing["aligned_sections"],
    "transcribe_words": pa.bundle["transcribe_words"] == fx.bundle["transcribe_words"],
    "lyrics": pa.bundle["lyrics"] == fx.bundle["lyrics"],
    "cue_spans": pa.bundle["cue_inputs"]["spans"] == fx.bundle["cue_inputs"]["spans"],
    "rescue_offset": [
        pa.bundle["cue_inputs"]["rescue_offset"],
        fx.bundle["cue_inputs"]["rescue_offset"],
    ],
    "first_pass_sections": pa.bundle["cue_inputs"]["sections"] == fx.bundle["cue_inputs"]["sections"],
    "bundle_json_diff_paths": [
        d
        for d in pr.json_diff(pa.bundle, fx.bundle)
        if not d.startswith("/output_") and not d.startswith("/joint_stats/")
    ][:25],
}

# 1. Line 91
cue = fx.bundle["cue_inputs"]["spans"][LINE]
off = fx.bundle["cue_inputs"]["rescue_offset"]
c0, c1 = cue[0] + off, cue[1] + off
row = {"text": fx.text(LINE), "cue": cue, "offset": off, "audio_cue": [round(c0, 3), round(c1, 3)]}
for name, s in sides.items():
    ln = s.lines.get(LINE)
    kind = (
        "cue_align_line"
        if LINE in s.steps["realigned_line_ids"]
        else "cue_align_fill" if LINE in s.steps["repaced_line_ids"] else "other"
    )
    realigns = [r for r in s.bundle["cue_inputs"]["realigns"] if r["line_id"] == LINE]
    row[name] = {
        "words": ln.words if ln else None,
        "start": ln.words[0][0] if ln else None,
        "end": ln.words[-1][1] if ln else None,
        "source": kind,
        "heard_aimed": LINE in s.steps["heard_aimed_line_ids"],
        "heard_aimed_kept": LINE in s.steps["heard_aimed_kept_line_ids"],
        "widened": LINE in s.steps["windows_widened_line_ids"],
        "unmeasured": LINE in s.steps["windows_unmeasured_line_ids"],
        "guard_lifted": LINE in s.steps["guard_lifted_line_ids"],
        "n_guessed": len(notes[name]["guessed"].get("tokens", {}).get(LINE, [])),
        "retries": [
            {
                "w0": round(r["w0"], 2),
                "w1": round(r["w1"], 2),
                "raw": None
                if r["words"] is None
                else [[w["word"], round(w["start"], 2), round(w["end"], 2)] for w in r["words"]],
            }
            for r in realigns
        ],
        "bounds": [d for d in notes[name]["bounds"] if d["line_id"] == LINE],
        "aimed_notes": [d for d in notes[name]["aimed"] if d["line_id"] == LINE],
    }
    if ln:
        s0, e0 = row[name]["start"], row[name]["end"]
        row[name]["start_vs_cue_start_plus_lead"] = round(s0 - c0, 2)
        row[name]["end_vs_cue_end_plus_lead"] = round(e0 - c1, 2)
        row[name]["on_cue"] = bool(s0 >= c0 - 0.5 and e0 <= c1)
out["line91"] = row

# 2. old line 86 (old id) -> new id
prev = {}
for name, s in sides.items():
    new = s.new_of_old[PREV_OLD]
    ln = s.lines[new]
    toks = notes[name]["guessed"].get("tokens", {}).get(new, [])
    prev[name] = {
        "new_id": new,
        "text": s.text(new),
        "start": ln.words[0][0],
        "last_end": ln.words[-1][1],
        "last_word": ln.words[-1][2],
        "guessed_token_idx": toks,
        "first_two_guessed": 0 in toks and 1 in toks,
        "first_words": ln.words[:3],
    }
out["old_line_86"] = prev

# 3. Sung-time overlaps
def sung(s, a, b):
    la, lb = s.lines.get(a), s.lines.get(b)
    if not la or not lb:
        return None
    sa, ea, sb, eb = la.words[0][0], la.words[-1][1], lb.words[0][0], lb.words[-1][1]
    return round(min(ea, eb) - max(sa, sb), 2)


out["overlap_sung"] = {
    f"{a}/{b}": {name: sung(s, a, b) for name, s in sides.items()}
    for a, b in ((91, 93), (91, 94), (93, 94))
}
out["overlap_sung_text"] = {i: fx.text(i) for i in (91, 92, 93, 94)}

# 4. Every line whose word times differ, P2 after vs fix
def memberships(s, lid):
    return [n.removesuffix("_line_ids") for n in pr.STEPS if lid in s.steps[n]]


def src(s, lid):
    return (
        "cue_align_line"
        if lid in s.steps["realigned_line_ids"]
        else "cue_align_fill" if lid in s.steps["repaced_line_ids"] else "section/other"
    )


diff = []
for lid in range(fx.n_lines):
    a, b = pa.lines.get(lid), fx.lines.get(lid)
    if (a is None) != (b is None):
        diff.append({"line": lid, "kind": "shown on one side only", "p2_after": a is not None})
        continue
    if a is None:
        continue
    if len(a.words) != len(b.words):
        diff.append({"line": lid, "kind": "word count", "n": [len(a.words), len(b.words)]})
        continue
    mv = [
        (round(y[0] - x[0], 2), round(y[1] - x[1], 2))
        for x, y in zip(a.words, b.words)
        if abs(y[0] - x[0]) > pr.SAME_S or abs(y[1] - x[1]) > pr.SAME_S
    ]
    if mv:
        diff.append(
            {
                "line": lid,
                "old": fx.old_ids[lid],
                "text": fx.text(lid),
                "n_words_moved": len(mv),
                "max_move": max(max(abs(x), abs(y)) for x, y in mv),
                "p2_after": {
                    "span": [a.words[0][0], a.words[-1][1]],
                    "source": src(pa, lid),
                    "lists": memberships(pa, lid),
                },
                "fix": {
                    "span": [b.words[0][0], b.words[-1][1]],
                    "source": src(fx, lid),
                    "lists": memberships(fx, lid),
                },
            }
        )
out["lines_differing_p2_after_vs_fix"] = diff

# 5. B2 against P2 before for old lines (fix), and p2 after for reference
def b2_groups(before, after, an_notes):
    an = pr.Analysis(
        {"key": "ru0K8uYEZWw"},
        before,
        after,
        pr.failed_lines(an_notes[0]["fail"]),
        pr.failed_lines(an_notes[1]["fail"]),
        an_notes[0],
        an_notes[1],
    )
    ws = pr.b2(an)
    res = {"mismatch": [w for w in ws if "mismatch" in w]}
    good = [w for w in ws if "mismatch" not in w]
    for g in ("gained", "middle", "other"):
        gw = [w for w in good if w["group"] == g]
        res[g] = {
            "words": len(gw),
            "lines": len({w["old"] for w in gw}),
            "moved_any": sum(1 for w in gw if pr.moved(w) > pr.SAME_S),
            "moved_far": sum(1 for w in gw if pr.moved(w) > pr.MOVED_S),
            "lines_moved_far": len({w["old"] for w in gw if pr.moved(w) > pr.MOVED_S}),
        }
    res["other_moves"] = [
        {"old": w["old"], "new": w["new"], "word": w["text"], "ds": w["ds"], "de": w["de"]}
        for w in good
        if w["group"] == "other" and pr.moved(w) > pr.SAME_S
    ]
    return res, good


b2_fix, good_fix = b2_groups(pb, fx, (notes["p2_before"], notes["fix"]))
b2_p2a, good_p2a = b2_groups(pb, pa, (notes["p2_before"], notes["p2_after"]))
out["b2_fix_vs_before"] = b2_fix
out["b2_p2after_vs_before"] = b2_p2a
# Which old words moved far differently between p2 after and fix, by old line
far_fix = {(w["old"], w["word"]): w for w in good_fix if pr.moved(w) > pr.MOVED_S}
far_p2a = {(w["old"], w["word"]): w for w in good_p2a if pr.moved(w) > pr.MOVED_S}
out["far_moved_only_p2after"] = sorted({k[0] for k in far_p2a if k not in far_fix})
out["far_moved_only_fix"] = sorted({k[0] for k in far_fix if k not in far_p2a})

# 6. The runs' lists and failures
def fails(name):
    lines, secs = pr.failed_lines(notes[name]["fail"])
    return {"line_retries": sorted(lines), "sections": sorted(secs), "raw": notes[name]["fail"]}


out["run_lists"] = {
    name: {
        "heard_aimed_line_ids": sorted(s.steps["heard_aimed_line_ids"]),
        "heard_aimed_kept_line_ids": sorted(s.steps["heard_aimed_kept_line_ids"]),
        "repaced_line_ids": sorted(s.steps["repaced_line_ids"]),
        "realigned_n": len(s.steps["realigned_line_ids"]),
        "n_guessed_words": s.rescue.get("n_guessed_words"),
        "failures": fails(name),
    }
    for name, s in sides.items()
}
out["added_lines"] = {
    "ids": fx.added(),
    "texts": {i: fx.text(i) for i in fx.added()},
}
out["added_line_end_state"] = {
    name: {
        i: (
            "heard-aimed kept"
            if i in s.steps["heard_aimed_kept_line_ids"]
            else src(s, i)
            if i in s.lines
            else "not shown"
        )
        for i in fx.added()
    }
    for name, s in sides.items()
    if name != "p2_before"
}

json.dump(out, sys.stdout, indent=1, default=list)
