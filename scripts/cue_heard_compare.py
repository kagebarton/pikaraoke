#!/usr/bin/env python3
"""Compare a copy library's regenerated bundles with the bundles it was made from (plan
``cue-heard-rescue``, steps 4a and 4b).

``scripts/regen_alignment_bundles.py`` re-ran the staged songs with the heard-words rules on.
Per song this reads:

* the **new bundle**, in ``COPY/alignment_debug``;
* the **source bundle**, made before the regen, from the oldest ``COPY/regen_backups/*/``
  (``--source`` names another folder holding ``alignment_debug/`` and ``karaoke/``);
* the **same-bundle baseline**: ``cue_heard_probe.replay`` with ``heard=False`` over the new
  bundle's own ``cue_inputs`` and saved re-aligns.

The rules are measured against the baseline, not against the source bundle, because the regen
re-ran whisper and decoded the stems on this machine, which moves snapped edges by itself. A
baseline call the new bundle holds no answer for (a line a rule kept before the cue-aimed retry
was asked) makes that line's "today" unreliable; its rows say so. The ``heard=True`` replay must
reproduce the new bundle's ``output_line_timings``, else the song is left out and named.

Moves against the source bundle are their own table. Tables go to stdout as markdown;
``OUT/compare/rows.json`` holds every row with its lyric text and ``OUT/listening-sheet.html``
the A/B sheet for VLC; neither is committed. The library probe's ``OUT/rows.json`` is not touched.

Run from the repo root::

    python scripts/cue_heard_compare.py COPY [--source DIR] [--out DIR] > report.md
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

# Allow running as ``python scripts/cue_heard_compare.py`` from repo root; the probe is a
# sibling script, not a package module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cue_heard_probe as probe  # noqa: E402

from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.lib.library_regen import list_videos, read_bundle  # noqa: E402
from pikaraoke.lib.metadata_parser import extract_youtube_id  # noqa: E402

# Table S lists a line whose start or end moved this much against the source bundle (the
# threshold GATE H names for a line to be explained).
SOURCE_MOVED_S = 0.3
# Table P counts the moves at these sizes as well.
SOURCE_MOVED_COUNTS = (probe.MOVED_S, SOURCE_MOVED_S, 1.0)

# "Within" in the heard column: the new start is this close to the heard start.
HEARD_CLOSE_S = 0.05

# The listening sheet starts this long before the earlier of a spot's two starts.
LEAD_IN_S = 4.0

# Spots from "What the three flawed picks showed": (YouTube id, line ids, kind). Target spots
# are on the sheet; the two Quit Playing Games lines Ken also heard are expected unchanged.
SPOTS = [
    ("Ug88HO2mg44", (24, 25), "target"),
    ("Q4VK9_CfOLQ", (22,), "target"),
    ("RNprQYHenNI", (36,), "target"),
    ("Ug88HO2mg44", (1,), "target"),
    ("Ug88HO2mg44", (8,), "unchanged"),
    ("Ug88HO2mg44", (37,), "unchanged"),
]

# The sheet after the target spots: (group, rows, rows per song at most), in order.
SHEET_GROUPS = [("C", 8, 2), ("D", 3, 99), ("B", 4, 99), ("A", 2, 99), ("Z", 1, 99)]


@dataclass(frozen=True)
class Spot:
    """One place on the listening sheet: the lines to listen to and where they sit in the
    source bundle (``before``) and the new bundle (``after``), as (start, end) per line."""

    group: str
    rank: float
    stem: str
    song: str
    lines: tuple[int, ...]
    rule: str
    text: str
    before: tuple[tuple[float | None, float | None], ...]
    after: tuple[tuple[float | None, float | None], ...]

    @property
    def moved(self) -> float:
        return max(
            max(probe.moved(b[0], a[0]), probe.moved(b[1], a[1]))
            for b, a in zip(self.before, self.after)
        )

    @property
    def listen_at(self) -> str:
        """m:ss, :data:`LEAD_IN_S` before the earliest start of either bundle."""
        starts = [t[0] for t in (*self.before, *self.after) if t[0] is not None]
        seconds = max(0, int(min(starts) - LEAD_IN_S)) if starts else 0
        return f"{seconds // 60}:{seconds % 60:02d}"


@dataclass
class Compared:
    """One staged song: its Table P row, and when its replay held, its table rows and the
    sheet's candidates by group."""

    song: probe.Song
    check: dict
    rows: dict[str, list[dict]] = field(default_factory=dict)
    pool: dict[str, list[Spot]] = field(default_factory=dict)


