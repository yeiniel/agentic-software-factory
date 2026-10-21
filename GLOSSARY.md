# Agentic Software Factory

A system that drives AI agents to carry out a Task over an existing repository, with the outcome judged by a passing acceptance test suite on `main`. Everything algorithmic is done by the Factory outside the agents.

## Language

**Factory**:
The system as a whole: it takes Tasks, launches Agents, integrates their work and decides whether a Task is done.

**Task**:
The lowest-level unit of work: a prompt describing a change to an existing repository. It lives in the Task Store, and Agents receive it as a plain prompt without ever reading the Task Store.
_Avoid_: Ticket, story, work item, issue

**Agent**:
An instance of the Pi agent runtime that works inside an Environment on a Run Context. It only edits files; it never branches, commits or pushes.

**Implementor**:
The Agent role that changes the repository to fulfil a Task. The Factory records its result on its own branch.

**Acceptance Writer**:
The Agent role that writes the acceptance tests for a Task. The Factory records its result on its own branch.

**Run Context**:
Everything provisioned for one Agent, or for the Integrator, in one Run. For an Agent: the prompt, the role's system prompt and skills, the project source on the role's branch as its workspace (including whatever the project itself brings for agents), and the resumed Pi session state. For the Integrator and for Acceptance Test Validation: what it runs and what it works on.

**Task Store**:
Where Tasks live and where their status is written back. An abstraction that Agents never see.

**Run Context Store**:
Where Run Contexts live between the Factory assembling them and an Environment running on them. An abstraction that Agents never see.

**Repo Host**:
Where a repository lives and where pushes to it are received. An abstraction, and the source of the events (such as a push) the Factory reacts to.

**Environment**:
The isolated container where a single Agent, or the Integrator, runs, built from the target repository's own container definition and booted with a Run Context and all dependencies already in place. It is either **agentic** (it reaches the model server) or **deterministic** (it has no network); it never knows what runs in it.

**Integrator**:
The deterministic, non-agent process that runs in an Environment on a Run Context holding the Implementor's and Acceptance Writer's branches. It combines the branches and runs the acceptance suite, and returns a verdict plus the combined branch; the Factory alone decides what reaches `main`.
_Avoid_: Merger, CI

**Acceptance Test Validation**:
The deterministic, non-agent process that checks the Acceptance Writer's work before integration: it runs in an Environment on a Run Context holding the base and the Acceptance Writer's branch, and returns a verdict on whether the new specs fail on the unchanged repository.

**Acceptance Report**:
The stdout and stderr of `make test`, made informative on failure by a good spec framework plus the Acceptance Writer's skill on how to write specs. The exit code is the green/red signal.

**Feedback**:
What the Factory hands back to a retriggered Agent after a failure: why it failed, the spec run output, conflicts, or both, a note that its previous changes were discarded, and a reminder to check against the Task when it is unclear whether the implementation or the test is at fault. It never discloses the other Agent's branch.

**Blocked**:
The status of a Task that reached its Run cap (2 Runs by default), or whose Acceptance Writer or Implementor used up its attempts within a Run, without a Deliverable and now waits for a human.

**Activity**:
One step in a Run's fixed graph: assemble the Run Contexts, run the Agents, validate, integrate, publish.

**Adapter**:
A swappable external executable through which the Factory performs an effect: events, Task Store, Repo Host, running an Environment on a Run Context, and records.

**Console**:
The read-only view onto Tasks, their Runs and the Factory's metrics, kept current as work happens. It never changes the Factory.
_Avoid_: Dashboard, Monitor

**Run**:
One attempt to complete a Task: each Agent is launched in its own Environment with its own Run Context, the Acceptance Writer's work is validated, and the Integrator is applied to their results. An Agent that crashes, or an Acceptance Writer whose specs fail validation, is retried within the Run up to a limit per role.

**Deliverable**:
The outcome that makes a Task done: the acceptance test suite passes on `main`.
_Avoid_: PR, output
