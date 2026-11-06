#!/usr/bin/env python3
"""GATE M measurement for plans/lrclib-auto-timing.md: would a fixed-shape bar let a
downloaded song be timed from an LRCLIB match, and is every match it accepts timed to
this video?

For each song in a group the library can answer for, every synced LRCLIB record the
search returns (plus the song's own ``.lrc`` when it has one) is fitted to the clip's
heard words with the Repair fit (``srt_slice_fit``). Songs timed from an uploader
caption (``ref``) have an independent reference: the caption is timed to the video and
is no input to the fit, so each accepted record is classed against it (``right``,
``wrong_timing``, ``hole``, ``unjudged``). The bar is then swept over a fixed grid.
Everything the run writes goes under ``--out``; the library is never written.

``--out`` holds lyric text (the LRCLIB cache, the eyeball sheets), so it is never
committed. The tables printed to stdout carry line numbers and counts, never text.

Run from the repo root::

    python scripts/lrc_auto_timing_probe.py --folder PATH [--out DIR] > DIR/report.md
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import logging
import math
import os
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from statistics import median
from typing import NamedTuple

import srt

# Allow running as ``python scripts/lrc_auto_timing_probe.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import lrclib, srt_slice_fit  # noqa: E402
from pikaraoke.lib.get_platform import (  # noqa: E402
    get_default_dl_dir,
    get_platform,
    get_temp_directory,
)
from pikaraoke.lib.library_regen import (  # noqa: E402
    LRC_ORIGIN,
    SongJob,
    default_query,
    media_duration,
    read_bundle,
)
from pikaraoke.lib.library_status import (  # noqa: E402
    SongStatus,
    length_gap_s,
    library_statuses,
)
from pikaraoke.lib.srt_cues import cue_spans_from_srt  # noqa: E402
from pikaraoke.lib.srt_slice_fit import (  # noqa: E402
    ASR,
    FITS,
    MIN_FLAGGED_RUN,
    MIN_UNHEARD_RUN,
    TRANSCRIBE,
    SliceFit,
    fit_slice,
    flagged_runs,
    heard_streams,
    lrc_to_srt,
    unheard_runs,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

REF, JOINT, REPAIR, KNOWN = "ref", "joint", "repair", "known"
OUT_OF_SCOPE = "out_of_scope"
NO_LENGTH = "no_length"
LRCLIB_UNAVAILABLE = "lrclib_unavailable"

# The LRCs known to time another edit than the video's, by YouTube ID: their id on disk
# must still be the one the plan names, or the label no longer applies.
KNOWN_BAD_LRC_IDS = {"AoON1CyhQAM": 34563601, "Orq_75kFi8I": 36006882, "wGyh_53ecgg": 27081884}

# ---------------------------------------------------------------------------
# Pre-registered settings (plans/lrclib-auto-timing.md, "Settled for the measurement")
# ---------------------------------------------------------------------------

# A caption is a usable reference when it fits the transcribe words with no speed
# change, no more than this shift, and no flagged run.
CAPTION_SHIFT_LIMIT_S = 1.5

# The class of a fitted LRC against the caption.
RIGHT, WRONG_TIMING, HOLE, UNJUDGED = "right", "wrong_timing", "hole", "unjudged"
NO_FIT, KNOWN_BAD, REF_UNUSABLE = "no_fit", "known_bad", "ref_unusable"
MIN_MAPPED_LINES = 8
MIN_MAPPED_SHARE = 0.5
MEDIAN_OFFSET_LIMIT_S = 1.5
OFF_LINE_S = 3.0
OFF_RUN = 2
HOLE_RUN = 4

# The bar's swept dimensions, each listed strict to loose. ``I`` True: an interior
# unheard run is allowed. ``V`` True: the ASR veto is on. ``math.inf``: no limit.
DIMS = ("M", "R", "G", "E", "I", "D", "P", "V")
GRID: dict[str, tuple] = {
    "M": (0, 1),
    "R": (0.9, 0.8, 0.7, 0.6, 0.5),
    "G": (2, 3, 5, 10, 15),
    "E": (0, 1, 2),
    "I": (False, True),
    "D": (0, math.inf),
    "P": (0.3, 0.5, math.inf),
    "V": (True, False),
}
HEADERS = {
    "M": "Mistimed <=",
    "R": "Matched >=",
    "G": "Gap s <=",
    "E": "End unheard <=",
    "I": "Interior unheard",
    "D": "Dropped <=",
    "P": "Spread s <=",
    "V": "ASR veto",
}

Point = tuple[int, ...]  # one step index per dimension of DIMS

COUNT_NAMES = (
    "wrong",
    "holes",
    "unjudged",
    "known",
    "a_ref",
    "a_ref_any",
    "b_ref",
    "b_ref_any",
    "a_joint",
    "b_joint",
    "a_repair",
    "b_repair",
)
CLASS_COUNT = {WRONG_TIMING: "wrong", HOLE: "holes", UNJUDGED: "unjudged"}
TOP_ROWS = 30

# ---------------------------------------------------------------------------
# One candidate and one song
# ---------------------------------------------------------------------------


class Judgement(NamedTuple):
    """A fitted LRC set against the caption: the class and the numbers behind it."""

    cls: str
    mapping: dict[int, int]  # fitted LRC line -> caption cue
    offsets: dict[int, float]  # fitted LRC line -> d, seconds
    median_d: float | None
    max_abs_d: float | None
    off_runs: list[tuple[int, int]]
    lrc_hole: int  # longest run of fitted LRC lines with no cue mapped
    caption_hole: int  # longest run of caption cues with no line mapped


@dataclass(frozen=True)
class Candidate:
    """One LRCLIB record (or the song's own ``.lrc``) fitted to one song."""

    group: str
    youtube_id: str
    title: str
    lrclib_id: object
    on_disk: bool
    duration: object
    gap: int | None
    fit: SliceFit
    asr: SliceFit | None = None
    cls: str = ""
    judgement: Judgement | None = None

    @property
    def share(self) -> float:
        return self.fit.matched / self.fit.total if self.fit.total else 0.0

    @property
    def end_unheard(self) -> int:
        return end_unheard(self.fit.unheard, self.fit.total)

    @property
    def interior_unheard(self) -> bool:
        return interior_unheard(self.fit.unheard, self.fit.total)

    @property
    def asr_vetoed(self) -> bool:
        """The ASR stream disagrees: its fit refused as ``disagree`` or has a flagged run."""
        asr = self.asr
        if asr is None:
            return False
        if asr.status == FITS:
            return bool(flagged_runs(asr.mistimed, asr.unheard, MIN_FLAGGED_RUN))
        return asr.reason == srt_slice_fit.DISAGREE


@dataclass
class SongResult:
    group: str
    youtube_id: str
    title: str
    reason: str = ""
    candidates: list[Candidate] = field(default_factory=list)
    arm_a_id: object = None
    caption: SliceFit | None = None
    ref_ok: bool = False


# ---------------------------------------------------------------------------
# Pure parts: derived numbers, class rule, the bar
# ---------------------------------------------------------------------------


def end_unheard(unheard: tuple[int, ...], total: int) -> int:
    """The longer of the unheard run that starts at line 0 and the one that ends at the last line.

    0 when both end lines were heard.
    """
    missing = set(unheard)
    head = next((i for i in range(total) if i not in missing), total)
    tail = next((i for i in range(total) if total - 1 - i not in missing), total)
    return max(head, tail)


def interior_unheard(unheard: tuple[int, ...], total: int) -> bool:
    """Whether an unheard run of ``MIN_UNHEARD_RUN`` or more touches neither end line."""
    return any(
        first > 0 and last < total - 1 for first, last in unheard_runs(unheard, MIN_UNHEARD_RUN)
    )


def caption_ok(fit: SliceFit) -> bool:
    """Whether the caption's own fit makes it a reference the LRC can be judged against."""
    return (
        fit.status == FITS
        and fit.speed == 1.0
        and abs(fit.shift_s) <= CAPTION_SHIFT_LIMIT_S
        and not flagged_runs(fit.mistimed, fit.unheard, MIN_FLAGGED_RUN)
    )


def longest_unmapped(mapped: set[int], count: int) -> int:
    """The longest run of consecutive indexes below ``count`` that are not in ``mapped``."""
    longest = run = 0
    for index in range(count):
        run = 0 if index in mapped else run + 1
        longest = max(longest, run)
    return longest


def classify(
    mapping: dict[int, int],
    lrc_starts: list[float],
    caption_starts: list[float],
    caption_shift: float,
) -> Judgement:
    """The class of a fitted LRC against the caption, given the line-to-cue ``mapping``.

    ``d`` of a mapped pair is the LRC line's fitted start less the cue's start moved
    by ``caption_shift`` (the caption's own lead or lag against the heard words).
    """
    offsets = {
        line: lrc_starts[line] - (caption_starts[cue] + caption_shift)
        for line, cue in sorted(mapping.items())
    }
    unmapped_lines = tuple(line for line in range(len(lrc_starts)) if line not in offsets)
    off = tuple(line for line, d in offsets.items() if abs(d) > OFF_LINE_S)
    off_runs = flagged_runs(off, unmapped_lines, OFF_RUN)
    median_d = median(offsets.values()) if offsets else None
    lrc_hole = longest_unmapped(set(offsets), len(lrc_starts))
    caption_hole = longest_unmapped(set(mapping.values()), len(caption_starts))
    share = len(offsets) / len(lrc_starts) if lrc_starts else 0.0

    if len(offsets) < MIN_MAPPED_LINES or share < MIN_MAPPED_SHARE:
        cls = UNJUDGED
    elif abs(median_d) > MEDIAN_OFFSET_LIMIT_S or off_runs:
        cls = WRONG_TIMING
    elif max(lrc_hole, caption_hole) >= HOLE_RUN:
        cls = HOLE
    else:
        cls = RIGHT
    return Judgement(
        cls,
        mapping,
        offsets,
        median_d,
        max((abs(d) for d in offsets.values()), default=None),
        off_runs,
        lrc_hole,
        caption_hole,
    )


def judge(fit: SliceFit, caption_texts: list[str], caption_starts: list[float], shift: float):
    """:func:`classify` for a fit that ``fits``, mapping its lines to the caption by text."""
    mapping = lrclib.map_lines_to_cues([text for text, _ in fit.lines], caption_texts)
    return classify(mapping, [start for _, start in fit.lines], caption_starts, shift)


# How each dimension's value turns a candidate away: True when the candidate passes it.
CONDITIONS = {
    "M": lambda c, v: len(c.fit.mistimed) <= v,
    "R": lambda c, v: c.share >= v,
    "G": lambda c, v: abs(c.gap) <= v,
    "E": lambda c, v: c.end_unheard <= v,
    "I": lambda c, v: v or not c.interior_unheard,
    "D": lambda c, v: c.fit.dropped <= v,
    "P": lambda c, v: (math.inf if c.fit.spread_s is None else c.fit.spread_s) <= v,
    "V": lambda c, v: not (v and c.asr_vetoed),
}


def fixed_refusal(cand: Candidate) -> str | None:
    """Why a conjunct fixed at every grid point refuses the candidate; None when it passes."""
    fit = cand.fit
    if fit.status != FITS:
        return f"fit {fit.status}" + (f"/{fit.reason}" if fit.reason else "")
    if fit.speed != 1.0:
        return f"speed {fit.speed:.4f}"
    if cand.gap is None:
        return "no record duration"
    if not fit.total:
        return "no lines in the clip"
    return None


def refusal_reason(cand: Candidate) -> str | None:
    """Why no grid point accepts the candidate; None when some point does."""
    if reason := fixed_refusal(cand):
        return reason
    never = [HEADERS[d] for d in DIMS if not any(CONDITIONS[d](cand, v) for v in GRID[d])]
    return "never passes: " + ", ".join(never) if never else None


def need_vector(cand: Candidate) -> Point | None:
    """The strictest grid point that accepts the candidate; None when none does.

    Every condition only loosens down its list, so the first step that passes in each
    dimension is the least a point must be loose there.
    """
    if fixed_refusal(cand):
        return None
    need = []
    for dim in DIMS:
        step = next((i for i, v in enumerate(GRID[dim]) if CONDITIONS[dim](cand, v)), None)
        if step is None:
            return None
        need.append(step)
    return tuple(need)


def covers(point: Point, need: Point) -> bool:
    return all(step >= least for step, least in zip(point, need))


def accepts(point: Point, cand: Candidate) -> bool:
    need = need_vector(cand)
    return need is not None and covers(point, need)


def id_key(lrclib_id: object) -> float:
    """Sort key for an LRCLIB id; a record with no usable id sorts last."""
    return lrclib_id if isinstance(lrclib_id, int) else math.inf


def arm_b_key(cand: Candidate) -> tuple:
    """Order of the best-fit pick: highest matched share, then smallest gap, spread, id."""
    spread = math.inf if cand.fit.spread_s is None else cand.fit.spread_s
    return (-cand.share, abs(cand.gap), spread, id_key(cand.lrclib_id))


def all_points() -> list[Point]:
    return list(itertools.product(*(range(len(GRID[dim])) for dim in DIMS)))


def neighbours(point: Point) -> Iterator[Point]:
    """The points one step looser than ``point`` in exactly one dimension."""
    for k, dim in enumerate(DIMS):
        if point[k] + 1 < len(GRID[dim]):
            yield point[:k] + (point[k] + 1,) + point[k + 1 :]


def margin_safe_points(clean: dict[Point, bool]) -> dict[Point, bool]:
    """Which points are clean themselves and have only clean one-step-looser neighbours.

    ``clean`` says per point that it accepts no ``wrong_timing`` and no ``known`` candidate.
    """
    return {p: ok and all(clean[n] for n in neighbours(p)) for p, ok in clean.items()}


def count_song(song: SongResult, accepted: list[Candidate], counts: Counter) -> None:
    """Add one song's contribution at one grid point to ``counts``."""
    a_pick = next((c for c in accepted if c.lrclib_id == song.arm_a_id), None)
    b_pick = min(accepted, key=arm_b_key, default=None)
    if song.group == KNOWN:
        counts["known"] += len(accepted)
    elif song.group == REF:
        if not song.ref_ok:
            return
        for cand in accepted:
            if name := CLASS_COUNT.get(cand.cls):
                counts[name] += 1
        counts["a_ref_any"] += a_pick is not None
        counts["a_ref"] += a_pick is not None and a_pick.cls == RIGHT
        counts["b_ref_any"] += b_pick is not None
        counts["b_ref"] += b_pick is not None and b_pick.cls == RIGHT
    else:
        counts[f"a_{song.group}"] += a_pick is not None
        counts[f"b_{song.group}"] += b_pick is not None


def run_sweep(songs: list[SongResult]) -> dict[Point, dict]:
    """Every grid point's counts, with ``margin_safe`` and the step sum added."""
    needed = [
        (song, [(c, n) for c in song.candidates if (n := need_vector(c)) is not None])
        for song in songs
    ]
    counts_by_point: dict[Point, Counter] = {}
    for point in all_points():
        counts: Counter = Counter()
        for song, pairs in needed:
            accepted = [c for c, need in pairs if covers(point, need)]
            count_song(song, accepted, counts)
        counts_by_point[point] = counts
    clean = {p: c["wrong"] == 0 and c["known"] == 0 for p, c in counts_by_point.items()}
    safe = margin_safe_points(clean)
    return {
        p: {**{name: counts[name] for name in COUNT_NAMES}, "margin_safe": safe[p], "steps": sum(p)}
        for p, counts in counts_by_point.items()
    }


# ---------------------------------------------------------------------------
# Reading a song
# ---------------------------------------------------------------------------


def title(status: SongStatus) -> str:
    return status.path.stem.split("---")[0][:40]


def group_of(status: SongStatus, bundle: dict | None) -> str:
    song = status.path
    has_words = bool((bundle or {}).get("transcribe_words"))
    subtitles = song.parent / "subtitles"
    if status.youtube_id in KNOWN_BAD_LRC_IDS:
        return KNOWN
    if status.origin == "srt" and not status.edited and has_words:
        if (subtitles / f"{song.stem}.srt").is_file() and not (
            subtitles / f"{song.stem}.srt.generated"
        ).exists():
            return REF
    if status.origin == "genius" and status.method == "joint" and has_words:
        return JOINT
    if status.origin == LRC_ORIGIN and has_words:
        return REPAIR
    return OUT_OF_SCOPE


def search_query_for(song: Path, bundle: dict | None) -> str:
    """The query Repair's LRCLIB search box starts with (``LibraryTools.custom_start``)."""
    genius = ((bundle or {}).get("lyrics") or {}).get("genius") or {}
    terms = lrclib.clean_key(genius.get("title") or default_query(song), genius.get("artist") or "")
    return " ".join(term for term in terms if term)


def search_records(youtube_id: str, query: str, cache_dir: Path) -> list[dict]:
    """The synced records LRCLIB returns for ``query``, cached per song.

    Raises :class:`lrclib.LrclibUnavailable`; nothing is cached then, so a rerun retries.
    """
    cache = cache_dir / f"{youtube_id}.json"
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))["records"]
        except (OSError, ValueError, KeyError) as e:
            logger.warning("Ignoring unreadable cache %s: %s", cache, e)
    records = [r for r in lrclib.search_query(query) if r.get("syncedLyrics")]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"query": query, "records": records}), encoding="utf-8")
    return records


