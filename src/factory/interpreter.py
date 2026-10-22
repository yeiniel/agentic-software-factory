"""Interprets a Graph for one Task at a time (ADR 0020, spec 0008).

The core knows two kinds of Activity, an agentic one that runs a named role and a deterministic one that runs a named
script, plus loops, parallel regions and the effects it alone performs. Everything else is in the Graph.
"""

import hashlib
import secrets
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field

from . import verdict as verdicts
from .adapters import Adapter, AdapterError, Json
from .contexts import Context, ContextStore
from .graph import Graph
from .prompts import compose, render


def trace_id(task: str) -> str:
    """One trace per Task: 32 hex characters derived from the Task id, stable across Factory restarts."""
    return hashlib.sha256(task.encode()).hexdigest()[:32]


class Span:
    """A started-then-finished stretch of work; `outcome` is set by the code it wraps."""

    def __init__(self, trace: str) -> None:
        self.id = secrets.token_hex(8)
        self.trace = trace
        self.outcome = "ok"

    @property
    def traceparent(self) -> str:
        return f"00-{self.trace}-{self.id}-01"


@dataclass
class Outcome:
    """How a state ended: the transition its Graph takes for it, and what it was about."""

    transition: Json
    check: str  # the failed check, or the trigger's name
    output: str
    green: bool = False  # the publish that advanced `main`
    loop: str | None = None  # the loop that ran out of attempts
    said: bool = False  # the Records already say so
    data: Json = field(default_factory=Json)

    @property
    def succeeded(self) -> bool:
        return self.transition["to"] == "$exit"

    def summary(self) -> Json:
        """The Run's outcome as the Records and the history carry it."""
        if self.green:
            return {"result": "green", "output": self.output, **self.data}
        extra = {"loop": self.loop} if self.loop else {}
        return {"result": "red", "failed_check": self.check, "output": self.output, **extra}


class TaskRunner:
    def __init__(self, adapters: dict[str, Adapter], config: Json, contexts: ContextStore, graph: Graph) -> None:
        self.a = adapters
        self.config = config
        self.contexts = contexts
        self.graph = graph

    def execute(self, task: str, repo: str) -> None:
        Execution(self, task, repo).go()


