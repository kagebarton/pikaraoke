#!/usr/bin/env python3
"""Report how a Genius sheet's lines pair with a song's LRC lines, as tables.

For each song the LRC on disk is fitted to the clip as the LRCLIB timing check
fits it (``fit_slice(lrc_to_srt(...))`` against the words heard in the clip), and
a lyric sheet is paired with the fitted lines by ``lrc_pairing.pair_lines``: the
function the feature would ship. The sheet is a Genius page named by id (fetched
from Genius) or, with no id, the song's own Genius sheet stored in its bundle.

Table 1 has a row per ``--song``. Table 2 has the same columns for every
Genius-origin song with a usable LRC, using its bundle's sheet and no network: it
answers whether two sources split lines alike across the library.

Read only, except ``--write-sheet DIR``: for each viable Table 1 song it writes the
built sheet to ``DIR`` as ``<stem>.lrclib-genius.srt``, and ``<stem>.listen.txt``
with the sheet lines whose words differ from the LRC's, as the places to listen.
``DIR`` must not be inside the library. Lyrics are copyrighted text, so the tables
and the listen list carry line numbers (counted as the pipeline loads the lines)
and times, never text; the built sheets do hold text and stay off git.

Run from the repo root::

    python scripts/genius_lrc_pairing_report.py [--folder PATH] \\
        [--song "Your Idol=12047339"] [--song "Seven"] [--write-sheet DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running as ``python scripts/genius_lrc_pairing_report.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib import lrclib  # noqa: E402
from pikaraoke.lib.genius import GeniusClient, GeniusUnavailable  # noqa: E402
from pikaraoke.lib.genius_lyrics import parse_lyric_lines  # noqa: E402
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
from pikaraoke.lib.library_tools import LRC_MAX_GAP_S  # noqa: E402
from pikaraoke.lib.lrc_pairing import (  # noqa: E402
    Pairing,
    Stretch,
    pair_lines,
    timed_sheet_srt,
)
from pikaraoke.lib.lrclib import map_lines_to_cues  # noqa: E402
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.lib.srt_cues import cue_spans_from_srt  # noqa: E402
from pikaraoke.lib.srt_slice_fit import (  # noqa: E402
    FITS,
    SliceFit,
    fit_slice,
    heard_streams,
    lrc_to_srt,
)

# ``srt`` writes milliseconds; fitted starts and the read-back spans agree to that.
START_TOLERANCE_S = 0.002

HEADER = (
    "| Song | Sheet | LRC fit | Paired on | Genius lines | LRC lines (paired/file) | "
    "Same-start LRC lines | Text pairs | Text pairs (sheet cleaned too) | Position pairs | "
    "Position stretches | "
    "Refused stretches | Gap s | LRC check | Viable | Reload changed/dropped | "
    "fit.lines = reload |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
)


class Skipped(Exception):
    """A song the report can't run; the message is its row."""


@dataclass
class Sheet:
    """The lyric lines to pair, and where they came from."""

    label: str
    lines: list[str]


@dataclass
class Analysis:
    status: SongStatus
    sheet: Sheet
    fit: SliceFit
    gap_s: int | None
    lrc_texts: list[str]  # the lines paired against: the fitted ones when the fit fits
    spans: list[tuple[float, float]]
    lrc_file_lines: int
    same_start: int
    pairing: Pairing
    cleaned_text_pairs: int  # text pairs when the sheet is cleaned as the cue route would too
    changed: list[int]
    dropped: list[int]
    fit_lines_match: str

    @property
    def lrc_check(self) -> str:
        """What ``LibraryTools._fit_lrc_timing`` makes of the LRC alone."""
        if self.fit.status != FITS:
            return "refused"
        within = self.gap_s is not None and abs(self.gap_s) <= LRC_MAX_GAP_S
        return "viable" if within else "overridable"

    @property
    def viable(self) -> bool:
        return self.lrc_check == "viable" and not self.pairing.refused


def title(status: SongStatus) -> str:
    return status.path.stem.split("---")[0][:40]


def line_range(first: int, end: int) -> str:
    """A half-open range of line indexes as ``a-b`` (inclusive); ``-`` when empty."""
    return f"{first}-{end - 1}" if end > first else "-"


def refused_text(stretches: tuple[Stretch, ...]) -> str:
    return (
        "; ".join(f"genius {line_range(*s.sheet)} / lrc {line_range(*s.lrc)}" for s in stretches)
        or "-"
    )