def candidate_entries(records: list[dict], on_disk: dict | None) -> list[tuple[dict, bool]]:
    """``(record, is_on_disk)`` for each distinct record, ordered by id.

    The song's own ``.lrc`` joins the search records unless one of them has its id.
    """
    by_id: dict[object, tuple[dict, bool]] = {}
    for record in records:
        by_id.setdefault(record.get("id"), (record, False))
    if on_disk is not None:
        disk_id = on_disk.get("id")
        if disk_id in by_id:
            by_id[disk_id] = (by_id[disk_id][0], True)
        else:
            by_id[disk_id] = (on_disk, True)
    return sorted(by_id.values(), key=lambda entry: id_key(entry[0].get("id")))


def disk_record(song: Path) -> dict | None:
    """The song's on-disk ``.lrc`` shaped as an LRCLIB record, None without a match."""
    lrc = lrclib.read_song_lrc(song)
    if lrc.state != "match":
        return None
    return {
        "id": lrc.meta.get("id"),
        "duration": lrc.meta.get("duration"),
        "syncedLyrics": lrc.text,
    }


def read_caption(song: Path) -> tuple[str, list[str], list[float]] | None:
    """The uploader caption's text, cleaned cue texts and cue starts; None when unreadable."""
    path = song.parent / "subtitles" / f"{song.stem}.srt"
    try:
        text = path.read_text(encoding="utf-8")
        texts, spans = cue_spans_from_srt(text)
    except (OSError, ValueError, OverflowError, srt.SRTParseError) as e:
        logger.warning("Cannot read caption %s: %s", path, e)
        return None
    return text, texts, [start for start, _ in spans]


