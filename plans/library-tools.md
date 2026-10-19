# Library tools: pick single songs, add songs from YouTube links

Model: Claude Opus 5.5 (design, 2026-09-28); executor Claude Sonnet 5.

> **Status (2026-10-19): Phase 3.1 IN PROGRESS** (Sonnet 5): commit A of G
> done. Don't cherry-pick anything to `dev` until 3.1 is done; then all code
> commits (`6cc2b29`, `2fdcf08`, `c8fe156`, `788b10c`, then 3.1's) go in
> branch order. There is no GATE and nothing here measures timing.

## Why

- Eyeball sessions need one song reprocessed on current code.
  `regen_alignment_bundles.py` skips songs whose bundle is current and has no
  way to name a song, so today this takes a hand-written driver (memory
  `regen-reprocessing-workflow`, "Reprocessing ONE song").
- Ken wants to add songs from YouTube video or playlist links without the app
  UI.

## Decisions (Opus design 2026-09-28, after Ken asked for this plan; the executor doesn't reopen them)

1. **Separate tools by job, no umbrella CLI.** Regen gets `--song`, backfill
   gets the same option, and a new `scripts/add_songs.py` handles links.
2. **`add_songs.py` = download through the app's `DownloadManager`, then hand
   the new songs to regen's code as brand-new songs (no bundle).** The download
   manager is the only place the uploader caption and the YTASR `.en.asr.json3`
   are fetched (Design Decision 3, cited in `lyrics_fetch.py`). Regen's plan
   path already does the rest: caption fetch with the words-per-minute gate,
   then the Genius prompt, the choice sidecar, `LyricsFetchStage` (YTASR,
   LRCLIB) and the de-reverb retry. Backfill has none of that, so the new tool
   does not build on backfill.
3. **Share only the song matching.** `add_songs.py` imports regen's functions
   directly, which keeps one copy of the plan/prompt/run path. No wider shared
   module.
4. **The tools never write the app's library DB.** The app picks new files up
   on its next library sync (startup, or the admin "sync library" action) with
   state `skipped`, which can be queued. Registering them as `pending` would
   block queueing for good, because only `ProcessingManager` sets `ready`
   (`routes/queue.py`, `_do_enqueue`).
5. **No change under `pikaraoke/` is expected.** If one seems needed, STOP and
   report (CLAUDE.md, Fork Maintenance).

## Where things live

- **Branch:** `library_tools`, off `dev` at `6bc19aa`. It carries both this
  plan and the code.
- **Worktree:** Ken's main checkout is `dev` and the app runs from it, so
  **do not switch that checkout**. The branch was checked out on 2026-09-28 at
  `C:/Users/TsangK/AppData/Local/Temp/claude/c--temp-Github-pikaraoke/5f6ce7d2-9c78-4bdc-a25d-5712d9d918b0/scratchpad/wt_libtools`.
  Check `git worktree list`; if that folder is gone, run
  `git worktree prune`, then `git worktree add <your scratchpad>/wt_libtools library_tools`.
  Follow memory `regen-reprocessing-workflow` ("Running from a scratch
  worktree", and traps 2-3: link `models/` with a junction, remove the junction
  before `git worktree remove`). Before trusting any test or script result,
  confirm `pikaraoke` imports from the worktree, not the main checkout.
- **Commits:** keep plan edits (Results log rows, status) and code in
  **separate commits**, never mixed. Because the branch carries `plans/`, it
  is **never merged into `dev`**. Its code commits reach `dev` by cherry-pick,
  the same way `edge_snap_refine`'s do (memory `feedback_master_landing`), and
  a mixed commit would drag the plan onto `dev`.

## Baseline

Before any edit, run the full unit suite in the worktree and record the
pass/fail counts in the Results log (memory `project_windows_dev_box` lists
the known Windows failures). Every phase must end at that baseline plus its
own new tests.

## Phase 1: `--song` on regen

### 1a. Song matching: `scripts/song_select.py` (new)

```python
def select_songs(videos: list[Path], patterns: list[str]) -> list[Path]:
```

- A pattern matches a video when it equals the video's YouTube ID
  (`extract_youtube_id(str(video))` from `pikaraoke.lib.metadata_parser`) or is
  a case-insensitive substring of `video.name`.
- Each pattern must match exactly one video. Zero or several matches raise
  `ValueError`. The message names the pattern and, for several, lists the
  matching file names so the user can retype with the ID.
- The result is deduped and in the input (sorted library) order.

Import it as `from scripts.song_select import select_songs`. Both scripts put
the repo root on `sys.path`. Smoke-test the import with
`python -P scripts/regen_alignment_bundles.py --help` from the worktree.

### 1b. Regen wiring: `scripts/regen_alignment_bundles.py`

Anchors at `6bc19aa` (the quoted signature is the anchor; the line number is
only a locator): `def scan_folder(folder: Path, include_all: bool)` L195,
`def backup_text_folders(folder: Path)` L701,
`def clear_output_folders(folder: Path)` L719, `def parse_args` L782,
`def main` L813.

- **Flag:** `--song PATTERN`, repeatable (`action="append"`). Help text: a
  YouTube ID or part of the file name, each must match one song, and selected
  songs run even if their bundle is current.
- **Selection:** with `--song`, scan only the selected videos and include them
  whatever their bundle state (`stale_reason="selected"`). Unselected songs are
  not touched, even if stale. A bad pattern prints the `ValueError` message to
  stderr and exits 2, before any backup.
- **Plans unchanged:** `resolve_plan(job, reset=args.reset)`. `--song` alone
  reuses the recorded lyric source. `--song --reset` re-resolves only the
  selected songs.
- **Report:** the `Selection:` line reads `selected songs` when `--song` is
  given.
- **Scoped backup:** with `--song`, copy only the selected songs' files from
  each of `BACKUP_DIRS` into the same `regen_backup_<UTC>/<dir>/` layout.
  Without `--song`, behaviour is unchanged.
- **Scoped reset wipe (safety-critical):** with `--song --reset`, delete only
  the selected songs' files in `OUTPUT_DIRS`, keeping the same two exceptions
  `clear_output_folders` keeps (`*.en.asr.json3` in `subtitles/`, `*.lrc` in
  `lyrics/`). Never call the whole-folder wipe when `--song` is set.
- **"A song's files" in a folder:** the name equals the stem or starts with
  `stem + "."` (this catches `<stem>.srt.generated`), and no other library
  video with a longer stem also claims it. That way `Song.mp4` never claims
  `Song.live.srt` when `Song.live.mp4` exists. Use one helper for both the
  backup and the wipe.

### 1c. Tests

New `tests/unit/test_song_select.py`, plus additions to
`tests/unit/test_regen_alignment_bundles.py` in its existing `tmp_path` +
importlib style.

- Select: ID match; case-insensitive substring; no match raises; two matches
  raise and list both; two patterns naming the same song give one entry.
- Scan with selection: a song with a current bundle is included when
  selected; a stale unselected song is excluded.
- Scoped backup: copies the selected song's `.srt`, `.srt.generated`, `.ass`
  and bundle, and nothing of another song's; the longer-stem rule holds.
- Scoped wipe: removes the selected song's regenerable files, keeps its
  `.en.asr.json3` and `.lrc`, and leaves every other song's files untouched.

### 1d. Docs, verify, commit

- `scripts/README.md`, regen section: `--song` usage and the eyeball-session
  one-liner.
- **Dry run on the real library (read-only):** `--song <an ID from the
  library> --dry-run` shows one row with a `reuse ...` plan. The library root
  is in memory `project_dev_environment_map`.
- **Real run on a scratch copy, never the library:** make a scratch library
  folder and copy in one song's files (video, `vocal/`/`nonvocal/` m4a,
  `subtitles/*`, `karaoke/*.ass`, `lyrics/*`, `alignment_debug/*.json` for that
  stem) plus a second song's files. Run `--song <id> --yes`. Check that the
  backup holds only the first song's files, that its `.ass` and bundle were
  rewritten, and that the second song's files are byte-identical.
