"""Black-box harness: starts the Factory as a process wired to scripted stand-in Adapters."""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

STANDIN = Path(__file__).parent / "standins" / "standin.py"
PORTS = ["event-source", "task-store", "repo-host", "environment-builder", "runner", "records"]


class Outcome:
    def __init__(self, fixture, process):
        self.fixture = fixture
        self.exit_code = process.returncode
        self.stderr = process.stderr
        self.calls = self._jsonl("calls.jsonl")
        self.records = self._jsonl("records.jsonl")
        state = fixture / "state.json"
        self.state = json.loads(state.read_text()) if state.exists() else {}

    def _jsonl(self, name):
        path = self.fixture / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    @property
    def main(self):
        """Files on `main`."""
        return self.state["commits"][self.state["main"]]

    def status(self, task):
        return self.state["status"].get(task, [])

    def calls_to(self, port, op=None):
        return [c for c in self.calls if c["port"] == port and (op is None or c["op"] == op)]

    def events(self, stream, kind):
        return [r["event"] for r in self.records if r["stream"] == stream and r["event"]["kind"] == kind]


@pytest.fixture
def run_factory(tmp_path):
    def run(scenario, timeout=30, **config):
        scenario.setdefault("repo", {"README": "base"})
        (tmp_path / "scenario.json").write_text(json.dumps(scenario))
        config["adapters"] = {p: [sys.executable, str(STANDIN), p] for p in PORTS}
        (tmp_path / "config.json").write_text(json.dumps(config))
        command = shlex.split(os.environ.get("FACTORY_CMD", f"{sys.executable} -m factory"))
        process = subprocess.run(
            command + ["--config", str(tmp_path / "config.json")],
            env={**os.environ, "FIXTURE_DIR": str(tmp_path)},
            capture_output=True, text=True, timeout=timeout)
        return Outcome(tmp_path, process)
    return run
