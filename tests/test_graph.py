"""The Graph is data the core interprets (spec 0008).

It is checked when the Factory starts, and a second Graph changes how a Task proceeds without a change in the core.
"""

TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}
SCENARIO = {"tasks": {"t1": "add a greeting"}, "events": [TASK_EVENT]}


def test_the_factory_refuses_a_graph_that_does_not_conform_to_the_schema(run_factory, graph_variant):
    def lose_the_attempts(data):
        del data["states"]["run"]["attempts"]

    out = run_factory(SCENARIO, graph=graph_variant(lose_the_attempts))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "states.run" in out.stderr  # where
    assert "attempts" in out.stderr  # what
    assert out.calls == []


def test_the_factory_starts_on_the_shipped_graph(run_factory):
    out = run_factory(SCENARIO)

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "done"]


def test_the_factory_refuses_a_cycle_that_no_attempt_budget_bounds(run_factory, graph_variant):
    def validation_back_to_the_writer(data):
        green = data["states"]["validate"]["transitions"][0]
        assert green["on"] == "green"
        green["to"] = "write"  # write -> validate -> write, and no loop is entered again

    out = run_factory(SCENARIO, graph=graph_variant(validation_back_to_the_writer))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "cycle" in out.stderr
    assert "write" in out.stderr
    assert "validate" in out.stderr
    assert out.calls == []


def test_the_factory_refuses_a_retry_of_something_that_is_not_a_loop(run_factory, graph_variant):
    def crash_retries_the_parallel_state(data):
        crashed = next(t for t in data["states"]["implement"]["transitions"] if t["on"] == "crashed")
        crashed["to"] = "work"  # `work` encloses `implement`, but it has no attempts to spend

    out = run_factory(SCENARIO, graph=graph_variant(crash_retries_the_parallel_state))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "implement" in out.stderr  # where
    assert "work" in out.stderr  # what it goes to
    assert "not a loop" in out.stderr
    assert out.calls == []


def test_the_factory_refuses_a_state_no_transition_reaches(run_factory, graph_variant):
    def add_an_orphan(data):
        data["states"]["orphan"] = {"type": "status", "status": "blocked", "reason": "nobody gets here"}

    out = run_factory(SCENARIO, graph=graph_variant(add_an_orphan))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "orphan" in out.stderr
    assert "no transition reaches" in out.stderr
    assert out.calls == []


def test_the_factory_refuses_an_outcome_that_has_no_transition(run_factory, graph_variant):
    def forget_the_failed_suite(data):
        transitions = data["states"]["integrate"]["transitions"]
        transitions[:] = [t for t in transitions if t["on"] != "red:suite"]

    out = run_factory(SCENARIO, graph=graph_variant(forget_the_failed_suite))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "integrate" in out.stderr  # where
    assert "red:suite" in out.stderr  # which outcome
    assert out.calls == []


def test_the_factory_refuses_a_path_into_done_that_does_not_come_from_publish(run_factory, graph_variant):
    def a_failed_suite_is_done(data):
        failed = next(t for t in data["states"]["integrate"]["transitions"] if t["on"] == "red:suite")
        failed["to"] = "done"
        failed.pop("feedback")
        failed.pop("reset")

    out = run_factory(SCENARIO, graph=graph_variant(a_failed_suite_is_done))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "integrate" in out.stderr  # where
    assert "done" in out.stderr
    assert "publish" in out.stderr  # who may
    assert out.calls == []
