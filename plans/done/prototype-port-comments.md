# Plan Review: Port Remaining Prototype Features

## Source Document

`plans/port-prototype-features.md`

## Context

This review cross-references the plan against the main project's existing codebase (`pikaraoke/`) and the prototype (`mpv/`) to identify gaps, incorrect assumptions, and potential issues before implementation begins.

______________________________________________________________________

## Issues Found

### Critical Issues (Must Fix Before Implementation)

#### 1. `build_filter` signature change breaks existing callers

- **Location:** `pikaraoke/lib/mpv_controller.py:340-346`
- **Problem:** The plan extends `MpvController.build_filter(pitch, normalization_db)` to take 4 args: `build_filter(pitch, normalization_db, dual_stem, vocal_volume)`. But `MpvController.set_pitch()` at line 340-346 calls the current 2-arg version. This will break at runtime.
- **Fix required:** Update `set_pitch()` to read `self._dual_stem` and `self._current_vocal_volume` and pass all four args to `build_filter`.

#### 2. `PlaybackController.seek()` doesn't exist

- **Location:** `pikaraoke/lib/playback_controller.py` (missing)
- **Problem:** Feature #6 references `PlaybackController.seek(position: float)` but the class has no such method. The plan shows it delegates to `mpv.seek()`, but the method doesn't exist.
- **Fix required:** Add the method to `PlaybackController` before Feature #6.

#### 3. `set_pitch()` doesn't pass `dual_stem` or `vocal_volume`

- **Location:** `pikaraoke/lib/mpv_controller.py:340-346`
- **Problem:** As noted in issue #1, the current `set_pitch()` only passes pitch and `normalization_db` to `build_filter`. For dual-stem playback, pitch changes while playing must preserve the dual-stem chain and vocal volume.

#### 4. Single-stem rubberband chain must align with prototype

- **Location:** `pikaraoke/lib/mpv_controller.py:485-511` vs `mpv/app.py:161-166`
- **Problem:** The prototype's single-stem chain uses `_RB_VOCAL` (a module constant with full preset: `pitchq=quality:transients=crisp:detector=compound:phase=laminar:window=long:formant=preserved:channels=together:smoothing=off`). The main project's `build_filter` inlines similar params but they differ slightly (e.g., missing `:pitchq=quality`). This means pitch shifting in single-stem mode behaves differently between prototype and main.
- **Fix required (confirmed):** Align single-stem chain with prototype's `_RB_VOCAL` preset. Define `_RB_VOCAL` and `_RB_NONVOCAL` as module-level constants in `mpv_controller.py` matching the prototype's values. Use `_RB_VOCAL` in both single-stem and dual-stem vocal chain; use `_RB_NONVOCAL` for dual-stem nonvocal chain.

#### 5. `@_safe` doesn't guard `lavfi_complex` assignment

- **Location:** `pikaraoke/lib/mpv_controller.py:307-308` and `345-346`
- **Problem:** Both `play()` and `set_pitch()` set `self._player.lavfi_complex` without the `@_safe` decorator. If lavfi_complex assignment fails mid-playback, exceptions propagate uncaught, unlike all other MPV operations.
- **Note:** `build_filter` itself is a static method with no side effects, so wrapping it is fine. The issue is the assignment.

______________________________________________________________________

### ZMQ / azmq Dependency

#### 6. ZMQ imports needed in main project

- **Location:** `pikaraoke/lib/mpv_controller.py` (no ZMQ imports)
- **Problem:** The plan uses `azmq=bind_address=tcp\\://127.0.0.1\\:5556` in the dual-stem filter chain and a ZMQ REQ socket for live vocal volume changes. The main project has no ZMQ dependency imported.
- **Fix required:** Add `import zmq` (or `import pyzmq as zmq`) and the `_zmq_ctx` context to `mpv_controller.py`. The prototype's `mpv/mpv_controller.py:282-302` shows the pattern to follow. Note: The prototype uses `zmq` as a module-level import with a context at module scope. The plan's suggestion to use raw `socket.socket` inside `_safe` is an alternative, but the prototype's ZMQ context approach is cleaner for repeated calls.

______________________________________________________________________

### State Management Issues

