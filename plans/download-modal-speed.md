# Download modal: open at once, one YouTube lookup

Model: Claude Sonnet 5.5 executes the Spec section, commit by commit (spec by Claude Opus 5.5,
2026-11-17; brief by Claude Fable 5.2, 2026-11-11; decisions 7-15 on the dialog's layout added
by Claude Opus 5.5, 2026-11-17)

Branch `download_modal_speed`, rebased onto `dev` at `764df44` on 2026-11-17 (first cut from
`1016e20`), worktree
`.claude/worktrees/download_modal_speed` (inside the main checkout, gitignored via `.claude/`;
`models/` is symlinked in). Work and run everything from the worktree. If `dev` has moved,
rebase onto it before the first code commit.

Goal through "Overlap" is the brief: what Ken decided, what was measured, and what must hold.
"Spec" is how, settled by Opus: Sonnet follows it, and where it is more specific than the brief,
it wins.

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

Settled in "Spec", O1-O13.

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

## Spec (Claude Opus 5.5, 2026-11-17)

Line numbers are `764df44`'s. `dev` has not moved since, and the branch has no code of its own.

### Settled by Opus

O1-O13 answer the "For Opus to settle" items. O14-O17 are readings of the brief; Ken can
overrule any of them.

- **O1. The combined lookup.**
  - `youtube_dl.py`: a module constant
    `_MANUAL_EN_SUB_ARGS = ["--write-subs", "--sub-langs", "en.*", "--convert-subs", "srt"]`,
    with a one-line comment: the video download and every caption fetch share it, so a fetched
    caption is what a download would save. `build_ytdl_download_command`,
    `download_manual_en_subs` and the new lookup all use it: one copy, not three.
  - `_run_caption_command(video_url, dest_dir, stem, extra_args, timeout) -> bytes`: makes
    `dest_dir`, runs `yt_dlp_cmd + ["--skip-download", *extra_args, *_MANUAL_EN_SUB_ARGS, "-o",
    <dest_dir>/<stem>.%(ext)s] + _js_runtime_args() + _impersonate_args() + [video_url]` and
    returns its stdout. It raises `CaptionDownloadFailed` on a timeout, a yt-dlp that can't run,
    or a non-zero exit, with today's messages. `download_manual_en_subs` becomes this call with no
    extra args and its 60 s, then `_select_en_srt`; its behaviour and tests do not change.
  - `@dataclass(frozen=True) class VideoLookup` with `srt_path: str | None`,
    `duration_s: float | None` and `stream_url: str | None`, one comment per field.
  - `lookup_video(video_url, dest_dir, stem) -> VideoLookup`: `_run_caption_command` with
    `--no-simulate`, `-f 18/worst[ext=mp4][protocol*=http]/worst[protocol*=http]`,
    `--ignore-no-formats-error`, `--print url`, `--print duration` and the client setting
    (`youtube:player_client=tv_simply,default`), whose comment from `6a6dfd2` moves over word
    for word. Timeout: O2. Of stdout's non-empty lines, the first is the link when it starts
    with `http` (yt-dlp prints `NA` when no format matched); the second is the length when it
    parses as a float (`NA` for a live stream). `srt_path` comes from `_select_en_srt`. The
    docstring says why `--no-simulate` (`--print` alone writes no caption) and why
    `--ignore-no-formats-error` (a video with no playable format still answers the caption).
  - Delete `get_preview_info`.
  - `library_regen.py`: `_check_caption` splits in two. `_caption_scratch()` is a context
    manager: `tempfile.mkdtemp(prefix="caption_check_", dir=get_temp_directory())`, removed in a
    `finally`. `_measure_caption(srt_path, duration, name) -> CaptionCheck` is "not found" when
    `srt_path` is None, else `_wpm` and `_caption_passes`. `check_caption(job)` keeps its
    signature, its `download_manual_en_subs` call and its lazy length read (`media_duration` is
    read only for a readable caption), so the library tools see no change.
    `check_video_caption(video_id) -> tuple[CaptionCheck, str | None]` runs
    `lookup_video(watch_url(video_id), <scratch>, video_id)` and measures against
    `duration_s`. A failed lookup is `CaptionCheck(found=False, wpm=None, passed=False,
    failed=True)` with no link. Both keep today's warning when a check can't run.
  - `CaptionCheck` gains no field: `library_tools` serialises it (`asdict`,
    `library_tools.py:1542`), so a link field would leak into the run status.