- One commit: `feat(regen): --song picks songs to reprocess, scoping backup and reset to them`.
- Results log row, then relay to Ken: done, plus the command he runs for an
  eyeball session.

**STOP if:** the dry-run plan for the chosen song is not a `reuse` plan and
you can't tell why, or any unselected file changes in the scratch run.

## Phase 2: `--song` on backfill

- `scripts/backfill_artifacts.py`: `--song`, repeatable, using the same
  `select_songs`. `scan_folder` (`def scan_folder(folder: Path)`, L96)
  considers only the selected videos. A selected song with nothing missing
  prints `<name>: nothing missing (use regen --song to reprocess)` and is not
  queued. Backfill still never reprocesses a finished song.
- Tests: new `tests/unit/test_backfill_artifacts.py` (none exists yet), kept
  small: the selection filter, and a nothing-missing song is not queued.
- `scripts/README.md` backfill section. Dry run on the real library with one
  ID.
- One commit: `feat(backfill): --song limits the scan to named songs`.

## Phase 3: `scripts/add_songs.py`

### 3a. Check first (STOP gate)

`DownloadManager._execute_download` calls flask_babel's `_`, and this tool has
no Flask app. The existing tests patch `_`, so they don't prove it works
without an app. Outside any app, run
`from flask_babel import _; print(_("Downloaded: %s") % "x")`. It must print
plainly. If it raises, STOP and report. Do not add an app context and do not
change `download_manager.py`.

### 3b. Split out regen's run tail (pure refactor, its own commit)

Move `main()`'s tail, from `execute_fetches(jobs)` (L871) through the
`Done.` print, into `def resolve_and_run(jobs, config, genius) -> int`, which
returns the exit code; `main()` calls it. Move the no-Genius-token warning
into a helper both tools call rather than copying it. Existing tests must pass
unchanged. Commit:
`refactor(regen): split caption fetch, prompts and run into resolve_and_run`.

### 3c. The tool

Usage: `python scripts/add_songs.py URL [URL ...] [--folder PATH] [--dry-run] [--yes]`.
The folder defaults to `get_default_dl_dir(get_platform())`, as in regen.

1. **Classify each URL.** Strip `&list=...` the way
   `DownloadManager.queue_download` does. If `get_youtube_id_from_url` then
   gives an 11-character ID, it's a video, so `watch?v=X&list=Y` and
   `youtu.be/X?si=...` are videos, matching the app. Otherwise, if it contains
   `list=`, it's a playlist. Otherwise report it as unrecognised and skip it.
   The help text says `watch?v=X&list=Y` downloads only X, and to paste the
   playlist page link to get the whole list.
2. **Expand playlists** with
   `yt_dlp_cmd + ["--flat-playlist", "--print", "id"] + _impersonate_args() + [url]`,
   imported from `pikaraoke.lib.youtube_dl` and modelled on
   `get_search_results`. On `CalledProcessError`, report that URL and continue.
3. **Dedupe** the IDs. Skip any ID already in the folder (a video file whose
   `extract_youtube_id` equals it) as `already in library`.
4. **Report** a table (ID, source URL, new/already). `--dry-run` stops here.
   Confirm unless `--yes`.
5. **Download** serially through a `DownloadManager` built with:
   - a real `EventSystem`
   - a real `PreferenceManager`, so the app's `high_quality` setting applies
   - `SongManager(folder, db=KaraokeDatabase(":memory:"))`. Only
     `songs.find_by_id` is used, and the in-memory DB keeps the app DB
     untouched (Decision 4).
   - `queue_manager=None`, with a comment that it's used only when
     `enqueue=True`
   - `temp_dir=get_temp_directory()`

   Register `events.on("song_downloaded", new_songs.append)`, then call
   `dm._execute_download(watch_url, False, "add_songs", None)` for each ID.
   It's synchronous, so the queue thread isn't needed. A non-zero return code
   counts as a download failure; continue with the next ID. A success runs the
   app's own caption move and YTASR fetch.
