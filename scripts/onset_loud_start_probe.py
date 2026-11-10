"""Measurement for plans/onset-loud-start.md: which line starts stay early, which exit
of the onset snap left them there, and what lifting the on-time skip would move.

Every cue-route bundle is replayed on the CPU (``repace_bad_lines`` over the bundle's
``cue_inputs``, then the edge snap), so each line's start before the snap is known. A
song whose replay does not equal the bundle's recorded output is left out and named. A
start is scored against the transcriber's first word for the line; that reference is
itself early after a gap (Table C), so the tables are for sizing and nothing here judges
a move.

With ``--listen`` it also builds the GATE S listening sheet for the rule under test (a
skipped line moves only where a heard word equal to its first word starts near the rise):
``<out>/listening-sheet.html`` and, for each sheet song, ``karaoke/<stem>.onsetfix.ass``
in the library, the shipped subtitles with the rule on. Those are the only files it ever
writes to the library; without ``--listen`` the library is never written.

``--out`` holds the envelope cache, ``rows.json`` (one row per line) and the sheet, all
with lyric text, so it is never committed. The tables printed to stdout carry counts and
line numbers only.

Run from the repo root::

    python scripts/onset_loud_start_probe.py --folder PATH [--out DIR] [--listen] > report.md
"""

import argparse
import copy
import glob
import html
import json
import logging
import sys
from collections import Counter
from pathlib import Path

import numpy as np

# Allow running as ``python scripts/onset_loud_start_probe.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import onset_snap  # noqa: E402
from pikaraoke.lib.cue_align import SOURCE_REALIGN, repace_bad_lines  # noqa: E402
from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.lib.token_align import _normalize_token  # noqa: E402
from pikaraoke.pipeline.config import PipelineConfig  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import generate_ass  # noqa: E402

DOUBTED = frozenset({SOURCE_REALIGN})

# A heard first word is looked for this far either side of the line's cue start.
HEARD_WINDOW_S = 3.0
# A start this far before the heard word is early; this far after, late.
EARLY_S = 0.3
# Two starts closer than this to the heard word are a tie.
TIE_S = 0.05
# The rule under test: a skipped line moves only when the transcriber's first word
# lies within this of the new start.
AGREE_S = 0.25
# A start is the previous line's end when it lies within this of it.
AT_PREVIOUS_END_S = 0.05
# Replayed and recorded line times are equal within this (bundles round to the ms).
REPLAY_TOLERANCE_S = 0.011

# The sheet: this many songs, two lines each.
SHEET_SONGS = 10
# A sheet line plays from this long before the earlier of its two starts.
SHEET_LEAD_S = 4.0
ONSETFIX_SUFFIX = ".onsetfix.ass"
# Marks a line the rule moves, so the real snap searches it as it does a doubted line.
AGREED_SOURCE = "onset_probe_agreed"

BRANCHES = ("on_time", "snapped", "below_min_shift", "no_rise", "narrow", "low_ref")


def heard_first(transcribe_words: list[dict], first_word: str, anchor: float) -> float | None:
    """Start of the heard word equal to ``first_word`` nearest ``anchor``, or None."""
    token = _normalize_token(first_word)
    if not token:
        return None
    starts = [
        w["start"]
        for w in transcribe_words
        if abs(w["start"] - anchor) <= HEARD_WINDOW_S and _normalize_token(w["word"]) == token
    ]
    return min(starts, key=lambda s: abs(s - anchor)) if starts else None


def heard_near(transcribe_words: list[dict], first_word: str, t: float) -> bool:
    """Whether a heard word equal to ``first_word`` starts within ``AGREE_S`` of ``t``."""
    token = _normalize_token(first_word)
    return bool(token) and any(
        abs(w["start"] - t) <= AGREE_S and _normalize_token(w["word"]) == token
        for w in transcribe_words
    )


def rise_start(env: np.ndarray, words: list[dict], ref: float) -> float | None:
    """Where the onset snap would start the line once it searches, or None."""
    w1s = words[0]["start"]
    bound = words[1]["start"] if len(words) >= 2 else words[0]["end"]
    onset = onset_snap._detect_rise(env, w1s, bound, ref, trust_bound=len(words) >= 2)
    if onset is None:
        return None
    new_start = min(max(onset - onset_snap.SNAP_MARGIN_S, w1s), bound - onset_snap.MIN_WORD_DUR_S)
    return new_start if new_start - w1s >= onset_snap.MIN_SHIFT_S else None


