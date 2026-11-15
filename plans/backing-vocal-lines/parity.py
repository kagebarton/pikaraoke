"""C2p: the built keep rule against Phase 0's, on the library. Read-only.

    PYTHONPATH=. python plans/backing-vocal-lines/parity.py ~/pikaraoke-songs plans/backing-vocal-lines/out

For every cue song of out/songs.json that was not skipped: read its sheet as the stage does
(UTF-8), run ``sheet_parens`` and ``judge`` with the bundle's ``transcribe_words``, its
``joint_stats.offset_s`` (or 0.0) and the sheet's line spans, and compare with out/heard.json's
``consume none +vocables +consist``. ``judge`` runs twice: as built, and with every group placed
(``at`` 0), so Phase 0's evidence kinds can be compared apart from ``unplaced``.

The built rule agrees with Phase 0 when: the same groups exist, each kept exactly where Phase 0
kept it with the same evidence kind, and the only groups lost are the ``unplaced`` (listed).
Anything else is printed under DIFFERENCES and the exit status is 1. The report is also written
to out/parity.txt (git-ignored: it holds the unplaced groups' texts).
"""

import json
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

from pikaraoke.lib.backing_vocals import _text_key, judge
from pikaraoke.lib.srt_cues import cue_spans_from_srt, sheet_parens

RULE = "consume none +vocables +consist"


def phase0_kind(row: dict) -> str | None:
    """The evidence kind Phase 0's rule kept the row by, None when it dropped it."""
    kept = row["kept"]
    if kept["consume none"]:
        return "heard"
    if kept["consume none +vocables"]:
        return "vocable"
    return "consistency" if kept[RULE] else None


def judge_song(lib: Path, song: dict):
    """The song's parens with the built verdicts, and the verdicts with every group placed."""
    sheet = (lib / song["sheet"]).read_text(encoding="utf-8")
    bundle = json.loads((lib / "alignment_debug" / song["bundle"]).read_text(encoding="utf-8"))
    words = bundle["transcribe_words"]
    offset = bundle["joint_stats"].get("offset_s") or 0.0
    cues = sheet_parens(sheet)
    _, spans = cue_spans_from_srt(sheet)
    placed = [replace(c, groups=tuple(replace(g, at=0) for g in c.groups)) for c in cues]
    return cues, judge(cues, spans, words, offset), judge(placed, spans, words, offset)


def main(lib: Path, out: Path) -> int:
    songs = [s for s in json.loads((out / "songs.json").read_text()) if "skipped" not in s]
    rows = json.loads((out / "heard.json").read_text())
    rows_of: dict[tuple[str, int], list[dict]] = {}
    for row in sorted(rows, key=lambda r: (r["song"], r["cue"], r["group"])):
        rows_of.setdefault((row["song"], row["cue"]), []).append(row)

    differences: list[str] = []
    unplaced: list[str] = []
    built = Counter()  # evidence kinds the built rule kept (every group placed)
    phase0 = Counter()
    real = Counter()  # verdicts as built
    seen = n_groups = 0
    for song in songs:
        try:
            cues, verdicts, evidence = judge_song(lib, song)
        except Exception as error:  # report the song, keep checking the rest
            differences.append(f"{song['key']}: could not run: {error!r}")
            continue
        by_cue = {(v.cue, v.group): v for v in verdicts}
        by_cue_evidence = {(v.cue, v.group): v for v in evidence}
        for cue in cues:
            mine = rows_of.get((song["key"], cue.index), [])
            seen += len(mine)
            if len(mine) != len(cue.groups):
                differences.append(
                    f"{song['key']} cue {cue.index}: {len(cue.groups)} groups built, "
                    f"{len(mine)} in Phase 0"
                )
                continue
            for g, (group, row) in enumerate(zip(cue.groups, mine)):
                n_groups += 1
                if _text_key(group.text) != row["label_key"]:
                    differences.append(f"{song['key']} cue {cue.index}.{g}: text key differs")
                verdict, kind = by_cue[(cue.index, g)], phase0_kind(row)
                evidence_kind = by_cue_evidence[(cue.index, g)].verdict
                real[verdict.verdict] += 1
                if evidence_kind in ("heard", "vocable", "consistency"):
                    built[evidence_kind] += 1
                if kind:
                    phase0[kind] += 1
                if (evidence_kind if evidence_kind != "not_heard" else None) != kind and not (
                    kind is None and evidence_kind == "quote"
                ):
                    differences.append(
                        f"{song['key']} cue {cue.index}.{g}: built {evidence_kind}, "
                        f"Phase 0 {kind}"
                    )
                if verdict.verdict == "unplaced":
                    unplaced.append(f"{song['key']} cue {cue.index}.{g} {group.text!r}")
                elif verdict.verdict != evidence_kind:
                    differences.append(
                        f"{song['key']} cue {cue.index}.{g}: {evidence_kind} became "
                        f"{verdict.verdict} once placed"
                    )
    if seen != len(rows):
        differences.append(f"{len(rows) - seen} Phase 0 groups have no built counterpart")

    lines = [
        f"songs read {len(songs)}, groups compared {n_groups} of {len(rows)} in Phase 0",
        f"Phase 0 kept {sum(phase0.values())}: {dict(phase0)}",
        f"built kept (every group placed) {sum(built.values())}: {dict(built)}",
        f"built verdicts as built: {dict(real)}",
        f"unplaced ({len(unplaced)}):",
        *[f"  {u}" for u in unplaced],
        f"DIFFERENCES ({len(differences)}):",
        *[f"  {d}" for d in differences],
    ]
    report = "\n".join(lines)
    print(report)
    (out / "parity.txt").write_text(report + "\n", encoding="utf-8")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2])))