def fit_candidate(
    song: SongResult, record: dict, on_disk: bool, streams: dict, length: float
) -> Candidate:
    srt_text = lrc_to_srt(record["syncedLyrics"])
    fit = fit_slice(srt_text, {TRANSCRIBE: streams[TRANSCRIBE]}, length)
    asr = fit_slice(srt_text, {ASR: streams[ASR]}, length) if ASR in streams else None
    duration = record.get("duration")
    return Candidate(
        group=song.group,
        youtube_id=song.youtube_id,
        title=song.title,
        lrclib_id=record.get("id"),
        on_disk=on_disk,
        duration=duration,
        gap=length_gap_s(duration, length),
        fit=fit,
        asr=asr,
    )


def pick_arm_a(
    song: SongResult,
    records: list[dict],
    on_disk: dict | None,
    sheet: list[str],
    length: float,
) -> object:
    """The id of today's pick: the on-disk match, else ``select_candidate`` on ``sheet``."""
    if song.group != REF and on_disk is not None:
        return on_disk.get("id")
    chosen = lrclib.select_candidate(records, sheet, length)
    return chosen.get("id") if chosen else None


def probe_song(status: SongStatus, out_dir: Path) -> SongResult:
    song = status.path
    bundle = read_bundle(song.parent, song.stem)
    result = SongResult(group_of(status, bundle), status.youtube_id or song.stem, title(status))
    if result.group == OUT_OF_SCOPE:
        result.reason = OUT_OF_SCOPE
        return result
    length = media_duration(SongJob(song, bundle, "probe"))
    if not length:
        result.reason = NO_LENGTH
        return result

    asr_path = song.parent / "subtitles" / f"{song.stem}.en.asr.json3"
    streams = heard_streams(
        bundle, asr_path.read_text(encoding="utf-8") if asr_path.is_file() else None
    )
    on_disk = disk_record(song)
    if result.group == KNOWN:
        if on_disk is None or on_disk.get("id") != KNOWN_BAD_LRC_IDS[result.youtube_id]:
            sys.exit(f"STOP: known-bad {result.youtube_id} no longer has its listed LRC on disk")
        records: list[dict] = []
    else:
        query = search_query_for(song, bundle)
        try:
            records = search_records(result.youtube_id, query, out_dir / "cache")
        except lrclib.LrclibUnavailable as e:
            logger.warning("%s", e)
            result.reason = LRCLIB_UNAVAILABLE
            return result

    caption = read_caption(song) if result.group == REF else None
    caption_texts = caption[1] if caption else []
    lyric_lines = ((bundle or {}).get("lyrics") or {}).get("lines") or []
    result.arm_a_id = pick_arm_a(
        result, records, on_disk, caption_texts if result.group == REF else lyric_lines, length
    )
    result.candidates = [
        fit_candidate(result, record, is_disk, streams, length)
        for record, is_disk in candidate_entries(records, on_disk)
    ]

    if result.group == KNOWN:
        result.candidates = [replace_class(c, KNOWN_BAD) for c in result.candidates]
    elif result.group == REF:
        judge_reference(
            result, caption, streams[TRANSCRIBE], bundle["transcribe_words"], length, out_dir
        )
    return result


