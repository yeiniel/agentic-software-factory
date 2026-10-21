"""The git server's hooks and the Event Source, together: push, and the event arrives."""

import json
import os
import queue
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "tests" / "standins"))

CREATE_REPO = ROOT / "git-server" / "create-repo"


@pytest.fixture
def server(tmp_path):
    """A bare repository `r` created the way the git server does, and a listening Event Source."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "README").write_text("base")
    env = {
        **os.environ,
        "HOOKS_DIR": str(ROOT / "git-server" / "hooks"),
        "EVENT_SOURCE_URL": f"http://127.0.0.1:{port}",
        "EVENT_SOURCE_PORT": str(port),
    }
    subprocess.run([str(CREATE_REPO), str(tmp_path / "srv"), "r", str(seed)], check=True, env=env)
    source = subprocess.Popen(
        [str(ROOT / "adapters" / "event-source"), "listen"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout = source.stdout
    assert stdout is not None and source.stderr is not None
    source.stderr.readline()  # "listening on port ..."
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(json.loads(l)) for l in stdout], daemon=True).start()
    yield tmp_path / "srv" / "r.git", env, lines
    source.kill()
    source.wait()
    stdout.close()
    source.stderr.close()


def clone(bare, tmp_path, env):
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True, env=env)
    return work


def git(work, env, *args, check=True):
    return subprocess.run(
        ["git", "-C", str(work), "-c", "user.name=h", "-c", "user.email=h@x", *args],
        capture_output=True,
        text=True,
        env=env,
        check=check,
    )


def test_a_new_issue_arrives_as_a_task_event(server, tmp_path):
    bare, env, events = server
    work = clone(bare, tmp_path, env)
    tree = git(work, env, "hash-object", "-t", "tree", "/dev/null").stdout.strip()
    commit = git(work, env, "commit-tree", tree, "-m", "Add a greeting\n\nState: open\n").stdout.strip()
    git(work, env, "push", "-q", "origin", f"{commit}:refs/issues/abc123")
    assert events.get(timeout=10) == {"type": "task", "task": "r/abc123", "repo": "r"}


def test_a_push_to_main_arrives_as_a_main_push_event(server, tmp_path):
    bare, env, events = server
    work = clone(bare, tmp_path, env)
    (work / "f").write_text("x")
    git(work, env, "add", "-A")
    git(work, env, "commit", "-q", "-m", "change")
    git(work, env, "push", "-q", "origin", "HEAD:main")
    head = git(work, env, "rev-parse", "HEAD").stdout.strip()
    assert events.get(timeout=10) == {"type": "main-push", "repo": "r", "commit": head}


def test_status_changes_to_an_existing_issue_are_not_events(server, tmp_path):
    bare, env, events = server
    work = clone(bare, tmp_path, env)
    tree = git(work, env, "hash-object", "-t", "tree", "/dev/null").stdout.strip()
    first = git(work, env, "commit-tree", tree, "-m", "T").stdout.strip()
    git(work, env, "push", "-q", "origin", f"{first}:refs/issues/abc")
    assert events.get(timeout=10)["type"] == "task"
    second = git(work, env, "commit-tree", tree, "-p", first, "-m", "Status: running").stdout.strip()
    git(work, env, "push", "-q", "origin", f"{second}:refs/issues/abc")
    other = git(work, env, "commit-tree", tree, "-m", "after").stdout.strip()
    git(work, env, "push", "-q", "origin", f"{other}:refs/issues/def")
    assert events.get(timeout=10)["task"] == "r/def"


def test_refs_may_not_be_deleted_or_rewritten(server, tmp_path):
    bare, env, _ = server
    work = clone(bare, tmp_path, env)
    assert git(work, env, "push", "origin", ":main", check=False).returncode != 0
    git(work, env, "commit", "-q", "--amend", "-m", "rewritten")
    assert git(work, env, "push", "-f", "origin", "HEAD:main", check=False).returncode != 0
    assert git(work, env, "push", "-f", "origin", "HEAD:refs/heads/factory/t/implementor").returncode == 0
    git(work, env, "commit", "-q", "--amend", "-m", "rewritten again")
    assert git(work, env, "push", "-f", "origin", "HEAD:refs/heads/factory/t/implementor").returncode == 0
    assert git(work, env, "push", "-f", "origin", "HEAD:refs/heads/other", check=False).returncode == 0
    git(work, env, "commit", "-q", "--amend", "-m", "again")
    assert git(work, env, "push", "-f", "origin", "HEAD:refs/heads/other", check=False).returncode != 0
