Model: Claude Opus 4.7

# Port Remaining Prototype Features

## Goal

Port the remaining playback features from the `mpv/` prototype into the main
PiKaraoke app. These build on the python-mpv migration (commit `128dc33`) and
the +/- step-button work (commit `847441f`). Each feature is independently
shippable; they are ordered so later features can build on earlier scaffolding.

## Feature Summary

| # | Feature | New UI? | New route? | Touches MPV? | Depends on |
|---|---|---|---|---|---|
| 1 | Dual-stem playback | — | — | yes | — |
| 2 | Vocal volume control | yes | yes | yes | 1 |
| 3 | Karaoke (.ass) subtitle support + mode toggle | yes | yes | yes | — |
| 4 | Volume normalization (deferred — placeholder only) | — | — | — | — |
| 5 | "Vocals: NN%" in timecode overlay | — | — | yes | 2 |
| 6 | Seek bar in now-playing UI | yes | yes | yes | — |
| 7 | Per-song reset of vocal volume | — | — | — | 2 |

______________________________________________________________________

## 1. Dual-stem (vocal/nonvocal) playback

### What & why

`ProcessingManager` already produces `<song>---vocal.m4a` and
`<song>---nonvocal.m4a` under `vocal/` and `nonvocal/` siblings of the source
file (see [\_stem_output_paths()](pikaraoke/lib/processing_manager.py#L286-L293)).
`MpvController.play()` ignores them; the lavfi-complex chain only references
`[aid1]`. Port the prototype's dual-stem chain so that — when both stems exist —
playback wires `[aid2]` (vocal) and `[aid3]` (nonvocal) into a per-track
rubberband and an `amix`, matching [mpv/app.py:143-166](mpv/app.py#L143-L166).

### Data structures

Extend `MpvController.play()` with optional companion paths:

```python
def play(
    self,
    file_path: str,
    semitones: int = 0,
    subtitle_path: str | None = None,
    subtitle_delay: float = 0.0,
    normalization_db: float | None = None,
    vocal_path: str | None = None,
    nonvocal_path: str | None = None,
    vocal_volume: float = 1.0,
) -> None
```

Add controller-level state:

```python
self._dual_stem: bool = False
self._current_vocal_volume: float = 1.0
```

### Methods

- **`MpvController.build_filter(pitch, normalization_db, dual_stem, vocal_volume)`**
  (extend existing static method)

  Define the prototype's two rubberband presets verbatim
  ([mpv/app.py:67-76](mpv/app.py#L67-L76)) as module-level constants
  `_RB_VOCAL` and `_RB_NONVOCAL` in `mpv_controller.py`.

  **Single-stem branch:** replace the inline rubberband params with `_RB_VOCAL`.
  This is a behavioral change vs. the current implementation — pitch quality
  becomes identical to the prototype (`pitchq=quality`, `transients=crisp`,
  `phase=laminar`, etc.). Confirmed acceptable.

  **Dual-stem branch** (new) mirrors the prototype:

  ```python
  if dual_stem:
      # [aid2] vocal track: volume@vocalvol → azmq → rubberband(_RB_VOCAL)
      # [aid3] nonvocal track: volume → rubberband(_RB_NONVOCAL)
      # amix → optional normalization → [ao]
  ```

  Include the `azmq=bind_address=tcp\\\\://127.0.0.1\\\\:5556` filter on the
  vocal `volume@vocalvol` so live vocal-volume changes can target the running
  filter without rebuilding lavfi-complex (rebuild causes audible glitches and
  loses position by ~50 ms).

- **`MpvController.play()`** — when `vocal_path` and `nonvocal_path` exist on
  disk:

  1. After `loadfile`, call `self._player.command("audio-add", vocal_path, "auto")`
     and again for the nonvocal stem.
  2. Sleep ~200 ms for the `audio-add` to settle (matches prototype).
  3. Call `build_filter(pitch, norm, dual_stem=True, vocal_volume=vocal_volume)`.
  4. Set `self._dual_stem = True` and `self._current_vocal_volume = vocal_volume`.

  **Track-ID assumption:** the dual-stem filter chain references `[aid2]` /
  `[aid3]`. The prototype confirms that `loadfile(video)` followed by two
  `audio-add` calls reliably produces tracks at those IDs. Trust this rather
  than asserting at runtime.

  Wrap the lavfi-complex assignment in this method (and in `set_pitch`) under
  the existing `_lock`, but also ensure the surrounding method is `@_safe` so
  exceptions during the assignment don't propagate uncaught — same invariant
  as every other MPV operation in the file.

- **`MpvController.set_pitch()`** — extend to pass all four args to
  `build_filter`:

  ```python
  @_safe
  def set_pitch(self, semitones: int) -> None:
      pitch = 2 ** (semitones / 12)
      self._current_pitch = pitch
      filter_str = self.build_filter(
          pitch,
          self._current_normalization_db,
          dual_stem=self._dual_stem,
          vocal_volume=self._current_vocal_volume,
      )
      with self._lock:
          self._player.lavfi_complex = filter_str
  ```

  Pitch change while dual-stem still rebuilds the full filter (rubberband pitch
  is not exposed via azmq).

- **`MpvController.set_vocal_volume(volume: float) -> None`** (new):

  - When `_dual_stem` is False: no-op (single-stem has no separate vocal track).

  - When True: send a ZMQ command to filter label `volume@vocalvol` via a tiny
    raw-socket helper (no `pyzmq` dependency — confirmed):

    ```python
    @_safe
    def set_vocal_volume(self, volume: float) -> None:
        if not self._dual_stem:
            return
        self._current_vocal_volume = volume
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(("127.0.0.1", 5556))
            s.sendall(f"volume@vocalvol volume {volume}\n".encode())
    ```

    Mirrors the prototype's `zmq_af_command`. Add `import socket` at the top of
    `mpv_controller.py`. Update `self._current_vocal_volume` *before* the send so
    a subsequent `set_pitch` rebuild preserves the new value even if the socket
    write fails.

### PlaybackController & Karaoke wiring

- **`PlaybackController._find_companions(file_path)`** (new) → returns
  `(vocal_path | None, nonvocal_path | None)`. Use `os.path` for consistency
  with the rest of the file:

  ```python
  base = os.path.splitext(os.path.basename(file_path))[0]
  parent = os.path.dirname(file_path)
  vocal = os.path.join(parent, "vocal", f"{base}---vocal.m4a")
  nonvocal = os.path.join(parent, "nonvocal", f"{base}---nonvocal.m4a")
  if os.path.exists(vocal) and os.path.exists(nonvocal):
      return (vocal, nonvocal)
  return (None, None)
  ```

  Both paths returned as a pair (or both `None`) — half-stem playback is not a
  supported state.

- **`PlaybackController.play_file()`** — call `_find_companions`, fetch
  `vocal_volume = preferences.get_or_default("vocal_volume")`, pass both into
  `mpv.play(...)`. Track `self.now_playing_dual_stem: bool` and
  `self.now_playing_vocal_volume: float` for UI gating. Set both inside the
  `_playback_lock` block alongside the other `now_playing_*` assignments.

- **`PlaybackController.reset_now_playing()`** — also reset
  `self.now_playing_dual_stem = False` and
  `self.now_playing_vocal_volume = 0.0`. Without this, a previous song's
  dual-stem state can briefly leak into the UI before the next song's
  `play_file` runs.

- **`PlaybackController.get_now_playing()`**
  ([playback_controller.py:226-239](pikaraoke/lib/playback_controller.py#L226-L239))
  — add to the returned dict:

  ```python
  "vocal_volume": self.now_playing_vocal_volume,
  "dual_stem": self.now_playing_dual_stem,
  ```

  (The Karaoke-layer payload additions in §2 wrap this; both layers need the
  fields.)

### Flow

```
play_file
  └─ _find_companions ──► (vocal, nonvocal) | (None, None)
  └─ mpv.play(..., vocal_path=, nonvocal_path=, vocal_volume=)
        └─ loadfile(video)
        └─ audio-add(vocal); audio-add(nonvocal)   # only if dual
        └─ build_filter(dual_stem=True/False)
        └─ lavfi_complex = filter_str
```

### Tests

- `MpvController.build_filter(pitch, None, dual_stem=True, vocal_volume=0.4)`
  returns a string containing `volume@vocalvol=0.4`, both rubberband chains,
  `amix=inputs=2`, and the `azmq` binding.
- `PlaybackController._find_companions` returns `(None, None)` when only one
  stem exists (half-state guard).
- `play_file` does not pass companion paths when stems are missing.

______________________________________________________________________

## 2. Vocal volume control (UI + route + preference)

### What & why

When dual-stem (#1) is active, the user should be able to attenuate vocals live
without rebuilding lavfi-complex. UI matches existing transpose/subtitle-delay
controls — slider with -/+ step buttons.

### Preference

Add to `PreferenceManager.DEFAULTS`:

```python
"vocal_volume": 0.4,   # matches prototype DEFAULT_VOCAL_VOLUME
```

Treat it like `subtitle_delay` in the `set()` per-song-override guard
([preference_manager.py:124](pikaraoke/lib/preference_manager.py#L124)):

```python
if preference in ("subtitle_delay", "volume", "vocal_volume"):
    return (True, _("Your preferences were changed successfully"))
```

### Karaoke wiring

- New attribute: `self.vocal_volume: float`. Loaded by `_load_preferences`
  automatically because the key exists in `DEFAULTS`.

- New method `Karaoke.set_vocal_volume(volume: float)`:

  ```python
  self.vocal_volume = volume
  self.playback_controller.set_vocal_volume(volume)
  self.log_and_send(_("Vocal volume: %s%%") % int(volume * 100))
  self.update_now_playing_socket()
  ```

- `Karaoke.reset_now_playing()` — also resets `self.vocal_volume` from preference
  (mirrors existing subtitle_delay reset
  at [karaoke.py:563](pikaraoke/karaoke.py#L563)).

### PlaybackController

```python
def set_vocal_volume(self, volume: float) -> None:
    if self.is_playing:
        self.mpv.set_vocal_volume(volume)
        self.now_playing_vocal_volume = volume
        self.events.emit("now_playing_update")
```

### Route

In [routes/controller.py](pikaraoke/routes/controller.py):

```python
@controller_bp.route("/vocal_volume/<volume>")
def vocal_volume(volume):
    k = get_karaoke_instance()
    k.set_vocal_volume(float(volume))
    broadcast_event("vocal_volume", volume)
    return redirect(url_for("home.home"))
```

### now_playing payload

Extend `Karaoke.get_now_playing()`
([karaoke.py:578](pikaraoke/karaoke.py#L578-L584)):

```python
"vocal_volume": self.vocal_volume,
"dual_stem": self.playback_controller.now_playing_dual_stem,
```

### UI ([home.html](pikaraoke/templates/home.html))

Add a new section above the subtitle-delay section, structurally identical to
the existing transpose row. Hide it unless `dual_stem` is true.

```html
<div id="vocal-volume-section" style="display: none">
    <div class="is-flex" style="justify-content: space-between">
        <div><h4>{% trans %}Vocal Volume{% endtrans %}</h4></div>
        <div class="is-flex">
            <h4 id="vocal-volume-label">40%</h4>
        </div>
    </div>
    <div style="width: 100%">
        <div class="is-flex" style="align-items: center; gap: 8px">
            <button class="button is-rounded is-small"
                    onclick="stepVocalVolume(-10)" style="flex-shrink: 0">−</button>
            <input type="range" min="0" max="100" value="40" step="1"
                   id="vocal-volume-slider" style="flex: 1; min-width: 0" />
            <button class="button is-rounded is-small"
                    onclick="stepVocalVolume(10)" style="flex-shrink: 0">+</button>
        </div>
    </div>
    <hr />
</div>
```

JS additions (alongside `stepPitch` / `stepSubtitleDelay`):

```javascript
function stepVocalVolume(delta) {
    var slider = document.getElementById("vocal-volume-slider");
    var val = Math.max(0, Math.min(100, parseInt(slider.value) + delta));
    slider.value = val;
    document.getElementById("vocal-volume-label").innerHTML = val + "%";
    debounceStep(() => $.get("/vocal_volume/" + (val / 100)), '_vocalvol');
}
```

In `handleNowPlaying(np)`:

```javascript
if (np.dual_stem) {
    $("#vocal-volume-section").show();
    if (np.vocal_volume !== undefined) {
        var pct = Math.round(np.vocal_volume * 100);
        $("#vocal-volume-slider").val(pct);
        $("#vocal-volume-label").html(pct + "%");
    }
} else {
    $("#vocal-volume-section").hide();
}
```

In the `$(function () { ... })` setup, add the input handler (mirrors transpose):

```javascript
var vvSlider = document.getElementById("vocal-volume-slider");
var vvLabel = document.getElementById("vocal-volume-label");
if (vvSlider && vvLabel) {
    vvSlider.oninput = () => { vvLabel.innerHTML = vvSlider.value + "%"; };
    vvSlider.onchange = () => {
        debounceStep(() => $.get("/vocal_volume/" + (vvSlider.value / 100)), '_vocalvol');
    };
}
```

### info.html preference field

Add to the server-settings card
([info.html:312](pikaraoke/templates/info.html#L312-L329)), matching the
`subtitle_delay` row:

```html
<div class="user-preference-container is-align-items-center">
    <input id="pref-vocal-volume" class="user-preference-input input"
           type="number" step="1" min="0" max="100"
           data-pref="vocal_volume" data-start-value="{{ vocal_volume }}"
           value="{{ vocal_volume }}" />
    <label class="label" for="pref-vocal-volume">
        {% trans %}Default vocal volume (0-100%, dual-stem songs only){% endtrans %}
    </label>
</div>
```

In [routes/info.py](pikaraoke/routes/info.py#L37-L70) add:

```python
vocal_volume = (int(k.preferences.get_or_default("vocal_volume") * 100),)
```

(Number-input value is 0-100; convert to 0.0-1.0 in `preferences.set()` — easiest
is to keep the preference stored as float and have the JS in info.html scale.
Since other prefs already do this kind of thing inline, use a small JS handler
on `#pref-vocal-volume` that POSTs `value / 100` instead of changing
preference_manager.)

### Tests

- `Karaoke.reset_now_playing()` resets `vocal_volume` to preference value.
- `PlaybackController.set_vocal_volume()` no-ops when not playing.
- `set_vocal_volume` route → `k.set_vocal_volume` → `mpv.set_vocal_volume` chain.

______________________________________________________________________

## 3. Karaoke (.ass) subtitle support + mode toggle

### What & why

The prototype supports three subtitle modes — `karaoke` (animated `.ass`
captions), `srt` (plain subtitles), `off` — selectable via a segmented control
([mpv/templates/index.html:432-437](mpv/templates/index.html#L432-L437)).
[playback_controller.py:140](pikaraoke/lib/playback_controller.py#L140) flags
this as a planned feature. Land it now alongside the dual-stem work since both
piggyback on the same companion-file discovery pattern.

### Subtitle file conventions

| Mode | File | Location |
|---|---|---|
| karaoke | `<song>.ass` | `<song-dir>/karaoke/<song>.ass` (parallel to the SRT convention; ProcessingManager will write here in a future change) |
| srt | `<song>.srt` | `<song-dir>/subtitles/<song>.srt` (existing main-project convention, see [playback_controller.py:148-154](pikaraoke/lib/playback_controller.py#L137-L154)) |
| off | — | none |

Note: this differs from the prototype, which puts `.ass` next to the video.
Main project keeps generated assets in per-format subfolders for cleanliness.

Resolution rule for default-on-load (matches prototype
[mpv/app.py:493-496](mpv/app.py#L493-L496)):

1. If `.ass` exists → karaoke
2. else if `.srt` exists → srt
3. else → off

### Data structures

Extend `MpvController.play()`:

```python
def play(
    self,
    ...,
    ass_path: str | None = None,
    srt_path: str | None = None,
    initial_sub_mode: str = "off",   # "karaoke" | "srt" | "off"
    subtitle_delay: float = 0.0,
):
```

Replace the existing single `subtitle_path` parameter — call sites move to
named args.

`MpvController` state:

```python
self._available_subs: dict[str, str | None] = {"ass": None, "srt": None}
self._current_sub_mode: str = "off"
```

### Methods

- **`MpvController._apply_subtitle_mode(mode: str, *, skip_remove=False)`**
  Direct port of [mpv/app.py:204-234](mpv/app.py#L204-L234). Two invariants
  must be preserved exactly:

  1. `skip_remove=True` MUST be used on the initial play call (after
     `lavfi_complex` is set but before any user mode change). Calling
     `sub_remove()` while lavfi-complex is active on the auto-loaded sub
     segfaults libmpv.
  2. `sub_remove()` is only called when an active sub track is currently
     loaded (i.e. `self._current_sub_mode in ("karaoke", "srt")`); never
     unconditionally.

  `set_subtitle_delay` invariant: delay is meaningful only in `srt` mode.
  `_apply_subtitle_mode` must reset `sub_delay = 0` when entering `karaoke`
  or `off`.

- **`MpvController.set_sub_mode(mode: str) -> None`** — public wrapper that
  calls `_apply_subtitle_mode(mode)` (with `skip_remove=False`).

- **`MpvController.set_subtitle_delay()`** — keep existing signature. Invariant:
  delay is only meaningful in `srt` mode. `_apply_subtitle_mode` enforces
  delay = 0 for non-srt modes.

- **`MpvController.play()`** — store `self._available_subs` and
  `self._current_sub_mode`, then call `_apply_subtitle_mode(initial_sub_mode, skip_remove=True)` after lavfi-complex is set.

### PlaybackController

- New helper `_find_subtitles(file_path)` returns
  `{"ass": path | None, "srt": path | None}`. Replaces the existing
  `_find_subtitle` method.

- `play_file` resolves initial mode and passes `ass_path`, `srt_path`,
  `initial_sub_mode` to `mpv.play`.

- New attribute `self.now_playing_sub_mode: str` and
  `self.now_playing_subs_available: dict[str, bool]`.

- New method:

  ```python
  def set_sub_mode(self, mode: str) -> None:
      if self.is_playing:
          self.mpv.set_sub_mode(mode)
          self.now_playing_sub_mode = mode
          self.events.emit("now_playing_update")
  ```

### Karaoke wiring

- `Karaoke.set_sub_mode(mode)` — log notification, delegate to playback
  controller, emit socket update.

- `get_now_playing()` payload additions:

  ```python
  "sub_mode": self.playback_controller.now_playing_sub_mode,
  "subs_available": self.playback_controller.now_playing_subs_available,
  ```

### Route ([routes/controller.py](pikaraoke/routes/controller.py))

```python
@controller_bp.route("/sub_mode/<mode>")
def sub_mode(mode):
    if mode not in ("karaoke", "srt", "off"):
        return ("invalid mode", 400)
    k = get_karaoke_instance()
    k.set_sub_mode(mode)
    broadcast_event("sub_mode", mode)
    return redirect(url_for("home.home"))
```

### UI ([home.html](pikaraoke/templates/home.html))

Above the existing subtitle-delay section, add a segmented control. Bulma
already ships `.buttons.has-addons` which gives the prototype's exact look:

```html
<div id="subtitle-mode-section" style="display: none">
    <div class="is-flex" style="justify-content: space-between">
        <div><h4>{% trans %}Subtitles{% endtrans %}</h4></div>
    </div>
    <div class="buttons has-addons" style="margin-bottom: 0.5rem">
        <button class="button is-small" data-mode="karaoke"
                onclick="setSubMode('karaoke')">Karaoke</button>
        <button class="button is-small" data-mode="srt"
                onclick="setSubMode('srt')">Subtitles</button>
        <button class="button is-small is-selected is-info" data-mode="off"
                onclick="setSubMode('off')">Off</button>
    </div>
    <hr />
</div>
```

Wrap the existing subtitle-delay block in `id="subtitle-delay-section"` so it
can be hidden when not in `srt` mode (matches prototype invariant).

JS additions:

```javascript
function setSubMode(mode) {
    debounceStep(() => $.get("/sub_mode/" + mode), '_submode');
    // optimistic UI — server pushes confirmation via socket
    applySubModeToButtons(mode);
    $("#subtitle-delay-section").toggle(mode === "srt");
}

function applySubModeToButtons(mode) {
    document.querySelectorAll("#subtitle-mode-section [data-mode]").forEach(b => {
        b.classList.toggle("is-info", b.dataset.mode === mode);
        b.classList.toggle("is-selected", b.dataset.mode === mode);
    });
}
```

In `handleNowPlaying`:

```javascript
if (np.subs_available) {
    $("#subtitle-mode-section").show();
    document.querySelector("[data-mode='karaoke']").disabled = !np.subs_available.ass;
    document.querySelector("[data-mode='srt']").disabled = !np.subs_available.srt;
    if (np.sub_mode) applySubModeToButtons(np.sub_mode);
    $("#subtitle-delay-section").toggle(np.sub_mode === "srt");
} else {
    $("#subtitle-mode-section").hide();
}
```

### Open question

Where do `.ass` files come from in the main project? The prototype assumes they
already exist next to the video. PiKaraoke's `ProcessingManager` doesn't
generate them. Two options:

- **A.** Land karaoke-mode support now; users supply `.ass` files manually
  (matches prototype). Ship a follow-up plan for `.ass` generation.
- **B.** Block this feature on `.ass` generation work.

Recommend (A) — the toggle button is auto-disabled when no `.ass` exists, so
the feature degrades cleanly.

### Tests

- `_apply_subtitle_mode("off")` clears delay regardless of prior state
  (invariant 2).
- Initial mode resolves to `karaoke` when `.ass` exists, `srt` otherwise, `off`
  when neither.
- Mode toggle while paused does not crash (covered by `skip_remove=True` only
  on initial play).

______________________________________________________________________

## 4. Volume normalization (deferred — placeholder only)

### What & why

`PlaybackController.play_file` already accepts a `normalization_db` argument and
threads it into `MpvController.play()`, but the value is hardcoded `None` (see
[playback_controller.py:108-112](pikaraoke/lib/playback_controller.py#L108-L112)).
The `normalize_audio` preference toggle exists in the info page but does
nothing yet.

Treat this the same way as `.ass` files in #3: the playback layer is ready to
consume the value, but the producer (ProcessingManager measuring loudness and
writing it to the song DB) is a separate, future change. Leave the playback
hardcoded `None` for now.

### Out of scope for this plan

- Loudness measurement (ffmpeg `ebur128` step in ProcessingManager)
- `normalization_db` column on the `songs` table + migration
- `KaraokeDatabase.get_normalization_db` / `set_normalization_db`

### Tiny prep change (optional)

When ProcessingManager grows the column read, the only edit at the playback
layer will be to replace
[playback_controller.py:108-112](pikaraoke/lib/playback_controller.py#L108-L112)
with a single DB lookup:

```python
normalization_db = None
if self.preferences.get_or_default("normalize_audio"):
    normalization_db = self._db.get_normalization_db(file_path)
```

For that, `PlaybackController.__init__` will need a `db: KaraokeDatabase`
parameter. Optional now to add the constructor parameter (unused) so the
follow-up change is purely additive — but cleaner to defer the constructor
change too until the read path actually exists.

### Tests

None for this plan. Tests land with the producer change.

______________________________________________________________________

## 5. "Vocals: NN%" in timecode overlay

### What & why

Prototype's timecode overlay
([mpv/app.py:395-410](mpv/app.py#L395-L410)) reads
`{elapsed} / {total} | Pitch: {st} | Vocals: {pct}%`. Main's
[\_build_timecode_overlay](pikaraoke/lib/overlay_manager.py#L128-L140) shows
only pitch. Add the vocal-volume tail when dual-stem is active.

Depends on #2 (vocal volume must exist as state).

### Changes

Extend `OverlayState` ([overlay_manager.py:44-63](pikaraoke/lib/overlay_manager.py#L44-L63)):

```python
@dataclass(frozen=True)
class OverlayState:
    ...
    dual_stem: bool
    vocal_volume: float  # 0.0-1.0
```

Because `OverlayState` is `@dataclass(frozen=True)` with no defaults, every
construction site must be updated. Grep for `OverlayState(` and update each —
expected sites are `PlaybackController.build_overlay_state()` and any test
fixtures that construct one directly.

Extend `PlaybackController.build_overlay_state()`
([playback_controller.py:252-275](pikaraoke/lib/playback_controller.py#L252-L275)):

```python
return OverlayState(
    ...,
    dual_stem=self.now_playing_dual_stem,
    vocal_volume=self.now_playing_vocal_volume,
)
```

Extend `_build_timecode_overlay`:

```python
text = f"{elapsed} / {total} | Pitch: {st_str}"
if state.dual_stem:
    text += f" | Vocals: {int(state.vocal_volume * 100)}%"
```

Because `OverlayManager` diffs by `Overlay` equality, the overlay re-renders
automatically the next tick after `set_vocal_volume` updates state.

### Tests

- Overlay text excludes "Vocals:" when `dual_stem=False`.
- Overlay text includes correct percentage when `dual_stem=True`.

______________________________________________________________________

## 6. Seek bar in now-playing UI

### What & why

`MpvController.seek()` exists ([mpv_controller.py:330-332](pikaraoke/lib/mpv_controller.py#L329-L332))
but the home page has no UI for it. Prototype has a draggable bar with elapsed
/ remaining time labels updated by polling
([mpv/templates/index.html:396-400](mpv/templates/index.html#L396-L400)).
Main project already broadcasts `playback_position` via Socket.IO
([playback_controller.py:285-288](pikaraoke/lib/playback_controller.py#L285-L288)),
so no new polling needed — the bar listens to that event.

### Lock pattern

The prototype's `S.locks.seeking` flag is essential: while the user is dragging,
incoming position updates from the server must NOT overwrite the slider value.
Port that pattern verbatim — it is the only thing that prevents the slider from
snapping back to the server's position mid-drag.

### Route

```python
@controller_bp.route("/seek/<position>")
def seek(position):
    k = get_karaoke_instance()
    k.playback_controller.seek(float(position))
    return ("", 204)
```

`PlaybackController.seek(position: float)`:

```python
def seek(self, position: float) -> None:
    if self.is_playing:
        self.mpv.seek(position)
```

### now_playing payload

Already includes `now_playing_position` and `now_playing_duration`. No change.

### UI

Add at the top of the `.control-box`, just under the header:

```html
<div class="seek-row" style="display: flex; align-items: center; gap: 8px;
                              margin-bottom: 0.75rem;">
    <span id="time-elapsed" class="is-size-7"
          style="width: 40px; text-align: right;">0:00</span>
    <input type="range" id="seek-bar" min="0" max="100" value="0" step="0.1"
           style="flex: 1; min-width: 0;" />
    <span id="time-total" class="is-size-7"
          style="width: 40px;">0:00</span>
</div>
```

JS additions:

```javascript
var _seekDragging = false;
var _seekDuration = 0;

function fmtTime(s) {
    if (!s || s <= 0) return "0:00";
    var m = Math.floor(s / 60);
    var sec = Math.floor(s % 60);
    return m + ":" + (sec < 10 ? "0" : "") + sec;
}

var seekBar = document.getElementById("seek-bar");
seekBar.addEventListener("input", function () { _seekDragging = true; });
seekBar.addEventListener("change", function () {
    var pos = (seekBar.value / 100) * _seekDuration;
    // Hold the drag-lock until *after* the seek confirms AND a small grace
    // window passes, so a stale playback_position event in flight cannot
    // snap the slider back to the pre-seek position.
    $.get("/seek/" + pos).always(() => {
        setTimeout(() => { _seekDragging = false; }, 200);
    });
});

window.socket.on("playback_position", function (pos) {
    if (!_seekDragging && _seekDuration > 0) {
        seekBar.value = (pos / _seekDuration) * 100;
    }
    document.getElementById("time-elapsed").innerHTML = fmtTime(pos);
});
```

In `handleNowPlaying(np)`:

```javascript
_seekDuration = np.now_playing_duration || 0;
document.getElementById("time-total").innerHTML = fmtTime(_seekDuration);
if (!_seekDragging && _seekDuration > 0) {
    seekBar.value = ((np.now_playing_position || 0) / _seekDuration) * 100;
}
```

### Tests

- `PlaybackController.seek()` no-ops when not playing.
- `/seek/<position>` route delegates to `playback_controller.seek`.

______________________________________________________________________

## 7. Per-song reset of vocal volume

### What & why

Item #1 already passes `vocal_volume` from preference into `play_file`. The
remaining work is the symmetrical reset in `Karaoke.reset_now_playing()` so
that mid-song slider tweaks don't leak across songs. Mirror the
[`subtitle_delay` reset](pikaraoke/karaoke.py#L562-L563):

```python
def reset_now_playing(self) -> None:
    self.playback_controller.reset_now_playing()
    self.volume = self.preferences.get_or_default("volume")
    self.subtitle_delay = self.preferences.get_or_default("subtitle_delay")
    self.vocal_volume = self.preferences.get_or_default("vocal_volume")
    self.update_now_playing_socket()
```

This is essentially one line + the Karaoke attribute initialization (which
`_load_preferences` does automatically once the key is in `DEFAULTS`). Only
listed separately for completeness — fold into #2's commit.

### Tests

- After `reset_now_playing()`, `k.vocal_volume == preferences.get_or_default("vocal_volume")`.

______________________________________________________________________

## Suggested rollout order

1. **#3 Karaoke subtitle mode** — independent; smallest blast radius; gives
   immediate user-visible payoff.
2. **#1 + #2 + #5 + #7 Dual-stem stack** — land together; vocal volume is the
   payoff for stems and gates the overlay change.
3. **#6 Seek bar** — independent; cosmetic-only; ship last.

#4 (normalization) is deferred entirely until ProcessingManager grows loudness
measurement — no work happens here.

## Out of scope

- `.ass` file generation (a separate plan; the toggle in #3 just disables
  cleanly when none exists)
- Loudness measurement and `normalization_db` storage (#4 — deferred to a
  future ProcessingManager change)
- Master volume slider in UI (existing volume-up / volume-down buttons +
  small slider already cover this — different from the prototype's "Master
  Volume" full-width slider, but functionally equivalent)
- Web file browser (the prototype's modal exists because the prototype has no
  song queue; main project always plays from queue)
