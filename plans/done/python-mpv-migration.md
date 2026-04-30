# Python-mpv Migration Plan

Model: Claude Sonnet 4.6

## Goal

Replace the raw IPC socket / subprocess architecture in `MpvController` with
`python-mpv` (libmpv bindings). This eliminates the subprocess spawn, JSON IPC
protocol, poll thread, and persistent overlay socket — replacing them with
direct libmpv calls and property observers.

The overlay system (`OverlayManager`), filter builder, volume control, and
`PlaybackController` orchestration layer remain structurally intact. Changes to
files outside `mpv_controller.py` are minimal and mechanical.

______________________________________________________________________

## Why python-mpv over raw IPC

| Concern | Raw IPC (current) | python-mpv |
|---|---|---|
| State updates | 500ms poll thread creating throwaway sockets | Property observers fire at native rate |
| Song-end detection | Poll `idle-active` every 500ms → up to 500ms latency | Observer callback fires instantly |
| Overlay scoping | `osd-overlay` / `overlay-add` scoped to socket connection → requires persistent socket with reconnect logic | Commands go through libmpv instance → no connection scoping |
| Duration readiness | Busy-wait loop (25 × 200ms) in `play()` | `threading.Event` set by `duration` observer |
| OSD size | Queried via `query_property` from PlaybackController | Observer-tracked, exposed as `osd_size` property |
| Code volume | ~320 lines of socket/subprocess plumbing | ~100 lines of python-mpv wiring |
| Error surface | Socket timeouts, stale sockets, reconnect races, JSON parse errors | `mpv.ShutdownError` + standard exceptions |

______________________________________________________________________

## Architecture (after migration)

```
                     PlaybackController
                           |
                     MpvController
                           |
                      mpv.MPV instance (libmpv via ctypes)
                           |
              ┌────────────┼────────────┐
              │            │            │
        observe_property  loadfile   command()
        callbacks         sub_add    osd-overlay
              │            │            │
              ▼            ▼            ▼
        _on_time_pos   playback     overlays
        _on_duration   control      (ASS + bitmap)
        _on_idle_active
        _on_osd_dim
```

State flow is now push-based: mpv pushes property changes → observer callbacks
update `MpvController` fields and fire application callbacks → no poll thread.

______________________________________________________________________

## Files Changed

| File | Scope |
|---|---|
| `pyproject.toml` | Add `python-mpv` dependency |
| `pikaraoke/lib/mpv_controller.py` | Major rewrite (this plan) |
| `pikaraoke/lib/playback_controller.py` | Replace `query_property` calls, remove `check_playback_ended` |
| `pikaraoke/karaoke.py` | Wire callbacks, remove `check_playback_ended` from run loop |
| `pikaraoke/lib/overlay_manager.py` | Rename `send_osd` → `osd_overlay` in apply() |
| `tests/unit/test_playback_controller.py` | Update mock, remove `check_playback_ended` tests |
| `tests/conftest.py` | Update `mock_mpv` fixture |

______________________________________________________________________

## Detailed Design

### 1. New dependency

```toml
# pyproject.toml [project] dependencies
"python-mpv>=1.0.7",
```

No `pyzmq` — that is prototype-only for dual-stem live filter params.

______________________________________________________________________

### 2. MpvController — new class structure

#### 2a. Constructor

