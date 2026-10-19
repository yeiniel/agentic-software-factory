"""The Integrator script against real git and a tiny real `make test`."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from helpers import CONTAINERFILE, ROOT, Exe, needs_podman

SCRIPT = ROOT / "images" / "integrator" / "integrator.sh"
MAKEFILE = "test:\n\t@sh check.sh\n"
CHECK = "[ ! -e spec_feature ] || [ -e feature.txt ] || { echo 'feature.txt is missing'; exit 1; }\n"


def git(path, *args):
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                   check=True, capture_output=True)


def commit(path, files, message="change"):
    for name, text in files.items():
        (path / name).write_text(text)
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)


@pytest.fixture
def context(tmp_path):
    """A Run Context: base, main (same as base) and a clone per role."""
    ctx = tmp_path / "ctx"
    base = ctx / "base"
    base.mkdir(parents=True)
    git(base, "init", "-q", "-b", "main")
    commit(base, {"Makefile": MAKEFILE, "check.sh": CHECK, "code.txt": "one\n"}, "base")
    for name in ("main", "implementor", "acceptance-writer"):
        subprocess.run(["git", "clone", "-q", str(base), str(ctx / name)], check=True)
    return ctx


def integrate(ctx):
    env = {k: v for k, v in os.environ.items() if k not in ("MAKELEVEL", "MAKEFLAGS", "MFLAGS")}  # we may run under make
    done = subprocess.run(["sh", str(SCRIPT), str(ctx)], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    v = ctx / "verdict"
    return {name: (v / name).read_text() for name in ("result", "output", "spec_output", "failed_check")
            if (v / name).exists()}


def test_branches_that_merge_and_pass_are_green_and_the_result_is_returned(context):
    commit(context / "acceptance-writer", {"spec_feature": ""})
    commit(context / "implementor", {"feature.txt": "feature\n"})
    commit(context / "main", {"unrelated.txt": "moved\n"}, "main moved")
    verdict = integrate(context)
    assert verdict["result"].strip() == "green"
    result = context / "result"
    assert all((result / name).exists() for name in ("feature.txt", "spec_feature", "unrelated.txt"))


def test_specs_that_are_not_red_on_base_fail_the_first_check(context):
    commit(context / "acceptance-writer", {"spec_feature": ""})
    commit(context / "acceptance-writer", {"feature.txt": "already\n"})
    verdict = integrate(context)
    assert verdict["result"].strip() == "red" and verdict["failed_check"] == "specs-not-red"
    assert not (context / "result").exists()


def test_a_conflict_fails_the_second_check_with_git_output(context):
    commit(context / "acceptance-writer", {"spec_feature": ""})
    commit(context / "implementor", {"code.txt": "two\n"})
    commit(context / "main", {"code.txt": "three\n"}, "main moved")
    verdict = integrate(context)
    assert verdict["result"].strip() == "red" and verdict["failed_check"] == "conflict"
    assert "code.txt" in verdict["output"]


def test_a_red_suite_reports_the_acceptance_report_verbatim(context):
    commit(context / "acceptance-writer", {"spec_feature": ""})
    verdict = integrate(context)
    assert verdict["result"].strip() == "red" and verdict["failed_check"] == "suite"
    assert verdict["output"].startswith("feature.txt is missing\n")
    assert verdict["spec_output"].startswith("feature.txt is missing\n")


@needs_podman
def test_the_integrator_layer_runs_in_a_container_built_from_the_repos_image(exe, repo, context, tmp_path):
    commit_sha = repo({"README": "x", "Containerfile": CONTAINERFILE})
    env = dict(exe("environment-builder").env)
    env.pop("ASF_IMAGES_DIR")  # the real layers
    image = Exe("environment-builder", env).ok("build", repo="r", commit=commit_sha, purpose="integrator")["image"]
    commit(context / "acceptance-writer", {"spec_feature": ""})
    runner = Exe("runner", env)
    done = runner.run("run-integrator", image=image, context=context, timeout=120)
    result = json.loads(done.stdout)
    assert result["verdict"]["failed_check"] == "suite" and result["output"].startswith("feature.txt is missing\n")
