"""Unit tests for scripts/split_songs.py: edge choice, pauses, and the clip SRT."""

import subprocess

import numpy as np
import pytest

from scripts.split_songs import (
    MAX_CUT_DETOUR,
    Cue,
    Edge,
    Episode,
    Part,
    Show,
    Voice,
    choose,
    clean,
    clip_srt,
    cue_text,
    label_re,
    lead_start,
    music_start,
    parse_srt,
    pick,
    recase,
    tail_end,
)


def _voice(*runs: tuple[int, float]) -> Voice:
    """A voice track from (frame count, dB) runs, starting at 0 s."""
    return Voice(0.0, np.concatenate([np.full(n, db) for n, db in runs]))


SILENT = _voice((2000, -60.0), (10, -10.0))  # 100 s, all quiet but a burst at the very end


class TestParseSrt:
    def test_bom_crlf_and_multiline(self):
        text = (
            "\ufeff1\r\n00:00:01,500 --> 00:00:02,000\r\nHello\r\nthere\r\n\r\n"
            "2\r\n01:00:00.250 --> 01:00:01.000\r\n( music playing )\r\n"
        )
        first, second = parse_srt(text)
        assert (first.num, first.start, first.end, first.text) == (1, 1.5, 2.0, "Hello\nthere")
        assert (second.start, second.end) == (3600.25, 3601.0)

    def test_a_bare_tag_is_not_spoken(self):
        assert not Cue(1, 0, 1, "[ guitar strumming ]").spoken
        assert Cue(1, 0, 1, "( whispering ) hi").spoken


class TestVoiceQuiet:
    def test_floor_is_quiet_speech_is_not(self):
        voice = _voice((100, -10.0), (100, -60.0))
        assert voice.quiet(7.5)
        assert not voice.quiet(2.5)
        assert not voice.quiet(5.0)  # the window around it reaches back into speech

    def test_outside_the_track_is_never_quiet(self):
        voice = _voice((100, -60.0), (100, -10.0))
        assert not voice.quiet(0.05)
        assert not voice.quiet(9.95)

    def test_crowd_murmur_under_a_separated_voice_counts_as_quiet(self):
        # Separated voice: digital silence, murmur, a little speech. The range rule alone
        # would put the threshold near the silence and call the murmur talking.
        voice = _voice((100, -96.0), (80, -31.0), (20, -5.0))
        assert voice.quiet(7.0)


class TestClean:
    def test_no_caption_is_clean_however_loud(self):
        assert clean(1.0, _voice((100, -10.0)), [])

    def test_inside_a_caption_needs_a_quiet_voice(self):
        cues = [Cue(1, 0.0, 10.0, "Some words. More words.")]
        assert clean(7.5, _voice((100, -10.0), (100, -60.0)), cues)
        assert not clean(2.5, _voice((100, -10.0), (100, -60.0)), cues)

    def test_a_tag_is_not_talking(self):
        assert clean(2.5, _voice((100, -10.0), (100, -60.0)), [Cue(1, 0, 10, "( music )")])


class TestPick:
    def test_prefers_the_padding_side(self):
        assert pick([9.0, 10.5], 10.0, -1, SILENT, []) == 9.0
        assert pick([9.5, 11.0], 10.0, 1, SILENT, []) == 11.0

    def test_falls_back_to_the_other_side(self):
        assert pick([11.0], 10.0, -1, SILENT, []) == 11.0

    def test_none_when_nothing_is_clean(self):
        cues = [Cue(1, 0.0, 100.0, "talking")]
        assert pick([5.0], 5.0, -1, _voice((2000, -10.0), (10, -60.0)), cues) is None


class TestChoose:
    WINDOW = [t / 20 for t in range(0, 1800)]  # 0-90 s, every frame

    def test_takes_a_camera_cut_within_the_detour(self):
        cut = 80.0 - MAX_CUT_DETOUR + 1
        assert choose([cut], self.WINDOW, 80.0, -1, SILENT, [], True) == Edge(cut, True)

    def test_a_camera_cut_too_far_loses_to_the_nearest_pause(self):
        cut = 80.0 - MAX_CUT_DETOUR - 1
        assert choose([cut], self.WINDOW, 80.0, -1, SILENT, [], True) == Edge(80.0, False)

    def test_inner_edges_skip_camera_cuts(self):
        assert choose([79.0], self.WINDOW, 80.0, -1, SILENT, [], False) == Edge(80.0, False)

    def test_no_quiet_moment_raises(self):
        with pytest.raises(RuntimeError):
            choose([], [], 80.0, -1, SILENT, [], True)

    def test_a_near_cut_on_the_far_side_beats_falling_off_cut(self):
        assert choose([62.0, 81.0], self.WINDOW, 80.0, -1, SILENT, [], True) == Edge(81.0, True)


