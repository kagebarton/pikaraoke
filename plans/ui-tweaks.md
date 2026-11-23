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
   - Queue: the same bars replace the five still grey bars (`BARS` in `queue.html`) on the Now
     card, about 32 px wide above the "Now" label, in the 60 px slot as landed (`.qp-now-slot`).
     The canvas draws that slot at 52 px; the build is right.
   - The gif keeps its own yellow (Ken, 2026-11-23), not the palette amber `#f1b70e`.
   - While the song is paused, both show the still frame (`now-playing.png`). One shared helper
     picks gif or png from `is_paused`; Queue's `np` already carries it.

2. **The top nav bar stays on screen while scrolling, on every page.** Open-issues entry "Keep
   the top blue nav bar on screen while scrolling, on every page."

   - One change in `base.html`, which owns the navbar for every page.
   - Check: the SPA page swap keeps it; on Queue, the nav bar plus the fixed BRB bar leave enough room for the list on a phone;
     `.base-notification` and the mobile `body { min-height: 120vh }` still behave.

3. **A tap's flash takes the button's rounded shape, on every page.** Open-issues entry "The
   brief flash after a tap is square, not rounded like the button." Added by Ken 2026-11-23.

   - Probable cause, not confirmed: nothing sets `-webkit-tap-highlight-color`, so the phone
     browser paints its own rectangular highlight over every button.
   - Fix once for all pages in a stylesheet `base.html` loads everywhere (`custom.css`): turn the
     browser's highlight off, and add a pressed look (`:active` tint) so a tap still shows.
   - Confirm the cause on Ken's phone before calling it fixed.

4. **The burger menu becomes an (i) icon that opens the Info page.** Added by Ken 2026-11-23.

   - The menu's only entry is Info (`#info`, `/info`): the share URL and QR code for everyone,
     then the admin login for a guest (when a password is set) or the settings and Log out for
     the admin. One tap instead of two.
   - The (i) (`icon-info-circled-1`, as the menu uses today) takes the burger's place at the
     right end of the bar, after the name pill, pushed into the bar's right padding so its
     icon sits near the edge and the rest of the bar keeps the room (Ken, 2026-11-23). Its tap
     area stays 44 px. Not a gear: beside the sliders pill it would
     read as a second settings button.
   - Delete what the burger needed: the `.navbar-menu` block, the burger markup, the
     burger's open/close code and its two close calls in `spa-navigation.js`, and the phone
     dropdown CSS in `base.html`. The nav highlight for `/info` keeps working through `#info`.
   - Do it before item 2, so the sticky nav bar has no menu to account for.

Ruled out (2026-11-23): putting the bars in the nav bar so they show on every page. The admin's
phone nav is already full, and every page would have to track pause state.

## Phases

0. Rebase onto `dev`; re-read the open-issues entries and the canvas boards.
1. Bars (item 1), with tests for the gif/png pick.
2. Burger to (i) (item 4).
3. Sticky nav bar (item 2).
4. Tap flash (item 3).
5. Ken's phone check (Chrome, Android): all four on Now Playing, Queue, and one other page,
   including the stepper buttons where the square flash was first seen, and the (i) as guest
   and as admin.
6. Land on `dev` per CLAUDE.md; drop the shipped entries from `plans/open-issues.md`; retire
   the branch as `archive/ui_tweaks`.

## Plan log

| Date       | Commit     | Step                                                          |
| ---------- | ---------- | ------------------------------------------------------------- |
| 2026-11-23 | `31f0adc1` | Plan recorded; waiting on the revamps.                        |
| 2026-11-23 | `29014e7f` | Ken: keep the gif's yellow, add the tap flash; slot is 60 px. |
| 2026-11-23 | -          | Ken: burger menu becomes an (i) icon to the Info page.        |
