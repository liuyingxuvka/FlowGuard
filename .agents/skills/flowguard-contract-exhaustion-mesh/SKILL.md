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
Status: boundary, cases, gaps, owner, next.

## Non-Goals

- Do not replace sibling routes or RiskLedger.
- Do not run tests directly or claim all software bugs are covered.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind each flowguard run to the declared integration mode, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-contract-exhaustion-mesh plus explicitly routed local materials; no unrelated repos, private files, external services, publication, or release claims unless requested and routed.
## Local Material Routing
Use workspace, skill directory, user files, or configured project paths; keep private machine paths local and public instructions portable.
## Entrypoint Acceptance Map
Use SkillGuard as the runtime contract executor attached to the native route/check owner: FlowGuard skill route map plus the real flowguard package/model checks. It enforces contract gates through that native owner before progress or closure; duplicate SkillGuard-owned execution paths are invalid. Declared gates/routes: model preflight, process review, evidence alignment, closure.
## Use When
Use when the request matches flowguard-contract-exhaustion-mesh and needs this governed workflow, materials, checks, or handoff behavior.
## Do Not Use When
Do not use outside the domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the target-owned native route/check surface, run the SkillGuard contract gates around the native workflow, collect evidence, run checks, fix failures, then report.
## Hard Gates
Do not skip phases, do not replace required evidence with prose, do not treat stale reports as current, do not weaken validation to pass, and do not claim completion when blockers remain.
## Output Requirements
Report evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary; distinguish checked, unchecked, blocked, and uncertain.
## SkillGuard Maintenance
Keep `.skillguard` contracts, checks, evidence, and ledger current; rerun SkillGuard after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
