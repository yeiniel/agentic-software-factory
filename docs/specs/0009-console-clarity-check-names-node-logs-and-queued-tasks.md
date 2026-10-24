---
status: draft
---

# Console clarity: check names, per-node logs and queued Tasks

## Problem Statement

Three things make the Console hard to read.

1. **The outcome of a failed deterministic Activity is the bare name of the check that failed.** In the Task view a green `validate` reads `green` and a crashed Agent reads `crashed`, but a failed `integrate` reads `suite`, or `conflict`. The other outcomes say what happened (`timed-out`, `specs-not-red`, `max-runs`, `no-golden`, `main-moved`, `succeeded`, `exhausted`); `suite` and `conflict` and `merge` are nouns, so the one node that failed looks like the one without a result. The name comes from the Activity's script (`red suite`), through `failed_check` in the verdict, to the Activity's outcome (`src/factory/interpreter.py`), to the Graph's `red:<check>` transitions, the Feedback file names and the Console.
2. **The log pane of the Task view cannot be narrowed to a node.** It merges every Factory event and every Agent transcript of the Task. To read what `integrate` did (its output, the failing test) you read the whole Task's log. The cause is in the data: of the log records a Run produces, only the transcript lines carry the id of the span they belong to. The Factory's own events (`agent`, `attempt`, `validate`, `integrate`, `branch-recorded`, `feedback`, `run-finished`) carry the Task, the Run and the kind, but no span.

3. **A Task is invisible until it starts.** The Console learns of a Task from its `task-received` event, which the interpreter records when the Task begins (`src/factory/interpreter.py`), not when the Factory takes the Task from the Event Source. `serve` (`src/factory/factory.py`) keeps a Task that has to wait, because `task_concurrency` is reached or its repository is busy (ADR 0021), in memory only. A queue of four Tasks shows as one: the Tasks view's `todo` status can never appear, and an operator cannot tell a queued Task from one that was never submitted.

## Solution

1. **Name every check for what happened**, hyphenated like the outcomes that already exist: the outcome of a failed check is the check's name, and the name is a short statement. The three nouns are renamed; the statements stay.
2. **Every event carries the id of the span it belongs to**, and the Task view's log pane shows the log of the selected node: the node's own records if it is a leaf, and its descendants' as well if it is not.
3. **A Task is recorded when the Factory takes it**, with status `todo`, and keeps that status until its first Run starts.

## Check names

The rule: a check name is lower-case words joined by hyphens, and it says what failed or what was found, as `timed-out`, `specs-not-red` and `no-golden` already do. A noun alone does not.

| Script | Today | New | Meaning |
|---|---|---|---|
| validation | `merge` | `merge-failed` | the Acceptance Writer's branch does not merge onto base |
| validation | `specs-not-red` | `specs-not-red` | unchanged |
| integrator | `conflict` | `merge-conflict` | the Implementor's and Writer's branches conflict |
| integrator | `suite` | `suite-failed` | the acceptance suite is red on the integrated result |
| golden (experiment Graph) | `no-golden` | `no-golden` | unchanged |
| core | `timed-out` | `timed-out` | unchanged |

- The verdict, the Activity's outcome and the Console show the new name. The Graph's transitions are `red:merge-failed`, `red:merge-conflict` and `red:suite-failed`; the Graph notation `red:<check>` is not changed. The Feedback files are renamed to match (`feedback/suite-failed.md` and so on).
- Past records are not rewritten. A Task run before the change keeps `suite` in its history; the Console shows what was recorded.
- No other rename: the `outcome` words of Runs, loops and attempts (`green`, `red`, `succeeded`, `exhausted`) are unchanged.

## Per-node logs

