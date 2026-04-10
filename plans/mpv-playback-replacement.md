# MPV Playback Replacement Plan

Model: Claude Opus 4.6

## Overview

Replace PiKaraoke's browser-based video playback (HLS/MP4 streaming → `<video>` element → Subtitles Octopus → HTML/CSS overlays) with MPV as the native playback engine. MPV handles video/audio rendering, pitch shifting, subtitle display, and OSD overlays directly — eliminating the need for server-side transcoding for playback and the browser splash page.

The playback screen becomes fully native MPV — no browser UI at all. The web UI is remote-only (queue management, search, playback controls).

**What stays:** Queue management, remote control web UI, server-side logic, Socket.IO, event system, download/processing pipelines, song management.

**What goes:** Browser `<video>`, HLS/MP4 streaming, Subtitles Octopus, `splash.html`, `splash.js`, `StreamManager`, `stream.py` routes, FFmpeg playback transcoding, master/slave splash architecture (register_splash, splash election, slave position sync in `socket_events.py`).

**What changes:** `PlaybackController` swaps `StreamManager` for an MPV controller. The MPV prototype (in `mpv/`) provides the foundation. Audio normalization moves from live FFmpeg `loudnorm` to a pre-computed dB value (stored in song database by `ProcessingManager`, passed to playback as a `volume` filter parameter).

---

## Architecture Change

### Current

```
QueueManager → PlaybackController → StreamManager → FFmpeg subprocess
    ↓                                    ↓
  HLS/MP4 temp files              HTTP stream routes (/stream/*)
                                        ↓
                              Splash browser <video> element
                                        ↓
                          Subtitles Octopus + HTML/CSS overlays
```

### After

```
QueueManager → PlaybackController → MPV Controller → MPV subprocess
                                          ↓
                              MPV window with native OSD
                              (subtitles, now-playing, up-next, QR)
                                        ↓
                          Socket.IO position broadcast (for remote UI)
```

---

## Method-Level Mapping

### Playback Controller Methods

| PiKaraoke Method | Prototype Equivalent | Status | Notes |
|---|---|---|---|
| `PlaybackController.play_file(path, user, semitones)` | `play()` + `reset_state_defaults()` + `loadfile` + `audio-add` + `build_filter()` + `sub-add` | ⚠️ Partial | Prototype mocks single song; needs per-song `semitones` param, queue integration, `EventSystem.emit` |
| `PlaybackController.end_song(reason)` | `end_song()` + `reset_state_defaults()` + `load_placeholder()` | ✅ | Prototype also clears OSD; needs `events.emit("song_ended")` |
| `PlaybackController.start_song()` | N/A (implicit in `play()`) | ✅ | MPV plays immediately on `loadfile`; no client-connect handshake needed. The current 10-second blocking wait in `play_file()` for a browser to call `start_song()` must be explicitly removed. |
| `PlaybackController.skip()` | N/A (calls `end_song()`, then next queue item) | ✅ | Logic stays in PiKaraoke; just triggers `end_song()` |
| `PlaybackController.pause()` | `pause()` → `cycle pause` | ✅ | Direct 1:1 |
| `Karaoke.transpose_current(st)` | `set_pitch()` → rebuild `lavfi-complex` | ⚠️ Differs | Current behavior: re-enqueues same song at queue top with new semitones, then calls `skip()` — full song restart with queue manipulation. MPV can do live transpose (prototype already does this via `set_pitch`). This is a user-visible behavior change: no song restart, no queue manipulation, pitch changes mid-song. |
| `Karaoke.volume_change(vol)` | `set_master_volume()` via `wpctl` | ⚠️ Differs | PiKaraoke stores `volume` as a preference (0.0-1.0, persisted to config.ini) and applies it via `<video>.volume` through Socket.IO broadcast. Prototype uses system `wpctl` and only adjusts vocal stem volume (ZMQ) in dual-stem mode — does nothing for single-stem. Need MPV `volume` property (0-200) for universal app-level control. |
| `Karaoke.vol_up()` / `Karaoke.vol_down()` | `stepMasterVolume()` in JS → `set_master_volume` API | ⚠️ Differs | Same as above — needs app-level MPV `volume` property, not system-level `wpctl` |
| `Karaoke.restart()` | `seek(0)` → `seek 0 absolute` | ⚠️ Improved | Current `karaoke.restart()` only unpauses — it does not actually seek to 0. The plan's proposed behavior (`seek 0 absolute` + unpause) is an improvement over current behavior, not a 1:1 mapping. |
| `Karaoke.set_subtitle_delay(delay)` | `set_sub_delay()` → `set_property sub-delay` | ✅ | Direct 1:1 |
| `PlaybackController.pause()` state tracking | Prototype `pause()` has no state tracking | ⚠️ Gap | Current `pause()` flips `is_paused` and emits `now_playing_update`. MPV controller must either query MPV `pause` property or track state locally. |
| `StreamManager.play_file(path, semitones)` | `play()` → `loadfile` + `audio-add` + `set_property lavfi-complex` | ✅ Replaced | No more FFmpeg transcoding; MPV reads files natively |
| `StreamManager.kill_ffmpeg()` | `quit_mpv()` / `stop` + `load_placeholder` | ✅ Replaced | MPV subprocess lifecycle is simpler |
| `StreamManager._transcode_file()` | N/A | ❌ Removed | MPV handles all formats natively |
| `build_ffmpeg_cmd()` (ffmpeg.py) | `build_filter(vocal_vol, pitch, dual_stem)` | ✅ Replaced | `lavfi-complex` string instead of ffmpeg-python builder. Normalization moves from live FFmpeg `loudnorm` to a pre-computed dB value from the song database, applied as a `volume` filter parameter in `build_filter`. |
| `FileResolver` (stream paths) | N/A | ✅ Removed | `FileResolver` primarily manages temp dirs and stream path generation (HLS UIDs, segment patterns) — none of which MPV needs. Companion file discovery (stems/subs) is already handled by `ProcessingManager`; the prototype's `derive_companion_paths` likely won't be needed either. |
| Splash `video.currentTime` polling | `poll_position()` → `time-pos` property | ✅ | Both poll every 500ms |
| Splash `video.onended` | `poll_position()` → `idle-active` check | ✅ | Both detect end-of-song |
| Splash HTML overlays | `send_nowplaying_overlay()`, `send_timecode_overlay()`, `send_upnext_overlay()`, `send_qr_overlay()`, `send_clock_overlay()` | ✅ | MPV OSD replaces all HTML overlays |
| Subtitles Octopus (ASS) | `sub-add` + MPV native ASS rendering + `apply_srt_style()` | ✅ | MPV handles ASS natively, better than Octopus |

