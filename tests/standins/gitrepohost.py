#!/usr/bin/env python3
"""Fixtures for the real-git Repo Host: seed bare repositories and push as a human would.

Test infrastructure only; the Repo Host itself is `adapters/repo-host`.
"""

import os
import subprocess
import tempfile
from pathlib import Path

IDENTITY = {
    "GIT_AUTHOR_NAME": "Factory",
    "GIT_AUTHOR_EMAIL": "factory@example.invalid",
    "GIT_COMMITTER_NAME": "Factory",
    "GIT_COMMITTER_EMAIL": "factory@example.invalid",
}


class GitError(Exception):
    pass


def git(*args, cwd=None, check=True):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env={**os.environ, **IDENTITY})
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
