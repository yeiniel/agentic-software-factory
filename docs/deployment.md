# Deployment: the local experiment's Adapters

The concrete Adapters for one machine (spec `specs/0002-deployment-adapters.md`). Contracts are in
`adapters/README.md`; this page is how to wire the implementations in this repository.

## Parts

| Part | Where | Notes |
|---|---|---|
| Git server | `git-server/` (container) | git daemon, anyone on the network may push; `pre-receive` refuses deletes and rewrites (except `refs/heads/factory/*`, the Factory's working branches); `post-receive` POSTs each push to the Event Source |
| Repo creation | `git-server/create-repo ROOT NAME [SEED_DIR]` | also in the image: `podman exec git-server create-repo /srv/git NAME /seed` |
| Event Source | `adapters/event-source` | `listen`: HTTP on `$EVENT_SOURCE_PORT` (8765). A new `refs/issues/<id>` is a Task `<repo>/<id>`, a push to `main` is a main-push. Status pushes to existing issues are not events |
| Task Store | `adapters/task-store` | git-native issues over `$REPO_HOST_URL`. `running`/`blocked` are labels on an open issue; `done` closes it with `Fixed-By: <commit>`; the prompt is title and body |
| Repo Host | `adapters/repo-host` | git over `$REPO_HOST_URL` (`<url>/<repo>.git`); local mirrors under `$ADAPTER_CACHE` |
| Environment Builder | `adapters/environment-builder` | builds the repo's `Containerfile` (must provide `git` and `make`), then `images/agent/` or `images/integrator/` on top; images cached per repo, commit and layer content |
| Runner | `adapters/runner` | `podman run` through the host socket (`CONTAINER_HOST`) |
| Records | `adapters/records` | JSON lines in `$RECORDS_DIR/<stream>.jsonl` |

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
- `PODMAN`: the podman executable.
- Agent and Integrator time limits are the Factory's `agent_timeout` and `integrator_timeout`.

## Target repo requirements

A `Containerfile` at the root whose image has `git` and `make`, and `make test` as the acceptance suite (ADR 0007).
The agent layer needs a base with `apk`, `apt-get` or `dnf` (to install Node and Pi 1.3.0).

## Tasks

`git issue create` in a clone, then `git push origin 'refs/issues/*'`. The push creates the Task.

## Known deviations

- Rewriting is refused everywhere except `refs/heads/factory/*`, because the Factory resets its working
  branches and re-records the integrated branch after `main` moves (the contract allows both).
- A Task whose issue is updated by a human is not re-triggered; only new issues are events.
- The Pi skills and configuration are content judged by the experiment. A real Pi against the real model server
  was smoke-tested only as far as starting, writing a session and resuming it (`--continue`) against an
  unreachable endpoint; the manual end-to-end run on the model server is still to do.
