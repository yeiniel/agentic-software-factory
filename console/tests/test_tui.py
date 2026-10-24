"""The TUI against a stub API: the three views render from the payloads; an empty receiver is not an error."""

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from textual.widgets import DataTable, RichLog, Static, TabbedContent, Tree

from asf_console.app import ConsoleApp
from asf_console.client import Client

NOW = 1792576800.0
NO_SUMMARY = {"count": 0, "avg": None, "max": None}
EMPTY_METRICS = {
    "tasks": {
        "done": 0,
        "blocked": 0,
        "running": 0,
        "todo": 0,
        "time_to_done": NO_SUMMARY,
        "runs": NO_SUMMARY,
        "activities": {},
        "agents": {},
    },
    "factory": {
        "runs_per_task": None,
        "attempts_per_loop": {},
        "loop_exhaustion_rate": None,
        "integration_failure_rate": None,
        "agents": {},
    },
    "model": {"available": False},
}
FULL_METRICS = {
    **EMPTY_METRICS,
    "tasks": {
        **EMPTY_METRICS["tasks"],
        "done": 2,
        "blocked": 1,
        "activities": {"integrate": {"count": 3, "avg": 4.0, "max": 7.0}},
    },
    "factory": {
        **EMPTY_METRICS["factory"],
        "runs_per_task": 1.5,
        "loop_exhaustion_rate": 1 / 3,
        "agents": {"implementor": {"runs": 2, "turns": 6, "tool_calls": 5, "tokens": 3600, "tokens_per_run": 1800.0}},
    },
    "model": {"available": True, "slots": {"total": 2, "busy": 1}, "queue_depth": 0, "tokens_per_second": 41.5},
}
TASKS = [
    {
        "task": "r/a",
        "repo": "r",
        "status": "running",
        "reason": None,
        "run": 2,
        "activity": "agent",
        "received": NOW - 90,
        "last_event": NOW - 3,
        "age": 90.0,
    },
    {
        "task": "r/b",
        "repo": "r",
        "status": "blocked",
        "reason": "loop-exhausted",
        "run": 1,
        "activity": None,
        "received": NOW - 600,
        "last_event": NOW - 500,
        "age": 600.0,
    },
]
SPANS = [
    {
        "id": "1",
        "span": "run",
        "name": "2",
        "state": "running",
        "duration": None,
        "outcome": None,
        "attrs": {},
        "children": [
            {
                "id": "2",
                "span": "activity",
                "name": "agent",
                "state": "running",
                "duration": None,
                "outcome": None,
                "attrs": {"role": "implementor"},
                "children": [],
            }
        ],
    }
]
LOG = [
    {"seq": 1, "ts": NOW, "source": "factory", "role": None, "run": 2, "text": "loop-feedback: try again"},
    {"seq": 2, "ts": NOW + 1, "source": "agent", "role": "implementor", "run": 2, "text": "says: reading"},
]


@pytest.fixture
def stub():
    payloads = {
        "/api/tasks": {"tasks": TASKS},
        "/api/metrics": FULL_METRICS,
        "/api/task": {"spans": SPANS},
        "/api/task/log": {"log": LOG},
    }

    requests = payloads.setdefault("requests", [])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path, _, query = self.path.partition("?")
            requests.append(urllib.parse.parse_qs(query))
            if path == "/stream":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'data: {"type": "hello"}\n\n')
                return
            payload = payloads[path]
            body = json.dumps(payload(urllib.parse.parse_qs(query)) if callable(payload) else payload).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield payloads, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


async def settle(pilot):
    await pilot.pause(0.5)
    await pilot.pause(0.5)


def text(widget):
    return str(widget.render())


async def test_the_tasks_view_lists_tasks_with_status_run_activity_and_age(stub):
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await settle(pilot)
        table = app.query_one("#tasks-table", DataTable)
        assert table.row_count == 2
        first = [str(c) for c in table.get_row("r/a")]
        assert first[0].endswith("running") and first[1:5] == ["r/a", "2", "agent", "1m30s"]
        assert "blocked (loop-exhausted)" in str(table.get_row("r/b")[0])


