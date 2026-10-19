---
status: ready-for-agent
---

# Deployment: adapters for the local experiment

## Problem Statement

The Factory core (spec 0001) deliberately does nothing itself. To run the experiment I need a concrete deployment: a git server that holds repositories and Tasks and signals pushes, an Environment that is a container built from the target repo's own `Containerfile`, Pi inside it talking to a local model server, and an Integrator that runs in its own container. Today none of that exists.

## Solution

A set of Adapter implementations, plus the container layers and the supporting services they need, that satisfy the contracts in spec 0001 for one local machine. Tasks are git-native issues on a self-hosted git server (ADR 0009). Every Agent and Integrator runs in a Podman container (ADRs 0006, 0010, 0012). Inference is the local llama.cpp server (ADR 0008). Vocabulary is in `GLOSSARY.md`, the design in `docs/design.md`, and the decisions in `docs/adr/`.

## User Stories

1. As a developer, I want a self-hosted git server on the Factory's network, so that I can push code and Tasks without GitHub.
2. As a developer, I want that server to signal each push to the Event Source adapter, so that the Factory reacts without polling.
3. As a developer, I want a Task to be a git-native issue in the target repo, so that Tasks travel with the code over ordinary push and fetch.
4. As a developer, I want the Task Store adapter to read an issue's title and body as the prompt, so that I write Tasks with `git issue create`.
5. As a developer, I want running and blocked to be labels on the issue and done to be closing it with a reference to the commit on `main`, so that the Task's status is visible in plain git-native-issue tooling.
6. As a developer, I want the Task Store adapter to push those status changes back to the server, so that I see them from any clone.
7. As a developer, I want the Repo Host adapter to create a role's branch from a base, so that each Agent has a pre-created branch.
8. As a developer, I want the Repo Host adapter to hand out a single-branch clone with no remote and none of the issue refs, so that an Agent can't see the other branch, the server or the Tasks.
9. As a developer, I want the Repo Host adapter to record an Agent's changes onto its branch from the Run Context, so that Agents never run git.
10. As a developer, I want the Repo Host adapter to fast-forward `main` only from a branch given by the Factory, so that all writes to `main` come from the Factory.
11. As a developer, I want the Environment Builder to build the repo's `Containerfile` at a commit, so that the repo's tech stack is the repo's own business.
12. As a developer, I want the builder to require `git` and `make` in that image and fail clearly if they are missing, so that a bad repo is reported rather than hanging.
13. As a developer, I want the builder to layer the agent harness on top of the repo's image, so that the repo knows nothing about Pi.
14. As a developer, I want the harness layer to install Pi along with the runtime it needs, so that it runs on any base image.
15. As a developer, I want the harness layer to configure Pi to use the local model server, so that no API key is needed.
16. As a developer, I want the harness layer to carry the Implementor's and Acceptance Writer's skills, so that both roles share one image and differ only by prompt.
17. As a developer, I want the Acceptance Writer's skill to teach writing behaviour-focused specs, run through `make test`, that fail with output that explains what went wrong, so that Feedback is useful without interpretation.
18. As a developer, I want the harness layer's entrypoint to read the prompt from the Run Context, run Pi in the clone as the working directory and resume the session if one exists, so that a retry continues the same conversation.
19. As a developer, I want the builder to also layer the Integrator tooling onto the repo's image, so that the Integrator runs against the repo's real dependencies.
20. As a developer, I want the Integrator tooling to start as a POSIX shell script that needs only `git` and `make`, so that it works in any repo's image.
21. As a developer, I want the Integrator to check the new specs are red on base, merge the branches, rebase onto the latest `main`, run the full `make test`, and report a verdict that says which check failed, so that the core can route the retry.
22. As a developer, I want the Integrator to return its output verbatim and the resulting branch, so that the core can use them as Feedback and for publishing.
23. As a developer, I want the built images cached per repo and commit, so that retries don't rebuild.
24. As a developer, I want the Runner adapter to run a container through the host's Podman socket with the Run Context mounted and a time limit, so that the Factory can launch Agents without nesting containers.
25. As a developer, I want the Runner to attach Environments to a network that reaches the local model server and carry no credentials for the git server, so that Agents have no way to reach the repositories.
26. As a developer, I want the Runner to return the exit status, the output and a pointer to the Pi session transcript, so that the core can record them.
27. As a developer, I want the Runner to run the Integrator on a Run Context without Pi and without access to the git server, so that Agent-written code never gets host or repo access.
28. As a developer, I want the Event Source adapter to turn a server push event into a Task or `main` event for the core, so that the core stays ignorant of git.
29. As a developer, I want a Records adapter that appends each Run's events to files outside the repo, so that records can be read by a person or an evaluator.
30. As a developer, I want the Pi session state kept in a local folder per role per Task and mounted into the Environment, behind the Runner's interface, so that the storage can be swapped later.
31. As a developer, I want each adapter to ship with the core's contract tests passing against it, so that a replacement implementation can prove conformance.
32. As a developer, I want a way to create a repository on the server and seed its first commit, so that I can set up a target repo for the experiment.

