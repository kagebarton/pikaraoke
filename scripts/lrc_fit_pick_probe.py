"""GATE P measurement for plans/lrclib-fit-pick.md: would the bar and the pick time a
downloaded song from an LRCLIB record, and is every record they pick timed to this video?

For each song the library can answer for, every synced record one LRCLIB search returns is
fitted to the clip's heard words (``lrc_auto_pick.evaluate``, the code the pipeline will
call) and the pick is made. A song timed from an uploader caption has an independent
reference: every record that passes the bar is fitted to the caption too and flagged where
the two disagree. A pick is never judged here; the tables, the listen files (the fitted
lines as an SRT to play over the video) and the sheets are what the judge reads.

The library is never written. ``--out`` and ``--listen-dir`` hold lyric text (the LRCLIB
cache, the sheets, the listen files), so neither is ever committed. The tables printed to
stdout carry line numbers and counts, never lyric text.

Run from the repo root::

    python scripts/lrc_fit_pick_probe.py --folder PATH [--out DIR] [--baseline FILE]
        [--old-cache DIR] [--listen-dir DIR] [--only ID ...] > DIR/report.md
"""

import argparse
import csv
import json
import logging
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import srt

# Allow running as ``python scripts/lrc_fit_pick_probe.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import lrc_auto_pick, lrclib  # noqa: E402
from pikaraoke.lib.get_platform import get_temp_directory  # noqa: E402
from pikaraoke.lib.library_regen import (  # noqa: E402
    CUSTOM_ORIGIN,
    LRC_ORIGIN,
    MOVIE_ORIGIN,
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
from pikaraoke.lib.lrc_auto_pick import REFUSALS, Entry, timing_key  # noqa: E402
from pikaraoke.lib.srt_slice_fit import (  # noqa: E402
    CAPTION,
    FITS,
    MIN_FLAGGED_RUN,
    MIN_UNHEARD_RUN,
    TRANSCRIBE,
    SliceFit,
    fit_slice,
    flagged_runs,
    heard_streams,
    lrc_to_srt,
    sheet_stream,
    unheard_runs,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Groups and settings
# ---------------------------------------------------------------------------

PICKS, JOINT, CAPTIONED, OUT_OF_SCOPE = "picks", "joint", "caption", "out_of_scope"
GROUPS = (PICKS, JOINT, CAPTIONED)

# Why a song is out of scope.
CUSTOM, MOVIE, NO_BUNDLE, NO_WORDS = "custom", "movie_srt", "no_bundle", "no_words"
EDITED, NO_CAPTION_FILE, OTHER = "edited", "no_caption_file", "other"
SCOPE_REASONS = (CUSTOM, MOVIE, NO_BUNDLE, NO_WORDS, EDITED, NO_CAPTION_FILE, OTHER)

# Why an in-scope song gives no result.
NO_LENGTH, LRCLIB_UNAVAILABLE = "no_length", "lrclib_unavailable"

# A caption is a usable reference when it fits the heard words at speed 1.0 within this
# shift with no flagged run; a record's shift against the caption may differ from its
# shift against the heard words by no more than this either.
SHIFT_LIMIT_S = 1.5
# Over this many unclaimed caption words, the caption sings what the record lacks.
REF_MAX_UNCLAIMED_RUN = 12

# The shortest unclaimed run a sheet lists.
MIN_X_RUN = 5

# Table V: the limits it counts picks at (never read for the verdict).
V_MISTIMED = (0, 1)
V_UNCLAIMED = (8, 10, 12, 15, 20)

# The LRC-wrong records GATE M found, by song: the bar must pick none of them.
GATE_M_WRONG: dict[str, tuple[int, ...]] = {
    "GZXHBgjQjNM": (20242140, 21912586, 27023721, 31535578, 32140003, 35793714, 36228137),
    "AJWtLf4-WWs": (6800151, 28307055, 34352818),
    "UAWcs5H-qgQ": (12572148,),
    "T6wbugWrfLU": (
        35468507,
        3458703,
        6335685,
        7720552,
        9641374,
        12149023,
        12377831,
        12515974,
        15413449,
        17099666,
        20411476,
        23305471,
        24586049,
        24809544,
        31956521,
        32182355,
        32691192,
        33133897,
        34902348,
    ),
}

# ---------------------------------------------------------------------------
# One record, one song
# ---------------------------------------------------------------------------


@dataclass
class Rec:
    """One LRCLIB record fitted to one song: from the search (``in_pool``) or the song's
    own ``.lrc`` (``on_disk``), or both. ``timing`` is its :func:`timing_key`,
    ``timing_id`` the lowest id of the search's records that share it."""

    record: dict
    fit: SliceFit
    refusal: str | None
    in_pool: bool
    on_disk: bool
    timing: str
    timing_id: object
    timing_size: int
    ref: SliceFit | None = None
    flags: tuple[str, ...] = ()

    @property
    def id(self) -> object:
        return self.record.get("id")

    @property
    def passes(self) -> bool:
        return self.refusal is None


@dataclass
class SongResult:
    group: str
    reason: str
    new: bool
    youtube_id: str
    title: str
    stem: str
    length: float | None = None
    words: list[dict] = field(default_factory=list)
    query: str = ""
    recs: list[Rec] = field(default_factory=list)  # the search's, passing ones first
    disk: Rec | None = None
    pick: Rec | None = None
    caption: SliceFit | None = None
    ref_ok: bool = False
    needs_verdict: bool = False

    @property
    def probed(self) -> bool:
        """Whether the song was searched and fitted: in scope, with a length, LRCLIB reached."""
        return self.group != OUT_OF_SCOPE and not self.reason


# ---------------------------------------------------------------------------
# Pure parts
# ---------------------------------------------------------------------------


def classify(
    *,
    bundle: bool,
    origin: str | None,
    method: str | None,
    edited: bool,
    words: bool,
    caption_file: bool,
) -> tuple[str, str]:
    """The song's ``(group, reason)``; the reason is empty for a group in scope."""
    if not bundle:
        return OUT_OF_SCOPE, NO_BUNDLE
    if origin == CUSTOM_ORIGIN:
        return OUT_OF_SCOPE, CUSTOM
    if origin == MOVIE_ORIGIN:
        return OUT_OF_SCOPE, MOVIE
    if not words:
        return OUT_OF_SCOPE, NO_WORDS
    if origin == LRC_ORIGIN:
        return PICKS, ""
    if origin == "genius" and method == "joint":
        return JOINT, ""
    if origin == "srt":
        if edited:
            return OUT_OF_SCOPE, EDITED
        if not caption_file:
            return OUT_OF_SCOPE, NO_CAPTION_FILE
        return CAPTIONED, ""
    return OUT_OF_SCOPE, OTHER


def caption_ok(fit: SliceFit) -> bool:
    """Whether the caption's own fit makes it a reference to judge records against."""
    return (
        fit.status == FITS
        and fit.speed == 1.0
        and abs(fit.shift_s) <= SHIFT_LIMIT_S
        and not flagged_runs(fit.mistimed, fit.unheard, MIN_FLAGGED_RUN)
    )


def reference_flags(fit: SliceFit, ref: SliceFit) -> list[str]:
    """Where a passing record's fit to the caption (``ref``) disagrees with its fit to the
    heard words (``fit``): a screen for the judge, not a verdict."""
    if ref.status != FITS:
        return ["ref_refused"]
    flags = []
    if ref.mistimed:
        flags.append("ref_mistimed")
    if ref.unclaimed_run > REF_MAX_UNCLAIMED_RUN:
        flags.append("ref_unclaimed")
    if unheard_runs(ref.unheard, MIN_UNHEARD_RUN):
        flags.append("ref_unheard")
    if abs(ref.shift_s - fit.shift_s) > SHIFT_LIMIT_S:
        flags.append("ref_shift")
    return flags


def needs_verdict(group: str, pick_timing: str | None, disk_timing: str | None) -> bool:
    """Every pick needs one, except a ``picks`` song's pick that has the timing already on
    disk: Ken sings on that one."""
    if pick_timing is None:
        return False
    return not (group == PICKS and disk_timing is not None and pick_timing == disk_timing)


def listen_tier(song: SongResult) -> int:
    """0: no reference to screen the pick; 1: the screen flagged it; 2: it did not."""
    if not song.ref_ok:
        return 0
    return 1 if song.pick and song.pick.flags else 2


def listen_key(song: SongResult) -> tuple:
    """Table L's order: no reference first, then flagged, then the longest unclaimed run,
    the most mistimed lines, and the YouTube id."""
    fit = song.pick.fit
    return (listen_tier(song), -fit.unclaimed_run, -len(fit.mistimed), song.youtube_id)


def locate_record(record_id: int, pool_ids: set, old_ids: set) -> str:
    """Where Table K finds a GATE M record: this run's search, else the old cache, else nowhere."""
    if record_id in pool_ids:
        return "pool"
    return "old cache" if record_id in old_ids else "not found"


def passes_at(fit: SliceFit, mistimed_limit: int, unclaimed_limit: int) -> bool:
    """The bar at other limits (Table V); the other conditions are the bar's."""
    return (
        fit.status == FITS
        and fit.speed == 1.0
        and len(fit.mistimed) <= mistimed_limit
        and fit.unclaimed_run <= unclaimed_limit
    )


def songs_with_pick_at(songs: list[SongResult], mistimed_limit: int, unclaimed_limit: int) -> int:
    """Songs where some record of the search passes at these limits. Whether a song has a
    pick depends on that alone, not on the pick order."""
    return sum(
        any(passes_at(rec.fit, mistimed_limit, unclaimed_limit) for rec in song.recs)
        for song in songs
    )


def body_of_lrc(text: str) -> str:
    """An LRC file's synced lines, without the ``[ti:..]``-style header ``write_lrc`` adds."""
    return "\n".join(line for line in text.splitlines() if not re.match(r"\s*\[[A-Za-z_]", line))


def id_key(record_id: object) -> float:
    """Sort key for an LRCLIB id; a record with no usable id sorts last."""
    return record_id if isinstance(record_id, int) else math.inf


def flagged_unpicked(recs: list[Rec], pick: Rec | None) -> list[list[Rec]]:
    """The passing records the caption screen flagged and the pick does not share a timing
    with, grouped by timing (each group by id, the groups by their lowest id)."""
    groups: dict[str, list[Rec]] = {}
    for rec in recs:
        if rec.passes and rec.flags and not (pick and rec.timing == pick.timing):
            groups.setdefault(rec.timing, []).append(rec)
    ordered = [sorted(group, key=lambda r: id_key(r.id)) for group in groups.values()]
    return sorted(ordered, key=lambda group: id_key(group[0].id))


def match_lines(fit_lines: tuple, other_lines: tuple) -> dict[int, int]:
    """Which line of ``fit_lines`` each line of ``other_lines`` is, by text and in order:
    ``{other index: fit index}``. Two fits of one sheet can drop different edge lines."""
    mapping: dict[int, int] = {}
    cursor = 0
    for j, (text, _) in enumerate(other_lines):
        found = next((i for i in range(cursor, len(fit_lines)) if fit_lines[i][0] == text), None)
        if found is not None:
            mapping[j] = found
            cursor = found + 1
    return mapping


def sheet_rows(
    fit: SliceFit, ref: SliceFit | None, caption_lines: tuple, words: list[dict]
) -> list[tuple[float, str, str, str]]:
    """The sheet as ``(time, kind, flags, text)``, in time order.

    ``L`` is a record line at its fitted start, flagged ``M``/``U`` by the heard words and
    ``m``/``u`` by the caption; ``C`` a caption cue; ``X`` a run of ``MIN_X_RUN`` or more
    heard words no line claims, at its first word.
    """
    flags: dict[int, str] = {i: "M" for i in fit.mistimed} | {i: "U" for i in fit.unheard}
    if ref is not None and ref.status == FITS:
        to_fit = match_lines(fit.lines, ref.lines)
        for j, i in to_fit.items():
            mark = "m" if j in ref.mistimed else "u" if j in ref.unheard else ""
            flags[i] = flags.get(i, "") + mark
    rows = [(start, "L", flags.get(i, ""), text) for i, (text, start) in enumerate(fit.lines)]
    rows += [(start, "C", "", text) for text, start in caption_lines]
    for first, length in fit.unclaimed_runs:
        if length >= MIN_X_RUN:
            heard = " ".join(w["norm"] for w in words[first : first + length])
            rows.append((words[first]["start"], "X", str(length), heard))
    return sorted(rows, key=lambda row: (row[0], "LCX".index(row[1])))


# ---------------------------------------------------------------------------
# Reading a song
# ---------------------------------------------------------------------------


def title(status: SongStatus) -> str:
    return status.path.stem.split("---")[0][:40]


def song_id(status: SongStatus) -> str:
    """The id the baseline lists and the cache is named by: the YouTube id, else the stem."""
    return status.youtube_id or status.path.stem


def caption_path(song: Path) -> Path:
    return song.parent / "subtitles" / f"{song.stem}.srt"


def has_caption_file(song: Path) -> bool:
    """An uploader caption on disk: its file exists and no ``.srt.generated`` marker sits
    beside it (the marker means the pipeline wrote it)."""
    generated = caption_path(song).with_name(f"{song.stem}.srt.generated")
    return caption_path(song).is_file() and not generated.exists()


def read_caption(song: Path) -> tuple[str, list[dict]] | None:
    """The caption's text and its word stream; None when it can't be read."""
    path = caption_path(song)
    try:
        text = path.read_text(encoding="utf-8")
        return text, sheet_stream(text)
    except (OSError, ValueError, OverflowError, srt.SRTParseError) as e:
        logger.warning("Cannot read caption %s: %s", path, e)
        return None


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


def read_old_records(old_cache: Path | None, youtube_id: str) -> list[dict]:
    """The records of an earlier probe's cache for the song; none when there is no cache."""
    if old_cache is None or not (path := old_cache / f"{youtube_id}.json").is_file():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))["records"]
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Ignoring unreadable old cache %s: %s", path, e)
        return []


