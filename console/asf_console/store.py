"""The receiver's store: one SQLite file holding the spans and log records the Factory and Runner export.

A `started` event arrives as a log record and a `finished` one as a complete span; both name the same span id,
so a span is one row that is running until its `finished` arrives.
"""
import json
import sqlite3
import threading
import time

from .transcript import render_event, render_transcript

SCHEMA = """
create table if not exists spans (
  trace text not null, id text not null, parent text, task text, run integer, kind text, name text,
  start_ns integer, end_ns integer, duration real, outcome text, attrs text not null default '{}',
  started_seen integer not null default 0, primary key (trace, id));
create index if not exists spans_task on spans (task);
create table if not exists logs (
  seq integer primary key autoincrement, ts_ns integer not null, task text, run integer, trace text, span text,
  source text not null, kind text, body text, attrs text not null default '{}');
create index if not exists logs_task on logs (task, seq);
"""


def attributes(items):
    """OTLP attributes as a dict; `asf.` is dropped and integer values come back as integers."""
    out = {}
    for item in items or []:
        value = item.get("value", {})
        if "intValue" in value:
            parsed = int(value["intValue"])
        elif "stringValue" in value:
            parsed = value["stringValue"]
        else:
            parsed = next(iter(value.values()), None)
        key = item["key"]
        out[key[4:] if key.startswith("asf.") else key] = parsed
    return out


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.listeners = []  # called with the task id after every write
        with self.lock:
            self.db.executescript(SCHEMA)

    def close(self):
        with self.lock:
            self.db.close()

    def query(self, sql, *args):
        with self.lock:
            return [dict(row) for row in self.db.execute(sql, args)]

    def notify(self, tasks):
        for task in sorted(tasks, key=str):
            for listener in list(self.listeners):
                listener(task)

    # ---- ingestion

    def ingest_logs(self, body):
        tasks = set()
        with self.lock, self.db:
            for resource in body.get("resourceLogs", []):
                for scope in resource.get("scopeLogs", []):
                    for record in scope.get("logRecords", []):
                        tasks.add(self.add_log(record))
        self.notify(tasks)

    def add_log(self, record):
        attrs = attributes(record.get("attributes"))
        trace, span = record.get("traceId"), record.get("spanId")
        source = attrs.pop("source", "factory")
        task, run = attrs.get("task"), as_int(attrs.get("run"))
        if source == "transcript" or task is None:
            linked = self.span_row(trace, span)
            if linked:
                task, run = task or linked["task"], run if run is not None else linked["run"]
                attrs.setdefault("role", json.loads(linked["attrs"]).get("role"))
        ts = int(record.get("timeUnixNano") or time.time_ns())
        kind = attrs.get("kind") or source
        body = record.get("body", {}).get("stringValue", "")
        if kind == "started":
            self.upsert_span(trace, span, task, run, attrs, start=ts, started=True)
        self.db.execute("insert into logs (ts_ns, task, run, trace, span, source, kind, body, attrs)"
                        " values (?,?,?,?,?,?,?,?,?)",
                        (ts, task, run, trace, span, source, kind, body, json.dumps(attrs)))
        return task

    def ingest_traces(self, body):
        tasks = set()
        with self.lock, self.db:
            for resource in body.get("resourceSpans", []):
                for scope in resource.get("scopeSpans", []):
                    for span in scope.get("spans", []):
                        attrs = attributes(span.get("attributes"))
                        start, end = int(span["startTimeUnixNano"]), int(span["endTimeUnixNano"])
                        self.upsert_span(span["traceId"], span["spanId"], attrs.get("task"),
                                         as_int(attrs.get("run")), attrs, start=start, end=end,
                                         parent=span.get("parentSpanId"))
                        tasks.add(attrs.get("task"))
        self.notify(tasks)

    def span_row(self, trace, span):
        rows = self.db.execute("select * from spans where trace = ? and id = ?", (trace, span)).fetchall()
        return dict(rows[0]) if rows else None

    def upsert_span(self, trace, span, task, run, attrs, start, end=None, parent=None, started=False):
        previous = self.span_row(trace, span)
        kind, name = attrs.get("span"), attrs.get("name")
        parent = parent or attrs.get("parent")
        if previous is None:
            self.db.execute("insert into spans (trace, id, parent, task, run, kind, name, start_ns, end_ns,"
                            " duration, outcome, attrs, started_seen) values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (trace, span, parent, task, run, kind, name, start, end,
                             None if end is None else (end - start) / 1e9, attrs.get("outcome"),
                             json.dumps(attrs), int(started)))
            return
        sets = {"parent": parent or previous["parent"], "task": task or previous["task"],
                "run": run if run is not None else previous["run"], "kind": kind or previous["kind"],
                "name": name or previous["name"], "attrs": json.dumps({**json.loads(previous["attrs"]), **attrs})}
        if started:
            sets.update(start_ns=start, started_seen=1)
        elif not previous["started_seen"]:
            sets["start_ns"] = start  # no `started` yet: the span's own start is the best there is
        if end is not None:
            sets.update(end_ns=end, duration=(end - start) / 1e9, outcome=attrs.get("outcome"))
        self.db.execute(f"update spans set {', '.join(f'{k} = ?' for k in sets)} where trace = ? and id = ?",
                        (*sets.values(), trace, span))

    # ---- views

    def tasks(self, now=None):
        now = now or time.time()
        out = []
        for row in self.query("select task, min(ts_ns) as received, max(ts_ns) as last from logs"
                              " where task is not null group by task order by received desc"):
            task = row["task"]
            received = self.query("select attrs, ts_ns from logs where task = ? and kind = 'task-received'"
                                  " order by seq limit 1", task)
            status = self.query("select attrs from logs where task = ? and kind = 'task-status'"
                                " order by seq desc limit 1", task)
            current = self.query("select name from spans where task = ? and kind = 'activity'"
                                 " and end_ns is null order by start_ns desc limit 1", task)
            runs = self.query("select max(run) as run from spans where task = ?", task)[0]["run"]
            state = json.loads(status[0]["attrs"]) if status else {}
            start = (received[0]["ts_ns"] if received else row["received"]) / 1e9
            out.append({"task": task, "repo": json.loads(received[0]["attrs"]).get("repo") if received else None,
                        "status": state.get("status", "todo"), "reason": state.get("reason"),
                        "run": runs, "activity": current[0]["name"] if current else None,
                        "received": start, "last_event": row["last"] / 1e9, "age": max(0.0, now - start)})
        return out

    def tree(self, task):
        rows = self.query("select * from spans where task = ? order by start_ns, rowid", task)
        nodes = {r["id"]: {"id": r["id"], "span": r["kind"], "name": r["name"], "parent": r["parent"],
                           "state": "running" if r["end_ns"] is None else "finished", "start": r["start_ns"] / 1e9,
                           "duration": r["duration"], "outcome": r["outcome"],
                           "attrs": json.loads(r["attrs"]), "children": []} for r in rows}
        roots = []
        for node in nodes.values():
            (nodes[node["parent"]]["children"] if node["parent"] in nodes else roots).append(node)
        return roots

    def log(self, task, after=0):
        entries = []
        for row in self.query("select * from logs where task = ? and seq > ? and kind not in ('started', 'finished')"
                              " order by seq", task, after):
            attrs = json.loads(row["attrs"])
            texts = render_transcript(row["body"]) if row["source"] == "transcript" else [render_event(row["kind"], attrs)]
            for text in texts:
                entries.append({"seq": row["seq"], "ts": row["ts_ns"] / 1e9,
                                "source": "agent" if row["source"] == "transcript" else "factory",
                                "role": attrs.get("role"), "run": row["run"], "text": text})
        return entries
