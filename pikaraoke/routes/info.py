"""System information and settings page route."""

import flask_babel
import psutil
from flask import jsonify, render_template
from flask_smorest import Blueprint

from pikaraoke import VERSION
from pikaraoke.constants import LANGUAGES
from pikaraoke.lib.current_app import (
    get_admin_password,
    get_karaoke_instance,
    get_site_name,
    is_admin,
)
from pikaraoke.lib.get_platform import get_platform

_ = flask_babel.gettext


def _audio_devices_for_render(k) -> tuple[str, list[dict[str, str]]]:
    """Return (saved_device, devices) ensuring the saved device is selectable.

    If the saved device is not in the enumerated list (e.g. unplugged hardware),
    prepend a synthetic entry so the user can still see what is currently set
    instead of silently rebinding to ``auto`` on save.
    """
    saved = k.preferences.get_or_default("audio_device")
    devices = k.mpv_controller.list_audio_devices()
    if saved and saved != "auto" and not any(d["name"] == saved for d in devices):
        devices = [{"name": saved, "description": f"{saved} (unavailable)"}, *devices]
    return saved, devices


info_bp = Blueprint("info", __name__)


@info_bp.route("/info")
def info():
    """System information and settings page."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    url = k.url
    admin_password = get_admin_password()
    is_linux = get_platform() == "linux"

    preferred_language = k.preferences.get("preferred_language", "en")
    # youtube-dl
    youtubedl_version = k.youtubedl_version
    audio_device, audio_devices = _audio_devices_for_render(k)

    return render_template(
        "info.html",
        site_title=site_name,
        title="Info",
        url=url,
        admin=is_admin(),
        admin_password=admin_password,
        platform=k.platform,
        os_version=k.os_version,
        ffmpeg_version=k.ffmpeg_version,
        is_transpose_enabled=k.is_transpose_enabled,
        youtubedl_version=youtubedl_version,
        pikaraoke_version=VERSION,
        cpu=None,
        memory=None,
        disk=None,
        is_pi=k.is_raspberry_pi,
        is_linux=is_linux,
        volume=int(k.preferences.get_or_default("volume") * 100),
        hide_notifications=k.hide_notifications,
        hide_clock=k.hide_clock,
        hide_url=k.hide_url,
        hide_now_playing_overlay=k.hide_now_playing_overlay,
        splash_delay=k.splash_delay,
        normalize_audio=k.normalize_audio,
        high_quality=k.high_quality,
        subtitle_delay=k.preferences.get_or_default("subtitle_delay"),
        audio_delay=k.preferences.get_or_default("audio_delay"),
        vocal_volume=int(k.preferences.get_or_default("vocal_volume") * 100),
        limit_user_songs_by=k.limit_user_songs_by,
        enable_fair_queue=k.enable_fair_queue,
        languages=LANGUAGES,
        preferred_language=preferred_language,
        browse_results_per_page=k.browse_results_per_page,
        temp_dir=k.temp_dir,
        blocked_processing_words=k.preferences.get_or_default("blocked_processing_words"),
        genius_token=k.preferences.get("genius_token", ""),
        audio_device=audio_device,
        audio_devices=audio_devices,
    )


@info_bp.route("/info/stats")
def get_system_stats():
    """Get system statistics (CPU, Memory, Disk).

    Returns:
        JSON response with system stats.
    """
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 403

    # cpu
    try:
        # We can afford to block a bit here since it is async
        cpu = str(psutil.cpu_percent(interval=1)) + "%"
    except:
        cpu = _("CPU usage query unsupported")

    # mem
    memory = psutil.virtual_memory()
    available = round(memory.available / 1024.0 / 1024.0, 1)
    total = round(memory.total / 1024.0 / 1024.0, 1)
    memory_str = (
        str(available) + "MB free / " + str(total) + "MB total ( " + str(memory.percent) + "% )"
    )

    # disk
    disk = psutil.disk_usage("/")
    free = round(disk.free / 1024.0 / 1024.0 / 1024.0, 1)
    total = round(disk.total / 1024.0 / 1024.0 / 1024.0, 1)
    disk_str = str(free) + "GB free / " + str(total) + "GB total ( " + str(disk.percent) + "% )"

    return jsonify({"cpu": cpu, "memory": memory_str, "disk": disk_str})


@info_bp.route("/info/audio_devices")
def get_audio_devices():
    """Get available audio output devices from the running mpv player."""
    k = get_karaoke_instance()
    return jsonify({"devices": k.mpv_controller.list_audio_devices()})
