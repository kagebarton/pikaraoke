# scripts/

Standalone CLI tools that run from the repo root against a live PiKaraoke
song library.

## backfill_artifacts.py

Scans the song folder for video files and generates any missing
pipeline outputs (stems, karaoke `.ass`, subtitles `.srt`) using the
same pipeline stages as the running app.

### Usage

```bash
python scripts/backfill_artifacts.py [folder] [--dry-run] [--yes]
```

Default `folder` = `get_default_dl_dir()` (e.g. `~/pikaraoke-songs`).
`--dry-run` prints the report and exits. `--yes` skips the
post-report confirmation prompt.

### Flow

1. **Scan** — enumerate video files in `folder`, classify per-song
   missing artifacts:
   - `stems` — both `vocal/<stem>---vocal.m4a` and
     `nonvocal/<stem>---nonvocal.m4a` present?
   - `karaoke` — `karaoke/<stem>.ass` present?
   - `subtitles` — `subtitles/<stem>.srt` OR `<stem>.en.srt` present?
     (The `.en.srt` form is YouTube captions; either counts.)
2. **Report + confirm** — print a table of songs and their missing
   artifacts. Confirm before proceeding unless `--yes`.
3. **Interactive Genius prompt** — for each song needing lyric work
   (`karaoke` or `subtitles` missing), prompt up front:
   ```
   <song name>
     search query [<default>]: <enter or edit>
     1) Title - Artist
     ...
     choose [1-N/s/t/k or new query]:
   ```
   Options: numbered hit picks Genius lyrics; `s` = use local SRT;
   `t` = transcribe (no reference lyrics); `k` = skip song entirely;
   any other input is treated as a new search query.

   Selections are stashed via `genius.write_choice()` (the same sidecar
   format `LyricsFetchStage` consumes from the live app), so phase 4
   runs unattended.
4. **Run unattended** — per song, build a *minimal* stage list (see
   `build_stages_for`) and run via `PipelineOrchestrator.run_one`.
   Stem worker starts only if any job needs stems; whisper worker only
   if any job needs lyric work.

### Stage selection

`build_stages_for(missing, ...)` constructs the per-song stage list:

| Missing                      | Stages                                                                                       |
|------------------------------|----------------------------------------------------------------------------------------------|
| `stems`                      | `FFmpegExtractStage → LoudnormAnalyzeStage → StemSeparationStage → FFmpegTranscodeStage`     |
| `stems` + (karaoke/subs)     | `LyricsFetchStage → ... full chain ... → LyricAlignStage`                                    |
| karaoke and/or subs only     | `LyricsFetchStage → LoadVocalFromM4aStage → LyricAlignStage`                                 |

`LoadVocalFromM4aStage` (in `pikaraoke/pipeline/stages/load_vocal.py`)
decodes the cached `vocal/<stem>---vocal.m4a` back to a WAV in
`tmp_dir` and populates `ctx.artifacts["vocal_wav"]`. This lets the
align path reuse the cached separator output instead of re-running
~50s of stem separation per song.

Tradeoff: whisper sees AAC-decoded audio rather than the raw separator
WAV. Acceptable for alignment (whisper resamples to 16k mono anyway).

## Architecture notes

### Why a separate script, not a Flask route?

This is a maintenance tool intended to run interactively against an
idle library — typically with the main app stopped (to free GPU
memory). It doesn't need PTY streaming, queue management, or any of
the live-app machinery; it can talk to `stdin`/`stdout` directly and
use `PipelineOrchestrator.run_one()` synchronously.

### Reuse vs duplication

The CLI does **not** rebuild the pipeline from scratch — it imports
the same stage classes, workers, and config as
`pikaraoke.lib.processing_manager`. The two diverge in:

1. **Stage list construction.** `processing_manager.start()` hardcodes
   the full stage list; this CLI's `build_stages_for()` picks subsets.
2. **No PTY.** ffmpeg subprocess output goes to `DEVNULL`; Python
   logging goes to stderr.
3. **No queue.** Songs run serially in a simple `for` loop. No
   cancellation, no event system, no song manager.

### What changes in the pipeline propagate automatically?

- Stage internals (`lyric_align.py` matchers, fallbacks, escalation,
  walk/tiling/auto logic) — picked up because the CLI imports the
  stage class directly.
- `PipelineConfig` defaults (thresholds, colors, styling, model paths,
  etc.) — `PipelineConfig()` is instantiated in `main()`.
- Worker internals (stem, whisper subprocess logic).

### What requires updating the CLI?

- **Adding a new pipeline stage.** Both `processing_manager.start()`
  and `scripts/backfill_artifacts.py:build_stages_for()` hardcode the
  stage list. New stages must be threaded into both.
- **Renaming a stage class** or changing its constructor signature.
- **Changing on-disk artifact paths/names** (`vocal/<stem>---vocal.m4a`,
  `karaoke/<stem>.ass`, etc.). Both `_missing_artifacts()` (the
  scanner) and `LoadVocalFromM4aStage` (the m4a→wav decoder) hardcode
  these paths.

### Reducing drift

The cleanest fix for the stage-list duplication would be to extract a
shared `build_full_pipeline_stages(...)` helper that both
`processing_manager.start()` and this CLI consume. Then the CLI only
owns the "which subset for which missing set" logic. Not done yet.

## Known limitations / ideas

- **One song at a time.** No parallelism. Stems and whisper are GPU-bound
  so this is fine on a single-GPU box, but a multi-GPU setup could
  pipeline stems(song N+1) against align(song N).
- **No resume.** A crash mid-run loses no artifacts (they're written
  atomically per stage), but already-prompted Genius choices for
  songs that didn't run yet are left as stale sidecar JSON in the
  temp `lyric_choices/` dir. `LyricsFetchStage.delete_choice()`
  cleans them up on successful consumption, but skipped or crashed
  songs leave them behind. A `--resume` mode could just rely on the
  scan re-running.
- **Genius search query default** is `clean_search_query(stem - yt_id)`,
  which sometimes underperforms vs. just the title. Could try a few
  variants (title-only, title+primary-artist) and merge results.
- **No SRT-only generation.** The pipeline writes ASS and SRT together
  from the same line objects; you can't generate `.srt` without also
  rewriting `.ass`. Acceptable for now.
- **Hardcoded VIDEO_EXTS.** Mirrors `SongList.VALID_EXTENSIONS`
  minus `.mp3` and `.zip`. If that set changes, update both.
- **No dry-run for the Genius prompt** — `--dry-run` exits after the
  scan report. A "dry plan" mode that walks the prompts without
  running could help when batching a big backfill.
- **PreferenceManager** is loaded via the default `config.ini` lookup;
  no way to point at a different config from the CLI. Add a
  `--config` flag if needed.

## Files

- `scripts/backfill_artifacts.py` — the CLI.
- `pikaraoke/pipeline/stages/load_vocal.py` — `LoadVocalFromM4aStage`,
  added for this tool but reusable elsewhere.