- **O2. Timeout: 30 s**, inline, with a one-line reason: one lookup measured 4-6 s; 30 s
  outlasts a slow day without leaving a guest a minute (the caption call's 60 s) before the
  Genius list. A timeout reads as "could not check" in the dialog, as today.
- **O3. The route keeps its name.** `/caption_check?yt_id=<id>` answers
  `{found, passed, failed, stream_url}`, `stream_url` null when there is none; `duration`
  goes. The caption answer is what the dialog waits on (decision 2) and the link rides along,
  so the name still says what the route is for; its `url_for` and its tests stay put. `/preview`
  and `PreviewQuery` are deleted.
- **O4. The (i) notes**, from the mockup's. Each is one `.info-tip-line` in the markup, through
  `{% trans %}`, with a `data-note` key. The script shows the lines that apply and hides the
  rest (`is-hidden`), so no note text is built in the script.

  | key          | shown when                                  | text |
  | ------------ | ------------------------------------------- | ---- |
  | `passed`     | the caption passed                          | This video has its own lyric captions, written for it rather than made by YouTube's speech recognition. They usually give the best timing. |
  | `sparse`     | the caption is too sparse                   | This video's captions are too sparse to be lyrics. |
  | `failed`     | the lookup could not answer                 | Could not check this video's captions. |
  | `none`       | no manual English caption                   | This video has no captions of its own. |
  | `title-hits` | the list holds the title search's hits      | These are Genius lyrics found from the video's title. Wrong song? Pick another, or search for other lyrics. |
  | `title-none` | the title search found nothing              | Genius found nothing for the video's title. |
  | `typed-hits` | the list holds a typed search's hits        | These are Genius lyrics found for what you typed. Pick the one that matches this video. |
  | `empty`      | the list offers nothing                     | A song needs lyrics to become karaoke: search by title and artist, or pick another video. |

  The captions screen's (i) holds `passed` only. The list layout's (i) shows one caption line
  (`passed`, `sparse`, `failed` or `none`), then one Genius line (`title-hits`, `title-none` or
  `typed-hits`), then `empty` only when the list offers nothing. Mockup screen 5's one sentence
  becomes `none`, `title-none` and `empty`.
- **O5. The (i) on the search page:** `search.html` loads `library-pages.css` and
  `library-pages.js` and imports `info_tip`. Both files are already shared, every rule in them
  is scoped by class, and the SPA loads each file once (`spa-navigation.js`,
  `loadedResources`). Moving the (i) into files of its own would touch seven library templates
  for no change in behaviour. The two files' header comments name the search page's dialog. The
  hit label reuses `libraryPages.byline`.
- **O6. What gets selected.** Every fill of the list selects the server's preselect, else
  "Choose the lyrics" (decision 13). For "Other lyrics…" that is the Genius preselect (mockup
  screen 6), or "Choose the lyrics" with YouTube captions one tap away. The server preselects
  nothing for typed text, so a typed search always opens on "Choose the lyrics": Queue cannot
  stay on lyrics the guest searched to replace.
- **O7. A typed search that finds nothing** leaves the list and its selection as they were,
  keeps the box open with the text, and shows "Nothing found for that search." under the box
  until the next search. Replacing the list would drop YouTube captions, and decision 8 lets a
  passing caption always be queued. An error answer reads the same, as today: `/lyrics_search`
  answers 200 with no hits when Genius is down.
- **O8. Reduced motion:** under `prefers-reduced-motion: reduce` the breathing line holds still
  at full opacity, and a waiting Play button (O14) holds at half opacity.
- **O9. The length** comes from a new `data-ytDuration="{{result.duration}}"` on the card's
  `<li>`, beside `data-ytChannel`. The line under the title reads "channel · length", or
  whichever exists, or is hidden when neither does (a card restored from a copy saved before
  this change has no length).
- **O10. Closing does not stop the lookup.** Aborting the request would not stop yt-dlp: the
  server's request thread runs it to the end. Stopping it needs a record of processes per
  request and a cancel route, to save about 5 s of one process. The dialog drops the late
  answer (O12).
- **O11. The open issue "A restored search page can show a stuck card":** the dialog's half is
  fixed here; the card's half is not.
  - The dialog moves out of `#container_search_result`, the element Show more's save copies,
    to just after it and outside `{% if search_rows %}`, so a saved copy never holds the
    dialog and a restored page still has one. A copy saved before this change holds its own
    old dialog, with the same ids; the restore drops it before inserting the copy (one line
    and a comment), so a phone tab restored after the update opens the new dialog.
  - Every open rebuilds every part of the dialog (commit 2). Today's reset misses the list's
    Download button, whose green success state carries into the next open.
  - The card's half (an in-library button saved mid-flash) is not touched here, and
    `search_official_captions` Part 2 rewrites that button. Reword the entry at landing.
- **O12. Stale answers: one open number.** `stillShowing` (open, same video) lets an answer
  from an earlier open of the same card through, and it can refill a list the guest is using.
  Every open and every close bumps one counter; every answer (lookup, title search, typed
  search) carries the number it was asked under and is dropped when that no longer matches.
  Typed searches also keep latest-wins among themselves. This replaces `stillShowing` and
  `_lyricsSeq`; the constraint they serve stays.
- **O13. Three commits,** the brief's split, each leaving the page working: commit 1 keeps
  today's dialog on the new route.
- **O14. No spinner on Play** (reading). The brief's "the thumbnail shows a spinner" predates
  decision 9 ("not a spinner, for every wait"), and the brief lists the video spinner among
  what decisions 7-15 change. Tapped before the link, the Play button breathes with decision
  9's animation, and the video starts when the link arrives. The thumbnail stays over the video
  until it plays (`playing`), so the box never goes black while it buffers. The spinner
  overlay and its CSS go.
- **O15. No link, no Play** (reading). When the answer has no link, the Play button gives way
  to "Preview unavailable" at once, rather than waiting for a tap on a button that cannot work.
  A video that reports an error after Play shows the same, over the thumbnail.
- **O16. One Queue path** (reading). Captions and Genius alike: post `/lyrics_select`, then on
  success `/download`. Today the captions path sends both at once, so a download could start
  before its choice is written. The video's id, link and title are taken at the tap, not read
  from the dialog's state when the answer arrives.
- **O17. A consequence of decision 8, recorded.** With Genius down or no Genius token set, a
  video without a passing caption cannot be queued from the dialog. The direct URL in Advanced
  still downloads it.

### Before the first commit

1. In the worktree: clean status on `download_modal_speed`, HEAD the commit that added this
   spec. Fetch; if `dev` has moved past `764df44`, rebase onto it and recheck the line numbers
   you rely on.
2. Run the unit suite once untouched and note any failures, so failures older than the branch
   are named in the Results log, not fixed.
3. Read Part 2 of `search_official_captions`' plan:
   `git show edd5fa3:plans/search-official-captions.md`, from "## Part 2".

### Each commit

- Pre-commit on the changed files; the unit suite
  (`/home/ken/miniconda3/envs/pik/bin/python -m pytest tests/unit`), no failure the baseline
  lacks; an import smoke of the changed modules (`pikaraoke.lib.youtube_dl`,
  `pikaraoke.lib.library_regen`, `pikaraoke.routes.search`); `test_search_render.py` renders
  `search.html`, so it covers the template.
- Read `git diff --cached` against the commit's list below, then CLAUDE.md's self-review.
  `graphify update .` only if `graphify-out/graph.json` exists.
- The commit's Results row goes in a plan-only commit of its own.

### Commit 1: `feat(search): one yt-dlp lookup answers the dialog's caption check and its preview link`

Decision 3; O1, O2, O3. Files: `pikaraoke/lib/youtube_dl.py`, `pikaraoke/lib/library_regen.py`,
`pikaraoke/routes/search.py`, `pikaraoke/templates/search.html`,
`tests/unit/test_youtube_dl.py`, `tests/unit/test_library_regen.py`,
`tests/unit/test_search_routes.py`.

1. The server: O1, O2, O3.
2. `search.html`, the least that keeps today's dialog working: `openPreviewModal` makes one
   request, `/caption_check?yt_id=`, in place of `/preview` then `checkCaption`. A link in the
   answer starts the video as today; then the caption answer branches as `checkCaption`'s
   success and error handlers do now. Fold `checkCaption` into it and keep the rest, spinner and
   autoplay included: commit 2 rewrites the open.
3. Tests.
   - `test_youtube_dl.py`: `TestLookupVideo` replaces `TestGetPreviewInfo`, with
     `subprocess.run` mocked and `_default_patches`:
     - one `subprocess.run` call, whose command carries `--skip-download`, `--no-simulate`,
       `--ignore-no-formats-error`, the format, `--print url`, `--print duration`,
       `-o <dest>/<stem>.%(ext)s`, the client setting (keep the old test's comment on why) and
       the URL last;
     - a link, a length and a written `<stem>.en.srt` come back together;
     - `NA` for the link with a caption written: `stream_url` None, the caption still found;
     - no caption written: `srt_path` None, the link kept;
     - `NA` for the length: `duration_s` None;
     - an error exit, a timeout and a missing yt-dlp each raise `CaptionDownloadFailed`
       (parametrized as in `TestDownloadManualEnSubs`);
     - the commands of `build_ytdl_download_command`, `download_manual_en_subs` and
       `lookup_video` each carry `_MANUAL_EN_SUB_ARGS` as one unbroken run.
   - `test_library_regen.py`: `TestCheckVideoCaption` fakes `lr.lookup_video` in place of
     `download_manual_en_subs`. Its three tests stay, unpacking `(check, link)`. New: the link
     comes back with the answer; a lookup with no link answers the caption the same; a failed
     lookup answers `failed=True` with no link. The fixture's empty-scratch assert stays.
     `TestCheckCaption` must pass unchanged.
   - `test_search_routes.py`: `TestCaptionCheck` mocks `check_video_caption` returning
     `(CaptionCheck, link)`: it is called with the id alone; the answer has the four keys,
     `stream_url` null when there is no link; an invalid id answers 400 as now. Delete
     `test_preview_returns_the_video_length`; `/preview` answers 404. One test through the route
     with only `subprocess.run` mocked (plus `library_regen.get_temp_directory` pointed at
     `tmp_path` and `_default_patches`; the fake run writes a 60-word caption where `-o` says):
     `GET /caption_check?yt_id=dQw4w9WgXcQ` makes exactly one yt-dlp call and answers passed with
     the link. Update the module docstring.
4. Measure before committing, on the VM against real YouTube (scripts in the scratchpad, not
   committed). For at least five videos (the two in Measurements, at least one with no manual
   English caption, the rest your pick), run `download_manual_en_subs` and `lookup_video` into
   folders under `get_temp_directory()`, and record per video: found by each, each caption's
   word count, the lookup's time, and the link's status from one ranged GET with an Android
   Chrome user agent. Add one row for a captioned video with the client setting changed to
   `no_such_client,default` in the working tree; put it back and check `git status` before
   committing. **If any video's caption answer differs between the two functions, do not
   commit: stop and report the table.** The Results row carries the table raw.

### Commit 2: `feat(search): the download dialog opens at once on the thumbnail and says what it waits for`

Decisions 1, 2 and 9; O8-O12, O14, O15. Files: `search.html`, `search_result.html`,
`tests/unit/test_search_render.py`. Today's lyric widgets stay; commit 3 replaces them.

1. The card: `data-ytDuration` (O9).
2. The dialog's markup moves after `#container_search_result` and out of
   `{% if search_rows %}`; the restore drops a saved copy's own dialog (O11).
3. The top of the dialog: the title; `#modal-video-meta` (O9); the 16:9 box holds the
   `<video>`, always rendered (`controls playsinline muted preload="metadata"` as today), under
   `#modal-thumb-layer`. The layer holds the card's own thumbnail (its `img` src, so nothing new
   is fetched; `object-fit: cover`), a round Play button `#modal-play` (`icon-play`,
   `aria-label` "Play preview" through `_()`), and "Preview unavailable"
   `#modal-preview-unavailable`, hidden. Delete `#video-loading-overlay`, `.video-spinner` and
   `@keyframes video-spin`.
4. The breathing line `#lyrics-wait`, in `#lyrics-section` just before where Queue appears: a
   large, bold, centred line (mockup: 24 px, about 36 px below the thumbnail) whose opacity
   breathes from 0.35 to 1 and back over 2.4 s. While the dialog waits it is the only thing in
   the lyric section. O8 under reduced motion.
5. State: one object for the open dialog, made anew on every open. It holds the open number
   (O12), the video (id, title, channel, link to the watch page), the caption answer (not yet,
   passed, sparse, failed, none), the stream link (not yet, none, a URL), whether Play waits,
   the title search's answer (not yet, or `{hits, preselect}`) and which view shows. Opening
   fills the top from the card with no request, then starts both requests at once:
   - `/caption_check?yt_id=`; an error answer reads as failed, with no link;
   - `/lyrics_search` with `title`, `channel` (always sent) and `typed` from
     `pikaraoke_search_term`, as `searchLyricsForActiveVideo` sends today; an error answer
     reads as no hits. The answer is held, not shown.
6. One render step sets the lyric section from the state, each time an answer arrives or the
   guest acts:
   - no caption answer yet: `#lyrics-wait` "Checking YouTube for captions…" alone;
   - the caption passed: today's captions block, at once, whether or not Genius has answered;
   - any other caption answer, or after "More options": the held list at once, with today's
     sparse or failed note; while the title search hasn't answered, `#lyrics-wait`
     "Searching Genius for lyrics…" instead. Today's custom search shows the same line while it
     runs, in place of "Searching lyrics...".
   - "More options" shows the held answer and does not search again.
7. Play:
   - link known: inside the tap, set the video's `src`, `load()`, `play()`;
   - link not known yet: inside the tap, today's unlock (`play()` the empty video, then
     `pause()`; lines 976-979 move here from the open), and the Play button breathes (O14); a
     link in the answer then starts the video, and no link gives O15;
   - an answer with no link: O15 at once, tapped or not;
   - the video's `playing` event hides the layer. Its `error` event, while this dialog is open
     and the video has a `src`, brings the layer back with "Preview unavailable". Bind both
     once when the script runs, not on each open: today's per-open `playing` listener piles up
     whenever a video never plays.
