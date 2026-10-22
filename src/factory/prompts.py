"""Prompt composition and Feedback rendering. The words themselves belong to the Graph (ADR 0020)."""

CHECK_AGAINST_TASK = "If it is unclear whether the implementation or the spec is wrong, check against the Task."


def truncate(text: str, cap: int) -> str:
    """Keep the tail of the output, where failures are reported."""
    if len(text) <= cap:
        return text
    return "[... output truncated ...]\n" + text[-cap:]


def render(message: str, check: str, output: str, cap: int) -> str:
    """A Feedback message with its two placeholders filled; the output is raw and truncated."""
    return message.replace("{check}", check).replace("{output}", truncate(output, cap))


def compose(sections: list[str], instruction: str, task: str, feedback: str | None = None) -> str:
    """The prompt: the sections the Graph lists, in its order. Feedback is left out when there is none."""
    parts = {
        "instruction": instruction,
        "task": "# Task\n" + task,
        "feedback": "# Feedback from the previous attempt\n" + (feedback or "") + "\n\n" + CHECK_AGAINST_TASK,
    }
    return "\n\n".join(parts[section] for section in sections if section != "feedback" or feedback)
