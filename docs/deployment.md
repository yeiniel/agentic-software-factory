# Deployment: the local experiment's Adapters

The concrete Adapters for one machine (spec `specs/0002-deployment-adapters.md`). Contracts are in
`adapters/README.md`; this page is how to wire the implementations in this repository.

## Where the code lives

`adapters/<name>` are one-line launchers; the logic is the typed `asf_adapters` package (`adapters/asf_adapters/`),
so the command lines below are unchanged. The Console's receiver and TUI start through `asf_console.serve` and
`asf_console.tui` (`bin/console` runs the latter). Tests exercise all of them only through those command lines (ADR 0018).

## Parts

| Part | Where | Notes |
|---|---|---|
| Git server | `git-server/` (container) | git daemon, anyone on the network may push; `pre-receive` refuses deletes and rewrites (except `refs/heads/factory/*`, the Factory's working branches); `post-receive` POSTs each push to the Event Source |
| Repo creation | `git-server/create-repo ROOT NAME [SEED_DIR]` | also in the image: `podman exec git-server create-repo /srv/git NAME /seed` |
| Event Source | `adapters/event-source` | `listen`: HTTP on `$EVENT_SOURCE_PORT` (8765). A new `refs/issues/<id>` is a Task `<repo>/<id>`, a push to `main` is a main-push. Status pushes to existing issues are not events |
| Task Store | `adapters/task-store` | git-native issues over `$REPO_HOST_URL`. `running`/`blocked` are labels on an open issue; `done` closes it with `Fixed-By: <commit>`; the prompt is title and body |
| Repo Host | `adapters/repo-host` | git over `$REPO_HOST_URL` (`<url>/<repo>.git`); local mirrors under `$ADAPTER_CACHE` |
| Runner | `adapters/runner` | builds `cwd/Containerfile` of a Run Context (must provide `git` and `make`; `images/agent/` on top for Agents; images cached by content) and `podman run`s it through the host socket (`CONTAINER_HOST`) |
| Records | `adapters/records-otlp` (deployed), `adapters/records` | OTLP to the Console's receiver (ADR 0017), or JSON lines in `$RECORDS_DIR/<stream>.jsonl` |
| Console | `console/` (container `console`, TUI `bin/console`) | receiver: OTLP on `asf-net:4318`, API on host `127.0.0.1:4319`; store `~/.local/share/asf/console/console.db`; see below |

## Configuration (environment)

- `REPO_HOST_URL`: base URL of the git server, e.g. `git://git-server`. Repositories are `<url>/<repo>.git`.
- `ADAPTER_CACHE`: where Repo Host and Task Store keep their mirrors (default `~/.cache/asf`).
- `EVENT_SOURCE_PORT` for the Event Source; `EVENT_SOURCE_URL` for the git server's hook (`http://factory:8765`).
- `RUNNER_ROOT`: Run Contexts and Pi session state (`sessions/<task>/<role>`). It must be the same path on the
  host and inside the Factory container, because Podman resolves mounts on the host.
- `RUNNER_AGENT_NETWORK`: Podman network for Agents; it must reach the model server and nothing else of ours.
  Agents are given no git credentials, and their clone has no remote. The Integrator runs with `--network none`.
- `ASF_MODEL_ENDPOINT`, `ASF_MODEL_NAME`, `ASF_MODEL_CONTEXT_WINDOW`: the model server (`model-server.md`), passed
  into Agent containers; the harness entrypoint writes Pi's `models.json` from them.
- `ASF_IMAGES_DIR`: alternative layers (the tests use stubs).
- `OTEL_EXPORTER_OTLP_ENDPOINT`: the Console's receiver (`http://console:4318`, in `factory.env`). With `records-otlp` an unreachable receiver blocks Tasks with reason `infrastructure`; the Runner also forwards Pi transcripts there and carries on if it is down.
- `CONSOLE_MODEL_URL` (Console container): the model server whose `/metrics` and `/slots` it scrapes while a TUI is connected (`bin/model` starts `llama-server` with `--metrics`).
- `PODMAN`: the podman executable.
- Agent and Integrator time limits are the Factory's `agent_timeout` and `integrator_timeout` (the latter also bounds Acceptance Test Validation). The attempt budgets (the Run cap, the Writer and Implementor loops) are fields of the Graph, not of the config.
- `task_concurrency` (config, default 1): how many Tasks run at once, never two of one repository (ADR 0021). Set it to the model server's slots divided by the Agents a Task keeps running (2 in the default Graph); `bin/model` and `ASF_MODEL_CONTEXT_WINDOW` stay as `model-server.md` says.
- `graph` (config): the Graph folder, `src/factory/resources/` by default. The Factory validates it against `graph.schema.json` and checks it once, at start, and exits non-zero with the reason on an invalid one; a changed Graph takes a restart. Its version is the commit of this repository it was loaded from: `graph_version` in the config, else `ASF_GRAPH_VERSION` (`deploy/install` renders the current commit into the Quadlet unit and `bin/restart` renders it again; uncommitted changes under `src/factory/resources/` add `-dirty`), else `unversioned`. The `task-received` Record carries it.

## Running it

Quadlet units in `deploy/quadlet/` (spec `specs/0003-deploy-the-factory.md`):

| Unit | What |
|---|---|
| `git-server` | the git server image; port 9418 on `127.0.0.1` for you to push; volume `asf-git` |
| `console` | `deploy/console.Containerfile`: the receiver, standard library only; OTLP for the Factory on `asf-net`, the API on `127.0.0.1:4319`; store `~/.local/share/asf/console/console.db` |
| `factory` | `deploy/factory.Containerfile`; the host's Podman socket, Run Contexts and Records under `~/.local/share/asf/`; volume `asf-cache` |
| `asf-net`, `asf-agents`, `asf-relay` | networks: Factory and git server; Agents (internal); the model relay's way to the host |
| `model-relay` | `deploy/model-relay.Containerfile` | TCP relay from the Agents' network to the model server; Agents use `ASF_MODEL_ENDPOINT=http://model-relay:8080/v1` (ADR 0019) |

```
deploy/install                       # render the units for this checkout, enable podman.socket
$EDITOR ~/.config/asf/factory.env    # model endpoint, name, context window
bin/model                            # start llama-server on the host (port 8080, all addresses)
systemctl --user start console factory git-server    # or bin/up
journalctl --user -u factory -f
bin/console                          # the TUI: Tasks, a Task's Run tree and log, Metrics (needs uv)
```

The Console replaced `bin/follow`. Back up its store by copying `console.db`; there is no rotation. An existing
`~/.config/asf/factory.env` needs `OTEL_EXPORTER_OTLP_ENDPOINT=http://console:4318` added (see `deploy/factory.env.example`);
to run without the Console point `deploy/config.json` back at `adapters/records`. Restart `llama-server` (`bin/model stop; bin/model`) to get `--metrics`.

Set up a target repo (it needs a `Containerfile` and `make test`), then push a Task:

```
podman exec git-server create-repo /srv/git myrepo
git -C ~/path/to/myrepo push git://localhost:9418/myrepo.git main
git clone git://localhost:9418/myrepo.git && cd myrepo
git issue create ...; git push origin 'refs/issues/*'
```

After changing the Factory, Adapters or layers, `systemctl --user restart factory` rebuilds the image.
The audit trail is the Console's store; `~/.local/share/asf/records/` only fills when `adapters/records` is configured.

## Target repo requirements

A `Containerfile` at the root whose image has `git` and `make`, and `make test` as the acceptance suite (ADR 0007).
The image is the Agents' whole toolchain and they run offline: the project's dependencies must be installed and its default `python`, `node` and the like must see them. An `AGENTS.md` at the root can say where the tools are; Pi loads it.
The agent layer needs a base with `apk`, `apt-get` or `dnf` (to install Node and Pi 1.3.0).

## Tasks

`git issue create` in a clone, then `git push origin 'refs/issues/*'`. The push creates the Task.

## Known deviations

- Rewriting is refused everywhere except `refs/heads/factory/*`, because the Factory resets its working
  branches and re-records the integrated branch after `main` moves (the contract allows both).
- Agents reach the model server through `host.containers.internal`; that route, and `llama-server` listening on
  all addresses, have not been checked from inside an Agent container.
- A Task whose issue is updated by a human is not re-triggered; only new issues are events.
- The Pi skills and configuration are content judged by the experiment. A real Pi against the real model server
  was smoke-tested only as far as starting, writing a session and resuming it (`--continue`) against an
  unreachable endpoint; the manual end-to-end run on the model server is still to do.
