"""Adapter conformance harness.

Each suite runs against the scripted stand-in by default. To test another implementation set
ADAPTER_<PORT> to its command (e.g. ADAPTER_REPO_HOST='/opt/git-host --root /srv') and, if it needs
different identifiers, ADAPTER_<PORT>_FIXTURE to a JSON object overriding FIXTURE below.
The suites need no Factory code: they check only the documented contract (docs/adapters/README.md).
"""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

STANDIN = Path(__file__).parent.parent / "standins" / "standin.py"

FIXTURE = {
    "repo": "r",                    # a repository whose `main` has at least one commit
    "task": "t1", "prompt": "add a greeting",  # a Task in the Task Store
    "commit": "c0",                 # a commit of `repo` to build an Environment for
    "agent_image": "img", "integrator_image": "img",  # images the Runner can run
    "events": [{"type": "task", "task": "t1", "repo": "r"},
               {"type": "main-push", "repo": "r", "commit": "c0"}],
}


class Target:
    def __init__(self, argv, env, fixture, timeout=30):
        self.argv, self.env, self.fixture, self.timeout = argv, env, fixture, timeout

    def run(self, op, body=None, **args):
        argv = [*self.argv, op]
        for key, value in args.items():
            argv += [f"--{key.replace('_', '-')}", str(value)]
        done = subprocess.run(argv, input=json.dumps(body) if body is not None else "",
                              capture_output=True, text=True, env=self.env, timeout=self.timeout)
        return done

    def ok(self, op, body=None, **args):
        """Call an op that must succeed and print a JSON object."""
        done = self.run(op, body, **args)
        assert done.returncode == 0, f"{op} {args} failed: {done.stderr}"
        result = json.loads(done.stdout) if done.stdout.strip() else {}
        assert isinstance(result, dict), f"{op} must print a JSON object, got {done.stdout!r}"
        return result

    def fails(self, op, body=None, **args):
        """Call an op that must be rejected with a non-zero exit."""
        done = self.run(op, body, **args)
        assert done.returncode != 0, f"{op} {args} should have failed but printed {done.stdout!r}"


@pytest.fixture
def adapter(tmp_path):
    def make(port):
        var = "ADAPTER_" + port.upper().replace("-", "_")
        fixture = {**FIXTURE, **json.loads(os.environ.get(var + "_FIXTURE", "{}"))}
        if os.environ.get(var):
            return Target(shlex.split(os.environ[var]), dict(os.environ), fixture)
        scenario = {"repo": {"README": "base"}, "tasks": {fixture["task"]: fixture["prompt"]},
                    "events": fixture["events"]}
        (tmp_path / "scenario.json").write_text(json.dumps(scenario))
        return Target([sys.executable, str(STANDIN), port],
                      {**os.environ, "FIXTURE_DIR": str(tmp_path)}, fixture)
    return make
