"""Runner against real Podman with the stub entrypoint: mounts, time limit, network, results, builds."""

import hashlib
import subprocess
from pathlib import Path

import pytest

from helpers import CONTAINERFILE, needs_podman

pytestmark = needs_podman


@pytest.fixture
def runner(exe):
    return exe("runner")


def agentic_context(tmp_path, prompt="do it", name="agent", containerfile=CONTAINERFILE):
    ctx = tmp_path / "contexts" / name
    (ctx / "cwd").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(ctx / "cwd")], check=True)
    (ctx / "cwd" / "Containerfile").write_text(containerfile)
    (ctx / "skills" / "a-skill").mkdir(parents=True)
    (ctx / "prompt").write_text(prompt)
    return ctx


def agent(runner, ctx, timeout=60):
    return runner.ok("run", type="agentic", context=ctx, timeout=timeout)


def deterministic_context(tmp_path, script, name="det", containerfile=CONTAINERFILE):
    ctx = tmp_path / "contexts" / name
    (ctx / "cwd").mkdir(parents=True)
    (ctx / "cwd" / "Containerfile").write_text(containerfile)
    (ctx / "cwd" / "input").write_text("some input\n")
    (ctx / "out").mkdir()
    (ctx / "run").write_text("#!/bin/sh\n" + script)
    (ctx / "run").chmod(0o755)
    return ctx


def test_the_agent_sees_the_context_prompt_skills_and_working_directory(runner, tmp_path):
    ctx = agentic_context(tmp_path, "add a greeting")
    result = agent(runner, ctx)
    assert result["exit_status"] == 0 and not result["timed_out"]
    assert "prompt=add a greeting" in result["output"]
    assert "skills=a-skill" in result["output"]
    assert (ctx / "cwd" / "stub.txt").read_text() == "stub\n"  # the Agent's edit is visible outside


def test_the_working_directory_has_no_remote(runner, tmp_path):
    assert "remotes=0" in agent(runner, agentic_context(tmp_path))["output"]


def test_the_agent_gets_the_model_server_settings_and_no_credentials(runner, tmp_path):
    output = agent(runner, agentic_context(tmp_path))["output"]
    assert "model=http://model:8080/v1 qwen 98304" in output
    assert "env=0" in output


def test_the_agent_runs_on_the_configured_network(runner, tmp_path):
    runner.env["RUNNER_AGENT_NETWORK"] = "none"
    assert "interfaces=lo" in agent(runner, agentic_context(tmp_path))["output"]


def test_the_exit_status_of_a_failing_agent_is_reported(runner, tmp_path):
    result = agent(runner, agentic_context(tmp_path, "FAIL please"))
    assert result["exit_status"] == 3 and not result["timed_out"]


def test_an_agent_over_its_time_limit_is_stopped(runner, tmp_path):
    result = agent(runner, agentic_context(tmp_path, "HANG"), timeout=3)
    assert result["timed_out"] is True and result["exit_status"] is None
    assert (
        subprocess.run(["podman", "ps", "-q", "--filter", "name=asf-"], capture_output=True, text=True).stdout.strip()
        == ""
    )


def test_the_transcript_is_the_newest_session_file_of_this_run(runner, tmp_path):
    ctx = agentic_context(tmp_path)
    (ctx / "session").mkdir()
    (ctx / "session" / "old.jsonl").write_text("old\n")
    result = agent(runner, ctx)
    assert Path(result["transcript"]).read_text() == '{"stub": true}\n'


def test_the_same_context_handed_back_resumes_its_session(runner, tmp_path):
    ctx = agentic_context(tmp_path)
    other = agentic_context(tmp_path, name="other")
    first, again, fresh = agent(runner, ctx), agent(runner, ctx), agent(runner, other)
    assert "session=0" in first["output"] and "session=1" in again["output"]
    assert "session=0" in fresh["output"]


