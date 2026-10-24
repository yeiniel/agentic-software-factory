"""The Factory as a black-box process: each scenario's assertion is its golden transcript (tests/goldens)."""

import pytest


TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}
OTHER_TASK_EVENT = {"type": "task", "task": "t2", "repo": "r"}
OTHER_REPO_EVENT = {"type": "task", "task": "t2", "repo": "s"}
THIRD_REPO_EVENT = {"type": "task", "task": "t3", "repo": "u"}
SLOW = {"implementor": [{"hang": 0.4}] * 3, "acceptance-writer": [{"hang": 0.4}] * 3}
IMPLEMENTOR_CRASH = {"exit_status": 1, "output": "impl crashed"}
SPECS_PASS = {"result": "red", "failed_check": "specs-not-red", "output": "specs passed on base"}


def red(check, output):
    return {"result": "red", "failed_check": check, "output": output}


def test_a_green_first_run_advances_main_and_marks_the_task_done(run_factory, golden_transcript):
    out = run_factory({"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_implementor_failure_retriggers_only_the_implementor_with_feedback(run_factory, golden_transcript):
    out = run_factory(
        {
            "tasks": {"t1": "add a greeting"},
            "events": [TASK_EVENT],
            "integrator": [red("suite-failed", "FAIL: greeting is empty")],
        }
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_specs_not_red_on_base_retry_the_writer_with_the_reason_first(run_factory, golden_transcript):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "validation": [SPECS_PASS]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_validation_runs_while_the_implementor_is_still_running(run_factory):
    # the hang outlasts the Writer, its recording and the validation's assembly even when every Adapter call is slow
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [{"hang": 5}]}})

    (validation,) = out.state["validation_runs"]
    implementor = next(s for s in out.state["agent_spans"] if s["role"] == "implementor")
    assert validation["at"] < implementor["end"]


def test_a_writer_fault_is_found_even_when_the_implementor_times_out(run_factory, golden_transcript):
    out = run_factory(
        {
            "tasks": {"t1": "x"},
            "events": [TASK_EVENT],
            "agent": {"implementor": [{"hang": 5}]},
            "validation": [red("merge-failed", "merge failed")],
        },
        agent_timeout=1,
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_crashed_implementor_is_retried_within_the_run(run_factory, golden_transcript):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [IMPLEMENTOR_CRASH]}})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_exhausting_the_implementors_attempts_blocks_the_task_naming_the_loop(run_factory, golden_transcript):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [IMPLEMENTOR_CRASH, IMPLEMENTOR_CRASH]}}
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_exhausting_the_writers_attempts_blocks_the_task_with_no_integration(run_factory, golden_transcript):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "validation": [SPECS_PASS, SPECS_PASS]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_failed_integration_reenters_only_the_implementor_loop_with_a_fresh_budget(run_factory, golden_transcript):
    out = run_factory(
        {
            "tasks": {"t1": "x"},
            "events": [TASK_EVENT],
            "integrator": [red("suite-failed", "FAIL: greeting is empty")],
            "agent": {"implementor": [{}, IMPLEMENTOR_CRASH, {}]},
        }
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_merge_conflict_is_blamed_on_the_implementor_by_default(run_factory, golden_transcript):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [red("merge-conflict", "CONFLICT in a.txt")]}
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_task_is_blocked_after_two_runs_with_its_history_and_main_untouched(run_factory, golden_transcript):
    out = run_factory(
        {
            "tasks": {"t1": "x"},
            "events": [TASK_EVENT],
            "integrator": [red("suite-failed", "red 1"), red("suite-failed", "red 2"), red("suite-failed", "red 3")],
        }
    )

    assert out.exit_code == 0, out.stderr
    assert out.main == {"README": "base"}
    golden_transcript(out)


def test_feedback_is_truncated_to_the_size_cap(run_factory, golden_transcript):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [red("suite-failed", "A" * 500 + "THE-END")]},
        feedback_cap=100,
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_main_moving_between_verdict_and_push_blocks_the_task_with_reason_main_moved(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "main_moves_after_integrator": [1]})

    assert out.exit_code == 0, out.stderr
    assert out.main["human.txt"] == "pushed by a human"
    assert out.status("t1") == ["running", "blocked"]
    assert out.events("task/t1", "task-status")[-1]["reason"] == "main-moved"
    assert len(out.calls_to("runner", "run")) == 4  # two Agents, validation and one Integrator run


