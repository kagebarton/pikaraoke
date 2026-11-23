# UI tweaks

Model: Claude Opus 5.5 (plan). Executor not yet named.

Branch `ui_tweaks` off `dev` at `c9c3b010`, worktree `.claude/worktrees/ui_tweaks`. A home for
small phone-UI changes found after the v2 revamp. **Starts after the other UI revamps land**
(`browse_phone`, `processing_phone`, and the Search restyle on `search_official_captions`):
rebase onto `dev` first, since `base.html` and the shared row stylesheet will have moved.

High-level only. Each item gets its detail (files, tests, phone checks) when the branch starts.

Visual reference: the canvas https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken),
boards "Now Playing: current singer", "Now Playing: admin" and the four "Queue" boards, mocked
up 2026-11-23. Where this file and the canvas differ, this file wins.

## Scope

1. **Yellow now-playing bars on Now Playing and Queue; a pause freezes them.** Open-issues entry
   "Bring the yellow Now Playing animation back, and use it on Queue; pause stops it."

   - Now Playing: the animated bars (`static/images/now-playing.gif`) beside the heading, about
     40 px wide, as Home had them.
   - Queue: the same bars replace the five still grey bars on the Now card, about 32 px wide
     above the "Now" label.
   - While the song is paused, both show the still frame (`now-playing.png`). One shared helper
     picks gif or png from `is_paused`; Queue's `np` already carries it.

2. **The top nav bar stays on screen while scrolling, on every page.** Open-issues entry "Keep
   the top blue nav bar on screen while scrolling, on every page."

   - One change in `base.html`, which owns the navbar for every page.
   - Check: the burger menu opens under the bar at any scroll position; the SPA page swap keeps
     it; on Queue, the nav bar plus the fixed BRB bar leave enough room for the list on a phone;
     `.base-notification` and the mobile `body { min-height: 120vh }` still behave.

Ruled out (2026-11-23): putting the bars in the nav bar so they show on every page. The admin's
phone nav is already full, and every page would have to track pause state.

## Candidates, not yet in scope

- **Square tap flash.** Open-issues entry "The brief flash after a tap is square, not rounded
  like the button." Ruled app-wide on 2026-11-23 with no owner branch; it fits here if Ken wants
  it.

## Open for Ken before starting

- **Which yellow.** The gif's yellow is brighter and more lemony than the palette amber
  `#f1b70e` used for song titles on Now Playing. Keep the gif as is, or recolour it to the amber.
- **Queue slot width.** The open-issues entry says 60 px; the canvas draws Queue at 52 px. The
  bars fit either; confirm against what landed.

## Phases

0. Rebase onto `dev`; re-read the open-issues entries and the canvas boards; settle the open
   questions above.
1. Bars (item 1), with tests for the gif/png pick.
2. Sticky nav bar (item 2).
3. Ken's phone check (Chrome, Android): both items on Now Playing, Queue, and one other page.
4. Land on `dev` per CLAUDE.md; drop the shipped entries from `plans/open-issues.md`; retire
   the branch as `archive/ui_tweaks`.

## Plan log

| Date       | Commit | Step                                    |
| ---------- | ------ | --------------------------------------- |
| 2026-11-23 | -      | Plan recorded; waiting on the revamps. |