6. **Hand off to regen:** `from scripts import regen_alignment_bundles as rab`.
   For each new song, build `rab.SongJob(path, None, "new")` and set
   `job.plan = rab.resolve_plan(job, reset=False)`, which gives a `fetch` plan
   since every download has an ID. Then call
   `rab.resolve_and_run(jobs, config, genius)`. No backup is needed, because
   new songs have no outputs. Set up config, logging and
   `PYTORCH_CUDA_ALLOC_CONF` as regen's `main()` does (`PipelineConfig()`,
   `intermediate_dir = get_temp_directory()`).
7. **End** by printing downloaded/failed/processed counts and: "In the app,
   run sync library from the admin page (or restart it) to see the new songs."

The flow is: downloads run unattended, then all Genius prompts come in one
batch, then the pipeline runs unattended. Say this in the help text so Ken
knows when to be at the keyboard.

**Accepted cost (SUPERSEDED by Phase 3.1, fix A):** `execute_fetches` asks yt-dlp for the manual caption again
right after the download fetched it. That's one small call per song, and it
applies the words-per-minute gate the live app lacks. Don't optimise it away.

**Out of scope:** the `blocked_processing_words` preference; the app's yt-dlp
proxy and extra-args settings (app command-line flags, not preferences); and
running alongside a busy app pipeline. Running two GPU jobs at once is 3-11x
slower (memory `concurrent-gpu-inference-rejected`), so the help text says to
run the tool while the app is idle. Don't enforce it.

### 3d. Tests: `tests/unit/test_add_songs.py` (subprocess mocked)

- Classify: `watch?v=X` gives video X; `watch?v=X&list=Y` gives video X;
  `youtu.be/X?si=Z` gives video X; `playlist?list=Y` gives a playlist; garbage
  is unrecognised.
- Expand: mocked yt-dlp output of three IDs plus a blank line gives three
  IDs; `CalledProcessError` is reported and the other URLs continue.
- Dedupe: an ID already in the folder is skipped; an ID repeated across URLs
  appears once.
- Handoff: a captured song path becomes a job with `bundle=None` and a
  `fetch` plan (`resolve_and_run` patched).

### 3e. Verify and commit

- **Real run into a scratch folder, never the library:** one short video URL,
  then a small public playlist of 2-3 entries (ask Ken for one if you don't
  have one). At the Genius prompt, pick normally. Check that the video,
  `subtitles/`, the `.en.asr.json3` (if YouTube has auto-captions for it),
  stems, `.ass` and bundle are all present, and that the app DB file's
  modification time is unchanged.
- `scripts/README.md` section for the new tool.
- One commit:
  `feat(scripts): add_songs downloads YouTube videos and playlists and runs the pipeline`.
- Results log row. Flag that a `/code-review` is due (a multi-file new tool),
  and flag a `/compact` point.

**STOP if:** 3a fails, a download succeeds but `song_downloaded` never fires,
or anything outside the scratch folder changes during the real run.

## Phase 3.1: fixes from the code review

Source: Opus 5.5 ran `/code-review` on 2026-09-28 at `a3fd9c4` with three
finders (correctness, simplicity, robustness). Opus checked every finding
against the code, and ran the link cases through `classify_url`. The fix
designs below are Opus decisions, and the executor doesn't reopen them.
Decisions 1-5 still hold.

Anchors are at `a3fd9c4`. The quoted code is the anchor; a line number only
helps you find it.

Make commits A-G in order. Each one carries its own tests, ends at the baseline
plus its new tests, and passes `pre-commit`. The fixes (A-F) come before the
cleanup (G), so the fixes still land if G is cut.

### A. Check the caption the download already saved

This is a gap in the Phase 3 design, not an execution error.

**The problem:**
- The download saves the uploader caption (`build_ytdl_download_command`:
  `--write-subs --sub-langs en.* --convert-subs srt`).
- `DownloadManager._move_downloaded_subtitle` then moves it to
  `subtitles/<stem>.srt` and clears its generated marker.
- `execute_fetches` downloads the same caption again to `<stem>.en.srt`.
  `download_manual_en_subs` uses the download's subtitle options, so it gets
  the same file.
- When the words-per-minute gate rejects the caption, it deletes only that
  second copy (`srt_path.unlink(missing_ok=True)`).

The rejected caption therefore stays on disk as a real `<stem>.srt`, and three
things follow:
- If the Genius fetch fails at run time, `LyricsFetchStage` falls through to its
  SRT branch and aligns the dialog caption as the lyrics.
- `[s]` at the prompt adopts it.
- The pipeline never writes its own SRT, because `_should_write_srt` sees a
  real caption.

The 3 songs already promoted into the library are unaffected: one passed the
gate, and the other two had no caption.

**The fix:**

1. **In regen, split the gate out of `execute_fetches`**
   (`def execute_fetches(jobs: list[SongJob]) -> None:`, L475) into a new
   function:

   ```python
   def adopt_caption(job: SongJob, srt_path: Path) -> None:
   ```

   - It takes the `fallback` computation and everything from
     `wpm = _caption_wpm(srt_path, job)` to the end of the loop body.
   - On reject, it unlinks `srt_path` and sets `job.plan = fallback`.
   - On accept, it promotes the caption to `<stem>.srt`, clears the marker and
     sets the seed plan. Skip the `os.replace` when `srt_path` already is
     `<stem>.srt`.
   - `execute_fetches` keeps the download and the `result is None` branch, and
     calls `adopt_caption(job, Path(result))`.
   - The behaviour of `execute_fetches` does not change, so its existing tests
     must pass unchanged.
