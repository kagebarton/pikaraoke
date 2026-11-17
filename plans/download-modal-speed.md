# Download modal: open at once, one YouTube lookup

Model: Claude Opus 5.5 writes the step-by-step spec for Claude Sonnet 5.5 from this brief
(brief by Claude Fable 5.2, 2026-11-11; decisions 7-15 on the dialog's layout added by Claude
Opus 5.5, 2026-11-17)

Branch `download_modal_speed`, rebased onto `dev` at `764df44` on 2026-11-17 (first cut from
`1016e20`), worktree
`.claude/worktrees/download_modal_speed` (inside the main checkout, gitignored via `.claude/`;
`models/` is symlinked in). Work and run everything from the worktree. If `dev` has moved,
rebase onto it before the first code commit.

This is a brief, not a spec: it fixes what Ken decided, what was measured, and what must hold.
The function shapes, the route shape, the exact wording of each (i) note and the commit split
are Opus's to write (see "For Opus to settle").

## Goal

Tapping Select on a search result opens the download modal. Today it shows a spinner while the
server runs two full yt-dlp lookups one after the other (the video link, then the caption), and
only then starts the Genius search. The download button appears after roughly 10 s, and nothing
on screen says what the wait is for. Guests get confused and tap away.

After this change the modal shows the video's thumbnail and details at once, says what it is
waiting for, and runs one yt-dlp lookup per open. The download button appears after the time of
one lookup.

The same change redesigns the dialog's lyric choice (decisions 7-15): Raw Transcription goes,
explanations move behind an (i), searching for other lyrics gets its own button, the list's
arrow is fixed on Android Chrome, and the button reads Queue.

## Decisions (Ken, 2026-11-11)

1. **Thumbnail first, video on tap.** The modal opens with the thumbnail, title, channel and
   length from the search card. The video plays only when the user taps Play. No autoplay.
2. **The lyric picker is held until the caption check answers.** Manual YouTube captions are the
   preferred lyric source, so the user must not be able to pick Genius before captions are
   offered. The Genius search runs at the same moment as the caption check, hidden, so its list
   shows at once when the caption is absent, too sparse, or could not be checked.
3. **The video link is folded into the caption lookup.** One yt-dlp call per modal open returns
   the caption, the video's length and a link the browser can play. There is no second lookup,
   on open or on Play.
4. **What counts as fixed.** Ken named two confusions: nothing happens for a while, and there is
   no download button yet. He also named the video sometimes not playing, which `6a6dfd2` was
   meant to fix; it measured as working on 2026-11-11 (Measurements, link check).
5. **Durable solutions only.** No code that needs editing whenever YouTube changes; package
   updates are fine. The one hand-picked setting that exists today (the client asked for a
   browser-playable link, `6a6dfd2`) may stay, as long as its breaking costs only the Play
   button.
6. **Still in force:** no caption lookup at search time, not even in the background
   (`plans/search-official-captions.md` on branch `search_official_captions`, decision 3).

Stated to Ken as assumptions and not objected to:

- yt-dlp stays a separate process per lookup. Loading it into the server saves about 0.7 s, but
  the app upgrades yt-dlp while running (`app.py:211`, `routes/admin.py:58`) and a loaded copy
  would stay old until a restart.
- A wait of about one lookup, with a line saying what it is for, counts as fixed for "no
  download button yet". A button present from the first instant would have the server choose
  the lyric source for the user; that is a different feature.
- Nothing is remembered between opens. Reopening the same card runs the lookup again.

## Decisions (Ken, 2026-11-17): the dialog's layout

Mockup (private to Ken), approved 2026-11-17: https://claude.ai/artifact/Bx2pwN8RgLPcFjN4hawcSQ.
Top row: the dialog today (four phone screens). Bottom row: after, six screens (waiting; caption
passed; caption too sparse with the Genius list; search box opened; nothing found; the list
opened). Three blank artboards on the canvas are strays. Where these decisions and the mockup
differ, the decisions win.

