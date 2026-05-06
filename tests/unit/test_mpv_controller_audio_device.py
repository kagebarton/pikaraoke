"""Tests for MpvController audio device handling."""

from unittest.mock import MagicMock

from pikaraoke.lib.mpv_controller import MpvController


def test_list_audio_devices_returns_auto_when_player_not_running():
    c = MpvController()
    assert c.list_audio_devices() == [{"name": "auto", "description": "Autoselect device"}]


def test_list_audio_devices_maps_libmpv_response():
    c = MpvController()
    c._player = MagicMock()
    c._player.audio_device_list = [
        {"name": "auto", "description": "Autoselect device"},
        {"name": "pipewire/sink-a", "description": "USB Headset"},
    ]
    assert c.list_audio_devices() == [
        {"name": "auto", "description": "Autoselect device"},
        {"name": "pipewire/sink-a", "description": "USB Headset"},
    ]


def test_list_audio_devices_falls_back_on_libmpv_error():
    c = MpvController()
    c._player = MagicMock()
    type(c._player).audio_device_list = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("mpv not ready"))
    )
    assert c.list_audio_devices() == [{"name": "auto", "description": "Autoselect device"}]


def test_list_audio_devices_handles_none_response():
    c = MpvController()
    c._player = MagicMock()
    c._player.audio_device_list = None
    assert c.list_audio_devices() == []
