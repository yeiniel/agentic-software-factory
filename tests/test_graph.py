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
