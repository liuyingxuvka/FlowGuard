---
name: flowguard-field-lifecycle-mesh
description: Use when a FlowGuard change adds, removes, renames, migrates, externalizes, replaces, preserves, or audits fields, schema keys, config flags, prompt/config fields, payload columns, or legacy or interface aliases.
---

# FlowGuard FieldLifecycleMesh

Standalone FlowGuard satellite skill for field-level coverage. It accounts
leaf fields, projects behavior-bearing fields, and closes old-field disposition
before broad confidence.

Return to `model-first-function-flow` when the behavior model is missing. Pair
with downstream evidence routes as needed.

## First Read

- Route id: `field_lifecycle_mesh`.
- Core helpers: `FieldLifecyclePlan`, `FieldLifecycleGroup`,
  `FieldLifecycleRow`, `FieldProjection`, `review_field_lifecycle()`,
  `field_lifecycle_to_model_obligations()`,
  `field_lifecycle_to_code_contracts()`.
- Contract exhaustion handoff: use `ContractDimension` when missing, empty,
  wrong-type, unknown enum, or old-field cases need canonical bad-case ids.
- Template: `field-lifecycle-template`.
- Reference: `references/field_lifecycle_mesh_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not
  create a fake mini-framework.
- Do not put every field into the high-level behavior model. Leaf rows account
  every field; only behavior-bearing fields project upward.
- Default replacement means cleanup. Old fields, aliases, fallbacks, wrappers,
  and compatibility-like fields need a concrete disposition.
- Explicit preservation requires compatibility intent and current evidence.
- Field inventory is not proof; behavior claims still need obligations, owner
  code contracts, tests, freshness, and closure evidence.
- FieldLifecycleMesh declares field boundaries and projections; ContractExhaustionMesh
  generates canonical malformed/missing/old-field case ids and oracle handoff.
- New/deepened models need template harvest closure before broad claims.

## Minimum Workflow

1. Name the field boundary and discovered field ids.
2. Group parent/child rows so the high-level view stays readable.
3. Add one `FieldLifecycleRow` per discovered field.
4. Project behavior-bearing fields with `FieldProjection` rows.
5. Send missing/empty/wrong-type/unknown/old-field cases to ContractExhaustionMesh.
6. Close old/replaced/deprecated field disposition or block full confidence.
7. Send projections, canonical case ids, and dispositions to downstream routes.

## Snapshot

Show parent groups, leaf rows, behavior-bearing projections,
contract-exhaustion case ids, old field dispositions, and route handoffs.
Status note: field boundary, projection, old-field disposition, gap, next handoff.

## Non-Goals

- Do not replace Model-Test Alignment, TestMesh, Architecture Reduction,
  Model-Miss Review, DevelopmentProcessFlow, or Closure Contract.
- Do not treat scoped-out display or metadata fields as behavior proof.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, current evidence, blockers, residual_risk, and claim_boundary.
## Entry Scope
Covers flowguard-field-lifecycle-mesh and explicitly routed local materials only; no unrelated repos, private paths, external services, publication, or release claims unless separately routed.
## Runtime Binding
SkillGuard is the contract executor around FlowGuard's native router/checker/model surface. Use native-integrated or hybrid mode when a route already exists; do not add a second execution path.
## Required Workflow
Select the FlowGuard-owned route, open or compile `.skillguard/work-contract.json`, start or update the run record, execute native model/check gates, refresh evidence, fix blockers, then close only from current checks.
## Hard Gates
Block skipped phases, stale or prose-only evidence, hollow contracts, quality downgrades, unresolved native-route conflicts, and completion claims with remaining blockers.
## Output
Report checked target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
