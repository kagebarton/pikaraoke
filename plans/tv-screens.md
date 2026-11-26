# TV screens: inter-song screen, during-song overlay, logo

Model: Claude Opus 5.5 (design record). Executor not yet named.

Branch `tv_screens` off `dev` at `442269f6`, worktree `.claude/worktrees/tv_screens`. Design
only so far: no code. Records the decisions and preferences from the 2026-11-23 design session.
Each item gets its detail (files, tests, TV checks) when a plan for building it is written.

## Canvases

Both are private to Ken. The live canvas is the working copy; a snapshot of each canvas's source
files (`canvas.json` plus one `.dc.html` per board) is committed beside this file. Where this
file and a canvas differ, this file wins.

| Canvas | Link | Snapshot |
| --- | --- | --- |
| GPUKaraoke logo ideas | https://claude.ai/artifact/9VP7X4UEq2kLzv9UdE5Dbg | `plans/tv-screens/logo-canvas/` |
| TV screens revamp: inter-song and during-song | https://claude.ai/artifact/5mAc6xxtxftYp2pgQeTvmG | `plans/tv-screens/screens-canvas/` |
| Phone UI reference (palette source) | https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL | not copied; board "Reference palette" |

Snapshot file to board:

- Logo canvas: `Main` = 1 Chip mic, `MicHouse` = 2, `ThreeMics` = 3, `StemBars` = 4 (chosen),
  `SplitNote` = 5, `LyricWipe` = 6.
- Screens canvas (rebuilt 2026-11-25 to the rules in this file, version 25): `Main` = inter-song
  A with `state` (queue / preparing / allPaused), `afterCount`, `queueLength`, `longNames` and
  `hideUrl` settings; `Empty` = empty queue with `hideUrl`; `DuringCards` = during-song 1 with
  `phase` (intro / middle / end), `paused`, `settingChange` (none / key / vocals), `queueEmpty`,
  `longTitle`, `hideNowPlaying` and `bg`. Every other board is one of these three set to a
  scenario (`InterShort`, `InterLong`, `InterPreparing`, `InterAllPaused`, `EmptyNoUrl`,
  `DuringCardsMid`, `DuringCardsEnd`, `DuringHidden`, `DuringPaused`, `DuringPausedEnd`,
  `DuringSettingKey`, `DuringSettingVocals`, `DuringQueueEmpty`, `DuringLongTitle`,
  `DuringLongTitleMid`). Two notes on the canvas sum up the rules that a still can't show
  (timing, fades, restarts). Inter-song B (`Stacked`) and during-song 2 (`DuringMinimal`) were
  removed; they are in git history before this change.
- Screens canvas backgrounds: the during-song boards show real frames from the library, each
  letterboxed onto 1920 x 1080 as mpv shows it, picked with a `bg` setting. In the snapshot the
  board files point at the canvas's uploads (`/_blob/<id>`); the same frames are in
  `screens-canvas/backgrounds/`: `89e92204…` = `bg-16x9-toxic.jpg` (Britney Spears, Toxic, 16:9),
  `9b7f4509…` = `bg-4x3-are-you-happy-now.jpg` (Michelle Branch, 4:3, side bars), `0477c44f…` =
  `bg-cinema-incomplete.jpg` (Backstreet Boys, Incomplete, 1280 x 538, top and bottom bars).
  Opening card and minimal use 16:9, middle 4:3, last 30 s cinematic.

## Today's screens, for reference

From `pikaraoke/lib/overlay_manager.py` and `mpv_controller.py` at `442269f6`:

- Everything is ASS text drawn by `render_ass`, except the QR code, a BGRA bitmap in mpv overlay
  slot 0 (`send_qr_bitmap`). Sizes key off `_qr_height` = `max(120, screen_h // 6)` times
  `overlay_scale` (180 px at 1080p); font size is a third of that.
- QR flush in the top-left corner; server URL bottom-right; clock bottom-left (white).
- Playing: now-playing title top-right (orange `rgb(255,127,80)`), under it a timecode row
  (singer, elapsed / total, key, vocal % in dual-stem; light orange), under that the next song
  (steel blue `rgb(70,130,180)`, singer light blue). Emoji icons throughout.
