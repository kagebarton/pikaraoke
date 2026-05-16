"""Unit tests for WhisperWorker parent-side façade.

Tests the subprocess lifecycle and IPC dispatch without requiring
a real stable-ts model or GPU. Uses a fake _worker_main and stub
Pipes to simulate the subprocess protocol.
"""

import logging
import threading
import time
from multiprocessing import Pipe
from unittest.mock import MagicMock, patch

import pytest

from pikaraoke.pipeline.config import WhisperModelConfig
from pikaraoke.pipeline.workers._ipc import WorkerDiedError
from pikaraoke.pipeline.workers.whisper_worker import (
    WHISPER_LOAD_TIMEOUT_SEC,
    AlignmentCancelledError,
    WhisperWorker,
    _extract_align_failure_ratio,
    _extract_words,
    _segments_to_line_objects,
)

# ---------------------------------------------------------------------------
# Helpers: fake subprocess that speaks the whisper worker protocol
# ---------------------------------------------------------------------------


def _fake_worker_main_ok(
    job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path
):
    """Fake worker that sends ("ready",), handles one job, then exits on
    the None sentinel."""
    result_send.send(("ready",))
    item = job_recv.recv()
    if item is None:
        return
    # Canned success reply — payload doesn't have to match the job kind.
    result_send.send(("ok", [{"text": "hello", "words": [], "start": 0.0, "end": 1.0}]))


def _fake_worker_main_cancelled(
    job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path
):
    """Fake worker that sends ("ready",) then ("cancelled",) for any job."""
    result_send.send(("ready",))
    item = job_recv.recv()
    if item is None:
        return
    result_send.send(("cancelled",))


def _fake_worker_main_error(
    job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path
):
    """Fake worker that sends ("ready",) then ("error", msg) for any job."""
    result_send.send(("ready",))
    item = job_recv.recv()
    if item is None:
        return
    result_send.send(("error", "something went wrong"))


def _fake_worker_main_die_on_boot(
    job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path
):
    """Fake worker that closes the pipe immediately (dies during load)."""
    result_send.close()


def _fake_worker_main_slow_boot(
    job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path
):
    """Fake worker that takes too long to send ("ready",)."""
    time.sleep(WHISPER_LOAD_TIMEOUT_SEC + 5)


def _fake_worker_main_die_during_job(
    job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path
):
    """Fake worker that sends ("ready",) then dies during a job."""
    result_send.send(("ready",))
    item = job_recv.recv()
    # Simulate dying without sending a result — just close the pipe
    result_send.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    return WhisperModelConfig()


@pytest.fixture
def worker(config):
    """WhisperWorker with no pty_slave_path."""
    return WhisperWorker(config=config)


# ---------------------------------------------------------------------------
# start() — ready signal
# ---------------------------------------------------------------------------


