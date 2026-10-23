"""Library tools routes: song counts, song lists by condition, and bulk runs (admin only)."""

from __future__ import annotations

import flask_babel
from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.library_regen import RegenError
from pikaraoke.lib.library_status import SONG_LISTS, SongStatus

_ = flask_babel.gettext
ngettext = flask_babel.ngettext

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


def _error(message: str, status: int):
    return jsonify({"success": False, "error": message}), status


def _to_tools_tab():
    """Where a run page goes when no run is open: the Library tools tab."""
    return redirect(url_for("processing.processing") + "#tools")


def _run_title(mode: str) -> str:
    return {
        "stale": _("Update stale songs"),
        "all": _("Reprocess all songs"),
        "reset": _("Reset all songs"),
    }[mode]


def _run_explanation(mode: str) -> str:
    return {
        "stale": _(
            "Songs on an older version are redone with the lyric picks they already have. "
            "Vocals are reused; only lyrics and timing are redone."
        ),
        "all": _(
            "Every song is redone on the current code, keeping its lyric pick. "
            "Vocals are reused; only lyrics and timing are redone."
        ),
        "reset": _(
            "Every song's lyric source is chosen again from scratch. "
            "Vocals are reused; only lyrics and timing are redone."
        ),
    }[mode]


def _now_text(now: dict) -> str:
    """The lyric source a song has today, in words."""
    if now["source"] == "genius":
        return _("Now: Genius, %(title)s · %(artist)s") % {
            "title": now["title"],
            "artist": now["artist"],
        }
    if now["source"] == "captions":
        return _("Now: YouTube captions")
    if now["source"] == "transcribed":
        return _("Now: transcribed, no lyrics")
    if now["source"] == "unprocessed":
        return _("Not processed yet")
    return _("Now: no recorded lyric source")


def _run_json(view: dict) -> dict:
    """The open run for the pages: each song's ``now`` in words."""
    for song in view["songs"]:
        song["now"] = _now_text(song["now"])
    return {"open": True, **view}


def _run_page(template: str, *, after_checks: bool = False):
    """Render a run page (``template``) for the open run, or send the admin to the tools tab.

    ``after_checks``: while captions are still being checked the page is the preview, which
    shows the progress.
    """
    if not is_admin():
        flash(_("You don't have permission to view the library tools"), "is-danger")
        return redirect(url_for("files.browse"))
    view = get_karaoke_instance().library_tools.run_view()
    if view is None:
        return _to_tools_tab()
    if after_checks and view["checking"]:
        return redirect(url_for("library.run_preview"))
    return render_template(
        template,
        site_title=get_site_name(),
        title=_run_title(view["mode"]),
        mode=view["mode"],
        explanation=_run_explanation(view["mode"]),
        run=_run_json(view),
    )


@library_bp.route("/library/run", methods=["POST"])
def open_run():
    """Open a bulk run: ``{"mode": "stale" | "all" | "reset"}``."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    body = request.get_json(silent=True)
    mode = body.get("mode") if isinstance(body, dict) else None
    if not isinstance(mode, str):
        return _error(_("Not a run"), 400)
    try:
        get_karaoke_instance().library_tools.open_run(mode)
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True})


@library_bp.route("/library/run")
def run_preview():
    """The open run's preview: the songs by what will happen to each."""
    return _run_page("library_run.html")


@library_bp.route("/library/run/picks")
def run_picks():
    """The pick pass: choose lyrics for the songs of the open run that need them."""
    return _run_page("pick_pass.html", after_checks=True)


@library_bp.route("/library/run/status")
def run_status():
    """The open run for the pages to poll (``{"open": false}`` when there is none)."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    view = get_karaoke_instance().library_tools.run_view()
    return jsonify(_run_json(view) if view is not None else {"open": False})


@library_bp.route("/library/run/pick", methods=["POST"])
def run_pick():
    """Save one song's pick: ``{"song", "pick": {"kind": ...}}``; answers with the run."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    body = request.get_json(silent=True)
    song = body.get("song") if isinstance(body, dict) else None
    if not isinstance(song, str):
        return _error(_("Not a song in this run"), 400)
    tools = get_karaoke_instance().library_tools
    try:
        tools.save_pick(song, body.get("pick"))
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True, "run": _run_json(tools.run_view())})


@library_bp.route("/library/run/keep_all", methods=["POST"])
def run_keep_all():
    """Keep the current Genius pick for every song not yet picked that has one."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    tools = get_karaoke_instance().library_tools
    try:
        kept = tools.keep_all()
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True, "kept": kept, "run": _run_json(tools.run_view())})


@library_bp.route("/library/run/recheck", methods=["POST"])
def run_recheck():
    """Check again the captions whose check couldn't run; answers with the run."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    tools = get_karaoke_instance().library_tools
    try:
        tools.recheck_captions()
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True, "run": _run_json(tools.run_view())})


@library_bp.route("/library/run/queue", methods=["POST"])
def run_queue():
    """Queue the open run, and leave a note for the Processing page the admin lands on."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    try:
        result = get_karaoke_instance().library_tools.queue_run()
    except RegenError as e:
        return _error(str(e), 400)
    queued, busy = result["queued"], result["busy"]
    message = ngettext("Queued %(n)d song.", "Queued %(n)d songs.", queued, n=queued)
    if busy:
        message += " " + ngettext(
            "%(n)d song was left out: it is already waiting or running.",
            "%(n)d songs were left out: they are already waiting or running.",
            busy,
            n=busy,
        )
    if result["backup"]:
        message += " " + _("Backup: %(folder)s.", folder=result["backup"])
    flash(message, "is-success")
    return jsonify({"success": True, **result})


@library_bp.route("/library/run/discard", methods=["POST"])
def run_discard():
    """Close the open run and its picks."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    get_karaoke_instance().library_tools.discard_run()
    return jsonify({"success": True})
