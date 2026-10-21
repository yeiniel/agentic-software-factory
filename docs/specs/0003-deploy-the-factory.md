---
status: ready-for-agent
---

# Deploy the Factory

## Problem Statement

The Factory core and its Adapters exist (specs 0001 and 0002), but nothing runs them. ADR 0010 says the Factory is a container on the Repo Host's network that launches Environments through the host's Podman socket, and spec 0002 left that container, the socket mount and the git server's deployment out of scope. To run the experiment I need one command that brings the whole stack up on my machine.

## Solution

Quadlet units (systemd-managed Podman) for the one-machine deployment, a Factory image, and an installer that renders the units for a checkout. Quadlet matches how the model server already runs (a user systemd unit) and needs nothing beyond Podman.

## User Stories

1. As a developer, I want the Factory built as a container image from this repository, so that it runs the same wherever Podman does.
2. As a developer, I want the Factory to reach the host's Podman socket, and nothing else to, so that only the trusted party can launch Environments (ADR 0010).
3. As a developer, I want the Factory and the git server on one network, with the Factory reachable as `factory` and the server as `git-server`, so that the push hook and `REPO_HOST_URL` work as configured.
4. As a developer, I want Agents on a separate network that reaches the model server and has nothing of ours attached, so that they cannot reach the git server (ADR 0012).
5. As a developer, I want the Run Contexts at the same path on the host and in the Factory container, so that the Runner's mounts resolve.
6. As a developer, I want the git server's repositories, the Adapters' mirrors and the Records to survive restarts, and the Records to be readable from the host.
7. As a developer, I want to push to the git server from the host without it being exposed beyond localhost.
8. As a developer, I want the model endpoint, model name and context window in one file outside the repo, so that changing the model needs no rebuild.
9. As a developer, I want to start, stop and read logs with `systemctl --user` and `journalctl --user`.
10. As a developer, I want `bin/model` to start the model server so that the Agents' endpoint exists.

## Implementation Decisions

- Units live in `deploy/quadlet/`; `deploy/install` renders them (substituting the checkout's path) into `~/.config/containers/systemd`, creates `~/.config/asf/factory.env` from `deploy/factory.env.example` if absent, and enables `podman.socket`.
- The Factory image is `deploy/factory.Containerfile`: Python, `git` and `podman-remote` (selected with `PODMAN=podman-remote`), the core, the Adapters, the image layers and `deploy/config.json`. The build context is the repository root.
- Networks `asf-net` (Factory and git server) and `asf-agents` (Agents, via `RUNNER_AGENT_NETWORK`; internal, ADR 0019), plus `asf-relay` for the model relay. The model server is the host's `llama-server` listening on all addresses; the `model-relay` container (on `asf-agents` and `asf-relay`) forwards to it as `host.containers.internal`, and Agents reach it as `model-relay`.
- The git server publishes 9418 on `127.0.0.1` only. It has no authentication (spec 0002).
- Out of scope: reconciling missed events, running the model server as a Quadlet unit.

## Testing Decisions

- Manual: the generated units are checked with the Quadlet generator's dry run; the stack is brought up and one Task is run end to end against the model server (the smoke test spec 0002 deferred).
- No automated tests; the Adapters' own suites cover their behaviour.
