"""Following a Pi session while an Environment runs (internal to the Runner).

Reads what a run appends to the session files under a Context's `session/`, forwards each entry to the
Console as an OTLP log record linked to the attempt, and counts turns, tool calls and tokens. The Console is
best effort: an unreachable endpoint never fails the run.
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from . import otlp as _otlp
from .common import Json, RequestError

POLL = 0.5
TRACEPARENT_PARTS = 4


def as_dict(value: object) -> Json | None:
    return cast("Json", value) if isinstance(value, dict) else None


class Session:
    def __init__(self, directory: str | Path) -> None:
        self.dir = Path(directory)
        self.offsets = {path: path.stat().st_size for path in self.dir.rglob("*.jsonl")}  # earlier runs' lines
        self.stats = {"turns": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0}
        self.lock = threading.Lock()

    def poll(self) -> list[str]:
        """The complete lines written since the last poll; a line still being written is left for the next."""
        lines: list[str] = []
        with self.lock:
            for path in sorted(self.dir.rglob("*.jsonl")):
                with path.open("rb") as f:
                    f.seek(self.offsets.get(path, 0))
                    data = f.read()
                complete = data[: data.rfind(b"\n") + 1]
                self.offsets[path] = self.offsets.get(path, 0) + len(complete)
                for line in complete.decode(errors="replace").splitlines():
                    if line.strip():
                        lines.append(line)
                        self.count(line)
        return lines

    def count(self, line: str) -> None:
        try:
            entry = as_dict(json.loads(line))
        except ValueError:
            return
        message = as_dict(entry.get("message")) if entry and entry.get("type") == "message" else None
        if message is None or message.get("role") != "assistant":
            return
        self.stats["turns"] += 1
        content = message.get("content")
        if isinstance(content, list):
            parts = (as_dict(part) for part in cast("list[object]", content))
            self.stats["tool_calls"] += sum(1 for part in parts if part and part.get("type") == "toolCall")
        usage = as_dict(message.get("usage")) or {}
        for key, field in (("input_tokens", "input"), ("output_tokens", "output")):
            value = usage.get(field)
            self.stats[key] += value if isinstance(value, int) else 0

    def usage(self) -> dict[str, int] | None:
        """The counts, or None when the session had no model turn."""
        return dict(self.stats) if self.stats["turns"] else None


def nanos(line: str) -> int:
    try:
        stamp = datetime.fromisoformat(json.loads(line)["timestamp"])
        return int(stamp.timestamp() * 1e9)
    except (ValueError, KeyError, TypeError, AttributeError):
        return time.time_ns()


def log_record(line: str, traceparent: str | None) -> Json:
    record: Json = {
        "timeUnixNano": str(nanos(line)),
        "severityText": "INFO",
        "body": {"stringValue": line},
        "attributes": [{"key": "asf.source", "value": {"stringValue": "transcript"}}],
    }
    parts = (traceparent or "").split("-")
    if len(parts) == TRACEPARENT_PARTS:
        record["traceId"], record["spanId"] = parts[1], parts[2]
    return record


class Forwarder:
    """Polls a Session on a thread and posts new entries until stopped; best effort."""

    def __init__(self, session: Session, traceparent: str | None) -> None:
        self.session, self.traceparent = session, traceparent
        self.pending: list[Json] = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def __enter__(self) -> Self:
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            self.thread.start()
        return self

    def __exit__(
        self, kind: type[BaseException] | None, error: BaseException | None, trace: TracebackType | None
    ) -> None:
        if self.thread.is_alive():
            self.stop.set()
            self.thread.join(timeout=_otlp.TIMEOUT * 2)

    def loop(self) -> None:
        while True:
            stopping = self.stop.wait(POLL)
            self.pending += [log_record(line, self.traceparent) for line in self.session.poll()]
            if self.pending:
                try:
                    _otlp.post("/v1/logs", _otlp.logs(self.pending))
                    self.pending = []
                except RequestError:
                    pass  # the full transcript stays in the Run Context; try again next time
            if stopping:
                return
