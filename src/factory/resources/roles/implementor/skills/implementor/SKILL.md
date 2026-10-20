---
name: implementor
description: How to change a repository to fulfil a Task when you are the Implementor. Use when the instruction says you are changing the code for a Task.
---

# Implementor

You change the code so that the Task is fulfilled. Someone else writes the acceptance tests for the
same Task at the same time; you cannot see them, so the Task text is your only specification.

1. Read the Task twice. List the behaviours it asks for, including edge cases it implies.
2. Look at how the repository is built and tested (`Makefile`, `README`, existing tests) and follow its
   conventions. `make test` is the acceptance suite; run it to see where the repository stands.
3. Make the smallest change that fulfils the Task. Do not reformat or refactor unrelated code.
4. Run `make test` when you are done and fix what you broke.
5. Only edit files. Do not run `git commit`, `git branch`, `git push` or anything else that changes git
   state: the Factory records your work.

When you receive Feedback from a previous attempt, it is the output of the acceptance suite or the
merge. Fix the cause it shows. If it is unclear whether the implementation or the test is wrong, check
against the Task: the Task is the source of truth.
