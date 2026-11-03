"""Tests for Socket.IO event handlers."""

from unittest.mock import MagicMock

from flask import Flask
from flask_socketio import SocketIO

from pikaraoke.routes.socket_events import setup_socket_events


def test_connect_sends_the_client_current_playback_state():
    """A phone reconnecting after a Wi-Fi drop missed the pushes in between."""
    app = Flask(__name__)
    k = MagicMock()
    k.get_now_playing.return_value = {"now_playing": "Song", "is_paused": True}
    app.config["KARAOKE_INSTANCE"] = k
    socketio = SocketIO(app)
    setup_socket_events(socketio)

    client = socketio.test_client(app)

    assert client.get_received() == [
        {
            "name": "now_playing",
            "args": [{"now_playing": "Song", "is_paused": True}],
            "namespace": "/",
        }
    ]