8. Close and reset: closing bumps the open number, pauses the video and clears its `src` as
   today. One reset, run on open and on close, puts back every element the dialog changes: the
   top, the layer, the views, the list, the custom box and its input, the notes, every button's
   classes, `disabled` and text, and the wait line (O11). The fade's delayed close closes only
   the dialog it faded (its open number), and an open removes `is-fading-out`: today a card
   tapped during the 2 s fade opens a dialog that the fade then closes, unseen.
9. Rewrite the "Flow:" comment (lines 659-674) for the new order.
10. Test (`test_search_render.py`): a card carries `data-ytduration` with the result's length,
    and an empty one when YouTube gave none.
11. ui-check (`.claude/skills/ui-check`; script in the scratchpad, not committed). Launch the
    worktree, run a real search, and fake `/caption_check` and `/lyrics_search` with Playwright's
    `page.route`, each answering after a delay the trial sets. Screenshot every state at
    390×844. Run each trial three times and record the pass counts:
    1. the caption passes at 1.5 s, Genius at 3 s: thumbnail, title, the line under it and
       "Checking YouTube for captions…" at once; the captions block at 1.5 s; one
       `/caption_check` request;
    2. no caption at 1 s, Genius at 3 s: "Searching Genius for lyrics…" between; the list at 3 s;
    3. sparse at 2 s, Genius at 0.5 s: the list at 2 s, with no second wait;
    4. Play tapped at 0.2 s, the answer at 1.5 s with a link that answers 404: the Play button
       breathes, then "Preview unavailable"; no request beyond the two at open, none on Play;
    5. an answer with no link: "Preview unavailable" with no tap;
    6. close at 0.5 s and open another card: the first card's late answers change nothing; the
       same when the same card is reopened;
    7. a card tapped during the fade-out after a download opens a dialog that stays open;
    8. a results copy saved in sessionStorage with an old-style dialog inside: back on Search,
       a card opens the new dialog;
    9. reduced motion (`emulate_media`): the line has no animation.
    If ui-check can't launch (the RDP drive not mounted), say so in the Results row and leave
    these to Ken.

