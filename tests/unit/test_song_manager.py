"""Unit tests for SongManager."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.events import EventSystem
from pikaraoke.lib.karaoke_database import KaraokeDatabase
from pikaraoke.lib.song_manager import SongManager


def _native(path: Path) -> str:
    """Convert Path to native OS string to match SongList's internal storage format."""
    return str(path)


class TestFilenameFromPath:
    """Tests for the filename_from_path static method."""

    def test_basic(self):
        assert SongManager.filename_from_path("/songs/My Song.mp4") == "My Song"

    def test_with_youtube_id(self):
        result = SongManager.filename_from_path("/songs/Artist - Song Title---dQw4w9WgXcQ.mp4")
        assert result == "Artist - Song Title"

    def test_keep_youtube_id(self):
        result = SongManager.filename_from_path(
            "/songs/Artist - Song---dQw4w9WgXcQ.mp4", remove_youtube_id=False
        )
        assert result == "Artist - Song---dQw4w9WgXcQ"

    def test_nested_directory(self):
        result = SongManager.filename_from_path(
            "/home/user/music/karaoke/songs/Track---dQw4w9WgXcQ.mp4"
        )
        assert result == "Track"

    def test_multiple_dashes(self):
        result = SongManager.filename_from_path(
            "/songs/Artist - Song - Live Version---dQw4w9WgXcQ.mp4"
        )
        assert result == "Artist - Song - Live Version"

    def test_no_extension(self):
        assert SongManager.filename_from_path("/songs/SongName") == "SongName"

    def test_zip_file(self):
        """ZIP files have no YouTube ID, so the name is returned as-is."""
        assert SongManager.filename_from_path("/songs/Karaoke Track.zip") == "Karaoke Track"

    def test_bracket_format_youtube_id(self):
        result = SongManager.filename_from_path("/songs/Artist - Song [dQw4w9WgXcQ].mp4")
        assert result == "Artist - Song"

    def test_bracket_format_keep_id(self):
        result = SongManager.filename_from_path(
            "/songs/Artist - Song [dQw4w9WgXcQ].mp4", remove_youtube_id=False
        )
        assert result == "Artist - Song [dQw4w9WgXcQ]"

    def test_bracket_format_short_id_not_stripped(self):
        """Non-YouTube files are not tidied, so short bracket text is preserved."""
        result = SongManager.filename_from_path("/songs/Song [short].mp4")
        assert result == "Song [short]"

    # --- regex_tidy integration: noise word stripping ---

    def test_strips_karaoke_noise_words(self):
        result = SongManager.filename_from_path(
            "/songs/Queen - Bohemian Rhapsody Karaoke Version HD---dQw4w9WgXcQ.mp4"
        )
        assert result == "Queen - Bohemian Rhapsody"

    def test_strips_instrumental_suffix(self):
        result = SongManager.filename_from_path(
            "/songs/Artist - Song Instrumental---dQw4w9WgXcQ.mp4"
        )
        assert result == "Artist - Song"

    def test_strips_lyrics_suffix(self):
        result = SongManager.filename_from_path(
            "/songs/Artist - Song With Lyrics---dQw4w9WgXcQ.mp4"
        )
        assert result == "Artist - Song"

    def test_underscores_replaced_with_spaces(self):
        result = SongManager.filename_from_path("/songs/Artist_-_Song_Title---dQw4w9WgXcQ.mp4")
        assert result == "Artist - Song Title"

    def test_all_noise_fallback_preserves_original(self):
        """When regex_tidy strips everything, fall back to the pre-tidy name."""
        result = SongManager.filename_from_path("/songs/Karaoke Track---dQw4w9WgXcQ.mp4")
        assert result == "Karaoke Track"

    def test_tidy_not_applied_when_keeping_youtube_id(self):
        """remove_youtube_id=False skips tidying (used by batch renamer for raw stems)."""
        result = SongManager.filename_from_path(
            "/songs/Artist - Song_Title Karaoke---dQw4w9WgXcQ.mp4",
            remove_youtube_id=False,
        )
        assert result == "Artist - Song_Title Karaoke---dQw4w9WgXcQ"