def onset_branch(obj: dict, env: np.ndarray) -> tuple[str, float | None]:
    """The exit ``snap_line_onsets`` takes on a worded line, and its sung reference.

    A copy of that function's gates in order; ``replay_song`` checks the copy against
    the real pass on every song it scores.
    """
    words = obj["words"]
    w1s, w1e = words[0]["start"], words[0]["end"]
    bound = words[1]["start"] if len(words) >= 2 else w1e
    if bound - w1s < onset_snap.MIN_WORD_DUR_S:
        return "narrow", None
    ref = onset_snap._sung_level_ref(env, words)
    if ref is None or ref < onset_snap.MIN_REF_DB:
        return "low_ref", ref
    a = min(max(int(w1s / onset_snap.HOP_S), 0), max(len(env) - onset_snap.EDGE_FRAMES, 0))
    span1 = env[a : max(int(w1e / onset_snap.HOP_S), a + 1)]
    if (
        obj.get("source") not in DOUBTED
        and env[a : a + onset_snap.EDGE_FRAMES].mean() >= ref - onset_snap.NEAR_SUNG_DB
        and float(np.median(span1)) >= ref - onset_snap.SUSTAIN_NEAR_DB
    ):
        return "on_time", ref
    if onset_snap._detect_rise(env, w1s, bound, ref, trust_bound=len(words) >= 2) is None:
        return "no_rise", ref
    if rise_start(env, words, ref) is None:
        return "below_min_shift", ref
    return "snapped", ref


def replay_song(bundle: dict, env: np.ndarray) -> tuple[list[dict], list[dict]] | None:
    """A cue-route song's lines before and after the edge snap, or None.

    None when the replay does not reproduce the bundle: a one-line re-align the bundle
    holds no answer for, a line whose times differ from ``output_line_timings``, or a
    different number of onset snaps.
    """
    inputs = bundle["cue_inputs"]
    answers = {
        (r["line_id"], round(r["w0"], 3), round(r["w1"], 3)): r["words"] for r in inputs["realigns"]
    }
    missed: list[tuple] = []

    def realign(lid: int, w0: float, w1: float) -> list[dict] | None:
        key = (lid, round(w0, 3), round(w1, 3))
        if key not in answers:
            missed.append(key)
            return None
        return copy.deepcopy(answers[key])

    before, _ = repace_bad_lines(
        copy.deepcopy(inputs["sections"]),
        [tuple(span) for span in inputs["spans"]],
        bundle["lyrics"]["lines"],
        bundle["lyrics"]["align_lines"],
        duration=bundle.get("media_duration_s"),
        realign=realign,
        env=env,
    )
    after, stats = onset_snap.snap_line_edges(before, "", env=env, doubted_sources=DOUBTED)
    recorded = {line["line_id"]: line for line in bundle["output_line_timings"]}
    for obj in after:
        if not obj.get("words"):
            continue
        rec = recorded.get(obj["line_id"])
        if (
            rec is None
            or abs(rec["start"] - obj["start"]) > REPLAY_TOLERANCE_S
            or abs(rec["end"] - obj["end"]) > REPLAY_TOLERANCE_S
        ):
            return None
    recorded_onset = bundle["joint_stats"]["edge_snap"]["onset"]
    if missed or stats["onset"]["n_snapped"] != recorded_onset["n_snapped"]:
        return None
    snapped = {snap["line_id"] for snap in stats["onset"]["snaps"]}
    for obj in before:
        if obj.get("words") and (onset_branch(obj, env)[0] == "snapped") != (
            obj["line_id"] in snapped
        ):
            raise AssertionError(f"onset_branch disagrees with the snap on line {obj['line_id']}")
    return before, after


