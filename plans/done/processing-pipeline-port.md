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

### Breaking change: model files must be pre-placed

This port removes audio-separator's auto-download path. Today the existing
pipeline lazily fetches `vocals_mel_band_roformer.ckpt` into
`./audio-separator/models/`. The new pipeline expects the user to copy
`mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` and
`large-v3-turbo.pt` into `<repo>/models/` before the first run — a missing
model file fails the first stem_separation with a clear "model not found"
error, no fallback. This must be called out in the upgrade notes when
this lands.

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
| `intermediate_dir` | `/mnt/ramdisk` | `""` — adapter resolves via `get_temp_directory(...)` and assigns the resulting **`str`** to `self._config.intermediate_dir`. `tempfile.mkdtemp(dir=...)` accepts both, but keep the field typed as `str` end-to-end so static checkers don't flip-flop. |

(`PipelineConfig` stays a plain dataclass with no Pikaraoke imports — the
adapter is the only place that resolves `intermediate_dir` against
`get_platform.get_temp_directory()`.)

## PTY fd lifecycle and ownership

The PTY slave fd is owned by `ProcessingManager` for the full lifetime of
the manager:

- Captured in `start()` from `ProcessTerminal.get_slave_fd()`.
- Held in `self._pty_slave_fd` and shared (read-only) with `StemWorker`,
  `WhisperWorker`, and stages via `ctx.artifacts["pty_slave_fd"]`.
- Closed exactly once in `stop()`, **after** the orchestrator thread has
  joined. `ProcessTerminal.stop()` must not close the slave fd
  independently — closing it while a stage still holds a `subprocess.Popen`
  using it as `stdout`/`stderr` would surface as `EBADF` from ffmpeg.

This matches the implicit ownership the current production code already
relies on; the plan only makes it explicit because the new pipeline shares
the fd across more components.

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

### WhisperWorker → PTY routing

WhisperWorker is in-process, so its output (model load progress, VAD chatter,
stable-ts encoder logs, faster-whisper's CTranslate2 C++ logs) defaults to
the parent's stdout/stderr — i.e., the main app terminal alongside Flask.
We want all processing chatter on the secondary PTY instead.

Python-level redirection (`contextlib.redirect_stderr`) won't capture the
CTranslate2 C-level writes, so we need an fd-level redirect scoped around
each worker call:

1. `WhisperWorker.__init__` accepts `pty_slave_fd: int | None = None` and
   stores it.
2. Add a context manager that dup2's the PTY fd over fds 1 and 2 for the
   duration of a call, then restores the saved originals:
   ```python
   @contextmanager
   def _route_to_pty(pty_fd: int | None):
       if pty_fd is None:
           yield
           return
       saved_out, saved_err = os.dup(1), os.dup(2)
       try:
           os.dup2(pty_fd, 1)
           os.dup2(pty_fd, 2)
           yield
       finally:
           os.dup2(saved_out, 1)
           os.dup2(saved_err, 2)
           os.close(saved_out)
           os.close(saved_err)
   ```
3. Wrap `load_model()`, `transcribe()`, `align()`, and `refine()` bodies in
   `with _route_to_pty(self._pty_fd):` so all whisper noise — including the
   first-time lazy load — lands on the secondary terminal.

The adapter passes the same `self._pty_slave_fd` it gives StemWorker into
WhisperWorker's constructor.

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
        subprocess.PIPE
        if capture_stderr
        else (pty_fd if pty_fd is not None else subprocess.DEVNULL)
    )
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=stdout_fd, stderr=stderr_fd
    )
    ...
```

## Lyric resolution (in adapter, before `run_one_async`)

Reuse [download_manager.py:446-476](pikaraoke/lib/download_manager.py#L446-L476)'s
output convention: yt-dlp drops English subs at
`{download_path}/subtitles/{stem}.srt` after each successful download.

### Restrict yt-dlp to English subs

Today `_move_downloaded_subtitle()` globs `*.srt` and picks whichever the
filesystem returns first — if yt-dlp emitted multiple language tracks, a
non-English `.srt` can survive and end up aligned against an English vocal
track, producing garbled output. Two changes:

1. Add `--sub-lang en` (and ensure `--write-subs` stays scoped to uploader
   subs only — auto-subs remain off per the non-goals) to the yt-dlp
   command in `download_manager.py` so non-English uploader subs aren't
   downloaded in the first place.
2. In `_move_downloaded_subtitle()`, prefer `*.en.srt` matches over the
   bare `*.srt` glob as a belt-and-suspenders defense against yt-dlp
   filename variations.

### Adapter helper

```python
def _resolve_lyrics_path(self, song_path: str) -> Path | None:
    """Look for an existing yt-dlp-downloaded .srt next to the song.

    Prefers `<song.parent>/subtitles/<song.stem>.en.srt`, falling back to
    `<song.parent>/subtitles/<song.stem>.srt`. Returns None if neither is
    present — LyricAlignStage falls through to transcribe mode.
    """
    song = Path(song_path)
    subs_dir = song.parent / "subtitles"
    for name in (f"{song.stem}.en.srt", f"{song.stem}.srt"):
        candidate = subs_dir / name
        if candidate.is_file():
            return candidate
    return None
