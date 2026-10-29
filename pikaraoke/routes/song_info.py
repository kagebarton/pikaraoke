"""Song Info: a song's lyric picks, alignment and history, plus regenerate and repair (admin only)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import flask_babel
from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.genius import GeniusUnavailable
from pikaraoke.lib.library_regen import (
    CUSTOM_ORIGIN,
    LRC_ORIGIN,
    MOVIE_ORIGIN,
    RegenError,
)
from pikaraoke.lib.library_status import HistoryEntry, SongStatus, length_gap_s
from pikaraoke.lib.library_tools import (
    LRC_MAX_GAP_S,
    REPAIR_SOURCES,
    LrcTimingCheck,
    LrcTimingRefused,
    MovieSliceCheck,
    MovieSliceRefused,
    custom_sheet_lines,
)
from pikaraoke.lib.lrclib import LrclibUnavailable
from pikaraoke.lib.srt_cues import cue_spans_from_srt
from pikaraoke.lib.srt_slice_fit import (
    DISAGREE,
    FITS,
    MAX_CUES,
    MIN_FLAGGED_RUN,
    MIN_UNHEARD_RUN,
    NO_REFERENCE,
    NOT_SRT,
    TOO_LONG,
    SliceFit,
    flagged_runs,
    unheard_runs,
)

logger = logging.getLogger(__name__)

_ = flask_babel.gettext
ngettext = flask_babel.ngettext

song_info_bp = Blueprint("song_info", __name__)

# Segment colours of the Alignment tab's bar (board SongInfoBAlign).
_ALIGNER_COLOR = "#2f7fc1"
_TRANSCRIPTION_COLOR = "#6cb8ec"
_CAPTIONS_COLOR = "#c4e4fa"
_LRCLIB_COLOR = "#1abc9c"
_GUESSED_COLOR = "#f1b70e"

# An LRCLIB match this much longer or shorter than the video is worth naming.
_LENGTH_GAP_NOTED_S = 5


@dataclass(frozen=True)
class Tile:
    label: str
    value: str
    sub: str
    warn: bool = False


@dataclass(frozen=True)
class Segment:
    label: str
    count: int
    percent: float
    color: str


@dataclass(frozen=True)
class Alignment:
    timed: int
    line_count: int
    guessed: int
    segments: list[Segment]
    fit: str | None  # "The match is m:ss; this video is m:ss (N s longer)."
    fit_status: str | None
    fit_warn: bool
    route: str | None


@dataclass(frozen=True)
class Version:
    date: str
    current: bool
    genius: str
    genius_changed: bool
    lrclib: str | None
    lrclib_changed: bool
    timed: str
    schema: str
    folder: str | None


def library_song(k, song: object) -> str | None:
    """``song`` when it is a path in the library, else None: the routes' guard on client input."""
    return song if isinstance(song, str) and song in k.song_manager.songs else None


def posted_song(k) -> str | None:
    """The library song the request's JSON body names as ``song``, else None."""
    body = request.get_json(silent=True)
    return library_song(k, body.get("song") if isinstance(body, dict) else None)


def _error(message: str, status: int):
    return jsonify({"success": False, "error": message}), status


def _int_arg(name: str) -> int | None:
    """The query argument ``name`` as an integer, else None."""
    try:
        return int(request.args[name])
    except (KeyError, ValueError):
        return None


def _typed(body: dict, key: str) -> str:
    """The text a JSON body holds under ``key``, trimmed; anything else counts as empty."""
    value = body.get(key)
    return value.strip() if isinstance(value, str) else ""


