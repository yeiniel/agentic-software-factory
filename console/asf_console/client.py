"""A client of the receiver's API (the TUI's only link to the Console)."""
import json
import urllib.parse
import urllib.request

DEFAULT_URL = "http://127.0.0.1:4319"


class Client:
    def __init__(self, base=DEFAULT_URL):
        self.base = base.rstrip("/")

    def get(self, path, **query):
        url = f"{self.base}{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)

    def events(self):
        """Yield the live stream's messages until the connection ends."""
        with urllib.request.urlopen(f"{self.base}/stream", timeout=60) as stream:
            for line in stream:
                if line.startswith(b"data:"):
                    yield json.loads(line[5:])
