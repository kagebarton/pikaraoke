"""Unit tests for KaraokeDatabase."""

import os
import sqlite3

import pytest

from pikaraoke.lib.karaoke_database import KaraokeDatabase


def _song(path, *, youtube_id=None, format="mp4", pipeline_state="skipped"):
    return {
        "file_path": path,
        "youtube_id": youtube_id,
        "format": format,
        "pipeline_state": pipeline_state,
    }


@pytest.fixture
def db(tmp_path):
    """A fresh KaraokeDatabase backed by a temporary file."""
    d = KaraokeDatabase(str(tmp_path / "test.db"))
    yield d
    d.close()


class TestInit:
    def test_creates_db_file(self, tmp_path):
        db_path = str(tmp_path / "pikaraoke.db")
        db = KaraokeDatabase(db_path)
        db.close()
        assert os.path.exists(db_path)

    def test_wal_mode(self, db):
        mode = db._conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_user_version(self, db):
        ver = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert ver == 2

    def test_songs_table_exists(self, db):
        tables = {
            row[0]
            for row in db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "songs" in tables

    def test_empty_on_init(self, db):
        assert db.get_song_count() == 0


class TestGetAllSongPaths:
    def test_returns_empty_list_when_no_songs(self, db):
        assert db.get_all_song_paths() == []

    def test_returns_all_inserted_paths(self, db):
        db.insert_songs(
            [
                _song("/songs/zebra.mp4"),
                _song("/songs/apple.mp4"),
                _song("/songs/Mango.mp4"),
            ]
        )
        paths = set(db.get_all_song_paths())
        assert paths == {"/songs/zebra.mp4", "/songs/apple.mp4", "/songs/Mango.mp4"}


class TestInsertSongs:
    def test_basic_insert(self, db):
        db.insert_songs([_song("/songs/test.mp4")])
        assert db.get_song_count() == 1

    def test_ignores_duplicate_file_path(self, db):
        record = _song("/songs/test.mp4")
        db.insert_songs([record])
        db.insert_songs([record])
        assert db.get_song_count() == 1

    def test_batch_insert(self, db):
        records = [_song(f"/songs/song{i}.mp4") for i in range(10)]
        db.insert_songs(records)
        assert db.get_song_count() == 10

    def test_stores_youtube_id(self, db):
        db.insert_songs([_song("/songs/t.mp4", youtube_id="dQw4w9WgXcQ")])
        row = db._conn.execute("SELECT youtube_id FROM songs").fetchone()
        assert row[0] == "dQw4w9WgXcQ"

    def test_pipeline_state_default_skipped(self, db):
        db.insert_songs([_song("/songs/t.mp4")])
        row = db._conn.execute("SELECT pipeline_state FROM songs").fetchone()
        assert row[0] == "skipped"

    def test_pipeline_state_pending(self, db):
        db.insert_songs([_song("/songs/t.mp4", pipeline_state="pending")])
        row = db._conn.execute("SELECT pipeline_state FROM songs").fetchone()
        assert row[0] == "pending"


class TestDeleteByPath:
    def test_deletes_single_song(self, db):
        db.insert_songs([_song("/songs/test.mp4")])
        db.delete_by_path("/songs/test.mp4")
        assert db.get_song_count() == 0

    def test_no_error_on_missing_path(self, db):
        db.delete_by_path("/songs/nonexistent.mp4")  # should not raise


class TestDeleteByPaths:
    def test_batch_delete(self, db):
        records = [_song(f"/songs/song{i}.mp4") for i in range(5)]
        db.insert_songs(records)
        db.delete_by_paths(["/songs/song0.mp4", "/songs/song1.mp4"])
        assert db.get_song_count() == 3


class TestUpdatePath:
    def test_updates_file_path(self, db):
        db.insert_songs([_song("/songs/old.mp4")])
        db.update_path("/songs/old.mp4", "/songs/new.mp4")
        assert db.get_all_song_paths() == ["/songs/new.mp4"]


class TestUpdatePaths:
    def test_batch_moves(self, db):
        db.insert_songs([_song("/old/a.mp4"), _song("/old/b.mp4")])
        db.update_paths([("/old/a.mp4", "/new/a.mp4"), ("/old/b.mp4", "/new/b.mp4")])
        paths = set(db.get_all_song_paths())
        assert paths == {"/new/a.mp4", "/new/b.mp4"}


class TestMetadata:
    def test_get_returns_none_when_unset(self, db):
        assert db.get_metadata("nonexistent") is None

    def test_set_and_get_round_trip(self, db):
        db.set_metadata("scan_dir", "/songs")
        assert db.get_metadata("scan_dir") == "/songs"

    def test_set_overwrites_existing(self, db):
        db.set_metadata("scan_dir", "/old")
        db.set_metadata("scan_dir", "/new")
        assert db.get_metadata("scan_dir") == "/new"

    def test_metadata_table_exists(self, db):
        tables = {
            row[0]
            for row in db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "metadata" in tables


class TestApplyScanDiff:
    def test_applies_moves_inserts_deletes_atomically(self, db):
        db.insert_songs([_song("/songs/old.mp4"), _song("/songs/remove.mp4")])
        db.apply_scan_diff(
            moves=[("/songs/old.mp4", "/songs/new.mp4")],
            inserts=[_song("/songs/added.mp4")],
            deletes=["/songs/remove.mp4"],
        )
        paths = set(db.get_all_song_paths())
        assert paths == {"/songs/new.mp4", "/songs/added.mp4"}

    def test_rolls_back_on_error(self, db):
        db.insert_songs([_song("/songs/a.mp4"), _song("/songs/b.mp4"), _song("/songs/c.mp4")])
        # Moving two rows to the same path violates UNIQUE on file_path.
        # The entire transaction (including the delete) should roll back.
        with pytest.raises(Exception):
            db.apply_scan_diff(
                moves=[("/songs/a.mp4", "/songs/clash.mp4"), ("/songs/b.mp4", "/songs/clash.mp4")],
                inserts=[],
                deletes=["/songs/c.mp4"],
            )
        # All 3 original songs should remain untouched
        assert db.get_song_count() == 3
        assert set(db.get_all_song_paths()) == {"/songs/a.mp4", "/songs/b.mp4", "/songs/c.mp4"}


class TestIntegrityCheck:
    def test_ok_on_fresh_db(self, db):
        ok, msg = db.check_integrity()
        assert ok is True
        assert msg == "ok"


class TestUnicodeFilenames:
    def test_unicode_path_stored_and_retrieved(self, db):
        path = "/songs/Céline Dion - My Heart---abc1234567x.mp4"
        db.insert_songs([_song(path, youtube_id="abc1234567x")])
        assert db.get_all_song_paths() == [path]


class TestPipelineColumns:
    """Tests for set/get_loudnorm_offset and set/get_pipeline_state."""

    def test_set_and_get_loudnorm_offset(self, db):
        db.insert_songs([_song("/songs/t.mp4")])
        db.set_loudnorm_offset("/songs/t.mp4", -3.5)
        assert db.get_loudnorm_offset("/songs/t.mp4") == pytest.approx(-3.5)

    def test_get_loudnorm_offset_none_when_unset(self, db):
        db.insert_songs([_song("/songs/t.mp4")])
        assert db.get_loudnorm_offset("/songs/t.mp4") is None

    def test_get_loudnorm_offset_none_for_missing_song(self, db):
        assert db.get_loudnorm_offset("/songs/nonexistent.mp4") is None

    def test_loudnorm_offset_persists_after_reopen(self, tmp_path):
        path = str(tmp_path / "reopen.db")
        db1 = KaraokeDatabase(path)
        db1.insert_songs([_song("/songs/t.mp4")])
        db1.set_loudnorm_offset("/songs/t.mp4", -1.25)
        db1.close()
        db2 = KaraokeDatabase(path)
        assert db2.get_loudnorm_offset("/songs/t.mp4") == pytest.approx(-1.25)
        db2.close()

    def test_set_and_get_pipeline_state(self, db):
        db.insert_songs([_song("/songs/t.mp4")])
        db.set_pipeline_state("/songs/t.mp4", "ready")
        assert db.get_pipeline_state("/songs/t.mp4") == "ready"

    def test_get_pipeline_state_none_for_missing_song(self, db):
        assert db.get_pipeline_state("/songs/nonexistent.mp4") is None

    def test_pipeline_state_round_trips_all_values(self, db):
        db.insert_songs([_song("/songs/t.mp4")])
        for state in ("pending", "ready", "failed", "skipped"):
            db.set_pipeline_state("/songs/t.mp4", state)
            assert db.get_pipeline_state("/songs/t.mp4") == state

    def test_pipeline_state_persists_after_reopen(self, tmp_path):
        path = str(tmp_path / "reopen.db")
        db1 = KaraokeDatabase(path)
        db1.insert_songs([_song("/songs/t.mp4")])
        db1.set_pipeline_state("/songs/t.mp4", "ready")
        db1.close()
        db2 = KaraokeDatabase(path)
        assert db2.get_pipeline_state("/songs/t.mp4") == "ready"
        db2.close()

    def test_get_pipeline_states_batch(self, db):
        db.insert_songs(
            [
                _song("/songs/a.mp4", pipeline_state="ready"),
                _song("/songs/b.mp4", pipeline_state="pending"),
            ]
        )
        db.set_pipeline_state("/songs/a.mp4", "ready")
        db.set_pipeline_state("/songs/b.mp4", "pending")
        result = db.get_pipeline_states(["/songs/a.mp4", "/songs/b.mp4", "/songs/missing.mp4"])
        assert result["/songs/a.mp4"] == "ready"
        assert result["/songs/b.mp4"] == "pending"
        assert "/songs/missing.mp4" not in result


class TestV2Migration:
    """Verify the v1 → v2 migration path is correct and idempotent."""

    def _make_v1_db(self, db_path: str) -> None:
        """Create a v1 database: full v1 column set, no loudnorm_offset_db or pipeline_state."""
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                youtube_id TEXT,
                format TEXT NOT NULL,
                artist TEXT,
                title TEXT,
                variant TEXT,
                year INTEGER,
                genre TEXT,
                metadata_status TEXT DEFAULT 'pending',
                enrichment_attempts INTEGER DEFAULT 0,
                last_enrichment_attempt TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_youtube_id ON songs(youtube_id);
            CREATE INDEX IF NOT EXISTS idx_artist ON songs(artist);
            CREATE INDEX IF NOT EXISTS idx_title ON songs(title);
            CREATE INDEX IF NOT EXISTS idx_metadata_status ON songs(metadata_status);

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO songs (file_path, youtube_id, format) VALUES (?, ?, ?)",
            ("/songs/old.mp4", None, "mp4"),
        )
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        conn.close()

    def test_migration_adds_columns(self, tmp_path):
        db_path = str(tmp_path / "v1.db")
        self._make_v1_db(db_path)
        db = KaraokeDatabase(db_path)
        cols = {row[1] for row in db._conn.execute("PRAGMA table_info(songs)")}
        assert "loudnorm_offset_db" in cols
        assert "pipeline_state" in cols
        db.close()

    def test_migration_existing_row_gets_skipped_default(self, tmp_path):
        db_path = str(tmp_path / "v1.db")
        self._make_v1_db(db_path)
        db = KaraokeDatabase(db_path)
        assert db.get_pipeline_state("/songs/old.mp4") == "skipped"
        assert db.get_loudnorm_offset("/songs/old.mp4") is None
        db.close()

    def test_migration_bumps_user_version(self, tmp_path):
        db_path = str(tmp_path / "v1.db")
        self._make_v1_db(db_path)
        db = KaraokeDatabase(db_path)
        ver = db._conn.execute("PRAGMA user_version").fetchone()[0]
        assert ver == 2
        db.close()

    def test_migration_is_idempotent(self, tmp_path):
        """Running migration twice on the same DB must not raise."""
        db_path = str(tmp_path / "v1.db")
        self._make_v1_db(db_path)
        db1 = KaraokeDatabase(db_path)
        db1.close()
        # Second open triggers _create_schema again; migration must be a no-op.
        db2 = KaraokeDatabase(db_path)
        assert db2.get_pipeline_state("/songs/old.mp4") == "skipped"
        db2.close()
