"""Helpers for the real Adapters' own behaviour tests (the shared contract is in tests/conformance)."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "tests" / "standins"))
import gitrepohost  # noqa: E402

ADAPTERS = ROOT / "adapters"
STUB_IMAGES = ROOT / "tests" / "standins" / "images"
CONTAINERFILE = "FROM docker.io/library/alpine\nRUN apk add --no-cache git make\n"

needs_podman = pytest.mark.skipif(shutil.which("podman") is None, reason="needs Podman")


class Exe:
    def __init__(self, name, env):
        self.path, self.env = str(ADAPTERS / name), env

    def run(self, op, body=None, **args):
        argv = [self.path, op] + [x for k, v in args.items() for x in (f"--{k.replace('_', '-')}", str(v))]
        return subprocess.run(argv, input=json.dumps(body) if body is not None else "",
                              capture_output=True, text=True, env=self.env, timeout=600)

    def ok(self, op, body=None, **args):
        done = self.run(op, body, **args)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout) if done.stdout.strip() else {}
