"""Read-only song status: what a song's alignment bundle says about its lyrics and timing.

The web UI's Song Info page and library lists are built on this. Nothing here
writes, so it is safe to call on a library the app is playing from.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pikaraoke.lib import lrclib
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.library_regen import list_videos, read_bundle
from pikaraoke.lib.metadata_parser import extract_youtube_id

# Ken, 2026-10-20: a song with 15% or more of its lines guessed "looks poor".
POOR_GUESSED_SHARE = 0.15


@dataclass(frozen=True)
class SongStatus:
    path: Path
    youtube_id: str | None
    category: str  # "current" | "behind" | "no_lyrics" | "not_processed"
    schema_version: int | None
    origin: str | None  # bundle lyrics.origin: "srt" | "genius"
    genius: dict | None  # lyrics.genius: {id, title, artist}
    lrclib: dict | None  # lyrics.lrclib: trackName, artistName, albumName, duration, id
    lrclib_state: str  # "used" | "rejected" | "none" | "skipped" | "n/a"
    lrclib_reason: str | None  # joint_stats.lrclib_fill.reason, when rejected
    lrclib_filled: int  # lines the LRCLIB fill placed
    ytasr_used: bool  # lyrics.ytasr present
    method: str | None  # pipeline_decisions.method_used: "joint" | "cue_align"
    line_count: int | None  # output_summary.line_count
    lines_timed: int | None  # output_summary.lines_with_words
    timed_by: dict | None  # joint only: lines won by aligner / transcription / captions
    media_duration_s: float | None
    captured_at: str | None

    @property
    def guessed(self) -> int | None:
        """Lines with no word timing; placed between their neighbours."""
        if self.line_count is None or self.lines_timed is None:
            return None
        return self.line_count - self.lines_timed

    @property
    def poor(self) -> bool:
        guessed = self.guessed
        if guessed is None or not self.line_count:
            return False
        return guessed / self.line_count >= POOR_GUESSED_SHARE


def song_status(song: Path) -> SongStatus:
    bundle = read_bundle(song.parent, song.stem)
    if bundle is None:
        karaoke = song.parent / "karaoke" / f"{song.stem}.ass"
        category = "no_lyrics" if karaoke.is_file() else "not_processed"
        return SongStatus(
            path=song,
            youtube_id=extract_youtube_id(str(song)),
            category=category,
            schema_version=None,
            origin=None,
            genius=None,
            lrclib=None,
            lrclib_state="n/a",
            lrclib_reason=None,
            lrclib_filled=0,
            ytasr_used=False,
            method=None,
            line_count=None,
            lines_timed=None,
            timed_by=None,
            media_duration_s=None,
            captured_at=None,
        )

    version = bundle.get("schema_version", 0)
    lyrics = bundle.get("lyrics") or {}
    summary = bundle.get("output_summary") or {}
    joint = bundle.get("joint_stats") or {}
    method = (bundle.get("pipeline_decisions") or {}).get("method_used")
    origin = lyrics.get("origin")
    fill = joint.get("lrclib_fill") or {}
    state = _lrclib_state(song, origin, lyrics, fill)
    return SongStatus(
        path=song,
        youtube_id=extract_youtube_id(str(song)),
        category="behind" if version < SCHEMA_VERSION else "current",
        schema_version=version,
        origin=origin,
        genius=lyrics.get("genius") or None,
        lrclib=_lrclib_match(lyrics),
        lrclib_state=state,
        lrclib_reason=fill.get("reason") if state == "rejected" else None,
        lrclib_filled=len(fill.get("filled_lids") or []),
        ytasr_used=bool(lyrics.get("ytasr")),
        method=method,
        line_count=summary.get("line_count"),
        lines_timed=summary.get("lines_with_words"),
        timed_by=(
            {
                "aligner": joint.get("align_won", 0),
                "transcription": joint.get("transcribe_won", 0),
                "captions": joint.get("ytasr_won", 0),
            }
            if method == "joint"
            else None
        ),
        media_duration_s=bundle.get("media_duration_s"),
        captured_at=bundle.get("captured_at"),
    )


def _lrclib_match(lyrics: dict) -> dict | None:
    """The LRCLIB record the bundle's run used, or None.

    The pipeline also records a skip marker as an LRCLIB reference (``lrc_file``
    alone, no ``id``). That is a match the admin rejected, not one.
    """
    ref = lyrics.get("lrclib")
    return ref if ref and ref.get("id") is not None else None


def _lrclib_state(song: Path, origin: str | None, lyrics: dict, fill: dict) -> str:
    """How LRCLIB figures in a Genius song: the disk says what the admin chose now,
    the bundle says what the last run did with it."""
    if origin != "genius":
        return "n/a"
    if lrclib.is_skip_marker(lrclib.lrc_path(song)):
        return "skipped"
    if fill.get("eligible"):
        return "used"
    if _lrclib_match(lyrics):
        return "rejected"
    return "none"


def library_statuses(folder: Path) -> list[SongStatus]:
    """Status of every video in ``folder``, in :func:`list_videos` order."""
    return [song_status(video) for video in list_videos(folder)]


def overview_counts(statuses: list[SongStatus]) -> dict[str, int]:
    return {
        "behind": sum(s.category == "behind" for s in statuses),
        "poor": sum(s.poor for s in statuses),
        "no_lyrics": sum(s.category == "no_lyrics" for s in statuses),
        "all": len(statuses),
    }


@dataclass(frozen=True)
class HistoryEntry:
    captured_at: str
    schema_version: int | None
    genius: dict | None
    lrclib: dict | None
    line_count: int | None
    lines_timed: int | None
    backup: str | None  # backup folder name; None for the current bundle


def song_history(song: Path) -> list[HistoryEntry]:
    """Every distinct version of the song's bundle, newest first.

    The current bundle, then each ``regen_backup_*`` folder newest first. A
    version saved in several backups is listed once, under the newest folder
    that holds it.
    """
    folder = song.parent
    sources: list[tuple[str | None, Path]] = [(None, folder)]
    backups = sorted(
        (d for d in folder.glob("regen_backup_*") if d.is_dir()), key=lambda d: d.name, reverse=True
    )
    sources += [(d.name, d) for d in backups]

    entries: list[HistoryEntry] = []
    seen: set[str] = set()
    for backup, root in sources:
        bundle = read_bundle(root, song.stem)
        captured_at = bundle.get("captured_at") if bundle else None
        if captured_at is None or captured_at in seen:
            continue
        seen.add(captured_at)
        lyrics = bundle.get("lyrics") or {}
        summary = bundle.get("output_summary") or {}
        entries.append(
            HistoryEntry(
                captured_at=captured_at,
                schema_version=bundle.get("schema_version"),
                genius=lyrics.get("genius") or None,
                lrclib=_lrclib_match(lyrics),
                line_count=summary.get("line_count"),
                lines_timed=summary.get("lines_with_words"),
                backup=backup,
            )
        )
    return sorted(entries, key=lambda e: e.captured_at, reverse=True)
