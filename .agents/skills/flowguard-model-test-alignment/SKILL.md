---
name: flowguard-model-test-alignment
description: Use when model obligations, owner external CodeContracts, source audits, transition cells, boundary observations, payload cases, closure targets, or ordinary test evidence need direct current comparison.
---

# FlowGuard Model-Test Alignment

## Purpose
Compare declared model obligations, owner code external contracts, and current test evidence for the same behavior without owning test/code/model partitioning.

## Entrypoint Scope
Route id: `model_test_alignment`; role: `public_owner`; native owner: `model_test_alignment`. This standalone FlowGuard satellite skill owns alignment rows; it sends large/slow evidence to TestMesh through a typed handoff while TestMesh retains its own execution and freshness authority.

## Local Material Routing
Read `references/model_test_alignment_protocol.md` for `CodeContract`, `ArtifactPayloadContract`, source audits, transition/leaf matrices, closure targets, and binding rows.

## Entrypoint Acceptance Map
Accept explicit obligations, owner contracts, and evidence; compare bindings/freshness; block missing external-contract proof, stale audits, or orphan/duplicate rows; hand evidence hierarchy, model gaps, and final risk decisions to typed owners.

## Use When
- Use for model-code-test coverage, transition/closure cells, field projections, real-code boundaries, counterexample targets, or file/generated/AI work-package payload evidence.

## Do Not Use When
- Do not split tests, code, or models, run mesh ownership, or replace conformance replay; return undefined obligations to `model-first-function-flow`.

## Required Workflow
1. List obligations, commitment ids, transitions/fields/payloads, owner `CodeContract` rows, and required evidence kinds.
2. Consume canonical ContractExhaustionMesh ids, source/boundary observations, and current test evidence; build `ModelCodeTestBindingRow` closure summaries.
3. Classify gaps and issue typed TestMesh, maturation, risk-ledger, or closure handoffs.

## Hard Gates
- Verify the real FlowGuard check engine and AGENTS.md managed record; never create a fake mini-framework.
- Full confidence requires each required obligation to bind one owner external code contract and current same-contract test evidence.
- Missing/stale/skipped/source-audit/payload/target evidence or template harvest closure blocks broad alignment; large evidence may be delegated, never silently counted.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, and `typed_next_actions`, plus coverage bindings and open gap codes.

## SkillGuard Maintenance
- Edit `.skillguard/contract-source.json`, then regenerate derived contracts; SkillGuard checks native alignment parity and cannot run TestMesh or manufacture code/test proof.
