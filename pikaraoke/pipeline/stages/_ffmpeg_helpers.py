"""FFmpeg helper: spawn ffmpeg under a cancellation activity scope.

Wraps a Popen in a KillProcess Cancellable so the orchestrator can
SIGKILL it via CancelToken.cancel().  The activity() contextmanager
ensures phase + cancellable are registered atomically and always cleared.

PTY routing: reads ``ctx.artifacts["pty_slave_fd"]`` to route ffmpeg
stdout/stderr to the secondary terminal when available (matching the
current production behaviour in processing_manager.py).
"""

import subprocess

from pikaraoke.pipeline.context import (
    KillProcess,
    Phase,
    PipelineCancelled,
    StageContext,
)


def run_ffmpeg(
    cmd: list[str],
    ctx: StageContext,
    phase: Phase,
    *,
    capture_stderr: bool = False,
) -> str:
    """Spawn ffmpeg under an activity scope, wait, raise on cancel/error.

    Returns captured stderr (as a string) when *capture_stderr* is True,
    otherwise returns an empty string.

    When ``ctx.artifacts["pty_slave_fd"]`` is present (the Linux/macOS
    processing terminal), ffmpeg stdout/stderr are routed to that fd.
    Otherwise they inherit the parent's stdio so output appears on the main
    terminal (e.g. on Windows, which has no processing terminal).

    Raises:
        PipelineCancelled: if the job was cancelled (the Popen was SIGKILL'd
            by the cancel mechanism, or a cancel arrived before/during the
            activity).
        RuntimeError: if ffmpeg exits with a non-zero code and the job was
            NOT cancelled.
    """
    # An fd routes to the processing terminal (Linux/macOS); None makes ffmpeg
    # inherit the parent's stdio — the main terminal (e.g. Windows).
    pty_fd = ctx.artifacts.get("pty_slave_fd")
    stdout_fd = pty_fd
    stderr_fd = subprocess.PIPE if capture_stderr else pty_fd

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=stdout_fd,
        stderr=stderr_fd,
    )

    stderr_data: bytes | None = None
    if ctx.cancel is not None:
        try:
            with ctx.cancel.activity(phase, KillProcess(proc)):
                if capture_stderr:
                    _, stderr_data = proc.communicate()
                else:
                    proc.wait()
            # activity() re-raises PipelineCancelled on exit if cancelled
        except PipelineCancelled:
            # A cancel landing between Popen() above and activity()'s
            # __enter__ registering KillProcess raises here with the proc
            # still un-killed (it wasn't the cancel target yet) — SIGKILL and
            # reap it so no orphaned ffmpeg finishes into the doomed tmp_dir.
            # No-op if the cancel mechanism already killed it inside the body.
            proc.kill()
            proc.wait()
            raise
    else:
        # No cancel support — straight wait, no activity bookkeeping.
        if capture_stderr:
            _, stderr_data = proc.communicate()
        else:
            proc.wait()

    if proc.returncode != 0:
        # If activity() raised PipelineCancelled, we never reach here —
        # CancelToken.cancel() sets cancelled=True before SIGKILLing, so the
        # activity's exit check sees it. The check below is defensive against
        # any future refactor that breaks that ordering.
        if ctx.cancel is not None and ctx.cancel.is_cancelled():
            raise PipelineCancelled(phase)
        raise RuntimeError(f"ffmpeg failed (exit code {proc.returncode})")

    if capture_stderr and stderr_data is not None:
        return stderr_data.decode("utf-8", errors="replace")
    return ""
