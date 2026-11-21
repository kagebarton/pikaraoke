"""Render tests for Now Playing (home.html): which controls each viewer is given.

The seek bar, Volume and Subtitle delay are the admin's, and a guest's Key stops at KEY_LIMIT
while the admin's reaches ADMIN_KEY_LIMIT. Hiding is all there is: the routes behind the
controls check nobody (ruled acceptable), so nothing here tests a refusal.
"""

import os
import re
from unittest.mock import MagicMock

import pytest
import werkzeug
from flask import Flask
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

import pikaraoke
from pikaraoke.lib.singers import ADMIN_KEY_LIMIT, KEY_LIMIT
from pikaraoke.routes.home import home_bp

ADMIN_PASSWORD = "secret"

# Endpoints home.html and base.html resolve via url_for, other than the home page itself.
_STUB_ENDPOINTS = (
    "queue.queue",
    "search.search",
    "files.browse",
    "info.info",
    "processing.processing",
    "now_playing.now_playing",
)

# The controls only the admin is given: the seek bar, Volume and Subtitle delay.
ADMIN_ONLY_IDS = ("seek-bar", "volume-slider", "subtitle-delay-slider")


@pytest.fixture
def karaoke():
    k = MagicMock()
    k.is_transpose_enabled = True
    k.volume = 0.85
    return k


def make_app(karaoke, admin_password):
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    app.register_blueprint(home_bp)
    for endpoint in _STUB_ENDPOINTS:
        app.add_url_rule(f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda *a, **k: "")
    app.config.update(KARAOKE_INSTANCE=karaoke, ADMIN_PASSWORD=admin_password, SITE_NAME="Test")
    Babel(app)
    return app


@pytest.fixture
def app(karaoke):
    return make_app(karaoke, ADMIN_PASSWORD)


def page(app, admin_cookie=None) -> str:
    client = app.test_client()
    if admin_cookie is not None:
        client.set_cookie("admin", admin_cookie)
    return client.get("/").get_data(as_text=True)


def key_range(html: str) -> tuple[int, int]:
    """The Key stepper's min and max."""
    [(low, high)] = re.findall(r'id="transpose" min="(-?\d+)" max="(\d+)"', html)
    return int(low), int(high)


def test_the_admin_has_every_control(app):
    html = page(app, admin_cookie=ADMIN_PASSWORD)

    for control_id in ADMIN_ONLY_IDS:
        assert f'id="{control_id}"' in html
    assert key_range(html) == (-ADMIN_KEY_LIMIT, ADMIN_KEY_LIMIT)


def test_a_guest_has_the_transport_key_and_lyrics_only(app):
    html = page(app)

    for control_id in ADMIN_ONLY_IDS:
        assert f'id="{control_id}"' not in html
    for control_id in ("restart", "pause-resume", "skip", "subtitle-mode-section"):
        assert f'id="{control_id}"' in html
    assert key_range(html) == (-KEY_LIMIT, KEY_LIMIT)


def test_a_wrong_admin_cookie_is_a_guest(app):
    html = page(app, admin_cookie="not-the-password")

    assert 'id="seek-bar"' not in html
    assert key_range(html) == (-KEY_LIMIT, KEY_LIMIT)


def test_without_transpose_there_is_no_key_stepper(app, karaoke):
    karaoke.is_transpose_enabled = False

    html = page(app, admin_cookie=ADMIN_PASSWORD)

    assert 'id="transpose"' not in html


def test_without_an_admin_password_everyone_is_the_admin(karaoke):
    html = page(make_app(karaoke, admin_password=None))

    for control_id in ADMIN_ONLY_IDS:
        assert f'id="{control_id}"' in html
    assert key_range(html) == (-ADMIN_KEY_LIMIT, ADMIN_KEY_LIMIT)
