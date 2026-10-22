"""The Graph is data the core interprets (spec 0008).

It is checked when the Factory starts, and a second Graph changes how a Task proceeds without a change in the core.
"""

import pytest

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


def test_the_factory_refuses_a_name_that_resolves_to_no_file_in_the_folder(run_factory, graph_variant):
    def a_role_without_instruction(data):
        data["states"]["implement"]["instruction"] = "roles/nobody/instruction.md"

    out = run_factory(SCENARIO, graph=graph_variant(a_role_without_instruction))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "implement" in out.stderr  # where
    assert "roles/nobody/instruction.md" in out.stderr  # what
    assert out.calls == []


def test_the_factory_refuses_a_feedback_message_with_a_placeholder_other_than_check_and_output(
    run_factory, graph_variant
):
    out = run_factory(SCENARIO, graph=graph_variant(files={"feedback/suite.md": "The {diff} failed.\n\n{output}\n"}))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "feedback/suite.md" in out.stderr  # where
    assert "{diff}" in out.stderr  # what
    assert out.calls == []


def test_the_factory_refuses_an_input_that_is_the_branch_of_nothing(run_factory, graph_variant):
    def validate_the_branch_of_nobody(data):
        data["states"]["validate"]["inputs"]["acceptance-writer"] = {"branch-of": "nobody"}

    out = run_factory(SCENARIO, graph=graph_variant(validate_the_branch_of_nobody))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "validate" in out.stderr  # where
    assert "nobody" in out.stderr  # what
    assert out.calls == []


@pytest.mark.parametrize(("state", "key"), [("implement", "workspace"), ("publish", "branch")])
def test_the_factory_refuses_a_workspace_or_a_publish_of_a_branch_nothing_makes(run_factory, graph_variant, state, key):
    def read_nobody(data):
        data["states"][state][key] = {"branch-of": "nobody"} if key == "workspace" else "nobody"

    out = run_factory(SCENARIO, graph=graph_variant(read_nobody))

    assert out.exit_code == 1
    assert state in out.stderr  # where
    assert "nobody" in out.stderr  # what
    assert out.calls == []


def test_a_state_can_leave_its_loop_for_a_status_instead_of_retrying(run_factory, graph_variant):
    def an_unmergeable_branch_blocks_the_task(data):
        merge = next(t for t in data["states"]["validate"]["transitions"] if t["on"] == "red:merge")
        merge["to"] = "blocked-loop-exhausted"
        merge.pop("feedback")

    out = run_factory(
        {**SCENARIO, "validation": [{"result": "red", "failed_check": "merge", "output": "no merge"}]},
        graph=graph_variant(an_unmergeable_branch_blocks_the_task),
    )

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "blocked"]
    assert out.events("task/t1", "task-status")[-1]["reason"] == "loop-exhausted"
    assert [r["role"] for r in out.state["agent_runs"]].count("acceptance-writer") == 1  # not retried
    (run,) = out.state["status_body"]["t1"][-1]["history"]
    assert run["outcome"]["failed_check"] == "merge"
    assert run["outcome"]["output"] == "no merge"


def test_a_retry_without_a_feedback_message_starts_the_role_with_no_feedback(run_factory, graph_variant):
    def retries_say_nothing(data):
        for state, trigger in (("implement", "crashed"), ("integrate", "red:suite")):
            next(t for t in data["states"][state]["transitions"] if t["on"] == trigger).pop("feedback")

    out = run_factory(
        {
            **SCENARIO,
            "agent": {"implementor": [{"exit_status": 1, "output": "crashed"}]},
            "integrator": [{"result": "red", "failed_check": "suite", "output": "FAIL"}],
        },
        graph=graph_variant(retries_say_nothing),
    )

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "running", "done"], out.events("task/t1", "infrastructure-error")
    prompts = [r["prompt"] for r in out.state["agent_runs"] if r["role"] == "implementor"]
    assert len(prompts) == 3  # the crash, the retry in the same Run, and the Implementor again in the second Run
    assert not any("Feedback" in prompt for prompt in prompts)
    assert out.events("task/t1", "loop-feedback") == []
    assert out.events("task/t1", "feedback") == []


@pytest.mark.parametrize(("session", "resumed"), [("resume", [False, True]), ("fresh", [False, False])])
def test_a_retry_resumes_the_pi_session_only_when_the_graph_says_so(run_factory, graph_variant, session, resumed):
    def set_session(data):
        data["states"]["implement"]["session"] = session

    out = run_factory(
        {**SCENARIO, "agent": {"implementor": [{"exit_status": 1, "output": "crashed"}]}},
        graph=graph_variant(set_session),
    )

    assert [r["resumed"] for r in out.state["agent_runs"] if r["role"] == "implementor"] == resumed


