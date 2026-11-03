"""Socket.IO event handlers for PiKaraoke."""


from flask_socketio import emit

from pikaraoke.lib.current_app import get_karaoke_instance


def setup_socket_events(socketio):
    """Register Socket.IO event handlers.

    Args:
        socketio: The SocketIO instance.
    """

    @socketio.on("connect")
    def connect() -> None:
        """Send the connecting client the current playback state.

        A phone whose socket dropped and reconnected missed every now_playing
        push in between, and would show stale pause state and song length
        until the next one.
        """
        emit("now_playing", get_karaoke_instance().get_now_playing())

    @socketio.on("end_song")
    def end_song(reason: str) -> None:
        """Handle end_song WebSocket event from client (manual force end from remote UI).

        Args:
            reason: Reason for ending the song (e.g., 'complete', 'error').
        """
        k = get_karaoke_instance()
        k.playback_controller.end_song(reason)

    @socketio.on("clear_notification")
    def clear_notification() -> None:
        """Handle clear_notification WebSocket event to dismiss notifications."""
        k = get_karaoke_instance()
        k.reset_now_playing_notification()
