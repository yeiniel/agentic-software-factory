"""Runner against real Podman with the stub entrypoints: mounts, time limit, network, results."""
import subprocess
from pathlib import Path

import pytest

from helpers import CONTAINERFILE, needs_podman

pytestmark = needs_podman


@pytest.fixture
def runner(exe, repo):
    commit = repo({"README": "x", "Containerfile": CONTAINERFILE})
    builder = exe("environment-builder")
    images = {p: builder.ok("build", repo="r", commit=commit, purpose=p)["image"] for p in ("agent", "integrator")}
    r = exe("runner")
    r.images = images
    return r


def agent(runner, prompt="do it", run=1, task="r/t1", role="implementor", timeout=60):
    ctx = Path(runner.ok("provision-context", {"prompt": prompt, "resume": run > 1}, kind=role, task=task,
                         run=run)["context"])
    (ctx / "work").mkdir()
    subprocess.run(["git", "init", "-q", str(ctx / "work")], check=True)
    result = runner.ok("run-agent", image=runner.images["agent"], context=ctx, task=task, role=role,
                       timeout=timeout)
    return ctx, result


def test_the_context_is_mounted_with_the_prompt_and_the_work_tree(runner):
    ctx, result = agent(runner, "add a greeting")
    assert result["exit_status"] == 0 and not result["timed_out"]
    assert "prompt=add a greeting" in result["output"]
    assert (ctx / "work" / "stub.txt").read_text() == "stub\n"  # the Agent's edit is visible outside


def test_the_work_tree_has_no_remote(runner):
    _, result = agent(runner)
    assert "remotes=0" in result["output"]


def test_the_agent_gets_the_model_server_settings_and_no_credentials(runner):
    _, result = agent(runner)
    assert "model=http://model:8080/v1 qwen 98304" in result["output"]
    assert "env=0" in result["output"]


def test_the_agent_runs_on_the_configured_network(runner):
    runner.env["RUNNER_AGENT_NETWORK"] = "none"
    _, result = agent(runner)
    assert "interfaces=lo" in result["output"]


def test_the_exit_status_of_a_failing_agent_is_reported(runner):
    _, result = agent(runner, "FAIL please")
    assert result["exit_status"] == 3 and not result["timed_out"]


def test_an_agent_over_its_time_limit_is_stopped(runner):
    _, result = agent(runner, "HANG", timeout=3)
    assert result["timed_out"] is True and result["exit_status"] is None
    assert subprocess.run(["podman", "ps", "-q", "--filter", "name=asf-"], capture_output=True,
                          text=True).stdout.strip() == ""


def test_the_transcript_points_at_the_session_state(runner):
    ctx, result = agent(runner)
    assert Path(result["transcript"]).read_text() == '{"stub": true}\n'


def test_session_state_is_kept_per_task_and_role_across_runs(runner):
    _, first = agent(runner, run=1)
    _, again = agent(runner, run=2)
    other_role = agent(runner, role="acceptance-writer", run=1)[1]
    other_task = agent(runner, task="r/t2", run=1)[1]
    assert "session=0" in first["output"]
    assert "session=1" in again["output"]
    assert "session=0" in other_role["output"] and "session=0" in other_task["output"]


def integrate(runner, script=None, timeout=60):
    ctx = runner.ok("provision-context", kind="integrator", task="r/t1", run=1)["context"]
    if script:
        (Path(ctx) / "script").write_text(script)
    return Path(ctx), runner.run("run-integrator", image=runner.images["integrator"], context=ctx,
                                 timeout=timeout)


def test_the_integrator_has_no_network_and_returns_its_green_verdict(runner):
    import json
    ctx, done = integrate(runner)
    result = json.loads(done.stdout)
    assert result["verdict"] == {"result": "green"} and result["output"] == "suite green\n"
    assert (ctx / "result").is_dir()


def test_a_red_verdict_names_the_failed_check_and_returns_the_output_verbatim(runner):
    import json
    _, done = integrate(runner, "RED")
    result = json.loads(done.stdout)
    assert result["exit_status"] == 1
    assert result["verdict"] == {"result": "red", "failed_check": "suite", "spec_output": "spec out\n"}
    assert result["output"] == "suite out\n"


def test_an_integrator_that_leaves_no_verdict_is_an_infrastructure_error(runner):
    _, done = integrate(runner, "NONE")
    assert done.returncode != 0 and "no verdict" in done.stderr


def test_an_integrator_over_its_time_limit_is_stopped(runner):
    import json
    _, done = integrate(runner, "HANG", timeout=3)
    assert json.loads(done.stdout)["timed_out"] is True


def test_the_integrator_runs_without_network(runner):
    ctx, _ = integrate(runner)
    assert (ctx / "interfaces").read_text().split() == ["lo"]
