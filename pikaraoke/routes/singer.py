"""Guest join and settings routes: who the guests are and the key and vocal volume they sing at."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote

from flask import jsonify, request
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

from pikaraoke.lib.current_app import get_karaoke_instance
from pikaraoke.lib.singers import KEY_LIMIT, NameTaken, SingerSettings

singer_bp = Blueprint("singer", __name__)

NAME_COOKIE = "user"
TOKEN_COOKIE = "singer_token"


class SingerForm(Schema):
    name = fields.String(
        load_default="",
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


def _cookies() -> tuple[str, str]:
    """The phone's name and token. The page stores the name percent-encoded."""
    return unquote(request.cookies.get(NAME_COOKIE, "")), request.cookies.get(TOKEN_COOKIE, "")


@singer_bp.route("/singer", methods=["POST"])
@singer_bp.arguments(SingerForm, location="form")
def save_singer(form):
    """Join as a new guest, or change the name and settings of the guest this phone is.

    The route sets no cookies: the page stores the returned name and token.
    """
    k = get_karaoke_instance()
    settings = SingerSettings(form["semitones"], form["vocal_volume"])
    name, token = _cookies()
    try:
        if k.singers.owns(name, token):
            name = k.singers.update(name, token, form["name"], settings, k.rename_singer)
        else:
            name, token = k.singers.join(form["name"], settings)
    except NameTaken as taken:
        return jsonify({"success": False, "error": str(taken)}), 409
    except PermissionError:
        # The phone's name changed under it, from a second save that was already in flight
        return jsonify({"success": False, "error": "Not a guest of this session"}), 403
    return jsonify({"success": True, "name": name, "token": token})


@singer_bp.app_context_processor
def inject_singer() -> dict[str, dict[str, Any]]:
    """Give every page the phone's guest state, so a page opens the join form when it has none."""
    k = get_karaoke_instance()
    name, token = _cookies()
    joined = k.singers.owns(name, token)
    house_vocal_volume = k.preferences.get_or_default("vocal_volume")
    settings = k.singers.settings_for(name) if joined else SingerSettings(0, house_vocal_volume)
    return {
        "singer": {
            "joined": joined,
            "name": name if joined else "",
            "semitones": settings.semitones,
            "vocal_volume": settings.vocal_volume,
            "house_vocal_volume": house_vocal_volume,
            "transpose_enabled": k.is_transpose_enabled,
        }
    }