def disk_record(song: Path) -> dict | None:
    """The song's on-disk ``.lrc`` shaped as an LRCLIB record, None without a match."""
    lrc = lrclib.read_song_lrc(song)
    if lrc.state != "match":
        return None
    return {**lrc.meta, "syncedLyrics": body_of_lrc(lrc.text)}


def fit_record(record: dict, words: list[dict], length: float) -> SliceFit:
    return fit_slice(lrc_to_srt(record["syncedLyrics"]), {TRANSCRIBE: words}, length)


def make_recs(
    entries: list[Entry], disk: dict | None, words: list[dict], length: float
) -> tuple[list[Rec], Rec | None]:
    """The search's entries as :class:`Rec`, and the on-disk record's (None without one).

    The on-disk record is the search's own when the search returned its id; otherwise it
    is fitted here and kept out of the pool.
    """
    keys = [timing_key(entry.record["syncedLyrics"]) for entry in entries]
    lowest: dict[str, object] = {}
    for key, entry in zip(keys, entries):
        if id_key(entry.record.get("id")) < id_key(lowest.get(key)):
            lowest[key] = entry.record.get("id")
    disk_id = disk.get("id") if disk else None
    recs = [
        Rec(
            entry.record,
            entry.fit,
            entry.refusal,
            True,
            disk is not None and entry.record.get("id") == disk_id,
            key,
            lowest[key],
            entry.timing_size,
        )
        for entry, key in zip(entries, keys)
    ]
    if disk is None:
        return recs, None
    on_disk = next((rec for rec in recs if rec.on_disk), None)
    if on_disk is None:
        key = timing_key(disk["syncedLyrics"])
        fit = fit_record(disk, words, length)
        same = [r for r in recs if r.timing == key]
        on_disk = Rec(
            disk,
            fit,
            lrc_auto_pick.refusal(fit),
            False,
            True,
            key,
            same[0].timing_id if same else disk_id,
            len(same),
        )
    return recs, on_disk