2. **In add_songs' `handoff`:** after `resolve_plan`, call
   `rab.adopt_caption(job, caption)` for each job where
   `rab._find_local_srt(job.song_path)` returns a caption.
   - A job with no caption on disk keeps its `fetch` plan, so regen asks
     YouTube once more. That covers a caption request that failed during the
     download.
   - `_find_local_srt` already skips a generated SRT. That matters for fix D's
     resumed songs.
3. **Tests**, in the existing `TestExecuteFetches` style (real SRT fixtures
   with a known word count):
   - `adopt_caption` with a sparse caption deletes it and sets the fallback.
   - `adopt_caption` with a dense caption already at `<stem>.srt` keeps it and
     sets a seed plan.
   - `handoff` with a caption on disk leaves no `fetch` plan.
   - `handoff` with no caption on disk keeps the `fetch` plan.
4. **README:** the downloaded caption goes through the same words-per-minute
   gate, and there's no second caption fetch for a song that has one.

Commit: `fix(add_songs): gate the caption the download saved instead of fetching it again`.

### B. Read links with the URL parser

**The problem** (reproduced): `classify_url` (L68) relies on
`get_youtube_id_from_url`, which cuts the ID at `?` but not at `&`.
- **Rejected as unrecognised, although the app accepts them:**
  - `watch?v=X&pp=…` (search results)
  - `music.youtube.com/watch?v=X&si=…`
  - `watch?v=X&t=30s`
  - `watch?feature=shared&v=X`
- **Read as the whole playlist:**
  - `watch?v=X&t=30s&list=Y`
  - `watch?v=X&pp=…&list=RDX&start_radio=1` (a search click that opened a
    Mix)

  With `--yes`, either link downloads and processes the whole list, although
  the help text promises only X.

**The fix:** rewrite `classify_url` on `urllib.parse`. It checks these in
order:
1. **Host:** `urlparse(url).hostname`, lowercased, must be `youtu.be` or end
   with `youtube.com`. Otherwise the link is unrecognised.
2. **Video:** for `youtu.be`, take the first path segment as the ID; for any
   other host, take the `v` query parameter (`parse_qs`). If the ID matches
   `[A-Za-z0-9_-]{11}`, it's a video, even when the link also carries `list=`.
3. **Playlist:** otherwise, a `list` query parameter makes it a playlist. Pass
   the URL through unchanged.
4. Otherwise the link is unrecognised.

The new version no longer calls `get_youtube_id_from_url`, so remove the
`"v=" in stripped or "u.be/" in stripped` guard and the `&list=` stripping.
Shorts and embed links stay unrecognised; nobody asked for them.

**Tests:** keep the 5 existing classify cases, and add:
- each link above, with its expected result
- `watch?list=Y&v=X` gives video X
- `m.youtube.com/watch?v=X` gives video X
- a non-YouTube host with `?v=<11 chars>` is unrecognised

**Help text and README:** "A link to one video downloads only that video, even
when it carries `list=`. Paste the playlist page link (`playlist?list=`) to get
the whole list."

Commit: `fix(add_songs): read video and playlist links with the URL parser`.

### C. Failures reach the summary and the exit code

**The problems:**
- **Pipeline result dropped:** `handoff` discards `rab.resolve_and_run`'s
  return code (it calls `rab.resolve_and_run(jobs, config, genius)` and then
  `return jobs`). `main` then prints `Processed: len(jobs)` and exits 0, even
  when every song failed or was skipped at the prompt.
- **Missing file counted as downloaded:** a download that returns 0 without
  firing `song_downloaded` (because `find_by_id` found no file) is counted as
  downloaded. It is never processed and never named.
- **Unreadable links look like "nothing to do":** a playlist that fails to
  expand, or an unrecognised URL, ends in "Nothing new to download." with
  exit 0.
- **No timeout:** `expand_playlist` calls `subprocess.check_output(cmd)` with
  no timeout.

**The fix:**
- **`handoff`:** return the code from `rab.resolve_and_run(...)`. Drop
  `Processed:` from the summary; regen's
  `Done. succeeded=… failed=… skipped=…` line already reports the pipeline.
- **Download loop:** count a download as successful only if `song_downloaded`
  fired during that call (compare `len(new_songs)` before and after). If the
  return code is 0 but no event fired, print
  `FAILED: <id> (yt-dlp finished but no file with that id is in the folder)`
  and count it as failed.
- **`resolve_urls`:** also return how many URLs couldn't be read, whether
  unrecognised or failed to expand.
- **`expand_playlist`:** pass `timeout=300`. Catch `subprocess.TimeoutExpired`
  alongside `CalledProcessError` and report it the same way.
- **Exit code:** 1 if any URL couldn't be read, any download failed, or the
  pipeline returned non-zero; otherwise 0.
  - This holds under `--dry-run` too.
  - It also holds on the "Nothing new to download" path, whose message then
    says how many URLs couldn't be read.

**Tests.** Drive `main()` by monkeypatching `sys.argv`, and use a fake
`DownloadManager` that emits `song_downloaded` through the real `EventSystem`
it's given. Patch `handoff` as each test needs, and make sure nothing touches
the real config or library. Cover:
- a pipeline failure (`handoff` returns 1) gives exit 1
- return code 0 with no event is counted as failed and gives exit 1
- one unreadable URL with nothing to download gives exit 1
- a `TimeoutExpired` from expansion is reported, and the other URLs continue

Commit: `fix(add_songs): report pipeline, download and link failures in the exit code`.

### D. An interrupted run can be resumed

**The problem:**
- The download loop has no guard around each download. The app's
  `_process_queue` wraps `_execute_download` in `try/except Exception` and
  logs the error.
- So an exception, Ctrl+C, or EOF at a Genius prompt kills the run, and the
  videos it already downloaded never reach the pipeline.
- A rerun then lists those videos as `already in library` and says "Nothing
  new to download."