```python
class MpvController:
    def __init__(self) -> None:
        self._player: mpv.MPV | None = None
        self._lock = threading.RLock()  # guards filter rebuilds
        self._duration_ready = threading.Event()  # set when duration > 0

        # Observer-tracked state (read by PlaybackController)
        self.position: float = 0.0
        self.duration: float = 0.0
        self.is_idle: bool = True
        self.is_paused: bool = False
        self.is_running: bool = False

        # OSD dimensions (coalesced from two observers)
        self._current_osd_dim: list[int | None] = [None, None]
        self._fired_osd_dim: tuple[int | None, int | None] = (None, None)
        self._last_tick_emit: float = 0.0

        # Playback filter state (needed for live rebuild)
        self._current_pitch: float = 1.0
        self._current_normalization_db: float | None = None

        # Callbacks — set via set_callbacks() before start()
        self._on_song_end: Callable[[], None] | None = None
        self._on_resize: Callable[[], None] | None = None
        self._on_tick: Callable[[], None] | None = None

        # Audio backend
        self._audio_backend: str | None = None

        # Overlay manager and state provider
        self._overlay_manager = OverlayManager(self)
        self._overlay_state_provider: Callable[[], OverlayState] | None = None
        self._screen_mode: ScreenMode = ScreenMode.IDLE

        # Paths
        self._placeholder_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "static",
            "images",
            "placeholder.png",
        )
        self._qr_code_path: str | None = None
        self._server_url: str = ""
        self._preferences = None
```

**What's removed vs current:**

- `_mpv_proc` (subprocess.Popen)
- `_ipc_socket_path`
- `_poll_thread`, `_poll_stop` (threading.Event for poll)
- `_overlay_sock`, `_overlay_sock_lock` (persistent socket)

**What's added vs current:**

- `_player` (mpv.MPV instance)
- `_lock` (RLock for filter rebuilds)
- `_duration_ready` (threading.Event)
- `_current_osd_dim`, `_fired_osd_dim` (observer-tracked OSD size)
- `_last_tick_emit` (throttle for time-pos → overlay tick)
- `_on_song_end`, `_on_resize`, `_on_tick` callbacks

#### 2b. `_safe` decorator

Wraps every public method (except `start`/`quit`) to catch `mpv.ShutdownError`
and log other exceptions without crashing:

```python
def _safe(method):
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except mpv.ShutdownError:
            return None
        except Exception:
            log.exception("MpvController.%s failed", method.__name__)
            return None

    wrapper.__name__ = method.__name__
    return wrapper
```

Applied to: `play`, `stop`, `seek`, `toggle_pause`, `set_pitch`,
`set_subtitle_delay`, `restart`, `load_placeholder`, `apply_srt_style`,
`osd_overlay`, `clear_osd`, `overlay_add`, `overlay_remove`,
`send_qr_bitmap`, `remove_qr_bitmap`.

**Not** applied to: `start`, `quit` (failures are fatal and must propagate),
`build_filter` (static, no player access), volume methods (subprocess-based).

#### 2c. `osd_size` property

```python
@property
def osd_size(self) -> tuple[int, int]:
    w, h = self._current_osd_dim
    return (int(w) if w else 1920, int(h) if h else 1080)
```

Returns the last observer-delivered dimensions. Safe to call from any thread
at any time — no IPC round-trip.

#### 2d. `duration_ready` property

```python
@property
def duration_ready(self) -> threading.Event:
    return self._duration_ready
```

Exposed so `play()` can `self._duration_ready.wait(timeout=5)` instead of
the current busy-wait loop.

______________________________________________________________________

### 3. Lifecycle methods

#### 3a. `set_callbacks(on_song_end, on_resize, on_tick)`

```python
def set_callbacks(
    self,
    on_song_end: Callable[[], None],
    on_resize: Callable[[], None],
    on_tick: Callable[[], None],
) -> None:
    self._on_song_end = on_song_end
    self._on_resize = on_resize
    self._on_tick = on_tick
```

Called by `Karaoke.__init__` after constructing `PlaybackController`, before
`start()`. Decouples MpvController from PlaybackController import.

#### 3b. `start()`

