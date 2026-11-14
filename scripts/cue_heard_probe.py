#!/usr/bin/env python3
"""Probe the cue rescue's heard-words rules over a library's saved alignment bundles.

For every bundle on the cue route (``cue_inputs`` and ``transcribe_words``) the rescue
(``cue_align.repace_bad_lines``) is replayed twice from what the bundle saved, then the
edge snap runs on each, as the pipeline stage does:

* the **baseline**, with no heard words and without rule C and the zero-length rule
  (nothing in ``repace_bad_lines`` switches those off, so the probe patches them out for
  this replay only). It must equal the bundle's ``output_line_timings`` within
  ``TOLERANCE_S``; a song it does not reproduce is left out of every table and named in
  Table P;
* the **new** replay, with the song's ``transcribe_words`` and every rule on.

The saved one-line re-aligns answer the ``realign`` calls by ``(line, w0, w1)``. A call the
bundle holds no answer for (a window only the new rules ask about) returns None and is
recorded: that line's result needs the GPU.

The snap stem is ``dereverb/<stem>---dereverb.m4a`` when the bundle records a successful
de-reverb, else ``vocal/<stem>---vocal.m4a``, decoded the way the pipeline does (44.1 kHz
stereo WAV, then the 16 kHz envelope; the pipeline stage's own ``_wav_duration`` gives the
audio length). The envelope is cached under ``--out``. The library is only read.

Tables go to stdout as markdown; ``--out`` also gets ``rows.json`` (every table row, with
the lyric line's text) which is never committed.

``--stage DIR --song ID...`` (a YouTube id, or the whole stem for a file without one) instead copies those songs (video, stems, bundle and the
other files ``library_regen.song_files`` lists) into a copy library at ``DIR``, taking each
from the first ``--from`` folder that has it, else from ``--folder``.

Run from the repo root::

    python scripts/cue_heard_probe.py [--folder PATH] [--out PATH] > report.md
    python scripts/cue_heard_probe.py --stage DIR --song ID... [--from DIR]... [--folder PATH]
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import numpy as np

# Allow running as ``python scripts/cue_heard_probe.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import cue_align, heard_lines  # noqa: E402
from pikaraoke.lib.get_platform import (  # noqa: E402
    get_default_dl_dir,
    get_platform,
    get_temp_directory,
)
from pikaraoke.lib.library_regen import (  # noqa: E402
    list_videos,
    read_bundle,
    song_files,
)
from pikaraoke.lib.metadata_parser import extract_youtube_id  # noqa: E402
from pikaraoke.lib.onset_snap import rms_envelope_db, snap_line_edges  # noqa: E402
from pikaraoke.lib.token_align import INSTANT_WORD_DUR_S  # noqa: E402
from pikaraoke.pipeline.stages.lyric_align import _wav_duration  # noqa: E402

# A replay equals the bundle when every start and end is this close: one envelope frame
# (0.025 s). The envelope decoded here is not bit-identical to the bundle's, and the edge
# snap lands a frame off on some edges; the bundle's own rounding is far smaller.
TOLERANCE_S = 0.026

# Table O lists a line whose start or end moves more than this between the two replays
# (both read the same envelope, so a frame of decode noise does not enter).
MOVED_S = 0.011

# A saved re-align answers a call whose window is this close to the one it was made over.
WINDOW_MATCH_S = 1e-6

# Table B: a line whose first heard word starts this long before its second is probably a
# lead the transcriber heard alone, so the heard start may not be the line's.
LONE_FIRST_WORD_S = 2.0

# Table V: the thresholds it sizes Table A at, as (HEARD_AGREE_S, HEARD_MIN_WORDS).
V_GRID = [(agree, words) for words in (2, 3) for agree in (0.5, 1.0, 1.5)]

# Table Z: a word still shorter than this after the rescue is as good as untimed.
SHORT_WORD_S = 0.1

CAPTION = "caption"
LRCLIB = "LRCLIB"
KINDS = (CAPTION, LRCLIB)


@dataclass(frozen=True)
class Song:
    stem: str
    kind: str
    bundle: dict


@dataclass(frozen=True)
class Call:
    """One ``realign`` call the rescue made, and whether the bundle held its answer."""

    line_id: int
    w0: float
    w1: float
    answered: bool


@dataclass
class Replay:
    """One replay: the lines the rescue gave (``pre``), after the edge snap (``final``),
    its stats and its ``realign`` calls in order. Lines are keyed by ``line_id``."""

    pre: dict[int, dict]
    final: dict[int, dict]
    stats: dict
    calls: list[Call]

    def calls_for(self, lid: int) -> list[Call]:
        return [call for call in self.calls if call.line_id == lid]


@dataclass(frozen=True)
class LeftOut:
    song: Song
    reason: str


@dataclass(frozen=True)
class Deviation:
    """The largest way a replay differs from the bundle's ``output_line_timings``."""

    line_id: int
    field: str
    amount: float

    def __str__(self) -> str:
        unit = " words" if self.field == "n_words" else " s"
        return f"line {self.line_id} {self.field} off by {self.amount:.3f}{unit}"


