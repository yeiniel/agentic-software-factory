import argparse
import json

from .adapters import Adapter
from .factory import serve

DEFAULTS = {"adapter_timeout": 60, "adapter_grace": 30, "agent_timeout": 1800, "integrator_timeout": 1800,
            "max_runs": 2, "feedback_cap": 8000}


def main():
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--config", required=True)
    with open(parser.parse_args().config) as f:
        config = {**DEFAULTS, **json.load(f)}
    adapters = {name: Adapter(name, command, config["adapter_timeout"])
                for name, command in config["adapters"].items()}
    serve(adapters, config)


main()