7. **Raw Transcription leaves the download dialog.** It is not good enough for karaoke and no
   guest should pick it. Song Repair ("No lyrics (transcribe)"), the pick pass's Transcribe
   button and library runs keep it, so the pipeline's `mode: raw` stays.
8. **No lyrics, no queueing from the dialog.** A video with no passing caption and no Genius
   hit, even after a search for other lyrics, cannot be sent from the dialog: the Queue button
   stays disabled, the search box opens by itself, and the (i) says why (search by title and
   artist, or pick another video). No pasted-lyrics fallback.
9. **Breathing text, not a spinner, for every wait.** A large line below the thumbnail fades in
   and out and says what the wait is for: "Checking YouTube for captions…" while the lookup
   runs, then "Searching Genius for lyrics…" only if Genius has not answered when the lookup
   does (and while a search for other lyrics runs). It sits where the Queue button will
   appear, not over the thumbnail, so Play stays usable.
10. **Explanations move behind an (i)** beside the "Lyrics" label: today's "YouTube captions
    will be used for lyrics.", the three `CAPTION_NOTES`, "Genius.com lyrics search results:"
    and "No lyrics results found…". The (i)'s note says why this source is offered: the caption
    passed, it was too sparse, it could not be checked, a Genius match, or nothing found. The
    icon sits about 4 px from its label; its full tap area stays, overlapping the label's end.
11. **The caption-passed screen stays separate and the least cluttered:** "Lyrics: YouTube
    captions" with its (i), at the same size as the "Lyrics" label on the other screens; the
    Queue button; an "Other lyrics…" link (was "More options"). No search button on it.
12. **Every other outcome uses one layout:** "Lyrics" (i), the list, a "Search for other
    lyrics…" button, then Queue. "Other lyrics…" opens this layout too. The search button swaps
    in a search box in its place: the label "Type the song title and artist", the input and a
    Search button.
13. **The list holds only lyrics:** a "YouTube" group with "YouTube captions (recommended)",
    present only when the caption passed (so only after "Other lyrics…"), then the "Genius.com"
    group. The "Other Options" group (Custom Search, Raw Transcription) goes. "Choose the
    lyrics" stays as the disabled first line when no hit is safe to preselect.
14. **The list is full size and its arrow is drawn in CSS.** Today it is `is-small` and its
    arrow is the `⌄` character scaled six times and nudged by a fixed offset; how large it is
    and where it lands depend on the phone's font, so it lands wrong on Android Chrome.
15. **The dialog's button reads "Queue"** while "Add to queue after download" is ticked: queue
    hold puts the song in the queue the moment it is tapped. Unticked, it reads "Add to
    library". After a tap: "Queued" or "Added", then the fade-out as today. The card's button
    that opens the dialog reads "Queue…" (`search_official_captions` decision 13, amended
    2026-11-17 in `edd5fa3` on that branch).

Stated to Ken as assumptions and not objected to (2026-11-17):

- The direct-URL download in Advanced stays as it is: it sends no lyric choice, so a video
  with no caption is still transcribed there.
- The card reads "Queue…" even when "Add to queue after download" is unticked; the dialog then
  says "Add to library". The box is an admin setting and rarely unticked.

## What exists (checked 2026-11-11; line numbers rechecked 2026-11-17 on `764df44`)

- `pikaraoke/lib/youtube_dl.py:263` `get_preview_info(video_url)`: the video-link lookup. Asks
  for format 18 with `--extractor-args youtube:player_client=tv_simply,default`, prints the
  link, the subtitles map and the duration, 15 s timeout. Only caller: the `/preview` route.
- `pikaraoke/lib/youtube_dl.py:365` `download_manual_en_subs(video_url, dest_dir, stem)`: the
  caption lookup. Writes `<stem>.en.srt` (manual English only, converted to SRT), 60 s timeout,
  raises `CaptionDownloadFailed` when yt-dlp could not
  answer. Also used by the library tools (`library_regen.py:554`, `fetch_caption`), so it stays.
