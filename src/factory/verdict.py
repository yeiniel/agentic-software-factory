"""The result files (`result`, `failed_check`, `output`) of the Integrator and of Acceptance Test Validation."""
from .adapters import AdapterError

VALIDATION_CHECKS = ("specs-not-red", "merge")
INTEGRATION_CHECKS = ("conflict", "suite")


def read(files, checks=INTEGRATION_CHECKS):
    """Validate the text of a deterministic process's top-level result files; returns the verdict."""
    result = files.get("result", "").strip()
    if result not in ("green", "red"):
        raise AdapterError(f"a deterministic process left a malformed verdict: result is {result!r}")
    if "output" not in files:
        raise AdapterError("a deterministic process left no output")
    verdict = {"result": result, "output": files["output"]}
    if result == "red":
        check = files.get("failed_check", "").strip()
        if check not in checks:
            raise AdapterError(f"a deterministic process left a malformed verdict: failed_check is {check!r}")
        verdict["failed_check"] = check
    return verdict