def add_references(recs: list[Rec], stream: list[dict], length: float) -> None:
    """Fit each passing record to the caption's words and flag where the two fits disagree."""
    for rec in recs:
        if rec.passes:
            text = lrc_to_srt(rec.record["syncedLyrics"])
            rec.ref = fit_slice(text, {CAPTION: stream}, length)
            rec.flags = tuple(reference_flags(rec.fit, rec.ref))


@dataclass(frozen=True)
class Run:
    out: Path
    listen_dir: Path
    baseline: set[str] | None


def probe_song(status: SongStatus, run: Run) -> SongResult:
    song = status.path
    bundle = read_bundle(song.parent, song.stem)
    words = heard_streams(bundle, None).get(TRANSCRIBE, [])
    group, reason = classify(
        bundle=bundle is not None,
        origin=status.origin,
        method=status.method,
        edited=status.edited,
        words=bool(words),
        caption_file=has_caption_file(song),
    )
    new = run.baseline is not None and song_id(status) not in run.baseline
    result = SongResult(group, reason, new, song_id(status), title(status), song.stem)
    if group == OUT_OF_SCOPE:
        return result
    result.length = media_duration(SongJob(song, bundle, "probe"))
    if not result.length:
        result.reason = NO_LENGTH
        return result
    result.words = words
    result.query = search_query_for(song, bundle)
    try:
        records = search_records(result.youtube_id, result.query, run.out / "cache")
    except lrclib.LrclibUnavailable as e:
        logger.warning("%s", e)
        result.reason = LRCLIB_UNAVAILABLE
        return result

    entries = lrc_auto_pick.evaluate(records, words, result.length)
    result.recs, result.disk = make_recs(entries, disk_record(song), words, result.length)
    # ``evaluate`` puts the passing records first in pick order, so this is ``lrc_auto_pick.pick``.
    result.pick = next((rec for rec in result.recs if rec.passes), None)
    caption_lines: tuple = ()
    if group == CAPTIONED:
        caption_lines = judge_reference(result, song)
    result.needs_verdict = needs_verdict(
        group,
        result.pick.timing if result.pick else None,
        result.disk.timing if result.disk else None,
    )
    write_song_files(result, caption_lines, run)
    return result


