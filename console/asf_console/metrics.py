"""Metrics derived from the stored spans and logs; nothing is exported as OTLP metrics."""

import json
from collections.abc import Iterable
from typing import Any

from .store import Store

Json = dict[str, Any]


def summary(values: Iterable[float]) -> Json:
    values = list(values)
    return {
        "count": len(values),
        "avg": sum(values) / len(values) if values else None,
        "max": max(values) if values else None,
    }


def number(value: str | float | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def ratio(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def metrics(store: Store, now: float | None = None) -> Json:
    q = store.query
    done = q("select task, ts_ns from logs where kind = 'task-status' and json_extract(attrs, '$.status') = 'done'")
    received = {r["task"]: r["ts_ns"] for r in q("select task, ts_ns from logs where kind = 'task-received'")}
    by_status: dict[str, int] = {}
    for task in store.tasks(now):
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1
    run_durations = [r["duration"] for r in q("select duration from spans where end_ns is not null and kind = 'run'")]
    activities: dict[str, list[float]] = {}
    for r in q("select name, duration from spans where kind = 'activity' and end_ns is not null"):
        activities.setdefault(r["name"], []).append(r["duration"])
    agents: dict[str, list[float]] = {}
    for r in q(
        "select json_extract(attrs, '$.role') as role, duration from spans"
        " where kind = 'activity' and name = 'agent' and end_ns is not null"
    ):
        agents.setdefault(r["role"], []).append(r["duration"])
    runs = q("select count(*) as n, count(distinct task) as tasks from spans where kind = 'run'")[0]
    loops = q(
        "select count(*) as n, sum(outcome = 'exhausted') as exhausted from spans"
        " where kind = 'loop' and end_ns is not null"
    )[0]
    attempts: dict[str, int] = {}
    for r in q(
        "select l.name as loop, count(*) as n from spans a join spans l on a.parent = l.id and a.trace = l.trace"
        " where a.kind = 'attempt' and l.kind = 'loop' group by l.name"
    ):
        attempts[r["loop"]] = r["n"]
    loop_counts = {
        r["name"]: r["n"] for r in q("select name, count(*) as n from spans where kind = 'loop' group by name")
    }
    integrations = q(
        "select count(*) as n, sum(outcome != 'green') as failed from spans"
        " where kind = 'activity' and name = 'integrate' and end_ns is not null"
    )[0]
    per_agent: dict[str, Json] = {}
    for r in q("select attrs from logs where kind = 'agent'"):
        a = json.loads(r["attrs"])
        entry = per_agent.setdefault(a.get("role"), {"runs": 0, "turns": 0, "tool_calls": 0, "tokens": 0})
        entry["runs"] += 1
        entry["turns"] += number(a.get("usage.turns"))
        entry["tool_calls"] += number(a.get("usage.tool_calls"))
        entry["tokens"] += number(a.get("usage.input_tokens")) + number(a.get("usage.output_tokens"))
    for entry in per_agent.values():
        entry["tokens_per_run"] = entry["tokens"] / entry["runs"]
    return {
        "tasks": {
            "done": by_status.get("done", 0),
            "blocked": by_status.get("blocked", 0),
            "running": by_status.get("running", 0),
            "todo": by_status.get("todo", 0),
            "time_to_done": summary((r["ts_ns"] - received[r["task"]]) / 1e9 for r in done if r["task"] in received),
            "runs": summary(run_durations),
            "activities": {name: summary(v) for name, v in activities.items()},
            "agents": {role: summary(v) for role, v in agents.items()},
        },
        "factory": {
            "runs_per_task": ratio(runs["n"], runs["tasks"]),
            "attempts_per_loop": {name: ratio(attempts.get(name, 0), n) for name, n in loop_counts.items()},
            "loop_exhaustion_rate": ratio(loops["exhausted"], loops["n"]),
            "integration_failure_rate": ratio(integrations["failed"], integrations["n"]),
            "agents": per_agent,
        },
    }
