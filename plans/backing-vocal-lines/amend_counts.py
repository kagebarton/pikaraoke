"""D7 amendment counts: how much room a kept paren-only cue has between its neighbours, and
where today's first pass already puts the lines around it.

Read-only over the library. From the worktree root:
    PYTHONPATH=. python plans/backing-vocal-lines/amend_counts.py ~/pikaraoke-songs plans/backing-vocal-lines/out

Reads out/heard.json, out/songs.json and each song's bundle (lines, cue spans, the section
align's line objects before any rescue, the rescue's fitted lead). An added line's time on
the audio clock is its cue span plus that lead, as the rescue's windows are. Prints the
totals.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from pikaraoke.lib.cue_align import SECTION_PAD_S
from pikaraoke.lib.joint_match import _tokenise_lines

RULE = "consume none +vocables +consist"
PAST_S = (0.0, 0.25, 0.5, 1.0)


def kept(row: dict) -> bool:
    """The ruled hybrid, with a quote-opened parenthetical dropped outright."""
    return row["kept"][RULE] and not row["text"].lstrip().startswith(('"', "“"))


def evidence(row: dict) -> str:
    return "heard" if row["kept"]["consume none"] else "vocable" if row["vocable"] else "consist"


def norm(text: str) -> str:
    """A line's text as the rescue compares lines: its normalised tokens."""
    return " ".join(token for token, _raw in _tokenise_lines([text])[0])


def clamped_pad(gap: float | None) -> float:
    """The pad a section's window gets on a side with ``gap`` s to the neighbouring cue."""
    return SECTION_PAD_S if gap is None else min(SECTION_PAD_S, max(0.0, gap / 2))


def main(lib: Path, out: Path) -> None:
    rows = json.loads((out / "heard.json").read_text())
    songs = {s["key"]: s for s in json.loads((out / "songs.json").read_text())}
    cues_of: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if kept(row) and row["kind"] == "paren_only":
            cues_of[row["song"]][row["cue"]].append(row)

    total: Counter = Counter()
    leads: list[float] = []
    for song, cues in sorted(cues_of.items()):
        bundle = json.loads((lib / "alignment_debug" / songs[song]["bundle"]).read_text())
        lines = [norm(line) for line in bundle["lyrics"]["align_lines"]]
        spans = [tuple(span) for span in bundle["cue_inputs"]["spans"]]
        first_pass = {obj["line_id"]: obj for obj in bundle["cue_inputs"]["sections"]}
        lead = bundle["joint_stats"]["repace"]["offset_s"]
        leads.append(lead)
        for groups in cues.values():
            row = groups[0]
            c0, c1 = row["start"], row["end"]
            prev, nxt = row["prev_line"], row["next_line"]
            nxt = nxt if nxt is not None and nxt < len(spans) else None
            text = norm(" ".join(g["text"] for g in groups))
            words = len(text.split())
            total["lines added"] += 1
            total[f"words: {min(words, 3)}{'+' if words >= 3 else ''}"] += 1
            total["evidence: " + "+".join(sorted({evidence(g) for g in groups}))] += 1
            # Equal text makes a run of identical lines; a lead's tail is the usual echo.
            total["text equals a neighbouring line's"] += any(
                lines[k] == text for k in (prev, nxt) if k is not None
            )
            total["text is the end of the line before"] += (
                prev is not None and lines[prev] != text and lines[prev].endswith(text)
            )

            gap_prev = None if prev is None else c0 - spans[prev][1]
            gap_next = None if nxt is None else spans[nxt][0] - c1
            for side, gap in (("before", gap_prev), ("after", gap_next)):
                if gap is not None:
                    total[f"cue touches the cue {side}"] += gap <= 0.001
                    total[f"gap {side} under 0.5 s"] += gap < 0.5
                pad = clamped_pad(gap)
                total[f"clamped pad {side} under 0.25 s"] += pad < 0.25
            # On raw cues the window must reach the singing, which starts `lead` from the cue.
            total["raw-cue window opens after the singing starts"] += clamped_pad(gap_prev) < -lead
            total["raw-cue window closes before the singing ends"] += clamped_pad(gap_next) < lead

            before = first_pass.get(prev) if prev is not None else None
            if before and before["words"]:
                total["line before has first-pass words"] += 1
                for past in PAST_S:
                    total[f"line before ends past the echo's start by > {past}"] += (
                        before["end"] - (c0 + lead) > past
                    )
            after = first_pass.get(nxt) if nxt is not None else None
            if after and after["words"]:
                total["line after has first-pass words"] += 1
                for past in PAST_S:
                    total[f"line after starts before the echo's end by > {past}"] += (
                        c1 + lead
                    ) - after["start"] > past

    for name, count in total.items():
        print(f"{name:52} {count}")
    print(
        f"songs {len(leads)}; rescue lead min / median / max "
        f"{min(leads):+.3f} / {median(leads):+.3f} / {max(leads):+.3f}; "
        f"over 0.25 s either way {sum(abs(lead) > 0.25 for lead in leads)}"
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