### Commit 3: `feat(search): the dialog's lyric choice is one list of lyrics with an (i), and its button reads Queue`

Decisions 7, 8 and 10-15; O4-O7, O16. Files: `search.html`, `pikaraoke/routes/search.py`,
`static/library-pages.css` and `static/library-pages.js` (header comments only),
`tests/unit/test_search_routes.py`, `tests/unit/test_search_render.py`.

1. `search.html` loads `library-pages.css` and `library-pages.js` in its scripts block and
   imports `info_tip` (O5).
2. The lyric section's markup, in this order (mockup screens 2-5):
   - `#lyrics-caption-view`: `Lyrics: <strong>YouTube captions</strong>` (one `{% trans %}`)
     with its (i), the `passed` line.
   - `#lyrics-list-view`: the label "Lyrics" (`<label for="lyrics-dropdown">`) with its (i)
     holding all of O4's lines; `#lyrics-select-wrap` (`select is-fullwidth`, no `is-small`)
     around `#lyrics-dropdown`; `#lyrics-empty` "No lyrics found for this video.", in the
     warning colour, in the list's place (mockup screen 5); `#lyrics-search-open` "Search for
     other lyrics…" (outlined, full width, 44 px, `icon-search`); `#lyrics-custom-search`
     holding the label "Type the song title and artist", the input and a Search button; under
     it, `#lyrics-search-none` "Nothing found for that search.", hidden. Keep the ids
     `lyrics-custom-input` and `lyrics-custom-btn`: the page-wide Enter handler (line 277)
     exempts the input by its id, until `search_official_captions` commit 6 deletes that
     handler.
   - `#lyrics-wait` (commit 2).
   - One `#lyrics-queue-btn` (`is-primary is-fullwidth`, 48 px, bold) for both views.
   - `#lyrics-other`: "Other lyrics…" as a link-styled `<button>` with a 44 px tap area, in the
     captions view only.
   - Delete `#lyrics-caption-note`, `#lyrics-loading`, `#lyrics-srt-primary` with
     `#lyrics-srt-note` and `#lyrics-srt-btn`, `#lyrics-more-options`, `#lyrics-results-label`,
     `#lyrics-download-wrap` with `#lyrics-download-btn`, the input's placeholder,
     `CAPTION_NOTES`, and the CSS of each.
