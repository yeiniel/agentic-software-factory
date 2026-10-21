"""Event Source Adapter: listens for the git server's push hook and prints one JSON event per line.

  listen    HTTP on $EVENT_SOURCE_PORT (default 8765); the hook POSTs `old new ref` lines to
            /push?repo=R. A new `refs/issues/<id>` is a Task (`<repo>/<id>`); a push to `main` is a
            main-push. Status changes the Factory pushes to existing issues are not events.
"""
import json
import os
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import common as _common

ZERO = "0" * 40
printing = threading.Lock()


def emit(event):
    with printing:
        print(json.dumps(event), flush=True)


def events_for(repo, lines):
    for line in lines:
        old, new, ref = line.split()
        if new == ZERO:
            continue
        if ref.startswith("refs/issues/") and old == ZERO:
            yield {"type": "task", "task": f"{repo}/{ref.removeprefix('refs/issues/')}", "repo": repo}
        elif ref == "refs/heads/main":
            yield {"type": "main-push", "repo": repo, "commit": new}


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        url = urlparse(self.path)
        repo = parse_qs(url.query).get("repo", [""])[0]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        try:
            if url.path != "/push" or not repo:
                raise ValueError
            for event in events_for(repo, body.splitlines()):
                emit(event)
        except ValueError:
            self.send_response(400)
        else:
            self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


class Server(ThreadingHTTPServer):
    def server_bind(self):  # skip HTTPServer's reverse lookup of our own name, which can stall
        socketserver.TCPServer.server_bind(self)
        self.server_port = self.socket.getsockname()[1]


def listen(a):
    server = Server(("0.0.0.0", int(os.environ.get("EVENT_SOURCE_PORT", "8765"))), Hook)
    print(f"listening on port {server.server_port}", file=sys.stderr, flush=True)
    server.serve_forever()



def main():
    _common.main({"listen": listen})