def add_a_reviewer(data):
    """A Reviewer works on the integrated branch after integration and before `main` moves."""
    states = data["states"]
    states["review"] = {
        "type": "agentic",
        "role": "reviewer",
        "instruction": "roles/reviewer/instruction.md",
        "system-prompt": "roles/reviewer/system-prompt.md",
        "skills": "roles/reviewer/skills",
        "prompt": ["instruction", "task", "feedback"],
        "workspace": {"branch-of": "integrated"},
        "timeout": "agent_timeout",
        "session": "fresh",
        "output": {"branch": "reviewed"},
        "transitions": [
            {"on": "green", "to": "publish"},
            {"on": "crashed", "to": "blocked-review"},
            {"on": "timed-out", "to": "blocked-review"},
        ],
    }
    states["blocked-review"] = {"type": "status", "status": "blocked", "reason": "review-failed"}
    states["integrate"]["transitions"][0]["to"] = "review"
    states["run"]["contains"] = ["work", "integrate", "review", "publish"]


REVIEWER = {
    "roles/reviewer/instruction.md": "Review the change.",
    "roles/reviewer/system-prompt.md": "You are a reviewer.",
    "roles/reviewer/skills/reviewer/SKILL.md": "# Reviewer",
}


def test_a_third_agentic_role_is_added_by_a_prompt_folder_and_the_graph_alone(run_factory, graph_variant):
    out = run_factory(SCENARIO, graph=graph_variant(add_a_reviewer, REVIEWER))

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "done"], out.events("task/t1", "infrastructure-error")
    (review,) = [r for r in out.state["agent_runs"] if r["role"] == "reviewer"]
    assert review["prompt"].startswith("Review the change.")
    assert review["system_prompt"] == "You are a reviewer."
    assert review["skills"] == ["reviewer"]
    assert {"implementor.txt", "acceptance-writer.txt"} <= set(review["cwd"])  # it works on the integrated branch
    assert out.events("task/t1", "run-started")[0]["roles"] == ["implementor", "acceptance-writer", "reviewer"]


def test_a_reviewer_that_crashes_blocks_the_task_with_the_reason_the_graph_gives(run_factory, graph_variant):
    out = run_factory(
        {**SCENARIO, "agent": {"reviewer": [{"exit_status": 1, "output": "crashed"}]}},
        graph=graph_variant(add_a_reviewer, REVIEWER),
    )

    assert out.status("t1") == ["running", "blocked"]
    assert out.events("task/t1", "task-status")[-1]["reason"] == "review-failed", out.events(
        "task/t1", "infrastructure-error"
    )
    assert out.main == {"README": "base"}


def test_the_version_of_the_graph_is_pinned_in_the_task_received_record(run_factory):
    out = run_factory(SCENARIO, graph_version="9f3c2e1")

    (received,) = out.events("task/t1", "task-received")
    assert received["graph"] == "9f3c2e1"


def test_a_graph_without_a_version_is_unversioned(run_factory):
    out = run_factory(SCENARIO)

    (received,) = out.events("task/t1", "task-received")
    assert received["graph"] == "unversioned"


def test_placeholders_in_a_feedback_message_are_filled_with_the_check_and_the_raw_output(run_factory, graph_variant):
    folder = graph_variant(files={"feedback/suite.md": "[{check}] failed:\n{output}"})

    out = run_factory(
        {**SCENARIO, "integrator": [{"result": "red", "failed_check": "suite", "output": "FAIL x"}]}, graph=folder
    )

    first, second = [r["prompt"] for r in out.state["agent_runs"] if r["role"] == "implementor"]
    assert "Feedback" not in first
    assert "[suite] failed:\nFAIL x" in second


def test_the_factory_refuses_a_transition_to_a_state_that_does_not_exist(run_factory, graph_variant):
    def crash_goes_nowhere(data):
        crashed = next(t for t in data["states"]["implement"]["transitions"] if t["on"] == "crashed")
        crashed["to"] = "nowhere"

    out = run_factory(SCENARIO, graph=graph_variant(crash_goes_nowhere))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "implement" in out.stderr  # where
    assert "nowhere" in out.stderr  # what
    assert out.calls == []


def rename(*path, to):
    def apply(data):
        node = data
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = to

    return apply


@pytest.mark.parametrize(
    ("change", "named"),
    [
        (rename("start", to="nowhere"), "nowhere"),
        (rename("error", to="nowhere"), "nowhere"),
        (rename("states", "run", "entry", to="nowhere"), "run"),
        (rename("states", "run", "contains", to=["work", "nowhere"]), "run"),
        (rename("states", "work", "regions", to=["implementor", "nowhere"]), "work"),
    ],
    ids=["start", "error", "entry", "contains", "regions"],
)
def test_the_factory_refuses_a_name_that_is_not_a_state(run_factory, graph_variant, change, named):
    out = run_factory(SCENARIO, graph=graph_variant(change))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert named in out.stderr
    assert "nowhere" in out.stderr
    assert out.calls == []


