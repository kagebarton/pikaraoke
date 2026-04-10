# MPV Migration Implementation Plan

Model: Claude Opus 4.6

## Goal

Replace the FFmpeg-HLS-browser playback pipeline with MPV as the native playback
engine. Migrate only existing PiKaraoke features -- no new prototype-only features
(dual-stem vocal slider, file browser, subtitle mode selector). The web UI becomes
remote-only; the playback screen is a native MPV window.

---

## Design Decisions

These decisions were made before implementation and should not be revisited during
migration unless a blocking issue is discovered.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transpose | Live mid-song pitch change via `lavfi-complex` rebuild | MPV advantage; no song restart needed |
| Volume | System volume with audio server abstraction (`wpctl` / `pactl` / `amixer` fallback) | Avoids complicating the normalization filter chain with additional volume nodes |
| Normalization | Pre-computed dB from song database, applied as `volume=XdB` at end of filter chain | 1st-pass analysis done by `ProcessingManager` (not yet implemented); playback just applies the stored value |
| Pause state | Query MPV `pause` property each time | Always accurate; avoids state drift |
| IPC | Raw Unix socket with JSON protocol | `python-mpv` is not actively maintained |
| Overlay socket | Persistent socket (prototype pattern) | MPV scopes `overlay-add`/`osd-overlay` to the connection that created them; persistent socket is proven and simplest viable approach |
| Controller hierarchy | `PlaybackController` orchestrates; `MpvController` is a thin IPC/subprocess wrapper | MPV takes commands and reports status; business logic stays in `PlaybackController` |
| Poll thread | `MpvController` owns the poll thread; updates its own state properties | `PlaybackController` reads those properties on its own cycle and handles Socket.IO emission + song-end detection. Keeps `MpvController` free of Socket.IO/event dependencies. |
| Song-end detection | 500ms polling of `idle-active` | Acceptable latency; event-based `observe_property` can be added later |
| `splash_delay` | Keep configurable delay between songs | Pause on placeholder image between songs, same as current behavior |

---

## Architecture

```
QueueManager --> PlaybackController --> MpvController --> MPV subprocess
                      |                     |                  |
                      |                     |           IPC socket (JSON)
                      |                     |                  |
                      |                poll thread -----> reads time-pos,
                      |                (daemon)           duration, pause,
                      |                                   idle-active
                      |                                      |
                      |<---- reads mpv state properties -----+
                      |
                      +----> Socket.IO emit (playback_position, now_playing)
                      +----> EventSystem emit (playback_started, song_ended)
```

**`MpvController`** -- thin layer, no business logic:
- Manages MPV subprocess lifecycle (start, quit)
- Sends IPC commands (loadfile, seek, cycle pause, set_property, etc.)
- Queries IPC properties (time-pos, duration, pause, idle-active, osd-width/height)
- Owns poll thread that keeps `position`, `duration`, `is_idle`, `is_paused` fresh
- Manages persistent overlay socket for OSD overlays
- Builds `lavfi-complex` filter strings
- System volume via audio server abstraction (wpctl/pactl/amixer)

**`PlaybackController`** -- orchestrator, owns playback state:
- Owns `now_playing`, `now_playing_user`, `now_playing_filename`, etc.
- Calls `MpvController` methods for playback operations
- Detects song-end by reading `mpv.is_idle` (was playing, now idle)
- Emits events via `EventSystem`
- No direct IPC socket access

---

## New Module: `pikaraoke/lib/mpv_controller.py`

### Class: `MpvController`

```python
class MpvController:
    """Thin wrapper around an MPV subprocess and its JSON IPC socket.

    Manages MPV lifecycle, sends commands, queries properties, and keeps
    a poll thread running that updates state properties. Does not contain
    business logic -- PlaybackController orchestrates.
    """
```

#### Constructor

```python
def __init__(self, ipc_socket_path: str = "/tmp/mpv-socket") -> None:
```

