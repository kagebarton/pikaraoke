"""Tests for the matcher-timing eval library (lib/alignment_eval.py)."""

import pytest

from pikaraoke.lib.alignment_eval import (
    GROSS_RESIDUAL_S,
    map_lines_to_cues,
    normalize_line,
    parse_lrc_lines,
    parse_reference_cues,
    placed_starts_from_line_objects,
    replay_joint_from_bundle,
    score_song,
)


class TestNormalizeLine:
    def test_strips_punctuation_and_case(self):
        assert normalize_line("Don't stop, believin'!") == "dont stop believin"
        assert normalize_line("Don’t stop, believin’!") == "dont stop believin"

    def test_strips_musical_notes_and_collapses_whitespace(self):
        assert normalize_line("♪  Hello   world ♪") == "hello world"

    def test_strips_html_tags_from_older_cleanup(self):
        assert normalize_line("<i>But I won't cry</i>") == "but i wont cry"


class TestParseReferenceCues:
    SRT = (
        "1\n00:00:05,000 --> 00:00:08,000\n♪ Hello world ♪\n\n"
        "2\n00:00:10,500 --> 00:00:12,000\n[Applause]\n\n"
        "3\n00:00:15,250 --> 00:00:18,000\nSecond line\n"
    )

    def test_keeps_cleaned_lines_with_timing(self):
        texts, starts = parse_reference_cues(self.SRT)
        assert texts == ["Hello world", "Second line"]
        assert starts == [5.0, 15.25]

    def test_dropped_cue_does_not_shift_timing_pairing(self):
        texts, starts = parse_reference_cues(self.SRT)
        assert dict(zip(texts, starts))["Second line"] == 15.25


class TestParseLrcLines:
    def test_basic_synced_lines(self):
        texts, starts = parse_lrc_lines(
            "[00:13.28] Tale as old as time\n[01:02.5] True as it can be\n"
        )
        assert texts == ["Tale as old as time", "True as it can be"]
        assert starts == [13.28, 62.5]

    def test_skips_metadata_unstamped_and_empty(self):
        lrc = "[ar:Artist]\n[offset:+200]\nno stamp here\n[00:10.00]\n[00:20.00] Real line\n"
        texts, starts = parse_lrc_lines(lrc)
        assert texts == ["Real line"]
        assert starts == [20.0]

    def test_multiple_stamps_emit_line_per_stamp_sorted(self):
        texts, starts = parse_lrc_lines("[00:30.00][00:10.00] Chorus\n[00:20.00] Verse\n")
        assert texts == ["Chorus", "Verse", "Chorus"]
        assert starts == [10.0, 20.0, 30.0]


class TestMapLinesToCues:
    def test_identical_lists_map_one_to_one(self):
        lines = ["alpha one", "beta two", "gamma three"]
        assert map_lines_to_cues(lines, list(lines)) == {0: 0, 1: 1, 2: 2}

    def test_cleanup_drift_in_punctuation_still_maps(self):
        bundle = ["don't stop", "♪ hello ♪"]
        cues = ["Dont stop!", "Hello"]
        assert map_lines_to_cues(bundle, cues) == {0: 0, 1: 1}

    def test_dropped_cue_skips_without_misparing(self):
        bundle = ["one", "two", "three"]
        cues = ["one", "three"]
        mapping = map_lines_to_cues(bundle, cues)
        assert mapping == {0: 0, 2: 1}

    def test_reworded_line_falls_out_of_mapping(self):
        bundle = ["one", "completely different words", "three"]
        cues = ["one", "two", "three"]
        mapping = map_lines_to_cues(bundle, cues)
        assert 1 not in mapping
        assert mapping[0] == 0 and mapping[2] == 2


