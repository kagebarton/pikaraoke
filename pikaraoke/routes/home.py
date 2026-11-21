"""Home page route."""

import flask_babel
from flask import render_template
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.singers import ADMIN_KEY_LIMIT, KEY_LIMIT

_ = flask_babel.gettext


home_bp = Blueprint("home", __name__)


@home_bp.route("/")
def home():
    """Home page with now playing info and controls.

    Only the admin is given the seek bar, volume and subtitle delay, and a key range wider
    than a guest's. The routes behind them check nobody, so this hides them, nothing more.
    """
    k = get_karaoke_instance()
    site_name = get_site_name()
    admin = is_admin()
    return render_template(
        "home.html",
        site_title=site_name,
        title="Home",
        admin=admin,
        key_limit=ADMIN_KEY_LIMIT if admin else KEY_LIMIT,
        is_transpose_enabled=k.is_transpose_enabled,
        volume=k.volume,
    )
