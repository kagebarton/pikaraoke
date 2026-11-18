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
3. Left slot: place in line, 52 px. Two looks only: solid grey for ready, dashed grey outline for
   not playable. Not playable covers paused and every held kind (downloading, processing, waiting
   for lyrics), since `queue_hold` never plays a held song. The slot keeps a word saying which
   ("paused" / "processing"), but the colour is the same so the page shows one signal, not three.
   Not-playable rows fade to 40%; the delete button on them stays full strength.
4. Now playing is its own card at the top (bars, singer, song · artist; admins get a gear). The
   bars and the NOW label are neutral grey; the singer's name stays green like every row.
5. Guests: a large "Pause my songs (BRB)" button pinned to the bottom of the screen (stays visible
   while the list scrolls under it), only when they have songs queued. Teal (the site's link
   colour): outlined while active, filled when it flips to "I'm back: unpause my songs". Their own
   rows get a red delete button instead of the gear; other rows get nothing.
6. Delete asks to confirm (dialog: Keep it / Remove).
7. Admins: drag handle, gear on every row and on Now playing, same menus as today. No pause button.
   Footer: Add random songs (how many beside it), Clear the whole queue.
8. Your own songs are marked by tinted rows (option A; B "YOU" label and C green outlined name
   were not picked). Admins see their own rows tinted too.

## Pending

- `/queue/user/pause` (`routes/queue.py`) already toggles all of a user's songs, but its form
  requires an unused `song` field: drop it from the schema or send a placeholder.
- Unlanded `singer_defaults` changes three lines of `queue.html` (modal background scope): expect a
  small conflict when it lands.
- Spec and phases (nothing blocks them now).

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