```

The adapter forwards the resolved `Path | None` to `orchestrator.run_one_async(song_path, lyrics_path)`. The lyric_align stage already handles both branches ([lyric_align.py:55-114](mpv/pipeline/stages/lyric_align.py#L55-L114)).

## Database changes

### Schema (`pikaraoke/lib/karaoke_database.py`)

Two new columns added in a single v2 migration:

- `loudnorm_offset_db REAL` — dB gain offset that brings the song to the
  configured loudnorm target (what playback would apply at runtime).
- `pipeline_state TEXT NOT NULL DEFAULT 'skipped'` — per-row pipeline state.
  Values: `'pending' | 'ready' | 'failed' | 'skipped'`. **Named
  `pipeline_state`, not `processing_status`, to avoid colliding with
  `PipelineItem.processing_status`** (the in-flight tracker field at
  [pipeline_tracker.py:44-46](pikaraoke/lib/pipeline_tracker.py#L44-L46)
  uses values `waiting | pending | active | complete | error | cancelling`,
  a different state machine). The `'skipped'` default means pre-upgrade
  rows stay singable with whatever subs they already have (no surprise
  reprocess backlog); the new-song insert path writes `'pending'`
  explicitly so newly downloaded songs gate on the pipeline. An admin
  reconcile tool (out of scope for this port) will let users flip
  `'skipped'` → `'pending'` to opt into reprocess.

Both columns must be **added to the `_SCHEMA` constant** as well as covered
by an `ALTER TABLE` migration, so a fresh DB and an upgraded DB land on the
same shape:

```python
_SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    youtube_id TEXT,
    format TEXT NOT NULL,
    artist TEXT,
    title TEXT,
    variant TEXT,
    year INTEGER,
    genre TEXT,
    metadata_status TEXT DEFAULT 'pending',
    enrichment_attempts INTEGER DEFAULT 0,
    last_enrichment_attempt TEXT,
    loudnorm_offset_db REAL,
    pipeline_state TEXT NOT NULL DEFAULT 'skipped',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
...
"""
```

The migration is gated on `PRAGMA user_version` so it only fires for
upgrades from v1; the per-column `table_info` check inside the migration
keeps it idempotent for safety:

```python
def _create_schema(self) -> None:
    self._conn.executescript(_SCHEMA)
    cur_version = self._conn.execute("PRAGMA user_version").fetchone()[0]
    if cur_version < 2:
        self._migrate_v2_pipeline_columns()
    with self._conn:
        self._conn.execute("PRAGMA user_version = 2")


def _migrate_v2_pipeline_columns(self) -> None:
    """Add loudnorm_offset_db and pipeline_state columns (idempotent).

    Defaults: pipeline_state='skipped' so pre-upgrade rows back-migrate
    without triggering a reprocess backlog. The new-song insert path
    writes 'pending' explicitly via build_song_record.
    """
    cols = {row[1] for row in self._conn.execute("PRAGMA table_info(songs)")}
    with self._conn:
        if "loudnorm_offset_db" not in cols:
            self._conn.execute("ALTER TABLE songs ADD COLUMN loudnorm_offset_db REAL")
        if "pipeline_state" not in cols:
            self._conn.execute(
                "ALTER TABLE songs ADD COLUMN pipeline_state TEXT "
                "NOT NULL DEFAULT 'skipped'"
            )
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


def set_pipeline_state(self, file_path: str, state: str) -> None:
    """Set 'pending' | 'ready' | 'failed' | 'skipped'."""
    with self._lock, self._conn:
        self._conn.execute(
            "UPDATE songs SET pipeline_state = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
            (state, file_path),
        )


def get_pipeline_state(self, file_path: str) -> str | None:
    with self._lock:
        row = self._conn.execute(
            "SELECT pipeline_state FROM songs WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        return row[0] if row else None
```

`insert_songs()` must be widened to write `pipeline_state` so the
download-insert path can persist `'pending'` (see "New-song insert path"
below):

```python
def insert_songs(self, songs: list[dict]) -> None:
    """Batch-insert song records. Silently ignores duplicate file_paths."""
    with self._lock, self._conn:
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO songs (file_path, youtube_id, format, pipeline_state)
            VALUES (:file_path, :youtube_id, :format, :pipeline_state)
            """,
            songs,
        )
