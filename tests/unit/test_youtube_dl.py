"""Unit tests for youtube_dl module."""

import subprocess
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from pikaraoke.lib.youtube_dl import (
    _select_en_srt,
    build_ytdl_download_command,
    download_manual_en_subs,
    get_youtube_id_from_url,
    get_youtubedl_version,
    upgrade_youtubedl,
)


def _default_patches():
    """Return the standard patches for build_ytdl_download_command tests.

    Patches both get_installed_js_runtime and _impersonate_args so command
    construction is deterministic regardless of the test environment.
    """
    return (
        patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None),
        patch(
            "pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"]
        ),
    )


class TestGetYoutubeIdFromUrl:
    """Tests for the get_youtube_id_from_url function."""

    def test_standard_watch_url(self):
        """Test parsing standard youtube.com/watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert get_youtube_id_from_url(url) == "dQw4w9WgXcQ"

    def test_mobile_watch_url(self):
        """Test parsing m.youtube.com URL."""
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        assert get_youtube_id_from_url(url) == "dQw4w9WgXcQ"

    def test_short_url(self):
        """Test parsing youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert get_youtube_id_from_url(url) == "dQw4w9WgXcQ"

    def test_url_with_extra_params(self):
        """Test parsing URL with additional parameters after ?."""
        # Note: current implementation only strips params after second ?
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ?extra=param"
        assert get_youtube_id_from_url(url) == "dQw4w9WgXcQ"

    def test_short_url_with_params(self):
        """Test parsing short URL with parameters."""
        url = "https://youtu.be/dQw4w9WgXcQ?t=30"
        assert get_youtube_id_from_url(url) == "dQw4w9WgXcQ"

    def test_invalid_url_returns_none(self):
        """Test that invalid URL returns None."""
        url = "https://example.com/video"
        assert get_youtube_id_from_url(url) is None

    def test_empty_url_returns_none(self):
        """Test that empty URL returns None."""
        url = ""
        assert get_youtube_id_from_url(url) is None


