"""The Runner forwards the Pi session to the Console while an agentic Environment runs (spec 0006).

Podman is replaced by a script standing in for the container: it appends to the session as an Agent would.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from helpers import Exe

TRACEPARENT = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
FAKE_PODMAN = r"""#!/bin/sh
case "$1" in
  image) exit 0 ;;
  run)
    for a in "$@"; do case "$a" in *:/ctx) ctx=${a%:/ctx} ;; esac; done
    mkdir -p "$ctx/session"
    echo '{"type":"session"}' >> "$ctx/session/s.jsonl"
    echo "$FAKE_LINES" | while IFS= read -r line; do echo "$line" >> "$ctx/session/s.jsonl"; sleep 0.7; done
    echo "container output"
    exit "${FAKE_EXIT:-0}" ;;
esac
"""


def message(role, content, stamp="2026-10-21T10:00:01.500Z", **extra):
    return json.dumps({"type": "message", "timestamp": stamp, "message": {"role": role, "content": content, **extra}})


LINES = [message("assistant", [{"type": "text", "text": "reading"}, {"type": "toolCall", "name": "read"}],
                 usage={"input": 100, "output": 20}),
         message("toolResult", [{"type": "text", "text": "file"}]),
         message("assistant", [{"type": "text", "text": "done"}], usage={"input": 150, "output": 30})]


@pytest.fixture
def receiver():
    got = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", got
    server.shutdown()


@pytest.fixture
def runner(env, tmp_path):
    podman = tmp_path / "podman"
    podman.write_text(FAKE_PODMAN)
    podman.chmod(0o755)
    env.update(PODMAN=str(podman), FAKE_LINES="\n".join(LINES))
    return Exe("runner", env)


@pytest.fixture
def ctx(tmp_path):
    ctx = tmp_path / "ctx"
    (ctx / "cwd").mkdir(parents=True)
    (ctx / "cwd" / "Containerfile").write_text("FROM scratch\n")
    return ctx


def forwarded(got):
    records = [r for path, body in got if path == "/v1/logs"
               for r in body["resourceLogs"][0]["scopeLogs"][0]["logRecords"]]
    return records


def run(runner, ctx, **extra):
    return runner.ok("run", type="agentic", context=ctx, timeout=60, **extra)


def test_each_session_entry_is_forwarded_in_order_linked_to_the_attempt(runner, ctx, receiver):
    url, got = receiver
    runner.env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    run(runner, ctx, traceparent=TRACEPARENT)

    records = forwarded(got)
    bodies = [json.loads(r["body"]["stringValue"]) for r in records]
    assert [b["message"]["role"] for b in bodies if b["type"] == "message"] == ["assistant", "toolResult", "assistant"]
    assert {r["traceId"] for r in records} == {"a" * 32} and {r["spanId"] for r in records} == {"b" * 16}
    assert all({"key": "asf.source", "value": {"stringValue": "transcript"}} in r["attributes"] for r in records)
    assert records[1]["timeUnixNano"] == "1792576801500000000"


def test_entries_arrive_while_the_environment_is_still_running(runner, ctx, receiver):
    url, got = receiver
    runner.env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    seen_before_exit = []

    def watch():
        import time
        for _ in range(40):
            time.sleep(0.1)
            if forwarded(got):
                seen_before_exit.append(len(forwarded(got)))
                return

    watcher = threading.Thread(target=watch)
    watcher.start()
    run(runner, ctx, traceparent=TRACEPARENT)
    watcher.join()
    assert seen_before_exit and seen_before_exit[0] < len(forwarded(got))


def test_a_resumed_session_forwards_only_what_this_run_added(runner, ctx, receiver):
    url, got = receiver
    runner.env["OTEL_EXPORTER_OTLP_ENDPOINT"] = url
    (ctx / "session").mkdir()
    (ctx / "session" / "s.jsonl").write_text(message("assistant", [{"type": "text", "text": "OLD"}]) + "\n")
    run(runner, ctx, traceparent=TRACEPARENT)

    assert not any("OLD" in r["body"]["stringValue"] for r in forwarded(got))


def test_an_unreachable_endpoint_does_not_fail_the_run(runner, ctx):
    runner.env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:9"
    result = run(runner, ctx, traceparent=TRACEPARENT)

    assert result["exit_status"] == 0 and "container output" in result["output"]


def test_without_an_endpoint_nothing_is_forwarded_and_the_run_is_unaffected(runner, ctx):
    runner.env.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    assert run(runner, ctx)["exit_status"] == 0


def test_the_result_reports_turns_tool_calls_and_tokens_of_this_run(runner, ctx):
    runner.env.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    assert run(runner, ctx)["usage"] == {"turns": 2, "tool_calls": 1, "input_tokens": 250, "output_tokens": 50}
