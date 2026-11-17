# Queue page for phones

Model: Claude Opus 5.5 (decisions). Executor not yet named.

Branch `queue_phone` off `dev` at `764df44`, worktree `.claude/worktrees/queue_phone`. Sibling of
`browse_phone` (`plans/browse-phone.md` there); the Processing page will get its own branch later.

Mockup (private to Ken): https://claude.ai/artifact/8nSQUuVfMQ3cKNnRY31C9p, row "Queue v2 (draft)"
(six screens). Today's Queue page is the "Queue today" row on the same canvas. Where this file and
the mockup differ, this file wins.

## Decided (Ken, 2026-11-17)

1. Own branch, not `browse_phone`: Queue is nearly all `templates/queue.html` and can land before
   Browse's name-source test. Queue lands first and creates the shared row style (two-line rows,
   coloured status slot, 40 px square buttons) in one stylesheet; Browse and Processing reuse it.
2. Rows: singer's name on top, 17 px bold; "song · artist" 13 px grey under it.
3. Left slot: place in line, 52 px; its colour is the state: grey ready, blue processing (every
   held kind: downloading, processing, waiting for lyrics), amber paused. Paused and held rows fade
   a little.
4. Now playing is its own card at the top (bars, singer, song · artist; admins get a gear).
5. Guests: a large "Pause my songs (BRB)" button at the top, only when they have songs queued; it
   flips to "I'm back: unpause my songs". Their own rows get a red delete button instead of the
   gear; other rows get nothing.
6. Delete asks to confirm (dialog: Keep it / Remove).
7. Admins: drag handle, gear on every row and on Now playing, same menus as today. No pause button.
   Footer: Add random songs (how many beside it), Clear the whole queue.

## Pending

- Highlight for your own songs: A tinted rows, B "YOU" label, C only your name green with a thin
  outline (mockup screens 2-4). Ken picks.
- `/queue/user/pause` (`routes/queue.py`) already toggles all of a user's songs, but its form
  requires an unused `song` field: drop it from the schema or send a placeholder.
- Unlanded `singer_defaults` changes three lines of `queue.html` (modal background scope): expect a
  small conflict when it lands.
- Spec and phases, after the highlight pick.

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
