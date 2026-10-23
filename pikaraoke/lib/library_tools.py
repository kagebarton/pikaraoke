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
import threading
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from pikaraoke.lib import lrclib
from pikaraoke.lib.genius import GeniusClient, GeniusSong, GeniusUnavailable
from pikaraoke.lib.genius_lyrics import parse_lyric_lines
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


def _pick_text(value: object) -> str:
    return value.strip()[:_PICK_TEXT_MAX] if isinstance(value, str) else ""


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
    ) -> None:
        self._processing = processing_manager
        self._song_manager = song_manager
        self._folder = Path(download_path)
        self._genius = genius_client
        self._genius_songs: dict[int, GeniusSong] = {}
        self._genius_lock = threading.Lock()
        self._lrclib_records: dict[int, dict] = {}
        self._lrclib_lock = threading.Lock()
        # The open run and its file, under one lock (D4).
        self._state_path = state_path
        self._state_lock = threading.Lock()
        self._checker: threading.Thread | None = None
        self._run = self._load_run()
        self._start_checks()  # a run left mid-check picks up where it stopped

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
        """Songs the database says never finished processing, for the Attention list.

        The database remembers what the tracker (memory only) forgets: a song
        left half-processed by an earlier session, or failed and then dismissed
        from the Jobs list. A song with a tracker row, or one waiting or
        running, is already shown there. Failed songs come first, each group
        by display name.
        """
        rows = []
        for db_state, state in (("failed", "failed"), ("pending", "unfinished")):
            paths = self._song_manager.get_paths_by_pipeline_state([db_state])
            titled = [
                (self._song_manager.filename_from_path(path), path)
                for path in paths
                if path in self._song_manager.songs
                and path not in tracked
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

    def _load_run(self) -> _Run | None:
        """The run an earlier session left open, over this library's songs still on disk.

        A song of another library (the app started with another download path)
        is dropped: queueing it would back up this library and reset that one.
        """
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            logger.warning("Ignoring unreadable library tools state %s: %s", self._state_path, e)
            return None
        saved = state.get("run") if isinstance(state, dict) else None
        if (
            not isinstance(saved, dict)
            or saved.get("mode") not in RUN_LABELS
            or not isinstance(saved.get("songs"), dict)
        ):
            return None
        folder = os.path.normcase(os.path.abspath(self._folder))
        entries = {}
        elsewhere = 0
        for path, kept in saved["songs"].items():
            if os.path.normcase(os.path.abspath(Path(path).parent)) != folder:
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

    def _save(self) -> None:
        """Write the open run to the state file, atomically; the caller holds the state lock.

        A write that fails is logged, and the run goes on in memory.
        """
        state = {"run": self._run.to_json() if self._run is not None else None}
        tmp = self._state_path.with_suffix(".tmp")
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except OSError as e:
            logger.error("Could not save the library tools state to %s: %s", self._state_path, e)
