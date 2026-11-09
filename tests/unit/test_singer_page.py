"""Render test for the guest state base.html writes into every page.

A guest's name is free text and lands inside an inline script, so a name that closes the script
tag must stay inert. The state's own values are tested in test_singer_routes.py.
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
from pikaraoke.lib.singers import SingerRegistry, SingerSettings
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