def _mmss(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _length_gap_s(status: SongStatus) -> int | None:
    """How many seconds longer the bundle's LRCLIB match is than the video (negative: shorter)."""
    return length_gap_s((status.lrclib or {}).get("duration"), status.media_duration_s)


def _gap_text(gap_s: int) -> str:
    if gap_s >= 0:
        return _("%(n)d s longer") % {"n": gap_s}
    return _("%(n)d s shorter") % {"n": -gap_s}


def _length_line(match_s: float, video_s: float, gap_s: int) -> str:
    """The length comparison, "The match is m:ss; this video is m:ss (N s longer)."; no gap at 0."""
    args = {"match": _mmss(match_s), "video": _mmss(video_s), "gap": _gap_text(gap_s)}
    if gap_s == 0:
        return _("The match is %(match)s; this video is %(video)s.") % args
    return _("The match is %(match)s; this video is %(video)s (%(gap)s).") % args


def _candidate_fit(candidate: dict) -> tuple[str, bool | None]:
    """An LRCLIB candidate's length line on the repair page, and whether it is near the video's.

    Near is None when the gap is unknown.
    """
    parts = []
    if isinstance(candidate.get("duration"), (int, float)):
        parts.append(_mmss(candidate["duration"]))
    gap = candidate["duration_diff_s"]
    near = None if gap is None else abs(gap) < _LENGTH_GAP_NOTED_S
    if near is not None:
        parts.append(_("within a few s") if near else _gap_text(gap))
    return " · ".join(parts), near


def _rejected_texts(reason: str | None) -> tuple[str, str]:
    """(short text for the tile, line for the Alignment tab) for a match the fill didn't use."""
    if reason in ("arm_a_bail", "slope_bail", "slope_dev"):
        return (
            _("lines didn't line up"),
            _(
                "Not used: its line times didn't line up with this video. "
                "Usually a different recording."
            ),
        )
    if reason == "no_mapping":
        return _("lyrics didn't match"), _("Not used: its lines didn't match these lyrics.")
    if reason == "negative_start":
        return _("starts too early"), _("Not used: its timing starts before this video does.")
    return _("not checked"), _("Not checked on the last run.")


def _source_name(status: SongStatus) -> str:
    if status.origin == "genius":
        return _("Genius")
    if status.origin == CUSTOM_ORIGIN:
        return _("Custom lyrics")
    if status.origin == MOVIE_ORIGIN:
        return _("Movie subtitles")
    if status.origin == LRC_ORIGIN:
        return "LRCLIB"
    if status.origin == "srt":
        return _("YouTube captions")
    if status.category == "no_lyrics":
        return _("No lyrics")
    if status.category == "not_processed":
        return _("Not processed")
    return "—"


def _lyrics_tile(status: SongStatus) -> Tile:
    if status.schema_version is None:
        sub = ""
    elif status.category == "behind":
        sub = _("behind (v%(v)d)") % {"v": status.schema_version}
    else:
        sub = _("up to date")
    return Tile(_("Lyrics"), _source_name(status), sub)


def _timed_tile(status: SongStatus) -> Tile:
    if not status.line_count or status.lines_timed is None:
        return Tile(_("Timed"), "—", "")
    percent = round(100 * status.lines_timed / status.line_count)
    return Tile(
        _("Timed"),
        f"{percent}%",
        _("%(n)d guessed") % {"n": status.guessed},
        warn=status.poor,
    )


def _lrclib_tile(status: SongStatus) -> Tile:
    label = "LRCLIB"
    if status.origin == LRC_ORIGIN:
        return Tile(label, _("Timing"), _("times this song"))
    if status.lrclib_state == "n/a":
        return Tile(label, "—", _("Genius or custom lyrics only"))
    state = status.lrclib_state
    if state == "used":
        n = status.lrclib_filled
        return Tile(label, _("Used"), ngettext("fills %(num)d line", "fills %(num)d lines", n))
    if state == "skipped":
        return Tile(label, _("Skipped"), _("skipped by you"))
    if state == "rejected":
        gap = _length_gap_s(status)
        if gap is not None and abs(gap) >= _LENGTH_GAP_NOTED_S:
            sub = _gap_text(gap)
        else:
            sub = _rejected_texts(status.lrclib_reason)[0]
        return Tile(label, _("Not used"), sub, warn=status.poor)
    return Tile(label, _("None"), _("no match found"), warn=status.poor)


def _tiles(status: SongStatus) -> list[Tile]:
    return [_lyrics_tile(status), _timed_tile(status), _lrclib_tile(status)]


def _lrclib_pick(status: SongStatus) -> str:
    if status.lrclib_state == "skipped":
        return _("Skipped")
    match = status.lrclib
    if match is None:
        return _("None")
    parts = [match.get("trackName"), match.get("artistName")]
    text = " · ".join(p for p in parts if p)
    if match.get("duration") is not None:
        text += f" · {_mmss(match['duration'])}"
    return text


def _alignment(status: SongStatus) -> Alignment | None:
    """The Alignment tab: who timed each line, and how the LRCLIB match fared."""
    if not status.line_count or status.lines_timed is None:
        return None
    total = status.line_count

    def segment(label: str, count: int, color: str) -> Segment:
        return Segment(label, count, 100 * count / total, color)

    if status.method == "joint" and status.timed_by:
        by = status.timed_by
        counted = [
            (_("Lyric aligner"), by["aligner"], _ALIGNER_COLOR),
            (_("Transcription"), by["transcription"], _TRANSCRIPTION_COLOR),
            (_("YouTube captions"), by["captions"], _CAPTIONS_COLOR),
            (_("LRCLIB fill"), status.lrclib_filled, _LRCLIB_COLOR),
        ]
    else:
        counted = [(_("Timed"), status.lines_timed, _ALIGNER_COLOR)]
    counted.append((_("Guessed"), status.guessed, _GUESSED_COLOR))
    segments = [segment(*row) for row in counted if row[1] > 0]

    fit = fit_status = None
    fit_warn = False
    if status.lrclib_state != "n/a":
        fit, fit_status, fit_warn = _lrclib_fit(status)

    return Alignment(
        timed=status.lines_timed,
        line_count=total,
        guessed=status.guessed,
        segments=segments,
        fit=fit,
        fit_status=fit_status,
        fit_warn=fit_warn,
        route=_route_text(status),
    )


def _lrclib_fit(status: SongStatus) -> tuple[str | None, str, bool]:
    """(the length comparison, the one status line, whether to flag it)."""
    fit = None
    gap = _length_gap_s(status) if status.lrclib_state in ("used", "rejected") else None
    if gap is not None:
        fit = _length_line(status.lrclib["duration"], status.media_duration_s, gap)

    state = status.lrclib_state
    if state == "used":
        n = status.lrclib_filled
        line = ngettext("Used: it filled %(num)d line.", "Used: it filled %(num)d lines.", n)
        return fit, line, False
    if state == "skipped":
        return fit, _("Skipped: you chose no match."), False
    if state == "rejected":
        return fit, _rejected_texts(status.lrclib_reason)[1], True
    return fit, _("No LRCLIB match was found."), True


def _route_text(status: SongStatus) -> str | None:
    if status.method == "cue_align":
        if status.origin == MOVIE_ORIGIN:
            return _(
                "Lyrics from the movie's subtitles, timed against the subtitles' own line times."
            )
        if status.origin == LRC_ORIGIN:
            return _("Lyrics from an LRCLIB match, timed against its own line times.")
        return _("Lyrics from the YouTube caption, timed against the caption's own line times.")
    if status.method == "joint":
        if status.origin == CUSTOM_ORIGIN:
            if status.ytasr_used:
                return _(
                    "Custom lyrics, timed by combining the lyric aligner, a transcription "
                    "and YouTube's auto-captions."
                )
            return _("Custom lyrics, timed by combining the lyric aligner and a transcription.")
        if status.ytasr_used:
            return _(
                "Genius lyrics, timed by combining the lyric aligner, a transcription "
                "and YouTube's auto-captions."
            )
        return _("Genius lyrics, timed by combining the lyric aligner and a transcription.")
    return None


def _date(captured_at: str) -> str:
    try:
        when = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError:
        return captured_at
    return f"{when.day} {when:%b %Y}"


def _lrclib_label(match: dict | None) -> str:
    if match is None:
        return _("no LRCLIB")
    if match.get("duration") is None:
        return "LRCLIB"
    return _("LRCLIB %(length)s") % {"length": _mmss(match["duration"])}


def _pick(entry: HistoryEntry) -> tuple:
    """What a version's lyric pick is: its source, and the Genius song or the custom words."""
    if entry.origin in (CUSTOM_ORIGIN, MOVIE_ORIGIN, LRC_ORIGIN):
        return (entry.origin, entry.lines)
    return (entry.origin, (entry.genius or {}).get("id"))


def _versions(history: list[HistoryEntry]) -> list[Version]:
    """The History tab's rows; each notes what its picks changed from the next older version."""
    versions = []
    for i, entry in enumerate(history):
        older = history[i + 1] if i + 1 < len(history) else None
        lrclib_id = (entry.lrclib or {}).get("id")
        if entry.genius:
            genius_text = _("Genius · %(artist)s") % {"artist": entry.genius.get("artist", "")}
            lrclib_text = _lrclib_label(entry.lrclib)
        elif entry.origin == CUSTOM_ORIGIN:
            genius_text, lrclib_text = _("Custom lyrics"), _lrclib_label(entry.lrclib)
        elif entry.origin == MOVIE_ORIGIN:
            genius_text, lrclib_text = _("Movie subtitles"), None
        elif entry.origin == LRC_ORIGIN:
            genius_text, lrclib_text = _("LRCLIB timing"), None
        else:
            genius_text, lrclib_text = _("YouTube captions"), None
        older_lrclib = (older.lrclib or {}).get("id") if older else lrclib_id
        lrclib_changed = lrclib_text is not None and lrclib_id != older_lrclib
        if lrclib_changed and lrclib_id is not None:
            lrclib_text += " " + (_("added") if older_lrclib is None else _("changed"))
        versions.append(
            Version(
                date=_date(entry.captured_at),
                current=entry.backup is None,
                genius=genius_text,
                genius_changed=older is not None and _pick(entry) != _pick(older),
                lrclib=lrclib_text,
                lrclib_changed=lrclib_changed,
                timed=(
                    _("%(timed)d of %(n)d lines")
                    % {"timed": entry.lines_timed, "n": entry.line_count}
                    if entry.line_count is not None and entry.lines_timed is not None
                    else "—"
                ),
                schema=f"v{entry.schema_version}" if entry.schema_version is not None else "—",
                folder=entry.backup,
            )
        )
    return versions


@song_info_bp.route("/song_info")
def song_info():
    """Song Info page: the picks, the alignment and the history behind a song's lyrics."""
    k = get_karaoke_instance()
    if not is_admin():
        flash(_("You don't have permission to view song info"), "is-danger")
        return redirect(url_for("files.browse"))
    song = library_song(k, request.args.get("song"))
    if song is None:
        abort(400)

    tools = k.library_tools
    status = tools.status(song)
    video = tools.is_video(song)
    history = _versions(tools.history(song)) if video else []
    return render_template(
        "song_info.html",
        site_title=get_site_name(),
        title=_("Song Info"),
        song=song,
        name=k.song_manager.filename_from_path(song),
        status=status,
        duration=_mmss(status.media_duration_s) if status.media_duration_s else None,
        video=video,
        tiles=_tiles(status),
        source=_("Genius lyrics") if status.origin == "genius" else _source_name(status),
        lrclib_pick=_lrclib_pick(status),
        lrclib_row=status.lrclib_state != "n/a" or status.origin == LRC_ORIGIN,
        alignment=_alignment(status),
        history=history,
        has_backups=any(not v.current for v in history),
        can_regenerate=video and tools.can_regenerate(song),
        busy=video and tools.is_busy(song),
    )


@song_info_bp.route("/song_info/regenerate", methods=["POST"])
def regenerate():
    """Queue a regeneration that reuses the song's recorded lyric pick."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = posted_song(k)
    if song is None:
        return _error(_("Not a song in the library"), 400)
    try:
        k.library_tools.regenerate(song)
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True})


def _current_source(status: SongStatus) -> str | None:
    """Which repair source the song's next regenerate uses, for the page's "current" tag."""
    if status.sheet_kind is not None:
        return status.sheet_kind  # a sheet's kind names its repair source
    if status.origin == "srt":
        return "caption"
    if status.origin == "genius":
        return "genius"
    return "transcribe" if status.category == "no_lyrics" else None


def _lrc_match(meta: dict | None, status: SongStatus) -> dict | None:
    """The song's LRCLIB match on disk as one row of the page's match list, or None."""
    if meta is None:
        return None
    row = {**meta, "duration_diff_s": length_gap_s(meta.get("duration"), status.media_duration_s)}
    row["fit"], row["fit_near"] = _candidate_fit(row)
    return {
        key: row.get(key)
        for key in ("id", "trackName", "artistName", "albumName", "fit", "fit_near")
    }


@song_info_bp.route("/song_info/repair")
def repair_page():
    """Repair lyrics: pick the lyric source (and the LRCLIB match) for a song.

    ``?source=`` opens the page with that source already chosen (the song lists link so).
    """
    k = get_karaoke_instance()
    if not is_admin():
        flash(_("You don't have permission to repair lyrics"), "is-danger")
        return redirect(url_for("files.browse"))
    song = library_song(k, request.args.get("song"))
    if song is None:
        abort(400)
    tools = k.library_tools
    if not tools.is_video(song):
        return redirect(url_for("song_info.song_info", song=song))

    status = tools.status(song)
    start = tools.custom_start(song)
    source = request.args.get("source")
    return render_template(
        "song_repair.html",
        site_title=get_site_name(),
        title=_("Repair lyrics"),
        song=song,
        name=k.song_manager.filename_from_path(song),
        has_youtube_id=status.youtube_id is not None,
        current_source=_current_source(status),
        preselect=source if source in REPAIR_SOURCES else None,
        current_genius_id=(status.genius or {}).get("id"),
        custom_prefill=start["text"],
        custom_query=start["query"],
        movie_prefill=start["movie"],
        lrc_match=_lrc_match(start["lrc"], status),
    )


@song_info_bp.route("/song_info/caption_check")
def caption_check():
    """Whether the video's YouTube caption passes the lyrics check (one yt-dlp call)."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = library_song(k, request.args.get("song"))
    if song is None:
        return _error(_("Not a song in the library"), 400)
    try:
        check = k.library_tools.caption_check(song)
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"found": check.found, "passed": check.passed, "wpm": check.wpm})


