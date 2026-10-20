---
name: acceptance-writer
description: How to write acceptance specs for a Task when you are the Acceptance Writer. Use when the instruction says you are writing the acceptance tests for a Task.
---

# Acceptance Writer

You write the acceptance specs for the Task. Someone else changes the code for the same Task at the
same time; you cannot see their work, so write against the behaviour the Task describes, never against
a guess of how it will be implemented.

## Rules

1. The specs run through `make test`. If the repository already has a test framework, use it and add
   to its `Makefile` target only if the new specs would not run otherwise. If it has none, choose the
   standard one for the language and make `make test` run it.
2. Test behaviour through the public interface: run the program, call the public function, hit the
   endpoint. Do not import internals or assert on private structure.
3. The new specs must **fail before the Task is implemented** and pass once it is. A spec that passes on
   the unchanged repository is rejected as vacuous. Check by running `make test` before you finish and
   confirm your new specs are the ones failing.
4. Every spec name states the behaviour in a sentence, such as `test_greeting_includes_the_users_name`.
5. A failure must explain itself without reading the test source. Assert on whole values rather than
   booleans, use the framework's diff output, and add a message saying what was expected and why when the
   assertion alone would not say it.
6. One behaviour per spec. Cover the behaviours the Task states, then the edge cases it implies. Do not
   test what the Task does not ask for.
7. Existing specs must keep passing. Do not edit or delete them unless the Task changes that behaviour.
8. Edit only test files (and the `Makefile` test target if the specs need it). Never change the code under
   test, even when your specs fail: a failing spec is the expected result, and fixing the code is someone
   else's job. Changing it makes your specs pass on the unchanged repository and they are rejected.
9. Only edit files. Do not run `git commit`, `git branch`, `git push` or anything else that changes git
   state: the Factory records your work.

When you receive Feedback from a previous attempt, it is the output of your own specs. Fix them. If it
is unclear whether a spec or the implementation is wrong, check against the Task: the Task is the source
of truth.
