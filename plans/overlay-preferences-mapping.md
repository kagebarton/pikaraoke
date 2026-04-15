# Overlay Preferences Mapping — MPV Era

Model: Claude Haiku 4.5

## Current State

Three overlay preferences from the splash-page era still exist in `PreferenceManager.DEFAULTS`:

| Preference | Default | Purpose |
|---|---|---|
| `hide_url` | `False` | Hide the URL and QR code |
| `hide_overlay` | `False` | Hide all overlays (now playing, up next, QR) |
| `show_splash_clock` | `False` | Show the digital clock |

All three are saved to `config.ini` and persist across restarts. The info page provides UI checkboxes to change them. However, **none are currently wired to MpvController** — the overlays always display regardless of these settings.

______________________________________________________________________

## MPV Overlay Mappings

### `hide_url` → OSD_URL + QR bitmap

Maps cleanly to the QR code and URL text in the top-left corner.

**Status**: ✓ Still valid. No changes needed.

______________________________________________________________________

### `hide_overlay` → Everything

Documented as hiding "now playing, up next, and QR code". In the MPV system this means:

- OSD_URL (URL text)
- QR bitmap
- OSD_NOWPLAYING ("Now Playing: <title>")
- OSD_TIMECODE (elapsed / total / pitch)
- OSD_UPNEXT ("Up Next: <title>")
- *(question: also OSD_CLOCK?)*

**Status**: ✓ Still valid. But see **Decision 1** below.

______________________________________________________________________

### `show_splash_clock` → OSD_CLOCK

Controls the digital clock overlay (bottom-left). Name references the splash page which no longer exists — "splash_clock" is now stale terminology.

**Status**: ✓ Functionally valid. But see **Decision 2** below.

______________________________________________________________________

## New Overlays

**OSD_TIMECODE** (elapsed/total time + pitch semitones) is new in the MPV playback system. It didn't exist on the old splash page. Currently it's controlled only by `hide_overlay` (lumped in with "all overlays"). Consider whether a dedicated hide option is needed.

**Status**: Acceptable for now. Can be revisited if users want fine-grained control.

______________________________________________________________________

## Open Decisions

### Decision 1: `hide_overlay` vs `show_splash_clock` hierarchy

When both are set, what should happen?

**Scenario A**: `hide_overlay = True` suppresses everything, including the clock (overrides `show_splash_clock`).

- Rationale: "hide all overlays" is absolute; the clock is an overlay.
- Implementation: In the poll loop, check `hide_overlay` first; if True, skip all overlay sends.

**Scenario B**: `show_splash_clock` is independent (old splash.js behavior).

- Rationale: Clock toggle is separate from the "hide overlays" toggle.
- Implementation: Check both independently; clock shows if `show_splash_clock = True` AND `hide_overlay = False`.

**Recommendation**: Scenario A feels more intuitive — "hide all overlays" should be nuclear and include the clock.

______________________________________________________________________

### Decision 2: Rename `show_splash_clock`

Options:

1. **Keep as-is**: Avoid migration burden; name is stale but harmless.
2. **Rename to `show_clock`**: Clearer now that splash is gone, but orphans any existing `config.ini` entries that have `show_splash_clock=True` (PreferenceManager would need migration logic).

**Recommendation**: Keep as-is for now. If a major version bump happens, consider renaming with a migration handler.

______________________________________________________________________

## Implementation Checklist

- \[ \] Add callbacks or direct preference checks to `MpvController._poll_loop()`
- \[ \] Respect `hide_url` → skip `send_qr_overlay()` and `send_url_overlay()`
- \[ \] Respect `hide_overlay` → skip QR, URL, now playing, timecode, up next overlays
- \[ \] Respect `show_splash_clock` → conditionally send `send_clock_overlay()`
- \[ \] Decide: does `hide_overlay` override `show_splash_clock`? (Recommendation: yes)
- \[ \] Optional: add dedicated preference for `hide_timecode` (deferred)
