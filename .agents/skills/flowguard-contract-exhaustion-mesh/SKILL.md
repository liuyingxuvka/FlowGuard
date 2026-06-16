---
name: flowguard-contract-exhaustion-mesh
description: Use when FlowGuard must generate canonical bad cases from declared finite boundaries, same-class families, fields, payloads, transitions, mesh closure, no-delta loops, or absorb hand-written analogous-bug paths.
---

# FlowGuard ContractExhaustionMesh

Standalone FlowGuard satellite skill for canonical coverage from a declared
finite boundary, family, payload, transition, or parent/child contract. Return
to `model-first-function-flow` when the risky behavior boundary is unclear.

## First Read

- Route id: `contract_exhaustion_mesh`.
- Starter: `ROUTE_STARTER_API["contract_exhaustion_mesh"]`.
- Core helpers: `ContractDimension`, `ContractAxis`,
  `ContractInteractionGroup`, `ContractMutationCase`,
  `ContractCombinationCase`, `ContractCoverageShard`,
  `ModelContractCoverageReceipt`, `ContractOracle`,
  `ContractExhaustionPlan`, `review_contract_exhaustion()`.
- Projection helpers: feeder-to-case converters plus
  `contract_exhaustion_to_model_obligations()`,
  `contract_exhaustion_to_test_mesh_cell_ids()`,
  `contract_exhaustion_to_test_mesh_shard_ids()`,
  `contract_exhaustion_to_coverage_receipt_ids()`,
  `contract_exhaustion_to_risk_gate_ids()`.
- Reference: `references/contract_exhaustion_mesh_protocol.md`.

## Hard Gates

- Verify the real package and AGENTS.md managed records; no fake mini-framework.
- Do not invent cases from prose; first declare the declared finite boundary or seed.
- Cartesian coverage is model-scoped. Declare the model id, finite axes, and
  interaction groups first; do not combine arbitrary project-wide fields.
- Required cases need an expected oracle reaction.
- Hand-written same-class examples are seed evidence, not canonical coverage.
- Matrix ready is not whole-chain ready; broad claims need handoff closure.
- Model-local Cartesian receipt is not parent closure; parent ModelMesh must
  consume child receipt ids before broad confidence.
- TestMesh owns shard evidence; Model-Test Alignment owns generated
  combination obligations.
- Unbounded dimensions must be split, bounded, or scoped.
- New/deepened route use needs template harvest closure before broad claims.

## Minimum Workflow

1. Identify the owning route declaration.
2. Convert it to `ContractDimension`, feeder `ContractMutationCase`, or
   model-scoped `ContractAxis` plus `ContractInteractionGroup`.
3. Run `review_contract_exhaustion()` and fix model/oracle/receipt/shard gaps.
4. Project accepted cases to MTA, TestMesh, ModelMesh, and Risk Ledger.
5. Remove old fallback or hand-written same-class generators that duplicate it.

## Snapshot

Show declared boundary -> canonical case id -> oracle -> downstream route.

## Non-Goals

- Do not replace StateClosure, FieldLifecycleMesh, MTA, TestMesh, ModelMesh,
  ModelMissReview, or Risk Evidence Ledger.
- Do not run tests directly or claim all software bugs are covered.
