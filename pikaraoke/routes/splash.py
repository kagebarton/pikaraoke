"""Splash screen / player display route."""

import shutil
import subprocess

from flask import render_template
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name
from pikaraoke.lib.raspi_wifi_config import get_raspi_wifi_text


splash_bp = Blueprint("splash", __name__)


@splash_bp.route("/splash")
def splash():
    """Splash screen / player display for TV output."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    text = ""
    if k.is_raspberry_pi:
        has_iwconfig = shutil.which("iwconfig")
        has_iw = shutil.which("iw")
        if has_iwconfig or has_iw:
            # iwconfig is deprecated on Ubuntu, but still available on Raspbian
            command = "iwconfig" if has_iwconfig else "iw"
            status = subprocess.run([command, "wlan0"], stdout=subprocess.PIPE).stdout.decode(
                "utf-8"
            )
            if "Mode:Master" in status:
                # handle raspiwifi connection mode
                text = get_raspi_wifi_text()

    return render_template(
        "splash.html",
        site_title=site_name,
        blank_page=True,
        url=k.url,
        hostap_info=text,
        hide_url=k.hide_url,
        show_splash_clock=k.show_splash_clock,
        hide_overlay=k.hide_overlay,
        subtitle_delay=k.subtitle_delay,
    )
