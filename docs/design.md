# Design: Agentic Software Factory

Status: agreed design from a grilling session, nothing implemented yet. Vocabulary is in `../GLOSSARY.md`; use those terms exactly. The fixed decisions are in `adr/`: `0001-agents-are-agnostic-to-task-delivery-and-change-delivery.md` and `0002-algorithmic-work-runs-outside-the-agents.md`, and, for this experiment branch, ADRs 0003 to 0011 (blind parallel Agents, the Deliverable, Pi, container Environments, `make test`, local inference, Tasks as git-native issues on a self-hosted git server, the Factory as a container with the Podman socket, a core with no direct effects). The **Experiment** markers below are now settled by those ADRs where one applies. Everything marked **Experiment** is the initial approach to be tested and may be replaced.

## Principle

Everything algorithmic runs outside the agents. Agents only do work that needs judgment; the Integrator, task-store integration, retry accounting and branch handling are plain code. Keep it as simple as possible. See ADR 0002.

## Scope

- The Factory handles one **Task**: a prompt plus an existing repository.
- Out of scope for now: decomposing products or features into Tasks, greenfield repo creation, other SDLC phases. These may become separate contexts later.
- The Factory itself integrates with a task store: a Task added to the store triggers a Run, and the Factory reads the Task and runs the Agent with it as the prompt, repo in scope. The store sits behind a boundary (first implementation: a git-native-issue repo); the Agents never see it. See ADR 0001.
- The same holds for output: Agents only edit the working tree. They are never told to branch, commit or push; the Factory captures their changes from the Environment and creates the branches itself.

## Deliverable

A Task is done when the full acceptance suite passes on `main`. (**Experiment**: other definitions, such as a reviewed PR, may be tried later.)

## Run flow (Experiment)

1. The Factory launches two **Agents** in separate **Environments**, each running Pi with its cwd set to a fresh clone of the repo, switched to the role's branch, and the Task as its prompt. The container is built from the `Containerfile` at the repo root (ADR 0006), which must provide `git` and `make`; the Factory layers Pi and the final run command on top of it, so repos declare only their stack, and the image is cached per repo and base commit. It is booted with everything in place; it reaches the local model server (ADR 0008). Both roles get identical Environments and may touch any path:
   - **Implementor**: changes the code; the Factory records the result on its own branch.
   - **Acceptance Writer**: writes acceptance specs; the Factory records the result on its own branch.
2. The Agents are **blind to each other**: neither sees the other's branch. Their only shared contract is the Task text.
3. The **Integrator** (non-agent, run in its own Environment on a Run Context holding both branches and the latest `main`; it returns a verdict and a branch, and the Factory alone pushes to `main`) then:
   1. Checks the new specs are valid: `make test` on the base plus the Acceptance Writer's branch must exit non-zero (vacuous specs are rejected). What is new is known from that branch's diff against base. The acceptance suite is `make test` (ADR 0007).
   2. Merges or rebases the two branches. A conflict fails the Run.
   3. Runs the entire acceptance suite on the integrated result.
   4. If green, rebases onto the latest `main`, re-runs the full suite and fast-forwards `main`. Integration is a single serial queue against the current `main`; the two Agents run in parallel.
   5. Marks the Task done in the task store. Agents never touch the store.
4. On failure, `main` is untouched, and a new Run starts for the same Task.
5. Only one Run is in flight at a time for now: the local model server has a fixed number of slots (ADR 0008). Parallel Tasks are future work and depend on more capacity.

Every actor, agentic and deterministic, leaves a record: each Run writes a structured event log (every Integrator command with its exit code and output, branch and merge results, the Feedback produced) plus the Agents' Pi session transcripts, stored outside the repo.

## Retries and Feedback

- A retry is a new Run that carries **Feedback**, so it is informed and not a blind re-roll.
- Only the failing role is retriggered; the passing role's branch is reused unchanged.
- Blame is coarse, because `make test` gives only an exit code (ADR 0007):
  - If the new specs are not red on base, the Acceptance Writer is retriggered.
  - Otherwise a failure is first the Implementor's, with the output as Feedback.
  - If the Implementor fails twice on the same output, the Acceptance Writer is also retriggered with its own run output, never the Implementor's diff.