@dataclass
class CompareCtx(probe.Ctx):
    """The probe's row context plus the source and new bundles' ``output_line_timings`` and the
    lines the baseline replay asked the new bundle's saved re-aligns about without an answer."""

    source: dict[int, dict]
    new_output: dict[int, dict]
    unanswered: set[int]

    def source_start(self, lid: int) -> float | None:
        rec = self.source.get(lid)
        return rec["start"] if rec else None


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def timings(bundle: dict | None) -> dict[int, dict]:
    """The bundle's ``output_line_timings`` by line id."""
    return {rec["line_id"]: rec for rec in (bundle or {}).get("output_line_timings") or []}


def span(rec: dict | None) -> tuple[float | None, float | None] | None:
    return None if rec is None else (rec["start"], rec["end"])


def vs_heard(before: float | None, after: float | None, heard: float | None) -> str | None:
    """Whether ``after`` is within :data:`HEARD_CLOSE_S` of ``heard``, else closer to it than
    ``before`` was, else further."""
    if before is None or after is None or heard is None:
        return None
    if round(abs(after - heard), 3) <= HEARD_CLOSE_S:  # times are to the millisecond
        return "within"
    return "closer" if abs(after - heard) < abs(before - heard) else "further"


def neighbour(final: dict[int, dict], lid: int, step: int) -> tuple[float, float] | None:
    """(start, end) of the nearest line before (``step`` -1) or after (+1) ``lid`` that has
    words."""
    i = lid + step
    while i in final:
        if final[i]["words"]:
            return final[i]["start"], final[i]["end"]
        i += step
    return None


def runs_into_next(final: dict[int, dict], lid: int) -> bool:
    """Whether line ``lid``'s last word ends after the next line's first word starts."""
    i = lid + 1
    while i in final and not final[i]["words"]:
        i += 1
    return i in final and final[lid]["words"][-1]["end"] > final[i]["words"][0]["start"]


def widen(
    ctx: CompareCtx, rows: list[dict], *, heard: bool = False, neighbours: bool = False
) -> list[dict]:
    """Add the compare columns to the probe's rows: the source start, whether the baseline
    had every answer it asked for, and, as asked, the heard comparison and, for the kept
    lines of rules B and D, the ends and the neighbours."""
    for row in rows:
        lid = row["line"]
        row["source"] = ctx.source_start(lid)
        row["today_ok"] = lid not in ctx.unanswered
        if heard:
            moved = row.get("kept", True)  # a line the rule left as it was has no move to judge
            row["vs_today"] = vs_heard(row["today"], row["new"], row["heard"]) if moved else None
            row["vs_source"] = vs_heard(row["source"], row["new"], row["heard"]) if moved else None
        if neighbours:
            row["today_end"] = ctx.today.final[lid]["end"]
            row["new_end"] = ctx.new.final[lid]["end"]
            row["previous"] = neighbour(ctx.new.final, lid, -1)
            row["next"] = neighbour(ctx.new.final, lid, 1)
            row["overlap"] = runs_into_next(ctx.new.final, lid) if row["kept"] else None
            row["guessed"] = lid in ctx.new.stats["guessed_word_line_ids"]
    return rows


def rule_tags(rows: dict[str, list[dict]]) -> dict[int, str]:
    """Each line's rules: A1/A2, G, Z, and B, D and C as tried or kept."""
    tags: dict[int, list[str]] = defaultdict(list)
    for row in rows["A"]:
        tags[row["line"]].append(row["rule"])
    for letter in "GZ":
        for row in rows[letter]:
            tags[row["line"]].append(letter)
    for letter in "BDC":
        for row in rows[letter]:
            tags[row["line"]].append(f"{letter} {'kept' if row['kept'] else 'tried'}")
    return {lid: ", ".join(found) for lid, found in tags.items()}


