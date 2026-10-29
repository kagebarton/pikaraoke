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

    @staticmethod
    def _srt(*cues: str) -> str:
        return "\n".join(
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\n{cue}\n"
            for i, cue in enumerate(cues, start=1)
        )

    def test_all_caps_file_is_recased(self):
        texts, _ = cue_spans_from_srt(
            self._srt(
                "♪ I′M GOING UNDER,\nAND THIS TIME ♪",
                "'TIL I COME BACK AROUND",
                "WAIT. NOW I KNOW",
            )
        )
        assert texts == [
            "I'm going under, and this time",
            "'Til I come back around",
            "Wait. Now I know",
        ]

    def test_shouted_line_in_a_normal_file_stays_as_written(self):
        texts, _ = cue_spans_from_srt(
            self._srt("I'm going under", "and this time", "I fear there's no one", "HEY!")
        )
        assert texts == ["I'm going under", "and this time", "I fear there's no one", "HEY!"]

    def test_caseless_script_is_not_recased_by_its_acronyms(self):
        """A caseless script has no lower case to dilute the share, so
        counting only cased letters made a handful of Latin acronyms read
        as a fully capitalized file."""
        cues = ["DJ 放音乐", "走吧 OK", "你是我的 MVP"]
        texts, _ = cue_spans_from_srt(self._srt(*cues))
        assert texts == cues

    def test_speaker_label_on_its_own_line_drops_the_cue(self):
        texts, spans = cue_spans_from_srt(self._srt("ANNA:", "Hello there", "BOTH:"))
        assert texts == ["Hello there"]
        assert spans == [(2.0, 2.9)]

    def test_inline_speaker_label_is_stripped_and_listen_style_prose_survives(self):
        texts, _ = cue_spans_from_srt(
            self._srt(
                "ANNA: Hello there",
                "MR. POTTS: Be our guest",
                "<i>MEN: Be a man</i>",
                "Listen: it's time",
            )
        )
        assert texts == ["Hello there", "Be our guest", "Be a man", "Listen: it's time"]

    def test_label_after_a_dialogue_dash_or_star_is_stripped(self):
        texts, _ = cue_spans_from_srt(
            self._srt("- ANNA: Hello there", "BOB: * Sing along *", "Hi\nCARL: bye")
        )
        assert texts == ["Hello there", "Sing along", "Hi bye"]

    def test_labels_survive_in_an_all_caps_file(self):
        texts, _ = cue_spans_from_srt(self._srt("ANNA: HELLO THERE", "I FEAR THERE'S NO ONE"))
        assert texts == ["Anna: hello there", "I fear there's no one"]

    def test_standalone_stars_are_stripped_and_censored_words_keep_theirs(self):
        texts, _ = cue_spans_from_srt(self._srt("* Sing along *", "* Next line", "what the f***"))
        assert texts == ["Sing along", "Next line", "what the f***"]

    def test_dialogue_dashes_at_line_start_and_after_a_sentence_end_are_stripped(self):
        texts, _ = cue_spans_from_srt(
            self._srt(
                "- Hello there. - What?",
                "- One\n- Two",
                "* - Sing it",
                "♪ - Sing it",
            )
        )
        assert texts == ["Hello there. What?", "One Two", "Sing it", "Sing it"]

    def test_glued_dialogue_dashes_are_stripped(self):
        """Many releases write the dash against the word: "-What?", "Be a man -With all"."""
        texts, _ = cue_spans_from_srt(
            self._srt("-Hello there. -What?", "-One\n-Two", "-Be a man -With all", "--miss it")
        )
        assert texts == ["Hello there. What?", "One Two", "Be a man With all", "miss it"]

    def test_hyphens_inside_words_and_a_spaced_dash_mid_sentence_stay(self):
        texts, _ = cue_spans_from_srt(self._srt("nine-to-five", "won- derful", "wait - what"))
        assert texts == ["nine-to-five", "won- derful", "wait - what"]