- **Event ids.** Every event the core emits while a Run is executing carries `span`, the `id` of the innermost running span it belongs to: `agent`, `validate`, `integrate`, `fast-forward` and `branch-recorded` belong to their Activity; `attempt` belongs to its attempt; `run-started`, `run-finished` and `feedback` (which is recorded once the Run's span has ended) belong to the Run; `loop-feedback` and `loop-exhausted` belong to their loop. `task-received` and `task-status` belong to the Task and have none. Fields are only added; no event kind or existing field changes.
- **Selecting.** In the Task view, moving the cursor in the tree selects a node, and the log pane shows the records of that node. For a leaf (an Activity) these are the records whose `span` is its id plus, for an agentic Activity, its transcript lines. For a non-leaf (a Run, a loop, an attempt or a parallel region) these are the records of the node and of all its descendants, in time order, so selecting a Run shows everything the Run did.
- **Default.** With nothing selected, or with the Task's root selected, the pane shows the whole Task as it does today. The pane's title says what it is showing (`integrate, Run 2`) and a key (`Esc`) clears the selection.
- **Live.** The pane keeps following new records of the selected node and its descendants while the node runs; it does not jump when the selection changes inside the same node.
- **Receiver.** The log API takes an optional `span` and returns the records of that span and its descendants; the TUI sends the selected node's id. The receiver derives descendants from the stored spans.

## Queued Tasks

- **Receipt.** When `serve` takes a `task` event from the Event Source it records `task-received` (with the repository and the pinned Graph version, which does not change: the Graph is loaded once when the Factory starts, spec 0008) and `task-status` `todo`, before the Task is queued. Nothing else about when a Run starts changes.
- **Start.** When the Task begins, the interpreter records `running` with the first Run as today and no longer records `task-received`.
- **Console.** The Tasks view lists the queued Task with status `todo`, no Run and no current Activity, and its age counts from receipt. A Task started later does not change its `received` time. The Task view of a `todo` Task shows an empty tree.
- **Restart.** A Task recorded `todo` that the Factory never started (it stopped first) stays `todo` in the Console: reconciling Task status after a restart is the known gap in `docs/design.md` and is not changed here.
- **Events.** `task-received` and `task-status` belong to the Task and carry no `span` (see Per-node logs). The Records contract is unchanged; only the time of one event moves.

## Implementation Decisions

- The check-name rule belongs in `docs/adapters/README.md` (the verdict contract) and the Graph schema's description of `checks`, which today say only that a check is a name.
- A renamed check is Graph data (`checks`, `on`) and script text, not core logic: the interpreter already treats a check name as opaque. The core changes only for the event ids.
- The `span` id on events uses the id already generated for the span's `started` event, so no new identifier appears. The OTLP Records implementation sets it as the log record's span id, as it does for transcript lines, so the receiver's join is the one it already has.
- The default Graph and the experiment Graph (`implementor-golden`) are both updated; the golden script's `no-golden` is already a statement and does not change.
- `docs/specs/0006-factory-console.md` (the Task view and the Tasks view's `todo`), `docs/specs/0008-the-graph-as-versioned-data.md` (where the version is pinned) and `docs/design.md` (the failure descriptions that name a conflict or a red suite) are updated when this lands. The terms in `GLOSSARY.md` do not change.

## Testing Decisions

- Core, black-box Runs against the stand-in as in `tests/test_runs.py`: with `task_concurrency` 1 and three Tasks sent at once, `task-received` and `todo` are recorded for all three before the first Run finishes, in order of arrival, and each Task still starts its first Run only when its turn comes; a Task queued behind a busy repository is recorded the same way; a red suite and a conflict produce Activity outcomes `suite-failed` and `merge-conflict` and route to the Implementor with the matching Feedback; a validation merge failure produces `merge-failed` and routes to the Acceptance Writer; every event emitted inside a Run carries a `span` that equals the `id` of a `started` event of the same Run, and `task-received` and `task-status` carry none.
- Graph load: the shipped Graphs load, every `red:<check>` has a script that can report it, and a Feedback file exists for each routed check (`make check` already loads the shipped Graph).
- OTLP Records: an event with a `span` arrives as a log record with that span id; one without arrives without.
- Receiver, recorded fixtures: a Task with a failed integration; the log for the `integrate` node returns its records and nothing from the Agents; the log for the Run returns the records of every descendant in order; the log for a running Activity grows as records arrive.
- TUI against a stub API: selecting a leaf sends its id and shows its records; selecting a Run shows the merged records; `Esc` returns to the whole Task; the pane title names the selection.

## Out of Scope

- Renaming Run, loop or attempt outcomes, or changing the outcome list the Graph uses (`green`, `red`, `red:<check>`, `crashed`, `timed-out`, `exhausted`, `advanced`, `main-moved`).
- Rewriting the history of Tasks already recorded.
- Searching or filtering the log by text or severity, and any control of the Factory from the Console (spec 0006).
- Showing a Task's `blocked` reason in the tree; the Tasks view already shows it.
- Reordering or cancelling queued Tasks, and persisting the queue across a restart.

## Open Questions

None. The names are `merge-failed`, `merge-conflict` and `suite-failed`.
