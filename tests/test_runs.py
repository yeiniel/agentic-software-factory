"""The Factory as a black-box process: observable results only."""

TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}


def test_green_first_run_advances_main_and_marks_task_done(run_factory):
    out = run_factory({"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT]})

    assert out.exit_code == 0, out.stderr
    assert out.main["implementor.txt"] == "implementor run 1"
    assert out.main["acceptance-writer.txt"] == "acceptance-writer run 1"
    assert out.status("t1") == ["running", "done"]
    ff = out.calls_to("repo-host", "fast-forward-main")
    assert len(ff) == 1
    # done only after main advanced
    order = [(c["port"], c["op"]) for c in out.calls]
    assert order.index(("repo-host", "fast-forward-main")) < max(
        i for i, c in enumerate(out.calls) if c["op"] == "set-status")


def agent_runs(out):
    return [r["role"] for r in out.state["agent_runs"]]


def prompts(out, role):
    return [r["prompt"] for r in out.state["agent_runs"] if r["role"] == role]


def red(check, output, **extra):
    return {"result": "red", "failed_check": check, "output": output, **extra}


def test_implementor_failure_retriggers_only_the_implementor_with_feedback(run_factory):
    out = run_factory({"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT],
                       "integrator": [red("suite", "FAIL: greeting is empty")]})

    assert out.exit_code == 0, out.stderr
    assert agent_runs(out).count("implementor") == 2
    assert agent_runs(out).count("acceptance-writer") == 1
    first, retry = prompts(out, "implementor")
    assert "FAIL: greeting is empty" not in first
    assert "FAIL: greeting is empty" in retry
    # the retried Agent gets its own Context back with its session, but its code starts again from the base
    first_run, retry_run = [r for r in out.state["agent_runs"] if r["role"] == "implementor"]
    assert retry_run["context"] == first_run["context"]
    assert retry_run["resumed"] and not first_run["resumed"]
    assert retry_run["cwd"] == ["README"]
    assert "start again from the original code" in retry
    # two Agents once, the Writer's validation, the Integrator's four twice, the retry's own
    assert len(out.calls_to("repo-host", "checkout")) == 2 + 2 + 4 + 1 + 4
    assert all("acceptance-writer" not in p for p in prompts(out, "implementor"))
    assert out.main["implementor.txt"] == "implementor run 2"
    assert out.main["acceptance-writer.txt"] == "acceptance-writer run 1"
    assert out.status("t1") == ["running", "running", "done"]
    assert [e["run"] for r in out.records for e in [r["event"]] if e["kind"] == "run-started"] == [1, 2]


def test_specs_not_red_on_base_retry_the_writer_with_the_reason_first(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "validation": [{"result": "red", "failed_check": "specs-not-red",
                                       "output": "specs passed on base"}]})

    assert sorted(agent_runs(out)) == ["acceptance-writer", "acceptance-writer", "implementor"]
    retry = prompts(out, "acceptance-writer")[1]
    assert "specs passed on base" in retry
    assert retry.index("passed on the unchanged code") < retry.index("specs passed on base")
    assert len(prompts(out, "implementor")) == 1
    assert out.status("t1") == ["running", "done"]
    assert len(out.events("task/t1", "run-started")) == 1
    attempts = [(e["loop"], e["attempt"], e["result"]) for e in out.events("task/t1", "attempt")]
    assert ("writer", 1, "specs-not-red") in attempts and ("writer", 2, "green") in attempts


def test_validation_gets_its_own_context_with_a_run_script_and_the_base_and_the_writers_branch(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    (validation,) = out.state["validation_runs"]
    assert validation["run"].startswith("#!/bin/sh")
    assert validation["cwd"] == ["acceptance-writer", "base"]
    assert validation["context"].endswith("validate-1-1")


def test_validation_runs_while_the_implementor_is_still_running(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 1}]}})

    (validation,) = out.state["validation_runs"]
    implementor = next(s for s in out.state["agent_spans"] if s["role"] == "implementor")
    assert validation["at"] < implementor["end"]


def test_a_writer_fault_is_found_even_when_the_implementor_times_out(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 5}]},
                       "validation": [{"result": "red", "failed_check": "merge", "output": "merge failed"}]},
                      agent_timeout=1)

    assert agent_runs(out).count("acceptance-writer") == 2
    assert agent_runs(out).count("implementor") == 2
    assert "merge failed" in prompts(out, "acceptance-writer")[1]
    assert out.status("t1") == ["running", "done"]


