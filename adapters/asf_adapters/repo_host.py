"""Repo Host Adapter: git over the server at $REPO_HOST_URL (`<url>/<repo>.git`).

The contract is in docs/adapters/README.md. Reads go through a local mirror of the server's branches
(under $ADAPTER_CACHE); writes are pushes. Clones handed out have one branch and no remote.
"""
import subprocess

from . import common as _common
from .common import IDENTITY, Failure, git, remote

MIRROR = "+refs/heads/*:refs/heads/*"


def mirror(repo):
    return _common.mirror("repo-host", repo, MIRROR)


def main_head(a):
    out = git("ls-remote", remote(a["repo"]), "refs/heads/main")
    if not out:
        raise Failure("repository has no main")
    return {"commit": out.split()[0]}


def create_branch(a):
    if a["name"] == "main":
        raise Failure("main is only advanced by fast-forward-main")
    cache = mirror(a["repo"])
    commit = git("rev-parse", "--verify", f"{a['base']}^{{commit}}", cwd=cache)
    git("push", "-q", "--force", remote(a["repo"]), f"{commit}:refs/heads/{a['name']}", cwd=cache)
    return {"commit": commit}


def checkout(a):
    cache, dest = mirror(a["repo"]), a["dest"]
    ref, local = (f"refs/heads/{a['branch']}", a["branch"]) if "branch" in a else (a["commit"], "work")
    git("init", "-q", dest)
    git("fetch", "-q", cache, ref, cwd=dest)  # no remote is configured
    git("checkout", "-q", "-b", local, "FETCH_HEAD", cwd=dest)
    git("config", "user.name", "Factory", cwd=dest)
    git("config", "user.email", IDENTITY["GIT_AUTHOR_EMAIL"], cwd=dest)
    return {"commit": git("rev-parse", "HEAD", cwd=dest)}


def record(a):
    src, branch, url = a["from"], a["branch"], remote(a["repo"])
    git("add", "-A", cwd=src)
    if git("status", "--porcelain", cwd=src):
        git("commit", "-q", "-m", f"Record {branch}", cwd=src)
    cache = mirror(a["repo"])
    before = git("rev-parse", "-q", "--verify", f"refs/heads/{branch}^{{tree}}", cwd=cache, check=False)
    after = git("rev-parse", "HEAD^{tree}", cwd=src)
    git("push", "-q", "--force", url, f"HEAD:refs/heads/{branch}", cwd=src)
    return {"commit": git("rev-parse", "HEAD", cwd=src), "changed": before != after}


def fast_forward_main(a):
    cache = mirror(a["repo"])
    head = git("rev-parse", "refs/heads/main", cwd=cache)
    commit = git("rev-parse", f"refs/heads/{a['branch']}", cwd=cache)
    if head != a["expect-main"] or git("merge-base", "--is-ancestor", head, commit, cwd=cache,
                                       check=False) is None:
        return {"advanced": False, "head": head}
    lease = f"--force-with-lease=refs/heads/main:{head}"
    pushed = subprocess.run(["git", "push", "-q", lease, remote(a["repo"]),
                                     f"{commit}:refs/heads/main"], cwd=cache, capture_output=True)
    if pushed.returncode:  # main moved, or the server refused
        return {"advanced": False, "head": main_head(a)["commit"]}
    return {"advanced": True, "head": commit}



def main():
    _common.main({"main-head": main_head, "create-branch": create_branch, "checkout": checkout,
                  "record": record, "fast-forward-main": fast_forward_main})
