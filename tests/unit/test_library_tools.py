"""Unit tests for pikaraoke/lib/library_tools.py -- song lists and regenerate.

The library is a real ``tmp_path`` folder with bundles; the processing manager is
a mock, so a queued job is whatever ``enqueue_regen`` was handed.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.library_regen import RegenError, RegenJob
from pikaraoke.lib.library_tools import LibraryTools
from pikaraoke.lib.song_list import SongList
from pikaraoke.lib.song_manager import SongManager

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


def make_tools(folder: Path, songs: list[str], *, active=None, pending=()):
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
    return LibraryTools(processing, song_manager, str(folder)), processing


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
        assert len(names("all")) == 4
        assert tools.overview() == {"behind": 1, "poor": 1, "no_lyrics": 1, "all": 4}

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

        [backup] = tmp_path.glob("regen_backup_*")
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

    def test_a_song_with_no_pick_is_pointed_at_repair(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        tools, processing = make_tools(tmp_path, [str(video)])

        assert not tools.can_regenerate(str(video))
        with pytest.raises(RegenError, match="Repair lyrics"):
            tools.regenerate(str(video))
        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backup_*"))

    def test_a_busy_song_is_refused_before_any_backup(self, tmp_path):
        [video] = make_videos(tmp_path, "A---aaaaaaaaaaa")
        genius_bundle(tmp_path, video.stem)
        tools, processing = make_tools(tmp_path, [str(video)], pending=[str(video)])

        with pytest.raises(RegenError, match="waiting or running"):
            tools.regenerate(str(video))

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backup_*"))

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