- Idle (between songs): `placeholder.png` (neon house with three mic chimneys inside a ring of
  amber, cyan and magenta arcs) plus a top-right list of up to 5 queued songs, the first in
  orange.
- The idle list comes from `queue_manager.upcoming(5)` as `QueuedSong(title, singer)`: no
  artist field and no processing state.
- `splash_delay` (seconds between songs) defaults to 2.

## Decisions (Ken, 2026-11-23)

1. **Rename: under consideration, not decided.** PiKaraoke to gpukaraoke, "to better reflect
   what the project is now". The logo work uses the lowercase wordmark `gpukaraoke`. Scope (package,
   repo, UI strings) not discussed. Moved to `plans/open-issues.md` on `dev` 2026-11-25 (Future
   features); for this branch the rename is only the new logo on the inter-song screen.

2. **Logo: concept 4, Stem bars, "for now".**

   - Five rounded vertical bars, each split by a gap into an amber top (`#f1b70e`, the vocals) and
     a teal bottom (`#1abc9c`, the music): the stem separation the app does.
   - Wordmark Lato 900, `gpu` amber, `karaoke` white, on black.
   - Small sizes drop bars: four at 48 px, three at 28 px.
   - Used on the inter-song screen (footer, bottom centre) and the empty-queue screen (large).

3. **Inter-song screen: layout A.** Drawn at 1920 x 1080 on black.

   - "Up next" fills the left: `UP NEXT` label, singer (green `#2ecc71`, 150 px, mic icon), song
     title (amber, 76 px), artist (`#dbdee0`, 52 px), then a countdown bar (info blue `#3298dc` on
     `#282f2f`) with "Starts in 0:08".
   - Top-right panel, 620 px wide on `#1f2424`, 20 px corners: `AFTER THAT`, then 3 to 5 rows, each a
     numbered slot (as on the phone Queue page; dashed grey while processing), singer in green and
     "title · artist". "+ N more in the queue" when the queue is longer.
   - Long singer names and titles cut off with an ellipsis.
   - Empty queue: large logo, "The queue is empty. Scan the code to add a song." Same corners.

4. **The fixed corners sit in the same spots on both screens.** Asked so nothing moves at the switch.

   - QR top-left, 40 px in from both edges, 180 px (same size as today, no longer flush). Margin
     now 16 px (2026-11-25).
   - Clock bottom-left, address bottom-right ("Add a song" + URL in teal), each on a 60% black
     pill (the phone UI's rule for badges over thumbnails). On the black inter-song screen the pill
     is invisible, so only the text shows.
   - The top-right box: inter-song panel 620 px, then the during-song card in its full stage at
     680 px (widened from 620 on 2026-11-23 so the settings row holds the time; see Open).

5. **During-song overlay: concept 1, in three stages.** All top-right, 40 px in, on 60% black
   (16 px and 70% since 2026-11-25; padding and fades there too).

   - First 15-20 s: the full card (680 px). Line 1 the song title (amber, 44 px) left and mic +
     singer (green, 40 px) right; line 2 the artist (`#dbdee0`, 34 px); line 3 the settings row,
     `Key +2` and `Original Vocals 40%` tags left, elapsed / total right. No progress bar: the
     card is only up for 15-20 s. Below it a `NEXT Jae · Dancing Queen` line.
   - Middle: the compact card, at most 560 px and only as wide as its text. Line 1 the title
     (amber, 36 px) left and mic + singer (green) right; line 2 the artist (`#dbdee0`, 28 px) left
     and elapsed / total right, with a `Key +2` tag before the time only when the key is changed;
     progress as a 6 px strip on the card's bottom edge. Under it a small one-line
     "Next Jae · Dancing Queen".
   - Both cards keep the same places: title top-left, singer top-right, artist under the title,
     time on the right. At the switch things shrink and the settings row goes, nothing moves
     across. Artist-to-title size ratio is the same on both (34/44, 28/36).
   - The vocal tag reads "Original Vocals" (capital V, Ken), after the phone's "Original vocals",
     so guests don't read it as their own microphone. The phone keeps the lowercase v for now.
   - Last 30 s: the compact card, and under it the large green-bordered card "Jae, you're up
     next" with "Dancing Queen · ABBA".

## Preferences (Ken, for later design work too)

- Flat, simple geometric shapes, like the phone UI revamp.
- The logo must work on a black background.
- The app's palette (`bulma-dark.css`, the "Reference palette" board) on the TV too. Today's
  orange and steel blue were picked for TV clarity and do not match the app; legibility on a TV
  still matters.
- Many people watch the video while someone else sings: the during-song overlay takes as little
  of the picture as it can without losing legibility.
- Fixed elements stay put across screens to keep movement down at the switch.
- Logo round: draw on the inter-song background's logo for one or two ideas only, the rest
  original (concepts 2 and 3 drew on it).

## Not chosen

- Logo concepts 1 (chip mic), 2 (mic house in the ring), 3 (three mics in the ring), 5 (split
  note), 6 (lyric-wipe wordmark). An earlier "equalizer house" and "chip house" were dropped
  before drawing, for leaning on the background logo too much.
- Inter-song B (stacked): "Up next" on top, the rest as a row of cards. Drawn with the old
  corners and not updated.
- During-song 2 (minimal): one line top-right, a full-width progress line on the screen's bottom
  edge, key shown only after a change, next singer only near the end. Its key-only-on-change idea
  went into the compact card.
- The first compact card had no next line in the middle of the song (an opt-in setting); Ken's
  three-stage version replaced it.

## Decisions (Ken, 2026-11-25, on the TV)

Judged on the production TV (HDMI, 1920 x 1080, 60 Hz) with libmpv drawing the during-song
stages in ASS over playing library videos with their karaoke lyrics: Backstreet Boys "I Want It
That Way" (near 4:3), then Adele "Rolling in the Deep" and Britney Spears "Toxic" (16:9; Toxic
kept for its light and dark scenes). Where these differ from the 2026-11-23 decisions or the
canvas, these win.

