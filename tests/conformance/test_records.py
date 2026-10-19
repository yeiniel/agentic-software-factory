def test_append_accepts_an_event_for_a_stream_and_run(adapter):
    records = adapter("records")
    assert records.ok("append", {"kind": "run-started", "run": 1}, stream="task/t1", run=1) == {}


def test_append_accepts_an_event_without_a_run(adapter):
    adapter("records").ok("append", {"kind": "main-push", "commit": "abc"}, stream="factory")


def test_append_without_a_stream_fails(adapter):
    adapter("records").fails("append", {"kind": "x"})


def test_unknown_operation_fails(adapter):
    adapter("records").fails("no-such-op")
