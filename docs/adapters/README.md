# Adapter contracts

Each Adapter port is an external executable (ADRs 0013, 0014). The Factory configures each as a command
prefix (`config.json`: `"adapters": {"repo-host": ["/path/to/exe", ...]}`) and calls

    <command...> <op> [--name value ...]

with an optional JSON body on stdin and a JSON object on stdout. A non-zero exit, unparseable
stdout or exceeding the deadline is an **infrastructure error**: the Task is set to blocked with
reason `infrastructure`, and the Run does not count toward the cap. All other failures (red
verdicts, Agent failures, timeouts reported by the Runner) are returned as data.

`repo` is passed to Repo Host; `task` and `run` identify a Run.

## Implementations

The real Adapters are in `adapters/` and are wired up in `../deployment.md`. Task ids are `<repo>/<issue id>`.

## Conformance

`tests/conformance/` holds one suite per port. It runs against the scripted stand-ins and the real Adapters (Podman ones skip without Podman); to test
another implementation set `ADAPTER_<PORT>` (e.g. `ADAPTER_REPO_HOST='cmd args'`) and, if its identifiers
differ, `ADAPTER_<PORT>_FIXTURE` (JSON overriding the defaults in `tests/conformance/conftest.py`).
The Repo Host suite mutates its repository, so use a disposable one. A real Event Source needs
`ADAPTER_EVENT_SOURCE_TRIGGER`, a shell command that makes it emit an event. The Runner suite builds trivial Contexts and checks the shape of both result types.

## Event Source

- `listen`: long-running; prints one JSON event per line: `{"type":"task","task":T,"repo":R}` or
  `{"type":"main-push","repo":R,"commit":C}`. When it exits 0 the Factory finishes queued work and exits.

## Task Store

- `get-prompt --task T` → `{"prompt": str}`
- `set-status --task T --status todo|running|done|blocked`, body optional: `{"commit"}` for done,
  `{"history":[...], "reason"?}` for blocked → `{}`

## Repo Host

- `main-head --repo R` → `{"commit"}`
- `create-branch --repo R --name N --base C` → `{"commit"}`; an existing branch is reset to `C`, but `main` is refused
- `checkout --repo R (--branch B | --commit C) --dest DIR` → `{"commit"}`: a single-branch clone, no remote
- `record --repo R --branch N --from DIR` → `{"commit","changed"}`: commits the directory's changes onto the branch
- `fast-forward-main --repo R --branch N --expect-main C` → `{"advanced": bool, "head"}`; must not
  advance if `main` is no longer `C`

## Runner

One operation (ADR 0014). The Run Context is a folder the core assembles in the Run Context Store (ADR 0013)
and hands over by path; the Runner knows no roles and none of the names inside `cwd`.

- `run --type agentic|deterministic --context DIR --timeout S [--build-timeout S] [--traceparent T]` →
  `{"exit_status","timed_out","output"}` plus, for `agentic`, `"transcript"` (the newest session transcript
  of this run), `"usage"` (`{"turns","tool_calls","input_tokens","output_tokens"}` of this run, when the session had a model turn) and, for `deterministic`, `"files"` (the text of each top-level regular file in `out/`, size-capped).

The Context's layout:

    cwd/       the working directory; holds Containerfile at its root
    prompt     agentic: the composed prompt
    skills/    agentic: one folder per skill, outside cwd
    run        deterministic: the executable, run with cwd as its working directory
    out/       deterministic: where `run` leaves its results (created by the core)

The Runner builds, or reuses, the image from `cwd/Containerfile` (build context `cwd`, cache key the
Containerfile's content, plus the harness layer for the agentic type), requires `git` and `make` in it, and
runs it. A build failure or exceeding `--build-timeout` is an infrastructure error. Agentic: the model-server
network, no git credentials, session state added to the Context and resumed when the same Context is handed
back. Deterministic: no network. A timeout is reported as data (`timed_out`).

`--traceparent` (W3C, agentic only) is optional and opaque to the Runner: while the Environment runs and
`$OTEL_EXPORTER_OTLP_ENDPOINT` is set, it forwards each new Pi session entry as an OTLP log record
(`asf.source=transcript`, body the raw JSONL line) linked to that trace context. An unreachable endpoint never
fails the run (spec 0006).

## Run Context Store

Not a port: local files in the core (`src/factory/contexts.py`). The core owns the names inside a Context
(`docs/specs/0004-run-context-and-the-runner.md`): `contexts/<task>/<role>` for each Agent and
`contexts/<task>/validate-<run>-<attempt>` for each Acceptance Test Validation (`cwd` holds `base` and `acceptance-writer`) and
`contexts/<task>/integrate-<run>-<attempt>` for each Integrator pass. The Integrator's inputs in `cwd` are
`base`, `main`, `implementor`, `acceptance-writer` plus a copy of `main`'s `Containerfile`; it leaves
`result`, `failed_check` and `output` in `out/` and the integrated clone in `out/integrated`.

## Records

- `append --stream S [--run N]`, body: one JSON event → `{}`. Streams: `task/<id>` and `factory`.

Implementations: `adapters/records` (JSON lines under `$RECORDS_DIR`, for tests and running without the Console)
and `adapters/records-otlp` (OTLP/HTTP JSON to `$OTEL_EXPORTER_OTLP_ENDPOINT`, ADR 0017). The OTLP one is
stateless: a `started` event becomes a log record and a `finished` one a complete span (start = now - `duration`),
both with the event's `trace`, `id` and `parent`, so the receiver pairs them; every other event is a log record
whose attributes are the event's fields (`asf.<field>`, nested objects as `asf.<field>.<key>`). An unreachable
receiver is an error, hence an infrastructure error for the Task.

### Events

Every event of a `task/<id>` stream has `kind`, `run` (or null) and `trace` (32 hex characters, one per Task).
Spec 0006 added the following; earlier kinds and fields are unchanged (`run-started`, `attempt`, `agent`,
`branch-recorded`, `validation`, `integrator`, `fast-forward`, `run-finished`, `feedback`, `loop-exhausted`,
`infrastructure-error`).

- `task-received` `{repo}`: the Event Source reported the Task.
- `task-status` `{status, reason?, commit?}`: after every status written to the Task Store. `reason` for
  `blocked` is `loop-exhausted`, `max-runs` or `infrastructure`.
- `started` / `finished` `{id, parent, span, name, ...}`: a stretch of work. `id` is 16 hex characters, `parent`
  is the enclosing span's `id` (null for a Run), `span` is `run`, `loop`, `attempt` or `activity`, and `name` is
  the Run number, `writer`/`implementor`, the attempt number, or `assemble`, `agent`, `validate`, `integrate`,
  `publish`. An `agent` Activity also has `role`. `finished` adds `duration` (seconds) and `outcome`: Run
  `green`/`red`, loop `succeeded`/`exhausted`, attempt `green` or the failed check, Activity `ok`, `green`, `crashed`,
  `timed-out`, the failed check, `advanced` or `main-moved`; `error` if the block raised.
- `loop-feedback` `{loop, attempt, feedback}`: the Feedback an inner loop's next attempt starts with.
- The `agent` event carries the Runner's `usage` when it reports one.

The `traceparent` the core passes the Runner for an agentic Environment is `00-<trace>-<id of the agent Activity>-01`.