@song_info_bp.route("/song_info/genius_lyrics")
def genius_lyrics():
    """A Genius song's lyrics, for the repair page's preview."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    genius_id = _int_arg("id")
    if genius_id is None:
        return _error(_("Not a Genius song"), 400)
    try:
        song = get_karaoke_instance().library_tools.genius_song(genius_id)
    except GeniusUnavailable as e:
        logger.warning("Genius lyrics preview for %s failed: %s", genius_id, e)
        return _error(_("Genius didn't return that song's lyrics. Try again."), 502)
    return jsonify({"title": song.title, "artist": song.artist, "text": song.text})


def _lrclib_results(song: str, sheet: list[str], query: str):
    """LRCLIB's matches for the typed search, scored against ``sheet`` and worded for the page."""
    try:
        found = get_karaoke_instance().library_tools.lrclib_candidates(song, sheet, query)
    except LrclibUnavailable as e:
        logger.warning("LRCLIB search for %s: %s", song, e)
        return _error(_("LRCLIB can't be reached right now. Try again."), 502)
    for candidate in found["candidates"]:
        candidate["fit"], candidate["fit_near"] = _candidate_fit(candidate)
    video_s = found["video_duration_s"]
    found["video_length"] = (
        _("video is %(length)s") % {"length": _mmss(video_s)} if video_s is not None else None
    )
    return jsonify(found)