```python
def start(self) -> None:
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

    # Property observers
    p.observe_property("time-pos", self._on_time_pos)
    p.observe_property("duration", self._on_duration)
    p.observe_property("idle-active", self._on_idle_active)
    p.observe_property("pause", self._on_pause)
    p.observe_property("osd-width", self._on_osd_dim)
    p.observe_property("osd-height", self._on_osd_dim)

    # Keyboard bindings (mpv window)
    @p.on_key_press("f")
    def _toggle_fullscreen():
        p.fullscreen = not p.fullscreen

    # Generate QR, load placeholder, apply SRT style
    self._generate_qr()
    self.load_placeholder()
    self.apply_srt_style()

    # Detect audio backend
    try:
        self._audio_backend = self._detect_audio_backend()
    except RuntimeError:
        logging.warning("No audio server found. Volume controls disabled.")
        self._audio_backend = None

    self.is_running = True
    logging.info("MPV started successfully (python-mpv / libmpv)")
```

**What's removed vs current `start()`:**

- `shutil.which("mpv")` binary lookup
- `subprocess.Popen(cmd, ...)` spawn
- IPC socket path cleanup + readiness polling loop (50 × 100ms)
- Poll thread creation and start

**What's added:**

- `mpv.MPV(...)` constructor (replaces subprocess + 7 CLI flags)
- 6 `observe_property` calls (replaces entire poll thread)
- `on_key_press('f')` binding
- `observe_property("pause", ...)` — not in current code (pause was manually toggled)

#### 3c. `quit()`

```python
def quit(self) -> None:
    self.is_running = False
    p = self._player
    if p is not None:
        self._player = None
        try:
            p.quit(0)
            p.wait_for_shutdown()
        except Exception:
            pass
    logging.info("MPV stopped")
```

**What's removed vs current `quit()`:**

- Poll thread stop + join
- `_close_overlay_sock()`
- `send_command({"command": ["quit"]})` + subprocess wait/kill
- IPC socket file unlink

______________________________________________________________________

### 4. Observer callbacks

All observers run on python-mpv's event-dispatch thread. They must NOT call
blocking primitives (`wait_for_property`, `wait_for_event`). They MAY call
`player.command()` / set properties (libmpv serialises internally).

Each wraps its body in try/except to prevent a transient error from killing
the dispatch thread.

#### 4a. `_on_time_pos(name, value)`

```python
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
```

- Updates `self.position` on every callback (~60Hz from mpv)
- Throttles `_on_tick` to ~2Hz (every 500ms) to match current poll rate
- `_on_tick` triggers overlay timecode update + Socket.IO position broadcast

#### 4b. `_on_duration(name, value)`

```python
def _on_duration(self, _name, value):
    try:
        if value is not None and float(value) > 0:
            self.duration = float(value)
            self._duration_ready.set()
    except Exception:
        log.exception("_on_duration error")
```

- Sets `self.duration` and signals `_duration_ready`
- `play()` calls `_duration_ready.clear()` before `loadfile`, then
  `_duration_ready.wait(timeout=5)` before applying lavfi-complex

#### 4c. `_on_idle_active(name, value)`

```python
def _on_idle_active(self, _name, value):
    try:
        if value is True and not self.is_idle:
            self.is_idle = True
            if self._on_song_end:
                self._on_song_end()
    except Exception:
        log.exception("_on_idle_active error")
```

- Fires `_on_song_end` exactly once when mpv transitions to idle
- The `not self.is_idle` guard prevents double-fire (e.g. placeholder load)
- `play()` sets `self.is_idle = False` after loading a video

**Replaces:** `check_playback_ended()` in PlaybackController + its call in
`karaoke.py` run loop.

#### 4d. `_on_pause(name, value)`

```python
def _on_pause(self, _name, value):
    try:
        if value is not None:
            self.is_paused = bool(value)
    except Exception:
        log.exception("_on_pause error")
```

- New observer (not in current code). Removes the manual
  `self.is_paused = not self.is_paused` toggle that can drift.

#### 4e. `_on_osd_dim(name, value)`

```python
def _on_osd_dim(self, name, value):
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
```

- Coalesces two back-to-back callbacks (width, height) into one resize event
- Invalidates overlay cache so next tick re-renders all
- Fires `_on_resize` callback

**Replaces:** the poll loop's `query_property("osd-width")` / `osd-height`
comparison + `invalidate()` call.

