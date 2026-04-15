Model: Claude Opus 4.6

# Overlay Architecture Refactor

## Problem

Overlay show/hide logic is scattered across `MpvController`:

- Each overlay has a bespoke `send_*_overlay` method that conditionally clears itself based on data truthiness.
- `_poll_loop` re-implements the same show/hide rules twice: once on the main cadence and again in the resize branch.
- `start()`, `stop()`, and `play()` each do partial overlay setup/teardown.
- `clear_all_overlays()` enumerates IDs independently of the poll-loop rules.
- There is no explicit "idle vs. playing" screen state — it's inferred ad-hoc from `is_idle` / `is_playing` / the `_get_now_playing()` callback.

Adding a new overlay (e.g. the clock) requires edits to at least five places. Changing one rule (e.g. "timecode visible only while playing") risks drift between paths.

## Goal

One pipeline: **state → desired overlays → diff → MPV**. Every trigger (poll tick, resize, mode change, preference change) funnels through the same render. Adding a new overlay becomes a single entry in one function.

## Scope

- Refactor `pikaraoke/lib/mpv_controller.py` overlay handling.
- Introduce a new `pikaraoke/lib/overlay_manager.py` module.
- Minor adjustments in `pikaraoke/lib/playback_controller.py` (mode transitions replace individual overlay callbacks).
- No changes to `preference_manager`, routes, or templates.
- No behavioral changes from the user's POV — overlays still look/behave the same. Pure internal restructure.

## Data Structures

### `ScreenMode` (enum)

Location: `pikaraoke/lib/overlay_manager.py`

```python
class ScreenMode(Enum):
    IDLE    = "idle"     # placeholder image loaded, splash overlays visible
    PLAYING = "playing"  # video loaded, playing
    PAUSED  = "paused"   # video loaded, paused
```

`PLAYING` and `PAUSED` are distinct so overlays can (optionally, later) react to pause. For now they produce identical overlays.

### `OverlayState` (dataclass, frozen)

Location: `pikaraoke/lib/overlay_manager.py`

Pure data — everything `compute_overlays` needs to make its decisions. `MpvController` fills this in each tick.

```python
@dataclass(frozen=True)
class OverlayState:
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
```

Frozen so that `Overlay` equality (used by the diff) is stable and hashable.

### `Overlay` (dataclass, frozen)

Location: `pikaraoke/lib/overlay_manager.py`

Declarative description of one OSD entry. Knows nothing about *when* it should appear — only what it looks like.

```python
@dataclass(frozen=True)
class Overlay:
    id: int                       # OSD_URL, OSD_NOWPLAYING, ...
    anchor: str                   # ASS anchor tag, e.g. "\\an7"
    pos: tuple[float, float]      # logical coords in a 1920x1080 canvas
    font_size: int                # final ASS \fs value
    color: str                    # ASS color, e.g. "&HFFFFFF&"
    text: str                     # already-formatted display text
```

Equality comparison is what powers the diff: an overlay whose `Overlay` is unchanged since last tick is not re-sent. This eliminates IPC spam and the "update every cycle" behavior in today's poll loop.

### Overlay ID constants

Stay in `mpv_controller.py` (re-exported for `overlay_manager`):

```python
OSD_URL        = 1
OSD_NOWPLAYING = 2
OSD_TIMECODE   = 3
OSD_UPNEXT     = 4
OSD_CLOCK      = 5

ALL_OSD_IDS = (OSD_URL, OSD_NOWPLAYING, OSD_TIMECODE, OSD_UPNEXT, OSD_CLOCK)
```

QR image (`overlay-add`, bitmap) is **not** in `ALL_OSD_IDS` — bitmap overlays use a different IPC channel. Handled separately (see §Flow).

## New Module: `pikaraoke/lib/overlay_manager.py`

Pure functions + one class. No threading, no IPC — only data transforms and diff. This makes the logic trivially unit-testable.

### `compute_overlays(state: OverlayState) -> dict[int, Overlay]`

The **only** place show/hide logic lives.

