"""Unit tests for the Phase D ffmpeg stages (C20).

Covers the genuinely bug-prone logic with mocked subprocess: run_ffmpeg's
error / cancel / capture / PTY-routing branches and the loudnorm backward
stderr-JSON walker plus its field validation. The stages are otherwise thin
ffmpeg command builders, verified end-to-end at C-PROC.
"""

import json
import subprocess
import threading
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import (
    CancelToken,
    Phase,
    PipelineCancelled,
    StageContext,
)
from pikaraoke.pipeline.stages._ffmpeg_helpers import run_ffmpeg
from pikaraoke.pipeline.stages.ffmpeg_extract import FFmpegExtractStage
from pikaraoke.pipeline.stages.ffmpeg_transcode import FFmpegTranscodeStage
from pikaraoke.pipeline.stages.load_vocal import LoadVocalFromM4aStage
from pikaraoke.pipeline.stages.loudnorm_analyze import LoudnormAnalyzeStage

_POPEN = "pikaraoke.pipeline.stages._ffmpeg_helpers.subprocess.Popen"


def _ctx(tmp_path, *, cancel=None, artifacts=None):
    return StageContext(
        song_path=tmp_path / "Song---abcdefghijk.mp4",
        tmp_dir=tmp_path,
        config=PipelineConfig(),
        artifacts=artifacts if artifacts is not None else {},
        cancel=cancel,
    )


