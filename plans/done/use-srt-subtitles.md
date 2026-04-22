Model: Claude Opus 4.6

# Switch yt-dlp to SRT subtitles, separate from future ASS karaoke captions

## Context

Today, yt-dlp is configured to convert downloaded YouTube captions to `.ass` and the rest of the code treats `.ass` as the canonical subtitle format. The user is changing this so that:

- **`.srt`** = closed captions downloaded from YouTube via yt-dlp (the only thing yt-dlp will produce going forward).
- **`.ass`** = karaoke-styled captions generated later from *confirmed* lyrics via stable-ts, stored in a separate folder. Not produced by this change; this plan only needs to stop conflating the two and make future coexistence easy.
- **In the future**, both file types will live side-by-side as companion files and the user will pick which to render per playback via a preference.

Extension is the discriminator — `.srt` means "subtitle", `.ass` means "karaoke caption". No umbrella rename needed; method names that currently say "ass" or generic "subtitle" but only mean the downloaded closed-captions path should be renamed to `subtitle`/`srt`-specific names so the future `.ass` code path has a clean namespace.

An incidental finding while exploring: the `format` column in the `songs` table is only ever written, never read (grep of `pikaraoke/` confirmed). The existing `"ass"` special case in `_detect_format` is dead signal. This plan removes it along with the now-unneeded `files_in_dir` / `files_lower` plumbing in `library_scanner`.

Case-sensitivity decision (confirmed with user): **lowercase `.srt` only**. We control the producer (yt-dlp always writes lowercase), so the existing ASS case-variant loops (`.ass/.ASS/.Ass`) get dropped rather than carried over.

## Files to modify

### 1. [pikaraoke/lib/youtube_dl.py](pikaraoke/lib/youtube_dl.py)

**Change**: Flip yt-dlp's `--convert-subs` target.

