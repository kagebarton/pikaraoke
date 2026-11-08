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

- ~~**Delete song and Rename leave the song's files behind.** Upstream's
  `SongManager._get_companion_files` knows only the `.srt`, the two stems and
  the `.ass`, so a delete leaves the bundle, the `.lrc`, a custom lyric sheet
  (`lyrics/<stem>.custom.txt`, added by `custom_lyrics`) and the `.srt.generated`,
  and a rename leaves them under the old name. On `dev` today. The sheet costs
  more than the rest: a rename silently drops the song's custom lyrics, and a
  re-download under the same name goes back to the old sheet at its next regen
  (`custom_lyrics` code review, row 6, on tag `archive/custom_lyrics`). Also: a renamed song on the needs-a-pick list stays listed under its old path,
  and a pick of it fails each time. Ken, 2026-10-23: small branch off `dev`.
  Record: web plan, D9 and 8.1f.~~
  Fixed 2026-11-08 as `957b256`, `e0c2a6c` on `dev` (`4393ee5`, `3d1d943` on
  tag `archive/song_files`): rename and
  delete carry every file a song owns, and delete backs up its text files
  first. Rename and delete refuse a song that is processing or waiting for a
  pick, so a renamed song can't be left on the needs-a-pick list. Record:
  `plans/song-files-rename-delete.md`.
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
- **An open bulk run keeps a renamed or deleted song under its old path**;
  queuing the run then fails that song's job. Pre-existing. Record:
  `plans/song-files-rename-delete.md` on tag `archive/song_files`, Not covered.
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
- ~~**`SongStatus` carries two overlapping sheet flags** (`library_status.py`):
  `custom_sheet` is true for either kind of sheet and `movie_sheet` for the
  `.custom.srt` one, so every reader (`_now`, `_current_source`) must test
  `movie_sheet` first, and `library_regen.custom_plan` repeats the suffix test.
  A reader that tests `custom_sheet` first labels a movie song "custom" and no
  test catches it. Shape: one `sheet_kind` (`custom`, `movie` or none), derived
  once. Deferred 2026-10-29. Record: `/code-review` of `7f07006^..cc88169` on
  tag `archive/movie_subtitles`, finding 8 (not in the plan file).~~ Fixed
  2026-10-29 as `5901020` on `dev` (`b9cdbda` on tag
  `archive/lyric_source_lists`): `SongStatus.sheet_kind`, with
  `library_regen.sheet_kind` the only place a sheet's suffix is tested.
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
- ~~**Cue align can start a line before its cue and squeeze the line before it.**
  She Used To Be Mine on its LRCLIB sheet (2026-10-30): the sheet's cue and the
  transcriber both put line 7 (0-based) at about 38.3 s, but the karaoke starts
  it at 36.09 s, so line 6's last four words get 0.10 s each (Ken heard "a fast
  sweep around 0:33"). The joint version before it had both lines in place.
  Record: `lyric-source-lists.md` Results row 21. Not looked into; the same
  route times every caption song.~~ Fixed 2026-11-05, on `dev` as `518ae9d`
  (zero-length words are rescued like missing ones; a re-aligned line may not
  start on the line before it): after a Regenerate, line 6's last four words sit
  at the transcriber's times and line 7 starts at 38.14 s. Record:
  `plans/cue-align-windows.md` on tag `archive/cue_align_windows`, Decision 13,
  rows 57-58.