@dataclass
class Analysed:
    song: Song
    rows: dict[str, list[dict]]
    d_unaimed: Counter
    a_counts: dict[tuple[float, int], tuple[int, int]]


# ---------------------------------------------------------------------------
# Songs and stems
# ---------------------------------------------------------------------------


def cue_route_songs(folder: Path) -> list[Song]:
    """Every bundle in ``folder`` with ``cue_inputs`` and ``transcribe_words``, by stem."""
    debug = folder / "alignment_debug"
    songs = []
    for path in sorted(debug.glob("*.json")) if debug.is_dir() else []:
        bundle = read_bundle(folder, path.stem)
        if not bundle or not bundle.get("cue_inputs") or bundle.get("transcribe_words") is None:
            continue
        origin = (bundle.get("lyrics") or {}).get("origin") or ""
        songs.append(Song(path.stem, LRCLIB if origin.startswith("lrclib") else CAPTION, bundle))
    return songs


def snap_stem(folder: Path, song: Song) -> Path:
    """The stem the pipeline aligned and snapped against: the de-reverbed one when the
    bundle records that the de-reverb retry succeeded, else the vocal stem."""
    dereverb = (song.bundle.get("joint_stats") or {}).get("dereverb") or {}
    kind = "dereverb" if dereverb.get("succeeded") else "vocal"
    return folder / kind / f"{song.stem}---{kind}.m4a"


def decode_stem(stem_file: Path) -> tuple[np.ndarray, float]:
    """The stem's dB envelope and length in seconds, decoded as ``LoadVocalFromM4aStage``
    and the lyric stage do (a 44.1 kHz stereo WAV first, which the envelope then reads)."""
    with tempfile.TemporaryDirectory(dir=get_temp_directory()) as work:
        wav = Path(work) / "stem.wav"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(stem_file)]
        cmd += ["-ac", "2", "-ar", "44100", "-sample_fmt", "s16", str(wav)]
        subprocess.run(cmd, check=True, capture_output=True)
        return rms_envelope_db(wav), _wav_duration(wav)


def load_envelope(stem_file: Path, cache_dir: Path) -> tuple[np.ndarray, float]:
    """:func:`decode_stem`, cached under ``cache_dir`` until the stem file changes."""
    cache = cache_dir / f"{stem_file.stem}.npz"
    if cache.is_file() and cache.stat().st_mtime >= stem_file.stat().st_mtime:
        saved = np.load(cache)
        return saved["env"], float(saved["duration"])
    env, duration = decode_stem(stem_file)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez(cache, env=env, duration=duration)
    return env, duration


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


class Answers:
    """The bundle's saved one-line re-aligns, standing in for the aligner.

    A call is answered by ``(line, w0, w1)``: a line can be aligned twice over different
    windows. A call with no saved answer returns None, as a failed align does, and is
    recorded as unanswered.
    """

    def __init__(self, saved: list[dict]):
        self.saved = saved
        self.calls: list[Call] = []

    def __call__(self, lid: int, w0: float, w1: float) -> list[dict] | None:
        for rec in self.saved:
            if (
                rec["line_id"] == lid
                and abs(rec["w0"] - w0) < WINDOW_MATCH_S
                and abs(rec["w1"] - w1) < WINDOW_MATCH_S
            ):
                self.calls.append(Call(lid, w0, w1, True))
                return copy.deepcopy(rec["words"])
        self.calls.append(Call(lid, w0, w1, False))
        return None


