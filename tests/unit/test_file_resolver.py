"""Unit tests for file_resolver module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.file_resolver import (
    FileResolver,
    create_tmp_dir,
    delete_tmp_dir,
    get_tmp_dir,
    is_transcoding_required,
    string_to_hash,
)


class TestIsTranscodingRequired:
    """Tests for the is_transcoding_required function."""

    def test_mp4_no_transcoding(self):
        """Test that .mp4 files don't need transcoding."""
        assert is_transcoding_required("/songs/video.mp4") is False

    def test_webm_no_transcoding(self):
        """Test that .webm files don't need transcoding."""
        assert is_transcoding_required("/songs/video.webm") is False

    def test_mkv_needs_transcoding(self):
        """Test that .mkv files need transcoding."""
        assert is_transcoding_required("/songs/video.mkv") is True

    def test_avi_needs_transcoding(self):
        """Test that .avi files need transcoding."""
        assert is_transcoding_required("/songs/video.avi") is True

    def test_mov_needs_transcoding(self):
        """Test that .mov files need transcoding."""
        assert is_transcoding_required("/songs/video.mov") is True

    def test_case_insensitive_mp4(self):
        """Test that MP4 detection is case insensitive."""
        assert is_transcoding_required("/songs/video.MP4") is False
        assert is_transcoding_required("/songs/video.Mp4") is False

    def test_case_insensitive_webm(self):
        """Test that WEBM detection is case insensitive."""
        assert is_transcoding_required("/songs/video.WEBM") is False
        assert is_transcoding_required("/songs/video.WebM") is False


class TestStringToHash:
    """Tests for the string_to_hash function."""

    def test_returns_positive_integer(self):
        """Test that hash is always positive."""
        result = string_to_hash("test string")
        assert isinstance(result, int)
        assert result >= 0

    def test_consistent_hashing(self):
        """Test that same input produces same hash."""
        hash1 = string_to_hash("same input")
        hash2 = string_to_hash("same input")
        assert hash1 == hash2

    def test_different_inputs_different_hashes(self):
        """Test that different inputs produce different hashes."""
        hash1 = string_to_hash("input one")
        hash2 = string_to_hash("input two")
        assert hash1 != hash2

    def test_empty_string(self):
        """Test hashing empty string."""
        result = string_to_hash("")
        assert isinstance(result, int)
        assert result >= 0

    def test_unicode_string(self):
        """Test hashing unicode string."""
        result = string_to_hash("こんにちは世界")
        assert isinstance(result, int)
        assert result >= 0

    def test_long_string(self):
        """Test hashing a very long string."""
        long_string = "a" * 10000
        result = string_to_hash(long_string)
        assert isinstance(result, int)
        assert result >= 0


class TestGetTmpDir:
    """Tests for the get_tmp_dir function."""

    def test_returns_string(self):
        """Test that get_tmp_dir returns a string path."""
        result = get_tmp_dir()
        assert isinstance(result, str)

    def test_includes_pid(self):
        """Test that temp dir includes process ID."""
        result = get_tmp_dir()
        assert str(os.getpid()) in result

    def test_consistent_path(self):
        """Test that repeated calls return same path."""
        path1 = get_tmp_dir()
        path2 = get_tmp_dir()
        assert path1 == path2


class TestCreateTmpDir:
    """Tests for the create_tmp_dir function."""

    def test_creates_directory(self, tmp_path):
        """Test that create_tmp_dir creates the directory."""
        with patch(
            "pikaraoke.lib.file_resolver.get_tmp_dir", return_value=str(tmp_path / "test_tmp")
        ):
            create_tmp_dir()
            assert (tmp_path / "test_tmp").exists()

    def test_idempotent(self, tmp_path):
        """Test that create_tmp_dir doesn't fail if dir exists."""
        test_dir = tmp_path / "test_tmp"
        test_dir.mkdir()
        with patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value=str(test_dir)):
            create_tmp_dir()  # Should not raise
            assert test_dir.exists()


class TestDeleteTmpDir:
    """Tests for the delete_tmp_dir function."""

    def test_deletes_directory(self, tmp_path):
        """Test that delete_tmp_dir removes the directory."""
        test_dir = tmp_path / "test_tmp"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("test")

        with patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value=str(test_dir)):
            delete_tmp_dir()
            assert not test_dir.exists()

    def test_handles_nonexistent_dir(self, tmp_path):
        """Test that delete_tmp_dir handles nonexistent directory."""
        with patch(
            "pikaraoke.lib.file_resolver.get_tmp_dir", return_value=str(tmp_path / "nonexistent")
        ):
            delete_tmp_dir()  # Should not raise


