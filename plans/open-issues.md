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
  `plans/search-caption-check.md` on tag `archive/search_caption_check`.

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

- ~~**The pick box's starting search keeps trailing words of a long YouTube
  title** (`library_regen.default_query`). Defying Gravity's search came back
  empty until the box was edited. Fixing it means a new title-cleaning rule.
  Record: web plan, Phase 7 row.~~ Closed 2026-11-16 by `genius_search_accuracy`
  (`64b4a0d4`): the pick pass's and Repair's Genius boxes start from
  `genius_query.start_query`, which drops a title's junk tail, and an unchanged
  box runs the title's whole query ladder. Defying Gravity's search was not
  re-run. `default_query` still starts the Repair page's LRCLIB box.
- **A service outage reads as "no results."** `/lyrics_search` returns `[]` on
  any Genius failure or a missing token ("No Genius results."), and
  `lrclib.search` returns `[]` on a 503 or timeout. `routes/search.py` is shared
  with the search page. Record: web plan, 6.1e and the Phase 6 row. Since
  `genius_search_accuracy` it also costs time: a failed call reads as "found
  nothing", so the title search asks its next query, and a Genius that times
  out holds a lookup for up to three 15 s calls on the search page (two on the
  pick pass, Repair and the prompt), each holding `GeniusClient`'s lock. Fix
  shape: `search` tells a failure from an empty answer and the ladder stops on
  a failure. Record: `/code-review` of `eb8d4be0..3743f4f2`, finding 2,
  logged in `plans/genius-search-spec.md` on tag `archive/genius_search_accuracy`,
  Results row 14.
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
  normalizes the sheet text twice; ~~`routes/song_info._typed` repeats
  `library_tools._pick_text` without its length cap, so the POST LRCLIB search
  sends title and artist uncapped~~ (`_typed` is gone and both LRCLIB search routes cap
  their query with `library_tools.pick_text`, `56903467`, from `lrclib_fit_pick`'s
  `182905e5`). Record: `plans/custom-lyrics-sheet.md`, Code review rows 7-8.
- **`add_songs --folder` defaults to `~\pikaraoke-songs`** (`get_default_dl_dir`)
  instead of `config.ini`'s `download_path`; `regen_alignment_bundles.py` on
  `dev` has the same default. The status report has no title column. Record:
  `library-tools.md`.
- **CLI paths never run on real data:** `regen --song --reset` and backfill's
  queued path. Record: `library-tools.md`.
