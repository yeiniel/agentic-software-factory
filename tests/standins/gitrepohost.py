#!/usr/bin/env python3
"""Real-git Repo Host stand-in: bare repositories at $FACTORY_TEST_GIT_ROOT/<repo>.git.

Same contract as the scripted stand-in (docs/adapters/README.md). Test infrastructure only.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

IDENTITY = {"GIT_AUTHOR_NAME": "Factory", "GIT_AUTHOR_EMAIL": "factory@example.invalid",
            "GIT_COMMITTER_NAME": "Factory", "GIT_COMMITTER_EMAIL": "factory@example.invalid"}


class GitError(Exception):
    pass


def git(*args, cwd=None, check=True):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, **IDENTITY})
    if check and done.returncode:
        raise GitError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip() if done.returncode == 0 else None


def seed_repo(root, repo, files):
    """Create a bare repository whose `main` has one commit holding `files`."""
    bare = Path(root) / f"{repo}.git"
    git("init", "-q", "--bare", "-b", "main", str(bare))
    commit_files(bare, files, "Seed")


def commit_files(bare, files, message):
    """Commit `files` on top of `main` the way a human would, by pushing."""
    with tempfile.TemporaryDirectory() as tmp:
        git("clone", "-q", str(bare), tmp)
        for name, text in files.items():
            (Path(tmp) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(tmp) / name).write_text(text)
        git("add", "-A", cwd=tmp)
        git("commit", "-q", "-m", message, cwd=tmp)
        git("push", "-q", "origin", "HEAD:refs/heads/main", cwd=tmp)


def bare_git(bare, *args, check=True):
    return git("--git-dir", str(bare), *args, check=check)


def main_head(bare, a):
    return {"commit": bare_git(bare, "rev-parse", "refs/heads/main")}


def create_branch(bare, a):
    if a["name"] == "main":
        raise GitError("main is only advanced by fast-forward-main")
    commit = bare_git(bare, "rev-parse", "--verify", f"{a['base']}^{{commit}}")
    bare_git(bare, "update-ref", f"refs/heads/{a['name']}", commit)
    return {"commit": commit}


def checkout(bare, a):
    dest = a["dest"]
    ref, local = (f"refs/heads/{a['branch']}", a["branch"]) if "branch" in a else (a["commit"], "work")
    git("init", "-q", dest)
    git("fetch", "-q", str(bare), ref, cwd=dest)  # no remote is configured
    git("checkout", "-q", "-b", local, "FETCH_HEAD", cwd=dest)
    git("config", "user.name", "Factory", cwd=dest)
    git("config", "user.email", IDENTITY["GIT_AUTHOR_EMAIL"], cwd=dest)
    return {"commit": git("rev-parse", "HEAD", cwd=dest)}


def record(bare, a):
    src, branch = a["from"], a["branch"]
    git("add", "-A", cwd=src)
    if git("status", "--porcelain", cwd=src):
        git("commit", "-q", "-m", f"Record {branch}", cwd=src)
    before = bare_git(bare, "rev-parse", "-q", "--verify", f"refs/heads/{branch}^{{tree}}", check=False)
    after = git("rev-parse", "HEAD^{tree}", cwd=src)
    git("push", "-q", "--force", str(bare), f"HEAD:refs/heads/{branch}", cwd=src)
    return {"commit": git("rev-parse", "HEAD", cwd=src), "changed": before != after}


def fast_forward_main(bare, a):
    head = bare_git(bare, "rev-parse", "refs/heads/main")
    commit = bare_git(bare, "rev-parse", f"refs/heads/{a['branch']}")
    if head != a["expect-main"] or bare_git(bare, "merge-base", "--is-ancestor", head, commit,
                                            check=False) is None:
        return {"advanced": False, "head": head}
    try:
        bare_git(bare, "update-ref", "refs/heads/main", commit, head)  # compare-and-swap
    except GitError:  # main moved since we read it
        return {"advanced": False, "head": bare_git(bare, "rev-parse", "refs/heads/main")}
    return {"advanced": True, "head": commit}


OPS = {"main-head": main_head, "create-branch": create_branch, "checkout": checkout,
       "record": record, "fast-forward-main": fast_forward_main}


def main():
    op, *rest = sys.argv[1:]
    if op not in OPS:
        print(f"unknown operation {op}", file=sys.stderr)
        sys.exit(2)
    args = {rest[i].lstrip("-"): rest[i + 1] for i in range(0, len(rest), 2)}
    bare = Path(os.environ["FACTORY_TEST_GIT_ROOT"]) / f"{args['repo']}.git"
    try:
        print(json.dumps(OPS[op](bare, args)))
    except GitError as error:
        print(error, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
