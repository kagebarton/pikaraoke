#!/usr/bin/env python3
"""Try a Korean romanizer on the Hangul lines of a song's cue sheet.

For each named song, the cue sheet its next regenerate would read (the same lines
the Edit words page shows) is read, and every line holding Hangul is romanized: only
the Hangul runs are changed, Latin words and punctuation stay. One file per song,
``<stem>.romanized.txt`` in ``--out``, has a tab-separated row per such line: its
number on the Edit words page, its start time, the line and the suggestion, so the
suggestions can be set beside a romanized lyric page and tried in the editor.

Read only: nothing is written next to a song, and ``--out`` may not be the library
folder. The output holds lyric text and stays out of git; stdout carries counts only.
The romanizer is ``koroman``, which is not a project dependency; install it into the
environment for the probe (``pip install koroman==1.0.16``).

Run from the repo root::

    python scripts/romanize_probe.py --song "Your Idol" --song Takedown --out DIR
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Allow running as ``python scripts/romanize_probe.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import koroman  # noqa: E402  # pylint: disable=wrong-import-position,import-error

from pikaraoke.lib.events import EventSystem  # noqa: E402
from pikaraoke.lib.get_platform import get_default_dl_dir, get_platform  # noqa: E402
from pikaraoke.lib.library_regen import RegenError  # noqa: E402
from pikaraoke.lib.library_tools import LibraryTools  # noqa: E402

# Hangul syllables (U+AC00-D7A3), and the jamo blocks a lyric line can also hold
# (U+1100-11FF, U+3130-318F).
_HANGUL = "ᄀ-ᇿ㄰-㆏가-힣"
# Words stay in one run so a sound change carries across the space between them.
_HANGUL_RUN = re.compile(f"[{_HANGUL}]+(?: +[{_HANGUL}]+)*")

HEADER = "line\tstarts\tsheet\tsuggestion\n"


def romanize_hangul(line: str) -> str | None:
    """The line with each Hangul run romanized, or None when it holds no Hangul."""
    suggestion, runs = _HANGUL_RUN.subn(lambda run: koroman.romanize(run.group()), line)
    return suggestion if runs else None


def mmss(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def sheet_reader(folder: Path, state_path: Path) -> LibraryTools:
    """A LibraryTools over ``folder`` used only to read cue sheets: nothing is queued or fetched."""
    return LibraryTools(None, None, str(folder), None, state_path, EventSystem(), None)


def pick_songs(folder: Path, patterns: list[str]) -> list[Path]:
    """The video songs in ``folder`` whose name holds any of ``patterns`` (any case)."""
    videos = sorted(p for p in folder.iterdir() if LibraryTools.is_video(str(p)))
    wanted = [pattern.lower() for pattern in patterns]
    return [p for p in videos if any(pattern in p.stem.lower() for pattern in wanted)]


def main() -> None:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, default=Path(default_folder))
    parser.add_argument(
        "--song",
        action="append",
        required=True,
        metavar="NAME_PART",
        help="part of a song's file name; repeat for more songs",
    )
    parser.add_argument("--out", type=Path, required=True, help="folder for the output files")
    args = parser.parse_args()

    library, out = args.folder.resolve(), args.out.resolve()
    if out == library or library in out.parents:
        parser.error(f"--out must be outside the library folder {library}")
    for pattern in args.song:
        if not pick_songs(library, [pattern]):
            parser.error(f"no song in {library} matches {pattern!r}")
    songs = pick_songs(library, args.song)

    out.mkdir(parents=True, exist_ok=True)
    tools = sheet_reader(library, out / "unused_state.json")
    for song in songs:
        try:
            sheet = tools.word_sheet(str(song))
        except RegenError as e:
            print(f"{song.name}: skipped ({e})")
            continue
        rows = []
        for number, (line, (start, _end)) in enumerate(zip(sheet.lines, sheet.spans), 1):
            suggestion = romanize_hangul(line)
            if suggestion is not None:
                rows.append(f"{number}\t{mmss(start)}\t{line}\t{suggestion}\n")
        state = "an edited" if sheet.edited else "the source's own"
        print(f"{song.name}: {state} sheet, {len(sheet.lines)} lines, {len(rows)} with Hangul")
        if rows:
            (out / f"{song.stem}.romanized.txt").write_text(
                HEADER + "".join(rows), encoding="utf-8"
            )


if __name__ == "__main__":
    main()