- **Simplicity leftovers:** ~~`_ActiveJob.kind` is set and never read~~ (dropped,
  `da11a06b`); `prepare_regen_job` accepts plan kinds no caller builds; ~~the
  int-not-bool Genius id check is written three times~~ (the route checks share
  `library_tools.is_whole_number`, `13dbee03`, from `genius_search_accuracy`;
  `_Entry.genius_id` still checks `isinstance(..., int)` and lets `true`
  through); ~~the watch URL is built in more than one module~~ (one
  `library_regen.watch_url`, `f4aa97b`). Record: web plan, 3.1i and 8.1f.
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
- **Whisper's refine pass may not earn its cost.** Refine is about 80% of every
  align+refine call: 78-157 s per cue song and 36-59 s per joint song in a
  14-song probe (2026-11-11). On the joint route it barely moves the output
  (most lines take transcribe timings, and edge snap owns line starts). On the
  cue route it moves many words about 0.4 s later, the direction of whisper's
  early-onset bias, but no reference on hand can say whether that is right.
  Ruled since (Ken): cue refine stays on after the blind listen (2026-11-14, on
  tighter on 3 of 4 songs); joint refine-off closed no-go, untested
  (2026-11-16). Open: a coarser `precision` (fewer positions tried per word),
  reopened 2026-11-16, untested, not scheduled. Record:
  `plans/refine-ablation.md` on branch `refine_ablation` (probe, report script
  and raw results under `scripts/`).

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
- **Unify the channel cleaners once `search_official_captions` lands.**
  `official_rank.py` and `genius_query.py` each work out what act a channel's name
  stands for, with their own noise words, kept apart while that branch rewrites
  `official_rank`'s. Once it lands: one function for the name, each module keeping
  its own list of names that stand for no act (the ranking's short, the Genius
  module's wide). Not ruled. Record: `plans/genius-search-spec.md` on tag
  `archive/genius_search_accuracy`, Calls item 3 and "Channel names".
- **A Genius hit is preselected when it does not account for the whole video title.**
  GATE G found two in 63 preselects, both film or stage: a hit titled `You Will Be
  Found (Reprise)` for a video of the full song, and `Mamma Mia — Meryl Streep` for
  `Mamma Mia! - The Winner Takes It All - Meryl Streep`, whose middle part the parse
  dropped. Both are pinned in `test_genius_query.py`. A guard that withholds the
  preselect when the hit's title carries a bracket the video's lacks, or a dash part
  went unread, can only withhold; its cost (right preselects withheld) is countable on
  the 500 frozen titles with no network. Not ruled, including whether it needs a new
  gate. Record: `plans/genius-search-spec.md` on tag `archive/genius_search_accuracy`,
  "Ruling on the failed gate" and `plans/genius-search-accuracy/gate_g/verdicts.md`.
- **For a film or stage video the first Genius hit is wrong about 4 times in 10.**
  GATE G: 18 of 47 on fresh titles, against 6 of 43 on the library titles the order
  was shaped on. Seven are another recording of the song (a later film, a stage cast,
  a live cast), eleven another song (the film's name read as the title, a page by an
  act named like the show). Apart from the two above none was preselected: the page
  asks the person to choose, with the year and artist shown. Shipped as it is (Ken,
  2026-11-16): no order tried fixes one film title without breaking another. Record:
  as above.

## Movie splits (on `dev`)

Found in the `scripts/split_songs.py` code review, 2026-11-08 (`c6be664` on `dev`; the
fixes Ken took landed as `5cbc495`..`c350c40`). Ken left these for now. No plan file: the
script's rules and workflow are in `scripts/movie_split.md`, and this entry is the record.

- **A camera cut in the gap between two back-to-back captions counts as nobody talking.** A
  moment with no spoken caption up is clean however loud the voice track is, and subtitlers
  leave a gap of a frame or two between captions, often right at a camera cut. Requiring a
  quiet voice within 0.15 s of any spoken caption closes it, but on FOTC that moves Carol
  Brown's start 32 s earlier and pulls about 15 dialogue lines in. Its start sits in a 0.1 s
  gap between two lines, at the hand-set music start, so the loud voice track there may be
  the music. A rule question for Ken: does a gap between back-to-back lines count as a
  pause? Not ruled.
- **Config patterns and titles aren't checked.** `source` and `subtitles` are globs in the
  folder the clips are written to, so `source = "*.mp4"` also matches the clips on a second
  run. `[1080p]` in a pattern is a glob character class, a `{` breaks the `{episode}` fill,
  and a title with `/` writes into a missing folder. All of these fail loudly. The silent
  one, two songs with the same title in different episodes overwriting each other's clip,
  is ruled out by the no-reprise rule.
- **`srt` re-derives the edges** instead of reusing the spans the mp4 was cut with. After a
  config or constant change, or a re-run separation, the rewritten SRT can be timed to other
  spans than the video, with no warning. Until then: run `srt` before deleting `split_cache/`
  and without touching the edge fields.
- **Music-tag words match inside other words.** "beat", "playing" and "music" match anywhere,
  so "[ heartbeat ]", "[ kids playing ]" or "[ music box clicks ]" before a song can be read
  as its music start and pull in a silent stretch. The plan line's long lead shows it.
- **`plan` spends about a minute of pure Python on a 20-song show.** The spoken-caption test
  runs a regex per cue for every candidate moment, and the quiet threshold is recomputed for
  every moment.

## Web pages (pre-existing on `dev`)

Found 2026-10-27 during the `queue_hold` manual checks on the Windows box.
Record: `plans/queue-hold.md` on tag `archive/queue_hold`, the manual checks row.

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
- ~~**The direct box ignores its own Add to queue tick.** `downloadSong` in
  `search.html` sends `$("#add-to-queue-search").is(":checked")`, and that box
  exists only when search results are on screen; with none, the download is
  never queued. The two ticks are kept in sync, so reading
  `#add-to-queue-direct` (always on the page) fixes it. Upstream code, also on
  `master`. A one-line fix was offered on `queue_hold`; not ruled.~~ Fixed
  2026-11-16 as `58ccd638` (landed from `genius_search_accuracy`, where Ken took it
  from the review triage): `downloadSong` reads `#add-to-queue-direct`.

## Landing order (every open branch)

Proposed by Claude Opus 5.5, 2026-11-18, from the branch plans and file overlaps at the
hashes named. Ken asked for it to be recorded; the order itself is not ruled beyond what each
plan already says. Each branch's own dependency notes stay in its plan, which wins where it is
more specific. Update this section when a branch lands or its gate moves.

The phone overhaul's two gates: `singer_defaults` Phase 5 puts L1, L15 and L16 in
`bulma-dark.css`, which every phone branch takes from `dev` ("Phone pages: one look", below);
`queue_phone` creates the shared row style that Browse, Processing and the Search restyle reuse
(`plans/queue-phone.md` decision 1).

Stage 1, can run now, side by side:

- `singer_defaults` (`fafc262`): Phase 5 (commit 1 the theme, `bulma-dark.css` only; commit 2
  L6, the name in the nav bar), the `/code-review` of Phase 4 that is due, Ken's Phase 6
  checks.
- `download_modal_speed` (`d3128ba`): commit 3b (L7), `/code-review`, Ken's phone checks. Its
  grey and disabled looks arrive with the theme; no build dependency on `singer_defaults`.
- `search_official_captions` Parts 1-2 (`5f1b446`): commit 9 (L11), the review of commits 5-8,
  Ken's manual checks.
- `queue_phone` (`0439038`): spec and phases written 2026-11-18. Its Phase 1 (server only:
  the failed row, the pause route, song and artist on queue rows) needs nothing from
  `singer_defaults` and can run now; Phases 2-3 wait for stage 3.
- `browse_phone` (`c2de136`): Phase 0 (name-source test, offline) and GATE N. Queue's row
  names use the file-name split until GATE N rules (`plans/queue-phone.md`, "Names on the
  rows").

Stage 2, landing:

1. `singer_defaults`, then `now_playing_remote` (`254bec0`) right after it. The latter is built
   on the former: rebase once Phase 5 is committed, then its Phases 1-4
   (`plans/now-playing-remote.md`).
2. `search_official_captions` Parts 1-2 and `download_modal_speed`, one after the other: both
   edit `youtube_dl.py`, `routes/search.py`, `search.html` and `search_result.html`. Proposed:
   Search first, since its commit 7 makes `#add-to-queue` the surviving box and
   `plans/download-modal-speed.md` ("At landing") already says how the second one repoints
   `queueAfterDownload()`. If the dialog clears Ken's checks first, it goes first and the same
   note applies the other way.

Stage 3: `queue_phone` code, after `singer_defaults` is on `dev`. It takes L1, L15, L16 from
`dev`, and its L14 nav half and `singer_defaults`' L6 both rewrite the nav bar in `base.html`;
landing `singer_defaults` first leaves no conflict to resolve. Failed row first, then the nav
change (L14).

Stage 4, after `queue_phone` lands, side by side:

- `browse_phone` Phase 1, after GATE N.
- `processing_phone` (`f28d582`), after its open question on group order under All is ruled.
- Search Part 3 (L12, L13), after `download_modal_speed` lands as well: it restyles the
  dialog's controls.

Independent of the phone order:

- `lrclib_fit_pick`: landed on `dev` 2026-11-18 (`0d203816`..`ee7062af`), retired as
  `archive/lrclib_fit_pick`. It changed
  `processing.html` and `routes/processing.py`, which `processing_phone` rewrites, so that
  branch writes its code on top of this `dev`. Its other overlaps (`routes/processing.py`
  with `singer_defaults`, `library_regen.py` with `download_modal_speed`) are in different
  functions.
- `defer_timing` (`9e7f6da`): plan only, parked behind `lrclib_fit_pick` (Ken, 2026-11-10),
  which has now landed.
- `chinese_karaoke` (`9900277`): probe scripts under `scripts/zh_probe/` only; research, not a
  landing candidate.
- `whisper_input_fresh_vs_regen` (`ed96958`): an experiment; its code commits are
  onset-loud-start's, already on `dev` (`archive/onset_loud_start`). Nothing to land; retire
  when done.

- `refine_ablation` (origin only, `c713bec`): research; one open item, decision 3 (a coarser
  `precision`), unscheduled. Stays until that is run or dropped (its "Next step").

Retired 2026-11-18 (every code commit patch-equal to one on `dev`; the rest only plan
records): `archive/movie_split`, `archive/queue_hold`, `archive/search_caption_check`.

Not ruled (Ken's calls):

- Land `singer_defaults` Phase 5 commit 1 (the theme) on `dev` ahead of the rest of the branch,
  so `queue_phone`'s code can start sooner. Bends landing in order; proposed only if
  `singer_defaults` stalls at its checks.
- Search Part 3 on a fresh branch off `dev` after `queue_phone` (proposed), or keep
  `search_official_captions` open until Part 3 is done and land all three parts together.

## Phone pages: one look (branches `browse_phone`, `queue_phone`, `processing_phone`, `search_official_captions`, `singer_defaults`, `now_playing_remote`, `download_modal_speed`)

Style and palette review, 2026-11-18 (Opus), of the seven branches' UI at `3b4d5cc`,
`0417a8c`, `af9d11a`, `3968c1a`, `13b96f2`, `52a9ce7`, `ce4fa69`. Canvas with every settled
screen side by side, a palette board, and a drift note per row (private to Ken):
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL. Its screens are copies of the
agreed mockups, so those stay the record of each page's decisions; the download dialog's
are its mockup's (Bx2pwN8RgLPcFjN4hawcSQ) with Queue in the colour it was built in.

The reference look is Queue v2 / Browse v2 / Processing draft 1: `bulma-dark.css`
greys, a `#343c3d` card, 17/13 px two-line rows, a 44 px state slot, 40 px square
buttons with 6 px corners, `#375a7f` for a chosen option, `#2ecc71` for a tap that
queues, dashed slots for a state.

- **Two greens are live.** `.button.is-success` and `.tag.is-success` use the theme's
  `#2ecc71` (`bulma-dark.css`); `has-text-success` and `--bulma-success` are Bulma's
  own `#48c78e`, as are singer names on `dev` today. Likewise two ambers: `#f1b70e`
  (buttons) and `#ffb70f` (`has-text-warning`, the song titles on Now Playing).
- **`now_playing_remote` ruling 9 rests on a wrong fact.** It picks `--bulma-success`
  as "the same as singer names and Save", but Save is `is-success`, so `#2ecc71`.
  The spec's knob, fill and chosen Lyrics button would be the only `#48c78e` fills.
- **Green means two things.** Every v2 page uses green for "tap to queue" and blue
  `#375a7f` for a chosen option. Now Playing (ruling 6) and the guest form use a green
  fill for the chosen lyric style and for the slider knob.
- **Now Playing spec, other drift:** a near-black `#14161a` control panel, 12-14 px
  corners and 56-64 px buttons, no `#343c3d` card behind the content.
- **Guest form as built on `singer_defaults`:** a plain Bulma modal with a native
  slider and `-`/`+` buttons. The spec swaps its controls, not its look.
- **Search as built is still Bulma defaults:** a yellow (`is-warning`) Search button,
  white inputs, 4 px corners, 40 px buttons; the Official tag and the In library note
  are `is-info is-light` pale-blue boxes, the only light surfaces in the app; a third
  blue (`#6cb8ea`) for the YouTube link and a grey `#a3b0b2` for the channel; titles
  16 px regular, not 17 px bold. Search plan decision 8 asked for the light tint.
- **Download dialog as built on `download_modal_speed`:** its Queue button is the
  chosen-blue `#375a7f` (`is-primary`, as the old Download button was; the mockup drew
  it teal `#00d1b2`), while every other Queue, the in-library card's on the same page
  included, is green `#2ecc71`. The rest is the Search page's Bulma look: an amber
  Search button, a white list and input, 4 px corners, `#a3b0b2` for the channel line
  and hints, no `#343c3d` card (the content sits on the dark backdrop). In the style:
  the 48 px list with its teal arrow, the 17.6 px bold title, the shared (i), amber for
  "No lyrics found" (a state, as on Processing).
- **Small gaps inside the v2 group**, for Queue's shared stylesheet to settle when it
  lands: the slot is 52 px on Queue, 60 px on Browse and Processing; "processing" is a
  solid blue Queue button on Browse but a dashed grey slot on Queue and Processing;
  the chevron opens a menu on Browse and expands the row on Processing (Queue uses a
  gear); the 13 px sub-line grey `#b5bfc0` is not a `bulma-dark.css` token yet.
  **Ruled 2026-11-18** (`plans/queue-phone.md` on `queue_phone` `0439038`, S1-S4): the
  slot is 60 px everywhere; solid means a tap and dashed a state, so Browse's green
  button and the dashed slots both stay; a gear opens a menu and a chevron expands a
  row, so Browse's admin button becomes a gear (`browse_phone` `c2de136`); `#b5bfc0`
  becomes a token on `queue_phone`.

Ruled by Ken, 2026-11-18. Each item names the branch that owes it. Written into each
owner's plan as L1-L16, no code yet: `singer_defaults` `fafc262` (its Phase 5),
`now_playing_remote` `254bec0`, `download_modal_speed` `d3128ba`, `browse_phone`
`f852240`, `queue_phone` `572ec80`, `processing_phone` `f28d582`,
`search_official_captions` `5f1b446`. The canvas shows items 1-16 and is the reference
look for the phone pages.

Colour meanings, every page:

1. **One green, one amber.** `#2ecc71` means a tap that queues; `--bulma-success` (so
   `has-text-success`) points at it in `bulma-dark.css`, and `--bulma-warning` at
   `#f1b70e`. Singer names and Save use that green. Lands first, on `singer_defaults`
   with 15 and 16 (placed by Ken, 2026-11-18).
2. **Blue `#375a7f` means chosen**, never an action: picked toggles, letters, chips,
   the chosen lyric style, the slider knob and fill (knob text white), BRB when on.
3. **Teal `#1abc9c` is for links and the current nav icon only.**
4. **Other actions are neutral grey:** a `#343c3d` fill (`#434d4e` since 15) with a
   `#5e6d6f` border and bold white text for a row's main action (Retry, Preview, Check
   playlist), an outline for the rest (Song info, Repair). Red outline stays for delete.

Per page:

5. `now_playing_remote`: rulings 6 and 9 change. The transport stays grey, but not
   because "green means chosen here"; the chosen lyric style, knob and fill are blue with
   white text (ruling 9's `--bulma-success` goes). Song titles use `#f1b70e`. The spec's
   mockup drew a grey nav bar; the app's blue bar stays. The near-black panel and 12-14 px
   corners are not ruled.
6. `singer_defaults`: the name leaves the burger menu for the nav bar on phones too: a
   sliders icon (not a gear: Queue rows use a gear for options) and the name, white, in a
   thin outlined pill, no chevron; it opens the guest form. Long names cut with an
   ellipsis (about 70 px for the name on a 390 px phone). The nav icons narrow from 50 to
   44 px to make room. The same icon replaces the mic beside the name on desktop. The
   edit form's title becomes "Your singer settings"; the join form gains one line under
   its controls: "Change these any time from [icon] <name> at the top of the page."
7. `download_modal_speed`: the dialog's Queue is green (`is-success`), now, before Ken's
   phone checks. Its button text stays "Queue" also when opened from "Download…" (13).
   Unticked, its "Add to library" is the raised grey of 15 (Ken, 2026-11-18).
8. `browse_phone`: the "Queue / processing" button is green, not info blue `#3298dc`.
   Empty letters take 16's disabled look, not the canvas's dimmer pill (Ken, 2026-11-18).
9. `queue_phone`: BRB is a grey button when off and blue when on (was teal).
10. `processing_phone`: Repair is a grey outline; Retry, Preview, Check playlist are
    neutral grey (4). Info blue stays only for the running-job spinner and step bar.
11. `search_official_captions`: the card's "Queue…" is green, like every Queue.
12. **Search's card restyle waits** (was call 3): its own pass after `queue_phone` lands
    its shared stylesheet, taking the download dialog's controls (Search button, list,
    input, no card) with it. Order: `queue_phone` lands, then the Search pass, which
    carries 13. Partly reverses Search decision 8 (the light tint).
13. **The In library note becomes a dark row** (option A), in the Search pass: `#282f2f`,
    6 px corners, the Browse folder icon, "In library" over the file name, a full-size
    green Queue. On a card with a library match, the card's own button reads
    "Download…" in neutral grey, to steer guests to the copy they have; cards without a
    match keep the green "Queue…".
14. **Processing is the admin's only.** Its nav icon is hidden from guests (the page still
    opens by its address, as with Now Playing's hidden controls), which frees an icon's
    width for the name. Before it goes: a guest's own song that fails processing stays
    on Queue as a red "failed" row with a short reason and Dismiss, until dismissed
    (today queue hold removes it with a passing notice, `queue_hold.py:157`). No step
    detail on Queue rows: Ken, guests prefer less information. Check that nothing a guest
    sees links to Processing. `processing_phone`'s guest view is dropped. Owner:
    `queue_phone`, the failed row first and then the nav change, so the order stays in
    one branch (placed by Ken, 2026-11-18).

Buttons, every page (Ken, 2026-11-18, drawn on the canvas; owner `singer_defaults`, in
`bulma-dark.css` with 1):

15. **Grey button fill `#434d4e`**, one step above the `#343c3d` card, so a button sits
    raised on it. Replaces 4's `#343c3d` fill; the `#5e6d6f` border stays.
16. **Disabled, whatever its colour:** no fill, a faded border (`#5e6d6f` at half
    strength), a `#8c9b9d` label, no opacity fade. A white label always means a tap
    works.

The "Small gaps inside the v2 group" above were ruled 2026-11-18 (S1-S4 in `plans/queue-phone.md`).

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
- **The other 65 caption-timed songs regenerated 2026-11-06** (Windows GPU,
  backup `regen_backups/20261106T170716Z`, checked by Ken). The first regen
  missed them because zero-length words don't show as "Missing from the
  screen" (they show only as runs of `\kf10` in the `.ass`). The library was
  mass-renamed afterwards, so stems in older lists may not match; select by
  YouTube ID.
- **Guessed words, library-wide on 2026-11-09** (`library_status._cue_fields`
  over all 114 cue bundles; none in the old format, none with missing words;
  words shown, timing guessed, lines in brackets where more than one): Rent
  Will I 12 (4), Rent What You Own 8 (3), Miss Independent 4 (3), Stronger 3,
  Climbing Uphill 3, Rent I Should Tell You 3, Inconsolable 2, One In A
  Million 2, Tornado 2, Best Part Of Me 2, Tribute 2, You Don't Love Me (Like
  You Used To Do) 2 (2), A Little More Time On You 1, Never Had A Dream Come
  True 1.

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
- ~~**The guard rejects a correct re-align at Miss Independent 3:59** (line 79:
  the unguarded re-align matched the transcriber). Ken left it (Decision 16,
  row 61).~~
  Fixed by the guard lift (`fecebdd2` on tag `archive/cue_heard_rescue`):
  a re-align the transcriber confirms as the aligner returned it is no longer cut to
  the previous line's end. 3:59 itself was not heard again: the staged copy of the
  song has no lifted line (`plans/cue-heard-rescue.md` on that tag, GATE H item 3).

Onset snap:

- ~~**A line starting on the previous line's held note is taken as on time.**
  Onset snap skips a line whose first word is loud at its claimed start, and the
  end snap then stops the held note just before it (Someone Like You 3:48
  "instead"). `bb7c8ca` lifts the skip for re-aligned lines only. Lifting it for
  every line that starts at the previous line's end moves 47 lines on the 10
  test songs, 13 further from the heard start; it needs its own probe over the
  library. Older than this branch, shared by every timing source (Decisions 12,
  17; rows 36, 63).
  Library probe 2026-11-10 (133 cue songs replayed on the CPU): 1174 of 6553
  lines start more than 0.3 s before the transcriber's first word, 954 of them
  skipped as on time, 678 of those starting at the previous line's end. The "13
  further" above is not a cost: the same reference calls 601 of the 1710 snaps
  that ship today further, so it cannot judge a start move, and Ken's ear has
  to. Ken, 2026-11-10: own branch, first rule to try is a move only where the
  transcriber's first word agrees with the rise. Record:
  `plans/onset-loud-start.md` on branch `onset_loud_start`.~~
  Fixed where the transcriber hears the first word at the rise (`fa91d145`,
  `eb7d1ffb`, `ff76a886` on `dev`, schema 12): a loud start moves there, and a
  first word the transcriber also heard earlier keeps its start. The 133-song
  replay moves 589 lines and holds 4. A line whose first word the transcriber
  does not hear at the rise is still taken as on time. Library songs change only
  when regenerated; the full regen is Ken's, later. Record:
  `plans/onset-loud-start.md` on tag `archive/onset_loud_start`.
- **The repeated-first-word guard needs both copies heard** (Results row 13).
  A line that starts with an echo of its own next word keeps its start only when
  the transcriber heard both copies; with only the second heard it still moves
  to a sliver before word 2. The two lines of that shape in the replay are among
  the four held, so none of the 589 moves is one. Said in `snap_line_onsets`'s
  docstring.
- **A joint song's lines can stack on one instant, zero length, when the heard
  words shift** (Results row 14). Already in pass 1, so not the onset snap's:
  `hvvjiE4AdUI` lines 41-43 all at 230.62, `1YiAzyCzZzw` lines 57-60 at 175.14,
  `pXNd2V88d60` lines 56-62 at 296.08, each on a song whose v11 bundle was a
  Windows capture. Heard in Ken's listen of the 13 songs, 2026-11-16.
- **Windows and Linux whisper give different words for the same song** (Results
  row 14). 11 of the 13 regenerated songs had Windows v11 bundles; their heard
  words differ from this box's by 5 to 88 of 340 to 777, with the config equal
  but the model path, and a second run here repeats the first exactly. So a regen
  on one box moves lines on songs last captured on the other, apart from any rule
  change. Ken, 2026-11-16: does not gate the onset snap. The cause is not settled
  in this file.

The rescue (review findings and decisions kept as built):

- **Repeated tokens get two assignment rules** (row 44, findings 3-4). The
  in-order match puts a word on the earliest repeat of its token, the time match
  on a later one. Fix: carry each word's token index on the line object from
  `_match_words_to_tokens`, which also removes `_assign_in_order`. Same
  prerequisite as Decision 12's unruled splice (keep the section's words, take
  only the missing ones from the re-align). `backing_vocal_lines`: an echo line
  repeats its lead's words within one line ("Baby (baby)"), so the in-order
  guess can put an echo's timing on the lead's token, now a common case, not a
  rare one; watched at that plan's GATE B (B3, B4).
