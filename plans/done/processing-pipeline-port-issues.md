# Processing Pipeline Port — Issues Analysis

Analysis of `plans/processing-pipeline-port.md` against the actual codebase and
the prototype at `mpv/pipeline/`.  The prototype exists and the plan's line-number
references are accurate.

Date: 2026-04-29

______________________________________________________________________

## CRITICAL

### 1. No database migration version-checking wrapper

The current `KaraokeDatabase._create_schema()` (karaoke_database.py:66–69) is:

```python
def _create_schema(self) -> None:
    self._conn.executescript(_SCHEMA)
    with self._conn:
        self._conn.execute("PRAGMA user_version = 1")
```

There is no conditional logic — `_migrate_v2_loudnorm()` and
`_migrate_v3_processing_status()` would run on every `_create_schema()` call
whether or not they are needed.

The plan must add a version-checking wrapper:

```python
def _create_schema(self) -> None:
    self._conn.executescript(_SCHEMA)
    cur = self._conn.execute("PRAGMA user_version").fetchone()[0]
    if cur < 2:
        self._migrate_v2_loudnorm()
    if cur < 3:
        self._migrate_v3_processing_status()
    with self._conn:
        self._conn.execute("PRAGMA user_version = 3")
```

The individual migrations are idempotent (check `table_info` before `ALTER TABLE`),
so the behavior is accidentally correct without the guards, but relying on this is
fragile. A future refactor that removes a migration (thinking the schema string now
includes the column) would silently break upgrades from version 1.

**Recommendation:** Add the `if cur < N:` guards shown above.

______________________________________________________________________

### 2. `_stems_already_exist` check is insufficient for the 5-stage pipeline

The plan defines `_stems_already_exist` (line 578) as checking only vocal/nonvocal
M4A files:

> Returns True iff both `vocal/{stem}---vocal.m4a` and
> `nonvocal/{stem}---nonvocal.m4a` exist.

In the prototype, `FFmpegTranscodeStage` promotes both M4As to final destinations
with `shutil.move()` at the **end** of its stage (ffmpeg_transcode.py:60–64),
before `LyricAlignStage` even begins. If the pipeline is cancelled during
`LyricAlignStage`, the M4As are already in their final locations but the `.ass`
and `.srt` (lyric_align.py:140–153) are only in `ctx.tmp_dir` and get cleaned up
by the orchestrator's `finally: shutil.rmtree(tmp_dir)`.

On the next run, `_stems_already_exist` returns `True`, the entire pipeline is
skipped, the song is marked `'ready'`, and it winds up singable **with no
karaoke subtitles**.

The same scenario occurs if `lyric_align` fails but transcode succeeded.

**Recommendation:** Either:

a) Extend `_stems_already_exist` to also check for `karaoke/{stem}.ass` (the
minimum required output for karaoke playback per `playback_controller.py:204`),
OR
b) Gate the early-exit on `processing_status` — only skip when the status is
already `'ready'` or `'skipped'`. If `'pending'` or `'failed'`, always run
the pipeline and let individual stages be internally incremental.

Option (b) is cleaner and aligns with the plan's own intent of using
`processing_status` as a gate. The current plan has `_stems_already_exist` acting
as a bypass around the status system.

______________________________________________________________________

## HIGH

### 3. `_SCHEMA` string not updated alongside ALTER TABLE migrations

The plan adds `loudnorm_offset_db` and `processing_status` columns via
`ALTER TABLE` migrations but never updates the `_SCHEMA` SQL constant
(karaoke_database.py:9–38). For fresh databases, `CREATE TABLE IF NOT EXISTS`
creates the old structure and migrations add the columns. This works, but:

- If someone later adds the columns to `_SCHEMA` (as good practice), the ALTER
  TABLE migration will fail (column already exists).
- If someone later removes the migration code (thinking the schema now includes
  the columns), the `user_version` check won't catch it.

**Recommendation:** Update `_SCHEMA` to include both new columns with their
defaults, AND keep the migration methods for idempotent upgrades from prior
versions.

______________________________________________________________________

### 4. `build_song_record` path needs explicit handling for `processing_status`

The plan says (line 261–264):

> The path that inserts a song row in response to `song_downloaded` writes
> `processing_status = 'pending'` on the INSERT (locate during implementation).

