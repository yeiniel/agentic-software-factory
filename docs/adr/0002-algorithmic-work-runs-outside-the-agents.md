# Algorithmic work runs outside the agents

Agents do only the work that needs judgment: writing code and writing acceptance specs. Everything algorithmic is plain code in the Factory: the task store, branching and committing, validating specs, integration, blame routing, Feedback construction, retry accounting and status updates. We chose this over letting agents orchestrate themselves because deterministic steps are cheaper, reproducible and testable, and an agent can't skip or misreport them. ADR 0001 is one consequence of this rule.