State attributes:
```python
# Subprocess
self._mpv_proc: subprocess.Popen | None = None
self._ipc_socket_path: str
self.is_running: bool = False      # True after successful start(), False after quit()

# State updated by poll thread (read by PlaybackController)
self.position: float = 0.0        # time-pos
self.duration: float = 0.0        # duration
self.is_idle: bool = True          # idle-active
self.is_paused: bool = False       # pause property

# Poll thread
self._poll_thread: threading.Thread | None = None
self._poll_stop: threading.Event

# Overlay persistent socket
self._overlay_sock: socket.socket | None = None
self._overlay_sock_lock: threading.Lock

# Playback filter state (needed for live rebuild)
self._current_pitch: float = 1.0           # rubberband multiplier
self._current_normalization_db: float | None = None
```

#### Lifecycle Methods

```python
def start(self) -> None:
    """Launch MPV in idle mode, start poll thread, load placeholder.

    Raises RuntimeError if MPV binary is not found or fails to start.
    Sets self.is_running = True on success.

    MPV startup flags:
      mpv --idle --force-window --image-display-duration=inf
          --input-ipc-server={path} --no-terminal
          --osd-margin-x=0 --osd-margin-y=0
          --hwdec=auto

    --hwdec=auto enables hardware-accelerated decoding when available
    (critical for Raspberry Pi with 1080p video). Falls back to software
    decoding transparently if no hardware decoder is present.

    Startup sequence:
    1. Verify `mpv` binary exists (shutil.which)
    2. Remove stale IPC socket file if present
    3. Launch subprocess
    4. Poll for IPC socket readiness (max 5s)
    5. If socket never appears: kill process, raise RuntimeError
    6. Load placeholder, apply SRT style, start poll thread
    7. self.is_running = True
    """

def quit(self) -> None:
    """Stop poll thread, close overlay socket, send quit command, clean up.

    Sets self.is_running = False.
    """
```

#### IPC Methods

```python
def send_command(self, cmd: dict) -> None:
    """Fire-and-forget JSON command to MPV via a transient socket."""

def query_property(self, name: str) -> Any:
    """Query a property and return its value (or None on failure)."""
    # Wraps: {"command": ["get_property", name]}

def set_property(self, name: str, value: Any) -> None:
    """Set a property on the running MPV instance."""
    # Wraps: {"command": ["set_property", name, value]}
```

#### Playback Methods

```python
def play(
    self,
    file_path: str,
    semitones: int = 0,
    subtitle_path: str | None = None,
    subtitle_delay: float = 0.0,
    normalization_db: float | None = None,
) -> None:
    """Load a file and start playback with pitch/normalization/subtitles.

    Steps:
    1. send_command(loadfile, file_path)
    2. Wait for duration > 0 (max 5s poll)
    3. Build and apply lavfi-complex filter
    4. If subtitle_path: sub-add, apply SRT style if .srt, set sub-delay
    5. Update internal filter state (_current_pitch, etc.)
    """

def stop(self) -> None:
    """Stop playback: clear lavfi-complex, load placeholder, clear OSD."""

def seek(self, position: float) -> None:
    """Seek to absolute position in seconds."""
    # {"command": ["seek", position, "absolute"]}

def toggle_pause(self) -> None:
    """Toggle pause state via 'cycle pause'."""

def set_pitch(self, semitones: int) -> None:
    """Live mid-song pitch change: rebuild lavfi-complex with new pitch."""
    # Recalculate pitch multiplier: 2 ** (semitones / 12)
    # Rebuild filter with current _current_normalization_db and new pitch
    # set_property("lavfi-complex", new_filter)

def set_subtitle_delay(self, seconds: float) -> None:
    """Set subtitle delay on running MPV."""
    # set_property("sub-delay", seconds)

def restart(self) -> None:
    """Seek to 0 and unpause."""
    # seek 0 absolute, set_property("pause", False)
```

#### Volume Methods

System volume uses an audio server abstraction that detects the available
audio backend at startup and delegates accordingly. Detection order:
`wpctl` (PipeWire) -> `pactl` (PulseAudio) -> `amixer` (ALSA).

