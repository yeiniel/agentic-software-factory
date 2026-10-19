# Design: Agentic Software Factory

Status: agreed design from a grilling session, nothing implemented yet. Vocabulary is in `../GLOSSARY.md`; use those terms exactly. The fixed decisions are in `adr/`: `0001-agents-are-agnostic-to-task-delivery-and-change-delivery.md` and `0002-algorithmic-work-runs-outside-the-agents.md`. Everything marked **Experiment** is the initial approach to be tested and may be replaced.

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

1. The Factory launches two **Agents** in separate **Environments**, each running Pi with its cwd set to a clone of the repo and the Task as its prompt:
   - **Implementor**: changes the code; the Factory records the result on its own branch.
   - **Acceptance Writer**: writes acceptance specs; the Factory records the result on its own branch.
2. The Agents are **blind to each other**: neither sees the other's branch. Their only shared contract is the Task text.
3. The **Integrator** (non-agent) then:
   1. Checks the new specs are valid: they run cleanly, and are red on the base repo (vacuous specs are rejected).
   2. Merges or rebases the two branches. A conflict fails the Run.
   3. Runs the entire acceptance suite on the integrated result.
   4. If green, rebases onto the latest `main`, re-runs the full suite and fast-forwards `main`. Integration is a single serial queue against the current `main`; Agents run in parallel.
   5. Marks the Task done in the task store. Agents never touch the store.
4. On failure, `main` is untouched, and a new Run starts for the same Task.

## Retries and Feedback

- A retry is a new Run that carries **Feedback**, so it is informed and not a blind re-roll.
- Only the failing role is retriggered; the passing role's branch is reused unchanged.
- Blame is decided algorithmically:
  - New specs that error for non-behavioural reasons, or that are not red on base, go to the Acceptance Writer.
  - Specs that run and fail on behaviour (new or existing) go to the Implementor.
  - If the Implementor fails twice on the same spec, that spec is also sent back to the Acceptance Writer. It receives only its own run output, never the Implementor's diff.
- The retried Agent continues from its own previous result (the Factory restores its branch into the working tree) and resumes its previous Pi session; Feedback arrives as an ordinary follow-up prompt. The Factory keeps a session record per role per Task, so Environments stay ephemeral.
- Feedback contents: the spec run output (the **Acceptance Report**), any conflicts, and a reminder to check against the Task spec when it is unclear whether the implementation or the spec is wrong. It never discloses the other Agent's branch. Output is passed raw and algorithmically, truncated to a size cap, with no LLM summarising step.
- The Acceptance Report is made informative on failure by two things: a good spec framework, and a repo-owned Pi skill that teaches the Acceptance Writer how to write specs that explain themselves when they fail.
- The cap is **2 Runs per Task in total** (not per role). After that the Task is **Blocked** and the history of each Run (inputs, Feedback, outcome) goes to a human.

## Open

- Isolation technology for an Environment (container, VM, other): undecided; the first implementation may pick the cheapest. Write an ADR once the choice is hard to reverse.
- Task-store details: the git-native-issue repo is the first implementation; how a new Task triggers the Factory (polling, hook, command) is undecided.
- Which spec framework, and the exact Pi skill for the Acceptance Writer.
- How an Acceptance Writer is kept to a known acceptance test directory to avoid conflicts (a possible rule, not decided).
- Pi session persistence format and how a resumed Environment is rebuilt.
- Pi is assumed to be the Pi coding agent runtime; confirm before building.

## Suggested first slice

An Integrator script plus a one-Task end-to-end run against a small sample repo, with the Environment as simply as possible (local container or even a plain worktree), to test the blind two-Agent flow and the Feedback loop.
