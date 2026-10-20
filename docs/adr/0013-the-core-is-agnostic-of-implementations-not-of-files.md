---
status: accepted
---

# The core is agnostic of implementations, not of files

Supersedes ADR 0011. What we wanted from 0011 was a core that knows nothing about how Tasks are stored, where repositories live or how Environments run, so those can be swapped and the core ported. "No direct effects" went further than that and forced the core to ask an Adapter to create folders and write files for the Run Context, which the Factory itself assembles from the Task Store, the Repo Host and its own resources. The core now reaches Tasks, repositories, events, Environments and records only through Adapters, and it assembles Run Contexts itself in the **Run Context Store**, an abstraction like the Task Store and the Repo Host.

The first Run Context Store is local files on the Factory's image, behind a narrow interface in the core and not a port: one implementation makes a seam hypothetical, so it becomes a port when a second one appears.

## Considered Options

- Keep 0011 as written: every file the core writes goes through an Adapter. Rejected because the Run Context is the Factory's own product, and the Adapter would only be a file writer with no variation behind it.
- Make the Run Context Store a port now: premature, with a single implementation.

## Consequences

- The Runner and the Repo Host see the same directory as the core writes to (as `RUNNER_ROOT` already does).
- The core stays free of git, Podman, the Task Store and the network.