@contextmanager
def before_rule_c_and_zero_length() -> Iterator[None]:
    """The rescue as it stood before rule C and the zero-length rule, for the baseline.

    Neither has a switch in ``repace_bad_lines`` and neither may get one, so they are
    patched out here: rule C finds nothing, and a line with a word for every token is
    not looked at by the guess pass.
    """
    timed_slots = cue_align._timed_slots

    def by_count(words: list[dict], toks: list) -> list:
        return list(words) if len(words) == len(toks) else timed_slots(words, toks)

    with patch.object(cue_align, "_timed_slots", by_count), patch.object(
        cue_align._Rescue, "gap_retry_line", return_value=None
    ):
        yield


def rescue_song(
    song: Song, env: np.ndarray, duration: float, answers: Answers, *, heard: bool
) -> tuple[dict[int, dict], dict]:
    """``repace_bad_lines`` over the bundle's saved first pass: with the transcriber's
    words and every rule (``heard``), else as the bundles were made."""
    bundle, cue_inputs = song.bundle, song.bundle["cue_inputs"]
    spans = [tuple(span) for span in cue_inputs["spans"]]
    with nullcontext() if heard else before_rule_c_and_zero_length():
        out, stats = cue_align.repace_bad_lines(
            copy.deepcopy(cue_inputs["sections"]),
            spans,
            bundle["lyrics"]["lines"],
            bundle["lyrics"]["align_lines"],
            duration=duration,
            realign=answers,
            env=env,
            heard_words=bundle["transcribe_words"] if heard else None,
        )
    return {obj["line_id"]: obj for obj in out}, stats


def replay(song: Song, stem_file: Path, env: np.ndarray, duration: float, *, heard: bool) -> Replay:
    """One full replay: the rescue, then the edge snap the lyric stage runs after it."""
    answers = Answers(song.bundle["cue_inputs"]["realigns"])
    pre, stats = rescue_song(song, env, duration, answers, heard=heard)
    snapped, _ = snap_line_edges(
        copy.deepcopy(list(pre.values())),
        stem_file,
        env=env,
        doubted_sources=frozenset({cue_align.SOURCE_REALIGN}),
    )
    return Replay(pre, {obj["line_id"]: obj for obj in snapped}, stats, answers.calls)


def moved(before: float | None, after: float | None) -> float:
    """How far a line edge moved (inf when it appeared or vanished)."""
    if before is None or after is None:
        return 0.0 if before is None and after is None else math.inf
    return abs(after - before)


def worst_deviation(final: dict[int, dict], saved: list[dict]) -> Deviation | None:
    """The largest difference above :data:`TOLERANCE_S` between ``final`` and the bundle's
    ``output_line_timings`` (start, end or word count), or None when they agree."""
    if set(final) != {rec["line_id"] for rec in saved}:
        return Deviation(-1, "line ids", math.inf)
    worst: Deviation | None = None
    for rec in saved:
        line = final[rec["line_id"]]
        found = [
            Deviation(rec["line_id"], field, moved(rec[field], line[field]))
            for field in ("start", "end")
        ]
        found.append(Deviation(rec["line_id"], "n_words", abs(rec["n_words"] - len(line["words"]))))
        for dev in found:
            if dev.amount > TOLERANCE_S and (worst is None or dev.amount > worst.amount):
                worst = dev
    return worst


# ---------------------------------------------------------------------------
# Table rows
# ---------------------------------------------------------------------------


def label(stem: str) -> str:
    """A short song name for a table: the title part and the YouTube id, or the whole stem
    when the file has no id (several songs would otherwise share a label)."""
    video_id = extract_youtube_id(stem)
    if video_id is None:
        return stem.replace("|", "/")
    return f"{stem.split('---')[0].replace('|', '/')[:30]} {video_id}"


