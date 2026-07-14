"""Tests for the SRT provenance marker (lib/srt_provenance.py)."""

from pikaraoke.lib.srt_provenance import (
    clear_generated_marker,
    is_generated,
    mark_generated,
)


class TestSrtProvenance:
    def test_mark_generated_then_is_generated_true(self, tmp_path):
        srt_path = tmp_path / "song.srt"
        srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        mark_generated(srt_path)

        assert is_generated(srt_path) is True
        assert (tmp_path / "song.srt.generated").is_file()

    def test_no_marker_is_generated_false(self, tmp_path):
        srt_path = tmp_path / "song.srt"
        srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        assert is_generated(srt_path) is False

    def test_clear_generated_marker_removes_it(self, tmp_path):
        srt_path = tmp_path / "song.srt"
        srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
        mark_generated(srt_path)

        clear_generated_marker(srt_path)

        assert is_generated(srt_path) is False

    def test_clear_generated_marker_missing_is_noop(self, tmp_path):
        srt_path = tmp_path / "song.srt"
        srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        clear_generated_marker(srt_path)  # must not raise

        assert is_generated(srt_path) is False