def stats_mismatch(replayed: dict, saved: dict) -> list[str]:
    """The ``*_line_ids`` stats whose lists differ between the replay and the bundle."""
    return sorted(
        key
        for key, ids in replayed.items()
        if key.endswith("_line_ids") and sorted(saved.get(key, [])) != sorted(ids)
    )


# ---------------------------------------------------------------------------
# One song
# ---------------------------------------------------------------------------


def moves_against_source(source: dict[int, dict], new: dict[int, dict]) -> list[tuple[int, float]]:
    """(line id, how far its start or end moved) for each line in both bundles' outputs."""
    return [
        (
            lid,
            max(
                probe.moved(src["start"], new[lid]["start"]),
                probe.moved(src["end"], new[lid]["end"]),
            ),
        )
        for lid, src in source.items()
        if lid in new
    ]


def check_row(song: probe.Song, source_bundle: dict | None, moves: list[tuple[int, float]]) -> dict:
    """The song's Table P row before any replay: what the regen changed in the bundle."""
    new_lyrics = song.bundle.get("lyrics") or {}
    old_lyrics = (source_bundle or {}).get("lyrics") or {}
    same = bool(source_bundle) and all(
        new_lyrics.get(key) == old_lyrics.get(key) for key in ("origin", "lines")
    )
    return {
        "src": song.kind,
        "song": probe.label(song.stem),
        "lines": len(song.bundle.get("output_line_timings") or []),
        "same_lyrics": same,
        "replay": "",
        "stats_match": None,
        "new_unanswered": None,
        "today_unanswered": None,
        **{f"moved_{t}": sum(1 for _, m in moves if m > t) for t in SOURCE_MOVED_COUNTS},
    }


def build_spot(group: str, rank: float, ctx: CompareCtx, lines: tuple[int, ...], rule: str) -> Spot:
    return Spot(
        group,
        rank,
        ctx.song.stem,
        probe.label(ctx.song.stem),
        lines,
        rule,
        " / ".join(ctx.rescue.display_lines[lid] for lid in lines),
        tuple(span(ctx.source.get(lid)) or (None, None) for lid in lines),
        tuple(span(ctx.new_output.get(lid)) or (None, None) for lid in lines),
    )


def sheet_pool(ctx: CompareCtx, rows: dict[str, list[dict]]) -> dict[str, list[Spot]]:
    """The spots this song offers the sheet: its target spots, and its kept lines of rules
    C, D and B, its A lines and its zero-length lines, each ranked within its group."""
    pool: dict[str, list[Spot]] = {"target": []}
    for index, (video_id, lines, kind) in enumerate(SPOTS):
        if kind == "target" and extract_youtube_id(ctx.song.stem) == video_id:
            if all(lid in ctx.new_output for lid in lines):
                pool["target"].append(build_spot("target", index, ctx, lines, "target"))
    for group, _, _ in SHEET_GROUPS:
        pool[group] = []
        for row in rows[group]:
            if group in ("B", "C", "D") and not row["kept"]:
                continue
            spot = build_spot(group, 0.0, ctx, (row["line"],), row.get("rule", group))
            rank = row["retimed"] if group == "Z" else spot.moved
            if rank > (0 if group == "Z" else probe.MOVED_S):  # a move nobody can hear is no spot
                pool[group].append(replace(spot, rank=rank))
    return pool


def spot_rows(ctx: CompareCtx, tags: dict[int, str]) -> list[dict]:
    """Table T: the lines of :data:`SPOTS` this song holds."""
    rows = []
    for video_id, lines, kind in SPOTS:
        if extract_youtube_id(ctx.song.stem) != video_id:
            continue
        for lid in lines:
            if lid not in ctx.new_output:
                continue
            heard = ctx.rescue.heard[lid]
            rows.append(
                ctx.row(
                    lid,
                    spot=kind,
                    cue=ctx.cue(lid) + ctx.rescue.offset,
                    heard=None if heard is None else heard.start,
                    source=span(ctx.source.get(lid)),
                    today=span(ctx.today.final[lid]),
                    new=span(ctx.new_output[lid]),
                    rules=tags.get(lid, ""),
                )
            )
    return rows


