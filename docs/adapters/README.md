# Adapter contracts

Each Adapter port is an external executable (ADR 0011). The Factory configures each as a command
prefix (`config.json`: `"adapters": {"repo-host": ["/path/to/exe", ...]}`) and calls

    <command...> <op> [--name value ...]

with an optional JSON body on stdin and a JSON object on stdout. A non-zero exit, unparseable
stdout or exceeding the deadline is an **infrastructure error**: the Task is set to blocked with
reason `infrastructure`, and the Run does not count toward the cap. All other failures (red
verdicts, Agent failures, timeouts reported by the Runner) are returned as data.

`repo` is passed to Repo Host and Environment Builder; `task` and `run` identify a Run.

## Conformance

`tests/conformance/` holds one suite per port. It runs against the scripted stand-ins by default; to test
another implementation set `ADAPTER_<PORT>` (e.g. `ADAPTER_REPO_HOST='cmd args'`) and, if its identifiers
differ, `ADAPTER_<PORT>_FIXTURE` (JSON overriding the defaults in `tests/conformance/conftest.py`).
The Repo Host suite mutates its repository, so use a disposable one. A real Event Source needs
`ADAPTER_EVENT_SOURCE_TRIGGER`, a shell command that makes it emit an event. The Runner suite checks the
shape of a green verdict only; forcing a red one is implementation-specific.

## Event Source

- `listen`: long-running; prints one JSON event per line: `{"type":"task","task":T,"repo":R}` or
  `{"type":"main-push","repo":R,"commit":C}`. When it exits 0 the Factory finishes queued work and exits.

## Task Store

- `get-prompt --task T` → `{"prompt": str}`
- `set-status --task T --status todo|running|done|blocked`, body optional: `{"commit"}` for done,
  `{"history":[...], "reason"?}` for blocked → `{}`

## Repo Host

- `main-head --repo R` → `{"commit"}`
- `create-branch --repo R --name N --base C` → `{"commit"}`
- `checkout --repo R (--branch B | --commit C) --dest DIR` → `{"commit"}`: a single-branch clone, no remote
- `record --repo R --branch N --from DIR` → `{"commit","changed"}`: commits the directory's changes onto the branch
- `fast-forward-main --repo R --branch N --expect-main C` → `{"advanced": bool, "head"}`; must not
  advance if `main` is no longer `C`

## Environment Builder

- `build --repo R --commit C --purpose agent|integrator` → `{"image"}`; cached per repo and commit

## Runner

The Run Context is a directory it provisions; the Factory only joins paths below it.

- `provision-context --kind implementor|acceptance-writer|integrator --task T --run N [--attempt K]`
  (`K` numbers fresh Integrator passes in the same Run; each needs a fresh directory), body
  `{"prompt","resume"}` for Agents → `{"context": DIR}`. Agents work in `DIR/work`; the Integrator
  finds `DIR/base`, `DIR/main`, `DIR/implementor`, `DIR/acceptance-writer` and leaves its result in `DIR/result`.
- `run-agent --image I --context DIR --task T --role R --timeout S` →
  `{"exit_status","timed_out","output","transcript"}`
- `run-integrator --image I --context DIR --timeout S` →
  `{"exit_status","timed_out","output","verdict":{"result":"green|red","failed_check":"specs-not-red|conflict|suite","spec_output"}}`
  (`failed_check` and `spec_output`, the output of the new specs alone, on red). `output` is the Acceptance Report, verbatim.

## Records

- `append --stream S [--run N]`, body: one JSON event → `{}`. Streams: `task/<id>` and `factory`.
