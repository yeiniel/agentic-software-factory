"""Role resources (instruction, skills, Integrator `run`) and prompt composition. Versioned with the core."""
from pathlib import Path

RESOURCES = Path(__file__).parent / "resources"

CHECK_AGAINST_TASK = ("If it is unclear whether the implementation or the spec is wrong, "
                      "check against the Task.")


def instruction(role):
    return (RESOURCES / "roles" / role / "instruction.md").read_text().strip()


def system_prompt(role):
    return (RESOURCES / "roles" / role / "system-prompt.md").read_text().strip()


def skills(role):
    return RESOURCES / "roles" / role / "skills"


INTEGRATOR_RUN = RESOURCES / "integrator" / "run"
VALIDATION_RUN = RESOURCES / "validation" / "run"

WHY_IT_FAILED = {
    "crashed": "Your previous attempt ended with an error.",
    "timed-out": "Your previous attempt ran out of time.",
    "specs-not-red": "Your specs passed on the unchanged code, so they do not test the Task.",
    "merge": "Your changes could not be merged onto the original code.",
    "conflict": "Your changes conflict with the other changes made for this Task.",
    "suite": "The acceptance suite failed on the combined changes.",
}
DISCARDED = "Your previous changes were discarded and you start again from the original code."


def truncate(text, cap):
    """Keep the tail of the output, where failures are reported."""
    if len(text) <= cap:
        return text
    return "[... output truncated ...]\n" + text[-cap:]


def feedback(kind, output, cap):
    """The Feedback after a failed attempt: why, that the changes are gone, then the raw output."""
    return f"{WHY_IT_FAILED[kind]}\n{DISCARDED}\n\n{truncate(output, cap)}"


def compose(role, task_prompt, feedback=None):
    parts = [instruction(role), "# Task\n" + task_prompt]
    if feedback:
        parts.append("# Feedback from the previous attempt\n" + feedback + "\n\n" + CHECK_AGAINST_TASK)
    return "\n\n".join(parts)
