# Agentic Software Factory

A system that drives AI agents to carry out a software change (a **Task**) on an existing repository. A Task is done when the full acceptance suite passes on `main`. Everything algorithmic runs outside the agents, and the design is kept as simple as possible.

Status: experiment. The Factory core, the Adapters for a single machine (git server, git-native-issue Task Store, Podman Environments and Runner) and the container layers are implemented.

## Documentation

- [`GLOSSARY.md`](GLOSSARY.md): the project's vocabulary.
- [`docs/design.md`](docs/design.md): the agreed design, open questions and what is still an experiment.
- [`docs/deployment.md`](docs/deployment.md): wiring the Adapters and running the stack (Quadlet) for the local experiment.
- [`docs/adr/`](docs/adr/): fixed architectural decisions.
- [`console/`](console/): the Console, a read-only view onto Tasks, Runs and metrics (`bin/console`; spec `docs/specs/0006-factory-console.md`).