```

### SongManager methods

```python
def set_loudnorm_offset(self, song_path: str, offset_db: float) -> None:
    """Forwarder so callers don't reach into KaraokeDatabase directly."""
    self._db.set_loudnorm_offset(song_path, offset_db)


def set_pipeline_state(self, song_path: str, state: str) -> None:
    """Forwarder for pipeline_state writes."""
    self._db.set_pipeline_state(song_path, state)
```

### New-song insert path (build_song_record)

`build_song_record` ([library_scanner.py:14-24](pikaraoke/lib/library_scanner.py#L14-L24))
is called from two places with different intents:

1. `library_scanner.scan()` — bulk-imports pre-existing songs from disk;
   these must default to `'skipped'` so we don't sweep the user's
   pre-upgrade library into a reprocess backlog.
2. `song_manager.register_download()` — inserts the row for a freshly
   downloaded song; this must write `'pending'` so the pipeline gates on
   it.

Parameterize the helper so each caller picks its own default explicitly:

```python
def build_song_record(file_path: str, *, pipeline_state: str = "skipped") -> dict:
    return {
        "file_path": file_path,
        "youtube_id": _extract_youtube_id(file_path),
        "format": _detect_format(file_path),
        "pipeline_state": pipeline_state,
    }
```

`scan()` keeps the default. `register_download()` calls
`build_song_record(path, pipeline_state="pending")`.

### SongManager.\_get_companion_files — include .ass

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

### PipelineTracker subscription

`PipelineTracker._subscribe_events()`
([pipeline_tracker.py:76-84](pikaraoke/lib/pipeline_tracker.py#L76-L84))
currently subscribes to seven events. Add an eighth for the blocked-words
filter path:

```python
self._events.on("processing_skipped", self._on_processing_skipped)
```

The handler removes the row from `_items` (or marks its status `'skipped'`
and drops it from the in-flight set on the next `get_status()` sweep).
Without this subscription the event the adapter emits has no listener and
the rejected song's badge never clears.

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
        song_manager: (
            SongManager | None
        ) = None,  # NEW (optional) — needed for loudnorm DB write; if None, offset is not persisted
        temp_dir: str = "",
        log_level: int = logging.INFO,
    ) -> None: ...

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def enqueue(self, song_path: str) -> None: ...
    def cancel_pending(self, song_path: str) -> None: ...
    def cancel_active(self, song_path: str) -> None: ...
    def get_active_job(self) -> str | None: ...

    pending_jobs: list[str]  # public, derived
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
    cancel_token: CancelToken  # from orchestrator.run_one_async()
    cancelling: bool = False  # set by cancel_active()


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

    _pending_queue: queue.Queue[str | None]  # FIFO; None == shutdown sentinel
    pending_jobs: list[str]  # mirrors queue for tracker
    _cancelled_paths: set[str]  # paths cancelled while pending

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
4. Construct `self._whisper_worker = WhisperWorker(build_whisper_config(self._config), pty_slave_fd=self._pty_slave_fd)` (helper copied from `mpv/pipeline/run_pipeline.py:34-49`). Passing the same fd we gave StemWorker is what routes whisper output (load progress, VAD, stable-ts) to the secondary PTY — see "WhisperWorker → PTY routing" above.
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
   `self.load_model()` if it hasn't been loaded yet. The orchestrator
   loop is single-threaded so a `bool` flag would suffice, but keep a
   `threading.Lock` around `_ensure_loaded` as cheap defense for any
   future caller (e.g., a CLI runner or a warmup hook) that might invoke
   from a second thread.

`PipelineOrchestrator.stop()` still calls `unload_model()` (idempotent —
no-op if never loaded). The first lyric_align stage on a fresh boot
takes the model-load hit; subsequent jobs reuse the loaded model.

### `stop()`

1. `self._stop_event.set()`; `self._pending_queue.put(None)`.
2. Join `_orchestrator_thread` (timeout 10s).
3. `self._orchestrator.stop()` — unloads whisper, stops stem worker.
4. `self._process_terminal.stop()` if present.

### `enqueue(song_path)`

Same shape as today ([processing_manager.py:118-139](pikaraoke/lib/processing_manager.py#L118-L139)), with status bookkeeping in the blocked-words branch:

1. Apply `blocked_processing_words` filter — on match:
   - `self._song_manager.set_pipeline_state(song_path, "skipped")` (if `_song_manager` is set)
   - `self._events.emit("processing_skipped", song_path)` so `pipeline_tracker` can drop the row from its in-flight set and any badge clears immediately
   - return.
2. `self.pending_jobs.append(song_path)` under `_state_lock`.
3. `self._pending_queue.put(song_path)`.

### `cancel_pending(song_path)`

```python
with self._state_lock:
    if song_path in self.pending_jobs:
        self.pending_jobs.remove(song_path)
    self._cancelled_paths.add(song_path)
