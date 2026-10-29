"""Unit tests for pikaraoke/lib/library_tools.py -- song lists, regenerate, repair, bulk runs,
the after-download check and playlists.

The library is a real ``tmp_path`` folder with bundles; the processing manager is
a mock, so a queued job is whatever ``enqueue_regen`` was handed. Genius is a
fake over a dict of songs, and LRCLIB's network calls are patched.
"""

import json
import os
import subprocess
import threading
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import srt

from pikaraoke.lib import lrclib
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.genius import (
    GeniusSong,
    GeniusUnavailable,
    read_choice,
    write_choice,
)
from pikaraoke.lib.library_links import Playlist, PlaylistVideo
from pikaraoke.lib.library_regen import (
    CaptionCheck,
    RegenError,
    RegenJob,
    gate_on_disk_caption,
)
from pikaraoke.lib.library_tools import (
    CUSTOM_SHEET_MAX_CHARS,
    LRC_MAX_GAP_S,
    MOVIE_SUBTITLES_MAX_CHARS,
    PLAYLIST_NOT_A_LINK,
    PLAYLIST_ONE_VIDEO,
    PLAYLIST_UNREADABLE,
    PLAYLIST_VIDEO_IN_LIST,
    RUN_LABELS,
    LibraryTools,
    LrcTimingRefused,
    MovieSliceRefused,
    custom_sheet_lines,
)
from pikaraoke.lib.song_list import SongList
from pikaraoke.lib.song_manager import SongManager
from pikaraoke.lib.srt_slice_fit import (
    DISAGREE,
    FITS,
    NO_REFERENCE,
    NOT_SRT,
    REFUSED,
    TOO_FEW,
    TOO_LONG,
    fit_slice,
)
from tests.unit.movie_slices import (
    CLIP_S,
    MOVIE_OFFSET_S,
    SLICE_LINES,
    asr_json3,
    clip_starts,
    heard_words,
    lrc_slice,
    movie_slice,
    slice_clip_start,
    slice_line,
)

GENIUS = {"id": 7, "title": "Song", "artist": "Artist"}


def make_video(folder: Path, stem: str) -> Path:
    video = folder / f"{stem}.mp4"
    video.write_bytes(b"")
    return video


def make_videos(folder: Path, *stems: str) -> list[Path]:
    return [make_video(folder, stem) for stem in stems]


def write_bundle(folder: Path, stem: str, **fields) -> None:
    bundle = {"schema_version": SCHEMA_VERSION, "captured_at": "2026-10-01T00:00:00Z"}
    bundle.update(fields)
    path = folder / "alignment_debug" / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle), encoding="utf-8")


def genius_bundle(folder: Path, stem: str, **fields) -> None:
    write_bundle(
        folder,
        stem,
        lyrics={"origin": "genius", "genius": GENIUS, "lines": ["one", "two"]},
        output_summary={"line_count": 10, "lines_with_words": 10},
        **fields,
    )


MOVIE_SRT = "1\n00:00:01,000 --> 00:00:03,000\none\n"


def write_sheet(folder: Path, stem: str, text: str = "one\ntwo\n") -> Path:
    sheet = folder / "lyrics" / f"{stem}.custom.txt"
    sheet.parent.mkdir(exist_ok=True)
    sheet.write_text(text, encoding="utf-8")
    return sheet


def write_movie_sheet(folder: Path, stem: str, text: str = MOVIE_SRT) -> Path:
    sheet = folder / "lyrics" / f"{stem}.custom.srt"
    sheet.parent.mkdir(exist_ok=True)
    sheet.write_text(text, encoding="utf-8")
    return sheet


def write_lrc_sheet(folder: Path, stem: str, text: str = MOVIE_SRT) -> Path:
    sheet = folder / "lyrics" / f"{stem}.lrclib.srt"
    sheet.parent.mkdir(exist_ok=True)
    sheet.write_text(text, encoding="utf-8")
    return sheet


def make_tools(folder: Path, songs: list[str], *, active=None, pending=(), genius=None, state=None):
    """A LibraryTools over ``folder`` whose library holds ``songs``, and its processing mock."""
    library = SongList()
    library.update(songs)
    song_manager = MagicMock()
    song_manager.songs = library
    song_manager.filename_from_path = SongManager.filename_from_path
    processing = MagicMock()
    processing.get_active_job.return_value = active
    processing.pending_jobs = list(pending)
    processing.enqueue_regen.return_value = True
    processing.is_blocked.return_value = False
    downloads = MagicMock()
    downloads.pending_downloads = []
    downloads.active_url = None
    state = state or folder / "library_tools_state.json"
    tools = LibraryTools(
        processing,
        song_manager,
        str(folder),
        genius or MagicMock(),
        state,
        EventSystem(),
        downloads,
    )
    return tools, processing


class TestSongsInList:
    def test_each_list_holds_the_songs_that_match_its_rule(self, tmp_path):
        current = make_video(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, current.stem)
        behind = make_video(tmp_path, "B---bbbbbbbbbbb")
        genius_bundle(tmp_path, behind.stem, schema_version=SCHEMA_VERSION - 1)
        poor = make_video(tmp_path, "C---ccccccccccc")
        write_bundle(tmp_path, poor.stem, output_summary={"line_count": 10, "lines_with_words": 5})
        no_lyrics = make_video(tmp_path, "D---ddddddddddd")
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{no_lyrics.stem}.ass").write_text("", encoding="utf-8")
        tools, _ = make_tools(tmp_path, [str(p) for p in (current, behind, poor, no_lyrics)])

        def names(kind):
            return [Path(path).name for path, _status in tools.songs_in_list(kind)]

        assert names("behind") == [behind.name]
        assert names("poor") == [poor.name]
        assert names("no_lyrics") == [no_lyrics.name]
        assert names("genius") == [current.name, behind.name]
        assert len(names("all")) == 4
        assert tools.overview() == {
            "behind": 1,
            "poor": 1,
            "no_lyrics": 1,
            "caption": 0,
            "movie": 0,
            "genius": 2,
            "custom": 0,
            "no_timed_source": 0,
            "all": 4,
        }

    def test_sorted_by_the_name_the_browser_shows(self, tmp_path):
        later = make_video(tmp_path, "Zed - Last---zzzzzzzzzzz")
        earlier = make_video(tmp_path, "abe - First---aaaaaaaaaaa")
        tools, _ = make_tools(tmp_path, [str(later), str(earlier)])

        rows = tools.songs_in_list("all")

        assert [Path(path).name for path, _status in rows] == [earlier.name, later.name]

    def test_the_path_is_the_librarys_own_spelling(self, tmp_path):
        """The library joins its root as given ('d:/songs' + backslash); a link built from
        the plain Path would not be found in it."""
        video = make_video(tmp_path, "A---aaaaaaaaaaa")
        spelled = os.path.join(tmp_path.as_posix(), video.name)
        tools, _ = make_tools(tmp_path, [spelled])

        [(path, status)] = tools.songs_in_list("all")

        assert path == spelled
        assert status.path == video

    def test_a_video_the_library_has_not_picked_up_is_left_out(self, tmp_path):
        known = make_video(tmp_path, "A---aaaaaaaaaaa")
        make_video(tmp_path, "B---bbbbbbbbbbb")
        tools, _ = make_tools(tmp_path, [str(known)])

        assert [Path(p).name for p, _s in tools.songs_in_list("all")] == [known.name]


class TestIsBusy:
    def test_the_running_song_is_busy(self, tmp_path):
        tools, _ = make_tools(tmp_path, [], active="a.mp4")
        assert tools.is_busy("a.mp4")
        assert not tools.is_busy("b.mp4")

    def test_a_waiting_song_is_busy(self, tmp_path):
        tools, _ = make_tools(tmp_path, [], pending=["a.mp4"])
        assert tools.is_busy("a.mp4")
        assert not tools.is_busy("b.mp4")


class TestAttentionRows:
    @staticmethod
    def tools_with_states(tmp_path, states, songs=None, **kwargs):
        """A LibraryTools whose database lists ``states`` (path -> pipeline_state)."""
        library = songs if songs is not None else list(states)
        tools, _ = make_tools(tmp_path, library, **kwargs)
        tools._song_manager.get_paths_by_pipeline_state.side_effect = lambda wanted: [
            path for path, state in states.items() if state in wanted
        ]
        return tools

    def test_lists_failed_and_unfinished_songs_with_what_the_admin_can_do(self, tmp_path):
        tools = self.tools_with_states(
            tmp_path,
            {
                "/songs/Zed---zzzzzzzzzzz.mp4": "pending",
                "/songs/Abe---aaaaaaaaaaa.mp4": "pending",
                "/songs/Mid---mmmmmmmmmmm.mp4": "failed",
                "/songs/Fine---fffffffffff.mp4": "ready",
            },
        )

        rows = tools.attention_rows(set())

        assert [(r["title"], r["state"]) for r in rows] == [
            ("Mid", "failed"),
            ("Abe", "unfinished"),
            ("Zed", "unfinished"),
        ]
        assert rows[0]["song_path"] == "/songs/Mid---mmmmmmmmmmm.mp4"
        assert rows[0]["actions"] == ["retry", "song_info", "delete"]

    def test_a_song_with_a_tracker_row_is_left_out(self, tmp_path):
        tools = self.tools_with_states(
            tmp_path,
            {"/songs/A---aaaaaaaaaaa.mp4": "failed", "/songs/B---bbbbbbbbbbb.mp4": "failed"},
        )

        rows = tools.attention_rows({"/songs/A---aaaaaaaaaaa.mp4"})

        assert [r["song_path"] for r in rows] == ["/songs/B---bbbbbbbbbbb.mp4"]

    def test_a_song_waiting_or_running_is_left_out(self, tmp_path):
        tools = self.tools_with_states(
            tmp_path,
            {"/songs/A---aaaaaaaaaaa.mp4": "pending", "/songs/B---bbbbbbbbbbb.mp4": "pending"},
            active="/songs/A---aaaaaaaaaaa.mp4",
            pending=["/songs/B---bbbbbbbbbbb.mp4"],
        )

        assert tools.attention_rows(set()) == []

    def test_a_database_row_for_a_song_not_in_the_library_is_left_out(self, tmp_path):
        tools = self.tools_with_states(
            tmp_path,
            {"/songs/Gone---ggggggggggg.mp4": "failed", "/songs/Here---hhhhhhhhhhh.mp4": "failed"},
            songs=["/songs/Here---hhhhhhhhhhh.mp4"],
        )

        rows = tools.attention_rows(set())

        assert [r["title"] for r in rows] == ["Here"]


class TestRegenerate:
    def test_queues_one_job_that_reuses_the_recorded_pick(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)])

        tools.regenerate(str(video))

        processing.enqueue_regen.assert_called_once()
        regen = processing.enqueue_regen.call_args.args[0]
        assert isinstance(regen, RegenJob)
        assert regen.label == "Regenerate"
        assert regen.reset is False
        assert regen.song.song_path == video
        assert regen.song.plan.kind == "seed"
        assert regen.song.plan.seed["genius"] == GENIUS

    def test_backs_up_only_that_song(self, tmp_path):
        mine, other = make_videos(tmp_path, "A---aaaaaaaaaaa", "B---bbbbbbbbbbb")
        genius_bundle(tmp_path, mine.stem)
        genius_bundle(tmp_path, other.stem)
        tools, _ = make_tools(tmp_path, [str(mine), str(other)])

        tools.regenerate(str(mine))

        [backup] = tmp_path.glob("regen_backups/*")
        saved = sorted(p.name for p in (backup / "alignment_debug").iterdir())
        assert saved == [f"{mine.stem}.json"]

    def test_a_song_with_only_a_transcription_transcribes_again(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{video.stem}.ass").write_text("", encoding="utf-8")
        tools, processing = make_tools(tmp_path, [str(video)])

        assert tools.can_regenerate(str(video))
        tools.regenerate(str(video))

        regen = processing.enqueue_regen.call_args.args[0]
        assert regen.song.plan.kind == "transcribe"

    def test_a_custom_sheet_is_replayed_over_the_recorded_pick(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        sheet = write_sheet(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)])

        tools.regenerate(str(video))

        plan = processing.enqueue_regen.call_args.args[0].song.plan
        assert (plan.kind, plan.lyrics_path, plan.seed) == (
            "seed",
            sheet,
            {"lyrics_origin": "custom"},
        )

    def test_a_movie_sheet_is_replayed_over_the_recorded_pick(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        sheet = write_movie_sheet(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)])

        tools.regenerate(str(video))

        plan = processing.enqueue_regen.call_args.args[0].song.plan
        assert (plan.kind, plan.lyrics_path, plan.seed) == (
            "seed",
            sheet,
            {"lyrics_origin": "movie_srt"},
        )

    def test_a_custom_sheet_beats_the_transcription_shortcut(self, tmp_path):
        """No bundle and a karaoke file reads as "only a transcription"; the sheet says otherwise."""
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{video.stem}.ass").write_text("", encoding="utf-8")
        write_sheet(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)])

        assert tools.can_regenerate(str(video))
        tools.regenerate(str(video))

        assert processing.enqueue_regen.call_args.args[0].song.plan.seed == {
            "lyrics_origin": "custom"
        }

    def test_a_song_with_no_pick_is_pointed_at_repair(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        tools, processing = make_tools(tmp_path, [str(video)])

        assert not tools.can_regenerate(str(video))
        with pytest.raises(RegenError, match="Repair lyrics"):
            tools.regenerate(str(video))
        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))

    def test_a_busy_song_is_refused_before_any_backup(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)], pending=[str(video)])

        with pytest.raises(RegenError, match="waiting or running"):
            tools.regenerate(str(video))

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))

    def test_a_song_the_queue_refuses_is_reported_busy(self, tmp_path):
        """is_busy and enqueue_regen can disagree if a job lands between them."""
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)])
        processing.enqueue_regen.return_value = False

        with pytest.raises(RegenError, match="waiting or running"):
            tools.regenerate(str(video))

    def test_only_video_songs(self, tmp_path):
        song = tmp_path / "Track.mp3"
        song.write_bytes(b"")
        tools, processing = make_tools(tmp_path, [str(song)])

        assert not tools.can_regenerate(str(song))
        with pytest.raises(RegenError, match="video songs only"):
            tools.regenerate(str(song))
        processing.enqueue_regen.assert_not_called()

    def test_a_backup_that_cannot_be_written_is_reported(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)])

        def disk_full(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pikaraoke.lib.library_tools.backup_text_folders", disk_full)

        with pytest.raises(RegenError, match="disk full"):
            tools.regenerate(str(video))
        processing.enqueue_regen.assert_not_called()


class FakeGenius:
    """A Genius client over a dict of songs that counts its fetches."""

    def __init__(self, songs: dict[int, GeniusSong] | None = None):
        self.songs = songs or {}
        self.fetches: list[int] = []

    def fetch_song(self, genius_id: int) -> GeniusSong:
        self.fetches.append(genius_id)
        if genius_id not in self.songs:
            raise GeniusUnavailable(f"no song {genius_id}")
        return self.songs[genius_id]


LYRICS = "Line one here\nLine two here\nLine three here\nLine four here"
GENIUS_SONG = GeniusSong(text=LYRICS, title="Defying Gravity", artist="Idina Menzel")
SHEET = LYRICS.split("\n")
RECORD = {
    "id": 5,
    "trackName": "Defying Gravity",
    "artistName": "Idina Menzel",
    "albumName": "Wicked",
    "duration": 250.0,
    "syncedLyrics": "[00:10.00] Line one here\n[00:14.00] Line two here\n",
}


def synced(*lines: str) -> str:
    return "".join(f"[00:{10 + 4 * i:02d}.00] {line}\n" for i, line in enumerate(lines))


class TestRepair:
    @pytest.fixture
    def song(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        return video

    def repaired(self, tmp_path, song, source, genius=None, **kwargs):
        genius = genius or FakeGenius({7: GENIUS_SONG, 8: GENIUS_SONG})
        tools, processing = make_tools(tmp_path, [str(song)], genius=genius)
        tools.repair(str(song), source, **kwargs)
        return processing.enqueue_regen.call_args.args[0]

    def test_a_caption_repair_queues_a_fetch_plan_that_wipes_first(self, tmp_path, song):
        regen = self.repaired(tmp_path, song, "caption")

        assert isinstance(regen, RegenJob)
        assert (regen.label, regen.reset) == ("Repair", True)
        assert regen.song.song_path == song
        assert regen.song.plan.kind == "fetch"

    def test_a_genius_repair_queues_a_sidecar_plan_with_the_picked_song(self, tmp_path, song):
        regen = self.repaired(tmp_path, song, "genius", genius_id=7)

        assert regen.reset is True
        assert regen.song.plan.kind == "sidecar"
        assert regen.song.plan.genius_id == 7
        assert regen.song.plan.lrclib_record is None
        assert regen.song.plan.lrclib_skip is False

    def test_a_picked_lrclib_match_travels_with_the_plan(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: {**RECORD, "id": record_id})

        regen = self.repaired(tmp_path, song, "genius", genius_id=7, lrclib_id=5)

        assert regen.song.plan.lrclib_record["id"] == 5
        assert regen.song.plan.lrclib_skip is False

    def test_skipping_lrclib_is_the_plans_choice_and_fetches_nothing(
        self, tmp_path, song, monkeypatch
    ):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))

        regen = self.repaired(tmp_path, song, "genius", genius_id=7, lrclib_id=5, lrclib_skip=True)

        assert regen.song.plan.lrclib_skip is True
        assert regen.song.plan.lrclib_record is None

    def test_a_caption_repair_of_a_custom_song_still_queues_a_fetch_plan(self, tmp_path, song):
        """An explicit pick, so the sheet must not win here (it is deleted by the run)."""
        write_sheet(tmp_path, song.stem)

        regen = self.repaired(tmp_path, song, "caption")

        assert regen.song.plan.kind == "fetch"

    @pytest.mark.parametrize(
        ("source", "kwargs", "replaces"),
        [
            ("caption", {}, True),
            ("genius", {"genius_id": 7}, True),
            ("transcribe", {}, True),
            ("custom", {"text": "Line one\n"}, False),
        ],
    )
    def test_only_a_repair_to_another_source_removes_the_sheet(
        self, tmp_path, song, source, kwargs, replaces
    ):
        regen = self.repaired(tmp_path, song, source, **kwargs)

        assert regen.song.replaces_custom is replaces

    def test_a_custom_repair_queues_the_sheet_plan_with_the_normalized_text(self, tmp_path, song):
        regen = self.repaired(tmp_path, song, "custom", text="[Verse]\r\nLine one\rLine two\n")

        assert (regen.label, regen.reset) == ("Repair", True)
        assert regen.song.song_path == song
        plan = regen.song.plan
        assert (plan.kind, plan.seed, plan.label) == (
            "seed",
            {"lyrics_origin": "custom"},
            "custom sheet",
        )
        assert plan.lyrics_path == tmp_path / "lyrics" / f"{song.stem}.custom.txt"
        assert plan.custom_text == "[Verse]\nLine one\nLine two\n"
        assert (plan.lrclib_record, plan.lrclib_skip) == (None, False)

    def test_a_custom_repair_writes_nothing_until_the_run(self, tmp_path, song):
        self.repaired(tmp_path, song, "custom", text="Line one\n")

        assert not (tmp_path / "lyrics").exists()

    def test_a_custom_repair_backs_up_only_that_song(self, tmp_path, song):
        other = make_video(tmp_path, "B---bbbbbbbbbbb")
        genius_bundle(tmp_path, other.stem)
        write_sheet(tmp_path, other.stem)

        self.repaired(tmp_path, song, "custom", text="Line one\n")

        [backup] = tmp_path.glob("regen_backups/*")
        assert [p.name for p in (backup / "alignment_debug").iterdir()] == [f"{song.stem}.json"]
        assert not (backup / "lyrics").exists()

    def test_an_existing_sheet_is_in_the_backup(self, tmp_path, song):
        write_sheet(tmp_path, song.stem, "the old words\n")

        self.repaired(tmp_path, song, "custom", text="Line one\n")

        [backup] = tmp_path.glob("regen_backups/*")
        saved = (backup / "lyrics" / f"{song.stem}.custom.txt").read_text(encoding="utf-8")
        assert saved == "the old words\n"

    def test_a_picked_lrclib_match_rides_on_a_custom_repair(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: {**RECORD, "id": record_id})

        regen = self.repaired(tmp_path, song, "custom", text="Line one\n", lrclib_id=5)

        assert regen.song.plan.lrclib_record["id"] == 5
        assert regen.song.plan.lrclib_skip is False

    def test_skipping_lrclib_rides_on_a_custom_repair_and_fetches_nothing(
        self, tmp_path, song, monkeypatch
    ):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))

        regen = self.repaired(
            tmp_path, song, "custom", text="Line one\n", lrclib_id=5, lrclib_skip=True
        )

        assert regen.song.plan.lrclib_skip is True
        assert regen.song.plan.lrclib_record is None

    def test_a_custom_repair_asks_genius_for_nothing(self, tmp_path, song):
        genius = FakeGenius({})

        self.repaired(tmp_path, song, "custom", genius=genius, text="Line one\n")

        assert genius.fetches == []

    @pytest.mark.parametrize(
        ("text", "kwargs", "message"),
        [
            ("", {}, "no lyric lines"),
            ("   \n\n  ", {}, "no lyric lines"),
            ("[Chorus]", {}, "no lyric lines"),
            (None, {}, "must be text"),
            (["Line one"], {}, "must be text"),
            ("la " * CUSTOM_SHEET_MAX_CHARS, {}, "too long"),
            ("Line one", {"lrclib_id": 5}, "LRCLIB didn't return"),
        ],
    )
    def test_a_custom_repair_that_cannot_start_changes_nothing(
        self, tmp_path, song, monkeypatch, text, kwargs, message
    ):
        """The run replaces the song's outputs, so every refusal comes before the backup."""
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: None)
        write_sheet(tmp_path, song.stem, "the old words\n")
        tools, processing = make_tools(tmp_path, [str(song)])

        with pytest.raises(RegenError, match=message):
            tools.repair(str(song), "custom", text=text, **kwargs)

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        sheet = tmp_path / "lyrics" / f"{song.stem}.custom.txt"
        assert sheet.read_text(encoding="utf-8") == "the old words\n"

    def test_a_transcribe_repair_queues_a_transcribe_plan(self, tmp_path, song):
        regen = self.repaired(tmp_path, song, "transcribe")

        assert regen.reset is True
        assert regen.song.plan.kind == "transcribe"

    def test_backs_up_only_that_song(self, tmp_path, song):
        other = make_video(tmp_path, "B---bbbbbbbbbbb")
        genius_bundle(tmp_path, other.stem)

        self.repaired(tmp_path, song, "transcribe")

        [backup] = tmp_path.glob("regen_backups/*")
        assert [p.name for p in (backup / "alignment_debug").iterdir()] == [f"{song.stem}.json"]

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"source": "genius", "genius_id": 99}, "Genius didn't return"),
            ({"source": "genius"}, "Pick a Genius song"),
            ({"source": "genius", "genius_id": 7, "lrclib_id": 5}, "LRCLIB didn't return"),
            ({"source": "lyrics-from-the-moon"}, "Unknown lyric source"),
        ],
    )
    def test_a_repair_that_cannot_start_changes_nothing(
        self, tmp_path, song, monkeypatch, kwargs, message
    ):
        """The run wipes the song's outputs, so every refusal comes before the backup."""
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: None)
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))

        with pytest.raises(RegenError, match=message):
            tools.repair(str(song), **kwargs)

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))

    def test_a_match_with_no_synced_lyrics_is_refused(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: {"id": record_id})
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))

        with pytest.raises(RegenError, match="no synced lyrics"):
            tools.repair(str(song), "genius", genius_id=7, lrclib_id=5)

        processing.enqueue_regen.assert_not_called()

    def test_a_caption_repair_needs_a_youtube_id(self, tmp_path):
        [video] = make_videos(tmp_path, "No Id Song")
        tools, processing = make_tools(tmp_path, [str(video)])

        with pytest.raises(RegenError, match="no YouTube ID"):
            tools.repair(str(video), "caption")

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))

    def test_a_busy_song_is_refused_before_anything_is_fetched(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))
        genius = FakeGenius({7: GENIUS_SONG})
        tools, processing = make_tools(tmp_path, [str(song)], pending=[str(song)], genius=genius)

        with pytest.raises(RegenError, match="waiting or running"):
            tools.repair(str(song), "genius", genius_id=7, lrclib_id=5)

        assert genius.fetches == []
        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))

    def test_a_song_the_queue_refuses_is_reported_busy(self, tmp_path, song):
        tools, processing = make_tools(tmp_path, [str(song)])
        processing.enqueue_regen.return_value = False

        with pytest.raises(RegenError, match="waiting or running"):
            tools.repair(str(song), "transcribe")

    def test_only_video_songs(self, tmp_path):
        mp3 = tmp_path / "Track.mp3"
        mp3.write_bytes(b"")
        tools, processing = make_tools(tmp_path, [str(mp3)])

        with pytest.raises(RegenError, match="video songs only"):
            tools.repair(str(mp3), "transcribe")
        processing.enqueue_regen.assert_not_called()


