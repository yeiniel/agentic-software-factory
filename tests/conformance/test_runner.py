from pathlib import Path

import pytest

ROLES = ["implementor", "acceptance-writer"]
CHECKS = {"specs-not-red", "conflict", "suite"}


@pytest.fixture
def runner(adapter):
    return adapter("runner")


def provision(runner, kind, run=1, **extra):
    body = {"prompt": "do it", "resume": False} if kind != "integrator" else None
    ctx = runner.ok("provision-context", body, kind=kind, task=runner.fixture["task"], run=run,
                    **extra)["context"]
    assert Path(ctx).is_dir()
    return ctx


@pytest.mark.parametrize("kind", [*ROLES, "integrator"])
def test_provision_context_returns_an_existing_directory(runner, kind):
    provision(runner, kind)


def test_each_kind_and_run_gets_its_own_context(runner):
    contexts = {provision(runner, "implementor", 1), provision(runner, "implementor", 2),
                provision(runner, "acceptance-writer", 1)}
    assert len(contexts) == 3


def test_integrator_passes_in_one_run_get_fresh_contexts(runner):
    assert provision(runner, "integrator", attempt=0) != provision(runner, "integrator", attempt=1)


def test_provisioning_an_unknown_kind_fails(runner):
    runner.fails("provision-context", {"prompt": "x", "resume": False}, kind="wizard", task=runner.fixture["task"], run=1)


@pytest.mark.parametrize("role", ROLES)
def test_run_agent_reports_the_documented_fields(runner, role):
    ctx = provision(runner, role)
    result = runner.ok("run-agent", image=runner.fixture["agent_image"], context=ctx,
                       task=runner.fixture["task"], role=role, timeout=30)
    assert isinstance(result["timed_out"], bool)
    assert result["exit_status"] is None or isinstance(result["exit_status"], int)
    assert isinstance(result["output"], str)
    assert isinstance(result["transcript"], str)


def test_run_integrator_returns_a_verdict(runner):
    ctx = provision(runner, "integrator")
    result = runner.ok("run-integrator", image=runner.fixture["integrator_image"], context=ctx, timeout=30)
    assert isinstance(result["timed_out"], bool)
    assert isinstance(result["output"], str)
    verdict = result["verdict"]
    assert verdict["result"] in ("green", "red")
    if verdict["result"] == "red":
        assert verdict["failed_check"] in CHECKS
        assert isinstance(verdict["spec_output"], str)
    else:
        assert (Path(ctx) / "result").is_dir()


def test_unknown_operation_fails(runner):
    runner.fails("no-such-op")
