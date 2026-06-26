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

Use this skill for its declared flowguard workflow while binding each run to a route, evidence, checks, and a bounded completion claim.

## Entrypoint Scope

The entrypoint covers the installed flowguard-contract-exhaustion-mesh skill and the local materials explicitly routed by its instructions. It does not expand to unrelated repositories, private files, external services, publication, or release claims unless the user request and skill workflow explicitly include them.

## Local Material Routing

Resolve local materials from the active workspace, this skill directory, user-provided files, or explicitly configured project paths. Treat private machine paths as local-only inputs and keep public-facing instructions portable.

## Entrypoint Acceptance Map

A valid run selects one declared route, follows the phase order, records direct evidence, runs required checks, reports blockers and failures, and closes only inside the claim boundary. Available routes: model preflight, process review, evidence alignment, closure.

## Use When

Use when the user request matches the flowguard-contract-exhaustion-mesh activation boundary and needs this skill's governed workflow, source material, checks, or handoff behavior.

## Do Not Use When

Do not use when the task is outside this skill's domain, when required local materials are unavailable, when another more specific skill owns the request, or when the user asks only for a tiny direct answer.

## Required Workflow

Select the route, inspect local materials, perform the work in phase order, collect direct evidence, run the required checks, fix failures, and only then report progress or completion.

## Output Requirements

When reporting, include evidence, failures, blockers, skipped_checks with reasons, residual_risk, and claim_boundary. State clearly what was checked, what was not checked, and what remains blocked or uncertain.

## SkillGuard Maintenance

Keep the `.skillguard` control root, work contract, check manifest, check scripts, evidence records, and progress ledger current. Re-run SkillGuard checks after changing this entrypoint, route behavior, evidence rules, or closure wording.

<!-- END SKILLGUARD CONTRACT LAYER -->
