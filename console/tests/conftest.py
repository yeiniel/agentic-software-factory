"""Fixtures: the receiver as a process, and the real OTLP Records Adapter replaying Factory events into it."""
import json
import re
import signal
import subprocess
import sys
import urllib.request
from types import SimpleNamespace

import pytest
from replay import Replay


@pytest.fixture
def start_receiver(tmp_path):
    """`start_receiver(model_url=None)` runs `python -m asf_console.receiver` on free ports."""
    processes = []

    def start(model_url=None):
        command = [sys.executable, "-m", "asf_console.receiver", "--db", str(tmp_path / f"console{len(processes)}.db"),
                   "--otlp-host", "127.0.0.1", "--otlp-port", "0", "--api-port", "0"]
        process = subprocess.Popen(command + (["--model-url", model_url] if model_url else []),
                                   stdout=subprocess.PIPE, text=True)
        processes.append(process)
        ports = re.search(r"OTLP on \S+:(\d+), API on \S+:(\d+)", process.stdout.readline())
        assert ports, "the receiver did not announce its ports"
        return SimpleNamespace(otlp_port=int(ports[1]), api_port=int(ports[2]))

    yield start
    for process in processes:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=10)
        process.stdout.close()


@pytest.fixture
def receiver(start_receiver):
    return start_receiver()


@pytest.fixture
def replay(receiver):
    return Replay(f"http://127.0.0.1:{receiver.otlp_port}")


@pytest.fixture
def api(receiver):
    def get(path):
        with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}{path}", timeout=10) as response:
            return json.load(response)
    return get
