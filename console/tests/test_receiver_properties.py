"""The receiver is the Console's only network-facing listener: whatever arrives, it answers and keeps serving."""

import json
import urllib.error
import urllib.request

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(st.text(max_size=12), inner, max_size=4),
    max_leaves=15,
)
ATTRIBUTE = st.fixed_dictionaries(
    {
        "key": st.sampled_from(["asf.task", "asf.run", "asf.kind", "asf.source", "asf.role", "other"]),
        "value": st.dictionaries(st.sampled_from(["stringValue", "intValue", "boolValue"]), JSON, max_size=1),
    }
)
RECORD = st.fixed_dictionaries(
    {},
    optional={
        "traceId": st.text(max_size=8),
        "spanId": st.text(max_size=8),
        "timeUnixNano": st.integers(min_value=0, max_value=2**62) | st.text(max_size=8),
        "body": st.dictionaries(st.just("stringValue"), JSON, max_size=1),
        "attributes": st.lists(ATTRIBUTE, max_size=4),
    },
)
LOGS = st.builds(
    lambda records: {"resourceLogs": [{"scopeLogs": [{"logRecords": records}]}]}, st.lists(RECORD, max_size=3)
)
CONFIG = settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


def post(receiver, path, data):
    request = urllib.request.Request(
        f"http://127.0.0.1:{receiver.otlp_port}{path}", data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        with error:
            return error.code


def serving(receiver):
    with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/api/tasks", timeout=10) as response:
        return response.status == 200


@pytest.mark.parametrize("path", ["/v1/logs", "/v1/traces"])
@CONFIG
@given(body=JSON)
def test_any_json_posted_to_the_receiver_is_accepted_or_refused_and_serving_continues(receiver, path, body):
    assert post(receiver, path, json.dumps(body).encode()) in (200, 400)
    assert serving(receiver)


@CONFIG
@given(data=st.binary(max_size=64))
def test_bytes_that_are_not_json_are_refused_and_serving_continues(receiver, data):
    status = post(receiver, "/v1/logs", data)
    assert status in (200, 400)
    assert serving(receiver)


@CONFIG
@given(body=LOGS)
def test_log_records_with_odd_fields_are_accepted_or_refused_and_the_views_still_answer(receiver, body):
    assert post(receiver, "/v1/logs", json.dumps(body).encode()) in (200, 400)
    assert serving(receiver)
    with urllib.request.urlopen(f"http://127.0.0.1:{receiver.api_port}/api/metrics", timeout=10) as response:
        assert response.status == 200
