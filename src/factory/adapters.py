"""Adapter ports: external executables called as `<command...> <op> [--arg value ...]`.

An optional JSON body goes on stdin; the result is a JSON object on stdout. A non-zero exit,
a timeout or unparseable output is an infrastructure error (AdapterError).
"""

import json
import subprocess
from collections.abc import Iterator, Sequence
from typing import IO, Any, cast

Json = dict[str, Any]


class AdapterError(Exception):
    pass


class Adapter:
    def __init__(self, name: str, command: Sequence[str], timeout: float) -> None:
        self.name = name
        self.command = list(command)
        self.timeout = timeout

    def argv(self, op: str, args: dict[str, object]) -> list[str]:
        argv = [*self.command, op]
        for key, value in args.items():
            if value is None:  # an optional argument that was not given
                continue
            argv += [f"--{key.rstrip('_').replace('_', '-')}", str(value)]
        return argv

    def call(self, op: str, body: Json | None = None, deadline: float | None = None, **args: object) -> Json:
        argv = self.argv(op, args)
        try:
            done = subprocess.run(
                argv,
                input=json.dumps(body) if body is not None else "",
                capture_output=True,
                text=True,
                timeout=deadline or self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdapterError(f"{self.name} {op}: {error}") from error
        if done.returncode != 0:
            raise AdapterError(f"{self.name} {op} exited {done.returncode}: {done.stderr.strip()}")
        try:
            return json.loads(done.stdout) if done.stdout.strip() else {}
        except json.JSONDecodeError as error:
            raise AdapterError(f"{self.name} {op}: invalid JSON on stdout: {error}") from error

    def stream(self, op: str, **args: object) -> Iterator[Json]:
        """Start a long-running Adapter and yield its stdout as JSON lines."""
        process = subprocess.Popen(self.argv(op, args), stdout=subprocess.PIPE, text=True, stdin=subprocess.DEVNULL)
        stdout = cast("IO[str]", process.stdout)  # stdout=PIPE
        try:
            for line in stdout:
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as error:
                        raise AdapterError(f"{self.name} {op}: invalid JSON line: {error}") from error
            if process.wait() != 0:
                raise AdapterError(f"{self.name} {op} exited {process.returncode}")
        finally:
            if process.poll() is None:
                process.kill()
