"""The Tasks already run, each with the end state the default Graph must give it (spec 0008).

The scripted Agents and verdicts reproduce what happened in each real Task; when a change to the Graph makes one of
these end differently, the baseline is what to look at before the change is trusted.
"""

TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}
SPECS_PASS = {"result": "red", "failed_check": "specs-not-red", "output": "specs passed on base"}


def test_pydantic_extra_types_326_is_done_in_one_run(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    assert out.status("t1") == ["running", "done"]
    assert len(out.events("task/t1", "run-started")) == 1


def test_unjs_ufo_379_is_done_in_one_run_after_the_writers_first_specs_are_rejected(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "validation": [SPECS_PASS]})

    assert out.status("t1") == ["running", "done"]
    assert len(out.events("task/t1", "run-started")) == 1
    assert [r["role"] for r in out.state["agent_runs"]].count("acceptance-writer") == 2
    writer = [e["result"] for e in out.events("task/t1", "attempt") if e["loop"] == "writer"]
    assert writer == ["specs-not-red", "green"]


def test_tailwind_merge_is_blocked_on_the_implementor_loop_when_both_attempts_time_out(run_factory):
    out = run_factory(
        {"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [{"hang": 5}, {"hang": 5}]}},
        agent_timeout=1,
    )

    assert out.status("t1") == ["running", "blocked"]
    assert out.events("task/t1", "task-status")[-1]["reason"] == "loop-exhausted"
    (run,) = out.state["status_body"]["t1"][-1]["history"]
    assert run["outcome"]["loop"] == "implementor"
    assert [a["result"] for a in run["attempts"]["implementor"]] == ["timed-out", "timed-out"]
