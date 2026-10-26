# Open issues

Model: Claude Opus 5.5 (2026-10-26)

What is still open across the branches, in one list. Each entry says where its
full record is; the record stays there (raw detail, provenance), this file only
points. Strike an entry when it is fixed or ruled closed, with the commit or
the ruling, rather than deleting it. Plans live on their own branches, so a
"record" path names the branch.

Sources gathered on 2026-10-26:

- `plans/web-library-tools.md` on `web_library_tools` (its "Not fixed" sections
  3.1i, 5.1f, 6.1e, 7.1f, 8.1f, 8.2e, the "Seen, not changed" notes in the
  Results log, D9, and the Phase 7 / Phase 8 check rows).
- `plans/library-tools.md` on `library_tools` (the 2026-10-20 real-world run).

## Decide at landing

- **The search-page picker does not check the caption it offers** (decision 18).
  "Use YouTube captions" writes an `srt` choice without looking at the caption,
  and a picker download skips the after-download check, so a sparse caption is
  not caught on that path (the direct box and playlists are checked). Decision
  18 said a separate plan lands on `dev` before `web_library_tools`; no plan
  file exists, and Ken left the item open on 2026-10-26 without revisiting the
  order. Record: web plan, D9 and the "Phase 7.2 and Phase 8 checks" row, item 2.

## Ruled: own branch or plan

- **Delete song and Rename leave the song's files behind.** Upstream's
  `SongManager._get_companion_files` knows only the `.srt`, the two stems and
  the `.ass`, so a delete leaves the bundle, the `.lrc` and the
  `.srt.generated`, and a rename leaves them under the old name. On `dev` today.
  Also: a renamed song on the needs-a-pick list stays listed under its old path,
  and a pick of it fails each time. Ken, 2026-10-23: small branch off `dev`.
  Record: web plan, D9 and 8.1f.
- **Upload hand-checked lyrics** as the lyric source of a Repair, Regenerate or
  Reset. Ken, 2026-10-23: a later plan of its own, after `web_library_tools`
  lands; needs its own design (what counts as the current pick, how an uploaded
  sheet survives a later Reset). Record: web plan, D9.

## Out of scope by design (web plan D9)

Restoring from a backup; regenerating non-video songs (`.mp3`, CDG `.zip`);
regenerating the translation catalogue for the new strings; keeping the
processing queue across a restart (queued regen jobs are lost, and the bulk run
that queued them is already closed; 7.1f).

## Library tools: small, unruled

- **The pick box's starting search keeps trailing words of a long YouTube
  title** (`library_regen.default_query`). Defying Gravity's search came back
  empty until the box was edited. Fixing it means a new title-cleaning rule.
  Record: web plan, Phase 7 row.
- **A service outage reads as "no results."** `/lyrics_search` returns `[]` on
  any Genius failure or a missing token ("No Genius results."), and
  `lrclib.search` returns `[]` on a 503 or timeout. `routes/search.py` is shared
  with the search page. Record: web plan, 6.1e and the Phase 6 row.
- **An empty LRCLIB title makes Search do nothing**; a hint would be new
  wording. Record: web plan, 6.1e.
- **A Reset removes a captioned song's `subtitles/<song>.en.vtt` and writes no
  new one.** The run uses the `.srt`, which stays; nothing found in the app
  reads the `.vtt` later. Not ruled. Record: web plan, Phase 7 checks row.
- **A link pasted into the direct box in another form** (`youtu.be/...`,
  `&t=...`) is not matched as already downloading by the playlist check or add,
  which compare the exact `watch?v=` string. Record: web plan, 8.1f and the
  `8b0f9ac` row.
- **Retry on a failed needs-a-pick song runs without its pick** (the lyrics
  stage deletes the choice file when it reads it). Retry is the admin's choice;
  the pick page offers the pick beside it. Record: web plan, 8.1f.
- **A failed regen restores the old `.lrc` even after a successful run** when
  the error comes after it (the `ready` state write or an event handler); on
  Windows the restored file comes back with CRLF line ends. Record: web plan,
  Phase 3.1 row.
- **A regen of a song whose `.lrc` is not UTF-8 fails at its start**, with the
  decode error shown on the job (no page breaks). Record: web plan, Phase 5.1
  row.
