"""Repo Host behaviour beyond the shared contract: what an Agent's clone can see."""

import subprocess

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "standins"))
import gitissues


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True).stdout


def test_a_clone_holds_no_issue_refs_even_when_the_server_has_issues(exe, repo, tmp_path):
    repo({"README": "x"})
    gitissues.create_issue(tmp_path / "git" / "r.git", "A Task", "secret body")
    host = exe("repo-host")
    head = host.ok("main-head", repo="r")["commit"]
    host.ok("create-branch", repo="r", name="factory/t/implementor", base=head)
    host.ok("checkout", repo="r", branch="factory/t/implementor", dest=tmp_path / "clone")
    assert git(tmp_path / "clone", "for-each-ref", "--format=%(refname)").split() == [
        "refs/heads/factory/t/implementor"
    ]
    assert git(tmp_path / "clone", "remote").strip() == ""
    assert git(tmp_path / "clone", "count-objects", "-v")  # a real repository
    assert "secret body" not in git(tmp_path / "clone", "log", "--all", "--format=%B")


def test_a_recorded_branch_reaches_the_server_and_a_retry_continues_from_it(exe, repo, tmp_path):
    repo({"README": "x"})
    host = exe("repo-host")
    head = host.ok("main-head", repo="r")["commit"]
    host.ok("create-branch", repo="r", name="factory/t/implementor", base=head)
    for n in (1, 2):
        dest = tmp_path / f"run{n}"
        host.ok("checkout", repo="r", branch="factory/t/implementor", dest=dest)
        (dest / f"f{n}.txt").write_text(str(n))
        host.ok("record", repo="r", branch="factory/t/implementor", **{"from": dest})
    log = git(tmp_path / "git" / "r.git", "log", "--format=%s", "factory/t/implementor").split("\n")
    assert len([l for l in log if l.startswith("Record")]) == 2


def test_a_repository_without_a_main_has_no_head(exe, tmp_path):
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(tmp_path / "git" / "empty.git")], check=True)
    done = exe("repo-host").run("main-head", repo="empty")
    assert done.returncode != 0 and "no main" in done.stderr


def test_a_server_that_refuses_the_push_to_main_leaves_main_where_it_is(exe, repo, tmp_path):
    repo({"README": "x"})
    host = exe("repo-host")
    head = host.ok("main-head", repo="r")["commit"]
    host.ok("create-branch", repo="r", name="factory/t/integrated", base=head)
    dest = tmp_path / "work"
    host.ok("checkout", repo="r", branch="factory/t/integrated", dest=dest)
    (dest / "new.txt").write_text("new")
    host.ok("record", repo="r", branch="factory/t/integrated", **{"from": dest})
    hook = tmp_path / "git" / "r.git" / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do [ "$ref" = refs/heads/main ] && exit 1; done\nexit 0\n')
    hook.chmod(0o755)

    result = host.ok("fast-forward-main", repo="r", branch="factory/t/integrated", expect_main=head)

    assert result == {"advanced": False, "head": head}
