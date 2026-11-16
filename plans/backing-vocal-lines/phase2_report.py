"""Phase 2 report: GATE B's B1-B6 and the D7 amendment's "For Phase 2" list. Read-only.

    PYTHONPATH=. python plans/backing-vocal-lines/phase2_report.py ~/pikaraoke-songs <scratch> plans/backing-vocal-lines/out

Reads the songs of out/phase2_songs.json from ``<scratch>/before`` and ``<scratch>/after`` (their
bundles, ``karaoke/*.ass`` and the run logs in ``<scratch>/logs``) and writes out/phase2_report.md
and out/phase2_details.json. The library is only used to tell a song that was run from one that
was not (its bundle's ``captured_at`` differs from the library's).

Word times come from the ``.ass`` (centiseconds): the bundle holds none for a cue song. A word
counts as moved when a time differs by more than 0.011 s, and as moved far at 0.3 s (B2). Evidence
the bundle does not keep comes from the ``PHASE2`` lines ``phase2_run.py`` logs: the words each
line had guessed, why a retry's start moved, rule B's shifts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from phase2_replay import kept_groups

from pikaraoke.lib.heard_lines import heard_lines, runs_heard
from pikaraoke.lib.joint_match import _tokenise_lines
from pikaraoke.lib.library_status import POOR_GUESSED_SHARE, song_status
from pikaraoke.lib.token_align import INSTANT_WORD_DUR_S

MOVED_S = 0.3  # the onset probe's threshold, B2
SAME_S = 0.011  # the .ass keeps centiseconds
B4_MIN_SHARE = 0.8
KEPT = ("heard", "vocable", "consistency")
BINS = (SAME_S, 0.05, 0.1, 0.3, 1.0, 3.0)
BIN_LABELS = ("same", "<=0.05", "<=0.1", "<=0.3", "<=1", "<=3", ">3")
STEPS = (
    "realigned_line_ids",
    "repaced_line_ids",
    "guessed_word_line_ids",
    "crammed_line_ids",
    "windows_widened_line_ids",
    "windows_unmeasured_line_ids",
    "heard_kept_line_ids",
    "guard_lifted_line_ids",
    "heard_aimed_line_ids",
    "heard_aimed_kept_line_ids",
)
MEMBERSHIP = (
    "heard_kept_line_ids",
    "heard_aimed_line_ids",
    "heard_aimed_kept_line_ids",
    "guard_lifted_line_ids",
)

TAG_RE = re.compile(r"\{\\(kf|k)(\d+)\}([^{]*)")
TIME_RE = re.compile(r"(\d+):(\d+):(\d+\.\d+)")
HEADER_RE = re.compile(r"^\[(\d+)/(\d+)\] (.+?)\.(?:mp4|mkv|webm|avi|mov|m4v) — ")
MATCH_RE = re.compile(r"for joint match: (.+?)_vocal\.wav")
NOTE_RE = re.compile(r"PHASE2 (\w+) (\{.*\})\s*$")
FAIL_RE = re.compile(r"\[lyric_align\] (.+?) slice-align failed, degrading: (.*)$")
PARENS_WARN_RE = re.compile(r"show_parens: .*not its align tokens")
PAREN_RE = re.compile(r"[()]")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clock(text: str) -> float:
    h, m, s = TIME_RE.match(text).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def stamp(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:05.2f}"


def parse_ass(path: Path) -> list[dict]:
    """Each Dialogue's display window and words ``(start, end, text)``, in file order."""
    dialogues = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("Dialogue:"):
            continue
        fields = raw.split(",", 9)
        start, end = clock(fields[1]), clock(fields[2])
        t, words = start, []
        for kind, cs, text in TAG_RE.findall(fields[9]):
            d = int(cs) / 100
            if kind == "kf":
                words.append((round(t, 2), round(t + d, 2), text.strip()))
            t += d
        dialogues.append({"start": start, "end": end, "words": words})
    return dialogues


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


def parse_logs(logdir: Path, side: str) -> dict[str, dict]:
    """Per song stem: aligner failures, show_parens warnings and the PHASE2 notes of ``side``'s
    logs. The driver's header or the transcription line says which song a line belongs to; a
    later log of the same song replaces an earlier one."""
    songs: dict[str, dict] = {}
    for path in sorted(logdir.glob(f"{side}_*.log")):
        current, seen = None, {}
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
        for line in text.splitlines():
            if m := HEADER_RE.match(line):
                current = m.group(3)
            elif m := MATCH_RE.search(line):
                current = m.group(1)
            if m and current is not None:
                seen.setdefault(
                    current,
                    {"fail": [], "parens": [], "guessed": {}, "bounds": [], "aimed": []},
                )
            if current is None:
                continue
            info = seen[current]
            if m := FAIL_RE.search(line):
                info["fail"].append({"label": m.group(1), "message": m.group(2)})
            elif PARENS_WARN_RE.search(line):
                info["parens"].append(line.strip())
            elif m := NOTE_RE.search(line):
                kind, data = m.group(1), json.loads(m.group(2))
                if kind == "guessed":
                    info["guessed"] = {
                        "words": {int(k): v for k, v in data["words"].items()},
                        "tokens": {int(k): v for k, v in data["tokens"].items()},
                    }
                elif kind == "start_bounded":
                    info["bounds"].append(data)
                elif kind == "heard_aimed":
                    info["aimed"].append(data)
        songs.update(seen)
    return songs


def failed_lines(fails: list[dict]) -> tuple[set[int], set[int]]:
    """The line ids a song's aligner failures hit: ``line N`` is one retry (the rescue's own ids),
    ``section lines a-b`` a section align (today's ids)."""
    lines: set[int] = set()
    sections: set[int] = set()
    for f in fails:
        if m := re.fullmatch(r"line (\d+)", f["label"]):
            lines.add(int(m.group(1)))
        elif m := re.fullmatch(r"section lines (\d+)-(\d+)", f["label"]):
            sections.update(range(int(m.group(1)), int(m.group(2)) + 1))
    return lines, sections


# ---------------------------------------------------------------------------
# One song on one side
# ---------------------------------------------------------------------------


@dataclass
class Line:
    id: int
    start: float
    end: float
    words: list[tuple[float, float, str]]
    dstart: float
    dend: float