```

**No event is emitted by `cancel_pending` on purpose.** `processing_cancelled`
is the "active job stopped" signal — `PipelineTracker.cancel()`
([pipeline_tracker.py:133](pikaraoke/lib/pipeline_tracker.py#L133)) handles
its own state cleanup synchronously after calling `cancel_pending`, so
there's no observer that needs the wakeup. Adding the event here would
double-count cancels in any future listener that also subscribes to the
active-cancel signal.

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

> **Follow-up (out of scope for this port):** the eager restart will spam
> error logs once per queued job if the stem worker dies from a persistent
> condition (missing model, OOM). Mirrors the current production behaviour,
> so leaving as-is for now. A future change should add a small backoff
> (e.g., suppress restart attempts for N seconds after a failure) and
> surface a single sticky error to the user.

### `_process_song(song_path)` — single job

The early-exit check is **gated on `pipeline_state`**, not on filesystem
inspection. Reason: the prototype's `ffmpeg_transcode` stage promotes both
M4As to their final destinations *before* `lyric_align` runs. A cancel or
failure during align leaves the M4As in place but no `.ass` — a check that
just looks for the M4As would mark such a song `'ready'` and the user
would queue it up only to find no karaoke subtitles. State is the
authority; filesystem is not.

```python
def _process_song(self, song_path: str) -> None:
    if self._song_manager is not None:
        state = self._song_manager.get_pipeline_state(song_path)
        if state in ("ready", "skipped"):
            # Already-processed or admin-skipped — nothing to do.
            self._events.emit("processing_complete", song_path)
            return

    lyrics_path = self._resolve_lyrics_path(song_path)
    token = self._orchestrator.run_one_async(Path(song_path), lyrics_path)
    with self._state_lock:
        self._active = _ActiveJob(song_path=song_path, cancel_token=token)

    try:
        ctx = self._orchestrator.join()
    except PipelineCancelled:
        # Leave state as 'pending' — user-initiated cancel, not a system
        # failure. The stale-pending badge surfaces it on next page load
        # so the user can retry or use the admin reconcile tool.
        self._events.emit("processing_cancelled", song_path)
        logging.info(f"Processing cancelled: {Path(song_path).name}")
        return
    except Exception as e:
        if self._song_manager is not None:
            self._song_manager.set_pipeline_state(song_path, "failed")
        logging.error(f"Processing failed for {Path(song_path).name}: {e}")
        self._events.emit("processing_error", {"song_path": song_path, "error": str(e)})
        return

    # Persist loudnorm offset and ready state
    offset = ctx.artifacts.get("loudnorm_target_offset")
    if self._song_manager is not None:
        if offset is not None:
            try:
                self._song_manager.set_loudnorm_offset(song_path, float(offset))
            except Exception as e:
                logging.warning(
                    f"Failed to persist loudnorm offset for {song_path}: {e}"
                )
        self._song_manager.set_pipeline_state(song_path, "ready")

    self._events.emit("processing_complete", song_path)
    logging.info(f"Processing complete: {Path(song_path).name}")
