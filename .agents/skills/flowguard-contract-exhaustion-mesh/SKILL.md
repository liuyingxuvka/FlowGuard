---
name: flowguard-contract-exhaustion-mesh
description: Use when FlowGuard must generate canonical bad cases from declared finite boundaries, same-class bug families, field/schema contracts, payload evidence, transition cells, parent/child mesh closure, no-delta loops, or when older hand-written analogous-bug paths should be replaced by one clean contract-exhaustion route.
---

# FlowGuard ContractExhaustionMesh

Standalone FlowGuard satellite skill for canonical finite bad-case generation.
Use it after an owning route declares the real boundary, family, payload,
evidence, transition, or parent/child contract. Return to
`model-first-function-flow` when the risky behavior boundary itself is unclear.

## First Read

- Route id: `contract_exhaustion_mesh`.
- Starter: `ROUTE_STARTER_API["contract_exhaustion_mesh"]`.
- Core helpers: `ContractDimension`, `ContractMutationCase`,
  `ContractOracle`, `ContractExhaustionPlan`,
  `review_contract_exhaustion()`.
- Projection helpers: `state_closure_cases_to_contract_cases()`,
  `scenario_matrix_to_contract_cases()`,
  `family_bad_case_seed_to_contract_cases()`,
  `artifact_payload_cases_to_contract_cases()`,
  `transition_coverage_to_contract_cases()`,
  `model_mesh_closure_to_contract_cases()`,
  `contract_exhaustion_to_model_obligations()`,
  `contract_exhaustion_to_test_mesh_cell_ids()`,
  `contract_exhaustion_to_risk_gate_ids()`.
- Reference: `references/contract_exhaustion_mesh_protocol.md`.

## Hard Gates

- Verify the real package and keep AGENTS.md managed records current.
- Do not create a fake mini-framework.
- Do not invent bad cases from prose alone; first declare the declared finite boundary or family seed.
- Required cases need an expected oracle reaction.
- Hand-written same-class examples are seed evidence, not canonical coverage.
- Matrix ready is not whole-chain ready; broad claims need composite handoff acceptance closure.
- Unbounded dimensions must be split, bounded, or scoped.
- New/deepened route use needs template harvest closure before broad claims.

## Minimum Workflow

1. Identify the owning route declaration.
2. Convert it to `ContractDimension` or feeder-generated `ContractMutationCase`
   rows.
3. Run `review_contract_exhaustion()`.
4. Fix blocked model/oracle gaps before production edits or broad claims.
5. Project accepted cases to Model-Test Alignment, TestMesh, ModelMesh, and
   Risk Evidence Ledger as needed.
6. Remove old fallback or hand-written same-class generator paths that duplicate
   canonical case generation.

## Snapshot

Show declared boundary -> canonical case id -> oracle -> downstream route.

## Non-Goals

- Do not replace StateClosure, FieldLifecycleMesh, Model-Test Alignment,
  TestMesh, ModelMesh, ModelMissReview, or Risk Evidence Ledger.
- Do not run tests directly.
- Do not claim all software bugs are covered; only declared finite boundaries
  are exhausted.
