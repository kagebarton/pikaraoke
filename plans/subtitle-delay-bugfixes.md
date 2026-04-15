Model: Claude Sonnet 4.6

# Subtitle Delay Bug Fixes

## Context

Three commits added subtitle delay support (default preference + live per-song override).
A follow-up commit (`eb6bda6`) fixed a race condition by deferring SubtitlesOctopus
initialization to the video `"play"` event instead of `handleNowPlayingUpdate`. Three
remaining issues were identified in review:

1. **Ordering bug**: `broadcast_event` fires before `k.subtitle_delay` is updated, so the
   `now_playing` event emitted by `set_subtitle_delay` carries the stale delay value.
2. **`timeOffset` ternary noise**: `pendingSubtitleDelay ? -pendingSubtitleDelay : 0` is
   equivalent to `-pendingSubtitleDelay` in JS (`-0 === 0`) — the guard is dead weight.
3. **Re-init before video plays**: Both the `subtitle_delay` socket handler and
   `PREFERENCE_EFFECTS.subtitle_delay` call `initializeSubtitles()` unconditionally.
   If the live delay is changed in the brief window after `handleNowPlayingUpdate` sets
   `pendingSubtitleUrl` but before the video fires `"play"`, SubtitlesOctopus is attached
   to a video with no source; then `"play"` fires and it inits a second time.

## Files to Modify

- `pikaraoke/routes/controller.py`
- `pikaraoke/static/js/splash.js`

______________________________________________________________________

## Fix 1 — Flip order in controller.py (lines 84–86)

Call `set_subtitle_delay` first so `k.subtitle_delay` is updated before the socket event
is broadcast. The `now_playing` event emitted by `update_now_playing_socket` will then
carry the correct value.

```python
# Before
broadcast_event("subtitle_delay", seconds)
k.set_subtitle_delay(float(seconds))

# After
k.set_subtitle_delay(float(seconds))
broadcast_event("subtitle_delay", seconds)
```

______________________________________________________________________

## Fix 2 — Remove ternary in `initializeSubtitles` (splash.js line 133)

```js
// Before
timeOffset: pendingSubtitleDelay ? -pendingSubtitleDelay : 0

// After
timeOffset: -pendingSubtitleDelay
```

Also remove the inline comment "Invert the sign: user expects negative = earlier, but
timeOffset works opposite" — move the explanation to the `initializeSubtitles` function
docblock/comment instead so it's said once.

______________________________________________________________________

## Fix 3 — Guard `initializeSubtitles()` calls on live delay change (splash.js)

Both the `PREFERENCE_EFFECTS.subtitle_delay` handler and the `"subtitle_delay"` socket
handler should only call `initializeSubtitles()` if the video is already playing. If it
isn't, the pending state is already set correctly and the `"play"` event will call
`initializeSubtitles()` at the right time.

Extract a helper `isVideoPlaying()` or inline the check:

```js
const video = getVideoPlayer();
if (video && !video.paused && !video.ended) {
  initializeSubtitles();
}
```

Apply this guard in both locations:

**`PREFERENCE_EFFECTS.subtitle_delay` (lines 383–391):**

```js
subtitle_delay: (v) => {
  PikaraokeConfig.subtitleDelay = v;
  pendingSubtitleDelay = v;
  if (nowPlaying.now_playing_subtitle_url) {
    pendingSubtitleUrl = nowPlaying.now_playing_subtitle_url;
    const video = getVideoPlayer();
    if (video && !video.paused && !video.ended) {
      initializeSubtitles();
    }
  }
},
```

**`"subtitle_delay"` socket handler (lines 488–500):**

```js
socket.on("subtitle_delay", (delay) => {
  const delayValue = parseFloat(delay);
  if (nowPlaying) {
    nowPlaying.subtitle_delay = delayValue;
  }
  pendingSubtitleDelay = delayValue;
  if (nowPlaying.now_playing_subtitle_url) {
    pendingSubtitleUrl = nowPlaying.now_playing_subtitle_url;
    const video = getVideoPlayer();
    if (video && !video.paused && !video.ended) {
      initializeSubtitles();
    }
  }
});
```

______________________________________________________________________

## Verification

1. **Default delay**: Set subtitle delay in Settings → open splash, confirm subtitles lead/lag correctly.
2. **Live override**: While a song with subtitles is playing, use the home page slider and hit Change → confirm subtitles shift immediately.
3. **Song change resets**: Confirm per-song override resets to default after skip/end.
4. **No double-init**: In browser devtools console, verify SubtitlesOctopus is not constructed twice on song start.
5. **Ordering fix**: Set live delay, then skip to next song; confirm the delay reported in `now_playing` is the new value, not the old one (check via `/api/v1/now_playing` or home slider sync).