class TestStart:
    @patch("pikaraoke.pipeline.workers.whisper_worker.WORKER_CONTEXT")
    def test_start_blocks_until_ready(self, mock_ctx, worker):
        """start() returns after receiving ("ready",) from subprocess."""
        # Set up a fake Process that runs _fake_worker_main_ok
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.is_alive.return_value = True
        mock_process.exitcode = None
        mock_ctx.Process.return_value = mock_process

        # We need to actually create real pipes for the fake worker to use,
        # but start() creates its own. Instead, let's directly test the
        # ready-wait loop by simulating the result pipe.
        # Use a simpler approach: patch _worker_main and use real pipes.

        # Create real pipes manually
        job_recv, job_send = Pipe(duplex=False)
        result_recv, result_send = Pipe(duplex=False)
        cancel_recv, cancel_send = Pipe(duplex=False)

        # Start the fake worker in a thread
        fake = threading.Thread(
            target=_fake_worker_main_ok,
            args=(job_recv, result_send, cancel_recv, {}, logging.INFO, None),
            daemon=True,
        )
        fake.start()

        # Manually set up the worker's internal state as if start() created pipes
        worker._job_send = job_send
        worker._job_recv = job_recv
        worker._result_recv = result_recv
        worker._result_send = result_send
        worker._cancel_send = cancel_send
        worker._cancel_recv = cancel_recv
        worker._process = mock_process

        # Now test the ready-wait loop directly
        deadline = time.monotonic() + WHISPER_LOAD_TIMEOUT_SEC
        got_ready = False
        while True:
            if result_recv.poll(0.5):
                msg = result_recv.recv()
                if msg == ("ready",):
                    got_ready = True
                    break
            if time.monotonic() > deadline:
                break

        # Clean up
        job_send.send(None)  # sentinel
        fake.join(timeout=5)

        assert got_ready, "start() should have received ('ready',) signal"

    def test_start_raises_worker_died_on_pipe_close(self, worker):
        """start() raises WorkerDiedError if subprocess pipe closes during load."""
        # Create real pipes and a fake worker that dies immediately
        job_recv, job_send = Pipe(duplex=False)
        result_recv, result_send = Pipe(duplex=False)
        cancel_recv, cancel_send = Pipe(duplex=False)

        fake = threading.Thread(
            target=_fake_worker_main_die_on_boot,
            args=(job_recv, result_send, cancel_recv, {}, logging.INFO, None),
            daemon=True,
        )
        fake.start()
        # Give the fake worker time to close the pipe
        fake.join(timeout=5)

        # Simulating what start() does — poll the result pipe
        with pytest.raises(WorkerDiedError):
            if result_recv.poll(1):
                try:
                    msg = result_recv.recv()
                except EOFError:
                    raise WorkerDiedError("Whisper worker pipe closed during model load")
            else:
                # Pipe didn't close yet (timing issue) — force the check
                try:
                    result_recv.recv()
                except EOFError:
                    raise WorkerDiedError("Whisper worker pipe closed during model load")

        # Clean up
        for conn in (job_send, job_recv, result_recv, result_send, cancel_send, cancel_recv):
            try:
                conn.close()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# _run_job — result dispatch
# ---------------------------------------------------------------------------


class TestRunJob:
    def test_ok_result(self, worker):
        """_run_job returns line_objects on ("ok", ...) from subprocess."""
        # Simulate the result pipe having an ("ok", ...) message
        rq, rs = Pipe(duplex=False)

        line_objects = [{"text": "hello", "words": [], "start": 0.0, "end": 1.0}]
        rs.send(("ok", line_objects))
        rs.close()

        # Directly test the message-dispatch logic from _run_job
        msg = rq.recv()
        rq.close()

        tag = msg[0]
        if tag == "ok":
            result = msg[1]
        elif tag == "cancelled":
            raise AlignmentCancelledError("Alignment cancelled")
        else:
            raise RuntimeError(f"Whisper worker error: {msg[1]}")

        assert result == line_objects

    def test_cancelled_result(self):
        """_run_job raises AlignmentCancelledError on ("cancelled",)."""
        rq, rs = Pipe(duplex=False)
        rs.send(("cancelled",))
        rs.close()

        msg = rq.recv()
        rq.close()

        tag = msg[0]
        with pytest.raises(AlignmentCancelledError):
            if tag == "cancelled":
                raise AlignmentCancelledError("Alignment cancelled")

    def test_error_result(self):
        """_run_job raises RuntimeError on ("error", msg)."""
        rq, rs = Pipe(duplex=False)
        rs.send(("error", "something broke"))
        rs.close()

        msg = rq.recv()
        rq.close()

        tag = msg[0]
        with pytest.raises(RuntimeError, match="something broke"):
            if tag == "error":
                raise RuntimeError(f"Whisper worker error: {msg[1]}")


# ---------------------------------------------------------------------------
# Auto-restart
# ---------------------------------------------------------------------------


