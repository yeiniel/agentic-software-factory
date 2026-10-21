"""`listen` is long-running: read lines until we have enough or the deadline passes, then stop it."""

import json
import os
import queue
import subprocess
import threading
import time


def first_events(source, count=1, wait=15):
    process = subprocess.Popen(
        [*source.argv, "listen"], stdout=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL, env=source.env
    )
    stdout = process.stdout
    assert stdout is not None
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in stdout] or lines.put(None), daemon=True).start()
    trigger = getattr(source, "trigger", None) or os.environ.get("ADAPTER_EVENT_SOURCE_TRIGGER")
    if trigger:  # a real source needs something to report
        subprocess.run(trigger, shell=True, check=True)
    events, deadline = [], time.time() + wait
    try:
        while len(events) < count and (left := deadline - time.time()) > 0:
            try:
                line = lines.get(timeout=left)
            except queue.Empty:
                break
            if line is None:
                break
            if line.strip():
                events.append(json.loads(line))
    finally:
        process.kill()
        process.wait()
        stdout.close()
    return events


def test_listen_prints_one_json_event_per_line(adapter):
    events = first_events(adapter("event-source"))
    assert events and all(isinstance(e, dict) for e in events)


def test_events_are_task_or_main_push_with_their_fields(adapter):
    events = first_events(adapter("event-source"), count=10)
    assert events
    for event in events:
        if event["type"] == "task":
            assert event["task"] and event["repo"]
        else:
            assert event["type"] == "main-push"
            assert event["repo"] and event["commit"]


def test_unknown_operation_fails(adapter):
    source = adapter("event-source")
    source.timeout = 5
    source.fails("no-such-op")
