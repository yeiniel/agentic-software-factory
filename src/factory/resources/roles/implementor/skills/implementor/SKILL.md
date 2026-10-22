---
name: implementor
description: How to change a repository to fulfil a Task when you are the Implementor. Use when the instruction says you are changing the code for a Task.
---

# Implementor

How to approach a Task. The rules that always apply (smallest change, run `make test`, change no git
state) are in your system prompt.

1. The Task is in your prompt, under `# Task`; it is not a file in the repository. Before you edit anything,
   list the behaviours it asks for, including the edge cases it implies, and keep to that list.
2. Look at how the repository is built and tested (`Makefile`, `README`, existing tests) and follow its
   conventions. `make test` runs the existing specs, not the ones written for this Task; run it to see where
   the repository stands.

When you receive Feedback from a previous attempt, it is the output of the acceptance suite or the
merge. Compare each failure with the Task before you touch the code: the failing spec may be an old one
that the Task makes obsolete, or one written for the Task that your change does not satisfy. Fix the
cause only when the Task calls for it. The Task is the source of truth.
