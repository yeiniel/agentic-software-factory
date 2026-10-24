"""An Adapter that misbehaves is an infrastructure error: the Task blocks visibly and the Factory carries on."""

TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}
SCENARIO = {"tasks": {"t1": "x"}, "events": [TASK_EVENT]}


def test_an_adapter_that_cannot_be_started_blocks_the_task(run_factory, golden_transcript):
    out = run_factory(SCENARIO, adapters={"repo-host": ["/nonexistent/repo-host"]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_adapter_that_exceeds_its_deadline_blocks_the_task(run_factory, golden_transcript):
    out = run_factory(
        {**SCENARIO, "fail": [{"port": "repo-host", "op": "main-head", "call": 1, "sleep": 5}]}, adapter_timeout=1
    )

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_adapter_that_exits_non_zero_blocks_the_task(run_factory, golden_transcript):
    out = run_factory({**SCENARIO, "fail": [{"port": "repo-host", "op": "main-head", "call": 1}]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_adapter_that_prints_invalid_json_blocks_the_task(run_factory, golden_transcript):
    out = run_factory({**SCENARIO, "fail": [{"port": "repo-host", "op": "main-head", "call": 1, "stdout": "{oops"}]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_infrastructure_error_that_cannot_be_reported_is_said_on_stderr(run_factory, golden_transcript):
    out = run_factory(
        {
            **SCENARIO,
            "fail": [
                {"port": "repo-host", "op": "main-head", "call": 1},
                {"port": "task-store", "op": "set-status", "call": 1},
            ],
        }
    )

    assert out.exit_code == 0
    assert "could not report infrastructure error for t1" in out.stderr
    golden_transcript(out)


def test_a_streaming_event_source_that_prints_invalid_json_stops_the_factory_and_is_stopped(run_factory):
    out = run_factory({"events": [{"raw": "{oops"}, {"sleep": 30}]}, timeout=20)

    assert out.exit_code != 0
    assert "invalid JSON line" in out.stderr


def test_blank_lines_from_the_event_source_are_ignored(run_factory, golden_transcript):
    out = run_factory({**SCENARIO, "events": [{"raw": ""}, {"raw": "  "}, TASK_EVENT]})

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "done"]
    golden_transcript(out)


def test_an_event_source_that_exits_non_zero_stops_the_factory(run_factory):
    out = run_factory({"events": [{"exit": 3}]})

    assert out.exit_code != 0
    assert "exited 3" in out.stderr


def test_an_event_of_an_unknown_type_is_ignored(run_factory, golden_transcript):
    out = run_factory({**SCENARIO, "events": [{"type": "weather", "repo": "r"}, TASK_EVENT]})

    assert out.exit_code == 0, out.stderr
    assert out.status("t1") == ["running", "done"]
    golden_transcript(out)


def test_a_main_push_that_cannot_be_recorded_is_said_on_stderr_and_serving_continues(run_factory):
    push = {"type": "main-push", "repo": "r", "commit": "abc"}
    out = run_factory(
        {**SCENARIO, "events": [push, TASK_EVENT], "fail": [{"port": "records", "op": "append", "call": 1}]}
    )

    assert out.exit_code == 0
    assert "could not record main push" in out.stderr
    assert out.status("t1") == ["running", "done"]


def test_a_receipt_that_cannot_be_recorded_is_said_on_stderr_and_the_task_still_runs(run_factory):
    out = run_factory({**SCENARIO, "events": [TASK_EVENT], "fail": [{"port": "records", "op": "append", "call": 1}]})

    assert out.exit_code == 0
    assert "could not record receipt of t1" in out.stderr
    assert out.status("t1") == ["running", "done"]


def test_a_repository_with_a_containerfile_has_it_in_the_validation_and_integration_contexts(
    run_factory, golden_transcript
):
    out = run_factory({**SCENARIO, "repo": {"README": "base", "Containerfile": "FROM scratch\n"}})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_a_validation_that_times_out_is_retried_with_feedback(run_factory, golden_transcript):
    out = run_factory({**SCENARIO, "validation": [{"timed_out": True}]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)


def test_an_integrator_that_times_out_sends_feedback_to_the_implementor(run_factory, golden_transcript):
    out = run_factory({**SCENARIO, "integrator": [{"timed_out": True}]})

    assert out.exit_code == 0, out.stderr
    golden_transcript(out)