class TestFileResolverInit:
    """Tests for FileResolver initialization."""

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_init_mp4_file(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test FileResolver initialization with MP4 file."""
        test_file = tmp_path / "song.mp4"
        test_file.touch()

        fr = FileResolver(str(test_file))

        assert fr.file_path == str(test_file)
        assert fr.file_extension == ".mp4"
        assert fr.tmp_dir == "/tmp/12345"
        assert fr.duration == 180
        assert fr.streaming_format == "hls"
        assert ".m3u8" in fr.output_file

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=200)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_init_mp4_streaming_format(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test FileResolver with mp4 streaming format."""
        test_file = tmp_path / "song.mp4"
        test_file.touch()

        fr = FileResolver(str(test_file), streaming_format="mp4")

        assert fr.streaming_format == "mp4"
        assert ".mp4" in fr.output_file

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_init_sets_segment_pattern(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test that init sets segment pattern and init filename."""
        test_file = tmp_path / "song.mp4"
        test_file.touch()

        fr = FileResolver(str(test_file))

        assert "_segment_" in fr.segment_pattern
        assert "_init.mp4" in fr.init_filename


class TestFileResolverHandleAegissubSubtitle:
    """Tests for FileResolver.handle_aegissub_subtile method."""

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_finds_ass_file(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test finding .ass subtitle file."""
        video_file = tmp_path / "song.mp4"
        subtitles_dir = tmp_path / "subtitles"
        subtitles_dir.mkdir()
        ass_file = subtitles_dir / "song.ass"
        video_file.touch()
        ass_file.touch()

        fr = FileResolver(str(video_file))

        assert fr.ass_file_path == str(ass_file)

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_finds_uppercase_ass_file(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test finding .ASS subtitle file (uppercase)."""
        video_file = tmp_path / "song.mp4"
        subtitles_dir = tmp_path / "subtitles"
        subtitles_dir.mkdir()
        ass_file = subtitles_dir / "song.ASS"
        video_file.touch()
        ass_file.touch()

        fr = FileResolver(str(video_file))

        assert fr.ass_file_path.casefold() == str(ass_file).casefold()

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_no_ass_file(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test when no .ass file exists."""
        video_file = tmp_path / "song.mp4"
        video_file.touch()

        fr = FileResolver(str(video_file))

        assert fr.ass_file_path is None


class TestFileResolverGetCurrentStreamSize:
    """Tests for FileResolver.get_current_stream_size method."""

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    def test_calculates_stream_size(self, mock_create, mock_duration, tmp_path):
        """Test calculating size of stream files."""
        video_file = tmp_path / "song.mp4"
        video_file.touch()

        with patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value=str(tmp_path)):
            fr = FileResolver(str(video_file))

            # Create some fake stream segment files
            segment1 = tmp_path / f"{fr.stream_uid}_segment_001.m4s"
            segment2 = tmp_path / f"{fr.stream_uid}_segment_002.m4s"
            segment1.write_bytes(b"x" * 1000)
            segment2.write_bytes(b"x" * 2000)

            size = fr.get_current_stream_size()

            assert size == 3000

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    def test_returns_zero_when_no_segments(self, mock_create, mock_duration, tmp_path):
        """Test returns 0 when no stream segments exist."""
        video_file = tmp_path / "song.mp4"
        video_file.touch()

        with patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value=str(tmp_path)):
            fr = FileResolver(str(video_file))
            size = fr.get_current_stream_size()

            assert size == 0


class TestFileResolverProcessFile:
    """Tests for FileResolver.process_file method."""

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_process_mp4(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test processing MP4 file."""
        video_file = tmp_path / "song.mp4"
        video_file.touch()

        fr = FileResolver(str(video_file))

        assert fr.file_extension == ".mp4"
        assert fr.file_path == str(video_file)

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_process_webm(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test processing WebM file."""
        video_file = tmp_path / "song.webm"
        video_file.touch()

        fr = FileResolver(str(video_file))

        assert fr.file_extension == ".webm"
        assert fr.file_path == str(video_file)

    @patch("pikaraoke.lib.file_resolver.get_media_duration", return_value=180)
    @patch("pikaraoke.lib.file_resolver.create_tmp_dir")
    @patch("pikaraoke.lib.file_resolver.get_tmp_dir", return_value="/tmp/12345")
    def test_process_mkv(self, mock_tmp, mock_create, mock_duration, tmp_path):
        """Test processing MKV file."""
        video_file = tmp_path / "song.mkv"
        video_file.touch()

        fr = FileResolver(str(video_file))

        assert fr.file_extension == ".mkv"
        assert fr.file_path == str(video_file)
