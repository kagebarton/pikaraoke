"""Unit tests for LyricAlignStage — lyrics loading, single-style ASS,
concentration-only routing, and sectional tiling repair."""

from unittest.mock import MagicMock

import pytest

from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import (
    LyricAlignStage,
    _build_repair_ranges,
    _decide_route,
    _splice_range,
    _words_for_window,
)


def _span(line_start, line_end, token_start, token_end, kind="dropped", recovered=False):
    """Minimal loss_spans entry for repair-router tests."""
    return {
        "token_start": token_start,
        "token_end": token_end,
        "line_start": line_start,
        "line_end": line_end,
        "t0": 0.0,
        "t1": 0.0,
        "kind": kind,
        "recovered": recovered,
    }


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
# Repair router — pure helpers
# ---------------------------------------------------------------------------


class TestBuildRepairRanges:
    def test_empty(self):
        assert _build_repair_ranges([], 10) == []

    def test_single_run_over_threshold(self):
        ranges = _build_repair_ranges([_span(3, 4, 10, 22)], 10)
        assert ranges == [{"line_start": 3, "line_end": 4, "failed_tokens": 12}]

    def test_single_run_under_threshold_dropped(self):
        assert _build_repair_ranges([_span(3, 3, 10, 16)], 10) == []

    def test_adjacent_sub_threshold_runs_combine(self):
        # Merge-then-threshold: two 6-token collapses on neighbouring lines
        # combine to 12 >= N and become one repair range.
        spans = [_span(3, 3, 10, 16), _span(4, 4, 16, 22)]
        ranges = _build_repair_ranges(spans, 10)
        assert ranges == [{"line_start": 3, "line_end": 4, "failed_tokens": 12}]

    def test_non_adjacent_runs_stay_separate(self):
        spans = [_span(3, 3, 0, 12), _span(8, 8, 20, 32)]
        ranges = _build_repair_ranges(spans, 10)
        assert len(ranges) == 2
        assert ranges[0]["line_start"] == 3
        assert ranges[1]["line_start"] == 8

    def test_merged_still_under_threshold_dropped(self):
        # Two adjacent 3-token runs → merged 6 < N → no range.
        spans = [_span(3, 3, 0, 3), _span(4, 4, 3, 6)]
        assert _build_repair_ranges(spans, 10) == []


class TestDecideRoute:
    def test_no_ranges_keeps_walk(self):
        route, ranges = _decide_route([_span(3, 3, 0, 6)], 20, 10, 0.5)
        assert route == "keep_walk"
        assert ranges == []

    def test_concentrated_hole_in_healthy_song_repairs(self):
        route, ranges = _decide_route([_span(3, 4, 0, 12)], 20, 10, 0.5)
        assert route == "repair"
        assert len(ranges) == 1

    def test_coverage_over_cap_whole_tiling(self):
        # One range covering 3 of 4 lines → 0.75 > 0.5 → whole-song tiling.
        route, _ranges = _decide_route([_span(0, 2, 0, 12)], 4, 10, 0.5)
        assert route == "whole_tiling"


class TestWordsForWindow:
    def test_inclusive_bounds_with_margin(self):
        words = [{"word": f"w{i}", "start": float(i), "end": i + 0.5} for i in range(5)]
        # t0=1.0, t1=3.0, margin=0.3 → keep starts in [0.7, 3.3] = 1,2,3
        kept = _words_for_window(words, 1.0, 3.0, 0.3)
        assert [w["word"] for w in kept] == ["w1", "w2", "w3"]

    def test_margin_includes_boundary_word(self):
        words = [{"word": "edge", "start": 0.7, "end": 1.0}]
        assert _words_for_window(words, 1.0, 3.0, 0.3) == words


class TestSpliceRange:
    def _walk(self):
        return [
            {"text": f"L{i}", "words": [{"word": f"L{i}", "start": float(i), "end": i + 0.5}]}
            for i in range(5)
        ]

    def test_tiling_found_replaces_walk_missing_keeps_walk(self):
        walk = self._walk()
        repair = [
            {"text": "L1", "line_id": 1, "words": [], "start": 5.0, "end": 6.0},
            {"text": "L3", "line_id": 3, "words": [], "start": 9.0, "end": 10.0},
        ]
        spliced = _splice_range(walk, repair, 1, 3)
        # line 1 → tiling, line 2 → walk kept, line 3 → tiling
        assert [o["text"] for o in spliced] == ["L1", "L2", "L3"]
        assert spliced[0]["start"] == 5.0  # tiling
        assert spliced[1] is walk[2]  # walk object kept verbatim
        assert spliced[1]["line_id"] == 2  # line_id back-filled on kept walk obj
        assert spliced[2]["start"] == 9.0  # tiling

    def test_repeated_line_preserved_sorted_by_start(self):
        walk = self._walk()
        repair = [
            {"text": "L2", "line_id": 2, "words": [], "start": 8.0, "end": 9.0},
            {"text": "L2", "line_id": 2, "words": [], "start": 6.0, "end": 7.0},
        ]
        spliced = _splice_range(walk, repair, 2, 2)
        assert [o["start"] for o in spliced] == [6.0, 8.0]


