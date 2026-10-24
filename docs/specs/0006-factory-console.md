---
status: implemented
---

# Factory Console

## Problem Statement

The only window into a Task is `bin/follow`, a terminal tail of the Records and the Pi transcripts. It shows one Task at a time, from files on one machine. It cannot answer which Tasks are running, blocked or done, where a Run spent its time, how often loops exhaust or integrations fail, or whether the model server is the bottleneck. Records carry one timestamp per event and no durations, so even the data for those answers is thin. The design already commits to auditable records of every actor (spec 0001, stories 33 and 34); this spec makes them observable. The operator is the first user. ADR 0017 records the decision to carry the data as OTLP.

## Solution

A **Console**: a read-only view onto Tasks, Runs and metrics, in two parts under `console/`:

- a **receiver** that takes OTLP/HTTP, stores it and serves a local HTTP API with a live stream;
- a **TUI**, `bin/console`, a client of that API. A web view could later be another client.

The Console never writes to the Factory, the Task Store or the Repo Host and has no effect on a Run. It is not a port of the core (ADR 0013). The core only emits richer events through the Records port, and the Runner forwards transcripts.

## The views

1. **Tasks**: every Task with status (todo, running, done, blocked), Run number, current Activity, age and last event, live.
2. **Task**: the Run → loop → attempt → Activity tree with durations and outcomes, live, next to a log pane that merges the Factory's events and the Agents' transcripts, with the Feedback shown at each retry.
3. **Metrics**: task timings (time to done, per Run, per Activity, per Agent); Factory performance (Runs per Task, attempts per loop, loop-exhaustion and integration-failure rates, tokens and tool calls per Agent); model server state (slot occupancy, queue depth, tokens per second).

## Data flow

- The core emits events through the Records port; the OTLP Records implementation exports them to the receiver. The JSONL implementation stays as the other implementation.
- One trace per Task. Run, loop, attempt and Activity are nested spans.
- The exporter is a process spawned per event and keeps no state. On `started` it exports an OTLP log record; on `finished` a complete span with the start time, duration and outcome. Both carry the event's `id` and `parent`, so the receiver pairs them and shows a started-but-unfinished Activity as running.
- The Runner follows the Pi session file for the length of an agentic Environment and exports each message as an OTLP log record, linked to the attempt by an optional `--traceparent` the core passes. If the endpoint is not reachable the Runner carries on running the Environment; the full transcript stays in the Run Context.
- The receiver derives all metrics from the stored spans and logs. The exporter emits no OTLP metrics.
- While at least one client is connected, the receiver scrapes the model server's `/metrics` and `/slots` every few seconds. If the model server is unreachable the Console shows its state as unavailable and nothing else breaks.
- Endpoint and model server URL come from the standard `OTEL_EXPORTER_OTLP_ENDPOINT` and a Console setting, not from the core's config.

## Core changes: richer events

- Existing event kinds and fields are unchanged (the Records contract keeps its shape and spawn-per-event call); fields are only added, so `bin/follow` keeps working.
- Each Run, loop, attempt and Activity emits `started` and `finished` events with `id` and `parent`; `finished` carries `duration` and the outcome.
- `task-received` when the Factory takes the Task from the Event Source (spec 0009: before it waits for its turn, followed by `task-status` `todo`), and `task-status` on every status the core writes to the Task Store, so the Console never queries the Task Store.
- The Agent event carries model turns, tool calls and tokens when the session provides them.
- The Run Context for a retry keeps its Pi session as before; the core computes the `traceparent` for each attempt.

## Deployment

- The receiver is a Quadlet container beside the Factory (`console.container` and its data volume) on `asf-net`. It exposes OTLP to the Factory and the Runner on that network and the API on host loopback only. Its store is one file under the Factory's data folder.
- `factory.env` gains `OTEL_EXPORTER_OTLP_ENDPOINT`, and the deployment's Records command points at the OTLP implementation.
- `bin/model` starts `llama-server` with `--metrics`.
- The TUI runs on the host as `bin/console`: Python and Textual, a dependency of `console/` only, sharing no code with `src/factory`.
- `bin/follow` is removed in the commit that makes the Task view cover what it shows.

## Implementation Decisions

- `console/` is its own program. Its only contract with the core is the event format, documented in `docs/adapters/README.md`, and the standard OTLP.
- A down receiver is an infrastructure error for the Records call: the Task is Blocked with reason `infrastructure` and no Run is used. The store is the audit trail, and copying its file backs it up.
- `GLOSSARY.md` gains **Console**. The other terms are the project's existing ones.
- The Console parses Pi's session JSONL format; a Pi change to it breaks the Console, which is accepted for the experiment.
- No retention or rotation.

## Testing Decisions

- Core: black-box Runs against the stand-in as in `tests/test_runs.py`: events carry `id`, `parent`, `started` and `finished` with duration; a `task-status` follows every status change; `task-received` is recorded; existing event kinds are unchanged; the Runner stand-in receives the `traceparent`.
- OTLP Records implementation: conformance for the Records port, plus a test that a `started` event arrives as a log and a `finished` one as a span with the same ids, and that an unreachable receiver is an error.
- Runner: a transcript written during a fake Environment is forwarded in order; an unreachable endpoint does not fail the run.
- Receiver: recorded fixtures (a green Task, a Task Blocked by an exhausted loop, a failed integration with a retry); assert on API responses: Task list, a Task's tree, the metrics figures, the live stream delivering new data, a running Activity shown before it finishes.
- TUI: against a stub API, the three views render from the payloads; an empty receiver gives empty views, not errors.

## Out of Scope

- Controlling the Factory from the Console: retrying, unblocking, creating or editing Tasks.
- A web view, authentication and remote access.
- Alerting and notifications.
- Retention and rotation of the store.
- A stock OpenTelemetry Collector, Tempo, Prometheus or Grafana.
- Judging the quality of results (rubrics for an external evaluator, still open in `docs/design.md`).
- Reconciling Task status against the Task Store when the Factory restarts (a known gap in `docs/design.md`).