@song_info_bp.route("/song_info/lrclib_search")
def lrclib_search():
    """LRCLIB matches for the typed search, scored against the Genius pick."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = library_song(k, request.args.get("song"))
    if song is None:
        return _error(_("Not a song in the library"), 400)
    genius_id = _int_arg("genius_id")
    if genius_id is None:
        return _error(_("Not a Genius song"), 400)
    query = request.args.get("q", "").strip()
    try:
        sheet = k.library_tools.genius_sheet_lines(genius_id)
    except GeniusUnavailable as e:
        logger.warning("LRCLIB search for %s: Genius lyrics unavailable: %s", song, e)
        return _error(_("Genius didn't return that song's lyrics. Try again."), 502)
    return _lrclib_results(song, sheet, query)


@song_info_bp.route("/song_info/lrclib_search", methods=["POST"])
def lrclib_search_custom():
    """LRCLIB matches scored against the admin's own lyrics, which are too long for a query string."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = posted_song(k)
    if song is None:
        return _error(_("Not a song in the library"), 400)
    body = request.get_json(silent=True)
    try:
        sheet = custom_sheet_lines(body.get("text"))
    except RegenError as e:
        return _error(str(e), 400)
    return _lrclib_results(song, sheet, _typed(body, "q"))


def _hms(seconds: float) -> str:
    whole = round(abs(seconds))
    return f"{whole // 3600}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def _card(
    fit: SliceFit,
    tone: str,
    head: str,
    lines: Sequence[tuple[str, str | None]] = (),
    tip: str | None = None,
    song_info_link: bool = False,
) -> dict:
    """One Check fit card: the headline (with its tip behind an (i)), then the detail lines.

    ``tone``: ``good`` (fits), ``bad`` (doesn't fit) or ``info`` (can't be checked yet). A
    line is ``(text, tip)``. Read in the order head, lines, tip, it is the sentence the
    Repair refuses with (:func:`_card_text`).
    """
    return {
        "status": fit.status,
        "tone": tone,
        "head": head,
        "tip": tip,
        "lines": [{"text": text, "tip": line_tip} for text, line_tip in lines],
        "song_info_link": song_info_link,
    }


