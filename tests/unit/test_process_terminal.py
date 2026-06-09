"""Unit tests for ProcessTerminal's platform-selection and guard logic.

The PTY relay / socket / subprocess machinery is exercised end-to-end at
C-PROC (live); these tests cover the pure-logic seams that are cheap to mock
and prone to silent platform regressions: terminal-emulator discovery, the
Windows no-op start, and the pre-start fd/path accessors.
"""

from unittest.mock import MagicMock, patch

import pytest

import pikaraoke.lib.process_terminal as pt
from pikaraoke.lib.process_terminal import ProcessTerminal


class TestFindTerminal:
    def test_returns_first_available_candidate(self):
        with patch.object(pt, "is_raspberry_pi", return_value=False), patch.object(
            pt, "is_macos", return_value=False
        ), patch.object(pt.shutil, "which", side_effect=lambda c: c if c == "xterm" else None):
            # gnome-terminal is absent, xterm is the next candidate present.
            assert ProcessTerminal._find_terminal() == "xterm"

    def test_returns_none_when_no_emulator(self):
        with patch.object(pt, "is_raspberry_pi", return_value=False), patch.object(
            pt, "is_macos", return_value=False
        ), patch.object(pt.shutil, "which", return_value=None):
            assert ProcessTerminal._find_terminal() is None

    def test_macos_returns_none(self):
        # macOS is handled via osascript, not _find_terminal.
        with patch.object(pt, "is_raspberry_pi", return_value=False), patch.object(
            pt, "is_macos", return_value=True
        ):
            assert ProcessTerminal._find_terminal() is None

    def test_raspberry_pi_prefers_lxterminal(self):
        with patch.object(pt, "is_raspberry_pi", return_value=True), patch.object(
            pt, "is_macos", return_value=False
        ), patch.object(pt.shutil, "which", side_effect=lambda c: c):
            # All candidates present → the first Pi candidate wins.
            assert ProcessTerminal._find_terminal() == "lxterminal"


class TestStartGuards:
    def test_start_on_windows_is_noop(self, tmp_path):
        term = ProcessTerminal(socket_path=str(tmp_path / "p.sock"))
        with patch.object(pt, "is_windows", return_value=True):
            term.start()  # must not open a PTY or spawn anything
        assert term.get_slave_fd() is None
        assert term.get_slave_path() is None

    def test_accessors_none_before_start(self, tmp_path):
        term = ProcessTerminal(socket_path=str(tmp_path / "p.sock"))
        assert term.get_slave_fd() is None
        assert term.get_slave_path() is None


class TestRelayLoopGuards:
    """The relay loop must not die silently on socket-setup failure (which would
    leave the PTY undrained and block a worker) and must exit cleanly if its
    master fd is closed under it by a racing stop()."""

    def test_survives_bind_failure_and_still_drains_pty(self, tmp_path):
        term = ProcessTerminal(socket_path=str(tmp_path / "p.sock"))
        term._master_fd = 5  # opaque; select/read are mocked
        reads = []
        fake_sock = MagicMock()
        fake_sock.bind.side_effect = OSError("address already in use")

        def fake_select(rlist, *a, **k):
            if not reads:
                return (rlist, [], [])
            term._shutdown_event.set()
            return ([], [], [])

        def fake_read(fd, _n):
            reads.append(fd)
            return b"worker output"

        with patch.object(pt.socket, "socket", return_value=fake_sock), patch.object(
            pt.select, "select", side_effect=fake_select
        ), patch.object(pt.os, "read", side_effect=fake_read):
            term._relay_loop()  # must not raise

        assert reads == [5]  # PTY drained despite no terminal client
        assert term._server_socket is None  # half-open socket never assigned
        fake_sock.close.assert_called_once()

    def test_breaks_cleanly_when_master_fd_closed(self, tmp_path):
        term = ProcessTerminal(socket_path=str(tmp_path / "p.sock"))
        term._master_fd = 5
        fake_sock = MagicMock()

        with patch.object(pt.socket, "socket", return_value=fake_sock), patch.object(
            pt.select, "select", side_effect=OSError("bad file descriptor")
        ):
            term._relay_loop()  # must return, not raise

        fake_sock.close.assert_called_once()  # bound socket cleaned up at exit
        assert term._server_socket is None


class TestReaderModule:
    def test_reader_main_requires_socket_arg(self):
        import pikaraoke.lib.process_terminal_reader as reader

        with patch.object(reader.sys, "argv", ["process_terminal_reader"]):
            with pytest.raises(SystemExit) as exc:
                reader.main()
        assert exc.value.code == 1
