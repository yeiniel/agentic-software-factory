"""Receiver tests replay recorded Factory events through the real OTLP Records Adapter into a live receiver."""
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from asf_console.receiver import Receiver
from asf_console.store import Store

RECORDS_OTLP = Path(__file__).parent.parent.parent / "adapters" / "records-otlp"


class Replay:
    """Emits events the way the core does (docs/adapters/README.md), one Adapter process per event."""

    def __init__(self, otlp_url):
        self.env = {**os.environ, "OTEL_EXPORTER_OTLP_ENDPOINT": otlp_url}

    def append(self, task, event, run=None):
        args = [sys.executable, str(RECORDS_OTLP), "append", "--stream", f"task/{task}" if task else "factory"]
        if run is not None:
            args += ["--run", str(run)]
        done = subprocess.run(args, input=json.dumps(event), text=True, capture_output=True, env=self.env)
        assert done.returncode == 0, done.stderr


class Script:
    def __init__(self, replay, task):
        self.replay, self.task = replay, task
        self.trace = hashlib.sha256(task.encode()).hexdigest()[:32]
        self.spans = {}

    def event(self, kind, run=None, **data):
        self.replay.append(self.task, {"kind": kind, "run": run, "trace": self.trace, **data}, run)

    def open(self, kind, name, parent=None, run=None, **attrs):
        span = secrets.token_hex(8)
        self.spans[span] = (kind, name, parent, run, attrs)
        self.event("started", run, id=span, parent=parent, span=kind, name=name, **attrs)
        return span

    def close(self, span, outcome="ok", duration=1.0):
        kind, name, parent, run, attrs = self.spans[span]
        self.event("finished", run, id=span, parent=parent, span=kind, name=name, **attrs,
                   duration=duration, outcome=outcome)

    def status(self, status, **extra):
        self.event("task-status", status=status, **extra)

    def step(self, kind, name, parent, run, outcome="ok", duration=1.0, **attrs):
        span = self.open(kind, name, parent, run, **attrs)
        self.close(span, outcome, duration)
        return span


def attempt(s, run, loop, number, parent, outcome, role, usage=None, activities=(), duration=2.0):
    loop_id = parent
    at = s.open("attempt", str(number), loop_id, run)
    agent = s.open("activity", "agent", at, run, role=role)
    s.event("agent", run, role=role, exit_status=0, output=f"{role} output", **({"usage": usage} if usage else {}))
    s.close(agent, "ok", duration)
    for name, result, took in activities:
        s.step("activity", name, at, run, result, took)
    s.close(at, outcome, duration + 1)
    s.event("attempt", run, loop=loop, attempt=number, result=outcome)
    return at


def green_task(replay, task="r/green"):
    s = Script(replay, task)
    s.event("task-received", repo="r")
    s.status("running")
    s.event("run-started", 1, roles=["implementor", "acceptance-writer"])
    run = s.open("run", "1", None, 1)
    w = s.open("loop", "writer", run, 1)
    attempt(s, 1, "writer", 1, w, "green", "acceptance-writer",
            {"turns": 4, "tool_calls": 3, "input_tokens": 1000, "output_tokens": 200},
            [("validate", "green", 5.0)])
    s.close(w, "succeeded", 10)
    i = s.open("loop", "implementor", run, 1)
    attempt(s, 1, "implementor", 1, i, "green", "implementor",
            {"turns": 6, "tool_calls": 5, "input_tokens": 3000, "output_tokens": 600}, duration=8.0)
    s.close(i, "succeeded", 12)
    s.step("activity", "integrate", run, 1, "green", 7.0)
    s.step("activity", "publish", run, 1, "advanced", 1.0)
    s.close(run, "green", 30)
    s.event("run-finished", 1, outcome={"result": "green"})
    s.status("done", commit="c9")
    return s


def blocked_task(replay, task="r/blocked"):
    """The Implementor's loop is exhausted after two crashes; the second attempt follows the Feedback."""
    s = Script(replay, task)
    s.event("task-received", repo="r")
    s.status("running")
    run = s.open("run", "1", None, 1)
    i = s.open("loop", "implementor", run, 1)
    attempt(s, 1, "implementor", 1, i, "crashed", "implementor")
    s.event("loop-feedback", 1, loop="implementor", attempt=1, feedback="Your last attempt crashed: boom")
    attempt(s, 1, "implementor", 2, i, "crashed", "implementor")
    s.close(i, "exhausted", 6)
    s.event("loop-exhausted", 1, loop="implementor")
    s.close(run, "red", 8)
    s.status("blocked", reason="loop-exhausted")
    return s


def retried_task(replay, task="r/retried"):
    """The integration fails in Run 1; Run 2 succeeds."""
    s = Script(replay, task)
    s.event("task-received", repo="r")
    s.status("running")
    run1 = s.open("run", "1", None, 1)
    s.step("activity", "integrate", run1, 1, "suite", 4.0)
    s.close(run1, "red", 10)
    s.event("feedback", 1, feedback={"implementor": "the suite failed: greeting is empty"})
    s.status("running")
    run2 = s.open("run", "2", None, 2)
    s.step("activity", "integrate", run2, 2, "green", 4.0)
    s.close(run2, "green", 10)
    s.status("done", commit="c5")
    return s


@pytest.fixture
def receiver(tmp_path):
    store = Store(tmp_path / "console.db")
    server = Receiver(store, ("127.0.0.1", 0), ("127.0.0.1", 0))
    server.start()
    yield server
    server.stop()


@pytest.fixture
def replay(receiver):
    return Replay(f"http://127.0.0.1:{receiver.otlp_port}")


@pytest.fixture
def api(receiver):
    def get(path):
        with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}{path}", timeout=10) as response:
            return json.load(response)
    return get