- **Duet ending** (row 44, finding 6): the song's last line is the last by
  index, not the latest-ending one, so an earlier line held past the last cue
  gets no tail window and the last line's tail runs over the other singer.
  `backing_vocal_lines`: a paren-only line after the last caption becomes the
  song's last line and takes the uncapped tail window.
- **The last line's window has no hold cap** (row 44, finding 5). Uncapped on
  purpose (the final note is often the longest), but outro ad-libs widen the
  window and the span the re-align is checked against. A cap needs the length
  of real final holds across the library first (Decision 16).
- **The guard does not see the previous line's held note** (row 44, finding 7).
  A re-aligned line may not start before the previous line's last word ends,
  but it can still start on that word's note past its timed end. How often is
  not measured (Decision 16).
- **The guard looks only backward** (row 51, finding 6): a rescued line's last
  word is never checked against the next line's first. The heard-aimed retry
  (rule B of `cue_heard_rescue`) moves a line's window 1.5 s or more, so it has
  the same gap, and a next line placed with every word is then kept as it is
  (`plans/cue-heard-rescue.md` on tag `archive/cue_heard_rescue`, Results log
  row 15, review finding 3). Measured on the 24-song copy: none of the 10 kept
  rule B lines ends after the next line's first word starts (row 17). Rule D,
  which had three such lines (Smokin Out The Window 45, Closer 45, Takedown 49),
  was left out. A bound would let a neighbour placed by its cue overrule a line
  the transcriber confirmed.