def source_rows(
    song: probe.Song, source: dict[int, dict], new_output: dict[int, dict], moves: list
) -> list[dict]:
    """Table S: lines whose start or end moved more than :data:`SOURCE_MOVED_S` against the
    source bundle. The baseline and the rules are filled in when the song is replayed."""
    lines = song.bundle["lyrics"]["lines"]
    return [
        {
            "src": song.kind,
            "song": probe.label(song.stem),
            "line": lid,
            "text": lines[lid] if lid < len(lines) else "",
            "source": span(source[lid]),
            "today": None,
            "new": span(new_output[lid]),
            "moved": amount,
            "rules": "",
        }
        for lid, amount in moves
        if amount > SOURCE_MOVED_S
    ]


def song_rows(ctx: CompareCtx) -> tuple[dict[str, list[dict]], dict[int, str]]:
    """Tables A, G, Z, B, D, C, O and T for a replayed song, and each line's rules."""
    rows = {
        "A": widen(ctx, probe.rows_a(ctx), heard=True),
        "G": widen(ctx, probe.rows_g(ctx)),
        "Z": probe.rows_z(ctx),
        "B": widen(ctx, probe.rows_b(ctx), heard=True, neighbours=True),
        "D": widen(ctx, probe.rows_d(ctx), heard=True, neighbours=True),
        "C": widen(ctx, probe.rows_c(ctx)),
    }
    claimed = {row["line"] for table in rows.values() for row in table}
    rows["O"] = probe.rows_o(ctx, claimed)
    for row in rows["O"]:
        row["near_unanswered"] = bool(
            {row["line"] - 1, row["line"], row["line"] + 1} & ctx.unanswered
        )
    tags = rule_tags(rows)
    rows["T"] = spot_rows(ctx, tags)
    return rows, tags


def compare_song(copy: Path, source_dir: Path, cache_dir: Path, stem: str) -> Compared | None:
    """Compare one staged song, or None when the source has no bundle for it."""
    source_bundle = read_bundle(source_dir, stem)
    if source_bundle is None:
        return None
    bundle = read_bundle(copy, stem)
    if bundle is None:
        stub = probe.Song(stem, probe.song_kind(source_bundle), source_bundle)
        return Compared(stub, {**check_row(stub, None, []), "replay": "bundle missing"})
    song = probe.Song(stem, probe.song_kind(bundle), bundle)
    source, new_output = timings(source_bundle), timings(bundle)
    moves = moves_against_source(source, new_output)
    check = check_row(song, source_bundle, moves)
    done = Compared(song, check, {"S": source_rows(song, source, new_output, moves)})
    if bundle.get("captured_at") == source_bundle.get("captured_at"):
        check["replay"] = "not regenerated"
        return done
    if not probe.on_cue_route(bundle):
        check["replay"] = "not on the cue route"
        return done
    loaded = probe.stem_and_envelope(copy, cache_dir, song)
    if isinstance(loaded, probe.LeftOut):
        check["replay"] = loaded.reason
        return done
    stem_file, env, duration = loaded
    today = probe.replay(song, stem_file, env, duration, heard=False)
    new = probe.replay(song, stem_file, env, duration, heard=True)
    deviation = probe.worst_deviation(new.final, bundle["output_line_timings"])
    check["replay"] = "reproduces" if deviation is None else f"differs: {deviation}"
    saved = (bundle.get("joint_stats") or {}).get("repace") or {}
    check["stats_match"] = not stats_mismatch(new.stats, saved)
    check["new_unanswered"] = sum(not call.answered for call in new.calls)
    unanswered = {call.line_id for call in today.calls if not call.answered}
    check["today_unanswered"] = len(unanswered)
    if deviation is not None:
        return done
    first = {obj["line_id"]: obj for obj in bundle["cue_inputs"]["sections"]}
    rescue = probe.song_rescue(song, env, duration)
    ctx = CompareCtx(song, rescue, first, today, new, source, new_output, unanswered)
    rows, tags = song_rows(ctx)
    done.rows.update(rows)
    for row in done.rows["S"]:
        row["today"], row["rules"] = span(today.final[row["line"]]), tags.get(row["line"], "")
    done.pool = sheet_pool(ctx, done.rows)
    return done


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

