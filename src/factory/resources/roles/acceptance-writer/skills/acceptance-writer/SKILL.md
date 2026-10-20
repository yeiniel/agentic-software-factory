---
name: acceptance-writer
description: How to write acceptance specs for a Task when you are the Acceptance Writer. Use when the instruction says you are writing the acceptance tests for a Task.
---

# Acceptance Writer

How to write good acceptance specs. The rules that always apply (edit only tests, the specs must fail
before the Task is implemented, keep existing specs passing, change no git state) are in your system prompt.

## Conventions

1. The specs run through `make test`. If the repository already has a test framework, use it and add
   to its `Makefile` target only if the new specs would not run otherwise. If it has none, choose the
   standard one for the language and make `make test` run it.
2. Test behaviour through the public interface: run the program, call the public function, hit the
   endpoint. Do not import internals or assert on private structure.
3. Every spec name states the behaviour in a sentence, such as `test_greeting_includes_the_users_name`.
4. A failure must explain itself without reading the test source. Assert on whole values rather than
   booleans, use the framework's diff output, and add a message saying what was expected and why when the
   assertion alone would not say it.
5. One behaviour per spec. Cover the behaviours the Task states, then the edge cases it implies. Do not
   test what the Task does not ask for.

When you receive Feedback from a previous attempt, it is the output of your own specs. Fix them. If it
is unclear whether a spec or the implementation is wrong, check against the Task: the Task is the source
of truth.
