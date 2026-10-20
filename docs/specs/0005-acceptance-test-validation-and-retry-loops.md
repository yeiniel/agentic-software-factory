---
status: ready-for-agent
---

# Acceptance Test Validation and retry loops

## Problem Statement

The Integrator's first step checks that the new specs are red on the base. That judges the Acceptance Writer's work, yet it runs only after both Agents have finished, so a Writer fault waits for the Implementor and shares the Integrator's verdict. The Feedback for it is the tail of a passing `make test` output, which does not say why the specs were rejected. A single cap of 2 Runs also lets one hung Agent use a Run before the Writer's retry can happen. And a retried Agent continues from its own failed edits, which get in the way. ADR 0016 records the decisions; vocabulary is in `GLOSSARY.md`.

## Solution

Acceptance Test Validation becomes a deterministic process of its own, run as soon as the Acceptance Writer is recorded. The Run becomes a set of nested loops with separate budgets, and a retried Agent starts again from the initial code with its Pi session kept.

## Flow

```
Task (outer cap: max_runs = 2; a failed integration costs a Run)
└─ Run
   ├─ Writer loop      (writer_attempts = 2): Acceptance Writer → Acceptance Test Validation   ┐ in parallel
   ├─ Implementor loop (implementor_attempts = 2): Implementor                                  ┘
   └─ Integrator, once, when both loops succeeded
```

- A Writer attempt fails if the Agent crashes or times out, or if validation returns red. The Feedback for the next attempt starts with the reason, then the validation output.
- An Implementor attempt fails if the Agent crashes or times out. Nothing else is checked before integration.
- If either loop uses up its attempts, the Task is Blocked and nothing is integrated. The history names the loop.
- A failed integration (conflict or red suite) ends the Run. The next Run re-enters only the Implementor loop, with the Integrator's output as Feedback and a fresh budget. The Writer's validated branch is kept.
- A loop that succeeded in an earlier Run is not re-entered.
- Adapter failures are infrastructure errors outside every budget, and so is the retry of the Integrator when `main` moved.

## Acceptance Test Validation

- A deterministic Environment on its own Run Context, `contexts/<task>/validate-<run>-<attempt>`. `cwd` holds `base` and `acceptance-writer` (names are the core's) and a copy of `base`'s `Containerfile` at its root. No network.
- The `run` script is a core resource beside the Integrator's. It merges the Writer's branch into a copy of the base and runs `make test`. A non-zero exit is green for validation; a zero exit is `specs-not-red`. A merge that fails is also red for the Writer.
- It leaves `result`, `failed_check` and `output` in `out/`, in the format the Verdict module already reads. It produces no branch.
- The Integrator's `run` script no longer checks the specs; it starts at combining the branches.

## Retry attempts

- A retry resets the Agent's branch to the base and checks out a fresh `cwd`. The Pi session in the Context is kept and resumed.
- The new `prompt` is the Task plus the Feedback. The Feedback is: one fixed sentence saying why it failed (per verdict); one fixed sentence saying the Agent's previous changes were discarded and it starts again from the original code; the raw output, truncated to the size cap; the reminder to check against the Task. No diff, no LLM step.
- A passing Agent keeps its branch and Context for the following Run.

## Implementation Decisions

- `max_runs` keeps its meaning. `writer_attempts` and `implementor_attempts` join the Factory's config, default 2.
- `blame` is replaced by loop logic in `run.py`. The "Implementor twice on the same output retriggers the Writer" rule is removed. `specs-not-red` is no longer a verdict of the Integrator.
- The Verdict module is shared by both processes; `failed_check` values for validation are `specs-not-red` and `merge`.
- The Context is handed back for the retry as before, but `cwd` is checked out again from the base. `docs/design.md`, spec 0001, spec 0004 and the Glossary change in the same commit as the code.
- Records get one event per attempt with the loop name and the attempt number, and a `loop-exhausted` event when a budget runs out.

## Testing Decisions

- Core: black-box Runs against the stand-in as in `tests/test_runs.py`:
  - a Writer whose specs are not red is retried with the reason first, and the Implementor's branch is untouched;
  - validation runs while the Implementor is still running, and a Writer fault is found even when the Implementor times out;
  - a crashed Implementor is retried within the Run, and exhausting the budget blocks the Task with the loop named in the history;
  - exhausting the Writer's budget blocks the Task with no integration;
  - a failed integration retriggers only the Implementor in the next Run, with a fresh budget, and the Writer is not re-entered;
  - the Writer can run four times over two Runs;
  - a retry starts from the base code with the session resumed, and its prompt contains the reset sentence and no diff;
  - infrastructure errors and the `main`-moved retry use no budget.
- Validation `run` script: against real git and a tiny real `make test`, as `tests/test_real_integrator.py` does for the Integrator.
- Verdict: table tests for the new `failed_check` values.

## Out of Scope

- Rejecting a Writer branch that changes non-test files (not decidable the same way for every repository).
- Cancelling an Agent that is still running when the other loop has already blocked the Task.
- Specs that are red on base but wrong: the Task ends Blocked for a human.
