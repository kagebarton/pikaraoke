Model: Claude Sonnet 4.6

# Remove Unused Features

Remove six features entirely from PiKaraoke: score screen, screen saver, background music, background video, dolphy mode, and MP3+CDG support.

## Features to Remove

### 1. Score Screen

**Delete files:**
- `pikaraoke/static/score.js`
- `pikaraoke/static/score.css`
- `pikaraoke/static/fireworks.js`
- `pikaraoke/static/sounds/applause-h.mp3`
- `pikaraoke/static/sounds/applause-m.mp3`
- `pikaraoke/static/sounds/applause-l.mp3`
- `pikaraoke/static/sounds/score-drums.mp3`

**Modify:**
- `pikaraoke/routes/splash.py` — Remove `_default_score_phrases()`, `_parse_stored_phrases()`, `_get_active_score_phrases()`, `/splash/score_phrases` route, `disable_score` template var
- `pikaraoke/routes/preferences.py` — Remove `_SCORE_PHRASE_KEYS` and `score_phrases_update` broadcast logic
- `pikaraoke/routes/info.py` — Remove `disable_score` and `score_phrases` template vars
- `pikaraoke/lib/preference_manager.py` — Remove `disable_score`, `low_score_phrases`, `mid_score_phrases`, `high_score_phrases` defaults
- `pikaraoke/lib/args.py` — Remove `--disable-score` argument
- `pikaraoke/karaoke.py` — Remove `disable_score` parameter/property
- `pikaraoke/app.py` — Remove `disable_score` kwarg
- `pikaraoke/templates/splash.html` — Remove score CSS, config vars, HTML block, audio, JS includes
- `pikaraoke/templates/info.html` — Remove `disable_score` checkbox, score phrases section, `serializePhrases()` JS
- `pikaraoke/static/js/splash.js` — Remove `isScoreShown`, `scoreReviews`, score logic in `endSong()`, socket listeners

**Tests:**
- `tests/unit/test_splash_routes.py` — Remove `TestDefaultScorePhrases`, `TestGetActiveScorePhrases`, `TestScorePhrasesEndpoint`
- `tests/unit/test_preference_routes.py` — Remove score broadcast tests
- `tests/unit/test_preference_manager.py` — Remove score phrase and `disable_score` assertions

---

### 2. Screen Saver

**Delete files:**
- `pikaraoke/static/screensaver.js`
- `pikaraoke/static/screensaver.css`

**Modify:**
- `pikaraoke/lib/preference_manager.py` — Remove `screensaver_timeout` default
- `pikaraoke/lib/args.py` — Remove `--screensaver-timeout` / `-t` argument
- `pikaraoke/karaoke.py` — Remove `screensaver_timeout` parameter/property
- `pikaraoke/routes/info.py` — Remove `screensaver_timeout` template var
- `pikaraoke/templates/splash.html` — Remove screensaver CSS, `screensaverTimeout` config, screensaver HTML, screensaver.js
- `pikaraoke/templates/info.html` — Remove screensaver timeout input
- `pikaraoke/static/js/splash.js` — Remove `screensaverTimeoutSeconds`, `setupScreensaver()`, idle timer, preference effect, ready call

**Tests:**
- `tests/unit/test_preference_manager.py` — Remove `screensaver_timeout` assertions

---

### 3. Background Music + Background Video + Dolphy Mode

**Delete files:**
- `pikaraoke/routes/background_music.py`
- `pikaraoke/static/music/midnight-dorufin.mp3` (and `music/` dir)
- `pikaraoke/static/video/night_sea.mp4`
- `pikaraoke/static/video/the_drive_by_visualdon.mp4`
- `pikaraoke/static/images/dolphly.png`

**Modify:**
- `pikaraoke/lib/preference_manager.py` — Remove `disable_bg_music`, `bg_music_volume`, `disable_bg_video`
- `pikaraoke/lib/args.py` — Remove `--bg-music-path`, `--disable-bg-music`, `--bg-music-volume`, `--bg-video-path`, `--disable-bg-video`, `--dolphly` arguments and related path/volume parsing
- `pikaraoke/karaoke.py` — Remove all bg_music and bg_video parameters/properties
- `pikaraoke/app.py` — Remove `background_music_bp`, blueprint registration, bg kwargs
- `pikaraoke/routes/splash.py` — Remove bg template vars
- `pikaraoke/routes/info.py` — Remove bg template vars
- `pikaraoke/routes/stream.py` — Remove `/stream/bg_video` route
- `pikaraoke/templates/splash.html` — Remove bg config vars, `#bg-video-container`, `#background-music`, bg-video CSS
- `pikaraoke/templates/info.html` — Remove bg checkboxes and volume input
- `pikaraoke/static/js/splash.js` — Remove all bg music/video functions and preference effects

**Tests:**
- `tests/unit/test_preference_manager.py` — Remove bg assertions
- `tests/unit/test_preference_routes.py` — Remove bg_video broadcast test

---

### 4. MP3+CDG Support

**Modify:**
- `pikaraoke/lib/file_resolver.py` — Remove `is_cdg_file()`, `handle_zipped_cdg()`, `handle_mp3_cdg()`, `cdg_file_path`
- `pikaraoke/lib/ffmpeg.py` — Remove CDG codec/bitrate/input handling
- `pikaraoke/lib/stream_manager.py` — Remove `cdg_pixel_scaling` passthrough
- `pikaraoke/lib/song_manager.py` — Remove CDG companion file detection/rename logic
- `pikaraoke/lib/library_scanner.py` — Remove CDG format detection
- `pikaraoke/lib/preference_manager.py` — Remove `cdg_pixel_scaling` default
- `pikaraoke/lib/args.py` — Remove `--cdg-pixel-scaling` argument
- `pikaraoke/karaoke.py` — Remove `cdg_pixel_scaling` parameter/property
- `pikaraoke/app.py` — Remove `cdg_pixel_scaling` kwarg
- `pikaraoke/routes/info.py` — Remove `cdg_pixel_scaling` template var
- `pikaraoke/templates/info.html` — Remove CDG pixel scaling checkbox

**Tests:**
- `tests/unit/test_file_resolver.py` — Remove `TestIsCdgFile`, `TestFileResolverHandleMp3Cdg`, `TestFileResolverHandleZippedCdg`
- `tests/unit/test_song_manager.py` — Remove CDG companion file tests
- `tests/unit/test_library_scanner.py` — Remove CDG format detection tests
- `tests/unit/test_preference_manager.py` — Remove `cdg_pixel_scaling` assertions

---

### 5. Translation Cleanup

Remove stale strings from all `.po` and `.pot` files for screensaver and score features.

---

## Commit Order

1. Score screen
2. Screen saver
3. Background music + background video + dolphy mode (intertwined)
4. MP3+CDG support
5. Translation cleanup
