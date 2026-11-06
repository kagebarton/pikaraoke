"""Guest join and settings routes: who the guests are and the key and vocal volume they sing at."""

from __future__ import annotations

from typing import Any

from flask import Response, jsonify, request
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from pikaraoke.lib.current_app import get_karaoke_instance
from pikaraoke.lib.singers import KEY_LIMIT, NAME_LIMIT, NameTaken, SingerSettings

singer_bp = Blueprint("singer", __name__)

TOKEN_COOKIE = "singer_token"


class SingerForm(Schema):
    name = fields.String(
        load_default="",
        validate=validate.Length(max=NAME_LIMIT),
        metadata={"description": "The name to sing under; blank gets an Anon name"},
    )
    semitones = fields.Integer(
        required=True,
        validate=validate.Range(min=-KEY_LIMIT, max=KEY_LIMIT),
        metadata={"description": "Key for the guest's songs, in semitones"},
    )
    vocal_volume = fields.Float(
        required=True,
        validate=validate.Range(min=0, max=1),
        metadata={"description": "Vocal volume for the guest's songs, from 0 to 1"},
    )


@singer_bp.route("/singer", methods=["POST"])
@singer_bp.arguments(SingerForm, location="form")
def save_singer(form: dict[str, Any]) -> Response | tuple[Response, int]:
    """Join as a new guest, or change the name and settings of the guest this phone is.

    The phone is found by its token cookie alone. The route sets no cookies: the page stores
    the returned name and token.
    """
    k = get_karaoke_instance()
    settings = SingerSettings(form["semitones"], form["vocal_volume"])
    try:
        name, token = k.singers.save(request.cookies.get(TOKEN_COOKIE), form["name"], settings)
    except NameTaken as taken:
        return jsonify({"success": False, "error": str(taken)}), 409
    return jsonify({"success": True, "name": name, "token": token})


def singer_state() -> dict[str, Any]:
    """The phone's guest as the form needs it: joined or not, and the values it starts at."""
    k = get_karaoke_instance()
    guest = k.singers.lookup(request.cookies.get(TOKEN_COOKIE))
    name, settings = guest if guest else ("", k.singers.house_defaults())
    return {
        "joined": guest is not None,
        "name": name,
        "semitones": settings.semitones,
        "vocal_volume": settings.vocal_volume,
        "name_limit": NAME_LIMIT,
        "key_limit": KEY_LIMIT,
        "transpose_enabled": k.is_transpose_enabled,
    }


@singer_bp.route("/singer", methods=["GET"])
def get_singer() -> Response:
    """The phone's current guest state, for the edit form.

    A page's copy of it is only as fresh as its last navigation: the guest may have renamed on
    another tab since, or the app may have restarted.
    """
    return jsonify(singer_state())


@singer_bp.app_context_processor
def inject_singer() -> dict[str, dict[str, Any]]:
    """Give every page the phone's guest state, so a page opens the join form when it has none."""
    return {"singer": singer_state()}
