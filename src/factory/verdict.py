"""The result files (`result`, `failed_check`, `output`) of the Integrator and of Acceptance Test Validation."""

from .adapters import AdapterError


def read(files: dict[str, str], checks: tuple[str, ...]) -> dict[str, str]:
    """Validate a deterministic Activity's result files; `checks` are the failed checks its Graph state declares."""
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