- **The end snap can stretch a song's last line into the outro.** NSYNC -
  Paradise on its LRCLIB sheet (2026-10-30): a one-word last line with a 1.77 s
  cue is extended 18.59 s, to 1 s before the video ends (Ken: "slow crawl on
  the last line"). Nothing after the last line bounds the extension. Likely
  the end-side blind spot (extension onto another voice) recorded on
  `archive/edge_snap_refine`. Record: `lyric-source-lists.md` Results row 21.

## Song rename (pre-existing on `dev`)

- ~~**A new name holding `/` or `..` leaves the song's folder.** On Linux and
  macOS `sanitize_filename` keeps both, so renaming to `../Out` moves the video
  out of the library and its captions and lyrics into the library root, and the
  DB then points outside the library. A title like `AC/DC - Thunderstruck`
  fails with nothing moved, showing "No such file or directory". Admin only. One
  line fixes both: replace `/` with `-` on every platform, as Windows already
  does. Not ruled. Record: `plans/song-files-rename-delete.md` on tag
  `archive/song_files`, follow-up gap 4.~~
  Fixed 2026-11-08 as `e7047fd` on `dev` (`fa2cf36` on tag `archive/song_files`).
- ~~**An empty new name hides the song.** The batch renamer accepts a blank name
  box: the video becomes `.mp4` and its files `.srt`, `.custom.txt` and so on,
  which the library scan skips, so the song drops out of the library while the
  DB points at `.mp4`. The edit page appends the YouTube ID, so there it only
  hits a song without one. Admin only. Refusing a name that is blank after
  sanitizing, in `SongManager.rename`, covers both pages. Not ruled. Record:
  `plans/song-files-rename-delete.md` on tag `archive/song_files`, review 2026-11-08.~~
  Fixed 2026-11-08 as `e7047fd` on `dev` (`fa2cf36` on tag `archive/song_files`).
- **A live song can claim a deleted song's backups.** Who owns a
  `regen_backups/` file is worked out from the songs that exist now, so with
  `Song.live` deleted and `Song` live, renaming `Song` carries `Song.live.srt`
  into the new name's history. Needs one name to be another plus `.something`;
  a YouTube ID ending every name rules it out. Not ruled. Record: review of
  `e755108..d80402b`, 2026-11-08 (no plan file; this entry is the record).
- **A backup file that can't move blocks the rename.** A rename moves the song's
  `regen_backups/` copies too and rolls everything back if one fails, so a
  read-only snapshot folder, or on Windows a backup open in an editor, leaves
  the song unrenamable until cleared. Not ruled. Record: same review.

## Display tidy (on `dev`)

- **A bracket with one junk word goes whole.** `(Official Live Video)`,
  `(Acoustic Video)` and `(Instrumental Version)` drop entirely, losing the
  live, acoustic or instrumental marker, so different versions tidy to the same
  name. The tidy did the same before `d80402b`. Not ruled. Record: review of
  `e755108..d80402b`, 2026-11-08 (this entry is the record).
- **CJK-style junk isn't recognised.** Full-width `（Official Video）`, `【MV】`
  brackets and a bare trailing `Official MV` stay in the tidied name. Before
  `d80402b` those titles came out mangled instead (`- LemonOfficial Video`). No
  song in the library starts with CJK today, so the A–Z bar is unaffected. Not
  ruled. Record: same review.
- **Thousands of stacked junk brackets are slow.** Each stripped bracket rescans
  the name: 8 KB of `(4k)(4k)…` costs 0.15 s, 32 KB 2.5 s. Filenames cap at
  255 bytes, so only the `/metadata/tidy-name` route takes such input. Linear
  needs a loop that finds the last opener itself and copes with nesting. Not
  ruled. Record: same review, and `a4b56ba`.
- **Joined emoji leave invisible joiners.** U+200D survives the emoji strip, so
  `Song (Official MV) 👨‍👩‍👧` keeps two invisible characters and, behind them,
  its junk bracket. Older than `d80402b`. Not ruled. Record: same review.

## Search results (on `dev`)

Found in the `search_official_first` review and its live checks, 2026-11-08. Ken left the
review's other findings for now. Record: `plans/search-official-first.md` on tag
`archive/search_official_first`, "Review follow-ups" and the Results log.

- **A restored search page can show a stuck card.** After Show more, the page saves the cards
  so coming back to Search restores them. The copy can catch a card's loading state or the
  preview modal's last contents, and the restored card then keeps a stuck loading button.
  Left by Ken 2026-11-08.
- **A "Song - Artist" title is read the wrong way round** when the query also names the
  artist: for "queen bohemian rhapsody", "Bohemian Rhapsody - Queen" credits the song name as
  the artist. Official uploads are nearly always "Artist - Song". Left by Ken 2026-11-08.
- **The ranking repeats work.** Each row re-normalises the query, and the lift walks the list
  three times. Thirty rows, so nothing visible. Left by Ken 2026-11-08.
- **A verified re-upload can be lifted as the music video.** "old town road" lifts the
  verified channel Wicked Sounds' "Lil Nas X - Old Town Road (Music Video)". A verified
  channel whose title says "music video" counts as a label upload without any check that the
  channel is the artist's or a label's. Not ruled.
- **A band whose channel spells its name another way gets no lift.** "celebration kool and the
  gang": the channel is "KoolandthegangShow", so the band's full name gets no channel credit
  and ties with its split-up parts; nothing is lifted and the page keeps YouTube's order. Not
  ruled.
- **YouTube sometimes drops the channel fields.** About 1 in 12 live searches came back with
  no channel, uploader, verified flag or description on any row; nothing is lifted and the
  channel line is missing, as before the branch. YouTube-side; recorded, not chased.

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

## Edit words (on `dev`)

Landed 2026-11-03 as `90c37f2`..`03dff3a`. Record: `plans/edit-words.md` on tag
`archive/edit_words`, its "Later (not scheduled)" list. GATE R ruled stop (row
18): no automatic Romanize suggestion; the probe `scripts/romanize_probe.py` and
its pick, `koroman`, are there if the question comes back.

- **The Repair page's Movie subtitles box is empty after a word edit.** The box
  is filled from the song's saved movie sheet (`custom_start`), and saving an
  edit removes that sheet, so a song with an edited movie sheet opens Repair with
  the box empty while its card says "current (edited)". Found by the Phase 4
  review (finding 5), not taken for 4.1. Needs a ruling on which sheet fills the
  box.
- **"Play this line" on the Edit words page**: a button per line that plays the
  song from the line's start. Ken, 2026-11-02: a later phase, not scheduled. No
  admin page plays audio today, so it needs a route that serves the song's audio.

## Cue align windows (on `dev`)

Landed 2026-11-05 as `f47f879`..`2e5d389`. Record: `plans/cue-align-windows.md`
on tag `archive/cue_align_windows` (Decisions 12-18, Results log). A line the
section align left short of its words, or with zero-length words, gets a
one-line re-align whose window ends where the singing stops; words still
missing are guessed and shown, never dropped. "Row" and "finding" below point
into that plan's Results log.

Library state:

- **Library regenerated at `7bb144d`** (Windows GPU, backup
  `regen_backups/20261105T201224Z`): the 10 test songs and the 15 others that
  showed "Missing from the screen". No song shows it now. Row 64's
  ten edges reproduce exactly on All of Me, Someone Like You and Baby One More
  Time; Miss Independent was regenerated from Ken's `caption-edited.srt`, where
  line 2 is no longer re-aligned, so its pair sits at its pre-branch times
  (1 ends 8.92, 2 starts 9.02). Ken listened 2026-11-06: most moves are too
  short to hear; the longer ones (Baby One More Time, All of Me) are good.
- **Guessed words left after the regen** (shown, timing guessed): Stronger 3,
  Climbing Uphill 3, Inconsolable 2, One In A Million 2, Tornado 2, A Little
  More Time On You 1, each on one line.

Heard at GATE B, not fixed:

- **The second of a repeated word lands 0.4-0.5 s late.** Baby One More Time
  "Oh baby, baby" at 0:28, 0:38, 2:22 (0:38 also before this branch); Ken: the
  two should be about equal. The aligner's own timing (Decision 18, row 63).
- **Miss Independent's captions do not match the video.** "God damn" is not
  sung (likely censored); "Ooh yeah" lines are sung "yeah yeah", and the
  transcriber finds no words on most of them. The fix is the song's caption
  text via Edit words (Decisions 12, 18; rows 33, 63).
- **Pocahontas "wind" is placed before the singer's pause.** The window holds
  the whole note, but both aligns put "wind" before the 1.2 s pause; the line
  has every word, so nothing flags it (Decision 12, rows 14, 57).
- **The guard rejects a correct re-align at Miss Independent 3:59** (line 79:
  the unguarded re-align matched the transcriber). Ken left it (Decision 16,
  row 61).

Onset snap:

- **A line starting on the previous line's held note is taken as on time.**
  Onset snap skips a line whose first word is loud at its claimed start, and the
  end snap then stops the held note just before it (Someone Like You 3:48
  "instead"). `bb7c8ca` lifts the skip for re-aligned lines only. Lifting it for
  every line that starts at the previous line's end moves 47 lines on the 10
  test songs, 13 further from the heard start; it needs its own probe over the
  library. Older than this branch, shared by every timing source (Decisions 12,
  17; rows 36, 63).

The rescue (review findings and decisions kept as built):

- **Repeated tokens get two assignment rules** (row 44, findings 3-4). The
  in-order match puts a word on the earliest repeat of its token, the time match
  on a later one. Fix: carry each word's token index on the line object from
  `_match_words_to_tokens`, which also removes `_assign_in_order`. Same
  prerequisite as Decision 12's unruled splice (keep the section's words, take
  only the missing ones from the re-align).
