"""The fixed graph of Activities for a Run, and the nested retry loops around it (ADR 0016)."""
import sys
from concurrent.futures import ThreadPoolExecutor

from . import verdict as verdicts
from .adapters import AdapterError
from .prompts import INTEGRATOR_RUN, VALIDATION_RUN, compose, feedback, skills, system_prompt

IMPLEMENTOR, WRITER = "implementor", "acceptance-writer"
ROLES = (IMPLEMENTOR, WRITER)
LOOPS = {WRITER: "writer", IMPLEMENTOR: "implementor"}  # the role each loop runs
MAX_INTEGRATIONS = 5  # fresh Integrator runs when `main` keeps moving


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
        feedbacks = {r: None for r in ROLES}  # the Feedback a loop starts with when a Run enters it
        succeeded, ran = set(), set()
        while True:
            run = len(history) + 1
            roles = [r for r in ROLES if r not in succeeded]
            a["task-store"].call("set-status", task=task, status="running")
            self.record(task, "run-started", run, roles=roles)
            loops = {WRITER: self.writer_loop, IMPLEMENTOR: self.implementor_loop}
            with ThreadPoolExecutor(len(roles)) as pool:
                futures = {r: pool.submit(loops[r], task, repo, run, branches[r], base, prompt,
                                          feedbacks[r], ran) for r in roles}
                results = {r: f.result() for r, f in futures.items()}
            attempts = {LOOPS[r]: res["attempts"] for r, res in results.items()}
            exhausted = [r for r in roles if not results[r]["succeeded"]]
            if exhausted:
                role = exhausted[0]
                self.record(task, "loop-exhausted", run, loop=LOOPS[role])
                outcome = {"result": "red", "failed_check": "loop-exhausted", "loop": LOOPS[role],
                           "output": results[role]["failure"]}
            else:
                succeeded.update(roles)
                outcome = self.integrate(task, repo, run, base, branches)
            history.append({"run": run, "roles": roles, "feedback": dict(feedbacks), "attempts": attempts,
                            "outcome": outcome})
            self.record(task, "run-finished", run, outcome=outcome)
            if outcome["result"] == "green":
                a["task-store"].call("set-status", task=task, status="done",
                                     body={"commit": outcome["commit"]})
                return
            if exhausted or len(history) >= self.config["max_runs"]:
                a["task-store"].call("set-status", task=task, status="blocked",
                                     body={"history": history})
                return
            # a failed integration retriggers only the Implementor; the Writer's validated branch stays
            succeeded.discard(IMPLEMENTOR)
            feedbacks = {IMPLEMENTOR: feedback(outcome["failed_check"], outcome["output"], cap)}
            self.record(task, "feedback", run, feedback=feedbacks)

    def attempts(self, task, run, loop, budget, first, step):
        """Run `step(attempt, feedback)` until it returns None (success) or the budget is spent."""
        log, text = [], first
        for number in range(1, budget + 1):
            failure = step(number, text)  # (kind, output) or None
            log.append({"attempt": number, "result": "green" if failure is None else failure[0]})
            self.record(task, "attempt", run, loop=loop, attempt=number, result=log[-1]["result"])
            if failure is None:
                return {"succeeded": True, "attempts": log}
            text = feedback(*failure, self.config["feedback_cap"])
        return {"succeeded": False, "attempts": log, "failure": failure[1]}

    def agent_failure(self, result):
        if result["timed_out"]:
            return "timed-out", "Timed out."
        if result["exit_status"]:
            return "crashed", result["output"]

    def writer_loop(self, task, repo, run, branch, base, prompt, first, ran):
        def step(number, text):
            result = self.agent(task, repo, run, WRITER, branch, base, prompt, text, ran)
            failure = self.agent_failure(result)
            if failure:
                return failure
            verdict = self.validate(task, repo, run, number, base, branch)
            if verdict["result"] == "red":
                return verdict["failed_check"], verdict["output"]
        return self.attempts(task, run, "writer", self.config["writer_attempts"], first, step)

    def implementor_loop(self, task, repo, run, branch, base, prompt, first, ran):
        def step(number, text):
            result = self.agent(task, repo, run, IMPLEMENTOR, branch, base, prompt, text, ran)
            return self.agent_failure(result)
        return self.attempts(task, run, "implementor", self.config["implementor_attempts"], first, step)

    def run_environment(self, kind, ctx, timeout):
        """The one Runner operation: an Environment on a Run Context."""
        build = self.config["build_timeout"]
        return self.a["runner"].call("run", type=kind, context=ctx, timeout=timeout,
                                     **{"build-timeout": build},
                                     deadline=timeout + build + self.config["adapter_grace"])

    def agent(self, task, repo, run, role, branch, base, prompt, feedback_text, ran):
        a = self.a
        text = compose(role, prompt, feedback_text)
        if role in ran:  # a retry: the Pi session in the Context is kept, the code starts again from the base
            ctx = self.contexts.get(task, role)
            ctx.write("prompt", text)
            ctx.remove("cwd")
            a["repo-host"].call("create-branch", repo=repo, name=branch, base=base)
        else:
            ctx = self.contexts.create(task, role)
            ctx.write("prompt", text)
            ctx.write("system-prompt", system_prompt(role))
            ctx.copy(skills(role), "skills")
            ran.add(role)
        a["repo-host"].call("checkout", repo=repo, branch=branch, dest=ctx.path("cwd"))
        result = self.run_environment("agentic", ctx, self.config["agent_timeout"])
        self.record(task, "agent", run, role=role, **result)
        recorded = a["repo-host"].call("record", repo=repo, branch=branch, **{"from": ctx.path("cwd")})
        self.record(task, "branch-recorded", run, role=role, branch=branch, **recorded)
        return result

    def validate(self, task, repo, run, attempt, base, branch):
        """Acceptance Test Validation: green when the new specs fail on the unchanged repository."""
        a = self.a
        ctx = self.contexts.create(task, f"validate-{run}-{attempt}")
        ctx.copy(VALIDATION_RUN, "run", executable=True)
        ctx.mkdir("out")
        a["repo-host"].call("checkout", repo=repo, commit=base, dest=ctx.path("cwd/base"))
        a["repo-host"].call("checkout", repo=repo, branch=branch, dest=ctx.path(f"cwd/{WRITER}"))
        if ctx.path("cwd/base/Containerfile").is_file():
            ctx.copy(ctx.path("cwd/base/Containerfile"), "cwd/Containerfile")
        result = self.run_environment("deterministic", ctx, self.config["integrator_timeout"])
        self.record(task, "validation", run, **result)
        if result["timed_out"]:
            return {"result": "red", "failed_check": "timed-out", "output": "Timed out."}
        return verdicts.read(result["files"], verdicts.VALIDATION_CHECKS)

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
                return {"result": "red", "failed_check": "timed-out", "output": "Timed out."}
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