3. The label rows: "Lyrics" and "Lyrics: YouTube captions" at one size (mockup: 15 px). The
   (i)'s icon sits about 4 px after the label's last letter, through a negative left margin on
   `.info-tip-btn` in a rule scoped to the dialog; the 36 px button keeps its size (decision 10).
4. The list's arrow (decision 14): delete the `⌄` rule and the rule that hides Bulma's arrow.
   Bulma 1.0.4's own arrow is drawn with borders and sized in `em`, and `bulma-dark.css` already
   colours it `--dark-link`. Give `#lyrics-select-wrap` the list's font size
   (`--lyrics-dropdown-font-size`), so the box is 44 px and the arrow scales with it, and give
   the arrow a 3 px border (mockup).
5. The list (decision 13), filled by one function from the answer it shows: a "YouTube" group
   holding `__srt__` "YouTube captions (recommended)" when the caption passed; a "Genius.com"
   group of hits, each "title — " + `libraryPages.byline(hit)`; the disabled "Choose the lyrics"
   first when nothing is selected (O6). No other group, no emoji. With neither group:
   `#lyrics-empty` in the list's place, the box open by itself and not focused (focus would
   raise a phone's keyboard over the dialog), the search button hidden, Queue disabled
   (decision 8).
6. The views:
   - the caption passed: the captions view. "Other lyrics…" switches to the list view on the
     held title answer, selected by O6; until the title search answers, "Searching Genius for
     lyrics…".
   - any other caption answer: the list view.
   - The list view's (i) shows O4's lines for the moment's state.