def _mock_popen(returncode=0, stderr=b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate.return_value = (b"", stderr)
    proc.wait.return_value = returncode
    return proc


class TestRunFfmpeg:
    """run_ffmpeg's wait/error/capture/PTY/cancel contract."""

    def test_success_without_capture_returns_empty_and_inherits_parent_stdio(self, tmp_path):
        proc = _mock_popen(returncode=0)
        with patch(_POPEN, return_value=proc) as popen:
            out = run_ffmpeg(["ffmpeg", "-i", "x"], _ctx(tmp_path), Phase.EXTRACT)
        assert out == ""
        proc.wait.assert_called_once()
        # No PTY fd -> inherit the parent's stdio (the main terminal), not discarded.
        assert popen.call_args.kwargs["stdout"] is None
        assert popen.call_args.kwargs["stderr"] is None

    def test_nonzero_exit_raises_runtimeerror(self, tmp_path):
        proc = _mock_popen(returncode=1)
        with patch(_POPEN, return_value=proc):
            with pytest.raises(RuntimeError, match="exit code 1"):
                run_ffmpeg(["ffmpeg"], _ctx(tmp_path), Phase.EXTRACT)

    def test_capture_stderr_decodes_with_replacement(self, tmp_path):
        proc = _mock_popen(returncode=0, stderr=b"loud\xffnorm")
        with patch(_POPEN, return_value=proc) as popen:
            out = run_ffmpeg(["ffmpeg"], _ctx(tmp_path), Phase.LOUDNORM, capture_stderr=True)
        proc.communicate.assert_called_once()
        assert "loud" in out and "norm" in out  # undecodable byte replaced, not raised
        assert popen.call_args.kwargs["stderr"] == subprocess.PIPE

    def test_pty_fd_routes_stdout_and_stderr(self, tmp_path):
        proc = _mock_popen()
        ctx = _ctx(tmp_path, artifacts={"pty_slave_fd": 7})
        with patch(_POPEN, return_value=proc) as popen:
            run_ffmpeg(["ffmpeg"], ctx, Phase.EXTRACT)
        assert popen.call_args.kwargs["stdout"] == 7
        assert popen.call_args.kwargs["stderr"] == 7

    def test_precancelled_token_reaps_orphan_and_raises(self, tmp_path):
        # A cancel that lands before activity() registers KillProcess (the
        # Popen-to-__enter__ window, reproduced here with an already-cancelled
        # token) must still SIGKILL + reap the just-spawned proc — the activity
        # body never runs, so the cancel mechanism never killed it, and an
        # un-reaped ffmpeg would otherwise finish into the doomed tmp_dir.
        proc = _mock_popen()
        tok = CancelToken(event=threading.Event())
        tok.cancel()
        with patch(_POPEN, return_value=proc):
            with pytest.raises(PipelineCancelled):
                run_ffmpeg(["ffmpeg"], _ctx(tmp_path, cancel=tok), Phase.EXTRACT)
        proc.kill.assert_called_once()  # orphan reaped
        proc.wait.assert_called_once()  # ...and waited (body's wait never ran)
        proc.communicate.assert_not_called()  # body work never started


class TestLoudnormJsonExtraction:
    """The backward stderr walk that isolates loudnorm's JSON block."""

    def test_extracts_trailing_block(self):
        stderr = (
            "ffmpeg version 5.1\n"
            "[Parsed_loudnorm_0 @ 0x] some log line\n"
            "{\n"
            '  "input_i" : "-15.00",\n'
            '  "normalization_type" : "dynamic"\n'
            "}\n"
        )
        out = LoudnormAnalyzeStage._extract_json_from_stderr(stderr)
        assert json.loads(out)["input_i"] == "-15.00"

    def test_picks_last_block_when_earlier_fragment_present(self):
        stderr = '{\n  "early" : "1"\n}\n' "noise\n" '{\n  "input_i" : "-9.0"\n}\n'
        out = LoudnormAnalyzeStage._extract_json_from_stderr(stderr)
        assert json.loads(out) == {"input_i": "-9.0"}

    def test_returns_none_without_closing_brace(self):
        assert LoudnormAnalyzeStage._extract_json_from_stderr("no json here\nat all\n") is None


_LOUDNORM_JSON = json.dumps(
    {
        "input_i": "-15.0",
        "input_tp": "-1.5",
        "input_lra": "6.0",
        "input_thresh": "-25.0",
        "target_offset": "0.5",
        "normalization_type": "dynamic",
    }
)


class TestLoudnormAnalyzeStage:
    """Artifact population and validation around the loudnorm measurement."""

    def test_populates_measurement_artifacts(self, tmp_path):
        ctx = _ctx(tmp_path, artifacts={"extracted_wav": tmp_path / "in.wav"})
        with patch(
            "pikaraoke.pipeline.stages.loudnorm_analyze.run_ffmpeg",
            return_value=f"log line\n{_LOUDNORM_JSON}\n",
        ):
            LoudnormAnalyzeStage(PipelineConfig()).run(ctx)
        assert ctx.artifacts["loudnorm_input_i"] == -15.0
        assert ctx.artifacts["loudnorm_target_offset"] == 0.5
        assert ctx.artifacts["loudnorm_type"] == "dynamic"

    def test_missing_extracted_wav_raises(self, tmp_path):
        with pytest.raises(RuntimeError, match="No extracted_wav"):
            LoudnormAnalyzeStage(PipelineConfig()).run(_ctx(tmp_path))

    def test_missing_json_field_raises(self, tmp_path):
        ctx = _ctx(tmp_path, artifacts={"extracted_wav": tmp_path / "in.wav"})
        with patch(
            "pikaraoke.pipeline.stages.loudnorm_analyze.run_ffmpeg",
            return_value=json.dumps({"input_i": "-15.0"}) + "\n",
        ):
            with pytest.raises(RuntimeError, match="missing or invalid field"):
                LoudnormAnalyzeStage(PipelineConfig()).run(ctx)


class TestStageGuardsAndNames:
    def test_transcode_missing_stems_raises(self, tmp_path):
        with pytest.raises(RuntimeError, match="Missing stem WAVs"):
            FFmpegTranscodeStage(PipelineConfig()).run(_ctx(tmp_path))

    def test_load_vocal_missing_stem_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Vocal stem missing"):
            LoadVocalFromM4aStage().run(_ctx(tmp_path))

    def test_stage_names(self):
        assert FFmpegExtractStage(PipelineConfig()).name == "ffmpeg_extract"
        assert FFmpegTranscodeStage(PipelineConfig()).name == "ffmpeg_transcode"
        assert LoudnormAnalyzeStage(PipelineConfig()).name == "loudnorm_analyze"
        assert LoadVocalFromM4aStage().name == "load_vocal"
