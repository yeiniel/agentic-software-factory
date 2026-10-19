import subprocess
import uuid
from pathlib import Path

import pytest


# These tests write branches and advance `main`: point ADAPTER_REPO_HOST at a disposable repository.
@pytest.fixture(params=["scripted", "git"])
def host(adapter, request):
    return adapter("repo-host", impl=request.param)


@pytest.fixture
def repo(host):
    return host.fixture["repo"]


def tree(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts}


def new_branch(host, repo, base=None):
    name = f"test/{uuid.uuid4().hex[:8]}"
    host.ok("create-branch", repo=repo, name=name, base=base or host.ok("main-head", repo=repo)["commit"])
    return name


def changed_branch(host, repo, tmp_path, base=None, content="changed"):
    """A new branch carrying one extra file, recorded from a checkout."""
    name = new_branch(host, repo, base)
    dest = tmp_path / uuid.uuid4().hex
    host.ok("checkout", repo=repo, branch=name, dest=dest)
    (dest / f"{uuid.uuid4().hex}.txt").write_text(content)
    recorded = host.ok("record", repo=repo, branch=name, **{"from": dest})
    return name, recorded["commit"]


def test_main_head_is_a_commit(host, repo):
    assert host.ok("main-head", repo=repo)["commit"]


def test_a_created_branch_starts_at_its_base(host, repo, tmp_path):
    head = host.ok("main-head", repo=repo)["commit"]
    name = new_branch(host, repo)
    host.ok("checkout", repo=repo, branch=name, dest=tmp_path / "branch")
    host.ok("checkout", repo=repo, commit=head, dest=tmp_path / "base")
    assert tree(tmp_path / "branch") == tree(tmp_path / "base") != {}


def test_checkout_of_main_matches_main_head(host, repo, tmp_path):
    head = host.ok("main-head", repo=repo)["commit"]
    host.ok("checkout", repo=repo, branch="main", dest=tmp_path / "a")
    host.ok("checkout", repo=repo, commit=head, dest=tmp_path / "b")
    assert tree(tmp_path / "a") == tree(tmp_path / "b")


def test_a_clone_holds_one_branch_and_no_remote(host, repo, tmp_path):
    name = new_branch(host, repo)
    host.ok("create-branch", repo=repo, name=f"other/{uuid.uuid4().hex[:8]}",
            base=host.ok("main-head", repo=repo)["commit"])
    dest = tmp_path / "clone"
    host.ok("checkout", repo=repo, branch=name, dest=dest)
    if not (dest / ".git").exists():
        pytest.skip("not a git clone: single-branch isolation is not observable")
    git = lambda *a: subprocess.run(["git", "-C", str(dest), *a], capture_output=True, text=True,
                                    check=True).stdout
    assert git("remote").strip() == ""
    assert [b for b in git("branch", "--all").split() if b != "*"] == [name]


def test_checkout_of_an_unknown_branch_fails(host, repo, tmp_path):
    host.fails("checkout", repo=repo, branch="no/such-branch", dest=tmp_path / "x")


def test_record_puts_the_directorys_changes_on_the_branch_only(host, repo, tmp_path):
    head = host.ok("main-head", repo=repo)["commit"]
    name, _ = changed_branch(host, repo, tmp_path, content="marker")
    host.ok("checkout", repo=repo, branch=name, dest=tmp_path / "again")
    assert "marker" in tree(tmp_path / "again").values()
    assert host.ok("main-head", repo=repo)["commit"] == head


def test_record_reports_whether_anything_changed(host, repo, tmp_path):
    name = new_branch(host, repo)
    dest = tmp_path / "w"
    host.ok("checkout", repo=repo, branch=name, dest=dest)
    assert host.ok("record", repo=repo, branch=name, **{"from": dest})["changed"] is False
    (dest / "new.txt").write_text("x")
    assert host.ok("record", repo=repo, branch=name, **{"from": dest})["changed"] is True


def test_fast_forward_advances_main_from_a_branch_derived_from_it(host, repo, tmp_path):
    head = host.ok("main-head", repo=repo)["commit"]
    name, commit = changed_branch(host, repo, tmp_path)
    result = host.ok("fast-forward-main", repo=repo, branch=name, expect_main=head)
    assert result["advanced"] is True
    assert result["head"] == commit == host.ok("main-head", repo=repo)["commit"]


def test_fast_forward_refuses_when_main_is_not_the_expected_commit(host, repo, tmp_path):
    stale = host.ok("main-head", repo=repo)["commit"]
    first, _ = changed_branch(host, repo, tmp_path)
    second, _ = changed_branch(host, repo, tmp_path, base=stale)
    host.ok("fast-forward-main", repo=repo, branch=first, expect_main=stale)
    moved = host.ok("main-head", repo=repo)["commit"]

    result = host.ok("fast-forward-main", repo=repo, branch=second, expect_main=stale)

    assert result["advanced"] is False
    assert host.ok("main-head", repo=repo)["commit"] == moved


def test_unknown_operation_fails(host):
    host.fails("no-such-op")


def test_main_cannot_be_overwritten_by_create_branch(host, repo):
    head = host.ok("main-head", repo=repo)["commit"]
    host.fails("create-branch", repo=repo, name="main", base=head)
