"""The implementor-golden Graph: the Implementor against a fixed suite, with no Acceptance Writer (spec 0008).

An experiment Graph, a folder next to the default one. `tools/make-golden` writes its `golden/run`.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_real_integrator import IMPLEMENTED, PROJECT

GRAPH = Path(__file__).parent.parent / "src" / "factory" / "graphs" / "implementor-golden"
MAKE_GOLDEN = Path(__file__).parent.parent / "tools" / "make-golden"
TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}
SPEC = "grep -q hello src/greeting.txt\n"
GIT = {
    **os.environ,
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def git(*args, cwd=None):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=GIT, check=True)
    return done.stdout.strip()


def seeded(tmp_path, name, files):
    """A work tree with one commit per entry of `files` (a list of dicts), and its bare copy."""
    work = tmp_path / name
    work.mkdir()
    git("init", "-q", "-b", "main", cwd=work)
    for change in files:
        for path, text in change.items():
            (work / path).parent.mkdir(parents=True, exist_ok=True)
            (work / path).write_text(text)
        git("add", "-A", cwd=work)
        git("commit", "-q", "-m", "c", cwd=work)
    bare = tmp_path / f"{name}.git"
    git("clone", "-q", "--bare", str(work), str(bare))
    return bare


def run_script(script, tmp_path, base_commit_of):
    """Run a `golden/run` the way the Runner does: `cwd` holds the clone `base`, `out` is the sibling."""
    ctx = tmp_path / "ctx"
    (ctx / "cwd").mkdir(parents=True)
    git("clone", "-q", str(base_commit_of), str(ctx / "cwd" / "base"))
    done = subprocess.run([str(script)], cwd=ctx / "cwd", env=GIT, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return ctx / "out"


def test_the_graph_is_valid_and_the_factory_starts_on_it(run_factory):
    out = run_factory({"events": []}, graph=str(GRAPH))

    assert out.exit_code == 0, out.stderr


def test_the_golden_script_writes_the_specs_of_the_base_it_was_made_for(tmp_path):
    bare = seeded(tmp_path, "w", [{"README": "base\n"}])
    git("--git-dir", str(bare), "update-ref", "refs/heads/writer", "main")
    work = tmp_path / "w"
    (work / "specs").mkdir()
    (work / "specs" / "a.sh").write_text(SPEC)
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "specs", cwd=work)
    git("push", "-q", str(bare), "HEAD:refs/heads/writer", cwd=work)
    script = tmp_path / "run"
    subprocess.run([str(MAKE_GOLDEN), str(script), str(bare), "refs/heads/writer"], check=True)
    base = tmp_path / "base"
    git("clone", "-q", "--bare", str(bare), str(base))
    git("--git-dir", str(base), "symbolic-ref", "HEAD", "refs/heads/main")

    out = run_script(script, tmp_path, base)

    assert (out / "result").read_text().strip() == "green"
    assert (out / "golden" / "specs" / "a.sh").read_text() == SPEC
    assert git("log", "--format=%s", cwd=out / "golden") == "Golden specs\nc"


def test_the_golden_script_reports_a_base_it_has_no_specs_for(tmp_path):
    bare = seeded(tmp_path, "w", [{"README": "base\n"}, {"specs/a.sh": SPEC}])
    script = tmp_path / "run"
    subprocess.run([str(MAKE_GOLDEN), str(script), str(bare), "main"], check=True)
    elsewhere = seeded(tmp_path, "other", [{"README": "something else\n"}])

    out = run_script(script, tmp_path, elsewhere)

    assert (out / "result").read_text().strip() == "red"
    assert (out / "failed_check").read_text() == "no-golden"
    assert "no golden specs for base commit" in (out / "output").read_text()


def test_the_golden_script_reports_specs_that_do_not_apply(tmp_path):
    bare = seeded(tmp_path, "w", [{"README": "base\n"}, {"README": "base\nmore\n"}])
    script = tmp_path / "run"
    subprocess.run([str(MAKE_GOLDEN), str(script), str(bare), "main"], check=True)
    broken = script.read_text().replace("\n base\n", "\n different\n")  # a context line the base does not have
    script.write_text(broken)
    first = git("--git-dir", str(bare), "rev-parse", "main^")
    clone = tmp_path / "base"
    git("clone", "-q", "--bare", str(bare), str(clone))
    git("--git-dir", str(clone), "update-ref", "refs/heads/main", first)

    out = run_script(script, tmp_path, clone)

    assert (out / "failed_check").read_text() == "no-golden"
    assert "do not apply" in (out / "output").read_text()


def test_make_golden_refuses_unpaired_arguments():
    done = subprocess.run([str(MAKE_GOLDEN), "out", "only-a-dir"], capture_output=True, text=True, check=False)

    assert done.returncode == 2
    assert "Usage" in done.stderr


def test_the_implementor_runs_against_the_golden_specs_and_no_writer_runs(run_factory, tmp_path):
    folder = tmp_path / "graph"
    shutil.copytree(GRAPH, folder, ignore=shutil.ignore_patterns("__pycache__"))
    (folder / "golden" / "run").write_text(
        "#!/bin/sh\n"
        'out=$(cd .. && pwd)/out; mkdir -p "$out"\n'
        'git clone -q base "$out/golden"; mkdir -p "$out/golden/specs"\n'
        f"printf %s '{SPEC}' >\"$out/golden/specs/greeting.sh\"\n"
        'git -C "$out/golden" add -A\n'
        'git -C "$out/golden" -c user.name=G -c user.email=g@example.invalid commit -q -m golden\n'
        'echo green >"$out/result"; echo ok >"$out/output"\n'
    )

    out = run_factory(
        {"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT], "agent": {"implementor": [{"edits": IMPLEMENTED}]}},
        real_git=PROJECT,
        graph=str(folder),
    )

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "done"], out.events("task/t1", "infrastructure-error")
    assert [r["role"] for r in out.state["agent_runs"]] == ["implementor"]
    assert out.git_main("src/greeting.txt") == "hello\n"
    assert out.git_main("specs/greeting.sh") == SPEC


def test_a_base_with_no_golden_blocks_the_task_before_any_agent_runs(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]}, real_git=PROJECT, graph=str(GRAPH))

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "blocked"]
    assert out.events("task/t1", "task-status")[-1]["reason"] == "no-golden"
    assert out.state["agent_runs"] == []


@pytest.mark.parametrize("name", ["golden/run", "feedback", "integrator", "roles/implementor"])
def test_everything_the_graph_names_is_in_its_folder(name):
    assert (GRAPH / name).exists()
