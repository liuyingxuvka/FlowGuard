---
name: flowguard-field-lifecycle-mesh
description: Use when a FlowGuard change adds, removes, renames, migrates, externalizes, replaces, preserves, or audits fields, schema keys, config flags, prompt/config fields, payload columns, persisted attributes, or compatibility field aliases.
---

# FlowGuard FieldLifecycleMesh

Standalone FlowGuard satellite skill for field-level coverage. Use it to account
all discovered fields at leaf level, project behavior-bearing fields into
model/code/test obligations, and close old-field disposition before broad
confidence claims.

Return to `model-first-function-flow` when the behavior model is missing. Pair
this route with Model-Test Alignment, Code Structure Recommendation, Model-Miss
Review, DevelopmentProcessFlow, Architecture Reduction, and Closure Contract
when their evidence is needed.

## First Read

- Route id: `field_lifecycle_mesh`.
- Core helpers: `FieldLifecyclePlan`, `FieldLifecycleGroup`,
  `FieldLifecycleRow`, `FieldProjection`, `review_field_lifecycle()`,
  `field_lifecycle_to_model_obligations()`, and
  `field_lifecycle_to_code_contracts()`.
- Template: `field-lifecycle-template`.
- Reference: `references/field_lifecycle_mesh_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep the AGENTS.md managed block/version record current for real projects.
- Do not create a fake mini-framework.
- Do not put every field into the high-level behavior model. Account every
  field in leaf rows, then project only behavior-bearing fields upward.
- Default replacement means cleanup. Old fields, aliases, fallbacks, wrappers,
  and compatibility-like fields need a deleted, blocked, migrated, delegated,
  same-contract repaired, explicitly preserved, or out-of-scope disposition.
- Explicit preservation requires compatibility intent and current evidence.
- Field inventory is not proof. Behavior claims still need model obligations,
  owner code contracts, tests, freshness, and closure evidence.

## Minimum Workflow

1. Name the field boundary and discovered field ids.
2. Group fields into parent/child field groups so the high-level view stays
   readable and the leaf view remains complete.
3. Add a `FieldLifecycleRow` for every discovered field.
4. Project behavior-bearing fields with `FieldProjection` rows.
5. Close old/replaced/deprecated field disposition or block full confidence.
6. Send projections and disposition rows to the owning downstream routes.

## Snapshot

Show parent field groups, leaf field rows, behavior-bearing projections, old
field dispositions, and downstream route handoffs.

## Non-Goals

- Do not replace Model-Test Alignment, TestMesh, Architecture Reduction,
  Model-Miss Review, DevelopmentProcessFlow, or Closure Contract.
- Do not treat scoped-out display or metadata fields as behavior proof.
