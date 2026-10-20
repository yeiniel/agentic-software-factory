"""The Integrator's result files, as the core reads them."""
import pytest

from factory.adapters import AdapterError
from factory.verdict import read


def test_a_green_verdict_carries_the_acceptance_report():
    assert read({"result": "green\n", "output": "suite green\n"}) == {
        "result": "green", "output": "suite green\n"}


@pytest.mark.parametrize("check", ["specs-not-red", "conflict", "suite"])
def test_a_red_verdict_names_the_failed_check_and_the_spec_output(check):
    files = {"result": "red\n", "failed_check": f"{check}\n", "spec_output": "spec out", "output": "out"}
    assert read(files) == {"result": "red", "failed_check": check, "spec_output": "spec out", "output": "out"}


def test_a_red_verdict_without_spec_output_has_it_empty():
    files = {"result": "red", "failed_check": "conflict", "output": "CONFLICT"}
    assert read(files)["spec_output"] == ""


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
