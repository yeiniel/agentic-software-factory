"""The long-running process: reacts to Event Source events and runs Tasks, up to `task_concurrency` at once."""

import queue
import sys
import threading
from dataclasses import dataclass
from typing import Any

from .adapters import Adapter, AdapterError, Json
from .contexts import ContextStore
from .graph import Graph
from .interpreter import TaskRunner

END: object = object()


@dataclass
class Finished:
    """A Task's thread is done, so its repository and one of the slots are free."""

    repo: str


class Queue:
    """Tasks received and not finished: which may start now, given the limit and the repositories in flight."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.waiting: list[tuple[str, str]] = []  # oldest first
        self.running: set[str] = set()  # one Task per repository, as `main` is the base (ADR 0021)

    @property
    def idle(self) -> bool:
        return not self.waiting and not self.running

    def startable(self) -> list[tuple[str, str]]:
        """Take the waiting Tasks that can start now, oldest first, and mark them running."""
        started: list[tuple[str, str]] = []
        for task, repo in list(self.waiting):
            if len(self.running) < self.limit and repo not in self.running:
                self.waiting.remove((task, repo))
                self.running.add(repo)
                started.append((task, repo))
        return started


def pump(adapters: dict[str, Adapter], events: queue.Queue[Any], failure: list[Exception]) -> None:
    try:
        for event in adapters["event-source"].stream("listen"):
            events.put(event)
    except (AdapterError, OSError) as error:
        failure.append(error)
    finally:
        events.put(END)


def work(runner: TaskRunner, events: queue.Queue[Any], task: str, repo: str) -> None:
    try:
        runner.execute(task, repo)
    finally:
        events.put(Finished(repo))


def record_main_push(adapters: dict[str, Adapter], event: Json) -> None:
    # a human push just changes the next Run's base
    try:
        adapters["records"].call("append", body={"kind": "main-push", **event}, stream="factory")
    except AdapterError as error:
        print(f"could not record main push: {error}", file=sys.stderr)


def serve(adapters: dict[str, Adapter], config: Json, graph: Graph) -> None:
    events: queue.Queue[Any] = queue.Queue()
    failure: list[Exception] = []
    threading.Thread(target=pump, args=(adapters, events, failure), daemon=True).start()
    runner = TaskRunner(adapters, config, ContextStore(config["context_root"]), graph)
    tasks = Queue(config["task_concurrency"])
    ended = False
    while not (ended and tasks.idle):
        event = events.get()
        if event is END:
            ended = True
        elif isinstance(event, Finished):
            tasks.running.discard(event.repo)
        elif event["type"] == "task":
            tasks.waiting.append((event["task"], event["repo"]))
        elif event["type"] == "main-push":
            record_main_push(adapters, event)
        for task, repo in tasks.startable():
            threading.Thread(target=work, args=(runner, events, task, repo)).start()
    if failure:
        raise failure[0]