- **A re-paced line can start before the previous line's end** (row 51,
  finding 3). Not built: the 3 cases on the test songs (Miss Independent 5, 7,
  37) are fills placed right, with the previous line overrunning into them;
  starting them later would put line 7's six words in 0.62 s (row 65).
- ~~**Zero-length words a failed rescue leaves stay on screen** (Decision 14,
  kept as built by Decision 16). The guess pass skips a line with a word for
  every token, so they show as 0.1 s fills. Guessing them instead is option
  (b), measurable on the CPU from the bundles' `cue_inputs`.~~
  Fixed (`65438683` on tag `archive/cue_heard_rescue`): the guess pass
  re-times them like words the aligner dropped. Library songs change when
  regenerated (see "Cue rescue by the heard words" below).
- **One zero-length word makes a line crammed** (Decision 15, kept as built).
  Costs 75 more one-line aligns on the 10 test songs (209 against 134, row 45);
  every partial line takes its own slice align too (row 24, finding 10).
  Options (b) two or more words, (c) a bound on how far timed words may move.
- ~~**A partial line's guessed words take their pace from its zero-length
  words too** (found by the `cue_heard_rescue` review, Results log row 15 of
  `plans/cue-heard-rescue.md`, finding 6). The guess pass sets a guessed
  word's length from the median length of the line's words, and in a line
  with fewer words than tokens a zero-length word counts in that median, so a
  guessed word can come out as short as half the line's shortest timed word.
  Never zero: a kept line has at most half its words instant. The zero-length
  rule (`65438683`) re-times them only in a line with a word for every token.
  Fix: pace from the timed words only.~~
  Fixed (`ccb80211` on `dev`): the guess pass paces from the timed words only.