______________________________________________________________________

### 5. Playback methods

All decorated with `@_safe`.

#### 5a. `play(file_path, semitones, subtitle_path, subtitle_delay, normalization_db)`

```python
@_safe
def play(
    self,
    file_path,
    semitones=0,
    subtitle_path=None,
    subtitle_delay=0.0,
    normalization_db=None,
):
    pitch = 2 ** (semitones / 12)
    self._current_pitch = pitch
    self._current_normalization_db = normalization_db

    # Signal that we're loading — prevents _on_idle_active from firing
    self.is_idle = False
    self.is_paused = False
    self.position = 0.0

    # Load and wait for duration
    self._duration_ready.clear()
    self._fired_osd_dim = (None, None)  # force overlay refresh
    self._player.loadfile(file_path)

    if not self._duration_ready.wait(timeout=5):
        log.warning("Duration not ready after 5s — proceeding anyway")

    # Apply lavfi-complex filter
    filter_str = self.build_filter(pitch, normalization_db)
    with self._lock:
        self._player.lavfi_complex = filter_str

    # Subtitles
    if subtitle_path and os.path.exists(subtitle_path):
        self._player.sub_add(subtitle_path, "select")
        if subtitle_path.endswith(".srt") and subtitle_delay != 0:
            self._player.sub_delay = float(subtitle_delay)

    self.duration = float(self._player.duration or 0.0)
    self.set_mode(ScreenMode.PLAYING)
```

**Key changes vs current:**

- `send_command({"command": ["loadfile", ...]})` → `self._player.loadfile(path)`
- Busy-wait loop → `self._duration_ready.wait(timeout=5)`
- `set_property("lavfi-complex", ...)` → `self._player.lavfi_complex = ...`
- `send_command({"command": ["sub-add", ...]})` → `self._player.sub_add(...)`
- `set_property("sub-delay", ...)` → `self._player.sub_delay = ...`
- Sets `self.is_idle = False` before `loadfile` to guard `_on_idle_active`

#### 5b. `stop()`

```python
@_safe
def stop(self):
    with self._lock:
        self._player.lavfi_complex = ""
    self._player.stop()
    self.position = 0.0
    self.duration = 0.0
    self.is_idle = True
    self.is_paused = False
    self.set_mode(ScreenMode.IDLE)
```

#### 5c. `seek(position)`

```python
@_safe
def seek(self, position: float):
    self._player.command("seek", position, "absolute")
```

#### 5d. `toggle_pause()`

```python
@_safe
def toggle_pause(self):
    self._player.cycle("pause")
    # is_paused updated by _on_pause observer — no manual flip
```

#### 5e. `set_pitch(semitones)`

```python
@_safe
def set_pitch(self, semitones: int):
    pitch = 2 ** (semitones / 12)
    self._current_pitch = pitch
    filter_str = self.build_filter(pitch, self._current_normalization_db)
    with self._lock:
        self._player.lavfi_complex = filter_str
```

#### 5f. `set_subtitle_delay(seconds)`

```python
@_safe
def set_subtitle_delay(self, seconds: float):
    self._player.sub_delay = float(seconds)
```

#### 5g. `restart()`

```python
@_safe
def restart(self):
    self._player.command("seek", 0, "absolute")
    self._player.pause = False
```

#### 5h. `load_placeholder()`

```python
@_safe
def load_placeholder(self):
    if os.path.exists(self._placeholder_path):
        self._player.loadfile(self._placeholder_path)
```

#### 5i. `apply_srt_style()`

```python
@_safe
def apply_srt_style(self):
    for prop, val in SRT_STYLE.items():
        setattr(self._player, prop.replace("-", "_"), val)
```

**Change:** `set_property(prop, val)` → `setattr(self._player, prop.replace("-", "_"), val)`.
python-mpv maps `prop_name` to `prop-name` via underscore-to-hyphen.

______________________________________________________________________

