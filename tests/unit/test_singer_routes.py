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
from pikaraoke.lib.singers import KEY_LIMIT, NAME_LIMIT, SingerRegistry, SingerSettings
from pikaraoke.routes.singer import singer_bp

SONG = "/songs/Artist - Song---dQw4w9WgXcQ.mp4"


@pytest.fixture
def karaoke(tmp_path):
    """A Karaoke stand-in with a real registry and queue, so a rename really moves songs."""
    events = EventSystem()
    preferences = PreferenceManager(config_file_path=str(tmp_path / "config.ini"))
    k = MagicMock()
    k.preferences = preferences
    k.singers = SingerRegistry(preferences, k.rename_singer)
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


def save(client, name="Mike", semitones=2, vocal_volume=0.7, sub_mode="karaoke", **extra):
    return client.post(
        "/singer",
        data={
            "name": name,
            "semitones": semitones,
            "vocal_volume": vocal_volume,
            "sub_mode": sub_mode,
            **extra,
        },
    )


def as_phone(app, name, token):
    """A client holding the cookies the page sets after joining."""
    phone = app.test_client()
    phone.set_cookie("user", name)
    phone.set_cookie("singer_token", token)
    return phone


def join(app, karaoke, name="Mike", settings=SingerSettings(2, 0.7, "karaoke")):
    held, token = karaoke.singers.save(None, name, settings)
    return as_phone(app, held, token), held, token


class TestJoin:
    def test_a_new_guest_joins_and_gets_their_name_and_token(self, client, karaoke):
        response = save(client, "Mike", semitones=2, vocal_volume=0.7)

        body = response.get_json()
        assert response.status_code == 200
        assert body["success"] is True
        assert body["name"] == "Mike"
        assert karaoke.singers.lookup(body["token"]) == ("Mike", SingerSettings(2, 0.7, "karaoke"))

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

        assert karaoke.singers.settings_for("Mike") == SingerSettings(2, 0.7, "karaoke")

    def test_a_token_nobody_holds_is_a_join_and_a_held_name_gets_409(self, app, karaoke):
        join(app, karaoke, "Mike")
        impostor = as_phone(app, "Mike", "not-their-token")

        response = save(impostor, "Mike", semitones=-3)

        assert response.status_code == 409
        assert karaoke.singers.settings_for("Mike") == SingerSettings(2, 0.7, "karaoke")