- ~~**Should Song Info's guessed-words count include zero-length words left on
  screen?** (Decision 13.) Unchanged today.~~
  Yes, since `65438683`: a zero-length word that gets guessed timing is one, and
  `n_guessed_words` and `guessed_word_line_ids`, which Song Info reads, count it.
- **`align_song` deep-copies sections and re-align words with debug capture
  off** (row 51, finding 10).

Older than this branch:

- **The `\kf10` floor's added time is never taken back.** `generate_ass` gives
  every word at least 0.1 s, so a run of floored words pushes the rest of the
  line late until its next gap: overrun of 0.3 s or more on 34 lines in 23 cue
  songs (Decision 14, row 43).

## Cue rescue by the heard words (on `dev`)

Branch `cue_heard_rescue`, ruled by Ken 2026-11-15: the rescue keeps a line the
transcriber confirms (A1), a re-align it confirms is not cut to the previous
line (the guard lift), a line heard 1.5 s or more from its cue is first looked
for there (B), and a kept line's zero-length words get guessed timing. Left
out by Ken's ear: A2 (hold a confirmed line against a re-align), D (whole lines
far from where heard) and C (retry between neighbours). Record:
`plans/cue-heard-rescue.md` on tag `archive/cue_heard_rescue`, with the probe
and compare scripts (`scripts/cue_heard_probe.py`, `scripts/cue_heard_compare.py`),
which read the stats of the three cut rules and stay on the tag.