The actual ingestion path is `song_manager.register_download(song_path)` →
`_db.insert_songs([build_song_record(song_path)])`.
`build_song_record` (library_scanner.py:14–24) constructs a dict with
**exactly three keys**: `file_path`, `youtube_id`, `format`.

To set `'pending'` on download insert, this function must be modified. However,
`build_song_record` is also called by `library_scanner.scan()`, which would
then also set `'pending'` — contradicting the plan's intent that pre-existing
scanned songs default to `'skipped'`.

**Recommendation:** Either:

a) Add `"processing_status": "pending"` to `build_song_record` and have
`scan()` override it to `'skipped'` on its bulk insert, or
b) Add a separate `processing_status` parameter to `build_song_record` (default
`"skipped"`), and have `register_download` call it with `"pending"`.

This is not a "locate during implementation" detail — it's a design decision
that affects whether library-scanned songs get swept into the pipeline backlog.

______________________________________________________________________

### 5. PTY file descriptor lifecycle and ownership is unclear

The plan captures `pty_slave_fd` in `start()` and uses it in three places:
`StemWorker` (subprocess dup2/close), `PreparePtyStage` (seeds
`ctx.artifacts`), and `run_ffmpeg()` (via artifact). The plan does not show
where this fd is closed in the parent process.

The current production code has the same pattern (fd captured in `start()`,
used for the lifetime of the manager, never explicitly closed), so this is not
a regression. However, the prototype's `run_ffmpeg()` (lines 33–37 of
`_ffmpeg_helpers.py`) currently uses `stdout=subprocess.DEVNULL` — the
plan's PTY routing change replaces this with the actual fd. If the fd is closed
prematurely (e.g., by `ProcessTerminal.stop()`), subsequent
`subprocess.Popen(..., stdout=pty_fd)` calls will get `EBADF`.

**Recommendation:** Explicitly state that the slave fd is owned by
`ProcessingManager` and only closed in `stop()` after the orchestrator thread
joins. `ProcessTerminal` should not close the slave fd independently.

______________________________________________________________________

### 6. `processing_skipped` event not subscribed in `PipelineTracker`

The plan introduces `"processing_skipped"` (line 453) emitted when
`enqueue()`'s blocked-words filter rejects a song, and describes it as:

> lets `pipeline_tracker` clear the row from its in-flight set immediately

But `PipelineTracker._subscribe_events()` (pipeline_tracker.py:76–84) only
subscribes to 7 events: `download_queued`, `song_downloaded`, `download_error`,
`processing_complete`, `processing_cancelled`, `processing_error`,
`song_deleted`. **No handler for `"processing_skipped"` exists.**

**Recommendation:** Add the subscription and implement a handler that clears
the item from `_items` (or marks its status `"skipped"`) when the event fires.

______________________________________________________________________

### 7. Subtitle language selection is unverified

`download_manager._move_downloaded_subtitle()` (line 446–476):

- Globs for `*.srt`, `*.vtt`, `*.srv3`, `*.ttml` in the song directory.
- Picks the **first** `.srt` by filesystem order.
- Deletes **all other subtitle files** (all formats, all languages).

If yt-dlp produces multiple `.srt` files (e.g., `en.srt`, `es.srt`,
`fr.srt`), a non-English file may survive, depending on filesystem ordering.
The plan's `_resolve_lyrics_path` then picks that up, and `LyricAlignStage`
would try to align non-English text against an English vocal track — producing
garbled output.

The transcript path (no `.srt` → whisper transcribe) is unaffected because it
forces `whisper_language = "en"` in the config.

**Recommendation:** Either:
a) Add `--sub-lang en` to yt-dlp options (best: prevents non-English downloads
entirely),
b) Filter `.srt` files by language prefix in `_move_downloaded_subtitle`
(prefer `*.en.srt`, fall back to any `.srt`), or
c) Have `_resolve_lyrics_path` try `{stem}.en.srt` first, then `{stem}.srt`.

______________________________________________________________________

## MEDIUM

### 8. No mention of `files.html` template or `files.browse` route changes for status badges

The plan's Library Gating section (line 610–627) describes badge rendering:

> render a badge for each row whose status is currently in `pipeline_tracker`'s
> in-flight set OR whose persisted status is `'pending'` / `'failed'`