- **`add_songs --folder` defaults to `~\pikaraoke-songs`** (`get_default_dl_dir`)
  instead of `config.ini`'s `download_path`; `regen_alignment_bundles.py` on
  `dev` has the same default. The status report has no title column. Record:
  `library-tools.md`.
- **CLI paths never run on real data:** `regen --song --reset` and backfill's
  queued path. Record: `library-tools.md`.
- **Simplicity leftovers:** `_ActiveJob.kind` is set and never read;
  `prepare_regen_job` accepts plan kinds no caller builds; the int-not-bool
  Genius id check is written three times; the watch URL is built in more than
  one module. Record: web plan, 3.1i and 8.1f.

## Library tools: rare races and timing windows (recorded, not fixed)

Each needs two requests in the same instant or a thread switch inside a short
window; none was seen live. Record: web plan, the section named.

- A fast failure can show as "complete", and a row can show Done for an instant
  between `song_downloaded` and `processing_queued` (3.1i, 5.1f).
- The download and regen lanes don't check each other for duplicates (3.1i).
- The tracker's cancel acts on the last status read; a row cancelled right
  after its job was taken drops the row and the job runs on (3.1i, pre-existing).
- A cancel that lands just as the loop takes a job: the job runs, and the
  recorded skip swallows that song's next queue (8.2e, pre-existing on `dev`).
- Two Regenerate or Repair requests at once both make a backup folder; two
  Retry requests at once can both queue (5.1f, Phase 5 and 6 rows).
- Two playlist adds from two tabs can both queue the same song (8.1f).
- A stale request after an SPA revisit can draw once into the new page (5.1f).
- A run doesn't see a Repair made while it is open; its older pick wins at
  queue time (7.1f).
- A library folder given with a different spelling between starts keeps old
  paths on the needs-a-pick list; starting on another library drops the first
  library's list (8.1f).
- A failed or cancelled playlist download leaves its id remembered for the
  session, so a later plain download of it is labelled "Playlist" (8.1f).

## Pipeline and Chinese lyrics (pre-existing on `dev`)

From the `library_tools` real-world run, 2026-10-20. Record: `library-tools.md`.

- ~~`download_auto_en_subs` (`en.*`) pulls every translated `en-<src>` auto
  track (drew an HTTP 429 on Queen) and discards a good track on a non-zero
  exit.~~ Fixed 2026-10-26 (`28995d6`): asks for `en,en-orig` only, and keeps
  what arrived on a failed run. Reproduced first on `6q0JnftlH-I`: `en.*` got
  the 429 on its first translation (`en-zh`) even with 3 s between requests;
  `en,en-orig` exited 0 with both tracks word-timed.
- **Library songs may lack their word-timed caption because of the bug above.**
  2026-10-26 count in `d:/shared/pikaraoke-songs`: 34 of 48 video songs have no
  `subtitles/<stem>.en.asr.json3`. The cause per song is not known: no ASR on
  YouTube, downloaded before the fetch existed (`0c5de67`, 2026-07-03), or lost
  to the 429. `dev` has no tool to re-fetch it; a fetched caption only takes
  effect at the song's next regen. Not ruled.
- A manual English caption that is a translation (Jay Chou, 龍捲風) passes the
  caption gate: no language check, and no way to send it to Genius instead.
- Mandarin on the joint route breaks (晴天: 24 of 42 lines absent, transcribe
  adds nothing, the LRCLIB fill finds no mapping). Input for GATE L and the
  `chinese_karaoke` work.
- The default Genius query strips all CJK characters (`EMOJI_PATTERN`'s range
  `U+24C2-U+1F251`).
- `stable_whisper.align` raises on its own failed-alignment `None`; the stage
  recovers but logs a traceback.

## Test suite (Windows box)

- Three known failures: `test_pipeline_stem_worker.py` (two
  `TestStemWorkerSeparate` tests) and `test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`.
- One-off on 2026-10-26: `test_library_regen.py::TestApplyLrclibChoice::test_skip_writes_the_marker`
  failed once in a full run and passed alone, with its neighbours and in the
  next full run. Cause not found.