class TestCustomSheetLines:
    def test_the_lines_are_what_the_song_will_display(self):
        text = "[Verse 1]\nLine one here\n\n(Line two) here\n[Chorus]\nLine three here\n"

        assert custom_sheet_lines(text) == ["Line one here", "(Line two) here", "Line three here"]

    def test_any_line_end_style_is_one_line_break(self):
        assert custom_sheet_lines("one a\r\ntwo b\rthree c\nfour d") == [
            "one a",
            "two b",
            "three c",
            "four d",
        ]

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("", "no lyric lines"),
            ("  \n\t\n ", "no lyric lines"),
            ("[Chorus]", "no lyric lines"),
            ("[Verse 1]\n[Chorus]\n\n[Outro]", "no lyric lines"),
            ("...\n♪ ♪", "no lyric lines"),
            (None, "must be text"),
            (123, "must be text"),
            (["one", "two"], "must be text"),
            (b"one", "must be text"),
            ("la " * CUSTOM_SHEET_MAX_CHARS, "too long"),
        ],
    )
    def test_a_sheet_that_cannot_be_used_is_refused_with_a_message(self, text, message):
        with pytest.raises(RegenError, match=message):
            custom_sheet_lines(text)

    def test_a_sheet_of_exactly_the_cap_is_taken(self):
        text = ("la" + "\n") * (CUSTOM_SHEET_MAX_CHARS // 3) + "x" * (CUSTOM_SHEET_MAX_CHARS % 3)

        assert len(text) == CUSTOM_SHEET_MAX_CHARS
        assert custom_sheet_lines(text)


class TestMovieRepair:
    """Repair with movie subtitles: the fit runs again here and only a fit is queued."""

    @pytest.fixture
    def song(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(
            tmp_path,
            video.stem,
            lyrics={"origin": "genius", "genius": GENIUS, "lines": ["one", "two"]},
            media_duration_s=CLIP_S,
            transcribe_words=heard_words(),
        )
        return video

    def repaired(self, tmp_path, song, text):
        tools, processing = make_tools(tmp_path, [str(song)])
        tools.repair(str(song), "movie", text=text)
        return processing.enqueue_regen.call_args.args[0]

    def test_a_slice_that_fits_queues_the_clip_timed_sheet(self, tmp_path, song):
        pasted = movie_slice()

        regen = self.repaired(tmp_path, song, pasted)

        plan = regen.song.plan
        assert (regen.label, regen.reset) == ("Repair", True)
        assert (plan.kind, plan.seed, plan.label) == (
            "seed",
            {"lyrics_origin": "movie_srt"},
            "movie subtitles",
        )
        assert plan.lyrics_path == tmp_path / "lyrics" / f"{song.stem}.custom.srt"
        assert clip_starts(pasted)[0] > MOVIE_OFFSET_S
        assert clip_starts(plan.custom_text) == [
            pytest.approx(slice_clip_start(k), abs=0.1) for k in range(SLICE_LINES)
        ]

    def test_a_movie_repair_keeps_its_own_sheet_and_writes_nothing_until_the_run(
        self, tmp_path, song
    ):
        regen = self.repaired(tmp_path, song, movie_slice())

        assert regen.song.replaces_custom is False
        assert not (tmp_path / "lyrics").exists()

    def test_the_text_is_taken_with_crlf_line_ends(self, tmp_path, song):
        regen = self.repaired(tmp_path, song, movie_slice().replace("\n", "\r\n"))

        assert len(clip_starts(regen.song.plan.custom_text)) == SLICE_LINES

    def test_the_youtube_auto_caption_can_carry_the_fit_alone(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, media_duration_s=CLIP_S)
        asr = tmp_path / "subtitles" / f"{video.stem}.en.asr.json3"
        asr.parent.mkdir()
        asr.write_text(asr_json3(), encoding="utf-8")

        regen = self.repaired(tmp_path, video, movie_slice())

        assert clip_starts(regen.song.plan.custom_text)[0] == pytest.approx(10.0, abs=0.1)

    def test_a_clip_with_no_bundle_length_is_measured(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, transcribe_words=heard_words())
        monkeypatch.setattr("pikaraoke.lib.library_regen.probe_duration", lambda path: CLIP_S)

        regen = self.repaired(tmp_path, video, movie_slice())

        assert len(clip_starts(regen.song.plan.custom_text)) == SLICE_LINES

    def refused(self, tmp_path, song, text, error=MovieSliceRefused):
        """Repair ``song`` with ``text``, which must be refused before anything is backed up."""
        write_sheet(tmp_path, song.stem, "the old words\n")
        tools, processing = make_tools(tmp_path, [str(song)])

        with pytest.raises(error) as refused:
            tools.repair(str(song), "movie", text=text)

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        sheet = tmp_path / "lyrics" / f"{song.stem}.custom.txt"
        assert sheet.read_text(encoding="utf-8") == "the old words\n"
        return refused.value

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            (None, "subtitles must be text"),
            (["1"], "subtitles must be text"),
            ("la " * MOVIE_SUBTITLES_MAX_CHARS, "subtitles are too long"),
        ],
        ids=["none", "list", "too_long"],
    )
    def test_text_that_is_not_usable_changes_nothing(self, tmp_path, song, text, message):
        """The run replaces the song's outputs, so every refusal comes before the backup."""
        assert message in str(self.refused(tmp_path, song, text, RegenError))

    @pytest.mark.parametrize(
        ("text", "status", "reason", "matched", "total"),
        [
            ("just some words, not subtitles", NOT_SRT, None, 0, 0),
            ("1\n00:00:01,000 --> 00:00:02,000\n[MUSIC]\n", REFUSED, TOO_FEW, 0, 0),
            (movie_slice(lines=range(40, 52)), REFUSED, TOO_FEW, 0, 12),
            (
                movie_slice(offset=lambda k: 900.0 if k < SLICE_LINES // 2 else 2400.0),
                REFUSED,
                DISAGREE,
                SLICE_LINES,
                SLICE_LINES,
            ),
            (
                "".join(f"{n}\n00:00:01,000 --> 00:00:02,000\nla\n\n" for n in range(1, 3002)),
                TOO_LONG,
                None,
                0,
                3001,
            ),
        ],
        ids=["not_srt", "no_lines", "too_few", "disagree", "too_many"],
    )
    def test_a_slice_that_does_not_fit_changes_nothing(
        self, tmp_path, song, text, status, reason, matched, total
    ):
        """The refusal carries the check, so the route words it as the Check fit card does."""
        fit = self.refused(tmp_path, song, text).check.fit

        assert (fit.status, fit.reason, fit.matched, fit.total) == (status, reason, matched, total)

    def test_a_song_with_no_heard_words_is_told_to_regenerate_first(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, media_duration_s=CLIP_S)

        check = self.refused(tmp_path, video, movie_slice()).check

        assert (check.fit.status, check.regenerate_helps) == (NO_REFERENCE, True)

    def test_a_transcribed_song_is_not_told_to_regenerate(self, tmp_path, monkeypatch):
        """A transcribe run keeps no heard words, so a Regenerate would not help."""
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{video.stem}.ass").write_text("", encoding="utf-8")
        monkeypatch.setattr("pikaraoke.lib.library_regen.probe_duration", lambda path: CLIP_S)

        check = self.refused(tmp_path, video, movie_slice()).check

        assert (check.fit.status, check.regenerate_helps) == (NO_REFERENCE, False)

    def test_a_whole_film_longer_than_a_lyric_sheet_fits(self, tmp_path, song):
        filler = "and the night goes on in the quiet little town " * 4
        film = srt.compose(
            [
                srt.Subtitle(n, timedelta(seconds=n), timedelta(seconds=n + 0.5), filler)
                for n in range(1, 600)
            ]
            + list(srt.parse(movie_slice()))
        )
        assert len(film) > CUSTOM_SHEET_MAX_CHARS

        regen = self.repaired(tmp_path, song, film)

        assert len(clip_starts(regen.song.plan.custom_text)) == SLICE_LINES

    def test_a_clip_whose_length_cannot_be_read_is_refused(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, transcribe_words=heard_words())
        monkeypatch.setattr("pikaraoke.lib.library_regen.probe_duration", lambda path: None)
        tools, processing = make_tools(tmp_path, [str(video)])

        with pytest.raises(RegenError, match="clip's length"):
            tools.repair(str(video), "movie", text=movie_slice())

        processing.enqueue_regen.assert_not_called()

    def test_an_auto_caption_that_cannot_be_read_is_ignored_and_says_so(self, tmp_path, caplog):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, media_duration_s=CLIP_S)
        asr = tmp_path / "subtitles" / f"{video.stem}.en.asr.json3"
        asr.parent.mkdir()
        asr.write_bytes("caf\xe9".encode("latin-1"))
        tools, _ = make_tools(tmp_path, [str(video)])

        check = tools.check_movie_slice(str(video), movie_slice())

        assert check.fit.status == "no_reference"
        assert "Could not read the auto-caption" in caplog.text

    def test_the_check_takes_video_songs_only(self, tmp_path):
        mp3 = tmp_path / "Track---aaaaaaaaaaa.mp3"
        mp3.write_bytes(b"")
        tools, _ = make_tools(tmp_path, [str(mp3)])

        with pytest.raises(RegenError, match="video songs only"):
            tools.check_movie_slice(str(mp3), movie_slice())

    def test_the_check_answers_a_refusal_and_does_not_raise(self, tmp_path, song):
        tools, processing = make_tools(tmp_path, [str(song)])

        check = tools.check_movie_slice(str(song), "just some words, not subtitles")

        assert check.fit.status == "not_srt"
        processing.enqueue_regen.assert_not_called()

    def test_the_check_returns_the_fit_the_repair_would_save(self, tmp_path, song):
        tools, processing = make_tools(tmp_path, [str(song)])

        check = tools.check_movie_slice(str(song), movie_slice())
        tools.repair(str(song), "movie", text=movie_slice())

        assert check.fit.status == "fits"
        assert processing.enqueue_regen.call_args.args[0].song.plan.custom_text == check.fit.srt


LRC_RECORD = {
    "id": 11,
    "trackName": "Invented Song",
    "artistName": "Invented Artist",
    "albumName": "Invented Album",
    "duration": CLIP_S,
    "syncedLyrics": lrc_slice(),
}