SRC_SONG_LINE = [("Src", "src"), ("Song", "song"), ("Line", "line")]
NEIGHBOURS = [
    ("Overlap", "overlap"),
    ("Guessed", "guessed"),
    ("Previous", "previous"),
    ("Next", "next"),
]

# Table letter -> (title, note, [(header, row key)]).
COMPARE_TABLES = {
    "T": (
        "Table T: the spots Ken named",
        "Starts and ends on the audio clock. Source: the source bundle's output; Today: the "
        "same-bundle baseline; New: the new bundle's output. Heard: the transcriber's start "
        "(blank when the line is not heard). Spot: target, or expected unchanged.",
        [
            *SRC_SONG_LINE,
            ("Spot", "spot"),
            ("Cue", "cue"),
            ("Heard", "heard"),
            ("Source", "source"),
            ("Today", "today"),
            ("New", "new"),
            ("Rules", "rules"),
        ],
    ),
    "A": (
        "Table A: lines rule A1 keeps and rule A2 holds",
        "Cue on the cue clock, the rest on the audio clock. Source: the source bundle's start. "
        "vs heard: the new start within 0.05 s of the heard start, else closer to it than "
        "the Today (or Source) start was, else further. Today answered: the baseline held every "
        "re-align answer it asked for on this line; if not, Today is not today's output.",
        [
            *SRC_SONG_LINE,
            ("Rule", "rule"),
            ("Cue", "cue"),
            ("Source", "source"),
            ("Today", "today"),
            ("New", "new"),
            ("Heard", "heard"),
            ("vs heard, today", "vs_today"),
            ("vs heard, source", "vs_source"),
            ("Today answered", "today_ok"),
            ("Run", "run"),
            ("Gap one side", "gap_side"),
        ],
    ),
    "G": (
        "Table G: starts the guard lift freed of the previous line",
        "Previous end: the previous line's end in the new replay.",
        [
            *SRC_SONG_LINE,
            ("Cue", "cue"),
            ("Source", "source"),
            ("Today", "today"),
            ("New", "new"),
            ("Heard", "heard"),
            ("Previous end", "previous_end"),
            ("Today answered", "today_ok"),
        ],
    ),
    "Z": probe.TABLES["Z"],
    "B": (
        "Table B: lines rule B aimed where they were heard",
        "Overlap: a kept line's last word ends after the next line's first word starts. "
        "Guessed: the line is in guessed_word_line_ids. Previous and Next: start-end of the "
        "neighbouring lines with words in the new output. Answered: the bundle holds the "
        "heard-aimed align's result; Today answered: it holds the baseline's cue-aimed one "
        "(not when rule B kept the line first).",
        [
            *SRC_SONG_LINE,
            ("Cue", "cue"),
            ("Heard", "heard"),
            ("Shift", "shift"),
            ("Window", "window"),
            ("Lone first", "lone_first"),
            ("Answered", "answered"),
            ("Kept", "kept"),
            ("Source", "source"),
            ("Today", "today"),
            ("Today end", "today_end"),
            ("New", "new"),
            ("New end", "new_end"),
            ("vs heard, today", "vs_today"),
            ("vs heard, source", "vs_source"),
            ("Today answered", "today_ok"),
            *NEIGHBOURS,
        ],
    ),
    "D": (
        "Table D: lines rule D aimed where they were heard",
        "Smallest and largest: signed pair offsets (heard - placed). Overlap, Guessed, Previous "
        "and Next as in Table B.",
        [
            *SRC_SONG_LINE,
            ("Heard", "heard"),
            ("Pairs", "pairs"),
            ("Smallest", "smallest"),
            ("Largest", "largest"),
            ("Run", "run"),
            ("Answered", "answered"),
            ("Kept", "kept"),
            ("Source", "source"),
            ("Today", "today"),
            ("Today end", "today_end"),
            ("New", "new"),
            ("New end", "new_end"),
            ("vs heard, today", "vs_today"),
            ("vs heard, source", "vs_source"),
            *NEIGHBOURS,
        ],
    ),
    "C": (
        "Table C: lines rule C looked for between their neighbours",
        probe.TABLES["C"][1],
        [
            *probe.TABLES["C"][2][:11],
            ("Source", "source"),
            *probe.TABLES["C"][2][11:],
            ("Today answered", "today_ok"),
        ],
    ),
    "O": (
        "Table O: other lines whose start or end moved, against the same-bundle baseline",
        "Lines outside Tables A, G, Z, B, D and C. Near unanswered today: this line or a "
        "neighbour had a baseline align without a saved answer.",
        [*probe.TABLES["O"][2], ("Near unanswered today", "near_unanswered")],
    ),
    "S": (
        "Table S: lines that moved against the source bundle",
        f"Lines whose start or end moved more than {SOURCE_MOVED_S} s between the source "
        "bundle's output and the new bundle's, as (start-end). Today is the same-bundle "
        "baseline, so Source to Today is what the regen's own changes did (whisper, the "
        "envelope decoded here) and Today to New is the rules. Rules: the rule lists the line "
        "is in.",
        [
            *SRC_SONG_LINE,
            ("Source", "source"),
            ("Today", "today"),
            ("New", "new"),
            ("Moved", "moved"),
            ("Rules", "rules"),
        ],
    ),
}
TABLE_ORDER = "TAGZBDCOS"


