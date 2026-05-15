"""Unit tests for LyricAlignStage — Genius header parsing, walk matching, and multi-speaker ASS.

These tests cover the _load_lyrics, _should_write_srt, speaker assignment,
and multi-speaker ASS generation introduced by the Genius integration plan.
"""

from unittest.mock import MagicMock

import pytest

from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import (
    LyricAlignStage,
    _assign_speakers_from_genius,
    _dominant_speaker_presence,
    _safe_style_name,
)

# ---------------------------------------------------------------------------
# _load_lyrics — Genius header parsing (3-tuple return)
# ---------------------------------------------------------------------------


class TestLoadLyrics:
    """Tests for _load_lyrics returning (text, format, structure)."""

    @pytest.fixture
    def stage(self):
        """Create a LyricAlignStage with mocked worker and config."""
        from unittest.mock import MagicMock

        from pikaraoke.pipeline.config import PipelineConfig

        return LyricAlignStage(
            whisper_worker=MagicMock(),
            config=PipelineConfig(),
        )

    def test_srt_returns_srt_format_no_structure(self, stage, tmp_path):
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello\n" "2\n00:00:02,000 --> 00:00:03,000\nWorld\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(srt_file)
        assert fmt == "srt"
        assert structure is None
        assert "Hello" in text
        assert "World" in text

    def test_plain_txt_no_headers(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("Just some lyrics\nNo headers here\n", encoding="utf-8")

        text, fmt, structure = stage._load_lyrics(txt_file)
        assert fmt == "txt"
        assert structure is None
        assert "Just some lyrics" in text

    def test_genius_txt_with_headers(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse 1: Brian]\nHello world\n[Chorus]\nSing along\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(txt_file)

        assert fmt == "txt"
        assert structure is not None
        assert len(structure) == 2

        # text uses align_text (inline parens stripped)
        assert "Hello world" in text
        assert "Sing along" in text

        # structure has section info
        assert structure[0]["section"] == "Verse 1"
        assert structure[0]["speaker_label"] == "Brian"
        assert structure[1]["section"] == "Chorus"
        assert structure[1]["is_ensemble"] is True

    def test_genius_txt_strips_headers_from_text(self, stage, tmp_path):
        """Section header lines must NOT appear in the returned text."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse 1]\nFirst line\n[Chorus]\nSecond line\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(txt_file)
        assert "[Verse 1]" not in text
        assert "[Chorus]" not in text
        assert "First line" in text
        assert "Second line" in text

    def test_genius_txt_uses_align_text(self, stage, tmp_path):
        """align_text (inline parens stripped) is used for alignment text."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse]\n(I can't help) Falling in love\n",
            encoding="utf-8",
        )

        text, fmt, structure = stage._load_lyrics(txt_file)

        # text (for alignment) should use align_text with parens stripped
        assert "Falling in love" in text
        # structure preserves full text with parens
        assert structure[0]["text"] == "(I can't help) Falling in love"
        assert structure[0]["align_text"] == "Falling in love"

    def test_genius_txt_empty_after_parsing(self, stage, tmp_path):
        """Genius txt where all lines are header-only falls back to plain txt."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("[Verse 1]\n[Chorus]\n", encoding="utf-8")

        text, fmt, structure = stage._load_lyrics(txt_file)
        # parse_genius_sections returns [], so the heuristic falls through
        # to the plain .txt branch
        assert fmt == "txt"
        assert structure is None


# ---------------------------------------------------------------------------
# _should_write_srt — conditional SRT write
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

    def test_en_srt_takes_priority(self, tmp_path):
        song = tmp_path / "Song---abc123.mp4"
        song.touch()
        subs = tmp_path / "subtitles"
        subs.mkdir()
        (subs / "Song---abc123.en.srt").write_text("en")
        (subs / "Song---abc123.srt").write_text("plain")

        # Either existing SRT prevents writing
        assert LyricAlignStage._should_write_srt(song) is False


# ---------------------------------------------------------------------------
# Speaker assignment
# ---------------------------------------------------------------------------


class TestAssignSpeakersFromGenius:
    def test_assigns_speaker_and_dominant(self):
        line_objects = [
            {"text": "hello", "words": [{"word": "hello", "speaker": None}]},
        ]
        genius_lines = [
            {"speaker_label": "Brian", "dominant_speaker": "Brian"},
        ]
        _assign_speakers_from_genius(line_objects, genius_lines)
        assert line_objects[0]["speaker"] == "Brian"
        assert line_objects[0]["dominant_speaker"] == "Brian"
        assert line_objects[0]["words"][0]["speaker"] == "Brian"
        assert line_objects[0]["words"][0]["dominant_speaker"] == "Brian"

    def test_assigns_duet(self):
        line_objects = [
            {"text": "hello", "words": [{"word": "hello"}]},
            {"text": "world", "words": [{"word": "world"}]},
        ]
        genius_lines = [
            {"speaker_label": "Brian & AJ", "dominant_speaker": "Brian"},
            {"speaker_label": "Nick", "dominant_speaker": "Nick"},
        ]
        _assign_speakers_from_genius(line_objects, genius_lines)
        assert line_objects[0]["speaker"] == "Brian & AJ"
        assert line_objects[0]["dominant_speaker"] == "Brian"
        assert line_objects[1]["speaker"] == "Nick"
        assert line_objects[1]["dominant_speaker"] == "Nick"


class TestAssignSpeakersZipsSilently:
    def test_more_line_objects_than_genius_lines(self):
        """Extra line_objects past the genius_lines list stay unlabeled."""
        line_objects = [
            {"text": "a", "words": [{"word": "a"}]},
            {"text": "b", "words": [{"word": "b"}]},
            {"text": "c", "words": [{"word": "c"}]},
        ]
        genius_lines = [
            {"speaker_label": "Brian", "dominant_speaker": "Brian"},
            {"speaker_label": "AJ", "dominant_speaker": "AJ"},
        ]
        # Should not raise
        _assign_speakers_from_genius(line_objects, genius_lines)
        assert line_objects[0]["speaker"] == "Brian"
        assert line_objects[1]["speaker"] == "AJ"
        # Third line never received a speaker key
        assert "speaker" not in line_objects[2]


class TestAssignSpeakersByLineId:
    """Tiling-style line_objects carry a line_id back-reference into the
    original genius_lines because tiling can drop, repeat, or split lines.
    Speaker assignment must follow the back-reference, not the positional
    index.
    """

    def test_line_id_overrides_positional_index(self):
        # 3 line_objects from a 5-line lyric: object 0 maps to line 0,
        # object 1 and 2 both map to line 4 (repeated chorus).
        line_objects = [
            {"text": "verse", "line_id": 0, "words": [{"word": "verse"}]},
            {"text": "chorus", "line_id": 4, "words": [{"word": "chorus"}]},
            {"text": "chorus", "line_id": 4, "words": [{"word": "chorus"}]},
        ]
        genius_lines = [
            {"speaker_label": "A", "dominant_speaker": "A"},
            {"speaker_label": "B", "dominant_speaker": "B"},
            {"speaker_label": "C", "dominant_speaker": "C"},
            {"speaker_label": "D", "dominant_speaker": "D"},
            {"speaker_label": "E", "dominant_speaker": "E"},
        ]
        _assign_speakers_from_genius(line_objects, genius_lines)
        assert line_objects[0]["speaker"] == "A"
        assert line_objects[1]["speaker"] == "E"
        assert line_objects[2]["speaker"] == "E"
        assert line_objects[2]["words"][0]["speaker"] == "E"


class TestDominantSpeakerPresence:
    def test_single_speaker(self):
        line_objects = [{"dominant_speaker": "Brian"}]
        present, has_ensemble = _dominant_speaker_presence(line_objects)
        assert present == ["Brian"]
        assert has_ensemble is False

    def test_ensemble(self):
        line_objects = [{"speaker": None}]
        present, has_ensemble = _dominant_speaker_presence(line_objects)
        assert present == []
        assert has_ensemble is True

    def test_first_appearance_order(self):
        line_objects = [
            {"dominant_speaker": "AJ"},
            {"dominant_speaker": "Brian"},
            {"dominant_speaker": "AJ"},
        ]
        present, has_ensemble = _dominant_speaker_presence(line_objects)
        assert present == ["AJ", "Brian"]
        assert has_ensemble is False


class TestSafeStyleName:
    def test_collapses_runs_of_unsafe_chars(self):
        # " & " (three non-word chars) collapses to one underscore
        assert _safe_style_name("Brian & AJ") == "Brian_AJ"

    def test_leaves_safe_chars(self):
        assert _safe_style_name("Brian") == "Brian"
        assert _safe_style_name("Kevin_AJ") == "Kevin_AJ"

    def test_strips_leading_and_trailing_underscores(self):
        assert _safe_style_name(" Brian ") == "Brian"
        assert _safe_style_name("!Brian!") == "Brian"


# ---------------------------------------------------------------------------
# Multi-speaker ASS generation
# ---------------------------------------------------------------------------


class TestGenerateAss:
    """Tests for _generate_ass with multi-speaker styles."""

    @pytest.fixture
    def stage(self):
        return LyricAlignStage(
            whisper_worker=MagicMock(),
            config=PipelineConfig(),
        )

    def test_single_speaker_style(self, stage):
        # Plain .txt files: line_objects from the walk matcher don't have
        # speaker/dominant_speaker keys at all
        line_objects = [
            {
                "text": "Hello",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
            }
        ]
        ass = stage._generate_ass(line_objects)
        assert "Style: Karaoke," in ass
        assert "Dialogue:" in ass

    def test_multi_speaker_styles(self, stage):
        line_objects = [
            {
                "text": "Brian's line",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
                "speaker": "Brian",
                "dominant_speaker": "Brian",
            },
            {
                "text": "AJ's line",
                "words": [{"word": "World", "start": 1.0, "end": 2.0}],
                "speaker": "AJ",
                "dominant_speaker": "AJ",
            },
        ]
        ass = stage._generate_ass(line_objects)
        assert "Style: Karaoke_Brian," in ass
        assert "Style: Karaoke_AJ," in ass
        assert "Karaoke_Brian,,0,0,0,," in ass or "Karaoke_AJ,,0,0,0,," in ass

    def test_ensemble_emits_ensemble_style(self, stage):
        # An explicit speaker=None line triggers Karaoke_ensemble
        line_objects = [
            {
                "text": "Brian's line",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
                "speaker": "Brian",
                "dominant_speaker": "Brian",
            },
            {
                "text": "All together",
                "words": [{"word": "Together", "start": 1.0, "end": 2.0}],
                "speaker": None,
                "dominant_speaker": None,
            },
        ]
        ass = stage._generate_ass(line_objects)
        assert "Style: Karaoke_Brian," in ass
        assert "Style: Karaoke_ensemble," in ass

    def test_solo_genius_emits_single_karaoke_style(self, stage):
        """A Genius song where genius_singer_mode == 'solo' goes through
        the same code path as plain .txt — line_objects have no speaker
        keys, so _generate_ass picks the single 'Karaoke' style.
        """
        line_objects = [
            {
                "text": "Hello",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
            },
            {
                "text": "World",
                "words": [{"word": "World", "start": 1.0, "end": 2.0}],
            },
        ]
        ass = stage._generate_ass(line_objects)
        assert "Style: Karaoke," in ass
        # Multi/ensemble styles must not appear
        assert "Karaoke_ensemble" not in ass
        assert "Style: Karaoke_" not in ass

    def test_no_inline_speaker_labels_in_dialogue_text(self, stage):
        """Speaker info goes to Style assignment only — never into the
        rendered Dialogue text.
        """
        line_objects = [
            {
                "text": "Brian's line",
                "words": [{"word": "Hello", "start": 0.0, "end": 1.0}],
                "speaker": "Brian",
                "dominant_speaker": "Brian",
            },
            {
                "text": "AJ's line",
                "words": [{"word": "World", "start": 1.0, "end": 2.0}],
                "speaker": "AJ",
                "dominant_speaker": "AJ",
            },
        ]
        ass = stage._generate_ass(line_objects)
        for line in ass.splitlines():
            if not line.startswith("Dialogue:"):
                continue
            # The text after the 9th comma is the karaoke text. Speaker
            # names must never appear there.
            karaoke_text = line.split(",", 9)[-1]
            assert "Brian" not in karaoke_text
            assert "AJ" not in karaoke_text


# ---------------------------------------------------------------------------
# Match-method selection + auto escalation
# ---------------------------------------------------------------------------


class TestMatchMethodEscalation:
    """LyricAlignStage chooses walk vs tiling based on cfg.match_method and
    the ratio reported by align_check.
    """

    def _make_stage_and_ctx(self, tmp_path, match_method="auto", fail_ratio=0.0, threshold=0.1):
        from pikaraoke.pipeline.context import StageContext

        cfg = PipelineConfig()
        cfg.match_method = match_method
        cfg.align_failure_escalation = threshold

        worker = MagicMock()
        # align_check always returns the canned ratio and a synthetic id.
        worker.align_check.return_value = {
            "fail_ratio": fail_ratio,
            "result_id": "rid-1",
        }
        worker.refine_from_cached.return_value = [
            {"word": "hello", "start": 0.0, "end": 1.0, "speaker": None, "dominant_speaker": None},
            {"word": "world", "start": 1.0, "end": 2.0, "speaker": None, "dominant_speaker": None},
        ]
        worker.transcribe_words.return_value = [
            {"word": "hello", "start": 0.0, "end": 1.0, "speaker": None, "dominant_speaker": None},
            {"word": "world", "start": 1.0, "end": 2.0, "speaker": None, "dominant_speaker": None},
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

    def test_walk_method_uses_align_check_only(self, tmp_path):
        stage, ctx, worker = self._make_stage_and_ctx(tmp_path, match_method="walk")
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()

    def test_tiling_method_skips_align_entirely(self, tmp_path):
        stage, ctx, worker = self._make_stage_and_ctx(tmp_path, match_method="tiling")
        stage.run(ctx)
        worker.align_check.assert_not_called()
        worker.refine_from_cached.assert_not_called()
        worker.transcribe_words.assert_called_once()

    def test_auto_below_threshold_keeps_walk(self, tmp_path):
        stage, ctx, worker = self._make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.05, threshold=0.1
        )
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()

    def test_auto_above_threshold_escalates_to_tiling(self, tmp_path):
        stage, ctx, worker = self._make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.25, threshold=0.1
        )
        stage.run(ctx)
        worker.align_check.assert_called_once()
        # Escalation: discard the cached result; do NOT refine; transcribe instead.
        worker.discard_cached.assert_called_once_with("rid-1")
        worker.refine_from_cached.assert_not_called()
        worker.transcribe_words.assert_called_once()

    def test_auto_discard_failure_doesnt_block_escalation(self, tmp_path):
        # discard_cached can raise if the worker died between check and the
        # discard call. The stage must keep going to the tiling matcher.
        stage, ctx, worker = self._make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.5, threshold=0.1
        )
        worker.discard_cached.side_effect = RuntimeError("worker died")
        stage.run(ctx)
        worker.transcribe_words.assert_called_once()
