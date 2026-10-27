"""Queue management for PiKaraoke.

Handles song queue operations including enqueueing, editing, clearing,
and fair queue algorithm.
"""

from __future__ import annotations

import functools
import logging
import random
import threading
from typing import Any, Callable

from flask_babel import _

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.preference_manager import PreferenceManager


def _locked(method: Callable[..., Any]) -> Callable[..., Any]:
    """Run a queue change under the queue lock.

    QueueHold changes held items from the download and processing threads
    while routes and the run loop change the queue.
    """

    @functools.wraps(method)
    def locked(self: QueueManager, *args: Any, **kwargs: Any) -> Any:
        with self.lock:
            return method(self, *args, **kwargs)

    return locked


class QueueManager:
    """Manages the song queue: enqueueing, editing, reordering, and fair queue logic."""

    def __init__(
        self,
        preferences: PreferenceManager,
        events: EventSystem,
        get_now_playing_user: Callable[[], str | None] | None = None,
        filename_from_path: Callable[[str, bool], str] | None = None,
        get_available_songs: Callable[[], Any] | None = None,
    ) -> None:
        self.queue: list[dict[str, Any]] = []
        # QueueHold changes held items from worker threads, so queue changes take this lock
        self.lock = threading.RLock()
        self._preferences = preferences
        self._events = events
        self._get_now_playing_user = get_now_playing_user
        self._filename_from_path = filename_from_path
        self._get_available_songs = get_available_songs

    def is_song_in_queue(self, song_path: str) -> bool:
        """Check if a song is already in the queue."""
        return any(item["file"] == song_path for item in self.queue)

    def is_user_limited(self, user: str) -> bool:
        """Check if a user has reached their queue limit."""
        limit = self._preferences.get_or_default("limit_user_songs_by")
        if limit == 0 or user in ("Pikaraoke", "Randomizer"):
            return False

        now_playing_user = self._get_now_playing_user() if self._get_now_playing_user else None
        count = sum(1 for item in self.queue if item["user"] == user) + (
            1 if now_playing_user == user else 0
        )
        return count >= int(limit)

    def _resolve_title(self, song_path: str) -> str:
        """Get a display title from a song path."""
        if self._filename_from_path:
            return self._filename_from_path(song_path, True)
        return song_path

    def _find_song_index(self, song_path: str) -> int:
        """Find a song's index in the queue by exact path match. Returns -1 if not found."""
        for idx, item in enumerate(self.queue):
            if song_path == item["file"]:
                return idx
        return -1

    def _calculate_fair_queue_position(self, user: str) -> int:
        """Calculate insertion position using Nagle Fair Queuing.

        Users take turns in rounds: a user's Nth song is placed after all
        other users' Nth songs (or at queue end).
        """
        # Count how many songs this user already has in queue
        user_song_count = sum(1 for item in self.queue if item["user"] == user)

        # Find position after the last song in "round N" where N = user_song_count
        # Round 0 = first song from each user, Round 1 = second song, etc.
        target_round = user_song_count
        songs_seen_per_user: dict[str, int] = {}

        for idx, item in enumerate(self.queue):
            queue_user = item["user"]
            songs_seen_per_user[queue_user] = songs_seen_per_user.get(queue_user, 0) + 1
            # This song is in round (count - 1) for its user
            song_round = songs_seen_per_user[queue_user] - 1
            if song_round == target_round:
                # Found a song in the target round, insert after it
                # Keep scanning to find the LAST song in this round
                pass
            elif song_round > target_round:
                # We've moved past target round, insert here
                return idx

        # All songs are in rounds <= target_round, append to end
        return len(self.queue)

    @_locked
    def enqueue(
        self,
        song_path: str,
        user: str = "Pikaraoke",
        semitones: int = 0,
        add_to_front: bool = False,
        log_action: bool = True,
        waiting: str | None = None,
        title: str | None = None,
    ) -> list[bool | str]:
        """Add a song to the queue. Returns [success, message].

        `waiting` holds the slot for a song that is not ready to play yet
        ("download", "processing" or "pick"); see QueueHold. `title` overrides the
        title derived from the path, for a held song whose path is still a URL.
        """
        title = title or self._resolve_title(song_path)

        if self.is_song_in_queue(song_path):
            logging.warning("Song is already in queue, will not add: " + song_path)
            return [
                False,
                _("Song is already in the queue: %s") % title,
            ]

        if self.is_user_limited(user):
            limit = self._preferences.get_or_default("limit_user_songs_by")
            logging.debug("User limited by: " + str(limit))
            return [
                False,
                _("You reached the limit of %s song(s) from an user in queue!") % (str(limit)),
            ]

        queue_item = {
            "user": user,
            "file": song_path,
            "title": title,
            "semitones": semitones,
            "paused": False,
            "waiting": waiting,
        }
        if add_to_front:
            # MSG: Message shown after the song is added to the top of the queue
            self._events.emit(
                "notification",
                _("%s added to top of queue: %s") % (user, queue_item["title"]),
                "info",
            )
            self.queue.insert(0, queue_item)
        else:
            if log_action:
                # MSG: Message shown after the song is added to the queue
                self._events.emit(
                    "notification",
                    _("%s added to the queue: %s") % (user, queue_item["title"]),
                    "info",
                )
            if self._preferences.get_or_default("enable_fair_queue"):
                insert_pos = self._calculate_fair_queue_position(user)
                self.queue.insert(insert_pos, queue_item)
            else:
                self.queue.append(queue_item)
        self._events.emit("queue_update")
        self._events.emit("now_playing_update")
        return [
            True,
            _("Song added to the queue: %s") % title,
        ]

    def queue_add_random(self, amount: int) -> bool:
        """Add random songs to the queue. Returns False if ran out of songs."""
        logging.info("Adding %d random songs to queue" % amount)

        if not self._get_available_songs:
            logging.error("No available songs callback provided!")
            return False

        available_songs = self._get_available_songs()

        if not available_songs:
            logging.warning("No available songs!")
            return False

        # Get songs not already in queue
        queued_paths = {item["file"] for item in self.queue}
        eligible_songs = [s for s in available_songs if s not in queued_paths]

        if not eligible_songs:
            logging.warning("All songs are already in queue!")
            return False

        # Sample up to 'amount' songs (or all eligible if fewer available)
        sample_size = min(amount, len(eligible_songs))
        selected = random.sample(eligible_songs, sample_size)

        for song in selected:
            self.enqueue(song, "Randomizer")

        if sample_size < amount:
            logging.warning("Ran out of songs! Only added %d" % sample_size)
            return False

        return True

    def queue_clear(self) -> None:
        """Clear all songs from the queue and skip current song."""
        # MSG: Message shown after the queue is cleared
        self._events.emit("notification", _("Clear queue"), "danger")
        with self.lock:
            self.queue = []
        # skip_requested takes the playback lock, which play_file holds while it reads
        # the queue, so the queue lock must be free before the events below
        self._events.emit("queue_update")
        self._events.emit("now_playing_update")
        self._events.emit("skip_requested")

    @_locked
    def reorder(self, old_index: int, new_index: int) -> bool:
        """Move a song from old_index to new_index. Returns False if indices are invalid."""
        if not (0 <= old_index < len(self.queue) and 0 <= new_index < len(self.queue)):
            logging.error(
                f"Invalid reorder indices: old={old_index}, new={new_index}, queue_len={len(self.queue)}"
            )
            return False

        if old_index == new_index:
            return True

        item = self.queue.pop(old_index)
        self.queue.insert(new_index, item)
        logging.info(f"Reordered queue: moved index {old_index} to {new_index}")
        self._events.emit("queue_update")
        self._events.emit("now_playing_update")
        return True

    @_locked
    def move_to_top(self, song_path: str) -> bool:
        """Move a song to the top of the queue (index 0). Returns False if not found or already at top."""
        index = self._find_song_index(song_path)
        if index < 1:  # Not found (-1) or already at top (0)
            if index == -1:
                logging.error("Song not found in queue: " + song_path)
            else:
                logging.warning("Song is already at top of queue: " + song_path)
            return False
        return self.reorder(index, 0)

    @_locked
    def move_to_bottom(self, song_path: str) -> bool:
        """Move a song to the bottom of the queue. Returns False if not found or already at bottom."""
        index = self._find_song_index(song_path)
        if index < 0:
            logging.error("Song not found in queue: " + song_path)
            return False
        if index >= len(self.queue) - 1:
            logging.warning("Song is already at bottom of queue: " + song_path)
            return False
        return self.reorder(index, len(self.queue) - 1)

    @staticmethod
    def is_playable(item: dict[str, Any]) -> bool:
        """Neither paused by its singer nor held for download or processing."""
        return not item.get("paused", False) and not item.get("waiting")

    @_locked
    def pop_next(self) -> dict[str, Any] | None:
        """Remove and return the next song to play from the queue.

        Paused and held songs stay in place; see _take_next for how a held
        song's turn is used. Returns None if no remaining song is playable.

        Does not emit queue_update to avoid UI flicker during song transitions.
        The playback system emits now_playing events which trigger queue UI updates.
        """
        song = self._take_next(self.queue)
        if song is not None:
            logging.info(f"Popped song from queue: {song['title']}")
        return song

    @_locked
    def upcoming(self, count: int) -> list[dict[str, Any]]:
        """The next ``count`` songs in the order pop_next will play them, as the queue stands."""
        remaining = list(self.queue)
        songs: list[dict[str, Any]] = []
        while len(songs) < count and (song := self._take_next(remaining)) is not None:
            songs.append(song)
        return songs

    @staticmethod
    def _take_next(queue: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Remove and return the song that plays next from ``queue``.

        Turns are taken in queue order. A playable song plays in its own turn.
        An unpaused held song's turn goes to its singer's first later playable
        song, which swaps places with it: turns belong to singers, so the ready
        song plays now and the held one moves back to its slot.
        """
        for turn, item in enumerate(queue):
            if QueueManager.is_playable(item):
                return queue.pop(turn)
            if item.get("waiting") and not item.get("paused", False):
                later = next(
                    (
                        idx
                        for idx in range(turn + 1, len(queue))
                        if queue[idx]["user"] == item["user"]
                        and QueueManager.is_playable(queue[idx])
                    ),
                    None,
                )
                if later is not None:
                    queue[turn], queue[later] = queue[later], queue[turn]
                    return queue.pop(turn)
        return None

    def has_playable_song(self) -> bool:
        """True if the queue has at least one playable song."""
        return any(self.is_playable(item) for item in self.queue)

    @_locked
    def toggle_pause_song(self, song_path: str) -> bool:
        """Toggle the paused flag on a single queued song. Used by admins. Returns False if not found."""
        index = self._find_song_index(song_path)
        if index == -1:
            logging.error("Song not found in queue: " + song_path)
            return False
        item = self.queue[index]
        item["paused"] = not item.get("paused", False)
        state = "paused" if item["paused"] else "unpaused"
        logging.info(f"Song {state}: {song_path}")
        self._events.emit("queue_update")
        self._events.emit("now_playing_update")
        return True

    @_locked
    def toggle_pause_user(self, user: str) -> bool:
        """Toggle pause on all queued songs for a user (step-away mode).

        Pauses all if any are unpaused; unpauses all if all are paused.
        Returns False if the user has no songs in the queue.
        """
        user_items = [item for item in self.queue if item["user"] == user]
        if not user_items:
            logging.error(f"No queued songs found for user: {user}")
            return False
        new_state = not all(item.get("paused", False) for item in user_items)
        for item in user_items:
            item["paused"] = new_state
        logging.info(f"All songs for {user} {'paused' if new_state else 'unpaused'}")
        # MSG: Shown when a user pauses/unpauses all their queued songs
        msg = _("%s paused their songs") % user if new_state else _("%s is back") % user
        self._events.emit("notification", msg, "info")
        self._events.emit("queue_update")
        self._events.emit("now_playing_update")
        return True

    @_locked
    def queue_edit(self, song_path: str, action: str) -> bool:
        """Move or remove a song in the queue. Action: 'up', 'down', or 'delete'."""
        index = self._find_song_index(song_path)
        if index == -1:
            logging.error("Song not found in queue: " + song_path)
            return False

        if action == "up":
            if index < 1:
                logging.warning("Song is up next, can't bump up in queue: " + song_path)
                return False
            return self.reorder(index, index - 1)

        if action == "down":
            if index == len(self.queue) - 1:
                logging.warning("Song is already last, can't bump down in queue: " + song_path)
                return False
            return self.reorder(index, index + 1)

        if action == "delete":
            logging.info("Deleting song from queue: " + song_path)
            del self.queue[index]
            self._events.emit("queue_update")
            self._events.emit("now_playing_update")
            return True

        logging.error("Unrecognized action: " + action)
        return False