**The fix:**
- **Guard each download** the way the app does. Wrap each `_execute_download`
  call in `except Exception:`, then call
  `logger.exception("Download failed: %s", entry.id)`, print `FAILED: <id>`,
  count it as failed and continue. This is the app's own boundary, and Ctrl+C
  still stops the tool.
- **Map IDs to files:** replace `existing_ids` with a dict from ID to file.
  Build it from every song file the app recognises
  (`SongList.VALID_EXTENSIONS` from `pikaraoke.lib.song_list`), so an `.mp3`
  or `.zip` with that ID also counts as `already in library`.
- **Add a third status, `in library, not processed`:** a video file (one in
  `rab._list_videos`, since regen only processes videos) with no bundle
  (`rab._read_bundle(folder, stem) is None`). Such a song:
  - isn't downloaded again
  - joins the handoff after the new downloads
  - counts in the confirm prompt: "Proceed with N download(s) and M
    unprocessed song(s)?"
- Keep the "Nothing new to download" early exit only for runs with nothing to
  download and nothing unprocessed. Size the report's status column from the
  longest status.

**Tests:**
- A folder video with no bundle gets `in library, not processed`, and its path
  is handed off without a download.
- A folder video with a bundle gets `already in library` and is not handed off.
- An `.mp3` with the ID gets `already in library`.
- An exception from one download is counted as failed, and the next download
  still runs.

Commit: `fix(add_songs): survive a failed download and resume songs a stopped run left unprocessed`.

### E. `--song`: an exact match wins

**The problems:**
- **No priority for exact matches.** `Hello.mp4` can't be selected when
  `Adele - Hello.mp4` is also in the library, because `--song Hello` is
  ambiguous.
- **Dead ID branch.** The exact-ID check in `_matches` never matters: the ID
  is always part of the file name, so the substring check already matches it.
- **Dead `sys.path.insert` in `song_select.py`.** The module has no
  `__main__`, and it can only be imported once the repo root is already on the
  path.

**The fix, in `select_songs`:** for each pattern, first collect exact matches.
A match is exact when the pattern equals the video's YouTube ID, or equals its
stem or file name case-insensitively.
- If there are any exact matches, use them. Otherwise fall back to the
  case-insensitive substring match.
- The rule that each pattern must match exactly one song is unchanged.
- Delete the `sys.path.insert`, its comment and the `sys` import.
- Change the help text in both scripts to: "a YouTube ID, the file name, or
  part of it; an exact match wins".

**Tests:**
- `Hello` and `hello` both select `Hello.mp4` when `Adele - Hello.mp4` is also
  in the library.
- An exact ID wins over a file whose title contains that string.
- Rename `test_result_is_deduped_and_in_input_order` (L41) to
  `test_result_is_in_input_order`, because it has no repeated pattern.

Commit: `fix(song_select): an exact ID or file name wins over a partial match`.

### F. Regen: `--song --reset` shows reset, ownership counts every song file, and the wiring is tested

**The problems:**
- **Reset is hidden in the report.** With `--song --reset`, `print_report`
  (L384) prints the `Selection:` line as `selected songs`. It hides that reset
  is on, right before the confirm prompt for a wipe.
- **The text still describes whole folders.** These all describe whole-folder
  behaviour:
  - the module docstring: the usage line, and "Before overwriting outputs,
    the … folders are copied"
  - the `--reset` help: "wipe subtitles/karaoke/lyrics after the backup"
  - `main`'s "Cleared subtitles/karaoke/lyrics (reset)" message

  Backfill's docstring usage line also lacks `--song`.
- **Ownership only sees videos.** `_all_stems` (L717) builds the set of song
  names from video files only (`_list_videos`), but the app also treats
  `.mp3` and `.zip` files as songs. Fixture: `Mr.mp4` plus
  `Mr. Brightside---<id>.mp3`. Running `--song Mr --reset` wiped the mp3
  song's `.srt`, `.srt.generated`, `.en.srt`, `.ass` and lyrics.
- **The wiring is untested.** No test covers `main()` passing the selected
  songs to the backup and the wipe. The safety rule is tested only on the
  helpers.

**The fix:**
- Print `Selection: selected songs (reset)` when both flags are given.
- Add `[--song PATTERN ...]` to the docstring usage line, with one sentence:
  with `--song`, the backup and the reset touch only the selected songs'
  files. Add the same clause to the `--reset` help.
- When scoped, the "Cleared" and "Backed up" messages say "for the selected
  songs".
- Add `[--song PATTERN ...]` to backfill's usage line.
- `_all_stems` uses every song file the app recognises
  (`SongList.VALID_EXTENSIONS`). Selection still lists videos only.
- **Test:** run regen `main()` with `sys.argv` set to
  `[<tmp library>, "--song", <id>, "--reset", "--yes"]`. Patch
  `resolve_and_run`, plus whatever `main` builds before calling it.
  - Assert that only the selected song's files were backed up and wiped.
  - Include a longer-stem sibling and an `.mp3` sibling, and assert both are
    untouched.

Commit: `fix(regen): --song --reset says so, and file ownership counts every song file`.

**Known limit, no code change.** `_select_en_srt`
(`pikaraoke/lib/youtube_dl.py` L301, called by `download_manual_en_subs`)
treats every `<stem>.*.srt` as an English variant and deletes the extras. That
includes a longer-stem sibling's caption, such as `Song.live.srt` when the
selected song is `Song`.
- With `--song`, the backup is scoped and no longer covers that sibling.
- It needs one song's name to be another's name plus a dot. The library has no
  such pair (checked 2026-09-28).
- The fix would be under `pikaraoke/` (Decision 5), so it stays out. Note it in
  the Results log.

### G. Cleanup (simplicity), one commit

- **Reset keep rules in one place.**
  - Add a table: `KEEP_ON_RESET = {"subtitles": ASR_JSON3_SUFFIX, "lyrics": ".lrc"}`.
  - Merge `_clear_except_suffix` (L818) and `_clear_selected` (L831) into one
    helper that takes the suffix to keep and an optional ownership filter.
  - The unscoped reset still removes the whole `karaoke/` folder; an existing
    test asserts that.
  - The merged helper logs a failed delete as a warning instead of passing
    `ignore_errors=True`.