def replace_class(cand: Candidate, cls: str, judgement: Judgement | None = None) -> Candidate:
    return replace(cand, cls=cls, judgement=judgement)


def judge_reference(
    result: SongResult,
    caption: tuple[str, list[str], list[float]] | None,
    words: list[dict],
    raw_words: list[dict],
    length: float,
    out_dir: Path,
) -> None:
    """Fit the caption, and when it is usable class every candidate against it.

    ``words`` is the normalised stream the fits read; ``raw_words`` is what the sheets show.
    """
    if caption is None:
        result.candidates = [replace_class(c, REF_UNUSABLE) for c in result.candidates]
        return
    text, texts, starts = caption
    result.caption = fit_slice(text, {TRANSCRIBE: words}, length)
    result.ref_ok = caption_ok(result.caption)
    judged = []
    for cand in result.candidates:
        if not result.ref_ok:
            judged.append(replace_class(cand, REF_UNUSABLE))
        elif cand.fit.status != FITS:
            judged.append(replace_class(cand, NO_FIT))
        else:
            judgement = judge(cand.fit, texts, starts, result.caption.shift_s)
            judged.append(replace_class(cand, judgement.cls, judgement))
            if judgement.cls in (WRONG_TIMING, HOLE, UNJUDGED):
                write_sheet(
                    out_dir, cand, judgement, texts, starts, result.caption.shift_s, raw_words
                )
    result.candidates = judged


