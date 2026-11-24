"""File management routes for browsing, editing, and deleting songs."""

from __future__ import annotations

import logging
import os
import string

import flask_babel
from flask import flash, make_response, redirect, render_template, request, url_for
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.metadata_parser import youtube_id_suffix
from pikaraoke.lib.song_list import browse_key, browse_letter
from pikaraoke.lib.song_manager import split_title

_ = flask_babel.gettext


files_bp = Blueprint("files", __name__)


class SongReferrerQuery(Schema):
    song = fields.String(required=True, metadata={"description": "Path to the song file"})
    referrer = fields.String(metadata={"description": "URL to redirect back to"})


class EditFileForm(Schema):
    new_file_name = fields.String(
        required=True, metadata={"description": "New filename (without extension)"}
    )
    old_file_name = fields.String(
        required=True, metadata={"description": "Current full path of the song file"}
    )
    referrer = fields.String(metadata={"description": "URL to redirect back to after editing"})


def song_busy_message(k, song_path: str) -> str | None:
    """Why a song can't be renamed or deleted right now, or None.

    A song being processed, queued for processing, or waiting for a lyrics pick
    has files a running job is about to write; the admin cancels first.
    """
    tools = k.library_tools
    if tools.is_busy(song_path) or tools.is_waiting_for_pick(song_path):
        # MSG: Message shown after trying to rename or delete a song that is still processing.
        return (
            _("Error: Can't change this song while it is processing or waiting for a lyrics pick")
            + ": "
            + song_path
        )
    return None


# The strip's entries in order: "#" takes digits and other scripts (see browse_letter).
BROWSE_LETTERS = ["#", *string.ascii_lowercase]
BROWSE_MODES = ("artist", "song")
BROWSE_COOKIE_AGE = 10 * 365 * 24 * 3600


def _letter_param(letter: str) -> str:
    """A strip entry as it goes in a URL: a bare "#" would start the fragment."""
    return "numeric" if letter == "#" else letter


def _song_states(k) -> dict[str, str]:
    """Browse's state for each library song that isn't ready, by path.

    "processing": a Queue tap holds the song's slot until it is ready. "fix": the queue
    refuses it (failed, or never finished with nothing working on it). Any other song is ready.
    """
    states = {}
    for pipeline_state in ("failed", "pending"):
        for path in k.song_manager.get_paths_by_pipeline_state([pipeline_state]):
            outcome = k.queue_hold.add_outcome(path, pipeline_state)
            states[path] = "fix" if outcome == "refused" else "processing"
    return states


def _browse_rows(k, by: str, admin: bool) -> list[dict]:
    """One row per library song: the chosen field is the top line, the other the bottom.

    A name that can't be split is one line under its first letter in both modes. A guest
    never sees a song that needs a fix.
    """
    states = _song_states(k)
    rows = []
    for path in k.song_manager.songs:
        state = states.get(path, "ready")
        if state == "fix" and not admin:
            continue
        artist, song = split_title(k.song_manager.filename_from_path(path))
        if not artist:
            top, bottom = song, ""
        elif by == "artist":
            top, bottom = artist, song
        else:
            top, bottom = song, artist
        rows.append({"path": path, "top": top, "bottom": bottom, "state": state})
    return rows


def _chosen_letter(filed: set[str]) -> str | None:
    """The strip entry to show: the requested one if it has songs, else the first that does."""
    asked = (request.args.get("letter") or request.cookies.get("browse_letter") or "").lower()
    if asked == "numeric":
        asked = "#"
    if asked in filed:
        return asked
    return next((entry for entry in BROWSE_LETTERS if entry in filed), None)


@files_bp.route("/browse", methods=["GET"])
def browse():
    """Browse the library one letter at a time, by artist or by song.

    The mode and letter come from the URL, else from the cookies this page last set, so a
    phone reopens where it left off. Rows show their state as the page loads.
    """
    k = get_karaoke_instance()
    by = request.args.get("by") or request.cookies.get("browse_by")
    if by not in BROWSE_MODES:
        by = "artist"
    rows = _browse_rows(k, by, is_admin())
    filed = {browse_letter(row["top"]) for row in rows}
    letter = _chosen_letter(filed)
    listed = sorted(
        (row for row in rows if browse_letter(row["top"]) == letter),
        key=lambda row: (browse_key(row["top"]), browse_key(row["bottom"]), row["path"]),
    )
    letter_param = _letter_param(letter) if letter else None
    response = make_response(
        render_template(
            "files.html",
            site_title=get_site_name(),
            # MSG: Title of the files page.
            title=_("Browse"),
            by=by,
            letter=letter,
            letter_param=letter_param,
            strip=[
                {"label": entry.upper(), "param": _letter_param(entry), "has_rows": entry in filed}
                for entry in BROWSE_LETTERS
            ],
            songs=listed,
            current_url=url_for("files.browse", by=by, letter=letter_param),
        )
    )
    response.set_cookie("browse_by", by, max_age=BROWSE_COOKIE_AGE, path="/")
    if letter_param:
        response.set_cookie("browse_letter", letter_param, max_age=BROWSE_COOKIE_AGE, path="/")
    return response


