# Review: Overlay State-Transition Refactor + Pause-on-Start Fix

Review of `plans/overlay-state-and-pause-fix.md` against the current codebase
(HEAD as of 2026-04-21).

---

## Correctly Identified

1. **Pause-on-start root cause** — Confirmed. `play()` (mpv_controller.py:335)
   and `stop()` (line 375) set `self.is_paused = False` but never set
   `self._player.pause = False`. The placeholder loaded with
   `image_display_duration="inf"` (line 188) leaves MPV's `pause=True`, and
   `_on_pause` won't re-fire because the value hasn't *changed*. Only
   `restart()` (line 486) does it right. The two one-line additions are
   correct.

2. **Race 1 (song-start stale render)** — Confirmed. `mpv.play()` at
   playback_controller.py:133 calls `set_mode(ScreenMode.PLAYING)` at
   mpv_controller.py:365, which triggers `_tick_overlays()` while
   `now_playing`/`is_playing` haven't been set yet (they're set at
   lines 146–160).

3. **Race 2 (song-end stale render)** — Confirmed. `mpv.stop()` at
   playback_controller.py:236 calls `set_mode(ScreenMode.IDLE)` at
   mpv_controller.py:376, which triggers `_tick_overlays()` and also
   `load_placeholder()`, all before `reset_now_playing()` at line 237.

4. **Race 3 (pop-before-play)** — Confirmed. `queue_manager.pop_next()` at
   karaoke.py:654 shrinks the queue before `play_file()` at line 657 runs.
   Any tick in that window renders a shortened queue preview. No existing
   band-aid covers this.

5. **`_screen_mode` has no external readers** — Confirmed. grep shows it's
   only referenced inside `set_mode()` itself (mpv_controller.py:496, 499).
   Safe to delete.

6. **All callers of `_tick_overlays`** — Confirmed at 4 sites:
   `set_mode` lines 497+502, `karaoke.py` lines 210–211,
   `playback_controller.py` line 353.

7. **`refresh_overlays()` external callers** — Confirmed:
   `preferences.py:38` (live pref toggles), and the two in-band-aids inside
   `play_file:163` and `end_song:238`. The method itself should be kept.

---

## Potential Issues

### 1. Re-entrancy risk in `_on_idle_active` during `end_song()` reorder

**Severity: Low**

The plan moves `reset_now_playing()` before `mpv.stop()`. `mpv.stop()` sets
`self.is_idle = True` (line 370) **before** clearing lavfi-complex. The
`_on_idle_active` callback (line 261–270) has the guard:

```python
if value is True and not self.is_idle:
```

Since `stop()` sets `is_idle = True` first (line 370), the guard suppresses
re-entry. **This is safe today.** However, after the refactor, `end_song()` is
called with `_playback_lock` already held (from karaoke.py:205). If an
`idle-active` observer fires on the MPV event thread while `end_song()` holds
`_playback_lock`, and the `_on_song_end` callback tries to acquire it, it
would **deadlock** — because `_playback_lock` is a `threading.Lock`
(non-reentrant), not an `RLock`.

The current code is safe only because `is_idle = True` is set *before* the
observer can fire, so the guard always blocks re-entry. A future refactor of
`stop()` that moves `is_idle = True` to after the loadfile would break this.
**Recommendation**: add a comment in `stop()` documenting the ordering
dependency, or switch `_playback_lock` to `threading.RLock` (mpv_controller
already uses `RLock` for `self._lock`).

### 2. Wider failure window after state-set reorder

**Severity: Medium**

The plan's target `play_file()` sets `is_playing = True` **before**
`self.mpv.play()`. If `mpv.play()` fails partway (e.g. loadfile raises an
exception caught by `@_safe`), `play_file()` proceeds to `tick_overlays()`
and `emit("playback_started")` with broken MPV state — the controller is stuck
in `is_playing = True` with no actual playback. The current code at least has
`mpv.play()` happen first, so the window for this inconsistency is narrower.

**Recommendation**: wrap the `mpv.play()` + `tick_overlays()` block in a
try/except that calls `reset_now_playing()` on failure, or remove `@_safe`
from `play()` so failures propagate to `play_file()`.