def test_the_factory_refuses_a_feedback_for_a_role_the_graph_does_not_run(run_factory, graph_variant):
    def feedback_for_the_reviewer(data):
        crashed = next(t for t in data["states"]["implement"]["transitions"] if t["on"] == "crashed")
        crashed["feedback"]["for"] = "reviewer"

    out = run_factory(SCENARIO, graph=graph_variant(feedback_for_the_reviewer))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "implement" in out.stderr  # where
    assert "reviewer" in out.stderr  # what
    assert out.calls == []


def test_the_factory_refuses_a_reset_of_something_that_is_not_a_loop(run_factory, graph_variant):
    def reset_the_agent(data):
        failed = next(t for t in data["states"]["integrate"]["transitions"] if t["on"] == "red:suite")
        failed["reset"] = ["implement"]  # an Activity, not a loop

    out = run_factory(SCENARIO, graph=graph_variant(reset_the_agent))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "integrate" in out.stderr  # where
    assert "implement" in out.stderr  # what
    assert "not a loop" in out.stderr
    assert out.calls == []


def test_the_factory_refuses_a_reset_of_a_state_that_does_not_exist(run_factory, graph_variant):
    def reset_nothing(data):
        failed = next(t for t in data["states"]["integrate"]["transitions"] if t["on"] == "red:suite")
        failed["reset"] = ["nowhere"]

    out = run_factory(SCENARIO, graph=graph_variant(reset_nothing))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "nowhere" in out.stderr
    assert "Traceback" not in out.stderr
    assert out.calls == []


def test_the_factory_refuses_an_environment_that_is_not_one_of_the_inputs(run_factory, graph_variant):
    def environment_of_nothing(data):
        data["states"]["validate"]["environment"] = "main"

    out = run_factory(SCENARIO, graph=graph_variant(environment_of_nothing))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "validate" in out.stderr  # where
    assert "main" in out.stderr  # what
    assert out.calls == []


def test_the_factory_refuses_a_timeout_that_names_no_config_key(run_factory, graph_variant):
    def a_timeout_nobody_configured(data):
        data["states"]["implement"]["timeout"] = "implementor_timeout"

    out = run_factory(SCENARIO, graph=graph_variant(a_timeout_nobody_configured))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "implement" in out.stderr  # where
    assert "implementor_timeout" in out.stderr  # what
    assert out.calls == []


def test_the_factory_refuses_a_start_loop_that_can_exit(run_factory, graph_variant):
    def integration_timeout_exits(data):
        timed_out = next(t for t in data["states"]["integrate"]["transitions"] if t["on"] == "timed-out")
        timed_out["to"] = "$exit"  # nothing would say what a finished start loop means
        timed_out.pop("reset")
        timed_out.pop("feedback")

    out = run_factory(SCENARIO, graph=graph_variant(integration_timeout_exits))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "integrate" in out.stderr  # where
    assert "$exit" in out.stderr
    assert out.calls == []


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data["states"]["run"].pop("runs"),
        lambda data: data["states"]["writer"].update(runs=True),
    ],
    ids=["start-without-runs", "another-loop-with-runs"],
)
def test_the_factory_refuses_a_graph_where_the_runs_are_not_the_start_loops_attempts(
    run_factory, graph_variant, change
):
    out = run_factory(SCENARIO, graph=graph_variant(change))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "runs" in out.stderr
    assert out.calls == []


def test_the_factory_refuses_a_loop_that_sits_directly_in_another_loop(run_factory, graph_variant):
    def writer_beside_the_work(data):
        data["states"]["work"]["regions"] = ["implementor"]
        data["states"]["run"]["contains"] = ["work", "writer", "integrate", "publish"]

    out = run_factory(SCENARIO, graph=graph_variant(writer_beside_the_work))

    assert out.exit_code == 1
    assert "factory: invalid Graph" in out.stderr
    assert "writer" in out.stderr  # what
    assert "parallel" in out.stderr  # where it should be
    assert out.calls == []


def test_a_timeout_in_the_graph_is_a_number_of_seconds_or_the_name_of_a_config_key(run_factory, graph_variant):
    def seven_seconds(data):
        data["states"]["implement"]["timeout"] = 7

    out = run_factory(SCENARIO, graph=graph_variant(seven_seconds), agent_timeout=11)

    agentic = {c["args"]["context"].rsplit("/", 1)[1]: c["args"]["timeout"] for c in out.calls_to("runner", "run")}
    assert agentic["implementor"] == "7"  # the number in the Graph
    assert agentic["acceptance-writer"] == "11"  # the config key the Graph names
