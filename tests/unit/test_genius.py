"""Unit tests for pikaraoke.lib.genius — GeniusClient and sidecar I/O."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.genius import (
    CHOICES_SUBDIR,
    GeniusClient,
    GeniusHit,
    GeniusUnavailable,
    choices_dir,
    delete_choice,
    read_choice,
    write_choice,
)

# ---------------------------------------------------------------------------
# GeniusClient — construction
# ---------------------------------------------------------------------------


class TestGeniusClientConstruction:
    """GeniusClient is always constructed, even with an empty token (DD2)."""

    def test_empty_token_creates_instance(self):
        client = GeniusClient(api_token="")
        assert client is not None
        assert client._token == ""
        assert client._genius is None

    def test_nonempty_token_creates_genius_instance(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="test-token-123")
            mock_cls.assert_called_once_with("test-token-123", timeout=15.0)
            assert client._genius is mock_inst

    def test_default_timeout(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = GeniusClient(api_token="tok")
            mock_cls.assert_called_once_with("tok", timeout=15.0)

    def test_custom_timeout(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = GeniusClient(api_token="tok", timeout=30.0)
            mock_cls.assert_called_once_with("tok", timeout=30.0)

    def test_remove_section_headers_true(self):
        """Genius client strips section headers so the aligner sees only sung text."""
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            GeniusClient(api_token="tok")
            assert mock_inst.remove_section_headers is True

    def test_skip_non_songs_true(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            GeniusClient(api_token="tok")
            assert mock_inst.skip_non_songs is True


# ---------------------------------------------------------------------------
# GeniusClient.search
# ---------------------------------------------------------------------------


class TestGeniusClientSearch:
    """GeniusClient.search() returns [] on failure; filters by type and blocked term."""

    def test_empty_token_returns_empty_list(self):
        client = GeniusClient(api_token="")
        result = client.search("anything")
        assert result == []

    def test_search_returns_filtered_hits(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.return_value = {
                "sections": [
                    {
                        "hits": [
                            {
                                "type": "song",
                                "result": {
                                    "id": 100,
                                    "title": "Never Gonna Give You Up",
                                    "primary_artist": {"name": "Rick Astley"},
                                },
                            },
                            {
                                "type": "artist",
                                "result": {
                                    "id": 200,
                                    "title": "Rick Astley",
                                    "primary_artist": {"name": "Rick Astley"},
                                },
                            },
                            {
                                "type": "song",
                                "result": {
                                    "id": 300,
                                    "title": "Song 2",
                                    "primary_artist": {"name": "Blur"},
                                },
                            },
                        ]
                    }
                ]
            }

            hits = client.search("rick astley")
            assert len(hits) == 2
            assert hits[0].id == 100
            assert hits[0].title == "Never Gonna Give You Up"
            assert hits[0].artist == "Rick Astley"
            assert hits[1].id == 300

    def test_search_drops_translation_artist_when_query_has_genius(self):
        """When the query contains 'genius', drop hits with 'translation' in artist."""
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.return_value = {
                "sections": [
                    {
                        "hits": [
                            {
                                "type": "song",
                                "result": {
                                    "id": 1,
                                    "title": "Song",
                                    "primary_artist": {"name": "Genius English Translations"},
                                },
                            },
                            {
                                "type": "song",
                                "result": {
                                    "id": 2,
                                    "title": "Good Song",
                                    "primary_artist": {"name": "Real Artist"},
                                },
                            },
                        ]
                    }
                ]
            }

            hits = client.search("genius search term")
            assert len(hits) == 1
            assert hits[0].id == 2

    def test_search_drops_genius_artist_when_query_has_no_genius(self):
        """When the query doesn't contain 'genius', drop hits with 'genius' in artist."""
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.return_value = {
                "sections": [
                    {
                        "hits": [
                            {
                                "type": "song",
                                "result": {
                                    "id": 1,
                                    "title": "Lyrics",
                                    "primary_artist": {"name": "Genius"},
                                },
                            },
                            {
                                "type": "song",
                                "result": {
                                    "id": 2,
                                    "title": "Good Song",
                                    "primary_artist": {"name": "Real Artist"},
                                },
                            },
                        ]
                    }
                ]
            }

            hits = client.search("some song")
            assert len(hits) == 1
            assert hits[0].id == 2

    def test_search_respects_limit(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            hits_data = []
            for i in range(20):
                hits_data.append(
                    {
                        "type": "song",
                        "result": {
                            "id": i,
                            "title": f"Song {i}",
                            "primary_artist": {"name": f"Artist {i}"},
                        },
                    }
                )
            mock_inst.search.return_value = {"sections": [{"hits": hits_data}]}

            hits = client.search("query", limit=3)
            assert len(hits) == 3

    def test_search_returns_empty_on_exception(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.side_effect = Exception("network error")
            hits = client.search("query")
            assert hits == []

    def test_search_returns_empty_on_none_response(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.return_value = None
            hits = client.search("query")
            assert hits == []

    def test_search_returns_empty_on_empty_sections(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.return_value = {"sections": []}
            hits = client.search("query")
            assert hits == []

    def test_search_returns_empty_on_malformed_response(self):
        """Review-fix: parse errors on a malformed-but-truthy response honor
        the documented "[] on any failure" contract instead of escaping."""
        malformed = [
            {"sections": [None]},  # null section -> AttributeError
            # song hit with null primary_artist and no artist_names -> AttributeError
            {
                "sections": [
                    {"hits": [{"type": "song", "result": {"primary_artist": {"name": None}}}]}
                ]
            },
            # song hit missing id/title -> KeyError
            {"sections": [{"hits": [{"type": "song", "result": {"artist_names": "X"}}]}]},
        ]
        for payload in malformed:
            with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
                mock_inst = MagicMock()
                mock_cls.return_value = mock_inst
                client = GeniusClient(api_token="tok")
                mock_inst.search.return_value = payload
                assert client.search("query") == [], payload


# ---------------------------------------------------------------------------
# GeniusClient.fetch_lyrics
# ---------------------------------------------------------------------------


class TestGeniusClientFetchLyrics:
    """GeniusClient.fetch_lyrics() raises GeniusUnavailable on failure."""

    def test_empty_token_raises_genius_unavailable(self):
        client = GeniusClient(api_token="")
        with pytest.raises(GeniusUnavailable, match="not configured"):
            client.fetch_lyrics(123)

    def test_fetch_returns_lyrics_text(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_song = MagicMock()
            mock_song.lyrics = "[Verse 1]\nHello world\n[Chorus]\nYeah\n"
            mock_inst.search_song.return_value = mock_song

            text = client.fetch_lyrics(456)
            assert "[Verse 1]" in text
            assert "Hello world" in text

    def test_fetch_raises_on_empty_lyrics(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_song = MagicMock()
            mock_song.lyrics = ""
            mock_inst.search_song.return_value = mock_song

            with pytest.raises(GeniusUnavailable, match="empty lyrics"):
                client.fetch_lyrics(456)

    def test_fetch_raises_on_none_song(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search_song.return_value = None

            with pytest.raises(GeniusUnavailable, match="empty lyrics"):
                client.fetch_lyrics(456)

    def test_fetch_raises_on_exception(self):
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search_song.side_effect = Exception("API error")

            with pytest.raises(GeniusUnavailable, match="fetch failed"):
                client.fetch_lyrics(456)

    def test_fetch_uses_song_id_not_song_name(self):
        """fetch_lyrics must call search_song(song_id=) — the page-scraping path."""
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_song = MagicMock()
            mock_song.lyrics = "lyrics"
            mock_inst.search_song.return_value = mock_song

            client.fetch_lyrics(789)
            mock_inst.search_song.assert_called_once_with(song_id=789)


# ---------------------------------------------------------------------------
# GeniusClient thread safety
# ---------------------------------------------------------------------------


class TestGeniusClientThreadSafety:
    """Search and fetch_lyrics share a threading.Lock."""

    def test_client_has_lock(self):
        client = GeniusClient(api_token="")
        assert isinstance(client._lock, type(threading.Lock()))

    def test_search_acquires_lock(self):
        """Verify search() acquires the lock — confirmed by it not crashing
        when two threads call it concurrently (basic smoke)."""
        with patch("pikaraoke.lib.genius.lyricsgenius.Genius") as mock_cls:
            mock_inst = MagicMock()
            mock_cls.return_value = mock_inst
            client = GeniusClient(api_token="tok")

            mock_inst.search.return_value = {"sections": [{"hits": []}]}

            results = []
            errors = []

            def do_search():
                try:
                    results.append(client.search("test"))
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=do_search) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
            assert len(results) == 5


# ---------------------------------------------------------------------------
# GeniusHit dataclass
# ---------------------------------------------------------------------------


class TestGeniusHit:
    def test_frozen(self):
        hit = GeniusHit(id=1, title="Song", artist="Artist")
        with pytest.raises(AttributeError):
            hit.id = 2

    def test_equality(self):
        a = GeniusHit(id=1, title="Song", artist="Artist")
        b = GeniusHit(id=1, title="Song", artist="Artist")
        assert a == b

    def test_inequality(self):
        a = GeniusHit(id=1, title="Song", artist="Artist")
        b = GeniusHit(id=2, title="Song", artist="Artist")
        assert a != b


# ---------------------------------------------------------------------------
# Sidecar I/O — choices_dir
# ---------------------------------------------------------------------------


class TestChoicesDir:
    @patch("pikaraoke.lib.genius.get_temp_directory", return_value="/tmp/pk")
    def test_returns_path_under_temp(self, mock_gtd):
        d = choices_dir()
        assert d == Path("/tmp/pk") / CHOICES_SUBDIR

    @patch("pikaraoke.lib.genius.get_temp_directory", return_value="/tmp/pk")
    def test_creates_directory(self, mock_gtd, tmp_path):
        with patch("pikaraoke.lib.genius.Path.mkdir") as mock_mkdir:
            choices_dir()
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Sidecar I/O — write_choice / read_choice / delete_choice
# ---------------------------------------------------------------------------


class TestSidecarIO:
    """Round-trip tests for the selection sidecar I/O helpers."""

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_write_and_read_round_trip(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        yt_id = "dQw4w9WgXcQ"
        payload = {"yt_id": yt_id, "genius_id": 4848515, "yt_title": "Rick Astley"}

        path = write_choice(yt_id, payload)
        result = read_choice(yt_id)

        assert result is not None
        assert result["yt_id"] == yt_id
        assert result["genius_id"] == 4848515
        assert result["yt_title"] == "Rick Astley"
        assert path.name == f"{yt_id}.json"

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_write_overwrites_existing(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        yt_id = "abc12345678"

        write_choice(yt_id, {"yt_id": yt_id, "genius_id": 1})
        write_choice(yt_id, {"yt_id": yt_id, "genius_id": 2})

        result = read_choice(yt_id)
        assert result["genius_id"] == 2

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_write_sets_yt_id_if_missing(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        yt_id = "abc12345678"

        write_choice(yt_id, {"genius_id": 99})

        result = read_choice(yt_id)
        assert result["yt_id"] == yt_id

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_read_returns_none_when_absent(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        assert read_choice("nonexistent_id") is None

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_read_returns_none_on_bad_json(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        yt_id = "badjson12345"

        # Write invalid JSON manually
        d = tmp_path / CHOICES_SUBDIR
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{yt_id}.json").write_text("{invalid json", encoding="utf-8")

        assert read_choice(yt_id) is None

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_delete_removes_file(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        yt_id = "todelete12345"

        write_choice(yt_id, {"yt_id": yt_id, "mode": "raw"})
        assert read_choice(yt_id) is not None

        delete_choice(yt_id)
        assert read_choice(yt_id) is None

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_delete_is_idempotent(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        # Deleting a nonexistent file should not raise
        delete_choice("never_existed12")

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_atomic_write_no_partial_on_failure(self, mock_gtd, tmp_path):
        """If the write fails after creating the temp file, read_choice should
        return either the old value (if any) or None — never partial data."""
        mock_gtd.return_value = str(tmp_path)
        yt_id = "atomic1234567"

        # Write a valid initial payload
        write_choice(yt_id, {"yt_id": yt_id, "genius_id": 1})

        # Simulate a write failure: make json.dump raise
        with patch("pikaraoke.lib.genius.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                write_choice(yt_id, {"yt_id": yt_id, "genius_id": 2})

        # The original file must still be intact
        result = read_choice(yt_id)
        assert result is not None
        assert result["genius_id"] == 1

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_raw_mode_payload(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path)
        yt_id = "rawmode1234567"

        write_choice(yt_id, {"yt_id": yt_id, "mode": "raw"})
        result = read_choice(yt_id)

        assert result["mode"] == "raw"
