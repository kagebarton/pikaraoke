#!/usr/bin/env python3
"""Run the LRC timing fit over every joint song that has a usable LRC, as tables.

For each joint-timed song in the library whose ``lyrics/<stem>.lrc`` is a real
match (not a skip marker), the LRC's own lines are fitted to the clip against
each heard-word stream on its own: the alignment bundle's ``transcribe_words``
and the ``subtitles/<stem>.en.asr.json3`` caption. A song with no heard words
gets its ``no_reference`` row.

The first table has one row per song and stream: the fit's verdict and numbers,
the length gap to the video (read from the bundle's record of the match and,
separately, from the LRC file's own length tag, since a bundle from before
schema 9 never recorded the match), the mistimed and the unheard lines, the
flagged runs at three minimum lengths and the unheard stretches. The second table
prints the mistimed lines again at five tolerances, so a tolerance can be checked
without running anything again.

Read only: nothing is written next to a song. An LRC is copyrighted text, so the
tables carry line numbers (counted as the pipeline loads the lines), never text.

Run from the repo root::

    python scripts/lrc_timing_report.py [--folder PATH]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Allow running as ``python scripts/lrc_timing_report.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import lrclib, srt_slice_fit  # noqa: E402
from pikaraoke.lib.get_platform import get_default_dl_dir, get_platform  # noqa: E402
from pikaraoke.lib.library_regen import (  # noqa: E402
    SongJob,
    media_duration,
    read_bundle,
)
from pikaraoke.lib.library_status import (  # noqa: E402
    SongStatus,
    length_gap_s,
    library_statuses,
)
from pikaraoke.lib.srt_slice_fit import (  # noqa: E402
    SliceFit,
    fit_slice,
    flagged_runs,
    heard_streams,
    lrc_to_srt,
    unheard_runs,
)

TOLERANCES_S = (3.0, 4.0, 5.0, 7.0, 10.0)
MIN_RUNS = (2, 3, 4)

HEADER = (
    "| Song | Origin | LRCLIB | Heard | Words | Clip s | Status | Matched | Shift s | Speed | "
    "Spread s | Anchors | Gap s (bundle) | Gap s (file) | Mistimed | Unheard | Runs>=2 | Runs>=3 | "
    "Runs>=4 | Unheard runs |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
)
TOLERANCE_HEADER = "| Song | Heard | Status | " + " | ".join(
    f"Mistimed @ {t} s" for t in TOLERANCES_S
) + " |\n" "|---|---|---|" + "---|" * len(TOLERANCES_S)


def title(status: SongStatus) -> str:
    return status.path.stem.split("---")[0][:40]


def indexes(lines: tuple[int, ...]) -> str:
    """The lines as ``n: i,j,k``; ``-`` for none."""
    return f"{len(lines)}: {','.join(map(str, lines))}" if lines else "-"


def spans(found: list[tuple[int, int]]) -> str:
    return " ".join(f"{first}-{last}" for first, last in found) or "-"


def runs(fit: SliceFit, min_run: int) -> str:
    return spans(flagged_runs(fit.mistimed, fit.unheard, min_run))


def verdict(fit: SliceFit) -> str:
    return fit.status + (f"/{fit.reason}" if fit.reason else "")


def gap(duration: object, length: float) -> str:
    seconds = length_gap_s(duration, length)
    return "" if seconds is None else f"{seconds:+d}"


def row(
    status: SongStatus,
    stream: str,
    n_words: int | None,
    fit: SliceFit,
    length: float,
    file_duration: object,
) -> str:
    spread = "" if fit.spread_s is None else f"{fit.spread_s:.3f}"
    match = status.lrclib or {}
    return (
        f"| {title(status)} | {status.origin} | {status.lrclib_state} | {stream} | "
        f"{'' if n_words is None else n_words} | {length:.0f} | {verdict(fit)} | "
        f"{fit.matched}/{fit.total} | {fit.shift_s:.2f} | {fit.speed:.4f} | {spread} | "
        f"{fit.anchors} | {gap(match.get('duration'), length)} | "
        f"{gap(file_duration, length)} | {indexes(fit.mistimed)} | {indexes(fit.unheard)} | "
        + " | ".join(runs(fit, n) for n in MIN_RUNS)
        + f" | {spans(unheard_runs(fit.unheard, srt_slice_fit.MIN_UNHEARD_RUN))} |"
    )


def fit_at(srt_text: str, name: str, words: list[dict], length: float, tolerance: float):
    """The fit with ``tolerance`` as the flag tolerance, the module's own left alone."""
    with patch.object(srt_slice_fit, "FLAG_TOLERANCE_S", tolerance):
        return fit_slice(srt_text, {name: words}, length)


def report(status: SongStatus) -> tuple[list[str], list[str]]:
    """The song's rows for the fit table and for the tolerance table."""
    song = status.path
    folder = song.parent
    lrc = lrclib.read_song_lrc(song)
    if lrc.state != "match":  # changed since the status read it
        return [f"| {title(status)} | LRC {lrc.state} |"], []
    lrc_text, meta = lrc.text, lrc.meta
    bundle = read_bundle(folder, song.stem)
    length = media_duration(SongJob(song, bundle, "report"))
    if not length:
        return [f"| {title(status)} | no clip length |"], []
    asr_path = folder / "subtitles" / f"{song.stem}.en.asr.json3"
    asr_text = asr_path.read_text(encoding="utf-8") if asr_path.is_file() else None
    streams = heard_streams(bundle, asr_text)
    srt_text = lrc_to_srt(lrc_text)
    if not streams:
        fit = fit_slice(srt_text, {}, length)
        return [row(status, "none", None, fit, length, meta.get("duration"))], []

    fit_rows, tolerance_rows = [], []
    for name, words in streams.items():
        fit = fit_slice(srt_text, {name: words}, length)
        fit_rows.append(row(status, name, len(words), fit, length, meta.get("duration")))
        by_tolerance = [fit_at(srt_text, name, words, length, t) for t in TOLERANCES_S]
        tolerance_rows.append(
            f"| {title(status)} | {name} | {verdict(fit)} | "
            + " | ".join(indexes(f.mistimed) for f in by_tolerance)
            + " |"
        )
    return fit_rows, tolerance_rows


def main() -> None:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, default=Path(default_folder))
    args = parser.parse_args()

    joint = [
        s for s in library_statuses(args.folder) if s.method == "joint" and s.lrc_match is not None
    ]
    print(
        f"Constants in force: FLAG_TOLERANCE_S={srt_slice_fit.FLAG_TOLERANCE_S}, "
        f"MIN_FLAGGED_RUN={srt_slice_fit.MIN_FLAGGED_RUN}, "
        f"MIN_UNHEARD_RUN={srt_slice_fit.MIN_UNHEARD_RUN}, "
        f"MIN_MATCHED_SHARE={srt_slice_fit.MIN_MATCHED_SHARE}. "
        f"{len(joint)} joint songs with a usable LRC in {args.folder}.\n"
    )
    fit_rows, tolerance_rows = [], []
    for status in joint:
        song_fit_rows, song_tolerance_rows = report(status)
        fit_rows += song_fit_rows
        tolerance_rows += song_tolerance_rows
    print(HEADER)
    print("\n".join(fit_rows))
    print("\n" + TOLERANCE_HEADER)
    print("\n".join(tolerance_rows))


if __name__ == "__main__":
    main()