# ---------------------------------------------------------------------------
# Match-method selection + auto escalation
# ---------------------------------------------------------------------------


def _aligned_words(lyric_tokens, collapse_range=None, step=2.0):
    """One whisper word per lyric token (text matches so the walk pairs 1:1).

    Tokens in ``collapse_range`` (half-open token indices) are crammed onto a
    single timestamp positioned between their neighbours — the stable-ts
    force-placement that the walk demotes as a collapsed run. Everything else
    is spread ``step`` seconds apart at its index.
    """
    words = []
    collapse_time = collapse_range[0] * step if collapse_range else 0.0
    for i, tok in enumerate(lyric_tokens):
        if collapse_range and collapse_range[0] <= i < collapse_range[1]:
            words.append({"word": tok, "start": collapse_time, "end": collapse_time})
        else:
            words.append({"word": tok, "start": i * step, "end": i * step + 0.5})
    return words


def _make_stage_and_ctx(
    tmp_path,
    *,
    match_method="auto",
    lyrics_text="hello world",
    raw_words=None,
    refine_words=None,
    transcribe_words=None,
    fail_ratio=0.0,
):
    from pikaraoke.pipeline.context import StageContext

    cfg = PipelineConfig()
    cfg.match_method = match_method

    default_words = [
        {"word": "hello", "start": 0.0, "end": 1.0},
        {"word": "world", "start": 1.0, "end": 2.0},
    ]
    worker = MagicMock()
    worker.align_check.return_value = {
        "fail_ratio": fail_ratio,
        "result_id": "rid-1",
        "words": default_words if raw_words is None else raw_words,
    }
    worker.refine_from_cached.return_value = default_words if refine_words is None else refine_words
    worker.transcribe_words.return_value = (
        default_words if transcribe_words is None else transcribe_words
    )

    stage = LyricAlignStage(whisper_worker=worker, config=cfg)

    song_path = tmp_path / "song.mp4"
    song_path.write_bytes(b"")
    vocal_wav = tmp_path / "song.vocals.wav"
    vocal_wav.write_bytes(b"")
    lyrics_path = tmp_path / "song.txt"
    lyrics_path.write_text(lyrics_text + "\n", encoding="utf-8")

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


class TestMatchMethodRouting:
    """Concentration-only routing: keep_walk / repair / whole_tiling."""

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

    def test_auto_clean_keeps_walk(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="auto")
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()
        assert ctx.artifacts["lyric_method"] == "none+walk"

    def test_auto_high_fail_ratio_no_longer_escalates(self, tmp_path):
        # fail_ratio is telemetry only now: a clean walk keeps walk even at
        # a fail_ratio that used to trip the old segment-failure gate.
        stage, ctx, worker = _make_stage_and_ctx(tmp_path, match_method="auto", fail_ratio=0.9)
        stage.run(ctx)
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()

    def test_auto_small_collapse_keeps_walk(self, tmp_path):
        # A sub-N collapse (9 < 10 tokens) no longer escalates — walk's
        # interpolation handles it (the dropped collapse_ratio gate).
        tokens = [f"t{i}" for i in range(12)]
        words = _aligned_words(tokens, collapse_range=(2, 11))  # 9-token run
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path,
            match_method="auto",
            lyrics_text=" ".join(tokens),
            raw_words=words,
            refine_words=words,
        )
        stage.run(ctx)
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_not_called()
        worker.discard_cached.assert_not_called()

    def test_auto_concentration_repairs(self, tmp_path):
        # A concentrated 12-token collapse (lines 5-8) in a healthy 20-line
        # song → repair: refine AND transcribe, no discard, method walk+repair.
        tokens = [f"t{i}" for i in range(60)]
        lines = "\n".join(" ".join(tokens[3 * k : 3 * k + 3]) for k in range(20))
        words = _aligned_words(tokens, collapse_range=(15, 27))  # 12 tokens
        # Clean transcribe words for the failed span, inside the audio window
        # (good neighbours: line4 end ~28.5, line9 start = 54.0).
        transcribe = [
            {"word": tokens[i], "start": 30.0 + (i - 15) * 2.0, "end": 30.0 + (i - 15) * 2.0 + 0.5}
            for i in range(15, 27)
        ]
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path,
            match_method="auto",
            lyrics_text=lines,
            raw_words=words,
            refine_words=words,
            transcribe_words=transcribe,
        )
        stage.run(ctx)
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()
        worker.transcribe_words.assert_called_once()
        worker.discard_cached.assert_not_called()
        assert ctx.artifacts["lyric_method"] == "none+walk+repair"

    def test_auto_pervasive_loss_whole_tiling(self, tmp_path):
        # A collapse covering 3 of 4 lines (> repair_max_line_fraction) →
        # whole-song tiling: discard align, transcribe, no refine.
        tokens = [f"t{i}" for i in range(16)]
        lines = "\n".join(" ".join(tokens[4 * k : 4 * k + 4]) for k in range(4))
        words = _aligned_words(tokens, collapse_range=(4, 14))  # 10 tokens, lines 1-3
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path,
            match_method="auto",
            lyrics_text=lines,
            raw_words=words,
            transcribe_words=_aligned_words(tokens),
        )
        stage.run(ctx)
        worker.discard_cached.assert_called_once_with("rid-1")
        worker.refine_from_cached.assert_not_called()
        worker.transcribe_words.assert_called_once()
        assert ctx.artifacts["lyric_method"] == "none+tiling"

    def test_auto_whole_tiling_discard_failure_survives(self, tmp_path):
        # discard_cached can raise if the worker died between check and the
        # discard. whole-song tiling must still proceed.
        tokens = [f"t{i}" for i in range(16)]
        lines = "\n".join(" ".join(tokens[4 * k : 4 * k + 4]) for k in range(4))
        words = _aligned_words(tokens, collapse_range=(4, 14))
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path,
            match_method="auto",
            lyrics_text=lines,
            raw_words=words,
            transcribe_words=_aligned_words(tokens),
        )
        worker.discard_cached.side_effect = RuntimeError("worker died")
        stage.run(ctx)
        worker.transcribe_words.assert_called_once()