@dataclass
class Side:
    folder: Path
    stem: str
    bundle: dict = field(init=False)
    lines: dict[int, Line] = field(init=False)
    ass_ok: bool = field(init=False)

    def __post_init__(self) -> None:
        self.bundle = read_json(self.folder / "alignment_debug" / f"{self.stem}.json")
        dialogues = parse_ass(self.folder / "karaoke" / f"{self.stem}.ass")
        timings = self.bundle["output_line_timings"]
        shown = [t for t in timings if t["n_words"]]
        self.ass_ok = len(shown) == len(dialogues) and all(
            len(d["words"]) == t["n_words"] for d, t in zip(dialogues, shown)
        )
        self.lines = {
            t["line_id"]: Line(t["line_id"], t["start"], t["end"], d["words"], d["start"], d["end"])
            for t, d in zip(shown, dialogues)
        }
        self.n_lines = len(timings)
        joint = self.bundle["joint_stats"]
        self.rescue = joint.get("repace") or {}
        self.backing = joint.get("backing")
        self.old_ids: list[int | None] = (self.backing or {}).get("old_line_ids") or list(
            range(self.n_lines)
        )
        self.new_of_old = {o: n for n, o in enumerate(self.old_ids) if o is not None}
        self.sent = [tuple(r) for r in (self.backing or {}).get("aligned_sections") or []]
        self.steps = {name: set(self.rescue.get(name, [])) for name in STEPS}
        self.kept = [
            g
            for g in (self.backing or {}).get("groups", [])
            if g["verdict"] in KEPT and g["tokens"] is not None
        ]
        self.new_idx: dict[int, set[int]] = defaultdict(set)
        for g in self.kept:
            self.new_idx[g["line_id"]].update(range(*g["tokens"]))
        snap = joint.get("edge_snap") or {}
        self.onset = {
            s["line_id"]: s["shift_s"] for s in (snap.get("onset") or {}).get("snaps", [])
        }
        self.extends: dict[int, list] = defaultdict(list)
        for e in (snap.get("end") or {}).get("extends", []):
            self.extends[e["line_id"]].append((e["word_idx"], e.get("extend_s")))
        self.first_pass = {
            o["line_id"]: [(w["start"], w["end"]) for w in o["words"]]
            for o in (self.bundle.get("cue_inputs") or {}).get("sections", [])
        }

    def heard(self) -> tuple[list, list[bool]]:
        """Which lines the transcriber heard, as the rescue finds out, and their runs."""
        b = self.bundle
        spans = b["cue_inputs"]["spans"]
        offset = b["cue_inputs"].get("rescue_offset")
        if offset is None:
            offset = self.rescue["offset_s"]
        audio = [(c0 + offset, c1 + offset) for c0, c1 in spans]
        align = b["lyrics"]["align_lines"]
        found = heard_lines(align, audio, b["transcribe_words"])
        return found, runs_heard(_tokenise_lines(align), found)

    def added(self) -> list[int]:
        return [n for n, o in enumerate(self.old_ids) if o is None]

    def text(self, lid: int) -> str:
        return self.bundle["lyrics"]["lines"][lid]

    def prev_with_words(self, lid: int) -> Line | None:
        return next((self.lines[n] for n in range(lid - 1, -1, -1) if n in self.lines), None)

    def next_with_words(self, lid: int) -> Line | None:
        return next((self.lines[n] for n in range(lid + 1, self.n_lines) if n in self.lines), None)


def zero_len(word: tuple[float, float, str]) -> bool:
    return word[1] - word[0] < INSTANT_WORD_DUR_S - 1e-9


def old_words(side: Side, new: int) -> list[tuple[float, float, str]]:
    """The words of line ``new`` that are not a kept group's."""
    line = side.lines.get(new)
    if line is None:
        return []
    skip = side.new_idx.get(new, set())
    return [w for i, w in enumerate(line.words) if i not in skip]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def json_diff(a, b, path="") -> list[str]:
    """The paths where two JSON values differ (``captured_at`` aside)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k == "captured_at" and not path:
                continue
            if k not in a or k not in b:
                out.append(f"{path}/{k} (only in {'before' if k in a else 'after'})")
            else:
                out += json_diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path} (length {len(a)} vs {len(b)})"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += json_diff(x, y, f"{path}[{i}]")
            if len(out) > 20:
                break
        return out
    return [] if a == b else [path]


def owned(folder: Path, stem: str) -> dict[str, Path]:
    files = {}
    for sub in ("karaoke", "lyrics", "subtitles"):
        if (folder / sub).is_dir():
            for p in sorted((folder / sub).iterdir()):
                if p.is_file() and (
                    p.name.startswith(stem + ".") or p.name.startswith(stem + "---")
                ):
                    files[f"{sub}/{p.name}"] = p
    return files


def b1(scratch: Path, rows: list[dict]) -> list[dict]:
    """The control songs, before against after: every output file and the whole bundle."""
    out = []
    for row in rows:
        stem = row["stem"]
        diffs = []
        b_files, a_files = owned(scratch / "before", stem), owned(scratch / "after", stem)
        for name in sorted(set(b_files) | set(a_files)):
            if name not in b_files or name not in a_files:
                diffs.append(f"{name}: only in {'before' if name in b_files else 'after'}")
            elif b_files[name].read_bytes() != a_files[name].read_bytes():
                diffs.append(f"{name}: bytes differ")
        bundles = [
            read_json(scratch / side / "alignment_debug" / f"{stem}.json")
            for side in ("before", "after")
        ]
        # The bundle records where the model file was loaded from, which is each worktree's own
        # models/ link: where the trees live, not what they do. Shown, not counted.
        paths = [b["config"]["whisper"]["load_model"].pop("model_path", None) for b in bundles]
        diffs += [f"bundle {d}" for d in json_diff(*bundles)]
        out.append(
            {
                "key": row["key"],
                "stem": stem,
                "files": len(a_files),
                "diffs": diffs,
                "model_paths": paths,
            }
        )
    return out


def bin_of(x: float) -> int:
    return next((i for i, edge in enumerate(BINS) if x <= edge), len(BINS))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


@dataclass
class Analysis:
    row: dict
    before: Side
    after: Side
    fails_before: tuple[set[int], set[int]]
    fails_after: tuple[set[int], set[int]]
    notes_before: dict
    notes_after: dict

    def group(self, new: int) -> str:
        a = self.after
        old = a.old_ids[new]
        if old is None:
            return "added"
        if new in a.new_idx:
            return "gained"
        changed = set(a.new_idx) | set(a.added())
        in_sent = any(lo <= new <= hi for lo, hi in a.sent)
        near = (new - 1 in changed) or (new + 1 in changed)
        return "middle" if in_sent or near else "other"

    def failure(self, old: int) -> str:
        """Whether an aligner failure hit old line ``old``, in the before run, the after run."""
        new = self.after.new_of_old.get(old)
        tags = []
        if old in self.fails_before[0] | self.fails_before[1]:
            tags.append("before")
        if new in self.fails_after[0] or old in self.fails_after[1]:
            tags.append("after")
        return "+".join(tags)


def b2(an: Analysis) -> list[dict]:
    """Every old word with its move, group and line."""
    out = []
    b, a = an.before, an.after
    for old, bl in b.lines.items():
        new = a.new_of_old.get(old)
        if new is None:
            continue
        aw = old_words(a, new)
        if len(aw) != len(bl.words):
            out.append({"old": old, "new": new, "mismatch": (len(bl.words), len(aw))})
            continue
        group = an.group(new)
        for i, (bw, w) in enumerate(zip(bl.words, aw)):
            out.append(
                {
                    "old": old,
                    "new": new,
                    "word": i,
                    "text": bw[2],
                    "group": group,
                    "ds": round(w[0] - bw[0], 3),
                    "de": round(w[1] - bw[1], 3),
                    "before": [bw[0], bw[1]],
                    "after": [w[0], w[1]],
                }
            )
    return out


def step_changes(an: Analysis, old: int) -> list[str]:
    """What differs for old line ``old`` between the runs: rescue lists, snaps, first pass."""
    b, a = an.before, an.after
    new = a.new_of_old[old]
    out = [
        f"{name.removesuffix('_line_ids')} {old in b.steps[name]}->{new in a.steps[name]}"
        for name in STEPS
        if (old in b.steps[name]) != (new in a.steps[name])
    ]
    if b.onset.get(old) != a.onset.get(new):
        out.append(f"onset snap {b.onset.get(old)}->{a.onset.get(new)}")
    if b.extends.get(old, []) != a.extends.get(new, []):
        out.append(f"end extends {b.extends.get(old, [])}->{a.extends.get(new, [])}")
    if b.first_pass.get(old) != a.first_pass.get(new):
        out.append("first-pass words differ")
    return out


def guessed_counts(side: Side, notes: dict) -> tuple[dict[int, int], dict[int, list[int]]]:
    g = notes.get("guessed") or {}
    return g.get("words", {}), g.get("tokens", {})


def b3(an: Analysis) -> dict:
    """Rescue counts on old lines, before and after, with each increase."""
    b, a = an.before, an.after
    gb_words, gb_tokens = guessed_counts(b, an.notes_before)
    ga_words, ga_tokens = guessed_counts(a, an.notes_after)
    counts = Counter()
    increases = []
    for old in range(b.n_lines):
        new = a.new_of_old.get(old)
        if new is None:
            continue
        bl, al = b.lines.get(old), a.lines.get(new)
        skip = a.new_idx.get(new, set())
        cells = {
            "realigned": (
                old in b.steps["realigned_line_ids"],
                new in a.steps["realigned_line_ids"],
            ),
            "paced": (old in b.steps["repaced_line_ids"], new in a.steps["repaced_line_ids"]),
            "guessed_lines": (
                old in b.steps["guessed_word_line_ids"],
                new in a.steps["guessed_word_line_ids"],
            ),
            "guessed_lines_old": (
                bool(gb_tokens.get(old)),
                bool([i for i in ga_tokens.get(new, []) if i not in skip]),
            ),
            "guessed_words": (
                gb_words.get(old, 0),
                len([i for i in ga_tokens.get(new, []) if i not in skip]),
            ),
            "zero_length": (
                sum(zero_len(w) for w in bl.words) if bl else 0,
                sum(zero_len(w) for w in old_words(a, new)) if al else 0,
            ),
        }
        for name, (x, y) in cells.items():
            counts[f"{name} before"] += int(x)
            counts[f"{name} after"] += int(y)
            if int(y) > int(x):
                increases.append(
                    {
                        "kind": name,
                        "old": old,
                        "new": new,
                        "before": int(x),
                        "after": int(y),
                        "group": an.group(new),
                        "aligner_failure": an.failure(old),
                        "changed": step_changes(an, old),
                    }
                )
    return {"counts": dict(counts), "increases": increases}


def b4(an: Analysis) -> dict:
    """Share of the kept words with measured timing, inline echo words and added-line words apart."""
    a = an.after
    _, tokens = guessed_counts(a, an.notes_after)
    result = {"inline": Counter(), "added": Counter()}
    for new, idx in a.new_idx.items():
        line = a.lines.get(new)
        kind = "added" if a.old_ids[new] is None else "inline"
        paced = new in a.steps["repaced_line_ids"]
        for i in sorted(idx):
            if line is None or i >= len(line.words):
                result[kind]["no word"] += 1
                continue
            why = (
                "paced"
                if paced
                else (
                    "guessed"
                    if i in tokens.get(new, [])
                    else "zero-length" if zero_len(line.words[i]) else "measured"
                )
            )
            result[kind][why] += 1
            result[kind]["words"] += 1
    return {k: dict(v) for k, v in result.items()}


def overlaps(side: Side) -> set[tuple[int, int]]:
    """Pairs of lines whose display windows overlap, by the lines' ids on that side."""
    items = sorted(side.lines.values(), key=lambda line: line.dstart)
    pairs = set()
    for i, x in enumerate(items):
        for y in items[i + 1 :]:
            if y.dstart >= x.dend:
                break
            pairs.add((min(x.id, y.id), max(x.id, y.id)))
    return pairs


