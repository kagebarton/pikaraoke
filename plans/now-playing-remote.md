Model: Claude Opus 5.5 (author, 2026-11-17). Executor: Claude Sonnet 5.5. Rulings 6 and 9 and
the Design's colours amended by Claude Opus 5.5 on 2026-11-18 from the phone pages' style
review, marked (L5), (L15) and (L16).

# Now Playing as a remote

## Goal

Now Playing reads like a TV remote: three big text buttons, big sliders with the value on the
knob and filled −/+ buttons at the ends, and only the controls a singer needs. The seek bar,
master volume and subtitle delay become the admin's. A guest's key stops at −3/+3. The guest
form's Original vocals and Key use the same control, so a setting looks the same everywhere.

Mockup (agreed with Ken 2026-11-17): https://claude.ai/artifact/1vCot5F227mmHnqpKBLaN5 (three
screens: current singer, admin, guest form). Visual reference since 2026-11-18: the canvas
https://claude.ai/artifact/RLxbcwiEeprw1MfaspcMkL (private to Ken), boards "Now Playing:
current singer", "Now Playing: admin", "Your singer settings (tap your name)" and "Reference
palette". For colours and buttons it wins over the mockup; this file wins over both.

Base: `dev` at `e1ac8adf`, which has `singer_defaults` landed (2026-11-21, tag
`archive/singer_defaults`). It owns the "Original vocals" name, the (i) notes, the guest form,
`KEY_LIMIT`, and the L1/L15/L16 colours in `bulma-dark.css`. Branch `now_playing_remote`, worktree
`.claude/worktrees/now_playing_remote`, rebased 2026-11-21 from the old branch (which sat on
`singer_defaults`' unlanded commits); only this plan's two commits carried over. The old
`origin/now_playing_remote` (`254bec0`) is superseded.

## Rulings (Ken, 2026-11-17)

1. **Admin only:** seek bar, master Volume, Subtitle delay. Everyone else who sees the controls
   (the current singer) gets Restart / Pause / Skip, Original vocals, Key and Lyrics.
2. **Key:** guests −3 to +3 (`KEY_LIMIT`), the admin keeps −12 to +12.
3. **No server-side refusal.** Hiding is enough: deployments always set an admin password.
4. **The name stays "Original vocals"** (singer_defaults Phase 4).
5. **One shared control** for every slider: Now Playing's four and the guest form's two.
6. **Transport:** three equal text buttons, Restart | Pause | Skip, all the same neutral grey. No
   button is highlighted. (L5) Grey because on every page green means a tap that queues and
   blue a chosen option; the earlier reason, "on this page the green fill already means
   chosen", goes.
7. **Pause reads "Resume" while paused** (a button names what a tap does), and a "Paused" tag
   shows beside the "Now Playing" heading.
8. **Confirm texts:** Restart asks "Restart this song?", Skip asks "Skip this song?". Skip's old
   "If you didn't add this song, ask permission first!" goes: only the singer and the admin see
   Skip now.
9. (L5) **The chosen lyric style, the knob and the fill are blue `#375a7f`, with white text.**
   This replaces "the green is Bulma's success green, the same as singer names and Save", which
   rested on a wrong fact: Save is `is-success`, `#2ecc71`, not `--bulma-success`. The "(mint)"
   comment in `home.html` still goes (it was wrong: `--bulma-success-dark-invert` resolves to
   the same 53% lightness as `--bulma-success`).
10. ~~Branch off `singer_defaults`~~ `singer_defaults` has landed; this branch is off `dev`.

## Rulings (Ken, 2026-11-18): one look

From the style review across the seven phone-page branches (`plans/open-issues.md` on `dev`,
"Phone pages: one look"; numbers are that list's, prefixed L). L5 changes rulings 6 and 9
above. Also:

11. (L5) **Song titles are amber `#f1b70e`.** They are `has-text-warning` (`#now-playing`,
    `#up-next`), which L1 points at `#f1b70e` (`singer_defaults` Phase 5); nothing to build
    here beyond checking it.
12. (L5) **The app's blue nav bar stays.** The mockup drew a grey one; it is not built.
13. (L15) **Grey buttons are filled `#434d4e`**, one step above the `#343c3d` card: the
    transport and the steppers' −/+.
14. (L16) **Disabled, whatever its colour:** no fill, a faded border (`#5e6d6f` at half
    strength), a `#8c9b9d` label, no opacity fade. A stepper's −/+ at its end is drawn so.

Not ruled (L5): the mockup's near-black control panel (not in this spec) and the 12-14 px
corners (in it). The spec stands until Ken rules.

## What the code does today (read 2026-11-17 at `13b96f2`; re-checked 2026-11-21 at `e1ac8adf`)

- `templates/home.html`: one `.control-box`, shown to the admin or the current singer
  (`handleNowPlaying`, `Cookies.get("user") === np.now_playing_user`); everyone else sees only
  the song and Next Song. Inside: an h4 "Player Control"; the seek bar; icon links for restart,
  play/pause and skip (`#restart`, `#pause-resume` toggling `icon-play`/`icon-pause`, `#skip`);
  the master volume range (0 to 1, `input` debounced 500 ms to `/volume/<v>`) between
  `#vol-down`/`#vol-up` icons that call `/vol_down` and `/vol_up`; then sections split by `<hr>`:
  Original vocals (dual-stem only, 0-100, `stepVocalVolume(±10)`), Change Key (−12..12,
  `stepPitch(±1)`, label from `getSemitonesLabel`, an `<a id="semitones-info">` notification),
  Lyrics (Karaoke/Subtitles/Off), Subtitle Delay (srt mode only, −5..5 s,
  `stepSubtitleDelay(±0.1)`, an `<a id="subtitle-delay-info">` notification). Each slider sends on
  `change` through `debounceStep(fn, key)`.
- The page script's `$(function)` binds the seek bar with no null check
  (`seekBar.addEventListener`), so the seek bar can't simply be left out of the markup.
- Next Song already shows a mic icon by the next singer (`handleNowPlaying`, `#up-next`). Nothing
  to add there; the mockup only lacked it at first.
- `routes/home.py` passes `admin=is_admin()`, `is_transpose_enabled`, `volume`, and
  `transpose_value`, which no template reads.
- `is_admin()` (`lib/current_app.py`) is true for everyone when no admin password is set.
- The routes (`routes/controller.py`) check nobody's role.
- Guest form (`templates/base.html` `#singer-modal`, handlers in `static/spa-navigation.js`):
  Original vocals is a plain range with a `%` label; Key is a hidden `#singer-key` with `-`/`+`
  buttons and a label, clamped in JS by `setSingerKey` to `singerFormKeyLimit`
  (`state.key_limit`). `saveSingerForm` reads `#singer-key` and `#singer-vocal-volume` by id.
- `getSemitonesLabel` (`base.html`) has two users: Now Playing's key label and the form's key
  label. Both go in this plan.
- `/vol_up`, `/vol_down` and `Karaoke.vol_up`/`vol_down` have one user: Now Playing's volume
  icons. Tests: `tests/unit/test_karaoke_utils.py` (two classes), `tests/conftest.py` lines
  binding them.
- `static/custom.css`: `.control-box a`, `.control-box i[onclick]`, `#vol-up`, `#vol-down` (and
  their hover block) colour the icon links; `--controls-link-color`/`--controls-link-hover` (the
  "(mint)" line) are defined in `home.html`. `--controls-header-size` and `--controls-icon-size`
  are defined there and read nowhere. `--button-selected-bg` (selected lyric button) is
  `var(--bulma-success-dark-invert)`.
- Re-check 2026-11-21: everything above still holds at `e1ac8adf`. The only `dev` changes since
  are the name pill and burger in `base.html` (`a31de3bb`), which this plan does not touch. The
  seek bar's `$(function)` binding (the null check) is still unguarded; the other two uses are
  guarded. `info_tip()`, `original_vocals_tip()` and `lyrics_tip()` live in `info_tip.html` and
  `singer_tips.html`; no `key_tip()` exists yet.
- `tests/unit/test_search_render.py` renders `base.html` without the singer blueprint, so
  `singer` can be undefined in `base.html` (it already guards with `singer or {}`).
- No test renders `home.html`.

## Design

### The shared control: `stepper`

Three new files, loaded the way the (i) notes are (`info_tip.html`, `info-tip.js`,
`info-tip.css`): `base.html` loads `stepper.js` and `stepper.css` on every page, once.

**`templates/stepper.html`**: one macro, `stepper(id, min, max, value, step=1, tap=1,
format="percent", labelled_by="")`:

```html
<div class="stepper{% if min < 0 %} has-zero{% endif %}" role="group"
     aria-labelledby="{{ labelled_by }}" data-tap="{{ tap }}" data-format="{{ format }}">
  <button type="button" class="stepper-btn" data-dir="-1" aria-label="{{ _('Lower') }}">−</button>
  <div class="stepper-track">
    <span class="stepper-fill"></span>
    <span class="stepper-knob" aria-hidden="true"></span>
    <input type="range" class="stepper-range" id="{{ id }}" min="{{ min }}" max="{{ max }}"
           step="{{ step }}" value="{{ value }}" aria-labelledby="{{ labelled_by }}">
  </div>
  <button type="button" class="stepper-btn" data-dir="1" aria-label="{{ _('Raise') }}">+</button>
</div>
```

The heading above it (label and (i) note) stays the page's own markup, with an `id` passed as
`labelled_by`.

**`static/stepper.js`**: delegated on `document`, bound once (like `info-tip.js`):

- A tap on `.stepper-btn` moves its range by `dir × tap`, clamped to min/max and rounded to the
  step's decimals. If the value changed, it repaints and fires bubbling `input` and `change`
  events on the range, so a page's own handlers treat a tap like a drag.
- `input` on `.stepper-range` repaints (dragging).
- `window.stepperSet(input, value)`: set from the server or a form, then repaint. It fires no
  events, so a page's send handler never echoes a server push back. It does nothing for a
  `null` input, because the admin-only steppers don't exist on a guest's page.
- The repaint sets `--frac` (where the value sits, 0..1), `--zero` (where 0 sits, clamped to
  0..1), and `--lo`/`--hi` (the fill's ends, between 0 and the value) on the `.stepper`. It
  writes the knob text and disables the −/+ button at its end.
- Knob text by `data-format`: `percent` → `40%`; `semitones` → `+2`, `0`, `-1`; `seconds` →
  `+0.5 s`, `0 s`, `-0.3 s`.

**`static/stepper.css`**, sizes as in the mockup:

- **−/+ buttons:** 56 px square, 14 px radius, filled `--dark-bg-raised` (L15), glyph
  `--dark-text-primary` 34 px bold. Disabled (L16): no fill, a `--dark-border` border at half
  strength, glyph `--dark-text-muted` (`#8c9b9d`), full opacity. Use `singer_defaults`' L16
  rule if it covers these buttons, else the same values once in `stepper.css`.
- **Rail:** 10 px, `--dark-bg-tertiary`. **Fill:** `--dark-primary` (L5) at 0.5 opacity, from
  `--lo` to `--hi`.
- **Zero tick:** `.has-zero` only, a 2 px tick at `--zero`.
- **Knob:** 68 × 44 px pill, `--dark-primary` (L5), text `--dark-text-primary` (white) 18 px
  heavy. Left edge at `calc((100% - 68px) * var(--frac))`, with `pointer-events: none`.
- **Range:** covers the track, `appearance: none`, transparent. Its native thumb is transparent
  and 68 × 48 px, so a drag grabs exactly where the knob is drawn (`::-webkit-slider-thumb`,
  `::-moz-range-thumb`, both tracks transparent).
- **Focus:** `:focus-visible` outlines the range.

The knob sizes live once in `stepper.css` as `--knob-w` (68 px), so the knob and thumb can't
drift apart.

### Now Playing (`templates/home.html`, `routes/home.py`)

Top to bottom inside `.control-box`. Sections are separated by spacing, with no `<hr>` rules
and no "Player Control" heading:

1. **Seek bar** (`{% if admin %}`), as today. Its `$(function)` binding gets a null check.
2. **Transport:** a 3-column grid of `<button type="button">`: `#restart` "Restart",
   `#pause-resume` "Pause"/"Resume", `#skip` "Skip". Each is 64 px tall, 12 px radius,
   `--dark-bg-raised` (L15; the canvas draws no border) with white 20 px bold text, and has no
   hover tint on touch (match
   `custom.css`'s `@media (hover: hover)` rule). `handleNowPlaying` sets the pause button's text
   from `np.is_paused`, and a tap flips it at once (optimistic, as today). The two labels come
   from Jinja into the script.
3. **Volume** (`{% if admin %}`): heading "Volume", stepper `volume-slider`, 0..100, tap 10,
   `percent`. Sends on `input`, debounced 500 ms, to `/volume/<v / 100>` (live while dragging,
   as today). The server push syncs it with `stepperSet(..., Math.round(np.volume * 100))`.
   The `var volume` compare goes.
4. **Original vocals** (dual-stem only, as today): heading plus `original_vocals_tip()`, stepper
   `vocal-volume-slider`, 0..100, tap 10.
5. **Key** (`{% if is_transpose_enabled %}`): heading "Key" plus `key_tip()`, a new macro in
   `singer_tips.html` beside `original_vocals_tip()` and `lyrics_tip()` (commit 1 adds it, with a
   `{# MSG: ... #}` comment): "Moves the song up or down in half-steps. 0 is the original
   key." The guest form uses the same macro (commit 4), so the two say the same thing.
   Stepper `transpose`, `-key_limit..key_limit`, tap 1, `semitones`. `routes/home.py` passes
   `key_limit=ADMIN_KEY_LIMIT if admin else KEY_LIMIT`, and drops `transpose_value`.
   `ADMIN_KEY_LIMIT = 12` sits beside `KEY_LIMIT` in `lib/singers.py`, commented as the admin's
   live change on Now Playing.
6. **Lyrics:** unchanged.
7. **Subtitle delay** (`{% if admin %}`, shown in srt mode as today): heading "Subtitle delay"
   plus an (i) note: "Below 0 the lines show earlier, above 0 later." Stepper
   `subtitle-delay-slider`, −5..5, step 0.1, tap 0.1, `seconds`.

Sliders 4, 5 and 7 send on `change` through `debounceStep`, as today. A tap fires `change` too,
so rapid taps still merge into one request. `handleNowPlaying` syncs every stepper through
`stepperSet`.

**Paused tag:** a Bulma `tag is-medium` with the id `paused-tag` and the text "Paused", in the
header `h1` after the playing gif. Shown to everyone while a song is paused
(`np.now_playing && np.is_paused`), hidden otherwise. The gif stays.

**Confirms:** Restart `{{ _('Restart this song?') }}` (today's text was untranslated), Skip
`{{ _('Skip this song?') }}`.

**Deleted:** `stepPitch`, `stepVocalVolume`, `stepSubtitleDelay`, `formatSubtitleDelay`,
`togglePausePlayButton`, the slider label `oninput` handlers, the `#semitones-info` and
`#subtitle-delay-info` notification handlers, the value labels in the section headings (the
knob shows the value now), `#vol-up`/`#vol-down`, and `var volume`. In the `:root` block:
`--controls-header-size`, `--controls-icon-size`, `--controls-link-color` and
`--controls-link-hover` (the "(mint)" line). In `custom.css`: the `.control-box a` /
`i[onclick]` / `#vol-up` / `#vol-down` rules and their hover block. Also `/vol_up`,
`/vol_down`, `Karaoke.vol_up`, `Karaoke.vol_down`, their tests and conftest lines, and the
`vol_up/down` mention in `Karaoke.volume_change`'s docstring.

**Changed (L5):** `--button-selected-bg` becomes `var(--dark-primary)` and
`--button-selected-text` becomes `var(--dark-text-primary)`, so the chosen lyric style is blue
with white text. `.subtitle-mode-btn.is-selected` is shared, so this turns the guest form's
chosen lyric style blue too.

### The guest form (`templates/base.html`, `static/spa-navigation.js`)

- **Original vocals:** the heading and its tip stay. Stepper `singer-vocal-volume`, 0..100,
  tap 10, `percent`. The `%` label and its `input.singer` handler go.
- **Key:** the label "Key" stays, now followed by `key_tip()` like Original vocals' label
  (closes the open-issues entry "The join form's Key has no (i)"). Stepper `singer-key`, `-limit..limit`, tap 1, `semitones`,
  where `limit` is the guest state's `key_limit`, read with the same guard as
  `window.singer` (`test_search_render.py` renders without `singer`). `#singer-key-field`
  still hides when transpose is off.
- **Deleted:** the hidden `#singer-key`, the `-`/`+` buttons and `#singer-key-label`,
  `setSingerKey`, `singerFormKeyLimit` and the key-up/down handlers.
- `openSingerForm` sets both through `stepperSet`. `saveSingerForm` and the 410 path are
  unchanged: they read and pass the same ids.
- `getSemitonesLabel` (`base.html`) is deleted: no users left.

Every new string gets a `{# MSG: ... #}` comment, as the branch does. No `.po` updates
(`singer_defaults` added its strings without them).

### Accepted edges

1. **Hiding isn't enforcement.** Any phone can still call `/seek`, `/volume`,
   `/subtitle_delay` or `/transpose/<n>` past ±3 directly. Ruled acceptable (ruling 3).
2. **No admin password means everyone is admin** and sees every control (existing
   `is_admin()` behaviour).
3. **A key the admin set past ±3 shows as ±3 on the singer's phone.** The browser clamps the
   range, and the singer's next tap lands inside ±3. The admin rarely sets a guest's key that
   far, and the singer's phone corrects on the next push.
4. **The name pill's place is not this branch's.** `dev` `a31de3bb` moved it beside the burger;
   this plan does not touch the navbar.

## Phases

### Phase 1: build (Sonnet)

Four commits, in this order. Tests ride with their code. Before each commit run the full
suite, then pre-commit on the changed files, then `git diff --cached` against this plan.

1. `feat(ui): Now Playing's sliders become steppers with the value on the knob`. The three
   `stepper` files, `base.html` loading them, and `key_tip()` in `singer_tips.html`. Now
   Playing's Volume, Original vocals, Key
   (still −12..12 for everyone in this commit) and Subtitle delay. The dead CSS and variables,
   the `--button-selected-bg` change (L5), and the `vol_up`/`vol_down` removal with their
   tests.
2. `feat(ui): Now Playing's transport is three text buttons; Pause reads Resume while paused`.
   The transport grid, the Paused tag and the confirm texts.
3. `feat(ui): the seek bar, volume and subtitle delay are the admin's; a guest's key stops at
   ±3`. The `{% if admin %}` blocks, the seek null check, `key_limit` from the route,
   `ADMIN_KEY_LIMIT`, and the new `tests/unit/test_home_page.py`. Pattern:
   `test_singer_page.py`, with a real `SingerRegistry` and `PreferenceManager`, an admin
   password set, and stub endpoints. Cases:
   - admin cookie: seek bar, volume and subtitle delay present, key `max="12"`;
   - no cookie: none of the three, key `max="3"`;
   - transpose disabled: no key stepper;
   - no admin password: the admin page.
4. `feat(ui): the guest form's Original vocals and Key use the stepper`. `base.html`,
   `spa-navigation.js`, the `getSemitonesLabel` removal, and `key_tip()` after the form's Key label.

Then **ui-check** (local skill), launched from this worktree (`launch.sh PORT WORKDIR
<worktree>`, `FAKE_JOB_S=5`) with an admin password set in the instance's config. Use two
browser contexts, one with the admin cookie and one guest who queued the playing song. Record
each outcome in the Results log, with screenshots of the three views at 390 px width. Expect
fake jobs to give no dual-stem song, so Original vocals may be hidden; say so rather than
forcing it.

1. **Guest view:** transport, Key and Lyrics only. No seek bar, Volume or Subtitle delay.
2. **Key taps:** + three times shows `+3` on the knob and disables +, and one `/transpose/3`
   request follows (requests seen through Playwright).
3. **Key drag:** dragging moves the knob and sends on release.
4. **Pause:** the button reads "Resume" and the Paused tag shows, also on a third context that
   isn't the singer. Resume turns both back.
5. **Confirms:** Restart and Skip show the new texts (Playwright dialog handler; dismiss them).
6. **Admin view:** seek bar, Volume (− sends `/volume/0.7` from 80%), Key to `+12`, Subtitles
   mode shows Subtitle delay, and + there sends `/subtitle_delay/0.1`.
7. **Guest form:** opened from the navbar name, the two steppers show the saved values. Change
   both, Save, reopen: the new values show.
8. **Navigation:** away to Queue and back twice, then one tap is one step (no stacked
   handlers), with no page errors.
9. **Width:** no horizontal scroll at 360 px and 390 px on Now Playing and the form.
10. **Colours (L5, L15, L16), computed:** the knob, the fill and the chosen lyric button are
    `#375a7f` with white text, on Now Playing and the form; the transport and an enabled −/+
    are `#434d4e`; Key's + at `+3` has a transparent background, a `#8c9b9d` glyph and opacity
    1; the song title is `#f1b70e`.

A `/code-review` is due after Phase 1. The session writes the line at the checkpoint.

### Phase 2: Ken's checks

On a phone, at a real dual-stem song: the size and feel of the buttons and knob, Original
vocals, the guest form, and the admin's view from the host's phone.

## Results log

(Executor: one row per phase: commit hashes, test counts, the ui-check outcome per check,
anything that deviated from this plan and why.)