def song_rows(bundle: dict, env: np.ndarray, before: list[dict], after: list[dict]) -> list[dict]:
    """One row per worded line: its starts, the snap's exit, and the heard first word."""
    offset = bundle["joint_stats"]["repace"]["offset_s"]
    spans = bundle["cue_inputs"]["spans"]
    heard_words = bundle.get("transcribe_words") or []
    rows: list[dict] = []
    previous_end: float | None = None
    for pre, post in zip(before, after):
        words = pre.get("words") or []
        if not words:
            continue
        lid = pre["line_id"]
        start = words[0]["start"]
        branch, ref = onset_branch(pre, env)
        anchor = spans[lid][0] + offset if lid < len(spans) else start
        rise = rise_start(env, words, ref) if branch == "on_time" else None
        rows.append(
            {
                "line_id": lid,
                "text": pre.get("text", ""),
                "source": pre.get("source"),
                "branch": branch,
                "before": start,
                "after": post["words"][0]["start"],
                "word1_end": words[0]["end"],
                "bound": words[1]["start"] if len(words) >= 2 else words[0]["end"],
                "heard": heard_first(heard_words, words[0]["word"], anchor),
                "at_previous_end": previous_end is not None
                and start - previous_end <= AT_PREVIOUS_END_S,
                "rise": rise,
                "agreed": rise is not None and heard_near(heard_words, words[0]["word"], rise),
            }
        )
        previous_end = words[-1]["end"]
    return rows


def with_rule(before: list[dict], rows: list[dict], env: np.ndarray) -> list[dict]:
    """The song's lines after the edge snap with the rule on.

    Each agreed line is handed to the real snap as a doubted one, so its start moves
    to the same rise and the line before it may extend into the room that frees.
    """
    agreed = {row["line_id"]: row["rise"] for row in rows if row["agreed"]}
    marked = [
        {**obj, "source": AGREED_SOURCE} if obj.get("line_id") in agreed else obj for obj in before
    ]
    after, _ = onset_snap.snap_line_edges(
        marked, "", env=env, doubted_sources=DOUBTED | {AGREED_SOURCE}
    )
    for obj in after:
        rise = agreed.get(obj.get("line_id"))
        if rise is not None and abs(obj["words"][0]["start"] - rise) > 1e-6:
            raise AssertionError(f"line {obj['line_id']} did not move to its rise")
    return after


