"""The fixed graph of Activities for a Run, and the retry accounting around it."""
import sys
from concurrent.futures import ThreadPoolExecutor

from .adapters import AdapterError
from .prompts import compose, truncate

IMPLEMENTOR, WRITER = "implementor", "acceptance-writer"
ROLES = (IMPLEMENTOR, WRITER)
MAX_INTEGRATIONS = 5  # fresh Integrator runs when `main` keeps moving


def blame(outcome, history, cap):
    """Which roles to retrigger, with their Feedback. Replaceable (ADR 0003, 0004)."""
    output = truncate(outcome["output"], cap)
    check = outcome["failed_check"]
    if check == "specs-not-red":
        return {WRITER: truncate(outcome.get("spec_output") or outcome["output"], cap)}
    if check == "agent":
        return {role: truncate(text, cap) for role, text in outcome["failures"].items()}
    roles = {IMPLEMENTOR: output}
    if len(history) >= 2:
        previous = history[-2]
        if (IMPLEMENTOR in previous["roles"] and previous["outcome"].get("output") == outcome["output"]
                and check == "suite"):
            # the writer gets its own run output only, never the Implementor's side
            roles[WRITER] = truncate(outcome.get("spec_output") or "No spec output available.", cap)
    return roles


class TaskRunner:
    def __init__(self, adapters, config):
        self.a = adapters
        self.config = config

    def record(self, task, kind, run=None, **data):
        args = {"stream": f"task/{task}"}
        if run is not None:
            args["run"] = run
        self.a["records"].call("append", body={"kind": kind, "run": run, **data}, **args)

    def execute(self, task, repo):
        history = []
        try:
            self.attempt(task, repo, history)
        except Exception as error:  # an Adapter error or a malformed Adapter reply
            self.infrastructure_error(task, history, error)

    def infrastructure_error(self, task, history, error):
        """Visible failure that does not consume a Run toward the cap."""
        data = {"error": str(error), "runs_used": len(history)}
        try:
            self.record(task, "infrastructure-error", **data)
            self.a["task-store"].call("set-status", task=task, status="blocked",
                                      body={"reason": "infrastructure", **data, "history": history})
        except AdapterError as reporting:
            print(f"could not report infrastructure error for {task}: {reporting}", file=sys.stderr)

    def attempt(self, task, repo, history):
        a, cap = self.a, self.config["feedback_cap"]
        prompt = a["task-store"].call("get-prompt", task=task)["prompt"]
        base = a["repo-host"].call("main-head", repo=repo)["commit"]
        branches = {r: f"factory/{task}/{r}" for r in ROLES}
        for name in branches.values():
            a["repo-host"].call("create-branch", repo=repo, name=name, base=base)
        feedback = {r: None for r in ROLES}  # the roles to run, each with its Feedback
        ran = set()
        while True:
            run = len(history) + 1
            roles = list(feedback)
            a["task-store"].call("set-status", task=task, status="running")
            self.record(task, "run-started", run, roles=roles)
            with ThreadPoolExecutor(len(roles)) as pool:
                results = list(pool.map(
                    lambda r: self.agent(task, repo, run, r, branches[r], base, prompt,
                                         feedback[r], r in ran), roles))
            ran.update(roles)
            failures = {r: "Timed out." if res["timed_out"] else res["output"]
                        for r, res in zip(roles, results) if res["timed_out"] or res["exit_status"]}
            if failures:
                outcome = {"result": "red", "failed_check": "agent", "failures": failures,
                           "output": "\n".join(f"{r}: {t}" for r, t in failures.items())}
            else:
                outcome = self.integrate(task, repo, run, base, branches)
            history.append({"run": run, "roles": roles, "feedback": dict(feedback), "outcome": outcome})
            self.record(task, "run-finished", run, outcome=outcome)
            if outcome["result"] == "green":
                a["task-store"].call("set-status", task=task, status="done",
                                     body={"commit": outcome["commit"]})
                return
            if len(history) >= self.config["max_runs"]:
                a["task-store"].call("set-status", task=task, status="blocked",
                                     body={"history": history})
                return
            feedback = blame(outcome, history, cap)
            self.record(task, "feedback", run, feedback=feedback)

    def agent(self, task, repo, run, role, branch, base, prompt, feedback, resume):
        a = self.a
        image = a["environment-builder"].call("build", repo=repo, commit=base, purpose="agent")["image"]
        ctx = a["runner"].call("provision-context",
                               body={"prompt": compose(role, prompt, feedback), "resume": resume},
                               kind=role, task=task, run=run)["context"]
        a["repo-host"].call("checkout", repo=repo, branch=branch, dest=f"{ctx}/work")
        timeout = self.config["agent_timeout"]
        result = a["runner"].call("run-agent", image=image, context=ctx, task=task, role=role,
                                  timeout=timeout, deadline=timeout + self.config["adapter_grace"])
        self.record(task, "agent", run, role=role, **result)
        recorded = a["repo-host"].call("record", repo=repo, branch=branch, **{"from": f"{ctx}/work"})
        self.record(task, "branch-recorded", run, role=role, branch=branch, **recorded)
        return result

    def integrate(self, task, repo, run, base, branches):
        a = self.a
        for attempt in range(MAX_INTEGRATIONS):
            main = a["repo-host"].call("main-head", repo=repo)["commit"]
            image = a["environment-builder"].call("build", repo=repo, commit=main,
                                                  purpose="integrator")["image"]
            ctx = a["runner"].call("provision-context", kind="integrator", task=task, run=run,
                                   attempt=attempt)["context"]
            a["repo-host"].call("checkout", repo=repo, commit=base, dest=f"{ctx}/base")
            a["repo-host"].call("checkout", repo=repo, commit=main, dest=f"{ctx}/main")
            for role, name in branches.items():
                a["repo-host"].call("checkout", repo=repo, branch=name, dest=f"{ctx}/{role}")
            timeout = self.config["integrator_timeout"]
            result = a["runner"].call("run-integrator", image=image, context=ctx, timeout=timeout,
                                      deadline=timeout + self.config["adapter_grace"])
            self.record(task, "integrator", run, **result)
            if result["timed_out"]:
                return {"result": "red", "failed_check": "timeout", "output": "Timed out."}
            verdict = result["verdict"]
            if verdict["result"] not in ("green", "red") or (
                    verdict["result"] == "red" and "failed_check" not in verdict):
                raise AdapterError(f"run-integrator returned a malformed verdict: {verdict}")
            if verdict["result"] == "red":
                return {**verdict, "output": result["output"]}
            integrated = f"factory/{task}/integrated"
            a["repo-host"].call("record", repo=repo, branch=integrated, **{"from": f"{ctx}/result"})
            pushed = a["repo-host"].call("fast-forward-main", repo=repo, branch=integrated,
                                         **{"expect-main": main})
            self.record(task, "fast-forward", run, **pushed)
            if pushed["advanced"]:
                return {"result": "green", "output": result["output"], "commit": pushed["head"]}
        raise AdapterError("main kept moving; gave up integrating")