# Every kind of file a song owns beside it: (folder, tail after the stem).
OWNED_KINDS = [
    ("subtitles", ".srt"),
    ("subtitles", ".srt.generated"),
    ("subtitles", ".en.srt"),
    ("subtitles", ".en.asr.json3"),
    ("subtitles", ".en.vtt"),
    ("karaoke", ".ass"),
    ("lyrics", ".lrc"),
    ("lyrics", ".custom.txt"),
    ("lyrics", ".custom.srt"),
    ("lyrics", ".lrclib.srt"),
    ("lyrics", ".caption-edited.srt"),
    ("lyrics", ".movie-edited.srt"),
    ("lyrics", ".lrclib-edited.srt"),
    ("alignment_debug", ".json"),
    ("vocal", "---vocal.m4a"),
    ("nonvocal", "---nonvocal.m4a"),
    ("dereverb", "---dereverb.m4a"),
]
# The kinds a backup snapshot holds: stems are regenerable and never backed up.
BACKED_UP_KINDS = [(sub, tail) for sub, tail in OWNED_KINDS if not tail.endswith(".m4a")]


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    return root


@pytest.fixture
def db(tmp_path):
    """A real KaraokeDatabase, kept outside the library folder."""
    d = KaraokeDatabase(str(tmp_path / "test.db"))
    yield d
    d.close()


@pytest.fixture
def sm(library, db):
    return SongManager(str(library), db=db, events=EventSystem())


def _add_song(sm: SongManager, folder: Path, stem: str, ext: str = ".mp4") -> Path:
    song = folder / (stem + ext)
    song.parent.mkdir(parents=True, exist_ok=True)
    song.write_text("video")
    sm.register_download(_native(song))
    return song


def _add_sidecar(folder: Path, stem: str, sub: str, tail: str) -> Path:
    path = folder / sub / (stem + tail)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{sub}{tail}")
    return path


