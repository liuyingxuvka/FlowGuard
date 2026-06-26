---
name: flowguard-field-lifecycle-mesh
description: Use when a FlowGuard change adds, removes, renames, migrates, externalizes, replaces, preserves, or audits fields, schema keys, config flags, prompt/config fields, payload columns, or compatibility aliases.
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

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-field-lifecycle-mesh skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-field-lifecycle-mesh activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
