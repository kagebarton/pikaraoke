# Processing Pipeline Port — Review Findings

Model: Claude Opus 4.7 (z-ai/glm-5.1)

Reviewed: `plans/processing-pipeline-port.md` against the current codebase
(`pikaraoke/lib/processing_manager.py`, `stem_worker.py`, `karaoke_database.py`,
`download_manager.py`, `song_manager.py`, `playback_controller.py`,
`pipeline_tracker.py`, `youtube_dl.py`, `karaoke.py`, `pyproject.toml`,
`tests/unit/test_processing_manager.py`, and related plans).

---

## Critical Issues (must fix before implementation)

### C1: Prototype source directory `mpv/pipeline/` does not exist

The plan references `mpv/pipeline/` throughout (stages, workers, orchestrator,
config, context) as the prototype to port. **No such directory exists in the
repo.** There is no `mpv/` directory, no `mpv_prototype/` directory, and no
`pipeline/` directory anywhere under the project root. Globbing for
`**/orchestrator*`, `**/whisper_worker*`, and `**/run_pipeline*` all return
nothing.

**Impact:** The entire port is blocked. The plan assumes complete prototype
code to copy from. Without it, every file listed under "File layout" must be
written from scratch — not ported. The plan's line references (e.g.,
`mpv/pipeline/stages/lyric_align.py:55-114`) are unverifiable.

**Recommendation:** Locate the prototype code (separate repo? local branch?
uncommitted?) and either commit it to the repo under the referenced path or
rewrite the plan to describe the prototype's interfaces as design
specifications rather than copy-and-adapt instructions.

---

### C2: `LyricAlignStage` and `WhisperWorker` are undefined — no interface spec

The plan says "the prototype's stage and worker code is complete" and "only the
subtitle generation logic… is unfinished," but the referenced prototype files
don't exist (see C1). The adapter's `_process_song` calls
`orchestrator.run_one_async(Path(song_path), lyrics_path)` and later reads
`ctx.artifacts.get("loudnorm_target_offset")`, but there's no specification of
what `run_one_async` returns, what `StageContext` looks like, what
`PipelineOrchestrator.join()` does, or what the `CancelToken` interface is.

**Impact:** The adapter rewrite depends on an API contract that's only
documented by reference to nonexistent files. The plan provides pseudocode for
the adapter but not for the pipeline internals it calls.

**Recommendation:** Add a section defining the `PipelineOrchestrator`,
`StageContext`, `CancelToken`, and `Cancellable` interfaces explicitly
(signatures, return types, artifact keys). This is the contract the adapter
depends on.

---

### C3: `song_manager` constructor change breaks the public API guarantee

The plan adds `song_manager: SongManager` as a **new required parameter** to
`ProcessingManager.__init__` (line 237). The plan's own "Public API (unchanged
from today)" header says the API doesn't change, then immediately adds a
parameter.

Current code at `karaoke.py:286-291`:
```python
self.processing_manager = ProcessingManager(
    events=self.events,
    preferences=self.preferences,
    temp_dir=self.temp_dir,
    log_level=self.log_level,
)
```

The plan says `karaoke.py:286-292` adds `song_manager=self.song_manager`. This
is a **breaking change** to the constructor signature. The claim "No other call
sites change" is correct only if `karaoke.py` is the sole construction site, but
the test fixture also constructs `ProcessingManager` without `song_manager`:

```python
# tests/unit/test_processing_manager.py:28-30
def manager(events, preferences):
    return ProcessingManager(events=events, preferences=preferences)
```

**Impact:** All existing tests and any other construction sites break. The plan
acknowledges the `karaoke.py` change but doesn't mention the test fixture
updates needed (the test section says to delete some tests and replace with
mocked-orchestrator tests, but the fixture also feeds
`TestProcessingManagerInit` and `TestProcessingManagerEnqueue`, which would
need the new parameter).

**Recommendation:** Make `song_manager` optional with a default of `None`
(acceptable since loudnorm persistence is a new feature, not a hard dependency).
Or explicitly enumerate every construction site that needs updating.

---

### C4: Stem model name mismatch — existing `stem_worker.py` hardcodes a different model

The plan changes `separator_model_name` from `vocals_mel_band_roformer.ckpt` to
`mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` and says models live
in `<repo_root>/models/`. But the current `stem_worker.py:16-19` has:

```python
MODEL_NAME = "vocals_mel_band_roformer.ckpt"
MODEL_DIR = "./audio-separator/models"
```