```python
def _detect_audio_backend(self) -> str:
    """Detect available audio backend. Called once during start().

    Returns 'wpctl', 'pactl', or 'amixer'.
    Raises RuntimeError if none found (logged as warning, volume
    controls disabled but playback continues).
    """
    # shutil.which("wpctl") -> "wpctl"
    # shutil.which("pactl") -> "pactl"
    # shutil.which("amixer") -> "amixer"

def get_system_volume(self) -> int:
    """Query system default sink volume as 0-100.

    Routes to the detected audio backend:
    - wpctl:  parse `wpctl get-volume @DEFAULT_AUDIO_SINK@`
    - pactl:  parse `pactl get-sink-volume @DEFAULT_SINK@`
    - amixer: parse `amixer get Master`
    Returns 100 on failure.
    """

def set_system_volume(self, percent: int) -> None:
    """Set system volume (0-100).

    Routes to the detected audio backend:
    - wpctl:  `wpctl set-volume @DEFAULT_AUDIO_SINK@ {pct/100:.2f}`
    - pactl:  `pactl set-sink-volume @DEFAULT_SINK@ {pct}%`
    - amixer: `amixer set Master {pct}%`
    Fails silently with a warning log on error.
    """
```

#### Filter Builder

```python
def build_filter(self, pitch: float, normalization_db: float | None = None) -> str:
    """Build the lavfi-complex string for single-stem playback.

    Chain: [aid1] -> rubberband(pitch) -> volume(normalization_db) -> [ao]

    Normalization is applied at the END of the chain as volume=XdB.
    If normalization_db is None, the volume node is omitted.
    """
```

This migration implements single-stem playback only (the current PiKaraoke
behavior). The prototype's dual-stem `build_filter` with `[aid2]`/`[aid3]`
mixing is reference code for a future feature -- do not add dual-stem state
or parameters until that feature is built.

#### Poll Thread

```python
def _poll_loop(self) -> None:
    """Background thread: query MPV state every 500ms.

    Updates: self.position, self.duration, self.is_idle, self.is_paused
    Also monitors osd-width/osd-height for resize -> re-sends overlays.
    """
```

#### Overlay Methods

Ported from prototype with same persistent-socket pattern:

```python
def send_overlay_command(self, cmd: dict) -> None:
def send_osd(self, overlay_id: int, data: str) -> None:
def clear_osd(self, overlay_id: int) -> None:
def load_placeholder(self) -> None:

# High-level overlay senders (called by poll thread on resize, and by
# PlaybackController when state changes)
def send_qr_overlay(self, url: str, qr_image_path: str) -> None:
def send_url_overlay(self, url: str) -> None:
def send_nowplaying_overlay(self, title: str) -> None:
def send_timecode_overlay(self, elapsed: float, total: float, semitones: int) -> None:
def send_upnext_overlay(self, next_title: str | None) -> None:
def send_clock_overlay(self) -> None:
def clear_all_overlays(self) -> None:
```

OSD ID constants (module-level):
```python
OSD_URL = 1
OSD_NOWPLAYING = 2
OSD_TIMECODE = 3
OSD_UPNEXT = 4
OSD_CLOCK = 5
```

#### SRT Style

```python
def apply_srt_style(self) -> None:
    """Push SRT subtitle style properties to MPV."""
    # Ported from prototype SRT_STYLE dict
```

---

## Modified Module: `pikaraoke/lib/playback_controller.py`

### Changes Summary

- Replace `StreamManager` dependency with `MpvController`
- Remove: `now_playing_url`, `now_playing_subtitle_url`, `ffmpeg_process` property
- Remove: `start_song()` method (MPV plays immediately, no browser handshake)
- Remove: 10-second blocking wait in `play_file()` for client connection
- Remove: `log_output()` method (no FFmpeg stderr to drain)
- Remove: `delete_tmp_dir()` call and 0.3s delay in `end_song()`
- Add: song-end detection by checking `mpv.is_idle` transition
- Add: Socket.IO position broadcast from `mpv.position`
- Modify: `pause()` queries `mpv.is_paused` instead of tracking locally

### Constructor

```python
def __init__(
    self,
    preferences: PreferenceManager,
    events: EventSystem,
    filename_from_path: Callable[[str, bool], str],
    mpv: MpvController,
) -> None:
```

Removed parameters: `streaming_format`
New parameter: `mpv` (injected `MpvController` instance)

Additional instance state:
```python
self._playback_lock = threading.Lock()  # guards is_playing transitions
```

### State Attributes

