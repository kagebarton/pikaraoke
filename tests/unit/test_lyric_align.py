"""Unit tests for LyricAlignStage — Genius header parsing and conditional SRT write.

These tests cover the _load_lyrics and _should_write_srt changes introduced
by the Genius integration plan. The full alignment/transcription path is
already tested via test_lyric_conversion.py (line-object conversion helpers).
"""

from pathlib import Path

import pytest

from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage


# ---------------------------------------------------------------------------
# _load_lyrics — Genius header parsing (3-tuple return)
# ---------------------------------------------------------------------------


class TestLoadLyrics:
    """Tests for _load_lyrics returning (text, format, structure)."""

    @pytest.fixture
    def stage(self):
        """Create a LyricAlignStage with mocked worker and config."""
        from unittest.mock import MagicMock

        from pikaraoke.pipeline.config import PipelineConfig

        return LyricAlignStage(
            whisper_worker=MagicMock(),
            config=PipelineConfig(),
        )

    def test_srt_returns_srt_format_no_structure(self, stage, tmp_path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello\n"
            "2\n00:00:02,000 --> 00:00:03,000\nWorld\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(srt_file)
        assert fmt == "srt"
        assert structure is None
        assert "Hello" in text
        assert "World" in text

    def test_plain_txt_no_headers(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("Just some lyrics\nNo headers here\n", encoding="utf-8")

        text, fmt, structure = stage._load_lyrics(txt_file)
        assert fmt == "txt"
        assert structure is None
        assert "Just some lyrics" in text

    def test_genius_txt_with_headers(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse 1: Brian]\nHello world\n[Chorus]\nSing along\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(txt_file)

        assert fmt == "txt"
        assert structure is not None
        assert len(structure) == 2

        # text uses align_text (inline parens stripped)
        assert "Hello world" in text
        assert "Sing along" in text

        # structure has section info
        assert structure[0]["section"] == "Verse 1"
        assert structure[0]["speaker_label"] == "Brian"
        assert structure[1]["section"] == "Chorus"
        assert structure[1]["is_ensemble"] is True

    def test_genius_txt_strips_headers_from_text(self, stage, tmp_path):
        """Section header lines must NOT appear in the returned text."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse 1]\nFirst line\n[Chorus]\nSecond line\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(txt_file)
        assert "[Verse 1]" not in text
        assert "[Chorus]" not in text
        assert "First line" in text
        assert "Second line" in text

    def test_genius_txt_uses_align_text(self, stage, tmp_path):
        """align_text (inline parens stripped) is used for alignment text."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse]\n(I can't help) Falling in love\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(txt_file)

        # text (for alignment) should use align_text with parens stripped
        assert "Falling in love" in text
        # structure preserves full text with parens
        assert structure[0]["text"] == "(I can't help) Falling in love"
        assert structure[0]["align_text"] == "Falling in love"

    def test_genius_txt_empty_after_parsing(self, stage, tmp_path):
        """Genius txt where all lines are header-only falls back to plain txt."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("[Verse 1]\n[Chorus]\n", encoding="utf-8")

        text, fmt, structure = stage._load_lyrics(txt_file)
        # parse_genius_sections returns [], so the heuristic falls through
        # to the plain .txt branch
        assert fmt == "txt"
        assert structure is None


# ---------------------------------------------------------------------------
# _should_write_srt — conditional SRT write
# ---------------------------------------------------------------------------


class TestShouldWriteSrt:
    """Skip SRT generation when yt-dlp already provided one."""

    def test_no_existing_srt_returns_true(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        assert LyricAlignStage._should_write_srt(song) is True

    def test_existing_en_srt_returns_false(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.en.srt").write_text("existing")

        assert LyricAlignStage._should_write_srt(song) is False

    def test_existing_plain_srt_returns_false(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.srt").write_text("existing")

        assert LyricAlignStage._should_write_srt(song) is False

    def test_en_srt_takes_priority(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.en.srt").write_text("en")
        (subs / "Song---abc123.srt").write_text("plain")

        # Either existing SRT prevents writing
        assert LyricAlignStage._should_write_srt(song) is False