class TestDelete:
    def test_removes_file_and_updates_songs(self, library, sm, db):
        song = _add_song(sm, library, "Test---abc")
        sm.delete(_native(song))
        assert not song.exists()
        assert len(sm.songs) == 0
        assert db.get_pipeline_state(_native(song)) is None

    @pytest.mark.parametrize("sub, tail", OWNED_KINDS)
    def test_removes_every_kind_of_owned_file(self, library, sm, sub, tail):
        song = _add_song(sm, library, "Test---abc")
        owned = _add_sidecar(library, "Test---abc", sub, tail)
        sm.delete(_native(song))
        assert not owned.exists()

    def test_emits_song_deleted_event(self, library, db):
        song = library / "Test---abc.mp4"
        song.write_text("fake")
        events = MagicMock()
        sm = SongManager(str(library), db=db, events=events)
        sm.songs.add_if_valid(_native(song))
        sm.delete(_native(song))
        events.emit.assert_called_once_with("song_deleted", _native(song))

    def test_leaves_a_sibling_whose_name_shares_the_prefix(self, library, sm):
        """``Song`` never takes ``Song.live``'s files, the way a prefix match would."""
        song = _add_song(sm, library, "Song")
        sibling = _add_song(sm, library, "Song.live")
        mine = _add_sidecar(library, "Song", "subtitles", ".srt")
        theirs = [_add_sidecar(library, "Song.live", sub, tail) for sub, tail in OWNED_KINDS]
        sm.delete(_native(song))
        assert not mine.exists()
        assert sibling.exists() and all(f.exists() for f in theirs)

    def test_nonexistent_file_no_error(self, library, sm):
        sm.delete(_native(library / "nonexistent.mp4"))

    def test_a_vanished_folder_still_clears_the_song_from_the_list_and_db(self, library, sm, db):
        song = _add_song(sm, library / "usb", "Gone---abc")
        song.unlink()
        song.parent.rmdir()
        sm.delete(_native(song))
        assert _native(song) not in sm.songs
        assert db.get_pipeline_state(_native(song)) is None

    def test_backs_up_the_text_files_before_removing_them(self, library, sm):
        song = _add_song(sm, library, "Test---abc")
        sheet = _add_sidecar(library, "Test---abc", "lyrics", ".custom.srt")
        bundle = _add_sidecar(library, "Test---abc", "alignment_debug", ".json")
        stem_file = _add_sidecar(library, "Test---abc", "vocal", "---vocal.m4a")
        sm.delete(_native(song))
        (backup,) = (library / "regen_backups").iterdir()
        assert (backup / "lyrics" / sheet.name).read_text() == "lyrics.custom.srt"
        assert (backup / "alignment_debug" / bundle.name).read_text() == "alignment_debug.json"
        assert not sheet.exists() and not bundle.exists()
        assert not (backup / "vocal").exists()  # stems are regenerable, not backed up
        assert not stem_file.exists()

    def test_backs_up_a_song_whose_video_is_already_gone(self, library, sm):
        """Backup and delete agree on what the song owns, so the sheet isn't lost."""
        song = _add_song(sm, library, "Gone---abc")
        sheet = _add_sidecar(library, "Gone---abc", "lyrics", ".custom.txt")
        song.unlink()
        sm.delete(_native(song))
        (backup,) = (library / "regen_backups").iterdir()
        assert (backup / "lyrics" / sheet.name).read_text() == "lyrics.custom.txt"
        assert not sheet.exists()

    def test_a_song_with_no_text_files_makes_no_backup_folder(self, library, sm):
        song = _add_song(sm, library, "Test---abc")
        _add_sidecar(library, "Test---abc", "vocal", "---vocal.m4a")
        sm.delete(_native(song))
        assert not (library / "regen_backups").exists()

    def test_a_failed_backup_deletes_nothing(self, library, sm, db):
        song = _add_song(sm, library, "Test---abc")
        sheet = _add_sidecar(library, "Test---abc", "lyrics", ".custom.srt")
        with patch(
            "pikaraoke.lib.song_manager.backup_text_folders", side_effect=OSError("disk full")
        ):
            with pytest.raises(OSError):
                sm.delete(_native(song))
        assert song.exists() and sheet.exists()
        assert _native(song) in sm.songs
        assert db.get_pipeline_state(_native(song)) == "pending"

    def test_a_file_that_cannot_be_removed_leaves_the_video(self, library, sm, db):
        """A locked stem (Windows) stops the delete with the song still playable."""
        song = _add_song(sm, library, "Test---abc")
        stem_file = _add_sidecar(library, "Test---abc", "vocal", "---vocal.m4a")
        real_remove = os.remove

        def remove(path):
            if Path(path) == stem_file:
                raise PermissionError("locked")
            real_remove(path)

        with patch("pikaraoke.lib.song_manager.os.remove", side_effect=remove):
            with pytest.raises(PermissionError):
                sm.delete(_native(song))
        assert song.exists() and stem_file.exists()
        assert _native(song) in sm.songs
        assert db.get_pipeline_state(_native(song)) == "pending"


