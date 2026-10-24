"""The TUI: three views (Tasks, Task, Metrics) over the receiver's API. Read-only."""

import argparse
import threading
import time
from typing import ClassVar, cast

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, RichLog, Static, TabbedContent, TabPane, Tree
from textual.widgets.tree import TreeNode

from .client import DEFAULT_URL, Client, Json
from .views import TASK_COLUMNS, log_line, metrics_lines, node_title, span_label, task_row


class ConsoleApp(App[None]):
    TITLE = "Factory Console"
    CSS = """
    #task-view { layout: horizontal; }
    #tree { width: 45%; border-right: solid $primary; }
    #log { width: 55%; }
    #status { height: 1; dock: bottom; color: $text-muted; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("1", "show('tasks')", "Tasks"),
        Binding("2", "show('task')", "Task"),
        Binding("3", "show('metrics')", "Metrics"),
        Binding("escape", "clear_selection", "Whole Task"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, client: Client | None = None, refresh: float = 5.0) -> None:
        super().__init__()
        self.client = client or Client()
        self.refresh_every = refresh
        self.selected: str | None = None
        self.log_after = 0
        self.span: str | None = None  # the node whose log the pane shows; None is the whole Task
        self.titles: dict[str | None, str] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="tasks"):
            with TabPane("Tasks", id="tasks"):
                yield DataTable(id="tasks-table", cursor_type="row")
            with TabPane("Task", id="task"), Horizontal(id="task-view"):
                yield Tree("Select a Task in the Tasks view", id="tree")
                yield RichLog(id="log", wrap=True, markup=False, highlight=False)
            with TabPane("Metrics", id="metrics"):
                yield Static("", id="metrics-text")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = cast("DataTable[str]", self.query_one("#tasks-table", DataTable))
        table.add_columns(*TASK_COLUMNS)
        table.focus()
        self.refresh_all()
        self.listen()
        self.set_interval(self.refresh_every, self.refresh_all)

    def action_show(self, view: str) -> None:
        self.query_one(TabbedContent).active = view
        focus = {"tasks": "#tasks-table", "task": "#tree"}.get(view)
        if focus:
            self.call_after_refresh(self.query_one(focus).focus)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.selected, self.span = event.row_key.value, None
        self.query_one("#tree", Tree).clear()
        self.restart_log()
        self.action_show("task")
        self.refresh_all()

    def restart_log(self) -> None:
        self.log_after = 0
        self.query_one("#log", RichLog).clear()

    def action_clear_selection(self) -> None:
        tree = cast("Tree[str | None]", self.query_one("#tree", Tree))
        tree.move_cursor(tree.root)

    def follow_cursor(self) -> bool:
        """Select the node the cursor is on, if it is not the one selected; True when the selection changed."""
        tree = cast("Tree[str | None]", self.query_one("#tree", Tree))
        node = tree.get_node_at_line(tree.cursor_line)
        span = node.data if node else None
        if span == self.span:
            return False
        self.span = span
        self.restart_log()
        self.query_one("#log", RichLog).border_title = self.titles.get(span, "")
        return True

    def on_tree_node_highlighted(self, _event: Tree.NodeHighlighted[str | None]) -> None:
        if self.follow_cursor():
            self.refresh_all()

    @work(thread=True, exclusive=True, group="refresh")
    def refresh_all(self) -> None:
        try:
            data = {"tasks": self.client.get("/api/tasks")["tasks"], "metrics": self.client.get("/api/metrics")}
            if self.selected:
                data["spans"] = self.client.get("/api/task", id=self.selected)["spans"]
                query = {"id": self.selected, "after": self.log_after, **({"span": self.span} if self.span else {})}
                data["log"] = self.client.get("/api/task/log", **query)["log"]
            self.call_from_thread(self.show, data, None)
        except OSError as error:
            self.call_from_thread(self.show, None, str(error))

    def listen(self) -> None:
        """Refresh on every message of the live stream, reconnecting when it drops.

        The thread is a daemon one, so that quitting does not wait on a blocked read.
        """

        def follow() -> None:
            while True:
                try:
                    for _ in self.client.events():
                        self.call_from_thread(self.refresh_all)
                except (OSError, RuntimeError):
                    pass
                time.sleep(2)

        threading.Thread(target=follow, daemon=True).start()

    def show(self, data: Json | None, error: str | None) -> None:
        status = self.query_one("#status", Static)
        if data is None:
            status.update(f"receiver unreachable: {error}")
            return
        status.update("")
        table = cast("DataTable[str]", self.query_one("#tasks-table", DataTable))
        cursor = table.cursor_row
        table.clear()
        for task in data["tasks"]:
            table.add_row(*task_row(task), key=task["task"])
        if data["tasks"]:
            table.move_cursor(row=min(cursor, len(data["tasks"]) - 1))
        self.query_one("#metrics-text", Static).update("\n".join(metrics_lines(data["metrics"])))
        if "spans" in data:
            self.show_task(data["spans"], data["log"])

    def show_task(self, spans: list[Json], entries: list[Json]) -> None:
        tree = cast("Tree[str | None]", self.query_one("#tree", Tree))
        moved = self.follow_cursor()  # the cursor may have moved since the last event was handled
        tree.clear()
        tree.root.label = self.selected or ""
        lines: dict[str | None, int] = {None: 0}  # every node is expanded, so its line is its place in preorder
        self.titles = {None: f"all of {self.selected}"}

        def add(parent: TreeNode[str | None], node: Json, run: str | None) -> None:
            run = node["name"] if node["span"] == "run" else run
            self.titles[node["id"]] = node_title(node, run)
            label = span_label(node)
            child = (
                parent.add(label, node["id"], expand=True) if node["children"] else parent.add_leaf(label, node["id"])
            )
            lines[node["id"]] = len(lines)
            for sub in node["children"]:
                add(child, sub, run)

        for node in spans:
            add(tree.root, node, None)
        tree.root.expand()
        tree.cursor_line = lines[self.span]
        log = self.query_one("#log", RichLog)
        log.border_title = self.titles[self.span]
        if moved:  # these entries are of the node before; ask again for the new one
            self.refresh_all()
            return
        for entry in entries:
            log.write(log_line(entry))
            self.log_after = max(self.log_after, entry["seq"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Factory Console")
    parser.add_argument("--url", default=DEFAULT_URL, help="the receiver's API")
    ConsoleApp(Client(parser.parse_args().url)).run()