class TestRepairSpans:
    """_repair_spans: keep walk's good lines, adopt tiling timing per span."""

    @pytest.fixture
    def stage(self):
        return LyricAlignStage(whisper_worker=MagicMock(), config=PipelineConfig())

    @staticmethod
    def _walk_obj(text, start):
        toks = text.split()
        words = [
            {"word": w, "start": start + i * 0.1, "end": start + i * 0.1 + 0.1}
            for i, w in enumerate(toks)
        ]
        return {"text": text, "words": words, "start": start, "end": words[-1]["end"]}

    def _line_objects(self):
        # Lines 2-3 are "smeared" (real but bunched at ~5s); 0,1,4,5 good.
        return [
            self._walk_obj("a b", 0.0),
            self._walk_obj("c d", 1.0),
            self._walk_obj("e f", 5.0),
            self._walk_obj("g h", 5.05),
            self._walk_obj("i j", 8.0),
            self._walk_obj("k l", 9.0),
        ]

    def test_adopts_tiling_timing_keeps_good_walk_lines(self, stage):
        lines = ["a b", "c d", "e f", "g h", "i j", "k l"]
        walk = self._line_objects()
        ranges = [{"line_start": 2, "line_end": 3, "failed_tokens": 4}]
        # Clean window words for lines 2-3 at their true (spread) times.
        transcribe = [
            {"word": "e", "start": 3.0, "end": 3.4},
            {"word": "f", "start": 3.5, "end": 3.9},
            {"word": "g", "start": 4.0, "end": 4.4},
            {"word": "h", "start": 4.5, "end": 4.9},
        ]
        result, meta = stage._repair_spans(walk, ranges, transcribe, lines, list(lines))
        assert [o["text"] for o in result] == ["a b", "c d", "e f", "g h", "i j", "k l"]
        # Good walk lines kept verbatim (object identity).
        assert result[0] is walk[0]
        assert result[1] is walk[1]
        assert result[4] is walk[4]
        assert result[5] is walk[5]
        # Repaired lines adopt tiling's spread timing, not the bunched ~5s.
        assert result[2]["start"] == 3.0
        assert result[3]["start"] == 4.0
        assert meta[0]["lines_repaired"] == 2
        assert meta[0]["lines_kept_from_walk"] == 0
        assert meta[0]["window_word_count"] == 4

    def test_line_tiling_misses_keeps_walk(self, stage):
        # Window words only cover line 2; line 3 finds nothing → walk kept,
        # never dropped.
        lines = ["a b", "c d", "e f", "g h", "i j", "k l"]
        walk = self._line_objects()
        ranges = [{"line_start": 2, "line_end": 3, "failed_tokens": 4}]
        transcribe = [
            {"word": "e", "start": 3.0, "end": 3.4},
            {"word": "f", "start": 3.5, "end": 3.9},
        ]
        result, meta = stage._repair_spans(walk, ranges, transcribe, lines, list(lines))
        assert result[2]["start"] == 3.0  # line 2 repaired
        assert result[3] is walk[3]  # line 3 kept from walk
        assert meta[0]["lines_repaired"] == 1
        assert meta[0]["lines_kept_from_walk"] == 1

    def test_empty_window_keeps_whole_range(self, stage):
        lines = ["a b", "c d", "e f", "g h", "i j", "k l"]
        walk = self._line_objects()
        ranges = [{"line_start": 2, "line_end": 3, "failed_tokens": 4}]
        result, meta = stage._repair_spans(walk, ranges, [], lines, list(lines))
        assert result[2] is walk[2]
        assert result[3] is walk[3]
        assert meta[0]["lines_repaired"] == 0
        assert meta[0]["lines_kept_from_walk"] == 2
