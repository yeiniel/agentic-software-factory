"""Records Adapter: appends each event to a JSON-lines file under $RECORDS_DIR, outside the repo.

  append --stream S [--run N]   body: one JSON event   ->  $RECORDS_DIR/<S>.jsonl
"""
import json
import os
import re
import time

from . import common as _common
from .common import Failure

STREAM = re.compile(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*")


def append(args):
    stream = args.get("stream", "")
    if not STREAM.fullmatch(stream) or any(part in ("", ".", "..") for part in stream.split("/")):
        raise Failure(f"invalid stream {stream!r}")
    path = os.path.join(_common.require_env("RECORDS_DIR"), stream + ".jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps({"time": time.time(), "run": args.get("run"), "event": _common.read_body()})
    with open(path, "a") as out:
        out.write(line + "\n")
    return {}



def main():
    _common.main({"append": append})
