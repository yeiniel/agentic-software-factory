# Agentic Software Factory

A system that drives AI agents to carry out a Task over an existing repository, with the outcome judged by a passing acceptance test suite on `main`. Everything algorithmic is done by the Factory outside the agents.

## Language

**Factory**:
The system as a whole: it takes Tasks, launches Agents, integrates their work and decides whether a Task is done.

**Task**:
The lowest-level unit of work: a prompt describing a change, plus the repository it applies to. Agents receive it as a plain prompt and never fetch it from a task store.
_Avoid_: Ticket, story, work item, issue

**Agent**:
An instance of the Pi agent runtime that receives a prompt inside an Environment, with its working directory set to a clone of the repository. It only edits files; it never branches, commits or pushes.

**Implementor**:
The Agent role that changes the repository to fulfil a Task. The Factory records its result on its own branch.

**Acceptance Writer**:
The Agent role that writes the acceptance tests for a Task. The Factory records its result on its own branch.

**Environment**:
The isolated place where a single Agent runs. The isolation technology (container, VM) is undecided.

**Integrator**:
The automated, non-agent process that combines the Implementor's and Acceptance Writer's branches, runs the acceptance suite, and merges to `main` only when it passes.
_Avoid_: Merger, CI

**Acceptance Report**:
The acceptance suite's run output, made informative on failure by a good spec framework plus the Acceptance Writer's skill on how to write specs.

**Feedback**:
What the Integrator hands back to a retriggered Agent after a failed Run: the spec run output, conflicts, or both, plus a reminder to check against the Task when it is unclear whether the implementation or the test is at fault. It never discloses the other Agent's branch.

**Blocked**:
The status of a Task that reached its Run cap (2 Runs by default) without a Deliverable and now waits for a human.

**Run**:
One attempt to complete a Task: the Agents are launched and the Integrator is applied to their results.

**Deliverable**:
The outcome that makes a Task done: the acceptance test suite passes on `main`.
_Avoid_: PR, output
