"""Model server state: scraped only while a client is connected; unreachable means unavailable."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from asf_console.model import ModelServer

METRICS = """# HELP llamacpp:requests_deferred x
llamacpp:requests_processing 1
llamacpp:requests_deferred 2
llamacpp:predicted_tokens_seconds 41.5
"""
SLOTS = [{"id": 0, "is_processing": True}, {"id": 1, "is_processing": False}]


@pytest.fixture
def llama():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            body = METRICS if self.path == "/metrics" else json.dumps(SLOTS)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", hits
    server.shutdown()


def wait(condition):
    for _ in range(100):
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_slots_queue_and_speed_are_read_from_the_model_server(llama):
    model = ModelServer(llama[0])
    model.scrape()
    assert model.state["slots"] == {"total": 2, "busy": 1}
    assert model.state["queue_depth"] == 2 and model.state["tokens_per_second"] == 41.5


def test_an_unreachable_model_server_is_unavailable(llama):
    model = ModelServer("http://127.0.0.1:9")
    model.scrape()
    assert model.state == {"available": False}


def test_nothing_is_scraped_until_a_client_connects(llama):
    url, hits = llama
    model = ModelServer(url, interval=0.1)
    model.start()
    time.sleep(0.4)
    assert hits == [] and model.state == {"available": False}
    model.connected(+1)
    assert wait(lambda: model.state.get("available"))
    model.connected(-1)
    model.stop()
