"""The Integrator's result files (`result`, `failed_check`, `spec_output`, `output`) as a verdict."""
from .adapters import AdapterError

CHECKS = ("specs-not-red", "conflict", "suite")


def read(files):
    """Validate the text of the Integrator's top-level result files; returns the verdict."""
    result = files.get("result", "").strip()
    if result not in ("green", "red"):
        raise AdapterError(f"the Integrator left a malformed verdict: result is {result!r}")
    if "output" not in files:
        raise AdapterError("the Integrator left no output")
    verdict = {"result": result, "output": files["output"]}
    if result == "red":
        check = files.get("failed_check", "").strip()
        if check not in CHECKS:
            raise AdapterError(f"the Integrator left a malformed verdict: failed_check is {check!r}")
        verdict.update(failed_check=check, spec_output=files.get("spec_output", ""))
    return verdict
