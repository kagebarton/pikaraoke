"""GATE A1 and A2 by rule, from out/heard.json.

PYTHONPATH=. python plans/backing-vocal-lines/report.py plans/backing-vocal-lines/out [rule ...]
"""

import json
import sys
from pathlib import Path

SOURCES = {"srt": "captions", "lrclib_srt": "LRC"}


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "0/0"


def a1_a2(rows: list[dict], rule: str) -> list[str]:
    cells = []
    for src in SOURCES:
        rs = [r for r in rows if r["origin"] == src]
        d = [r for r in rs if r["label"] == "direction"]
        cells.append(str(sum(r["kept"][rule] for r in d)) if d else "-")
    for src in SOURCES:
        for voc in (True, False):
            s = [
                r
                for r in rows
                if r["origin"] == src and r["label"] == "sung" and r["vocable"] == voc
            ]
            cells.append(pct(sum(r["kept"][rule] for r in s), len(s)))
    s = [r for r in rows if r["label"] == "sung"]
    cells.append(pct(sum(r["kept"][rule] for r in s), len(s)))
    return cells


def main(out: Path, rules: list[str]) -> None:
    rows = json.loads((out / "heard.json").read_text())
    rules = rules or list(rows[0]["kept"])
    print(
        "| Rule | A1 captions | A1 LRC | A2 captions vocable | A2 captions worded | A2 LRC vocable | A2 LRC worded | A2 all sung |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for rule in rules:
        print(f"| {rule} | " + " | ".join(a1_a2(rows, rule)) + " |")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:])
