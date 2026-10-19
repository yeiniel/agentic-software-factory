"""Repo Host behaviour beyond the shared contract: what an Agent's clone can see."""
import subprocess

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "standins"))
import gitissues  # noqa: E402


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, check=True).stdout


def test_a_clone_holds_no_issue_refs_even_when_the_server_has_issues(exe, repo, tmp_path):
    repo({"README": "x"})
    gitissues.create_issue(tmp_path / "git" / "r.git", "A Task", "secret body")
    host = exe("repo-host")
    head = host.ok("main-head", repo="r")["commit"]
    host.ok("create-branch", repo="r", name="factory/t/implementor", base=head)
    host.ok("checkout", repo="r", branch="factory/t/implementor", dest=tmp_path / "clone")
    assert git(tmp_path / "clone", "for-each-ref", "--format=%(refname)").split() == ["refs/heads/factory/t/implementor"]
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