def tally_kept(rows: list[dict]) -> str:
    """``caption: N tried, M kept in K songs; LRCLIB: ...`` for a rule that can refuse."""
    parts = []
    for kind in probe.KINDS:
        mine = [row for row in rows if row["src"] == kind]
        kept = sum(1 for row in mine if row["kept"])
        songs = len({row["song"] for row in mine})
        parts.append(f"{kind}: {len(mine)} tried, {kept} kept in {songs} songs")
    return "; ".join(parts)


def table_p(done: list[Compared]) -> str:
    moved = [(f"Moved over {t} s", f"moved_{t}") for t in SOURCE_MOVED_COUNTS]
    columns = [
        ("Src", "src"),
        ("Song", "song"),
        ("Lines", "lines"),
        ("Same lyrics as source", "same_lyrics"),
        ("Heard replay of the new bundle", "replay"),
        ("Stats match", "stats_match"),
        ("New unanswered", "new_unanswered"),
        ("Today unanswered", "today_unanswered"),
        *moved,
    ]
    rows = sorted((c.check for c in done), key=lambda r: (probe.KINDS.index(r["src"]), r["song"]))
    return "\n".join(
        [
            "### Table P: songs regenerated, replayed and left out",
            "Same lyrics: the lyric origin and lines equal the source bundle's. Heard replay: "
            "the replay with the transcriber's words and every rule against the new bundle's "
            "output_line_timings, tolerance "
            f"{probe.TOLERANCE_S} s; a song it does not reproduce is left out of every table "
            "but S. Stats match: the replay's *_line_ids equal the bundle's repace stats. New "
            "unanswered: re-align calls of that replay the bundle holds no answer for. Today "
            "unanswered: lines whose baseline re-align has no saved answer (the cue-aimed retry "
            "a rule made unnecessary). Moved: lines whose start or end moved against the "
            "source bundle by more than that.",
            "",
            probe.markdown_table(
                [h for h, _ in columns], [[row[k] for _, k in columns] for row in rows]
            ),
        ]
    )