1. **Draw everything in ASS** (`osd-overlay`); the QR stays the only bitmap. Icons are ASS vector
   drawings, not font glyphs: the fallback mic glyph (U+1F399) draws at about half the mock's
   icon size, while the mock's SVG mic redrawn as `\p1` paths matches it.
2. **Stage changes fade: 400 ms in 8 steps, as a crossfade.** Variants shown first: 150 / 250 /
   400 / 600 ms stepped every frame, 250 ms in 5 steps, 400 ms in 8 steps, and full-to-compact as
   an instant swap or a 250 / 400 ms crossfade. All looked smooth; 5 and 8 steps were barely
   distinguishable from every frame, so the length was the only real choice. Shown in place:
   song start (full card and NEXT line fade in), transition 1 (full card out, compact card and
   small Next line in), transition 2 (compact card stays, Next line out, up-next card in), song
   end (all out).
3. **Corner margin 16 px** for all four corner elements (QR, top-right box, clock, address), on
   both screens; was 40. Ken: overscan is turned off on every production TV. An edge ruler at
   0-40 px was put up to check overscan; Ken answered with that rule instead of a reading.
4. **Card backing 70% black** (was 60%) for the full card, its NEXT line, the compact card and the
   small Next line. The up-next card stays at 75%.
5. **Card padding trimmed** (vertical / horizontal, was in brackets): full card 12 / 16 (24 / 28),
   corners 14 (20), width 656 (680, same content width); NEXT line 8 / 16 (16 / 28), corners 12;
   tags 4 / 10 (6 / 14); compact card 6 top, 12 bottom (clears the 6 px strip), 12 sides
   (12 / 18 / 20), corners 10 (14); small Next line 3 / 10 (6 / 16), corners 8; up-next card
   12 / 16 inside its 3 px border (22 / 28), width 596 (620), corners 14; gap between stacked
   boxes 8 (14 / 10).
6. **Clock and address stay on pills, now 40% black** (was 60%), 12 px side padding, almost none
   top and bottom, corners 10. Tried against bare text with the lyrics' outline and shadow, and
   at 50% and 30%.