- `pikaraoke/lib/library_regen.py:610` `_check_caption`: downloads the caption into a scratch
  folder under `get_temp_directory()`, measures it with `_wpm` (line 500) and `_caption_passes`
  (line 512), returns `CaptionCheck(found, wpm, passed, failed)`. Two entry points:
  `check_caption(job)` (line 591, library tools) and `check_video_caption(video_id, duration_s)`
  (line 602, whose only caller is the search route).
- `pikaraoke/routes/search.py`: `/preview` (line 184) returns the stream link, whether a manual
  English caption exists, and the duration. `/caption_check` (line 194) takes `yt_id` and
  `duration` and returns `found`, `passed` and `failed`.
- `pikaraoke/templates/search.html`: the flow is described in the comment at lines 659-674.
  `openPreviewModal` (line 963) calls `/preview`, then `checkCaption` (line 791) calls
  `/caption_check`, then `searchLyricsForActiveVideo` (line 781) calls `/lyrics_search`. Modal
  markup is at lines 1191-1231. Lines 976-979 play the empty `<video>` inside the click so iOS
  Safari allows a later `.play()` from an AJAX callback.
- `search.html`, the parts decisions 7-15 change:
  - CSS: the video spinner (lines 166-184); the list's arrow, Bulma's own hidden and a `⌄`
    drawn at `font-size: 6em` with `translateY(-75%)` (lines 232-244).
  - `CAPTION_NOTES` (line 680); `resetLyricsSection` (line 690) resets the button text to
    "Download" (line 707).
  - `populateLyricsDropdown` (line 719): the "Genius.com Results" group, then "Other Options"
    (lines 742-748) with "Custom Search...", "YouTube Captions" (only when the caption passed)
    and "Raw Transcription", each with an emoji in front.
  - The list's change handler (line 832) opens the custom search box on `__custom__`;
    `doCustomLyricsSearch` (line 849); the "More options" handler (line 866).
  - `#lyrics-srt-btn` handler (line 873) and `#lyrics-download-btn` handler (line 890, its
    `__raw__`/`__srt__` branch at line 894) post `/lyrics_select`, set "Added for
    processing..." (lines 883, 903, 931) and call `postDownload`, which reads
    `#add-to-queue-search` (line 584).
  - Markup: "Searching lyrics..." (line 1201), the caption note and its "Download" button
    (lines 1203-1206), "More options" (line 1208), "Genius.com lyrics search results:" (line
    1211), "No lyrics results found. Use custom search below..." (line 1212), the list's
    wrapper `select is-fullwidth is-small` (line 1213), the custom search box (line 1216), the
    list's "Download" button (line 1227).
- `pikaraoke/routes/search.py:261` `/lyrics_select` accepts `genius_id`, or `mode` `raw` or
  `srt` (line 297). Its only callers are the three posts in `search.html` (lines 877, 897,
  925), so after decision 7 nothing sends `raw`. The library tools write their transcribe
  choice straight to the choice file (`library_tools.py:1244`, through `write_choice`), so the
  pipeline's `raw` branch (`pipeline/stages/lyrics_fetch.py:105`) is still reached.
- The (i): `templates/info_tip.html` (the `info_tip` macro), styled by
  `static/library-pages.css` (lines 1-16) and opened and placed by `static/library-pages.js`.
  Only the library pages load those two files (`library_run.html`, `pick_pass.html`,
  `playlist.html`, `processing.html` and others); `search.html` does not.
- Queue hold: `pikaraoke/lib/queue_hold.py`. A download sent with `queue: true` holds its
  queue slot from the moment it is sent, until it can play.
- `pikaraoke/templates/search_result.html`: each card already carries the thumbnail
  (`https://img.youtube.com/vi/<id>/mqdefault.jpg`), the title, the channel and the duration
  badge. The `<li>` has `data-ytid`, `data-yttitle`, `data-ytchannel` and `value` (the URL);
  the duration is only in the badge's markup. The button that opens the dialog reads "Select"
  (line 21) until `search_official_captions` commit 8.
- Tests: `tests/unit/test_youtube_dl.py`, `tests/unit/test_search_routes.py`,
  `tests/unit/test_library_regen.py`.

## The change

