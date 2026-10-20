# Library tools: pick single songs, add songs from YouTube links

Model: Claude Opus 5.5 (design, 2026-09-28; Phase 3.2 design 2026-10-19);
executor Claude Sonnet 5 (through Phase 3.1 commit C), Claude Sonnet 5.5
(commit D on).

> **Status (2026-10-19): Phase 3.2 DONE** (executor Sonnet 5.5): commits A-C
> `965776f`, `84e0f2f`, `75454c1`, plus its Verify pass (see the Results log).
> Phase 3.1 is done (commits A-G `c096631`, `975175b`, `6ecb41d`, `e81607b`,
> `db2d193`, `f6490e1`, `73dada4`, plus its Verify pass). The `/code-review` of
> the 3.1 commits ran the same day (Opus 5.5, see the Results log), and Ken
> ruled that all of its findings are fixed in one pass: Phase 3.2. Landing is
> next, which is Ken's call: all code commits (`6cc2b29`, `2fdcf08`, `c8fe156`,
> `788b10c`, then 3.1's, then 3.2's) go to `dev` by cherry-pick in branch
> order.
> There is no GATE and nothing here measures timing.
> **2026-10-20:** Ken's real-world run of `add_songs` on a 6-song playlist
> (prompts live, then a rerun) is in the Results log.
> **Landing RULED by Ken 2026-10-20: deferred.** This branch does not land on
> its own. It waits for the plan (being written in another session) that
> moves these tools, and others, into the web UI; when that plan is done,
> both land on `dev` together. The cherry-pick list above still holds.

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

## Phase 3.2: fixes from the second code review

Source: Opus 5.5 ran `/code-review` on 2026-10-19 at `8730fff` over the 3.1
code commits (`d9c86a2..73dada4`), with three finders (correctness,
simplicity, robustness), and checked every finding against the code. Ken
ruled on 2026-10-19: fix 1 the way it is designed below, and fix all the
others in the same pass. These designs are Opus decisions, and the executor
doesn't reopen them. Decisions 1-5 and the 3.1 designs A-G still hold.

Anchors are at `8730fff` (the code is the same as at `73dada4`). The quoted
code is the anchor; a line number only helps you find it.

**Baseline** at `8730fff`: **4 known-failed, 1554 passed, 2 skipped** (3.1's
end state). Make commits A-C in order. Each one carries its own tests, ends at
the baseline plus its new tests, and passes `pre-commit`. Plan-log rows go in
their own commits, as before.

### A. A song with a karaoke file counts as processed

**The problem:**
- 3.1 D's `_library_status` (`scripts/add_songs.py` L131) calls a video with
  no bundle `in library, not processed`, and hands it to the pipeline again.
- The pipeline writes a bundle only when the song had lyrics:
  `if self._config.capture_alignment_debug and lyrics_path is not None:` in
  `pikaraoke/pipeline/stages/lyric_align.py` L289. It writes the karaoke file
  (`karaoke/<stem>.ass`, L264-276) either way.
- So a song that already ran without lyrics (transcribed, or no lyrics
  found) comes back as unprocessed on every rerun of its playlist. It then
  gets a Genius prompt and a full GPU pipeline run, which overwrites its
  karaoke file with no backup.
- README step 5 says "a song with no bundle has no finished outputs to lose".
  That is wrong for exactly these songs.

**The fix:**
1. **`_library_status`:** a video is `in library, not processed` only when it
   has **neither** `alignment_debug/<stem>.json` **nor** `karaoke/<stem>.ass`,
   checked with `Path.is_file()` on both. Anything else is
   `already in library`. Drop the `rab._read_bundle` call: the question is
   whether the file exists, not what it says.
   - Intended behaviour change: a bundle that exists but doesn't parse now
     counts as processed. Regen already warns about an unreadable bundle and
     ignores it when it reprocesses the song.
   - A song skipped at the Genius prompt has neither file, so it still comes
     back as unprocessed. That is intended: it was never processed.
   - Docstring: say why the karaoke file counts. The pipeline writes a bundle
     only when the song had lyrics, so a transcribed song has the karaoke file
     alone.
2. **README** (`scripts/README.md`, `add_songs` flow):
   - Step 2: "A video with no alignment bundle is one an earlier run downloaded
     but never processed" becomes "A video with neither an alignment bundle
     nor a karaoke file is one an earlier run downloaded but never processed".
   - Step 5's last sentence becomes: "No backup is needed; a song handed off
     has no bundle and no karaoke file, so it has no finished outputs to
     lose."

**Tests** (`TestResolveUrlsDedupe`, existing style):
- A video with `karaoke/<stem>.ass` and no bundle is `already in library`.
  Check that this test fails against the old `_library_status`.
- A video with an unreadable bundle (`alignment_debug/<stem>.json` holding
  `not json`) and no karaoke file is `already in library`.
- The existing four tests (video with a bundle, video with neither file,
  `.mp3`, video wins over `.mp3`) pass unchanged.

Commit: `fix(add_songs): a song with a karaoke file counts as processed`.

### B. A reset that hits a locked file stops with a message, not a traceback

**The problem:**
- `_remove` (`regen_alignment_bundles.py` L855) raises when a single file
  can't be deleted (`path.unlink(missing_ok=True)`). On Windows that happens
  when another process holds the file open.
- `regen.main()` calls `clear_output_folders` after the backup with no guard,
  so the reset dies with a traceback partway through the wipe.

