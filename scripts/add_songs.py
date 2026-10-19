#!/usr/bin/env python3
"""Download YouTube videos or playlists into the library and run the pipeline.

Classifies each URL as a video or a playlist (expanding playlists via
yt-dlp), skips IDs already in the folder, downloads the new ones through
the app's own ``DownloadManager`` (so the uploader caption and YTASR
caption are fetched exactly as the live app would), then hands the new
songs to ``regen_alignment_bundles``'s run path: caption fetch with the
words-per-minute gate, the Genius prompt, and the pipeline.

The tool never writes the app's library database -- the app picks up the
new files on its next library sync (startup, or the admin "sync library"
action).

Run from the repo root::

    python scripts/add_songs.py URL [URL ...] [--folder PATH] [--dry-run] [--yes]
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Allow running as ``python scripts/add_songs.py`` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pikaraoke.lib.download_manager import DownloadManager  # noqa: E402
from pikaraoke.lib.events import EventSystem  # noqa: E402
from pikaraoke.lib.get_platform import (  # noqa: E402
    get_default_dl_dir,
    get_platform,
    get_temp_directory,
)
from pikaraoke.lib.karaoke_database import KaraokeDatabase  # noqa: E402
from pikaraoke.lib.metadata_parser import extract_youtube_id  # noqa: E402
from pikaraoke.lib.preference_manager import PreferenceManager  # noqa: E402
from pikaraoke.lib.song_list import SongList  # noqa: E402
from pikaraoke.lib.song_manager import SongManager  # noqa: E402
from pikaraoke.lib.youtube_dl import _impersonate_args, yt_dlp_cmd  # noqa: E402
from scripts import regen_alignment_bundles as rab  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classify + expand + dedupe
# ---------------------------------------------------------------------------


@dataclass
class UrlEntry:
    id: str
    source: str
    status: str  # "new" | "already in library" | "in library, not processed"


# A link to one video downloads only that video, even when it carries
# list= (a search-result click or a Mix can attach one to a plain video
# link); the playlist page link (playlist?list=) is what gets the whole list.
_YOUTUBE_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")


def classify_url(url: str) -> tuple[str, str] | None:
    """Classify ``url`` as ``("video", id)`` or ``("playlist", url)``.

    Checks the host first (``youtu.be``, or ``youtube.com`` / any of its
    subdomains, case insensitive) -- any other host is unrecognised. A
    ``youtu.be`` link's id is its first path segment; any other host's is its
    ``v`` query parameter. An id matching the YouTube id shape is a video,
    even when the link also carries ``list=``. Otherwise a ``list`` query
    parameter makes it a playlist, passed through unchanged. Returns ``None``
    for anything else (including shorts and embed links -- nobody asked for
    those).
    """
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    if host != "youtu.be" and host != "youtube.com" and not host.endswith(".youtube.com"):
        return None

    query = parse_qs(parsed.query)
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/", 1)[0]
    else:
        video_id = query.get("v", [None])[0]
    if video_id and _YOUTUBE_ID_RE.fullmatch(video_id):
        return ("video", video_id)
    if "list" in query:
        return ("playlist", url)
    return None


def expand_playlist(url: str) -> list[str]:
    """Return every video id in a YouTube playlist, via yt-dlp --flat-playlist.

    Modelled on ``youtube_dl.get_search_results``. May raise
    ``subprocess.CalledProcessError`` or ``subprocess.TimeoutExpired``.
    """
    cmd = yt_dlp_cmd + ["--flat-playlist", "--print", "id"] + _impersonate_args() + [url]
    output = subprocess.check_output(cmd, timeout=300).decode("utf-8", "ignore")
    return [line.strip() for line in output.splitlines() if line.strip()]


def library_files(folder: Path) -> dict[str, Path]:
    """Map each YouTube id in ``folder`` to its song file.

    Counts every file type the app recognises (an ``.mp3`` or ``.zip`` with an
    id is in the library too). When a video and another file share an id, the
    video wins -- it is the one regen can process.
    """
    files = sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SongList.VALID_EXTENSIONS
    )
    files.sort(key=lambda p: p.suffix.lower() in rab.VIDEO_EXTS)  # videos last, so they win
    library: dict[str, Path] = {}
    for path in files:
        video_id = extract_youtube_id(str(path))
        if video_id:
            library[video_id] = path
    return library


def _library_status(path: Path) -> str:
    """Status for an id that already has a file in the library.

    A video with neither an alignment bundle nor a karaoke file is a song an
    earlier run downloaded but never processed. The pipeline writes a bundle
    only when the song had lyrics, so a transcribed song has the karaoke file
    alone and counts as processed too. Anything else is done, or isn't a video.
    """
    outputs = (
        path.parent / "alignment_debug" / f"{path.stem}.json",
        path.parent / "karaoke" / f"{path.stem}.ass",
    )
    if path.suffix.lower() in rab.VIDEO_EXTS and not any(p.is_file() for p in outputs):
        return "in library, not processed"
    return "already in library"


def resolve_urls(urls: list[str], library: dict[str, Path]) -> tuple[list[UrlEntry], int]:
    """Classify and expand ``urls`` into deduped entries, in first-seen order.

    ``library`` is :func:`library_files` of the target folder. Prints one line
    and continues for a URL that can't be classified, or a playlist whose
    expansion fails or times out. Returns the entries and how many URLs could
    not be read at all -- not a per-video count, since one bad playlist link
    can account for many missing songs.
    """
    seen: set[str] = set()
    entries: list[UrlEntry] = []
    unreadable = 0
    for url in urls:
        classified = classify_url(url)
        if classified is None:
            print(f"  unrecognised: {url}")
            unreadable += 1
            continue
        kind, value = classified
        if kind == "video":
            ids = [value]
        else:
            try:
                ids = expand_playlist(value)
            except subprocess.CalledProcessError as e:
                print(f"  failed to expand playlist: {value} ({e})")
                unreadable += 1
                continue
            except subprocess.TimeoutExpired:
                print(f"  timed out expanding playlist: {value}")
                unreadable += 1
                continue
        for vid in ids:
            if vid in seen:
                continue
            seen.add(vid)
            status = _library_status(library[vid]) if vid in library else "new"
            entries.append(UrlEntry(id=vid, source=url, status=status))
    return entries, unreadable


def print_report(entries: list[UrlEntry]) -> None:
    print(f"\nSongs found: {len(entries)}\n")
    if not entries:
        return
    id_width = max(len(e.id) for e in entries)
    source_width = max(len(e.source) for e in entries)
    status_width = max(len("status"), *(len(e.status) for e in entries))
    print(f"{'id':<{id_width}}  {'source':<{source_width}}  status")
    print(f"{'-' * id_width}  {'-' * source_width}  {'-' * status_width}")
    for e in entries:
        print(f"{e.id:<{id_width}}  {e.source:<{source_width}}  {e.status}")
    print()


# ---------------------------------------------------------------------------
# Hand off to regen's run path
# ---------------------------------------------------------------------------


def handoff(song_paths: list[str]) -> int:
    """Build a no-bundle job per song and hand them to regen's run path.

    Every job starts with ``bundle=None`` (a fresh download, or a video a
    stopped run left unprocessed, has no prior bundle to reuse), which gives
    it a ``fetch`` plan -- it always has a YouTube id. A caption the download
    already saved is gated in place (:func:`rab.adopt_caption`) instead of
    being fetched again. Returns regen's own exit code.
    """
    jobs = [rab.SongJob(Path(p), None, "new") for p in song_paths]
    for job in jobs:
        job.plan = rab.resolve_plan(job, reset=False)
        caption = rab._find_local_srt(job.song_path)
        if caption is not None:
            rab.adopt_caption(job, caption)
    return rab.resolve_and_run(jobs)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    default_folder = os.path.expanduser(get_default_dl_dir(get_platform()))
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Downloads run unattended, then any Genius prompts come in one "
            "batch, then the pipeline runs unattended -- be at the keyboard "
            "for the prompts, not the downloads or the pipeline run. Run "
            "while the app is idle: two GPU pipelines at once is much "
            "slower (not enforced here)."
        ),
    )
    p.add_argument(
        "urls",
        nargs="+",
        metavar="URL",
        help="YouTube video or playlist URL(s). A link to one video "
        "downloads only that video, even when it carries list=; paste the "
        "playlist page link (playlist?list=) to get the whole list.",
    )
    p.add_argument(
        "--folder",
        default=default_folder,
        help=f"Library folder to download into (default: {default_folder})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report and exit without downloading or running.",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the post-report confirmation prompt.",
    )
    return p.parse_args()


def main() -> int:
    rab.setup_process()

    args = parse_args()
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"Folder not found: {folder}", file=sys.stderr)
        return 2

    library = library_files(folder)

    entries, unreadable = resolve_urls(args.urls, library)
    print_report(entries)
    to_download = [e for e in entries if e.status == "new"]
    unprocessed = [library[e.id] for e in entries if e.status == "in library, not processed"]

    if args.dry_run:
        return 0 if unreadable == 0 else 1
    if not to_download and not unprocessed:
        print("Nothing new to download.")
        if unreadable:
            print(f"{unreadable} link(s) could not be read.")
        return 0 if unreadable == 0 else 1

    if not args.yes:
        reply = (
            input(
                f"Proceed with {len(to_download)} download(s) and "
                f"{len(unprocessed)} unprocessed song(s)? [y/N] "
            )
            .strip()
            .lower()
        )
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 0

    events = EventSystem()
    preferences = PreferenceManager()
    song_manager = SongManager(str(folder), db=KaraokeDatabase(":memory:"))
    dm = DownloadManager(
        events=events,
        preferences=preferences,
        song_manager=song_manager,
        queue_manager=None,  # only consulted when enqueue=True, which we never pass
        download_path=str(folder),
        temp_dir=get_temp_directory(),
    )
    new_songs: list[str] = []
    events.on("song_downloaded", new_songs.append)

    downloaded = failed = 0
    for entry in to_download:
        watch_url = f"https://www.youtube.com/watch?v={entry.id}"
        print(f"\nDownloading {entry.id} ({entry.source})...")
        before = len(new_songs)
        try:
            rc = dm._execute_download(watch_url, False, "add_songs", None)
        except Exception:  # the app's own per-download boundary; Ctrl+C still stops the tool
            logger.exception("Download failed: %s", entry.id)
            rc = 1
        if rc != 0:
            failed += 1
            print(f"  FAILED: {entry.id}")
            continue
        if len(new_songs) == before:
            failed += 1
            print(
                f"  FAILED: {entry.id} (yt-dlp finished but no file with that id is in the folder)"
            )
            continue
        downloaded += 1

    pipeline_rc = 0
    to_process = new_songs + [str(p) for p in unprocessed]
    if to_process:
        pipeline_rc = handoff(to_process)

    print(f"\nDownloaded: {downloaded} Failed: {failed}")
    if downloaded:
        print(
            "In the app, run sync library from the admin page (or restart "
            "it) to see the new songs."
        )
    return 0 if (unreadable == 0 and failed == 0 and pipeline_rc == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
