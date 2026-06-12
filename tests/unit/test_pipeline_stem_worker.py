"""Unit tests for the Phase D stem-separation worker/stage (C21).

The worker drives a spawned subprocess that loads a Melband-Roformer model;
none of that is touched here. Instead these tests mock the subprocess and use
real in-process ``Pipe``s to pin the robustness logic this commit absorbs:

- ``StemWorker.separate``'s state machine: OOM auto-restart, death mid-wait,
  and the ``ok``/``cancelled``/``error`` result-tag dispatch.
- ``_ipc`` cancel forwarding and pipe draining.
- the per-chunk forward pre-hook, including the re-raise when audio-separator
  swallows ``_CancelledInsideDemix`` and returns ``[]``.
- the vocal/instrumental stem-ID heuristic.
- ``StemSeparationStage``'s WorkerCancelled/WorkerDied translation matrix,
  which differs between the cancel and no-cancel paths.

The real separation is exercised end-to-end at C-PROC.
"""

import logging
import threading
from multiprocessing import Pipe
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.pipeline.config import PipelineConfig
from pikaraoke.pipeline.context import (
    CancelToken,
    Phase,
    PipelineCancelled,
    StageContext,
)
from pikaraoke.pipeline.stages.stem_separation import StemSeparationStage
from pikaraoke.pipeline.workers._ipc import (
    WORKER_CONTEXT,
    WorkerDiedError,
    drain_pipe,
    forward_cancel,
)
from pikaraoke.pipeline.workers.stem_worker import (
    StemWorker,
    WorkerCancelledError,
    _CancelledInsideDemix,
    _run_separation_unpatched,
    _separate_with_cancel_check,
)

_LOG = logging.getLogger("test_stem_worker")


def _worker_with_fakes(*, alive=True, result=("ok", "/o/v.wav", "/o/i.wav")):
    """A StemWorker with its subprocess + IPC channels replaced by mocks."""
    w = StemWorker(temp_dir="/tmp")
    proc = MagicMock()
    proc.is_alive.return_value = alive
    proc.pid = 1234
    w._process = proc

    rq = MagicMock()
    rq.poll.return_value = True  # result is immediately available
    rq.recv.return_value = result
    w._result_recv = rq

    w._job_send = MagicMock()
    w._cancel_send = MagicMock()
    cancel_recv = MagicMock()
    cancel_recv.poll.return_value = False  # nothing to drain
    w._cancel_recv = cancel_recv
    return w, proc, rq


class TestIpcPrimitives:
    """The shared spawn/forward/drain helpers both workers depend on."""

    def test_worker_context_is_spawn(self):
        # fork-after-CUDA is unsafe; both workers must spawn.
        assert WORKER_CONTEXT.get_start_method() == "spawn"

    def test_forward_cancel_sends_one_byte_after_event(self):
        recv, send = Pipe()
        event = threading.Event()
        event.set()
        forward_cancel(event, send, threading.Event())  # done unset; sends the byte
        assert recv.recv() == 1

    def test_forward_cancel_swallows_broken_pipe(self):
        _recv, send = Pipe()
        send.close()
        event = threading.Event()
        event.set()
        forward_cancel(event, send, threading.Event())  # must not raise on a closed pipe

    def test_forward_cancel_exits_when_job_done(self):
        # A job that completes without cancelling sets ``done``; the forwarder
        # must exit without sending, rather than strand a thread blocked on the
        # never-fired cancel event for the life of the process.
        recv, send = Pipe()
        done = threading.Event()
        done.set()
        forward_cancel(threading.Event(), send, done)
        assert recv.poll(0) is False

    def test_drain_pipe_empties_pending_messages(self):
        recv, send = Pipe()
        send.send("a")
        send.send("b")
        drain_pipe(recv)
        assert recv.poll(0) is False


