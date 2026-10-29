# Open issues

Model: Claude Opus 5.5 (2026-10-26)

What is still open across the branches, in one list. Each entry says where its
full record is; the record stays there (raw detail, provenance), this file only
points. Strike an entry when it is fixed or ruled closed, with the commit or
the ruling, rather than deleting it. Plans live on their own branches, so a
"record" path names the branch.

Sources gathered on 2026-10-26:

- `plans/web-library-tools.md` on tag `archive/web_library_tools` (its "Not fixed" sections
  3.1i, 5.1f, 6.1e, 7.1f, 8.1f, 8.2e, the "Seen, not changed" notes in the
  Results log, D9, and the Phase 7 / Phase 8 check rows).
- `plans/library-tools.md` on tag `archive/web_library_tools` (the 2026-10-20 real-world run).

## Decide at landing

- ~~**The search-page picker does not check the caption it offers** (decision 18).
  "Use YouTube captions" writes an `srt` choice without looking at the caption,
  and a picker download skips the after-download check, so a sparse caption is
  not caught on that path (the direct box and playlists are checked). Decision
  18 said a separate plan lands on `dev` before `web_library_tools`; no plan
  file exists, and Ken left the item open on 2026-10-26 without revisiting the
  order. Record: web plan, D9 and the "Phase 7.2 and Phase 8 checks" row, item 2.~~
  Fixed 2026-10-27, on `dev` as `640a661`, `dadecd0` (with review fixes
  `7b07fc8`, `f4aa97b`): the modal checks the caption before offering it, and a
  caption choice gets the after-download gate. Record:
  `plans/search-caption-check.md` on branch `search_caption_check`.

## Ruled: own branch or plan

- **Delete song and Rename leave the song's files behind.** Upstream's
  `SongManager._get_companion_files` knows only the `.srt`, the two stems and
  the `.ass`, so a delete leaves the bundle, the `.lrc`, a custom lyric sheet
  (`lyrics/<stem>.custom.txt`, added by `custom_lyrics`) and the `.srt.generated`,
  and a rename leaves them under the old name. On `dev` today. The sheet costs
  more than the rest: a rename silently drops the song's custom lyrics, and a
  re-download under the same name goes back to the old sheet at its next regen
  (`custom_lyrics` code review, row 6, on tag `archive/custom_lyrics`). Also: a renamed song on the needs-a-pick list stays listed under its old path,
  and a pick of it fails each time. Ken, 2026-10-23: small branch off `dev`.
  Record: web plan, D9 and 8.1f.
- ~~**Upload hand-checked lyrics** as the lyric source of a Repair, Regenerate or
  Reset. Ken, 2026-10-23: a later plan of its own, after `web_library_tools`
  lands; needs its own design (what counts as the current pick, how an uploaded
  sheet survives a later Reset). Record: web plan, D9.~~
  Done 2026-10-28, landed on `dev` as
  `768364e`..`6fa7abc`: Repair takes typed, pasted or opened plain-text lyrics as a
  custom sheet that every later run replays and only a Repair to another source
  removes. Timed uploads (`.lrc`, `.srt`) were left out. Record:
  `plans/custom-lyrics-sheet.md`.
- **Heard words only live in the alignment bundle.** Whisper hears every
  song's words, but only the lyric routes keep them (the bundle's
  `transcribe_words`), and only while `capture_alignment_debug` is on. A
  transcribe run deletes the bundle, since the bundle is also the record of the
  lyric source. So movie subtitles can never be checked on a song that was only
  ever transcribed: the check has nothing to compare them with, and a
  Regenerate transcribes again. Ken, 2026-10-29: move the heard words into a
  file of their own that every route writes, every song, separate from the
  bundle; its own feature after Phase 4 of `movie_subtitles`. Record:
  `plans/movie-subtitle-slice.md` on tag `archive/movie_subtitles`, decision 7 and
  row 27.

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
- ~~**The repair page's LRCLIB search is field-scoped**: it reused the
  pipeline's `lrclib.search` (`track_name` + `artist_name`), so a word that sits
  in another field (a show name in the album, an artist credited differently)
  found nothing.~~ The repair page now searches LRCLIB's all-fields `q=` from one
  box, on `lrclib_search_box`; the pipeline stays field-scoped. Every word must
  still appear somewhere, so a misspelt word still finds nothing.
