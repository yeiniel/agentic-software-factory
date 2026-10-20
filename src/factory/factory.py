"""The long-running process: reacts to Event Source events and runs one Task at a time."""
import queue
import sys
import threading

from .adapters import AdapterError
from .contexts import ContextStore
from .run import TaskRunner

END = object()


def serve(adapters, config):
    events = queue.Queue()

    failure = []

    def pump():
        try:
            for event in adapters["event-source"].stream("listen"):
                events.put(event)
        except Exception as error:
            failure.append(error)
        finally:
            events.put(END)

    threading.Thread(target=pump, daemon=True).start()
    runner = TaskRunner(adapters, config, ContextStore(config["context_root"]))
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
