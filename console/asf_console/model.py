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
        self.clients = 0
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stopped = False
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self):
        if self.url:
            self.thread.start()

    def stop(self):
        self.stopped = True
        self.wake.set()

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
        self.state = {"available": True, "updated": time.time(),
                      "slots": {"total": len(slots), "busy": sum(1 for s in slots if s.get("is_processing"))},
                      "queue_depth": int(values.get("llamacpp:requests_deferred", 0)),
                      "tokens_per_second": values.get("llamacpp:predicted_tokens_seconds")}

    def loop(self):
        while not self.stopped:
            if self.clients > 0:
                self.scrape()
            self.wake.wait(self.interval)
            self.wake.clear()
