Model: Claude Opus 4.7

# Processing pipeline port (mpv/pipeline → pikaraoke/pipeline)

## Context

The `mpv/pipeline/` prototype (5-stage extract → loudnorm → stem → transcode →
lyric_align with phase-targeted cancel) replaces the 3-stage
`pikaraoke/lib/processing_manager.py` (extract → stem → transcode). The
prototype's stage and worker code is complete; only the **subtitle generation
logic** (final ASS shaping inside `LyricAlignStage`) is unfinished. We're
porting now and using the yt-dlp-downloaded `.srt` as alignment input when
available, falling back to whisper transcribe otherwise — that lets us defer
the lyricsgenius UI/modal work until the subtitle logic is finalized.

We also want the loudnorm measurement persisted per song so the playback layer
can level-match across the library later.

## Goals

- Drop the prototype in as `pikaraoke/pipeline/` (new package, upstream-safe).
- Rewrite `pikaraoke/lib/processing_manager.py` as a thin adapter so
  `karaoke.py`, `pipeline_tracker.py`, and the routes don't change.
- Run `lyric_align` in v1, sourcing the yt-dlp `.srt` when present, transcribing otherwise.
- Persist the loudnorm dB target offset on the song row.
- Keep PTY routing for stem-worker / ffmpeg output.
- Keep the `blocked_processing_words` preference filter.
- Stem model: `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt`
  (prototype's karaoke-tuned roformer).
- Whisper model: `large-v3-turbo.pt` via stable-ts.
- Models live in `<repo_root>/models/` (the user copies them in; no download
  step in the project).

## Non-goals (deferred)

- lyricsgenius integration / lyrics-fetch modal.
- Final ASS subtitle styling (the user is still iterating in the prototype).
- Auto-subs (`--write-auto-subs`) for yt-dlp — leave off for now; uploader
  subs only.
- Wiring loudnorm offset into mpv playback gain. This plan only stores it.

## File layout

```
pikaraoke/pipeline/                       # NEW (port from mpv/pipeline)
    __init__.py
    config.py                              # PipelineConfig, WhisperModelConfig
    context.py                             # Phase, CancelToken, KillProcess, SetEvent, PipelineCancelled, StageContext
    orchestrator.py                        # PipelineOrchestrator
    stages/
        __init__.py
        base.py                            # PipelineStage, BaseStage
        _ffmpeg_helpers.py                 # run_ffmpeg(...)
        ffmpeg_extract.py                  # FFmpegExtractStage
        loudnorm_analyze.py                # LoudnormAnalyzeStage
        stem_separation.py                 # StemSeparationStage
        ffmpeg_transcode.py                # FFmpegTranscodeStage
        lyric_align.py                     # LyricAlignStage
    workers/
        __init__.py
        stem_worker.py                     # StemWorker (subprocess) — extended with pty_slave_fd
        whisper_worker.py                  # WhisperWorker (in-process)

pikaraoke/lib/processing_manager.py        # REWRITE as adapter (same public API)
pikaraoke/lib/stem_worker.py               # DELETE (superseded)

models/                                    # NEW dir, user-populated
    mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt
    large-v3-turbo.pt
```

All `from pipeline.X` imports inside the moved package become
`from pikaraoke.pipeline.X`.

## PipelineConfig adjustments (`pikaraoke/pipeline/config.py`)

Change the defaults so the pipeline runs on this project's layout:

| Field | Old default | New default |
|-------|-------------|-------------|
| `_REPO_ROOT` | `Path(__file__).parent.parent` | `Path(__file__).resolve().parents[2]` (project root) |
| `_MODELS_DIR` | `<repo>/models` | `<repo>/models` (unchanged path; just resolves to project root) |
| `whisper_model_path` | `<repo>/models/large-v3-turbo.pt` | unchanged |
| `separator_model_dir` | `<repo>/models` | unchanged |
| `separator_model_name` | `vocals_mel_band_roformer.ckpt` | `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` |
| `intermediate_dir` | `/mnt/ramdisk` | `""` — adapter derives via `get_temp_directory(...)` and passes a resolved Path through to the orchestrator's `tempfile.mkdtemp(dir=...)` |

(`PipelineConfig` stays a plain dataclass with no Pikaraoke imports — the
adapter is the only place that resolves `intermediate_dir` against
`get_platform.get_temp_directory()`.)

## StemWorker PTY integration (`pikaraoke/pipeline/workers/stem_worker.py`)

The prototype StemWorker needs to mirror the current PTY routing behaviour
([pikaraoke/lib/stem_worker.py:206-209](pikaraoke/lib/stem_worker.py#L206-L209)).

- Add `pty_slave_fd: int | None = None` to `StemWorker.__init__`.
- Pass it to `Process(target=_worker_main, args=(..., pty_slave_fd, ...))`.
- In `_worker_main`, before loading the model:
  ```python
  if pty_slave_fd is not None:
      os.dup2(pty_slave_fd, 1)
      os.dup2(pty_slave_fd, 2)
      os.close(pty_slave_fd)
  ```
- Update `_setup_worker_logger` to use the existing `pikaraoke.lib.stem_worker`
  logger name (or a new `pikaraoke.pipeline.workers.stem_worker` name — keep
  consistent with module path).

WhisperWorker is in-process; it already logs via stderr and inherits whatever
the parent process has. No PTY work needed there.

ffmpeg subprocesses spawned in `_ffmpeg_helpers.run_ffmpeg()` currently use
`stdout=DEVNULL, stderr=DEVNULL/PIPE`. The current production code routes
ffmpeg output to the PTY ([processing_manager.py:345-348](pikaraoke/lib/processing_manager.py#L345-L348)).
Mirror this: extend `run_ffmpeg(...)` to take an optional `stdout_fd` /
`stderr_fd` (defaulting to `DEVNULL`), and have the adapter pass the PTY
slave fd through `StageContext.artifacts["pty_slave_fd"]`. The helper reads
that artifact and uses it when present.

Concretely in `_ffmpeg_helpers.py`:

```python
def run_ffmpeg(cmd, ctx, phase, *, capture_stderr=False) -> str:
    pty_fd = ctx.artifacts.get("pty_slave_fd")
    stdout_fd = pty_fd if pty_fd is not None else subprocess.DEVNULL
    stderr_fd = (
        subprocess.PIPE if capture_stderr
        else (pty_fd if pty_fd is not None else subprocess.DEVNULL)
    )
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=stdout_fd, stderr=stderr_fd)
    ...
```

## Lyric resolution (in adapter, before `run_one_async`)

Reuse [download_manager.py:446-476](pikaraoke/lib/download_manager.py#L446-L476)'s
output convention: yt-dlp drops English subs at
`{download_path}/subtitles/{stem}.srt` after each successful download.

Adapter helper:

```python
def _resolve_lyrics_path(self, song_path: str) -> Path | None:
    """Look for an existing yt-dlp-downloaded .srt next to the song.

    Searches `<song.parent>/subtitles/<song.stem>.srt` first, then any
    `*.srt` matching that stem. Returns None if no .srt is found —
    LyricAlignStage will fall through to transcribe mode.
    """
    song = Path(song_path)
    candidate = song.parent / "subtitles" / f"{song.stem}.srt"
    return candidate if candidate.is_file() else None
```

The adapter forwards the resolved `Path | None` to `orchestrator.run_one_async(song_path, lyrics_path)`. The lyric_align stage already handles both branches ([lyric_align.py:55-114](mpv/pipeline/stages/lyric_align.py#L55-L114)).

## Database changes

### Schema (`pikaraoke/lib/karaoke_database.py`)

Add a single column for the dB gain offset that brings the song to the
configured loudnorm target (this is what playback would apply at runtime):

```sql
ALTER TABLE songs ADD COLUMN loudnorm_offset_db REAL;
```

Apply via a small migration step in `_create_schema`. After the existing
`executescript(_SCHEMA)`:

```python
def _create_schema(self) -> None:
    self._conn.executescript(_SCHEMA)
    self._migrate_v2_loudnorm()
    with self._conn:
        self._conn.execute("PRAGMA user_version = 2")

def _migrate_v2_loudnorm(self) -> None:
    """Add loudnorm_offset_db column if not present (idempotent)."""
    cols = {row[1] for row in self._conn.execute("PRAGMA table_info(songs)")}
    if "loudnorm_offset_db" not in cols:
        with self._conn:
            self._conn.execute("ALTER TABLE songs ADD COLUMN loudnorm_offset_db REAL")
```

Bump `PRAGMA user_version` from 1 to 2.

### KaraokeDatabase methods

```python
def set_loudnorm_offset(self, file_path: str, offset_db: float) -> None:
    """Persist the loudnorm target offset (in dB) for one song."""
    with self._lock, self._conn:
        self._conn.execute(
            "UPDATE songs SET loudnorm_offset_db = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
            (offset_db, file_path),
        )

def get_loudnorm_offset(self, file_path: str) -> float | None:
    with self._lock:
        row = self._conn.execute(
            "SELECT loudnorm_offset_db FROM songs WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        return row[0] if row else None
```

### SongManager method

```python
def set_loudnorm_offset(self, song_path: str, offset_db: float) -> None:
    """Forwarder so callers don't reach into KaraokeDatabase directly."""
    self._db.set_loudnorm_offset(song_path, offset_db)
```

### SongManager._get_companion_files — include .ass

`song_manager.py:70-71` has a placeholder comment noting `.ass` files
will be added "in a separate change." This is that change. Extend
`_get_companion_files()` so deleting a song also removes
`{parent}/karaoke/{stem}.ass` (the lyric_align output) — otherwise it
becomes an orphan after deletion. The convention matches what
`playback_controller.py:204` already reads.

(Open question: store `target_offset` (dB, applied gain) or `input_i`
(integrated LUFS, raw measurement)? Plan stores `target_offset` because
"loudnorm dB value" reads as a dB-denominated number; `input_i` is in LUFS.
Both are one column each — easy to flip later.)

## Atomicity guarantee (no `_cleanup_stems` needed in the adapter)

The current `processing_manager.py` writes `vocal/{stem}---vocal.m4a`
and `nonvocal/{stem}---nonvocal.m4a` directly to their final
destinations as ffmpeg runs, so a cancel mid-transcode leaves a partial
file that the next run's `_stems_already_exist` check would treat as
"done." The current code papers over this with `_cleanup_stems()` calls
on the cancel and error paths.

The prototype solves this **structurally** — every stage that produces
user-visible output writes into `ctx.tmp_dir` first and only
`shutil.move`s to the final directory after **all** that stage's
outputs succeed:

| Stage | tmp_dir output | Promoted to (only on full success) |
|---|---|---|
| `ffmpeg_extract` | `{stem}_input.wav` | (intermediate only — never promoted) |
| `loudnorm_analyze` | (no file output) | n/a |
| `stem_separation` | `vocal.wav`, `instrumental.wav` | (intermediate only — never promoted) |
| `ffmpeg_transcode` | `{stem}---vocal.m4a`, `{stem}---nonvocal.m4a` | `vocal/`, `nonvocal/` after **both** transcodes succeed ([ffmpeg_transcode.py:46-64](mpv/pipeline/stages/ffmpeg_transcode.py#L46-L64)) |
| `lyric_align` | `{stem}.ass`, `{stem}.srt` | `karaoke/`, `subtitles/` after **both** writes succeed ([lyric_align.py:131-153](mpv/pipeline/stages/lyric_align.py#L131-L153)) |

`PipelineOrchestrator._run_pipeline` wraps the stage loop in a `finally`
that calls `shutil.rmtree(tmp_dir, ignore_errors=True)`
([orchestrator.py:209-211](mpv/pipeline/orchestrator.py#L209-L211)) — so
the temp dir is wiped on success, exception, and cancel paths alike.

**Consequence for the adapter:** no `_cleanup_stems()` call is needed
in the cancel or error handlers of `_process_song`. A cancel between
the two transcodes, mid-stem-separation, or mid-align leaves nothing in
`vocal/` / `nonvocal/` / `karaoke/` / `subtitles/`. The adapter's job
is purely event emission and state bookkeeping.

## ProcessingManager adapter rewrite

`pikaraoke/lib/processing_manager.py` keeps the same public surface that
`PipelineTracker` and `karaoke.py` depend on, but delegates all execution to
`PipelineOrchestrator`.

### Public API (unchanged from today)

```python
class ProcessingManager:
    def __init__(
        self,
        events: EventSystem,
        preferences: PreferenceManager,
        song_manager: SongManager | None = None,  # NEW (optional) — needed for loudnorm DB write; if None, offset is not persisted
        temp_dir: str = "",
        log_level: int = logging.INFO,
    ) -> None: ...

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def enqueue(self, song_path: str) -> None: ...
    def cancel_pending(self, song_path: str) -> None: ...
    def cancel_active(self, song_path: str) -> None: ...
    def get_active_job(self) -> str | None: ...

    pending_jobs: list[str]                    # public, derived
```

`song_manager` is **optional** so the existing test fixture
(`tests/unit/test_processing_manager.py:28-30`, which builds
`ProcessingManager(events=events, preferences=preferences)`) keeps
working — and any future caller that doesn't need loudnorm persistence
(e.g., a pure-CLI runner) can omit it. When `None`, `_process_song`
silently skips the `set_loudnorm_offset` call.

`karaoke.py:286-292` adds `song_manager=self.song_manager` to the
constructor call. No other call sites change.

### Internal data structures

```python
@dataclass
class _ActiveJob:
    song_path: str
    cancel_token: CancelToken          # from orchestrator.run_one_async()
    cancelling: bool = False           # set by cancel_active()

class ProcessingManager:
    _events: EventSystem
    _preferences: PreferenceManager
    _song_manager: SongManager
    _temp_dir: str
    _log_level: int

    _orchestrator: PipelineOrchestrator
    _stem_worker: StemWorker
    _whisper_worker: WhisperWorker
    _config: PipelineConfig

    _process_terminal: ProcessTerminal | None
    _pty_slave_fd: int | None

    _pending_queue: queue.Queue[str | None]    # FIFO; None == shutdown sentinel
    pending_jobs: list[str]                    # mirrors queue for tracker
    _cancelled_paths: set[str]                 # paths cancelled while pending

    _active: _ActiveJob | None
    _state_lock: threading.Lock

    _orchestrator_thread: threading.Thread | None
    _stop_event: threading.Event
```

### Construction (`__init__`)

- Build `PipelineConfig()`.
- Resolve intermediate temp dir via
  `get_temp_directory(self._temp_dir) if self._temp_dir else get_temp_directory()`
  and assign to `self._config.intermediate_dir` as a string.
- Don't construct workers / orchestrator yet — defer to `start()`.

### `start()`

1. Subscribe `self._events.on("song_downloaded", self.enqueue)`.
2. On non-Windows, spawn `ProcessTerminal()` and capture
   `self._pty_slave_fd = self._process_terminal.get_slave_fd()`.
3. Construct `self._stem_worker = StemWorker(pty_slave_fd=self._pty_slave_fd, model_dir=self._config.separator_model_dir, model_name=self._config.separator_model_name, log_level=self._log_level)`.
4. Construct `self._whisper_worker = WhisperWorker(build_whisper_config(self._config))` (helper copied from `mpv/pipeline/run_pipeline.py:34-49`).
5. Build the stage list (PreparePtyStage first so all subsequent stages
   see `ctx.artifacts["pty_slave_fd"]`):
   ```python
   stages = [
       PreparePtyStage(self._pty_slave_fd),
       FFmpegExtractStage(self._config),
       LoudnormAnalyzeStage(self._config),
       StemSeparationStage(self._stem_worker),
       FFmpegTranscodeStage(self._config),
       LyricAlignStage(self._whisper_worker, self._config),
   ]
   ```
6. `self._orchestrator = PipelineOrchestrator(stages, self._stem_worker, self._whisper_worker, self._config)`
7. `self._orchestrator.start()` — spawns the stem worker (fast). **Whisper
   model loading is deferred** to first `lyric_align` invocation so app
   boot stays snappy on Pi-class hardware.
8. Spawn the orchestrator thread (`self._run_loop`).

#### Lazy Whisper loading

The prototype's `PipelineOrchestrator.start()` calls
`self._whisper_worker.load_model()` synchronously, which is a 10–30s
block on slow hardware and ~1.5 GB of resident memory whether or not
the user ever processes a song that needs transcription/alignment.

Two changes:

1. In `PipelineOrchestrator.start()`, drop the `load_model()` call —
   only `self._stem_worker.start()` runs eagerly.
2. In `WhisperWorker.transcribe()` / `align()` / `refine()`, gate the
   first call on a one-shot `_ensure_loaded()` helper that calls
   `self.load_model()` if it hasn't been loaded yet. Idempotent and
   thread-safe via a `threading.Lock`.

`PipelineOrchestrator.stop()` still calls `unload_model()` (idempotent —
no-op if never loaded). The first lyric_align stage on a fresh boot
takes the model-load hit; subsequent jobs reuse the loaded model.

### `stop()`

1. `self._stop_event.set()`; `self._pending_queue.put(None)`.
2. Join `_orchestrator_thread` (timeout 10s).
3. `self._orchestrator.stop()` — unloads whisper, stops stem worker.
4. `self._process_terminal.stop()` if present.

### `enqueue(song_path)`

Same shape as today ([processing_manager.py:118-139](pikaraoke/lib/processing_manager.py#L118-L139)):

1. Apply `blocked_processing_words` filter (verbatim).
2. `self.pending_jobs.append(song_path)` under `_state_lock`.
3. `self._pending_queue.put(song_path)`.

### `cancel_pending(song_path)`

```python
with self._state_lock:
    if song_path in self.pending_jobs:
        self.pending_jobs.remove(song_path)
    self._cancelled_paths.add(song_path)
```

### `cancel_active(song_path)`

```python
with self._state_lock:
    active = self._active
    if active is None or active.song_path != song_path:
        logging.warning(f"Cancel requested for non-active job: {Path(song_path).name}")
        return
    active.cancelling = True
self._orchestrator.cancel_active()
```

The orchestrator delegates to `cancel_token.cancel()`, which signals whichever
`Cancellable` is currently registered (FFmpeg `KillProcess` or worker
`SetEvent`). The current pipeline thread sees `PipelineCancelled` and exits.

### `get_active_job()`

```python
with self._state_lock:
    return self._active.song_path if self._active else None
```

### Orchestrator loop (`_run_loop`)

```python
def _run_loop(self) -> None:
    while not self._stop_event.is_set():
        try:
            song_path = self._pending_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        if song_path is None:
            return

        with self._state_lock:
            if song_path in self._cancelled_paths:
                self._cancelled_paths.discard(song_path)
                self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
                continue

        try:
            self._process_song(song_path)
        finally:
            # In-place mutation preserves identity for external readers (PipelineTracker).
            with self._state_lock:
                self.pending_jobs[:] = [p for p in self.pending_jobs if p != song_path]
                self._active = None

            # Eager restart: if a cancel or crash killed the stem worker,
            # bring it back before the next job arrives.  Mirrors the
            # current `processing_manager.py:226-231` behaviour.
            if not self._stem_worker.is_alive():
                try:
                    self._stem_worker.start()
                except Exception as e:
                    logging.error(f"Failed to restart stem worker: {e}")
```

### `_process_song(song_path)` — single job

```python
def _process_song(self, song_path: str) -> None:
    if self._stems_already_exist(song_path):
        # Match current behaviour: skip silently if outputs already there.
        self._events.emit("processing_complete", song_path)
        return

    lyrics_path = self._resolve_lyrics_path(song_path)
    token = self._orchestrator.run_one_async(Path(song_path), lyrics_path)
    # Inject PTY fd so run_ffmpeg() routes stdout/stderr to the secondary
    # terminal — the orchestrator owns the StageContext, so we pass via
    # config rather than mutating ctx after the fact. Simpler approach:
    # plumb pty_slave_fd through PipelineOrchestrator → StageContext.artifacts.
    # See "PTY plumbing" note below.
    with self._state_lock:
        self._active = _ActiveJob(song_path=song_path, cancel_token=token)

    try:
        ctx = self._orchestrator.join()
    except PipelineCancelled:
        self._events.emit("processing_cancelled", song_path)
        logging.info(f"Processing cancelled: {Path(song_path).name}")
        return
    except Exception as e:
        logging.error(f"Processing failed for {Path(song_path).name}: {e}")
        self._events.emit("processing_error", {"song_path": song_path, "error": str(e)})
        return

    # Persist loudnorm offset
    offset = ctx.artifacts.get("loudnorm_target_offset")
    if offset is not None:
        try:
            self._song_manager.set_loudnorm_offset(song_path, float(offset))
        except Exception as e:
            logging.warning(f"Failed to persist loudnorm offset for {song_path}: {e}")

    self._events.emit("processing_complete", song_path)
    logging.info(f"Processing complete: {Path(song_path).name}")
```

`_stems_already_exist` mirrors the existing check
([processing_manager.py:240-243](pikaraoke/lib/processing_manager.py#L240-L243)):
returns True iff both `vocal/{stem}---vocal.m4a` and
`nonvocal/{stem}---nonvocal.m4a` exist.

### PTY plumbing into the pipeline

Seed `StageContext.artifacts["pty_slave_fd"]` before stages run by
prepending a tiny `PreparePtyStage` whose `run()` does:

```python
class PreparePtyStage(BaseStage):
    name = "prepare_pty"

    def __init__(self, pty_slave_fd: int | None) -> None:
        self._fd = pty_slave_fd

    def run(self, ctx: StageContext) -> None:
        if self._fd is not None:
            ctx.artifacts["pty_slave_fd"] = self._fd
```

`_ffmpeg_helpers.run_ffmpeg()` reads `ctx.artifacts.get("pty_slave_fd")`
(already proposed in the helper sketch above). `StemWorker` receives the
fd directly via its constructor, so it doesn't need the artifact.

Rationale: `PipelineConfig` is meant to be a serialisable, Pikaraoke-free
dataclass. A per-process file descriptor is runtime state, not config —
keeping it in `ctx.artifacts` (per-job context) avoids polluting the
shared config object and keeps the `PipelineConfig` surface clean for
tests and CLI runners.

## Dependencies (`pyproject.toml`)

Add to `dependencies`:

```toml
"audio-separator[gpu]>=0.30",   # already required at runtime today (implicit) — make explicit
"stable-ts>=2.17",
"faster-whisper>=1.0.3",
"srt>=3.5.3",
"torch>=2.2",                   # explicit; required by stable-ts/faster-whisper
```

(Verify exact pins against `mpv/pipeline/requirements.txt`.)

## Tests

- Delete `tests/unit/test_processing_manager.py` tests that reach into
  `_Step` / `_JobState` (those types vanish).
- Replace with adapter-level tests against a **mocked** `PipelineOrchestrator`:
  - `enqueue` adds to queue + appends to `pending_jobs`.
  - `enqueue` respects `blocked_processing_words`.
  - `cancel_pending` removes from queue / tags `_cancelled_paths`.
  - `cancel_active` calls `orchestrator.cancel_active()` only when path matches.
  - `_process_song` emits `processing_complete` with `song_path` when
    `orchestrator.join()` returns a ctx; calls
    `song_manager.set_loudnorm_offset` with the expected float.
  - `_process_song` emits `processing_cancelled` when `PipelineCancelled` raised.
  - `_process_song` emits `processing_error` with `{song_path, error}` on
    arbitrary exception.
  - `_resolve_lyrics_path` returns the `.srt` when present and `None` otherwise.
- DB: add a `KaraokeDatabase` test that round-trips `set_loudnorm_offset` /
  `get_loudnorm_offset` and verifies the column survives after a re-open
  (migration idempotency).
- Pipeline internals (stages/workers): the prototype's existing tests in
  `mpv/pipeline/` (if any) come along for the ride — but most are integration
  tests requiring real models, so don't run by default. CLAUDE.md's testing
  rule (mock external I/O) keeps them out of the default `pytest` selection.

## Verification

1. `/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit -q` — all
   unit tests green.
2. `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
   — formatting clean. `plans/` already excluded.
3. Manual end-to-end:
   - **Required first step:** copy
     `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` and
     `large-v3-turbo.pt` into `<repo>/models/`. This is a **breaking
     change from current behaviour** — the existing pipeline relies on
     audio-separator's auto-download cache at
     `./audio-separator/models/vocals_mel_band_roformer.ckpt`. The new
     pipeline does **not** auto-download; if the model file is missing,
     the first stem_separation will fail with a clear "model not found"
     error. There is no fallback path. Document this in the upgrade
     notes when this lands.
   - Start app; download a YouTube song that ships with English subs;
     watch the processing page advance through the 5 stages; verify
     `vocal/`, `nonvocal/`, `karaoke/*.ass` outputs land; verify the
     `loudnorm_offset_db` column populates (`sqlite3 pikaraoke.db "SELECT
     file_path, loudnorm_offset_db FROM songs WHERE loudnorm_offset_db IS
     NOT NULL"`).
   - Download a song with **no** subs; verify pipeline runs transcribe
     mode and an `.ass` is written.
   - Cancel during stem separation; verify the secondary terminal still
     shows worker output and the next song processes successfully (model
     still loaded).
4. `git status` — confirm `pikaraoke/lib/stem_worker.py` is deleted and the
   new `pikaraoke/pipeline/` package is added; nothing under `mpv/` was
   modified.

## Open question (defer or call now)

- **Loudnorm column semantics.** Plan stores `loudnorm_target_offset` (the dB
  gain to apply at playback). Alternative: store `loudnorm_input_i` (LUFS,
  raw measurement) and let the playback layer compute the offset against any
  target. Easy to add a second column later; flagging the choice for review.
