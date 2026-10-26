# Web library tools: regen, repair and playlists in the app

Model: Claude Opus 5.5 (design, 2026-10-20); executor Claude Sonnet 5.5.

> **Status (2026-10-26): Phases 0-7 and 6.1 done (3.1 = fixes from the Phase
> 1-3 code review, 3.1g included; the review of 3.1b-3.1d is done with its
> two fix commits; Phase 4's code is `7f5853e` and `55cfdbb`, Phase 5's is
> `641600a`, Phase 6's is `8a3b585`, Phase 7's is `0541907` and `ecbde50`,
> see the Results log). Phase 5.1 (the fixes from the Phase 4-5 code review,
> as Ken ruled them) is done too, code `874d49c`..`6caad6f`. Phase 6.1 (the
> fixes from the Phase 6 code review, approved by Ken 2026-10-22) is done
> too, code `a14906a`..`febeb2c`. Phase 7.1 (the fixes from the Phase 7
> code review, as Ken ruled them 2026-10-23) is done too, code
> `d280722`..`1bc3c29`. Ken's checks for Phase 7 (covering 7.1) ran
> 2026-10-23 and passed (record `01d9475`). Phase 7.2 (two fixes from
> that check, ruled by Ken 2026-10-23) is done too, code `71d565e` and
> `2c352b4`. Phase 8 (the after-download check and needs-a-pick list, the
> pick page, and playlists) is executed, code `1a26b68` and `3d26811`.
> Its code review ran 2026-10-23; Phase 8.1 (its recommended fixes,
> written up at Ken's request) is executed too, code `14632ae`..`2ba0c3d`.
> Phase 9 (the scripts README, the end-to-end runs and the landing list) is
> executed too, code `235d58b`. The code review of 8.1c and 8.1d ran
> 2026-10-24; Phase 8.2 (its recommended fixes, written up at Ken's request)
> is executed too, code `76f44e2`..`af07df4`. Ken's checks of Phase 7.2 and
> Phase 8 (covering 8.1 and 8.2) are done, with two open items he left as
> they are (see the Results log). Landing is next (see Landing).**
> Ken approved D2's Phase 3.1 bullet on 2026-10-20. Branch
> `web_library_tools`, off `library_tools` at `0bfa02a`; `dev` merged as
> `c34d889`. There is no GATE and nothing here measures timing. Landing is
> Ken's call (see Landing).
>
> **Landing list** (72 commits, in cherry-pick order onto `dev`; no `docs(plan)`
> commit, no merge). A dry run of all 72 on a throwaway worktree off `dev`
> (`3a5a2eb`) applied with no conflict and left a tree identical to this
> branch's outside `plans/`. Ken's checks added no commit to it.
>
> From `library_tools` (14):
>
> `6cc2b29`, `2fdcf08`, `c8fe156`, `788b10c`, `c096631`, `975175b`, `6ecb41d`, `e81607b`,
> `db2d193`, `f6490e1`, `73dada4`, `965776f`, `84e0f2f`, `75454c1`
>
> From `web_library_tools` (58):
>
> `870e34f`, `dd011af`, `9857986`, `b50595a`, `1ead8a8`, `fb13913`, `30f7c84`, `b871285`,
> `b2d8857`, `1b48a39`, `289a942`, `b5c4637`, `e8006da`, `86de4f7`, `26cf3b3`, `b6301da`,
> `5b67bff`, `25ace83`, `b849bb7`, `2bc909d`, `4165281`, `bc308ba`, `7f5853e`, `55cfdbb`,
> `641600a`, `874d49c`, `8b8d34f`, `6f08c59`, `14c7c14`, `b433e90`, `6caad6f`, `8a3b585`,
> `a14906a`, `e414e43`, `7a4a30e`, `febeb2c`, `0541907`, `ecbde50`, `d280722`, `05322ee`,
> `84a8220`, `fc0699b`, `2d83e70`, `1bc3c29`, `71d565e`, `2c352b4`, `1a26b68`, `3d26811`,
> `14632ae`, `9aae99d`, `59dd376`, `763d64e`, `2ba0c3d`, `235d58b`, `76f44e2`, `9f33dba`,
> `b5aa830`, `af07df4`

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
| `pikaraoke/templates/song_info.html`, `song_repair.html`, `library_run.html`, `pick_pass.html`, `playlist.html` | the new pages (`library_songs.html`, Phase 4d, was deleted by 7.2a: its lists open inline on the Library tools tab) |
| `pikaraoke/static/library-pages.js` | the page helpers the library pages share (Phase 7.1e; Ken, 2026-10-23) |

Changed (fork-owned unless marked upstream):

- `pikaraoke/pipeline/orchestrator.py`: a per-job stage list.
- `pikaraoke/lib/processing_manager.py`: the regen lane; the cancel count
  (Phase 8.2a).
- `pikaraoke/lib/genius.py`: `write_choice` replaces an existing choice file
  (Phase 8.2b; Ken, 2026-10-24).
- `pikaraoke/lib/pipeline_tracker.py`: regen and reprocess rows, new actions, ordering.
- `pikaraoke/routes/processing.py`, `pikaraoke/templates/processing.html` (rewritten).
- `pikaraoke/lib/lrclib.py`: fetch one record, skip marker.
- `pikaraoke/lib/youtube_dl.py` (upstream file): the fork's own
  `download_manual_en_subs` raises when the download fails, and nothing
  else changes there (Phase 7.1a; Ken, 2026-10-23).
- `pikaraoke/pipeline/stages/lyrics_fetch.py`: the one LRCLIB log call in
  `_resolve_lrclib` names a skip marker as a skip (Phase 7.2b; Ken,
  2026-10-23).
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
- *(Phase 3.1, approved by Ken 2026-10-20)* A regen that doesn't finish (it fails, or
  is cancelled during setup or during the run) also puts
  `lyrics/<stem>.lrc` back as it was when the job started. The old bundle
  stays in that case, so the LRCLIB choice must stay with it. Without this,
  a cancelled Genius re-pick loses the admin's skip or picked match (D3
  deletes or rewrites the file before the run), or leaves the new song's
  match next to the old song's bundle. The CLI does the same.
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

From Ken's live check of Phases 4-7.1 (2026-10-23; Ken ruled where each
goes):

- **Uploading hand-checked lyrics** as the lyric source of a Repair,
  Regenerate or Reset: a later plan of its own, after this branch lands on
  `dev`. It builds on this branch's Repair page and pick pass, and needs its
  own design first (what counts as the current pick, and how an uploaded
  sheet survives a later Reset).
- **Delete song and Rename leave the song's files behind**:
  `SongManager._get_companion_files` (upstream) knows only the `.srt`, the
  two stems and the `.ass`, so a delete leaves the bundle, the `.lrc` and
  the `.srt.generated`, and a rename leaves them under the old name. That is
  on `dev` today, from the Edit page, so it is fixed on its own small branch
  off `dev`, not here.

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

## Phase 3.1: fixes from the Phase 1-3 code review

Model: Claude Opus 5.5 (design, 2026-10-20); executor Claude Sonnet 5.5.

A read-only `/code-review` of `0381917..1428f47` (2026-10-20) found the
defects below. Each step names the defect it fixes, so you don't need the
review itself. Same worktree, same ground rules, same "Every phase ends the
same way". Before starting, confirm the worktree is clean at `1428f47` plus
this plan commit.

Every file touched here is in D1. `pikaraoke/pipeline/stages/lyric_align.py`
is **not**, so leave it alone even where a fix would be tidier there
(3.1a, 3.1h). Do the steps in order. Later steps use 3.1a's helpers, and
3.1c and 3.1d both change `_take_regen_job`.

### 3.1a. Tidy first (no behaviour change)

These make the fixes below land in one place each.

- `lrclib.lrc_path(song: Path) -> Path`: `song.parent / "lyrics" /
  f"{song.stem}.lrc"`. Use it in `ensure_lrc`,
  `library_regen.apply_lrclib_choice` and `library_status._lrclib_state`.
  Under D3 that file *is* the admin's LRCLIB choice, so the code that writes
  it and the code that reads it must not spell the path separately.
- `library_regen.bundle_path(folder: Path, stem: str) -> Path`:
  `folder / "alignment_debug" / f"{stem}.json"`. Use it in `read_bundle`,
  `finish_regen_job` and `library_links.file_status` (`library_links`
  already imports `library_regen`).
- `library_regen.is_genius_reuse(plan: Plan | None) -> bool`: a `seed` plan
  with `lyrics_origin == "genius"`. Use it in `prepare_regen_job` and in the
  script's `execute_lrclib_backfill`, which today repeats the test.
- `scripts/add_songs.py` `handoff`: keep the `resolve_plan` line, and
  replace the `find_local_srt` / `adopt_caption` lines with
  `gate_on_disk_caption(job)`. It is the same step, and D6's after-download
  check uses it too, so the CLI and the app can't drift apart.
- `PipelineTracker.retry`: delete the `item.kind == "regen" and
  item.regen_job is None` check. It can't be true, because `_on_regen_queued`
  always sets the job. `regen_job = item.regen_job` is enough, since only
  regen rows carry one.

The existing tests must pass unchanged. No new tests (the helpers are
one-liners).

Commits: `refactor(library): one place each for the .lrc and bundle paths,
the Genius-reuse rule and the on-disk caption gate`;
`refactor(processing): drop a retry check that can't fire`.

### 3.1b. An error while setting up a job no longer stops the queue

**Defect:** `_process_regen` catches errors only from `prepare_regen_job`
and the launch. `tempfile.mkdtemp` and `build_stages` can also raise: the
latter deletes the old de-reverb file, which gives a PermissionError on
Windows while the file is open. Such an error goes through `_run_job`'s
`finally` and out of `_run_loop`, which has no `except`, so the processing
thread dies. Every later job then stays "pending" until a restart, and the
failed row shows "complete".

- `_run_job(song_path, process, regen: RegenJob | None = None)` gains
  `except Exception as e: self._report_failure(song_path, e, regen)` before
  its `finally`. This becomes the one place where a job's error becomes
  `processing_error` (and `failed`, for a download only, as today).
- Remove the three catches that now repeat it, each of which only reports
  and returns:
  - around `prepare_regen_job` in `_process_regen`;
  - around the launch in `_launch_and_report`;
  - the generic `except Exception` after `join()` in `_launch_and_report`.

  Keep `except PipelineCancelled`.
- `_launch_and_report` returns `True` when the run succeeded and `False`
  when it was cancelled (3.1c and 3.1g use this). Update its docstring and
  `_process_regen`'s.
- Leave alone: an event handler that raises inside `_report_failure` still
  ends the loop (`EventSystem` lets handler errors through). That was true
  before this branch.

Tests (`test_processing_manager.py`). Each of these emits `processing_error`
with the error's message, leaves `pipeline_state` alone for a regen, and the
loop then runs the next queued job:
- `build_stages` raises PermissionError;
- `tempfile.mkdtemp` raises OSError;
- a download whose `get_pipeline_state` raises (this one marks `failed`).

`TestLaunchFailures` and `TestProcessRegen` stay green.

Commit: `fix(processing): an error while setting up a job no longer stops
the queue`.

### 3.1c. Cancelling a regen while it prepares stops it before the run

**Defect:** `_take_regen_job` pops the job from the lane, but `_active` is
set only at launch. During `prepare_regen_job` (the caption fetch, the
Genius and LRCLIB calls) the job is in neither place, and the row shows
"pending" with a Cancel button. That Cancel puts the path into
`_cancelled_paths`, which is the download lane's set, and the regen keeps
running. A later Process or Retry of that song is then silently skipped,
and its row shows "complete".

- `_ActiveJob.cancel_token: CancelToken | None`. It is None while a regen
  job prepares. `cancelling` is now read, so fix its "vestigial" comment.
- `_take_regen_job` sets `self._active = _ActiveJob(song_path=<the job's
  path>, cancel_token=None, kind="regen")` in the same lock hold as the pop.
  From the moment a job leaves the lane it counts as running, for
  `get_active_job`, for `enqueue_regen`'s refusal, and for the tracker,
  which shows it active with no phase.
- `get_active_phase`: None when the token is None.
- `cancel_active`: when the active job matches and its token is None, set
  `cancelling = True`, log, and return. Don't call the orchestrator: its
  token belongs to the previous job.
- `_launch_and_report`, under the lock:
  - if `_active` is set and `cancelling`, don't launch. After releasing the
    lock, emit `processing_cancelled` with the lifecycle log line, and
    return `False`;
  - otherwise launch. A download creates its `_ActiveJob` as today. A regen
    sets the token on the existing one, so `started_at` keeps counting from
    when the job was taken.
- So a cancel during setup takes effect when setup ends, before any
  pipeline stage runs. A reset's wipe has already happened by then, which is
  D2's accepted case: the files are in the backup.
- If setup fails after the cancel was asked for, the job ends as an error.
  `PipelineTracker._on_processing_error` and `_on_processing_complete` clear
  `cancelling` on the row they finish. Otherwise `get_status` would show
  that row as "cancelling" forever: the flag overrides every other status.

Tests:
- With `prepare_regen_job` blocked on a `threading.Event`, `get_active_job()`
  is the song and the phase is None.
- `tracker.get_status()` then `tracker.cancel(row)` marks the row
  cancelling. Releasing the event then launches no pipeline (no
  `run_one_async` call), emits `processing_cancelled`, removes the row,
  never calls `song_manager.delete`, and leaves `_cancelled_paths` empty.
- A later `enqueue(path)` of that song runs.
- A cancel during setup followed by a `RegenError` leaves an error row that
  isn't cancelling and offers `retry` and `dismiss`.

Commit: `fix(processing): cancelling a regen while it prepares stops it
before the run`.

### 3.1d. Regen jobs use the library's own spelling of the song path

**Defect:** the regen side compares `str(regen.song.song_path)` with path
strings from the song manager, which come from `os.walk` plus
`os.path.join` and keep whatever separators the library root was given.
With Ken's Windows root `d:/shared/pikaraoke-songs`, the library says
`d:/shared/pikaraoke-songs\X.mp4` and `str(Path(...))` says
`d:\shared\pikaraoke-songs\X.mp4`. Then:
- the "don't regen the playing song" check misses, so a Reset can wipe the
  playing song;
- the duplicate check and the `song_deleted` drop miss;
- `set_pipeline_state` / `set_loudnorm_offset` match no database row.