#### 7. `now_playing_vocal_volume` never included in `get_now_playing()` payload

- **Location:** `pikaraoke/lib/playback_controller.py:226-239`
- **Problem:** Feature #1 tracks `self.now_playing_vocal_volume: float` on `PlaybackController` and `set_vocal_volume()` updates it (line 203). But `PlaybackController.get_now_playing()` never includes it in the returned dict. The UI `handleNowPlaying()` won't receive the vocal volume value.
- **Fix required:** Add `"vocal_volume": self.now_playing_vocal_volume` to the dict returned by `get_now_playing()`.

#### 8. `now_playing_dual_stem` not reset in `PlaybackController.reset_now_playing()`

- **Location:** `pikaraoke/lib/playback_controller.py:241-250`
- **Problem:** The plan adds `self.now_playing_dual_stem: bool` to track dual-stem state. But `reset_now_playing()` doesn't reset it. After a song ends, the next song could incorrectly show dual-stem UI until actual playback determines the state.
- **Fix required:** Add `self.now_playing_dual_stem = False` to `reset_now_playing()`.

#### 9. `vocal_volume` parameter missing from `Karaoke.__init__` signature

- **Location:** `pikaraoke/karaoke.py:82-108`
- **Problem:** For `_load_preferences` to auto-set `self.vocal_volume` via `apply_all()`, the parameter must exist in `Karaoke.__init__` with a `vocal_volume: float | None = None` default. The plan (line 183) says it "will be loaded automatically" but `apply_all()` (preference_manager.py:189-200) only hydrates attributes whose names match a key in `DEFAULTS`. If the parameter isn't in `__init__`, it won't be passed through and `_load_preferences` won't set it.
- **Fix required:** Add `vocal_volume: float | None = None` to `Karaoke.__init__` parameters.

______________________________________________________________________

### Audio Track ID Assumption

#### 10. `audio-add` track ID ordering is assumed, not verified

- **Location:** Plan lines 88-92, `mpv/app.py:480-486`
- **Problem:** The plan assumes `loadfile(video)` + `audio-add(vocal)` + `audio-add(nonvocal)` produces tracks at `aid2` and `aid3`. But the main project currently doesn't add secondary audio tracks, so there are no guarantees about ID ordering when `lavfi_complex` is active and references `[aid2]` and `[aid3]`.
- **Recommendation:** Document this as a known assumption that needs verification, or add a test that confirms track IDs after `audio-add`.

______________________________________________________________________

### Type Annotation Issues

#### 11. All `OverlayState` construction sites must be updated

- **Location:** `pikaraoke/lib/overlay_manager.py:44-63`
- **Problem:** The plan adds `dual_stem: bool` and `vocal_volume: float` to `OverlayState` (a `@dataclass(frozen=True)`). The plan identifies `PlaybackController.build_overlay_state()` (lines 599-607) but doesn't check for other call sites constructing `OverlayState`.
- **Fix required:** Search codebase for all `OverlayState(` constructions and update each to include the new fields.

#### 12. `get_now_playing()` return type is broad but consistent

- **Location:** `pikaraoke/lib/playback_controller.py:226`
- **Problem:** `PlaybackController.get_now_playing()` is typed `-> dict[str, str | int | float | bool | None]`. Adding `vocal_volume` (float) and `dual_stem` (bool) is already within this union. `Karaoke.get_now_playing()` returns `dict[str, Any]` — the type annotations are inconsistent but not a runtime issue.
- **Note:** Not a blocker; just noting the type divergence.

______________________________________________________________________

### Subtitle Mode Issues

#### 13. `_apply_subtitle_mode` must guard `sub_remove()` before video loaded

- **Location:** Plan lines 389-393, `mpv/app.py:204-234`
- **Problem:** The prototype's `_apply_subtitle_mode` documents that `skip_remove` exists because calling `sub_remove()` while lavfi-complex is active can segfault libmpv. The main project's implementation must only call `sub_remove()` when a subtitle is actually active, and must use `skip_remove=True` on initial play when an auto-loaded sub may exist.
- **Fix required:** Verify the main project's `_apply_subtitle_mode` (which the plan creates in Feature #3) follows this invariant.

