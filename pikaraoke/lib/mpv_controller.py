"""MPV controller using python-mpv (libmpv) bindings."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from typing import Callable

import qrcode
from PIL import Image

import mpv
from pikaraoke.lib.overlay_manager import OverlayManager, OverlayState, ScreenMode

# ── SRT subtitle style ─────────────────────────────────────────────────────────
SRT_STYLE = {
    "sub-ass-override": "no",
    "sub-font": "Arial",
    "sub-font-size": 40,
    "sub-color": "#FFD700",
    "sub-border-color": "#000000",
    "sub-border-size": 3,
    "sub-shadow-offset": 2,
    "sub-shadow-color": "#80000000",
    "sub-bold": "no",
    "sub-margin-y": 100,
}

# OSD ID constants (re-exported for callers that only import mpv_controller)
from pikaraoke.lib.overlay_manager import (  # noqa: E402
    ALL_OSD_IDS,
    OSD_CLOCK,
    OSD_NOWPLAYING,
    OSD_TIMECODE,
    OSD_UPNEXT,
    OSD_URL,
)

log = logging.getLogger(__name__)

# ── Rubberband filter presets (from mpv/ prototype) ─────────────────────────
_RB_VOCAL = (
    "pitchq=quality:transients=crisp:detector=compound"
    ":phase=laminar:window=long:formant=preserved"
    ":channels=together:smoothing=off"
)
_RB_NONVOCAL = (
    "pitchq=quality:transients=crisp:detector=percussive"
    ":phase=laminar:window=short:formant=shifted"
    ":channels=apart:smoothing=off"
)


def _semiround(val: float, decimals: int = 4) -> float:
    """Round to avoid floating-point noise in filter strings."""
    return round(val, decimals)


def _safe(method):
    """Catch and log exceptions from mpv calls; return None on failure.

    Applied to every public method that touches the player so a transient
    libmpv error or a ShutdownError during teardown does not crash the caller.
    Not applied to start/quit (failures there are fatal and must propagate).
    """

    def wrapper(self, *args, **kwargs):
        if self._player is None:
            return None
        try:
            return method(self, *args, **kwargs)
        except mpv.ShutdownError:
            return None
        except Exception:
            log.exception("MpvController.%s failed", method.__name__)
            return None

    wrapper.__name__ = method.__name__
    return wrapper


class MpvController:
    """Thin wrapper around a libmpv instance and its property observers.

    Manages the MPV lifecycle, sends commands via python-mpv, and drives
    overlay rendering via observer callbacks. Does not contain business
    logic -- PlaybackController orchestrates.
    """

    def __init__(self) -> None:
        self._player: mpv.MPV | None = None
        self._lock = threading.RLock()  # guards filter rebuilds
        self._duration_ready = threading.Event()
        self.is_running = False

        # Observer-tracked state (read by PlaybackController)
        self.position: float = 0.0
        self.duration: float = 0.0
        self.is_idle: bool = True
        self.is_paused: bool = False

        # OSD dimensions (coalesced from two observers)
        self._current_osd_dim: list[int | None] = [None, None]
        self._fired_osd_dim: tuple[int | None, int | None] = (None, None)
        self._last_tick_emit: float = 0.0

        # Playback filter state (needed for live rebuild)
        self._current_pitch: float = 1.0
        self._current_normalization_db: float | None = None
        self._dual_stem: bool = False
        self._current_vocal_volume: float = 1.0

        # Subtitle mode state
        self._available_subs: dict[str, str | None] = {"ass": None, "srt": None}
        self._current_sub_mode: str = "off"
        self._subtitle_delay: float = 0.0

        # Audio backend
        self._audio_backend: str | None = None

        # Overlay manager and state provider
        self._overlay_manager = OverlayManager(self)
        self._overlay_state_provider: Callable[[], OverlayState] | None = None
        self._screen_mode: ScreenMode = ScreenMode.IDLE

        # Callbacks -- set via set_callbacks() before start()
        self._on_song_end: Callable[[], None] | None = None
        self._on_resize: Callable[[], None] | None = None
        self._on_tick: Callable[[], None] | None = None

        # Preferences -- set by Karaoke before calling start()
        self._preferences = None

        self._placeholder_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static",
            "images",
            "placeholder.png",
        )
        self._qr_code_path: str | None = None
        self._server_url: str = ""

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def set_callbacks(
        self,
        on_song_end: Callable[[], None],
        on_resize: Callable[[], None],
        on_tick: Callable[[], None],
    ) -> None:
        """Register application callbacks. Call before start()."""
        self._on_song_end = on_song_end
        self._on_resize = on_resize
        self._on_tick = on_tick

    def set_overlay_state_provider(self, provider: Callable[[], OverlayState]) -> None:
        """Register a callable that builds the current OverlayState each tick.

        Called once by Karaoke during wiring. The provider is invoked each poll
        cycle and on mode changes to get a fresh snapshot of playback + prefs.
        """
        self._overlay_state_provider = provider

    @property
    def osd_size(self) -> tuple[int, int]:
        """Current (width, height) of the mpv OSD, defaulting to 1920x1080.

        Returns the last values received via osd-width/osd-height observers
        rather than querying the player, so it is safe to call at any time.
        """
        w, h = self._current_osd_dim
        return (int(w) if w else 1920, int(h) if h else 1080)

    @property
    def duration_ready(self) -> threading.Event:
        """Event set when duration > 0 is known; cleared on each play()."""
        return self._duration_ready

    def start(self) -> None:
        """Create the libmpv instance, register observers, load placeholder."""
        self._player = mpv.MPV(
            idle=True,
            force_window=True,
            image_display_duration="inf",
            osd_margin_x=0,
            osd_margin_y=0,
            terminal=False,
            input_vo_keyboard=True,
        )
        p = self._player
        p.observe_property("time-pos", self._on_time_pos)
        p.observe_property("duration", self._on_duration)
        p.observe_property("idle-active", self._on_idle_active)
        p.observe_property("pause", self._on_pause)
        p.observe_property("osd-width", self._on_osd_dim)
        p.observe_property("osd-height", self._on_osd_dim)

        @p.on_key_press("f")
        def _toggle_fullscreen():
            p.fullscreen = not p.fullscreen

        self._generate_qr()
        self.load_placeholder()
        self.apply_srt_style()

        try:
            self._audio_backend = self._detect_audio_backend()
        except RuntimeError:
            logging.warning("No audio server found (wpctl/pactl/amixer). Volume controls disabled.")
            self._audio_backend = None

        self.is_running = True
        logging.info("MPV started successfully (python-mpv / libmpv)")

    def quit(self) -> None:
        """Shut down the libmpv instance cleanly."""
        self.is_running = False
        p = self._player
        if p is not None:
            self._player = None
            try:
                p.quit(0)
                p.wait_for_shutdown()
            except Exception:
                pass
            try:
                p.terminate()
            except Exception:
                pass
        logging.info("MPV stopped")

    # ── Observer callbacks ─────────────────────────────────────────────────────
    # All run on python-mpv's event-dispatch thread. Must NOT call blocking
    # primitives (wait_for_property, wait_for_event) -- that would deadlock.

    def _on_time_pos(self, _name, value):
        try:
            if value is None:
                return
            self.position = float(value)
            now = time.monotonic()
            if now - self._last_tick_emit >= 0.5:
                self._last_tick_emit = now
                if self._on_tick:
                    self._on_tick()
        except Exception:
            log.exception("_on_time_pos error")

    def _on_duration(self, _name, value):
        try:
            if value is not None and float(value) > 0:
                self.duration = float(value)
                self._duration_ready.set()
        except Exception:
            log.exception("_on_duration error")

    def _on_idle_active(self, _name, value):
        # not self.is_idle guards against re-entry: placeholder loads and
        # programmatic stop() both set is_idle = True before triggering mpv idle.
        try:
            if value is True and not self.is_idle:
                self.is_idle = True
                if self._on_song_end:
                    self._on_song_end()
        except Exception:
            log.exception("_on_idle_active error")

    def _on_pause(self, _name, value):
        try:
            if value is not None:
                self.is_paused = bool(value)
        except Exception:
            log.exception("_on_pause error")

    def _on_osd_dim(self, name, value):
        # Each observer delivers one dimension at a time. Coalesce into a pair
        # and fire resize only when the complete (w, h) pair changes.
        try:
            if value is None:
                return
            if "width" in name:
                self._current_osd_dim[0] = value
            else:
                self._current_osd_dim[1] = value
            w, h = self._current_osd_dim
            if w is None or h is None:
                return
            pair = (w, h)
            if pair == self._fired_osd_dim:
                return
            self._fired_osd_dim = pair
            self._overlay_manager.invalidate()
            if self._on_resize:
                self._on_resize()
        except Exception:
            log.exception("_on_osd_dim error")

    # ── Playback ───────────────────────────────────────────────────────────────

    @_safe
    def play(
        self,
        file_path: str,
        semitones: int = 0,
        *,
        ass_path: str | None = None,
        srt_path: str | None = None,
        initial_sub_mode: str = "off",
        subtitle_delay: float = 0.0,
        normalization_db: float | None = None,
        vocal_path: str | None = None,
        nonvocal_path: str | None = None,
        vocal_volume: float = 1.0,
    ) -> None:
        """Load a file and start playback with pitch/normalization/subtitles."""
        pitch = 2 ** (semitones / 12)
        self._current_pitch = pitch
        self._current_normalization_db = normalization_db

        # Store available subtitle paths and resolve initial mode
        self._available_subs = {"ass": ass_path, "srt": srt_path}
        self._current_sub_mode = initial_sub_mode
        self._subtitle_delay = subtitle_delay

        # Dual-stem state
        self._dual_stem = bool(vocal_path and nonvocal_path)
        self._current_vocal_volume = vocal_volume

        # Set before loadfile to guard _on_idle_active
        self.is_idle = False
        self.is_paused = False
        self.position = 0.0

        self._duration_ready.clear()
        self._fired_osd_dim = (None, None)  # force overlay refresh on resize
        self._player.loadfile(file_path)

        if not self._duration_ready.wait(timeout=5):
            log.warning("Duration not ready after 5s -- proceeding anyway")

        # Add audio tracks for dual-stem playback
        if self._dual_stem:
            self._player.command("audio-add", vocal_path, "auto")
            self._player.command("audio-add", nonvocal_path, "auto")
            time.sleep(0.2)

        filter_str = self.build_filter(
            pitch,
            normalization_db,
            dual_stem=self._dual_stem,
            vocal_volume=vocal_volume,
        )
        with self._lock:
            self._player.lavfi_complex = filter_str

        # Apply subtitle mode after lavfi-complex is set (skip_remove=True
        # on initial play to avoid segfault when lavfi-complex is active)
        self._apply_subtitle_mode(initial_sub_mode, skip_remove=True, subtitle_delay=subtitle_delay)

        self.duration = float(self._player.duration or 0.0)
        self.set_mode(ScreenMode.PLAYING)

    @_safe
    def stop(self) -> None:
        """Stop playback and return to idle/placeholder."""
        self.is_idle = True  # guard _on_idle_active before clearing filter
        with self._lock:
            self._player.lavfi_complex = ""
        self.position = 0.0
        self.duration = 0.0
        self.is_paused = False
        self.set_mode(ScreenMode.IDLE)

    @_safe
    def seek(self, position: float) -> None:
        """Seek to absolute position in seconds."""
        self._player.command("seek", position, "absolute")

    @_safe
    def toggle_pause(self) -> None:
        """Toggle pause state. is_paused is updated by _on_pause observer."""
        self._player.cycle("pause")

    @_safe
    def set_pitch(self, semitones: int) -> None:
        """Live mid-song pitch change: rebuild lavfi-complex with new pitch."""
        pitch = 2 ** (semitones / 12)
        self._current_pitch = pitch
        filter_str = self.build_filter(
            pitch,
            self._current_normalization_db,
            dual_stem=self._dual_stem,
            vocal_volume=self._current_vocal_volume,
        )
        with self._lock:
            self._player.lavfi_complex = filter_str

    @_safe
    def set_vocal_volume(self, volume: float) -> None:
        """Live vocal volume change via ZMQ (no filter rebuild needed).

        Only works when dual-stem is active; no-op otherwise.
        """
        if not self._dual_stem:
            return
        self._current_vocal_volume = volume
        try:
            import zmq

            ctx = zmq.Context.instance()
            sock = ctx.socket(zmq.REQ)
            sock.setsockopt(zmq.RCVTIMEO, 500)
            sock.connect("tcp://127.0.0.1:5556")
            sock.send_string(f"volume@vocalvol volume {volume}")
            sock.recv()
            sock.close()
        except Exception:
            log.debug("set_vocal_volume ZMQ send failed (non-fatal)")

    @_safe
    def _apply_subtitle_mode(
        self, mode: str, *, skip_remove: bool = False, subtitle_delay: float = 0.0
    ) -> None:
        """Atomic: update state, remove current sub, add new, apply delay.

        Invariant: sub_delay is 0.0 for any mode != 'srt'.

        Args:
            mode: One of 'karaoke', 'srt', 'off'.
            skip_remove: When True, skip the sub_remove() call. Used on
                initial play where mpv may have auto-loaded a matching subtitle;
                calling sub-remove on that auto-loaded track while lavfi-complex
                is active triggers a libmpv segfault. sub_add(..., "select")
                alone correctly replaces the active subtitle without the crash.
            subtitle_delay: Delay to apply when mode is 'srt'. Ignored for
                other modes (delay is reset to 0.0).
        """
        prev_mode = self._current_sub_mode
        self._current_sub_mode = mode
        path = None
        if mode == "karaoke":
            path = self._available_subs.get("ass")
        elif mode == "srt":
            path = self._available_subs.get("srt")

        if not skip_remove:
            # sid="no" is safe with lavfi-complex active; sub-remove segfaults libmpv.
            self._player.sid = "no"

        if path and os.path.exists(path):
            self._player.sub_add(path, "select")
            if mode == "srt":
                self.apply_srt_style()
                self._player.sub_delay = float(subtitle_delay)
            else:
                self._player.sub_delay = 0.0
        else:
            self._player.sub_delay = 0.0

    @_safe
    def set_sub_mode(self, mode: str) -> None:
        """Public wrapper for subtitle mode changes (skip_remove=False).

        When switching to 'srt' mode, applies the current subtitle delay.
        """
        self._apply_subtitle_mode(mode, skip_remove=False, subtitle_delay=self._subtitle_delay)

    @_safe
    def set_subtitle_delay(self, seconds: float) -> None:
        """Set subtitle delay on the running player.

        Delay is meaningful only in 'srt' mode; _apply_subtitle_mode
        enforces delay=0 for other modes.
        """
        self._subtitle_delay = float(seconds)
        self._player.sub_delay = float(seconds)

    @_safe
    def restart(self) -> None:
        """Seek to 0 and unpause."""
        self._player.command("seek", 0, "absolute")
        self._player.pause = False

    # ── Screen mode ────────────────────────────────────────────────────────────

    def set_mode(self, mode: ScreenMode) -> None:
        """Transition the display mode and trigger an immediate overlay render.

        This is the single place that drives placeholder loading -- callers
        (play, stop) just set the desired mode.
        """
        if mode == self._screen_mode:
            self._tick_overlays()
            return
        self._screen_mode = mode
        if mode == ScreenMode.IDLE:
            self.load_placeholder()
        self._tick_overlays()

    def _tick_overlays(self) -> None:
        """Build an OverlayState snapshot and hand it to OverlayManager."""
        if self._overlay_state_provider is None:
            return
        state = self._overlay_state_provider()
        self._overlay_manager.apply(state)

    # ── OSD / Overlay ──────────────────────────────────────────────────────────

    @_safe
    def osd_overlay(self, overlay_id: int, data: str, res_x: int = 1920, res_y: int = 1080) -> None:
        """Send an ASS-events OSD overlay."""
        self._player.command(
            "osd-overlay",
            id=overlay_id,
            format="ass-events",
            data=data,
            res_x=res_x,
            res_y=res_y,
        )

    @_safe
    def clear_osd(self, overlay_id: int, res_x: int = 1920, res_y: int = 1080) -> None:
        """Clear an OSD overlay slot."""
        self._player.command(
            "osd-overlay",
            id=overlay_id,
            format="none",
            data="",
            res_x=res_x,
            res_y=res_y,
        )

    @_safe
    def overlay_add(
        self,
        overlay_id: int,
        x: int,
        y: int,
        path: str,
        offset: int,
        fmt: str,
        w: int,
        h: int,
        stride: int,
    ) -> None:
        """Add a raw BGRA bitmap overlay."""
        self._player.command(
            "overlay-add",
            overlay_id,
            x,
            y,
            path,
            offset,
            fmt,
            w,
            h,
            stride,
        )

    @_safe
    def overlay_remove(self, overlay_id: int) -> None:
        """Remove a bitmap overlay slot."""
        self._player.command("overlay-remove", overlay_id)

    @_safe
    def load_placeholder(self) -> None:
        """Load the placeholder image into the running mpv instance."""
        if os.path.exists(self._placeholder_path):
            self._player.loadfile(self._placeholder_path)

    @_safe
    def apply_srt_style(self) -> None:
        """Push SRT subtitle style properties to the player."""
        for prop, val in SRT_STYLE.items():
            setattr(self._player, prop.replace("-", "_"), val)

    @_safe
    def send_qr_bitmap(self, screen_h: int, screen_w: int = 1920) -> None:
        """Send the QR code BGRA bitmap to mpv overlay slot 0."""
        qr_path = self._qr_code_path
        if not qr_path or not os.path.exists(qr_path):
            return
        qr_h = max(120, screen_h // 6)
        qr_img = Image.open(qr_path).convert("RGBA").resize((qr_h, qr_h))
        r, g, b, a = qr_img.split()
        bgra = Image.merge("RGBA", (b, g, r, a))
        bgra_bytes = bgra.tobytes()

        from pikaraoke.lib.get_platform import get_temp_directory

        overlay_path = os.path.join(get_temp_directory(), "qr_overlay.bgra")
        with open(overlay_path, "wb") as f:
            f.write(bgra_bytes)

        self.overlay_add(0, 0, 0, overlay_path, 0, "bgra", qr_h, qr_h, qr_h * 4)

    @_safe
    def remove_qr_bitmap(self) -> None:
        """Remove the QR bitmap overlay from mpv (overlay slot 0)."""
        self.overlay_remove(0)

    # ── Filter Builder ─────────────────────────────────────────────────────────

    @staticmethod
    def build_filter(
        pitch: float,
        normalization_db: float | None = None,
        dual_stem: bool = False,
        vocal_volume: float = 1.0,
    ) -> str:
        """Build the lavfi-complex string for single-stem or dual-stem playback.

        Single-stem: [aid1] -> rubberband(_RB_VOCAL) -> volume(norm) -> [ao]
        Dual-stem:   [aid2] -> volume@vocalvol -> azmq -> rubberband(_RB_VOCAL) -> [vocal];
                     [aid3] -> volume -> rubberband(_RB_NONVOCAL) -> [nonvocal];
                     amix -> volume(norm) -> [ao]
        """
        pitch = _semiround(pitch)

        if dual_stem:
            # Nonvocal volume is always 1.0 (fixed)
            nonvocal_vol = 1.0
            amix_out = (
                f"[vocal][nonvocal]amix=inputs=2:normalize=0[mixed];"
                f"[mixed]volume={normalization_db}dB[ao]"
                if normalization_db is not None
                else "[vocal][nonvocal]amix=inputs=2:normalize=0[ao]"
            )
            return (
                f"[aid2]volume@vocalvol={vocal_volume}"
                f",azmq=bind_address=tcp\\\\://127.0.0.1\\\\:5556"
                f",rubberband@vocalrb=pitch={pitch}:{_RB_VOCAL}[vocal];"
                f"[aid3]volume@nonvocalvol={nonvocal_vol}"
                f",rubberband@nonvocalrb=pitch={pitch}:{_RB_NONVOCAL}[nonvocal];"
                f"{amix_out}"
            )

        # Single-stem branch
        if normalization_db is not None:
            norm_str = f"{normalization_db}dB"
            return (
                f"[aid1]rubberband@rb=pitch={pitch}:{_RB_VOCAL}" f"[pre];[pre]volume={norm_str}[ao]"
            )
        return f"[aid1]rubberband@rb=pitch={pitch}:{_RB_VOCAL}[ao]"

    # ── Volume (Audio Server Abstraction) ──────────────────────────────────────

    @staticmethod
    def _detect_audio_backend() -> str:
        """Detect available audio backend."""
        if shutil.which("wpctl"):
            return "wpctl"
        if shutil.which("pactl"):
            return "pactl"
        if shutil.which("amixer"):
            return "amixer"
        raise RuntimeError("No audio backend found (wpctl, pactl, amixer)")

    def get_system_volume(self) -> int:
        """Query system default sink volume as 0-100."""
        if not self._audio_backend:
            return 100
        try:
            if self._audio_backend == "wpctl":
                r = subprocess.run(
                    ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                import re

                m = re.search(r"(\d+(?:\.\d+)?)", r.stdout)
                return round(float(m.group(1)) * 100) if m else 100
            elif self._audio_backend == "pactl":
                r = subprocess.run(
                    ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                import re

                m = re.search(r"(\d+)%", r.stdout)
                return int(m.group(1)) if m else 100
            elif self._audio_backend == "amixer":
                r = subprocess.run(
                    ["amixer", "get", "Master"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                import re

                m = re.search(r"(\d+)%", r.stdout)
                return int(m.group(1)) if m else 100
        except Exception:
            pass
        return 100

    def set_system_volume(self, percent: int) -> None:
        """Set system volume (0-100)."""
        if not self._audio_backend:
            return
        pct = max(0, min(100, int(percent)))
        try:
            if self._audio_backend == "wpctl":
                subprocess.run(
                    ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{pct / 100:.2f}"],
                    check=False,
                    timeout=2,
                )
            elif self._audio_backend == "pactl":
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"],
                    check=False,
                    timeout=2,
                )
            elif self._audio_backend == "amixer":
                subprocess.run(
                    ["amixer", "set", "Master", f"{pct}%"],
                    check=False,
                    timeout=2,
                )
        except Exception as e:
            logging.warning(f"Failed to set system volume: {e}")

    def _generate_qr(self) -> None:
        """Generate a high-res QR code for the MPV overlay screen.

        Uses box_size=10 so the source image is large enough that MPV
        downscales it rather than upscaling, keeping it crisp.
        """
        from pikaraoke.lib.get_platform import get_temp_directory

        qr_path = os.path.join(get_temp_directory(), "qrcode_mpv.png")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(self._server_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_path)
        self._qr_code_path = qr_path
