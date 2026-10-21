"""Shared plumbing for the Adapter executables: `<exe> <op> [--name value ...]`, JSON out."""

import fcntl
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

Json = dict[str, Any]
Args = dict[str, str]
Op = Callable[[Args], Json | None]

IDENTITY = {
    "GIT_AUTHOR_NAME": "Factory",
    "GIT_AUTHOR_EMAIL": "factory@example.invalid",
    "GIT_COMMITTER_NAME": "Factory",
    "GIT_COMMITTER_EMAIL": "factory@example.invalid",
}
USAGE_ERROR = 2


class RequestError(Exception):
    """A request the Adapter cannot honour; reported on stderr with exit status 1."""


def run_git(*args: str, cwd: str | Path | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **IDENTITY}, check=False
    )


def git(*args: str, cwd: str | Path | None = None) -> str:
    done = run_git(*args, cwd=cwd)
    if done.returncode:
        raise RequestError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def try_git(*args: str, cwd: str | Path | None = None) -> str | None:
    """The output of a git command that may fail, or None when it did."""
    done = run_git(*args, cwd=cwd)
    return done.stdout.strip() if done.returncode == 0 else None


def read_body() -> object:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else None


def main(ops: dict[str, Op]) -> None:
    """Dispatch `argv` to `ops[op](args)` and print the JSON object it returns."""
    if len(sys.argv) < USAGE_ERROR or sys.argv[1] not in ops:
        print(f"unknown operation {sys.argv[1:2]}", file=sys.stderr)
        sys.exit(USAGE_ERROR)
    op, rest = sys.argv[1], sys.argv[2:]
    args = {rest[i].lstrip("-"): rest[i + 1] for i in range(0, len(rest) - 1, 2)}
    try:
        result = ops[op](args)
    except (RequestError, KeyError, ValueError) as error:
        print(f"{op}: {error!r}" if isinstance(error, KeyError) else f"{op}: {error}", file=sys.stderr)
        sys.exit(1)
    if result is not None:
        print(json.dumps(result))


def require_env(name: str) -> str:
    if not os.environ.get(name):
        raise RequestError(f"{name} is not set")
    return os.environ[name]


def remote(repo: str) -> str:
    """URL of a repository on the git server: `$REPO_HOST_URL/<repo>.git`."""
    return f"{require_env('REPO_HOST_URL').rstrip('/')}/{repo}.git"


def mirror(adapter: str, repo: str, refspec: str) -> Path:
    """A local bare mirror of `refspec` from `repo` for one Adapter, refreshed; returns its path."""
    root = Path(os.environ.get("ADAPTER_CACHE") or Path("~/.cache/asf").expanduser())
    cache = root / adapter / (repo.replace("/", "_") + ".git")
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.with_suffix(".git.lock").open("w") as lock:  # Adapter processes run in parallel and share the mirror
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not cache.is_dir():
            git("init", "-q", "--bare", str(cache))
        git("fetch", "-q", remote(repo), refspec, cwd=cache)
    return cache


def podman(*args: str, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """Run `$PODMAN` (default `podman`; with CONTAINER_HOST set it talks to the host's socket)."""
    done = subprocess.run(
        [os.environ.get("PODMAN", "podman"), *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if check and done.returncode:
        raise RequestError(f"podman {' '.join(args[:2])}: {(done.stderr or done.stdout).strip()}")
    return done


def slug(text: str) -> str:
    """A name safe in image tags, container names and paths."""
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-.")
