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
    return [c["args"]["role"] for c in out.calls_to("runner", "run-agent")]


def prompts(out, role):
    return [c["body"]["prompt"] for c in out.calls_to("runner", "provision-context")
            if c["args"]["kind"] == role]


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
    # the retried Agent resumes its session, on its own branch; the other branch is never named
    retry_ctx = [c for c in out.calls_to("runner", "provision-context")
                 if c["args"]["kind"] == "implementor" and c["args"]["run"] == "2"][0]
    assert retry_ctx["body"]["resume"] is True
    assert all("acceptance-writer" not in p for p in prompts(out, "implementor"))
    assert out.main["implementor.txt"] == "implementor run 2"
    assert out.main["acceptance-writer.txt"] == "acceptance-writer run 1"
    assert out.status("t1") == ["running", "running", "done"]
    assert [e["run"] for r in out.records for e in [r["event"]] if e["kind"] == "run-started"] == [1, 2]


def test_specs_not_red_on_base_are_blamed_on_the_acceptance_writer(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [red("specs-not-red", "integrator output",
                                          spec_output="specs passed on base")]})

    assert sorted(agent_runs(out)) == ["acceptance-writer", "acceptance-writer", "implementor"]
    assert "specs passed on base" in prompts(out, "acceptance-writer")[1]
    assert out.status("t1") == ["running", "running", "done"]


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
    assert len(out.calls_to("runner", "run-integrator")) == 2
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


def test_implementor_failing_twice_on_the_same_output_also_retriggers_the_writer(run_factory):
    same = red("suite", "same failure", spec_output="WRITER-OWN-OUTPUT")
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [same, same]},
                      max_runs=3)

    third_writer = prompts(out, "acceptance-writer")[1]
    assert "WRITER-OWN-OUTPUT" in third_writer
    assert "same failure" not in third_writer  # never the Implementor's side
    assert len(prompts(out, "implementor")) == 3
    assert len(prompts(out, "acceptance-writer")) == 2


def test_main_moving_between_verdict_and_push_triggers_a_fresh_integrator_run(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "main_moves_after_integrator": [1]})

    assert len(out.calls_to("runner", "run-integrator")) == 2
    assert out.main["human.txt"] == "pushed by a human"
    assert out.main["implementor.txt"] == "implementor run 1"
    assert out.status("t1") == ["running", "done"]  # still one Run
    assert len(out.calls_to("runner", "run-agent")) == 2


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
    # build calls: run 1 has three (two Agents, Integrator); the fourth is run 2's Implementor
    out = run_factory({"tasks": {"t1": "x"},
                       "events": [TASK_EVENT, TASK_EVENT],
                       "integrator": [red("suite", "red")],
                       "fail": [{"port": "environment-builder", "op": "build", "call": 4}]})

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
    assert out.status("t1") == ["running", "running", "done"]


def test_hung_adapter_is_cut_off_and_reported_as_an_infrastructure_error(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 5, "ignore_timeout": True}]}},
                      agent_timeout=1, adapter_grace=1)

    assert out.status("t1") == ["running", "blocked"]
    assert len(out.events("task/t1", "infrastructure-error")) == 1


def test_agents_run_in_parallel(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"hang": 0.5}], "acceptance-writer": [{"hang": 0.5}]}})

    a, b = out.state["agent_spans"]
    assert a["start"] < b["end"] and b["start"] < a["end"]


def test_both_agents_failing_in_one_run_are_both_retriggered(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "agent": {"implementor": [{"exit_status": 1, "output": "impl crashed"}],
                                 "acceptance-writer": [{"exit_status": 1, "output": "writer crashed"}]}})

    assert "impl crashed" in prompts(out, "implementor")[1]
    assert "writer crashed" in prompts(out, "acceptance-writer")[1]
    assert out.status("t1") == ["running", "running", "done"]


def test_malformed_verdict_is_an_infrastructure_error(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT],
                       "integrator": [{"result": "red"}]})  # red without failed_check

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "blocked"]
    assert out.main == {"README": "base"}