- ~~**The Processing page's main buttons are off-palette.** Check playlist is
  `is-link` (Bulma's blue); every other page, the library pages included, uses
  `is-primary` for its main action. The same page has four more `is-link`
  buttons: the run banner's Continue, Update stale's Preview, and a job row's
  Retry and Pick lyrics (`processing.html`). Fix: `is-primary` on all five.
  Seen by Ken 2026-10-29.~~ Fixed 2026-10-29 on `dev` as `6aea3c5`: all five are
  `is-primary`.
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
  the error comes after it (the `ready` state write or an event handler);
  ~~on Windows the restored file comes back with CRLF line ends~~ (restored byte
  for byte since `2fa2473`). Record: web plan, Phase 3.1 row.
- ~~**A regen of a song whose `.lrc` is not UTF-8 fails at its start**, with the
  decode error shown on the job (no page breaks).~~ The start-of-run snapshot
  reads bytes since `2fa2473`; whether the rest of the run
  reads such a file is not checked. Record: web plan, Phase 5.1 row.
- **Custom-sheet review leftovers**: `_custom_repair_plan`
  normalizes the sheet text twice; `routes/song_info._typed` repeats
  `library_tools._pick_text` without its length cap, so the POST LRCLIB search
  sends title and artist uncapped. Record: `plans/custom-lyrics-sheet.md`, Code
  review rows 7-8.
- **`add_songs --folder` defaults to `~\pikaraoke-songs`** (`get_default_dl_dir`)
  instead of `config.ini`'s `download_path`; `regen_alignment_bundles.py` on
  `dev` has the same default. The status report has no title column. Record:
  `library-tools.md`.
- **CLI paths never run on real data:** `regen --song --reset` and backfill's
  queued path. Record: `library-tools.md`.
- **Simplicity leftovers:** `_ActiveJob.kind` is set and never read;
  `prepare_regen_job` accepts plan kinds no caller builds; the int-not-bool
  Genius id check is written three times; ~~the watch URL is built in more than
  one module~~ (one `library_regen.watch_url`, `f4aa97b`). Record: web plan, 3.1i and 8.1f.
- **`SongStatus` carries two overlapping sheet flags** (`library_status.py`):
  `custom_sheet` is true for either kind of sheet and `movie_sheet` for the
  `.custom.srt` one, so every reader (`_now`, `_current_source`) must test
  `movie_sheet` first, and `library_regen.custom_plan` repeats the suffix test.
  A reader that tests `custom_sheet` first labels a movie song "custom" and no
  test catches it. Shape: one `sheet_kind` (`custom`, `movie` or none), derived
  once. Deferred 2026-10-29. Record: `/code-review` of `7f07006^..cc88169` on
  tag `archive/movie_subtitles`, finding 8 (not in the plan file).
- **A movie song can be labelled two ways at once.** Song Info's Lyrics tile
  names the source from the bundle's origin; the Repair page's "current" tag and
  the run lists ("Now: movie subtitles") go by the sheet on disk. After a movie
  Repair writes its `.custom.srt` and the run fails or is still queued, Song Info
  still says Genius or No lyrics while the others say movie subtitles, and the
  admin can't tell which the next Regenerate uses. Not ruled (Ken's call).
  Record: same review, finding 10.

## Library tools: rare races and timing windows (recorded, not fixed)

Each needs two requests in the same instant or a thread switch inside a short
window; none was seen live. Record: web plan, the section named.

- A fast failure can show as "complete", and a row can show Done for an instant
  between `song_downloaded` and `processing_queued` (3.1i, 5.1f).
- The download and regen lanes don't check each other for duplicates (3.1i).
- The tracker's cancel acts on the last status read; a row cancelled right
  after its job was taken drops the row and the job runs on (3.1i, pre-existing).
  For a `download` row it also deletes the song file under the running job
  (`PipelineTracker.cancel`'s pending branch; `cancel_pending` skips an active
  path). Seen in code 2026-10-27, not live.
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
  Probed 2026-10-26 with the fixed request (`en,en-orig`, json3, 5 s apart; output in
  the session scratchpad, not the library), plus `--list-subs` on the empty ones:
  - 2 have a word-timed ASR track now: `TZ0pXUb5jVU` (#OutOfOz For Good, file
    date 2026-06-23, before the fetch existed; 280 words, frac 0.773) and
    `6q0JnftlH-I` (Standing Next to You, 2026-09-28; 223 words, 0.805). Only the
    second one could have been lost to the bug. Both bundles are `origin: srt`
    (caption route), and `_resolve_ytasr` runs on the Genius route only, so a
    regen with the track on disk would not use it; not copied in, not regenerated.
    The bug has cost the library nothing that the pipeline uses today.
  - 17 have no `en`/`en-orig` auto track (several list only machine
    translations of the manual caption into other languages).
  - 13 list an `en` auto track that is vtt-only and is the manual caption
    mirrored back (line-level, `♪` marks; checked on `WVe80iZtlYU`), so nothing
    json3 arrives: `WVe80iZtlYU 1OwfYjemrYw iWZmdoY1aTE 450p7goxZqg FQ3slUz7Jo8
    uuZE_IRwLNI TSVHoHyErBQ je0roKRn3nY zABLecsR5UE Eo-KmOd3i7s fJ9rUzIMcZQ
    3JWTaaS7LdU RPWDeLqsN0g`.
  - `8NJVNkzhJM4` (Eason Chan): YouTube's only original auto track is `th-orig`
    (Thai, misdetected); its `en` is a translation of that and drew HTTP 429.
  - `NSYNC - Paradise` has no video id in its name.
