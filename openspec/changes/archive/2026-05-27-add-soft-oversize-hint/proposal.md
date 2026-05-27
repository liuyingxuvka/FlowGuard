## Why

FlowGuard now has sibling mesh routes for large models, tests, and code
structure. Agents still need a light reminder to consider those routes when an
artifact is becoming large, slow, or hard to follow.

This reminder must stay soft. It should not add timing thresholds, forced
splits, hard gates, or dependency on any external planner. Public Skill text
should remain generic and portable across machines.

## What Changes

- Add a short "consider a parent/child split" hint to the Skill Kernel.
- Keep the hint generic: models, tests, scripts, modules, and long commands.
- Route suggestions stay lightweight: ModelMesh, TestMesh, StructureMesh, and
  LongCheck are options to consider.
- Replace public Skill wording that names a specific external planner with a
  generic optional planning/spec artifact reference.
- Add focused tests that keep the hint soft and generic.

## Impact

- Skill/docs/tests only.
- No new runtime API, schema change, dependency, or hard rule.
- Local install, global Skill copy, and shadow workspace should be resynced
  after validation.
