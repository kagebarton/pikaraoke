# Download modal: open at once, one YouTube lookup

Model: Claude Opus 5.5 writes the step-by-step spec for Claude Sonnet 5.5 from this brief
(brief by Claude Fable 5.2, 2026-11-11)

Branch `download_modal_speed` off `dev` at `1016e20`, worktree
`.claude/worktrees/download_modal_speed` (inside the main checkout, gitignored via `.claude/`;
`models/` is symlinked in). Work and run everything from the worktree. If `dev` has moved,
rebase onto it before the first code commit.

This is a brief, not a spec: it fixes what Ken decided, what was measured, and what must hold.
The function shapes, the route shape, the wording of each status line and the commit split are
Opus's to write (see "For Opus to settle").

## Goal

Tapping Select on a search result opens the download modal. Today it shows a spinner while the
server runs two full yt-dlp lookups one after the other (the video link, then the caption), and
only then starts the Genius search. The download button appears after roughly 10 s, and nothing
on screen says what the wait is for. Guests get confused and tap away.

After this change the modal shows the video's thumbnail and details at once, says what it is
waiting for, and runs one yt-dlp lookup per open. The download button appears after the time of
one lookup.

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

## What exists (checked 2026-11-11, `dev` at `1016e20`)

- `pikaraoke/lib/youtube_dl.py:263` `get_preview_info(video_url)`: the video-link lookup. Asks
  for format 18 with `--extractor-args youtube:player_client=tv_simply,default`, prints the
  link, the subtitles map and the duration, 15 s timeout. Only caller: the `/preview` route.
- `pikaraoke/lib/youtube_dl.py:365` `download_manual_en_subs(video_url, dest_dir, stem)`: the
  caption lookup. Writes `<stem>.en.srt` (manual English only, converted to SRT), 60 s timeout,
  raises `CaptionDownloadFailed` when yt-dlp could not
  answer. Also used by the library tools (`library_regen.py:550`, `fetch_caption`), so it stays.
- `pikaraoke/lib/library_regen.py:595` `_check_caption`: downloads the caption into a scratch
  folder under `get_temp_directory()`, measures it with `_wpm` (line 485) and `_caption_passes`
  (line 497), returns `CaptionCheck(found, wpm, passed, failed)`. Two entry points:
  `check_caption(job)` (line 576, library tools) and `check_video_caption(video_id, duration_s)`
  (line 587, whose only caller is the search route).
- `pikaraoke/routes/search.py`: `/preview` (line 184) returns the stream link, whether a manual
  English caption exists, and the duration. `/caption_check` (line 194) takes `yt_id` and
  `duration` and returns `found`, `passed` and `failed`.
- `pikaraoke/templates/search.html`: the flow is described in the comment at lines 659-672.
  `openPreviewModal` (line 946) calls `/preview`, then `checkCaption` (line 778) calls
  `/caption_check`, then `searchLyricsForActiveVideo` (line 771) calls `/lyrics_search`. Modal
  markup is at lines 1173-1213. Lines 958-961 play the empty `<video>` inside the click so iOS
  Safari allows a later `.play()` from an AJAX callback.
- `pikaraoke/templates/search_result.html`: each card already carries the thumbnail
  (`https://img.youtube.com/vi/<id>/mqdefault.jpg`), the title, the channel and the duration
  badge. The `<li>` has `data-ytid`, `data-yttitle` and `value` (the URL) only; the channel and
  duration are in the card's markup, not in data attributes.
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
  the channel and the length, and a status line saying it is checking for YouTube captions.
- On open, two requests start together: the combined lookup, and the Genius search (title
  first, then the page's search term, as `runLyricsSearch` does today). The Genius answer is
  held, not shown.
- When the lookup answers: a caption that passes shows the "Use YouTube captions" block as
  today. Otherwise the held Genius list shows at once, with today's note for a sparse caption
  or a check that could not run. If Genius has not answered yet, its own loading line shows.
- "More options" under the caption block shows the held Genius list without searching again.
- Play: with the link in hand, the video replaces the thumbnail and plays. Tapped before the
  lookup has answered, the thumbnail shows a spinner and the video starts when the link
  arrives. With no link, or when the video element reports an error, the modal says the preview
  is unavailable; the caption answer and the download are unaffected.
- The download buttons, the sidecar choice written by `/lyrics_select`, and the fade-out stay
  as they are.

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
  dropped (`stillShowing`, `search.html:785`).
- New user-facing strings go through `_()` / `{% trans %}`.
- iOS Safari only allows `.play()` tied to a tap. A Play tap that arrives before the link must
  keep that permission (the trick at `search.html:958-961` belongs with the Play tap now, not
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

## For Opus to settle

- The shape and home of the combined lookup, and how `_check_caption` shares it with
  `check_video_caption` without changing `check_caption(job)` for the library tools.
- The combined call's timeout. Today the link call gives up at 15 s and the caption call at
  60 s; the modal now waits on one number.
- The route: extend `/caption_check` or rename it. Its `duration` parameter is no longer needed,
  since the lookup returns the length.
- The wording of the status line in each state, and what becomes of today's three
  `CAPTION_NOTES` strings.
- Where the modal reads the channel and length from (the card's markup today; data attributes
  on the `<li>` would be the cleaner source).
- Whether closing the modal stops the running lookup. Today it does not; the process runs to
  its timeout and its answer is dropped.
- `plans/open-issues.md`, "Search results": "A restored search page can show a stuck card"
  mentions the modal's saved contents. Say whether the reorder makes it a few-line fix; if not,
  leave it.
- The commit split. Two looks natural: the single lookup with its route and tests, then the
  modal.

## Out of scope

- Any lookup when search results load (decision 6).
- YouTube's embedded player, and relaying the video through the server. Both were offered to
  Ken as alternatives to decision 1 and not chosen.
- yt-dlp loaded into the server process.
- Remembering a lookup between opens.
- A download button that is usable before the caption check answers.
- yt-dlp options that skip parts of the lookup (`player_skip`, `skip`). They are the kind of
  setting decision 5 rules out.

## Done when

- The modal shows the thumbnail, title, channel, length and status line with no network wait.
- A unit test with the subprocess mocked shows one yt-dlp call for a modal open, returning the
  caption answer and the link together; no route remains that fetches a link on its own.
- A lookup whose link is missing still answers the caption correctly (unit test), and by hand:
  with the client setting pointed at a name yt-dlp does not have, captions and download work
  and Play says the preview is unavailable.
- On a video with a good manual caption, "Use YouTube captions" appears after one lookup. On a
  video without one, the Genius list appears as soon as the lookup answers, with no second
  wait.
- Ken's live check on an iPhone (Safari) and an Android phone (Chrome): Play works when tapped
  before the lookup answers and when tapped after.

## Overlap with `search_official_captions`

That branch (plan committed, code not started, Sonnet due the week of 2026-11-16) edits the
search command at `youtube_dl.py:249`, the `/search` and `/search/more` routes, and
`official_rank.py`. This one edits the preview and caption functions further down
`youtube_dl.py`, the `/preview` and `/caption_check` routes, and the modal half of
`search.html`. No function is touched by both. Whichever lands second rebases.

## Results log

(empty)
