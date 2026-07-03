"""Tests for the SRT cue utilities (lib/srt_cues.py)."""

from pikaraoke.lib.srt_cues import cue_spans_from_srt, offset_mad_against_cues


class TestOffsetMadAgainstCues:
    """Direct tests of the pure offset-calibration step."""

    def test_consistent_anchors_fit_offset(self):
        anchors = [{"lid": i, "start": 10.0 * (i + 1)} for i in range(4)]
        cues = {i: (10.0 * (i + 1) - 1.5, 10.0 * (i + 1) - 1.5 + 2.0) for i in range(4)}
        stats = offset_mad_against_cues(anchors, cues)
        assert stats == {"n_anchors_fit": 4, "bailed": None, "offset_s": 1.5, "mad_s": 0.0}

    def test_few_anchors_bails_without_offset_or_mad(self):
        anchors = [{"lid": i, "start": 10.0 * (i + 1)} for i in range(3)]
        cues = {i: (10.0 * (i + 1) - 1.5, 10.0 * (i + 1) - 1.5 + 2.0) for i in range(3)}
        stats = offset_mad_against_cues(anchors, cues)
        assert stats == {"n_anchors_fit": 3, "bailed": "few_anchors"}

    def test_wide_spread_bails_but_still_reports_offset_and_mad(self):
        anchors = [{"lid": i, "start": 10.0 * (i + 1)} for i in range(4)]
        leads = (0.0, 0.9, 1.8, 3.6)
        cues = {
            i: (10.0 * (i + 1) - lead, 10.0 * (i + 1) - lead + 2.0) for i, lead in enumerate(leads)
        }
        stats = offset_mad_against_cues(anchors, cues)
        assert stats["bailed"] == "wide_spread"
        assert stats["n_anchors_fit"] == 4
        assert "offset_s" in stats and "mad_s" in stats

    def test_anchors_without_a_cue_are_ignored(self):
        anchors = [{"lid": 0, "start": 10.0}, {"lid": 99, "start": 999.0}]
        cues = {0: (8.5, 10.5)}
        stats = offset_mad_against_cues(anchors, cues)
        assert stats["n_anchors_fit"] == 1


class TestCueSpansFromSrt:
    def test_cleanup_and_spans_stay_parallel(self):
        srt_text = (
            "1\n00:00:01,000 --> 00:00:02,000\n(gentle music)\n"
            "\n2\n00:00:02,500 --> 00:00:04,000\n<i>♪ Hello\nworld ♪</i>\n"
        )
        texts, spans = cue_spans_from_srt(srt_text)
        assert texts == ["Hello world"]
        assert spans == [(2.5, 4.0)]
