---
status: ready-for-agent
---

# Factory core

## Problem Statement

I want to hand a software change, written as a prompt, to a system that carries it out on an existing repository without my involvement and without risking `main`. Today that means supervising an agent, deciding when its work is good enough, and doing the branching and merging myself. I need a Factory that decides on its own whether a Task is done, learns from failures instead of blindly retrying, and is independent of any particular git server, container runtime or task tracker, so the same logic can later move to another language or deployment.

## Solution

A Factory core that contains only business logic and a fixed graph of Activities for each Run, and that performs every effect through an Adapter (ADR 0011). On a Task event it runs the Implementor and the Acceptance Writer as blind, parallel Agents, hands their branches to the Integrator, and lets the Integrator's verdict decide whether `main` advances. On failure it retriggers only the failing role with Feedback. After 2 Runs the Task is Blocked for a human. Vocabulary is in `GLOSSARY.md`, the design in `docs/design.md`, and the decisions in `docs/adr/`.

## User Stories

1. As a developer, I want the Factory to react when a Task is added to the Task Store, so that I never launch work by hand.
2. As a developer, I want the Factory to read the Task's prompt itself and hand it to the Agents as plain text, so that Agents never see the Task Store.
3. As a developer, I want the Factory to compose each Agent's prompt from the Task, the role's instruction and any Feedback, so that the roles differ only in the prompt.
4. As a developer, I want every effect (events, Task Store, git, Environment building, running Agents and the Integrator, records) to go through an Adapter, so that deployment specifics stay swappable.
5. As a developer, I want each Adapter to be an external executable with a documented contract, so that I can replace one with a scripted stand-in in tests or with a different implementation in production.
6. As a developer, I want the Factory core to run no git, container or file-system effects itself, so that porting it later doesn't require redoing the effects.
7. As a developer, I want a fixed graph of Activities for each Run (prepare, build the Environment, run the Agents, integrate, publish, update the Task), so that the flow is predictable and testable.
8. As a developer, I want the Implementor and the Acceptance Writer launched in parallel, so that a Run takes as long as its slowest Agent.
9. As a developer, I want neither Agent to see the other's branch, so that tests aren't fitted to code or code to tests.
10. As a developer, I want each Agent to get its own pre-created branch in its own Run Context, so that the Factory knows what it handed out.
11. As a developer, I want the Factory to record each Agent's changes onto that role's branch, so that Agents never branch, commit or push.
12. As a developer, I want the Integrator to run in an Environment on a Run Context holding the base, both branches and the latest `main`, so that Agent-written code never runs in the Factory.
13. As a developer, I want the Integrator to return a verdict, its output and a resulting branch, so that the Factory can decide without running anything itself.
14. As a developer, I want the verdict to say which check failed (new specs not red on base, merge conflict, or the suite red), so that the Factory can route the retry.
15. As a developer, I want `main` advanced only by the Factory, only after a green verdict, so that `main` is never red.
16. As a developer, I want Integrator runs queued one at a time, so that two Tasks never integrate against the same `main`.
17. As a developer, I want a fresh Integrator run if `main` moved between the verdict and the push, so that a stale green can't land.
18. As a developer, I want a Task marked done only after `main` has advanced, so that done means done.
19. As a developer, I want the Task marked running while a Run is in flight, so that I can see what the Factory is doing.
20. As a developer, I want a failed Run to leave `main` untouched, so that failed work never leaks in.
21. As a developer, I want a failed Run to start a new Run for the same Task, so that retries are tracked uniformly.
22. As a developer, I want only the failing role retriggered, so that work that passed isn't redone.
23. As a developer, I want the passing role's branch reused unchanged on a retry, so that a retry costs only what failed.
24. As a developer, I want specs that are not red on base blamed on the Acceptance Writer, so that vacuous specs are fixed by the right role.
25. As a developer, I want any other failure sent first to the Implementor with the Integrator's output, so that the suite acts as the specification.
26. As a developer, I want the Acceptance Writer also retriggered, with its own run output only, if the Implementor fails twice on the same output, so that a wrong spec can be corrected without breaking blindness.
27. As a developer, I want a retried Agent to continue from its own previous branch and resume its previous session, so that its fix is targeted.
28. As a developer, I want Feedback to be the Integrator's output verbatim, truncated to a size cap, so that no summarising step is needed.
29. As a developer, I want Feedback to remind the Agent to check the Task when it is unclear whether the implementation or the spec is wrong, so that ambiguity is resolved against the source of truth.
30. As a developer, I want Feedback never to disclose the other Agent's branch, so that blindness holds across retries.
31. As a developer, I want a Task to stop after 2 Runs in total and become Blocked, so that a bad prompt can't burn budget forever.
32. As a developer, I want a Blocked Task to carry the history of every Run, so that I can understand what happened and rewrite the prompt.
33. As a developer, I want every actor, agentic and deterministic, to leave a record in each Run (every command with exit code and output, every branch and merge result, the Feedback produced, pointers to Agent transcripts), so that a person or an evaluator can audit it.
34. As a developer, I want records written through an Adapter, so that where they live is a deployment choice.
35. As a developer, I want only one Run in flight at a time, so that the local model server isn't oversubscribed.
36. As a developer, I want the Factory to handle events it receives while a Run is in flight by queueing them in memory, so that none is dropped while it's running.
37. As a developer, I want a per-Activity time limit, so that a stuck Agent or suite can't hang the Factory.
38. As a developer, I want the Factory to ignore `main` push events except to record them, so that a human push just changes the next Run's base.
39. As a developer, I want the core's test suite to treat the Factory as a black-box process, so that the same suite can later drive a port to another language.
40. As a developer, I want the Factory to fail a Task visibly, not silently, when an Adapter reports an error, so that infrastructure problems aren't mistaken for Agent failures.