class FakeEpisode:
    """An episode's measurements without the video: a quiet voice track and given cuts."""

    def __init__(self, cues: list[Cue], cuts: list[float]):
        self.cues, self.cuts, self.duration = cues, cuts, 600.0

    def voice(self, t0: float, t1: float) -> Voice:
        t0 = max(0.0, t0)
        return Voice(t0, np.concatenate([np.full(int((t1 - t0) * 20), -60.0), [-10.0] * 10]))

    def shot_cuts(self, t0: float, t1: float) -> list[float]:
        return [t for t in self.cuts if t0 <= t <= t1]


class TestEdgeSearch:
    def test_an_end_capped_by_the_next_line_stays_before_it(self):
        cues = [Cue(1, 90.0, 95.0, "♪ Last line ♪"), Cue(2, 100.0, 103.0, "Well, then.")]
        ep = FakeEpisode(cues, [98.0, 104.0])
        assert tail_end(ep, Part(1, 1), 5.0, True) == Edge(98.0, True)

    def test_a_start_by_of_zero_keeps_the_cold_open(self):
        ep = FakeEpisode([Cue(1, 30.0, 32.0, "♪ First line ♪")], [])
        assert lead_start(ep, Part(1, 1, start_by=0.0), 5.0, True).time == 0.0


class TestShotCuts:
    def test_window_times_get_the_window_start_back(self, tmp_path, monkeypatch):
        (tmp_path / "film.mkv").touch()
        ep = Episode(Show(tmp_path, "", "film.mkv", []), "")
        log = "[scdet @ 0x1] lavfi.scd.score: 17.204, lavfi.scd.time: 12.918\n"
        monkeypatch.setattr(
            "scripts.split_songs.run", lambda cmd: subprocess.CompletedProcess(cmd, 0, "", log)
        )
        assert ep.shot_cuts(1490.2, 1510.0) == [pytest.approx(1502.918)]


class TestMusicStart:
    CUES = [
        Cue(1, 10.0, 12.0, "So, a song?"),
        Cue(2, 14.0, 15.0, "[ guitar strumming ]"),
        Cue(3, 20.0, 22.0, "♪ First line ♪"),
    ]

    def test_set_by_hand(self):
        assert music_start(Part(3, 3, music_from=5.0), self.CUES) == 5.0

    def test_an_sdh_music_tag_after_the_last_spoken_line(self):
        assert music_start(Part(3, 3), self.CUES) == 13.0

    def test_no_tag_means_the_first_sung_line(self):
        assert music_start(Part(3, 3), [self.CUES[0], self.CUES[2]]) == 20.0


class TestCueText:
    LABELS = label_re(["both", "girls"])

    def test_strips_mixed_case_labels_and_lines_they_empty(self):
        assert cue_text("Both: Hey\n- Girls:\n- you", self.LABELS, None) == "Hey\n- you"

    def test_recase_keeps_tags_lowercase_and_restores_names(self):
        text = "( WHISPERING ) WHAT'S UP, CAROL BROWN? I'M FINE.\n- NEW ZEALAND"
        assert (
            recase(text, ["Carol Brown", "New Zealand"])
            == "( whispering ) What's up, Carol Brown? I'm fine.\n- New Zealand"
        )

    def test_recase_only_when_names_given(self):
        assert cue_text("HELLO THERE", None, None) == "HELLO THERE"
        assert cue_text("HELLO THERE", None, []) == "Hello there"


class TestClipSrt:
    def test_spoken_cues_by_midpoint_tags_by_overlap_across_joined_spans(self):
        cues = [
            Cue(1, 8.0, 11.0, "mostly before"),  # midpoint 9.5: out
            Cue(2, 9.0, 13.0, "mostly inside"),  # midpoint 11: in, clipped to 10
            Cue(3, 9.0, 10.5, "( music )"),  # overlaps: in
            Cue(4, 52.0, 53.0, "second part"),
        ]
        srt = clip_srt(cues, [(10.0, 20.0), (50.0, 60.0)])
        assert srt == (
            "1\n00:00:00,000 --> 00:00:03,000\nmostly inside\n\n"
            "2\n00:00:00,000 --> 00:00:00,500\n( music )\n\n"
            "3\n00:00:12,000 --> 00:00:13,000\nsecond part\n"
        )


class TestShowLoad:
    def test_reads_songs_and_finds_one_source(self, tmp_path):
        (tmp_path / "Season 1").mkdir()
        (tmp_path / "Season 1" / "Show S01E01.mkv").touch()
        config = tmp_path / "show.toml"
        config.write_text(
            'prefix = "Show - "\nsource = "Season */*{episode}*.mkv"\nlabels = ["both"]\n'
            '[[songs]]\nepisode = "S01E01"\ntitle = "Song"\n'
            "parts = [{ first = 3, last = 9, music_to = 50.5 }]\n"
        )
        show = Show.load(config)
        (song,) = show.songs
        assert song.parts == [Part(3, 9, music_to=50.5)]
        assert show.find(show.source, "S01E01").name == "Show S01E01.mkv"
        with pytest.raises(SystemExit):
            show.find(show.source, "S01E02")
