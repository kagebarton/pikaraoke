"""Unit tests for LyricAlignStage — lyrics loading, single-style ASS, joint route."""

import json
from unittest.mock import MagicMock

import pytest

from pikaraoke.lib import lrclib
from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.stages.lyric_align import LyricAlignStage

# ---------------------------------------------------------------------------
# _load_lyrics
# ---------------------------------------------------------------------------


class TestLoadLyrics:
    """Tests for _load_lyrics returning (display_lines, align_lines, cue_spans)."""

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
        display, align, cues = stage._load_lyrics(srt_file)
        assert display == ["Hello", "World"]
        # SRT has no paren-strip distinction — display == align
        assert align == display
        assert cues == [(1.0, 2.0), (2.0, 3.0)]

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
        display, align, cues = stage._load_lyrics(srt_file)
        assert display == ["Hello world", "Beauty and the beast"]
        assert align == display
        # Cue spans stay parallel to the *kept* lines: the dropped
        # (gentle music) entry takes its timing with it.
        assert cues == [(2.0, 3.0), (3.0, 4.0)]

    def test_plain_txt(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("Just some lyrics\nNo headers here\n", encoding="utf-8")
        display, align, cues = stage._load_lyrics(txt_file)
        assert display == ["Just some lyrics", "No headers here"]
        assert align == display
        assert cues is None

    def test_txt_keeps_inline_paren_contents_for_align(self, stage, tmp_path):
        """Bracket chars stripped from align text, but enclosed words
        kept — those backing vocals are sung in the audio."""
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text("(I can't help) Falling in love\n", encoding="utf-8")
        display, align, cues = stage._load_lyrics(txt_file)
        assert display == ["(I can't help) Falling in love"]
        assert align == ["I can't help Falling in love"]
        assert cues is None

    def test_txt_skips_blank_and_bracket_lines(self, stage, tmp_path):
        txt_file = tmp_path / "lyrics.txt"
        txt_file.write_text(
            "[Verse]\n\nFirst line\n[Chorus]\nSecond line\n",
            encoding="utf-8",
        )
        display, align, cues = stage._load_lyrics(txt_file)
        assert display == ["First line", "Second line"]
        assert cues is None


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
# Joint alignment route
# ---------------------------------------------------------------------------


def _make_stage_and_ctx(tmp_path, *, dereverb_yield_wpm=0.0):
    from pikaraoke.pipeline.context import StageContext

    cfg = PipelineConfig()
    # Off by default so the de-reverb gate never trips on fixtures with
    # tiny word counts; TestDereverbRetry opts in explicitly.
    cfg.dereverb_yield_wpm = dereverb_yield_wpm

    worker = MagicMock()
    worker.align_check.return_value = {
        "fail_ratio": 0.0,
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

    stage = LyricAlignStage(whisper_worker=worker, config=cfg, stem_worker=MagicMock())

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


class TestJointRoute:
    """Alignment mode runs align + refine + transcribe(refine=False) →
    joint matcher; no escalation, no gating."""

    def test_joint_calls_all_three_with_refine_false_on_transcribe(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(tmp_path)
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
        stage, ctx, worker = _make_stage_and_ctx(tmp_path)
        # The fixture's align_words and transcribe_words already match
        # the lyrics ("hello world") at [0-1, 1-2].
        stage.run(ctx)
        ass_path = ctx.song_path.parent / "karaoke" / f"{ctx.song_path.stem}.ass"
        assert ass_path.exists()

    def test_joint_misplaced_long_line_goes_to_transcribe(self, tmp_path):
        # Align places the lyrics at a wrong time; transcribe finds them at
        # the correct sung time. Joint matcher should adopt transcribe's
        # placement for the misplaced line.
        stage, ctx, worker = _make_stage_and_ctx(tmp_path)

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


# ---------------------------------------------------------------------------
# Windowed re-align second pass (joint route)
# ---------------------------------------------------------------------------


class TestWindowedRealign:
    """Orchestration of the second pass: gating, slice calls, merge,
    per-span error degradation. Merge/anchor semantics themselves are
    covered in tests/unit/test_windowed_realign.py."""

    LINE0 = "glowing river twilight ember"
    LINE1 = "phantom of the lost parade"

    def _make(self, tmp_path, monkeypatch):
        import pikaraoke.pipeline.stages.lyric_align as la_mod

        stage, ctx, worker = _make_stage_and_ctx(tmp_path)
        ctx.artifacts["lyrics_path"].write_text(f"{self.LINE0}\n{self.LINE1}\n", encoding="utf-8")

        def _words(specs):
            return [{"word": w, "start": s, "end": e} for w, s, e in specs]

        line0_words = _words(
            [
                ("glowing", 10.0, 10.4),
                ("river", 10.6, 10.9),
                ("twilight", 11.0, 11.4),
                ("ember", 11.5, 12.0),
            ]
        )
        line1_wrong = _words(
            [
                ("phantom", 20.0, 20.3),
                ("of", 20.4, 20.5),
                ("the", 20.6, 20.7),
                ("lost", 20.8, 21.2),
                ("parade", 21.4, 22.0),
            ]
        )
        # Slice words are slice-relative; the span starts at the anchor's
        # start minus pad: 10.0 - 0.75 = 9.25. Line 1 lands at 25-27 absolute.
        slice_words = _words(
            [
                ("glowing", 0.75, 1.15),
                ("river", 1.35, 1.65),
                ("twilight", 1.75, 2.15),
                ("ember", 2.25, 2.75),
                ("phantom", 15.75, 16.05),
                ("of", 16.15, 16.25),
                ("the", 16.35, 16.45),
                ("lost", 16.55, 16.95),
                ("parade", 17.15, 17.75),
            ]
        )

        worker.align_check.side_effect = [
            {"fail_ratio": 0.0, "result_id": "rid-1", "words": line0_words + line1_wrong},
            {"fail_ratio": 0.0, "result_id": "rid-2", "words": slice_words},
        ]
        worker.refine_from_cached.side_effect = [line0_words + line1_wrong, slice_words]
        # Transcribe echoes only line 0 — line 1 is uncorroborated (suspect).
        worker.transcribe_words.return_value = list(line0_words)

        ffmpeg_calls = []
        monkeypatch.setattr(
            la_mod, "run_ffmpeg", lambda cmd, _ctx, _phase: ffmpeg_calls.append(cmd)
        )
        monkeypatch.setattr(la_mod, "_wav_duration", lambda _p: 30.0)
        return stage, ctx, worker, ffmpeg_calls

    @staticmethod
    def _ass_start_seconds(ctx) -> list[float]:
        ass_path = ctx.song_path.parent / "karaoke" / f"{ctx.song_path.stem}.ass"
        starts = []
        for line in ass_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Dialogue:"):
                h, m, s = line.split(",", 2)[1].split(":")
                starts.append(int(h) * 3600 + int(m) * 60 + float(s))
        return starts

    def test_suspect_span_is_sliced_realigned_and_merged(self, tmp_path, monkeypatch):
        stage, ctx, worker, ffmpeg_calls = self._make(tmp_path, monkeypatch)
        stage.run(ctx)

        # Second align ran on the span slice with the span's lyric lines.
        assert worker.align_check.call_count == 2
        span_call = worker.align_check.call_args_list[1]
        assert span_call.kwargs["lyrics_text"] == f"{self.LINE0}\n{self.LINE1}"
        assert worker.refine_from_cached.call_count == 2
        cmd = ffmpeg_calls[0]
        assert cmd[cmd.index("-ss") + 1] == "9.250"
        assert cmd[cmd.index("-to") + 1] == "30.000"

        # Line 1's pass-1 placement (20s) was replaced by the slice
        # re-align (25s absolute); line 0 kept its anchor timing. ASS
        # timestamps truncate to centiseconds, hence the tolerance.
        starts = self._ass_start_seconds(ctx)
        lead_in = stage._config.line_lead_in_cs / 100.0
        assert starts == pytest.approx([10.0 - lead_in, 25.0 - lead_in], abs=0.011)

    def test_span_failure_keeps_pass1_placement(self, tmp_path, monkeypatch):
        stage, ctx, worker, _ = self._make(tmp_path, monkeypatch)
        pass1_check = next(iter(worker.align_check.side_effect))
        worker.align_check.side_effect = [
            pass1_check,
            RuntimeError("refine blew up on a degenerate slice"),
        ]
        stage.run(ctx)

        starts = self._ass_start_seconds(ctx)
        lead_in = stage._config.line_lead_in_cs / 100.0
        assert starts == pytest.approx([10.0 - lead_in, 20.0 - lead_in], abs=0.011)

    def test_no_suspects_skips_second_pass_entirely(self, tmp_path, monkeypatch):
        import pikaraoke.pipeline.stages.lyric_align as la_mod

        stage, ctx, worker = _make_stage_and_ctx(tmp_path)

        def _boom(_p):
            raise AssertionError("duration probe must not run when nothing is suspect")

        monkeypatch.setattr(la_mod, "_wav_duration", _boom)
        stage.run(ctx)
        # Fixture lyrics are fully transcribe-corroborated: one align pass only.
        worker.align_check.assert_called_once()
        worker.refine_from_cached.assert_called_once()

    def test_no_anchors_skips_second_pass(self, tmp_path, monkeypatch):
        # All lines suspect but nothing trustworthy to pin spans on:
        # the lone full-song span would just repeat pass-1, so skip.
        stage, ctx, worker, ffmpeg_calls = self._make(tmp_path, monkeypatch)
        worker.transcribe_words.return_value = []
        stage.run(ctx)
        worker.align_check.assert_called_once()
        assert ffmpeg_calls == []

    def test_hook_failure_keeps_pass1_for_the_song(self, tmp_path, monkeypatch):
        import pikaraoke.pipeline.stages.lyric_align as la_mod

        stage, ctx, worker, _ = self._make(tmp_path, monkeypatch)

        def _broken(_p):
            raise RuntimeError("corrupt WAV header")

        monkeypatch.setattr(la_mod, "_wav_duration", _broken)
        stage.run(ctx)  # must not raise

        starts = self._ass_start_seconds(ctx)
        lead_in = stage._config.line_lead_in_cs / 100.0
        assert starts == pytest.approx([10.0 - lead_in, 20.0 - lead_in], abs=0.011)


# ---------------------------------------------------------------------------
# De-reverb retry gate (joint route)
# ---------------------------------------------------------------------------


class TestDereverbRetry:
    """Low transcribe yield → de-reverb the stem via the stem worker and
    re-run the whisper legs on the dry stem; any retry failure keeps the
    wet-stem results."""

    def _make(self, tmp_path, monkeypatch, *, duration_s=60.0):
        import pikaraoke.pipeline.stages.lyric_align as la_mod

        # Fixture transcribe returns 2 words; over 60 s that is 2 wpm
        # (gate trips at 30), over 1 s it is 120 wpm (gate passes).
        stage, ctx, worker = _make_stage_and_ctx(
            tmp_path, dereverb_yield_wpm=30.0
        )
        monkeypatch.setattr(la_mod, "_wav_duration", lambda _p: duration_s)
        return stage, ctx, worker, stage._stem_worker

    def test_low_yield_reruns_whisper_legs_on_dry_stem(self, tmp_path, monkeypatch):
        stage, ctx, worker, stem_worker = self._make(tmp_path, monkeypatch)
        dry = ctx.tmp_dir / "vocal_(Noreverb)_dereverb.wav"
        tail = ctx.tmp_dir / "vocal_(Reverb)_dereverb.wav"
        stem_worker.separate.return_value = (dry, tail)

        stage.run(ctx)

        stem_worker.separate.assert_called_once()
        sep_kwargs = stem_worker.separate.call_args.kwargs
        assert sep_kwargs["model_name"] == stage._config.dereverb_model_name
        assert sep_kwargs["wav_path"] == ctx.artifacts["vocal_wav"]
        # Both whisper legs ran twice: wet pass, then dry retry.
        assert worker.align_check.call_count == 2
        assert worker.align_check.call_args_list[1].kwargs["vocal_path"] == dry
        assert worker.transcribe_words.call_count == 2
        assert worker.transcribe_words.call_args_list[1].kwargs["vocal_path"] == dry
        ass_path = ctx.song_path.parent / "karaoke" / f"{ctx.song_path.stem}.ass"
        assert ass_path.exists()

    def test_dereverb_telemetry_lands_in_capture_bundle(self, tmp_path, monkeypatch):
        stage, ctx, worker, stem_worker = self._make(tmp_path, monkeypatch)
        stem_worker.separate.return_value = (
            ctx.tmp_dir / "v_(Noreverb).wav",
            ctx.tmp_dir / "v_(Reverb).wav",
        )
        stage.run(ctx)
        debug_dir = ctx.song_path.parent / "alignment_debug"
        bundles = list(debug_dir.glob("*.json"))
        assert len(bundles) == 1
        assert '"dereverb"' in bundles[0].read_text(encoding="utf-8")

    def test_high_yield_skips_retry(self, tmp_path, monkeypatch):
        stage, ctx, worker, stem_worker = self._make(tmp_path, monkeypatch, duration_s=1.0)
        stage.run(ctx)
        stem_worker.separate.assert_not_called()
        worker.align_check.assert_called_once()
        worker.transcribe_words.assert_called_once()

    def test_retry_failure_keeps_wet_results(self, tmp_path, monkeypatch):
        stage, ctx, worker, stem_worker = self._make(tmp_path, monkeypatch)
        stem_worker.separate.side_effect = RuntimeError("stem worker died")
        stage.run(ctx)  # must not raise
        worker.align_check.assert_called_once()
        worker.transcribe_words.assert_called_once()
        ass_path = ctx.song_path.parent / "karaoke" / f"{ctx.song_path.stem}.ass"
        assert ass_path.exists()

    def test_cancellation_propagates_not_degraded(self, tmp_path, monkeypatch):
        import threading

        from pikaraoke.pipeline.context import CancelToken, PipelineCancelled
        from pikaraoke.pipeline.workers.stem_worker import WorkerCancelledError

        stage, ctx, worker, stem_worker = self._make(tmp_path, monkeypatch)
        ctx.cancel = CancelToken(event=threading.Event())
        stem_worker.separate.side_effect = WorkerCancelledError("cancelled between chunks")
        with pytest.raises(PipelineCancelled):
            stage.run(ctx)

    def test_no_stem_worker_disables_gate(self, tmp_path, monkeypatch):
        stage, ctx, worker, _ = self._make(tmp_path, monkeypatch)
        stage._stem_worker = None
        stage.run(ctx)  # gate silently off — single wet pass
        worker.align_check.assert_called_once()
        worker.transcribe_words.assert_called_once()


class TestJointLrclibPrior:
    """Joint route: the fill-only LRCLIB timing prior for txt-sourced songs."""

    _LINES = [
        "alpha bravo charlie delta",
        "echo foxtrot golf hotel",
        "india juliet kilo lima",
        "mike november oscar papa",
    ]

    def _words(self):
        words = []
        for i, line in enumerate(self._LINES):
            t0 = 10.0 * (i + 1)
            for j, tok in enumerate(line.split()):
                words.append({"word": tok, "start": t0 + 0.5 * j, "end": t0 + 0.5 * j + 0.4})
        return words

    def _setup(self, tmp_path):
        stage, ctx, worker = _make_stage_and_ctx(tmp_path)
        words = self._words()
        ctx.artifacts["lyrics_path"].write_text("\n".join(self._LINES) + "\n", encoding="utf-8")
        worker.align_check.return_value = {"fail_ratio": 0.0, "result_id": "rid-1", "words": words}
        worker.refine_from_cached.return_value = words
        worker.transcribe_words.return_value = words
        # Persisted LRCLIB choice: each cue leads the audio by 1.5 s.
        synced = "".join(f"[00:{8.5 + 10 * i:05.2f}]{line}\n" for i, line in enumerate(self._LINES))
        rel = f"lyrics/{ctx.song_path.stem}.lrc"
        lrclib.write_lrc(
            ctx.song_path.parent / rel,
            {"id": 5, "trackName": "T", "artistName": "A", "syncedLyrics": synced},
        )
        ctx.artifacts["lrclib"] = {
            "lrc_file": rel,
            "record": {"id": 5, "trackName": "T", "artistName": "A"},
            "query": {"track_name": "T", "artist_name": "A"},
        }
        ctx.artifacts["media_duration_s"] = 212.0
        return stage, ctx

    def test_fill_only_prior_runs_and_is_captured(self, tmp_path):
        stage, ctx = self._setup(tmp_path)
        stage.run(ctx)

        debug = ctx.song_path.parent / "alignment_debug" / f"{ctx.song_path.stem}.json"
        bundle = json.loads(debug.read_text(encoding="utf-8"))

        prior = bundle["joint_stats"]["lrclib_prior"]
        assert prior["bailed"] is None
        assert prior["snap_enabled"] is False  # fill-only on the LRCLIB path
        assert prior["offset_s"] == 1.5
        assert prior["n_snapped"] == 0

        # Schema version + LRCLIB reference + context land in the bundle.
        assert bundle["schema_version"] == 6
        assert bundle["lyrics"]["lrclib"]["record"]["id"] == 5
        assert bundle["media_duration_s"] == 212.0
        assert bundle["config"]["joint_lrclib_prior"] is True

    def test_srt_origin_never_triggers_lrclib(self, tmp_path):
        # An SRT-sourced song carries cue_spans and no "lrclib" artifact:
        # the SRT prior owns it; the LRCLIB block must stay dormant.
        stage, ctx = self._setup(tmp_path)
        srt = ctx.song_path.parent / "subtitles" / f"{ctx.song_path.stem}.srt"
        srt.parent.mkdir(exist_ok=True)
        srt.write_text(
            "".join(
                f"{i + 1}\n00:00:{8 + 10 * i:02d},500 --> 00:00:{9 + 10 * i:02d},500\n{line}\n\n"
                for i, line in enumerate(self._LINES)
            ),
            encoding="utf-8",
        )
        ctx.artifacts["lyrics_path"] = srt
        del ctx.artifacts["lrclib"]
        stage.run(ctx)

        bundle = json.loads(
            (ctx.song_path.parent / "alignment_debug" / f"{ctx.song_path.stem}.json").read_text(
                encoding="utf-8"
            )
        )
        assert "lrclib_prior" not in bundle["joint_stats"]
        assert "srt_prior" in bundle["joint_stats"]