- **Library songs change only when regenerated.** They wait for one full regen
  from `dev` now that `onset_loud_start` has landed (2026-11-16, after this
  branch and `backing_vocal_lines`); its schema bump makes every bundle stale
  anyway. Ken, 2026-11-15: no `--song` batch for this branch alone.
- **Reflection line 36 (3:11) is still about 5 s early.** The transcriber
  hears nothing there, and the line's cue-aimed retry timed three of five words
  before its window ended. Lines 35 to 37 are word for word the same in the old
  and new `.ass`.
- **Quit Playing Games line 1 is still 4 s late.** The first pass was right;
  one of its words is 1.72 s from where the transcriber heard it, so the line is
  not confirmed (A1 needs every paired word within 1.0 s) and a one-line
  re-align moves it.
- **Rule B aims at a stretched first word after a pause.** When the first heard
  word runs on from the line before ("lone first": it starts 2 s or more before
  the second), the heard start is not the line's start. Before You Go 27 now
  shows its first word about 2.5 s early (Ken: a little early).
- **Tangled line 30 stays late.** It is heard 1.47 s before its cue, 0.03 s
  under rule B's 1.5 s threshold.
- **A failed re-align cannot be told from a refused one.** The 24-song regen
  logged 18 aligner failures in 6 songs (`'NoneType' object has no attribute
  'language'` from `stable_whisper`'s `align`; 15 one-line re-aligns, 3 section
  aligns, all of those in Will I). The stats record a re-align that was not
  kept the same whether the aligner failed or a check refused it; only the log
  tells (Results log row 16).
- **If rule D or C is ever revisited.** D's three wrong moves were two lines moved
  before the previous line's start (Takedown 33, Bring It All Back 52) and one
  twin's audio in a run the transcriber only seemed to hear in full (Closer 45).
  C gave no audible gain in eight listens, and for 22 of its 96 tries on the
  library the stretch ended at a twin the cue test rejects (row 15, finding 4).
- **Rule B measures the singing end against the next line's unmoved cue.** A
  line heard early can have its window and aimed span stretch back over its own
  cue position; one heard late past the next cue's start gets no singing end at
  all. Confirmation still refuses a result on the cue position, so the cost is a
  rule B miss, not a wrong line. Fixing it reopens the ruled "the next line's
  cue stays where it is" (review of the landed set, Results log row 22,
  finding 5).
- **The heard match splits duet lines by order, not by voice.** `heard_lines`
  matches the whole song in line order, so where two cues overlap and share
  words, one line can take the other singer's words, and rule B could then move
  a right line. Needs a match that knows lines overlap; wait for a duet that
  shows it (row 22, finding 9).

## Backing vocal lines (on `dev`)

Landed 2026-11-16 from branch `backing_vocal_lines`: a parenthetical group in a
caption or LRCLIB sheet ("(oh, oh)") is shown when the transcriber heard it in
its cue's window. An inline group joins its line, and a cue of only a group
becomes a line of its own, timed by the rescue's one-line retry. Genius and
custom songs show their parentheses too. Record: `plans/backing-vocal-lines.md`
on tag `archive/backing_vocal_lines` (the Phase 2 run logs and the GATE B
listening sheets are in its `plans/backing-vocal-lines/probes/`).

- **Edit words drops a song's backing lines on save.** The page opens the
  sheet's cleaned lines, which hold no parenthetical group, and saves them as
  typed, so a song that shows backing lines loses them the next time its words
  are edited. Keeping them needs the page to show the bundle's kept groups and
  an edited sheet that keeps them as typed: a step of its own (plan, Design
  choice 3).
- **Repair's LRCLIB search scores against the backing lines too.**
  `library_tools.current_lines` returns the bundle's `lyrics.lines`, which now
  hold the added lines with their parentheses, so "mapped N of M" counts them in
  M and a record with no echo cues maps fewer of them.
- **Song Info counts an added line like any other.** `library_status._cue_fields`
  counts it among the re-aligned or paced lines, and a paced one toward the 15%
  guessed-lines share (`POOR_GUESSED_SHARE`), so a song can read as poor from
  new lines alone.
- **Re-aligning a section for an echo can cost another line its held last
  word.** A section goes back to the aligner when one of its lines gains a kept
  group, and its other lines are re-made with it. Where the aligner returns a
  line's last word shorter or later than before, the end snap that used to
  stretch it to the note's release may not fire, so the word ends seconds early
  with no echo near it. 4 old lines in 34 songs at that plan's GATE B (NSYNC -
  Thinking Of You 3:54, 5.7 s; three of about 1.1 s). Accepted (Ken,
  2026-11-15): the same re-align fixed two lines that were 6 s off. The fix, if
  wanted, is to keep every non-gaining line's first-pass words when its section
  is re-aligned, which gives those two back.