def b5(an: Analysis) -> dict:
    """Display-window pairs that overlap after and did not before (old lines), and the pairs an
    added line is in."""
    b, a = an.before, an.after
    before_pairs = overlaps(b)
    new_old_pairs, added_pairs = [], []
    for x, y in sorted(overlaps(a)):
        ox, oy = a.old_ids[x], a.old_ids[y]
        if ox is None or oy is None:
            added_pairs.append((x, y))
        elif (min(ox, oy), max(ox, oy)) not in before_pairs:
            new_old_pairs.append((ox, oy, x, y))
    return {"new_old_pairs": new_old_pairs, "added_pairs": added_pairs}


def b6(an: Analysis) -> dict:
    """A Genius or custom song: every word's times, and the words whose text differs."""
    b, a = an.before, an.after
    out = {"lines_equal": b.bundle["output_line_timings"] == a.bundle["output_line_timings"]}
    bw, aw = b.bundle.get("words") or [], a.bundle.get("words") or []
    out["bundle_words"] = [len(bw), len(aw)]
    out["bundle_times_equal"] = len(bw) == len(aw) and all(
        (x["start"], x["end"]) == (y["start"], y["end"]) for x, y in zip(bw, aw)
    )
    ass_b = [w for ln in sorted(b.lines) for w in b.lines[ln].words]
    ass_a = [w for ln in sorted(a.lines) for w in a.lines[ln].words]
    out["ass_words"] = [len(ass_b), len(ass_a)]
    out["ass_times_equal"] = len(ass_b) == len(ass_a) and all(
        x[:2] == y[:2] for x, y in zip(ass_b, ass_a)
    )
    changed = [(x[2], y[2]) for x, y in zip(ass_b, ass_a) if x[2] != y[2]]
    out["text_changed"] = len(changed)
    out["only_parens"] = sum(1 for x, y in changed if PAREN_RE.sub("", y) == PAREN_RE.sub("", x))
    out["other_text"] = [(x, y) for x, y in changed if PAREN_RE.sub("", y) != PAREN_RE.sub("", x)][
        :10
    ]
    out["samples"] = changed[:5]
    out["parens_warnings"] = an.notes_after.get("parens", [])
    return out


def added_rows(an: Analysis) -> list[dict]:
    """The amendment's per-added-line record."""
    a = an.after
    _, tokens = guessed_counts(a, an.notes_after)
    heard, _ = a.heard()
    rows = []
    for new in a.added():
        line = a.lines.get(new)
        ended = (
            "heard-aimed, kept"
            if new in a.steps["heard_aimed_kept_line_ids"]
            else (
                "re-aligned"
                if new in a.steps["realigned_line_ids"]
                else (
                    "paced"
                    if new in a.steps["repaced_line_ids"]
                    else "not shown" if line is None else "other"
                )
            )
        )
        retries = [
            {
                "window": [round(r["w0"], 2), round(r["w1"], 2)],
                "raw": (
                    None
                    if r["words"] is None
                    else [[w["word"], round(w["start"], 2), round(w["end"], 2)] for w in r["words"]]
                ),
            }
            for r in a.bundle["cue_inputs"]["realigns"]
            if r["line_id"] == new
        ]
        bounds = [d for d in an.notes_after.get("bounds", []) if d["line_id"] == new]
        prev, nxt = a.prev_with_words(new), a.next_with_words(new)
        row = {
            "new": new,
            "text": a.text(new),
            "ended": ended,
            "guessed": len(tokens.get(new, [])),
            "words": len(line.words) if line else 0,
            "retries": retries,
            "heard_aim_tried": new in a.steps["heard_aimed_line_ids"],
            "aligner_failure": new in an.fails_after[0],
            "lifted": new in a.steps["guard_lifted_line_ids"],
            "bounds": bounds,
            "cut_to_previous_end": any(
                d["start"] is not None
                and d["raw_start"] is not None
                and d["raw_start"] < d["bound"] - SAME_S
                and abs(d["start"] - d["bound"]) <= SAME_S
                for d in bounds
            ),
            "onset_snap": a.onset.get(new),
            "heard": heard[new] is not None,
        }
        if line:
            row["start"], row["end"] = line.words[0][0], line.words[-1][1]
            row["prev_overlap_words"] = (
                None if prev is None else round(prev.words[-1][1] - row["start"], 2)
            )
            row["next_overlap_words"] = (
                None if nxt is None else round(row["end"] - nxt.words[0][0], 2)
            )
            row["prev_overlap_window"] = None if prev is None else round(prev.dend - line.dstart, 2)
            row["next_overlap_window"] = None if nxt is None else round(line.dend - nxt.dstart, 2)
        before_prev = a.old_ids[prev.id] if prev else None
        if prev and before_prev is not None and before_prev in an.before.lines:
            row["prev_last_end"] = [an.before.lines[before_prev].words[-1][1], prev.words[-1][1]]
        rows.append(row)
    return rows