```

PTY routing for `run_ffmpeg` is handled by `PreparePtyStage` seeding
`ctx.artifacts["pty_slave_fd"]` (see "PTY plumbing" below) — no extra
work needed in `_process_song`.

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

## Library gating (`files.html` and queue/sing routes)

`pipeline_state` does two jobs:

1. **Server-side gate** — the actual safety. Any route that adds a song to
   the playback queue or starts immediate playback checks
   `pipeline_state` and rejects `'pending'` / `'failed'` with a clear
   message. `'ready'` and `'skipped'` are both singable. UI badges are
   only the explanation layer; the gate stands on its own.
2. **Badges on the library page** — render a badge for each row whose
   state is currently in `pipeline_tracker`'s in-flight set OR whose
   persisted `pipeline_state` is `'pending'` / `'failed'` at page-render
   time (stale from a prior session). `'ready'` and `'skipped'` rows
   render plain so the bulk of the library stays uncluttered.

### Routes that need the gate

- `pikaraoke/routes/queue.py` — the "add to queue" endpoint(s). Any
  handler that takes a `file_path` and pushes onto `QueueManager` calls
  `song_manager.get_pipeline_state(path)` first; if the state is
  `'pending'` or `'failed'`, return a clear error response (HTTP 409 with
  a JSON message that the caller can surface as a toast).
- The "sing now" / immediate-play handler (whatever currently bypasses the
  queue and hands a path to the player) gets the same guard.
- The SSE flow that emits `queue_added` / `queue_changed` should never
  see a blocked path because the gate runs before the push, but a defense-
  in-depth assertion in `QueueManager.add()` is cheap.

Locate the exact endpoints during implementation and call them out in the
PR description; today's queue handlers all live under
`pikaraoke/routes/queue.py` so the surface is small.

### `files.html` / `routes/files.py` badges

Today `files.browse` ([routes/files.py](pikaraoke/routes/files.py)) hands
the template a flat list of paths from `song_manager.songs`. The template
needs three pieces of data per row to render the badges described above:

1. The persisted `pipeline_state` (single DB read; batch via a new
   `KaraokeDatabase.get_pipeline_states(paths)` returning a dict).
2. The current in-flight set from `pipeline_tracker.get_status()`.
3. The current `active_job` path from `processing_manager.get_active_job()`
   (for the "active" badge variant).

Pass an enriched list of `{path, pipeline_state, tracker_status}` dicts
to `files.html` and add a small badge component near the song-row title.
Tracker-driven badges flip live over the existing pipeline_tracker SSE
channel; stale-state badges are static until the user retries or uses the
admin reconcile tool.

The `processing_skipped` event from `enqueue()`'s blocked-words branch
lets `pipeline_tracker` clear the row from its in-flight set immediately,
so a badge that briefly appeared during the download → enqueue handoff
disappears as soon as the filter rejects it.

The admin reconcile tool (out of scope here) will be where users flip
`'skipped'` rows back to `'pending'` to opt into pipeline reprocess for
their pre-upgrade library.

## Dependencies (`pyproject.toml`)

Add to `dependencies`:

```toml
"audio-separator[gpu]>=0.30",   # already required at runtime today (implicit) — make explicit
"stable-ts>=2.17",
"faster-whisper>=1.0.3",
"srt>=3.5.3",
"torch>=2.2",                   # explicit; required by stable-ts/faster-whisper
```

The prototype's `mpv/pipeline/requirements.txt` is unversioned, so these
pins are new. **Before committing them**, install the combination into a
clean conda env (`pik`-equivalent), run a full pipeline against a test
song, and confirm `torch>=2.2` doesn't conflict with anything else in the
project on Pi-class hardware (where the torch wheel size and CPU build
flavour matter). If a pin needs relaxing, do it before merge — easier than
chasing a dependency-hell bug post-port.

## Tests

- Delete `tests/unit/test_processing_manager.py` tests that reach into
  `_Step` / `_JobState` (those types vanish).
- Replace with adapter-level tests against a **mocked** `PipelineOrchestrator`:
  - `enqueue` adds to queue + appends to `pending_jobs`.
  - `enqueue` respects `blocked_processing_words`.
  - `cancel_pending` removes from queue / tags `_cancelled_paths` and
    **does not emit any event** (regression guard against accidentally
    adding one).
  - `cancel_active` calls `orchestrator.cancel_active()` only when path matches.
  - `_process_song` early-exits when `pipeline_state` is `'ready'` or
    `'skipped'`: emits `processing_complete` and **does not** call
    `orchestrator.run_one_async`.
  - `_process_song` emits `processing_complete` with `song_path` when
    `orchestrator.join()` returns a ctx; calls
    `song_manager.set_loudnorm_offset` with the expected float and
    `song_manager.set_pipeline_state(path, "ready")`.
  - `_process_song` emits `processing_cancelled` when `PipelineCancelled`
    raised; **does not** write state (leaves `'pending'`).
  - `_process_song` emits `processing_error` with `{song_path, error}` on
    arbitrary exception; calls `set_pipeline_state(path, "failed")`.
  - `enqueue` on a blocked-word match calls
    `set_pipeline_state(path, "skipped")` and emits `processing_skipped`.
  - `_resolve_lyrics_path` prefers `<stem>.en.srt` over `<stem>.srt` and
    returns `None` when neither exists.
- DB: add `KaraokeDatabase` tests that round-trip `set_loudnorm_offset` /
  `get_loudnorm_offset` and `set_pipeline_state` / `get_pipeline_state`,
  and verify both columns survive after re-open (migration idempotency).
  Also verify the v2 migration: open a DB at v1 schema (insert a song
  via raw SQL with no new columns and `PRAGMA user_version = 1`), run
  `_create_schema` again, confirm the row reads back with
  `pipeline_state = 'skipped'` and `loudnorm_offset_db IS NULL`, and
  confirm `PRAGMA user_version` is now `2`. Run the migration a second
  time and confirm it's a no-op (idempotency).
- `library_scanner.build_song_record`: round-trip the new
  `pipeline_state` parameter — default `'skipped'`, override `'pending'`
  for the download path. Confirm `register_download` calls with
  `'pending'` and `scan()` keeps the default.
- `PipelineTracker`: subscribe-and-fire test for `processing_skipped`
  removing the item from the in-flight set.
- Routes: gate test for the queue-add and sing-now endpoints — paths with
  `pipeline_state = 'pending'` / `'failed'` get rejected; `'ready'` /
  `'skipped'` are accepted.
- Pipeline internals (stages/workers): the prototype's existing tests in
  `mpv/pipeline/` (if any) come along for the ride — but most are integration
  tests requiring real models, so don't run by default. CLAUDE.md's testing
  rule (mock external I/O) keeps them out of the default `pytest` selection.

## Verification

1. `/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit -q` — all
   unit tests green.
2. `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
   — formatting clean. `plans/` already excluded.