- **The auto-caption fetch leaves a stray `<stem>.en.vtt` in `subtitles/`** when
  the `en` auto entry is vtt-only (yt-dlp falls back from json3 to vtt;
  `_select_asr_track` only looks at `.json3`). Reproduced with the fixed
  request on `WVe80iZtlYU`. All five `.en.vtt` files in
  `d:/shared/pikaraoke-songs/subtitles` belong to songs in the 13 above, so this
  is likely where they come from (the Reset `.vtt` entry above may be the same
  file). Not ruled.
- A manual English caption that is a translation (Jay Chou, 龍捲風) passes the
  caption gate: no language check, and no way to send it to Genius instead.
- Mandarin on the joint route breaks (晴天: 24 of 42 lines absent, transcribe
  adds nothing, the LRCLIB fill finds no mapping). Input for GATE L and the
  `chinese_karaoke` work.
- The default Genius query strips all CJK characters (`EMOJI_PATTERN`'s range
  `U+24C2-U+1F251`).
- `stable_whisper.align` raises on its own failed-alignment `None`; the stage
  recovers but logs a traceback.

## Web pages (pre-existing on `dev`)

Found 2026-10-27 during the `queue_hold` manual checks on the Windows box.
Record: `plans/queue-hold.md` on branch `queue_hold`, the manual checks row.

- **Server messages never reach a screen.** `Karaoke.send_notification` emits
  the socket event `notification`, and its only listener was the browser splash
  (`static/js/splash.js`), removed by `367375cc` (2026-06-03). Every
  `events.emit("notification", ...)` since then shows only in the console log:
  added to the queue, download starting or failed, couldn't be processed,
  already in the queue, the per-user limit, library updated. Toasts the pages
  do show come from their own request's answer. Also: nothing emits
  `clear_notification` any more, so `now_playing_notification` stays set after
  the first message and later ones are not even sent. `queue_hold` relies on
  these messages for every case where it drops a held slot. Recommended: own
  small branch off `dev` after `queue_hold` lands (pages listen and toast); not
  ruled.
- **The direct box ignores its own Add to queue tick.** `downloadSong` in
  `search.html` sends `$("#add-to-queue-search").is(":checked")`, and that box
  exists only when search results are on screen; with none, the download is
  never queued. The two ticks are kept in sync, so reading
  `#add-to-queue-direct` (always on the page) fixes it. Upstream code, also on
  `master`. A one-line fix was offered on `queue_hold`; not ruled.

## Test suite (Windows box)

- Three known failures: `test_pipeline_stem_worker.py` (two
  `TestStemWorkerSeparate` tests) and `test_whisper_worker.py::TestStart::test_start_raises_worker_died_on_pipe_close`.
- One-off on 2026-10-26: `test_library_regen.py::TestApplyLrclibChoice::test_skip_writes_the_marker`
  failed once in a full run and passed alone, with its neighbours and in the
  next full run. Cause not found.

## Future features

- **Fold Edit Song (rename, delete) into Song Info.** They are two admin pages
  for one song. Why they are apart: Edit refuses to open while the song is in
  the singing queue (`files.edit_file`), and Song Info must not (web plan,
  decisions 2 and 11); the web plan also touched upstream `edit.html` only for
  its Song info link (4e). Nothing records a ruling against merging; the design
  session's record (`i-am-contemplating-moving-jazzy-toucan.md`) is not on the
  Linux box. Shape: rename and delete as Song Info actions, with the queue
  refusal on those two actions only. Do it with the Delete/Rename entry above,
  since both change the same code. Raised 2026-10-29; not ruled.
- **An LRCLIB match the admin has checked becomes the song's timing (Repair).**
  As an automatic scaffold, LRCLIB was withdrawn (S-1, 2026-09-08). The text
  matched, but an LRC can be timed to another edit of the song (a cut verse,
  an extra repeat), and the offset-and-speed gate cannot see a section the
  video never sings. It passed 5 of the 6 known edit mismatches. Record:
  `plans/PROGRAM.md` and `plans/route-line-timing.md` on tag
  `archive/edge_snap_refine`. On Repair, the admin is the check.
  Today the picked LRC only fills lines the matcher leaves unplaced, and
  "Preview selected timing" shows only the LRC's text, which a wrong edit
  passes. Shape: send the picked LRC through the movie-subtitle route
  (`srt_slice_fit.fit_slice`, then a saved sheet timed by cue align). An LRC
  has start stamps only; `lrclib` already ends each line at the next start.
  Ruled by Ken 2026-10-29:
  1. **The LRC's own lyrics are the sheet**, since they are what the timing is
     checked against.
  2. **Preview = flagged lines first.** After the fit, mark each line by whether
     heard words landed near its fitted time. A cut verse or an extra repeat
     shows as a run of flagged lines. The fit's spread check can't catch that
     itself, because it ignores a minority of lines that disagree. Playback with
     the lines overlaid is held back until flagged lines prove not enough.
  3. **Offered only once the fit makes it viable**; otherwise the pick stays a
     fill, as today. Not settled: what "viable" means. Suggested: the fit
     passes, the length gap to the video is small, and the flagged lines are
     shown before the admin confirms. Open to other ideas.