@dataclass
class Ctx:
    """What one song's row builders read."""

    song: Song
    rescue: cue_align._Rescue
    first: dict[int, dict]
    today: Replay
    new: Replay

    def row(self, lid: int, **fields) -> dict:
        return {
            "src": self.song.kind,
            "song": label(self.song.stem),
            "line": lid,
            "text": self.rescue.display_lines[lid],
            **fields,
        }

    def cue(self, lid: int) -> float:
        return self.rescue.cue_spans[lid][0]

    def start(self, replay: Replay, lid: int) -> float | None:
        return replay.final[lid]["start"]

    def in_run(self, lid: int) -> bool:
        return lid in self.rescue.repeat_slacks

    def ids(self, key: str) -> list[int]:
        return self.new.stats[key]


def inner_gap_one_side(line: dict, heard: heard_lines.HeardLine) -> bool:
    """Whether ``line`` has a gap of over :data:`cue_align.DRIFT_GAP_S` between two of its
    words and every heard word starts on one side of that gap's middle."""
    words = line["words"]
    gaps = [(b["start"] - a["end"], (a["end"] + b["start"]) / 2) for a, b in zip(words, words[1:])]
    if not gaps or max(gaps)[0] <= cue_align.DRIFT_GAP_S:
        return False
    middle = max(gaps)[1]
    starts = [w["start"] for w in heard.words]
    return all(s < middle for s in starts) or all(s >= middle for s in starts)


def previous_end(ctx: Ctx, lid: int) -> float | None:
    """The end of the nearest line before ``lid`` that has words, as the new replay left it."""
    return next(
        (ctx.new.final[i]["end"] for i in range(lid - 1, -1, -1) if ctx.new.final[i]["words"]),
        None,
    )


def rows_a(ctx: Ctx) -> list[dict]:
    """Lines rule A1 keeps and rule A2 holds."""
    rows = []
    for rule, key in (("A1", "heard_kept_line_ids"), ("A2", "heard_held_line_ids")):
        for lid in ctx.ids(key):
            heard = ctx.rescue.heard[lid]
            rows.append(
                ctx.row(
                    lid,
                    rule=rule,
                    cue=ctx.cue(lid),
                    today=ctx.start(ctx.today, lid),
                    new=ctx.start(ctx.new, lid),
                    heard=heard.start,
                    run=ctx.in_run(lid),
                    gap_side=inner_gap_one_side(ctx.first[lid], heard),
                )
            )
    return rows


def rows_g(ctx: Ctx) -> list[dict]:
    """Starts the guard lift freed of the previous line."""
    return [
        ctx.row(
            lid,
            cue=ctx.cue(lid),
            today=ctx.start(ctx.today, lid),
            new=ctx.start(ctx.new, lid),
            heard=ctx.rescue.heard[lid].start,
            previous_end=previous_end(ctx, lid),
        )
        for lid in ctx.ids("guard_lifted_line_ids")
    ]


def rows_z(ctx: Ctx) -> list[dict]:
    """Kept lines (first pass or re-align) with a word for every token, some zero-length as
    the baseline rescue left them, that the zero-length rule re-timed."""
    rows = []
    for lid in ctx.ids("guessed_word_line_ids"):
        before, after = ctx.today.pre[lid], ctx.new.pre[lid]
        n_tokens = len(ctx.rescue.line_toks[lid])
        zero = sum(1 for w in before["words"] if w["end"] - w["start"] < INSTANT_WORD_DUR_S)
        if len(before["words"]) != n_tokens or not zero or after["source"] != before["source"]:
            continue
        retimed = sum(
            1
            for b, a in zip(before["words"], after["words"])
            if (b["start"], b["end"]) != (a["start"], a["end"])
        )
        short = sum(1 for w in ctx.new.final[lid]["words"] if w["end"] - w["start"] < SHORT_WORD_S)
        rows.append(ctx.row(lid, tokens=n_tokens, zero_length=zero, retimed=retimed, short=short))
    return rows


def rows_b(ctx: Ctx) -> list[dict]:
    """Lines rule B aimed where they were heard."""
    rows = []
    kept = set(ctx.ids("heard_aimed_kept_line_ids"))
    for lid in ctx.ids("heard_aimed_line_ids"):
        heard = ctx.rescue.heard[lid]
        call = ctx.new.calls_for(lid)[0]
        rows.append(
            ctx.row(
                lid,
                cue=ctx.cue(lid) + ctx.rescue.offset,
                heard=heard.start,
                shift=heard.start - ctx.rescue.audio_spans[lid][0],
                window=(call.w0, call.w1),
                lone_first=len(heard.words) > 1
                and heard.words[1]["start"] - heard.start >= LONE_FIRST_WORD_S,
                answered=call.answered,
                kept=lid in kept,
                today=ctx.start(ctx.today, lid),
                new=ctx.start(ctx.new, lid),
            )
        )
    return rows