- **A group kept only because it repeats elsewhere can lead a line it was not
  sung in.** Leave the Door Open 3:46: `(Tell me that you're coming through)
  for you`, kept on a repeat elsewhere (nothing heard in its own cue), is placed
  first and "for you" lands 1.6 s later than before. Ken (2026-11-15): "for
  you" is roughly right, but he would rather the group were not in that line.
  Not ruled as a change. The candidate: do not keep a group on consistency
  alone when it leads its line (13 inline groups are kept on consistency; this
  is the one found worse).
- **An echo the aligner cannot find can cost its line a good retry.** Takedown
  2:46, `I'ma take it down (oh, da-da-da, down, ooh)`: the first pass puts the
  line 4.3 s before its cue, on `dev` as well, where the words come back clean
  and a clean line is trusted outside its cue (the transcript hears it on the
  cue, so rule B has nothing to look for). With the echo joined the line is
  squeezed and gets a retry, which finds the lead on its cue with high
  confidence and parks the echo's last word 0.2 s past the end bound, so the
  whole retry is refused and the line stays early. Ken (2026-11-16): it starts
  at 2:46 and is shown quite early; logged, nothing built. 28 retries on lines
  with a kept group ran past the end bound at that plan's GATE B; this is the
  one where the lead it found was seconds from what shipped. Two candidates,
  each a change to what the rescue keeps and needing its own replay: judge
  such a retry on the lead's words when only the echo overruns; or give a
  clean line a retry when it sits seconds off its cue and the transcript hears
  it on the cue, which fixes the line on `dev` too.
- **An echo on its cue can show over the next line's early first word.** The
  first pass can start a line's first word at the previous line's end, well
  before its own cue, and the end snap holds it to the second word. Where an
  added line now fills that time, both are lit at once. Can't Stop The Feeling
  3:29 and 3:34: `(I can't stop the feeling)` over "Got" and over "Wanna", each
  placed about 1.5 s before its cue (on `dev` as well) and held 1.9 and 2.3 s;
  overlaps of 1.34 and 1.44 s. 5 added-line pairs overlap by over 1 s in 47
  songs at that plan's GATE B (these two; the other three not read for
  cause). No old word moves for it. Not heard by Ken as of 2026-11-16. The
  candidate: the line after an added line starts no earlier than the echo's
  end, or is a doubted start for the onset snap; either moves an old line's
  first word and needs a replay.
- **A group after a dialogue dash or song star is dropped as unplaced.**
  `srt_cues._group_at` gives up on a group when the text before it has no
  letter, which also catches a mark the cleaner removes ("- (hey) go",
  "* (oh) go"), where the group's place is the line's start. A group glued to
  the word before it ("Hello(oh), there") is dropped the same way, and a glued
  label is misread: in "OK:(oh)go", "OK:" cut off at the group reads as a
  speaker label, so the group lands before it. The letter check is a second,
  looser copy of the cleaner's own rule. None of the library's 261 kept groups
  is unplaced, and a dropped group leaves its line as it is today. Fix: place
  the group from the cleaner's own output, not a check before it (stage 2
  review, findings 4 and 9).
- **The stage reads the sheet twice.** `srt_cues.sheet_parens` parses and
  cleans the sheet again after `cue_spans_from_srt` has, and works out again
  which cues are lines. Both use the same cleaning helpers, so their line ids
  agree today; a change to which cues count as lines in one and not the other
  would put inline groups into the wrong line with no error. Fix: one function
  that returns the lines, spans and groups from a single parse (stage 2
  review, finding 8).
- **The LRCLIB origin names are spelled twice.** `backing_vocals.ORIGINS` writes
  out `"lrclib_srt"` and, since `lrclib_fit_pick` (4d2), `"lrclib_auto_srt"`,
  because the align stage cannot import `library_regen`, where `LRC_ORIGIN` and
  `LRC_AUTO_ORIGIN` live with the other origin names; a test keeps them equal.
  Moving only these to `lrclib` would split the list, so the fix is a small
  module the stage can import that holds every origin name (stage 2 review,
  finding 11; the second name from the review of `2fd9c4f9~1..313384ea`).

## LRCLIB timing picked at download

- **A pick does not look at what is already in `lyrics/`.** The align stage
  moves the picked sheet in and writes the record's `.lrc` without checking for
  another sheet or for the admin's choice. A download over a song already in the
  library (same file name) would leave the auto sheet beside an older custom,
  movie or LRCLIB sheet, and the next regen replays the older one, which comes
  first in `SHEETS`; a skip marker or a hand-placed `.lrc`, which the joint fill
  treats as the admin's choice, is overwritten. Needs a re-download over a
  library song; not seen. Record: review of `2fd9c4f9~1..313384ea`, finding 5.
- **Song Info's download-check note can sit under an LRCLIB match the joint fill
  used.** The note goes by the download's check alone (`_download_check_note`): a
  Genius song whose check returned no pick, while the joint fill used the `.lrc`
  on disk, shows the match on its LRCLIB row and "Checked at download: no LRCLIB
  record passed the timing check." right under it. A wording question; not ruled.
  Record: review of `bac42182~1..0bde9554`, finding 7.
- **History names a version by its Genius identity before its origin.**
  `song_info._versions` tests `entry.genius` ahead of the custom, movie and
  caption origins (both LRCLIB origins now come first, `17c0a6bc`). A later origin
  whose bundle also keeps `lyrics.genius` would read "Genius · <artist>". Going by
  origin first changes what a custom version that keeps a Genius identity reads,
  so not done blind. Record: review of `bac42182~1..0bde9554`, finding 10.
- **A Processing job row never says "edited".** The row names its source from the
  origin in the job's `lyric_method` (`<origin>+<route>`), which doesn't say whether
  the run read an edited sheet, so a regen from `.lrclib-auto-edited.srt` reads
  "LRCLIB (auto)" where Song Info reads "LRCLIB (auto, edited)" (and an edited
  caption reads "YouTube captions"). Fix shape: the pipeline records the edit in the
  job's method or row, and the page qualifies it. Not ruled. Record: review of
  `dc17c08e~1..7b5eec48`, finding 2.
