# Environments are prebuilt containers

Every Agent runs in a container, the lowest level of isolation we accept: a local git worktree gives none, since an Agent runs arbitrary shell commands. The container is booted with as little left to do as possible: the repository clone, the prompt and all language-specific dependencies are already in place, so the Agent needs network access for little beyond its model server. The target repository supplies its own tech stack as a container definition file, so the Factory is tied to no container technology or language.

The first implementation runs them with rootless Podman. Egress is not restricted beyond what the container network gives it (it reaches the local model server, see ADR 0008); tightening that is left for later.
