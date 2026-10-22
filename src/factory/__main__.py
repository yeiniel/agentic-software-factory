import argparse
import json
import os
from pathlib import Path

from .adapters import Adapter, Json
from .factory import serve
from .graph import RESOURCES, GraphError, load

DEFAULTS = {
    "adapter_timeout": 60,
    "adapter_grace": 30,
    "agent_timeout": 3600,
    "integrator_timeout": 1800,
    "build_timeout": 900,
    "max_runs": 2,
    "writer_attempts": 2,
    "implementor_attempts": 2,
    "feedback_cap": 8000,
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--config", required=True)
    config: Json = {**DEFAULTS, **json.loads(Path(parser.parse_args().config).read_text())}
    # the Runner mounts these paths into Environments, so both must see the same one
    config.setdefault(
        "context_root",
        str((Path(os.environ.get("RUNNER_ROOT") or Path.home() / ".local/share/asf/runner") / "contexts").resolve()),
    )
    version = config.get("graph_version") or os.environ.get("ASF_GRAPH_VERSION") or "unversioned"
    try:
        graph = load(
            Path(config.get("graph", RESOURCES)), version, config
        )  # checked once: no start on an invalid Graph
    except GraphError as error:
        raise SystemExit(f"factory: invalid Graph: {error}") from error
    adapters = {name: Adapter(name, command, config["adapter_timeout"]) for name, command in config["adapters"].items()}
    serve(adapters, config, graph)


main()
