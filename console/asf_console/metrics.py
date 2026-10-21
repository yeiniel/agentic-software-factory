"""Metrics derived from the stored spans and logs; nothing is exported as OTLP metrics."""
import json


def summary(values):
    values = list(values)
    return {"count": len(values), "avg": sum(values) / len(values) if values else None,
            "max": max(values) if values else None}


def number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def ratio(part, whole):
    return part / whole if whole else None


def metrics(store, now=None):
    q = store.query
    done = q("select task, ts_ns from logs where kind = 'task-status' and json_extract(attrs, '$.status') = 'done'")
    received = {r["task"]: r["ts_ns"] for r in q("select task, ts_ns from logs where kind = 'task-received'")}
    by_status = {}
    for task in store.tasks(now):
        by_status[task["status"]] = by_status.get(task["status"], 0) + 1
    durations = lambda where, *args: [r["duration"] for r in q(  # noqa: E731
        f"select duration from spans where end_ns is not null and {where}", *args)]
    activities = {}
    for r in q("select name, duration from spans where kind = 'activity' and end_ns is not null"):
        activities.setdefault(r["name"], []).append(r["duration"])
    agents = {}
    for r in q("select json_extract(attrs, '$.role') as role, duration from spans"
               " where kind = 'activity' and name = 'agent' and end_ns is not null"):
        agents.setdefault(r["role"], []).append(r["duration"])
    runs = q("select count(*) as n, count(distinct task) as tasks from spans where kind = 'run'")[0]
    loops = q("select count(*) as n, sum(outcome = 'exhausted') as exhausted from spans"
              " where kind = 'loop' and end_ns is not null")[0]
    attempts = {}
    for r in q("select l.name as loop, count(*) as n from spans a join spans l on a.parent = l.id and a.trace = l.trace"
               " where a.kind = 'attempt' and l.kind = 'loop' group by l.name"):
        attempts[r["loop"]] = r["n"]
    loop_counts = {r["name"]: r["n"] for r in q("select name, count(*) as n from spans where kind = 'loop' group by name")}
    integrations = q("select count(*) as n, sum(outcome != 'green') as failed from spans"
                     " where kind = 'activity' and name = 'integrate' and end_ns is not null")[0]
    per_agent = {}
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
        "tasks": {"done": by_status.get("done", 0), "blocked": by_status.get("blocked", 0),
                  "running": by_status.get("running", 0), "todo": by_status.get("todo", 0),
                  "time_to_done": summary((r["ts_ns"] - received[r["task"]]) / 1e9 for r in done if r["task"] in received),
                  "runs": summary(durations("kind = 'run'")),
                  "activities": {name: summary(v) for name, v in activities.items()},
                  "agents": {role: summary(v) for role, v in agents.items()}},
        "factory": {"runs_per_task": ratio(runs["n"], runs["tasks"]),
                    "attempts_per_loop": {name: ratio(attempts.get(name, 0), n) for name, n in loop_counts.items()},
                    "loop_exhaustion_rate": ratio(loops["exhausted"], loops["n"]),
                    "integration_failure_rate": ratio(integrations["failed"], integrations["n"]),
                    "agents": per_agent},
    }
