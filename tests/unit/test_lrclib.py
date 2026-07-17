"""Tests for the LRCLIB fetch/select/persist helpers (lib/lrclib.py)."""

from unittest.mock import MagicMock, patch

import requests

from pikaraoke.lib import lrclib
from pikaraoke.lib.lrclib import (
    ensure_lrc,
    map_lines_to_cues,
    normalize_line,
    parse_lrc_lines,
)

_SYNCED_AB = "[00:01.00]hello world\n[00:05.00]goodbye world\n"


class TestCleanKey:
    def test_strips_parenthetical_and_feature_qualifiers(self):
        track, artist = lrclib.clean_key(
            "Best Part of Me (Live At Abbey Road)", "Ed Sheeran (Ft. Yebba)"
        )
        assert (track, artist) == ("Best Part of Me", "Ed Sheeran")

    def test_strips_trailing_feat(self):
        assert lrclib.clean_key("Song feat. Other", "Artist") == ("Song", "Artist")

    def test_leaves_clean_keys_untouched(self):
        assert lrclib.clean_key("Incomplete", "Backstreet Boys") == (
            "Incomplete",
            "Backstreet Boys",
        )

    def test_falls_back_when_cleaning_empties_a_field(self):
        # A title that is *only* a qualifier must not become empty.
        assert lrclib.clean_key("(Live)", "Artist") == ("(Live)", "Artist")


class TestSearch:
    @patch("pikaraoke.lib.lrclib.time.sleep")
    @patch("pikaraoke.lib.lrclib.requests.get")
    def test_parses_response_and_sends_cleaned_keys(self, mock_get, _sleep):
        resp = MagicMock()
        resp.json.return_value = [{"id": 1, "syncedLyrics": _SYNCED_AB}]
        mock_get.return_value = resp

        out = lrclib.search("Song (Remastered)", "Artist")

        assert out == [{"id": 1, "syncedLyrics": _SYNCED_AB}]
        assert mock_get.call_args.kwargs["params"] == {
            "track_name": "Song",
            "artist_name": "Artist",
        }

    @patch("pikaraoke.lib.lrclib.requests.get", side_effect=requests.RequestException("boom"))
    def test_network_error_returns_empty(self, _get):
        assert lrclib.search("T", "A") == []

    @patch("pikaraoke.lib.lrclib.time.sleep")
    @patch("pikaraoke.lib.lrclib.requests.get")
    def test_non_list_response_returns_empty(self, mock_get, _sleep):
        resp = MagicMock()
        resp.json.return_value = {"message": "not found"}
        mock_get.return_value = resp
        assert lrclib.search("T", "A") == []


class TestSelectCandidate:
    _SHEET = ["Hello world", "Goodbye world"]

    def test_picks_higher_mapping_rate(self):
        full = {"id": 1, "duration": 100.0, "syncedLyrics": _SYNCED_AB}
        partial = {"id": 2, "duration": 100.0, "syncedLyrics": "[00:01.00]hello world\n"}
        assert lrclib.select_candidate([partial, full], self._SHEET, None) is full

    def test_duration_breaks_map_rate_ties(self):
        near = {"id": 1, "duration": 198.0, "syncedLyrics": _SYNCED_AB}
        far = {"id": 2, "duration": 120.0, "syncedLyrics": _SYNCED_AB}
        assert lrclib.select_candidate([far, near], self._SHEET, 200.0) is near

    def test_none_when_no_synced_candidates(self):
        assert lrclib.select_candidate([{"id": 1, "plainLyrics": "x"}], self._SHEET, None) is None


class TestWriteReadLrc:
    def test_round_trips_synced_text_and_provenance(self, tmp_path):
        record = {
            "id": 42,
            "trackName": "T",
            "artistName": "A",
            "albumName": "Al",
            "duration": 187.0,
            "syncedLyrics": "[00:01.00]Hello\n[00:05.00]World\n",
        }
        path = tmp_path / "lyrics" / "Song.lrc"
        lrclib.write_lrc(path, record)

        text = path.read_text(encoding="utf-8")
        assert "[ti:T]" in text
        assert "[lrclib_id:42]" in text
        assert "[length:03:07]" in text

        synced, meta = lrclib.read_lrc(path)
        # duration round-trips via the [length] tag (whole-second precision).
        assert meta == {
            "id": 42,
            "trackName": "T",
            "artistName": "A",
            "albumName": "Al",
            "duration": 187.0,
        }
        # The header is invisible to the cue parser.
        texts, starts = parse_lrc_lines(synced)
        assert texts == ["Hello", "World"]
        assert starts == [1.0, 5.0]


