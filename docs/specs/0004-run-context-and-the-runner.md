---
status: ready-for-agent
---

# Run Context and the Runner

## Problem Statement

The Runner's interface carries the Factory's graph: it takes `--kind implementor|acceptance-writer|integrator`, has separate `run-agent` and `run-integrator` operations, keys session state by role, and parses the Integrator's verdict files. The core joins paths below the Run Context (`work`, `base`, `main`, `result`) and carries an image tag from the Environment Builder to the Runner. Role skills and the Integrator script are baked into image layers. Changing a role or the Integrator therefore means changing an Adapter, its contract and its conformance suite.

## Solution

The core assembles every Run Context itself in the Run Context Store and asks the Runner to run it (ADRs 0013, 0014, 0015). The Runner has one operation, `run`, and knows only whether the Environment is agentic or deterministic. Roles, their skills and the Integrator are resources of the core. Vocabulary is in `GLOSSARY.md`.

## Run Context layout

A folder. The Runner creates nothing in it except its own state.

```
<context>/
  cwd/            the working directory; holds Containerfile at its root
  prompt          agentic only: the composed prompt (role instruction, Task, Feedback)
  system-prompt   agentic only: the role's rules that always apply, appended to the Agent's system prompt
  skills/         agentic only: the role's skills, outside cwd
  run             deterministic only: the executable to run, with cwd as its working directory
  out/            deterministic only: where `run` leaves its results
  <runner state>  added and reused by the Runner (e.g. the Pi session)
```

- Agentic: `cwd` is the project clone on the role's branch.
- Deterministic (the Integrator): `cwd` holds `base`, `main`, `implementor`, `acceptance-writer` (names are the core's), plus a copy of `main`'s `Containerfile` at its root.
- Context paths: `contexts/<task>/implementor`, `contexts/<task>/acceptance-writer`, `contexts/<task>/integrate-<run>-<attempt>`. Agent Contexts live across the Task's Runs; the Integrator gets a fresh Context per attempt. Contexts are kept after the Task for analysis.

## Runner contract

- `run --type agentic|deterministic --context DIR --timeout S [--build-timeout S]` → `{"exit_status","timed_out","output"}` plus:
  - agentic: `"transcript"`, the newest session transcript of this run;
  - deterministic: `"files"`, the text of each top-level regular file in `out/`, size-capped.
- The Runner builds (or reuses) the image from `cwd/Containerfile`, requires `git` and `make` in it, and for the agentic type layers the Pi harness on top. The build timeout is separate from the run timeout; a build failure is an infrastructure error.
- Agentic: model-server network, no git credentials, `cwd` as the working directory, skills from `skills/`, prompt from `prompt`, session state in the Context, resumed when present. Deterministic: no network, executes `run` in `cwd`.
- The Runner knows no roles and none of the input or result names.

## Implementation Decisions

- `provision-context`, `run-agent`, `run-integrator` and the Environment Builder port are removed, with no compatibility shim. `adapters/environment-builder` becomes an internal module of the Runner.
- A Run Context Store module in the core, over local files on the Factory image. Interface: create a Context, write a file into it, give the path for the Repo Host to check out into, hand the same Context back. It is not a port.
- The core's resources live in `src/factory/resources/`: each role's instruction and skills, and the Integrator `run` script. `images/agent/skills` and `images/integrator/` are removed; the agent layer holds only Pi and its configuration.
- A Verdict module in the core reads the Integrator's `files` (`result`, `failed_check`, `spec_output`, `output`) and validates them; `blame` consumes it. The stand-in drops its own parser.
- Before a retry the core alters the existing Agent Context (the new `prompt`), checks `cwd` out again from the base (spec 0005) and hands it back; the Pi session in the Context is kept.
- The Integrator leaves its integrated clone in `out/`; the core passes that path to the Repo Host `record`.
- `docs/adapters/README.md`, `docs/design.md`, the Runner conformance suite, the stand-in and the deploy files change in the same commit.

## Testing Decisions

- Runner conformance: both types through the one `run` operation against real Podman with a trivial image (skipped without Podman), asserting the network, the time limit, the exit status, `files` from `out/`, the transcript, session reuse when the same Context is handed back, and the `git`/`make` check.
- Core: black-box Runs against the stand-in as in `tests/test_runs.py`, now asserting what the core writes into each Context (prompt, skills, `run`, `cwd`), that retries reuse the Context with an updated prompt, and that no Runner call names a role.
- Verdict: table tests per `failed_check` and for malformed files.

## Out of Scope

- A Run Context Store port.
- A read side for Records, so `bin/follow` stops reading storage directly (it needs a small fix for the new session location).
- One shared definition of the Adapter call convention.
- Context cleanup.

## Open Questions

- The build context for a deterministic Environment: `cwd` holds four clones, so a Containerfile that `COPY`s repo files would fail. The Runner may need to build from the repo's directory instead, or the core may need to place what the Containerfile expects at the `cwd` root.
- The cache key for images when the Containerfile comes from `cwd` instead of a commit.
- Whether Pi finds the `AGENTS.md` and `.agents/skills` of the project in `cwd` alongside `--skill` paths from the Context (skills are confirmed; `AGENTS.md` discovery is not).
