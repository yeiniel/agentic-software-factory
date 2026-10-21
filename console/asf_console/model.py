"""The model server's state, scraped from llama-server's `/metrics` and `/slots` while a client is connected."""

import json
import threading
import time
import urllib.request
from collections.abc import Callable
from contextlib import suppress
from typing import Any

Json = dict[str, Any]


def fetch(url: str, timeout: float = 3) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode()


def prometheus(text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.rpartition(" ")
            with suppress(ValueError):
                values[name.split("{")[0]] = float(value)
    return values


class ModelServer:
    """`state` is what the metrics view shows; `available` is false until a scrape succeeds."""

    def __init__(self, url: str | None, interval: float = 3.0, get: Callable[[str], str] = fetch) -> None:
        self.url, self.interval, self.get = (url or "").rstrip("/"), interval, get
        self.state: Json = {"available": False}
        self.counters: tuple[float, float] | None = None  # (predicted tokens, decode seconds) at the last scrape
        self.rate: float | None = None
        self.clients = 0
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self) -> None:
        if self.url:
            self.thread.start()

    def connected(self, delta: int) -> None:
        with self.lock:
            self.clients += delta
        self.wake.set()

    def scrape(self) -> None:
        try:
            values = prometheus(self.get(f"{self.url}/metrics"))
            slots = json.loads(self.get(f"{self.url}/slots"))
        except (OSError, ValueError):
            self.state = {"available": False}
            return
        self.rate = self.decode_rate(values)
        self.state = {
            "available": True,
            "updated": time.time(),
            "slots": {"total": len(slots), "busy": sum(1 for s in slots if s.get("is_processing"))},
            "queue_depth": int(values.get("llamacpp:requests_deferred", 0)),
            "tokens_per_second": self.rate,
        }

    def decode_rate(self, values: dict[str, float]) -> float | None:
        """Tokens per second of decoding since the last scrape, per slot.

        llama-server's own `predicted_tokens_seconds` gauge reads 0 whenever it is sampled mid-request, so use
        the counters.
        """
        tokens_now = values.get("llamacpp:tokens_predicted_total")
        seconds_now = values.get("llamacpp:tokens_predicted_seconds_total")
        before = self.counters
        self.counters = None if tokens_now is None or seconds_now is None else (tokens_now, seconds_now)
        if self.counters is None or before is None:
            return self.rate
        tokens, seconds = self.counters[0] - before[0], self.counters[1] - before[1]
        return tokens / seconds if seconds > 0 and tokens >= 0 else self.rate

    def loop(self) -> None:
        while True:
            if self.clients > 0:
                self.scrape()
            self.wake.wait(self.interval)
            self.wake.clear()
