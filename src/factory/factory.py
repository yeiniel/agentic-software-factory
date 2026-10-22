"""The long-running process: reacts to Event Source events and runs one Task at a time."""

import queue
import sys
import threading
from typing import Any

from .adapters import Adapter, AdapterError, Json
from .contexts import ContextStore
from .graph import Graph
from .interpreter import TaskRunner

END: object = object()


def serve(adapters: dict[str, Adapter], config: Json, graph: Graph) -> None:
    events: queue.Queue[Any] = queue.Queue()
    failure: list[Exception] = []

    def pump() -> None:
        try:
            for event in adapters["event-source"].stream("listen"):
                events.put(event)
        except (AdapterError, OSError) as error:
            failure.append(error)
        finally:
            events.put(END)

    threading.Thread(target=pump, daemon=True).start()
    runner = TaskRunner(adapters, config, ContextStore(config["context_root"]), graph)
    while (event := events.get()) is not END:
        if event["type"] == "task":
            runner.execute(event["task"], event["repo"])
        elif event["type"] == "main-push":
            # a human push just changes the next Run's base
            try:
                adapters["records"].call("append", body={"kind": "main-push", **event}, stream="factory")
            except AdapterError as error:
                print(f"could not record main push: {error}", file=sys.stderr)
    if failure:
        raise failure[0]