- **SexyBack's repeated lines come out early and overlapping in three places.** Ken
  listened (2026-11-18): at 1:25, 2:31 and 3:20 "all the lines are there, just overlapping
  and early", the same repeated lines each time; he ruled "ship and log". The bundle marks
  lines 19-25, 45-51 and 65, 69-71, 74-75 as re-paced (timed from their cue spans, not from
  heard words; 21 of its 79 lines are re-paced), and the line before each block ends 1.05-3.18 s
  after the block's first line starts. Not the pick order (a video-matching record's fit puts
  every line at the same clip time to within about a second) and not the aligner's `NoneType`
  failure (see "A failed re-align cannot be told from a refused one"): SexyBack's one failure
  was line 78. Why these blocks were re-paced instead of placed from the singing is not shown;
  same family as "A re-paced line can start before the previous line's end". Not ruled beyond
  shipping. Record: `plans/lrclib-fit-pick.md` on tag `archive/lrclib_fit_pick`, Results rows 21-24.
- **A line the record stamps late stays late (Who You Are, 1:49).** Ken (2026-11-18): "1:48
  late line, otherwise good". Line 21 ("'Cause everything inside me screams") is shown at
  109.6 s, the record's own stamp (01:49.54); the transcriber hears its first word at 106.1 s
  and its last at 109.7 s. The pick passes: the fit calls a line mistimed only past 5 s, and
  this is one line, under the shift run's limit of two. Cue align tried to aim the line from the
  heard words (`heard_aimed_line_ids` holds 21) and did not keep the move
  (`heard_aimed_kept_line_ids` is empty); why is not read. One of the song's two re-paced
  lines (21 and 38). Not ruled. Record: Results row 24.
- **Echo lines beside the lead overlap it on screen (Rolling in the Deep).** Ken
  (2026-11-18): the echoes overlap the main lines and are "more or less correct"; he asks
  whether the aligner handles overlapping lines badly. Its bundle: 45 backing groups, 32 kept,
  of those 20 by consistency alone (timed from where the same text was heard earlier), 9 heard
  and 3 vocable. An echo sung over the lead is mostly not among the transcriber's words, so its
  time is inferred, not heard; that is the likely reason, not measured. It is the keep rule as
  ruled (Decision 36 shows an automatic pick's backing vocals like a manual pick's), not new to
  the automatic pick. A pair that overlaps on screen is also listed under "Backing vocal lines"
  ("An echo on its cue can show over the next line's early first word"). Not ruled; no echo
  seen placed wrong. Record: Results row 24 and row 23's disk read.

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
- **Flag finished-karaoke lines that are shifted, for an eyeball and a repair.**
  Raised by Ken 2026-11-12 after the Decision 30 listen (record:
  `plans/lrclib-shift-check.md` Results row 9 on tag `archive/lrclib_fit_pick`): on
  three LRCLIB-timed songs, lines that "come in early but end on time" and one late
  stretch. Tried once, scratch only, on those three songs' bundles: the finished
  lines (`output_line_timings` + `lyrics.lines`, as an SRT) put through
  `srt_slice_fit.fit_slice` against the bundle's `transcribe_words`, then each
  line's `offsets` at the bar's 1.5 s. It caught three of the five spots Ken heard:
  Crazy 1:51 (+4.6 s early), Quit Playing Games 2:32 (+3.2 s) and the first two lines
  of its late stretch (rest unheard by whisper). It missed Reflection 3:11 (line unheard)
  and Quit Playing Games 0:52 (0.7 s). It also flags lines nobody listened to
  (7 / 2 / 4); the false-alarm rate is unknown. A long first `\k` word is no signal: nearly
  every line has one. Possible shape: computed at the end of each run, a Tools-tab
  list beside "poor" and the flagged lines with time and direction on Song Info. Open:
  no tool fixes one line's time today (Edit words keeps times, Repair swaps the whole
  source), so the flag needs a nudge tool or an automatic fix; `onset_loud_start`
  (landed 2026-11-16, tag `archive/onset_loud_start`) fixes the early-start kind
  where the transcriber hears the first word at the rise, once a song is regenerated. Cheap
  next step: run the check over the whole library (VM, read-only) and have Ken
  listen to a sample of flagged lines.
  `cue_heard_rescue` (record: `plans/cue-heard-rescue.md` on tag
  `archive/cue_heard_rescue`) sized the kinds on the library's 177 cue-route
  bundles, 2026-11-13. Most far-off whole lines have only their first word early
  and the rest of the line agrees with the transcriber (about 250 caption lines
  and 40 LRCLIB lines); that large group is `onset_loud_start`'s. Whole lines
  displaced as a whole number about 27. Rule D re-aligned them where heard, and
  by ear 3 of its 6 kept lines went onto the wrong audio, so it was left out.
  Of Ken's five spots, Quit Playing Games 1:57 and Crazy 1:51 are fixed (rules
  A1 and B); Quit Playing Games 0:52 and 2:32 and Reflection 3:11 are not. The
  flag itself is still unbuilt. Not ruled; ask the CLAUDE.md design questions
  before any plan.
- **Repair's LRCLIB list in the bar's order.** The list marks its `best` by the old
  text rule (`lrclib.select_candidate`, used in `LibraryTools.lrclib_candidates`), which
  Ken says lands on compilation records. `lrc_auto_pick.evaluate` already gives the
  order the download uses and each record's refusal, so the list could show the same
  first pick. Also: Repair's own check still uses the length gap the bar dropped
  (`LRC_MAX_GAP_S`), so a record the download picked can show there as needing an
  override. Not in the build (Decision 33). Raised 2026-11-12. Record:
  `plans/lrclib-fit-pick.md` on tag `archive/lrclib_fit_pick`, "How the open points were
  settled".
- **Prefer the record with fewer shifted lines in the pick order.** Raised by
  I'm A Slave 4 U at GATE Q of `plans/lrclib-shift-check.md`. Sized 2026-11-12 on the
  saved tables of both shift-check runs: it swaps 23 of 133 picks, and judged by the
  uploader captions it helps about as often as it hurts (of the 23: 5 better, 7 the
  same, 4 worse, 7 with no caption). The replacement records were not heard. Not
  done: Ken kept the measured order (Decision 32). Record: `plans/lrclib-fit-pick.md`
  on tag `archive/lrclib_fit_pick`, "Sizing for Decision 32".
