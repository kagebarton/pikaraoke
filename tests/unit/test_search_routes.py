"""Unit tests for search routes: /lyrics_search, /lyrics_select and /caption_check."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import werkzeug
from flask import Flask

# Monkeypatch werkzeug.__version__ for Flask compatibility if missing
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.genius import GeniusClient, GeniusHit
from pikaraoke.lib.genius_query import ladder, parse
from pikaraoke.lib.library_regen import CaptionCheck
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
    """GET /lyrics_search: ``?title=`` finds the song a video is of, ``?q=`` searches as typed."""

    TITLE = "Rick Astley - Never Gonna Give You Up (Official Video)"  # a three-rung ladder
    SURE = GeniusHit(
        id=1,
        title="Never Gonna Give You Up",
        artist="Rick Astley",
        primary_artist="Rick Astley",
        year=1987,
        views=5000,
    )

    @pytest.fixture
    def genius(self, client):
        """The app's Genius client, replaced by one that finds nothing and records its calls."""
        k = _get_karaoke(client.application)
        k.genius_client = MagicMock(spec=GeniusClient)
        k.genius_client.search.return_value = []
        with patch("pikaraoke.routes.search.get_karaoke_instance", return_value=k):
            yield k.genius_client

    @staticmethod
    def _queries(genius) -> list[str]:
        return [call.args[0] for call in genius.search.call_args_list]

    def test_no_query_answers_empty_without_asking_genius(self, client, genius):
        for url in ("/lyrics_search", "/lyrics_search?q=", "/lyrics_search?q=+&title="):
            resp = client.get(url)
            assert resp.status_code == 200
            assert resp.json == {"hits": [], "preselect": None}
        genius.search.assert_not_called()

    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_genius_off_answers_empty_hits(self, mock_get_k, client):
        """A client with no token finds nothing for either form; the route still answers 200."""
        mock_get_k.return_value = _get_karaoke(client.application)
        typed = client.get("/lyrics_search?q=rick+astley")
        assert typed.status_code == 200
        assert typed.json == {"hits": [], "preselect": None}

        found = client.get("/lyrics_search", query_string={"title": self.TITLE, "channel": ""})
        assert found.status_code == 200
        assert found.json == {"hits": [], "preselect": None}

    def test_typed_text_is_one_call_as_typed_in_genius_order(self, client, genius):
        genius.search.return_value = [
            GeniusHit(id=200, title="Together Forever", artist="Rick Astley", year=1988),
            GeniusHit(id=100, title="Never Gonna Give You Up", artist="Rick Astley"),
        ]
        resp = client.get("/lyrics_search", query_string={"q": "  Rick Astley Karaoke_(HD) 🎤  "})

        genius.search.assert_called_once_with("Rick Astley Karaoke_(HD) 🎤")
        assert resp.status_code == 200
        assert resp.json == {
            "hits": [
                {"id": 200, "title": "Together Forever", "artist": "Rick Astley", "year": 1988},
                {
                    "id": 100,
                    "title": "Never Gonna Give You Up",
                    "artist": "Rick Astley",
                    "year": None,
                },
            ],
            "preselect": None,
        }

    def test_title_with_channel_asks_three_calls_of_twenty_hits(self, client, genius):
        rungs = ladder(parse(self.TITLE))
        assert len(rungs) >= 3

        resp = client.get("/lyrics_search", query_string={"title": self.TITLE, "channel": "Rick"})

        assert self._queries(genius) == rungs[:3]
        assert {call.kwargs["limit"] for call in genius.search.call_args_list} == {20}
        assert resp.status_code == 200

    def test_empty_channel_still_means_the_search_page(self, client, genius):
        client.get("/lyrics_search", query_string={"title": self.TITLE, "channel": ""})
        assert len(self._queries(genius)) == 3

    def test_title_without_channel_asks_two_calls(self, client, genius):
        client.get("/lyrics_search", query_string={"title": self.TITLE})
        assert self._queries(genius) == ladder(parse(self.TITLE))[:2]

    def test_typed_term_is_asked_last_and_only_when_a_call_is_left(self, client, genius):
        typed = "never gonna give you up lyrics"
        short = "Never Gonna Give You Up"  # two rungs with this channel: a third call is left
        args = {"title": short, "channel": "Rick Astley", "typed": typed}
        client.get("/lyrics_search", query_string=args)
        assert self._queries(genius) == [*ladder(parse(short, "Rick Astley")), typed]

        genius.search.reset_mock()  # three rungs use every call the search page allows
        client.get("/lyrics_search", query_string={**args, "title": self.TITLE})
        assert typed not in self._queries(genius)

    def test_a_sure_first_hit_is_preselected_and_ends_the_search(self, client, genius):
        genius.search.return_value = [self.SURE]
        resp = client.get("/lyrics_search", query_string={"title": self.TITLE, "channel": ""})

        assert len(self._queries(genius)) == 1
        assert resp.json == {
            "hits": [
                {"id": 1, "title": "Never Gonna Give You Up", "artist": "Rick Astley", "year": 1987}
            ],
            "preselect": 1,
        }

    def test_title_wins_when_both_are_sent(self, client, genius):
        client.get("/lyrics_search", query_string={"title": self.TITLE, "q": "something typed"})
        assert "something typed" not in self._queries(genius)


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
    def test_srt_mode_writes_sidecar(self, mock_get_k, mock_write, client):
        mock_get_k.return_value = _get_karaoke(client.application)

        resp = client.post(
            "/lyrics_select",
            data=json.dumps({"yt_id": "dQw4w9WgXcQ", "mode": "srt"}),
            content_type="application/json",
        )

        assert resp.status_code == 204
        mock_write.assert_called_once_with("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "mode": "srt"})

    @patch("pikaraoke.routes.search.write_choice")
    @patch("pikaraoke.routes.search.get_karaoke_instance")
    def test_raw_mode_is_turned_away_and_writes_nothing(self, mock_get_k, mock_write, client):
        """The dialog no longer offers Raw Transcription; the library tools write that choice
        themselves, so nothing sends it here."""
        mock_get_k.return_value = _get_karaoke(client.application)

        resp = client.post(
            "/lyrics_select",
            data=json.dumps({"yt_id": "dQw4w9WgXcQ", "mode": "raw"}),
            content_type="application/json",
        )

        assert resp.status_code == 400
        mock_write.assert_not_called()

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


# ---------------------------------------------------------------------------
# /caption_check
# ---------------------------------------------------------------------------


class TestCaptionCheck:
    """GET /caption_check → the dialog's one lookup: the caption's gate and the preview link."""

    @patch("pikaraoke.routes.search.check_video_caption")
    def test_checks_the_video_by_its_id_alone(self, mock_check, client):
        mock_check.return_value = (
            CaptionCheck(found=True, wpm=3.0, passed=False),
            "https://example.test/v",
        )

        resp = client.get("/caption_check?yt_id=dQw4w9WgXcQ")

        mock_check.assert_called_once_with("dQw4w9WgXcQ")
        assert resp.get_json() == {
            "found": True,
            "passed": False,
            "failed": False,
            "stream_url": "https://example.test/v",
        }

    @patch("pikaraoke.routes.search.check_video_caption")
    def test_no_link_answers_a_null_stream_url(self, mock_check, client):
        mock_check.return_value = (CaptionCheck(found=True, wpm=60.0, passed=True), None)

        resp = client.get("/caption_check?yt_id=dQw4w9WgXcQ")

        assert resp.get_json() == {
            "found": True,
            "passed": True,
            "failed": False,
            "stream_url": None,
        }

    @patch("pikaraoke.routes.search.check_video_caption")
    def test_invalid_yt_id_returns_400(self, mock_check, client):
        resp = client.get("/caption_check?yt_id=../etc")

        assert resp.status_code == 400
        mock_check.assert_not_called()

    def test_preview_is_gone(self, client):
        assert client.get("/preview?url=https://youtu.be/dQw4w9WgXcQ").status_code == 404

    @patch("pikaraoke.lib.youtube_dl._impersonate_args", return_value=[])
    @patch("pikaraoke.lib.youtube_dl.get_installed_js_runtime", return_value=None)
    def test_one_yt_dlp_call_answers_the_caption_and_the_link(
        self, mock_js, mock_impersonate, client, tmp_path, monkeypatch
    ):
        monkeypatch.setattr("pikaraoke.lib.library_regen.get_temp_directory", lambda: str(tmp_path))

        def fake_run(cmd, **kwargs):
            srt = cmd[cmd.index("-o") + 1].replace("%(ext)s", "en.srt")
            words = " ".join(["la"] * 60)
            Path(srt).write_text(f"1\n00:00:01,000 --> 00:00:04,000\n{words}\n", encoding="utf-8")
            return MagicMock(returncode=0, stdout=b"https://example.test/v.mp4\n60\n", stderr=b"")

        with patch("subprocess.run", side_effect=fake_run) as mock_run:
            resp = client.get("/caption_check?yt_id=dQw4w9WgXcQ")

        assert mock_run.call_count == 1
        assert resp.get_json() == {
            "found": True,
            "passed": True,
            "failed": False,
            "stream_url": "https://example.test/v.mp4",
        }
        assert list(tmp_path.iterdir()) == []