def test_two_tasks_run_one_after_the_other(run_factory, golden_transcript):
    out = run_factory({"tasks": {"t1": "a", "t2": "b"}, "events": [TASK_EVENT, OTHER_TASK_EVENT]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def spans_of(out, task):
    """The (start, end) of each Agent attempt of `task`; the Context path names the Task."""
    return [(s["start"], s["end"]) for s in out.state["agent_spans"] if f"/{task}/" in s["context"]]


def overlap(a, b):
    return any(x[0] < y[1] and y[0] < x[1] for x in a for y in b)


def test_tasks_on_different_repos_run_together_up_to_task_concurrency(run_factory):
    out = run_factory(
        {"tasks": {"t1": "a", "t2": "b"}, "events": [TASK_EVENT, OTHER_REPO_EVENT], "agent": SLOW},
        task_concurrency=2,
    )

    assert out.exit_code == 0, out.stderr
    assert overlap(spans_of(out, "t1"), spans_of(out, "t2"))
    assert out.status("t1") == ["running", "done"] and out.status("t2") == ["running", "done"]


def test_tasks_of_one_repo_never_run_together_whatever_the_limit(run_factory):
    out = run_factory(
        {"tasks": {"t1": "a", "t2": "b"}, "events": [TASK_EVENT, OTHER_TASK_EVENT], "agent": SLOW},
        task_concurrency=2,
    )

    assert out.exit_code == 0, out.stderr
    assert not overlap(spans_of(out, "t1"), spans_of(out, "t2"))
    assert out.status("t2") == ["running", "done"]  # started from the main the first left, so no `main-moved`


def test_a_task_on_a_busy_repo_does_not_hold_up_the_ones_behind_it(run_factory):
    out = run_factory(
        {
            "tasks": {"t1": "a", "t2": "b", "t3": "c"},
            "events": [TASK_EVENT, OTHER_TASK_EVENT, OTHER_REPO_EVENT | {"task": "t3"}],
            "agent": SLOW,
        },
        task_concurrency=2,
    )

    assert out.exit_code == 0, out.stderr
    assert overlap(spans_of(out, "t1"), spans_of(out, "t3"))  # t2 waits for t1, t3 does not
    assert not overlap(spans_of(out, "t1"), spans_of(out, "t2"))


def test_queued_tasks_are_recorded_todo_in_order_before_the_first_run_finishes(run_factory):
    out = run_factory(
        {
            "tasks": {"t1": "a", "t2": "b", "t3": "c"},
            "events": [TASK_EVENT, OTHER_REPO_EVENT, THIRD_REPO_EVENT],
            "agent": SLOW,
        }
    )

    assert out.exit_code == 0, out.stderr
    kinds = [(r["stream"], r["event"]["kind"], r["event"].get("status")) for r in out.records]
    receipts = [k[0] for k in kinds if k[1] == "task-received"]
    assert receipts == ["task/t1", "task/t2", "task/t3"]
    first_finish = next(i for i, k in enumerate(kinds) if k[1] == "run-finished")
    assert all(("task/" + t, "task-status", "todo") in kinds[:first_finish] for t in ("t1", "t2", "t3"))
    for task in ("t2", "t3"):  # recorded todo, started only on its turn
        stream = [k for k in kinds if k[0] == f"task/{task}"]
        assert [k[1] for k in stream[:3]] == ["task-received", "task-status", "task-status"]
        assert [k[2] for k in stream[1:3]] == ["todo", "running"]


def test_a_task_behind_a_busy_repository_is_recorded_todo_on_receipt(run_factory):
    out = run_factory(
        {"tasks": {"t1": "a", "t2": "b"}, "events": [TASK_EVENT, OTHER_TASK_EVENT], "agent": SLOW},
        task_concurrency=2,
    )

    kinds = [(r["stream"], r["event"]["kind"], r["event"].get("status")) for r in out.records]
    first_finish = next(i for i, k in enumerate(kinds) if k[1] == "run-finished")
    assert ("task/t2", "task-status", "todo") in kinds[:first_finish]


def test_no_more_tasks_run_at_once_than_task_concurrency(run_factory):
    out = run_factory(
        {
            "tasks": {"t1": "a", "t2": "b", "t3": "c"},
            "events": [TASK_EVENT, OTHER_REPO_EVENT, THIRD_REPO_EVENT],
            "agent": SLOW,
        },
        task_concurrency=2,
    )

    assert out.exit_code == 0, out.stderr
    assert all(out.status(t) == ["running", "done"] for t in ("t1", "t2", "t3"))
    starts = sorted(min(s for s, _ in spans_of(out, t)) for t in ("t1", "t2", "t3"))
    first_end = min(max(e for _, e in spans_of(out, t)) for t in ("t1", "t2", "t3"))
    assert starts[2] >= first_end  # the third began only after one of the others finished


def test_tasks_run_one_at_a_time_by_default_even_on_different_repos(run_factory):
    out = run_factory({"tasks": {"t1": "a", "t2": "b"}, "events": [TASK_EVENT, OTHER_REPO_EVENT], "agent": SLOW})

    assert out.exit_code == 0, out.stderr
    assert not overlap(spans_of(out, "t1"), spans_of(out, "t2"))


@pytest.mark.parametrize("value", [0, -1, 1.5, "2", True])
def test_a_task_concurrency_that_is_not_a_positive_whole_number_stops_the_factory_at_start(run_factory, value):
    out = run_factory({}, task_concurrency=value)

    assert out.exit_code != 0
    assert "task_concurrency" in out.stderr


def test_a_main_push_is_recorded_and_not_acted_on(run_factory, golden_transcript):
    out = run_factory({"events": [{"type": "main-push", "repo": "r", "commit": "abc"}]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_adapter_error_blocks_visibly_and_does_not_consume_a_run(run_factory, golden_transcript):
    # run calls: run 1 has four (two Agents, validation, Integrator); the fifth is run 2's Implementor
    out = run_factory(
        {
            "tasks": {"t1": "x"},
            "events": [TASK_EVENT, TASK_EVENT],
            "integrator": [red("suite-failed", "red")],
            "fail": [{"port": "runner", "op": "run", "call": 5}],
        }
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_agent_exceeding_the_time_limit_fails_the_run_and_is_retried(run_factory, golden_transcript):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [{"hang": 5}]}}, agent_timeout=1
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_hung_adapter_is_cut_off_and_reported_as_an_infrastructure_error(run_factory, golden_transcript):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [{"hang": 5, "ignore_timeout": True}]}},
        agent_timeout=1,
        adapter_grace=1,
        build_timeout=0,
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_the_two_agents_run_in_parallel(run_factory):
    out = run_factory(
        {
            "tasks": {"t1": "x"},
            "events": [TASK_EVENT],
            "agent": {"implementor": [{"hang": 0.5}], "acceptance-writer": [{"hang": 0.5}]},
        }
    )

    a, b = out.state["agent_spans"]
    assert a["start"] < b["end"] and b["start"] < a["end"]


def test_both_agents_failing_in_one_run_are_both_retried(run_factory, golden_transcript):
    out = run_factory(
        {
            "tasks": {"t1": "x"},
            "events": [TASK_EVENT],
            "agent": {
                "implementor": [IMPLEMENTOR_CRASH],
                "acceptance-writer": [{"exit_status": 1, "output": "writer crashed"}],
            },
        }
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_malformed_verdict_is_an_infrastructure_error(run_factory, golden_transcript):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [{"result": "red"}]}
    )  # red without failed_check

    assert out.exit_code == 0, out.stderr
    assert out.main == {"README": "base"}
    golden_transcript(out)