## Implementation Decisions

- One implementation per port, each an executable with the contract from spec 0001: the Event Source (a listener for the git server's push events), the Task Store (git-native-issue), the Repo Host (git over the server, with the hook for events), the Environment Builder (Podman build plus layers), the Runner (Podman run via the socket), and Records (files).
- The git server is a container running a git daemon, with a hook that sends each push to the Event Source adapter over the network. It runs in the Factory's network. The human owner may write to it; the Factory is the only automated writer. Refs may not be rewritten or deleted.
- The target repo must provide a `Containerfile` at its root whose image has `git` and `make`, and `make test` as its acceptance suite (ADR 0007).
- The agent harness layer holds Pi and its runtime, Pi configuration for the local model server (endpoint, model name and context window as configuration, not hardcoded), both roles' skills and an entrypoint. Skills are versioned in this repo.
- The Integrator layer is separate from the agent layer and has no Pi.
- Run Context layout: a directory with the prompt, the clone or clones, and the session state, as in `docs/design.md`.
- The Runner attaches Environments to a network that reaches only the model server and passes no git credentials. An Environment's clone has no remote, so it couldn't reach the server even if it could route there.
- Environment time limits and the model server's settings are configuration.
- The Factory's own image, the Podman socket mount and the git server container's deployment are out of this spec's scope except for the hook and the interfaces the Factory expects.
- Pi is the Pi coding agent (pi.dev), invoked as a command-line executable. Model server details are in `docs/model-server.md`.

## Testing Decisions

- Each Adapter is tested against the core's contract tests plus its own behaviour tests, through its executable interface and not its internals.
- Repo Host and Task Store are tested against real git in temporary directories: branch creation, single-branch clones with no remote and no issue refs, recording changes, fast-forwarding `main`, and status changes round-tripping through git-native-issue.
- The Environment Builder and Runner are tested against real Podman with a trivial test image and the layered entrypoint stubbed. The tests assert on mounts, the time limit, the network, the exit status and the `git` and `make` check. They don't call a model.
- The Integrator is tested with real git and a tiny `make test` in a fixture repo: a branch pair that merges and passes, one with a conflict, one with specs not red on base, and one with a red suite.
- The git server and its hook are tested with one integration test: push, and the event arrives.
- A real Pi against the local model server is smoke-tested manually once; it isn't part of the automated suite.
- No prior art in the repository.

## Out of Scope

- The Factory core's logic (spec 0001).
- The experiment harness: sample repos and Tasks, and the external evaluator.
- Deployment of the Factory container itself.
- Restricting egress beyond the model server network.
- Event reliability and recovery of missed events.
- Authentication on the git server.

## Further Notes

- The model server runs on the host as a service; its hardware, models and settings are in `docs/model-server.md`.
- The Integrator is deliberately replaceable: the core sees only a Run Context in and a verdict plus branch out.
- Skills and Pi configuration are content, and their quality is judged by the experiment rather than by unit tests.
