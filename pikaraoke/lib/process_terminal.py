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
        """Bind the Unix socket, accept one client, and forward PTY bytes."""
        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(self._socket_path)
        self._server_socket.listen(1)
        self._server_socket.settimeout(0.5)

        client: socket.socket | None = None
        # Pre-connection buffer: drain PTY so the worker never blocks, but
        # keep the bytes so we can flush them once the client connects.
        pre_buffer: bytearray = bytearray()
        MAX_PRE_BUFFER = 64 * 1024  # 64 KB cap

        while not self._shutdown_event.is_set():
            # Always drain PTY master so the worker never blocks on a full buffer.
            ready, _, _ = select.select([self._master_fd], [], [], 0.1)
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
            if client is None:
                try:
                    conn, _ = self._server_socket.accept()
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

        try:
            self._server_socket.close()
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