class TestValidation:
    def test_a_name_of_the_limit_is_accepted(self, client):
        name = "x" * NAME_LIMIT

        response = save(client, name)

        assert response.status_code == 200
        assert response.get_json()["name"] == name

    def test_a_name_one_longer_is_422_and_joins_nobody(self, client, karaoke):
        name = "x" * (NAME_LIMIT + 1)

        assert save(client, name).status_code == 422
        assert karaoke.singers.settings_for(name) == karaoke.singers.house_defaults()

    def test_a_long_name_is_refused_on_a_rename_too(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike")

        assert save(phone, "x" * (NAME_LIMIT + 1)).status_code == 422
        assert karaoke.singers.lookup(token) == ("Mike", SingerSettings(2, 0.7, "karaoke"))

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

    @pytest.mark.parametrize("sub_mode", ["karaoke", "srt", "off"])
    def test_each_lyric_style_is_accepted_and_saved(self, client, karaoke, sub_mode):
        body = save(client, sub_mode=sub_mode).get_json()

        assert karaoke.singers.lookup(body["token"])[1].sub_mode == sub_mode

    @pytest.mark.parametrize("sub_mode", ["subtitles", "Karaoke", ""])
    def test_a_lyric_style_that_is_not_one_of_the_three_is_422_and_joins_nobody(
        self, client, karaoke, sub_mode
    ):
        assert save(client, sub_mode=sub_mode).status_code == 422
        assert karaoke.singers.settings_for("Mike") == karaoke.singers.house_defaults()

    @pytest.mark.parametrize("missing", ["semitones", "vocal_volume", "sub_mode"])
    def test_a_missing_setting_is_422(self, client, missing):
        data = {"name": "Mike", "semitones": 0, "vocal_volume": 0.4, "sub_mode": "karaoke"}
        del data[missing]

        assert client.post("/singer", data=data).status_code == 422

    def test_a_refused_value_joins_nobody(self, client, karaoke):
        save(client, "Mike", semitones=9)

        assert karaoke.singers.settings_for("Mike") == karaoke.singers.house_defaults()


class TestUpdate:
    def test_the_owner_changes_their_settings_and_keeps_their_token(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike")

        response = save(phone, "Mike", semitones=-2, vocal_volume=0.1)

        body = response.get_json()
        assert response.status_code == 200
        assert (body["name"], body["token"]) == ("Mike", token)
        assert karaoke.singers.settings_for("Mike") == SingerSettings(-2, 0.1, "karaoke")
        karaoke.rename_singer.assert_not_called()

    def test_a_rename_moves_the_songs_through_rename_singer(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike")
        karaoke.queue_manager.enqueue(SONG, "Mike", log_action=False)

        response = save(phone, "Michael")

        body = response.get_json()
        assert (body["name"], body["token"]) == ("Michael", token)
        karaoke.rename_singer.assert_called_once_with("Mike", "Michael")
        assert karaoke.queue_manager.queue[0]["user"] == "Michael"
        assert karaoke.singers.lookup(token) == ("Michael", SingerSettings(2, 0.7, "karaoke"))

    def test_renaming_to_a_name_in_use_is_409_and_moves_nothing(self, app, karaoke):
        phone, _, _ = join(app, karaoke, "Mike")
        join(app, karaoke, "Sue")
        karaoke.queue_manager.enqueue(SONG, "Mike", log_action=False)

        response = save(phone, "sue")

        assert response.status_code == 409
        karaoke.rename_singer.assert_not_called()
        assert karaoke.queue_manager.queue[0]["user"] == "Mike"

    @pytest.mark.parametrize("stale_cookie", ["Mike", "mike", "Someone Else", ""])
    def test_a_good_token_with_a_stale_name_cookie_still_updates_the_same_guest(
        self, app, karaoke, stale_cookie
    ):
        """A first save renamed the guest but its reply never reached the phone's cookie."""
        _, _, token = join(app, karaoke, "Mike")
        karaoke.singers.save(token, "Michael", SingerSettings(2, 0.7, "karaoke"))
        phone = as_phone(app, stale_cookie, token)

        response = save(phone, "Michael", semitones=-1, vocal_volume=0.2)

        body = response.get_json()
        assert response.status_code == 200
        assert (body["name"], body["token"]) == ("Michael", token)
        assert karaoke.singers.lookup(token) == ("Michael", SingerSettings(-1, 0.2, "karaoke"))

    @pytest.mark.parametrize("stale_cookie", ["Mike", ""])
    def test_a_good_token_with_a_stale_name_cookie_and_a_blank_name_keeps_the_guest(
        self, app, karaoke, stale_cookie
    ):
        _, _, token = join(app, karaoke, "Mike")
        karaoke.singers.save(token, "Michael", SingerSettings(2, 0.7, "karaoke"))
        phone = as_phone(app, stale_cookie, token)

        response = save(phone, "", semitones=1)

        body = response.get_json()
        assert response.status_code == 200
        assert (body["name"], body["token"]) == ("Michael", token)


class TestEditing:
    """The edit form posts `editing`, so a restart while it is open can't make an Anon name."""

    @pytest.mark.parametrize(
        "make_phone",
        [
            lambda app: as_phone(app, "Mike", "from-an-earlier-run"),
            lambda app: app.test_client(),
        ],
        ids=["token from an earlier run", "no cookies"],
    )
    def test_an_edit_from_a_phone_the_app_does_not_know_is_410_and_joins_nobody(
        self, app, make_phone
    ):
        response = save(make_phone(app), "Mike", semitones=-1, editing="true")

        assert response.status_code == 410
        assert response.get_json() == {"success": False}
        # A guest made by the refused save would hold the name `Mike`, and this join would get 409
        assert save(app.test_client(), "Mike").status_code == 200

    def test_an_edit_from_a_known_token_saves(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike")

        response = save(phone, "", semitones=-1, vocal_volume=0.2, editing="true")

        assert response.get_json() == {"success": True, "name": "Mike", "token": token}
        assert karaoke.singers.lookup(token) == ("Mike", SingerSettings(-1, 0.2, "karaoke"))

    @pytest.mark.parametrize("extra", [{}, {"editing": "false"}])
    def test_a_join_from_a_token_nobody_holds_still_joins(self, app, extra):
        phone = as_phone(app, "Mike", "from-an-earlier-run")

        response = save(phone, "", **extra)

        assert response.status_code == 200
        assert response.get_json()["name"].startswith("Anon-")


class TestPageState:
    """The `singer` every template gets, from the phone's cookies and the registry."""

    @pytest.fixture
    def page_state(self):
        def read(client):
            return json.loads(client.get("/state").get_data(as_text=True))

        return read

    def test_a_phone_with_no_cookies_has_not_joined_and_gets_the_house_defaults(
        self, app, karaoke, page_state
    ):
        karaoke.preferences.set("vocal_volume", 0.55)

        state = page_state(app.test_client())

        assert state == {
            "joined": False,
            "name": "",
            "semitones": 0,
            "vocal_volume": 0.55,
            "sub_mode": "karaoke",
            "name_limit": NAME_LIMIT,
            "key_limit": KEY_LIMIT,
            "transpose_enabled": True,
        }

    def test_a_phone_with_a_good_token_has_joined_with_its_settings(self, app, karaoke, page_state):
        phone, _, _ = join(app, karaoke, "Mike", SingerSettings(-2, 0.1, "srt"))

        state = page_state(phone)

        assert state["joined"] is True
        assert state["name"] == "Mike"
        assert (state["semitones"], state["vocal_volume"], state["sub_mode"]) == (-2, 0.1, "srt")
        assert "house_vocal_volume" not in state

    def test_a_phone_with_a_token_nobody_holds_has_not_joined(self, app, karaoke, page_state):
        join(app, karaoke, "Mike")

        state = page_state(as_phone(app, "Mike", "from-an-earlier-run"))

        assert state["joined"] is False
        assert state["name"] == ""

    @pytest.mark.parametrize("cookie", ["Mike", "mike", "Someone Else", "Mary%20Ann", ""])
    def test_the_name_is_the_registrys_whatever_the_name_cookie_says(
        self, app, karaoke, page_state, cookie
    ):
        _, _, token = join(app, karaoke, "Mike")
        karaoke.singers.save(token, "Michael", SingerSettings(2, 0.7, "karaoke"))

        state = page_state(as_phone(app, cookie, token))

        assert (state["joined"], state["name"]) == (True, "Michael")

    def test_the_key_control_is_reported_off_when_pitch_shifting_is_missing(
        self, app, karaoke, page_state
    ):
        karaoke.is_transpose_enabled = False

        assert page_state(app.test_client())["transpose_enabled"] is False


class TestGetSinger:
    """`GET /singer` gives the edit form the same state a page load would, fresh."""

    @pytest.mark.parametrize("phone_kind", ["new", "joined", "token_nobody_holds"])
    def test_it_returns_the_state_the_pages_get(self, app, karaoke, phone_kind):
        phone = {
            "new": lambda: app.test_client(),
            "joined": lambda: join(app, karaoke, "María José", SingerSettings(-2, 0.1, "karaoke"))[
                0
            ],
            "token_nobody_holds": lambda: as_phone(app, "Mike", "from-an-earlier-run"),
        }[phone_kind]()

        response = phone.get("/singer")

        assert response.status_code == 200
        assert response.get_json() == json.loads(phone.get("/state").get_data(as_text=True))

    def test_it_reflects_a_save_made_after_the_page_loaded(self, app, karaoke):
        phone, _, token = join(app, karaoke, "Mike", SingerSettings(2, 0.7, "karaoke"))
        karaoke.singers.save(token, "Michael", SingerSettings(-1, 0.3, "karaoke"))

        state = phone.get("/singer").get_json()

        assert (state["name"], state["semitones"], state["vocal_volume"]) == ("Michael", -1, 0.3)
