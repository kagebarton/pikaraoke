"""Unit tests for pikaraoke.pipeline.stages.lyrics_fetch — LyricsFetchStage."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib import lrclib
from pikaraoke.lib.genius import (
    GeniusClient,
    GeniusSong,
    GeniusUnavailable,
    delete_choice,
    read_choice,
    write_choice,
)
from pikaraoke.pipeline.context import StageContext
from pikaraoke.pipeline.stages.lyrics_fetch import LyricsFetchStage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    song_path: Path,
    tmp_dir: Path,
    artifacts: dict | None = None,
) -> StageContext:
    """Create a minimal StageContext for testing."""
    from pikaraoke.pipeline.config import PipelineConfig

    return StageContext(
        song_path=song_path,
        tmp_dir=tmp_dir,
        config=PipelineConfig(),
        artifacts=artifacts if artifacts is not None else {},
    )


# ---------------------------------------------------------------------------
# _extract_yt_id
# ---------------------------------------------------------------------------


class TestExtractYtId:
    def test_pikaraoke_format(self):
        result = LyricsFetchStage._extract_yt_id(Path("/songs/Artist - Song---dQw4w9WgXcQ.mp4"))
        assert result == "dQw4w9WgXcQ"

    def test_ytdlp_bracket_format(self):
        result = LyricsFetchStage._extract_yt_id(Path("/songs/Artist - Song [dQw4w9WgXcQ].mp4"))
        assert result == "dQw4w9WgXcQ"

    def test_no_id_returns_none(self):
        result = LyricsFetchStage._extract_yt_id(Path("/songs/Just A Song.mp4"))
        assert result is None


# ---------------------------------------------------------------------------
# _find_srt
# ---------------------------------------------------------------------------


class TestFindSrt:
    def test_prefers_en_srt(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
        (subs / "Song---abc123.srt").write_text("fallback")

        result = LyricsFetchStage._find_srt(song)
        assert result == subs / "Song---abc123.en.srt"

    def test_falls_back_to_plain_srt(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        result = LyricsFetchStage._find_srt(song)
        assert result == subs / "Song---abc123.srt"

    def test_returns_none_when_no_srt(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        result = LyricsFetchStage._find_srt(song)
        assert result is None

    def test_returns_none_when_subtitles_dir_missing(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        result = LyricsFetchStage._find_srt(song)
        assert result is None


# ---------------------------------------------------------------------------
# Branch (a): Genius selection
# ---------------------------------------------------------------------------


class TestBranchAGeniusSelection:
    """Genius selection → fetch lyrics → write lyrics.txt → set artifacts."""

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_genius_selection_sets_lyrics_path(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        genius.fetch_song.return_value = GeniusSong(
            text="[Verse 1]\nHello world\n", title="Hello", artist="World"
        )

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        # Write a choice file
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        ctx.config.joint_lrclib_prior = False  # isolate the Genius branch
        ctx.config.joint_ytasr_prior = False  # (no prior fetch in this test)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] == job_tmp / "lyrics.txt"
        assert ctx.artifacts["lyrics_origin"] == "genius"
        assert (job_tmp / "lyrics.txt").read_text() == "[Verse 1]\nHello world\n"

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_genius_selection_stashes_identity(self, mock_gtd, tmp_path):
        """The chosen Genius id/title/artist is stashed for the debug bundle."""
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        genius.fetch_song.return_value = GeniusSong(text="lyrics", title="Hello", artist="World")

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        ctx.config.joint_lrclib_prior = False  # isolate the Genius branch
        ctx.config.joint_ytasr_prior = False  # (no prior fetch in this test)
        LyricsFetchStage(genius).run(ctx)

        assert ctx.artifacts["genius"] == {"id": 456, "title": "Hello", "artist": "World"}

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_genius_selection_deletes_choice_on_success(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        genius.fetch_song.return_value = GeniusSong(text="lyrics", title="t", artist="a")

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        ctx.config.joint_lrclib_prior = False  # isolate the Genius branch
        ctx.config.joint_ytasr_prior = False  # (no prior fetch in this test)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        # Choice file should be deleted
        assert read_choice("dQw4w9WgXcQ") is None

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_genius_failure_falls_through_to_srt(self, mock_gtd, tmp_path):
        """Genius fetch failure → falls through to SRT fallback, preserves choice."""
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        genius.fetch_song.side_effect = GeniusUnavailable("API error")

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        # Create an SRT file
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---dQw4w9WgXcQ.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_origin"] == "srt"
        # Choice file preserved for retry
        assert read_choice("dQw4w9WgXcQ") is not None

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_genius_failure_no_srt_sets_none(self, mock_gtd, tmp_path):
        """Genius failure + no SRT → lyrics_path = None, origin = 'none'."""
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        genius.fetch_song.side_effect = GeniusUnavailable("API error")

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] is None
        assert ctx.artifacts["lyrics_origin"] == "none"


# ---------------------------------------------------------------------------
# Branch (a): LRCLIB timing prior (joint_lrclib_prior)
# ---------------------------------------------------------------------------


class TestBranchALrclibPrior:
    """Genius branch: LRCLIB timing-prior fetch + persist."""

    _LYRICS = "Hello world\nGoodbye world\n"
    _SYNCED = "[00:01.00]Hello world\n[00:05.00]Goodbye world\n"

    @pytest.fixture(autouse=True)
    def _no_ytasr(self):
        # These synthetic songs have no YouTube ASR caption; the YTASR prior
        # (now tried first) finds nothing and falls through to LRCLIB. Stub the
        # download so the fall-through is deterministic and never hits the
        # network.
        with patch(
            "pikaraoke.pipeline.stages.lyrics_fetch.youtube_dl.download_auto_en_subs",
            return_value=None,
        ):
            yield

    def _genius(self, title="Hello World (Live)", artist="The Band"):
        g = MagicMock(spec=GeniusClient)
        g.fetch_song.return_value = GeniusSong(text=self._LYRICS, title=title, artist=artist)
        return g

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=200.0)
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search")
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_writes_lrc_and_stashes_reference(self, mock_gtd, mock_search, _probe, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)
        mock_search.return_value = [
            {
                "id": 99,
                "trackName": "Hello World",
                "artistName": "The Band",
                "albumName": "Greetings",
                "duration": 200.0,
                "syncedLyrics": self._SYNCED,
            }
        ]
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        LyricsFetchStage(self._genius()).run(ctx)

        lrc_path = song_path.parent / "lyrics" / "Song---dQw4w9WgXcQ.lrc"
        assert lrc_path.is_file()
        ref = ctx.artifacts["lrclib"]
        assert ref["lrc_file"] == "lyrics/Song---dQw4w9WgXcQ.lrc"
        assert ref["record"]["id"] == 99
        # query key was cleaned: the "(Live)" qualifier is stripped.
        assert ref["query"] == {"track_name": "Hello World", "artist_name": "The Band"}
        assert ctx.artifacts["media_duration_s"] == 200.0

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=None)
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search")
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_reuses_existing_lrc_without_query(self, mock_gtd, mock_search, _probe, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()
        lrc_path = song_path.parent / "lyrics" / "Song---dQw4w9WgXcQ.lrc"
        lrclib.write_lrc(
            lrc_path,
            {"id": 7, "trackName": "T", "artistName": "A", "syncedLyrics": self._SYNCED},
        )
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        LyricsFetchStage(self._genius()).run(ctx)

        mock_search.assert_not_called()
        ref = ctx.artifacts["lrclib"]
        assert ref["query"] is None
        assert ref["record"]["id"] == 7

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=None)
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search", return_value=[])
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_no_candidate_stashes_nothing(self, mock_gtd, _search, _probe, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        LyricsFetchStage(self._genius()).run(ctx)

        assert "lrclib" not in ctx.artifacts
        assert ctx.artifacts["lyrics_origin"] == "genius"

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=None)
    @patch(
        "pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search",
        side_effect=RuntimeError("boom"),
    )
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_fetch_failure_never_fails_stage(self, mock_gtd, _search, _probe, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        LyricsFetchStage(self._genius()).run(ctx)  # must not raise

        assert "lrclib" not in ctx.artifacts
        assert ctx.artifacts["lyrics_origin"] == "genius"


# ---------------------------------------------------------------------------
# Branch (a): YouTube ASR timing prior (joint_ytasr_prior), preferred over LRCLIB
# ---------------------------------------------------------------------------


class TestBranchAYtasrPrior:
    """Genius branch: YouTube ASR caption adopted over LRCLIB when usable."""

    _LYRICS = "hello world again\ngoodbye world\n"
    # Real ASR: per-word tOffsetMs (word-seg fraction 0.6).
    _ASR_WORD = json.dumps(
        {
            "events": [
                {
                    "tStartMs": 1000,
                    "segs": [
                        {"utf8": "hello"},
                        {"utf8": " world", "tOffsetMs": 300},
                        {"utf8": " again", "tOffsetMs": 600},
                    ],
                },
                {
                    "tStartMs": 3000,
                    "segs": [{"utf8": "goodbye"}, {"utf8": " world", "tOffsetMs": 400}],
                },
            ]
        }
    )
    # Manual-mirrored / line-level: no per-word offsets (fraction 0).
    _ASR_LINE = json.dumps(
        {"events": [{"tStartMs": 1000, "segs": [{"utf8": "hello world again goodbye world"}]}]}
    )
    _SYNCED = "[00:01.00]hello world again\n[00:05.00]goodbye world\n"

    def _genius(self, title="Hello", artist="World"):
        g = MagicMock(spec=GeniusClient)
        g.fetch_song.return_value = GeniusSong(text=self._LYRICS, title=title, artist=artist)
        return g

    def _run(self, tmp_path, mock_gtd):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})
        ctx = _make_ctx(song_path, job_tmp)
        return song_path, ctx

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.youtube_dl.download_auto_en_subs")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=10.0)
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_reuses_on_disk_asr_and_skips_lrclib(
        self, mock_gtd, _probe, mock_search, mock_dl, tmp_path
    ):
        song_path, ctx = self._run(tmp_path, mock_gtd)
        asr_path = song_path.parent / "subtitles" / "Song---dQw4w9WgXcQ.en.asr.json3"
        asr_path.parent.mkdir(parents=True, exist_ok=True)
        asr_path.write_text(self._ASR_WORD, encoding="utf-8")

        LyricsFetchStage(self._genius()).run(ctx)

        ref = ctx.artifacts["ytasr"]
        assert ref["asr_file"] == "subtitles/Song---dQw4w9WgXcQ.en.asr.json3"
        assert ref["n_words"] == 5
        assert ref["wpm"] == 30.0  # 5 words / (10s / 60)
        # Adopted ASR means no download and no LRCLIB query.
        mock_dl.assert_not_called()
        mock_search.assert_not_called()
        assert "lrclib" not in ctx.artifacts

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.youtube_dl.download_auto_en_subs")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=10.0)
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_downloads_when_absent(self, mock_gtd, _probe, mock_search, mock_dl, tmp_path):
        song_path, ctx = self._run(tmp_path, mock_gtd)
        asr_path = song_path.parent / "subtitles" / "Song---dQw4w9WgXcQ.en.asr.json3"

        def fake_dl(url, dest_dir, stem):
            asr_path.parent.mkdir(parents=True, exist_ok=True)
            asr_path.write_text(self._ASR_WORD, encoding="utf-8")
            return str(asr_path)

        mock_dl.side_effect = fake_dl

        LyricsFetchStage(self._genius()).run(ctx)

        mock_dl.assert_called_once()
        assert "ytasr" in ctx.artifacts
        mock_search.assert_not_called()

    @patch("pikaraoke.pipeline.stages.lyrics_fetch.youtube_dl.download_auto_en_subs")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=200.0)
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_line_level_asr_falls_back_to_lrclib(
        self, mock_gtd, _probe, mock_search, mock_dl, tmp_path
    ):
        mock_search.return_value = [
            {"id": 9, "trackName": "Hello", "artistName": "World", "syncedLyrics": self._SYNCED}
        ]
        song_path, ctx = self._run(tmp_path, mock_gtd)
        asr_path = song_path.parent / "subtitles" / "Song---dQw4w9WgXcQ.en.asr.json3"
        asr_path.parent.mkdir(parents=True, exist_ok=True)
        asr_path.write_text(self._ASR_LINE, encoding="utf-8")

        LyricsFetchStage(self._genius()).run(ctx)

        # Line-level track rejected -> LRCLIB adopted instead.
        assert "ytasr" not in ctx.artifacts
        assert ctx.artifacts["lrclib"]["record"]["id"] == 9
        mock_dl.assert_not_called()  # the on-disk file was present, just unusable

    @patch(
        "pikaraoke.pipeline.stages.lyrics_fetch.youtube_dl.download_auto_en_subs",
        return_value=None,
    )
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search")
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=200.0)
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_absent_asr_falls_back_to_lrclib(self, mock_gtd, _probe, mock_search, _dl, tmp_path):
        mock_search.return_value = [
            {"id": 9, "trackName": "Hello", "artistName": "World", "syncedLyrics": self._SYNCED}
        ]
        _song_path, ctx = self._run(tmp_path, mock_gtd)

        LyricsFetchStage(self._genius()).run(ctx)

        assert "ytasr" not in ctx.artifacts
        assert ctx.artifacts["lrclib"]["record"]["id"] == 9

    @patch(
        "pikaraoke.pipeline.stages.lyrics_fetch.youtube_dl.download_auto_en_subs",
        side_effect=RuntimeError("boom"),
    )
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.lrclib.search", return_value=[])
    @patch("pikaraoke.pipeline.stages.lyrics_fetch.probe_duration", return_value=200.0)
    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_ytasr_failure_never_fails_stage(self, mock_gtd, _probe, _search, _dl, tmp_path):
        _song_path, ctx = self._run(tmp_path, mock_gtd)

        LyricsFetchStage(self._genius()).run(ctx)  # must not raise

        assert "ytasr" not in ctx.artifacts
        assert ctx.artifacts["lyrics_origin"] == "genius"


# ---------------------------------------------------------------------------
# Branch (b): raw mode selection
# ---------------------------------------------------------------------------


class TestBranchBRawSelection:
    """Raw mode → lyrics_path = None, origin = 'none'."""

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_raw_mode_sets_none(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "mode": "raw"})

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] is None
        assert ctx.artifacts["lyrics_origin"] == "none"

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_raw_mode_deletes_choice(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "mode": "raw"})

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert read_choice("dQw4w9WgXcQ") is None


# ---------------------------------------------------------------------------
# Branch (c): SRT fallback (no choice file)
# ---------------------------------------------------------------------------


class TestBranchCSrtFallback:
    """No choice file → look for SRT → or fall through to transcription."""

    def test_srt_exists_sets_path(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---dQw4w9WgXcQ.en.srt").write_text("srt content")

        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] == subs / "Song---dQw4w9WgXcQ.en.srt"
        assert ctx.artifacts["lyrics_origin"] == "srt"

    def test_no_srt_sets_none(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] is None
        assert ctx.artifacts["lyrics_origin"] == "none"

    def test_plain_srt_fallback(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---abc1234567.mp4"
        song_path.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc1234567.srt").write_text("srt content")

        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] == subs / "Song---abc1234567.srt"
        assert ctx.artifacts["lyrics_origin"] == "srt"


# ---------------------------------------------------------------------------
# Short-circuit: test override (DD5)
# ---------------------------------------------------------------------------


class TestShortCircuitOverride:
    """When ctx.artifacts['lyrics_path'] is pre-populated (not None), stage
    must short-circuit and NOT override (Design Decision 5)."""

    def test_pre_populated_lyrics_path_is_respected(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---abc1234567.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        override_path = Path("/override/lyrics.txt")
        ctx = _make_ctx(song_path, job_tmp, artifacts={"lyrics_path": override_path})

        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] == override_path
        assert ctx.artifacts["lyrics_origin"] == "override"
        # Genius client should NOT have been called
        genius.fetch_song.assert_not_called()

    def test_none_lyrics_path_is_not_short_circuit(self, tmp_path):
        """orchestrator sets lyrics_path=None before stage runs — must NOT
        short-circuit (DD5: check 'is not None', not 'in')."""
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song---abc1234567.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(song_path, job_tmp, artifacts={"lyrics_path": None})

        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        # Should proceed to branch (c) — SRT fallback
        assert "lyrics_origin" in ctx.artifacts

    def test_override_without_existing_origin_gets_default(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(song_path, job_tmp, artifacts={"lyrics_path": Path("/x.txt")})
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_origin"] == "override"

    def test_override_with_existing_origin_preserves_it(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "Song.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(
            song_path,
            job_tmp,
            artifacts={"lyrics_path": Path("/x.txt"), "lyrics_origin": "test"},
        )
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_origin"] == "test"


# ---------------------------------------------------------------------------
# No YouTube ID in filename
# ---------------------------------------------------------------------------


class TestNoYouTubeId:
    """Manually-added library files with no yt_id → no choice lookup."""

    def test_no_yt_id_goes_to_srt_fallback(self, tmp_path):
        genius = MagicMock(spec=GeniusClient)
        song_path = tmp_path / "My Song.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] is None
        assert ctx.artifacts["lyrics_origin"] == "none"
