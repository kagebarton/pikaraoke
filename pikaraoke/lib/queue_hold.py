"""Holds a searched song's queue slot from the click until the song is ready to play.

Invariant: a held item's ``file`` is a URL until its download lands, and ``waiting`` is
cleared only once ``file`` is a library path, so the run loop never pops a URL.
Wiring: construct it before LibraryTools' ``song_downloaded`` handler is registered, because
that handler can emit processing events synchronously and they must find the item's path set.
"""

from __future__ import annotations

from typing import Any

from flask_babel import _

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.library_tools import LibraryTools
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.lib.queue_manager import QueueManager
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.youtube_dl import get_youtube_id_from_url


class QueueHold:
    """Follows a held queue item through download and processing until it can play."""

    def __init__(
        self,
        queue_manager: QueueManager,
        events: EventSystem,
        library_tools: LibraryTools,
        song_manager: SongManager,
    ) -> None:
        self._queue_manager = queue_manager
        self._events = events
        self._library_tools = library_tools
        self._song_manager = song_manager
        events.on("download_queued", self._on_download_queued)
        events.on("song_downloaded", self._on_song_downloaded)
        events.on("needs_pick", self._on_needs_pick)
        events.on("processing_queued", self._on_processing_queued)
        events.on("processing_complete", self._on_processing_complete)
        events.on("processing_skipped", self._release)
        events.on("processing_error", self._on_processing_error)
        events.on("processing_cancelled", self._drop)
        events.on("song_deleted", self._drop)
        events.on("download_error", self._on_download_failed)
        events.on("download_cancelled", self._on_download_failed)

    def waiting_for(self, song_path: str) -> str | None:
        """What a library song that is not ready is still waiting on: "pick", "processing" or None.

        None means nothing will finish it, so a manual Add must not hold a slot for it.
        """
        if self._library_tools.is_waiting_for_pick(song_path):
            return "pick"
        if self._library_tools.is_busy(song_path):
            return "processing"
        return None

    def settle(self, song_path: str) -> None:
        """Release or drop a song a manual Add has just held, if its event came first.

        The Add reads the song's state and then holds it. Processing can finish
        or fail in between, and its event then finds nothing to change.
        """
        state = self._song_manager.get_pipeline_state(song_path)
        if state == "failed":
            self._on_processing_error({"song_path": song_path})
        elif state != "pending":
            self._release(song_path)

    def _held(self, file: str) -> dict[str, Any] | None:
        """The held item with this ``file``; a ready item is never returned."""
        return next(
            (
                item
                for item in self._queue_manager.queue
                if item["file"] == file and item.get("waiting")
            ),
            None,
        )

    def _held_download(self, song_path: str) -> dict[str, Any] | None:
        """The item holding a slot for the download that produced ``song_path``."""
        path_id = extract_youtube_id(song_path)
        if not path_id:
            return None
        return next(
            (
                item
                for item in self._queue_manager.queue
                if item.get("waiting") == "download"
                and get_youtube_id_from_url(item["file"]) == path_id
            ),
            None,
        )

    def _changed(self) -> None:
        self._events.emit("queue_update")
        self._events.emit("now_playing_update")

    def _set_waiting(self, song_path: str, waiting: str | None) -> None:
        with self._queue_manager.lock:
            item = self._held(song_path)
            if item is None or item["waiting"] == waiting:
                return
            item["waiting"] = waiting
            self._changed()

    def _remove(self, item: dict[str, Any]) -> None:
        self._queue_manager.queue_edit(item["file"], "delete")

    def _on_download_queued(self, data: dict[str, Any]) -> None:
        if not data["enqueue"]:
            return
        success, message = self._queue_manager.enqueue(
            data["video_url"], data["user"], waiting="download", title=data["title"]
        )
        if not success:
            # The download still runs, as a library-only one.
            self._events.emit("notification", message, "warning")

    def _on_song_downloaded(self, song_path: str) -> None:
        with self._queue_manager.lock:
            item = self._held_download(song_path)
            if item is None:
                return
            if self._queue_manager.is_song_in_queue(song_path):
                self._remove(item)
                self._events.emit(
                    "notification", _("Already in the queue: %s") % item["title"], "warning"
                )
                return
            # file first, then waiting: the item stays unplayable throughout
            item["file"] = song_path
            item["waiting"] = "processing"
            self._changed()

    def _on_needs_pick(self, song_path: str) -> None:
        self._set_waiting(song_path, "pick")

    def _on_processing_queued(self, song_path: str) -> None:
        self._set_waiting(song_path, "processing")

    def _on_processing_complete(self, data: dict[str, Any]) -> None:
        self._release(data["song_path"])

    def _release(self, song_path: str) -> None:
        self._set_waiting(song_path, None)

    def _on_processing_error(self, data: dict[str, Any]) -> None:
        with self._queue_manager.lock:
            item = self._held(data["song_path"])
            if item is None:
                return
            self._remove(item)
            self._events.emit(
                "notification",
                _("%s couldn't be processed and was taken off the queue") % item["title"],
                "danger",
            )

    def _drop(self, song_path: str) -> None:
        with self._queue_manager.lock:
            item = self._held(song_path)
            if item is not None:
                self._remove(item)

    def _on_download_failed(self, data: dict[str, Any]) -> None:
        """A failed or cancelled download frees its slot; the download side has told the user."""
        self._drop(data["url"])