class TestScoreSong:
    def test_constant_display_lead_scores_perfect(self):
        # Matcher placed every line exactly 0.8s after its cue: pure
        # display lead, fully absorbed by the offset fit.
        cues = {0: 10.0, 1: 20.0, 2: 30.0}
        placed = {lid: t + 0.8 for lid, t in cues.items()}
        s = score_song("x", placed, cues, ["a", "b", "c"], n_lines=3)
        assert s.offset_s == pytest.approx(0.8)
        assert s.median_abs_residual_s == 0.0
        assert s.pct_within_half_s == 100.0
        assert s.gross_count == 0

    def test_gross_misplacement_detected_after_offset_fit(self):
        cues = {0: 10.0, 1: 20.0, 2: 30.0, 3: 40.0, 4: 50.0}
        placed = {lid: t + 0.5 for lid, t in cues.items()}
        placed[2] = 95.0  # wrong chorus instance
        s = score_song("x", placed, cues, ["a"] * 5, n_lines=5)
        assert s.gross_count == 1
        assert s.worst[0]["line_id"] == 2
        assert s.worst[0]["residual_s"] > GROSS_RESIDUAL_S

    def test_unplaced_lines_excluded_from_scoring(self):
        cues = {0: 10.0, 1: 20.0, 2: 30.0}
        placed = {0: 10.1, 2: 30.1}  # line 1 never placed
        s = score_song("x", placed, cues, ["a", "b", "c"], n_lines=3)
        assert s.n_scored == 2
        assert s.n_mapped == 3

    def test_no_scored_lines_yields_zero_score(self):
        s = score_song("x", {}, {0: 1.0}, ["a"], n_lines=1)
        assert s.n_scored == 0
        assert s.pct_within_half_s == 0.0

    def test_worst_list_only_contains_gross_offenders(self):
        cues = {0: 10.0, 1: 20.0, 2: 30.0}
        placed = {0: 10.0, 1: 20.4, 2: 30.1}
        s = score_song("x", placed, cues, ["a", "b", "c"], n_lines=3)
        assert s.worst == []

    def test_drift_fit_absorbs_reference_tempo_mismatch(self):
        # Reference synced to a 5% slower master: delta grows linearly.
        cues = {i: 60.0 * i for i in range(5)}
        placed = {i: t * 1.05 + 3.0 for i, t in cues.items()}
        s = score_song("x", placed, cues, ["a"] * 5, n_lines=5, fit_drift=True)
        assert s.median_abs_residual_s == 0.0
        assert s.drift_s_per_min == pytest.approx(3.0)
        assert s.gross_count == 0

    def test_drift_fit_falls_back_on_structural_break(self):
        # Constant offset except an inserted-section block: the drift
        # model fits worse and must not be selected.
        cues = {i: 20.0 * i for i in range(8)}
        placed = {i: t + 1.0 for i, t in cues.items()}
        placed[6] += 50.0
        placed[7] += 50.0
        s = score_song("x", placed, cues, ["a"] * 8, n_lines=8, fit_drift=True)
        assert s.drift_s_per_min == 0.0
        assert s.gross_count == 2
        assert s.median_abs_residual_s == 0.0


class TestPlacedStartsFromLineObjects:
    def test_excludes_interp_and_absent(self):
        objs = [
            {"line_id": 0, "start": 1.0, "words": [{"word": "a"}]},
            {"line_id": 1, "start": 2.0, "words": [], "source": "interp"},
            {"line_id": 2, "start": None, "words": []},
            {"line_id": 3, "start": 4.0, "words": [{"word": "b"}]},
        ]
        assert placed_starts_from_line_objects(objs) == {0: 1.0, 3: 4.0}


class TestReplayJointFromBundle:
    def _bundle(self):
        # Two lines, two align words each, transcribe corroborating both.
        align_words = [
            {"word": "hello", "start": 1.0, "end": 1.4},
            {"word": "world", "start": 1.5, "end": 1.9},
            {"word": "second", "start": 5.0, "end": 5.4},
            {"word": "line", "start": 5.5, "end": 5.9},
        ]
        transcribe_words = [dict(w) for w in align_words]
        return {
            "song_stem": "test",
            "words": align_words,
            "transcribe_words": transcribe_words,
            "lyrics": {
                "lines": ["Hello world", "Second line"],
                "align_lines": ["Hello world", "Second line"],
            },
        }

    def test_replays_matcher_from_cached_inputs(self):
        line_objects, stats = replay_joint_from_bundle(self._bundle(), alpha=2.0, margin_s=0.3)
        starts = placed_starts_from_line_objects(line_objects)
        assert starts == {0: 1.0, 1: 5.0}
        assert stats["knobs"]["alpha"] == 2.0

    def test_missing_transcribe_words_raises(self):
        bundle = self._bundle()
        bundle["transcribe_words"] = None
        with pytest.raises(ValueError, match="lacks cached matcher inputs"):
            replay_joint_from_bundle(bundle, alpha=2.0, margin_s=0.3)