class TestLrcTimingRepair:
    """Repair with an LRCLIB match's own line times: the fit runs again here, and only a viable
    one is queued."""

    @pytest.fixture
    def song(self, tmp_path):
        """A song with heard words and the LRC on disk (record 11, as long as the clip)."""
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(
            tmp_path,
            video.stem,
            lyrics={"origin": "genius", "genius": GENIUS, "lines": ["one", "two"]},
            media_duration_s=CLIP_S,
            transcribe_words=heard_words(),
        )
        self.write_match(video, LRC_RECORD)
        return video

    @staticmethod
    def write_match(video: Path, record: dict) -> Path:
        path = lrclib.lrc_path(video)
        path.parent.mkdir(exist_ok=True)
        lrclib.write_lrc(path, record)
        return path

    @pytest.fixture
    def fetched(self, monkeypatch):
        """The ids LRCLIB's get-by-id was asked for (it has no record for any)."""
        fetched = []
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: fetched.append(record_id))
        return fetched

    def repaired(self, tmp_path, song, **kwargs):
        tools, processing = make_tools(tmp_path, [str(song)])
        tools.repair(str(song), "lrclib", **kwargs)
        return processing.enqueue_regen.call_args.args[0]

    def test_with_no_id_the_lrc_on_disk_is_checked(self, tmp_path, song, fetched):
        tools, processing = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), None)

        assert (check.fit.status, check.gap_s, check.viable) == (FITS, 0, True)
        assert (check.record["id"], check.record["trackName"]) == (11, "Invented Song")
        assert check.regenerate_helps is True
        assert fetched == []
        processing.enqueue_regen.assert_not_called()

    def test_with_an_id_that_record_is_checked_not_the_one_on_disk(
        self, tmp_path, song, monkeypatch
    ):
        other = {
            **LRC_RECORD,
            "id": 12,
            "duration": CLIP_S + 10,
            "syncedLyrics": lrc_slice(lines=range(9)),
        }
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: other)
        tools, _ = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), 12)

        assert (check.record["id"], check.gap_s, check.fit.total) == (12, 10, 9)

    def test_a_record_a_search_listed_is_not_asked_of_lrclib_again(
        self, tmp_path, song, monkeypatch
    ):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))
        monkeypatch.setattr(lrclib, "search_query", lambda query: [{**LRC_RECORD, "id": 13}])
        tools, _ = make_tools(tmp_path, [str(song)])
        tools.lrclib_candidates(str(song), ["one"], "t a")

        assert tools.check_lrc_timing(str(song), 13).record["id"] == 13

    @pytest.mark.parametrize(
        ("gap", "viable"),
        [
            (0, True),
            (LRC_MAX_GAP_S, True),
            (-LRC_MAX_GAP_S, True),
            (LRC_MAX_GAP_S + 1, False),
            (-LRC_MAX_GAP_S - 1, False),
        ],
    )
    def test_the_match_may_be_a_little_longer_or_shorter_than_the_clip(
        self, tmp_path, song, gap, viable
    ):
        self.write_match(song, {**LRC_RECORD, "duration": CLIP_S + gap})
        tools, _ = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), None)

        assert check.fit.status == FITS  # the lines fit either way: only the length is judged
        assert (check.gap_s, check.viable) == (gap, viable)

    def test_a_match_with_no_length_is_not_viable(self, tmp_path, song):
        self.write_match(song, {**LRC_RECORD, "duration": None})
        tools, _ = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), None)

        assert (check.fit.status, check.gap_s, check.viable) == (FITS, None, False)

    def test_a_fit_that_is_refused_is_not_viable_whatever_the_length(self, tmp_path, song):
        self.write_match(song, {**LRC_RECORD, "syncedLyrics": lrc_slice(lines=range(40, 52))})
        tools, _ = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), None)

        assert (check.fit.status, check.fit.reason, check.gap_s) == (REFUSED, TOO_FEW, 0)
        assert check.viable is False

    def test_a_match_with_no_timed_lines_is_refused_as_not_srt(self, tmp_path, song):
        self.write_match(song, {**LRC_RECORD, "syncedLyrics": "no stamps here\n"})
        tools, _ = make_tools(tmp_path, [str(song)])

        assert tools.check_lrc_timing(str(song), None).fit.status == NOT_SRT

    def test_a_song_with_no_heard_words_is_told_to_regenerate_first(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, media_duration_s=CLIP_S)
        self.write_match(video, LRC_RECORD)
        tools, _ = make_tools(tmp_path, [str(video)])

        check = tools.check_lrc_timing(str(video), None)

        assert (check.fit.status, check.viable, check.regenerate_helps) == (
            NO_REFERENCE,
            False,
            True,
        )

    def test_lines_heard_far_from_their_time_are_flagged_and_do_not_stop_a_viable_fit(
        self, tmp_path, song
    ):
        """Decision 4: the admin reads the flagged lines, then confirms."""
        self.write_match(
            song,
            {**LRC_RECORD, "syncedLyrics": lrc_slice(offset=lambda k: 20.0 if k >= 8 else 0.0)},
        )
        tools, _ = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), None)

        assert check.viable is True
        assert check.fit.mistimed == (8, 9, 10, 11)

    @pytest.mark.parametrize("remove", ["missing", "skipped"])
    def test_a_song_with_no_usable_lrc_and_no_id_says_to_search(self, tmp_path, song, remove):
        path = lrclib.lrc_path(song)
        path.unlink()
        if remove == "skipped":
            lrclib.write_skip_marker(path)
        tools, _ = make_tools(tmp_path, [str(song)])

        with pytest.raises(RegenError, match="Search for one"):
            tools.check_lrc_timing(str(song), None)

    def test_an_lrc_that_cannot_be_read_is_refused_and_says_so(self, tmp_path, song, caplog):
        lrclib.lrc_path(song).write_bytes("caf\xe9".encode("latin-1"))
        tools, _ = make_tools(tmp_path, [str(song)])

        with pytest.raises(RegenError, match="Could not read"):
            tools.check_lrc_timing(str(song), None)

        assert "Could not read the LRCLIB match" in caplog.text

    @pytest.mark.parametrize(
        ("returned", "message"),
        [(None, "didn't return"), ({**LRC_RECORD, "syncedLyrics": ""}, "no synced lyrics")],
        ids=["gone", "unsynced"],
    )
    def test_a_record_lrclib_cannot_give_is_refused(
        self, tmp_path, song, monkeypatch, returned, message
    ):
        monkeypatch.setattr(lrclib, "get_record", lambda record_id: returned)
        tools, _ = make_tools(tmp_path, [str(song)])

        with pytest.raises(RegenError, match=message):
            tools.check_lrc_timing(str(song), 12)

    def test_a_clip_whose_length_cannot_be_read_is_refused(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_bundle(tmp_path, video.stem, lyrics={"origin": "srt"}, transcribe_words=heard_words())
        self.write_match(video, LRC_RECORD)
        monkeypatch.setattr("pikaraoke.lib.library_regen.probe_duration", lambda path: None)
        tools, processing = make_tools(tmp_path, [str(video)])

        with pytest.raises(RegenError, match="clip's length"):
            tools.repair(str(video), "lrclib")

        processing.enqueue_regen.assert_not_called()

    def test_the_check_takes_video_songs_only(self, tmp_path):
        mp3 = tmp_path / "Track---aaaaaaaaaaa.mp3"
        mp3.write_bytes(b"")
        tools, _ = make_tools(tmp_path, [str(mp3)])

        with pytest.raises(RegenError, match="video songs only"):
            tools.check_lrc_timing(str(mp3), None)

    def test_a_viable_match_queues_the_fitted_lines_as_the_songs_sheet(self, tmp_path, song):
        self.write_match(song, {**LRC_RECORD, "syncedLyrics": lrc_slice(offset=lambda k: 3.0)})

        regen = self.repaired(tmp_path, song)

        plan = regen.song.plan
        assert (regen.label, regen.reset) == ("Repair", True)
        assert (plan.kind, plan.seed, plan.label) == (
            "seed",
            {"lyrics_origin": "lrclib_srt"},
            "LRCLIB timing",
        )
        assert plan.lyrics_path == tmp_path / "lyrics" / f"{song.stem}.lrclib.srt"
        # The LRC says 3 s late; the saved sheet is in the clip's time, not the match's.
        assert clip_starts(plan.custom_text) == [
            pytest.approx(slice_clip_start(k), abs=0.1) for k in range(SLICE_LINES)
        ]

    def test_the_lrc_on_disk_stays_and_nothing_is_written_until_the_run(self, tmp_path, song):
        match = lrclib.lrc_path(song).read_text(encoding="utf-8")

        regen = self.repaired(tmp_path, song)

        assert regen.song.plan.lrclib_record is None
        assert regen.song.replaces_custom is False
        assert lrclib.lrc_path(song).read_text(encoding="utf-8") == match
        assert not (tmp_path / "lyrics" / f"{song.stem}.lrclib.srt").exists()

    def test_a_record_given_by_id_is_queued_to_become_the_songs_lrc(
        self, tmp_path, song, monkeypatch
    ):
        listed = {**LRC_RECORD, "id": 14, "trackName": "Listed"}
        monkeypatch.setattr(lrclib, "search_query", lambda query: [listed])
        tools, processing = make_tools(tmp_path, [str(song)])
        tools.lrclib_candidates(str(song), ["one"], "t a")

        tools.repair(str(song), "lrclib", lrclib_id=14)

        plan = processing.enqueue_regen.call_args.args[0].song.plan
        assert plan.lrclib_record is listed
        assert plan.custom_text is not None

    def refused(self, tmp_path, song, **kwargs):
        """Repair ``song``, which must be refused before anything is backed up."""
        write_sheet(tmp_path, song.stem, "the old words\n")
        tools, processing = make_tools(tmp_path, [str(song)])

        with pytest.raises(LrcTimingRefused) as refused:
            tools.repair(str(song), "lrclib", **kwargs)

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        sheet = tmp_path / "lyrics" / f"{song.stem}.custom.txt"
        assert sheet.read_text(encoding="utf-8") == "the old words\n"
        return refused.value

    def test_a_match_too_far_off_in_length_changes_nothing(self, tmp_path, song):
        self.write_match(song, {**LRC_RECORD, "duration": CLIP_S + 38})

        check = self.refused(tmp_path, song).check

        assert (check.fit.status, check.gap_s, check.viable) == (FITS, 38, False)

    def test_a_fit_that_is_refused_changes_nothing(self, tmp_path, song):
        self.write_match(song, {**LRC_RECORD, "syncedLyrics": lrc_slice(lines=range(40, 52))})

        check = self.refused(tmp_path, song).check

        assert (check.fit.status, check.fit.reason) == (REFUSED, TOO_FEW)

    def test_the_repair_fits_again_and_refuses_on_its_own_result(self, tmp_path, song, monkeypatch):
        """What was saved is never a number an earlier check said: here the second fit differs."""
        real = fit_slice
        calls = []

        def second_fit_differs(srt_text, streams, length):
            calls.append(1)
            return real(srt_text if len(calls) == 1 else "", streams, length)

        monkeypatch.setattr("pikaraoke.lib.library_tools.fit_slice", second_fit_differs)
        tools, processing = make_tools(tmp_path, [str(song)])

        assert tools.check_lrc_timing(str(song), None).viable is True
        with pytest.raises(LrcTimingRefused) as refused:
            tools.repair(str(song), "lrclib")

        assert refused.value.check.fit.status == NOT_SRT
        processing.enqueue_regen.assert_not_called()

    def test_with_no_lrc_and_no_id_nothing_is_queued(self, tmp_path, song):
        lrclib.lrc_path(song).unlink()
        tools, processing = make_tools(tmp_path, [str(song)])

        with pytest.raises(RegenError, match="Search for one"):
            tools.repair(str(song), "lrclib")

        processing.enqueue_regen.assert_not_called()

    def test_a_song_with_a_regen_waiting_is_busy(self, tmp_path, song):
        tools, processing = make_tools(tmp_path, [str(song)], pending=[str(song)])

        with pytest.raises(RegenError, match="waiting or running"):
            tools.repair(str(song), "lrclib")

        processing.enqueue_regen.assert_not_called()

    def test_the_check_returns_the_fit_the_repair_would_save(self, tmp_path, song):
        tools, processing = make_tools(tmp_path, [str(song)])

        check = tools.check_lrc_timing(str(song), None)
        tools.repair(str(song), "lrclib")

        assert processing.enqueue_regen.call_args.args[0].song.plan.custom_text == check.fit.srt


class TestCustomStart:
    """What the repair page's custom-lyrics box and its LRCLIB search start with."""

    @pytest.fixture
    def song(self, tmp_path):
        [video] = make_videos(tmp_path, "Some Song (Official Video)---aaaaaaaaaaa")
        return video

    def start(self, tmp_path, song):
        tools, _ = make_tools(tmp_path, [str(song)])
        return tools.custom_start(str(song))

    def test_the_sheet_on_disk_comes_first(self, tmp_path, song):
        genius_bundle(tmp_path, song.stem)
        write_sheet(tmp_path, song.stem, "my own words\n")

        assert self.start(tmp_path, song)["text"] == "my own words\n"

    def test_a_movie_sheet_is_not_lyric_lines_so_the_box_starts_from_the_current_lyrics(
        self, tmp_path, song
    ):
        genius_bundle(tmp_path, song.stem)
        write_movie_sheet(tmp_path, song.stem)

        assert self.start(tmp_path, song)["text"] == "one\ntwo"

    def test_the_movie_box_starts_with_the_saved_slice(self, tmp_path, song):
        genius_bundle(tmp_path, song.stem)
        write_movie_sheet(tmp_path, song.stem, MOVIE_SRT)

        start = self.start(tmp_path, song)

        assert start["movie"] == MOVIE_SRT
        assert start["text"] == "one\ntwo"  # the typed box is not filled from it

    def test_both_boxes_start_from_their_own_sheet_when_both_are_on_disk(self, tmp_path, song):
        write_sheet(tmp_path, song.stem, "my own words\n")
        write_movie_sheet(tmp_path, song.stem, MOVIE_SRT)

        start = self.start(tmp_path, song)

        assert (start["text"], start["movie"]) == ("my own words\n", MOVIE_SRT)

    def test_without_a_movie_sheet_the_movie_box_starts_empty(self, tmp_path, song):
        genius_bundle(tmp_path, song.stem)
        write_sheet(tmp_path, song.stem, "my own words\n")

        assert self.start(tmp_path, song)["movie"] == ""

    def test_a_movie_sheet_that_cannot_be_read_starts_the_box_empty_and_says_so(
        self, tmp_path, song, caplog
    ):
        write_movie_sheet(tmp_path, song.stem).write_bytes("caf\xe9\n".encode("latin-1"))

        assert self.start(tmp_path, song)["movie"] == ""
        assert "Could not read the .custom.srt sheet" in caplog.text

    def test_without_a_sheet_it_is_the_lines_of_the_current_lyrics(self, tmp_path, song):
        genius_bundle(tmp_path, song.stem)

        assert self.start(tmp_path, song)["text"] == "one\ntwo"

    def test_with_nothing_it_is_empty(self, tmp_path, song):
        assert self.start(tmp_path, song)["text"] == ""

    def test_a_sheet_that_cannot_be_read_falls_back_to_the_bundle_and_says_so(
        self, tmp_path, song, caplog
    ):
        genius_bundle(tmp_path, song.stem)
        sheet = write_sheet(tmp_path, song.stem)
        sheet.write_bytes("caf\xe9\n".encode("latin-1"))

        assert self.start(tmp_path, song)["text"] == "one\ntwo"
        assert "Could not read the .custom.txt sheet" in caplog.text

    def test_the_search_starts_from_the_genius_song_the_bundle_records(self, tmp_path, song):
        genius_bundle(tmp_path, song.stem)

        assert self.start(tmp_path, song)["query"] == "Song Artist"

    def test_the_search_drops_feature_credits_as_the_pipeline_does(self, tmp_path, song):
        genius = {**GENIUS, "title": "Song (Ft. Guest) [Live]", "artist": "Artist"}
        write_bundle(tmp_path, song.stem, lyrics={"origin": "genius", "genius": genius})

        assert self.start(tmp_path, song)["query"] == "Song Artist"

    def test_without_one_it_starts_from_the_file_name(self, tmp_path, song):
        assert self.start(tmp_path, song)["query"] == "Some Song"


class TestGeniusSong:
    def test_a_song_is_fetched_once_for_the_preview_the_search_and_the_queue(self, tmp_path):
        genius = FakeGenius({7: GENIUS_SONG})
        tools, _ = make_tools(tmp_path, [], genius=genius)

        assert tools.genius_song(7) is tools.genius_song(7)
        assert genius.fetches == [7]

    def test_only_the_last_few_are_kept(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pikaraoke.lib.library_tools.GENIUS_CACHE_SIZE", 2)
        genius = FakeGenius({n: GENIUS_SONG for n in (1, 2, 3)})
        tools, _ = make_tools(tmp_path, [], genius=genius)

        for genius_id in (1, 2, 3, 3, 2, 1):
            tools.genius_song(genius_id)

        assert genius.fetches == [1, 2, 3, 1]

    def test_a_song_genius_cannot_return_is_not_cached(self, tmp_path):
        genius = FakeGenius()
        tools, _ = make_tools(tmp_path, [], genius=genius)

        for _attempt in range(2):
            with pytest.raises(GeniusUnavailable):
                tools.genius_song(7)

        assert genius.fetches == [7, 7]


class TestCaptionCheck:
    def test_measures_the_caption_without_writing_to_the_library(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        checked = MagicMock(return_value=CaptionCheck(found=True, wpm=40.0, passed=True))
        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", checked)
        tools, _ = make_tools(tmp_path, [str(video)])

        assert tools.caption_check(str(video)) == CaptionCheck(True, 40.0, True)

        [job] = checked.call_args.args
        assert job.song_path == video

    def test_a_custom_song_with_a_youtube_id_can_still_check_its_caption(
        self, tmp_path, monkeypatch
    ):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        write_sheet(tmp_path, video.stem)
        checked = MagicMock(return_value=CaptionCheck(found=True, wpm=40.0, passed=True))
        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", checked)
        tools, _ = make_tools(tmp_path, [str(video)])

        assert tools.caption_check(str(video)).passed
        checked.assert_called_once()

    def test_a_song_with_no_youtube_id_has_nothing_to_check(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "No Id Song")
        checked = MagicMock()
        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", checked)
        tools, _ = make_tools(tmp_path, [str(video)])

        with pytest.raises(RegenError, match="no YouTube ID"):
            tools.caption_check(str(video))
        checked.assert_not_called()

    def test_only_video_songs(self, tmp_path):
        mp3 = tmp_path / "Track---aaaaaaaaaaa.mp3"
        mp3.write_bytes(b"")
        tools, _ = make_tools(tmp_path, [str(mp3)])

        with pytest.raises(RegenError, match="video songs only"):
            tools.caption_check(str(mp3))


class TestLrclibCandidates:
    @pytest.fixture
    def song(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem, media_duration_s=257.0)
        return video

    def tools(self, tmp_path, song, records, monkeypatch):
        searches = []

        def fake_search(query):
            searches.append(query)
            return records

        monkeypatch.setattr(lrclib, "search_query", fake_search)
        tools, _ = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))
        return tools, searches

    def full(self, **fields):
        lines = ("Line one here", "Line two here", "Line three here", "Line four here")
        return {**RECORD, "syncedLyrics": synced(*lines), **fields}

    def test_each_candidate_is_scored_against_the_genius_lyrics(self, tmp_path, song, monkeypatch):
        records = [
            self.full(id=1, duration=255.0),
            # two lines the lyrics have and one they don't: 2 of its 3 cues map
            {
                **RECORD,
                "id": 2,
                "duration": 354.0,
                "syncedLyrics": synced("Line one here", "Line two here", "Words from nowhere"),
            },
        ]
        tools, searches = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), SHEET, "defying gravity idina menzel")

        assert searches == ["defying gravity idina menzel"]
        assert found["video_duration_s"] == 257.0
        full, partial = found["candidates"]
        assert (full["id"], full["mapped"], full["sheet_lines"]) == (1, 4, 4)
        assert (partial["id"], partial["mapped"], partial["sheet_lines"]) == (2, 2, 4)
        assert (full["trackName"], full["artistName"], full["albumName"]) == (
            "Defying Gravity",
            "Idina Menzel",
            "Wicked",
        )
        assert (full["duration_diff_s"], partial["duration_diff_s"]) == (-2, 97)
        assert full["syncedLyrics"] == records[0]["syncedLyrics"]

    def test_best_is_the_candidate_the_selection_rule_picks(self, tmp_path, song, monkeypatch):
        records = [{**RECORD, "id": 2, "duration": 254.0}, self.full(id=1, duration=300.0)]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), SHEET, "t a")

        assert [(c["id"], c["best"]) for c in found["candidates"]] == [(2, False), (1, True)]

    def test_current_is_the_match_the_lrc_on_disk_records(self, tmp_path, song, monkeypatch):
        lrclib.write_lrc(lrclib.lrc_path(song), {**RECORD, "id": 2})
        records = [self.full(id=1), self.full(id=2)]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), SHEET, "t a")

        assert [(c["id"], c["current"]) for c in found["candidates"]] == [(1, False), (2, True)]

    @pytest.mark.parametrize("on_disk", ["marker", "not-utf8", "none"])
    def test_no_candidate_is_current_without_a_readable_match_on_disk(
        self, tmp_path, song, monkeypatch, on_disk
    ):
        lrc = lrclib.lrc_path(song)
        if on_disk == "marker":
            lrclib.write_skip_marker(lrc)
        elif on_disk == "not-utf8":
            lrc.parent.mkdir(exist_ok=True)
            lrc.write_bytes("[ti:Café]\n".encode("latin-1"))
        records = [self.full(id=1), {k: v for k, v in self.full().items() if k != "id"}]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), SHEET, "t a")

        assert [c["current"] for c in found["candidates"]] == [False, False]

    def test_a_record_without_synced_lyrics_is_left_out(self, tmp_path, song, monkeypatch):
        records = [{"id": 3, "trackName": "Plain only", "syncedLyrics": None}, self.full(id=1)]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), SHEET, "t a")

        assert [c["id"] for c in found["candidates"]] == [1]

    def test_no_matches_is_an_empty_list(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [], monkeypatch)

        assert tools.lrclib_candidates(str(song), SHEET, "t a")["candidates"] == []

    def test_a_match_with_no_length_has_no_difference(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [self.full(id=1, duration=None)], monkeypatch)

        [candidate] = tools.lrclib_candidates(str(song), SHEET, "t a")["candidates"]

        assert candidate["duration_diff_s"] is None

    def test_candidates_are_scored_against_whatever_lines_are_given(
        self, tmp_path, song, monkeypatch
    ):
        records = [self.full(id=1)]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), ["Line one here", "Line two here"], "t a")

        [candidate] = found["candidates"]
        assert (candidate["mapped"], candidate["sheet_lines"]) == (2, 2)

    def test_a_genius_songs_lines_are_the_ones_it_displays(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [], monkeypatch)

        assert tools.genius_sheet_lines(7) == SHEET

    def test_genius_lyrics_that_cannot_be_fetched_raise(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [self.full(id=1)], monkeypatch)

        with pytest.raises(GeniusUnavailable):
            tools.genius_sheet_lines(99)


