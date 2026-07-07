---
name: flowguard-model-test-alignment
description: Use when FlowGuard obligations, tests, code contracts, or source audits need comparison.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for obligations, tests, owner
`CodeContract`s, source audits, boundary observations, payloads, and fields.

Return to `model-first-function-flow` when obligations are undefined. Do not invoke TestMesh, ModelMesh, or StructureMesh.

## First Read

- Route id: `model_test_alignment`.
- Starter: `ROUTE_STARTER_API["model_test_alignment"]` and
  `model-test-alignment-template`.
- Full template covers source audit, boundary conformance, matrices, and reuse.
- Helpers: `review_model_test_alignment()`, `TransitionCoverageMatrix`, `CodeContract`, `ArtifactPayloadContract`.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine, keep AGENTS.md managed records current, and do not create a fake mini-framework.
- Tests cover declared obligations, not just helper/internal paths.
- Full confidence requires each obligation to bind an owner `CodeContract` and current external-contract test evidence.
- Real Python code claims with paths/symbols require green `source_audit_reports` when `require_source_audit=True`.
- Counterexample and known-bad repairs require target-aware `counterexample_regression` or `known_bad_replay` tests bound to owner code.
- Final claims cite `ModelCodeTestBindingRow` closure summaries and their open gaps.
- Transition coverage needs cells plus evidence targets, or scoped-out boundary.
- Behavior fields need FieldLifecycleMesh projection or scoped-out reason.
- Reused results need current `TestResultReuseTicket` and `ProofArtifactRef`.
- File/work-package claims need `ArtifactPayloadContract` plus real evidence.
- Same-class, payload, transition, mesh-closure, and Cartesian bad cases require ContractExhaustionMesh projection.
- Source audit is support, not semantic proof; missing evidence is maintenance.
- New/deepened obligations need template harvest closure before broad claims.

## Minimum Workflow

1. List obligations, scenarios, hazards, transitions, and fields.
2. Project transition matrices into obligations when coverage is claimed.
3. Feed finite bad-case groups through ContractExhaustionMesh.
4. Add owner code contracts, boundary observations, and same-contract tests.
5. Add synthetic payload cases for the real file/work-package surface.
6. Compare rows, classify gaps, and route split needs outward.

## Snapshot

Show coverage from model obligations to code contracts to tests; edges mean covers, partially covers, or leaves scoped gaps.
Status note: obligation, code/test evidence, missing or stale rows, next alignment step.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.
