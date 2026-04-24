"""Command-line argument parsing for PiKaraoke."""

import argparse
import logging
import os

from pikaraoke.lib.get_platform import get_default_dl_dir, get_platform
from pikaraoke.lib.preference_manager import PreferenceManager


def arg_path_parse(path: str | list[str] | None) -> str | None:
    """Convert a path argument to a string.

    Handles argparse nargs="+" which returns a list.

    Args:
        path: Path as string, list of strings, or None.

    Returns:
        Path as a single string (joined with spaces if list), or None.
    """
    if path is None:
        return None
    if isinstance(path, list):
        return " ".join(path)
    return path


def parse_volume(volume: str | float | None, volume_type: str) -> float | None:
    """Parse and validate a volume value.

    Args:
        volume: Volume value as string or float, or None if not provided.
        volume_type: Description of the volume type for error messages.

    Returns:
        Validated volume as float between 0 and 1, or None if not provided.
    """
    if volume is None:
        return None
    parsed_volume = float(volume)
    if parsed_volume > 1 or parsed_volume < 0:
        default = PreferenceManager.DEFAULTS["volume"]
        print(
            f"[ERROR] {volume_type}: {volume} must be between 0 and 1. Setting to default: {default}"
        )
        parsed_volume = default
    return parsed_volume


# Default values for non-preference CLI args only
# Preference defaults are in PreferenceManager.DEFAULTS (single source of truth)
platform = get_platform()
default_port = 5555
default_log_level = logging.INFO
default_config_file_path = "config.ini"
default_dl_dir = get_default_dl_dir(platform)

# Alias for cleaner help text formatting
_DEFAULTS = PreferenceManager.DEFAULTS


def parse_pikaraoke_args() -> argparse.Namespace:
    """Parse command-line arguments for PiKaraoke.

    Returns:
        Parsed arguments namespace with all configuration options.
    """
    parser = argparse.ArgumentParser()

    # --- Non-preference arguments (keep their own defaults) ---

    parser.add_argument(
        "-p",
        "--port",
        help=f"Desired http port (default: {default_port})",
        default=default_port,
        type=int,
        required=False,
    )
    parser.add_argument(
        "-d",
        "--download-path",
        nargs="+",
        help=f"Desired path for downloaded songs. (default: {default_dl_dir})",
        default=default_dl_dir,
        required=False,
    )
    parser.add_argument(
        "--youtubedl-proxy",
        help="Proxy server to use for youtube-dl, in case blocked by a firewall",
        required=False,
    )
    parser.add_argument(
        "--ytdl-args",
        help="Additional arguments to pass to youtube-dl/yt-dlp (as a single string)",
        required=False,
    )
    parser.add_argument(
        "-l",
        "--log-level",
        help=f"Logging level int value (DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50). (default: {default_log_level})",
        default=default_log_level,
        required=False,
    )
    parser.add_argument(
        "--logo-path",
        nargs="+",
        help="Path to a custom logo image file for the MPV window. Recommended dimensions ~ 2048x1024px",
        default=None,
        required=False,
    )
    parser.add_argument(
        "-u",
        "--url",
        help="Override the displayed IP address with a supplied URL. This argument should include port, if necessary",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--config-file-path",
        help=f"Path to a config file to load settings from. CLI arguments override and persist to this file. (default: {default_config_file_path})",
        default=default_config_file_path,
        required=False,
    )
    parser.add_argument(
        "--preferred-language",
        help="Set the preferred language for the web interface. This will persist across restarts. Available codes: en, de_DE, es_VE, fi_FI, fr_FR, id_ID,it_IT, ja_JP, ko_KR, nl_NL, no_NO, pt_BR, ru_RU, th_TH, zh_Hans_CN, zh_Hant_TW",
        default=None,
        required=False,
    )
    parser.add_argument(
        "--enable-swagger",
        action="store_true",
        help="Enable Swagger API documentation at /apidocs.",
        required=False,
    )

    # --- Preference arguments (default=None, use PreferenceManager.DEFAULTS for help text) ---

    parser.add_argument(
        "-v",
        "--volume",
        help=f"Set initial player volume. A value between 0 and 1. (default: {_DEFAULTS['volume']})",
        default=None,
        required=False,
    )
    parser.add_argument(
        "-n",
        "--normalize-audio",
        help="Normalize volume. May cause performance issues on slower devices",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-s",
        "--splash-delay",
        help=f"Delay during splash screen between songs (in secs). (default: {_DEFAULTS['splash_delay']})",
        default=None,
        type=int,
        required=False,
    )
    parser.add_argument(
        "--hide-url",
        action="store_true",
        help="Hide URL and QR code from the splash screen.",
        required=False,
    )
    parser.add_argument(
        "--hide-now-playing-overlay",
        action="store_true",
        help="Hide the now playing and up next overlays.",
        required=False,
    )
    parser.add_argument(
        "--hide-notifications",
        action="store_true",
        help="Hide notifications from the splash screen.",
        required=False,
    )
    parser.add_argument(
        "--show-clock",
        action="store_true",
        help="Show the digital clock overlay.",
        required=False,
    )
    parser.add_argument(
        "--high-quality",
        action="store_true",
        help="Download higher quality video. May cause CPU, download speed, and other performance issues",
        required=False,
    )
    parser.add_argument(
        "--limit-user-songs-by",
        help=f"Limit the number of songs a user can add to queue. User name 'Pikaraoke' is always unlimited (default: {_DEFAULTS['limit_user_songs_by']} = unlimited)",
        default=None,
        required=False,
    )
    args = parser.parse_args()

    # Additional sanitization of args (only process if provided)
    if args.volume is not None:
        args.volume = parse_volume(args.volume, "Volume")
    if args.limit_user_songs_by is not None:
        args.limit_user_songs_by = int(args.limit_user_songs_by)

    logo_path = arg_path_parse(args.logo_path)
    dl_path = os.path.expanduser(arg_path_parse(args.download_path) or default_dl_dir)

    args.logo_path = logo_path
    args.download_path = dl_path

    return args