def _timing_changes(fit: SliceFit) -> tuple[bool, bool]:
    """Whether a fit moves the times by a whole second or more, and whether it changes their speed."""
    return round(fit.move_s) != 0, round(abs(fit.speed - 1) * 100, 1) != 0


def _fit_lines(
    fit: SliceFit, earlier: str, later: str, speed_tip: str
) -> list[tuple[str, str | None]]:
    """The lines under a fit's headline: how many matched, how the times move, the speed, the
    lines dropped. ``earlier`` and ``later`` are the move sentence, ``speed_tip`` the speed's note.
    """
    lines = [(_("matches %(n)s of %(m)s lines") % {"n": fit.matched, "m": fit.total}, None)]
    moves, speeds = _timing_changes(fit)
    if moves:
        move = later if fit.move_s > 0 else earlier
        lines.append((move % {"time": _hms(fit.move_s)}, None))
    if speeds:
        speed_change = abs(fit.speed - 1) * 100
        lines.append(
            (_("Speed adjusted by %(pct)s%%.") % {"pct": f"{speed_change:.1f}"}, speed_tip)
        )
    if fit.dropped:
        lines.append(
            (
                ngettext(
                    "%(num)d line falls outside the clip and is dropped.",
                    "%(num)d lines fall outside the clip and are dropped.",
                    fit.dropped,
                ),
                None,
            )
        )
    return lines