- **Ownership as "the longest stem that claims a file owns it."**
  - Replace `_owns_file` with `_owner(name, all_stems) -> str | None`. It
    returns the longest stem `s` for which `name == s` or
    `name.startswith(s + ".")`.
  - Both call sites become `_owner(e.name, all_stems) in stems`.
  - This is equivalent to the current rule: two claiming stems of the same
    length must be the same string.
- **Process setup in one place.**
  - Move the `PYTORCH_CUDA_ALLOC_CONF` default and the logging setup out of
    regen's `main()` into `def setup_process() -> None:` in regen. Both
    `main()`s call it.
  - `resolve_and_run(jobs)` builds the `PipelineConfig` (with
    `intermediate_dir`), calls `_make_genius()` and prints the no-token warning
    itself. `warn_if_no_genius_token` goes back inline.
  - add_songs drops those lines and its `GeniusClient` and `PipelineConfig`
    imports.
  - The no-token warning then prints after the backup message instead of
    before it, which is fine. Adjust F's `main()` test so it patches only
    `resolve_and_run`.
- **README, `add_songs` section.**
  - Drop step 1's parenthetical ("`song_select.py`'s sibling, … in this
    file"). It is wrong.
  - Two passages repeat `--help`: the "Downloads run unattended…" paragraph and
    "Run it while the app is idle". Replace them with one line pointing at
    `--help`.
  - Step 4 keeps the reasons (same download path as the app; never writes the
    app DB) and drops the internals (`KaraokeDatabase(":memory:")`,
    `find_by_id`, the `SongJob` details).
- **Tests:** the two near-identical `_setup` library fixtures in
  `test_regen_alignment_bundles.py` (`TestBackupTextFoldersScoped` L355,
  `TestClearOutputFoldersScoped` L458) become one module-level helper.

Commit: `refactor(scripts): one home for reset keep rules, file ownership and process setup`.

### Verify, then relay

- **Unit suite:** the full suite ends at the baseline plus the new tests.
- **Link check** (real CLI, into an empty scratch folder, read-only): run
  `add_songs.py <link> --folder <scratch> --dry-run` for each link shape in B.
  The Mix-style link must report exactly one entry.
- **Real run** into a scratch folder, never the library:
  - One video that has a manual caption. `Z3x9i7njCCo` from Run B had one.
  - The log must show no "Fetching video captions" line.
  - The song's plan must be its downloaded caption.
  - The artifacts must match Run B's.
  - Then delete that song's bundle and rerun the same command with
    `--dry-run`. It must report `in library, not processed`.
- **Safety check:** the app DB and `config.ini` hashes are unchanged, as in 3e.
- **Record and relay:** write a Results log row per commit, then relay to Ken.
  - Flag that a `/code-review` of the 3.1 commits is due. Don't run it.
  - Flag a `/compact` point.
  - Tell Ken the interactive prompts inside `main()` (confirm and Genius) have
    still not run live, so his first real use is that check.

**STOP if:**
- `execute_fetches`' existing tests change outcome after the split in A
- any fix seems to need a change under `pikaraoke/` (Decision 5)
- anything outside the scratch folder changes during the real run

**Landing** is Ken's call: cherry-pick every code commit to `dev` in branch
order. Once `--song` is on `dev`, it replaces the one-song driver recipe in
memory `regen-reprocessing-workflow`, and the session that lands it updates
that memory.

## Results log

### Baseline

2026-09-28, worktree `wt_libtools` at `66e7b6d` (`library_tools`, off `dev`
`6bc19aa`). Fresh `uv sync` (first sync in this worktree; one transient
`uv-trampoline` access-denied retry, unrelated to the repo) plus a manual copy
of `.venv/Scripts/libmpv-2.dll` from the main checkout (hand-placed, not a
dependency — memory `project_dev_environment_map`). Confirmed `pikaraoke`
imports from the worktree, not the main checkout.

`uv run --no-sync python -m pytest tests/unit -q`: **4 failed, 1487 passed, 2
skipped**. The 4 failures are exactly the known Windows set (memory
`project_windows_dev_box`): `test_genius.py::TestSidecarIO::test_write_overwrites_existing`,
`test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job`,
`test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple`,
`test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`.
No new failures. Baseline for every phase below: 4 known-failed + new tests
passed.

### Phase 1

Code `6cc2b29` (docs-only prep `263ab88` before it). Built `scripts/song_select.py`
(`select_songs`) and wired `--song` into `regen_alignment_bundles.py`: scoped
scan (`stale_reason="selected"`), scoped `backup_text_folders`/
`clear_output_folders` via a shared `_owns_file` ownership rule (longer
sibling stem, e.g. `Song.live`, wins its own files over `Song`), and the
`Selection:` report line. Anchors at `6bc19aa` all lined up exactly with no
drift.

Tests: `tests/unit/test_song_select.py` (6, new) +
`tests/unit/test_regen_alignment_bundles.py` (+4: selection scan,
scoped-backup x2, scoped-wipe). Full suite:
**4 known-failed, 1497 passed, 2 skipped** (1487 + 10 new, no regressions).
`pre-commit` clean (black reformatted once, cosmetic only — reviewed the
diff, reran the targeted tests).

Verify: dry run on the real library (`D:/shared/pikaraoke-songs`) with
`--song hLQl3WQQoQ0 --dry-run` showed exactly one row, plan `reuse srt (from
video)`. Real run on a scratch copy (Adele "Someone Like You" selected +
"Free" by Sony Animation as the untouched control, full per-song artifact
sets copied from the real library) with `--song hLQl3WQQoQ0 --yes`: hit the
known `models/` worktree trap on the first attempt (whisper worker died,
before any job ran — confirmed via hash diff that nothing real changed) and
was recovered by the documented `models/` junction. On the successful rerun:
backup held exactly Adele's 4 files (nothing of Free's); Adele's `.ass` and
`alignment_debug/*.json` hashes changed (rewritten); every other file,
including all of Free's, hashed identical before/after. No STOP triggered.