**Decided: keep the stop.** Raising on a file is right. The reset exists so
that "no stale caption or transcript survives to be mistaken for current"
(`main()`'s own comment). A locked `subtitles/<stem>.srt` that survived while
its `.srt.generated` marker was deleted would look like a real caption to
`_find_local_srt`. A tree that can't be fully removed is still only warned
about, as in 3.1 G: only the unscoped `karaoke/` goes through `rmtree`, and the
pipeline overwrites every `.ass` it rebuilds. What is wrong today is the
traceback, and that nothing tells Ken what to do.

**The fix:**
1. In `regen.main()`, wrap `clear_output_folders(folder, stems=stems)` in
   `try` / `except OSError as e:`. On error, print to stderr:
   `Reset stopped: {e}. Nothing was processed. Close whatever has the file open
   (the app, a player) and rerun; the backup above holds the files as they
   were.` Then return 1. `resolve_and_run` is not called.
2. Docstrings say which failure does what:
   - `_remove`: a file that can't be removed raises, so a reset never goes on
     past a stale caption. A tree is warned about.
   - `clear_output_folders`: one line, a file it can't remove raises
     `OSError`.

**Tests:**
- `TestRemove`: a file whose `unlink` raises `OSError` propagates (patch
  `Path.unlink` for that path). This pins the asymmetry so a later cleanup
  doesn't "fix" it.
- `TestMainSongReset` style, driving `regen.main()` with `--song Mr --reset
  --yes`: patch `regen.clear_output_folders` to raise
  `PermissionError(13, "in use", "<path>")`, and `regen.resolve_and_run` with a
  `MagicMock`. Assert that `main()` returns 1, `resolve_and_run` is not called,
  and stderr holds `Reset stopped`. Reuse that class's `_setup_library` and its
  `PYTORCH_CUDA_ALLOC_CONF` `setenv`.

Commit: `fix(regen): a reset that cannot remove a file stops with a message`.

### C. Cleanup (simplicity and test hygiene), one commit

- **Ownership: the cheap test first.** `_owner(name, all_stems)` checks every
  stem in the library for every folder entry. 3.1's `_owns_file` gave up early
  on names no selected stem claims. Results are identical; only the speed
  changed.
  - Add `def _claims(stem: str, name: str) -> bool:` (`name == stem or
    name.startswith(stem + ".")`). `_owner` uses it.
  - Add
    `def _owned_by_any(name: str, stems: Collection[str], all_stems: set[str]) -> bool:`.
    It returns False unless some stem in `stems` claims `name`, and then
    returns `_owner(name, all_stems) in stems`. This gives the same answer as
    `_owner(...) in stems` (the owner always claims the name) while only
    claimed names pay for the full scan.
  - Both call sites use it: the `entries` list in `backup_text_folders`, and
    `selected` in `clear_output_folders`.
  - Tests (`TestOwner` or a new sibling class): `Song.srt` is owned by any of
    `["Song"]`; `Song.live.srt` with `["Song"]` and library
    `{"Song", "Song.live"}` is not; an unclaimed name is not. The existing
    scoped backup and wipe tests pass unchanged.
- **`TestMain` (`tests/unit/test_add_songs.py` L307) is isolated from the
  machine.** Add one autouse fixture to the class that:
  - patches `add_songs.rab.setup_process` to a no-op, so neither the allocator
    env var nor `logging.basicConfig` leaks into the rest of the session, and
  - patches `add_songs.PreferenceManager` to build a **real**
    `PreferenceManager` on an absolute path under
    `tmp_path_factory.mktemp("prefs")`. CLAUDE.md requires a real instance. An
    absolute path also skips `_migrate_legacy_config`, which would otherwise
    move a `./config.ini` from the current folder. Keep the config out of
    `tmp_path`, which is the test's library folder.
  - No new tests. The existing `TestMain` tests pass unchanged.
- **`add_songs` module docstring** (L2-9): replace the paragraph after the
  first line with:

  > Classifies each URL as a video or a playlist (expanding playlists via
  > yt-dlp) and downloads the IDs not yet in the folder through the app's own
  > ``DownloadManager`` (so the uploader caption and YTASR caption are fetched
  > exactly as the live app would). It then hands the new songs, plus any
  > video already in the folder that was never processed, to
  > ``regen_alignment_bundles``'s run path: the words-per-minute gate on the
  > caption the download saved, the Genius prompt, and the pipeline.

- **Comments:**
  - `adopt_caption` (regen L496-499): delete the inline comment's first
    sentence ("Promote yt-dlp's <stem>.en.srt ... in the live app."). The
    docstring already says it. Keep the sentence about playback and
    `_should_write_srt` keying on `subtitles/<stem>.srt`.
  - The comment above `_YOUTUBE_ID_RE` (`add_songs.py` L65-67) describes
    `classify_url`, not the regex. Delete it, and move its reason into
    `classify_url`'s docstring. The sentence "An id matching the YouTube id
    shape is a video, even when the link also carries ``list=``." gains: "(a
    search result or a Mix attaches one to a plain video link; the playlist
    page link, ``playlist?list=``, is what gets the whole list)".
- **`library_files`** (`add_songs.py` L119): one `sorted(...)` with
  `key=lambda p: (p.suffix.lower() in rab.VIDEO_EXTS, p)`, in place of
  `sorted` and then `.sort`. Keep the "videos last, so they win" comment. The
  existing video-wins test passes unchanged.

Commit: `refactor(scripts): cheaper ownership check, isolated add_songs main tests, docstring fixes`.

### Verify, then relay

- **Unit suite:** the full suite ends at the baseline plus the new tests.
- **Status check** (real CLI, `--dry-run`, no network beyond classifying the
  link, a fresh scratch folder, never the library):
  - Put an empty `Title---Z3x9i7njCCo.mp4` and an empty
    `karaoke/Title---Z3x9i7njCCo.ass` in the folder. Run
    `add_songs.py "https://www.youtube.com/watch?v=Z3x9i7njCCo" --folder <scratch> --dry-run`.
    It must report `already in library`.
  - Delete the `.ass` and rerun. It must report `in library, not processed`.
  - (3.1's Verify check "delete the bundle, then expect `not processed`" no
    longer holds on its own: a processed song also keeps its `.ass`.)
- **Safety check:** the app DB and `config.ini` hashes are unchanged, as in
  3.1.
- **Record and relay:** write a Results log row per commit plus the verify
  pass, then relay to Ken.
  - The change is small enough that the self-review covers it. Say so; don't
    flag another `/code-review`.
  - Flag a `/compact` point.
  - Landing is next and is Ken's call.

**STOP if:**
- any fix seems to need a change under `pikaraoke/` (Decision 5)
- an existing test changes outcome, other than one this section names
- anything outside the scratch folder changes during the status check

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

**Commit B** (`975175b`): `classify_url` rewritten on `urllib.parse` (host
check first, then a `youtu.be` link's id is its first path segment and any
other host's is its `v` query parameter via `parse_qs`, matched against the
YouTube id shape regardless of where `v=` falls in the query string).
`get_youtube_id_from_url` is no longer called or imported. A schemeless link
(no `://`) gets `https://` prepended before parsing, so a pasted link missing
its scheme still classifies (not asked for by the plan, but a real regression
the rewrite would otherwise have introduced — the old string-slicing version
didn't need a scheme). Host check is a dot-boundary suffix match
(`== "youtube.com"` or `.endswith(".youtube.com")`), not the plan's literal
"ends with youtube.com", so `notyoutube.com` is correctly unrecognised —
checked against all 9 link shapes the plan and its problem list name (`pp=`,
`music.youtube.com`, `t=`, a param before `v=`, a param between `v=` and
`list=`, a Mix link, `list=` before `v=`, `m.youtube.com`, a non-YouTube host
with a `v` param) before writing any code, via a standalone dry run, then
again as tests.

Tests: `TestClassifyUrl` keeps its 5 existing cases + 9 new (one per link
shape above). Full suite: **4 known-failed, 1521 passed, 2 skipped** (1512 +
9 new, no regressions). `pre-commit` clean on the first pass.

Help text (`--help`) and `scripts/README.md`'s Usage section restated as the
general rule instead of one example shape.

**Commit C** (`6ecb41d`): `handoff` returns regen's exit code (was: discarded
it, returned the job list). `resolve_urls` returns `(entries, unreadable)`
instead of just `entries` -- every existing call site updated. The download
loop counts a download successful only when `song_downloaded` actually fired
during that call (`len(new_songs)` before/after), printing why when a
return-code-0 download leaves no file. `expand_playlist` passes
`timeout=300`; `TimeoutExpired` is caught and reported alongside
`CalledProcessError`. `main()`'s exit code is 1 on any unreadable URL, failed
download, or non-zero pipeline result -- checked under `--dry-run` and on the
"Nothing new to download" path too. `Processed:` dropped from the summary
(regen's own `Done.` line already reports the pipeline).

Tests: drove `main()` end to end for the first time (`TestMain`, 5 new, via a
scripted `DownloadManager` stand-in that emits `song_downloaded` through the
real `EventSystem` `main()` builds, per the plan's own instruction) + 3 more
on `resolve_urls`/`handoff` directly (timeout reported, an unrecognised URL
counts as unreadable, `handoff` returns the pipeline code) + 1 existing test's
mocked `check_output` fixed for the new `timeout` kwarg. Full suite: **4
known-failed, 1529 passed, 2 skipped** (1521 + 8 new, no regressions).
`pre-commit`'s first pass reformatted one long `FAILED:` print across two
lines (black, cosmetic only -- reviewed the diff, reran the targeted tests).

**Commit D** (`e81607b`, Sonnet 5.5 session): each `_execute_download` call is
wrapped in `except Exception:` (`logger.exception("Download failed: %s", id)`),
and the exception sets `rc = 1` so it takes the same `FAILED: <id>` / count /
continue branch a non-zero return already did (one failure path, not two).
`existing_ids` (a set of ids from `rab._list_videos`) is replaced by
`library_files(folder) -> dict[str, Path]`, built from every file whose suffix
is in `SongList.VALID_EXTENSIONS`; when a video and another file share an id
the video is the one kept (the plan didn't say; regen only processes videos,
so the video has to be the entry that can come back `in library, not
processed`). `resolve_urls`'s second parameter is now `library` (that dict)
instead of `existing_ids`, with a new `_library_status(path)` returning
`in library, not processed` for a video (`rab.VIDEO_EXTS`) whose
`rab._read_bundle(folder, stem)` is `None` (which includes a bundle that
exists but doesn't parse), else `already in library`. `main()` builds
`unprocessed` (the library paths of those entries), keeps the "Nothing new to
download" exit for runs with neither list, prompts `Proceed with N download(s)
and M unprocessed song(s)? [y/N]`, and hands off
`new_songs + unprocessed` (downloads first). The report's dash rule is sized
from `max(len("status"), longest status)` instead of a fixed 18.
`scripts/README.md` flow steps 2, 3, 4 and 5 and the "no backup is needed"
sentence updated for the above.

Tests: `TestResolveUrlsDedupe`'s one `existing_ids={VID_A}` case became four
(video with a bundle -> `already in library`; video without one -> `in library,
not processed`; `.mp3` with the id -> `already in library`; video wins over an
`.mp3` sharing its id, asserted on `library_files` directly). `TestMain` gained
5: an exception in one download is counted failed and the next still runs (exit
1, handoff gets only the second song's path, `Downloaded: 1 Failed: 1`); an
unprocessed video is handed off with no download (the fake `DownloadManager`
now fails the test on any id not in its script); unprocessed videos follow the
new downloads in the handoff order; a processed video isn't handed off
(`Nothing new to download.`); the confirm prompt text for 1 download + 1
unprocessed. New `TestPrintReport` (1): the dash rule is as wide as the longest
status. Full suite: **4 known-failed, 1538 passed, 2 skipped** (1529 + 9 new, no
regressions; run once before a last simplification of the failure path, which
the add_songs + regen files then re-passed, 78). `pre-commit`'s first pass
reformatted the test file (black, cosmetic only); second pass clean.

Not exercised: the interactive confirm prompt and a real `DownloadManager`
raising mid-download (a stand-in raises `RuntimeError`).

**Commit E** (`db2d193`): `select_songs` collects, per pattern, the videos
whose YouTube ID equals the pattern, or whose stem or file name equals it
case-insensitively; those are the hits when there are any, else the
case-insensitive substring match is used as before. The one-song-per-pattern
rule is unchanged (a pattern with two exact matches, e.g. `Hello.mp4` +
`Hello.mkv`, still raises). `_matches` is replaced by `_is_exact_match` (the ID
test is now doing real work, since it picks the exact tier). The
`sys.path.insert`, its comment and the `sys` import are gone from
`song_select.py`, along with the now-unneeded `# noqa: E402` on its one
remaining import. `--song` help in regen and backfill reads "a YouTube ID, the
file name, or part of it; an exact match wins", and `scripts/README.md`'s two
`--song` paragraphs say so too.

Tests: `test_result_is_deduped_and_in_input_order` renamed
`test_result_is_in_input_order`; 4 new in `TestSelectSongs` (`Hello` and `hello`
both pick `Hello.mp4` over `Adele - Hello.mp4`; the file name `hello.mp4` does
too; an exact ID wins over a title containing that string; two exact matches
still raise). The first three fail against the old `song_select.py` (checked by
swapping the old file back in) and the fourth passes on both. Full suite: **4
known-failed, 1542 passed, 2 skipped** (1538 + 4 new, no regressions).
`pre-commit` clean on the first pass.

**Commit F** (`f6490e1`): `print_report` prints `Selection: selected songs
(reset)` when `--song` and `--reset` are both given. The module docstring has
the `[--song PATTERN]...` usage and one paragraph saying the backup and the
`--reset` wipe touch only the selected songs' files; the `--reset` help has
the same clause; `main()`'s `Backed up ...`, `No ... folders to back up` and
`Cleared ...` lines say `for the selected songs` when scoped. Backfill's
docstring usage line has `--song`, and its `[--folder PATH]` is now `[folder]`
(`folder` is a positional argument in its `parse_args`; the old text was wrong,
not asked for by the plan, fixed on the line already being edited).
`_all_stems` now builds from every file whose suffix is in
`SongList.VALID_EXTENSIONS` (it no longer goes through `_list_videos`);
selection and `scan_folder` still list videos only.

Tests: `TestPrintReportScope` (2: selected + reset says `(reset)`; selected
alone doesn't) and `TestMainSongReset` (1, drives `regen.main()` with `argv`
`[<tmp library>, "--song", "Mr", "--reset", "--yes"]`, patching `_make_genius`
and `resolve_and_run`). Fixture: videos `Mr`, `Mr.live`, `Other`, plus
`Mr. Brightside---abcdefghijk.mp3`, each with a `.srt` / `.srt.generated` /
`.ass` / `.txt` / bundle. Asserts the run path is handed only `Mr.mp4`; the
backup holds `Mr`'s files and none of the three siblings'; `Mr`'s regenerable
files are wiped and its bundle survives; every sibling's files survive. Against
the old video-only `_all_stems` the test fails on exactly the `.mp3` sibling's
`.srt` being backed up (checked by swapping the old line back in). Full suite:
**4 known-failed, 1545 passed, 2 skipped** (1542 + 3 new, no regressions).
`pre-commit` clean on the first pass.

Known limit, no code change (per the plan): `_select_en_srt`
(`pikaraoke/lib/youtube_dl.py`, called by `download_manual_en_subs`) treats
every `<stem>.*.srt` as an English variant and deletes the extras, which
includes a longer-stem sibling's caption (`Song.live.srt` when the selected
song is `Song`). With `--song` the backup is scoped and no longer covers that
sibling. It needs one song's name to be another's name plus a dot; the plan
recorded the library as having no such pair (checked 2026-09-28) and this
session did not re-check. The fix would be under `pikaraoke/` (Decision 5).

**Commit G** (`73dada4`): `KEEP_ON_RESET = {"subtitles": ASR_JSON3_SUFFIX,
"lyrics": ".lrc"}` replaces the two inline branches; `_clear_except_suffix` and
`_clear_selected` are one `_clear_dir(dir_path, keep_suffix, selected)` (where
`selected(name)` is always true unscoped, else `_owner(name, all_stems) in
stems`) plus a `_remove(path)` helper. The unscoped reset still removes
`karaoke/` whole (`KEEP_ON_RESET` has no entry for it; the existing test still
passes). A failed `shutil.rmtree` is now a `logger.warning` ("Could not fully
remove ...") instead of `ignore_errors=True`; a failed file `unlink` still
raises as before (the plan named only the `ignore_errors` path).
`_owns_file(name, stem, all_stems)` is replaced by `_owner(name, all_stems) ->
str | None` (longest claiming stem); both call sites are `_owner(e.name,
all_stems) in stems`. Checked against the old function on 200,000 random
stem sets and names (a throwaway script outside the repo): they agree on every
case. `setup_process()` (allocator env default + logging) is in regen, called
by regen's and `add_songs`'s `main()`; backfill keeps its own copy (not in the
plan). `resolve_and_run(jobs)` now builds the `PipelineConfig` (with
`intermediate_dir`), calls `_make_genius()` and prints the no-token warning
itself; `warn_if_no_genius_token` is gone; `add_songs.handoff(song_paths)` lost
its `config` and `genius` parameters and `add_songs` dropped its `GeniusClient`
and `PipelineConfig` imports. As the plan said, the no-token warning now prints
after the backup message; the config and Genius client are also now built
after the backup and the reset wipe rather than before them (so a failure
constructing either would now come after the wipe; nothing in this session
triggered one).

README (`add_songs` section): step 1's parenthetical dropped; step 4 no longer
names `KaraokeDatabase(":memory:")` or `find_by_id`; step 5 no longer names
`SongJob`, the `fetch` plan or `resolve_and_run`; the "Downloads run
unattended" paragraph and the "Run it while the app is idle" section became one
line pointing at `--help` (so the README no longer carries the 3-11x
measurement; the memory `concurrent-gpu-inference-rejected` and the `--help`
epilog still say it).

Tests: `TestBackupTextFoldersScoped._setup` and
`TestClearOutputFoldersScoped._setup` became one module-level
`_scoped_library(folder)` (the superset of the two: ASR json3, `.lrc`,
`.srt.generated`, bundles); their assertions are unchanged and still pass.
`TestMainSongReset` and the `add_songs` `TestMain` tests no longer patch
`_make_genius`; `TestHandoff` calls `handoff(paths)` and asserts
`resolve_and_run` got `(jobs)`. New: `TestOwner` (4: own stem, longest stem
wins, a prefix without a dot isn't a claim, unclaimed entry -> `None`),
`TestRemove` (3: file and tree removed, missing path is a no-op, a tree whose
`rmtree` raises `OSError` is warned about, not raised), `TestResolveAndRunSetup`
(2: warns with no token; passes `run_jobs` a config with
`intermediate_dir` set and the Genius client). Full suite: **4 known-failed,
1554 passed, 2 skipped** (1545 + 9 new, no regressions). `pre-commit` clean on
the first pass.

**Verify pass** (2026-10-19, Sonnet 5.5, worktree at `970f241`, all runs from
the repo root with `uv run --no-sync`; scratch folders `verify_links` and
`verify_run` in the session scratchpad, never the library).

Unit suite after G: **4 known-failed, 1554 passed, 2 skipped** (Phase 3's end
state 1509 + 45 new across A-G).

Link check, the real CLI, `--dry-run`, an empty scratch folder, one run per
link, id `dQw4w9WgXcQ`: all 11 shapes below report `Songs found: 1`, `new`,
exit 0 (`watch?v=X`, `watch?v=X&list=PLxxxx`, `youtu.be/X?si=`, `&pp=`,
`music.youtube.com`, `&t=30s`, `watch?feature=shared&v=X`, `&t=30s&list=Y`, the
Mix link `&pp=abc&list=RDX&start_radio=1`, `watch?list=Y&v=X`,
`m.youtube.com`). `notyoutube.com/watch?v=X` prints `unrecognised`, `Songs
found: 0`, exit 1. The scratch folder was still empty afterwards. The status
column's dash rule is 6 wide for `new` (commit D).

Real run, `add_songs.py "https://www.youtube.com/watch?v=Z3x9i7njCCo" --folder
verify_run --yes`, stdin `\nt\n`, three invocations on the same folder:
1. 11:02-11:04: downloaded the video and both captions, gated the uploader
   caption, reached `run_jobs`, no Genius prompt; `whisper_worker.start()` then
   raised `TimeoutError: Whisper worker did not become ready in time` (the
   constant is 60 s; the model had not loaded in that time). Exit 1.
2. Same command: the report said `in library, not processed` (a video, no
   bundle), nothing was downloaded, the song was handed to the run path. The
   Whisper model loaded in 12.0 s this time. Then
   `UnicodeEncodeError: 'charmap' codec can't encode ...` in
   `run_jobs`' own `print(f"[i/n] {song.name} -- {label}")` (stdout piped to a
   file is cp1252 here; the title is Korean). Not a line these commits touch.
   Exit 1.
3. Same command with `PYTHONUTF8=1`: `in library, not processed`, then
   `[1/1] ... -- fetched srt (from video)`, `OK`, `Done. succeeded=1 failed=0
   skipped=0`, `Downloaded: 0 Failed: 0`, exit 0. Whisper loaded in 11.7 s; the
   pipeline took ~5.5 min (11:07:26-11:12:44). The line `Fetching video
   captions` appears **0 times in all three logs**.

Artifacts in `verify_run` after invocation 3: video, `subtitles/<stem>.srt`
(uploader caption; no `.srt.generated`), `subtitles/<stem>.en.asr.json3`,
`vocal/`, `nonvocal/`, `karaoke/<stem>.ass`, `alignment_debug/<stem>.json`,
the same set as Run B. Byte sizes of six of them equal the real library's copy
of the same song (video 31,369,791; vocal 7,642,256; nonvocal 9,582,312; `.ass`
12,469; `.srt` 5,744; `.en.asr.json3` 49,812). The scratch bundle's size was
not recorded before the next step deleted it (the library's is 23,832 B).

Bundle delete then `--dry-run` (same command): before the delete the song
reported `already in library`; after deleting
`verify_run/alignment_debug/<stem>.json` it reported `in library, not
processed`. Exit 0 both times.

Safety: app DB `%APPDATA%\pikaraoke\pikaraoke.db` sha256 `5c9dec18...bedab`,
mtime `1779911392`, and `config.ini` sha256 `e264ca26...0cb8` identical before
and after (and equal to Run A/B's values). The real library
(`D:/shared/pikaraoke-songs`) already holds seven files for `Z3x9i7njCCo`
(video, both captions, both stems, `.ass`, bundle), all with mtimes
2026-09-28 15:02-15:07; none changed during these runs (the plan's Run B entry
says that song was not promoted at the time; someone has since copied it, not
this session). `%APPDATA%\pikaraoke\tmp` holds only `lyric_choices` (Sep 28)
after the runs; the pipeline's own temp dir was removed. `git status` in the
worktree: clean.

Not exercised: the confirm prompt (`--yes`) and the Genius prompt (a usable
caption existed, so none fired) inside `main()`.

Observations, not changes: a run that only resumes unprocessed songs prints
`Downloaded: 0 Failed: 0` and no sync-library reminder (the reminder is gated on
`downloaded`); the Whisper 60 s load timeout was hit once on a cold start and
not again; a piped stdout on Windows crashes regen's progress line for titles
outside cp1252 (not new, not in scope).

No STOP fired (A's existing tests did not change outcome; nothing needed a
change under `pikaraoke/`; nothing outside the scratch folder changed).

Left: nothing in Phase 3.1. A `/code-review` of the 3.1 commits is due, not run.
Landing on `dev` is Ken's call: cherry-pick every code commit in branch order
(`6cc2b29`, `2fdcf08`, `c8fe156`, `788b10c`, `c096631`, `975175b`, `6ecb41d`,
`e81607b`, `db2d193`, `f6490e1`, `73dada4`); the session that lands `--song`
then retires the one-song driver recipe in memory `regen-reprocessing-workflow`.

### Code review (3.1)

2026-10-19, Opus 5.5, `/code-review` at `8730fff` over `d9c86a2..73dada4 --
scripts tests`: three finders (correctness, simplicity, robustness), 10
findings returned, each checked by Opus against the code. Read-only; nothing
on the branch changed.

Checked and kept (all fixed in Phase 3.2):

| # | Where (at `8730fff`) | What the code does | 3.2 |
|---|---|---|---|
| 1 | `add_songs.py` `_library_status` L131 | no bundle means `not processed`; `lyric_align.py` L289 writes a bundle only when `lyrics_path is not None`, while the `.ass` is written either way | A |
| 2 | regen `_owner` L747, both call sites | every folder entry is checked against every library stem (`_owns_file` returned early on a name the stem didn't claim) | C |
| 3 | regen `_remove` L855 / `main()` | a file `unlink` that fails raises out of `main()` after the backup and a partial wipe, with a traceback | B |
| 4 | `test_add_songs.py` `TestMain` L307 | runs the real `setup_process()` (no `setenv`) and `PreferenceManager()` on the default path | C |
| 5 | `add_songs.py` module docstring L4-9 | still says it skips every id in the folder and fetches the caption again | C |
| 6 | `adopt_caption` inline comment; comment above `_YOUTUBE_ID_RE`; `library_files` double sort; `_library_status` parses the bundle JSON for an existence check | duplicate or misplaced text, redundant work | A, C |

Checked and dropped:
- A sparse caption at `subtitles/<stem>.srt` is deleted by `adopt_caption`.
  That is 3.1 A's specified fix.
- The broad `except Exception` around `_execute_download`. That is 3.1 D's
  specified boundary, and it logs with a traceback.
- A malformed `v=` plus `list=` becoming a playlist. That is 3.1 B's
  specified rule.

Ken's flagged areas, checked with no finding:
- G's config and Genius construction now runs after the wipe. The caption
  fetch, the prompts and `run_jobs` already ran after it, and the backup comes
  first.
- `_owner` matches `_owns_file` for every possible name, not only on the
  sampled domain: two claiming stems of the same length are the same string.
- C's exit code and the event-based success check.
- A's `srt_path == playback_srt` branch: no path gates a caption twice.

Ken's ruling (2026-10-19): fix 1 as designed ("has a bundle or a karaoke file"),
and fix all the others in the same pass. That pass is Phase 3.2.

### Phase 3.2

**Worktree state (2026-10-19, before any edit).** Branch tip `8c149a0`, `git
status` clean, `pikaraoke` imports from the worktree. The `.venv` was not
intact, the same pattern as the 3.1 recovery note: a RECORD-versus-disk check
found missing files in 129 of the 130 installed dists (file counts present
here against the main checkout's venv: torch 2,018 of 11,761; numpy 307 of
1,041; yt_dlp 211 of 1,154; babel 23 of 1,108). The folder mtimes are
2026-10-19 11:33-11:34, after the 3.1 Verify pass ended (11:12). `models/` is
still a junction to the main checkout's `models/`, and `libmpv-2.dll` is in
`.venv/Scripts`.

The first full run read **10 failed, 1548 passed, 2 skipped**: the four known
failures plus six route-render tests (`test_files_routes` x3,
`test_info_routes`, `test_search_render` x2) that return 500 with
`UnknownLocaleError: unknown locale 'en'`, because `babel/locale-data` was
empty. Repaired that one package only, from the uv cache with no network:
`uv pip install --python .venv/Scripts/python.exe --offline
--reinstall-package babel babel==2.17.0` (1,068 locale files back). The other
damaged packages were left alone: the unit suite passes without them and the
Verify check only classifies a link. Full suite after the repair: **4
known-failed, 1554 passed, 2 skipped**, the plan's baseline exactly.

**Commit A** (`965776f`): `_library_status` calls a video `in library, not
processed` only when neither `alignment_debug/<stem>.json` nor
`karaoke/<stem>.ass` is a file (`Path.is_file()` on both), so the
`rab._read_bundle` call is gone from `add_songs`. The docstring says why the
karaoke file counts. README step 2 and step 5's last sentence reworded as
designed.

Tests: two new in `TestResolveUrlsDedupe` (a video with a karaoke file and no
bundle; a video with `not json` in its bundle and no karaoke file; both
`already in library`). Both were run against the old `_library_status` first
and failed (`2 failed, 6 passed`); the four existing tests pass unchanged.
`_add_bundle` gained a `text` parameter (default `"{}"`) and a new
`_add_karaoke_file` helper. Full suite: **4 known-failed, 1556 passed, 2
skipped** (1554 + 2). `pre-commit` clean on the first pass.

**Commit B** (`84e0f2f`): `regen.main()` wraps `clear_output_folders(folder,
stems=stems)` in `try` / `except OSError`; the handler prints the designed
`Reset stopped: ...` message to stderr and returns 1, so `resolve_and_run` is
not called. `_remove` and `clear_output_folders` docstrings say which failure
does what. `_remove` itself is unchanged.

Tests: `TestRemove` gained a file whose `unlink` raises `PermissionError`
(patched on `Path.unlink` for that one path) and propagates; `TestMainSongReset`
gained the `main()` case (`clear_output_folders` patched to raise
`PermissionError(13, "in use", ...)`, `resolve_and_run` a `MagicMock`; asserts
return 1, not called, stderr holds `Reset stopped` and `in use`). The `main()`
test failed against the old code (raw `PermissionError` out of `main()`);
the `_remove` test passes against both, as intended, since it pins today's
behaviour. The stderr check uses `in use` and not the path because `str()` of
the error escapes backslashes on Windows. Full suite: **4 known-failed, 1558
passed, 2 skipped** (1556 + 2). `pre-commit` clean on the first pass.

**Commit C** (`75454c1`): regen gained `_claims(stem, name)` and
`_owned_by_any(name, stems, all_stems)`; `_owner` uses `_claims`, and the
`entries` list in `backup_text_folders` and `selected` in
`clear_output_folders` use `_owned_by_any`. `add_songs`: the module docstring
paragraph replaced as designed; the comment above `_YOUTUBE_ID_RE` deleted and
its reason moved into `classify_url`'s docstring; `library_files` sorts once
with `key=lambda p: (p.suffix.lower() in rab.VIDEO_EXTS, p)`. `adopt_caption`'s
inline comment lost its first sentence.

Tests: `TestOwnedByAny` (3 new: an entry of a selected stem; `Song.live.srt`
with `["Song"]` and library `{"Song", "Song.live"}` is not owned; an unclaimed
name is rejected, with `_owner` patched to raise so the test fails if the full
scan runs). `TestMain` gained one autouse fixture that no-ops
`add_songs.rab.setup_process` and builds a real `PreferenceManager` on an
absolute path under `tmp_path_factory.mktemp("prefs")`; no tests added to it
and its existing tests pass unchanged. Leak check, `TestMain` run in-process
from an unset `PYTORCH_CUDA_ALLOC_CONF`: the test file at `75454c1^` leaves it
set in `os.environ`, the new one does not (root logger handlers 0 -> 0 either
way, because `logging.basicConfig` does nothing while pytest's own handler is
attached). Full suite: **4 known-failed, 1561 passed, 2 skipped** (1558 + 3).
`pre-commit` clean on the first pass.

**Verify pass** (2026-10-19, Sonnet 5.5, worktree at `75454c1`, `uv run
--no-sync` from the worktree root; `pikaraoke` and `scripts/add_songs.py`
confirmed to import from the worktree).

Unit suite after C: **4 known-failed, 1561 passed, 2 skipped** (the four are
the known Windows set; 1554 baseline + 2 + 2 + 3 = 1561).

Status check, the real CLI with `--dry-run`, a fresh scratch folder
(`verify_status` in the session scratchpad, never the library), an empty
`Title---Z3x9i7njCCo.mp4`, link `watch?v=Z3x9i7njCCo`, exit 0 both times:

| Folder state | Status reported |
|---|---|
| `.mp4` and empty `karaoke/Title---Z3x9i7njCCo.ass` | `already in library` |
| `.ass` deleted, `.mp4` only | `in library, not processed` |

Safety: `%APPDATA%\pikaraoke\pikaraoke.db` sha256 `5c9dec18...bedab` and
`config.ini` sha256 `e264ca26...0cb8` identical before and after (and equal to
3.1's values); the db, `-wal` and `-shm` files kept their sizes and mtimes
(`-wal` 1,334,912 B, Sep 28 15:06); `%APPDATA%\pikaraoke\tmp` unchanged
(`lyric_choices` only, mtime Oct 19 11:12); the main checkout is still on
`dev` with a clean status; the worktree is clean after the three commits.

Not exercised: the interactive prompts inside `main()` (confirm and Genius)
still have not run live, and no real download or pipeline run was needed for
this phase.

No STOP fired: `execute_fetches`' tests were not touched, no existing test
changed outcome, nothing needed a change under `pikaraoke/`, and nothing
outside the scratch folder changed.

Left: nothing in Phase 3.2. Landing on `dev` is Ken's call: cherry-pick every
code commit in branch order (`6cc2b29`, `2fdcf08`, `c8fe156`, `788b10c`,
`c096631`, `975175b`, `6ecb41d`, `e81607b`, `db2d193`, `f6490e1`, `73dada4`,
`965776f`, `84e0f2f`, `75454c1`); the session that lands `--song` then
retires the one-song driver recipe in memory `regen-reprocessing-workflow`.

### Real-world run (Ken at the keyboard, 2026-10-20)

Ken asked for a real-world run before landing. Driver Claude Opus 5.5; Ken ran
every command and answered every prompt. The corpus regen had exited and no
other GPU job ran. Worktree at `3b62430`; the `.venv` passed an import smoke
(`pikaraoke` from the worktree, `torch 2.6.0+cu124` with CUDA,
`audio_separator`, `stable_whisper 2.19.1`, `yt_dlp`, `lyricsgenius`) and
`uv sync --locked --dry-run` reported no changes, so it was not rebuilt.
yt-dlp `2026.08.19` in both the worktree and the main checkout, which is the
latest stable on PyPI (only `.dev0` builds are newer).

Command, from the worktree root in PowerShell with `PYTHONUTF8=1`, no `--yes`:

```
uv run --no-sync python -P scripts/add_songs.py "https://www.youtube.com/playlist?list=PLWPORwgk3oWc" --folder "D:\shared\libtools-test-20261020"
```

The scratch folder was new and seeded by hand with Adele's `.mp4` and
`karaoke/<stem>.ass` copied from `d:/shared/pikaraoke-songs`, so the
`already in library` row could fire; nothing else was in it.

Caption check before the run (`yt-dlp -J`, no download):

| id | manual subs | auto langs | `-orig` auto |
|---|---|---|---|
| `xFYQQPAOz7Y` Eminem, Lose Yourself | none | 0 | none |
| `fJ9rUzIMcZQ` Queen, Bohemian Rhapsody | 18 incl. `en` | 18 | none |
| `hLQl3WQQoQ0` Adele, Someone Like You | `en-nP7-2PuUl7o` | 157 | `en-orig` |
| `DYptgVvkVLQ` Jay Chou, 晴天 | none | 0 | none |
| `RPWDeLqsN0g` Jay Chou, 龍捲風 | `en` | 1 | none |
| `3JWTaaS7LdU` Whitney Houston, I Will Always Love You | `en-nP7-2PuUl7o` | 1 | none |

`RPWDeLqsN0g`'s `en` track, downloaded to the session scratchpad, is an English
translation ("Love is like a gust of wind, / here one moment, gone the next").

Genius search probe (the run's `GeniusClient`, read-only):

| query | hit 1 | other hits |
|---|---|---|
| `Jay Chou Sunny Day-` (the default for `DYptgVvkVLQ`) | 晴天 (Sunny Day) - 周杰倫 (Jay Chou), id 6347511 | none |
| `Jay Chou Tornado-` | 龍捲風 (Tornado) - 周杰倫 (Jay Chou), id 425304 | Mayday cover ft. Jay Chou, id 7581612 |
| `周杰倫 晴天` | id 6347511 | 晴天 - Andy Luidje ft. Jay Chou, id 6666632 |
| `Jay Chou Qing Tian`, `Jay Chou Long Juan Feng` | no hits | |

Ids 6347511 and 425304 return Traditional Chinese lyrics (42 and 26 lines).

Dry run with `--dry-run`: `Songs found: 6`; `hLQl3WQQoQ0` `already in library`,
the other five `new`. The report table's columns are `id`, `source` (the
playlist URL on every row) and `status`; no title column.

Real run: the confirm prompt was answered `y`; Genius prompts fired for
`xFYQQPAOz7Y` and `DYptgVvkVLQ`. One warning during the downloads, from the
auto-caption fetch for `fJ9rUzIMcZQ` (`download_auto_en_subs`, `--sub-langs
en.*`): `No subtitle format found matching "json3" for language en, using vtt`
then `Unable to download video subtitles for 'en-ar': HTTP Error 429: Too Many
Requests`. The video download continued; later downloads had no errors.
During `3JWTaaS7LdU`'s cue-align, three `Whisper align_refine failed`
tracebacks (`stable_whisper/alignment.py` line 212, `set_result_language` on a
`None` result: `AttributeError: 'NoneType' object has no attribute
'language'`), each followed by `lyric_align` `slice-align failed, degrading`:
`section lines 30-30`, `line 30`, `line 51`. Downloads 09:54-09:57, pipeline
done 10:37.

Outputs per song (bundles are `schema_version` 10, since the branch's base
`6bc19aa` is before `dev`'s `67d1c1f` / `50da4b0` / `e5c683e`):

| id | origin | Genius id | method | lines | lines with words | `.ass` Dialogue | interpolated | LRCLIB `.lrc` | `lrclib_fill` |
|---|---|---|---|---|---|---|---|---|---|
| `xFYQQPAOz7Y` | genius | 207 | joint | 87 | 86 | 86 | 1 | yes | eligible, 53 cues mapped |
| `fJ9rUzIMcZQ` | srt | | cue_align | 65 | 65 | 65 | 0 | no | |
| `DYptgVvkVLQ` | genius | 6347511 | joint | 42 | 18 | 18 | 20 | yes | `no_mapping`, 0 cues |
| `RPWDeLqsN0g` | srt | | cue_align | 55 | 55 | 55 | 0 | no | |
| `3JWTaaS7LdU` | srt | | cue_align | 60 | 60 | 60 | 0 | no | |

`xFYQQPAOz7Y`: `align_won` 59, `transcribe_won` 27. `DYptgVvkVLQ`: `align_won`
22, `transcribe_won` 0, 86 words; its `.ass` starts at line 5 (`Re-sol-sol-...`),
and its `\kf` tags span space-separated phrases. `RPWDeLqsN0g`'s `.ass` text is
the English translation. `3JWTaaS7LdU` lines 30 (`You ooh`, 126.86-129.10) and
51 (`Ooh I`, 228.72-230.56) are present with 2 words each.
`n_ytasr_words` 0 on both joint songs.

Rerun of the same command (Ken): every row `already in library`, nothing
downloaded.

Safety: `%APPDATA%\pikaraoke\pikaraoke.db` sha256 `5c9dec18...bedab` and
`config.ini` sha256 `e264ca26...0cb8`, the 3.2 values; db, `-wal`, `-shm`
sizes and mtimes as 3.2 recorded. `%APPDATA%\pikaraoke\tmp\lyric_choices`
mtime 10:13 (empty after the run). `d:/shared/pikaraoke-songs` not written;
the main checkout still on `dev`, clean.

Observed outside the branch's code (nothing here changed `pikaraoke/`):

- `download_auto_en_subs`' `en.*` matches every `en-<src>` translated
  auto-track, which is what drew the 429; on a non-zero exit it returns `None`
  without running `_select_asr_track` on what did arrive.
- A manual `en` track that is a translation passes the caption gate
  (`MIN_CAPTION_WPM` counts words, not language); no Genius prompt for it.
- Mandarin on the joint path: 24 of 42 lines absent from the `.ass`,
  `transcribe_won` 0, `lrclib_fill` `no_mapping` with an `.lrc` present.
- `stable_whisper.align` raises on its own failed-alignment `None` instead of
  returning it; the stage's degrade path catches it.
- In the branch's code: the `--folder` default is `get_default_dl_dir`'s
  `C:\Users\TsangK\pikaraoke-songs` (absent on this box), while `config.ini`
  holds `download_path = D:\Shared\pikaraoke-songs`; `add_songs` already
  builds a `PreferenceManager` (for the Genius token) but does not read
  `download_path`. Also in the branch's code: the report has no title column.
- The default Genius query drops CJK (`EMOJI_PATTERN` spans
  `U+24C2-U+1F251`); here the titles' English words carried the search.

Not exercised: `regen --song --reset` on real data; `backfill --song`'s queued
path.