### 3. `@_safe` on `mpv.play()` silently swallows errors after reorder

**Severity: High**

This is the most impactful concern. `play()` is decorated with `@_safe`
(mpv_controller.py:304), which catches all exceptions and returns `None`.
After the reorder, `play_file()` sets `is_playing = True`, then calls
`mpv.play()`. If `mpv.play()` hits a `ShutdownError` or any other exception,
`@_safe` swallows it and returns `None`. `play_file()` doesn't check the
return value, so it proceeds to set `now_playing_duration`, call
`tick_overlays()`, and emit `"playback_started"` — all with a broken player.

Similarly, `stop()` is `@_safe`-decorated (line 367). If it fails silently in
`end_song()`, `load_placeholder()` and `tick_overlays()` run against a
player that wasn't actually stopped.

**Recommendation**: either remove `@_safe` from `play()` and `stop()` (so
exceptions propagate to the caller that can roll back state), or add explicit
return-value checks in `play_file()` / `end_song()` that call
`reset_now_playing()` on `None` returns.

### 4. `@_safe` on `load_placeholder()` can silently fail

**Severity: Low**

The target `end_song()` calls `mpv.load_placeholder()` + `mpv.tick_overlays()`.
`load_placeholder()` is `@_safe`-decorated (line 569). If it fails silently,
the placeholder won't be loaded but `tick_overlays()` will still render IDLE
overlays on whatever frame MPV is showing (possibly the last video frame,
frozen). This is a cosmetic degradation, not a functional bug, but worth
noting.

### 5. `mpv.stop()` sets `is_idle = True` — redundancy not addressed

**Severity: Low (documentation only)**

After the refactor, `stop()` still sets `is_idle = True` manually (line 370).
The `idle-active` observer *also* sets it (line 266). This is intentional
re-entry protection, but the plan doesn't mention whether to keep it. It
should be kept — removing it would allow the observer to fire `on_song_end`
again. A comment explaining the dual-write would prevent a future cleanup
pass from removing it.

### 6. Test coverage gaps

**Severity: Trivial**

- `test_play_file_success` (test_playback_controller.py:81–99) only asserts
  `mock_mpv.play.assert_called_once()`. After the reorder, it should also
  assert that `mock_mpv.tick_overlays()` is called exactly once and that
  `mock_mpv._tick_overlays()` (old name) is not called.
- `conftest.py` `MockPlaybackController` doesn't include `refresh_overlays`
  or `tick_overlays`. Tests using the real `PlaybackController` with a
  `MagicMock` mpv will auto-handle the rename, but explicit assertions on
  method names will need updating.
- The docstring in `build_overlay_state` (playback_controller.py:322)
  references `MpvController._tick_overlays` and needs updating to
  `tick_overlays`.

### 7. Observer-thread tick during `_duration_ready.wait()` — acceptable but untested

The plan acknowledges (§2, target `play_file()` note) that observer-thread
renders are theoretically possible during `mpv.play()`'s
`_duration_ready.wait(timeout=5)`, but argues they don't fire in practice
because `time-pos` only advances after `pause=False` AND loadfile completes.
This is correct, but there's no test asserting that `tick_overlays()` is not
called during that window. If a future MPV version changes `time-pos` behavior
during loading, the stale-duration flash returns. Low risk, but worth a
comment in the code.

---

## Summary

The plan is **architecturally sound**. The root-cause analysis is accurate, the
invariant (PC state before render) is correct, and the implementation order
is well-chosen. The two main concerns are:

| # | Severity | Issue |
|---|----------|-------|
| 3 | **High** | `@_safe` on `mpv.play()` silently swallows errors after state-set reorder, leaving PC stuck in `is_playing=True` with broken MPV. |
| 2 | **Medium** | Wider window for `is_playing=True` with no playback if `mpv.play()` fails — needs a rollback path. |
| 1 | **Low** | Latent deadlock risk if `stop()` reorder ever changes the `is_idle = True` placement relative to loadfile. |
| 4 | **Low** | `@_safe` on `load_placeholder()` can silently fail, leaving last video frame visible under IDLE overlays. |
| 5–7 | **Trivial** | Documentation, comment, and test coverage gaps. |