class TestRename:
    def test_renames_file_and_updates_songs(self, library, sm, db):
        song = _add_song(sm, library, "Old Name---abc")
        new = sm.rename(_native(song), "New Name---abc")
        assert not song.exists()
        assert (library / "New Name---abc.mp4").exists()
        assert new in sm.songs and _native(song) not in sm.songs
        assert db.get_pipeline_state(new) == "pending"
        assert db.get_pipeline_state(_native(song)) is None

    @pytest.mark.parametrize("sub, tail", OWNED_KINDS)
    def test_moves_every_kind_of_owned_file(self, library, sm, sub, tail):
        song = _add_song(sm, library, "Old---abc")
        old = _add_sidecar(library, "Old---abc", sub, tail)
        sm.rename(_native(song), "New---abc")
        assert (library / sub / ("New---abc" + tail)).read_text() == f"{sub}{tail}"
        assert not old.exists()

    def test_returns_new_path(self, library, sm):
        song = _add_song(sm, library, "Old---abc")
        assert sm.rename(_native(song), "New---abc") == _native(library / "New---abc.mp4")

    def test_leaves_a_sibling_whose_name_shares_the_prefix(self, library, sm):
        """``Song`` never takes ``Song.live``'s files, the way a prefix match would."""
        song = _add_song(sm, library, "Song")
        sibling = _add_song(sm, library, "Song.live")
        mine = _add_sidecar(library, "Song", "subtitles", ".srt")
        theirs = [_add_sidecar(library, "Song.live", sub, tail) for sub, tail in OWNED_KINDS]
        sm.rename(_native(song), "Other")
        assert (library / "subtitles" / "Other.srt").exists() and not mine.exists()
        assert sibling.exists() and all(f.exists() for f in theirs)

    def test_a_song_in_a_subfolder_is_renamed_in_place(self, library, sm):
        folder = library / "Musicals"
        song = _add_song(sm, folder, "Old---abc")
        _add_sidecar(folder, "Old---abc", "subtitles", ".srt")
        new = sm.rename(_native(song), "New---abc")
        assert new == _native(folder / "New---abc.mp4")
        assert (folder / "subtitles" / "New---abc.srt").exists()
        assert not (library / "New---abc.mp4").exists()

    @pytest.mark.parametrize("new_name", ["../New---abc", "AC/DC - New---abc"])
    def test_a_slash_in_the_new_name_keeps_the_song_in_its_folder(self, library, sm, new_name):
        song = _add_song(sm, library, "Old---abc")
        _add_sidecar(library, "Old---abc", "subtitles", ".srt")
        new = Path(sm.rename(_native(song), new_name))
        assert new.parent == library and new.exists()
        assert (library / "subtitles" / (new.stem + ".srt")).exists()

    @pytest.mark.parametrize("new_name", ["", "   "])
    def test_refuses_a_blank_name(self, library, sm, db, new_name):
        song = _add_song(sm, library, "Old---abc")
        sidecar = _add_sidecar(library, "Old---abc", "subtitles", ".srt")
        self._assert_refused(sm, db, song, new_name, touched=[song, sidecar], error=ValueError)

    def _assert_refused(self, sm, db, song, new_name, *, touched, error=FileExistsError):
        """The rename raises ``error`` and leaves files, SongList and DB alone."""
        before = {p: p.read_text() for p in touched}
        with pytest.raises(error):
            sm.rename(_native(song), new_name)
        assert {p: p.read_text() for p in touched} == before
        assert _native(song) in sm.songs
        assert db.get_pipeline_state(_native(song)) == "pending"

    def test_refuses_a_name_another_song_has_with_a_different_extension(self, library, sm, db):
        song = _add_song(sm, library, "Old")
        other = _add_song(sm, library, "New", ".mp3")
        sidecar = _add_sidecar(library, "Old", "subtitles", ".srt")
        self._assert_refused(sm, db, song, "New", touched=[song, other, sidecar])

    def test_refuses_a_name_whose_leftover_files_it_would_take_over(self, library, sm, db):
        song = _add_song(sm, library, "Old")
        sidecar = _add_sidecar(library, "Old", "subtitles", ".srt")
        orphan = _add_sidecar(library, "New", "subtitles", ".srt.generated")
        self._assert_refused(sm, db, song, "New", touched=[song, sidecar, orphan])

    def test_refuses_when_a_moved_file_would_land_on_a_sibling_songs(self, library, sm, db):
        """``Old.live.srt`` belongs to ``Old`` and would become ``New.live.srt``, which
        the song ``New.live`` owns."""
        song = _add_song(sm, library, "Old")
        _add_song(sm, library, "New.live")
        mine = _add_sidecar(library, "Old", "subtitles", ".live.srt")
        theirs = _add_sidecar(library, "New.live", "subtitles", ".srt")
        self._assert_refused(sm, db, song, "New", touched=[song, mine, theirs])

    def test_moves_its_backed_up_files_so_its_history_survives(self, library, sm):
        song = _add_song(sm, library, "Old---abc")
        backup = library / "regen_backups" / "20260101T000000Z"
        old = [_add_sidecar(backup, "Old---abc", sub, tail) for sub, tail in BACKED_UP_KINDS]
        sm.rename(_native(song), "New---abc")
        for (sub, tail), f in zip(BACKED_UP_KINDS, old):
            assert (backup / sub / ("New---abc" + tail)).read_text() == f"{sub}{tail}"
            assert not f.exists()

    def test_leaves_a_siblings_backed_up_files(self, library, sm):
        song = _add_song(sm, library, "Song")
        _add_song(sm, library, "Song.live")
        backup = library / "regen_backups" / "20260101T000000Z"
        theirs = _add_sidecar(backup, "Song.live", "lyrics", ".lrc")
        sm.rename(_native(song), "Other")
        assert theirs.exists()

    def test_refuses_a_name_with_backed_up_files_of_its_own(self, library, sm, db):
        """A deleted song's backups under the new name would join this song's history."""
        song = _add_song(sm, library, "Old")
        sidecar = _add_sidecar(library, "Old", "subtitles", ".srt")
        orphan = _add_sidecar(
            library / "regen_backups" / "20260101T000000Z", "New", "lyrics", ".lrc"
        )
        self._assert_refused(sm, db, song, "New", touched=[song, sidecar, orphan])

    def test_a_move_failing_partway_puts_every_file_back(self, library, sm, db):
        song = _add_song(sm, library, "Old---abc")
        owned = [_add_sidecar(library, "Old---abc", sub, tail) for sub, tail in OWNED_KINDS[:4]]
        real_rename = os.rename
        calls = []

        def flaky_rename(src, dst):
            calls.append(src)
            if len(calls) == 3:
                raise PermissionError("locked")
            real_rename(src, dst)

        with patch("pikaraoke.lib.song_manager.os.rename", side_effect=flaky_rename):
            with pytest.raises(PermissionError):
                sm.rename(_native(song), "New---abc")
        assert song.exists() and all(f.exists() for f in owned)
        assert not (library / "New---abc.mp4").exists()
        assert _native(song) in sm.songs
        assert db.get_pipeline_state(_native(song)) == "pending"
        assert db.get_pipeline_state(_native(library / "New---abc.mp4")) is None