**Server.** One function runs the single lookup and returns the caption file (or none), the
video's length and the link (or none). The modal's caption check is built on it and reuses
`_wpm` and `_caption_passes`, so the modal's answer and the after-download gate stay one rule.
The modal's route returns the caption answer plus the link. `/preview`, `get_preview_info`,
`PreviewQuery` and their tests are deleted.

The combined call was tried by hand (Measurements, combined lookup):

```
python -m yt_dlp --skip-download --no-simulate \
  --write-subs --sub-langs "en.*" --convert-subs srt -o "<scratch>/<stem>.%(ext)s" \
  -f "18/worst[ext=mp4][protocol*=http]/worst[protocol*=http]" --ignore-no-formats-error \
  --print url --print duration \
  --extractor-args "youtube:player_client=tv_simply,default" \
  --impersonate chrome <watch url>
```

`--print` alone implies `--simulate`, which writes no caption file; `--no-simulate` restores the
write. `--ignore-no-formats-error` keeps a video with no matching format from failing the
caption answer. The real command is built from the existing helpers (`yt_dlp_cmd`,
`_js_runtime_args`, `_impersonate_args`), as the two calls it replaces are.

**Modal.**

- On open, with no network wait: the card's thumbnail with a Play button over it, the title,
  the channel and the length, and the breathing line "Checking YouTube for captions…"
  (decision 9).
- On open, two requests start together: the combined lookup, and the Genius search (one
  `/lyrics_search` call with the video's title and channel and the page's search term, as
  `searchLyricsForActiveVideo` sends today; the server works out what to ask). The Genius answer is
  held, not shown.
- When the lookup answers: a caption that passes shows the caption-passed screen (decision 11).
  Otherwise the held Genius list shows at once in the list layout (decision 12), with the
  reason (sparse, could not check, none) in its (i). If Genius has not answered yet, the
  breathing line says "Searching Genius for lyrics…".
- "Other lyrics…" on the caption-passed screen shows the held Genius list without searching
  again, with YouTube captions kept in the list (decision 13).
- Play: with the link in hand, the video replaces the thumbnail and plays. Tapped before the
  lookup has answered, the thumbnail shows a spinner and the video starts when the link
  arrives. With no link, or when the video element reports an error, the modal says the preview
  is unavailable; the caption answer and the download are unaffected.
- The sidecar choice written by `/lyrics_select` and the fade-out stay as they are; the
  button's labels follow decision 15.
- The rest of the layout: decisions 7-14 and the mockup.

## Constraints

- Exactly one yt-dlp process per modal open, and none on Play.
- The caption answer must not depend on the link. A missing or unplayable link, an unknown
  client name in the setting, or no matching format leaves `found`/`passed`/`failed` correct.
- The client setting lives in one place with its reason (the comment from `6a6dfd2`).
- `download_manual_en_subs` keeps its behaviour for the library tools; do not grow a third copy
  of the subtitle options (`build_ytdl_download_command` and `download_manual_en_subs` are the
  first two).
- Scratch files go under `get_temp_directory()` and are removed in a `finally`, as
  `_check_caption` does.
- The stale-answer guards stay: an answer for a modal that has closed, or for another video, is
  dropped (`stillShowing`, `search.html:798`).
- `/lyrics_select` stops accepting `mode: raw` (no caller is left after decision 7), and its
  `raw` test goes with it. The pipeline's `raw` branch and the library tools' transcribe
  choice stay.
- The button's label (Queue or Add to library) reads the same checkbox `postDownload` sends,
  so what the button says and what happens cannot disagree.
- The (i) is the existing `info_tip` macro with its own script and styles, not a second copy.
- New user-facing strings go through `_()` / `{% trans %}`.
- iOS Safari only allows `.play()` tied to a tap. A Play tap that arrives before the link must
  keep that permission (the trick at `search.html:976-979` belongs with the Play tap now, not
  with opening the modal).

## Measurements (2026-11-11, this box, yt-dlp 2026.10.26, curl_cffi 0.14.0, deno)

Today's two calls, each a separate process:

