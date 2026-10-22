"""Event-driven pipeline tracker for monitoring download + stem separation."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from pikaraoke.lib.download_manager import DownloadManager
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.library_regen import RegenJob
from pikaraoke.lib.library_status import song_status
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
    """Represents a single song moving through the download/processing pipeline.

    ``kind`` is ``download`` (a song fetched through the app; cancelling or
    removing it deletes the song), ``regen`` (a library tool regenerating a
    song already in the library) or ``process`` (processing of a song already
    in the library). Regen and process rows never delete files.
    """

    def __init__(
        self,
        title: str,
        url: str,
        user: str,
        kind: str = "download",
        label: str | None = None,
    ) -> None:
        self.id: str = str(uuid.uuid4())
        self.title: str = title
        self.song_path: str | None = None
        self.url: str = url
        self.user: str = user
        self.kind: str = kind  # download | regen | process
        self.label: str | None = label  # the row's kind word, e.g. "Repair"
        self.regen_job: RegenJob | None = None  # kept so a failed regen can be retried
        self.finished_at: float | None = None  # time.time() at complete / error
        self.download_status: str = "pending"  # pending | active | complete | error
        self.processing_status: str = (
            "waiting"  # waiting | pending | active | complete | error | cancelling
        )
        self.processing_phase: str | None = None
        self.error_message: str | None = None
        self.cancelling: bool = False
        # Lyric source + matcher combo recorded at processing completion
        # (e.g. "genius+joint", "srt+joint", "transcribe"). Surfaced in the
        # processing-page label so the lyric source is visible at a glance.
        self.lyric_method: str | None = None
        # Set at completion when the song looks poor (see library_status): how
        # many of its lines have no word timing. Shown to admins only.
        self.guessed: int | None = None
        self.line_count: int | None = None

    @property
    def is_terminal(self) -> bool:
        """Finished one way or the other: nothing more will happen to this row."""
        return self.processing_status in ("complete", "error")


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
        self._events.on("regen_queued", self._on_regen_queued)
        self._events.on("processing_queued", self._on_processing_queued)
        self._events.on("processing_complete", self._on_processing_complete)
        self._events.on("processing_cancelled", self._on_processing_cancelled)
        self._events.on("processing_error", self._on_processing_error)
        self._events.on("processing_skipped", self._on_processing_skipped)
        self._events.on("song_deleted", self._on_song_deleted)
        self._events.on("pipeline_stage_changed", self._on_pipeline_stage_changed)

    def get_status(self, admin: bool = False, user: str | None = None) -> list[dict[str, Any]]:
        """Return enriched status for all pipeline items, in the order the page shows them.

        Derives processing status from ProcessingManager state and flips
        the active download status by reading DownloadManager.active_url.
        Includes an ``actions`` list per item so the client doesn't have
        to re-derive which buttons to show — auth logic lives here, in
        one place. Each row also carries its ``group`` and, in the active
        group, its queue ``position`` (see :meth:`_in_display_order`).

        Only ``download`` rows are shown to non-admins: regen and process
        rows are library maintenance.

        Args:
            admin: Whether the requesting user is an admin.
            user: The requesting user's identifier (from cookie).
        """
        with self._lock:
            active_job = self._processing_manager.get_active_job()
            active_phase = self._processing_manager.get_active_phase()
            active_elapsed_s = self._processing_manager.get_active_elapsed_s()
            pending_jobs = list(self._processing_manager.pending_jobs)
            active_url = self._download_manager.active_url

            rows = []
            for item in self._items:
                if item.kind != "download" and not admin:
                    continue
                if active_url == item.url and item.download_status == "pending":
                    item.download_status = "active"
                self._derive_processing_status(item, active_job, active_phase, pending_jobs)
                running = item.song_path is not None and item.song_path == active_job
                elapsed_s = active_elapsed_s if running and item.finished_at is None else None
                rows.append((item, self._item_to_dict(item, admin, user, elapsed_s)))

            return self._in_display_order(rows, active_job, pending_jobs)

    @staticmethod
    def _derive_processing_status(
        item: PipelineItem,
        active_job: str | None,
        active_phase: str | None,
        pending_jobs: list[str],
    ) -> None:
        """Set the item's processing status and phase from the manager's live state."""
        # Cancelling overrides all other processing status
        if item.cancelling:
            item.processing_status = "cancelling"
            item.processing_phase = None
            return

        # A row its complete or error event finished keeps that status:
        # the manager names the job as running until it has cleaned up.
        if item.finished_at is not None:
            return

        if item.song_path is None:
            # Download not yet complete (a failed one has finished above)
            item.processing_status = "waiting"
            item.processing_phase = None
        elif active_job == item.song_path:
            item.processing_status = "active"
            item.processing_phase = active_phase
        elif item.song_path in pending_jobs:
            item.processing_status = "pending"
            item.processing_phase = None
        else:
            # Download complete and not in processing queues
            # Preserve "complete"/"error" already set by events
            if item.processing_status not in ("complete", "error"):
                item.processing_status = "complete"
            item.processing_phase = None

    @staticmethod
    def _in_display_order(
        rows: list[tuple[PipelineItem, dict[str, Any]]],
        active_job: str | None,
        pending_jobs: list[str],
    ) -> list[dict[str, Any]]:
        """Sort rows for display and stamp each with its ``group`` and ``position``.

        Groups come in this order, each sorted as described:

        - ``active``: the running job; the download in progress; downloads
          waiting to start, in the order they were added; then songs waiting
          for processing in the order the manager will run them (the download
          lane, which holds downloads and process rows, before the regen lane).
          Every active row but the running one gets a ``position`` from 1.
        - ``attention``: downloads and jobs that failed, newest first.
        - ``finished``: complete rows, newest first.
        """

        def group_of(item: PipelineItem) -> str:
            if item.processing_status == "error":
                return "attention"
            return "finished" if item.processing_status == "complete" else "active"

        def is_running(item: PipelineItem) -> bool:
            return item.cancelling or (item.song_path is not None and item.song_path == active_job)

        def active_rank(item: PipelineItem) -> tuple[int, int]:
            """(step, queue order); equal ranks keep the order the rows were added."""
            if is_running(item):
                return 0, 0
            if item.download_status == "active":
                return 1, 0
            if item.download_status == "pending":
                return 2, 0
            queued = pending_jobs.index(item.song_path) if item.song_path in pending_jobs else 0
            return (4 if item.kind == "regen" else 3), queued

        groups: dict[str, list[tuple[PipelineItem, dict[str, Any]]]] = {
            "active": [],
            "attention": [],
            "finished": [],
        }
        for item, result in rows:
            groups[group_of(item)].append((item, result))

        ordered = []
        for group, members in groups.items():
            if group == "active":
                members.sort(key=lambda member: active_rank(member[0]))
            else:
                members.sort(key=lambda member: -(member[0].finished_at or 0.0))
            position = 0
            for item, result in members:
                result["group"] = group
                result["position"] = None
                if group == "active" and not is_running(item):
                    position += 1
                    result["position"] = position
                ordered.append(result)
        return ordered

    def cancel(self, item_id: str) -> bool:
        """Cancel an in-progress download or processing job.

        Cancelling a processing job (pending or active) of a ``download`` item
        also deletes the downloaded song file from the library so the user
        starts clean. A ``regen`` or ``process`` item is a song already in the
        library: its file is never touched.
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
                    "Cancel: removing pending processing job for '%s' (%s): %s",
                    item.title,
                    item.kind,
                    item.song_path,
                )
                self._processing_manager.cancel_pending(item.song_path)
                if item.kind == "download":
                    # The next attempt starts clean.
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

        Only ``download`` items: a ``regen`` or ``process`` row is a song
        already in the library (use :meth:`dismiss` to drop the row).

        If the item is not in a terminal state (complete/error), routes
        through cancel() first so active processing is cleanly wound down
        instead of being orphaned.
        """
        # Route non-terminal items through cancel() to avoid orphaning
        # active processing jobs (which would keep running after their
        # tracker entry and song file are deleted).
        # We loop up to twice to handle the race condition where an active item
        # transitions to terminal exactly between dropping the lock and calling cancel().
        for _ in range(2):
            song_to_delete: str | None = None
            removed = False
            with self._lock:
                item = self._find_item(item_id)
                if item is None or item.kind != "download":
                    return False
                if item.cancelling:
                    return False
                if item.processing_status not in ("complete", "error"):
                    # Release lock before calling cancel(), which acquires it.
                    is_terminal = False
                else:
                    # Terminal item — safe to remove directly.
                    song_to_delete = item.song_path
                    removed = self._remove_item(item_id)
                    is_terminal = True

            if is_terminal:
                if song_to_delete:
                    self._delete_song(song_to_delete)
                if removed:
                    self._notify_change()
                return removed

            # Non-terminal: delegate to cancel() for clean shutdown.
            if self.cancel(item_id):
                return True

        return False

    def dismiss(self, item_id: str) -> bool:
        """Drop a finished row from the list. Never touches files."""
        with self._lock:
            item = self._find_item(item_id)
            if item is None or not item.is_terminal:
                return False
            removed = self._remove_item(item_id)
        if removed:
            self._notify_change()
        return removed

    def retry(self, item_id: str) -> bool:
        """Run a failed item again.

        A ``regen`` item queues its job again as a new row; any other item
        goes back to ``waiting`` with its error cleared and is queued for
        processing. False when the item isn't a failed one with a song path,
        or the song is already queued.
        """
        with self._lock:
            item = self._find_item(item_id)
            if item is None or item.processing_status != "error" or item.song_path is None:
                return False
            song_path = item.song_path
            regen_job = item.regen_job  # only regen rows carry one
            if regen_job is None:
                item.processing_status = "waiting"
                item.processing_phase = None
                item.error_message = None
                item.finished_at = None

        # Outside the lock: queueing emits events that this tracker handles.
        if regen_job is not None:
            return self._processing_manager.enqueue_regen(regen_job)
        self._processing_manager.enqueue(song_path)
        self._notify_change()
        return True

    def tracked_paths(self) -> set[str]:
        """Song paths that have a row, finished or not."""
        with self._lock:
            return {item.song_path for item in self._items if item.song_path}

    def clear_finished(self) -> int:
        """Drop every completed row; returns how many went. Never touches files."""
        with self._lock:
            before = len(self._items)
            self._items = [item for item in self._items if item.processing_status != "complete"]
            cleared = before - len(self._items)
        if cleared:
            self._notify_change()
        return cleared

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
                    break
        self._notify_change()

    def _on_download_error(self, data: dict[str, Any]) -> None:
        url = data.get("url", "")
        with self._lock:
            for item in self._items:
                if item.url == url and item.download_status in ("pending", "active"):
                    item.download_status = "error"
                    item.processing_status = "error"
                    item.error_message = data.get("error", "Unknown error")
                    item.finished_at = time.time()
                    break
        self._notify_change()

    def _on_regen_queued(self, data: dict[str, Any]) -> None:
        """A library tool queued a regen job: show it as a ``regen`` row."""
        song_path = data["song_path"]
        item = PipelineItem(
            title=SongManager.filename_from_path(song_path),
            url="",
            user="",
            kind="regen",
            label=data["label"],
        )
        item.song_path = song_path
        item.download_status = "complete"
        item.regen_job = data["job"]
        with self._lock:
            self._drop_terminal_items(song_path)
            self._items.append(item)
        self._notify_change()

    def _on_processing_queued(self, song_path: str) -> None:
        """A song was queued for processing: a song with no live row gets a ``process`` row.

        A download already has its row (the tracker hears ``song_downloaded``
        first), and a retried item is back in flight, so neither adds one.
        """
        with self._lock:
            if self._find_unfinished(song_path) is not None:
                return
            self._drop_terminal_items(song_path)
            item = PipelineItem(
                title=SongManager.filename_from_path(song_path),
                url="",
                user="",
                kind="process",
                label="Process",
            )
            item.song_path = song_path
            item.download_status = "complete"
            self._items.append(item)
        self._notify_change()

    def _on_processing_complete(self, data: dict[str, Any]) -> None:
        song_path = data["song_path"]
        lyric_method = data.get("lyric_method")
        poor = self._poor_lines(song_path)  # reads the new bundle; keep it outside the lock
        with self._lock:
            item = self._find_unfinished(song_path)
            if item is not None:
                item.processing_status = "complete"
                item.processing_phase = None
                item.cancelling = False  # a cancel that came too late
                item.finished_at = time.time()
                if lyric_method is not None:
                    item.lyric_method = lyric_method
                if poor is not None:
                    item.guessed, item.line_count = poor
        self._notify_change()

    def _on_processing_cancelled(self, song_path: str) -> None:
        should_delete = False
        with self._lock:
            for item in self._items:
                if item.song_path == song_path and item.cancelling:
                    self._items.remove(item)
                    # Only a download's file is the tracker's to delete.
                    should_delete = item.kind == "download"
                    break
        # File I/O outside the lock — song_manager.delete() does DB + disk ops
        # that must not block get_status() callers waiting on _lock.
        if should_delete:
            self._delete_song(song_path)
        self._notify_change()

    def _on_processing_error(self, data: dict[str, Any]) -> None:
        song_path = data.get("song_path", "")
        with self._lock:
            item = self._find_unfinished(song_path)
            if item is not None:
                item.processing_status = "error"
                item.processing_phase = None
                item.cancelling = False  # get_status shows a cancelling row as nothing else
                item.error_message = data.get("error", "Unknown error")
                item.finished_at = time.time()
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

    def _on_pipeline_stage_changed(self) -> None:
        """Push an update when the pipeline transitions between stages.

        The actual phase value is read live by get_status() from
        ProcessingManager.get_active_phase(), so this handler just
        fires _notify_change to trigger a push-driven re-render.
        """
        self._notify_change()

    # -- Internal helpers ---------------------------------------------------

    def _notify_change(self) -> None:
        """Fire the on_change callback (if configured) to push updates to clients."""
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                logging.debug("pipeline_tracker on_change callback failed", exc_info=True)

    @staticmethod
    def _poor_lines(song_path: str) -> tuple[int, int] | None:
        """(guessed, line_count) when the finished song looks poor, else None.

        Never raises: an exception from an event handler would reach the
        manager and fail a job that had just succeeded.
        """
        try:
            # poor and guessed do arithmetic on the bundle's counts, so they stay inside too
            status = song_status(Path(song_path))
            return (status.guessed, status.line_count) if status.poor else None
        except (OSError, ValueError, TypeError, AttributeError) as e:
            logging.warning("Could not read the bundle of %s: %s", song_path, e)
            return None

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

    def _find_unfinished(self, song_path: str) -> PipelineItem | None:
        """The first row for ``song_path`` that hasn't finished (caller holds _lock)."""
        for item in self._items:
            if item.song_path == song_path and not item.is_terminal:
                return item
        return None

    def _drop_terminal_items(self, song_path: str) -> None:
        """Drop finished rows for ``song_path`` so a new run starts a fresh row (caller holds _lock)."""
        self._items = [
            item for item in self._items if item.song_path != song_path or not item.is_terminal
        ]

    def _remove_item(self, item_id: str) -> bool:
        initial_len = len(self._items)
        self._items = [item for item in self._items if item.id != item_id]
        return len(self._items) < initial_len

    @staticmethod
    def _item_to_dict(
        item: PipelineItem,
        admin: bool = False,
        user: str | None = None,
        elapsed_s: float | None = None,
    ) -> dict[str, Any]:
        is_download = item.kind == "download"
        # A regen or process row has no singer: only an admin operates it.
        is_owner = is_download and user is not None and item.user == user
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

            if admin:
                # Remove deletes the song, so only a download that has a file offers it.
                if is_download and item.song_path:
                    actions.append("remove")
                # Dismiss drops a finished row and touches no file.
                if item.is_terminal:
                    actions.append("dismiss")
                # Retry: processing failed on a song that is in the library.
                if item.processing_status == "error" and item.song_path:
                    actions.append("retry")
                if item.song_path:
                    actions.append("song_info")

            # Enqueue: available when both stages are complete and song exists
            if (
                is_download
                and item.download_status == "complete"
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
            "kind": item.kind,
            "label": item.label,
            "download_status": item.download_status,
            "processing_status": item.processing_status,
            "processing_phase": item.processing_phase,
            "error_message": item.error_message,
            "actions": actions,
            "lyric_method": item.lyric_method,
            "mine": is_owner,
            "guessed": item.guessed if admin else None,
            "line_count": item.line_count if admin else None,
            "finished_ago_s": (
                time.time() - item.finished_at if item.finished_at is not None else None
            ),
            "elapsed_s": elapsed_s,
        }
