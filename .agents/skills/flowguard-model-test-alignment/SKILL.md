---
name: flowguard-model-test-alignment
description: Use when obligations, tests, code contracts, or source audits need comparison.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for obligations, tests, owner `CodeContract`s, source audits, boundary observations, payloads, and fields. Return to `model-first-function-flow` when obligations are undefined. Do not invoke TestMesh, ModelMesh, or StructureMesh.

## First Read

- Route id: `model_test_alignment`.
- Starter: `ROUTE_STARTER_API["model_test_alignment"]`, `model-test-alignment-template`.
- Helpers: `review_model_test_alignment()`, `TransitionCoverageMatrix`, `CodeContract`, `ArtifactPayloadContract`.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify FlowGuard check engine and AGENTS.md managed records; no fake mini-framework.
- Tests cover declared obligations, not just helper/internal paths.
- Full confidence requires each obligation to bind an owner `CodeContract` and current external-contract test evidence.
- Broad behavior claims bind test/code/model rows to commitment ids, not only local model ids.
- BCL change-mode, source-freshness, replacement/model-sync, and model-miss cases bind to the same commitment id as repaired model obligation and owner code contract.
- Real code claims with paths/symbols require green `source_audit_reports` when `require_source_audit=True`.
- Counterexample repairs require target-aware replay/regression tests bound to owner code.
- Final claims cite `ModelCodeTestBindingRow` closure summaries and open gaps.
- Transition coverage needs cells plus evidence targets, or scoped-out boundary.
- Behavior fields need FieldLifecycleMesh projection or scoped-out reason.
- Reused results need current `TestResultReuseTicket` and `ProofArtifactRef`.
- File/work-package claims need `ArtifactPayloadContract` plus real evidence.
- Same-class, payload, transition, mesh-closure, and Cartesian bad cases require ContractExhaustionMesh projection.
- New/deepened obligations need template harvest closure.

## Minimum Workflow

1. List obligations, scenarios, hazards, transitions, fields, affected commitment ids.
2. Project transition matrices into obligations when coverage is claimed.
3. Feed finite bad-case groups through ContractExhaustionMesh, including BCL DCAR cases.
4. Add owner code contracts, boundary observations, same-contract tests, commitment-id bindings.
5. Add payload cases for the real file/work-package surface.
6. Compare rows, classify gaps, route split needs outward.

## Snapshot

Show coverage from model obligations to code contracts to tests; edges mean covers, partially covers, or leaves scoped gaps.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.
