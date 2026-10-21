"""Following a Pi session while an Environment runs (internal to the Runner).

Reads what a run appends to the session files under a Context's `session/`, forwards each entry to the
Console as an OTLP log record linked to the attempt, and counts turns, tool calls and tokens. The Console is
best effort: an unreachable endpoint never fails the run.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from . import otlp as _otlp
from .common import Failure

POLL = 0.5


class Session:
    def __init__(self, directory):
        self.dir = Path(directory)
        self.offsets = {path: path.stat().st_size for path in self.dir.rglob("*.jsonl")}  # earlier runs' lines
        self.stats = {"turns": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.lock = threading.Lock()

    def poll(self):
        """The complete lines written since the last poll; a line still being written is left for the next."""
        lines = []
        with self.lock:
            for path in sorted(self.dir.rglob("*.jsonl")):
                with open(path, "rb") as f:
                    f.seek(self.offsets.get(path, 0))
                    data = f.read()
                complete = data[:data.rfind(b"\n") + 1]
                self.offsets[path] = self.offsets.get(path, 0) + len(complete)
                for line in complete.decode(errors="replace").splitlines():
                    if line.strip():
                        lines.append(line)
                        self.count(line)
        return lines

    def count(self, line):
        try:
            entry = json.loads(line)
            message = entry["message"] if entry.get("type") == "message" else None
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        if not isinstance(message, dict) or message.get("role") != "assistant":
            return
        self.stats["turns"] += 1
        content = message.get("content")
        self.stats["tool_calls"] += sum(1 for part in content if isinstance(part, dict)
                                        and part.get("type") == "toolCall") if isinstance(content, list) else 0
        usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
        for key, field in (("input_tokens", "input"), ("output_tokens", "output")):
            value = usage.get(field)
            self.stats[key] += value if isinstance(value, int) else 0

    def usage(self):
        """The counts, or None when the session had no model turn."""
        return dict(self.stats) if self.stats["turns"] else None


def nanos(line):
    try:
        stamp = datetime.fromisoformat(json.loads(line)["timestamp"].replace("Z", "+00:00"))
        return int(stamp.timestamp() * 1e9)
    except (ValueError, KeyError, TypeError, AttributeError):
        return int(datetime.now().timestamp() * 1e9)


def log_record(line, traceparent):
    record = {"timeUnixNano": str(nanos(line)), "severityText": "INFO", "body": {"stringValue": line},
              "attributes": [{"key": "asf.source", "value": {"stringValue": "transcript"}}]}
    parts = (traceparent or "").split("-")
    if len(parts) == 4:
        record["traceId"], record["spanId"] = parts[1], parts[2]
    return record


class Forwarder:
    """Polls a Session on a thread and posts new entries until stopped; best effort."""

    def __init__(self, session, traceparent):
        self.session, self.traceparent = session, traceparent
        self.pending = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def __enter__(self):
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.thread.start()
        return self

    def __exit__(self, *exc):
        if self.thread.is_alive():
            self.stop.set()
            self.thread.join(timeout=_otlp.TIMEOUT * 2)

    def loop(self):
        while True:
            stopping = self.stop.wait(POLL)
            self.pending += [log_record(line, self.traceparent) for line in self.session.poll()]
            if self.pending:
                try:
                    _otlp.post("/v1/logs", _otlp.logs(self.pending))
                    self.pending = []
                except Failure:
                    pass  # the full transcript stays in the Run Context; try again next time
            if stopping:
                return
