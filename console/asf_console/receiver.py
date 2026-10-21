"""The receiver: OTLP/HTTP (JSON) in, a local read-only HTTP API with a live stream out.

  python -m asf_console.receiver [--db FILE] [--otlp-port 4318] [--api-port 4319] [--model-url URL]

Two listeners share one store: OTLP for the Factory and the Runner, and the API for clients (put it on
loopback only). GET /api/tasks, /api/task?id=T, /api/task/log?id=T[&after=SEQ], /api/metrics, and /stream
(server-sent events: `{"type": "changed", "task": T}` after every write).
"""
import argparse
import json
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .metrics import metrics
from .model import ModelServer
from .store import Store

KEEPALIVE = 15


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(routes):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def dispatch(self, method):
            url = urlparse(self.path)
            handler = routes.get((method, url.path))
            if handler is None:
                return self.reply(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                result = handler(self, {k: v[0] for k, v in parse_qs(url.query).items()}, body)
            except (ValueError, KeyError) as error:
                return self.reply(400, {"error": str(error)})
            if result is not None:
                self.reply(200, result)

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")
    return Handler


class Receiver:
    def __init__(self, store, otlp_address, api_address, model_url=None, model_interval=3.0):
        self.store = store
        self.model = ModelServer(model_url, model_interval)
        self.subscribers = []
        self.lock = threading.Lock()
        store.listeners.append(self.publish)
        otlp = {("POST", "/v1/logs"): self.otlp(store.ingest_logs), ("POST", "/v1/traces"): self.otlp(store.ingest_traces)}
        api = {("GET", "/api/tasks"): lambda h, q, b: {"tasks": store.tasks()},
               ("GET", "/api/task"): self.task, ("GET", "/api/task/log"): self.log,
               ("GET", "/api/metrics"): self.metrics, ("GET", "/stream"): self.stream}
        self.otlp_server = Server(otlp_address, make_handler(otlp))
        self.api_server = Server(api_address, make_handler(api))
        self.otlp_port, self.api_port = self.otlp_server.server_port, self.api_server.server_port

    @staticmethod
    def otlp(ingest):
        def handle(handler, query, body):
            ingest(body or {})
            return {}
        return handle

    def task(self, handler, query, body):
        task = query["id"]
        return {"task": task, "spans": self.store.tree(task)}

    def log(self, handler, query, body):
        return {"log": self.store.log(query["id"], int(query.get("after", 0)))}

    def metrics(self, handler, query, body):
        return {**metrics(self.store), "model": self.model.state}

    def publish(self, task):
        with self.lock:
            for subscriber in self.subscribers:
                subscriber.put({"type": "changed", "task": task})

    def stream(self, handler, query, body):
        mailbox = queue.Queue()
        with self.lock:
            self.subscribers.append(mailbox)
        self.model.connected(+1)
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        try:
            handler.wfile.write(b'data: {"type": "hello"}\n\n')
            handler.wfile.flush()
            while True:
                try:
                    handler.wfile.write(b"data: " + json.dumps(mailbox.get(timeout=KEEPALIVE)).encode() + b"\n\n")
                except queue.Empty:
                    handler.wfile.write(b": keepalive\n\n")
                handler.wfile.flush()
        except OSError:
            pass
        finally:
            with self.lock:
                self.subscribers.remove(mailbox)
            self.model.connected(-1)

    def start(self):
        for server in (self.otlp_server, self.api_server):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        self.model.start()

    def stop(self):
        self.model.stop()
        for server in (self.otlp_server, self.api_server):
            server.shutdown()
            server.server_close()


def main():
    data = Path(os.environ.get("CONSOLE_DATA", "console-data"))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(data / "console.db"))
    parser.add_argument("--otlp-host", default="0.0.0.0")
    parser.add_argument("--otlp-port", type=int, default=4318)
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=4319)
    parser.add_argument("--model-url", default=os.environ.get("CONSOLE_MODEL_URL"))
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    receiver = Receiver(Store(args.db), (args.otlp_host, args.otlp_port), (args.api_host, args.api_port),
                        args.model_url)
    receiver.start()
    print(f"OTLP on {args.otlp_host}:{receiver.otlp_port}, API on {args.api_host}:{receiver.api_port}", flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
