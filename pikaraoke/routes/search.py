"""YouTube search and download routes."""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, replace

import flask_babel
from flask import get_template_attribute, jsonify, render_template, request, url_for
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name
from pikaraoke.lib.genius import HITS_PER_QUERY, GeniusHit, write_choice
from pikaraoke.lib.genius_query import LIBRARY_CALLS, SEARCH_PAGE_CALLS, find_song
from pikaraoke.lib.library_regen import check_video_caption
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.lib.official_rank import (
    Acts,
    OfficialKind,
    official_first,
    read_first_page,
)
from pikaraoke.lib.song_match import SongIndex, similar_songs
from pikaraoke.lib.youtube_dl import SearchResult, get_search_results

_ = flask_babel.gettext

search_bp = Blueprint("search", __name__)

# Library copies noted on a search page, so a long list would bury the results.
MAX_SIMILAR_SONGS = 3

# YouTube results fetched for a search.
PAGE_SIZE = 30

# YouTube ID validation: exactly 11 chars of the allowed character set
_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class SearchMoreQuery(Schema):
    search_string = fields.String(
        required=True, metadata={"description": "The search to fetch the next results of"}
    )


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
    """One result card: the YouTube hit, the library file that already carries its ID, whether
    it is badged as an original act's official upload, and the library songs noted on it."""

    result: SearchResult
    existing_path: str | None
    official: OfficialKind | None
    library_copies: tuple[str, ...] = ()


def _note_library_copies(songs: Iterable[str], rows: list[SearchRow]) -> list[SearchRow]:
    """The rows with each library song that looks like a result under another YouTube ID noted
    on the first row it matches.

    A copy titled like the song matches nearly every upload of it, so noting it on each match
    would repeat one line down the page. A row already in the library is skipped (its own button
    queues it), and so is a song carrying any result's ID.
    """
    library = SongIndex.from_songs(songs)
    result_ids = {row.result.id for row in rows}
    noted: set[str] = set()
    noted_rows = []
    for row in rows:
        copies: tuple[str, ...] = ()
        if not row.existing_path:
            copies = tuple(
                path
                for path in similar_songs(row.result.title, library)
                if path not in noted and extract_youtube_id(path) not in result_ids
            )[: MAX_SIMILAR_SONGS - len(noted)]
            noted.update(copies)
        noted_rows.append(replace(row, library_copies=copies))
    return noted_rows


def _search_rows(
    songs: Iterable[str], results: list[SearchResult], query: str, acts: Acts
) -> list[SearchRow]:
    """Result cards in display order: the songs already in the library, then the official
    uploads, then YouTube's order."""
    # Read from the song list, not find_by_id, which misses "Title [ID].mp4" and subfolders.
    library_ids = {video_id: path for path in songs if (video_id := extract_youtube_id(path))}
    rows = [
        SearchRow(r, library_ids.get(r.id), official)
        for r, official in official_first(results, query, acts)
    ]
    return sorted(rows, key=lambda row: row.existing_path is None)


@search_bp.route("/search", methods=["GET"])
def search():
    """YouTube search page."""
    k = get_karaoke_instance()
    site_name = get_site_name()
    search_string = request.args.get("search_string")
    if search_string:
        results = get_search_results(search_string, PAGE_SIZE)
        acts = read_first_page(results, search_string)
        search_rows = _note_library_copies(
            k.song_manager.songs,
            _search_rows(k.song_manager.songs, results, search_string, acts),
        )
        show_more = len(results) >= PAGE_SIZE
    else:
        search_string = None
        search_rows = None
        show_more = False
    return render_template(
        "search.html",
        site_title=site_name,
        title="Search",
        songs=k.song_manager.songs,
        search_rows=search_rows,
        show_more=show_more,
        search_string=search_string,
        genius_client=k.genius_client,
    )


@search_bp.route("/search/more", methods=["GET"])
@search_bp.arguments(SearchMoreQuery, location="query")
def search_more(query):
    """The next page of result cards, as HTML without the page shell, for Show more.

    One fetch of two pages, with the originals voted over the first as on /search so the lifted
    rows agree; only the second page is returned.
    """
    k = get_karaoke_instance()
    search_string = query["search_string"]
    try:
        results = get_search_results(search_string, 2 * PAGE_SIZE)
    except subprocess.CalledProcessError as e:
        logging.error(f"Could not fetch more results for {search_string!r}: {e}")
        return "", 502
    acts = read_first_page(results[:PAGE_SIZE], search_string)
    rows = _search_rows(k.song_manager.songs, results[PAGE_SIZE:], search_string, acts)
    result_card = get_template_attribute("search_result.html", "result_card")
    return "".join(result_card(row) for row in rows)


@search_bp.route("/caption_check")
def caption_check():
    """GET ``?yt_id=<id>`` -> ``{found, passed, failed, stream_url}``.

    Whether the video's manual English caption is dense enough to be the lyrics, so the
    dialog offers it only when it is. One yt-dlp call, which also returns a link the browser
    can play (``stream_url``, null when there is none); nothing is written. A missing link
    leaves the caption answer as it was.
    """
    yt_id = request.args.get("yt_id", "")
    if not _YT_ID_RE.match(yt_id):
        return jsonify({"error": "Invalid yt_id"}), 400
    check, stream_url = check_video_caption(yt_id)
    return jsonify(
        {
            "found": check.found,
            "passed": check.passed,
            "failed": check.failed,
            "stream_url": stream_url,
        }
    )


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
    ``{hits: [{id, title, artist, year}], preselect: id | null}``.

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
        hits, preselect = found.hits, found.preselect
    else:
        hits = k.genius_client.search(typed_text) if typed_text else []
        preselect = None
    return jsonify({"hits": [_hit_json(h) for h in hits], "preselect": preselect})


@search_bp.route("/lyrics_select", methods=["POST"])
def lyrics_select():
    """POST ``{ yt_id, genius_id?, mode?, yt_title? }`` → 204.

    Validates *yt_id* is the 11-char YouTube ID.  One of
    ``{genius_id, mode}`` must be present, and ``mode`` can only be ``srt``
    (the video's own caption).  Writes the sidecar; does not fetch lyrics yet.

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
        if mode_str != "srt":
            return jsonify({"error": "mode must be 'srt'"}), 400
        payload = {"yt_id": yt_id, "mode": mode_str}
    else:
        return jsonify({"error": "One of genius_id or mode is required"}), 400

    write_choice(yt_id, payload)
    return "", 204