def judge_reference(result: SongResult, song: Path) -> tuple:
    """Fit the caption and, when it is a usable reference, screen every passing record
    against it. Returns the caption's fitted lines (for the sheets)."""
    caption = read_caption(song)
    if caption is None:
        return ()
    text, stream = caption
    result.caption = fit_slice(text, {TRANSCRIBE: result.words}, result.length)
    result.ref_ok = caption_ok(result.caption)
    if not result.ref_ok:
        return ()
    add_references(song_recs(result), stream, result.length)
    return result.caption.lines


# ---------------------------------------------------------------------------
# Listen files and sheets (lyric text: local only)
# ---------------------------------------------------------------------------


def write_song_files(result: SongResult, caption_lines: tuple, run: Run) -> None:
    """The listen file of a pick that needs a verdict, and the sheets of the pick and of
    each timing the caption flagged but the pick does not share."""
    sheeted = [result.pick] if result.pick else []
    sheeted += [group[0] for group in flagged_unpicked(result.recs, result.pick)]
    if result.pick and result.needs_verdict:
        run.listen_dir.mkdir(parents=True, exist_ok=True)
        name = listen_name(result.stem, result.pick.id)
        (run.listen_dir / name).write_text(result.pick.fit.srt, encoding="utf-8")
    if not sheeted:
        return
    folder = run.out / "sheets" / result.youtube_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "words.txt").write_text(
        "".join(f"{w['start']:.2f}\t{w['norm']}\n" for w in result.words), encoding="utf-8"
    )
    for rec in sheeted:
        label = "picked" if rec is result.pick else "flagged, not picked"
        text = sheet_text(result, rec, label, caption_lines)
        (folder / f"{rec.id}.txt").write_text(text, encoding="utf-8")