Keep:
```python
now_playing: str | None
now_playing_filename: str | None
now_playing_user: str | None
now_playing_transpose: int
now_playing_duration: int | None
now_playing_position: float | None  # now read from mpv.position
is_paused: bool                     # now read from mpv.is_paused
is_playing: bool
```

Remove:
```python
now_playing_url: str | None           # no stream URLs
now_playing_subtitle_url: str | None  # no stream URLs
```

### Method Changes

#### `play_file(file_path, user, semitones=0)`

```python
@dataclass
class PlaybackResult:
    """Simplified result -- no stream URLs needed with MPV."""
    success: bool
    error: str | None = None

def play_file(self, file_path: str, user: str, semitones: int = 0) -> PlaybackResult:
    """Start playback of a media file. Non-blocking -- MPV plays immediately.

    Returns PlaybackResult with success status and optional error message.
    """
    # 1. Validate file exists -> PlaybackResult(False, "Song file not found: ...")
    # 2. Find subtitle file (check subtitles/ subfolder for .ass, fall back to .srt)
    # 3. Get normalization_db from song database (if normalize_audio enabled)
    # 4. Acquire _playback_lock
    # 5. Call mpv.play(file_path, semitones, subtitle_path, subtitle_delay, normalization_db)
    # 6. Set now_playing state (title, user, transpose, duration from mpv.duration)
    # 7. Set is_playing = True (immediate -- no wait for client)
    # 8. Release _playback_lock
    # 9. events.emit("playback_started")
    # 10. Update overlays (now playing, timecode, up next)
    # 11. Return PlaybackResult(True)
```

`PlaybackResult` is simplified from the current version (removed `stream_url`,
`subtitle_url`, `duration` fields) but keeps `success` + `error` so the run
loop can report meaningful error messages.

#### `end_song(reason)`

```python
def end_song(self, reason: str | None = None) -> None:
    """End current song. Must be called with _playback_lock held
    (check_playback_ended acquires it) or acquires it when called
    externally (skip, Socket.IO end_song).
    """
    # 1. Guard: if not is_playing, return (prevents double end_song)
    # 2. Log reason, emit notification if abnormal
    # 3. Call mpv.stop() (clears filter, loads placeholder, clears OSD)
    # 4. reset_now_playing()  (sets is_playing = False)
    # 5. events.emit("song_ended")
    # NO delete_tmp_dir, NO 0.3s delay, NO kill_ffmpeg
```

#### `pause()`

```python
def pause(self) -> bool:
    # 1. Check is_playing
    # 2. mpv.toggle_pause()
    # 3. Query mpv.is_paused for actual state
    # 4. Emit notification (pause/resume)
    # 5. events.emit("now_playing_update")
```

#### `get_now_playing()`

```python
def get_now_playing(self) -> dict:
    return {
        "now_playing": self.now_playing,
        "now_playing_user": self.now_playing_user,
        "now_playing_duration": self.now_playing_duration,
        "now_playing_transpose": self.now_playing_transpose,
        "now_playing_position": self.mpv.position,  # live from poll thread
        "is_paused": self.mpv.is_paused,             # live from MPV query
    }
    # Removed: now_playing_url, now_playing_subtitle_url
```

#### New: `check_playback_ended()`

```python
def check_playback_ended(self) -> None:
    """Called from the main run loop. Detects song-end via MPV idle state.

    Uses _playback_lock to prevent race conditions between idle detection
    and concurrent skip/transpose/pause commands. Without the lock, a user
    could hit 'skip' during the ~500ms window between MPV reporting idle
    and end_song() being called, causing double end_song or operating on
    stale state.
    """
    with self._playback_lock:
        if self.is_playing and self.mpv.is_idle:
            self.end_song(reason="complete")
```

#### New: `broadcast_position(socketio)`

```python
def broadcast_position(self, socketio) -> None:
    """Emit current playback position to all Socket.IO clients."""
    if self.is_playing and socketio:
        socketio.emit("playback_position", self.mpv.position, namespace="/")
```

#### New: `set_pitch(semitones)`

```python
def set_pitch(self, semitones: int) -> None:
    """Live pitch change on current song."""
    if self.is_playing:
        self.mpv.set_pitch(semitones)
        self.now_playing_transpose = semitones
        self.events.emit("now_playing_update")
```

