# TV screens: inter-song screen, during-song overlay, logo

Model: Claude Opus 5.5 (design record 2026-11-23 to 25; build spec 2026-11-26). Executor:
Claude Sonnet 5.5, Phases 1-5 of the build spec.

Branch `tv_screens`, off `dev` at `442269f6`, rebased 2026-11-26 onto `dev` `efb91f2d` (plan
commits only). Worktree on the VM: `.claude/worktrees/tv_screens`. **Executors: read "Build
spec" (near the end) first.** It is the build target; the sections before it are the decision
log it was built from, and where they differ the build spec wins.

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

Made in the mock, confirmed 2026-11-26: the tags at 26 px (the compact card's artist is 28 px)
on the full card's tag boxes; the grow and shrink over 400 ms in stepped resends, like the stage
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

## Open for the build plan (each settled in the build spec below)

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

## Build spec (Claude Opus 5.5, 2026-11-26)

Executor: Claude Sonnet 5.5, Phases 1-5, one phase per session. Stop after each phase's Results
row so Ken can `/compact`. Phase 6 is Ken's, at the TV.

This section is the build target. Every ruling above is already in it; where it and the decision
log differ, this section wins. For every size, padding, gap, corner radius and colour not
repeated here, use the board sources in `plans/tv-screens/screens-canvas/`: `Main.dc.html`
(inter-song), `Empty.dc.html` (empty queue) and `DuringCards.dc.html` (during song). They already
carry the 2026-11-25 TV-session values. Canvas CSS px map 1:1 to the 1920 x 1080 ASS canvas.

### Rulings (Ken, 2026-11-26)

1. The settings-row mock is confirmed: tags at 26 px, the card grows and shrinks over 400 ms in
   stepped resends, and whatever sits under the compact card shifts down with it.
2. The box widths stay: inter-song panel 620 px, full card 656 px, compact card at most 560 px.
3. `overlay_scale`: the plan decides how the cards stay on screen at large scales (item 3
   below).

### Decided by this plan

Ken can overrule any of these at Phase 6. Each is one constant or one rule.

1. The full card shows for the first **15 s** of playing time (the record says 15-20 s).
2. The countdown setting is **`song_countdown`**: default 8 s, range 0-99, labelled "Countdown
   before the next song (seconds)" in the Queue section where `splash_delay` was. On the command
   line it is `-s` / `--song-countdown`, and `--splash-delay` stays as another name for the same
   flag. On the first start after the change, a saved `splash_delay` is copied to
   `song_countdown` (unless that is already set) and then removed. A saved 2 stays 2.
3. **`overlay_scale` runs 0.5-2** (was 0.5-3). At 2 the full card is 1312 px wide and still fits
   beside the QR; at 3 it is wider than the screen. A saved value above 2 reads as 2.
4. `static/fonts/Arial.ttf` and `DroidSansFallback.ttf` are deleted (nothing references them).
5. The play clock that times the full card restarts on Restart. Seeking does not move it.
6. Text widths are measured with Pillow and the bundled Lato files. East Asian wide characters
   (CJK, Hangul, most emoji) count as one em each, because libass draws them from a fallback
   font. Phase 2 checks this against libass's own measurement.
7. The key tag reads `Key 0` when the key is unchanged, otherwise `Key +2` or `Key -1`.
   Single-stem songs have no vocal tag.
8. Each AFTER THAT row keeps its phone number (its place among the queue's non-failed songs),
   and the Up next song's row is left out. Usually the list starts at 2. When a held song's turn
   has gone to a later song, the numbers can skip one.
9. When the up-next card has to move (a pause in the last 30 s puts the full card above it), it
   crossfades to its new place instead of jumping.
10. The compact card's settings row shows for any change in the last 4 s, including one made
    while the full card was up.
11. The `.ass` files keep `Arial,60` in their style line. At playback the override draws them in
    Lato Bold 66 (TV-session ruling 8). `pipeline/config.py` does not change.
12. TV text is written in plain English in the code, without `_()` (inter-song ruling 12).
13. The up-next card cuts the singer's name short before it cuts ", you're up next".

### The code today (read 2026-11-26 at `dev` `efb91f2d`)

- `lib/overlay_manager.py`: `OverlayState` -> `compute_overlays()` -> one `Overlay` per OSD id
  (6 ids) -> diffed against what was last sent -> `osd_overlay`/`clear_osd`. The QR is a
  bitmap in overlay slot 0 at (0, 0): `send_qr_bitmap(px)` writes a temp file and calls
  `overlay-add`. Every size comes from `_qr_height` = `max(120, screen_h // 6) × overlay_scale`.
- What triggers a render (`MpvController.tick_overlays`): `_on_time_pos` at most every 0.5 s
  while `time-pos` moves (`on_tick`); `_on_osd_dim` (`invalidate()` + `on_resize`);
  `play_file`; `end_song`; `refresh_overlays()`, called by the preference route for
  `_OVERLAY_PREFS` (`routes/preferences.py:23`) and by `Karaoke.rename_singer`.
- `PlaybackController.build_overlay_state()` reads five preferences with `get_or_default`, and
  each read re-reads `config.ini`. It does not take `_playback_lock`, which `play_file` holds
  through the whole load.
- `karaoke.py:326-334` wires the provider; `_get_queue_preview` is `upcoming(5)` mapped to
  `QueuedSong(title, singer)`.
- `Karaoke.run()` (`karaoke.py:704-731`): when a song can play, it calls `reset_now_playing()`,
  waits `splash_delay` by counting 500 ms loop steps, then runs `pop_next()` and `play_file()`.
- `QueueManager.upcoming(n)` follows play order (`_take_next`), so it never returns a held,
  paused or failed song. The phone Queue page (`templates/queue.html`) lists `/get_queue` in
  queue order. Its slot words are `downloading`, `processing`, `lyrics` (for `pick`) and
  `paused`, and a waiting word beats paused. It numbers every row except a failed one
  (`place++` skips failed). `/get_queue` splits titles with `split_title`, which returns
  `("", title)` when it can't find an artist.
- `skip()` has two callers: the `/skip` route, and `queue_clear`'s `skip_requested` event. No
  page sends the Socket.IO `end_song` event (`routes/socket_events.py:34`).
- Only `mpv_controller.py` references `static/images/placeholder.png`. Nothing references
  `static/fonts/*`.
- The karaoke `.ass` style is named `Karaoke` (`pipeline/stages/lyric_align.py:1251`);
  `font_size` is 60 (`pipeline/config.py:295`).
- `splash_delay` appears in `preference_manager.py` (DEFAULTS), `args.py` (`-s/--splash-delay`),
  `app.py:174`, `karaoke.py` (parameter, docstring, run loop), `routes/info.py:75`,
  `templates/info.html:369` and the tests (`test_preference_manager.py`, which uses it as its
  example int setting throughout; `test_info_routes.py`; `test_karaoke_singer_playback.py`).
  The `overlay_scale` input is at `info.html:352` (`max="3"`).
- VM: the libmpv is 0.42.0, the same as production, and `DISPLAY=:10.0` (the RDP desktop). A
  minimized 1920 x 1080 libmpv window renders OSD text and `screenshot-to-file <path> window`
  captures it; CJK text falls back per glyph to Noto CJK. Both checked 2026-11-26. The
  `ui-check` skill runs mpv with `vo=null`, so it has no picture.

### Design

#### Modules

The new package is `pikaraoke/lib/tv/`:

| Module | Holds | Phase |
| --- | --- | --- |
| `fonts.py` | `FONTS_DIR` (`static/fonts`), the three Lato files by weight, the `\fn` names | 1 |
| `draw.py` | pure ASS helpers: colours, alpha, escaping, text events, rounded rects, rings, dashed rects, clipped strips, the mic, pause and logo drawings | 2 |
| `text_fit.py` | `text_width`, `fit` (one line, ellipsis), `wrap` (n lines, last one ellipsized) | 2 |
| `screens.py` | `Layer`, `Frame`, `compute_layers(state)`; the corners, and the black layer (Phase 5) | 2 |
| `timeline.py` | `TvTimeline`: countdown, play clock, settings change, starting and ending | 3-5 |
| `queue_view.py` | the pure `queue_view(items, up_next)` -> `QueueView` | 3 |
| `inter_song.py` | the inter-song and empty-queue layers | 3 |
| `during_song.py` | the stage rules and the cards' layers | 4 |

`overlay_manager.py` keeps `OverlayState`, `ScreenMode` and `OverlayManager`. `OverlayManager`
becomes the render thread and the animator. Its old builders go in Phases 2-4.

#### Render loop (Phase 2)

- `OverlayManager` runs one daemon thread. Each frame: build the state with the provider, run
  `compute_layers(state)` to get `Frame(layers, animating)`, have the animator turn that into
  one ASS string, and send it as `osd-overlay` id 1 only when it differs from what was last
  sent (clear the overlay when the string is empty). Then do the QR.
- Cadence: 50 ms while the animator or the frame is animating, 250 ms otherwise. `wake()`
  renders at once. `tick_overlays()` keeps its name and now only wakes the thread, so
  `play_file`, `end_song`, the preference route and `rename_singer` still render at once.
- One OSD id holds everything. The order of events inside the string is the stacking order,
  because libass draws later events over earlier ones, so no z ids are needed. The QR stays a
  bitmap, and mpv always draws bitmaps over ASS.
- The provider runs on this thread. It must not take `_playback_lock`; it may take the queue
  lock.
- `_on_time_pos` keeps updating `position` but no longer triggers a render. `set_callbacks`
  loses `on_tick` and `on_resize`: the thread covers both, and `_on_osd_dim` calls
  `invalidate()`, which also wakes the thread.
- `MpvController.start()` starts the thread once the player exists. `quit()` stops and joins
  it before shutting the player down.
- When a frame raises, log it with `log.exception` (a repeat of the same message only once)
  and keep looping.
- `render_frame()` is a plain method, so tests drive frames with a fake clock and never start
  the thread.

#### Layers and fades (Phase 2)

```python
@dataclass(frozen=True)
class Layer:
    key: str                            # identity: a new key fades in, a vanished one fades out
    z: int                              # 0 black, 1 screens and cards, 2 corners
    draw: Callable[[float], list[str]]  # opacity 0-1 -> ASS events
    fade_s: float = FADE_S              # 0.4; 0 = appears and goes at once
```

- The animator keeps one opacity ramp per key (from, to, start time). A key that appears ramps
  from 0 to 1. A key that disappears keeps its last `draw`, ramps to 0, and is then dropped. A
  key that comes back mid-fade ramps up from wherever it is. Opacity moves in 50 ms steps
  (`round(fade_s / 0.05)` steps, so 8 for 400 ms), and a fade resends 8 times.
- A crossfade is two keys: the old one fades out while the new one fades in. So the key carries
  whatever should crossfade when it changes: the stage (`full`, `compact`), the next song's
  identity (`upnext:<file>:<singer>`), and where a box sits (`...:under-full`). Everything else
  (time, list rows, progress, the settings row) updates in place under the same key.
- Output order: by `z`, then by place in the latest list. A fading-out layer keeps its last
  place.
- `draw` multiplies its own alphas by the opacity it is given: a 70% black panel drawn at
  opacity 0.5 comes out at 35%.
- `Frame.animating` is True while a countdown runs, while the settings row is growing or
  shrinking, while the black layer is between 0 and 1, and while a song has under 1.5 s left.
  The animator adds its own "a fade is running".

#### State

`OverlayState` (frozen) grows over the phases. Its final shape:

- `mode`, `screen_h`, `server_url`, `hide_url`, `hide_now_playing`, `hide_clock`
- `overlay_scale` (clamped to 0.5-2), `overlay_margin` (clamped to 0-40), `song_countdown`
- `now` (monotonic) and `clock_text` ("9:42 PM"), so `compute_layers` stays pure
- `song: NowSong | None`: song and artist (`split_title` of the title), singer, semitones,
  dual_stem, vocal_volume, position, duration
- `queue: QueueView`
- `timeline: TimelineSnapshot`

The old fields (`now_playing_title`, `queue_preview`, `singer_name` and the rest) go with the
old builders in Phases 3-4, and `QueuedSong` goes in Phase 4.

#### Text (Phase 2)

- Every text event looks like `{\an7\pos(x,y)\q2\fn<name>\b<0|1>\fs<size>\fsp<ls>\bord0\shad0\c<colour>\1a<alpha>}text`.
  `\q2` stops libass from wrapping lines. `\bord0\shad0` override mpv's OSD style, because
  overlay text has no outline (TV-session ruling 8). Weights: Black is `\fnLato Black\b0`, Bold
  `\fnLato\b1`, Regular `\fnLato\b0`.
- Sizes are the boards' CSS px, and `\fs` = px x 1.2 (Lato's line box, measured 2026-11-25).
  With `\an7`, a line whose CSS line-height is L goes at `line top + (L − 1.2) × px / 2`.
- Escape every user string with `_ass_escape`, moved to `draw.py`. Extend it to turn `\n` and
  `\r` into spaces: one osd-overlay string holds one event per line, so a newline in a singer's
  name would start a new event.
- `text_width(text, px, weight)`: Pillow's `ImageFont.truetype(<Lato file>, px).getlength()`
  for runs of narrow characters, plus `px` for each character whose
  `unicodedata.east_asian_width` is `W` or `F`. Cache the results.
- `fit(text, max_w, ...)` returns the text, or else the longest start of it plus `…` that fits.
  `wrap(text, max_w, lines, ...)` breaks at spaces and between wide characters, and the last
  line `fit`s whatever is left. A word longer than a whole line is cut with `…`.
- When `overlay_scale` is not 1, measure at the scaled size.

#### Drawing (Phase 2)

- Panels: one `\p1` event per shape, with `\an7\pos(x,y)` and `\bord0\shad0`, filled through
  `\c` and `\1a`, with bezier corners (k = 0.5523 × r).
- Borders (the up-next card's 3 px green): draw a ring, the outer rounded rect plus the inner
  one wound the other way. Don't use `\bord`: libass fills the outline as a whole shape under
  the fill, which tints a see-through fill. A CSS border sits inside the box.
- Dashed slots (held rows): dashes about 6 px long with 5 px gaps along the straight edges, and
  solid corners. This doesn't match the CSS exactly; Ken judges it on the TV.
- Progress strip: a strip rect with `\clip(<the card's rounded-rect drawing>)`, so it follows
  the bottom corners (worked on production 2026-11-25).
- Icons come from the boards' SVGs (viewBox 24, scaled). Mic: a capsule ring (rect 9,2,6x12,
  rx 3), the lower half of a circle at (12,10) with radius 7, and a stem from (12,17) to
  (12,22). Each 2.2-wide stroke becomes a filled outline with round caps. Pause: two rounded
  rects. Logo bars: from `Empty.dc.html` (5 bars) and `Main.dc.html` (4 bars), viewBox 200.
  Never use font glyphs for icons (TV-session ruling 1).

#### Timeline (Phases 3-5)

`TvTimeline(clock=time.monotonic)` is owned by `PlaybackController` as `timeline`. It holds a
lock, and `snapshot()` returns a frozen `TimelineSnapshot` with the times already turned into
seconds and progress.

| Call | Called by | Phase |
| --- | --- | --- |
| `start_countdown(key, seconds)`, `clear_countdown()` | run loop | 3 |
| `song_started()` | `play_file`, after `mpv.play` returns | 4 |
| `paused()`, `resumed()` | `PlaybackController.pause`, by the state it ends in | 4 |
| `restarted()` | `PlaybackController.restart` | 4 |
| `setting_changed("key" or "vocals")` | `set_pitch`, `set_vocal_volume` | 4 |
| `song_cleared()` | `end_song`, and a start that fails | 4 |
| `song_starting()` | run loop, when the countdown runs out | 5 |
| `song_ending()` -> bool (False when already ending) | `skip` | 5 |

Snapshot fields: `countdown_key`, `countdown_left`, `countdown_s`; `play_s` (playing seconds,
pauses not counted, reset by `song_started` and `restarted`); `started` and `since_start`;
`row_progress` (0-1, stepped) and `row_changed`; `starting`; `since_ending` (None when not
ending).

Settings row: `setting_changed` keeps the row's current progress p, setting
`shown_since = now − p × 0.4` and `hold_until = now + 4.0`. The row grows over 0.4 s from
`shown_since`, holds until `hold_until`, then shrinks over 0.4 s. A change during the shrink
grows the row back from where it is.

### The screens

#### Corners (both screens, Phase 2)

All four sit `overlay_margin` px in from the edges (default 16, not scaled). Their sizes scale
with `overlay_scale`. They never fade at a song switch.

- QR: bitmap, top-left, 180 x `overlay_scale` canvas px square. The bitmap overlay works in
  screen px, so multiply size and position by `screen_h / 1080` (the 120 px floor goes).
  `hide_url` hides it.
- Clock: a bottom-left pill. "9:42 PM" in Bold 52 white, line-height 1.15, on 40% black with
  padding 0 / 12 and corner radius 10. `hide_clock` hides it.
- Address: a bottom-right pill. "Add a song" in Bold 34 white, a 14 px gap, then the URL in
  Regular 34 teal `#1abc9c`, line-height 1.2, on 40% black with padding 2 / 12 and corner
  radius 10. `hide_url` hides it.

#### Inter-song screen (Phase 3; `Main.dc.html`, `Empty.dc.html`)

On the black placeholder. `overlay_scale` and `hide_now_playing_overlay` leave it alone.

- **Up next** (when a song is next, `upcoming(1)`): a column centred vertically in the box from
  x 88 to 1204 and y 260 to 930, with 28 px gaps:
  - `UP NEXT` in Bold 36, letter-spacing 6, `#b5bfc0`.
  - A mic icon (104 px), a 28 px gap, then the singer in Black 150 green `#2ecc71` on one line,
    cut short with `…`.
  - The song title in Bold 76 amber `#f1b70e`, line-height 1.1, wrapping to two lines and then
    cut short. Then, 10 px below, the artist in Regular 52 `#dbdee0` on one line (no artist
    line when there is no artist).
  - The countdown row, 24 px further down: a bar (14 px tall, corner radius 7, track
    `#282f2f`, filled in `#3298dc` from the left by the share of time gone), a 28 px gap, then
    "Starts in 0:08" in Bold 40 `#b5bfc0` (seconds left rounded up, as m:ss). If the countdown
    isn't running for this song yet (the run loop polls every 0.5 s), the bar is empty and the
    text shows `song_countdown`.
  - Key: `inter:upnext:<file>:<singer>`, so a change of song crossfades.
- **Waiting message** (no song is next, but the queue has songs that haven't failed): in the
  same box, Bold 76 white, line-height 1.15. It reads "Getting the first song ready." when any
  of those songs is held and not paused, else "Every song in the queue is paused." Key:
  `inter:wait:<message>`.
- **Panel**: top-right at the margin, 620 px wide, bottom edge at y 930, padding 32, corner
  radius 20, fill `#1f2424`, 26 px gaps:
  - The heading `AFTER THAT` (`IN THE QUEUE` when no song is next) in Bold 28, letter-spacing
    5, `#b5bfc0`.
  - Up to 5 rows. A row has an 80 x 80 slot with corner radius 14. A ready slot is filled
    `#282f2f` with its number in Black 38 white. A held or paused slot has no fill, a 2 px
    dashed `#8c9b9d` border, its number in Black 38 `#b5bfc0`, and its word 4 px under it in
    Regular 14. Then a 22 px gap and a text column: the singer in Black 44 green, line-height
    1.1, and under it "song · artist" (just the song when there's no artist) in Regular 30
    `#dbdee0`, line-height 1.2, each on one line cut short with `…`. On held and paused rows
    the text column is at 40% opacity; the slot stays at full strength.
  - "+ N more in the queue" in Regular 28 `#b5bfc0`, at the panel's bottom.
  - The panel is one key and its rows update in place.
- **Footer logo**: bottom centre, 20 px up. The 4-bar icon at 52 px, a 14 px gap, then the
  wordmark in Black 38, letter-spacing −1, with `gpu` in amber and `karaoke` in white. Not on
  the empty screen.
- **Empty queue** (no songs that haven't failed): a column centred in the box from y 200 to
  930, with 40 px gaps: the 5-bar logo at 240 px, the wordmark in Black 120 with
  letter-spacing −3, then the message in Regular 48 `#dbdee0`: "The queue is empty. Scan the
  code to add a song.", or "The queue is empty. Add a song from your phone." when `hide_url`
  is on.
- `queue_view`: rows are the queue's non-failed songs in queue order, numbered by their place
  among the non-failed songs, with the Up next song's row taken out. It shows the first 5, and
  `more` counts the rest. The words are `downloading` / `processing` / `lyrics`, else `paused`.

#### During song (Phase 4; `DuringCards.dc.html`)

Top-right at the margin. Every size is multiplied by `overlay_scale`. Boxes are stacked with an
8 px gap and right-aligned.

- **Full card**: 656 px wide, padding 12 / 16, corner radius 14, 70% black.
  - Line 1: the title (Black 44 amber, line-height 1.2, wrapping to two lines, then cut short)
    and, 24 px to its right, the singer block: a 34 px mic, a 10 px gap, then the name in Black
    40 green, at most 260 px wide, cut short with `…`, top-aligned.
  - Then the artist (Regular 34 `#dbdee0`, line-height 1.2, one line, cut short), 4 px below.
  - 12 px below that, the settings row. On the left are tags (Bold 28 white, padding 4 / 10,
    corner radius 10, 14% white fill, 10 px apart): `Key +2`, plus `Original Vocals 40%` for
    dual-stem songs. On the right is the time, "1:42 / 5:55", in Regular 30 `#dbdee0`. While
    paused, the time is replaced by a 24 px pause icon, a 10 px gap and "Paused" in Bold 30
    white.
- **NEXT line**, under the full card and as wide: padding 8 / 16, corner radius 12, 70% black.
  `NEXT` in Bold 24, letter-spacing 4, `#b5bfc0`, then the singer in Black 34 green, then the
  song in Regular 30 `#dbdee0` cut short, with 16 px gaps and baselines aligned.
- **Compact card**: as wide as its content, between 420 and 560 px. Padding 6 at the top, 12 at
  the bottom and 12 at the sides; corner radius 10; 70% black.
  - Line 1: the title (Black 36 amber, one line, cut short), a 20 px gap, a 28 px mic, a 10 px
    gap, then the singer (Black 34 green, at most 220 px).
  - Line 2, 2 px below: the artist (Regular 28 `#dbdee0`, cut short) on the left and the time
    (Regular 28 `#dbdee0`, with 6 px of padding before it) on the right. With no artist, the
    time stands alone on the right.
  - A 6 px progress strip runs along the card's bottom edge: a 18% white track, filled in
    `#3298dc` up to position / duration, and clipped to the rounded bottom corners.
- **Settings row on the compact card** (Phase 4, commit 2): 6 px under line 2, the full card's
  tags at 26 px. The tag that changed is amber `#f1b70e`; the other is `#dbdee0` at 70%. The
  row's height and its tags' opacity follow `row_progress`. The card's bottom edge (and so the
  strip, and every box below it) moves with it.
- **Small Next line**, under the compact card: at most 560 px wide, padding 3 / 10, corner
  radius 8, 70% black, 28 px with line-height 1.2, on one line cut short with `…`. It reads
  "Next " (`#b5bfc0`), the singer (Black green), " · " and the song (`#dbdee0`).
- **Up-next card**: 596 px wide, a 3 px green border inside the box, padding 12 / 16, corner
  radius 14, 75% black, 6 px gaps. "<singer>, you're up next" in Black 46 green (only the name
  is cut short). Then the song in Bold 32 amber, followed by " · <artist>" in Regular 32
  `#dbdee0` (just the song when there's no artist), on one line cut short.

Which boxes show is a pure function of the state:

- `full_s = 15` and `up_s = 30`; when the duration is under 45 s, both are duration / 2.
- Full card: when paused, or when `play_s < full_s`. Compact card: otherwise.
- Up-next card: when a song is next and the time left is at most `up_s`.
- NEXT line: with the full card, when a song is next and the up-next card is not up.
- Small Next line: with the compact card, under the same condition.
- `hide_now_playing_overlay` hides all of these; the corners stay.
- Cards only show once the song has started (`timeline.started`). In Phase 5, they also go
  while the song is ending or in its last 1 s.
- Keys: `full`, `compact`, `next:<id>`, `smallnext:<id>`, `upnext:<id>:<under full|compact>`.
  A new key crossfades over 400 ms in 8 steps.
- Text: "Key +2" style as in Decided item 7; vocals as `round(vocal_volume × 100)`; time as
  m:ss / m:ss.

#### Song switches (Phase 5)

- **Black layer**: a full-screen black rect, `z` 0 (under the cards and corners; the QR bitmap
  is always on top), `fade_s` 0. Its opacity comes from the state and moves in 50 ms steps:
  - natural end: `1 − time_left` over the last 1 s, when the duration is known;
  - skip: `since_ending / 1.0`;
  - song start: 1 from `song_starting()` until `song_started()`, then `1 − since_start / 1.0`.
  - It is listed whenever `starting` or `since_ending` is set, whatever the mode. At other times
    it shows only while a song plays and is in its first or last 1 s, so it isn't on the
    inter-song screen, which sits on the black placeholder.
  - `end_song` calls `timeline.song_cleared()` after `load_placeholder()`. After a skip the
    black layer stays up until then: `reset_now_playing()` switches the mode to idle before the
    placeholder replaces the video, and without the black layer a video frame could flash in
    that gap.
- **Skip**: `skip()` returns at once. If `timeline.song_ending()` is False (already ending),
  it does nothing more. Otherwise a short-lived thread steps mpv's `volume` property (a new
  `MpvController.set_player_volume`, kept apart from `set_system_volume`) from 100
  to 0 in 20 steps over 1 s, then runs `end_song("skip")` under `_playback_lock`. `end_song`'s
  existing `is_playing` guard covers a natural end that lands in between. `MpvController.play`
  sets `volume` back to 100 before `loadfile`. The master volume is the system mixer, so mpv's
  own `volume` is otherwise always 100.
- **Natural end**: no music fade. The cards go when 1 s is left, the black layer fades in, the
  video ends, `end_song` runs, and the inter-song pieces fade in (400 ms).
- **Song start**: when the countdown runs out, the run loop calls `timeline.song_starting()`,
  the inter-song layers stop being listed (so they fade out over 400 ms) and the black layer
  is drawn opaque. The run loop sleeps 0.4 s, then calls `pop_next()` and `play_file()`.
  `play_file` calls `timeline.song_started()`, after which the video fades in from black over
  1 s and the full card and NEXT line fade in. If `pop_next()` returns None or the play fails,
  `timeline.song_cleared()` brings the inter-song screen back.
- The Socket.IO `end_song` handler keeps ending at once (no page sends it).

### Settings (Phases 2-3)

- `overlay_margin` (Phase 2): an int in DEFAULTS, default 16. A number input in the Display
  section after `overlay_scale`: `min="0" max="40" step="1"`, labelled "Overlay margin from
  screen edge (px)", with a `{# MSG: ... #}` comment. Add it to `_OVERLAY_PREFS` and pass it
  from `routes/info.py`.
- `overlay_scale` (Phase 2): the input's `max` becomes 2, and the state builder clamps the value
  to 0.5-2.
- `song_countdown` (Phase 3): replaces `splash_delay` in every place listed under "The code
  today", with the default, flag and migration from Decided item 2. The migration is
  `PreferenceManager.migrate_splash_delay()`, called in `Karaoke.__init__` straight after
  `scaffold_hidden_settings()`. No `.po` updates (as on earlier branches).

### Accepted edges

1. At `overlay_scale` 2, the QR (360 px) can overlap the Up next singer line, because the
   inter-song layout has fixed sizes.
2. If a file's duration is longer than its real end, the natural-end fade stops short of black.
3. If the next song changes during the 0.4 s start fade, the song that plays is the new next
   one, under a name that already faded out.
4. A Restart during a skip's fade doesn't stop the skip.
5. CJK widths are estimated (Decided item 6); a few px of overrun into a card's padding is
   possible.
6. A held song is never named as Next during a song, because only `upcoming()` songs are.
7. The provider re-reads `config.ini` on every frame (up to 20 a second during animations).
   That's cheap, and the cache it would need isn't worth it.

### Phases

Every commit: tests ride with their code; use real `EventSystem` and `PreferenceManager`
instances. Before each commit, run the full suite
(`/home/ken/miniconda3/envs/pik/bin/python -m pytest`), then pre-commit on the changed files,
then read `git diff --cached` against this spec. Delete what each commit replaces, tests
included.

**Screenshots** go to `/home/ken/pikaraoke/.claude/tv-shots/phase<N>/` (local, gitignored),
named after the canvas board they match. Take them with a scratchpad harness that subclasses
`mpv.MPV` the way `ui-check`'s `run_app.py` does, adding `window_minimized=True` and
`geometry="1920x1080"`. Drive the real `MpvController` and `OverlayManager`, and save with
`screenshot-to-file <path> window`. For the during-song shots, load the stills in
`screens-canvas/backgrounds/` (16:9, 4:3, cinematic) as the video. Read every shot back, and
note in the Results anything that differs from its board beyond font hinting.

#### Phase 1: Lato and the lyrics (1 commit)

`feat(tv): bundle Lato and draw the lyrics in Lato Bold`

- Run `apt download fonts-lato` (2.015) into the scratchpad and unpack it with
  `dpkg-deb -x`. Copy `Lato-Regular.ttf`, `Lato-Bold.ttf` and `Lato-Black.ttf` to
  `pikaraoke/static/fonts/`, and put the SIL OFL 1.1 text with Lato's copyright line from the
  package's copyright file into `static/fonts/OFL.txt`. Delete `Arial.ttf` and
  `DroidSansFallback.ttf`.
- `lib/tv/__init__.py` (empty) and `lib/tv/fonts.py`: `FONTS_DIR`, the files by weight, and the
  names `Lato` and `Lato Black`.
- `MpvController.start()`: pass `osd_fonts_dir=FONTS_DIR`, `sub_fonts_dir=FONTS_DIR` and
  `sub_ass_style_overrides="Karaoke.Fontname=Lato,Karaoke.Fontsize=66,Karaoke.Bold=-1"` to the
  constructor. `SRT_STYLE`: `sub-font` Lato, `sub-font-size` 44, `sub-bold` yes.
- Tests: the constructor gets the three options; the `SRT_STYLE` values; the three font files
  exist.
- VM checks, recorded in the Results:
  1. Shots (harness, `play()` with the real sub paths, seek to a sung line, pause) of a karaoke
     song with Latin lyrics, a karaoke song in Chinese or Korean, and a song in SRT mode. The
     library is `/home/ken/shared-drives/D:/Shared/pikaraoke-songs` (`karaoke/*.ass`,
     `subtitles/*.srt`).
  2. Using `osd-overlay` with `hidden=yes compute_bounds=yes`, compare the widths of
     "Hamburgefonstiv" under `\fnLato\b0`, `\fnLato\b1`, `\fnLato Black\b0` and a font name
     that doesn't exist. All four must differ, which proves the bundled files load.
- **Stop** and report, without committing, if the lyrics aren't in Lato or the CJK lyrics lose
  their glyphs.
- The commit stands alone, so Ken can copy it to `dev` early if he wants the lyrics sooner.

#### Phase 2: drawing kit, render thread, corners (2 commits)

1. `feat(tv): an ASS drawing kit and a text measurer for the TV screens`: `draw.py` and
   `text_fit.py` with their tests (colour and alpha, escaping including newlines,
   rounded-rect, ring and dash paths, opacity multiplying, the width rule, fit, wrap with CJK
   and an over-long word). Nothing is wired in yet.
2. `feat(tv): one render thread draws the TV overlay with stepped fades; new corners`: the
   render loop, `Layer`/`Frame`/animator, `screens.compute_layers` with the three corners, the
   QR at the margin in canvas units, `overlay_margin`, `overlay_scale` 0.5-2, and the callback
   cleanup. The URL and clock builders are deleted. The idle list, now-playing, timecode and
   up-next builders stay, joined into one `legacy` layer (`z` 1, `fade_s` 0) until Phases 3-4.
   Tests:
   - A 400 ms fade gives exactly 8 distinct strings, then stops resending.
   - A key change crossfades; a fading-out layer is dropped after its fade; a key that returns
     mid-fade ramps from where it was.
   - The fast cadence is on only while something is animating.
   - Corner positions at margins 0, 16 and 40 and scales 1 and 2; the QR's bitmap size and
     position at `screen_h` 1080 and 2160.
   - `hide_url` and `hide_clock`.
   - The preference route refreshes for `overlay_margin`.

VM checks:

1. Measurer against libass: at least 150 titles from the library's file names (including every
   CJK one), each at Black 36 and Regular 30. Tabulate the `text_width` against the
   `compute_bounds` width (x1 − x0). Record the max and the mean difference in px, split into
   CJK and the rest.
2. Shots of the corners on the black placeholder and over each still, at scales 1 and 2,
   margins 0 / 16 / 40, and with `hide_url` and `hide_clock`.
3. The CPU of the process on an idle inter-song screen over 30 s (`ps -o %cpu`).

**Stop** and report if any title is under-measured by more than 8 px at Black 36. That decides
whether the measurer switches to `compute_bounds`, which is Opus's call.

A `/code-review` is due after Phase 2 (a new render thread). The session writes the line at its
checkpoint.

#### Phase 3: the inter-song screen (2 commits)

1. `feat(tv): the countdown before each song replaces splash_delay and restarts when the next
   song changes`: `song_countdown` with the flag and the migration, `timeline.py` (countdown
   part), and `Karaoke._count_down()`. In a loop that sleeps 0.1 s, it keys the next song by
   `(file, user)` from `upcoming(1)`, restarts the deadline when the key changes, publishes it
   with `start_countdown`, returns False (and clears) when nothing can play or the app stops,
   and returns True when time runs out. `run()` calls it in place of the `splash_delay` loop.
   Tests: the restart on a change, the countdown at 0, the queue emptying mid-countdown (fake
   clock and sleep), the migration (value carried, key removed, an existing `song_countdown`
   kept), and the CLI alias.
2. `feat(tv): the inter-song screen: up next with its countdown, the queue as on the phone, the
   empty screen`: `queue_view.py`, `inter_song.py`, the logo drawings, and a black 1344 x 768
   `placeholder.png` in place of the image. The provider adds `queue` (built under the queue
   lock from a copy of the items plus `upcoming(1)`), the timeline snapshot and
   `song_countdown`. Delete the idle list builder, `OSD_QUEUE_PREVIEW` and their tests.
   Tests for `queue_view` (numbering, Up next left out, failed hidden and not counted, words,
   the two waiting messages, the empty queue, `more`) and the inter-song layers (which keys show
   for each state, heading text, countdown text and bar share, the `hide_url` message, wrap and
   cut on long names).

VM checks: add a window mode to `ui-check`'s `run_app.py` (local and gitignored). When
`UI_CHECK_MPV_IPC=<socket path>` is set, it keeps a real minimized 1920 x 1080 window with
`input-ipc-server=<socket>` instead of `vo=null` (still `ao=null`); with the variable unset,
nothing changes. Launch from this worktree on an unusual port with `FAKE_JOB_S=20`, drive the
queue over HTTP, and take shots through the socket (`screenshot-to-file`). Record each:

1. Empty queue, and the same with `hide_url` (`Empty`, `EmptyNoUrl`).
2. Songs added while still processing: "Getting the first song ready." with dashed rows
   (`InterPreparing`).
3. The first song becomes ready: Up next with a countdown, and a second shot 3 s later shows
   the bar has moved (`InterShort`, `Main`).
4. Pause the Up next song (the queue's pause route): the next song takes over Up next and the
   countdown restarts (two shots, 2 s apart, plus the log).
5. Every song paused: "Every song in the queue is paused." (`InterAllPaused`).
6. Long names (a singer of 30+ characters, a title over two lines) and 7+ songs, so the panel
   shows "+ N more" (`InterLong`).
7. `song_countdown` set to 3 on the Settings page: the next countdown runs 3 s.

#### Phase 4: the during-song cards (2 commits)

1. `feat(tv): during-song cards in three stages`: the timeline's play clock (`song_started`,
   `paused`, `resumed`, `restarted`, `song_cleared`) wired into `PlaybackController`, and
   `during_song.py` with the stage rules, pause, short songs, the hide setting and long titles.
   Delete the legacy layer and everything only it used: the old builders, `Overlay`,
   `render_ass`, `_OVERLAY_STYLE`, the old colours and icons, `_qr_height`,
   `_overlay_font_size`, `QueuedSong`, `_get_queue_preview` and the old `OverlayState` fields,
   along with their tests.
   Tests:
   - A stage table over (play_s, time_left, duration, paused, next song or none, hidden),
     covering every bullet of "Which boxes show".
   - The play clock not counting pauses, and resetting on restart.
   - Keys that change at each transition, and the up-next card's key changing when a pause
     puts the full card above it.
   - The time text and the Paused swap.
   - Single-stem: no vocal tag.
   - No card before `started`.
2. `feat(tv): a key or vocal change grows the compact card by a settings row for 4 s`:
   `setting_changed`, `row_progress`, the row on the compact card, and the boxes below
   following it. Tests: progress over time (grow, hold, shrink); a second change during the hold
   (holds longer) and during the shrink (grows back from where it was); highlight colours; the
   full card's row updating in place with no highlight.

VM checks: hand-built states in the harness over the three stills, one shot per board:
`DuringCards`, `DuringCardsMid`, `DuringCardsEnd`, `DuringHidden`, `DuringPaused`,
`DuringPausedEnd`, `DuringSettingKey`, `DuringSettingVocals`, `DuringQueueEmpty`,
`DuringLongTitle` and `DuringLongTitleMid`. Then one pass in the real app (window mode, real
library songs):

1. A song starts with the full card, and a shot at 20 s shows the compact card.
2. `/seek` to 40 s before the end: the up-next card shows. `/seek` back: it goes.
3. `/pause`: the full card with Paused. Resume: back to compact.
4. `/transpose/2` mid-song: the row grows. Shots at 1 s and at 5 s (gone).

A `/code-review` of Phases 3-4 is due after Phase 4.

#### Phase 5: songs fade through black (1 commit)

`feat(tv): songs fade through black at the end and the start; a skip fades the music`: the
black layer, `song_starting`/`song_ending`, the skip thread with `set_player_volume`,
the volume reset in `play()`, and the run loop's start sequence. Tests:

- Black opacity in each case (natural end, skip, start before and after `started`), stepped.
- The skip thread's 20 volume steps, then `end_song` (fake sleep).
- A second skip while ending does nothing; a natural end during the fade ends the song once.
- `play()` resets the volume.
- A `pop_next()` that returns None during the start fade brings the inter-song screen back.

VM checks:

1. Audio: with `ao=pcm` to a wav in the scratchpad and the app's dual-stem filter graph on a
   library song, step `volume` from 100 to 0 mid-song. Record the RMS of the wav in 100 ms
   windows. **Stop** and report if the level doesn't fall by at least 40 dB: then the music fade
   needs a different route, which is Opus's call.
2. App, window mode: `/skip` mid-song, with shots at about 0.5 s (black partly in, cards gone)
   and at 1.5 s (inter-song screen). Seek to 3 s before the end and shoot the last second.
   Shoot a song start just after the countdown runs out (black, corners only) and at 0.5 s.

A `/code-review` of Phase 5 is due after it.

#### Phase 6: Ken at the TV

On the production box, from this branch. Record each finding as a ruling in this file.

1. Lyrics in Lato Bold over 16:9 and 4:3 songs, and a song in SRT mode (the first SRT look on
   the TV).
2. Corners at 16 px: the QR scans, the pills read well, `overlay_margin` changes live.
3. Inter-song: Up next and the countdown, held and paused rows, the dashed slots, "+ N more",
   the footer logo, the empty screen.
4. During song: full to compact to up-next, pause and resume, a key change (the row), a long
   title, the hide setting, a short song.
5. Song end, skip (and its music fade), song start.
6. A quick look at `overlay_scale` 2.
7. Settings: the countdown's value after the migration (set it to 8 if it carried a 2). Then
   Decided items 1, 7 and 13, which are the ones most likely to read differently on the TV.

## Results log

(Executor: one entry per phase, with the commit hashes, suite count, pre-commit, each VM check's
outcome with screenshot paths and raw numbers, and anything that departed from this spec and
why. No verdicts on the stop rules; report the numbers and stop.)