| call                      | video       | time   |
| ------------------------- | ----------- | ------ |
| `get_preview_info` command | dQw4w9WgXcQ | 4.50 s |
| `download_manual_en_subs` command | dQw4w9WgXcQ | 4.78 s |
| `get_preview_info` command | fJ9rUzIMcZQ | 4.27 s |
| `download_manual_en_subs` command | fJ9rUzIMcZQ | 3.98 s |

Combined lookup (the command above), one process:

| client setting              | video       | time   | exit | caption file | link in a browser-style GET |
| --------------------------- | ----------- | ------ | ---- | ------------ | --------------------------- |
| `tv_simply,default`         | dQw4w9WgXcQ | 4.52 s | 0    | `x.en.srt`   | 206                         |
| `tv_simply,default`         | fJ9rUzIMcZQ | 5.21 s | 0    | `x.en.srt`   | 206                         |
| `no_such_client,default`    | dQw4w9WgXcQ | 5.39 s | 0    | `x.en.srt`   | 403                         |

The third row printed `WARNING: [youtube] Skipping unsupported client "no_such_client"` and
otherwise ran as normal.

Link check (three ranged GETs each, Android Chrome user agent, no other headers):

| client setting      | client in the link | results       |
| ------------------- | ------------------ | ------------- |
| `tv_simply,default` | `TVHTML5_SIMPLY`   | 206, 206, 206 |
| yt-dlp defaults     | `TVHTML5`          | 403, 403, 403 |

yt-dlp loaded in-process (`YoutubeDL.extract_info`, then the caption fetched from the URL in the
subtitles map), one instance reused across four lookups:

| video                | extract | caption fetch |
| -------------------- | ------- | ------------- |
| dQw4w9WgXcQ          | 3.67 s  | 0.11 s        |
| fJ9rUzIMcZQ          | 3.26 s  | 0.12 s        |
| kJQP7kiw5Fk          | 3.44 s  | 0.11 s        |
| dQw4w9WgXcQ (repeat) | 3.25 s  | 0.11 s        |

Process start: `python -m yt_dlp --version` 0.26 s.

Where one lookup's time goes (`-v`, video 9bZkp7q19f0, seconds from process start):

| at     | step                                   |
| ------ | -------------------------------------- |
| 0.46   | start of extraction                    |
| 1.37   | watch page downloaded                  |
| 2.02   | three player API answers downloaded    |
| 2.30   | player JS downloaded                   |
| 3.41   | deno finished the JS challenge         |
| 3.83   | m3u8 information downloaded            |
| 3.88   | link printed                           |

Re-check (2026-11-17, `dev` at `764df44`, same yt-dlp 2026.10.26 and curl_cffi 0.14.0, deno
2.7.7): the combined lookup above, one process each; link tested with one ranged GET, Android
Chrome user agent.

| video       | time   | exit | caption file | duration | link | format, client in the link |
| ----------- | ------ | ---- | ------------ | -------- | ---- | -------------------------- |
| dQw4w9WgXcQ | 6.03 s | 0    | `x.en.srt`   | 213      | 206  | 18 (mp4 360p), `TVHTML5_SIMPLY` |
| fJ9rUzIMcZQ | 5.43 s | 0    | `x.en.srt`   | 359      | 206  | not recorded               |

New since 2026-11-11, on both: `WARNING: [youtube] <id>: tv_simply client https formats require
a GVS PO Token which was not provided. They will be skipped as they may yield HTTP Error 403.`
Format 18 still came from `tv_simply` and played; the warning is about that client's other
formats. Between 2026-11-11 and this re-check, `youtube_dl.py` and the `/preview` and
`/caption_check` routes did not change.

## For Opus to settle

- The shape and home of the combined lookup, and how `_check_caption` shares it with
  `check_video_caption` without changing `check_caption(job)` for the library tools.
- The combined call's timeout. Today the link call gives up at 15 s and the caption call at
  60 s; the modal now waits on one number.
- The route: extend `/caption_check` or rename it. Its `duration` parameter is no longer needed,
  since the lookup returns the length.
