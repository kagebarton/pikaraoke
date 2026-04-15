"""Overlay state machine and renderer for MPV OSD.

Pipeline: OverlayState -> compute_overlays() -> diff -> MPV IPC.

Every trigger (poll tick, mode change, resize, preference toggle) funnels
through OverlayManager.apply(). Adding a new overlay means a new ID constant,
one _build_* function, and one branch in compute_overlays() -- nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pikaraoke.lib.mpv_controller import MpvController

# ── OSD ID constants ───────────────────────────────────────────────────────────
OSD_URL = 1
OSD_NOWPLAYING = 2
OSD_TIMECODE = 3
OSD_UPNEXT = 4
OSD_CLOCK = 5

ALL_OSD_IDS = (OSD_URL, OSD_NOWPLAYING, OSD_TIMECODE, OSD_UPNEXT, OSD_CLOCK)

# ── ASS style constants ────────────────────────────────────────────────────────
_URL_COLOR = "&HFFFFFF&"
_NOWPLAYING_COLOR = "&H507FFF&"
_TIMECODE_COLOR = "&HAAD5FF&"
_UPNEXT_COLOR = "&HB48246&"
_CLOCK_COLOR = "&HFFFFFF&"
_OVERLAY_STYLE = "\\bord3\\shad2\\3c&H000000&\\4c&H000000&\\4a&H80&"


class ScreenMode(Enum):
    IDLE = "idle"  # placeholder loaded; splash overlays visible
    PLAYING = "playing"  # video playing
    PAUSED = "paused"  # video paused


@dataclass(frozen=True)
class OverlayState:
    """Immutable snapshot of all data compute_overlays needs.

    Built once per render cycle by PlaybackController.build_overlay_state().
    """

    mode: ScreenMode
    now_playing_title: str | None
    up_next_title: str | None
    semitones: int
    position: float
    duration: float
    screen_w: int
    screen_h: int
    # preference snapshot
    hide_url: bool
    hide_now_playing: bool
    show_clock: bool
    server_url: str


@dataclass(frozen=True)
class Overlay:
    """Declarative description of one OSD text entry.

    Equality is used by OverlayManager to diff against the last-sent set,
    so unchanged overlays are never re-sent over IPC.
    """

    id: int
    anchor: str  # ASS anchor tag, e.g. "\\an7"
    pos: tuple[float, float]  # logical coords on 1920x1080 canvas
    font_size: int
    color: str
    text: str


# ── Pure helpers ───────────────────────────────────────────────────────────────


def _overlay_font_size(screen_h: int) -> int:
    qr_h = max(120, screen_h // 6)
    return qr_h // 3


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def render_ass(o: Overlay) -> str:
    """Render an Overlay to an ASS event string."""
    x, y = o.pos
    return f"{{{o.anchor}\\pos({x},{y})\\fs{o.font_size}{_OVERLAY_STYLE}\\c{o.color}}}{o.text}"


# ── Overlay builders ───────────────────────────────────────────────────────────


def _build_url_overlay(state: OverlayState, fs: int) -> Overlay:
    qr_h = max(120, state.screen_h // 6)
    x = (qr_h + 10) * 1920 / state.screen_w
    return Overlay(
        id=OSD_URL,
        anchor="\\an7",
        pos=(x, 0),
        font_size=fs,
        color=_URL_COLOR,
        text=state.server_url,
    )


def _build_nowplaying_overlay(state: OverlayState, fs: int) -> Overlay:
    return Overlay(
        id=OSD_NOWPLAYING,
        anchor="\\an9",
        pos=(1920, 0),
        font_size=fs,
        color=_NOWPLAYING_COLOR,
        text=f"Now Playing: {state.now_playing_title}",
    )


def _build_timecode_overlay(state: OverlayState, fs: int) -> Overlay:
    y = int(fs * 0.9)
    elapsed = _fmt_time(state.position)
    total = _fmt_time(state.duration)
    st_str = f"+{state.semitones}st" if state.semitones > 0 else f"{state.semitones}st"
    return Overlay(
        id=OSD_TIMECODE,
        anchor="\\an9",
        pos=(1920, y),
        font_size=fs - 15,
        color=_TIMECODE_COLOR,
        text=f"{elapsed} / {total} | Pitch: {st_str}",
    )


def _build_upnext_overlay(state: OverlayState, fs: int) -> Overlay:
    y = int(fs * 0.9) + int((fs - 10) * 1.05)
    return Overlay(
        id=OSD_UPNEXT,
        anchor="\\an9",
        pos=(1920, y),
        font_size=fs - 10,
        color=_UPNEXT_COLOR,
        text=f"Up Next: {state.up_next_title}",
    )


def _build_clock_overlay(state: OverlayState, fs: int) -> Overlay:
    clock_text = datetime.now().strftime("%I:%M %p").lstrip("0")
    return Overlay(
        id=OSD_CLOCK,
        anchor="\\an1",
        pos=(0, 1080),
        font_size=fs,
        color=_CLOCK_COLOR,
        text=clock_text,
    )


# ── Decision layer ─────────────────────────────────────────────────────────────


def compute_overlays(state: OverlayState) -> dict[int, Overlay]:
    """Return the set of overlays that should be visible for the given state.

    This is the only place show/hide rules live. To add a new overlay:
    1. Add its OSD_* constant and to ALL_OSD_IDS.
    2. Write a _build_* function.
    3. Add one branch here.
    """
    result: dict[int, Overlay] = {}
    fs = _overlay_font_size(state.screen_h)

    # ── Placeholder (IDLE) overlays ────────────────────────────────────────────
    if state.mode == ScreenMode.IDLE:
        pass  # placeholder-only overlays go here

    # ── Playback overlays ──────────────────────────────────────────────────────
    if state.mode in (ScreenMode.PLAYING, ScreenMode.PAUSED) and not state.hide_now_playing:
        if state.now_playing_title:
            result[OSD_NOWPLAYING] = _build_nowplaying_overlay(state, fs)
            result[OSD_TIMECODE] = _build_timecode_overlay(state, fs)

    # ── All-screen overlays ────────────────────────────────────────────────────
    if not state.hide_url:
        result[OSD_URL] = _build_url_overlay(state, fs)

    if state.up_next_title and not state.hide_now_playing:
        result[OSD_UPNEXT] = _build_upnext_overlay(state, fs)

    if state.show_clock:
        result[OSD_CLOCK] = _build_clock_overlay(state, fs)

    return result


# ── Diff & apply ───────────────────────────────────────────────────────────────


class OverlayManager:
    """Diffs desired overlays against last-sent and drives MpvController IPC.

    Keeps overlay re-sends to a minimum: an overlay whose Overlay value is
    unchanged since last apply() is silently skipped.
    """

    def __init__(self, mpv: MpvController) -> None:
        self._mpv = mpv
        self._last_sent: dict[int, Overlay] = {}
        self._last_bitmap_visible: bool | None = None
        self._last_bitmap_screen_h: int | None = None

    def apply(self, state: OverlayState) -> None:
        """Compute desired overlays and apply only the diff to MPV."""
        desired = compute_overlays(state)

        for oid in ALL_OSD_IDS:
            old = self._last_sent.get(oid)
            new = desired.get(oid)
            if new is None and old is not None:
                self._mpv.clear_osd(oid)
            elif new is not None and new != old:
                self._mpv.send_osd(oid, render_ass(new))

        self._last_sent = desired
        self._apply_qr(state)

    def invalidate(self) -> None:
        """Force the next apply() to re-send everything (used on resize)."""
        self._last_sent = {}
        self._last_bitmap_visible = None
        self._last_bitmap_screen_h = None

    def _apply_qr(self, state: OverlayState) -> None:
        """Redraw QR bitmap only when visibility or screen size changes."""
        visible = not state.hide_url
        if visible == self._last_bitmap_visible and state.screen_h == self._last_bitmap_screen_h:
            return
        if visible:
            self._mpv.send_qr_bitmap(state.screen_h, state.screen_w)
        else:
            self._mpv.remove_qr_bitmap()
        self._last_bitmap_visible = visible
        self._last_bitmap_screen_h = state.screen_h
