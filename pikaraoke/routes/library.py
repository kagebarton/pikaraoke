"""Library tools routes: song counts and song lists by condition (admin only)."""

from __future__ import annotations

import flask_babel
from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.library_status import SONG_LISTS, SongStatus

_ = flask_babel.gettext

library_bp = Blueprint("library", __name__)


def _list_title(name: str) -> str:
    return {
        "behind": _("Songs behind the current version"),
        "poor": _("Songs that look poor"),
        "no_lyrics": _("Songs with no lyrics"),
        "all": _("All songs"),
    }[name]


def _subline(name: str, status: SongStatus) -> str:
    if name == "behind":
        return _("Version %(v)d") % {"v": status.schema_version}
    if name == "poor":
        return _("%(guessed)d of %(n)d lines guessed") % {
            "guessed": status.guessed,
            "n": status.line_count,
        }
    if name == "no_lyrics":
        return _("Transcribed")
    if status.category == "behind":
        return _("Behind (v%(v)d)") % {"v": status.schema_version}
    if status.category == "current":
        return _("Up to date")
    if status.category == "no_lyrics":
        return _("No lyrics")
    return _("Not processed")


@library_bp.route("/library/overview")
def overview():
    """Song counts for the library tools: behind, looks poor, no lyrics, all."""
    if not is_admin():
        return jsonify({"success": False, "error": _("Admin only")}), 403
    return jsonify(get_karaoke_instance().library_tools.overview())


@library_bp.route("/library/songs")
def songs():
    """The songs behind one of the overview counts, each linking to its Song Info."""
    if not is_admin():
        flash(_("You don't have permission to view the library tools"), "is-danger")
        return redirect(url_for("files.browse"))
    name = request.args.get("list", "")
    if name not in SONG_LISTS:
        abort(400)
    k = get_karaoke_instance()
    rows = [
        {
            "path": path,
            "name": k.song_manager.filename_from_path(path),
            "subline": _subline(name, status),
        }
        for path, status in k.library_tools.songs_in_list(name)
    ]
    return render_template(
        "library_songs.html",
        site_title=get_site_name(),
        title=_list_title(name),
        rows=rows,
    )
