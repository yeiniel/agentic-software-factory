---
status: accepted
---

# Observability data travels as OTLP

The Factory's records and the Agents' transcripts reach the Console as OpenTelemetry (OTLP over HTTP), not by the Console reading the Factory's files. Records stays a port (ADR 0013): the core keeps emitting events through it and knows nothing about OTLP. A Records implementation exports each event to the Console's receiver, which in that deployment is the system of record, so an unreachable receiver is an infrastructure error like any other Adapter failure. The Runner, which already runs outside the Environment for the whole Run, forwards the Pi session transcript as OTLP log records while the container runs; it takes one optional opaque trace context from the core to link them to the attempt. We chose a standard protocol so the same stream can be pointed at an OpenTelemetry Collector, Tempo or Grafana later without touching the core, and so a second front-end (a web view) is only another client.

## Considered Options

- The Console reads the Records and session files directly: the least machinery for a single machine, but it ties the Console to the Factory's file layout and to one machine, and gives up the standard.
- A full OpenTelemetry backend (Collector, Tempo, Prometheus, Grafana) now: generic UI and no code, but it has no Factory-specific view of Tasks, Runs and loops, and adds several services to a single-machine experiment.
- One Records implementation that writes JSONL and exports OTLP: rejected, because an Adapter is swappable and does one job. The JSONL implementation stays as the other Records implementation, for tests and for running without the Console.
- A Pi extension that pushes OTLP from inside the Environment: rejected, because it opens a network path from Agent code to the Console (ADR 0012).

## Consequences

- The Records contract stays one process spawn per event and only gains fields; the exporter is stateless, so a started Activity is exported as a log record and a finished one as a complete span.
- With the OTLP implementation configured, the receiver's store is the audit trail; there is no JSONL beside it. It is a file that can be copied to back it up.
- A down receiver blocks Tasks with reason `infrastructure`, without using a Run.
- The Runner's contract gains one optional argument, `--traceparent`, and no knowledge of roles or Tasks (ADR 0014).
- The Console parses Pi's session format, as `bin/follow` already does.
