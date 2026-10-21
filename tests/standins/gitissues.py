"""Create and read git-native issues (`refs/issues/<uuid>`) the way `git issue` lays them out."""

import uuid

from gitrepohost import git


def create_issue(bare, title, body=""):
    """Add an open issue to the bare repository; returns its id."""
    ident = str(uuid.uuid4())
    tree = git("hash-object", "-t", "tree", "/dev/null")
    message = (
        f"{title}\n\n{body}\n\nState: open\nFormat-Version: 1\n"
        if body
        else f"{title}\n\nState: open\nFormat-Version: 1\n"
    )
    commit = git("commit-tree", tree, "-m", message, cwd=bare)
    git("--git-dir", str(bare), "update-ref", f"refs/issues/{ident}", commit)
    return ident


def issue_log(bare, ident):
    """Messages of the issue's commits, oldest first."""
    out = git("--git-dir", str(bare), "log", "--reverse", "--format=%B%x00", f"refs/issues/{ident}") or ""
    return [m.strip() for m in out.split("\0") if m.strip()]


def add_labels(bare, ident, labels):
    """Label an issue the way `git issue edit` does: a new commit with the Labels trailer."""
    ref = f"refs/issues/{ident}"
    tree = git("hash-object", "-t", "tree", "/dev/null")
    commit = git(
        "commit-tree",
        tree,
        "-p",
        ref,
        "-m",
        f"Edit labels\n\nState: open\nLabels: {labels}\nFormat-Version: 1\n",
        cwd=bare,
    )
    git("--git-dir", str(bare), "update-ref", ref, commit)