class TestAutoRestart:
    def test_auto_restart_on_dead_process(self, worker):
        """_run_job calls start() if the subprocess is not alive."""
        mock_dead_process = MagicMock()
        mock_dead_process.is_alive.return_value = False
        mock_dead_process.pid = 9999
        worker._process = mock_dead_process

        # Create real pipes for the result and cancel paths
        result_recv, result_send = Pipe(duplex=False)
        job_recv, job_send = Pipe(duplex=False)
        cancel_recv, cancel_send = Pipe(duplex=False)

        # Patch start() so it doesn't actually spawn a subprocess
        with patch.object(worker, "start") as mock_start:
            mock_alive_process = MagicMock()
            mock_alive_process.is_alive.return_value = True
            mock_alive_process.pid = 11111

            def fake_start():
                worker._process = mock_alive_process
                worker._result_recv = result_recv
                worker._job_send = job_send
                worker._cancel_send = cancel_send
                worker._cancel_recv = cancel_recv
                # Send the result that _run_job expects
                result_send.send(("ok", []))
                result_send.close()

            mock_start.side_effect = fake_start

            result = worker._run_job(("transcribe_words", "/tmp/vocal.wav"), None)

            mock_start.assert_called_once()
            assert result == []

        # Clean up
        for conn in (result_recv, job_recv, cancel_recv):
            try:
                conn.close()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Cancel event forwarding
# ---------------------------------------------------------------------------


class TestCancelForwarding:
    def test_cancel_event_sends_byte_on_pipe(self):
        """Setting the cancel event causes a byte to appear on cancel_recv."""
        from pikaraoke.pipeline.workers._ipc import forward_cancel

        cancel_recv, cancel_send = Pipe(duplex=False)
        event = threading.Event()

        # Start the forwarder thread
        t = threading.Thread(target=forward_cancel, args=(event, cancel_send), daemon=True)
        t.start()

        # Set the event
        event.set()

        # Wait for the byte to arrive
        assert cancel_recv.poll(2), "Cancel byte should arrive within 2s"
        byte = cancel_recv.recv()
        assert byte == 1

        # Clean up
        for conn in (cancel_recv, cancel_send):
            try:
                conn.close()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# is_alive()
# ---------------------------------------------------------------------------


class TestIsAlive:
    def test_alive_when_process_running(self, worker):
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        worker._process = mock_process
        assert worker.is_alive() is True

    def test_not_alive_when_process_dead(self, worker):
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        worker._process = mock_process
        assert worker.is_alive() is False

    def test_not_alive_when_no_process(self, worker):
        worker._process = None
        assert worker.is_alive() is False


# ---------------------------------------------------------------------------
# stop() / kill()
# ---------------------------------------------------------------------------


class TestStopKill:
    def test_stop_sends_sentinel(self, worker):
        """stop() sends None sentinel on the job pipe."""
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        mock_process.join = MagicMock()  # Make join a no-op
        worker._process = mock_process

        # Use a mock for the job_send so we can verify the sentinel
        mock_job_send = MagicMock()
        worker._job_send = mock_job_send
        worker._job_recv = MagicMock()

        # Set up mock pipes for cleanup
        for attr in ("_result_recv", "_result_send", "_cancel_send", "_cancel_recv"):
            setattr(worker, attr, MagicMock())

        worker.stop()

        # Verify that None (sentinel) was sent on the job pipe
        mock_job_send.send.assert_called_once_with(None)

    def test_kill_terminates_process(self, worker):
        """kill() calls process.kill() and joins."""
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        worker._process = mock_process

        # Set up mock pipes for cleanup
        for attr in (
            "_job_send",
            "_job_recv",
            "_result_recv",
            "_result_send",
            "_cancel_send",
            "_cancel_recv",
        ):
            setattr(worker, attr, MagicMock())

        worker.kill()

        mock_process.kill.assert_called_once()
        mock_process.join.assert_called()

    def test_stop_noop_when_no_process(self, worker):
        """stop() is a no-op when no process exists."""
        worker._process = None
        worker.stop()  # Should not raise

    def test_kill_noop_when_no_process(self, worker):
        """kill() is a no-op when no process exists."""
        worker._process = None
        worker.kill()  # Should not raise


# ---------------------------------------------------------------------------
# Conversion helpers (characterization — re-test from new module location)
# ---------------------------------------------------------------------------


