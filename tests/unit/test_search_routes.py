"""Unit tests for search routes — /lyrics_search and /lyrics_select."""

import json
from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask

# Monkeypatch werkzeug.__version__ for Flask compatibility if missing
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.genius import GeniusClient, GeniusHit
from pikaraoke.routes.search import search_bp

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path):
    """Create a Flask app for testing with mocked Karaoke instance."""
    test_app = Flask(__name__)
    test_app.secret_key = "test"
    test_app.register_blueprint(search_bp)
    test_app.extensions["babel"] = MagicMock()

    # Mock the Karaoke instance that routes access via current_app
    mock_karaoke = MagicMock()
    mock_karaoke.genius_client = GeniusClient(api_token="")  # always constructed (DD2)
    mock_karaoke.song_manager = MagicMock()
    mock_karaoke.song_manager.songs = MagicMock()
    mock_karaoke.download_path = "/fake/path"

    test_app.config["KARAOKE_INSTANCE"] = mock_karaoke
    test_app.config["SITE_NAME"] = "TestKaraoke"
    test_app.config["ADMIN_PASSWORD"] = None

    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


def _get_karaoke(app):
    return app.config["KARAOKE_INSTANCE"]


# ---------------------------------------------------------------------------
# /lyrics_search
# ---------------------------------------------------------------------------


class TestLyricsSearch:
    """GET /lyrics_search?q=<query> → JSON list of {id, title, artist}."""

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_empty_query_returns_empty_list(self, mock_get_k, client):
        mock_get_k.return_value = _get_karaoke(client.application)
        resp = client.get("/lyrics_search?q=")
        assert resp.status_code == 200
        assert resp.json == []

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_missing_query_returns_empty_list(self, mock_get_k, client):
        mock_get_k.return_value = _get_karaoke(client.application)
        resp = client.get("/lyrics_search")
        assert resp.status_code == 200
        assert resp.json == []

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_empty_token_returns_empty_list(self, mock_get_k, client):
        """GeniusClient with empty token returns [] — always 200, never gated (DD2)."""
        mock_get_k.return_value = _get_karaoke(client.application)
        resp = client.get("/lyrics_search?q=rick+astley")
        assert resp.status_code == 200
        assert resp.json == []

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_with_hits_returns_json(self, mock_get_k, client):
        """When Genius returns hits, route serializes them as JSON."""
        k = _get_karaoke(client.application)
        # Replace genius_client with one that returns hits
        k.genius_client = MagicMock(spec=GeniusClient)
        k.genius_client.search.return_value = [
            GeniusHit(id=100, title="Never Gonna Give You Up", artist="Rick Astley"),
            GeniusHit(id=200, title="Together Forever", artist="Rick Astley"),
        ]
        mock_get_k.return_value = k

        resp = client.get("/lyrics_search?q=rick+astley")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 2
        assert data[0]["id"] == 100
        assert data[0]["title"] == "Never Gonna Give You Up"
        assert data[0]["artist"] == "Rick Astley"

    @patch("pikaraoke.routes.search.clean_genius_query")
    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_uses_clean_genius_query(self, mock_get_k, mock_clean, client):
        """Route calls clean_genius_query instead of regex_tidy (DD8)."""
        k = _get_karaoke(client.application)
        k.genius_client = MagicMock(spec=GeniusClient)
        k.genius_client.search.return_value = []
        mock_get_k.return_value = k
        mock_clean.return_value = "cleaned query"

        client.get("/lyrics_search?q=rick+astley+karaoke")
        mock_clean.assert_called_once_with("rick astley karaoke")
        k.genius_client.search.assert_called_once_with("cleaned query")

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_search_failure_returns_empty(self, mock_get_k, client):
        """Genius search failure returns [] — never 500 (graceful degradation)."""
        k = _get_karaoke(client.application)
        k.genius_client = MagicMock(spec=GeniusClient)
        k.genius_client.search.return_value = []  # GeniusClient.search returns [] on failure
        mock_get_k.return_value = k

        resp = client.get("/lyrics_search?q=test")
        assert resp.status_code == 200
        assert resp.json == []


# ---------------------------------------------------------------------------
# /lyrics_select
# ---------------------------------------------------------------------------


class TestLyricsSelect:
    """POST /lyrics_select → writes sidecar, returns 204."""

    @patch("pikaraoke.routes.search.write_choice")
    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_genius_id_writes_sidecar(self, mock_get_k, mock_write, client):
        mock_get_k.return_value = _get_karaoke(client.application)
        mock_write.return_value = MagicMock()

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "dQw4w9WgXcQ",
                    "genius_id": 4848515,
                    "yt_title": "Rick Astley - Never Gonna Give You Up",
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 204
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][0] == "dQw4w9WgXcQ"
        assert call_args[0][1]["genius_id"] == 4848515

    @patch("pikaraoke.routes.search.write_choice")
    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_raw_mode_writes_sidecar(self, mock_get_k, mock_write, client):
        mock_get_k.return_value = _get_karaoke(client.application)
        mock_write.return_value = MagicMock()

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "dQw4w9WgXcQ",
                    "mode": "raw",
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 204
        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][0] == "dQw4w9WgXcQ"
        assert call_args[0][1]["mode"] == "raw"

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_invalid_yt_id_returns_400(self, mock_get_k, client):
        mock_get_k.return_value = _get_karaoke(client.application)

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "too-short",
                    "genius_id": 123,
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 400

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_yt_id_exactly_11_chars_accepted(self, mock_get_k, client):
        """Exactly 11 alphanumeric/underscore/dash chars should be accepted."""
        mock_get_k.return_value = _get_karaoke(client.application)

        with patch("pikaraoke.routes.search.write_choice") as mock_write:
            mock_write.return_value = MagicMock()
            resp = client.post(
                "/lyrics_select",
                data=json.dumps(
                    {
                        "yt_id": "dQw4w9WgXcQ",
                        "genius_id": 123,
                    }
                ),
                content_type="application/json",
            )

            assert resp.status_code == 204

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_yt_id_12_chars_rejected(self, mock_get_k, client):
        mock_get_k.return_value = _get_karaoke(client.application)

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "dQw4w9WgXcQ1",
                    "genius_id": 123,
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 400

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_missing_both_genius_id_and_mode_returns_400(self, mock_get_k, client):
        mock_get_k.return_value = _get_karaoke(client.application)

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "dQw4w9WgXcQ",
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 400

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_non_integer_genius_id_returns_400(self, mock_get_k, client):
        mock_get_k.return_value = _get_karaoke(client.application)

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "dQw4w9WgXcQ",
                    "genius_id": "not_a_number",
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 400

    @patch("pikaraoke.routes.search.write_choice")
    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_string_genius_id_coerced_to_int(self, mock_get_k, mock_write, client):
        """genius_id as a numeric string should be accepted and coerced."""
        mock_get_k.return_value = _get_karaoke(client.application)
        mock_write.return_value = MagicMock()

        resp = client.post(
            "/lyrics_select",
            data=json.dumps(
                {
                    "yt_id": "dQw4w9WgXcQ",
                    "genius_id": "12345",
                }
            ),
            content_type="application/json",
        )

        assert resp.status_code == 204
        call_args = mock_write.call_args
        assert call_args[0][1]["genius_id"] == 12345