def test_a_deterministic_run_has_no_network_and_runs_in_cwd(runner, tmp_path):
    ctx = deterministic_context(tmp_path, "ls /sys/class/net > ../out/interfaces; cat input > ../out/seen\n")
    result = runner.ok("run", type="deterministic", context=ctx, timeout=60)
    assert result["files"] == {"interfaces": "lo\n", "seen": "some input\n"}


def test_a_failing_deterministic_run_reports_its_status_and_files(runner, tmp_path):
    ctx = deterministic_context(tmp_path, "echo red > ../out/result; exit 1\n")
    result = runner.ok("run", type="deterministic", context=ctx, timeout=60)
    assert result["exit_status"] == 1 and result["files"] == {"result": "red\n"}


def test_a_deterministic_run_over_its_time_limit_is_stopped(runner, tmp_path):
    result = runner.ok("run", type="deterministic", context=deterministic_context(tmp_path, "sleep 60\n"), timeout=3)
    assert result["timed_out"] is True and result["exit_status"] is None


def test_oversized_files_are_capped_keeping_the_tail(runner, tmp_path):
    ctx = deterministic_context(
        tmp_path, "head -c 1500000 /dev/zero | tr '\\0' A > ../out/big; echo END >> ../out/big\n"
    )
    big = runner.ok("run", type="deterministic", context=ctx, timeout=60)["files"]["big"]
    assert len(big) < 1_100_000 and big.endswith("END\n")


@pytest.mark.parametrize("type_", ["agentic", "deterministic"])
def test_a_context_without_a_containerfile_is_reported(runner, tmp_path, type_):
    ctx = (agentic_context if type_ == "agentic" else lambda p: deterministic_context(p, "true\n"))(tmp_path)
    (ctx / "cwd" / "Containerfile").unlink()
    done = runner.run("run", type=type_, context=ctx, timeout=60)
    assert done.returncode != 0 and "no Containerfile" in done.stderr


@pytest.mark.parametrize(
    ("missing", "containerfile"),
    [
        ("make", "FROM docker.io/library/alpine\nRUN apk add --no-cache git\n"),
        ("git", "FROM docker.io/library/alpine\nRUN apk add --no-cache make\n"),
    ],
)
def test_an_image_without_git_or_make_is_reported_and_not_kept(runner, tmp_path, missing, containerfile):
    ctx = agentic_context(tmp_path, containerfile=containerfile)
    done = runner.run("run", type="agentic", context=ctx, timeout=60)
    assert done.returncode != 0 and f"lacks `{missing}`" in done.stderr
    tag = "localhost/asf-base:" + hashlib.sha256(containerfile.encode()).hexdigest()[:12]
    assert subprocess.run(["podman", "image", "exists", tag]).returncode != 0


def test_a_build_that_fails_is_an_infrastructure_error(runner, tmp_path):
    ctx = agentic_context(tmp_path, containerfile="FROM docker.io/library/alpine\nRUN exit 7\n")
    done = runner.run("run", type="agentic", context=ctx, timeout=60)
    assert done.returncode != 0 and "podman build" in done.stderr


def test_the_build_has_its_own_time_limit(runner, tmp_path):
    ctx = agentic_context(tmp_path, containerfile=CONTAINERFILE + "RUN sleep 30\n")
    done = runner.run("run", type="agentic", context=ctx, timeout=60, **{"build-timeout": 3})
    assert done.returncode != 0 and "exceeded" in done.stderr


def test_a_second_run_reuses_the_cached_image(runner, tmp_path):
    log = tmp_path / "podman.log"
    wrapper = tmp_path / "podman"
    wrapper.write_text(f'#!/bin/sh\necho "$1" >> {log}\nexec podman "$@"\n')
    wrapper.chmod(0o755)
    runner.env["PODMAN"] = str(wrapper)
    ctx = agentic_context(tmp_path)
    agent(runner, ctx)
    log.write_text("")
    agent(runner, ctx)
    assert "build" not in log.read_text().split()
