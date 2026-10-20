"""The Acceptance Test Validation script against real git and a tiny real `make test`."""
import os
import subprocess

import pytest

from test_integrator import CHECK, MAKEFILE, ROOT, commit, git

SCRIPT = ROOT / "src" / "factory" / "resources" / "validation" / "run"


@pytest.fixture
def context(tmp_path):
    """A Run Context's `cwd`: base and a clone for the Acceptance Writer; results go to ../out."""
    ctx = tmp_path / "ctx" / "cwd"
    base = ctx / "base"
    base.mkdir(parents=True)
    git(base, "init", "-q", "-b", "main")
    commit(base, {"Makefile": MAKEFILE, "check.sh": CHECK, "code.txt": "one\n"}, "base")
    subprocess.run(["git", "clone", "-q", str(base), str(ctx / "acceptance-writer")], check=True)
    return ctx


def validate(ctx):
    env = {k: v for k, v in os.environ.items() if k not in ("MAKELEVEL", "MAKEFLAGS", "MFLAGS")}
    done = subprocess.run(["sh", str(SCRIPT)], cwd=ctx, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    out = ctx.parent / "out"
    return {name: (out / name).read_text() for name in ("result", "output", "failed_check")
            if (out / name).exists()}


def test_specs_that_fail_on_base_are_green_with_the_acceptance_report(context):
    commit(context / "acceptance-writer", {"spec_feature": ""})
    verdict = validate(context)
    assert verdict["result"].strip() == "green"
    assert verdict["output"].startswith("feature.txt is missing\n")
    assert not (context.parent / "out" / "integrated").exists()


def test_specs_that_pass_on_base_are_red_as_not_red(context):
    commit(context / "acceptance-writer", {"spec_feature": ""})
    commit(context / "acceptance-writer", {"feature.txt": "already\n"})
    verdict = validate(context)
    assert verdict["result"].strip() == "red" and verdict["failed_check"] == "specs-not-red"


def test_a_branch_that_does_not_merge_onto_the_base_is_red_as_merge(context):
    commit(context / "base", {"code.txt": "two\n"}, "base moved")
    commit(context / "acceptance-writer", {"code.txt": "three\n"})
    # the Writer's branch was cut before the base moved, so its change to the same line conflicts
    verdict = validate(context)
    assert verdict["result"].strip() == "red" and verdict["failed_check"] == "merge"
    assert "code.txt" in verdict["output"]
