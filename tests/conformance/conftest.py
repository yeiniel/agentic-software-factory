"""Adapter conformance harness.

Each suite runs against the scripted stand-in by default. To test another implementation set
ADAPTER_<PORT> to its command (e.g. ADAPTER_REPO_HOST='/opt/git-host --root /srv') and, if it needs
different identifiers, ADAPTER_<PORT>_FIXTURE to a JSON object overriding FIXTURE below.
The suites need no Factory code: they check only the documented contract (docs/adapters/README.md).
"""

import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "standins"))
import gitissues
import gitrepohost

ADAPTERS = Path(__file__).parent.parent.parent / "adapters"
STANDIN = Path(__file__).parent.parent / "standins" / "standin.py"

FIXTURE = {
    "repo": "r",  # a repository whose `main` has at least one commit
    "task": "t1",
    "prompt": "add a greeting",  # a Task in the Task Store
    "commit": "c0",  # a commit of `repo`
    "events": [{"type": "task", "task": "t1", "repo": "r"}, {"type": "main-push", "repo": "r", "commit": "c0"}],
}


class Target:
    def __init__(self, argv, env, fixture, timeout=30):
        self.argv, self.env, self.fixture, self.timeout = argv, env, fixture, timeout

    def run(self, op, body=None, **args):
        argv = [*self.argv, op]
        for key, value in args.items():
            argv += [f"--{key.replace('_', '-')}", str(value)]
        done = subprocess.run(
            argv,
            input=json.dumps(body) if body is not None else "",
            capture_output=True,
            text=True,
            env=self.env,
            timeout=self.timeout,
        )
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


STUB_IMAGES = Path(__file__).parent.parent / "standins" / "images"
CONTAINERFILE = "FROM docker.io/library/alpine\nRUN apk add --no-cache git make\n"
needs_podman = pytest.mark.skipif(shutil.which("podman") is None, reason="needs Podman")


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def real_target(port, tmp_path):
    """The real Adapter for `port`, set up against a temporary git server, with matching fixture."""
    root = tmp_path / "git"
    gitrepohost.seed_repo(root, FIXTURE["repo"], {"README": "base", "Containerfile": CONTAINERFILE})
    head = gitrepohost.git("--git-dir", str(root / "r.git"), "rev-parse", "main")
    env = {
        **os.environ,
        "REPO_HOST_URL": str(root),
        "ADAPTER_CACHE": str(tmp_path / "cache"),
        "RECORDS_DIR": str(tmp_path / "records"),
        "RUNNER_ROOT": str(tmp_path / "runner"),
        "ASF_IMAGES_DIR": str(STUB_IMAGES),
        "ASF_MODEL_ENDPOINT": "http://model/v1",
        "ASF_MODEL_NAME": "m",
        "ASF_MODEL_CONTEXT_WINDOW": "1000",
    }
    fixture = {**FIXTURE, "commit": head}
    exe = [str(ADAPTERS / port)]
    if port == "task-store":
        ident = gitissues.create_issue(root / "r.git", FIXTURE["prompt"])
        fixture["task"] = f"r/{ident}"
    if port == "event-source":
        env["EVENT_SOURCE_PORT"] = str(free_port())
    if port == "runner" and shutil.which("podman") is None:
        pytest.skip("needs Podman")
    target = Target(exe, env, fixture, timeout=600 if port == "runner" else 120)
    if port == "event-source":
        post = (
            "import sys,time,urllib.request as u\n"
            "for line in ('%s %s refs/issues/abc', '%s %s refs/heads/main'):\n"
            "    for _ in range(50):\n"
            "        try: u.urlopen(u.Request('http://127.0.0.1:%s/push?repo=r', data=(line %% ()).encode())); break\n"
            "        except OSError: time.sleep(0.1)\n"
        ) % ("0" * 40, "1" * 40, "1" * 40, "2" * 40, env["EVENT_SOURCE_PORT"])
        target.trigger = f"{shlex.quote(sys.executable)} -c {shlex.quote(post)}"
    return target


@pytest.fixture(params=["scripted", "real"])
def adapter(tmp_path, request):
    def make(port):
        var = "ADAPTER_" + port.upper().replace("-", "_")
        if os.environ.get(var) and request.param == "real":
            pytest.skip(f"{var} targets another implementation")
        if request.param == "real":
            return real_target(port, tmp_path)
        fixture = {**FIXTURE, **json.loads(os.environ.get(var + "_FIXTURE", "{}"))}
        if os.environ.get(var):
            return Target(shlex.split(os.environ[var]), dict(os.environ), fixture)
        scenario = {
            "repo": {"README": "base"},
            "tasks": {fixture["task"]: fixture["prompt"]},
            "events": fixture["events"],
        }
        (tmp_path / "scenario.json").write_text(json.dumps(scenario))
        return Target([sys.executable, str(STANDIN), port], {**os.environ, "FIXTURE_DIR": str(tmp_path)}, fixture)

    return make
