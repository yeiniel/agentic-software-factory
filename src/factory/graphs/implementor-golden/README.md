# implementor-golden

An experiment Graph: the Implementor against a fixed acceptance suite, with no Acceptance Writer. It compares
models on the same Tasks, because the specs no longer vary from Run to Run. The Implementor never sees the specs
(ADR 0003); they join the Implementor's branch at the Integrator, as in the default Graph.

`golden` is a deterministic step that stands in for the Acceptance Writer: `golden/run` applies the change an earlier
Acceptance Writer made for the Task's base commit and records it as the `acceptance-writer` branch. It is generated
by `tools/make-golden` from Writer branches that stayed on the git server, so edit the tool's input, not the script.
A base commit it has no specs for blocks the Task with reason `no-golden`, before any Agent runs. One attempt per
loop and one Run: a failed Task is `blocked`, so each Task is one sample.

| Repo | Task id | Base commit |
|---|---|---|
| `pydantic-extra-types` | `8f539106-1bc0-4b59-915e-5140f1672bc6` | `288cff2b47ba737b9caa95d3bedc9b4e21c658e0` |
| `pydantic-extra-types-v9` | `942d8e03-8652-47d0-9264-31e30bceaa77` | `5ca25f2150e13ede6f03a1b7ecdd076a59280070` |
| `ufo` | `fd0f933a-c4c0-4821-92f1-106ed2b8e4bb` | `22ab16a9f53cf3b7f758c6a90cfba1d7bd859e47` |
| `ufo-v2` | `7fe736ac-56f1-4056-afcb-19932ca1d6d8` | `ff102c93694888b5695f23ea28c808e6bdf1d427` |

Each of them reached `done` with its Writer's specs. `tailwind-merge` has validated specs but no Implementor that
passed them, so it is left out.

## Running it

1. A repository with `main` at the base commit: `bin/new-golden-repo NAME SOURCE_GIT_DIR BASE_COMMIT`. Publishing
   advances `main`, so every sample needs a fresh repository.
2. A Task in it, with the original Task's text: `bin/task NAME TITLE -m BODY`.
3. In `deploy/config.json`, for the Factory image (then `bin/restart`):
   `"graph": "/opt/asf/src/factory/graphs/implementor-golden"`, `"agent_timeout": 2700`, `"task_concurrency": 2`.
   Two Tasks at once need two model server slots (`bin/model` starts two) and Tasks on different repositories.
4. Compare the Runs with the baseline in the Console: outcome, wall-clock, timeouts, tokens.