def test_a_green_verdict_carries_the_acceptance_report_into_the_run_record(run_factory, golden_transcript):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [{"output": "42 specs green"}]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


@pytest.mark.parametrize("check", ["merge-conflict", "suite-failed"])
def test_a_red_integration_verdict_names_the_failed_check(run_factory, golden_transcript, check):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [red(check, "out")]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


@pytest.mark.parametrize("check", ["specs-not-red", "merge-failed"])
def test_a_red_validation_verdict_names_the_failed_check(run_factory, golden_transcript, check):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "validation": [red(check, "out")]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


@pytest.mark.parametrize(
    "integrator",
    [
        {"result": "red", "failed_check": "specs-not-red", "output": "x"},  # a check of the validation process
        {"result": "red", "failed_check": "vibes", "output": "x"},
        {"result": "maybe", "output": "x"},
        {"result": "green", "no_output": True},
    ],
    ids=["other-process-check", "unknown-check", "unknown-result", "no-output"],
)
def test_a_malformed_integration_verdict_is_an_infrastructure_error(run_factory, golden_transcript, integrator):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "integrator": [integrator]})

    assert out.exit_code == 0, out.stderr
    assert out.main == {"README": "base"}
    golden_transcript(out)


@pytest.mark.parametrize(
    "validation",
    [
        {"result": "red", "failed_check": "suite-failed", "output": "x"},  # a check of the integration process
        {"result": "maybe", "output": "x"},
        {"result": "green", "no_output": True},
    ],
    ids=["other-process-check", "unknown-result", "no-output"],
)
def test_a_malformed_validation_verdict_is_an_infrastructure_error(run_factory, golden_transcript, validation):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "validation": [validation]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)