class Execution:
    """One Task against the Graph, from `task-received` to its last status."""

    def __init__(self, runner: TaskRunner, task: str, repo: str) -> None:
        self.runner, self.task, self.repo = runner, task, repo
        self.a, self.config, self.graph = runner.a, runner.config, runner.graph
        self.history: list[Json] = []
        self.logs: dict[str, list[Json]] = {}  # loop -> its attempts in the current Run
        self.run = 0  # the number of the current Run
        self.base = ""
        self.prompt = ""
        self.succeeded: set[str] = set()  # loops kept when an enclosing loop enters again
        self.pending: dict[str, str] = {}  # role -> the Feedback its next attempt starts with
        self.ran: set[str] = set()  # roles whose Run Context exists
        self.report = ""  # the output of the last Activity that was green

    def go(self) -> None:
        try:
            self.record("task-received", None, repo=self.repo, graph=self.graph.version)
            self.prompt = self.a["task-store"].call("get-prompt", task=self.task)["prompt"]
            self.base = self.a["repo-host"].call("main-head", repo=self.repo)["commit"]
            for state in self.graph.states.values():
                if state["type"] == "agentic":
                    name = self.branch(state["output"]["branch"])
                    self.a["repo-host"].call("create-branch", repo=self.repo, name=name, base=self.base)
            outcome = self.run_loop(self.graph.start)
            status = self.graph.states[outcome.transition["to"]]
            if status["status"] == "done":
                self.set_status("done", {"commit": outcome.data["commit"]})
            else:
                self.set_status("blocked", {"history": self.history}, reason=status["reason"])
        except Exception as error:  # noqa: BLE001  # an Adapter error or a malformed Adapter reply
            self.infrastructure_error(error)

    def infrastructure_error(self, error: Exception) -> None:
        """Visible failure that does not consume a Run toward the cap."""
        data: Json = {"error": str(error), "runs_used": len(self.history)}
        reason = self.graph.states[self.graph.error]["reason"]
        try:
            self.record("infrastructure-error", None, **data)
            self.set_status("blocked", {"reason": reason, **data, "history": self.history}, reason=reason)
        except AdapterError as reporting:
            print(f"could not report infrastructure error for {self.task}: {reporting}", file=sys.stderr)

    def branch(self, name: str) -> str:
        return f"factory/{self.task}/{name}"

    def record(self, kind: str, run: int | None, **data: object) -> None:
        body = {"kind": kind, "run": run, "trace": trace_id(self.task), **data}
        self.a["records"].call("append", body=body, stream=f"task/{self.task}", run=run)

    @contextmanager
    def span(self, kind: str, name: str, parent: str | None, **attributes: object) -> Generator[Span]:
        """Emit `started` and, however the block ends, `finished` with its duration and outcome."""
        span = Span(trace_id(self.task))
        fields = {"id": span.id, "parent": parent, "span": kind, "name": name, **attributes}
        self.record("started", self.run, **fields)
        began = time.monotonic()
        try:
            yield span
        except BaseException:
            span.outcome = "error"
            raise
        finally:
            self.record(
                "finished", self.run, **fields, duration=round(time.monotonic() - began, 3), outcome=span.outcome
            )

    def set_status(self, status: str, body: Json | None = None, reason: str | None = None) -> None:
        """Write a status to the Task Store, and record it so the Console never queries the store."""
        self.a["task-store"].call("set-status", task=self.task, status=status, body=body)
        extra: Json = {k: v for k, v in {"reason": reason, "commit": (body or {}).get("commit")}.items() if v}
        self.record("task-status", None, status=status, **extra)

    # -- the Graph's control flow

    def roles(self, name: str) -> list[str]:
        """The roles that run in a state."""
        state = self.graph.states[name]
        if state["type"] == "agentic":
            return [state["role"]]
        children = [c for c in [*state.get("contains", []), *state.get("regions", [])] if c not in self.succeeded]
        return [role for child in children for role in self.roles(child)]

    def transition(self, name: str, trigger: str) -> Json:
        """The transition a state takes on a trigger; `red` covers every failed check."""
        transitions = {t["on"]: t for t in self.graph.states[name]["transitions"]}
        return transitions.get(trigger) or transitions[trigger.split(":", maxsplit=1)[0]]

    def run_loop(self, name: str) -> Outcome:
        """The start loop: each attempt is a Run, the body from its entry until it leaves."""
        loop = self.graph.states[name]
        last = ""
        for number in range(1, loop["attempts"] + 1):
            self.run, self.logs = number, {}
            roles = self.roles(name)
            started = {role: self.pending.get(role) for role in roles}
            self.set_status("running")
            self.record("run-started", number, roles=roles)
            with self.span("run", str(number), None) as run_span:
                outcome = self.drive(loop, run_span.id, 0)
                summary = outcome.summary()
                run_span.outcome = summary["result"]
                self.history.append(
                    {"run": number, "roles": roles, "feedback": started, "attempts": self.logs, "outcome": summary}
                )
                self.record("run-finished", number, outcome=summary)
            if outcome.transition["to"] != name:
                return outcome
            last = outcome.output
            if number < loop["attempts"] and self.apply(outcome):
                self.record("feedback", number, feedback=dict(self.pending))
        return Outcome(self.transition(name, "exhausted"), "max-runs", last)

    def drive(self, loop: Json, parent: str, attempt: int) -> Outcome:
        """Follow the transitions from the loop's entry until one leaves the body: through `$exit`, or elsewhere."""
        current = loop["entry"]
        while True:
            outcome = self.noted(self.execute(current, parent, attempt))
            if outcome.transition["to"] not in loop["contains"]:
                return outcome
            current = outcome.transition["to"]

    def execute(self, name: str, parent: str, attempt: int) -> Outcome:
        state = self.graph.states[name]
        match state["type"]:
            case "loop":
                return self.nested_loop(name, state, parent)
            case "parallel":
                return self.parallel(name, state, parent, attempt)
            case "agentic":
                return self.agentic(name, state, parent)
            case "deterministic":
                return self.deterministic(name, state, parent, attempt)
            case _:
                return self.publish(name, state, parent)

    def nested_loop(self, name: str, loop: Json, parent: str) -> Outcome:
        """The body again and again until it succeeds or the attempts are spent; the budget is fresh on each entry."""
        log: list[Json] = []
        self.logs[name] = log
        last = ""
        with self.span("loop", name, parent) as loop_span:
            loop_span.outcome = "exhausted"
            for number in range(1, loop["attempts"] + 1):
                with self.span("attempt", str(number), loop_span.id) as at:
                    outcome = self.drive(loop, at.id, number)
                    at.outcome = "green" if outcome.succeeded else outcome.check
                log.append({"attempt": number, "result": at.outcome})
                self.record("attempt", self.run, loop=name, attempt=number, result=at.outcome)
                if outcome.succeeded:
                    loop_span.outcome = "succeeded"
                    self.succeeded.add(name)
                    return outcome
                if outcome.transition["to"] != name:  # not a retry: the Graph sends it somewhere else
                    loop_span.outcome = "left"
                    return outcome
                last = outcome.output
                text = self.apply(outcome)
                if text and number < loop["attempts"]:
                    self.record("loop-feedback", self.run, loop=name, attempt=number, feedback=text)
        return Outcome(self.transition(name, "exhausted"), "loop-exhausted", last, loop=name)

    def noted(self, outcome: Outcome) -> Outcome:
        """Say it in the Records when an outcome is a loop that ran out of attempts, from the thread taking it up."""
        if outcome.loop and not outcome.said:
            self.record("loop-exhausted", self.run, loop=outcome.loop)
            outcome.said = True
        return outcome

    def apply(self, outcome: Outcome) -> str | None:
        """Take a retry: the loops it resets run again, and its Feedback, if any, waits for the role it is for."""
        self.succeeded.difference_update(outcome.transition.get("reset", ()))
        feedback = outcome.transition.get("feedback")
        if feedback is None:
            return None
        text = render(self.graph.read(feedback["message"]), outcome.check, outcome.output, self.config["feedback_cap"])
        self.pending[feedback["for"]] = text
        return text

    def parallel(self, name: str, state: Json, parent: str, attempt: int) -> Outcome:
        """Regions run together and join when all have succeeded."""
        regions = [r for r in state["regions"] if r not in self.succeeded]
        with ThreadPoolExecutor(max(1, len(regions))) as pool:
            outcomes = [f.result() for f in [pool.submit(self.execute, r, parent, attempt) for r in regions]]
        left = next((o for o in outcomes if not o.succeeded), None)  # the first region, in the Graph's order
        return self.noted(left) if left else Outcome(self.transition(name, "green"), "green", "")

    # -- the Activities

    def timeout(self, state: Json) -> float:
        setting = state["timeout"]
        return self.config[setting] if isinstance(setting, str) else setting

    def run_environment(self, kind: str, ctx: Context, timeout: float, traceparent: str | None = None) -> Json:
        """The one Runner operation: an Environment on a Run Context."""
        build = self.config["build_timeout"]
        return self.a["runner"].call(
            "run",
            type=kind,
            context=ctx,
            timeout=timeout,
            build_timeout=build,
            traceparent=traceparent,
            deadline=timeout + build + self.config["adapter_grace"],
        )

    def agentic(self, name: str, state: Json, parent: str) -> Outcome:
        a, role = self.a, state["role"]
        branch = self.branch(state["output"]["branch"])
        text = compose(
            state["prompt"], self.graph.read(state["instruction"]), self.prompt, self.pending.pop(role, None)
        )
        with self.span("activity", "assemble", parent):
            if role in self.ran:  # a retry: the code starts again from the base
                a["repo-host"].call("create-branch", repo=self.repo, name=branch, base=self.base)
            if role in self.ran and state["session"] == "resume":  # the Pi session in the Context is kept
                ctx = self.runner.contexts.get(self.task, role)
                ctx.write("prompt", text)
                ctx.remove("cwd")
            else:
                ctx = self.runner.contexts.create(self.task, role)
                ctx.write("prompt", text)
                ctx.write("system-prompt", self.graph.read(state["system-prompt"]))
                ctx.copy(self.graph.folder / state["skills"], "skills")
            self.ran.add(role)
            workspace = state["workspace"]
            source = branch if workspace == "base" else self.branch(workspace["branch-of"])
            a["repo-host"].call("checkout", repo=self.repo, branch=source, dest=ctx.path("cwd"))
        with self.span("activity", "agent", parent, role=role) as activity:
            result = self.run_environment("agentic", ctx, self.timeout(state), activity.traceparent)
            self.record("agent", self.run, role=role, **result)
            recorded = a["repo-host"].call("record", repo=self.repo, branch=branch, from_=ctx.path("cwd"))
            self.record("branch-recorded", self.run, role=role, branch=branch, **recorded)
            if result["timed_out"]:
                activity.outcome = "timed-out"
                return Outcome(self.transition(name, "timed-out"), "timed-out", "Timed out.")
            if result["exit_status"]:
                activity.outcome = "crashed"
                return Outcome(self.transition(name, "crashed"), "crashed", result["output"])
        return Outcome(self.transition(name, "green"), "green", "")

    def deterministic(self, name: str, state: Json, parent: str, attempt: int) -> Outcome:
        a = self.a
        with self.span("activity", "assemble", parent):
            ctx = self.runner.contexts.create(self.task, f"{name}-{self.run}-{attempt}")
            ctx.copy(self.graph.folder / state["script"], "run", executable=True)
            ctx.mkdir("out")
            for folder, source in state["inputs"].items():
                where = ctx.path(f"cwd/{folder}")
                if source == "base":
                    a["repo-host"].call("checkout", repo=self.repo, commit=self.base, dest=where)
                else:
                    a["repo-host"].call("checkout", repo=self.repo, branch=self.branch(source["branch-of"]), dest=where)
            containerfile = ctx.path(f"cwd/{state['environment']}/Containerfile")
            if containerfile.is_file():  # the Environment is the named input's
                ctx.copy(containerfile, "cwd/Containerfile")
        with self.span("activity", name, parent) as activity:
            result = self.run_environment("deterministic", ctx, self.timeout(state))
            self.record(name, self.run, **result)
            if result["timed_out"]:
                verdict = {"result": "red", "failed_check": "timed-out", "output": "Timed out."}
            else:
                verdict = verdicts.read(result["files"], tuple(state["checks"]))
            activity.outcome = "green" if verdict["result"] == "green" else verdict["failed_check"]
        if verdict["result"] == "red":
            check = verdict["failed_check"]
            trigger = "timed-out" if check == "timed-out" else f"red:{check}"
            return Outcome(self.transition(name, trigger), check, verdict["output"])
        self.report = verdict["output"]
        if "output" in state:
            branch = self.branch(state["output"]["branch"])
            a["repo-host"].call("record", repo=self.repo, branch=branch, from_=ctx.path(state["output"]["path"]))
        return Outcome(self.transition(name, "green"), "green", "")

    def publish(self, name: str, state: Json, parent: str) -> Outcome:
        with self.span("activity", "publish", parent) as activity:
            branch = self.branch(state["branch"])
            pushed = self.a["repo-host"].call("fast-forward-main", repo=self.repo, branch=branch, expect_main=self.base)
            self.record("fast-forward", self.run, **pushed)
            activity.outcome = "advanced" if pushed["advanced"] else "main-moved"
        if pushed["advanced"]:
            return Outcome(
                self.transition(name, "advanced"), "advanced", self.report, green=True, data={"commit": pushed["head"]}
            )
        return Outcome(self.transition(name, "main-moved"), "main-moved", "")