3. Manual end-to-end (the model-files prerequisite is called out in
   Context → "Breaking change: model files must be pre-placed" — copy
   both files into `<repo>/models/` before starting):
   - Start app; download a YouTube song that ships with English subs;
     watch the processing page advance through the 5 stages; verify
     `vocal/`, `nonvocal/`, `karaoke/*.ass` outputs land; verify both
     new columns populate (`sqlite3 pikaraoke.db "SELECT file_path, loudnorm_offset_db, pipeline_state FROM songs WHERE loudnorm_offset_db IS NOT NULL"` — `pipeline_state` should read
     `'ready'`).
   - Download a song with **no** subs; verify the pipeline runs
     transcribe mode and an `.ass` is written.
   - Verify whisper output (model load progress, VAD chatter) appears in
     the secondary terminal, not in the main Flask terminal.
   - Cancel **mid-`lyric_align`** (not just stem separation): confirm
     no `.ass` lands, `pipeline_state` stays `'pending'`, the song shows
     a stale-pending badge on the next library page load, and a manual
     re-trigger reprocesses cleanly. (This exercises the #2 fix —
     filesystem-based skip would have falsely marked it `'ready'`.)
   - Cancel during stem separation; verify the secondary terminal still
     shows worker output and the next song processes successfully (model
     still loaded).
   - Pre-upgrade rows: open the DB before the migration runs, dump
     `pipeline_state` after the upgrade — every existing row should be
     `'skipped'`, no reprocess backlog appears.
   - Try to add a `'pending'` row to the queue via the route layer —
     confirm the gate rejects it with a clear message.
4. `git status` — confirm `pikaraoke/lib/stem_worker.py` is deleted and the
   new `pikaraoke/pipeline/` package is added; nothing under `mpv/` was
   modified.

## Open question (defer or call now)

- **Loudnorm column semantics.** Plan stores `loudnorm_target_offset` (the dB
  gain to apply at playback). Alternative: store `loudnorm_input_i` (LUFS,
  raw measurement) and let the playback layer compute the offset against any
  target. Easy to add a second column later; flagging the choice for review.