But `files.browse` (files.py:40–115) passes only raw song paths from
`song_manager.songs` to the template. No `processing_status` query or
`PipelineTracker.get_status()` call exists.

**Recommendation:** Add a subsection specifying:

- The route should join DB processing_status with PipelineTracker's in-flight
  set for each song.
- The template (`files.html`) should render a badge or indicator per row.
- The changes should be localized enough that a UI reviewer can find them.

______________________________________________________________________

### 9. WhisperWorker output goes to the main terminal, not the secondary PTY

The plan says: "WhisperWorker is in-process … No PTY work needed there."

The prototype's WhisperWorker logs via `logging.StreamHandler(sys.stderr)` and
inherits the parent process's stderr. This means whisper transcription/alignment
output (model loading progress, VAD messages, stable-ts logs, encoder pass
counts) will appear in the **main application terminal** (where Flask logs
appear), not in the secondary PTY terminal where stem worker and ffmpeg output
are routed.

This is inconsistent — users currently see all processing output in the
secondary terminal.

**Recommendation:** Consider routing WhisperWorker output to the PTY as well.
Since it's in-process, this would need `sys.stderr` redirection around the
whisper calls. Mark this as a conscious tradeoff in the plan.

______________________________________________________________________

### 10. `cancel_pending` does not emit an event

```python
def cancel_pending(self, song_path: str) -> None:
    with self._state_lock:
        if song_path in self.pending_jobs:
            self.pending_jobs.remove(song_path)
        self._cancelled_paths.add(song_path)
```

No event is emitted. The current code has the same behavior, and
`PipelineTracker.cancel()` handles its own state cleanup after calling
`cancel_pending()`. However, no external observer (SSE clients, etc.) can
react to a pending cancellation without polling `pending_jobs`.

**Recommendation:** Low priority, but consider emitting `"processing_cancelled"`
from `cancel_pending` as well. The event handler already distinguishes
pending vs active by matching song_path.

______________________________________________________________________

### 11. Migration `user_version` jumps from 1 to 3

Not technically wrong, but unusual and potentially confusing for future
maintainers. The two migrations (v2 and v3) could coexist in one step.

**Recommendation:** Either combine into one version step (v2) or add a comment
explaining the skip.

______________________________________________________________________

### 12. `PipelineConfig.intermediate_dir` type inconsistency

The plan says (line 86): "adapter derives via `get_temp_directory(...)` and
passes a resolved Path through", but then (line 391): "assign to
`self._config.intermediate_dir` as a string". Python's `tempfile.mkdtemp(dir=)`
accepts both, so this is cosmetic, but inconsistent type treatment could
cause mypy/pyright issues.

**Recommendation:** Pick one type (prefer Path) and use it consistently.
`get_temp_directory()` currently returns `str` — this could be updated to
return `Path` or the assignment could wrap it.

______________________________________________________________________

### 13. Breaking model path change buried in verification section

The plan's verification step 3 (line 689–697) reveals:

> This is a **breaking change from current behaviour** — the existing pipeline
> relies on audio-separator's auto-download cache at
> `./audio-separator/models/vocals_mel_band_roformer.ckpt`. The new pipeline does
> **not** auto-download; if the model file is missing, the first stem_separation
> will fail.

This is in the verification section and would be missed by anyone not carefully
reading the full plan. It should be prominently called out in the Context or
Goals sections, and must be included in release upgrade notes.

**Recommendation:** Move this warning to the top of the plan (Context section)
so implementers and reviewers see it immediately.

______________________________________________________________________

### 14. Processing status naming collision with PipelineItem

`PipelineTracker.PipelineItem` already has a `processing_status` field
(pipeline_tracker.py:44–46) with values `waiting | pending | active | complete | error | cancelling`. The proposed DB column is also called `processing_status`
with values `pending | ready | failed | skipped`.

These are **different concepts** — the tracker field is per-job in-flight state
(for the processing.html page), while the DB column is persistent per-song
pipeline state (for library gating). The identical name will cause confusion
during implementation.

**Recommendation:** Rename one. For example:

- DB column: `pipeline_state` or `processing_phase`
- Tracker field: unchanged (many templates/routes depend on it)

______________________________________________________________________

### 15. Queue route gating mentioned but not specified