#### New: `set_subtitle_delay(seconds)`

```python
def set_subtitle_delay(self, seconds: float) -> None:
    """Forward subtitle delay to MPV."""
    if self.is_playing:
        self.mpv.set_subtitle_delay(seconds)
```

#### New: `restart()`

```python
def restart(self) -> bool:
    """Restart current song from beginning (seek 0 + unpause)."""
    if self.is_playing:
        self.mpv.restart()
        self.events.emit("now_playing_update")
        return True
    return False
```

#### Removed Methods

- `start_song()` -- no browser handshake
- `log_output()` -- no FFmpeg stderr
- `ffmpeg_process` property -- no FFmpeg

---

## Modified Module: `pikaraoke/karaoke.py`

### Constructor Changes

- Remove `streaming_format` parameter and attribute
- Create `MpvController` instance
- Pass `MpvController` to `PlaybackController` instead of `streaming_format`
- Start MPV on init: `self.mpv_controller.start()`

```python
# Before:
self.playback_controller = PlaybackController(
    preferences=self.preferences,
    events=self.events,
    filename_from_path=SongManager.filename_from_path,
    streaming_format=self.streaming_format,
)

# After:
self.mpv_controller = MpvController()
try:
    self.mpv_controller.start()
except RuntimeError as e:
    logging.error(f"MPV failed to start: {e}")
    logging.error("Install MPV (apt install mpv / brew install mpv) and restart.")
    # mpv_controller.is_running will be False; run() checks this before entering loop

self.playback_controller = PlaybackController(
    preferences=self.preferences,
    events=self.events,
    filename_from_path=SongManager.filename_from_path,
    mpv=self.mpv_controller,
)
```

### Method Changes

#### `transpose_current(semitones)`

```python
def transpose_current(self, semitones: int) -> None:
    """Live pitch change on current song (no restart, no re-enqueue)."""
    if not self.playback_controller.is_playing:
        logging.warning("Cannot transpose: no song currently playing")
        return
    self.log_and_send(_("Transposing by %s semitones: %s") % (
        semitones, self.playback_controller.now_playing
    ))
    self.playback_controller.set_pitch(semitones)
    self.update_now_playing_socket()
```

No more `queue_manager.enqueue()` + `skip()`.

#### `volume_change(vol_level)`

```python
def volume_change(self, vol_level: float) -> bool:
    """Set system volume level."""
    self.volume = vol_level
    pct = max(0, min(100, int(vol_level * 100)))
    self.mpv_controller.set_system_volume(pct)
    self.log_and_send(_("Volume: %s") % pct)
    self.update_now_playing_socket()
    return True
```

#### `restart()`

```python
def restart(self) -> bool:
    """Restart current song from beginning."""
    if self.playback_controller.is_playing:
        logging.info("Restarting: " + (self.playback_controller.now_playing or "unknown"))
        self.playback_controller.restart()
        self.update_now_playing_socket()
        return True
    logging.warning("Tried to restart, but no file is playing!")
    return False
```

Now actually seeks to 0 + unpauses.

#### `set_subtitle_delay(delay)`

```python
def set_subtitle_delay(self, delay: float) -> None:
    """Set subtitle delay -- applies live to MPV."""
    self.subtitle_delay = delay
    self.playback_controller.set_subtitle_delay(delay)
    self.log_and_send(_("Subtitle delay: %s seconds") % delay)
    self.update_now_playing_socket()
```

#### `run()` -- main loop

```python
def run(self) -> None:
    if not self.mpv_controller.is_running:
        logging.error("Cannot start run loop: MPV is not running")
        return

    self.running = True
    while self.running:
        try:
            # Song-end detection (reads mpv.is_idle)
            self.playback_controller.check_playback_ended()

            # Clean up if playback ended but state wasn't reset
            if (not self.playback_controller.is_playing
                    and self.playback_controller.now_playing is not None):
                self.reset_now_playing()

            # Broadcast position to remote UI clients
            self.playback_controller.broadcast_position(self.socketio)

            # Start next song from queue
            if self.queue_manager.queue and not self.playback_controller.is_playing:
                self.reset_now_playing()
                # splash_delay between songs (same as current)
                splash_delay = self.preferences.get_or_default("splash_delay")
                i = 0
                while i < (splash_delay * 1000):
                    self.handle_run_loop()
                    i += self.loop_interval

                song = self.queue_manager.pop_next()
                if not song:
                    continue
                result = self.playback_controller.play_file(
                    song["file"], song["user"], song["semitones"]
                )
                if not result.success and result.error:
                    self.log_and_send(result.error, "danger")

            # No more playback_controller.log_output() -- no FFmpeg
            self.handle_run_loop()
        except KeyboardInterrupt:
            logging.warning("Keyboard interrupt: Exiting pikaraoke...")
            self.running = False
```