class TestRepairUsesTheListedRecord:
    """LRCLIB's get-by-id can be down while its search works (Phase 6's live run)."""

    @pytest.fixture
    def song(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem, media_duration_s=257.0)
        return video

    @pytest.fixture
    def fetched(self, monkeypatch):
        """The ids LRCLIB's get-by-id was asked for; it returns a record for each."""
        fetched = []

        def get_record(record_id):
            fetched.append(record_id)
            return {**RECORD, "id": record_id, "trackName": "fetched"}

        monkeypatch.setattr(lrclib, "get_record", get_record)
        return fetched

    def listed(self, tools, song, monkeypatch, *ids):
        records = [{**RECORD, "id": record_id} for record_id in ids]
        monkeypatch.setattr(lrclib, "search_query", lambda query: records)
        tools.lrclib_candidates(str(song), SHEET, "t a")
        return records

    def queued_record(self, tools, processing, song, lrclib_id):
        tools.repair(str(song), "genius", genius_id=7, lrclib_id=lrclib_id)
        return processing.enqueue_regen.call_args.args[0].song.plan.lrclib_record

    def test_a_repair_after_a_search_queues_the_listed_record(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))
        _, listed = self.listed(tools, song, monkeypatch, 4, 5)

        assert self.queued_record(tools, processing, song, 5) is listed

    def test_a_custom_repair_after_a_search_queues_the_listed_record_too(
        self, tmp_path, song, monkeypatch
    ):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))
        tools, processing = make_tools(tmp_path, [str(song)])
        _, listed = self.listed(tools, song, monkeypatch, 4, 5)

        tools.repair(str(song), "custom", text="Line one\n", lrclib_id=5)

        assert processing.enqueue_regen.call_args.args[0].song.plan.lrclib_record is listed

    def test_without_a_search_a_repair_still_asks_lrclib(self, tmp_path, song, fetched):
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))

        record = self.queued_record(tools, processing, song, 5)

        assert fetched == [5]
        assert (record["id"], record["trackName"]) == (5, "fetched")

    def test_a_record_without_an_id_is_not_remembered(self, tmp_path, song, monkeypatch, fetched):
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))
        no_id = {k: v for k, v in RECORD.items() if k != "id"}
        monkeypatch.setattr(lrclib, "search_query", lambda query: [no_id])
        tools.lrclib_candidates(str(song), SHEET, "t a")

        self.queued_record(tools, processing, song, 5)

        assert fetched == [5]

    def test_only_the_last_few_listed_are_kept(self, tmp_path, song, monkeypatch, fetched):
        monkeypatch.setattr("pikaraoke.lib.library_tools.LRCLIB_CACHE_SIZE", 2)
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))
        for ids in ((1, 2), (1,), (3,)):  # listed again, 1 counts as newer than 2
            self.listed(tools, song, monkeypatch, *ids)

        for record_id in (1, 3, 2):
            self.queued_record(tools, processing, song, record_id)

        assert fetched == [2]


# --- bulk runs -------------------------------------------------------------

PASS = CaptionCheck(found=True, wpm=40.0, passed=True)
SPARSE = CaptionCheck(found=True, wpm=3.0, passed=False)
NO_CAPTION = CaptionCheck(found=False, wpm=None, passed=False)

STEMS = {
    "current": "Current---aaaaaaaaaaa",
    "behind": "Behind---bbbbbbbbbbb",
    "unlined": "Unlined---ccccccccccc",
    "caption": "Caption---ddddddddddd",
    "transcribed": "Transcribed---eeeeeeeeeee",
    "unprocessed": "Unprocessed---fffffffffff",
    "no_id": "No Id Song",
}
KEY_OF = {stem: key for key, stem in STEMS.items()}

# Every song with a YouTube id gets an answer; the rest of a run never asks.
RUN_ANSWERS = {
    "current": PASS,
    "behind": NO_CAPTION,
    "unlined": PASS,
    "caption": PASS,
    "transcribed": SPARSE,
    "unprocessed": SPARSE,
}


def bulk_library(folder: Path) -> dict[str, str]:
    """One video for each state a run sorts songs by; returns the library's path of each.

    current      genius bundle, up to date: has a lyric source to replay
    behind       genius bundle, an older version: has one too
    unlined      an older bundle with a Genius id but no lines: nothing to replay, can keep
    caption      a YouTube-caption bundle with its caption file: has a source
    transcribed  a karaoke file and no bundle: "no lyrics"
    unprocessed  nothing yet, with a YouTube id
    no_id        nothing yet, and no YouTube id
    """
    videos = {key: make_video(folder, stem) for key, stem in STEMS.items()}
    genius_bundle(folder, videos["current"].stem)
    genius_bundle(folder, videos["behind"].stem, schema_version=SCHEMA_VERSION - 1)
    write_bundle(
        folder,
        videos["unlined"].stem,
        schema_version=SCHEMA_VERSION - 1,
        lyrics={"origin": "genius", "genius": GENIUS},
    )
    write_bundle(folder, videos["caption"].stem, lyrics={"origin": "srt"})
    subtitles = folder / "subtitles"
    subtitles.mkdir()
    cue = "1\n00:00:01,000 --> 00:00:02,000\nhello\n\n"
    (subtitles / f"{videos['caption'].stem}.en.srt").write_text(cue, encoding="utf-8")
    (folder / "karaoke").mkdir()
    (folder / "karaoke" / f"{videos['transcribed'].stem}.ass").write_text("", encoding="utf-8")
    return {key: str(video) for key, video in videos.items()}


def answer_captions(monkeypatch, answers: dict[str, CaptionCheck]) -> list[str]:
    """Patch the caption check to answer by song key (no caption when unlisted).

    Returns the list that fills with the stems asked about, in order.
    """
    by_stem = {STEMS[key]: check for key, check in answers.items()}
    asked: list[str] = []

    def check(job):
        asked.append(job.song_path.stem)
        return by_stem.get(job.song_path.stem, NO_CAPTION)

    monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", check)
    return asked


def hold_captions(monkeypatch) -> threading.Event:
    """Patch the caption check to wait for the returned event, then pass every song."""
    release = threading.Event()

    def check(job):
        release.wait(10)
        return PASS

    monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", check)
    return release


def finish_checks(tools: LibraryTools) -> None:
    if tools._checker is not None:
        tools._checker.join(10)
        assert not tools._checker.is_alive()


def groups(tools: LibraryTools) -> dict[str, str]:
    """The open run's song keys with their groups."""
    return {KEY_OF[Path(s["song"]).stem]: s["group"] for s in tools.run_view()["songs"]}


def open_run(tmp_path, monkeypatch, mode, answers=None):
    """A bulk library with its run open and checked; returns (tools, processing, paths)."""
    paths = bulk_library(tmp_path)
    answer_captions(monkeypatch, answers or {})
    tools, processing = make_tools(tmp_path, list(paths.values()))
    tools.open_run(mode)
    finish_checks(tools)
    return tools, processing, paths


def run_song(tools: LibraryTools, key: str) -> dict:
    return next(s for s in tools.run_view()["songs"] if Path(s["song"]).stem == STEMS[key])


class TestOpenRun:
    @pytest.mark.parametrize(
        "mode, checked, expected",
        [
            ("stale", {"unlined"}, {"behind": "reuse", "unlined": "caption"}),
            (
                "all",
                {"unlined", "unprocessed"},
                {
                    "current": "reuse",
                    "behind": "reuse",
                    "unlined": "caption",
                    "caption": "reuse",
                    "transcribed": "transcribe",
                    "unprocessed": "needs_pick",
                    "no_id": "needs_pick",
                },
            ),
            (
                "reset",
                {"current", "behind", "unlined", "caption", "transcribed", "unprocessed"},
                {
                    "current": "caption",
                    "behind": "needs_pick",
                    "unlined": "caption",
                    "caption": "caption",
                    "transcribed": "needs_pick",
                    "unprocessed": "needs_pick",
                    "no_id": "needs_pick",
                },
            ),
        ],
    )
    def test_each_mode_checks_and_sorts_its_songs_by_the_plan_table(
        self, tmp_path, monkeypatch, mode, checked, expected
    ):
        paths = bulk_library(tmp_path)
        asked = answer_captions(monkeypatch, RUN_ANSWERS)
        tools, _ = make_tools(tmp_path, list(paths.values()))

        tools.open_run(mode)
        finish_checks(tools)

        assert sorted(KEY_OF[stem] for stem in asked) == sorted(checked)
        assert groups(tools) == expected

    def test_a_song_the_library_has_not_picked_up_is_not_in_the_run(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        answer_captions(monkeypatch, {})
        tools, _ = make_tools(tmp_path, [paths["current"]])

        tools.open_run("all")

        assert [Path(s["song"]).stem for s in tools.run_view()["songs"]] == [STEMS["current"]]

    def test_a_second_run_is_refused_while_one_is_open(self, tmp_path, monkeypatch):
        tools, _, _ = open_run(tmp_path, monkeypatch, "all")

        with pytest.raises(RegenError, match="already open"):
            tools.open_run("reset")

        assert tools.run_view()["mode"] == "all"

    def test_an_unknown_mode_and_an_empty_run_are_refused(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        tools, _ = make_tools(tmp_path, [str(video)])

        with pytest.raises(RegenError, match="Unknown run"):
            tools.open_run("everything")
        with pytest.raises(RegenError, match="no songs"):
            tools.open_run("stale")  # nothing is behind

        assert tools.run_view() is None

    def test_the_view_describes_each_song(self, tmp_path, monkeypatch):
        [video] = make_videos(tmp_path, "Pop Song (Official Video)---aaaaaaaaaaa")
        write_bundle(
            tmp_path,
            video.stem,
            lyrics={"origin": "genius", "genius": GENIUS, "lines": ["one", "two"]},
            output_summary={"line_count": 10, "lines_with_words": 5},
        )
        answer_captions(monkeypatch, {})
        tools, _ = make_tools(tmp_path, [str(video)])
        tools.open_run("all")

        view = tools.run_view()

        [song] = view["songs"]
        assert song == {
            "song": str(video),
            "title": SongManager.filename_from_path(str(video)),
            "group": "reuse",
            "needs_pick": False,
            "now": {"source": "genius", "title": "Song", "artist": "Artist"},
            "query": "Pop Song",
            "poor": True,
            "guessed": 5,
            "line_count": 10,
            "has_youtube_id": True,
            "genius_id": GENIUS["id"],
            "caption": None,
            "pick": None,
        }
        assert view["queueable"] == 1

    def test_where_each_kind_of_song_stands_today_is_reported(self, tmp_path, monkeypatch):
        tools, _, _ = open_run(tmp_path, monkeypatch, "all", RUN_ANSWERS)

        now = {KEY_OF[Path(s["song"]).stem]: s["now"]["source"] for s in tools.run_view()["songs"]}

        assert now == {
            "current": "genius",
            "behind": "genius",
            "unlined": "genius",
            "caption": "captions",
            "transcribed": "transcribed",
            "unprocessed": "unprocessed",
            "no_id": "unprocessed",
        }

    def test_a_check_that_crashes_counts_as_one_that_could_not_run(
        self, tmp_path, monkeypatch, caplog
    ):
        paths = bulk_library(tmp_path)
        monkeypatch.setattr("pikaraoke.lib.library_tools.CAPTION_RETRY_PAUSE_S", 0)
        monkeypatch.setattr(
            "pikaraoke.lib.library_tools.check_caption", MagicMock(side_effect=RuntimeError("x"))
        )
        tools, _ = make_tools(tmp_path, list(paths.values()))

        tools.open_run("reset")
        finish_checks(tools)

        assert set(groups(tools).values()) == {"needs_pick"}
        assert tools.run_view()["failed"] == 6  # every song with a YouTube id
        assert "Caption check of" in caplog.text

    def test_the_view_counts_the_checks_as_they_finish(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        release = hold_captions(monkeypatch)
        tools, _ = make_tools(tmp_path, list(paths.values()))

        tools.open_run("reset")
        waiting = tools.run_view()
        release.set()
        finish_checks(tools)
        done = tools.run_view()

        assert (waiting["checking"], waiting["to_check"], waiting["checked"]) == (True, 6, 0)
        assert (done["checking"], done["to_check"], done["checked"]) == (False, 6, 6)


class OpensRuns:
    """Open a bulk run over a ``library`` fixture and read where its songs landed."""

    def opened(self, tmp_path, monkeypatch, library, mode):
        asked = answer_captions(monkeypatch, {})
        tools, processing = make_tools(tmp_path, library)
        tools.open_run(mode)
        finish_checks(tools)
        return tools, processing, asked

    def group_of(self, tools, stem):
        return next(s["group"] for s in tools.run_view()["songs"] if Path(s["song"]).stem == stem)


class TestRunsReplayCustomSheets(OpensRuns):
    """A custom lyric sheet is replayed by every bulk run, a reset included: it is never
    left for a pick, never asked of YouTube, and its plan is the sheet."""

    MINE, PLAIN, SHEET_ONLY = "A---aaaaaaaaaaa", "B---bbbbbbbbbbb", "C---ccccccccccc"

    @pytest.fixture
    def library(self, tmp_path):
        """A custom song, an ordinary Genius one, and a custom one whose bundle is gone.

        The last has only a karaoke file and its sheet, which alone says it is not a plain
        transcription.
        """
        mine, plain, sheet_only = (
            make_video(tmp_path, s) for s in (self.MINE, self.PLAIN, self.SHEET_ONLY)
        )
        write_bundle(
            tmp_path,
            mine.stem,
            lyrics={"origin": "custom", "lines": ["one", "two"]},
            output_summary={"line_count": 2, "lines_with_words": 2},
        )
        write_sheet(tmp_path, mine.stem)
        genius_bundle(tmp_path, plain.stem)
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{sheet_only.stem}.ass").write_text("", encoding="utf-8")
        write_sheet(tmp_path, sheet_only.stem)
        return [str(mine), str(plain), str(sheet_only)]

    @pytest.mark.parametrize("mode", ["all", "reset"])
    def test_a_custom_song_is_reused_in_every_mode_ahead_of_the_transcribe_rule(
        self, tmp_path, monkeypatch, library, mode
    ):
        tools, _, asked = self.opened(tmp_path, monkeypatch, library, mode)

        assert self.group_of(tools, self.MINE) == "reuse"
        assert self.group_of(tools, self.SHEET_ONLY) == "reuse"  # "all" would transcribe it
        assert self.MINE not in asked and self.SHEET_ONLY not in asked  # no yt-dlp call for them
        assert tools.run_view()["to_pick"] == (0 if mode == "all" else 1)  # only the plain song

    def test_an_update_replays_a_custom_song_that_is_behind(self, tmp_path, monkeypatch, library):
        write_bundle(
            tmp_path,
            self.MINE,
            schema_version=SCHEMA_VERSION - 1,
            lyrics={"origin": "custom", "lines": ["one"]},
        )
        tools, processing, _ = self.opened(tmp_path, monkeypatch, library, "stale")

        assert [Path(s["song"]).stem for s in tools.run_view()["songs"]] == [self.MINE]
        assert self.group_of(tools, self.MINE) == "reuse"

    @pytest.mark.parametrize(("mode", "reset"), [("all", False), ("reset", True)])
    def test_the_queued_job_is_the_custom_plan(self, tmp_path, monkeypatch, library, mode, reset):
        tools, processing, _ = self.opened(tmp_path, monkeypatch, library, mode)
        if self.group_of(tools, self.PLAIN) == "needs_pick":
            tools.save_pick(library[1], {"kind": "skip"})

        tools.queue_run()

        queued = {
            c.args[0].song.song_path.stem: c.args[0]
            for c in processing.enqueue_regen.call_args_list
        }
        for stem in (self.MINE, self.SHEET_ONLY):
            regen = queued[stem]
            assert regen.reset is reset
            assert regen.label == RUN_LABELS[mode]
            plan = regen.song.plan
            assert plan.kind == "seed"
            assert plan.lyrics_path == tmp_path / "lyrics" / f"{stem}.custom.txt"
            assert plan.seed == {"lyrics_origin": "custom"}

    @pytest.mark.parametrize("mode", ["all", "reset"])
    def test_a_sheet_saved_after_the_run_opened_wins_and_is_kept(
        self, tmp_path, monkeypatch, library, mode
    ):
        """The plain song was grouped without a sheet; a custom repair since then wins."""
        tools, processing, _ = self.opened(tmp_path, monkeypatch, library, mode)
        if self.group_of(tools, self.PLAIN) == "needs_pick":
            tools.save_pick(library[1], {"kind": "transcribe"})
        write_sheet(tmp_path, self.PLAIN)

        tools.queue_run()

        [regen] = [
            c.args[0]
            for c in processing.enqueue_regen.call_args_list
            if c.args[0].song.song_path.stem == self.PLAIN
        ]
        assert regen.song.plan.seed == {"lyrics_origin": "custom"}
        assert regen.song.replaces_custom is False

    def test_the_run_says_where_a_custom_song_stands_today(self, tmp_path, monkeypatch, library):
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "reset")

        now = {Path(s["song"]).stem: s["now"] for s in tools.run_view()["songs"]}

        assert now[self.MINE] == now[self.SHEET_ONLY] == {"source": "custom"}

    def test_a_custom_bundle_whose_sheet_is_gone_is_not_custom_now(
        self, tmp_path, monkeypatch, library
    ):
        (tmp_path / "lyrics" / f"{self.MINE}.custom.txt").unlink()
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "reset")

        song = next(s for s in tools.run_view()["songs"] if Path(s["song"]).stem == self.MINE)

        assert song["now"] != {"source": "custom"}
        assert song["group"] != "reuse"

    def test_a_song_with_a_sheet_is_not_one_that_needs_a_pick(self, tmp_path, monkeypatch, library):
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "reset")

        with pytest.raises(RegenError, match="doesn't need a pick"):
            tools.save_pick(library[0], {"kind": "transcribe"})


