"""Unit tests for scripts/song_select.py — pattern-to-video resolution."""

from pathlib import Path

import pytest

from scripts.song_select import select_songs


def _videos(*names: str) -> list[Path]:
    return [Path(f"/lib/{n}") for n in names]


class TestSelectSongs:
    def test_id_match(self):
        videos = _videos("Song---dQw4w9WgXcQ.mp4", "Other---abcdefghijk.mp4")
        assert select_songs(videos, ["dQw4w9WgXcQ"]) == videos[:1]

    def test_case_insensitive_substring_match(self):
        videos = _videos("My Great Song---dQw4w9WgXcQ.mp4", "Other---abcdefghijk.mp4")
        assert select_songs(videos, ["great song"]) == videos[:1]

    def test_no_match_raises(self):
        videos = _videos("Song---dQw4w9WgXcQ.mp4")
        with pytest.raises(ValueError, match="nope"):
            select_songs(videos, ["nope"])

    def test_multiple_matches_raises_and_lists_both(self):
        videos = _videos("Song One---dQw4w9WgXcQ.mp4", "Song Two---abcdefghijk.mp4")
        with pytest.raises(ValueError) as exc_info:
            select_songs(videos, ["Song"])
        message = str(exc_info.value)
        assert "Song One---dQw4w9WgXcQ.mp4" in message
        assert "Song Two---abcdefghijk.mp4" in message

    def test_two_patterns_naming_the_same_song_give_one_entry(self):
        videos = _videos("Song---dQw4w9WgXcQ.mp4", "Other---abcdefghijk.mp4")
        result = select_songs(videos, ["dQw4w9WgXcQ", "song"])
        assert result == videos[:1]

    def test_result_is_deduped_and_in_input_order(self):
        videos = _videos("A---dQw4w9WgXcQ.mp4", "B---abcdefghijk.mp4", "C---zzzzzzzzzzz.mp4")
        result = select_songs(videos, ["zzzzzzzzzzz", "dQw4w9WgXcQ"])
        assert result == [videos[0], videos[2]]