@files_bp.route("/files/delete", methods=["GET"])
@files_bp.arguments(SongReferrerQuery, location="query")
def delete_file(query):
    """Delete a song file."""
    k = get_karaoke_instance()
    song_path = query["song"]
    referrer = query.get("referrer") or url_for("files.browse")
    if not is_admin():
        flash(_("You don't have permission to delete songs"), "is-danger")
        return redirect(referrer)
    if k.queue_manager.is_song_in_queue(song_path):
        flash(
            # MSG: Message shown after trying to delete a song that is in the queue.
            _("Error: Can't delete this song because it is in the current queue")
            + ": "
            + song_path,
            "is-danger",
        )
    elif busy := song_busy_message(k, song_path):
        flash(busy, "is-danger")
    else:
        try:
            k.song_manager.delete(song_path)
        except OSError as e:
            logging.error(f"Error deleting file: {e}")
            # MSG: Message shown when a song could not be deleted. Followed by the path and the reason
            flash(_("Error deleting file: '%s', %s") % (song_path, e), "is-danger")
        else:
            # MSG: Message shown after deleting a song. Followed by the song path
            flash(
                _("Song deleted: %s") % k.song_manager.filename_from_path(song_path),
                "is-warning",
            )
    return redirect(referrer)


@files_bp.route("/files/edit", methods=["GET"])
@files_bp.arguments(SongReferrerQuery, location="query")
def edit_file(query):
    """Show the song rename page."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    song_path = query["song"]
    referrer = query.get("referrer") or url_for("files.browse")
    if not is_admin():
        flash(_("You don't have permission to edit songs"), "is-danger")
        return redirect(referrer)
    if k.queue_manager.is_song_in_queue(song_path):
        # MSG: Message shown after trying to edit a song that is in the queue.
        flash(
            _("Error: Can't edit this song because it is in the current queue: ") + song_path,
            "is-danger",
        )
        return redirect(referrer)
    if busy := song_busy_message(k, song_path):
        flash(busy, "is-danger")
        return redirect(referrer)
    raw_stem = k.song_manager.filename_from_path(song_path, tidy=False)
    return render_template(
        "edit.html",
        site_title=site_name,
        title="Song File Edit",
        song=song_path,
        raw_stem=raw_stem,
        referrer=referrer,
    )


@files_bp.route("/files/edit", methods=["POST"])
@files_bp.arguments(EditFileForm, location="form")
def rename_file(form):
    """Process a song rename."""
    k = get_karaoke_instance()
    referrer = form.get("referrer") or url_for("files.browse")
    new_name = form["new_file_name"]
    old_name = form["old_file_name"]
    if not is_admin():
        flash(_("You don't have permission to edit songs"), "is-danger")
        return redirect(referrer)
    yt_suffix = youtube_id_suffix(old_name)
    new_name_full = new_name + yt_suffix
    if k.queue_manager.is_song_in_queue(old_name):
        # check one more time just in case someone added it during editing
        # MSG: Message shown after trying to edit a song that is in the queue.
        flash(
            _("Error: Can't edit this song because it is in the current queue: ") + old_name,
            "is-danger",
        )
    elif busy := song_busy_message(k, old_name):
        flash(busy, "is-danger")
    else:
        try:
            k.song_manager.rename(old_name, new_name_full)
        except ValueError:
            # MSG: Message shown after trying to rename a song to a blank name.
            flash(_("Error: The new name can't be empty"), "is-danger")
        except FileExistsError:
            flash(
                # MSG: Message shown after trying to rename a file to a name that already exists.
                _("Error renaming file: '%s' to '%s', Filename already exists")
                % (old_name, new_name_full + os.path.splitext(old_name)[1]),
                "is-danger",
            )
        except OSError as e:
            logging.error(f"Error renaming file: {e}")
            flash(
                _("Error renaming file: '%s' to '%s', %s") % (old_name, new_name_full, e),
                "is-danger",
            )
        else:
            flash(
                # MSG: Message shown after renaming a file.
                _("Renamed file: %s to %s") % (old_name, new_name_full),
                "is-warning",
            )
    return redirect(referrer)