class TestRunsReplayMovieSheets(OpensRuns):
    """A movie-subtitles sheet is replayed by every bulk run like a typed one: never left
    for a pick, never asked of YouTube, and its plan is the sheet."""

    MINE, SHEET_ONLY, PLAIN = "A---aaaaaaaaaaa", "C---ccccccccccc", "B---bbbbbbbbbbb"

    @pytest.fixture
    def library(self, tmp_path):
        """A movie song, a movie one whose bundle is gone, and an ordinary Genius one."""
        mine, sheet_only, plain = (
            make_video(tmp_path, s) for s in (self.MINE, self.SHEET_ONLY, self.PLAIN)
        )
        write_bundle(
            tmp_path,
            mine.stem,
            lyrics={"origin": "movie_srt", "lines": ["one", "two"]},
            output_summary={"line_count": 2, "lines_with_words": 2},
        )
        write_movie_sheet(tmp_path, mine.stem)
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{sheet_only.stem}.ass").write_text("", encoding="utf-8")
        write_movie_sheet(tmp_path, sheet_only.stem)
        genius_bundle(tmp_path, plain.stem)
        return [str(mine), str(sheet_only), str(plain)]

    @pytest.mark.parametrize("mode", ["all", "reset"])
    def test_a_movie_song_is_reused_in_every_mode_ahead_of_the_transcribe_rule(
        self, tmp_path, monkeypatch, library, mode
    ):
        tools, _, asked = self.opened(tmp_path, monkeypatch, library, mode)

        assert self.group_of(tools, self.MINE) == "reuse"
        assert self.group_of(tools, self.SHEET_ONLY) == "reuse"  # "all" would transcribe it
        assert self.MINE not in asked and self.SHEET_ONLY not in asked  # no yt-dlp call for them

    def test_an_update_replays_a_movie_song_that_is_behind(self, tmp_path, monkeypatch, library):
        write_bundle(
            tmp_path,
            self.MINE,
            schema_version=SCHEMA_VERSION - 1,
            lyrics={"origin": "movie_srt", "lines": ["one"]},
        )
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "stale")

        assert [Path(s["song"]).stem for s in tools.run_view()["songs"]] == [self.MINE]
        assert self.group_of(tools, self.MINE) == "reuse"

    def test_the_run_says_a_movie_song_has_movie_subtitles_today(
        self, tmp_path, monkeypatch, library
    ):
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "reset")

        now = {Path(s["song"]).stem: s["now"] for s in tools.run_view()["songs"]}

        # The sheet on disk says it, with a bundle (MINE) or without one (SHEET_ONLY).
        assert now[self.MINE] == now[self.SHEET_ONLY] == {"source": "movie"}
        assert now[self.PLAIN]["source"] == "genius"

    @pytest.mark.parametrize(("mode", "reset"), [("all", False), ("reset", True)])
    def test_the_queued_job_is_the_movie_plan_and_keeps_the_sheet(
        self, tmp_path, monkeypatch, library, mode, reset
    ):
        tools, processing, _ = self.opened(tmp_path, monkeypatch, library, mode)
        if self.group_of(tools, self.PLAIN) == "needs_pick":
            tools.save_pick(library[2], {"kind": "skip"})

        tools.queue_run()

        queued = {
            c.args[0].song.song_path.stem: c.args[0]
            for c in processing.enqueue_regen.call_args_list
        }
        for stem in (self.MINE, self.SHEET_ONLY):
            regen = queued[stem]
            assert regen.reset is reset
            plan = regen.song.plan
            assert plan.kind == "seed"
            assert plan.lyrics_path == tmp_path / "lyrics" / f"{stem}.custom.srt"
            assert plan.seed == {"lyrics_origin": "movie_srt"}
            assert regen.song.replaces_custom is False

    def test_a_song_with_a_movie_sheet_is_not_one_that_needs_a_pick(
        self, tmp_path, monkeypatch, library
    ):
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "reset")

        with pytest.raises(RegenError, match="doesn't need a pick"):
            tools.save_pick(library[0], {"kind": "transcribe"})


class TestRunsReplayLrcSheets(OpensRuns):
    """An LRCLIB-timing sheet is replayed by every bulk run like the other kinds: never left
    for a pick, never asked of YouTube, and its plan is the sheet."""

    MINE, SHEET_ONLY, PLAIN = "A---aaaaaaaaaaa", "C---ccccccccccc", "B---bbbbbbbbbbb"

    @pytest.fixture
    def library(self, tmp_path):
        """An LRCLIB-timed song, one whose bundle is gone, and an ordinary Genius one."""
        mine, sheet_only, plain = (
            make_video(tmp_path, s) for s in (self.MINE, self.SHEET_ONLY, self.PLAIN)
        )
        write_bundle(
            tmp_path,
            mine.stem,
            lyrics={"origin": "lrclib_srt", "lines": ["one", "two"]},
            output_summary={"line_count": 2, "lines_with_words": 2},
        )
        write_lrc_sheet(tmp_path, mine.stem)
        (tmp_path / "karaoke").mkdir()
        (tmp_path / "karaoke" / f"{sheet_only.stem}.ass").write_text("", encoding="utf-8")
        write_lrc_sheet(tmp_path, sheet_only.stem)
        genius_bundle(tmp_path, plain.stem)
        return [str(mine), str(sheet_only), str(plain)]

    @pytest.mark.parametrize("mode", ["all", "reset"])
    def test_an_lrc_timed_song_is_reused_in_every_mode_ahead_of_the_transcribe_rule(
        self, tmp_path, monkeypatch, library, mode
    ):
        tools, _, asked = self.opened(tmp_path, monkeypatch, library, mode)

        assert self.group_of(tools, self.MINE) == "reuse"
        assert self.group_of(tools, self.SHEET_ONLY) == "reuse"  # "all" would transcribe it
        assert self.MINE not in asked and self.SHEET_ONLY not in asked  # no yt-dlp call for them

    def test_the_run_says_an_lrc_timed_song_is_timed_by_lrclib_today(
        self, tmp_path, monkeypatch, library
    ):
        tools, _, _ = self.opened(tmp_path, monkeypatch, library, "reset")

        now = {Path(s["song"]).stem: s["now"] for s in tools.run_view()["songs"]}

        # The sheet on disk says it, with a bundle (MINE) or without one (SHEET_ONLY).
        assert now[self.MINE] == now[self.SHEET_ONLY] == {"source": "lrc"}
        assert now[self.PLAIN]["source"] == "genius"

    @pytest.mark.parametrize(("mode", "reset"), [("all", False), ("reset", True)])
    def test_the_queued_job_is_the_lrc_plan_and_keeps_the_sheet(
        self, tmp_path, monkeypatch, library, mode, reset
    ):
        tools, processing, _ = self.opened(tmp_path, monkeypatch, library, mode)
        if self.group_of(tools, self.PLAIN) == "needs_pick":
            tools.save_pick(library[2], {"kind": "skip"})

        tools.queue_run()

        queued = {
            c.args[0].song.song_path.stem: c.args[0]
            for c in processing.enqueue_regen.call_args_list
        }
        for stem in (self.MINE, self.SHEET_ONLY):
            regen = queued[stem]
            assert regen.reset is reset
            plan = regen.song.plan
            assert plan.kind == "seed"
            assert plan.lyrics_path == tmp_path / "lyrics" / f"{stem}.lrclib.srt"
            assert plan.seed == {"lyrics_origin": "lrclib_srt"}
            assert regen.song.replaces_custom is False