### 6. OSD / Overlay methods

All decorated with `@_safe`.

#### 6a. `osd_overlay(overlay_id, data, res_x, res_y)`

```python
@_safe
def osd_overlay(self, overlay_id: int, data: str, res_x: int = 1920, res_y: int = 1080):
    self._player.command(
        "osd-overlay",
        id=overlay_id,
        format="ass-events",
        data=data,
        res_x=res_x,
        res_y=res_y,
    )
```

**Replaces** the current `send_osd()` which builds a JSON dict, sends it over
the persistent socket, and parses the multi-line response. This is 3 lines
instead of ~40.

#### 6b. `clear_osd(overlay_id, res_x, res_y)`

```python
@_safe
def clear_osd(self, overlay_id: int, res_x: int = 1920, res_y: int = 1080):
    self._player.command(
        "osd-overlay",
        id=overlay_id,
        format="none",
        data="",
        res_x=res_x,
        res_y=res_y,
    )
```

#### 6c. `overlay_add(overlay_id, x, y, path, offset, fmt, w, h, stride)`

```python
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
):
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
```

#### 6d. `overlay_remove(overlay_id)`

```python
@_safe
def overlay_remove(self, overlay_id: int):
    self._player.command("overlay-remove", overlay_id)
```

______________________________________________________________________

### 7. Methods unchanged

These methods have no IPC dependency and remain as-is:

- `build_filter(pitch, normalization_db)` — static, pure string builder
- `_detect_audio_backend()` — static, subprocess-based
- `get_system_volume()` — subprocess calls to wpctl/pactl/amixer
- `set_system_volume(percent)` — subprocess calls to wpctl/pactl/amixer
- `_generate_qr()` — PIL/qrcode, writes to temp dir
- `set_overlay_state_provider(provider)` — stores a callable
- `set_mode(mode)` — screen mode transition + overlay tick
- `_tick_overlays()` — builds OverlayState snapshot, hands to OverlayManager

______________________________________________________________________

### 8. Methods deleted

| Method | Reason |
|---|---|
| `send_command(cmd)` | Replaced by direct python-mpv API calls |
| `query_property(name)` | Replaced by observer-tracked fields + `osd_size` |
| `set_property(name, value)` | Replaced by property assignment on `_player` |
| `_poll_loop()` | Replaced by observer callbacks |
| `_get_overlay_sock()` | No persistent socket needed |
| `_close_overlay_sock()` | No persistent socket needed |
| `send_overlay_command(cmd)` | Replaced by `_player.command(...)` |
| `send_osd(overlay_id, data, ...)` | Renamed/replaced by `osd_overlay(...)` |
| `send_qr_bitmap(screen_h, screen_w)` | Rewritten to use `overlay_add(...)` |
| `remove_qr_bitmap()` | Rewritten to use `overlay_remove(...)` |

______________________________________________________________________

### 9. OverlayManager changes

