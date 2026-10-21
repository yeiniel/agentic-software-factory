"""Task Store Adapter: Tasks are git-native issues (`refs/issues/<uuid>`) on the git server.

A Task is `<repo>/<issue id>` (an id prefix is enough). The prompt is the issue's title and body.
Status lives in the newest commit's trailers: running and blocked are labels on an open issue, done is
`State: closed` with `Fixed-By: <commit>`. Changes are pushed back to the server.
"""
import json
import os
import re

from . import common as _common
from .common import Failure, git

TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: ")
STATUS_LABELS = ("running", "blocked")
ISSUES = "+refs/issues/*:refs/issues/*"


def trailers(message):
    """The trailer block (last paragraph of `Key: value` lines) of a commit message, as a dict."""
    paragraph = message.strip().split("\n\n")[-1].splitlines()
    if len(message.strip().split("\n\n")) < 2 or not all(TRAILER.match(l) for l in paragraph):
        return {}
    found = dict(line.split(": ", 1) for line in paragraph)
    return found if "Format-Version" in found else {}  # every git-native-issue commit carries it


def body_of(message):
    """The message without its trailer block."""
    parts = message.strip().split("\n\n")
    return "\n\n".join(parts[:-1] if trailers(message) else parts)


def resolve(task):
    repo, _, ident = task.rpartition("/")
    if not repo or not ident:
        raise Failure(f"task {task!r} is not <repo>/<issue>")
    cache = _common.mirror("task-store", repo, ISSUES)
    refs = git("for-each-ref", "--format=%(refname)", f"refs/issues/{ident}*", cwd=cache).split()
    if len(refs) != 1:
        raise Failure(f"{len(refs)} issues match {task!r}")
    return repo, cache, refs[0]


def get_prompt(a):
    _, cache, ref = resolve(a["task"])
    root = git("rev-list", "--max-parents=0", ref, cwd=cache)
    return {"prompt": body_of(git("log", "-1", "--format=%B", root, cwd=cache))}


def current_labels(cache, ref):
    """Labels as of the newest commit that states them (comments carry no trailers)."""
    for message in git("log", "--format=%B%x00", ref, cwd=cache).split("\0"):
        found = trailers(message)
        if "State" in found:
            return [l for l in found.get("Labels", "").split(", ") if l]
    return []


def set_status(a):
    status = a["status"]
    if status not in ("todo", "running", "done", "blocked"):
        raise Failure(f"unknown status {status!r}")
    body = _common.read_body() or {}
    for attempt in range(3):  # someone else may append to the issue between our fetch and push
        try:
            return push_status(a["task"], status, body)
        except Failure:
            if attempt == 2:
                raise


def push_status(task, status, body):
    repo, cache, ref = resolve(task)
    labels = [l for l in current_labels(cache, ref) if l not in STATUS_LABELS]
    detail, extra = "", {}
    if status in STATUS_LABELS:
        labels.append(status)
    if status == "blocked":
        detail = json.dumps({k: body[k] for k in ("reason", "history") if k in body}, indent=1) + "\n\n"
    if status == "done":
        extra["Fixed-By"] = body.get("commit", "")
    lines = {"State": "closed" if status == "done" else "open", "Labels": ", ".join(labels), **extra,
             "Format-Version": "1"}
    if not lines["Labels"]:
        del lines["Labels"]
    message = f"Status: {status}\n\n{detail}" + "\n".join(f"{k}: {v}" for k, v in lines.items()) + "\n"
    tree = git("hash-object", "-t", "tree", os.devnull)
    commit = git("commit-tree", tree, "-p", ref, "-m", message, cwd=cache)
    git("push", "-q", _common.remote(repo), f"{commit}:{ref}", cwd=cache)
    return {}



def main():
    _common.main({"get-prompt": get_prompt, "set-status": set_status})
