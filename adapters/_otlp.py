"""OTLP/HTTP with JSON encoding, enough for the Records exporter and the Runner's transcript forwarding."""
import json
import urllib.request

from _common import Failure, require_env

TIMEOUT = 5


def endpoint():
    return require_env("OTEL_EXPORTER_OTLP_ENDPOINT").rstrip("/")


def value(v):
    """An OTLP AnyValue; numbers, booleans and strings keep their type, anything else is JSON text."""
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": v if isinstance(v, str) else json.dumps(v)}


def flatten(prefix, fields):
    """Attributes for a dict of fields; nested dicts become dotted keys and are all strings."""
    out = []
    for key, v in fields.items():
        if v is None:
            continue
        if isinstance(v, dict):
            out += flatten(f"{prefix}.{key}", {k: str(x) for k, x in v.items()})
        else:
            out.append({"key": f"{prefix}.{key}", "value": value(v)})
    return out


def post(path, body):
    request = urllib.request.Request(endpoint() + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT):
            pass
    except OSError as error:
        raise Failure(f"OTLP receiver at {endpoint()}: {error}") from error


RESOURCE = {"attributes": [{"key": "service.name", "value": {"stringValue": "asf"}}]}


def logs(records):
    return {"resourceLogs": [{"resource": RESOURCE, "scopeLogs": [{"scope": {"name": "asf"},
                                                                  "logRecords": records}]}]}


def traces(spans):
    return {"resourceSpans": [{"resource": RESOURCE, "scopeSpans": [{"scope": {"name": "asf"},
                                                                    "spans": spans}]}]}