class TestEnsureLrc:
    _RECORD = {
        "id": 7,
        "trackName": "T",
        "artistName": "A",
        "duration": 120.0,
        "syncedLyrics": _SYNCED_AB,
    }

    def test_reuses_on_disk_file_without_searching(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        lrc_dir = song_path.parent / "lyrics"
        lrc_dir.mkdir()
        existing = lrc_dir / f"{song_path.stem}.lrc"
        existing.write_text("[00:01.00]cached\n", encoding="utf-8")

        with patch("pikaraoke.lib.lrclib.search") as mock_search:
            result = ensure_lrc(song_path, "T", "A", ["hello world"], 120.0)

        assert result == existing
        mock_search.assert_not_called()

    @patch("pikaraoke.lib.lrclib.search")
    def test_fetches_selects_and_persists_on_a_miss(self, mock_search, tmp_path):
        mock_search.return_value = [self._RECORD]
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"

        result = ensure_lrc(song_path, "T", "A", ["hello world", "goodbye world"], 120.0)

        assert result == song_path.parent / "lyrics" / "Song---dQw4w9WgXcQ.lrc"
        assert result.is_file()
        assert "[lrclib_id:7]" in result.read_text(encoding="utf-8")

    @patch("pikaraoke.lib.lrclib.search", return_value=[])
    def test_no_candidate_persists_nothing_and_returns_none(self, _search, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"

        result = ensure_lrc(song_path, "T", "A", ["hello world"], 120.0)

        assert result is None
        assert not (song_path.parent / "lyrics").exists()


class TestCueSpansForLines:
    def test_maps_lrc_cues_onto_sheet(self):
        spans = lrclib.cue_spans_for_lines(_SYNCED_AB, ["Hello world", "Goodbye world"])
        # Each line ends at the next start; the last holds LRC_LAST_LINE_HOLD_S.
        assert spans == {0: (1.0, 5.0), 1: (5.0, 9.0)}

    def test_returns_none_when_nothing_maps(self):
        assert lrclib.cue_spans_for_lines(_SYNCED_AB, ["totally different lyric"]) is None


class TestNormalizeLine:
    def test_strips_punctuation_and_case(self):
        assert normalize_line("Don't stop, believin'!") == "dont stop believin"
        assert normalize_line("Don’t stop, believin’!") == "dont stop believin"

    def test_acute_accent_apostrophe_deleted_not_split(self):
        # U+00B4 NFKD-decomposes to space + combining mark; apostrophe
        # deletion must run before ASCII folding or "don´t" -> "don t".
        assert normalize_line("don´t") == "dont"

    def test_folds_homoglyphs_and_diacritics(self):
        assert normalize_line("as it did when we wеre young") == "as it did when we were young"
        assert normalize_line("cheese soufflé") == "cheese souffle"

    def test_strips_musical_notes_and_collapses_whitespace(self):
        assert normalize_line("♪  Hello   world ♪") == "hello world"

    def test_strips_html_tags_from_older_cleanup(self):
        assert normalize_line("<i>But I won't cry</i>") == "but i wont cry"


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

    def test_near_equal_drift_still_maps(self):
        # g-dropping between lyric variants must not break the pairing.
        bundle = ["I've been waitin' forever right here"]
        cues = ["I've been waiting forever right here"]
        assert map_lines_to_cues(bundle, cues) == {0: 0}

    def test_repeated_chorus_pairs_each_instance_to_its_own_cues(self):
        # Both sides contain the chorus twice; the bundle's first instance
        # has small text drift. Exact-equality block matching used to pair
        # bundle instance 2 with cue instance 1, shifting every chorus cue
        # by a whole section (observed on NSYNC - Paradise).
        chorus = [
            "and all this time I've always wondered",
            "as it did when we were young",
            "right here for this moment",
        ]
        drifted = [
            "and all this time I've always wondered",
            "as it did when we wеre young",  # Cyrillic е watermark
            "right here for this moment",
        ]
        bundle = ["intro line one"] + drifted + ["bridge line here"] + chorus
        cues = ["intro line one"] + chorus + ["bridge line here"] + chorus
        mapping = map_lines_to_cues(bundle, cues)
        assert mapping == {i: i for i in range(len(bundle))}
