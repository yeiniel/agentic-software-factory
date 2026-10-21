"""Model server state, seen through the receiver: scraped only while a client is connected."""

import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SLOTS = [{"id": 0, "is_processing": True}, {"id": 1, "is_processing": False}]


@pytest.fixture
def llama():
    """A model server whose decode counters advance by 60 tokens in 4 seconds on every scrape."""
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            scrapes = hits.count("/metrics")
            body = (
                (
                    f"# HELP llamacpp:requests_deferred x\nllamacpp:requests_deferred 2\n"
                    f"llamacpp:tokens_predicted_total {100 + 60 * scrapes}\n"
                    f"llamacpp:tokens_predicted_seconds_total {10 + 4 * scrapes}\n"
                    "not a metric line\nllamacpp:broken abc\n"
                )
                if self.path == "/metrics"
                else json.dumps(SLOTS)
            )
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", hits
    server.shutdown()
    server.server_close()


@pytest.fixture
def connect():
    """`connect(receiver)` opens a live stream and keeps it open until the test ends."""
    streams = []

    def open_stream(receiver):
        stream = urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/stream", timeout=10)
        stream.readline()  # the hello event: the client is registered
        streams.append(stream)

    yield open_stream
    for stream in streams:
        stream.close()


def metrics(receiver):
    with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/api/metrics", timeout=10) as response:
        return json.load(response)["model"]


def wait_for(condition):
    for _ in range(100):
        if value := condition():
            return value
        time.sleep(0.05)
    raise AssertionError("condition not met")


def test_slots_queue_and_speed_are_read_from_the_model_server(start_receiver, llama, connect):
    receiver = start_receiver(llama[0])

    connect(receiver)

    model = wait_for(lambda: (m := metrics(receiver))["available"] and m)
    assert model["slots"] == {"total": 2, "busy": 1}
    assert model["queue_depth"] == 2


def test_speed_is_the_decode_rate_between_scrapes_not_the_servers_gauge(start_receiver, llama, connect):
    receiver = start_receiver(llama[0])

    connect(receiver)
    wait_for(lambda: metrics(receiver)["available"])
    connect(receiver)  # a second client wakes the scraper for another scrape

    assert wait_for(lambda: metrics(receiver).get("tokens_per_second")) == 15.0


def test_an_unreachable_model_server_is_unavailable(start_receiver, connect):
    receiver = start_receiver("http://127.0.0.1:9")

    connect(receiver)

    time.sleep(0.3)
    assert metrics(receiver) == {"available": False}


def test_nothing_is_scraped_until_a_client_connects(start_receiver, llama, connect):
    url, hits = llama
    receiver = start_receiver(url)

    time.sleep(0.4)
    assert hits == [] and metrics(receiver) == {"available": False}
    connect(receiver)
    wait_for(lambda: metrics(receiver)["available"])


def test_without_a_model_server_the_model_is_unavailable(receiver, connect):
    connect(receiver)

    assert metrics(receiver) == {"available": False}
