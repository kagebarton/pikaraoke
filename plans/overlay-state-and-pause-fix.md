Model: Claude Opus 4.7

# Overlay state-transition refactor + pause-on-start fix

Two related issues surfaced while adding the idle queue-preview overlay:

1. The next song after a song change always loads paused.
2. Overlay ticks fire at moments when `PlaybackController`, `MpvController`,
   and `QueueManager` state aren't consistent with each other — producing
   stale-now-playing flashes on the splash and a "queue loses a line" flash
   on song transitions. Two committed `refresh_overlays()` calls cover two
   of the three races; the third (pop-before-play) was previously masked by
   an uncommitted `freeze_queue_preview` scaffold that has since been
   discarded, so it's live on HEAD.

Both are fallout from the same root pattern: mutating state in an order that a
subsequent render can observe before the transition completes. Fix the pause
bug, then make state updates strictly precede the renders that read them so
the band-aids (and the remaining uncovered race) all fall out together.

---

## 1. Pause-on-start bug

### Root cause

`MpvController.play()` and `stop()` set the Python attribute `self.is_paused =
False` but never touch MPV's actual `pause` property. MPV preserves `pause`
across `loadfile` calls, and the placeholder image (loaded with
`image_display_duration=inf`) leaves MPV in `pause=True`. The next video
therefore loads paused.

