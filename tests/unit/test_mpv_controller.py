"""Unit tests for MpvController playback control, observers, and filters.

Complements test_mpv_controller_audio_device.py with the coverage C11 calls
for: callback registration, the song-end (idle) hook, the pause toggle,
property/playback setters, and the lavfi-complex filter builder. All libmpv
interaction is mocked; MpvController.__init__ does no I/O.
"""

import subprocess
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import mpv
import pytest

from pikaraoke.lib.mpv_controller import (
    _RB_FULLMIX,
    _RB_NONVOCAL,
    _RB_VOCAL,
    MpvController,
)


@pytest.fixture
def controller():
    c = MpvController()
    c._player = MagicMock()
    return c


# ── Callback registration ────────────────────────────────────────────────────


def test_set_callbacks_stores_all_three():
    c = MpvController()
    end, resize, tick = MagicMock(), MagicMock(), MagicMock()
    c.set_callbacks(end, resize, tick)
    assert c._on_song_end is end
    assert c._on_resize is resize
    assert c._on_tick is tick


# ── Song-end hook (idle-active observer) ──────────────────────────────────────


def test_idle_active_fires_song_end_once_on_transition(controller):
    end = MagicMock()
    controller.set_callbacks(end, MagicMock(), MagicMock())
    controller.is_idle = False

    controller._on_idle_active("idle-active", True)
    assert controller.is_idle is True
    end.assert_called_once()

    # Re-entry guard: already idle, must not fire again.
    controller._on_idle_active("idle-active", True)
    end.assert_called_once()


def test_idle_active_ignores_non_idle_value(controller):
    end = MagicMock()
    controller.set_callbacks(end, MagicMock(), MagicMock())
    controller.is_idle = False
    controller._on_idle_active("idle-active", False)
    assert controller.is_idle is False
    end.assert_not_called()


# ── Pause ─────────────────────────────────────────────────────────────────────


def test_toggle_pause_cycles_pause_property(controller):
    controller.toggle_pause()
    controller._player.cycle.assert_called_once_with("pause")


def test_toggle_pause_noop_when_player_not_running():
    c = MpvController()  # _player is None
    assert c.toggle_pause() is None  # _safe short-circuits, no crash


def test_on_pause_observer_updates_state(controller):
    controller._on_pause("pause", True)
    assert controller.is_paused is True
    controller._on_pause("pause", False)
    assert controller.is_paused is False


def test_on_pause_observer_ignores_none(controller):
    controller.is_paused = True
    controller._on_pause("pause", None)
    assert controller.is_paused is True


# ── Property / playback setters ───────────────────────────────────────────────


def test_seek_issues_absolute_seek(controller):
    controller.seek(42.5)
    controller._player.command.assert_called_once_with("seek", 42.5, "absolute")


def test_restart_seeks_zero_and_unpauses(controller):
    controller.restart()
    controller._player.command.assert_called_once_with("seek", 0, "absolute")
    assert controller._player.pause is False


def test_set_subtitle_delay_sets_property_and_state(controller):
    controller.set_subtitle_delay(0.4)
    assert controller._subtitle_delay == 0.4
    assert controller._player.sub_delay == 0.4


def test_set_pitch_rebuilds_filter_at_new_pitch(controller):
    controller.set_pitch(2)
    assert controller._current_pitch == pytest.approx(2 ** (2 / 12))
    # single-stem, no normalization → rubberband-only graph at the rounded pitch
    assert "rubberband@rb=pitch=1.1225" in controller._player.lavfi_complex


def test_set_vocal_volume_noop_for_single_stem(controller):
    controller._dual_stem = False
    controller.set_vocal_volume(0.5)
    assert controller._current_vocal_volume == 1.0  # early return leaves it unchanged


# ── osd_size property ──────────────────────────────────────────────────────────


def test_osd_size_defaults_to_1080p():
    assert MpvController().osd_size == (1920, 1080)


def test_osd_size_reflects_observed_dimensions(controller):
    controller._current_osd_dim = [1280, 720]
    assert controller.osd_size == (1280, 720)


# ── build_filter (pure) ─────────────────────────────────────────────────────────


def test_build_filter_single_stem_no_normalization():
    assert MpvController.build_filter(1.0) == f"[aid1]rubberband@rb=pitch=1.0:{_RB_FULLMIX}[ao]"


def test_build_filter_single_stem_applies_normalization_volume():
    f = MpvController.build_filter(1.0, normalization_db=-3.5)
    assert f == f"[aid1]rubberband@rb=pitch=1.0:{_RB_FULLMIX}[pre];[pre]volume=-3.5dB[ao]"


def test_build_filter_dual_stem_graph():
    f = MpvController.build_filter(1.0, dual_stem=True, vocal_volume=0.8)
    assert "volume@vocalvol=0.8" in f
    assert "azmq=bind_address=" in f
    assert f"rubberband@vocalrb=pitch=1.0:{_RB_VOCAL}[vocal]" in f
    assert f"rubberband@nonvocalrb=pitch=1.0:{_RB_NONVOCAL}[nonvocal]" in f
    assert f.endswith("[vocal][nonvocal]amix=inputs=2:normalize=0[ao]")