7. **Lato stays for the overlays.** Inter (`fonts-inter` 4.0) tried side by side on the same
   cards: "too heavy". Lato's digits are one width, so the ticking time doesn't shift; Inter's
   default digits are proportional, and its tabular set can't be switched on from ASS.
8. **Lyrics in Lato Bold 66**, was Arial 60 regular; outline (3 px black), shadow (2 px, 50%) and
   karaoke colours unchanged. Ken first called the Arial lyrics "very legible" and kept their
   outline-and-shadow approach, then asked to try Lato. Shown per pass on the same video: Arial 60,
   Lato 66, Lato Bold 66. Lato's lowercase is about 10% shorter per `\fs` than Arial's, so 66
   matches Arial 60's lowercase height. Applied at playback with mpv's
   `sub-ass-style-overrides=Karaoke.Fontname=Lato,Karaoke.Fontsize=66,Karaoke.Bold=-1` (takes
   effect live, no regeneration of `.ass` files); mpv also needs `sub-fonts-dir` pointing at Lato
   when it is not installed. No outline on overlay text: its contrast comes from the panels.
9. **SRT lyrics follow: Lato Bold.** Songs without a karaoke `.ass` use `SRT_STYLE` in
   `mpv_controller.py` (Arial 40 today). Same ratio as 60 to 66 gives Lato Bold 44; not yet seen on
   the TV.
10. **Lato is bundled in the repo**, not installed from apt: the Regular, Bold and Black files the
    screens use (400 / 700 / 900), with the SIL Open Font License text beside them, loaded with
    `osd-fonts-dir` and `sub-fonts-dir`. The folder is for the build plan to pick.

Test scripts (scratchpad, not kept): `stages_eyeball.py` drew the stages from the canvas's CSS
values; ASS `\fs` = CSS px x 1.20 for Lato, 1.21 for Inter. `\fnInter Black` and
`\fnLato Black` select Black by name.

## Decisions (Ken, 2026-11-25, settings)

1. **Corner margin becomes a preference.** One value for all four edges and all four corner
   elements (QR, top-right box, clock, address) on both screens, in px of the 1920 x 1080 canvas,
   default 16 (decision 3 above). Not multiplied by `overlay_scale`: it is about the TV's edge,
   not legibility. Recorded for the build plan; no change to today's overlays on `dev`.
   Not discussed: name, range, and whether the lyrics follow it (they have
   `subtitle_pos_offset`).

## Decisions (Ken, 2026-11-25, during-song behaviour)

Asked after the TV session; where these differ from earlier sections, these win.

1. **Pause brings back the full card** with a pause symbol and "Paused" in place of the elapsed
   time. If the last-30-s up-next card is up, it stays. On resume, crossfade back to the stage
   shown before the pause. Not discussed: whether the NEXT line comes back with the full card.
2. **The compact card shows neither key nor vocal level** (Ken: not needed for the whole song);
   this replaces its `Key +2` tag. A change to either brings a brief tag styled like the small
   Next line, holding both (`Key +2`, `Original Vocals 40%`) with the changed one highlighted.
   It sits on its own line under the compact card, above the Next line or up-next card, for
   about 4 s; each further change restarts the 4 s. While the full card is up its settings row
   updates in place and no tag shows. Not discussed: the highlight's look; single-stem songs
   have no vocal level, so the tag would hold the key alone.
3. **Stage timing:** the full card runs on playing time, pauses not counted; the up-next card on
   time left in the song, so seeking back out of the last 30 s takes it away.
4. **QR, clock and address stay visible for the whole song.**
5. **Song switches fade through black.** Song end: a full-screen black ASS layer fades in over
   the video over 1 s, under the corner elements (they stay up throughout); the video stops;
   the inter-song pieces fade in over 400 ms. At a natural end the fade starts 1 s before the
   last frame. A skip fades the same way, and the music fades out over the same 1 s. Song start
   mirrors it: inter-song pieces fade out (400 ms), the video fades in from black (1 s).
   Options not chosen: hard cut then fade in; a direct crossfade with no black moment.
6. **Empty queue:** the middle of the song is the compact card alone; no up-next card at the end.
7. **Same singer next:** the up-next card shows as normal.
8. **Songs too short for both the full card and the last 30 s** split their time evenly between
   the full card and the up-next card, with no compact stage.