## Implementation Decisions

- The core exposes one long-running process. It starts and reacts to events from the Event Source adapter. It does not look for Tasks that were already pending when it started; that is a known gap.
- The six Adapter ports are Event Source, Task Store, Repo Host, Environment Builder, Runner and Records. Their operations, as the core needs them:
  - **Event Source**: emits events (a Task added or updated, a push to `main`).
  - **Task Store**: reads a Task's prompt, and sets a Task's status among todo, running, done and blocked.
  - **Repo Host**: creates a branch for a role from a base, hands out a clone of one branch (single branch, no remote), records a Run Context's changes onto a branch, reports the latest `main`, and fast-forwards `main` from a branch.
  - **Environment Builder**: builds the image for a repo at a commit for a given purpose (Agent or Integrator), cached per repo and commit.
  - **Runner**: runs an Agent or the Integrator in an Environment on a Run Context directory, with a time limit, and returns the exit status, output and a pointer to any transcript.
  - **Records**: appends events to the Run's log.
- A Run Context is a directory on storage visible to the Adapters. For an Agent it holds the prompt, the clone on the role's branch as the working directory, and the Pi session state. For the Integrator it holds the clones of the base and the branches.
- Adapter contracts are documented in the repo as part of the core, with arguments in and JSON out. They are exercised by contract tests, so a new implementation can prove it conforms.
- The Task statuses are abstract in the core. Mapping them onto a particular Task Store is the Adapter's job.
- The Run is a single pass. Retry accounting, the cap of 2 Runs per Task, blame routing and Feedback construction live in the core. Blame follows `docs/design.md`.
- The Acceptance Report and Feedback are the Integrator's output passed verbatim; the core only truncates it.
- The core composes prompts from a role instruction template, the Task and Feedback. The templates are versioned with the core.
- The Factory serialises Integrator runs and final pushes to `main`. It never pushes to `main` except from a green verdict on a branch derived from the current `main`.
- The core is written in Python for the experiment and treated as portable. Nothing in its tests may depend on Python.
- Adapter failures are infrastructure errors, distinct from Agent failures, and don't consume a Run toward the cap.

## Testing Decisions

- A good test drives the Factory as a process and asserts on observable results: the state of `main`, the Task Store, the records and what each Adapter was asked to do. It never imports Factory code.
- All Adapters are scripted stand-in executables backed by a temporary fixture repo and a fixture Task Store. The Runner stand-in applies canned edits per role per Run, and the Integrator stand-in is either a scripted verdict or the real Integrator against real git and a tiny real `make test`.
- Scenarios to cover: green on the first Run; Implementor fails once then succeeds with Feedback; specs not red on base routed to the Acceptance Writer; the Implementor fails twice and the Acceptance Writer is also retriggered; branch conflict; `main` moves between verdict and push; two Tasks queued behind one Run; the cap reached and the Task Blocked with its history; a retried Agent's prompt contains the Feedback and never the other branch; an Adapter error not counting against the cap; a `main` push event being recorded but not acted on; an Activity time limit.
- Each Adapter contract has its own conformance test, reusable against any implementation.
- No prior art exists: the repository is empty of code.

## Out of Scope

- Any concrete Adapter (git-native-issue, git server, Podman, Pi); those are in spec 0002.
- The experiment harness: sample repos, Tasks and the evaluator.
- Deployment of the Factory itself.
- Decomposing features into Tasks, and greenfield repositories.
- Event reliability and pending Tasks: the Factory only reacts to events, so a Task added while it is down, or any event lost in transit, is never picked up. This is a known gap.
- Restricting egress from Environments, and protecting `main` against human pushes.

## Further Notes

- On a merge conflict the Run fails. The blamed role is not yet decided. The default is the Implementor, with the conflict output as Feedback; revisit if it proves wrong.
- The blind two-Agent flow and the full-suite Deliverable are experiments (ADRs 0003 and 0004). The core should keep the blame routing and Run graph replaceable.
- A later self-hosting evaluation, where the Factory is given a Task about itself, is a good test of the whole system.
