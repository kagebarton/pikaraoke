"""Tests for preference routes — broadcast on change and reset."""

from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask

if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.routes.preferences import preferences_bp

ROUTE_PREFIX = "pikaraoke.routes.preferences"


@pytest.fixture
def app():
    test_app = Flask(__name__)
    test_app.secret_key = "test"
    test_app.register_blueprint(preferences_bp)
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def route_mocks():
    """Patch all external dependencies used by preference routes."""
    with (
        patch(f"{ROUTE_PREFIX}.get_karaoke_instance") as mock_get_instance,
        patch(f"{ROUTE_PREFIX}.is_admin", return_value=True),
        patch(f"{ROUTE_PREFIX}.broadcast_event") as mock_broadcast,
    ):
        mock_k = MagicMock()
        mock_get_instance.return_value = mock_k
        yield {
            "karaoke": mock_k,
            "broadcast": mock_broadcast,
        }


class TestChangePreferencesBroadcast:
    """Tests that change_preferences broadcasts Socket.IO events."""

    def test_broadcasts_preferences_update_on_success(self, client, route_mocks):
        route_mocks["karaoke"].preferences.set.return_value = (True, "Success")

        client.get("/change_preferences?pref=volume&val=0.5")

        route_mocks["broadcast"].assert_any_call(
            "preferences_update", {"key": "volume", "value": "0.5"}
        )

    def test_does_not_broadcast_on_failure(self, client, route_mocks):
        route_mocks["karaoke"].preferences.set.return_value = (False, "Error")

        client.get("/change_preferences?pref=volume&val=0.5")

        route_mocks["broadcast"].assert_not_called()


class TestClearPreferencesBroadcast:
    """Tests that clear_preferences broadcasts Socket.IO events."""

    def test_broadcasts_reset_on_success(self, client, route_mocks):
        route_mocks["karaoke"].preferences.reset_all.return_value = (True, "Success")

        client.get("/clear_preferences", follow_redirects=False)

        route_mocks["broadcast"].assert_called_once_with(
            "preferences_reset", PreferenceManager.DEFAULTS
        )

    def test_does_not_broadcast_on_reset_failure(self, client, route_mocks):
        route_mocks["karaoke"].preferences.reset_all.return_value = (False, "Error")

        client.get("/clear_preferences", follow_redirects=False)

        route_mocks["broadcast"].assert_not_called()
