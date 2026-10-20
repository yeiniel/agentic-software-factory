---
status: accepted
---

# Validating the specs is separate from integrating, and retries are nested loops

Checking that the new specs are red on the base judges the Acceptance Writer's work, not an integration step, so it is its own deterministic process, Acceptance Test Validation, with its own Run Context and `run` script (a core resource, as in ADR 0015). It needs only the base and the Writer's branch, so it runs as soon as the Writer is recorded, in parallel with the Implementor. The Integrator keeps combining the branches and running the full suite. We chose this over one script with two modes because a failed validation is the Writer's failure by construction and needs no blame logic, and because a Writer fault no longer waits for the Implementor to finish before it is found.

Retries become nested loops. The outer loop is the Run, capped at 2 per Task: a failed integration costs a Run. Inside a Run, a Writer loop (the Acceptance Writer, then Acceptance Test Validation) and an Implementor loop run in parallel, each with its own attempt budget (2 by default) that resets every time a Run enters it, so two Runs can run the Writer four times. A Writer attempt fails when the Agent crashes or times out or its specs fail validation; an Implementor attempt fails only when the Agent crashes or times out, because whether its code is right is only judged at integration. Exhausting either budget makes the Task Blocked, with the exhausted budget in its history, and nothing is integrated. A failed integration retriggers only the Implementor; the earlier rule that also retriggered the Writer after two identical failures is dropped, since the cap of 2 Runs meant it could never fire. A loop that succeeded keeps its branch in the next Run and is not re-entered. We chose this over a single cap of 2 Runs because that was too restrictive when a Run can stop before it reaches integration, and over a separate integration budget because the Run cap already bounds integration retries.

A retried Agent starts again from the initial code (its branch is reset to the base and the clone is fresh) but resumes its Pi session, and its prompt says so. Continuing from its own previous work, as `docs/design.md` used to say, keeps a failed attempt's edits in the way; the session already holds the story of what was tried, so the Feedback carries no diff.

## Considered Options

- One Integrator script with two modes: fewer files, but validation keeps depending on integration inputs and a Writer fault still hides behind a slow Implementor.
- Checking that the Writer touched only test files: rejected, because which files are tests cannot be decided the same way for every repository. The red-on-base check still rejects a Writer whose code change makes its own specs pass.
- A global cap only: simple, but a hung Agent in Run 1 used a Run and kept the Writer's retry from ever happening.

## Consequences

- Known gaps: a Writer that changes unrelated code alongside valid specs gets that change integrated, and specs that are red on base but wrong end the Task Blocked for a human.
- Retries cost more time per attempt, since the Agent redoes its work from the base; the budgets bound the worst case to four runs of each Agent over two Runs.
- Infrastructure errors stay outside every budget, and so does the retry when `main` moves during integration.
- The Factory's config gains `writer_attempts` and `implementor_attempts` next to `max_runs`.