def rows_d(ctx: Ctx) -> list[dict]:
    """Lines rule D aimed where they were heard."""
    rows = []
    kept = set(ctx.ids("whole_aimed_kept_line_ids"))
    for lid in ctx.ids("whole_aimed_line_ids"):
        heard = ctx.rescue.heard[lid]
        offsets = heard_lines.pair_offsets(ctx.first[lid], len(ctx.rescue.line_toks[lid]), heard)
        rows.append(
            ctx.row(
                lid,
                today=ctx.start(ctx.today, lid),
                heard=heard.start,
                pairs=len(offsets),
                smallest=min(offsets),
                largest=max(offsets),
                run=ctx.in_run(lid),
                answered=ctx.new.calls_for(lid)[0].answered,
                kept=lid in kept,
                new=ctx.start(ctx.new, lid),
            )
        )
    return rows


def d_unaimed_reason(ctx: Ctx, lid: int) -> str | None:
    """Why rule D did not aim line ``lid``, a complete line the rescue left alone that is
    heard and not confirmed; None for any other line."""
    first, heard = ctx.first[lid], ctx.rescue.heard[lid]
    n_tokens = len(ctx.rescue.line_toks[lid])
    if (
        heard is None
        or lid in ctx.ids("whole_aimed_line_ids")
        or ctx.new.pre[lid] != first
        or cue_align._timed_words(first["words"]) < n_tokens
        or ctx.rescue.confirmed(first)
    ):
        return None
    if not heard.first:
        return "first token unheard"
    if not ctx.rescue.run_heard[lid]:
        return "run not heard in full"
    offsets = heard_lines.pair_offsets(first, n_tokens, heard)
    if offsets is None:
        return "too few pairs"
    if any(abs(off) < cue_align.HEARD_SHIFT_S for off in offsets):
        return "some pair under 1.5 s"
    if min(offsets) < 0 < max(offsets):
        return "pairs off both ways"
    return "trigger held, not aimed"


def rows_c(ctx: Ctx) -> list[dict]:
    """Lines rule C looked for between their neighbours."""
    rows = []
    kept = set(ctx.ids("gap_retry_kept_line_ids"))
    for lid in ctx.ids("gap_retry_line_ids"):
        call = ctx.new.calls_for(lid)[-1]
        aimable = ctx.rescue.aimable(lid)
        rows.append(
            ctx.row(
                lid,
                cue=ctx.cue(lid) + ctx.rescue.offset,
                stretch=(call.w0, call.w1),
                length=call.w1 - call.w0,
                heard_shift=None
                if aimable is None
                else aimable.start - ctx.rescue.audio_spans[lid][0],
                run=ctx.in_run(lid),
                answered=call.answered,
                kept=lid in kept,
                today=ctx.start(ctx.today, lid),
                new=ctx.start(ctx.new, lid),
            )
        )
    return rows


def rows_o(ctx: Ctx, claimed: set[int]) -> list[dict]:
    """Every line outside the rules' own lists whose start or end moved."""
    rows = []
    for lid, new in ctx.new.final.items():
        today = ctx.today.final[lid]
        amount = max(moved(today["start"], new["start"]), moved(today["end"], new["end"]))
        if lid not in claimed and amount > MOVED_S:
            rows.append(
                ctx.row(
                    lid,
                    start_today=today["start"],
                    start_new=new["start"],
                    end_today=today["end"],
                    end_new=new["end"],
                    moved=amount,
                )
            )
    return rows