7. Searching for other lyrics: the button gives way to the box and focuses the input. Search or
   Enter with text hides `#lyrics-search-none`; while the search runs, `#lyrics-wait`
   "Searching Genius for lyrics…" stands in Queue's place. With hits, the Genius group is
   replaced, the selection is "Choose the lyrics" (O6) and the Genius line becomes
   `typed-hits`. With none: O7. The box stays open after either.
8. Queue (decision 15).
   - `queueAfterDownload()` returns the tick of `#add-to-queue-search`. `postDownload` and the
     button's label both read it, so what the button says and what happens cannot disagree.
   - The label reads "Queue" when ticked and "Add to library" when not, set on every render.
     The button is enabled in the captions view, and in the list view when something is
     selected.
   - A tap (O16): take the video from the state; disable the button, with no spinner (decision
     9); post `/lyrics_select` (`mode: "srt"` from the captions view or for `__srt__`, else
     `genius_id`); on success `postDownload`, the label "Queued" or "Added" with today's check
     icon, and `fadeOutPreviewModal(1000)`; on an error, today's "!" flash, then back.
9. Strings: the script's (the wait lines, the four Queue labels, "Choose the lyrics", "Preview
   unavailable", the group and option labels) sit in one object through
   `{{ _("…") | tojson }}`; the markup's go through `{% trans %}`. "…" is U+2026. The catalogs
   are not regenerated.
