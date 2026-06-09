"""Secondary terminal reader: connects to Unix socket and prints relay output.

Runnable as a module::

    python3 -m pikaraoke.lib.process_terminal_reader <socket_path>

Connects to the Unix domain socket opened by ProcessTerminal and writes
all received bytes to stdout so the terminal displays the processing log
in real time (including ANSI progress bars from ffmpeg / audio-separator).
"""

import socket
import sys
import time


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: process_terminal_reader <socket_path>", file=sys.stderr)
        sys.exit(1)

    socket_path = sys.argv[1]

    # Retry connection a few times (relay thread may still be binding).
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connected = False
    for attempt in range(5):
        try:
            sock.connect(socket_path)
            connected = True
            break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.5)

    if not connected:
        print(
            "--- PiKaraoke Processing: could not connect to relay ---",
            file=sys.stdout,
            flush=True,
        )
        sys.exit(1)

    print("--- PiKaraoke Processing Output ---", file=sys.stdout, flush=True)

    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except (OSError, BrokenPipeError):
        pass
    finally:
        try:
            sock.close()
        except OSError:
            pass

    print("\n--- PiKaraoke Processing: disconnected ---", file=sys.stdout, flush=True)


if __name__ == "__main__":
    main()
