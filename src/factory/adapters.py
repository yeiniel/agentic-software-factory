"""Adapter ports: external executables called as `<command...> <op> [--arg value ...]`.

An optional JSON body goes on stdin; the result is a JSON object on stdout. A non-zero exit,
a timeout or unparseable output is an infrastructure error (AdapterError).
"""
import json
import subprocess


class AdapterError(Exception):
    pass


class Adapter:
    def __init__(self, name, command, timeout):
        self.name = name
        self.command = list(command)
        self.timeout = timeout

    def argv(self, op, args):
        argv = [*self.command, op]
        for key, value in args.items():
            argv += [f"--{key}", str(value)]
        return argv

    def call(self, op, body=None, deadline=None, **args):
        argv = self.argv(op, args)
        try:
            done = subprocess.run(argv, input=json.dumps(body) if body is not None else "",
                                  capture_output=True, text=True, timeout=deadline or self.timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise AdapterError(f"{self.name} {op}: {error}") from error
        if done.returncode != 0:
            raise AdapterError(f"{self.name} {op} exited {done.returncode}: {done.stderr.strip()}")
        try:
            return json.loads(done.stdout) if done.stdout.strip() else {}
        except json.JSONDecodeError as error:
            raise AdapterError(f"{self.name} {op}: invalid JSON on stdout: {error}") from error

    def stream(self, op, **args):
        """Start a long-running Adapter and yield its stdout as JSON lines."""
        process = subprocess.Popen(self.argv(op, args), stdout=subprocess.PIPE, text=True,
                                   stdin=subprocess.DEVNULL)
        try:
            for line in process.stdout:
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
