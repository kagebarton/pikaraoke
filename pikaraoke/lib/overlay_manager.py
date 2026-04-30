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
OSD_QUEUE_PREVIEW = 6

ALL_OSD_IDS = (OSD_URL, OSD_NOWPLAYING, OSD_TIMECODE, OSD_UPNEXT, OSD_CLOCK, OSD_QUEUE_PREVIEW)

# ── ASS style constants ────────────────────────────────────────────────────────
# ASS colors are BGR: &HBBGGRR&
_COLOR_URL = "&HFFFFFF&"  # rgb(255,255,255) white
_COLOR_CLOCK = "&HFFFFFF&"  # rgb(255,255,255) white
_COLOR_NOWPLAYING = (
    "&H507FFF&"  # rgb(255,127,80)  orange — now-playing title, queue preview first row
)
_COLOR_UPNEXT = "&HB48246&"  # rgb(70,130,180)  blue   — upnext row, queue preview rest rows
_COLOR_TIMECODE = "&HAAD5FF&"  # rgb(255,213,170) light orange — timecode row, singer on orange rows
_COLOR_SINGER_BLUE = "&HFACD8C&"  # rgb(140,205,250) light blue  — singer name on blue rows
_OVERLAY_STYLE = "\\bord3\\shad2\\3c&H000000&\\4c&H000000&\\4a&H80&"


# ── OSD icon symbols ──────────────────────────────────────────────────────────
_ICON_PLAY = "▶"  # U+25B6
_ICON_CLEF = "𝄞"  # U+1D11E
_ICON_CLOCK = "🕐"  # U+1F550
_ICON_NEXT = "⏭"  # U+23ED
_ICON_MIC_SINGER = "🎙"  # U+1F399  condenser — matches web UI singer name
_ICON_MIC_VOCAL = "🗣️"  # U+1F32C  head exhale — vocal volume level


class ScreenMode(Enum):
    IDLE = "idle"  # placeholder loaded; splash overlays visible
    PLAYING = "playing"  # video playing
    PAUSED = "paused"  # video paused


@dataclass(frozen=True)
class QueuedSong:
    """Minimal queue entry consumed by overlays.

    Decoupled from the queue dict so overlay logic stays pure. The future
    "next N songs" overlay will receive a list of these.
    """

    title: str
    singer: str


@dataclass(frozen=True)
class OverlayState:
    """Immutable snapshot of all data compute_overlays needs.

    Built once per render cycle by PlaybackController.build_overlay_state().
    """

    mode: ScreenMode
    now_playing_title: str | None
    queue_preview: tuple[QueuedSong, ...]
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
    # dual-stem vocal volume (for timecode overlay)
    dual_stem: bool = False
    vocal_volume: float = 0.0
    singer_name: str = ""


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
        color=_COLOR_URL,
        text=state.server_url,
    )


def _build_nowplaying_overlay(state: OverlayState, fs: int) -> Overlay:
    return Overlay(
        id=OSD_NOWPLAYING,
        anchor="\\an9",
        pos=(1920, 0),
        font_size=fs,
        color=_COLOR_NOWPLAYING,
        text=f"{_ICON_PLAY} {state.now_playing_title}",
    )


def _build_timecode_overlay(state: OverlayState, fs: int) -> Overlay:
    y = int(fs * 0.9)
    elapsed = _fmt_time(state.position)
    total = _fmt_time(state.duration)
    st_str = f"+{state.semitones}st" if state.semitones > 0 else f"{state.semitones}st"
    text = f"{_ICON_MIC_SINGER} {state.singer_name} | {elapsed} / {total} | {_ICON_CLEF} {st_str}"
    if state.dual_stem:
        text += f" | {_ICON_MIC_VOCAL} {int(state.vocal_volume * 100)}%"
    return Overlay(
        id=OSD_TIMECODE,
        anchor="\\an9",
        pos=(1920, y),
        font_size=fs - 15,
        color=_COLOR_TIMECODE,
        text=text,
    )


def _build_upnext_overlay(state: OverlayState, fs: int) -> Overlay:
    y = int(fs * 0.9) + int((fs - 10) * 1.05)
    song = state.queue_preview[0]
    singer_part = f"{{\\c{_COLOR_SINGER_BLUE}}}{_ICON_MIC_SINGER} {song.singer}"
    return Overlay(
        id=OSD_UPNEXT,
        anchor="\\an9",
        pos=(1920, y),
        font_size=fs - 10,
        color=_COLOR_UPNEXT,
        text=f"{_ICON_NEXT} {song.title} {singer_part}",
    )


def _build_queue_preview_overlay(state: OverlayState, fs: int) -> Overlay:
    songs = state.queue_preview[:5]
    # First row: orange, singer in lighter orange
    singer1 = f"{{\\c{_COLOR_TIMECODE}}}{_ICON_MIC_SINGER} {songs[0].singer}"
    first = f"{_ICON_NEXT} {songs[0].title} {singer1}"
    # Remaining rows: blue, singer in lighter blue
    rest = [
        f"{i}. {s.title} {{\\c{_COLOR_SINGER_BLUE}}}{_ICON_MIC_SINGER} {s.singer}"
        for i, s in enumerate(songs[1:], 2)
    ]
    if rest:
        inline = f"{{\\c{_COLOR_UPNEXT}\\fs{fs - 10}}}"
        text = first + "\\N" + inline + "\\N".join(rest)
    else:
        text = first
    return Overlay(
        id=OSD_QUEUE_PREVIEW,
        anchor="\\an9",
        pos=(1920, 0),
        font_size=fs,
        color=_COLOR_NOWPLAYING,
        text=text,
    )


def _build_clock_overlay(state: OverlayState, fs: int) -> Overlay:
    clock_text = datetime.now().strftime("%I:%M %p").lstrip("0")
    return Overlay(
        id=OSD_CLOCK,
        anchor="\\an1",
        pos=(0, 1080),
        font_size=fs,
        color=_COLOR_CLOCK,
        text=f"{_ICON_CLOCK}{clock_text}",
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
        if state.queue_preview and not state.hide_now_playing:
            result[OSD_QUEUE_PREVIEW] = _build_queue_preview_overlay(state, fs)

    # ── Playback overlays ──────────────────────────────────────────────────────
    if state.mode in (ScreenMode.PLAYING, ScreenMode.PAUSED) and not state.hide_now_playing:
        if state.now_playing_title:
            result[OSD_NOWPLAYING] = _build_nowplaying_overlay(state, fs)
            result[OSD_TIMECODE] = _build_timecode_overlay(state, fs)
        if state.queue_preview:
            result[OSD_UPNEXT] = _build_upnext_overlay(state, fs)

    # ── All-screen overlays ────────────────────────────────────────────────────
    if not state.hide_url:
        result[OSD_URL] = _build_url_overlay(state, fs)

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
                self._mpv.osd_overlay(oid, render_ass(new))

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
