"""Redirect processing output to a secondary terminal window via PTY relay."""

import logging
import os
import select
import shutil
import socket
import subprocess
import sys
import threading

from pikaraoke.lib.get_platform import (
    get_data_directory,
    is_macos,
    is_raspberry_pi,
    is_windows,
)

logger = logging.getLogger(__name__)


class ProcessTerminal:
    """Opens a secondary terminal and relays PTY output to it.

    Creates a PTY pair so that child processes (ffmpeg, audio-separator)
    see a real TTY (isatty() == True) and render progress bars. A relay
    thread drains the PTY master and forwards bytes to the secondary
    terminal over a Unix domain socket.
    """

    def __init__(self, socket_path: str | None = None) -> None:
        if socket_path is None:
            data_dir = get_data_directory()
            socket_path = os.path.join(data_dir, "processing.sock")
        self._socket_path = socket_path

        self._master_fd: int | None = None
        self._slave_fd: int | None = None
        self._server_socket: socket.socket | None = None
        self._terminal_proc: subprocess.Popen | None = None
        self._relay_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

    # -- Public API -----------------------------------------------------------

    def start(self) -> None:
        """Create the PTY pair, start the relay thread, and spawn the terminal."""
        if is_windows():
            logger.warning(
                "ProcessTerminal: PTY not supported on Windows; "
                "output will fall back to main stderr"
            )
            return

        try:
            self._master_fd, slave_fd = os.openpty()
        except OSError as e:
            logger.warning("ProcessTerminal: failed to open PTY: %s", e)
            return

        # The worker process will inherit the slave fd.
        os.set_inheritable(slave_fd, True)
        self._slave_fd = slave_fd

        # Remove stale socket if present and not in use.
        self._cleanup_stale_socket()

        # Start the relay thread (binds Unix socket, drains PTY master).
        self._shutdown_event.clear()
        self._relay_thread = threading.Thread(target=self._relay_loop, daemon=True)
        self._relay_thread.start()

        # Spawn the secondary terminal emulator.
        self._spawn_terminal()

    def stop(self) -> None:
        """Shut down the relay thread, close PTY/socket, and terminate the terminal."""
        self._shutdown_event.set()

        if self._relay_thread is not None and self._relay_thread.is_alive():
            self._relay_thread.join(timeout=3)

        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

        if self._slave_fd is not None:
            try:
                os.close(self._slave_fd)
            except OSError:
                pass
            self._slave_fd = None

        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        if self._terminal_proc is not None:
            self._terminal_proc.terminate()
            try:
                self._terminal_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._terminal_proc.kill()
            self._terminal_proc = None

        # Clean up socket file.
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass

    def get_slave_fd(self) -> int | None:
        """Return the PTY slave fd for the worker to dup2 onto stdout/stderr."""
        return self._slave_fd

    def get_slave_path(self) -> str | None:
        """Return the PTY slave device path (e.g. /dev/pts/3).

        Spawn'd subprocesses cannot inherit file descriptors from the
        parent, so they must re-open the slave by path. fork-based
        children can still use get_slave_fd() instead.
        """
        if self._slave_fd is None:
            return None
        try:
            return os.ttyname(self._slave_fd)
        except OSError as e:
            logger.warning("ProcessTerminal: failed to resolve slave path: %s", e)
            return None

    # -- Internals ------------------------------------------------------------

    def _cleanup_stale_socket(self) -> None:
        """Remove a leftover socket file from a previous run, if safe."""
        if os.path.exists(self._socket_path):
            # Try connecting to see if something is still listening.
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.settimeout(0.2)
                probe.connect(self._socket_path)
                probe.close()
                # Something is listening — leave the socket alone.
                logger.debug(
                    "ProcessTerminal: socket %s is in use, leaving intact",
                    self._socket_path,
                )
                return
            except (OSError, ConnectionRefusedError):
                # Nothing listening — safe to remove.
                try:
                    os.unlink(self._socket_path)
                except OSError:
                    pass
            finally:
                try:
                    probe.close()
                except OSError:
                    pass

    def _relay_loop(self) -> None:
        """Bind the Unix socket, accept one client, and forward PTY bytes.

        Socket setup is guarded: if the bind fails (e.g. the socket path is in
        use by a second instance sharing the data dir), we still drain the PTY
        master below so the worker never blocks on a full buffer — it just runs
        without a terminal client instead of the relay dying silently.
        ``self._server_socket`` is assigned only after a successful bind so a
        failed setup can't leak a half-open fd.
        """
        server: socket.socket | None = None
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(self._socket_path)
            sock.listen(1)
            sock.settimeout(0.5)
            server = sock
            self._server_socket = sock
        except OSError as e:
            logger.warning(
                "ProcessTerminal: relay socket setup failed (%s); "
                "draining PTY without a terminal client",
                e,
            )
            try:
                sock.close()
            except OSError:
                pass

        client: socket.socket | None = None
        # Pre-connection buffer: drain PTY so the worker never blocks, but
        # keep the bytes so we can flush them once the client connects.
        pre_buffer: bytearray = bytearray()
        MAX_PRE_BUFFER = 64 * 1024  # 64 KB cap

        while not self._shutdown_event.is_set():
            # Always drain PTY master so the worker never blocks on a full buffer.
            try:
                ready, _, _ = select.select([self._master_fd], [], [], 0.1)
            except (OSError, ValueError, TypeError):
                # _master_fd was closed/cleared by stop() racing the relay join.
                break
            if ready:
                try:
                    data = os.read(self._master_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                if client is not None:
                    try:
                        client.sendall(data)
                    except (OSError, BrokenPipeError):
                        logger.debug("ProcessTerminal: terminal client disconnected")
                        client = None
                        sys.stderr.buffer.write(data)
                        sys.stderr.buffer.flush()
                else:
                    if len(pre_buffer) < MAX_PRE_BUFFER:
                        pre_buffer.extend(data)

            # Accept a new client connection if not yet connected.
            if server is not None and client is None:
                try:
                    conn, _ = server.accept()
                    client = conn
                    logger.debug("ProcessTerminal: terminal client connected")
                    # Flush everything that arrived before the client connected.
                    if pre_buffer:
                        try:
                            client.sendall(bytes(pre_buffer))
                        except (OSError, BrokenPipeError):
                            client = None
                        pre_buffer.clear()
                except socket.timeout:
                    pass
                except OSError:
                    break

        if client is not None:
            try:
                client.close()
            except OSError:
                pass

        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        self._server_socket = None

    def _spawn_terminal(self) -> None:
        """Launch a terminal emulator running the reader script."""
        reader_module = "pikaraoke.lib.process_terminal_reader"
        socket_path = self._socket_path
        exe = sys.executable or "python3"
        cmd_parts: list[str] = []

        if is_macos():
            # Use osascript to open Terminal.app and run the reader.
            script = f'do script "{exe} -m {reader_module} {socket_path}"'
            cmd_parts = ["osascript", "-e", script]
        else:
            terminal = self._find_terminal()
            if terminal is None:
                logger.warning(
                    "ProcessTerminal: no terminal emulator found; "
                    "output will fall back to main stderr"
                )
                return
            cmd_parts = [terminal, "-e", f"{exe} -m {reader_module} {socket_path}"]

        try:
            self._terminal_proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("ProcessTerminal: launched terminal: %s", " ".join(cmd_parts))
        except OSError as e:
            logger.warning("ProcessTerminal: failed to spawn terminal: %s", e)

    @staticmethod
    def _find_terminal() -> str | None:
        """Return the path to an available terminal emulator."""
        if is_raspberry_pi():
            candidates = ["lxterminal", "xterm", "x-terminal-emulator"]
        elif is_macos():
            # macOS handled separately via osascript.
            return None
        else:
            candidates = [
                "gnome-terminal",
                "xterm",
                "lxterminal",
                "x-terminal-emulator",
                "konsole",
                "alacritty",
                "kitty",
            ]

        for candidate in candidates:
            if shutil.which(candidate) is not None:
                return candidate
        return None