class TestStemWorkerSeparate:
    """The main-process side of separate(): restart + death + tag dispatch."""

    def test_ok_returns_stem_paths_and_sends_job(self):
        w, _proc, _rq = _worker_with_fakes(result=("ok", "/o/v.wav", "/o/i.wav"))
        out = w.separate(Path("/in/x.wav"), Path("/o"))
        assert out == (Path("/o/v.wav"), Path("/o/i.wav"))
        w._job_send.send.assert_called_once_with(("/in/x.wav", "/o"))

    def test_cancelled_tag_raises_worker_cancelled(self):
        w, _proc, _rq = _worker_with_fakes(result=("cancelled",))
        with pytest.raises(WorkerCancelledError):
            w.separate(Path("/in/x.wav"), Path("/o"))

    def test_error_tag_raises_runtimeerror_with_message(self):
        w, _proc, _rq = _worker_with_fakes(result=("error", "boom"))
        with pytest.raises(RuntimeError, match="boom"):
            w.separate(Path("/in/x.wav"), Path("/o"))

    def test_separate_without_process_raises_worker_died(self):
        w = StemWorker(temp_dir="/tmp")  # never started
        with pytest.raises(WorkerDiedError, match="not running"):
            w.separate(Path("/in/x.wav"), Path("/o"))

    def test_dead_subprocess_is_restarted_before_next_job(self):
        # OOM exit leaves a dead subprocess; the next separate() must restart
        # it (fresh CUDA context) rather than block on a torn-down pipe.
        w, _dead, _rq = _worker_with_fakes(alive=False)

        fresh_proc = MagicMock()
        fresh_proc.is_alive.return_value = True
        fresh_proc.pid = 999
        fresh_rq = MagicMock()
        fresh_rq.poll.return_value = True
        fresh_rq.recv.return_value = ("ok", "/o/v.wav", "/o/i.wav")

        def fake_start():
            w._process = fresh_proc
            w._result_recv = fresh_rq
            w._job_send = MagicMock()

        with patch.object(w, "start", side_effect=fake_start) as start_mock:
            out = w.separate(Path("/in/x.wav"), Path("/o"))
        start_mock.assert_called_once()
        assert out == (Path("/o/v.wav"), Path("/o/i.wav"))

    def test_process_death_mid_wait_raises_worker_died(self):
        w, proc, rq = _worker_with_fakes()
        rq.poll.return_value = False  # result never arrives
        proc.is_alive.side_effect = [True, False]  # alive at entry, dead in loop
        with pytest.raises(WorkerDiedError, match="died during separation"):
            w.separate(Path("/in/x.wav"), Path("/o"))

    def test_cancel_event_path_still_completes(self):
        # Passing a cancel_event spawns the forwarder thread; an un-triggered
        # event must not disturb a normal separation.
        w, _proc, _rq = _worker_with_fakes(result=("ok", "/o/v.wav", "/o/i.wav"))
        out = w.separate(Path("/in/x.wav"), Path("/o"), cancel_event=threading.Event())
        assert out == (Path("/o/v.wav"), Path("/o/i.wav"))


# --- Worker-subprocess helpers: cancel hook + stem identification ----------


class _FakeHandle:
    def __init__(self):
        self.removed = False

    def remove(self):
        self.removed = True


class _FakeModelRun:
    """Stands in for the Roformer nn.Module the pre-hook attaches to."""

    def __init__(self):
        self.hook = None
        self.handle = _FakeHandle()

    def register_forward_pre_hook(self, fn):
        self.hook = fn
        return self.handle


class _FakeModelInstance:
    def __init__(self, model_run):
        self.model_run = model_run
        self.output_dir = None


class _FakeSeparator:
    """Drives a caller-supplied ``separate`` body in place of audio-separator."""

    def __init__(self, model_run, separate_impl):
        self.model_instance = _FakeModelInstance(model_run) if model_run else None
        self.output_dir = None
        self._impl = separate_impl

    def separate(self, _path):
        return self._impl(self)


class TestCancelHook:
    """The per-chunk forward pre-hook injected into the demix loop."""

    def test_pending_signal_raises_cancelled_inside_demix(self):
        recv, send = Pipe()
        send.send(1)  # cancel already pending
        model_run = _FakeModelRun()

        def impl(_sep):
            model_run.hook(model_run, ("chunk",))  # hook polls + raises
            return ["unreached"]

        sep = _FakeSeparator(model_run, impl)
        with pytest.raises(_CancelledInsideDemix):
            _separate_with_cancel_check(Path("a.wav"), Path("/o"), sep, recv, _LOG)
        assert model_run.handle.removed is True

    def test_reraises_when_separator_swallows_cancel(self):
        # audio-separator catches exceptions internally and returns []; the
        # stage must still surface the cancel, not a stem-ID RuntimeError.
        recv, send = Pipe()
        send.send(1)
        model_run = _FakeModelRun()

        def impl(_sep):
            try:
                model_run.hook(model_run, ("chunk",))
            except _CancelledInsideDemix:
                pass
            return []  # swallowed

        sep = _FakeSeparator(model_run, impl)
        with pytest.raises(_CancelledInsideDemix):
            _separate_with_cancel_check(Path("a.wav"), Path("/o"), sep, recv, _LOG)

    def test_clean_run_identifies_stems_and_removes_hook(self):
        recv, _send = Pipe()  # no pending signal
        model_run = _FakeModelRun()

        def impl(_sep):
            model_run.hook(model_run, ("chunk",))  # no raise; counter advances
            model_run.hook(model_run, ("chunk",))
            return ["Song_(Vocals).wav", "Song_(Instrumental).wav"]

        sep = _FakeSeparator(model_run, impl)
        vocal, instrumental = _separate_with_cancel_check(
            Path("a.wav"), Path("/o"), sep, recv, _LOG
        )
        assert vocal == Path("/o/Song_(Vocals).wav")
        assert instrumental == Path("/o/Song_(Instrumental).wav")
        assert model_run.handle.removed is True


