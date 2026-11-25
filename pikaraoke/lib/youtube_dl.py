from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pikaraoke.lib import ytasr
from pikaraoke.lib.get_platform import get_installed_js_runtime

yt_dlp_cmd = [sys.executable, "-m", "yt_dlp"]

# Browser to impersonate via curl_cffi TLS fingerprint spoofing.
# This makes yt-dlp's HTTP requests indistinguishable from a real Chrome browser,
# bypassing YouTube's primary bot-detection vector (TLS/JA3 fingerprinting).
_IMPERSONATE_TARGET = "chrome"

# The video download and every caption fetch share these, so a fetched caption is what a
# download would save.
_MANUAL_EN_SUB_ARGS = ["--write-subs", "--sub-langs", "en.*", "--convert-subs", "srt"]


def _js_runtime_args() -> list[str]:
    """Return yt-dlp args to select the preferred JS runtime, if any."""
    runtime = get_installed_js_runtime()
    if runtime and runtime != "deno":
        # Deno is automatically assumed by yt-dlp, and does not need specification here
        return ["--js-runtimes", runtime]
    return []


def _impersonate_args() -> list[str]:
    """Return yt-dlp args for browser impersonation via curl_cffi.

    Returns --impersonate flag only if curl_cffi is installed AND yt-dlp can
    actually load it. yt-dlp pins a specific curl_cffi version range; an
    incompatible version makes every --impersonate target unavailable, so we
    suppress the flag and warn instead of producing a runtime error.
    """
    try:
        import curl_cffi  # noqa: F401 — presence check only
    except ImportError:
        logging.debug("curl_cffi not installed; skipping --impersonate")
        return []

    try:
        import yt_dlp.networking._curlcffi  # noqa: F401 — version-compat check
    except ImportError as e:
        installed = getattr(curl_cffi, "__version__", "unknown")
        logging.warning(
            f"curl_cffi {installed} is incompatible with the installed yt-dlp "
            f"({e}); skipping --impersonate. Pin curl_cffi to a supported range."
        )
        return []

    return ["--impersonate", _IMPERSONATE_TARGET]


def get_youtubedl_version() -> str:
    """Get the installed yt-dlp version.

    Returns:
        Version string of the installed yt-dlp or an error message.
    """
    try:
        cmd = yt_dlp_cmd + ["--version"]
        return subprocess.check_output(cmd).strip().decode("utf8")
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as e:
        logging.warning(f"Could not get yt-dlp version: {e}")
        return "Not found"
    except Exception as e:
        logging.error(f"Unexpected error getting yt-dlp version: {e}")
        return "Error"


_URL_VIDEO_ID_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/v/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])")


def get_youtube_id_from_url(url: str) -> str | None:
    """The 11-character video ID in a YouTube link, or None when it carries none.

    Reads the forms the search page accepts (``watch?v=``, ``youtu.be/``, ``/v/``); whatever
    follows the ID (``&list=``, ``?t=``, ``#t=``) is not part of it. Callers compare the ID
    with a library file's, so a link without one is an answer, not an error.
    """
    match = _URL_VIDEO_ID_RE.search(url)
    return match.group(1) if match else None


def upgrade_youtubedl() -> str:
    """Upgrade yt-dlp to the latest version.

    Attempts self-upgrade first, then falls back to pip if needed.

    Returns:
        The new version string after upgrade.
    """
    try:
        output = (
            subprocess.check_output(yt_dlp_cmd + ["-U"], stderr=subprocess.STDOUT)
            .decode("utf8")
            .strip()
        )
    except subprocess.CalledProcessError as e:
        output = e.output.decode("utf8")
    except (FileNotFoundError, PermissionError) as e:
        logging.warning(f"Could not run yt-dlp for upgrade: {e}")
        return get_youtubedl_version()

    # Check if already up to date
    if "is up to date" in output.lower():
        logging.debug("yt-dlp is already up to date")
        return get_youtubedl_version()

    upgrade_success = False
    if "pip" in output.lower():
        # [default] carries yt-dlp-ejs (YouTube's JS challenge solver), which each
        # yt-dlp release pins to an exact version; upgrading bare yt-dlp leaves it stale.
        pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]"]

        # Outside a venv, pip requires --break-system-packages on modern Python
        if sys.prefix == sys.base_prefix:
            pip_cmd.append("--break-system-packages")

        try:
            logging.info(f"yt-dlp is outdated! Attempting upgrade via {pip_cmd}...")
            subprocess.check_output(pip_cmd, stderr=subprocess.STDOUT)
            upgrade_success = True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error(f"Failed to upgrade yt-dlp using pip: {e}")

    youtubedl_version = get_youtubedl_version()
    if upgrade_success:
        logging.info(f"Done. Installed version: {youtubedl_version}")
    else:
        logging.error("Failed to upgrade yt-dlp.")
    return youtubedl_version


