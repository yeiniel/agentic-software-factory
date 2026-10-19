"""Shared plumbing for the Adapter executables: `<exe> <op> [--name value ...]`, JSON out."""
import fcntl
import json
import os
import subprocess
import sys

IDENTITY = {"GIT_AUTHOR_NAME": "Factory", "GIT_AUTHOR_EMAIL": "factory@example.invalid",
            "GIT_COMMITTER_NAME": "Factory", "GIT_COMMITTER_EMAIL": "factory@example.invalid"}


class Failure(Exception):
    """A request the Adapter cannot honour; reported on stderr with exit status 1."""


def git(*args, cwd=None, check=True, input=None):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, input=input,
                          env={**os.environ, **IDENTITY})
    if check and done.returncode:
        raise Failure(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip() if done.returncode == 0 else None


def read_body():
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else None


def main(ops):
    """Dispatch `argv` to `ops[op](args, body)` and print the JSON object it returns."""
    if len(sys.argv) < 2 or sys.argv[1] not in ops:
        print(f"unknown operation {sys.argv[1:2]}", file=sys.stderr)
        sys.exit(2)
    op, rest = sys.argv[1], sys.argv[2:]
    args = {rest[i].lstrip("-"): rest[i + 1] for i in range(0, len(rest) - 1, 2)}
    try:
        result = ops[op](args)
    except (Failure, KeyError, ValueError) as error:
        print(f"{op}: {error!r}" if isinstance(error, KeyError) else f"{op}: {error}", file=sys.stderr)
        sys.exit(1)
    if result is not None:
        print(json.dumps(result))


def require_env(name):
    if not os.environ.get(name):
        raise Failure(f"{name} is not set")
    return os.environ[name]


def remote(repo):
    """URL of a repository on the git server: `$REPO_HOST_URL/<repo>.git`."""
    return f"{require_env('REPO_HOST_URL').rstrip('/')}/{repo}.git"


def mirror(adapter, repo, refspec):
    """A local bare mirror of `refspec` from `repo` for one Adapter, refreshed; returns its path."""
    root = os.environ.get("ADAPTER_CACHE") or os.path.expanduser("~/.cache/asf")
    cache = os.path.join(root, adapter, repo.replace("/", "_") + ".git")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache + ".lock", "w") as lock:  # Adapter processes run in parallel and share the mirror
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not os.path.isdir(cache):
            git("init", "-q", "--bare", cache)
        git("fetch", "-q", remote(repo), refspec, cwd=cache)
    return cache


def podman(*args, check=True, **kwargs):
    """Run `$PODMAN` (default `podman`; with CONTAINER_HOST set it talks to the host's socket)."""
    done = subprocess.run([os.environ.get("PODMAN", "podman"), *args], capture_output=True, text=True,
                          **kwargs)
    if check and done.returncode:
        raise Failure(f"podman {' '.join(args[:2])}: {(done.stderr or done.stdout).strip()}")
    return done


def slug(text):
    """A name safe in image tags, container names and paths."""
    import re
    return re.sub(r"[^a-z0-9_.-]+", "-", text.lower()).strip("-.")
