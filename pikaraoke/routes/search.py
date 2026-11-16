"""YouTube search and download routes."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass

import flask_babel
from flask import (
    current_app,
    get_template_attribute,
    jsonify,
    render_template,
    request,
    url_for,
)
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name
from pikaraoke.lib.genius import HITS_PER_QUERY, GeniusHit, write_choice
from pikaraoke.lib.genius_query import LIBRARY_CALLS, SEARCH_PAGE_CALLS, find_song
from pikaraoke.lib.library_regen import check_video_caption
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.lib.official_rank import OfficialKind, official_first, pick_artist
from pikaraoke.lib.song_match import SongIndex, similar_songs
from pikaraoke.lib.youtube_dl import SearchResult, get_preview_info, get_search_results

_ = flask_babel.gettext

search_bp = Blueprint("search", __name__)

# The search page's one note lists library copies, so a long list would bury the results.
MAX_SIMILAR_SONGS = 3

# YouTube results fetched for a search.
PAGE_SIZE = 30

# YouTube ID validation: exactly 11 chars of the allowed character set
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class AutocompleteQuery(Schema):
    q = fields.String(required=True, metadata={"description": "Search query for autocomplete"})


class SearchMoreQuery(Schema):
    search_string = fields.String(
        required=True, metadata={"description": "The search to fetch the next results of"}
    )


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


@dataclass(frozen=True)
class SearchRow:
    """One result card: the YouTube hit, the library file that already carries its ID, and
    whether it was lifted as the original artist's official upload."""

    result: SearchResult
    existing_path: str | None
    official: OfficialKind | None


def _library_copies(songs: Iterable[str], results: list[SearchResult]) -> list[str]:
    """Library songs that look like a result found under another YouTube ID.

    A song that carries a result's own ID is left out: that row says "Add to
    Queue" itself.
    """
    library = SongIndex.from_songs(songs)
    result_ids = {result.id for result in results}
    copies = dict.fromkeys(
        path
        for result in results
        for path in similar_songs(result.title, library)
        if extract_youtube_id(path) not in result_ids
    )
    return list(copies)[:MAX_SIMILAR_SONGS]


def _search_rows(
    songs: Iterable[str], results: list[SearchResult], query: str, artist: str | None
) -> list[SearchRow]:
    """Result cards in display order: the artist's official uploads first, then YouTube's order."""
    # Read from the song list, not find_by_id, which misses "Title [ID].mp4" and subfolders.
    library_ids = {video_id: path for path in songs if (video_id := extract_youtube_id(path))}
    return [
        SearchRow(r, library_ids.get(r.id), official)
        for r, official in official_first(results, query, artist)
    ]


@search_bp.route("/search", methods=["GET"])
def search():
    """YouTube search page."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    search_string = request.args.get("search_string")
    if search_string:
        results = get_search_results(search_string, PAGE_SIZE)
        artist = pick_artist(results, search_string)
        search_rows = _search_rows(k.song_manager.songs, results, search_string, artist)
        library_copies = _library_copies(k.song_manager.songs, results)
        show_more = len(results) >= PAGE_SIZE
    else:
        search_string = None
        search_rows = None
        library_copies = []
        show_more = False
    return render_template(
        "search.html",
        site_title=site_name,
        title="Search",
        songs=k.song_manager.songs,
        search_rows=search_rows,
        show_more=show_more,
        similar_songs=library_copies,
        search_string=search_string,
        genius_client=k.genius_client,
    )


@search_bp.route("/search/more", methods=["GET"])
@search_bp.arguments(SearchMoreQuery, location="query")
def search_more(query):
    """The next page of result cards, as HTML without the page shell, for Show more.

    One fetch of two pages, with the artist voted over the first as on /search so the lifted
    rows agree; only the second page is returned.
    """
    k = get_karaoke_instance()
    search_string = query["search_string"]
    try:
        results = get_search_results(search_string, 2 * PAGE_SIZE)
    except subprocess.CalledProcessError as e:
        logging.error(f"Could not fetch more results for {search_string!r}: {e}")
        return "", 502
    artist = pick_artist(results[:PAGE_SIZE], search_string)
    rows = _search_rows(k.song_manager.songs, results[PAGE_SIZE:], search_string, artist)
    result_card = get_template_attribute("search_result.html", "result_card")
    return "".join(result_card(row) for row in rows)


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
    """Get a direct stream URL, SRT availability and duration for a YouTube video."""
    stream_url, srt_available, duration = get_preview_info(query["url"])
    if stream_url is None:
        return jsonify({"error": "Could not fetch stream URL"}), 500
    return jsonify({"stream_url": stream_url, "srt_available": srt_available, "duration": duration})


@search_bp.route("/caption_check")
def caption_check():
    """GET ``?yt_id=<id>&duration=<s>`` -> ``{found, passed, failed}``.

    Whether the video's manual English caption is dense enough to be the
    lyrics, so the picker offers "Use YouTube captions" only when it is. One
    yt-dlp call; nothing is written. ``duration`` is the preview's YouTube
    length; without it the caption can't be measured and passes.
    """
    yt_id = request.args.get("yt_id", "")
    if not _YT_ID_RE.match(yt_id):
        return jsonify({"error": "Invalid yt_id"}), 400
    check = check_video_caption(yt_id, request.args.get("duration", type=float))
    return jsonify({"found": check.found, "passed": check.passed, "failed": check.failed})


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


def _hit_json(hit: GeniusHit) -> dict:
    return {"id": hit.id, "title": hit.title, "artist": hit.artist, "year": hit.year}


@search_bp.route("/lyrics_search")
def lyrics_search():
    """GET ``?title=<video title>[&channel=..&typed=..]`` or ``?q=<typed text>`` →
    ``{hits: [{id, title, artist, year}], preselect: id | null, query}``.

    ``title`` finds the song the video is of (``genius_query.find_song``); a ``channel``
    parameter, even an empty one, marks the search page and allows three Genius calls rather
    than two. ``q`` is what someone typed: one call, as typed, in Genius's order, nothing
    preselected. ``title`` wins when both are sent.

    Always 200, with ``hits`` empty when Genius is disabled or finds nothing, so the UI can
    render an empty state without error handling.
    """
    k = get_karaoke_instance()
    title = request.args.get("title", "").strip()
    typed_text = request.args.get("q", "").strip()
    if title:
        found = find_song(
            lambda query: k.genius_client.search(query, limit=HITS_PER_QUERY),
            title,
            channel=request.args.get("channel", ""),
            typed=request.args.get("typed", ""),
            max_calls=SEARCH_PAGE_CALLS if "channel" in request.args else LIBRARY_CALLS,
        )
        hits, preselect, query = found.hits, found.preselect, found.query
    else:
        hits = k.genius_client.search(typed_text) if typed_text else []
        preselect, query = None, typed_text
    return jsonify({"hits": [_hit_json(h) for h in hits], "preselect": preselect, "query": query})


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
