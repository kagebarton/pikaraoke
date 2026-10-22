"""Song Info: what a song's bundle says about its lyrics and timing, and regenerate (admin only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import flask_babel
from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_smorest import Blueprint

from pikaraoke.lib.current_app import get_karaoke_instance, get_site_name, is_admin
from pikaraoke.lib.library_regen import RegenError
from pikaraoke.lib.library_status import HistoryEntry, SongStatus

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


def _library_song(k, song: object) -> bool:
    """Whether ``song`` is a path in the library: the routes' guard on client input."""
    return isinstance(song, str) and song in k.song_manager.songs


def _mmss(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _length_gap_s(status: SongStatus) -> int | None:
    """How many seconds longer the LRCLIB match is than the video (negative: shorter)."""
    match_s = (status.lrclib or {}).get("duration")
    if match_s is None or status.media_duration_s is None:
        return None
    return round(match_s - status.media_duration_s)


def _gap_text(gap_s: int) -> str:
    if gap_s >= 0:
        return _("%(n)d s longer") % {"n": gap_s}
    return _("%(n)d s shorter") % {"n": -gap_s}


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
    if status.origin != "genius":
        return Tile(label, "—", _("Genius songs only"))
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
    if status.origin == "genius":
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
        args = {
            "match": _mmss(status.lrclib["duration"]),
            "video": _mmss(status.media_duration_s),
            "gap": _gap_text(gap),
        }
        if gap == 0:
            fit = _("The match is %(match)s; this video is %(video)s.") % args
        else:
            fit = _("The match is %(match)s; this video is %(video)s (%(gap)s).") % args

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
        return _("Lyrics from the YouTube caption, timed against the caption's own line times.")
    if status.method == "joint":
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


def _versions(history: list[HistoryEntry]) -> list[Version]:
    """The History tab's rows; each notes what its picks changed from the next older version."""
    versions = []
    for i, entry in enumerate(history):
        older = history[i + 1] if i + 1 < len(history) else None
        genius = (entry.genius or {}).get("id")
        lrclib_id = (entry.lrclib or {}).get("id")
        if entry.genius:
            genius_text = _("Genius · %(artist)s") % {"artist": entry.genius.get("artist", "")}
            lrclib_text = _lrclib_label(entry.lrclib)
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
                genius_changed=older is not None and genius != (older.genius or {}).get("id"),
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
    song = request.args.get("song")
    if not _library_song(k, song):
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
        genius_song=status.origin == "genius",
        lrclib_pick=_lrclib_pick(status),
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
        return jsonify({"success": False, "error": _("Admin only")}), 403
    k = get_karaoke_instance()
    body = request.get_json(silent=True)
    song = body.get("song") if isinstance(body, dict) else None
    if not _library_song(k, song):
        return jsonify({"success": False, "error": _("Not a song in the library")}), 400
    try:
        k.library_tools.regenerate(song)
    except RegenError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    return jsonify({"success": True})