- **Duet ending** (row 44, finding 6): the song's last line is the last by
  index, not the latest-ending one, so an earlier line held past the last cue
  gets no tail window and the last line's tail runs over the other singer.
- **The last line's window has no hold cap** (row 44, finding 5). Uncapped on
  purpose (the final note is often the longest), but outro ad-libs widen the
  window and the span the re-align is checked against. A cap needs the length
  of real final holds across the library first (Decision 16).
- **The guard does not see the previous line's held note** (row 44, finding 7).
  A re-aligned line may not start before the previous line's last word ends,
  but it can still start on that word's note past its timed end. How often is
  not measured (Decision 16).
- **The guard looks only backward** (row 51, finding 6): a rescued line's last
  word is never checked against the next line's first.
- **A re-paced line can start before the previous line's end** (row 51,
  finding 3). Not built: the 3 cases on the test songs (Miss Independent 5, 7,
  37) are fills placed right, with the previous line overrunning into them;
  starting them later would put line 7's six words in 0.62 s (row 65).
- **Zero-length words a failed rescue leaves stay on screen** (Decision 14,
  kept as built by Decision 16). The guess pass skips a line with a word for
  every token, so they show as 0.1 s fills. Guessing them instead is option
  (b), measurable on the CPU from the bundles' `cue_inputs`.