def build_ytdl_download_command(
    video_url: str,
    download_path: str,
    high_quality: bool = False,
    youtubedl_proxy: str | None = None,
    additional_args: str | None = None,
    temp_dir: str = "",
) -> list[str]:
    """Build the yt-dlp command line for downloading a video.

    Args:
        video_url: URL of the video to download.
        download_path: Directory path where videos will be saved.
        high_quality: If True, download up to 1080p; otherwise download mp4.
        youtubedl_proxy: Optional proxy server URL.
        additional_args: Optional additional command-line arguments as a string.
        temp_dir: Optional directory for yt-dlp temporary files.

    Returns:
        List of command-line arguments for subprocess execution.
    """
    file_quality = (
        "bestvideo[ext!=webm][height<=1080]+bestaudio[ext!=webm]/best[ext!=webm]"
        if high_quality
        else "bestvideo[ext!=webm][height<=720]+bestaudio[ext!=webm]/best[ext!=webm]"
    )
    args = [
        "-f",
        file_quality,
        # Use --paths home: + filename-only -o so that --paths temp: is respected
        # for .part files and merge intermediates. A full path in -o overrides temp:.
        "--paths",
        f"home:{download_path}",
        "-o",
        "%(title)s---%(id)s.%(ext)s",
        "-S",
        "vcodec:h264",
        "--compat-options",
        "filename-sanitization",
        *_MANUAL_EN_SUB_ARGS,
    ]
    cmd = yt_dlp_cmd + args + _js_runtime_args() + _impersonate_args()
    if youtubedl_proxy:
        cmd += ["--proxy", youtubedl_proxy]
    if temp_dir:
        cmd += ["--paths", f"temp:{temp_dir}"]
    if additional_args:
        cmd += shlex.split(additional_args)
    cmd += [video_url]
    return cmd


@dataclass(frozen=True)
class SearchResult:
    """One YouTube search hit, as yt-dlp's flat search reports it."""

    title: str
    url: str
    id: str
    channel: str  # "" when YouTube gives none
    duration: str  # "M:SS", or "" when YouTube gives none
    channel_verified: bool
    description: str  # YouTube's snippet; art tracks start "Provided to YouTube by"


def _parse_search_line(line: str) -> SearchResult | None:
    """Parse one yt-dlp JSON line; None for a blank line or a row without a title, URL or ID."""
    if len(line) <= 2:
        return None
    j = json.loads(line)
    if not (j.get("title") and j.get("url") and j.get("id")):
        return None
    duration_raw = j.get("duration")
    duration = ""
    if isinstance(duration_raw, (int, float)):
        seconds = int(duration_raw)
        duration = f"{seconds // 60}:{seconds % 60:02d}"
    return SearchResult(
        title=j["title"],
        url=j["url"],
        id=j["id"],
        channel=j.get("channel") or j.get("uploader") or "",
        duration=duration,
        channel_verified=bool(j.get("channel_is_verified")),
        description=j.get("description") or "",
    )


def get_search_results(query: str, count: int) -> list[SearchResult]:
    """Search YouTube for the first ``count`` videos matching the query.

    Raises:
        subprocess.CalledProcessError: yt-dlp failed.
    """
    logging.info(f"Searching YouTube for: {query}")
    yt_search = f"ytsearch{count}:{query}"
    cmd = yt_dlp_cmd + ["-j", "--no-playlist", "--flat-playlist"] + _impersonate_args()
    cmd += [yt_search]
    logging.debug(f"yt-dlp search command: {' '.join(cmd)}")
    try:
        output = subprocess.check_output(cmd).decode("utf-8", "ignore")
        logging.debug(f"Search results: {output}")
        parsed = (_parse_search_line(line) for line in output.split("\n"))
        return [result for result in parsed if result is not None]
    except subprocess.CalledProcessError as e:
        logging.debug(f"Error while executing search: {e}")
        raise


def _select_en_srt(dest_dir: str, stem: str) -> str | None:
    """Pick the canonical ``<stem>.en.srt`` from yt-dlp's subtitle output.

    yt-dlp may write several English variants (``en``, ``en-US``, ...). Prefer an
    exact ``<stem>.en.srt``; otherwise promote the first variant to that name and
    drop the rest, so callers and later runs find one predictable file. A pre-
    existing language-less ``<stem>.srt`` (e.g. a pipeline-generated transcript)
    is never matched. Returns the path, or ``None`` when no English SRT exists.
    """
    prefix = f"{stem}."
    variants = []
    for entry in Path(dest_dir).iterdir():
        if not entry.is_file() or not entry.name.startswith(prefix):
            continue
        lang_ext = entry.name[len(prefix) :]  # e.g. "en.srt", "en-US.srt"
        if lang_ext.endswith(".srt") and len(lang_ext) > len(".srt"):
            variants.append(entry)
    if not variants:
        return None
    variants.sort()
    canonical = Path(dest_dir) / f"{stem}.en.srt"
    chosen = canonical if canonical in variants else variants[0]
    if chosen != canonical:
        chosen.replace(canonical)
    for extra in variants:
        if extra != chosen and extra != canonical:
            extra.unlink(missing_ok=True)
    return str(canonical)


