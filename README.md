# Agentic Software Factory

A system that drives AI agents to carry out a software change (a **Task**) on an existing repository. A Task is done when the full acceptance suite passes on `main`. Everything algorithmic runs outside the agents, and the design is kept as simple as possible.

Status: experiment. The Factory core, the Adapters for a single machine (git server, git-native-issue Task Store, Podman Environments and Runner), the Console and the container layers are implemented. The manual end-to-end run against the real model server is still to do (see "Known deviations" in [`docs/deployment.md`](docs/deployment.md)).

## How it works

A Task is a git-native issue pushed to a self-hosted git server. The push is an event, and the **Factory** (a container holding the Podman socket) takes it from there:

1. An **Acceptance Writer** and an **Implementor**, two Agents running Pi in containers, work *blind* in parallel: one writes acceptance tests, the other the change.
2. **Acceptance Test Validation** checks that the new tests fail on the base, then an **Integrator** merges both branches and runs `make test`. Retries are nested loops with Feedback.
3. A green suite fast-forwards `main` and the Task is done. Otherwise the Task is blocked, with a reason.

The Factory core has no direct effects. Everything outside it (git, the issue store, Podman, event delivery, records) is an **Adapter**, an executable behind a command-line contract. Every step is recorded as OTLP and shown in the **Console**, a read-only TUI.

```
git push refs/issues/*  ->  git server  --hook-->  Event Source ---> Factory core
                                                                        |  Adapters: Task Store, Repo Host,
                                                                        |  Runner (Podman), Records
                                                  Agents / Integrator <-+      \--> Console (OTLP) --> TUI
```

Read [`GLOSSARY.md`](GLOSSARY.md) for the vocabulary (used exactly throughout) and [`docs/design.md`](docs/design.md) for the design.

## Repository layout

| Path | What |
|---|---|
| `src/factory/` | the Factory core: the Graph interpreter (the default Graph is `resources/graph.json`, shaped by `graph.schema.json`); talks to the world only through Adapter ports |
| `adapters/` | the Adapters: launchers (`event-source`, `task-store`, `repo-host`, `runner`, `records`, `records-otlp`) over the typed `asf_adapters` package. Contracts in [`docs/adapters/`](docs/adapters/README.md) |
| `console/` | the Console: OTLP receiver, SQLite store and TUI (`asf_console`) |
| `git-server/` | the git server image, its hooks and `create-repo` |
| `images/agent/` | the Agent container layer (Pi harness) built on top of a target repo's own image |
| `deploy/` | the Factory and Console images, config, and Quadlet units |
| `bin/` | operator scripts: `up`, `down`, `restart`, `model`, `new-repo`, `task`, `console` |
| `tests/` | scenarios at the seams, golden transcripts, stand-ins; `console/tests/` and `tools/` hold the Console tests and gate tooling |
| `docs/` | design, ADRs, specs, deployment and research notes |

## Quickstart

You need Linux with systemd (user units), [Podman](https://podman.io/) with `podman.socket`, [`uv`](https://docs.astral.sh/uv/) (for the Console TUI) and a local `llama-server` with a model of your choice (edit `bin/model` for the model path; see [`docs/model-server.md`](docs/model-server.md)).

```sh
# 1. Configure: the first install writes ~/.config/asf/factory.env from deploy/factory.env.example
deploy/install
$EDITOR ~/.config/asf/factory.env      # model endpoint, model name, context window

# 2. Start the stack: Console, Factory, git server (--model also starts llama-server)
bin/up --model

# 3. Create a repository on the git server (SEED_DIR becomes `main`).
#    It needs a Containerfile whose image has git and make, and `make test` as the acceptance suite.
bin/new-repo myrepo ~/path/to/seed

# 4. Give the Factory a Task: this creates the issue and pushes it, which starts the Task
bin/task myrepo "Add a greeting command" -m "greet NAME prints Hello, NAME"

# 5. Watch it
bin/console                            # Tasks, a Task's Run tree and log, Metrics
journalctl --user -u factory -f

# Afterwards
bin/restart                            # rebuild and restart after changing the core, Adapters or layers
bin/down --model                       # stop everything
```

The result lands as a fast-forward of `main` in `git://localhost:9418/myrepo.git`. [`docs/deployment.md`](docs/deployment.md) has the configuration, the target repo requirements and the known deviations.

## Development

Tools are pinned: system tools in `mise.toml` (`mise install`), Python tools and dependencies in `uv.lock` (`uv sync`).

```sh
make check      # the quality gate: format, lint, types, dead code, shell, Containerfiles, Quadlet, links, tests
make test       # the test suite alone, with 100% line and branch coverage required
make audit      # dependency vulnerability audit (needs the network)
make mutate     # on-demand mutation testing (cosmic-ray)
make hooks      # install the git pre-commit hook that runs `make check`
```

`make check` takes several minutes: the Podman-backed scenarios build real images. Products are tested only at their seams ([ADR 0018](docs/adr/0018-products-are-tested-at-their-seams.md), [spec 0007](docs/specs/0007-seam-tested-products-and-the-quality-gate.md)): the core through the Adapter ports and the Run Contexts it writes, an Adapter through its command line, the Console through OTLP and the TUI. The core's scenarios are asserted against the golden transcripts in `tests/goldens/`; after an intended behaviour change regenerate them with `UPDATE_GOLDENS=1 make test` and review the diff. There are no coverage exclusions: code no scenario reaches is deleted.

## Documentation

- [`GLOSSARY.md`](GLOSSARY.md): the project's vocabulary.
- [`docs/design.md`](docs/design.md): the agreed design, open questions and what is still an experiment.
- [`docs/deployment.md`](docs/deployment.md): wiring the Adapters and running the stack (Quadlet) for the local experiment.
- [`docs/adapters/README.md`](docs/adapters/README.md): the Adapter contracts.
- [`docs/model-server.md`](docs/model-server.md): the local inference server.
- [`docs/adr/`](docs/adr/): fixed architectural decisions.
- [`docs/specs/`](docs/specs/): the specs the implementation follows (the Console is spec 0006, the test strategy and quality gate spec 0007).
- [`AGENTS.md`](AGENTS.md): instructions for coding agents working on this repository.
