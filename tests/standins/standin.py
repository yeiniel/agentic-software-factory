#!/usr/bin/env python3
"""Scripted stand-in for all six Adapter ports: `standin.py <port> <op> [--k v ...]`.

Behaviour is scripted by $FIXTURE_DIR/scenario.json; every call is logged to
calls.jsonl and state lives in state.json. Test infrastructure only.
"""
import fcntl
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

FIX = Path(os.environ["FIXTURE_DIR"])
SCENARIO = json.loads((FIX / "scenario.json").read_text())


@contextmanager
def locked():
    with open(FIX / "lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = FIX / "state.json"
        if path.exists():
            state = json.loads(path.read_text())
        else:
            state = {"main": "c0", "n": 0, "commits": {"c0": SCENARIO.get("repo", {})},
                     "branches": {}, "status": {}, "status_body": {}, "counters": {},
                     "agent_spans": []}
        yield state
        path.write_text(json.dumps(state))


def read_tree(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()}


def write_tree(root, files):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


def new_commit(state, files):
    state["n"] += 1
    commit = f"c{state['n']}"
    state["commits"][commit] = files
    return commit


def parse(argv):
    args = {}
    for i in range(0, len(argv), 2):
        args[argv[i].lstrip("-")] = argv[i + 1]
    return args


def bump(state, key):
    state["counters"][key] = state["counters"].get(key, 0) + 1
    return state["counters"][key]


def main():
    port, op, *rest = sys.argv[1:]
    args = parse(rest)
    raw = "" if port == "event-source" else sys.stdin.read()
    body = json.loads(raw) if raw.strip() else None
    with open(FIX / "calls.jsonl", "a") as log:
        log.write(json.dumps({"port": port, "op": op, "args": args, "body": body}) + "\n")
    with locked() as state:
        nth = bump(state, f"{port}/{op}")
    for fail in SCENARIO.get("fail", []):
        if fail["port"] == port and fail["op"] == op and fail["call"] == nth:
            print("injected failure", file=sys.stderr)
            sys.exit(1)
    result = globals()["do_" + port.replace("-", "_")](op, args, body)
    if result is not None:
        print(json.dumps(result))


def do_event_source(op, args, body):
    for event in SCENARIO.get("events", []):
        if "sleep" in event:
            time.sleep(event["sleep"])
        else:
            print(json.dumps(event), flush=True)


def do_task_store(op, args, body):
    if op == "get-prompt":
        return {"prompt": SCENARIO["tasks"][args["task"]]}
    if op == "set-status":
        with locked() as state:
            state["status"].setdefault(args["task"], []).append(args["status"])
            state["status_body"].setdefault(args["task"], []).append(body)
        return {}


def do_repo_host(op, args, body):
    with locked() as state:
        if op == "main-head":
            return {"commit": state["main"]}
        if op == "create-branch":
            state["branches"][args["name"]] = args["base"]
            return {"commit": args["base"]}
        if op == "checkout":
            commit = args["commit"] if "commit" in args else (
                state["main"] if args["branch"] == "main" else state["branches"][args["branch"]])
            write_tree(args["dest"], state["commits"][commit])
            return {"commit": commit}
        if op == "record":
            files = read_tree(args["from"])
            previous = state["commits"][state["branches"][args["branch"]]] if args["branch"] in state["branches"] else None
            commit = new_commit(state, files)
            state["branches"][args["branch"]] = commit
            return {"commit": commit, "changed": files != previous}
        if op == "fast-forward-main":
            if state["main"] != args["expect-main"]:
                return {"advanced": False, "head": state["main"]}
            state["main"] = state["branches"][args["branch"]]
            return {"advanced": True, "head": state["main"]}


def do_environment_builder(op, args, body):
    return {"image": f"img-{args['purpose']}-{args['commit']}"}


def do_runner(op, args, body):
    if op == "provision-context":
        ctx = FIX / "contexts" / f"{args['task']}-{args['run']}-{args['kind']}-{args.get('attempt', 0)}"
        ctx.mkdir(parents=True, exist_ok=True)
        (ctx / "context.json").write_text(json.dumps(body))
        return {"context": str(ctx)}
    if op == "run-agent":
        return run_agent(args)
    if op == "run-integrator":
        return run_integrator(args)


def run_agent(args):
    role, ctx = args["role"], Path(args["context"])
    with locked() as state:
        n = bump(state, f"agent/{role}") - 1
    plan = (SCENARIO.get("agent", {}).get(role, []) + [{}] * (n + 1))[n]
    start = time.time()
    hang = plan.get("hang", 0)
    timed_out = hang > float(args["timeout"]) and not plan.get("ignore_timeout")
    time.sleep(float(args["timeout"]) if timed_out else hang)
    if not timed_out:
        write_tree(ctx / "work", plan.get("edits", {f"{role}.txt": f"{role} run {n + 1}"}))
    with locked() as state:
        state["agent_spans"].append({"role": role, "start": start, "end": time.time()})
    return {"exit_status": None if timed_out else plan.get("exit_status", 0),
            "timed_out": timed_out, "output": plan.get("output", f"{role} output"),
            "transcript": str(ctx / "transcript.jsonl")}


def run_integrator(args):
    ctx = Path(args["context"])
    with locked() as state:
        n = bump(state, "integrator") - 1
    plan = (SCENARIO.get("integrator", []) + [{}] * (n + 1))[n]
    verdict = {"result": plan.get("result", "green")}
    output = plan.get("output", "suite green")
    if verdict["result"] == "red":
        if "failed_check" in plan:
            verdict["failed_check"] = plan["failed_check"]
        verdict["spec_output"] = plan.get("spec_output", "")
    else:
        base = read_tree(ctx / "base")
        merged = read_tree(ctx / "main")
        for role in ("implementor", "acceptance-writer"):
            tree = read_tree(ctx / role)
            merged.update({k: v for k, v in tree.items() if base.get(k) != v})
        write_tree(ctx / "result", merged)
    if (n + 1) in SCENARIO.get("main_moves_after_integrator", []):
        with locked() as state:
            files = dict(state["commits"][state["main"]])
            files["human.txt"] = "pushed by a human"
            state["main"] = new_commit(state, files)
    return {"exit_status": 0 if verdict["result"] == "green" else 1, "timed_out": False,
            "output": output, "verdict": verdict}


def do_records(op, args, body):
    with open(FIX / "records.jsonl", "a") as out:
        out.write(json.dumps({"stream": args["stream"], "run": args.get("run"), "event": body}) + "\n")
    return {}


if __name__ == "__main__":
    main()