class TestDBCoordination:
    """Tests that SongManager coordinates with KaraokeDatabase when provided."""

    def test_delete_calls_db_delete(self, tmp_path):
        song = tmp_path / "Test---abc.mp4"
        song.write_text("fake")
        mock_db = MagicMock()
        sm = SongManager(str(tmp_path), db=mock_db)
        sm.songs.add_if_valid(_native(song))
        sm.delete(_native(song))
        mock_db.delete_by_path.assert_called_once_with(_native(song))

    def test_rename_calls_db_update_path(self, tmp_path):
        song = tmp_path / "Old---abc.mp4"
        song.write_text("fake")
        mock_db = MagicMock()
        sm = SongManager(str(tmp_path), db=mock_db)
        sm.songs.add_if_valid(_native(song))
        sm.rename(_native(song), "New---abc")
        mock_db.update_path.assert_called_once_with(
            _native(song), _native(tmp_path / "New---abc.mp4")
        )

    def test_register_download_adds_to_songs_and_db(self, tmp_path):
        song = tmp_path / "New---xyz12345678.mp4"
        song.write_text("fake")
        mock_db = MagicMock()
        sm = SongManager(str(tmp_path), db=mock_db)
        sm.register_download(_native(song))
        assert _native(song) in sm.songs
        mock_db.insert_songs.assert_called_once()
