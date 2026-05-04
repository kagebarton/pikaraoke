"""Unit tests for pikaraoke.pipeline.stages.lyrics_fetch — LyricsFetchStage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.lib.genius import GeniusClient, GeniusUnavailable, delete_choice, read_choice, write_choice
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
        result = LyricsFetchStage._extract_yt_id(
            Path("/songs/Artist - Song---dQw4w9WgXcQ.mp4")
        )
        assert result == "dQw4w9WgXcQ"

    def test_ytdlp_bracket_format(self):
        result = LyricsFetchStage._extract_yt_id(
            Path("/songs/Artist - Song [dQw4w9WgXcQ].mp4")
        )
        assert result == "dQw4w9WgXcQ"

    def test_no_id_returns_none(self):
        result = LyricsFetchStage._extract_yt_id(
            Path("/songs/Just A Song.mp4")
        )
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
        genius.fetch_lyrics.return_value = "[Verse 1]\nHello world\n"

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        # Write a choice file
        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
        stage = LyricsFetchStage(genius)
        stage.run(ctx)

        assert ctx.artifacts["lyrics_path"] == job_tmp / "lyrics.txt"
        assert ctx.artifacts["lyrics_origin"] == "genius"
        assert (job_tmp / "lyrics.txt").read_text() == "[Verse 1]\nHello world\n"

    @patch("pikaraoke.lib.genius.get_temp_directory")
    def test_genius_selection_deletes_choice_on_success(self, mock_gtd, tmp_path):
        mock_gtd.return_value = str(tmp_path / "temp")
        (tmp_path / "temp" / "lyric_choices").mkdir(parents=True, exist_ok=True)

        genius = MagicMock(spec=GeniusClient)
        genius.fetch_lyrics.return_value = "lyrics"

        song_path = tmp_path / "Song---dQw4w9WgXcQ.mp4"
        song_path.touch()
        job_tmp = tmp_path / "job_tmp"
        job_tmp.mkdir()

        write_choice("dQw4w9WgXcQ", {"yt_id": "dQw4w9WgXcQ", "genius_id": 456})

        ctx = _make_ctx(song_path, job_tmp)
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
        genius.fetch_lyrics.side_effect = GeniusUnavailable("API error")

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
        genius.fetch_lyrics.side_effect = GeniusUnavailable("API error")

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
        genius.fetch_lyrics.assert_not_called()

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