10. `/lyrics_select` (decision 7): `mode` accepts only `"srt"`, the error message says so, and
    the docstring loses `raw`. The pipeline's `raw` branch and the library tools' transcribe
    choice are untouched.
11. Tests.
    - `test_search_routes.py`: the `mode: raw` test becomes "`raw` answers 400 and writes
      nothing". New: `srt` answers 204 and writes `{"yt_id": …, "mode": "srt"}` (no test covers
      it today).
    - `test_search_render.py`: the results page loads `library-pages.css` and
      `library-pages.js`; the dialog holds an `info-tip`; the page has no `__raw__`,
      "Raw Transcription", "Other Options" or `__custom__`; `id="lyrics-custom-input"` appears
      exactly once.
12. ui-check, as in commit 2, with `/lyrics_select` and `/download` also faked so nothing
    downloads; record their bodies. Screenshot every state at 390×844 beside the mockup's
    screen; three runs of each, pass counts in the Results row:
    1. the caption passed: "Lyrics: YouTube captions", Queue and "Other lyrics…", no search
       button; Queue posts `mode: "srt"`, then `/download`;
    2. "Other lyrics…": the YouTube group, then the Genius group, the preselect selected; with
       no preselect, "Choose the lyrics" and Queue disabled;
    3. sparse, hits, no preselect: "Choose the lyrics", Queue disabled until a pick; the (i)
       shows `sparse` and `title-hits`;
    4. no caption, no hits: "No lyrics found for this video.", the box open and not focused, no
       search button, Queue disabled; the (i) shows `none`, `title-none` and `empty`;
    5. a typed search with hits: "Choose the lyrics"; with none: the list and its selection
       unchanged, "Nothing found for that search.";
    6. the box ticked: "Queue", then "Queued", `/download` sent `queue: true`; unticked: "Add
       to library", "Added", `queue: false`;
    7. the list is 44 px tall and its arrow is Bulma's `::after`, with no `::before`.

### Stop

After commit 3 and its Results row. Don't push, land or retire anything. Report a Review-due
checkpoint for commits 1-3 (several files, a helper the library tools share, and a client state
machine with answers racing each other): the `/code-review` line with the commit range, the
files, and one finder angle per Self-Review axis.

### Manual checks (Ken, on phones)

- [ ] Each screen matches the mockup's lower row. Where they differ, the decisions win (the
  card reads "Queue…", decision 15).
