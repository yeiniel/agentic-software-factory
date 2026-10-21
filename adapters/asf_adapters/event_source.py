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
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import NoReturn
from urllib.parse import parse_qs, urlparse

from . import common as _common
from .common import Args, Json

ZERO = "0" * 40
printing = threading.Lock()


def emit(event: Json) -> None:
    with printing:
        print(json.dumps(event), flush=True)


def events_for(repo: str, lines: list[str]) -> Iterator[Json]:
    for line in lines:
        old, new, ref = line.split()
        if new == ZERO:
            continue
        if ref.startswith("refs/issues/") and old == ZERO:
            yield {"type": "task", "task": f"{repo}/{ref.removeprefix('refs/issues/')}", "repo": repo}
        elif ref == "refs/heads/main":
            yield {"type": "main-push", "repo": repo, "commit": new}


def accept(path: str, repo: str, body: str) -> int:
    """Emit the events of a hook's push lines; the HTTP status to answer with."""
    if path != "/push" or not repo:
        return HTTPStatus.BAD_REQUEST
    try:
        for event in events_for(repo, body.splitlines()):
            emit(event)
    except ValueError:
        return HTTPStatus.BAD_REQUEST
    return HTTPStatus.NO_CONTENT


class Hook(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        url = urlparse(self.path)
        repo = parse_qs(url.query).get("repo", [""])[0]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        self.send_response(accept(url.path, repo, body))
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002  (the base class's signature)
        pass


class Server(ThreadingHTTPServer):
    def server_bind(self) -> None:  # skip HTTPServer's reverse lookup of our own name, which can stall
        socketserver.TCPServer.server_bind(self)
        self.server_port = self.socket.getsockname()[1]


def listen(_args: Args) -> NoReturn:
    port = int(os.environ.get("EVENT_SOURCE_PORT", "8765"))
    server = Server(("0.0.0.0", port), Hook)  # noqa: S104  (the hook reaches us from another container)
    print(f"listening on port {server.server_port}", file=sys.stderr, flush=True)
    while True:
        server.handle_request()


def main() -> None:
    _common.main({"listen": listen})