- Each Run starts a fresh container with a fresh clone, switched to the role's branch, so the retried Agent continues from its own previous result. It also resumes its previous Pi session, whose state lives in a local folder per role per Task that is mounted into the container, behind an abstraction so it can be swapped later; Feedback arrives as an ordinary follow-up prompt. A Run's clone contains only its pre-created branch, with the remote and every other branch removed, so blindness holds by construction; the Factory fetches the result back from the clone after the container exits.
- Feedback contents: the spec run output (the **Acceptance Report**), any conflicts, and a reminder to check against the Task spec when it is unclear whether the implementation or the spec is wrong. It never discloses the other Agent's branch. Output is passed raw and algorithmically, truncated to a size cap, with no LLM summarising step.
- The Acceptance Report is made informative on failure by two things: a good spec framework, and a repo-owned Pi skill that teaches the Acceptance Writer how to write specs that explain themselves when they fail.
- The cap is **2 Runs per Task in total** (not per role). After that the Task is **Blocked** and the history of each Run (inputs, Feedback, outcome) goes to a human.

## Architecture

The Factory core holds business logic and the fixed graph of Activities for a Run; it runs no git, Podman or file effects itself (ADR 0011). Each effect is an Adapter, an executable with a documented contract (arguments in, JSON out). The six ports:

- **Event Source**: subscribes to Task and repo events.
- **Task Store**: reads a Task and updates its status.
- **Repo Host**: hands out a clone of one branch, creates and records branches, and fast-forwards `main`. All git lives here.
- **Environment Builder**: builds the image for a repo at a commit, with the tooling layered on.
- **Runner**: runs an Agent or the Integrator in an Environment on a Run Context and returns the result.
- **Records**: receives the event log.

The Integrator runs in an Environment because it executes Agent-written code (`make test`), which must never run in the Factory container (it holds the Podman socket). It is a pure function from a Run Context (base, both branches, latest `main`) to a verdict plus a branch; it starts as a small POSIX shell script layered onto the repo image like Pi, and may be replaced by any tool that honours the contract. The Factory queues Integrator runs one at a time, fast-forwards `main` only on a green verdict, and starts a fresh Integrator run if `main` moved.

The **agent harness layer** is what the Environment Builder adds on top of a repo's image for Agents: Pi and its runtime, Pi's configuration (pointing at the local model server), the skills for both roles, and an entrypoint. There is one layer for both roles; the roles differ only in the prompt, which the core composes (the Task, the role's instruction and any Feedback) and the Run Context provisions per Run. The Run Context is a mounted directory holding the prompt, the clone on the role's branch as the working directory, and the Pi session state (empty on the first Run). The Integrator has its own layer and entrypoint, with its three branches in the clone area, and no Pi.

Deployment (the Factory's own image, the Podman socket mount, the Repo Host container) is separate and tracked outside the core. The core expects a reachable Repo Host, a Podman socket and a model server, and nothing more.

## Topology

The Factory is a container on the same network as the Repo Host. It boots Environments as sibling containers through the host's Podman socket (ADR 0010), and the Environments reach the local model server (ADR 0008). Tasks are git-native issues in the target repo on the Repo Host (ADR 0009); the Repo Host sends the Factory a push event over the network, and the Factory reacts to the Task event and records `main` pushes without reacting. The Task Store and Repo Host are abstractions so either can be swapped.

Blindness and `main`'s protection from Agents come from construction: the Factory is the only automated party with read/write access to the Repo Host (the human owner also has it, unrestricted, and adds Tasks by pushing), hands each Agent a clone that holds only its branch and has no remote, and Agents never know the Repo Host exists.

## Known gaps

- Events are not guaranteed: a webhook missed while the Factory is down is lost. Reconciling against the Task Store on start is the likely fix, deferred.
- Humans can write anything to the Repo Host, including `main`; nothing enforces that only the Integrator advances `main` against a human push. A convention for this experiment.
- Egress from Environments is not restricted beyond the container network.

## Open


- Which spec framework, and the exact Pi skill for the Acceptance Writer.
- Factory implementation language: Python for the experiment, because fast development matters more than performance now. The plan is to build a strong test suite and later use it to port the Factory to something more performant and durable (Go and Rust were considered). Not an ADR, since reversing it is the plan.
- Experiment evaluation: records of every actor are kept; how an external agent judges the results (rubrics, criteria) is addressed once the Factory is built.
- Sample repos for the experiment: two (TypeScript and Python), with history at different stages, stored as git bundles under `experiments/`, Tasks pinned to a commit. Not yet built.

## Suggested first slice

An Integrator script plus a one-Task end-to-end run against a small sample repo, with a local container as the Environment (ADR 0006), to test the blind two-Agent flow and the Feedback loop.
