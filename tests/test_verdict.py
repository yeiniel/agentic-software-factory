"""The Integrator's result files, as the core reads them."""
import pytest

from factory.adapters import AdapterError
from factory.verdict import VALIDATION_CHECKS, read


def test_a_green_verdict_carries_the_acceptance_report():
    assert read({"result": "green\n", "output": "suite green\n"}) == {
        "result": "green", "output": "suite green\n"}


@pytest.mark.parametrize("check", ["conflict", "suite"])
def test_a_red_integration_verdict_names_the_failed_check(check):
    files = {"result": "red\n", "failed_check": f"{check}\n", "output": "out"}
    assert read(files) == {"result": "red", "failed_check": check, "output": "out"}


@pytest.mark.parametrize("check", ["specs-not-red", "merge"])
def test_a_red_validation_verdict_names_the_failed_check(check):
    files = {"result": "red\n", "failed_check": f"{check}\n", "output": "out"}
    assert read(files, VALIDATION_CHECKS) == {"result": "red", "failed_check": check, "output": "out"}


def test_a_check_of_the_other_process_is_malformed():
    with pytest.raises(AdapterError):
        read({"result": "red", "failed_check": "specs-not-red", "output": "x"})
    with pytest.raises(AdapterError):
        read({"result": "red", "failed_check": "suite", "output": "x"}, VALIDATION_CHECKS)


@pytest.mark.parametrize("files", [
    {},                                                                    # no result at all
    {"output": "x"},                                                       # no result file
    {"result": "green"},                                                   # no output
    {"result": "maybe", "output": "x"},                                    # unknown result
    {"result": "red", "output": "x"},                                      # red without a failed check
    {"result": "red", "failed_check": "vibes", "output": "x"},             # unknown failed check
])
def test_malformed_files_are_an_infrastructure_error(files):
    with pytest.raises(AdapterError):
        read(files)
