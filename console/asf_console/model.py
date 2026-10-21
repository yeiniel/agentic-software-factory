"""The model server's state, scraped from llama-server's `/metrics` and `/slots` while a client is connected."""
import json
import threading
import time
import urllib.request


def fetch(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode()


def prometheus(text):
    values = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.rpartition(" ")
            try:
                values[name.split("{")[0]] = float(value)
            except ValueError:
                pass
    return values


class ModelServer:
    """`state` is what the metrics view shows; `available` is false until a scrape succeeds."""

    def __init__(self, url, interval=3.0, get=fetch):
        self.url, self.interval, self.get = (url or "").rstrip("/"), interval, get
        self.state = {"available": False}
        self.counters = None  # (predicted tokens, decode seconds) at the previous scrape
        self.rate = None
        self.clients = 0
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self):
        if self.url:
            self.thread.start()

    def connected(self, delta):
        with self.lock:
            self.clients += delta
        self.wake.set()

    def scrape(self):
        try:
            values = prometheus(self.get(f"{self.url}/metrics"))
            slots = json.loads(self.get(f"{self.url}/slots"))
        except (OSError, ValueError):
            self.state = {"available": False}
            return
        self.rate = self.decode_rate(values)
        self.state = {"available": True, "updated": time.time(),
                      "slots": {"total": len(slots), "busy": sum(1 for s in slots if s.get("is_processing"))},
                      "queue_depth": int(values.get("llamacpp:requests_deferred", 0)),
                      "tokens_per_second": self.rate}

    def decode_rate(self, values):
        """Tokens per second of decoding since the last scrape, per slot. llama-server's own
        `predicted_tokens_seconds` gauge reads 0 whenever it is sampled mid-request, so use the counters."""
        now = (values.get("llamacpp:tokens_predicted_total"), values.get("llamacpp:tokens_predicted_seconds_total"))
        before, self.counters = self.counters, now
        if None in now or before is None or None in before:
            return self.rate
        tokens, seconds = now[0] - before[0], now[1] - before[1]
        return tokens / seconds if seconds > 0 and tokens >= 0 else self.rate

    def loop(self):
        while True:
            if self.clients > 0:
                self.scrape()
            self.wake.wait(self.interval)
            self.wake.clear()