async def test_selecting_a_task_shows_its_tree_and_merged_log(stub):
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        tree = app.query_one("#tree", Tree)
        labels = [str(n.label) for n in tree.root.children[0].children] + [str(tree.root.children[0].label)]
        assert any("run 2" in label and "running" in label for label in labels)
        assert any("activity agent (implementor)" in label for label in labels)
        log = "\n".join(line.text for line in app.query_one("#log", RichLog).lines)
        assert "FACTORY run 2 loop-feedback: try again" in log and "IMPLEMENTOR run 2 says: reading" in log


async def test_the_metrics_view_shows_the_three_groups(stub):
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await settle(pilot)
        metrics = text(app.query_one("#metrics-text", Static))
        for expected in (
            "done 2  blocked 1",
            "integrate",
            "Runs per Task           1.50",
            "loop exhaustion         33%",
            "tokens 3600",
            "slots busy 1/2",
            "41.50 tokens/s",
        ):
            assert expected in metrics


async def test_an_empty_receiver_gives_empty_views_not_errors(stub):
    stub[0].update({"/api/tasks": {"tasks": []}, "/api/metrics": EMPTY_METRICS})
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.query_one("#tasks-table", DataTable).row_count == 0
        assert "unavailable" in text(app.query_one("#metrics-text", Static))
        assert text(app.query_one("#status", Static)).strip() == ""


async def test_an_unreachable_receiver_is_said_in_the_status_line():
    app = ConsoleApp(Client("http://127.0.0.1:9"))
    async with app.run_test() as pilot:
        await settle(pilot)
        assert "receiver unreachable" in text(app.query_one("#status", Static))


async def test_the_number_keys_switch_between_the_views(stub):
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await settle(pilot)
        for key, view in (("3", "metrics"), ("2", "task"), ("1", "tasks")):
            await pilot.press(key)
            assert app.query_one(TabbedContent).active == view


def by_span(entries):
    """A stub log API: the entries of the span asked for, or all of them."""
    return lambda query: {"log": [e for e in entries if not query.get("span") or e["span"] in query["span"]]}


SELECTABLE = [
    {"seq": 1, "ts": NOW, "source": "factory", "role": None, "run": 2, "span": "1", "text": "run-started"},
    {"seq": 2, "ts": NOW + 1, "source": "agent", "role": "implementor", "run": 2, "span": "2", "text": "says: reading"},
]


async def open_task(pilot):
    await settle(pilot)
    await pilot.press("enter")
    await settle(pilot)


def pane(app):
    return "\n".join(line.text for line in app.query_one("#log", RichLog).lines)


async def test_selecting_a_leaf_sends_its_id_and_shows_its_records_under_its_title(stub):
    stub[0]["/api/task/log"] = by_span(SELECTABLE)
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await open_task(pilot)
        assert "run-started" in pane(app) and "says: reading" in pane(app)
        await pilot.press("down", "down")  # the run, then its Activity
        await settle(pilot)
        assert stub[0]["requests"][-1].get("span") == ["2"]
        assert pane(app).strip().endswith("says: reading") and "run-started" not in pane(app)
        assert app.query_one("#log", RichLog).border_title == "agent, Run 2"


async def test_selecting_a_run_shows_the_merged_records_and_escape_returns_to_the_whole_task(stub):
    stub[0]["/api/task/log"] = by_span(SELECTABLE)
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await open_task(pilot)
        await pilot.press("down")
        await settle(pilot)
        assert stub[0]["requests"][-1].get("span") == ["1"]
        assert app.query_one("#log", RichLog).border_title == "Run 2"
        await pilot.press("escape")
        await settle(pilot)
        assert "span" not in stub[0]["requests"][-1]
        assert app.query_one("#log", RichLog).border_title == "all of r/a"
        assert "run-started" in pane(app) and "says: reading" in pane(app)


async def test_a_rebuild_before_the_cursor_event_is_handled_still_selects_the_node(stub):
    stub[0]["/api/task/log"] = by_span(SELECTABLE)
    app = ConsoleApp(Client(stub[1]))
    async with app.run_test() as pilot:
        await open_task(pilot)
        tree = app.query_one("#tree", Tree)
        tree.cursor_line = 2
        app.show_task(SPANS, [])  # a refresh lands before the cursor's event does
        assert app.span == "2" and tree.cursor_line == 2
        await settle(pilot)
        assert stub[0]["requests"][-1].get("span") == ["2"]
