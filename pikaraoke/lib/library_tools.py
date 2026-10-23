"""The app service behind the web library tools.

Song Info and the song lists read bundles through :mod:`library_status`;
regenerate and repair queue a job in the processing manager. Song paths here
are the library's own strings (``song_manager.songs``), which is what the
processing queue, the playing check and the database key on.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pikaraoke.lib import lrclib
from pikaraoke.lib.download_manager import DownloadManager
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.genius import (
    GeniusClient,
    GeniusSong,
    GeniusUnavailable,
    read_choice,
    write_choice,
)
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
from pikaraoke.lib.library_links import (
    NOT_PROCESSED,
    classify_url,
    file_status,
    is_video_id,
    library_files,
    read_playlist,
)
from pikaraoke.lib.library_regen import (
    VIDEO_EXTS,
    CaptionCheck,
    Plan,
    RegenError,
    RegenJob,
    SongJob,
    backup_text_folders,
    check_caption,
    default_query,
    find_local_srt,
    gate_on_disk_caption,
    media_duration,
    read_bundle,
    resolve_plan,
    reuse_plan,
)
from pikaraoke.lib.library_status import (
    SONG_LISTS,
    HistoryEntry,
    SongStatus,
    length_gap_s,
    library_statuses,
    overview_counts,
    song_history,
    song_status,
)
from pikaraoke.lib.metadata_parser import extract_youtube_id
from pikaraoke.lib.processing_manager import ProcessingManager
from pikaraoke.lib.song_manager import SongManager

logger = logging.getLogger(__name__)

BUSY_MESSAGE = "This song has a regen waiting or running."

# Fetched Genius songs kept, so a repair's preview, its LRCLIB step and the
# final queue scrape the page once.
GENIUS_CACHE_SIZE = 20

# LRCLIB records the repair page's searches listed (a search lists up to about
# 20), so a repair queues the picked one without asking LRCLIB again.
LRCLIB_CACHE_SIZE = 100


def _remember(cache: dict, key: object, value: object, size: int) -> None:
    """Store ``value`` as the newest entry of ``cache``, dropping the oldest past ``size``."""
    cache.pop(key, None)
    cache[key] = value
    while len(cache) > size:
        del cache[next(iter(cache))]


# The bulk runs (D5), each with the label of the regen rows it queues.
RUN_LABELS = {"stale": "Update", "all": "Reprocess", "reset": "Reset"}

# The group a picked song moves to; the others a song can stand in are ``checking``,
# ``needs_pick``, ``caption`` and ``reuse`` (see :meth:`_Run.undecided_group`).
_PICK_GROUPS = {"genius": "genius", "keep": "genius", "transcribe": "transcribe", "skip": "skip"}

# A typed Genius title or artist is shown back on the pick page; this much is plenty.
_PICK_TEXT_MAX = 200

# A caption check that couldn't run (YouTube refusing, often after many calls in a
# row) is tried once more after this pause.
CAPTION_RETRY_PAUSE_S = 30

# Why a downloaded song waits for the admin to pick its lyrics, and where it came from (D6).
NEEDS_PICK_REASONS = ("no_caption", "sparse_caption")
NEEDS_PICK_SOURCES = ("playlist", "download")

# What the playlist box says of a link it can't use (D13).
PLAYLIST_NOT_A_LINK = "Paste a YouTube playlist link."
PLAYLIST_ONE_VIDEO = "This is a link to one video. Use the search page to add single videos."
PLAYLIST_VIDEO_IN_LIST = (
    "This link opens one video in a playlist. "
    "Paste the playlist page link (youtube.com/playlist?list=…) to add the whole list."
)
PLAYLIST_UNREADABLE = "Couldn't read that playlist."

# Who a playlist's downloads are attributed to on the Processing page.
PLAYLIST_USER = "Playlist"


def _pick_text(value: object) -> str:
    return value.strip()[:_PICK_TEXT_MAX] if isinstance(value, str) else ""


@dataclass
class _NeedsPick:
    """A downloaded song waiting for the admin to pick its lyrics (D6)."""

    song: str  # the path as the library spells it
    reason: str  # one of NEEDS_PICK_REASONS
    source: str  # one of NEEDS_PICK_SOURCES
    added_at: float  # time.time() when it was listed
    # Chosen and queued this session. Not saved: the choice file is lost with the
    # temp folder, so a restart lists the song again.
    picked: bool = False


@dataclass
class _Entry:
    """One song of an open run: what its files said when the run opened, and the admin's say.

    ``check`` is the caption check once measured: ``{found, passed, wpm, failed}``
    (``failed``: it couldn't run; a state file from before has no such key). ``pick`` is
    ``{kind: genius | keep | transcribe | skip, genius_id?, title?, artist?}``.
    """

    status: SongStatus
    reusable: bool  # its bundle holds a lyric source a regen can replay
    check: dict | None = None
    pick: dict | None = None

    @property
    def genius_id(self) -> int | None:
        """The Genius song the bundle records, which a ``keep`` pick would replay."""
        genius_id = (self.status.genius or {}).get("id")
        return genius_id if isinstance(genius_id, int) else None

    @property
    def check_failed(self) -> bool:
        """Its caption check couldn't run and no pick decides it, so it can be checked again."""
        return self.pick is None and bool((self.check or {}).get("failed"))


@dataclass
class _Run:
    """The open bulk run: its mode and its songs in list order, keyed by the library's path."""

    mode: str
    entries: dict[str, _Entry]
    # Set when the run is discarded or queued: a caption check's retry pause ends at once.
    closed: threading.Event = field(default_factory=threading.Event)

    def needs_check(self, entry: _Entry) -> bool:
        """Whether the run measures this song's YouTube caption before choosing its source.

        Exactly the songs that would wait in ``checking`` with no check made, so
        the two rules can't drift apart and leave a song there for good.
        """
        return self.undecided_group(replace(entry, check=None)) == "checking"

    def undecided_group(self, entry: _Entry) -> str:
        """Where the song stands before any pick; ``needs_pick`` is the group a pick decides."""
        if self.mode == "all" and entry.status.category == "no_lyrics":
            return "transcribe"
        if self.mode != "reset" and entry.reusable:
            return "reuse"
        if not entry.status.youtube_id:
            return "needs_pick"
        if entry.check is None:
            return "checking"
        return "caption" if entry.check.get("passed") else "needs_pick"

    def group(self, entry: _Entry) -> str:
        if entry.pick is not None:
            return _PICK_GROUPS[entry.pick["kind"]]
        return self.undecided_group(entry)

    def unchecked(self) -> str | None:
        """The first song still to check, or None."""
        return next(
            (path for path, e in self.entries.items() if e.check is None and self.needs_check(e)),
            None,
        )

    def to_json(self) -> dict:
        songs = {p: {"check": e.check, "pick": e.pick} for p, e in self.entries.items()}
        return {"mode": self.mode, "songs": songs}


class LibraryTools:
    def __init__(
        self,
        processing_manager: ProcessingManager,
        song_manager: SongManager,
        download_path: str,
        genius_client: GeniusClient,
        state_path: Path,
        events: EventSystem,
        download_manager: DownloadManager,
    ) -> None:
        self._processing = processing_manager
        self._song_manager = song_manager
        self._folder = Path(download_path)
        self._genius = genius_client
        self._events = events
        self._download_manager = download_manager
        self._genius_songs: dict[int, GeniusSong] = {}
        self._genius_lock = threading.Lock()
        self._lrclib_records: dict[int, dict] = {}
        self._lrclib_lock = threading.Lock()
        # The open run, the needs-a-pick list and their file, under one lock (D4).
        self._state_path = state_path
        self._state_lock = threading.Lock()
        self._checker: threading.Thread | None = None
        # Video ids queued from a playlist, until their download lands.
        self._playlist_ids: set[str] = set()
        state = self._read_state()
        self._run = self._load_run(state)
        self._needs_pick = self._load_needs_pick(state)
        self._start_checks()  # a run left mid-check picks up where it stopped
        events.on("processing_complete", self._on_processing_complete)
        events.on("processing_error", self._on_processing_error)
        events.on("processing_cancelled", self._unpick)
        events.on("song_deleted", self._forget_needs_pick)

    @staticmethod
    def is_video(song_path: str) -> bool:
        """Lyrics tools work on video songs only (not .mp3 or CDG .zip)."""
        return Path(song_path).suffix.lower() in VIDEO_EXTS

    def status(self, song_path: str) -> SongStatus:
        return song_status(Path(song_path))

    def history(self, song_path: str) -> list[HistoryEntry]:
        return song_history(Path(song_path))

    def overview(self) -> dict[str, int]:
        return overview_counts(library_statuses(self._folder))

    def songs_in_list(self, name: str) -> list[tuple[str, SongStatus]]:
        """The songs of one of :data:`SONG_LISTS`, by display name.

        Each song comes with its path as the library spells it, so a link built
        from it passes the routes' library check. A video on disk the library
        has not picked up yet is left out.
        """
        in_list = SONG_LISTS[name]
        spelling = {Path(path): path for path in self._song_manager.songs}
        rows = [
            (spelling[status.path], status)
            for status in library_statuses(self._folder)
            if in_list(status) and status.path in spelling
        ]
        return sorted(rows, key=lambda row: self._song_manager.filename_from_path(row[0]).lower())

    def is_busy(self, song_path: str) -> bool:
        """Whether a download or a regen of this song is running or waiting."""
        return (
            self._processing.get_active_job() == song_path
            or song_path in self._processing.pending_jobs
        )

    def attention_rows(self, tracked: set[str]) -> list[dict]:
        """Songs that need the admin and have no job row, for the Attention list.

        The database remembers what the tracker (memory only) forgets: a song
        left half-processed by an earlier session, or failed and then dismissed
        from the Jobs list. A song with a tracker row, or one waiting or
        running, is already shown there. Failed songs come first, then the
        unfinished ones (each group by display name), then the songs waiting
        for a lyrics pick, oldest first. A song waiting for a pick is not
        called unfinished: its row says what it waits for.
        """
        with self._state_lock:
            waiting = sorted(self._needs_pick.values(), key=lambda entry: entry.added_at)
        listed = {entry.song for entry in waiting}
        rows = []
        for db_state, state in (("failed", "failed"), ("pending", "unfinished")):
            paths = self._song_manager.get_paths_by_pipeline_state([db_state])
            titled = [
                (self._song_manager.filename_from_path(path), path)
                for path in paths
                if path in self._song_manager.songs
                and path not in tracked
                and path not in listed
                and not self.is_busy(path)
            ]
            rows += [
                {
                    "song_path": path,
                    "title": title,
                    "state": state,
                    "actions": ["retry", "song_info", "delete"],
                }
                for title, path in sorted(titled, key=lambda pair: pair[0].lower())
            ]
        rows += [
            {
                "song_path": entry.song,
                "title": self._song_manager.filename_from_path(entry.song),
                "state": "needs_pick",
                "reason": entry.reason,
                "source": entry.source,
                "actions": ["pick", "song_info", "delete"],
            }
            for entry in waiting
            if entry.song not in tracked and not self.is_busy(entry.song)
        ]
        return rows

    def can_regenerate(self, song_path: str) -> bool:
        """Whether :meth:`regenerate` has lyrics to work from (busy or not)."""
        return self.is_video(song_path) and self._regen_job(song_path) is not None

    def regenerate(self, song_path: str) -> None:
        """Queue a regen that reuses the song's recorded lyric pick.

        The song's files are backed up first. Raises :class:`RegenError`, with
        a message for the admin, when the song can't be queued.
        """
        if not self.is_video(song_path):
            raise RegenError("Lyrics tools work on video songs only.")
        if self.is_busy(song_path):
            raise RegenError(BUSY_MESSAGE)
        job = self._regen_job(song_path)
        if job is None:
            raise RegenError("Pick lyrics with Repair lyrics first.")
        self._queue(job, reset=False, label="Regenerate")

    def genius_song(self, genius_id: int) -> GeniusSong:
        """A Genius song's lyrics and canonical title and artist, from the last few fetched.

        Raises :class:`~pikaraoke.lib.genius.GeniusUnavailable` when Genius
        can't return it.
        """
        with self._genius_lock:
            song = self._genius_songs.get(genius_id)
        if song is not None:
            return song
        song = self._genius.fetch_song(genius_id)
        with self._genius_lock:
            _remember(self._genius_songs, genius_id, song, GENIUS_CACHE_SIZE)
        return song

    def caption_check(self, song_path: str) -> CaptionCheck:
        """Whether the video's YouTube caption could serve as the lyrics.

        One yt-dlp call; nothing in the library is written.
        """
        if not self.is_video(song_path):
            raise RegenError("Lyrics tools work on video songs only.")
        job = self._song_job(song_path)
        self._caption_plan(job)
        return check_caption(job)

    def lrclib_candidates(self, song_path: str, genius_id: int, title: str, artist: str) -> dict:
        """LRCLIB's synced matches for the admin's search terms, scored against a Genius song.

        Each candidate says how many of the Genius lyrics' lines it maps to, how
        far its length is from the video's, whether the selection rule would
        pick it (``best``) and whether it is the match on disk (``current``).
        The listed records are remembered for :meth:`repair`. Raises
        :class:`~pikaraoke.lib.genius.GeniusUnavailable` when the Genius lyrics
        can't be fetched.
        """
        sheet = [item["text"] for item in parse_lyric_lines(self.genius_song(genius_id).text)]
        video_s = media_duration(self._song_job(song_path))
        records = [r for r in lrclib.search(title, artist) if r.get("syncedLyrics")]
        with self._lrclib_lock:
            for record in records:
                # Only an integer id can come back in a repair request.
                if isinstance(record.get("id"), int):
                    _remember(self._lrclib_records, record["id"], record, LRCLIB_CACHE_SIZE)
        best = lrclib.select_candidate(records, sheet, video_s)
        current_id = self._lrc_record_id(Path(song_path))
        candidates = []
        for record in records:
            cue_texts, _ = lrclib.parse_lrc_lines(record["syncedLyrics"])
            candidates.append(
                {
                    **lrclib.record_meta(record),
                    "duration_diff_s": length_gap_s(record.get("duration"), video_s),
                    "mapped": len(lrclib.map_lines_to_cues(sheet, cue_texts)),
                    "sheet_lines": len(sheet),
                    "best": record is best,
                    "current": current_id is not None and record.get("id") == current_id,
                    "syncedLyrics": record["syncedLyrics"],
                }
            )
        return {"video_duration_s": video_s, "candidates": candidates}

    def repair(
        self,
        song_path: str,
        source: str,
        genius_id: int | None = None,
        lrclib_id: int | None = None,
        lrclib_skip: bool = False,
    ) -> None:
        """Queue a regen that replaces the song's lyric pick.

        ``source`` is ``caption`` (the video's YouTube caption), ``genius`` (the
        Genius song ``genius_id``) or ``transcribe``. For Genius the LRCLIB
        match is the record ``lrclib_id``, or none at all with ``lrclib_skip``
        (which wins over an id); with neither, the automatic rule applies. The
        song's files are backed up first, and the run wipes its old outputs.
        Raises :class:`RegenError`, with a message for the admin, when the song
        can't be queued; nothing has changed on disk by then.
        """
        if not self.is_video(song_path):
            raise RegenError("Lyrics tools work on video songs only.")
        if self.is_busy(song_path):
            raise RegenError(BUSY_MESSAGE)
        job = self._song_job(song_path)
        if source == "caption":
            job.plan = self._caption_plan(job)
        elif source == "genius":
            job.plan = self._genius_plan(genius_id, lrclib_id, lrclib_skip)
        elif source == "transcribe":
            job.plan = self._transcribe_plan()
        else:
            raise RegenError("Unknown lyric source.")
        self._queue(job, reset=True, label="Repair")

    def open_run(self, mode: str) -> None:
        """Open a bulk run (``stale``, ``all`` or ``reset``) over the library's video songs.

        A background thread then measures the YouTube caption of each song that
        needs it (:meth:`_check_captions`). Raises :class:`RegenError` when a
        run is already open or the mode has no songs.
        """
        if mode not in RUN_LABELS:
            raise RegenError("Unknown run.")
        with self._state_lock:
            if self._run is not None:
                raise RegenError("A run is already open.")
            rows = self.songs_in_list("behind" if mode == "stale" else "all")
            if not rows:
                raise RegenError("There are no songs for this run.")
            self._run = _Run(mode, {path: self._entry(path, status) for path, status in rows})
            self._save()
            self._start_checks()

    def run_view(self) -> dict | None:
        """The open run for its pages, or None.

        ``songs`` are in list order, each with its ``group``: ``checking``
        (caption not measured yet), ``needs_pick``, ``genius`` (a pick or a
        keep), ``caption``, ``reuse``, ``transcribe`` or ``skip``. A song with
        ``needs_pick`` true is one a pick decides, whether or not it has one
        yet; ``to_pick`` counts those songs and ``picked`` the ones already
        picked. ``failed`` counts the songs with no pick whose caption check
        couldn't run (:meth:`recheck_captions`). ``now`` is the lyric source the
        song has today, in raw parts for the route to put in words.
        """
        with self._state_lock:
            run = self._run
            if run is None:
                return None
            songs = [self._song_view(run, path, e) for path, e in run.entries.items()]
            checkable = [e for e in run.entries.values() if run.needs_check(e)]
            deciding = [e for e in run.entries.values() if run.undecided_group(e) == "needs_pick"]
            return {
                "mode": run.mode,
                "checking": any(s["group"] == "checking" for s in songs),
                "to_check": len(checkable),
                "checked": sum(e.check is not None for e in checkable),
                "to_pick": len(deciding),
                "picked": sum(e.pick is not None for e in deciding),
                "failed": sum(e.check_failed for e in run.entries.values()),
                "queueable": sum(s["group"] != "skip" for s in songs),
                "songs": songs,
            }

    def save_pick(self, song_path: str, pick: dict) -> None:
        """Record the admin's pick for a song that needs one, replacing an earlier pick.

        ``pick`` is ``{"kind": "genius", "genius_id", "title", "artist"}`` (a
        Genius hit), ``{"kind": "keep"}`` (the Genius song the bundle records),
        ``{"kind": "transcribe"}`` or ``{"kind": "skip"}`` (left out of this
        run). Raises :class:`RegenError` for anything else.
        """
        with self._state_lock:
            run = self._open_run()
            entry = run.entries.get(song_path)
            if entry is None:
                raise RegenError("That song isn't in this run.")
            group = run.undecided_group(entry)
            if group == "checking":
                raise RegenError("That song's caption is still being checked.")
            if group != "needs_pick":
                raise RegenError("That song doesn't need a pick.")
            entry.pick = self._valid_pick(entry, pick)
            self._save()

    def keep_all(self) -> int:
        """Keep the recorded Genius song for every song that needs a pick and has none yet.

        Returns how many songs were picked; a song whose bundle records no
        Genius song is left for the admin.
        """
        with self._state_lock:
            run = self._open_run()
            kept = 0
            for entry in run.entries.values():
                if (
                    run.undecided_group(entry) == "needs_pick"
                    and entry.pick is None
                    and entry.genius_id is not None
                ):
                    entry.pick = {"kind": "keep", "genius_id": entry.genius_id}
                    kept += 1
            if kept:
                self._save()
            return kept

    def recheck_captions(self) -> int:
        """Check again every song with no pick whose caption check couldn't run.

        Returns how many songs are checked again. Raises :class:`RegenError`
        while captions are being checked, or when no such song is left.
        """
        with self._state_lock:
            run = self._open_run()
            # A checker still alive is about to end; a second one would check songs twice.
            checker_alive = self._checker is not None and self._checker.is_alive()
            if run.unchecked() is not None or checker_alive:
                raise RegenError("Captions are still being checked.")
            failed = [e for e in run.entries.values() if e.check_failed]
            if not failed:
                raise RegenError("No caption check failed.")
            for entry in failed:
                entry.check = None
            self._save()
            self._start_checks()
            return len(failed)

    def discard_run(self) -> None:
        """Close the open run with its picks (a caption check in flight stops at its next song)."""
        with self._state_lock:
            if self._run is not None:
                self._run.closed.set()
                self._run = None
                self._save()

    def queue_run(self) -> dict:
        """Queue the open run: one backup of the library's lyric folders, then a job per song.

        Skipped songs are dropped and a song already waiting or running is set
        aside. Returns ``{"queued", "busy", "backup"}`` (the backup folder's
        name, None when nothing was copied) and closes the run. Raises
        :class:`RegenError`, with the run left open and nothing changed on
        disk, while captions are still being checked, a song still needs a pick,
        or a song can no longer be queued the way the preview said.
        """
        with self._state_lock:
            run = self._open_run()
            groups = {run.group(entry) for entry in run.entries.values()}
            if "checking" in groups:
                raise RegenError("Captions are still being checked.")
            if "needs_pick" in groups:
                raise RegenError("Pick lyrics for every song first.")
            jobs = [(path, self._run_job(run, path, e)) for path, e in run.entries.items()]
            waiting = [(p, j) for p, j in jobs if j is not None and not self.is_busy(p)]
            busy = sum(job is not None for _path, job in jobs) - len(waiting)
            if not waiting:
                raise RegenError("Nothing to queue: every song is skipped or already waiting.")
            try:
                backup = backup_text_folders(self._folder)
            except OSError as e:
                logger.error("Backup before queueing the run failed: %s", e)
                raise RegenError(f"Could not back up the lyric files: {e}") from e
            queued = 0
            for _path, job in waiting:
                regen = RegenJob(job, reset=run.mode == "reset", label=RUN_LABELS[run.mode])
                if self._processing.enqueue_regen(regen):
                    queued += 1
                else:
                    busy += 1
            run.closed.set()
            self._run = None
            self._save()
        return {"queued": queued, "busy": busy, "backup": backup.name if backup else None}

    def on_song_downloaded(self, song_path: str) -> None:
        """Queue a fresh download for processing, or list it as needing a lyrics pick (D6).

        A song needs no pick when the search page's picker already chose, when
        the caption its download saved passes the length gate, or when its
        title is blocked (the queue skips it). Wired after the pipeline
        tracker, which hears the same event first and gives its row the song path.
        """
        video_id = extract_youtube_id(song_path)
        with self._state_lock:
            from_playlist = video_id in self._playlist_ids
            self._playlist_ids.discard(video_id)
        try:
            reason = self._pick_reason(song_path, video_id)
        except Exception:  # the handler's boundary: a failed check must not lose the queue add
            logger.exception("Lyrics check of %s failed; processing it", Path(song_path).name)
            reason = None
        if reason is None:
            self._processing.enqueue(song_path)
            return
        source = "playlist" if from_playlist else "download"
        with self._state_lock:
            self._needs_pick[song_path] = _NeedsPick(song_path, reason, source, time.time())
            self._save()
        logger.info("%s needs a lyrics pick (%s)", Path(song_path).name, reason)
        self._events.emit("needs_pick", song_path)

    def pick_lyrics(self, song_path: str, pick: object) -> None:
        """Record the admin's lyrics pick for a listed song and queue it.

        ``pick`` is ``{"kind": "genius", "genius_id": id}`` or ``{"kind":
        "transcribe"}``. It is written as the choice file the search page's
        picker writes, so the pipeline's lyrics stage does the rest (LRCLIB
        included). The song stays listed, as picked, until it finishes. Raises
        :class:`RegenError`, with a message for the admin, when nothing was queued.
        """
        choice = self._choice_for(pick)
        with self._state_lock:
            entry = self._needs_pick.get(song_path)
            if entry is None:
                raise RegenError("That song isn't waiting for a pick.")
            if entry.picked:
                raise RegenError("That song already has a pick.")
            entry.picked = True
        try:
            write_choice(extract_youtube_id(song_path), choice)
        except OSError as e:
            self._unpick(song_path)
            logger.error("Could not save the lyrics pick for %s: %s", Path(song_path).name, e)
            raise RegenError("Could not save that pick.") from e
        self._processing.enqueue(song_path)

    def needs_pick_view(self) -> dict:
        """The needs-a-pick list for its page, shaped like :meth:`run_view` for the pick pass.

        Songs are oldest first. ``now`` holds the song's ``source`` and
        ``reason`` in raw parts for the route to put in words; a song already
        picked carries a ``pick``.
        """
        with self._state_lock:
            entries = sorted(self._needs_pick.values(), key=lambda entry: entry.added_at)
            songs = [
                {
                    "song": entry.song,
                    "title": self._song_manager.filename_from_path(entry.song),
                    "needs_pick": True,
                    "now": {"source": entry.source, "reason": entry.reason},
                    "query": default_query(Path(entry.song)),
                    "poor": False,
                    "genius_id": None,  # no current pick to keep
                    "caption": None,
                    "pick": {"kind": "queued"} if entry.picked else None,
                }
                for entry in entries
            ]
            picked = sum(entry.picked for entry in entries)
        return {"to_pick": len(songs), "picked": picked, "songs": songs}

    def check_playlist(self, url: str) -> dict:
        """Read a YouTube playlist and compare it with the library (D13).

        Returns ``{"title", "videos"}``; each video has its ``id``, ``title``
        and ``status``: ``new``, ``not_processed`` (downloaded earlier and never
        processed; it carries its ``song`` path as the library spells it) or
        ``in_library``. Raises :class:`RegenError`, with a message for the
        admin, for a link that isn't a playlist and for one that can't be read.
        """
        url = url.strip() if isinstance(url, str) else ""
        link = classify_url(url)
        if link is None:
            raise RegenError(PLAYLIST_NOT_A_LINK)
        kind, target = link
        if kind == "video":
            in_list = "list" in parse_qs(urlparse(url).query)
            raise RegenError(PLAYLIST_VIDEO_IN_LIST if in_list else PLAYLIST_ONE_VIDEO)
        try:
            playlist = read_playlist(target)
        except (subprocess.SubprocessError, OSError, ValueError) as e:
            logger.warning("Could not read playlist %s: %s", target, e)
            raise RegenError(PLAYLIST_UNREADABLE) from e
        files = library_files(self._folder)
        spelling = {Path(path): path for path in self._song_manager.songs}
        videos = []
        seen = set()
        for video in playlist.videos:
            if video.id in seen:
                continue  # a playlist can hold a video twice
            seen.add(video.id)
            path = files.get(video.id)
            song = spelling.get(path) if path is not None else None
            if path is None:
                status = "new"
            elif song is not None and file_status(path) == NOT_PROCESSED:
                status = "not_processed"
            else:
                status = "in_library"
            videos.append(
                {
                    "id": video.id,
                    "title": video.title,
                    "status": status,
                    "song": song if status == "not_processed" else None,
                }
            )
        return {"title": playlist.title, "videos": videos}

    def add_playlist(self, videos: object, unprocessed: object) -> dict:
        """Download the chosen playlist videos and process the chosen unprocessed songs (D13).

        ``videos`` is a list of ``{"id", "title"}``; ``unprocessed`` is a list of
        library song paths. A video already in the library or already waiting
        to download is left out, and so is a song that is busy, listed for a
        pick, or no longer unprocessed. Returns ``{"downloads", "processing"}``,
        how many of each were taken up. Raises :class:`RegenError` for a
        request that isn't lists.
        """
        if not isinstance(videos, list) or not isinstance(unprocessed, list):
            raise RegenError("Not a playlist selection.")
        in_library = library_files(self._folder)
        waiting = {job["video_url"] for job in list(self._download_manager.pending_downloads)}
        waiting.add(self._download_manager.active_url)
        downloads = 0
        for video in videos:
            video_id = video.get("id") if isinstance(video, dict) else None
            url = f"https://www.youtube.com/watch?v={video_id}"
            if not is_video_id(video_id) or video_id in in_library or url in waiting:
                continue
            waiting.add(url)
            with self._state_lock:
                self._playlist_ids.add(video_id)
            self._download_manager.queue_download(
                url, enqueue=False, user=PLAYLIST_USER, title=_pick_text(video.get("title")) or None
            )
            downloads += 1
        processing = 0
        for song_path in unprocessed:
            if self._is_unprocessed(song_path):
                with self._state_lock:
                    self._playlist_ids.add(extract_youtube_id(song_path))
                self.on_song_downloaded(song_path)
                processing += 1
        return {"downloads": downloads, "processing": processing}

    def _is_unprocessed(self, song_path: object) -> bool:
        """Whether a playlist's song can still be processed: in the library, idle and not done."""
        if not isinstance(song_path, str) or song_path not in self._song_manager.songs:
            return False
        with self._state_lock:
            listed = song_path in self._needs_pick
        return (
            self.is_video(song_path)
            and not listed
            and not self.is_busy(song_path)
            and file_status(Path(song_path)) == NOT_PROCESSED
        )

    @staticmethod
    def _choice_for(pick: object) -> dict:
        """The choice file's content for a pick, as the pipeline's lyrics stage reads it."""
        kind = pick.get("kind") if isinstance(pick, dict) else None
        if kind == "transcribe":
            return {"mode": "raw"}
        if kind == "genius":
            genius_id = pick.get("genius_id")
            if not isinstance(genius_id, int) or isinstance(genius_id, bool):
                raise RegenError("Pick a Genius song first.")
            return {"genius_id": genius_id}
        raise RegenError("Unknown pick.")

    def _pick_reason(self, song_path: str, video_id: str | None) -> str | None:
        """Why this download needs a lyrics pick before processing, or None when it doesn't.

        The gate deletes a caption too sparse to be lyrics. A check that fails
        raises; :meth:`on_song_downloaded` is where that is caught.
        """
        if (
            video_id is None
            or not self.is_video(song_path)
            or self._processing.is_blocked(song_path)
            or read_choice(video_id) is not None
        ):
            return None
        job = SongJob(Path(song_path), bundle=None, stale_reason="downloaded")
        had_caption = find_local_srt(job.song_path) is not None
        if gate_on_disk_caption(job):
            return None
        return "sparse_caption" if had_caption else "no_caption"

    def _forget_needs_pick(self, song_path: str) -> None:
        """Drop a song from the needs-a-pick list: it was deleted or finished processing."""
        with self._state_lock:
            if self._needs_pick.pop(song_path, None) is not None:
                self._save()

    def _unpick(self, song_path: str) -> None:
        """List a song for a pick again: the job queued for its pick ended without finishing."""
        with self._state_lock:
            entry = self._needs_pick.get(song_path)
            if entry is not None:
                entry.picked = False

    def _on_processing_complete(self, data: dict) -> None:
        self._forget_needs_pick(data["song_path"])

    def _on_processing_error(self, data: dict) -> None:
        self._unpick(data.get("song_path", ""))

    @staticmethod
    def _caption_plan(job: SongJob) -> Plan:
        """The plan that fetches the video's caption; only a song with a YouTube ID has one."""
        plan = resolve_plan(job, reset=True)
        if plan.kind != "fetch":
            raise RegenError("This song has no YouTube ID.")
        return plan

    def _genius_plan(self, genius_id: int | None, lrclib_id: int | None, lrclib_skip: bool) -> Plan:
        if genius_id is None:
            raise RegenError("Pick a Genius song first.")
        try:
            self.genius_song(genius_id)
        except GeniusUnavailable as e:
            logger.warning("Genius pick %s refused: %s", genius_id, e)
            raise RegenError("Genius didn't return that song's lyrics. Try again.") from e
        plan = Plan(kind="sidecar", genius_id=genius_id, label="genius pick")
        if lrclib_skip:
            plan.lrclib_skip = True
        elif lrclib_id is not None:
            # The record a search listed; after a restart, LRCLIB's copy.
            with self._lrclib_lock:
                record = self._lrclib_records.get(lrclib_id)
            if record is None:
                record = lrclib.get_record(lrclib_id)
            if record is None:
                raise RegenError("LRCLIB didn't return that match. Try again.")
            if not record.get("syncedLyrics"):
                raise RegenError("That LRCLIB match has no synced lyrics.")
            plan.lrclib_record = record
        return plan

    def _queue(self, job: SongJob, *, reset: bool, label: str) -> None:
        """Back up the song's files, then queue its regen job."""
        song = job.song_path
        try:
            backup_text_folders(song.parent, stems=[song.stem])
        except OSError as e:
            logger.error("Backup before queueing %s failed: %s", song.name, e)
            raise RegenError(f"Could not back up this song's lyric files: {e}") from e
        if not self._processing.enqueue_regen(RegenJob(job, reset=reset, label=label)):
            raise RegenError(BUSY_MESSAGE)

    @staticmethod
    def _song_job(song_path: str) -> SongJob:
        """The song's job with its bundle read and no plan yet."""
        song = Path(song_path)
        return SongJob(
            song_path=song, bundle=read_bundle(song.parent, song.stem), stale_reason="selected"
        )

    @staticmethod
    def _transcribe_plan() -> Plan:
        return Plan(kind="transcribe", label="no lyrics -> transcribe")

    def _regen_job(self, song_path: str) -> SongJob | None:
        """The song's job with the plan a plain regenerate uses, or None without one.

        A song with a recorded pick reuses it; one whose only output is a
        transcription (no bundle, a karaoke file) transcribes again.
        """
        job = self._song_job(song_path)
        if song_status(job.song_path).category == "no_lyrics":
            job.plan = self._transcribe_plan()
        else:
            job.plan = reuse_plan(job)
        return job if job.plan is not None else None

    @staticmethod
    def _lrc_record_id(song: Path) -> int | str | None:
        """The LRCLIB id the song's ``.lrc`` on disk records (a skip marker has none)."""
        try:
            return lrclib.read_lrc(lrclib.lrc_path(song))[1].get("id")
        except (OSError, UnicodeDecodeError):
            return None

    def _open_run(self) -> _Run:
        """The open run, for a caller that holds the state lock."""
        if self._run is None:
            raise RegenError("No run is open.")
        return self._run

    def _entry(self, path: str, status: SongStatus) -> _Entry:
        return _Entry(status, reusable=reuse_plan(self._song_job(path)) is not None)

    def _song_view(self, run: _Run, path: str, entry: _Entry) -> dict:
        status = entry.status
        return {
            "song": path,
            "title": self._song_manager.filename_from_path(path),
            "group": run.group(entry),
            "needs_pick": run.undecided_group(entry) == "needs_pick",
            "now": self._now(status),
            "query": default_query(status.path),
            "poor": status.poor,
            "guessed": status.guessed,
            "line_count": status.line_count,
            "has_youtube_id": status.youtube_id is not None,
            "genius_id": entry.genius_id,
            "caption": entry.check,
            "pick": entry.pick,
        }

    @staticmethod
    def _now(status: SongStatus) -> dict:
        """The lyric source a song has today: ``source``, and for Genius its title and artist."""
        if status.category == "no_lyrics":
            return {"source": "transcribed"}
        if status.category == "not_processed":
            return {"source": "unprocessed"}
        if status.origin == "genius" and status.genius:
            return {
                "source": "genius",
                "title": status.genius.get("title"),
                "artist": status.genius.get("artist"),
            }
        return {"source": "captions" if status.origin == "srt" else "unknown"}

    @staticmethod
    def _valid_pick(entry: _Entry, pick: object) -> dict:
        """``pick`` as the run stores it; the client's text is trimmed and capped."""
        kind = pick.get("kind") if isinstance(pick, dict) else None
        if kind in ("transcribe", "skip"):
            return {"kind": kind}
        if kind == "keep":
            if entry.genius_id is None:
                raise RegenError("This song has no recorded Genius song to keep.")
            return {"kind": "keep", "genius_id": entry.genius_id}
        if kind == "genius":
            genius_id = pick.get("genius_id")
            if not isinstance(genius_id, int) or isinstance(genius_id, bool):
                raise RegenError("Pick a Genius song first.")
            return {
                "kind": "genius",
                "genius_id": genius_id,
                "title": _pick_text(pick.get("title")),
                "artist": _pick_text(pick.get("artist")),
            }
        raise RegenError("Unknown pick.")

    def _run_job(self, run: _Run, path: str, entry: _Entry) -> SongJob | None:
        """The song's job with the plan its group calls for (D5); None for a skipped song.

        The plan comes from the song's files as they are now. Raises
        :class:`RegenError` when a song the preview said could reuse its lyrics
        no longer can.
        """
        group = run.group(entry)
        if group == "skip":
            return None
        job = self._song_job(path)
        if group == "reuse":
            job.plan = reuse_plan(job)
            if job.plan is None:
                title = self._song_manager.filename_from_path(path)
                raise RegenError(
                    f"{title} no longer has lyrics to reuse. Discard the run and open it again."
                )
        elif group == "caption":
            job.plan = self._caption_plan(job)
        elif group == "transcribe":
            job.plan = self._transcribe_plan()
        else:  # genius: a pick or a keep
            job.plan = Plan(kind="sidecar", genius_id=entry.pick["genius_id"], label="genius pick")
        return job

    def _start_checks(self) -> None:
        """Start the open run's caption checks, when it has any left."""
        run = self._run
        if run is not None and run.unchecked() is not None:
            self._checker = threading.Thread(
                target=self._check_captions, args=(run,), name="caption-checks", daemon=True
            )
            self._checker.start()

    def _check_captions(self, run: _Run) -> None:
        """Measure ``run``'s captions one song at a time (a yt-dlp call each), saving after each.

        A check that couldn't run is tried once more after
        :data:`CAPTION_RETRY_PAUSE_S`, and the second answer is stored, whatever
        it is. Ends when none are left, or once ``run`` is no longer the open
        run (it was discarded or queued): the song it was on is the last it
        measures, and a run closed during the pause gets nothing stored.
        """
        while True:
            with self._state_lock:
                path = run.unchecked() if self._run is run else None
            if path is None:
                return
            check = self._measure_caption(path)
            if check["failed"]:
                if run.closed.wait(CAPTION_RETRY_PAUSE_S):
                    return
                check = self._measure_caption(path)
            with self._state_lock:
                run.entries[path].check = check
                self._save()

    def _measure_caption(self, path: str) -> dict:
        """The song's caption check; one that crashes counts as a check that couldn't run."""
        try:
            return asdict(check_caption(self._song_job(path)))
        except Exception:
            logger.exception("Caption check of %s failed", Path(path).name)
            return asdict(CaptionCheck(found=False, wpm=None, passed=False, failed=True))

    def _read_state(self) -> dict:
        """The state file's content; empty when there is none or it can't be read."""
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            logger.warning("Ignoring unreadable library tools state %s: %s", self._state_path, e)
            return {}
        return state if isinstance(state, dict) else {}

    def _in_library_folder(self, song_path: str) -> bool:
        """Whether a saved song path is in this library (the app may start on another one)."""
        folder = os.path.normcase(os.path.abspath(self._folder))
        return os.path.normcase(os.path.abspath(Path(song_path).parent)) == folder

    def _load_run(self, state: dict) -> _Run | None:
        """The run an earlier session left open, over this library's songs still on disk.

        A song of another library (the app started with another download path)
        is dropped: queueing it would back up this library and reset that one.
        """
        saved = state.get("run")
        if (
            not isinstance(saved, dict)
            or saved.get("mode") not in RUN_LABELS
            or not isinstance(saved.get("songs"), dict)
        ):
            return None
        entries = {}
        elsewhere = 0
        for path, kept in saved["songs"].items():
            if not self._in_library_folder(path):
                elsewhere += 1
                continue
            if not isinstance(kept, dict) or not Path(path).is_file():
                continue
            entry = self._entry(path, song_status(Path(path)))
            entry.check = kept["check"] if isinstance(kept.get("check"), dict) else None
            try:
                entry.pick = self._valid_pick(entry, kept.get("pick"))
            except RegenError:  # no pick, or one this song can no longer take
                entry.pick = None
            entries[path] = entry
        if elsewhere:
            logger.warning(
                "Dropped %d song(s) of the saved run that are not in the library %s",
                elsewhere,
                self._folder,
            )
        return _Run(saved["mode"], entries) if entries else None

    def _load_needs_pick(self, state: dict) -> dict[str, _NeedsPick]:
        """The songs an earlier session left waiting for a pick, still in this library on disk."""
        saved = state.get("needs_pick")
        entries = {}
        for item in saved if isinstance(saved, list) else []:
            if not isinstance(item, dict):
                continue
            song, added_at = item.get("song"), item.get("added_at")
            if (
                isinstance(song, str)
                and item.get("reason") in NEEDS_PICK_REASONS
                and item.get("source") in NEEDS_PICK_SOURCES
                and isinstance(added_at, (int, float))
                and extract_youtube_id(song) is not None
                and self._in_library_folder(song)
                and Path(song).is_file()
            ):
                entries[song] = _NeedsPick(song, item["reason"], item["source"], float(added_at))
        return entries

    def _save(self) -> None:
        """Write the open run and the needs-a-pick list to the state file, atomically.

        The caller holds the state lock. A write that fails is logged, and
        the run goes on in memory.
        """
        state = {
            "run": self._run.to_json() if self._run is not None else None,
            "needs_pick": [
                {
                    "song": entry.song,
                    "reason": entry.reason,
                    "source": entry.source,
                    "added_at": entry.added_at,
                }
                for entry in self._needs_pick.values()
            ],
        }
        tmp = self._state_path.with_suffix(".tmp")
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except OSError as e:
            logger.error("Could not save the library tools state to %s: %s", self._state_path, e)