def listen_name(stem: str, lrclib_id: object) -> str:
    return f"{stem}.{lrclib_id}.srt"


def sheet_text(result: SongResult, rec: Rec, label: str, caption_lines: tuple) -> str:
    fit = rec.fit
    head = [
        f"# {result.youtube_id} LRCLIB {rec.id} ({label})",
        f"# fit {fit.status} speed {fit.speed:.4f} shift {fit.shift_s:.2f} mistimed "
        f"{len(fit.mistimed)} unheard {len(fit.unheard)} unclaimed_run {fit.unclaimed_run}",
        "# L record line at its fitted start (M mistimed, U unheard by the heard words; m, u by "
        "the caption); C caption cue; X heard words no line claims (count, then words)",
        "time\tkind\tflags\ttext",
    ]
    rows = sheet_rows(fit, rec.ref, caption_lines, result.words)
    return "\n".join(head + [sheet_line(*row) for row in rows]) + "\n"


def sheet_line(time: float, kind: str, flags: str, text: str) -> str:
    return "\t".join([f"{time:.2f}", kind, flags, text.replace("\t", " ")])


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def md_table(header: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|")

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def write_tsv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def num(value: float | None, places: int = 2) -> str:
    return "" if value is None else f"{value:.{places}f}"


def indexes(lines: tuple[int, ...]) -> str:
    return ",".join(map(str, lines))


def verdict(fit: SliceFit) -> str:
    return fit.status + (f"/{fit.reason}" if fit.reason else "")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def song_recs(song: SongResult) -> list[Rec]:
    """The search's records and, when the search did not return it, the on-disk one."""
    disk_only = [song.disk] if song.disk and not song.disk.in_pool else []
    return song.recs + disk_only


CANDIDATE_HEADER = (
    "group new youtube_id title lrclib_id in_pool on_disk picked track_len album_len "
    "timing timing_size duration gap status reason speed shift_s spread_s matched total "
    "dropped mistimed_n mistimed unheard unclaimed_run refusal "
    "ref_status ref_shift_s ref_matched ref_total ref_mistimed ref_unheard "
    "ref_unclaimed_run ref_flags"
).split()


def candidate_row(song: SongResult, rec: Rec) -> list[object]:
    fit, ref, record = rec.fit, rec.ref, rec.record
    gap = length_gap_s(record.get("duration"), song.length)
    return [
        song.group,
        int(song.new),
        song.youtube_id,
        song.title,
        rec.id,
        int(rec.in_pool),
        int(rec.on_disk),
        int(rec is song.pick),
        len(record.get("trackName") or ""),
        len(record.get("albumName") or ""),
        rec.timing_id,
        rec.timing_size,
        record.get("duration"),
        "" if gap is None else f"{gap:+d}",
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
        fit.unclaimed_run,
        rec.refusal or "",
        *(
            [
                verdict(ref),
                num(ref.shift_s),
                ref.matched,
                ref.total,
                len(ref.mistimed),
                indexes(ref.unheard),
                ref.unclaimed_run,
                " ".join(rec.flags) or "none",
            ]
            if ref
            else [""] * 8
        ),
    ]


SONG_HEADER = (
    "group reason new youtube_id title length query records timings passing pick_id "
    "pick_mistimed pick_unclaimed_run pick_timing_size ref_ok caption_status caption_shift_s "
    "ref_flags on_disk_id on_disk_refusal pick_has_disk_timing needs_verdict"
).split()


def reference_column(song: SongResult) -> str:
    """The pick's reference flags: ``none``, the names, or ``no reference``."""
    if not song.pick:
        return ""
    if not song.ref_ok:
        return "no reference"
    return " ".join(song.pick.flags) or "none"


def same_as_disk(song: SongResult) -> str:
    if not (song.pick and song.disk):
        return ""
    return yes_no(song.pick.timing == song.disk.timing)


def ref_ok_column(song: SongResult) -> int | str:
    return int(song.ref_ok) if song.group == CAPTIONED and song.probed else ""


def pick_columns(song: SongResult) -> list[object]:
    """The pick's id, mistimed lines, unclaimed run and timing size."""
    pick = song.pick
    if not pick:
        return [""] * 4
    return [pick.id, len(pick.fit.mistimed), pick.fit.unclaimed_run, pick.timing_size]


def disk_columns(song: SongResult) -> list[object]:
    """The on-disk record's id and refusal, and whether the pick has its timing."""
    disk = song.disk
    return [disk.id if disk else "", (disk.refusal or "passes") if disk else "", same_as_disk(song)]


def song_row(song: SongResult) -> list[object]:
    caption = song.caption
    return [
        song.group,
        song.reason,
        int(song.new),
        song.youtube_id,
        song.title,
        num(song.length, 1),
        song.query,
        len(song.recs),
        len({rec.timing for rec in song.recs}),
        sum(rec.passes for rec in song.recs),
        *pick_columns(song),
        ref_ok_column(song),
        verdict(caption) if caption else "",
        num(caption.shift_s) if caption else "",
        reference_column(song),
        *disk_columns(song),
        yes_no(song.needs_verdict) if song.pick else "",
    ]


def table_p(results: list[SongResult]) -> str:
    """Per group, and for the new songs apart (they also count in their group)."""
    rows = []
    for label, members in [
        *((group, [s for s in results if s.group == group]) for group in GROUPS),
        ("new", [s for s in results if s.new]),
    ]:
        rows.append(
            [
                label,
                len(members),
                sum(s.reason == NO_LENGTH for s in members),
                sum(s.reason == LRCLIB_UNAVAILABLE for s in members),
                sum(s.probed and not s.recs for s in members),
                sum(s.pick is not None for s in members),
            ]
        )
    header = ["Group", "Songs", NO_LENGTH, LRCLIB_UNAVAILABLE, "No synced record", "With a pick"]
    reasons = Counter(s.reason for s in results if s.group == OUT_OF_SCOPE)
    scope = [[reason, reasons[reason]] for reason in SCOPE_REASONS]
    return md_table(header, rows) + "\n\n" + md_table([OUT_OF_SCOPE + " reason", "Songs"], scope)


def table_s(results: list[SongResult]) -> str:
    rows = []
    for song in (s for s in results if s.group in GROUPS):
        refusals = Counter(rec.refusal for rec in song.recs)
        rows.append(
            [
                song.group,
                int(song.new),
                song.youtube_id,
                song.title,
                song.reason,
                len(song.recs),
                len({rec.timing for rec in song.recs}),
                sum(rec.passes for rec in song.recs),
                "/".join(str(refusals[name]) for name in REFUSALS),
                *pick_columns(song),
                ref_ok_column(song),
                reference_column(song),
                *disk_columns(song),
                yes_no(song.needs_verdict) if song.pick else "",
            ]
        )
    header = (
        "Group New youtube_id Title Skipped Records Timings Passing "
        f"{'/'.join(REFUSALS)} Pick Mistimed Unclaimed Timing_size ref_ok Reference_flags "
        "On_disk_id On_disk_refusal Pick_has_disk_timing Needs_verdict"
    ).split()
    return md_table(header, rows)


def table_k(results: list[SongResult], old_cache: Path | None) -> str:
    by_id = {s.youtube_id: s for s in results}
    rows = []
    for youtube_id, ids in GATE_M_WRONG.items():
        song = by_id.get(youtube_id)
        runnable = song is not None and song.probed and bool(song.words)
        pool = {rec.id: rec for rec in song.recs} if runnable else {}
        old = {r.get("id"): r for r in read_old_records(old_cache, youtube_id)} if runnable else {}
        for record_id in ids:
            source = locate_record(record_id, set(pool), set(old))
            rec = None
            if source == "pool":
                rec = pool[record_id]
            elif source == "old cache":
                rec = old_rec(old[record_id], song)
            rows.append(k_row(youtube_id, record_id, source, rec, song, runnable))
    header = "youtube_id lrclib_id Source In_pool Status Speed Mistimed Unclaimed Refusal Picked"
    return md_table(header.split() + ["Note"], rows)


def k_row(
    youtube_id: str,
    record_id: int,
    source: str,
    rec: Rec | None,
    song: SongResult | None,
    runnable: bool,
) -> list[object]:
    if source == "not found":
        return [
            youtube_id,
            record_id,
            source,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "" if runnable else "song not probed in this run",
        ]
    fit = rec.fit
    return [
        youtube_id,
        record_id,
        source,
        yes_no(source == "pool"),
        verdict(fit),
        f"{fit.speed:.4f}",
        len(fit.mistimed),
        fit.unclaimed_run,
        rec.refusal or "passes",
        yes_no(rec is song.pick),
        "",
    ]


def old_rec(record: dict, song: SongResult) -> Rec:
    """A GATE M record from the old cache, fitted as the search's records are."""
    fit = fit_record(record, song.words, song.length)
    key = timing_key(record["syncedLyrics"])
    return Rec(record, fit, lrc_auto_pick.refusal(fit), False, False, key, record.get("id"), 0)


def table_x(results: list[SongResult]) -> str:
    rows = []
    for song in results:
        for group in flagged_unpicked(song.recs, song.pick):
            rec = group[0]
            rows.append(
                [
                    song.title,
                    song.youtube_id,
                    ", ".join(str(r.id) for r in group),
                    " ".join(rec.flags),
                    len(rec.fit.mistimed),
                    rec.fit.unclaimed_run,
                ]
            )
    header = ["Song", "youtube_id", "Ids of the timing", "Flags", "Mistimed", "Unclaimed"]
    return md_table(header, rows)


def table_v(results: list[SongResult]) -> str:
    """Songs with a pick at other limits. Sensitivity only: never read for the verdict."""
    probed = [s for s in results if s.probed]
    rows = []
    for label, members in [
        *((group, [s for s in probed if s.group == group]) for group in GROUPS),
        ("new", [s for s in probed if s.new]),
    ]:
        for mistimed in V_MISTIMED:
            rows.append(
                [
                    label,
                    mistimed,
                    len(members),
                    *(songs_with_pick_at(members, mistimed, limit) for limit in V_UNCLAIMED),
                ]
            )
    header = ["Group", "Mistimed <=", "Songs"] + [f"Unclaimed <= {n}" for n in V_UNCLAIMED]
    return md_table(header, rows)


def table_l(results: list[SongResult]) -> str:
    """The picks that need a verdict, in the order to listen to them."""
    songs = sorted((s for s in results if s.pick and s.needs_verdict), key=listen_key)
    rows = []
    for rank, song in enumerate(songs, 1):
        tier = listen_tier(song)
        why = ["no reference", "flagged: " + " ".join(song.pick.flags), "unflagged"][tier]
        rows.append(
            [
                rank,
                song.group,
                int(song.new),
                song.title,
                song.youtube_id,
                song.pick.id,
                why,
                listen_name(song.stem, song.pick.id),
            ]
        )
    header = "Rank Group New Title youtube_id lrclib_id Why Listen_file".split()
    return md_table(header, rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def read_baseline(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, required=True, help="the song library")
    parser.add_argument("--out", type=Path, default=Path(get_temp_directory()) / "lrclib_fit_pick")
    parser.add_argument("--baseline", type=Path, help="ids of the songs that are not new")
    parser.add_argument("--old-cache", type=Path, help="an earlier probe's records, for Table K")
    parser.add_argument("--listen-dir", type=Path, help="default: <out>/listen")
    parser.add_argument("--only", action="extend", nargs="+", default=[], metavar="ID")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "started").write_text("", encoding="utf-8")
    run = Run(out, args.listen_dir or out / "listen", read_baseline(args.baseline))

    statuses = [
        s for s in library_statuses(args.folder) if not args.only or song_id(s) in args.only
    ]
    results = []
    for n, status in enumerate(statuses, 1):
        logger.info("[%d/%d] %s", n, len(statuses), status.path.name)
        results.append(probe_song(status, run))

    write_tsv(
        out / "candidates.tsv",
        CANDIDATE_HEADER,
        [candidate_row(s, rec) for s in results for rec in song_recs(s)],
    )
    write_tsv(out / "songs.tsv", SONG_HEADER, [song_row(s) for s in results])

    print(
        f"Bar in force: mistimed <= {lrc_auto_pick.MAX_MISTIMED}, unclaimed run <= "
        f"{lrc_auto_pick.MAX_UNCLAIMED_RUN}, speed 1.0. {len(results)} songs in {args.folder}; "
        f"output in {out}; listen files in {run.listen_dir}.\n"
    )
    print("## Table P: groups and skip reasons\n\n" + table_p(results) + "\n")
    print("## Table S: songs\n\n" + table_s(results) + "\n")
    print("## Table K: GATE M LRC-wrong records\n\n" + table_k(results, args.old_cache) + "\n")
    print("## Table X: flagged passing records not picked\n\n" + table_x(results) + "\n")
    print("## Table V: songs with a pick at other limits\n\n" + table_v(results) + "\n")
    print("## Table L: the listen list\n\n" + table_l(results))


if __name__ == "__main__":
    main()
