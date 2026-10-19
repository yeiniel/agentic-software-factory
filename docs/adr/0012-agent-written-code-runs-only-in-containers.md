# Agent-written code runs only in containers

Anything that executes code written by an Agent, including `make test` run by the Integrator, runs inside an Environment, never in the Factory container. The Factory holds the host's Podman socket (ADR 0010), so running untrusted code there would hand it host-level control. We rejected running `make test` in the Factory itself as simpler but unsafe; the cost is that the Integrator is its own container with its own tooling layer.