The current `MODEL_DIR` points to audio-separator's auto-download cache
(`./audio-separator/models`), not `<repo_root>/models/`. The plan silently
changes both the model name and the model directory convention. Users who
currently have a working stem separation with the cached roformer model will
find the new pipeline looking for a different model in a different directory
with no automatic download.

**Impact:** On upgrade, stem separation breaks with a "model not found" error
unless the user manually copies the new model file. There's no migration path
or fallback. The plan mentions "the user copies them in; no download step in
the project," but this is a breaking change from the current behavior where
audio-separator auto-downloads the model on first run.

**Recommendation:** Either (a) keep audio-separator's auto-download behavior as
a fallback if the file isn't in `<repo_root>/models/`, (b) add a startup check
that logs a clear error if the model file is missing, or (c) document the
migration step in the verification section.

---

## Significant Issues (should fix)

### S1: `_cleanup_stems` is missing from the adapter's error/cancel paths

The current `processing_manager.py:209-219` calls `self._cleanup_stems()` on
both cancel and error. The plan's `_process_song` pseudocode (lines 394-431)
emits events on cancel/error but **does not call `_cleanup_stems`**. This means
partial stem files (`vocal/Song---vocal.m4a`, `nonvocal/Song---nonvocal.m4a`)
and intermediate temp directories survive a failed or cancelled pipeline run.

The next time that song is enqueued, `_stems_already_exist` will find the
partial vocal file and skip the song — emitting `processing_complete` for a
song with corrupt/incomplete stems.

**Impact:** Silent data corruption. A cancelled song gets marked "complete"
with partial stems on re-enqueue.

**Recommendation:** Add `_cleanup_stems(song_path)` calls to the
`PipelineCancelled` and generic `Exception` handlers in `_process_song`,
mirroring the current code. Also call it when `_stems_already_exist` returns
True if the user explicitly re-enqueues (optional enhancement).

---

### S2: `_stems_already_exist` skip silently emits `processing_complete`

The plan (line 396-398) says:
```python
if self._stems_already_exist(song_path):
    self._events.emit("processing_complete", song_path)
    return
```

The current code (line 241-243) also skips and emits `processing_complete`,
but **only** within the `_run_pipeline` call, which is wrapped by the
orchestrator loop that also sets `_active_state = None` and cleans up
`pending_jobs`. In the plan's version, `_process_song` returns after emitting
the event, but the `_run_loop` (lines 369-389) also sets `self._active = None`
and removes from `pending_jobs`. This works, but there's a subtle difference:
the current code logs `"Stems already exist, skipping"` — the plan drops that
log line. More importantly, the `PipelineTracker` will see a
`processing_complete` event for a song that was never in the "active"
processing state, which is fine but could be confusing if the tracker doesn't
find the item.

**Impact:** Minor. The event is harmless but could confuse diagnostics.

**Recommendation:** Add the log line back. Consider emitting a different event
(e.g., `processing_skipped`) if tracker semantics matter.

---

### S3: Eager stem-worker restart is missing from the orchestrator loop

The current orchestrator loop (`processing_manager.py:226-231`) has an
**eager restart** in the `finally` block:

```python
finally:
    with self._state_lock:
        if song_path in self.pending_jobs:
            self.pending_jobs.remove(song_path)
        self._active_state = None
    # Eager restart: if cancel or crash killed the worker, bring
    # it back before the next job arrives.
    if not self._stem_worker.is_alive():
        try:
            self._stem_worker.start()
        except Exception as e:
            logging.error(f"Failed to restart stem worker: {e}")
```

The plan's `_run_loop` (lines 369-389) drops this entirely:

```python
with self._state_lock:
    self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
    self._active = None
```

If the stem worker dies during a cancelled job (e.g., OOM crash during
separation), the next enqueued song will fail immediately because the worker
isn't alive, and `StemSeparationStage` will presumably raise an error.

**Impact:** The pipeline becomes fragile after any worker crash. The existing
robustness guarantee is lost.

**Recommendation:** Add the eager-restart check back to `_run_loop`'s finally
block. This was specifically designed for this scenario (see
`pipeline-refactor.md:226-231` and `pipeline-robustness-fixes.md:A1`).

---

### S4: PTY fd through `PipelineConfig` is a process-global side channel

The plan (lines 440-450) chooses option 2: add `pty_slave_fd: int | None =
None` to `PipelineConfig`. But `PipelineConfig` is a dataclass shared across
all stages and the orchestrator. Putting a process-specific fd (which changes
per run, per platform, and is meaningless in a worker subprocess) into a
config object conflates configuration with runtime state.

This also means:
- If `PipelineConfig` is ever serialized (e.g., logged, pickled for IPC), the
  fd integer leaks as a meaningless number.
