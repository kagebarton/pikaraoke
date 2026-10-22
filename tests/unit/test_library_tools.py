"""Unit tests for pikaraoke/lib/library_tools.py -- song lists, regenerate, repair and bulk runs.

The library is a real ``tmp_path`` folder with bundles; the processing manager is
a mock, so a queued job is whatever ``enqueue_regen`` was handed. Genius is a
fake over a dict of songs, and LRCLIB's network calls are patched.
"""

import json
import os
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pikaraoke.lib import lrclib
from pikaraoke.lib.alignment_capture import SCHEMA_VERSION
from pikaraoke.lib.genius import GeniusSong, GeniusUnavailable
from pikaraoke.lib.library_regen import CaptionCheck, RegenError, RegenJob
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
    state = state or folder / "library_tools_state.json"
    tools = LibraryTools(processing, song_manager, str(folder), genius or MagicMock(), state)
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

    def test_a_transcribe_repair_queues_a_transcribe_plan(self, tmp_path, song):
        regen = self.repaired(tmp_path, song, "transcribe")

        assert regen.reset is True
        assert regen.song.plan.kind == "transcribe"

    def test_backs_up_only_that_song(self, tmp_path, song):
        other = make_video(tmp_path, "B---bbbbbbbbbbb")
        genius_bundle(tmp_path, other.stem)

        self.repaired(tmp_path, song, "transcribe")

        [backup] = tmp_path.glob("regen_backup_*")
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
        assert not list(tmp_path.glob("regen_backup_*"))

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
        assert not list(tmp_path.glob("regen_backup_*"))

    def test_a_busy_song_is_refused_before_anything_is_fetched(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))
        genius = FakeGenius({7: GENIUS_SONG})
        tools, processing = make_tools(tmp_path, [str(song)], pending=[str(song)], genius=genius)

        with pytest.raises(RegenError, match="waiting or running"):
            tools.repair(str(song), "genius", genius_id=7, lrclib_id=5)

        assert genius.fetches == []
        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backup_*"))

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

        def fake_search(track, artist):
            searches.append((track, artist))
            return records

        monkeypatch.setattr(lrclib, "search", fake_search)
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

        found = tools.lrclib_candidates(str(song), 7, "defying gravity", "idina menzel")

        assert searches == [("defying gravity", "idina menzel")]
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

        found = tools.lrclib_candidates(str(song), 7, "t", "a")

        assert [(c["id"], c["best"]) for c in found["candidates"]] == [(2, False), (1, True)]

    def test_current_is_the_match_the_lrc_on_disk_records(self, tmp_path, song, monkeypatch):
        lrclib.write_lrc(lrclib.lrc_path(song), {**RECORD, "id": 2})
        records = [self.full(id=1), self.full(id=2)]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), 7, "t", "a")

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

        found = tools.lrclib_candidates(str(song), 7, "t", "a")

        assert [c["current"] for c in found["candidates"]] == [False, False]

    def test_a_record_without_synced_lyrics_is_left_out(self, tmp_path, song, monkeypatch):
        records = [{"id": 3, "trackName": "Plain only", "syncedLyrics": None}, self.full(id=1)]
        tools, _ = self.tools(tmp_path, song, records, monkeypatch)

        found = tools.lrclib_candidates(str(song), 7, "t", "a")

        assert [c["id"] for c in found["candidates"]] == [1]

    def test_no_matches_is_an_empty_list(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [], monkeypatch)

        assert tools.lrclib_candidates(str(song), 7, "t", "a")["candidates"] == []

    def test_a_match_with_no_length_has_no_difference(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [self.full(id=1, duration=None)], monkeypatch)

        [candidate] = tools.lrclib_candidates(str(song), 7, "t", "a")["candidates"]

        assert candidate["duration_diff_s"] is None

    def test_genius_lyrics_that_cannot_be_fetched_raise(self, tmp_path, song, monkeypatch):
        tools, _ = self.tools(tmp_path, song, [self.full(id=1)], monkeypatch)

        with pytest.raises(GeniusUnavailable):
            tools.lrclib_candidates(str(song), 99, "t", "a")


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
        monkeypatch.setattr(lrclib, "search", lambda track, artist: records)
        tools.lrclib_candidates(str(song), 7, "t", "a")
        return records

    def queued_record(self, tools, processing, song, lrclib_id):
        tools.repair(str(song), "genius", genius_id=7, lrclib_id=lrclib_id)
        return processing.enqueue_regen.call_args.args[0].song.plan.lrclib_record

    def test_a_repair_after_a_search_queues_the_listed_record(self, tmp_path, song, monkeypatch):
        monkeypatch.setattr(lrclib, "get_record", MagicMock(side_effect=AssertionError("fetched")))
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))
        _, listed = self.listed(tools, song, monkeypatch, 4, 5)

        assert self.queued_record(tools, processing, song, 5) is listed

    def test_without_a_search_a_repair_still_asks_lrclib(self, tmp_path, song, fetched):
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))

        record = self.queued_record(tools, processing, song, 5)

        assert fetched == [5]
        assert (record["id"], record["trackName"]) == (5, "fetched")

    def test_a_record_without_an_id_is_not_remembered(self, tmp_path, song, monkeypatch, fetched):
        tools, processing = make_tools(tmp_path, [str(song)], genius=FakeGenius({7: GENIUS_SONG}))
        no_id = {k: v for k, v in RECORD.items() if k != "id"}
        monkeypatch.setattr(lrclib, "search", lambda track, artist: [no_id])
        tools.lrclib_candidates(str(song), 7, "t", "a")

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

    def test_a_check_that_fails_counts_as_no_usable_caption(self, tmp_path, monkeypatch, caplog):
        paths = bulk_library(tmp_path)
        monkeypatch.setattr(
            "pikaraoke.lib.library_tools.check_caption", MagicMock(side_effect=RuntimeError("x"))
        )
        tools, _ = make_tools(tmp_path, list(paths.values()))

        tools.open_run("reset")
        finish_checks(tools)

        assert set(groups(tools).values()) == {"needs_pick"}
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
        assert not list(tmp_path.glob("regen_backup_*"))
        assert tools.run_view() is not None

    def test_it_refuses_while_a_song_still_needs_a_pick(self, tmp_path, monkeypatch):
        tools, processing, paths = open_run(tmp_path, monkeypatch, "all", RUN_ANSWERS)
        tools.save_pick(paths["no_id"], {"kind": "skip"})  # unprocessed still needs one

        with pytest.raises(RegenError, match="Pick lyrics"):
            tools.queue_run()

        processing.enqueue_regen.assert_not_called()
        assert not list(tmp_path.glob("regen_backup_*"))

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
            backups_at_enqueue.append(len(list(tmp_path.glob("regen_backup_*")))) or True
        )

        result = tools.queue_run()

        [backup] = tmp_path.glob("regen_backup_*")
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
        assert not list(tmp_path.glob("regen_backup_*"))
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
        assert not list(tmp_path.glob("regen_backup_*"))
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
        assert not list(tmp_path.glob("regen_backup_*"))
        assert tools.run_view() is not None
