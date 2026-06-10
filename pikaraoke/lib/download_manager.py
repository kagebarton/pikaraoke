"""Download queue manager for serialized video downloads."""

from __future__ import annotations

import contextlib
import glob
import logging
import subprocess
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
        self.pending_downloads: list[dict] = []  # Shadow queue for cancellation lookup
        self.active_url: str | None = None
        self._active_process: subprocess.Popen | None = None  # Stored for cancellation
        # URLs the worker must skip — only for the in-flight case (already dequeued
        # before cancel_pending_download could rebuild it out of the queue). A
        # still-queued cancel is handled by the rebuild alone and never recorded
        # here, or a later re-queue of the same URL would be silently skipped.
        self._cancelled_urls: set[str] = set()
        self._cancelling: bool = False  # Suppress the error toast for a user-killed download
        self._worker_thread: Thread | None = None
        self._is_downloading: bool = False  # Track if a download is currently in progress

    def start(self) -> None:
        """Start the download worker thread."""
        self._worker_thread = Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        logging.debug("Download queue worker started")

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

        download_data = {
            "video_url": video_url,
            "enqueue": enqueue,
            "user": user,
            "title": title,
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
                continue

            # Remove from shadow queue
            # Note: Since this is a single worker thread and append happens on main thread,
            # we simply pop the first item as it corresponds to FIFO queue.
            # In a multi-worker scenario, this would need a lock.
            if self.pending_downloads:
                self.pending_downloads.pop(0)

            self._is_downloading = True
            self.active_url = video_url

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
                self.active_url = None
                q.task_done()

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

        # A fresh download starts un-cancelled; a user cancel during the run below
        # flips this flag so the non-zero exit from the killed process is treated
        # as a deliberate stop rather than a download error.
        self._cancelling = False

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

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self._active_process = process
        video_id = get_youtube_id_from_url(video_url)

        output, _stderr = process.communicate()
        rc = process.returncode
        self._active_process = None

        if rc != 0:
            if self._cancelling:
                # The user cancelled: this non-zero rc is from our own process
                # kill, not a real failure, so stay quiet instead of flashing a
                # spurious danger toast / download_error.
                self._cancelling = False
                logging.info("Download cancelled by user: %s", displayed_title)
            else:
                # MSG: Message shown after the download process is completed but the song is not found
                self._events.emit(
                    "notification", _("Error downloading song: ") + displayed_title, "danger"
                )
                logging.error(f"yt-dlp stderr: {output}")
                self._events.emit(
                    "download_error",
                    {"url": video_url, "error": output or "Unknown error"},
                )
        else:
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
                # Move subtitle into subtitles/ BEFORE emitting song_downloaded,
                # so the processing pipeline can find it for alignment.
                self._move_downloaded_subtitle(song_path)
                self._events.emit("song_downloaded", song_path)
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
                If provided and it does not match ``self.active_url``,
                the call is a no-op (the active download has already moved on
                to a different song and must not be killed).
        """
        active_url = self.active_url

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
            # Flag the kill so the worker's non-zero rc is read as a deliberate
            # cancel (no danger toast) rather than a download failure.
            self._cancelling = True
            try:
                self._active_process.kill()
            except ProcessLookupError:
                pass
            self._active_process = None

        if active_url:
            video_id = get_youtube_id_from_url(active_url)
            if video_id:
                self._cleanup_partial_downloads(video_id)

        self._is_downloading = False
        self.active_url = None

    def cancel_pending_download(self, video_url: str) -> None:
        """Cancel a download the caller believes is still queued.

        Drops the item from the shadow list and the work queue. If the rebuild
        can't find it the item already left the queue, which means one of:

        * it is the **active** download — the tracker flips status to "active"
          only lazily, so an in-flight song can be routed here; kill it via the
          active path rather than recording it (the worker is past its skip
          check, so a recorded entry would never be consumed and would leak);
        * the worker **just dequeued** it but hasn't marked it active yet —
          record it so the worker skips (and discards) it as it starts.

        A still-queued item is dropped by the rebuild alone and is *not*
        recorded; otherwise a later re-queue of the same URL would be silently
        skipped.
        """
        # Remove from shadow queue
        self.pending_downloads = [d for d in self.pending_downloads if d["video_url"] != video_url]
        # Drain from the Queue (there's no public remove, so we rebuild)
        new_queue: Queue = Queue()
        removed = False
        while not self.download_queue.empty():
            item = self.download_queue.get_nowait()
            if item["video_url"] == video_url and not removed:
                removed = True
                self.download_queue.task_done()
            else:
                new_queue.put(item)
        self.download_queue = new_queue
        if not removed:
            if video_url == self.active_url:
                self.cancel_active_download(video_url)
            else:
                self._cancelled_urls.add(video_url)

    def _cleanup_partial_downloads(self, video_id: str) -> None:
        """Remove partial download files matching a video ID.

        Sweeps the temp directory as well as the download directory: with a
        non-empty temp_dir, yt-dlp writes .part/merge intermediates under
        ``--paths temp:`` there, so a cancelled download would orphan them
        unless both locations are cleaned.
        """
        # Match the bare 11-char ID, which covers both filename conventions
        # (Title---VIDEOID.* and Title [VIDEOID].*). Globbing the literal ID rather than
        # a [VIDEOID] bracket pattern avoids the character-class misread that would match
        # every file in the directory.
        search_dirs = [Path(self._download_path)]
        if self._temp_dir and Path(self._temp_dir) != Path(self._download_path):
            search_dirs.append(Path(self._temp_dir))
        for search_dir in search_dirs:
            for f in search_dir.glob(f"*{video_id}*"):
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
            for f in video.parent.glob(f"{glob.escape(video.stem)}*{ext}")
        }

        srt_files = {f for f in candidates if f.suffix == ".srt"}
        if not srt_files:
            logging.debug(f"No subtitle found for video: {video_path}")
            return

        # Prefer .en.srt over bare .srt as a defense against yt-dlp
        # filename variations where multiple language tracks were emitted.
        en_srts = {f for f in srt_files if ".en.srt" in f.name}
        source = next(iter(en_srts)) if en_srts else next(iter(srt_files))
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
