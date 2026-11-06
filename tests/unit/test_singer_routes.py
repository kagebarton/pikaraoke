"""Unit tests for the guest join route and the page state every template gets."""

import json
from unittest.mock import MagicMock

import pytest
import werkzeug
from flask import Flask, render_template_string
from flask_babel import Babel

# Monkeypatch werkzeug.__version__ for Flask compatibility if missing
if not hasattr(werkzeug, "__version__"):
    werkzeug.__version__ = "3.0.0"

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.preference_manager import PreferenceManager
from pikaraoke.lib.queue_manager import QueueManager
from pikaraoke.lib.singers import SingerRegistry, SingerSettings
from pikaraoke.routes.singer import singer_bp

SONG = "/songs/Artist - Song---dQw4w9WgXcQ.mp4"


@pytest.fixture
def karaoke(tmp_path):
    """A Karaoke stand-in with a real registry and queue, so a rename really moves songs."""
    events = EventSystem()
    preferences = PreferenceManager(config_file_path=str(tmp_path / "config.ini"))
    k = MagicMock()
    k.preferences = preferences
    k.singers = SingerRegistry(preferences)
    k.queue_manager = QueueManager(preferences=preferences, events=events)
    k.rename_singer.side_effect = k.queue_manager.rename_user
    k.is_transpose_enabled = True
    return k


@pytest.fixture
def app(karaoke):
    test_app = Flask(__name__)
    Babel(test_app)
    test_app.register_blueprint(singer_bp)
    test_app.config["KARAOKE_INSTANCE"] = karaoke
    # Any page: its template sees the `singer` the context processor gives every template
    test_app.add_url_rule("/state", "state", lambda: render_template_string("{{ singer|tojson }}"))
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


def save(client, name="Mike", semitones=2, vocal_volume=0.7):
    return client.post(
        "/singer", data={"name": name, "semitones": semitones, "vocal_volume": vocal_volume}
    )


def as_phone(app, name, token):
    """A client holding the cookies the page sets after joining."""
    phone = app.test_client()
    phone.set_cookie("user", name)
    phone.set_cookie("singer_token", token)
    return phone


def join(app, karaoke, name="Mike", settings=SingerSettings(2, 0.7)):
    held, token = karaoke.singers.join(name, settings)
    return as_phone(app, held, token), held, token


class TestJoin:
    def test_a_new_guest_joins_and_gets_their_name_and_token(self, client, karaoke):
        response = save(client, "Mike", semitones=2, vocal_volume=0.7)

        body = response.get_json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["name"] == "Mike"
        assert karaoke.singers.owns("Mike", body["token"])
        assert karaoke.singers.settings_for("Mike") == SingerSettings(2, 0.7)

    def test_a_blank_name_becomes_an_anon_name(self, client):
        body = save(client, name="").get_json()

        assert body["name"].startswith("Anon-")

    def test_the_route_sets_no_cookies(self, client):
        response = save(client)

        assert response.headers.getlist("Set-Cookie") == []

    @pytest.mark.parametrize("taken_as", ["Mike", "mike"])
    def test_a_name_in_use_is_refused_with_409(self, app, karaoke, taken_as):
        join(app, karaoke, "Mike")

        response = save(app.test_client(), taken_as)

        assert response.status_code == 409
        body = response.get_json()
        assert body["success"] is False
        assert body["error"] == "That name is already taken. Please choose another."

    @pytest.mark.parametrize("name", ["Randomizer", "pikaraoke"])
    def test_a_reserved_name_is_refused_with_409(self, client, name):
        assert save(client, name).status_code == 409

    def test_a_refusal_adds_no_guest(self, app, karaoke):
        join(app, karaoke, "Mike")
        save(app.test_client(), "mike", semitones=-3, vocal_volume=0.0)

        assert karaoke.singers.settings_for("Mike") == SingerSettings(2, 0.7)

    def test_a_wrong_token_on_a_known_name_is_a_join_and_gets_409(self, app, karaoke):
        join(app, karaoke, "Mike")
        impostor = as_phone(app, "Mike", "not-their-token")

        response = save(impostor, "Mike", semitones=-3)

        assert response.status_code == 409
        assert karaoke.singers.settings_for("Mike") == SingerSettings(2, 0.7)

    def test_a_name_with_a_space_or_an_accent_is_found_again_from_its_encoded_cookie(
        self, app, karaoke
    ):
        """The page stores the name percent-encoded, so Mary Ann arrives as Mary%20Ann."""
        _, held, token = join(app, karaoke, "José Mary")
        phone = as_phone(app, "Jos%C3%A9%20Mary", token)

        response = save(phone, "José Mary", semitones=-1, vocal_volume=0.2)

        assert response.status_code == 200
        assert response.get_json()["name"] == held
        assert karaoke.singers.settings_for(held) == SingerSettings(-1, 0.2)