def test_build_filter_dual_stem_with_normalization():
    f = MpvController.build_filter(1.0, normalization_db=-2.0, dual_stem=True, vocal_volume=1.0)
    assert "[vocal][nonvocal]amix=inputs=2:normalize=0[mixed]" in f
    assert f.endswith("[mixed]volume=-2.0dB[ao]")


# ── play(): duration reset (Review-fix: stale-duration race) ─────────────────


@pytest.fixture
def ready_controller(controller):
    """A mocked controller whose duration-ready wait resolves immediately."""
    controller._duration_ready = MagicMock()
    controller._duration_ready.wait.return_value = True
    controller._player.duration = 0
    return controller


def test_play_clears_stale_duration_when_new_file_reports_none(ready_controller):
    # Leftover duration from a previous song must not survive a load whose
    # observer never fires (the synchronous fallback read also finds nothing).
    ready_controller.duration = 212.0
    ready_controller.play("/tmp/song.mp4")
    assert ready_controller.duration == 0.0


def test_play_keeps_synchronous_duration_when_observer_misses(ready_controller):
    ready_controller._player.duration = 187.5  # fallback read succeeds
    ready_controller.play("/tmp/song.mp4")
    assert ready_controller.duration == 187.5


# ── play(): dual-stem audio-add wait (Review-fix: fixed-sleep race) ──────────


def test_audio_track_count_counts_only_audio(controller):
    controller._player.track_list = [
        {"type": "video"},
        {"type": "audio"},
        {"type": "audio"},
        {"type": "sub"},
    ]
    assert controller._audio_track_count() == 2


def test_audio_track_count_zero_without_player():
    assert MpvController()._audio_track_count() == 0


def test_wait_for_audio_tracks_returns_promptly_once_target_met(controller, monkeypatch):
    monkeypatch.setattr(controller, "_audio_track_count", lambda: 3)
    start = time.monotonic()
    controller._wait_for_audio_tracks(3, timeout=2.0)
    assert time.monotonic() - start < 0.5  # did not burn the whole budget


def test_wait_for_audio_tracks_times_out_with_warning(controller, monkeypatch, caplog):
    monkeypatch.setattr(controller, "_audio_track_count", lambda: 1)
    controller._wait_for_audio_tracks(3, timeout=0.05)  # never reaches target
    assert any("not ready" in r.message for r in caplog.records)


def test_play_dual_stem_adds_tracks_then_waits_for_them(ready_controller, monkeypatch):
    waited = []
    monkeypatch.setattr(ready_controller, "_audio_track_count", lambda: 1)
    monkeypatch.setattr(
        ready_controller,
        "_wait_for_audio_tracks",
        lambda target, timeout: waited.append((target, timeout)),
    )
    ready_controller.play("/tmp/v.mp4", vocal_path="/tmp/voc.wav", nonvocal_path="/tmp/inst.wav")
    issued = [c.args for c in ready_controller._player.command.call_args_list]
    assert ("audio-add", "/tmp/voc.wav", "auto") in issued
    assert ("audio-add", "/tmp/inst.wav", "auto") in issued
    assert waited == [(3, 2.0)]  # before-count (1) + 2 added, 2.0s budget


# ── play()/stop(): shutdown safety (Review-fix: teardown race) ───────────────


def test_play_noop_when_player_none():
    assert MpvController().play("/tmp/x.mp4") is None  # no AttributeError


def test_stop_noop_when_player_none():
    assert MpvController().stop() is None


def test_play_aborts_cleanly_on_shutdown(ready_controller):
    ready_controller._player.loadfile.side_effect = mpv.ShutdownError()
    assert ready_controller.play("/tmp/x.mp4") is None  # ShutdownError swallowed


def test_stop_aborts_cleanly_on_shutdown():
    class _ShutdownPlayer:
        @property
        def lavfi_complex(self):
            return ""

        @lavfi_complex.setter
        def lavfi_complex(self, value):
            raise mpv.ShutdownError()

    c = MpvController()
    c._player = _ShutdownPlayer()
    assert c.stop() is None  # ShutdownError swallowed, is_idle still set
    assert c.is_idle is True


# ── get_system_volume(): wpctl muted sink (Review-fix) ───────────────────────


def test_get_system_volume_wpctl_muted_reports_zero(controller, monkeypatch):
    controller._audio_backend = "wpctl"
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="Volume: 0.65 [MUTED]")
    )
    assert controller.get_system_volume() == 0


def test_get_system_volume_wpctl_unmuted_parses_percentage(controller, monkeypatch):
    controller._audio_backend = "wpctl"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="Volume: 0.65"))
    assert controller.get_system_volume() == 65