---

## Gaps to Fill

### High Severity

| # | Gap | PiKaraoke Dependency | Fix |
|---|-----|---------------------|-----|
| 1 | **Socket.IO position broadcast** | Remote UI shows progress bar; slave splashes sync position. `splash.js` master emits `playback_position` via Socket.IO every 500ms. | `poll_position()` must call `socketio.emit("playback_position", pos)` on each cycle. |
| 2 | **Per-song transpose at play time** | `play_file(path, user, semitones)` — semitones come from queue item. Each queued song can have different transpose. | `play()` must accept `semitones` parameter. Build `lavfi-complex` with that value from the start. |
| 3 | **Event system integration** | `events.emit("playback_started")`, `events.emit("song_ended")` drive notifications, UI updates, and the main run loop. | Add `EventSystem` calls in `play()` and `end_song()`. |

### Medium Severity

| # | Gap | PiKaraoke Dependency | Fix |
|---|-----|---------------------|-----|
| 4 | **App-level volume (not system)** | `Karaoke.volume` (0–1) stored in preferences (persisted to config.ini). Volume applies via `<video>.volume` through Socket.IO. Prototype only adjusts vocal stem volume (ZMQ) in dual-stem mode — does nothing for single-stem. | Use MPV `volume` property (0–200) for universal app-level control. Drop `wpctl` system calls and ZMQ vocal-only approach. |
| 5 | **`now_playing` metadata in status** | `get_now_playing()` returns title, user, duration, transpose, paused, position, URLs. Remote UI and queue display depend on this. | Extend `status()` response to include `now_playing`, `now_playing_user`, `is_paused`. |
| 6 | **Pause state tracking** | `PlaybackController.pause()` flips `is_paused` and emits `now_playing_update`. Prototype `pause()` fires `cycle pause` but doesn't track state. | Query MPV `pause` property or track locally. Emit `now_playing_update` on toggle. |

### Low Severity

| # | Gap | PiKaraoke Dependency | Fix |
|---|-----|---------------------|-----|
| 7 | **Restart current song endpoint** | Current `karaoke.restart()` only unpauses — does not seek to 0. | Add `/api/restart` route → `seek 0 absolute` + unpause. This is an improvement over current behavior. |
| 8 | **Transpose without restart** | Current PiKaraoke re-enqueues song at queue top with new semitones, then calls `skip()` — full song restart with queue manipulation. MPV pitch is live. | Adopt live mid-song transpose (MPV advantage). Simplifies `transpose_current()` — no more queue manipulation. User-visible behavior change: pitch changes instantly without song restart. |

