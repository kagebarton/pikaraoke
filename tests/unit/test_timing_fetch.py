"""Unit tests for pikaraoke.lib.timing_fetch — synced-timing fetch pillar."""

import json
from unittest.mock import MagicMock, patch

from pikaraoke.lib import timing_fetch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resp(status_code: int, body: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = {"message": {"header": {"status_code": status_code}, "body": body}}
    return r


def _search_body(*tracks: dict) -> dict:
    return {"track_list": [{"track": t} for t in tracks]}


def _track(track_id=1, name="Song", artist="Artist", length=200, has_richsync=True, **kw):
    return {
        "track_id": track_id,
        "track_name": name,
        "artist_name": artist,
        "track_length": length,
        "has_subtitles": True,
        "has_richsync": has_richsync,
        "instrumental": False,
        **kw,
    }


def _richsync_body(entries: list[dict]) -> dict:
    return {"richsync": {"richsync_body": json.dumps(entries)}}


def _subtitle_body(lrc_text: str) -> dict:
    return {"subtitle": {"subtitle_body": lrc_text}}


# ---------------------------------------------------------------------------
# _mm_get
# ---------------------------------------------------------------------------


class TestMmGet:
    def test_200_returns_body(self):
        client = MagicMock()
        client._get.return_value = _resp(200, {"x": 1})
        result = timing_fetch._mm_get(client, "track.search", [("q", "x")])
        assert result == {"message": {"header": {"status_code": 200}, "body": {"x": 1}}}

    def test_404_returns_none_no_retry(self):
        client = MagicMock()
        client._get.return_value = _resp(404, {})
        result = timing_fetch._mm_get(client, "track.search", [("q", "x")])
        assert result is None
        assert client._get.call_count == 1

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.TOKEN_PATH")
    def test_401_backs_off_and_retries_once(self, mock_token_path, _sleep):
        client = MagicMock()
        client.token = "stale"
        client._get.side_effect = [_resp(401, {}), _resp(200, {"ok": True})]
        result = timing_fetch._mm_get(client, "track.search", [("q", "x")])
        assert result == {"message": {"header": {"status_code": 200}, "body": {"ok": True}}}
        assert client._get.call_count == 2
        assert client.token is None
        mock_token_path.unlink.assert_called_once_with(missing_ok=True)


# ---------------------------------------------------------------------------
# candidate_lyrics
# ---------------------------------------------------------------------------


class TestCandidateLyrics:
    @patch("pikaraoke.lib.timing_fetch._mm_get")
    def test_richsync_present_returns_word_kind(self, mock_get):
        entries = [{"ts": 0.0, "te": 1.0, "l": [{"c": "hi", "o": 0.0}]}]
        mock_get.return_value = {"message": {"body": _richsync_body(entries)}}
        kind, body = timing_fetch.candidate_lyrics(MagicMock(), 1)
        assert kind == "word"
        assert body == entries

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch._mm_get")
    def test_richsync_absent_falls_to_subtitle(self, mock_get, _sleep):
        mock_get.side_effect = [
            {"message": {"body": {}}},
            {"message": {"body": _subtitle_body("[00:01.00]hi\n")}},
        ]
        kind, body = timing_fetch.candidate_lyrics(MagicMock(), 1)
        assert kind == "line"
        assert body == "[00:01.00]hi\n"

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch._mm_get")
    def test_neither_returns_none_kind(self, mock_get, _sleep):
        mock_get.side_effect = [None, None]
        kind, body = timing_fetch.candidate_lyrics(MagicMock(), 1)
        assert kind == "none"
        assert body is None


# ---------------------------------------------------------------------------
# best_by_reference
# ---------------------------------------------------------------------------


class TestBestByReference:
    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.candidate_lyrics")
    @patch("pikaraoke.lib.timing_fetch._mm_get")
    def test_skips_instrumental_and_no_lyrics_candidates(self, mock_get, mock_cand, _sleep):
        mock_get.return_value = {
            "message": {
                "body": _search_body(
                    _track(track_id=1, instrumental=True),
                    _track(track_id=2, has_subtitles=False, has_richsync=False),
                    _track(track_id=3),
                )
            }
        }
        mock_cand.return_value = ("line", "[00:01.00]hi there\n")
        row = timing_fetch.best_by_reference(MagicMock(), "term", ["hi there"], 200.0)
        assert row is not None
        assert row["track_id"] == 3
        mock_cand.assert_called_once_with(mock_cand.call_args[0][0], 3)

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.candidate_lyrics")
    @patch("pikaraoke.lib.timing_fetch._mm_get")
    def test_picks_best_map_rate_then_duration(self, mock_get, mock_cand, _sleep):
        mock_get.return_value = {
            "message": {
                "body": _search_body(
                    _track(track_id=1, length=100),
                    _track(track_id=2, length=200),
                )
            }
        }
        # track 1: weak match; track 2: perfect match, exact duration.
        mock_cand.side_effect = [
            ("line", "[00:01.00]nothing matches\n"),
            ("line", "[00:01.00]hi there\n"),
        ]
        row = timing_fetch.best_by_reference(MagicMock(), "term", ["hi there"], 200.0)
        assert row["track_id"] == 2
        assert row["map_rate"] == 1.0

    @patch("pikaraoke.lib.timing_fetch._mm_get")
    def test_no_search_results_returns_none(self, mock_get):
        mock_get.return_value = None
        assert timing_fetch.best_by_reference(MagicMock(), "term", ["hi"], None) is None


# ---------------------------------------------------------------------------
# reference_pick — the title-only retry gate
# ---------------------------------------------------------------------------


class TestReferencePick:
    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.best_by_reference")
    def test_confident_full_query_skips_title_only(self, mock_best, _sleep):
        mock_best.return_value = {
            "track_id": 1,
            "track_name": "t",
            "artist_name": "a",
            "track_length": 200,
            "kind": "line",
            "body": "x",
            "map_rate": 0.9,
        }
        result = timing_fetch.reference_pick(MagicMock(), "Song", "Artist", ["hi"], 200.0)
        assert result["variant"] == "full"
        assert mock_best.call_count == 1  # title-only never called

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.best_by_reference")
    def test_unconfident_full_query_tries_title_only(self, mock_best, _sleep):
        full_row = {
            "track_id": 1,
            "track_name": "t",
            "artist_name": "a",
            "track_length": 200,
            "kind": "line",
            "body": "x",
            "map_rate": 0.2,
        }
        title_row = {**full_row, "track_id": 2, "map_rate": 0.8}
        mock_best.side_effect = [full_row, title_row]
        result = timing_fetch.reference_pick(MagicMock(), "Song", "Artist", ["hi"], 200.0)
        assert result["variant"] == "title-only"
        assert result["map_rate"] == 0.8
        assert mock_best.call_count == 2

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.best_by_reference")
    def test_title_only_worse_keeps_full(self, mock_best, _sleep):
        full_row = {
            "track_id": 1,
            "track_name": "t",
            "artist_name": "a",
            "track_length": 200,
            "kind": "line",
            "body": "x",
            "map_rate": 0.3,
        }
        title_row = {**full_row, "track_id": 2, "map_rate": 0.1}
        mock_best.side_effect = [full_row, title_row]
        result = timing_fetch.reference_pick(MagicMock(), "Song", "Artist", ["hi"], 200.0)
        assert result["variant"] == "full"
        assert result["map_rate"] == 0.3

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.best_by_reference")
    def test_empty_artist_never_retries_title_only(self, mock_best, _sleep):
        mock_best.return_value = None
        result = timing_fetch.reference_pick(MagicMock(), "Song", "", ["hi"], 200.0)
        assert result is None
        assert mock_best.call_count == 1

    @patch("pikaraoke.lib.timing_fetch.time.sleep")
    @patch("pikaraoke.lib.timing_fetch.best_by_reference")
    def test_nothing_found_returns_none(self, mock_best, _sleep):
        mock_best.return_value = None
        result = timing_fetch.reference_pick(MagicMock(), "Song", "Artist", ["hi"], 200.0)
        assert result is None


# ---------------------------------------------------------------------------
# NetEase trigger
# ---------------------------------------------------------------------------


class TestNeteaseFallback:
    @patch("pikaraoke.lib.timing_fetch.syncedlyrics.search")
    def test_returns_line_kind_on_hit(self, mock_search):
        mock_search.return_value = "[00:01.00]hi there\n"
        row = timing_fetch._netease_fallback("term", ["hi there"])
        assert row["kind"] == "line"
        assert row["variant"] == "netease"
        assert row["map_rate"] == 1.0

    @patch("pikaraoke.lib.timing_fetch.syncedlyrics.search")
    def test_no_hit_returns_none(self, mock_search):
        mock_search.return_value = None
        assert timing_fetch._netease_fallback("term", ["hi"]) is None

    @patch("pikaraoke.lib.timing_fetch.syncedlyrics.search")
    @patch("pikaraoke.lib.timing_fetch.reference_pick")
    def test_fetch_builds_sidecar_only_when_musixmatch_empty_or_zero(self, mock_pick, mock_search):
        # Musixmatch found something non-zero: NetEase must not be consulted.
        mock_pick.return_value = {
            "track_id": 1,
            "track_name": "t",
            "artist_name": "a",
            "track_length": 200,
            "kind": "line",
            "body": "[00:01.00]hi\n",
            "map_rate": 0.3,
            "term": "Song Artist",
            "variant": "full",
        }
        sidecar = timing_fetch._fetch_and_build_sidecar("Song", "Artist", ["hi"], 200.0)
        assert sidecar["source"] == "musixmatch"
        mock_search.assert_not_called()


# ---------------------------------------------------------------------------
# ensure_timing — disk-first, corrupt-sidecar refetch, never-raises
# ---------------------------------------------------------------------------


class TestEnsureTiming:
    def _sidecar_path(self, song_path):
        return song_path.parent / "lyrics" / f"{song_path.stem}.timing.json"

    def test_existing_confident_sidecar_skips_fetch(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        path = self._sidecar_path(song_path)
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                    "query": {"term": "Song Artist", "variant": "full"},
                    "source": "musixmatch",
                    "kind": "word",
                    "map_rate": 0.9,
                    "track": {"track_id": 1},
                    "body": [{"ts": 0.0, "te": 1.0, "l": []}],
                }
            ),
            encoding="utf-8",
        )
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            result = timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        mock_fetch.assert_not_called()
        assert result == {
            "kind": "word",
            "path": path,
            "source": "musixmatch",
            "map_rate": 0.9,
            "track": {"track_id": 1},
        }

    def test_existing_none_sidecar_skips_refetch_and_returns_none(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        path = self._sidecar_path(song_path)
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                    "query": {"term": "Song Artist", "variant": "full"},
                    "source": "none",
                    "kind": "none",
                    "map_rate": 0.0,
                    "track": {},
                    "body": None,
                }
            ),
            encoding="utf-8",
        )
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            result = timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        mock_fetch.assert_not_called()
        assert result is None

    def test_corrupt_sidecar_triggers_refetch_and_overwrite(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        path = self._sidecar_path(song_path)
        path.parent.mkdir()
        path.write_text("{ not valid json", encoding="utf-8")
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            mock_fetch.return_value = {
                "schema_version": 1,
                "fetched_at": "x",
                "query": {"term": "Song Artist", "variant": "full"},
                "source": "musixmatch",
                "kind": "line",
                "map_rate": 0.9,
                "track": {},
                "body": "[00:01.00]hi\n",
            }
            result = timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        mock_fetch.assert_called_once()
        assert result["kind"] == "line"
        assert json.loads(path.read_text(encoding="utf-8"))["source"] == "musixmatch"

    def test_missing_schema_version_treated_as_corrupt(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        path = self._sidecar_path(song_path)
        path.parent.mkdir()
        path.write_text(json.dumps({"kind": "line", "map_rate": 0.9}), encoding="utf-8")
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            mock_fetch.return_value = timing_fetch._empty_sidecar("Song Artist")
            timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        mock_fetch.assert_called_once()

    def test_miss_still_writes_none_sidecar(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            mock_fetch.return_value = timing_fetch._empty_sidecar("Song Artist")
            result = timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        assert result is None
        path = self._sidecar_path(song_path)
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8"))["kind"] == "none"

    def test_low_confidence_pick_persisted_but_not_stashed(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            mock_fetch.return_value = {
                "schema_version": 1,
                "fetched_at": "x",
                "query": {"term": "Song Artist", "variant": "full"},
                "source": "musixmatch",
                "kind": "line",
                "map_rate": 0.2,
                "track": {},
                "body": "[00:01.00]hi\n",
            }
            result = timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        assert result is None
        path = self._sidecar_path(song_path)
        assert json.loads(path.read_text(encoding="utf-8"))["map_rate"] == 0.2

    def test_never_raises_on_fetch_exception(self, tmp_path):
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        with patch("pikaraoke.lib.timing_fetch._fetch_and_build_sidecar") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("network exploded")
            result = timing_fetch.ensure_timing(song_path, "Song", "Artist", ["hi"], 200.0)
        assert result is None
        path = self._sidecar_path(song_path)
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8"))["kind"] == "none"