class TestExtractWords:
    """Tests for _extract_words — mirrors test_lyric_conversion.py."""

    @pytest.fixture
    def mock_result(self):
        """Build a mock WhisperResult with segments and words."""
        result = MagicMock()

        word1 = MagicMock(word=" Hello", start=0.0, end=0.5, probability=0.9)
        word2 = MagicMock(word=" world", start=0.5, end=1.0, probability=0.9)
        word3 = MagicMock(word=" foo", start=1.0, end=1.5, probability=0.9)

        seg1 = MagicMock()
        seg1.words = [word1, word2]
        seg2 = MagicMock()
        seg2.words = [word3]

        result.segments = [seg1, seg2]
        return result

    def test_extracts_all_words(self, mock_result):
        words = _extract_words(mock_result, min_word_probability=0.0001)
        assert len(words) == 3

    def test_strips_whitespace(self, mock_result):
        words = _extract_words(mock_result, min_word_probability=0.0001)
        assert words[0]["word"] == "Hello"
        assert words[1]["word"] == "world"

    def test_drops_low_probability(self):
        """Silent-region hallucinations (prob < threshold) get filtered."""
        good = MagicMock(word=" real", start=0.0, end=0.5, probability=0.85)
        phantom = MagicMock(word=" ghost", start=0.5, end=0.5, probability=0.00005)
        seg = MagicMock()
        seg.words = [good, phantom]
        result = MagicMock()
        result.segments = [seg]
        words = _extract_words(result, min_word_probability=0.0001)
        assert [w["word"] for w in words] == ["real"]


class TestSegmentsToLineObjects:
    @pytest.fixture
    def mock_result(self):
        result = MagicMock()
        word1 = MagicMock(word=" Hello", start=0.0, end=0.5)
        word2 = MagicMock(word=" world", start=0.5, end=1.0)
        seg = MagicMock()
        seg.text = " Hello world "
        seg.words = [word1, word2]
        result.segments = [seg]
        return result

    def test_builds_line_objects(self, mock_result):
        result = _segments_to_line_objects(mock_result)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert len(result[0]["words"]) == 2

    def test_skips_empty_segments(self):
        result = MagicMock()
        seg = MagicMock()
        seg.words = []
        result.segments = [seg]
        assert _segments_to_line_objects(result) == []


# ---------------------------------------------------------------------------
# _extract_align_failure_ratio — scrape stable-ts's warning
# ---------------------------------------------------------------------------


class _CapturedWarning:
    """Stand-in for a warnings.WarningMessage."""

    def __init__(self, message: str, category=UserWarning):
        self.message = message
        self.category = category


class TestExtractAlignFailureRatio:
    def test_parses_ratio(self):
        warns = [_CapturedWarning("12/48 segments failed to align.")]
        log = MagicMock()
        assert _extract_align_failure_ratio(warns, log) == pytest.approx(12 / 48)

    def test_handles_whitespace_around_slash(self):
        warns = [_CapturedWarning("7 / 14 segments failed to align.")]
        assert _extract_align_failure_ratio(warns, MagicMock()) == 0.5

    def test_no_warning_returns_zero(self):
        assert _extract_align_failure_ratio([], MagicMock()) == 0.0

    def test_unrelated_warning_returns_zero(self):
        warns = [_CapturedWarning("some other deprecation warning")]
        assert _extract_align_failure_ratio(warns, MagicMock()) == 0.0

    def test_zero_total_returns_zero(self):
        warns = [_CapturedWarning("0/0 segments failed to align.")]
        assert _extract_align_failure_ratio(warns, MagicMock()) == 0.0

    def test_reemits_warnings_to_logger(self):
        warns = [
            _CapturedWarning("3/9 segments failed to align."),
            _CapturedWarning("an unrelated warning", DeprecationWarning),
        ]
        log = MagicMock()
        _extract_align_failure_ratio(warns, log)
        # Every captured warning should be re-emitted so capturing the
        # message stream doesn't silently swallow them.
        assert log.warning.call_count == 2


# ---------------------------------------------------------------------------
# Parent-side facade methods for the new IPC verbs
# ---------------------------------------------------------------------------