`scripts/README.md` gained a `regen_alignment_bundles.py` section (it had
none before this) with `--song` usage and the eyeball one-liner.

**For Ken — eyeball-session one-liner** (replaces the old scratch driver):

```bash
python scripts/regen_alignment_bundles.py --song <YouTube-ID-or-part-of-name> --yes
```

### Phase 2

Code `2fdcf08`. Same `select_songs`, wired the same way as Phase 1 (bad
pattern -> stderr + exit 2), but `scan_folder`'s selection path stays
inside the existing missing-artifact gate instead of overriding it: a
selected song with nothing missing is reported
(`<name>: nothing missing (use regen --song to reprocess)`) and left out of
`jobs`, never force-queued. `_list_videos` is duplicated from regen rather
than shared, per Decision 3 (no wider shared module beyond `select_songs`).
Anchor `def scan_folder(folder: Path)` at `6bc19aa` L96 matched exactly.

Tests: `tests/unit/test_backfill_artifacts.py` (new, first ever for this
script) — 2, kept small per the plan: selection scoping, nothing-missing
not queued. Full suite: **4 known-failed, 1499 passed, 2 skipped** (1497 +
2 new, no regressions). `pre-commit` clean on the first pass.

Verify: dry run on the real library, `--song hLQl3WQQoQ0 --dry-run` ->
correctly reported "nothing missing" (that song is already fully
backfilled) and queued 0 songs; a full unscoped `--dry-run` confirmed the
whole library currently has nothing missing, so the "queued row" path
couldn't be shown against real data — it's covered by the tmp_path tests
instead. Read-only throughout, no STOP condition (Phase 2 has none).

`scripts/README.md` backfill section gained the `--song` usage line and
its "not force queued" distinction from regen's `--song`.

### Phase 3

Commits: 3b refactor `c8fe156`; tool, tests and README `788b10c`.

**3a (STOP gate).** `from flask_babel import _; print(_("Downloaded: %s") % "x")`
outside any app printed `Downloaded: x`. No STOP.

**3b.** `resolve_and_run(jobs, config, genius) -> int` and
`warn_if_no_genius_token(genius)` split out of regen's `main()`; the 39 existing
regen tests passed unchanged.

**3c/3d.** `scripts/add_songs.py` (mode 100755, like its sibling CLIs) and
`tests/unit/test_add_songs.py` (10 tests: classify 5, expand 1, expansion
failure 1, dedupe 2, handoff 1). Full suite: **4 known-failed, 1509 passed, 2
skipped** (1499 + 10). `pre-commit` clean.

Implementation notes:

- `classify_url` calls `get_youtube_id_from_url` only for URLs containing `v=`
  or `u.be/`. That helper logs `ERROR ... Error parsing youtube id from url` for
  any URL it can't parse, and Stage 1 printed that line first for a playlist
  link. The caption assertion in `test_bare_playlist_url` fails with the guard
  disabled (checked) and passes with it.
- `main()` reuses regen's underscore-named `_list_videos` and `_make_genius`
  (Decision 3, direct import).
- Limit: a link with an extra parameter between `v=` and `list=`
  (`watch?v=X&t=30s&list=Y`) is read as a playlist. `watch?v=X&list=Y&t=30s` is a
  video, and `watch?v=X&t=30s` with no list is reported unrecognised (the app's
  own helper cannot parse it either).

**3e real runs (scratch folders only).** Playlist `PLWPORwgk3oWc`, 4 entries
(from Ken).

Run A, in two stages. The drivers (`verify_stage1.py`, `verify_stage2.py`, in the
session scratchpad, not committed) reproduce `main()`'s download block and stop
before the interactive prompt; `classify_url`, `resolve_urls`, `print_report`,
the real `DownloadManager`, `execute_fetches` and `run_jobs` were the real code.

- Stage 1: `Songs found: 4`. Downloads: 3 succeeded, 1 failed (`Z3x9i7njCCo`,
  yt-dlp `HTTP Error 403: Forbidden`). `song_downloaded` fired 3 times for 3
  successes, so no STOP. Captions: `6q0JnftlH-I` fetched a manual caption and got
  a seed-srt plan; `1QYBiNRu1ok` and `6oQZFjJDI7s` had none, so both went to
  the Genius prompt. The ASR fetch for `6q0JnftlH-I` returned `HTTP Error 429` and
  left a stray partial `subtitles/<stem>.en.json3` (26,649 B); upstream
  `download_auto_en_subs` does not clean up when yt-dlp exits non-zero. Not
  touched, not copied to the library.
- Genius prompt: the Bash tool cannot type into a live prompt, so the driver
  injected the `Plan(kind="sidecar", genius_id=...)` that `_prompt_one` returns
  for a numbered pick. The default query for `1QYBiNRu1ok` was `'Seven ' Performance`:
  `clean_search_query` strips parenthesised text, and `EMOJI_PATTERN`
  (`\U000024C2-\U0001F251` in `metadata_parser.py`) also removes all Hangul and
  Japanese text (checked: `EMOJI_PATTERN.sub("", "정국") == ""`). The 6 hits
  were wrong. Variants (`Jung Kook Seven`, `Jungkook Seven`, `jung kook seven`,
  `Seven Jungkook Latto`) returned 0 hits after filtering: the raw API gave 20
  hits, all `Genius ... Translations` pages, which `search()` drops by design.
  Ken supplied `genius.com/Jung-kook-and-latto-seven-clean-ver-lyrics`; it
  resolved to id 9283569 by matching `result["url"]` in the raw hits for a query
  containing "Clean Ver" (a direct page fetch returns 403). For `6oQZFjJDI7s`
  Ken picked hit 1, id 1259925.