```python
def compute_overlays(state: OverlayState) -> dict[int, Overlay]:
    result: dict[int, Overlay] = {}
    fs = _overlay_font_size(state.screen_h)

    # URL splash: visible in IDLE always, in PLAYING unless hidden
    if state.mode == ScreenMode.IDLE or not state.hide_url:
        result[OSD_URL] = _build_url_overlay(state, fs)

    # Now playing / timecode / up next: only while a song is loaded
    if state.mode in (ScreenMode.PLAYING, ScreenMode.PAUSED) and not state.hide_now_playing:
        if state.now_playing_title:
            result[OSD_NOWPLAYING] = _build_nowplaying_overlay(state, fs)
            result[OSD_TIMECODE]   = _build_timecode_overlay(state, fs)
        if state.up_next_title:
            result[OSD_UPNEXT] = _build_upnext_overlay(state, fs)

    # Clock: always honors preference regardless of mode
    if state.show_clock:
        result[OSD_CLOCK] = _build_clock_overlay(state, fs)

    return result
```

Each `_build_*` is a small pure function that returns an `Overlay`. They replace today's `send_*_overlay` methods but without the IPC side-effect — they just build the data.

### `render_ass(overlay: Overlay) -> str`

One function replacing five nearly identical ASS string builders:

```python
def render_ass(o: Overlay) -> str:
    x, y = o.pos
    return (
        f"{{{o.anchor}\\pos({x},{y})\\fs{o.font_size}"
        f"{_OVERLAY_STYLE}\\c{o.color}}}{o.text}"
    )
```

### `OverlayManager` (class)

Owns the last-sent snapshot and drives the diff. Takes an `mpv` reference for the IPC side-effects.

```python
class OverlayManager:
    def __init__(self, mpv: MpvController) -> None:
        self._mpv = mpv
        self._last_sent: dict[int, Overlay] = {}
        self._last_bitmap_key: tuple | None = None  # (screen_h,) for QR

    def apply(self, state: OverlayState) -> None:
        """Compute desired overlays for `state` and diff against what was last sent."""
        desired = compute_overlays(state)

        for oid in ALL_OSD_IDS:
            old = self._last_sent.get(oid)
            new = desired.get(oid)
            if new is None and old is not None:
                self._mpv.clear_osd(oid)
            elif new is not None and new != old:
                self._mpv.send_osd(oid, render_ass(new))

        self._last_sent = desired

        # QR bitmap is handled separately because it's a bitmap overlay
        self._apply_qr(state)

    def invalidate(self) -> None:
        """Force the next `apply()` to re-send everything (used on resize)."""
        self._last_sent = {}
        self._last_bitmap_key = None

    def _apply_qr(self, state: OverlayState) -> None:
        """Redraw QR bitmap only when screen size or visibility changes."""
        visible = (state.mode == ScreenMode.IDLE or not state.hide_url)
        key = (state.screen_h,) if visible else None
        if key == self._last_bitmap_key:
            return
        if visible:
            self._mpv.send_qr_bitmap(state.screen_h)
        # (mpv overlay-remove 0 omitted: the placeholder/video underneath covers it,
        # and the QR only matters on IDLE where it's always re-sent.)
        self._last_bitmap_key = key
```

Why the QR split: OSD text overlays go via `osd-overlay` (the diff path). The QR is a BGRA bitmap sent via `overlay-add`. They share no IPC machinery in MPV, so they share none here — but both funnel through the same `apply()` call.

## Changes to `MpvController`

### Remove

