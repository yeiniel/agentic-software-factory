"""The events the core emits for the Console (spec 0006): spans with ids, task lifecycle, trace context."""
import re

TASK_EVENT = {"type": "task", "task": "t1", "repo": "r"}


def spans(out, kind):
    return [e for e in (r["event"] for r in out.records if r["stream"] == "task/t1") if e["kind"] == kind]


def pairs(out):
    """(started, finished) for every span, matched by id."""
    started = {e["id"]: e for e in spans(out, "started")}
    finished = {e["id"]: e for e in spans(out, "finished")}
    assert started.keys() == finished.keys()
    return [(started[i], finished[i]) for i in started]


def test_every_span_starts_and_finishes_with_an_id_a_parent_and_a_duration(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    assert out.exit_code == 0, out.stderr
    everything = pairs(out)
    ids = {s["id"] for s, _ in everything}
    for started, finished in everything:
        assert re.fullmatch(r"[0-9a-f]{16}", started["id"])
        assert started["parent"] is None or started["parent"] in ids
        assert (started["span"], started["name"]) == (finished["span"], finished["name"])
        assert finished["duration"] >= 0
        assert finished["outcome"]
    assert len({s["trace"] for s, _ in everything}) == 1
    assert re.fullmatch(r"[0-9a-f]{32}", everything[0][0]["trace"])


def test_a_green_task_nests_run_loop_attempt_and_activity(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    by_id = {s["id"]: s for s, _ in pairs(out)}

    def chain(span):
        names = []
        while span:
            names.append(f"{span['span']}:{span['name']}")
            span = by_id.get(span["parent"])
        return list(reversed(names))

    chains = {tuple(chain(s)) for s in by_id.values()}
    assert ("run:1", "loop:writer", "attempt:1", "activity:agent") in chains
    assert ("run:1", "loop:writer", "attempt:1", "activity:validate") in chains
    assert ("run:1", "loop:implementor", "attempt:1", "activity:agent") in chains
    assert ("run:1", "activity:integrate") in chains
    assert ("run:1", "activity:publish") in chains
    outcomes = {(s["span"], s["name"]): f["outcome"] for s, f in pairs(out)}
    assert outcomes[("run", "1")] == "green"


def test_a_failed_attempt_is_a_span_with_its_outcome_and_its_feedback_is_recorded(run_factory):
    crash = {"exit_status": 1, "output": "impl crashed"}
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [crash]}})

    attempts = [(s["name"], f["outcome"]) for s, f in pairs(out) if s["span"] == "attempt"]
    assert ("1", "crashed") in attempts and ("1", "green") in attempts
    (loop_feedback,) = spans(out, "loop-feedback")
    assert loop_feedback["loop"] == "implementor" and "impl crashed" in loop_feedback["feedback"]


def test_an_exhausted_loop_finishes_its_span_exhausted(run_factory):
    crash = {"exit_status": 1, "output": "impl crashed"}
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [crash, crash]}})

    loops = {s["name"]: f["outcome"] for s, f in pairs(out) if s["span"] == "loop"}
    assert loops["implementor"] == "exhausted" and loops["writer"] == "succeeded"


def test_every_event_of_a_task_carries_the_trace(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    traces = {e["trace"] for r in out.records if r["stream"] == "task/t1" for e in [r["event"]]}
    assert len(traces) == 1


def test_task_received_is_recorded_before_anything_else(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    first = out.records[0]
    assert first["stream"] == "task/t1" and first["event"]["kind"] == "task-received"
    assert first["event"]["repo"] == "r"


def test_a_task_status_event_follows_every_status_written(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    assert [e["status"] for e in spans(out, "task-status")] == out.status("t1") == ["running", "done"]


def test_a_blocked_task_records_its_status_and_reason(run_factory):
    crash = {"exit_status": 1, "output": "impl crashed"}
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT], "agent": {"implementor": [crash, crash]}})

    last = spans(out, "task-status")[-1]
    assert last["status"] == "blocked" and last["reason"] == "loop-exhausted"


def test_existing_event_kinds_are_unchanged(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    kinds = {r["event"]["kind"] for r in out.records}
    assert {"run-started", "attempt", "agent", "branch-recorded", "validation", "integrator",
            "fast-forward", "run-finished"} <= kinds
    (run_started,) = spans(out, "run-started")
    assert run_started["run"] == 1 and set(run_started["roles"]) == {"implementor", "acceptance-writer"}


def test_the_runner_gets_a_traceparent_that_names_the_agents_span(run_factory):
    out = run_factory({"tasks": {"t1": "x"}, "events": [TASK_EVENT]})

    agentic = [c for c in out.calls_to("runner", "run") if c["args"]["type"] == "agentic"]
    deterministic = [c for c in out.calls_to("runner", "run") if c["args"]["type"] == "deterministic"]
    assert len(agentic) == 2
    agent_spans = {s["id"]: s for s, _ in pairs(out) if s["name"] == "agent"}
    for call in agentic:
        version, trace, span, flags = call["args"]["traceparent"].split("-")
        assert (version, flags) == ("00", "01")
        assert span in agent_spans and trace == agent_spans[span]["trace"]
    assert all("traceparent" not in c["args"] for c in deterministic)