[overlay_manager.py:228-230](pikaraoke/lib/overlay_manager.py#L228-L230) — The
`apply()` method calls `self._mpv.send_osd(...)` and `self._mpv.clear_osd(...)`.

- `send_osd` → rename to `osd_overlay` (matches python-mpv naming and prototype)
- `clear_osd` — name stays the same, implementation changes internally

```python
# overlay_manager.py apply() — only change is method name
elif new is not None and new != old:
    self._mpv.osd_overlay(oid, render_ass(new))    # was: send_osd
```

`_apply_qr()` calls `self._mpv.send_qr_bitmap(...)` and
`self._mpv.remove_qr_bitmap()`. The `send_qr_bitmap` method is rewritten
internally in MpvController to use `overlay_add()` but the signature stays
the same — **no change needed in OverlayManager**.

______________________________________________________________________

### 10. PlaybackController changes

#### 10a. `build_overlay_state()` — replace query_property

[playback_controller.py:269-270](pikaraoke/lib/playback_controller.py#L269-L270):

```python
# Before
screen_w = (int(self.mpv.query_property("osd-width") or 1920),)
screen_h = (int(self.mpv.query_property("osd-height") or 1080),)

# After
screen_w = (self.mpv.osd_size[0],)
screen_h = (self.mpv.osd_size[1],)
```

#### 10b. `pause()` — remove manual state read

[playback_controller.py:214-215](pikaraoke/lib/playback_controller.py#L214-L215):

```python
# Before
self.mpv.toggle_pause()
is_now_paused = self.mpv.is_paused

# After — same code, but is_paused is now observer-driven (always accurate)
self.mpv.toggle_pause()
is_now_paused = self.mpv.is_paused
```

No code change needed here; the observer makes `is_paused` reliably accurate.

#### 10c. Delete `check_playback_ended()`

[playback_controller.py:285-293](pikaraoke/lib/playback_controller.py#L285-L293)
— entirely removed. Song-end is now detected by `_on_idle_active` observer →
`_on_song_end` callback → `PlaybackController.end_song(reason="complete")`.

______________________________________________________________________

### 11. Karaoke wiring changes

#### 11a. Wire callbacks before start

[karaoke.py:189-199](pikaraoke/karaoke.py#L189-L199):

```python
# Before
self.mpv_controller = MpvController()
self.mpv_controller._server_url = self.url
self.mpv_controller._preferences = self.preferences
self.mpv_controller.start()

# After
self.mpv_controller = MpvController()
self.mpv_controller._server_url = self.url
self.mpv_controller._preferences = self.preferences

# PlaybackController must exist before wiring callbacks
self.playback_controller = PlaybackController(...)


# Wire song-end callback through PlaybackController
def _on_song_end():
    with self.playback_controller._playback_lock:
        self.playback_controller.end_song(reason="complete")


self.mpv_controller.set_callbacks(
    on_song_end=_on_song_end,
    on_resize=lambda: self.mpv_controller._tick_overlays(),
    on_tick=lambda: self.mpv_controller._tick_overlays(),
)

self.mpv_controller.start()
```

**Ordering concern:** Currently `MpvController.start()` is called before
`PlaybackController` is constructed. With python-mpv, `start()` registers
observers that fire callbacks into `PlaybackController`. Two options:

1. Construct `PlaybackController` first, then wire callbacks and call `start()`.
2. Use `set_callbacks()` (lazy binding) — callbacks are `None` until wired,
   observers silently skip if callback is None.

Option 2 is simpler because it doesn't require reordering the init sequence.
Observers that fire before callbacks are wired just see `None` and skip.

#### 11b. Remove `check_playback_ended` from run loop

[karaoke.py:591](pikaraoke/karaoke.py#L591):

```python
# Delete this line:
self.playback_controller.check_playback_ended()
```

Song-end detection is now instant via the `_on_idle_active` observer.

#### 11c. Simplify run loop

The run loop still needs `broadcast_position` and queue processing, but the
position broadcast can also move into the `_on_tick` callback:

```python
def run(self) -> None:
    ...
    while self.running:
        try:
            # Clean up if playback ended but state wasn't reset
            if (
                not self.playback_controller.is_playing
                and self.playback_controller.now_playing is not None
            ):
                self.reset_now_playing()

            # Broadcast position to remote UI clients
            self.playback_controller.broadcast_position(self.socketio)

            # Start next song from queue if not currently playing
            if self.queue_manager.queue and not self.playback_controller.is_playing:
                ...  # existing splash_delay + play logic

            self.handle_run_loop()
        except KeyboardInterrupt:
            ...
```

______________________________________________________________________

### 12. send_qr_bitmap / remove_qr_bitmap rewrite

Current implementation builds BGRA bytes, writes to file, sends via
`send_overlay_command` (persistent socket). New version does the same byte
prep but calls `overlay_add` / `overlay_remove` directly:

```python
@_safe
def send_qr_bitmap(self, screen_h: int, screen_w: int = 1920) -> None:
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
    self.overlay_remove(0)
```

______________________________________________________________________

### 13. Thread safety model

| Thread | What it does | Safe operations |
|---|---|---|
| Flask request threads | Call public MpvController methods | `_player.command()`, property sets, `_player.loadfile()` — all safe (libmpv serialises internally) |
| python-mpv event thread | Runs observer callbacks | May call `_player.command()` / set properties. Must NOT call `wait_for_property` / `wait_for_event` (deadlock) |
| `_on_tick` / `_on_resize` | Called from event thread | Calls `_tick_overlays()` → `OverlayManager.apply()` → `osd_overlay` / `clear_osd` — safe |
| `_on_song_end` | Called from event thread | Calls `PlaybackController.end_song()` — acquires `_playback_lock`, then calls `mpv.stop()` — safe |

The `_lock` (RLock) in MpvController guards only lavfi-complex rebuilds
(`play`, `stop`, `set_pitch`) to prevent interleaved filter string writes.

______________________________________________________________________

### 14. Test changes

#### 14a. `tests/conftest.py` — mock_mpv fixture

```python
class MockMpv:
    position: float = 0.0
    duration: float = 0.0
    is_idle: bool = True
    is_paused: bool = False
    is_running: bool = True
    _server_url: str = "http://localhost:5555"
    _screen_mode = ScreenMode.IDLE

    @property
    def osd_size(self) -> tuple[int, int]:
        return (1920, 1080)

    def play(self, *a, **kw):
        pass

    def stop(self):
        pass

    def seek(self, pos):
        pass

    def toggle_pause(self):
        pass

    def set_pitch(self, st):
        pass

    def set_subtitle_delay(self, s):
        pass

    def restart(self):
        pass

    def set_mode(self, mode):
        pass

    def _tick_overlays(self):
        pass

    def set_overlay_state_provider(self, p):
        pass

    def osd_overlay(self, *a, **kw):
        pass

    def clear_osd(self, *a, **kw):
        pass
```

**Removed:** `query_property`, `send_command`, `set_property`,
`send_overlay_command`, `send_osd`, `check_playback_ended`.

#### 14b. `tests/unit/test_playback_controller.py`

- Delete `test_check_playback_ended` and `test_check_playback_ended_not_idle`
- Update `test_build_overlay_state` if it references `query_property`
- Verify `test_pause` still works (is_paused is now observer-driven but mock
  can still set it directly)

______________________________________________________________________

### 15. Migration sequence

Execute in this order to keep tests passing at each step:

1. **Add `python-mpv` to pyproject.toml** and install in `pik` env
2. **Rewrite `mpv_controller.py`** with all sections above
3. **Update `overlay_manager.py`** — rename `send_osd` → `osd_overlay` call
4. **Update `playback_controller.py`** — replace `query_property`, delete `check_playback_ended`
5. **Update `karaoke.py`** — wire callbacks, remove `check_playback_ended` from loop
6. **Update test fixtures** — `conftest.py` mock_mpv, delete stale tests
7. **Run tests** — `python -m pytest`
8. **Manual smoke test** — start app, play a song, verify overlays/pause/skip/pitch

______________________________________________________________________

### 16. Risk areas

| Risk | Mitigation |
|---|---|
| `_on_idle_active` fires during `loadfile` (placeholder → video transition) | `self.is_idle = False` set before `loadfile` in `play()` — observer checks `not self.is_idle` |
| Observer callback crashes kill the dispatch thread | Every callback wraps body in try/except + log |
| `_on_song_end` acquires `_playback_lock` on event thread | RLock is reentrant; no other blocking call on event thread |
| `lavfi_complex` assignment during filter rebuild races with another thread | `self._lock` (RLock) guards all lavfi-complex writes |
| `_duration_ready.wait(5)` times out | Log warning, proceed — duration will arrive later via observer |
| python-mpv not installed | `import mpv` fails at module load — clear error message |