- [ ] The list's arrow sits right on Android Chrome.
- [ ] iPhone (Safari) and Android (Chrome): Play tapped before the wait ends starts the video
  once it ends; tapped after, it starts at once.
- [ ] A video with a good manual caption: the captions screen after one wait. A video without:
  the Genius list the moment the wait ends.
- [ ] "Add to queue after download" unticked: the dialog reads "Add to library", and the song
  downloads without joining the queue.

### At landing (not this run)

- `plans/open-issues.md` on `dev`: reword "A restored search page can show a stuck card" to
  the card's half only (O11), in a plan-only commit.
- Whichever of this branch and `search_official_captions` Part 2 lands second points
  `queueAfterDownload()` at the surviving box (`#add-to-queue` after Part 2's commit 7), and
  rebases over `search_result.html` and `search.html`, which both edit.

## Results log

| commit | hash | unit tests | checks | notes |
| ------ | ---- | ---------- | ------ | ----- |
| 1 `feat(search): one yt-dlp lookup answers the dialog's caption check and its preview link` | `142d0c3` | baseline before the branch's code: 3849 passed, 0 failed. After: 3862 passed, 0 failed (+13). `TestCheckCaption` unchanged and passing | pre-commit passed on the 7 files; import smoke of `youtube_dl`, `library_regen`, `routes.search` ok; real-YouTube measurement below (8 videos + the bad-client row); `search.html`'s script not driven in a browser this commit (ui-check is commit 2); no `graphify-out/graph.json`, no update | Run 2026-11-17 on the VM, yt-dlp 2026.10.26, curl_cffi 0.14.0, deno 2.7.7. Client setting put back after the last row; no `no_such_client` left in the tree. `/code-review` due at the stop (plan, Stop section) |
| 2 `feat(search): the download dialog opens at once on the thumbnail and says what it waits for` | | | | |
| 3 `feat(search): the dialog's lyric choice is one list of lyrics with an (i), and its button reads Queue` | | | | |
| manual checks (Ken) | | n/a | | |

### Commit 1 measurement (raw)

Script `measure_lookup.py` in the session scratchpad, not committed. Per video, one
`download_manual_en_subs` call and one `lookup_video` call, each into its own folder under
`get_temp_directory()`. Words: `_srt_word_count` of each caption. Length: the lookup's `duration_s`,
used for both gates (`_measure_caption`). Link: one ranged GET (`bytes=0-1023`), Android Chrome user
agent, no other headers. "Answer identical" = both functions agree on found, word count and
passed.

| client setting | video | `download_manual_en_subs`: caption (words) | `lookup_video`: caption (words) | length s | passed old/new | lookup time | link GET | answer identical |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| tv_simply | dQw4w9WgXcQ | yes (352) | yes (352) | 213.0 | True/True | 5.92 s | 206 | yes |
| tv_simply | fJ9rUzIMcZQ | yes (380) | yes (380) | 359.0 | True/True | 5.89 s | 206 | yes |
| tv_simply | kJQP7kiw5Fk | yes (519) | yes (519) | 282.0 | True/True | 6.00 s | 206 | yes |
| tv_simply | 9bZkp7q19f0 | no | no | 252.0 | False/False | 5.50 s | 206 | yes |
| tv_simply | JGwWNGJdvx8 | yes (603) | yes (603) | 263.0 | True/True | 5.38 s | 206 | yes |
| tv_simply | hT_nvWreIhg | yes (521) | yes (521) | 283.0 | True/True | 5.74 s | 206 | yes |
| tv_simply | OPf0YbXqDm0 | yes (632) | yes (632) | 270.0 | True/True | 5.75 s | 206 | yes |
| tv_simply | RgKAFK5djSk | yes (471) | yes (471) | 237.0 | True/True | 6.13 s | 206 | yes |
| no_such_client | dQw4w9WgXcQ | yes (352) | yes (352) | 213.0 | True/True | 5.56 s | 403 | yes |

Every call exited 0. No video in the table has a caption that fails the gate; the one sparse case
(found, below the gate) is covered by the unit tests only.
