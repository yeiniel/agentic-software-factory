---
status: draft
---

# Seam-tested products and the quality gate

## Problem Statement

The Factory core's internal model has stopped matching how it works (see the architecture review of 2026-10-21): Run Context assembly, verdict handling and the event vocabulary each live in several places. Rethinking the core's internals is only safe if the tests pin what the core does at its seams and fail only when that behaviour changes. Today:

- The core is already driven as a process through its Adapters (`tests/test_runs.py`, `tests/test_events.py`), but `tests/test_verdict.py` imports `factory.verdict`, and `tests/test_runs.py` asserts by counting Adapter calls (`2 + 2 + 4 + 1 + 4`), so a layout change breaks tests without any behaviour changing.
- Measured on the existing suite, `src/factory` has 92% line-plus-branch coverage (21 lines and 14 branches missed). Every missed line is reachable by making an Adapter misbehave, except `ContextStore.get`'s missing-Context branch, which nothing in the core reaches.
- The Console tests import `Receiver`, `Store` and `ModelServer` directly.
- The repo has no linter, formatter, type checker, dead-code check, dependency audit, shell or Containerfile analysis, git hook or CI. `mise.toml` pins only `uv`.
- A test that is skipped hides behaviour behind a green run, and a leaked container fails a test only by accident.

## Solution

Every product in the monorepo is tested only through its own seam, held to 100% line and branch coverage measured through that seam, and checked by strict static and dynamic analysis. One command, `make check`, is the gate; a git pre-commit hook runs it in full.

### Products and their seams

| Product | Seam: what a test may touch |
|---|---|
| Factory core (`src/factory`) | The Adapter ports it calls (Event Source, Task Store, Repo Host, Runner, Records) and the Run Contexts it writes for the Runner; the process exit status and stderr. |
| Adapters (`adapters/`) | The executable's command line and stdin in, JSON on stdout and exit status out, plus the external system each one fronts (git, Podman, the Task Store's git issues, OTLP endpoint). The conformance suites stay. |
| Console (`console/`) | OTLP over HTTP into the receiver, the model server's metrics endpoint it polls, and the TUI as rendered by Textual's Pilot. |
| Git server, images, `bin/`, `deploy/` | The scripts' command lines and the files, hooks and containers they produce. |

No test imports the internals of a module that has a single caller (ADR 0018). A module shared inside a product, or between products, has an interface of its own and may have unit tests that enter through it (for example the Adapter wire format or the OTLP encoding, if more than one executable uses them). A test is a named scenario: "when X happens at a seam, the product does Y". Names state the behaviour, for example `test_a_validation_that_times_out_is_retried_with_feedback`.

### Golden transcripts

For the core, the assertion of a scenario is its golden transcript: the ordered Adapter calls (port, operation, arguments, body) plus the Records stream and the Run Contexts written, as one file per scenario in `tests/goldens/`. Only what is genuinely nondeterministic is normalised: timestamps, trace and span ids, Context paths (relative to the root), commit ids (stable labels), and the order of the two parallel Agents within a concurrent step. Hand-written assertions remain only for what a transcript cannot say (for example the real git contents of `main`). `UPDATE_GOLDENS=1` regenerates, and the diff is reviewed like code. The call-count arithmetic in `test_runs.py` is dropped. The Records stream in the goldens also pins the vocabulary the Console depends on.

### Coverage

- 100% line and 100% branch of every Python product, measured through subprocesses (`coverage` with `patch = ["subprocess"]`, `branch`, parallel data, `combine`, `fail_under = 100`).
- No `# pragma: no cover` and no omit lists. Code no scenario can reach through a seam is deleted. Every gap gets a scenario that reaches it.
- A check that every Adapter appears in the combined coverage data, because an Adapter that no test runs would otherwise be absent from the report.

Gap scenarios for the core (from the baseline measurement):