- `send_url_overlay`, `send_nowplaying_overlay`, `send_timecode_overlay`, `send_upnext_overlay`, `send_clock_overlay` (logic moves into `overlay_manager._build_*`).
- `send_qr_overlay` → rename to `send_qr_bitmap(screen_h: int)`, stripped of decision logic (just does the BGRA conversion and `overlay-add`).
- `clear_all_overlays` (diff handles it; if needed externally, `OverlayManager.apply(OverlayState(mode=IDLE, ...))` does it).
- `set_overlay_callbacks` and the four `_get_*` callback fields (`_get_now_playing`, `_get_up_next`, `_get_semitones`, `_is_playing`). Replaced by `set_overlay_state(...)`.
- The entire show/hide block in `_poll_loop` (the ~60 lines starting at [mpv_controller.py:450](pikaraoke/lib/mpv_controller.py#L450)).

### Keep / repurpose

- `send_osd`, `clear_osd`: low-level IPC primitives — unchanged, called by `OverlayManager`.
- `send_overlay_command`, `_overlay_sock` machinery: unchanged.
- `load_placeholder`, `play`, `stop`: become the sole surface for mode transitions.

### Add

```python
# New fields
self._screen_mode: ScreenMode = ScreenMode.IDLE
self._overlay_manager: OverlayManager  # constructed in __init__
self._overlay_state_provider: Callable[[], OverlayState] | None = None

def set_overlay_state_provider(self, provider: Callable[[], OverlayState]) -> None:
    """Register a callable that builds the current OverlayState.

    Called once by Karaoke during wiring. The provider is invoked each tick
    (and on mode changes) to get a fresh snapshot of playback + preference data.
    """
    self._overlay_state_provider = provider

def set_mode(self, mode: ScreenMode) -> None:
    """Transition the display mode. Single place where placeholder/video loading lives."""
    if mode == self._screen_mode:
        return
    prev = self._screen_mode
    self._screen_mode = mode
    if mode == ScreenMode.IDLE and prev != ScreenMode.IDLE:
        self.load_placeholder()
    # PLAYING/PAUSED do not loadfile here -- that's play()'s job, which
    # calls set_mode(PLAYING) *after* loadfile.
    self._tick_overlays()

def _tick_overlays(self) -> None:
    """Build an OverlayState and hand it to OverlayManager.apply()."""
    if self._overlay_state_provider is None:
        return
    state = self._overlay_state_provider()
    self._overlay_manager.apply(state)
```

### `_poll_loop` after refactor

Collapses to state-polling only. Overlay rendering becomes a single call.

```python
def _poll_loop(self) -> None:
    last_osd_w = last_osd_h = None
    while not self._poll_stop.is_set():
        # Query MPV state
        pos = self.query_property("time-pos")
        if pos is not None:
            self.position = float(pos)
        dur = self.query_property("duration")
        if dur is not None:
            self.duration = float(dur)
        self.is_idle   = self.query_property("idle-active") is True
        self.is_paused = self.query_property("pause") is True

        # Resize detection -> invalidate so next apply() re-sends everything
        w = self.query_property("osd-width")
        h = self.query_property("osd-height")
        if w is not None and h is not None and (w != last_osd_w or h != last_osd_h):
            last_osd_w, last_osd_h = w, h
            self._overlay_manager.invalidate()

        # Single render pass
        self._tick_overlays()

        self._poll_stop.wait(0.5)
```

One path, not three.

### `play()` / `stop()` simplifications

```python
def play(self, file_path, ...):
    ... existing loadfile / filter / subtitle logic ...
    self.is_idle = False
    self.is_paused = False
    self.set_mode(ScreenMode.PLAYING)  # triggers immediate overlay tick

def stop(self):
    self.set_property("lavfi-complex", "")
    self.position = 0.0
    self.duration = 0.0
    self.is_idle = True
    self.is_paused = False
    self.set_mode(ScreenMode.IDLE)     # loads placeholder, triggers overlay tick
```

No more `load_placeholder()` + `clear_all_overlays()` sprinkled through `stop()`. `set_mode(IDLE)` does both (the placeholder load is in `set_mode`; `clear_all_overlays` is replaced by the diff — when `compute_overlays(IDLE state)` returns no PLAYING overlays, the diff clears them).

## Changes to `PlaybackController`

Replace the four-callback wiring with a single state-provider hook.

### Remove from `Karaoke.__init__`

The `mpv_controller.set_overlay_callbacks(...)` call at [karaoke.py:268](pikaraoke/karaoke.py#L268).

### Add: `PlaybackController.build_overlay_state()`

```python
def build_overlay_state(self) -> OverlayState:
    """Snapshot all data compute_overlays needs into a single immutable record."""
    if self.is_playing:
        mode = ScreenMode.PAUSED if self.is_paused else ScreenMode.PLAYING
    else:
        mode = ScreenMode.IDLE

    return OverlayState(
        mode=mode,
        now_playing_title=self.now_playing,
        up_next_title=self._peek_up_next_title(),
        semitones=self.now_playing_transpose,
        position=self.mpv.position,
        duration=self.mpv.duration,
        screen_w=int(self.mpv.query_property("osd-width") or 1920),
        screen_h=int(self.mpv.query_property("osd-height") or 1080),
        hide_url=self.preferences.get_or_default("hide_url"),
        hide_now_playing=self.preferences.get_or_default("hide_now_playing_overlay"),
        show_clock=self.preferences.get_or_default("show_clock"),
        server_url=self._server_url,
    )
```

(`_peek_up_next_title()` is already accessible — `Karaoke` owns `queue_manager` and passed an up-next getter before; we just move that lookup into this snapshot helper, wiring the queue via a small callback as before.)

### Wire it up in `Karaoke.__init__`

Replace the `set_overlay_callbacks(...)` block with:

```python
self.mpv_controller.set_overlay_state_provider(
    self.playback_controller.build_overlay_state
)
```

### Trigger a tick on preference changes

Preference routes (info page toggles) currently just write the pref. They should also nudge the overlay pipeline so the change is visible within one render, not up to 500 ms later. Add a helper:

```python
# PlaybackController
def refresh_overlays(self) -> None:
    """Force an immediate overlay re-render. Safe to call from any thread."""
    self.mpv._tick_overlays()
```

Routes that toggle `hide_url`, `hide_now_playing_overlay`, `show_clock` call `karaoke.playback_controller.refresh_overlays()` after updating the preference. (This replaces nothing — today those toggles depend on the 500 ms poll to pick them up.)

## Flow Diagrams

### Startup

```
Karaoke.__init__
  -> MpvController(...)
  -> PlaybackController(..., mpv=mpv)
  -> mpv.set_overlay_state_provider(pc.build_overlay_state)
  -> mpv.start()
       -> spawn mpv subprocess
       -> load_placeholder()
       -> set_mode(IDLE)  [no-op transition; triggers initial tick]
           -> _tick_overlays()
               -> state = provider()  # ScreenMode.IDLE, no song, prefs snapshot
               -> overlay_manager.apply(state)
                   -> compute_overlays() -> {URL, (CLOCK if pref)}
                   -> diff vs {} -> send_osd(URL), send_osd(CLOCK)
                   -> _apply_qr() -> send_qr_bitmap()
```

### Song start

```
PlaybackController.play_file()
  -> mpv.play(file_path, ...)
       -> loadfile, wait for duration, apply lavfi-complex, sub-add
       -> set_mode(PLAYING)
           -> _tick_overlays()
               -> state.mode == PLAYING, title filled in
               -> compute_overlays -> {URL (unless hidden), NOWPLAYING, TIMECODE, UPNEXT?, CLOCK?}
               -> diff vs idle set -> add NOWPLAYING/TIMECODE/UPNEXT, remove nothing new
```

### Poll tick during playback

```
_poll_loop (every 500 ms)
  -> query time-pos / duration / idle / pause
  -> resize check -> invalidate() if dims changed
  -> _tick_overlays()
      -> provider() -> new OverlayState with updated position
      -> compute_overlays() -> TIMECODE text differs (elapsed seconds changed)
      -> diff -> send_osd(TIMECODE) only; NOWPLAYING/UPNEXT unchanged -> skipped
```

This is where the diff pays off most: today the poll loop re-sends *every* overlay every 500 ms; after the refactor, only the timecode (and clock, once per minute) actually goes over IPC.

### Preference toggle

```
POST /info/hide_url
  -> preferences.set(hide_url, True)
  -> playback_controller.refresh_overlays()
      -> mpv._tick_overlays()
          -> provider() -> new state with hide_url=True
          -> compute_overlays() -> URL dropped from result
          -> diff -> clear_osd(URL)
```

Sub-500ms response instead of waiting for the next poll tick.

### Song end

```
PlaybackController.end_song()
  -> mpv.stop()
      -> clear lavfi-complex
      -> is_idle=True, is_paused=False
      -> set_mode(IDLE)
          -> load_placeholder()
          -> _tick_overlays()
              -> compute_overlays(IDLE state) -> {URL, CLOCK?}
              -> diff -> clear_osd(NOWPLAYING/TIMECODE/UPNEXT)
```

No explicit `clear_all_overlays` call — falls out of the diff.

### Resize

```
_poll_loop detects osd-width/height change
  -> overlay_manager.invalidate()  # forget last_sent
  -> _tick_overlays()
      -> compute_overlays() -> same result structurally, but font size & positions
         depend on screen_h, so every Overlay compares != old
      -> diff -> send_osd(all visible overlays)
      -> _apply_qr() -> bitmap key changed -> send_qr_bitmap()
```

One path. The "resize" branch in today's poll loop disappears.

## Testing

New tests (`tests/unit/test_overlay_manager.py`) — pure unit tests, no MPV:

1. `compute_overlays` returns URL + CLOCK (when pref on) in IDLE mode.
2. `compute_overlays` omits URL when `hide_url=True` and mode is PLAYING.
3. `compute_overlays` always includes URL when mode is IDLE (splash screen rule), even if `hide_url=True`.
4. `compute_overlays` omits NOWPLAYING/TIMECODE/UPNEXT when mode is IDLE.
5. `compute_overlays` omits UPNEXT when `up_next_title is None`.
6. `compute_overlays` includes CLOCK iff `show_clock=True`, independent of mode.
7. `render_ass` produces the expected ASS string for a known `Overlay`.
8. `OverlayManager.apply` with unchanged state calls no `send_osd` on the second invocation.
9. `OverlayManager.apply` after a mode change sends only the *added* overlays and clears removed ones.
10. `OverlayManager.invalidate()` forces a full re-send on next `apply`.

Tests 8–10 use a fake `MpvController` that records calls.

Existing tests touching the old `send_*_overlay` methods or `set_overlay_callbacks` get updated to use `set_overlay_state_provider` + assertions against computed state, or deleted if they were testing the show/hide rules (which are now covered by the pure unit tests above).

## Migration Order

Implement in this sequence so the tree is working at every commit:

1. **Create `overlay_manager.py`**: `ScreenMode`, `OverlayState`, `Overlay`, `_build_*`, `compute_overlays`, `render_ass`, `OverlayManager`. Include the new unit tests. Not yet wired in.
2. **Add mode + manager + provider hook to `MpvController`**: `set_mode`, `_tick_overlays`, `set_overlay_state_provider`, `_overlay_manager = OverlayManager(self)`. Keep old `send_*_overlay` methods intact so nothing breaks yet.
3. **Switch wiring in `Karaoke.__init__`**: add `PlaybackController.build_overlay_state`, call `set_overlay_state_provider`. Remove `set_overlay_callbacks` call. Overlays now render via both paths — verify visually this is fine, the old poll-loop branch still runs but is now redundant.
4. **Replace `_poll_loop` overlay block** with the single `_tick_overlays()` call and resize invalidation. Update `play()` and `stop()` to call `set_mode(...)`. Delete the old per-overlay `send_*_overlay` methods and `set_overlay_callbacks` / `_get_*` fields and `clear_all_overlays`. Rename `send_qr_overlay` → `send_qr_bitmap`.
5. **Preference-toggle nudge**: add `PlaybackController.refresh_overlays()` and call it from the info routes that toggle overlay prefs.

Each step is independently reviewable; steps 1–2 are strictly additive.

## Non-Goals

- Animation or transitions between modes.
- Per-overlay positioning config in preferences.
- Handling of the bitmap QR through the same diff machinery as text OSDs (kept separate — not worth the generalization for one bitmap).
- Removing the 500 ms poll entirely (still needed for time-pos / idle detection).

## Success Criteria

- Adding a hypothetical new "battery indicator" overlay requires edits only to: the ID constant list, one `_build_battery_overlay` function, and one branch in `compute_overlays`. No changes to `_poll_loop`, `start`, `stop`, `play`, or any clear list.
- Toggling `hide_url`, `hide_now_playing_overlay`, or `show_clock` from the info page takes visible effect within one render cycle (bounded by `refresh_overlays` → immediate tick).
- The poll loop no longer re-sends an unchanged overlay over IPC every 500 ms (verified by counting `send_osd` calls under a stable state in a unit test against `OverlayManager`).
- All existing overlay behavior (positions, colors, font sizes, splash/url/QR/clock/now-playing/timecode/up-next) is visually unchanged.
