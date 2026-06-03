"""Unit tests for overlay_manager module."""

from unittest.mock import MagicMock, call

import pytest

from pikaraoke.lib.overlay_manager import (
    OSD_CLOCK,
    OSD_NOWPLAYING,
    OSD_QUEUE_PREVIEW,
    OSD_TIMECODE,
    OSD_UPNEXT,
    OSD_URL,
    Overlay,
    OverlayManager,
    OverlayState,
    QueuedSong,
    ScreenMode,
    _ass_escape,
    _overlay_font_size,
    compute_overlays,
    render_ass,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

_SONG_A = QueuedSong(title="Take On Me", singer="UserA")
_SONG_B = QueuedSong(title="Bohemian Rhapsody", singer="UserB")


def _idle_state(**overrides) -> OverlayState:
    defaults = dict(
        mode=ScreenMode.IDLE,
        now_playing_title=None,
        queue_preview=(),
        semitones=0,
        position=0.0,
        duration=0.0,
        screen_w=1920,
        screen_h=1080,
        hide_url=False,
        hide_now_playing=False,
        hide_clock=False,
        server_url="http://pikaraoke.local:5555",
        dual_stem=False,
        vocal_volume=0.0,
        singer_name="",
    )
    defaults.update(overrides)
    return OverlayState(**defaults)


def _playing_state(**overrides) -> OverlayState:
    defaults = dict(
        mode=ScreenMode.PLAYING,
        now_playing_title="Never Gonna Give You Up",
        queue_preview=(_SONG_A,),
        semitones=0,
        position=42.0,
        duration=212.0,
        screen_w=1920,
        screen_h=1080,
        hide_url=False,
        hide_now_playing=False,
        hide_clock=False,
        server_url="http://pikaraoke.local:5555",
        dual_stem=False,
        vocal_volume=0.0,
        singer_name="Singer1",
    )
    defaults.update(overrides)
    return OverlayState(**defaults)


def _mock_mpv():
    mpv = MagicMock()
    mpv.osd_overlay = MagicMock()
    mpv.clear_osd = MagicMock()
    mpv.send_qr_bitmap = MagicMock()
    mpv.remove_qr_bitmap = MagicMock()
    return mpv


# ── compute_overlays: IDLE ─────────────────────────────────────────────────────


class TestComputeOverlaysIdle:
    def test_url_always_visible_on_idle(self):
        state = _idle_state()
        result = compute_overlays(state)
        assert OSD_URL in result

    def test_url_hidden_on_idle_when_hide_url_true(self):
        """hide_url preference is respected even on the splash screen."""
        state = _idle_state(hide_url=True)
        result = compute_overlays(state)
        assert OSD_URL not in result

    def test_no_playing_overlays_on_idle(self):
        state = _idle_state()
        result = compute_overlays(state)
        assert OSD_NOWPLAYING not in result
        assert OSD_TIMECODE not in result
        assert OSD_UPNEXT not in result

    def test_queue_preview_absent_when_no_queue(self):
        state = _idle_state(queue_preview=())
        result = compute_overlays(state)
        assert OSD_QUEUE_PREVIEW not in result

    def test_queue_preview_present_when_queue_has_songs(self):
        state = _idle_state(queue_preview=(_SONG_A, _SONG_B))
        result = compute_overlays(state)
        assert OSD_QUEUE_PREVIEW in result

    def test_queue_preview_hidden_when_hide_now_playing(self):
        state = _idle_state(queue_preview=(_SONG_A,), hide_now_playing=True)
        result = compute_overlays(state)
        assert OSD_QUEUE_PREVIEW not in result

    def test_clock_present_by_default(self):
        state = _idle_state(hide_clock=False)
        result = compute_overlays(state)
        assert OSD_CLOCK in result

    def test_clock_absent_when_hidden(self):
        state = _idle_state(hide_clock=True)
        result = compute_overlays(state)
        assert OSD_CLOCK not in result


# ── compute_overlays: PLAYING ──────────────────────────────────────────────────


class TestComputeOverlaysPlaying:
    def test_url_present_by_default(self):
        state = _playing_state()
        result = compute_overlays(state)
        assert OSD_URL in result

    def test_url_hidden_by_pref(self):
        state = _playing_state(hide_url=True)
        result = compute_overlays(state)
        assert OSD_URL not in result

    def test_nowplaying_and_timecode_present(self):
        state = _playing_state()
        result = compute_overlays(state)
        assert OSD_NOWPLAYING in result
        assert OSD_TIMECODE in result

    def test_upnext_present_when_queue_has_songs(self):
        state = _playing_state(queue_preview=(_SONG_A,))
        result = compute_overlays(state)
        assert OSD_UPNEXT in result

    def test_upnext_absent_when_queue_empty(self):
        state = _playing_state(queue_preview=())
        result = compute_overlays(state)
        assert OSD_UPNEXT not in result

    def test_nowplaying_absent_when_hide_now_playing(self):
        state = _playing_state(hide_now_playing=True)
        result = compute_overlays(state)
        assert OSD_NOWPLAYING not in result
        assert OSD_TIMECODE not in result
        assert OSD_UPNEXT not in result

    def test_nowplaying_absent_when_no_title(self):
        state = _playing_state(now_playing_title=None)
        result = compute_overlays(state)
        assert OSD_NOWPLAYING not in result
        assert OSD_TIMECODE not in result

    def test_clock_honours_pref_independent_of_mode(self):
        on = _playing_state(hide_clock=False)
        off = _playing_state(hide_clock=True)
        assert OSD_CLOCK in compute_overlays(on)
        assert OSD_CLOCK not in compute_overlays(off)

    def test_paused_mode_produces_same_overlays_as_playing(self):
        playing = _playing_state(mode=ScreenMode.PLAYING)
        paused = _playing_state(mode=ScreenMode.PAUSED)
        assert set(compute_overlays(playing).keys()) == set(compute_overlays(paused).keys())

    def test_nowplaying_text_contains_title(self):
        state = _playing_state(now_playing_title="Bohemian Rhapsody")
        result = compute_overlays(state)
        assert "Bohemian Rhapsody" in result[OSD_NOWPLAYING].text

    def test_timecode_reflects_position_and_duration(self):
        state = _playing_state(position=90.0, duration=210.0)
        result = compute_overlays(state)
        assert "1:30" in result[OSD_TIMECODE].text
        assert "3:30" in result[OSD_TIMECODE].text

    def test_timecode_shows_pitch(self):
        state = _playing_state(semitones=3)
        result = compute_overlays(state)
        assert "+3st" in result[OSD_TIMECODE].text

    def test_timecode_shows_negative_pitch(self):
        state = _playing_state(semitones=-2)
        result = compute_overlays(state)
        assert "-2st" in result[OSD_TIMECODE].text

    def test_timecode_excludes_vocals_when_not_dual_stem(self):
        state = _playing_state(dual_stem=False)
        result = compute_overlays(state)
        assert "🗣️" not in result[OSD_TIMECODE].text

    def test_timecode_includes_vocals_pct_when_dual_stem(self):
        state = _playing_state(dual_stem=True, vocal_volume=0.4)
        result = compute_overlays(state)
        assert "🗣️" in result[OSD_TIMECODE].text
        assert "40%" in result[OSD_TIMECODE].text

    def test_timecode_vocals_zero_pct(self):
        state = _playing_state(dual_stem=True, vocal_volume=0.0)
        result = compute_overlays(state)
        assert "🗣️" in result[OSD_TIMECODE].text
        assert "0%" in result[OSD_TIMECODE].text


# ── render_ass ─────────────────────────────────────────────────────────────────


class TestRenderAss:
    def test_contains_anchor_and_position(self):
        o = Overlay(
            id=OSD_URL,
            anchor="\\an7",
            pos=(100.0, 0.0),
            font_size=30,
            color="&HFFFFFF&",
            text="http://test",
        )
        result = render_ass(o)
        assert "\\an7" in result
        assert "\\pos(100.0,0.0)" in result
        assert "\\fs30" in result
        assert "http://test" in result

    def test_text_is_at_end(self):
        o = Overlay(
            id=OSD_NOWPLAYING,
            anchor="\\an9",
            pos=(1920.0, 0.0),
            font_size=40,
            color="&H507FFF&",
            text="Now Playing: Foo",
        )
        result = render_ass(o)
        assert result.endswith("Now Playing: Foo")


# ── OverlayManager diff behaviour ─────────────────────────────────────────────


class TestOverlayManagerDiff:
    def test_first_apply_sends_visible_overlays(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        state = _idle_state()
        manager.apply(state)
        # URL and clock are both visible by default on splash
        sent_ids = {c.args[0] for c in mpv.osd_overlay.call_args_list}
        assert sent_ids == {OSD_URL, OSD_CLOCK}

    def test_unchanged_state_does_not_resend(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        state = _idle_state()
        manager.apply(state)
        mpv.osd_overlay.reset_mock()
        manager.apply(state)
        mpv.osd_overlay.assert_not_called()

    def test_mode_change_adds_playing_overlays(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        # IDLE state with queue items (produces QUEUE_PREVIEW)
        manager.apply(_idle_state(queue_preview=(_SONG_A,)))
        mpv.osd_overlay.reset_mock()
        mpv.clear_osd.reset_mock()

        # Transition to PLAYING — now-playing + timecode + upnext appear
        manager.apply(_playing_state(queue_preview=(_SONG_A,)))
        sent_ids = {c.args[0] for c in mpv.osd_overlay.call_args_list}
        assert OSD_NOWPLAYING in sent_ids
        assert OSD_TIMECODE in sent_ids

    def test_mode_change_clears_removed_overlays(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_playing_state(queue_preview=(_SONG_A,)))
        mpv.clear_osd.reset_mock()

        # Transition to IDLE — playing overlays cleared
        manager.apply(_idle_state(queue_preview=(_SONG_A,)))
        cleared_ids = {c.args[0] for c in mpv.clear_osd.call_args_list}
        assert OSD_NOWPLAYING in cleared_ids
        assert OSD_TIMECODE in cleared_ids

    def test_invalidate_forces_full_resend(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        state = _idle_state()
        manager.apply(state)
        mpv.osd_overlay.reset_mock()

        manager.invalidate()
        manager.apply(state)
        mpv.osd_overlay.assert_called()

    def test_invalidate_still_clears_now_undesired_overlays(self):
        # Regression: invalidate() must not orphan overlays that became
        # undesired. It keeps _last_sent so the next apply() can still clear
        # them (clearing _last_sent would leave them rendered on screen).
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_idle_state(queue_preview=(_SONG_A,)))  # QUEUE_PREVIEW visible
        mpv.clear_osd.reset_mock()

        manager.invalidate()  # e.g. an osd-dimensions resize
        manager.apply(_idle_state(queue_preview=()))  # queue now empty
        cleared_ids = {c.args[0] for c in mpv.clear_osd.call_args_list}
        assert OSD_QUEUE_PREVIEW in cleared_ids

    def test_only_changed_overlay_is_resent(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        state1 = _playing_state(position=10.0, hide_clock=False)
        manager.apply(state1)
        mpv.osd_overlay.reset_mock()

        # Advance time only -- only TIMECODE should differ
        state2 = _playing_state(position=11.0, hide_clock=False)
        manager.apply(state2)
        sent_ids = {c.args[0] for c in mpv.osd_overlay.call_args_list}
        assert OSD_TIMECODE in sent_ids
        assert OSD_NOWPLAYING not in sent_ids

    def test_qr_sent_on_first_apply(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_idle_state())
        mpv.send_qr_bitmap.assert_called_once()

    def test_qr_not_resent_when_unchanged(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_idle_state())
        mpv.send_qr_bitmap.reset_mock()
        manager.apply(_idle_state())
        mpv.send_qr_bitmap.assert_not_called()

    def test_qr_resent_after_invalidate(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_idle_state())
        manager.invalidate()
        mpv.send_qr_bitmap.reset_mock()
        manager.apply(_idle_state())
        mpv.send_qr_bitmap.assert_called_once()

    def test_qr_not_sent_when_hide_url(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_idle_state(hide_url=True))
        mpv.send_qr_bitmap.assert_not_called()

    def test_qr_removed_when_hide_url_toggled_on(self):
        mpv = _mock_mpv()
        manager = OverlayManager(mpv)
        manager.apply(_idle_state(hide_url=False))
        mpv.remove_qr_bitmap.reset_mock()
        manager.apply(_idle_state(hide_url=True))
        mpv.remove_qr_bitmap.assert_called_once()


# ── ASS escaping (Review-fix: user-text tag/line-break injection) ─────────────


class TestAssEscape:
    def test_braces_become_parens(self):
        assert _ass_escape("Mix {Remix} (Live)") == "Mix (Remix) (Live)"

    def test_backslash_neutralized(self):
        # '\N' would be an ASS line break; the backslash is replaced so it isn't.
        assert "\\" not in _ass_escape("AC\\DC \\N")

    def test_plain_text_unchanged(self):
        assert _ass_escape("Take On Me - UserA") == "Take On Me - UserA"

    def test_empty_string(self):
        assert _ass_escape("") == ""


class TestBuildersEscapeUserText:
    def test_nowplaying_title_braces_and_backslash_neutralized(self):
        state = _playing_state(now_playing_title="Evil {\\b1}Title}")
        text = compute_overlays(state)[OSD_NOWPLAYING].text
        assert "{" not in text and "}" not in text  # no override block survives
        assert "\\" not in text  # no line-break code survives

    def test_timecode_escapes_singer_name(self):
        state = _playing_state(singer_name="DJ {evil}")
        text = compute_overlays(state)[OSD_TIMECODE].text
        assert "{evil}" not in text
        assert "(evil)" in text

    def test_upnext_escapes_title_and_singer_but_keeps_intentional_tag(self):
        song = QueuedSong(title="A{\\b1}B", singer="C}D")
        state = _playing_state(queue_preview=(song,))
        text = compute_overlays(state)[OSD_UPNEXT].text
        assert "A(⧵b1)B" in text  # title braces + backslash neutralized
        assert "C)D" in text  # singer brace neutralized
        assert text.count("{") == 1 and text.count("}") == 1  # only singer-color block

    def test_queue_preview_keeps_structural_newline_but_escapes_title(self):
        songs = (
            QueuedSong(title="Row\\None", singer="S1"),
            QueuedSong(title="T2", singer="S2"),
        )
        state = _idle_state(queue_preview=songs)
        text = compute_overlays(state)[OSD_QUEUE_PREVIEW].text
        assert text.count("\\N") == 1  # one structural row separator, not the title's
        assert "Row⧵None" in text  # the title's backslash was neutralized
