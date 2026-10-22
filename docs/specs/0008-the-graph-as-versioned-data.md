---
status: implemented
---

# The Graph as versioned data

## Problem Statement

How a Run proceeds is written into `src/factory/run.py`: the two role names, one loop function per role, the rule that a failed integration retriggers only the Implementor, the Run cap, the Feedback sentences and what each Activity's Run Context holds. The Graph is what has changed most between experiments (the validation split, the nested loops), and each change edits the core. ADR 0020 records the decisions; vocabulary is in `GLOSSARY.md`.

## Solution

The Graph becomes a folder in the Factory repository that a small interpreter in the core runs. The core knows two kinds of Activity (an agentic one running a named role, a deterministic one running a named script), loops and parallel regions, and the effects it alone performs. It knows no role names.

## The Graph

- A folder holding `graph.json` and everything it names by relative path: role instructions, system prompts and skills, Activity `run` scripts and Feedback messages. The shape of `graph.json` is `src/factory/graph.schema.json`. The version of a Graph is the commit of the Factory repository it was loaded from; a Task pins it at `task-received` and the Records carry it.
- A Graph is states and transitions, and the file says everything the core needs: nothing is implied by the order of a list or by a convention of the core. Every state lists its `transitions`, `{on, to}`, where `on` is an outcome from a closed list owned by the core (`green`, `red` or `red:<check>`, `crashed`, `timed-out`, `exhausted`, `advanced`, `main-moved`) and `to` is a state, `$exit` (leave the enclosing compound state, succeeded) or an enclosing loop (its next attempt). A transition may `reset` loops, and carry a Feedback message `{for: <role>, message: <file>}` that uses only `{check}` and `{output}` (raw, truncated to the Factory's cap).
- Kinds of state:
  - an **agentic** Activity carries everything handed to its executor: the role, the files of its instruction, system prompt and skills, the sections of its prompt, its workspace (`base`, or the branch of another Activity), its timeout, whether a retry keeps the Pi session, and the branch its result is recorded to;
  - a **deterministic** Activity: the script, its inputs (what is checked out into which folder), which input holds the Containerfile of its Environment, the failed checks it may report, its timeout and the branch it records when green;
  - a **loop**: `attempts`, an `entry` and the states it `contains`; the core defines that the budget resets on each entry and that a succeeded loop is kept when an enclosing loop re-enters unless a transition resets it. The start loop, marked `runs`, has the Runs as its attempts;
  - a **parallel** state: regions that run together and join when all have succeeded;
  - **publish**: the core's effect that fast-forwards `main` from the base to a recorded branch; its outcomes are `advanced` and `main-moved`;
  - **status** states: `done` or `blocked` plus a reason; `running` is written by the core at the start of each Run. `blocked` is terminal; a human re-adds the Task.
- `main` is not an input: it equals `base` for the whole Task.
- The default Graph is today's flow: the Run loop (2 attempts) around a parallel state of the Writer loop (2: Acceptance Writer, then Acceptance Test Validation) and the Implementor loop (2), then the Integrator, then publish. A failed integration leaves the Integrator and re-enters the Run loop with `reset` on the Implementor loop and the Integrator's output as Feedback. The top-level `error` names the `blocked` status (reason `infrastructure`) an Adapter error or a malformed verdict leads to; `main-moved` goes to `blocked` with reason `main-moved`.

## Load-time checks

The Factory loads and checks the Graph once, at start, and refuses to start on a failure; a changed Graph takes a restart. A Graph is rejected for:

- a state no transition reaches, a loop without `attempts`, or a name that resolves to no file in the folder;
- an outcome that has no transition, so no outcome is unhandled;
- a path into `done` that does not come from publish, or a Feedback message with a placeholder other than `{check}` and `{output}`;
- an Activity input that is not `base` or `branch-of` a role the Graph runs;
- a cycle that no attempt budget bounds: a transition to an enclosing loop is the next attempt of that loop and its attempts are finite, so the transitions that remain (not to an enclosing loop, not `$exit`) must form no cycle.

`make check` runs the same load on the shipped Graph.

## Implementation Decisions

- The interpreter replaces the control flow in `run.py`; Spans, Records and the Task statuses stay as they are, with loop and role names taken from the Graph.
- `MAX_INTEGRATIONS`, the retry on `main-moved`, the Integrator's `main` checkout and its rebase onto the latest `main` are removed. The Repo Host's `expect_main` guard stays.
- ADR 0015 is superseded on where resources live: `src/factory/resources/` becomes the default Graph folder; the core still writes them into each Run Context.
- `docs/design.md` and the glossary's **Run** entry change in the same commit as the code, as in spec 0005.

## Testing Decisions

- Equivalence: the default Graph reproduces today's golden transcripts in `tests/goldens`, differing only by the removals above. `run.py` stays as the reference until it does, then is deleted.
- Editability: a second Graph that adds a third agentic role (a Reviewer after integration) through a new prompt folder only. If it needs a change in the core, the model has failed.
- Load-time checks: one scenario per rejection above, through the Factory's start and its exit status.
- Baseline scenarios, the Tasks already run, each with its commit and the end state the default Graph must give it:
  - `pydantic-extra-types` #326: `done` in one Run;
  - `unjs/ufo` #379: `done` in one Run, the Writer's first specs rejected by validation and its second accepted;
  - `tailwind-merge`: `blocked` on the Implementor loop (both attempts timed out). It is updated when the rerun on the isolated network changes the outcome.
- All of it through the seams of ADR 0018, with 100% line and branch coverage.

## Out of Scope

- Tasks running in parallel, which need the cross-Task queue the Graph does not model; a human tool to release a `blocked` Task; a Graph per repository; the Factory proposing Graphs; any automatic rule for promoting a Graph.
