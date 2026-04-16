"""MPV subprocess lifecycle and IPC controller."""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from typing import Callable

import qrcode
from PIL import Image

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


def _semiround(val: float, decimals: int = 4) -> float:
    """Round to avoid floating-point noise in filter strings."""
    return round(val, decimals)


class MpvController:
    """Thin wrapper around an MPV subprocess and its JSON IPC socket.

    Manages MPV lifecycle, sends commands, queries properties, and keeps
    a poll thread running that updates state properties. Does not contain
    business logic -- PlaybackController orchestrates.
    """

    def __init__(self, ipc_socket_path: str = "/tmp/mpv-pikaraoke") -> None:
        self._mpv_proc: subprocess.Popen | None = None
        self._ipc_socket_path = ipc_socket_path
        self.is_running = False

        # State updated by poll thread (read by PlaybackController)
        self.position: float = 0.0
        self.duration: float = 0.0
        self.is_idle: bool = True
        self.is_paused: bool = False

        # Poll thread
        self._poll_thread: threading.Thread | None = None
        self._poll_stop = threading.Event()

        # Overlay persistent socket
        self._overlay_sock: socket.socket | None = None
        self._overlay_sock_lock = threading.Lock()

        # Playback filter state (needed for live rebuild)
        self._current_pitch: float = 1.0
        self._current_normalization_db: float | None = None

        # Audio backend
        self._audio_backend: str | None = None

        # Overlay manager and state provider
        self._overlay_manager = OverlayManager(self)
        self._overlay_state_provider: Callable[[], OverlayState] | None = None
        self._screen_mode: ScreenMode = ScreenMode.IDLE

        # Preferences -- set by Karaoke before calling start()
        self._preferences = None  # PreferenceManager, set by Karaoke.__init__

        # Paths -- set by Karaoke before calling start()
        self._placeholder_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "static", "images", "placeholder.png"
        )
        self._qr_code_path: str | None = None
        self._server_url: str = ""

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def set_overlay_state_provider(self, provider: Callable[[], OverlayState]) -> None:
        """Register a callable that builds the current OverlayState each tick.

        Called once by Karaoke during wiring. The provider is invoked each poll
        cycle and on mode changes to get a fresh snapshot of playback + prefs.
        """
        self._overlay_state_provider = provider

    def start(self) -> None:
        """Launch MPV in idle mode, start poll thread, load placeholder."""
        mpv_binary = shutil.which("mpv")
        if not mpv_binary:
            raise RuntimeError(
                "MPV binary not found. Install MPV (apt install mpv / brew install mpv) and retry."
            )

        # Remove stale IPC socket
        if os.path.exists(self._ipc_socket_path):
            try:
                os.unlink(self._ipc_socket_path)
            except OSError:
                pass

        cmd = [
            mpv_binary,
            "--idle",
            "--force-window",
            "--image-display-duration=inf",
            f"--input-ipc-server={self._ipc_socket_path}",
            "--no-terminal",
            "--osd-margin-x=0",
            "--osd-margin-y=0",
            "--hwdec=auto",
        ]

        logging.info("Starting MPV...")
        self._mpv_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Poll for IPC socket readiness (max 5s)
        for _ in range(50):
            if os.path.exists(self._ipc_socket_path):
                break
            time.sleep(0.1)
        else:
            self._mpv_proc.kill()
            self._mpv_proc = None
            raise RuntimeError("MPV failed to create IPC socket within 5 seconds")

        # Generate high-res QR for the playback screen
        self._generate_qr()

        # Load placeholder, apply SRT style
        self.load_placeholder()
        self.apply_srt_style()

        # Detect audio backend
        try:
            self._audio_backend = self._detect_audio_backend()
        except RuntimeError:
            logging.warning("No audio server found (wpctl/pactl/amixer). Volume controls disabled.")
            self._audio_backend = None

        self._poll_stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        self.is_running = True
        logging.info("MPV started successfully")

    def quit(self) -> None:
        """Stop poll thread, close overlay socket, send quit command, clean up."""
        self.is_running = False
        self._poll_stop.set()

        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2)

        self._close_overlay_sock()

        if self._mpv_proc:
            try:
                self.send_command({"command": ["quit"]})
                self._mpv_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._mpv_proc.kill()
            except Exception:
                pass
            self._mpv_proc = None

        if os.path.exists(self._ipc_socket_path):
            try:
                os.unlink(self._ipc_socket_path)
            except OSError:
                pass

        logging.info("MPV stopped")

    # ── IPC ────────────────────────────────────────────────────────────────────

    def send_command(self, cmd: dict) -> None:
        """Fire-and-forget JSON command to MPV via a transient socket."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self._ipc_socket_path)
                s.sendall(json.dumps(cmd).encode() + b"\n")
                s.settimeout(0.5)
                try:
                    s.recv(4096)
                except socket.timeout:
                    pass
        except (ConnectionRefusedError, OSError) as e:
            logging.debug(f"MPV IPC send_command failed: {e}")

    def query_property(self, name: str):
        """Query a property and return its value (or None on failure)."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self._ipc_socket_path)
                s.sendall(json.dumps({"command": ["get_property", name]}).encode() + b"\n")
                s.settimeout(1.0)
                resp = s.recv(4096).decode()
                data = json.loads(resp)
                return data.get("data")
        except (ConnectionRefusedError, OSError, json.JSONDecodeError, socket.timeout):
            return None

    def set_property(self, name: str, value) -> None:
        """Set a property on the running MPV instance."""
        self.send_command({"command": ["set_property", name, value]})

    # ── Playback ───────────────────────────────────────────────────────────────

    def play(
        self,
        file_path: str,
        semitones: int = 0,
        subtitle_path: str | None = None,
        subtitle_delay: float = 0.0,
        normalization_db: float | None = None,
    ) -> None:
        """Load a file and start playback with pitch/normalization/subtitles."""
        pitch_multiplier = 2 ** (semitones / 12)
        self._current_pitch = pitch_multiplier
        self._current_normalization_db = normalization_db

        # Load the file
        self.send_command({"command": ["loadfile", file_path]})

        # Wait for duration > 0 (max 5s)
        for _ in range(25):
            dur = self.query_property("duration")
            if dur is not None and float(dur) > 0:
                break
            time.sleep(0.2)

        # Build and apply lavfi-complex filter
        filter_str = self.build_filter(pitch_multiplier, normalization_db)
        self.set_property("lavfi-complex", filter_str)

        # Handle subtitles
        if subtitle_path and os.path.exists(subtitle_path):
            self.send_command({"command": ["sub-add", subtitle_path, "select"]})
            if subtitle_path.endswith(".srt") and subtitle_delay != 0:
                self.set_property("sub-delay", subtitle_delay)

        # Reset state then transition mode (triggers immediate overlay tick)
        self.position = 0.0
        self.is_idle = False
        self.is_paused = False
        self.duration = float(self.query_property("duration") or 0.0)
        self.set_mode(ScreenMode.PLAYING)

    def stop(self) -> None:
        """Stop playback: clear lavfi-complex, return to idle/placeholder."""
        self.set_property("lavfi-complex", "")
        self.position = 0.0
        self.duration = 0.0
        self.is_idle = True
        self.is_paused = False
        self.set_mode(ScreenMode.IDLE)

    def seek(self, position: float) -> None:
        """Seek to absolute position in seconds."""
        self.send_command({"command": ["seek", position, "absolute"]})

    def toggle_pause(self) -> None:
        """Toggle pause state via 'cycle pause'."""
        self.send_command({"command": ["cycle", "pause"]})
        self.is_paused = not self.is_paused

    def set_pitch(self, semitones: int) -> None:
        """Live mid-song pitch change: rebuild lavfi-complex with new pitch."""
        pitch_multiplier = 2 ** (semitones / 12)
        self._current_pitch = pitch_multiplier
        filter_str = self.build_filter(pitch_multiplier, self._current_normalization_db)
        self.set_property("lavfi-complex", filter_str)

    def set_subtitle_delay(self, seconds: float) -> None:
        """Set subtitle delay on running MPV."""
        self.set_property("sub-delay", seconds)

    def restart(self) -> None:
        """Seek to 0 and unpause."""
        self.seek(0)
        self.set_property("pause", False)

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

    # ── Filter Builder ─────────────────────────────────────────────────────────

    @staticmethod
    def build_filter(pitch: float, normalization_db: float | None = None) -> str:
        """Build the lavfi-complex string for single-stem playback.

        Chain: [aid1] -> rubberband(pitch) -> volume(normalization_db) -> [ao]
        """
        pitch = _semiround(pitch)
        if normalization_db is not None:
            norm_str = f"{normalization_db}dB"
            return (
                f"[aid1]rubberband@rb=pitch={pitch}"
                f":pitchq=quality"
                f":transients=crisp"
                f":detector=compound"
                f":phase=laminar"
                f":window=long"
                f":formant=preserved"
                f":channels=together"
                f":smoothing=off"
                f"[pre];[pre]volume={norm_str}[ao]"
            )
        return (
            f"[aid1]rubberband@rb=pitch={pitch}"
            f":pitchq=quality"
            f":transients=crisp"
            f":detector=compound"
            f":phase=laminar"
            f":window=long"
            f":formant=preserved"
            f":channels=together"
            f":smoothing=off"
            f"[ao]"
        )

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

    # ── Poll Thread ────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Background thread: query MPV state every 500ms and update overlays."""
        last_osd_w = None
        last_osd_h = None
        while not self._poll_stop.is_set():
            # Query MPV state
            pos = self.query_property("time-pos")
            if pos is not None:
                self.position = float(pos)

            dur = self.query_property("duration")
            if dur is not None:
                self.duration = float(dur)

            self.is_idle = self.query_property("idle-active") is True
            self.is_paused = self.query_property("pause") is True

            # Resize detection -- invalidate overlay cache so next tick re-renders all
            w = self.query_property("osd-width")
            h = self.query_property("osd-height")
            if w is not None and h is not None and (w != last_osd_w or h != last_osd_h):
                last_osd_w, last_osd_h = w, h
                self._overlay_manager.invalidate()

            self._tick_overlays()
            self._poll_stop.wait(0.5)

    # ── OSD primitives ─────────────────────────────────────────────────────────

    def _get_overlay_sock(self) -> socket.socket | None:
        """Return the persistent overlay socket, creating it if needed."""
        if self._overlay_sock is not None:
            return self._overlay_sock
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self._ipc_socket_path)
            return s
        except OSError:
            return None

    def _close_overlay_sock(self) -> None:
        """Close the persistent overlay socket."""
        with self._overlay_sock_lock:
            if self._overlay_sock is not None:
                try:
                    self._overlay_sock.close()
                except OSError:
                    pass
                self._overlay_sock = None

    def send_overlay_command(self, cmd: dict) -> None:
        """Send an overlay/OSD command over the persistent socket (with one reconnect retry)."""
        with self._overlay_sock_lock:
            for _ in range(2):
                s = self._overlay_sock or self._get_overlay_sock()
                if s is None:
                    return
                try:
                    payload = json.dumps(cmd).encode() + b"\n"
                    s.sendall(payload)
                    s.settimeout(1.0)
                    buf = b""
                    for _ in range(10):
                        try:
                            buf += s.recv(4096)
                        except socket.timeout:
                            break
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                msg = json.loads(line)
                                if "error" in msg or "request_id" in msg:
                                    self._overlay_sock = s
                                    return
                            except json.JSONDecodeError:
                                pass
                    self._overlay_sock = s
                    return
                except OSError:
                    try:
                        s.close()
                    except OSError:
                        pass
                    self._overlay_sock = None

    def send_osd(self, overlay_id: int, data: str, res_x: int = 1920, res_y: int = 1080) -> None:
        """Send an ASS event string to a specific OSD overlay slot."""
        self.send_overlay_command(
            {
                "command": {
                    "name": "osd-overlay",
                    "id": overlay_id,
                    "format": "ass-events",
                    "data": data,
                    "res_x": res_x,
                    "res_y": res_y,
                }
            }
        )

    def clear_osd(self, overlay_id: int, res_x: int = 1920, res_y: int = 1080) -> None:
        """Clear a specific OSD overlay slot."""
        self.send_overlay_command(
            {
                "command": {
                    "name": "osd-overlay",
                    "id": overlay_id,
                    "format": "none",
                    "data": "",
                    "res_x": res_x,
                    "res_y": res_y,
                }
            }
        )

    def load_placeholder(self) -> None:
        """Load the placeholder image into the running MPV instance."""
        if os.path.exists(self._placeholder_path):
            self.send_command({"command": ["loadfile", self._placeholder_path]})

    def apply_srt_style(self) -> None:
        """Push SRT subtitle style properties to MPV."""
        for prop, val in SRT_STYLE.items():
            self.set_property(prop, val)

    def _generate_qr(self) -> None:
        """Generate a high-res QR code for the MPV overlay screen.

        Uses box_size=10 so the source image is large enough that MPV
        downscales it rather than upscaling, keeping it crisp.
        Saved separately from the web UI's small QR code.
        """
        from pikaraoke.lib.get_platform import get_temp_directory

        qr_path = os.path.join(get_temp_directory(), "qrcode_mpv.png")
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(self._server_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_path)
        self._qr_code_path = qr_path

    def remove_qr_bitmap(self) -> None:
        """Remove the QR bitmap overlay from MPV (overlay slot 0)."""
        self.send_overlay_command({"command": ["overlay-remove", 0]})

    def send_qr_bitmap(self, screen_h: int, screen_w: int = 1920) -> None:
        """Send the QR code BGRA bitmap to MPV overlay slot 0.

        Called by OverlayManager when visibility or screen size changes.
        """
        qr_path = self._qr_code_path
        if not qr_path or not os.path.exists(qr_path):
            return

        qr_h = max(120, screen_h // 6)
        qr_img = Image.open(qr_path).convert("RGBA").resize((qr_h, qr_h))
        # Convert RGBA -> BGRA for mpv overlay format
        r, g, b, a = qr_img.split()
        bgra = Image.merge("RGBA", (b, g, r, a))
        bgra_bytes = bgra.tobytes()

        from pikaraoke.lib.get_platform import get_temp_directory

        overlay_path = os.path.join(get_temp_directory(), "qr_overlay.bgra")
        with open(overlay_path, "wb") as f:
            f.write(bgra_bytes)

        self.send_overlay_command(
            {"command": ["overlay-add", 0, 0, 0, overlay_path, 0, "bgra", qr_h, qr_h, qr_h * 4]}
        )