- If someone constructs a `PipelineConfig` independently (e.g., in tests or a
  CLI runner), they'd need to know to set `pty_slave_fd` — violating the
  separation the plan explicitly wants ("PipelineConfig stays a plain dataclass
  with no Pikaraoke imports").

**Impact:** Design smell that will cause confusion. Not a bug today, but the
plan's own rationale ("PipelineConfig stays a plain dataclass with no Pikaraoke
imports") is contradicted by this choice.

**Recommendation:** Option 1 (a `PreparePtyStage` that writes into
`ctx.artifacts`) is cleaner — it keeps runtime state in the per-job context,
not in the shared config. Alternatively, pass `pty_slave_fd` through the
`StageContext` constructor or as a separate argument to `run_one_async`.

---

### S5: `WhisperWorker` is "in-process" but the plan also calls `orchestrator.start()` to "load whisper model"

Line 316: `self._orchestrator.start()` — "loads whisper model, spawns stem
worker." But `WhisperWorker` is described as "in-process" (line 111). Loading a
large Whisper model (~1.5 GB for large-v3-turbo) in the main process at app
startup means:

1. **Memory pressure.** The Whisper model + the stem model (~400 MB) are both
   resident before any song is processed. On a Raspberry Pi with 4 GB RAM, this
   is significant.
2. **Startup latency.** Loading the Whisper model can take 10-30 seconds on
   slow hardware. The plan puts this in `start()`, which blocks app startup.
3. **No lazy loading option.** If no song ever needs transcription (all songs
   have `.srt` files), the Whisper model was loaded for nothing.

**Impact:** Significant on resource-constrained devices (the project's stated
target includes Raspberry Pi).

**Recommendation:** Consider lazy-loading the Whisper model on first
transcription request, or making the LyricAlign stage a no-op when
`lyrics_path` is provided (SRT mode). Document the memory and startup cost in
the plan.

---

### S6: `playback_controller.py` already has a placeholder for `normalization_db`

At `playback_controller.py:123-130`:
```python
normalization_db = None
if self.preferences.get_or_default("normalize_audio"):
    # Normalization value will be fetched from song database when implemented
    normalization_db = None  # Will be populated when ProcessingManager stores it
```

The plan adds `loudnorm_offset_db` to the database and a `SongManager` forwarder
but **does not wire it into `playback_controller.py`**. The plan explicitly
lists this as a non-goal ("Wiring loudnorm offset into mpv playback gain. This
plan only stores it."), which is fine. However, the plan also doesn't update
`SongManager` or `playback_controller.py` to **read** the stored value, even
though the infrastructure is already there to consume it.

**Impact:** The column gets written but never read. This is by design per the
non-goals, but the plan should note that the playback_controller plumbing
exists and is ready to be wired up — otherwise the next implementer may not
realize it.

**Recommendation:** Add a note to the plan pointing to
`playback_controller.py:123-130` as the integration point for the follow-up
work.

---

### S7: `song_manager._get_companion_files` doesn't include `.ass` files yet

At `song_manager.py:70-71`:
```python
# Karaoke captions (.ass, generated from confirmed lyrics) will be added here
# in a separate subfolder in a separate change.
```

The plan's pipeline writes `karaoke/*.ass` output, but `SongManager.delete()`
won't clean up the `.ass` file when a song is deleted. The `.ass` file becomes
an orphan.

**Impact:** Orphaned `.ass` files on song deletion. Not catastrophic, but the
plan introduces output that the cleanup code doesn't know about.

**Recommendation:** Add `karaoke/{stem}.ass` to `_get_companion_files()` as
part of this change. The playback_controller already looks for
`{parent}/karaoke/{base_name}.ass` (line 204), confirming the convention.

---

## Minor Issues (worth noting)

### M1: `_resolve_lyrics_path` only checks the first `.srt` candidate

The plan's adapter helper (lines 144-153):
```python
candidate = song.parent / "subtitles" / f"{song.stem}.srt"
return candidate if candidate.is_file() else None
```

This is correct given that `_move_downloaded_subtitle` in `download_manager.py`
already renames any downloaded `.srt` to `{stem}.srt` (stripping the language
code). However, if a user manually places a differently-named `.srt` in the
`subtitles/` folder, it won't be found. The current
`_move_downloaded_subtitle` (line 453-457) also searches for `*.vtt`,
`*.srv3`, `*.ttml` and converts them. The plan's resolver ignores these.

**Recommendation:** Either document that only yt-dlp-placed `.srt` files are
supported, or add a fallback glob for any `.srt` matching the stem.

---

### M2: Database migration relies on `PRAGMA table_info` but doesn't check `PRAGMA user_version`

The plan's `_migrate_v2_loudnorm` (lines 179-184) uses
`PRAGMA table_info(songs)` to check if the column exists. This is idempotent
and correct. However, the `_create_schema` method sets
`PRAGMA user_version = 2` unconditionally after the migration (line 177). If
the migration somehow fails partway (unlikely with a single `ALTER TABLE`, but
possible if the DB is locked), the version would be set to 2 even though the
column doesn't exist.

**Recommendation:** Move the `PRAGMA user_version = 2` inside the same
transaction as the `ALTER TABLE`, or check user_version before running the
migration:

```python
def _create_schema(self) -> None:
    self._conn.executescript(_SCHEMA)
    version = self._conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        self._migrate_v2_loudnorm()
        with self._conn:
            self._conn.execute("PRAGMA user_version = 2")
```

---

### M3: `pyproject.toml` dependency additions need version reconciliation

The plan proposes adding `audio-separator[gpu]>=0.30`, `stable-ts>=2.17`,
`faster-whisper>=1.0.3`, `srt>=3.5.3`, and `torch>=2.2`. Currently
`pyproject.toml` has **none** of these. Notably:

- `torch>=2.2` is a very heavy dependency (~2 GB). It's already implicitly
  required by audio-separator and stable-ts, but making it explicit in
  `pyproject.toml` means `pip install pikaraoke` would try to install PyTorch,
  which may fail on some platforms (ARM, Alpine musl, etc.).
- `audio-separator[gpu]` has a `[gpu]` extra that pulls in
  `torch[cuda]`-specific dependencies. This is platform-dependent and may
  break on non-CUDA systems.
- The current code imports `audio_separator` at runtime (inside
  `_stem_worker_main`), so the dependency is implicit. The plan makes it
  explicit, which is good for correctness but changes the install behavior
  significantly.

**Recommendation:** Make the ML dependencies optional extras (e.g.,
`pikaraoke[ml]` or `pikaraoke[gpu]`) so the base install doesn't require
PyTorch. The app already has a path without processing (blocked words, manual
mode).

---

### M4: `cancel_active` semantic change — no more per-step targeting

The current `cancel_active` (lines 149-177) does **surgical cancellation**:
it checks `_Step.EXTRACTING`/`_Step.TRANSCODING` and kills the FFmpeg Popen,
or does nothing during `_Step.STEMMING` (delayed cancel). The plan's
`cancel_active` (lines 345-353) just calls `orchestrator.cancel_active()`,
delegating to the orchestrator's `CancelToken`.

This is correct **if** the orchestrator's cancel mechanism preserves the
same semantics (kill FFmpeg subprocesses immediately, let the stem worker
finish). But the plan doesn't verify this — it just assumes the prototype's
`CancelToken` + `Cancellable` interface does the right thing. The current
behavior was specifically designed to avoid killing the stem worker during
separation (see `pipeline-refactor.md:394-402`).

**Recommendation:** Verify (or specify in the plan) that the pipeline's
cancel mechanism preserves the delayed-cancel-for-stem-workers behavior. The
plan mentions "KillProcess" for FFmpeg and "SetEvent" for workers, which
sounds right, but this should be an explicit assertion, not an assumption.

---

### M5: `pending_jobs` list mutation uses slice assignment — subtle difference

The plan (line 381, 387):
```python
self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
```

The current code uses `.remove()`:
```python
if song_path in self.pending_jobs:
    self.pending_jobs.remove(song_path)
```

Slice assignment (`list[:] = ...`) replaces the contents **in-place**, which
preserves the list object identity. This is correct for `pipeline_tracker.py`,
which reads `self._processing_manager.pending_jobs` by reference. If the
adapter accidentally reassigned `self.pending_jobs = [filtered]`, external
readers holding the old reference would see stale data. The plan's approach is
correct but could use a comment explaining why.

**Recommendation:** Add a brief comment: `# In-place mutation preserves
identity for external readers (PipelineTracker).`

---

### M6: Tests reference `_Step` and `_JobState` which vanish

The plan says "Delete `tests/unit/test_processing_manager.py` tests that reach
into `_Step` / `_JobState` (those types vanish)." But looking at the test file:

- `TestProcessingManagerCancelActive` (lines 91-161) constructs `_JobState`
  objects directly to test cancel behavior.
- `TestProcessingManagerGetActiveJob` (line 171-174) constructs a `_JobState`
  to test `get_active_job()`.
- `TestProcessingManagerOrchestratorIntegration` (lines 205-316) does full
  integration tests with mocked `StemWorker` and `Popen`.

The plan says to replace with "adapter-level tests against a mocked
`PipelineOrchestrator`." This is sound, but the integration tests at
lines 205-316 are the only end-to-end tests for the pipeline. Replacing them
with pure orchestrator mocks loses coverage for the enqueue→process→event
flow. The plan's replacement tests (listed in the Tests section) don't include
an equivalent integration test.

**Recommendation:** Keep one integration test that mocks only the heavy
dependencies (StemWorker, WhisperWorker, FFmpeg Popen) but runs the real
adapter loop. This catches wiring bugs that pure orchestrator mocks miss.

---

### M7: `build_whisper_config` helper referenced but not defined

Line 304: "Construct `self._whisper_worker = WhisperWorker(build_whisper_config(self._config))`
(helper copied from `mpv/pipeline/run_pipeline.py:34-49`)." The referenced file
doesn't exist (see C1). The plan doesn't describe what `build_whisper_config`
returns or what `WhisperWorker.__init__` expects.

**Recommendation:** Define this helper's interface inline in the plan.

---

### M8: `intermediate_dir` default change needs validation

The plan changes `intermediate_dir` from `/mnt/ramdisk` (hardcoded) to `""`
with the adapter resolving it via `get_temp_directory()`. The current
`processing_manager.py:245-246` already does this resolution:

```python
resolved_temp_dir = get_temp_directory(self._temp_dir) if self._temp_dir else None
tmp_dir = Path(tempfile.mkdtemp(prefix="pikaraoke_stems_", dir=resolved_temp_dir))
```

When `self._temp_dir` is empty, `resolved_temp_dir` is `None`, and
`tempfile.mkdtemp(dir=None)` uses the OS default temp dir. The plan says the
adapter "derives via `get_temp_directory(...)` and passes a resolved Path
through to the orchestrator's `tempfile.mkdtemp(dir=...)`." This means the
pipeline always gets a non-None directory, which changes behavior: currently
the OS default is used when no temp_dir is configured; the plan would use
`~/.pikaraoke/tmp` instead.

**Impact:** Different temp directory location. Not necessarily wrong, but a
behavioral change that should be noted.

**Recommendation:** Document this behavioral change explicitly. The
`~/.pikaraoke/tmp` path is likely better (persistent, user-visible), but it's
different from the OS temp dir.

---

## Design Observations (non-blocking)

### D1: The plan is simultaneously a port and a redesign

The plan says "port" but also introduces: (a) a new loudnorm stage, (b) a new
lyric_align stage, (c) a new database column, (d) a new whisper worker, (e)
new dependencies, and (f) a rewritten adapter. That's significantly more than
a port. The "port" framing understates the risk. Consider splitting into:
1. Port the 3-stage pipeline (extract→stem→transcode) as-is, validating the
   orchestrator/stage/worker architecture.
2. Add loudnorm stage + DB column.
3. Add lyric_align stage + whisper worker.

This reduces blast radius and makes rollback possible at each step.

### D2: The `PipelineOrchestrator` has a synchronous `start()` that blocks app startup

Line 317: `self._orchestrator.start()` "loads whisper model, spawns stem worker
— this is the slow path, acceptable at app boot." This is a 10-30 second
blocking call on the main thread. The current code's `StemWorker.start()`
spawns the subprocess and returns immediately; model loading happens in the
background. If `PipelineOrchestrator.start()` blocks until the Whisper model
is loaded, the web server won't accept connections during that window.

### D3: No `.ass` output path specified

The plan mentions `karaoke/*.ass` outputs in the verification section but
doesn't specify where the lyric_align stage writes them or what naming
convention it uses. The playback_controller expects
`{parent}/karaoke/{base_name}.ass` — this convention should be documented in
the plan.

---

## Summary

| Category | Count | Key items |
|----------|-------|-----------|
| Critical | 4 | C1: no prototype source; C2: undefined interfaces; C3: breaking API change; C4: model name/dir mismatch |
| Significant | 7 | S1: missing cleanup on cancel; S3: no eager restart; S5: Whisper memory/startup; S7: orphaned .ass files |
| Minor | 8 | M1–M8: edge cases, behavioral changes, missing test coverage |
| Design | 3 | D1: scope too large for a "port"; D2: blocking startup; D3: unspecified .ass path |

**Overall assessment:** The plan is well-structured and the adapter design is
sound, but it cannot be executed as-is because the source prototype doesn't
exist in the repo (C1). Even if the prototype is located, C2–C4 and S1, S3, S7
should be addressed before implementation begins. The incremental approach
suggested in D1 would significantly reduce risk.