9. **A queue change while the up-next card is up** crossfades it to the new singer and song.
10. **Long titles wrap only on the full card** (then cut off with an ellipsis); the compact
    card cuts off on one line. No scrolling.
11. **4:3 and cinematic videos:** no special placement. The corners stay 16 px in from the
    screen edges as on the inter-song screen, so on 4:3 the QR, clock and address fall wholly
    in the side bars and the top-right box partly.
12. **mpv's own controls:** already off. libmpv starts with `input-default-bindings=no` and
    `osc=no`; with the app's options the only live binding is the app's `f` fullscreen toggle
    (`input-bindings` read 2026-11-25: 194 default-section bindings, mouse included, all
    disabled). Ken keeps `f`. Seeks and volume from the phone are client-API commands and show
    no mpv OSD. Separately, `dev` `9c381e0b` opens the player fullscreen on the first
    non-primary monitor when there are two or more (`xrandr --listmonitors` order matches mpv's
    `screen` index on this box: 0 `eDP`, 1 `HDMI-A-0`), windowed otherwise.

## Decisions (Ken, 2026-11-25, the open points)

Answers to the points left open above; where these differ, these win.

1. **Plain black inter-song background** confirmed; `placeholder.png` goes.
2. **Progress and countdown bars in info blue `#3298dc`** confirmed.
3. **The inter-song countdown gets its own setting, which replaces `splash_delay`**, default
   8 s. `splash_delay` is today's wait between songs, and the countdown shows that wait, so one
   setting holds it; the CLI flag and the saved preference migrate. Its name is for the build
   plan.
4. **Pause brings back the NEXT line with the full card**, as at song start.
5. **The settings tag colours:** the unchanged setting in a neutral colour, the changed one in a
   brighter colour. Ken open to suggestions; this one agreed 2026-11-25: unchanged in
   the artist grey `#dbdee0` at about 70% (reads as quieter than the white-ish artist line),
   changed in amber `#f1b70e`, the screens' accent and the logo's vocals colour; colour only, no
   extra box or weight. Single-stem songs show the key alone.
6. **Corner margin preference:** range 0-40 px, default 16; the lyrics do not follow it (they
   keep `subtitle_pos_offset`). Name agreed 2026-11-25: `overlay_margin`, labelled "Overlay
   margin from screen edge (px)" in the Display section beside `overlay_scale`.
7. **`hide_now_playing_overlay` hides the during-song cards only** (full card, compact card,
   Next lines, up-next card, settings tag), for the most video; the inter-song screen keeps its
   "Up next" area and AFTER THAT panel.
8. **Rename** moved to `plans/open-issues.md` (decision 1 of 2026-11-23).
9. **SRT lyrics at Lato Bold 44 are fine if they render like the karaoke `.ass` lyrics.** They
   do, by mpv's units: `sub-font-size` and `sub-margin-y` are in pixels at a 720-line window, so
   44 and 100 draw as 66 and 150 on the `.ass` files' 1080 canvas; `#FFD700` is the karaoke sung
   colour (`&H00D7FF&`), and outline 3 and shadow 2 match. Only difference, as today: an SRT line
   has no word timing, so it is all gold, with no white not-yet-sung part. Still to see on the TV
   during the build.
10. **Lato goes in `pikaraoke/static/fonts/`**, beside `static/icons/`. That folder exists and
    holds `Arial.ttf` and `DroidSansFallback.ttf`, which nothing references: leftovers of the
    removed browser splash's CJK fix (`ba116f18`). Whether to delete them is for the build plan.

## Decisions (Ken, 2026-11-25, inter-song screen)

Asked after a look at what the screen's data needs; where these differ from earlier sections,
these win.

Wiring found (`dev` `89b14b33`): the idle list is `queue_manager.upcoming(5)`, which follows
play order and so never returns a held (download, processing, lyrics pick, failed) or paused
song: a held song's turn goes to its singer's next ready song, or it is passed over. The phone
Queue page instead lists `/get_queue` in queue order, numbers every row but a failed one, and
fades held and paused rows with their word in the slot. The overlay re-reads its data on every
poll tick, so queue changes need no event wiring. The between-songs wait in `Karaoke.run()`
counts loop steps, not clock time, and the overlay is not told it is running.