- **One zero-length word makes a line crammed** (Decision 15, kept as built).
  Costs 75 more one-line aligns on the 10 test songs (209 against 134, row 45);
  every partial line takes its own slice align too (row 24, finding 10).
  Options (b) two or more words, (c) a bound on how far timed words may move.
- **Should Song Info's guessed-words count include zero-length words left on
  screen?** (Decision 13.) Unchanged today.
- **`align_song` deep-copies sections and re-align words with debug capture
  off** (row 51, finding 10).

Older than this branch:

- **The `\kf10` floor's added time is never taken back.** `generate_ass` gives
  every word at least 0.1 s, so a run of floored words pushes the rest of the
  line late until its next gap: overrun of 0.3 s or more on 34 lines in 23 cue
  songs (Decision 14, row 43).

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
- ~~**An LRCLIB match the admin has checked becomes the song's timing (Repair).**~~
  Done; see the last paragraph.
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
  Built on branch `lyric_source_lists`, now tag `archive/lyric_source_lists`
  (plan `plans/lyric-source-lists.md`); landed on `dev` 2026-10-30 as
  `1a5d059`..`c99e632`, the core being `7e69533`, `1b354c6`, `8767f65` and
  their fixes up to `39aa25a`. Ken's end-to-end checks passed 2026-10-30
  (Results row 21). Point 3 ruled
  2026-10-29 (Decision 4): viable means the fit passes and the length gap to
  the video is small, with the flagged lines shown before the admin confirms.
  GATE A set the numbers (Decisions 8-9): a line heard more than 5 s from its
  fitted time is mistimed, 2 mistimed lines make a flagged run, 3 unheard
  lines make a "couldn't check" note, and the gap limit is 15 s. Decision 11
  (2026-10-30): a fit that passes may override the gap limit with a checkbox.
