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
from datetime import datetime
from typing import Callable
import qrcode

from flask_babel import _
from PIL import Image

# ── OSD ID constants ───────────────────────────────────────────────────────────
OSD_URL = 1
OSD_NOWPLAYING = 2
OSD_TIMECODE = 3
OSD_UPNEXT = 4
OSD_CLOCK = 5

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

# Overlay text colors (ASS hex BB GG RR format)
_URL_COLOR = "&HFFFFFF&"
_NOWPLAYING_COLOR = "&H507FFF&"
_TIMECODE_COLOR = "&HAAD5FF&"
_UPNEXT_COLOR = "&HB48246&"
_CLOCK_COLOR = "&HFFFFFF&"

# Common ASS style tags for overlay text
_OVERLAY_STYLE = "\\bord3\\shad2\\3c&H000000&\\4c&H000000&\\4a&H80&"

_OVERLAY_MARGIN_TOP = 0
_OVERLAY_MARGIN_BOTTOM = 0


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

        # Overlay callbacks -- set by PlaybackController for data MpvController doesn't own
        self._get_now_playing: Callable[[], str | None] = lambda: None
        self._get_up_next: Callable[[], str | None] = lambda: None
        self._get_semitones: Callable[[], int] = lambda: 0
        self._is_playing: Callable[[], bool] = lambda: False

        # Preferences -- set by Karaoke before calling start()
        self._preferences = None  # PreferenceManager, set by Karaoke.__init__

        # Paths -- set by Karaoke before calling start()
        self._placeholder_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "static", "images", "placeholder.png"
        )
        self._qr_code_path: str | None = None
        self._server_url: str = ""

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def set_overlay_callbacks(
        self,
        get_now_playing: Callable[[], str | None],
        get_up_next: Callable[[], str | None],
        get_semitones: Callable[[], int],
        is_playing: Callable[[], bool],
    ) -> None:
        """Register callbacks for overlay data owned by PlaybackController.

        Args:
            get_now_playing: Returns current song display title.
            get_up_next: Returns next song display title (or None).
            get_semitones: Returns current transpose value.
            is_playing: Returns whether a song is actively playing.
        """
        self._get_now_playing = get_now_playing
        self._get_up_next = get_up_next
        self._get_semitones = get_semitones
        self._is_playing = is_playing

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
        self._mpv_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # Poll for IPC socket readiness (max 5s)
        for _ in range(50):
            if os.path.exists(self._ipc_socket_path):
                break
            time.sleep(0.1)
        else:
            self._mpv_proc.kill()
            self._mpv_proc = None
            raise RuntimeError("MPV failed to create IPC socket within 5 seconds")

        # Generate high-res QR for the playback screen (separate from the web UI's small QR)
        self._generate_qr()

        # Load placeholder, apply SRT style, start poll thread
        self.load_placeholder()
        self.apply_srt_style()

        # Show QR and URL overlays on idle screen
        self.send_qr_overlay()
        self.send_url_overlay()
        self.send_clock_overlay()

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

        # Re-send QR overlay after loading new file (loadfile clears bitmap overlays)
        self.send_qr_overlay()

        # Reset state
        self.position = 0.0
        self.is_idle = False
        self.is_paused = False
        self.duration = float(self.query_property("duration") or 0.0)

    def stop(self) -> None:
        """Stop playback: clear lavfi-complex, load placeholder, clear OSD."""
        self.set_property("lavfi-complex", "")
        self.load_placeholder()
        self.clear_all_overlays()
        self.position = 0.0
        self.duration = 0.0
        self.is_idle = True
        self.is_paused = False

    def seek(self, position: float) -> None:
        """Seek to absolute position in seconds."""
        self.send_command({"command": ["seek", position, "absolute"]})

    def toggle_pause(self) -> None:
        """Toggle pause state via 'cycle pause'."""
        self.send_command({"command": ["cycle", "pause"]})

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
                    capture_output=True, text=True, timeout=1,
                )
                import re
                m = re.search(r"(\d+(?:\.\d+)?)", r.stdout)
                return round(float(m.group(1)) * 100) if m else 100
            elif self._audio_backend == "pactl":
                r = subprocess.run(
                    ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                    capture_output=True, text=True, timeout=1,
                )
                import re
                m = re.search(r"(\d+)%", r.stdout)
                return int(m.group(1)) if m else 100
            elif self._audio_backend == "amixer":
                r = subprocess.run(
                    ["amixer", "get", "Master"],
                    capture_output=True, text=True, timeout=1,
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
                    check=False, timeout=2,
                )
            elif self._audio_backend == "pactl":
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"],
                    check=False, timeout=2,
                )
            elif self._audio_backend == "amixer":
                subprocess.run(
                    ["amixer", "set", "Master", f"{pct}%"],
                    check=False, timeout=2,
                )
        except Exception as e:
            logging.warning(f"Failed to set system volume: {e}")

    # ── Poll Thread ────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Background thread: query MPV state every 500ms and send overlays."""
        last_osd_w = None
        last_osd_h = None
        while not self._poll_stop.is_set():
            # Read overlay preferences each cycle so live changes take effect
            prefs = self._preferences
            hide_url = prefs.get_or_default("hide_url") if prefs else False
            hide_now_playing = prefs.get_or_default("hide_now_playing_overlay") if prefs else False
            show_clock = prefs.get_or_default("show_clock") if prefs else False

            # Query state
            pos = self.query_property("time-pos")
            if pos is not None:
                self.position = float(pos)

            dur = self.query_property("duration")
            if dur is not None:
                self.duration = float(dur)

            idle = self.query_property("idle-active")
            self.is_idle = idle is True

            paused = self.query_property("pause")
            self.is_paused = paused is True

            # Monitor OSD dimensions for resize
            resp_w = self.query_property("osd-width")
            resp_h = self.query_property("osd-height")
            cur_w = resp_w if resp_w is not None else None
            cur_h = resp_h if resp_h is not None else None

            if cur_w is not None and cur_h is not None:
                if cur_w != last_osd_w or cur_h != last_osd_h:
                    last_osd_w = cur_w
                    last_osd_h = cur_h
                    # Re-send all overlays on resize
                    if not hide_url:
                        self.send_qr_overlay()
                    if not hide_now_playing:
                        title = self._get_now_playing()
                        self.send_nowplaying_overlay(title)
                        if self._is_playing():
                            self.send_timecode_overlay(
                                self.position, self.duration, self._get_semitones()
                            )
                        up_next = self._get_up_next()
                        self.send_upnext_overlay(up_next)
                    if show_clock:
                        self.send_clock_overlay()

            # Update overlays every cycle
            if not hide_url:
                self.send_url_overlay()

            if not hide_now_playing:
                title = self._get_now_playing()
                self.send_nowplaying_overlay(title)
                if self._is_playing():
                    self.send_timecode_overlay(
                        self.position, self.duration, self._get_semitones()
                    )
                else:
                    self.clear_osd(OSD_TIMECODE)
                up_next = self._get_up_next()
                self.send_upnext_overlay(up_next)
            else:
                self.clear_osd(OSD_NOWPLAYING)
                self.clear_osd(OSD_TIMECODE)
                self.clear_osd(OSD_UPNEXT)

            if show_clock:
                self.send_clock_overlay()
            else:
                self.clear_osd(OSD_CLOCK)

            self._poll_stop.wait(0.5)

    # ── Overlay Methods ────────────────────────────────────────────────────────

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
        self.send_overlay_command({
            "command": {
                "name": "osd-overlay",
                "id": overlay_id,
                "format": "ass-events",
                "data": data,
                "res_x": res_x,
                "res_y": res_y,
            }
        })

    def clear_osd(self, overlay_id: int, res_x: int = 1920, res_y: int = 1080) -> None:
        """Clear a specific OSD overlay slot."""
        self.send_overlay_command({
            "command": {
                "name": "osd-overlay",
                "id": overlay_id,
                "format": "none",
                "data": "",
                "res_x": res_x,
                "res_y": res_y,
            }
        })

    def load_placeholder(self) -> None:
        """Load the placeholder image into the running MPV instance."""
        if os.path.exists(self._placeholder_path):
            self.send_command({"command": ["loadfile", self._placeholder_path]})

    def apply_srt_style(self) -> None:
        """Push SRT subtitle style properties to MPV."""
        for prop, val in SRT_STYLE.items():
            self.set_property(prop, val)

    @staticmethod
    def _osd_screen_h(osd_height_query_result) -> int:
        return osd_height_query_result if osd_height_query_result is not None else 1080

    @staticmethod
    def _overlay_font_size(screen_h: int) -> int:
        qr_h = max(120, screen_h // 6)
        return qr_h // 3

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

    def send_qr_overlay(self, url: str = "", qr_image_path: str = "") -> None:
        """Send the QR code bitmap as a persistent overlay via overlay-add."""
        qr_path = qr_image_path or self._qr_code_path
        if not qr_path or not os.path.exists(qr_path):
            return

        screen_h = self._osd_screen_h(self.query_property("osd-height"))
        screen_w = self.query_property("osd-width") or 1920
        qr_h = max(120, screen_h // 6)

        qr_img = Image.open(qr_path).convert("RGBA").resize((qr_h, qr_h))
        # Convert RGBA -> BGRA for mpv overlay format
        r, g, b, a = qr_img.split()
        bgra = Image.merge("RGBA", (b, g, r, a))
        bgra_bytes = bgra.tobytes()

        overlay_path = "/tmp/qr_overlay.bgra"
        with open(overlay_path, "wb") as f:
            f.write(bgra_bytes)

        self.send_overlay_command({
            "command": [
                "overlay-add", 0, 0, 0, overlay_path, 0, "bgra", qr_h, qr_h, qr_h * 4
            ]
        })

    def send_url_overlay(self, url: str = "") -> None:
        """Send the server URL text as an OSD overlay, positioned to the right of the QR image."""
        screen_h = self._osd_screen_h(self.query_property("osd-height"))
        screen_w = self.query_property("osd-width") or 1920
        qr_h = max(120, screen_h // 6)
        font_size = self._overlay_font_size(screen_h)

        url_text = url or self._server_url
        x = (qr_h + 10) * 1920 / screen_w
        y = _OVERLAY_MARGIN_TOP
        data = (
            f"{{\\an7\\pos({x},{y})\\fs{font_size}{_OVERLAY_STYLE}\\c{_URL_COLOR}}}{url_text}"
        )
        self.send_osd(OSD_URL, data)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m}:{s:02d}"

    def send_nowplaying_overlay(self, title: str) -> None:
        """Send 'Now Playing: <title>' line via osd-overlay."""
        if not title:
            self.clear_osd(OSD_NOWPLAYING)
            return
        screen_h = self._osd_screen_h(self.query_property("osd-height"))
        fs = self._overlay_font_size(screen_h)
        data = (
            f"{{\\an9\\pos(1920,{_OVERLAY_MARGIN_TOP})\\fs{fs}{_OVERLAY_STYLE}"
            f"\\c{_NOWPLAYING_COLOR}}}Now Playing: {title}"
        )
        self.send_osd(OSD_NOWPLAYING, data)

    def send_timecode_overlay(
        self, elapsed: float, total: float, semitones: int
    ) -> None:
        """Send elapsed/total time + pitch via osd-overlay."""
        screen_h = self._osd_screen_h(self.query_property("osd-height"))
        fs = self._overlay_font_size(screen_h)
        y = _OVERLAY_MARGIN_TOP + int(fs * 0.9)

        elapsed_str = self._fmt_time(elapsed)
        total_str = self._fmt_time(total)
        st_str = f"+{semitones}st" if semitones > 0 else f"{semitones}st"

        data = (
            f"{{\\an9\\pos(1920,{y})\\fs{fs - 15}{_OVERLAY_STYLE}"
            f"\\c{_TIMECODE_COLOR}}}{elapsed_str} / {total_str} | Pitch: {st_str}"
        )
        self.send_osd(OSD_TIMECODE, data)

    def send_upnext_overlay(self, next_title: str | None) -> None:
        """Send 'Up Next: <title>' via osd-overlay."""
        if not next_title:
            self.clear_osd(OSD_UPNEXT)
            return
        screen_h = self._osd_screen_h(self.query_property("osd-height"))
        fs = self._overlay_font_size(screen_h)
        y = _OVERLAY_MARGIN_TOP + int(fs * 0.9) + int((fs - 10) * 1.05)
        data = (
            f"{{\\an9\\pos(1920,{y})\\fs{fs - 10}{_OVERLAY_STYLE}"
            f"\\c{_UPNEXT_COLOR}}}Up Next: {next_title}"
        )
        self.send_osd(OSD_UPNEXT, data)

    def send_clock_overlay(self) -> None:
        """Send current time as an OSD overlay, bottom-left corner."""
        screen_h = self._osd_screen_h(self.query_property("osd-height"))
        fs = self._overlay_font_size(screen_h)
        y = 1080 - _OVERLAY_MARGIN_BOTTOM
        now = datetime.now()
        clock_text = now.strftime("%I:%M %p").lstrip("0")
        data = (
            f"{{\\an1\\pos(0,{y})\\fs{fs}{_OVERLAY_STYLE}"
            f"\\c{_CLOCK_COLOR}}}{clock_text}"
        )
        self.send_osd(OSD_CLOCK, data)

    def clear_all_overlays(self) -> None:
        """Clear all OSD overlays."""
        for overlay_id in [OSD_URL, OSD_NOWPLAYING, OSD_TIMECODE, OSD_UPNEXT, OSD_CLOCK]:
            self.clear_osd(overlay_id)