- *Adapters misbehaving:* an Adapter that cannot be started; one that exceeds its deadline; one that exits non-zero; one that prints invalid JSON; a streaming Event Source that prints an invalid JSON line, prints blank lines, exits non-zero, or is still running when the Factory stops.
- *Event handling:* the Event Source fails (the Factory exits non-zero); a main-push whose Record cannot be written (reported on stderr, serving continues); an event of an unknown type (ignored).
- *Run:* an infrastructure error that cannot be reported to the Task Store; validation and integration of a repository that has a Containerfile; a validation that times out; an integrator that times out; main moving on every integration attempt until the Factory gives up.
- *Verdicts* (replacing `test_verdict.py`): the Runner returns a verdict with a malformed `result`, with no `output`, for each valid `failed_check`, and for an unknown one.

### Static analysis

All gating from day one, with no baseline files. Versions and trade-offs are in `docs/research/2026-10-python-tooling.md`.

| Area | Tool |
|---|---|
| Python lint and format | ruff, `select = ["ALL"]` with a short ignore list, version pinned |
| Python types | pyright, strict mode |
| Dead code | vulture |
| POSIX shell (14 scripts) | shellcheck in POSIX mode, shfmt |
| Containerfiles | hadolint |
| Quadlet units | the Quadlet dry-run through Podman's generator |
| Docs | lychee, offline link check |
| Dependency vulnerabilities | `uv audit`, as a separate `make audit` because it needs the network |

Tools other than Python packages are pinned in `mise.toml`. The repo becomes one uv workspace (members `factory`, `console`, `adapters`) with a single lock file and a single tool configuration.

### Adapters become typed modules

Each Adapter keeps its executable name and its interface (ADR 0013). Its logic moves into a normal Python module next to it, and the executable becomes a one-line launcher. The tools above then see the logic as ordinary code (ruff, pyright, vulture, coverage and mutation testing all skip extension-less files by default).

### Dynamic analysis

- Every Python test run uses strict pytest configuration, `filterwarnings = error`, Python dev mode and a per-test timeout, so a leaked process, file or socket fails the test that leaked it. No test depends on the machine's leftover containers.
- A skipped test fails the gate in check mode, including the tests that need Podman.
- Property-based tests (Hypothesis) at the wire seams: each Adapter's command line and JSON, the OTLP receiver (the only network-facing listener), and the Pi session lines the Runner and the Console decode.
- Mutation testing (cosmic-ray, on the core) is a separate `make mutate` that reports surviving mutants and does not gate, because the black-box suite takes about three minutes per run.

### The gate

`make check` runs formatting, lint, types, dead code, the shell, Containerfile, Quadlet and link checks, and the tests with coverage. A git pre-commit hook runs it: a plain `core.hooksPath` script running `mise exec -- make check`, installed by `make hooks`. Without a git remote there is no CI to configure; a CI job later is one line.

## Order of work

1. The workspace, the tool configuration, the coverage measurement and the golden harness, on the existing scenarios.
2. Re-express `test_verdict.py` as scenarios and delete it; move the Console tests onto their seam.
3. Add the gap scenarios, and delete any dead code they show.
4. Restructure the Adapters into modules with launchers.
5. Turn on the gates, ending with `fail_under = 100`.

No refactor of the core's internals starts before step 5 is green.

## Out of Scope

- Rethinking the core's internals (the candidates of the architecture review); this spec only makes that safe.
- A CI service and the dependency audit in the hook.
- Anything that changes behaviour at a seam, except deleting code no scenario reaches.

## Open Questions

- Which modules are shared, and so get their own unit tests (ADR 0018), is decided as the Adapters are restructured: candidates are the Adapter wire format, the OTLP encoding and the Pi session parsing.
- Whether `pyrefly` should replace pyright later (stable, but less proven in strict mode).
- How the Hypothesis tests reach the Adapters' command lines (through the launchers as subprocesses is slow; the property tests may need a faster in-process route that is still the Adapter's seam).
