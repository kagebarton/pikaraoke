"""Unit tests for LyricAlignStage — lyrics loading, single-style ASS, escalation."""

from unittest.mock import MagicMock

import pytest

from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage

# ---------------------------------------------------------------------------
# _load_lyrics
# ---------------------------------------------------------------------------


class TestLoadLyrics:
    """Tests for _load_lyrics returning (display_lines, align_lines)."""

    @pytest.fixture
    def stage(self):
        return LyricAlignStage(
            whisper_worker=MagicMock(),
            config=PipelineConfig(),
        )

    def test_srt_returns_lines(self, stage, tmp_path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello\n"
            "\n2\n00:00:02,000 --> 00:00:03,000\nWorld\n",
            encoding="utf-8",
        )
        display, align = stage._load_lyrics(srt_file)
        assert display == ["Hello", "World"]
        # SRT has no paren-strip distinction — display == align
        assert align == display

    def test_plain_txt(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("Just some lyrics\nNo headers here\n", encoding="utf-8")
        display, align = stage._load_lyrics(txt_file)
        assert display == ["Just some lyrics", "No headers here"]
        assert align == display

    def test_txt_strips_inline_parens_for_align(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("(I can't help) Falling in love\n", encoding="utf-8")
        display, align = stage._load_lyrics(txt_file)
        assert display == ["(I can't help) Falling in love"]
        assert align == ["Falling in love"]

    def test_txt_skips_blank_and_bracket_lines(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse]\n\nFirst line\n[Chorus]\nSecond line\n",
            encoding="utf-8",
        )
        display, align = stage._load_lyrics(txt_file)
        assert display == ["First line", "Second line"]


# ---------------------------------------------------------------------------
# _should_write_srt
# ---------------------------------------------------------------------------


class TestShouldWriteSrt:
    """Skip SRT generation when yt-dlp already provided one."""

    def test_no_existing_srt_returns_true(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        assert LyricAlignStage._should_write_srt(song) is True

    def test_existing_en_srt_returns_false(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.en.srt").write_text("existing")
        assert LyricAlignStage._should_write_srt(song) is False

    def test_existing_plain_srt_returns_false(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.srt").write_text("existing")
        assert LyricAlignStage._should_write_srt(song) is False


# ---------------------------------------------------------------------------
# _generate_ass — single Karaoke style
# ---------------------------------------------------------------------------


class TestGenerateAss:
    @pytest.fixture
    def stage(self):
        return LyricAlignStage(
            whisper_worker=MagicMock(),
            config=PipelineConfig(),
        )

    def test_single_karaoke_style(self, stage):
        line_objects = [
            {
                "text": "Hello",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
            }
        ]
        ass = stage._generate_ass(line_objects)
        assert "Style: Karaoke," in ass
        assert "Dialogue:" in ass
        # No per-speaker or ensemble styles should ever appear.
        assert "Karaoke_" not in ass

    def test_empty_words_line_skipped(self, stage):
        line_objects = [
            {"text": "Empty", "words": []},
            {
                "text": "Real",
                "words": [{"word": "Real", "start": 0.0, "end": 1.0}],
            },
        ]
        ass = stage._generate_ass(line_objects)
        # Only one Dialogue event (the line with words).
        assert ass.count("Dialogue:") == 1


# ---------------------------------------------------------------------------
# Match-method selection + auto escalation
# ---------------------------------------------------------------------------


def _make_stage_and_ctx(tmp_path, *, match_method="auto", fail_ratio=0.0, threshold=0.1):
    from pikaraoke.pipeline.context import StageContext

    cfg = PipelineConfig()
    cfg.match_method = match_method
    cfg.align_failure_escalation = threshold

    worker = MagicMock()
    worker.align_check.return_value = {"fail_ratio": fail_ratio, "result_id": "rid-1"}
    worker.refine_from_cached.return_value = [
        {"word": "hello", "start": 0.0, "end": 1.0},
        {"word": "world", "start": 1.0, "end": 2.0},
    ]
    worker.transcribe_words.return_value = [
        {"word": "hello", "start": 0.0, "end": 1.0},
        {"word": "world", "start": 1.0, "end": 2.0},
    ]

    stage = LyricAlignStage(whisper_worker=worker, config=cfg)

    song_path = tmp_path / "song.mp4"
    song_path.write_bytes(b"")
    vocal_wav = tmp_path / "song.vocals.wav"
    vocal_wav.write_bytes(b"")
    lyrics_path = tmp_path / "song.txt"
    lyrics_path.write_text("hello world\n", encoding="utf-8")

    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    ctx = StageContext(
        song_path=song_path,
        tmp_dir=tmp_dir,
        config=cfg,
        artifacts={"vocal_wav": vocal_wav, "lyrics_path": lyrics_path},
        cancel=None,
    )
    return stage, ctx, worker


class TestMatchMethodEscalation:
    def test_walk_method_uses_align_check_only(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="walk")
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()

    def test_tiling_method_skips_align_entirely(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="tiling")
        stage.run(ctx)
        worker.align_check.assert_not_called()
        worker.refine_from_cached.assert_not_called()
        worker.transcribe_words.assert_called_once()

    def test_auto_below_threshold_keeps_walk(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.05, threshold=0.1
        )
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()

    def test_auto_above_threshold_escalates_to_tiling(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.25, threshold=0.1
        )
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.discard_cached.assert_called_once_with("rid-1")
        worker.refine_from_cached.assert_not_called()
        worker.transcribe_words.assert_called_once()

    def test_auto_discard_failure_doesnt_block_escalation(self, tmp_path):
        # discard_cached can raise if the worker died between check and the
        # discard call. The stage must keep going to the tiling matcher.
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.5, threshold=0.1
        )
        worker.discard_cached.side_effect = RuntimeError("worker died")
        stage.run(ctx)
        worker.transcribe_words.assert_called_once()