Phases 4-7 build jobs from `Path`s (7a's come from `list_videos`), so fix
it once, in the manager.

- `ProcessingManager._library_spelling(path: Path) -> str`:
  - `str(path)` when it is in `song_manager.songs`;
  - else the first entry `s` of `song_manager.songs` with `Path(s) == path`;
  - else `str(path)`, which also covers having no song manager.

  The scan is linear, which is fine at this library's size.
- `enqueue_regen` works out the spelling once and keeps it with the job:
  `_regen_jobs: list[tuple[str, RegenJob]]`. Every place that now uses
  `str(regen.song.song_path)` uses the stored spelling: the running and
  pending checks, `pending_jobs`, `regen_queued`'s `song_path`,
  `_drop_regen_jobs`, `_take_regen_job` (the `is_playing` call and
  `_active`), the loop's `_run_job` call, and `_process_regen` (pass it in).
  File work still uses `regen.song.song_path`.
- The tracker needs no change. `retry` hands the job back to
  `enqueue_regen`, which works the spelling out again.

Tests: a song manager whose `songs` holds the song spelled with a doubled
separator (`<tmp>` + `"//X---dQw4w9WgXcQ.mp4"`, the same file under `Path`
equality on every OS), and a `RegenJob` built from the plain `Path`. Then:
- `regen_queued` carries the library spelling, and so does `is_playing`;
- `song_deleted` with that spelling drops the job;
- a successful run calls `set_pipeline_state` with it.

Commit: `fix(processing): regen jobs use the library's own spelling of the
song path`.

### 3.1e. A retried regen starts from the plan it was queued with

**Defect:** `prepare_regen_job` changes the queued job's plan in place, and
the tracker keeps that same job for Retry. A Reset with a `fetch` plan (and
6a's "Repair from caption") fetches `subtitles/<stem>.srt` and turns the
plan into "use that .srt". If the pipeline then fails, Retry's reset wipe
deletes that `.srt` first, and the launch fails with "Lyrics file not
found" on every retry. `b2d8857` fixed only the case where the fetch itself
fails.

- `prepare_regen_job` works on a copy: `job = dataclasses.replace(regen.song)`
  at the top, and everything after uses the copy. `fetch_caption`,
  `adopt_caption` and `prepare_lyrics` replace `job.plan` rather than
  editing it, so a shallow copy is enough. The queued `RegenJob` is never
  changed. Say so in the docstring.
- Remove `b2d8857`'s put-back (`fetch_plan` and its restore). The copy
  makes it unnecessary.

Tests (`TestPrepareRegenJob`):
- After a reset `fetch` job whose caption passes, the queued job's plan is
  still `fetch`.
- Preparing the same job a second time wipes and fetches again (the
  download mock is called twice) and returns an `.srt` that exists.
- `b2d8857`'s retry test stays green.

Commit: `fix(regen): a retried regen starts from the plan it was queued
with`.

### 3.1f. The old bundle goes whenever the run transcribed

**Defect:** `finish_regen_job` removes the old bundle only for a
`transcribe` *plan*. A Genius pick (a `sidecar` plan) can also end up
transcribing when Genius is unavailable, either in `prepare_lyrics` for a
song without a YouTube id or in `LyricsFetchStage`. That run writes no
bundle, but the plan still says `sidecar`, so the old bundle stays. Song
Info then shows the old lyrics, and the next reuse run brings them back.

- `finish_regen_job(song: Path, lyric_method: str | None)` removes the
  bundle when `lyric_method == "transcribe"`. That is what `LyricAlignStage`
  sets exactly when it had no lyrics, which is exactly when it writes no
  bundle.
- Callers pass the run's `ctx.artifacts.get("lyric_method")`:
  - the manager in `_launch_and_report`;
  - the CLI's `run_jobs`: `ctx = orch.run_one(...)`, since `run_one`
    returns the context.

Tests:
- `TestFinishRegenJob`: `"transcribe"` removes the bundle;
  `"genius+joint"` and None keep it.
- The manager: a `sidecar` regen whose run reports `"transcribe"` removes
  the bundle.
- The CLI: update `TestRunJobsFinishesEachSong`.

Commit: `fix(regen): drop the old bundle whenever the run transcribed`.

### 3.1g. A regen that doesn't finish puts the song's LRCLIB file back

**STOP unless the status block says Ken approved D2's Phase 3.1 bullet.**
That bullet adds a rule to D2. If it isn't approved, skip to 3.1h and say
so in the relay.

**Defect:** D3 deletes or rewrites `lyrics/<stem>.lrc` before the run (a
skip marker, a picked record, or a delete for a new Genius id), and
`LyricsFetchStage` can write a new one during the run. A cancelled or
failed run leaves the old bundle in place, so one of two things follows:
- the admin's earlier skip or pick is gone, and the next reuse run fetches
  the automatic match;
- or the new song's match sits next to the old song's bundle.

This happens in the app and in the CLI (`--song X --reset`).

- `lrclib.snapshot_lrc(path: Path) -> str | None`: the file's text, or None
  when there is no file. Any other `OSError` raises, so the job fails before
  anything is changed.
- `lrclib.restore_lrc(path: Path, snapshot: str | None) -> None`: None
  deletes the file (`missing_ok`). Text is written back with the same
  sibling-tmp atomic write as `write_lrc`.
- `_process_regen`: take the snapshot (`lrclib.lrc_path(song)`) before
  anything else. Every end other than success restores it: an error
  anywhere, or a cancel during setup or during the run (`_launch_and_report`
  returned False). If the restore itself raises `OSError`, log a warning;
  it must not hide the job's own error.
- The CLI's `run_jobs`: take the snapshot before `prepare_lyrics`, and
  restore it in the `except` branch. A `prepare_lyrics` error still aborts
  the CLI, as it does today; leave that alone.

Tests:
- `lrclib`: the snapshot/restore round trip for a missing file, a skip
  marker and a record.
- The manager:
  - a Genius re-pick to a new id whose run fails gets the old `.lrc` text
    back;
  - a skip marker followed by a re-pick that is cancelled during the run
    gets the marker back;
  - with no `.lrc` before, a run that writes one (the mocked run writes the
    file) and then fails leaves no file;
  - success keeps the new file.
- The CLI: a failing song gets its `.lrc` back.

Commit: `fix(regen): a regen that doesn't finish puts the song's LRCLIB file
back`.

### 3.1h. Three small fixes

- **A skip marker isn't an LRCLIB match.** The pipeline records a skip
  marker as an LRCLIB reference with no id (`{"lrc_file": ...}`), so
  `SongStatus.lrclib` and every history entry show a match the admin
  rejected. In `library_status`, count an LRCLIB reference only when it has
  an `id`, through one helper used for `SongStatus.lrclib`,
  `HistoryEntry.lrclib` and `_lrclib_state`'s `rejected` test. (The writer
  is in `lyric_align.py`, which D1 doesn't list.) Tests: a bundle with
  `lyrics.lrclib == {"lrc_file": ...}` gives `lrclib` None in both, and
  `none` rather than `rejected` when there is no marker.
- **The caption error message.** `fetch_caption` falls back the same way
  for "no caption", "download failed" (a YouTube 403) and "too sparse", so
  the current message ("no longer passes the lyrics check") is wrong for
  two of the three. In Phase 6's Repair from caption, it would send the
  admin to the screen they are already on. New text: "No usable YouTube
  caption: none could be downloaded, or it is too short to be lyrics. Try
  again later, or pick lyrics with Repair lyrics on Song Info." Update the
  test that checks the text.
- **A playlist link can't be read as a yt-dlp option.** `classify_url`
  accepts a link without a scheme, so `--exec=x.youtube.com?list=1` reaches
  yt-dlp as an option. In `read_playlist`, put `"--"` before the URL. Test:
  the command ends with `["--", url]`.

Commit: `fix(library): a skipped LRCLIB match isn't shown as one, a clearer
caption error, playlist links can't pass as options`.

### 3.1i. Not fixed, and why (record only; don't change)

- **Two timing gaps in which a fast failure can show as "complete".** One is
  `regen_queued`, which is sent after the job is takeable. The other is a
  status read between the tracker's `song_downloaded` handler and `enqueue`.
  Each needs a thread switch inside a window of microseconds, and closing
  them means reworking the event order.
- **The two lanes don't check each other for duplicates.** This needs a
  re-download of a song while its regen waits, and `enqueue` is upstream's
  download path.
- **The tracker's `cancel` acts on the status from the last `get_status`.**
  A row cancelled right after its job was taken drops the row and lets the
  job run on. This was already true for downloads before this branch.
- **The finished-row conditions of `remove`, the remove button and
  `is_terminal` differ.** The first two are upstream's and were there
  before this branch.
- **Small items:**
  - `_ActiveJob.kind` has no reader, but 3c names it;
  - `get_record` repeats `search`'s request code, and the tracker builds a
    library row in two places: two copies each, and CLAUDE.md refactors at
    the third;
  - `prepare_regen_job` accepts `prompt` and `skip` plans, but no planned
    caller builds them.

### 3.1j. Verify

- The full suite at baseline plus the new tests. pre-commit per commit with
  `--files` (as in Phase 3), and the import smoke.
- The CLI still runs: `uv run --no-sync python -P
  scripts/regen_alignment_bundles.py --help` and `scripts/add_songs.py
  --help`.
- The isolated app (Ground rules first): the Processing page loads and a
  search download still processes. 3.1b and 3.1c touch the download path.
  Nothing queues regen jobs from the UI yet.
- The real-library manifest compare (ignore `zh_probe/`).

**Review due:** 3.1b-3.1d change the processing loop and its locking again.
Say so in the relay: a short `/code-review` of those three commits. Don't
run it unless Ken asks.

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

(Phase 7.2a replaces this page: the same rows open inline under the Library
card, from a JSON answer of the same route.)

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

## Phase 5.1: fixes from the Phase 4-5 code review

Model: Claude Opus 5.5 (review and design, 2026-10-22); executor Claude Opus
5.5.

A read-only `/code-review` of `9231bc2..641600a` (Phases 4 and 5; 2026-10-22;
three angles: correctness, simplicity, robustness) found the defects below.
Ken ruled on 2026-10-22 which ones get fixed. Each step names the defect it
fixes. Same worktree, same ground rules, same "Every phase ends the same
way". Before starting, confirm the worktree is clean at `9d28e85` plus this
plan commit.

Every file touched here is in D1. Do the steps in order: 5.1a changes the
tracker's actions and the page's Delete test, and 5.1e builds on both.

Probes (scratchpad of the review session
`65fef55e-e098-476e-9ae8-e45f76710fac`): `probes\p1_status.py` shows 5.1b and
5.1d, `probe_race.py` shows 5.1c. Before the fixes they print, in order:
`song_status RAISES UnicodeDecodeError`, `overview RAISES UnicodeDecodeError`,
`_poor_lines -> None`, `_poor_lines malformed RAISES TypeError`; and
`read in window: [('download', 'complete', 'finished')]`, `admin after queue:
[('process', '', 'active')]`, `alice after queue: []`.

### 5.1a. Tidy first

- **A failed download's two "error" fields.** Since Phase 5,
  `_on_download_error` sets `processing_status` to `error` and stamps
  `finished_at` along with `download_status`, so every test of
  `download_status == "error"` next to `processing_status == "error"` is
  redundant. Delete:
  - in `_derive_processing_status`, the `download_status == "error"` branch
    under `item.song_path is None` (a failed download has `finished_at` set
    and has already returned), leaving `processing_status = "waiting"`;
  - the `download_status == "error"` half of `PipelineItem.is_terminal` and
    of `group_of` in `_in_display_order`;
  - the `download_status === 'error'` half in the page's `statusOf`. The
    guest row's test that tells a download failure from a processing failure
    stays: it is the only reader of the difference.
- **`remove` only where there is a song to delete.** `_item_to_dict` offers
  `remove` on a download row with a song path, and on no other (a song path
  is set by `song_downloaded`, which sets `download_status` to `complete` in
  the same step, so this is the old condition minus the failed download with
  no file). The page then shows Delete song for `remove` or `delete` alone;
  drop its `row.song_path` filter and its comment. `PipelineTracker.remove`
  itself is unchanged.
- **One song check for the routes.** In `routes/song_info.py`, replace
  `_library_song` with:
  - `library_song(k, song: object) -> str | None`: `song` when it is a string
    in `k.song_manager.songs`, else None;
  - `posted_song(k) -> str | None`: `library_song` of the JSON body's
    `"song"` (None for a body that isn't a JSON object).

  `song_info` uses `library_song(k, request.args.get("song"))`; `regenerate`
  and `processing.retry_song` use `posted_song(k)` (`routes/processing.py`
  imports it). Phases 6-8 use the same two.
- **The poor-list label from its rule.** `processing.html` hardcodes "Looks
  poor (15%+ lines guessed)". The `/processing` route passes
  `poor_share=round(library_status.POOR_GUESSED_SHARE * 100)`; the label is
  `{% trans share=poor_share %}Looks poor ({{ share }}%%+ lines
  guessed){% endtrans %}` (with a variable, Jinja's i18n block needs `%%`
  for one `%`).
- **The attention route asks for tracked paths only.**
  `PipelineTracker.tracked_paths() -> set[str]`: the song paths of every row,
  finished or not, read under the lock. `/processing/attention` uses it
  instead of building the set from a whole `get_status(admin=True)`. The
  route still makes two reads (the tracker, then the database); that stays.

Tests:
- a failed download with no file offers no `remove` (admin), one with a file
  still does; existing tests that set `download_status = "error"` by hand
  also set `processing_status`, as the event does;
- `tracked_paths` holds a finished row's and a running row's paths and no
  `None`;
- the label follows the constant (patch it to 0.2: "Looks poor (20%+ lines
  guessed)", one `%`);
- the route tests for bad song bodies stay green unchanged.

Commits: `refactor(processing): one error field per failed download, Delete
only with a file, attention reads tracked paths`; `refactor(library): one
song check for the routes, the poor label from its rule`.

### 5.1b. A bundle with bad counts no longer fails a finished job

**Defect:** `PipelineTracker._poor_lines` catches errors from `song_status`
but evaluates `status.poor` after the `try`. `poor` does arithmetic on the
bundle's counts, so a bundle with a non-number count (say `"5"`) raises
`TypeError` out of the `processing_complete` handler. That reaches
`_run_job`, which reports the job as failed and sets the song's database
state to `failed`, after the pipeline had already set it to `ready`.

- Move the `return` inside the `try`.

Test: a `processing_complete` event for a song whose bundle has
`lines_with_words: "5"` leaves the row `complete`, with no `guessed` or
`line_count`, and raises nothing.

Commit: `fix(processing): a bundle with bad counts no longer fails a
finished job`.

### 5.1c. A download keeps its row when a status read lands before the queue

**Defect:** `song_downloaded` runs the tracker's handler (the row gets its
song path) and then `ProcessingManager.enqueue`. A status read in between
finds the song neither running nor waiting and calls the row `complete`,
with no `finished_at`. That makes it terminal, so `processing_queued`
doesn't find it as unfinished: it drops it and adds an ownerless `process`
row. The guest loses their row (process rows are admin-only), and its
`user` is gone. `PipelineTracker.retry` of a download row has the same
window: it puts the row back to `waiting` and clears `finished_at`, then
calls `enqueue` outside the lock.

- `_on_processing_queued`: when `_find_unfinished` finds nothing, look for a
  row of this song with `finished_at` None. Only a status read's guess can
  make such a row complete, so it is this run's row: set its
  `processing_status` back to `waiting` and add nothing. Otherwise drop the
  finished rows and add a `process` row, as today. Update the docstring.
- `_find_unfinished` keeps its meaning: a re-download of the same song has a
  new row, which must win over an older one.

Tests (real `EventSystem`, as `probe_race.py`):
- `download_queued` for Alice, `song_downloaded`, a `get_status` read, then
  the song added to `pending_jobs` and `processing_queued`: Alice's status
  has one `download` row, `mine`, group `active`; the admin status has no
  `process` row;
- `retry` of a failed download row whose `enqueue` mock does a `get_status`
  read before it adds the song to `pending_jobs` and emits
  `processing_queued`: the same row comes back as `active` with its `user`.

Commit: `fix(processing): a download keeps its row when a status read lands
before the queue`.

### 5.1d. A `.lrc` that isn't UTF-8 no longer breaks the library pages

**Defect:** `lrclib.is_skip_marker` reads the file as UTF-8 and catches only
`OSError`. A `.lrc` in another encoding (a hand-placed file) raises
`UnicodeDecodeError` out of `song_status`, so `/library/overview`, every
`/library/songs` list, and that song's Song Info and Regenerate return 500.

- `is_skip_marker` returns False for a file that isn't UTF-8 too, and logs
  a warning naming the file. Nothing new on screen: the song shows as it
  would with any other non-marker `.lrc`.

Tests: `is_skip_marker` of a cp1252 file is False; `song_status` of a
Genius song with that file returns (its LRCLIB state is not `skipped`).

Commit: `fix(library): a .lrc that isn't UTF-8 no longer breaks the library
pages`.

### 5.1e. Two page glitches

- **An open confirm closes when its action goes.** The page draws a row's
  confirm ("Cancel this job?", "Delete this song from the library?") before
  it looks at `row.actions`, so a confirm stays open after the job has
  ended, and its button posts an action the server no longer offers. In the
  page script:
  - `offers(row, act)`: whether the server's `actions` allow the confirm's
    action (`cancel`: `cancel`; `delete`: `remove` or `delete`). Delete
    song's button uses it too, so the two can't disagree;
  - `pruneState(rows)`, called by `render` before drawing: what `render`
    does today (forget the open and confirming state of rows that are
    gone), plus close a confirm whose action the row no longer offers.
- **YOU only for a named guest.** `mine` is true when the row's `user`
  equals the caller's cookie, so a guest with no name sees YOU on every
  other nameless guest's row. `mine` requires a non-empty user. The cancel
  permission (`is_owner`) is upstream's and stays as it is.

Tests: a `get_status(user="")` read of two nameless downloads gives `mine`
false on both, and a named owner still gets true. The page script has no JS
runner in the suite: add a page test in the existing style (the rendered
script has `pruneState` and `offers`, and the Delete button's test goes
through `offers`), and check the behaviour once with Deno on the page's own
functions (a confirming `cancel` row whose actions become `["dismiss"]`
loses its confirm; a confirming `delete` row with `remove` keeps it). Record
that check in the Results row; it is not committed.

Commit: `fix(processing): a confirm closes when its action goes, and YOU
only marks a named guest's rows`.

### 5.1f. Not fixed, and why (record only; don't change)

Ken's ruling, 2026-10-22:
- **Regen-lane positions while a queued song plays.** The numbers can be
  off while a waiting regen's song is on screen; they correct themselves
  when it moves on. The waiting numbers stay as they are.
- **A song path with a lone surrogate makes the page's `encodeURIComponent`
  throw.** No real filename on this library has one.
- **A double Regenerate makes an extra backup folder.** Two requests in the
  same instant both pass the busy check and both back up; the second
  enqueue is refused.
- **A stale in-flight request after an SPA revisit** can draw once into the
  new page before the next refresh.
- **The page tests read the script's text, and the page works out running
  and status again from fields the server sends.** Both stay.
- **A row can show as Done (or Ready to sing) for an instant** between
  `song_downloaded` and `processing_queued`. 5.1c keeps the row; the flash
  itself is the status derivation, recorded in 3.1i.

### 5.1g. Verify

- The full suite at baseline plus the new tests. pre-commit per commit with
  `--files`, and the import smoke.
- The two probes print the fixed outputs: `song_status`, `overview` and the
  malformed `_poor_lines` return without raising; Alice keeps her
  `download` row and there is no `process` row.
- Mutation checks on each fix, as in Phase 5's row.
- No app run: every change is covered by a unit test, a probe or the Deno
  check.

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

## Phase 6.1: fixes from the Phase 6 code review

Model: Claude Opus 5.5 (review and design, 2026-10-22); executor Claude Opus
5.5.

A read-only `/code-review` of `220ac2b..8a3b585` (Phase 6's code; 2026-10-22;
three angles: correctness, simplicity, robustness; the docs commit `9dd41c4`
out of scope) found the defects below. Ken approved this section on
2026-10-22, the new caption wording in 6.1b included. Each step names the
defect it fixes. Same worktree, same ground rules, same "Every phase ends the
same way". Before starting, confirm the worktree is clean at `9dd41c4` plus
this plan commit.

Every file touched here is in D1 (`library_status.py`, `library_tools.py`,
`routes/song_info.py`, `song_repair.html` and tests). One code commit per
step, each with its test. Do 6.1c before 6.1d: both change
`library_tools.py`'s candidate list.

The suite at `9dd41c4`: 4 failed (the baseline's four), 1949 passed, 2
skipped.

Probes (scratchpad of the review session
`65fef55e-e098-476e-9ae8-e45f76710fac`, folder `p6review\`):

- `test_dump_repair_page.py` renders the repair page for a Genius song
  through `test_library_routes`'s `env` fixture and writes the HTML to
  `$REPAIR_PAGE_OUT`. Run it from the worktree root with
  `PYTHONPATH=tests/unit` and `--rootdir=.`.
- `stale_lrclib.mjs` (Deno, `npm:jsdom@24.1.0`, the app's own
  `static/jquery-3.7.1.min.js`) drives that page: Genius hit 7, Next, an
  LRCLIB search held open, Back, hit 8, then the held answer arrives. Args:
  `<page.html> <jquery.js> asis|fix`. Before the fix, `asis` prints `search
  was for genius_id: 7`, `step 2 heading: Genius pick: Defying Gravity ·
  Idina Menzel.`, hit 7's candidate listed as `best fit`, and `send enabled:
  true`. `fix` patches the page in memory the way 6.1a does and prints only
  the None option with `send enabled: false`. (Its last line, the POST body,
  comes from jsdom's `trigger` running a handler on a disabled button; a
  browser sends nothing.)
- `probe_caption_fail.py <a scratch folder>` shows 6.1b: a yt-dlp timeout
  and an HTTP 403 both print `CaptionCheck(found=False, wpm=None,
  passed=False)`.

### 6.1a. A new Genius pick drops an LRCLIB search still in flight

`song_repair.html`: the Genius pick handler (`geniusOption`'s `change`)
clears the LRCLIB list but leaves `state.lrclibSeq` alone, so a search sent
for the previous pick still passes `seq !== state.lrclibSeq` when it
answers. It then fills step 2 with the old pick's matches, scored against
the old lyrics, with the old best fit preselected, under the new pick's
heading; Regenerate song sends the new Genius id with that match.

Fix: the handler also does `state.lrclibSeq++` (next to the reset of
`state.candidates`). Nothing else changes.

Test: a render test that the pick handler bumps `lrclibSeq` (the page tests
read the script's text, 5.1f). The real check is the Deno probe: render the
fixed page with `test_dump_repair_page.py` and run `stale_lrclib.mjs ...
asis`; it must print what `fix` printed before. Record both runs in the
Results row; the probe is not committed.

Commit: `fix(library): a new Genius pick drops the LRCLIB search still
loading`.

### 6.1b. A caption check that failed no longer says the video has no caption

`check_caption` gets `None` from `download_manual_en_subs` both when there is
no manual English caption and when yt-dlp fails (timeout, YouTube 403), so
the page says "This video has no English caption." about a video whose
caption may be fine. Telling the two apart needs a change to
`download_manual_en_subs`, whose file is not in D1, so this is a wording fix
only.

Fix: in `song_repair.html`, the `noCaption` text becomes "No usable English
caption found. If YouTube is busy, reload the page to check again." (Ken,
2026-10-22). The sparse-caption and "Could not check the caption." texts stay.

Test: a render test that the page carries the new text and not the old one.

Commit: `fix(library): the repair page doesn't claim a video has no caption
when the check failed`.

### 6.1c. One length rule, and the server writes the fit line

Two defects of the same rule:

- `LibraryTools._length_diff_s` repeats `song_info._length_gap_s` (the same
  arithmetic and docstring).
- The page script writes the fit wording again (`fitLine`: "N s longer",
  "N s shorter", "within a few s", its own `mmss`), with the 5 s threshold
  handed over as `NOTED_S`. Song Info renders its own fit text on the server.

Fix:

- `library_status.py`: a public `length_gap_s(match_s: object, video_s:
  float | None) -> int | None`, the seconds by which the LRCLIB match is
  longer than the video (negative: shorter), None when either length is
  missing or the match's length isn't a number (the `isinstance` test of
  `_length_diff_s`, since LRCLIB records come off the network).
  `LibraryTools._length_diff_s` is deleted and `lrclib_candidates` calls it;
  `song_info._length_gap_s(status)` calls it with the bundle's values (or is
  replaced by direct calls, whichever reads better).
- `routes/song_info.py`, the `lrclib_search` route: each candidate also gets
  `fit` (text) and `fit_near` (bool), and the response gets `video_length`
  (text, or None without a video length). `fit` joins with " · " the match's
  length as m:ss (`_mmss`; left out without a length) and, with a gap, either
  "within a few s" (under `_LENGTH_GAP_NOTED_S`) or `_gap_text(gap)`.
  `fit_near` is true for a gap under the threshold and false otherwise, and
  null without a gap. `video_length` is "video is m:ss". The wording is the
  page's wording today, so nothing on screen changes. `duration_diff_s` and
  `video_duration_s` stay in the JSON (they are the data the text is built
  from); the page stops reading them.
- `song_repair.html`: `fitLine` uses `candidate.fit` and `candidate.fit_near`
  (the tone stays: near `rp-good`, far `rp-bad`, null none); `#video-length`
  shows `found.video_length` (step 2 keeps it in state in place of
  `videoSeconds`). Delete `NOTED_S`, `mmss`, and the `videoIs`, `withinFew`,
  `longer` and `shorter` texts. `repair_page` stops passing
  `length_gap_noted_s`. Also delete the unused `rp-step` class on the two
  sections.

Tests: `length_gap_s` (longer, shorter, a missing or non-numeric length);
the route's `fit`, `fit_near` and `video_length` for a near, a far longer, a
far shorter and a length-less match; `test_the_length_rule_comes_from_song_info`
is replaced by a test that the route's text follows `_LENGTH_GAP_NOTED_S`
(patch it, as the poor-share label test does); the existing
`duration_diff_s` tests keep passing unchanged.

Commit: `refactor(library): one length-gap rule, and the LRCLIB fit line comes
from the server`.

### 6.1d. A repair uses the LRCLIB record its search already listed

A repair POST with `lrclib_id` fetches that record again through LRCLIB's
get-by-id endpoint, which the search didn't use. In Phase 6's live run that
endpoint answered 503 for about two minutes while search worked, and six
POSTs were refused. The server already held the full record, synced lyrics
included, when it listed the candidates.

Fix, in `LibraryTools`:

- `lrclib_candidates` remembers every record it lists, keyed by id (records
  without an id are not remembered), in a dict capped at
  `LRCLIB_CACHE_SIZE = 100` (a search returns up to about 20), oldest out,
  under a lock: the Genius cache's shape. Move the eviction into one small
  helper both caches call, so the rule exists once.
- `_genius_plan`: with `lrclib_id`, take the remembered record, else
  `lrclib.get_record` as today. The "LRCLIB didn't return that match" and "no
  synced lyrics" refusals stay for the fetched record. The client never
  supplies the record; it only names an id the server listed or can fetch.
- A restart forgets the records; the fallback covers that.

Tests: after a search, a repair queues the listed record with `get_record`
patched to raise; without a search, a repair still calls `get_record`; the
cache keeps only the last `LRCLIB_CACHE_SIZE` (patch it small, as the
Genius cache test does); the Genius cache tests pass unchanged.

Commit: `feat(library): a repair uses the LRCLIB record its search listed`.

### 6.1e. Not fixed, and why (record only; don't change)

- **A Genius outage reads as "No Genius results."** `/lyrics_search` returns
  `[]` on any failure and with no token. It is shared with the search page,
  and `routes/search.py` is not in D1.
- **A `.lrc` left over after a repair switches a song away from Genius.** It
  can't reach a run: the fill runs only on the joint route, a caption run
  takes the cue-align route, and a transcribe run has no fill. Its one effect
  is that a later Genius repair's step 2 tags that match `current`, which is
  true of the file on disk.
- **An empty LRCLIB title makes Search do nothing.** A hint would be new
  wording.
- **`caption_check` builds a caption plan only for its "no YouTube ID"
  refusal,** and **the mapped count is worked out twice per record** (once
  for the list, once inside `select_candidate`). The first keeps one
  YouTube-ID rule, the second keeps "best" on the production rule.

### 6.1f. Verify

- The full suite at baseline plus the new tests. pre-commit per commit with
  `--files`, and the import smoke.
- The Deno probe on the fixed page prints the `fix` output (6.1a).
- Mutation checks on each fix, as in Phase 6's row (6.1a's check is the
  probe: with the bump removed, `asis` lists the stale match again).
- No app run: every change is covered by a unit test, a render test or the
  Deno probe, and 6.1c's text is the page's text today.

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

## Phase 7.1: fixes from the Phase 7 code review

Model: Claude Opus 5.5 (review and design, 2026-10-23); executor Claude
Sonnet 5.5.

A read-only `/code-review` of `8b6e4a4..ecbde50` (Phase 7's code; 2026-10-23;
three angles: correctness, simplicity, robustness; the docs commit `3b863af`
out of scope) found the defects below. Ken ruled the open questions on
2026-10-23:

- a caption check that couldn't run is told apart from "no caption", is
  tried once more after a pause, and can be checked again from the preview
  (7.1a);
- a regen job with a Genius pick fails before it changes anything when
  Genius doesn't return the lyrics (7.1b).

Each step names the defect it fixes. Same worktree, same ground rules, same
"Every phase ends the same way". Before starting, confirm the worktree is
clean at `3b863af` plus this plan commit.

Files: all in D1. Two additions to D1 come with this phase (Ken,
2026-10-23): `pikaraoke/lib/youtube_dl.py`, for one change to the fork's
own `download_manual_en_subs` (`8a69fd6`) and nothing else in that file
(7.1a), and the new `pikaraoke/static/library-pages.js` (7.1e). One code
commit per step, each with its test, in order: 7.1a to 7.1e (7.1e moves
helpers that 7.1a and 7.1d edit).

The suite at `3b863af`: 4 failed (the baseline's four), 2067 passed, 2
skipped.

Probes (scratchpad of the review session
`65fef55e-e098-476e-9ae8-e45f76710fac`, folder `p7review\`; not committed):

- `test_dump_run_pages.py` renders the run pages through
  `test_library_routes`'s fixtures into `$RUN_PAGES_OUT`: a Reset all while
  checking (`preview_checking.html`), a Reprocess all with nothing picked
  (`picks_none.html`, `preview_none.html`), one Genius pick whose title and
  artist are markup (`picks_one.html`), and every pick made
  (`preview_allpicked.html`, `picks_allpicked.html`,
  `status_allpicked.json`). Run it from the worktree root with
  `PYTHONPATH=tests/unit` and `--rootdir` set to the probe folder.
- `run_pages.mjs` (Deno, `npm:jsdom@24.1.0`, the app's own
  `static/jquery-3.7.1.min.js`) loads a dumped page with every request held;
  `pick_probe.mjs` and `preview_probe.mjs` drive the pick page and the
  preview. Args: `<folder> <jquery.js>`. Anything about a disabled button
  needs a native `click()`, as `preview_probe.mjs` does: jQuery's `trigger`
  runs a handler on a disabled button, which a browser never does. At
  `3b863af` they print, among the rest:
  - `3. all picked: go: Start picks (3 of 3 done) | 'queued only after the
    last pick' shown: true`, then `3. tap go -> ["Not implemented:
    navigation (except hash changes)"] | posts: 0` (7.1d);
  - `3. posts so far: 1` after Transcribe was tapped on another song while a
    pick saved, then `3. after the save answer: picker open: 0` (7.1d);
  - `4. Change hits: [ "Defying GravitycurrentKristin Chenoweth", "Defying
    GravityIdina Menzel" ]` for a song picked as the second hit (7.1d).

  After 7.1e, `run_pages.mjs` must also load the new shared script before
  the page script.

### 7.1a. A caption check that couldn't run is not "no caption"

Defect: `download_manual_en_subs` returns None both when the video has no
manual English caption and when yt-dlp fails (a timeout, YouTube refusing,
yt-dlp missing), and `_measure_caption` turns any exception into the same
answer. The run saves it as a finished check that found nothing: the song
needs a pick and is never checked again, a restart included, and a pick
can't send it back to its caption. A Reset all makes one YouTube call per
song back to back, which is when YouTube starts refusing. The Phase 7 row
lists this as 6.1b's limit; in a run it costs more, since the only way back
is to discard the run with its picks.

Fix:

- `youtube_dl.py`: a new `CaptionDownloadFailed(Exception)`.
  `download_manual_en_subs` raises it, with the reason, where it now logs
  and returns None: a timeout, a yt-dlp that can't be run, a non-zero exit.
  It still returns None when yt-dlp ran and wrote no English SRT. Docstring
  to match.
- `library_regen.py`:
  - `fetch_caption` catches it, logs it, and goes on as it does for None
    today (the plan's fallback), so a regen job behaves exactly as before.
  - `CaptionCheck` gets `failed: bool = False`; `check_caption` catches the
    exception and returns `CaptionCheck(found=False, wpm=None,
    passed=False, failed=True)`.
- `library_tools.py`:
  - `_measure_caption`'s catch-all returns `failed=True` too: the check
    couldn't run, and the traceback stays in the log. The `except
    Exception` stays, since it guards the thread and the song can now be
    checked again.
  - `_check_captions`: after a failed check, wait `CAPTION_RETRY_PAUSE_S =
    30` and check that song once more; store the second answer, whatever it
    is, and go on to the next song. The wait is outside the state lock and
    ends at once when the run closes: `_Run` gets a `closed`
    `threading.Event` (not saved), which `discard_run` and `queue_run` set;
    the thread returns when it is set, storing nothing.
  - `recheck_captions() -> int`: under the state lock, refuses while
    captions are being checked ("Captions are still being checked.") or
    when no song without a pick has a failed check ("No caption check
    failed."). Otherwise it clears `check` on every song whose check failed
    and that has no pick, saves, starts the checker, and returns how many.
  - `run_view` adds `failed`: the songs with a failed check and no pick. A
    failed song's group stays `needs_pick` (it can be picked as today), and
    its `caption` carries `failed: true`.
  - A state file from before the fix has no `failed` key; such a check
    reads as a finished one, as it does today.
- `routes/library.py`: `POST /library/run/recheck` (admin), answering with
  the run as `/library/run/pick` does; a `RegenError` is a 400.
- `library_run.html`: when not checking and `failed > 0`, a box "N caption
  checks failed: YouTube didn't answer." (one and many forms, as
  `queueOne`/`queueMany`) with a "Check again" button. One tap posts the
  recheck, takes the answered run, renders, and starts the poll. A
  needs-pick row whose check failed says "Caption check failed: YouTube
  didn't answer." `pick_pass.html`: the same line on such a row.

Live check (network only, no app): call `download_manual_en_subs` into a
scratch temp folder for:

- a scratch-library video whose caption passed in Phase 7 (Queen or
  Backstreet Boys): returns a path;
- a scratch-library video with no manual English caption: returns None
  without raising. Find one by trying the scratch library's other videos;
  only their file names are read;
- a video id that doesn't exist (`aaaaaaaaaaa`): raises.

Record each call's yt-dlp exit code and last stderr line. **STOP if** the
no-caption video raises (yt-dlp exits non-zero for "no caption", so the exit
code can't tell the two apart) or the missing video returns None.

Tests:

- The download, with `subprocess.run` mocked: a timeout, a missing yt-dlp
  and a non-zero exit raise; a zero exit with no file returns None.
- `check_caption` on a failure gives `failed=True`; `fetch_caption` on a
  failure falls back as it does for None; a crashing check gives `failed`.
- The checker, with the pause patched:
  - a failed check is tried once more (two calls), and a second failure is
    stored as failed;
  - a pass on the second try is stored as a pass;
  - a discard during the pause stores nothing, and the thread ends at once
    (patch the pause to several seconds and join with a short timeout).
- `recheck_captions` clears only failed songs without a pick, refuses while
  checking or with none, and starts the checker; the view's `failed`; a
  restart keeps a failed check, and Check again is still offered.
- The route is admin-only and answers 400 on a refusal; render tests for
  the box and the row line.

Commit: `fix(library): a caption check that couldn't run is tried again and
can be checked again`.

### 7.1b. A Genius pick that Genius doesn't return fails the job before anything changes

Defect: a regen job with a `sidecar` plan (a run's Genius pick or Keep, or
Repair's Genius pick) fetches the lyrics inside the pipeline. When Genius
doesn't answer, the fetch stage falls back to a caption on disk, else
transcribes; `finish_regen_job` then deletes the old bundle and the job
reads complete. Repair checks Genius when it queues; a bulk run doesn't,
and its jobs run hours after queueing anyway. A Reset all with Keep for
every song fetches Genius once per song (D5: a Keep is a fresh pick).

Fix (Ken, 2026-10-23): first thing in `prepare_regen_job`, before the reset
wipe and the caption fetch, a `sidecar` plan calls
`genius.fetch_song(plan.genius_id)`. On `GeniusUnavailable` it raises
`RegenError("Genius didn't return this song's lyrics, so nothing was
changed. Retry when Genius answers.")`, and the job fails like any job that
can't start: the row shows the error and Retry, `put_back_lrc` runs, and no
file was touched.

- The fetch inside the pipeline stays as it is. It fetches again seconds
  later, and a failure in that window still falls back as today; record
  that in the row as seen, not changed.
- The CLI is unchanged: it calls `prepare_lyrics`, not
  `prepare_regen_job`.
- Repair's own check when it queues stays: it answers on the page at once.

Tests: a reset job with a `sidecar` plan and `fetch_song` raising raises
`RegenError`, `clear_output_folders` is never called (the song's files are
all still there) and the `.lrc` is unchanged; with `fetch_song` answering,
the job prepares as before; a plan of another kind doesn't call Genius.
Through the processing manager (the regen-lane fixtures): the failing job
ends as an error with the message, and the next job runs.

Commit: `fix(library): a regen job stops before any change when Genius
doesn't return its pick`.

### 7.1c. A run read back at start belongs to this library

Defect: `_load_run` keeps a saved song if its file exists, wherever it is,
and `enqueue_regen` takes any path. With the same app data and a different
`--download-path`, a run left open comes back over the old library's songs.
Queueing it backs up the new library (`backup_text_folders(self._folder)`)
and resets the old library's songs with no backup.

Fix: `_load_run` keeps a saved song only when it is a file directly in
`self._folder`. Compare the parent folders with
`os.path.normcase(os.path.abspath(...))`, so another spelling of the same
folder still matches. One log line counts the songs dropped.

Tests: a saved run whose songs are in another folder is not restored (with
no songs left, no run); a run with songs in both keeps only this library's;
the same folder spelled with a trailing separator or a `..` is kept.

Commit: `fix(library): a run read back at start keeps only this library's
songs`.

### 7.1d. The pages once every pick is made, and while a pick saves

Three page defects (the probe output above):

- With every pick made, the preview still says "Start picks (k of k done)"
  and "Songs are queued only after the last pick.", and its button opens the
  pick page instead of queueing. The Processing banner says "k of k
  picked." and never "ready to queue." Both pages test `to_pick > 0`.
- A pick tapped while another pick saves is dropped without a word
  (`savePick`'s `if (state.sending) return;`), and the save's answer closes
  the picker the admin opened in the meantime (`state.open = null`).
- Change on a song picked from Genius: the list tags the bundle's song
  `current`, but the admin's own pick in this run is neither tagged nor
  selected.

Fix:

- `library_run.html`: picks are left when `to_pick - picked > 0`. That
  decides the button's text, the after-picks note, and what a tap does (the
  pick page, or queue). `processing.html`'s `renderRun`: `runPicks` while
  picks are left, else `runReady`.
- `pick_pass.html`:
  - While `state.sending`, the picker's Transcribe, Skip song and Use pick
    and each row's Keep are disabled (the render reads `state.sending`).
  - A save's answer closes the picker only if it is still that song's
    (`state.open === song.song`); Keep all still closes it.
  - A hit whose id is the song's Genius pick in this run (`pick.kind ===
    'genius'`) gets a "your pick" tag (new text) next to `current`, which
    stays the bundle's song. Nothing is preselected.

Tests: render tests on the script text, as the page tests do (5.1f). The
real check is the probes: render the fixed pages with
`test_dump_run_pages.py` and rerun both. Switch `pick_probe.mjs`'s
Transcribe tap during the save to a native click. They must print:

- `3. all picked: go: Queue 3 songs`, with the note hidden, and a tap that
  posts the queue;
- no post for the Transcribe tap during the save, and the No Id picker
  still open after the save answers;
- `your pick` on the second hit after Change.

Record the before (above) and after in the row.

Commit: `fix(library): the run pages once every pick is made and while a
pick saves`.

### 7.1e. Cleanup: one caption-check rule, one copy of the page helpers

- `_Run.needs_check` repeats `undecided_group`'s rules (the mode, a source
  to replay, no lyrics, a YouTube ID). They agree on every song a run can
  hold today, but an edit to one alone could leave a song in `checking` for
  good: never checked, and queueing refused. Derive it: a song needs a
  check when its group with no check made is `checking`
  (`undecided_group(dataclasses.replace(entry, check=None)) ==
  "checking"`). The D5 table tests must pass unchanged.
- `fill`, `el` and `errorOf` are copied in `song_repair.html`,
  `library_run.html` and `pick_pass.html`, and `fill` in `processing.html`
  too: four copies, past CLAUDE.md's third-copy rule.
  - Move them to `pikaraoke/static/library-pages.js`, under one global
    object (`libraryPages`). Load it with a `<script src>` in each page's
    `scripts` block, before the page script; each page script takes the
    names from it.
  - Check first that the copies are identical; a difference is a STOP.
  - The SPA loads a page's external scripts once, before it runs the inline
    ones (`spa-navigation.js`, `loadExternalResources`).
  - The page tests that look for `.html(` and `.innerHTML` in the page
    script read the new file too.

Tests: the existing suite; a render test per page that the script tag is
there and the three helpers aren't defined inline. The jsdom harness loads
the file.

Commit: `refactor(library): one caption-check rule, and the library pages
share their helpers`.

### 7.1f. Not fixed, and why (record only; don't change)

- **`open_run` and `_load_run` read each bundle twice** (once for the
  status, once for the reuse test), and `open_run` holds the run lock while
  it scans. It's cheap at this library's size.
- **The whole-folder backup holds the run lock while it copies.** The
  backup is D5's rule; the lock is held for a moment.
- **A restart loses the queued jobs, and the run is closed by then** (D2;
  the Phase 7 row).
- **A run doesn't see a Repair made while it is open, and the run's older
  pick wins at queue time** (the Phase 7 row's first "seen" item).
- **The repair page's caption text (6.1b) stays.** Song Info's caption
  check now answers `failed`, but the page's one wording covers both cases,
  and a new wording is Ken's call.

### 7.1g. Verify

- The full suite at baseline plus the new tests; pre-commit per commit with
  `--files`; the import smoke (`youtube_dl`, `library_regen`,
  `library_tools`, `routes.library`, `karaoke`, `app`).
- Mutation checks on each fix, as in the Phase 7 row:
  - 7.1a: no second try; the pause not ended by a discard; a failed check
    stored as a finished one; the recheck clearing picked songs; `failed`
    miscounted; the download returning None on a failure.
  - 7.1b: the Genius check after the wipe; the check skipped.
  - 7.1c: the folder test removed.
  - 7.1d: through the probes.
  - 7.1e: the derived rule inverted.
- 7.1a's live yt-dlp check, above.
- One isolated app run, to look only: nothing is queued. Check the Ground
  rules first. Hash the scratch library before and after; the two must
  match.
  - Library tools → Reset all → let the checks finish → pick every song
    (Keep, Transcribe, Skip song) → back to the preview: "Queue N songs",
    and the banner says "ready to queue" → Discard.
  - Song Info → Repair lyrics: the Genius search and the caption line still
    work (7.1e's shared file), reached both through the SPA and by a reload.
  - Headless Edge, as in the Phase 7 row, is fine. A failed check can't be
    forced live; the unit tests cover it.
- The `### Phase 7.1` Results row (raw facts) and the status block, in
  their own docs(plan) commit.

## Phase 7.2: fixes from Ken's live check of Phases 4-7.1

Model: Claude Opus 5.5 (design, 2026-10-23); executor Claude Sonnet 5.5.

Ken's live pass on 2026-10-23 (the `### Phase 7 checks` Results row) passed
every box. Ken ruled on 2026-10-23 that two of its findings are fixed on this
branch before Phase 8:

- the four Library card lists open inline on the Library tools tab, instead
  of on their own page, which has no way back (7.2a);
- the pipeline log stops saying an LRCLIB file is "available for fill" when
  that file is the skip marker (7.2b).

The pass's other two findings go elsewhere (D9): uploading hand-checked
lyrics is a later plan, and Delete song / Rename leaving files behind is
fixed off `dev`.

Same worktree, same ground rules, same "Every phase ends the same way".
Before starting, confirm the worktree is clean at `01d9475` plus this plan
commit. One code commit per step, each with its tests: 7.2a, then 7.2b.

Files: all in D1 except one addition that comes with this phase (Ken,
2026-10-23): `pikaraoke/pipeline/stages/lyrics_fetch.py` (fork-owned), for
the one log call in `_resolve_lrclib` and nothing else (7.2b).
`library_songs.html` leaves D1 (7.2a deletes it).

The suite at `01d9475`: the Phase 7.1 row's count (4 failed, the baseline's
four; 2100 passed). Rerun it first and use what it prints as the baseline.

### 7.2a. The four lists open inline on the Library tools tab

Today each row of the Library card (`processing.html`, `#pr-tools`) is a
link to `GET /library/songs?list=<name>`, which renders
`library_songs.html` as a page of its own. That page has no back link.

- **Server** (`routes/library.py`): `GET /library/songs?list=<name>` answers
  JSON instead of a page, the way `/library/overview` does: a guest gets
  403 `{"success": false, "error": ...}` (no redirect, no flash); an unknown
  or missing list gets 400 through `_error`; otherwise
  `{"success": true, "rows": [{"name", "subline", "info_url"}, ...]}`, in
  `songs_in_list`'s order. `name` and `subline` are what the page shows
  today (`filename_from_path`, `_subline`). `info_url` is the Song Info
  link, built in Python the way the deleted template built it (the
  `url_for('song_info.song_info')` path, `?song=`, and `quote` of the path
  encoded with `utf-8` and `surrogateescape`), so the page never escapes a
  path itself. Delete `_list_title` (nothing else uses it; the card row's
  own label is the title), `library_songs.html`, and the route's
  `render_template` and `get_site_name` imports if nothing else uses them.
- **Page** (`processing.html`): each of the four `a.pr-link` rows becomes a
  `<button type="button">` with `data-list="<name>"`, `aria-expanded`, the
  same label and count tag, and a chevron that turns when open. Under each
  sits an empty, hidden list box. Style the button like `.pr-link` (full
  width, left-aligned, no border or background of its own, the inherited
  font and colour), with a 48 px tap height as today.
  - Tapping a closed row closes any other open list, opens this one with
    "Loading…", and fetches its JSON. Tapping an open row closes it. One
    list is open at a time, so a long All songs list never pushes the
    Regenerate card far down.
  - The answer fills the box: each song is a link (`no-spa`, as today) to
    its `info_url`, showing the name and the muted subline, at least 44 px
    tall. An empty answer shows "No songs in this list." A failed fetch
    shows the server's `error`, or "Couldn't load this list." when there is
    none.
  - An answer that arrives after its list was closed, or after another
    list was opened, is dropped: a sequence number bumped on every open and
    close, as `song_repair.html`'s `lrclibSeq` does (6.1a).
  - Build every row with jQuery `.text()` (or the shared `el` helper), never
    an HTML string: song names are file names.
  - Showing the Library tools tab closes any open list, so a list always
    comes from a fresh fetch beside the counts that `loadOverview` just
    fetched.
  - The footnote under the card becomes "Tap a list to show its songs, then
    a song for its Song Info."
- **Tests:**
  - `test_library_routes.py`: the list tests that read the page become JSON
    tests: each list's rows and sublines (the current assertions, read from
    `rows`); an empty list gives `rows: []`; an unknown or missing list is
    400; a guest gets 403 JSON. A song whose name has a space, `&`, `#`, `%`
    and a non-ASCII character (no `?`: Windows refuses it in a file name):
    its `info_url`, requested with the test
    client, opens that song's Song Info (200, the song's name in the page).
  - `test_processing_page.py`: the admin page has four `data-list` buttons
    and no `/library/songs` link.
  - A Deno/jsdom probe of the Library tools tab, in the 7.1 style (the
    rendered page, requests held): open a list and its rows appear; open a
    second and the first closes; tap the open one and it closes; an answer
    for a list that was closed in the meantime renders nothing; a name with
    markup in it shows as text; an empty answer shows the empty text; a
    failed answer shows the error.

Commit: `feat(processing): the Library card's song lists open inline on the tab`.

### 7.2b. The log names the LRCLIB skip as a skip

`LyricsFetchStage._resolve_lrclib` logs `LRCLIB: variant available for fill
(<file>)` whenever `ensure_lrc` returns a path. Since Phase 2A that path can
be the skip marker, which `ensure_lrc` returns as is. The live pass logged
that line for Defying Gravity's Repair with None and for its Reset, while
the bundle showed no fill.

- When the returned path is a skip marker (`lrclib.is_skip_marker`), log
  `LRCLIB: skipped by the admin's choice (<file>), no fill` at info instead.
  Every other branch and line stays as it is.
- **Test** (`test_lyrics_fetch.py`, `caplog`): with a skip marker on disk the
  skip line is logged and the "available" line isn't; with a real `.lrc` on
  disk the "available" line is logged as before.

Commit: `fix(lyrics): the log names an LRCLIB skip as a skip, not a fill source`.

### 7.2c. Verify

- The full suite against the baseline above plus the new tests; pre-commit
  per commit with `--files`; the import smoke (`routes.library`,
  `pipeline.stages.lyrics_fetch`, `karaoke`, `app`).
- Mutation checks: 7.2a's dropped-answer counter removed, a second open
  list not closing the first, and `info_url` built without `quote`; 7.2b's
  marker test inverted. Each must fail a test or the probe.
- One isolated app run, to look only: nothing is queued. Check the Ground
  rules first. Hash the scratch library before and after; the two must
  match. Headless Edge at 390 px, as in the Phase 7 row, is fine: on the
  Library tools tab, open each of the four lists in turn (each list's row
  count matches its count tag; Looks poor reads Defying Gravity "38 of 89
  lines guessed" and Jay Chou "26 of 42 lines guessed"), open a song
  from one, come back with the browser's back, and the tab is there with the
  lists closed. Screenshot one open list.
- The `### Phase 7.2` Results row (raw facts) and the status block, in their
  own docs(plan) commit.

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

## Phase 8.1: fixes from the Phase 8 code review

Model: Claude Opus 5.5 (review and design, 2026-10-23); executor Claude
Sonnet 5.5.

A read-only `/code-review` of `1a26b68` and `3d26811` (Phase 8's code;
2026-10-23; three angles: correctness, simplicity, robustness; the docs
commit `fd38a1b` out of scope) found the defects below. Ken asked on
2026-10-23 for the review's recommended fixes to be written up: 8.1a-8.1e.
The rest of what the review found is in 8.1f, not fixed, each with its
reason.

Each step names the defect it fixes. Same worktree, same ground rules, same
"Every phase ends the same way". Before starting, confirm the worktree is
clean at `fd38a1b` plus this plan commit.

Files: all in D1 (`library_tools.py`, `library_regen.py`,
`pipeline_tracker.py`, `routes/library.py`, `routes/processing.py`,
`processing.html`, `playlist.html`, `scripts/add_songs.py`, and tests). No
additions to D1. One code commit per step, each with its tests, in order:
8.1a to 8.1e (8.1d moves the code 8.1a guards).

The suite at `fd38a1b`: 4 failed (the baseline's four), 2243 passed, 2
skipped. Rerun it first and use what it prints as the baseline.

Probes (scratchpad of the review session
`a85d9ebe-ab3e-44a5-b6f3-45382ebad848`; not committed; run from the worktree
root with `uv run --no-sync python -P`):

- `finder_correctness\probe_race.py` (no args): a status read during the
  caption check, with the real tracker and `EventSystem`. At `fd38a1b` it
  prints `read during gate: ['complete']`, then `after needs_pick: status
  complete group finished actions ['remove', 'dismiss', 'song_info',
  'enqueue']` (8.1b).
- `finder_robustness\probe1.py <empty scratch folder>`: `LibraryTools` with
  a real `EventSystem` and mocked managers. At `fd38a1b` it prints, among
  the rest:
  - `P1 raised UnicodeDecodeError ... | enqueue called: False | later
    handler ran: False` (8.1a);
  - `P2 second pick refused: That song already has a pick.` after a pending
    cancel (8.1c);
  - `P3 enqueue calls (busy song): 1` (8.1c).

  `probe2.py` shows `srt.parse` raising `OverflowError` on an out-of-range
  timestamp (8.1a).

Record each probe's before (above) and after in the row.

### 8.1a. A caption that can't be read no longer drops the download

Defect: `on_song_downloaded` runs inside the download worker's
`song_downloaded` dispatch, and `EventSystem.emit` doesn't guard its
handlers. `_pick_reason` catches only `OSError` from
`gate_on_disk_caption`, and `_srt_word_count` only `OSError` and
`srt.SRTParseError`. A caption that isn't UTF-8 (`UnicodeDecodeError`, a
`ValueError`) or that has an out-of-range timestamp (`OverflowError` from
`srt.parse`) escapes. Then:

- the song is neither queued nor listed;
- `_execute_download` unwinds before `queue_manager.enqueue`, so a
  "download and queue" never reaches the playback queue;
- through `add_playlist`, the request answers 500 partway, after some
  downloads were queued.

The handler it replaced (`processing_manager.enqueue`) read no caption. The
likeliest trigger is the playlist "not processed" path: older songs can
carry hand-placed captions.

Fix:

- `library_regen.py` `_srt_word_count`: catch `(OSError, ValueError,
  OverflowError, srt.SRTParseError)`. A caption that can't be read can't be
  measured, and the gate already passes a caption it can't measure
  (`_caption_passes`). Never delete it: it may be the admin's own file.
- `library_tools.py` `on_song_downloaded`: the check (`_pick_reason`) runs
  under `except Exception`, which logs with the traceback
  (`logger.exception`, naming the song) and queues the song, as the app did
  before Phase 8. Remove `_pick_reason`'s own `OSError` catch: the one
  guard covers it. The `except Exception` is the handler's boundary, as
  `_measure_caption`'s is for the checker thread (7.1a): anything that
  escapes it loses the playback queue add too.

Tests:

- `_srt_word_count` on a latin-1 caption and on one with an out-of-range
  timestamp returns None and logs; `gate_on_disk_caption` on such a caption
  passes and keeps the file.
- `on_song_downloaded` with `gate_on_disk_caption` patched to raise
  `RuntimeError`: the song is queued, nothing is listed, and a second
  `song_downloaded` handler registered after it still runs.
- `add_playlist` with an unprocessed song whose check raises: the request
  answers 200, and the next song in the list is still taken.

Commit: `fix(library): a caption that can't be read no longer drops the
download`.

### 8.1b. A status read during the caption check no longer hides the pick

Defect: the tracker gives a download's row its song path on
`song_downloaded`; `LibraryTools` then runs the check. A status read in
between (the 250 ms push refresh, the 10 s poll, another viewer) finds the
song neither running nor waiting and derives the row `complete` with no
`finished_at`. `_on_needs_pick` looks only for an unfinished row, finds
none, and changes nothing:

- the admin's row reads Done, in Finished, with no Pick lyrics;
- `attention_rows` leaves the song out, because it has a row;
- a guest sees Done and Enqueue for a song never processed.

The window is short with no caption and longer with a sparse one (an
ffprobe call first). `_on_processing_queued` already handles the same race
(5.1c, `called_complete`); `_on_needs_pick` doesn't.

Fix (`pipeline_tracker.py`):

- Move `_on_processing_queued`'s `called_complete` lookup into a helper,
  `_find_called_complete(song_path)` (caller holds `_lock`): the row for
  the song derived `complete` with no `finished_at`.
  `_on_processing_queued` uses it, unchanged in behaviour.
- `_on_needs_pick`: when there is no unfinished row, it takes the row
  `_find_called_complete` returns and sets it to `needs_pick` (phase None).
  With neither, it changes nothing, as now.

Tests (`test_processing_routes.py`, the tracker `TestNeedsPick` class, real
`EventSystem`):

- the probe's sequence: download queued, `song_downloaded`, a `get_status`
  read, then `needs_pick`. The admin's row is `needs_pick`, in Attention,
  with `pick`; the guest's row is `needs_pick` in Active;
- a row stamped complete by `processing_complete` (it has `finished_at`)
  is not touched by a later `needs_pick`;
- the 5.1c tests pass unchanged.

Commit: `fix(processing): a status read during the caption check no longer
hides the pick`.

### 8.1c. Whether a listed song is queued comes from the queue

Defect: the Attention list asks the processing manager whether a listed
song is busy, but the pick page and `pick_lyrics` use `_NeedsPick.picked`,
which three handlers keep up (`_unpick`, `_on_processing_error`, the
`processing_cancelled` subscription). The two disagree:

- Cancelling a picked song's job while it waits (`tracker.cancel` →
  `cancel_pending`) emits no event, so `picked` stays True. The pick page
  shows "Picked · processing", its row opens no picker, and a pick answers
  "That song already has a pick." until a restart. Attention offers Pick
  lyrics meanwhile. This hits songs with no download row: songs listed
  before a restart, and a playlist's unprocessed songs. A download row's
  cancel deletes the song, so `song_deleted` clears it.
- `pick_lyrics` doesn't check whether the song is already waiting or
  running, and `ProcessingManager.enqueue` doesn't either. After a picked
  song fails, Retry on its Jobs row plus a new pick queues it twice: two
  full GPU runs. `routes/processing.retry_song` refuses a busy song; the
  pick doesn't.

Fix (`library_tools.py`): busy means `is_busy`, everywhere.

- Replace `picked` with `picking: bool = False` (not saved): set under the
  state lock when a pick starts, cleared in a `finally` once
  `processing_manager.enqueue` has returned or the pick has failed. It only
  stops a second request for the same song during those few
  milliseconds. Once `enqueue` returns, the song is in `pending_jobs`, so
  `is_busy` takes over.
- `pick_lyrics`, under the state lock: no entry → "That song isn't waiting
  for a pick." (as now); `picking` or `is_busy` → "That song is already
  waiting or processing." (new text, replacing "That song already has a
  pick."). `write_choice` and `enqueue` run outside the lock, as now.
- `needs_pick_view`: a song is picked when `picking` or `is_busy`. `pick`
  and the `picked` count follow from that.
- Delete `_unpick`, `_on_processing_error` and the `processing_error` and
  `processing_cancelled` subscriptions. A job that fails or is cancelled
  leaves the song not busy, so it can be picked again (the Phase 8 row's
  call 2, now covering a cancel while waiting too).
- `attention_rows` already uses `is_busy`; it is unchanged.

Tests (`test_library_tools.py`):

- A song picked, then its job cancelled while waiting (`pending_jobs`
  emptied, no event): the view shows it to pick, and a new pick is taken.
- A song busy for any reason (a Retry, a regen): the view shows it as
  picked, and a pick is refused with the new text, with no `enqueue` and
  no `write_choice`.
- A second pick while the first is between its check and `enqueue`
  (`write_choice` patched to call `pick_lyrics` again for the same song):
  the inner call is refused, and `enqueue` runs once.
- A failed `write_choice` leaves the song pickable.
- The existing pick, failure and restart tests, with `picked` read through
  the view instead of the entry.

Commit: `fix(library): whether a listed song is queued comes from the
queue`.

### 8.1d. The playlist page and its add agree on what will be processed

Two defects:

- `check_playlist` calls a song `not_processed` when it is in the library
  and `file_status` says so. `_is_unprocessed`, which `add_playlist` uses,
  also needs it idle and not listed. The page shows a busy or listed song
  under "In library, not processed", counts it in "Process M", and the add
  then drops it silently. The Phase 8 row shows this: a re-check gave
  `not_processed: 4`, and adding them gave `processing: 0`.
- `add_playlist` counts every unprocessed song it sends through the check
  as "sent to processing", including the songs the check lists for a pick.
  With the Phase 8 playlist (no manual captions), "2 songs sent to
  processing." was flashed for two songs that went to Attention.

Fix:

- `library_tools.py`:
  - Split `on_song_downloaded`: the handler takes the song's source from
    `_playlist_ids` (as now) and calls `_check_download(song_path, source)
    -> bool`. That holds today's body with 8.1a's guard, and returns True
    when it queued the song, False when it listed it. `add_playlist` calls
    `_check_download(song_path, "playlist")` directly and no longer adds
    unprocessed songs' ids to `_playlist_ids`. The set is then only for
    downloads that land later.
  - `_is_unprocessed(song_path)` is the one rule. `check_playlist` uses it
    for a song in the library that `file_status` calls not processed:
    True → `not_processed`, False → a new status `waiting` (busy or
    listed). A `waiting` video carries no `song`. Drop
    `_is_unprocessed`'s `is_video` test: `file_status` returns
    `NOT_PROCESSED` only for a video extension (`VIDEO_EXTS`), so it adds
    nothing.
  - `add_playlist` returns `{"downloads", "processing", "listed"}`:
    `processing` counts songs `_check_download` queued, `listed` the ones
    it listed.
- `routes/library.py` `playlist_add`: the flash keeps its two parts for
  `downloads` and `processing`, and adds a third for `listed`: "%(n)d song
  needs a lyrics pick." / "%(n)d songs need a lyrics pick." (`ngettext`;
  new text). The warning flash is shown only when all three are zero.
- `playlist.html`: `waiting` videos get a section of their own after "In
  library, not processed": "Already waiting (%(n)s)", with the note
  "Queued for processing or waiting for a lyrics pick." (new text). No box,
  no tag pill, and not counted in M.

Tests:

- `check_playlist`: a song in the library that is busy, and one that is
  listed, come back `waiting` with no `song`; an idle unlisted one is
  `not_processed`, as now.
- `add_playlist`: one unprocessed song whose check queues and one whose
  check lists give `processing: 1, listed: 1`. The listed one's entry has
  source `playlist`, and `_playlist_ids` is empty afterwards.
- `on_song_downloaded` for an id queued by `add_playlist` still lists with
  source `playlist` (`TestPlaylistSource` unchanged).
- Route: the flash for each mix of the three counts, and the warning only
  at all zero.
- Render: the `waiting` section text is in the script, and M is counted
  from `not_processed` only.

Commit: `fix(library): the playlist page and its add agree on what will be
processed`.

### 8.1e. Cleanup: the needs-a-pick words and "not processed" once each

- The source and reason words ("Playlist", "Download", "no caption",
  "caption too sparse") are in `routes/library.py` `_needs_pick_json` and
  again in `processing.html`'s `T.sources`/`T.reasons`. A new reason added
  to one fails differently in each: a `KeyError` in the route, the raw key
  on the page.
  - Word them once in `routes/library.py`, as `needs_pick_subline(source,
    reason) -> str` ("<source> · <reason>"), used by `_needs_pick_json`.
  - `routes/processing.py`'s attention route adds `subline` to each
    `needs_pick` row from it.
  - `processing.html`'s `subline` shows `row.subline` for such a row, and
    `T.sources` and `T.reasons` go.
- `scripts/add_songs.py` still writes `"in library, not processed"` itself
  (line 205, and the comment at line 69), so 3d26811's "one definition"
  isn't met. It imports `NOT_PROCESSED` from `library_links` and uses it at
  both.

Tests: the existing suite; the attention route's needs-pick row carries the
worded `subline` (both sources, both reasons); the page script no longer
holds `sources:` or `reasons:`; `add_songs`'s own tests pass unchanged.

Commit: `refactor(library): the needs-a-pick words and "not processed" have
one definition each`.

### 8.1f. Not fixed, and why (record only; don't change)

- **A listed song's saved path keeps the spelling it was saved with.** If
  the library folder is given differently between starts (`D:\lib` vs
  `D:\lib/`), a deleted song can stay listed, and a pick queues a path the
  library doesn't know. The library scan compares paths as strings, so on
  such a start the library itself re-spells every song (it reads them as
  moved); every path-keyed record in the app shares this, and the run
  handles it only at queue time. Not seen live.
- **A playlist download that fails or is cancelled leaves its id in
  `_playlist_ids`** until the session ends. A later plain download of the
  same video is then listed with the source "Playlist". The label is the
  only harm, and the set is tiny.
- **Renaming a listed song leaves the old path listed**, and a pick of it
  fails each time. This is the same gap as Delete song/Rename leaving
  files behind, which Ken ruled 2026-10-23 goes to its own branch off
  `dev` (D9).
- **Starting the app on another library drops the first library's list**
  for good, as 7.1c drops a run's songs from another library. Back on the
  first library its songs show as plain Unfinished, and Retry processes
  them without asking for a pick.
- **Two playlist adds from two tabs at once can both queue the same
  song.** The page's sending flag covers one tab. The result is a
  duplicate job, not lost or changed files.
- **Retry on a failed listed song runs it without its pick.** The lyrics
  stage deletes the choice file when it uses it, so a job that failed
  after that point retries from the caption or transcribes. Retry is the
  admin's own choice; the pick page offers the pick again beside it.
- **Simplicity items left as they are:** the int-not-bool Genius id check
  is written three times (`_choice_for`, `_valid_pick`, `routes/song_info.py`),
  two lines each; `playlist_add` checks the body is a dict before the tool
  does; the watch URL is built in a third place, and the waiting-download
  check compares URL strings; the playlist page keeps its own link box and
  Check button (the Phase 8 row's call 5; Ken's Phase 8 check decides);
  the route tests repeat five of the tool's playlist message cases.

### 8.1g. Verify

- The full suite against the baseline plus the new tests; pre-commit per
  commit with `--files`; the import smoke (`library_regen`,
  `library_tools`, `pipeline_tracker`, `routes.library`,
  `routes.processing`, `karaoke`, `app`, and `scripts/add_songs.py --help`).
- The three probes, after: `probe_race.py` prints `needs_pick` in group
  attention with `pick`; `probe1.py` P1 queues the song and the later
  handler runs, P2 takes the second pick, and P3 refuses the busy song's
  pick with no `enqueue`. The probes call `_unpick` or read `picked`, so
  adjust them to the 8.1c names and record the change.
- Mutation checks, each must fail a test: 8.1a the guard removed, and the
  word-count catch narrowed back; 8.1b the `_find_called_complete`
  fallback removed from `_on_needs_pick`; 8.1c the `is_busy` test removed
  from `pick_lyrics`, and `picking` never cleared; 8.1d `check_playlist`
  back on `file_status` alone, and `listed` counted as `processing`.
- One isolated app run, to look only: nothing is queued or downloaded.
  Check the Ground rules first. Use `C:\temp\p8\appdata` (the short path);
  hash the scratch library before and after, and the two must match.
  - Before starting, write one needs-a-pick entry into that app data's
    `library_tools\state.json` for a scratch-library video with a YouTube
    id: `source` `playlist`, `reason` `no_caption`. Put the file back to
    `{"run": null, "needs_pick": []}` after.
  - Processing → Attention: its row reads "Playlist · no caption" (now the
    server's words), with Pick lyrics, Song info and Delete song.
  - Pick lyrics: the list shows it to pick. Don't pick: a pick would queue
    a GPU run.
  - Headless Edge at 390 px, as in the Phase 8 row, is fine.
- The `### Phase 8.1` Results row (raw facts) and the status block, in
  their own docs(plan) commit.

## Phase 8.2: fixes from the Phase 8.1c-8.1d code review

Model: Claude Opus 5.5 (review and design, 2026-10-24); executor Claude
Sonnet 5.5.

A read-only `/code-review` of `59dd376` (8.1c) and `763d64e` (8.1d)
(2026-10-24; three angles: correctness, simplicity, robustness) found the
defects below, each reproduced by a probe except the cleanups. Ken asked on
2026-10-24 for the recommended fixes to be written up, and dropped one
(8.2e). Phase 9 ran before this review, so 8.2's commits go on the end of
the landing list.

Each step names the defect it fixes. Same worktree, same ground rules, same
"Every phase ends the same way". Before starting, confirm the worktree is
clean at `17aee04` plus this plan commit.

Files: `processing_manager.py`, `library_tools.py` and their tests are in
D1. `genius.py` and `test_genius.py` are added to D1 for 8.2b (fork-owned;
Ken, 2026-10-24). One code commit per step, each with its tests, in order:
8.2a to 8.2d. 8.2a comes before 8.2b on purpose: 8.2b lets a Windows
re-pick through, and without 8.2a that re-pick can queue a song twice.

The suite at `17aee04`: 4 failed (the baseline's four), 2274 passed, 2
skipped. Rerun it first and use what it prints as the baseline. After 8.2b
it should be 3 failed: `test_genius.py::TestSidecarIO::test_write_overwrites_existing`
now passes.

Probe (scratchpad of the review session
`a85d9ebe-ab3e-44a5-b6f3-45382ebad848`, folder `review_81cd`; not committed;
run from the worktree root with `uv run --no-sync python -P
<scratchpad>\review_81cd\probe_81cd.py <empty scratch folder>`). It drives
the real `ProcessingManager` queue, cancel and run loop, with a stand-in for
the pipeline run (no workers, no GPU, no app). Output at `17aee04`
(`probe_81cd.out`):

- [1] cancel while waiting, re-pick, another song between: after A
  finishes, `pending=['Sb---bbbbbbbbbbb']` with X still in the queue, and
  `Sx---xxxxxxxxxxx.pick=None`; `pick #3: accepted`; `jobs that ran: [A, B,
  X, X]` (8.2a). The probe deletes the choice file before each re-pick, to
  stand in for Linux's overwrite.
- [2] a blocked word added after listing: `pick: accepted`, then `pending=[]`
  and `pick=None` (still listed); `pick again: RegenError: Could not save that
  pick.` (8.2c, and 8.2b on Windows).
- [3] a job that fails in stems, then a re-pick: `pick #2: RegenError: Could
  not save that pick.` (8.2b).
- [4] two picks at once: one refused with "That song is already waiting or
  processing.", one accepted (fine; unchanged by 8.2).
- [5] the playlist page and add, a song cancelled while waiting and added
  again: after A finishes the page shows `'y': 'not_processed'` while Y still
  waits; `add #3: {'downloads': 0, 'processing': 1, 'listed': 0}`; `jobs that
  ran: [A, B, Y, Y]` (8.2a, reached on Windows as shipped).

Record its before (above) and after in the row.

### 8.2a. A song queued again after a cancel while waiting is queued once

Defect (`processing_manager.py`): a cancel while waiting takes the song's
entry off `pending_jobs` and records the path in `_cancelled_paths`, but its
copy stays in `_pending_queue`. When the run loop later takes that copy, it
skips it and removes **every** entry for the path from `pending_jobs`. If the
song was queued again in between, the new job's entry goes too: it still
waits in the queue, but `is_busy` says False until its turn. With another
song queued between the two copies, that lasts the other song's whole run.
Meanwhile:

- the pick page shows the song to pick, and a pick is accepted and queues it
  again (8.1c made `is_busy` the only "picked");
- the playlist page shows it `not_processed`, and an add queues it again
  (8.1d);
- the song is processed twice: two full GPU runs.

A second form: cancel while waiting, queue again, cancel again before the
first copy is taken. `_cancelled_paths` is a set, so it holds one entry; the
loop skips the first copy and runs the second, which was cancelled.

The strip-all predates this branch, but on `dev` nothing queues a cancelled
song again, so only this branch's pick page and playlist add reach it.

Fix (`processing_manager.py`):

- `_cancelled_paths` becomes a `collections.Counter` (keep the name): how
  many waiting copies of each path to skip. `cancel_pending` adds one where
  it adds the path today (same conditions: not active, not a regen-lane
  path; a path not yet queued is still recorded, as
  `test_cancel_pending_not_in_queue_still_marks_cancelled` pins).
- `_run_loop`: a dequeued path with a count above zero takes one off
  (deleting the key at zero) and is skipped, and `pending_jobs` is **not**
  touched. `cancel_pending` already removed that copy's entry, so the strip
  only ever removed someone else's.
- `_drop_regen_jobs`, `enqueue`, `enqueue_regen`, `_run_job` are unchanged.

Tests (`test_processing_manager.py`, real `EventSystem`):

- Run-loop sequence (a stand-in `_process_song` that waits on an event, as
  the probe does, or by driving the dequeue directly if the file already
  has a helper): A running; X queued; B queued; X cancelled while waiting; X
  queued again. After A, X is still in `pending_jobs` while B runs, and X
  runs once.
- Cancel, queue, cancel, with A running: X runs zero times, and the counter
  is empty afterwards.
- The existing assertions that `_cancelled_paths == set()` become an empty
  check (`not manager._cancelled_paths`); `in` checks read as before.

Commit: `fix(processing): a song queued again after a cancel while waiting
is queued once`.

### 8.2b. A new lyrics choice replaces the old one on Windows too

Defect (`genius.py` `write_choice`): the temp file is moved into place with
`Path.rename`, which on Windows raises `FileExistsError` when a choice file
for the song is already there (the baseline's
`test_write_overwrites_existing`). A listed song's job leaves its choice
file whenever it ends before the lyrics stage uses it, so its re-pick
answers "Could not save that pick." until the temp folder is cleared:

- cancelled while waiting (recorded under Phase 8.1's row);
- failed, or cancelled while running, in extract, loudness, stems or
  transcode. The lyrics stage runs after the stem stage, so this is most of
  a job's run time (probe [3]).

Two branch tests hide it by deleting the choice file by hand:
`test_a_job_cancelled_while_it_waits_offers_the_pick_again` (with a comment
saying why) and `test_a_job_that_fails_offers_the_pick_again` (as if the
lyrics stage always runs before a failure).

Fix:

- `write_choice`: `Path(tmp_path).replace(target)` instead of `.rename`,
  which overwrites on every platform. Update the comment to match. Nothing
  else in `genius.py` changes.
- `test_library_tools.py`: the cancel-while-waiting test drops its
  `delete_choice` and comment, and its check that the new Genius pick is
  the one on disk now proves the overwrite. The failed-job test drops its
  `delete_choice`, so it is a failure before the lyrics stage. The re-pick
  is a Genius pick, and the file holds it afterwards.

Tests: the two above; `test_write_overwrites_existing` passes (3 failed in
the suite from here).

Commit: `fix(genius): a new lyrics choice replaces the old one on Windows
too`.

### 8.2c. A listed song whose title is now blocked leaves the list

Defect (`library_tools.py`): a blocked title is never listed (the
after-download check queues it for the queue to skip). But a word added to
the blocked list after a song was listed makes its pick a no-op.
`pick_lyrics` writes the choice and calls `enqueue`, which emits
`processing_skipped` and queues nothing. The pick answers success, `is_busy`
is False at once, and the song stays listed and pickable for good. Before
8.1c it showed "queued" for good instead.

Fix: `LibraryTools` subscribes `processing_skipped` to
`_forget_needs_pick`, beside `processing_complete` and `song_deleted`. A
skipped song leaves the list, as a blocked download is never on it. No new
text; no blocked check in `pick_lyrics`. `enqueue` emits outside
`LibraryTools`' lock, so the handler can take it. The choice file stays in
the temp folder (8.2e).

Tests (`test_library_tools.py`, real `EventSystem`): a listed song whose
`enqueue` emits `processing_skipped` (the fixture's `enqueue` side effect):
the pick returns, the view and `attention_rows` no longer have it, and the
saved state doesn't either. `test_a_blocked_title_is_queued_for_the_queue_to_skip`
passes unchanged.

Commit: `fix(library): a listed song whose title is now blocked leaves the
list`.

### 8.2d. Cleanup: one "already waiting" rule, and a stale docstring

- `check_playlist` calls `file_status` itself and then `_is_unprocessed`,
  which checks library membership and `file_status` again. The rule the
  page and the add are meant to share is half copied at the call site, and
  the disk checks run twice per such video. Add `_is_taken(song_path) ->
  bool`: listed for a pick, or `is_busy` (it takes the state lock for the
  listed read itself, as `_is_unprocessed` does today). `_is_unprocessed`
  is in the library, not `_is_taken`, and `NOT_PROCESSED`. `check_playlist`
  keeps its one `file_status` call and picks `waiting` when `_is_taken`, else
  `not_processed`.
- `_pick_reason`'s docstring says `on_song_downloaded` catches what it
  raises; since 8.1d it is `_check_download`.

Tests: the existing `TestCheckPlaylist` and `TestAddPlaylist` pass unchanged.

Commit: `refactor(library): one "already waiting" rule for the playlist page
and its add`.

### 8.2e. Not fixed, and why (record only; don't change)

- **The playlist page's summary tags leave waiting songs out**, so new + not
  processed + in library is less than the playlist's size when some are
  waiting. Ken dropped the fix on 2026-10-24: the "Already waiting (n)"
  section shows the count.
- **A blocked song's choice file stays in the temp folder** after 8.2c. Its
  song is marked skipped and is never processed, so nothing reads the file,
  and it goes with the temp folder.
- **A cancel that lands just as the loop takes the job** is pre-existing on
  `dev` (found while writing 8.2a). That is between the dequeue and
  `_launch_and_report` making the job active, with no workers involved yet.
  The job runs anyway, and the recorded skip then swallows that song's next
  download-lane queue. The window is the length of a pipeline-state read.
  Not seen live.

### 8.2f. Verify

- The full suite against the baseline plus the new tests (3 failed from
  8.2b); pre-commit per commit with `--files`; the import smoke
  (`processing_manager`, `genius`, `library_tools`, `routes.library`,
  `karaoke`, `app`).
- The probe, after: [1] X stays in `pending_jobs` while B runs, `pick #3`
  is refused with "That song is already waiting or processing.", and X runs
  once; [2] after the pick the song is not listed, and the second pick
  answers "That song isn't waiting for a pick."; [3] `pick #2: accepted`;
  [4] unchanged; [5] the page shows `'y': 'waiting'` after A, `add #3` gives
  `processing: 0`, and Y runs once. Run it unchanged (its `delete_choice`
  calls are harmless after 8.2b).
- Mutation checks, each must fail a test: 8.2a the run loop's skip strips
  `pending_jobs` again, and the counter back to a set (`add`/`discard`);
  8.2b `.rename` back (on Windows); 8.2c the `processing_skipped`
  subscription removed.
- No app run: nothing on a page changes.
- Append 8.2's four code commits to the landing list in the status block,
  and redo Phase 9's dry run (all of the list cherry-picked on a throwaway
  worktree off `dev`, then the tree compared with this branch outside
  `plans/`). Record both.
- The `### Phase 8.2` Results row (raw facts) and the status block, in
  their own docs(plan) commit.

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
  halfway and come back) → queue → watch the Jobs tab. After 7.1: with
  every pick made, the preview and the banner offer to queue.
- **Phase 7.2** (with Phase 8's check): Library tools → each of the four
  lists opens under its row and closes again; a song opens Song Info, and
  back returns to the tab.
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

Executed 2026-10-20 by Sonnet 5.5. Code commits: 2A `dd011af`, `9857986`
(tests only), `b50595a`; 2B `1ead8a8`; 2C `fb13913`.

- **Suite** (`uv run --no-sync python -P -m pytest tests/unit -q`, 36.8 s):
  **4 failed, 1626 passed, 2 skipped** = 1632 (baseline 1570 + 62 new tests). The
  four failures are the baseline's four (ids unchanged, `diff` of the two
  `FAILED` lists empty). New tests: 2A 20 (`TestGetRecord` 5, `TestSkipMarker` 3,
  `TestBackfillLrc` 3, `TestApplyLrclibChoice` 8, the CLI re-pick test 1), 2B 29
  (`test_library_status.py`), 2C 13 (`TestCheckCaption` 5, `TestGateOnDiskCaption`
  3, `TestReadPlaylist` 4, one `resolve_urls` ValueError test; the old
  `TestExpandPlaylist` test was replaced, not added).
- **2A, the re-pick defect:** `apply_lrclib_choice` is the first step of
  `prepare_lyrics`. A `sidecar` plan whose Genius id differs from the bundle's
  recorded id (or whose bundle has none) deletes `lyrics/<stem>.lrc`. Both the
  CLI-driven test (`regen.main()` with `--song <id> --reset --yes`, asserting the
  `.lrc` is gone when `run_one` runs) and the `prepare_lyrics` test fail with
  the fix disabled and pass with it. Touched test files: 108 passed.
- **2A, live `get_record(34563601)`:** first call a 503, second succeeded
  (`get_record` has no retry): `trackName` "Defying Gravity", `artistName`
  "Kristin Chenoweth & Idina Menzel", `albumName` "Wicked: Original Broadway
  Cast", `duration` 354.0, `syncedLyrics` 93 lines.
- **2B, live over `D:/Shared/pikaraoke-songs`** (`library_statuses`, read-only):
  `overview_counts` = **behind 5, poor 8, no_lyrics 2, all 48**. Categories:
  current 41, behind 5, no_lyrics 2. `lrclib_state`: n/a 26, rejected 10, used
  12, none 0, skipped 0. `method`: cue_align 24, joint 22, none 2. Behind =
  `xFYQQPAOz7Y`, `fJ9rUzIMcZQ`, `3JWTaaS7LdU`, `DYptgVvkVLQ`, `RPWDeLqsN0g` (all v10);
  no_lyrics = `qu_FSptjRic`, `8NJVNkzhJM4`. Poor (timed/lines): Defying Gravity
  51/89, Popular 51/62, Bloodstream 47/74, HUNTR/X This Is What It Sounds Like
  32/53, Mulan 36/47, Seasons of Love 25/34, Hakuna Matata 33/40, Jay Chou Sunny
  Day 18/42.
- **2B, `song_history` for `AoON1CyhQAM`:** 3 entries, newest first:
  `2026-10-19T18:03:52+00:00` v11 51/89 (current bundle, Genius 105865, LRCLIB
  34563601); `2026-09-21T17:13:07+00:00` v10 51/89 (`regen_backup_20261019T175506Z`,
  same ids); `2026-07-16T20:58:17+00:00` v8 51/89 (`regen_backup_20260921T170629Z`,
  Genius 105865, no LRCLIB). Matches the plan's expectation.
- **2B, one change after writing the module:** `SongStatus.poor` returns False
  when `lines_with_words` is missing (it divided by None before). A test covers
  it. With the threshold `>=` changed to `>` and the history dedupe removed, three
  tests failed; restored.
- **2C, live `check_caption`** (job built from the real library's bundle):
  `fJ9rUzIMcZQ` -> `CaptionCheck(found=True, wpm=63.42, passed=True)`;
  `xFYQQPAOz7Y` -> `CaptionCheck(found=False, wpm=None, passed=False)`. A
  before/after listing of the whole library (2605 files, size and mtime) was
  identical, and no `caption_check_*` folder was left in
  `C:\Users\TsangK\AppData\Roaming\pikaraoke\tmp`. With the `rmtree` removed four
  `check_caption` tests failed; restored.
- **2C, live `read_playlist`** on
  `https://www.youtube.com/playlist?list=PLRxQryWW8Yw1hcJrE_Aip8wJCPeSh2Ahe`
  (found by a yt-dlp playlist search; title "Musisi Karaoke BEST 10 | Popular
  Karaoke Songs"): 17 videos, each with an id and title; `expand_playlist` on the
  same URL returned the same 17 ids. The count was compared with the
  `playlist_count` yt-dlp reports from the same page (17), not by opening the
  page in a browser. The title says 10; the playlist holds 17.
- **Real library after all live checks:** `manifest.py compare` against the
  Phase 0 manifest: 2605 / 2605, 0 added, 0 removed, 0 changed.
- **pre-commit** (`--all-files`): black reformatted my test files only
  (re-staged). The run also edited `pikaraoke/lib/args.py` (upstream unused
  `import os`) and rewrote both plan files via mdformat; reverted with
  `git checkout` each time and not in any commit. Pylint passed. Import smoke:
  `library_regen`, `library_links`, `library_status` and both scripts import.

### Phase 3

Executed 2026-10-20 by Sonnet 5.5. Code commits: 3a `30f7c84`; 3b `b871285`,
then a fix `b2d8857`; 3c and 3d `1b48a39`; the three actions `289a942`.

- **Suite** (`uv run --no-sync python -P -m pytest tests/unit -q`, 41.1 s):
  **4 failed, 1715 passed, 2 skipped** = 1721 (Phase 2's 1632 + 89 new tests).
  The four failures are the baseline's four (ids unchanged). New tests by
  commit: 3a 1 (`TestStageOrdering`); 3b 15 (`TestPrepareRegenJob` 10,
  `TestFinishRegenJob` 3, CLI `TestRunJobsFinishesEachSong` 2); processing
  manager 29 (`TestIsBlocked` 3, `TestProcessingQueuedEvent` 2,
  `TestEnqueueRegen` 5, `TestRegenLaneOrder` 3, `TestSongDeletedDropsRegenJobs`
  2, `TestProcessRegen` 8, `TestLaunchFailures` 2, `TestActiveJobTiming` 3,
  `TestStart` gained 1) and tracker rows 19 (`TestRegenRows` 7, `TestProcessRows`
  4, `TestRowsThatFinish` 4, `TestRowActions` 4), both in `1b48a39`; actions 25
  (`TestDismiss` 8, `TestRetry` 7, `TestClearFinished` 2, `TestNewAdminEndpoints`
  6, 2 more in `TestRowActions`). `PipelineTracker` has no test file of its own;
  its tests live in `test_processing_routes.py`, where the existing ones are.
- **One transient failure** in an intermediate run (not in either full-suite
  run): `test_library_regen.py::TestApplyLrclibChoice::test_skip_wins_over_a_record_and_over_the_id_rule`
  raised `PermissionError [WinError 5]` from `os.replace` of
  `lyrics/<stem>.lrc.tmp` (the 2A atomic write). Three reruns of the touched
  test files (130 tests) passed.
- **Mutation checks** (each reverted afterwards): 3b, finish removes the
  bundle for non-transcribe plans (3 tests failed), backfill for a reused
  Genius pick off (1), reset ignored (2). Manager: regen path recorded in
  `_cancelled_paths` (1), playing song not held back (1), a failed regen marks
  `failed` (3), `song_deleted` not dropping regen jobs (1), launch failure not
  caught (the loop dies; 1 test failed). Tracker: a cancelled active regen
  deletes the song (1), a cancelled pending regen deletes it (1), regen rows
  shown to guests (1), events hit finished rows (2), `processing_queued` always
  adds a row (2), `remove` allowed for any kind (2). The retry fix (below) with
  the line removed: 1 failed.
- **Differences from the plan's text:**
  - `3b` is its own commit (`feat(regen): prepare and finish a queued regen job
    in the shared core`), with the CLI's one-line `finish_regen_job` call. The
    plan names three commits; there are five code commits.
  - `_launch_and_report(song_path, launch, regen=None)` takes the `RegenJob`
    (None for a download) instead of a separate `mark_failed` flag; the two were
    the same fact. A launch exception is handled for both kinds; a download's
    launch failure marks `failed`, a regen's does not. `finish_regen_job` is
    wrapped for `OSError` (logged), because an exception there would end the
    run loop.
  - `b2d8857`: found while writing Retry. A regen whose caption fetch failed
    left the job on its fallback `prompt` plan, which `prepare_lyrics` treats as
    transcribe, so a retry would have transcribed the song. `prepare_regen_job`
    now puts the `fetch` plan back before raising.
  - Tracker actions: `enqueue` (to the singing queue) is offered for `download`
    rows only; for `regen` and `process` rows only an admin can `cancel` (they
    have no singer, and an unnamed guest cookie matched the empty `user`).
    `dismiss` is offered to admins on any finished row, `remove` on finished
    `download` rows, `retry` on a row in `error` with a song path.
  - `process` rows are shown to guests (only `regen` rows are hidden, as the
    plan's text says).
  - Row titles use `SongManager.filename_from_path` (the static method), not an
    instance call.
- **Isolated app run** (Ground rules checked first: nothing listening on 5555
  or 5556, no python or mpv process, GPU idle at 1218 MiB). Scratchpad
  `appdata\pikaraoke\config.ini` is a copy of Ken's, with `download_path` edited
  to `D:/shared/weblib-test`; its `admin_password` is empty, so every request is
  an admin. Command: `APPDATA=<scratchpad>\appdata`, `PYTHONUTF8=1`,
  `uv run --no-sync python -P -m pikaraoke.app --download-path D:/shared/weblib-test --port 5556`
  from the worktree root. Log: `Library updated: 7 added`.
  - `GET /processing` HTTP 200 (27,997 bytes); `GET /processing/status` `[]`.
  - `POST /download` `{"song_url": ".../watch?v=aF8voKa_3Us", "song_added_by":
    "Tester", "song_title": "Traditional - Happy Birthday (Karaoke Version)",
    "queue": false}` (57 s video). Status rows over time, from
    `poll_status.py`: 2 s download `active`; 12 s download `complete`, processing
    `pending`; 28 s `active` / `stem_separation`, `elapsed_s` 3.8; 129 s
    `transcode`; 134 s `transcribe`; 169 s `complete`, `lyric_method`
    `transcribe`, actions `remove`, `dismiss`, `enqueue`. One row throughout,
    `kind` `download`; no `process` row appeared. Log: `Queued for pipeline`,
    `Processing started`, `Processing complete`; no traceback.
  - On that finished row: `POST .../retry` `{"success":false}`; `.../dismiss`
    `{"success":true}`, then the rows were `[]` and the song file was still in
    the scratch folder; `POST /processing/clear_finished` `{"count":0,"success":true}`.
  - Stopped with `taskkill /T` on the listener's pid (3 processes). Afterwards
    nothing listened on 5556 and no python or mpv process remained.
  - The scratch library now also holds the Happy Birthday video and its files
    (a transcribe run writes no bundle). Nothing queued a regen job, as the
    plan says; the regen lane has only run in the unit tests.
- **Real-library manifest:** `manifest.py compare` against the Phase 0 manifest:
  `manifest=2605 now=2616 added=11 removed=0 changed=1`. All 12 are under
  `zh_probe/phase0/`: added `phase0b_diffs.txt`, `phase0b_score.json`,
  `phase0b_score.txt` and eight `transcripts/<id>.json|.txt`; changed
  `phase0c_vocab.json`. Their mtimes are 13:33 to 13:40; the `chinese_karaoke`
  worktree has commits at 13:44 ("whisper transcript narrows the Phase 0b lyric
  candidates", "log the Phase 0b transcript-narrowing results"). This session's
  app run started at 13:55 and wrote to the scratch folder and the scratchpad
  `appdata` only. Nothing outside `zh_probe/` differs. Output:
  `...\66751cff-eade-4c4e-a440-a5ea44850245\scratchpad\manifest_compare_phase3.txt`.
- **pre-commit:** run per commit with `--files <changed files>` instead of
  `--all-files`, so `args.py` and the plan files were not touched. Black and
  isort reformatted my own files (re-staged); pylint passed. Import smoke:
  `pipeline_tracker`, `processing_manager`, `karaoke`, `routes.processing`,
  `library_regen` and `scripts.regen_alignment_bundles` import.

### Phase 3.1

Executed 2026-10-20 by Sonnet 5.5, starting from `af318ff` (clean, `1428f47`
plus the plan commit). Code commits: 3.1a `b5c4637`, `e8006da`; 3.1b `86de4f7`;
3.1c `26cf3b3`; 3.1d `b6301da`; 3.1e `5b67bff`; 3.1f `25ace83`; 3.1g `b849bb7`;
3.1h `2bc909d`. The status block carried Ken's approval of D2's Phase 3.1 bullet,
so 3.1g ran.

- **Suite** (`uv run --no-sync python -P -m pytest tests/unit -q`, 42.4 s at
  `2bc909d`): **4 failed, 1756 passed, 2 skipped** = 1762 (Phase 3's 1715 passed
  + 42 new - 1 deleted). The four failures are the baseline's four (ids
  unchanged). Net per commit: 3.1a -1, 3.1b +5, 3.1c +5, 3.1d +7, 3.1e +2, 3.1f
  +4 (the `finish_regen_job` tests were rewritten, not added), 3.1g +15, 3.1h +4.
  New tests: `TestSetupFailures` 3 and `TestLaunchAndReportResult` 2 (3.1b);
  `TestCancelWhilePreparing` 4 and `TestCancelActiveBeforeTheRun` 1 (3.1c);
  `TestLibrarySpelling` 7 (3.1d); 2 in `TestPrepareRegenJob` (3.1e); 3.1f: 2 in
  `TestProcessRegen`, 2 in `TestRunJobsFinishesEachSong`; 3.1g: `TestSnapshotRestore`
  4, `TestPutBackLrc` 2, `TestLrcPutBackWhenTheRegenDoesNotFinish` 6, one more in
  `TestCancelWhilePreparing`, 2 in `TestRunJobsFinishesEachSong`; 3.1h: 3 in
  `test_library_status.py`, 1 in `test_library_links.py`. The deleted test is
  `test_processing_routes.py::TestRetry::test_a_regen_row_that_lost_its_job_is_not_retried_as_processing`.
- **Mutation checks** (each reverted afterwards; failures counted in the new or
  touched test files). 3.1b: the old manager code against the 5 new tests, 5
  failed. 3.1c: `cancelling` kept after an error 1; setup cancel ignored at launch
  2; taking a job does not register it 4; `cancel_active` calls the orchestrator
  for a token-less job 2. 3.1d: spelling always the plain string 6; the
  `song_deleted` drop compares the plain path 1; `is_playing` called with the plain
  path 1. 3.1e: the 2 new tests against the old code, 2 failed. 3.1f: bundle
  removed for any non-None method 3; manager passes None 2; CLI passes None 2.
  3.1g: manager never puts the `.lrc` back 4; a cancel counted as success 3; CLI
  never puts it back 1; `put_back_lrc` lets an `OSError` through 2; restore always
  deletes 7. 3.1h: the 6 new or changed tests against the old source, 6 failed.
- **Differences from the plan's text:**
  - 3.1a: the plan says the existing tests pass unchanged. The deleted test above
    forced a regen row with no job, the state the deleted check guarded, so it
    went with the check.
  - 3.1b: with the inner catches gone, an error raises out of `_process_song` /
    `_process_regen` and `_run_job` reports it. The existing tests that called
    those two directly and expected the error event (`TestProcessSongError` 4,
    the `_run` helper of `TestProcessRegen`) now go through `_run_job`, as the
    loop does. `TestLaunchFailures` needed no change.
  - 3.1c: `_launch_and_report` shares `_report_cancelled` (the event and the log
    line) between its two cancel branches. If `_active` is None when a regen
    launches (a direct caller, as the tests are), it creates the `_ActiveJob`
    itself with `kind` taken from the job. `TestActiveJobTiming::test_a_job_records_which_lane_it_came_from`
    now takes the regen through `_take_regen_job` and `_run_job`.
  - 3.1d: `_take_regen_job` returns `(song_path, regen)` and `_process_regen` takes
    `song_path` as a second argument; `TestRegenLaneOrder` and
    `TestSongDeletedDropsRegenJobs` were adjusted to the tuple.
  - 3.1g: added `library_regen.put_back_lrc(song, snapshot)`, which restores and
    logs an `OSError`; both the manager and the CLI call it, so the "must not hide
    the job's own error" rule is written once. The plan named only `snapshot_lrc`
    and `restore_lrc`.
  - 3.1h: four existing status tests stood for a real LRCLIB record with
    `{"lrc_file": ...}` alone; they now carry `"id": 5`.
- **Seen while doing 3.1g, not changed:** an error raised after a successful run
  (the `set_pipeline_state("ready")` write, or an event handler) leaves the run
  counted as unfinished, so the old `.lrc` goes back next to the new bundle.
  `snapshot_lrc` reads text, so on Windows a restored LF-only file comes back with
  CRLF (the text is the same). `_report_failure` for a download still calls
  `set_pipeline_state("failed")` unguarded, as before this branch.
- **Isolated app run** (Ground rules checked first: nothing listening on 5555 or
  5556; GPU 1035 MiB, 0 %; the only process matching `python` was `TPython.exe`
  pid 4624, which has no path or command line and is not a pikaraoke process).
  The scratch library's six files for the Happy Birthday song (video, `.ass`,
  vocal, nonvocal, `.srt`, `.srt.generated`) were removed first (76 files left).
  Same command and config copy as the Phase 3 row. Log: `Scan: found 7 song(s) on
  disk`, `Library updated: 1 removed`, library path `D:/shared/weblib-test`.
  - `GET /processing` HTTP 200, 27,997 bytes (as in Phase 3); `GET
    /processing/status` `[]`.
  - A first `POST /download` with a form body returned HTTP 422 (the route takes
    JSON); nothing queued and the 360 s poll ended on `[]`. With a JSON body (the
    Phase 3 payload) it returned `{"status":"ok"}`. Rows from `poll_status.py`: 2 s
    download `active`; 28 s download `complete`, processing `loudnorm`; 33 s
    `stem_separation`; 53 s `transcode`; 58 s `transcribe`; 83 s `complete`,
    `lyric_method` `transcribe`, actions `remove`, `dismiss`, `enqueue`. One row,
    `kind` `download`, throughout; its `song_path` is
    `D:/shared/weblib-test\Traditional - Happy Birthday (Karaoke Version)---aF8voKa_3Us.mp4`
    (the library's own separators). Log: `Queued for pipeline`, `Processing
    started`, `Processing complete`; no traceback. The scratch library is back to
    82 files.
  - Stopped with `taskkill /T` on the listener's pid 34884 (3 processes); the
    background shell reported exit 1 because of that. Afterwards nothing listened on
    5555 or 5556 and no python or mpv process remained.
  - Nothing queued a regen job; the regen lane has only run in the unit tests.
- **Other live checks:** `scripts/regen_alignment_bundles.py --help` and
  `scripts/add_songs.py --help` both exit 0. Read-only over
  `D:/Shared/pikaraoke-songs` with the 3.1h rule: `lrclib_state` n/a 26, rejected
  10, used 12 (the Phase 2 counts); 0 current bundles hold an LRCLIB reference with
  no `id`; `overview_counts` behind 5, poor 8, no_lyrics 2, all 48. `read_playlist`
  with the `--` on the Phase 2 playlist returned 17 videos, and `expand_playlist`
  the same ids.
- **Real-library manifest:** `manifest.py compare` against the Phase 0 manifest:
  `manifest=2605 now=2616 added=11 removed=0 changed=1`, all 12 under
  `zh_probe/phase0/` (the same set as the Phase 3 row); nothing else differs.
  Output: `...\66751cff-eade-4c4e-a440-a5ea44850245\scratchpad\manifest_compare_phase31.txt`.
- **pre-commit:** per commit with `--files`, not `--all-files`. Black or isort
  reformatted my own files on 3.1c, 3.1d and 3.1g (re-staged and rerun until
  clean); the other commits passed first time. Pylint passed. Import smoke per commit: `lrclib`, `library_regen`,
  `library_status`, `library_links`, `processing_manager`, `pipeline_tracker`,
  `karaoke` and `scripts.regen_alignment_bundles` import.
- **3.1i:** nothing changed, as the step says.

#### Review of 3.1b-3.1d, and its fixes

Reviewed 2026-10-20 by Opus 5.5 (Ken asked), read-only, on
`e8006da..b6301da` (code only) with HEAD at `6317056`. Three finder agents,
one per axis (correctness, simplicity, robustness), with the verdicts checked
in the session. Ken then asked for findings 1-3 to be fixed in the same session.

| # | Axis | Verdict | Where (at `6317056`) | Finding |
|---|---|---|---|---|
| 1 | robustness | CONFIRMED (probe, real manager + tracker) | `processing_manager.py:563-571`, `pipeline_tracker.py:159-168`, `:225-236` | `_run_job` emits `processing_error` before its `finally` clears `_active` and `pending_jobs`. A `get_status` in that moment re-derives the error row as `active`; the next read makes it `complete` for good. A cancel in the moment leaves the row `cancelling` with no actions until restart (3.1c's tracker change covers only a cancel before the event). Retry in the moment is refused. Run errors in both lanes had it before; 3.1c added regen setup failures. The moment lasts as long as the tracker's `_notify_change` push. |
| 2 | simplicity | CONFIRMED (assert in the branch failed 6 tests, all direct callers) | `processing_manager.py:681-686` | `_launch_and_report`'s `_ActiveJob(kind="download" if regen is None else "regen")` for a regen runs only in tests that skip `_take_regen_job`; production always arrives registered. Its comment contradicts it. |
| 3 | simplicity | CONFIRMED | `processing_manager.py:663-667` | `_launch_and_report`'s docstring states the failed-regen `pipeline_state` rule, which since 3.1b lives in `_report_failure` (no docstring). |
| 4 | simplicity | CONFIRMED / PLAUSIBLE | `test_processing_manager.py:1104-1108`, `:1113-1121`, `:1192-1218`, `:1365-1375` | A stub repeating the `mock_orchestrator` fixture and a hand stub repeating `prepared`; `TestLaunchAndReportResult` and `TestCancelActiveBeforeTheRun` repeat checks behaviour tests already make, through private state. |

Additions to known items (recorded, not changed):
- The unguarded `set_pipeline_state("failed")`: with the database failing for
  both the read and the write, the loop still dies (probe: loop dead, the
  second download left pending). 3.1b's test fakes only the read failing.
- An error after a successful regen: besides the `.lrc` put-back, a run that
  transcribed keeps the old bundle, because `finish_regen_job` is skipped.
  Needs a database write to fail; Retry repairs it.
- `_library_spelling` costs about 7.4 ms per call at 2000 songs on this box
  (every call scans on Ken's root); the plan accepted a linear scan.

Checked clean: `PipelineCancelled` comes only from `join()` and is caught;
cancel during setup at each point (before, during, after the launch, after
`join`) with one event each and the temp lyrics folder removed; the previous
job's token never touched; lock order (`_is_playing` reads an attribute with
no lock); `SongList` iteration is a snapshot under its lock; Windows spellings
(`/` vs `\`, letter case) resolve to the library's string, which matches the
playing check, the database rows and the tracker row; the 3.1c/3.1d tests drive
the real loop, tracker and `SongList`.

Fixes (Ken: 1-3, and the redundant stubs of 4 with 2; the two private-state
test groups and the known-item additions left alone):
- `4165281` `fix(processing): a finished row keeps its status while the job
  cleans up`: `get_status` returns a row with `finished_at` set as its event
  left it (Retry clears `finished_at`). Tests: 2 parametrized + 1 in
  `test_processing_routes.py::TestRowsThatFinish` (mocked manager naming the
  job), 1 in `test_processing_manager.py::TestAFailedRowWhileTheJobCleansUp`
  (real loop and tracker, a handler after the tracker's holding the moment open:
  read, then cancel). Without the fix all 4 fail; with it they pass.
- `bc308ba` `refactor(processing): regen tests take the job the way the loop
  does`: the launch creates `_ActiveJob` only for a download; `_run_regen(mgr,
  regen)` (queue, take, run) replaces the three direct `_process_regen` calls;
  the `pipeline_state` rule moves to `_report_failure`'s docstring; `_run_job`'s
  docstring says an error while reporting still escapes; the two redundant
  stubs go. Mutation: `_take_regen_job` not registering the job fails 7 tests
  in the file.
- Suite (`uv run --no-sync python -P -m pytest -q`): **4 failed, 1760 passed,
  2 skipped** (1756 + 4 new; the baseline's four). pre-commit with `--files`
  (Black reformatted the new tests once per commit), import smoke for
  `pipeline_tracker`, `processing_manager`, `karaoke`.
- Environment: the first full run had 6 more failures (`files`, `info`,
  `search` render tests, `babel.core.UnknownLocaleError: unknown locale 'en'`).
  The worktree venv's `babel/locale-data` was empty; every package folder in the
  venv had a 21:34 timestamp, during the review's finder runs (cause not found;
  the session's own commands all used `--no-sync`). Repaired with `uv pip install
  --python .venv/Scripts/python.exe --reinstall --no-deps --offline
  babel==2.17.0` (1068 locale files back); then the run above.

### Phase 4

Executed 2026-10-22 by Sonnet 5.5, starting from `9231bc2` (clean). Code
commits: `7f5853e` (the veto fix below), `55cfdbb` (the feature).

- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`,
  122.4 s at `55cfdbb`): **4 failed, 1816 passed, 2 skipped** = 1822 (the
  baseline's 1760 + 56 new). The four failures are the baseline's four (ids
  unchanged). New tests: `test_library_tools.py` 14 (`TestSongsInList` 4,
  `TestIsBusy` 2, `TestRegenerate` 8); `test_library_routes.py` 37
  (`TestSongInfoAccess` 2, `TestSongInfoPage` 15, `TestSongInfoHistory` 4,
  `TestRegenerateRoute` 9 incl. 4 parametrized bodies, `TestOverviewRoute` 2,
  `TestSongListsRoute` 5); `test_library_status.py` +2 (veto);
  `test_files_routes.py` +3 (the info link for an admin and not for a guest, the
  Edit page link). The existing `test_files_routes.py` fixture gained
  `song_info.song_info` in its stub endpoints.
- **Environment:** the worktree venv's `babel/locale-data` was empty again at the
  start (first run: `UnknownLocaleError: unknown locale 'en'`, 1 failed in 3.8 s
  with `-x`). Repaired with the command in the task (`uv pip install --python
  .venv/Scripts/python.exe --reinstall --no-deps --offline babel==2.17.0`; 1068
  locale files); then the 1760 / 4 / 2 baseline reproduced before any change.
- **Mutation checks** (each reverted afterwards; failures counted in the new or
  touched test files). `library_status`: veto ignored 2. `library_tools`: list rows
  use the plain `Path` spelling 1; backup the whole folder 2; `is_busy` ignores
  waiting jobs 3; `regenerate` never checks busy 2. Routes: library check accepts
  any string 1, then 2 after the regenerate outside-path test was given a real
  bundle (it passed before, because a bundle-less song is refused anyway); no admin
  guard on regenerate 1; no admin guard on the page 1; list name unchecked 1; bar
  widths rounded 1; an LRCLIB record without a length labelled "no LRCLIB" 1.
- **Differences from the plan's text:**
  - 4a: `LibraryTools(processing_manager, song_manager, download_path)`. The plan names
    the events, Genius client and download manager as well; nothing in this slice
    reads them, so they are not stored. Later phases add them with their first use.
  - 4a: `songs_in_list(name)` returns `(path, status)` rows with the library's own
    spelling of each path (a dict from `Path` to the library string, built once; a
    video on disk that the library has not picked up is left out), because the
    routes' membership test is exact and the library keeps `d:/songs\X.mp4`-style
    strings. `SONG_LISTS` (name to rule) moved into `library_status` so
    `overview_counts` and the lists share one rule. `can_regenerate(song)` is the
    page's "would `regenerate` accept it" (busy or not); a backup that raises
    `OSError` becomes a `RegenError` with the message.
  - `7f5853e` (not in the plan, a fix to Phase 2B): `timed_by["aligner"]` is
    `align_won - evidence_veto.n_vetoed`. A real bundle (`DYptgVvkVLQ`, 22 aligner
    wins, `n_vetoed` 4, 18 timed lines of 42) otherwise made the bar run to 110%.
    Read-only over the real library's 22 joint bundles: `aligner - veto + transcription
    + captions + LRCLIB fills` equals `lines_with_words` on 17; on 5 it is 1 or 2
    higher (`22QYya-LGDY`, `otxTf5hZ0Yw`, `Orq_75kFi8I`, `hI-y5anGcUA`,
    `UvyHuse6buY`). Cause of those 1-2 lines not found. The bar follows the plan
    (each width is its count over the line count, no fixing), so on those songs it
    runs 1-2 lines past 100% and the container clips the right end.
  - 4c: segments and legend entries with a count of 0 are left out (the board's
    legend has no LRCLIB fill entry). A song with no bundle has no Alignment tab
    (nothing to show). The History rows mark what a version changed from the next
    older one (the board's "LRCLIB 5:54 added"); the same marker says "changed" when
    the LRCLIB match differs, and highlights the Genius part when its id differs
    (new wording: "changed"). A bundle with no Genius identity is listed as "YouTube
    captions". The route sentence for a Genius song with auto-captions follows the
    board ("the lyric aligner, a transcription and YouTube's auto-captions.").
  - 4e: the Song Info links carry `no-spa` (the SPA navigation intercepts every
    internal link and re-runs the page's scripts); the admin cell in `files.html`
    gained `white-space: nowrap` so the two icons stay on one line.
  - Page and list titles are mine, since the plan gives none: "Songs behind the
    current version", "Songs that look poor", "Songs with no lyrics", "All songs"; an
    empty list says "No songs in this list."; the busy note's link text is
    "Processing".
- **Isolated app run** (Ground rules first: nothing on 5555 or 5556, no python or
  mpv process other than `TPython.exe` pid 15952, which is not pikaraoke; GPU 1122
  MiB, 4 %). Config and `APPDATA` as in the Phase 3 row. The library path in the log
  is `D:/shared/weblib-test`; `Scan: found 8 song(s) on disk`. Before the run the
  scratch library was hashed (82 files, sha256).
  - Song Info for each of the 8 scratch songs, tiles as rendered (Lyrics | Timed |
    LRCLIB): Defying Gravity `Genius, up to date | 57%, 38 guessed | Not used, 97 s
    longer` (Timed and LRCLIB outlined amber); Backstreet Boys `YouTube captions, up
    to date | 100%, 0 guessed | -, Genius songs only`; Eason Chan `No lyrics | - | -`;
    Eminem `Genius, behind (v10) | 99%, 1 guessed | Used, fills 0 lines`; Jay Chou
    `Genius, behind (v10) | 43%, 24 guessed | Not used, 19 s shorter` (both amber);
    Josh Gad `Genius, up to date | 94%, 2 guessed | Not used, lines didn't line up`;
    Queen `YouTube captions, behind (v10) | 100%, 0 guessed | -`; Happy Birthday `No
    lyrics | - | -`. `/library/overview` `{"all":8,"behind":3,"no_lyrics":2,"poor":2}`
    (the Phase 2B counts for this folder). Eminem's "Used, fills 0 lines" is
    `eligible` true with an empty `filled_lids`.
  - Defying Gravity's History tab lists three versions: 19 Oct 2026 Current v11
    (`Genius · Kristin Chenoweth; LRCLIB 5:54`, 51 of 89 lines), 21 Sep 2026 Backup
    v10 under `regen_backup_20261019T175506Z` (`LRCLIB 5:54 added`), 16 Jul 2026
    Backup v8 under `regen_backup_20260921T170629Z` (`no LRCLIB`).
  - **Regenerate `xFYQQPAOz7Y`:** `POST /song_info/regenerate` at 10:11:40 returned
    `{"success":true}`; a second POST while it ran returned HTTP 400 `{"error":"This
    song has a regen waiting or running.","success":false}`. `/processing/status`
    row: `kind` `regen`, `label` `Regenerate`, `download_status` `complete`,
    `processing_phase` `transcribe` at 2 s (`elapsed_s` 7.4), `align` at 63 s,
    `processing_status` `complete` at 246 s of polling, `lyric_method` `genius+joint`,
    actions `cancel` while running and `dismiss` after. Log: `Queued for regen
    (Regenerate)` 10:11:42, `Regen started` 10:11:42, `Processing complete` 10:15:51
    (4 min 9 s from the POST); no traceback.
  - After the run: bundle `schema_version` 11, `captured_at` 2026-10-22T14:15:51Z;
    Eminem's Song Info `Genius, up to date | 98%, 2 guessed | Used, fills 0 lines`
    (85 of 87 lines timed: aligner 60, transcription 25; before: 86 of 87, aligner
    59, transcription 27); `behind` count 3 to 2. The backup folder
    `regen_backup_20261022T141142Z` holds 5 files, all of that song:
    `alignment_debug/<stem>.json`, `karaoke/<stem>.ass`, `lyrics/<stem>.lrc`,
    `subtitles/<stem>.srt`, `subtitles/<stem>.srt.generated`. Hash diff of the scratch
    library (script `hashlib_tree.py`, before 82 files, after 87): added 5 (those),
    removed 0, changed 3 (its bundle, `.ass` and `.srt`); the other 69 files of the
    other songs are byte-identical. Its History tab: Current 22 Oct 2026 v11 (85 of
    87 lines) over Backup 20 Oct 2026 v10 (86 of 87) under the new folder, no change
    markers.
  - Layout was looked at in headless Edge at 390 px (a 390 px iframe, since Edge's
    window will not go below 500 px), tabs Picks, Alignment, History for Defying
    Gravity and Eminem, Alignment for Backstreet Boys, Picks for Eason Chan, the
    poor list and Browse; the screenshots are in
    `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\shot_*.png`. In those the
    icon font did not load (the page was opened from `file://`), so the Browse
    icons are boxes and the icons were not checked; the first two headless runs hung
    and were killed by their profile folder (only those processes). Not live-checked:
    `white-space: nowrap` on the Browse admin cell and the `_lrclib_label` helper
    (both added after the run; covered by unit tests only).
  - Stopped with `taskkill /F /T` on the listener's pid (twice, once for a restart
    that picked up a template change); afterwards nothing listened on 5555 or 5556
    and no python or mpv process remained (the background shells reported exit 1
    because of that).
- **Real-library manifest:** `manifest.py compare` against the Phase 0 manifest:
  `manifest=2605 now=2616 added=11 removed=0 changed=1`, the same 12 files under
  `zh_probe/phase0/` as the Phase 3 and 3.1 rows; nothing else differs. Output:
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\manifest_compare_phase4.txt`.
  The real library was only read (status scans for the veto check).
- **pre-commit:** `--files <changed files>` per commit (and once before staging),
  all hooks passed, Black made no change. Import smoke: `library_status`,
  `library_tools`, `routes.song_info`, `routes.library`, `karaoke`. A stash of the
  feature work let `7f5853e` be tested alone (37 passed in `test_library_status.py`
  plus `test_files_routes.py`) before it was committed.

### Phase 5

Executed 2026-10-22 by Sonnet 5.5, starting from `232aa9b` (clean). Code commit:
`641600a` (one commit: the server and the page, as the plan names it).

- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`,
  127.4 s at `641600a`): **4 failed, 1855 passed, 2 skipped** (1861 tests; passed =
  Phase 4's 1816 + 39 new). The four failures are the baseline's four (ids
  unchanged). New tests: `test_processing_page.py` 10 (`TestProcessingPage` 8,
  `TestStatusJson` 2); `test_processing_routes.py` +24 net (`TestDisplayOrder` 6,
  `TestPoorSongNumbers` 5, `TestAttentionRoute` 3, `TestRetrySongRoute` 9 incl. 5
  and 2 parametrized, and 1 net in `TestRowActions`: the guest-process-row test was
  replaced by two); `test_library_tools.py` 4 (`TestAttentionRows`);
  `test_karaoke_database.py` 1. One existing assertion changed: a regen row's
  admin `actions` is now `["cancel", "song_info"]`.
- **Mutation checks** (each reverted afterwards, files restored as bytes; failures
  counted in the touched test files; 25 mutations, each caught): tracker: process
  rows ranked with the regen lane 1, the running job not ranked first 2, the active
  download not ranked before waiting downloads 1, finished rows oldest first 1,
  the running row also gets a position 2, guests see process rows 2 (routes and
  page tests), `song_info` offered to guests 1, a download error not stamped
  finished 1, a download error leaving `processing_status` alone 2, poor numbers
  shown to guests 1, numbers kept for songs that are not poor 1, a bundle that
  cannot be read fails the finished job 1, `mine` always false 1. Tools: attention
  rows keep songs the tracker shows 2, keep busy songs 1, keep songs outside the
  library 1, failed after unfinished 2. Routes: attention list given to guests 1,
  retry without the admin guard 1, retry accepts any string 1, retry ignores a busy
  song 2. Database: the `states` argument ignored 1. Page: guests get the admin
  URLs 1, the library card shown to guests 1, `window.confirm` back 1.
- **Environment:** no `UnknownLocaleError` this time (the babel locale data was
  intact). The scratch library had changed since Phase 4: Ken had run his own
  Phase 4 checks (a regen of Queen at 10:39, folder
  `regen_backup_20261022T143904Z`, Queen's bundle `captured_at`
  `2026-10-22T14:43:45Z`, v11), so 91 files and `behind` was 1 (Jay Chou) at the
  start.
- **Differences from the plan's text:**
  - 5a ordering: songs waiting for processing run in this order: `download` and
    `process` rows (the download lane, in queue order), then `regen` rows (the regen
    lane). The plan says `download` rows before `regen` and `process` rows. A
    `process` row is queued with `ProcessingManager.enqueue`, which is the download
    lane, and the loop takes that lane first.
  - 5a position: every active row except the running job is numbered from 1,
    including the download in progress (the board numbers it).
  - 5a guests: `get_status` leaves out `process` rows for non-admins as well as
    `regen` rows (5b: a guest never sees a regen or library row). The old test that
    a nameless guest cannot operate a process row became one that guests do not see
    it.
  - 5a rows: tracker rows gain `song_info` in `actions` for admins when the row
    has a song path (the plan lists it for attention rows only; the expanded row's
    Song info button follows the server's actions), and a `mine` flag (the row is
    the caller's own download) for the guest page's YOU tag.
  - 5a poor songs: `guessed` and `line_count` are read from the bundle once, in the
    `processing_complete` handler (`PipelineTracker._poor_lines`), not at every
    status read. The read catches `OSError`, `ValueError`, `TypeError` and
    `AttributeError` and logs a warning: an exception from a handler reaches
    `_run_job` and would mark a song that had just finished as failed.
  - 5a failed downloads: `_on_download_error` now also sets `processing_status` to
    `error` and stamps `finished_at`, so the row sorts by when it failed, shows "N
    min ago", and `remove` works before any status read (before, `remove` on a
    fresh download error returned False until a status read had derived the state).
  - 5a retry: `POST /processing/song/retry` refuses a song that is not in the
    library (400) and one already waiting or running (400 `This song is already
    waiting or running.`) before it calls `processing_manager.enqueue`, which has
    no duplicate guard.
  - 5a attention rows: failed songs come before unfinished ones, each by display
    name; a DB row for a path that is not in the library is left out.
  - 5b: the running job is shown in the Now box only (the board does not repeat it
    in the list, and counts it under Active); the box taps open to Song info and
    Cancel, because the running job has no other row to act on. A failed download
    with no file offers Dismiss only (no "Delete song"). A guest's cancel confirms
    inside the row too. The Now box and rows show the kind word: `Download`, `Regen`
    (box tag) and the job's label (row subline).
  - 5b: the page script is handed no admin-only URL when the viewer is a guest.
  - Wording is mine where the plan gives none: "Didn't finish processing" and
    "Processing failed" (database rows), "Cancel this job?" with "Cancel job" and
    "Keep", "Delete this song from the library?" with "Delete song" and "Keep",
    "Ready to sing", "just now", "N min/h/d ago", "N of M lines guessed", the tag
    words Downloading / Waiting / Processing / Cancelling / Failed / Unfinished /
    Done. "Looks poor (15%+ lines guessed)" is the board's. The `.pot` is not
    regenerated.
- **Defects found by looking, fixed before the commit:** (1) a database row on the
  Attention list could not be expanded or acted on (the page keyed it `db:<path>`
  but the existence check used the raw entry, so the expansion was pruned on every
  draw); found in the live DOM, not by the first synthetic render, where I read the
  screenshot wrongly. (2) The Library card label showed `15%%+` (a `%` in a `trans`
  block with no variables is not unescaped). (3) The filter chips wrapped at 390 px
  (padding 12 to 10 px, gap 8 to 6 px). (4) The running job's clock jumped back on
  every row tap (it was reset from the last fetched value on each draw). (5) A
  `.pr-chip` highlight appeared to stay on "All" in the screenshots: headless Edge
  does not advance CSS transitions in virtual time; the DOM and computed styles were
  right, the harness now sets `transition: none`.
- **Isolated app runs** (Ground rules first each time: nothing on 5555 or 5556, no
  python or mpv process, GPU 913 to 1218 MiB at 3 to 33 % from desktop programs
  only). Scratch config and `APPDATA` as in the Phase 3 row. Run A (`app_run_phase5.log`):
  the scratch library was hashed first (91 files, `scratch_before_p5.json`), the six
  Happy Birthday files were removed so it could be downloaded again (as in 3.1),
  and a 2 KB file `Throwaway - Delete Me---zzzzzzzzzzz.mp4` was added; log `Scan:
  found 8 song(s) on disk`, added 1, deleted 1. The throwaway's `pipeline_state`
  was set to `pending` with sqlite3 on the scratch DB. `/processing/status` `[]`,
  `/processing/attention` one row (`Throwaway - Delete Me`, `unfinished`, actions
  `retry`, `song_info`, `delete`), `/library/overview` `{"all":8,"behind":1,"no_lyrics":1,"poor":2}`.
  - Jobs (poller `live5.py poll`, one snapshot per change): 11:31:12 `POST
    /song_info/regenerate` Jay Chou (success); 11:31:28 the same for Josh Gad, whose
    video was then renamed to `.away`; 11:32:31 `POST /download` Happy Birthday
    (`song_added_by` `Tester`). Rows at 63 s: Jay Chou `regen` `active` position
    null (`processing_phase` `transcribe`), Happy Birthday `download` `active`
    position 1, Josh Gad `regen` `pending` position 2; at 93 s the download was
    `complete` / `pending` and still position 1 ahead of Josh Gad; Jay Chou reached
    `align` by 186 s. Jay Chou finished 11:39:03 (7 min 51 s from the POST): group
    `finished`, `lyric_method` `genius+joint`, `guessed` 26, `line_count` 42, actions
    `dismiss`, `song_info`. The download then processed 11:39:03 to 11:40:12
    (`extract`, `loudnorm`, `stem_separation`, `transcode`, `transcribe`), actions
    `cancel`, `remove`, `song_info`, then `remove`, `dismiss`, `song_info`,
    `enqueue`. Josh Gad's job started 11:40:12 and failed 11:40:14: `Song file not
    found: D:\shared\weblib-test\Josh Gad - In Summer (From 'Frozen'_Sing-Along).mp4`,
    group `attention`, actions `dismiss`, `retry`, `song_info`; the video was
    renamed back at once. Josh Gad's `pipeline_state` stayed `skipped`.
  - `POST /processing/clear_finished` `{"count":2,"success":true}`; both songs'
    files stayed. Happy Birthday set to `failed` in the DB: `/processing/attention`
    listed it (`failed`) before the throwaway (`unfinished`); `POST
    /processing/song/retry` `{"success":true}`; a second POST at once HTTP 400
    `{"error":"This song is already waiting or running.","success":false}`. The row
    was `kind` `process` (`active`, `transcribe`, then `complete`, actions `dismiss`,
    `song_info`), log 11:54:38 to 11:55:44, state `ready` afterwards; attention was
    `[]` while it ran. `GET /files/delete?song=<throwaway>&referrer=/processing`
    returned 200 after its redirect, the file was gone, attention `[]`.
  - Log: no traceback; the only `ERROR` lines are the yt-dlp pip upgrade (the known
    uv gotcha) and Josh Gad's failure. Stopped with `taskkill /F /T` on the
    listener's pid 11548.
  - Run A's code did not yet have three late edits: the `_poor_lines` guard, the
    attention-row mapping fix and the Delete-button condition. Run B
    (`app_run_phase5b.log`) had the first two, run C (`app_run_phase5c.log`) all
    three. The poor-song numbers on a finished row were therefore seen live on the
    unguarded version only. One last edit came after run C: the page no longer
    sets a `key` field on an attention row that nothing read.
  - Run B, with a throwaway admin password put in the scratch config copy (set, then
    emptied; never written down): Josh Gad's video renamed away, then `POST
    /song_info/regenerate` as admin (success; it failed at 12:01:30 with the same
    message; `backup_text_folders` copied nothing because the video was already
    renamed, and no folder appeared), then the video renamed back; and a `POST
    /download` as guest Alice (`user` cookie, no admin cookie) of `watch?v=zzzzzzzzzzz`
    (does not exist). Guest requests: `/processing/attention` `[]`; `/library/overview`
    403; `/library/songs?list=all` and `/song_info` 302 to `/browse`; `POST
    /song_info/regenerate`, `/processing/song/retry`, `/processing/clear_finished`
    403; `/processing` 200, 33,892 bytes, no tab, chip, library link or admin URL,
    the guest sections and intro sentence present; `/processing/status` one row: Alice's
    failed download, group `attention`, `mine` true, `actions` `[]`. Its `error_message`
    still holds the raw yt-dlp text (the page shows the plain sentence). Admin
    requests: `/processing/attention` one row (Eason Chan, `unfinished`, set `pending`
    for this run and set back to `skipped`), `/library/overview`
    `{"all":8,"behind":0,"no_lyrics":2,"poor":2}`, status rows: the failed download
    (actions `remove`, `dismiss`) and Josh Gad's failed regen (`dismiss`, `retry`,
    `song_info`); `/processing` 200, 35,789 bytes with both tabs, the chips and the
    library links.
  - Layout was looked at in headless Edge at 390 px (a 390 px iframe): with rows from a
    real tracker and mocked managers (`...\p5shots\*.png`), and with the live JSON of
    runs A and B drawn through the live app's own page (`...\p5live\final_*.png`: admin
    Jobs, expanded rows with the failed regen, the failed download and an Attention
    row with its delete confirm, the running job with its Cancel, a finished poor
    song, the Library tools tab, the guest page). The Library tools counts in those
    screenshots are a fixed stub; the live counts are the `/library/overview` values
    above. The Browse and Song info pages were not part of this phase's layout.
  - After: the scratch library hashed again (106 files, `scratch_final_p5.json`):
    added 15 (`regen_backup_20261022T153112Z`, Jay Chou's 5 files;
    `regen_backup_20261022T153128Z`, Josh Gad's 10 files), removed 0, changed 3
    (Jay Chou's bundle, `.ass` and `.srt`), 88 identical, which includes all six
    re-created Happy Birthday files. Scratch DB: throwaway row gone, Happy Birthday and
    Jay Chou `ready`, Eason Chan and Josh Gad `skipped`; scratch config
    `admin_password` empty. Nothing listens on 5555 or 5556 and no python or mpv
    process remains; headless Edge was killed by its profile folder only.
- **Real-library manifest:** `manifest.py compare` against the Phase 0 manifest:
  `manifest=2605 now=2616 added=11 removed=0 changed=1`, the same 12 files under
  `zh_probe/phase0/` as the Phase 3, 3.1 and 4 rows; nothing else differs. Output:
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\manifest_compare_phase5.txt`.
  The real library was not touched.
- **pre-commit:** `--files <changed files>`; Black reformatted four of my files on the
  first run (re-run clean), every hook passed on the last run. Import smoke:
  `pipeline_tracker`, `library_tools`, `karaoke_database`, `song_manager`,
  `routes.processing`, `karaoke`.
- **Seen, not changed:** `POST /processing/song/retry` checks the song is idle and then
  queues it; two requests in the same instant could both pass (`ProcessingManager.enqueue`
  has no duplicate guard, as before). The status JSON gives a guest the raw
  `error_message` of any download row (the old page showed it too; the new page shows
  fixed sentences). A row can show as Done for an instant between `song_downloaded` and
  `processing_queued` (the status derivation, unchanged). The page script has no
  automated test: the checks above are the unit tests on the markup and JSON, the
  headless renders and the live DOM. Jay Chou is now at v11, so no scratch song is
  behind; Song Info regenerates any video song.

### Phase 5.1

Executed 2026-10-22 by Opus 5.5, starting from `5d44150` (the 5.1 plan commit, on
`9d28e85`, clean). Ken gave the go on the section as written (the cancel permission of
nameless guests left as upstream has it). Code commits, in order:

| Step | Commit | Files |
|---|---|---|
| 5.1a | `874d49c` refactor(processing): one error field per failed download, Delete only with a file, attention reads tracked paths | `pipeline_tracker.py`, `routes/processing.py`, `processing.html`, `test_processing_routes.py` |
| 5.1a | `8b8d34f` refactor(library): one song check for the routes, the poor label from its rule | `routes/song_info.py`, `routes/processing.py`, `processing.html`, `test_processing_page.py` |
| 5.1b | `6f08c59` fix(processing): a bundle with bad counts no longer fails a finished job | `pipeline_tracker.py`, `test_processing_routes.py` |
| 5.1c | `14c7c14` fix(processing): a download keeps its row when a status read lands before the queue | `pipeline_tracker.py`, `test_processing_routes.py` |
| 5.1d | `b433e90` fix(library): a .lrc that isn't UTF-8 no longer breaks the library pages | `lrclib.py`, `test_lrclib.py`, `test_library_status.py` |
| 5.1e | `6caad6f` fix(processing): a confirm closes when its action goes, and YOU only marks a named guest's rows | `pipeline_tracker.py`, `processing.html`, `test_processing_routes.py`, `test_processing_page.py` |

- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`, 121.6 s
  at `6caad6f`): **4 failed, 1865 passed, 2 skipped**; passed = Phase 5's 1855 + 10
  new. The four failures are the baseline's four (ids unchanged). New tests:
  `test_processing_routes.py` 7 (`TestRowActions` 1: a download that failed before it
  had a file offers no `remove`; `TestTrackedPaths` 1; `TestPoorSongNumbers` 1: a count
  that is not a number; `TestAStatusReadBeforeTheQueue` 2: a download and a retried
  download keep their row; `TestDisplayOrder` 1: a guest with no name owns no row);
  `test_processing_page.py` 2 (the label follows `POOR_GUESSED_SHARE` patched to 0.2;
  the confirm prune is in the script); `test_lrclib.py` 1; `test_library_status.py` 1.
  No existing test changed.
- **Probes** (scratchpad of session `65fef55e-e098-476e-9ae8-e45f76710fac`), run at
  `9d28e85` before any change and again after each fix:
  - `probes\p1_status.py`: before, `song_status RAISES UnicodeDecodeError`, `overview
    RAISES UnicodeDecodeError`, `_poor_lines -> None` (it caught the decode error and
    logged), `_poor_lines malformed RAISES TypeError`. After 5.1b, `_poor_lines
    malformed -> None` with the warning logged. After 5.1d, `song_status -> none`,
    `overview -> {'behind': 0, 'poor': 1, 'no_lyrics': 0, 'all': 1}`, `_poor_lines ->
    (5, 10)`, each read logging `... is not UTF-8, so it is not a skip marker`.
  - `probe_race.py`: before, `read in window: [('download', 'complete', 'finished')]`,
    `admin after queue: [('process', '', 'active')]`, `alice after queue: []`. After
    5.1c, the first line is unchanged (the read still calls the row complete for that
    instant), `admin after queue: [('download', 'alice', 'active')]`, `alice after
    queue: [('download', 'active')]`.
- **Each new test fails on the code before its fix:** 5.1b's (1 failed with
  `pipeline_tracker.py` at the parent commit), 5.1c's (both), 5.1d's (both, with
  `lrclib.py` at the parent).
- **Mutation checks** (each reverted, files restored from a scratch copy; failures in
  the touched test files): `remove` offered again on a failed download with no file 1;
  `tracked_paths` leaving out finished rows 1 (the attention route test);
  `library_song` not checking the library 3 (routes); `posted_song` skipping
  `library_song` 4; 5.1c without the reset to `waiting` 1 (the dismiss assertion; the
  next status read alone re-derives `pending`, so only a call between the event and
  that read sees the difference); 5.1c matching any unstamped row, not only a complete
  one 1 (`TestProcessRows`, whose helper marks a row failed without the stamp);
  `mine` without the name test 1. The label test failed on the first try of the
  template (see below), which served as its check.
- **Deno check of 5.1e** (not committed; `extract_confirm.py` renders `/processing` as
  admin through the page test's app, takes `CONFIRM_NEEDS`, `rowKey`, `offers` and
  `pruneState` from the page, and writes `confirm_check.js`; `deno run`): `PASS cancel
  closes when cancel goes` (a `cancel` confirm on a row whose actions become `dismiss`,
  `song_info`; the row stays expanded), `PASS delete stays while remove is offered`,
  `PASS db row delete stays` (a database row with `delete`), `PASS cancel stays while
  offered`, `PASS gone row forgotten`. With the prune line taken out of the generated
  file, the first prints `FAIL`.
- **Differences from the plan's text:**
  - 5.1a label: the template has one `%` (`{{ share }}%+`), not `%%`. With a variable,
    Jinja's `trans` block doubles a lone `%` itself and the newstyle gettext formats it
    back; the plan's `%%` rendered as `15%%+`.
  - 5.1c: `_on_processing_queued` takes back a row of the song that is `complete` with
    no `finished_at`, not any row with no `finished_at`. Only a status read makes a row
    complete without the stamp, and the narrower test is the ruling's own words.
  - 5.1e: the Delete button's test went through `offers` in 5.1e, after 5.1a had made it
    `has('remove') || has('delete')`.
- **Seen, not changed:**
  - A regen of a song whose `.lrc` is not UTF-8 fails at its start: the job's
    `snapshot_lrc` reads the file as UTF-8 and the error becomes the job's error (an
    Attention row with the decode message, no 500). The pipeline's own `read_lrc` reads
    it the same way.
  - The tests' `_finished` helper sets a row's status without stamping `finished_at`,
    which real events always do.
- **No app run:** every change is covered by a unit test, a probe or the Deno check.
- **pre-commit:** `--files <changed files>` per commit, every hook passed first time.
  Import smoke: `pipeline_tracker`, `lrclib`, `library_status`, `routes.processing`,
  `routes.song_info`, `karaoke`, `app`.

### Phase 6

Executed 2026-10-22 by Sonnet 5.5, starting from `220ac2b` (the Phase 5.1 record, clean).
Code commit: `8a3b585` feat(library): repair a song's lyrics with typed Genius and LRCLIB
searches (8 files, +1583/-26: `karaoke.py`, `library_tools.py`, `routes/song_info.py`,
`song_info.html`, `song_repair.html` new, `test_library_tools.py`, `test_library_routes.py`,
`test_processing_routes.py`).

- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`, 125.9 s at
  `8a3b585`): **4 failed, 1949 passed, 2 skipped**; passed = 5.1's 1865 + 84 new. The four
  failures are the baseline's four (ids unchanged). New tests: `test_library_tools.py` 31
  (`TestRepair` 15, `TestGeniusSong` 3, `TestCaptionCheck` 3, `TestLrclibCandidates` 10);
  `test_library_routes.py` 53 (`TestRepairButton` 4, `TestRepairPage` 10,
  `TestCaptionCheckRoute` 4, `TestGeniusLyricsRoute` 7, `TestLrclibSearchRoute` 7,
  `TestRepairRoute` 21). Existing tests changed only in their fixtures: the three places that
  build `LibraryTools` pass its new fourth argument (`test_library_tools.make_tools`,
  `test_library_routes.Env`, `test_processing_routes`), and `search.lyrics_search` joined the
  route tests' stub endpoints.
- **Mutation checks** (35, each reverted, failures counted in the touched test files; script
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\mutate6.py`). Caught: an LRCLIB id
  beating skip 1; `repair` ignoring a busy song 2; the Genius pick not checked before queueing
  1; a repair that doesn't wipe first 4; a missing LRCLIB record not refused 2; a record with
  no synced lyrics accepted 1; the caption plan built for a song with no YouTube id 3; the
  transcribe source queueing another plan 2; an unknown source queued as nothing 4; the Genius
  cache never evicting 1; never caching 3; `best` never marked 2, marking the first candidate
  2; `current` never marked 2, compared when both ids are None 3; records without synced
  lyrics listed 1; a non-UTF-8 `.lrc` breaking the search 1; the length difference with the
  wrong sign 2; `mapped` counting every cue 1; no admin guard on the repair POST 1, the
  caption check 1, the Genius lyrics 1, the LRCLIB search 1, the repair page 1; the repair
  page rendering for a non-video song 1; the LRCLIB search skipping the library check 1; bool
  ids accepted 1; the skip flag of any type 1; the current source swapped between caption and
  Genius 2; the length rule not handed to the page 1; the Genius 502 leaking the exception
  text 1; Genius text put in with `.html()` 1; Repair enabled for a busy song on Song Info 1.
  Survived: hard-coding `var NOTED_S = 5;` in the page (the route's constant is also 5, so
  nothing differs; the other mutation of that line, a different value, is caught). The first
  run had 36 checks with three survivors: that one, `current` for a record with no id (the
  test records all had one) and `mapped` counting cues that don't map (every cue of the test
  records mapped). The tests were extended (a record with no id; a cue the lyrics don't
  have), and both mutations are caught afterwards. The two caption mutations became one after
  the `_caption_plan` helper (below).
- **Differences from the plan's text:**
  - `LibraryTools(processing_manager, song_manager, download_path, genius_client)`;
    `karaoke.py` passes `self.genius_client`. `genius_song(id)` (the last-20 cache, a dict
    under a lock, oldest out), `caption_check(song)` and `lrclib_candidates(song, genius_id,
    title, artist)` live there, so the routes only serialise and the tests need no Flask; the
    plan describes the candidate fields at route level. Regenerate and Repair share one
    `_queue(job, reset, label)` (backup that song, then `enqueue_regen`), and the YouTube-id
    rule for a caption plan is one helper, `_caption_plan`, which `repair` and
    `caption_check` both use (it is `resolve_plan(job, reset=True)` and requires `fetch`).
  - Before the backup, a Genius repair fetches the pick (`genius_song`, cached, normally free
    after the LRCLIB step) and refuses with "Genius didn't return that song's lyrics. Try
    again." when it can't. Not in the plan: the run wipes the song's outputs first (D2), so a
    bad id would otherwise fail after the wipe. A record whose `syncedLyrics` is empty is
    refused too ("That LRCLIB match has no synced lyrics."); the page only offers records with
    synced lyrics, a hand-made POST doesn't have to.
  - `lrclib_skip` wins over `lrclib_id` (no `get_record` call), the same order as
    `apply_lrclib_choice`. `repair` validates `source` itself ("Unknown lyric source."),
    "Pick a Genius song first." for a Genius source with no id; the route checks the types of
    `genius_id`, `lrclib_id` (int, not bool) and `lrclib_skip` (bool).
  - `duration_diff_s` is signed like Song Info's gap (positive: the match is longer) and null
    when either length is missing. Each candidate also carries `record_meta`'s fields. `best`
    is the record `select_candidate` returns (same rule as the automatic pick); `current`
    compares with the id the `.lrc` on disk records, so a skip marker or an unreadable file
    marks none (the `.lrc` read follows 5.1d).
  - Song Info: Repair lyrics is a `<button>` that sets `location` (not a link), so one
    `disabled` covers both buttons, and a Regenerate click disables Repair until it fails.
    It shows for every video song, also one with no pick (Regenerate still needs one).
  - The repair page for a non-video song redirects to Song Info (the plan is silent); a guest
    gets the same redirect with a flash as the other pages.
  - Page details the boards don't settle: the song name is a quiet line under the page title;
    step 2 has its own heading, "LRCLIB match"; the board's note about the backup also shows
    under step 1 for the caption and transcribe sources (they queue from there); the
    secondary line of a result row is clamped to two lines (see below); an empty Genius
    result list reads "No Genius results."; an empty LRCLIB list reads "No synced matches
    found. If LRCLIB is busy, try again in a moment."; the LRCLIB search needs a title (an
    empty artist works, an artist alone finds nothing at LRCLIB). The length rule (a gap under
    5 s reads "within a few s") is Song Info's `_LENGTH_GAP_NOTED_S`, handed to the page.
- **Isolated app run** (Ground rules first: nothing on 5555 or 5556, no python or mpv process
  besides `TPython.exe` pid 15952, which is not pikaraoke; GPU 1173 MiB, 0 %). Config and
  `APPDATA` as in the Phase 3 row (the scratch config has no admin password). The log says
  library `D:\shared\weblib-test`, `Scan: found 8 song(s) on disk`. The scratch library was
  hashed before (114 files, `scratch_before_p6.json`). The pages were driven through headless
  Edge 155 over the DevTools protocol (`cdp6.py`, a 390 px emulated window; clicks, typing,
  reading the page), screenshots in `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\p6shots\`.
  - Look-only pass: Song Info shows `Repair lyrics` and `Regenerate`. Repair page step 1 for
    Defying Gravity: caption card disabled with "This video has no English caption." (the check
    ran when the page opened), Genius selected and tagged `current`, "Next: LRCLIB match"
    disabled. A Genius search for "defying gravity idina menzel" listed 8 hits, id 105865
    tagged `current`.
  - **B** (Defying Gravity `AoON1CyhQAM` to a different Genius hit with a picked LRCLIB
    candidate): Genius id 3550231 ("Defying Gravity", Idina Menzel, 40 lines; the preview
    started "Something has changed within me"). Step 2 with Title "Defying Gravity", Artist
    "Idina Menzel": 20 candidates, each "matches 34 of 40 lines", the video 4:17, the best fit
    preselected (id 28322312, 4:24, 7 s longer); the admin picked 28220808 (3:47, 30 s
    shorter) and opened the timing preview. LRCLIB's `/api/get/28220808` answered 503 for the
    first six POSTs (15:29:08, then five tries 15:30:42-15:31:02 by the script's retry): each
    returned HTTP 400, the page showed the notification, no `regen_backup_*` folder was
    created and nothing queued. `get` answered 200 again at 15:32:12; the POST at 15:32:59
    queued `Repair`. Song Info then read "This song has a regen waiting or running.
    Processing", both buttons disabled. The job finished 15:36:00 (3 min 1 s). After: `.lrc`
    header `[ti:Defying Gravity] [ar:Idina Menzel / Idina Menzel] [al:Defying Gravity
    (Single)] [length:03:47] [lrclib_id:28220808]`, 43 stamped lines; bundle schema 11,
    `captured_at` 2026-10-22T19:36:00Z, `lyrics.genius` {id 3550231, "Defying Gravity",
    "Idina Menzel"}, `lyrics.lrclib.id` 28220808, `lrclib_fill` `eligible` false, reason
    `arm_a_bail`, 0 filled, 40 lines, 33 timed. The backup `regen_backup_20261022T193259Z`
    holds 13 files, all of that song. (Song Info's tiles were not captured after B; the next
    two rows are the ones recorded.)
  - **E** (the no-YouTube-ID song, Josh Gad `In Summer`, to Genius with LRCLIB `None`): the
    caption card was disabled; Genius 358333 (tagged `current`), LRCLIB None. 15:36:01-
    15:37:48 (1 min 47 s). The log says "No YouTube id for Josh Gad - In Summer ...; YTASR 3rd
    source unavailable". After: `.lrc` is `[lrclib_skipped:1]` (19 bytes); bundle genius id
    358333, `lyrics.lrclib` without an id, `lrclib_fill` reason `no_mapping`, 31 lines, 29
    timed (as before). Song Info: `Genius, up to date | 94%, 2 guessed | Skipped, skipped by
    you`; Picks: Genius "In Summer" Josh Gad, LRCLIB Skipped, Captions not used. One Genius
    hit for that search (id 6700027) lists hundreds of names as its artist (see below).
  - **C** (Defying Gravity again, same Genius pick, LRCLIB `None`): 15:38:35-15:40:58 (2 min 23
    s). After: `.lrc` `[lrclib_skipped:1]` (19 bytes); bundle `captured_at`
    2026-10-22T19:40:58Z, genius id 3550231, `lyrics.lrclib` without an id, `lrclib_fill`
    `eligible` false, reason `no_mapping`, 40 lines, 33 timed. Song Info: `Genius, up to date
    | 82%, 7 guessed | Skipped, skipped by you`; Picks: Genius "Defying Gravity" Idina Menzel,
    LRCLIB Skipped; Alignment: 33 of 40 timed (lyric aligner 7, transcription 9, YouTube
    captions 18, guessed 7), LRCLIB fit "Skipped: you chose no match."; History: Current 22
    Oct (Genius · Idina Menzel; no LRCLIB; 33 of 40, v11), Backup 22 Oct (LRCLIB 3:47
    changed; 33 of 40), Backup 19 Oct (Genius · Kristin Chenoweth; LRCLIB 5:54; 51 of 89,
    v11), Backup 21 Sep (LRCLIB 5:54 added; v10), Backup 16 Jul (no LRCLIB; v8).
  - **D** (Regenerate from Song Info, reuse): "Queued. It runs after any new downloads.",
    both buttons disabled. 15:41:52-15:44:10 (2 min 18 s). After: `.lrc` still the skip marker
    (19 bytes), bundle genius id 3550231, `lrclib_fill` reason `no_mapping`, 40 lines, 33
    timed, `captured_at` 2026-10-22T19:44:10Z.
  - Queen (`fJ9rUzIMcZQ`) **caption** repair: the caption card enabled ("Use the video's
    caption as the lyrics."), tagged `current` and preselected, button "Regenerate song";
    queued while D ran, 15:44:11-15:48:22 (4 min 11 s). After: bundle origin `srt`, 65 lines,
    65 timed (as before), `.srt` and `.ass` byte-identical to before (the fetched caption
    equals the old one), the leftover `subtitles/*.en.vtt` gone (the reset wipe). Song Info:
    `YouTube captions, up to date | 100%, 0 guessed | -, Genius songs only`.
  - Eason Chan (`8NJVNkzhJM4`) **transcribe** repair: tagged `current`, caption card
    disabled ("This video has no English caption."); 15:48:23-15:49:45 (1 min 22 s). After: no
    bundle, `.ass` and `.srt` rewritten. Song Info: `No lyrics | - | -`.
  - Hash diff after the runs (`hashdiff.py`): before 114, after 143: added 42 (the six backup
    folders: 13, 10, 6, 6, 4, 3 files), removed 13 (the reset wipe's diagnostic files:
    Defying Gravity's `armC`, `armW`, `baseline`, `edgereplay`, `edgesnap`, `scaffold` `.ass`
    and `.timing.json`; Josh Gad's `baseline`, `edgereplay`, `edgesnap`, `scaffold` `.ass` and
    `.timing.json`; Queen's `.en.vtt`), changed 9 (three bundles, Defying Gravity's `.ass`,
    `.srt`, `.lrc`, Josh Gad's `.lrc`, Eason Chan's `.ass` and `.srt`). The four songs were
    then put back from each one's first backup folder (30 files copied): the scratch library
    is 114 identical files, 0 removed, 0 changed, plus the 42 backup files. Defying Gravity's
    Song Info afterwards: `Genius, up to date | 57%, 38 guessed | Not used, 97 s longer`,
    Picks Kristin Chenoweth and LRCLIB 5:54.
  - Layout was looked at in the same Edge run. Found by looking and fixed before the commit:
    the two preview boxes were `<pre>` and clipped sideways (Bulma's `pre` rules beat
    `white-space: pre-wrap`), now `<div>`s (`scrollWidth > clientWidth` false for both in the
    runs); and the Genius hit above made one row several screens tall, so a result row's
    secondary line is clamped to two lines (the tallest row measured 114 px afterwards, no
    sideways page overflow). The song name was a second large heading and is now a quiet line.
  - Stopped with `taskkill /F /T` on the listener's pid (four times, for template changes and
    at the end); afterwards 5555 and 5556 were free and no python or mpv process remained
    besides `TPython.exe` (the background shells reported exit 1 because of that).
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the
  Phase 0 manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, the same 12 files
  under `zh_probe/phase0/` as the earlier rows; nothing else differs. Output:
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\manifest_compare_phase6.txt`. The real
  library was not read by the app or any tool of this phase.
- **pre-commit:** `--files <the eight changed files>`; Black reformatted two test files the
  first time, the second pass passed every hook, and again after the last edit. Import smoke:
  `library_tools`, `routes.song_info`, `karaoke`, `app`.
- **Seen, not changed:**
  - A repair is a reset job: a failure after its wipe leaves the song without its karaoke
    file until it is regenerated (D2). Everything that can be known before queueing refuses
    before the backup and the wipe.
  - Two simultaneous Repair POSTs for one song can both pass the busy check; the second
    `enqueue_regen` refuses and both have made a backup folder (Regenerate behaves the same).
  - A failed LRCLIB search (503, timeout) looks like "no results": `lrclib.search` returns
    `[]` on any failure. LRCLIB's get-by-id was down for about two minutes during the run,
    which the repair handled as above (HTTP 400, nothing written).
  - Keeping the current Genius pick while changing only the LRCLIB match means searching
    Genius and picking the hit tagged `current` (the plan has no one-tap keep here).
  - `lrclib.search` cleans the typed terms with `clean_key` (trailing parentheses dropped), so
    typing "(Live)" doesn't narrow the search.
  - The History tab lists a skip marker's version as "no LRCLIB" (the bundle has no LRCLIB
    id); the tile and Picks say Skipped (Phase 4's wording).
  - `/lyrics_search`, which the page reuses as the plan says, is open to guests (the search
    page's picker uses it).
  - The page script has no automated test; its checks are the render tests (no `.html(`, the
    handed-over values) and the Edge run above.

### Phase 6.1

Executed 2026-10-22 by Opus 5.5, starting from `d6fa927` (the approved Phase 6.1 section,
clean; the suite there is the `9dd41c4` one: 4 failed, 1949 passed, 2 skipped). Code commits,
in the section's order:

- `a14906a` fix(library): a new Genius pick drops the LRCLIB search still loading
  (`song_repair.html`, `test_library_routes.py`; +9/-1)
- `e414e43` fix(library): the repair page doesn't claim a video has no caption when the
  check failed (`song_repair.html`, `test_library_routes.py`; +7/-1)
- `7a4a30e` refactor(library): one length-gap rule, and the LRCLIB fit line comes from the
  server (`library_status.py`, `library_tools.py`, `routes/song_info.py`, `song_repair.html`,
  `test_library_routes.py`, `test_library_status.py`; +96/-48)
- `febeb2c` feat(library): a repair uses the LRCLIB record its search listed
  (`library_tools.py`, `test_library_tools.py`; +96/-6)

Facts:

- **Probes before the fix** (the review's scratchpad,
  `...\65fef55e-e098-476e-9ae8-e45f76710fac\scratchpad\p6review\`; the page rendered at
  `d6fa927` with `test_dump_repair_page.py` to `page_before.html`):
  - `stale_lrclib.mjs page_before.html ... asis`: `search was for genius_id: 7`; `step 2
    heading: Genius pick: Defying Gravity · Idina Menzel.`; listed `Defying Gravity best fit
    Kristin Chenoweth 5:54 · 97 s longer matches 80 of 89 lines` and the None option; `send
    enabled: true`; POST body `genius_id: 8, lrclib_id: 501`.
  - The same with `fix`: listed only the None option, `send enabled: false`, POST body
    `genius_id: 8, lrclib_id: null` (jsdom's `trigger` on the disabled button, as the section
    says).
  - `probe_caption_fail.py <scratch>\capfail`: `timeout -> CaptionCheck(found=False,
    wpm=None, passed=False)` and `http 403 -> CaptionCheck(found=False, wpm=None,
    passed=False)`, after yt-dlp's warnings "subtitle download timed out" and "HTTP Error
    403: Forbidden".
- **6.1a probe after the fix:** the page rendered at the fix (`page_after61a.html`) with
  `stale_lrclib.mjs ... asis` prints `search was for genius_id: 7`, the same heading, listed
  only `NoneSkip LRCLIB. Guessed lines stay guessed.`, `send enabled: false`, POST body
  `lrclib_id: null`: the `fix` run's output above. Rerun on the page at `7a4a30e`
  (`page_after61c.html`): the same first four lines.
- **6.1c page check** (a new jsdom probe, `fit_line.mjs`, set up like `stale_lrclib.mjs`, with
  an LRCLIB answer carrying the new fields; not committed), on the page at `7a4a30e`: `video
  length: "video is 4:17"`; `fit: "4:19 · within a few s" class: "rp-good"`, `fit: "5:54 · 97
  s longer" class: "rp-bad"`, `fit: "" class: ""`, each followed by `matches 3 of 4 lines`;
  the best fit preselected. The old page's own text for the 97 s match was `5:54 · 97 s
  longer` (the `asis` run above).
- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`):
  - At `7a4a30e`: 4 failed, 1955 passed, 2 skipped (121.2 s).
  - At `febeb2c`: **4 failed, 1959 passed, 2 skipped** (121.7 s); passed = 1949 + 10.
  - The four failures are the baseline's four (ids unchanged).
  - New tests:
    - `TestRepairPage` 2: 6.1a's handler bumps `lrclibSeq`; 6.1b's text is present and the
      old text absent.
    - `TestLengthGap` 2 (`test_library_status.py`).
    - `TestLrclibSearchRoute` 3, replacing `test_the_length_rule_comes_from_song_info`:
      - `fit` and `fit_near` for a near, a far longer, a far shorter and a length-less
        match, with `video_length`;
      - no video length;
      - the text follows a patched `_LENGTH_GAP_NOTED_S`.
    - `TestRepairUsesTheListedRecord` 4 (`test_library_tools.py`):
      - a listed record is queued with `get_record` raising;
      - with no search, the repair asks `get_record`;
      - a record without an id isn't remembered;
      - the cap holds, with a record listed again counting as newer.
  - The existing `duration_diff_s` and Genius cache tests are unchanged and pass.
- **Mutation checks** (each reverted; failures counted over `test_library_routes.py`,
  `test_library_status.py` and `test_library_tools.py`; script `p6review\mutate61.py`, inputs
  `mut61c.json` and `mut61d.json`):
  - 6.1a: the bump removed. The `TestRepairPage` test fails (1). The page rendered from it
    (`page_mut61a.html`), run through `stale_lrclib.mjs ... asis`, lists the stale `Defying
    Gravity best fit ... 5:54 · 97 s longer` again.
  - 6.1b: the old wording put back: 1.
  - 6.1c:

    | Mutation | Failures |
    |---|---|
    | the gap's sign flipped | 7 |
    | the gap taking a non-number | 1 |
    | Song Info's gap returning None | 3 |
    | the threshold hard-coded to 5 | 1 |
    | near tested on the signed gap | 1 |
    | near False without a gap | 2 |
    | the match length left out | 3 |
    | a far gap reading "within a few s" | 1 |
    | no video length | 1 |

    The page's tones swapped: `fit_line.mjs` prints `rp-bad` for the near match and
    `rp-good` for the far one. The probe prints; it doesn't assert.
  - 6.1d:

    | Mutation | Failures |
    |---|---|
    | the search remembering nothing | 2 |
    | the repair ignoring the remembered record | 2 |
    | a record without an integer id keyed anyway | 4 |
    | a stored-again entry keeping its old place | 1 |
    | the caches never evicting | 2 |
    | the LRCLIB cache sized by the Genius constant | 1 |
    | the Genius cache sized by the LRCLIB constant | 1 |
    | LRCLIB asked before the remembered record | 2 |

  - None survived.
- **Differences from the section's text:**
  - 6.1c:
    - `song_info._length_gap_s(status)` stays, as a one-line wrapper over `length_gap_s`
      (its two callers pass the same bundle values).
    - Song Info now treats a match length in the bundle that isn't a number as missing;
      before, it raised.
    - The match length in `fit` is shown only when it is a number (LRCLIB data), the same
      guard as the gap's.
    - A length-less match with no gap has `fit` `""` and `fit_near` null.
    - The page keeps the server's text in `state.videoLength`, in place of `videoSeconds`.
  - 6.1d:
    - Only records whose id is an integer are remembered, since the repair POST accepts
      only an integer id. That also covers "records without an id".
    - `_remember(cache, key, value, size)` is a module function that both caches call under
      their own lock.
    - `_remember` re-inserts a key that is stored again, so "oldest out" is by when an entry
      was last stored. The Genius cache only stores on a miss, so it behaves as before.
    - The two refusals ("LRCLIB didn't return that match", "no synced lyrics") check
      whichever record was found. A listed record always has synced lyrics.
    - The plan holds the remembered dict itself; its one reader is `write_lrc`.
- **pre-commit:** `--files` with each commit's changed files. All hooks passed on the first run
  each time, with no reformatting. Import smoke: `library_status`, `library_tools`,
  `routes.song_info`, `karaoke`, `app`.
- **No app run** (6.1f). Nothing in this phase started the app, ran a pipeline or read a song
  library, so the real-library manifest was not compared.
- **Seen, not changed:** the mockup board `RepairGenius.dc.html` still shows "This video has
  no English caption." It is a design reference, and the section changes the template only.

### Phase 7

Executed 2026-10-22 by Sonnet 5.5, starting from `8b6e4a4` (the Phase 6.1 record, clean). Two
code commits (the plan allows the split):

- `0541907` feat(library): bulk regen runs with a caption check and saved picks (5 files,
  +1176/-5: `library_tools.py` +395, `karaoke.py` +2, `test_library_tools.py`, and the three
  fixtures that build `LibraryTools`: `test_library_routes.Env`, `test_processing_routes`,
  `test_library_tools.make_tools`).
- `ecbde50` feat(library): pages for bulk runs: the Library tools card, the preview and the
  pick pass (6 files, +1307/-6: `routes/library.py` +185, `library_run.html` new,
  `pick_pass.html` new, `processing.html`, `test_library_routes.py`, `test_processing_page.py`).

- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`, 136.4 s at
  `ecbde50`): **4 failed, 2067 passed, 2 skipped**; passed = 1959 + 108 new. The four failures
  are the baseline's four (ids unchanged). New tests:
  - `test_library_tools.py` 55: `TestOpenRun` 10 (the three modes against the D5 table with the
    checks asked, parametrized; library-only songs; a second run refused; an unknown mode and an
    empty run refused; the view's fields; each song's source today; a crashing check; the check
    counts), `TestRunPicks` 17, `TestRunState` 14 (restart keeps checks and picks; a run left
    mid-check resumes only its unchecked songs; a song gone from disk drops out; a pick the song
    can no longer take is dropped; five unusable state files; a failed write is logged; discard,
    and a closed run gets no more checks), `TestQueueRun` 14 (waits for checks and picks; the
    plan and `reset` flag and label per mode; one whole-folder backup before the first job;
    skipped, busy and turned-away songs; nothing to queue; a failed backup; a song that lost its
    lyrics refused before the backup).
  - `test_library_routes.py` 49: `TestRunAccess` 8, `TestOpenRunRoute` 12, `TestRunPages` 11,
    `TestRunPickRoutes` 15, `TestRunQueueRoute` 3.
  - `test_processing_page.py` 4: the three Preview buttons with their counts; the banner and
    its in-place confirm; a guest gets no run controls; the tab is read from the URL at once.
  - Existing tests changed only in their fixtures (the new fifth argument of `LibraryTools`).
- **Mutation checks** (77; each reverted; failures counted over the touched test files; scripts
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\mutate7.py` and `mutate7b.py`). Service,
  52 checks, failures per check:

  | Mutation | Failures |
  |---|---|
  | a song with no YouTube id is checked | 3 |
  | a reset treated like the other modes | 5 |
  | a transcribed song checked in a reprocess | 1 |
  | a song with a source to replay is checked | 3 |
  | a transcribed song in a reprocess not transcribed | 5 |
  | a reset reuses a song's source | 4 |
  | a reprocess never reuses | 15 |
  | a passing caption needs a pick | 23 |
  | a song with no YouTube id waits for a check | 16 |
  | a pick ignored | 8 |
  | keep goes to reuse | 2 |
  | a song still being checked takes a pick | 1 |
  | a song that needs no pick takes one | 1 |
  | a song outside the run not refused | 1 |
  | a bool is a Genius id | 1 |
  | typed text not trimmed or capped | 1 |
  | keep without a recorded Genius song accepted | 2 |
  | keep_all overwrites a pick | 2 |
  | keep_all keeps songs with no Genius song | 2 |
  | keep_all counts every song it looks at | 2 |
  | discard leaves the run in the file | 1 |
  | queue without waiting for the checks | 1 |
  | queue without waiting for the picks | 1 |
  | busy songs queued anyway | 2 |
  | busy songs not counted | 1 |
  | nothing to queue goes on to back up | 2 |
  | every job resets | 2 |
  | no job resets | 1 |
  | the wrong label | 1 |
  | the backup covers some songs only | 2 |
  | the run stays open | 1 |
  | a turned-away song not counted | 1 |
  | a skipped song queued | 4 |
  | a song that lost its lyrics not refused | 1 |
  | a caption song queues a reuse plan | 2 |
  | a Genius pick queued as a fetch | 2 |
  | a second run allowed | 1 |
  | an update lists every song | 10 |
  | an empty run opened | 1 |
  | the checks not started | 28 |
  | an unknown mode accepted | 1 |
  | a result not saved | 1 |
  | a check that crashes not caught | 1 |
  | a restart doesn't resume | 1 |
  | a song gone from disk stays | 1 |
  | a pick not checked again on load | 1 |
  | a saved check dropped | 2 |
  | a failed write raises | 1 |
  | skipped songs count as queueable | 1 |
  | a picked song leaves the to-pick count | 2 |
  | no song needs a pick | 1 |
  | a discarded run's thread goes on | survived |

  The survivor: the caption thread stopped in two places (before asking for a song, and
  before storing its answer) and either alone stopped it, so breaking the first changed
  nothing a test could see. The second check was removed (an answer for a closed run lands
  on the orphaned run object and writes the current state again, which changes nothing), a
  test now calls the thread's loop for a closed run while another run is open
  (`test_a_run_that_is_no_longer_open_gets_no_more_checks`), and the mutation fails 2 tests.
  Routes and pages, 25 checks, all caught: no admin guard on the open, status, pick, keep_all,
  queue and discard routes (1 each); no guard on the pages 2; a page with no run not sent to
  the tools tab 2; the pick page not waiting for the checks 1; a mode that isn't text 1; a
  song that isn't text 1; the note without the busy songs 1, without the backup 1; each song's
  source left raw 1; a Genius source read as captions 1; a pick answering without the run 2;
  the preview polling when nothing is checked 1; a song title as markup 1; a Genius hit as
  markup 1; a stale Genius answer used 1, a stale failure shown 1; the Preview buttons
  starting enabled 1; the tab read after the SPA dropped the hash 1; Update's Preview showing
  the wrong count 1; the banner without its in-place confirm 1.
- **Differences from the plan's text:**
  - `LibraryTools(processing_manager, song_manager, download_path, genius_client, state_path)`;
    `karaoke.py` passes `Path(get_data_directory()) / "library_tools" / "state.json"` (D4).
    The file holds `{"run": {mode, songs: {path: {check, pick}}}}` (the needs-a-pick list of
    Phase 8 joins it); a run read back at start is rebuilt over the songs still on disk
    (each song's status, and whether its bundle holds a source to replay, are read again).
  - `run_view()` returns the songs as one flat list in name order, each with its `group`
    (`checking`, `needs_pick`, `genius`, `caption`, `reuse`, `transcribe`, `skip`), instead of
    a dict of groups. `genius` is the group of a song with a Genius pick or a keep; a song's
    `needs_pick` says whether a pick decides it (true also once it has one), and the view
    carries `to_pick`, `picked`, `to_check`, `checked`, `checking` and `queueable` (songs not
    skipped). A song has `title`, `now` (in words, put there by the route), `query`
    (`default_query`), `poor`, `guessed`, `line_count`, `has_youtube_id`, `genius_id` (in
    place of `can_keep`: the pick page needs the id to tag the current hit; keep is offered
    when it is not null), `caption` (the check) and `pick`.
  - Songs of a run: `stale` is the songs with a bundle behind the current version
    (`SONG_LISTS["behind"]`), the other modes every video the library holds. A song
    with no bundle that isn't transcribed is "not processed" and sorts like any song with no
    source to replay.
  - `save_pick` takes a pick only for a song that needs one: any other song is refused ("That
    song doesn't need a pick."), as is one whose caption is still being checked. A pick is
    `{kind: genius, genius_id (an int, not a bool), title, artist}` (text trimmed to 200
    characters), `keep` (stores the bundle's Genius id), `transcribe` or `skip`; anything else
    is refused.
  - `queue_run` refuses before the backup while captions are checked, a song needs a pick, a
    reuse song has lost its bundle since the preview, or nothing would be queued (every song
    skipped or already waiting; the plan says it clears the run and returns the counts); the
    run stays open in each case. With songs to queue it takes the one whole-folder backup,
    queues, closes the run and returns `{queued, busy, backup}` (the folder's name). A song
    the queue turns away at the last moment counts as busy.
  - A state file that can't be written is logged and the run goes on in memory (nothing in
    the plan); an unreadable one is ignored at start.
  - Routes: `GET /library/run/picks` goes to the preview while captions are being checked;
    `POST .../pick` and `.../keep_all` answer with the run; `GET /library/run/status` answers
    `{"open": false}` with no run (the Library tools tab and the preview read it); `POST
    /library/run` rejects a mode that isn't text and a run with no songs.
  - The pick page opens a row's Genius search by itself, with the song's cleaned title in the
    box; a picked row shows Change, an unpicked one with a recorded Genius song shows Keep.
  - `processing.html`: the page script reads its tab from the URL when it first runs. The
    SPA's start-up (`spa-navigation.js`, upstream) rewrites the URL without its hash before the
    page's ready handler ran, so `/processing#tools` always opened Jobs. Found by driving the
    pages: Discard and "no run open" both go to `/processing#tools`.
  - The Preview buttons start disabled and wait for the counts (a run with no songs can't open).
- **Isolated app run** (Ground rules first, again before each start: nothing on 5555 or 5556, no
  python, mpv or pikaraoke process besides `TPython.exe`, GPU 509 MiB 0 %). Config and `APPDATA`
  as in the Phase 3 row (the scratch config has no admin password). The log says library
  `D:\shared\weblib-test`, `Scan: found 8 song(s) on disk`. The scratch library was hashed first
  (156 files, `scratch_before_p7.json`). It had no song behind, so three bundles (Eminem,
  Josh Gad, Backstreet Boys) were made behind by editing `schema_version` 11 to 10 (the originals
  kept for the restore). The pages were driven through headless Edge 155 over the DevTools
  protocol (`cdp7.py`, a 390 px emulated window), screenshots in
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\p7shots\`. App logs `app_run_phase7*.log`
  in the same folder.
  - Look-only pass, before the commit: Library tools tab, Reset all preview with its check
    progress, the pick page with a picker open, the banner and both in-place discards (tab and
    preview). Found and fixed before `ecbde50`: the hash loss above; the Preview buttons read
    "Preview3" (no gap between the word and the count; the button now has a gap).
  - The picker's own search for Defying Gravity returned "No Genius results.": the box holds
    the song's cleaned title, `'Defying Gravity' - Wicked 20th Anniversary Edition WICKED the
    Musical`, which Genius doesn't match. Typing `defying gravity idina menzel` listed 8 hits
    with the bundle's 105865 tagged `current`.
  - **1. Update stale songs** (the three made behind): Library tools tab showed `Preview 3`,
    `Preview 8`, `Preview 8`. The preview listed "Keeps its lyric pick (3)" (Backstreet Boys,
    Eminem, Josh Gad), no check box, `Queue 3 songs`. Queued 18:48:39; flash "Queued 3 songs.
    Backup: regen_backup_20261022T224839Z."; Jobs tab rows labelled `Update`. Jobs, in the
    order they ran: Backstreet Boys 18:49:02-18:52:31 (3 min 29 s), Eminem 18:52:31-18:55:49
    (3 min 18 s), Josh Gad 18:55:49-18:57:35 (1 min 46 s). All three `complete`. The behind
    count went 3 to 0 (`{"all":8,"behind":0,"no_lyrics":2,"poor":2}`); the bundles read v11 with
    new `captured_at`, 87 lines / 85 timed, 31 / 29, 39 / 39 (as before).
  - **2. Reset all.** Opened 18:58:30; the 7 caption checks (the song with no YouTube id isn't
    checked) were done at 18:59:37. Preview: "Needs a pick (6)" (Defying Gravity, Eason Chan,
    Eminem, Jay Chou, Josh Gad with "No YouTube ID: Genius or transcribe only", Happy Birthday;
    Defying Gravity and Jay Chou with "Looks poor: 38 of 89 lines guessed" and "26 of 42") and
    "Uses its YouTube caption (2)" (Backstreet Boys, Queen, each `Caption OK`), `Start picks
    (0 of 6 done)`. Pick page: chips `To pick 6`, `Picked 0`, `Looks poor 2`, Keep on four rows
    (not Eason Chan or Happy Birthday: no recorded Genius song), `Keep current pick for all 4
    not yet picked`, `Queue 8 songs (6 still to pick)` disabled. Picks made: Keep for
    Defying Gravity and Eminem; Josh Gad by Genius search `in summer josh gad` (hit "In
    Summer", Josh Gad, 358333, tagged `current`; the list also had one hit whose artist field
    is hundreds of names, clamped to two lines). `3 of 6 picked`; banner "Reset all is open: 3
    of 6 picked." App stopped (`taskkill /F /T`) and started again: the banner, the preview
    (`Start picks (3 of 6 done)`; "Needs a pick (3)", "Picked: Genius (3)", "Uses its YouTube
    caption (2)") and the pick page (`3 of 6 picked`, the three picked rows with their picks and
    Change) all came back. Then Keep for Jay Chou, Transcribe for Eason Chan, Skip song for
    Happy Birthday: `6 of 6`, `Keep current pick for all 0 not yet picked` disabled, `Queue 7
    songs`. The library was hashed before queueing (207 files,
    `scratch_before_reset_p7.json`). Queued 19:01:02; flash "Queued 7 songs. Backup:
    regen_backup_20261022T230102Z."; Jobs tab with the Now box and rows labelled `Reset`.
    Jobs, in the order they ran: Defying Gravity 19:01:02-19:04:30 (3 min 28 s), Backstreet
    Boys 19:04:30-19:08:04 (3 min 34 s), Eason Chan 19:08:04-19:09:29 (1 min 25 s), Eminem
    19:09:29-19:12:54 (3 min 25 s), Jay Chou 19:12:54-19:16:23 (3 min 29 s), Josh Gad
    19:16:23-19:18:15 (1 min 52 s), Queen 19:18:15-19:22:33 (4 min 18 s); 21 min 31 s from the
    queue to the last job. All seven `complete`, no `error_message`.
  - **After the Reset run** (hash `scratch_after_reset_p7.json`, `verify7.py`): the backup
    folder holds 51 files and the library had 51 in `subtitles`, `karaoke`, `lyrics` and
    `alignment_debug` when it was queued: 0 missing, 0 different, 0 extra. Library outside the
    backup folders: before 78, after 61: added 0; removed 17 (13 `karaoke/*.ass` diagnostic
    files: Defying Gravity's `armC`, `armW`, `baseline`, `edgereplay`, `edgesnap`, `scaffold`,
    Backstreet Boys' `cuealign`, `cuealign.sb_ctc_adapter`, `richsync`, Josh Gad's `baseline`,
    `edgereplay`, `edgesnap`, `scaffold`; 3 `lyrics/*.timing.json`; Queen's
    `subtitles/*.en.vtt`); changed 10 (the 6 bundles; Defying Gravity's and Eason Chan's `.ass`
    and `.srt`); identical 51, every `.lrc` among them. Happy Birthday (skipped): its 6 files
    identical, `.ass` still 11:55:44. Every other song's karaoke file was rewritten within its
    job's window and its bundle's `captured_at` is that job's end time. Songs after: Defying
    Gravity v11 origin genius id 105865, 86 lines / 50 timed (89 / 51 before: the keep pick is
    a sidecar plan, which fetches the Genius page again where the old bundle had replayed its
    stored lines); Backstreet Boys 39 / 39, Queen 65 / 65 (captions, `.srt` and `.ass`
    byte-identical to before), Eminem 87 / 85, Josh Gad 31 / 29, Jay Chou 42 / 16; Eason
    Chan and Happy Birthday still "no lyrics". Overview `{"all":8,"behind":0,"no_lyrics":2,
    "poor":2}`. `state.json` reads `{"run": null}` after queueing.
  - The app was stopped with `taskkill /F /T` on the listener's pid after each part that needed
    a restart and at the end; afterwards 5555 and 5556 were free and no python, mpv or
    pikaraoke process remained.
- **Restore** (`restore7.py`): the first backup's 51 files copied over the library, the 6
  original bundles put back, 0 files removed. Hash after (`scratch_restored_p7.json`) against
  before: before 156, after 258: added 102 (the two backup folders, 51 files each), removed 0,
  changed 0, identical 156.
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the
  Phase 0 manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, the same 12 files
  under `zh_probe/phase0/` as the earlier rows; nothing else differs. Output:
  `...\c192729b-188a-40ca-8bf1-a9cba38de26f\scratchpad\manifest_compare_phase7.txt`. The real
  library was not read by the app or any tool of this phase.
- **pre-commit:** `--files` with each commit's files (the first Black pass reformatted
  `test_library_tools.py`; the second pass passed every hook, and again after the last edit).
  Import smoke: `library_tools`, `karaoke`, `routes.library`, `app`.
- **Seen, not changed:**
  - A run's songs are what the files said when it opened (read again at a restart). A repair
    or regenerate of a song while the run is open isn't reflected; queueing refuses a song
    that was to reuse its lyrics and no longer can, and the admin opens the run again.
  - Queued regen jobs don't survive an app restart (D2) and queueing closes the run, so a
    restart with jobs waiting loses them and the run isn't there to open again from.
  - A caption check that fails (timeout, HTTP 403) is the same as "no caption" and sends the
    song to the pick list (6.1b's limit, in `download_manual_en_subs`).
  - The pick box starts as `default_query`, which keeps trailing words of a long YouTube
    title: Defying Gravity's search was empty until the box was edited.
  - `/lyrics_search` (reused as the plan says, open to guests) returns hits with huge artist
    strings; the row clamps them to two lines.
  - The pick page doesn't poll and sends the admin to the preview while captions are checked;
    a song whose caption is still unchecked can't take a pick.
  - A run with every song skipped or busy can't be queued; the admin discards it.
  - Update stale leaves out songs with no bundle (they aren't behind); Reprocess all and
    Reset all include them.
  - The queued note is the base template's flash, which fades after 3 s.
  - `spa-navigation.js` rewrites a page's URL without its hash at start (upstream file, not
    touched); only the Processing page reads its hash now.
  - Page scripts have no automated test beyond the render tests (no markup insertion, the
    polling rule, the stale-answer guard); their checks are those and the Edge run above.
  - The mockup boards say "Cancel reset" and show the primary button blue; the page says
    "Cancel" (the plan's word) and uses the theme's primary.

### Phase 7.1

Executed 2026-10-23 by Opus 5.5 (session `7793017c`), starting from `6c1f245` (clean). Scratchpad
for this row: `...\7793017c-e313-469d-b821-3298b30187fa\scratchpad\`. Six code commits, in order:

- `d280722` 7.1a fix(library): a caption check that couldn't run is tried again and can be checked
  again (10 files, +393/-45: `youtube_dl.py`, `library_regen.py`, `library_tools.py`,
  `routes/library.py`, `library_run.html`, `pick_pass.html`, four test files).
- `05322ee` 7.1b fix(library): a regen job stops before any change when Genius doesn't return its
  pick (3 files, +91/-2: `library_regen.py`, `test_library_regen.py`, `test_processing_manager.py`).
- `84a8220` 7.1c fix(library): a run read back at start keeps only this library's songs (2 files,
  +63/-1).
- `fc0699b` 7.1d fix(library): the run pages once every pick is made and while a pick saves
  (5 files, +47/-9: `library_run.html`, `pick_pass.html`, `processing.html`, two test files).
- `2d83e70` 7.1e refactor(library): one caption-check rule, and the library pages share their
  helpers (8 files, +80/-62; `static/library-pages.js` new, 23 lines).
- `1bc3c29` test(library): the Genius-check test never writes a real choice sidecar (1 file, +3).
  Found by the full suite: during 7.1b's mutation run ("the Genius check skipped"), the 7.1b test
  for a Genius pick Genius doesn't return went on into `prepare_lyrics` and wrote a real
  `%APPDATA%\pikaraoke\tmp\lyric_choices\dQw4w9WgXcQ.json` (`{"genius_id": 1}`, 09:51:37, Ken's real
  app temp folder, not the scratch one). It made `test_lyrics_fetch.py::TestBranchCSrtFallback`'s
  `test_srt_exists_sets_path` and `test_no_srt_sets_none` fail (6 failed, 2098 passed). The file
  was deleted (the folder then held 0 files); the test now patches `write_choice` and asserts it
  isn't called; the two mutations were run again (2 and 3 failures) and the folder stayed empty.

- **7.1a live yt-dlp check** (network only, no app; `live_ytdlp.py`, which wraps
  `subprocess.run` to record each call; output into `live_ytdlp_tmp\`). Before the fix, at
  `6c1f245`:

  | Video | Scratch song | Returned | yt-dlp exit | Last stderr line |
  |---|---|---|---|---|
  | `fJ9rUzIMcZQ` | Queen | path `probe.en.srt` | 0 | (empty) |
  | `1OwfYjemrYw` | Backstreet Boys | path `probe.en.srt` | 0 | (empty) |
  | `xFYQQPAOz7Y` | Eminem | None | 0 | (empty) |
  | `DYptgVvkVLQ` | Jay Chou | None | 0 | (empty) |
  | `8NJVNkzhJM4` | Eason Chan | None | 0 | (empty) |
  | `aF8voKa_3Us` | Happy Birthday | None | 0 | (empty) |
  | `AoON1CyhQAM` | Defying Gravity | None | 0 | (empty) |
  | `aaaaaaaaaaa` | (none) | None | 1 | `ERROR: [youtube] aaaaaaaaaaa: This video is unavailable` |

  After the fix (`fJ9rUzIMcZQ`, `xFYQQPAOz7Y`, `aaaaaaaaaaa`): a path (exit 0), None (exit 0),
  raised `CaptionDownloadFailed: yt-dlp subtitle download failed for
  https://www.youtube.com/watch?v=aaaaaaaaaaa: ERROR: [youtube] aaaaaaaaaaa: This video is
  unavailable` (exit 1). The STOP condition did not occur.
- **Suite** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`, 139.1 s at
  `1bc3c29`): **4 failed, 2100 passed, 2 skipped**; passed = 2067 + 33 new. The four failures are
  the baseline's four (ids unchanged). New tests by file: `test_youtube_dl.py` +1 (a
  three-case parametrized test replaced the two "returns None" tests), `test_library_regen.py` +5,
  `test_library_tools.py` +13 (`TestFailedCaptionChecks` 9; `TestRunState` 4, one of them
  parametrized over two spellings), `test_library_routes.py` +11 (`TestRunAccess` one more route;
  `TestRunRecheck` 4; three 7.1d render tests; three 7.1e render tests), `test_processing_page.py`
  +2, `test_processing_manager.py` +1. Changed: `test_a_check_that_fails_counts_as_no_usable_caption`
  became `test_a_check_that_crashes_counts_as_one_that_could_not_run` (pause patched to 0; the
  view's `failed` is 6); the two run-page and the repair-page markup tests read
  `static/library-pages.js` too.
- **Mutation checks** (`mutate71.py <step>`; each reverted; failures counted over the listed test
  files):

  | Step | Mutation | Failures |
  |---|---|---|
  | 7.1a | no second try | 5 |
  | 7.1a | the pause not ended by a discard (a fresh Event waited on) | 1 |
  | 7.1a | a failed download stored as a finished check (`check_caption`) | 1 |
  | 7.1a | a crashing check stored as a finished one (`_measure_caption`) | 1 |
  | 7.1a | the recheck clearing picked songs | 2 |
  | 7.1a | `failed` counts picked songs | 1 |
  | 7.1a | `failed` always 0 | 5 |
  | 7.1a | the recheck allowed while checking | 1 |
  | 7.1a | the recheck doesn't start the checker | 3 |
  | 7.1a | the download returns None on an error exit | 1 |
  | 7.1a | the download returns None on a timeout | 1 |
  | 7.1a | the download returns None without yt-dlp | 1 |
  | 7.1a | `fetch_caption` lets the failure through | 1 |
  | 7.1a | the recheck route not admin-only | 1 |
  | 7.1a | the failed box shown while checking | 1 |
  | 7.1a | no failed line on a preview row | 1 |
  | 7.1a | no failed line on a pick row | 1 |
  | 7.1b | the Genius check after the wipe | 2 |
  | 7.1b | the Genius check skipped | 3 |
  | 7.1c | the folder test removed | 2 |
  | 7.1c | the folders compared as typed (no `normcase`/`abspath`) | 1 |
  | 7.1d | the banner reads `to_pick > 0` | 1 |
  | 7.1d | the preview reads `to_pick > 0` | 1 |
  | 7.1d | Keep not disabled while a pick saves | 1 |
  | 7.1d | a save's answer closes any picker | 1 |
  | 7.1e | the derived rule inverted | 47 |
  | 7.1e | the derived rule reads the stored check | 1 |

  7.1d through the probes (`mutate71.py d-probes`: mutate, dump the pages, run both probes,
  revert): picks left read as `to_pick > 0` → `3. all picked: go: Start picks (3 of 3 done) |
  'queued only after the last pick' shown: true`, `3. tap go -> ["Not implemented: navigation
  (except hash changes)"] | posts: 0`; Transcribe not disabled → `3. while saving, disabled:
  Transcribe false Skip true Use pick true`; a save's answer closes any picker → `3. after the
  save answer: picker open: 0`; no your-pick tag → `4. Change hits: [ "Defying
  GravitycurrentKristin Chenoweth", "Defying GravityIdina Menzel" ]`.
- **Probes** (copied from the review's `p7review\` to `p71\`, not committed). Changes to the
  copies: `pick_probe.mjs`'s Transcribe tap during the save is a native `click()`, and it also
  prints the three picker buttons' `disabled` during the save and whose picker is open after the
  answer; `preview_probe.mjs` prints the URLs posted by the all-picked Go tap; after 7.1e
  `run_pages.mjs` loads `static/library-pages.js` (next to the jQuery path) before the page
  script. Pages dumped with `test_dump_run_pages.py` (`PYTHONPATH=tests/unit`, `--rootdir` the
  probe folder; 2 passed) into `p71\pages_71d\` (at `fc0699b`) and `p71\pages_71e\` (at
  `2d83e70`). Before (the plan's text, at `3b863af`) and after (both dumps print the same):
  - `3. all picked: go: Start picks (3 of 3 done) | 'queued only after the last pick' shown:
    true` and `3. tap go -> ["Not implemented: navigation (except hash changes)"] | posts: 0`
    became `3. all picked: go: Queue 3 songs | 'queued only after the last pick' shown: false`
    and `3. tap go -> [] | posts: 1 [ "/library/run/queue" ]`.
  - `3. posts so far: 1` (Transcribe tapped through jQuery's `trigger`) and `3. after the save
    answer: picker open: 0` became `3. while saving, disabled: Transcribe true Skip true Use pick
    true`, `3. posts so far: 1` (a native tap), `3. after the save answer: picker open: 1 | ... |
    picker for: No Id Song`, `3. No Id's search answer after that: picker open: 1`.
  - `4. Change hits: [ "Defying GravitycurrentKristin Chenoweth", "Defying GravityIdina Menzel" ]`
    became `[ "Defying GravitycurrentKristin Chenoweth", "Defying Gravityyour pickIdina Menzel" ]`.
  - Unchanged from before: `6. queue posts after two taps: 2` (jQuery `trigger` on a disabled
    button; `0. ... two native taps on Queue -> posts: 1`), `4. two taps on Discard run -> posts:
    2` on the preview.
- **7.1e helper copies:** `fill`, `el` and `errorOf` hashed alike (md5 of the indent-stripped
  block `86161f58...` in `song_repair.html`, `library_run.html` and `pick_pass.html`; `fill`
  `3d0c0da7...` in all four, `processing.html` included). No call to them before their
  declaration's line in any of the four page scripts.
- **Isolated app run** (Ground rules checked first and again before the start: nothing on 5555 or
  5556, no python, mpv or pikaraoke process besides `TPython.exe`, GPU 1092 MiB 8 %). `APPDATA` the
  Phase 3 session's scratch folder (`...\66751cff-...\scratchpad\appdata`; its config's
  `download_path` is `D:/shared/weblib-test`, no admin password; `state.json` read `{"run":
  null}` before). Log `app_run_phase71.log`: `Background library scan starting:
  D:\shared\weblib-test`, `Scan: found 8 song(s) on disk`. Scratch library hashed before
  (`scratch_before_p71.json`, 258 files). Headless Edge over DevTools at 390 px (`cdp71.py`, a copy
  of the Phase 7 `cdp7.py`; steps `steps71.py`, then `steps71b.py` and `steps71d.py` resuming after
  two step-file errors of mine, `steps71c.py` a debug of the second); output `drive71*.txt`,
  screenshots `p71shots\01`-`10`. Nothing was queued; Queue, Regenerate, Next and Send were never
  tapped.
  - Library tools: `Preview 0`, `Preview 8`, `Preview 8`. Reset all: while checking `Checking
    captions… 0 of 7`; checked `7 of 7`, status `failed 0`, `to_pick 6`; the failed box hidden; go
    `Start picks (0 of 6 done)`, the after-picks note shown; "Needs a pick (6)", "Uses its YouTube
    caption (2)" (Backstreet Boys, Queen, `Caption OK`).
  - Pick page: `0 of 6 picked`. Josh Gad by Genius search `in summer josh gad` (hit `In Summer`,
    `current`, Josh Gad) then Use pick; Change on it, the same search: `In Summer` tagged `current`
    and `your pick`. Keep: Defying Gravity, Eminem, Jay Chou. Eason Chan → Transcribe, Happy
    Birthday → Skip song. Then `6 of 6 picked`, `Queue 7 songs` enabled, `Keep current pick for all
    0 not yet picked`.
  - Preview with every pick made: go `Queue 7 songs` (enabled), the after-picks note hidden;
    "Picked: Genius (4)", "Uses its YouTube caption (2)", "No lyrics (transcribe) (1)", "Skipped
    (1)".
  - Processing reached through the SPA (Home, then the nav link; the same document before and
    after), Library tools tab: `libraryPages` an object, the banner `Reset all is open: ready to
    queue.`, no window error. A full load of `/processing#tools` showed the same banner. Discard →
    the in-place confirm → Discard run → `/library/run/status` `{"open": false}`.
  - Song Info (Queen) → Repair lyrics (the button loads the page in full), and the repair URL
    loaded directly: both times `libraryPages` an object, caption line `Use the video's caption as
    the lyrics.` (choosable), Genius search `bohemian rhapsody queen` 8 hits (first `Bohemian
    Rhapsody` Queen).
  - App stopped with `taskkill /F /T` on the listener's pid; afterwards 5555 and 5556 free, no
    python, mpv or pikaraoke process. Scratch library after (`scratch_after_p71.json`): before 258,
    after 258, added 0, removed 0, changed 0, identical 258.
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the Phase 0
  manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, the same 12 files under
  `zh_probe/phase0/` as the earlier rows. Output `manifest_compare_phase71.txt`. The real library
  was not read by the app or any tool of this phase.
- **pre-commit:** `--files` with each commit's files; every hook passed, except Black reformatting
  one test signature in `test_library_tools.py` at 7.1c (restaged, then passed). Import smoke:
  `youtube_dl`, `library_regen`, `library_tools`, `routes.library`, `processing_manager`,
  `karaoke`, `app`.
- **Differences from the plan's text:**
  - `recheck_captions` also refuses while the caption thread is still alive (it is between
    storing its last answer and ending); a second thread would check the cleared songs twice.
  - A song's failed check is told by `_Entry.check_failed` (a failed check and no pick), used by
    `run_view`'s `failed` and by `recheck_captions`.
  - `_load_run` counts a saved song of another folder before it tests the file exists, so the
    log line counts every song of another library, gone or not; the line is `Dropped N song(s) of
    the saved run that are not in the library <folder>`.
  - The Check again box's button is 44 px tall (`.lr-failed .button`); the box's sentence and the
    row line use the theme's warning colour, as the poor note does.
  - The Genius check in `prepare_regen_job` logs `Genius pick <id> for <song> refused: <reason>`.
- **Seen, not changed:**
  - The pipeline's own Genius fetch, seconds after 7.1b's check, still falls back to a caption
    or transcribes when it fails in that window (the plan's text).
  - The repair page's caption line (6.1b's one wording) covers a failed check too (7.1f).
  - The Processing page loads the run banner and the counts only when its Library tools tab is
    shown; the nav link opens Jobs.
  - The preview's Discard run takes two posts on two quick native taps (it has no sending
    guard); discarding twice is harmless (the second finds no run).
  - A failed caption check could not be forced live; the unit tests cover it.

### Phase 7 checks (Ken's live pass of Phases 4-7.1)

Model: Claude Opus 5.5 (prep, log reading, restore); Ken clicked. 2026-10-23, HEAD `330e9fb`.

- **Procedure:** the Claude Doc "Web library tools: check procedure (Phases 4-7.1)",
  https://claude.ai/artifact/Lt67nBswVwNNZptZnYMq47 (Blocks A-E, every box checked). Guest view,
  a regen waiting on a playing song, a restart mid-picks, a failed regen with Retry, Genius not
  answering (7.1b) and Phase 8 not covered.
- **Setup:** isolated app from the worktree on 5556 (`APPDATA` the session's scratch folder
  `...\96b3d5a8-e290-4c0d-bd2a-57b2d05397dd\scratchpad\appdata`, a copy of Ken's config, no admin
  password, `--download-path D:\shared\weblib-test`); `Scan: found 8 song(s) on disk`. Log
  `...\96b3d5a8-...\scratchpad\app.log`. Scratch library hashed before (`weblib_start.json`, 258
  files, digest `be5cc8bf7ad573c5`). EM, BSB and JG bundles set from `schema_version` 11 to 10
  (`mark_behind.py`, originals in `bundle_originals\`). Ken's app on 5555 off throughout.
- **Job timeline (app.log):**

  | Time | Event |
  | -------- | ------------------------------------------------------------------------------------ |
  | 11:04:19 | DG Repair queued and started (Genius Idina Menzel, a non-best-fit LRCLIB match) |
  | 11:05:17 | EM Regenerate queued |
  | 11:06:48 | `zzzzzzzzzzz` direct download failed: `This video is unavailable` |
  | 11:08:47 | DG Repair complete |
  | 11:10:23 | NEW (`Baby Hotline - Jack Stauber---jbTj2M3vmts`) processing complete, ahead of EM |
  | 11:10:24 | EM Regenerate started |
  | 11:15:39 | EM complete |
  | 11:21:26 | Update stale queued BSB and JG; BSB started |
  | 11:23:06 | `LRCLIB search failed for 'defying gravity' / 'idinal menzel': 503` (C2's search) |
  | 11:23:22 | DG second Repair queued (LRCLIB None) |
  | 11:25:05 | BSB complete; JG started |
  | 11:26:53 | JG complete; DG second Repair started |
  | 11:29:19 | DG second Repair complete |
  | 13:36:33 | Reset all queued 6 (DG, BSB, EC, EM, JG, Q; JC and HB skipped); DG started |
  | 13:38:59 | DG complete; BSB started |
  | 13:42:35 | BSB complete; EC started |
  | 13:44:04 | EC complete; EM started |
  | 13:47:37 | EM complete; JG started |
  | 13:49:34 | JG complete; Q started |
  | 13:54:03 | Q complete |

  No `Regen failed` and no traceback in the log. Other ERROR lines: the yt-dlp self-upgrade at start
  (expected under uv) and `yt-dlp preview info timed out` at 11:06:03 (the picker preview).
- **Ken's findings:**
  - A4 (procedure text): a search-page download also adds the song to the singing queue, so NEW
    started playing at 11:06. The procedure was updated.
  - B1 (procedure text): the procedure said spinners don't restart; the design has no spinners.
    The procedure was updated.
  - B2, the four lists: each Library card row opens `library_songs.html` as its own page (as 4d
    specifies), and that page has no back button. Ken wants the lists to expand inline on the
    Library tools tab.
  - Feature request (during D7): the admin uploads their own lyric text file as the lyric source
    for a Repair, Regenerate or Reset, so hand-checked lyrics can replace the Genius, caption or
    transcribed text. Outside Phases 4-8; where it sits is Ken's call.
  - C, D and E: no differences reported.
- **Claude's findings from the log and the files:**
  - With the LRCLIB skip marker in place, DG's second Repair (11:26:59) and its Reset (13:36:40) both
    log `LRCLIB: variant available for fill (<the .lrc>)`. After the Reset the `.lrc` is the
    20-byte `[lrclib_skipped:1]` marker, and the bundle's `joint_stats.lrclib_fill` reads
    `n_cues_mapped 0`, `eligible false`, `reason no_mapping`, `fills []`. The line fires on the file
    existing.
  - Delete song (C3) left `alignment_debug/<NEW>.json`, `lyrics/<NEW>.lrc` and
    `subtitles/<NEW>.srt.generated`. `SongManager._get_companion_files` lists only the `.srt`, the
    vocal and nonvocal stems and the `.ass`; `rename` uses the same list. This branch's diff to
    `song_manager.py` (5 added lines) does not touch either.
  - After the pass, the library lacked Q's `subtitles/<Q>.en.vtt` and the probe-harness files of DG,
    BSB and JG (`.armC.ass`, `.armW.ass`, `.baseline.ass`, `.edgereplay.ass`, `.edgesnap.ass`,
    `.scaffold.ass`, `.cuealign*.ass`, `.richsync.ass`, `lyrics/*.timing.json`); each was in one of
    this pass's backups. Q's Reset ran on its `.srt` (`cue-align: 65 cues -> 9 sections`) and
    wrote no new `.en.vtt`.
- **Restore:** the app stopped with `taskkill /F /T` on the listener's pid (7244); 5556 free. Scratch
  library after the pass: 364 files. `restore_weblib.py` copied back the 27 files that were changed
  or missing, each from a file with its start hash (this pass's backups or `bundle_originals\`),
  removed NEW's three leftovers, and removed this pass's five backup folders
  (`regen_backup_20261023T150419Z`, `...150517Z`, `...152126Z`, `...152322Z`, `...173633Z`; none in
  the start map). Re-hash `weblib_after.json`: 258 files, digest `be5cc8bf7ad573c5`, byte-identical
  to `weblib_start.json`.
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the Phase 0
  manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, all 12 under `zh_probe/`, as in
  the earlier rows. Output `...\96b3d5a8-...\scratchpad\manifest_compare_phase7check.txt`.

### Phase 7.2

Executed 2026-10-23 by Opus 5.5 (session `5f459679`), starting from `f67a970` (clean). Scratchpad
for this row: `...\5f459679-8ee1-4028-ade6-efafb3573f16\scratchpad\`. Two code commits, in order:

- `71d565e` 7.2a feat(processing): the Library card's song lists open inline on the tab (5 files,
  +135/-83: `routes/library.py`, `processing.html`, `library_songs.html` deleted,
  `test_library_routes.py`, `test_processing_page.py`).
- `2c352b4` 7.2b fix(lyrics): the log names an LRCLIB skip as a skip, not a fill source (2 files,
  +30/-1: `lyrics_fetch.py`, `test_lyrics_fetch.py`).

- **Baseline** (`PYTHONIOENCODING=utf-8 uv run --no-sync python -P -m pytest -q`, at `f67a970`,
  141.1 s): **4 failed, 2100 passed, 2 skipped**, the baseline's four ids. The run collected before
  7.2a's first edit was saved (the old page-reading list tests passed).
- **Suite at `2c352b4`** (142.7 s): **4 failed, 2103 passed, 2 skipped**; the same four ids; passed
  = 2100 + 3. `test_library_routes.py` `TestSongListsRoute`: 5 tests became 6 (each row's `name`,
  `subline`, `info_url`; the other lists' sublines; empty `rows: []`; unknown and missing list 400
  JSON; guest 403 JSON; a song named `Rock & Roll #1 100% Café---aaaaaaaaaaa.mp4` whose `info_url`
  opens its Song Info, 200, name in the page). `test_processing_page.py`: the four-links test
  became "four `data-list` buttons, no `href="/library/songs`". `test_lyrics_fetch.py`
  `TestBranchALrclib`: +1 test parametrized over a skip marker and a real `.lrc` (+2).
- **Server** (`/library/songs`): `_list_title`, `abort` and the guest flash/redirect are gone;
  `render_template` and `get_site_name` stay (the run pages use them). An unknown or missing list
  answers `Not a song list` (400). Each row's `info_url` is `url_for("song_info.song_info")` +
  `?song=` + `quote(path.encode("utf-8", "surrogateescape"))`.
- **Page** (`processing.html`): four `<button type="button" class="pr-link" data-list=...
  aria-expanded>`, each in a `.pr-list` with a hidden `.pr-songs` box; the count tag and an
  `icon-angle-down` chevron (rotated 180° when `aria-expanded="true"`) in `.pr-link-end`. State
  `openList` and `listSeq`; `closeLists` bumps `listSeq`, `openList` closes the others and bumps it
  again, both answers (done, fail) drop on a stale `seq`. Rows are built with `libraryPages.el`
  (called by its full name: `syncList` and `tickElapsed` hold a local `el`). `showTab('tools')`
  calls `closeLists()` before `loadOverview()`. New strings: `Loading…`, `No songs in this list.`
  (already in the Jobs panel), `Couldn't load this list.`, `Not a song list`, and the footnote.
- **Deno/jsdom probe** (`p72\lists_probe.mjs` on `p72\run_pages.mjs`, a copy of the 7.1 harness;
  page dumped by `p72\test_dump_processing.py` through `test_processing_page.py`'s fixture,
  `PYTHONPATH=tests/unit`, `--rootdir p72`, into `p72\pages\processing_admin.html`). Output
  `p72\probe_after.txt`:
  - `0. buttons: 4`; `1. while loading: behind: expanded=true hidden=false text="Loading…"`.
  - `1. answered`: two links `/song_info?song=%2Fa%20%26%20b.mp4`, `/song_info?song=%2Fplain.mp4`,
    both `a.pr-song.no-spa`; the name `<b>Bold</b><script>window.pwned=1</script>` shown as text,
    `<b> elements: 0`, `script elements: 0`, `pwned: undefined`.
  - `2.` opening poor: behind `expanded=false hidden=true text=""`, poor `Loading…`.
  - `3.` tapping poor again: all four `expanded=false hidden=true`; poor's answer after that
    renders nothing (`text=""`).
  - `4.` no_lyrics's answer after all was opened: no_lyrics `hidden=true text=""`, all still
    `Loading…`.
  - `5.` empty answer: `No songs in this list.`
  - `6.` failed with `{"error": "Admin only"}`: `Admin only`, class `pr-error pr-songs-note`; failed
    with an HTML body: `Couldn't load this list.`
  - `7.` Jobs then Library tools: all four closed; no `songs?list` request left pending.
- **Mutation checks** (`p72\mutate72.py <worktree> <step>`; each reverted; `git status` clean of
  them after). Probe steps count output lines not in `probe_after.txt`:

  | Step | Mutation | Result |
  |---|---|---|
  | 7.2a | the dropped-answer check removed (both `seq !== state.listSeq` lines) | probe: 2 lines (`poor: ... text="LATE POORx"`, `no_lyrics: ... text="LATE NO LYRICSx"`) |
  | 7.2a | `openList` doesn't call `closeLists` | probe: 1 line (`no_lyrics: expanded=true hidden=false text="Loading…"` at step 4) |
  | 7.2a | `info_url` built without `quote` | 2 failed (`test_each_row_has_its_name_subline_and_song_info_link`, `test_the_song_info_link_survives_a_name_with_url_characters`) |
  | 7.2b | the marker test inverted | 2 failed (both parametrized cases) |

  `%APPDATA%\pikaraoke\tmp\lyric_choices` (Ken's real temp folder) held 0 files after the 7.2b
  runs.
- **pre-commit:** `--files` per commit; every hook passed at 7.2a; at 7.2b Black reflowed one list
  comprehension in the new test (restaged, then passed). Import smoke: `routes.library`,
  `pipeline.stages.lyrics_fetch`, `karaoke`, `app`.
- **Isolated app run** (Ground rules checked first and again before the start: nothing on 5555 or
  5556, no python, mpv or pikaraoke process besides `TPython.exe` once the suite had ended, GPU
  980 MiB). Port 9333 was held by two `msedge` processes started 2026-10-22 (not touched); the
  driver used 9334. `APPDATA` the Phase 3 session's scratch folder (`...\66751cff-...\scratchpad\
  appdata`, `download_path` `D:/shared/weblib-test`, admin password empty; `state.json` `{"run":
  null}` before and after). Log `app_run_phase72.log`: `Background library scan starting:
  D:\shared\weblib-test`, `Scan: found 8 song(s) on disk`; ERROR lines only the yt-dlp self-upgrade.
  Scratch library hashed before (`scratch_before_p72.json`, 258 files; identical to Ken's check's
  `weblib_after.json`: 258 identical). Headless Edge at 390 px (`cdp72.py`, a copy of `cdp71.py`,
  port 9334, profile `edgeprofile72`; steps `steps72.py`; output `drive72.txt`; screenshots
  `p72shots\01_tools_closed`, `02_poor_open`, `03_after_back`). Nothing was queued.
  - Counts `behind=0`, `poor=2`, `no_lyrics=2`, `all=8`; all four closed; button heights 48 px; the
    footnote `Tap a list to show its songs, then a song for its Song Info.`
  - Behind: tag 0, `No songs in this list.` Looks poor: tag 2, rows 2, `'Defying Gravity' - Wicked
    20th Anniversary Edition WICKED the Musical | 38 of 89 lines guessed`, `Jay Chou Sunny Day | 26
    of 42 lines guessed`. No lyrics: tag 2, rows 2 (Eason Chan, Traditional - Happy Birthday,
    `Transcribed`). All songs: tag 8, rows 8 (six `Up to date`, two `No lyrics`). After each open,
    only that list `expanded=true/shown`; the chevron's transform `matrix(-1, 0, 0, -1, 0, 0)`; song
    rows 56-81 px tall. Tapping the open All songs closed it.
  - Defying Gravity from Looks poor (`no-spa`) loaded `/song_info?song=D%3A%5Cshared%5Cweblib-test
    %5C%27Defying%20Gravity%27...---AoON1CyhQAM.mp4`, h1 `Song Info`. `history.back()`:
    `/processing#tools`, navigation type `back_forward`, the Library tools tab active, all four
    lists closed.
  - App stopped with `taskkill /F /T` on the listener's pid (40580); the driver's leftover Edge on
    9334 (profile `edgeprofile72`) stopped; afterwards 5555, 5556 and 9334 free. Scratch library
    after (`scratch_after_p72.json`): before 258, after 258, added 0, removed 0, changed 0,
    identical 258.
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the Phase 0
  manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, all 12 under `zh_probe/`, as in
  the earlier rows. Output `manifest_compare_phase72.txt`.
- **Differences from the plan's text:** none.

### Phase 8

Executed 2026-10-23 by Sonnet 5.5 (session `7c41e33d`), starting from `0552146` (clean). Scratchpad for
this row: `...\7c41e33d-b508-4b41-8c26-8efd77d9542a\scratchpad\`. Two code commits, in order:

- `1a26b68` 8a+8b feat(library): downloads without a pick get the caption check and a needs-a-pick list
  (11 files, +1056/-64: `karaoke.py`, `library_tools.py`, `pipeline_tracker.py`,
  `processing_manager.py` (a docstring), `routes/library.py`, `pick_pass.html`, `processing.html`,
  and four test files).
- `3d26811` 8c feat(library): add a YouTube playlist from the Processing page (9 files, +971/-6:
  `library_links.py`, `library_tools.py`, `routes/library.py`, `playlist.html` (new),
  `processing.html`, and four test files).

The tree was built whole, tested and run live, then split into the two commits by stripping the
playlist parts for the first (script `strip_playlist.py`), so the first commit's tree was tested on
its own (below).

- **Baseline** (`uv run --no-sync python -P -m pytest tests/unit -q`, at `0552146`, 144.8 s): **4
  failed, 2103 passed, 2 skipped**; the four are the baseline's four ids.
- **Suite at `1a26b68`** (146.6 s): 4 failed, **2171 passed**, 2 skipped (+68). **At `3d26811`**
  (149.6 s): 4 failed, **2243 passed**, 2 skipped (+72); the same four ids both times.
- **New tests** (collected counts): `test_library_tools.py` `TestAfterDownloadCheck` 10,
  `TestPickLyrics` 13, `TestWhenAListedSongLeaves` 5, `TestNeedsPickAcrossARestart` 13,
  `TestNeedsPickView` 1, `TestPlaylistSource` 2, `TestCheckPlaylist` 15, `TestAddPlaylist` 19;
  `test_library_routes.py` `TestPicksPage` 7, `TestNeedsPickRoute` 9, `TestPlaylistPage` 5,
  `TestPlaylistCheckRoute` 9, `TestPlaylistAddRoute` 8; `test_processing_routes.py` `TestNeedsPick`
  (tracker) 8; `test_library_links.py` `TestIsVideoId` 13; `test_processing_page.py` +3 (the Add
  playlist card, the tag and link for a row waiting for a pick, the guest's waiting song).
  Changed tests: `test_processing_page.py` `test_the_script_rebinds_its_handlers...` now expects
  `$(document).off('.processing')` (was `'click.processing'`); the four `LibraryTools(...)` calls in
  the test files take `events` and `download_manager`.
- **Windows trap found by a test, not changed:** `genius.write_choice` renames its temp file onto
  the choice file with `Path.rename`, which raises `FileExistsError` on Windows when the target
  exists (the cause of the baseline's `test_write_overwrites_existing` failure). On Windows a pick for
  a song whose choice file is still there answers "Could not save that pick."; the file is gone when
  the lyrics stage has used it, so a re-pick after a failed job works. `genius.py` is not in D1, so it
  is untouched; the re-pick test deletes the file first, as the pipeline does. Linux replaces it.
- **8a, as built.** `LibraryTools(..., events, download_manager)`; `on_song_downloaded` is wired in
  `karaoke.py` after the tracker in place of the processing manager's subscription (LibraryTools is
  built just before it). Order of the checks: not a video, no YouTube id, blocked title, or a choice
  file already there -> queue; else `gate_on_disk_caption`: passes -> queue; otherwise listed with
  `no_caption` or `sparse_caption` (the sparse caption file is deleted by the gate), `source`
  `playlist` when the id was queued by `add_playlist` (8c) and `download` otherwise. An `OSError`
  from the gate queues the song as before. The list is `_NeedsPick` entries in `state.json` beside
  the run (`{"run": ..., "needs_pick": [...]}`; `picked` is not saved). `processing_complete` and
  `song_deleted` drop an entry. Tracker: `needs_pick` status kept like `complete`/`error`; actions
  `["remove", "pick", "song_info"]` for an admin; `remove` deletes the song directly (no cancel).
  `attention_rows` adds entries with no tracker row after the failed and unfinished rows, with
  `reason`, `source`, actions `["pick", "song_info", "delete"]`; a listed song is left out of the
  database's failed/unfinished rows.
- **Calls the plan did not settle** (made here, for Ken to see):
  1. A guest's row for a song waiting for a pick stays in **Getting ready** with a Waiting tag
     (the admin's is in Attention): decision 16, nothing is wrong from the guest's side. In the
     server's ordering it ranks after the queued jobs.
  2. A listed song whose queued job fails (`processing_error`) or is cancelled
     (`processing_cancelled`) can be picked again (`picked` cleared); the plan only had
     `processing_complete` and `song_deleted` end an entry. Without it the row would read "Picked ·
     processing" for good.
  3. `_on_processing_queued` sets a `needs_pick` row back to `waiting` (a pick queued it), so a
     Remove clicked before the next status read cannot reach a job that is already queued.
  4. The pick page's list mode shows no Looks poor chip, no progress sentence about saving, and a
     picked song's row does not open a picker.
  5. The Add playlist page has a Check button beside the link box (the board shows none), and the
     button reads "Download K", "Process M" or "Download K and process M" by what is selected.
  6. Wording added: "Paste a YouTube playlist link." (a link that is not YouTube), "Nothing to add:
     those songs are already in the library or waiting." (flash, `is-warning`), "Added N videos to
     the download queue." and "N songs sent to processing." (flash, `is-success`). The board's step
     3 says "Needs attention"; the page says "Attention", the name of the chip.
- **8c, as built.** `check_playlist` and `add_playlist` as the plan describes; `add_playlist` also
  leaves out a video already waiting or downloading (`download_manager.pending_downloads` and
  `active_url`) and a duplicate id, caps a title at 200 characters, and takes an unprocessed song
  only when it is in the library, a video, not busy, not already listed and still
  `in library, not processed`. `library_links.is_video_id` and `NOT_PROCESSED` are new (D1 lists
  `library_links.py`). Routes: `GET /library/playlist` (page, link from `?url=`),
  `POST /library/playlist/check`, `POST /library/playlist/add`, all admin only.
- **Isolated app run** (Ground rules checked first: nothing on 5555 or 5556, no python, mpv or
  pikaraoke process, GPU 970 MiB; port 9333 held by two `msedge` processes from 2026-10-22, not
  touched, the driver used 9334). The first start used the Phase 3 scratch `APPDATA`; its deep
  path made **"Hello" fail in stem separation with `Error exporting audio file: [Errno 2] No such
  file or directory`** (the output path was about 267 characters; "Someone Like You" would have
  been about 262; Windows' 260 limit). The app was stopped with `taskkill /F /T`, its `APPDATA`
  copied without `tmp` to **`C:\temp\p8\appdata`** (short path) and the app restarted there; every
  later run used that. Library `D:\shared\weblib-test`, admin password empty, 258 files hashed
  before (`scratch_before_p8.json`). Logs `app_run_phase8.log.err` (first start),
  `app_run_phase8b.log.err`, `app_run_phase8c.log.err`; the only ERROR lines before the runs are the
  yt-dlp self-upgrade. Headless Edge at 390 px (`cdp8.py`, port 9334, profile `edgeprofile8`;
  steps `steps8a.py`, `steps8b.py`, `steps8c.py`, `steps8d.py`; output `drive8a.txt` to
  `drive8d.txt`; screenshots in `p8shots\`: `01_attention_row`, `02_picks_list`, `03_picker_open`,
  `04_picked`, `05_tools_playlist_card`, `06_playlist_checked`, `07_playlist_unchecked`,
  `08_after_add`, `09_attention_after_restart`, `10_delete_confirm`).
  - **A download with no manual caption (plain download box).** "Someone Like You - Adele
    (Karaoke Songs With Lyrics)" (`rMSQwIp4Jg8`): log `needs a lyrics pick (no_caption)`; row
    `proc=needs_pick`, group attention, actions `['remove', 'pick', 'song_info']`; page row "Download
    · no caption", tag "Needs a pick", buttons Pick lyrics (`/library/picks`), Song info, Delete song.
    The pick page: h1 "Pick lyrics", back link "‹ Processing" -> `/processing#jobs`, "0 of 1 picked",
    chips To pick 1 / Picked 0 (no Looks poor), 0 footer buttons, the search box prefilled "Someone Like
    You - Adele", picker buttons Transcribe and Use pick only; after selecting the Adele hit and Use
    pick: "1 of 1 picked", To pick 0 / Picked 1, the Picked tab row "Picked · processing" with no
    buttons, and tapping it opened no picker. The screenshots (390 px) were read by eye.
  - **A download with a passing caption.** "ABBA - Mamma Mia" (`unfzfe8f9NI`, manual `en`): log
    `Queued for pipeline` at once, `Lyrics: YouTube SRT`, never listed; its first run was cut off by
    the restart above (an `Unfinished` row), **retried from that row: `lyric_method` `srt+cue_align`**,
    `karaoke/...ass` and `alignment_debug/...json` written.
  - **A search-picker download.** `POST /lyrics_select` `{"yt_id": "doWWkG2gPPE", "genius_id":
    2332455}` then `/download` for "Hello - Adele": log `Queued for pipeline` with no listing,
    `Lyrics: Genius — 'Hello' by 'Adele' (genius #2332455)`, `LRCLIB: variant available for fill`.
    Its second run (the first was lost to the path limit above; the song was deleted from its
    Attention row and downloaded again the same way) **failed in Whisper:**
    `Whisper align_refine failed ... AttributeError: 'NoneType' object has no attribute 'language'`
    (`stable_whisper` `align` returned nothing; the log before it: `transcribe yield 0.0 wpm`,
    `Failed to transcribe audio. Result contains no text`, a de-reverb retry, then the align). "Someone
    Like You" (picked on the new page, Genius #51294, LRCLIB variant found) failed the same way, and
    "Shallow" (picked Transcribe) with `Whisper transcribe_refine failed ... IndexError: list index out
    of range`. All three are Musisi "Karaoke Songs With Lyrics" videos; their `vocal.m4a` are 7.4 MB
    (Hello), 235 KB (Someone Like You) and 214 KB (Shallow) for 3 to 5 minute songs. Not
    investigated; the code that fails is `whisper_worker.py` after the lyrics stage, which this
    phase does not touch.
  - **A no-caption song with vocals, end to end.** "Ed Sheeran - Shape Of You [Official Lyric
    Video]" (`_dK2tDK9grQ`, no manual caption): downloaded through the plain box, listed (`needs_pick`),
    picked Genius #2949128 through `POST /library/needs_pick/pick` (`to_pick 4, picked 1`), processed:
    **`lyric_method` `genius+joint`**, `lyrics/...lrc` written with `[lrclib_id:37713208]`, `karaoke`
    and `alignment_debug` written; the song left the list on completion (`to_pick 3`).
  - **A failed or cancelled job offers the pick again:** after the three Whisper failures the pick
    list read `to_pick 3, picked 0` ("Someone Like You", "Shallow", "Wannabe"). A second pick of
    "Shallow" while it was queued answered 400 `That song already has a pick.`
  - **Playlist** `PLRxQryWW8Yw1hcJrE_Aip8wJCPeSh2Ahe` (the Phase 2C one, 17 videos, none with a
    manual `en` caption: `probe_playlist.txt`). Library tools tab: the Check playlist button
    disabled until a link is typed; the page then showed `Musisi Karaoke BEST 10 | Popular Karaoke
    Songs · 17 videos`, `15 new`, `2 not processed` ("Someone Like You" and "Hello", both in progress
    then), `0 in library`; sections "New: will download (15)" and "In library, not processed (2)" with
    "Downloaded earlier but never finished. Will be processed."; button "Download 15 and process 2".
    With 13 boxes unchecked ("Left out" shown on each): "Download 2 and process 2". Add -> `/processing#jobs`,
    one toast "Added 2 videos to the download queue.", the two rows downloading `by Playlist`, then
    `needs_pick` rows in Attention. A re-check: `{'new': 13, 'not_processed': 4}`; adding the four
    unprocessed songs: `{'downloads': 0, 'processing': 0}` (two busy, two already listed). Links:
    `watch?v=...` -> "This is a link to one video. Use the search page to add single videos.";
    `watch?v=...&list=...` -> "This link opens one video in a playlist. Paste the playlist page
    link (youtube.com/playlist?list=…) to add the whole list."; `hello` -> "Paste a YouTube playlist link."
  - **Restart.** After each of two `taskkill` restarts (temp folder dropped as a clean exit does):
    the Attention list held the listed songs once each, in order failed, unfinished, needs-pick,
    with `source: playlist` on the two playlist songs, and "Someone Like You" (whose job had failed)
    only as needs-pick, not also as failed; no pick survived (`picked 0`).
  - **Delete.** "Wannabe" deleted from its Attention row (confirm in the row: "Delete this song from
    the library?"): gone from Attention, from the pick list (`to_pick 2`) and from `state.json`.
  - App stopped with `taskkill /F /T`; my headless Edge processes (profile `edgeprofile8`) stopped;
    afterwards 5555, 5556 and 9334 free (9333 is the older Edge, not mine). Scratch library after:
    258 before, 285 after, 27 added, 0 removed, 0 changed, 258 identical; the 27 added files deleted
    (`restore_scratch.py`), re-hashed: **258 identical, added 0, removed 0, changed 0**.
    `C:\temp\p8\appdata` reset: `state.json` `{"run": null, "needs_pick": []}`, `tmp` removed.
  - Ken's real temp folder `%APPDATA%\pikaraoke\tmp\lyric_choices` held 0 files after the test runs.
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the Phase 0
  manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, all under `zh_probe/`, as in the
  earlier rows (`manifest_compare_phase8.txt`).
- **pre-commit:** `--files` per code commit; at each, Black reformatted one file (the tests at the first
  run of the full tree, `library_tools.py` once on the stripped tree), restaged, then every hook
  passed. A strip script wrote CRLF once on Windows; the six files were converted back to LF before
  the first commit (`git diff --check` clean). Import smoke: `karaoke`, `app`, `routes.library`,
  `library_tools`, `library_links`. pre-commit was not run on this plan file (CLAUDE.md excludes
  `plans/`; run once by mistake, the markdown hook reformatted the whole file and that was reverted).
- **Differences from the plan's text:** the live playlist step downloaded 2 of the 17 videos (13 of
  the 15 new ones left out) instead of "the rest", because each download is a full GPU run and the
  videos have no captions; the "captioned songs process" case was shown with a direct download
  (ABBA) because no video in that playlist has a manual caption. Review due (see the relay).

### Phase 8.1

Executed 2026-10-23 by Sonnet 5.5 (session `7c41e33d`), starting from `babdca2` (clean; the plan
commit on top of `fd38a1b`). Scratchpad for this row:
`...\7c41e33d-b508-4b41-8c26-8efd77d9542a\scratchpad\p81\`. Five code commits, in order:

- `14632ae` 8.1a fix(library): a caption that can't be read no longer drops the download (5 files,
  +111/-16: `library_regen.py`, `library_tools.py`, `test_library_regen.py`,
  `test_library_routes.py`, `test_library_tools.py`).
- `9aae99d` 8.1b fix(processing): a status read during the caption check no longer hides the pick
  (2 files, +55/-12: `pipeline_tracker.py`, `test_processing_routes.py`).
- `59dd376` 8.1c fix(library): whether a listed song is queued comes from the queue (3 files,
  +103/-32: `library_tools.py`, `test_library_routes.py`, `test_library_tools.py`).
- `763d64e` 8.1d fix(library): the playlist page and its add agree on what will be processed (5
  files, +150/-32: `library_tools.py`, `routes/library.py`, `playlist.html`, `test_library_routes.py`,
  `test_library_tools.py`).
- `2ba0c3d` 8.1e refactor(library): the needs-a-pick words and "not processed" have one definition
  each (6 files, +67/-18: `routes/library.py`, `routes/processing.py`, `processing.html`,
  `scripts/add_songs.py`, `test_processing_page.py`, `test_processing_routes.py`).

- **Baseline** (`uv run --no-sync python -P -m pytest tests/unit -q -p no:cacheprovider`, at
  `babdca2`, 141.6 s): **4 failed, 2243 passed, 2 skipped**; the baseline's four ids. Imports
  checked to resolve to the worktree first.
- **Suite after each commit** (same four failed ids every time, 2 skipped):

  | Commit | Passed | Time | New tests |
  |---|---|---|---|
  | `14632ae` | 2255 | 150.3 s | +12 |
  | `9aae99d` | 2257 | 147.4 s | +2 |
  | `59dd376` | 2261 | 148.8 s | +4 |
  | `763d64e` | 2269 | 147.8 s | +8 |
  | `2ba0c3d` | 2274 | 149.4 s | +5 |

- **Tests, by step.**
  - 8.1a: `test_library_regen.py` `TestSrtWordCount` (new class: the count of a good caption; a
    latin-1 caption, an out-of-range timestamp and a non-SRT each give None and log `Cannot read
    SRT`; a missing file gives None), `TestGateOnDiskCaption` (+3: each of the three unreadable
    captions passes and is kept, plan seed-srt); `test_library_tools.py` `TestAfterDownloadCheck`
    (the old `..._cannot_be_checked_is_queued_as_before`, an `OSError` only, became one test over
    `OSError` and `RuntimeError`: queued, nothing listed, a second `song_downloaded` handler
    registered after it ran, the log names the song; +1 for a latin-1 caption: queued, nothing listed,
    the file kept), `TestAddPlaylist` (+1: the first song's check raises, the second is still taken),
    `test_library_routes.py` `TestPlaylistAddRoute` (+1: 200 and the song queued).
  - 8.1b: `test_processing_routes.py` `TestNeedsPick` (+2): the probe's sequence with the real
    `EventSystem` (admin row `needs_pick`, group `attention`, `pick` among the actions; the guest's
    row `needs_pick`, group `active`, no `pick`; `finished_at` still None); a row stamped by
    `processing_complete` is not touched by a later `needs_pick`. The 5.1c tests
    (`TestAStatusReadBeforeTheQueue`) passed unchanged.
  - 8.1c: the `download` fixture (`test_library_tools.py`) and `listed_song` (`test_library_routes.py`)
    now make `processing.enqueue` append to `pending_jobs`, as the manager does. `TestPickLyrics`:
    second pick refused with the new text; a song busy as waiting and as running shows as picked and
    is refused with no `enqueue` and no choice file (2); a second pick from inside `write_choice` is
    refused and `enqueue` runs once; a failed `write_choice` leaves the song pickable and a second
    pick then queues it; an `enqueue` that raises leaves it pickable (+1, new).
    `TestWhenAListedSongLeaves`: the cancel test became "a job cancelled while it waits offers the
    pick again" (`pending_jobs` emptied, no event, view `picked 0`, a new Genius pick taken, `enqueue`
    called twice); the failed-job test removes the song from `pending_jobs` before the
    `processing_error` event. Net +4.
  - 8.1d: `TestCheckPlaylist` +1 (a busy song and a listed song `waiting` with no `song`, an idle
    unlisted one `not_processed`); `TestAddPlaylist` +1 (one song queued and one listed give
    `processing 1, listed 1`; the listed one's entry has source `playlist`; `_playlist_ids` empty) and
    the existing results now carry `listed`; `TestPlaylistAddRoute` +5 (the flash for 0/0/1, 0/0/3,
    2/0/1, 0/1/2 and 1/2/3 downloads/processing/listed; the existing nothing-to-add test covers all zero);
    `TestPlaylistPage` +1 (the `waiting` section text, no box or tag, M counted from `not_processed`
    only). `TestPlaylistSource` unchanged and passing.
  - 8.1e: `test_processing_page.py` +1 (the script shows `row.subline`; `sources:`, `reasons:`,
    `T.sources`, `T.reasons` and `caption too sparse` are not in the page); `test_processing_routes.py`
    `TestAttentionRoute` +4 (each source with each reason: the row's `subline`, actions, and no
    `subline` on other rows; `pikaraoke.routes.library._` patched to the identity, as the file does
    for its own route). `test_add_songs.py` unchanged and passing.
- **As built (the plan left these open).**
  - 8.1a: `_srt_word_count` catches `(OSError, ValueError, OverflowError, srt.SRTParseError)`.
    `_pick_reason` has no catch of its own. The boundary logs with `logger.exception("Lyrics check of
    %s failed; processing it", name)`; after 8.1d it is in `_check_download`.
  - 8.1c: `_is_picked(entry)` is `entry.picking or self.is_busy(entry.song)` (caller holds the state
    lock; `queue_run` already calls `is_busy` under it). `pick_lyrics` is `try: write_choice / except
    OSError: raise RegenError / else: enqueue / finally: picking = False`. `_unpick`,
    `_on_processing_error` and the `processing_error` and `processing_cancelled` subscriptions are gone.
  - 8.1d: `check_playlist` calls `file_status` and then `_is_unprocessed` for a not-processed file, so
    `file_status` runs twice for such a file. `on_song_downloaded` keeps the `_playlist_ids` lookup and
    calls `_check_download(song_path, source)`. No pill for `waiting` on the page (the plan named none).
  - 8.1e: `routes/processing.py` imports `needs_pick_subline` from `routes/library.py` (a first
    import between two route modules). The attention rows still carry `reason` and `source` (the
    page's change key uses them). The `add_songs.py` comment now reads `# "new" | "already in library"
    | NOT_PROCESSED`.
- **Windows behaviour not changed (8.1c's consequence).** A job cancelled while it waits leaves its
  choice file; the pick that follows calls `write_choice`, which on Windows raises `FileExistsError`
  (`Path.rename` onto an existing file; the baseline's `test_write_overwrites_existing`) and answers
  "Could not save that pick." until the file is gone. Linux replaces it. `genius.py` is not in D1; the
  cancel test deletes the file first and says why in a comment.
- **Mutation checks** (each reverted from a copy; `git status` clean after). Test ids are the new
  ones above.

  | Step | Mutation | Result |
  |---|---|---|
  | 8.1a | the boundary removed (in `on_song_downloaded` at `14632ae`, again in `_check_download` at `2ba0c3d`) | 4 failed both times: the `OSError` and `RuntimeError` cases, the playlist "does not stop the songs after it", the route's 200 |
  | 8.1a | `_srt_word_count`'s catch narrowed back to `(OSError, srt.SRTParseError)` | 4 failed: the not-UTF-8 and out-of-range cases in `TestSrtWordCount` and in `TestGateOnDiskCaption` |
  | 8.1b | `_on_needs_pick` takes `_find_unfinished` only | 1 failed: the probe-sequence test |
  | 8.1b | `_find_called_complete` ignores `finished_at` (extra) | 1 failed: the stamped-row test |
  | 8.1c | `_is_picked` without `is_busy` | 5 failed: stays listed as picked, second pick refused, busy waiting, busy running, the route's pick-then-list |
  | 8.1c | `picking` never cleared | 4 failed: failed write, failing `enqueue`, failed job, cancelled while waiting |
  | 8.1d | `check_playlist` on `file_status` alone | 1 failed: waiting-not-unprocessed |
  | 8.1d | `listed` counted as `processing` | 2 failed: the counted-apart test and the failing-check test |

- **Probes** (review session `a85d9ebe`'s scratchpad; run from the worktree root with
  `uv run --no-sync python -P`; outputs `race_before.txt`, `race_final.txt`, `probe1_before.txt`,
  `probe1_final.txt`, `probe2_before.txt`). Before at `babdca2`, after at `2ba0c3d`:

  | Probe | Before | After |
  |---|---|---|
  | `probe_race.py` | `read during gate: ['complete']`; `after needs_pick: status complete group finished actions ['remove', 'dismiss', 'song_info', 'enqueue']`; `guest: complete finished ['enqueue']` | `read during gate: ['complete']`; `after needs_pick: status needs_pick group attention actions ['remove', 'pick', 'song_info']`; `guest: needs_pick active []` |
  | `probe1.py` P1 | `raised UnicodeDecodeError 'utf-8' codec can't decode byte 0xe9 in position 35 ... \| enqueue called: False \| later handler ran: False` | `no exception; enqueue calls [call(<the song>)]`, a `Cannot read SRT` warning logged (the later handler is asserted by the unit test; the probe prints it only on an exception) |
  | P2 | `second pick refused: That song already has a pick.`; view `[{'kind': 'queued'}]` | `second pick accepted`; view `[None]` |
  | P3 | view `[(..., None)]`; `enqueue calls (busy song): 1` | view `[(..., {'kind': 'queued'})]`; `pick refused: That song is already waiting or processing.`; `enqueue calls (busy song): 0` |
  | `probe2.py` | `huge hours raised OverflowError`; `bom -> ['la la']`; `garbage raised SRTParseError` | the same (it calls `cue_spans_from_srt` directly); `_srt_word_count` on those inputs: huge hours None, latin-1 None, garbage None, a good caption 3 |

  P4 and P5 (8.1f's items) print as before. The probes read neither `_unpick` nor `picked`, so no rename
  was needed; the copy `probe1_adj.py` differs from the original in two ways: P3's pick is wrapped
  in `try/except RegenError` and prints the refusal, and P3 clears the choice file first (P2's second
  pick is now accepted and writes one; without that, P3's download was queued, not listed, in the first
  adjusted run).
- **pre-commit:** `--files` per commit. 8.1a, 8.1b and 8.1c passed at once; at 8.1d and 8.1e Black
  reformatted files on the first run (restaged, then every hook passed). `scripts/add_songs.py` was CRLF
  in the working copy (`git ls-files --eol`: `i/lf w/crlf`; `core.autocrlf` is `true` globally and
  `input` in the repository's config); converted to LF in place before the 8.1e commit; its staged diff is
  5 lines. `git diff --cached --check` clean at each commit. Import smoke at `2ba0c3d`:
  `library_regen`, `library_tools`, `pipeline_tracker`, `routes.library`, `routes.processing`,
  `karaoke`, `app`; `scripts/add_songs.py --help` prints its usage.
- **Isolated app run** (look only). Ground rules checked first with `Get-NetTCPConnection` and
  `Win32_Process`: nothing listening on 5555, 5556 or 9334, no `pikaraoke` process. `APPDATA`
  `C:\temp\p8\appdata`, library `D:\shared\weblib-test`, port 5556. Scratch library hashed before
  (`scratch_before_81.json`, 258 files). One entry written to `C:\temp\p8\appdata\pikaraoke\library_tools\
  state.json`: song `D:\shared\weblib-test\Traditional - Happy Birthday (Karaoke Version)---aF8voKa_3Us.mp4`,
  `source` `playlist`, `reason` `no_caption`. Log `app_run_81.log`: the app answered on 5556 after about 8
  s; the only ERROR line is the yt-dlp self-upgrade. Headless Edge at 390 px (`cdp8.py`, port 9334,
  profile `edgeprofile8`; steps `steps_81.py`; output `drive_81.txt`; screenshots `p8shots\81_01_attention_row`
  and `81_02_pick_list`, read by eye). Nothing was picked, queued or downloaded.
  - Processing: chips `All 1`, `Active 0`, `Attention 1`, `Finished 0`; the row reads `Traditional - Happy
    Birthday`, `Playlist · no caption`, tag `Needs a pick`; expanded buttons `Pick lyrics -> /library/picks`,
    `Song info -> /song_info?song=D%3A%5Cshared%5Cweblib-test%5C...`, `Delete song -> delete`.
    `/processing/attention` returned `[{"state":"needs_pick","source":"playlist","reason":"no_caption",
    "subline":"Playlist · no caption","actions":["pick","song_info","delete"]}]`.
  - Pick lyrics: h1 `Pick lyrics`, `0 of 1 picked`, chips `To pick 1` and `Picked 0`, the song with
    `Playlist · no caption`.
  - App stopped (the `uv.exe` and its two `python.exe` with `--port 5556`); my eight headless Edge
    processes (profile `edgeprofile8`) stopped; afterwards 5555, 5556 and 9334 free. `state.json` put back
    to `{"run": null, "needs_pick": []}` (read back). Scratch library after (`scratch_after_81.json`):
    before 258, after 258, added 0, removed 0, changed 0, identical 258 (`hashdiff_81.txt`).
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the Phase 0
  manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, all under `zh_probe/`, as in the
  earlier rows (`manifest_compare_81.txt`). `%APPDATA%\pikaraoke\tmp\lyric_choices` (Ken's real temp folder)
  held 0 files.
- **Differences from the plan's text:** the probe adjustments above; the 8.1a boundary mutation was
  run twice (the code moved in 8.1d); the extra 8.1b mutation. Nothing else.

### Phase 8.2

Executed 2026-10-24 by Sonnet 5.5 (session `7c41e33d`), starting from `591ce32` (clean; the plan
commit on top of `17aee04`). Scratchpad for this row:
`...\7c41e33d-b508-4b41-8c26-8efd77d9542a\scratchpad\p82\`. Four code commits, in order:

- `76f44e2` 8.2a fix(processing): a song queued again after a cancel while waiting is queued once (2
  files, +100/-14: `processing_manager.py`, `test_processing_manager.py`).
- `9f33dba` 8.2b fix(genius): a new lyrics choice replaces the old one on Windows too (2 files,
  +7/-10: `genius.py`, `test_library_tools.py`).
- `b5aa830` 8.2c fix(library): a listed song whose title is now blocked leaves the list (2 files,
  +21/-1: `library_tools.py`, `test_library_tools.py`).
- `af07df4` 8.2d refactor(library): one "already waiting" rule for the playlist page and its add (1
  file, +13/-10: `library_tools.py`).

- **Baseline** (`uv run --no-sync python -P -m pytest tests/unit -q -p no:cacheprovider`, at
  `591ce32`, 148.5 s, `suite_base.txt`): **4 failed, 2274 passed, 2 skipped**; the baseline's four
  ids. Imports checked to resolve to the worktree first.
- **Suite after the four commits** (same command, 145.8 s, `suite_82.txt`): **3 failed, 2279 passed,
  2 skipped**. The three failed ids are the baseline's other three:
  `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job`,
  `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple`,
  `test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`.
  `test_genius.py::TestSidecarIO::test_write_overwrites_existing` passes. 2279 = 2274 + 4 new tests
  (3 in 8.2a, 1 in 8.2c) + the one that failed before. After each commit I ran the files it touches
  and the ones that use them, not the whole suite: 8.2a `test_processing_manager.py`,
  `test_library_tools.py`, `test_library_routes.py` (514 passed); 8.2b `test_genius.py`,
  `test_genius_lyrics.py`, `test_library_tools.py`, `test_library_routes.py` (482 passed); 8.2c
  `test_library_tools.py`, `test_library_routes.py`, `test_processing_manager.py` (515 passed); 8.2d
  `test_library_tools.py`, `test_library_routes.py` (409 passed).
- **Tests, by step.**
  - 8.2a, `test_processing_manager.py`: `TestCancelPending.test_each_cancel_counts_one_waiting_copy`
    (new: enqueue and cancel twice, the count for the path is 2). New class
    `TestCancelledCopiesInTheLoop` (+2; real `EventSystem`, `_runnable_manager` and `_drive_loop`, a
    stand-in `_process_song` that holds job A until released and records each job with the pending
    list at that moment): A running, X queued, B queued, X cancelled, X queued again, then a last job
    -> `ran == [A, B, X, last]`, pending while B ran `[B, X, last]`, counter empty, `pending_jobs`
    empty; A running, X queued, cancelled, queued, cancelled, then the last job -> `ran == [A, last]`,
    counter empty, `pending_jobs` empty. The three `_cancelled_paths == set()` assertions (`TestInit`,
    the regen-path cancel test, the cancel-while-preparing test) became `not ..._cancelled_paths`.
  - 8.2b, `test_library_tools.py` `TestWhenAListedSongLeaves`: both tests lost their
    `delete_choice` call (the cancel test its explaining comment too). The failed-job test's comment now
    says the job failed before the lyrics stage, and its re-pick is `{"kind": "genius", "genius_id":
    5}`, read back as `{"genius_id": 5, "yt_id": "dQw4w9WgXcQ"}`. The cancel test's existing check of
    the new Genius pick on disk now covers the overwrite. The `delete_choice` import went (unused).
    `test_genius.py` was not edited.
  - 8.2c, `TestWhenAListedSongLeaves` +1: a listed song whose `enqueue` emits `processing_skipped`
    (the fixture's side effect replaced): the pick returns, `needs_pick_view()["songs"]` and
    `listed(...)` are empty, the state file's `needs_pick` is `[]`, and a second pick raises "isn't
    waiting for a pick". `test_a_job_for_another_song_changes_nothing` also emits `processing_skipped`
    for another path (extra). `test_a_blocked_title_is_queued_for_the_queue_to_skip` passed unchanged.
  - 8.2d: no test changed; `TestCheckPlaylist` and `TestAddPlaylist` pass unchanged.
- **As built (the plan left these open).**
  - 8.2a: `from collections import Counter`; `_cancelled_paths: Counter[str]` with a one-line comment
    above it. The loop's block is `if song_path in self._cancelled_paths:` then take one off, `del` at
    zero, `continue`, under a two-line comment saying the entry was already taken out by
    `cancel_pending`. `cancel_pending`'s docstring says "counted ... one per cancel" in place of
    "recorded".
  - 8.2b: the comment above `Path(tmp_path).replace(target)` reads "replace is atomic when source and
    dest are on the same filesystem, and it overwrites an existing choice on Windows too, where rename
    raises". The docstring ("tmpfile + rename") is unchanged.
  - 8.2c: `events.on("processing_skipped", self._forget_needs_pick)` after the `song_deleted` line;
    `_forget_needs_pick`'s docstring reads "deleted, finished processing, or skipped".
  - 8.2d: `_is_taken` as the plan gives it; `_is_unprocessed` is now one boolean chain (`isinstance`,
    in the library, `not _is_taken`, `NOT_PROCESSED`) and its docstring says the add uses it and the
    page applies the same rule, with its one disk check, through `_is_taken`. `check_playlist` reads
    `"waiting" if self._is_taken(song) else "not_processed"`. `_pick_reason`'s docstring names
    `_check_download`.
- **Probe** (`probe_81cd.py` from review session `a85d9ebe`, unchanged, run from the worktree root
  with `uv run --no-sync python -P <probe> <empty folder>`; outputs `probe_before.out` at `591ce32`
  and `probe_after.out` at `af07df4`). Before is the same as the plan's quote of `probe_81cd.out`:

  | Scenario | Before (`591ce32`) | After (`af07df4`) |
  |---|---|---|
  | [1] | after A: `pending=['Sb---bbbbbbbbbbb']`, `queue_size=1`, `Sx.pick=None`; `pick #3: accepted`; `jobs that ran: [A, B, X, X]` | after A: `pending=['Sb---bbbbbbbbbbb', 'Sx---xxxxxxxxxxx']`, `Sx.pick={'kind': 'queued'}`; `pick #3: RegenError: That song is already waiting or processing.`; `jobs that ran: [A, B, X]` |
  | [2] | `pick: accepted`; after: `pending=[]`, `Sx.pick=None`; `pick again: RegenError: Could not save that pick.` | `pick: accepted`; after: `pending=[]`, `Sx.pick=not listed`; `pick again: RegenError: That song isn't waiting for a pick.` |
  | [3] | `pick #2: RegenError: Could not save that pick.` (logged `[WinError 183] Cannot create a file when that file already exists`) | `pick #2: accepted` |
  | [4] | `answers: ['RegenError: That song is already waiting or processing.', 'accepted']` | the same |
  | [5] | after A: page `{'x': 'waiting', 'y': 'not_processed', 'b': 'waiting'}`, `add #3: {'downloads': 0, 'processing': 1, 'listed': 0} (M was 1)`; `jobs that ran: [A, B, Y, Y]` | after A: page `{'x': 'waiting', 'y': 'waiting', 'b': 'waiting'}`, `add #3: {'downloads': 0, 'processing': 0, 'listed': 0} (M was 0)`; `jobs that ran: [A, B, Y]` |

  In [1] the "after A" line is the probe's `A done; loop skipped X's cancelled copy; B runs`; after
  the change `queue_size=1` too, with X's new copy still in the queue.
- **Mutation checks** (each applied to the working copy, the test files run, then `git checkout --
  <file>`; `git status` clean after each):

  | Step | Mutation | Result |
  |---|---|---|
  | 8.2a | the run loop's skip strips `pending_jobs` again | 1 failed: `TestCancelledCopiesInTheLoop::test_a_song_queued_again_stays_pending_and_runs_once` (`mut_8_2a_1.txt`) |
  | 8.2a | `_cancelled_paths` back to a set (`add` in `cancel_pending`, `discard` in the loop, no strip) | 2 failed: `TestCancelPending::test_each_cancel_counts_one_waiting_copy`, `TestCancelledCopiesInTheLoop::test_a_song_cancelled_twice_while_waiting_does_not_run` (`mut_8_2a_2.txt`) |
  | 8.2b | `Path(tmp_path).replace(target)` back to `.rename` | 3 failed: `test_genius.py::TestSidecarIO::test_write_overwrites_existing`, `TestWhenAListedSongLeaves::test_a_job_that_fails_offers_the_pick_again`, `TestWhenAListedSongLeaves::test_a_job_cancelled_while_it_waits_offers_the_pick_again` (`mut_8_2b.txt`) |
  | 8.2c | the `processing_skipped` subscription removed | 1 failed: `TestWhenAListedSongLeaves::test_a_pick_for_a_title_blocked_since_it_was_listed_takes_the_song_off_the_list` (`mut_8_2c.txt`) |

- **pre-commit:** `--config code_quality/.pre-commit-config.yaml --files <the commit's files>` per
  commit. 8.2a, 8.2c and 8.2d passed at once. At 8.2b isort rewrote `test_library_tools.py` on the
  first run (the genius import line, kept in its multi-line form); every hook passed on the second.
  `git ls-files --eol` read `i/lf w/lf` for the touched files, `git diff --cached --stat` and the
  source diff were read before each commit, and `git diff --check 591ce32..HEAD` is clean. Import
  smoke before each commit, all resolving to the worktree: 8.2a and 8.2b `processing_manager`,
  `genius`, `library_tools`, `routes.library`, `karaoke`, `app`; 8.2c `library_tools`,
  `routes.library`, `karaoke`, `app`; 8.2d `library_tools`, `routes.library`.
- **Landing list** (status block): the four code commits appended after `235d58b`, so 72 commits. The
  web half was derived again with `git log --reverse --first-parent --no-merges 0bfa02a..HEAD` without
  the `docs(plan)` commits: 58 hashes (`landing_web.txt`), and with `library_tools`' 14
  (`landing_libtools.txt`) the first 68 are identical to Phase 9's list (`diff` empty) and to the
  status block's text. No hash appears twice. None of 8.2's four touches `plans/`
  (`git show --name-only`).
  **Dry run, redone:** `git worktree add --detach` off `dev` (`3a5a2eb`), `git cherry-pick` of all 72
  in list order: exit 0, 72 commits above `dev`, no conflict (`landing_cherry.txt`); `git diff --stat
  HEAD web_library_tools -- . ':!plans'`: 0 lines (`landing_treediff.txt`). The throwaway worktree
  was removed and pruned (no `dry_run` entry in `git worktree list`). Ken's main checkout: `dev` at
  `3a5a2eb`, clean, never touched.
- **Left as it was:** no app was started (the plan: nothing on a page changes), so the scratch library
  `D:/shared/weblib-test`, the isolated `APPDATA` folder `C:\temp\p8\appdata` and the real library
  were not opened, and the real-library manifest was not compared (8.2f does not ask for it). The
  worktree's `models` junction is still in place (Phase 9's row). `%APPDATA%\pikaraoke` was not
  touched.
- **Differences from the plan's text:** after each commit I ran the affected test files, and the
  whole suite once after 8.2d. The mutation of 8.2a was run as the two the plan names, separately.
  Nothing else.

### Phase 9

Executed 2026-10-24 by Sonnet 5.5 (session `7c41e33d`), starting from `6ad5890` (clean). Scratchpad
for this row: `...\7c41e33d-b508-4b41-8c26-8efd77d9542a\scratchpad\p9\`. One code commit:

- `235d58b` docs(scripts): the web UI shares the regen and add_songs core (1 file, +24/-6:
  `scripts/README.md`). A new "Shared core and the web UI" section names `library_regen.py` and
  `library_links.py` as the shared core, names the web controls that do the same jobs (Processing,
  Library tools: Update stale songs, Reset all, Add playlist; Song Info: Regenerate, Repair lyrics),
  names `library_tools.py` as the app service that queues them, and says the CLI runs its own GPU
  workers and needs the app stopped. "Why a separate script, not a Flask route?" is now "Why a
  script as well as the web UI?". No Python file changed in Phase 9 (`git diff 6ad5890..235d58b
  --stat`: the README only).

- **Full suite** (`uv run --no-sync python -P -m pytest tests/unit -q -p no:cacheprovider`, 147.5 s,
  `suite_9.txt`): **4 failed, 2274 passed, 2 skipped**. The four failed ids are the baseline's:
  `test_genius.py::TestSidecarIO::test_write_overwrites_existing`,
  `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_ok_returns_stem_paths_and_sends_job`,
  `test_pipeline_stem_worker.py::TestStemWorkerSeparate::test_model_override_travels_in_job_tuple`,
  `test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`. The first
  one fails for the cause recorded under Phase 8.1: `write_choice` renames its temp file onto an
  existing choice file, which raises `FileExistsError` on Windows. No change to `genius.py` was made.
- **pre-commit** (`code_quality/.pre-commit-config.yaml`, `precommit_all_9.txt`): `--all-files` once.
  Every hook passed except two. pycln removed `import os` from `pikaraoke/lib/args.py` (the file is
  identical to `dev`'s, `git diff dev HEAD` empty, and the import is also in `dev`'s copy);
  mdformat reformatted `plans/library-tools.md` and `plans/web-library-tools.md` (CLAUDE.md excludes
  `plans/`). Both edits were reverted with `git checkout -- <file>`; `scripts/README.md` was not
  changed by either hook. Then `--files scripts/README.md` (`precommit_files_9.txt`): mdformat,
  trailing whitespace, large files, case, merge conflicts, BOM, line endings, shebang and master hooks
  passed; the Python hooks had no files. `git diff --cached --stat` read before the commit.
- **Import smoke:** not run for `235d58b` (no Python changed). Last run at `2ba0c3d` (Phase 8.1 row).
- **Real-library manifest:** `manifest.py compare "D:/Shared/pikaraoke-songs"` against the Phase 0
  manifest: `manifest=2605 now=2616 added=11 removed=0 changed=1`, all 12 under `zh_probe/phase0/`
  (11 added, `phase0c_vocab.json` changed), the same as the earlier rows (`manifest_compare_9.txt`).
  Phase 3.1's verify list says to ignore `zh_probe/`.
- **Landing list** (written into the status block): `library_tools`' 14 code commits, from
  `git log --reverse --no-merges dev..library_tools` without the `docs(plan)` ones, which match its
  plan's status block (`6cc2b29`, `2fdcf08`, `c8fe156`, `788b10c`, then 3.1's seven, then 3.2's
  three); then this branch's 54 from `git log --reverse --first-parent --no-merges 0bfa02a..HEAD`
  without the `docs(plan)` ones, ending with `235d58b`. Lists in `landing_libtools.txt`,
  `landing_web.txt` and `landing_all.txt`. At `6ad5890` this branch's log had 78 first-parent commits
  above `0bfa02a`: 53 code, 24 `docs(plan)`, 1 merge (`c34d889`); `235d58b` is the 54th code commit.
  No code commit touches `plans/` and no
  `docs(plan)` commit touches anything else (checked per commit with `git show --name-only`).
  **Dry run** (not asked for by the plan): `git worktree add --detach` off `dev` (`3a5a2eb`), `git
  cherry-pick` of all 68 in list order: exit 0, 68 commits, no conflict (`landing_cherry.txt`); `git
  diff --stat HEAD web_library_tools -- . ':!plans'`: 0 lines (`landing_treediff.txt`). The throwaway
  worktree was removed (`git worktree list` has no entry for it). Ken's main checkout: `dev` at
  `3a5a2eb`, clean, never touched.
- **Left in place for Ken's checks:** the scratch library `D:/shared/weblib-test` (258 files;
  re-hashed against `scratch_after_81.json`: before=258 after=258 added=0 removed=0 changed=0
  identical=258, `hashdiff_9.txt`), the isolated `APPDATA` folder `C:\temp\p8\appdata` (`state.json`
  under `pikaraoke\library_tools\` reads `{"run": null, "needs_pick": []}`), and this worktree. No
  `pikaraoke` process is running and nothing listens on 5555, 5556 or 9334. (Ken's Firefox, PID 27012,
  holds retrying connections to 5556.) Phase 9 started no app.
- **Differences from the plan's text:** the worktree's `models` junction (to the main checkout's
  `models`, made in Phase 0) was **not** removed. The regen and download-then-pick checks run the
  pipeline from this worktree, and `pikaraoke/pipeline/config.py` and `stem_worker.py` look for
  `models` next to the repository root, so without it those checks fail. It has to be removed before
  `git worktree remove`; `cmd /c rmdir <worktree>\models` removes the link only. The dry-run
  cherry-pick of the landing list is extra.

### Phase 7.2 and Phase 8 checks (Ken's live pass, covering 8.1 and 8.2)

Model: Claude Sonnet 5.5 (procedure, relay, this record); Ken ran the checks. Reported 2026-10-26,
HEAD `1c860b4` (code `af07df4`).

- **Procedure:** given in chat by session `7c41e33d` from "Ken's checks", the Phase 8 row's live list
  and the 8.1g and 8.2 text (no Claude Doc). Check A (Phase 7.2, no GPU): each of the four Library
  card lists opens under its row and its count matches the tag; a second open closes the first;
  tapping the open one closes it; a song opens Song Info and the browser's back returns to the
  Library tools tab with the lists closed. Check B (Phase 8, GPU, scratch library):
  1. a plain-box download of `_dK2tDK9grQ` (no manual caption) lands in Attention as "Download · no
     caption";
  2. Pick lyrics, a Genius hit, Use pick: "Picked · processing", runs in Jobs, leaves the list;
  3. Add playlist (2-4 videos), one box unchecked, Add goes to Jobs;
  4. a re-check afterwards shows queued or listed songs under "Already waiting";
  5. a search-page picker download processes without a check;
  6. optional, 8.2's Windows case: pick a waiting listed song, cancel it while it waits, pick it
     again.
- **State before the run** (read by session `7c41e33d`, 2026-10-26): 5555, 5556 and 9334 not
  listening; no `pikaraoke` process; isolated `APPDATA` `C:\temp\p8\appdata` with its `config.ini`
  copy and `library_tools\state.json` reading `{"run": null, "needs_pick": []}`; scratch library
  `D:\shared\weblib-test` 258 files; the worktree's `models` junction and `libmpv-2.dll` in place.
  Start command as in "Where things live", with `--port 5556`.
- **Ken's report:** "the checks came out fine other than the 2 open things we left". He gave no
  per-box list, and the session did not see the app log, any screenshot, or the scratch library
  after the run. The Phase 8 row's six open calls (including the Check button beside the playlist
  link box, which 8.1f left for this check to decide) drew no objection in his report, so they
  stand as built.
- **The two open items** (Ken, 2026-10-26: leave both; the landing list is already long). Neither
  is on the landing list and neither has a plan step.
  1. **A playlist re-check while a video is still downloading shows it as `new`, checked and
     counted in the button.** Read from the code, not run live to confirm: `check_playlist` takes a
     video's status from `library_files` and the song manager, and neither holds a download in
     flight. `add_playlist` skips a video that is `download_manager.active_url` or in
     `pending_downloads`, comparing the exact string `https://www.youtube.com/watch?v=<id>` (the
     form `queue_download` stores; `test_a_video_listed_twice_or_already_waiting_is_queued_once`), so
     the Add does not queue it twice, and its toast counts fewer downloads than the button said. A
     link in another form pasted into the direct box (`youtu.be/...`, `&t=...`) would not match
     (8.1f's URL-string note). A fix would mark such a video `waiting` in `check_playlist` from the
     same two lists.
  2. **The search-page picker does not check the caption it offers.** Decision 18, a separate
     prerequisite plan; `plans/` holds no file for it. `POST /lyrics_select` writes a choice
     (`genius_id`, `raw` or `srt`) for every picker download, `_pick_reason` returns None for a
     video that has a choice, and `search.html` offers "Use YouTube captions" (mode `srt`) without
     looking at the caption. So nothing checks a sparse caption on that path. The direct-download
     box and playlist downloads do get the check (D14). Decision 18's "lands on `dev` before this
     plan" was not revisited.
- **After the run, not done:** the scratch library re-hash and restore, the `state.json` reset, the
  `models` junction removal. Landing is next: `dev` is still `3a5a2eb`, Ken's main checkout is
  clean on `dev`, so the 72-commit dry run still applies.
