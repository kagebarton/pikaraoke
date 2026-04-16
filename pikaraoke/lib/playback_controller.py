"""Playback controller for managing video playback state and coordination."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from flask_babel import _

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.overlay_manager import OverlayState, ScreenMode
from pikaraoke.lib.preference_manager import PreferenceManager

if TYPE_CHECKING:
    from pikaraoke.lib.mpv_controller import MpvController


@dataclass
class PlaybackResult:
    """Result of a playback operation.

    Attributes:
        success: Whether playback started successfully.
        error: Error message if playback failed.
    """

    success: bool
    error: str | None = None


class PlaybackController:
    """Controller for managing playback state and MPV coordination.

    Owns all "now playing" state and coordinates with MpvController for
    native MPV playback.

    Attributes:
        now_playing: Title of the currently playing song.
        now_playing_filename: File path of the currently playing song.
        now_playing_user: User who queued the current song.
        now_playing_transpose: Semitones to transpose current song.
        now_playing_duration: Duration of current song in seconds.
        now_playing_position: Current playback position in seconds.
        is_paused: Whether playback is paused.
        is_playing: Whether a song is currently playing.
    """

    now_playing: str | None = None
    now_playing_filename: str | None = None
    now_playing_user: str | None = None
    now_playing_transpose: int = 0
    now_playing_duration: int | None = None
    now_playing_position: float | None = None
    is_paused: bool = True
    is_playing: bool = False

    def __init__(
        self,
        preferences: PreferenceManager,
        events: EventSystem,
        filename_from_path: Callable[[str, bool], str],
        mpv: MpvController,
    ) -> None:
        """Initialize the playback controller.

        Args:
            preferences: PreferenceManager instance for configuration.
            events: EventSystem instance for event emission.
            filename_from_path: Function to extract display name from path.
            mpv: MpvController instance for MPV IPC.
        """
        self.preferences = preferences
        self.events = events
        self.filename_from_path = filename_from_path
        self.mpv = mpv
        self._playback_lock = threading.Lock()
        # Injected by Karaoke after queue_manager is available
        self._get_up_next_title: Callable[[], str | None] = lambda: None

    def play_file(self, file_path: str, user: str, semitones: int = 0) -> PlaybackResult:
        """Start playback of a media file. Non-blocking -- MPV plays immediately.

        Args:
            file_path: Path to the media file to play.
            user: User who queued the song.
            semitones: Number of semitones to transpose (0 = no change).

        Returns:
            PlaybackResult with success status and optional error message.
        """
        if not os.path.isfile(file_path):
            error_msg = _("Song file not found: %s") % file_path
            logging.warning(error_msg)
            return PlaybackResult(success=False, error=error_msg)

        logging.info(
            f"Playing file: {file_path} for user: {user}, transposed {semitones} semitones"
        )

        # Find subtitle file (.srt in subtitles/ subfolder)
        subtitle_path = self._find_subtitle(file_path)
        subtitle_delay = self.preferences.get_or_default("subtitle_delay")

        # Get normalization_db from song database (if normalize_audio enabled)
        normalization_db = None
        if self.preferences.get_or_default("normalize_audio"):
            # Normalization value will be fetched from song database when implemented
            # For now, normalization is toggled but no per-song dB values are stored
            normalization_db = None  # Will be populated when ProcessingManager stores it

        with self._playback_lock:
            self.mpv.play(
                file_path,
                semitones=semitones,
                subtitle_path=subtitle_path,
                subtitle_delay=subtitle_delay,
                normalization_db=normalization_db,
            )

            self.now_playing = self.filename_from_path(file_path, remove_youtube_id=True)
            self.now_playing_filename = file_path
            self.now_playing_user = user
            self.now_playing_transpose = semitones
            self.now_playing_duration = int(self.mpv.duration) if self.mpv.duration else None
            self.now_playing_position = 0.0
            self.is_paused = False
            self.is_playing = True

        self.events.emit("playback_started")

        logging.debug("MPV playback started")
        return PlaybackResult(success=True)

    def _find_subtitle(self, file_path: str) -> str | None:
        """Find the downloaded-subtitle (.srt) companion for a media file.

        Karaoke captions (.ass, generated from confirmed lyrics) will be
        added here behind a user preference in a future change.

        Args:
            file_path: Path to the media file.

        Returns:
            Path to subtitle file, or None.
        """
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        srt_path = os.path.join(os.path.dirname(file_path), "subtitles", base_name + ".srt")
        if os.path.exists(srt_path):
            logging.debug(f"SRT subtitle file found: {srt_path}")
            return srt_path
        return None

    def end_song(self, reason: str | None = None) -> None:
        """End current song. Must be called with _playback_lock held
        (check_playback_ended acquires it) or acquires it when called
        externally (skip, Socket.IO end_song).

        Args:
            reason: Optional reason for ending (e.g., 'complete', 'skip').
        """
        # Guard: prevent double end_song
        if not self.is_playing:
            return

        logging.info(f"Song ending: {self.now_playing}")
        if reason:
            logging.info(f"Reason: {reason}")
            if reason not in ("complete", "skip"):
                self.events.emit(
                    "notification",
                    _("Song ended abnormally: %s") % reason,
                    "danger",
                )

        self.mpv.stop()
        self.reset_now_playing()
        self.events.emit("song_ended")
        logging.debug("Cleanup complete")

    def skip(self, log_action: bool = True) -> bool:
        """Skip the currently playing song.

        Args:
            log_action: Whether to log and notify about the skip.

        Returns:
            True if a song was skipped, False if nothing playing.
        """
        if self.is_playing:
            if log_action:
                self.events.emit(
                    "notification",
                    _("Skip: %s") % self.now_playing,
                    "info",
                )
            with self._playback_lock:
                self.end_song(reason="skip")
            return True
        else:
            logging.warning("Tried to skip, but no file is playing!")
            return False

    def pause(self) -> bool:
        """Toggle pause state of the current song.

        Returns:
            True if successful, False if nothing playing.
        """
        if self.is_playing:
            self.mpv.toggle_pause()
            # Query actual state from MPV
            is_now_paused = self.mpv.is_paused
            if is_now_paused:
                self.events.emit("notification", _("Pause: %s") % self.now_playing, "info")
            else:
                self.events.emit("notification", _("Resume: %s") % self.now_playing, "info")
            self.events.emit("now_playing_update")
            return True
        else:
            logging.warning("Tried to pause, but no file is playing!")
            return False

    def get_now_playing(self) -> dict[str, str | int | float | bool | None]:
        """Get the current playback state.

        Returns:
            Dictionary with now playing information.
        """
        return {
            "now_playing": self.now_playing,
            "now_playing_user": self.now_playing_user,
            "now_playing_duration": self.now_playing_duration,
            "now_playing_transpose": self.now_playing_transpose,
            "now_playing_position": self.mpv.position,
            "is_paused": self.mpv.is_paused,
        }

    def reset_now_playing(self) -> None:
        """Reset all now playing state to defaults."""
        self.now_playing = None
        self.now_playing_filename = None
        self.now_playing_user = None
        self.now_playing_transpose = 0
        self.now_playing_duration = None
        self.now_playing_position = None
        self.is_paused = True
        self.is_playing = False

    def build_overlay_state(self) -> OverlayState:
        """Snapshot all data needed by compute_overlays into one immutable record.

        Called each poll tick (and on immediate renders) by MpvController._tick_overlays.
        """
        if self.is_playing:
            mode = ScreenMode.PAUSED if self.mpv.is_paused else ScreenMode.PLAYING
        else:
            mode = ScreenMode.IDLE

        return OverlayState(
            mode=mode,
            now_playing_title=self.now_playing,
            up_next_title=self._get_up_next_title(),
            semitones=self.now_playing_transpose,
            position=self.mpv.position,
            duration=self.mpv.duration,
            screen_w=self.mpv.osd_size[0],
            screen_h=self.mpv.osd_size[1],
            hide_url=self.preferences.get_or_default("hide_url"),
            hide_now_playing=self.preferences.get_or_default("hide_now_playing_overlay"),
            show_clock=self.preferences.get_or_default("show_clock"),
            server_url=self.mpv._server_url,
        )

    def refresh_overlays(self) -> None:
        """Force an immediate overlay re-render outside the poll cycle.

        Call this after toggling any overlay-related preference so the change
        is visible within the current frame rather than waiting up to 500ms.
        """
        self.mpv._tick_overlays()

    def broadcast_position(self, socketio) -> None:
        """Emit current playback position to all Socket.IO clients."""
        if self.is_playing and socketio:
            socketio.emit("playback_position", self.mpv.position, namespace="/")

    def set_pitch(self, semitones: int) -> None:
        """Live pitch change on current song."""
        if self.is_playing:
            self.mpv.set_pitch(semitones)
            self.now_playing_transpose = semitones
            self.events.emit("now_playing_update")

    def set_subtitle_delay(self, seconds: float) -> None:
        """Forward subtitle delay to MPV."""
        if self.is_playing:
            self.mpv.set_subtitle_delay(seconds)

    def restart(self) -> bool:
        """Restart current song from beginning (seek 0 + unpause)."""
        if self.is_playing:
            self.mpv.restart()
            self.events.emit("now_playing_update")
            return True
        logging.warning("Tried to restart, but no file is playing!")
        return False