def table_c_runs(rows: list[dict]) -> str:
    """Rule C's tries and keeps by whether the line is in a run of identical lines and, if it
    is, whether its stretch ends at a parked twin."""
    groups = {
        "not in a run": lambda r: not r["run"],
        "in a run, stretch between twins on their cues": lambda r: r["run"] and not r["twin"],
        "in a run, stretch ends at a parked twin": lambda r: r["run"] and r["twin"],
    }
    body = [
        [name, sum(1 for r in rows if pick(r)), sum(1 for r in rows if pick(r) and r["kept"])]
        for name, pick in groups.items()
    ]
    return "Rule C by run:\n\n" + probe.markdown_table(["Lines", "Tried", "Kept"], body)


def kept_without_answer(rows: list[dict]) -> str:
    """The kept rule B lines whose cue-aimed retry has no saved answer."""
    names = [f"{r['song']} line {r['line']}" for r in rows if r["kept"] and not r["today_ok"]]
    return "Kept B lines whose cue-aimed retry has no saved answer: " + (
        ", ".join(names) if names else "none"
    )


def report(done: list[Compared]) -> tuple[str, list[dict]]:
    """The markdown report, and every table row tagged with its table, for ``rows.json``."""
    sections = [table_p(done)]
    all_rows: list[dict] = []
    for letter in TABLE_ORDER:
        title, note, columns = COMPARE_TABLES[letter]
        rows = sorted(
            (row for c in done for row in c.rows.get(letter, [])),
            key=lambda row: (probe.KINDS.index(row["src"]), row["song"], row["line"]),
        )
        all_rows += [{"table": letter, **row} for row in rows]
        count = tally_kept(rows) if letter in "BDC" else probe.tally(rows)
        body = probe.markdown_table(
            [h for h, _ in columns], [[row[k] for _, k in columns] for row in rows]
        )
        sections.append(f"### {title}\n{note}\n\n{count}\n\n{body}")
        if letter == "B":
            sections.append(kept_without_answer(rows))
        if letter == "C":
            sections.append(table_c_runs(rows))
    return "\n\n".join(sections) + "\n", all_rows


# ---------------------------------------------------------------------------
# Listening sheet
# ---------------------------------------------------------------------------


def pick_spots(done: list[Compared]) -> list[Spot]:
    """The sheet's spots: the target spots in the order of :data:`SPOTS`, then each of
    :data:`SHEET_GROUPS` by largest move (zero-length: most words re-timed) up to its row
    limit and per-song limit, never twice the same line."""
    picked = sorted((s for c in done for s in c.pool.get("target", [])), key=lambda s: s.rank)
    taken = {(s.stem, lid) for s in picked for lid in s.lines}
    for group, limit, per_song in SHEET_GROUPS:
        candidates = sorted(
            (s for c in done for s in c.pool.get(group, [])),
            key=lambda s: (-s.rank, s.stem, s.lines),
        )
        chosen: list[Spot] = []
        per = Counter()
        for spot in candidates:
            if len(chosen) == limit:
                break
            if per[spot.stem] == per_song or (spot.stem, spot.lines[0]) in taken:
                continue
            chosen.append(spot)
            per[spot.stem] += 1
            taken.add((spot.stem, spot.lines[0]))
        picked += chosen
    return picked


SHEET_STYLE = """
:root { --bg: #ffffff; --fg: #1a1a1a; --muted: #666666; --line: #d8d8d8; --accent: #0b5cad; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14161a; --fg: #e8e8e8; --muted: #9aa0a6; --line: #343840; --accent: #6cb2ff;
  }
}
body { background: var(--bg); color: var(--fg); font: 15px/1.45 system-ui, sans-serif; margin: 0; padding: 16px; }
h1 { font-size: 20px; margin: 0 0 4px; }
p { color: var(--muted); max-width: 70ch; margin: 4px 0 16px; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 13px; }
td.at { font-size: 20px; font-weight: 700; color: var(--accent); white-space: nowrap; }
td.path { font: 12px/1.35 ui-monospace, monospace; word-break: break-all; user-select: all; }
"""


