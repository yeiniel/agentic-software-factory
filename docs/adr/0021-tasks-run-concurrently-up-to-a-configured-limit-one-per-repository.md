---
status: accepted
---

# Tasks run concurrently up to a configured limit, one per repository

The Factory runs up to `task_concurrency` Tasks at once (default 1, so nothing changes until it is raised). A Task received while the limit is reached, or while another Task of the same repository is in flight, waits; the oldest waiting Task that can start does, so a busy repository never holds up Tasks of others. The limit is the operator's to match to the model server: a Task in the default Graph keeps two Agents running at once, so the model server needs `task_concurrency` times that many slots (ADR 0008), and with fewer the Agents queue inside the server and hit their time limits. The Factory does not read the server's slot count.

One Task per repository at a time keeps what ADR 0020 relies on: `main` equals `base` for the whole Task, and the Integrator no longer rebases. Two Tasks of one repository in flight would make the second one's fast-forward refuse every time, and ADR 0020 gives that no retry. The Graph is unchanged and still describes one Task; the limit and the queue are the core's, not the Graph's.

This supersedes the premise in ADR 0020 and `docs/design.md` that Tasks run in sequence. It does not change a Task's own Runs, which stay in sequence, or the rule that only a human push can move `main` during a Task.

## Considered Options

- A queue per repository with a worker pool of its own: the same behaviour with more moving parts, and nothing in the experiments needs it.
- Rebasing the Integrator again so Tasks of one repository can overlap: it brings back the retry for a moved `main` that ADR 0020 removed, for a case no experiment has asked for.
- Reading the model server's slots and deriving the limit: a coupling between the core and one implementation of the server (ADR 0013).

## Consequences

- `task_concurrency` is a Factory config field, a whole number of at least 1; the Factory refuses to start on anything else.
- Task ids are already the key of Run Contexts, branches, sessions and traces, so concurrent Tasks do not share any of them; the Adapters already take a lock around the shared git mirrors.
- The Console shows several Tasks running at once; its views are per Task and need no change.
