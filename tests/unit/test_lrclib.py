"""Tests for the LRCLIB fetch/select/persist helpers (lib/lrclib.py)."""

from unittest.mock import MagicMock, patch

import requests

from pikaraoke.lib import lrclib
from pikaraoke.lib.alignment_eval import parse_lrc_lines

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


class TestCueSpansForLines:
    def test_maps_lrc_cues_onto_sheet(self):
        spans = lrclib.cue_spans_for_lines(_SYNCED_AB, ["Hello world", "Goodbye world"])
        # Each line ends at the next start; the last holds LRC_LAST_LINE_HOLD_S.
        assert spans == {0: (1.0, 5.0), 1: (5.0, 9.0)}

    def test_returns_none_when_nothing_maps(self):
        assert lrclib.cue_spans_for_lines(_SYNCED_AB, ["totally different lyric"]) is None
