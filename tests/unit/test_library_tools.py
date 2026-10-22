"""Unit tests for pikaraoke/lib/library_tools.py -- song lists, regenerate and repair.

The library is a real ``tmp_path`` folder with bundles; the processing manager is
a mock, so a queued job is whatever ``enqueue_regen`` was handed. Genius is a
fake over a dict of songs, and LRCLIB's network calls are patched.
"""

import json
import os
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


def make_tools(folder: Path, songs: list[str], *, active=None, pending=(), genius=None):
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
    return LibraryTools(processing, song_manager, str(folder), genius or MagicMock()), processing


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