#### `stop()`

```python
def stop(self) -> None:
    self.running = False
    self.processing_manager.stop()
    self.mpv_controller.quit()  # NEW: shut down MPV
```

#### `get_now_playing()`

```python
def get_now_playing(self) -> dict:
    playback_state = self.playback_controller.get_now_playing()
    queue = self.queue_manager.queue
    next_song = queue[0] if queue else None
    return {
        **playback_state,
        "up_next": next_song["title"] if next_song else None,
        "next_user": next_song["user"] if next_song else None,
        "volume": self.volume,
        "subtitle_delay": self.subtitle_delay,
    }
    # Consumers that checked now_playing_url or now_playing_subtitle_url
    # must be updated to not depend on those keys
```

### Removed Imports

```python
# Remove:
from pikaraoke.lib.ffmpeg import supports_hardware_h264_encoding
# Keep get_ffmpeg_version and is_transpose_enabled only if still used elsewhere
```

### Removed Attributes

- `streaming_format`
- `supports_hardware_h264_encoding`

---

## Modified Module: `pikaraoke/routes/socket_events.py`

### Remove

- `splash_connections` set
- `master_splash_id` global
- `register_splash()` handler
- `handle_disconnect()` handler (splash role handover)
- Master-only guard in `handle_playback_position()`

### Keep

- `end_song()` handler -- but this should be reviewed. With no browser detecting
  `video.ended`, the server-side poll thread handles song-end detection.
  Keep for now as a manual "force end" from remote UI.
- `start_song()` handler -- remove (no browser handshake)
- `clear_notification()` handler -- keep
- `playback_position` handler -- remove or repurpose. Position now flows
  server -> client (from poll thread), not client -> server. The remote UI
  receives position via `now_playing` or a dedicated server-emitted event.

### After

```python
def setup_socket_events(socketio):
    @socketio.on("end_song")
    def end_song(reason: str) -> None:
        k = get_karaoke_instance()
        k.playback_controller.end_song(reason)

    @socketio.on("clear_notification")
    def clear_notification() -> None:
        k = get_karaoke_instance()
        k.reset_now_playing_notification()
```

---

## Modified Module: `pikaraoke/routes/controller.py`

### Changes

#### `/transpose/<semitones>`

```python
@controller_bp.route("/transpose/<semitones>", methods=["GET"])
def transpose(semitones):
    k = get_karaoke_instance()
    # No more broadcast_event("skip") -- no song restart
    k.transpose_current(int(semitones))
    return redirect(url_for("home.home"))
```

#### `/restart`

No change needed -- `karaoke.restart()` now actually seeks to 0.

#### `/volume/<volume>`, `/vol_up`, `/vol_down`

No route changes needed -- `karaoke.volume_change()` now calls system volume.

#### `/subtitle_delay/<seconds>`

No route changes needed -- `karaoke.set_subtitle_delay()` now forwards to MPV.

---

## Modified Module: `pikaraoke/lib/preference_manager.py`

### Remove from DEFAULTS

```python
"complete_transcode_before_play": False,
"buffer_size": 150,
"avsync": 0,
```

### Keep

```python
"normalize_audio": False,  # now controls whether pre-computed dB is applied
"volume": 0.85,            # still the default system volume level
"splash_delay": 2,         # delay between songs (on placeholder screen)
"subtitle_delay": 0,       # default subtitle delay
```

---

## Modified Module: `pikaraoke/lib/args.py`

### Remove Arguments

- `--streaming-format`
- `--complete-transcode-before-play` / `-c`
- `--buffer-size` / `-b`
- `--avsync`

### Keep

