"""Render tests for the Queue page.

queue.html builds its rows in the browser, so what the server decides is which controls exist:
an admin gets the song menus and the footer, a guest gets the pinned pause-my-songs bar, and
both get the remove dialog. A template error is a 500 on the Queue page.
"""

import os
from unittest.mock import MagicMock

import pytest
import werkzeug
from flask import Flask, render_template
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

import pikaraoke
from pikaraoke.routes.admin import admin_bp
from pikaraoke.routes.queue import queue_bp

# Endpoints base.html and queue.html resolve via url_for that are not on queue_bp.
_STUB_ENDPOINTS = (
    "home.home",
    "search.search",
    "files.browse",
    "info.info",
    "processing.processing",
    "now_playing.now_playing",
)

ADMIN_PASSWORD = "secret"


def make_app(admin_password: str | None) -> Flask:
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    app.register_blueprint(queue_bp)
    app.register_blueprint(admin_bp)
    for endpoint in _STUB_ENDPOINTS:
        app.add_url_rule(f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda *a, **k: "")
    app.config.update(
        KARAOKE_INSTANCE=MagicMock(), ADMIN_PASSWORD=admin_password, SITE_NAME="PiKaraoke"
    )
    Babel(app)
    return app


@pytest.fixture
def guest_page() -> str:
    return make_app(ADMIN_PASSWORD).test_client().get("/queue").get_data(as_text=True)


@pytest.fixture
def admin_page() -> str:
    client = make_app(ADMIN_PASSWORD).test_client()
    client.set_cookie("admin", ADMIN_PASSWORD)
    return client.get("/queue").get_data(as_text=True)


def test_an_admin_gets_the_song_menus_and_the_footer(admin_page):
    assert "var isAdmin = true;" in admin_page
    for admin_only in (
        'id="song-options-modal"',
        'id="now-playing-options-modal"',
        'id="randomNumberInput"',
        "confirm-clear",
    ):
        assert admin_only in admin_page
    assert 'id="queue-brb"' not in admin_page


def test_a_guest_gets_the_pause_bar_and_none_of_the_admin_controls(guest_page):
    assert "var isAdmin = false;" in guest_page
    assert 'id="queue-brb"' in guest_page
    for admin_only in ('id="song-options-modal"', 'id="randomNumberInput"', "confirm-clear"):
        assert admin_only not in guest_page


def test_every_viewer_gets_the_remove_dialog_and_the_shared_row_stylesheet(admin_page, guest_page):
    for page in (admin_page, guest_page):
        assert 'id="remove-confirm-modal"' in page
        assert "phone-rows.css" in page


def test_with_no_admin_password_everyone_is_an_admin_and_nobody_sees_the_pause_bar():
    page = make_app(None).test_client().get("/queue").get_data(as_text=True)

    assert "var isAdmin = true;" in page
    assert 'id="queue-brb"' not in page


def bare_page(admin_password: str | None, *, admin_cookie: bool = False) -> str:
    """A page whose route passes no `admin`, so the nav sees only the context processor's."""
    app = make_app(admin_password)
    app.add_url_rule(
        "/__bare",
        endpoint="bare",
        view_func=lambda: render_template("base.html", site_title="PiKaraoke", title="Bare"),
    )
    client = app.test_client()
    if admin_cookie:
        client.set_cookie("admin", ADMIN_PASSWORD)
    return client.get("/__bare").get_data(as_text=True)


def test_the_processing_nav_icon_is_the_admins_only_on_a_page_that_passes_no_admin_flag():
    assert 'id="processing"' in bare_page(ADMIN_PASSWORD, admin_cookie=True)
    assert 'id="processing"' not in bare_page(ADMIN_PASSWORD)


def test_with_no_admin_password_everyone_gets_the_processing_nav_icon():
    assert 'id="processing"' in bare_page(None)


def test_the_queue_page_hides_the_processing_nav_icon_from_a_guest(admin_page, guest_page):
    assert 'id="processing"' in admin_page
    assert 'id="processing"' not in guest_page