def _fit_card(fit: SliceFit) -> dict:
    """The card for subtitles that fit: how many lines matched and what the fit moves."""
    lines = _fit_lines(
        fit,
        earlier=_("Subtitle times move %(time)s earlier."),
        later=_("Subtitle times move %(time)s later."),
        speed_tip=_(
            "The subtitles run at a different speed than the clip. That happens when "
            "they were made for a different frame rate, or when the clip was sped up "
            "or slowed down."
        ),
    )
    head = _("Fits. The timing already matches the clip.")
    if any(_timing_changes(fit)):
        head = _("Fits. These subtitles can time this song.")
    return _card(fit, "good", head, lines)


def _slice_card(check: MovieSliceCheck) -> dict:
    """The Check fit card for how pasted movie subtitles checked, worded for the repair page."""
    fit = check.fit
    if fit.status == FITS:
        return _fit_card(fit)
    if fit.status == NOT_SRT:
        return _card(
            fit,
            "bad",
            _("Not an SRT file."),
            tip=_(
                "SRT subtitles are numbered cues with times, like 00:01:02,500 --> 00:01:05,000."
            ),
        )
    if fit.status == TOO_LONG:
        return _card(
            fit,
            "bad",
            _("These subtitles have more than %(n)s lines.") % {"n": f"{MAX_CUES:,}"},
            tip=_("Paste only the part of the movie with the song."),
        )
    if fit.status == NO_REFERENCE and not check.regenerate_helps:
        return _card(
            fit,
            "info",
            _("Can't check."),
            [
                (
                    _(
                        "This song has no heard words to compare the subtitles with, and a "
                        "song whose lyrics were transcribed doesn't keep them yet."
                    ),
                    None,
                )
            ],
        )
    if fit.status == NO_REFERENCE:
        return _card(
            fit,
            "info",
            _("Can't check yet."),
            [
                (
                    _(
                        "This song has no heard words yet, so there is nothing to compare "
                        "the subtitles with."
                    ),
                    None,
                ),
                (
                    _("Regenerate the song from Song info first, then come back and check."),
                    None,
                ),
            ],
            song_info_link=True,
        )
    head = _("Doesn't fit.")
    if not fit.total:
        return _card(fit, "bad", head, [(_("These subtitles have no lines to check."), None)])
    counts = {"n": fit.matched, "m": fit.total}
    if fit.reason == DISAGREE:
        return _card(
            fit,
            "bad",
            head,
            [(_("Found %(n)d of %(m)d lines, but they don't agree on one timing.") % counts, None)],
            tip=_(
                "The clip may be cut from several scenes, or these subtitles are for a "
                "different release."
            ),
        )
    return _card(
        fit,
        "bad",
        head,
        [(_("Only %(n)d of %(m)d lines were found in the clip.") % counts, None)],
        tip=_("Check that these subtitles are from this movie and cover the part this clip shows."),
    )


