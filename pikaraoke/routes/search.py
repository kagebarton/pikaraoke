"""YouTube search and download routes."""

from __future__ import annotations

import json
import re

import flask_babel
from flask import current_app, jsonify, render_template, request, url_for
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name
from pikaraoke.lib.genius import write_choice
from pikaraoke.lib.genius_lyrics import clean_genius_query
from pikaraoke.lib.youtube_dl import get_preview_info, get_search_results

_ = flask_babel.gettext

search_bp = Blueprint("search", __name__)

# YouTube ID validation: exactly 11 chars of the allowed character set
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class AutocompleteQuery(Schema):
    q = fields.String(required=True, metadata={"description": "Search query for autocomplete"})


class PreviewQuery(Schema):
    url = fields.String(required=True, metadata={"description": "YouTube video URL to preview"})


class DownloadBody(Schema):
    song_url = fields.String(required=True, metadata={"description": "YouTube URL to download"})
    song_added_by = fields.String(
        required=True, metadata={"description": "Name of the user requesting the download"}
    )
    song_title = fields.String(
        required=True, metadata={"description": "Display title for the song"}
    )
    queue = fields.Boolean(
        load_default=False, metadata={"description": "Whether to queue the song after download"}
    )


@search_bp.route("/search", methods=["GET"])
def search():
    """YouTube search page."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    search_string = request.args.get("search_string")
    if search_string:
        raw_results = get_search_results(search_string)
        search_results = [
            (*r, k.song_manager.songs.find_by_id(k.download_path, r[2])) for r in raw_results
        ]
    else:
        search_string = None
        search_results = None
    return render_template(
        "search.html",
        site_title=site_name,
        title="Search",
        songs=k.song_manager.songs,
        search_results=search_results,
        search_string=search_string,
        genius_client=k.genius_client,
    )


@search_bp.route("/autocomplete")
@search_bp.arguments(AutocompleteQuery, location="query")
def autocomplete(query):
    """Search available songs for autocomplete."""
    k = get_karaoke_instance()
    q = query["q"].lower()
    result = []
    for each in k.song_manager.songs:
        if q in each.lower():
            result.append(
                {
                    "path": each,
                    "fileName": k.song_manager.filename_from_path(each),
                    "type": "autocomplete",
                }
            )
    response = current_app.response_class(response=json.dumps(result), mimetype="application/json")
    return response


@search_bp.route("/preview")
@search_bp.arguments(PreviewQuery, location="query")
def preview(query):
    """Get a direct stream URL and SRT availability for a YouTube video."""
    stream_url, srt_available = get_preview_info(query["url"])
    if stream_url is None:
        return jsonify({"error": "Could not fetch stream URL"}), 500
    return jsonify({"stream_url": stream_url, "srt_available": srt_available})


@search_bp.route("/download", methods=["POST"])
@search_bp.arguments(DownloadBody, location="json")
def download(form):
    """Download a video from YouTube."""
    k = get_karaoke_instance()
    song = form["song_url"]
    user = form["song_added_by"]
    title = form["song_title"]
    queue = form.get("queue", False)

    # Queue the download (processed serially by the download worker)
    k.download_manager.queue_download(song, queue, user, title)

    return jsonify({"status": "ok"})


@search_bp.route("/lyrics_search")
def lyrics_search():
    """GET ``?q=<query>`` → JSON list of ``{id, title, artist}``.

    Returns ``[]`` when Genius is disabled or the search fails.  Always 200
    so the UI can render an empty state without error handling.
    """
    k = get_karaoke_instance()
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    cleaned = clean_genius_query(query)
    if not cleaned:
        return jsonify([])
    hits = k.genius_client.search(cleaned)
    return jsonify([{"id": h.id, "title": h.title, "artist": h.artist} for h in hits])


@search_bp.route("/lyrics_select", methods=["POST"])
def lyrics_select():
    """POST ``{ yt_id, genius_id?, mode?, yt_title? }`` → 204.

    Validates *yt_id* is the 11-char YouTube ID.  One of
    ``{genius_id, mode}`` must be present.  Writes the sidecar; does
    not fetch lyrics yet.

    Replaces the prototype's ``/lyrics_download`` route — the prototype
    fetched and saved lyrics text immediately; we only record the choice.
    """
    data = request.get_json(force=True, silent=True) or {}
    yt_id = str(data.get("yt_id", "")).strip()

    if not _YT_ID_RE.match(yt_id):
        return (
            jsonify(
                {
                    "error": "Invalid yt_id: must be exactly 11 alphanumeric/underscore/dash characters"
                }
            ),
            400,
        )

    genius_id = data.get("genius_id")
    mode = data.get("mode")
    yt_title = str(data.get("yt_title", "")).strip()

    if genius_id is not None:
        try:
            genius_id = int(genius_id)
        except (ValueError, TypeError):
            return jsonify({"error": "genius_id must be an integer"}), 400
        payload = {"yt_id": yt_id, "genius_id": genius_id, "yt_title": yt_title}
    elif mode is not None:
        mode_str = str(mode).strip()
        if mode_str not in ("raw", "srt"):
            return jsonify({"error": "mode must be 'raw' or 'srt'"}), 400
        payload = {"yt_id": yt_id, "mode": mode_str}
    else:
        return jsonify({"error": "One of genius_id or mode is required"}), 400

    write_choice(yt_id, payload)
    return "", 204