class TestBuildYtdlDownloadCommand:
    """Tests for the build_ytdl_download_command function."""

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_basic_command(self, mock_js, mock_impersonate):
        """Test building basic download command."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "yt_dlp"
        assert "-f" in cmd
        assert "-o" in cmd
        output_idx = cmd.index("-o") + 1
        assert cmd[output_idx] == "%(title)s---%(id)s.%(ext)s"
        assert "--paths" in cmd
        paths_idx = cmd.index("--paths") + 1
        assert cmd[paths_idx] == "home:/songs"
        assert "https://www.youtube.com/watch?v=test123" in cmd

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_high_quality_format(self, mock_js, mock_impersonate):
        """Test that high quality uses correct format string."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
            high_quality=True,
        )
        format_idx = cmd.index("-f") + 1
        assert "bestvideo" in cmd[format_idx]
        assert "1080" in cmd[format_idx]

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_standard_quality_format(self, mock_js, mock_impersonate):
        """Test that standard quality uses 720p format."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
            high_quality=False,
        )
        format_idx = cmd.index("-f") + 1
        assert "bestvideo" in cmd[format_idx]
        assert "720" in cmd[format_idx]

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_with_proxy(self, mock_js, mock_impersonate):
        """Test command with proxy setting."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
            youtubedl_proxy="http://proxy:8080",
        )
        assert "--proxy" in cmd
        proxy_idx = cmd.index("--proxy") + 1
        assert cmd[proxy_idx] == "http://proxy:8080"

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_with_additional_args(self, mock_js, mock_impersonate):
        """Test command with additional arguments."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
            additional_args="--no-playlist --age-limit 18",
        )
        assert "--no-playlist" in cmd
        assert "--age-limit" in cmd
        assert "18" in cmd

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value="node")
    def test_with_js_runtime_node(self, mock_js, mock_impersonate):
        """Test that node JS runtime is added to command."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert "--js-runtimes" in cmd
        js_idx = cmd.index("--js-runtimes") + 1
        assert cmd[js_idx] == "node"

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value="deno")
    def test_deno_not_added(self, mock_js, mock_impersonate):
        """Test that deno JS runtime is NOT added (it's yt-dlp default)."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert "--js-runtimes" not in cmd

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value="bun")
    def test_with_js_runtime_bun(self, mock_js, mock_impersonate):
        """Test that bun JS runtime is added to command."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert "--js-runtimes" in cmd
        js_idx = cmd.index("--js-runtimes") + 1
        assert cmd[js_idx] == "bun"

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_vcodec_sort(self, mock_js, mock_impersonate):
        """Test that h264 codec sorting is included."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert "-S" in cmd
        sort_idx = cmd.index("-S") + 1
        assert cmd[sort_idx] == "vcodec:h264"

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_url_is_last_argument(self, mock_js, mock_impersonate):
        """Test that video URL is always the last argument."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
            youtubedl_proxy="http://proxy:8080",
            additional_args="--no-playlist",
        )
        assert cmd[-1] == "https://www.youtube.com/watch?v=test123"

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=["--impersonate", "chrome"])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_impersonate_included_when_available(self, mock_js, mock_impersonate):
        """Test that --impersonate chrome is added when curl_cffi is available."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert "--impersonate" in cmd
        imp_idx = cmd.index("--impersonate") + 1
        assert cmd[imp_idx] == "chrome"

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=[])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_impersonate_omitted_when_unavailable(self, mock_js, mock_impersonate):
        """Test that --impersonate is omitted when curl_cffi is not installed."""
        cmd = build_ytdl_download_command(
            video_url="https://www.youtube.com/watch?v=test123",
            download_path="/songs",
        )
        assert "--impersonate" not in cmd


class TestImpersonateArgs:
    """Tests for the _impersonate_args helper function."""

    @patch("pikaraoke.lib.youtube_dl._impersonate_args")
    def test_returns_impersonate_args_when_curl_cffi_installed(self, mock_fn):
        """Test that _impersonate_args returns impersonation flags."""
        mock_fn.return_value = ["--impersonate", "chrome"]
        from pikaraoke.lib.youtube_dl import _impersonate_args

        result = _impersonate_args()
        assert result == ["--impersonate", "chrome"]

    @patch("pikaraoke.lib.youtube_dl._impersonate_args")
    def test_returns_empty_when_curl_cffi_missing(self, mock_fn):
        """Test that _impersonate_args returns empty list without curl_cffi."""
        mock_fn.return_value = []
        from pikaraoke.lib.youtube_dl import _impersonate_args

        result = _impersonate_args()
        assert result == []

    def test_logs_warning_on_yt_dlp_version_mismatch(self, caplog):
        """Test that a curl_cffi/yt-dlp version mismatch logs a warning and disables --impersonate."""
        import builtins
        import logging as _logging

        from pikaraoke.lib import youtube_dl as ytdl

        fake_curl_cffi = MagicMock()
        fake_curl_cffi.__version__ = "0.15.0"
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "curl_cffi":
                return fake_curl_cffi
            if name == "yt_dlp.networking._curlcffi":
                raise ImportError(
                    "Only curl_cffi versions 0.5.10 and 0.10.x through 0.14.x are supported"
                )
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            with caplog.at_level(_logging.WARNING, logger=ytdl.__name__):
                result = ytdl._impersonate_args()

        assert result == []
        assert any("0.15.0" in r.message and "incompatible" in r.message for r in caplog.records)


class TestGetYoutubedlVersion:
    """Tests for the get_youtubedl_version function."""

    def test_returns_version_string(self):
        """Test that version string is returned."""
        with patch("subprocess.check_output", return_value=b"2024.01.01\n"):
            result = get_youtubedl_version()
            assert result == "2024.01.01"

    def test_calls_with_version_flag(self):
        """Test that --version flag is passed."""
        with patch("subprocess.check_output", return_value=b"2024.01.01") as mock_check:
            get_youtubedl_version()
            mock_check.assert_called_once_with([sys.executable, "-m", "yt_dlp", "--version"])


class TestUpgradeYoutubedl:
    """Tests for the upgrade_youtubedl function."""

    @patch("pikaraoke.lib.youtube_dl.get_youtubedl_version", return_value="2024.02.01")
    def test_successful_self_upgrade(self, mock_version):
        """Test successful self-upgrade via yt-dlp -U."""
        with patch("subprocess.check_output", return_value=b"Updated to 2024.02.01"):
            result = upgrade_youtubedl()
            assert result == "2024.02.01"

    def test_fallback_to_pip_upgrade(self):
        """Test fallback to pip when yt-dlp -U suggests pip (in venv, no --break-system-packages)."""
        pip_message = b"You installed yt-dlp with pip or using the wheel from PyPi"
        error = subprocess.CalledProcessError(1, "yt-dlp", pip_message)
        error.output = pip_message

        with patch(
            "pikaraoke.lib.youtube_dl.get_youtubedl_version", return_value="2024.02.01"
        ), patch("shutil.which", return_value=None), patch(
            "subprocess.check_output"
        ) as mock_check, patch(  # noqa: SIM117
            "pikaraoke.lib.youtube_dl.sys.prefix", "/venv"
        ), patch(
            "pikaraoke.lib.youtube_dl.sys.base_prefix", "/different"
        ):
            # First call raises error suggesting pip, second call succeeds
            mock_check.side_effect = [error, b"Successfully installed yt-dlp"]
            result = upgrade_youtubedl()

            assert result == "2024.02.01"
            # Check sys.executable -m pip was called (in a venv, no --break-system-packages)
            assert mock_check.call_count == 2
            second_call_args = mock_check.call_args_list[1][0][0]
            assert "-m" in second_call_args
            assert "pip" in second_call_args
            assert "--break-system-packages" not in second_call_args

    def test_pip_upgrade_adds_break_system_packages_for_system_install(self):
        """Test that --break-system-packages is added when in system install."""
        pip_message = b"You installed yt-dlp with pip or using the wheel from PyPi"
        error = subprocess.CalledProcessError(1, "yt-dlp", pip_message)
        error.output = pip_message

        with patch(
            "pikaraoke.lib.youtube_dl.get_youtubedl_version", return_value="2024.02.01"
        ), patch("shutil.which", return_value=None), patch(
            "subprocess.check_output"
        ) as mock_check, patch(  # noqa: SIM117
            "pikaraoke.lib.youtube_dl.sys.prefix", "/usr"
        ), patch(
            "pikaraoke.lib.youtube_dl.sys.base_prefix", "/usr"
        ):
            # First call raises error suggesting pip, second call succeeds
            mock_check.side_effect = [error, b"Successfully installed yt-dlp"]
            result = upgrade_youtubedl()

            assert result == "2024.02.01"
            # Check --break-system-packages was added for system install
            assert mock_check.call_count == 2
            second_call_args = mock_check.call_args_list[1][0][0]
            assert "-m" in second_call_args
            assert "pip" in second_call_args
            assert "--break-system-packages" in second_call_args

    @patch("pikaraoke.lib.youtube_dl.get_youtubedl_version", return_value="2024.01.01")
    def test_returns_version_after_upgrade(self, mock_version):
        """Test that current version is returned after upgrade."""
        with patch("subprocess.check_output", return_value=b"Already up to date"):
            result = upgrade_youtubedl()
            assert result == "2024.01.01"
            mock_version.assert_called_once_with()


class TestSelectEnSrt:
    """Tests for choosing the canonical caption from yt-dlp's output."""

    def test_prefers_exact_en_and_drops_extras(self, tmp_path):
        (tmp_path / "Song.en.srt").write_text("en", encoding="utf-8")
        (tmp_path / "Song.en-US.srt").write_text("us", encoding="utf-8")
        result = _select_en_srt(str(tmp_path), "Song")
        assert result == str(tmp_path / "Song.en.srt")
        assert (tmp_path / "Song.en.srt").read_text(encoding="utf-8") == "en"
        assert not (tmp_path / "Song.en-US.srt").exists()

    def test_promotes_variant_when_no_exact_en(self, tmp_path):
        (tmp_path / "Song.en-GB.srt").write_text("gb", encoding="utf-8")
        result = _select_en_srt(str(tmp_path), "Song")
        assert result == str(tmp_path / "Song.en.srt")
        assert (tmp_path / "Song.en.srt").read_text(encoding="utf-8") == "gb"

    def test_ignores_language_less_srt(self, tmp_path):
        # A pipeline-generated <stem>.srt must not be mistaken for a caption.
        (tmp_path / "Song.srt").write_text("generated", encoding="utf-8")
        assert _select_en_srt(str(tmp_path), "Song") is None
        assert (tmp_path / "Song.srt").exists()

    def test_none_when_no_srt(self, tmp_path):
        assert _select_en_srt(str(tmp_path), "Song") is None