class CaptionDownloadFailed(Exception):
    """yt-dlp couldn't answer whether the video has a caption (timeout, not runnable, error).

    ``stdout`` is what yt-dlp printed before an error exit or a timeout. From
    :func:`lookup_video`, ``stream_url`` is the preview link found in it, since yt-dlp prints
    the link before it fetches the caption.
    """

    def __init__(self, message: str, stdout: bytes = b"") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stream_url: str | None = None


def _run_caption_command(
    what: str, video_url: str, dest_dir: str, stem: str, extra_args: list[str], timeout: float
) -> bytes:
    """Run yt-dlp for the video's manual English caption into ``<dest_dir>/<stem>.*``.

    ``what`` names the run in the log and in errors. Returns yt-dlp's stdout. Raises
    :class:`CaptionDownloadFailed` when yt-dlp timed out, couldn't be run or exited with an
    error. No media is downloaded.
    """
    os.makedirs(dest_dir, exist_ok=True)
    cmd = (
        yt_dlp_cmd
        + [
            "--skip-download",
            *extra_args,
            *_MANUAL_EN_SUB_ARGS,
            "-o",
            os.path.join(dest_dir, f"{stem}.%(ext)s"),
        ]
        + _js_runtime_args()
        + _impersonate_args()
        + [video_url]
    )
    logging.debug(f"yt-dlp {what} command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # The kill keeps what yt-dlp printed (it flushes each line), as an error exit does.
        raise CaptionDownloadFailed(
            f"yt-dlp {what} timed out for: {video_url}", stdout=e.stdout or b""
        ) from e
    except (FileNotFoundError, PermissionError) as e:
        raise CaptionDownloadFailed(f"Could not run yt-dlp: {e}") from e
    if result.returncode != 0:
        raise CaptionDownloadFailed(
            f"yt-dlp {what} failed for {video_url}: "
            f"{result.stderr.decode('utf-8', 'ignore').strip()}",
            stdout=result.stdout,
        )
    return result.stdout


def download_manual_en_subs(video_url: str, dest_dir: str, stem: str) -> str | None:
    """Download YouTube's *manual* English caption as ``<dest_dir>/<stem>.en.srt``.

    Returns the SRT path when a manual English caption exists and was written;
    returns ``None`` when yt-dlp ran and found no such caption. Raises
    :class:`CaptionDownloadFailed` when yt-dlp timed out, couldn't be run or
    exited with an error, so a caller can tell "no caption" from "couldn't
    ask". Auto-generated (ASR) captions are never fetched and no media is
    downloaded.
    """
    _run_caption_command("subtitle download", video_url, dest_dir, stem, [], 60)
    return _select_en_srt(dest_dir, stem)


@dataclass(frozen=True)
class VideoLookup:
    """What one :func:`lookup_video` call learned about a video."""

    srt_path: str | None  # the manual English caption, None when the video has none
    duration_s: float | None  # YouTube's length, None when it gives none (a live stream)
    stream_url: str | None  # a link a browser plays unaided, None when no format matched


def lookup_video(video_url: str, dest_dir: str, stem: str) -> VideoLookup:
    """One yt-dlp call for the search dialog: the caption, the length and a playable link.

    Writes the caption as :func:`download_manual_en_subs` does. ``--no-simulate`` is there
    because ``--print`` alone implies a simulation, which writes no caption;
    ``--ignore-no-formats-error`` lets a video with no playable format still answer its
    caption, with no link. Raises :class:`CaptionDownloadFailed` as
    :func:`download_manual_en_subs` does, carrying the link when yt-dlp printed one before
    the caption failed (an HTTP 429, say) or stalled past the time limit, so the preview
    survives.
    """
    lookup_args = [
        "--no-simulate",
        "-f",
        "18/worst[ext=mp4][protocol*=http]/worst[protocol*=http]",
        "--ignore-no-formats-error",
        "--print",
        "url",
        "--print",
        "duration",
        # The browser fetches this URL itself, so the client must hand out
        # format-18 links that play without yt-dlp's headers or a PO token.
        # tv_simply does (2026.10); the default client's tv links 403 at
        # random and mweb's almost always do. default stays as a fallback.
        "--extractor-args",
        "youtube:player_client=tv_simply,default",
    ]
    try:
        # one lookup measures 4-6 s; 30 outlasts a slow day, and a guest waits no minute
        stdout = _run_caption_command("lookup", video_url, dest_dir, stem, lookup_args, 30)
    except CaptionDownloadFailed as e:
        e.stream_url, _ = _parse_lookup_print(e.stdout)
        raise
    stream_url, duration_s = _parse_lookup_print(stdout)
    return VideoLookup(
        srt_path=_select_en_srt(dest_dir, stem), duration_s=duration_s, stream_url=stream_url
    )


def _parse_lookup_print(stdout: bytes) -> tuple[str | None, float | None]:
    """The link and the length :func:`lookup_video` has yt-dlp print, each None when absent."""
    lines = [line.strip() for line in stdout.decode("utf-8", "ignore").splitlines() if line.strip()]
    stream_url = lines[0] if lines and lines[0].startswith("http") else None  # "NA": no format
    duration_s = None
    if len(lines) > 1:
        try:
            duration_s = float(lines[1])
        except ValueError:  # "NA" for a live stream
            pass
    return stream_url, duration_s


# Canonical name for the selected real-ASR track. The ``.en.asr.json3`` suffix
# is distinct from ``.en.srt`` / ``.srt`` so SRT discovery never mistakes it for
# a manual caption.
ASR_JSON3_SUFFIX = ".en.asr.json3"


def _select_asr_track(dest_dir: str, stem: str) -> str | None:
    """Pick the real word-level ASR track from yt-dlp's json3 output.

    yt-dlp writes one ``<stem>.<lang>.json3`` per English auto-caption track
    (``en``, ``en-orig``, ...). Only genuine ASR is word-level; a track may be
    the uploader's manual caption mirrored back (line-level, no per-word timing).
    Select by *content*, not name: the track with the highest word-seg fraction
    (the real-ASR discriminator) is promoted to the canonical
    ``<stem>.en.asr.json3`` and the rest dropped. Returns the canonical path, or
    ``None`` (after dropping every track) when none clears
    :data:`ytasr.WORD_SEG_MIN_FRAC`.
    """
    prefix = f"{stem}."
    canonical = Path(dest_dir) / f"{stem}{ASR_JSON3_SUFFIX}"
    candidates = []
    for entry in Path(dest_dir).iterdir():
        if not entry.is_file() or entry == canonical or not entry.name.startswith(prefix):
            continue
        lang_ext = entry.name[len(prefix) :]  # e.g. "en.json3", "en-orig.json3"
        if lang_ext.endswith(".json3") and len(lang_ext) > len(".json3"):
            candidates.append(entry)

    best: Path | None = None
    best_frac = -1.0
    for entry in candidates:
        try:
            _, frac = ytasr.parse_json3(entry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logging.warning(f"Could not parse ASR track {entry.name}: {e}")
            continue
        if frac > best_frac:
            best_frac, best = frac, entry

    if best is None or best_frac < ytasr.WORD_SEG_MIN_FRAC:
        for entry in candidates:
            entry.unlink(missing_ok=True)
        return None
    if best != canonical:
        best.replace(canonical)
    for entry in candidates:
        if entry != best:
            entry.unlink(missing_ok=True)
    return str(canonical)


def download_auto_en_subs(video_url: str, dest_dir: str, stem: str) -> str | None:
    """Download YouTube's *auto-generated* (ASR) English caption as json3.

    Fetches the ``en`` and ``en-orig`` auto-caption tracks in word-level ``json3``
    and selects the real ASR track by content (:func:`_select_asr_track`),
    written as ``<dest_dir>/<stem>.en.asr.json3``. Returns that path, or ``None``
    when no real word-level ASR arrived. The ``en-<src>`` tracks are not
    requested: they are machine translations of other captions, not the ASR, and
    YouTube answers them with HTTP 429, which aborts the run. A failed run still
    keeps any track that arrived before the failure. No media and no manual
    captions are fetched; json3 is kept un-converted because ``--convert-subs
    srt`` collapses the per-word timing this prior depends on.
    """
    os.makedirs(dest_dir, exist_ok=True)
    cmd = (
        yt_dlp_cmd
        + [
            "--skip-download",
            "--write-auto-subs",
            "--sub-langs",
            "en,en-orig",
            "--sub-format",
            "json3",
            "-o",
            os.path.join(dest_dir, f"{stem}.%(ext)s"),
        ]
        + _js_runtime_args()
        + _impersonate_args()
        + [video_url]
    )
    logging.debug(f"yt-dlp auto-sub download command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        logging.warning(f"yt-dlp auto-sub download timed out for: {video_url}")
        return None
    except (FileNotFoundError, PermissionError) as e:
        logging.error(f"Could not run yt-dlp: {e}")
        return None
    if result.returncode != 0:
        logging.warning(
            f"yt-dlp auto-sub download failed for {video_url}: "
            f"{result.stderr.decode('utf-8', 'ignore').strip()}"
        )
    return _select_asr_track(dest_dir, stem)
