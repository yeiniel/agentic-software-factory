"""The Runner's one operation, `run`, for both Environment types (docs/adapters/README.md)."""
import json

import pytest

CONTAINERFILE = "FROM docker.io/library/alpine\nRUN apk add --no-cache git make\n"


@pytest.fixture
def runner(adapter):
    return adapter("runner")


def context(tmp_path, kind, run_script="echo hi > ../out/hello\n"):
    """A Run Context in the standard layout (docs/specs/0004)."""
    ctx = tmp_path / "ctx" / kind
    (ctx / "cwd").mkdir(parents=True)
    (ctx / "cwd" / "Containerfile").write_text(CONTAINERFILE)
    if kind == "agentic":
        (ctx / "skills" / "a-skill").mkdir(parents=True)
        (ctx / "prompt").write_text("do it")
    else:
        (ctx / "out").mkdir()
        (ctx / "run").write_text("#!/bin/sh\n" + run_script)
        (ctx / "run").chmod(0o755)
    return ctx


def run(runner, ctx, kind, **extra):
    return runner.ok("run", type=kind, context=ctx, timeout=60, **{"build-timeout": 600}, **extra)


def test_an_agentic_run_reports_the_documented_fields(runner, tmp_path):
    result = run(runner, context(tmp_path, "agentic"), "agentic")
    assert isinstance(result["timed_out"], bool)
    assert result["exit_status"] is None or isinstance(result["exit_status"], int)
    assert isinstance(result["output"], str)
    assert isinstance(result["transcript"], str)


def test_a_deterministic_run_returns_the_text_of_the_files_in_out(runner, tmp_path):
    result = run(runner, context(tmp_path, "deterministic"), "deterministic")
    assert result["exit_status"] == 0 and result["timed_out"] is False
    assert result["files"] == {"hello": "hi\n"}
    assert isinstance(result["output"], str)


def test_directories_in_out_are_not_files(runner, tmp_path):
    ctx = context(tmp_path, "deterministic", "mkdir ../out/clone; echo x > ../out/clone/f; echo y > ../out/top\n")
    assert run(runner, ctx, "deterministic")["files"] == {"top": "y\n"}


def test_a_failing_run_is_data_not_an_error(runner, tmp_path):
    result = run(runner, context(tmp_path, "deterministic", "exit 3\n"), "deterministic")
    assert result["exit_status"] == 3 and result["timed_out"] is False


def test_an_unknown_type_fails(runner, tmp_path):
    runner.fails("run", type="wizard", context=context(tmp_path, "agentic"), timeout=10)


def test_unknown_operation_fails(runner):
    runner.fails("no-such-op")