class TestDownloadManualEnSubs:
    """Tests for downloading a manual English caption via yt-dlp."""

    def test_success_returns_path(self, tmp_path):
        dest = tmp_path / "subtitles"

        def fake_run(cmd, **kwargs):
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "Song.en.srt").write_text("1\n", encoding="utf-8")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        with _default_patches()[0], _default_patches()[1], patch(
            "subprocess.run", side_effect=fake_run
        ):
            result = download_manual_en_subs("https://yt/watch?v=x", str(dest), "Song")
        assert result == str(dest / "Song.en.srt")

    def test_no_caption_written_returns_none(self, tmp_path):
        dest = tmp_path / "subtitles"
        with _default_patches()[0], _default_patches()[1], patch(
            "subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b"")
        ):
            result = download_manual_en_subs("https://yt/watch?v=x", str(dest), "Song")
        assert result is None

    def test_nonzero_returncode_returns_none(self, tmp_path):
        dest = tmp_path / "subtitles"
        with _default_patches()[0], _default_patches()[1], patch(
            "subprocess.run", return_value=MagicMock(returncode=1, stdout=b"", stderr=b"boom")
        ):
            result = download_manual_en_subs("https://yt/watch?v=x", str(dest), "Song")
        assert result is None

    def test_timeout_returns_none(self, tmp_path):
        dest = tmp_path / "subtitles"
        with _default_patches()[0], _default_patches()[1], patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("yt-dlp", 60)
        ):
            result = download_manual_en_subs("https://yt/watch?v=x", str(dest), "Song")
        assert result is None
