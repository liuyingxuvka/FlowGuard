---
name: flowguard-model-test-alignment
description: Use when FlowGuard obligations, tests, code contracts, or source audits need direct comparison.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for obligations, tests, owner
`CodeContract`s, source audits, boundary observations, payload evidence, and
field projections.

Return to `model-first-function-flow` when obligations are undefined. Do not invoke TestMesh, ModelMesh, or StructureMesh from this route.

## First Read

- Route id: `model_test_alignment`.
- Starter: `ROUTE_STARTER_API["model_test_alignment"]` and
  `model-test-alignment-template`.
- Full template covers source audit, boundary conformance, matrices, and reuse.
- Helpers: `review_model_test_alignment()`, `TransitionCoverageMatrix`,
  `CodeContract`, `ArtifactPayloadContract`,
  `contract_exhaustion_to_model_obligations()`.
- Similarity handoff: cite group ids plus shared/variant test obligations.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify the real package, keep AGENTS.md managed records current, and do not
  create a fake mini-framework.
- Tests cover declared obligations, not just helper/internal paths.
- Full confidence requires each obligation to bind an owner `CodeContract` and
  current external-contract test evidence.
- Transition coverage needs cells plus evidence targets, or scoped-out boundary.
- Behavior fields need FieldLifecycleMesh projection or scoped-out reason.
- Reused results need current `TestResultReuseTicket` and `ProofArtifactRef`.
- File/work-package claims need `ArtifactPayloadContract` plus real evidence.
- Same-class, payload, transition, and mesh-closure bad cases become canonical
  obligations only after projection to `ContractMutationCase`.
- Cartesian combination cases become obligations only after ContractExhaustionMesh
  projection and must cite the generated case id in current external tests.
- Source audit is support, not semantic proof; missing evidence is maintenance.
- New/deepened obligations need template harvest closure before broad claims.

## Minimum Workflow

1. List obligations, scenarios, invariants, hazards, transitions, and fields.
2. Project transition matrices into obligations when coverage is claimed.
3. Feed same-class, payload, transition, mesh-closure, or Cartesian groups
   through ContractExhaustionMesh and add resulting obligations.
4. Add owner code contracts, boundary observations, and same-contract tests.
5. Add synthetic payload cases for the real file/work-package surface.
6. Compare rows, classify gaps, and route split needs outward.

## Snapshot

Snapshot: model obligation -> code contract -> test evidence; edges mean covers, partially covers, contradicts, or lacks evidence.
Status: obligation, code/test evidence, missing or stale rows, next alignment step.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.

<!-- BEGIN SKILLGUARD CONTRACT LAYER -->
## Purpose
Bind this FlowGuard route to one work contract, native checks, evidence, blockers, residual_risk, and claim_boundary.
## Entrypoint Scope
Covers flowguard-model-test-alignment and routed local materials only; no unrelated repos, private paths, services, publication, or release claims unless separately routed.
## Local Material Routing
Use FlowGuard's native router, package/model checks, `.skillguard/work-contract.json`, check_manifest, and run records; keep public text portable.
## Entrypoint Acceptance Map
Mode is native-integrated/hybrid as declared; SkillGuard executes gates around the native owner and must not add a second execution route.
## Use When
Use when this skill is selected and the task needs governed route, evidence, check, handoff, or closure behavior.
## Do Not Use When
Do not use outside the skill domain, without required materials, when a more specific skill owns the work, or for tiny direct answers.
## Required Workflow
Select the FlowGuard-owned route, open/compile the contract, start/update run record, run native model/check gates, refresh evidence, fix blockers, then close from current checks.
## Hard Gates
Block skipped phases, stale/prose-only evidence, hollow contracts, quality downgrades, native-route conflicts, and completion claims with blockers.
## Output Requirements
Report target, route, evidence, failures, blockers, skipped_checks, residual_risk, and claim_boundary; separate checked facts from judgment.
## SkillGuard Maintenance
Refresh contracts, checks, evidence, and installed copies after entrypoint, route, evidence, or closure changes.
<!-- END SKILLGUARD CONTRACT LAYER -->
