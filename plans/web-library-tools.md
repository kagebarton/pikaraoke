# Web library tools: regen, repair and playlists in the app

Model: Claude Opus 5.5 (design, 2026-10-20); executor Claude Sonnet 5.5.

> **Status (2026-10-20): Phases 0-1 done; Phase 2 is next.** Branch
> `web_library_tools`, off `library_tools` at `0bfa02a`; `dev` merged as
> `c34d889`. There is no GATE and nothing here measures timing. Landing is
> Ken's call (see Landing).

## Why

Ken runs the library tools (`scripts/regen_alignment_bundles.py`,
`scripts/add_songs.py`, both on `library_tools`) from a terminal with the app
stopped. This plan moves them into the app:

- fix one song's lyrics when the automatic pick was wrong: a different Genius
  match and LRCLIB match, or the video caption, or transcribe;
- regenerate the songs behind the current schema, every song, or reset every
  song, with the page listing the songs first;
- add a YouTube playlist;
- and rework the Processing page, which has always been clunky.

## Decisions (Ken, 2026-10-20; the executor does not reopen them)

The design session's record is `~/.claude/plans/i-am-contemplating-moving-jazzy-toucan.md`
on Ken's machine. Condensed:

1. **Queue through the app.** Regen jobs go through the app's processing queue,
   one at a time, and the app stays usable. A new download jumps ahead of
   waiting regen jobs.
2. **Busy songs.** A regen of the song now playing waits until it stops
   playing. Songs merely in the singing queue regenerate normally.
3. **Explicit lyric source per song:** the video caption, a Genius result, or
   transcribe. A Genius pick can replace a good caption.
4. **Admin-typed search terms in a repair**, for Genius and for LRCLIB (the
   automatic search found the wrong thing, which is why the repair is
   needed). The admin picks an LRCLIB candidate, or skips LRCLIB; with no
   match the song runs with no `.lrc` and the fill does nothing.
5. **Bulk options:** "update stale" (behind the current schema), "reprocess
   all" (reuse every recorded pick), "reset all" (start over, like CLI
   `--reset`). **Pick first, then queue:** the preview lists the songs, the
   admin resolves every song that needs a pick, then everything queues and
   runs unattended. Picks made so far are kept on the server, reopening
   resumes, and nothing queues until the admin confirms.
6. **LRCLIB is automatic in bulk passes**; manual only in a per-song repair.
7. **Transcribed songs** are their own "no lyrics" group, not counted as
   stale, and repairable with a lyric pick.
8. **"Looks poor"** = 15% or more of a song's lines have no word timing
   (guessed). A fixed rule in code.
9. **Backups:** the same `regen_backup_<UTC>/` folder layout as the CLI; no
   restore UI.
10. **CLI:** keep both tools; they share the core with the web.
11. **Song Info page** (new, admin only), linked from the song browser and
    from Edit Song, not blocked when the song is queued. Shows the picks,
    the alignment stats, and history; hosts repair and regenerate.
12. **Bulk options and playlists live on the Processing page.**
13. **Playlists:** expand, dedupe against the library, preview (new / in the
    library but not processed / already in the library) with a checkbox per
    new video. Every checked video downloads. A song whose caption passes the
    words-per-minute check processes automatically; the rest wait in a
    "needs a pick" list and process once picked. Playlist songs are not added
    to the singing queue.
14. **The search page's direct-download box** (no picker) gets the same
    after-download caption check.
15. **Layouts:** Processing page variant B (Jobs / Library tools tabs, filter
    chips, compact rows that expand). Song Info variant B (summary tiles +
    tabs: Picks, Alignment, History). Pick pass variant B (the whole list,
    pick inline, one-tap Keep, "keep current pick for all"). The bulk pick
    pass prefills the Genius search with the song's cleaned title. Ken prefers
    tabs over long pages.
16. **No system information for guests when nothing is wrong.** Library
    maintenance is admin only.
17. **History tab:** read-only, built from
    `regen_backup_*/alignment_debug/<stem>.json`, one entry per distinct
    `captured_at`, newest first, each under its newest backup folder. No
    restore button.
18. **Prerequisite, separate plan (not written yet):** the search-page picker
    checks the caption itself and offers "Use YouTube captions" only when it
    passes. It lands on `dev` before this plan does. Nothing here touches the
    search picker or depends on that work.
19. **Branch off `library_tools`;** both land on `dev` together, by
    cherry-pick.

## Design (Opus, 2026-10-20; follows from the decisions)

### D1. Files

New:

| File | Holds |
|---|---|
| `pikaraoke/lib/library_regen.py` | the regen core, moved from `scripts/regen_alignment_bundles.py` (Phase 1), plus the LRCLIB choice, caption check and per-job prep (Phases 2-3) |
| `pikaraoke/lib/library_links.py` | link classification, playlist reading and library dedupe, moved from `scripts/add_songs.py` (Phase 1) |
| `pikaraoke/lib/library_status.py` | read-only song status, alignment stats and history from bundles (Phase 2B) |
| `pikaraoke/lib/library_tools.py` | `LibraryTools`, the app service: single-song jobs, bulk runs, the needs-a-pick list, the after-download check, playlists, persisted state |
| `pikaraoke/routes/song_info.py` | `song_info_bp`: Song Info, regenerate, repair and its search helpers |
| `pikaraoke/routes/library.py` | `library_bp`: Library tools tab data, song lists, bulk runs, pick screens, playlists |
| `pikaraoke/templates/song_info.html`, `song_repair.html`, `library_songs.html`, `library_run.html`, `pick_pass.html`, `playlist.html` | the new pages |

Changed (fork-owned unless marked upstream):

- `pikaraoke/pipeline/orchestrator.py`: a per-job stage list.
- `pikaraoke/lib/processing_manager.py`: the regen lane.
- `pikaraoke/lib/pipeline_tracker.py`: regen and reprocess rows, new actions, ordering.
- `pikaraoke/routes/processing.py`, `pikaraoke/templates/processing.html` (rewritten).
- `pikaraoke/lib/lrclib.py`: fetch one record, skip marker.
- `pikaraoke/karaoke.py`: wiring.
- Upstream, smallest possible change each: `pikaraoke/app.py` (import and
  register two blueprints), `pikaraoke/lib/karaoke_database.py` and
  `pikaraoke/lib/song_manager.py` (one query and its forwarder),
  `pikaraoke/templates/files.html` and `edit.html` (one Song Info link each).
- `scripts/regen_alignment_bundles.py`, `scripts/add_songs.py`,
  `scripts/README.md`, and tests.

Any other change under `pikaraoke/` is a STOP (CLAUDE.md, Fork Maintenance).

### D2. A regen job runs through the processing queue