#### 17. `.ass` file location is `<song-dir>/karaoke/<song>.ass`

- **Location:** Plan lines 351-353 (Subtitle file conventions table)
- **Clarified:** `.ass` files will be in a `karaoke/` subfolder of the song's directory, not sibling to the video file. The path pattern is `<song-dir>/karaoke/<base_name>.ass` where `base_name` is the video filename without extension.
- **Fix required:** `_find_subtitles()` in PlaybackController must look in `<os.path.dirname(file_path)>/karaoke/` for `.ass` files, not the video's parent directory directly.

______________________________________________________________________

### Minor Issues

#### 14. `azmq` filter escaping syntax unclear

- **Location:** Plan line 81
- **Problem:** The filter string shows `tcp\\\\://127.0.0.1\\\\:5556`. In Python source, `\\\\` becomes `\\` at the string level. It's unclear if this produces the correct `tcp://127.0.0.1:5556` that mpv's azmq expects. The prototype has `tcp\\\\://127.0.0.1\\\\:5556` which in a Python raw string or f-string context likely needs verification.
- **Recommendation:** Test the escaping or examine the exact string the prototype sends to mpv.

#### 15. `Path` vs `os.path` inconsistency in `_find_companions`

- **Location:** Plan lines 117-124, `playback_controller.py` consistently uses `os.path`
- **Problem:** The plan's `_find_companions` uses `Path()` objects, but `playback_controller.py` uses `os.path.splitext()` and `os.path.dirname()` everywhere else.
- **Fix required:** Use `os.path` for consistency, or update to `Path` with proper imports.

#### 16. Seek bar JS `_seekDragging` has post-seek race condition

- **Location:** Plan lines 688-710
- **Problem:** If `playback_position` arrives between slider `change` event and the `$.get("/seek/")` completing, the slider could snap back to server position after the user releases. The `_seekDragging` lock should persist until after the seek request confirms (e.g., in the `.always()` callback).
- **Note:** Low severity; may be acceptable given the 500ms poll interval.

______________________________________________________________________

## Already Correct Items

The following items in the plan align correctly with the existing codebase:

| Item | Location |
|------|----------|
| `_find_subtitle` logic for SRT | `playback_controller.py:137-154` |
| `PreferenceManager.set()` per-song override guard pattern | `preference_manager.py:124` |
| `Karaoke.reset_now_playing()` structure | `karaoke.py:558-564` |
| `MpvController.seek()` existing method | `mpv_controller.py:330-332` |
| `PlaybackController.build_overlay_state()` existing method | `playback_controller.py:252-275` |
| `MpvController._lock` threading lock exists | `mpv_controller.py:82` |
| `_semiround` helper exists | `mpv_controller.py:46-48` |

______________________________________________________________________

## Questions for Clarification

1. **Feature #3 (.ass file location):** Confirmed — `.ass` files will be supplied manually in a song folder subfolder called `karaoke/`, with files named `<video_prefix>.ass`. This will be generated by ProcessingManager in a future update. The plan should reference this path convention.

2. **Single-stem chain alignment:** Confirmed — the single-stem rubberband chain in `build_filter` should be made identical to the prototype's `_RB_VOCAL` preset for consistency.

______________________________________________________________________

## Summary

The plan is well-structured and the feature decomposition is sound. ZMQ availability is confirmed via the prototype. Clarifications applied: (.ass files in `karaoke/` subfolder, single-stem chain must match prototype exactly). The critical issues are:

1. **Must fix before Feature #1 work:** Issues #1, #3 (build_filter signature), #4 (align single-stem chain with prototype), #7, #8, #9 (state management), #10 (track ID assumption), #15 (Path vs os.path).

2. **Land with Feature #2:** Issue #6 (add ZMQ imports and context).

3. **Land with Feature #3:** Issues #13 (sub_remove guard), #17 (.ass path is `karaoke/` subfolder not same directory).

4. **Land with Feature #6:** Issue #2 (add `PlaybackController.seek()`).

5. **Low priority:** Issues #5, #11, #14, #16.

The suggested rollout order in the plan (#3 → #1+#2+#5+#7 → #6) is still sound. With ZMQ confirmed available, Feature #2 (vocal volume) can proceed without the fallback concern.
