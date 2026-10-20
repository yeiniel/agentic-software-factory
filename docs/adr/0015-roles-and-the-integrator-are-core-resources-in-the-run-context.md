---
status: accepted
---

# Roles and the Integrator are core resources provisioned in the Run Context

A role is its instruction plus its skills, and the Integrator is its `run` script; all of them are resources versioned with the core. The core writes them into each Run Context (skills outside `cwd`, so they never reach a branch recorded from `cwd`), instead of baking them into an image layer. The agent harness layer is then identical for both roles and carries only Pi and its configuration, and the Integrator has no layer: it runs in the repo's own image.

This replaces the earlier "skills come with the Environment" rule. Baked-in skills made every skill edit change every image tag, let each Agent see the other role's skill (against ADR 0003), and kept role knowledge in the Environment. Skills about the toolchain or the harness may still be part of an Environment; role skills are not.

## Considered Options

- Keep role skills in the agent layer: simple, but couples the Environment to the roles and rebuilds images on every skill edit.
- Have the repo own the Acceptance Writer's skill, as `docs/design.md` once suggested: the repo's own `.agents/skills` still load from `cwd`, but the Factory cannot rely on a repo to teach the role.

## Consequences

- Moves `images/agent/skills` and `images/integrator/integrator.sh` into the core's resources.
- The core owns the Integrator's input names and the format of its result files, in one Verdict module.
