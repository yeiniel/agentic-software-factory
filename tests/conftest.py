"""Black-box harness: starts the Factory as a process wired to scripted stand-in Adapters."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import golden
import podman_images

sys.path.insert(0, str(Path(__file__).parent / "standins"))
import gitrepohost

STANDIN = Path(__file__).parent / "standins" / "standin.py"
ADAPTERS = Path(__file__).parent.parent / "adapters"
DEFAULT_GRAPH = Path(__file__).parent.parent / "src" / "factory" / "resources"
PORTS = ["event-source", "task-store", "repo-host", "runner", "records"]


class Outcome:
    def __init__(self, fixture, process):
        self.fixture = fixture
        self.exit_code = process.returncode
        self.stderr = process.stderr
        self.calls = self._jsonl("calls.jsonl")
        self.records = self._jsonl("records.jsonl")
        state = fixture / "state.json"
        self.state = json.loads(state.read_text()) if state.exists() else {}

    def git_main(self, path):
        """Contents of `path` on `main` of the real-git repo `r`, or None."""
        bare = self.fixture / "git" / "r.git"
        done = subprocess.run(["git", "--git-dir", str(bare), "show", f"main:{path}"], capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    def git_log_main(self):
        bare = self.fixture / "git" / "r.git"
        return subprocess.run(
            ["git", "--git-dir", str(bare), "log", "--format=%s", "main"], capture_output=True, text=True
        ).stdout.split("\n")

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
    def run(scenario, timeout=30, real_git=None, **config):
        scenario.setdefault("repo", {"README": "base"})
        (tmp_path / "scenario.json").write_text(json.dumps(scenario))
        config["context_root"] = str(tmp_path / "contexts")
        config["adapters"] = {**{p: [sys.executable, str(STANDIN), p] for p in PORTS}, **config.get("adapters", {})}
        if real_git is not None:  # real git Repo Host and the real Integrator script
            root = tmp_path / "git"
            gitrepohost.seed_repo(root, "r", real_git)
            config["adapters"]["repo-host"] = [sys.executable, str(ADAPTERS / "repo-host")]
            scenario["integrator_impl"] = "real"
            (tmp_path / "scenario.json").write_text(json.dumps(scenario))
        (tmp_path / "config.json").write_text(json.dumps(config))
        command = shlex.split(os.environ.get("FACTORY_CMD", f"{sys.executable} -m factory"))
        process = subprocess.run(
            [*command, "--config", str(tmp_path / "config.json")],
            env={
                **os.environ,
                "FIXTURE_DIR": str(tmp_path),
                "FACTORY_TEST_GIT_ROOT": str(tmp_path / "git"),
                "REPO_HOST_URL": str(tmp_path / "git"),
                "ADAPTER_CACHE": str(tmp_path / "cache"),
            },
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return Outcome(tmp_path, process)

    return run


@pytest.fixture
def graph_variant(tmp_path):
    """`graph_variant(change, files)`: a copy of the shipped Graph with `graph.json` changed and files added."""

    def make(change=None, files=None):
        folder = tmp_path / "graph"
        shutil.copytree(DEFAULT_GRAPH, folder, ignore=shutil.ignore_patterns("__pycache__"))
        data = json.loads((folder / "graph.json").read_text())
        if change:
            change(data)
        (folder / "graph.json").write_text(json.dumps(data))
        for name, text in (files or {}).items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(text)
        return str(folder)

    return make


@pytest.fixture
def golden_transcript(request):
    """`golden_transcript(out)` asserts the scenario against tests/goldens/<test name>.txt."""
    return lambda out: golden.check(out, request.node.name)


def pytest_runtest_makereport(item, call):
    """In the quality gate (ASF_CHECK=1) a skipped test fails: a skip hides behaviour behind a green run."""
    if os.environ.get("ASF_CHECK") and call.excinfo is not None and call.excinfo.errisinstance(pytest.skip.Exception):
        call.excinfo = pytest.ExceptionInfo.from_exception(
            AssertionError(f"skipped in check mode: {call.excinfo.value}")
        )


def pytest_sessionfinish(session, exitstatus):
    """Remove the images this session built (tests/podman_images.py)."""
    podman_images.remove_images()