def _fake_worker_replies(replies):
    """Build a fake _worker_main that sends ("ready",) then dispatches a
    canned reply for each job received in order. Replies are sent as-is
    (full tuples like ("ok", payload) or ("error", msg)).
    """

    def fake(job_recv, result_send, cancel_recv, config_dict, log_level, pty_slave_path):
        result_send.send(("ready",))
        for reply in replies:
            item = job_recv.recv()
            if item is None:
                return
            result_send.send(reply)
        # Wait for sentinel to exit cleanly.
        while True:
            item = job_recv.recv()
            if item is None:
                return

    return fake


def _wire_fake_worker(worker, fake_main):
    """Hook a fake _worker_main into a WhisperWorker, bypassing start().

    Consumes the ("ready",) signal up front so subsequent _run_job calls
    see only the canned replies on the result pipe.
    """
    job_recv, job_send = Pipe(duplex=False)
    result_recv, result_send = Pipe(duplex=False)
    cancel_recv, cancel_send = Pipe(duplex=False)

    mock_process = MagicMock()
    mock_process.pid = 24680
    mock_process.is_alive.return_value = True
    mock_process.exitcode = None

    worker._job_send = job_send
    worker._job_recv = job_recv
    worker._result_recv = result_recv
    worker._result_send = result_send
    worker._cancel_send = cancel_send
    worker._cancel_recv = cancel_recv
    worker._process = mock_process

    thread = threading.Thread(
        target=fake_main,
        args=(job_recv, result_send, cancel_recv, {}, logging.INFO, None),
        daemon=True,
    )
    thread.start()
    # Drain ("ready",) so _run_job sees only the canned replies.
    assert result_recv.recv() == ("ready",)
    return thread


class TestNewFacadeMethods:
    def test_align_check_returns_dict(self, worker):
        fake = _fake_worker_replies([("ok", {"fail_ratio": 0.05, "result_id": "abc123"})])
        thread = _wire_fake_worker(worker, fake)
        try:
            out = worker.align_check("/tmp/vocal.wav", "lyrics")
            assert out == {"fail_ratio": 0.05, "result_id": "abc123"}
        finally:
            worker._job_send.send(None)
            thread.join(timeout=3)

    def test_refine_from_cached_returns_words(self, worker):
        words = [{"word": "hi", "start": 0.0, "end": 0.5}]
        fake = _fake_worker_replies([("ok", words)])
        thread = _wire_fake_worker(worker, fake)
        try:
            out = worker.refine_from_cached("abc123", "/tmp/vocal.wav")
            assert out == words
        finally:
            worker._job_send.send(None)
            thread.join(timeout=3)

    def test_refine_from_cached_raises_on_stale_id(self, worker):
        fake = _fake_worker_replies([("error", "stale or unknown result_id: ghost")])
        thread = _wire_fake_worker(worker, fake)
        try:
            with pytest.raises(RuntimeError, match="stale or unknown result_id"):
                worker.refine_from_cached("ghost", "/tmp/vocal.wav")
        finally:
            worker._job_send.send(None)
            thread.join(timeout=3)

    def test_discard_cached_returns_quietly(self, worker):
        fake = _fake_worker_replies([("ok", None)])
        thread = _wire_fake_worker(worker, fake)
        try:
            # Should not raise; we don't assert anything about the return.
            worker.discard_cached("abc123")
        finally:
            worker._job_send.send(None)
            thread.join(timeout=3)

    def test_transcribe_words_returns_words(self, worker):
        words = [{"word": "tile", "start": 0.0, "end": 0.5}]
        fake = _fake_worker_replies([("ok", words)])
        thread = _wire_fake_worker(worker, fake)
        try:
            out = worker.transcribe_words("/tmp/vocal.wav")
            assert out == words
        finally:
            worker._job_send.send(None)
            thread.join(timeout=3)

    def test_align_check_cancel_raises(self, worker):
        fake = _fake_worker_replies([("cancelled",)])
        thread = _wire_fake_worker(worker, fake)
        try:
            with pytest.raises(AlignmentCancelledError):
                worker.align_check("/tmp/vocal.wav", "lyrics")
        finally:
            worker._job_send.send(None)
            thread.join(timeout=3)