def test_a_crashed_implementor_is_retried_within_the_run(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"exit_status": 1, "output": "impl crashed"}]}})

    assert "impl crashed" in prompts(out, "implementor")[1]
    assert out.status("t1") == ["running", "done"]
    assert len(out.state["integrator_runs"]) == 1


def test_exhausting_the_implementors_attempts_blocks_the_task_naming_the_loop(run_factory):
    crash = {"exit_status": 1, "output": "impl crashed"}
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [crash, crash]}})

    assert out.status("t1") == ["running", "blocked"]
    assert out.state["integrator_runs"] == []
    assert out.main == {"README": "base"}
    (history,) = out.state["status_body"]["t1"][-1]["history"]
    assert history["outcome"]["loop"] == "implementor"
    assert [e["loop"] for e in out.events("task/t1", "loop-exhausted")] == ["implementor"]


def test_exhausting_the_writers_attempts_blocks_the_task_with_no_integration(run_factory):
    red_specs = {"result": "red", "failed_check": "specs-not-red", "output": "passes"}
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "validation": [red_specs, red_specs]})

    assert out.status("t1") == ["running", "blocked"]
    assert out.state["integrator_runs"] == []
    assert agent_runs(out).count("acceptance-writer") == 2
    (history,) = out.state["status_body"]["t1"][-1]["history"]
    assert history["outcome"]["loop"] == "writer"


def test_a_failed_integration_reenters_only_the_implementor_loop_with_a_fresh_budget(run_factory):
    crash = {"exit_status": 1, "output": "impl crashed"}
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [red("suite", "FAIL: greeting is empty")],
                       "agent": {"implementor": [{}, crash, {}]}})

    assert agent_runs(out).count("implementor") == 3
    assert agent_runs(out).count("acceptance-writer") == 1
    assert len(out.state["validation_runs"]) == 1
    assert out.status("t1") == ["running", "running", "done"]
    assert [e["roles"] for e in out.events("task/t1", "run-started")] == [
        ["implementor", "acceptance-writer"], ["implementor"]]
    assert "FAIL: greeting is empty" in prompts(out, "implementor")[1]
    assert "impl crashed" in prompts(out, "implementor")[2]


def test_merge_conflict_is_blamed_on_the_implementor_by_default(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [red("conflict", "CONFLICT in a.txt")]})

    assert agent_runs(out).count("implementor") == 2
    assert "CONFLICT in a.txt" in prompts(out, "implementor")[1]


def test_task_is_blocked_after_two_runs_with_history_and_main_untouched(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [red("suite", "red 1"), red("suite", "red 2"), red("suite", "red 3")]})

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "running", "blocked"]
    assert len(out.state["integrator_runs"]) == 2
    assert out.main == {"README": "base"}
    history = out.state["status_body"]["t1"][-1]["history"]
    assert [h["run"] for h in history] == [1, 2]
    assert [h["outcome"]["failed_check"] for h in history] == ["suite", "suite"]
    assert "red 1" in str(history[0])


def test_feedback_is_truncated_to_the_size_cap(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [red("suite", "A" * 500 + "THE-END")]}, feedback_cap=100)

    retry = prompts(out, "implementor")[1]
    assert "THE-END" in retry
    assert "A" * 101 not in retry


def test_main_moving_between_verdict_and_push_triggers_a_fresh_integrator_run(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "main_moves_after_integrator": [1]})

    assert len(out.state["integrator_runs"]) == 2
    assert out.main["human.txt"] == "pushed by a human"
    assert out.main["implementor.txt"] == "implementor run 1"
    assert out.status("t1") == ["running", "done"]  # still one Run
    assert len(out.state["agent_runs"]) == 2


def test_two_tasks_run_one_after_the_other(run_factory):
    out = run_factory({"tasks": {"t1": "a", "t2": "b"},
                       "events": [TASK_EVENT, {"type": "task", "task": "t2", "repo": "r"}]})

    statuses = [(c["args"]["task"], c["args"]["status"]) for c in out.calls_to("task-store", "set-status")]
    assert statuses == [("t1", "running"), ("t1", "done"), ("t2", "running"), ("t2", "done")]


