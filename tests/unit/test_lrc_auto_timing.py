"""Tests for the LRCLIB check of a first-time download (lib/lrc_auto_timing.py).

The fit is the real one, run on small made-up songs; only the search is patched.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pikaraoke.lib import lrc_auto_pick, lrc_auto_timing, lrclib
from pikaraoke.lib.lrc_auto_timing import (
    ERROR,
    NO_PICK,
    NO_RECORDS,
    PICKED,
    SEARCH_FAILED,
    check,
    sheet_path,
)

GENIUS = {"id": 7, "title": "Some Song (Live)", "artist": "Artist (feat. Other)"}


def _word(i: int) -> str:
    return f"w{chr(97 + i // 26)}{chr(97 + i % 26)}x"


def _sung(lines: int) -> list[dict]:
    """The transcribe words of ``lines`` five-word lines sung 5 s apart from 10 s, in the
    shape the bundle stores them."""
    return [
        {"word": _word(k * 5 + i), "start": 10.0 + 5.0 * k + 0.6 * i, "end": 10.4 + 5.0 * k}
        for k in range(lines)
        for i in range(5)
    ]


def _lrc(lines: int) -> str:
    """A record's lines on the singing's clock."""

    def stamp(k: int) -> str:
        seconds = 10.0 + 5.0 * k
        return f"[{int(seconds) // 60:02d}:{seconds % 60:05.2f}]"

    return "".join(
        f"{stamp(k)} {' '.join(_word(k * 5 + i) for i in range(5))}\n" for k in range(lines)
    )


def _record(record_id: int, synced: str | None, album: str = "Album") -> dict:
    return {"id": record_id, "syncedLyrics": synced, "trackName": "Song", "albumName": album}


@pytest.fixture
def search():
    """Patch the search; set its result with ``search.return_value`` or ``side_effect``."""
    with patch.object(lrclib, "search_query", return_value=[]) as mock:
        yield mock


class TestPicked:
    def test_a_passing_record_is_picked_and_the_record_of_the_check_counts_the_search(self, search):
        whole, short = _lrc(30), _lrc(10)
        search.return_value = [
            _record(4, whole),
            _record(1, short),
            _record(2, short.replace("\n", " \n"), album="Other"),  # the same timing again
            _record(3, None),  # no synced text: not counted
        ]

        result = check(GENIUS, _sung(30), 300.0)

        assert result.outcome == PICKED
        assert result.entry.record["id"] == 4
        assert result.record() == {
            "outcome": "picked",
            "query": "Some Song Artist",
            "records": 3,
            "timings": 2,
            "passing": 1,
            "refusals": {"unclaimed": 2},
            "pick": {
                "id": 4,
                "trackName": "Song",
                "artistName": None,
                "albumName": "Album",
                "duration": None,
                "timing_size": 1,
                "mistimed": 0,
                "unclaimed_run": 0,
                "shift_run": 0,
                "shift_s": 0.0,
            },
        }

    def test_the_record_of_the_check_holds_no_lyric_text(self, search):
        search.return_value = [_record(4, _lrc(30))]

        text = json.dumps(check(GENIUS, _sung(30), 300.0).record())

        assert _word(0) not in text

    def test_the_search_is_sent_the_cleaned_title_and_artist_once(self, search):
        check(GENIUS, _sung(30), 300.0)

        search.assert_called_once_with("Some Song Artist")


class TestNotPicked:
    def test_no_record_passing_the_bar_is_no_pick_and_counts_why(self, search):
        search.return_value = [_record(1, _lrc(10))]

        result = check(GENIUS, _sung(30), 300.0)

        assert (result.outcome, result.entry) == (NO_PICK, None)
        assert result.record()["pick"] is None
        assert result.record()["refusals"] == {"unclaimed": 1}

    @pytest.mark.parametrize("records", [[], [_record(1, None), _record(2, "")]])
    def test_no_synced_record_is_no_records(self, search, records):
        search.return_value = records

        result = check(GENIUS, _sung(30), 300.0)

        assert (result.outcome, result.entry) == (NO_RECORDS, None)
        assert result.record()["records"] == 0
        assert result.record()["query"] == "Some Song Artist"

    def test_a_song_the_transcriber_heard_nothing_in_picks_nothing(self, search):
        search.return_value = [_record(1, _lrc(30))]

        result = check(GENIUS, [], 300.0)

        assert result.outcome == NO_PICK
        assert result.record()["refusals"] == {"no_fit": 1}

    def test_an_unreachable_lrclib_is_search_failed(self, search, caplog):
        search.side_effect = lrclib.LrclibUnavailable("LRCLIB search failed")

        result = check(GENIUS, _sung(30), 300.0)

        assert (result.outcome, result.entry) == (SEARCH_FAILED, None)
        assert result.record()["query"] == "Some Song Artist"
        assert "LRCLIB search failed" in caplog.text

    def test_a_failure_inside_the_fit_is_an_error_with_its_traceback_logged(
        self, search, monkeypatch, caplog
    ):
        search.return_value = [_record(1, _lrc(30))]

        def boom(*args):
            raise ValueError("fit exploded")

        monkeypatch.setattr(lrc_auto_pick, "fit_slice", boom)

        result = check(GENIUS, _sung(30), 300.0)

        assert (result.outcome, result.entry) == (ERROR, None)
        assert "fit exploded" in caplog.text
        assert "Traceback" in caplog.text

    def test_a_genius_identity_without_a_title_is_an_error_not_a_crash(self, search):
        assert check({"id": 7}, _sung(30), 300.0).outcome == ERROR
        search.assert_not_called()


class TestSheetPath:
    def test_the_sheet_sits_in_the_songs_lyrics_folder(self):
        song = Path("/lib/Artist - Song---aaaaaaaaaaa.mp4")

        assert sheet_path(song) == Path("/lib/lyrics/Artist - Song---aaaaaaaaaaa.lrclib-auto.srt")
        assert sheet_path(song).name.endswith(lrc_auto_timing.SHEET_SUFFIX)