### Informational (No Action Needed)

| # | Item | Notes |
|---|------|-------|
| 9 | **Temp dir cleanup** | `delete_tmp_dir()` in `end_song()` — no longer needed since MPV has no temp streams. Remove the call and the 0.3s delay. |
| 10 | **FFmpeg output logging** | `log_output()` → `StreamManager.log_ffmpeg_output()` — no longer needed. Can be removed or made a no-op. |
| 11 | **Master/slave splash architecture** | `register_splash`, master election, slave position sync in `socket_events.py` — all dead code with no browser playback. Remove alongside splash.html/splash.js. |

---

## Features in Prototype Not Needed by PiKaraoke

| Feature | Prototype Method | Reason to Exclude |
|---------|-----------------|-------------------|
| System master volume | `get_master_volume_pct()`, `set_master_volume()` via `wpctl` | PiKaraoke uses app-level volume |
| Dual-stem vocal volume slider | `set_volume()` → ZMQ live update | PiKaraoke doesn't have dual-stem concept (for now) |
| File browser modal | `browse()`, `derive_files()` API | PiKaraoke has its own search/browse UI via remote |
| Companion file auto-detect | `derive_companion_paths()`, JS auto-populate | PiKaraoke has `ProcessingManager` for stem/sub discovery |
| Subtitle mode selector (Karaoke/SRT/Off) | `set_sub_mode()` + segmented control UI | PiKaraoke handles via preferences + splash config |
| Flask exit endpoint | `exit_app()` | PiKaraoke has its own shutdown |
| `SHOW_QR`, `SHOW_CLOCK` flags | Module-level constants | Configurable via PiKaraoke preferences |

---

## Components to Remove

| File/Module | Reason |
|-------------|--------|
| `pikaraoke/lib/stream_manager.py` | No HLS/MP4 streaming |
| `pikaraoke/lib/ffmpeg.py` (`build_ffmpeg_cmd` for playback) | Pitch/volume/codec handling moves to MPV `lavfi-complex` |
| `pikaraoke/routes/stream.py` | No stream endpoints |
| `pikaraoke/static/js/splash.js` | No browser video player |
| `pikaraoke/static/js/subtitles-octopus.js` | MPV handles subtitles natively |
| `pikaraoke/templates/splash.html` | Replaced by MPV window |
| `pikaraoke/lib/file_resolver.py` (HLS/MP4 stream path logic) | No temp stream files. `FileResolver` primarily manages temp dirs and stream UIDs — all MPV-irrelevant. |
| `pikaraoke/lib/get_platform.py` (`get_temp_directory` stream usage only) | Only remove stream-specific temp dir usage. `get_temp_directory` itself is used project-wide (downloads, processing) and must stay. |
| `pikaraoke/lib/omxclient.py` | Legacy OMX player, already superseded |

---

## Components to Create

| New File | Purpose |
|----------|---------|
| `pikaraoke/lib/mpv_controller.py` | MPV subprocess lifecycle, IPC communication, playback state. Replaces `StreamManager`. |

Key methods to implement:

| Method | Purpose |
|--------|---------|
| `mpv_play(file_path, semitones=0, normalization_db=None)` | Accept per-song transpose and pre-computed normalization dB (from song database). Load file + stems + subs, set `lavfi-complex` with pitch and normalization filters, emit `playback_started` event |
| `mpv_stop()` | Call `stop`, `load_placeholder`, clear OSD, emit `song_ended` event |
| `mpv_seek(position)` | `seek <pos> absolute` |
| `mpv_set_pitch(semitones)` | Rebuild `lavfi-complex` with new pitch multiplier |
| `mpv_set_volume(vol_0_to_1)` | Set MPV `volume` property (universal — works for both single-stem and dual-stem) |
| `mpv_set_sub_delay(seconds)` | `set_property sub-delay` |
| `mpv_restart()` | `seek 0 absolute` + unpause |
| `mpv_pause()` | Toggle pause via `cycle pause`. Track `is_paused` state (query MPV `pause` property or track locally). Emit `now_playing_update`. |
| `poll_position()` | Poll `time-pos`, `duration`, `idle-active`; emit `playback_position` via Socket.IO |
| `start_mpv()` | Launch MPV in idle mode, create IPC socket |
| `quit_mpv()` | Graceful shutdown |
| `end_song()` | Clear filter, load placeholder, reset state, clear OSD |

---

