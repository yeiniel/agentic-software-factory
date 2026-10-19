"""Task Store against real git: issues round-trip through refs/issues/* on a bare repository."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "standins"))
import gitissues  # noqa: E402
import gitrepohost  # noqa: E402

STORE = Path(__file__).parent.parent.parent / "adapters" / "task-store"


@pytest.fixture
def server(tmp_path):
    gitrepohost.seed_repo(tmp_path / "git", "r", {"README": "base"})
    return tmp_path / "git" / "r.git"


@pytest.fixture
def store(tmp_path, server):
    env = {"PATH": "/usr/bin:/bin", "REPO_HOST_URL": str(tmp_path / "git"), "ADAPTER_CACHE": str(tmp_path / "cache")}

    def run(op, body=None, **args):
        argv = [str(STORE), op] + [x for k, v in args.items() for x in (f"--{k}", str(v))]
        return subprocess.run(argv, input=json.dumps(body) if body is not None else "",
                              capture_output=True, text=True, env=env)
    return run


def ok(done):
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def labels_and_state(server, ident):
    """Trailers of the issue's newest commit."""
    top = gitissues.issue_log(server, ident)[-1]
    return dict(line.split(": ", 1) for line in top.split("\n\n")[-1].splitlines() if ": " in line)


def test_the_prompt_is_the_issues_title_and_body(store, server):
    ident = gitissues.create_issue(server, "Add a greeting", "Print hello on start.")
    assert ok(store("get-prompt", task=f"r/{ident}")) == {"prompt": "Add a greeting\n\nPrint hello on start."}


def test_the_prompt_of_an_issue_without_a_body_is_its_title(store, server):
    ident = gitissues.create_issue(server, "Add a greeting")
    assert ok(store("get-prompt", task=f"r/{ident}")) == {"prompt": "Add a greeting"}


def test_an_id_prefix_is_enough(store, server):
    ident = gitissues.create_issue(server, "Add a greeting")
    assert ok(store("get-prompt", task=f"r/{ident[:8]}"))["prompt"] == "Add a greeting"


def test_a_task_without_a_repo_or_unknown_fails(store, server):
    gitissues.create_issue(server, "x")
    assert store("get-prompt", task="nope").returncode != 0
    assert store("get-prompt", task="r/ffffffff").returncode != 0


def test_running_and_blocked_are_labels_on_an_open_issue(store, server):
    ident = gitissues.create_issue(server, "T")
    ok(store("set-status", task=f"r/{ident}", status="running"))
    assert labels_and_state(server, ident)["State"] == "open"
    assert labels_and_state(server, ident)["Labels"] == "running"
    ok(store("set-status", {"history": [{"run": 1}], "reason": "cap"}, task=f"r/{ident}", status="blocked"))
    assert labels_and_state(server, ident)["Labels"] == "blocked"
    ok(store("set-status", task=f"r/{ident}", status="todo"))
    assert "Labels" not in labels_and_state(server, ident)


def test_other_labels_survive_status_changes(store, server):
    ident = gitissues.create_issue(server, "T")
    gitissues.add_labels(server, ident, "bug")
    ok(store("set-status", task=f"r/{ident}", status="running"))
    assert labels_and_state(server, ident)["Labels"] == "bug, running"
    ok(store("set-status", task=f"r/{ident}", status="done", body={"commit": "abc"}))
    assert labels_and_state(server, ident)["Labels"] == "bug"


def test_done_closes_the_issue_with_a_reference_to_the_commit(store, server):
    ident = gitissues.create_issue(server, "T")
    ok(store("set-status", task=f"r/{ident}", status="running"))
    ok(store("set-status", {"commit": "abc123"}, task=f"r/{ident}", status="done"))
    trailers = labels_and_state(server, ident)
    assert trailers["State"] == "closed" and trailers["Fixed-By"] == "abc123"
    assert "running" not in trailers.get("Labels", "")


def test_blocked_keeps_the_history_in_the_issue(store, server):
    ident = gitissues.create_issue(server, "T")
    ok(store("set-status", {"history": [{"run": 1}], "reason": "cap"}, task=f"r/{ident}", status="blocked"))
    assert '"run": 1' in "\n".join(gitissues.issue_log(server, ident))


def test_status_changes_only_append(store, server):
    ident = gitissues.create_issue(server, "T")
    before = subprocess.run(["git", "--git-dir", str(server), "rev-parse", f"refs/issues/{ident}"],
                            capture_output=True, text=True).stdout.strip()
    ok(store("set-status", task=f"r/{ident}", status="running"))
    done = subprocess.run(["git", "--git-dir", str(server), "merge-base", "--is-ancestor", before, f"refs/issues/{ident}"])
    assert done.returncode == 0


def test_a_cleared_label_stays_cleared(store, server):
    ident = gitissues.create_issue(server, "T")
    ok(store("set-status", task=f"r/{ident}", status="running"))
    ok(store("set-status", task=f"r/{ident}", status="todo"))
    ok(store("set-status", task=f"r/{ident}", status="blocked"))
    assert labels_and_state(server, ident)["Labels"] == "blocked"


def test_a_body_ending_in_a_key_value_paragraph_is_kept_whole(store, server):
    ident = gitissues.create_issue(server, "T", "Do it.\n\nNote: keep the API stable")
    assert ok(store("get-prompt", task=f"r/{ident}"))["prompt"] == "T\n\nDo it.\n\nNote: keep the API stable"
