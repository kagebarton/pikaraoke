"""Unit tests for ffmpeg module."""

from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.ffmpeg import (
    get_ffmpeg_version,
    is_ffmpeg_installed,
    is_transpose_enabled,
)


class TestGetFfmpegVersion:
    """Tests for the get_ffmpeg_version function."""

    def test_version_parsed_correctly(self):
        """Test parsing FFmpeg version from output."""
        mock_result = MagicMock()
        mock_result.stdout = "ffmpeg version 5.1.2 Copyright (c) 2000-2022"

        with patch("subprocess.run", return_value=mock_result):
            result = get_ffmpeg_version()
            assert result == "5.1.2"

    def test_ffmpeg_not_installed(self):
        """Test handling when FFmpeg is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = get_ffmpeg_version()
            assert result == "FFmpeg is not installed"

    def test_unable_to_parse_version(self):
        """Test handling when version can't be parsed."""
        mock_result = MagicMock()
        mock_result.stdout = "unexpected format"

        with patch("subprocess.run", return_value=mock_result):
            result = get_ffmpeg_version()
            assert result == "Unable to parse FFmpeg version"


class TestIsTransposeEnabled:
    """Tests for the is_transpose_enabled function."""

    def test_rubberband_available(self):
        """Test when rubberband filter is available."""
        mock_result = MagicMock()
        mock_result.stdout = b"... rubberband ... other filters"

        with patch("subprocess.run", return_value=mock_result):
            assert is_transpose_enabled() is True

    def test_rubberband_not_available(self):
        """Test when rubberband filter is not available."""
        mock_result = MagicMock()
        mock_result.stdout = b"aecho, aresample, volume"

        with patch("subprocess.run", return_value=mock_result):
            assert is_transpose_enabled() is False

    def test_ffmpeg_not_installed(self):
        """Test when FFmpeg is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert is_transpose_enabled() is False


class TestIsFfmpegInstalled:
    """Tests for the is_ffmpeg_installed function."""

    def test_ffmpeg_installed(self):
        """Test when FFmpeg is installed."""
        with patch("subprocess.run", return_value=MagicMock()):
            assert is_ffmpeg_installed() is True

    def test_ffmpeg_not_installed(self):
        """Test when FFmpeg is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert is_ffmpeg_installed() is False


class TestIsTransposeEnabledIndexError:
    """Additional tests for is_transpose_enabled IndexError handling."""

    def test_index_error_returns_false(self):
        """Test that IndexError returns False."""
        with patch("subprocess.run", side_effect=IndexError):
            assert is_transpose_enabled() is False