class TestRunPicks:
    @pytest.fixture
    def run(self, tmp_path, monkeypatch):
        """A reprocess where unlined, unprocessed and no_id need a pick."""
        answers = {"unlined": NO_CAPTION, "unprocessed": SPARSE}
        return open_run(tmp_path, monkeypatch, "all", answers)

    def test_the_songs_that_need_a_pick_are_known_once_the_checks_are_done(self, run):
        tools, _, _ = run

        view = tools.run_view()

        assert [s["needs_pick"] for s in view["songs"]].count(True) == 3
        assert groups(tools)["unlined"] == "needs_pick"
        assert (view["to_pick"], view["picked"]) == (3, 0)

    def test_a_genius_pick_is_trimmed_and_moves_the_song_to_genius(self, run):
        tools, _, paths = run
        pick = {"kind": "genius", "genius_id": 9, "title": " Defying Gravity ", "artist": "x" * 500}

        tools.save_pick(paths["no_id"], pick)

        picked = run_song(tools, "no_id")
        assert picked["group"] == "genius"
        assert picked["needs_pick"]  # still a song the admin decided
        assert picked["pick"] == {
            "kind": "genius",
            "genius_id": 9,
            "title": "Defying Gravity",
            "artist": "x" * 200,
        }
        view = tools.run_view()
        assert (view["to_pick"], view["picked"]) == (3, 1)

    def test_transcribe_and_skip_picks(self, run):
        tools, _, paths = run

        tools.save_pick(paths["no_id"], {"kind": "transcribe"})
        tools.save_pick(paths["unprocessed"], {"kind": "skip"})

        assert groups(tools)["no_id"] == "transcribe"
        assert groups(tools)["unprocessed"] == "skip"
        assert tools.run_view()["queueable"] == 6

    def test_a_pick_can_be_changed(self, run):
        tools, _, paths = run
        tools.save_pick(paths["no_id"], {"kind": "skip"})

        tools.save_pick(paths["no_id"], {"kind": "genius", "genius_id": 3})

        assert run_song(tools, "no_id")["pick"]["genius_id"] == 3
        assert tools.run_view()["picked"] == 1

    def test_keep_replays_the_genius_song_the_bundle_records(self, run):
        tools, _, paths = run

        tools.save_pick(paths["unlined"], {"kind": "keep"})

        assert run_song(tools, "unlined")["pick"] == {"kind": "keep", "genius_id": GENIUS["id"]}
        assert groups(tools)["unlined"] == "genius"

    def test_keep_is_refused_for_a_song_with_no_recorded_genius_song(self, run):
        tools, _, paths = run

        with pytest.raises(RegenError, match="no recorded Genius song"):
            tools.save_pick(paths["no_id"], {"kind": "keep"})

        assert run_song(tools, "no_id")["pick"] is None

    @pytest.mark.parametrize(
        "pick",
        [
            None,
            "skip",
            {"kind": "caption"},
            {"kind": "genius"},
            {"kind": "genius", "genius_id": "7"},
            {"kind": "genius", "genius_id": True},
        ],
    )
    def test_a_pick_that_is_not_one_is_refused(self, run, pick):
        tools, _, paths = run

        with pytest.raises(RegenError):
            tools.save_pick(paths["no_id"], pick)

        assert run_song(tools, "no_id")["pick"] is None

    def test_a_song_that_does_not_need_a_pick_is_refused(self, run):
        tools, _, paths = run

        with pytest.raises(RegenError, match="doesn't need a pick"):
            tools.save_pick(paths["current"], {"kind": "skip"})
        with pytest.raises(RegenError, match="isn't in this run"):
            tools.save_pick("/elsewhere/a.mp4", {"kind": "skip"})

    def test_a_song_still_being_checked_waits(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        release = hold_captions(monkeypatch)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("reset")

        with pytest.raises(RegenError, match="still being checked"):
            tools.save_pick(paths["current"], {"kind": "skip"})

        release.set()
        finish_checks(tools)

    def test_every_call_needs_an_open_run(self, tmp_path):
        tools, _ = make_tools(tmp_path, [])

        for call in (
            lambda: tools.save_pick("a.mp4", {"kind": "skip"}),
            tools.keep_all,
            tools.queue_run,
        ):
            with pytest.raises(RegenError, match="No run is open"):
                call()

    def test_keep_all_keeps_every_unpicked_song_that_can(self, run):
        tools, _, _ = run

        kept = tools.keep_all()

        assert kept == 1  # unlined: the others have no recorded Genius song
        assert run_song(tools, "unlined")["pick"]["kind"] == "keep"
        assert run_song(tools, "no_id")["pick"] is None
        assert tools.keep_all() == 0

    def test_keep_all_leaves_a_pick_the_admin_made(self, run):
        tools, _, paths = run
        tools.save_pick(paths["unlined"], {"kind": "transcribe"})

        assert tools.keep_all() == 0

        assert run_song(tools, "unlined")["pick"] == {"kind": "transcribe"}


class TestRunState:
    def test_picks_and_checks_survive_a_restart(self, tmp_path, monkeypatch):
        answers = {"unlined": NO_CAPTION, "unprocessed": SPARSE}
        tools, _, paths = open_run(tmp_path, monkeypatch, "all", answers)
        tools.save_pick(paths["no_id"], {"kind": "genius", "genius_id": 9, "title": "T"})
        before = tools.run_view()
        monkeypatch.setattr(
            "pikaraoke.lib.library_tools.check_caption", MagicMock(side_effect=AssertionError)
        )

        restarted, _ = make_tools(tmp_path, list(paths.values()))

        assert restarted.run_view() == before
        assert restarted._checker is None  # every check was already made

    def test_a_run_left_mid_check_resumes_its_unchecked_songs(self, tmp_path, monkeypatch):
        _, _, paths = open_run(tmp_path, monkeypatch, "reset", RUN_ANSWERS)
        state_path = tmp_path / "library_tools_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for key in ("unlined", "caption"):
            state["run"]["songs"][paths[key]]["check"] = None
        state_path.write_text(json.dumps(state), encoding="utf-8")
        asked = answer_captions(monkeypatch, RUN_ANSWERS)

        restarted, _ = make_tools(tmp_path, list(paths.values()))
        finish_checks(restarted)

        assert sorted(asked) == sorted([STEMS["unlined"], STEMS["caption"]])
        assert not restarted.run_view()["checking"]
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["run"]["songs"][paths["unlined"]]["check"]["passed"] is True

    def test_a_song_gone_since_drops_out_of_the_run(self, tmp_path, monkeypatch):
        _, _, paths = open_run(tmp_path, monkeypatch, "all")
        Path(paths["no_id"]).unlink()

        restarted, _ = make_tools(tmp_path, list(paths.values()))

        stems = [Path(s["song"]).stem for s in restarted.run_view()["songs"]]
        assert STEMS["no_id"] not in stems and len(stems) == 6

    def test_a_run_over_another_librarys_songs_is_not_restored(self, tmp_path, monkeypatch, caplog):
        old, new = tmp_path / "old", tmp_path / "new"
        old.mkdir()
        new.mkdir()
        _, _, paths = open_run(old, monkeypatch, "all")

        # The same app data, started with another download path.
        restarted, _ = make_tools(new, [], state=old / "library_tools_state.json")

        assert restarted.run_view() is None
        assert f"Dropped {len(paths)} song(s) of the saved run" in caplog.text

    def test_a_run_keeps_only_this_librarys_songs(self, tmp_path, monkeypatch):
        library, other = tmp_path / "library", tmp_path / "other"
        library.mkdir()
        other.mkdir()
        _, _, paths = open_run(library, monkeypatch, "all")
        state_path = library / "library_tools_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        stranger = make_video(other, "Stranger---ggggggggggg")
        state["run"]["songs"][str(stranger)] = {"check": None, "pick": None}
        state_path.write_text(json.dumps(state), encoding="utf-8")

        restarted, _ = make_tools(library, list(paths.values()))

        assert {s["song"] for s in restarted.run_view()["songs"]} == set(paths.values())

    @pytest.mark.parametrize("spelling", ["trailing separator", "dot-dot"])
    def test_the_same_folder_spelled_another_way_keeps_the_run(
        self, tmp_path, monkeypatch, spelling
    ):
        _, _, paths = open_run(tmp_path, monkeypatch, "all")
        folder = (
            str(tmp_path) + os.sep
            if spelling == "trailing separator"
            else os.path.join(str(tmp_path), "sub", "..")
        )
        library = SongList()
        library.update(list(paths.values()))
        song_manager = MagicMock(songs=library, filename_from_path=SongManager.filename_from_path)

        restarted = LibraryTools(
            MagicMock(),
            song_manager,
            folder,
            MagicMock(),
            tmp_path / "library_tools_state.json",
            EventSystem(),
            MagicMock(),
        )

        assert len(restarted.run_view()["songs"]) == len(paths)

    def test_a_pick_the_song_can_no_longer_take_is_dropped(self, tmp_path, monkeypatch):
        tools, _, paths = open_run(tmp_path, monkeypatch, "all", {"unlined": NO_CAPTION})
        tools.save_pick(paths["unlined"], {"kind": "keep"})
        bundle = tmp_path / "alignment_debug" / f"{STEMS['unlined']}.json"
        bundle.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

        restarted, _ = make_tools(tmp_path, list(paths.values()))

        assert run_song(restarted, "unlined")["pick"] is None

    @pytest.mark.parametrize(
        "content",
        [
            "not json",
            "[1, 2]",
            '{"run": 5}',
            '{"run": {"mode": "x", "songs": {}}}',
            '{"run": {"mode": "all", "songs": {}}}',
        ],
    )
    def test_an_unusable_state_file_is_ignored(self, tmp_path, content):
        (tmp_path / "library_tools_state.json").write_text(content, encoding="utf-8")

        tools, _ = make_tools(tmp_path, [])

        assert tools.run_view() is None

    def test_a_write_that_fails_is_logged_and_the_run_goes_on(self, tmp_path, monkeypatch, caplog):
        paths = bulk_library(tmp_path)
        answer_captions(monkeypatch, {})
        (tmp_path / "blocker").write_text("", encoding="utf-8")  # a file where a folder must go
        tools, _ = make_tools(
            tmp_path, list(paths.values()), state=tmp_path / "blocker" / "state.json"
        )

        tools.open_run("all")
        finish_checks(tools)

        assert tools.run_view() is not None
        assert "Could not save the library tools state" in caplog.text

    def test_the_state_is_written_in_one_piece(self, tmp_path, monkeypatch):
        open_run(tmp_path, monkeypatch, "all")

        saved = json.loads((tmp_path / "library_tools_state.json").read_text(encoding="utf-8"))
        assert saved["run"]["mode"] == "all"
        assert not list(tmp_path.glob("*.tmp"))

    def test_discard_closes_the_run_for_good(self, tmp_path, monkeypatch):
        tools, _, paths = open_run(tmp_path, monkeypatch, "all")

        tools.discard_run()
        tools.discard_run()  # nothing open: not an error

        assert tools.run_view() is None
        restarted, _ = make_tools(tmp_path, list(paths.values()))
        assert restarted.run_view() is None

    def test_discard_stops_the_checks_of_the_run_it_closed(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        started, release = threading.Event(), threading.Event()
        calls: list[str] = []

        def check(job):
            calls.append(job.song_path.stem)
            started.set()
            release.wait(10)
            return PASS

        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", check)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("reset")
        old_checks = tools._checker
        assert started.wait(10)

        tools.discard_run()
        tools.open_run("stale")  # a new run, with its own thread
        release.set()
        old_checks.join(10)
        finish_checks(tools)

        # The old run's thread finished the song it was on and asked for no more.
        assert not old_checks.is_alive()
        assert len(calls) == 1 + 1  # that song, then the new run's one song to check (unlined)

    def test_a_run_that_is_no_longer_open_gets_no_more_checks(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        release = hold_captions(monkeypatch)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("reset")
        closed = tools._run
        tools.discard_run()
        release.set()
        finish_checks(tools)
        asked = answer_captions(monkeypatch, {})
        tools.open_run("stale")  # another run is open, with checks of its own
        finish_checks(tools)
        asked.clear()

        tools._check_captions(closed)

        assert asked == []


FAILED = CaptionCheck(found=False, wpm=None, passed=False, failed=True)


def answer_in_turn(monkeypatch, answers: dict[str, list[CaptionCheck]]) -> list[str]:
    """Patch the caption check to give each song its answers in turn (no caption after them).

    Returns the list that fills with the stems asked about, in order.
    """
    left = {STEMS[key]: list(checks) for key, checks in answers.items()}
    asked: list[str] = []

    def check(job):
        stem = job.song_path.stem
        asked.append(stem)
        return left[stem].pop(0) if left.get(stem) else NO_CAPTION

    monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", check)
    return asked


class TestFailedCaptionChecks:
    @pytest.fixture(autouse=True)
    def no_pause(self, monkeypatch):
        monkeypatch.setattr("pikaraoke.lib.library_tools.CAPTION_RETRY_PAUSE_S", 0)

    @staticmethod
    def stale_run(tmp_path, monkeypatch, answers):
        """An update, whose one song to check is ``unlined``; returns (tools, asked, paths)."""
        paths = bulk_library(tmp_path)
        asked = answer_in_turn(monkeypatch, answers)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("stale")
        finish_checks(tools)
        return tools, asked, paths

    def test_a_check_that_could_not_run_is_tried_once_more_then_stored_as_failed(
        self, tmp_path, monkeypatch
    ):
        tools, asked, _ = self.stale_run(tmp_path, monkeypatch, {"unlined": [FAILED, FAILED]})

        assert asked == [STEMS["unlined"]] * 2
        song = run_song(tools, "unlined")
        assert song["group"] == "needs_pick"
        assert song["caption"]["failed"] is True
        view = tools.run_view()
        assert (view["checking"], view["failed"]) == (False, 1)

    def test_a_pass_on_the_second_try_is_stored_as_a_pass(self, tmp_path, monkeypatch):
        tools, asked, _ = self.stale_run(tmp_path, monkeypatch, {"unlined": [FAILED, PASS]})

        assert asked == [STEMS["unlined"]] * 2
        assert run_song(tools, "unlined")["group"] == "caption"
        assert tools.run_view()["failed"] == 0

    def test_a_check_that_found_no_caption_is_not_tried_again(self, tmp_path, monkeypatch):
        tools, asked, _ = self.stale_run(tmp_path, monkeypatch, {"unlined": [NO_CAPTION]})

        assert asked == [STEMS["unlined"]]
        assert run_song(tools, "unlined")["caption"]["failed"] is False
        assert tools.run_view()["failed"] == 0

    def test_a_discard_during_the_pause_ends_the_checks_at_once_and_stores_nothing(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr("pikaraoke.lib.library_tools.CAPTION_RETRY_PAUSE_S", 5)
        paths = bulk_library(tmp_path)
        asked = threading.Event()
        calls: list[str] = []

        def check(job):
            calls.append(job.song_path.stem)
            asked.set()
            return FAILED

        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", check)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("stale")
        checker, run = tools._checker, tools._run
        assert asked.wait(10)

        tools.discard_run()
        checker.join(1)

        assert not checker.is_alive()
        assert calls == [STEMS["unlined"]]
        assert run.entries[paths["unlined"]].check is None

    def test_check_again_clears_only_the_failed_songs_without_a_pick(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        answers = {"current": [FAILED, FAILED], "behind": [FAILED, FAILED], "unlined": [PASS]}
        asked = answer_in_turn(monkeypatch, answers)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("reset")
        finish_checks(tools)
        tools.save_pick(paths["behind"], {"kind": "transcribe"})
        assert tools.run_view()["failed"] == 1
        asked.clear()

        assert tools.recheck_captions() == 1
        finish_checks(tools)

        assert asked == [STEMS["current"]]
        assert run_song(tools, "current")["caption"]["failed"] is False  # no caption this time
        assert run_song(tools, "behind")["caption"]["failed"] is True  # its pick decides it
        assert run_song(tools, "unlined")["group"] == "caption"
        assert tools.run_view()["failed"] == 0

    def test_check_again_is_refused_while_captions_are_being_checked(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        release = hold_captions(monkeypatch)
        tools, _ = make_tools(tmp_path, list(paths.values()))
        tools.open_run("reset")

        with pytest.raises(RegenError, match="still being checked"):
            tools.recheck_captions()

        release.set()
        finish_checks(tools)

    def test_check_again_is_refused_when_no_unpicked_check_failed(self, tmp_path, monkeypatch):
        tools, _, paths = self.stale_run(tmp_path, monkeypatch, {"unlined": [FAILED, FAILED]})
        tools.save_pick(paths["unlined"], {"kind": "skip"})

        with pytest.raises(RegenError, match="No caption check failed"):
            tools.recheck_captions()

        assert run_song(tools, "unlined")["caption"]["failed"] is True

    def test_a_failed_check_survives_a_restart_and_can_be_checked_again(
        self, tmp_path, monkeypatch
    ):
        _, asked, paths = self.stale_run(tmp_path, monkeypatch, {"unlined": [FAILED, FAILED, PASS]})

        restarted, _ = make_tools(tmp_path, list(paths.values()))

        assert restarted._checker is None  # a failed check is a finished one
        assert restarted.run_view()["failed"] == 1
        assert restarted.recheck_captions() == 1
        finish_checks(restarted)
        assert run_song(restarted, "unlined")["group"] == "caption"
        assert len(asked) == 3

    def test_a_check_saved_before_failures_were_recorded_reads_as_finished(
        self, tmp_path, monkeypatch
    ):
        _, _, paths = self.stale_run(tmp_path, monkeypatch, {"unlined": [NO_CAPTION]})
        state_path = tmp_path / "library_tools_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        del state["run"]["songs"][paths["unlined"]]["check"]["failed"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        restarted, _ = make_tools(tmp_path, list(paths.values()))

        assert run_song(restarted, "unlined")["group"] == "needs_pick"
        assert restarted.run_view()["failed"] == 0
        with pytest.raises(RegenError, match="No caption check failed"):
            restarted.recheck_captions()


class TestQueueRun:
    @staticmethod
    def jobs(processing) -> dict[str, RegenJob]:
        return {
            Path(call.args[0].song.song_path).stem: call.args[0]
            for call in processing.enqueue_regen.call_args_list
        }

    def test_it_waits_for_the_captions(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        release = hold_captions(monkeypatch)
        tools, processing = make_tools(tmp_path, list(paths.values()))
        tools.open_run("reset")

        with pytest.raises(RegenError, match="still being checked"):
            tools.queue_run()

        release.set()
        finish_checks(tools)
        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        assert tools.run_view() is not None

    def test_it_refuses_while_a_song_still_needs_a_pick(self, tmp_path, monkeypatch):
        tools, processing, paths = open_run(tmp_path, monkeypatch, "all", RUN_ANSWERS)
        tools.save_pick(paths["no_id"], {"kind": "skip"})  # unprocessed still needs one

        with pytest.raises(RegenError, match="Pick lyrics"):
            tools.queue_run()

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))

    def test_a_reprocess_queues_each_songs_plan_without_a_reset(self, tmp_path, monkeypatch):
        tools, processing, paths = open_run(tmp_path, monkeypatch, "all", RUN_ANSWERS)
        tools.save_pick(paths["unprocessed"], {"kind": "genius", "genius_id": 9})
        tools.save_pick(paths["no_id"], {"kind": "skip"})

        result = tools.queue_run()

        jobs = self.jobs(processing)
        assert set(jobs) == {stem for key, stem in STEMS.items() if key != "no_id"}
        assert {job.reset for job in jobs.values()} == {False}
        assert {job.label for job in jobs.values()} == {"Reprocess"}
        plans = {KEY_OF[stem]: job.song.plan for stem, job in jobs.items()}
        assert {key: plan.kind for key, plan in plans.items()} == {
            "current": "seed",
            "behind": "seed",
            "unlined": "fetch",  # its caption passed
            "caption": "seed",
            "transcribed": "transcribe",
            "unprocessed": "sidecar",
        }
        assert plans["unprocessed"].genius_id == 9
        assert plans["current"].seed["genius"] == GENIUS
        assert (result["queued"], result["busy"]) == (6, 0)

    def test_a_reset_queues_a_wiping_job_per_song(self, tmp_path, monkeypatch):
        tools, processing, paths = open_run(tmp_path, monkeypatch, "reset", RUN_ANSWERS)
        tools.save_pick(paths["behind"], {"kind": "keep"})
        tools.save_pick(paths["transcribed"], {"kind": "transcribe"})
        tools.save_pick(paths["unprocessed"], {"kind": "genius", "genius_id": 4})
        tools.save_pick(paths["no_id"], {"kind": "genius", "genius_id": 5})

        tools.queue_run()

        jobs = self.jobs(processing)
        assert len(jobs) == 7
        assert {job.reset for job in jobs.values()} == {True}
        assert {job.label for job in jobs.values()} == {"Reset"}
        kinds = {KEY_OF[stem]: job.song.plan.kind for stem, job in jobs.items()}
        assert kinds == {
            "current": "fetch",
            "behind": "sidecar",
            "unlined": "fetch",
            "caption": "fetch",
            "transcribed": "transcribe",
            "unprocessed": "sidecar",
            "no_id": "sidecar",
        }
        assert jobs[STEMS["behind"]].song.plan.genius_id == GENIUS["id"]
        assert jobs[STEMS["no_id"]].song.plan.genius_id == 5

    def test_an_update_labels_its_jobs_and_leaves_current_songs_out(self, tmp_path, monkeypatch):
        tools, processing, _ = open_run(tmp_path, monkeypatch, "stale", RUN_ANSWERS)

        result = tools.queue_run()

        jobs = self.jobs(processing)
        assert set(jobs) == {STEMS["behind"], STEMS["unlined"]}
        assert {job.label for job in jobs.values()} == {"Update"}
        assert {job.reset for job in jobs.values()} == {False}
        assert result["queued"] == 2

    def test_one_backup_of_the_whole_library_comes_first(self, tmp_path, monkeypatch):
        tools, processing, _ = open_run(tmp_path, monkeypatch, "stale", RUN_ANSWERS)
        backups_at_enqueue = []
        processing.enqueue_regen.side_effect = lambda regen: (
            backups_at_enqueue.append(len(list(tmp_path.glob("regen_backups/*")))) or True
        )

        result = tools.queue_run()

        [backup] = tmp_path.glob("regen_backups/*")
        assert result["backup"] == backup.name
        assert backups_at_enqueue == [1, 1]  # there before the first job was queued
        saved = sorted(p.name for p in (backup / "alignment_debug").iterdir())
        bundled = ("current", "behind", "unlined", "caption")
        assert saved == sorted(f"{STEMS[key]}.json" for key in bundled)

    def test_skipped_songs_are_dropped(self, tmp_path, monkeypatch):
        tools, processing, paths = open_run(tmp_path, monkeypatch, "all", RUN_ANSWERS)
        tools.save_pick(paths["unprocessed"], {"kind": "skip"})
        tools.save_pick(paths["no_id"], {"kind": "genius", "genius_id": 2})

        result = tools.queue_run()

        assert STEMS["unprocessed"] not in self.jobs(processing)
        assert result["queued"] == 6

    def test_busy_songs_are_set_aside_and_counted(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        answer_captions(monkeypatch, RUN_ANSWERS)
        tools, processing = make_tools(
            tmp_path, list(paths.values()), active=paths["behind"], pending=[paths["unlined"]]
        )
        tools.open_run("all")
        finish_checks(tools)
        tools.save_pick(paths["unprocessed"], {"kind": "skip"})
        tools.save_pick(paths["no_id"], {"kind": "skip"})

        result = tools.queue_run()

        assert (result["queued"], result["busy"]) == (3, 2)
        assert set(self.jobs(processing)) == {
            STEMS["current"],
            STEMS["caption"],
            STEMS["transcribed"],
        }

    def test_a_run_of_busy_songs_queues_nothing_and_stays_open(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        answer_captions(monkeypatch, RUN_ANSWERS)
        tools, processing = make_tools(
            tmp_path, list(paths.values()), active=paths["behind"], pending=[paths["unlined"]]
        )
        tools.open_run("stale")  # exactly those two
        finish_checks(tools)

        with pytest.raises(RegenError, match="Nothing to queue"):
            tools.queue_run()

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        assert tools.run_view() is not None

    def test_a_run_of_skipped_songs_queues_nothing_and_stays_open(self, tmp_path, monkeypatch):
        paths = bulk_library(tmp_path)
        answer_captions(monkeypatch, {})  # unlined: no caption, so it needs a pick
        tools, processing = make_tools(tmp_path, [paths["unlined"]])
        tools.open_run("stale")
        finish_checks(tools)
        tools.save_pick(paths["unlined"], {"kind": "skip"})

        with pytest.raises(RegenError, match="Nothing to queue"):
            tools.queue_run()

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        assert tools.run_view() is not None

    def test_a_song_the_queue_turns_away_is_counted_busy(self, tmp_path, monkeypatch):
        tools, processing, _ = open_run(tmp_path, monkeypatch, "stale", RUN_ANSWERS)
        processing.enqueue_regen.side_effect = [True, False]

        result = tools.queue_run()

        assert (result["queued"], result["busy"]) == (1, 1)

    def test_queueing_closes_the_run(self, tmp_path, monkeypatch):
        tools, _, paths = open_run(tmp_path, monkeypatch, "stale", RUN_ANSWERS)

        tools.queue_run()

        assert tools.run_view() is None
        restarted, _ = make_tools(tmp_path, list(paths.values()))
        assert restarted.run_view() is None
        with pytest.raises(RegenError, match="No run is open"):
            tools.queue_run()

    def test_a_failed_backup_queues_nothing_and_keeps_the_run(self, tmp_path, monkeypatch):
        tools, processing, _ = open_run(tmp_path, monkeypatch, "stale", RUN_ANSWERS)

        def disk_full(folder):
            raise OSError("disk full")

        monkeypatch.setattr("pikaraoke.lib.library_tools.backup_text_folders", disk_full)

        with pytest.raises(RegenError, match="Could not back up"):
            tools.queue_run()

        processing.enqueue_regen.assert_not_called()
        assert tools.run_view() is not None

    def test_a_song_that_lost_its_lyrics_since_the_preview_is_refused_before_the_backup(
        self, tmp_path, monkeypatch
    ):
        tools, processing, _ = open_run(tmp_path, monkeypatch, "stale", RUN_ANSWERS)
        (tmp_path / "alignment_debug" / f"{STEMS['behind']}.json").unlink()

        with pytest.raises(RegenError, match="no longer has lyrics to reuse"):
            tools.queue_run()

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backups/*"))
        assert tools.run_view() is not None


# ---------------------------------------------------------------------------
# After a download: the caption check and the needs-a-pick list
# ---------------------------------------------------------------------------

VIDEO_ID = "dQw4w9WgXcQ"
STEM = f"Song---{VIDEO_ID}"


def write_caption(folder: Path, stem: str, words: int) -> Path:
    subs = folder / "subtitles"
    subs.mkdir(exist_ok=True)
    caption = subs / f"{stem}.srt"
    caption.write_text(
        f"1\n00:00:01,000 --> 00:00:04,000\n{' '.join(['la'] * words)}\n", encoding="utf-8"
    )
    return caption


@pytest.fixture
def download(tmp_path, monkeypatch):
    """A fresh download in a library of its own, with the app's real temp folder and ffprobe
    kept out of it (the song is 60 s long). A song handed to ``enqueue`` waits in
    ``pending_jobs``, as it does in the processing manager."""
    monkeypatch.setattr("pikaraoke.lib.genius.get_temp_directory", lambda *a: str(tmp_path / "tmp"))
    monkeypatch.setattr("pikaraoke.lib.library_regen.probe_duration", lambda path: 60.0)
    folder = tmp_path / "library"
    folder.mkdir()
    video = make_video(folder, STEM)
    tools, processing = make_tools(folder, [str(video)])
    processing.enqueue.side_effect = lambda path: processing.pending_jobs.append(path)
    needs_pick = []
    tools._events.on("needs_pick", needs_pick.append)
    return SimpleNamespace(
        tools=tools, processing=processing, folder=folder, song=str(video), events=needs_pick
    )


def listed(tools: LibraryTools) -> list[dict]:
    """The needs-a-pick rows the Attention list would show."""
    return [r for r in tools.attention_rows(set()) if r["state"] == "needs_pick"]


class TestIsWaitingForPick:
    def test_a_listed_song_waits_until_it_is_picked(self, download):
        download.tools.on_song_downloaded(download.song)
        assert download.tools.is_waiting_for_pick(download.song) is True

        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        # still listed, as picked, while its job waits: that is processing
        assert download.tools.is_waiting_for_pick(download.song) is False
        assert download.tools.is_busy(download.song)

    def test_a_song_that_is_not_listed_is_not_waiting(self, download):
        assert download.tools.is_waiting_for_pick(download.song) is False


class TestAfterDownloadCheck:
    @pytest.mark.parametrize("choice", [{"genius_id": 7}, {"mode": "raw"}])
    def test_a_song_the_picker_chose_lyrics_for_is_queued(self, download, choice):
        write_choice(VIDEO_ID, choice)

        download.tools.on_song_downloaded(download.song)

        download.processing.enqueue.assert_called_once_with(download.song)
        assert listed(download.tools) == []

    def test_a_picker_caption_choice_that_passes_the_gate_is_queued(self, download):
        write_choice(VIDEO_ID, {"mode": "srt"})
        write_caption(download.folder, STEM, words=60)

        download.tools.on_song_downloaded(download.song)

        download.processing.enqueue.assert_called_once_with(download.song)
        assert listed(download.tools) == []

    def test_a_picker_caption_choice_still_gets_the_length_gate(self, download):
        write_choice(VIDEO_ID, {"mode": "srt"})
        caption = write_caption(download.folder, STEM, words=3)

        download.tools.on_song_downloaded(download.song)

        assert not caption.exists()
        download.processing.enqueue.assert_not_called()
        [row] = listed(download.tools)
        assert row["reason"] == "sparse_caption"

    def test_a_caption_that_passes_the_length_gate_is_queued(self, download):
        write_caption(download.folder, STEM, words=60)  # 60 words per minute

        download.tools.on_song_downloaded(download.song)

        download.processing.enqueue.assert_called_once_with(download.song)
        assert listed(download.tools) == []

    def test_a_sparse_caption_is_deleted_and_the_song_listed(self, download):
        caption = write_caption(download.folder, STEM, words=3)

        download.tools.on_song_downloaded(download.song)

        assert not caption.exists()
        download.processing.enqueue.assert_not_called()
        [row] = listed(download.tools)
        assert (row["song_path"], row["reason"], row["source"]) == (
            download.song,
            "sparse_caption",
            "download",
        )
        assert download.events == [download.song]

    def test_a_song_with_no_caption_is_listed(self, download):
        download.tools.on_song_downloaded(download.song)

        download.processing.enqueue.assert_not_called()
        [row] = listed(download.tools)
        assert row["reason"] == "no_caption"
        assert download.events == [download.song]

    def test_a_blocked_title_is_queued_for_the_queue_to_skip(self, download):
        download.processing.is_blocked.return_value = True

        download.tools.on_song_downloaded(download.song)

        download.processing.enqueue.assert_called_once_with(download.song)
        assert listed(download.tools) == []

    def test_a_song_with_no_youtube_id_is_queued_as_before(self, download):
        plain = make_video(download.folder, "Plain Song")

        download.tools.on_song_downloaded(str(plain))

        download.processing.enqueue.assert_called_once_with(str(plain))
        assert listed(download.tools) == []

    @pytest.mark.parametrize("error", [OSError("locked"), RuntimeError("boom")])
    def test_a_check_that_fails_queues_the_song_as_before_and_later_handlers_still_run(
        self, download, monkeypatch, caplog, error
    ):
        def fail(job):
            raise error

        monkeypatch.setattr("pikaraoke.lib.library_tools.gate_on_disk_caption", fail)
        write_caption(download.folder, STEM, words=3)
        later = []
        events = download.tools._events
        events.on("song_downloaded", download.tools.on_song_downloaded)
        events.on("song_downloaded", later.append)

        events.emit("song_downloaded", download.song)

        download.processing.enqueue.assert_called_once_with(download.song)
        assert listed(download.tools) == []
        assert later == [download.song]
        assert f"Lyrics check of {Path(download.song).name} failed" in caplog.text

    def test_a_caption_that_cannot_be_read_does_not_stop_the_download(self, download):
        caption = download.folder / "subtitles" / f"{STEM}.srt"
        caption.parent.mkdir()
        caption.write_bytes("1\n00:00:01,000 --> 00:00:04,000\ncafé la la\n".encode("latin-1"))

        download.tools.on_song_downloaded(download.song)

        download.processing.enqueue.assert_called_once_with(download.song)
        assert listed(download.tools) == []
        assert caption.exists()  # it may be the admin's own file

    def test_a_listed_song_is_not_called_unfinished(self, download):
        download.tools._song_manager.get_paths_by_pipeline_state.side_effect = lambda wanted: (
            [download.song] if "pending" in wanted else []
        )
        download.tools.on_song_downloaded(download.song)

        rows = download.tools.attention_rows(set())

        assert [r["state"] for r in rows] == ["needs_pick"]
        assert rows[0]["title"] == "Song"
        assert rows[0]["actions"] == ["pick", "song_info", "delete"]

    def test_a_song_with_a_tracker_row_or_a_queued_job_is_left_to_that_row(self, download):
        download.tools.on_song_downloaded(download.song)

        assert download.tools.attention_rows({download.song}) == []
        download.processing.pending_jobs = [download.song]
        assert download.tools.attention_rows(set()) == []

    def test_the_oldest_listed_song_comes_first(self, download, monkeypatch):
        second = make_video(download.folder, "Second---aaaaaaaaaaa")
        download.tools._song_manager.songs.update([str(second)])
        times = iter([200.0, 100.0])
        monkeypatch.setattr(
            "pikaraoke.lib.library_tools.time", SimpleNamespace(time=lambda: next(times))
        )
        download.tools.on_song_downloaded(download.song)
        download.tools.on_song_downloaded(str(second))

        assert [r["song_path"] for r in listed(download.tools)] == [str(second), download.song]


class TestPlaylistSource:
    def test_a_song_queued_from_a_playlist_is_listed_as_one(self, download):
        download.tools.add_playlist([{"id": "aaaaaaaaaaa", "title": "From the list"}], [])
        arrived = make_video(download.folder, "From the list---aaaaaaaaaaa")

        download.tools.on_song_downloaded(str(arrived))
        download.tools.on_song_downloaded(download.song)

        sources = {r["song_path"]: r["source"] for r in listed(download.tools)}
        assert sources == {str(arrived): "playlist", download.song: "download"}

    def test_the_playlist_mark_is_used_up_by_the_first_download(self, download):
        download.tools.add_playlist([{"id": "aaaaaaaaaaa", "title": "From the list"}], [])
        arrived = str(make_video(download.folder, "From the list---aaaaaaaaaaa"))
        download.tools.on_song_downloaded(arrived)
        download.tools._forget_needs_pick(arrived)

        download.tools.on_song_downloaded(arrived)

        assert [r["source"] for r in listed(download.tools)] == ["download"]


class TestPickLyrics:
    def test_a_genius_pick_writes_the_choice_file_and_queues_the_song(self, download):
        download.tools.on_song_downloaded(download.song)

        download.tools.pick_lyrics(download.song, {"kind": "genius", "genius_id": 42})

        assert read_choice(VIDEO_ID) == {"genius_id": 42, "yt_id": VIDEO_ID}
        download.processing.enqueue.assert_called_once_with(download.song)

    def test_transcribing_writes_the_raw_choice(self, download):
        download.tools.on_song_downloaded(download.song)

        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        assert read_choice(VIDEO_ID) == {"mode": "raw", "yt_id": VIDEO_ID}
        download.processing.enqueue.assert_called_once_with(download.song)

    def test_a_picked_song_stays_listed_as_picked(self, download):
        download.tools.on_song_downloaded(download.song)

        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        view = download.tools.needs_pick_view()
        assert (view["to_pick"], view["picked"]) == (1, 1)
        assert view["songs"][0]["pick"] is not None

    def test_a_second_pick_is_refused(self, download):
        download.tools.on_song_downloaded(download.song)
        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        with pytest.raises(RegenError, match="already waiting or processing"):
            download.tools.pick_lyrics(download.song, {"kind": "genius", "genius_id": 5})

        download.processing.enqueue.assert_called_once()

    @pytest.mark.parametrize("busy", ["waiting", "running"])
    def test_a_song_busy_for_any_reason_shows_as_picked_and_is_not_queued_again(
        self, download, busy
    ):
        download.tools.on_song_downloaded(download.song)
        # A Retry on its Jobs row, or a regen, queued it without this list's pick.
        if busy == "waiting":
            download.processing.pending_jobs = [download.song]
        else:
            download.processing.get_active_job.return_value = download.song

        view = download.tools.needs_pick_view()
        assert (view["to_pick"], view["picked"]) == (1, 1)
        with pytest.raises(RegenError, match="already waiting or processing"):
            download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        download.processing.enqueue.assert_not_called()
        assert read_choice(VIDEO_ID) is None

    def test_a_second_pick_while_the_first_is_being_saved_is_refused(self, download, monkeypatch):
        download.tools.on_song_downloaded(download.song)
        write = write_choice
        inner = []

        def write_then_pick_again(yt_id, payload):
            with pytest.raises(RegenError, match="already waiting or processing") as raised:
                download.tools.pick_lyrics(download.song, {"kind": "genius", "genius_id": 5})
            inner.append(raised.value)
            return write(yt_id, payload)

        monkeypatch.setattr("pikaraoke.lib.library_tools.write_choice", write_then_pick_again)

        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        assert len(inner) == 1
        download.processing.enqueue.assert_called_once_with(download.song)
        assert read_choice(VIDEO_ID) == {"mode": "raw", "yt_id": VIDEO_ID}

    def test_a_song_that_is_not_listed_is_refused(self, download):
        with pytest.raises(RegenError, match="isn't waiting for a pick"):
            download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        download.processing.enqueue.assert_not_called()

    @pytest.mark.parametrize(
        "pick",
        [
            None,
            "transcribe",
            {"kind": "skip"},
            {"kind": "keep"},
            {"kind": "genius"},
            {"kind": "genius", "genius_id": "7"},
            {"kind": "genius", "genius_id": True},
        ],
    )
    def test_a_pick_that_is_not_a_genius_song_or_transcribe_changes_nothing(self, download, pick):
        download.tools.on_song_downloaded(download.song)

        with pytest.raises(RegenError):
            download.tools.pick_lyrics(download.song, pick)

        assert read_choice(VIDEO_ID) is None
        download.processing.enqueue.assert_not_called()
        assert download.tools.needs_pick_view()["picked"] == 0

    def test_a_choice_file_that_cannot_be_written_leaves_the_song_to_pick_again(
        self, download, monkeypatch
    ):
        download.tools.on_song_downloaded(download.song)
        write = write_choice
        writes = []

        def disk_full_once(yt_id, payload):
            writes.append(yt_id)
            if len(writes) == 1:
                raise OSError("disk full")
            return write(yt_id, payload)

        monkeypatch.setattr("pikaraoke.lib.library_tools.write_choice", disk_full_once)
        with pytest.raises(RegenError, match="Could not save that pick"):
            download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        download.processing.enqueue.assert_not_called()
        assert download.tools.needs_pick_view()["picked"] == 0
        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})
        download.processing.enqueue.assert_called_once_with(download.song)

    def test_a_queue_that_fails_leaves_the_song_to_pick_again(self, download):
        download.tools.on_song_downloaded(download.song)
        download.processing.enqueue.side_effect = RuntimeError("queue closed")

        with pytest.raises(RuntimeError):
            download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        assert download.tools.needs_pick_view()["picked"] == 0


class TestWhenAListedSongLeaves:
    def test_finishing_processing_drops_the_song(self, download):
        download.tools.on_song_downloaded(download.song)
        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        download.tools._events.emit("processing_complete", {"song_path": download.song})

        assert download.tools.needs_pick_view()["songs"] == []

    def test_deleting_the_song_drops_it(self, download):
        download.tools.on_song_downloaded(download.song)

        download.tools._events.emit("song_deleted", download.song)

        assert download.tools.needs_pick_view()["songs"] == []

    def test_a_job_that_fails_offers_the_pick_again(self, download):
        download.tools.on_song_downloaded(download.song)
        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        # It failed before the lyrics stage, so its choice file is still there.
        download.processing.pending_jobs.remove(download.song)  # the job ran, and failed
        download.tools._events.emit(
            "processing_error", {"song_path": download.song, "error": "boom"}
        )

        assert download.tools.needs_pick_view()["picked"] == 0
        download.tools.pick_lyrics(download.song, {"kind": "genius", "genius_id": 5})
        assert read_choice(VIDEO_ID) == {"genius_id": 5, "yt_id": VIDEO_ID}

    def test_a_job_cancelled_while_it_waits_offers_the_pick_again(self, download):
        download.tools.on_song_downloaded(download.song)
        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        # Cancelling a waiting job emits no event, and its choice file stays.
        download.processing.pending_jobs.remove(download.song)

        view = download.tools.needs_pick_view()
        assert (view["to_pick"], view["picked"]) == (1, 0)
        assert view["songs"][0]["pick"] is None
        download.tools.pick_lyrics(download.song, {"kind": "genius", "genius_id": 5})
        assert read_choice(VIDEO_ID) == {"genius_id": 5, "yt_id": VIDEO_ID}
        assert download.processing.enqueue.call_count == 2

    def test_a_pick_for_a_title_blocked_since_it_was_listed_takes_the_song_off_the_list(
        self, download
    ):
        download.tools.on_song_downloaded(download.song)
        # The queue skips a blocked title and says so; nothing will run for the pick.
        download.processing.enqueue.side_effect = lambda path: download.tools._events.emit(
            "processing_skipped", path
        )

        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        assert download.tools.needs_pick_view()["songs"] == []
        assert listed(download.tools) == []
        saved = json.loads(download.tools._state_path.read_text(encoding="utf-8"))
        assert saved["needs_pick"] == []
        with pytest.raises(RegenError, match="isn't waiting for a pick"):
            download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

    def test_a_job_for_another_song_changes_nothing(self, download):
        download.tools.on_song_downloaded(download.song)

        download.tools._events.emit("processing_complete", {"song_path": "/elsewhere/x.mp4"})
        download.tools._events.emit("processing_error", {"song_path": "/elsewhere/x.mp4"})
        download.tools._events.emit("song_deleted", "/elsewhere/x.mp4")
        download.tools._events.emit("processing_skipped", "/elsewhere/x.mp4")

        assert len(download.tools.needs_pick_view()["songs"]) == 1


def saved_entry(song: str, changes: dict) -> dict:
    """A needs-a-pick entry as the state file holds it, with ``changes`` made to it."""
    return {"song": song, "reason": "no_caption", "source": "download", "added_at": 1.0} | changes


class TestNeedsPickAcrossARestart:
    @staticmethod
    def restart(download):
        return make_tools(download.folder, list(download.tools._song_manager.songs))[0]

    def test_a_listed_song_is_listed_again(self, download):
        download.tools.on_song_downloaded(download.song)

        [row] = listed(self.restart(download))

        assert (row["song_path"], row["reason"], row["source"]) == (
            download.song,
            "no_caption",
            "download",
        )

    def test_a_pick_is_not_remembered_because_its_choice_file_is_not(self, download):
        download.tools.on_song_downloaded(download.song)
        download.tools.pick_lyrics(download.song, {"kind": "transcribe"})

        assert self.restart(download).needs_pick_view()["picked"] == 0

    def test_a_song_whose_file_is_gone_is_dropped(self, download):
        download.tools.on_song_downloaded(download.song)
        Path(download.song).unlink()

        assert self.restart(download).needs_pick_view()["songs"] == []

    def test_a_song_of_another_library_is_dropped(self, download, tmp_path):
        download.tools.on_song_downloaded(download.song)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        restarted, _ = make_tools(elsewhere, [], state=download.folder / "library_tools_state.json")

        assert restarted.needs_pick_view()["songs"] == []

    def test_a_run_and_the_list_share_the_state_file(self, download, monkeypatch):
        download.tools.on_song_downloaded(download.song)
        monkeypatch.setattr("pikaraoke.lib.library_tools.check_caption", lambda job: NO_CAPTION)
        download.tools.open_run("all")
        finish_checks(download.tools)

        restarted = self.restart(download)

        assert restarted.run_view() is not None
        assert len(restarted.needs_pick_view()["songs"]) == 1

    @pytest.mark.parametrize(
        "changes",
        [
            {"song": 5},
            {"song": "/no/such/song---aaaaaaaaaaa.mp4"},
            {"reason": "other"},
            {"source": "other"},
            {"added_at": "yesterday"},
        ],
    )
    def test_an_unusable_entry_is_ignored(self, download, changes):
        state = {"needs_pick": [saved_entry(download.song, changes)]}
        (download.folder / "library_tools_state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        assert self.restart(download).needs_pick_view()["songs"] == []

    @pytest.mark.parametrize("needs_pick", ["not a list", [5], [None]])
    def test_a_list_that_is_not_entries_is_ignored(self, download, needs_pick):
        state = {"needs_pick": needs_pick}
        (download.folder / "library_tools_state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )

        assert self.restart(download).needs_pick_view()["songs"] == []


class TestNeedsPickView:
    def test_each_song_is_shaped_for_the_pick_page(self, download):
        download.tools.on_song_downloaded(download.song)

        view = download.tools.needs_pick_view()

        assert (view["to_pick"], view["picked"]) == (1, 0)
        assert view["songs"] == [
            {
                "song": download.song,
                "title": "Song",
                "needs_pick": True,
                "now": {"source": "download", "reason": "no_caption"},
                "query": "Song",
                "poor": False,
                "genius_id": None,
                "caption": None,
                "pick": None,
            }
        ]


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLabc"


def playlist_of(*videos: tuple[str, str], title: str = "A playlist") -> Playlist:
    return Playlist(title=title, videos=[PlaylistVideo(id=i, title=t) for i, t in videos])


# What a video from a playlist that gave no channel or length carries.
NO_DETAILS = {"channel": "", "duration": None}


def read_as(monkeypatch, playlist: Playlist) -> list[str]:
    """Make the playlist box read ``playlist``; returns the links it was asked for."""
    asked = []

    def read(url):
        asked.append(url)
        return playlist

    monkeypatch.setattr("pikaraoke.lib.library_tools.read_playlist", read)
    return asked


class TestCheckPlaylist:
    def test_each_video_is_new_unprocessed_or_in_the_library(self, tmp_path, monkeypatch):
        unprocessed = make_video(tmp_path, "Old---bbbbbbbbbbb")
        processed = make_video(tmp_path, "Done---ccccccccccc")
        genius_bundle(tmp_path, processed.stem)
        tools, _ = make_tools(tmp_path, [str(unprocessed), str(processed)])
        asked = read_as(
            monkeypatch,
            playlist_of(("aaaaaaaaaaa", "Fresh"), ("bbbbbbbbbbb", "Old"), ("ccccccccccc", "Done")),
        )

        result = tools.check_playlist(f"  {PLAYLIST_URL} ")

        assert asked == [PLAYLIST_URL]
        assert result["title"] == "A playlist"
        assert result["videos"] == [
            {**NO_DETAILS, "id": "aaaaaaaaaaa", "title": "Fresh", "status": "new", "song": None},
            {
                **NO_DETAILS,
                "id": "bbbbbbbbbbb",
                "title": "Old",
                "status": "not_processed",
                "song": str(unprocessed),
            },
            {
                **NO_DETAILS,
                "id": "ccccccccccc",
                "title": "Done",
                "status": "in_library",
                "song": None,
            },
        ]
        assert result["groups"] == []

    def test_a_video_carries_the_channel_and_length_the_playlist_gave(self, tmp_path, monkeypatch):
        tools, _ = make_tools(tmp_path, [])
        read_as(
            monkeypatch,
            Playlist(
                "P",
                [
                    PlaylistVideo("aaaaaaaaaaa", "Given", channel="Some Channel", duration=213),
                    PlaylistVideo("bbbbbbbbbbb", "Not given"),
                ],
            ),
        )

        given, not_given = tools.check_playlist(PLAYLIST_URL)["videos"]

        assert (given["channel"], given["duration"]) == ("Some Channel", 213)
        assert (not_given["channel"], not_given["duration"]) == ("", None)

    def test_an_unprocessed_video_the_library_has_not_picked_up_counts_as_in_the_library(
        self, tmp_path, monkeypatch
    ):
        make_video(tmp_path, "Old---bbbbbbbbbbb")
        tools, _ = make_tools(tmp_path, [])
        read_as(monkeypatch, playlist_of(("bbbbbbbbbbb", "Old")))

        [video] = tools.check_playlist(PLAYLIST_URL)["videos"]

        assert video["status"] == "in_library"

    def test_a_song_already_queued_or_listed_is_waiting_not_unprocessed(
        self, download, monkeypatch
    ):
        busy = make_video(download.folder, "Busy---bbbbbbbbbbb")
        idle = make_video(download.folder, "Idle---ccccccccccc")
        download.tools._song_manager.songs.update([download.song, str(busy), str(idle)])
        download.processing.pending_jobs = [str(busy)]
        download.tools.on_song_downloaded(download.song)  # no caption: listed for a pick
        read_as(
            monkeypatch,
            playlist_of(("bbbbbbbbbbb", "Busy"), (VIDEO_ID, "Listed"), ("ccccccccccc", "Idle")),
        )

        videos = download.tools.check_playlist(PLAYLIST_URL)["videos"]

        assert [(v["title"], v["status"], v["song"]) for v in videos] == [
            ("Busy", "waiting", None),
            ("Listed", "waiting", None),
            ("Idle", "not_processed", str(idle)),
        ]

    def test_a_video_still_downloading_is_waiting_not_new(self, tmp_path, monkeypatch):
        tools, _ = make_tools(tmp_path, [])
        tools._download_manager.pending_downloads = [
            {"video_url": "https://www.youtube.com/watch?v=bbbbbbbbbbb"}
        ]
        tools._download_manager.active_url = "https://www.youtube.com/watch?v=ccccccccccc"
        read_as(
            monkeypatch,
            playlist_of(
                ("aaaaaaaaaaa", "Fresh"), ("bbbbbbbbbbb", "Queued"), ("ccccccccccc", "Now")
            ),
        )

        videos = tools.check_playlist(PLAYLIST_URL)["videos"]

        assert [(v["title"], v["status"], v["song"]) for v in videos] == [
            ("Fresh", "new", None),
            ("Queued", "waiting", None),
            ("Now", "waiting", None),
        ]

    def test_a_video_listed_twice_is_listed_once(self, tmp_path, monkeypatch):
        tools, _ = make_tools(tmp_path, [])
        read_as(monkeypatch, playlist_of(("aaaaaaaaaaa", "Fresh"), ("aaaaaaaaaaa", "Fresh again")))

        videos = tools.check_playlist(PLAYLIST_URL)["videos"]

        assert [v["title"] for v in videos] == ["Fresh"]

    def test_new_videos_that_look_alike_are_grouped(self, tmp_path, monkeypatch):
        tools, _ = make_tools(tmp_path, [])
        read_as(
            monkeypatch,
            playlist_of(
                ("aaaaaaaaaaa", "Shape of You - Ed Sheeran (Lyrics)"),
                ("bbbbbbbbbbb", "Mirrors - Justin Timberlake"),
                ("ccccccccccc", "Ed Sheeran - Shape of You [Official Video]"),
            ),
        )

        result = tools.check_playlist(PLAYLIST_URL)

        assert result["groups"] == [
            {
                "part": "ed sheeran / shape of you",
                "videos": ["aaaaaaaaaaa", "ccccccccccc"],
                "songs": [],
            }
        ]
        assert [v["status"] for v in result["videos"]] == ["new", "new", "new"]  # nothing hidden

    def test_a_new_video_is_grouped_with_the_library_song_it_looks_like(
        self, tmp_path, monkeypatch
    ):
        have = make_video(tmp_path, "Justin Timberlake - Mirrors---uuZE_IRwLNI")
        genius_bundle(tmp_path, have.stem)
        tools, _ = make_tools(tmp_path, [str(have)])
        read_as(monkeypatch, playlist_of(("aaaaaaaaaaa", "Mirrors - Justin Timberlake (Lyrics)")))

        [group] = tools.check_playlist(PLAYLIST_URL)["groups"]

        assert group["videos"] == ["aaaaaaaaaaa"]
        assert group["songs"] == [{"song": str(have), "title": "Justin Timberlake - Mirrors"}]

    def test_a_video_already_in_the_library_is_not_a_group_member(self, tmp_path, monkeypatch):
        """Its twin is grouped with the library copy; the copy is not grouped with itself."""
        have = make_video(tmp_path, "Justin Timberlake - Mirrors---bbbbbbbbbbb")
        genius_bundle(tmp_path, have.stem)
        tools, _ = make_tools(tmp_path, [str(have)])
        read_as(
            monkeypatch,
            playlist_of(
                ("aaaaaaaaaaa", "Mirrors - Justin Timberlake (Lyrics)"),
                ("bbbbbbbbbbb", "Justin Timberlake - Mirrors [HD]"),
            ),
        )

        result = tools.check_playlist(PLAYLIST_URL)

        assert [(g["videos"], [s["song"] for s in g["songs"]]) for g in result["groups"]] == [
            (["aaaaaaaaaaa"], [str(have)])
        ]

    def test_videos_that_look_like_nothing_form_no_group(self, tmp_path, monkeypatch):
        have = make_video(tmp_path, "Justin Timberlake - Mirrors---uuZE_IRwLNI")
        tools, _ = make_tools(tmp_path, [str(have)])
        read_as(
            monkeypatch,
            playlist_of(
                ("aaaaaaaaaaa", "Queen - Bohemian Rhapsody"), ("bbbbbbbbbbb", "ABBA - SOS")
            ),
        )

        assert tools.check_playlist(PLAYLIST_URL)["groups"] == []

    @pytest.mark.parametrize(
        "url, message",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", PLAYLIST_ONE_VIDEO),
            ("https://youtu.be/dQw4w9WgXcQ", PLAYLIST_ONE_VIDEO),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc", PLAYLIST_VIDEO_IN_LIST),
            ("youtu.be/dQw4w9WgXcQ?list=PLabc", PLAYLIST_VIDEO_IN_LIST),
            ("https://example.com/playlist?list=PLabc", PLAYLIST_NOT_A_LINK),
            ("not a link", PLAYLIST_NOT_A_LINK),
            ("", PLAYLIST_NOT_A_LINK),
            (None, PLAYLIST_NOT_A_LINK),
        ],
    )
    def test_a_link_that_is_not_a_playlist_gets_a_message_and_no_read(
        self, tmp_path, monkeypatch, url, message
    ):
        tools, _ = make_tools(tmp_path, [])
        asked = read_as(monkeypatch, playlist_of())

        with pytest.raises(RegenError) as raised:
            tools.check_playlist(url)

        assert str(raised.value) == message
        assert asked == []

    @pytest.mark.parametrize(
        "error",
        [
            subprocess.CalledProcessError(1, "yt-dlp"),
            subprocess.TimeoutExpired("yt-dlp", 300),
            ValueError("not json"),
            FileNotFoundError("yt-dlp"),
        ],
        ids=["exit code", "timeout", "not json", "no yt-dlp"],
    )
    def test_a_playlist_that_cannot_be_read_says_so(self, tmp_path, monkeypatch, error):
        tools, _ = make_tools(tmp_path, [])

        def fail(url):
            raise error

        monkeypatch.setattr("pikaraoke.lib.library_tools.read_playlist", fail)

        with pytest.raises(RegenError) as raised:
            tools.check_playlist(PLAYLIST_URL)

        assert str(raised.value) == PLAYLIST_UNREADABLE


class TestAddPlaylist:
    @staticmethod
    def queued(tools: LibraryTools) -> list:
        return tools._download_manager.queue_download.call_args_list

    def test_each_video_is_queued_as_a_playlist_download(self, tmp_path):
        tools, _ = make_tools(tmp_path, [])

        result = tools.add_playlist(
            [{"id": "aaaaaaaaaaa", "title": "  First "}, {"id": "bbbbbbbbbbb", "title": "Second"}],
            [],
        )

        assert result == {"downloads": 2, "processing": 0, "listed": 0}
        assert [(c.args, c.kwargs) for c in self.queued(tools)] == [
            (
                ("https://www.youtube.com/watch?v=aaaaaaaaaaa",),
                {"enqueue": False, "user": "Playlist", "title": "First"},
            ),
            (
                ("https://www.youtube.com/watch?v=bbbbbbbbbbb",),
                {"enqueue": False, "user": "Playlist", "title": "Second"},
            ),
        ]

    def test_a_missing_title_is_left_to_the_download_manager(self, tmp_path):
        tools, _ = make_tools(tmp_path, [])

        tools.add_playlist([{"id": "aaaaaaaaaaa"}, {"id": "bbbbbbbbbbb", "title": 5}], [])

        assert [c.kwargs["title"] for c in self.queued(tools)] == [None, None]

    def test_a_long_title_is_cut(self, tmp_path):
        tools, _ = make_tools(tmp_path, [])

        tools.add_playlist([{"id": "aaaaaaaaaaa", "title": "x" * 500}], [])

        assert len(self.queued(tools)[0].kwargs["title"]) == 200

    def test_a_video_already_in_the_library_is_skipped(self, tmp_path):
        have = make_video(tmp_path, "Have---aaaaaaaaaaa")
        tools, _ = make_tools(tmp_path, [str(have)])

        result = tools.add_playlist(
            [{"id": "aaaaaaaaaaa", "title": "Have"}, {"id": "bbbbbbbbbbb", "title": "New"}], []
        )

        assert result["downloads"] == 1
        assert [c.args[0][-11:] for c in self.queued(tools)] == ["bbbbbbbbbbb"]

    @pytest.mark.parametrize(
        "video_id", [None, 5, "short", "twelve-chars", "bad id!!!!!!", "ünicode-ünic", ["a"]]
    )
    def test_an_id_that_is_not_eleven_url_safe_characters_is_skipped(self, tmp_path, video_id):
        tools, _ = make_tools(tmp_path, [])

        result = tools.add_playlist([{"id": video_id, "title": "x"}, "bad", None, 5], [])

        assert result["downloads"] == 0
        tools._download_manager.queue_download.assert_not_called()

    def test_a_video_listed_twice_or_already_waiting_is_queued_once(self, tmp_path):
        tools, _ = make_tools(tmp_path, [])
        tools._download_manager.pending_downloads = [
            {"video_url": "https://www.youtube.com/watch?v=bbbbbbbbbbb"}
        ]
        tools._download_manager.active_url = "https://www.youtube.com/watch?v=ccccccccccc"
        videos = [
            {"id": "aaaaaaaaaaa", "title": "A"},
            {"id": "aaaaaaaaaaa", "title": "A"},
            {"id": "bbbbbbbbbbb", "title": "B"},
            {"id": "ccccccccccc", "title": "C"},
        ]

        result = tools.add_playlist(videos, [])

        assert result["downloads"] == 1
        assert [c.args[0][-11:] for c in self.queued(tools)] == ["aaaaaaaaaaa"]

    @pytest.mark.parametrize("videos, unprocessed", [(None, []), ([], None), ("a", []), ({}, [])])
    def test_a_request_that_is_not_two_lists_is_refused(self, tmp_path, videos, unprocessed):
        tools, _ = make_tools(tmp_path, [])

        with pytest.raises(RegenError, match="Not a playlist selection"):
            tools.add_playlist(videos, unprocessed)

    def test_an_unprocessed_song_goes_through_the_download_check(self, download):
        write_caption(download.folder, STEM, words=60)

        result = download.tools.add_playlist([], [download.song])

        assert result == {"downloads": 0, "processing": 1, "listed": 0}
        download.processing.enqueue.assert_called_once_with(download.song)

    def test_an_unprocessed_song_without_a_usable_caption_is_listed_from_the_playlist(
        self, download
    ):
        download.tools.add_playlist([], [download.song])

        [row] = listed(download.tools)
        assert (row["song_path"], row["source"], row["reason"]) == (
            download.song,
            "playlist",
            "no_caption",
        )

    def test_songs_the_check_queues_and_songs_it_lists_are_counted_apart(self, download):
        captioned = make_video(download.folder, "Captioned---aaaaaaaaaaa")
        write_caption(download.folder, captioned.stem, words=60)
        download.tools._song_manager.songs.update([download.song, str(captioned)])

        result = download.tools.add_playlist([], [download.song, str(captioned)])

        assert result == {"downloads": 0, "processing": 1, "listed": 1}
        download.processing.enqueue.assert_called_once_with(str(captioned))
        [row] = listed(download.tools)
        assert (row["song_path"], row["source"]) == (download.song, "playlist")
        assert download.tools._playlist_ids == set()  # only for downloads that land later

    def test_a_check_that_fails_does_not_stop_the_songs_after_it(self, download, monkeypatch):
        second = make_video(download.folder, "Second---aaaaaaaaaaa")
        download.tools._song_manager.songs.update([download.song, str(second)])
        check = gate_on_disk_caption

        def fail_for_the_first(job):
            if job.song_path == Path(download.song):
                raise RuntimeError("boom")
            return check(job)

        monkeypatch.setattr("pikaraoke.lib.library_tools.gate_on_disk_caption", fail_for_the_first)

        result = download.tools.add_playlist([], [download.song, str(second)])

        assert result == {"downloads": 0, "processing": 1, "listed": 1}
        download.processing.enqueue.assert_called_once_with(download.song)
        assert [r["song_path"] for r in listed(download.tools)] == [str(second)]

    def test_a_song_that_is_busy_listed_processed_or_not_in_the_library_is_skipped(self, download):
        busy = make_video(download.folder, "Busy---bbbbbbbbbbb")
        done = make_video(download.folder, "Done---ccccccccccc")
        genius_bundle(download.folder, done.stem)
        stranger = make_video(download.folder, "Stranger---ddddddddddd")  # not in the library
        music = download.folder / "Tune---eeeeeeeeeee.mp3"
        music.write_bytes(b"")
        download.tools._song_manager.songs.update([str(busy), str(done), str(music)])
        download.processing.pending_jobs = [str(busy)]
        download.tools.on_song_downloaded(download.song)  # listed already
        download.processing.enqueue.reset_mock()

        result = download.tools.add_playlist(
            [], [str(busy), str(done), str(stranger), str(music), download.song, 5, None]
        )

        assert result == {"downloads": 0, "processing": 0, "listed": 0}
        download.processing.enqueue.assert_not_called()
