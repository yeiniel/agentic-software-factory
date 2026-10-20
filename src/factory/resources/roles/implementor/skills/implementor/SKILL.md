---
name: implementor
description: How to change a repository to fulfil a Task when you are the Implementor. Use when the instruction says you are changing the code for a Task.
---

# Implementor

How to approach a Task. The rules that always apply (smallest change, run `make test`, change no git
state) are in your system prompt.

1. Read the Task twice. List the behaviours it asks for, including edge cases it implies.
2. Look at how the repository is built and tested (`Makefile`, `README`, existing tests) and follow its
   conventions. `make test` is the acceptance suite; run it to see where the repository stands.

When you receive Feedback from a previous attempt, it is the output of the acceptance suite or the
merge. Fix the cause it shows. If it is unclear whether the implementation or the test is wrong, check
against the Task: the Task is the source of truth.
