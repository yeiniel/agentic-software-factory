---
status: accepted
---

# Agents reach only the model server

An Agent's network has no route to the internet or to the host. The one way out is a relay to the model server, a container that sits on the Agents' network and on a second one that can reach the host. The Agents' network is internal; nothing else is attached to it. An Environment already holds everything the Agent needs (ADR 0006), so nothing is lost: what an Agent could still fetch from the network is exactly what makes a Run differ from the Integrator's, which has no network at all.

This supersedes the last sentence of ADR 0006, which left egress unrestricted "for later".

## Considered Options

- Keep telling the Agents they are offline in the prompts and `AGENTS.md`: it only says so. The experiments showed an Agent whose toolchain fetches on its own (`pnpm test` installs what it finds missing) quietly builds a different environment from the one the Integrator validates in, and a prompt cannot stop a tool from doing that.
- Firewall rules on the host: they enforce the same thing, but outside the repository, where the checkout cannot install or test them.
- An internal network alone: it also cuts the route to the host, so the model server becomes unreachable (`ENETUNREACH`); the relay is what keeps that one route.

## Consequences

- `ASF_MODEL_ENDPOINT` points at the relay (`http://model-relay:8080/v1`), not at `host.containers.internal`.
- The Console and the Factory keep their own networks; only the Agents are cut off.
- The relay is one more unit to run (`model-relay`); if it is down, Agents cannot reach the model and their Runs end in the Agent timeout.