def aimed_rows(an: Analysis) -> list[dict]:
    """Every heard-aimed try on an added or gaining line, with its shift and what sits there."""
    a = an.after
    heard, _ = a.heard()
    offset = a.bundle["cue_inputs"].get("rescue_offset") or a.rescue["offset_s"]
    rows = []
    interesting = set(a.added()) | set(a.new_idx)
    for new in sorted(a.steps["heard_aimed_line_ids"] & interesting):
        c0 = a.bundle["cue_inputs"]["spans"][new][0] + offset
        shift = heard[new].start - c0 if heard[new] else None
        tried = [r for r in a.bundle["cue_inputs"]["realigns"] if r["line_id"] == new]
        line = a.lines.get(new)
        kept = new in a.steps["heard_aimed_kept_line_ids"]
        lo, hi = (
            (line.words[0][0], line.words[-1][1])
            if line and kept
            else ((tried[0]["w0"], tried[0]["w1"]) if tried else (0.0, 0.0))
        )
        sits = [
            {
                "line": n,
                "old": a.old_ids[n],
                "text": a.text(n)[:40],
                "overlap": round(min(hi, o.words[-1][1]) - max(lo, o.words[0][0]), 2),
            }
            for n, o in a.lines.items()
            if n != new and min(hi, o.words[-1][1]) > max(lo, o.words[0][0])
        ]
        rows.append(
            {
                "new": new,
                "kind": "added" if a.old_ids[new] is None else "gaining",
                "kept": kept,
                "shift": None if shift is None else round(shift, 2),
                "logged": [d for d in an.notes_after.get("aimed", []) if d["line_id"] == new],
                "window": [round(lo, 2), round(hi, 2)],
                "sits_on": sits,
            }
        )
    return rows


def membership_rows(an: Analysis) -> list[dict]:
    """Old lines whose membership of the four rescue lists changed, or whose heard status did."""
    b, a = an.before, an.after
    hb, rb = b.heard()
    ha, ra = a.heard()
    rows = []
    for old in range(b.n_lines):
        new = a.new_of_old.get(old)
        if new is None:
            continue
        changes = [
            f"{name.removesuffix('_line_ids')} {old in b.steps[name]}->{new in a.steps[name]}"
            for name in MEMBERSHIP
            if (old in b.steps[name]) != (new in a.steps[name])
        ]
        for what, x, y in (
            ("heard", hb[old] is not None, ha[new] is not None),
            ("first word heard", bool(hb[old] and hb[old].first), bool(ha[new] and ha[new].first)),
            ("run heard", rb[old], ra[new]),
        ):
            if x != y:
                changes.append(f"{what} {x}->{y}")
        if changes:
            rows.append({"old": old, "new": new, "group": an.group(new), "changes": changes})
    return rows


def prev_end_rows(an: Analysis) -> list[dict]:
    """The line before each added line: its last word's end before and after."""
    a, b = an.after, an.before
    rows = []
    for new in a.added():
        prev = a.prev_with_words(new)
        old = a.old_ids[prev.id] if prev else None
        if prev is None or old is None or old not in b.lines:
            continue
        rows.append(
            {
                "added": new,
                "line_before": prev.id,
                "old": old,
                "before_end": b.lines[old].words[-1][1],
                "after_end": prev.words[-1][1],
            }
        )
    return rows


def video_in(folder: Path, stem: str) -> Path:
    return next(p for p in folder.iterdir() if p.stem == stem and p.suffix.lower() != ".json")


