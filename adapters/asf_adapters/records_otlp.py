"""Records Adapter that exports each event to the Console's receiver as OTLP/HTTP (ADR 0017).

  append --stream S [--run N]   body: one JSON event

Stateless, one process per event. A `started` event becomes an OTLP log record and a `finished` event a
complete span (start = now - duration), both with the event's `trace`, `id` and `parent`, so the receiver
pairs them; every other event is a log record. The endpoint is $OTEL_EXPORTER_OTLP_ENDPOINT; an unreachable
receiver is an error.
"""

import time
from typing import cast

from . import common as _common
from . import otlp as _otlp
from .common import Args, Json, RequestError

OK_OUTCOMES = ("ok", "green", "succeeded", "advanced")


def task_of(stream: str) -> str | None:
    return stream[len("task/") :] if stream.startswith("task/") else None


def attributes(stream: str, run: str | None, event: Json) -> list[Json]:
    fields = {k: v for k, v in event.items() if k not in ("trace", "run")}
    return _otlp.flatten("asf", {"task": task_of(stream), "stream": stream, "run": run, **fields})


def append(args: Args) -> Json:
    stream = args.get("stream", "")
    if not stream:
        raise RequestError("append needs --stream")
    body = _common.read_body()
    if not isinstance(body, dict) or "kind" not in body:
        raise RequestError("the body must be an event with a kind")
    event = cast("Json", body)
    run = args.get("run")
    now = time.time()
    ids = {"traceId": event["trace"]} if event.get("trace") else {}
    if event["kind"] == "finished":
        end = int(now * 1e9)
        span: Json = {
            **ids,
            "spanId": event["id"],
            "name": f"{event['span']}:{event['name']}",
            "kind": 1,
            "startTimeUnixNano": str(end - int(event["duration"] * 1e9)),
            "endTimeUnixNano": str(end),
            "attributes": attributes(stream, run, event),
            "status": {"code": 1 if event["outcome"] in OK_OUTCOMES else 2},
        }
        if event.get("parent"):
            span["parentSpanId"] = event["parent"]
        _otlp.post("/v1/traces", _otlp.traces([span]))
    else:
        log: Json = {
            **ids,
            "timeUnixNano": str(int(now * 1e9)),
            "severityText": "INFO",
            "body": {"stringValue": event["kind"]},
            "attributes": attributes(stream, run, event),
        }
        if event["kind"] == "started":
            log["spanId"] = event["id"]
        _otlp.post("/v1/logs", _otlp.logs([log]))
    return {}


def main() -> None:
    _common.main({"append": append})
