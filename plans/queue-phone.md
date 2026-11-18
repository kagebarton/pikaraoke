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
   colour; grey off and blue on since L9, below): outlined while active, filled when it flips to
   "I'm back: unpause my songs". Their own
   rows get a red delete button instead of the gear; other rows get nothing.
6. Delete asks to confirm (dialog: Keep it / Remove).
7. Admins: drag handle, gear on every row and on Now playing, same menus as today. No pause button.
   Footer: Add random songs (how many beside it), Clear the whole queue.
8. Your own songs are marked by tinted rows (option A; B "YOU" label and C green outlined name
   were not picked). Admins see their own rows tinted too.

## Phone pages: one look (Ken, 2026-11-18)

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). Visual reference: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Queue: admin",
"Queue: guest, with a failed row", "Queue: guest after BRB", "Queue: guest, delete confirm" and
"Reference palette". For colours and buttons it wins over this branch's mockup; this file wins
over both.

- **L9. BRB is a grey button while off and blue `#375a7f` while on** (was teal). Changes
  decision 5's colours: teal is for links and the current nav icon only (L3). The canvas draws
  it off as `#434d4e` with a `#5e6d6f` border (L15) and on as `#375a7f`, white text both ways.
- **L14. Processing is the admin's only.** This branch owns both halves, in this order (Ken
  placed the nav half here on 2026-11-18, so the order stays inside one branch):
  1. **The failed row first.** A guest's own song that fails processing stays on Queue as a red
     "failed" row with a short reason and Dismiss, until dismissed. Today queue hold takes it
     off with a passing notice (`_on_processing_error`, `queue_hold.py:157`). No step detail on
     Queue rows: Ken, guests prefer less information.
  2. **Then the nav icon.** The Processing nav icon (`#processing`, `base.html`) is hidden from
     guests. The page still opens by its address, as Now Playing's hidden controls do. That
     frees an icon's width for the name pill (`singer_defaults`, L6). Check that nothing a guest
     sees links to Processing.
- The shared stylesheet (decision 1) uses L1 (one green, one amber), L15 (grey fill `#434d4e`)
  and L16 (disabled: no fill, a faded border, a `#8c9b9d` label, no opacity fade) from
  `bulma-dark.css`. They land on `singer_defaults`, its Phase 5; take them from `dev` once that
  lands rather than restating the values here.
- **Not ruled, for the shared stylesheet to settle** (the review's "small gaps"): the slot is
  52 px here, 60 px on Browse and Processing; "processing" is a green Queue button on Browse
  (L8) but a dashed grey slot here and on Processing; the chevron opens a menu on Browse and
  expands the row on Processing, where Queue uses a gear; the 13 px sub-line grey `#b5bfc0` is
  not a `bulma-dark.css` token yet (the canvas palette says it becomes one here).
- The Search page's restyle (L12) waits for this branch to land with its shared stylesheet.

## Pending

- `/queue/user/pause` (`routes/queue.py`) already toggles all of a user's songs, but its form
  requires an unused `song` field: drop it from the schema or send a placeholder.
- Unlanded `singer_defaults` changes three lines of `queue.html` (modal background scope): expect a
  small conflict when it lands.
- `singer_defaults` L6 rewrites the same nav bar in `base.html` (the name pill, 44 px icons):
  expect a small conflict with L14's nav half, resolved by whichever lands second.
- Spec and phases (nothing blocks them now).

## Results log

| Date | Phase | Commit | Note |
|---|---|---|---|
