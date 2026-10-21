"""Records Adapter: appends each event to a JSON-lines file under $RECORDS_DIR, outside the repo.

append --stream S [--run N]   body: one JSON event   ->  $RECORDS_DIR/<S>.jsonl
"""

import json
import re
import time
from pathlib import Path

from . import common as _common
from .common import Args, Json, RequestError

STREAM = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")


def append(args: Args) -> Json:
    stream = args.get("stream", "")
    if not STREAM.fullmatch(stream) or any(part in ("", ".", "..") for part in stream.split("/")):
        raise RequestError(f"invalid stream {stream!r}")
    path = Path(_common.require_env("RECORDS_DIR")) / (stream + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"time": time.time(), "run": args.get("run"), "event": _common.read_body()})
    with path.open("a") as out:
        out.write(line + "\n")
    return {}


def main() -> None:
    _common.main({"append": append})
