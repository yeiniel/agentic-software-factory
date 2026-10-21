---
status: accepted
---

# Products are tested at their seams

Every product in the monorepo (the Factory core, the Adapters, the Console, the git server, the images, `bin/` and `deploy/`) is tested through its own seam: the interface a caller or a neighbouring product uses. For the core that is the Adapter ports and the Run Contexts it writes; for an Adapter, its command line, stdin, stdout and exit status; for the Console, OTLP over HTTP and the TUI. A test is a scenario: when something happens at the seam, the product does something at the seam. Coverage of 100% (lines and branches) is measured through those scenarios, so code that no scenario can reach through a seam is dead and is deleted.

A module shared inside a product, used by more than one other module or by more than one product, has an interface of its own, and that interface is a seam too. It may have unit tests that enter through it. Such a test fails only when the shared module's behaviour changes, which is what its callers rely on. A module with a single caller is not shared: its behaviour is tested through its caller's seam, and it gets no unit tests of its own. Where a module becomes shared, its unit tests may be added then.

## Considered Options

- Allow tests of any internal module: they pin the current decomposition, so reorganising a product's internals breaks tests while no behaviour has changed. This is what makes a rethink of the core's internals expensive.
- Allow tests only at the outermost seam, with no unit tests anywhere: it leaves shared modules such as the OTLP encoding or the Adapter wire format to be tested only indirectly, through each of their callers, and a failure shows in several places.

## Consequences

- Tests that import internals of a single-caller module are rewritten as scenarios at the product's seam and then deleted (for example `tests/test_verdict.py`, and the Console tests that import `Store`, `Receiver` and `ModelServer`).
- Spec 0007 holds the tooling and the gate that enforce this: coverage gated at 100% with no `# pragma: no cover`, golden transcripts for the core's scenarios, strict static analysis.
- Making a module shared is a design decision with a cost: it now has an interface that is tested and has to stay stable. Splitting a single-caller module out only for testability is not a reason.
