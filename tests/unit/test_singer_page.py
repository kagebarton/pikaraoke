"""Render tests for the guest parts base.html puts on every page.

A guest's name is free text and lands inside an inline script, so a name that closes the script
tag must stay inert. The name's link sits in the bar, not the burger menu, and the join form's
line draws the settings icon rather than printing it. The state's own values are tested in
test_singer_routes.py.
"""

import json
import os
import re
from unittest.mock import MagicMock

import pytest
import werkzeug
from flask import Flask, render_template
from flask_babel import Babel

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

import pikaraoke
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.singers import KEY_LIMIT, SingerRegistry, SingerSettings
from pikaraoke.routes.singer import singer_bp

# Endpoints base.html resolves via url_for.
_STUB_ENDPOINTS = (
    "home.home",
    "queue.queue",
    "search.search",
    "files.browse",
    "info.info",
    "processing.processing",
)


@pytest.fixture
def karaoke(tmp_path):
    k = MagicMock()
    preferences = PreferenceManager(config_file_path=str(tmp_path / "config.ini"))
    k.singers = SingerRegistry(preferences, MagicMock())
    k.is_transpose_enabled = True
    return k


@pytest.fixture
def app(karaoke):
    pkg_dir = os.path.dirname(pikaraoke.__file__)
    test_app = Flask(
        __name__,
        template_folder=os.path.join(pkg_dir, "templates"),
        static_folder=os.path.join(pkg_dir, "static"),
    )
    test_app.register_blueprint(singer_bp)
    for endpoint in _STUB_ENDPOINTS:
        test_app.add_url_rule(
            f"/__stub/{endpoint}", endpoint=endpoint, view_func=lambda *a, **k: ""
        )
    test_app.add_url_rule("/page", "page", lambda: render_template("base.html", site_title="Test"))
    test_app.config["KARAOKE_INSTANCE"] = karaoke
    Babel(test_app)
    return test_app


def page_state(client) -> dict:
    """What the page script reads: the `window.singer = ...;` line of the rendered page."""
    html = client.get("/page").get_data(as_text=True)
    [state] = re.findall(r"window\.singer = (\{.*\});", html)
    return json.loads(state)


def test_a_name_that_closes_the_script_tag_stays_inert(app, karaoke):
    name = "</script><img src=x onerror=alert(1)>"
    _, token = karaoke.singers.save(None, name, SingerSettings(0, 0.4, "karaoke"))
    phone = app.test_client()
    phone.set_cookie("singer_token", token)

    html = phone.get("/page").get_data(as_text=True)

    assert "</script><img" not in html
    assert page_state(phone)["name"] == name


def test_the_page_opens_on_its_doctype(app):
    html = app.test_client().get("/page").get_data(as_text=True)

    assert html.startswith("<!DOCTYPE html>")


def test_the_name_sits_in_the_bar_outside_the_burger_menu(app):
    html = app.test_client().get("/page").get_data(as_text=True)

    assert html.index('id="brand"') < html.index('id="current-user"') < html.index('id="menu"')


def test_the_join_line_draws_the_settings_icon(app):
    html = app.test_client().get("/page").get_data(as_text=True)

    [line] = re.findall(r'<p class="help singer-join-only">(.*?)</p>', html, re.DOTALL)
    assert '<svg class="sliders-icon"' in line
    assert "&lt;" not in line


def test_the_form_sets_original_vocals_and_key_with_the_shared_stepper(app):
    html = app.test_client().get("/page").get_data(as_text=True)

    ranges = re.findall(r'<input type="range" class="stepper-range" id="(singer-[\w-]+)"', html)
    assert ranges == ["singer-vocal-volume", "singer-key"]
    assert 'type="hidden" id="singer-key"' not in html


def test_the_forms_key_stops_at_the_guest_limit_and_has_its_note(app):
    html = app.test_client().get("/page").get_data(as_text=True)

    assert f'id="singer-key" min="-{KEY_LIMIT}" max="{KEY_LIMIT}"' in html
    heading = html.index('id="singer-key-heading"')
    assert (
        heading < html.index('class="info-tip"', heading) < html.index('id="singer-key"', heading)
    )