def a_counts(
    song: Song, env: np.ndarray, duration: float
) -> dict[tuple[float, int], tuple[int, int]]:
    """Table A's counts (lines A1 keeps, lines A2 holds) at each :data:`V_GRID` threshold."""
    counts = {}
    for agree, words in V_GRID:
        with patch.object(heard_lines, "HEARD_AGREE_S", agree), patch.object(
            heard_lines, "HEARD_MIN_WORDS", words
        ):
            _, stats = rescue_song(
                song, env, duration, Answers(song.bundle["cue_inputs"]["realigns"]), heard=True
            )
        counts[(agree, words)] = (
            len(stats["heard_kept_line_ids"]),
            len(stats["heard_held_line_ids"]),
        )
    return counts


def analyse_song(folder: Path, cache_dir: Path, song: Song) -> Analysed | LeftOut:
    """Replay one song; its table rows, or why it is left out."""
    stem_file = snap_stem(folder, song)
    if not stem_file.is_file():
        return LeftOut(song, f"stem missing: {stem_file.parent.name}/{stem_file.name}")
    try:
        env, duration = load_envelope(stem_file, cache_dir)
    except (subprocess.CalledProcessError, OSError, ValueError, wave.Error, EOFError) as exc:
        return LeftOut(song, f"stem unreadable: {exc.__class__.__name__}")
    today = replay(song, stem_file, env, duration, heard=False)
    deviation = worst_deviation(today.final, song.bundle["output_line_timings"])
    if deviation is not None:
        return LeftOut(song, f"baseline replay differs: {deviation}")
    new = replay(song, stem_file, env, duration, heard=True)
    cue_inputs, lyrics = song.bundle["cue_inputs"], song.bundle["lyrics"]
    rescue = cue_align._Rescue(
        cue_inputs["sections"],
        [tuple(span) for span in cue_inputs["spans"]],
        lyrics["lines"],
        lyrics["align_lines"],
        song.bundle["transcribe_words"],
        drift_gap_s=cue_align.DRIFT_GAP_S,
        min_anchors=cue_align.CUE_MIN_ANCHORS,
        max_word_dur=cue_align.MAX_WORD_DUR_S,
        duration=duration,
        realign=None,
        env=env,
        pad_s=cue_align.SECTION_PAD_S,
    )
    ctx = Ctx(song, rescue, {obj["line_id"]: obj for obj in cue_inputs["sections"]}, today, new)
    rows = {
        "A": rows_a(ctx),
        "G": rows_g(ctx),
        "Z": rows_z(ctx),
        "B": rows_b(ctx),
        "D": rows_d(ctx),
        "C": rows_c(ctx),
    }
    claimed = {row["line"] for table in rows.values() for row in table}
    rows["O"] = rows_o(ctx, claimed)
    unaimed = Counter(
        reason for lid in ctx.new.pre if (reason := d_unaimed_reason(ctx, lid)) is not None
    )
    return Analysed(song, rows, unaimed, a_counts(song, env, duration))


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