- [line 157](pikaraoke/lib/youtube_dl.py#L157): `"ass"` → `"srt"`
- [lines 154-155](pikaraoke/lib/youtube_dl.py#L154-L155): remove the commented-out `--sub-format` / `best` lines (dead commented code per CLAUDE.md).

### 2. [pikaraoke/lib/download_manager.py](pikaraoke/lib/download_manager.py)

**Change**: Rename `_rename_subtitle_file` → `_move_downloaded_subtitle` and make it target `.srt`. Name reflects both what the method does (moves the file from song dir into `subtitles/`) and the source (downloaded closed captions, not karaoke captions).

- [line 352](pikaraoke/lib/download_manager.py#L352): call site — rename to `_move_downloaded_subtitle(song_path)`.
- [line 419](pikaraoke/lib/download_manager.py#L419): def `_move_downloaded_subtitle(self, video_path: str) -> None:`
- [line 423](pikaraoke/lib/download_manager.py#L423): `target = subtitles_dir / f"{video.stem}.srt"`
- [lines 425-430](pikaraoke/lib/download_manager.py#L425-L430): candidate extensions — drop `.ass`, keep `.srt` plus yt-dlp intermediates (`.vtt`, `.srv3`, `.ttml`) that may linger if `--convert-subs` leaves them behind.
  ```python
  candidates = {
      f
      for ext in (".srt", ".vtt", ".srv3", ".ttml")
      for f in video.parent.glob(f"{video.stem}*{ext}")
  }
  ```
- [line 432](pikaraoke/lib/download_manager.py#L432): rename local `ass_files` → `srt_files`, filter `f.suffix == ".srt"`.
- Update the "No subtitle found" and "Moved subtitle" log lines to say `subtitle` (already generic enough, just verify).

### 3. [pikaraoke/lib/playback_controller.py](pikaraoke/lib/playback_controller.py)

**Change**: Simplify `_find_subtitle` to lowercase `.srt`-only lookup in `subtitles/`. Delete the ASS case-variant loop and the stale comments. Leave the method name generic (`_find_subtitle`) so the future karaoke-caption branch slots in here behind a preference check.

- [line 103](pikaraoke/lib/playback_controller.py#L103): update the inline comment — `# Find subtitle file (.srt in subtitles/ subfolder)`.
- [lines 137-165](pikaraoke/lib/playback_controller.py#L137-L165): replace body with:
  ```python
  def _find_subtitle(self, file_path: str) -> str | None:
      """Find the downloaded-subtitle (.srt) companion for a media file.

      Karaoke captions (.ass, generated from confirmed lyrics) will be
      added here behind a user preference in a future change.
      """
      base_name = os.path.splitext(os.path.basename(file_path))[0]
      srt_path = os.path.join(os.path.dirname(file_path), "subtitles", base_name + ".srt")
      if os.path.exists(srt_path):
          logging.debug(f"SRT subtitle file found: {srt_path}")
          return srt_path
      return None
  ```
- Rename is intentionally NOT to `_find_srt_subtitle`: this is the dispatch point for the future preference-gated `.ass` branch, so the generic name stays accurate.

### 4. [pikaraoke/lib/song_manager.py](pikaraoke/lib/song_manager.py)

**Change**: Switch `_get_companion_files` to discover `.srt` in `subtitles/`. The rename logic at [line 123](pikaraoke/lib/song_manager.py#L123) already works off the basename tail suffix, so it handles `.srt` without changes.

- [lines 65-92](pikaraoke/lib/song_manager.py#L65-L92): Replace the ASS block with:
  ```python
  # Downloaded subtitles live in the subtitles/ subfolder as .srt
  srt_path = os.path.join(dirpath, "subtitles", base + ".srt")
  if os.path.exists(srt_path):
      companions.append(srt_path)
  ```
- Update the docstring at [line 66](pikaraoke/lib/song_manager.py#L66): `"""Return paths to companion files (.srt, vocal/nonvocal) ..."""`
- Update the "ASS subtitles live in..." comment.
- Leave a one-line comment marking where karaoke `.ass` companions will be added later (separate folder — name TBD, not decided in this plan).

### 5. [pikaraoke/lib/library_scanner.py](pikaraoke/lib/library_scanner.py)

**Change**: Delete the dead `_detect_format` companion branch and the `files_in_dir` / `files_lower` plumbing that exists solely to serve it. The DB `format` column is only ever written, never read, so the `"ass"` marker never mattered — but removing the plumbing simplifies the scan hot path (one fewer `os.listdir` pass worth of bookkeeping per directory).

- [lines 15-43](pikaraoke/lib/library_scanner.py#L15-L43): `build_song_record(file_path: str) -> dict` — drop both optional params, drop the `if files_in_dir is None` / `files_lower is None` setup, call `_detect_format(file_path)`.
- [lines 57-64](pikaraoke/lib/library_scanner.py#L57-L64): `_detect_format(file_path: str) -> str` — drop the `files_lower` param and the companion branch. Body becomes:
  ```python
  def _detect_format(file_path: str) -> str:
      """Detect the song format from its extension."""
      return os.path.splitext(file_path)[1].lstrip(".").lower()
  ```
- [lines 141-155](pikaraoke/lib/library_scanner.py#L141-L155): in `scan()`, remove the per-directory `files_in_dir` / `files_lower` caching block. The `records` comprehension collapses to:
  ```python
  records = [build_song_record(p) for p in to_insert]
  ```
- Update the "Inspects the file's directory for companion files..." docstring at [line 22](pikaraoke/lib/library_scanner.py#L22).

### 6. [pikaraoke/lib/mpv_controller.py](pikaraoke/lib/mpv_controller.py)

**No change.** The `"format": "ass-events"` at [line 544](pikaraoke/lib/mpv_controller.py#L544) is an mpv OSD overlay API parameter (mpv's internal ASS-events rendering format), not a file-format reference. Unrelated to this task. Flagged here so the search hits don't surprise a reviewer.

## Data / flow summary

**Download path (yt-dlp → disk)**

1. `DownloadManager` runs yt-dlp with `--write-subs --sub-langs en.* --convert-subs srt`.
2. yt-dlp writes `Title---VIDEOID.mp4` plus `Title---VIDEOID.en.srt` (and possibly intermediate `.vtt`/`.srv3`/`.ttml` if conversion is skipped for some streams) into the download dir.
3. After download, `DownloadManager._move_downloaded_subtitle(video_path)` creates `subtitles/` if needed, moves the `.srt` candidate to `subtitles/Title---VIDEOID.srt` (stripping the `.en` language tag), and deletes any leftover intermediate candidates.

**Playback path (database → mpv)**

1. `PlaybackController.play_file(file_path, ...)` calls `self._find_subtitle(file_path)`.
2. `_find_subtitle` returns `subtitles/<basename>.srt` if it exists, else `None`.
3. `mpv.play(..., subtitle_path=subtitle_path)` loads it.
4. Future: `_find_subtitle` will first consult a user preference (`caption_preference`: `"karaoke"` | `"subtitle"` | `"auto"`) and look in the karaoke-caption folder for `<basename>.ass` when appropriate, falling back to the current `.srt` path.

**Library management path**

- `LibraryScanner.scan()` rebuilds song records using only file paths — no companion inspection.
- `SongManager.delete()` / `rename()` discover `.srt` companions via `_get_companion_files` and propagate the operation. Future karaoke `.ass` companions will be added to the same list without changing callers.

## Tests to update

- [tests/unit/test_library_scanner.py:318-347](tests/unit/test_library_scanner.py#L318-L347): delete the two ASS-companion tests that assert `record["format"] == "ass"` (the branch they exercise is being removed). Keep the plain-mp4 / zip / mp3 assertions; they still work.
- [tests/unit/test_song_manager.py:123,150-156](tests/unit/test_song_manager.py#L123): swap `.ass` fixture files to `.srt` (same `subtitles/` subfolder). Assertions about the renamed companion become `New---abc.srt`.
- [tests/unit/test_download_manager.py](tests/unit/test_download_manager.py): any test that references `_rename_subtitle_file` → `_move_downloaded_subtitle`, any `.ass` fixture → `.srt`.
- [tests/unit/test_playback_controller.py](tests/unit/test_playback_controller.py): subtitle-discovery tests — remove ASS-preferred cases, keep a lowercase `.srt` happy-path test and a "no subtitle" test.
- [tests/unit/test_youtube_dl.py](tests/unit/test_youtube_dl.py): if any test asserts on the `--convert-subs` argument, update to `"srt"`.

## Verification

1. **Unit tests**
   ```
   /home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit/test_library_scanner.py tests/unit/test_song_manager.py tests/unit/test_download_manager.py tests/unit/test_playback_controller.py tests/unit/test_youtube_dl.py
   ```
2. **Code quality**
   ```
   pre-commit run --config code_quality/.pre-commit-config.yaml --all-files
   ```
3. **Manual end-to-end**
   - Start PiKaraoke against a writable songs dir.
   - Search and download a YouTube video that is known to have English captions.
   - Confirm on disk: `songs/Title---VIDEOID.mp4` exists and `songs/subtitles/Title---VIDEOID.srt` exists (lowercase, no `.en` language tag, no stray `.vtt`/`.ass`/`.srv3`).
   - Queue and play the song in mpv; confirm captions render on the video.
   - Rename the song from the UI; confirm the `.srt` companion is renamed alongside it.
   - Delete the song from the UI; confirm the `.srt` companion is also removed.
4. **Regression spot-check**
   - Play a song that has no captions available — confirm no errors, playback still works.
   - Trigger a library scan on a directory with a mix of mp4/mp3/zip files — confirm the scan completes and song count matches expectations.