def _card_text(card: dict) -> str:
    """A card as one sentence, for the Repair's refusal: head, lines, then the tip."""
    parts = [card["head"], *(line["text"] for line in card["lines"])]
    return " ".join(parts + ([card["tip"]] if card["tip"] else []))


def _line_runs(
    runs: list[tuple[int, int]], texts: list[str], spans: list[tuple[float, float]]
) -> list[dict]:
    """Stretches of a match's lines: a title ("m:ss–m:ss · n lines") and each line with its clip time."""
    return [
        {
            "title": ngettext(
                "%(first)s–%(last)s · %(num)d line",
                "%(first)s–%(last)s · %(num)d lines",
                last - first + 1,
                first=_mmss(spans[first][0]),
                last=_mmss(spans[last][0]),
            ),
            "lines": [
                {"time": _mmss(spans[line][0]), "text": texts[line]}
                for line in range(first, last + 1)
            ],
        }
        for first, last in runs
    ]


def _lrc_fit_card(check: LrcTimingCheck, length: str | None) -> dict:
    """The card for a match whose lines fit: the numbers, then the lines to read before confirming.

    ``runs`` are stretches heard far from where the match puts them, the warning; ``unheard``
    are stretches nothing was heard for, so they could not be checked, a quieter note.
    """
    fit = check.fit
    texts, spans = cue_spans_from_srt(fit.srt)
    runs = _line_runs(flagged_runs(fit.mistimed, fit.unheard, MIN_FLAGGED_RUN), texts, spans)
    unheard = _line_runs(unheard_runs(fit.unheard, MIN_UNHEARD_RUN), texts, spans)
    lines = _fit_lines(
        fit,
        earlier=_("Line times move %(time)s earlier."),
        later=_("Line times move %(time)s later."),
        speed_tip=_(
            "The match runs at a different speed than the clip. That happens when it was "
            "made for a different frame rate, or when the video is sped up or slowed down."
        ),
    )
    too_far = not check.viable  # the lines fit, so only the length can be what rules it out
    tone, head = "good", _("Fits. This match can time this song.")
    if too_far:
        tone = "bad"
        head = _("The lines fit, but the length is too far off.")
        if length is None:
            head = _("The lines fit, but the match has no length to check.")
    elif runs:
        tone, head = "bad", _("Fits, but check these lines first.")
    if length is not None:
        limit = _(
            "A match this much longer or shorter than the video is usually another edit or "
            "another recording, so its line times would drift. The limit is %(n)d s."
        )
        lines.insert(1, (length, limit % {"n": LRC_MAX_GAP_S} if too_far else None))
    if not (runs or unheard or fit.mistimed):
        lines.append((_("No line was heard far from its time."), None))
    card = _card(fit, tone, head, lines)
    if too_far and length is not None:
        card["lines"][1]["warn"] = True
    card.update(runs=runs, unheard=unheard)
    return card


def _lrc_refusal_card(check: LrcTimingCheck, length: str | None) -> dict:
    """The card for a match that can't be checked or whose lines don't fit."""
    fit = check.fit
    if fit.status == NOT_SRT:
        return _card(fit, "bad", _("Doesn't fit."), [(_("This match has no timed lines."), None)])
    if fit.status == TOO_LONG:
        return _card(
            fit, "bad", _("This match has more than %(n)s lines.") % {"n": f"{MAX_CUES:,}"}
        )
    if fit.status == NO_REFERENCE and not check.regenerate_helps:
        return _card(
            fit,
            "info",
            _("Can't check."),
            [
                (
                    _(
                        "This song has no heard words to compare the match with, and a "
                        "song whose lyrics were transcribed doesn't keep them yet."
                    ),
                    None,
                )
            ],
        )
    if fit.status == NO_REFERENCE:
        return _card(
            fit,
            "info",
            _("Can't check yet."),
            [
                (
                    _(
                        "This song has no heard words yet, so there is nothing to compare "
                        "the match with."
                    ),
                    None,
                ),
                (
                    _("Regenerate the song from Song info first, then come back and check."),
                    None,
                ),
            ],
            song_info_link=True,
        )
    counts = {"n": fit.matched, "m": fit.total}
    tip = None
    if not fit.total:
        lines = [(_("This match has no lines to check."), None)]
    elif fit.reason == DISAGREE:
        lines = [
            (_("Found %(n)d of %(m)d lines, but they don't agree on one timing.") % counts, None)
        ]
        tip = _(
            "The video may be a different edit of the song, with a section this match lacks "
            "or repeats."
        )
    else:
        lines = [(_("Only %(n)d of %(m)d lines were found in the clip.") % counts, None)]
        tip = _(
            "Check that this match is the same song as the video. A cover, a live take or "
            "another language won't match the words heard."
        )
    if length is not None:
        lines.append((length, None))
    return _card(fit, "bad", _("Doesn't fit."), lines, tip=tip)


