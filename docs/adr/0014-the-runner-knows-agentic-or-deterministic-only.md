---
status: accepted
---

# The Runner knows agentic or deterministic, and nothing about what runs

The Runner runs an Environment on a Run Context and has one operation: `run (agentic | deterministic, context)`. The only thing it knows about the work is whether the Environment is **agentic** (the Agent harness, with access to the model server) or **deterministic** (no network, executes the Context's `run`). It knows no roles, no Integrator and no names of inputs.

The Run Context is a folder in a standard layout: `cwd/` is the working directory and holds the Containerfile; an agentic Context also has the prompt and the skills outside `cwd`; a deterministic one has a `run` script at its top level and its inputs in `cwd`. The Runner adds its own state (the Pi session) to the Context and reuses it when the core hands the same Context back. The Runner builds the Environment's image from `cwd/Containerfile` itself, so the core never sees an image and the Environment Builder is no longer a port.

## Considered Options

- Keep `run-agent` and `run-integrator`, with `provision-context --kind <role>`: the roles of the graph leak into the Runner, its contract and its conformance suite.
- Keep the Environment Builder as a port: the core had to carry an opaque image between two Adapters, and there is only one implementation.

## Consequences

- Adding a role or changing the Integrator is a change to the core's resources, not to an Adapter.
- Supersedes the Environment Builder and Runner sections of `docs/adapters/README.md` and the six-port list in `docs/design.md`.
- ADR 0012 still holds: Agent-written code runs only in containers.
