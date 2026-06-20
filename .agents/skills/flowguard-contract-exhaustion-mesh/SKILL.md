---
name: flowguard-contract-exhaustion-mesh
description: Use when FlowGuard must generate canonical bad cases from declared finite boundaries, same-class families, payloads, transitions, mesh closure, coverage universes, or backfeed.
---

# FlowGuard ContractExhaustionMesh

Standalone FlowGuard satellite skill for canonical coverage from a declared finite boundary, family, payload, transition, parent/child contract, or universe. Return to `model-first-function-flow` when unclear.

## First Read

- Route: `contract_exhaustion_mesh`.
- Starter: `ROUTE_STARTER_API["contract_exhaustion_mesh"]`.
- Core helpers: `ContractDimension`, `ContractMutationCase`, `ContractCoverageUniverse`, `ContractOracle`, `ContractFaultProfile`, `ObservedProblemBackfeed`, `ContractExhaustionPlan`, `review_contract_exhaustion()`.
- Projection helpers: feeder converters, `contract_fault_profiles_from_report()`, `review_observed_problem_backfeed()`, and contract-exhaustion projections to MTA/TestMesh/ModelMesh/RiskLedger.
- Reference: `references/contract_exhaustion_mesh_protocol.md`.

## Hard Gates

- Verify the real package and AGENTS.md managed records; no fake mini-framework.
- Do not invent cases from prose; first declare the declared finite boundary or seed.
- Cartesian coverage is model-scoped: declare model id, finite axes, interaction groups.
- Broad/full claims need `ContractCoverageUniverse`; missing items are model gaps unless scoped.
- Required cases need an oracle; reject/block/reissue/repair cases need actionable feedback fields.
- Hand-written same-class examples are seed evidence, not canonical coverage.
- Observed real misses map to generated, same-class, and receipt evidence or stay as gaps.
- `ContractFaultProfile` rows are synthetic rehearsal inputs, not live completion evidence.
- Matrix ready is not whole-chain ready; broad claims need handoff closure.
- Model-local Cartesian receipt is not parent closure; parent ModelMesh consumes child receipt ids.
- TestMesh owns shard evidence; Model-Test Alignment owns generated combination obligations.
- Unbounded dimensions must be split, bounded, or scoped.
- New/deepened routes need template harvest closure before broad claims.

## Minimum Workflow

1. Identify the owning route declaration.
2. Convert it to `ContractDimension`, feeder `ContractMutationCase`, or model-scoped axes/groups.
3. For broad/full claims, declare `ContractCoverageUniverse` and exclusions.
4. Run `review_contract_exhaustion()` and fix universe/model/oracle/feedback/receipt/shard/backfeed gaps.
5. Project accepted cases to MTA, TestMesh, ModelMesh, and Risk Ledger.
6. Remove old fallback or hand-written same-class generators that duplicate it.

## Snapshot

Show universe -> case id -> oracle/fault profile -> observed-backfeed -> downstream route.

## Non-Goals

- Do not replace StateClosure, FieldLifecycleMesh, MTA, TestMesh, ModelMesh, ModelMissReview, or RiskLedger.
- Do not run tests directly or claim all software bugs are covered.
