"""Shared IPC primitives for worker subprocesses.

Both StemWorker and WhisperWorker use the same patterns for:
- Spawning subprocesses via multiprocessing (always 'spawn' to avoid
  fork-after-CUDA issues).
- Forwarding threading.Event cancellation to a multiprocessing Pipe.
- Draining stale signals from a Pipe.
- Reporting subprocess death via WorkerDiedError.

Centralising these here avoids copy-paste between the two worker modules
and ensures both use the 'spawn' start method (fork-after-CUDA is unsafe:
any prior torch.cuda.* call in the parent leaves the child with a
duplicated, broken CUDA context).
"""

import multiprocessing as mp
import threading
from multiprocessing.connection import Connection

# Always use 'spawn' for worker subprocesses. fork-after-CUDA is
# unsafe: any prior torch.cuda.* call in the parent (intentional or
# not) leaves the child with a duplicated, broken CUDA context.
# Using a dedicated context here ensures both workers are immune
# regardless of what the parent process does.
WORKER_CONTEXT = mp.get_context("spawn")


class WorkerDiedError(Exception):
    """Raised when a worker subprocess dies during a job or boot."""


def forward_cancel(event: threading.Event, cancel_send: Connection, done: threading.Event) -> None:
    """Daemon-thread target: forward the cancel event to the cancel pipe.

    Bridges the main-process threading world to the subprocess Pipe world.
    Exits when the cancel fires (one byte sent — a job only needs one) or
    when ``done`` is set by the job finishing. Without the ``done`` exit,
    every uncancelled job would strand a thread blocked on ``event.wait()``
    for the life of the process.
    """
    while not done.is_set():
        if event.wait(0.5):
            if not done.is_set():
                try:
                    cancel_send.send(1)
                except (OSError, BrokenPipeError):
                    pass
            return


def drain_pipe(conn: Connection) -> None:
    """Non-blocking: read and discard any pending messages."""
    while conn.poll(0):
        try:
            conn.recv()
        except (EOFError, OSError):
            break
