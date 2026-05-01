"""Event-driven pipeline tracker for monitoring download + stem separation."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from pikaraoke.lib.download_manager import DownloadManager
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.metadata_parser import youtube_id_suffix
from pikaraoke.lib.processing_manager import ProcessingManager
from pikaraoke.lib.queue_manager import QueueManager
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.youtube_dl import get_youtube_id_from_url


def _video_id_from_path(path: str) -> str | None:
    """Extract the 11-char YouTube ID from a song filename."""
    suffix = youtube_id_suffix(path)
    if not suffix:
        return None
    if suffix.startswith("---"):
        return suffix[3:]
    return suffix.strip(" []")


class PipelineItem:
    """Represents a single song moving through the download/processing pipeline."""

    def __init__(
        self,
        title: str,
        url: str,
        user: str,
    ) -> None:
        self.id: str = str(uuid.uuid4())
        self.title: str = title
        self.song_path: str | None = None
        self.url: str = url
        self.user: str = user
        self.download_status: str = "pending"  # pending | active | complete | error
        self.processing_status: str = (
            "waiting"  # waiting | pending | active | complete | error | cancelling
        )
        self.download_progress: float = 0.0
        self.error_message: str | None = None
        self.cancelling: bool = False


class PipelineTracker:
    """Tracks songs through the download and stem-separation pipeline.

    Subscribes to manager events and derives status by reading live state
    from DownloadManager and ProcessingManager.
    """

    def __init__(
        self,
        download_manager: DownloadManager,
        processing_manager: ProcessingManager,
        queue_manager: QueueManager,
        song_manager: SongManager,
        events: EventSystem,
        on_change: Any | None = None,
    ) -> None:
        self._download_manager = download_manager
        self._processing_manager = processing_manager
        self._queue_manager = queue_manager
        self._song_manager = song_manager
        self._events = events
        self._on_change = on_change
        self._items: list[PipelineItem] = []
        self._lock = threading.Lock()
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """Wire up event subscriptions."""
        self._events.on("download_queued", self._on_download_queued)
        self._events.on("song_downloaded", self._on_song_downloaded)
        self._events.on("download_error", self._on_download_error)
        self._events.on("processing_complete", self._on_processing_complete)
        self._events.on("processing_cancelled", self._on_processing_cancelled)
        self._events.on("processing_error", self._on_processing_error)
        self._events.on("processing_skipped", self._on_processing_skipped)
        self._events.on("song_deleted", self._on_song_deleted)

    def get_status(
        self, admin: bool = False, user: str | None = None
    ) -> list[dict[str, Any]]:
        """Return enriched status for all pipeline items.

        Derives processing status from ProcessingManager state and merges
        live download progress from DownloadManager.  Includes an ``actions``
        list per item so the client doesn't have to re-derive which buttons
        to show — auth logic lives here, in one place.

        Args:
            admin: Whether the requesting user is an admin.
            user: The requesting user's identifier (from cookie).
        """
        with self._lock:
            active_job = self._processing_manager.get_active_job()
            pending_jobs = list(self._processing_manager.pending_jobs)
            active_download = self._download_manager.active_download

            results = []
            for item in self._items:
                # Merge live download progress
                if active_download and active_download["url"] == item.url:
                    item.download_progress = active_download.get("progress", 0.0)
                    item.download_status = "active"
                elif item.download_status == "pending":
                    item.download_progress = 0.0

                # Cancelling overrides all other processing status
                if item.cancelling:
                    item.processing_status = "cancelling"
                    results.append(self._item_to_dict(item, admin, user))
                    continue

                # Derive processing status
                if item.song_path is None:
                    # Download not yet complete — show error if download failed
                    if item.download_status == "error":
                        item.processing_status = "error"
                    else:
                        item.processing_status = "waiting"
                elif active_job == item.song_path:
                    item.processing_status = "active"
                elif item.song_path in pending_jobs:
                    item.processing_status = "pending"
                else:
                    # Download complete and not in processing queues
                    # Preserve "complete"/"error" already set by events
                    if item.processing_status not in ("complete", "error"):
                        item.processing_status = "complete"

                results.append(self._item_to_dict(item, admin, user))

            return results

    def cancel(self, item_id: str) -> bool:
        """Cancel an in-progress download or processing job.

        Cancelling a processing job (pending or active) also deletes the
        downloaded song file from the library so the user starts clean.
        File I/O is done outside the lock to avoid blocking get_status().
        """
        song_to_delete: str | None = None
        notify = False
        with self._lock:
            item = self._find_item(item_id)
            if item is None:
                logging.warning("Cancel: item not found (id=%s)", item_id)
                return False

            if item.cancelling:
                logging.debug("Cancel: item already cancelling (id=%s)", item_id)
                return False

            if item.download_status == "active":
                logging.info(
                    "Cancel: aborting active download for '%s' (url=%s)", item.title, item.url
                )
                self._download_manager.cancel_active_download(item.url)
                self._remove_item(item_id)
                notify = True
            elif item.download_status == "pending":
                logging.info(
                    "Cancel: removing pending download for '%s' (url=%s)", item.title, item.url
                )
                self._download_manager.cancel_pending_download(item.url)
                self._remove_item(item_id)
                notify = True
            elif item.song_path and item.processing_status == "pending":
                logging.info(
                    "Cancel: removing pending processing job for '%s'; "
                    "song file will be deleted so the next attempt starts clean: %s",
                    item.title,
                    item.song_path,
                )
                self._processing_manager.cancel_pending(item.song_path)
                song_to_delete = item.song_path
                self._remove_item(item_id)
                notify = True
            elif item.song_path and item.processing_status == "active":
                # Delayed cancel: worker finishes current separation before
                # stopping (preserves loaded model). Mark as cancelling so the
                # UI shows the amber pulse until the pipeline exits.
                # _on_processing_cancelled handles item removal + song deletion
                # once the orchestrator emits the event.
                logging.info(
                    "Cancel: requesting cancellation of active processing for '%s'",
                    item.title,
                )
                self._processing_manager.cancel_active(item.song_path)
                item.cancelling = True
                notify = True
            else:
                logging.warning(
                    "Cancel: no cancellable state for '%s' "
                    "(download_status=%s, processing_status=%s)",
                    item.title,
                    item.download_status,
                    item.processing_status,
                )
                return False

        # File I/O outside the lock — song_manager.delete() does DB + disk ops
        # that must not block get_status() callers waiting on _lock.
        if song_to_delete:
            self._delete_song(song_to_delete)
        if notify:
            self._notify_change()
        return True

    def get_item_user(self, item_id: str) -> str | None:
        """Return the user who submitted a pipeline item, or None if not found."""
        with self._lock:
            item = self._find_item(item_id)
            return item.user if item else None

    def enqueue(self, item_id: str) -> bool:
        """Queue a completed song for playback."""
        with self._lock:
            item = self._find_item(item_id)
            if item is None or item.song_path is None:
                return False

            self._queue_manager.enqueue(item.song_path, item.user, log_action=False)
            self._remove_item(item_id)
        self._notify_change()
        return True

    def remove(self, item_id: str) -> bool:
        """Remove an item from the tracker and delete its file from disk.

        If the item is not in a terminal state (complete/error), routes
        through cancel() first so active processing is cleanly wound down
        instead of being orphaned.
        """
        # Route non-terminal items through cancel() to avoid orphaning
        # active processing jobs (which would keep running after their
        # tracker entry and song file are deleted).
        song_to_delete: str | None = None
        removed = False
        with self._lock:
            item = self._find_item(item_id)
            if item is None:
                return False
            if item.processing_status not in ("complete", "error") or item.cancelling:
                # Release lock before calling cancel(), which acquires it.
                pass
            else:
                # Terminal item — safe to remove directly.
                song_to_delete = item.song_path
                removed = self._remove_item(item_id)

        if song_to_delete:
            self._delete_song(song_to_delete)
        if removed:
            self._notify_change()
            return True

        # Non-terminal: delegate to cancel() for clean shutdown.
        return self.cancel(item_id)

    # -- Event handlers -----------------------------------------------------

    def _on_download_queued(self, data: dict[str, Any]) -> None:
        item = PipelineItem(
            title=data["title"],
            url=data["video_url"],
            user=data["user"],
        )
        with self._lock:
            self._items.append(item)
        self._notify_change()

    def _on_song_downloaded(self, song_path: str) -> None:
        path_id = _video_id_from_path(song_path)
        with self._lock:
            for item in self._items:
                if item.download_status not in ("pending", "active"):
                    continue
                url_id = get_youtube_id_from_url(item.url)
                if path_id and url_id and path_id == url_id:
                    item.song_path = song_path
                    item.download_status = "complete"
                    item.download_progress = 100.0
                    break
        self._notify_change()

    def _on_download_error(self, data: dict[str, Any]) -> None:
        url = data.get("url", "")
        with self._lock:
            for item in self._items:
                if item.url == url and item.download_status in ("pending", "active"):
                    item.download_status = "error"
                    item.error_message = data.get("error", "Unknown error")
                    break
        self._notify_change()

    def _on_processing_complete(self, song_path: str) -> None:
        with self._lock:
            for item in self._items:
                if item.song_path == song_path:
                    item.processing_status = "complete"
                    break
        self._notify_change()

    def _on_processing_cancelled(self, song_path: str) -> None:
        should_delete = False
        with self._lock:
            for item in self._items:
                if item.song_path == song_path and item.cancelling:
                    self._items.remove(item)
                    should_delete = True
                    break
        # File I/O outside the lock — song_manager.delete() does DB + disk ops
        # that must not block get_status() callers waiting on _lock.
        if should_delete:
            self._delete_song(song_path)
        self._notify_change()

    def _on_processing_error(self, data: dict[str, Any]) -> None:
        song_path = data.get("song_path", "")
        with self._lock:
            for item in self._items:
                if item.song_path == song_path:
                    item.processing_status = "error"
                    item.error_message = data.get("error", "Unknown error")
                    break
        self._notify_change()

    def _on_song_deleted(self, song_path: str) -> None:
        with self._lock:
            self._items = [item for item in self._items if item.song_path != song_path]
        self._notify_change()

    def _on_processing_skipped(self, song_path: str) -> None:
        """Remove the item from the in-flight set when blocked-words filter rejects it.

        Without this handler the rejected song's badge never clears.
        """
        with self._lock:
            self._items = [item for item in self._items if item.song_path != song_path]
        self._notify_change()

    # -- Internal helpers ---------------------------------------------------

    def _notify_change(self) -> None:
        """Fire the on_change callback (if configured) to push updates to clients."""
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                logging.debug("pipeline_tracker on_change callback failed", exc_info=True)

    def _delete_song(self, song_path: str) -> None:
        """Delete song file from library. Must be called outside _lock."""
        try:
            self._song_manager.delete(song_path)
        except Exception as e:
            logging.warning(f"Failed to delete cancelled song {song_path}: {e}")

    def _find_item(self, item_id: str) -> PipelineItem | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def _remove_item(self, item_id: str) -> bool:
        initial_len = len(self._items)
        self._items = [item for item in self._items if item.id != item_id]
        return len(self._items) < initial_len

    @staticmethod
    def _item_to_dict(
        item: PipelineItem,
        admin: bool = False,
        user: str | None = None,
    ) -> dict[str, Any]:
        is_owner = user is not None and item.user == user
        can_operate = admin or is_owner

        # --- Compute allowed actions (auth lives here, not in the client) ---
        actions: list[str] = []

        # Nothing can be done while cancellation is in flight
        if not item.cancelling:
            # Cancel: available when download or processing is in progress
            if item.download_status in ("active", "pending") or item.processing_status in (
                "active",
                "pending",
            ):
                if can_operate:
                    actions.append("cancel")

            # Remove: available on terminal items (admin only)
            if item.download_status in ("complete", "error") or item.processing_status in (
                "complete",
                "error",
            ):
                if admin:
                    actions.append("remove")

            # Enqueue: available when both stages are complete and song exists
            if (
                item.download_status == "complete"
                and item.processing_status == "complete"
                and item.song_path
            ):
                actions.append("enqueue")

        return {
            "id": item.id,
            "title": item.title,
            "song_path": item.song_path,
            "url": item.url,
            "user": item.user,
            "download_status": item.download_status,
            "processing_status": item.processing_status,
            "download_progress": item.download_progress,
            "error_message": item.error_message,
            "actions": actions,
        }