1. **AFTER THAT mirrors the phone Queue page:** queue order, held songs dashed with their word
   in the slot ("downloading", "processing", "lyrics"). "Up next" stays the song that actually
   plays next, and is left out of the list. As on the phone, when a held song's turn goes to a
   later song, the list shows the queue as it stands, not the exact play order.
2. **Paused songs show in the list**, faded with "paused" in the slot, as on the phone. No
   separate paused section (it would repeat names already in the list; revisit if several
   singers on a break read badly).
3. **Failed songs are hidden**, and not counted in "+ N more".
4. **Numbering starts at 2:** Up next is 1, so a guest's number matches the phone's.
5. **Songs queued but none ready:** no Up next song is named (whichever finishes first plays
   first) and no countdown runs; the left side reads "Getting the first song ready." and AFTER
   THAT lists the waiting songs. When every song left is paused (none downloading or being
   prepared, so none will get ready on its own) the message is "Every song in the queue is
   paused." instead; with both kinds waiting, the first message.
6. **The countdown restarts when the Up next song changes** (removed, paused, moved, a new
   song ahead of it), so the new singer gets the full wait. The list updates live throughout.
7. **No "start now" button.** The countdown setting (Decisions on the open points, item 3) can
   be set shorter.
8. **Countdown at zero: the song-start fade.** No "Starting…" text; the inter-song pieces fade
   out and the video fades in from black (during-song behaviour item 5). Videos load quickly.
9. **Long titles in Up next wrap** to two lines, then cut off with an ellipsis, as on the full
   card. A title with no artist part has no artist line.
10. **`overlay_scale` leaves the inter-song layout alone:** it scales the corner elements and the
    during-song cards only. Layout A fills the screen at fixed sizes and would not fit at 2x.
11. **Black placeholder** in place of `placeholder.png`, the same 1344 x 768, so the windowed
    player (no TV connected) opens at today's size; mpv sizes a window to the file it shows. On
    the TV the window is fullscreen and the size does not matter.
12. **Text stays English for now** (the phone pages are translated, the TV never was). Logged in
    `plans/open-issues.md` on `dev` (`bf11d9c5`, Future features).

13. **Empty queue with `hide_url` on:** "The queue is empty. Add a song from your phone." (no
    QR or address to point at; the alternative, "The queue is empty." alone, not chosen).

## Decisions (Ken, 2026-11-25, settings change mid-song)

Replaces the separate tag in during-song behaviour item 2 (and the colour-only look in the open
points item 5, for this case).

1. **A key or vocal change grows the compact card** by a settings row like the full card's:
   `Key +2` and `Original Vocals 40%` tags, under the artist and time line, the changed one in
   amber `#f1b70e`, the other in `#dbdee0` at about 70%. After 4 s the row goes and the card
   shrinks back; each further change restarts the 4 s. Ken asked for the grow and shrink as a
   transition, not a separate line appearing. Single-stem songs show the key alone. While the
   full card is up its own row updates in place, as before.