def clip_time(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def reload_changes(sheet: list[str]) -> tuple[list[str], list[int], list[int]]:
    """A sheet read back by the cue route: its lines, and the indexes changed and dropped.

    Every line is given its own span, so the reload tells which line each cue was.
    """
    n = len(sheet)
    identity = Pairing({i: i for i in range(n)}, (), ())
    spans = [(float(i), i + 1.0) for i in range(n)]
    texts, read_back = cue_spans_from_srt(timed_sheet_srt(sheet, spans, identity))
    kept = [round(start) for start, _ in read_back]
    changed = [i for i, text in zip(kept, texts) if text != sheet[i]]
    return texts, changed, sorted(set(range(n)) - set(kept))


def fit_lines_agree(fit: SliceFit, texts: list[str], spans: list[tuple[float, float]]) -> str:
    """Whether ``fit.lines`` (what the flags index) and the reloaded fitted SRT are the same lines."""
    if fit.status != FITS:
        return "n/a"
    if len(fit.lines) != len(texts):
        return f"NO ({len(fit.lines)} vs {len(texts)} lines)"
    text_diffs = sum(a != b for (a, _), b in zip(fit.lines, texts))
    start_diffs = sum(abs(a - s[0]) > START_TOLERANCE_S for (_, a), s in zip(fit.lines, spans))
    return (
        "yes"
        if not text_diffs and not start_diffs
        else f"NO ({text_diffs} text, {start_diffs} start)"
    )


def analyse(status: SongStatus, sheet: Sheet) -> Analysis:
    song = status.path
    lrc = lrclib.read_song_lrc(song)
    if lrc.state != "match":  # changed since the status read it
        raise Skipped(f"LRC {lrc.state}")
    bundle = read_bundle(song.parent, song.stem)
    length = media_duration(SongJob(song, bundle, "report"))
    if not length:
        raise Skipped("no clip length")
    asr_path = song.parent / "subtitles" / f"{song.stem}.en.asr.json3"
    asr_text = asr_path.read_text(encoding="utf-8") if asr_path.is_file() else None
    srt_text = lrc_to_srt(lrc.text)
    fit = fit_slice(srt_text, heard_streams(bundle, asr_text), length)
    file_texts, _ = cue_spans_from_srt(srt_text)
    texts, spans = cue_spans_from_srt(fit.srt) if fit.status == FITS else (file_texts, [])
    starts = [start for start, text in lrclib.lrc_stamps(lrc.text) if text]
    reloaded, changed, dropped = reload_changes(sheet.lines)
    return Analysis(
        status=status,
        sheet=sheet,
        fit=fit,
        gap_s=length_gap_s(lrc.meta.get("duration"), length),
        lrc_texts=texts,
        spans=spans,
        lrc_file_lines=len(file_texts),
        same_start=len(starts) - len(set(starts)),
        pairing=pair_lines(sheet.lines, texts),
        cleaned_text_pairs=len(map_lines_to_cues(reloaded, texts)),
        changed=changed,
        dropped=dropped,
        fit_lines_match=fit_lines_agree(fit, texts, spans),
    )


def row(a: Analysis) -> str:
    fit = a.fit
    verdict = fit.status + (f"/{fit.reason}" if fit.reason else "")
    verdict += f" ({fit.heard_source})" if fit.heard_source else ""
    pairing = a.pairing
    position_lines = sum(s.sheet[1] - s.sheet[0] for s in pairing.by_position)
    gap = "" if a.gap_s is None else f"{a.gap_s:+d}"
    return (
        f"| {title(a.status)} | {a.sheet.label} | {verdict} | "
        f"{'fitted lines' if fit.status == FITS else 'all lines'} | {len(a.sheet.lines)} | "
        f"{len(a.lrc_texts)}/{a.lrc_file_lines} | {a.same_start} | {len(pairing.by_text)} | "
        f"{a.cleaned_text_pairs} | {position_lines} | {len(pairing.by_position)} | {refused_text(pairing.refused)} | "
        f"{gap} | {a.lrc_check} | {'yes' if a.viable else 'no'} | "
        f"{len(a.changed)}/{len(a.dropped)} | {a.fit_lines_match} |"
    )


def reload_detail(a: Analysis) -> str | None:
    if not a.changed and not a.dropped:
        return None
    return (
        f"- {title(a.status)}: changed on reload {','.join(map(str, a.changed)) or '-'}; "
        f"dropped {','.join(map(str, a.dropped)) or '-'}"
    )


def listen_list(a: Analysis) -> list[str]:
    """The sheet lines whose words differ from the LRC's own line, by index and clip time."""
    by_text = a.pairing.by_text
    lines = []
    for sheet_line, lrc_line in sorted(a.pairing.line_map().items()):
        if lrclib.normalize_line(a.sheet.lines[sheet_line]) == lrclib.normalize_line(
            a.lrc_texts[lrc_line]
        ):
            continue
        how = "text" if sheet_line in by_text else "position"
        lines.append(
            f"genius {sheet_line} / lrc {lrc_line} / {clip_time(a.spans[lrc_line][0])} / {how}"
        )
    return lines


def write_sheet(a: Analysis, out: Path) -> None:
    stem = a.status.path.stem
    sheet_srt = timed_sheet_srt(a.sheet.lines, a.spans, a.pairing)
    (out / f"{stem}.lrclib-genius.srt").write_text(sheet_srt, encoding="utf-8")
    listen = listen_list(a)
    (out / f"{stem}.listen.txt").write_text("\n".join(listen) + "\n", encoding="utf-8")


def bundle_sheet(status: SongStatus) -> Sheet:
    bundle = read_bundle(status.path.parent, status.path.stem) or {}
    lines = (bundle.get("lyrics") or {}).get("lines") or []
    if status.origin != "genius" or not lines:
        raise Skipped(f"no Genius sheet in the bundle (origin {status.origin})")
    return Sheet("bundle", list(lines))


def genius_sheet(client: GeniusClient, genius_id: int) -> tuple[Sheet, str]:
    """The Genius page's lyric lines, as the Genius card shows them, and its title and artist."""
    try:
        song = client.fetch_song(genius_id)
    except GeniusUnavailable as e:
        raise Skipped(f"Genius unavailable ({e})") from e
    lines = [item["text"] for item in parse_lyric_lines(song.text)]
    return Sheet(f"genius {genius_id}", lines), f"{genius_id} | {song.title} | {song.artist}"


def parse_song(arg: str) -> tuple[str, int | None]:
    """``"<name part>=<genius id>"``; no ``=`` or no id after it means the bundle's sheet."""
    name, _, ident = arg.rpartition("=") if "=" in arg else (arg, "", "")
    if ident and not ident.isdigit():
        raise argparse.ArgumentTypeError(f"not a Genius id: {ident!r}")
    return name.strip(), int(ident) if ident else None


def skipped_row(label: str, reason: str) -> str:
    return f"| {label} | {reason} |"


def named_song(statuses: list[SongStatus], name: str) -> SongStatus:
    found = [s for s in statuses if name.lower() in s.path.stem.lower()]
    if len(found) != 1:
        raise Skipped(f"{len(found)} songs match")
    return found[0]


def main() -> None:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", type=Path, default=Path(default_folder))
    parser.add_argument("--song", type=parse_song, action="append", default=[])
    parser.add_argument("--write-sheet", type=Path, metavar="DIR")
    args = parser.parse_args()
    out = args.write_sheet.resolve() if args.write_sheet else None
    library = args.folder.resolve()
    if out and (out == library or library in out.parents):
        parser.error("--write-sheet DIR must not be the library folder or inside it")

    statuses = library_statuses(args.folder)
    client = GeniusClient(api_token=PreferenceManager().get("genius_token", ""))
    pages, rows1, details = [], [], []
    for name, genius_id in args.song:
        try:
            status = named_song(statuses, name)
            if genius_id is None:
                sheet = bundle_sheet(status)
            else:
                sheet, page = genius_sheet(client, genius_id)
                pages.append(page)
            a = analyse(status, sheet)
        except Skipped as e:
            rows1.append(skipped_row(name, str(e)))
            continue
        rows1.append(row(a))
        details.append(reload_detail(a))
        if a.viable and out:
            out.mkdir(parents=True, exist_ok=True)
            write_sheet(a, out)

    rows2 = []
    for status in statuses:
        if status.origin != "genius" or status.lrc_match is None:
            continue
        try:
            a = analyse(status, bundle_sheet(status))
        except Skipped as e:
            rows2.append(skipped_row(title(status), str(e)))
            continue
        rows2.append(row(a))
        details.append(reload_detail(a))

    print(f"Folder {args.folder}. Fit thresholds in force: LRC_MAX_GAP_S={LRC_MAX_GAP_S}.\n")
    print("Genius pages fetched (id | title | artist):")
    print("\n".join(f"- {page}" for page in pages) or "- none")
    print("\nTable 1: the named songs\n")
    print(HEADER)
    print("\n".join(rows1))
    print(f"\nTable 2: every Genius-origin song with a usable LRC ({len(rows2)}), bundle sheets\n")
    print(HEADER)
    print("\n".join(rows2))
    print("\nLines the saved sheet's reload changes or drops (line indexes in the Genius sheet):")
    print("\n".join(d for d in details if d) or "- none")
    if out:
        print(f"\nSheets written to {out}")


if __name__ == "__main__":
    main()
