# Search-page picker: check the caption before offering it

Model: Claude Opus 5.5 (2026-10-27)

Decision 18 of `plans/web-library-tools.md` (branch `web_library_tools`), open
in `plans/open-issues.md` under "Decide at landing". Branch
`search_caption_check`, off `dev` at `e9c7922`.

## Rulings (Ken, 2026-10-27)

1. Check before offering, plus a backstop after the download.
2. While the check runs the modal says "Checking the caption…"; on a fail it
   shows the Genius list with the note "This video's caption is too sparse to
   be lyrics."
3. A check that can't run hides the caption option (as the repair page does).
4. Built in-session on a branch, not handed to an executor.

## Built

- `get_preview_info` also prints YouTube's `duration` (same yt-dlp call);
  `/preview` returns it.
- `library_regen.check_video_caption(video_id, duration_s)`: `check_caption`'s
  throwaway download and words-per-minute gate, measured against YouTube's
  length instead of the file's. Both share `_check_caption`.
- `GET /caption_check?yt_id=&duration=` on `search_bp` (open to guests, like
  `/preview`) -> `{found, passed, failed}`. A missing or unparseable duration
  goes in as `None`, so the caption can't be measured and passes (the gate's
  existing rule); the backstop then decides.
- `search.html`: with `srt_available`, the modal runs the check. Pass -> the
  captions-first view, as before. Fail -> note + Genius search, and the
  "YouTube Captions" dropdown option stays out. Found-but-sparse gets the
  sparse note; no answer gets "Could not check the caption."; a check that
  ran and found no caption after all gets no note, like a video without
  one. All three strings are the repair page's msgids.
- Backstop: `_pick_reason` no longer skips a `{"mode": "srt"}` choice; it
  gets the same on-disk gate as a direct-box download, so a sparse caption
  is deleted and the song goes on the needs-a-pick list. A Genius or
  transcribe choice still skips the gate.

## Behaviour changes worth knowing

- A picker caption choice whose download saved no caption now lands on the
  needs-a-pick list ("no caption") instead of transcribing.
- The overruled `{"mode": "srt"}` choice file stays until the admin's pick
  overwrites it; nothing reads it in between.

## Test plan (manual)

- [ ] Search, open a video with a manual English caption: "Checking the
  caption…" shows under the playing preview, then the captions-first view.
- [ ] A video whose caption is sparse (e.g. lyrics on screen, caption only
  `[Music]`): the note, then the Genius list, and its dropdown has no
  "YouTube Captions".
- [ ] A video with no manual caption: straight to the Genius list, no note.
- [ ] Close the modal mid-check and open another video: the first answer
  does not draw into the second.
- [ ] Download through "Use YouTube captions": processes as before.

## Results log

| date | commit | what |
| --- | --- | --- |
| 2026-10-27 | `c3e567d`, `a4363cb` | built (picker check; after-download backstop); full suite 2298 passed on the VM; live `check_video_caption` on `WVe80iZtlYU` (234 s, 51.8 wpm, pass) and `dQw4w9WgXcQ` (213 s, 99.2 wpm, pass) |
| 2026-10-27 | `79f6ea3`, `b1a5801` | `/code-review` of `c3e567d`, `a4363cb` (3 angles): 10 candidates, 2 taken: a check that found no caption showed "Could not check the caption." (now no note), and `library_regen._watch_url` duplicated `library_tools._watch_url` (now one `library_regen.watch_url`); full suite 2298 passed. Ken kept the srt-choice-without-caption -> needs-a-pick change. Dropped: check failure hides captions (ruling 3); no download control while checking (follows ruling 1; server-bounded ~75 s); non-finite `duration` from a hand-made request; same-video reopen mid-check (needs two different answers); `except ValueError: pass` on "NA" and positional `--print` parse (match the function's existing idiom); folding the check into `/preview` (design, not defect) |