The plan says (line 612–618) routes that enqueue for playback should check
`processing_status` and reject `'pending'`/`'failed'`, but no specific route
files or code changes are identified.

**Recommendation:** Add references to the specific routes/files that need
changes — at minimum `routes/queue.py:enqueue()`, any "play now" endpoint,
and the SSE flow for queue adds.

______________________________________________________________________

## LOW

### 16. WIP comment in `_process_song` needs cleanup

Lines 540–543 contain a confused design note:

```python
# Inject PTY fd so run_ffmpeg() routes stdout/stderr to the secondary
# terminal — the orchestrator owns the StageContext, so we pass via
# config rather than mutating ctx after the fact. Simpler approach:
# plumb pty_slave_fd through PipelineOrchestrator → StageContext.artifacts.
```

The `PreparePtyStage` approach (resolved later in the plan) makes this comment
obsolete. The code should drop it.

______________________________________________________________________

### 17. Unnecessary `threading.Lock` for lazy whisper loading

The plan adds a lock to `WhisperWorker._ensure_loaded()`. The orchestrator
processes one job at a time sequentially (the `_run_loop` is a single thread),
so there is no concurrent access. The lock has no benefit and adds complexity.

**Recommendation:** Simplify to a `bool` flag checked under the assumption of
single-threaded access.

______________________________________________________________________

### 18. No backoff for eager `StemWorker` restart on persistent failures

The `_run_loop` `finally` block restarts the stem worker after every job if it
died. If it died from a persistent condition (missing model, OOM), every subsequent
job produces a restart attempt and an error log.

**Recommendation:** Consider adding a backoff (exponential or capped retry
count) so a persistent failure doesn't flood logs on every queued job.

______________________________________________________________________

### 19. Prototype `requirements.txt` is unversioned — plan's pins are new

The prototype's `mpv/pipeline/requirements.txt` has unversioned dependencies:

```
stable-ts
faster-whisper
lyricsgenius
srt
audio-separator
#torch
```

The plan proposes versioned pins in `pyproject.toml`:

```
stable-ts>=2.17, faster-whisper>=1.0.3, srt>=3.5.3, torch>=2.2,
audio-separator[gpu]>=0.30
```

`lyricsgenius` is intentionally excluded (it's a non-goal). The pins are
reasonable but unverified — the prototype runs without specific version
constraints, so the pin values should be tested together before finalizing.

**Recommendation:** Test the dependency combination in a clean environment
before committing the plan's pins. Note that `torch>=2.2` may conflict with
other system packages — on Pi-class hardware this is a significant
constraint.

______________________________________________________________________

## SUMMARY TABLE

| # | Severity | Issue |
|---|----------|-------|
| 1 | CRITICAL | No DB migration version-checking wrapper |
| 2 | CRITICAL | `_stems_already_exist` doesn't check for `.ass` — can skip after partial cancel |
| 3 | HIGH | `_SCHEMA` string not updated alongside ALTER TABLE migrations |
| 4 | HIGH | `build_song_record` path for `processing_status` not specified (scan vs download conflict) |
| 5 | HIGH | PTY fd lifecycle and ownership unclear (when is it closed?) |
| 6 | HIGH | `processing_skipped` event not subscribed in `PipelineTracker` |
| 7 | HIGH | Subtitle language selection unverified (non-English `.srt` may survive) |
| 8 | MEDIUM | No mention of `files.html` template changes for status badges |
| 9 | MEDIUM | WhisperWorker output goes to main terminal, not secondary PTY |
| 10 | MEDIUM | `cancel_pending` doesn't emit an event |
| 11 | MEDIUM | Migration user_version jumps from 1 to 3 |
| 12 | MEDIUM | `PipelineConfig.intermediate_dir` type inconsistency (str vs Path) |
| 13 | MEDIUM | Breaking model path change buried in verification section |
| 14 | MEDIUM | `processing_status` naming collision (DB column vs `PipelineItem` field) |
| 15 | MEDIUM | Queue route gating mentioned but not specified |
| 16 | LOW | WIP comment in `_process_song` needs cleanup |
| 17 | LOW | Unnecessary `threading.Lock` for lazy whisper loading |
| 18 | LOW | No backoff for eager StemWorker restart on persistent failures |
| 19 | LOW | Prototype `requirements.txt` is unversioned — plan's pins are new |