# Table letter -> (title, note, [(header, row key)]).
TABLES = {
    "A": (
        "Table A: lines rule A1 keeps and rule A2 holds",
        "Starts in seconds on the cue clock (cue) and the audio clock (the rest). "
        "Run: in a run of identical lines. Gap one side: an inner gap over 2 s with every "
        "heard word on one side of it.",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Rule", "rule"),
            ("Cue", "cue"),
            ("Today", "today"),
            ("New", "new"),
            ("Heard", "heard"),
            ("Run", "run"),
            ("Gap one side", "gap_side"),
        ],
    ),
    "G": (
        "Table G: starts the guard lift freed of the previous line",
        "Previous end: the previous line's end in the new replay.",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Cue", "cue"),
            ("Today", "today"),
            ("New", "new"),
            ("Heard", "heard"),
            ("Previous end", "previous_end"),
        ],
    ),
    "Z": (
        "Table Z: zero-length words re-timed",
        "Zero-length: words under 0.05 s in the line as the baseline rescue left it. Re-timed: "
        "words whose times the zero-length rule changed. Short after: words under 0.1 s in the snapped line.",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Tokens", "tokens"),
            ("Zero-length", "zero_length"),
            ("Re-timed", "retimed"),
            ("Short after", "short"),
        ],
    ),
    "B": (
        "Table B: lines rule B aimed where they were heard",
        "Cue: start + offset. Shift: heard start - cue. Window: the heard-aimed align's "
        "slice. Lone first: the first heard word starts 2 s or more before the second. "
        "Answered: the bundle holds this align's result; if not, the line needs the GPU.",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Cue", "cue"),
            ("Heard", "heard"),
            ("Shift", "shift"),
            ("Window", "window"),
            ("Lone first", "lone_first"),
            ("Answered", "answered"),
            ("Kept", "kept"),
            ("Today", "today"),
            ("New", "new"),
        ],
    ),
    "D": (
        "Table D: lines rule D aimed where they were heard",
        "Smallest and largest: signed pair offsets (heard - placed).",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Today", "today"),
            ("Heard", "heard"),
            ("Pairs", "pairs"),
            ("Smallest", "smallest"),
            ("Largest", "largest"),
            ("Run", "run"),
            ("Answered", "answered"),
            ("Kept", "kept"),
            ("New", "new"),
        ],
    ),
    "C": (
        "Table C: lines rule C looked for between their neighbours",
        "Heard shift: heard start - cue start on the audio clock; blank when the line is not "
        "heard, its first token is not matched or its run is not heard in full.",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Cue", "cue"),
            ("Stretch", "stretch"),
            ("Length", "length"),
            ("Heard shift", "heard_shift"),
            ("Run", "run"),
            ("Answered", "answered"),
            ("Kept", "kept"),
            ("Today", "today"),
            ("New", "new"),
        ],
    ),
    "O": (
        "Table O: other lines whose start or end moved",
        "Lines outside Tables A, G, Z, B, D and C.",
        [
            ("Src", "src"),
            ("Song", "song"),
            ("Line", "line"),
            ("Start today", "start_today"),
            ("Start new", "start_new"),
            ("End today", "end_today"),
            ("End new", "end_new"),
            ("Moved", "moved"),
        ],
    ),
}

D_REASONS = (
    "first token unheard",
    "run not heard in full",
    "too few pairs",
    "some pair under 1.5 s",
    "pairs off both ways",
    "trigger held, not aimed",
)


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else ""
    if isinstance(value, float):
        return "inf" if math.isinf(value) else f"{value:.3f}"
    if isinstance(value, tuple):
        return "-".join(fmt(v) for v in value)
    return str(value)