def sheet_picks(rows: list[dict], songs: set[str]) -> list[dict]:
    """Two agreed lines from each of the ``SHEET_SONGS`` songs in ``songs`` with the most.

    The largest move and the median one; songs by count then name, so the sheet is the
    same on every run over the same library.
    """
    by_song: dict[str, list[dict]] = {}
    for row in rows:
        if row["agreed"] and row["song"] in songs:
            by_song.setdefault(row["song"], []).append(row)
    picks: list[dict] = []
    for song in sorted(by_song, key=lambda name: (-len(by_song[name]), name))[:SHEET_SONGS]:
        moved = sorted(by_song[song], key=lambda r: (r["before"] - r["rise"], r["line_id"]))
        picks += [moved[0], moved[len(moved) // 2]] if len(moved) > 1 else moved
    return picks


def changed_dialogue(shipped: str, fixed: str) -> list[int]:
    """Positions of the Dialogue lines that differ between two subtitle files."""
    old = [line for line in shipped.splitlines() if line.startswith("Dialogue:")]
    new = [line for line in fixed.splitlines() if line.startswith("Dialogue:")]
    if len(old) != len(new):
        raise ValueError("the two files hold different numbers of lines")
    return [i for i, (a, b) in enumerate(zip(old, new)) if a != b]


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def sheet_html(picks: list[dict], videos: dict[str, str]) -> str:
    """The listening sheet: one row per pick, with a play command for each file.

    The commands are run from the library folder. ``videos`` maps a song to its video
    file's name.
    """
    body = []
    for n, row in enumerate(picks, 1):
        start = max(0.0, min(row["before"], row["rise"]) - SHEET_LEAD_S)
        video = html.escape(videos[row["song"]])
        stem = html.escape(row["song"])
        commands = "<br>".join(
            f'<code>mpv --start={start:.1f} --sub-file="karaoke/{stem}{suffix}" "{video}"</code>'
            for suffix in (".ass", ONSETFIX_SUFFIX)
        )
        body.append(
            f"<tr><td>{n}</td><td>{html.escape(row['song'].rsplit('---', 1)[0])}</td>"
            f"<td>{html.escape(row['text'])}</td><td>{_clock(row['before'])}</td>"
            f"<td>{_clock(row['rise'])}</td><td>+{row['rise'] - row['before']:.2f}</td>"
            f"<td>{commands}</td><td></td></tr>"
        )
    return (
        "<!doctype html><meta charset='utf-8'><title>Onset loud start: GATE S</title>"
        "<style>body{font-family:sans-serif}table{border-collapse:collapse}"
        "td,th{border:1px solid #999;padding:4px 8px;vertical-align:top}"
        "code{font-size:12px}</style>"
        "<p>Each line's fill start, shipped and with the rule on. Play each command from "
        "the library folder (shipped first, then fixed) and label the line better, same "
        "or worse; say so when a worse line starts late.</p>"
        "<table><tr><th>#</th><th>Song</th><th>Line</th><th>Shipped start</th>"
        "<th>Fixed start</th><th>Move (s)</th><th>Play: shipped, then fixed</th>"
        "<th>Label</th></tr>" + "".join(body) + "</table>\n"
    )


def compare(row: dict, new_start: float) -> str:
    """Whether ``new_start`` is closer to the heard word than the start before the snap."""
    was = abs(row["heard"] - row["before"])
    now = abs(row["heard"] - new_start)
    if abs(now - was) <= TIE_S:
        return "same"
    return "closer" if now < was else "further"


def snap_stem(folder: Path, stem: str, bundle: dict) -> Path:
    """The stem production snapped against: the de-reverbed one when the gate took it."""
    dry = folder / "dereverb" / f"{stem}---dereverb.m4a"
    if (bundle["joint_stats"].get("dereverb") or {}).get("succeeded") and dry.is_file():
        return dry
    return folder / "vocal" / f"{stem}---vocal.m4a"


def load_env(folder: Path, stem: str, bundle: dict, cache: Path) -> np.ndarray | None:
    """The snap stem's envelope, decoded once and kept in ``cache`` by video id."""
    cached = cache / f"{stem.rsplit('---', 1)[-1]}.npy"
    if cached.is_file():
        return np.load(cached)
    env = onset_snap.decode_env_db(snap_stem(folder, stem, bundle), "onset probe")
    if env is not None:
        cache.mkdir(parents=True, exist_ok=True)
        np.save(cached, env)
    return env


def _moves_line(name: str, moved: list[dict]) -> str:
    scored = [r for r in moved if r["heard"] is not None]
    verdicts = Counter(compare(r, r["rise"]) for r in scored)
    fixed = sum(
        1
        for r in scored
        if r["heard"] - r["before"] > EARLY_S and abs(r["heard"] - r["rise"]) <= EARLY_S
    )
    return (
        f"| {name} | {len(moved)} | {len(scored)} | {verdicts['closer']} | {verdicts['same']} "
        f"| {verdicts['further']} | {fixed} |"
    )


def report(rows: list[dict], n_songs: int, left_out: list[str]) -> str:
    """The tables, as markdown."""
    heard = [r for r in rows if r["heard"] is not None]
    early = [r for r in heard if r["heard"] - r["after"] > EARLY_S]
    late = [r for r in heard if r["after"] - r["heard"] > EARLY_S]
    skipped = [r for r in rows if r["branch"] == "on_time"]
    skipped_early = [r for r in early if r["branch"] == "on_time"]
    out = [
        f"Songs replayed exactly: {n_songs}. Left out: {len(left_out)}.",
        *(f"- left out: {name}" for name in left_out),
        "",
        f"Worded lines {len(rows)}; with a heard first word {len(heard)}; "
        f"early (start more than {EARLY_S} s before it) {len(early)}; late {len(late)}.",
        "",
        "**Table A** lines by the onset snap's exit",
        "",
        "| exit | lines | with heard | early | late |",
        "|---|---|---|---|---|",
    ]
    for branch in BRANCHES:
        out.append(
            f"| {branch} | {sum(1 for r in rows if r['branch'] == branch)} "
            f"| {sum(1 for r in heard if r['branch'] == branch)} "
            f"| {sum(1 for r in early if r['branch'] == branch)} "
            f"| {sum(1 for r in late if r['branch'] == branch)} |"
        )
    out += [
        "",
        f"Skipped as on time and early: {len(skipped_early)}; starting at the previous line's "
        f"end {sum(1 for r in skipped_early if r['at_previous_end'])}; with a rise to move to "
        f"{sum(1 for r in skipped_early if r['rise'] is not None)}; heard word after word 2's "
        f"start {sum(1 for r in skipped_early if r['heard'] > r['bound'] + 0.1)}.",
        "",
        "**Table B** rules for searching a line skipped as on time",
        "",
        "| rule | moved | with heard | closer | same | further | early now within 0.3 s |",
        "|---|---|---|---|---|---|---|",
    ]
    with_rise = [r for r in skipped if r["rise"] is not None]
    out.append(_moves_line("every skipped line", with_rise))
    out.append(
        _moves_line(
            "starts at the previous line's end", [r for r in with_rise if r["at_previous_end"]]
        )
    )
    out.append(
        _moves_line(
            f"heard word within {AGREE_S} s of the rise",
            [
                r
                for r in with_rise
                if r["heard"] is not None and abs(r["heard"] - r["rise"]) <= AGREE_S
            ],
        )
    )
    out.append(
        _moves_line(
            f"a heard first word within {AGREE_S} s of the rise, no cue anchor",
            [r for r in with_rise if r["agreed"]],
        )
    )
    shipped = [r for r in heard if r["branch"] == "snapped"]
    verdicts = Counter(compare(r, r["after"]) for r in shipped)
    out += [
        "",
        "**Table C** the snaps that ship today, by the same reference",
        "",
        f"Snapped lines with a heard word {len(shipped)}: closer {verdicts['closer']}, "
        f"same {verdicts['same']}, further {verdicts['further']}.",
    ]
    return "\n".join(out) + "\n"


def write_listen_files(folder: Path, out: Path, rows: list[dict], fixed_ass: dict[str, str]) -> str:
    """Write the sheet and its songs' after-files; return Table D (no lyric text)."""
    picks = sheet_picks(rows, set(fixed_ass))
    videos: dict[str, str] = {}
    table = [
        "",
        f"**Table D** the listening sheet ({len(picks)} lines; a song is eligible when its "
        f"replay regenerates the shipped subtitle file exactly: {len(fixed_ass)} songs)",
        "",
        "| # | song | line | shipped start | fixed start | lines moved in song "
        "| Dialogue lines changed in song |",
        "|---|---|---|---|---|---|---|",
    ]
    for n, row in enumerate(picks, 1):
        song = row["song"]
        shipped_path = folder / "karaoke" / f"{song}.ass"
        if song not in videos:
            videos[song] = next(
                p.name for p in sorted(folder.glob(f"{glob.escape(song)}.*")) if p.is_file()
            )
            shipped_path.with_name(song + ONSETFIX_SUFFIX).write_text(
                fixed_ass[song], encoding="utf-8"
            )
        changed = changed_dialogue(shipped_path.read_text(encoding="utf-8"), fixed_ass[song])
        table.append(
            f"| {n} | {song.rsplit('---', 1)[-1]} | {row['line_id']} | {row['before']:.2f} "
            f"| {row['rise']:.2f} | {sum(1 for r in rows if r['song'] == song and r['agreed'])} "
            f"| {len(changed)} |"
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / "listening-sheet.html").write_text(sheet_html(picks, videos), encoding="utf-8")
    return "\n".join(table) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--folder", type=Path, required=True, help="the song library")
    parser.add_argument("--out", type=Path, default=Path(get_temp_directory()) / "onset_loud_start")
    parser.add_argument(
        "--listen",
        action="store_true",
        help="write the listening sheet and each sheet song's karaoke/<stem>.onsetfix.ass",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    rows: list[dict] = []
    left_out: list[str] = []
    fixed_ass: dict[str, str] = {}
    config = PipelineConfig()
    n_songs = 0
    for path in sorted((args.folder / "alignment_debug").glob("*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        if (bundle.get("pipeline_decisions") or {}).get("method_used") != "cue_align":
            continue
        env = load_env(args.folder, path.stem, bundle, args.out / "env")
        replayed = replay_song(bundle, env) if env is not None else None
        if replayed is None:
            left_out.append(path.stem)
            continue
        n_songs += 1
        before, after = replayed
        song = song_rows(bundle, env, before, after)
        rows += [{"song": path.stem, **row} for row in song]
        shipped = args.folder / "karaoke" / f"{path.stem}.ass"
        # The after-file is only a clean A/B when the replay regenerates the shipped one.
        if (
            args.listen
            and shipped.is_file()
            and shipped.read_text(encoding="utf-8") == generate_ass(after, config)
        ):
            fixed_ass[path.stem] = generate_ass(with_rule(before, song, env), config)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    sys.stdout.write(report(rows, n_songs, left_out))
    if args.listen:
        sys.stdout.write(write_listen_files(args.folder, args.out, rows, fixed_ass))
    return 0


if __name__ == "__main__":
    sys.exit(main())