def test_main_push_is_recorded_and_not_acted_on(run_factory):
    out = run_factory({"events": [{"type": "main-push", "repo": "r", "commit": "abc"}]})

    assert out.exit_code == 0, out.stderr
    assert [e["commit"] for e in out.events("factory", "main-push")] == ["abc"]
    assert out.calls_to("runner") == []
    assert out.calls_to("task-store") == []


def test_adapter_error_blocks_visibly_and_does_not_consume_a_run(run_factory):
    # run calls: run 1 has four (two Agents, validation, Integrator); the fifth is run 2's Implementor
    out = run_factory({"tasks": {"t1": "x"},
                       "events": [TASK_EVENT, TASK_EVENT],
                       "integrator": [red("suite", "red")],
                       "fail": [{"port": "runner", "op": "run", "call": 5}]})

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "running", "blocked", "running", "done"]
    (error,) = out.events("task/t1", "infrastructure-error")
    assert error["runs_used"] == 1
    assert out.state["status_body"]["t1"][2]["reason"] == "infrastructure"


def test_agent_exceeding_the_time_limit_fails_the_run_and_is_retried(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 5}]}}, agent_timeout=1)

    assert agent_runs(out).count("implementor") == 2
    assert agent_runs(out).count("acceptance-writer") == 1
    assert "Timed out" in prompts(out, "implementor")[1]
    assert out.status("t1") == ["running", "done"]


def test_hung_adapter_is_cut_off_and_reported_as_an_infrastructure_error(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 5, "ignore_timeout": True}]}},
                      agent_timeout=1, adapter_grace=1, build_timeout=0)

    assert out.status("t1") == ["running", "blocked"]
    assert len(out.events("task/t1", "infrastructure-error")) == 1


def test_agents_run_in_parallel(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 0.5}], "acceptance-writer": [{"hang": 0.5}]}})

    a, b = out.state["agent_spans"]
    assert a["start"] < b["end"] and b["start"] < a["end"]


def test_both_agents_failing_in_one_run_are_both_retried(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"exit_status": 1, "output": "impl crashed"}],
                                 "acceptance-writer": [{"exit_status": 1, "output": "writer crashed"}]}})

    assert "impl crashed" in prompts(out, "implementor")[1]
    assert "writer crashed" in prompts(out, "acceptance-writer")[1]
    assert out.status("t1") == ["running", "done"]


def test_malformed_verdict_is_an_infrastructure_error(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [{"result": "red"}]})  # red without failed_check

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "blocked"]
    assert out.main == {"README": "base"}


def test_each_agent_context_holds_the_prompt_its_own_skills_and_the_project_on_its_branch(run_factory):
    out = run_factory({"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT]})

    by_role = {r["role"]: r for r in out.state["agent_runs"]}
    assert by_role["implementor"]["skills"] == ["implementor"]
    assert by_role["acceptance-writer"]["skills"] == ["acceptance-writer"]
    assert "add a greeting" in by_role["implementor"]["prompt"]
    assert "Never change the code under" in by_role["acceptance-writer"]["system_prompt"]
    assert "smallest change" in by_role["implementor"]["system_prompt"]
    assert by_role["implementor"]["cwd"] == ["README"]
    assert by_role["implementor"]["context"] != by_role["acceptance-writer"]["context"]


def test_skills_stay_outside_the_working_directory_that_is_recorded(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    assert all("SKILL.md" not in name for r in out.state["agent_runs"] for name in r["cwd"])
    assert not any("SKILL.md" in name for name in out.main)


def test_the_integrator_gets_a_fresh_context_per_attempt_with_a_run_script_and_the_four_inputs(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "main_moves_after_integrator": [1]})

    first, second = out.state["integrator_runs"]
    assert first["context"] != second["context"]
    assert first["run"].startswith("#!/bin/sh")
    assert first["cwd"] == ["acceptance-writer", "base", "implementor", "main"]


def test_the_runner_is_never_told_a_role(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [red("suite", "red")]})

    calls = out.calls_to("runner")
    assert {c["op"] for c in calls} == {"run"}
    assert {c["args"]["type"] for c in calls} == {"agentic", "deterministic"}
    for call in calls:
        rest = {k: v for k, v in call["args"].items() if k != "context"}
        assert "implementor" not in str(rest) and "acceptance-writer" not in str(rest)
        assert call["body"] is None
