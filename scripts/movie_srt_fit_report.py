#!/usr/bin/env python3
"""Run the movie-subtitle slice fit over every slice in a folder, as a table.

Each ``<name>.srt`` in the slices folder is the stretch of a movie's subtitles
that one library song covers. The name is resolved to a song by
case-insensitive substring of the video's filename (stop on none or several),
then the fit runs against that song's heard words on disk: the alignment
bundle's ``transcribe_words`` and the ``subtitles/<stem>.en.asr.json3``
caption, each on its own and then both together. One row per run, as markdown,
so the table pastes into a plan's results log as is.

The verdict column uses ``MIN_MATCHED_SHARE`` and the spread limit of
``offset_mad_against_cues`` as they stand in the code; "slope" is the free
speed (``free_speed``) over the order-only anchors, printed whichever speed the
fit kept.

With ``--cross``, a second table runs each slice against every *other* slice's
song (transcribe words): the wrong-song cases a matched-share floor must refuse.

The slices are copyrighted subtitle text: keep them out of the repo.

Run from the repo root::

    python scripts/movie_srt_fit_report.py [--folder PATH] [--slices PATH] [--cross]
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running as ``python scripts/movie_srt_fit_report.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.ffmpeg import probe_duration  # noqa: E402
from pikaraoke.lib.get_platform import get_default_dl_dir, get_platform  # noqa: E402
from pikaraoke.lib.library_regen import VIDEO_EXTS, read_bundle  # noqa: E402
from pikaraoke.lib.srt_cues import cue_spans_from_srt  # noqa: E402
from pikaraoke.lib.srt_slice_fit import (  # noqa: E402
    TRANSCRIBE,
    SliceFit,
    _CueTokens,
    _match_by_order,
    fit_slice,
    free_speed,
    heard_streams,
)

HEADER = (
    "| Song | Heard | Words | Clip s | Status | Matched | Dropped | Shift s | Speed | "
    "Spread s | Anchors | Slope |\n|---|---|---|---|---|---|---|---|---|---|---|---|"
)
CROSS_HEADER = (
    "| Slice (song) | Against | Status | Matched | Spread s | Anchors |\n|---|---|---|---|---|---|"
)


def resolve_song(folder: Path, name: str) -> Path:
    """The one video in ``folder`` whose filename contains ``name``; exits otherwise."""
    matches = sorted(
        p
        for p in folder.iterdir()
        if p.suffix.lower() in VIDEO_EXTS and name.lower() in p.name.lower()
    )
    if len(matches) != 1:
        sys.exit(
            f"Slice {name!r} matches {len(matches)} videos in {folder}: "
            + (", ".join(p.name for p in matches) or "none")
        )
    return matches[0]


def free_slope(srt_text: str, words: list[dict]) -> float | None:
    """The free speed over the order-only anchors."""
    texts, spans = cue_spans_from_srt(srt_text)
    anchors, _ = _match_by_order(_CueTokens.of(texts), words)
    return free_speed(anchors, spans)


def row(song: Song, label: str, n_words: int | None, fit: SliceFit, slope) -> str:
    status = fit.status + (f"/{fit.reason}" if fit.reason else "")
    spread = "" if fit.spread_s is None else f"{fit.spread_s:.3f}"
    slope_text = "" if slope is None else f"{slope:.4f}"
    words = "" if n_words is None else n_words
    return (
        f"| {song.title} | {label} | {words} | {song.length:.0f} | {status} | "
        f"{fit.matched}/{fit.total} | {fit.dropped} | {fit.shift_s:.2f} | {fit.speed:.4f} | "
        f"{spread} | {fit.anchors} | {slope_text} |"
    )


@dataclass
class Song:
    """A slice's song: its heard-word streams on disk and its length."""

    path: Path
    streams: dict[str, list[dict]]
    length: float

    @property
    def title(self) -> str:
        return self.path.stem.split("---")[0][:40]


def load_song(folder: Path, name: str) -> Song:
    song = resolve_song(folder, name)
    bundle = read_bundle(folder, song.stem)
    asr_path = folder / "subtitles" / f"{song.stem}.en.asr.json3"
    asr_text = asr_path.read_text(encoding="utf-8") if asr_path.is_file() else None
    length = (bundle or {}).get("media_duration_s") or probe_duration(song)
    if not length:
        sys.exit(f"{song.name}: no clip length (bundle has none and ffprobe failed)")
    return Song(song, heard_streams(bundle, asr_text), length)


def report(song: Song, srt_text: str) -> list[str]:
    if not song.streams:
        return [row(song, "none", None, fit_slice(srt_text, {}, song.length), None)]
    rows = [
        row(
            song,
            name,
            len(words),
            fit_slice(srt_text, {name: words}, song.length),
            free_slope(srt_text, words),
        )
        for name, words in song.streams.items()
    ]
    if len(song.streams) > 1:
        both = fit_slice(srt_text, song.streams, song.length)
        rows.append(row(song, f"both->{both.heard_source}", None, both, None))
    return rows


def cross_report(slices: dict[str, str], songs: dict[str, Song]) -> list[str]:
    """Each slice against every other slice's song: the cases that must be refused."""
    rows = [CROSS_HEADER]
    for slice_name, srt_text in slices.items():
        for other_name, other in songs.items():
            words = other.streams.get(TRANSCRIBE)
            if other_name == slice_name or not words:
                continue
            fit = fit_slice(srt_text, {TRANSCRIBE: words}, other.length)
            status = fit.status + (f"/{fit.reason}" if fit.reason else "")
            spread = "" if fit.spread_s is None else f"{fit.spread_s:.3f}"
            rows.append(
                f"| {songs[slice_name].title} | {other.title} | {status} | "
                f"{fit.matched}/{fit.total} | {spread} | {fit.anchors} |"
            )
    return rows


def main() -> None:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, default=Path(default_folder))
    parser.add_argument("--slices", type=Path, default=Path(default_folder) / "movie_subs")
    parser.add_argument(
        "--cross", action="store_true", help="also run each slice against the other songs"
    )
    args = parser.parse_args()
    slices = {p.stem: p.read_text(encoding="utf-8-sig") for p in sorted(args.slices.glob("*.srt"))}
    songs = {name: load_song(args.folder, name) for name in slices}
    print(HEADER)
    for name, srt_text in slices.items():
        print("\n".join(report(songs[name], srt_text)))
    if args.cross:
        print("\n" + "\n".join(cross_report(slices, songs)))


if __name__ == "__main__":
    main()
