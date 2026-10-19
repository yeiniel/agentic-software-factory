"""Role instruction templates and prompt composition. Versioned with the core."""

INSTRUCTIONS = {
    "implementor": "Change the repository so that the Task below is fulfilled. Only edit files.",
    "acceptance-writer": "Write acceptance specs for the Task below, runnable with `make test`. "
                         "Only edit files.",
}

CHECK_AGAINST_TASK = ("If it is unclear whether the implementation or the spec is wrong, "
                      "check against the Task.")


def truncate(text, cap):
    """Keep the tail of the output, where failures are reported."""
    if len(text) <= cap:
        return text
    return "[... output truncated ...]\n" + text[-cap:]


def compose(role, task_prompt, feedback=None):
    parts = [INSTRUCTIONS[role], "# Task\n" + task_prompt]
    if feedback:
        parts.append("# Feedback from the previous attempt\n" + feedback + "\n\n" + CHECK_AGAINST_TASK)
    return "\n\n".join(parts)