- The exact (i) note for each state, starting from the mockup's. The waiting lines and the
  home of today's `CAPTION_NOTES` are settled by decisions 9 and 10.
- How `search.html` gets the (i): load `library-pages.css` and `library-pages.js` there, or move
  the (i)'s parts into files of their own that both load. One copy either way.
- What "Other lyrics…" preselects. The mockup's screen 6 shows the Genius preselect, with
  YouTube captions above it.
- What a search for other lyrics that finds nothing shows; the mockup's screen 5 covers only
  the video's own title finding nothing.
- Whether the breathing line holds still under `prefers-reduced-motion`.
- Where the modal reads the length from: the channel is now a data attribute on the `<li>`
  (`data-ytchannel`), the length is still only the badge's text.
- Whether closing the modal stops the running lookup. Today it does not; the process runs to
  its timeout and its answer is dropped.
- `plans/open-issues.md`, "Search results": "A restored search page can show a stuck card"
  mentions the modal's saved contents. Say whether the reorder makes it a few-line fix; if not,
  leave it.
- The commit split. Three look natural: the single lookup with its route and tests; the
  modal's open, wait and Play (decisions 1-3 and 9); the lyric layout (decisions 7, 8 and
  10-15).

## Out of scope

- Any lookup when search results load (decision 6).
- YouTube's embedded player, and relaying the video through the server. Both were offered to
  Ken as alternatives to decision 1 and not chosen.
- yt-dlp loaded into the server process.
- Remembering a lookup between opens.
- A download button that is usable before the caption check answers.
- yt-dlp options that skip parts of the lookup (`player_skip`, `skip`). They are the kind of
  setting decision 5 rules out.
- Transcription on Song Repair, the pick pass and library runs (decision 7).
- Pasted lyrics in the dialog (decision 8).
- The direct-URL download in Advanced, which still sends no lyric choice.
- The card's button: its rename is `search_official_captions` commit 8, and it does not follow
  the "Add to queue after download" box.

## Done when

- The modal shows the thumbnail, title, channel, length and the breathing line with no network
  wait.
- A unit test with the subprocess mocked shows one yt-dlp call for a modal open, returning the
  caption answer and the link together; no route remains that fetches a link on its own.
- A lookup whose link is missing still answers the caption correctly (unit test), and by hand:
  with the client setting pointed at a name yt-dlp does not have, captions and download work
  and Play says the preview is unavailable.
- On a video with a good manual caption, the caption-passed screen appears after one lookup. On
  a video without one, the Genius list appears as soon as the lookup answers, with no second
  wait.
- The dialog offers no Raw Transcription and no "Other Options" group; `/lyrics_select` turns
  away `mode: raw` (unit test).
- With no caption and no Genius hit, Queue stays disabled and the search box is open.
- The button reads "Queue" with "Add to queue after download" ticked and "Add to library" with
  it unticked, and the download is sent with the matching `queue` value.
- Ken's check on a phone: each screen matches the mockup, and the list's arrow sits right on
  Android Chrome.
- Ken's live check on an iPhone (Safari) and an Android phone (Chrome): Play works when tapped
  before the lookup answers and when tapped after.

## Overlap with `search_official_captions`

That branch's Part 1 (commits 1-4, done 2026-11-17, not landed) edits the search command at
`youtube_dl.py:249`, the `/search` and `/search/more` routes, and `official_rank.py`. This one
edits the preview and caption functions further down `youtube_dl.py`, the `/preview`,
`/caption_check` and `/lyrics_select` routes, and the modal half of `search.html`. No function
is touched by both.

Its Part 2 (commits 5-8, not started) edits the search half of `search.html`: the library box,
the search box, and one "Add to queue after download" box `#add-to-queue` in place of
`#add-to-queue-search` and `#add-to-queue-direct` (commit 7). This branch's button label reads
the same box `postDownload` sends (Constraints), and commit 7 repoints `postDownload`, so
whichever lands second points the label at the surviving box. Its commit 8 renames the card's
button to "Queue…" in `search_result.html`. Whichever lands second rebases.

## Results log

(empty)