- Stage 2 (`run_jobs`): `succeeded=3 failed=0 skipped=0`, 1433 s. LRCLIB
  returned 503 for `6oQZFjJDI7s`.

| id | video | .srt | .srt.generated | .en.asr.json3 | vocal + nonvocal | .ass | bundle | .lrc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1QYBiNRu1ok` Seven | yes | yes | yes | yes | yes | yes | yes | yes |
| `6q0JnftlH-I` Standing Next to You | yes | yes (uploader caption) | no | no (429) | yes | yes | yes | no |
| `6oQZFjJDI7s` The Next Ten Minutes | yes | yes | yes | no (no error logged) | yes | yes | yes | no (503) |
| `Z3x9i7njCCo` 3D | download failed | | | | | | | |

Run B, the file's own `main()`: `add_songs.py "https://www.youtube.com/watch?v=Z3x9i7njCCo"
--folder <fresh scratch> --yes`, stdin `\nt\n` in case a prompt appeared. The
403 did not recur. A manual caption was fetched, so no prompt fired.
`Downloaded: 1 Failed: 0 Processed: 1`, exit 0, sync-library reminder printed.
Artifacts: video, `.srt` (uploader caption), `.en.asr.json3`, both stems, `.ass`,
bundle. Run B is the only run that executed `main()`'s download-to-handoff
branch itself. The interactive Genius prompt inside `main()` and the
confirmation prompt were not exercised live in any run.

Safety checks after Run A and again after Run B: real app DB
`%APPDATA%\pikaraoke\pikaraoke.db` sha256 `5c9dec18...bedab` and mtime
`1779911392` identical to before; real `config.ini` sha256 `e264ca26...0cb8`
identical; no file in the real library carried any of the four ids. Files
modified in the real library during the runs (`karaoke/*.p6base.ass`,
`*.p6ends.ass`) are Ken's concurrent work (Ken's statement), not produced by this
branch. `lyric_choices/` sidecars in the shared temp dir come from regen's
existing sidecar path.

**Promotion into the library (Ken's request after Run A).** 3 songs
(`1QYBiNRu1ok`, `6q0JnftlH-I`, `6oQZFjJDI7s`), 22 files (7 + 9 + 6), additive
(every destination checked absent first), companions first and the video last,
sha256 of every copy equal to its source (0 mismatches). The stray `.en.json3`
was not copied. Run B's song (`Z3x9i7njCCo`) was not promoted. Afterwards
`add_songs.py <playlist> --folder D:/shared/pikaraoke-songs --dry-run` (real
CLI, read-only) reported 3 x `already in library` and 1 x `new`
(`Z3x9i7njCCo`). The app DB was not written, so the songs appear at the next
library sync.

**Left in place.** Worktree `wt_libtools` with its `models/` junction (remove the
junction with `cmd //c rmdir` before any `git worktree remove`); scratch folders
`add_songs_verify` and `add_songs_verify2` in the session scratchpad.

**Flags.** A `/code-review` is due (multi-file new tool plus the regen refactor);
not run, per CLAUDE.md. This is a `/compact` point (code committed, plan-log
row written).

### Code review

2026-09-28, Opus 5.5, `/code-review` at `a3fd9c4`: three finders (correctness,
simplicity, robustness), every finding checked by Opus. Read-only; nothing on
the branch changed. The findings and their fixes are Phase 3.1 above. A
read-only library check the same day found no `.mp3`/`.zip` songs and no pair
of stems where one is the other plus a dot, so F's ownership fix and its known
limit are latent in this library.

### Phase 3.1

**Worktree recovery (2026-10-19, before any commit).** The `wt_libtools`
worktree named in "Where things live" had its tracked files and its `.venv`
site-packages gutted between sessions (directories and `__pycache__` survived,
every regular file under them didn't; same pattern in both the git working
tree and `.venv/Lib/site-packages`) — consistent with an external temp-cleanup
sweep over the scratchpad path, not anything this session or the Sep 28 one
did. `git reset --hard HEAD` restored the tracked files (branch tip
unchanged, nothing uncommitted to lose); the `models` junction had to be
recreated (`cmd /c mklink /J`, per "Where things live"); `.venv` was deleted
and rebuilt with `uv sync` (first sync since recovery) plus the usual
hand-copied `libmpv-2.dll`. Confirmed `pikaraoke` imports from the worktree,
not the main checkout, before trusting anything. Full suite after recovery,
before any 3.1 edit: **4 known-failed, 1509 passed, 2 skipped** — matches
Phase 3's end state exactly, so the recovery is a full match, not a near-miss.

**Commit A** (`c096631`): `adopt_caption(job, srt_path)` split out of
`execute_fetches` in regen (gate + promotion only; `execute_fetches`'s own
behavior and its existing tests are unchanged, verified by running them
unmodified). `add_songs`' `handoff` calls it on a caption `_find_local_srt`
finds on disk, before `resolve_and_run`, instead of letting regen re-fetch it.
Anchors at `a3fd9c4` (`execute_fetches` L475, `_find_local_srt` L234) matched
exactly, no drift from the worktree recovery.

Tests: `TestAdoptCaption` (regen, 2 new: sparse caption deleted + fallback;
dense caption already at `<stem>.srt` kept + seeded, exercising the
skip-the-os.replace branch) + `TestHandoff` (add_songs, +1: a caption on disk
is gated, not re-fetched; the existing no-caption test renamed to say what it
now covers). Full suite: **4 known-failed, 1512 passed, 2 skipped** (1509 + 3
new, no regressions). `pre-commit` clean on the first pass.

`scripts/README.md`'s `add_songs` flow step 5 now says the already-saved
caption is gated in place, not fetched a second time.

Left: commits B-G (link parsing, failure reporting/exit code, resumability,
`--song` exact-match priority, `--song --reset` reporting + file ownership,
cleanup).
