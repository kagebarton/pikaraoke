# Central Temp Directory Configuration

## Context

Temp/intermediate files are currently scattered across system temp (`/tmp`), working directory, and hardcoded paths in three modules. This change introduces a single, persistent, user-configurable temp directory preference stored in `config.ini`, defaulting to `~/.pikaraoke/tmp`.

## Files to Modify

### 1. Add preference and helper — `pikaraoke/lib/get_platform.py`

- Add `get_temp_directory(configured: str = "") -> str` function near `get_data_directory()`
- If `configured` is non-empty and valid, return it (create if needed)
- Otherwise return `os.path.join(get_data_directory(), "tmp")`, create if needed

### 2. Register default — `pikaraoke/lib/preference_manager.py`

- Add `"temp_dir": ""` to `DEFAULTS` dict (empty string = use default `~/.pikaraoke/tmp`)

### 3. Update file_resolver.py — `pikaraoke/lib/file_resolver.py`

- Import `get_temp_directory` from `get_platform`
- Change `get_tmp_dir()` to accept an optional `base_dir: str = ""` parameter
- When `base_dir` provided, use `os.path.join(base_dir, f"{pid}")` instead of `os.path.join(tempfile.gettempdir(), f"{pid}")`
- Update `create_tmp_dir()` and `delete_tmp_dir()` similarly
- Update `FileResolver.__init__` to accept and pass through `temp_dir`
- Update callers in `stream_manager.py` and `routes/stream.py` to pass `temp_dir` from karaoke instance

### 4. Update processing_manager.py — `pikaraoke/lib/processing_manager.py`

- **Intermediate files**: Pass `temp_dir` to worker process via args; use it in `tempfile.mkdtemp(prefix="pikaraoke_stems_", dir=temp_dir)`
- **Log file**: Change `PROCESSING_LOG_FILE` to use `os.path.join(temp_dir, "processing_manager.log")` — pass temp_dir into `ProcessingManager.__init__` and through to `_get_log_handler`

### 5. Update youtube_dl.py — `pikaraoke/lib/youtube_dl.py`

- Add `temp_dir: str = ""` parameter to `build_ytdl_download_command`
- If non-empty, add `"--paths", f"temp:{temp_dir}"` to the yt-dlp args
- Update caller in `download_manager.py` to pass the value

### 6. Wire through karaoke.py — `pikaraoke/karaoke.py`

- After preferences load, resolve `self.temp_dir = get_temp_directory(self.temp_dir)`
- Pass `temp_dir` to `ProcessingManager`, `DownloadManager` (for yt-dlp), and anywhere `FileResolver` is created

### 7. UI entry — `pikaraoke/templates/info.html` + `pikaraoke/routes/info.py`

- In `info.py`: pass `temp_dir=k.temp_dir` to template context
- In `info.html`: add a text input in the **Server settings** section:
  ```html
  <div class="user-preference-container is-align-items-center">
    <input id="pref-temp-dir" class="user-preference-input input" type="text"
           data-pref="temp_dir" data-start-value="{{ temp_dir }}" value="{{ temp_dir }}" />
    <label class="label" for="pref-temp-dir">Temporary files directory (blank = ~/.pikaraoke/tmp)</label>
  </div>
  ```

### 8. CLAUDE.md rule

Add under an appropriate section:

```
## Temporary Files

All non-persistent files (intermediate processing artifacts, logs, HLS segments,
download temp files) must use the centralized `temp_dir` preference from config.ini.
Never hardcode temp paths or use `tempfile.gettempdir()` directly. Use
`get_temp_directory()` from `get_platform.py` to resolve the configured path.
```

## Verification

1. Start PiKaraoke, go to Info page > Server settings — verify temp dir field shows `~/.pikaraoke/tmp`
2. Change the temp dir path in the UI, reload — verify it persists
3. Download a song — verify yt-dlp .part files go to the configured temp dir
4. Play a song — verify HLS segments appear in `<temp_dir>/<pid>/`
5. Trigger stem processing — verify intermediate WAV files and `processing_manager.log` appear in configured temp dir
6. Run `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
7. Run `python -m pytest`
