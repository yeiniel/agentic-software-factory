"""The receiver's API against recorded fixtures: a green Task, one Blocked by an exhausted loop, a retry."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from replay import Script, blocked_task, green_task, retried_task


def by_task(api):
    return {t["task"]: t for t in api("/api/tasks")["tasks"]}


def flat(nodes):
    for node in nodes:
        yield node
        yield from flat(node["children"])


def test_an_empty_receiver_answers_with_empty_views(api):
    assert api("/api/tasks") == {"tasks": []}
    metrics = api("/api/metrics")
    assert metrics["tasks"]["done"] == 0 and metrics["model"]["available"] is False


def test_the_task_list_shows_status_run_and_age(replay, api):
    green_task(replay)
    blocked_task(replay)
    retried_task(replay)

    tasks = by_task(api)
    assert {k: (v["status"], v["run"]) for k, v in tasks.items()} == {
        "r/green": ("done", 1),
        "r/blocked": ("blocked", 1),
        "r/retried": ("done", 2),
    }
    assert tasks["r/blocked"]["reason"] == "loop-exhausted"
    assert tasks["r/green"]["repo"] == "r" and tasks["r/green"]["age"] >= 0
    assert tasks["r/green"]["last_event"] >= tasks["r/green"]["received"]


def test_a_started_but_unfinished_activity_shows_as_running(replay, api):
    s = Script(replay, "r/live")
    s.event("task-received", repo="r")
    s.status("running")
    run = s.open("run", "1", None, 1)
    at = s.open("attempt", "1", s.open("loop", "writer", run, 1), 1)
    s.open("activity", "agent", at, 1, role="acceptance-writer")

    task = by_task(api)["r/live"]
    assert (task["status"], task["activity"]) == ("running", "agent")
    tree = api("/api/task?id=r/live")["spans"]
    assert [n["state"] for n in flat(tree)] == ["running"] * 4


def test_once_finished_the_activity_is_no_longer_current(replay, api):
    s = Script(replay, "r/live")
    s.event("task-received", repo="r")
    s.status("running")
    run = s.open("run", "1", None, 1)
    agent = s.open("activity", "agent", run, 1, role="implementor")
    assert by_task(api)["r/live"]["activity"] == "agent"
    s.close(agent, "ok", 3.0)
    assert by_task(api)["r/live"]["activity"] is None


def test_a_tasks_tree_nests_runs_loops_attempts_and_activities_with_durations_and_outcomes(replay, api):
    retried_task(replay)
    green_task(replay)

    tree = api("/api/task?id=r/green")["spans"]
    (run,) = tree
    assert (run["span"], run["name"], run["outcome"], run["duration"], run["state"]) == (
        "run",
        "1",
        "green",
        30,
        "finished",
    )
    loops = {n["name"]: n for n in run["children"] if n["span"] == "loop"}
    assert set(loops) == {"writer", "implementor"}
    attempt = loops["implementor"]["children"][0]
    assert attempt["span"] == "attempt" and attempt["outcome"] == "green"
    assert [(c["name"], c["duration"]) for c in attempt["children"]] == [("agent", 8.0)]
    assert [c["name"] for c in run["children"] if c["span"] == "activity"] == ["integrate", "publish"]
    retried = api("/api/task?id=r/retried")["spans"]
    assert [(r["name"], r["outcome"]) for r in retried] == [("1", "red"), ("2", "green")]


def test_a_blocked_tasks_tree_names_the_exhausted_loop(replay, api):
    blocked_task(replay)

    (run,) = api("/api/task?id=r/blocked")["spans"]
    (loop,) = run["children"]
    assert (loop["name"], loop["outcome"]) == ("implementor", "exhausted")
    assert [a["outcome"] for a in loop["children"]] == ["crashed", "crashed"]


def test_the_log_merges_factory_events_with_the_feedback_shown_at_each_retry(replay, api):
    blocked_task(replay)
    retried_task(replay)

    texts = [e["text"] for e in api("/api/task/log?id=r/blocked")["log"]]
    assert any("Your last attempt crashed: boom" in t for t in texts)
    assert not any(t.startswith(("started", "finished")) for t in texts)
    assert any("the suite failed: greeting is empty" in e["text"] for e in api("/api/task/log?id=r/retried")["log"])


def test_transcript_entries_are_merged_into_the_log_by_their_attempt(replay, receiver, api):
    s = Script(replay, "r/talk")
    s.event("task-received", repo="r")
    run = s.open("run", "1", None, 1)
    agent = s.open("activity", "agent", run, 1, role="implementor")
    entries = [
        {
            "type": "message",
            "timestamp": "2026-10-21T10:00:01.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I will read the file"},
                    {"type": "toolCall", "name": "read", "arguments": {"path": "a.py"}},
                ],
            },
        },
        {
            "type": "message",
            "timestamp": "2026-10-21T10:00:02.000Z",
            "message": {"role": "toolResult", "toolName": "read", "content": [{"type": "text", "text": "print(1)"}]},
        },
    ]
    records = [
        {
            "timeUnixNano": "1792576801000000000",
            "body": {"stringValue": json.dumps(e)},
            "traceId": s.trace,
            "spanId": agent,
            "attributes": [{"key": "asf.source", "value": {"stringValue": "transcript"}}],
        }
        for e in entries
    ]
    body = {"resourceLogs": [{"scopeLogs": [{"logRecords": records}]}]}
    request = urllib.request.Request(
        f"http://127.0.0.1:{receiver.otlp_port}/v1/logs",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(request).read()

    agent_lines = [e for e in api("/api/task/log?id=r/talk")["log"] if e["source"] == "agent"]
    assert [(e["role"], e["run"]) for e in agent_lines] == [("implementor", 1)] * 3
    assert [e["text"] for e in agent_lines] == [
        "says: I will read the file",
        'calls read {"path": "a.py"}',
        "read returned: print(1)",
    ]


def test_the_log_can_be_read_from_a_point(replay, api):
    blocked_task(replay)

    everything = api("/api/task/log?id=r/blocked")
    after = everything["log"][2]["seq"]
    assert [e["seq"] for e in api(f"/api/task/log?id=r/blocked&after={after}")["log"]] == [
        e["seq"] for e in everything["log"] if e["seq"] > after
    ]


def test_metrics_report_task_timings_and_factory_performance(replay, api):
    green_task(replay)
    blocked_task(replay)
    retried_task(replay)

    metrics = api("/api/metrics")
    assert metrics["tasks"]["done"] == 2 and metrics["tasks"]["blocked"] == 1
    assert metrics["tasks"]["time_to_done"]["count"] == 2
    assert metrics["tasks"]["activities"]["integrate"]["count"] == 3
    assert metrics["tasks"]["activities"]["validate"] == {"count": 1, "avg": 5.0, "max": 5.0}
    assert metrics["tasks"]["agents"]["implementor"]["avg"] == 4.0  # three Agent steps: 8.0, 2.0 and 2.0
    assert metrics["tasks"]["runs"]["count"] == 4
    factory = metrics["factory"]
    assert factory["runs_per_task"] == 4 / 3
    assert factory["attempts_per_loop"] == {"writer": 1.0, "implementor": 1.5}
    assert factory["loop_exhaustion_rate"] == 1 / 3
    assert factory["integration_failure_rate"] == 1 / 3
    implementor = factory["agents"]["implementor"]
    assert (implementor["tokens"], implementor["tool_calls"], implementor["turns"]) == (3600, 5, 6)


def test_the_stream_announces_new_data(replay, receiver):
    seen = []
    stream = urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/stream", timeout=10)

    def read():
        for line in stream:
            if line.startswith(b"data:"):
                seen.append(json.loads(line[5:]))
                if len(seen) == 2:
                    return

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    time.sleep(0.3)
    s = Script(replay, "r/stream")
    s.event("task-received", repo="r")
    reader.join(timeout=10)
    stream.close()
    assert seen and seen[-1]["type"] == "changed" and seen[-1]["task"] == "r/stream"


def post(receiver, path, body):
    request = urllib.request.Request(
        f"http://127.0.0.1:{receiver.otlp_port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(request, timeout=10).read()


def logs(*records):
    return {"resourceLogs": [{"scopeLogs": [{"logRecords": list(records)}]}]}


def string(key, value):
    return {"key": f"asf.{key}", "value": {"stringValue": value}}


TRACE = "a" * 32


def span_started(span, task="r/t"):
    return {
        "traceId": TRACE,
        "spanId": span,
        "body": {"stringValue": "started"},
        "attributes": [string("kind", "started"), string("task", task), string("span", "run"), string("name", "1")],
    }


def span_finished(span, task="r/t"):
    return {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": TRACE,
                                "spanId": span,
                                "name": "run:1",
                                "startTimeUnixNano": "1000000000",
                                "endTimeUnixNano": "3000000000",
                                "attributes": [
                                    string("task", task),
                                    string("span", "run"),
                                    string("name", "1"),
                                    string("outcome", "green"),
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }


def test_an_unknown_path_is_not_found(receiver):
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/nope", timeout=10)
    with refused.value:
        assert refused.value.code == 404


def test_a_run_that_is_not_a_number_is_ignored(receiver, api):
    post(
        receiver,
        "/v1/logs",
        logs({"attributes": [string("kind", "task-received"), string("task", "r/t"), string("run", "abc")]}),
    )

    assert [t["task"] for t in api("/api/tasks")["tasks"]] == ["r/t"]


def test_usage_that_is_not_a_number_counts_as_nothing(receiver, api):
    post(
        receiver,
        "/v1/logs",
        logs(
            {
                "attributes": [
                    string("kind", "agent"),
                    string("task", "r/t"),
                    string("role", "implementor"),
                    string("usage.turns", "many"),
                ]
            }
        ),
    )

    assert api("/api/metrics")["factory"]["agents"]["implementor"]["turns"] == 0


def test_a_span_that_finishes_before_it_is_started_is_one_span(receiver, api):
    post(receiver, "/v1/traces", span_finished("b" * 16))
    post(receiver, "/v1/logs", logs(span_started("b" * 16)))

    (span,) = api("/api/task?id=r/t")["spans"]
    assert (span["span"], span["state"], span["outcome"]) == ("run", "finished", "green")


def test_a_span_that_is_exported_twice_is_still_one_span(receiver, api):
    post(receiver, "/v1/traces", span_finished("b" * 16))
    post(receiver, "/v1/traces", span_finished("b" * 16))

    assert len(api("/api/task?id=r/t")["spans"]) == 1


def transcript(receiver, *bodies):
    post(
        receiver,
        "/v1/logs",
        logs(
            *(
                {
                    "traceId": TRACE,
                    "spanId": "b" * 16,
                    "body": {"stringValue": body},
                    "attributes": [string("source", "transcript"), string("task", "r/t")],
                }
                for body in bodies
            )
        ),
    )


def test_transcript_entries_that_say_nothing_readable_are_left_out_of_the_log(receiver, api):
    transcript(
        receiver,
        "not json",
        json.dumps({"type": "message", "message": {"role": "assistant"}}),
        json.dumps({"type": "message", "message": {"role": "assistant", "content": ["bare", {"type": "image"}]}}),
        json.dumps({"type": "message", "message": {"role": "assistant", "content": "plain"}}),
    )

    assert [e["text"] for e in api("/api/task/log?id=r/t")["log"]] == ["says: plain"]


def test_the_stream_is_kept_alive_and_a_client_that_leaves_is_dropped(start_receiver, replay):
    receiver = start_receiver(keepalive=0.2)
    stream = urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/stream", timeout=10)
    stream.readline()
    stream.readline()
    assert b"keepalive" in stream.readline() + stream.readline()
    stream.close()
    for _ in range(3):  # the first write after the client left may still succeed
        post(receiver, "/v1/logs", logs({"attributes": [string("kind", "task-received"), string("task", "r/t")]}))
        time.sleep(0.3)
    with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/api/tasks", timeout=10) as response:
        assert response.status == 200
