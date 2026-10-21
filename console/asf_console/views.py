"""What each view shows, as plain text built from the API's payloads."""
import time

STATUS_MARKS = {"todo": "·", "running": "▶", "done": "✓", "blocked": "✗"}


def duration(seconds):
    if seconds is None:
        return "-"
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}m{rest:02d}s" if minutes < 60 else f"{minutes // 60}h{minutes % 60:02d}m"


def task_row(task, now=None):
    now = now or time.time()
    status = task["status"] + (f" ({task['reason']})" if task.get("reason") else "")
    return (f"{STATUS_MARKS.get(task['status'], '?')} {status}", task["task"],
            str(task["run"] or "-"), task["activity"] or "-", duration(task["age"]),
            duration(max(0.0, now - task["last_event"])) + " ago")


TASK_COLUMNS = ("Status", "Task", "Run", "Activity", "Age", "Last event")


def span_label(node):
    if node["state"] == "running":
        outcome = "running…"
    else:
        outcome = f"{node['outcome']}  {duration(node['duration'])}"
    role = f" ({node['attrs']['role']})" if node["attrs"].get("role") else ""
    return f"{node['span']} {node['name']}{role}  {outcome}"


def log_line(entry):
    stamp = time.strftime("%H:%M:%S", time.localtime(entry["ts"]))
    who = (entry.get("role") or "agent").upper() if entry["source"] == "agent" else "FACTORY"
    run = f" run {entry['run']}" if entry.get("run") else ""
    return f"{stamp} {who}{run} {entry['text']}"


def fmt(value, unit=""):
    if value is None:
        return "-"
    return f"{value:.2f}{unit}" if isinstance(value, float) else f"{value}{unit}"


def summary_line(label, s):
    return f"  {label:<22} n={s['count']:<4} avg {duration(s['avg'])}  max {duration(s['max'])}"


def metrics_lines(m):
    t, f, model = m["tasks"], m["factory"], m["model"]
    lines = ["TASKS", f"  done {t['done']}  blocked {t['blocked']}  running {t['running']}  todo {t['todo']}",
             summary_line("time to done", t["time_to_done"]), summary_line("per Run", t["runs"]),
             "  per Activity"]
    lines += [summary_line("  " + name, s) for name, s in sorted(t["activities"].items())]
    lines += ["  per Agent"] + [summary_line("  " + name, s) for name, s in sorted(t["agents"].items())]
    pct = lambda r: "-" if r is None else f"{r:.0%}"  # noqa: E731
    lines += ["", "FACTORY", f"  Runs per Task           {fmt(f['runs_per_task'])}",
              "  attempts per loop       " + (", ".join(f"{k} {fmt(v)}" for k, v in f["attempts_per_loop"].items()) or "-"),
              f"  loop exhaustion         {pct(f['loop_exhaustion_rate'])}",
              f"  integration failures    {pct(f['integration_failure_rate'])}", "  per Agent role"]
    for role, a in sorted(f["agents"].items()):
        lines.append(f"    {role:<20} runs {a['runs']}  turns {a['turns']}  tool calls {a['tool_calls']}"
                     f"  tokens {a['tokens']} ({fmt(a['tokens_per_run'])}/run)")
    lines += ["", "MODEL SERVER"]
    if model.get("available"):
        lines += [f"  slots busy {model['slots']['busy']}/{model['slots']['total']}  queue {model['queue_depth']}"
                  f"  {fmt(model['tokens_per_second'])} tokens/s"]
    else:
        lines += ["  unavailable"]
    return lines