Made in the mock, not yet confirmed: the tags at 26 px (the compact card's artist is 28 px) on
the full card's tag boxes; the grow and shrink over 400 ms in stepped resends, like the stage
crossfades; whatever sits under the card (small Next line or up-next card) shifts down with it
while the row is up, against the keep-movement-down preference.

## Made in the mock, not yet confirmed by Ken

- Plain black inter-song background; `placeholder.png` goes. Confirmed 2026-11-25.
- Lato on the TV (the phone UI's font). Confirmed 2026-11-25, bundled in the repo.
- Progress and countdown bars in info blue `#3298dc`: the remote's `#375a7f` is too dark over
  video. Confirmed 2026-11-25.
- The countdown would run on `splash_delay`, whose default of 2 s is too short to read a countdown.
  Ruled 2026-11-25: its own setting, replacing `splash_delay`, default 8 s.
- The compact card drops the vocal-level tag; Key shows only when changed. Superseded
  2026-11-25: the compact card shows neither; a brief tag shows both on a change.
- The lyrics' own style is untouched; the amber sung words in the mock are a stand-in. Superseded
  2026-11-25: lyrics change font to Lato Bold, colours and outline untouched.
- 60% black backing for every during-song box; 75% for the last-30-s card. Superseded
  2026-11-25: cards 70%, clock and address pills 40%.
- Long titles: on the full card the title wraps to two lines, then cuts off with an ellipsis; on
  the compact card it cuts off on one line. Singer names are capped in width (260 / 220 px) so a
  long title can't push them out. No scrolling text: recommended against (moving text over video,
  and the compact card would loop for minutes); Ken asked, did not rule. A single scroll on the
  full card only is the fallback if wrapping isn't enough. By filename, about 200 of 248 songs
  overflow one compact line and about 60 overflow two full-card lines. Confirmed 2026-11-25:
  wrap on the full card, cut off on the compact card, no scrolling.
- On 4:3 videos the QR sits wholly in the left side bar and the card partly in the right: the
  corners could be placed in the bars for 4:3. Ruled 2026-11-25: no special placement.
- From the 2026-11-25 canvas rebuild:
  - With no Up next song (none ready, or all paused) the panel heading reads `IN THE QUEUE`,
    not `AFTER THAT`, and its rows number from 1, as on the phone.
  - Held and paused rows fade the singer and song to 40%, as the phone does; the slot (dashed,
    number and word) stays full strength.
  - Paused in the last 30 s: the full card with the up-next card under it, and no NEXT line,
    which would repeat the up-next card.
  - Lyrics drawn at CSS 55 px (ASS 66 at the 1.2 ratio) in the karaoke gold `#FFD700` with
    white for words not yet sung, replacing the amber stand-in.

## mpv feature check (production Linux box, 2026-11-25)

Method: libmpv opened with `mpv_controller.start()`'s OSD options in a minimized 1920 x 1080
window on the laptop panel, captured with `screenshot-raw window` over the library frames in
`screens-canvas/backgrounds/`. Lato came from the `fonts-lato` .deb, unpacked to a folder, not
installed. Probe scripts lived in the session scratchpad and were not kept.

Stack: libmpv 0.42.0 (`libmpv2 0.42.0-0ubuntu1~ubuntu2404`), libass 0.17.1, python-mpv 1.0.8,
Pillow 12.1.1 (FreeType 2.14.1, raqm), numpy 2.4.4. VO `gpu-next` on `x11egl` (mpv's default; the
app sets none). The `mpv` CLI is not installed (package removed, config left); the app does not
use it.

| Check | Result |
| --- | --- |
| Lato installed | No. `fonts-lato` 2.015 is in apt (18 weights). Loaded from a folder via `osd-fonts-dir`, it renders; with no `\fn` the OSD falls back to a different sans, silently. |
| Lato weights in ASS | `\fnLato` + `\b1` = Bold. `\fnLato\b900` also gives Bold (same width as `\b1`). `\fnLato Black` and `\fnLato Heavy` select by name. |
| ASS size vs CSS px | `\fs` = CSS px x 1.2 for Lato (1.193-1.197 measured: 35-char string, `\fs100` vs Pillow at 100 px). |
| `osd-overlay` args | `id format data res_x res_y z hidden compute_bounds` |
| `z` | z=1 draws over z=0 whatever the id order. |
| `compute_bounds` | With `hidden=yes` it returns `x0 y0 x1 y1` without drawing: a text measurer for ellipsis and wrapping. Pillow's width / 1.2 lands within 0.6% of it. |
| ASS rounded panels | `\p1` drawing with bezier corners: antialiased. 60% black = `\1a&H66&`. |
| ASS progress strip | `\clip(<drawing>)` clips a 6 px strip to the card's rounded bottom corners. |
| ASS animation | `\fad`, `\t`, `\move` are frozen at time 0 inside `osd-overlay`: `\fad(400,0)` text never appears. A fade is resending with stepped `\alpha`: 0.33 ms per resend of the full card. |
| Icons via ASS | libass falls back per glyph to system fonts: U+1F399 mic, U+25B6, U+23ED, U+1F550 draw in one colour; U+1F3A4 mic is a missing-glyph box. |
| Icons via Pillow + Lato | No fallback: every icon is a box. Icons would be drawn as shapes. |
| `overlay-add` args | `id x y file offset fmt w h stride dw dh video_colorspace max_luma primaries transfer`. Ids 0-63; 64 is refused. |
| `bgra` alpha | Read as premultiplied: stored (128,0,0,128) over gray 128 shows (192,64,64). |
| `&<address>` source | Copied at the call: zeroing the buffer after `overlay-add` changes nothing on screen. No temp file needed (the QR writes one today). |
| Bitmap vs ASS stacking | Bitmaps always draw over ASS overlays, whatever `z` (an ASS rect at z=100 sat under a bitmap). ASS text on a bitmap panel is not possible. |
| `dw`/`dh` | Scales the bitmap. A half-size text card shown at 2x is visibly soft. |
| Pillow shapes | `rounded_rectangle` at 1x has stepped corners; drawn at 4x and downscaled (LANCZOS) they are smooth. |
| Bitmap cost | Full card in Pillow: 9 ms (1x), 36 ms (4x shapes). One fade step on a 680 x 200 card (numpy alpha scale + `overlay-add`): 5 ms. `overlay-add` of a prebuilt 1920 x 1080 bitmap: 4.4 ms. |
| Colour on screen | Identical for both routes, a few levels off the hex: `#3298dc` shows (53,151,219), `#1abc9c` (32,187,155). |
| Bare idle window | `screenshot-raw` refuses with no file loaded, so overlays there were not captured. Over a loaded still (how `placeholder.png` is shown today) both routes draw. |
| Not tested | Output above 1080p. (Stepped fades on the TV: tested later the same day, see Decisions 2026-11-25.) |

## Open for the build plan

- **Data the screens need that `QueuedSong` lacks:** artist (separate from title), processing
  state for the dashed slot, and more rows (A shows up to 5 after "up next", so 6 in all;
  `upcoming(5)` gives 5). Also, per Decisions 2026-11-25 (inter-song screen): the rows in
  queue order with held and paused songs (which `upcoming()` never returns), the count for
  "+ N more", and the countdown's end time, which the overlay is not given today.
- **Box widths across the switch:** inter-song panel 620, full card 656, compact card at most
  560. The box changes width twice. Accepted for now; could match if the jump shows.
- **Existing display preferences against the new screens** (state at `442269f6`, unchanged on
  `dev` `d3f3bf66`):
  - `overlay_scale` (0.5-3, Display section, "including QR code"): today scales `_qr_height`,
    every font is a third of it and row offsets derive from the font size, all flush to the edges.
    The new cards are fixed px (padding, corners, widths, singer caps, 6 px strip, pill padding):
    each needs multiplying, and the ellipsis / wrap measuring must measure at the scaled size. At
    2x the full card is about 1312 px wide; the 3x maximum may need lowering or the cards capping.
  - Size basis: `_qr_height` keys off `screen_h`, but ASS overlays draw on a fixed 1920 x 1080
    canvas mpv scales to the window, while the QR bitmap (`overlay-add`) is in screen px. Away
    from 1080p text and QR fall out of proportion (at 2160p text is 2x relative to QR and
    screen). The new screens should size in canvas units and scale only the QR bitmap by
    `screen_h / 1080`.
  - `subtitle_scale` / `subtitle_pos_offset` (`sub-scale`, `sub-pos`, with `sub-ass-override`
    `scale` for karaoke): expected to compose with the Lato Bold 66 `sub-ass-style-overrides`;
    not checked on the TV. Karaoke lyrics are bottom-centre (`\an2`), `MarginV` 150, margins
    50 / 50 (`pipeline/config.py`), and stacked lines grow upward: a negative offset (min -50)
    lowers them toward the bottom-corner pills; a large positive one (max 100 = `sub-pos` 0, top)
    lifts them under the QR and the top-right box.
  - `hide_clock` -> clock pill; `hide_url` -> QR and address pill. `hide_now_playing_overlay`
    hides the during-song cards only (ruled 2026-11-25; today it also hides the idle queue list).
  - `hide_notifications` is phone-only (Socket.IO); its UI label still says "splash screen".
