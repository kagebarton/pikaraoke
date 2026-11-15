"""Build spec read counts: how many old lines each placement of a kept parenthetical sends
back to the aligner, and which gaining lines the half-the-tokens bar could empty.

Read-only over the library. From the worktree root:
    PYTHONPATH=. python plans/backing-vocal-lines/read_counts.py ~/pikaraoke-songs plans/backing-vocal-lines/out

Reads out/heard.json, out/songs.json and each song's bundle (lines, cue spans, the section
align's words before any rescue). Three placements of a kept paren-only cue are counted:
A, the spec's (the song is re-sectioned with the new line as a cue); B, the new line joins
the nearer of today's sections; C, the new line is aligned in a window of its own and today's
sections stay. A section goes back to the aligner when its window or text is not one of
today's. Prints totals, the coverage counts and one row per song.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from pikaraoke.lib.cue_align import MIN_LINE_COVERAGE, Section, segment_by_gaps
from pikaraoke.lib.joint_match import _tokenise_lines

RULE = "consume none +vocables +consist"


def kept(row: dict) -> bool:
    """The ruled hybrid, with a quote-opened parenthetical dropped outright."""
    return row["kept"][RULE] and not row["text"].lstrip().startswith(('"', "“"))


def evidence(row: dict) -> str:
    return "heard" if row["kept"]["consume none"] else "vocable" if row["vocable"] else "consist"


def n_tokens(text: str) -> int:
    return len(_tokenise_lines([text])[0])


def keyed(spans: list, texts: list[str], duration: float | None) -> list[tuple[Section, tuple]]:
    """Each section with what an aligner call on it is: its window and its text."""
    return [
        (s, (s.t0, s.t1, "\n".join(texts[s.lid_lo : s.lid_hi + 1])))
        for s in segment_by_gaps(spans, duration=duration)
    ]


def main(lib: Path, out: Path) -> None:
    rows = json.loads((out / "heard.json").read_text())
    songs = {s["key"]: s for s in json.loads((out / "songs.json").read_text())}
    by_song: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if kept(row):
            by_song[row["song"]].append(row)

    total, cover, cover_by, need_by = Counter(), Counter(), Counter(), Counter()
    per_song = []
    for song, kept_rows in sorted(by_song.items()):
        bundle = json.loads((lib / "alignment_debug" / songs[song]["bundle"]).read_text())
        lines = bundle["lyrics"]["align_lines"]
        spans = [tuple(span) for span in bundle["cue_inputs"]["spans"]]
        duration = bundle.get("media_duration_s")
        first_pass = {obj["line_id"]: obj for obj in bundle["cue_inputs"]["sections"]}
        n = len(lines)
        assert not bundle["joint_stats"].get("resectioned")

        gain: dict[int, list[dict]] = defaultdict(list)
        added: dict[int, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for row in sorted(kept_rows, key=lambda r: (r["cue"], r["group"])):
            if row["kind"] == "inline":
                gain[row["line_id"]].append(row)
            else:
                before = n if row["next_line"] is None else row["next_line"]
                added[before][row["cue"]].append(row)

        # The new lines: (span, align text, today's line id or None for an added line).
        new: list[tuple[tuple, str, int | None]] = []
        for k in range(n + 1):
            for _cue, groups in sorted(added.get(k, {}).items()):
                span = (groups[0]["start"], groups[0]["end"])
                new.append((span, " ".join(g["text"] for g in groups), None))
            if k < n:
                echo = "".join(" " + g["text"] for g in gain.get(k, []))
                new.append((spans[k], lines[k] + echo, k))

        today = segment_by_gaps(spans, duration=duration)
        today_keys = {key for _s, key in keyed(spans, lines, duration)}
        section_of = {lid: i for i, s in enumerate(today) for lid in s.line_ids}
        gainers = set(gain)

        re_a: set[int] = set()
        for section, key in keyed([x[0] for x in new], [x[1] for x in new], duration):
            if key not in today_keys:
                re_a |= {new[i][2] for i in section.line_ids if new[i][2] is not None}

        gain_sections = {section_of[lid] for lid in gainers}
        re_c = {lid for lid in range(n) if section_of[lid] in gain_sections}

        nearer = set(gain_sections)
        for before, cues in added.items():
            for groups in cues.values():
                c0, c1 = groups[0]["start"], groups[0]["end"]
                prev_gap = c0 - spans[before - 1][1] if before > 0 else float("inf")
                next_gap = spans[before][0] - c1 if before < n else float("inf")
                nearer.add(section_of[before - 1 if prev_gap <= next_gap else before])
        re_b = {lid for lid in range(n) if section_of[lid] in nearer}

        changed = {i for i, x in enumerate(new) if x[2] is None or x[2] in gainers}
        beside = {
            new[j][2]
            for i in changed
            for j in (i - 1, i + 1)
            if 0 <= j < len(new) and new[j][2] is not None
        }

        total["songs"] += 1
        total["old lines"] += n
        total["gain words"] += len(gainers)
        total["lines added"] += sum(len(cues) for cues in added.values())
        for name, again in (("A", re_a), ("B", re_b), ("C", re_c)):
            total[f"{name}: back to the aligner, not gaining"] += len(again - gainers)
            total[f"{name}: beside a change only"] += len(beside - again - gainers)
            total[f"{name}: all other lines"] += n - len(again | beside | gainers)
        again_counts = [len(again - gainers) for again in (re_a, re_b, re_c)]
        per_song.append((song, n, len(gainers), *again_counts))

        # The half-the-tokens bar on a gaining line, if the aligner timed none of its echo.
        for lid, groups in gain.items():
            n_old = n_tokens(lines[lid])
            n_echo = sum(n_tokens(g["text"]) for g in groups)
            timed = len(first_pass[lid]["words"])
            kinds = {evidence(g) for g in groups}
            by = "heard" if kinds == {"heard"} else "mixed" if "heard" in kinds else "no audio"
            if not timed:
                cover["empty after today's section align"] += 1
                continue
            cover["timed by today's section align"] += 1
            cover_by[("timed", by)] += 1
            need = 0
            while (timed + need) / (n_old + n_echo) < MIN_LINE_COVERAGE:
                need += 1
            if need:
                cover["under the bar with no echo word timed"] += 1
                cover_by[("under", by)] += 1
                need_by[f"needs {need} of {n_echo}"] += 1

    for name, count in total.items():
        print(f"{name}: {count}")
    print(dict(cover))
    print(dict(cover_by))
    print(dict(sorted(need_by.items())))
    print("song | old lines | gain | A | B | C  (back to the aligner, not gaining)")
    for row in per_song:
        print(" | ".join(str(x) for x in row))


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
