import argparse
import json
import os
from pathlib import Path

from .adapters import Adapter
from .factory import serve

DEFAULTS = {"adapter_timeout": 60, "adapter_grace": 30, "agent_timeout": 1800, "integrator_timeout": 1800,
            "build_timeout": 900, "max_runs": 2,
            "writer_attempts": 2, "implementor_attempts": 2, "feedback_cap": 8000}


def main():
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--config", required=True)
    with open(parser.parse_args().config) as f:
        config = {**DEFAULTS, **json.load(f)}
    # the Runner mounts these paths into Environments, so both must see the same one
    config.setdefault("context_root", str((Path(os.environ.get("RUNNER_ROOT") or
                                                 Path.home() / ".local/share/asf/runner") / "contexts").resolve()))
    adapters = {name: Adapter(name, command, config["adapter_timeout"])
                for name, command in config["adapters"].items()}
    serve(adapters, config)


main()
