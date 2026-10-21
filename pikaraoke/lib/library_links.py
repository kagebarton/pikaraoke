"""YouTube link handling shared by the add_songs CLI and the web UI.

Classifies a link as a video or a playlist, expands a playlist, and compares
the result with the files already in the library.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pikaraoke.lib.library_regen import VIDEO_EXTS, bundle_path
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.lib.song_list import SongList
from pikaraoke.lib.youtube_dl import _impersonate_args, yt_dlp_cmd

_YOUTUBE_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")


def classify_url(url: str) -> tuple[str, str] | None:
    """Classify ``url`` as ``("video", id)`` or ``("playlist", url)``.

    Checks the host first (``youtu.be``, or ``youtube.com`` / any of its
    subdomains, case insensitive) -- any other host is unrecognised. A
    ``youtu.be`` link's id is its first path segment; any other host's is its
    ``v`` query parameter. An id matching the YouTube id shape is a video,
    even when the link also carries ``list=`` (a search result or a Mix
    attaches one to a plain video link; the playlist page link,
    ``playlist?list=``, is what gets the whole list). Otherwise a ``list``
    query parameter makes it a playlist, passed through unchanged. Returns
    ``None`` for anything else (including shorts and embed links -- nobody
    asked for those).
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


@dataclass(frozen=True)
class PlaylistVideo:
    id: str
    title: str


@dataclass(frozen=True)
class Playlist:
    title: str
    videos: list[PlaylistVideo]


def read_playlist(url: str) -> Playlist:
    """Read a YouTube playlist's title and videos, via yt-dlp --flat-playlist -J.

    Modelled on ``youtube_dl.get_search_results``. May raise
    ``subprocess.CalledProcessError``, ``subprocess.TimeoutExpired`` or
    ``ValueError`` (yt-dlp's output was not JSON).
    """
    # "--" so that a link that looks like an option (classify_url accepts a
    # scheme-less link such as "--exec=x.youtube.com?list=1") stays a URL.
    cmd = yt_dlp_cmd + ["--flat-playlist", "-J"] + _impersonate_args() + ["--", url]
    output = subprocess.check_output(cmd, timeout=300).decode("utf-8", "ignore")
    info = json.loads(output)
    videos = [
        PlaylistVideo(id=entry["id"], title=entry.get("title") or entry["id"])
        for entry in info.get("entries") or []
        if entry and entry.get("id")
    ]
    return Playlist(title=info.get("title") or "", videos=videos)


def expand_playlist(url: str) -> list[str]:
    """Return every video id in a YouTube playlist."""
    return [video.id for video in read_playlist(url).videos]


def library_files(folder: Path) -> dict[str, Path]:
    """Map each YouTube id in ``folder`` to its song file.

    Counts every file type the app recognises (an ``.mp3`` or ``.zip`` with an
    id is in the library too). When a video and another file share an id, the
    video wins -- it is the one regen can process.
    """
    files = sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in SongList.VALID_EXTENSIONS
        ),
        key=lambda p: (p.suffix.lower() in VIDEO_EXTS, p),  # videos last, so they win
    )
    library: dict[str, Path] = {}
    for path in files:
        video_id = extract_youtube_id(str(path))
        if video_id:
            library[video_id] = path
    return library


def file_status(path: Path) -> str:
    """Status for an id that already has a file in the library.

    A video with neither an alignment bundle nor a karaoke file is a song an
    earlier run downloaded but never processed. The pipeline writes a bundle
    only when the song had lyrics, so a transcribed song has the karaoke file
    alone and counts as processed too. Anything else is done, or isn't a video.
    """
    outputs = (
        bundle_path(path.parent, path.stem),
        path.parent / "karaoke" / f"{path.stem}.ass",
    )
    if path.suffix.lower() in VIDEO_EXTS and not any(p.is_file() for p in outputs):
        return "in library, not processed"
    return "already in library"