- `RegenJob` (in `library_regen`): `song: SongJob` (path, bundle, plan),
  `reset: bool` (wipe this song's regenerable outputs before running),
  `label: str` (the row's kind word: `Update`, `Reprocess`, `Reset`,
  `Repair`, `Regenerate`).
- `ProcessingManager` keeps today's download lane (the `_pending_queue`) and
  adds a regen lane. The run loop always takes a download first; it takes a
  regen job only when the download lane is empty, and skips a regen job
  whose song is now playing (that job stays queued and is retried on the
  loop's next pass).
- A regen job runs through the same orchestrator and workers, with its own
  stage list (`PreparePtyStage`, then `library_regen.build_stages`). The
  orchestrator gains an optional per-call `stages` argument for this.
- Before the run, `library_regen.prepare_regen_job` does the per-song file
  work: the reset wipe, the caption fetch, the LRCLIB choice, the automatic
  LRCLIB fetch for reused Genius picks, and the lyric files.
- Success sets the song's `pipeline_state` to `ready` (and stores the
  loudnorm offset when the run produced one). **Failure leaves
  `pipeline_state` alone**: `_do_enqueue` refuses `failed` songs, and a
  failed regen of a playable song must not make it unqueueable. Events are
  the same as for downloads (`processing_complete`, `processing_error`,
  `processing_cancelled`).
- Cancelling or removing a regen row never deletes the song file (today a
  cancelled or removed *download* deletes its file, and that stays).
- Queued regen jobs do not survive an app restart, the same as today's
  processing queue. A reset job interrupted after its wipe leaves that song
  without lyrics until it is regenerated; its files are in the backup.

### D3. The LRCLIB choice is the file on disk

`lyrics/<stem>.lrc` already decides LRCLIB everywhere: `ensure_lrc` reuses any
file on disk and `KEEP_ON_RESET` keeps it through a reset. So:

- the admin picks a candidate: write that record (`lrclib.write_lrc`) before
  the run;
- the admin skips LRCLIB: write a **skip marker**, a header-only `.lrc`
  holding `[lrclib_skipped:1]`. `ensure_lrc` reuses it (no fetch), the fill
  finds no cues and does nothing (`no_mapping`), and a later "reprocess all"
  keeps it, so the admin's skip survives bulk passes;
- a Genius pick whose id differs from the bundle's recorded Genius id: delete
  the `.lrc` before the run, so the automatic fetch runs for the new song.
  The same id keeps it. **This also fixes the CLI defect** where
  `--song X --reset` re-picked Genius but kept the old song's `.lrc`.

### D4. State that survives a restart

`get_data_directory()/library_tools/state.json`, **not** the temp directory:
`app.py` deletes `k.temp_dir` on exit, which is also where the Genius choice
sidecars live. It holds the open bulk run (mode, songs, caption-check
results, picks) and the needs-a-pick list. Writes are atomic (sibling `.tmp`
plus `os.replace`) under one lock. Regen jobs themselves live in memory only.

### D5. Bulk runs

At most one open run at a time. A run is open while it checks captions or
waits for picks; queueing it ends it (its jobs then live in the processing
queue).

| Mode | Songs | Caption check (one yt-dlp call each) | Needs a pick | Plan at queue time, no pick made |
|---|---|---|---|---|
| `stale` (Update stale songs) | bundle `schema_version` below `SCHEMA_VERSION` | songs with no reusable source and a YouTube ID | no reusable source, and no YouTube ID or the check failed | reuse plan (`reuse_plan`), else caption plan (`fetch`) when the check passed |
| `all` (Reprocess all) | every video | as `stale` | as `stale`; "no lyrics" songs do not need one | reuse plan; "no lyrics" songs transcribe; else caption plan when the check passed |
| `reset` (Reset all) | every video | every song with a YouTube ID | no YouTube ID, or the check failed | caption plan (`fetch`) |

- A pick is `genius` (a Genius hit: `sidecar` plan with its id), `keep` (the
  bundle's current Genius id: `sidecar` plan with that id, offered only when
  the bundle records one), `transcribe`, or `skip` (left out of this run).
- `reset` jobs wipe the song's outputs; `stale` and `all` jobs don't (the CLI
  does the same).
- Queueing takes one whole-folder backup (`backup_text_folders(folder)`, as
  the CLI does without `--song`), then enqueues one `RegenJob` per song. A
  song already waiting or running in the processing queue is left out and
  counted.
- A caption plan re-downloads the caption at run time, into `subtitles/`,
  and applies the gate again (`fetch_caption`). The preview's check only
  measured a throwaway copy, so the library is never written before the
  backup. If the caption fails at run time, the job fails with a message
  that names Song Info's repair as the fix.

### D6. The after-download caption check and the needs-a-pick list

`LibraryTools` handles `song_downloaded` (it takes over
`ProcessingManager`'s subscription):

- a Genius choice sidecar exists for the video (the search page's picker made
  a choice) → queue for processing, as today;
- otherwise gate the caption the download saved (`gate_on_disk_caption`, no
  network): passes → queue; too sparse (the file is deleted, as
  `adopt_caption` does) or no caption → add to the **needs-a-pick list** and
  emit `needs_pick`;
- a title that matches the blocked-words preference → queue it (the queue
  skips it, as today).

Resolving a needs-a-pick song writes the choice sidecar (Genius id, or
`{"mode": "raw"}` for transcribe) and queues it, so `LyricsFetchStage` does the
rest, LRCLIB included. The entry stays (shown as picked) until that song's
`processing_complete`, so a restart before then shows it again.

### D7. Processing page

- **Admin:** tabs Jobs / Library tools. Jobs: chips All / Active / Attention
  / Finished with counts; a "Now" box for the running job (title, kind,
  phase in words, elapsed time); compact rows (queue position, title, a
  subline with kind / source / who / when, a status tag) that expand to show
  details and actions; "Clear N finished". Rows come back from the server
  already ordered.
- **Guest:** no tabs and no chips. Three headed sections (Getting ready /
  Ready / Problems), the guest's own rows tagged YOU, plain-language failure
  text, never a regen or library row.
- **Attention** holds failed rows, needs-a-pick rows, and songs left
  unfinished or failed in an earlier session (from the DB's `pipeline_state`,
  today shown only as badges in the browser). Each gets a way to act.
- **Row kinds** (`PipelineItem.kind`): `download` (today's rows; cancelling or
  removing one deletes the song, unchanged), `regen`, and `process`
  (processing of a song already in the library: a retry, an unprocessed
  playlist song). `regen` and `process` rows never delete files.
- Confirmations happen inside the expanded row, not in `window.confirm()`.
- Labels are plain words: `srt+…` shows as "YouTube captions", `genius+…` as
  "Genius", `transcribe` and `none+…` as "No lyrics", `override+…` as "Lyrics
  file". The `genius+tiling` warning is dead code (the pipeline no longer
  produces that value) and is deleted.

### D8. The mockup and where the build deviates from it

The chosen boards are on this branch in `plans/web-library-tools-mockup/`.
Read them as text; they reference a `support.js` that isn't there. They are
also published at https://claude.ai/artifact/LAE9pK75B1hifo8miSmYQo (canvas;
the A variants there were not chosen). Build with Bulma 0.9 components and the
app's dark theme (`static/bulma-dark.css`): `.tabs`, `.tag`, `.button`,
`.box`. Use the mockup's hex colours only where Bulma has no match (for
example, the timing bar's segments). Keep touch targets at least 44 px tall,
and lay out for a 390 px phone first. The names and numbers in the mockup
are examples.

Deviations, decided here:

- The Now box shows the phase in words plus elapsed time. **No "step N of M"
  bar:** the pipeline reports phases, which repeat and vary by song, so there
  is no fixed step count to show.
- The guest intro is one sentence: "Songs being downloaded and prepared for
  karaoke." The board's second sentence (about hidden maintenance) is system
  information and is dropped (decision 16).
- **In a repair, the Genius and LRCLIB search boxes start empty** (decision
  4). The board's filled values are examples. The bulk pick pass prefills
  Genius with the cleaned title (decision 15).
- The playlist box takes playlist links only. A link to a single video gets
  a message pointing to the search page.
- The board's "No lyrics (0)" is 2 on the real library today.

### D9. Not in this plan

The search-picker change (decision 18); restoring from a backup; regenerating
non-video songs (`.mp3`, CDG `.zip`: Song Info says the tools work on videos
only); updating the translation catalogue (new strings use `{% trans %}` and
`_()` like the existing pages, and the `.pot` is not regenerated); keeping the
processing queue across restarts.

## Where things live

- **Branch:** `web_library_tools`, off `library_tools` at `0bfa02a`. It
  carries this plan, the mockup boards, and the code.
- **Worktree:** Ken's main checkout is on `dev` and the app runs from it, so
  **never switch that checkout.** Run `git worktree list`; if the branch isn't
  checked out anywhere, run
  `git worktree add <your scratchpad>/wt_weblib web_library_tools`. Follow
  memory `regen-reprocessing-workflow` ("Running from a scratch worktree":
  `python -P`, the `models` junction, remove the junction before
  `git worktree remove`) and memory `project_dev_environment_map` (copy
  `libmpv-2.dll` into the worktree's `.venv\Scripts` after its first `uv run`).
  Confirm `uv run --no-sync python -P -c "import pikaraoke; print(pikaraoke.__file__)"`
  prints the worktree's path before trusting any result.
- **Commits:** plan edits (Results log rows, status) and code are **separate
  commits**, never mixed. The branch is never merged into `dev`; its code
  commits reach `dev` by cherry-pick (memory `feedback_master_landing`), and
  a mixed commit would drag the plan along.
- **The real library** is `D:/Shared/pikaraoke-songs`. It is **read-only**
  for this plan: copy from it, never write to it, never point a run of the
  app or a tool at it.
- **Scratch library** (built in Phase 0): `D:/shared/weblib-test/`.
- **Isolated app run** (Phases 3-9). The app keeps its DB, `config.ini`, temp
  folder and this plan's state under `%APPDATA%\pikaraoke`; pointing
  `APPDATA` at a scratch folder keeps Ken's DB and config untouched. From the
  worktree root in PowerShell:

  ```
  $env:APPDATA = "<your scratchpad>\appdata"
  $env:PYTHONUTF8 = "1"
  uv run --no-sync python -P -m pikaraoke.app --download-path D:\shared\weblib-test --port 5556
  ```

  Before the first run, copy Ken's `%APPDATA%\pikaraoke\config.ini` (read it
  with the real `APPDATA`) to `<your scratchpad>\appdata\pikaraoke\config.ini`,
  so the Genius token comes along. Confirm in the app log that the library
  path is the scratch folder. If the copied config's `download_path` wins over
  the flag, edit the **copy**. Never write the Genius token or an admin
  password into the plan, a commit, or chat. If the config sets an admin
  password, send it as the `admin` cookie from `curl`.
  The app opens an mpv window on Ken's screen; say so when relaying.

## Ground rules (STOP and report, don't work around)

- Ken's app is running (something is listening on port 5555, or a
  `pikaraoke` process runs from the main checkout) when you are about to
  start the scratch app or any GPU run. Two GPU pipelines at once are much
  slower (memory `concurrent-gpu-inference-rejected`). Ask Ken; never stop
  his app yourself.
- A change seems needed in a file D1 doesn't list.
- A test outside the baseline's known failures fails and you can't fix it
  within the phase's own scope.
- The UI needs something the decisions, D1-D9 and the mockup don't settle.
  Don't invent screens, wording that shows system information to guests, or
  extra options.
- Any file in the real library changes (compare the Phase 0 manifest).
- Phase-specific STOPs are listed in each phase.

## Every phase ends the same way

1. The full unit suite: the baseline plus the phase's new tests, with no new
   failures. Then pre-commit (CLAUDE.md), and an import smoke of the changed
   modules.
2. Read `git diff --cached` against the phase text before each code commit
   (CLAUDE.md, Commits), and do the self-review (correctness, simplicity,
   robustness).
3. Code commit(s) as named in the phase. Then a Results log row (raw facts:
   commands, counts, hashes, paths, what the live checks showed; no
   verdicts) in its own `docs(plan)` commit, plus the status block.
4. Relay to Ken in plain language: what works now, what he can try (the
   matching part of "Ken's checks"), anything that stopped you, and whether
   a review is due. This is a good point to `/compact` (CLAUDE.md).
5. Go on to the next phase only when Ken says so. Phases 0-2 may run
   back to back.

## Phase 0: setup and baseline (no code)

