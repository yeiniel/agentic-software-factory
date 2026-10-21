"""Fixtures: a live receiver and the real OTLP Records Adapter replaying Factory events into it."""
import json
import urllib.request

import pytest
from replay import Replay

from asf_console.receiver import Receiver
from asf_console.store import Store


@pytest.fixture
def receiver(tmp_path):
    store = Store(tmp_path / "console.db")
    server = Receiver(store, ("127.0.0.1", 0), ("127.0.0.1", 0))
    server.start()
    yield server
    server.stop()
    store.close()


@pytest.fixture
def replay(receiver):
    return Replay(f"http://127.0.0.1:{receiver.otlp_port}")


@pytest.fixture
def api(receiver):
    def get(path):
        with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}{path}", timeout=10) as response:
            return json.load(response)
    return get
