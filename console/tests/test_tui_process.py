"""The TUI as a command: it starts from its command line on a terminal and quits on `q`."""

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time


def read_until(master, text, seconds=20):
    seen, deadline = b"", time.time() + seconds
    while text not in seen and time.time() < deadline:
        if select.select([master], [], [], 0.2)[0]:
            seen += os.read(master, 65536)
    return seen


def test_the_tui_starts_on_a_terminal_and_quits_on_q(receiver):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
    process = subprocess.Popen(
        [sys.executable, "-m", "asf_console.tui", "--url", f"http://127.0.0.1:{receiver.api_port}"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env={**os.environ, "TERM": "xterm-256color"},
    )
    os.close(slave)
    try:
        assert b"Factory Console" in read_until(master, b"Factory Console")
        os.write(master, b"q")
        assert process.wait(timeout=20) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