def _lrc_card(check: LrcTimingCheck) -> dict:
    """The Check fit card for how an LRCLIB match's own line times checked against the clip.

    The movie card's shape, plus ``viable`` (whether Regenerate may be offered) and the
    ``runs`` and ``unheard`` stretches of the match's lines.
    """
    fit = check.fit
    length = (
        None
        if check.gap_s is None
        else _length_line(check.record["duration"], check.clip_s, check.gap_s)
    )
    if fit.status == FITS:
        card = _lrc_fit_card(check, length)
    else:
        card = _lrc_refusal_card(check, length)
        card.update(runs=[], unheard=[])
    card["viable"] = check.viable
    return card


@song_info_bp.route("/song_info/subtitle_fit", methods=["POST"])
def subtitle_fit():
    """Check pasted movie subtitles against the clip's heard words; nothing is saved or queued.

    A preview: the Repair fits the subtitles again on the server and saves that, never
    anything this answer says.
    """
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = posted_song(k)
    if song is None:
        return _error(_("Not a song in the library"), 400)
    try:
        check = k.library_tools.check_movie_slice(song, request.get_json(silent=True).get("text"))
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify(_slice_card(check))


def _non_number(body: dict, *keys: str) -> str | None:
    """The first of ``keys`` the body holds as something other than a whole number, else None."""
    for key in keys:
        value = body.get(key)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            return key
    return None


@song_info_bp.route("/song_info/lrc_fit", methods=["POST"])
def lrc_fit():
    """Check an LRCLIB match's own line times against the clip; nothing is saved or queued.

    ``lrclib_id`` names the match, or with none the song's ``.lrc`` on disk. A preview: the
    Repair fits again on the server and saves that, never anything this answer says.
    """
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = posted_song(k)
    if song is None:
        return _error(_("Not a song in the library"), 400)
    body = request.get_json(silent=True)
    if (bad := _non_number(body, "lrclib_id")) is not None:
        return _error(_("%(key)s must be a number") % {"key": bad}, 400)
    try:
        check = k.library_tools.check_lrc_timing(song, body.get("lrclib_id"))
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify(_lrc_card(check))


@song_info_bp.route("/song_info/lrc_search")
def lrc_search():
    """LRCLIB matches for the typed search, scored against the lyrics the song has now."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = library_song(k, request.args.get("song"))
    if song is None:
        return _error(_("Not a song in the library"), 400)
    sheet = k.library_tools.current_lines(song)
    return _lrclib_results(song, sheet, request.args.get("q", "").strip())


@song_info_bp.route("/song_info/repair", methods=["POST"])
def repair():
    """Queue a regeneration with a new lyric source, and for Genius or custom the LRCLIB match."""
    if not is_admin():
        return _error(_("Admin only"), 403)
    k = get_karaoke_instance()
    song = posted_song(k)
    if song is None:
        return _error(_("Not a song in the library"), 400)
    body = request.get_json(silent=True)
    if (bad := _non_number(body, "genius_id", "lrclib_id")) is not None:
        return _error(_("%(key)s must be a number") % {"key": bad}, 400)
    skip = body.get("lrclib_skip", False)
    if not isinstance(skip, bool):
        return _error(_("lrclib_skip must be true or false"), 400)
    try:
        k.library_tools.repair(
            song,
            body.get("source"),
            genius_id=body.get("genius_id"),
            lrclib_id=body.get("lrclib_id"),
            lrclib_skip=skip,
            text=body.get("text"),
        )
    except MovieSliceRefused as e:
        return _error(_card_text(_slice_card(e.check)), 400)
    except LrcTimingRefused as e:
        return _error(_card_text(_lrc_card(e.check)), 400)
    except RegenError as e:
        return _error(str(e), 400)
    return jsonify({"success": True})