- `--normalize-audio` / `-n` (repurposed: apply pre-computed dB during playback)
- `--volume` / `-v`

### Remove from `Karaoke.__init__`

Remove corresponding parameters: `streaming_format`, `avsync`, `buffer_size`,
`complete_transcode_before_play`

---

## Files to Remove

| File | Reason |
|------|--------|
| `pikaraoke/lib/stream_manager.py` | Replaced by `MpvController` |
| `pikaraoke/lib/file_resolver.py` | Temp dir / stream UID management; MPV reads files directly |
| `pikaraoke/lib/ffmpeg.py` | Playback transcoding; keep only `get_media_duration` and `is_transpose_enabled` if still needed (move to a utility or inline) |
| `pikaraoke/routes/stream.py` | All `/stream/*` and `/subtitle/*` routes |
| `pikaraoke/templates/splash.html` | Browser playback page |
| `pikaraoke/static/js/splash.js` | Browser playback logic |
| `pikaraoke/static/js/subtitles-octopus.js` | ASS rendering in browser |
| `pikaraoke/lib/omxclient.py` | Legacy OMX player |

### Files to Partially Clean

| File | What to remove |
|------|----------------|
| `pikaraoke/lib/get_platform.py` | Remove stream-specific temp dir usage only; `get_temp_directory` stays for downloads/processing |

---

## Data Flow: Song Playback Lifecycle

### Song Start

```
1. karaoke.run() loop detects queue has songs, nothing playing
2. Waits splash_delay seconds (shows placeholder on MPV window)
3. queue_manager.pop_next() -> {file, user, semitones}
4. playback_controller.play_file(file, user, semitones)
   a. Validates file exists
   b. Finds subtitle file (.ass or .srt in subtitles/ subfolder)
   c. Reads normalization_db from song database (if normalize_audio enabled)
   d. mpv.play(file, semitones, subtitle_path, subtitle_delay, normalization_db)
      - loadfile command
      - Wait for duration > 0
      - Build lavfi-complex: rubberband(pitch) -> volume(norm_db) -> [ao]
      - set_property lavfi-complex
      - sub-add if subtitle exists
      - apply_srt_style if .srt
      - set sub-delay
   e. Sets now_playing state attributes
   f. is_playing = True
   g. events.emit("playback_started")
   h. Updates overlays (now playing, timecode, up next)
```

### During Playback

```
MpvController poll thread (every 500ms):
  - Queries: time-pos, duration, idle-active, pause
  - Updates: self.position, self.duration, self.is_idle, self.is_paused
  - Monitors osd-width/osd-height for resize -> re-sends overlays
  - Updates clock overlay

karaoke.run() loop (every 500ms):
  - playback_controller.check_playback_ended()
    -> reads mpv.is_idle; if was playing and now idle -> end_song("complete")
  - playback_controller.broadcast_position(socketio)
    -> emits "playback_position" with mpv.position to all clients

Remote UI commands (via HTTP routes / Socket.IO):
  - /pause -> playback_controller.pause() -> mpv.toggle_pause()
  - /transpose/N -> karaoke.transpose_current(N) -> mpv.set_pitch(N)
  - /volume/V -> karaoke.volume_change(V) -> mpv.set_system_volume(pct)
  - /restart -> karaoke.restart() -> mpv.restart() (seek 0 + unpause)
  - /subtitle_delay/S -> karaoke.set_subtitle_delay(S) -> mpv.set_subtitle_delay(S)
  - /skip -> playback_controller.skip() -> end_song("skip")
```

### Song End

```
1. Poll thread detects idle-active = True
2. karaoke.run() calls check_playback_ended()
3. playback_controller.end_song("complete")
   a. mpv.stop() -- clears lavfi-complex, loads placeholder, clears OSD
   b. reset_now_playing() -- clears all state
   c. events.emit("song_ended")
4. karaoke.run() detects now_playing != None but not playing -> reset_now_playing()
5. Loop continues: if queue has songs, start next after splash_delay
```

---

## Data Flow: Filter Chain

### Single-Stem (current PiKaraoke behavior)

```
[aid1] -> rubberband@rb=pitch={multiplier}:pitchq=quality:... -> volume={norm_db}dB -> [ao]
```

