"""Role resources (instruction, skills, Integrator `run`) and prompt composition. Versioned with the core."""
from pathlib import Path

RESOURCES = Path(__file__).parent / "resources"

CHECK_AGAINST_TASK = ("If it is unclear whether the implementation or the spec is wrong, "
                      "check against the Task.")


def instruction(role):
    return (RESOURCES / "roles" / role / "instruction.md").read_text().strip()


def skills(role):
    return RESOURCES / "roles" / role / "skills"


INTEGRATOR_RUN = RESOURCES / "integrator" / "run"


def truncate(text, cap):
    """Keep the tail of the output, where failures are reported."""
    if len(text) <= cap:
        return text
    return "[... output truncated ...]\n" + text[-cap:]


def compose(role, task_prompt, feedback=None):
    parts = [instruction(role), "# Task\n" + task_prompt]
    if feedback:
        parts.append("# Feedback from the previous attempt\n" + feedback + "\n\n" + CHECK_AGAINST_TASK)
    return "\n\n".join(parts)
