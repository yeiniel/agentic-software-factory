"""The OTLP Records implementation: started events arrive as logs, finished ones as complete spans."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

TRACE, SPAN, PARENT = "a" * 32, "b" * 16, "c" * 16


@pytest.fixture
def receiver():
    got = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            got.append((self.path, body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", got
    server.shutdown()
    server.server_close()


def attrs(record):
    return {a["key"]: next(iter(a["value"].values())) for a in record["attributes"]}


def first_log(got):
    path, body = got[-1]
    assert path == "/v1/logs"
    return body["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]


def test_a_started_event_is_exported_as_a_log_record_with_its_ids(exe, env, receiver):
    url, got = receiver
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    exe("records-otlp").ok(
        "append",
        {
            "kind": "started",
            "run": 1,
            "trace": TRACE,
            "id": SPAN,
            "parent": PARENT,
            "span": "activity",
            "name": "agent",
        },
        stream="task/r/t1",
        run=1,
    )

    log = first_log(got)
    assert log["traceId"] == TRACE and log["spanId"] == SPAN
    a = attrs(log)
    assert (a["asf.kind"], a["asf.task"], a["asf.parent"], a["asf.name"]) == ("started", "r/t1", PARENT, "agent")
    assert a["asf.run"] == "1" or a["asf.run"] == 1


def test_a_finished_event_is_exported_as_a_complete_span_with_the_same_ids(exe, env, receiver):
    url, got = receiver
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    exe("records-otlp").ok(
        "append",
        {
            "kind": "finished",
            "run": 1,
            "trace": TRACE,
            "id": SPAN,
            "parent": PARENT,
            "span": "activity",
            "name": "agent",
            "duration": 2.5,
            "outcome": "crashed",
        },
        stream="task/r/t1",
        run=1,
    )

    path, body = got[-1]
    assert path == "/v1/traces"
    span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert (span["traceId"], span["spanId"], span["parentSpanId"]) == (TRACE, SPAN, PARENT)
    assert int(span["endTimeUnixNano"]) - int(span["startTimeUnixNano"]) == 2_500_000_000
    assert attrs(span)["asf.outcome"] == "crashed" and attrs(span)["asf.task"] == "r/t1"
    assert span["status"]["code"] == 2  # an outcome other than ok/green is an error


def test_other_events_are_logs_with_nested_fields_flattened(exe, env, receiver):
    url, got = receiver
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    exe("records-otlp").ok(
        "append",
        {"kind": "agent", "run": 2, "trace": TRACE, "role": "implementor", "usage": {"turns": 3, "tool_calls": 4}},
        stream="task/r/t1",
        run=2,
    )

    a = attrs(first_log(got))
    assert a["asf.kind"] == "agent" and a["asf.usage.turns"] == "3" and a["asf.usage.tool_calls"] == "4"


def test_a_factory_stream_event_has_no_task(exe, env, receiver):
    url, got = receiver
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    exe("records-otlp").ok("append", {"kind": "main-push", "commit": "abc"}, stream="factory")

    assert "asf.task" not in attrs(first_log(got))


def test_an_unreachable_receiver_is_an_error(exe, env):
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:9"
    assert exe("records-otlp").run("append", {"kind": "x"}, stream="factory").returncode != 0


def test_a_missing_endpoint_is_an_error(exe, env):
    env.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    assert exe("records-otlp").run("append", {"kind": "x"}, stream="factory").returncode != 0


def test_append_without_a_stream_fails_and_unknown_operations_fail(exe, env, receiver):
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = receiver[0]
    assert exe("records-otlp").run("append", {"kind": "x"}).returncode != 0
    assert exe("records-otlp").run("no-such-op").returncode != 0