# ---------------------------------------------------------------------------
# Eyeball sheets (lyric text: local only)
# ---------------------------------------------------------------------------


def write_sheet(
    out_dir: Path,
    cand: Candidate,
    judgement: Judgement,
    caption_texts: list[str],
    caption_starts: list[float],
    shift: float,
    words: list[dict],
) -> None:
    folder = out_dir / "sheets" / cand.youtube_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "words.txt").write_text(
        "".join(f"{w['start']:.2f}\t{w['word']}\n" for w in words), encoding="utf-8"
    )
    fit = cand.fit
    by_cue = {cue: line for line, cue in judgement.mapping.items()}
    lines = [f"# {cand.youtube_id} LRCLIB {cand.lrclib_id}: {judgement.cls}", "## LRC lines"]
    lines.append("index\tfitted start\tflag\tcue\td\ttext")
    for i, (text, start) in enumerate(fit.lines):
        flag = "M" if i in fit.mistimed else "U" if i in fit.unheard else ""
        cue = judgement.mapping.get(i)
        d = judgement.offsets.get(i)
        lines.append(
            f"{i}\t{start:.2f}\t{flag}\t{'' if cue is None else cue}\t"
            f"{'' if d is None else f'{d:+.2f}'}\t{text}"
        )
    lines += ["## Caption cues", "index\tstart + shift\tLRC line\ttext"]
    for j, text in enumerate(caption_texts):
        line = by_cue.get(j)
        lines.append(
            f"{j}\t{caption_starts[j] + shift:.2f}\t{'' if line is None else line}\t{text}"
        )
    (folder / f"{cand.lrclib_id}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def fmt_value(dim: str, value: object) -> str:
    if value == math.inf:
        return "any"
    if dim == "I":
        return "allow" if value else "forbid"
    if dim == "V":
        return "on" if value else "off"
    return str(value)


def point_values(point: Point) -> list[str]:
    return [fmt_value(dim, GRID[dim][step]) for dim, step in zip(DIMS, point)]


def verdict(fit: SliceFit | None) -> str:
    if fit is None:
        return ""
    return fit.status + (f"/{fit.reason}" if fit.reason else "")


def indexes(lines: tuple[int, ...]) -> str:
    return ",".join(map(str, lines))


def spans(found: list[tuple[int, int]]) -> str:
    return " ".join(f"{first}-{last}" for first, last in found)


def num(value: float | None, places: int = 2) -> str:
    return "" if value is None else f"{value:.{places}f}"


def md_table(header: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


CANDIDATE_HEADER = (
    "group youtube_id title lrclib_id on_disk arm_a duration gap "
    "status reason speed shift_s spread_s matched total dropped "
    "mistimed_n mistimed unheard end_unheard interior_unheard "
    "asr_status asr_reason asr_flagged_runs "
    "mapped median_d max_abs_d off_runs lrc_hole_max caption_hole_max class"
).split()


def candidate_row(song: SongResult, cand: Candidate) -> list[object]:
    fit, asr, j = cand.fit, cand.asr, cand.judgement
    return [
        cand.group,
        cand.youtube_id,
        cand.title,
        cand.lrclib_id,
        int(cand.on_disk),
        int(cand.lrclib_id == song.arm_a_id),
        cand.duration,
        "" if cand.gap is None else f"{cand.gap:+d}",
        fit.status,
        fit.reason or "",
        f"{fit.speed:.4f}",
        num(fit.shift_s),
        num(fit.spread_s, 3),
        fit.matched,
        fit.total,
        fit.dropped,
        len(fit.mistimed),
        indexes(fit.mistimed),
        indexes(fit.unheard),
        cand.end_unheard,
        int(cand.interior_unheard),
        asr.status if asr else "",
        (asr.reason or "") if asr else "",
        len(flagged_runs(asr.mistimed, asr.unheard, MIN_FLAGGED_RUN)) if asr else "",
        len(j.mapping) if j else "",
        num(j.median_d) if j else "",
        num(j.max_abs_d) if j else "",
        spans(j.off_runs) if j else "",
        j.lrc_hole if j else "",
        j.caption_hole if j else "",
        cand.cls,
    ]


SONG_HEADER = (
    "group youtube_id title reason candidates arm_a_id "
    "caption_status caption_speed caption_shift_s caption_flagged_runs ref_ok"
).split()


def song_row(song: SongResult) -> list[object]:
    cap = song.caption
    is_ref = song.group == REF and not song.reason
    return [
        song.group,
        song.youtube_id,
        song.title,
        song.reason,
        len(song.candidates),
        "" if song.arm_a_id is None else song.arm_a_id,
        (verdict(cap) or "unreadable") if is_ref else "",
        f"{cap.speed:.4f}" if cap else "",
        num(cap.shift_s) if cap else "",
        len(flagged_runs(cap.mistimed, cap.unheard, MIN_FLAGGED_RUN)) if cap else "",
        int(song.ref_ok) if is_ref else "",
    ]


def write_tsv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def sweep_row(point: Point, row: dict) -> list[object]:
    return [
        *point_values(point),
        *(row[name] for name in COUNT_NAMES),
        int(row["margin_safe"]),
        row["steps"],
    ]


SWEEP_HEADER = [HEADERS[d] for d in DIMS] + list(COUNT_NAMES) + ["margin_safe", "steps"]


def table_p(songs: list[SongResult]) -> str:
    rows = []
    for group in (REF, JOINT, REPAIR, KNOWN, OUT_OF_SCOPE):
        members = [s for s in songs if s.group == group]
        reasons = Counter(s.reason for s in members if s.reason and s.reason != OUT_OF_SCOPE)
        rows.append(
            [
                group,
                len(members),
                reasons[NO_LENGTH],
                reasons[LRCLIB_UNAVAILABLE],
                sum(s.ref_ok for s in members) if group == REF else "",
            ]
        )
    return md_table(["Group", "Songs", NO_LENGTH, LRCLIB_UNAVAILABLE, "ref_ok"], rows)


def table_s1(sweep: dict[Point, dict]) -> tuple[str, list[Point], int]:
    """The printed table, the points it shows (in rank order) and how many qualify."""
    qualifying = [
        p
        for p, row in sweep.items()
        if row["wrong"] == 0 and row["known"] == 0 and row["margin_safe"]
    ]
    ranked = sorted(
        qualifying,
        key=lambda p: (-sweep[p]["b_ref"], -sweep[p]["a_ref"], sweep[p]["steps"], p),
    )[:TOP_ROWS]
    header = ["#"] + [HEADERS[d] for d in DIMS] + list(COUNT_NAMES)
    rows = [
        [rank, *point_values(p), *(sweep[p][name] for name in COUNT_NAMES)]
        for rank, p in enumerate(ranked, 1)
    ]
    return md_table(header, rows), ranked, len(qualifying)


def table_s2(songs: list[SongResult], ranked: list[Point]) -> str:
    """The hole and unjudged candidates the printed S1 rows accept, with those rows' numbers."""
    rows = []
    for song in songs:
        if song.group != REF or not song.ref_ok:
            continue
        for cand in song.candidates:
            need = need_vector(cand)
            if cand.cls not in (HOLE, UNJUDGED) or need is None:
                continue
            accepting = [rank for rank, p in enumerate(ranked, 1) if covers(p, need)]
            if accepting:
                rows.append(
                    [
                        cand.title,
                        cand.youtube_id,
                        cand.lrclib_id,
                        cand.cls,
                        ",".join(map(str, accepting)),
                    ]
                )
    return md_table(["Title", "youtube_id", "lrclib_id", "class", "S1 rows that accept it"], rows)


def table_k(songs: list[SongResult]) -> str:
    rows = []
    for song in songs:
        for cand in song.candidates if song.group == KNOWN else ():
            fit, need = cand.fit, need_vector(cand)
            bar = (
                " ".join(f"{d}={v}" for d, v in zip(DIMS, point_values(need)))
                if need
                else f"none ({refusal_reason(cand)})"
            )
            rows.append(
                [
                    cand.title,
                    cand.youtube_id,
                    cand.lrclib_id,
                    verdict(fit),
                    f"{fit.speed:.4f}",
                    f"{fit.matched}/{fit.total}",
                    "" if cand.gap is None else f"{cand.gap:+d}",
                    f"{len(fit.mistimed)}: {indexes(fit.mistimed)}" if fit.mistimed else "0",
                    cand.end_unheard,
                    bar,
                ]
            )
    header = ["Title", "youtube_id", "lrclib_id", "Fit", "Speed", "Matched", "Gap s", "Mistimed"]
    return md_table(
        header + ["End unheard", "Loosest bar it needs (strictest point that accepts it)"], rows
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, default=Path(default_folder))
    parser.add_argument(
        "--out", type=Path, default=Path(get_temp_directory()) / "lrclib_auto_timing"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "started").write_text("", encoding="utf-8")

    statuses = library_statuses(args.folder)
    songs = []
    for n, status in enumerate(statuses, 1):
        logger.info("[%d/%d] %s", n, len(statuses), status.path.name)
        songs.append(probe_song(status, out))

    write_tsv(
        out / "candidates.tsv",
        CANDIDATE_HEADER,
        [candidate_row(s, c) for s in songs for c in s.candidates],
    )
    song_rows = [song_row(s) for s in songs]
    write_tsv(out / "songs.tsv", SONG_HEADER, song_rows)
    sweep = run_sweep(songs)
    write_tsv(out / "sweep.tsv", SWEEP_HEADER, [sweep_row(p, row) for p, row in sweep.items()])

    s1, ranked, n_qualifying = table_s1(sweep)
    print(
        f"Constants in force: FLAG_TOLERANCE_S={srt_slice_fit.FLAG_TOLERANCE_S}, "
        f"MIN_FLAGGED_RUN={MIN_FLAGGED_RUN}, MIN_UNHEARD_RUN={MIN_UNHEARD_RUN}, "
        f"MIN_MATCHED_SHARE={srt_slice_fit.MIN_MATCHED_SHARE}. "
        f"{len(songs)} songs in {args.folder}; output in {out}.\n"
    )
    print("## Table P: groups and skip reasons\n\n" + table_p(songs) + "\n")
    print("## Table C: songs\n\n" + md_table(SONG_HEADER, song_rows) + "\n")
    print(
        f"## Table S1: top {TOP_ROWS} of {n_qualifying} points with wrong = 0, known = 0 and "
        "margin_safe\n\n" + s1 + "\n"
    )
    print(
        "## Table S2: hole and unjudged candidates the S1 rows above accept\n\n"
        + table_s2(songs, ranked)
        + "\n"
    )
    print("## Table K: known-bad candidates\n\n" + table_k(songs))


if __name__ == "__main__":
    main()