- `pitch` = `2 ** (semitones / 12)`, default 1.0 (no shift)
- `norm_db` = pre-computed value from song database, e.g. `-14.0`
- If normalization disabled or no dB value: omit the `volume` node

### Live Pitch Change

When user hits transpose, only the `lavfi-complex` is rebuilt and re-applied:
```python
new_filter = build_filter(new_pitch, current_normalization_db)
set_property("lavfi-complex", new_filter)
```
No song restart, no queue manipulation, no FFmpeg re-launch.

---

## Migration Order

### Phase 1: Create `MpvController` with tests

1. Create `pikaraoke/lib/mpv_controller.py`
2. Implement: lifecycle (start/quit) with startup validation (binary check, socket readiness, `--hwdec=auto`), `is_running` flag
3. Implement: IPC (send_command/query_property/set_property)
4. Implement: play, stop, seek, toggle_pause, set_pitch, restart, set_subtitle_delay
5. Implement: build_filter (single-stem only, no dual-stem state)
6. Implement: audio server detection (`_detect_audio_backend`) and system volume (get/set) with wpctl/pactl/amixer fallback
7. Implement: poll thread
8. Implement: overlay methods (port from prototype)
9. Unit tests with mocked subprocess/socket

### Phase 2: Rewire `PlaybackController`

1. Replace `StreamManager` with `MpvController`
2. Remove stream URL / FFmpeg / temp dir logic
3. Simplify `PlaybackResult` (keep `success` + `error`, drop stream fields)
4. Add `_playback_lock` for thread-safe state transitions
5. Add `check_playback_ended()` (with lock), `broadcast_position()`, `set_pitch()`, `restart()`
6. Update `play_file()` to be non-blocking, return simplified `PlaybackResult`
7. Update `pause()` to query MPV
8. Update `end_song()` with is_playing guard to prevent double-end
9. Update `get_now_playing()` to remove stream URLs
10. Update tests

### Phase 3: Rewire `Karaoke`

1. Remove `streaming_format` parameter chain
2. Create and inject `MpvController`
3. Update `transpose_current()` for live pitch
4. Update `volume_change()` / `vol_up()` / `vol_down()` for system volume
5. Update `restart()` to use `playback_controller.restart()`
6. Update `set_subtitle_delay()` to forward to MPV
7. Update `run()` loop: add `check_playback_ended()`, `broadcast_position()`, remove `log_output()`
8. Update `stop()` to quit MPV
9. Update tests

### Phase 4: Clean up routes and socket events

1. Remove `pikaraoke/routes/stream.py` and its blueprint registration
2. Simplify `socket_events.py` (remove splash architecture)
3. Update `controller.py` transpose route (no more skip broadcast)
4. Update tests

### Phase 5: Remove dead code

1. Delete `stream_manager.py`, `file_resolver.py`, `ffmpeg.py` (or extract keepers), `omxclient.py`
2. Delete `splash.html`, `splash.js`, `subtitles-octopus.js`
3. Clean up `preference_manager.py` DEFAULTS
4. Clean up `args.py`
5. Remove `streaming_format` from anywhere it's referenced
6. Run full test suite, verify no import errors

### Phase 6: Manual verification

- [ ] Start PiKaraoke, MPV window appears with placeholder
- [ ] Queue a song from remote UI, playback starts on MPV window
- [ ] Overlays show: now playing, timecode, QR code, clock
- [ ] Remote UI shows progress bar updating
- [ ] Transpose +2 mid-song: pitch changes live, no restart
- [ ] Volume up/down: system volume changes
- [ ] Pause/resume from remote UI
- [ ] Restart: song seeks to beginning
- [ ] Subtitle delay: SRT timing shifts
- [ ] Song ends naturally: placeholder shown, next song starts after delay
- [ ] Skip: song stops immediately, next starts after delay
- [ ] Queue multiple songs: transitions work correctly
- [ ] Resize MPV window: overlays reposition
- [ ] Up Next overlay shows when next song differs
- [ ] Missing video file: error logged, no crash
- [ ] MPV binary not installed: clear error message, run loop does not start
- [ ] Volume controls work on PipeWire (wpctl), PulseAudio (pactl), and ALSA (amixer)
