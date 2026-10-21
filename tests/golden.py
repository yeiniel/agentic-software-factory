"""Golden transcripts: a scenario's Adapter calls, Records and Run Contexts, normalised, as one text file.

Only what is nondeterministic is normalised: durations, span ids, commit ids, Context paths, and the order in
which the two parallel Agents' calls interleave. `UPDATE_GOLDENS=1` rewrites the files; review the diff.
"""
import json
import os
import re
from pathlib import Path

GOLDENS = Path(__file__).parent / "goldens"
LANES = ("acceptance-writer", "implementor")  # flushed in this order after a concurrent step
SPAN_ID = re.compile(r"\b[0-9a-f]{16}\b")
COMMIT_ID = re.compile(r'(?<=")c\d+(?=")')


def loop_lane(spans, span):
    """The loop a span belongs to (`writer` or `implementor`), or None outside both loops."""
    while span in spans:
        kind, name, parent = spans[span]
        if kind == "loop":
            return LANES[name == "implementor"]
        span = parent
    return None


def role_in(text):
    """The Agent role a branch name or Context path names; the Integrator's Contexts name none."""
    if "integrate-" in text:
        return None
    if "validate-" in text:
        return "acceptance-writer"
    return next((role for role in LANES if role in text), None)


def lane_of(call, spans):
    """Which concurrent Agent loop issued `call`, or None when the Run's own thread did."""
    body, args = call["body"], call["args"]
    if call["port"] == "records":
        if body["kind"] in ("started", "finished"):
            spans.setdefault(body["id"], (body["span"], body["name"], body["parent"]))
            return loop_lane(spans, body["id"])
        if body["kind"] in ("agent", "branch-recorded"):
            return body["role"]
        if body["kind"] in ("attempt", "loop-feedback"):
            return LANES[body["loop"] == "implementor"]
        return LANES[0] if body["kind"] == "validation" else None
    if call["port"] in ("repo-host", "runner"):
        return next(filter(None, (role_in(str(v)) for v in args.values())), None)
    return None


def canonical(calls):
    """The calls with each concurrent step's calls grouped by lane, so the order is reproducible."""
    spans, buffers, out = {}, {lane: [] for lane in LANES}, []

    def flush():
        for lane in LANES:
            out.extend(buffers[lane])
            buffers[lane].clear()

    for call in calls:
        lane = lane_of(call, spans)
        if lane:
            buffers[lane].append(call)
        else:
            flush()
            out.append(call)
    flush()
    return out


def contexts(state):
    """The Run Contexts the core wrote, as the stand-in Runner saw them."""
    runs = [("agent", r) for r in state["agent_runs"]] + [("validation", r) for r in state["validation_runs"]] \
        + [("integrator", r) for r in state["integrator_runs"]]
    return [{"kind": kind, **{k: v for k, v in run.items() if k not in ("at", "start", "end")}}
            for kind, run in sorted(runs, key=lambda item: item[1]["context"])]


def transcript(out):
    lines = ["## calls"]
    lines += [json.dumps(call, sort_keys=True) for call in canonical(out.calls)]
    lines += ["", "## run contexts"]
    lines += [json.dumps(context, sort_keys=True) for context in contexts(out.state)]
    return "\n".join(lines) + "\n"


def normalise(text, fixture):
    text = re.sub(r'"duration": [0-9.e-]+', '"duration": "<duration>"', text)
    text = text.replace(f"{fixture}/contexts/", "<contexts>/").replace(str(fixture), "<fixture>")
    for pattern, label in ((SPAN_ID, "span"), (COMMIT_ID, "commit")):
        labels = {}
        text = pattern.sub(lambda m, labels=labels, label=label: labels.setdefault(
            m.group(), f"{label}-{len(labels) + 1}"), text)
    return text


def check(out, name):
    """Assert the scenario's transcript equals its golden file, or write it when UPDATE_GOLDENS=1."""
    actual = normalise(transcript(out), out.fixture)
    path = GOLDENS / f"{name}.txt"
    if os.environ.get("UPDATE_GOLDENS"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(actual)
    assert path.read_text() == actual, f"{path} differs; run with UPDATE_GOLDENS=1 to review the change"