class TestStemIdentification:
    """The vocal/instrumental heuristic over audio-separator's output names."""

    def _separator(self, outputs):
        return _FakeSeparator(model_run=None, separate_impl=lambda _s: outputs)

    def test_vocals_and_instrumental(self):
        sep = self._separator(["x_(Vocals).wav", "x_(Instrumental).wav"])
        vocal, inst = _run_separation_unpatched(Path("a.wav"), Path("/o"), sep, _LOG)
        assert vocal.name == "x_(Vocals).wav"
        assert inst.name == "x_(Instrumental).wav"

    def test_other_stem_counts_as_instrumental(self):
        # Non-karaoke Roformer emits (Other) rather than (Instrumental).
        sep = self._separator(["x_(Vocals).wav", "x_(Other).wav"])
        vocal, inst = _run_separation_unpatched(Path("a.wav"), Path("/o"), sep, _LOG)
        assert vocal.name == "x_(Vocals).wav"
        assert inst.name == "x_(Other).wav"

    def test_unidentifiable_output_raises(self):
        sep = self._separator(["x_(Drums).wav", "x_(Bass).wav"])
        with pytest.raises(RuntimeError, match="Could not identify"):
            _run_separation_unpatched(Path("a.wav"), Path("/o"), sep, _LOG)


# --- Stage adapter ---------------------------------------------------------


class _FakeWorker:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def separate(self, wav_path, output_dir, cancel_event=None):
        self.calls.append((wav_path, output_dir, cancel_event))
        if self.exc is not None:
            raise self.exc
        return self.result


def _ctx(tmp_path, *, cancel=None, artifacts=None):
    return StageContext(
        song_path=tmp_path / "Song---abcdefghijk.mp4",
        tmp_dir=tmp_path,
        config=PipelineConfig(),
        artifacts=artifacts if artifacts is not None else {},
        cancel=cancel,
    )


class TestStemSeparationStage:
    """The stage's artifact wiring and exception-translation matrix."""

    def test_name(self):
        assert StemSeparationStage(_FakeWorker()).name == "stem_separation"

    def test_missing_extracted_wav_raises(self, tmp_path):
        stage = StemSeparationStage(_FakeWorker())
        with pytest.raises(RuntimeError, match="No extracted_wav"):
            stage.run(_ctx(tmp_path))

    def test_no_cancel_happy_path_populates_artifacts(self, tmp_path):
        worker = _FakeWorker(result=(tmp_path / "v.wav", tmp_path / "i.wav"))
        ctx = _ctx(tmp_path, artifacts={"extracted_wav": tmp_path / "in.wav"})
        StemSeparationStage(worker).run(ctx)
        assert ctx.artifacts["vocal_wav"] == tmp_path / "v.wav"
        assert ctx.artifacts["instrumental_wav"] == tmp_path / "i.wav"
        assert worker.calls[0][2] is None  # no cancel_event without a token

    def test_no_cancel_worker_died_raises_runtime(self, tmp_path):
        worker = _FakeWorker(exc=WorkerDiedError("gone"))
        ctx = _ctx(tmp_path, artifacts={"extracted_wav": tmp_path / "in.wav"})
        with pytest.raises(RuntimeError, match="died unexpectedly"):
            StemSeparationStage(worker).run(ctx)

    def test_no_cancel_worker_cancelled_raises_runtime(self, tmp_path):
        # Without a token there is no cancel scope, so a stray cancel is a bug.
        worker = _FakeWorker(exc=WorkerCancelledError("between chunks"))
        ctx = _ctx(tmp_path, artifacts={"extracted_wav": tmp_path / "in.wav"})
        with pytest.raises(RuntimeError, match="cancelled between chunks"):
            StemSeparationStage(worker).run(ctx)

    def test_cancel_token_happy_path_passes_event(self, tmp_path):
        worker = _FakeWorker(result=(tmp_path / "v.wav", tmp_path / "i.wav"))
        token = CancelToken(event=threading.Event())
        ctx = _ctx(tmp_path, cancel=token, artifacts={"extracted_wav": tmp_path / "in.wav"})
        StemSeparationStage(worker).run(ctx)
        assert worker.calls[0][2] is token.event
        assert ctx.artifacts["vocal_wav"] == tmp_path / "v.wav"

    def test_cancel_token_worker_cancelled_translates_to_pipeline_cancelled(self, tmp_path):
        worker = _FakeWorker(exc=WorkerCancelledError("between chunks"))
        token = CancelToken(event=threading.Event())
        ctx = _ctx(tmp_path, cancel=token, artifacts={"extracted_wav": tmp_path / "in.wav"})
        with pytest.raises(PipelineCancelled) as exc_info:
            StemSeparationStage(worker).run(ctx)
        assert exc_info.value.phase is Phase.STEM_SEPARATION

    def test_cancel_token_worker_died_raises_runtime(self, tmp_path):
        worker = _FakeWorker(exc=WorkerDiedError("gone"))
        token = CancelToken(event=threading.Event())
        ctx = _ctx(tmp_path, cancel=token, artifacts={"extracted_wav": tmp_path / "in.wav"})
        with pytest.raises(RuntimeError, match="died unexpectedly"):
            StemSeparationStage(worker).run(ctx)