The `_on_pause` observer doesn't re-fire on the next `play()` because the
property value hasn't changed since MPV set it `True` during placeholder
display — so the Python tracker `self.is_paused` stays `False` (it was cleared
by `play()`) while the actual video is frozen. Only place in the codebase that
correctly clears MPV's property today is `restart()` at
[mpv_controller.py:486](pikaraoke/lib/mpv_controller.py#L486).

### Fix

One-line addition in each of `play()` and `stop()`:

```python
# pikaraoke/lib/mpv_controller.py, inside play() around line 335
self.is_idle = False
self.is_paused = False
self._player.pause = False   # NEW — also clear MPV's pause property
self.position = 0.0
```

```python
# pikaraoke/lib/mpv_controller.py, inside stop() around line 375
self.position = 0.0
self.duration = 0.0
self.is_paused = False
self._player.pause = False   # NEW — symmetry; covers user-paused-then-skipped
```

The explicit assignment to `self._player.pause` triggers MPV's change
notification, which fires `_on_pause(value=False)` on the event thread — this
is harmless (it just writes the same `False` back to `self.is_paused`) but
guarantees the property is cleared on both sides.

### Verification

- Queue two songs, pause the first mid-play, then skip. Second song plays.
- Queue two songs, let the first complete naturally. Second song plays.
- Queue two songs, pause mid-play of the first, wait for natural completion
  while paused, verify second song plays.
- Sanity: `restart()` still works (already had the correct pattern).

---

## 2. State-then-render refactor

### Current architecture

#### Data flow

```
QueueManager.queue (list[dict])
        │
        │ lambda in Karaoke.__init__ maps first 5 to QueuedSong tuples
        ▼
PlaybackController._get_queue_preview  ── callable[[], tuple[QueuedSong, ...]]
        │
        │ called from build_overlay_state()
        ▼
PlaybackController.build_overlay_state()  ── reads: self.now_playing_*, self.is_playing,
        │                                          self.mpv.{position,duration,is_paused,osd_size},
        │                                          preferences, _get_queue_preview()
        ▼
OverlayState (frozen dataclass)
        │
        │ passed to OverlayManager.apply()
        ▼
OverlayManager.apply()  ── diffs desired vs last-sent, sends osd_overlay / clear_osd
        │
        ▼
MPV IPC (osd-overlay command)
```

#### Render triggers (who calls `_tick_overlays()`)

| Trigger                               | Thread              | Call site                                     |
| ------------------------------------- | ------------------- | --------------------------------------------- |
| Every 0.5s while `time-pos` advances  | MPV event thread    | `_on_time_pos` → `on_tick` cb → `_tick_overlays` |
| OSD resize                            | MPV event thread    | `_on_osd_dim` → `on_resize` cb → `_tick_overlays` |
| Mode change inside `play()`/`stop()`  | Calling thread      | `set_mode()` → `_tick_overlays`               |
| `PlaybackController.refresh_overlays()` | Calling thread    | `mpv._tick_overlays` (used by pitch/sub/pref toggles) |

#### Key state fields

- `MpvController._screen_mode: ScreenMode` — only written by `set_mode()`;
  only read by `set_mode()` itself (for transition diffing). Effectively a
  private write-only field today.
- `MpvController.is_paused: bool` — tracker for Python-side reads; written by
  `_on_pause` observer and by `play()`/`stop()` (and the current pause bug).
- `MpvController.is_idle: bool` — tracker; gated by `_on_idle_active` for
  song-end callback re-entry protection.
- `PlaybackController.now_playing*` — the authoritative source for what's
  playing. Read by `build_overlay_state` and `get_now_playing` (Socket.IO).
- `PlaybackController.is_playing: bool` / `is_paused: bool` — high-level
  flags; `build_overlay_state` uses them to derive `ScreenMode`.

#### Current song-start flow

```
karaoke.run (main thread)
  │
  ├─ pop_next()                       ── queue shrinks from 5 → 4
  │
  └─ playback_controller.play_file(file, user, semitones)
       │
       ├─ acquire _playback_lock
       │   │
       │   ├─ mpv.play(...)
       │   │    ├─ loadfile
       │   │    ├─ wait _duration_ready
       │   │    ├─ apply filters, subs
       │   │    └─ set_mode(ScreenMode.PLAYING)
       │   │         └─ _tick_overlays()                ◀── RENDER 1
       │   │              build_overlay_state sees:
       │   │                • is_playing = False (not set yet)
       │   │                • now_playing = None
       │   │                • queue_preview = 4 items
       │   │              → mode=IDLE, renders queue-preview overlay
       │   │                with 4 items (visible flash!)
       │   │
       │   └─ set now_playing*, is_playing=True
       │
       ├─ release lock
       ├─ emit("playback_started")
       └─ refresh_overlays() → _tick_overlays()         ◀── RENDER 2
              → mode=PLAYING, correct overlays
```

#### Current song-end flow

```
MPV reports idle-active=True (on MPV event thread)
  │
  └─ _on_idle_active → on_song_end callback (karaoke.py:204)
       │
       └─ with _playback_lock:  end_song(reason="complete")
            │
            ├─ mpv.stop()
            │    ├─ lavfi_complex = ""
            │    ├─ is_paused = False  (Python only; see bug #1)
            │    └─ set_mode(ScreenMode.IDLE)
            │         ├─ load_placeholder()              ── new file loaded
            │         └─ _tick_overlays()                ◀── RENDER 1
            │              build_overlay_state sees:
            │                • is_playing = True (not reset yet)
            │                • now_playing = "<song title>"
            │              → mode=PLAYING, renders now-playing overlay
            │                on top of the splash (stale flash!)
            │
            ├─ reset_now_playing()                       ── clears PC state
            ├─ refresh_overlays() → _tick_overlays()     ◀── RENDER 2
            │        → mode=IDLE, correct splash overlays
            └─ emit("song_ended")
```

### Current races

Three spots trigger overlay renders against transitional state:

1. **Song-start, render 1.** `MpvController.play()` calls
   `set_mode(ScreenMode.PLAYING)` at
   [line 365](pikaraoke/lib/mpv_controller.py#L365) *before* `PlaybackController`
   has set `now_playing`/`is_playing`. Committed band-aid: second
   `refresh_overlays()` call at
   [playback_controller.py:163](pikaraoke/lib/playback_controller.py#L163).
2. **Song-end, render 1.** `MpvController.stop()` calls
   `set_mode(ScreenMode.IDLE)` at
   [line 376](pikaraoke/lib/mpv_controller.py#L376) *before*
   `reset_now_playing()` runs, so the tick sees stale `now_playing_title`.
   Committed band-aid: `refresh_overlays()` in `end_song()` at
   [playback_controller.py:238](pikaraoke/lib/playback_controller.py#L238).
3. **Pop-before-play.** `karaoke.run` pops from the queue at
   [karaoke.py:654](pikaraoke/karaoke.py#L654) *before* `play_file()` runs.
   Any tick in that window (plus the inner set_mode tick from race 1)
   renders IDLE with a shortened queue. No band-aid on HEAD — this race is
   live and visible as the "queue loses a line right before the video plays"
   flash.

### Target architecture

**Invariant:** `PlaybackController` owns all logical state. Any render
triggered inside `MpvController` must see a `PlaybackController` snapshot
that already reflects the transition. No render happens before both state
sources are consistent.

#### Method changes

##### `MpvController.play()` — remove `set_mode`; add pause-clear

Before (current):
```python
def play(self, file_path, semitones=0, *, ass_path=None, ...):
    # ... subtitle/stem setup ...
    self.is_idle = False
    self.is_paused = False
    self.position = 0.0
    self._duration_ready.clear()
    self._fired_osd_dim = (None, None)
    self._player.loadfile(file_path)
    if not self._duration_ready.wait(timeout=5):
        log.warning(...)
    # ... dual-stem, filters, subtitle mode ...
    self.duration = float(self._player.duration or 0.0)
    self.set_mode(ScreenMode.PLAYING)         # ← REMOVE (triggers bad render)
```

After:
```python
def play(self, file_path, semitones=0, *, ass_path=None, ...):
    # ... subtitle/stem setup unchanged ...
    self.is_idle = False
    self.is_paused = False
    self._player.pause = False                # ← ADD (pause fix)
    self.position = 0.0
    self._duration_ready.clear()
    self._fired_osd_dim = (None, None)
    self._player.loadfile(file_path)
    if not self._duration_ready.wait(timeout=5):
        log.warning(...)
    # ... dual-stem, filters, subtitle mode ...
    self.duration = float(self._player.duration or 0.0)
    # no set_mode — caller decides when to render
```

##### `MpvController.stop()` — remove `set_mode`; add pause-clear

Before:
```python
def stop(self):
    self.is_idle = True
    with self._lock:
        self._player.lavfi_complex = ""
    self.position = 0.0
    self.duration = 0.0
    self.is_paused = False
    self.set_mode(ScreenMode.IDLE)            # ← REMOVE (triggers bad render)
```

After:
```python
def stop(self):
    # Set is_idle BEFORE clearing lavfi_complex. _on_idle_active fires on the
    # MPV event thread when the filter clear causes the player to go idle,
    # and its guard `if value is True and not self.is_idle` is what keeps it
    # from re-entering on_song_end. Reorder at your peril: _playback_lock is
    # non-reentrant, so a second on_song_end would deadlock the caller.
    self.is_idle = True
    with self._lock:
        self._player.lavfi_complex = ""
    self.position = 0.0
    self.duration = 0.0
    self.is_paused = False
    self._player.pause = False                # ← ADD (pause fix)
    # no set_mode — caller decides when to render/load placeholder
```

##### `MpvController` — delete `set_mode()` and `_screen_mode`

`_screen_mode` has no external readers (grep confirms: only `set_mode`
references it). Remove the field and the method entirely. Keep
`load_placeholder()` and `_tick_overlays()` as separate public primitives.

Rename `_tick_overlays` → `tick_overlays` (drop the underscore) since it's
now explicitly part of the public API consumed by `PlaybackController`.
`refresh_overlays` in `PlaybackController` continues to forward to it.

##### `PlaybackController.play_file()` — state first, then mpv, then tick

Before:
```python
def play_file(self, file_path, user, semitones=0):
    # ... validate, find subs/companions ...
    with self._playback_lock:
        self.mpv.play(file_path, ..., vocal_volume=vocal_volume)  # triggers inner tick (stale)
        self.now_playing = self.filename_from_path(file_path, remove_youtube_id=True)
        self.now_playing_filename = file_path
        # ... set remaining now_playing_* ...
        self.is_paused = False
        self.is_playing = True

    self.events.emit("playback_started")
    self.refresh_overlays()                   # ← band-aid render
    return PlaybackResult(success=True)
```

After:
```python
def play_file(self, file_path, user, semitones=0):
    # ... validate, find subs/companions (unchanged) ...
    with self._playback_lock:
        # 1. Set all PC state that doesn't depend on mpv.play having run
        self.now_playing = self.filename_from_path(file_path, remove_youtube_id=True)
        self.now_playing_filename = file_path
        self.now_playing_user = user
        self.now_playing_transpose = semitones
        self.now_playing_position = 0.0
        self.now_playing_sub_mode = initial_sub_mode
        self.now_playing_subs_available = {
            "ass": subs["ass"] is not None and os.path.exists(subs["ass"]),
            "srt": subs["srt"] is not None and os.path.exists(subs["srt"]),
        }
        self.now_playing_dual_stem = vocal_path is not None and nonvocal_path is not None
        self.now_playing_vocal_volume = vocal_volume
        self.is_paused = False
        self.is_playing = True

        # 2. Run MPV loadfile + filter setup (no inner tick now)
        self.mpv.play(file_path, ..., vocal_volume=vocal_volume)

        # 3. Duration is only known after mpv.play completes the duration wait
        self.now_playing_duration = int(self.mpv.duration) if self.mpv.duration else None

        # 4. Single render with fully-consistent state
        self.mpv.tick_overlays()

    self.events.emit("playback_started")
    return PlaybackResult(success=True)
```

Note: during `mpv.play()`'s `_duration_ready.wait(timeout=5)`, observer-thread
renders are theoretically possible but in practice don't fire (time-pos only
advances after pause=False AND loadfile completes; osd_dim only changes on
actual window resize). If one did fire, it would render with
`duration=<stale>` or `0.0` — a brief "0:00 / 0:00" timecode that the
subsequent tick corrects. Acceptable degradation, no flash.

##### `PlaybackController.end_song()` — reset PC state first, then mpv, then placeholder, then tick

Before:
```python
def end_song(self, reason=None):
    if not self.is_playing:
        return
    # ... log, emit abnormal notification ...
    self.mpv.stop()                           # triggers inner tick (stale)
    self.reset_now_playing()
    self.refresh_overlays()                   # ← band-aid render
    self.events.emit("song_ended")
```

After:
```python
def end_song(self, reason=None):
    if not self.is_playing:
        return
    # ... log, emit abnormal notification (unchanged) ...

    # 1. Clear PC state before any render observes it
    self.reset_now_playing()

    # 2. Stop MPV playback (filter clear, pause clear, counters reset)
    self.mpv.stop()

    # 3. Show splash and trigger the one render with consistent state
    self.mpv.load_placeholder()
    self.mpv.tick_overlays()

    self.events.emit("song_ended")
```

#### Target song-start flow

```
karaoke.run (main thread)
  │
  ├─ pop_next()                       ── queue shrinks 5 → 4
  │
  └─ play_file(...)
       │
       └─ with _playback_lock:
            ├─ set now_playing*, is_playing=True                ── PC state consistent
            ├─ mpv.play(...)                                    ── no inner render
            │    ├─ _player.pause = False                       ── pause fix
            │    ├─ loadfile + duration wait + filters + subs
            │    └─ (returns)
            ├─ now_playing_duration = mpv.duration
            └─ mpv.tick_overlays()                              ◀── SINGLE RENDER
                 build_overlay_state sees:
                   • is_playing = True
                   • now_playing = "<title>"
                   • queue_preview = 4 items (post-pop)
                 → mode=PLAYING, renders now-playing + up-next
```

#### Target song-end flow

```
MPV idle-active=True (on MPV event thread)
  │
  └─ _on_idle_active → on_song_end cb → with _playback_lock: end_song("complete")
       │
       ├─ reset_now_playing()                                   ── PC state cleared
       ├─ mpv.stop()                                            ── _player.pause=False, filters clear
       ├─ mpv.load_placeholder()                                ── splash image loaded
       └─ mpv.tick_overlays()                                   ◀── SINGLE RENDER
            build_overlay_state sees:
              • is_playing = False
              • now_playing = None
              • queue_preview = N items
            → mode=IDLE, renders queue preview / clock / URL
```

#### Observer behavior (unchanged)

| Observer         | Writes                                   | Keeps firing? |
| ---------------- | ---------------------------------------- | ------------- |
| `_on_time_pos`   | `self.position`; fires `on_tick` every 0.5s | Yes, drives the periodic render |
| `_on_duration`   | `self.duration`, sets `_duration_ready`  | Yes          |
| `_on_idle_active`| `self.is_idle`; fires `on_song_end` once | Yes          |
| `_on_pause`      | `self.is_paused`                         | Yes          |
| `_on_osd_dim`    | `_current_osd_dim`; fires `on_resize`    | Yes          |

Periodic render (`on_tick` → `tick_overlays`) is unchanged — it's the
mechanism that refreshes the clock, the timecode, and the position. Resize
render is unchanged. The only deletions are the two internal renders that
`set_mode` used to do.

#### State field changes

| Field                          | Before         | After         |
| ------------------------------ | -------------- | ------------- |
| `MpvController._screen_mode`   | Present, internal | **Removed**  |
| `MpvController.set_mode()`     | Present        | **Removed**   |
| `MpvController._tick_overlays` | Present, private | Renamed → `tick_overlays` (public) |
| `MpvController.load_placeholder` | Private-ish (only called from `start`, `set_mode`) | Public — called from `end_song` |
| `PlaybackController.refresh_overlays` | Present | **Kept** (still used by live preference/pitch/sub changes — grep `refresh_overlays` shows routes in `controller.py` and other live toggles) |
| `PlaybackController.freeze_queue_preview` | **Not on HEAD** (discarded) | n/a |
| `PlaybackController._queue_preview_override` | **Not on HEAD** (discarded) | n/a |

#### Who still calls `refresh_overlays()`?

These paths stay — they're legitimate "state changed mid-song, render now":
- `set_pitch`, `set_sub_mode`, `set_vocal_volume` (all already emit
  `now_playing_update` and need a fresh OSD)
- Preference toggles for `hide_url`, `hide_now_playing_overlay`, `show_clock`
  (each sets the pref then calls `refresh_overlays` so the effect is visible
  within the current frame)

The refactor only deletes the two `refresh_overlays()` calls in `play_file`
and `end_song` (the band-aids). The method itself stays.

---

## 3. Risks / caveats

The refactor relies on **no overlay tick running between `queue.pop_next()`
and the state-set block of `play_file()`**. Today that holds because:

- The run-loop thread is synchronous across those two calls (no `await`,
  no thread handoff).
- During placeholder display, `time-pos` does not advance, so `_on_time_pos`
  doesn't fire `on_tick`.
- `_on_osd_dim` only fires on actual window resize.
- `_on_pause` writes a bool and does not tick.

If a future change adds a periodic tick on the placeholder, or emits
overlay-refreshing events from another thread during that window, the flash
returns. A fully race-proof version would acquire `_playback_lock` inside
`tick_overlays` too — not worth it for the current overlay surface (no
foreseeable karaoke overlay needs tick-level consistency with queue/playback
state; see chat 2026-04-21 for the overlay-surface analysis).

### Known pre-existing issue: `@_safe` silent failure

`MpvController.play()` and `stop()` are decorated with `@_safe`
([mpv_controller.py:63](pikaraoke/lib/mpv_controller.py#L63)), which catches
and logs every exception and returns `None`. If either fails silently
(`ShutdownError` or transient libmpv fault), the caller (`play_file` /
`end_song`) has no way to know and proceeds to update PC state / render
overlays against a broken player.

This is true on HEAD today (the committed `refresh_overlays()` band-aids fire
unconditionally, too), so the refactor does **not** regress it — it simply
re-exposes the latent inconsistency on the happy path where a band-aid used
to mask it.

Deferred to a follow-up plan so the diff here stays focused on state-order.
Likely fix: drop `@_safe` from `play()` and `stop()` and let exceptions
propagate; `play_file` / `end_song` then call `reset_now_playing()` in a
`try/except` to roll back PC state. `load_placeholder()` keeping `@_safe` is
fine — silent failure there only leaves the last video frame visible, which
is cosmetic.

---

## 4. Files touched

- [pikaraoke/lib/mpv_controller.py](pikaraoke/lib/mpv_controller.py)
  - Delete `_screen_mode` field, `set_mode()` method.
  - Remove `set_mode()` calls from `play()` and `stop()`.
  - Add `self._player.pause = False` to `play()` and `stop()`.
  - Rename `_tick_overlays` → `tick_overlays` (and update internal callers:
    `_on_time_pos`'s `on_tick` wiring still goes through the Karaoke-side
    callback so no change there, but `set_mode`'s removed call is gone).
- [pikaraoke/lib/playback_controller.py](pikaraoke/lib/playback_controller.py)
  - Reorder `play_file`: state-set block before `mpv.play`; single
    `mpv.tick_overlays()` at end of locked block.
  - Drop the `refresh_overlays()` after `emit("playback_started")`.
  - Reorder `end_song`: `reset_now_playing()` before `mpv.stop()`; add
    explicit `mpv.load_placeholder()` + `mpv.tick_overlays()`.
  - Drop the `refresh_overlays()` in `end_song`.
  - Update `refresh_overlays` body: `self.mpv.tick_overlays()` (rename).
  - Update `build_overlay_state` docstring reference from
    `MpvController._tick_overlays` to `tick_overlays` (rename).
- [pikaraoke/karaoke.py](pikaraoke/karaoke.py)
  - No changes expected. `pop_next()` / `play_file()` ordering in `run()` is
    already correct once `play_file` is reordered.
- Tests: sweep [tests/unit/test_playback_controller.py](tests/unit/test_playback_controller.py)
  and [tests/unit/test_karaoke_utils.py](tests/unit/test_karaoke_utils.py)
  for references to `set_mode`, `_screen_mode`, or mock expectations about
  the order of `mpv.play` and state-set. Update mocks for the rename of
  `_tick_overlays` → `tick_overlays`. Tighten `test_play_file_success`:
  assert `mock_mpv.tick_overlays` is called exactly once and that the
  now_playing\_\* state-set happens before `mock_mpv.play` (inspect the
  `method_calls` ordering on the mock).

---

## 5. Implementation order

Do them in this sequence — each step is independently testable:

1. **Pause fix.** Add the two `self._player.pause = False` lines. Run the
   pause verification steps above. This is mechanical and low-risk.
2. **Rename `_tick_overlays` → `tick_overlays`.** Pure rename, no behavior
   change. Update every caller (`_on_time_pos`'s `on_tick` wiring in
   `karaoke.py:211`, `on_resize` wiring in `karaoke.py:210`, the two
   internal `set_mode` call sites that are about to be deleted, and
   `PlaybackController.refresh_overlays`).
3. **Reorder `end_song`.** Insert `reset_now_playing()` before `mpv.stop()`,
   add `mpv.load_placeholder()` + `mpv.tick_overlays()`, drop the trailing
   `refresh_overlays()`. At this point `mpv.stop()` still calls `set_mode`,
   so the stale-now-playing flash may still occur for one tick — but the
   subsequent render corrects it. Acceptable interim state.
4. **Reorder `play_file`.** Move the state-set block above `self.mpv.play()`,
   move duration-set after `mpv.play`, add `mpv.tick_overlays()` at the end
   of the locked block, drop the post-lock `refresh_overlays()`.
5. **Remove `set_mode` and `_screen_mode`.** Now that nothing depends on the
   internal renders, delete both and their call sites in `play()`/`stop()`.
   While in `stop()`, add the ordering-dependency comment noted in §2 above
   (why `is_idle = True` must precede `lavfi_complex = ""`).
6. **Sweep tests.** Run `pytest`; fix any tests that mocked `set_mode` or
   the old ordering. Update `test_play_file_success` to assert the new
   `tick_overlays()` call and the state-set-before-`mpv.play` ordering.

---

## 6. Test plan (manual)

- Natural end-of-song → next song: no stale now-playing text on splash,
  queue preview replaced atomically by up-next overlay.
- Skip → next song: same as above.
- Pause → skip → next song: plays, not paused (covers pause bug).
- Pause → wait for natural end → next song: plays, not paused.
- Idle with queue of 5: full 5-item preview, upper-right, correct styling.
- Queue of 1 during playback: up-next overlay shows, no queue preview.
- Queue of 0, song ending: splash shows with clock + URL, no overlays linger.
- Toggle `hide_now_playing` mid-song: overlays clear immediately (verifies
  `refresh_overlays` still works for live preference toggles).
- Toggle `show_clock` on splash: clock appears within a frame.
- Pitch shift mid-song: timecode overlay's pitch indicator updates.
- Switch subtitle mode mid-song: no overlay flicker.
- Resize the MPV window mid-song: overlays re-render at new size.
