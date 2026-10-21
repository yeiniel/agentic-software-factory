"""Runner Adapter: runs an Environment on a Run Context as a Podman container through the host's socket.

  run --type agentic|deterministic --context DIR --timeout S [--build-timeout S] [--traceparent T]

The Context is mounted at /ctx (the same path on the host and in the Factory container, since mounts are
resolved by the host). The image is built from `cwd/Containerfile` (see _environment.py). The Runner knows
no roles and none of the input or result names; its own state is `session/` in an agentic Context.

  agentic: working directory /ctx/cwd, on $RUNNER_AGENT_NETWORK (which must reach the model server),
  configured by ASF_MODEL_ENDPOINT, ASF_MODEL_NAME and ASF_MODEL_CONTEXT_WINDOW. No git credentials are
  passed. Pi reads /ctx/prompt and /ctx/skills and keeps its session in /ctx/session. While it runs, new
  session entries are forwarded to $OTEL_EXPORTER_OTLP_ENDPOINT, linked to the optional --traceparent; the
  result's `usage` counts the turns, tool calls and tokens of this run.
  deterministic: no network; executes /ctx/run in /ctx/cwd. Its results are the files in /ctx/out.
"""
import os
import subprocess
import time
from pathlib import Path

from . import common as _common
from . import environment as _environment
from . import session as _session
from .common import Failure, podman, require_env, slug

MODEL_ENV = ("ASF_MODEL_ENDPOINT", "ASF_MODEL_NAME", "ASF_MODEL_CONTEXT_WINDOW")
FILE_CAP = 1_000_000  # characters of each result file; the tail is kept, where failures are reported
DEFAULT_BUILD_TIMEOUT = 900


def run_container(name, args, timeout):
    """Run a container to completion or kill it at the deadline; returns (status, output, timed_out)."""
    process = subprocess.Popen([os.environ.get("PODMAN", "podman"), "run", "--rm", "--name", name,
                                "--security-opt", "label=disable", *args],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output, False
    except subprocess.TimeoutExpired:
        podman("rm", "-f", "-t", "0", name, check=False)
        output, _ = process.communicate()
        return None, output or "", True


def container_name(ctx):
    return f"asf-{slug(ctx.parent.name + '-' + ctx.name)}-{os.getpid()}"


def read_files(out):
    files = {}
    for path in sorted(out.glob("*")) if out.is_dir() else []:
        if path.is_file() and not path.is_symlink():
            text = path.read_text(errors="replace")
            files[path.name] = text if len(text) <= FILE_CAP else "[... truncated ...]\n" + text[-FILE_CAP:]
    return files


def run(a):
    kind, ctx = a["type"], Path(a["context"]).resolve()
    if kind not in ("agentic", "deterministic"):
        raise Failure(f"unknown type {kind!r}")
    timeout = float(a["timeout"])
    image = _environment.image(ctx / "cwd", kind == "agentic", float(a.get("build-timeout", DEFAULT_BUILD_TIMEOUT)))
    name = container_name(ctx)
    if kind == "deterministic":
        status, output, timed_out = run_container(
            name, ["--network", "none", "-v", f"{ctx}:/ctx", "-w", "/ctx/cwd", "--entrypoint", "/ctx/run", image],
            timeout)
        return {"exit_status": status, "timed_out": timed_out, "output": output,
                "files": read_files(ctx / "out")}
    session = ctx / "session"
    session.mkdir(exist_ok=True)
    started = time.time()
    env = [x for var in MODEL_ENV for x in ("-e", f"{var}={require_env(var)}")]
    network = ["--network", os.environ["RUNNER_AGENT_NETWORK"]] if os.environ.get("RUNNER_AGENT_NETWORK") else []
    watched = _session.Session(session)
    with _session.Forwarder(watched, a.get("traceparent")):
        status, output, timed_out = run_container(name, [*network, "-v", f"{ctx}:/ctx", *env, image], timeout)
    watched.poll()  # whatever the last interval left, for the counts
    transcripts = sorted((p for p in session.rglob("*.jsonl") if p.stat().st_mtime >= started),
                         key=lambda p: p.stat().st_mtime)  # this run's, not an earlier one's
    result = {"exit_status": status, "timed_out": timed_out, "output": output,
              "transcript": str(transcripts[-1]) if transcripts else ""}
    if watched.usage():
        result["usage"] = watched.usage()
    return result



def main():
    _common.main({"run": run})