def sheet_html(spots: list[Spot], copy: Path, source_dir: Path) -> str:
    """The listening sheet: per spot the time to seek to and the video with the new and old
    .ass, to open in VLC without the app."""
    videos = {v.stem: v for v in list_videos(copy)}

    def path_cell(path: Path | None) -> str:
        shown = "(missing)" if path is None or not path.is_file() else str(path)
        return f'<td class="path">{html.escape(shown)}</td>'

    def times(spans: tuple) -> str:
        return html.escape("; ".join(f"{probe.fmt(a)}-{probe.fmt(b)}" for a, b in spans))

    rows = []
    for number, spot in enumerate(spots, 1):
        new_ass = copy / "karaoke" / f"{spot.stem}.ass"
        old_ass = source_dir / "karaoke" / f"{spot.stem}.ass"
        rows.append(
            "<tr>"
            f"<td>{number}</td><td>{html.escape(spot.song)}</td>"
            f'<td class="at">{spot.listen_at}</td>'
            f"<td>{html.escape(spot.rule)}</td>"
            f"<td>{html.escape(', '.join(map(str, spot.lines)))}<br>"
            f'<span style="color:var(--muted)">{html.escape(spot.text)}</span></td>'
            f"<td>{times(spot.before)}</td><td>{times(spot.after)}</td>"
            f"{path_cell(videos.get(spot.stem))}{path_cell(new_ass)}{path_cell(old_ass)}"
            "</tr>"
        )
    head = (
        "<tr><th>#</th><th>Song</th><th>Seek to</th><th>Rule</th><th>Line</th>"
        "<th>Before</th><th>After</th><th>Video</th><th>New .ass</th><th>Old .ass</th></tr>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Cue Heard Listening</title>"
        f"<style>{SHEET_STYLE}</style></head><body>"
        "<h1>Cue rescue listening sheet</h1>"
        f"<p>Open the video in VLC with the new .ass, then with the old one, and seek to the "
        f"time. Seek is {LEAD_IN_S:g} s before the earlier of the two starts. Before and After "
        "are the line's start-end in the source bundle (the old .ass) and the new bundle, in "
        f"seconds. {len(spots)} spots.</p>"
        f"<table><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table></body></html>"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def source_folder(copy: Path) -> Path:
    """The folder the regen backed the source bundles up to: the oldest ``regen_backups/*``
    of ``copy`` that holds an ``alignment_debug`` folder."""
    found = sorted(
        p for p in (copy / "regen_backups").glob("*") if (p / "alignment_debug").is_dir()
    )
    if not found:
        raise SystemExit(f"No regen backup with alignment_debug/ under {copy / 'regen_backups'}")
    return found[0]


def run_compare(copy: Path, source_dir: Path, out: Path) -> str:
    """Compare every song the source folder has a bundle for; the report text. ``out`` gets
    ``compare/`` (the envelope cache and ``rows.json``) and ``listening-sheet.html``."""
    work = out / "compare"
    work.mkdir(parents=True, exist_ok=True)
    stems = sorted(p.stem for p in (source_dir / "alignment_debug").glob("*.json"))
    done = []
    for i, stem in enumerate(stems, 1):
        print(f"[{i}/{len(stems)}] {stem}", file=sys.stderr)
        if (result := compare_song(copy, source_dir, work / "env", stem)) is not None:
            done.append(result)
    text, rows = report(done)
    (work / "rows.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding="utf-8"
    )
    (out / "listening-sheet.html").write_text(
        sheet_html(pick_spots(done), copy, source_dir), encoding="utf-8"
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("copy", type=Path, help="the copy library the regen ran on")
    parser.add_argument(
        "--source", type=Path, help="folder with the source alignment_debug/ and karaoke/"
    )
    parser.add_argument("--out", type=Path, help="scratch folder (default: the probe's)")
    args = parser.parse_args()
    copy = args.copy.expanduser().resolve()
    source_dir = args.source or source_folder(copy)
    out = args.out or Path(get_temp_directory()) / "cue_heard_rescue"
    sys.stdout.write(run_compare(copy, source_dir, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
