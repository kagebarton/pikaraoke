# Library tools: pick single songs, add songs from YouTube links

Model: Claude Opus 5.5 (design, 2026-09-28); executor Claude Sonnet 5.

> **Status (2026-09-28): Phases 1-3 EXECUTED** (Sonnet 5), Results log below.
> Code commits `6cc2b29`, `2fdcf08`, `c8fe156`, `788b10c` reach `dev` by
> cherry-pick, in that order. A `/code-review` is due and has not been run
> (CLAUDE.md, Self-Review). There is no GATE and nothing here measures timing.

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

**Accepted cost:** `execute_fetches` asks yt-dlp for the manual caption again
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
