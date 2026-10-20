"""The fixed graph of Activities for a Run, and the retry accounting around it."""
import sys
from concurrent.futures import ThreadPoolExecutor

from . import verdict as verdicts
from .adapters import AdapterError
from .prompts import INTEGRATOR_RUN, compose, skills, truncate

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
    def __init__(self, adapters, config, contexts):
        self.a = adapters
        self.config = config
        self.contexts = contexts

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

    def run_environment(self, kind, ctx, timeout):
        """The one Runner operation: an Environment on a Run Context."""
        build = self.config["build_timeout"]
        return self.a["runner"].call("run", type=kind, context=ctx, timeout=timeout,
                                     **{"build-timeout": build},
                                     deadline=timeout + build + self.config["adapter_grace"])

    def agent(self, task, repo, run, role, branch, base, prompt, feedback, resume):
        a = self.a
        text = compose(role, prompt, feedback)
        if resume:  # the Agent's Context lives across the Task's Runs and its cwd holds its last work
            ctx = self.contexts.get(task, role)
            ctx.write("prompt", text)
        else:
            ctx = self.contexts.create(task, role)
            ctx.write("prompt", text)
            ctx.copy(skills(role), "skills")
            a["repo-host"].call("checkout", repo=repo, branch=branch, dest=ctx.path("cwd"))
        result = self.run_environment("agentic", ctx, self.config["agent_timeout"])
        self.record(task, "agent", run, role=role, **result)
        recorded = a["repo-host"].call("record", repo=repo, branch=branch, **{"from": ctx.path("cwd")})
        self.record(task, "branch-recorded", run, role=role, branch=branch, **recorded)
        return result

    def integrate(self, task, repo, run, base, branches):
        a = self.a
        for attempt in range(MAX_INTEGRATIONS):
            main = a["repo-host"].call("main-head", repo=repo)["commit"]
            ctx = self.contexts.create(task, f"integrate-{run}-{attempt}")
            ctx.copy(INTEGRATOR_RUN, "run", executable=True)
            ctx.mkdir("out")
            a["repo-host"].call("checkout", repo=repo, commit=base, dest=ctx.path("cwd/base"))
            a["repo-host"].call("checkout", repo=repo, commit=main, dest=ctx.path("cwd/main"))
            for role, name in branches.items():
                a["repo-host"].call("checkout", repo=repo, branch=name, dest=ctx.path(f"cwd/{role}"))
            if ctx.path("cwd/main/Containerfile").is_file():  # the Environment is main's
                ctx.copy(ctx.path("cwd/main/Containerfile"), "cwd/Containerfile")
            result = self.run_environment("deterministic", ctx, self.config["integrator_timeout"])
            self.record(task, "integrator", run, **result)
            if result["timed_out"]:
                return {"result": "red", "failed_check": "timeout", "output": "Timed out."}
            verdict = verdicts.read(result["files"])
            if verdict["result"] == "red":
                return verdict
            integrated = f"factory/{task}/integrated"
            a["repo-host"].call("record", repo=repo, branch=integrated, **{"from": ctx.path("out/integrated")})
            pushed = a["repo-host"].call("fast-forward-main", repo=repo, branch=integrated,
                                         **{"expect-main": main})
            self.record(task, "fast-forward", run, **pushed)
            if pushed["advanced"]:
                return {**verdict, "commit": pushed["head"]}
        raise AdapterError("main kept moving; gave up integrating")
