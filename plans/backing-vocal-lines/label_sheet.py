"""Phase 0 step 2's labelling view: one line per distinct text, with its counts, songs and
first cue. Built from the inventory alone, no transcript.

    python plans/backing-vocal-lines/label_sheet.py plans/backing-vocal-lines/out

Kinds: C/L caption or LRC, i/o inline or paren-only. Writes out/label_sheet.txt.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def short(stem: str) -> str:
    stem = re.sub(r"---[A-Za-z0-9_-]{11}$", "", stem)
    return re.sub(r"\s*[\(\[](Official|Lyric|Sing|From)[^)\]]*[\)\]]", "", stem)[:38]


def main(out: Path) -> None:
    by = defaultdict(list)
    for row in json.loads((out / "inventory.json").read_text()):
        by[row["label_key"]].append(row)
    lines = []
    for key in sorted(by):
        rows = by[key]
        songs = "; ".join(sorted({short(r["stem"]) for r in rows}))[:80]
        kinds = Counter(
            ("L" if r["origin"] == "lrclib_srt" else "C")
            + ("o" if r["kind"] == "paren_only" else "i")
            for r in rows
        )
        example = rows[0]["cue_text"][:70]
        lines.append(f"{key!r:42} n={len(rows):<2} {dict(kinds)} | {songs} | e.g. {example}")
    (out / "label_sheet.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
