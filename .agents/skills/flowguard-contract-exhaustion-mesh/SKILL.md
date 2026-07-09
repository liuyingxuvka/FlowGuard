---
name: flowguard-contract-exhaustion-mesh
description: Generate canonical bad cases from finite boundaries, families, payloads, transitions, mesh closure, universes, or feed.
---

# FlowGuard ContractExhaustionMesh

Standalone FlowGuard satellite skill for canonical coverage from a declared finite boundary, family, payload, transition, parent/child contract, or universe. Return to `model-first-function-flow` if unclear.

## First Read

- Route: `contract_exhaustion_mesh`.
- Starter: `ROUTE_STARTER_API["contract_exhaustion_mesh"]`.
- Core helpers: `ContractDimension`, `ContractMutationCase`, `ContractCoverageUniverse`, `ContractExhaustionPlan`, `review_contract_exhaustion()`.
- Reference: `references/contract_exhaustion_mesh_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Do not invent cases from prose; declare the finite boundary or seed.
- Cartesian coverage is model-scoped: model id, finite axes, interaction groups.
- Broad/full claims need `ContractCoverageUniverse`; missing items are gaps.
- Required cases need `ContractOracle`; reject/block/repair cases need feedback fields.
- Hand-written same-class examples are seeds, not canonical coverage.
- Real misses map to generated, same-class, and receipt evidence or stay gaps.
- Matrix ready is not whole-chain ready; broad claims need handoff.
- ModelMesh consumes child receipts; TestMesh owns shards; MTA owns generated obligations.
- New/deepened routes need template harvest closure.
- PPA single-path claims need intent, result, candidate surface/trigger/behavior, disposition, evidence axes; A-failed/B-succeeded examples are seeds.
- BCL broad claims add source, owner, evidence, dependency, path, PPA, release, change-mode, source-freshness, replacement, model-sync, TestMesh, and model-miss axes.

## Minimum Workflow

1. Identify the owning route declaration.
2. Convert it to `ContractDimension`, feeder `ContractMutationCase`, or axes/groups.
3. For broad/full claims, declare `ContractCoverageUniverse` and exclusions.
4. Run `review_contract_exhaustion()` and fix universe/model/oracle/feedback/receipt/shard gaps.
5. Project cases to MTA, TestMesh, ModelMesh, and Risk Ledger.
6. Remove old hand-written generators that duplicate canonical coverage.
7. For BCL, generate commitment coverage first, then let path-sensitive rows consume PPA coverage.
8. For PPA, prove primary failure cannot auto-return alternate success, then project ids.

## Snapshot

Show universe -> case id -> oracle/fault profile -> observed-backfeed -> downstream route. Status: boundary, cases, gaps, next.

## Non-Goals

- Do not replace sibling routes or RiskLedger.
- Do not run tests directly or claim all software bugs are covered.
