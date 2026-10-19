# The Implementor and Acceptance Writer work blind, in parallel

Two Agents work on every Task at the same time, neither seeing the other's branch: the Implementor changes the code and the Acceptance Writer writes the acceptance specs, both from the Task prompt alone. The Integrator is the only place their work meets, which keeps the specs from being fitted to the code and the code from being fitted to the specs. This is the hypothesis the `experiment/parallel-implemen-write-acceptance` branch tests.

## Considered Options

- One Agent writes both code and specs: simplest, but it grades its own homework.
- Sequential test-first (Acceptance Writer, then Implementor): the Implementor sees the specs, and the roles can't run in parallel.
- A human writes the specs: strongest oracle, but it makes every Task wait on a human.

These are the baselines the experiment is compared against; if blindness proves too costly, the sequential option is the likeliest successor.