1. Worktree as above. Merge `dev` into the branch:
   `git merge --no-ff dev -m "merge dev: schema v11 and edge-snap repairs"`.
   `dev` is 4 commits ahead of `library_tools` (schema v11, the
   interior-pause repair, CLAUDE.md's graphify notes) and merges cleanly
   (checked 2026-10-20 with `git merge-tree`). Without it, the branch writes
   v10 bundles and the real library's 5 v10 songs don't count as behind, so
   nothing could test "update stale". A merge commit is harmless here:
   landing is by cherry-pick of named commits.
2. Baseline: `uv run --no-sync python -P -m pytest tests/unit -q` in the
   worktree. Record the pass/fail/skip counts and each failure's id. Memory
   `project_windows_dev_box` lists the known Windows failures (4, or 10 when
   a swept scratch venv lost babel's locale data; repair per that memory).
3. **Real-library manifest** (read-only): with a stdlib Python script in your
   scratchpad (`uv run --no-sync python -I <script>`), write path, size and
   mtime for every file under `D:/Shared/pikaraoke-songs` to your
   scratchpad. Phase 9 compares against it.
4. **Scratch library:** `D:/shared/weblib-test/` must not exist yet (if it
   does, STOP). Create it and copy in the full file set of these songs from
   the real library: the video, plus every entry in `vocal/`, `nonvocal/`,
   `dereverb/`, `subtitles/`, `karaoke/`, `lyrics/`, `alignment_debug/` that
   the song's stem owns (the `_owner` rule in the regen script: the name
   equals the stem or starts with `stem + "."`, longest stem wins). Use
   Python, not PowerShell; names hold `[...]`, soft hyphens and CJK (memory
   `project_windows_dev_box`). Pick each song by its YouTube ID:

   | ID | Why |
   |---|---|
   | `xFYQQPAOz7Y` | Genius, v10: behind |
   | `fJ9rUzIMcZQ` | caption, v10: behind |
   | `DYptgVvkVLQ` | Genius, v10, Mandarin, looks poor |
   | `AoON1CyhQAM` | Genius, v11, looks poor, LRCLIB rejected (Defying Gravity) |
   | `8NJVNkzhJM4` | no bundle, has a karaoke file: no lyrics |
   | one caption song with a v11 bundle (your choice; record it) | current |

   Also copy each `regen_backup_*/alignment_debug/<AoON1CyhQAM stem>.json`
   to the same relative path, so the History tab has data. Then make one
   song without a YouTube ID: copy one more Genius song's files and rename
   the copies, dropping the `---<id>` from every name (scratch only; record
   which song). Record the file count per folder.
5. Commit nothing but the merge. Results log row (baseline counts, merge
   hash, the scratch song list and file counts), its own `docs(plan)`
   commit. Relay, then go on to Phase 1.

## Phase 1: shared core (pure move, no behaviour change)

### 1a. `pikaraoke/lib/library_regen.py`

Move from `scripts/regen_alignment_bundles.py`. The quoted names are the
anchors at `0bfa02a`. Names used from other modules lose their underscore:

| In the script | In `library_regen` |
|---|---|
| `VIDEO_EXTS`, `MIN_CAPTION_WPM`, `OUTPUT_DIRS`, `BACKUP_DIRS`, `KEEP_ON_RESET` | same |
| `SeedArtifactsStage`, `Plan`, `SongJob`, `scan_folder`, `resolve_plan`, `_fetch_or_prompt_plan`, `adopt_caption`, `backup_text_folders`, `clear_output_folders`, `_srt_word_count`, `_stems_present`, `_dereverb_cache`, `_all_stems`, `_claims`, `_owner`, `_owned_by_any`, `_clear_dir`, `_remove` | same |
| `_read_bundle`, `_list_videos`, `_find_local_srt`, `_reuse_plan`, `_media_duration`, `_caption_wpm`, `_default_query`, `_build_stages`, `_prepare_lyrics` | `read_bundle`, `list_videos`, `find_local_srt`, `reuse_plan`, `media_duration`, `caption_wpm`, `default_query`, `build_stages`, `prepare_lyrics` |
| the loop body of `execute_fetches` | `fetch_caption(job: SongJob) -> None` (one song: download into `subtitles/`, then `adopt_caption`, or fall back to the plan's fallback) |
| the per-job body of `execute_lrclib_backfill`, with its `try`/`except` | `backfill_lrc(job: SongJob, config: PipelineConfig) -> None` (never raises; logs) |

- `prepare_lyrics`' two `print()` calls become `logger.warning(...)`. The CLI
  still shows them through its INFO logging; the app has no stdout.
- Staying in the script: `print_report`, `prompt_jobs`, `_prompt_one`,
  `execute_fetches` (its print plus a loop over `fetch_caption`),
  `execute_lrclib_backfill` (filter, print, loop over `backfill_lrc`),
  `run_jobs`, `_make_genius`, `setup_process`, `parse_args`,
  `resolve_and_run`, `main`. The script imports the core by name. Its module
  docstring stays (it describes the tool); the core module gets a short
  docstring saying the CLI and the web UI share it.

### 1b. `pikaraoke/lib/library_links.py`

Move from `scripts/add_songs.py`: `_YOUTUBE_ID_RE`, `classify_url`,
`expand_playlist`, `library_files`, and `_library_status`, renamed
`file_status` (the module name `library_status` is taken by Phase 2B).
`library_files` uses `library_regen.VIDEO_EXTS`. `UrlEntry`, `resolve_urls`,
`print_report`, `handoff` and the CLI stay in `add_songs.py`, which now calls
the core names instead of `rab.<private>`.

### 1c. Tests

Move the tests that exercise moved functions into
`tests/unit/test_library_regen.py` and `tests/unit/test_library_links.py`,
updating imports and `patch()` targets. Tests of the CLI flow stay where they
are. **The total test count must equal the baseline's**, and every test
passes except the baseline's known failures.

### 1d. Verify and commit

- `uv run --no-sync python -P scripts/regen_alignment_bundles.py --help` and
  the same for `add_songs.py` both print their help.
- Dry run on the **real** library (read-only):
  `... regen_alignment_bundles.py D:/Shared/pikaraoke-songs --dry-run` lists
  the same songs and plans as the same command run from the
  `library_tools` worktree. Record both outputs' song counts.
- `pre-commit run --config code_quality/.pre-commit-config.yaml --all-files`
  (with `plans/` and `static/` excluded, per CLAUDE.md).
- One commit: `refactor(library): move the regen and add_songs core into pikaraoke/lib`.

**STOP if** the dry runs differ, or the test count changes.

## Phase 2: core additions

### 2A. LRCLIB: one record by id, the skip marker, and the choice rule

`pikaraoke/lib/lrclib.py`:

```python
GET_URL = "https://lrclib.net/api/get/{id}"
SKIP_TAG = "lrclib_skipped"

def get_record(record_id: int, *, timeout: float = _REQUEST_TIMEOUT_S) -> dict | None:
    """``GET /api/get/{id}``: one record with its synced lyrics, or None on any failure."""

def write_skip_marker(path: Path) -> None:
    """Record that the admin chose no LRCLIB match (a header-only .lrc).

    ensure_lrc reuses any file on disk, so the marker stops the automatic
    fetch; it has no stamped lines, so the fill finds no cues.
    """

def is_skip_marker(path: Path) -> bool:
```

- `get_record` mirrors `search`: `User-Agent`, `raise_for_status`, the polite
  sleep, catches `requests.RequestException` and `ValueError`, logs a warning.
- `write_skip_marker` writes `[lrclib_skipped:1]\n` with the same sibling
  `.tmp` plus replace that `write_lrc` uses.

`pikaraoke/lib/library_regen.py`:

- `Plan` gains `lrclib_record: dict | None = None` and `lrclib_skip: bool = False`.
- New `apply_lrclib_choice(job: SongJob) -> None`, called first thing in
  `prepare_lyrics`:
  1. `lrclib_skip` → `write_skip_marker(lyrics/<stem>.lrc)`;
  2. else `lrclib_record` → `write_lrc(lyrics/<stem>.lrc, record)`;
  3. else a `sidecar` plan whose `genius_id` differs from the bundle's
     `lyrics.genius.id` (or the bundle has none) → delete `lyrics/<stem>.lrc`
     if present;
  4. anything else: leave the file alone.

Tests (`test_lrclib.py`, `test_library_regen.py`, with `requests.get` mocked):

- `get_record` returns the JSON; returns None on an HTTP error and on bad JSON.
- The marker round-trip: `is_skip_marker` is true for the marker and false
  for a real `.lrc`. `ensure_lrc` returns the marker path without calling
  `search`. `lrclib_fill.plan_fills` on the marker's text gives `eligible`
  False with reason `no_mapping`.
- `apply_lrclib_choice`: a different Genius id deletes the file; the same id
  keeps it; a bundle without a Genius id deletes it; a record writes it; skip
  writes the marker; a seed or transcribe plan leaves it alone.
- **The CLI defect, end to end in the script's test style:** `--song X
  --reset` whose prompt picks a different Genius id leaves no old `.lrc` when
  `LyricsFetchStage` would run (patch the pipeline run).

Live check (read-only network): `get_record(34563601)` (Defying Gravity's
current match, from its bundle) returns a record whose `trackName` is
"Defying Gravity" and which has `syncedLyrics`. If LRCLIB has no
`/api/get/{id}` route or returns something else, STOP.

Commits: `feat(lrclib): fetch one record by id, and a marker for a skipped match`;
`fix(regen): a new Genius pick drops the old song's LRCLIB match`.

### 2B. `pikaraoke/lib/library_status.py` (read-only)

```python
POOR_GUESSED_SHARE = 0.15  # Ken, 2026-10-20: 15%+ of lines guessed "looks poor"

@dataclass(frozen=True)
class SongStatus:
    path: Path
    youtube_id: str | None
    category: str            # "current" | "behind" | "no_lyrics" | "not_processed"
    schema_version: int | None
    origin: str | None       # bundle lyrics.origin: "srt" | "genius"
    genius: dict | None      # lyrics.genius: {id, title, artist}
    lrclib: dict | None      # lyrics.lrclib (trackName, artistName, albumName, duration, id)
    lrclib_state: str        # "used" | "rejected" | "none" | "skipped" | "n/a"
    lrclib_reason: str | None  # joint_stats.lrclib_fill.reason when rejected
    lrclib_filled: int       # len(joint_stats.lrclib_fill.filled_lids)
    ytasr_used: bool         # lyrics.ytasr present
    method: str | None       # pipeline_decisions.method_used: "joint" | "cue_align"
    line_count: int | None   # output_summary.line_count
    lines_timed: int | None  # output_summary.lines_with_words
    timed_by: dict | None    # joint only: {"aligner", "transcription", "captions"} from align_won / transcribe_won / ytasr_won
    media_duration_s: float | None
    captured_at: str | None

    @property
    def guessed(self) -> int | None: ...   # line_count - lines_timed
    @property
    def poor(self) -> bool: ...            # guessed / line_count >= POOR_GUESSED_SHARE

def song_status(song: Path) -> SongStatus: ...
def library_statuses(folder: Path) -> list[SongStatus]: ...   # every video, list_videos order
def overview_counts(statuses: list[SongStatus]) -> dict[str, int]: ...  # behind, poor, no_lyrics, all

@dataclass(frozen=True)
class HistoryEntry:
    captured_at: str
    schema_version: int | None
    genius: dict | None
    lrclib: dict | None
    line_count: int | None
    lines_timed: int | None
    backup: str | None       # backup folder name; None for the current bundle

def song_history(song: Path) -> list[HistoryEntry]: ...
```

- **Category:** a readable bundle with `schema_version < SCHEMA_VERSION` is
  `behind`, otherwise `current`. No bundle (or an unreadable one, via
  `read_bundle`) plus `karaoke/<stem>.ass` is `no_lyrics`; neither is
  `not_processed`.
- **`lrclib_state`:** `n/a` unless the origin is `genius`. Then `skipped`
  when `lyrics/<stem>.lrc` is a skip marker (from disk, the current choice);
  else `used` when `lrclib_fill.eligible` is true; `rejected` when the bundle
  recorded an `.lrc` (`lyrics.lrclib`) but the fill wasn't eligible; else
  `none`.
- **`song_history`:** the current bundle first (`backup=None`), then each
  `regen_backup_*` folder newest first. Read
  `<folder>/alignment_debug/<stem>.json`, skip a `captured_at` already listed,
  and keep the first (newest) folder for each version. Sort by `captured_at`,
  newest first.

Tests (`tests/unit/test_library_status.py`, `tmp_path` bundles): each
category; `poor` at exactly 15% and just under; each `lrclib_state`; history
dedupe (one version copied into two backups is listed once, under the newer
folder), the order, and the current bundle on top.

Live check (read-only): over the real library, record `overview_counts`
(expected today: behind 5, no_lyrics 2, all 48; record `poor` as it comes),
and `song_history` for `AoON1CyhQAM` (expected: the current version plus two
older ones, 51 of 89 lines timed in each).

Commit: `feat(library): read song status, alignment stats and history from bundles`.

### 2C. A caption check that writes nothing, and playlist titles

`library_regen`:

```python
@dataclass(frozen=True)
class CaptionCheck:
    found: bool
    wpm: float | None
    passed: bool

def check_caption(job: SongJob) -> CaptionCheck:
    """Download the manual English caption into a throwaway folder and measure it.

    Nothing in the library is written, so a preview can run before the backup.
    """

def gate_on_disk_caption(job: SongJob) -> bool:
    """Gate the caption a download already saved (no network). True when it passes;
    a too-sparse caption is deleted, as adopt_caption does."""
```

- One pass/fail rule, shared by `adopt_caption`, `check_caption` and
  `gate_on_disk_caption`: `wpm is None or wpm >= MIN_CAPTION_WPM` (today's
  `adopt_caption` rule). Factor it out rather than copying it.
- `check_caption` downloads with `download_manual_en_subs` into
  `tempfile.mkdtemp(prefix="caption_check_", dir=get_temp_directory())` and
  removes that folder in `finally`.
- `gate_on_disk_caption` uses `find_local_srt`, then `adopt_caption` with a
  `fetch` plan whose fallback is the Genius prompt, and returns whether the
  plan became `seed`.

`library_links`:

```python
@dataclass(frozen=True)
class PlaylistVideo:
    id: str
    title: str

@dataclass(frozen=True)
class Playlist:
    title: str
    videos: list[PlaylistVideo]

def read_playlist(url: str) -> Playlist:
    """yt-dlp --flat-playlist -J. May raise CalledProcessError, TimeoutExpired, ValueError."""
```

- `expand_playlist(url)` becomes `[v.id for v in read_playlist(url).videos]`:
  one yt-dlp call shape. Drop entries without an `id`.
- `add_songs.resolve_urls` also catches `ValueError` (bad JSON) with the
  same "failed to expand playlist" line. Update `test_add_songs.py`'s mocked
  yt-dlp output to the JSON shape.

Tests: `check_caption` with `download_manual_en_subs` mocked (none, sparse,
dense, unmeasurable) leaves no file behind in the song folder or in the
temp folder; `gate_on_disk_caption` (no caption, sparse caption deleted,
dense caption kept); `read_playlist` parses the title, ids and titles, and
skips id-less entries.

Live checks (read-only network): `check_caption` on `fJ9rUzIMcZQ` (has a
caption) and on `xFYQQPAOz7Y` (Genius song; record what comes back);
`read_playlist` on any small public playlist (record the URL, the title and
the video count, and compare the count with the playlist page).

Commit: `feat(library): check a caption without touching the library, and read playlist titles`.

Relay after Phase 2: the core is shared and the LRCLIB re-pick defect is
fixed in the CLI as well.

## Phase 3: regen jobs in the processing queue (backend)

### 3a. Orchestrator

`run_one_async(self, song_path, lyrics_path=None, stages: Sequence[PipelineStage] | None = None)`,
passed to `_run_pipeline`, which runs `stages` when given, else
`self._stages`. Test in `test_orchestrator.py`: a given list runs instead of
the fixed one.

### 3b. `library_regen`

```python
@dataclass
class RegenJob:
    song: SongJob
    reset: bool
    label: str

class RegenError(Exception):
    """A regen job can't start; the message is for the admin."""

def prepare_regen_job(
    regen: RegenJob, genius: GeniusClient, config: PipelineConfig, lyrics_dir: Path
) -> tuple[Path | None, BaseStage | None]:
```

In order:

1. `reset` → `clear_output_folders(folder, stems=[stem])`. An `OSError`
   becomes `RegenError("A file of this song is in use: ... Close the player
   and retry.")`.
2. A `fetch` plan → `fetch_caption`; if the plan isn't `seed` afterwards,
   raise `RegenError("The YouTube caption no longer passes the lyrics check.
   Use Repair lyrics on Song Info to pick lyrics.")`.
3. A `seed` plan with `lyrics_origin == "genius"` → `backfill_lrc` (the
   automatic LRCLIB fetch for reused Genius picks).
4. `return prepare_lyrics(...)` (which applies the LRCLIB choice first).

```python
def finish_regen_job(job: SongJob) -> None:
    """After a successful run: a transcribe plan removes the song's old bundle."""
```

A transcribe run writes no bundle, so the old one would stay. Song Info would
then show the old lyrics, and the next reuse run (CLI default or "reprocess
all") would bring them back. The backup holds the removed bundle. The app
calls this after a successful regen; the CLI's `run_jobs` calls it after each
successful song too (one line, the same core rule).

Tests: each step with the network and the pipeline mocked; the reset wipe
leaves `.en.asr.json3` and `.lrc` (`KEEP_ON_RESET`); `finish_regen_job`
removes the bundle for transcribe and nothing for the other plans.

### 3c. `ProcessingManager`

- `__init__` gains `is_playing: Callable[[str], bool] | None = None`.
- Extract the blocked-words test from `enqueue` into `is_blocked(song_path) -> bool`.
- `enqueue` emits `processing_queued` (song path) after it queues.
- `start()` stops subscribing to `song_downloaded`; `karaoke.py` subscribes
  `processing_manager.enqueue` **after** constructing the `PipelineTracker`,
  so the tracker's `song_downloaded` handler runs first (`EventSystem` calls
  handlers in registration order) and the item has its `song_path` when
  `processing_queued` arrives.
- Regen lane: `self._regen_jobs: list[RegenJob]` under `_state_lock`.
  `enqueue_regen(regen) -> bool` refuses (returns False) when the path is
  active or in `pending_jobs`; otherwise it appends the job, appends the path
  to `pending_jobs`, and emits `regen_queued` with
  `{"song_path", "label", "job"}`.
- `cancel_pending(song_path)`: a path in the regen lane is removed from the
  lane and from `pending_jobs`, and is **not** added to `_cancelled_paths`
  (that set is only for the download queue; an entry for a regen path would
  leak and later swallow a real download of that song). Otherwise unchanged.
- `_run_loop`: on `queue.Empty`, take the first regen job whose song isn't
  playing (`_take_regen_job`) and run it. Factor the existing `finally`
  (clear `pending_jobs`, clear `_active`, restart dead workers) into one
  helper both job kinds use.
- `_process_regen(regen)`: a lifecycle log line; a temp lyrics folder under
  the intermediate dir (removed in `finally`); `prepare_regen_job` (a
  `RegenError` or any other exception → `processing_error` with its message,
  and return); stages `[PreparePtyStage(fd), *build_stages(song, lyric_stage,
  whisper, regen_config, stem_worker)]`, where
  `regen_config = dataclasses.replace(self._config, cache_dereverb_stem=True)`
  (the CLI sets the same flag); then run it.
- Share the launch/join/report tail of `_process_song` with
  `_process_regen` through one helper with a `mark_failed: bool` argument:
  `True` for downloads (today's behaviour), `False` for regen (D2). The
  helper calls `finish_regen_job` after a successful regen.
- **The launch can raise:** `run_one_async` validates its inputs on the
  calling thread, so a song file that is gone (deleted or renamed while the
  job waited) raises `FileNotFoundError` before any pipeline thread exists.
  Today that escapes `_process_song` and ends the run loop, because
  `_run_loop` has `try`/`finally` and no `except`. The shared helper treats
  a launch exception as a failed job (log it, emit `processing_error`), for
  both job kinds.
- `_ActiveJob` gains `kind` and `started_at` (`time.monotonic()`); add
  `get_active_elapsed_s() -> float | None`.
- Subscribe `song_deleted`: drop regen jobs for that path.
- `karaoke.py`: pass
  `is_playing=lambda p: self.playback_controller.now_playing_filename == p`.

### 3d. `PipelineTracker`

- `PipelineItem` gains `kind` (`"download"` default, `"regen"`, `"process"`),
  `label: str | None`, `regen_job`, `finished_at: float | None`.
- `_on_regen_queued(data)`: drop terminal items for that path, then append a
  `regen` item (`download_status="complete"`, `song_path` set, title from the
  song manager's display name, the job kept for Retry).
- `_on_processing_queued(song_path)`: if a non-terminal item for that path
  exists, do nothing (it shows as pending). Otherwise drop terminal items for
  that path and append a `process` item (label `Process`).
- Complete / error / cancelled handlers update the first **non-terminal**
  item with that path, and set `finished_at` (`time.time()`) on complete and
  error.
- `_on_processing_cancelled` and `cancel()` delete the song file only for
  `download` items.
- `remove()` (deletes the song) is offered and allowed only for `download`
  items.
- New `dismiss(item_id)` (terminal items, drops the row, never touches files),
  `retry(item_id)` (an error item with a song path: a `regen` item re-enqueues
  its job; any other kind sets processing back to `waiting`, clears the
  error, then `processing_manager.enqueue(path)`), and `clear_finished() -> int`
  (drops every complete item).
- `get_status` leaves out `regen` items for non-admins. Each dict adds
  `kind`, `label`, `finished_ago_s`, and `elapsed_s` for the running item.
  Actions: `dismiss` (admin, terminal), `retry` (admin, processing error with
  a song path), `remove` (admin, terminal `download` items only), `cancel`
  and `enqueue` as today.

### 3e. Routes (`routes/processing.py`, all admin-only, JSON `{"success": ...}`)

`POST /processing/<item_id>/retry`, `POST /processing/<item_id>/dismiss`,
`POST /processing/clear_finished` (returns the count).

### 3f. Tests

- `ProcessingManager`: a download queued after two regen jobs runs before
  the second regen job; a regen job for the playing song is skipped while
  another runs, and runs once the song stops playing; `cancel_pending` on a
  regen path leaves `_cancelled_paths` empty and a later download of that
  path still runs; a failed regen leaves `pipeline_state` as it was; a
  successful regen sets `ready`; a missing song file at launch emits
  `processing_error` and the loop keeps running the next job (both kinds); `enqueue_regen` refuses a path already
  pending; `song_deleted` drops a queued regen job; a `RegenError` emits
  `processing_error` with its message and runs no pipeline.
- `PipelineTracker`: a regen item is hidden from guests; cancelling a
  pending or active regen item never calls `song_manager.delete`; `remove`
  isn't offered for regen or process items; `dismiss`, `retry` (both kinds)
  and `clear_finished` never delete; `processing_queued` for a song with a
  live download item adds no row; for a song with no item it adds a
  `process` row.
- Update existing tests that relied on the `song_downloaded` subscription in
  `start()`.

Verify: the full suite at baseline plus the new tests; import smoke; start
the isolated app (Ground rules first) and confirm the old Processing page
still loads and a search download still processes. Nothing queues regen jobs
yet, so record only that the page loads and the download completes.

Commits: `feat(pipeline): an orchestrator run can take its own stage list`;
`feat(processing): regen jobs queue behind downloads and never delete songs`;
`feat(processing): retry, dismiss and clear-finished actions`.

**Review due:** this phase changes the core queue and its concurrency. When
you relay, say a `/code-review` is due at this boundary. Don't run it unless
Ken asks.

## Phase 4: Song Info, song lists, Regenerate

### 4a. `LibraryTools` (first slice)

Constructed in `karaoke.py` after the tracker, as `self.library_tools`
(annotated next to `pipeline_tracker`), with the events, processing
manager, song manager, Genius client, download manager and download path.

- `status(song) -> SongStatus`, `history(song)`, `overview()` (wrapping
  Phase 2B over `download_path`).
- `is_busy(song) -> bool`: active, or in `pending_jobs`.
- `regenerate(song) -> None`: the plan is `reuse_plan(SongJob(...))`; a
  `no_lyrics` song gets a `transcribe` plan; any other song without one
  raises `RegenError("Pick lyrics with Repair lyrics first.")`. Back up that
  song only (`backup_text_folders(folder, stems=[stem])`), then
  `enqueue_regen(RegenJob(job, reset=False, label="Regenerate"))`. A busy
  song raises `RegenError`.

### 4b. Routes

Every route that takes a song path rejects one that isn't in the library
(`k.song_manager.songs`; use `SongList`'s own membership test) with 400. Song
paths come from the client, so this check is what stops the pages reading or
backing up arbitrary files. A non-admin is redirected with a flash on a page
route, the way `files.edit_file` does it, and gets 403
`{"success": false, "error": ...}` on a JSON route, the way
`routes/processing.py` does it.

- `GET /song_info?song=<path>` → `song_info.html`.
- `POST /song_info/regenerate` (JSON `{song}`) → `{success, error?}`.
- `GET /library/overview` → counts JSON (used by the Processing page in Phase 5).
- `GET /library/songs?list=behind|poor|no_lyrics|all` → `library_songs.html`.
- Register `song_info_bp` and `library_bp` in `app.py` the way the existing
  blueprints are registered.

### 4c. `song_info.html` (boards `SongInfoB`, `SongInfoBAlign`, `SongInfoBHistory`)

- **Header:** the YouTube thumbnail
  (`https://img.youtube.com/vi/<id>/mqdefault.jpg`, as `search.html` uses)
  when the song has an ID; the display name the song browser shows; the
  duration (m:ss) from the bundle.
- **Tiles:**
  - Lyrics: `Genius` / `YouTube captions` / `No lyrics` / `Not processed`;
    subline "up to date" or "behind (vN)".
  - Timed: the percentage of lines timed; subline "N guessed". Amber outline
    when `poor`.
  - LRCLIB (Genius songs only, else "—" with "Genius songs only"): `Used`
    ("fills N lines"), `Not used` (the length difference when 5 s or more,
    e.g. "97 s longer", else the reason's short text), `None` ("no match
    found"), `Skipped` ("skipped by you"). Amber outline when the song is
    poor and LRCLIB is `Not used` or `None`.
- **Tabs** (client-side show/hide; everything rendered server-side):
  - **Picks:** rows Source, Genius (title, artist, a link to
    `https://genius.com/songs/<id>`), LRCLIB (track · artist · m:ss, or
    Skipped / None), Captions ("YouTube auto-captions used" / "not used").
    The last three show only for Genius songs.
  - **Alignment:** "N of M lines timed word by word", plus "The other K are
    placed between their neighbours." when K > 0. A stacked bar and legend:
    on the joint route, aligner / transcription / YouTube auto-captions /
    LRCLIB fill / guessed, using the board's colours (LRCLIB fill `#1abc9c`);
    on the caption route, timed / guessed. Bar widths are each count over
    the line count, with no rounding fixes. Then the LRCLIB fit block (Genius
    songs): "The match is m:ss; this video is m:ss (N s longer/shorter)." and
    one status line. Then the route block (below).
  - **History:** the board's list, the footnote "A version saved in several
    backups is listed once, under its newest folder.", and the empty state
    "No earlier versions yet. Versions appear here once a regen has backed
    this song up."
- **Status and route text** (in the route module, through `_()`):
  - LRCLIB fit: `arm_a_bail`, `slope_bail` and `slope_dev` → "Not used: its
    line times didn't line up with this video. Usually a different
    recording."; `no_mapping` → "Not used: its lines didn't match these
    lyrics."; `negative_start` → "Not used: its timing starts before this
    video does."; `no_env` and `error` → "Not checked on the last run.";
    used → "Used: it filled N lines."; none → "No LRCLIB match was found.";
    skipped → "Skipped: you chose no match."
  - Route: caption → "Lyrics from the YouTube caption, timed against the
    caption's own line times." Genius → "Genius lyrics, timed by combining
    the lyric aligner and a transcription", plus ", and YouTube's
    auto-captions" when `ytasr_used`.
- **Buttons:** Regenerate (secondary; shown only when `regenerate` would
  accept the song). Repair lyrics arrives in Phase 6. A busy song disables
  both and shows "This song has a regen waiting or running." with a link to
  Processing. After a successful POST: "Queued. It runs after any new
  downloads." and the buttons disabled.
- A non-video song shows "Lyrics tools work on video songs only." and nothing
  else below the header.

### 4d. `library_songs.html`

The list's title and its songs sorted by name; each row links to Song Info,
with a subline per list: behind → "Version N"; poor → "N of M lines
guessed"; no lyrics → "Transcribed"; all → "Up to date" / "Behind (vN)" /
"No lyrics" / "Not processed".

### 4e. Links (upstream templates, one link each)

- `files.html`: in the admin cell beside the edit icon, an `icon-info-circled`
  link to Song Info (`title="Song info"`).
- `edit.html`: a "Song info" link near the delete link.

### 4f. Tests and verify

- Route tests in the `test_processing_routes.py` style (a Flask app with the
  blueprint, `get_karaoke_instance` patched): a non-admin is redirected; an
  unknown song path gets 400; the page renders each category; regenerate
  queues one job and backs up only that song (with a `tmp_path` library); a
  busy song is refused.
- **Live:** isolated app, open Song Info for each scratch song and check the
  tiles against Phase 2B's numbers. Regenerate `xFYQQPAOz7Y` (behind): the
  job appears on the Processing page, runs, the bundle becomes v11, the
  backup folder holds only that song's files, and the other scratch songs'
  files are byte-identical. Record the run time.

Commit: `feat(library): Song Info page with picks, alignment and history, and per-song regenerate`.

Relay with Ken's check list (see Ken's checks).

## Phase 5: Processing page redesign

### 5a. Server

- `KaraokeDatabase.get_paths_by_pipeline_state(states: Iterable[str]) -> list[str]`
  (one `SELECT ... WHERE pipeline_state IN (...)`) and its `SongManager`
  forwarder.
- `LibraryTools.attention_rows(tracked: set[str]) -> list[dict]`: DB
  `pending` and `failed` songs that have no tracker item, aren't busy, and
  (from Phase 8) aren't on the needs-a-pick list. Each row has `song_path`,
  `title`, `state` (`unfinished` / `failed`) and `actions` (`retry`,
  `song_info`, `delete`).
- `GET /processing/attention` (admin; `[]` for guests).
  `POST /processing/song/retry` (admin, JSON `{song}`) →
  `processing_manager.enqueue(song)`. Delete reuses `files.delete_file` with
  `referrer=/processing`.
- `PipelineTracker.get_status` returns rows in display order, each with
  `group` (`active` / `attention` / `finished`) and, for waiting rows,
  `position`:
  - active: the running job, then the active download, then pending
    downloads in queue order, then pending processing with `download` rows
    before `regen` and `process` rows, each in queue order;
  - attention: processing or download errors, and (Phase 8) `needs_pick`,
    newest first;
  - finished: complete, newest finished first.
- For admins, complete rows of poor songs carry `guessed` and `line_count`
  (from `library_status`).

### 5b. `processing.html`, rewritten (boards `ProcessingB`, `ProcessingBTools`, `ProcessingGuest`)

- **Admin:** Bulma `.tabs` Jobs / Library tools; the active tab is kept in
  the URL hash (`#jobs`, `#tools`).
  - **Jobs:** the chips (counts from the rows; All is the sum); the Now box
    (title, a kind tag `Download` / `Regen`, the phase in words, elapsed time
    ticking each second from `elapsed_s`); then the rows. A row is one line:
    the position number for waiting rows, the title (truncated), a subline
    (kind or label · `by <user>` for downloads · "N min ago" for finished
    rows · the plain lyric label and, for poor songs, "· N of M lines
    guessed"), and a status tag (Downloading / Waiting / Processing /
    Cancelling / Failed / Needs a pick / Unfinished / Done).
  - Tapping a row expands it: the full error in a scrolling pre-wrap box (at
    most about 12 lines tall), then its actions as buttons: Retry, Song info,
    Add to queue, Cancel, Delete song, Dismiss, as the server's `actions`
    allow. Cancel and Delete song confirm inside the row ("Cancel this job?"
    / "Delete this song from the library?", with a confirm and a keep
    button).
  - "Clear N finished" under the list when N > 0.
  - **Library tools** (this phase): the Library card from `ProcessingBTools`
    (four rows linking to `/library/songs?list=...`, count tags from
    `/library/overview`, fetched when the tab opens) and its footnote. The
    Regenerate card arrives in Phase 7, Add playlist in Phase 8.
- **Guest:** the one-sentence intro, then three headed sections: Getting
  ready (active rows; a needs-a-pick row reads "Waiting for the host"),
  Ready (complete; Add to queue), Problems. Own rows get a YOU tag, others
  "added by <user>". Failure text: a download error → "The download failed.
  Try another video of this song."; a processing error → "This song couldn't
  be prepared. The host can retry it." Cancel stays on the guest's own
  waiting and running rows.
- Keep what works: push updates on `pipeline_updated` with the 10 s fallback
  poll; keyed row updates so spinners don't restart; the `.off()` rebinding
  for the SPA (`$(document).off('click.processing')`,
  `window.socket.off('pipeline_updated')`). Render in server order (no
  `reverse()`). Delete the `genius+tiling` code. Phase words reuse today's
  translated strings.

### 5c. Tests and verify

Route tests: attention rows for guests are `[]`; a DB-`failed` song without a
tracker item is listed; a tracked song isn't; retry queues. Tracker
ordering: the group and position for a mixed set of rows. Template render
tests: admin output has both tabs; guest output has neither tab and no
regen rows.

Live: queue a search download and a Song Info regenerate together in the
isolated app, and check the order, the Now box, the chips, and an expanded
failure (make one fail by renaming a scratch song's video while its regen
waits behind another job, then renaming it back). Set a scratch song's DB
state to `failed` through the app's DB under the scratch `APPDATA`, and
check that it appears under Attention with Retry.

Commit: `feat(processing): Jobs and Library tools tabs, grouped rows, unfinished songs listed`.

Relay with Ken's check list.

## Phase 6: Repair lyrics

### 6a. `LibraryTools.repair`

`repair(song, source, genius_id=None, lrclib_id=None, lrclib_skip=False)`:

- `source` is `"caption"` (a `fetch` plan; YouTube-ID songs only), `"genius"`
  (a `sidecar` plan with `genius_id`), or `"transcribe"`.
- For Genius: `lrclib_id` → `lrclib.get_record(lrclib_id)`; None →
  `RegenError("LRCLIB didn't return that match. Try again.")`; else set
  `plan.lrclib_record`. `lrclib_skip` → `plan.lrclib_skip = True`. Neither →
  the automatic rule (D3).
- Back up that song only, then `enqueue_regen(RegenJob(job, reset=True,
  label="Repair"))`. A busy song raises `RegenError`.

### 6b. Routes (`song_info_bp`, admin)

- `GET /song_info/repair?song=` → `song_repair.html`.
- `GET /song_info/caption_check?song=` → `{found, passed, wpm}`
  (`check_caption`; one yt-dlp call; YouTube-ID songs only).
- The Genius search reuses `/lyrics_search?q=` (`search_bp`).
- `GET /song_info/genius_lyrics?id=` → `{title, artist, text}`. Cache
  fetched songs in `LibraryTools` (a dict of the last 20 by id) so the
  preview and the LRCLIB step don't scrape Genius twice.
- `GET /song_info/lrclib_search?song=&genius_id=&title=&artist=` →
  `{video_duration_s, candidates: [...]}`. Only records with
  `syncedLyrics`; each candidate has `id`, `trackName`, `artistName`,
  `albumName`, `duration`, `duration_diff_s`, `mapped` (the count from
  `map_lines_to_cues(sheet, parse_lrc_lines(synced)[0])`), `sheet_lines`,
  `best` (the record `select_candidate` picks), `current` (its id equals the
  current `.lrc`'s `lrclib_id`), and `syncedLyrics` (for the preview). The
  sheet is `[item["text"] for item in parse_lyric_lines(genius_text)]`, as in
  `LyricsFetchStage`.
- `POST /song_info/repair` (JSON) → `{success, error?}`.

### 6c. `song_repair.html` (boards `RepairGenius`, `RepairLrclib`)

One page, two steps switched client-side, with Back.

- **Step 1, lyric source:** three radio cards.
  - YouTube caption: for a song without an ID, disabled with "This song has
    no YouTube ID."; otherwise "Checking the caption…" while
    `/caption_check` runs, then disabled with "This video has no English
    caption." or "This video's caption is too sparse to be lyrics.", or
    enabled with "Use the video's caption as the lyrics."
  - Genius lyrics: "Search and pick, then choose an LRCLIB match."
  - No lyrics (transcribe): "Words come from what the singer is heard
    singing."
  - The current source carries a "current" tag.
  - With Genius selected: an empty search box, then results as a radio list
    (the bundle's Genius id tagged "current"), and "Preview these lyrics",
    which expands the fetched text in a scrolling box.
  - The button reads "Next: LRCLIB match" for Genius and "Regenerate song"
    otherwise. It stays disabled until the choice is complete.
- **Step 2, LRCLIB:** "Genius pick: <title> · <artist>." Then empty Title and
  Artist fields, Search, and the results, each showing its fit (length and
  difference from the video, "matches N of M lines", tags "best fit" and
  "current"). The best fit is preselected. The last option is "None: skip
  LRCLIB. Guessed lines stay guessed." "Preview selected timing" expands the
  selected candidate's synced lyrics. The board's note (backup, runs behind
  new downloads, waits if the song is playing), then Back / Regenerate song.
- After success: go to Song Info, which shows the busy state.

Add the Repair lyrics button (primary) to Song Info.

### 6d. Tests and verify

Route tests: each source gives the right plan (mock `enqueue_regen`); an
LRCLIB id gives `lrclib_record`; skip gives `lrclib_skip`; a failed
`get_record` returns the error and queues nothing; an unknown song gets 400;
`lrclib_search` marks `best` and `current` (requests mocked).

Live:

- Repair `AoON1CyhQAM` to a different Genius hit with an admin-picked
  LRCLIB candidate: the `.lrc` header carries the picked id and the new
  bundle's `lyrics.genius.id` is the new pick.
- Repair it again with "None": the skip marker is on disk, the Song Info
  tile says Skipped, and the bundle's fill reason is `no_mapping`.
- Regenerate it (reuse): the skip marker survives.
- Repair the no-YouTube-ID scratch song to Genius.

Record what Song Info shows after each.

Commit: `feat(library): repair a song's lyrics with typed Genius and LRCLIB searches`.

Relay with Ken's check list.

## Phase 7: bulk runs and the pick pass

### 7a. `LibraryTools` runs (D5)

- `open_run(mode)`: refuses when a run is open. Builds the song list from
  `library_statuses`, saves the run, and starts a daemon thread that runs
  `check_caption` for each song needing one, saving after each song. On
  startup, a run saved mid-check resumes its unchecked songs.
- `run_view() -> dict | None`: the mode, `checking`, `checked`/`to_check`,
  and the songs grouped (`needs_pick`, `caption`, `reuse`, `transcribe`,
  `skip`, `checking`), each song with its title, status line ("Now: Genius,
  <title> · <artist>", or the caption or transcribed state), `poor`
  (`guessed`/`line_count`), `has_youtube_id`, `can_keep`, and its pick.
- `save_pick(song, pick)`, `keep_all() -> int` (every unpicked song that
  `can_keep`), `discard_run()` (also stops the check thread).
- `queue_run() -> dict`: refuses while checking or while a song still needs
  a pick. Builds each plan (D5), drops `skip`, sets busy songs aside, backs up
  the whole folder, enqueues `RegenJob`s (`reset` for mode `reset`; labels
  `Update` / `Reprocess` / `Reset`), clears the run, and returns
  `{queued, busy, backup}`.

### 7b. Routes (`library_bp`, admin)

`POST /library/run {mode}`, `GET /library/run` (the preview page; with no
open run, redirect to `/processing#tools`), `GET /library/run/status`,
`GET /library/run/picks` (the pick page), `POST /library/run/pick`,
`POST /library/run/keep_all`, `POST /library/run/queue`,
`POST /library/run/discard`.

### 7c. Pages

- **Library tools tab:** the Regenerate card from `ProcessingBTools`.
  Update stale songs [Preview N], Reprocess all [Preview N], Reset all
  [Preview N], each with the board's one-line description, and the footnote
  "Regen jobs wait behind new downloads. Each song's lyric files are backed
  up first." When a run is open, a banner replaces the card: "<Mode> is open:
  k of n picked." [Continue] [Discard], where Discard confirms in place.
- **`library_run.html`** (board `RegenPreview`): the title per mode, a
  one-line explanation per mode, the check-progress box while checking (poll
  `/library/run/status` every 2 s, only while checking), then the groups
  (more than 5 songs collapse behind "Show N more"), with poor and
  no-YouTube-ID notes on rows. Then the backup note and the primary button:
  "Start picks (k of n done)" when songs need picks, else "Queue N songs".
  Last, "Cancel" (discard; confirm in place).
- **`pick_pass.html`** (board `PickPassB`): chips To pick / Picked / Looks
  poor. A row is one line (title and "Now: ...") with Keep (when
  `can_keep`) or Change (when picked). Tapping a row expands the picker: a
  search box prefilled with `default_query(song)`, Search (via
  `/lyrics_search`), results as a radio list (the current pick tagged), and
  the buttons Transcribe, Skip song, Use pick. Every pick saves at once.
  Then "Keep current pick for all N not yet picked", and the primary
  "Queue N songs (k still to pick)", disabled until nothing is left to pick.
  After queueing, go to `/processing#jobs`, with a flash saying how many
  songs queued, how many were left out as busy, and the backup folder name.

### 7d. Tests and verify

Unit tests: the song set and the plan for each mode (D5 table), including
`no_lyrics` in `all` (transcribe) and in `reset` (check, then pick); picks
persist across a new `LibraryTools` instance (a restart); queueing refuses
while picks remain; queueing backs up once and enqueues the right jobs with
the right `reset` flag; busy songs are set aside; `keep_all` counts; discard
clears.

Live, on the scratch library (record times):

1. **Update stale:** preview lists the stale scratch songs, which need no
   picks; queue; all run; then the behind count is 0.
2. **Reset all:** captions checked, the expected songs need picks; make
   some picks, restart the app, check that they're still there, finish,
   queue, and let it run to the end. Check that each song's outputs were
   rebuilt and that the backup folder is complete.

**STOP if** any job in the reset run fails for a reason other than one the
plan names.

Commits: `feat(library): bulk regen runs with a caption check and a pick pass`
(one commit, or split the service from the pages if the diff is easier to
read that way).

**Review due** at this boundary (multi-file, new flow). Say so in the relay.

## Phase 8: after-download check, needs-a-pick list, playlists

### 8a. After-download check (D6)

- `LibraryTools.on_song_downloaded(song_path)` replaces the `karaoke.py`
  subscription from Phase 3. For a song with no sidecar and no passing
  caption it saves a needs-a-pick entry (`song`, `reason`: `no_caption` /
  `sparse_caption`, `source`: `playlist` when the ID was queued from a
  playlist, else `download`; `added_at`) and emits `needs_pick` (song path).
- Tracker: `_on_needs_pick` sets the item's processing status to
  `needs_pick`. Status derivation keeps `needs_pick` the way it keeps
  `complete` and `error` (active and pending still win). Action `pick`
  (admin) links to `/library/picks`.
- `processing_complete` and `song_deleted` remove that song's entry.
- `attention_rows` adds the entries that have no tracker item (after a
  restart), each with the reason ("no caption" / "caption too sparse") and
  the source ("Playlist" / "Download").

### 8b. Resolving a needs-a-pick song

`GET /library/picks` renders `pick_pass.html` in list mode: the same rows and
inline picker, with no Keep (there's no current pick), no Skip, no batch
button, and each "Use pick" queues at once. Picks are Genius (write the
sidecar `{"genius_id": id}`) or Transcribe (`{"mode": "raw"}`).
`POST /library/needs_pick/pick {song, pick}` writes the sidecar, marks the
entry as picked, and calls `processing_manager.enqueue`. A picked entry shows
"Picked · processing".

### 8c. Playlists

- `LibraryTools.check_playlist(url)`: `classify_url`. A video link gets
  "This is a link to one video. Use the search page to add single videos.",
  or, when it carries `list=`, "This link opens one video in a playlist.
  Paste the playlist page link (youtube.com/playlist?list=…) to add the whole
  list." A playlist link → `read_playlist`, and each video's status from
  `library_files` and `file_status` (`new` / `not processed` / `in library`).
  Expansion failure → "Couldn't read that playlist."
- `LibraryTools.add_playlist(videos: list[{id, title}], unprocessed: list[path])`:
  validates IDs (the 11-character shape), skips IDs already in the library,
  remembers the IDs as playlist downloads, calls
  `download_manager.queue_download(f"https://www.youtube.com/watch?v={id}", enqueue=False, user="Playlist", title=title)`
  for each, and runs each unprocessed song through the same check as a
  download (queue or needs-a-pick).
- Routes: `GET /library/playlist?url=` (the page; it calls the check),
  `POST /library/playlist/check {url}`, `POST /library/playlist/add`.
- `playlist.html` (board `Playlist`): the URL; tags "<playlist title> · N
  videos", "k new", "m not processed", "j in library"; the sections, with a
  checkbox per new video (all checked); the board's three steps; then
  "Download K and process M" (the counts follow the checkboxes; disabled at
  zero) and Cancel. After adding, go to `/processing#jobs`.
- Library tools tab: the Add playlist card from `ProcessingBTools`.

### 8d. Tests and verify

Unit tests: with a sidecar the song queues; a passing caption queues; a
sparse caption is deleted and the song is listed; no caption is listed; a
blocked title queues; a pick writes the sidecar and queues; the entry goes
away on `processing_complete`; entries survive a restart; tracker
`needs_pick` derivation; `check_playlist` statuses and messages;
`add_playlist` skips IDs already in the library and validates IDs.

Live (network; the downloads go into the scratch library):

- the direct-download box with a video that has no manual English caption:
  it lands on the needs-a-pick list; pick Genius; it processes with LRCLIB;
- a small playlist (2-4 videos; ask Ken for one in the relay before this
  step, or use the one from Phase 2C): uncheck one, download the rest, and
  check that captioned songs process and the rest wait for a pick;
- a search-page download through the picker still processes without a
  check.

Commits: `feat(library): downloads without a pick get the caption check and a needs-a-pick list`;
`feat(library): add a YouTube playlist from the Processing page`.

**Review due** at this boundary. Say so in the relay.

## Phase 9: docs, end to end, landing list

- `scripts/README.md`: the shared core's new home; the web UI does the same
  jobs from the Processing page and Song Info; the CLI still needs the app
  stopped (it runs its own GPU workers). Update "Why a separate script, not
  a Flask route?" in a few lines (both exist now, sharing the core).
- Run the full suite and pre-commit, and record the counts.
- Compare the real library against the Phase 0 manifest: every file
  unchanged. **STOP if** anything differs.
- Remove the scratch worktree's `models` junction if you made one; leave the
  scratch library and `APPDATA` folder in place for Ken's checks and say
  where they are.
- Write the landing list into the status block: `library_tools`' code
  commits (from its plan's status block), then this branch's code commits in
  order, excluding the dev merge and every `docs(plan)` commit. Landing is
  Ken's call.
- Commit: `docs(scripts): the web UI shares the regen and add_songs core`.

## Ken's checks (relay the relevant part after each UI phase)

Run the isolated app (the command in "Where things live"), open
`http://localhost:5556` on a phone or a narrow window, and check:

- **Phase 4:** Browse → the info icon on a song → Song Info. Tiles, tabs and
  numbers make sense for Defying Gravity (looks poor, LRCLIB not used) and
  for a caption song. History shows three versions. Regenerate a behind
  song and watch it finish.
- **Phase 5:** Processing → Jobs. While a download and a regen run, the
  order, the Now box, the chips and an expanded failure read clearly. Clear
  finished removes rows and no songs. As a guest (a private window with no
  admin cookie, if an admin password is set): no tabs, no regen rows, plain
  failure text.
- **Phase 6:** Song Info → Repair lyrics, through both steps, once with an
  LRCLIB pick and once with None.
- **Phase 7:** Library tools → Reset all → preview → picks (leave the page
  halfway and come back) → queue → watch the Jobs tab.
- **Phase 8:** a direct download with no caption → Attention → Pick lyrics.
  Add playlist with one box unchecked.

## Landing

Ken's call, after Phase 9 and his checks: cherry-pick the landing list onto
`dev`, in order, then his singing session, as for the other branches (memory
`feedback_master_landing`).

## Results log

### Baseline (Phase 0)

Executed 2026-10-20 by Sonnet 5.5.

- **Worktree:** `web_library_tools` already had one, the design session's
  `...\e06fcfcd-448b-4e95-82bf-396f179bc1c9\scratchpad\wt_weblib` (clean at
  `4eb98c0`); no new one was added. It had no `.venv`: `uv sync` (51 s) built it;
  `libmpv-2.dll` copied from the main checkout's `.venv\Scripts`; `models`
  junction made to the main checkout's `models`.
  `uv run --no-sync python -P -c "import pikaraoke; print(pikaraoke.__file__)"`
  prints `...\wt_weblib\pikaraoke\__init__.py`.
- **Merge:** `git merge --no-ff dev` clean, `c34d889` (4 files: `CLAUDE.md`,
  `alignment_capture.py`, `onset_snap.py`, `test_onset_snap.py`).
- **Baseline** (`uv run --no-sync python -P -m pytest tests/unit -q`, 118.6 s):
  **4 failed, 1564 passed, 2 skipped** (1570 collected). The four failures are
  the known set: `test_genius.py::TestSidecarIO::test_write_overwrites_existing`,
  `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job`,
  `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple`,
  `test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`.
- **Real-library manifest:** 2605 files, 3,104,569,762 bytes, written by a stdlib
  script (`manifest.py write`) to
  `...\66751cff-eade-4c4e-a440-a5ea44850245\scratchpad\real_library_manifest.json`;
  `manifest.py compare` after the scratch copy: 0 added, 0 removed, 0 changed.
  Nothing was listening on 5555 or 5556 and no python process was running.
- **Real-library survey** (48 videos): behind (v10) = `xFYQQPAOz7Y`, `fJ9rUzIMcZQ`,
  `3JWTaaS7LdU`, `DYptgVvkVLQ`, `RPWDeLqsN0g`; no bundle but a karaoke file =
  `qu_FSptjRic`, `8NJVNkzhJM4`; the other 41 are v11.
- **Scratch library** `D:/shared/weblib-test/` (did not exist before), 76 files,
  288 MB. Seven songs:

  | Song | Role | Files copied (video / vocal / nonvocal / dereverb / subtitles / karaoke / lyrics / alignment_debug) |
  |---|---|---|
  | `xFYQQPAOz7Y` Eminem, Lose Yourself | Genius, v10 | 1 / 1 / 1 / 0 / 2 / 1 / 1 / 1 |
  | `fJ9rUzIMcZQ` Queen, Bohemian Rhapsody | caption, v10 | 1 / 1 / 1 / 0 / 2 / 1 / 0 / 1 |
  | `DYptgVvkVLQ` Jay Chou, Sunny Day | Genius, v10, Mandarin, 18 of 42 timed | 1 / 1 / 1 / 1 / 2 / 1 / 1 / 1 |
  | `AoON1CyhQAM` Defying Gravity | Genius, v11, 51 of 89 timed | 1 / 1 / 1 / 0 / 3 / 7 / 2 / 1 |
  | `8NJVNkzhJM4` Eason Chan, Ming Nin Gam Yat | no bundle, karaoke file | 1 / 1 / 1 / 0 / 2 / 1 / 0 / 0 |
  | `1OwfYjemrYw` Backstreet Boys, More Than That | caption, v11 (my pick) | 1 / 1 / 1 / 1 / 1 / 4 / 1 / 1 |
  | Josh Gad, In Summer (from `9tcaM06eGrY`, renamed) | Genius, v11, no YouTube ID | 1 / 1 / 1 / 1 / 2 / 5 / 2 / 1 |

  Folder totals: root videos 7, `vocal` 7, `nonvocal` 7, `dereverb` 3,
  `subtitles` 14, `karaoke` 20, `lyrics` 7, `alignment_debug` 6. History data:
  `Defying Gravity`'s bundle copied from each of the 5 `regen_backup_*` folders
  (1 file each: `20260921T170629Z`, `20260921T181132Z`, `20260921T183151Z`,
  `20261019T175506Z`, `20261019T212308Z`).
  The no-ID copy has `---9tcaM06eGrY` dropped from all 14 of its filenames;
  `extract_youtube_id` returns None for it. Its bundle was not edited.
- **Deviation from the plan's text:** the `_owner` rule (name equals the stem or
  starts with `stem + "."`) claims nothing in `vocal/`, `nonvocal/` and
  `dereverb/`, whose files are named `<stem>---vocal.m4a`,
  `<stem>---nonvocal.m4a`, `<stem>---vocal-dereverb.wav`. Applied literally the
  copy would have left every song without stems and a regen would have re-run
  separation. The copy script claims `stem + "---"` names as well (longest stem
  still wins). The backup/wipe code keeps the plan's rule because it never
  touches those three folders.

### Phase 1

Executed 2026-10-20 by Sonnet 5.5. Code commit `870e34f`.

- **Suite:** 4 failed, 1564 passed, 2 skipped = 1570, the same as the baseline;
  the four failures are the baseline's four (ids unchanged). No tests were added
  or removed; they moved.
- **Test split:** `test_library_regen.py` (scan, plans, `adopt_caption`,
  `fetch_caption`, backup, wipe, ownership, `prepare_lyrics`),
  `test_library_links.py` (`classify_url`, `expand_playlist`, `library_files`);
  `test_regen_alignment_bundles.py` keeps the report, `main()` wiring,
  `resolve_and_run` setup and the `execute_lrclib_backfill` batch tests;
  `test_add_songs.py` keeps expansion failures, dedupe, report, handoff and `main()`.
  The old `TestExecuteFetches` became `TestFetchCaption` (calls `fetch_caption`).
- **Helpers:** `fetch_caption` and `backfill_lrc` follow the plan's table.
  `backfill_lrc` checks `config.lrclib_fill` itself (the plan's signature takes
  `config`; Phase 3 calls it from the web path). The script's
  `execute_lrclib_backfill` keeps its own early `lrclib_fill` return, so its
  "Backfilling..." line is still skipped when the knob is off; the CLI cannot
  turn the knob off, so the two checks only differ for a direct caller.
- **Dry runs on the real library** (`regen_alignment_bundles.py D:/Shared/pikaraoke-songs --dry-run`),
  output files in the executor's scratchpad (`dry_*_{default,reset}.txt`):

  | Script | default | `--reset` |
  |---|---|---|
  | pre-move script at `0381917` (schema 11) | 7 songs | 48 songs |
  | moved script at `870e34f` | 7 songs, byte-identical to the pre-move run | 48 songs, byte-identical |
  | `library_tools` worktree `0bfa02a` (schema 10) | 2 songs | 48 songs, byte-identical |

  The plan's literal comparison (against the `library_tools` worktree) differs in
  default mode only because that branch has no schema 11 (the `dev` merge in
  `c34d889` brought it): it lists the 2 no-bundle songs, this branch also lists
  the 5 v10 songs. The pre-move script on this branch is the like-for-like control.
  `add_songs.py <video-in-library> <new-id> "not a url" --folder <real library> --dry-run`:
  output byte-identical before and after, exit 1 both times (the unreadable URL).
  `--help` prints for both scripts.
- **pre-commit** (`--all-files`): isort, black and pycln reformatted my files only
  (re-staged). The run also edited `pikaraoke/lib/args.py` (an unused `import os`,
  upstream, not mine) and mdformat rewrote both plan files; all three were
  reverted with `git checkout` and are not in the commit. Pylint passed.
- **Import smoke:** `library_regen`, `library_links` and both scripts import.
- The real library manifest was not touched (dry runs only read).

### Phase 2

### Phase 3

### Phase 4

### Phase 5

### Phase 6

### Phase 7

### Phase 8

### Phase 9