class TestValidation:
    @pytest.mark.parametrize("semitones", [-4, 4, 12])
    def test_a_key_beyond_the_limit_is_422(self, client, semitones):
        assert save(client, semitones=semitones).status_code == 422

    @pytest.mark.parametrize("semitones", [-3, 0, 3])
    def test_a_key_within_the_limit_is_accepted(self, client, semitones):
        assert save(client, name=f"S{semitones}", semitones=semitones).status_code == 200

    @pytest.mark.parametrize("vocal_volume", [-0.1, 1.1, 5])
    def test_a_vocal_volume_outside_0_to_1_is_422(self, client, vocal_volume):
        assert save(client, vocal_volume=vocal_volume).status_code == 422

    @pytest.mark.parametrize("vocal_volume", [0, 1])
    def test_the_ends_of_the_vocal_volume_range_are_accepted(self, client, vocal_volume):
        assert save(client, name=f"V{vocal_volume}", vocal_volume=vocal_volume).status_code == 200

    @pytest.mark.parametrize("missing", ["semitones", "vocal_volume"])
    def test_a_missing_setting_is_422(self, client, missing):
        data = {"name": "Mike", "semitones": 0, "vocal_volume": 0.4}
        del data[missing]

        assert client.post("/singer", data=data).status_code == 422

    def test_a_refused_value_joins_nobody(self, client, karaoke):
        save(client, "Mike", semitones=9)

        assert karaoke.singers.settings_for("Mike") == SingerSettings(
            0, karaoke.preferences.get_or_default("vocal_volume")
        )


class TestUpdate:
    def test_the_owner_changes_their_settings_and_keeps_their_token(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike")

        response = save(phone, "Mike", semitones=-2, vocal_volume=0.1)

        body = response.get_json()
        assert response.status_code == 200
        assert (body["name"], body["token"]) == ("Mike", token)
        assert karaoke.singers.settings_for("Mike") == SingerSettings(-2, 0.1)
        karaoke.rename_singer.assert_not_called()

    def test_a_rename_moves_the_songs_through_rename_singer(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike")
        karaoke.queue_manager.enqueue(SONG, "Mike", log_action=False)

        response = save(phone, "Michael")

        body = response.get_json()
        assert (body["name"], body["token"]) == ("Michael", token)
        karaoke.rename_singer.assert_called_once_with("Mike", "Michael")
        assert karaoke.queue_manager.queue[0]["user"] == "Michael"
        assert karaoke.singers.owns("Michael", token)

    def test_renaming_to_a_name_in_use_is_409_and_moves_nothing(self, app, karaoke):
        phone, _, _ = join(app, karaoke, "Mike")
        join(app, karaoke, "Sue")
        karaoke.queue_manager.enqueue(SONG, "Mike", log_action=False)

        response = save(phone, "sue")

        assert response.status_code == 409
        karaoke.rename_singer.assert_not_called()
        assert karaoke.queue_manager.queue[0]["user"] == "Mike"

    def test_a_save_after_the_name_changed_under_the_phone_is_403(self, app, karaoke, monkeypatch):
        """A second save already in flight passed the ownership check before the first renamed."""
        phone, _, token = join(app, karaoke, "Mike")
        karaoke.singers.update("Mike", token, "Michael", SingerSettings(2, 0.7), MagicMock())
        monkeypatch.setattr(karaoke.singers, "owns", lambda name, token: True)

        response = save(phone, "Mike")

        assert response.status_code == 403
        assert response.get_json()["success"] is False


class TestPageState:
    """The `singer` every template gets, from the phone's cookies and the registry."""

    @pytest.fixture
    def page_state(self):
        def read(client):
            return json.loads(client.get("/state").get_data(as_text=True))

        return read

    def test_a_phone_with_no_cookies_has_not_joined(self, app, karaoke, page_state):
        karaoke.preferences.set("vocal_volume", 0.55)

        state = page_state(app.test_client())

        assert state == {
            "joined": False,
            "name": "",
            "semitones": 0,
            "vocal_volume": 0.55,
            "house_vocal_volume": 0.55,
            "transpose_enabled": True,
        }

    def test_a_phone_with_a_good_token_has_joined_with_its_settings(self, app, karaoke, page_state):
        phone, _, _ = join(app, karaoke, "Mike", SingerSettings(-2, 0.1))

        state = page_state(phone)

        assert state["joined"] is True
        assert state["name"] == "Mike"
        assert (state["semitones"], state["vocal_volume"]) == (-2, 0.1)
        assert state["house_vocal_volume"] == karaoke.preferences.get_or_default("vocal_volume")

    def test_a_phone_with_a_stale_token_has_not_joined(self, app, karaoke, page_state):
        join(app, karaoke, "Mike")

        state = page_state(as_phone(app, "Mike", "from-an-earlier-run"))

        assert state["joined"] is False
        assert state["name"] == ""

    def test_a_phone_whose_name_someone_else_took_has_not_joined(self, app, karaoke, page_state):
        join(app, karaoke, "Mike")
        old_phone = as_phone(app, "Mike", "token-of-the-phone-that-lost-the-name")

        assert page_state(old_phone)["joined"] is False

    def test_an_encoded_name_cookie_is_read_back_as_the_name(self, app, karaoke, page_state):
        _, _, token = join(app, karaoke, "Mary Ann")

        state = page_state(as_phone(app, "Mary%20Ann", token))

        assert (state["joined"], state["name"]) == (True, "Mary Ann")

    def test_the_key_control_is_reported_off_when_pitch_shifting_is_missing(
        self, app, karaoke, page_state
    ):
        karaoke.is_transpose_enabled = False

        assert page_state(app.test_client())["transpose_enabled"] is False
