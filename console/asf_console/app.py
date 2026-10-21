"""The TUI: three views (Tasks, Task, Metrics) over the receiver's API. Read-only."""

import argparse
import threading
import time
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, RichLog, Static, TabbedContent, TabPane, Tree
from textual.widgets.tree import TreeNode

from .client import DEFAULT_URL, Client, Json
from .views import TASK_COLUMNS, log_line, metrics_lines, span_label, task_row


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
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, client: Client | None = None, refresh: float = 5.0) -> None:
        super().__init__()
        self.client = client or Client()
        self.refresh_every = refresh
        self.selected: str | None = None
        self.log_after = 0

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
        table = self.query_one("#tasks-table", DataTable[str])
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
        self.selected, self.log_after = event.row_key.value, 0
        self.query_one("#log", RichLog).clear()
        self.action_show("task")
        self.refresh_all()

    @work(thread=True, exclusive=True, group="refresh")
    def refresh_all(self) -> None:
        try:
            data = {"tasks": self.client.get("/api/tasks")["tasks"], "metrics": self.client.get("/api/metrics")}
            if self.selected:
                data["spans"] = self.client.get("/api/task", id=self.selected)["spans"]
                data["log"] = self.client.get("/api/task/log", id=self.selected, after=self.log_after)["log"]
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
        table = self.query_one("#tasks-table", DataTable[str])
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
        tree = self.query_one("#tree", Tree[None])
        tree.clear()
        tree.root.label = self.selected or ""

        def add(parent: TreeNode[None], node: Json) -> None:
            child = parent.add(span_label(node), expand=True) if node["children"] else parent.add_leaf(span_label(node))
            for sub in node["children"]:
                add(child, sub)

        for node in spans:
            add(tree.root, node)
        tree.root.expand()
        log = self.query_one("#log", RichLog)
        for entry in entries:
            log.write(log_line(entry))
            self.log_after = max(self.log_after, entry["seq"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Factory Console")
    parser.add_argument("--url", default=DEFAULT_URL, help="the receiver's API")
    ConsoleApp(Client(parser.parse_args().url)).run()


if __name__ == "__main__":
    main()