def markdown_table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(fmt(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def tally(rows: list[dict]) -> str:
    """``caption: N lines in M songs; LRCLIB: ...``"""
    parts = []
    for kind in KINDS:
        mine = [row for row in rows if row["src"] == kind]
        parts.append(f"{kind}: {len(mine)} lines in {len({row['song'] for row in mine})} songs")
    return "; ".join(parts)


def table_p(analysed: list[Analysed], left_out: list[LeftOut], n_read: Counter) -> str:
    rows = [
        [
            kind,
            n_read[kind],
            sum(a.song.kind == kind for a in analysed),
            sum(lo.song.kind == kind for lo in left_out),
        ]
        for kind in KINDS
    ]
    text = [
        "### Table P: songs read, replayed and left out",
        "A song is left out when its stem is missing or unreadable, or its baseline replay "
        f"differs from the bundle's output_line_timings by more than {TOLERANCE_S} s.",
        "",
        markdown_table(["Src", "Read", "Replayed", "Left out"], rows),
    ]
    if left_out:
        text += [
            "",
            markdown_table(
                ["Src", "Song", "Why"],
                [[lo.song.kind, label(lo.song.stem), lo.reason] for lo in left_out],
            ),
        ]
    return "\n".join(text)


def table_d_unaimed(analysed: list[Analysed]) -> str:
    rows = [
        [
            kind,
            *(
                sum(a.d_unaimed[reason] for a in analysed if a.song.kind == kind)
                for reason in D_REASONS
            ),
        ]
        for kind in KINDS
    ]
    return "\n".join(
        [
            "Complete lines the rescue left alone, heard and not confirmed, that rule D did "
            "not aim, by why:",
            "",
            markdown_table(["Src", *D_REASONS], rows),
        ]
    )


def table_v(analysed: list[Analysed]) -> str:
    rows = []
    for agree, words in V_GRID:
        counts = [
            sum(a.a_counts[(agree, words)][i] for a in analysed if a.song.kind == kind)
            for kind in KINDS
            for i in (0, 1)
        ]
        rows.append([agree, words, *counts])
    headers = ["HEARD_AGREE_S", "HEARD_MIN_WORDS"]
    headers += [f"{kind} {rule}" for kind in KINDS for rule in ("A1 kept", "A2 held")]
    return "\n".join(
        [
            "### Table V: Table A's counts at other thresholds (sizing only)",
            "",
            markdown_table(headers, rows),
        ]
    )


def report(
    analysed: list[Analysed], left_out: list[LeftOut], n_read: Counter
) -> tuple[str, list[dict]]:
    """The markdown report, and every table row tagged with its table, for ``rows.json``."""
    sections = [table_p(analysed, left_out, n_read)]
    all_rows: list[dict] = []
    for letter, (title, note, columns) in TABLES.items():
        rows = sorted(
            (row for a in analysed for row in a.rows[letter]),
            key=lambda row: (KINDS.index(row["src"]), row["song"], row["line"]),
        )
        all_rows += [{"table": letter, **row} for row in rows]
        body = markdown_table(
            [h for h, _ in columns], [[row[k] for _, k in columns] for row in rows]
        )
        sections.append(f"### {title}\n{note}\n\n{tally(rows)}\n\n{body}")
        if letter == "D":
            sections.append(table_d_unaimed(analysed))
    sections.append(table_v(analysed))
    return "\n\n".join(sections) + "\n", all_rows


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def find_video(sources: list[Path], song: str) -> Path:
    """The video whose YouTube id or whole stem is ``song``, in the first of ``sources`` that
    has one."""
    for source in sources:
        hits = [v for v in list_videos(source) if song in (v.stem, extract_youtube_id(v.name))]
        if len(hits) > 1:
            raise ValueError(f"{song} matches several videos in {source}: {hits}")
        if hits:
            return hits[0]
    raise ValueError(f"No video with id or stem {song} in {', '.join(map(str, sources))}")


def stage_songs(songs: list[str], sources: list[Path], dest: Path) -> list[Path]:
    """Copy each song (video, stems, bundle and the other ``song_files``) into ``dest``."""
    staged = []
    for song in songs:
        video = find_video(sources, song)
        for path in [video, *song_files(video)]:
            target = dest / path.relative_to(video.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        staged.append(video)
    return staged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_probe(folder: Path, out: Path) -> str:
    """Replay every cue-route song of ``folder``; the report text. ``out`` gets the
    envelope cache, ``rows.json`` and a ``started`` marker."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "started").touch()
    songs = cue_route_songs(folder)
    analysed: list[Analysed] = []
    left_out: list[LeftOut] = []
    for i, song in enumerate(songs, 1):
        print(f"[{i}/{len(songs)}] {song.stem}", file=sys.stderr)
        result = analyse_song(folder, out / "env", song)
        (left_out if isinstance(result, LeftOut) else analysed).append(result)
    text, rows = report(analysed, left_out, Counter(song.kind for song in songs))
    (out / "rows.json").write_text(
        json.dumps(rows, indent=1, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, help="library folder (default: the download dir)")
    parser.add_argument(
        "--out", type=Path, help="scratch folder (default: <temp>/cue_heard_rescue)"
    )
    parser.add_argument("--stage", type=Path, metavar="DIR", help="copy the --song songs to DIR")
    parser.add_argument(
        "--song", nargs="+", metavar="ID", default=[], help="YouTube ids (or whole stems) to stage"
    )
    parser.add_argument(
        "--from",
        dest="sources",
        type=Path,
        action="append",
        default=[],
        metavar="DIR",
        help="folder to take a staged song from before --folder (repeatable)",
    )
    args = parser.parse_args()
    folder = args.folder or Path(os.path.expanduser(get_default_dl_dir(get_platform())))
    if args.stage:
        if not args.song:
            parser.error("--stage needs --song ID...")
        try:
            staged = stage_songs(args.song, [*args.sources, folder], args.stage)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Staged {len(staged)} songs into {args.stage}")
        return 0
    if args.song or args.sources:
        parser.error("--song and --from only go with --stage")
    out = args.out or Path(get_temp_directory()) / "cue_heard_rescue"
    sys.stdout.write(run_probe(folder, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
