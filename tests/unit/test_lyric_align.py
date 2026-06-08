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

    def test_srt_cleanup_strips_noise(self, stage, tmp_path):
        """SRT route runs each sub through clean_srt_line: musical
        notes, HTML tags, bracketed/paren stage directions, and 2-line
        wraps all vanish; entries that become empty are dropped."""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\n(gentle music)\n"
            "\n2\n00:00:02,000 --> 00:00:03,000\n<i>♪ Hello\nworld ♪</i>\n"
            "\n3\n00:00:03,000 --> 00:00:04,000\n[together]\n♪ Beauty and the beast ♪\n",
            encoding="utf-8",
        )
        display, align = stage._load_lyrics(srt_file)
        assert display == ["Hello world", "Beauty and the beast"]
        assert align == display

    def test_plain_txt(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("Just some lyrics\nNo headers here\n", encoding="utf-8")
        display, align = stage._load_lyrics(txt_file)
        assert display == ["Just some lyrics", "No headers here"]
        assert align == display

    def test_txt_keeps_inline_paren_contents_for_align(self, stage, tmp_path):
        """Bracket chars stripped from align text, but enclosed words
        kept — those backing vocals are sung in the audio."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("(I can't help) Falling in love\n", encoding="utf-8")
        display, align = stage._load_lyrics(txt_file)
        assert display == ["(I can't help) Falling in love"]
        assert align == ["I can't help Falling in love"]

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
    worker.align_check.return_value = {
        "fail_ratio": fail_ratio,
        "result_id": "rid-1",
        "words": [
            {"word": "hello", "start": 0.0, "end": 1.0},
            {"word": "world", "start": 1.0, "end": 2.0},
        ],
    }
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

    def test_auto_escalates_on_collapse_ratio_alone(self, tmp_path):
        # Catches the Pocahontas failure mode: fail_ratio is well below
        # the segment-level threshold but stable-ts force-placed a long
        # run of tokens at one timestamp. Collapse-ratio gate should fire.
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path, match_method="auto", fail_ratio=0.05, threshold=0.1
        )
        # 12 lyric tokens, first 9 raw whisper words crammed at t=0 →
        # walk demotes them as one collapsed run → 9/12 = 75% > default
        # collapse threshold 0.15. fail_ratio 0.05 stays below 0.1.
        lyric_words = [f"w{i}" for i in range(12)]
        ctx.artifacts["lyrics_path"].write_text(" ".join(lyric_words) + "\n", encoding="utf-8")
        collapsed = [{"word": w, "start": 0.0, "end": 0.0} for w in lyric_words[:9]]
        spread = [
            {"word": w, "start": 10.0 + i, "end": 10.0 + i + 0.5}
            for i, w in enumerate(lyric_words[9:])
        ]
        worker.align_check.return_value = {
            "fail_ratio": 0.05,
            "result_id": "rid-1",
            "words": collapsed + spread,
        }
        stage.run(ctx)
        worker.discard_cached.assert_called_once_with("rid-1")
        worker.refine_from_cached.assert_not_called()
        worker.transcribe_words.assert_called_once()


class TestJointRoute:
    """match_method='joint' runs align + refine + transcribe(refine=False) →
    joint matcher; no escalation, no gating."""

    def test_joint_calls_all_three_with_refine_false_on_transcribe(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="joint")
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_called_once()
        # transcribe runs with refine=False under joint — saves a whole-song
        # refine pass we don't use on transcribe-won lines.
        call = worker.transcribe_words.call_args
        assert call.kwargs.get("refine") is False
        # No escalation/discard on the joint path.
        worker.discard_cached.assert_not_called()

    def test_joint_clean_song_lines_use_align_timings(self, tmp_path):
        # Align and transcribe agree everywhere → align wins on ties →
        # per-word timings should be the align ones (exactly the input).
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="joint")
        # The fixture's align_words and transcribe_words already match
        # the lyrics ("hello world") at [0-1, 1-2].
        stage.run(ctx)
        ass_path = ctx.song_path.parent / "karaoke" / f"{ctx.song_path.stem}.ass"
        assert ass_path.exists()

    def test_joint_misplaced_long_line_goes_to_transcribe(self, tmp_path):
        # Align places the lyrics at a wrong time; transcribe finds them at
        # the correct sung time. Joint matcher should adopt transcribe's
        # placement for the misplaced line.
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="joint")

        # Long line so the transcribe_match outscores the joint_alpha prior:
        # 8 tokens of lyrics. Align maps them all to 3-9s (wrong audio).
        # Transcribe finds the matching content at 15-19s.
        lyric_words = ["no", "worries", "for", "the", "rest", "of", "your", "days"]
        ctx.artifacts["lyrics_path"].write_text(" ".join(lyric_words) + "\n", encoding="utf-8")
        worker.align_check.return_value = {
            "fail_ratio": 0.0,
            "result_id": "rid-1",
            "words": [
                {"word": w, "start": 3.0 + i * 0.5, "end": 3.0 + i * 0.5 + 0.4}
                for i, w in enumerate(lyric_words)
            ],
        }
        worker.refine_from_cached.return_value = [
            {"word": w, "start": 3.0 + i * 0.5, "end": 3.0 + i * 0.5 + 0.4}
            for i, w in enumerate(lyric_words)
        ]
        # Transcribe heard the line correctly at 15-19s plus some noise at 3-9s.
        noise = [
            {"word": w, "start": 3.0 + i, "end": 3.5 + i}
            for i, w in enumerate(["zzz", "qqq", "vvv", "xxx", "yyy", "ttt"])
        ]
        sung = [
            {"word": w, "start": 15.0 + i * 0.5, "end": 15.0 + i * 0.5 + 0.4}
            for i, w in enumerate(lyric_words)
        ]
        worker.transcribe_words.return_value = noise + sung

        stage.run(ctx)
        ass_path = ctx.song_path.parent / "karaoke" / f"{ctx.song_path.stem}.ass"
        assert ass_path.exists()
        ass_text = ass_path.read_text(encoding="utf-8")
        # The dialogue line should be timed near 15s, not 3s — assert no
        # event starts in [3, 9].
        dialogue = [line for line in ass_text.splitlines() if line.startswith("Dialogue:")]
        assert len(dialogue) == 1
        # Dialogue: 0,H:MM:SS.cc,H:MM:SS.cc,...
        start_str = dialogue[0].split(",", 2)[1]
        h, m, s = start_str.split(":")
        start_secs = int(h) * 3600 + int(m) * 60 + float(s)
        assert start_secs >= 14.0, f"expected start near 15s; got {start_secs}"