def share_crossing(scratch: Path, stem: str) -> dict:
    b = song_status(video_in(scratch / "before", stem))
    a = song_status(video_in(scratch / "after", stem))

    def share(s):
        return None if s.guessed is None or not s.line_count else s.guessed / s.line_count

    return {
        "before": [b.guessed, b.line_count, share(b)],
        "after": [a.guessed, a.line_count, share(a)],
        "crosses": bool(b.poor) != bool(a.poor),
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def listening_list(
    scratch: Path, analyses: list[Analysis], far: list[dict], added: list[dict], aimed: list[dict]
) -> list[dict]:
    """At most 10 spots for Ken: B2's largest moves first, then a spread of new inline and new
    paren-only lines (one per way an added line ended, and any heard-aimed keep). A new line is
    played in the after .ass only; the before .ass shows what was on screen without it."""
    by_key = {an.row["key"]: an for an in analyses}
    spots: list[dict] = []
    per_song: Counter = Counter()

    def paths(an: Analysis) -> dict:
        stem = an.row["stem"]
        return {
            "video": str(video_in(scratch / "after", stem)),
            "before_ass": str(scratch / "before" / "karaoke" / f"{stem}.ass"),
            "after_ass": str(scratch / "after" / "karaoke" / f"{stem}.ass"),
        }

    def add(an: Analysis, kind: str, t: float, what: str) -> bool:
        if len(spots) >= 10 or per_song[an.row["key"]] >= 2:
            return False
        per_song[an.row["key"]] += 1
        spots.append(
            {
                "key": an.row["key"],
                "song": an.row["stem"][:70],
                "kind": kind,
                "time": stamp(t),
                "t": t,
                "what": what,
                **paths(an),
            }
        )
        return True

    seen_lines = set()
    for w in far:
        if len([x for x in spots if x["kind"] == "old word moved"]) >= 4:
            break
        if (w["key"], w["old"]) in seen_lines:
            continue
        an = by_key[w["key"]]
        line = an.before.lines[w["old"]]
        if add(
            an,
            "old word moved",
            w["before"][0],
            f"[{w['group']}] the line that starts {' '.join(x[2] for x in line.words[:6])!r}: word {w['word']} "
            f"{w['text']!r} moves start {w['ds']:+.2f} s, end {w['de']:+.2f} s; play the before .ass at "
            f"{stamp(w['before'][0])} and the after .ass at {stamp(w['after'][0])}; aligner failure: "
            f"{an.failure(w['old']) or 'no'}",
        ):
            seen_lines.add((w["key"], w["old"]))

    by_end: dict[str, list[dict]] = defaultdict(list)
    for r in added:
        if "start" in r:
            by_end[r["ended"]].append(r)
    aimed_done = set()
    for r in aimed:
        if r["kept"] and r["sits_on"]:
            aimed_done.add((r["key"], r["new"]))
            an = by_key[r["key"]]
            line = an.after.lines.get(r["new"])
            if line:
                add(
                    an,
                    "heard-aimed keep",
                    line.words[0][0],
                    f"{r['kind']} line {r['new']} aimed {r['shift']:+.2f} s from its cue; other lines there: {[(x['line'], x['overlap']) for x in r['sits_on']]}",
                )
    for ended in ("heard-aimed, kept", "re-aligned", "paced"):
        fresh = [r for r in by_end.get(ended, []) if (r["key"], r["new"]) not in aimed_done]
        for r in fresh[:: max(1, len(fresh) // 4)] + fresh:
            if add(
                by_key[r["key"]],
                f"new paren-only line, {ended}",
                r["start"],
                f"added line {r['new']} {r['text'][:40]!r}: words {r['words']}, guessed {r['guessed']}, "
                f"overlap with line before {r.get('prev_overlap_words')} s, line after {r.get('next_overlap_words')} s",
            ):
                break
    gaining = [
        (an, n)
        for an in analyses
        for n in sorted(an.after.new_idx)
        if an.after.old_ids[n] is not None and n in an.after.lines
    ]
    for an, n in gaining[:: max(1, len(gaining) // 4)] + gaining:
        line = an.after.lines[n]
        new_words = [line.words[i][2] for i in sorted(an.after.new_idx[n]) if i < len(line.words)]
        if add(
            an,
            "new inline words",
            line.words[0][0],
            f"line {n} gains {new_words}; paced {n in an.after.steps['repaced_line_ids']}, "
            f"guessed {len(guessed_counts(an.after, an.notes_after)[1].get(n, []))}",
        ):
            break
    return spots


def paren_display(an: Analysis) -> dict:
    """Anchor check: each kept group's ``tokens`` range, read off the .ass, opens with "(" and
    closes with ")" (a one-word group has both), and no kept group is missing from the screen."""
    a = an.after
    out = Counter()
    bad = []
    for g in a.kept:
        line = a.lines.get(g["line_id"])
        first, end = g["tokens"]
        if line is None or end > len(line.words) or first >= end:
            out["no words"] += 1
            bad.append((g["cue"], g["group"], "no words"))
            continue
        opens, closes = line.words[first][2].startswith("("), line.words[end - 1][2].endswith(")")
        out["ok" if opens and closes else "no parens"] += 1
        if not (opens and closes):
            bad.append((g["cue"], g["group"], line.words[first][2], line.words[end - 1][2]))
    return {"counts": dict(out), "bad": bad}


def d8_rows(an: Analysis) -> list[dict]:
    """D8: gaining lines whose new tokens outnumber the old ones, so that with no echo word
    timed the line is under the half-the-tokens bar a kept re-align must clear. By id, with the
    evidence the judge kept the echo on and how the line ended."""
    a = an.after
    align = _tokenise_lines(a.bundle["lyrics"]["align_lines"])
    rows = []
    for new, idx in sorted(a.new_idx.items()):
        if a.old_ids[new] is None:
            continue
        tokens, added = len(align[new]), len(idx)
        if added <= tokens - added:
            continue
        verdicts = {g["verdict"] for g in a.kept if g["line_id"] == new}
        evidence = (
            "heard"
            if verdicts == {"heard"}
            else "no audio evidence" if "heard" not in verdicts else "mixed"
        )
        rows.append(
            {
                "old": a.old_ids[new],
                "new": new,
                "tokens": tokens,
                "new_tokens": added,
                "evidence": evidence,
                "steps": [name.removesuffix("_line_ids") for name in STEPS if new in a.steps[name]],
            }
        )
    return rows


def adjacent_overlaps(side: Side, keep: set[int] | None = None) -> tuple[int, int]:
    """(adjacent line pairs whose display windows overlap, adjacent pairs), among the lines
    with words; ``keep`` limits it to pairs whose two lines are both in the set."""
    items = [side.lines[n] for n in sorted(side.lines) if keep is None or n in keep]
    pairs = list(zip(items, items[1:]))
    return sum(y.dstart < x.dend for x, y in pairs), len(pairs)


def summary_block(details: dict, done: list[dict], rows: list[dict]) -> list[str]:
    """The headline counts of every check, raw, for the plan's Results row."""
    roles = Counter(r["role"] for r in done)
    out = [
        "## Summary (raw counts)",
        "",
        f"- songs run on both sides: {dict(roles)} of {dict(Counter(r['role'] for r in rows))}",
    ]
    b1s = details.get("b1", [])
    out.append(f"- B1: {sum(not r['diffs'] for r in b1s)} of {len(b1s)} controls identical")
    for group, r in details.get("b2", {}).items():
        out.append(
            f"- B2 {group}: {r['words']} words in {r['lines']} lines; moved at all {r['moved_any']}; "
            f"moved over {MOVED_S} s {r['moved_far']} (in {r['lines_moved_far']} lines); largest {r['max']:.2f} s"
        )
    hit = details.get("b2_far_aligner_failure", {})
    out.append(
        f"- B2 words moved over {MOVED_S} s on a line an aligner failure hit: {hit.get('words')} words "
        f"in {hit.get('lines')} lines (of {len(details.get('b2_far', []))})"
    )
    b3s = details.get("b3", {})
    counts = b3s.get("counts", {})
    out.append(
        "- B3 old lines before -> after: "
        + ", ".join(
            f"{k} {counts.get(k + ' before', 0)}->{counts.get(k + ' after', 0)}"
            for k in (
                "realigned",
                "paced",
                "guessed_lines",
                "guessed_lines_old",
                "guessed_words",
                "zero_length",
            )
        )
        + f"; increases {len(b3s.get('increases', []))} "
        + str(dict(Counter(i["kind"] for i in b3s.get("increases", []))))
    )
    b4s = details.get("b4", {}).get("total", {})
    for kind in ("inline", "added"):
        t = b4s.get(kind, {})
        n = t.get("words", 0)
        out.append(
            f"- B4 {kind}: {n} words, {dict(sorted((k, v) for k, v in t.items() if k != 'words'))}"
            + (f", measured {t.get('measured', 0) / n:.1%}" if n else "")
        )
    both = sum(b4s.get(k, {}).get("words", 0) for k in ("inline", "added"))
    if both:
        measured = sum(b4s.get(k, {}).get("measured", 0) for k in ("inline", "added"))
        out.append(f"- B4 all new words: {both}, measured {measured / both:.1%}")
    b5s = details.get("b5", {})
    out.append(
        f"- B5: kept groups by label {b5s.get('kept_labels')}; old-line pairs newly overlapping "
        f"{len(b5s.get('new_old_pairs', []))}; overlaps involving an added line {len(b5s.get('added_pairs', []))}"
    )
    b6s = details.get("b6", {})
    out.append(
        f"- B6: {len(b6s)} songs; line timings equal {sum(r['lines_equal'] for r in b6s.values())}, "
        f"bundle word times equal {sum(r['bundle_times_equal'] for r in b6s.values())}, "
        f".ass word times equal {sum(r['ass_times_equal'] for r in b6s.values())}; words compared "
        f"{sum(r['ass_words'][0] for r in b6s.values())}; text changed {sum(r['text_changed'] for r in b6s.values())} "
        f"(only parentheses {sum(r['only_parens'] for r in b6s.values())}); "
        f"other text changes {sum(len(r['other_text']) for r in b6s.values())}"
    )
    added = details.get("added", [])
    aimed = details.get("aimed", [])
    out.append(
        f"- added lines {len(added)}: {dict(Counter(r['ended'] for r in added))}; guessed words in them "
        f"{sum(r['guessed'] for r in added)}; start cut to the previous end {sum(r['cut_to_previous_end'] for r in added)}; "
        f"guard lift {sum(r['lifted'] for r in added)}; onset snap moved {sum(r['onset_snap'] is not None for r in added)}; "
        f"aligner failed on the retry {sum(r['aligner_failure'] for r in added)}"
    )
    out.append(
        f"- heard-aimed tries on added or gaining lines {len(aimed)}, kept {sum(r['kept'] for r in aimed)}"
    )
    member = details.get("membership", [])
    out.append(
        f"- old lines with a changed rescue-list membership or heard status {len(member)}: {dict(Counter(r['group'] for r in member))}"
    )
    out.append(f"- gaining lines under the half-the-tokens bar (D8): {len(details.get('d8', []))}")
    crossing = [k for k, v in details.get("share", {}).items() if v["crosses"]]
    out.append(f"- songs crossing the 15% guessed-line share: {len(crossing)} {crossing}")
    pdisp = details.get("paren_display", {}).get("counts", {})
    out.append(
        f"- kept groups on screen with their parentheses (tokens range read off the .ass): {pdisp}"
    )
    return out + [""]


def labels_of(out: Path) -> dict[tuple[str, int, int], str]:
    rows = read_json(out / "heard.json")
    return {(r["song"], r["cue"], r["group"]): r["label"] for r in rows}


def run_songs(lib: Path, scratch: Path, rows: list[dict]) -> list[dict]:
    """The rows that were run on both sides (a bundle that is not the library's)."""
    done = []
    for row in rows:
        paths = [
            scratch / side / "alignment_debug" / f"{row['stem']}.json"
            for side in ("before", "after")
        ]
        if not all(p.is_file() for p in paths):
            continue
        library = read_json(lib / "alignment_debug" / f"{row['stem']}.json")["captured_at"]
        if all(read_json(p)["captured_at"] != library for p in paths):
            done.append(row)
    return done


def render_dist(words: list[dict]) -> list[str]:
    lines = []
    for label, key in (("start", "ds"), ("end", "de")):
        counts = Counter(bin_of(abs(w[key])) for w in words)
        lines.append(
            f"  {label}: "
            + ", ".join(f"{BIN_LABELS[i]} {counts.get(i, 0)}" for i in range(len(BIN_LABELS)))
        )
    moved = [max(abs(w["ds"]), abs(w["de"])) for w in words]
    lines.append(
        f"  max(|start|,|end|): p50 {percentile(moved, .5):.2f}  p90 {percentile(moved, .9):.2f}  "
        f"p99 {percentile(moved, .99):.2f}  max {max(moved, default=0):.2f}"
    )
    return lines


@dataclass
class Report:
    """What the sections read and write: the songs run, their analyses and logs, the report's
    text and the details file's data."""

    lib: Path
    scratch: Path
    rows: list[dict]
    done: list[dict]
    log_b: dict
    log_a: dict
    labels: dict
    songs: dict[str, dict]  # out/songs.json by key: where each cue song's sheet and bundle are
    analyses: list[Analysis] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    text: list[str] = field(default_factory=list)
    far: list[dict] = field(default_factory=list)  # B2's moved-far words, largest first
    added: list[dict] = field(default_factory=list)
    aimed: list[dict] = field(default_factory=list)

    def emit(self, *lines: str) -> None:
        self.text.extend(lines)

    def by_key(self) -> dict[str, Analysis]:
        return {an.row["key"]: an for an in self.analyses}

    def rows_of(self, role: str) -> list[dict]:
        return [r for r in self.done if r["role"] == role]


def build_analyses(rep: Report) -> None:
    for row in rep.rows_of("keep"):
        before, after = Side(rep.scratch / "before", row["stem"]), Side(
            rep.scratch / "after", row["stem"]
        )
        nb, na = rep.log_b.get(row["stem"], {}), rep.log_a.get(row["stem"], {})
        rep.analyses.append(
            Analysis(
                row,
                before,
                after,
                failed_lines(nb.get("fail", [])),
                failed_lines(na.get("fail", [])),
                nb,
                na,
            )
        )


def section_b1(rep: Report) -> None:
    checks = b1(rep.scratch, rep.rows_of("control"))
    rep.details["b1"] = checks
    rep.emit("## B1 control", "")
    for r in checks:
        rep.emit(
            f"- {r['key']}: {r['files']} output files and the bundle compared; "
            + ("IDENTICAL" if not r["diffs"] else f"DIFFERENCES {r['diffs'][:10]}")
            + (f" (model_path apart: {r['model_paths'][0] != r['model_paths'][1]})")
        )
    rep.emit("")


def section_inputs(rep: Report) -> None:
    bad_ass = [
        (an.row["key"], s)
        for an in rep.analyses
        for s, side in (("before", an.before), ("after", an.after))
        if not side.ass_ok
    ]
    no_note = [
        (an.row["key"], side)
        for an in rep.analyses
        for side, notes in (("before", an.notes_before), ("after", an.notes_after))
        if not notes.get("guessed")
    ]
    heard_off = [
        (an.row["key"], name)
        for an in rep.analyses
        for name, side in (("before", an.before), ("after", an.after))
        if sum(h is not None for h in side.heard()[0]) != side.rescue["n_heard_lines"]
    ]
    rep.emit(
        "## Inputs",
        "",
        f"keep songs analysed: {len(rep.analyses)}; songs whose .ass lines do not match their bundle: {bad_ass}",
        f"songs with no PHASE2 guessed note in a log (before or after): {no_note}",
        f"songs whose recomputed heard-line count differs from the bundle's n_heard_lines: {heard_off}",
        "",
        "## Per song",
        "",
        "key | origin | kept (inline/paren-only) | added | gaining | sections sent back | guessed share before->after",
    )
    for an in rep.analyses:
        a = an.after
        share = share_crossing(rep.scratch, an.row["stem"])
        rep.emit(
            f"{an.row['key']} | {an.row['origin']} | {len(a.kept)} ({an.row['kept_inline']}/{an.row['kept_paren_only']}) | "
            f"{len(a.added())} | {len([n for n in a.new_idx if a.old_ids[n] is not None])} | {len(a.sent)} | "
            f"{share['before'][2]:.1%} -> {share['after'][2]:.1%}"
        )
    rep.emit("")


def section_anchor(rep: Report) -> None:
    shown = Counter()
    shown_bad = []
    for an in rep.analyses:
        r = paren_display(an)
        shown.update(r["counts"])
        shown_bad += [(an.row["key"], *x) for x in r["bad"]]
    rep.details["paren_display"] = {"counts": dict(shown), "bad": shown_bad}
    rep.emit(
        "## Anchor check: kept groups on screen",
        "",
        f"- kept groups whose tokens range opens with ( and closes with ) in the .ass: {dict(shown)}",
    )
    for x in shown_bad[:30]:
        rep.emit(f"  - {x}")
    rep.emit("")


def moved(word: dict) -> float:
    return max(abs(word["ds"]), abs(word["de"]))


def section_kept_set(rep: Report) -> None:
    """The replay transcribes again, so its verdicts can differ from the library transcripts the
    song list was drawn from: the kept groups of the two, per song."""
    lost_all, gained_all = [], []
    for an in rep.analyses:
        library = {(g["cue"], g["group"]) for g in kept_groups(rep.lib, rep.songs[an.row["key"]])}
        replay = {(g["cue"], g["group"]) for g in an.after.kept}
        verdict = {(g["cue"], g["group"]): g for g in an.after.backing["groups"]}
        lost_all += [
            (an.row["key"], c, g, verdict[(c, g)]["kind"], verdict[(c, g)]["verdict"])
            for c, g in sorted(library - replay)
        ]
        gained_all += [
            (an.row["key"], c, g, verdict[(c, g)]["kind"], verdict[(c, g)]["verdict"])
            for c, g in sorted(replay - library)
        ]
    rep.details["kept_set"] = {"lost": lost_all, "gained": gained_all}
    rep.emit(
        "## Kept groups: the library transcript's judge against the after run",
        "",
        f"- kept in the library judge and not in the after run: {len(lost_all)}; kept in the after run only: {len(gained_all)}",
    )
    for label, items in (
        ("not kept in the after run", lost_all),
        ("kept in the after run only", gained_all),
    ):
        for key, cue, group, kind, verdict in items:
            rep.emit(
                f"  - {key} cue {cue} group {group} ({kind}): {label}; its verdict now {verdict}"
            )
    rep.emit("")


def section_b2(rep: Report) -> None:
    all_words: list[dict] = []
    mismatches = []
    for an in rep.analyses:
        for w in b2(an):
            w["key"] = an.row["key"]
            (mismatches if "mismatch" in w else all_words).append(w)
    rep.details["b2_mismatch"] = mismatches
    rep.emit(
        "## B2 old words moved",
        "",
        f"old lines whose word count differs between runs (skipped): {len(mismatches)}",
        "",
    )
    for group in ("gained", "middle", "other"):
        ws = [w for w in all_words if w["group"] == group]
        moved_far = [w for w in ws if moved(w) > MOVED_S]
        moved_any = [w for w in ws if moved(w) > SAME_S]
        lines_ = len({(w["key"], w["old"]) for w in ws})
        rep.details.setdefault("b2", {})[group] = {
            "words": len(ws),
            "lines": lines_,
            "moved_any": len(moved_any),
            "moved_far": len(moved_far),
            "lines_moved_far": len({(w["key"], w["old"]) for w in moved_far}),
            "max": max((moved(w) for w in ws), default=0.0),
        }
        rep.emit(
            f"### {group}: {len(ws)} words in {lines_} lines; moved at all {len(moved_any)}; moved more than {MOVED_S} s {len(moved_far)}"
        )
        rep.emit(*render_dist(ws), "")
    rep.far = sorted((w for w in all_words if moved(w) > MOVED_S), key=lambda w: -moved(w))
    rep.details["b2_far"] = rep.far
    by_key = rep.by_key()
    hit = [w for w in rep.far if by_key[w["key"]].failure(w["old"])]
    rep.details["b2_far_aligner_failure"] = {
        "words": len(hit),
        "lines": len({(w["key"], w["old"]) for w in hit}),
    }
    rep.emit(
        "### every old word moved more than 0.3 s (largest first; the listening list draws from the top)",
        "",
    )
    for w in rep.far:
        an = by_key[w["key"]]
        rep.emit(
            f"- {w['key']} old line {w['old']} word {w['word']} {w['text']!r} [{w['group']}] start {w['ds']:+.2f} end {w['de']:+.2f} "
            f"(before {stamp(w['before'][0])}, after {stamp(w['after'][0])}) aligner failure: {an.failure(w['old']) or 'no'}; "
            f"changed: {step_changes(an, w['old']) or 'nothing recorded'}"
        )
    rep.emit("")
    others = defaultdict(list)
    for w in all_words:
        if w["group"] == "other" and moved(w) > SAME_S:
            others[(w["key"], w["old"])].append(w)
    rep.emit(f"### 'other' lines with any move: {len(others)} lines", "")
    for (key, old), ws in sorted(others.items()):
        an = by_key[key]
        rep.emit(
            f"- {key} old line {old}: {len(ws)} words moved, largest {max(moved(w) for w in ws):.2f} s; "
            f"aligner failure: {an.failure(old) or 'no'}; changed: {step_changes(an, old) or 'nothing recorded'}"
        )
    rep.emit("")


def section_b3(rep: Report) -> None:
    total = Counter()
    increases = []
    for an in rep.analyses:
        r = b3(an)
        total.update(r["counts"])
        increases += [{"key": an.row["key"], **inc} for inc in r["increases"]]
    rep.details["b3"] = {"counts": dict(total), "increases": increases}
    rep.emit("## B3 rescue counts on old lines", "")
    for name in (
        "realigned",
        "paced",
        "guessed_lines",
        "guessed_lines_old",
        "guessed_words",
        "zero_length",
    ):
        rep.emit(f"- {name}: before {total[name + ' before']}, after {total[name + ' after']}")
    rep.emit("", f"### increases: {len(increases)}", "")
    by_kind = Counter((inc["kind"], inc["group"]) for inc in increases)
    rep.emit(
        "by kind and B2 group: "
        + ", ".join(f"{k[0]} {k[1]} {v}" for k, v in sorted(by_kind.items()))
    )
    rep.emit(
        f"on a line an aligner failure hit: {sum(bool(inc['aligner_failure']) for inc in increases)}",
        "",
    )
    for inc in increases:
        rep.emit(
            f"- {inc['key']} old line {inc['old']} (new {inc['new']}) {inc['kind']} {inc['before']}->{inc['after']} [{inc['group']}] aligner failure: {inc['aligner_failure'] or 'no'}; changed: {inc['changed']}"
        )
    rep.emit("")


def section_d8(rep: Report) -> None:
    d8 = [{"key": an.row["key"], **r} for an in rep.analyses for r in d8_rows(an)]
    rep.details["d8"] = d8
    rep.emit(
        f"### D8: gaining lines under the half-the-tokens bar if no echo word is timed: {len(d8)}"
        f" (evidence {dict(Counter(r['evidence'] for r in d8))})",
        "",
    )
    for r in d8:
        rep.emit(
            f"- {r['key']} old line {r['old']} (new {r['new']}): {r['new_tokens']} of {r['tokens']} tokens new; "
            f"echo evidence: {r['evidence']}; rescue steps: {r['steps']}"
        )
    rep.emit("")


def section_b4(rep: Report) -> None:
    t4 = {"inline": Counter(), "added": Counter()}
    per_song = []
    for an in rep.analyses:
        r = b4(an)
        per_song.append({"key": an.row["key"], **r})
        for kind in t4:
            t4[kind].update(r[kind])
    rep.details["b4"] = {"total": {k: dict(v) for k, v in t4.items()}, "songs": per_song}
    rep.emit("## B4 new words timed", "")
    both = Counter()
    for kind, label in (
        ("inline", "inline echo words (gaining lines)"),
        ("added", "added-line words"),
    ):
        n = t4[kind]["words"]
        both.update(t4[kind])
        rep.emit(
            f"- {label}: {n} words; "
            + ", ".join(f"{k} {v}" for k, v in sorted(t4[kind].items()) if k != "words")
            + f"; measured share {t4[kind]['measured'] / n:.1%}"
            if n
            else f"- {label}: none"
        )
    if both["words"]:
        rep.emit(
            f"- all new words: {both['words']}; measured share {both['measured'] / both['words']:.1%} (threshold {B4_MIN_SHARE:.0%})"
        )
    rep.emit("")


def section_b5(rep: Report) -> None:
    kept_labels = Counter()
    for an in rep.analyses:
        for g in an.after.kept:
            kept_labels[rep.labels.get((an.row["key"], g["cue"], g["group"]), "no label")] += 1
    new_pairs, added_pairs = [], []
    adjacent = Counter()
    for an in rep.analyses:
        r = b5(an)
        new_pairs += [(an.row["key"], *p) for p in r["new_old_pairs"]]
        added_pairs += [(an.row["key"], *p) for p in r["added_pairs"]]
        old_new = {n for n, o in enumerate(an.after.old_ids) if o is not None}
        for name, side, keep in (
            ("before", an.before, None),
            ("after_old", an.after, old_new),
            ("after_all", an.after, None),
        ):
            overlapping, pairs = adjacent_overlaps(side, keep)
            adjacent.update({name: overlapping, name + "_pairs": pairs})
    rep.details["b5"] = {
        "kept_labels": dict(kept_labels),
        "new_old_pairs": new_pairs,
        "added_pairs": added_pairs,
        "adjacent": dict(adjacent),
    }
    rep.emit("## B5 screen", "", f"- kept groups by Phase 0 label: {dict(kept_labels)}")
    rep.emit(
        f"- old-line pairs whose display windows overlap after and did not before: {len(new_pairs)}"
    )
    for p in new_pairs:
        rep.emit(f"  - {p}")
    rep.emit(f"- display-window overlaps involving an added line: {len(added_pairs)}")
    rep.emit(
        f"- for context, adjacent lines whose display windows overlap (the pre-roll): before {adjacent['before']} of {adjacent['before_pairs']}; "
        f"after, old lines only {adjacent['after_old']} of {adjacent['after_old_pairs']}; after, all lines {adjacent['after_all']} of {adjacent['after_all_pairs']}",
        "",
    )


def section_b6(rep: Report) -> None:
    rep.emit("## B6 Genius and custom sample", "")
    rep.details["b6"] = {}
    for row in rep.rows_of("b6"):
        an = Analysis(
            row,
            Side(rep.scratch / "before", row["stem"]),
            Side(rep.scratch / "after", row["stem"]),
            (set(), set()),
            (set(), set()),
            rep.log_b.get(row["stem"], {}),
            rep.log_a.get(row["stem"], {}),
        )
        r = b6(an)
        rep.details["b6"][row["key"]] = r
        rep.emit(
            f"- {row['key']} ({row['origin']}): output_line_timings equal {r['lines_equal']}; bundle words {r['bundle_words']} times equal {r['bundle_times_equal']}; "
            f".ass words {r['ass_words']} times equal {r['ass_times_equal']}; text changed {r['text_changed']} (only parentheses {r['only_parens']}); "
            f"other text changes {r['other_text']}; show_parens warnings {len(r['parens_warnings'])}"
        )
    rep.emit("")


def section_amendment(rep: Report) -> None:
    """The D7 amendment's "For Phase 2" list, in its order."""
    rep.emit("## For Phase 2 (the D7 amendment)", "", "### Added lines", "")
    rep.added = [{"key": an.row["key"], **r} for an in rep.analyses for r in added_rows(an)]
    rep.details["added"] = rep.added
    rep.emit(
        f"added lines: {len(rep.added)}; ended: {dict(Counter(r['ended'] for r in rep.added))}", ""
    )
    for r in rep.added:
        rep.emit(
            f"- {r['key']} line {r['new']} {r['text']!r}: {r['ended']}; aligner failed on its retry: {r['aligner_failure']}; words {r['words']}, guessed {r['guessed']}; lifted {r['lifted']}; start cut to previous end {r['cut_to_previous_end']}; onset snap {r['onset_snap']}; "
            f"start {stamp(r['start']) if 'start' in r else '-'}; overlap with line before {r.get('prev_overlap_words')} (window {r.get('prev_overlap_window')}), line after {r.get('next_overlap_words')} (window {r.get('next_overlap_window')}); "
            f"line before ends {r.get('prev_last_end')}; retries {r['retries']}; bounds {r['bounds']}"
        )
    rep.emit("", "### Heard-aimed tries on added or gaining lines", "")
    rep.aimed = [{"key": an.row["key"], **r} for an in rep.analyses for r in aimed_rows(an)]
    rep.details["aimed"] = rep.aimed
    rep.emit(f"tries: {len(rep.aimed)}; kept {sum(r['kept'] for r in rep.aimed)}", "")
    for r in rep.aimed:
        rep.emit(
            f"- {r['key']} {r['kind']} line {r['new']}: kept {r['kept']}, shift {r['shift']}, window {r['window']}, logged {r['logged']}; other lines there: {r['sits_on']}"
        )
    rep.emit("", "### Old lines whose rescue-list membership or heard status changed", "")
    member = [{"key": an.row["key"], **r} for an in rep.analyses for r in membership_rows(an)]
    rep.details["membership"] = member
    rep.emit(f"lines: {len(member)}; by group {dict(Counter(r['group'] for r in member))}", "")
    for r in member:
        rep.emit(
            f"- {r['key']} old line {r['old']} (new {r['new']}) [{r['group']}]: {r['changes']}"
        )
    rep.emit("", "### The line before each added line", "")
    previous = [{"key": an.row["key"], **r} for an in rep.analyses for r in prev_end_rows(an)]
    rep.details["line_before"] = previous
    for r in previous:
        rep.emit(
            f"- {r['key']} added line {r['added']}: line before {r['line_before']} (old {r['old']}) last word ends {r['before_end']:.2f} -> {r['after_end']:.2f}"
        )
    rep.emit("", "### Guessed-line share (Song Info), songs that cross 15%", "")
    crossing = []
    for row in rep.rows_of("keep"):
        r = share_crossing(rep.scratch, row["stem"])
        rep.details.setdefault("share", {})[row["key"]] = r
        if r["crosses"]:
            crossing.append((row["key"], r))
    rep.emit(f"songs crossing {POOR_GUESSED_SHARE:.0%}: {len(crossing)}")
    for key, r in crossing:
        rep.emit(f"- {key}: before {r['before']}, after {r['after']}")
    rep.emit("")


def section_listening(rep: Report) -> None:
    rep.emit("## Listening list", "")
    spots = listening_list(rep.scratch, rep.analyses, rep.far, rep.added, rep.aimed)
    rep.details["listening"] = spots
    for i, sp in enumerate(spots, 1):
        rep.emit(
            f"{i}. {sp['song']} at {sp['time']}: {sp['kind']}: {sp['what']}",
            f"   video {sp['video']}",
            f"   before {sp['before_ass']}",
            f"   after {sp['after_ass']}",
        )
    rep.emit("")


def section_failures(rep: Report) -> None:
    rep.emit("## Aligner failures (every 'slice-align failed' line)", "")
    for side, logs in (("before", rep.log_b), ("after", rep.log_a)):
        rep.emit(f"### {side}: {sum(len(v['fail']) for v in logs.values())}", "")
        for stem, v in sorted(logs.items()):
            for f in v["fail"]:
                rep.emit(f"- {stem}: {f['label']}: {f['message'][:100]}")
        rep.emit("")
    warnings = [(stem, w) for stem, v in rep.log_a.items() for w in v["parens"]]
    rep.emit(f"## show_parens warnings in the after run: {len(warnings)}", "")
    for stem, w in warnings:
        rep.emit(f"- {stem}: {w}")


def main(lib: Path, scratch: Path, out: Path) -> int:
    rows = read_json(out / "phase2_songs.json")
    done = run_songs(lib, scratch, rows)
    skipped = [r["key"] for r in rows if r not in done]
    rep = Report(
        lib,
        scratch,
        rows,
        done,
        parse_logs(scratch / "logs", "before"),
        parse_logs(scratch / "logs", "after"),
        labels_of(out),
        {s["key"]: s for s in read_json(out / "songs.json") if "skipped" not in s},
        details={"skipped": skipped},
    )
    rep.emit(
        "# Phase 2 report",
        "",
        f"songs run on both sides: {len(done)} of {len(rows)}; not yet run: {skipped}",
        "",
    )
    build_analyses(rep)
    section_b1(rep)
    section_inputs(rep)
    section_anchor(rep)
    section_kept_set(rep)
    section_b2(rep)
    section_b3(rep)
    section_d8(rep)
    section_b4(rep)
    section_b5(rep)
    section_b6(rep)
    section_amendment(rep)
    section_listening(rep)
    section_failures(rep)

    summary = summary_block(rep.details, done, rows)
    rep.text[3:3] = summary
    (out / "phase2_report.md").write_text("\n".join(rep.text) + "\n", encoding="utf-8")
    (out / "phase2_details.json").write_text(
        json.dumps(rep.details, indent=1, ensure_ascii=False, default=list), encoding="utf-8"
    )
    print("\n".join(summary))
    print(f"written: {out / 'phase2_report.md'}, {out / 'phase2_details.json'}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("library", type=Path)
    ap.add_argument("scratch", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    sys.exit(main(args.library.expanduser(), args.scratch.expanduser(), args.out))
