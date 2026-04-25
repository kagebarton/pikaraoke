"""Download queue manager for serialized video downloads."""

from __future__ import annotations

import contextlib
import logging
import re
import subprocess
import uuid
from pathlib import Path
from queue import Queue
from threading import Thread

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.queue_manager import QueueManager
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.youtube_dl import (
    build_ytdl_download_command,
    get_youtube_id_from_url,
)


class DownloadManager:
    """Manages a queue of video downloads, processing them serially.

    This prevents rate limiting from download sources and reduces CPU load
    by ensuring only one download runs at a time.

    Attributes:
        download_queue: Queue holding pending download requests.
    """

    def __init__(
        self,
        events: EventSystem,
        preferences: PreferenceManager,
        song_manager: SongManager,
        queue_manager: QueueManager,
        download_path: str,
        youtubedl_proxy: str | None = None,
        additional_ytdl_args: str | None = None,
        temp_dir: str = "",
    ) -> None:
        """Initialize the download manager.

        Args:
            events: Event system for notifications and broadcasts.
            preferences: Configuration manager for persistent settings.
            song_manager: Manager for song library operations.
            queue_manager: Manager for playback queue.
            download_path: Directory where downloads are saved.
            youtubedl_proxy: Optional proxy URL for yt-dlp.
            additional_ytdl_args: Optional additional arguments for yt-dlp.
            temp_dir: Optional directory for yt-dlp temporary files.
        """
        self._events = events
        self._preferences = preferences
        self._song_manager = song_manager
        self._queue_manager = queue_manager
        self._download_path = download_path
        self._youtubedl_proxy = youtubedl_proxy
        self._additional_ytdl_args = additional_ytdl_args
        self._temp_dir = temp_dir
        self.download_queue: Queue = Queue()
        self.pending_downloads: list[dict] = []  # Shadow queue for visibility
        self.download_errors: list[dict] = []  # Track failed downloads
        self.active_download: dict | None = None
        self._active_process: subprocess.Popen | None = None  # Stored for cancellation
        self._cancelled_urls: set[str] = set()  # URLs cancelled while pending
        self._worker_thread: Thread | None = None
        self._is_downloading: bool = False  # Track if a download is currently in progress

    def start(self) -> None:
        """Start the download worker thread."""
        self._worker_thread = Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        logging.debug("Download queue worker started")

    def get_downloads_status(self) -> dict:
        """Get the status of active and pending downloads.

        Returns:
            Dict containing 'active' download info and list of 'pending' downloads.
        """
        return {
            "active": self.active_download,
            "pending": self.pending_downloads,
            "errors": self.download_errors,
        }

    def remove_error(self, error_id: str) -> bool:
        """Remove an error from the list by ID.

        Args:
            error_id: The ID of the error to remove.

        Returns:
            True if removed, False if not found.
        """
        initial_len = len(self.download_errors)
        self.download_errors = [e for e in self.download_errors if e["id"] != error_id]
        return len(self.download_errors) < initial_len

    def queue_download(
        self,
        video_url: str,
        enqueue: bool = False,
        user: str = "Pikaraoke",
        title: str | None = None,
    ) -> None:
        """Queue a video for download.

        Downloads are processed serially to prevent rate limiting and CPU overload.

        Args:
            video_url: YouTube video URL.
            enqueue: Whether to add to playback queue after download.
            user: Username to attribute the download to.
            title: Display title (defaults to URL if not provided).
        """
        from flask_babel import _

        # Strip playlist parameter to avoid downloading entire playlists
        if "&list=" in video_url:
            video_url = video_url.split("&list=")[0]

        displayed_title = title if title else video_url

        # Check how many items are ahead (in queue + currently downloading)
        pending_count = self.download_queue.qsize() + (1 if self._is_downloading else 0)

        if pending_count > 0:
            # MSG: Message shown when download is added to queue (not first in line)
            self._events.emit(
                "notification",
                _("Download queued (#%d): %s") % (pending_count + 1, displayed_title),
            )
        else:
            # MSG: Message shown when download is added and will start immediately
            self._events.emit("notification", _("Download starting: %s") % displayed_title)

        # If queue was just started (was not downloading before), emit event
        if not self._is_downloading and self.download_queue.empty():
            self._events.emit("download_started")

        download_data = {
            "video_url": video_url,
            "enqueue": enqueue,
            "user": user,
            "title": title,
            "display_title": displayed_title,
        }

        # Add to the download queue and shadow list
        self.download_queue.put(download_data)
        self.pending_downloads.append(download_data)

        # Emit download_queued event for pipeline tracker
        self._events.emit(
            "download_queued",
            {
                "video_url": video_url,
                "enqueue": enqueue,
                "user": user,
                "title": displayed_title,
            },
        )

    def _process_queue(self) -> None:
        """Worker thread that processes downloads from the queue serially.

        Runs indefinitely, blocking on queue.get() until items are available.
        Each download is processed completely before the next one starts.
        """
        while True:
            # Capture queue reference before get() — cancel_pending_download may
            # replace self.download_queue mid-download; task_done() must be called
            # on the same instance that get() was called on.
            q = self.download_queue
            download_request = q.get()

            # Skip if this URL was cancelled while pending
            video_url = download_request["video_url"]
            if video_url in self._cancelled_urls:
                self._cancelled_urls.discard(video_url)
                q.task_done()
                if self.download_queue.empty():
                    self._events.emit("download_stopped")
                continue

            # Remove from shadow queue
            # Note: Since this is a single worker thread and append happens on main thread,
            # we simply pop the first item as it corresponds to FIFO queue.
            # In a multi-worker scenario, this would need a lock.
            if self.pending_downloads:
                self.pending_downloads.pop(0)

            self._is_downloading = True

            # Initialize active download state
            self.active_download = {
                "title": download_request.get("display_title", download_request["video_url"]),
                "url": download_request["video_url"],
                "user": download_request["user"],
                "progress": 0.0,
                "status": "starting",
                "eta": "--:--",
                "speed": "---",
            }

            try:
                self._execute_download(
                    download_request["video_url"],
                    download_request["enqueue"],
                    download_request["user"],
                    download_request["title"],
                )
            except Exception as e:
                logging.error(f"Error processing download: {e}")
            finally:
                self._is_downloading = False
                self.active_download = None
                q.task_done()

                # Check if we are done with all downloads
                if self.download_queue.empty():
                    self._events.emit("download_stopped")

    def _execute_download(
        self,
        video_url: str,
        enqueue: bool,
        user: str,
        title: str | None,
    ) -> int:
        """Execute a video download.

        Args:
            video_url: YouTube video URL.
            enqueue: Whether to add to queue after download.
            user: Username to attribute the download to.
            title: Display title (defaults to URL if not provided).

        Returns:
            Return code from the download process (0 = success).
        """
        from flask_babel import _

        displayed_title = title if title else video_url

        # MSG: Message shown when download actually starts (after waiting in queue)
        self._events.emit("notification", _("Downloading video: %s") % displayed_title)

        cmd = build_ytdl_download_command(
            video_url,
            self._download_path,
            self._preferences.get_or_default("high_quality"),
            self._youtubedl_proxy,
            self._additional_ytdl_args,
            self._temp_dir,
        )
        logging.debug("Youtube-dl command: " + " ".join(cmd))

        # Use Popen to capture output in real-time
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,
        )
        self._active_process = process

        output_buffer = []

        # Regex to parse progress from yt-dlp stdout
        # Example: [download]   0.0% of    4.62MiB at  396.66KiB/s ETA 00:12
        progress_regex = re.compile(
            r"\[download\]\s+(\d+\.?\d*)%\s+of\s+.*?\s+at\s+([^\s]+)\s+ETA\s+([^\s]+)"
        )
        video_id = get_youtube_id_from_url(video_url)

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_buffer.append(line)
                match = progress_regex.search(line)
                if match and self.active_download:
                    percent = float(match.group(1))
                    speed = match.group(2)
                    eta = match.group(3)

                    self.active_download["progress"] = percent
                    self.active_download["status"] = "downloading"
                    self.active_download["speed"] = speed
                    self.active_download["eta"] = eta
                # Log only non-progress lines to avoid spamming logs, or log everything at debug
                # logging.debug(line.strip())

        rc = process.poll()
        output = "".join(output_buffer)
        self._active_process = None

        if rc != 0:
            # Logic removed: We no longer retry synchronously as it blocks the queue.
            # Failed downloads are now failed fast and logged.

            # MSG: Message shown after the download process is completed but the song is not found
            self._events.emit(
                "notification", _("Error downloading song: ") + displayed_title, "danger"
            )
            logging.error(f"yt-dlp stderr: {output}")
            error_data = {
                "id": str(uuid.uuid4()),
                "title": displayed_title,
                "url": video_url,
                "user": user,
                "error": output or "Unknown error",
            }
            self.download_errors.append(error_data)
            # Emit download_error event for pipeline tracker
            self._events.emit("download_error", error_data)
        else:
            if self.active_download:
                self.active_download["progress"] = 100
                self.active_download["status"] = "complete"

            if enqueue:
                # MSG: Message shown after the download is completed and queued
                self._events.emit(
                    "notification", _("Downloaded and queued: %s") % displayed_title, "success"
                )
            else:
                # MSG: Message shown after the download is completed but not queued
                self._events.emit("notification", _("Downloaded: %s") % displayed_title, "success")

            # After download, find the file path by ID
            song_path = None
            if video_id:
                logging.debug(f"Searching for downloaded file by ID: {video_id}")
                song_path = self._song_manager.songs.find_by_id(self._download_path, video_id)
            else:
                logging.warning("No video ID available to find downloaded song")

            if song_path:
                self._events.emit("song_downloaded", song_path)
                # Rename subtitle file to remove language code
                self._move_downloaded_subtitle(song_path)
            else:
                logging.warning(
                    f"Could not find downloaded song in {self._download_path} matching ID: {video_id}"
                )

            if enqueue:
                if song_path:
                    self._queue_manager.enqueue(song_path, user, log_action=False)
                else:
                    # MSG: Message shown after the download is completed but the adding to queue fails
                    self._events.emit(
                        "notification", _("Error queueing song: ") + displayed_title, "danger"
                    )

        return rc

    def cancel_active_download(self, target_url: str | None = None) -> None:
        """Cancel the currently active download and clean up partial files.

        Args:
            target_url: The URL the caller believes is currently downloading.
                If provided and it does not match ``self.active_download['url']``,
                the call is a no-op (the active download has already moved on
                to a different song and must not be killed).
        """
        active_url = self.active_download["url"] if self.active_download else None

        if target_url is not None and active_url != target_url:
            logging.warning(
                "cancel_active_download: target URL %r does not match active URL %r — "
                "skipping to avoid killing a different download",
                target_url,
                active_url,
            )
            return

        if active_url:
            logging.info("Cancelling active download: %s", active_url)
        else:
            logging.info("cancel_active_download called but no download is active")

        if self._active_process is not None:
            try:
                self._active_process.kill()
            except ProcessLookupError:
                pass
            self._active_process = None

        # Clean up partial downloads matching the active video ID
        if self.active_download:
            video_id = get_youtube_id_from_url(self.active_download["url"])
            if video_id:
                self._cleanup_partial_downloads(video_id)

        self._is_downloading = False
        self.active_download = None

    def cancel_pending_download(self, video_url: str) -> None:
        """Cancel a download that is still in the pending queue."""
        self._cancelled_urls.add(video_url)
        # Remove from shadow queue
        self.pending_downloads = [d for d in self.pending_downloads if d["video_url"] != video_url]
        # Also drain from the Queue (there's no public remove, so we rebuild)
        new_queue: Queue = Queue()
        skipped = False
        while not self.download_queue.empty():
            item = self.download_queue.get_nowait()
            if item["video_url"] == video_url and not skipped:
                skipped = True
                self.download_queue.task_done()
            else:
                new_queue.put(item)
        self.download_queue = new_queue

    def _cleanup_partial_downloads(self, video_id: str) -> None:
        """Remove partial download files matching a video ID."""
        from pathlib import Path

        download_dir = Path(self._download_path)
        # Match both filename conventions: Title---VIDEOID.mp4 and Title [VIDEOID].mp4.
        # The triple-dash pattern is checked first for specificity; the bare ID pattern
        # catches the bracketed format (and anything else) without using glob character
        # classes, which would misinterpret [VIDEOID] as a character set and match everything.
        for pattern in [f"*---{video_id}*", f"*{video_id}*"]:
            for f in download_dir.glob(pattern):
                if f.is_file():
                    try:
                        f.unlink()
                        logging.debug(f"Cleaned up partial download: {f}")
                    except OSError as e:
                        logging.warning(f"Failed to clean partial download {f}: {e}")

    def _move_downloaded_subtitle(self, video_path: str) -> None:
        video = Path(video_path)
        subtitles_dir = video.parent / "subtitles"
        subtitles_dir.mkdir(exist_ok=True)
        target = subtitles_dir / f"{video.stem}.srt"

        # All subtitle candidates in the song folder: Song---abc123.en.srt, .vtt, .srv3, etc.
        candidates = {
            f
            for ext in (".srt", ".vtt", ".srv3", ".ttml")
            for f in video.parent.glob(f"{video.stem}*{ext}")
        }

        srt_files = {f for f in candidates if f.suffix == ".srt"}
        if not srt_files:
            logging.debug(f"No subtitle found for video: {video_path}")
            return

        source = next(iter(srt_files))
        try:
            source.rename(target)
            logging.debug(f"Moved subtitle: {source.name} -> {target}")
        except OSError as e:
            logging.warning(f"Failed to move subtitle: {e}")
            return

        # Delete everything else (other langs, intermediate formats)
        for f in candidates - {source}:
            with contextlib.suppress(OSError):
                f.unlink()
                logging.debug(f"Removed extra subtitle: {f.name}")