## Components to Modify

| File | Changes |
|------|---------|
| `pikaraoke/lib/playback_controller.py` | Replace `StreamManager` with `MpvController`. Remove `now_playing_url`, `now_playing_subtitle_url`, stream-wait logic. Remove the 10-second blocking wait for browser `start_song()` call. Keep all public methods (`play_file`, `end_song`, `skip`, `pause`, `get_now_playing`, `reset_now_playing`). `start_song()` can be removed or made a no-op (MPV plays immediately). |
| `pikaraoke/karaoke.py` | Wire MPV lifecycle into song loop. Remove HLS/stream references. Simplify `transpose_current()` to call MPV live pitch (no re-enqueue/skip). Remove `reset_now_playing()` temp dir cleanup. Pass pre-computed normalization dB from song database to `mpv_play()` when normalization is enabled. |
| `pikaraoke/routes/controller.py` | Volume/transpose/restart routes stay, but wire to MPV controller instead of stream-based methods. |
| `pikaraoke/routes/socket_events.py` | Keep `playback_position` handler. Position source changes from splash master to MPV poll thread. Remove `register_splash`, master/slave election, and slave position sync — all dead code with no browser playback. |
| `pikaraoke/routes/now_playing.py` | No changes — data source unchanged. |
| `pikaraoke/routes/preferences.py` | May add MPV-specific prefs (e.g., `mpv_extra_flags`, `show_qr_overlay`, `show_clock_overlay`). |
| `pikaraoke/lib/preference_manager.py` | Add MPV-specific defaults if needed. Remove from DEFAULTS: `complete_transcode_before_play`, `buffer_size`, `avsync`. Keep `normalize_audio` (now controls whether pre-computed dB value is applied during playback). |
| `pikaraoke/lib/args.py` | Remove `--streaming-format`, `--complete-transcode-before-play`, `--buffer-size`, `--avsync` args. Keep `--normalize-audio` (repurposed: enables applying pre-computed normalization dB during MPV playback). |

---

## Test Plan

### MPV Lifecycle
- [ ] `start_mpv()` launches MPV in idle mode, creates IPC socket
- [ ] `quit_mpv()` gracefully terminates MPV, cleans up socket file
- [ ] MPV survives Flask request/reload cycles (persistent process)

### Playback
- [ ] `mpv_play(file)` loads and plays a video file
- [ ] `mpv_play(file, semitones=2)` plays with pitch shifted up 2 semitones
- [ ] `mpv_play(file, semitones=-3)` plays with pitch shifted down 3 semitones
- [ ] `mpv_stop()` stops playback, shows placeholder, clears OSD
- [ ] `mpv_seek(60)` jumps to 60 seconds
- [ ] `mpv_restart()` returns to 0:00
- [ ] `pause()` toggles pause/resume
- [ ] `mpv_set_pitch(1)` changes pitch mid-song without restart
- [ ] `mpv_set_volume(0.5)` changes volume mid-song
- [ ] `mpv_set_sub_delay(-0.8)` delays SRT subtitles

### Song Transitions
- [ ] Song ends naturally → `idle-active` detected → `end_song()` fires → placeholder shown
- [ ] `end_song()` emits `song_ended` event
- [ ] `play()` after `end_song()` loads new song correctly
- [ ] State resets between songs (semitones=0, volume=default, sub_delay=default)

### Overlays
- [ ] Now Playing shows title during playback, clears when stopped
- [ ] Timecode shows elapsed/total + pitch + volume during playback
- [ ] Up Next shows when next song differs from current
- [ ] QR code overlay renders at correct size
- [ ] Clock overlay shows correct time (if enabled)
- [ ] Overlays reposition on window resize

### Subtitles
- [ ] ASS subtitles load and render with embedded styles
- [ ] SRT subtitles load and render with configured style
- [ ] `sub-delay` applies correctly to SRT files
- [ ] Subtitle file switch mid-playback works (`sub-remove` + `sub-add`)

### Socket.IO Integration
- [ ] `playback_position` emitted every 500ms during playback
- [ ] Position broadcast reaches remote UI clients
- [ ] `playback_started` event fires when song begins
- [ ] `song_ended` event fires when song ends

### Edge Cases
- [ ] Missing video file → returns error, no crash
- [ ] MPV process dies unexpectedly → graceful recovery or error
- [ ] IPC socket unavailable → command silently fails, no crash
- [ ] Rapid play/stop cycles → no race conditions
- [ ] Dual-stem files (vocal + nonvocal) load and mix correctly
- [ ] Single-stem files play without dual-stem filter chain
