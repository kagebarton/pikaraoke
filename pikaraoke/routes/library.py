"""Library tools routes: song counts, song lists by condition, and bulk runs (admin only)."""

from __future__ import annotations

from urllib.parse import quote

import flask_babel
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.library_regen import RegenError
from pikaraoke.lib.library_status import SONG_LISTS, SongStatus

_ = flask_babel.gettext
ngettext = flask_babel.ngettext

library_bp = Blueprint("library", __name__)


def _joint_subline(status: SongStatus) -> str:
    """How a joint-timed song got its timing help: captions and the LRCLIB match, in words."""
    parts = []
    if status.ytasr_used:
        parts.append(_("with captions"))
    state = status.lrclib_state
    if state == "used":
        n = status.lrclib_filled
        parts.append(ngettext("LRCLIB filled %(num)d line", "LRCLIB filled %(num)d lines", n))
    elif state == "rejected":
        parts.append(_("LRCLIB not used"))
    elif state == "skipped":
        parts.append(_("LRCLIB skipped"))
    else:
        parts.append(_("LRC on disk") if status.lrc_on_disk else _("no LRCLIB match"))
    return " · ".join(parts)


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
    if name in ("caption", "movie", "lrc"):
        return _("Cue align")
    if name in ("genius", "custom", "no_timed_source"):
        return _joint_subline(status)
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
    """The songs behind one of the overview counts, each with its Song Info link."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    name = request.args.get("list", "")
    if name not in SONG_LISTS:
        return _error(_("Not a song list"), 400)
    k = get_karaoke_instance()
    info = url_for("song_info.song_info")
    rows = []
    for path, status in k.library_tools.songs_in_list(name):
        # Bytes, so a file name that isn't UTF-8 still makes a link.
        raw = path.encode("utf-8", "surrogateescape")
        rows.append(
            {
                "name": k.song_manager.filename_from_path(path),
                "subline": _subline(name, status),
                "info_url": f"{info}?song={quote(raw)}",
                "repair_url": url_for(
                    "song_info.repair_page", song=raw, source=_repair_source(status)
                ),
            }
        )
    return jsonify({"success": True, "rows": rows})


def _repair_source(status: SongStatus) -> str | None:
    """The Repair source a song's list link opens with, or None for the plain page.

    An LRC on disk can time the song by its own line times (LRCLIB timing); a joint song
    without one can move to the cue route with its video's YouTube caption.
    """
    if status.lrc_on_disk:
        return "lrclib"
    return "caption" if status.method == "joint" else None


def _error(message: str, status: int):
    return jsonify({"success": False, "error": message}), status


def _to_tools_tab():
    """Where a run page goes when no run is open: the Library tools tab."""
    return redirect(url_for("processing.processing") + "#tools")


def _not_admin_page():
    flash(_("You don't have permission to view the library tools"), "is-danger")
    return redirect(url_for("files.browse"))


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
            "Every song's lyric source is chosen again from scratch, except songs with "
            "custom lyrics or movie subtitles, which keep them. "
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
    if now["source"] == "custom":
        return _("Now: custom lyrics")
    if now["source"] == "movie":
        return _("Now: movie subtitles")
    if now["source"] == "lrclib":
        return _("Now: LRCLIB timing")
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
        return _not_admin_page()
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


def needs_pick_subline(source: str, reason: str) -> str:
    """Where a song waiting for a lyrics pick came from and why it waits, in words."""
    sources = {"playlist": _("Playlist"), "download": _("Download")}
    reasons = {"no_caption": _("no caption"), "sparse_caption": _("caption too sparse")}
    return f"{sources[source]} · {reasons[reason]}"


def _needs_pick_json(view: dict) -> dict:
    """The needs-a-pick list for the pick page: each song's source and reason in words."""
    for song in view["songs"]:
        song["now"] = needs_pick_subline(song["now"]["source"], song["now"]["reason"])
    return view


@library_bp.route("/library/picks")
def picks_page():
    """Songs downloaded without a usable caption, to pick lyrics for."""
    if not is_admin():
        return _not_admin_page()
    view = get_karaoke_instance().library_tools.needs_pick_view()
    return render_template(
        "pick_pass.html",
        site_title=get_site_name(),
        title=_("Pick lyrics"),
        list_mode=True,
        run=_needs_pick_json(view),
    )


@library_bp.route("/library/needs_pick/pick", methods=["POST"])
def needs_pick_pick():
    """Pick lyrics for a listed song and queue it: ``{"song", "pick": {"kind": ...}}``."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    body = request.get_json(silent=True)
    song = body.get("song") if isinstance(body, dict) else None
    if not isinstance(song, str):
        return _error(_("Not a song waiting for a pick"), 400)
    tools = get_karaoke_instance().library_tools
    try:
        tools.pick_lyrics(song, body.get("pick"))
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True, "run": _needs_pick_json(tools.needs_pick_view())})


@library_bp.route("/library/playlist")
def playlist_page():
    """The Add playlist page; its script checks the link in the query."""
    if not is_admin():
        return _not_admin_page()
    return render_template(
        "playlist.html",
        site_title=get_site_name(),
        title=_("Add playlist"),
        url=request.args.get("url", "").strip(),
    )


@library_bp.route("/library/playlist/check", methods=["POST"])
def playlist_check():
    """Read a playlist link and say what is new: ``{"url"}``."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    body = request.get_json(silent=True)
    url = body.get("url") if isinstance(body, dict) else None
    try:
        playlist = get_karaoke_instance().library_tools.check_playlist(url)
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True, "playlist": playlist})


@library_bp.route("/library/playlist/add", methods=["POST"])
def playlist_add():
    """Download the chosen videos and process the chosen songs: ``{"videos", "unprocessed"}``."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error(_("Not a playlist selection"), 400)
    try:
        result = get_karaoke_instance().library_tools.add_playlist(
            body.get("videos"), body.get("unprocessed")
        )
    except RegenError as e:
        return _error(str(e), 400)
    downloads, processing, listed = result["downloads"], result["processing"], result["listed"]
    parts = []
    if downloads:
        parts.append(
            ngettext(
                "Added %(n)d video to the download queue.",
                "Added %(n)d videos to the download queue.",
                downloads,
                n=downloads,
            )
        )
    if processing:
        parts.append(
            ngettext(
                "%(n)d song sent to processing.",
                "%(n)d songs sent to processing.",
                processing,
                n=processing,
            )
        )
    if listed:
        parts.append(
            ngettext(
                "%(n)d song needs a lyrics pick.",
                "%(n)d songs need a lyrics pick.",
                listed,
                n=listed,
            )
        )
    if parts:
        flash(" ".join(parts), "is-success")
    else:
        flash(_("Nothing to add: those songs are already in the library or waiting."), "is-warning")
    return jsonify({"success": True, **result})
